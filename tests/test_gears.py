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
)
from build123d import Edge, GeomType, Vector


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


if __name__ == "__main__":
    test_spur_gear_plan()
    test_invalid_spur_gear()
    test_spur_gear()
