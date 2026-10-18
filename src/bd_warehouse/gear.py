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

from math import (
    acos,
    asin,
    atan,
    atan2,
    ceil,
    cos,
    degrees,
    hypot,
    inf,
    nan,
    pi,
    radians,
    sin,
    sqrt,
    tan,
)
from typing import Callable, Literal

from bd_materials.finishes import black_oxide
from bd_materials.materials.metals import AlloySteel, alloy_steel, bronze
from build123d import (
    MM,
    Align,
    Axis,
    BaseLineObject,
    BasePartObject,
    BaseSketchObject,
    BuildLine,
    BuildPart,
    BuildSketch,
    Compound,
    Edge,
    Face,
    GeomType,
    GridLocations,
    Helix,
    Line,
    Location,
    Matrix,
    Mode,
    Plane,
    PolarLocations,
    Polyline,
    Pos,
    RadiusArc,
    Rectangle,
    RigidJoint,
    Rot,
    RotationLike,
    Shell,
    Solid,
    Spline,
    Trapezoid,
    UVFrame,
    Vector,
    Wire,
    extrude,
    fillet,
    mirror,
    pack,
)


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
            RadiusArc(
                l2 @ 1,
                Vector(self.root_radius, 0).rotate(Axis.Z, -2 * half_thick_angle),
                self.root_radius,
            )
            RadiusArc(
                l1 @ 1,
                Vector(self.addendum_radius, 0),
                -self.addendum_radius,
            )
            if root_fillet is not None:
                try:
                    fillet(tooth.vertices().sort_by(Axis.X)[1], root_fillet)
                except ValueError as err:
                    raise ValueError(
                        "Invalid root radius, try a smaller value"
                    ) from err

            mirror(tooth.edges(), about=Plane.XZ)

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

        super().__init__(Wire.combine(tooth.edges() + close)[0], mode=mode)


class RackGearPlan(BaseSketchObject):
    """Create a finite metric basic-rack profile in the transverse XY plane.

    A rack tooth does not have a finite involute curve. It is the infinite-radius
    limiting form of an involute gear tooth, so each flank is a straight line at
    the transverse pressure angle. End boundaries lie on tooth-space centerlines,
    giving an exact pitch length of ``tooth_count * pi * transverse_module``.

    Args:
        module: Normal or transverse metric module in millimeters, selected by
            ``module_system``.
        tooth_count: Number of complete teeth in the finite rack.
        pressure_angle: Normal or transverse pressure angle in degrees, selected
            by ``module_system``.
        helix_angle: Signed rack tooth angle in degrees. Defaults to 0.
        module_system: Measurement plane for ``module`` and ``pressure_angle``.
            Defaults to ``"normal"``.
        root_fillet: Optional radius of each concave tooth-root fillet. A value
            of zero leaves the roots unfilleted.
        addendum: Tooth height above the pitch line. Defaults to ``module``.
        dedendum: Tooth depth below the pitch line. Defaults to ``1.25 * module``.
        base_height: Material below the root line. Defaults to ``2 * module``.
        rotation: In-plane rotation in degrees. Defaults to 0.
        align: Build123d sketch alignment. Defaults to Y=0 at the pitch line.
        mode: Build123d combination mode. Defaults to ``Mode.ADD``.

    Raises:
        ValueError: If a dimension, angle, module system, or resulting tooth
            proportion is invalid.
    """

    @staticmethod
    def _validate_parameters(
        module: float,
        tooth_count: int,
        pressure_angle: float,
        helix_angle: float,
        module_system: Literal["normal", "transverse"],
        root_fillet: float | None,
        addendum: float | None,
        dedendum: float | None,
        base_height: float,
    ) -> None:
        """Validate values shared by the rack plan and solid."""
        if module <= 0:
            raise ValueError("module must be greater than zero")
        if (
            not isinstance(tooth_count, int)
            or isinstance(tooth_count, bool)
            or tooth_count <= 0
        ):
            raise ValueError("tooth_count must be a positive integer")
        if not 0 <= pressure_angle < 90:
            raise ValueError("pressure_angle must be in the range [0, 90)")
        if not -90 < helix_angle < 90:
            raise ValueError("helix_angle must be in the range (-90, 90)")
        if module_system not in ("normal", "transverse"):
            raise ValueError("module_system must be either 'normal' or 'transverse'")
        if root_fillet is not None and root_fillet < 0:
            raise ValueError("root_fillet must be non-negative")
        if addendum is not None and addendum <= 0:
            raise ValueError("addendum must be greater than zero")
        if dedendum is not None and dedendum <= 0:
            raise ValueError("dedendum must be greater than zero")
        if base_height <= 0:
            raise ValueError("base_height must be greater than zero")

    @staticmethod
    def _reference_values(
        module: float,
        pressure_angle: float,
        helix_angle: float,
        module_system: Literal["normal", "transverse"],
    ) -> tuple[float, float, float, float]:
        """Return normal/transverse module and pressure-angle values."""
        beta = radians(helix_angle)
        if module_system == "normal":
            normal_module = module
            transverse_module = module / cos(beta)
            normal_pressure_angle = pressure_angle
            transverse_pressure_angle = degrees(
                atan(tan(radians(pressure_angle)) / cos(beta))
            )
        else:
            transverse_module = module
            normal_module = module * cos(beta)
            transverse_pressure_angle = pressure_angle
            normal_pressure_angle = degrees(
                atan(tan(radians(pressure_angle)) * cos(beta))
            )
        return (
            normal_module,
            transverse_module,
            normal_pressure_angle,
            transverse_pressure_angle,
        )

    def __init__(
        self,
        module: float,
        tooth_count: int,
        pressure_angle: float,
        helix_angle: float = 0,
        module_system: Literal["normal", "transverse"] = "normal",
        root_fillet: float | None = None,
        addendum: float | None = None,
        dedendum: float | None = None,
        base_height: float | None = None,
        rotation: float = 0,
        align: Align | tuple[Align, Align] = Align.NONE,
        mode: Mode = Mode.ADD,
    ):
        resolved_base_height = 2 * module if base_height is None else base_height
        self._validate_parameters(
            module,
            tooth_count,
            pressure_angle,
            helix_angle,
            module_system,
            root_fillet,
            addendum,
            dedendum,
            resolved_base_height,
        )

        (
            self.normal_module,
            self.transverse_module,
            self.normal_pressure_angle,
            self.transverse_pressure_angle,
        ) = self._reference_values(module, pressure_angle, helix_angle, module_system)

        self.module = module
        self.module_system = module_system
        self.tooth_count = tooth_count
        self.pressure_angle = pressure_angle
        self.helix_angle = helix_angle
        self.addendum = module if addendum is None else addendum
        self.dedendum = 1.25 * module if dedendum is None else dedendum
        self.root_fillet = root_fillet
        self.base_height = resolved_base_height
        self.pitch = pi * self.transverse_module
        self.pitch_length = tooth_count * self.pitch
        self.tooth_height = self.addendum + self.dedendum

        alpha_t = radians(self.transverse_pressure_angle)
        half_pitch_thickness = self.pitch / 4
        half_tip = half_pitch_thickness - self.addendum * tan(alpha_t)
        half_root = half_pitch_thickness + self.dedendum * tan(alpha_t)
        half_space = self.pitch / 2 - half_root
        if half_tip <= 0:
            raise ValueError(
                "addendum and pressure_angle produce zero or negative tip width"
            )
        if half_space <= 0:
            raise ValueError(
                "dedendum and pressure_angle produce zero or negative root space"
            )

        # Constructive form: an array of pressure-angle trapezoidal teeth
        # joined to the rectangular rack body at the root line.
        tooth_profile = Trapezoid(
            width=2 * half_root,
            height=self.tooth_height,
            left_side_angle=90 - self.transverse_pressure_angle,
            right_side_angle=90 - self.transverse_pressure_angle,
            align=(Align.CENTER, Align.MIN),
        )

        rack_profile = Pos(0, -self.dedendum) * (
            Rectangle(
                self.pitch_length, self.base_height, align=(Align.CENTER, Align.MAX)
            )
            + GridLocations(self.pitch, 0, tooth_count, 1) * tooth_profile
        )
        if root_fillet not in (None, 0):
            try:
                root_vertices = (
                    rack_profile.vertices().group_by(Axis.Y)[1].sort_by(Axis.X)[1:-1]
                )
                rack_profile = fillet(root_vertices, root_fillet)
            except ValueError as err:
                raise ValueError(
                    "Invalid root fillet radius, try a smaller value"
                ) from err

        super().__init__(rack_profile, rotation, align, mode)


