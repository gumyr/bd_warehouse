"""

Parametric O-Rings

name: o_rings.py
by:   Gumyr
date: June 29th 2026

desc: This python/build123d code provides parameterized O-rings and gland profiles.

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

import csv
import math
from bisect import bisect_left
from collections import defaultdict
from importlib import resources
from typing import Literal

from build123d.build_enums import Align, Mode
from build123d.geometry import Axis, Color, Pos, RotationLike
from build123d.objects_part import BasePartObject
from build123d.objects_sketch import Rectangle
from build123d.operations_generic import fillet
from build123d.topology import Sketch, Solid

import bd_warehouse
from bd_warehouse.fastener import (
    evaluate_parameter_dict_of_dict,
    isolate_fastener_type,
    read_fastener_parameters_from_csv,
)


def read_parameters_from_csv(filename: str) -> dict:
    """Parse a metric O-ring gland CSV parameter file."""
    parameters = {}
    data_resource = resources.files(bd_warehouse) / f"data/{filename}"

    with data_resource.open(encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise ValueError(f"No header found in {filename}")
        for row in reader:
            key = row[fieldnames[0]]
            row.pop(fieldnames[0])
            parameters[key] = {
                str(k): (None if v.strip() == "-" else float(v)) for k, v in row.items()
            }

    return parameters


def _build_o_ring_indexes(
    parameter_data: dict[str, dict[str, str]],
) -> tuple[
    dict[str, dict[str, dict[str, float]]],
    dict[str, dict[float, list[tuple[float, str]]]],
]:
    """Build evaluated parameter and width-family indexes for each standard."""
    if not parameter_data:
        raise ValueError("O-ring parameter data is empty")

    first_row = next(iter(parameter_data.values()))
    standards = {
        parameter.split(":", maxsplit=1)[0]
        for parameter in first_row
        if ":" in parameter
    }
    if not standards:
        raise ValueError("O-ring parameter headers contain no standards")

    parameters_by_type = {}
    width_families_by_type = {}
    for standard in sorted(standards):
        standard_parameters = evaluate_parameter_dict_of_dict(
            isolate_fastener_type(standard, parameter_data)
        )
        if not standard_parameters:
            raise ValueError(f"O-ring parameter data for {standard} is empty")

        width_families = defaultdict(list)
        for size_code, dimensions in standard_parameters.items():
            try:
                width_families[dimensions["w"]].append((dimensions["id"], size_code))
            except KeyError as error:
                raise ValueError(
                    f"O-ring parameter data for {standard}:{size_code} is incomplete"
                ) from error
        for entries in width_families.values():
            entries.sort()

        parameters_by_type[standard] = standard_parameters
        width_families_by_type[standard] = dict(width_families)

    return parameters_by_type, width_families_by_type


class ORing(BasePartObject):  # pylint: disable=too-many-instance-attributes
    """Parametric O-ring for static and dynamic sealing applications.

    O-rings are toroidal elastomeric seals installed in a gland and compressed
    between mating components to prevent fluid or gas leakage. This class creates
    nominal general-industrial Class A geometry from ISO 3601-1 and provides
    :meth:`static_gland_profile` and :meth:`dynamic_gland_profile` helpers for
    designing a corresponding gland. The gland dimensions are initial design
    recommendations from the Apple Rubber Seal Design Guide; they have not been
    verified against ISO 3601-2.

    Args:
        size: Three-digit O-ring size code, such as ``"025"``. A leading hyphen
            and omitted leading zeroes are accepted and normalized.
        o_ring_type: Dimensional standard used to interpret ``size``. Defaults to
            ``"iso3601"``.
        rotation: Sequence of angles about the X, Y, and Z axes. Defaults to
            ``(0, 0, 0)``.
        align: Align MIN, CENTER, or MAX of the O-ring. Defaults to None.
        mode: Combination mode. Defaults to Mode.ADD.

    Raises:
        ValueError: ``size`` or ``o_ring_type`` is invalid.
    """

    o_ring_data = read_fastener_parameters_from_csv("o-ring_parameters.csv")
    o_ring_parameters, o_ring_width_families = _build_o_ring_indexes(o_ring_data)

    o_ring_static_gland_data = read_parameters_from_csv(
        "o-ring_static_gland_parameters.csv"
    )
    o_ring_dynamic_gland_data = read_parameters_from_csv(
        "o-ring_dynamic_gland_parameters.csv"
    )

    @staticmethod
    def _normalize_size(size: str) -> str:
        """Normalize an O-ring size code to three digits."""
        normalized_size = size.strip().removeprefix("-")
        if not normalized_size.isdigit() or len(normalized_size) > 3:
            raise ValueError(f"{size!r} invalid, size must be a three-digit code")
        return normalized_size.zfill(3)

    @classmethod
    def types(cls) -> set[str]:
        """Return the available O-ring standards."""
        return set(cls.o_ring_parameters)

    @classmethod
    def sizes(cls, o_ring_type: str = "iso3601") -> list[str]:
        """Return the available size codes for an O-ring standard."""
        if o_ring_type not in cls.types():
            raise ValueError(f"{o_ring_type} invalid, must be one of {cls.types()}")
        return list(cls.o_ring_parameters[o_ring_type])

    @classmethod
    def parameters(cls, size: str, o_ring_type: str = "iso3601") -> dict[str, float]:
        """Return the evaluated metric parameters for a size and standard."""
        normalized_size = cls._normalize_size(size)
        if o_ring_type not in cls.types():
            raise ValueError(f"{o_ring_type} invalid, must be one of {cls.types()}")
        try:
            parameters = cls.o_ring_parameters[o_ring_type][normalized_size]
        except KeyError as error:
            raise ValueError(
                f"{size!r} invalid, must be one of {cls.sizes(o_ring_type)}"
            ) from error
        return parameters.copy()

    @classmethod
    def select_by_size(cls, size: str) -> dict[type["ORing"], list[str]]:
        """Return the standards that provide the given size code."""
        normalized_size = cls._normalize_size(size)
        matching_types = [
            o_ring_type
            for o_ring_type in sorted(cls.types())
            if normalized_size in cls.sizes(o_ring_type)
        ]
        return {cls: matching_types} if matching_types else {}

    @classmethod
    def _find_neighbors(
        cls,
        target: float,
        tolerance: float,
        o_ring_type: str,
        by_diameter: bool = True,
    ) -> dict[str, tuple[str | None, ...]]:
        if target <= 0:
            raise ValueError("target must be greater than zero")
        if tolerance < 0:
            raise ValueError("tolerance must be greater than or equal to zero")
        if o_ring_type not in cls.types():
            raise ValueError(f"{o_ring_type} invalid, must be one of {cls.types()}")

        results = {}
        for width, diameter_entries in cls.o_ring_width_families[o_ring_type].items():
            entries = (
                diameter_entries
                if by_diameter
                else [
                    (math.pi * (inner_diameter + width), size_code)
                    for inner_diameter, size_code in diameter_entries
                ]
            )
            values = [entry[0] for entry in entries]
            index = bisect_left(values, target)

            if index < len(entries) and values[index] == target:
                results[str(width)] = (entries[index][1],)
                continue

            lower = (
                entries[index - 1][1]
                if index > 0 and abs(values[index - 1] - target) / target <= tolerance
                else None
            )
            upper = (
                entries[index][1]
                if index < len(entries)
                and abs(values[index] - target) / target <= tolerance
                else None
            )

            if lower is not None or upper is not None:
                results[str(width)] = (lower, upper)

        return results

    @classmethod
    def select_by_inner_diameter(
        cls,
        inner_diameter: float,
        tolerance: float = 0.05,
        o_ring_type: str = "iso3601",
    ) -> dict:
        """select_by_inner_diameter

        Find closest matches to the given inner_diameter within tolerance. The
        results are returned in a dict with the key being the O-ring width and the
        values being a tuple of O-ring size codes in (lower, upper) pairs. Should
        there be an exact match, a (match,) tuple will be generated.

        Args:
            inner_diameter (float): inner diameter in mm
            tolerance (float, optional): ± deviation from target. Defaults to 0.05.

        Returns:
            dict: width as key and tuple of o-ring dash numbers as values

        Example:
            >>> ORing.select_by_inner_diameter(650)
            {'5.33': ('394', '395'), '6.99': ('474', '475')}
        """
        return cls._find_neighbors(inner_diameter, tolerance, o_ring_type)

    @classmethod
    def select_by_length(
        cls,
        length: float,
        tolerance: float = 0.05,
        o_ring_type: str = "iso3601",
    ) -> dict:
        """Find O-rings for a target installed centre-line length.

        For each cross-section family, the result contains the nearest free O-ring
        lengths below and above ``length`` as a ``(lower, upper)`` pair. A lower
        candidate will be stretched when installed on the target path, while an
        upper candidate will be circumferentially compressed. An exact free-length
        match is returned as a one-item tuple.

        For typical piston or male-gland applications, use about 2% installed
        stretch as a design target. The usual range is 1% to 5%, with 5% treated as
        an upper limit rather than a target. Stretch above 5% can accelerate ageing
        and reduce the O-ring cross-section and resulting seal compression. Rotary
        shaft seals generally require no installed stretch.

        The installed stretch for a candidate is calculated as::

            stretch = length / candidate.length - 1

        Gland squeeze calculations should account for the reduction in cross-section
        caused by stretching.

        Args:
            length: Target installed centre-line length in millimetres.
            tolerance: Maximum fractional difference between the free and installed
                lengths. The default 0.05 searches within 5% of the target.
            o_ring_type: Dimensional standard used for selection. Defaults to
                ``"iso3601"``.

        Returns:
            Cross-section widths mapped to lower and upper O-ring size codes.

        Example:
            Select a size for a 101.42 mm installed path and verify that size 025
            is stretched by approximately 2%:

            >>> installed_length = 101.42
            >>> matches = ORing.select_by_length(installed_length)
            >>> matches["1.78"]
            ('025', '026')
            >>> candidate = ORing(matches["1.78"][0])
            >>> round(installed_length / candidate.length - 1, 3)
            0.02

        """
        return cls._find_neighbors(length, tolerance, o_ring_type, by_diameter=False)

    @classmethod
    def nominal_widths(cls, o_ring_type: str = "iso3601") -> list[float]:
        """Return the nominal cross-section widths for an O-ring standard."""
        if o_ring_type not in cls.types():
            raise ValueError(f"{o_ring_type} invalid, must be one of {cls.types()}")
        return sorted(cls.o_ring_width_families[o_ring_type])

    @classmethod
    def gland_width_for(
        cls,
        o_ring_width: float,
        application: Literal["static", "dynamic"] = "static",
        number_backing_rings: Literal[0, 1, 2] = 0,
    ) -> float:
        """Return the recommended gland width for an O-ring cross-section.

        Args:
            o_ring_width: Nominal O-ring cross-section diameter in millimetres.
            application: ``"static"`` or ``"dynamic"`` gland design. Defaults
                to ``"static"``.
            number_backing_rings: Number of anti-extrusion backing rings
                accommodated by the gland. Defaults to 0.

        Returns:
            The nominal gland width in millimetres.

        Raises:
            ValueError: The application, backing-ring count, or O-ring
                cross-section is invalid or unsupported.
        """
        if application not in ("static", "dynamic"):
            raise ValueError("application must be 'static' or 'dynamic'")
        if number_backing_rings not in (0, 1, 2):
            raise ValueError("number_backing_rings must be 0, 1, or 2")
        if not math.isfinite(o_ring_width) or o_ring_width <= 0:
            raise ValueError("o_ring_width must be greater than zero")

        gland_table = (
            cls.o_ring_static_gland_data
            if application == "static"
            else cls.o_ring_dynamic_gland_data
        )
        try:
            gland_data = gland_table[f"{o_ring_width:g}"]
        except KeyError as error:
            raise ValueError(
                f"No {application} gland data for an O-ring with a "
                f"{o_ring_width} mm cross-section"
            ) from error

        gland_width = gland_data[f"g_w_{number_backing_rings}"]
        if gland_width is None:
            raise ValueError(
                f"{number_backing_rings} backing rings are not supported for "
                f"an O-ring with a {o_ring_width} mm cross-section"
            )
        return gland_width

    def __init__(  # pylint: disable=too-many-positional-arguments
        self,
        size: str,
        o_ring_type: str = "iso3601",
        rotation: RotationLike = (0, 0, 0),
        align: None | Align | tuple[Align, Align, Align] = None,
        mode: Mode = Mode.ADD,
    ):
        self.o_ring_size = self._normalize_size(size)
        self.o_ring_type = o_ring_type
        dimensions = self.parameters(self.o_ring_size, self.o_ring_type)

        self.dash_number = self.o_ring_size  #: ISO 3601 size code
        self.inner_diameter = dimensions["id"]  #: inner diameter
        self.inner_diameter_tolerance = dimensions["id_tol"]
        self.width = dimensions["w"]  #: cross-section diameter
        self.width_tolerance = dimensions["w_tol"]
        self.major_radius = (
            self.inner_diameter + self.width
        ) / 2  #: torus major radius
        self.minor_radius = self.width / 2  #: torus minor radius
        self.length = 2 * math.pi * self.major_radius  #: center line length

        o_ring = Solid.make_torus(self.major_radius, self.minor_radius)
        self.gland_width = None
        self.gland_width_tol = 0.13
        self.gland_depth = None
        self.gland_depth_tol = None
        self.gland_radius = None
        self.gland_radius_tol = None
        self.gland_profile: Sketch | None = None

        super().__init__(part=o_ring, rotation=rotation, align=align, mode=mode)
        self.label = f"ORing-{self.o_ring_type}-{self.o_ring_size}"
        self.color = Color(0x202020)

    @property
    def info(self) -> str:
        """Return identifying information for this O-ring."""
        return f"ORing({self.o_ring_type}): {self.o_ring_size}"

    def _gland_data_for_width(
        self,
        gland_table: dict[str, dict[str, float | None]],
        application: str,
    ) -> dict[str, float | None]:
        """Return gland parameters or report an unsupported cross-section."""
        try:
            return gland_table[f"{self.width:g}"]
        except KeyError as error:
            raise ValueError(
                f"No {application} gland data for an O-ring with a "
                f"{self.width} mm cross-section"
            ) from error

    def _make_gland_profile(
        self,
        gland_data: dict[str, float | None],
        *,
        depth_min_key: str,
        depth_max_key: str,
        number_backing_rings: Literal[0, 1, 2],
    ) -> Sketch:
        """Create and record a gland profile from evaluated gland parameters."""
        if number_backing_rings not in (0, 1, 2):
            raise ValueError("number_backing_rings must be 0, 1, or 2")

        gland_w = gland_data[f"g_w_{number_backing_rings}"]
        if gland_w is None:
            raise ValueError(
                f"{number_backing_rings} backing rings are not supported for "
                f"an O-ring with a {self.width} mm cross-section"
            )

        depth_min = gland_data[depth_min_key]
        depth_max = gland_data[depth_max_key]
        if depth_min is None or depth_max is None:  # pragma: no cover
            raise ValueError("Gland depth data is incomplete")
        depth_avg = (depth_max + depth_min) / 2
        groove_r_min = gland_data["g_r_min"]
        groove_r_max = gland_data["g_r_max"]
        if groove_r_min is None or groove_r_max is None:  # pragma: no cover
            raise ValueError("Gland radius data is incomplete")
        groove_r_avg = (groove_r_max + groove_r_min) / 2
        gland_profile = Rectangle(gland_w, depth_avg, align=(Align.CENTER, Align.MAX))
        gland_profile = fillet(
            gland_profile.vertices().group_by(Axis.Y)[0], groove_r_avg
        )
        self.gland_width = gland_w
        self.gland_depth = depth_avg
        self.gland_depth_tol = depth_max - depth_avg
        self.gland_radius = groove_r_avg
        self.gland_radius_tol = groove_r_max - groove_r_avg
        self.gland_profile = gland_profile
        return gland_profile

    def static_gland_profile(
        self, axial: bool = True, number_backing_rings: Literal[0, 1, 2] = 0
    ) -> Sketch:
        """Create the recommended profile for a static O-ring gland.

        Args:
            axial: Select axial squeeze when True or radial squeeze when False.
                Defaults to True.
            number_backing_rings: Number of anti-extrusion backing rings accommodated
                by the gland. Defaults to 0.

        Returns:
            The gland cross-section with its opening on the local X axis.

        Raises:
            ValueError: The backing-ring count is invalid or unsupported for the
                O-ring cross-section.
        """
        gland_data = self._gland_data_for_width(self.o_ring_static_gland_data, "static")
        axial_radial = "a" if axial else "r"
        return self._make_gland_profile(
            gland_data,
            depth_min_key=f"d_{axial_radial}_min",
            depth_max_key=f"d_{axial_radial}_max",
            number_backing_rings=number_backing_rings,
        )

    def dynamic_gland_profile(
        self, number_backing_rings: Literal[0, 1, 2] = 0
    ) -> Sketch:
        """Create the recommended profile for a dynamic radial O-ring gland.

        The dimensions are intended as initial design guidance for reciprocating or
        oscillating seals. Dynamic seal performance also depends on material,
        lubrication, surface finish, pressure, temperature, stretch, and friction.

        Args:
            number_backing_rings: Number of anti-extrusion backing rings accommodated
                by the gland. Defaults to 0.

        Returns:
            The gland cross-section with its opening on the local X axis.

        Raises:
            ValueError: The backing-ring count is invalid or unsupported for the
                O-ring cross-section.
        """
        gland_data = self._gland_data_for_width(
            self.o_ring_dynamic_gland_data, "dynamic"
        )
        return self._make_gland_profile(
            gland_data,
            depth_min_key="d_min",
            depth_max_key="d_max",
            number_backing_rings=number_backing_rings,
        )


if __name__ == "__main__":
    from ocp_vscode import show_all

    external_ring = ORing("40")
    rings = []
    stack_height = 0.0
    for size in reversed(ORing.sizes()):
        try:
            ring = Pos(Z=stack_height) * ORing(size)
            rings.append(ring)
            stack_height += ring.width
        except Exception as error:  # pylint: disable=broad-exception-caught
            print(f"{size} failed: {error}")

    show_all()
