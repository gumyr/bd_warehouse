"""

Parametric Threaded Fasteners

name: fastener.py
by:   Gumyr
date: August 14th 2021
      March 24th 2024 - ported to bd_warehouse

desc: This python/build123d code is a parameterized threaded fastener generator.

todo: - add helix line to thread object if simple enabled
      - support unthreaded sections on screw shanks
      - calculate depth for thru threaded holes
      - optimize recess creation when recess_taper = 0

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

from __future__ import annotations

import csv
import math
from abc import ABC, abstractmethod
from math import atan, cos, pi, radians, sin, sqrt, tan
from typing import Literal, Optional, Union

import bd_warehouse

from importlib import resources
from bd_warehouse.thread import IsoThread, imperial_str_to_float, is_safe
from build123d.build_common import (
    IN,
    MM,
    PolarLocations,
    LocationList,
    Locations,
    validate_inputs,
)
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
    RotationLike,
    Vector,
)
from build123d.joints import (
  CylindricalJoint,
  RigidJoint
)
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
    Polygon,
    Rectangle,
    RectangleRounded,
    RegularPolygon,
    SlotOverall,
    Trapezoid,
)
from build123d.operations_generic import add, chamfer, fillet, split
from build123d.operations_part import extrude, revolve, loft
from build123d.operations_sketch import make_face
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

# ISO standards use single variable dimension labels which are used extensively
# pylint: disable=invalid-name


def polygon_diagonal(width: float, num_sides: Optional[int] = 6) -> float:
    """Distance across polygon diagonals given width across flats"""
    return width / cos(pi / num_sides)


def read_fastener_parameters_from_csv(filename: str) -> dict:
    """Parse a csv parameter file into a dictionary of strings"""

    parameters = {}
    data_resource = resources.files(bd_warehouse) / f"data/{filename}"
    with data_resource.open() as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = reader.fieldnames
        for row in reader:
            key = row[fieldnames[0]]
            row.pop(fieldnames[0])
            parameters[key] = row

    return parameters


def decode_imperial_size(size: str) -> tuple[float, float]:
    """Extract the major diameter and pitch from an imperial size"""

    # Imperial # sizes to diameters
    imperial_numbered_sizes = {
        "#0000": 0.0210 * IN,
        "#000": 0.0340 * IN,
        "#00": 0.0470 * IN,
        "#0": 0.0600 * IN,
        "#1": 0.0730 * IN,
        "#2": 0.0860 * IN,
        "#3": 0.0990 * IN,
        "#4": 0.1120 * IN,
        "#5": 0.1250 * IN,
        "#6": 0.1380 * IN,
        "#8": 0.1640 * IN,
        "#10": 0.1900 * IN,
        "#12": 0.2160 * IN,
    }

    sizes = size.split("-")
    if size[0] == "#":
        major_diameter = imperial_numbered_sizes[sizes[0]]
    else:
        major_diameter = imperial_str_to_float(sizes[0])
    pitch = IN / (imperial_str_to_float(sizes[1]) / IN)
    return (major_diameter, pitch)


def metric_str_to_float(measure: str) -> float:
    """Convert a metric measurement to a float value"""

    if is_safe(measure):
        # pylint: disable=eval-used
        # Before eval() is called the string, extracted from the csv file, is verified as safe
        result = eval(measure)
    else:
        result = measure
    return result


def evaluate_parameter_dict_of_dict(
    parameters: dict,
    is_metric: Optional[bool] = True,
) -> dict:
    """Convert string values in a dict of dict structure to floats based on provided units"""

    measurements = {}
    for key, value in parameters.items():
        measurements[key] = evaluate_parameter_dict(
            parameters=value, is_metric=is_metric
        )

    return measurements


def evaluate_parameter_dict(
    parameters: dict,
    is_metric: Optional[bool] = True,
) -> dict:
    """Convert the strings in a parameter dictionary into dimensions"""
    measurements = {}
    for params, value in parameters.items():
        if is_metric:
            measurements[params] = metric_str_to_float(value)
        else:
            measurements[params] = imperial_str_to_float(value)
    return measurements


def isolate_fastener_type(target_fastener: str, fastener_data: dict) -> dict:
    """Split the fastener data 'type:value' strings into dictionary elements"""
    result = {}
    for size, parameters in fastener_data.items():
        dimension_dict = {}
        for type_dimension, value in parameters.items():
            (fastener_name, dimension) = tuple(type_dimension.strip().split(":"))
            if target_fastener == fastener_name and not value == "":
                dimension_dict[dimension] = value
        if len(dimension_dict) > 0:
            result[size] = dimension_dict
    return result


def read_drill_sizes() -> dict:
    """Read the drill size csv file and build a drill_size dictionary (Ah, the imperial system)"""
    drill_sizes = {}
    data_resource = resources.files(bd_warehouse) / "data/drill_sizes.csv"

    with data_resource.open() as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = reader.fieldnames
        for row in reader:
            drill_sizes[row[fieldnames[0]]] = float(row[fieldnames[1]]) * IN
    return drill_sizes


def lookup_drill_diameters(drill_hole_sizes: dict) -> dict:
    """Return a dict of dict of drill size to drill diameter"""

    drill_sizes = read_drill_sizes()

    #  Build a dictionary of hole diameters for these hole sizes
    drill_hole_diameters = {}
    for size, drill_data in drill_hole_sizes.items():
        hole_data = {}
        for fit, drill in drill_data.items():
            try:
                hole_data[fit] = drill_sizes[drill]
            except KeyError:
                if size[0] == "M":
                    hole_data[fit] = float(drill)
                else:
                    hole_data[fit] = imperial_str_to_float(drill)
        drill_hole_diameters[size] = hole_data
    return drill_hole_diameters


def lookup_nominal_screw_lengths() -> dict:
    """Return a dict of dict of drill size to drill diameter"""

    # Read the nominal screw length csv file and build a dictionary
    nominal_screw_lengths = {}
    data_resource = resources.files(bd_warehouse) / "data/nominal_screw_lengths.csv"
    with data_resource.open() as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            unit_factor = MM if row["Unit"] == "mm" else IN
            sizes = [
                unit_factor * float(size)
                for size in str(row["Nominal_Sizes"]).split(",")
            ]
            nominal_screw_lengths[row["Screw_Type"]] = sizes

    return nominal_screw_lengths


def cross_recess(size: str) -> tuple[Face, float]:
    """Type H Cross / Phillips recess for screws

    size must be one of: PH0, PH1, PH2, PH3, or PH4

    Note: the following dimensions are somewhat simplified to a single
    value per drive size instead of unique sizes for each fastener
    """
    widths = {"PH0": 1.9, "PH1": 3.1, "PH2": 5.3, "PH3": 6.8, "PH4": 10.0}
    depths = {"PH0": 1.1, "PH1": 2.0, "PH2": 3.27, "PH3": 3.53, "PH4": 5.88}
    try:
        m = widths[size]
    except KeyError as e:
        raise ValueError(f"{size} is an invalid cross size {widths}") from e

    with BuildSketch() as recess:
        Rectangle(m, m / 6)
        Rectangle(m / 6, m)
        fillet(recess.vertices().group_by(SortBy.DISTANCE)[0], m / 3)
    return (recess.face(), depths[size])


def hex_recess(size: float) -> Face:
    """Hexagon recess for screws

    size refers to the size across the flats
    """
    with BuildSketch() as plan:
        RegularPolygon(radius=size / 2, side_count=6, major_radius=False)
    return plan.face()


def hexalobular_recess(size: str) -> tuple[Face, float]:
    """Plan of Hexalobular recess for screws

    size must be one of: T6, T8, T10, T15, T20, T25, T30, T40, T45, T50, T55, T60,
                         T70, T80, T90, T100

    depth approximately 60% of maximum diameter
    """
    try:
        screw_data = evaluate_parameter_dict_of_dict(
            read_fastener_parameters_from_csv("iso10664def.csv")
        )[size]
    except KeyError as e:
        raise ValueError(f"{size} is an invalid hexalobular size") from e

    (A, B, Re) = (screw_data[p] for p in ["A", "B", "Re"])

    # Given the outer (A) and inner (B) diameters and the external radius (Re),
    # calculate the internal radius
    sqrt_3 = sqrt(3)
    Ri = (A**2 - sqrt_3 * A * B - 4 * A * Re + B**2 + 2 * sqrt_3 * B * Re) / (
        2 * (sqrt_3 * A - 2 * B - 2 * sqrt_3 * Re + 4 * Re)
    )

    center_external_arc = [
        Vector(0, A / 2 - Re),
        Vector(sqrt_3 * (A / 2 - Re) / 2, A / 4 - Re / 2),
    ]
    center_internal_arc = Vector(B / 4 + Ri / 2, sqrt_3 * (B / 2 + Ri) / 2)

    # Determine where the two arcs are tangent (i.e. touching)
    tangent_points = [
        center_external_arc[0]
        + (center_internal_arc - center_external_arc[0]).normalized() * Re,
        center_external_arc[1]
        + (center_internal_arc - center_external_arc[1]).normalized() * Re,
    ]

    # Create one sixth of the wire and repeat it
    with BuildSketch() as plan:
        with BuildLine(mode=Mode.PRIVATE) as arc:
            RadiusArc((0, A / 2), tangent_points[0], Re)
            RadiusArc(*tangent_points, -Ri)
            RadiusArc(tangent_points[1], (sqrt_3 * A / 4, A / 4), Re)
        with PolarLocations(0, 6):
            add(arc.line)
        make_face()

    return (plan.face(), 0.6 * A)


def slot_recess(width: float, length: float) -> Face:
    """Slot recess for screws"""
    return Face.make_rect(width, length)


def square_recess(size: str) -> tuple[Face, float]:
    """Robertson Square recess for screws

    size must be one of: R00, R0, R1, R2, and R3

    Note: Robertson sizes are also color coded: Orange, Yellow, Green, Red, Black

    """
    widths = {"R00": 1.80, "R0": 2.31, "R1": 2.86, "R2": 3.38, "R3": 4.85}
    depths = {"R00": 1.85, "R0": 2.87, "R1": 3.56, "R2": 4.19, "R3": 5.11}

    try:
        m = widths[size]
    except KeyError as e:
        raise ValueError(f"{size} is an invalid square size {widths}") from e
    return (Face.make_rect(m, m), depths[size])


def select_by_size_fn(cls, size: str) -> dict:
    """Given a fastener size, return a dictionary of {class:[type,...]}"""
    type_dict = {}
    for fastener_class in cls.__subclasses__():
        for fastener_type in fastener_class.types():
            if size in fastener_class.sizes(fastener_type):
                if fastener_class in type_dict.keys():
                    type_dict[fastener_class].append(fastener_type)
                else:
                    type_dict[fastener_class] = [fastener_type]

    return type_dict


def method_exists(cls, method: str) -> bool:
    """Did the derived class create this method"""
    return hasattr(cls, method) and callable(getattr(cls, method))


class Nut(ABC, BasePartObject):
    """Parametric Nut

    Base Class used to create standard threaded nuts

    Args:
        size (str): standard sizes - e.g. "M6-1"
        fastener_type (str): type identifier - e.g. "iso4032"
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.

    Raises:
        ValueError: invalid size, must be formatted as size-pitch or size-TPI
        ValueError: invalid fastener_type
        ValueError: invalid hand, must be one of 'left' or 'right'
        ValueError: invalid size

    Each nut instance creates a set of instance variables that provide the CAD object as well as valuable
    parameters, as follows (values intended for internal use are not shown):

    """

    _applies_to = [BuildPart._tag]

    # Read clearance and tap hole dimensions tables
    # Close, Medium, Loose
    clearance_hole_drill_sizes = read_fastener_parameters_from_csv(
        "clearance_hole_sizes.csv"
    )
    clearance_hole_data = lookup_drill_diameters(clearance_hole_drill_sizes)

    # Soft (Aluminum, Brass, & Plastics) or Hard (Steel, Stainless, & Iron)
    tap_hole_drill_sizes = read_fastener_parameters_from_csv("tap_hole_sizes.csv")
    tap_hole_data = lookup_drill_diameters(tap_hole_drill_sizes)

    @property
    def tap_drill_sizes(self):
        """A dictionary of drill sizes for tapped holes"""
        try:
            return self.tap_hole_drill_sizes[self.thread_size]
        except KeyError as e:
            raise ValueError(f"No tap hole data for size {self.thread_size}") from e

    @property
    def tap_hole_diameters(self):
        """A dictionary of drill diameters for tapped holes"""
        try:
            return self.tap_hole_data[self.thread_size]
        except KeyError as e:
            raise ValueError(f"No tap hole data for size {self.thread_size}") from e

    @property
    def clearance_drill_sizes(self):
        """A dictionary of drill sizes for clearance holes"""
        try:
            return self.clearance_hole_drill_sizes[self.thread_size.split("-")[0]]
        except KeyError as e:
            raise ValueError(
                f"No clearance hole data for size {self.thread_size}"
            ) from e

    @property
    def clearance_hole_diameters(self):
        """A dictionary of drill diameters for clearance holes"""
        try:
            return self.clearance_hole_data[self.thread_size.split("-")[0]]
        except KeyError as e:
            raise ValueError(
                f"No clearance hole data for size {self.thread_size}"
            ) from e

    @classmethod
    def select_by_size(cls, size: str) -> dict:
        """Return a dictionary of list of fastener types of this size"""
        return select_by_size_fn(cls, size)

    @property
    @abstractmethod
    def fastener_data(cls):  # pragma: no cover
        """Each derived class must provide a fastener_data dictionary"""
        return NotImplementedError

    @abstractmethod
    def nut_profile(self) -> Face:  # pragma: no cover
        """Each derived class must provide the profile of the nut"""
        return NotImplementedError

    @abstractmethod
    def nut_plan(self) -> Face:  # pragma: no cover
        """Each derived class must provide the plan of the nut"""
        return NotImplementedError

    @abstractmethod
    def countersink_profile(
        self, fit: Literal["Close", "Normal", "Loose"]
    ) -> Face:  # pragma: no cover
        """Each derived class must provide the profile of a countersink cutter"""
        return NotImplementedError

    @property
    def info(self):
        """Return identifying information"""
        return f"{self.nut_class}({self.fastener_type}): {self.thread_size}"

    @property
    def nut_class(self):
        """Which derived class created this nut"""
        return type(self).__name__

    @classmethod
    def types(cls) -> set[str]:
        """Return a set of the nut types"""
        return set(p.split(":")[0] for p in list(cls.fastener_data.values())[0].keys())

    @classmethod
    def sizes(cls, fastener_type: str) -> list[str]:
        """Return a list of the nut sizes for the given type"""
        return list(isolate_fastener_type(fastener_type, cls.fastener_data).keys())

    @property
    def nut_thickness(self):
        """Calculate the maximum thickness of the nut"""
        return self.bounding_box().max.Z

    @property
    def nut_diameter(self):
        """Calculate the maximum diameter of the nut"""
        bottom_vertices = self.nut_plan().vertices()
        if len(bottom_vertices) < 3:
            raise Exception(f"Invalid nut: {type(self).__name__},{self.__dict__}")
        bottom_arc = Edge.make_three_point_arc(*bottom_vertices[0:3])
        return 2 * bottom_arc.radius

    def length_offset(self):
        """Screw only parameter"""
        return 0

    def __init__(
        self,
        size: str,
        fastener_type: str,
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        self.hole_locations: list[Location] = []  #: custom holes locations
        self.nut_thickness: float  #: maximum thickness of the nut
        self.nut_diameter: float  #: maximum diameter of the nut

        self.nut_size = size.strip()
        size_parts = self.nut_size.split("-")
        if 3 > len(size_parts) < 2:
            raise ValueError(
                f"{size_parts} invalid, must be formatted as size-pitch(-length) or size-TPI(-length) where length is optional"
            )
        self.thread_size = "-".join(size_parts[:2])
        if len(size_parts) >= 3:
            self.length_size = size_parts[2]
        self.is_metric = self.thread_size[0] == "M"
        if self.is_metric:
            self.thread_diameter = float(size_parts[0][1:])
            self.thread_pitch = float(size_parts[1])
        else:
            (self.thread_diameter, self.thread_pitch) = decode_imperial_size(
                self.thread_size
            )

        if fastener_type not in self.types():
            raise ValueError(f"{fastener_type} invalid, must be one of {self.types()}")
        self.fastener_type = fastener_type
        if hand in ["left", "right"]:
            self.hand = hand
        else:
            raise ValueError(f"{hand} invalid, must be one of 'left' or 'right'")
        self.simple = simple
        self.socket_clearance = 6 * MM  # Used as extra clearance when countersinking
        try:
            self.nut_data = evaluate_parameter_dict(
                isolate_fastener_type(self.fastener_type, self.fastener_data)[
                    self.nut_size
                ],
                is_metric=self.is_metric,
            )
        except KeyError as e:
            raise ValueError(
                f"{size} invalid, must be one of {self.sizes(self.fastener_type)}"
            ) from e
        if method_exists(self.__class__, "custom_make"):
            bd_object = self.custom_make()
        else:
            bd_object = self.make_nut()

        # Unwrap the Compound if possible
        if isinstance(bd_object, Compound) and len(bd_object.solids()) == 1:
            super().__init__(bd_object.solid(), rotation, align, mode)
        else:
            super().__init__(bd_object, rotation, align, mode)
        self.label = f"{self.__class__.__name__}({size}, {fastener_type})"
        self.color = Color(0xC0C0C0)
        RigidJoint("a", self, Location())
        RigidJoint("b", self, Pos(Z=self.nut_thickness))

    def make_nut(self) -> Union[Compound, Solid]:
        """Create a screw head from the 2D shapes defined in the derived class"""

        # pylint: disable=no-member
        profile = self.nut_profile()
        max_nut_height = profile.bounding_box().max.Z
        nut_thread_height = self.nut_data["m"]

        # Create the basic nut shape
        nut = revolve(profile, Axis.Z)

        # Modify the head to conform to the shape of head_plan (e.g. hex)
        # Note that some nuts (e.g. domed nuts) extend beyond the threaded section
        nut_blank = extrude(
            self.nut_plan(), max_nut_height, (0, 0, 1)
        ) - Solid.make_cylinder(self.thread_diameter / 2, nut_thread_height)
        nut = nut.intersect(nut_blank)
        if isinstance(nut, list):
            nut = nut[0]

        # Add a flange as it exists outside of the head plan
        if method_exists(self.__class__, "flange_profile"):
            flange = revolve(
                split(
                    self.flange_profile(),
                    Plane.YZ.offset(self.thread_diameter / 2 + 0.1),
                ),
                Axis.Z,
            )
            nut = nut.fuse(flange)

        nut.label = "body"

        # Add the thread to the nut body
        if not self.simple:
            # Create the thread
            thread = IsoThread(
                major_diameter=self.thread_diameter,
                pitch=self.thread_pitch,
                length=self.nut_data["m"],
                external=False,
                end_finishes=("fade", "fade"),
                hand=self.hand,
            )
            thread.label = "thread"
            nut = Part(children=[nut, thread])

        return nut

    def default_nut_profile(self) -> Face:
        """Create 2D profile of hex nuts with double chamfers"""
        (m, s) = (self.nut_data[p] for p in ["m", "s"])
        e = polygon_diagonal(s, 6)
        # Chamfer angle must be between 15 and 30 degrees
        cs = (e - s) * tan(radians(15)) / 2

        # Note that when intersecting a revolved shape with a extruded polygon the OCCT
        # core may fail unless the polygon is slightly larger than the circle so
        # all profiles must be reduced by a small fudge factor
        with BuildSketch(Plane.XZ) as profile:
            Polygon(
                (0, 0),
                (s / 2, 0),
                (e / 2 - 0.001, cs),
                (e / 2 - 0.001, m - cs),
                (s / 2, m),
                (0, m),
                (0, 0),
                align=None,
            )
        return profile.sketch.face()

    def default_nut_plan(self) -> Face:
        """Create a hexagon solid"""
        with BuildSketch() as plan:
            RegularPolygon(self.nut_data["s"] / 2, 6, major_radius=False)
        return plan.face()

    def default_countersink_profile(self, fit) -> Face:
        """A simple rectangle with gets revolved into a cylinder with an
        extra socket_clearance (defaults to 6mm across the diameter) for a socket wrench
        """
        # Note that fit is only used for some flanged nuts but is here for uniformity
        del fit
        (m, s) = (self.nut_data[p] for p in ["m", "s"])
        width = polygon_diagonal(s, 6) + self.socket_clearance
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(width / 2, m, align=Align.MIN)
        return profile.sketch.face()


class DomedCapNut(Nut):
    """Domed Cap Nut

    DIN 1587 domed cap nuts, also known as acorn nuts, feature a high, rounded, closed-end top.
    These nuts are typically used to provide a finished appearance while also protecting exposed
    bolt threads from damage or corrosion. The dome prevents the entry of dirt and moisture, making
    them suitable for applications where hygiene, safety, or aesthetics are important. Domed cap nuts
    are often found in furniture, machinery, automotive, and architectural applications.

    These nuts are tightened like standard hex nuts but offer the added benefit of thread protection
    and a smoother exterior that reduces the risk of snagging or injury.

    Args:
        size (str): size specification, e.g. "M6-1"
        fastener_type (Literal["din1587"], optional): Defaults to "din1587".
            din1587 Hexagon domed cap nuts
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment.
            Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.

    """

    fastener_data = read_fastener_parameters_from_csv("domed_cap_nut_parameters.csv")

    def __init__(
        self,
        size: str,
        fastener_type: Literal["din1587"] = "din1587",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(size, fastener_type, hand, simple, rotation, align, mode)

    def nut_profile(self) -> Face:
        """Create 2D profile of hex nuts with double chamfers"""
        (dk, m, s) = (self.nut_data[p] for p in ["dk", "m", "s"])
        e = polygon_diagonal(s, 6)
        # Chamfer angle must be between 15 and 30 degrees
        cs = (e - s) * tan(radians(15)) / 2
        with BuildSketch(Plane.XZ) as profile:
            with BuildLine():
                Polyline(
                    (1 * MM, 0),
                    (s / 2, 0),
                    (e / 2, cs),
                    (e / 2, m - cs),
                    (s / 2, m),
                    (dk / 2, m),
                )
                RadiusArc((dk / 2, m), (0, m + dk / 2), -dk / 2)
                Line((0, m + dk / 2), (0, m + dk / 2 - 1 * MM))
                RadiusArc(
                    (0, m + dk / 2 - 1 * MM), (dk / 2 - 1 * MM, m), (dk / 2 - 1 * MM)
                )
                Polyline((dk / 2 - 1 * MM, m), (1 * MM, m), (1 * MM, 0))
            make_face()

        return profile.sketch.face()

    def countersink_profile(self, fit) -> Face:
        """A simple rectangle with gets revolved into a cylinder with an
        extra socket_clearance (defaults to 6mm across the diameter) for a socket wrench
        """
        # Note that fit is only used for some flanged nuts but is here for uniformity
        del fit
        (dk, m, s) = (self.nut_data[p] for p in ["dk", "m", "s"])
        width = polygon_diagonal(s, 6) + self.socket_clearance
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(width / 2, m + dk / 2, align=Align.MIN)
        return profile.sketch.face()

    nut_plan = Nut.default_nut_plan


# class BradTeeNut(Nut):
#     """Brad Tee Nut

