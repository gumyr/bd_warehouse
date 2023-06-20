import timeit
from build123d import *
from bd_warehouse.thread import IsoThread
from ocp_vscode import show, show_object, set_port, set_defaults

set_port(3939)
set_defaults(reset_camera=True, ortho=True)

starttime = timeit.default_timer()

with BuildPart() as iso_internal:
    iso_internal_thread = IsoThread(
        major_diameter=6 * MM,
        pitch=1 * MM,
        length=4.35 * MM,
        external=False,
        end_finishes=("square", "chamfer"),
        hand="left",
    )
    with BuildSketch():
        RegularPolygon(iso_internal_thread.major_diameter * 0.75, 6)
        Circle(iso_internal_thread.major_diameter / 2 - 0.1, mode=Mode.SUBTRACT)
    extrude(amount=iso_internal_thread.length)

elapsed_time = timeit.default_timer() - starttime
print(f"IsoThread internal elapsed time: {elapsed_time:.3f}s")
print(f"{iso_internal.part.is_valid()=}")

# show(iso_internal_thread, iso_internal)
show(iso_internal)
