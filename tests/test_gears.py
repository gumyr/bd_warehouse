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
import sys
from pathlib import Path

import pytest
from bd_warehouse.gear import (
    BevelGear,
    HelicalGear,
    InvoluteToothProfile,
    MiterGear,
    RackGear,
    RackGearPlan,
    SphericalInvoluteToothProfile,
    SpurGear,
    SpurGearPlan,
    Worm,
    WormFlank,
    WormGear,
    WormWheel,
)
from build123d import (
    Axis,
    Compound,
    Edge,
    Face,
    GeomType,
    Location,
    Plane,
    Pos,
    Rot,
    Solid,
    Vector,
    Vertex,
    Wire,
)
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps


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


"""Tests for the isolated bevel/miter gear.

Profile tests check SphericalInvoluteToothProfile against the analytic spherical
involute. Gear tests build real BevelGear/MiterGear solids and check standard
bevel-gear formulas, B-rep validity and topology, measured geometry, an
independent Boolean volume cross-check, and meshing of placed pairs.
"""


M, ALPHA = 2.0, 20.0


# ====================================================================== helpers


def flank_spline(profile):
    """The +Y involute flank spline, oriented root -> tip."""
    edges = [
        e
        for e in profile.edges()
        if e.geom_type == GeomType.BSPLINE and (e @ 0.5).Y > 0
    ]
    assert len(edges) == 1
    edge = edges[0]
    return (
        (lambda t: edge @ t)
        if (edge @ 0).length < (edge @ 1).length
        else (lambda t: edge @ (1 - t))
    )


