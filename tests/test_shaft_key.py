"""Tests for DIN 6885-1 shaft keys and keyways."""

from math import pi

import pytest

from build123d.build_enums import Align, Mode
from build123d.build_part import BuildPart
from build123d.objects_part import Box

from bd_warehouse.shaft_key import Keyway, ShaftKey


@pytest.mark.parametrize(
    "shaft_diameter,key_form",
    [
        (shaft_diameter, key_form)
        for shaft_diameter in ShaftKey.sizes()
        for key_form in ("A", "B")
    ],
)
def test_parallel_key_geometry(shaft_diameter, key_form):
    parameters = ShaftKey.parameters(shaft_diameter)
    length = 2 * parameters["b"]
    key = ShaftKey(shaft_diameter, length, key_form)

    expected_area = (
        parameters["b"] * (length - parameters["b"])
        + pi * parameters["b"] ** 2 / 4
        if key_form == "A"
        else length * parameters["b"]
    )
    assert key.is_valid
    assert len(key.solids()) == 1
    assert key.width == parameters["b"]
    assert key.key_height == parameters["h"]
    assert key.plan_area == pytest.approx(expected_area)
    assert key.volume == pytest.approx(expected_area * parameters["h"])
    assert key.bounding_box().size.X == pytest.approx(length)
    assert key.bounding_box().size.Y == pytest.approx(parameters["b"])
    assert key.bounding_box().min.Z == pytest.approx(0)
    assert key.bounding_box().max.Z == pytest.approx(parameters["h"])


def test_parallel_key_parameters_and_selection():
    assert len(ShaftKey.sizes()) == 31
    assert all(isinstance(size, int) for size in ShaftKey.sizes())
    assert ShaftKey.parameters(25) == {
        "b": 8,
        "h": 7,
        "t2": 3.3,
        "t2_tol+": 0.2,
        "t4": 4,
        "t4_tol+": 0.2,
    }
    assert ShaftKey.select_by_size(25) == {ShaftKey: ["DIN6885-1"]}


def test_parallel_key_metadata():
    key = ShaftKey(25.0, 40, "A")

    assert key.shaft_diameter == 25
    assert isinstance(key.shaft_diameter, int)
    assert key.info == "ShaftKey(DIN6885-1, Form A): 25x40"
    assert key.label == "ShaftKey-DIN6885-1-FormA-25x40"


@pytest.mark.parametrize("key_form", ["A", "B"])
@pytest.mark.parametrize("keyway_type", ["shaft", "hub"])
@pytest.mark.parametrize(
    "fit,expected_shaft_tolerance,expected_hub_tolerance",
    [
        ("Tight", "P9", "P9"),
        ("Loose", "N9", "JS9"),
        ("Sliding", "H9", "D10"),
    ],
)
def test_keyway_geometry_and_fits(
    key_form, keyway_type, fit, expected_shaft_tolerance, expected_hub_tolerance
):
    key = ShaftKey(25, 40, key_form)
    keyway = Keyway(key, keyway_type, fit, mode=Mode.ADD)
    depth_parameter = "t4" if keyway_type == "shaft" else "t2"
    tolerance_parameter = f"{depth_parameter}_tol+"

    assert keyway.is_valid
    assert keyway.keyway_depth == key.key_dict[depth_parameter]
    assert keyway.keyway_depth_tolerance == key.key_dict[tolerance_parameter]
    assert keyway.width_tolerance == (
        expected_shaft_tolerance
        if keyway_type == "shaft"
        else expected_hub_tolerance
    )
    expected_area = (
        keyway.width * (keyway.length - keyway.width)
        + pi * keyway.width**2 / 4
        if key_form == "A"
        else keyway.length * keyway.width
    )
    assert keyway.volume == pytest.approx(expected_area * keyway.keyway_depth)
    bounding_box = keyway.bounding_box()
    shaft_radius = key.shaft_diameter / 2
    if keyway_type == "shaft":
        assert bounding_box.min.X == pytest.approx(
            shaft_radius - keyway.keyway_depth
        )
        assert bounding_box.max.X == pytest.approx(shaft_radius)
    else:
        assert bounding_box.min.X == pytest.approx(shaft_radius)
        assert bounding_box.max.X == pytest.approx(
            shaft_radius + keyway.keyway_depth
        )
    assert bounding_box.min.Y == pytest.approx(-keyway.width / 2)
    assert bounding_box.max.Y == pytest.approx(keyway.width / 2)
    assert bounding_box.min.Z == pytest.approx(-keyway.length / 2)
    assert bounding_box.max.Z == pytest.approx(keyway.length / 2)


