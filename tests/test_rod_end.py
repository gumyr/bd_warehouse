"""

Rod End Tests

name: test_rod_end.py
by:   Gabriel Jesus
date: September 10th 2026

desc: Basic pytests for the rod end classes.

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

from math import atan2, degrees, hypot

import pytest

from build123d.build_enums import Align, Keep, Mode
from build123d.geometry import Axis, Plane, Pos
from build123d.objects_part import Box, Cylinder, Sphere
from build123d.operations_generic import split

from bd_warehouse.rod_end import FemaleThreadRodEnd, MaleThreadRodEnd, RodEnd

# ISO 12240-1:1998 table 4, radial spherical plain bearings, dimension series K.
# Its note states that the bearings of this series are the ones incorporated in
# the rod ends of ISO 12240-4:1998 table 5, so every rod end this module builds
# must agree with these values.  bore: (D, B, C, d1, dk)
ISO_12240_1_SERIES_K = {
    5: (13, 8, 6, 7.7, 11.1),
    6: (16, 9, 6.75, 8.9, 12.7),
    8: (19, 12, 9, 10.3, 15.8),
    10: (22, 14, 10.5, 12.9, 19.0),
    12: (26, 16, 12, 15.4, 22.2),
    14: (29, 19, 13.5, 16.8, 25.4),
    16: (32, 21, 15, 19.3, 28.5),
    18: (35, 23, 16.5, 21.8, 31.7),
    20: (40, 25, 18, 24.3, 34.9),
    22: (42, 28, 20, 25.8, 38.1),
    25: (47, 31, 22, 29.5, 42.8),
    30: (55, 37, 25, 34.8, 50.8),
    35: (65, 43, 30, 40.3, 59.0),
}

# The 35 mm bore row of the DIN 648 catalogue departs from ISO 12240-1 series K:
# the catalogue narrows the outer ring and shrinks the inner ring's end faces.
# The catalogue wins - it is what is actually manufactured - but the divergence
# is recorded here rather than hidden.
ISO_DIVERGENT_SIZES = {"M35"}

ALL_CASES = [
    (rod_end_class, rod_end_type, size)
    for rod_end_class in RodEnd.__subclasses__()
    for rod_end_type in rod_end_class.types()
    for size in rod_end_class.sizes(rod_end_type)
]


@pytest.mark.parametrize("rod_end_class, rod_end_type, size", ALL_CASES)
def test_rod_end_builds(rod_end_class: type[RodEnd], rod_end_type: str, size: str):
    """Every catalogued size builds into a valid three part compound."""
    rod_end = rod_end_class(size=size, rod_end_type=rod_end_type)

    assert rod_end.is_valid
    assert {part.label for part in rod_end.children} == {
        "Housing",
        "BearingSocket",
        "InternalRing",
    }
    assert all(part.material is not None for part in rod_end.children)
    assert all(part.volume > 0 for part in rod_end.children)

    assert rod_end.bore_diameter > 0
    assert rod_end.ball_diameter > rod_end.bore_diameter
    assert rod_end.eye_diameter > rod_end.socket_diameter > rod_end.ball_diameter
    assert rod_end.width >= rod_end.eye_width
    assert 0 < rod_end.tilt_angle < 45
    assert rod_end.static_load_rating > 0
    assert size in rod_end.info
    assert rod_end.rod_end_class == rod_end_class.__name__


@pytest.mark.parametrize("rod_end_class, rod_end_type, size", ALL_CASES)
def test_overall_length_closes(
    rod_end_class: type[RodEnd], rod_end_type: str, size: str
):
    """l2 = l1 + d4/2 - an independent chain the catalogue closes on every row."""
    rod_end = rod_end_class(size=size, rod_end_type=rod_end_type)

    assert rod_end.overall_length == pytest.approx(
        rod_end.center_to_end + rod_end.eye_diameter / 2
    )


@pytest.mark.parametrize("rod_end_class, rod_end_type, size", ALL_CASES)
def test_agrees_with_iso_12240_1(
    rod_end_class: type[RodEnd], rod_end_type: str, size: str
):
    """The spherical plain bearing inside matches ISO 12240-1 series K."""
    rod_end = rod_end_class(size=size, rod_end_type=rod_end_type)
    iso_D, iso_B, iso_C, iso_d1, iso_dk = ISO_12240_1_SERIES_K[
        round(rod_end.bore_diameter)
    ]

    assert rod_end.socket_diameter == pytest.approx(iso_D)
    assert rod_end.width == pytest.approx(iso_B)

    if size in ISO_DIVERGENT_SIZES:
        pytest.skip(f"{size} is a documented catalogue departure from ISO 12240-1")

    assert rod_end.eye_width == pytest.approx(iso_C, abs=0.1)
    assert rod_end.ball_diameter == pytest.approx(iso_dk, abs=0.1)


def test_ball_diameter_is_derived_not_tabulated():
    """dk is not printed on the catalogue sheet - it closes on d3 and b1."""
    rod_end = FemaleThreadRodEnd("M10")

    assert rod_end.ball_diameter == pytest.approx(
        2 * hypot(rod_end.ring_face_diameter / 2, rod_end.width / 2)
    )


def test_m10_geometry():
    """Bounding box and stations of the 10 mm bore size, from the DIN 648 table."""
    rod_end = FemaleThreadRodEnd("M10")
    bbox = rod_end.bounding_box()

    # The origin is the ball centre, the bore runs along X, the shank along -Z.
    assert bbox.max.Z == pytest.approx(28 / 2)  # top of the eye, d4/2
    assert bbox.min.Z == pytest.approx(-43)  # thread face, l1
    assert bbox.size.Z == pytest.approx(57)  # l2
    assert bbox.size.Y == pytest.approx(28)  # eye diameter d4
    # Widest of the ring (b1), the shank (d5) and the collar (d6).
    assert bbox.size.X == pytest.approx(19)

    assert rod_end.thread_size == "M10"
    assert rod_end.thread_diameter == pytest.approx(10)
    assert rod_end.thread_pitch == pytest.approx(1.5)
    assert rod_end.thread_depth == pytest.approx(20)
    assert rod_end.static_load_rating == pytest.approx(1.4)
    assert rod_end.tilt_angle == pytest.approx(13)


def test_thread_minor_diameter():
    """The tapped hole is drawn at the ISO 261 basic minor diameter."""
    rod_end = FemaleThreadRodEnd("M10")

    assert rod_end.thread_minor_diameter == pytest.approx(10 - 1.0825 * 1.5)
    assert rod_end.thread_minor_diameter < rod_end.thread_diameter


def test_a_rod_at_the_minor_diameter_screws_in_without_overlap():
    """A mating rod drawn at the minor diameter fits the tapped hole."""
    rod_end = FemaleThreadRodEnd("M10")
    engagement = rod_end.thread_depth
    rod = Pos(Z=-rod_end.center_to_end) * Cylinder(
        radius=rod_end.thread_minor_diameter / 2,
        height=engagement,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )

    assert (rod & _part(rod_end, "Housing")).volume == pytest.approx(0, abs=1e-6)


def test_fine_pitch_thread_designation():
    """Sizes whose catalogue thread is not the coarse one report the pitch."""
    assert FemaleThreadRodEnd("M18").thread_size == "M18x1.5"
    assert FemaleThreadRodEnd("M25").thread_size == "M24x2"
    assert FemaleThreadRodEnd("M35").thread_size == "M36x2"


def _part(rod_end: RodEnd, label: str):
    """The named piece of the compound - labels live on children, not solids."""
    return next(child for child in rod_end.children if child.label == label)


def _above(part, station: float):
    """Whatever of a solid lies above a station on the shank axis."""
    return split(
        part, bisect_by=Plane.XY.offset(station), keep=Keep.TOP, mode=Mode.PRIVATE
    )


def _slab(part, station: float, thickness: float = 0.2):
    """A thin slice of a solid, taken across the shank axis."""
    reach = 4 * part.bounding_box().size.X
    return part & Pos(Z=station) * Box(reach, reach, thickness, mode=Mode.PRIVATE)


def test_bore_is_clear():
    """A pin of the nominal bore diameter passes through without fouling."""
    rod_end = FemaleThreadRodEnd("M10")
    # The bore runs along X, so swing a cylinder from Z onto it.
    pin = Cylinder(
        radius=rod_end.bore_diameter / 2,
        height=4 * rod_end.width,
        rotation=(0, 90, 0),
    )

    assert (pin & _part(rod_end, "Housing")).volume == pytest.approx(0, abs=1e-6)
    assert (pin & _part(rod_end, "BearingSocket")).volume == pytest.approx(0, abs=1e-6)


def test_housing_is_clear_of_the_ball():
    """The ball's spherical envelope is not fouled by housing material.

    Nothing relieves it: the socket seat clears the eye, and every point of
    the blend cone is d4/2 or more from the ball centre by construction.
    """
    rod_end = FemaleThreadRodEnd("M10")
    envelope = Sphere(radius=rod_end.ball_diameter / 2)

    assert (envelope & _part(rod_end, "Housing")).volume == pytest.approx(0, abs=1e-6)


@pytest.mark.parametrize("rod_end_class, rod_end_type, size", ALL_CASES)
def test_blend_cone_touches_the_eye_circle(
    rod_end_class: type[RodEnd], rod_end_type: str, size: str
):
    """The blend is a BLEND_ANGLE cone tangent to the eye, which fixes it.

    Both halves are checked against each other: the station the cone reaches
    the eye at lies on the eye's outer circle, and the flank from where it
    leaves the shank up to that station runs at BLEND_ANGLE.
    """
    rod_end = rod_end_class(size=size, rod_end_type=rod_end_type)
    eye_radius = rod_end.eye_diameter / 2

    assert hypot(
        rod_end.blend_tangent_radius, rod_end.blend_tangent_station
    ) == pytest.approx(eye_radius)
    assert degrees(
        atan2(
            rod_end.blend_tangent_radius - rod_end.shank_diameter / 2,
            rod_end.blend_tangent_station - rod_end.blend_base,
        )
    ) == pytest.approx(rod_end.BLEND_ANGLE)

    assert rod_end.blend_base < rod_end.blend_tangent_station < 0
    assert rod_end.blend_tangent_radius > rod_end.shank_diameter / 2
    assert rod_end.flank_flare_station <= rod_end.blend_base


@pytest.mark.parametrize("rod_end_class, rod_end_type, size", ALL_CASES)
def test_the_head_is_no_wider_than_the_eye(
    rod_end_class: type[RodEnd], rod_end_type: str, size: str
):
    """Nothing stands out alongside the eye, on either variant.

    The tapped type's shank is thicker than the eye is wide on every size, so
    taken straight up to the ball it would stand out either side of the head.
    Both catalogue front views show it does not: the flanks run the whole
    height of the head, b2 apart. The blend cone is wider than the eye too,
    and the same flanks hold it.
    """
    rod_end = rod_end_class(size=size, rod_end_type=rod_end_type)
    head = _above(_part(rod_end, "Housing"), rod_end.blend_base)

    assert rod_end.blend_tangent_radius > rod_end.eye_width / 2
    assert head.bounding_box().size.X == pytest.approx(rod_end.eye_width)


def test_head_silhouette_is_the_eye_circle():
    """Above the tangency the head is a plain circle of d4, nothing outside."""
    rod_end = FemaleThreadRodEnd("M20")
    crown = _above(_part(rod_end, "Housing"), rod_end.blend_tangent_station)
    eye = Cylinder(rod_end.eye_diameter / 2, 2 * rod_end.eye_width, rotation=(0, 90, 0))

    assert (crown - eye).volume == pytest.approx(0, abs=1e-6)


@pytest.mark.parametrize(
    "rod_end", [FemaleThreadRodEnd("M20"), MaleThreadRodEnd("M30")]
)
def test_shank_is_round_below_the_flare(rod_end: RodEnd):
    """Where the shank is the thicker of the two, the flanks flare off it."""
    housing = _part(rod_end, "Housing")
    assert rod_end.shank_diameter > rod_end.eye_width
    assert rod_end.flank_flare_station < rod_end.blend_base

    round_shank = _slab(housing, rod_end.flank_flare_station - 1).bounding_box()
    assert round_shank.size.X == pytest.approx(rod_end.shank_diameter, abs=0.01)
    assert round_shank.size.Y == pytest.approx(rod_end.shank_diameter, abs=0.01)

    # Halfway along the flare the flanks are still there, and narrower.
    flaring = _slab(
        housing, (rod_end.blend_base + rod_end.flank_flare_station) / 2
    ).bounding_box()
    assert rod_end.eye_width < flaring.size.X < rod_end.shank_diameter
    assert flaring.size.Y == pytest.approx(rod_end.shank_diameter, abs=0.01)


def test_a_thin_stem_needs_no_flare():
    """Below the 14 mm bore the threaded stem is thinner than the eye is wide.

    There is then nothing to flare: the flanks simply stop where the blend
    runs out onto the stem.
    """
    rod_end = MaleThreadRodEnd("M10")
    assert rod_end.shank_diameter < rod_end.eye_width
    assert rod_end.flank_flare_station == pytest.approx(rod_end.blend_base)

    stem = _slab(_part(rod_end, "Housing"), rod_end.blend_base - 1).bounding_box()
    assert stem.size.X == pytest.approx(rod_end.shank_diameter, abs=0.01)
    assert stem.size.Y == pytest.approx(rod_end.shank_diameter, abs=0.01)


# Nothing dimensions the blend angle. Three drawings and one chain of printed
# numbers bear on it, and they span about 1.5 degrees either way.
BLEND_ANGLE_READINGS = {
    "JW Winco threaded stem drawing, 12 mm bore": 30.0,
    "JW Winco threaded stem table, the l1 - l3 chain": 29.4,
    "JW Winco tapped drawing, 25 mm bore": 31.5,
    "mbo Osswald series K male drawing": 31.4,
}


@pytest.mark.parametrize("source, reading", BLEND_ANGLE_READINGS.items())
def test_blend_angle_agrees_with_every_reading(source: str, reading: float):
    """The one angle taken on the drawings' word, against all four readings."""
    assert RodEnd.BLEND_ANGLE == pytest.approx(reading, abs=1.6), source


