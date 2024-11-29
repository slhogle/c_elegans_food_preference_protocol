from opentrons import protocol_api
from opentrons import types

metadata = {
    "protocolName": "C elegans food preference",
    "description": """This protocol spots 1 ul of C elegans at the center of each well of a 12 well
                   a plate after rinsing the pipette tip with a solution of Triton X100.The goal of
                   the experiment is to observe which bacteria spots the worms spend the most time
                   at and hence prefer as a food source.""",
    "author": "Shane Hogle"
}

requirements = {"robotType": "OT-2", "apiLevel": "2.16"}

# Global vars

# change the position of the pipette (left/right) if necessary
P20_SIDE = "left"


# Functions ####################################################################


def triton_rinse(pipette, well, n_rinses=3, vol_rinses=20):
    pipette.mix(repetitions=n_rinses,
                volume=vol_rinses,
                location=well)


def get_new_tip_if(pipette, needs_new_tip):
    if needs_new_tip:
        if pipette.has_tip:
            pipette.drop_tip()
        pipette.pick_up_tip()
        return False


def spot(pipette, well, x, y, z, spot_vol=2,
         safe_height=15, z_speed=50, spotting_dispense_rate=0.1):
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


def distribute_to_agar(pipette, triton_well, worm_well, destinations,
                       n_rinses=3, vol_rinses=20, asp_vol=20, spot_vol=1):
    needs_new_tip = True
    needs_new_tip = get_new_tip_if(pipette, needs_new_tip)
    triton_rinse(pipette=pipette,
                 well=triton_well,
                 n_rinses=n_rinses,
                 vol_rinses=vol_rinses)
    pipette.aspirate(volume=asp_vol, location=worm_well)
    pipette.touch_tip(location=worm_well)
    for well in list(destinations):
        spot(pipette=pipette,
             well=well,
             x=0, y=0, z=0,
             spot_vol=spot_vol,
             safe_height=15,
             z_speed=50,
             spotting_dispense_rate=0.1)
    pipette.drop_tip()


def run(protocol: protocol_api.ProtocolContext):

    # number of plates to be spotted. Plates are in deck positions 1,2,3...
    no_plates = 5

    # Loading labware ##########################################################
    # pipette tips always in position 11
    tiprack = protocol.load_labware("opentrons_96_tiprack_20ul", 11)
    # Worms and rinse in position 10
    worms = protocol.load_labware(
        "corning_6_wellplate_16.8ml_flat", 10, label="c elegans")
    # position of plates to be spotted
    spot_plate_pos = [i+1 for i in range(0, no_plates)]
    spot_plates = [protocol.load_labware(
        "corning_12_wellplate_6.9ml_flat", slot, label="agar Plates") for slot in spot_plate_pos]
    # specify the pipette
    p20_single = protocol.load_instrument(
        "p20_single_gen2", mount=P20_SIDE, tip_racks=[tiprack])

    # define some variables #####################################################

    # well on the worm plate that has triton x rinse in m9. By default this is the
    # last well on the plate (i.e., B3)
    triton_well = worms.wells()[5]
    # Well on the worm plate that has the solution of L1 C elegans to be spotted.
    # By default this is the first well (i.e., A1)
    worm_well = worms.wells()[0]

    # Run the protocol ##########################################################

    for plate in spot_plates:
        chunk01 = [plate.wells()[well] for well in range(0, 6)]
        chunk02 = [plate.wells()[well] for well in range(6, 12)]
        for chunk in [chunk01, chunk02]:
            distribute_to_agar(pipette=p20_single, triton_well=triton_well,
                               worm_well=worm_well, destinations=chunk,
                               n_rinses=3, vol_rinses=20, asp_vol=20, spot_vol=1)
