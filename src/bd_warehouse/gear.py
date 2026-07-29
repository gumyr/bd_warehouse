"""

Gears - parametric involute spur and helical gears

name: gear.py
by:   Gumyr
date: July 14nd 2024

This module can be used to create a wide variety of metric-module involute spur
and helical gears, either standard ISO profiles or fully custom. ``SpurGear`` creates
straight teeth parallel to the gear axis, while ``HelicalGear`` creates twisted
teeth and supports both normal- and transverse-module specifications. Involute
gears have the property of continually meshing at a specific angle (the pressure
angle), thus avoiding the stutter of non-involute gears as the teeth lose contact
with each other. Imagine a telescope mount: involute gears would allow the
telescope to smoothly follow a star as it moves across the night sky, while
non-involute gears would introduce a shake that would blur the image of a long
exposure.

Gears are art pieces unless they mesh with each other. To ensure two
gears can mesh, follow these guidelines:
    - Meshing gears need the same tooth shape and size, so use a common module
      and pressure angle. For fully custom gears, the base, pitch and outer
      radii will all need to be calculated appropriately.
    - When positioning two gears to mesh, they need to be separated by the
      sum of their pitch radii. For spur gears and transverse-module helical
      gears, this is ``module * (n0 + n1) / 2``. For normal-module helical
      gears, the transverse pitch radii calculated by ``HelicalGear`` should be
      used.

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

from math import sin, cos, tan, acos, atan, radians, degrees, pi, inf
from typing import Literal
from build123d import *
from OCP.StdFail import StdFail_NotDone
from bd_materials.materials.metals import alloy_steel, AlloySteel
from bd_materials.finishes import black_oxide


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
        root_fillet: float | None = None,
        addendum: float | None = None,
        dedendum: float | None = None,
        closed: bool = False,
        mode: Mode = Mode.ADD,
    ):
        self.module = module
        self.tooth_count = tooth_count
        self.pitch_radius = module * tooth_count / 2
        self.base_radius = self.pitch_radius * cos(radians(pressure_angle))
        self.addendum = addendum if addendum is not None else module
        self.addendum_radius = self.pitch_radius + self.addendum
        self.dedendum = dedendum if dedendum is not None else 1.25 * module
        self.root_radius = self.pitch_radius - self.dedendum
        half_thick_angle = 90 / tooth_count
        half_pitch_angle = half_thick_angle + degrees(
            tan(radians(pressure_angle)) - radians(pressure_angle)
        )
        # # Create the involute curve points
        involute_size = self.addendum_radius - self.base_radius
        pnts = []
        for i in range(11):
            r = self.base_radius + involute_size * i / 10
            α = acos(self.base_radius / r)  # in radians
            involute = tan(α) - α
            if (rp := r * cos(involute)) > self.root_radius:
                pnts.append((rp, r * sin(involute)))

        with BuildLine() as tooth:
            rotated_pnts = [
                Vector(*point).rotate(Axis.Z, -half_pitch_angle) for point in pnts
            ]
            l1 = Spline(*rotated_pnts)
            root_flank = Vector(self.root_radius, 0).rotate(Axis.Z, -half_pitch_angle)
            l2 = Line(rotated_pnts[0], root_flank)
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
            if root_fillet is not None:
                try:
                    fillet(tooth.vertices().sort_by(Axis.X)[1], root_fillet)
                except StdFail_NotDone as err:
                    raise ValueError(
                        "Invalid root radius, try a smaller value"
                    ) from err

            mirror(tooth.edges(), about=Plane.XZ)

        close = (
            [
                Edge.make_line(
                    tooth.line.vertices().sort_by(Axis.Y)[-1].to_tuple(),
                    tooth.line.vertices().sort_by(Axis.Y)[0].to_tuple(),
                )
            ]
            if closed
            else []
        )

        super().__init__(Wire.combine(tooth.line.edges() + close)[0], mode=mode)


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
        align (Align | tuple[Align, Align], optional): align min, center, or max
            of object. Defaults to (Align.CENTER, Align.CENTER).
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    _applies_to = [BuildSketch._tag]

    def __init__(
        self,
        module: float,
        tooth_count: int,
        pressure_angle: float,
        root_fillet: float | None = None,
        addendum: float | None = None,
        dedendum: float | None = None,
        rotation: float = 0,
        align: Align | tuple[Align, Align] = (Align.CENTER, Align.CENTER),
        mode: Mode = Mode.ADD,
    ):
        gear_tooth = InvoluteToothProfile(
            module, tooth_count, pressure_angle, root_fillet, addendum, dedendum
        )
        self.pitch_radius = gear_tooth.pitch_radius
        self.base_radius = gear_tooth.base_radius
        self.addendum_radius = gear_tooth.addendum_radius
        self.root_radius = gear_tooth.root_radius
        if self.base_radius < self.root_radius:
            raise ValueError("Invalid configuration, try changing the pressure angle")
        gear_teeth = PolarLocations(0, tooth_count) * gear_tooth
        gear_wire = Wire([e for tooth in gear_teeth for e in tooth.edges()])
        gear_face = Face(gear_wire)
        if gear_face.normal_at().Z < 0:
            gear_face = -gear_face
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
        align (Align | tuple[Align, Align, Align] | None, optional): align min,
            center, or max of object. Defaults to Align.CENTER.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        module: float,
        tooth_count: int,
        pressure_angle: float,
        thickness: float,
        root_fillet: float | None = None,
        addendum: float | None = None,
        dedendum: float | None = None,
        rotation: RotationLike = (0, 0, 0),
        align: Align | tuple[Align, Align, Align] | None = Align.CENTER,
        mode: Mode = Mode.ADD,
    ):
        gear_plan = SpurGearPlan(
            module, tooth_count, pressure_angle, root_fillet, addendum, dedendum
        )
        self.pitch_radius = gear_plan.pitch_radius
        self.base_radius = gear_plan.base_radius
        self.addendum_radius = gear_plan.addendum_radius
        self.root_radius = gear_plan.root_radius
        super().__init__(
            extrude(gear_plan, amount=thickness),
            rotation,
            align,
            mode,
        )
        self.material = alloy_steel(
            grade=AlloySteel.G4140_QUENCHED_TEMPERED, finish=black_oxide()
        )


class HelicalGear(BasePartObject):
    """A cylindrical involute gear with helical teeth.

    Helical-gear module and pressure angle can be specified in either of two
    measurement planes:

    * ``"normal"`` means the plane perpendicular (normal) to the direction of a
      tooth helix. Here, "normal" is a geometric term and does not mean ordinary
      or default. Normal-system dimensions correspond to the rack or cutting-tool
      profile commonly used to manufacture the gear.
    * ``"transverse"`` means the plane perpendicular to the gear axis, equivalent
      to looking directly at the circular end of the gear. The transverse module
      determines pitch diameter directly: ``pitch_diameter = module * tooth_count``.

    For a helix angle ``β``, the modules are related by
    ``transverse_module = normal_module / cos(β)``. The pressure angle is also
    converted between the selected normal or transverse plane. Catalogue gears may
    use either convention, so ``module_system`` should match the convention used by
    the source dimensions.

    A positive helix angle produces a positive rotation about the Z axis through
    the gear thickness; a negative angle produces the opposite hand.

    Args:
        module (float): normal or transverse module, as selected by
            ``module_system``.
        tooth_count (int): number of teeth.
        pressure_angle (float): normal or transverse pressure angle, as selected
            by ``module_system``.
        helix_angle (float): signed helix angle in degrees.
        thickness (float): gear face width.
        module_system (Literal["normal", "transverse"], optional): measurement
            plane for both ``module`` and ``pressure_angle``. ``"normal"`` is
            perpendicular to the tooth helix; ``"transverse"`` is perpendicular
            to the gear axis. Defaults to "normal".
        root_fillet (float, optional): radius of the tooth-root fillet.
        addendum (float, optional): radial addendum. When omitted, the module in
            the selected reference system is used.
        dedendum (float, optional): radial dedendum. When omitted, 1.25 times the
            module in the selected reference system is used.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Align | tuple[Align, Align, Align] | None, optional): object
            alignment. Defaults to Align.CENTER.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        module: float,
        tooth_count: int,
        pressure_angle: float,
        helix_angle: float,
        thickness: float,
        module_system: Literal["normal", "transverse"] = "normal",
        root_fillet: float | None = None,
        addendum: float | None = None,
        dedendum: float | None = None,
        rotation: RotationLike = (0, 0, 0),
        align: Align | tuple[Align, Align, Align] | None = Align.CENTER,
        mode: Mode = Mode.ADD,
    ):
        if module <= 0:
            raise ValueError("module must be greater than zero")
        if tooth_count <= 0:
            raise ValueError("tooth_count must be greater than zero")
        if thickness <= 0:
            raise ValueError("thickness must be greater than zero")
        if not 0 <= pressure_angle < 90:
            raise ValueError("pressure_angle must be in the range [0, 90)")
        if not -90 < helix_angle < 90:
            raise ValueError("helix_angle must be in the range (-90, 90)")
        if module_system not in ("normal", "transverse"):
            raise ValueError("module_system must be either 'normal' or 'transverse'")

        beta = radians(helix_angle)
        reference_addendum = module if addendum is None else addendum
        reference_dedendum = 1.25 * module if dedendum is None else dedendum

        if module_system == "normal":
            self.normal_module = module
            self.transverse_module = module / cos(beta)
            self.normal_pressure_angle = pressure_angle
            self.transverse_pressure_angle = degrees(
                atan(tan(radians(pressure_angle)) / cos(beta))
            )
        else:
            self.transverse_module = module
            self.normal_module = module * cos(beta)
            self.transverse_pressure_angle = pressure_angle
            self.normal_pressure_angle = degrees(
                atan(tan(radians(pressure_angle)) * cos(beta))
            )

        gear_plan = SpurGearPlan(
            module=self.transverse_module,
            tooth_count=tooth_count,
            pressure_angle=self.transverse_pressure_angle,
            root_fillet=root_fillet,
            addendum=reference_addendum,
            dedendum=reference_dedendum,
        )
        self.module = module
        self.module_system = module_system
        self.tooth_count = tooth_count
        self.pressure_angle = pressure_angle
        self.helix_angle = helix_angle
        self.thickness = thickness
        self.pitch_radius = gear_plan.pitch_radius
        self.base_radius = gear_plan.base_radius
        self.addendum_radius = gear_plan.addendum_radius
        self.root_radius = gear_plan.root_radius
        self.twist_angle = degrees(thickness * tan(beta) / self.pitch_radius)
        self.lead = (
            2 * pi * self.pitch_radius / abs(tan(beta)) if helix_angle != 0 else inf
        )

        gear = (
            extrude(gear_plan, amount=thickness)
            if helix_angle == 0
            else Solid.extrude_linear_with_rotation(
                section=gear_plan.face(),
                center=(0, 0, 0),
                normal=(0, 0, thickness),
                angle=self.twist_angle,
            )
        )
        gear.material = alloy_steel(
            grade=AlloySteel.G4140_QUENCHED_TEMPERED, finish=black_oxide()
        )
        super().__init__(gear, rotation, align, mode)


if __name__ == "__main__":
    from ocp_vscode import show

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

    helical_gear = HelicalGear(
        module=2, tooth_count=13, pressure_angle=20, helix_angle=45, thickness=10 * MM
    )
    show(pack([gear_tooth, gear_profile, spur_gear, helical_gear], 5))
