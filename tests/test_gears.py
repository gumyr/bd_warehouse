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
from bd_warehouse.gear import HelicalGear, SpurGear, SpurGearPlan
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


def test_invalid_spur_gear():
    # Too large root fillet
    with pytest.raises(Exception):
        spur_gear_plan = SpurGearPlan(
            module=1,
            tooth_count=100,
            pressure_angle=14.5,
            root_fillet=0.5,
        )
    # Too many teeth for pressure angle
    with pytest.raises(Exception):
        spur_gear_plan = SpurGearPlan(
            module=1,
            tooth_count=100,
            pressure_angle=14.5,
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


def test_normal_module_helical_gear():
    gear = HelicalGear(
        module=1,
        tooth_count=13,
        pressure_angle=20,
        helix_angle=45,
        thickness=10,
        module_system="normal",
    )

    assert 2 * gear.pitch_radius == pytest.approx(18.3847763)
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
