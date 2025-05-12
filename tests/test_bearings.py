"""

Bearing Tests

name: test_bearings.py
by:   Gumyr
date: May 12, 2025

desc: Basic pytests for the bearing classes.

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

import random
import re

import pytest
from bd_warehouse.bearing import (
    Bearing,
    PressFitHole,
    SingleRowDeepGrooveBallBearing,
    SingleRowTaperedRollerBearing,
)
from build123d import Axis, Box, BuildPart, Locations


@pytest.mark.parametrize(
    "bearing_class, bearing_type, bearing_size",
    [
        (bearing_class, bearing_type, bearing_size)
        for bearing_class in Bearing.__subclasses__()
        for bearing_type in bearing_class.types()
        for bearing_size in bearing_class.sizes(bearing_type)
    ],
)
def test_bearings(bearing_class: Bearing, bearing_type: str, bearing_size: str):
    bearing: Bearing = bearing_class(
        size=bearing_size,
        bearing_type=bearing_type,
    )

    # Check that bearing properties are created
    assert bearing.roller_diameter > 0
    assert bearing.bore_diameter > 0
    assert len(bearing.clearance_hole_diameters) > 0
    assert len(bearing.info) > 2
    assert bearing.length_offset() is not None

    # Check that the bearing is the correct size
    bbox_size = bearing.bounding_box().size
    _, diameter, thickness = re.match(
        r"M(\d+)-([\d\.]+)-([\d\.]+)", bearing_size
    ).groups()
    assert bbox_size.X == pytest.approx(float(diameter), abs=1e-2)
    # The cage may extend past the bottom of the outer race
    if bearing_class != SingleRowTaperedRollerBearing:
        assert bbox_size.Z == pytest.approx(float(thickness), abs=1e-2)

    # Check that holes can be created
    with BuildPart() as hole_tests:
        Box(100, 100, 50)
        top = hole_tests.faces().sort_by(Axis.Z)[-1]
        with Locations(top):
            PressFitHole(bearing, fit=random.choice(["Close", "Normal", "Loose"]))
    assert hole_tests.part.volume < 100 * 100 * 50


if __name__ == "__main__":
    test_bearings(SingleRowDeepGrooveBallBearing, "SKT", "M8-22-7")
    test_bearings(SingleRowTaperedRollerBearing, "SKT", "M15-42-14.25")
