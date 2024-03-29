import copy
from build123d import *
from bd_warehouse.fastener import *
from ocp_vscode import *

height, width, thickness, padding, fillet_radius = 30, 50, 10, 12, 2

# Make the screw
screw = SocketHeadCapScrew(
    size="M2-0.4", fastener_type="iso4762", length=16, simple=False
)
screw.color = Color(0xC0C0C0)  # Silver

# Make the base
with BuildPart() as pillow_block:
    with BuildSketch():
        RectangleRounded(width, height, fillet_radius)
        Circle(10, mode=Mode.SUBTRACT)
    extrude(amount=thickness)
    with Locations(pillow_block.faces().sort_by(Axis.Z)[-1]):
        with GridLocations(width - padding, height - padding, 2, 2):
            ClearanceHole(fastener=screw)

pillow_block.part.color = Color("teal")

# Create the assembly of all the parts
pillow_block_assembly = Compound(
    children=[pillow_block.part]
    + [copy.copy(screw).moved(l) for l in screw.hole_locations]
)
show(pillow_block_assembly)
# show(pillow_block)
