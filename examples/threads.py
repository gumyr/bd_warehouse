"""

Parametric Threads Examples

name: threads.py
by:   Gumyr
date: June 30th 2023

desc: A collection of different thread types.

license:

    Copyright 2023 Gumyr

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

import timeit

from bd_warehouse.thread import (
    AcmeThread,
    IsoThread,
    MetricTrapezoidalThread,
    PlasticBottleThread,
    Thread,
)
from build123d import *
from ocp_vscode import show

# Raw Thread internal
starttime = timeit.default_timer()
internal = Thread(
    apex_radius=5,
    apex_width=0.1,
    root_radius=6,
    root_width=0.8,
    pitch=1,
    length=12.001,
    apex_offset=0.2,
    end_finishes=["raw", "square"],
)
elapsed_time = timeit.default_timer() - starttime
print(f"Internal Thread time: {elapsed_time:.3f}s")

# Raw Thread external
starttime = timeit.default_timer()
external = Thread(
    apex_radius=6,
    apex_width=0.1,
    root_radius=5,
    root_width=0.8,
    pitch=1,
    length=8.0,
    apex_offset=0.2,
    end_finishes=["fade", "chamfer"],
)
elapsed_time = timeit.default_timer() - starttime
print(f"External Thread time: {elapsed_time:.3f}s")

# IsoThread internal in the form of a nut
starttime = timeit.default_timer()
iso_internal = IsoThread(
    major_diameter=6 * MM,
    pitch=1 * MM,
    length=8 * MM,
    external=False,
    end_finishes=("chamfer", "fade"),
    hand="right",
)
with BuildPart() as iso_internal_nut:
    with BuildSketch():
        RegularPolygon(iso_internal.major_diameter * 0.75, 6)
        Circle(iso_internal.major_diameter / 2, mode=Mode.SUBTRACT)
    extrude(amount=iso_internal.length)

nut = iso_internal.fuse(iso_internal_nut.part)
elapsed_time = timeit.default_timer() - starttime
print(f"Nut elapsed time: {elapsed_time:.3f}s")
print(f"{nut.is_valid()=}")

# IsoThread external in the form of a screw
starttime = timeit.default_timer()
iso_external = IsoThread(
    major_diameter=6 * MM,
    pitch=1 * MM,
    length=4.5 * MM,
    external=True,
    end_finishes=("square", "square"),
    hand="right",
)
external_core = Cylinder(
    iso_external.root_radius,
    iso_external.length,
    align=(Align.CENTER, Align.CENTER, Align.MIN),
)
iso_external_screw = iso_external.fuse(external_core)
elapsed_time = timeit.default_timer() - starttime
print(f"Iso External Screw elapsed time: {elapsed_time:.3f}s")

# Acme Screw
starttime = timeit.default_timer()
acme = AcmeThread(size="1/4", length=1 * IN)

acme_screw = acme + Cylinder(
    acme.root_radius, acme.length, align=(Align.CENTER, Align.CENTER, Align.MIN)
)
elapsed_time = timeit.default_timer() - starttime
print(f"Acme external elapsed time: {elapsed_time:.3f}s")
print(f"{acme_screw.is_valid()=}")

# Metric Trapezoidal Thread
starttime = timeit.default_timer()
metric = MetricTrapezoidalThread(size="8x1.5", length=20 * MM)
metric_screw = metric + Cylinder(
    metric.root_radius, metric.length, align=(Align.CENTER, Align.CENTER, Align.MIN)
)

elapsed_time = timeit.default_timer() - starttime
print(f"Metric external elapsed time: {elapsed_time:.3f}s")
print(f"{metric_screw.is_valid()=}")

# Plastic Thread
starttime = timeit.default_timer()
plastic_external = PlasticBottleThread("M40SP444", external=True)
plastic_internal = PlasticBottleThread("M38SP444", external=False)

elapsed_time = timeit.default_timer() - starttime
print(f"Plastic elapsed time: {elapsed_time:.3f}s")
print(f"{plastic_external.is_valid()=}")
print(f"{plastic_internal.is_valid()=}")
print(f"Plastic external & internal elapsed time: {elapsed_time:.3f}s")


show(
    internal.locate(Location((-10, -10, 0))),
    external.locate(Location((10, -10, 0))),
    nut.locate(Location((-10, 10, 0))),
    iso_external_screw.locate(Location((10, 10, 0))),
    acme_screw.locate(Location((20, 0, 0))),
    metric_screw.locate(Location((-20, 0, 0))),
    plastic_internal.locate(Location((0, -40))),
    plastic_external.locate(Location((0, 40))),
    timeit=False,
)
