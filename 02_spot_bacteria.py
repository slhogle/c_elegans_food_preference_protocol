from opentrons import protocol_api
from opentrons import types
from itertools import combinations, zip_longest
from math import floor

metadata = {
    "protocolName": "C elegans food preference",
    "description": """This protocol spots 1 ul of different bacterial 
                   species in a cross orientation at the center of each well of a 
                   12 well plate. The goal of the experiment is to observe which bacteria 
                   spots the worms spend the most time at and hence prefer
                   as a food source.""",
    "author": "Shane Hogle"
}

requirements = {"robotType": "OT-2", "apiLevel": "2.16"}

# change the position of the pipette (left/right) if necessary
P20_SIDE = "left"

# Functions ####################################################################


def find(tp, a):
    """Get the position in tuple tp of value a"""
    for i, x in enumerate(tp):
        if x == a:
            return i


def n_clusters(iterable, n=2, fillvalue=None):
    """For clusters of size n, get the non overlapping cluster membership.
    For example [1, 2, 3, 4] returns [(1, 2), (3, 4)]"""
    return zip_longest(*[iter(iterable)]*n, fillvalue=fillvalue)


def if_used_fifty(well_idx, needs_new_tip):
    # if tip has been used 50 times then get a new tip
    if (well_idx + 1) % 50 == 0:
        return True
    else:
        return needs_new_tip


def get_new_tip_if(pipette, needs_new_tip):
    if needs_new_tip:
        if pipette.has_tip:
            pipette.drop_tip()
        pipette.pick_up_tip()
        return False


def get_volume_to_aspirate(pipette, remaining_vol, disposal_vol, spot_vol):
    # if we have less than enough volume then aspirate more
    if remaining_vol + disposal_vol > pipette.max_volume:
        asp_vol = floor((pipette.max_volume - disposal_vol*2) / spot_vol) * \
            spot_vol + disposal_vol - pipette.current_volume
    else:
        asp_vol = remaining_vol + disposal_vol - pipette.current_volume
    return asp_vol


def spot(pipette, well, x, y, z, spot_vol=2,
         safe_height=15, z_speed=50, spotting_dispense_rate=0.5):
    # move pipette to destination stopping tip at safe_height=15 mm above
    # the top center of the well.
    pipette.move_to(well.top(safe_height))
    # for safety, set the z-axis speed limit to 50 mm/s.
    pipette.default_speed = z_speed
    # dispense at a slower speed. default is 1 ul/sec
    pipette.dispense(volume=spot_vol, rate=spotting_dispense_rate)
    # Move pipette tip down to plate surface to let go of the drop. Before
    # running the protocol this should checked during labware position check
    # that 'well.top(0)' is right at the surface of the agar.
    pipette.move_to(well.center().move(types.Point(x=x, y=y, z=z)))
    # reset the max speed
    pipette.default_speed = None


def distribute_to_agar(pipette, spot_vol, source, destination, disposal_vol, orientation):
    needs_new_tip = True
    dest = list(destination)  # allows for non-lists
    for cnt, well in enumerate(dest):
        needs_new_tip = if_used_fifty(cnt, needs_new_tip)
        if pipette.current_volume < (spot_vol + disposal_vol):
            pipette.blow_out(pipette.trash_container)
            needs_new_tip = get_new_tip_if(pipette, needs_new_tip)

            # spot_vol volume below is multiplied by 2 because we place two spots
            # for each well below so we need twice the actual disposal volume

            # remaining_vol = (len(dest) - cnt) * spot_vol
            # asp_vol = get_volume_to_aspirate(pipette=pipette,
            #                                  remaining_vol=remaining_vol,
            #                                  disposal_vol=disposal_vol,
            #                                  spot_vol=spot_vol*2)

            # manually set the aspiration volume to 20 ul. For each species one block will require
            # 6 * 2 * x ul of bacteria where x is the ul of the spot volume. Any larger than a 1 ul
            # spot will require a refilling in the middle of a block.

            asp_vol = 20
            pipette.mix(repetitions=3,
                        volume=20,
                        location=source)
            pipette.aspirate(volume=asp_vol,
                             location=source)
            pipette.touch_tip(location=source)

        if orientation == 0:  # vertical
            spot(pipette=pipette,
                 well=well,
                 x=0, y=2, z=0,
                 spot_vol=spot_vol,
                 safe_height=15,
                 z_speed=50,
                 spotting_dispense_rate=0.1)
            spot(pipette=pipette,
                 well=well,
                 x=0, y=-2, z=0,
                 spot_vol=spot_vol,
                 safe_height=15,
                 z_speed=50,
                 spotting_dispense_rate=0.1)
        if orientation == 1:  # horizontal
            spot(pipette=pipette,
                 well=well,
                 x=2, y=0, z=0,
                 spot_vol=spot_vol,
                 safe_height=15,
                 z_speed=50,
                 spotting_dispense_rate=0.1)
            spot(pipette=pipette,
                 well=well,
                 x=-2, y=0, z=0,
                 spot_vol=spot_vol,
                 safe_height=15,
                 z_speed=50,
                 spotting_dispense_rate=0.1)
    pipette.drop_tip()


