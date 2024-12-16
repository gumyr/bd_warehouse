"""

Gears - parametric, involute gears of all types

name: gear.py
by:   Gumyr
date: July 14nd 2024

This module can be used to create a wide variety of involute spur gears, 
either standard ISO (metric) or fully custom.  Involute gears have
the property of continually meshing at a specific angle (the pressure angle)
thus avoiding the stutter of non-involute gears as the teeth lose
contact with each other. Imagine a telescope mount: involute gears would
allow the telescope to smoothly follow a star as it moves across the night
sky, while non-involute gears would introduce a shake that would blur the
image of a long exposure.

Gears are art pieces unless they mesh with each other. To ensure two
gears can mesh, follow these guidelines:
    - Meshing gears need the same tooth shape and size, so use a common
      module (for metric gears) or diametral pitch value (for imperial gears).
      For fully custom gears, the base, pitch and outer radii will all
      need to be calculated appropriately.
    - When positioning two gears to mesh, they need to be separated by the
      sum of their pitch radii. For ISO metric gears this is very easy to
      do - simply multiply the gear module by the sum of the tooth count and 
      divide by two (in mm), or: separation = module*(n0 + n1)/2 [mm]

license:

    Copyright 2024 Gumyr

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

from math import sin, cos, tan, acos, radians, degrees
from typing import Union
from build123d import *
from ocp_vscode import *


class InvoluteToothProfile(BaseLineObject):
    """InvoluteToothProfile

    The outline of a single involute tooth.

    Args:
        module (float): the ratio of the pitch diameter to the number of teeth and
            is expressed in millimeters (mm)
        tooth_count (int): number of teeth in complete gear
        pressure_angle (float): the angle between the line of action (the line along
            which the force is transmitted between meshing gear teeth) and the tangent
            to the pitch circle. Common values are 14.5 or 20.
        root_fillet (float): radius of the fillet at the root of the tooth
        addendum (float, optional): the radial distance between the pitch circle and
            the top of the gear tooth. Defaults to None (calculated).
        dedendum (float, optional): the radial distance between the pitch circle and
            the bottom of the gear tooth space. It defines the depth of the space
            between gear teeth below the pitch circle. Defaults to None (calculated).
        closed (bool, optional): create a closed wire. Defaults to False.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    _applies_to = [BuildLine._tag]

    def __init__(
        self,
        module: float,
        tooth_count: int,
        pressure_angle: float,
        root_fillet: float,
        addendum: float = None,
        dedendum: float = None,
        closed: bool = False,
        mode: Mode = Mode.ADD,
    ):
        self.module = module
        self.tooth_count = tooth_count
        self.pitch_radius = module * tooth_count / 2
        self.base_radius = self.pitch_radius * cos(radians(pressure_angle))
        self.addendum = addendum if addendum is not None else module
        self.addendum_radius = self.pitch_radius + self.addendum
        self.dedendum = (
            dedendum
            if dedendum is not None
            else (1.25 * module)
        )
        self.root_radius = self.pitch_radius - self.dedendum
        half_thick_angle = 90 / tooth_count
        half_pitch_angle = half_thick_angle + degrees(
            tan(radians(pressure_angle)) - radians(pressure_angle)
        )
        # Create the involute curve points
        involute_size = self.addendum_radius - self.base_radius
        pnts = []
        for i in range(11):
            r = self.base_radius + involute_size * i / 10
            α = acos(self.base_radius / r)  # in radians
            involute = tan(α) - α
            if (rp := r * cos(involute)) > self.root_radius:
                pnts.append((rp, r * sin(involute)))

        with BuildLine(Plane.XY.rotated((0, 0, -half_pitch_angle))) as tooth:
            l1 = Spline(*pnts)
            l2 = Line(pnts[0], (self.root_radius, 0))
            root = RadiusArc(
                l2 @ 1,
                Vector(self.root_radius, 0).rotate(Axis.Z, -2 * half_thick_angle),
                self.root_radius,
            )
            top_land = RadiusArc(
                l1 @ 1,
                Vector(self.addendum_radius, 0),
                -self.addendum_radius,
            )
            if root_fillet:
                fillet(tooth.vertices().sort_by(Axis.X)[1], root_fillet)
            mirror(about=Plane.XZ)

        close = (
            [
                Edge.make_line(
                    tooth.vertices().sort_by(Axis.Y)[-1].to_tuple(),
                    tooth.vertices().sort_by(Axis.Y)[0].to_tuple(),
                )
            ]
            if closed
            else []
        )

        super().__init__(Wire(tooth.edges() + close), mode=mode)