class RackGear(BasePartObject):
    """Create a finite straight or helical metric rack gear.

    Args:
        module: Normal or transverse metric module in millimeters, selected by
            ``module_system``.
        tooth_count: Number of complete rack teeth.
        pressure_angle: Pressure angle in degrees in the selected measurement plane.
        thickness: Rack face width along Y in millimeters.
        helix_angle: Signed rack tooth angle in degrees. Defaults to 0.
        module_system: Measurement plane for ``module`` and ``pressure_angle``.
            Defaults to ``"normal"``.
        root_fillet: Optional concave tooth-root fillet radius.
        addendum: Tooth height above the pitch line. Defaults to ``module``.
        dedendum: Tooth depth below the pitch line. Defaults to ``1.25 * module``.
        base_height: Material below the tooth root. Defaults to ``2 * module``.
        rotation: Build123d object rotation. Defaults to no rotation.
        align: Build123d part alignment. Defaults to Z=0 at pitch line.
        mode: Build123d combination mode. Defaults to ``Mode.ADD``.

    Raises:
        ValueError: If thickness or a rack-plan parameter is invalid.
    """

    def __init__(
        self,
        module: float,
        tooth_count: int,
        pressure_angle: float,
        thickness: float,
        helix_angle: float = 0,
        module_system: Literal["normal", "transverse"] = "normal",
        root_fillet: float | None = None,
        addendum: float | None = None,
        dedendum: float | None = None,
        base_height: float | None = None,
        rotation: RotationLike = (0, 0, 0),
        align: Align | tuple[Align, Align, Align] | None = Align.NONE,
        mode: Mode = Mode.ADD,
    ):
        if thickness <= 0:
            raise ValueError("thickness must be greater than zero")

        rack_plan = RackGearPlan(
            module=module,
            tooth_count=tooth_count,
            pressure_angle=pressure_angle,
            helix_angle=helix_angle,
            module_system=module_system,
            root_fillet=root_fillet,
            addendum=addendum,
            dedendum=dedendum,
            base_height=base_height,
        )
        for attribute in (
            "module",
            "module_system",
            "tooth_count",
            "pressure_angle",
            "helix_angle",
            "normal_module",
            "transverse_module",
            "normal_pressure_angle",
            "transverse_pressure_angle",
            "addendum",
            "dedendum",
            "root_fillet",
            "base_height",
            "pitch",
            "pitch_length",
            "tooth_height",
        ):
            setattr(self, attribute, getattr(rack_plan, attribute))
        self.thickness = thickness
        self.lateral_offset = thickness * tan(radians(helix_angle))

        if helix_angle == 0:
            rack = Solid.extrude(rack_plan.face(), Vector(0, 0, thickness))
        else:
            # Ruled loft between equivalent planar profiles gives linear tooth traces.
            top_plan = Pos(self.lateral_offset, 0, thickness) * rack_plan
            rack = Solid.make_loft(
                [rack_plan.face().wire(), top_plan.face().wire()], ruled=True
            )
        super().__init__(
            Rot(X=90) * Pos(Z=-thickness / 2) * rack, rotation, align, mode
        )
        self.material = alloy_steel(
            grade=AlloySteel.G4140_QUENCHED_TEMPERED, finish=black_oxide()
        )


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


# ---------------------------------------------------------------------------
# Worm gears
# ---------------------------------------------------------------------------

FlankForm = Literal["ZI", "ZA"]
Hand = Literal["right", "left"]
FlankSide = Literal["lower", "upper"]


def _involute(angle: float) -> float:
    """Involute function inv(α) = tan(α) − α, with α in radians."""
    return tan(angle) - angle


def _uv_faces(surface: Face, corners: list[tuple[float, float]]) -> list[Face]:
    """Faces on ``surface`` bounded by straight segments between ``corners`` in
    its (u, v) parameter space.

    Every worm face has such a domain: helices are straight lines in a cylinder's
    (angle, z) space, and on a ruled helicoid z is linear in both parameters so
    z = const trims are straight lines too. Writing the outline into parameter
    space avoids surface/surface intersections entirely. An outline crossing the
    seam of a cylinder comes back as one face on each side of it.
    """
    outline = Face(Polyline(*corners, close=True))
    return list(UVFrame(surface, Matrix()).write_face(outline))


def _edges_at_z(faces: list[Face], z: float, tolerance: float = 1e-5) -> list[Edge]:
    """The edges of ``faces`` lying in the plane at height ``z``."""
    return [
        edge
        for face in faces
        for edge in face.edges()
        if all(abs(edge.position_at(t).Z - z) < tolerance for t in (0, 0.5, 1))
    ]


def _u_parameter(
    z_start: float, root_offset: float, tip_offset: float, u_scale: float
) -> Callable[[float, float], float]:
    """Return ``u_at(z, v)``: the u parameter of a ruled helicoid at height ``z``
    on the v = const isoline, given the axial offsets of its bounding helices."""

    def u_at(z: float, v: float) -> float:
        return (z - z_start - (1 - v) * root_offset - v * tip_offset) * u_scale

    return u_at


