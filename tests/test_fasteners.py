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
import math
import random

import pytest
from bd_warehouse.fastener import (
    ButtonHeadScrew,
    ButtonHeadWithCollarScrew,
    CheeseHeadScrew,
    ClearanceHole,
    CounterSunkScrew,
    DomedCapNut,
    HeatSetNut,
    HexHeadScrew,
    HexHeadWithFlangeScrew,
    HexNut,
    HexNutWithFlange,
    InsertHole,
    Nut,
    PanHeadScrew,
    PanHeadWithCollarScrew,
    RaisedCheeseHeadScrew,
    RaisedCounterSunkOvalHeadScrew,
    Screw,
    SetScrew,
    ShoulderScrew,
    SocketHeadCapScrew,
    SquareNut,
    TapHole,
    ThreadedHole,
    UnchamferedHexagonNut,
    Washer,
)
from build123d import IN, Align, Axis, Box, BuildPart, Compound, Locations, Plane


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


def test_simple_threaded_hole_uses_material_specific_tap_drill():
    """A simple ThreadedHole is a material-specific cylindrical tap drill."""
    screw = SocketHeadCapScrew("M6-1", 10)
    soft_tap = ThreadedHole(
        screw, material="Soft", depth=20, counter_sunk=False
    )
    hard_tap = ThreadedHole(
        screw, material="Hard", depth=20, counter_sunk=False
    )

    assert soft_tap.thread is None
    assert hard_tap.thread is None
    assert hard_tap.volume > soft_tap.volume
    assert soft_tap.bounding_box().min.Z == pytest.approx(-20)
    assert soft_tap.bounding_box().max.Z == pytest.approx(0)

    workpiece = Box(20, 20, 20, align=(Align.CENTER, Align.CENTER, Align.MAX))
    threaded_part = workpiece - soft_tap
    assert threaded_part.is_valid
    assert threaded_part.volume < workpiece.volume


def test_detailed_threaded_hole_is_compound_tap_to_requested_depth():
    """The detailed algebra cutter contains a core and square-ended tap thread."""
    screw = SocketHeadCapScrew("M6-1", 10)
    tap = ThreadedHole(
        screw,
        material="Soft",
        depth=20,
        counter_sunk=False,
        simple=False,
    )

    assert tap.thread is not None
    assert len(tap.solids()) > 1
    assert tap.bounding_box().min.Z == pytest.approx(-20)
    assert tap.bounding_box().max.Z == pytest.approx(0, abs=1e-6)
    assert tap.thread.bounding_box().min.Z == pytest.approx(-20)
    assert tap.thread.bounding_box().max.Z == pytest.approx(0, abs=1e-6)

    workpiece = Box(20, 20, 20, align=(Align.CENTER, Align.CENTER, Align.MAX))
    threaded_part = workpiece - tap
    assert threaded_part.is_valid
    assert threaded_part.volume < workpiece.volume


def test_threaded_hole_builder_locations_and_fastener_locations():
    """Builder locations are applied once and retained by the fastener."""
    screw = SocketHeadCapScrew("M6-1", 20)
    with BuildPart() as plate:
        Box(40, 20, 10, align=(Align.CENTER, Align.CENTER, Align.MAX))
        with Locations((-10, 0), (10, 0)):
            ThreadedHole(screw, depth=10)

    assert plate.part.is_valid
    assert len(screw.hole_locations) == 2
    assert sorted(location.position.X for location in screw.hole_locations) == [
        -10,
        10,
    ]


def test_threaded_hole_on_rotated_face():
    """A private construction builder doesn't double-apply an oriented location."""
    screw = SocketHeadCapScrew("M6-1", 20)
    with BuildPart() as block:
        Box(20, 20, 20)
        side = block.faces().sort_by(Axis.X)[-1]
        with Locations(side):
            ThreadedHole(screw, depth=8, counter_sunk=False)

    assert block.part.is_valid
    assert len(screw.hole_locations) == 1
    assert screw.hole_locations[0].position.X == pytest.approx(10)


