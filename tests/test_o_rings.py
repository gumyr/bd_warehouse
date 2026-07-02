"""Tests for ISO 3601 O-rings."""

from math import pi

import pytest

from build123d.build_enums import Mode
from build123d.build_part import BuildPart
from build123d.objects_part import Box
from build123d.topology import Sketch

from bd_warehouse.o_rings import ORing


def o_ring_for_width(width: float) -> ORing:
    """Return an O-ring from the requested cross-section family."""
    size = next(
        size
        for size in ORing.sizes()
        if ORing.parameters(size)["w"] == width
    )
    return ORing(size)


def test_iso3601_parameter_schema():
    assert ORing.types() == {"iso3601"}
    assert len(ORing.sizes("iso3601")) == 349
    assert all(len(size) == 3 and size.isdigit() for size in ORing.sizes())
    assert ORing.sizes()[:4] == ["001", "002", "003", "004"]

    parameters = ORing.parameters("025")
    assert parameters == {
        "id": 29.87,
        "w": 1.78,
        "id_tol": 0.28,
        "w_tol": 0.08,
    }
    assert ORing.select_by_size("25") == {ORing: ["iso3601"]}


def test_iso3601_o_ring_geometry():
    o_ring = ORing("025")

    assert o_ring.is_valid
    assert o_ring.dash_number == "025"
    assert o_ring.o_ring_size == "025"
    assert o_ring.o_ring_type == "iso3601"
    assert o_ring.inner_diameter == 29.87
    assert o_ring.inner_diameter_tolerance == 0.28
    assert o_ring.width == 1.78
    assert o_ring.width_tolerance == 0.08
    assert o_ring.info == "ORing(iso3601): 025"
    assert o_ring.label == "ORing-iso3601-025"
    assert o_ring.volume == pytest.approx(
        2 * pi**2 * o_ring.major_radius * o_ring.minor_radius**2
    )


@pytest.mark.parametrize("size", ORing.sizes())
def test_all_iso3601_o_ring_geometry(size):
    o_ring = ORing(size)

    assert o_ring.is_valid
    assert o_ring.volume > 0
    assert len(o_ring.solids()) == 1


def test_select_by_exact_o_ring_length():
    o_ring = ORing("025")

    assert ORing.select_by_length(o_ring.length, tolerance=0) == {
        "1.78": ("025",)
    }


def test_o_ring_subtracts_in_builder_mode():
    with BuildPart() as box:
        Box(10, 10, 10)
        ORing("004", mode=Mode.SUBTRACT)

    assert box.part.volume < 1000


@pytest.mark.parametrize("size", ["not-a-size", "1000", "999"])
def test_invalid_o_ring_size(size):
    with pytest.raises(ValueError, match="invalid"):
        ORing(size)


def test_invalid_o_ring_type():
    with pytest.raises(ValueError, match="invalid"):
        ORing("025", o_ring_type="not-a-standard")


@pytest.mark.parametrize("target", [0, -1])
def test_invalid_selection_target(target):
    with pytest.raises(ValueError, match="greater than zero"):
        ORing.select_by_inner_diameter(target)


@pytest.mark.parametrize(
    "application,gland_table",
    [
        ("static", ORing.o_ring_static_gland_data),
        ("dynamic", ORing.o_ring_dynamic_gland_data),
    ],
)
def test_gland_width_for(application, gland_table):
    for width, gland_data in gland_table.items():
        for number_backing_rings in (0, 1, 2):
            expected_width = gland_data[f"g_w_{number_backing_rings}"]
            if expected_width is not None:
                assert ORing.gland_width_for(
                    float(width), application, number_backing_rings
                ) == pytest.approx(expected_width)


def test_gland_width_for_defaults_to_static():
    assert ORing.gland_width_for(2.62) == 3.56


