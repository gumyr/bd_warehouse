"""

Parametric Bearings

name: bearing.py
by:   Gumyr
date: March 20th 2022

desc: This python/cadquery code is a parameterized bearing generator.

TODO:

license:

    Copyright 2022 Gumyr

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

import copy
from abc import ABC, abstractmethod
from math import pi, radians, degrees, asin, sin
from typing import Literal
from build123d.build_common import Locations, PolarLocations, MM, validate_inputs
from build123d.build_enums import Align, Mode, SortBy
from build123d.build_line import BuildLine
from build123d.build_part import BuildPart
from build123d.build_sketch import BuildSketch
from build123d.geometry import (
    Axis,
    Color,
    Location,
    Plane,
    Pos,
    Rot,
    Vector,
)
from build123d.joints import RigidJoint
from build123d.objects_curve import (
    JernArc,
    Line,
    PolarLine,
    Polyline,
    RadiusArc,
    Spline,
)
from build123d.objects_part import BasePartObject, Cylinder
from build123d.objects_sketch import (
    Circle,
    Polygon,
    Rectangle,
    RectangleRounded,
    RegularPolygon,
    Trapezoid,
)
from build123d.operations_generic import add, chamfer, fillet, split
from build123d.operations_part import extrude, revolve
from build123d.operations_sketch import make_face
from build123d.pack import pack
from build123d.topology import (
    Compound,
    Curve,
    Edge,
    Face,
    Part,
    Shell,
    Sketch,
    Solid,
    Wire,
)

from bd_warehouse.fastener import (
    evaluate_parameter_dict,
    read_fastener_parameters_from_csv,
    isolate_fastener_type,
    lookup_drill_diameters,
    select_by_size_fn,
    _make_fastener_hole,
)


class Bearing(ABC, BasePartObject):
    """Parametric Bearing

    Base Class used to create standard bearings

    Args:
        size (str): bearing size, e.g. "M8-22-7"
        bearing_type (str): type identifier - e.g. "SKT"

    Raises:
        ValueError: bearing_type is invalid
        ValueError: size is invalid

    """

    def method_exists(self, method: str) -> bool:
        """Did the derived class create this method"""
        return hasattr(self.__class__, method) and callable(
            getattr(self.__class__, method)
        )

    # Read clearance and tap hole dimensions tables
    # Close, Medium, Loose
    clearance_hole_drill_sizes = read_fastener_parameters_from_csv(
        "clearance_hole_sizes.csv"
    )
    clearance_hole_data = lookup_drill_diameters(clearance_hole_drill_sizes)

    @property
    def clearance_hole_diameters(self):
        """A dictionary of drill diameters for clearance holes"""
        try:
            return self.clearance_hole_data[self.bearing_size.split("-")[0]]
        except KeyError as e:
            raise ValueError(
                f"No clearance hole data for size {self.bore_diameter}"
            ) from e

    @property
    def bore_diameter(self) -> float:
        """Diameter of central hole"""
        return self.bearing_dict["d"]

    @property
    def outer_diameter(self) -> float:
        """Bearing outer diameter"""
        return self.bearing_dict["D"]

    @property
    def thickness(self) -> float:
        """Bearing thickness"""
        return (
            self.bearing_dict["T"]
            if self.bearing_class == "SingleRowTaperedRollerBearing"
            else self.bearing_dict["B"]
        )

    @classmethod
    def select_by_size(cls, size: str) -> dict:
        """Return a dictionary of list of fastener types of this size"""
        return select_by_size_fn(cls, size)

    @property
    @abstractmethod
    def bearing_data(cls):
        """Each derived class must provide a bearing_data dictionary"""
        return NotImplementedError  # pragma: no cover

    @abstractmethod
    def inner_race_section(self) -> Solid:
        """Each derived class must provide the section of the inner race"""
        return NotImplementedError  # pragma: no cover

    @abstractmethod
    def outer_race_section(self) -> Solid:
        """Each derived class must provide the section of the outer race"""
        return NotImplementedError  # pragma: no cover

    @abstractmethod
    def roller(self) -> Solid:
        """Each derived class must provide the roller object - a sphere, cylinder or cone"""
        return NotImplementedError  # pragma: no cover

    @abstractmethod
    def countersink_profile(self) -> Face:
        """Each derived class must provide the profile of a countersink cutter"""
        return NotImplementedError  # pragma: no cover

    @property
    @abstractmethod
    def roller_diameter(self):
        """Each derived class must provide the roller diameter"""
        return NotImplementedError  # pragma: no cover

    @property
    @abstractmethod
    def race_center_radius(self):
        return NotImplementedError  # pragma: no cover

    def default_race_center_radius(self):
        """Default roller race center radius"""
        (d1, D1) = (self.bearing_dict[p] for p in ["d1", "D1"])
        return (D1 + d1) / 4

    def default_roller_diameter(self):
        """Default roller diameter"""
        (d1, D1) = (self.bearing_dict[p] for p in ["d1", "D1"])
        return 0.625 * (D1 - d1)

    @property
    def info(self):
        """Return identifying information"""
        return f"{self.bearing_class}({self.bearing_type}): {self.bearing_size}"

    @property
    def bearing_class(self):
        """Which derived class created this bearing"""
        return type(self).__name__

    def length_offset(self):
        """Screw only parameter"""
        return 0

    @classmethod
    def types(cls) -> list[str]:
        """Return a set of the bearing types"""
        return set(p.split(":")[0] for p in list(cls.bearing_data.values())[0].keys())

    @classmethod
    def sizes(cls, bearing_type: str) -> list[str]:
        """Return a list of the bearing sizes for the given type"""
        return list(isolate_fastener_type(bearing_type, cls.bearing_data).keys())

    def __init__(
        self,
        size: str,
        bearing_type: str = "SKT",
    ):
        """Parse Bearing input parameters"""
        self.bearing_size = size.strip()
        if bearing_type not in self.types():
            raise ValueError(f"{bearing_type} invalid, must be one of {self.types()}")
        self.bearing_type = bearing_type
        self.capped = self.method_exists("cap")
        self.is_metric = self.bearing_size[0] == "M"
        self.hole_locations: list[Location] = []  #: custom holes locations

        try:
            self.bearing_dict = evaluate_parameter_dict(
                isolate_fastener_type(self.bearing_type, self.bearing_data)[
                    self.bearing_size
                ],
                is_metric=self.is_metric,
            )
        except KeyError as e:
            raise ValueError(
                f"{size} invalid, must be one of {self.sizes(self.bearing_type)}"
            ) from e

        self.roller_count = int(
            1.8 * pi * self.race_center_radius / self.roller_diameter
        )
        super().__init__(self.make_bearing())
        bbox = self.bounding_box()
        RigidJoint("a", self, Pos(Z=bbox.min.Z))
        RigidJoint("b", self, Pos(Z=bbox.max.Z))
        self.label = f"{self.__class__.__name__}-{self.bearing_size}"

    def make_bearing(self) -> Compound:
        """Create bearing from the shapes defined in the derived class"""

        outer_race = revolve(self.default_outer_race_section(), Axis.Z)
        outer_race.color = Color(0xC0C0C0)
        outer_race.label = "OuterRace"
        inner_race = revolve(self.default_inner_race_section(), Axis.Z)
        inner_race.color = Color(0xC0C0C0)
        inner_race.label = "InnerRace"

        bearing_pieces = [outer_race, inner_race]
        if self.capped:
            cap = self.cap()
            cap.label = "Cap"
            bearing_pieces.extend(
                [
                    cap,
                    copy.copy(cap).mirror(Plane.XY),
                ]
            )
        else:
            roller = self.roller()
            roller.label = "Roller"
            locs = PolarLocations(self.race_center_radius, self.roller_count).locations
            bearing_pieces.extend(
                [locs[0] * roller] + [l * copy.copy(roller) for l in locs[1:]]
            )

            if self.method_exists("cage"):
                cage = self.cage()
                cage.label = "Cage"
                bearing_pieces.append(cage)

        bearing = Compound(children=bearing_pieces)
        bearing.color = Color(0xC0C0C0)
        return bearing

    def default_inner_race_section(self) -> Face:
        """Create 2D profile inner race"""
        (d1, d, B, r12) = (self.bearing_dict[p] for p in ["d1", "d", "B", "r12"])

        with BuildSketch(Plane.XZ) as section:
            with Locations(((d1 + d) / 4, 0)):
                RectangleRounded((d1 - d) / 2, B, r12)
        return section.sketch.face()

    def default_outer_race_section(self) -> Face:
        """Create 2D profile inner race"""
        (D1, D, B, r12) = (self.bearing_dict[p] for p in ["D1", "D", "B", "r12"])

        with BuildSketch(Plane.XZ) as section:
            with Locations(((D1 + D) / 4, 0)):
                RectangleRounded((D - D1) / 2, B, r12)

        return section.sketch.face()

    def default_countersink_profile(self, interference: float = 0) -> Face:
        (D, B) = (self.bearing_dict[p] for p in ["D", "B"])
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(D / 2 - interference, B, align=Align.MIN)
        return profile.sketch.face()

    def default_roller(self) -> Solid:
        roller = Solid.make_sphere(self.roller_diameter / 2)
        roller.color = Color(0x909090)
        return roller

    def default_cap(self) -> Solid:
        (D1, d1, B) = (self.bearing_dict[p] for p in ["D1", "d1", "B"])
        with BuildPart() as cap:
            with BuildSketch(Plane.XY.offset(B * 0.42)):
                Circle(D1 / 2)
                Circle(d1 / 2, mode=Mode.SUBTRACT)
            extrude(amount=B * 0.05)
        cap_solid = cap.solid()
        cap_solid.color = Color(0x030303)
        return cap_solid


class SingleRowDeepGrooveBallBearing(Bearing):
    """Single Row Deep Groove Ball Bearing

    Deep groove ball bearings are particularly
    versatile. They are simple in design, non-
    separable, suitable for high and very high
    speeds and are robust in operation, requiring
    little maintenance. Because deep groove ball
    bearings are the most widely used bearing
    type, they are available in many
    designs, variants and sizes."""

    bearing_data = read_fastener_parameters_from_csv(
        "single_row_deep_groove_ball_bearing_parameters.csv"
    )

    @property
    def roller_diameter(self):
        return self.default_roller_diameter()

    @property
    def race_center_radius(self):
        return self.default_race_center_radius()

    outer_race_section = Bearing.default_outer_race_section
    inner_race_section = Bearing.default_inner_race_section
    roller = Bearing.default_roller
    countersink_profile = Bearing.default_countersink_profile


class SingleRowCappedDeepGrooveBallBearing(Bearing):
    """Single Row Capped Deep Groove Ball Bearings

    Deep groove ball bearings capped with a seal or
    shield on both sides."""

    bearing_data = read_fastener_parameters_from_csv(
        "single_row_capped_deep_groove_ball_bearing_parameters.csv"
    )

    @property
    def roller_diameter(self):
        return self.default_roller_diameter()

    @property
    def race_center_radius(self):
        return self.default_race_center_radius()

    outer_race_section = Bearing.default_outer_race_section
    inner_race_section = Bearing.default_inner_race_section
    roller = Bearing.default_roller
    cap = Bearing.default_cap
    countersink_profile = Bearing.default_countersink_profile


class SingleRowAngularContactBallBearing(Bearing):
    """Single Row Angular Contact Ball Bearing

    Angular contact ball bearings have raceways
    in the inner and outer rings that are displaced
    relative to each other in the direction of the
    bearing axis. This means that they are
    designed to accommodate combined loads, i.e.
    simultaneously acting radial and axial loads.
    The axial load carrying capacity of angular
    contact ball bearings increases with increasing
    contact angle. The contact angle is defined
    as the angle between the line joining the points
    of contact of the ball and the raceways in the
    radial plane, along which the load is transmit-
    ted from one raceway to another, and a line
    perpendicular to the bearing axis."""

    bearing_data = read_fastener_parameters_from_csv(
        "single_row_angular_contact_ball_bearing_parameters.csv"
    )

    @property
    def roller_diameter(self):
        """Default roller diameter"""
        (d, d2, D) = (self.bearing_dict[p] for p in ["d", "d2", "D"])
        D2 = D - (d2 - d)
        return 0.4 * (D2 - d2)

    @property
    def race_center_radius(self):
        return self.default_race_center_radius()

    def inner_race_section(self):
        (d, d1, d2, r12, B) = (
            self.bearing_dict[p] for p in ["d", "d1", "d2", "r12", "B"]
        )

        inner_race = (
            Workplane("XZ")
            .moveTo(d2 / 2 - r12, 0)
            .radiusArc((d2 / 2, r12), -r12)
            .spline([(d1 / 2, B - r12)], tangents=[(0, 1), (0, 1)], includeCurrent=True)
            .radiusArc((d1 / 2 - r12, B), -r12)
            .hLineTo(d / 2 + r12)
            .radiusArc((d / 2, B - r12), -r12)
            .vLineTo(r12)
            .radiusArc((d / 2 + r12, 0), -r12)
            .close()
        )
        return inner_race

    def outer_race_section(self):
        (d, D, D1, d2, r12, r34, B) = (
            self.bearing_dict[p] for p in ["d", "D", "D1", "d2", "r12", "r34", "B"]
        )
        D2 = D - (d2 - d)
        outer_race = (
            Workplane("XZ")
            .moveTo(D / 2 - r12, 0)
            .radiusArc((D / 2, r12), -r12)
            .vLineTo(B - r34)
            .radiusArc((D / 2 - r34, B), -r34)
            .hLineTo(D2 / 2 + r12)
            .radiusArc((D2 / 2, B - r12), -r12)
            .spline([(D1 / 2, r12)], tangents=[(0, -1), (0, -1)], includeCurrent=True)
            .radiusArc((D1 / 2 + r12, 0), -r12)
            .close()
        )
        return outer_race

    def cap(self) -> Solid:
        (d, D, d2, B) = (self.bearing_dict[p] for p in ["d", "D", "d2", "B"])
        D2 = D - (d2 - d)

        with BuildPart() as cap:
            with BuildSketch(Plane.XY.offset(B * 0.42)):
                Circle(D2 / 2)
                Circle(d2 / 2, mode=Mode.SUBTRACT)
            extrude(amount=B * 0.05)
        cap_solid = cap.solid()
        cap_solid.color = Color(0x030303)
        return cap_solid

    roller = Bearing.default_roller

    countersink_profile = Bearing.default_countersink_profile


class SingleRowCylindricalRollerBearing(Bearing):
    """Single Row Cylindrical Roller Bearings

    Suitable for very heavy radial loads at moderate speeds,
    roller bearings use cylindrical rollers instead of
    spherical ball bearings."""

    bearing_data = read_fastener_parameters_from_csv(
        "single_row_cylindrical_roller_bearing_parameters.csv"
    )

    @property
    def roller_diameter(self):
        return self.default_roller_diameter()

    @property
    def race_center_radius(self):
        return self.default_race_center_radius()

    outer_race_section = Bearing.default_outer_race_section
    inner_race_section = Bearing.default_inner_race_section

    def roller(self) -> Solid:
        roller_length = 0.7 * self.bearing_dict["B"]
        roller = Solid.make_cylinder(
            self.roller_diameter / 2,
            roller_length,
            Plane.XY.offset(-roller_length / 2),
        )
        roller.color = Color(0x909090)
        return roller

    countersink_profile = Bearing.default_countersink_profile


class SingleRowTaperedRollerBearing(Bearing):
    """Tapered Roller Bearing

    Tapered roller bearings have tapered inner
    and outer ring raceways and tapered rollers.
    They are designed to accommodate combined
    loads, i.e. simultaneously acting radial and
    axial loads. The projection lines of the race-
    ways meet at a common point on the bearing
    axis to provide true rolling and low
    friction. The axial load carrying capacity of
    tapered roller bearings increases with
    increasing contact angle.  A single row tapered
    roller bearing is typically adjusted against a
    second tapered roller bearing.

    Single row tapered roller bearings are sep-
    ar able, i.e. the inner ring with roller
    and cage assembly (cone) can be mounted
    separately from the outer ring (cup)."""

    bearing_data = read_fastener_parameters_from_csv(
        "single_row_tapered_roller_bearing_parameters.csv"
    )

    @property
    def roller_diameter(self) -> float:
        """Diameter of the larger end of the roller - increased diameter
        allows for room for the cage between the rollers"""
        return self.roller().edges().sort_by(Axis.Z)[-1].radius * 2.5

    @property
    def cone_angle(self) -> float:
        """Angle of the inner cone raceway"""
        (a, d1, Db) = (self.bearing_dict[p] for p in ["a", "d1", "Dbmin"])
        cone_length = (Db / 2) / asin(radians(a))
        return degrees(asin((d1 / 2) / cone_length))

    @property
    def roller_axis_angle(self) -> float:
        """Angle of the central axis of the rollers"""
        return (self.bearing_dict["a"] + self.cone_angle) / 2

    @property
    def roller_length(self) -> float:
        """Roller length"""
        return 0.7 * self.bearing_dict["B"]

    @property
    def cone_length(self) -> float:
        """Distance to intersection of projection lines"""
        (a, Db) = (self.bearing_dict[p] for p in ["a", "Dbmin"])
        return (Db / 2) / asin(radians(a))

    @property
    def race_center_radius(self) -> float:
        """Radius of cone to place the rollers"""
        return (self.cone_length - self.roller_length / 2) * sin(
            radians(self.roller_axis_angle)
        )

    def outer_race_section(self) -> Face:
        """Outer Cup"""
        (D, C, Db, a, r34) = (
            self.bearing_dict[p] for p in ["D", "C", "Dbmin", "a", "r34"]
        )
        with BuildSketch() as cup_sketch:
            # with Locations((C / 2, D / 2 - (D - Db) / 4)):
            with Locations((C / 2, 0)):
                Trapezoid((D - Db) / 2, C, a + 90, 90)
                fillet(cup_sketch.vertices(), r34)

        # cup_sketch = (
        #     Sketch()
        #     .push([(C / 2, D / 2 - (D - Db) / 4)])
        #     .trapezoid((D - Db) / 2, C, a + 90, 90, 90)
        #     .reset()
        #     .vertices()
        #     .fillet(r34)
        # )
        # cup = Workplane(
        #     cup_sketch._faces.Faces()[0].rotate(Vector(), Vector(0, 1, 0), -90)
        # ).wires()

        return cup_sketch.sketch

    def inner_race_section(self) -> Face:
        """Central Cone"""
        (d, B, da, r12, T) = (
            self.bearing_dict[p] for p in ["d", "B", "da", "r12", "T"]
        )
        cone_sketch = (
            Sketch()
            .push([(T - B / 2, d / 2 + (da - d) / 2)])
            .trapezoid((da - d) / 2, B, 90 + self.cone_angle, 90, -90)
            .reset()
            .vertices()
            .fillet(r12)
        )
        cone = Workplane(
            cone_sketch._faces.Faces()[0].rotate(Vector(), Vector(0, 1, 0), -90)
        ).wires()
        return cone

    def roller(self) -> Solid:
        """Tapered Roller"""
        roller_cone_angle = self.bearing_dict["a"] - self.cone_angle
        cone_radii = [
            1.2 * (self.cone_length - l) * sin(radians(roller_cone_angle) / 2)
            for l in [0, self.roller_length]
        ]
        return Rot(X=-self.roller_axis_angle) * Solid.make_cone(
            cone_radii[1],
            cone_radii[0],
            self.roller_length,
            Plane.XY.offset(-self.roller_length / 2),
        )

    countersink_profile = Bearing.default_countersink_profile

    def cage(self) -> Compound:
        """Cage holding the rollers together with the cone"""
        thickness = 0.9 * self.bearing_dict["T"]
        cage_radii = [
            (self.cone_length - l) * sin(radians(self.roller_axis_angle)) + 0.5 * MM
            for l in [0, thickness]
        ]
        cage_face = Solid.make_cone(
            cage_radii[1],
            cage_radii[0],
            thickness,
        ).cut(
            Solid.make_cone(
                cage_radii[1] - 1 * MM,
                cage_radii[0] - 1 * MM,
                thickness,
            )
        )
        return cage_face


class PressFitHole(BasePartObject):
    """Press Fit Hole

    A press fit hole for a bearing is a precisely machined cavity designed to hold
    a bearing securely through interference fit, where the hole's diameter is slightly
    smaller than the bearing's outer diameter. This fit relies on frictional force to
    keep the bearing in place without additional fasteners. Key factors include material
    compatibility, tight tolerance control, and smooth surface finish to ensure a
    reliable and stable fit. Press fit holes are widely used in high-precision
    applications like automotive, aerospace, and industrial machinery, offering a
    robust and maintenance-free solution for securing bearings.

    Args:
        bearing: A bearing instance
        interference: The amount the decrease the hole radius from the bearing outer
            radius. Defaults to 0.
        fit: one of "Close", "Normal", "Loose" which determines hole diameter for the
            bore. Defaults to "Normal".
        depth: hole depth. Defaults to through part.
        mode (Mode, optional): combination mode. Defaults to Mode.SUBTRACT.

    Raises:
        ValueError: PressFitHole only accepts bearings of type Bearing
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        bearing: Bearing,
        interference: float = 0,
        fit: Literal["Close", "Normal", "Loose"] = "Normal",
        depth: float = None,
        mode: Mode = Mode.SUBTRACT,
    ):
        context: BuildPart = BuildPart._get_context(self)
        validate_inputs(context, self)

        if not isinstance(bearing, Bearing):
            raise ValueError("pressFitHole only accepts bearings")

        if depth is not None:
            self.hole_depth = depth
        elif depth is None and context is not None:
            self.hole_depth = 2 * context.max_dimension
        else:
            raise ValueError("No depth provided")

        hole_part = _make_fastener_hole(
            hole_diameters=bearing.clearance_hole_diameters,
            fastener=bearing,
            depth=self.hole_depth,
            countersink_profile=bearing.countersink_profile(interference),
            fit=fit,
            counter_sunk=True,
            update_hole_locations=context is not None,
        )

        super().__init__(
            part=hole_part,
            align=None,
            rotation=(0, 0, 0),
            mode=mode,
        )


if __name__ == "__main__":
    from ocp_vscode import show, set_defaults, Camera

    set_defaults(reset_camera=Camera.CENTER)

    b1 = SingleRowCappedDeepGrooveBallBearing(size="M8-22-7")
    b2 = SingleRowDeepGrooveBallBearing(size="M8-22-7")
    # print(SingleRowAngularContactBallBearing.sizes("SKT"))
    b3 = SingleRowAngularContactBallBearing(size="M10-30-9")
    # print(SingleRowCylindricalRollerBearing.sizes("SKT"))
    b4 = SingleRowCylindricalRollerBearing("M15-35-11")
    # print(SingleRowTaperedRollerBearing.sizes("SKT"))
    # b5 = SingleRowTaperedRollerBearing("M15-42-14.25")
    # show(b5)
    show(pack([b1, b2, b3, b4], 5))
