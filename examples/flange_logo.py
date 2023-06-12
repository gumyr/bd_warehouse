from build123d import *
from bd_warehouse.pipe import Pipe, PipeSection
from bd_warehouse.flange import Nps, SlipOnFlange, WeldNeckFlange

from ocp_vscode import show, set_port, set_defaults

set_port(3939)
set_defaults(reset_camera=False, ortho=True)


flange = WeldNeckFlange(nps="12", flange_class=300)

with BuildPart() as pipes:
    with BuildLine():
        Line((0, 0, 0), (10 * FT, 0, 0))
    Pipe(nps="12", material="steel", identifier="40")
    with BuildSketch(Plane((7 * FT, 0, 5 * FT), z_dir=(0, 0, -1))):
        p = PipeSection(nps="8", material="steel", identifier="40")
    extrude(until=Until.NEXT)
    print(p.location)
