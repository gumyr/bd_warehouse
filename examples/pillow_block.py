import copy
from build123d import *
from bd_warehouse.fastener import SocketHeadCapScrew, ClearanceHole
from bd_warehouse.bearing import SingleRowDeepGrooveBallBearing, PressFitHole
from ocp_vscode import show

# Dimensions in the default unit of MM
height, width, thickness, padding, fillet_radius = 30, 50, 10, 12, 2

# Create the screw & bearing
cap_screw = SocketHeadCapScrew(size="M2-0.4", length=16, simple=False)
skate_bearing = SingleRowDeepGrooveBallBearing(size="M8-22-7")

# Create the pillow block
with BuildPart() as pillow_block:
    with BuildSketch():
        RectangleRounded(width, height, fillet_radius)
    extrude(amount=thickness)
    with Locations((0, 0, thickness)):  # On the top
        PressFitHole(bearing=skate_bearing, interference=0.025 * MM)
        with GridLocations(width - padding, height - padding, 2, 2):
            ClearanceHole(fastener=cap_screw)

pillow_block.part.color = Color("teal")

# Create an assembly of all the positioned parts
pillow_block_assembly = Compound(
    children=[pillow_block.part, skate_bearing.moved(skate_bearing.hole_locations[0])]
    + [copy.copy(cap_screw).moved(l) for l in cap_screw.hole_locations]
)
show(pillow_block_assembly)