def test_blend_agrees_with_the_tapped_sheet():
    """The blend measured off the tapped type's drawing, which dimensions none of it.

    Drawn at the 25 mm bore size; its own lines, measured at 600 dpi and
    scaled off d4, put the cone's flank at 31.5 deg, its junction with the
    shank at -31.1 mm and the arc where the flanks flare off onto the shank at
    -39.8 mm. The bold line weight is worth about 0.6 mm at that scale.
    """
    rod_end = FemaleThreadRodEnd("M25")

    assert rod_end.BLEND_ANGLE == pytest.approx(31.5, abs=1.6)
    assert rod_end.blend_base == pytest.approx(-31.1, abs=0.6)
    assert rod_end.flank_flare_station == pytest.approx(-39.8, abs=1.2)


def test_blend_agrees_with_the_threaded_stem_sheet():
    """The same blend measured off the threaded stem's drawing.

    Drawn at the 12 mm bore size, whose stem is thin enough to tell a fixed
    angle apart from one that varies with the shank: the two candidates sit
    5 mm apart there, and the sheet picks the fixed angle.
    """
    rod_end = MaleThreadRodEnd("M12")

    assert rod_end.BLEND_ANGLE == pytest.approx(30.0, abs=0.3)
    assert rod_end.blend_base == pytest.approx(-21.5, abs=0.3)