class SpurGearPlan(BaseSketchObject):
    """InvoluteToothProfile

    The 2D plan of the gear.

    Args:
        module (float): the ratio of the pitch diameter to the number of teeth and
            is expressed in millimeters (mm)
        tooth_count (int): number of teeth in complete gear
        pressure_angle (float): the angle between the line of action (the line along
            which the force is transmitted between meshing gear teeth) and the tangent
            to the pitch circle. Common values are 14.5 or 20.
        root_fillet (float): radius of the fillet at the root of the tooth
        addendum (float, optional): the radial distance between the pitch circle and
            the top of the gear tooth. Defaults to None (calculated).
        dedendum (float, optional): the radial distance between the pitch circle and
            the bottom of the gear tooth space. It defines the depth of the space
            between gear teeth below the pitch circle. Defaults to None (calculated).
        closed (bool, optional): create a closed wire. Defaults to False.
        align (Union[None, Align, tuple[Align, Align]], optional): align min, center,
            or max of object. Defaults to (Align.CENTER, Align.CENTER).
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    _applies_to = [BuildSketch._tag]

    def __init__(
        self,
        module: float,
        tooth_count: int,
        pressure_angle: float,
        root_fillet: float,
        addendum: float = None,
        dedendum: float = None,
        rotation: float = 0,
        align: Union[Align, tuple[Align, Align]] = (Align.CENTER, Align.CENTER),
        mode: Mode = Mode.ADD,
    ):
        gear_tooth = InvoluteToothProfile(
            module, tooth_count, pressure_angle, root_fillet, addendum, dedendum
        )
        gear_teeth = PolarLocations(0, tooth_count) * gear_tooth
        gear_wire = Wire([e for tooth in gear_teeth for e in tooth.edges()])
        gear_face = -Face(gear_wire)
        super().__init__(gear_face, rotation, align, mode)


class SpurGear(BasePartObject):
    """InvoluteToothProfile

    The 3D representation of the gear.

    Args:
        module (float): the ratio of the pitch diameter to the number of teeth and
            is expressed in millimeters (mm)
        tooth_count (int): number of teeth in complete gear
        pressure_angle (float): the angle between the line of action (the line along
            which the force is transmitted between meshing gear teeth) and the tangent
            to the pitch circle. Common values are 14.5 or 20.
        root_fillet (float): radius of the fillet at the root of the tooth
        thickness (float): gear thickness
        addendum (float, optional): the radial distance between the pitch circle and
            the top of the gear tooth. Defaults to None (calculated).
        dedendum (float, optional): the radial distance between the pitch circle and
            the bottom of the gear tooth space. It defines the depth of the space
            between gear teeth below the pitch circle. Defaults to None (calculated).
        closed (bool, optional): create a closed wire. Defaults to False.
        align (Union[None, Align, tuple[Align, Align, Align]], optional): align min,
            center, or max of object. Defaults to Align.CENTER.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        module: float,
        tooth_count: int,
        pressure_angle: float,
        root_fillet: float,
        thickness: float,
        addendum: float = None,
        dedendum: float = None,
        rotation: Rotation = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = Align.CENTER,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(
            extrude(
                SpurGearPlan(
                    module, tooth_count, pressure_angle, root_fillet, addendum, dedendum
                ),
                amount=thickness,
            ),
            rotation,
            align,
            mode,
        )


if __name__ == "__main__":
    from ocp_vscode import show, set_defaults, Camera

    set_defaults(reset_camera=Camera.CENTER)

    gear_tooth = InvoluteToothProfile(
        module=2,
        tooth_count=12,
        pressure_angle=14.5,
        root_fillet=0.5 * MM,
    )

    gear_profile = SpurGearPlan(
        module=2,
        tooth_count=12,
        pressure_angle=14.5,
        root_fillet=0.5 * MM,
    )

    spur_gear = SpurGear(
        module=2,
        tooth_count=12,
        pressure_angle=14.5,
        root_fillet=0.5 * MM,
        thickness=5 * MM,
    )
    show(pack([gear_tooth, gear_profile, spur_gear], 5))
