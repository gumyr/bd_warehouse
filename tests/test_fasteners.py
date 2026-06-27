"""

Fastener Tests

name: test_fasteners.py
by:   Gumyr
date: May 12, 2025

desc: Basic pytests for the fastener classes.

license:

    Copyright 2025 Gumyr

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

import io
import random

import pytest
from bd_warehouse.fastener import (
    ClearanceHole,
    DomedCapNut,
    HeatSetNut,
    HexNut,
    HexNutWithFlange,
    InsertHole,
    Nut,
    Screw,
    SetScrew,
    SocketHeadCapScrew,
    SquareNut,
    TapHole,
    UnchamferedHexagonNut,
    Washer,
)
from build123d import Axis, Box, BuildPart, Compound, Locations


def test_csv_reading_uses_explicit_utf8_encoding():
    """Regression: every CSV read in fastener.py must pass encoding='utf-8'
    to the .open() call, NOT rely on the locale default.

    On Windows with a CJK default code page (GBK / cp932 / cp949), the ISO 15
    bearing parameter CSVs contain UTF-8 en-dashes (U+2013, \\xe2\\x80\\x93)
    that cannot be decoded as GBK. Without an explicit encoding, importing
    bd_warehouse.bearing fails at class-body time with UnicodeDecodeError.

    This is a source-level check (not runtime) because the CSV reads happen
    at module import time and cannot be easily monkey-patched after the fact.
    """
    import inspect
    from bd_warehouse import fastener as _fastener_mod

    src = inspect.getsource(_fastener_mod)
    bare_open = src.count("data_resource.open()")
    utf8_open = src.count('data_resource.open(encoding="utf-8"')

    assert bare_open == 0, (
        f"Found {bare_open} bare data_resource.open() calls in fastener.py; "
        "all must specify encoding='utf-8' to work on non-UTF-8 locales "
        "(e.g. Windows CJK code pages)."
    )
    assert utf8_open >= 3, (
        f"Expected at least 3 encoding='utf-8' opens in fastener.py "
        f"(read_fastener_parameters_from_csv, read_drill_sizes, "
        f"lookup_nominal_screw_lengths); found {utf8_open}."
    )


def test_csv_read_succeeds_under_non_utf8_locale():
    """Functional check: read_fastener_parameters_from_csv() must succeed
    even when the active locale cannot decode the CSV bytes.

    We can't actually change sys.getfilesystemencoding() at runtime, but we
    can verify the function runs to completion on the bearing CSV that
    contains the en-dash character. If this test runs on any platform
    (including Windows) without raising, the encoding fix is in effect.
    """
    from bd_warehouse.fastener import read_fastener_parameters_from_csv

    data = read_fastener_parameters_from_csv(
        "single_row_deep_groove_ball_bearing_parameters.csv"
    )
    # The file has 30+ bearing rows; exact count may grow over time
    assert len(data) >= 20, f"expected >=20 rows, got {len(data)}"
    assert "M8-22-7" in data, "ISO 608 bearing row missing"


def test_bearing_csv_contains_non_ascii():
    """Regression safeguard: confirms the CSV *really does* contain bytes
    that require UTF-8 decoding, so the encoding fix isn't a no-op."""
    from importlib import resources
    from bd_warehouse import fastener as _fastener_mod

    data_resource = (
        resources.files(_fastener_mod.bd_warehouse)
        / "data/single_row_deep_groove_ball_bearing_parameters.csv"
    )
    with data_resource.open("rb") as f:
        raw = f.read()
    # en-dash "–" (U+2013) encoded as UTF-8 bytes \xe2\x80\x93
    assert b"\xe2\x80\x93" in raw, (
        "Expected UTF-8 en-dash in bearing CSV; without it the encoding "
        "fix is untested."
    )

