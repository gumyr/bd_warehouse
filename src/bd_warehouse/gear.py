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
    atan,
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
    GridLocations,
    Helix,
    Line,
    Location,
    Mode,
    Plane,
    PolarLocations,
    Pos,
    RadiusArc,
    Rectangle,
    RigidJoint,
    Rot,
    RotationLike,
    Solid,
    Spline,
    Trapezoid,
    Vector,
    Wire,
    extrude,
    faces,
    fillet,
    mirror,
    pack,
)
from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeSolid,
    BRepBuilderAPI_MakeWire,
    BRepBuilderAPI_Sewing,
)
from OCP.BRepFill import BRepFill
from OCP.BRepLib import BRepLib
from OCP.BRepTools import BRepTools
from OCP.Geom import Geom_CylindricalSurface, Geom_Surface
from OCP.Geom2d import Geom2d_Line, Geom2d_TrimmedCurve
from OCP.gp import gp_Ax3, gp_Dir, gp_Dir2d, gp_Pnt, gp_Pnt2d
from OCP.StdFail import StdFail_NotDone
from OCP.TopoDS import TopoDS


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
                except StdFail_NotDone as err:
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
            except (StdFail_NotDone, ValueError) as err:
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


def _uv_face(
    surface: Geom_Surface, corners: list[tuple[float, float]]
) -> tuple[Face, list[Edge]]:
    """Face on ``surface`` bounded by straight segments between ``corners`` in its
    (u, v) parameter space.

    Every worm face has such a domain: helices are straight lines in a cylinder's
    (angle, z) space, and on a ruled helicoid z is linear in both parameters so
    z = const trims are straight lines too. Building faces from pcurves avoids
    surface/surface intersections entirely.

    Returns:
        the face and its edges in ``corners`` order (edge i runs corner i → i+1)
    """
    wire_builder = BRepBuilderAPI_MakeWire()
    edges = []
    for (u0, v0), (u1, v1) in zip(corners, corners[1:] + corners[:1]):
        # a line's parameter is distance along it; OCP 8 dropped GCE2d_MakeSegment
        line = Geom2d_Line(gp_Pnt2d(u0, v0), gp_Dir2d(u1 - u0, v1 - v0))
        segment = Geom2d_TrimmedCurve(line, 0.0, hypot(u1 - u0, v1 - v0))
        edge = BRepBuilderAPI_MakeEdge(segment, surface).Edge()
        BRepLib.BuildCurves3d_s(edge)
        wire_builder.Add(edge)
        edges.append(Edge(edge))
    face = BRepBuilderAPI_MakeFace(surface, wire_builder.Wire()).Face()
    return Face(face), edges


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
    ) -> list[tuple[Geom_Surface, Callable[[float, float], float]]]:
        """Ruled helicoid surfaces of one flank of the tooth centred on ``tooth_angle``.

        Returns:
            (surface, u_at) pairs from root to tip where ``u_at(z, v)`` gives the
            surface u parameter at height ``z`` on the v = const isoline.
        """
        z_start, height = self.helix_span(length)
        total_angle = 2 * pi * height / self.lead
        surfaces: list[tuple[Geom_Surface, Callable[[float, float], float]]] = []
        for radii in self.flank_radii():
            helices, offsets = [], []
            for radius in radii:
                phase, offset = self.flank_helix(radius, side)
                helix = Helix(
                    self.lead, height, radius, center=(0, 0, z_start + offset)
                )
                helices.append(helix.rotate(Axis.Z, degrees(tooth_angle + phase)))
                offsets.append(offset)
            ruled = BRepFill.Face_s(helices[0].wrapped, helices[1].wrapped)
            surface = BRep_Tool.Surface_s(ruled)
            _, u_max, _, _ = BRepTools.UVBounds_s(ruled)
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
        face, _ = _uv_face(
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
        faces: list[Face] = []
        cap_edges: tuple[list[Edge], list[Edge]] = ([], [])

        def add_bands(surface, corners_at):
            for i, (z_lo, z_hi) in enumerate(zip(z_lines, z_lines[1:])):
                face, edges = _uv_face(surface, corners_at(z_lo, z_hi))
                faces.append(face)
                if i == 0:
                    cap_edges[0].append(edges[0])
                if i == band_count - 1:
                    cap_edges[1].append(edges[2])

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
                cylinder = Geom_CylindricalSurface(
                    gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), radius
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
        faces += [Face(Wire(edges)) for edges in cap_edges]

        # The band edges of adjacent faces are separately approximated copies of
        # the same helix, so sew with a tolerance above the approximation error.
        sewing = BRepBuilderAPI_Sewing(1e-5)
        for face in faces:
            sewing.Add(face.wrapped)
        sewing.Perform()
        if sewing.NbFreeEdges() != 0:
            raise RuntimeError("worm surfaces did not sew into a closed shell")
        solid = BRepBuilderAPI_MakeSolid(TopoDS.Shell(sewing.SewedShape())).Solid()
        BRepLib.OrientClosedSolid_s(solid)
        worm = Solid(solid)
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
    show(pack([gear_tooth, gear_profile, spur_gear, helical_gear, worm_gear], 5))