# The two largest sizes carry more thread than the blend leaves room for.
@pytest.mark.parametrize(
    "size", [s for s in MaleThreadRodEnd.sizes("DIN648K") if s not in {"M25", "M30"}]
)
def test_thread_starts_where_the_blend_ends(size: str):
    """l1 - l3 is an independent chain onto the blend, and it closes.

    The threaded stem sheet prints the thread's length but says nothing about
    the blend. Where the thread starts - l1 - l3 down from the ball centre -
    lands within a millimetre of the derived blend_base on every size but the
    two largest, which is a second source for the blend angle: solving the
    chain for it gives 28.7 deg to 30.2 deg.
    """
    rod_end = MaleThreadRodEnd(size)
    thread_start = -(rod_end.center_to_end - rod_end.thread_length)

    assert rod_end.blend_base == pytest.approx(thread_start, abs=1.1)


def test_male_stem_is_the_thread_diameter():
    """The sheet prints no shank dimension because the stem is the thread."""
    rod_end = MaleThreadRodEnd("M25")

    assert rod_end.thread_size == "M24x2"
    assert rod_end.shank_diameter == pytest.approx(24)
    assert rod_end.shank_diameter == rod_end.thread_diameter


def test_m12_male_geometry():
    """Bounding box and stations of the 12 mm bore threaded stem."""
    rod_end = MaleThreadRodEnd("M12")
    bbox = rod_end.bounding_box()

    assert bbox.max.Z == pytest.approx(32 / 2)  # top of the eye, d4/2
    assert bbox.min.Z == pytest.approx(-54)  # end of the stem, l1
    assert bbox.size.Z == pytest.approx(70)  # l2
    assert bbox.size.Y == pytest.approx(32)  # eye diameter d4
    # The ball, at b1, is wider than the stem: there is no collar to beat it.
    assert bbox.size.X == pytest.approx(16)

    assert rod_end.thread_size == "M12"
    assert rod_end.thread_length == pytest.approx(32)
    assert rod_end.static_load_rating == pytest.approx(1.7)


