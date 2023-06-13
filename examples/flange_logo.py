from build123d import *
from bd_warehouse.pipe import Pipe, PipeSection
from bd_warehouse.flange import SlipOnFlange, WeldNeckFlange

from ocp_vscode import show, set_port, set_defaults

set_port(3939)
set_defaults(reset_camera=False, ortho=True)


horizontal_flange = WeldNeckFlange(nps="12", flange_class=300, face_type="Ring")
vertical_flange = SlipOnFlange(nps="8", flange_class=300)

with BuildPart() as pipes:
    # Create horizontal pipe
    with BuildLine():
        l1 = Line((0, 0, 0), (6 * FT, 0, 0))
    horizontal_pipe = Pipe(nps="12", material="steel", identifier="40")

    # Create vertical pipe intersecting horizontal pipe
    vertical_pipe_outlet = Location(Plane((3 * FT, 0, 2 * FT), z_dir=(0, 0, 1)))
    horizontal_pipe_outlet = Location(Plane(l1 @ 1, z_dir=(-1, 0, 0)))
    with BuildSketch(vertical_pipe_outlet):
        pipe_section = PipeSection(nps="8", material="steel", identifier="40")
    vertical_pipe = extrude(until=Until.PREVIOUS)

    # Weld the two pipe together by creating a fillet
    welded_edges = (
        vertical_pipe.edges()
        .filter_by_position(Axis.Z, 0, horizontal_pipe.od / 2)
        .group_by(SortBy.LENGTH)[-1]
    )
    fillet(welded_edges, 8 * MM)

    # Create a hole in the horizontal pipe to join it to the vertical
    with Locations((3 * FT, 0, 0)):
        Cylinder(
            pipe_section.id / 2,
            1 * FT,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
            mode=Mode.SUBTRACT,
        )
    RigidJoint("vertical", pipes.part, vertical_pipe_outlet)
    RigidJoint("horizontal", pipes.part, l1.location_at(1))

# Attach the flanges to the ends of the pipes
pipes.part.joints["vertical"].connect_to(vertical_flange.joints["pipe"])
pipes.part.joints["horizontal"].connect_to(horizontal_flange.joints["pipe"])

show(pipes, horizontal_flange, vertical_flange)