#     A Brad Tee Nut - a large flanged nut fastened with multiple screws countersunk
#     into the flange.

#     Args:
#         size (str): nut size, e.g. M6-1
#         fastener_type (str): "Hilitchi"
#         hand (Literal["right", "left"]): thread direction. Defaults to "right".
#         simple (bool): omit the thread from the nut. Defaults to True.
#     """

#     fastener_data = read_fastener_parameters_from_csv("brad_tee_nut_parameters.csv")

#     def custom_make(self) -> Compound:
#         """A build123d Compound nut as defined by class attributes"""
#         brad = CounterSunkScrew(
#             size=self.nut_data["brad_size"],
#             length=2 * self.nut_data["c"],
#             fastener_type="iso10642",
#         )

#         return (
#             self.make_nut()
#             .faces(">Z")
#             .workplane()
#             .polarArray(self.nut_data["bcd"] / 2, 0, 360, self.nut_data["brad_num"])
#             .clearanceHole(fastener=brad)
#             .val()
#         )

#     def nut_profile(self):
#         (dc, s, m, c) = (self.nut_data[p] for p in ["dc", "s", "m", "c"])
#         return (
#             cq.Workplane("XZ")
#             .vLine(m)
#             .hLine(dc / 2)
#             .vLine(-c)
#             .hLineTo(s)
#             .vLineTo(0)
#             .hLineTo(0)
#             .close()
#         )

#     def nut_plan(self):
#         return cq.Workplane("XY").circle(self.nut_data["dc"] / 2)

#     def countersink_profile(
#         self, fit: Literal["Close", "Normal", "Loose"]
#     ) -> cq.Workplane:
#         """A enlarged cavity allowing the nut to be countersunk"""
#         try:
#             clearance_hole_diameter = self.clearance_hole_diameters[fit]
#         except KeyError as e:
#             raise ValueError(
#                 f"{fit} invalid, must be one of {list(self.clearance_hole_diameters.keys())}"
#             ) from e
#         (dc, s, m, c) = (self.nut_data[p] for p in ["dc", "s", "m", "c"])
#         clearance = (clearance_hole_diameter - self.thread_diameter) / 2
#         return (
#             cq.Workplane("XZ")
#             .vLine(m)
#             .hLine(dc / 2 + clearance)
#             .vLine(-c - clearance)
#             .hLineTo(s + clearance)
#             .vLineTo(-clearance)
#             .hLineTo(0)
#             .close()
#         )