def test_threaded_hole_supports_headless_fastener():
    """A missing countersink profile is valid for a headless set screw."""
    screw = SetScrew("M6-1", 20)
    tap = ThreadedHole(screw, depth=20, simple=False)

    assert tap.thread is not None
    assert tap.bounding_box().min.Z == pytest.approx(-20)
    assert tap.bounding_box().max.Z == pytest.approx(0, abs=1e-6)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"depth": 0}, "greater than zero"),
        ({"depth": -1}, "greater than zero"),
        ({"depth": 5}, "too shallow"),
        ({"depth": 20, "material": "Wood"}, "invalid"),
    ],
)
def test_threaded_hole_rejects_invalid_parameters(kwargs, message):
    screw = SocketHeadCapScrew("M6-1", 20)
    with pytest.raises(ValueError, match=message):
        ThreadedHole(screw, **kwargs)


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
    "size,length,expected_thread_length",
    [
        ("M8-1.25", 16, 16),
        ("M8-1.25", 50, 28),
        ("M24-3", 130, 60),
        ("M42-4.5", 220, 96),
    ],
)
def test_iso4762_thread_and_grip_lengths(size, length, expected_thread_length):
    """ISO 4762 screws use the fixed reference thread length b = 2d + 12."""
    screw = SocketHeadCapScrew(size, length, "iso4762")

    assert screw.thread_length == pytest.approx(expected_thread_length)
    assert screw.grip_length == pytest.approx(length - expected_thread_length)
    assert screw.thread_length + screw.grip_length == pytest.approx(
        screw.max_thread_length
    )

    profile = screw.shank_profile()
    if screw.grip_length == 0:
        assert profile is None
    else:
        assert profile is not None
        assert profile.bounding_box().size.X == pytest.approx(
            screw.thread_diameter / 2
        )
        assert profile.bounding_box().size.Z == pytest.approx(screw.grip_length)


def test_non_iso4762_screw_remains_fully_threaded():
    """The existing ASME screw remains fully threaded."""
    screw = SocketHeadCapScrew("1/4-20", 2, "asme_b18.3")

    assert screw.thread_length == pytest.approx(screw.max_thread_length)
    assert screw.grip_length == pytest.approx(0)
    assert screw.shank_profile() is None


def test_iso7379_shoulder_and_thread_lengths():
    """ISO 7379 thread length b extends beyond the nominal shoulder length."""
    screw = ShoulderScrew("M6-1", 12)

    assert screw.grip_length == pytest.approx(12)
    assert screw.thread_offset == pytest.approx(2.5)
    assert screw.thread_length == pytest.approx(8.5)
    assert screw.bounding_box().min.Z == pytest.approx(-23)


def test_iso7379_body_hole_has_shoulder_bore():
    """Shoulder screws cut a precision shoulder bore above the thread hole."""
    screw = ShoulderScrew("M6-1", 12)
    head_offset = screw.screw_data["k"]
    body_hole = screw.make_body_hole(
        screw.clearance_hole_diameters["Normal"] / 2, 30, head_offset
    )

    thread_hole_diameter = screw.clearance_hole_diameters["Normal"]
    shoulder_bore_depth = head_offset + screw.length
    expected_volume = math.pi * (
        (screw.screw_data["ds"] / 2) ** 2 * shoulder_bore_depth
        + (thread_hole_diameter / 2) ** 2 * (30 - shoulder_bore_depth)
    )
    assert body_hole.bounding_box().size.X == pytest.approx(8)
    assert body_hole.volume == pytest.approx(expected_volume)


def test_iso7379_min_hole_depth_includes_threaded_end():
    """Shoulder-screw hole depth includes the head, shoulder, and length b."""
    screw = ShoulderScrew("M6-1", 12)

    assert screw.min_hole_depth(counter_sunk=True) == pytest.approx(28.5)
    assert screw.min_hole_depth(counter_sunk=False) == pytest.approx(23)


@pytest.mark.parametrize(
    "screw_class,fastener_type",
    [
        (HexHeadScrew, "din931"),
        (HexHeadScrew, "iso4014"),
        (HexHeadWithFlangeScrew, "din1662"),
        (HexHeadWithFlangeScrew, "din1665"),
    ],
)
@pytest.mark.parametrize(
    "length,expected_thread_length",
    [
        (20, 20),
        (125, 22),
        (126, 28),
        (200, 28),
        (201, 41),
    ],
)
def test_iso888_thread_length_bands(
    screw_class, fastener_type, length, expected_thread_length
):
    """Partially threaded bolts select the ISO 888 band from total length."""
    screw = screw_class("M8-1.25", length, fastener_type)

    assert screw.thread_length == pytest.approx(expected_thread_length)
    assert screw.grip_length == pytest.approx(length - expected_thread_length)


