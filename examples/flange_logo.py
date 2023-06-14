from build123d import *
from bd_warehouse.pipe import Pipe, PipeSection
from bd_warehouse.flange import (
    SlipOnFlange,
    WeldNeckFlange,
    BlindFlange,
    SocketWeldFlange,
)

from ocp_vscode import show, show_object, set_port, set_defaults

set_port(3939)
set_defaults(reset_camera=False, ortho=True)

trunk_pipe_size = "8"
horizontal_outlet_flange = WeldNeckFlange(
    nps=trunk_pipe_size, flange_class=300, face_type="Ring"
)
horizontal_inlet_flange = SlipOnFlange(nps=trunk_pipe_size, flange_class=300)
blind_flange = BlindFlange(nps="3", flange_class=300)
socket_flange = SocketWeldFlange(nps="3", flange_class=300)

with BuildPart() as pipes:
    # Create horizontal pipe
    with BuildLine():
        l1 = Line((0, 0, 0), (4 * FT, 0, 0))
    horizontal_pipe = Pipe(nps=trunk_pipe_size, material="steel", identifier="40")

    # Create vertical pipe intersecting horizontal pipe
    vertical_pipe_outlet = Location(Plane((2 * FT, 0, 1 * FT), z_dir=(0, 0, 1)))
    horizontal_pipe_outlet = Location(Plane(l1 @ 1, z_dir=(-1, 0, 0)))
    with BuildSketch(vertical_pipe_outlet):
        pipe_section = PipeSection(nps="3", material="steel", identifier="40")
    vertical_pipe = extrude(until=Until.PREVIOUS)

    # Weld the two pipe together by creating a fillet
    welded_edges = (
        vertical_pipe.edges()
        .filter_by_position(Axis.Z, 0, horizontal_pipe.od / 2)
        .group_by(SortBy.LENGTH)[-1]
    )
    fillet(welded_edges, 8 * MM)

    # Create a hole in the horizontal pipe to join it to the vertical
    with Locations((2 * FT, 0, 0)):
        Cylinder(
            pipe_section.id / 2,
            1 * FT,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
            mode=Mode.SUBTRACT,
        )
    RigidJoint("vertical", pipes.part, vertical_pipe_outlet)
    RigidJoint("horizontal-outlet", pipes.part, l1.location_at(1))
    RigidJoint("horizontal-inlet", pipes.part, Location(Plane(l1 @ 0, z_dir=-(l1 % 0))))


# Attach the flanges to the ends of the pipes
pipes.part.joints["vertical"].connect_to(socket_flange.joints["pipe"])
socket_flange.joints["face"].connect_to(blind_flange.joints["face"])
pipes.part.joints["horizontal-outlet"].connect_to(
    horizontal_outlet_flange.joints["pipe"]
)
pipes.part.joints["horizontal-inlet"].connect_to(horizontal_inlet_flange.joints["pipe"])

show(
    pipes,
    horizontal_outlet_flange,
    horizontal_inlet_flange,
    blind_flange,
    socket_flange,
    render_joints=True,
)