@pytest.mark.parametrize(
    "keyway_type,fit,expected_tolerance,expected_min,expected_max",
    [
        ("shaft", "Tight", "P9", 7.949, 7.985),
        ("hub", "Tight", "P9", 7.949, 7.985),
        ("shaft", "Loose", "N9", 7.964, 8.000),
        ("hub", "Loose", "JS9", 7.982, 8.018),
        ("shaft", "Sliding", "H9", 8.000, 8.036),
        ("hub", "Sliding", "D10", 8.040, 8.098),
    ],
)
def test_keyway_iso_286_widths(
    keyway_type, fit, expected_tolerance, expected_min, expected_max
):
    keyway = Keyway(ShaftKey(25, 40), keyway_type, fit, mode=Mode.ADD)

    assert keyway.nominal_width == 8
    assert keyway.width_tolerance == expected_tolerance
    assert keyway.min_width == pytest.approx(expected_min)
    assert keyway.max_width == pytest.approx(expected_max)
    assert keyway.width == pytest.approx((expected_min + expected_max) / 2)


def test_keyway_subtracts_in_builder_mode():
    key = ShaftKey(25, 20, "A")

    with BuildPart() as keyed_part:
        Box(
            30,
            20,
            20,
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
        )
        Keyway(key)

    assert keyed_part.part.volume == pytest.approx(
        30 * 20 * 20 - Keyway(key, mode=Mode.ADD).volume
    )


def test_hub_keyway_broach_profile():
    keyway = Keyway(ShaftKey(25, 20), "hub", "Loose", mode=Mode.ADD)
    profile = keyway.broach_profile()
    bounding_box = profile.bounding_box()
    profile_depth = keyway.key.shaft_diameter / 2 + keyway.keyway_depth

    assert profile.is_valid
    assert profile.area == pytest.approx(profile_depth * keyway.width)
    assert bounding_box.min.X == pytest.approx(0)
    assert bounding_box.max.X == pytest.approx(profile_depth)
    assert bounding_box.min.Y == pytest.approx(-keyway.width / 2)
    assert bounding_box.max.Y == pytest.approx(keyway.width / 2)


def test_shaft_keyway_has_no_broach_profile():
    keyway = Keyway(ShaftKey(25, 20), "shaft", mode=Mode.ADD)

    with pytest.raises(ValueError, match="hub keyways"):
        keyway.broach_profile()


@pytest.mark.parametrize("shaft_diameter", [0, -1, 19, 51])
def test_invalid_shaft_diameter(shaft_diameter):
    with pytest.raises(ValueError):
        ShaftKey(shaft_diameter, 20)


@pytest.mark.parametrize(
    "shaft_diameter", [25.5, "25", True, float("inf"), float("nan")]
)
def test_non_integer_shaft_diameter(shaft_diameter):
    with pytest.raises(ValueError, match="whole number"):
        ShaftKey(shaft_diameter, 20)


@pytest.mark.parametrize("length", [0, -1, 7])
def test_invalid_parallel_key_length(length):
    with pytest.raises(ValueError, match="length"):
        ShaftKey(25, length)


def test_invalid_parallel_key_form():
    with pytest.raises(ValueError, match="key_form"):
        ShaftKey(25, 20, "C")


def test_invalid_keyway_inputs():
    key = ShaftKey(25, 20)

    with pytest.raises(ValueError, match="ShaftKey"):
        Keyway(object())
    with pytest.raises(ValueError, match="keyway_type"):
        Keyway(key, "invalid")
    with pytest.raises(ValueError, match="fit"):
        Keyway(key, fit="invalid")
