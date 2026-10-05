"""

Gears Tests

name: test_gears.py
by:   Gumyr
date: May 13, 2025

desc: Basic pytests for the gear classes.

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

import math

import pytest
from bd_warehouse.gear import (
    HelicalGear,
    RackGear,
    RackGearPlan,
    SpurGear,
    SpurGearPlan,
    Worm,
    WormFlank,
    WormGear,
    WormWheel,
)
from build123d import Compound, Edge, GeomType, Vector, Vertex


def test_spur_gear_plan():
    module, tooth_count, pressure_angle, root_fillet = (1, 14, 14.5, 0.5)
    spur_gear_plan = SpurGearPlan(
        module=module,
        tooth_count=tooth_count,
        pressure_angle=pressure_angle,
        root_fillet=root_fillet,
    )
    outside_arcs = (
        spur_gear_plan.edges().filter_by(GeomType.CIRCLE).group_by(Edge.radius)[-1]
    )
    # Each tooth has two tip edges
    assert len(outside_arcs) == 2 * tooth_count
    # Validate the addendum_radius
    assert outside_arcs[0].radius == pytest.approx(
        module * tooth_count / 2 + module, abs=1e-5
    )
    # Face should point up
    assert spur_gear_plan.face().normal_at() == pytest.approx(Vector(0, 0, 1), abs=1e-5)


def test_invalid_spur_gear_root_fillet():
    # Too large root fillet
    with pytest.raises(Exception):
        SpurGearPlan(
            module=1,
            tooth_count=100,
            pressure_angle=14.5,
            root_fillet=0.5,
        )


def test_spur_gear_plan_tip_fillet():
    module, tooth_count, pressure_angle, tip_fillet = (1.55, 35, 20, 0.2)
    unfilleted = SpurGearPlan(module, tooth_count, pressure_angle)
    zero_fillet = SpurGearPlan(module, tooth_count, pressure_angle, tip_fillet=0)
    filleted = SpurGearPlan(module, tooth_count, pressure_angle, tip_fillet=tip_fillet)

    assert zero_fillet.area == pytest.approx(unfilleted.area)
    assert len(zero_fillet.edges()) == len(unfilleted.edges())
    assert filleted.is_valid
    assert filleted.area < unfilleted.area
    tip_arcs = [
        e
        for e in filleted.edges().filter_by(GeomType.CIRCLE)
        if e.radius == pytest.approx(tip_fillet)
    ]
    # Each tooth has two rounded tip corners
    assert len(tip_arcs) == 2 * tooth_count
    # The rounds stay on the tip land, so the outside diameter is unchanged
    outside_arcs = filleted.edges().filter_by(GeomType.CIRCLE).group_by(Edge.radius)
    assert outside_arcs[-1][0].radius == pytest.approx(unfilleted.addendum_radius)


def test_spur_gear_tip_fillet():
    sharp = SpurGear(1.55, 35, 20, 8, root_fillet=0.3)
    rounded = SpurGear(1.55, 35, 20, 8, root_fillet=0.3, tip_fillet=0.2)

    assert rounded.is_valid
    assert rounded.volume < sharp.volume
    assert rounded.area < sharp.area
    # One cylindrical face per rounded tip corner
    assert len(rounded.faces()) == len(sharp.faces()) + 2 * 35


@pytest.mark.parametrize("tip_fillet", [-0.1, 0.95, 5])
def test_invalid_spur_gear_tip_fillet(tip_fillet):
    with pytest.raises(ValueError, match="tip_fillet|tip fillet"):
        SpurGearPlan(
            module=1.55, tooth_count=35, pressure_angle=20, tip_fillet=tip_fillet
        )


def test_spur_gear():
    module, tooth_count, pressure_angle, root_fillet, thickness = (2, 12, 14.5, 0.5, 5)
    spur_gear = SpurGear(
        module=module,
        tooth_count=tooth_count,
        pressure_angle=pressure_angle,
        root_fillet=root_fillet,
        thickness=thickness,
    )

    # Validate size
    addendum_radius = module * tooth_count / 2 + module
    bbox = spur_gear.bounding_box()
    assert bbox.size == pytest.approx(
        Vector(2 * addendum_radius, 2 * addendum_radius, thickness), abs=1e-5
    )


def test_rack_gear_plan():
    module, tooth_count, pressure_angle = (2, 8, 20)
    rack_plan = RackGearPlan(
        module=module,
        tooth_count=tooth_count,
        pressure_angle=pressure_angle,
        module_system="transverse",
    )

    pitch = math.pi * module
    addendum = module
    dedendum = 1.25 * module
    base_height = 2 * module
    bbox = rack_plan.bounding_box()

    assert rack_plan.is_valid
    assert rack_plan.pitch == pytest.approx(pitch)
    assert rack_plan.pitch_length == pytest.approx(tooth_count * pitch)
    assert rack_plan.tooth_height == pytest.approx(addendum + dedendum)
    assert bbox.min == pytest.approx(
        Vector(-rack_plan.pitch_length / 2, -dedendum - base_height, 0)
    )
    assert bbox.max == pytest.approx(Vector(rack_plan.pitch_length / 2, addendum, 0))
    assert rack_plan.face().normal_at() == pytest.approx(Vector(0, 0, 1))


def test_straight_rack_gear():
    module, tooth_count, pressure_angle, thickness = (2, 8, 20, 8)
    rack_plan = RackGearPlan(
        module, tooth_count, pressure_angle, module_system="transverse"
    )
    rack = RackGear(
        module,
        tooth_count,
        pressure_angle,
        thickness,
        module_system="transverse",
    )
    pinion = SpurGear(module, 16, pressure_angle, thickness)

    assert rack.is_valid
    assert rack.lateral_offset == pytest.approx(0)
    assert rack.volume == pytest.approx(rack_plan.area * thickness)
    assert rack.bounding_box().size == pytest.approx(
        Vector(rack.pitch_length, thickness, rack.tooth_height + rack.base_height)
    )
    assert rack.bounding_box().min.Z == pytest.approx(-rack.dedendum - rack.base_height)
    assert rack.bounding_box().max.Z == pytest.approx(rack.addendum)
    assert rack.pitch == pytest.approx(2 * math.pi * pinion.pitch_radius / 16)


def test_normal_module_helical_rack_gear():
    module, tooth_count, pressure_angle = (2, 8, 20)
    helix_angle, thickness = (-25, 8)
    rack_plan = RackGearPlan(
        module,
        tooth_count,
        pressure_angle,
        helix_angle=helix_angle,
        module_system="normal",
        root_fillet=0.5,
    )
    rack = RackGear(
        module,
        tooth_count,
        pressure_angle,
        thickness,
        helix_angle=helix_angle,
        module_system="normal",
        root_fillet=0.5,
    )
    pinion = HelicalGear(
        module,
        16,
        pressure_angle,
        -helix_angle,
        thickness,
        module_system="normal",
    )

    expected_transverse_module = module / math.cos(math.radians(helix_angle))
    expected_pressure_angle = math.degrees(
        math.atan(
            math.tan(math.radians(pressure_angle)) / math.cos(math.radians(helix_angle))
        )
    )
    expected_offset = thickness * math.tan(math.radians(helix_angle))

    assert rack.is_valid
    assert rack.normal_module == pytest.approx(module)
    assert rack.transverse_module == pytest.approx(expected_transverse_module)
    assert rack.transverse_pressure_angle == pytest.approx(expected_pressure_angle)
    assert rack.pitch == pytest.approx(math.pi * expected_transverse_module)
    assert rack.lateral_offset == pytest.approx(expected_offset)
    assert rack.volume == pytest.approx(rack_plan.area * thickness)
    assert rack.bounding_box().size.X == pytest.approx(
        rack.pitch_length + abs(expected_offset)
    )
    assert rack.transverse_module == pytest.approx(pinion.transverse_module)
    assert rack.transverse_pressure_angle == pytest.approx(
        pinion.transverse_pressure_angle
    )
    assert rack.pitch == pytest.approx(2 * math.pi * pinion.pitch_radius / 16)


def test_rack_root_fillet():
    unfilleted = RackGearPlan(2, 8, 20)
    zero_fillet = RackGearPlan(2, 8, 20, root_fillet=0)
    filleted = RackGearPlan(2, 8, 20, root_fillet=0.5)

    assert zero_fillet.area == pytest.approx(unfilleted.area)
    assert len(zero_fillet.edges()) == len(unfilleted.edges())
    assert filleted.area > unfilleted.area
    assert len(filleted.edges().filter_by(GeomType.CIRCLE)) == 2 * 8

    with pytest.raises(ValueError, match="Invalid root fillet radius"):
        RackGearPlan(2, 8, 20, root_fillet=1)


def test_rack_tip_fillet():
    unfilleted = RackGearPlan(2, 8, 20)
    zero_fillet = RackGearPlan(2, 8, 20, tip_fillet=0)
    filleted = RackGearPlan(2, 8, 20, tip_fillet=0.5)
    rack = RackGear(2, 8, 20, 8, root_fillet=0.5, tip_fillet=0.5)

    assert zero_fillet.area == pytest.approx(unfilleted.area)
    assert len(zero_fillet.edges()) == len(unfilleted.edges())
    assert filleted.area < unfilleted.area
    assert len(filleted.edges().filter_by(GeomType.CIRCLE)) == 2 * 8
    assert filleted.bounding_box().max.Y == pytest.approx(filleted.addendum)
    assert rack.is_valid
    assert rack.tip_fillet == pytest.approx(0.5)

    with pytest.raises(ValueError, match="Invalid tip fillet radius"):
        RackGearPlan(2, 8, 20, tip_fillet=1.3)


@pytest.mark.parametrize(
    "overrides",
    [
        {"module": 0},
        {"tooth_count": 0},
        {"tooth_count": 1.5},
        {"pressure_angle": 90},
        {"helix_angle": 90},
        {"module_system": "invalid"},
        {"root_fillet": -0.1},
        {"tip_fillet": -0.1},
        {"addendum": 0},
        {"dedendum": 0},
        {"base_height": 0},
    ],
)
def test_invalid_rack_gear_plan_parameters(overrides):
    parameters = {"module": 2, "tooth_count": 8, "pressure_angle": 20}
    parameters.update(overrides)
    with pytest.raises(ValueError):
        RackGearPlan(**parameters)


def test_invalid_rack_gear_thickness():
    with pytest.raises(ValueError, match="thickness must be greater than zero"):
        RackGear(2, 8, 20, 0)


def test_normal_module_helical_gear():
    """Match McMaster-Carr 3598N299 catalogue pitch and outside diameters."""
    gear = HelicalGear(
        module=1,
        tooth_count=30,
        pressure_angle=20,
        helix_angle=45,
        thickness=10,
        module_system="normal",
    )

    assert gear.base_radius < gear.root_radius
    assert 2 * gear.pitch_radius == pytest.approx(42.4264069)
    assert 2 * gear.addendum_radius == pytest.approx(44.4264069)
    assert gear.addendum_radius - gear.pitch_radius == pytest.approx(1)
    assert gear.normal_module == pytest.approx(1)
    assert gear.transverse_module == pytest.approx(2**0.5)


def test_transverse_module_helical_gear():
    gear = HelicalGear(
        module=1,
        tooth_count=20,
        pressure_angle=20,
        helix_angle=21.5,
        thickness=8,
        module_system="transverse",
    )

    assert 2 * gear.pitch_radius == pytest.approx(20)
    assert 2 * gear.addendum_radius == pytest.approx(22)
    assert gear.transverse_module == pytest.approx(1)


def test_helical_gear_tip_fillet():
    unfilleted = HelicalGear(1.5, 30, 20, 15, 8)
    filleted = HelicalGear(1.5, 30, 20, 15, 8, tip_fillet=0.2)

    assert filleted.is_valid
    assert filleted.volume < unfilleted.volume
    assert filleted.addendum_radius == pytest.approx(unfilleted.addendum_radius)
    with pytest.raises(ValueError, match="Invalid tip fillet radius"):
        HelicalGear(1.5, 30, 20, 15, 8, tip_fillet=1.5)


def test_zero_angle_helical_gear_matches_spur_gear():
    helical = HelicalGear(2, 12, 20, 0, 5)
    spur = SpurGear(2, 12, 20, 5)

    assert helical.twist_angle == pytest.approx(0)
    assert math.isinf(helical.lead)
    assert helical.volume == pytest.approx(spur.volume)
    assert helical.bounding_box().size == pytest.approx(spur.bounding_box().size)


# ---------------------------------------------------------------------------
# Worm gears
# ---------------------------------------------------------------------------


def _involute(angle: float) -> float:
    return math.tan(angle) - angle


def _circular_spread(angles: list[float]) -> float:
    """Spread of angles that are only meaningful modulo 2π."""
    reference = angles[0]
    deltas = [((a - reference + math.pi) % (2 * math.pi)) - math.pi for a in angles]
    return max(deltas) - min(deltas)


def _worm_section_area(worm: Worm) -> float:
    """Transverse section area from the closed-form angular tooth thickness."""
    z1, r1 = worm.starts, worm.pitch_radius
    advance = worm.lead / (2 * math.pi)
    if worm.flank_form == "ZA":
        alpha_x = math.radians(worm.axial_pressure_angle)

        def thickness_angle(r):
            return math.pi / z1 - 2 * (r - r1) * math.tan(alpha_x) / advance

    else:
        r_b = worm.base_radius
        inv_reference = _involute(math.acos(r_b / r1))

        def thickness_angle(r):
            return math.pi / z1 + 2 * (
                inv_reference - _involute(math.acos(r_b / max(r, r_b)))
            )

    # Simpson's rule on the smooth integrand ∫ψ(r)·r dr
    n, r_lo, r_hi = 400, worm.root_radius, worm.addendum_radius
    h = (r_hi - r_lo) / n
    total = sum(
        (1 if i in (0, n) else 4 if i % 2 else 2) * thickness_angle(r) * r
        for i, r in ((i, r_lo + i * h) for i in range(n + 1))
    )
    return math.pi * worm.root_radius**2 + z1 * total * h / 3


def _polar(point):
    return (
        math.hypot(point.X, point.Y),
        math.atan2(point.Y, point.X),
        point.Z,
    )


def test_worm_dimensions():
    worm = Worm(module=2, starts=2, diametral_quotient=10, length=30)

    assert worm.pitch_radius == pytest.approx(10)
    assert worm.addendum_radius == pytest.approx(12)
    assert worm.root_radius == pytest.approx(7.6)
    assert worm.lead == pytest.approx(4 * math.pi)
    assert worm.axial_pitch == pytest.approx(2 * math.pi)
    assert worm.lead_angle == pytest.approx(math.degrees(math.atan(0.2)))
    assert worm.normal_pressure_angle == 20
    assert worm.axial_pressure_angle == pytest.approx(
        math.degrees(math.atan(math.tan(math.radians(20)) / math.cos(math.atan(0.2))))
    )
    # involute helicoid: cos(γb) = cos(γ)·cos(αn) and rb·tan(γb) = lead / 2π
    gamma_b = math.acos(math.cos(math.atan(0.2)) * math.cos(math.radians(20)))
    assert worm.base_lead_angle == pytest.approx(math.degrees(gamma_b))
    assert worm.base_radius == pytest.approx(2 / math.tan(gamma_b))
    assert worm.transverse_pressure_angle == pytest.approx(
        math.degrees(math.acos(worm.base_radius / 10))
    )
    assert worm.length == 30
    assert worm.hand == "right"
    assert worm.flank_form == "ZI"


def test_archimedean_worm_has_no_base_cylinder():
    worm = Worm(2, 1, 10, 20, flank_form="ZA")

    assert worm.base_radius is None
    assert worm.base_lead_angle is None
    assert worm.transverse_pressure_angle is None


def test_zi_worm_flank_is_involute_helicoid():
    """Transverse sections are base-circle involutes and every surface normal is
    inclined at the base lead angle to the axis (the tangent developable of the
    base helix)."""
    flank = WormFlank(module=2, starts=2, diametral_quotient=10, length=30)
    advance = flank.lead / (2 * math.pi)
    gamma_b = math.radians(flank.base_lead_angle)

    origins = []
    for i in range(9):
        for j in range(9):
            point = flank.position_at(i / 8, j / 8)
            r, phi, z = _polar(point)
            assert flank.inner_radius - 1e-6 <= r <= flank.addendum_radius + 1e-6
            origins.append(
                phi - z / advance + _involute(math.acos(flank.base_radius / r))
            )
            normal = flank.normal_at(point)
            assert abs(normal.Z) == pytest.approx(math.cos(gamma_b), abs=1e-6)

    assert _circular_spread(origins) < 1e-6
    assert flank.bounding_box().min.Z == pytest.approx(-15)
    assert flank.bounding_box().max.Z == pytest.approx(15)


def test_za_worm_flank_is_archimedean_helicoid():
    """Every axial section of the flank is a straight line at the axial pressure
    angle: z − advance·θ − (r − r1)·tan(αx) is constant over the surface."""
    flank = WormFlank(2, 1, 10, 30, flank_form="ZA", side="upper")
    advance = flank.lead / (2 * math.pi)
    tan_alpha_x = math.tan(math.radians(flank.axial_pressure_angle))

    origins = []
    for i in range(9):
        for j in range(9):
            r, phi, z = _polar(flank.position_at(i / 8, j / 8))
            origins.append(phi - (z + (r - flank.pitch_radius) * tan_alpha_x) / advance)

    assert _circular_spread(origins) < 1e-6
    assert flank.inner_radius == pytest.approx(flank.root_radius)


def test_worm_flank_sides_are_mirror_images():
    lower = WormFlank(2, 2, 10, 30, side="lower")
    upper = WormFlank(2, 2, 10, 30, side="upper")

    assert lower.area == pytest.approx(upper.area)
    # on the reference cylinder the tooth centred on +X is π·module/2 thick, so
    # its flanks cross the X axis half that distance below and above z = 0
    half_thickness = math.pi * lower.module / 4
    below = Vertex(lower.pitch_radius, 0, -half_thickness)
    above = Vertex(lower.pitch_radius, 0, half_thickness)
    assert lower.distance_to(below) == pytest.approx(0, abs=1e-6)
    assert upper.distance_to(above) == pytest.approx(0, abs=1e-6)
    assert lower.distance_to(above) > 1
    assert upper.distance_to(below) > 1


@pytest.mark.parametrize(
    "flank_form, module, starts, diametral_quotient, length",
    [
        ("ZI", 2, 1, 10, 30),
        ("ZA", 2, 1, 10, 30),
        ("ZI", 2, 2, 10, 30),
        ("ZA", 2, 2, 10, 30),
        ("ZI", 2, 3, 10, 30),
        ("ZI", 1, 2, 12, 20),
        ("ZA", 4, 1, 9, 60),
        ("ZI", 2, 2, 10, 5),
    ],
)
def test_worm_section_matches_analytic_profile(
    flank_form, module, starts, diametral_quotient, length
):
    worm = Worm(module, starts, diametral_quotient, length, flank_form=flank_form)

    assert worm.is_valid
    assert len(worm.solids()) == 1
    end_caps = [f for f in worm.faces() if f.geom_type == GeomType.PLANE]
    assert len(end_caps) == 2
    area = _worm_section_area(worm)
    for cap in end_caps:
        assert cap.area == pytest.approx(area, rel=1e-6)
    # a helicoidal solid has volume = section area × length
    assert worm.volume == pytest.approx(area * length, rel=1e-6)
    bbox = worm.bounding_box()
    assert bbox.min.Z == pytest.approx(-length / 2)
    assert bbox.max.Z == pytest.approx(length / 2)
    assert bbox.max.X == pytest.approx(worm.addendum_radius)


def test_zi_worm_with_root_below_base_cylinder():
    """High-lead worms have their root inside the base cylinder; the involute
    flank is continued radially down to the root there."""
    worm = Worm(2, 4, 8, 30)

    assert worm.root_radius < worm.base_radius
    assert worm.is_valid
    assert worm.volume == pytest.approx(_worm_section_area(worm) * 30, rel=1e-6)
    assert WormFlank(2, 4, 8, 30).inner_radius == pytest.approx(worm.base_radius)


def test_worm_thread_phase_and_hand():
    worm = Worm(2, 2, 10, 30)
    r1, advance = worm.pitch_radius, worm.lead / (2 * math.pi)
    quarter_turn = advance * math.pi / 2

    # thread 0 is centred on +X at z = 0 and, being right handed, turns
    # counter-clockwise as z increases
    assert worm.is_inside((r1, 0, 0))
    assert not worm.is_inside((0, r1, 0))
    assert worm.is_inside((0, r1, quarter_turn))
    assert not worm.is_inside((r1, 0, quarter_turn))

    left = Worm(2, 2, 10, 30, hand="left")
    assert left.is_inside((r1, 0, 0))
    assert left.is_inside((0, -r1, quarter_turn))
    assert not left.is_inside((r1, 0, quarter_turn))
    assert left.volume == pytest.approx(worm.volume)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"module": 0}, "module"),
        ({"starts": 0}, "starts"),
        ({"starts": 1.5}, "starts"),
        ({"starts": True}, "starts"),
        ({"diametral_quotient": 0}, "diametral_quotient"),
        ({"length": 0}, "length"),
        ({"pressure_angle": 0}, "pressure_angle"),
        ({"pressure_angle": 90}, "pressure_angle"),
        ({"flank_form": "ZN"}, "flank_form"),
        ({"hand": "both"}, "hand"),
        ({"addendum": 0}, "addendum"),
        ({"dedendum": 0}, "dedendum"),
        ({"dedendum": 20}, "reference radius"),
        ({"pressure_angle": 45}, "tip width"),
        ({"dedendum": 4, "pressure_angle": 35}, "root space"),
    ],
)
def test_invalid_worm_parameters(kwargs, message):
    parameters = {
        "module": 2,
        "starts": 2,
        "diametral_quotient": 10,
        "length": 30,
        **kwargs,
    }
    with pytest.raises(ValueError, match=message):
        Worm(**parameters)


def test_invalid_worm_flank_side():
    with pytest.raises(ValueError, match="side"):
        WormFlank(2, 2, 10, 30, side="left")


def test_worm_wheel_matches_worm():
    worm = Worm(2, 2, 10, 30)
    wheel = WormWheel(
        module=2, tooth_count=30, thickness=12, starts=2, diametral_quotient=10
    )

    assert wheel.transverse_module == pytest.approx(worm.module)
    assert wheel.helix_angle == pytest.approx(worm.lead_angle)
    assert wheel.transverse_pressure_angle == pytest.approx(worm.axial_pressure_angle)
    assert wheel.normal_pressure_angle == pytest.approx(worm.normal_pressure_angle)
    assert wheel.pitch_radius == pytest.approx(30)
    assert wheel.addendum_radius - wheel.pitch_radius == pytest.approx(worm.addendum)
    assert wheel.pitch_radius - wheel.root_radius == pytest.approx(worm.dedendum)
    assert wheel.center_distance == pytest.approx(
        worm.pitch_radius + wheel.pitch_radius
    )
    assert wheel.is_valid

    left = WormWheel(2, 30, 12, starts=2, diametral_quotient=10, hand="left")
    assert left.helix_angle == pytest.approx(-worm.lead_angle)


def test_worm_gear_meshes_without_interference():
    gear = WormGear(
        module=2,
        starts=2,
        diametral_quotient=10,
        tooth_count=30,
        worm_length=30,
        wheel_thickness=12,
    )
    worm, wheel = gear.children

    assert [child.label for child in gear.children] == ["worm", "wheel"]
    assert set(gear.joints) == {"wheel", "worm"}
    assert gear.center_distance == pytest.approx(40)
    assert gear.ratio == 15
    # worm axis along Y through (center_distance, 0, 0)
    assert worm.bounding_box().center() == pytest.approx(Vector(40, 0, 0))
    assert worm.bounding_box().size.Y == pytest.approx(30)

    # the wheel tooth on +X sits in a thread space and the neighbouring worm
    # thread sits in a wheel tooth space
    assert not worm.is_inside((wheel.addendum_radius, 0, 0))
    half_axial_pitch = math.pi * 2 / 2
    thread_point = (gear.center_distance - 10, half_axial_pitch, 0)
    assert worm.is_inside(thread_point)
    assert not wheel.is_inside(thread_point)

    overlap = worm.intersect(wheel)
    overlap_volume = (
        0.0
        if overlap is None
        else sum(
            solid.volume
            for solid in Compound(
                list(overlap) if isinstance(overlap, list) else [overlap]
            ).solids()
        )
    )
    assert overlap_volume < 1e-9 * wheel.volume


if __name__ == "__main__":
    test_spur_gear_plan()
    test_invalid_spur_gear()
    test_spur_gear()