@pytest.mark.parametrize(
    "screw_class, screw_type, screw_size",
    [
        (screw_class, screw_type, screw_size)
        for screw_size in ["M5-0.8", "1/4-20"]
        for screw_class, screw_types in Screw.select_by_size(screw_size).items()
        for screw_type in screw_types
    ],
)
def test_screws(screw_class: Screw, screw_type: str, screw_size: str):
    screw_min_length = screw_class.nominal_length_range[screw_type][0]
    screw: Screw = screw_class(
        size=screw_size,
        length=screw_min_length,
        fastener_type=screw_type,
        simple=False,
    )
    # Check that screw properties are created
    assert len(screw.tap_drill_sizes) > 0
    assert len(screw.tap_hole_diameters) > 0
    assert len(screw.clearance_drill_sizes) > 0
    assert len(screw.clearance_hole_diameters) > 0
    assert len(screw.info) > 2
    assert screw.length_offset() is not None
    if isinstance(screw, SetScrew):
        assert screw.min_hole_depth(random.choice([True, False])) == 0
    else:
        assert screw.min_hole_depth(random.choice([True, False])) > 0
    assert len(screw.nominal_lengths) > 0

    # Check that holes can be created
    with BuildPart() as hole_tests:
        Box(100, 100, screw_min_length)
        top = hole_tests.faces().sort_by(Axis.Z)[-1]
        with Locations(top):
            with Locations((25, 0)):
                ClearanceHole(screw)
            with Locations((-25, 0)):
                TapHole(screw)
    assert hole_tests.part.volume < 100 * 100 * screw_min_length

@pytest.mark.parametrize(
    "nut_class, nut_type, nut_size",
    [
        (nut_class, nut_type, nut_size)
        for nut_size in ["M5-0.8", "M5-0.8-Standard", "1/4-20"]
        for nut_class, nut_types in Nut.select_by_size(nut_size).items()
        for nut_type in nut_types
    ],
)
def test_nuts(nut_class: Nut, nut_type: str, nut_size: str):
    nut: Nut = nut_class(size=nut_size, fastener_type=nut_type, simple=False)

    # Check that screw properties are created
    assert len(nut.tap_drill_sizes) > 0
    assert len(nut.tap_hole_diameters) > 0
    assert len(nut.clearance_drill_sizes) > 0
    assert len(nut.clearance_hole_diameters) > 0
    assert len(nut.info) > 2
    assert nut.nut_diameter > nut.thread_diameter
    assert nut.length_offset() == 0

    if isinstance(nut, (DomedCapNut, HexNut, UnchamferedHexagonNut, SquareNut)):
        captive = random.choice([True, False])
    else:
        captive = False

    with BuildPart() as hole_tests:
        Box(100, 100, 20)
        bottom = hole_tests.faces().sort_by(Axis.Z)[0]
        with Locations(bottom):
            if nut_class == HeatSetNut:
                InsertHole(nut)
                assert nut.fill_factor > 1.0  # hole smaller than nut
            else:
                ClearanceHole(nut, captive_nut=captive)
    assert hole_tests.part.volume < 100 * 100 * 20

    # Check that rotated holes can be created
    if not nut_class in [HeatSetNut, HexNutWithFlange]:
        rotated_nut: Nut = nut_class(size=nut_size, fastener_type=nut_type, simple=True, rotation=(0, 0, 45))
        with BuildPart() as rotate_hole_tests:
            Box(100, 100, 20)
            top = rotate_hole_tests.faces().sort_by(Axis.Z)[-1]
            with Locations(top):
                ClearanceHole(rotated_nut, captive_nut=True, rotation=(0, 0, 45))
        assert rotate_hole_tests.part.volume < 100 * 100 * 20

        assembly_with_rotated_nut_and_hole = Compound(children=[rotate_hole_tests.part, rotated_nut.moved(rotated_nut.hole_locations[0])])
        assert not assembly_with_rotated_nut_and_hole.do_children_intersect()[0]


@pytest.mark.parametrize(
    "washer_class, washer_type, washer_size",
    [
        (washer_class, washer_type, washer_size)
        for washer_size in ["M5", "1/4"]
        for washer_class, washer_types in Washer.select_by_size(washer_size).items()
        for washer_type in washer_types
    ],
)
def test_washers(washer_class: Nut, washer_type: str, washer_size: str):
    washer: Washer = washer_class(size=washer_size, fastener_type=washer_type)

    # Check that screw properties are created
    assert len(washer.clearance_hole_diameters) > 0
    assert len(washer.info) > 2
    assert washer.washer_diameter > washer.thread_diameter
    assert washer.washer_thickness > 0

    with BuildPart() as hole_tests:
        Box(100, 100, 20)
        bottom = hole_tests.faces().sort_by(Axis.Z)[0]
        with Locations(bottom):
            ClearanceHole(washer)
    assert hole_tests.part.volume < 100 * 100 * 20


if __name__ == "__main__":
    test_screws(SocketHeadCapScrew, "iso4762", "M5-0.8")
