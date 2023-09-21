from build123d import *
from bd_warehouse.pipe import Pipe, PipeSection
from bd_warehouse.flange import SlipOnFlange, WeldNeckFlange

from ocp_vscode import show

inlet_flange = WeldNeckFlange(nps="12", flange_class=300, face_type="Ring")
outlet_flange = SlipOnFlange(nps="12", flange_class=300)

pipe = Pipe(
    nps="12",
    material="steel",
    identifier="40",
    path=Edge.make_line((0, 0, 0), (6 * FT, 0, 0)),
)

pipe.joints["inlet"].connect_to(inlet_flange.joints["pipe"])
pipe.joints["outlet"].connect_to(outlet_flange.joints["pipe"])

show(pipe, inlet_flange, outlet_flange)
