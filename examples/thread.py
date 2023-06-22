import timeit
from build123d import *
from bd_warehouse.thread import (
    AcmeThread,
    IsoThread,
    MetricTrapezoidalThread,
    PlasticBottleThread,
)
from ocp_vscode import show, show_object, set_port, set_defaults

set_port(3939)
set_defaults(reset_camera=True, ortho=True)

starttime = timeit.default_timer()

with BuildPart() as iso_internal_nut:
    iso_internal = IsoThread(
        major_diameter=6 * MM,
        pitch=1 * MM,
        length=4.35 * MM,
        external=False,
        end_finishes=("chamfer", "chamfer"),
        hand="left",
    )
    with BuildSketch():
        RegularPolygon(iso_internal.major_diameter * 0.75, 6)
        Circle(iso_internal.major_diameter / 2 - 0.1, mode=Mode.SUBTRACT)
    extrude(amount=iso_internal.length)

elapsed_time = timeit.default_timer() - starttime
print(f"IsoThread internal elapsed time: {elapsed_time:.3f}s")
print(f"{iso_internal_nut.part.is_valid()=}")

with BuildPart() as iso_external_screw:
    iso_external = IsoThread(
        major_diameter=6 * MM,
        pitch=1 * MM,
        length=8 * MM,
        external=True,
        end_finishes=("square", "chamfer"),
        hand="right",
        align=None,
    )
    Cylinder(
        iso_external.major_diameter / 2,
        8 * MM,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )

elapsed_time = timeit.default_timer() - starttime
print(f"IsoThread external elapsed time: {elapsed_time:.3f}s")
print(f"{iso_external_screw.part.is_valid()=}")

with BuildPart() as acme_screw:
    acme = AcmeThread(size="1/4", length=1 * IN)
    Cylinder(
        acme.root_radius, acme.length, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )

elapsed_time = timeit.default_timer() - starttime
print(f"Acme external elapsed time: {elapsed_time:.3f}s")
print(f"{acme_screw.part.is_valid()=}")


with BuildPart() as metric_screw:
    metric = MetricTrapezoidalThread(size="8x1.5", length=20 * MM)
    Cylinder(
        metric.root_radius, metric.length, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )

elapsed_time = timeit.default_timer() - starttime
print(f"Metric external elapsed time: {elapsed_time:.3f}s")
print(f"{metric_screw.part.is_valid()=}")

end_finishes = [["raw", "fade"], ["square", "chamfer"]]
with BuildPart() as end_examples:
    locs = GridLocations(5 * MM, 5 * MM, 2, 1).locations
    for i, loc in enumerate(locs):
        with Locations(loc):
            iso_end = IsoThread(
                major_diameter=3 * MM,
                pitch=1 * MM,
                length=4 * MM,
                end_finishes=("square", end_finishes[i // 2][i % 2]),
            )
            Cylinder(
                iso_end.min_radius,
                iso_end.length,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )

elapsed_time = timeit.default_timer() - starttime
print(f"End finishes external elapsed time: {elapsed_time:.3f}s")
print(f"{end_examples.part.is_valid()=}")

plastic_external = PlasticBottleThread("M40SP444", external=True)
plastic_internal = PlasticBottleThread("M38SP444", external=False)

elapsed_time = timeit.default_timer() - starttime
print(f"Plastic elapsed time: {elapsed_time:.3f}s")
print(f"{plastic_external.is_valid()=}")
print(f"{plastic_internal.is_valid()=}")

show(
    iso_internal_nut.part.locate(Location((-20, -20))),
    iso_external_screw.part.locate(Location((-20, 20))),
    acme_screw.part.locate(Location((10, -20))),
    metric_screw.part.locate(Location((10, 20))),
    end_examples,
    plastic_internal.locate(Location((40, -20))),
    plastic_external.locate(Location((40, 20))),
)
