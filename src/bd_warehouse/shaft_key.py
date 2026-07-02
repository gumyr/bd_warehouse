"""

Parametric Shaft Keys

name: shaft_key.py
by:   Gumyr
date: June 29th 2026

desc: This python/build123d code provides parameterized shaft keys and keyways.

license:

    Copyright 2026 Gumyr

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

from math import isfinite, pi
from numbers import Real
from typing import ClassVar, Literal

from build123d.build_enums import Align, Mode
from build123d.build_sketch import BuildSketch
from build123d.geometry import Axis, Color, Location, Plane, RotationLike
from build123d.joints import RigidJoint
from build123d.objects_part import BasePartObject
from build123d.objects_sketch import Rectangle, SlotOverall
from build123d.topology import Face, Solid

from bd_warehouse.fastener import (
    evaluate_parameter_dict_of_dict,
    isolate_fastener_type,
    read_fastener_parameters_from_csv,
)

KeyForm = Literal["A", "B"]
KeywayType = Literal["shaft", "hub"]
KeywayFit = Literal["Tight", "Loose", "Sliding"]


# ISO 286-1:2010 Tables 1 to 3, limited to the DIN 6885 key widths.
# Values are upper size limit, IT9, IT10, D lower deviation, and P upper
# deviation, respectively, expressed in micrometres except for the size limit.
_ISO_286_HOLE_RANGES = (
    (3, 25, 40, 20, -6),
    (6, 30, 48, 30, -12),
    (10, 36, 58, 40, -15),
    (18, 43, 70, 50, -18),
)


def _iso_286_hole_deviations(
    nominal_size: float, tolerance_class: str
) -> tuple[float, float]:
    """Return the lower and upper hole deviations in millimetres."""
    try:
        _, it9, it10, d_lower, p_upper = next(
            values for values in _ISO_286_HOLE_RANGES if nominal_size <= values[0]
        )
    except StopIteration as error:
        raise ValueError(
            f"No ISO 286 hole deviations available for {nominal_size:g} mm"
        ) from error

    if tolerance_class == "D10":
        deviations = (d_lower, d_lower + it10)
    elif tolerance_class == "H9":
        deviations = (0, it9)
    elif tolerance_class == "JS9":
        deviations = (-it9 / 2, it9 / 2)
    elif tolerance_class == "N9":
        deviations = (-it9, 0)
    elif tolerance_class == "P9":
        deviations = (p_upper - it9, p_upper)
    else:
        raise ValueError(f"Unsupported ISO 286 hole tolerance {tolerance_class}")

    return tuple(deviation / 1000 for deviation in deviations)


def _key_plan(length: float, width: float, key_form: KeyForm) -> Face:
    """Create a private nominal plan for a DIN 6885 parallel key."""
    with BuildSketch(mode=Mode.PRIVATE) as key_plan:
        if key_form == "A":
            SlotOverall(length, width)
        else:
            Rectangle(length, width)
    return key_plan.sketch.face()


def _read_parallel_key_parameters() -> dict[int, dict[str, float]]:
    """Read DIN 6885 parameters with integer shaft-diameter keys."""
    raw_parameters = read_fastener_parameters_from_csv("shaft_key_parameters.csv")
    evaluated_parameters = evaluate_parameter_dict_of_dict(
        isolate_fastener_type("din6885", raw_parameters)
    )
    return {
        int(shaft_diameter): dimensions
        for shaft_diameter, dimensions in evaluated_parameters.items()
    }


class ShaftKey(BasePartObject):  # pylint: disable=too-many-instance-attributes
    """DIN 6885-1 parallel key for a shaft-hub connection.

    Shaft keys transmit torque between a shaft and a mounted component such as a
    gear, pulley, or coupling. Form A has two rounded ends and Form B has two square
    ends. DIN 6885-1 selects the nominal width and height from the shaft diameter;
    the key length is supplied by the caller because it depends on hub length and
    the required torque capacity. This initial dataset covers the nominal shaft
    diameters from 6 mm through 50 mm listed in the available DIN 6885-1 extract.

    Args:
        shaft_diameter: Whole-number nominal shaft diameter in millimetres. An
            integer or integer-valued float may be supplied.
        length: Overall key length in millimetres. The supplied custom length is not
            validated against the DIN preferred-length series.
        key_form: ``"A"`` for rounded ends or ``"B"`` for square ends. Defaults
            to ``"A"``.
        rotation: Sequence of angles about the X, Y, and Z axes. Defaults to
            ``(0, 0, 0)``.
        align: Align MIN, CENTER, or MAX of the key. Defaults to None, which keeps
            the key centered in XY with its minimum Z face on the placement plane.
        mode: Combination mode. Defaults to Mode.ADD.

    Raises:
        ValueError: The shaft diameter, length, or key form is invalid.
    """

    standard = "DIN6885-1"
    key_data = _read_parallel_key_parameters()

    @staticmethod
    def _validate_shaft_diameter(shaft_diameter: int | float) -> int:
        """Validate and normalize a whole-number nominal shaft diameter."""
        if (
            isinstance(shaft_diameter, bool)
            or not isinstance(shaft_diameter, Real)
            or not isfinite(float(shaft_diameter))
            or int(shaft_diameter) != shaft_diameter
        ):
            raise ValueError("shaft_diameter must be a whole number of millimetres")
        normalized_diameter = int(shaft_diameter)
        if normalized_diameter <= 0:
            raise ValueError("shaft_diameter must be greater than zero")
        return normalized_diameter

    @classmethod
    def sizes(cls) -> list[int]:
        """Return the supported nominal shaft diameters."""
        return list(cls.key_data)

    @classmethod
    def parameters(cls, shaft_diameter: int | float) -> dict[str, float]:
        """Return the nominal key and keyway parameters for a shaft diameter."""
        validated_diameter = cls._validate_shaft_diameter(shaft_diameter)
        try:
            parameters = cls.key_data[validated_diameter]
        except KeyError as error:
            raise ValueError(
                f"{shaft_diameter} invalid, must be one of {cls.sizes()}"
            ) from error
        return parameters.copy()

    @classmethod
    def select_by_size(
        cls, shaft_diameter: int | float
    ) -> dict[type["ShaftKey"], list[str]]:
        """Return the shaft-key class and standard available for a diameter."""
        validated_diameter = cls._validate_shaft_diameter(shaft_diameter)
        return {cls: [cls.standard]} if validated_diameter in cls.sizes() else {}

    @property
    def info(self) -> str:
        """Return identifying information for this shaft key."""
        return (
            f"{self.__class__.__name__}({self.standard}, Form {self.key_form}): "
            f"{self.shaft_diameter:g}x{self.length:g}"
        )

    def __init__(  # pylint: disable=too-many-positional-arguments
        self,
        shaft_diameter: int | float,
        length: float,
        key_form: KeyForm = "A",
        rotation: RotationLike = (0, 0, 0),
        align: Align | tuple[Align, Align, Align] | None = None,
        mode: Mode = Mode.ADD,
    ):
        if key_form not in ("A", "B"):
            raise ValueError("key_form must be 'A' or 'B'")
        self.key_form = key_form
        self.shaft_diameter = self._validate_shaft_diameter(shaft_diameter)
        self.key_dict = self.parameters(self.shaft_diameter)
        self.length = float(length)
        if self.length <= 0:
            raise ValueError("length must be greater than zero")

        self.width = self.key_dict["b"]
        self.key_height = self.key_dict["h"]
        if self.length < self.width:
            raise ValueError("length must be greater than or equal to the key width")

        super().__init__(
            part=self.make_key(),
            rotation=rotation,
            align=align,
            mode=mode,
        )
        self.label = (
            f"{self.__class__.__name__}-{self.standard}-Form{self.key_form}-"
            f"{self.shaft_diameter}x{self.length:g}"
        )
        self.color = Color(0x909090)
        RigidJoint("a", self, Location())

    @property
    def plan_area(self) -> float:
        """Return the nominal area of the key plan."""
        if self.key_form == "A":
            return self.width * (self.length - self.width) + pi * self.width**2 / 4
        return self.length * self.width

    def make_key(self) -> Solid:
        """Create the parallel-key solid with its minimum Z face at zero."""
        return Solid.extrude(
            _key_plan(self.length, self.width, self.key_form),
            (0, 0, self.key_height),
        )


class Keyway(BasePartObject):  # pylint: disable=too-many-instance-attributes
    """Nominal keyway cutter for a DIN 6885-1 parallel key.

    ``fit`` selects the DIN 6885-1 tolerance class for the shaft or hub keyway.
    ISO 286-1 limit deviations determine ``min_width`` and ``max_width``; the
    cutter is modeled at their midpoint, available as ``width``. By default the
    cutter is positioned for a shaft or bore centered on Axis.Z: its length is
    centered on Z, its width is centered on Y, and its radial face is located at
    the nominal shaft radius. Shaft keyways extend inward along negative X; hub
    keyways extend outward along positive X.

    Args:
        key: Parallel key defining the nominal length, width, and end form.
        keyway_type: ``"shaft"`` for a shaft keyseat or ``"hub"`` for a hub
            keyway. Defaults to ``"shaft"``.
        fit: DIN 6885-1 fit selection: ``"Tight"``, ``"Loose"``, or
            ``"Sliding"``. Defaults to ``"Loose"``.
        rotation: Sequence of angles about the X, Y, and Z axes. Defaults to
            ``(0, 0, 0)``.
        align: Align MIN, CENTER, or MAX of the cutter. Defaults to None, which
            retains the shaft-centered placement.
        mode: Combination mode. Defaults to Mode.SUBTRACT.

    Raises:
        ValueError: The key, keyway type, or fit is invalid.
    """

    keyway_fits: ClassVar[dict[str, dict[str, str]]] = {
        "Tight": {"hub": "P9", "shaft": "P9"},
        "Loose": {"hub": "JS9", "shaft": "N9"},
        "Sliding": {"hub": "D10", "shaft": "H9"},
    }

    def __init__(  # pylint: disable=too-many-positional-arguments
        self,
        key: ShaftKey,
        keyway_type: KeywayType = "shaft",
        fit: KeywayFit = "Loose",
        rotation: RotationLike = (0, 0, 0),
        align: Align | tuple[Align, Align, Align] | None = None,
        mode: Mode = Mode.SUBTRACT,
    ):
        if not isinstance(key, ShaftKey):
            raise ValueError("Keyway only accepts a ShaftKey")
        if keyway_type not in ("shaft", "hub"):
            raise ValueError("keyway_type must be 'shaft' or 'hub'")
        if fit not in self.keyway_fits:
            raise ValueError(f"fit must be one of {list(self.keyway_fits)}")

        self.key = key
        self.keyway_type = keyway_type
        self.fit = fit
        self.nominal_width = key.width
        self.length = key.length
        self.keyway_depth = key.key_dict["t4" if keyway_type == "shaft" else "t2"]
        self.keyway_depth_tolerance = key.key_dict[
            "t4_tol+" if keyway_type == "shaft" else "t2_tol+"
        ]
        self.width_tolerance = self.keyway_fits[fit][keyway_type]
        lower_deviation, upper_deviation = _iso_286_hole_deviations(
            self.nominal_width, self.width_tolerance
        )
        self.min_width = self.nominal_width + lower_deviation
        self.max_width = self.nominal_width + upper_deviation
        self.width = (self.min_width + self.max_width) / 2

        cutter = Solid.extrude(
            _key_plan(self.length, self.width, key.key_form),
            (0, 0, -self.keyway_depth),
        )
        cutter = cutter.rotate(Axis.Y, 90 if keyway_type == "shaft" else -90).translate(
            (key.shaft_diameter / 2, 0, 0)
        )
        super().__init__(
            part=cutter,
            rotation=rotation,
            align=align,
            mode=mode,
        )
        self.label = (
            f"Keyway-{keyway_type}-{fit}-{key.standard}-Form{key.key_form}-"
            f"{key.shaft_diameter}x{key.length:g}"
        )

    def broach_profile(self) -> Face:
        """Return the transverse profile of a broached hub keyway.

        The profile lies on the XY plane and extends from the shaft axis at X=0
        through the bore to the bottom of the keyway at the nominal shaft radius
        plus the keyway depth. Its width is centered on the X axis. Extrude the
        profile along the bore axis without applying a radial offset.

        Raises:
            ValueError: If this is not a hub keyway.
        """
        if self.keyway_type != "hub":
            raise ValueError("broach_profile is only available for hub keyways")

        profile_depth = self.key.shaft_diameter / 2 + self.keyway_depth
        return Face.make_rect(
            profile_depth,
            self.width,
            Plane(origin=(profile_depth / 2, 0, 0)),
        )