def test_iso4017_remains_fully_threaded():
    """ISO 4017 hexagon head screws retain their full thread."""
    screw = HexHeadScrew("M8-1.25", 50, "iso4017")

    assert screw.thread_length == pytest.approx(screw.max_thread_length)
    assert screw.grip_length == pytest.approx(0)
    assert screw.shank_profile() is None


def test_din931_and_iso4014_select_independent_dimensions():
    """DIN 931 and ISO 4014 retain their own dimensional table columns."""
    din_screw = HexHeadScrew("M2-0.4", 20, "din931")
    iso_screw = HexHeadScrew("M2-0.4", 20, "iso4014")

    assert din_screw.screw_data["k"] == pytest.approx(1.4)
    assert din_screw.screw_data["s"] == pytest.approx(3.82)
    assert iso_screw.screw_data["k"] == pytest.approx(1.6)
    assert iso_screw.screw_data["s"] == pytest.approx(4)


@pytest.mark.parametrize(
    "screw_class,fastener_type",
    [
        (ButtonHeadScrew, "iso7380_1"),
        (ButtonHeadWithCollarScrew, "iso7380_2"),
    ],
)
@pytest.mark.parametrize(
    "size,length,expected_thread_length",
    [
        ("M8-1.25", 20, 20),
        ("M8-1.25", 50, 28),
        ("M16-2", 90, 48),
    ],
)
def test_iso7380_thread_lengths(
    screw_class, fastener_type, size, length, expected_thread_length
):
    """ISO 7380 uses 2d + 12, with a 3d exception for M16."""
    screw = screw_class(size, length, fastener_type)

    assert screw.thread_length == pytest.approx(expected_thread_length)
    assert screw.grip_length == pytest.approx(length - expected_thread_length)


@pytest.mark.parametrize(
    "screw_class,fastener_type",
    [
        (ButtonHeadScrew, "iso7380_1"),
        (ButtonHeadWithCollarScrew, "iso7380_2"),
    ],
)
def test_iso7380_2022_nominal_lengths(screw_class, fastener_type):
    """The 2022 standards extend M10, M12, and M16 through 100 mm."""
    assert 100 in screw_class("M10-1.5", 100, fastener_type).nominal_lengths
    assert 100 in screw_class("M12-1.75", 100, fastener_type).nominal_lengths
    assert 100 in screw_class("M16-2", 100, fastener_type).nominal_lengths
    assert 100 not in screw_class("M8-1.25", 80, fastener_type).nominal_lengths


@pytest.mark.parametrize(
    "screw_class,fastener_type",
    [
        (CheeseHeadScrew, "iso1207"),
        (CheeseHeadScrew, "iso7048"),
        (CheeseHeadScrew, "iso14580"),
        (CounterSunkScrew, "iso2009"),
        (CounterSunkScrew, "iso7046"),
        (CounterSunkScrew, "iso14581"),
        (PanHeadScrew, "iso1580"),
        (PanHeadScrew, "iso14583"),
        (PanHeadWithCollarScrew, "din967"),
        (RaisedCheeseHeadScrew, "iso7045"),
        (RaisedCounterSunkOvalHeadScrew, "iso2010"),
        (RaisedCounterSunkOvalHeadScrew, "iso7047"),
        (RaisedCounterSunkOvalHeadScrew, "iso14584"),
    ],
)
def test_machine_screws_threaded_to_head(screw_class, fastener_type):
    """Complete machine-screw threads stop at the 2P incomplete thread."""
    screw = screw_class("M4-0.7", 20, fastener_type)

    assert screw.thread_length == pytest.approx(screw.max_thread_length - 1.4)
    assert screw.grip_length == pytest.approx(1.4)