def point_at_radius(curve, radius):
    """Bisect a root -> tip curve for the point at ``radius`` from the origin."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if curve(mid).length < radius else (lo, mid)
    return curve((lo + hi) / 2)


def to_sphere(point, profile):
    """Wrap a developed back-cone point onto the back cone, then onto the unit sphere."""
    delta = math.radians(profile.pitch_cone_angle)
    radius, phi = math.hypot(point.X, point.Y), math.atan2(point.Y, point.X)
    eta = phi / math.cos(delta)
    rho = radius * math.cos(delta)
    z = profile.cone_distance / math.cos(delta) - radius * math.sin(delta)
    return Vector(rho * math.cos(eta), rho * math.sin(eta), z).normalized()


def planar_involute_half_angle(radius, tooth_count, pressure_angle):
    """Exact planar involute: half tooth-thickness angle at ``radius``."""
    inv = lambda a: math.tan(a) - a
    alpha = math.radians(pressure_angle)
    base_radius = M * tooth_count / 2 * math.cos(alpha)
    return (
        math.pi / (2 * tooth_count) + inv(alpha) - inv(math.acos(base_radius / radius))
    )


def solid_volume(shape):
    """Total solid volume of a Boolean result (Shape, ShapeList or None)."""
    if shape is None:
        return 0.0
    solids = (
        shape.solids()
        if hasattr(shape, "solids")
        else [s for item in shape for s in item.solids()]
    )
    return sum(s.volume for s in solids)


def interference(a, b):
    return solid_volume(a.intersect(b))


def precise_volume(shape):
    """Volume with adaptive integration.

    ``Shape.volume`` uses OCCT's default Gauss integration, which is only good to
    ~5e-5 relative on the B-spline flank faces; the adaptive form converges.
    """
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape.wrapped, props, 1e-7, True)
    return props.Mass()


def transformed(location, point):
    """Apply a Location to a point."""
    return (location * Location(point)).position


def face_width_for(z, mate_z=None, shaft=90, ratio=3.5, module=M):
    """A comfortable face width below the cone_distance / 3 limit."""
    mate_z = z if mate_z is None else mate_z
    s = math.radians(shaft)
    delta = math.atan2(math.sin(s), mate_z / z + math.cos(s))
    return module * z / (2 * math.sin(delta)) / ratio


def to_apex_frame(gear):
    """Apex at the origin, gear axis +Z, gear body at positive Z."""
    return Rot(180, 0, 0) * Pos(0, 0, -gear.mounting_distance) * gear


def polar_angle(point):
    return math.atan2(math.hypot(point.X, point.Y), point.Z)


def classify_face(face, gear):
    """Classify a face of a gear placed in the apex frame."""
    centre = face.center()
    radius, z = math.hypot(centre.X, centre.Y), centre.Z
    sigma = polar_angle(centre)
    if face.geom_type == GeomType.PLANE:
        return (
            "back"
            if z > gear.mounting_distance - gear.front_face_height / 2
            else "front"
        )
    if face.geom_type == GeomType.CYLINDER or (
        gear.bore_diameter and abs(radius - gear.bore_diameter / 2) < 1e-6
    ):
        return "bore"
    if (
        abs(math.degrees(sigma) - gear.face_cone_angle) < 1e-6
        and face.geom_type == GeomType.CONE
    ):
        return "tip"
    if (
        abs(math.degrees(sigma) - gear.root_cone_angle) < 1e-6
        and face.geom_type == GeomType.CONE
    ):
        return "root"
    if face.geom_type == GeomType.CONE:
        return (
            "back-cone"
            if centre.length > gear.inner_cone_distance * 1.05
            else "front-cone"
        )
    return "flank"


# ================================================================ profile tests


def test_profile_default_pressure_angle_is_20():
    assert SphericalInvoluteToothProfile(M, 16, 45).pressure_angle == 20


def test_profile_reference_radii_match_virtual_spur_gear():
    profile = SphericalInvoluteToothProfile(M, 16, 45, ALPHA)
    virtual = InvoluteToothProfile(M, profile.virtual_tooth_count, ALPHA)
    assert profile.cone_distance == pytest.approx(M * 16 / (2 * math.sin(math.pi / 4)))
    assert profile.virtual_tooth_count == pytest.approx(16 * math.sqrt(2))
    for name in ("pitch_radius", "addendum_radius", "root_radius"):
        assert getattr(profile, name) == pytest.approx(getattr(virtual, name))
    assert profile.base_cone_angle == pytest.approx(
        math.degrees(math.asin(math.sin(math.pi / 4) * math.cos(math.radians(ALPHA))))
    )


@pytest.mark.parametrize("z, delta", [(10, 45), (16, 45), (20, 26.565), (40, 63.435)])
def test_profile_pitch_thickness_and_pressure_angle(z, delta):
    """Heel pitch-line tooth thickness is pi*m/2; flank meets the pitch circle at alpha.

    The back cone is tangent to the reference sphere along the pitch circle and cone
    development is an isometry, so both properties hold exactly in the developed plane.
    """
    profile = SphericalInvoluteToothProfile(M, z, delta, ALPHA)
    curve = flank_spline(profile)
    p = point_at_radius(curve, profile.pitch_radius)
    half_thickness = profile.pitch_radius * math.atan2(p.Y, p.X)
    assert 2 * half_thickness == pytest.approx(math.pi * M / 2, abs=1e-6)

    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if curve(mid).length < profile.pitch_radius else (lo, mid)
    t = (lo + hi) / 2
    tangent = (curve(t + 1e-5) - curve(t - 1e-5)).normalized()
    angle = math.degrees(math.acos(abs(tangent.dot(p.normalized()))))
    assert angle == pytest.approx(ALPHA, abs=1e-3)


@pytest.mark.parametrize("z, delta", [(10, 45), (25, 45), (40, 63.435)])
def test_profile_is_an_exact_spherical_involute(z, delta):
    """Pointwise involute property checked on the wrapped 3D curve.

    On the sphere, the involute normal is the generating great circle tangent to the
    base cone, so at polar angle sigma the flank tangent makes the angle
    asin(sin(base) / sin(sigma)) with the azimuthal direction. Checked at spline
    parameters between the fitted samples.
    """
    profile = SphericalInvoluteToothProfile(M, z, delta, ALPHA)
    curve = flank_spline(profile)
    base = math.radians(profile.base_cone_angle)
    worst = 0.0
    for i in range(1, 60):
        t = (i + 0.37) / 61
        p = to_sphere(curve(t), profile)
        tangent = to_sphere(curve(t + 1e-6), profile) - to_sphere(
            curve(t - 1e-6), profile
        )
        sigma = math.acos(p.Z)
        if sigma <= base * 1.001:
            continue
        azimuthal = Vector(-p.Y, p.X, 0).normalized()
        measured = math.acos(min(1.0, abs(tangent.normalized().dot(azimuthal))))
        expected = math.asin(min(1.0, math.sin(base) / math.sin(sigma)))
        worst = max(worst, abs(measured - expected))
    assert worst < 1e-3  # radians; spline fit, not formula, limits this


def test_profile_converges_to_planar_involute_at_small_cone_angle():
    """At a tiny cone angle the spherical profile equals the exact planar involute of
    the virtual spur gear, and agrees with bd_warehouse to its own spline accuracy."""
    profile = SphericalInvoluteToothProfile(M, 16, 0.5, ALPHA)
    sph = flank_spline(profile)
    worst_exact = 0.0
    for i in range(41):
        radius = profile.base_radius + (
            profile.addendum_radius - profile.base_radius
        ) * (0.02 + 0.96 * i / 40)
        p = point_at_radius(sph, radius)
        exact = planar_involute_half_angle(radius, profile.virtual_tooth_count, ALPHA)
        worst_exact = max(worst_exact, abs(radius * (math.atan2(p.Y, p.X) - exact)))
    assert worst_exact < 1e-4  # mm

    planar = InvoluteToothProfile(M, profile.virtual_tooth_count, ALPHA)
    pla = flank_spline(planar)
    radius = profile.pitch_radius
    assert (point_at_radius(sph, radius) - point_at_radius(pla, radius)).length < 2.5e-3


@pytest.mark.parametrize("z, delta, radial", [(16, 45, True), (60, 45, False)])
def test_profile_root_flank_depends_on_base_cone(z, delta, radial):
    """Radial root line only when the root cone lies inside the base cone; otherwise
    the involute starts on the root (avoids the bd_warehouse root-flank defect)."""
    profile = SphericalInvoluteToothProfile(M, z, delta, ALPHA)
    assert (profile.root_radius < profile.base_radius) == radial
    side = [
        e for e in profile.edges() if (e @ 0.5).Y > 0 and e.geom_type != GeomType.CIRCLE
    ]
    assert {e.geom_type for e in side} == (
        {GeomType.LINE, GeomType.BSPLINE} if radial else {GeomType.BSPLINE}
    )
    lowest = min(min((e @ 0).length, (e @ 1).length) for e in side)
    assert lowest == pytest.approx(profile.root_radius, abs=1e-6)


def test_profile_closed_wire_and_root_fillet():
    profile = SphericalInvoluteToothProfile(M, 16, 45, ALPHA, closed=True)
    assert profile.is_closed
    filleted = SphericalInvoluteToothProfile(M, 16, 45, ALPHA, root_fillet=0.3)
    plain = SphericalInvoluteToothProfile(M, 16, 45, ALPHA)
    assert len(filleted.edges()) > len(plain.edges())


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"module": 0}, "module"),
        ({"tooth_count": 0}, "tooth_count"),
        ({"tooth_count": 12.5}, "tooth_count"),
        ({"pressure_angle": 0}, "pressure_angle"),
        ({"pitch_cone_angle": 90}, "pitch_cone_angle"),
        ({"addendum": 0}, "addendum"),
        ({"dedendum": -1}, "dedendum"),
        ({"addendum": 3 * M}, "pointed"),
        ({"root_fillet": 5.0}, "root radius"),
    ],
)
def test_profile_invalid_inputs(kwargs, message):
    inputs = dict(module=M, tooth_count=16, pitch_cone_angle=45, pressure_angle=ALPHA)
    inputs.update(kwargs)
    with pytest.raises(ValueError, match=message):
        SphericalInvoluteToothProfile(**inputs)


# =================================================================== gear tests


@pytest.fixture(scope="module")
def miter16():
    return MiterGear(M, 16, face_width_for(16))


@pytest.fixture(scope="module")
def pinion_gear_1_2():
    fw = face_width_for(20, 40)
    return BevelGear(M, 20, 40, fw), BevelGear(M, 40, 20, fw)


def test_default_pressure_angle_is_20(miter16):
    assert miter16.pressure_angle == 20
    assert BevelGear(M, 16, 16, face_width_for(16)).pressure_angle == 20


def test_miter_gear_matches_equal_bevel_gear(miter16):
    bevel = BevelGear(M, 16, 16, miter16.face_width)
    assert miter16.pitch_cone_angle == pytest.approx(45)
    assert miter16.mate_tooth_count == 16
    assert miter16.volume == pytest.approx(bevel.volume, rel=1e-9)
    assert len(miter16.faces()) == len(bevel.faces())


def test_miter_gear_reference_dimensions(miter16):
    """Standard straight-bevel formulas (ISO 23509 / KHK) for a 16T m2 miter gear."""
    g = miter16
    delta = math.radians(45)
    assert g.pitch_diameter == pytest.approx(32)
    assert g.cone_distance == pytest.approx(32 / (2 * math.sin(delta)))
    assert g.virtual_tooth_count == pytest.approx(16 * math.sqrt(2))
    assert g.addendum_angle == pytest.approx(
        math.degrees(math.atan(M / g.cone_distance))
    )
    assert g.dedendum_angle == pytest.approx(
        math.degrees(math.atan(1.25 * M / g.cone_distance))
    )
    assert g.face_cone_angle == pytest.approx(45 + g.addendum_angle)
    assert g.root_cone_angle == pytest.approx(45 - g.dedendum_angle)
    # Outside (tip) diameter: d + 2 * h_a * cos(delta) for an apex-tapered tooth.
    tip_slant = g.cone_distance / math.cos(math.radians(g.addendum_angle))
    assert g.outside_diameter == pytest.approx(
        2 * tip_slant * math.sin(math.radians(g.face_cone_angle))
    )
    assert g.outside_diameter == pytest.approx(32 + 2 * M * math.cos(delta), rel=1e-12)
    assert g.base_cone_angle == pytest.approx(
        math.degrees(math.asin(math.sin(delta) * math.cos(math.radians(ALPHA))))
    )


@pytest.mark.parametrize(
    "z, z_mate, shaft",
    # (15, 30, 120) would make the 30T member a crown gear (delta = 90) - see the
    # "crown" invalid-input case below.
    [
        (16, 16, 90),
        (20, 40, 90),
        (40, 20, 90),
        (18, 27, 60),
        (20, 30, 110),
        (12, 12, 75),
    ],
)
def test_pair_cone_angles_and_cone_distance(z, z_mate, shaft):
    fw = min(face_width_for(z, z_mate, shaft), face_width_for(z_mate, z, shaft))
    a, b = BevelGear(M, z, z_mate, fw, shaft_angle=shaft), BevelGear(
        M, z_mate, z, fw, shaft_angle=shaft
    )
    assert a.pitch_cone_angle + b.pitch_cone_angle == pytest.approx(shaft)
    assert a.mate_pitch_cone_angle == pytest.approx(b.pitch_cone_angle)
    assert a.cone_distance == pytest.approx(b.cone_distance)
    # Pitch circle radii satisfy r = R sin(delta) for both members.
    for g in (a, b):
        assert g.pitch_radius == pytest.approx(
            g.cone_distance * math.sin(math.radians(g.pitch_cone_angle))
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(tooth_count=10),
        dict(tooth_count=16),
        dict(tooth_count=15, bore_diameter=6),
        dict(tooth_count=30),
        dict(tooth_count=50),
        dict(tooth_count=16, pressure_angle=14.5),
        dict(tooth_count=16, pressure_angle=25),
        dict(tooth_count=16, root_fillet=0.4),
        dict(tooth_count=16, shaft_angle=60),
    ],
)
def test_miter_gear_is_a_valid_single_solid(kwargs):
    z = kwargs["tooth_count"]
    gear = MiterGear(
        M, face_width=face_width_for(z, z, kwargs.get("shaft_angle", 90)), **kwargs
    )
    assert gear.is_valid
    assert len(gear.solids()) == 1
    assert gear.is_manifold
    assert gear.volume > 0
    assert gear.face_count == len(gear.faces())


def test_bevel_gear_with_many_teeth_is_valid():
    """Virtual tooth count ~190: far beyond the bd_warehouse planar-involute limit."""
    gear = BevelGear(M, 60, 20, face_width_for(60, 20))
    assert gear.virtual_tooth_count > 150
    assert gear.is_valid and len(gear.solids()) == 1


@pytest.mark.parametrize(
    "z, kwargs, faces_per_tooth",
    [
        (16, {}, 6),  # root inside base cone: 2 radial lines + 2 involutes + tip + root
        (60, {}, 4),  # root outside base cone: 2 involutes + tip + root
        (16, {"root_fillet": 0.4}, 8),  # + 2 fillet faces
    ],
)
def test_face_count_is_predictable(z, kwargs, faces_per_tooth):
    """Topology is deterministic: tooth faces x z + back cone, front cone, back face,
    front face (+ bore)."""
    gear = MiterGear(M, z, face_width_for(z), **kwargs)
    assert len(gear.faces()) == faces_per_tooth * z + 4
    bored = MiterGear(M, z, face_width_for(z), bore_diameter=8, **kwargs)
    assert len(bored.faces()) == faces_per_tooth * z + 5


def test_face_surface_types(miter16):
    """Tip and root lands, back and front cones are exact cones; back and front
    faces are planes; flanks are ruled B-spline surfaces through the apex."""
    gear = to_apex_frame(miter16)
    kinds = {}
    for face in gear.faces():
        kinds.setdefault(classify_face(face, miter16), []).append(face.geom_type)
    assert len(kinds["tip"]) == 16 and len(kinds["root"]) == 16
    assert set(kinds["back"]) == {GeomType.PLANE} and len(kinds["back"]) == 1
    assert set(kinds["front"]) == {GeomType.PLANE} and len(kinds["front"]) == 1
    assert len(kinds["back-cone"]) == 1 and len(kinds["front-cone"]) == 1
    assert len(kinds["flank"]) == 16 * 4


def test_flank_rulings_pass_through_apex(miter16):
    """Every flank face is generated by straight lines through the cone apex: points
    on the heel and toe boundaries are related by scaling about the apex."""
    gear = to_apex_frame(miter16)
    k = miter16.inner_cone_distance / miter16.cone_distance
    flanks = [f for f in gear.faces() if classify_face(f, miter16) == "flank"]
    worst = 0.0
    for face in flanks[:8]:
        for u in (0.1, 0.5, 0.9):
            heel = (
                face.position_at(u, 0)
                if face.position_at(u, 0).length > face.position_at(u, 1).length
                else face.position_at(u, 1)
            )
            toe_expected = heel * k
            worst = max(worst, face.distance_to(toe_expected))
            mid = heel * ((1 + k) / 2)
            worst = max(worst, face.distance_to(mid))
    assert worst < 1e-6


def test_placement_and_bounding_box(miter16):
    g = miter16
    bbox = g.bounding_box()
    assert bbox.min.Z == pytest.approx(0, abs=1e-6)  # back face on z = 0
    assert bbox.max.Z == pytest.approx(g.total_height, abs=1e-6)
    assert bbox.size.X == pytest.approx(g.outside_diameter, abs=1e-3)
    assert bbox.size.Y == pytest.approx(g.outside_diameter, abs=1e-3)
    assert g.apex == Vector(0, 0, g.mounting_distance)
    assert g.apex.Z > g.total_height  # apex beyond the toe
    # a tooth is centred on +X at the heel: the heel tip point lies in the XZ plane
    heel_tip = Vector(
        g.outside_diameter / 2,
        0,
        g.mounting_distance - g.pitch_apex_to_crown,
    )
    assert g.distance_to(heel_tip) < 1e-6


def test_measured_tooth_thickness_at_heel_pitch_circle(miter16):
    """The heel pitch-circle arc crosses the solid in 16 teeth whose chordal
    thickness on the back cone equals pi * m / 2 (zero backlash)."""
    g = to_apex_frame(miter16)
    delta = math.radians(45)
    radius = miter16.cone_distance * math.sin(delta)
    z = miter16.cone_distance * math.cos(delta)
    probe = Edge.make_circle(radius, Plane(origin=(0, 0, z)))
    inside = probe.intersect(g)
    segments = inside.edges() if inside is not None else []
    assert len(segments) == 16
    for seg in segments:
        # arc length on the pitch circle; back-cone thickness differs only by the
        # isometric development which preserves arc length along the pitch circle
        assert seg.length == pytest.approx(math.pi * M / 2, abs=2e-4)


def test_bore_is_through_and_concentric():
    gear = MiterGear(M, 20, face_width_for(20), bore_diameter=10)
    assert gear.is_valid
    bore_faces = [f for f in gear.faces() if f.geom_type == GeomType.CYLINDER]
    assert len(bore_faces) == 1
    assert bore_faces[0].radius == pytest.approx(5)
    assert gear.is_inside((0, 0, gear.total_height / 2)) is False
    solid = MiterGear(M, 20, face_width_for(20))
    expected = math.pi * 5**2 * solid.front_face_height
    assert solid.volume - gear.volume == pytest.approx(expected, rel=1e-6)


@pytest.mark.parametrize("z", [10, 16, 25])
def test_volume_matches_independent_boolean_construction(z):
    """Cross-check the sewn B-rep against a Boolean model built from the same
    pitch geometry.

    The blank (face cone) and root body (root cone) are revolved independently from
    the published cone angles. The sewn gear must contain the whole root body and
    lie inside the blank, so volume(gear) == volume(root) + volume(gear & ring).
    Missing root material, overshooting teeth or leaky sewing break the identity.
    """
    gear = MiterGear(M, z, face_width_for(z))
    apex = to_apex_frame(gear)
    delta = math.radians(gear.pitch_cone_angle)
    R, Ri = gear.cone_distance, gear.inner_cone_distance
    ta, tf = math.radians(gear.addendum_angle), math.radians(gear.dedendum_angle)

    def meridian(rho, sigma):
        return (rho * math.sin(sigma), rho * math.cos(sigma))

    def revolve(points):
        wire = Wire.make_polygon([Vector(r, 0, zz) for r, zz in points], close=True)
        return Solid.revolve(Face(wire), 360, Axis.Z)

    z_back = gear.mounting_distance
    z_front = z_back - gear.front_face_height
    r_back, r_front = gear.back_face_diameter / 2, gear.front_face_diameter / 2
    blank = revolve(
        [
            (0, z_front),
            (r_front, z_front),
            meridian(Ri / math.cos(ta), delta + ta),
            meridian(R / math.cos(ta), delta + ta),
            (r_back, z_back),
            (0, z_back),
        ]
    )
    root = revolve(
        [
            (0, z_front),
            (r_front, z_front),
            meridian(Ri / math.cos(tf), delta - tf),
            meridian(R / math.cos(tf), delta - tf),
            (r_back, z_back),
            (0, z_back),
        ]
    )
    # independent tooth volume: the root-to-tip ring minus the measured tooth spaces
    ring = blank.cut(root)
    teeth = sum(precise_volume(s) for s in apex.intersect(ring).solids())
    assert precise_volume(apex) == pytest.approx(precise_volume(root) + teeth, rel=1e-5)
    assert solid_volume(apex.cut(blank)) == pytest.approx(0, abs=1e-6)
    # teeth occupy just under half the ring (tooth thinner than space above pitch)
    assert 0.3 < teeth / precise_volume(ring) < 0.6


@pytest.mark.parametrize(
    "first, second, label",
    [
        ((M, 16, 16), (M, 16, 16), "miter 16"),
        ((M, 15, 15), (M, 15, 15), "miter 15 (odd)"),
        ((M, 20, 40), (M, 40, 20), "1:2"),
    ],
)
def test_pairs_mesh_without_interference(first, second, label):
    fw = min(face_width_for(first[1], first[2]), face_width_for(second[1], second[2]))
    g1, g2 = BevelGear(*first, fw), BevelGear(*second, fw)
    for t in (0.0, 0.25, 0.5, 0.75):
        angle = t * 360 / g1.tooth_count
        p1 = Rot(0, 0, angle) * g1
        p2 = g1.mate_location(g2, angle) * g2
        assert interference(p1, p2) < 1e-4, f"{label} interferes at phase {t}"
        assert (
            p1.distance_to(p2) < 1e-4
        ), f"{label} teeth are not in contact at phase {t}"
    # positive control: half a pitch out of phase the teeth must collide
    wrong = g1.mate_location(g2, 0) * Rot(0, 0, 180 / g2.tooth_count) * g2
    assert interference(g1, wrong) > 1.0


def test_pair_at_non_right_shaft_angle_meshes():
    fw = min(
        face_width_for(18, 27, 60, module=1.5), face_width_for(27, 18, 60, module=1.5)
    )
    g1 = BevelGear(1.5, 18, 27, fw, shaft_angle=60)
    g2 = BevelGear(1.5, 27, 18, fw, shaft_angle=60)
    location = g1.mate_location(g2)
    p2 = location * g2
    # the mate's axis is at the shaft angle to this gear's axis
    mate_axis = transformed(location, (0, 0, 1)) - transformed(location, (0, 0, 0))
    assert Vector(0, 0, 1).get_angle(mate_axis) == pytest.approx(60)  # degrees
    assert interference(g1, p2) < 1e-4
    assert g1.distance_to(p2) < 1e-4
    wrong = location * Rot(0, 0, 180 / 27) * g2
    assert interference(g1, wrong) > 1.0


def test_pitch_apexes_coincide_in_mate_location(pinion_gear_1_2):
    g1, g2 = pinion_gear_1_2
    assert (transformed(g1.mate_location(g2), g2.apex) - g1.apex).length < 1e-9


def test_mate_location_rejects_non_pairs(miter16, pinion_gear_1_2):
    g1, g2 = pinion_gear_1_2
    with pytest.raises(ValueError, match="tooth counts"):
        miter16.mate_location(g1)
    with pytest.raises(ValueError, match="pressure_angle"):
        miter16.mate_location(MiterGear(M, 16, miter16.face_width, pressure_angle=25))
    with pytest.raises(ValueError, match="BevelGear"):
        miter16.mate_location("not a gear")


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"module": 0}, "module"),
        ({"tooth_count": 0}, "tooth_count"),
        ({"mate_tooth_count": 2.5}, "mate_tooth_count"),
        ({"pressure_angle": 90}, "pressure_angle"),
        ({"shaft_angle": 180}, "shaft_angle"),
        ({"face_width": 0}, "face_width"),
        ({"face_width": 100}, "face_width"),
        ({"bore_diameter": -1}, "bore_diameter"),
        ({"bore_diameter": 30}, "bore_diameter"),
        ({"back_cone_width": 0}, "back_cone_width"),
        ({"root_fillet": -1}, "root_fillet"),
        ({"mate_tooth_count": 8, "shaft_angle": 150}, "crown"),
    ],
)
def test_bevel_gear_invalid_inputs(kwargs, message):
    inputs = dict(module=M, tooth_count=16, mate_tooth_count=16, face_width=5)
    inputs.update(kwargs)
    with pytest.raises(ValueError, match=message):
        BevelGear(**inputs)


# if __name__ == "__main__":
#     test_spur_gear_plan()
#     test_invalid_spur_gear()
#     test_spur_gear()
