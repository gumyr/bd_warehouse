from build123d import *
from pipe import *
from ocp_vscode import show, set_port, set_defaults

set_port(3939)
set_defaults(reset_camera=False, ortho=True)

with BuildPart() as pipe_logo:
    # P
    with BuildLine(Plane.XZ):
        l1 = Line((0, 0), (0, 6 * FT))
        l2 = Line(l1 @ 1 + (0, -3 * IN), l1 @ 1 + (1 * FT, -3 * IN))
        l3 = RadiusArc(l2 @ 1, l2 @ 1 + (0, -3 * FT), 1.5 * FT)
        l4 = Line(l3 @ 1, l3 @ 1 + (-1 * FT, 0))
    Pipe("6", "copper", "K")

    # i
    with BuildLine(Plane.XZ):
        l1 = Line((3 * FT, 0), (3 * FT, 3 * FT))
        l2 = Line((3 * FT, 3 * FT, -6 * IN), (3 * FT, 3 * FT, 6 * IN))
    pipe_i = Pipe("6", "copper", "K")
    with Locations(l1 @ 1):
        Cylinder(
            radius=pipe_i.id / 2,
            height=pipe_i.length,
            rotation=(90, 0, 0),
            mode=Mode.SUBTRACT,
        )

    # p
    with BuildLine(Plane.XZ):
        l1 = Line((4 * FT, -2.5 * FT), (4 * FT, 3 * FT))
        l2 = Line(l1 @ 1 + (0, -3 * IN), l1 @ 1 + (1 * FT, -3 * IN))
        l3 = RadiusArc(l2 @ 1, l2 @ 1 + (0, -30 * IN), 15 * IN)
        l4 = Line(l3 @ 1, l3 @ 1 + (-1 * FT, 0))
    Pipe("6", "copper", "K")

    # e
    with BuildLine(Plane.XZ) as e_path:
        l1 = Line((7 * FT, 19 * IN), (7 * FT + 30 * IN, 19 * IN))
        l2 = Spline(
            l1 @ 1 - (3 * IN, 0),
            (l1 @ 0 + l1 @ 1) / 2 + (0, 15 * IN),
            l1 @ 0,
            l1 @ 1 - (0, 15 * IN),
        )
    Pipe("6", "copper", "K")


show(pipe_logo)