@pytest.mark.parametrize(
    "screw_class,fastener_type,length",
    [
        (CheeseHeadScrew, "iso1207", 45),
        (CheeseHeadScrew, "iso7048", 45),
        (CheeseHeadScrew, "iso14580", 45),
        (CounterSunkScrew, "iso2009", 50),
        (CounterSunkScrew, "iso7046", 45),
        (CounterSunkScrew, "iso14581", 45),
        (PanHeadScrew, "iso1580", 45),
        (PanHeadScrew, "iso14583", 45),
        (PanHeadWithCollarScrew, "din967", 45),
        (RaisedCheeseHeadScrew, "iso7045", 45),
        (RaisedCounterSunkOvalHeadScrew, "iso2010", 50),
        (RaisedCounterSunkOvalHeadScrew, "iso7047", 45),
        (RaisedCounterSunkOvalHeadScrew, "iso14584", 45),
    ],
)
def test_long_machine_screws_use_iso888(screw_class, fastener_type, length):
    """Machine screws beyond their table cutoff use ISO 888 thread lengths."""
    screw = screw_class("M4-0.7", length, fastener_type)

    assert screw.thread_length == pytest.approx(14)
    assert screw.grip_length == pytest.approx(screw.max_thread_length - 14)


@pytest.mark.parametrize(
    "size,length",
    [
        ("M3-0.5", 8),
        ("M8-1.25", 50),
        ("M10-1.5", 100),
    ],
)
@pytest.mark.parametrize("fastener_type", ["iso10642", "iso14582"])
def test_iso_countersunk_reference_thread_length(fastener_type, size, length):
    """ISO 10642 and ISO 14582 use reference thread length b = 2d + 12."""
    screw = CounterSunkScrew(size, length, fastener_type)
    expected_thread_length = min(
        screw.max_thread_length, 2 * screw.thread_diameter + 12
    )

    assert screw.thread_length == pytest.approx(expected_thread_length)
    assert screw.grip_length == pytest.approx(
        screw.max_thread_length - expected_thread_length
    )


@pytest.mark.parametrize(
    "size,length,expected_thread_length",
    [
        ("#5-40", 3 * 0.125 * IN, (3 * 0.125 - 1 / 40) * IN),
        ("#5-40", (3 * 0.125 + 0.001) * IN, (3 * 0.125 + 0.001 - 2 / 40) * IN),
        ("#5-40", 1.125 * IN, (1.125 - 2 / 40) * IN),
        ("#5-40", 1.126 * IN, 1 * IN),
        ("#6-32", 3 * 0.138 * IN, (3 * 0.138 - 1 / 32) * IN),
        ("#6-32", (3 * 0.138 + 0.001) * IN, (3 * 0.138 + 0.001 - 2 / 32) * IN),
        ("#6-32", 2 * IN, (2 - 2 / 32) * IN),
        ("#6-32", 2.001 * IN, 1.5 * IN),
    ],
)
def test_asme_b18_6_3_thread_length(size, length, expected_thread_length):
    """ASME B18.6.3 changes rules at 3D and by numbered screw size."""
    screw = PanHeadScrew(size, length, "asme_b_18.6.3")

    assert screw.thread_length == pytest.approx(expected_thread_length)
    assert screw.grip_length == pytest.approx(length - expected_thread_length)


@pytest.mark.parametrize(
    "size,length,expected_thread_length",
    [
        ("#3-56", 0.75 * IN, (0.75 - 2 / 56) * IN),
        ("#3-56", 0.88 * IN, 0.62 * IN),
        ("#4-40", 1.00 * IN, 0.75 * IN),
        ("1/4-20", 2.00 * IN, 1.00 * IN),
        ("1/2-13", 3.00 * IN, 1.50 * IN),
        ("5/8-11", 4.00 * IN, 1.75 * IN),
        ("3/4-10", 2.50 * IN, 2.50 * IN),
        ("3/4-10", 4.00 * IN, 2.00 * IN),
        ("1-8", 4.00 * IN, 2.50 * IN),
    ],
)
def test_asme_b18_3_thread_length(size, length, expected_thread_length):
    """ASME B18.3 uses its minimum thread lengths for partial screws."""
    screw = SocketHeadCapScrew(size, length, "asme_b18.3")

    assert screw.thread_length == pytest.approx(expected_thread_length)
    assert screw.grip_length == pytest.approx(length - expected_thread_length)


@pytest.mark.parametrize("simple", [True, False])
def test_iso4762_partial_thread_geometry_spans_nominal_length(simple):
    """Simple and detailed partial threads both join the shank at the screw tip."""
    screw = SocketHeadCapScrew("M8-1.25", 50, "iso4762", simple=simple)

    assert screw.bounding_box().min.Z == pytest.approx(-50)
    assert screw.bounding_box().max.Z == pytest.approx(screw.head_height)
    assert screw.volume > 0


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
