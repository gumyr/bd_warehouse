"""Tests for parametric bushings."""

import pytest

from build123d.build_enums import Align, Mode
from build123d.build_part import BuildPart
from build123d.geometry import Axis
from build123d.objects_part import Box

from bd_warehouse.bushing import HexFlangedEccentricBushing


def test_hex_flanged_eccentric_bushing_geometry():
    bushing = HexFlangedEccentricBushing(8, 12, 16, 4, 17, 1)
    assert bushing.is_valid
    assert len(bushing.solids()) == 1
    assert bushing.overall_length == 20
    assert bushing.bounding_box().min.Z == pytest.approx(-16)
    assert bushing.bounding_box().max.Z == pytest.approx(4)
    assert bushing.bounding_box().size.Y == pytest.approx(17)

    top_edges = bushing.edges().filter_by_position(
        axis=Axis.Z, minimum=4, maximum=4
    )
    # Six edges bound the rounded hex top and one bounds the bore.
    assert len(top_edges) == 7


def test_bushing_joints():
    bushing = HexFlangedEccentricBushing(8, 12, 16, 4, 17, 1)

    outer_center = bushing.joints["outer_center"].location.position
    eccentric_top_center = bushing.joints["ecc_top_center"].location.position

    assert outer_center.X == pytest.approx(0)
    assert outer_center.Y == pytest.approx(0)
    assert outer_center.Z == pytest.approx(0)
    assert eccentric_top_center.X == pytest.approx(1)
    assert eccentric_top_center.Y == pytest.approx(0)
    assert eccentric_top_center.Z == pytest.approx(4)


def test_bushing_works_in_builder_mode():
    bushing = HexFlangedEccentricBushing(8, 12, 16, 4, 17, 1, mode=Mode.ADD)
    with BuildPart() as assembly:
        Box(30, 30, 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
        HexFlangedEccentricBushing(8, 12, 16, 4, 17, 1)

    assert assembly.part.is_valid
    assert assembly.part.volume < 30 * 30 * 2 + bushing.volume


@pytest.mark.parametrize(
    "arguments,match",
    [
        ((8, -12, 16, 4, 17, 1), "body_diameter"),
        ((8, 12, 16, 4, 0, 1), "hex_size"),
        ((8, 12, 16, 4, 17, -1), "eccentricity"),
        ((8, 12, 16, 4, 17, 2), "twice eccentricity"),
        ((8, 12, 16, 4, 11, 1), "hex_size"),
    ],
)
def test_invalid_bushing_dimensions(arguments, match):
    with pytest.raises(ValueError, match=match):
        HexFlangedEccentricBushing(*arguments)
