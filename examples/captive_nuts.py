from bd_warehouse.fastener import ClearanceHole, HexNut, SquareNut
from build123d import *
from ocp_vscode import show

# Create the nuts
hex_nut = HexNut(size="M6-1", fastener_type="iso4033")
square_nut = SquareNut(size="M6-1", fastener_type="din557")

# Create a block with a captive hole for each nut
with BuildPart() as block:
    Box(50, 50, 10)
    with Locations((-12.5, 0, 5)):  # On the top face
        ClearanceHole(fastener=hex_nut, fit="Loose", captive_nut=True)
    with Locations((12.5, 0, 5)):
        ClearanceHole(fastener=square_nut, captive_nut=True)

block.part.color = Color("tan")

# Create an assembly of the block with the nuts in their holes
captive_nut_assembly = Compound(
    children=[
        block.part,
        hex_nut.moved(hex_nut.hole_locations[0]),
        square_nut.moved(square_nut.hole_locations[0]),
    ]
)
show(captive_nut_assembly)