def test_male_stem_has_a_lead_in_chamfer():
    """The stem's end is chamfered down to the thread's minor diameter.

    The sheet draws the end face 9.9 mm across on the 12 mm bore size, which
    is the basic minor diameter to within the width of its own lines.
    """
    rod_end = MaleThreadRodEnd("M12")
    end_face = _part(rod_end, "Housing").faces().sort_by(Axis.Z)[0]

    assert end_face.center().Z == pytest.approx(-rod_end.center_to_end)
    assert end_face.bounding_box().size.X == pytest.approx(
        rod_end.thread_minor_diameter
    )
    assert end_face.bounding_box().size.X == pytest.approx(9.9, abs=0.3)


def test_invalid_size():
    with pytest.raises(ValueError):
        FemaleThreadRodEnd("M7")


def test_invalid_type():
    with pytest.raises(ValueError):
        FemaleThreadRodEnd("M10", rod_end_type="ACME")


def test_types_and_sizes():
    """Each variant brings its own table - the threaded stem stops at 30 mm."""
    assert FemaleThreadRodEnd.types() == {"DIN648K"}
    assert MaleThreadRodEnd.types() == {"DIN648K"}

    tapped = FemaleThreadRodEnd.sizes("DIN648K")
    assert (tapped[0], tapped[-1], len(tapped)) == ("M5", "M35", 13)

    stem = MaleThreadRodEnd.sizes("DIN648K")
    assert (stem[0], stem[-1], len(stem)) == ("M5", "M30", 12)