def test_invalid_gland_width_lookup():
    with pytest.raises(ValueError, match="application"):
        ORing.gland_width_for(2.62, "rotary")
    with pytest.raises(ValueError, match="must be 0, 1, or 2"):
        ORing.gland_width_for(2.62, number_backing_rings=3)
    with pytest.raises(ValueError, match="greater than zero"):
        ORing.gland_width_for(0)
    with pytest.raises(ValueError, match="No static gland data"):
        ORing.gland_width_for(2.0)
    with pytest.raises(ValueError, match="not supported"):
        ORing.gland_width_for(1.02, number_backing_rings=1)


@pytest.mark.parametrize(
    "width,number_backing_rings",
    [
        (float(width), number_backing_rings)
        for width, gland_data in ORing.o_ring_dynamic_gland_data.items()
        for number_backing_rings in (0, 1, 2)
        if gland_data[f"g_w_{number_backing_rings}"] is not None
    ],
)
def test_dynamic_gland_profile(width, number_backing_rings):
    o_ring = o_ring_for_width(width)
    gland_data = ORing.o_ring_dynamic_gland_data[str(width)]
    profile = o_ring.dynamic_gland_profile(number_backing_rings)
    expected_depth = (gland_data["d_min"] + gland_data["d_max"]) / 2
    expected_radius = (gland_data["g_r_min"] + gland_data["g_r_max"]) / 2

    assert isinstance(profile, Sketch)
    assert profile.is_valid
    assert profile.bounding_box().size.X == pytest.approx(
        gland_data[f"g_w_{number_backing_rings}"]
    )
    assert profile.bounding_box().size.Y == pytest.approx(expected_depth)
    assert profile.bounding_box().max.Y == pytest.approx(0)
    assert o_ring.gland_width == gland_data[f"g_w_{number_backing_rings}"]
    assert o_ring.gland_depth == expected_depth
    assert o_ring.gland_depth_tol == pytest.approx(
        gland_data["d_max"] - expected_depth
    )
    assert o_ring.gland_radius == expected_radius
    assert o_ring.gland_radius_tol == pytest.approx(
        gland_data["g_r_max"] - expected_radius
    )
    assert o_ring.gland_profile is profile


@pytest.mark.parametrize(
    "width,axial,number_backing_rings",
    [
        (float(width), axial, number_backing_rings)
        for width, gland_data in ORing.o_ring_static_gland_data.items()
        for axial in (True, False)
        for number_backing_rings in (0, 1, 2)
        if gland_data[f"g_w_{number_backing_rings}"] is not None
    ],
)
def test_static_gland_profile(width, axial, number_backing_rings):
    o_ring = o_ring_for_width(width)
    gland_data = ORing.o_ring_static_gland_data[str(width)]
    profile = o_ring.static_gland_profile(axial, number_backing_rings)
    direction = "a" if axial else "r"
    expected_depth = (
        gland_data[f"d_{direction}_min"] + gland_data[f"d_{direction}_max"]
    ) / 2

    assert isinstance(profile, Sketch)
    assert profile.is_valid
    assert profile.bounding_box().size.X == pytest.approx(
        gland_data[f"g_w_{number_backing_rings}"]
    )
    assert profile.bounding_box().size.Y == pytest.approx(expected_depth)
    assert profile.bounding_box().max.Y == pytest.approx(0)


def test_corrected_dynamic_gland_parameters():
    assert ORing.o_ring_dynamic_gland_data["3.53"]["sq_mm_max"] == 0.61
    assert ORing.o_ring_dynamic_gland_data["6.99"]["sq_mm_min"] == 0.74
    assert all(
        gland_data["g_r_min"] == 0.13
        for gland_data in ORing.o_ring_dynamic_gland_data.values()
    )


@pytest.mark.parametrize("number_backing_rings", [1, 2])
def test_unsupported_dynamic_gland_backing_rings(number_backing_rings):
    with pytest.raises(ValueError, match="not supported"):
        ORing("001").dynamic_gland_profile(number_backing_rings)


def test_invalid_gland_backing_ring_count():
    with pytest.raises(ValueError, match="must be 0, 1, or 2"):
        ORing("025").dynamic_gland_profile(3)


def test_missing_gland_cross_section_data():
    with pytest.raises(ValueError, match="No dynamic gland data"):
        ORing("025")._gland_data_for_width({}, "dynamic")