class _WormGeometry:
    """Derived dimensions of a cylindrical worm (ISO 54 / DIN 3975 nomenclature).

    The worm axis is Z, the reference tooth (start 0) is centred on the +X axis
    in the z = 0 transverse plane, and the worm is right handed. Left-handed
    worms are produced by mirroring the finished geometry.

    Two flank forms are supported, both exact ruled surfaces between two helices
    of the worm's lead:

    * ``"ZI"`` (involute helicoid): the tangent developable of the base helix.
      Rulings are tangent to the base cylinder, transverse sections are circle
      involutes, and the normal pressure angle is constant. This is the only
      form conjugate to an involute (helical) worm wheel.
    * ``"ZA"`` (Archimedean helicoid): straight flanks at the axial pressure angle
      in every axial section (like a trapezoidal thread); transverse sections are
      Archimedean spirals.
    """

    def __init__(
        self,
        module: float,
        starts: int,
        diametral_quotient: float,
        pressure_angle: float,
        flank_form: FlankForm,
        addendum: float | None,
        dedendum: float | None,
    ):
        if module <= 0:
            raise ValueError("module must be greater than zero")
        if not isinstance(starts, int) or isinstance(starts, bool) or starts <= 0:
            raise ValueError("starts must be a positive integer")
        if diametral_quotient <= 0:
            raise ValueError("diametral_quotient must be greater than zero")
        if not 0 < pressure_angle < 90:
            raise ValueError("pressure_angle must be in the range (0, 90)")
        if flank_form not in ("ZI", "ZA"):
            raise ValueError("flank_form must be either 'ZI' or 'ZA'")
        if addendum is not None and addendum <= 0:
            raise ValueError("addendum must be greater than zero")
        if dedendum is not None and dedendum <= 0:
            raise ValueError("dedendum must be greater than zero")

        self.module = module
        self.starts = starts
        self.diametral_quotient = diametral_quotient
        self.flank_form = flank_form
        self.normal_pressure_angle = pressure_angle
        self.addendum = module if addendum is None else addendum
        self.dedendum = 1.2 * module if dedendum is None else dedendum

        self.pitch_radius = module * diametral_quotient / 2
        self.addendum_radius = self.pitch_radius + self.addendum
        self.root_radius = self.pitch_radius - self.dedendum
        if self.root_radius <= 0:
            raise ValueError("dedendum must be less than the reference radius")
        self.axial_pitch = pi * module
        self.lead = pi * module * starts
        self._advance = self.lead / (2 * pi)  # axial advance per radian of rotation
        gamma = atan(starts / diametral_quotient)
        alpha_n = radians(pressure_angle)
        self.lead_angle = degrees(gamma)
        self.axial_pressure_angle = degrees(atan(tan(alpha_n) / cos(gamma)))

        if flank_form == "ZI":
            # cos γb = cos γ · cos αn relates the base and reference helices of an
            # involute helicoid; the lead is shared so r·tan(γ_r) is constant.
            self._gamma_b = acos(cos(gamma) * cos(alpha_n))
            self._base_radius = self._advance / tan(self._gamma_b)
            self._alpha_t1 = acos(self._base_radius / self.pitch_radius)
            self.base_lead_angle: float | None = degrees(self._gamma_b)
            self.base_radius: float | None = self._base_radius
            self.transverse_pressure_angle: float | None = degrees(self._alpha_t1)
        else:
            self._gamma_b = self._base_radius = self._alpha_t1 = nan
            self.base_lead_angle = None
            self.base_radius = None
            self.transverse_pressure_angle = None

        if self.half_thickness_angle(self.addendum_radius) <= 0:
            raise ValueError(
                "addendum and pressure_angle produce zero or negative tip width"
            )
        if self.half_thickness_angle(self.root_radius) >= pi / starts:
            raise ValueError(
                "dedendum and pressure_angle produce zero or negative root space"
            )

    def half_thickness_angle(self, radius: float) -> float:
        """Half the angular tooth thickness (radians) in a transverse section."""
        half_pitch_angle = pi / (2 * self.starts)
        if self.flank_form == "ZA":
            return (
                half_pitch_angle
                - (radius - self.pitch_radius)
                * tan(radians(self.axial_pressure_angle))
                / self._advance
            )
        alpha_t = acos(self._base_radius / max(radius, self._base_radius))
        return half_pitch_angle + _involute(self._alpha_t1) - _involute(alpha_t)

    def flank_helix(self, radius: float, side: int) -> tuple[float, float]:
        """Phase and axial offset of a flank helix.

        The flank of the tooth centred on angle 0 at z = 0 crosses the cylinder of
        ``radius`` along the helix ``(radius, phase + z/advance, z + offset)``.
        ``side`` +1 is the flank facing −Z (lower), −1 the flank facing +Z (upper).
        """
        if self.flank_form == "ZA":
            return (
                side * pi / (2 * self.starts),
                side
                * (radius - self.pitch_radius)
                * tan(radians(self.axial_pressure_angle)),
            )
        # ZI: rulings are tangents of the base helix. The ruling touching the base
        # helix at angle θ reaches ``radius`` at angle θ + acos(rb/r) and has risen
        # by sqrt(r² − rb²)·tan(γb). Below the base cylinder the flank continues
        # radially (a plain helicoid), as an involute is undefined there.
        base_phase = side * (pi / (2 * self.starts) + _involute(self._alpha_t1))
        if radius <= self._base_radius:
            return base_phase, 0.0
        return (
            base_phase + side * acos(self._base_radius / radius),
            side * sqrt(radius**2 - self._base_radius**2) * tan(self._gamma_b),
        )

    def flank_angle(self, radius: float, side: int, z: float) -> float:
        """Angle of a flank of the reference tooth at ``radius`` and height ``z``."""
        phase, offset = self.flank_helix(radius, side)
        return phase + (z - offset) / self._advance

    def flank_radii(self) -> list[tuple[float, float]]:
        """Radial spans of the ruled surfaces making up one flank, root to tip."""
        if self.flank_form == "ZI" and self.root_radius < self._base_radius:
            return [
                (self.root_radius, self._base_radius),
                (self._base_radius, self.addendum_radius),
            ]
        return [(self.root_radius, self.addendum_radius)]

    def helix_span(self, length: float) -> tuple[float, float]:
        """Start height and height of helices covering z ∈ [−length/2, length/2]
        with margin for the flank offsets, starting a whole number of leads below
        z = 0 so the phase at z = 0 is unchanged."""
        start = -self.lead * ceil(length / (2 * self.lead) + 1)
        return start, -2 * start

    def flank_surfaces(
        self, side: int, tooth_angle: float, length: float
    ) -> list[tuple[Face, Callable[[float, float], float]]]:
        """Ruled helicoid surfaces of one flank of the tooth centred on ``tooth_angle``.

        Returns:
            (surface, u_at) pairs from root to tip where ``u_at(z, v)`` gives the
            surface u parameter at height ``z`` on the v = const isoline.
        """
        z_start, height = self.helix_span(length)
        total_angle = 2 * pi * height / self.lead
        surfaces: list[tuple[Face, Callable[[float, float], float]]] = []
        for radii in self.flank_radii():
            helices, offsets = [], []
            for radius in radii:
                phase, offset = self.flank_helix(radius, side)
                helix = Helix(
                    self.lead, height, radius, center=(0, 0, z_start + offset)
                )
                helices.append(helix.rotate(Axis.Z, degrees(tooth_angle + phase)))
                offsets.append(offset)
            surface = Face.make_surface_from_curves(helices[0], helices[1])
            # the ruled surface's u is the first helix's parameter
            u_max = helices[0].param_at(1.0)
            # z is linear along the helices (u) and along the rulings (v):
            # z(u, v) = z_start + advance·total_angle·u/u_max + (1−v)·offset0 + v·offset1
            u_scale = u_max / (self._advance * total_angle)
            surfaces.append(
                (surface, _u_parameter(z_start, offsets[0], offsets[1], u_scale))
            )
        return surfaces


_WORM_ATTRIBUTES = (
    "module",
    "starts",
    "diametral_quotient",
    "flank_form",
    "normal_pressure_angle",
    "axial_pressure_angle",
    "transverse_pressure_angle",
    "addendum",
    "dedendum",
    "pitch_radius",
    "addendum_radius",
    "root_radius",
    "base_radius",
    "axial_pitch",
    "lead",
    "lead_angle",
    "base_lead_angle",
)


class WormFlank(Face):
    """The working flank surface of one worm thread.

    Both supported flank forms are exact ruled surfaces between two helices of
    the worm's lead, so the face is an OCCT ruled surface rather than a swept or
    lofted approximation. The tooth is centred on the +X axis at z = 0 and the
    face spans the axial length ``[-length/2, length/2]``.

    Args:
        module: Axial module in millimeters (equal to the worm wheel's transverse
            module).
        starts: Number of threads.
        diametral_quotient: q = reference diameter / module (ISO 54). The lead
            angle follows from ``tan(γ) = starts / q``.
        length: Axial length of the flank.
        pressure_angle: Normal pressure angle in degrees. Defaults to 20.
        flank_form: ``"ZI"`` involute helicoid or ``"ZA"`` Archimedean helicoid.
            Defaults to ``"ZI"``.
        hand: Thread hand. Defaults to ``"right"``.
        side: ``"lower"`` is the flank facing −Z, ``"upper"`` the flank facing +Z.
            Defaults to ``"lower"``.
        addendum: Radial addendum. Defaults to ``module``.
        dedendum: Radial dedendum. Defaults to ``1.2 * module`` (DIN 3975).

    Raises:
        ValueError: If a parameter is invalid or the tooth proportions are
            impossible.

    Note:
        A ZI flank exists only outside the base cylinder. When the root radius is
        smaller than the base radius the face starts at the base radius;
        :class:`Worm` closes the tooth below it with a radial helicoid.
    """

    def __init__(
        self,
        module: float,
        starts: int,
        diametral_quotient: float,
        length: float,
        pressure_angle: float = 20,
        flank_form: FlankForm = "ZI",
        hand: Hand = "right",
        side: FlankSide = "lower",
        addendum: float | None = None,
        dedendum: float | None = None,
    ):
        if length <= 0:
            raise ValueError("length must be greater than zero")
        if hand not in ("right", "left"):
            raise ValueError("hand must be either 'right' or 'left'")
        if side not in ("lower", "upper"):
            raise ValueError("side must be either 'lower' or 'upper'")
        geometry = _WormGeometry(
            module,
            starts,
            diametral_quotient,
            pressure_angle,
            flank_form,
            addendum,
            dedendum,
        )
        surface, u_at = geometry.flank_surfaces(
            1 if side == "lower" else -1, 0, length
        )[-1]
        z0, z1 = -length / 2, length / 2
        # a ruled surface has no seam, so the outline writes as one face
        (face,) = _uv_faces(
            surface,
            [(u_at(z0, 0), 0), (u_at(z0, 1), 1), (u_at(z1, 1), 1), (u_at(z1, 0), 0)],
        )
        if hand == "left":
            face = face.mirror(Plane.XZ)
        super().__init__(face.wrapped)
        self.axial_length = length
        self.hand = hand
        self.side = side
        self.inner_radius = geometry.flank_radii()[-1][0]
        for attribute in _WORM_ATTRIBUTES:
            setattr(self, attribute, getattr(geometry, attribute))


