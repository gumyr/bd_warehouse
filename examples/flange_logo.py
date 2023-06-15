"""

Flange Logo

name: flange_logo.py
by:   Gumyr
date: JUne 13th, 2023

desc:
    This python module creates a logo for the flanges packages as an example 
    of using Pipes and Flanges.

license:

    Copyright 2023 Gumyr

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

"""

from build123d import *
from bd_warehouse.pipe import Pipe, PipeSection
from bd_warehouse.flange import (
    SlipOnFlange,
    WeldNeckFlange,
    BlindFlange,
    SocketWeldFlange,
    LappedFlange,
)

from ocp_vscode import show, show_object, set_port, set_defaults

set_port(3939)
set_defaults(reset_camera=False, ortho=True)

trunk_pipe_size = "8"
trunk_outlet_flange = WeldNeckFlange(
    nps=trunk_pipe_size, flange_class=300, face_type="Ring"
)
trunk_inlet_flange = SlipOnFlange(nps=trunk_pipe_size, flange_class=300)
blind_flange = BlindFlange(nps="3", flange_class=300)
socket_flange = SocketWeldFlange(nps="3", flange_class=300)
lapped_flange = LappedFlange(nps="5", flange_class=300)

with BuildPart() as pipes:
    # Create trunk pipe
    with BuildLine():
        l1 = Line((0, 0, 0), (4 * FT, 0, 0))
    trunk_pipe = Pipe(nps=trunk_pipe_size, material="steel", identifier="40")
    trunk_pipe_outlet = Location(Plane(l1 @ 1, z_dir=(-1, 0, 0)))

    # Create vertical pipe intersecting trunk pipe
    vertical_pipe_outlet = Location(Plane((2 * FT, 0, 1 * FT), z_dir=(0, 0, 1)))
    with BuildSketch(vertical_pipe_outlet):
        pipe_section = PipeSection(nps="3", material="steel", identifier="40")
    vertical_pipe = extrude(until=Until.PREVIOUS)

    # Weld the two pipe together by creating a fillet
    welded_edges = (
        vertical_pipe.edges()
        .filter_by_position(Axis.Z, 0, trunk_pipe.od / 2)
        .group_by(SortBy.LENGTH)[-1]
    )
    fillet(welded_edges, 8 * MM)

    # Create a hole in the trunk pipe to join it to the vertical
    with Locations((2 * FT, 0, 0)):
        Cylinder(
            pipe_section.id / 2,
            1 * FT,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
            mode=Mode.SUBTRACT,
        )

    # Create horizontal pipe intersecting trunk pipe
    horizontal_pipe_outlet = Location(
        Plane((3 * FT, -2 * FT, 0 * FT), z_dir=(0, -1, 0))
    )
    with BuildSketch(horizontal_pipe_outlet):
        pipe_section = PipeSection(nps="5", material="steel", identifier="40")
    horizontal_pipe = extrude(until=Until.PREVIOUS)

    # Weld the two pipe together by creating a fillet
    welded_edges = (
        horizontal_pipe.edges()
        .filter_by_position(Axis.Y, -trunk_pipe.od / 2, 0)
        .group_by(SortBy.LENGTH)[-1]
    )
    fillet(welded_edges, 8 * MM)

    # Create a hole in the trunk pipe to join it to the vertical
    with Locations((3 * FT, 0, 0)):
        Cylinder(
            pipe_section.id / 2,
            1 * FT,
            rotation=(90, 0, 0),
            align=(Align.CENTER, Align.CENTER, Align.MIN),
            mode=Mode.SUBTRACT,
        )

    RigidJoint("vertical", pipes.part, vertical_pipe_outlet)
    RigidJoint("horizontal", pipes.part, horizontal_pipe_outlet)
    RigidJoint("trunk-outlet", pipes.part, l1.location_at(1))
    RigidJoint("trunk-inlet", pipes.part, Location(Plane(l1 @ 0, z_dir=-(l1 % 0))))


# Attach the flanges to the ends of the pipes
pipes.part.joints["vertical"].connect_to(socket_flange.joints["pipe"])
pipes.part.joints["horizontal"].connect_to(lapped_flange.joints["pipe"])
socket_flange.joints["face"].connect_to(blind_flange.joints["face"])
pipes.part.joints["trunk-outlet"].connect_to(trunk_outlet_flange.joints["pipe"])
pipes.part.joints["trunk-inlet"].connect_to(trunk_inlet_flange.joints["pipe"])

show(
    pipes,
    trunk_outlet_flange,
    trunk_inlet_flange,
    blind_flange,
    socket_flange,
    lapped_flange,
    names=[
        "pipes",
        "trunk_outlet_flange",
        "trunk_inlet_flange",
        "blind_flange",
        "socket_flange",
        "lapped_flange",
    ],
    render_joints=False,
)
