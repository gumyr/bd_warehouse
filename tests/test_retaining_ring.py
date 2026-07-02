"""Tests for retaining ring parameter processing."""

from math import pi

import pytest

from build123d.build_common import Locations
from build123d.build_enums import Align, Mode
from build123d.build_part import BuildPart
from build123d.objects_part import Cylinder

from bd_warehouse.retaining_ring import (
    ExternalSnapRing,
    InternalSnapRing,
    RetainingRing,
    RetainingRingGroove,
)

STEEL_DENSITY_G_PER_MM3 = 0.00785


@pytest.mark.parametrize(
    "ring_class, ring_size",
    [
        (ring_class, ring_size)
        for ring_class in (ExternalSnapRing, InternalSnapRing)
        for ring_size in ring_class.sizes()
    ],
)
def test_retaining_ring_geometry(ring_class, ring_size):
    ring = ring_class(ring_size)

    assert ring.is_valid
    assert ring.volume > 0
    assert len(ring.solids()) == 1
    assert ring.bounding_box().min.Z == pytest.approx(0)
    assert ring.bounding_box().size.Z == pytest.approx(ring.ring_dict["s"])

    # W is kg/1000 pieces, which is numerically equal to grams per ring.
    modeled_mass = ring.volume * STEEL_DENSITY_G_PER_MM3
    tabulated_mass = ring.ring_dict["W"]
    assert 0.5 <= modeled_mass / tabulated_mass <= 2.0


def test_external_snap_ring_parameters():
    parameters = ExternalSnapRing.parameters("3")

    assert len(ExternalSnapRing.sizes()) == 86
    assert parameters["d1"] == 3
    assert parameters["s"] == 0.4
    assert parameters["d2_tol-"] == -0.04


def test_retaining_ring_select_by_size():
    assert RetainingRing.select_by_size("3") == {ExternalSnapRing: ["DIN471"]}
    assert RetainingRing.select_by_size("10") == {
        ExternalSnapRing: ["DIN471"],
        InternalSnapRing: ["DIN472"],
    }
    assert len(InternalSnapRing.sizes()) == 88


def test_invalid_external_snap_ring_size():
    with pytest.raises(ValueError, match="invalid"):
        ExternalSnapRing.parameters("not-a-size")


@pytest.mark.parametrize("ring_class", [ExternalSnapRing, InternalSnapRing])
def test_retaining_ring_groove(ring_class):
    ring = ring_class("10")
    groove = RetainingRingGroove(ring, mode=Mode.ADD)
    parameters = ring.ring_dict

    assert groove.is_valid
    assert len(groove.solids()) == 1
    assert groove.ring is ring
    assert groove.groove_diameter == parameters["d2"]
    assert groove.groove_width == parameters["m"]
    assert groove.clearance_diameter == parameters["d4"]
    assert groove.bounding_box().min.Z == pytest.approx(0)
    assert groove.bounding_box().max.Z == pytest.approx(parameters["m"])
    assert groove.volume == pytest.approx(
        pi
        / 4
        * abs(parameters["d4"] ** 2 - parameters["d2"] ** 2)
        * parameters["m"]
    )


def test_centered_retaining_ring_and_groove():
    ring = ExternalSnapRing("10", align=Align.CENTER)
    groove = RetainingRingGroove(ring, align=Align.CENTER, mode=Mode.ADD)

    assert ring.bounding_box().min.Z == pytest.approx(-ring.ring_dict["s"] / 2)
    assert groove.bounding_box().min.Z == pytest.approx(-ring.ring_dict["m"] / 2)


def test_retaining_ring_groove_rejects_other_objects():
    with pytest.raises(ValueError, match="only accepts"):
        RetainingRingGroove(object())


def test_external_retaining_ring_groove_in_builder():
    ring = ExternalSnapRing("10")
    parameters = ring.ring_dict
    height = 3 * parameters["m"]

    with BuildPart() as shaft:
        Cylinder(
            parameters["d1"] / 2,
            height,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
        with Locations((0, 0, parameters["m"])):
            RetainingRingGroove(ring)

    initial_volume = pi / 4 * parameters["d1"] ** 2 * height
    removed_volume = (
        pi
        / 4
        * (parameters["d1"] ** 2 - parameters["d2"] ** 2)
        * parameters["m"]
    )
    assert shaft.part.volume == pytest.approx(initial_volume - removed_volume)


def test_internal_retaining_ring_groove_in_builder():
    ring = InternalSnapRing("10")
    parameters = ring.ring_dict
    height = 3 * parameters["m"]
    body_diameter = 2 * parameters["d2"]

    with BuildPart() as bore:
        Cylinder(
            body_diameter / 2,
            height,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
        Cylinder(
            parameters["d1"] / 2,
            height,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
            mode=Mode.SUBTRACT,
        )
        with Locations((0, 0, parameters["m"])):
            RetainingRingGroove(ring)

    initial_volume = (
        pi
        / 4
        * (body_diameter**2 - parameters["d1"] ** 2)
        * height
    )
    removed_volume = (
        pi
        / 4
        * (parameters["d2"] ** 2 - parameters["d1"] ** 2)
        * parameters["m"]
    )
    assert bore.part.volume == pytest.approx(initial_volume - removed_volume)