class Worm(BasePartObject):
    """A cylindrical worm with ISO 54 / DIN 3975 proportions.

    The worm is built as a single exact boundary representation: ruled-helicoid
    flanks (see :class:`WormFlank`), cylindrical tip and root surfaces, and planar
    ends — no sweeps or boolean operations are involved, so construction takes
    milliseconds and the transverse section matches the analytic tooth profile.
    The axis is Z, the part is centred on the origin, and thread 0 is centred on
    the +X axis at z = 0.

    Args:
        module: Axial module in millimeters (equal to the worm wheel's transverse
            module).
        starts: Number of threads.
        diametral_quotient: q = reference diameter / module (ISO 54); typical
            values are 8 to 12. The lead angle follows from ``tan(γ) = starts / q``.
        length: Axial length of the worm.
        pressure_angle: Normal pressure angle in degrees. Defaults to 20.
        flank_form: ``"ZI"`` involute helicoid (conjugate to an involute worm
            wheel) or ``"ZA"`` Archimedean helicoid. Defaults to ``"ZI"``.
        hand: Thread hand. Defaults to ``"right"``.
        addendum: Radial addendum. Defaults to ``module``.
        dedendum: Radial dedendum. Defaults to ``1.2 * module`` (DIN 3975).
        rotation: Build123d object rotation. Defaults to no rotation.
        align: Build123d part alignment. Defaults to ``Align.CENTER``.
        mode: Build123d combination mode. Defaults to ``Mode.ADD``.

    Raises:
        ValueError: If a parameter is invalid or the tooth proportions are
            impossible.
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        module: float,
        starts: int,
        diametral_quotient: float,
        length: float,
        pressure_angle: float = 20,
        flank_form: FlankForm = "ZI",
        hand: Hand = "right",
        addendum: float | None = None,
        dedendum: float | None = None,
        rotation: RotationLike = (0, 0, 0),
        align: Align | tuple[Align, Align, Align] | None = Align.CENTER,
        mode: Mode = Mode.ADD,
    ):
        if length <= 0:
            raise ValueError("length must be greater than zero")
        if hand not in ("right", "left"):
            raise ValueError("hand must be either 'right' or 'left'")
        geometry = _WormGeometry(
            module,
            starts,
            diametral_quotient,
            pressure_angle,
            flank_form,
            addendum,
            dedendum,
        )
        self.length = length
        self.hand = hand
        for attribute in _WORM_ATTRIBUTES:
            setattr(self, attribute, getattr(geometry, attribute))

        # Every face is split into axial bands no longer than one lead so that
        # OCCT's fixed-order quadrature stays accurate on the twisted flanks.
        band_count = ceil(length / geometry.lead)
        z_lines = [-length / 2 + length * i / band_count for i in range(band_count + 1)]
        advance = geometry._advance
        bands: list[Face] = []

        def add_bands(surface: Face, corners_at):
            for z_lo, z_hi in zip(z_lines, z_lines[1:]):
                bands.extend(_uv_faces(surface, corners_at(z_lo, z_hi)))

        for start in range(starts):
            tooth_angle = 2 * pi * start / starts
            for side in (1, -1):
                for surface, u_at in geometry.flank_surfaces(side, tooth_angle, length):
                    add_bands(
                        surface,
                        lambda z_lo, z_hi, u_at=u_at: [
                            (u_at(z_lo, 0), 0),
                            (u_at(z_lo, 1), 1),
                            (u_at(z_hi, 1), 1),
                            (u_at(z_hi, 0), 0),
                        ],
                    )
            # tip strip between this tooth's flanks and root strip to the next tooth
            tip_lo = tooth_angle + geometry.flank_angle(geometry.addendum_radius, -1, 0)
            tip_hi = tooth_angle + geometry.flank_angle(geometry.addendum_radius, 1, 0)
            root_lo = tooth_angle + geometry.flank_angle(geometry.root_radius, 1, 0)
            root_hi = (
                tooth_angle
                + 2 * pi / starts
                + geometry.flank_angle(geometry.root_radius, -1, 0)
            )
            for radius, angle_lo, angle_hi in (
                (geometry.addendum_radius, tip_lo, tip_hi),
                (geometry.root_radius, root_lo, root_hi),
            ):
                cylinder = (
                    Solid.make_cylinder(radius, length)
                    .faces()
                    .filter_by(GeomType.CYLINDER)[0]
                )
                add_bands(
                    cylinder,
                    lambda z_lo, z_hi, lo=angle_lo, hi=angle_hi: [
                        (lo + z_lo / advance, z_lo),
                        (hi + z_lo / advance, z_lo),
                        (hi + z_hi / advance, z_hi),
                        (lo + z_hi / advance, z_hi),
                    ],
                )
        # the end caps are bounded by the band edges in the end planes
        caps = [Face(Wire(_edges_at_z(bands, z))) for z in (z_lines[0], z_lines[-1])]

        # The band edges of adjacent faces are separately approximated copies of
        # the same helix, so sew with a tolerance above the approximation error.
        shell = Shell(bands + caps, tolerance=1e-5)
        if not shell.is_manifold:
            raise RuntimeError("worm surfaces did not sew into a closed shell")
        worm = Solid(shell)
        if hand == "left":
            worm = worm.mirror(Plane.XZ)

        super().__init__(worm, rotation, align, mode)
        self.material = alloy_steel(
            grade=AlloySteel.G4140_QUENCHED_TEMPERED, finish=black_oxide()
        )


class WormWheel(HelicalGear):
    """A worm wheel: an involute helical gear matched to a :class:`Worm`.

    For a 90° shaft angle the wheel's transverse module equals the worm's axial
    module, its helix angle equals the worm's lead angle (same hand), and its
    transverse pressure angle equals the worm's axial pressure angle. This is a
    plain (non-throated) wheel, exactly conjugate to a ``"ZI"`` worm.

    Args:
        module: Worm axial module = wheel transverse module in millimeters.
        tooth_count: Number of wheel teeth.
        thickness: Wheel face width.
        starts: Number of worm threads. Defaults to 1.
        diametral_quotient: Worm q = reference diameter / module. Defaults to 10.
        pressure_angle: Normal pressure angle in degrees. Defaults to 20.
        hand: Hand of the worm and wheel. Defaults to ``"right"``.
        root_fillet: Optional radius of the tooth-root fillet.
        addendum: Radial addendum. Defaults to ``module``.
        dedendum: Radial dedendum. Defaults to ``1.2 * module`` (DIN 3975).
        rotation: Build123d object rotation. Defaults to no rotation.
        align: Build123d part alignment. Defaults to ``Align.CENTER``.
        mode: Build123d combination mode. Defaults to ``Mode.ADD``.
    """

    def __init__(
        self,
        module: float,
        tooth_count: int,
        thickness: float,
        starts: int = 1,
        diametral_quotient: float = 10,
        pressure_angle: float = 20,
        hand: Hand = "right",
        root_fillet: float | None = None,
        addendum: float | None = None,
        dedendum: float | None = None,
        rotation: RotationLike = (0, 0, 0),
        align: Align | tuple[Align, Align, Align] | None = Align.CENTER,
        mode: Mode = Mode.ADD,
    ):
        if hand not in ("right", "left"):
            raise ValueError("hand must be either 'right' or 'left'")
        worm = _WormGeometry(
            module, starts, diametral_quotient, pressure_angle, "ZA", addendum, dedendum
        )
        super().__init__(
            module=module,
            tooth_count=tooth_count,
            pressure_angle=worm.axial_pressure_angle,
            helix_angle=worm.lead_angle if hand == "right" else -worm.lead_angle,
            thickness=thickness,
            module_system="transverse",
            root_fillet=root_fillet,
            addendum=worm.addendum,
            dedendum=worm.dedendum,
            rotation=rotation,
            align=align,
            mode=mode,
        )
        self.starts = starts
        self.diametral_quotient = diametral_quotient
        self.hand = hand
        self.lead_angle = worm.lead_angle
        self.axial_pressure_angle = worm.axial_pressure_angle
        self.center_distance = module * (diametral_quotient + tooth_count) / 2
        self.material = bronze()


class WormGear(Compound):
    """Assembly: a :class:`Worm` meshed with a :class:`WormWheel` at a 90° shaft angle.

    The wheel is centred on the origin with its axis along Z; the worm axis is
    parallel to Y through ``(center_distance, 0, 0)`` with a thread space facing
    the wheel tooth on the +X axis. ``RigidJoint`` "wheel" and "worm" mark the
    two axes.

    Args:
        module: Worm axial module = wheel transverse module in millimeters.
        starts: Number of worm threads.
        diametral_quotient: Worm q = reference diameter / module.
        tooth_count: Number of wheel teeth.
        worm_length: Axial length of the worm.
        wheel_thickness: Wheel face width.
        pressure_angle: Normal pressure angle in degrees. Defaults to 20.
        flank_form: Worm flank form. Defaults to ``"ZI"``.
        hand: Hand of the worm and wheel. Defaults to ``"right"``.
        root_fillet: Optional wheel tooth-root fillet radius.
    """

    def __init__(
        self,
        module: float,
        starts: int,
        diametral_quotient: float,
        tooth_count: int,
        worm_length: float,
        wheel_thickness: float,
        pressure_angle: float = 20,
        flank_form: FlankForm = "ZI",
        hand: Hand = "right",
        root_fillet: float | None = None,
    ):
        super().__init__()
        worm = Worm(
            module,
            starts,
            diametral_quotient,
            worm_length,
            pressure_angle,
            flank_form,
            hand,
        )
        wheel = WormWheel(
            module,
            tooth_count,
            wheel_thickness,
            starts,
            diametral_quotient,
            pressure_angle,
            hand,
            root_fillet,
        )
        self.center_distance = wheel.center_distance
        self.ratio = tooth_count / starts
        # Thread 0 is centred on the worm's local +X; turn a thread space to face
        # the wheel (local −X), then stand the worm axis along Y beside the wheel.
        worm = (
            Pos(self.center_distance, 0, 0)
            * Rot(X=-90)
            * Rot(Z=180 - 180 / starts)
            * worm
        )
        # HelicalGear twists from its bottom face, so undo half the twist to
        # centre a wheel tooth on +X in the z = 0 mid-plane.
        wheel = Rot(Z=-wheel.twist_angle / 2) * wheel
        worm.label = "worm"
        wheel.label = "wheel"
        self.children = [worm, wheel]
        RigidJoint("wheel", self, Location())
        RigidJoint("worm", self, Pos(self.center_distance, 0, 0) * Rot(X=-90))


# Number of points used to fit the spherical-involute spline in the developed plane.
# Points are spaced uniformly in the great-circle unwinding angle, which concentrates
# them near the base cone where the involute curvature is highest.
_INVOLUTE_SAMPLES = 21
# Number of points used to refit a developed spline after wrapping it onto the cone.
_WRAP_SAMPLES = 31
# Radial root-flank segments shorter than this fraction of the module are omitted.
_MIN_EDGE_LENGTH = 1e-3


def _spherical_involute_azimuth(polar_angle: float, base_cone_angle: float) -> float:
    """Azimuth (radians) of a spherical-involute point at ``polar_angle``.

    The involute is generated by unwinding a great circle from the base cone of
    half angle ``base_cone_angle`` on the unit sphere centred on the cone apex. The
    curve leaves the base cone at azimuth 0 and its azimuth increases with polar
    angle, like the planar involute function ``tan(a) - a`` it reduces to as the
    cone angles approach zero.
    """
    theta = acos(min(1.0, cos(polar_angle) / cos(base_cone_angle)))
    psi = theta / sin(base_cone_angle)
    sin_b = sin(base_cone_angle)
    return atan2(
        sin_b * sin(psi) * cos(theta) - cos(psi) * sin(theta),
        sin_b * cos(psi) * cos(theta) + sin(psi) * sin(theta),
    )


class SphericalInvoluteToothProfile(BaseLineObject):
    """SphericalInvoluteToothProfile

    The outline of a single straight-bevel tooth with exact spherical-involute
    flanks, developed onto the plane of the back cone.

    The output has the same layout as ``InvoluteToothProfile``: the origin is the
    back-cone apex, the tooth is centred on +X, radii are slant distances along the
    back cone and the profile spans one angular pitch of the developed back cone,
    ``2 * pi / virtual_tooth_count``, with half a root arc on each side. As
    ``pitch_cone_angle`` approaches zero the profile converges to the planar
    involute of ``InvoluteToothProfile(module, virtual_tooth_count, ...)``.

    Args:
        module (float): module at the outer (heel) end of the tooth, in millimeters.
        tooth_count (int): number of teeth of the bevel gear.
        pitch_cone_angle (float): pitch cone half angle in degrees, in (0, 90).
        pressure_angle (float, optional): pressure angle in degrees, in (0, 90).
            Defaults to 20, the ISO/AGMA standard. See :class:`BevelGear` for other
            common values.
        root_fillet (float, optional): radius of the fillet at the root of the tooth.
            Defaults to None.
        addendum (float, optional): tooth height above the pitch cone at the heel,
            measured along the back cone. Defaults to None (``module``).
        dedendum (float, optional): tooth depth below the pitch cone at the heel,
            measured along the back cone. Defaults to None (``1.25 * module``).
        closed (bool, optional): close the wire across the tooth space. Defaults
            to False.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.

    Raises:
        ValueError: invalid dimensions or angles, pointed teeth, no tooth space at
            the root, or a root fillet that is too large.
    """

    _applies_to = [BuildLine._tag]

    def __init__(
        self,
        module: float,
        tooth_count: int,
        pitch_cone_angle: float,
        pressure_angle: float = 20,
        root_fillet: float | None = None,
        addendum: float | None = None,
        dedendum: float | None = None,
        closed: bool = False,
        mode: Mode = Mode.ADD,
    ):
        if module <= 0:
            raise ValueError("module must be greater than zero")
        if (
            not isinstance(tooth_count, int)
            or isinstance(tooth_count, bool)
            or tooth_count <= 0
        ):
            raise ValueError("tooth_count must be a positive integer")
        if not 0 < pressure_angle < 90:
            raise ValueError("pressure_angle must be in the range (0, 90)")
        if not 0 < pitch_cone_angle < 90:
            raise ValueError("pitch_cone_angle must be in the range (0, 90)")
        if addendum is not None and addendum <= 0:
            raise ValueError("addendum must be greater than zero")
        if dedendum is not None and dedendum <= 0:
            raise ValueError("dedendum must be greater than zero")
        if root_fillet is not None and root_fillet < 0:
            raise ValueError("root_fillet must be non-negative")

        delta = radians(pitch_cone_angle)
        alpha = radians(pressure_angle)
        self.module = module
        self.tooth_count = tooth_count
        self.pressure_angle = pressure_angle
        self.pitch_cone_angle = pitch_cone_angle
        self.cone_distance = module * tooth_count / (2 * sin(delta))
        self.virtual_tooth_count = tooth_count / cos(delta)
        self.addendum = module if addendum is None else addendum
        self.dedendum = 1.25 * module if dedendum is None else dedendum
        base = asin(sin(delta) * cos(alpha))
        self.base_cone_angle = degrees(base)

        # Developed back-cone radius of the point at polar angle sigma (on the
        # back cone, measured from the gear axis at the cone apex).
        cone_distance = self.cone_distance
        self.pitch_radius = cone_distance * tan(delta)
        self.addendum_radius = self.pitch_radius + self.addendum
        self.root_radius = self.pitch_radius - self.dedendum
        self.base_radius = self.pitch_radius + cone_distance * tan(base - delta)
        if self.root_radius <= 0:
            raise ValueError("dedendum is too large for the back-cone radius")

        def developed(sigma: float, eta: float) -> Vector:
            radius = self.pitch_radius + cone_distance * tan(sigma - delta)
            angle = eta * cos(delta)
            return Vector(radius * cos(angle), radius * sin(angle))

        def flank_azimuth(sigma: float) -> float:
            """Half-tooth azimuth about the gear axis, measured from the centreline."""
            return (
                pi / (2 * tooth_count)
                + _spherical_involute_azimuth(delta, base)
                - _spherical_involute_azimuth(sigma, base)
            )

        tip_sigma = delta + atan(self.addendum / cone_distance)
        root_sigma = delta - atan(self.dedendum / cone_distance)
        # The involute exists only outside the base cone: start it on the base cone
        # or on the root cone, whichever is further out.
        start_sigma = max(base, root_sigma)
        if flank_azimuth(tip_sigma) <= 0:
            raise ValueError("addendum and pressure_angle produce pointed teeth")
        if flank_azimuth(start_sigma) >= pi / tooth_count:
            raise ValueError("dedendum and pressure_angle leave no tooth space")

        # Lower (-Y) half of the tooth, built like InvoluteToothProfile.
        theta_start = acos(min(1.0, cos(start_sigma) / cos(base)))
        theta_tip = acos(min(1.0, cos(tip_sigma) / cos(base)))
        involute_points = []
        for i in range(_INVOLUTE_SAMPLES):
            theta = theta_start + (theta_tip - theta_start) * i / (
                _INVOLUTE_SAMPLES - 1
            )
            sigma = acos(min(1.0, cos(base) * cos(theta)))
            involute_points.append(developed(sigma, -flank_azimuth(sigma)))
        if 0 < self.base_radius - self.root_radius <= _MIN_EDGE_LENGTH * module:
            # Root cone just inside the base cone: a radial line would be a sliver
            # edge. The involute is radial at the base cone, so move its first
            # point radially onto the root instead (shift <= _MIN_EDGE_LENGTH * m).
            involute_points[0] = developed(root_sigma, -flank_azimuth(base))
        half_space_angle = 180 / self.virtual_tooth_count

        with BuildLine() as tooth:
            l1 = Spline(*involute_points)
            if self.base_radius - self.root_radius > _MIN_EDGE_LENGTH * module:
                # Below the base cone the flank continues as a radial line, as in
                # InvoluteToothProfile.
                l2 = Line(
                    involute_points[0], developed(root_sigma, -flank_azimuth(base))
                )
                root_start = l2 @ 1
            else:
                # Root on or outside the base cone: the involute starts on the root.
                root_start = l1 @ 0
            RadiusArc(
                root_start,
                Vector(self.root_radius, 0).rotate(Axis.Z, -half_space_angle),
                self.root_radius,
            )
            RadiusArc(l1 @ 1, Vector(self.addendum_radius, 0), -self.addendum_radius)
            if root_fillet:
                try:
                    fillet(tooth.vertices().sort_by(Axis.X)[1], root_fillet)
                except ValueError as err:
                    raise ValueError(
                        "Invalid root radius, try a smaller value"
                    ) from err
            mirror(tooth.edges(), about=Plane.XZ)

        close = []
        if closed:
            ends = tooth.line.vertices().sort_by(Axis.Y)
            close = [Edge.make_line(Vector(ends[-1]), Vector(ends[0]))]
        super().__init__(Wire.combine(tooth.line.edges() + close)[0], mode=mode)


# ---------------------------------------------------------------------------
# B-rep construction helpers.
#
# The gear is first built in an "apex frame": cone apex at the origin, gear axis
# +Z, gear body at positive Z (the back face is the furthest from the apex). It is
# then turned over and translated so that the back face lies on z = 0 and the
# apex lies on +Z at ``mounting_distance``.
# ---------------------------------------------------------------------------


def _wrap_point(point: Vector, delta: float, cone_distance: float) -> Vector:
    """Wrap a developed back-cone point onto the back cone (apex frame).

    The back-cone apex lies on the gear axis at ``cone_distance / cos(delta)``.
    A developed point at slant radius ``r`` and angle ``phi`` maps to azimuth
    ``phi / cos(delta)`` -- the isometric inverse of cone development.
    """
    radius, phi = hypot(point.X, point.Y), atan2(point.Y, point.X)
    eta = phi / cos(delta)
    return Vector(
        radius * cos(delta) * cos(eta),
        radius * cos(delta) * sin(eta),
        cone_distance / cos(delta) - radius * sin(delta),
    )


def _wrap_edge(edge: Edge, delta: float, cone_distance: float) -> Edge:
    """Wrap a developed profile edge onto the back cone.

    Arcs centred on the back-cone apex become exact circles and radial lines
    become exact back-cone generators; other edges (involute splines, chords,
    root fillets) are refitted through wrapped samples.
    """
    start, end = edge @ 0, edge @ 1

    def wrap(point: Vector) -> Vector:
        return _wrap_point(point, delta, cone_distance)

    if (
        edge.geom_type == GeomType.CIRCLE
        and edge.arc_center.length < 1e-7 * edge.radius
    ):
        return Edge.make_three_point_arc(wrap(start), wrap(edge @ 0.5), wrap(end))
    radial = abs(start.X * end.Y - start.Y * end.X) < 1e-12 * max(
        1.0, start.length * end.length
    )
    if edge.geom_type == GeomType.LINE and radial:
        return Edge.make_line(wrap(start), wrap(end))
    return Edge.make_spline(
        [wrap(edge @ (i / (_WRAP_SAMPLES - 1))) for i in range(_WRAP_SAMPLES)]
    )


def _is_centred_arc(edge: Edge, radius: float) -> bool:
    """Is ``edge`` an arc of ``radius`` centred on the developed-profile origin?

    bd_warehouse builds its arcs with ``RadiusArc`` so their centres carry ~1e-9
    relative error; the tolerance is relative to the radius.
    """
    return (
        edge.geom_type == GeomType.CIRCLE
        and edge.arc_center.length < 1e-7 * radius
        and abs(edge.radius - radius) < 1e-7 * radius
    )


def _coaxial_cone_face(
    z_position: float,
    radius: float,
    semi_angle: float,
    outer_edges: list[Edge],
    inner_edge: Edge,
) -> Face:
    """Face on a cone coaxial with Z whose radius grows toward -Z.

    ``(radius, z_position)`` is a point on the cone's meridian and ``semi_angle``
    the angle between the cone generators and the axis, in radians.
    The face is bounded by the closed ``outer_edges`` loop and ``inner_edge``,
    which lie on the cone. The cone's surface comes from a cone solid with the
    same apex and semi-angle; its extent does not matter.
    """
    cone = Solid.make_cone(
        radius, 0, radius / tan(semi_angle), Plane(origin=(0, 0, z_position))
    )
    surface = cone.faces().filter_by(GeomType.CONE)[0]
    return Face(Wire(outer_edges), [Wire([inner_edge])], surface=surface)


def _annulus(z_position: float, outer_radius: float, inner_radius: float) -> Face:
    plane = Plane(origin=(0, 0, z_position))
    outer = Wire([Edge.make_circle(outer_radius, plane)])
    if inner_radius > 0:
        return Face(outer, [Wire([Edge.make_circle(inner_radius, plane)])])
    return Face(outer)


class BevelGear(BasePartObject):
    """BevelGear

    A straight bevel gear with exact spherical-involute teeth, built directly as a
    B-rep.

    Module, pressure angle, addendum and dedendum are specified at the outer
    (heel) end of the teeth. The pitch cone angle follows from the tooth counts of
    the pair and the shaft angle, ``tan(delta) = sin(shaft) / (z_mate / z +
    cos(shaft))``, so the two gears of a pair share one cone distance. Face, pitch
    and root cones share the cone apex; the teeth taper toward it.

    Placement: the gear axis is +Z, the back face lies on z = 0 and the teeth face
    +Z. The pitch cone apex is at ``apex = (0, 0, mounting_distance)`` and a tooth
    is centred on +X. Use :meth:`mate_location` to position the mating gear.

    Args:
        module (float): module at the heel, in millimeters.
        tooth_count (int): number of teeth on this gear.
        mate_tooth_count (int): number of teeth on the mating gear.
        face_width (float): tooth length along the pitch cone generator. At most
            one third of ``cone_distance`` (standard design limit).
        pressure_angle (float, optional): pressure angle in degrees, in (0, 90).
            Both gears of a pair must use the same value. Defaults to 20, the
            ISO/AGMA standard and the usual catalogue value. Other values in use:

            - 14.5: legacy (mainly inch-series) designs; smoother and quieter, but
              weaker and more prone to undercut at low tooth counts.
            - 17.5: occasionally used for quieter running.
            - 22.5: heavily loaded, slow-speed drives.
            - 25: higher tooth strength and less undercut; recommended by AGMA for
              straight bevel gears with very few (12-13) teeth.

        shaft_angle (float, optional): angle between the two gear axes in
            degrees, in (0, 180). Defaults to 90.
        root_fillet (float, optional): radius of the tooth-root fillet at the heel.
            Defaults to None.
        addendum (float, optional): heel addendum along the back cone. Defaults to
            None (``module``).
        dedendum (float, optional): heel dedendum along the back cone. Defaults to
            None (``1.25 * module``).
        bore_diameter (float, optional): diameter of a through bore on the axis.
            Defaults to None (solid).
        back_cone_width (float, optional): slant width of the back-cone band below
            the heel root, ending at the flat back face. Defaults to None
            (``1.5 * module``).
        front_cone_width (float, optional): slant width of the front-cone band
            below the toe root, ending at the flat front face. Defaults to None
            (``0.5 * module``).
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Align | tuple[Align, Align, Align] | None, optional): object
            alignment. Defaults to None, which keeps the placement described above.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.

    Raises:
        ValueError: invalid input, unsupported (crown or internal) cone angle, or a
            blank whose faces would not form a closed shell.
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        module: float,
        tooth_count: int,
        mate_tooth_count: int,
        face_width: float,
        pressure_angle: float = 20,
        shaft_angle: float = 90,
        root_fillet: float | None = None,
        addendum: float | None = None,
        dedendum: float | None = None,
        bore_diameter: float | None = None,
        back_cone_width: float | None = None,
        front_cone_width: float | None = None,
        rotation: RotationLike = (0, 0, 0),
        align: Align | tuple[Align, Align, Align] | None = None,
        mode: Mode = Mode.ADD,
    ):
        # ---- validate inputs --------------------------------------------------
        if module <= 0:
            raise ValueError("module must be greater than zero")
        for name, count in (
            ("tooth_count", tooth_count),
            ("mate_tooth_count", mate_tooth_count),
        ):
            if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not 0 < pressure_angle < 90:
            raise ValueError("pressure_angle must be in the range (0, 90)")
        if not 0 < shaft_angle < 180:
            raise ValueError("shaft_angle must be in the range (0, 180)")
        for name, value in (
            ("addendum", addendum),
            ("dedendum", dedendum),
            ("back_cone_width", back_cone_width),
            ("front_cone_width", front_cone_width),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if bore_diameter is not None and bore_diameter <= 0:
            raise ValueError("bore_diameter must be greater than zero")
        if root_fillet is not None and root_fillet < 0:
            raise ValueError("root_fillet must be non-negative")

        sigma = radians(shaft_angle)
        delta = atan2(sin(sigma), mate_tooth_count / tooth_count + cos(sigma))
        if delta >= pi / 2 - 1e-9:
            raise ValueError(
                "pitch cone angle must be below 90 degrees; crown and internal "
                "bevel gears are not supported"
            )
        cone_distance = module * tooth_count / (2 * sin(delta))
        if not 0 < face_width <= cone_distance / 3 + 1e-9:
            raise ValueError(
                f"face_width must be greater than zero and at most cone_distance / 3 "
                f"({cone_distance / 3:.4g} mm)"
            )

        ha = module if addendum is None else addendum
        hf = 1.25 * module if dedendum is None else dedendum
        if cone_distance * tan(delta) - hf <= 0:
            raise ValueError("dedendum is too large for the back-cone radius")
        lb = 1.5 * module if back_cone_width is None else back_cone_width
        lf = 0.5 * module if front_cone_width is None else front_cone_width
        bore_radius = 0.0 if bore_diameter is None else bore_diameter / 2

        # ---- pitch geometry and blank layout (apex frame, meridian r-z) --------
        k = (cone_distance - face_width) / cone_distance  # toe / heel scale
        theta_a, theta_f = atan(ha / cone_distance), atan(hf / cone_distance)
        heel_root_r = cone_distance / cos(theta_f) * sin(delta - theta_f)
        heel_root_z = cone_distance / cos(theta_f) * cos(delta - theta_f)
        heel_tip_r = cone_distance / cos(theta_a) * sin(delta + theta_a)
        heel_tip_z = cone_distance / cos(theta_a) * cos(delta + theta_a)
        # Moving inward along a back/front cone generator: (-cos(delta), sin(delta)).
        r_back, z_back = heel_root_r - lb * cos(delta), heel_root_z + lb * sin(delta)
        r_front = k * heel_root_r - lf * cos(delta)
        z_front = k * heel_root_z + lf * sin(delta)
        if r_back <= bore_radius:
            raise ValueError("back_cone_width or bore_diameter is too large")
        if r_front <= bore_radius:
            raise ValueError("front_cone_width or bore_diameter is too large")
        if z_front >= z_back:
            raise ValueError("front face would lie behind the back face")

        # ---- developed tooth profile -------------------------------------------
        profile = SphericalInvoluteToothProfile(
            module,
            tooth_count,
            degrees(delta),
            pressure_angle,
            root_fillet=root_fillet,
            addendum=ha,
            dedendum=hf,
        )

        # ---- store design values -----------------------------------------------
        self.module = module
        self.tooth_count = tooth_count
        self.mate_tooth_count = mate_tooth_count
        self.pressure_angle = pressure_angle
        self.shaft_angle = shaft_angle
        self.face_width = face_width
        self.addendum = ha
        self.dedendum = hf
        self.root_fillet = root_fillet
        self.bore_diameter = bore_diameter
        self.back_cone_width = lb
        self.front_cone_width = lf
        self.pitch_cone_angle = degrees(delta)
        self.mate_pitch_cone_angle = shaft_angle - self.pitch_cone_angle
        self.addendum_angle = degrees(theta_a)
        self.dedendum_angle = degrees(theta_f)
        self.face_cone_angle = degrees(delta + theta_a)
        self.root_cone_angle = degrees(delta - theta_f)
        self.base_cone_angle = profile.base_cone_angle
        self.cone_distance = cone_distance
        self.inner_cone_distance = cone_distance - face_width
        self.virtual_tooth_count = profile.virtual_tooth_count
        self.pitch_radius = module * tooth_count / 2
        self.pitch_diameter = module * tooth_count
        self.outside_diameter = 2 * heel_tip_r
        self.mounting_distance = z_back
        self.apex = Vector(0, 0, z_back)
        self.pitch_apex_to_crown = heel_tip_z
        self.front_face_height = z_back - z_front
        self.back_face_diameter = 2 * r_back
        self.front_face_diameter = 2 * r_front
        self.total_height = z_back - k * heel_tip_z
        self.tooth_profile = profile

        # ---- one pitch of heel (back-cone) edges --------------------------------
        def wrap_point(point: Vector) -> Vector:
            return _wrap_point(point, delta, cone_distance)

        def wrap(edge: Edge) -> Edge:
            return _wrap_edge(edge, delta, cone_distance)

        lower_flank = sorted(
            (
                e
                for e in profile.edges()
                if (e @ 0.5).Y < 0
                and not _is_centred_arc(e, profile.root_radius)
                and not _is_centred_arc(e, profile.addendum_radius)
            ),
            key=lambda e: (e @ 0.5).length,
        )
        if not lower_flank:
            raise ValueError("unable to identify the tooth flank in the profile")
        upper_flank = [e.mirror(Plane.XZ) for e in reversed(lower_flank)]
        root_point = min(
            (lower_flank[0] @ 0, lower_flank[0] @ 1), key=lambda p: p.length
        )
        tip_point = max(
            (lower_flank[-1] @ 0, lower_flank[-1] @ 1), key=lambda p: p.length
        )

        pitch_angle = 360 / tooth_count
        heel_root_lower = wrap_point(root_point)
        heel_root_upper = wrap_point(Vector(root_point.X, -root_point.Y))
        heel_tip_lower = wrap_point(tip_point)
        heel_tip_upper = wrap_point(Vector(tip_point.X, -tip_point.Y))
        tip_span = 2 * degrees(atan2(heel_tip_upper.Y, heel_tip_upper.X))
        root_span = pitch_angle - 2 * degrees(
            atan2(heel_root_upper.Y, heel_root_upper.X)
        )
        if tip_span <= 1e-6 or root_span <= 1e-6:
            raise ValueError("tooth proportions leave no tip land or root space")

        # Centre of the tooth space, half a developed pitch from the tooth centre.
        half_space = degrees(pi * cos(delta) / tooth_count)
        tip_arc = Edge.make_three_point_arc(
            heel_tip_lower,
            wrap_point(Vector(profile.addendum_radius, 0)),
            heel_tip_upper,
        )
        root_arc = Edge.make_three_point_arc(
            heel_root_upper,
            wrap_point(Vector(profile.root_radius, 0).rotate(Axis.Z, half_space)),
            heel_root_lower.rotate(Axis.Z, pitch_angle),
        )
        lower_heel = [wrap(e) for e in lower_flank]
        upper_heel = [wrap(e) for e in upper_flank]
        # One closed pitch of the heel boundary, in sequence around the gear.
        pitch_edges = lower_heel + [tip_arc] + upper_heel + [root_arc]

        # ---- tooth faces: ruled toward the apex ---------------------------------
        # Toe edges are heel edges scaled about the apex, so each ruled face is the
        # exact cone through the apex over its heel edge.
        origin = (0, 0, 0)
        flank_faces = [
            Face.make_surface_from_curves(e, e.scale(k, about=origin))
            for e in lower_heel + upper_heel
        ]
        # Face and root cone patches are exact cones: revolve the apex generator.
        tip_face = Face.revolve(
            Edge.make_line(heel_tip_lower, heel_tip_lower * k), tip_span, Axis.Z
        )
        root_face = Face.revolve(
            Edge.make_line(heel_root_upper, heel_root_upper * k), root_span, Axis.Z
        )
        pitch_faces = flank_faces + [tip_face, root_face]

        faces: list[Face] = []
        heel_edges: list[Edge] = []
        for index in range(tooth_count):
            location = Rot(0, 0, index * pitch_angle)
            faces.extend(location * f for f in pitch_faces)
            heel_edges.extend(location * e for e in pitch_edges)
        toe_edges = [e.scale(k, about=origin) for e in heel_edges]

        # ---- blank faces --------------------------------------------------------
        def circle(radius: float, z_position: float) -> Edge:
            return Edge.make_circle(radius, Plane(origin=(0, 0, z_position)))

        back_cone_semi_angle = pi / 2 - delta
        faces.append(
            _coaxial_cone_face(
                z_back, r_back, back_cone_semi_angle, heel_edges, circle(r_back, z_back)
            )
        )
        faces.append(
            _coaxial_cone_face(
                z_front,
                r_front,
                back_cone_semi_angle,
                toe_edges,
                circle(r_front, z_front),
            )
        )
        faces.append(_annulus(z_back, r_back, bore_radius))
        faces.append(_annulus(z_front, r_front, bore_radius))
        if bore_radius > 0:
            faces.append(
                Face.extrude(circle(bore_radius, z_front), (0, 0, z_back - z_front))
            )

        # ---- sew and convert to a solid -----------------------------------------
        shell = Shell(faces)
        if not shell.is_manifold:
            raise ValueError("bevel gear faces did not sew into a closed shell")
        gear = Solid(shell)
        if not gear.is_valid or gear.volume <= 0:
            raise ValueError("bevel gear B-rep is not a valid solid")
        self.face_count = len(gear.faces())

        # Apex frame -> placement frame: back face on z = 0, teeth facing +Z.
        gear = Pos(0, 0, z_back) * Rot(180, 0, 0) * gear
        gear.material = alloy_steel(
            grade=AlloySteel.G4140_QUENCHED_TEMPERED, finish=black_oxide()
        )
        gear.label = "Bevel Gear"
        super().__init__(gear, rotation, align, mode)

    def mate_location(self, mate: "BevelGear", angle: float = 0.0) -> Location:
        """Location that places ``mate`` in mesh with this gear.

        Both gears must be in their default placement (``rotation=(0, 0, 0)``,
        ``align=None``). The pitch apexes coincide, the mate's axis lies in the XZ
        plane at ``shaft_angle`` to this gear's axis on the +X side, and the mate is
        phased so that a tooth space receives this gear's tooth on +X.

        Args:
            mate (BevelGear): the mating gear.
            angle (float, optional): rotation of this gear about its axis in
                degrees, i.e. this gear is placed with ``Rot(0, 0, angle)``. The
                mate is turned by the conjugate ``-angle * z / z_mate``.
                Defaults to 0.

        Raises:
            ValueError: the gears are not a mating pair.

        Returns:
            Location: location to apply to ``mate``.
        """
        if not isinstance(mate, BevelGear):
            raise ValueError("mate must be a BevelGear")
        if (
            mate.tooth_count != self.mate_tooth_count
            or mate.mate_tooth_count != self.tooth_count
        ):
            raise ValueError("tooth counts of the two gears do not form a pair")
        for name in ("module", "pressure_angle", "shaft_angle"):
            if abs(getattr(mate, name) - getattr(self, name)) > 1e-9:
                raise ValueError(f"{name} of the two gears differs")
        phase = 180 / mate.tooth_count if mate.tooth_count % 2 == 0 else 0.0
        mate_angle = phase - angle * self.tooth_count / mate.tooth_count
        return (
            Pos(0, 0, self.mounting_distance)
            * Rot(0, -self.shaft_angle, 0)
            * Pos(0, 0, -mate.mounting_distance)
            * Rot(0, 0, mate_angle)
        )


class MiterGear(BevelGear):
    """MiterGear

    A straight bevel gear that meshes with an identical gear: equal tooth counts,
    so a 1:1 ratio. With the default 90 degree shaft angle the pitch cone angle is
    45 degrees; other shaft angles give angular miter gears. See
    :class:`BevelGear` for the placement convention, the common pressure angles
    and the remaining arguments.

    Args:
        module (float): module at the heel, in millimeters.
        tooth_count (int): number of teeth on each gear of the pair.
        face_width (float): tooth length along the pitch cone generator.
        pressure_angle (float, optional): pressure angle in degrees. Defaults to 20.
        shaft_angle (float, optional): angle between the axes in degrees.
            Defaults to 90.
    """

    def __init__(
        self,
        module: float,
        tooth_count: int,
        face_width: float,
        pressure_angle: float = 20,
        shaft_angle: float = 90,
        root_fillet: float | None = None,
        addendum: float | None = None,
        dedendum: float | None = None,
        bore_diameter: float | None = None,
        back_cone_width: float | None = None,
        front_cone_width: float | None = None,
        rotation: RotationLike = (0, 0, 0),
        align: Align | tuple[Align, Align, Align] | None = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(
            module,
            tooth_count,
            tooth_count,
            face_width,
            pressure_angle=pressure_angle,
            shaft_angle=shaft_angle,
            root_fillet=root_fillet,
            addendum=addendum,
            dedendum=dedendum,
            bore_diameter=bore_diameter,
            back_cone_width=back_cone_width,
            front_cone_width=front_cone_width,
            rotation=rotation,
            align=align,
            mode=mode,
        )
        self.label = "Miters Gear"


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
    worm_gear = WormGear(
        module=2,
        starts=2,
        diametral_quotient=10,
        tooth_count=30,
        worm_length=30,
        wheel_thickness=12,
    )

    base_bevel_gear = BevelGear(2, 40, 30, face_width=16)
    pinion_bevel_gear = BevelGear(2, 30, 40, face_width=16)
    pinion_bevel_gear_loc = base_bevel_gear.mate_location(pinion_bevel_gear)
    pinion_bevel_gear.move(pinion_bevel_gear_loc)

    rack_plan = RackGearPlan(2, 10, 20, 20)
    rack = RackGear(2, 10, 20, 10, 20)
    spherical_gear_tooth = SphericalInvoluteToothProfile(2, 12, 40)
    miter_gear0 = MiterGear(2, 20, 8)
    miter_gear1 = MiterGear(2, 20, 8)
    miter_gear1_loc = miter_gear0.mate_location(miter_gear1)
    miter_gear1.move(miter_gear1_loc)

    show(
        pack(
            [
                gear_tooth,
                gear_profile,
                spur_gear,
                helical_gear,
                worm_gear,
                rack_plan,
                rack,
                spherical_gear_tooth,
                Compound(children=[miter_gear0, miter_gear1]),
                Compound(children=[base_bevel_gear, pinion_bevel_gear]),
            ],
            10,
        )
    )