# Experiment specific stuff  ##################################################
# the species used in the experiment
species_names = ['OP50', 'anc_1287', 'anc_1977', 'evo_1287', 'evo_1977']
# numerical indexes for species
species = list(range(0, 5))
# generate all possible unique pairwise combinations of the species
combos = list(combinations(species, 2))
# number of plates needed, 2 combos per plate
no_plates = round(len(combos)/2)
# column pairings for the 12-well plates. Each 12-well plate holds 2 treatments
# with 6 replicates divided between the first and last 2 columns of the plate
cols = ((0, 1), (2, 3))

# Make the nested data structure holding information about which species go
# on which plates, in which columns, and in which orientation
sp_d = {}
for x in species:
    sp_d[x] = {}
    # the reason this works is that we use 2 columns and 3 rows per 12-well
    # plate to hold one species pairing (so 6 replicates per pairing).
    for i, j in enumerate(n_clusters(combos)):
        for k in [0, 1]:
            if j[k] is not None:
                if x in j[k]:
                    sp_d[x][j[k]] = [cols[k], i]


# Main body ####################################################################

def run(protocol: protocol_api.ProtocolContext):
    # Loading labware ##########################################################
    # pipette tips always in position 11
    tiprack = protocol.load_labware("opentrons_96_tiprack_20ul", 11)
    # bacteria source cultures always in position 10
    bacteria = protocol.load_labware(
        "corning_6_wellplate_16.8ml_flat", 10, label="bacteria cultures")
    # position of plates to be spotted
    spot_plate_pos = [i+1 for i in range(0, no_plates)]
    spot_plates = [protocol.load_labware(
        "corning_12_wellplate_6.9ml_flat", slot, label="agar Plates") for slot in spot_plate_pos]

    # specify the pipette
    p20_single = protocol.load_instrument(
        "p20_single_gen2", mount=P20_SIDE, tip_racks=[tiprack])

    for sp in species:
        protocol.comment(f'''
                         ############################################
                         ####### CHANGING SPECIES TO {species_names[sp]} #######
                         ############################################
                         ''')
        source_well = bacteria.wells()[sp]
        for pos_k, pos_v in sp_d[sp].items():
            if find(pos_k, sp) == 0:
                protocol.comment(f'''
                                 #################################################################
                                 Spotting {species_names[sp]} in vertical orientation for A{pos_v[0][0]+1} to C{pos_v[0][1]+1} of plate {pos_v[1]+1} 
                                 #################################################################
                                 ''')
                target_wells = []
                for col in pos_v[0]:
                    for well in spot_plates[pos_v[1]].columns()[col]:
                        target_wells.append(well)
                distribute_to_agar(pipette=p20_single,
                                   spot_vol=1,
                                   source=source_well,
                                   destination=target_wells,
                                   disposal_vol=5,
                                   orientation=0)
            if find(pos_k, sp) == 1:
                protocol.comment(f'''
                                 ###################################################################
                                 Spotting {species_names[sp]} in horizontal orientation for A{pos_v[0][0]+1} to C{pos_v[0][1]+1} of plate {pos_v[1]+1} 
                                 ###################################################################
                                 ''')
                target_wells = []
                for col in pos_v[0]:
                    for well in spot_plates[pos_v[1]].columns()[col]:
                        target_wells.append(well)
                distribute_to_agar(pipette=p20_single,
                                   spot_vol=1,
                                   source=source_well,
                                   destination=target_wells,
                                   disposal_vol=5,
                                   orientation=1)