class HeatSetNut(Nut):
    """Heat Set Nut

    Heat set insert nuts are specially designed threaded inserts used in thermoplastics to provide
    durable, reusable threads in 3D printed or injection-molded parts. These inserts are installed
    by heating them—typically with a soldering iron—and pressing them into a pre-formed hole in the
    plastic. As the insert heats the surrounding plastic, it melts slightly and flows into the
    knurled or slotted features of the insert, forming a strong mechanical bond upon cooling.

    Heat set nuts are ideal for applications where threaded fasteners are frequently assembled and
    disassembled, helping to prevent wear and stripping in plastic components. They are widely used
    in prototyping, enclosures, robotics, and other applications where lightweight, modular designs
    are needed.

    Args:
        size (str): nut size, e.g. M5-0.8-Standard
        fastener_type (str): standard or manufacturer that defines the nut ["McMaster-Carr"]
        hand (Literal["right", "left"], optional): direction of thread. Defaults to "right".
        simple (bool): omit the thread from the nut. Defaults to True.

    Attributes:
        fill_factor (float): Fraction of insert hole filled with heatset nut
    """

    fastener_data = read_fastener_parameters_from_csv("heatset_nut_parameters.csv")

    @property
    def nut_diameter(self):
        """Calculate the maximum diameter of the nut"""
        return float(self.fastener_data[self.nut_size][self.fastener_type + ":s"])

    def __init__(
        self,
        size: str,
        fastener_type: Literal["McMaster-Carr", "Hilitchi"] = "McMaster-Carr",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(size, fastener_type, hand, simple, rotation, align, mode)

    @staticmethod
    def knurled_cylinder_faces(
        diameter: float,
        bottom_hole_radius: float,
        top_hole_radius: float,
        height: float,
        knurl_depth: float,
        pitch: float,
        tip_count: int,
        hand: Literal["right", "left"] = "right",
    ) -> list[Face]:
        """Faces of Knurled Cylinder

        Generate a list of Faces on a knurled cylinder with a central hole. These faces are
        used to build a knurled HeatSet insert with maximal performance.

        Args:
            diameter (float): outside diameter of knurled cylinder
            bottom_hole_radius (float): size of bottom hole
            top_hole_radius (float): size of top hole
            height (float): end-to-end height
            knurl_depth (float): size of the knurling
            pitch (float): knurling helical pitch
            tip_count (int): number of knurled tips
            hand (Literal["right", "left"], optional): direction of knurling. Defaults to "right".

        Returns:
            list[Face]: Faces of the knurled cylinder except for central hole
        """

        # Start by creating helical edges for the inside and outside of the knurling
        lefthand = hand == "left"
        inside_edges = [
            Edge.make_helix(
                pitch, height, diameter / 2 - knurl_depth, lefthand=lefthand
            ).rotate(Axis.Z, i * 360 / tip_count)
            for i in range(tip_count)
        ]
        outside_edges = [
            Edge.make_helix(pitch, height, diameter / 2, lefthand=lefthand).rotate(
                Axis.Z, (i + 0.5) * 360 / tip_count
            )
            for i in range(tip_count)
        ]
        # Connect the bottoms of the helical edges into a star shaped bottom face
        bottom_edges = [
            (
                Edge.make_line(
                    inside_edges[i].position_at(0), outside_edges[i].position_at(0)
                ),
                Edge.make_line(
                    outside_edges[i].position_at(0),
                    inside_edges[(i + 1) % tip_count].position_at(0),
                ),
            )
            for i in range(tip_count)
        ]
        # Flatten the list of tuples to a list
        bottom_edges = list(sum(bottom_edges, ()))

        top_edges = [
            (
                Edge.make_line(
                    inside_edges[i].position_at(1), outside_edges[i].position_at(1)
                ),
                Edge.make_line(
                    outside_edges[i].position_at(1),
                    inside_edges[(i + 1) % tip_count].position_at(1),
                ),
            )
            for i in range(tip_count)
        ]
        top_edges = list(sum(top_edges, ()))

        # Build the faces from the edges
        outside_faces = [
            (
                Face.make_surface(
                    [
                        inside_edges[i],
                        outside_edges[i],
                        bottom_edges[2 * i],
                        top_edges[2 * i],
                    ],
                ),
                Face.make_surface(
                    [
                        outside_edges[i],
                        inside_edges[(i + 1) % tip_count],
                        bottom_edges[2 * i + 1],
                        top_edges[2 * i + 1],
                    ],
                ),
            )
            for i in range(tip_count)
        ]
        outside_faces = list(sum(outside_faces, ()))

        # Create the top and bottom faces with holes in them
        bottom_face = Face(
            Wire(bottom_edges), [Wire(Edge.make_circle(bottom_hole_radius))]
        )
        top_face = Face(
            Wire(top_edges),
            [Wire(Edge.make_circle(top_hole_radius, Plane.XY.offset(height)))],
        )

        return [bottom_face, top_face] + outside_faces

    @property
    def fill_factor(self) -> float:
        """Relative size of nut vs hole

        Returns:
            float: Fraction of insert hole filled with heatset nut
        """
        drill_sizes = read_drill_sizes()
        hole_radius = drill_sizes[self.nut_data["drill"].strip()] / 2
        heatset_volume = (
            self.volume + self.nut_data["m"] * pi * (self.thread_diameter / 2) ** 2
        )
        hole_volume = self.nut_data["m"] * pi * hole_radius**2
        return heatset_volume / hole_volume

    def make_nut(self) -> Solid:
        """Build heatset nut object

        Create the heatset nut with a flanged bottom and two knurled sections
        with opposite twist direction which locks into the plastic when heated
        and inserted into an appropriate hole.

        To maximize performance, the nut is created by building assembling Faces
        into a Shell which is converted to a Solid. No extrusions or boolean
        operations are used until the thread is added to the nut.

        Returns:
            Solid: the heatset nut
        """
        nut_base = Cylinder(
            self.nut_data["dc"] / 2,
            0.11 * self.nut_data["m"],
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        ) + Cylinder(
            0.425 * self.nut_data["dc"],
            0.24 * self.nut_data["m"],
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
        base_bottom_face = (
            nut_base.faces()
            .sort_by(Axis.Z)[0]
            .make_holes([Wire(Edge.make_circle(self.thread_diameter / 2))])
        )
        base_outside_faces = nut_base.faces().sort_by(Axis.Z)[1:-1]

        # Create the lower knurled section Faces
        lower_knurl_faces = HeatSetNut.knurled_cylinder_faces(
            self.nut_data["s"],
            0.425 * self.nut_data["dc"],
            0.425 * self.nut_data["dc"],
            height=0.33 * self.nut_data["m"],
            knurl_depth=0.1 * self.nut_data["s"],
            pitch=3 * self.nut_data["m"],
            tip_count=self.nut_data["knurls"],
            hand="right",
        )
        lower_knurl_faces = [
            f.translate(Vector(0, 0, 0.24 * self.nut_data["m"]))
            for f in lower_knurl_faces
        ]
        # Create the Face in the gap between the knurled sections
        nut_middle_face = Face.extrude(
            Edge.make_circle(
                0.425 * self.nut_data["dc"], Plane.XY.offset(0.57 * self.nut_data["m"])
            ),
            (0, 0, 0.1 * self.nut_data["m"]),
        )

        # Create the Faces in the upper knurled section
        upper_knurl_faces = HeatSetNut.knurled_cylinder_faces(
            self.nut_data["s"],
            0.425 * self.nut_data["dc"],
            self.thread_diameter / 2,
            height=0.33 * self.nut_data["m"],
            knurl_depth=0.1 * self.nut_data["s"],
            pitch=3 * self.nut_data["m"],
            tip_count=20,
            hand="left",
        )
        upper_knurl_faces = [
            f.translate(Vector(0, 0, 0.67 * self.nut_data["m"]))
            for f in upper_knurl_faces
        ]

        # Create the Face for the inside of the nut
        thread_hole_face = Face.extrude(
            Edge.make_circle(self.thread_diameter / 2),
            (0, 0, self.nut_data["m"]),
        )

        # Build a Shell of the nut from all of the Faces
        nut_shell = Shell(
            [base_bottom_face, nut_middle_face, thread_hole_face]
            + base_outside_faces
            + lower_knurl_faces
            + upper_knurl_faces
        )

        # Finally create the Solid from the Shell
        nut = Solid(nut_shell)
        nut.label = "body"

        # Add the thread to the nut body
        if not self.simple:
            # Create the thread
            thread = IsoThread(
                major_diameter=self.thread_diameter,
                pitch=self.thread_pitch,
                length=self.nut_data["m"],
                external=False,
                end_finishes=("fade", "fade"),
                hand=self.hand,
            )
            nut = Part(children=[nut, thread])

        return nut

    def nut_profile(self) -> Face:  # pragma: no cover
        """Not used but required by the abstract base class"""
        pass

    def nut_plan(self) -> Face:  # pragma: no cover
        """Not used but required by the abstract base class"""
        pass

    def countersink_profile(self, manufacturing_compensation: float = 0.0) -> Face:
        """countersink_profile

        Create the profile for a cavity allowing the heatset nut to be countersunk into the plastic.

        Args:
            manufacturing_compensation (float, optional): used to compensate for over-extrusion
                of 3D printers. A value of 0.2mm will reduce the radius of an external thread
                by 0.2mm (and increase the radius of an internal thread) such that the resulting
                3D printed part matches the target dimensions. Defaults to 0.0.

        Returns:
            Face: The countersink hole profile
        """
        drill_sizes = read_drill_sizes()
        hole_radius = (
            drill_sizes[self.nut_data["drill"].strip()] / 2 + manufacturing_compensation
        )
        # chamfer_size = self.nut_data["s"] / 2 - hole_radius
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(hole_radius, self.nut_data["m"], align=Align.MIN).face()
        return profile.sketch


class HexNut(Nut):
    """Hex Nut

    Hex nuts are the most commonly used type of fastening nut, featuring a six-sided profile that
    provides a strong grip and easy installation with standard tools. They are used in conjunction
    with bolts, screws, and other externally threaded fasteners to secure components in mechanical
    assemblies.

    ISO 4032, ISO 4033, and ISO 4035 define different variants of metric hex nuts:
    - ISO 4032 specifies a regular height hex nut with a standard width across flats.
    - ISO 4033 defines a heavy series hex nut, typically used for larger or more heavily loaded assemblies.
    - ISO 4035 specifies a thin (jam) nut, used where space is limited or as a locknut against a standard nut.

    These nuts are widely used across industries including automotive, aerospace, machinery, and
    construction. They are available in various grades and finishes to suit different strength,
    corrosion resistance, and environmental requirements.

    Args:
        size (str): size specification, e.g. "M6-1"
        fastener_type (Literal["iso4032", "iso4033", "iso4035"], optional):
            Defaults to "iso4032".
            iso4032	Hexagon nuts, Style 1
            iso4033	Hexagon nuts, Style 2
            iso4035	Hexagon thin nuts, chamfered
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment.
            Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv("hex_nut_parameters.csv")

    def __init__(
        self,
        size: str,
        fastener_type: Literal["iso4032", "iso4033", "iso4035"] = "iso4032",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(size, fastener_type, hand, simple, rotation, align, mode)

    nut_profile = Nut.default_nut_profile
    nut_plan = Nut.default_nut_plan
    countersink_profile = Nut.default_countersink_profile


class HexNutWithFlange(Nut):
    """Hex Nut With Flange

    A hex nut with flange combines a standard six-sided nut with an integrated flange at the base,
    which acts like a built-in washer. This flange helps distribute the clamping load over a larger
    surface area, reducing surface pressure and the risk of damage to softer materials. It also
    improves resistance to loosening due to vibration by increasing friction at the mating surface.

    DIN 1665 specifies metric hex flange nuts used in general-purpose and structural applications.
    These nuts are often used in automotive, machinery, and assembly applications where ease of use,
    improved load distribution, and vibration resistance are desired. The flanged base eliminates the
    need for a separate washer in many cases, simplifying assembly and reducing part count.

    Args:
        size (str): size specification, e.g. "M6-1"
        fastener_type (Literal["din1665"], optional): Defaults to "din1665".
            din1665 Hexagon nuts with flange
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment.
            Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv(
        "hex_nut_with_flange_parameters.csv"
    )

    def __init__(
        self,
        size: str,
        fastener_type: Literal["din1665"] = "din1665",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(size, fastener_type, hand, simple, rotation, align, mode)

    nut_profile = Nut.default_nut_profile
    nut_plan = Nut.default_nut_plan

    def flange_profile(self) -> Face:
        """Flange for hexagon Bolts"""
        (dc, c) = (self.nut_data[p] for p in ["dc", "c"])
        flange_angle = 25
        tangent_point = Vector(
            (c / 2) * cos(radians(90 - flange_angle)),
            (c / 2) * sin(radians(90 - flange_angle)),
        ) + Vector((dc - c) / 2, c / 2)
        with BuildSketch(Plane.XZ) as profile:
            with BuildLine():
                l1 = Line((0, 0), (dc / 2 - c / 2, 0))
                RadiusArc(l1 @ 1, tangent_point, -c / 2)
                l3 = PolarLine(tangent_point, dc / 2 - c / 2, 180 - flange_angle)
                Polyline(l3 @ 1, (0, l3.position_at(1).Y), (0, 0))
            make_face()
        return profile.sketch.face()

    def countersink_profile(self, fit: Literal["Close", "Normal", "Loose"]) -> Face:
        """A simple rectangle with gets revolved into a cylinder with
        at least socket_clearance (default 6mm across the diameter) for a socket wrench
        """
        try:
            clearance_hole_diameter = self.clearance_hole_diameters[fit]
        except KeyError as e:
            raise ValueError(
                f"{fit} invalid, must be one of {list(self.clearance_hole_diameters.keys())}"
            ) from e
        (dc, s, m) = (self.nut_data[p] for p in ["dc", "s", "m"])
        clearance = clearance_hole_diameter - self.thread_diameter
        width = max(dc + clearance, polygon_diagonal(s, 6) + self.socket_clearance)
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(width / 2, m, align=Align.MIN)
        return profile.sketch.face()

    nut_plan = Nut.default_nut_plan


class UnchamferedHexagonNut(Nut):
    """Unchamfered Hexagon Nut

    ISO 4036 defines a thin, unchamfered hexagon nut, typically used in non-critical applications
    or where space and weight constraints are a priority. Unlike standard hex nuts, these nuts lack
    a chamfered edge and are manufactured with reduced height, which makes them suitable for
    low-stress assemblies, locking applications (e.g., as a jam nut), or secondary fastening positions.

    Due to their minimal height and absence of chamfers, they are generally not intended for high-load
    structural use. Instead, they are ideal for internal assemblies, compact enclosures, or when used
    in combination with standard nuts to resist loosening under vibration. ISO 4036 nuts are most often
    found in light mechanical assemblies and electronics hardware.

    Args:
        size (str): size specification, e.g. "M6-1"
        fastener_type (Literal["iso4036"], optional): Defaults to "iso4036".
            iso4036 Hexagon thin nuts, unchamfered
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment. Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv(
        "unchamfered_hex_nut_parameters.csv"
    )

    def __init__(
        self,
        size: str,
        fastener_type: Literal["iso4036"] = "iso4036",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(size, fastener_type, hand, simple, rotation, align, mode)

    def nut_profile(self):
        """Create 2D profile of hex nuts with double chamfers"""
        (m, s) = (self.nut_data[p] for p in ["m", "s"])
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(polygon_diagonal(s, 6) / 2 - 0.001, m, align=Align.MIN)
        return profile.sketch.face()

    nut_plan = Nut.default_nut_plan
    countersink_profile = Nut.default_countersink_profile


class SquareNut(Nut):
    """Square Nut

    Square nuts, as defined by DIN 557, are four-sided nuts commonly used in older machinery,
    woodworking, and applications where a flat bearing surface and greater resistance to loosening
    are beneficial. Their larger surface area compared to hex nuts provides increased grip and load
    distribution, especially when used with flat washers or in slots.

    DIN 557 specifies standard square nuts with a flat top and bottom and sharp or slightly chamfered
    corners. These nuts are well-suited for tightening by hand or with simple tools, and are often
    found in applications where ease of alignment or aesthetics are not critical. Their geometry makes
    them less prone to rounding and easier to weld or lock in place.

    Args:
        size (str): size specification, e.g. "M6-1"
        fastener_type (Literal["din557"], optional): Defaults to "din557".
            din557 - Square Nuts
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment.
            Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv("square_nut_parameters.csv")

    def __init__(
        self,
        size: str,
        fastener_type: Literal["din557"] = "din557",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(size, fastener_type, hand, simple, rotation, align, mode)

    def nut_profile(self) -> Face:
        """Create 2D profile of hex nuts with double chamfers"""
        (m, s) = (self.nut_data[p] for p in ["m", "s"])
        e = polygon_diagonal(s, 4)
        # Chamfer angle must be between 15 and 30 degrees
        cs = (e - s) * tan(radians(15)) / 2
        with BuildSketch(Plane.XZ) as profile:
            Polygon(
                (0, 0),
                (e / 2 - 0.001, 0),
                (e / 2 - 0.001, m - cs),
                (s / 2, m),
                (0, m),
                (0, 0),
                align=None,
            )
        return profile.sketch.face()

    def nut_plan(self) -> Face:
        """Simple square for the plan"""
        # return cq.Workplane("XY").rect(self.nut_data["s"], self.nut_data["s"])
        return Face.make_rect(self.nut_data["s"], self.nut_data["s"])

    def countersink_profile(self, fit) -> Face:
        """A simple rectangle with gets revolved into a cylinder with an
        extra socket_clearance (defaults to 6mm across the diameter) for a socket wrench
        """
        # Note that fit is only used for some flanged nuts but is here for uniformity
        del fit
        (m, s) = (self.nut_data[p] for p in ["m", "s"])
        width = polygon_diagonal(s, 4) + self.socket_clearance
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(width / 2, m, align=Align.MIN)
        return profile.sketch.face()


class Screw(ABC, BasePartObject):
    """Parametric Screw

    Base class for a set of threaded screws or bolts

    Args:
        size (str): standard sizes - e.g. "M6-1"
        length (float): distance from base of head to tip of thread
        fastener_type (str): type identifier - e.g. "iso4014"
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        socket_clearance (float, optional): gap around screw with no recess (e.g. hex head)
            which allows a socket wrench to be inserted. Defaults to 6mm.

    Raises:
        ValueError: invalid size, must be formatted as size-pitch or size-TPI
        ValueError: invalid fastener_type
        ValueError: invalid hand, must be one of 'left' or 'right'
        ValueError: invalid size

    """

    _applies_to = [BuildPart._tag]

    # Read clearance and tap hole dimesions tables
    # Close, Medium, Loose
    clearance_hole_drill_sizes = read_fastener_parameters_from_csv(
        "clearance_hole_sizes.csv"
    )
    clearance_hole_data = lookup_drill_diameters(clearance_hole_drill_sizes)

    # Soft (Aluminum, Brass, & Plastics) or Hard (Steel, Stainless, & Iron)
    tap_hole_drill_sizes = read_fastener_parameters_from_csv("tap_hole_sizes.csv")
    tap_hole_data = lookup_drill_diameters(tap_hole_drill_sizes)

    # Build a dictionary of nominal screw lengths keyed by screw type
    nominal_length_range = lookup_nominal_screw_lengths()

    @property
    def tap_drill_sizes(self) -> dict[str:float]:
        """A dictionary of drill sizes for tapped holes"""
        try:
            return self.tap_hole_drill_sizes[self.thread_size]
        except KeyError as e:
            raise ValueError(f"No tap hole data for size {self.thread_size}") from e

    @property
    def tap_hole_diameters(self) -> dict[str:float]:
        """A dictionary of drill diameters for tapped holes"""
        try:
            return self.tap_hole_data[self.thread_size]
        except KeyError as e:
            raise ValueError(f"No tap hole data for size {self.thread_size}") from e

    @property
    def clearance_drill_sizes(self) -> dict[str:float]:
        """A dictionary of drill sizes for clearance holes"""
        try:
            return self.clearance_hole_drill_sizes[self.thread_size.split("-")[0]]
        except KeyError as e:
            raise ValueError(
                f"No clearance hole data for size {self.thread_size}"
            ) from e

    @property
    def clearance_hole_diameters(self) -> dict[str:float]:
        """A dictionary of drill diameters for clearance holes"""
        try:
            return self.clearance_hole_data[self.thread_size.split("-")[0]]
        except KeyError as e:
            raise ValueError(
                f"No clearance hole data for size {self.thread_size}"
            ) from e

    @property
    @abstractmethod
    def fastener_data(cls):  # pragma: no cover
        """Each derived class must provide a fastener_data dictionary"""
        return NotImplementedError

    @abstractmethod
    def countersink_profile(
        self, fit: Literal["Close", "Normal", "Loose"]
    ) -> Face:  # pragma: no cover
        """Each derived class must provide the profile of a countersink cutter"""
        return NotImplementedError

    @classmethod
    def select_by_size(cls, size: str) -> dict[str:float]:
        """Return a dictionary of list of fastener types of this size"""
        return select_by_size_fn(cls, size)

    @classmethod
    def types(cls) -> list[str]:
        """Return a set of the screw types"""
        return set(p.split(":")[0] for p in list(cls.fastener_data.values())[0].keys())

    @classmethod
    def sizes(cls, fastener_type: str) -> list[str]:
        """Return a list of the screw sizes for the given type"""
        return list(isolate_fastener_type(fastener_type, cls.fastener_data).keys())

    def length_offset(self) -> float:
        """
        To enable screws to include the head height in their length (e.g. Countersunk),
        allow each derived class to override this length_offset calculation to the
        appropriate head height.
        """
        return 0

    def min_hole_depth(self, counter_sunk: bool = True) -> float:
        """Minimum depth of a hole able to accept the screw"""
        countersink_profile = self.countersink_profile("Loose")
        if countersink_profile is None:  # SetScrew
            return 0
        head_offset = countersink_profile.vertices().sort_by(Axis.Z)[-1].Z
        if counter_sunk:
            result = self.length + head_offset - self.length_offset()
        else:
            result = self.length - self.length_offset()
        return result

    @property
    def nominal_lengths(self) -> list[float] | None:
        """A list of nominal screw lengths for this screw"""
        try:
            range_min = self.screw_data["short"]
        except KeyError:
            range_min = None
        try:
            range_max = self.screw_data["long"]
        except KeyError:
            range_max = None
        if (
            range_min is None
            or range_max is None
            or not self.fastener_type in Screw.nominal_length_range.keys()
        ):
            result = None
        else:
            result = [
                size
                for size in Screw.nominal_length_range[self.fastener_type]
                if range_min <= size <= range_max
            ]
        return result

    @property
    def info(self) -> str:
        """Return identifying information"""
        return f"{self.screw_class}({self.fastener_type}): {self.thread_size}x{self.length}{' left hand thread' if self.hand=='left' else ''}"

    @property
    def screw_class(self) -> str:
        """Which derived class created this screw"""
        return type(self).__name__

    def __init__(
        self,
        size: str,
        length: float,
        fastener_type: str,
        hand: Optional[Literal["right", "left"]] = "right",
        simple: Optional[bool] = True,
        socket_clearance: Optional[float] = 6 * MM,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        self.hole_locations: list[Location] = []  #: custom holes locations
        self.screw_size = size
        self.head_height: float  #: maximum height of the screw head
        self.head_diameter: float  #: maximum diameter of the screw head

        size_parts = size.strip().split("-")
        if not len(size_parts) == 2:
            raise ValueError(
                f"{size_parts} invalid, must be formatted as size-pitch or size-TPI"
            )

        self.thread_size = size
        self.is_metric = self.thread_size[0] == "M"
        if self.is_metric:
            self.thread_diameter = float(size_parts[0][1:])
            self.thread_pitch = float(size_parts[1])
        else:
            (self.thread_diameter, self.thread_pitch) = decode_imperial_size(
                self.thread_size
            )

        self.length = length
        if fastener_type not in self.types():
            raise ValueError(f"{fastener_type} invalid, must be one of {self.types()}")
        self.fastener_type = fastener_type
        if hand in ["left", "right"]:
            self.hand = hand
        else:
            raise ValueError(f"{hand} invalid, must be one of 'left' or 'right'")
        self.simple = simple
        try:
            self.screw_data = evaluate_parameter_dict(
                isolate_fastener_type(self.fastener_type, self.fastener_data)[
                    self.thread_size
                ],
                is_metric=self.is_metric,
            )
        except KeyError as e:
            raise ValueError(
                f"{size} invalid, must be one of {self.sizes(self.fastener_type)}"
            ) from e
        self.socket_clearance = socket_clearance  # Only used for hex head screws

        length_offset = self.length_offset()
        if length_offset >= self.length:
            raise ValueError(
                f"Screw length {self.length} is <= countersunk screw head {length_offset}"
            )
        self.max_thread_length = self.length - length_offset
        self.thread_length = length - length_offset
        head = self.make_head()

        if head is None:  # A fully custom screw
            screw = None
            self.head_height = 0
            self.head_diameter = 0
            ends = ("fade", "fade")
        else:
            head_bb = head.bounding_box()
            self.head_height = head_bb.max.Z
            self.head_diameter = 2 * max(head_bb.max.X, head_bb.max.Y)
            ends = ("fade", "raw")
            head = head.translate((0, 0, -self.length_offset()))

        thread = IsoThread(
            major_diameter=self.thread_diameter,
            pitch=self.thread_pitch,
            length=self.thread_length,
            external=True,
            hand=self.hand,
            end_finishes=ends,
            simple=self.simple,
            # ).locate(Pos(Z=-self.length))
        )
        if not self.simple:
            thread = thread.locate(Pos(Z=-self.length))
        thread.label = "thread"

        shank = Solid.make_cylinder(
            thread.min_radius, self.thread_length, Plane.XY.offset(-self.length)
        )

        if method_exists(self.__class__, "custom_make"):
            screw = self.custom_make()
        elif head is not None:
            screw = head.fuse(shank)
        else:
            screw = shank

        # Unwrap the Compound as it's unnecessary
        if isinstance(screw, Compound):
            screw = screw.unwrap(fully=True)
        screw.label = "body"

        if not self.simple:
            screw = Part(children=[screw, thread])

        super().__init__(screw, rotation, align, mode)
        self.label = (
            f"{self.__class__.__name__}({size}, {length:0.2f}, {fastener_type})"
        )
        self.color = Color(0xC0C0C0)
        RigidJoint("a", self, Location())
        CylindricalJoint("b", self, axis=Axis(self.faces().filter_by(Plane.XY).sort_by(Axis.Z)[0].center_location), linear_range=(-self.length + self.head_height, 0))

    def make_head(self) -> Solid:
        """Create a screw head from the 2D shapes defined in the derived class"""

        # Determine what shape creation methods have been defined
        has_profile = method_exists(self.__class__, "head_profile")
        has_plan = method_exists(self.__class__, "head_plan")
        has_recess = method_exists(self.__class__, "head_recess")
        has_flange = method_exists(self.__class__, "flange_profile")
        # raise RuntimeError
        if has_profile:
            # pylint: disable=no-member
            profile = self.head_profile()
            profile_bbox = profile.bounding_box()
            max_head_height = profile_bbox.size.Z
            max_head_radius = profile_bbox.max.X
            min_head_height = profile_bbox.min.Z

            # Create the basic head shape
            head = revolve(profile)
        if has_plan:
            # pylint: disable=no-member
            head_plan = self.head_plan()
        else:
            # Ensure this default plan is outside of the maximum profile dimension.
            # As the slot cuts across the entire head it must go outside of the top
            # face. By creating an overly large head plan the slot can be safely
            # contained within and it doesn't clip the revolved profile.
            head_plan = Face.make_rect(
                3 * max_head_radius,
                3 * max_head_radius,
                Plane.XY.offset(min_head_height),
            )

        # Potentially modify the head to conform to the shape of head_plan
        # (e.g. hex) and/or to add an engagement recess
        if has_recess:
            # pylint: disable=no-member
            (recess_plan, recess_depth, recess_taper) = self.head_recess()
            recess = Solid.extrude_taper(
                recess_plan,
                (0, 0, -recess_depth),
                taper=recess_taper,
            ).translate((0, 0, max_head_height))
            head_blank = extrude(head_plan, max_head_height, (0, 0, 1)) - recess
            head = head.intersect(head_blank)
        elif has_plan:
            head_blank = extrude(head_plan, max_head_height)
            head = head.intersect(head_blank)
        if isinstance(head, list):
            head = head[0]

        # Add a flange as it exists outside of the head plan
        if has_flange:
            # pylint: disable=no-member
            head = head.fuse(revolve(self.flange_profile()))
        return head

    def default_head_recess(self) -> tuple[Face, float, float]:
        """Return the plan of the recess, its depth and taper"""

        recess_plan = None
        # Slot Recess
        try:
            (dk, n, t) = (self.screw_data[p] for p in ["dk", "n", "t"])
            recess_plan = slot_recess(dk, n)
            recess_depth = t
            recess_taper = 0
        except KeyError:
            pass
        # Hex Recess
        try:
            (s, t) = (self.screw_data[p] for p in ["s", "t"])
            recess_plan = hex_recess(s)
            recess_depth = t
            recess_taper = 0
        except KeyError:
            pass

        # Philips, Torx or Robertson Recess
        try:
            recess = self.screw_data["recess"]
            recess = str(recess).upper()
            if recess.startswith("PH"):
                (recess_plan, recess_depth) = cross_recess(recess)
                recess_taper = 30  # TODO
                recess_taper = 20
            elif recess.startswith("T"):
                (recess_plan, recess_depth) = hexalobular_recess(recess)
                recess_taper = 0
                recess_taper = 5
            elif recess.startswith("R"):
                (recess_plan, recess_depth) = square_recess(recess)
                recess_taper = 0
        except KeyError:
            pass

        if recess_plan is None:
            raise ValueError(f"Recess data missing from screw_data{self.screw_data}")

        return (recess_plan, recess_depth, recess_taper)

    def default_countersink_profile(
        self, fit: Literal["Close", "Normal", "Loose"]
    ) -> Face:
        """A simple rectangle with gets revolved into a cylinder"""
        try:
            clearance_hole_diameter = self.clearance_hole_diameters[fit]
        except KeyError as e:
            raise ValueError(
                f"{fit} invalid, must be one of {list(self.clearance_hole_diameters.keys())}"
            ) from e
        width = clearance_hole_diameter - self.thread_diameter + self.screw_data["dk"]

        with BuildSketch(Plane.XZ) as profile:
            Rectangle(width / 2, self.screw_data["k"], align=Align.MIN)
        return profile.sketch.face()


class ButtonHeadScrew(Screw):
    """Button Head Screw

    ISO 7380-1 defines hexagon socket button head screws, characterized by a low-profile, rounded
    head and an internal hex drive. These screws are designed for applications requiring a smooth,
    finished appearance with moderate strength. The large head diameter provides a greater bearing
    surface, reducing the risk of pull-through and improving load distribution on softer materials.

    Button head screws are commonly used in enclosures, furniture, robotics, and lightweight mechanical
    assemblies where aesthetics and compact form factor are important. The internal hex socket allows
    for easy installation with standard hex keys, and their shallow head height makes them well-suited
    for space-constrained applications. However, they are not intended for high-torque or high-strength
    applications due to their smaller head-to-shank transition area.

    Args:
        size (str): size specification, e.g. "M6-1"
        length (float): screw length
        fastener_type (Literal["iso7380_1"], optional): Defaults to "iso7380_1".
            iso7380_1 - Hexagon socket button head screws
            hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment. Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv("button_head_parameters.csv")

    def __init__(
        self,
        size: str,
        length: float,
        fastener_type: Literal["iso7380_1"] = "iso7380_1",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(
            size,
            length,
            fastener_type,
            hand,
            simple,
            rotation=rotation,
            align=align,
            mode=mode,
        )

    def head_profile(self) -> Face:
        """Create 2D profile of button head screws"""
        (dk, dl, k, rf) = (self.screw_data[p] for p in ["dk", "dl", "k", "rf"])

        with BuildSketch(Plane.XZ) as profile:
            with BuildLine():
                l1 = Polyline((0, 0), (0, k), (dl / 2, k))
                l2 = RadiusArc(l1 @ 1, (dk / 2, 0), rf)
                Line(l2 @ 1, l1 @ 0)
            make_face()

        return profile.sketch.face()

    head_recess = Screw.default_head_recess

    countersink_profile = Screw.default_countersink_profile


class ButtonHeadWithCollarScrew(Screw):
    """Button Head With Collar Screw

    ISO 7380-2 defines hexagon socket button head screws with an integrated collar or washer face
    beneath the head. This collar increases the bearing surface area, improving load distribution and
    reducing surface deformation when fastening into softer materials. Compared to standard button
    head screws (ISO 7380-1), the collar also adds stability and reduces the risk of loosening due to
    vibration.

    These screws retain the low-profile, rounded aesthetic of button head designs while providing
    enhanced performance in critical applications. They are ideal for assemblies in robotics, consumer
    electronics, machinery panels, and enclosures where a smooth finish and added clamping force are
    needed. The internal hex drive allows for easy and secure installation using standard hex keys.

    Args:
        size (str): size specification, e.g. "M6-1"
        length (float): screw length
        fastener_type (Literal["iso7380_2"], optional): Defaults to "iso7380_2".
            iso7380_2 - Hexagon socket button head screws with collar
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment.
            Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv(
        "button_head_with_collar_parameters.csv"
    )

    def __init__(
        self,
        size: str,
        length: float,
        fastener_type: Literal["iso7380_2"] = "iso7380_2",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(
            size,
            length,
            fastener_type,
            hand,
            simple,
            rotation=rotation,
            align=align,
            mode=mode,
        )

    def head_profile(self) -> Face:
        """Create 2D profile of button head screws with collar"""
        (dk, dl, dc, k, rf, c) = (
            self.screw_data[p] for p in ["dk", "dl", "dc", "k", "rf", "c"]
        )
        with BuildSketch(Plane.XZ) as profile:
            with BuildLine():
                Polyline((0, 0), (0, k), (dl / 2, k))
                RadiusArc((dl / 2, k), (dk / 2, c), rf)
                Line((dk / 2, c), (dc / 2 - c / 2, c))
                JernArc((dc / 2 - c / 2, c), (1, 0), c / 2, -180)
                Line((dc / 2 - c / 2, 0), (0, 0))
            make_face()
        return profile.sketch.face()

    head_recess = Screw.default_head_recess

    def countersink_profile(self, fit: Literal["Close", "Normal", "Loose"]) -> Face:
        """A simple rectangle with gets revolved into a cylinder"""
        try:
            clearance_hole_diameter = self.clearance_hole_diameters[fit]
        except KeyError as e:
            raise ValueError(
                f"{fit} invalid, must be one of {list(self.clearance_hole_diameters.keys())}"
            ) from e
        width = clearance_hole_diameter - self.thread_diameter + self.screw_data["dc"]
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(width / 2, self.screw_data["k"], align=Align.MIN)
        return profile.sketch.face()


class CheeseHeadScrew(Screw):
    """Cheese Head Screw

    Cheese head screws are cylindrical-head fasteners with vertical sides and a flat top, offering a
    clean, compact profile. The head has a smaller diameter and taller profile than pan or button head
    screws, providing a deep drive socket or slot for strong torque transmission. These screws are
    commonly used where head space is limited or where components are recessed into counterbores.

    Multiple ISO standards define variations:
    - ISO 1207: Slotted cheese head machine screws for general applications.
    - ISO 7048: Cross-recessed (Phillips) cheese head screws.
    - ISO 14580: Hex socket cheese head screws, often used in precision assemblies.

    Cheese head screws are widely used in electrical components, enclosures, and machinery where a tall
    head is acceptable but a compact footprint is desired. Their straight vertical sides also make them
    ideal for components that require precise guidance or centering in assembly features.

    Args:
        size (str): size specification, e.g. "M6-1"
        length (float): screw length
        fastener_type (Literal["iso1207", "iso7048", "iso14580"], optional):
            Defaults to "iso7048".
            iso1207 - Slotted cheese head screws
            iso7048 - Cross-recessed cheese head screws
            iso14580 - Hexalobular socket cheese head screws
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment.
            Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv("cheese_head_parameters.csv")

    def __init__(
        self,
        size: str,
        length: float,
        fastener_type: Literal["iso1207", "iso7048", "iso14580"] = "iso7048",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(
            size,
            length,
            fastener_type,
            hand,
            simple,
            rotation=rotation,
            align=align,
            mode=mode,
        )

    def head_profile(self) -> Face:
        """cheese head screws"""
        (k, dk) = (self.screw_data[p] for p in ["k", "dk"])
        with BuildSketch(Plane.XZ) as profile:
            Trapezoid(dk, k, 90 - 5, align=(Align.CENTER, Align.MIN))
            fillet(profile.vertices().group_by(Axis.Z)[-1], k * 0.25)
            split(bisect_by=Plane.YZ)

        return profile.sketch.face()

    head_recess = Screw.default_head_recess

    countersink_profile = Screw.default_countersink_profile


class CounterSunkScrew(Screw):
    """CounterSunk Screw

    Countersunk screws are flat-head fasteners designed to sit flush with or below the surface of the
    material they are installed into. The conical underside of the head matches a countersunk hole,
    allowing for a clean finish and reduced interference in assembled products. These screws are used
    in applications where appearance, clearance, or aerodynamics are important, such as in enclosures,
    electronics, automotive panels, and structural components.

    Multiple ISO standards define specific variations:
    - ISO 2009: Slotted countersunk head screws.
    - ISO 7046: Cross-recessed (Phillips) countersunk screws for general use.
    - ISO 10642: Hex socket countersunk screws, often used in machinery and precision equipment.
    - ISO 14581: Low-profile, cross-recessed countersunk screws for space-constrained applications.
    - ISO 14582: Hex socket, low-profile countersunk screws for compact, high-strength fastening.

    The variety of head heights and drive types enables countersunk screws to meet the aesthetic,
    mechanical, and space requirements of a wide range of assemblies.

    Args:
        size (str): size specification, e.g. "M6-1"
        length (float): screw length
        fastener_type (Literal[ "iso2009", "iso7046", "iso10642", "iso14581", "iso14582"], optional):
            Defaults to "iso10642".
            iso2009 - Slotted countersunk head screws
            iso7046 - Cross recessed countersunk flat head screws
            iso10642 - Hexagon socket countersunk head cap screws
            iso14581 - Hexalobular socket countersunk flat head screws
            iso14582 - Hexalobular socket countersunk flat head screws, high head
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment.
            Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.

    """

    fastener_data = read_fastener_parameters_from_csv("countersunk_head_parameters.csv")

    def __init__(
        self,
        size: str,
        length: float,
        fastener_type: Literal[
            "iso2009", "iso7046", "iso10642", "iso14581", "iso14582"
        ] = "iso10642",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(
            size,
            length,
            fastener_type,
            hand,
            simple,
            rotation=rotation,
            align=align,
            mode=mode,
        )

    def length_offset(self):
        """Countersunk screws include the head in the total length"""
        return self.screw_data["k"]

    def head_profile(self) -> Face:
        """Create 2D profile of countersunk screw heads"""
        (a, k, dk) = (self.screw_data[p] for p in ["a", "k", "dk"])
        with BuildSketch(Plane.XZ) as profile:
            Trapezoid(dk, k, 90 - a / 2, align=(Align.CENTER, Align.MAX), rotation=180)
            fillet(profile.vertices().group_by(Axis.Y)[-1], k * 0.075)
            split(bisect_by=Plane.YZ)
        return profile.sketch.face()

    head_recess = Screw.default_head_recess

    def countersink_profile(self, fit: Literal["Close", "Normal", "Loose"]) -> Face:
        """Create 2D profile of countersink profile"""
        (a, dk, k) = (self.screw_data[p] for p in ["a", "dk", "k"])
        with BuildSketch(Plane.XZ) as profile:
            Trapezoid(dk, k, 90 - a / 2, align=(Align.CENTER, Align.MIN), rotation=180)
            split(bisect_by=Plane.YZ)
        return profile.sketch.face()


class HexHeadScrew(Screw):
    """Hex Head Screw

    Hex head screws, also referred to as hex bolts or hex cap screws, are externally threaded fasteners
    with a six-sided head designed for use with wrenches or sockets. They are widely used in
    construction, machinery, automotive, and industrial applications where strong, reliable bolted joints
    are required.

    Two main ISO standards define their dimensional properties:
    - ISO 4014: Hex head screws with a partially threaded shank, typically used where shear strength is
    needed along the unthreaded portion.
    - ISO 4017: Fully threaded hex head screws, used for general-purpose fastening where full thread
    engagement is desired.

    These screws are available in a range of material grades and finishes, and are often used with
    corresponding hex nuts and washers to ensure uniform clamping force and load distribution. Their
    standardized geometry ensures compatibility with automated assembly tools and industry-standard hardware.

    Args:
        size (str): size specification, e.g. "M6-1"
        length (float): screw length
        fastener_type (Literal["iso4014", "iso4017"], optional): Defaults to "iso4014".
            iso4014 - Hexagon head bolt
            iso4017 - Hexagon head screws
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment.
            Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv("hex_head_parameters.csv")

    def __init__(
        self,
        size: str,
        length: float,
        fastener_type: Literal["iso4014", "iso4017"] = "iso4014",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(
            size,
            length,
            fastener_type,
            hand,
            simple,
            rotation=rotation,
            align=align,
            mode=mode,
        )

    def head_profile(self) -> Face:
        """Create 2D profile of hex head screws"""
        (k, s) = (self.screw_data[p] for p in ["k", "s"])
        e = polygon_diagonal(s, 6)
        # Chamfer angle must be between 15 and 30 degrees
        cs = (e - s) * tan(radians(15)) / 2
        with BuildSketch(Plane.XZ) as profile:
            Polygon(
                (0, 0),
                (e / 2, 0),
                (e / 2, k - cs),
                (s / 2, k),
                (0, k),
                (0, 0),
                align=None,
            )
        return profile.sketch.face()

    def head_plan(self) -> Face:
        """Create a hexagon solid"""
        with BuildSketch() as plan:
            RegularPolygon(self.screw_data["s"] / 2, 6, major_radius=False)
        return plan.sketch.face()

    def countersink_profile(self, fit: Literal["Close", "Normal", "Loose"]) -> Face:
        """A simple rectangle with gets revolved into a cylinder with an
        extra socket_clearance (defaults to 6mm across the diameter) for a socket wrench
        """
        # Note that fit isn't used but remains for uniformity in the workplane hole methods
        del fit
        (k, s) = (self.screw_data[p] for p in ["k", "s"])
        e = polygon_diagonal(s, 6)
        width = e + self.socket_clearance + e
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(width / 2, k, align=Align.MIN)
        return profile.sketch.face()


class HexHeadWithFlangeScrew(Screw):
    """Hex Head With Flange Screw

    Hex head screws with flanges combine a standard hexagonal head with an integrated washer-like
    flange at the base. The flange increases the bearing surface area under the head, distributing
    clamping forces more evenly and reducing surface damage to the assembled material. This design
    also improves resistance to loosening caused by vibration, especially when used without a separate
    washer.

    DIN 1662 and DIN 1665 define common types of flanged hex screws:
    - DIN 1662: Hex flange screws with a partially threaded shank.
    - DIN 1665: Hex flange screws that are fully threaded, offering continuous engagement over the
    entire shaft.

    These screws are frequently used in automotive, structural, and industrial applications where
    secure fastening, reduced part count, and simplified assembly are important. The integrated flange
    simplifies the design and assembly process by eliminating the need for a separate washer while
    enhancing load distribution.

    Args:
        size (str): size specification, e.g. "M6-1"
        length (float): screw length
        fastener_type (Literal["din1662", "din1665"], optional): Defaults to "din1662".
            din1662 - Hexagon bolts with flange small series
            din1665 - Hexagon head bolts with flange

        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment.
            Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv(
        "hex_head_with_flange_parameters.csv"
    )

    def __init__(
        self,
        size: str,
        length: float,
        fastener_type: Literal["din1662", "din1665"] = "din1662",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(
            size,
            length,
            fastener_type,
            hand,
            simple,
            rotation=rotation,
            align=align,
            mode=mode,
        )

    head_profile = HexHeadScrew.head_profile
    head_plan = HexHeadScrew.head_plan

    def flange_profile(self) -> Face:
        """Flange for hexagon Bolts"""
        (dc, c) = (self.screw_data[p] for p in ["dc", "c"])
        flange_angle = 25
        tangent_point = Vector(
            (c / 2) * cos(radians(90 - flange_angle)),
            (c / 2) * sin(radians(90 - flange_angle)),
        ) + Vector((dc - c) / 2, c / 2)
        with BuildSketch(Plane.XZ) as profile:
            with BuildLine():
                l1 = Line((0, 0), (dc / 2 - c / 2, 0))
                RadiusArc(l1 @ 1, tangent_point, -c / 2)
                l3 = PolarLine(tangent_point, dc / 2 - c / 2, 180 - flange_angle)
                Polyline(l3 @ 1, (0, (l3 @ 1).Y), (0, 0))
            make_face()
        return profile.sketch.face()

    def countersink_profile(self, fit: Literal["Close", "Normal", "Loose"]) -> Face:
        """A simple rectangle with gets revolved into a cylinder with
        at least socket_clearance (default 6mm across the diameter) for a socket wrench
        """
        try:
            clearance_hole_diameter = self.clearance_hole_diameters[fit]
        except KeyError as e:
            raise ValueError(
                f"{fit} invalid, must be one of {list(self.clearance_hole_diameters.keys())}"
            ) from e
        (dc, s, k) = (self.screw_data[p] for p in ["dc", "s", "k"])
        shaft_clearance = clearance_hole_diameter - self.thread_diameter
        width = max(
            dc + shaft_clearance, polygon_diagonal(s, 6) + self.socket_clearance
        )
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(width / 2, k, align=Align.MIN)
        return profile.sketch.face()


class PanHeadScrew(Screw):
    """Pan Head Screw

    Pan head screws feature a broad, low-profile head with gently curved sides and a flat bearing
    surface underneath. This shape provides a large contact area, reducing the likelihood of damage
    to the fastened material and allowing for a clean, finished appearance. The rounded sides offer a
    smoother look than hex or cheese heads while still accommodating a variety of drive types.

    Several standards define pan head screws:
    - ISO 1580: Slotted pan head machine screws for general mechanical use.
    - ISO 14583: Pan head screws with a hexalobular (Torx) drive for improved torque transfer and
    reduced cam-out.
    - ASME B18.6.3: The U.S. standard for slotted, cross-recessed (Phillips), or combination-drive
    pan head machine screws.

    Pan head screws are commonly used in enclosures, electronics, mechanical assemblies, and
    applications where aesthetics, low head height, and easy access are important. Their wide head
    allows for secure fastening without requiring countersinking or additional washers.

    Args:
        size (str): size specification, e.g. "M6-1"
        length (float): screw length
        fastener_type (Literal["iso1580", "iso14583", "asme_b_18.6.3"], optional):
            Defaults to "iso14583".
            iso1580 - Slotted pan head screws
            iso14583 - Hexalobular socket pan head screws
            asme_b_18.6.3 - Type 1 Cross Recessed Pan Head Machine Screws
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment.
            Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv("pan_head_parameters.csv")

    def __init__(
        self,
        size: str,
        length: float,
        fastener_type: Literal["iso1580", "iso14583", "asme_b_18.6.3"] = "iso14583",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(
            size,
            length,
            fastener_type,
            hand,
            simple,
            rotation=rotation,
            align=align,
            mode=mode,
        )

    def head_profile(self) -> Face:
        """Slotted pan head screws"""
        (k, dk) = (self.screw_data[p] for p in ["k", "dk"])
        with BuildSketch(Plane.XZ) as profile:
            with BuildLine():
                l1 = Line((0, 0), (dk / 2, 0))
                l2 = Spline(
                    l1 @ 1,
                    (dk * 0.25, k),
                    tangents=[(-sin(radians(5)), cos(radians(5))), (-1, 0)],
                )
                Polyline(l2 @ 1, (0, (l2 @ 1).Y), (0, 0))
            make_face()
        return profile.sketch.face()

    head_recess = Screw.default_head_recess
    countersink_profile = Screw.default_countersink_profile


class PanHeadWithCollarScrew(Screw):
    """Pan Head With Collar Screw

    DIN 967 defines a pan head screw with an integrated collar or washer-like flange beneath the head.
    The collar increases the bearing surface area, improving load distribution and reducing surface
    indentation on the clamped material. The pan head retains a low-profile, rounded appearance,
    while the collar eliminates the need for a separate washer in many applications.

    These screws typically feature a slotted or cross-recessed (Phillips) drive and are widely used
    in automotive, appliance, and light mechanical assemblies where compactness, aesthetics, and
    vibration resistance are important. The combination of pan head geometry and an integral flange
    makes them especially useful when fastening to softer materials such as plastics or thin sheet metal.

    Args:
        size (str): size specification, e.g. "M6-1"
        length (float): screw length
        fastener_type (Literal["din967"], optional): Defaults to "din967".
            din967 - Cross recessed pan head screws with collar
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment.
            Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv(
        "pan_head_with_collar_parameters.csv"
    )

    def __init__(
        self,
        size: str,
        length: float,
        fastener_type: Literal["din967"] = "din967",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(
            size,
            length,
            fastener_type,
            hand,
            simple,
            rotation=rotation,
            align=align,
            mode=mode,
        )

    def head_profile(self) -> Face:
        """Cross recessed pan head screws with collar"""
        (rf, k, dk, c) = (self.screw_data[p] for p in ["rf", "k", "dk", "c"])

        flat = sqrt(k - c) * sqrt(2 * rf - (k - c))
        with BuildSketch(Plane.XZ) as profile:
            with BuildLine():
                Polyline((0, 0), (dk / 2, 0), (dk / 2, c), (flat, c))
                RadiusArc((flat, c), (0, k), -rf)
                Line((0, k), (0, 0))
            make_face()
        return profile.sketch.face()

    head_recess = Screw.default_head_recess

    countersink_profile = Screw.default_countersink_profile


class RaisedCheeseHeadScrew(Screw):
    """Raised Cheese Head Screw

    ISO 7045 defines raised cheese head screws with a cylindrical, slightly domed head and a flat
    underside. These screws combine the deep drive engagement and tall profile of standard cheese head
    screws with a subtle domed surface for improved aesthetics and reduced edge sharpness. The result
    is a screw that offers high torque capability while maintaining a more refined appearance.

    Raised cheese head screws are typically available with slotted or cross-recessed (Phillips) drives,
    and are used in mechanical assemblies, consumer electronics, and enclosures where clearance is
    limited but drive reliability is important. The tall head allows for secure tool engagement, while
    the rounded top helps reduce snagging and cosmetic impact in visible assemblies.

    Args:
        size (str): size specification, e.g. "M6-1"
        length (float): screw length
        fastener_type (Literal["iso7045"], optional): Defaults to "iso7045".
            iso7045 - Cross recessed raised cheese head screws
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment.
            Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv(
        "raised_cheese_head_parameters.csv"
    )

    def __init__(
        self,
        size: str,
        length: float,
        fastener_type: Literal["iso7045"] = "iso7045",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(
            size,
            length,
            fastener_type,
            hand,
            simple,
            rotation=rotation,
            align=align,
            mode=mode,
        )

    def head_profile(self) -> Face:
        """raised cheese head screws"""
        (dk, k, rf) = (self.screw_data[p] for p in ["dk", "k", "rf"])
        oval_height = rf - sqrt(4 * rf**2 - dk**2) / 2
        with BuildSketch(Plane.XZ) as profile:
            with BuildLine():
                Line((0, 0), (0, k))
                RadiusArc((0, k), (dk / 2, k - oval_height), rf)
                Polyline((dk / 2, k - oval_height), (dk / 2, 0), (0, 0))
            make_face()

        return profile.sketch.face()

    head_recess = Screw.default_head_recess

    countersink_profile = Screw.default_countersink_profile


class RaisedCounterSunkOvalHeadScrew(Screw):
    """Raised CounterSunk Oval Head Screw

    Raised countersunk screws—also known as oval head screws—feature a conical bearing surface like
    standard countersunk screws, but with a gently domed top. This combination provides a flush fit
    with a slightly protruding decorative finish, making them suitable for applications where appearance
    and smooth contours are important.

    Multiple ISO standards define oval head screws with different drive types:
    - ISO 2010: Slotted raised countersunk head screws for general-purpose use.
    - ISO 7047: Cross-recessed (Phillips) version for improved alignment and automation.
    - ISO 14584: Hexalobular (Torx) drive version for high torque applications with reduced cam-out.

    These screws are commonly used in electronics, appliance housings, mechanical assemblies, and
    consumer products where flush mounting is required but a low-profile dome provides a more refined
    look and reduced snagging.

    Args:
        size (str): size specification, e.g. "M6-1"
        length (float): screw length
        fastener_type (Literal["iso2010", "iso7047", "iso14584"], optional):
            Defaults to "iso14584".
            iso2010 - Slotted raised countersunk oval head screws
            iso7047 - Cross recessed raised countersunk head screws
            iso14584 - Hexalobular socket raised countersunk head screws
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment.
            Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv(
        "raised_countersunk_oval_head_parameters.csv"
    )

    def __init__(
        self,
        size: str,
        length: float,
        fastener_type: Literal["iso2010", "iso7047", "iso14584"] = "iso14584",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(
            size,
            length,
            fastener_type,
            hand,
            simple,
            rotation=rotation,
            align=align,
            mode=mode,
        )

    def length_offset(self):
        """Raised countersunk oval head screws include the head but not oval
        in the total length"""
        return self.screw_data["k"]

    def head_profile(self):
        """raised countersunk oval head screws"""
        (a, k, rf, dk) = (self.screw_data[p] for p in ["a", "k", "rf", "dk"])
        side_length = k / cos(radians(a / 2))
        oval_height = rf - sqrt(4 * rf**2 - dk**2) / 2
        with BuildSketch(Plane.XZ) as profile:
            with BuildLine():
                l1 = Line((0, 0), (0, k + oval_height))
                l2 = RadiusArc(l1 @ 1, (dk / 2, k), rf)
                l3 = PolarLine(l2 @ 1, side_length, -90 - a / 2)
                Line(l3 @ 1, (0, 0))
            make_face()
            fillet(
                profile.vertices().group_by(Axis.Z)[-1].sort_by(Axis.X)[-1], k * 0.075
            )
        return profile.sketch.face()

    head_recess = Screw.default_head_recess

    def countersink_profile(self, fit: Literal["Close", "Normal", "Loose"]) -> Face:
        """A flat bottomed cone"""
        (a, k, dk) = (self.screw_data[p] for p in ["a", "k", "dk"])
        side_length = k / cos(radians(a / 2))

        with BuildSketch(Plane.XZ) as profile:
            with BuildLine():
                l1 = Polyline((0, 0), (0, k), (dk / 2, k))
                l2 = PolarLine(l1 @ 1, side_length, -90 - a / 2)
                Line(l2 @ 1, (0, 0))
            make_face()
        return profile.sketch.face()


class SetScrew(Screw):
    """Set Screw

    ISO 4026 defines set screws with a flat point and a hexagon socket drive. These screws are fully
    threaded and lack a head, allowing them to sit flush or recessed within a mating part. Set screws
    are primarily used to secure one component against another—most commonly to fix a rotating part
    such as a gear or pulley onto a shaft.

    The flat point provides secure contact without damaging the mating surface, making it ideal for
    use in applications where frequent adjustments or disassembly may be required. Set screws are
    commonly used in mechanical assemblies, couplings, collars, and linkages where space is limited
    and unobtrusive fastening is essential.

    Args:
        size (str): size specification, e.g. "M6-1"
        length (float): screw length
        fastener_type (Literal["iso4026"], optional): Defaults to "iso4026".
            iso4026 - Hexagon socket set screws with flat point
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment. Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv("setscrew_parameters.csv")

    def __init__(
        self,
        size: str,
        length: float,
        fastener_type: Literal["iso4026"] = "iso4026",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(
            size,
            length,
            fastener_type,
            hand,
            simple,
            rotation=rotation,
            align=align,
            mode=mode,
        )

    def custom_make(self):
        """Setscrews are custom builds"""
        return self.make_setscrew()

    def make_setscrew(self) -> Solid:
        """Construct set screw shape"""

        (s, t) = (self.screw_data[p] for p in ["s", "t"])

        thread = IsoThread(
            major_diameter=self.thread_diameter * 1,
            pitch=self.thread_pitch,
            length=self.length,
            external=True,
            end_finishes=("fade", "fade"),
            hand=self.hand,
            simple=self.simple,
        )
        with BuildPart() as screw:
            # Core
            Cylinder(
                thread.min_radius,
                self.length,
                align=(Align.CENTER, Align.CENTER, Align.MAX),
            )
            # if not self.simple:
            #     with Locations((0, 0, -self.length)):
            #         add(thread)

            # Recess
            with BuildSketch():
                RegularPolygon(s / 2, 6, major_radius=False)
            extrude(amount=-t, mode=Mode.SUBTRACT)

        return screw.part.solid()

    def make_head(self):
        """There is no head on a setscrew"""
        return None

    def countersink_profile(self, fit):
        """There is no head on a setscrew"""
        return None


class SocketHeadCapScrew(Screw):
    """Socket Head Cap Screw

    Socket head cap screws are high-strength fasteners with a cylindrical head and an internal
    hexagonal drive. Designed for use where external wrench clearance is limited, these screws are
    tightened with a hex key (Allen wrench) and provide excellent torque transfer and holding power.
    The tall head allows for deep socket engagement, reducing the risk of stripping.

    - ISO 4762 specifies metric socket head cap screws for general and precision mechanical use.
    - ASME B18.3 defines the inch-based counterpart, widely used in North American engineering standards.

    Socket head cap screws are commonly used in machinery, robotics, automotive assemblies, and
    structural applications where compactness and reliability are important. Their strong clamping force
    and clean geometry make them ideal for pre-tapped holes and locations with tight access.

    Args:
        size (str): size specification, e.g. "M6-1"
        length (float): screw length
        fastener_type (Literal["iso4762","asme_b18.3"], optional): Defaults to "iso4762".
            iso4762 - Hexagon socket head cap screws
            asme_b18.3 - Imperial hexagon socket head cap screws
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment. Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv("socket_head_cap_parameters.csv")

    def __init__(
        self,
        size: str,
        length: float,
        fastener_type: Literal["iso4762", "asme_b18.3"] = "iso4762",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(
            size,
            length,
            fastener_type,
            hand,
            simple,
            rotation=rotation,
            align=align,
            mode=mode,
        )

    def head_profile(self):
        """Socket Head Cap Screws"""
        (dk, k) = (self.screw_data[p] for p in ["dk", "k"])
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(dk / 2, k, align=Align.MIN)
            fillet(
                profile.vertices().group_by(Axis.Y)[-1].sort_by(Axis.X)[-1], k * 0.075
            )
        return profile.sketch.face()

    head_recess = Screw.default_head_recess

    countersink_profile = Screw.default_countersink_profile


class LowProfileScrew(Screw):
    """Low Profile Screw

    Low profile screws are specialized fasteners designed with a wide, flat, and shallow head that
    minimizes protrusion above the mating surface. These screws are commonly used in aluminum
    extrusion-based assemblies—such as those built with OpenBuilds V-slot and C-beam systems—where
    clearance is limited and flush mounting is desired.

    The large diameter head offers generous bearing area and good load distribution, while the low
    height ensures smooth movement of linear components and avoids interference with adjacent parts.
    These screws typically feature an internal hex drive and come in standard metric thread sizes (e.g., M5).

    Low profile screws are ideal for use in DIY CNC machines, 3D printers, linear motion assemblies,
    and other modular hardware systems where both mechanical performance and compactness are essential.

    Args:
        size (str): size specification, e.g. "M5-0.8"
        length (float): screw length
        fastener_type (Literal["OpenBuilds"], optional): Defaults to "OpenBuilds".
            OpenBuilds - OpenBuilds custom low profile socket head cap screw
        hand (Literal["right","left"], optional): thread direction. Defaults to "right".
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment. Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv("low_profile_parameters.csv")

    def __init__(
        self,
        size: str,
        length: float,
        fastener_type: Literal["OpenBuilds"] = "OpenBuilds",
        hand: Literal["right", "left"] = "right",
        simple: bool = True,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(
            size,
            length,
            fastener_type,
            hand,
            simple,
            rotation=rotation,
            align=align,
            mode=mode,
        )

    def head_profile(self):
        """Low Profile Screws"""
        (dk, k) = (self.screw_data[p] for p in ["dk", "k"])
        with BuildSketch(Plane.XZ) as profile:
            SlotOverall(dk, 2)
            Rectangle(dk, k, mode=Mode.INTERSECT)
            split(bisect_by=Plane.YZ)
        return profile.sketch.face().move(Pos(0, 0, k / 2))

    head_recess = Screw.default_head_recess

    countersink_profile = Screw.default_countersink_profile


class Washer(ABC, BasePartObject):
    """Parametric Washer

    Base class used to create standard washers

    Args:
        size (str): standard sizes - e.g. "M6"
        fastener_type (str): type identifier - e.g. "iso4032"

    Raises:
        ValueError: invalid fastener_type
        ValueError: invalid size

    Each washer instance creates a set of properties that provide the Solid CAD object
    as well as valuable parameters, as follows (values intended for internal use are not shown):

    """

    _applies_to = [BuildPart._tag]

    # Read clearance and tap hole dimesions tables
    # Close, Normal, Loose
    clearance_hole_drill_sizes = read_fastener_parameters_from_csv(
        "clearance_hole_sizes.csv"
    )
    clearance_hole_data = lookup_drill_diameters(clearance_hole_drill_sizes)

    @property
    def clearance_hole_diameters(self):
        """A dictionary of drill diameters for clearance holes"""
        try:
            return self.clearance_hole_data[self.thread_size.split("-")[0]]
        except KeyError as e:
            raise ValueError(
                f"No clearance hole data for size {self.thread_size}"
            ) from e

    @property
    @abstractmethod
    def fastener_data(cls):  # pragma: no cover
        """Each derived class must provide a fastener_data dictionary"""
        return NotImplementedError

    @abstractmethod
    def washer_profile(self) -> Face:  # pragma: no cover
        """Each derived class must provide the profile of the washer"""
        return NotImplementedError

    @property
    def info(self):
        """Return identifying information"""
        return f"{self.washer_class}({self.fastener_type}): {self.thread_size}"

    @property
    def washer_class(self):
        """Which derived class created this washer"""
        return type(self).__name__

    @classmethod
    def types(cls) -> list[str]:
        """Return a set of the washer types"""
        return set(p.split(":")[0] for p in list(cls.fastener_data.values())[0].keys())

    @classmethod
    def sizes(cls, fastener_type: str) -> list[str]:
        """Return a list of the washer sizes for the given type"""
        return list(isolate_fastener_type(fastener_type, cls.fastener_data).keys())

    @classmethod
    def select_by_size(cls, size: str) -> dict:
        """Return a dictionary of list of fastener types of this size"""
        return select_by_size_fn(cls, size)

    @property
    def washer_thickness(self) -> float:
        """Calculate the maximum thickness of the washer"""
        return self.bounding_box().size.Z

    @property
    def washer_diameter(self):
        """Calculate the maximum diameter of the washer"""
        radii = [(Vector(0, 0, v.Z) - Vector(v)).length for v in self.vertices()]
        return 2 * max(radii)

    def __init__(
        self,
        size: str,
        fastener_type: str,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        self.hole_locations: list[Location] = []  #: custom holes locations
        self.washer_size = size
        self.thread_size = size
        self.is_metric = self.thread_size[0] == "M"

        # Used only for clearance gap calculations
        if self.is_metric:
            self.thread_diameter = float(size[1:])
        else:
            self.thread_diameter = imperial_str_to_float(size)

        if fastener_type not in self.types():
            raise ValueError(f"{fastener_type} invalid, must be one of {self.types()}")
        self.fastener_type = fastener_type
        try:
            self.washer_data = evaluate_parameter_dict(
                isolate_fastener_type(self.fastener_type, self.fastener_data)[
                    self.thread_size
                ],
                is_metric=self.is_metric,
            )
        except KeyError as e:
            raise ValueError(
                f"{size} invalid, must be one of {self.sizes(self.fastener_type)}"
            ) from e
        bd_object = self.make_washer()

        super().__init__(bd_object, rotation, align, mode)
        self.label = f"{self.__class__.__name__}({size}, {fastener_type})"
        self.color = Color(0xC0C0C0)

    def make_washer(self) -> Solid:
        """Create a screw head from the 2D shapes defined in the derived class"""

        # Create the basic washer shape
        # pylint: disable=no-member
        return revolve(self.washer_profile()).solid()

    def default_washer_profile(self) -> Face:
        """Create 2D profile of hex washers with double chamfers"""
        (d1, d2, h) = (self.washer_data[p] for p in ["d1", "d2", "h"])
        with BuildSketch(Plane.XZ) as profile:
            with Locations((d1 / 2, 0)):
                Rectangle((d2 - d1) / 2, h, align=Align.MIN)
        return profile.sketch.face()

    def default_countersink_profile(
        self, fit: Literal["Close", "Normal", "Loose"]
    ) -> Face:
        """A simple rectangle with gets revolved into a cylinder"""
        try:
            clearance_hole_diameter = self.clearance_hole_diameters[fit]
        except KeyError as e:
            raise ValueError(
                f"{fit} invalid, must be one of {list(self.clearance_hole_diameters.keys())}"
            ) from e
        gap = clearance_hole_diameter - self.thread_diameter
        (d2, h) = (self.washer_data[p] for p in ["d2", "h"])
        with BuildSketch(Plane.XZ) as profile:
            Rectangle(d2 / 2 + gap, h, align=Align.MIN)
        return profile.sketch.face()


class PlainWasher(Washer):
    """Plain Washer

    Plain washers are flat, disc-shaped components used under the head of a screw or nut to distribute
    the clamping load and protect the mating surface from damage. They also help reduce surface
    deformation and prevent fasteners from loosening due to vibration or movement.

    Several ISO standards define plain washers of different series:
    - ISO 7089: Normal series washers with standard outer diameter and thickness.
    - ISO 7091: Normal series washers with slightly tighter tolerances and more controlled flatness.
    - ISO 7093: Large series washers with greater outer diameter for use with oversized or slotted holes.
    - ISO 7094: Extra-large series washers, offering the greatest surface area and ideal for use with
    soft materials or wide clearances.

    These washers are used in nearly all types of bolted assemblies across mechanical, structural,
    automotive, and industrial applications.

    Args:
        size (str): size specification, e.g. "M6"
        fastener_type (Literal["iso7089", "iso7091", "iso7093", "iso7094"]):
            iso7089 - Plain washers, Form A
            iso7091 - Plain washers
            iso7093 - Plain washers — Large series
            iso7094 - Plain washers - Extra large series
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment. Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    def __init__(
        self,
        size: str,
        fastener_type: Literal["iso7089", "iso7091", "iso7093", "iso7094"],
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(size, fastener_type, rotation, align, mode)

    fastener_data = read_fastener_parameters_from_csv("plain_washer_parameters.csv")
    washer_profile = Washer.default_washer_profile
    countersink_profile = Washer.default_countersink_profile


class ChamferedWasher(Washer):
    """Chamfered Washer

    ISO 7090 defines chamfered washers, which are plain washers with a conical or beveled underside
    designed to match the chamfer on fasteners such as countersunk or chamfered-head bolts. The chamfer
    provides full surface contact between the washer and fastener head, improving load distribution and
    alignment, especially in high-stress or structural applications.

    These washers help prevent damage to the mating surface by reducing point loading and ensuring
    even contact. They are typically used with screws or bolts that have a 120° chamfer under the head—
    such as ISO 7379 shoulder screws—or in assemblies requiring enhanced axial alignment and bearing
    surface support.

    Chamfered washers are commonly found in heavy machinery, construction, tooling fixtures, and
    high-precision assemblies where joint integrity is critical.

    Args:
        size (str): size specification, e.g. "M6"
        fastener_type (Literal["iso7090"], optional): Defaults to "iso7090".
            iso7090 - Plain washers, Form B
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment. Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv("chamfered_washer_parameters.csv")

    def __init__(
        self,
        size: str,
        fastener_type: Literal["iso7090"] = "iso7090",
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(size, fastener_type, rotation, align, mode)

    def washer_profile(self) -> Face:
        """Create 2D profile of hex washers with double chamfers"""
        (d1, d2, h) = (self.washer_data[p] for p in ["d1", "d2", "h"])
        with BuildSketch(Plane.XZ) as profile:
            with Locations((d1 / 2, 0)):
                Rectangle((d2 - d1) / 2, h, align=Align.MIN)
            chamfer(
                profile.vertices().group_by(Axis.Y)[-1].sort_by(Axis.X)[-1], 0.25 * h
            )
        return profile.sketch.face()

    countersink_profile = Washer.default_countersink_profile


class CheeseHeadWasher(Washer):
    """Cheese Head Washer

    ISO 7092 defines plain washers specifically designed for use with cheese head screws. These washers
    have a reduced outer diameter and a thickness tailored to the narrow, cylindrical profile of cheese
    head fasteners, ensuring proper seating and load distribution under the head without protruding
    beyond its edges.

    Cheese head washers help prevent surface damage, distribute clamping forces more evenly, and improve
    appearance in precision assemblies. Their compact size makes them ideal for use in electronics,
    instrumentation, and machine components where space is limited and a clean, flush appearance is desired.

    These washers are especially useful when paired with ISO 1207 or ISO 14580 cheese head screws in
    counterbored holes or recessed applications.

    Args:
        size (str): size specification, e.g. "M6"
        fastener_type (Literal["iso7092"], optional): Defaults to "iso7092".
            iso7092 - Washers for cheese head screws
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment. Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv(
        "cheese_head_washer_parameters.csv"
    )

    def __init__(
        self,
        size: str,
        fastener_type: Literal["iso7092"] = "iso7092",
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(size, fastener_type, rotation, align, mode)

    def washer_profile(self) -> Face:
        """Create 2D profile of hex washers with double chamfers"""
        (d1, d2, h) = (self.washer_data[p] for p in ["d1", "d2", "h"])
        with BuildSketch(Plane.XZ) as profile:
            with Locations((d1 / 2, 0)):
                Rectangle((d2 - d1) / 2, h, align=Align.MIN)
            chamfer(profile.vertices().group_by(Axis.X)[0], 0.25 * h)
        return profile.sketch.face()

    countersink_profile = Washer.default_countersink_profile


class InternalToothLockWasher(Washer):
    """Internal Tooth Lock Washer

    Internal tooth lock washers are circular washers with multiple sharp, radially inward-facing teeth
    designed to bite into the surface of the mating part and the underside of the fastener head. This
    toothed profile increases friction and provides mechanical resistance to loosening caused by
    vibration or rotation.

    - DIN 6797 defines metric internal tooth lock washers commonly used in precision electrical and
    mechanical assemblies.
    - ASME B18.21.1 provides similar specifications for inch-based applications and general-purpose use.

    Because the teeth are located on the inner circumference, internal tooth lock washers are ideal
    for use under round or pan head screws, where edge clearance is limited or appearance is important.
    They are commonly used in electronics, appliance housings, and light-duty machinery to maintain
    tight assemblies without chemical threadlockers or locking nuts.

    Args:
        size (str): size specification, e.g. "M6"
        fastener_type (Literal["din6797", "asme_b18.21.1"], optional): Defaults to "din6797".
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional): object alignment. Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    fastener_data = read_fastener_parameters_from_csv(
        "internal_tooth_lock_washer_parameters.csv"
    )

    def __init__(
        self,
        size: str,
        fastener_type: Literal["din6797", "asme_b18.21.1"] = "din6797",
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        super().__init__(size, fastener_type, rotation, align, mode)

    def make_washer(self):
        (d1, d2, h) = (self.washer_data[p] for p in ["d1", "d2", "h"])
        n = round(self.washer_data["n"] / (IN if not self.is_metric else MM))

        # tooth outer diameter
        dt = d1 + (d2 - d1) / 2

        # tooth arc angle
        at = ({6: 30, 8: 27, 9: 22.5, 10: 20, 12: 20, 14: 16, 16: 12}).get(n)

        # tooth inner and outer widths
        w1, w2 = (d1 * pi * at / 360, dt * pi * at / 360)

        # solve for angle to rotate inner face of tooth -> overall height == 2*h per DIN 6797
        # +---------+
        # |         | h
        # +---------+
        #      w1
        # ref: https://math.stackexchange.com/questions/213545/solving-trigonometric-equations-of-the-form-a-sin-x-b-cos-x-c
        a, b = w1 / 2, h / 2
        c, d = h, sqrt((w1 / 2) ** 2 + (h / 2) ** 2 - h**2)
        angle = (-atan(d / c) + atan(a / b)) * 180 / pi

        # tooth inner and outer faces pre projection
        f1 = (Rot(Y=angle) * (Plane.XZ * Rectangle(w1, h))).faces()[0]
        f2 = (Plane.XZ * Rectangle(w2, h)).faces()[0]

        return Pos(Z=h / 2) * (
            Cylinder(d2 / 2, h)
            - Cylinder(dt / 2, h, mode=Mode.SUBTRACT)
            + PolarLocations(0, n)
            * loft(
                [
                    f1.project_to_shape(Cylinder(d1 / 2, 10 * h), (0, -1, 0)),
                    f2.project_to_shape(Cylinder(dt / 2, 10 * h), (0, -1, 0)),
                ]
            )
        )

    washer_profile = Washer.default_washer_profile
    countersink_profile = Washer.default_countersink_profile


#
# Holes
#
def _make_fastener_hole(
    hole_diameters: dict,
    fastener: Union[Nut, Screw],
    countersink_profile: Face,
    depth: float,
    fit: Literal["Close", "Normal", "Loose"] = None,
    material: Literal["Soft", "Hard"] = None,
    counter_sunk: bool = True,
    captive_nut: bool = False,
    threaded_hole: bool = False,
    update_hole_locations: bool = False,
) -> Part:
    """_make_fastener_hole

    Makes a counterbore clearance, tap or threaded hole for the given screw for each item
    on the stack. The surface of the hole is at the current workplane.

    Args:
        hole_diameters (dict): either clearance or tap hole diameter specifications
        fastener (Union[Nut, Screw]): A nut or screw instance
        countersink_profile (Face): the 2D side profile of the fastener (not including a
            screw's shaft)
        depth (float): hole depth
        fit (Literal["Close", "Normal", "Loose"], optional): determines clearance hole
            diameter. Defaults to None.
        material (Literal["Soft", "Hard"], optional): determines tap hole size.
            Defaults to None.
        counter_sunk (bool, optional): Is the fastener countersunk into the part?.
            Defaults to True.
        captive_nut (bool, optional): Countersink with a rectangular, filleted, hole..
            Defaults to False.
        threaded_hole (bool, optional): Does the hole have threads. Defaults to False.
        update_hole_locations (bool, optional): If in Builder mode. Defaults to False.

    Raises:
        ValueError: fit or material not in hole_diameters dictionary

    Returns:
        Part: the hole to be subtracted from the base object
    """
    bore_direction = Vector(0, 0, -1)
    origin = Vector(0, 0, 0)

    # Setscrews' countersink_profile is None so check if it exists
    # countersink_profile = fastener.countersink_profile(fit)
    if captive_nut:
        clearance = fastener.clearance_hole_diameters[fit] - fastener.thread_diameter
        head_offset = countersink_profile.vertices().sort_by(Axis.Z)[-1].Z
        if isinstance(fastener, (DomedCapNut, HexNut, UnchamferedHexagonNut)):
            fillet_radius = fastener.nut_diameter / 4
            rect_width = fastener.nut_diameter + clearance
            rect_height = fastener.nut_diameter * math.sin(math.pi / 3) + clearance
        elif isinstance(fastener, SquareNut):
            fillet_radius = fastener.nut_diameter / 8
            rect_height = fastener.nut_diameter * math.sqrt(2) / 2 + clearance
            rect_width = rect_height + 2 * fillet_radius + clearance

        with BuildPart(mode=Mode.PRIVATE) as countersink_cutter_builder:
            with BuildSketch():
                RectangleRounded(rect_width, rect_height, fillet_radius)
            extrude(amount=-head_offset)
        countersink_cutter = countersink_cutter_builder.part

    elif counter_sunk and not countersink_profile is None:
        head_offset = countersink_profile.vertices().sort_by(Axis.Z)[-1].Z
        countersink_cutter = revolve(countersink_profile, mode=Mode.PRIVATE).moved(
            Pos(0, 0, -head_offset)
        )
    else:
        head_offset = 0

    if threaded_hole:
        hole_radius = fastener.thread_diameter / 2
    else:
        key = fit if material is None else material
        try:
            hole_radius = hole_diameters[key] / 2
        except KeyError as e:
            raise ValueError(
                f"{key} invalid, must be one of {list(hole_diameters.keys())}"
            ) from e

    shank_hole = Solid.make_cylinder(
        radius=hole_radius, height=depth, plane=Plane(origin, z_dir=bore_direction)
    )
    if counter_sunk and not countersink_profile is None:
        fastener_hole = countersink_cutter.fuse(shank_hole)
    else:
        fastener_hole = shank_hole

    csk_angle = 180 - 82  # 82 is a common tip angle
    h = hole_radius / math.tan(math.radians(csk_angle / 2.0))
    drill_tip = Solid.make_cone(
        hole_radius, 0.0, h, plane=Plane(bore_direction * depth, z_dir=bore_direction)
    )
    fastener_hole = fastener_hole.fuse(drill_tip)

    # Update the hole location list for this fastener
    # Countersunk screws shouldn't be lowered into the hole
    if isinstance(fastener, (CounterSunkScrew, RaisedCounterSunkOvalHeadScrew)):
        head_offset -= head_offset
    if update_hole_locations:
        fastener.hole_locations.extend(
            [
                location * Pos(0, 0, -head_offset)
                for location in LocationList._get_context().locations
            ]
        )

    return fastener_hole


class ClearanceHole(BasePartObject):
    """Part Object: ClearanceHole

    A clearance hole is a hole that is drilled through one of two (or more) parts to be
    assembled together with a screw or bolt. The diameter of the clearance hole is larger
    than the diameter of the screw or bolt so that it can pass through freely without
    engaging the threads. The purpose of a clearance hole is to ensure that the screw
    or bolt can be tightened into a threaded hole on another part without being obstructed
    by the part it passes through. This allows the head of the screw or bolt to clamp
    the parts together.

    Args:
        fastener (Union[Nut, Screw]): A nut or screw instance
        fit (Optional[Literal["Close", "Normal", "Loose"]], optional): Control hole diameter.
            Defaults to "Normal".
        depth (float, optional): hole depth - None implies through part. Defaults to None.
        counter_sunk (bool, optional): Is the fastener countersunk into the part?.
            Defaults to True.
        captive_nut (bool, optional): Is rotation of the nut disabled?. Defaults to False.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        mode (Mode, optional): combination mode. Defaults to Mode.SUBTRACT.

    Raises:
        ValueError: Use InsertHole for HeatSetNut
        ValueError: Invalid nut given
        ValueError: No depth provided
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        fastener: Union[Nut, Screw],
        fit: Literal["Close", "Normal", "Loose"] = "Normal",
        depth: float = None,
        counter_sunk: bool = True,
        captive_nut: bool = False,
        rotation: RotationLike = (0, 0, 0),
        mode: Mode = Mode.SUBTRACT,
    ):
        context: BuildPart = BuildPart._get_context(self)
        validate_inputs(context, self)

        if isinstance(fastener, HeatSetNut):
            raise ValueError(
                "ClearanceHole doesn't accept fasteners of type HeatSetNut - use insertHole instead"
            )

        if captive_nut and not isinstance(
            fastener, (DomedCapNut, HexNut, UnchamferedHexagonNut, SquareNut)
        ):
            raise ValueError(
                "Only DomedCapNut, HexNut, UnchamferedHexagonNut or SquareNut can be captive"
            )

        if depth is not None:
            self.hole_depth = depth
        elif depth is None and context is not None:
            self.hole_depth = 2 * context.max_dimension
        else:
            raise ValueError("No depth provided")

        hole_part = _make_fastener_hole(
            hole_diameters=fastener.clearance_hole_diameters,
            fastener=fastener,
            countersink_profile=fastener.countersink_profile(fit),
            depth=self.hole_depth,
            fit=fit,
            counter_sunk=counter_sunk,
            captive_nut=captive_nut,
            update_hole_locations=context is not None,
        )

        super().__init__(
            part=hole_part,
            align=None,
            rotation=rotation,
            mode=mode,
        )


class TapHole(BasePartObject):
    """Part Object: TapHole

    A tap hole is precisely drilled through a component, sized optimally for a subsequent
    operation where a tap is employed to cut threads into the material. The diameter of
    this pre-drilled hole is critical and is influenced by the specifications of the
    fastener that will be threaded into it, as well as the properties of the base
    material. This preparatory step ensures that the final tapped hole accurately
    accommodates the intended fastener, providing a secure and reliable fit.

    Args:
        fastener (Union[Nut, Screw]): A nut or screw instance
        material (Literal["Soft", "Hard"], optional): Determines tap hole size.
            Defaults to "Soft".
        fit (Optional[Literal["Close", "Normal", "Loose"]], optional): Control hole diameter
            for a countersunk fastener head. Defaults to "Normal".
        depth (float, optional): hole depth - None implies through part. Defaults to None.
        counter_sunk (bool, optional): Is the fastener countersunk into the part?.
            Defaults to True.
        mode (Mode, optional): combination mode. Defaults to Mode.SUBTRACT.

    Raises:
        ValueError: Use InsertHole for HeatSetNut
        ValueError: No depth provided
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        fastener: Union[Nut, Screw],
        material: Literal["Soft", "Hard"] = "Soft",
        fit: Literal["Close", "Normal", "Loose"] = "Normal",
        depth: float = None,
        counter_sunk: bool = True,
        mode: Mode = Mode.SUBTRACT,
    ):
        context: BuildPart = BuildPart._get_context(self)
        validate_inputs(context, self)

        if isinstance(fastener, HeatSetNut):
            raise ValueError(
                "TapHole doesn't accept fasteners of type HeatSetNut - use insertHole instead"
            )

        if depth is not None:
            self.hole_depth = depth
        elif depth is None and context is not None:
            self.hole_depth = 2 * context.max_dimension
        else:
            raise ValueError("No depth provided")

        hole_part = _make_fastener_hole(
            hole_diameters=fastener.tap_hole_diameters,
            fastener=fastener,
            countersink_profile=fastener.countersink_profile(fit),
            depth=self.hole_depth,
            fit=fit,
            material=material,
            counter_sunk=counter_sunk,
            update_hole_locations=context is not None,
        )

        super().__init__(
            part=hole_part,
            align=None,
            rotation=(0, 0, 0),
            mode=mode,
        )


class ThreadedHole(BasePartObject):
    """Part Object: ThreadedHole

    A threaded hole refers to a hole that has been provided with internal threads,
    either through cutting (tapping) or forming, to allow a bolt or screw to be
    screwed into it. Threaded holes are used in a wide range of applications where
    secure fastening is required. They can be found in various sizes and thread
    patterns to match the corresponding screws or bolts.

    Args:
        fastener (Union[Nut, Screw]): A nut or screw instance
        material (Literal["Soft", "Hard"], optional): Determines tap hole size.
            Defaults to "Soft".
        fit (Optional[Literal["Close", "Normal", "Loose"]], optional): Control hole diameter.
            Defaults to "Normal".
        depth (float, optional): hole depth - None implies through part. Defaults to None.
        counter_sunk (bool, optional): Is the fastener countersunk into the part?.
            Defaults to True.
        simple (bool, optional): simplify by not creating thread. Defaults to True.
        mode (Mode, optional): combination mode. Defaults to Mode.SUBTRACT.

    Raises:
        ValueError: Use InsertHole for HeatSetNut
        ValueError: No depth provided
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        fastener: Union[Nut, Screw],
        material: Literal["Soft", "Hard"] = "Soft",
        fit: Literal["Close", "Normal", "Loose"] = "Normal",
        depth: float = None,
        counter_sunk: bool = True,
        simple: bool = True,
        mode: Mode = Mode.SUBTRACT,
    ):
        context: BuildPart = BuildPart._get_context(self)
        validate_inputs(context, self)

        if isinstance(fastener, HeatSetNut):
            raise ValueError(
                "ThreadedHole doesn't accept fasteners of type HeatSetNut - use InsertHole instead"
            )

        if depth is not None:
            self.hole_depth = depth
        elif depth is None and context is not None:
            self.hole_depth = 2 * context.max_dimension
        else:
            raise ValueError("No depth provided")

        hole_part = _make_fastener_hole(
            hole_diameters=fastener.clearance_hole_diameters,
            fastener=fastener,
            countersink_profile=fastener.countersink_profile(fit),
            depth=self.hole_depth,
            fit=fit,
            material=material,
            counter_sunk=counter_sunk,
            threaded_hole=True,
            update_hole_locations=context is not None,
        )
        if not simple:
            with BuildPart(mode=Mode.PRIVATE):
                thread = IsoThread(
                    major_diameter=fastener.thread_diameter + 0.01,
                    pitch=fastener.thread_pitch,
                    length=min(fastener.length, self.hole_depth),
                    external=False,
                    end_finishes=("fade", "fade"),
                    hand=fastener.hand,
                ).move(Pos(Z=-self.hole_depth))

        super().__init__(
            part=hole_part,
            align=None,
            rotation=(0, 0, 0),
            mode=mode,
        )

        self.thread = None if simple else thread
        self.thread_locations = LocationList._get_context().locations


class InsertHole(BasePartObject):
    """Part Object: InsertHole

    An insert hole is precisely sized to accommodate a heat-set nut, which is embedded
    into the base component. This process creates a robust connection with the base
    material, offering a durable metal threaded interface for the fastener. Heat-set
    nuts are particularly favored for use with 3D-printed objects, as they ensure
    strong and reliable connections between components, enhancing the structural
    integrity of the assembled parts.

    Args:
        fastener (Union[Nut, Screw]): A nut or screw instance
        fit (Optional[Literal["Close", "Normal", "Loose"]], optional): Control hole diameter.
            Defaults to "Normal".
        depth (float, optional): hole depth - None implies through part. Defaults to None.
        manufacturing_compensation (float, optional): used to compensate for over-extrusion
            of 3D printers. A value of 0.2mm will reduce the radius of an external thread
            by 0.2mm (and increase the radius of an internal thread) such that the resulting
            3D printed part matches the target dimensions. Defaults to 0.0.
        mode (Mode, optional): combination mode. Defaults to Mode.SUBTRACT.

    Raises:
        ValueError: Use InsertHole for HeatSetNut
        ValueError: No depth provided
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        fastener: HeatSetNut,
        fit: Literal["Close", "Normal", "Loose"] = "Normal",
        depth: float = None,
        manufacturing_compensation: float = 0.0,
        mode: Mode = Mode.SUBTRACT,
    ):
        context: BuildPart = BuildPart._get_context(self)
        validate_inputs(context, self)

        if depth is not None:
            self.hole_depth = depth
        elif depth is None and context is not None:
            self.hole_depth = 2 * context.max_dimension
        else:
            raise ValueError("No depth provided")

        hole_part = _make_fastener_hole(
            hole_diameters=fastener.clearance_hole_diameters,
            fastener=fastener,
            countersink_profile=fastener.countersink_profile(
                manufacturing_compensation
            ),
            depth=self.hole_depth,
            fit=fit,
            update_hole_locations=context is not None,
        )

        super().__init__(
            part=hole_part,
            align=None,
            rotation=(0, 0, 0),
            mode=mode,
        )
