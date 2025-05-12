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
from functools import cached_property
from math import atan, degrees, floor, pi
from typing import Literal

from build123d.build_common import MM, Locations, PolarLocations, validate_inputs
from build123d.build_enums import Align, GeomType, Kind, LengthMode, Mode, Side
from build123d.build_line import BuildLine
from build123d.build_part import BuildPart
from build123d.build_sketch import BuildSketch
from build123d.geometry import Axis, Color, Location, Plane, Pos, Vector
from build123d.joints import RigidJoint
from build123d.objects_curve import JernArc, Line, PolarLine, Polyline, Spline
from build123d.objects_part import BasePartObject, Sphere
from build123d.objects_sketch import Circle, Rectangle, RectangleRounded
from build123d.operations_generic import add, fillet, offset, sweep
from build123d.operations_part import extrude, revolve, section
from build123d.operations_sketch import make_face
from build123d.topology import Compound, Edge, Face, Shell, Solid, Wire, Part

from bd_warehouse.fastener import (
    _make_fastener_hole,
    evaluate_parameter_dict,
    isolate_fastener_type,
    lookup_drill_diameters,
    read_fastener_parameters_from_csv,
    select_by_size_fn,
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

    @property
    def roller_count(self):
        return int(1.8 * pi * self.race_center_radius / self.roller_diameter)

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

        super().__init__(self.make_bearing())
        # Change position to match PressFitHole expectations
        self.position += (0, 0, self.bearing_dict["B"] / 2)
        bbox = self.bounding_box()
        RigidJoint("a", self, Pos(Z=bbox.min.Z))
        RigidJoint("b", self, Pos(Z=bbox.max.Z))
        self.label = f"{self.__class__.__name__}-{self.bearing_size}"

    def make_bearing(self) -> Compound:
        """Create bearing from the shapes defined in the derived class"""

        outer_race = revolve(self.outer_race_section(), Axis.Z)
        outer_race.color = Color(0xC0C0C0)
        outer_race.label = "OuterRace"
        inner_race = revolve(self.inner_race_section(), Axis.Z)
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
        d, d2, D = (self.bearing_dict[p] for p in ["d", "d2", "D"])
        D2 = D - (d2 - d)
        return (D2 - d2) / 2

    @property
    def contact_angle(self):
        a, D = (self.bearing_dict[p] for p in ["a", "D"])
        return degrees(atan(a / (D / 2)))

    @property
    def race_center_radius(self):
        return self.default_race_center_radius()

    def inner_race_section(self):
        d, d1, d2, r12, B, D = (
            self.bearing_dict[p] for p in ["d", "d1", "d2", "r12", "B", "D"]
        )
        roller_r = self.roller_diameter / 2
        with BuildSketch(Plane.XZ) as section:
            with Locations(((d1 + d) / 4, 0)):
                Rectangle((d1 - d) / 2, B)
            with Locations((d1 / 2, 0)):
                Rectangle(
                    (d1 - d2) / 2,
                    B / 2,
                    align=(Align.MAX, Align.MIN),
                    mode=Mode.SUBTRACT,
                )
            with Locations(((D + d) / 4, 0)):
                Circle(roller_r, mode=Mode.SUBTRACT)
            fillet(section.vertices().group_by(Axis.X)[0], r12)

        return section.sketch.face()

    def outer_race_section(self):
        d, D, D1, d2, r12, r34, B = (
            self.bearing_dict[p] for p in ["d", "D", "D1", "d2", "r12", "r34", "B"]
        )
        D2 = D - (d2 - d)

        roller_r = self.roller_diameter / 2
        with BuildSketch(Plane.XZ) as section:
            with Locations(((D1 + D) / 4, 0)):
                Rectangle((D1 - D) / 2, B)
            with Locations((D1 / 2, 0)):
                Rectangle(
                    (D1 - D2) / 2,
                    B / 2,
                    align=(Align.MIN, Align.MAX),
                    mode=Mode.SUBTRACT,
                )
            with Locations(((D + d) / 4, 0)):
                Circle(roller_r, mode=Mode.SUBTRACT)
            fillet(section.vertices().group_by(Axis.X)[-1].sort_by(Axis.Y)[-1], r12)
            fillet(section.vertices().group_by(Axis.X)[-1].sort_by(Axis.Y)[0], r34)

        return section.sketch.face()

    def cage(self):
        d, d1, D, D1, d2, r12, r34, B = (
            self.bearing_dict[p]
            for p in ["d", "d1", "D", "D1", "d2", "r12", "r34", "B"]
        )
        hole = Sphere(0.525 * self.roller_diameter)
        cage_t = 0.2 * (D1 - d2)

        cage_line = Plane.XZ * Spline(
            (d2 / 2 + cage_t, 0.4 * B),
            (d1 / 2 + cage_t, -0.4 * B),
            tangents=((0, -1), (0, -1)),
        )
        cage_face = Face.revolve(cage_line, 360, Axis.Z)
        cage_face -= PolarLocations((D - d) / 2, self.roller_count) * hole
        cage = Solid.thicken(cage_face, -cage_t)
        cage.color = Color(0x909090)

        return cage

    # def cap(self) -> Solid:
    #     (d, D, d2, B) = (self.bearing_dict[p] for p in ["d", "D", "d2", "B"])
    #     D2 = D - (d2 - d)

    #     with BuildPart() as cap:
    #         with BuildSketch(Plane.XY.offset(B * 0.42)):
    #             Circle(D2 / 2)
    #             Circle(d2 / 2, mode=Mode.SUBTRACT)
    #         extrude(amount=B * 0.05)
    #     cap_solid = cap.solid()
    #     cap_solid.color = Color(0x030303)
    #     return cap_solid

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
        return max(self._roller_diameters) * 1.25

    @property
    def contact_angle(self) -> float:
        """Angle of the outer raceway"""
        e = self.bearing_dict["e"]
        return degrees(atan(e))

    @property
    def race_center_radius(self) -> float:
        """Radius of cone to place the rollers"""
        if not hasattr(self, "_race_center_radius"):
            self.roller()
        return self._race_center_radius

    @property
    def roller_count(self):
        return floor(self._race_center_radius * 2 * pi / self.roller_diameter)

    def outer_race_section(self) -> Face:
        """Outer Cup"""
        if not hasattr(self, "_outer_race_section_cache"):
            self._outer_race_section_cache = self._outer_race_section()
        return self._outer_race_section_cache

    def _outer_race_section(self) -> Face:
        """Non cached version of outer race"""
        B, C, D, T, r34 = (self.bearing_dict[p] for p in ["B", "C", "D", "T", "r34"])
        with BuildSketch(
            Plane((0, 0, -B / 2), x_dir=(1, 0, 0), z_dir=(0, -1, 0))
        ) as section:
            with BuildLine() as bl:
                l1 = Polyline(
                    (D / 2, 0),
                    (D / 2, C),
                    (D / 2 - r34 * 1.5, C),
                )
                l2 = PolarLine(
                    l1 @ 1,
                    C,
                    direction=Vector(0, -1).rotate(Axis.Z, -self.contact_angle),
                    length_mode=LengthMode.VERTICAL,
                )
                Line(l2 @ 1, l1 @ 0)
            make_face()
            fillet(section.vertices().group_by(Axis.X)[-1], r34)
        return section.sketch.face()

    def inner_race_section(self) -> Face:
        """Central Cone"""
        if not hasattr(self, "_inner_race_section_cache"):
            self._inner_race_section_cache = self._inner_race_section()
        return self._inner_race_section_cache

    def _inner_race_section(self) -> Face:
        """Non cached version of inner race"""

        d, da, B, T, r12 = (self.bearing_dict[p] for p in ["d", "da", "B", "T", "r12"])
        inner_raceway_angle = self.contact_angle / 1.5
        with BuildSketch(
            Plane((0, 0, T - B / 2), x_dir=(1, 0, 0), z_dir=(0, -1, 0))
        ) as section:
            with BuildLine() as bl:
                l1 = Polyline((da / 2 - r12, -B), (d / 2, -B), (d / 2, 0))
                l2 = PolarLine(
                    l1 @ 0, B, 90 - inner_raceway_angle, length_mode=LengthMode.VERTICAL
                )
                l3 = Line(l1 @ 1, l2 @ 1)
            make_face()
            fillet(section.vertices().group_by(Axis.X)[0], r12)
            # Make a slot around the inner race to capture the rollers
            outside_edge = section.edges().sort_by(Edge.length)[-1]
            self.taper_length = outside_edge.length
            add(
                sweep(
                    outside_edge.trim(0.075, 0.925),
                    Edge.make_line(
                        outside_edge.position_at(0.5),
                        outside_edge.position_at(0.5)
                        + outside_edge.tangent_at(0.5).rotate(Axis.Z, 90) * r12 / 2,
                    ),
                ),
                mode=Mode.SUBTRACT,
            )
        return section.sketch.face()

    def roller(self) -> Face:
        """Tapered Roller"""
        if not hasattr(self, "_roller_cache"):
            self._roller_cache = self._roller()
        return self._roller_cache

    def _roller(self) -> Solid:
        """Non cached version of tapered roller"""
        GAP = 0.05
        inner_section = self.inner_race_section()
        outer_section = self.outer_race_section()
        inner_edge = (
            inner_section.edges()
            .filter_by(Axis.Z, reverse=True)
            .sort_by(Edge.length)[-1]
        )
        outer_edge = outer_section.edges().sort_by(Axis.X)[0]
        roller_inner_edge = inner_edge.trim(GAP, 1 - GAP)
        c_inner_a = Axis(inner_edge)
        c_outer_a = Axis(outer_edge)
        r_axis = Axis(
            c_inner_a.intersect(c_outer_a),
            (c_inner_a.direction + c_outer_a.direction * -1) / 2,
        )
        roller_non_planar_face = Face.revolve(roller_inner_edge, 360, r_axis)
        roller_circles = roller_non_planar_face.edges().filter_by(GeomType.CIRCLE)
        roller_ends = [Face(Wire(e)) for e in roller_circles]
        roller = Solid(Shell(roller_ends + [roller_non_planar_face]))
        self._roller_diameters = [2 * e.radius for e in roller_circles]
        self.cage_edge = section(roller, Plane.XZ).intersect(
            Axis(
                r_axis.position + Vector(0.3 * min(self._roller_diameters), 0, 0),
                r_axis.direction,
            )
        )
        self._race_center_radius = roller.faces().sort_by(Axis.Z)[-1].center().X
        roller.position -= (self._race_center_radius, 0, 0)
        roller.color = Color(0x909090)
        return roller

    countersink_profile = Bearing.default_countersink_profile

    def cage(self) -> Compound:
        """Cage holding the rollers together with the cone"""
        # To make the cage first create the appropriate conical surface
        # then punch holes for the rollers which can then be thickened to
        # a solid object.  This is more efficient then making holes in
        # a solid cage.
        roller = self.roller()
        roller_hole_cutter = offset(roller, 0.25 * MM, kind=Kind.INTERSECTION).move(
            Pos(X=self.race_center_radius)
        )
        roller_max_r = (
            roller.faces().filter_by(GeomType.PLANE).sort_by(Face.area)[0].edge().radius
        )
        cage_side: Edge = Pos(X=roller_max_r / 4) * Edge.make_line(
            self.cage_edge @ -0.1, self.cage_edge @ 1.1
        )
        bottom = (
            1
            if self.cage_edge.position_at(0).Y < self.cage_edge.position_at(1).Y
            else 0
        )
        hook_sign = -1 if bottom == 0 else 1
        hook = JernArc(cage_side @ bottom, (cage_side % bottom) * hook_sign, 3 * MM, 80)
        cage_profile = Wire([cage_side, hook])
        cage_surface = Shell.revolve(cage_profile, 360, Axis.Z)
        cage_surface -= PolarLocations(0, self.roller_count) * roller_hole_cutter
        cage = Solid.thicken(cage_surface, 0.5 * MM)
        cage.color = Color(0x909090)

        return cage


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
    from ocp_vscode import Camera, set_defaults, show, show_all

    set_defaults(reset_camera=Camera.CENTER)

    # b1 = SingleRowCappedDeepGrooveBallBearing(size="M8-22-7")
    # b2 = SingleRowDeepGrooveBallBearing(size="M8-22-7")
    # print(SingleRowAngularContactBallBearing.sizes("SKT"))
    b3 = SingleRowAngularContactBallBearing(size="M10-30-9")
    # print(SingleRowCylindricalRollerBearing.sizes("SKT"))
    # b4 = SingleRowCylindricalRollerBearing("M15-35-11")
    # print(SingleRowTaperedRollerBearing.sizes("SKT"))
    # b5 = SingleRowTaperedRollerBearing("M25-52-19.25")
    bbox = b3.bounding_box()
    print(b3.bearing_dict["B"], b3.bearing_dict["D"], bbox.size)
    show(b3)
    # show(pack([b1, b2, b3, b4], 5))
