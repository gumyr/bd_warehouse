"""

Gears - parametric, involute gears of all types

name: gears.py
by:   Gumyr
date: October 2nd 2023

This module can be used to create a wide variety of involute gears, 
either standard ISO (metric), imperial or fully custom.  Involute gears have
the property of continually meshing at a specific angle (the pressure angle)
thus avoiding the stutter of non-involute gears as the teeth lose
contact with each other. Imagine a telescope mount: involute gears would
allow the telescope to smoothly follow a star as it moves across the night
sky, while non-involute gears would introduce a shake that would blur the
image of a long exposure.

All common types of gears are supported as follows:
- bevel:    cone as its pitch surface
- helical:  cylindrical gears with winding tooth lines
- miter:    bevel gears with a speed ratio of 1
- rack:     linear arrangement of teeth
- ring:     an internal gear
- screw:    helical gear with 45 twist angle
- spiral:   bevel gears with curved tooth lines
- spur:     simple, with cylindrical pitch surfaces
- worm:     a single tooth spooled around the gear core
- wormgear: a helical gear that interfaces with the worm

Gears are art pieces unless they mesh with each other. To ensure two
gears can mesh, follow these guidelines:
- Meshing gears need the same tooth shape and size, so use a common
    module (for metric gears) or diametral pitch value (for imperial gears).
    For fully custom gears, the base, pitch and outer radii will all
    need to be calculated appropriately.
- For gears that do not spin in the same plane (i.e. bevel or spiral gears)
    the pitch angle parameter is used to describe the cone that the face of the
    teeth follow. The sum of the two pitch angles equals the angle of the
    two shafts. For example, a miter gear has a pitch angle of 45 degrees
    so two of them spin 90 degrees from each other (45 + 45 = 90). Two bevel
    gears at 25 and 65 degrees (25 + 65 = 90) also spin at 90 degrees.
    There is no need for the sum of the pitch angles to be 90 degrees,
    this is just the most common use case.
- Spiral gears are bevel gears with a twist. When meshing two twisted gears
    the twists must be complimentary - as follows: the twist of the second
    gear is equal to the twist of the first multiplied by negated ratio of
    the two gears, or:
    t1 = -t0*(n0/n1) 
    where n are teeth counts and t spiral twist values. Note this rule
    applies to helical and screw gears which are simplified versions of
    spiral gears. Wormgears also have a fixed twist which need not be
    directly specified.
- When positioning two gears to mesh, they need to be separated by the
    sum of their pitch radii. For ISO metric gears this is very easy to
    do - simply multiply the gear module by the sum of the tooth count and 
    divide by two (in mm), or:
    separation = module*(n0 + n1)/2 [mm]
    Gears with a non-zero pitch angle are created with a vertical
    displacement preset for simple meshing. For example, when positioning
    two miter gears, rotate the second one by 90 degrees and displace it
    both horizontally and vertically by the module multiplied by half its
    tooth count, or:
    translate((0,gear_module*n/2,gear_module*n/2)) rotate((90,0,0))


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

from math import sin, cos, tan, acos, radians
from typing import Union
from build123d import *


class InvoluteToothProfile(BaseLineObject):
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
            else (self.pitch_radius - self.base_radius) + 2 * root_fillet
        )
        self.root_radius = self.pitch_radius - self.dedendum
        half_thick_angle = 90 / tooth_count

        # Create the involute curve points
        involute_size = self.addendum_radius - self.base_radius
        pnts = []
        for i in range(11):
            r = self.base_radius + involute_size * i / 10
            α = acos(self.base_radius / r)  # in radians
            involute = tan(α) - α
            pnts.append((r * cos(involute), r * sin(involute)))

        with BuildLine(Plane.XY.rotated((0, 0, -half_thick_angle))) as tooth:
            side = Spline(*pnts) + Line(pnts[0], (self.root_radius, 0))
            root = RadiusArc(
                side @ 0,
                Vector(self.root_radius, 0).rotate(Axis.Z, -2 * half_thick_angle),
                self.root_radius,
            )
            top_land = RadiusArc(
                side @ 1,
                Vector(self.addendum_radius, 0),
                -self.addendum_radius,
            )
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

        tooth = Wire(tooth.edges().sort_by(Axis.Y) + close)

        super().__init__(tooth, mode=mode)


class SpurGearPlan(BaseSketchObject):
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
        gear_wire = Wire.make_wire([e for tooth in gear_teeth for e in tooth.edges()])
        gear_face = -Face.make_from_wires(gear_wire)
        super().__init__(gear_face, rotation, align, mode)


class SpurGear(BasePartObject):
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
        align: Union[Align, tuple[Align, Align, Align]] = (
            Align.CENTER,
            Align.CENTER,
            Align.CENTER,
        ),
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
