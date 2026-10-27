"""

Rod End Examples

Run this with the OCP CAD Viewer running in VS Code:

    python examples/rod_ends.py

Five things are shown side by side:

1. the DIN 648 series K size range in both variants - tapped, 5 mm to 35 mm
   bore, and threaded stem, 5 mm to 30 mm,
2. one of each cut on its bore axis, so the bronze socket and the hardened
   ball inside the housing are visible, along with what the two variants do
   differently past the head: a tapped hole with a drilled point, or a solid
   stem with a lead-in chamfer,
3. a link assembled from two tapped rod ends and a threaded rod, put together
   with the joints rather than by positioning the parts by hand,
4. a threaded stem rod end screwed into a tapped one.

"""

from build123d import *
from ocp_vscode import Camera, set_defaults, show

from bd_warehouse.rod_end import FemaleThreadRodEnd, MaleThreadRodEnd, RodEnd

set_defaults(reset_camera=Camera.CENTER)


def section(rod_end: RodEnd, plane: Plane = Plane.XZ) -> Compound:
    """Cut a rod end in half, keeping the three parts labelled and materialled

    Splitting the compound itself would flatten it, so each part is cut on its
    own and the compound is rebuilt around the halves.
    """
    halves = []
    for part in rod_end.children:
        half = split(part, bisect_by=plane, keep=Keep.BOTTOM, mode=Mode.PRIVATE)
        half.label = part.label
        half.material = part.material
        halves.append(half)
    return Compound(children=halves, label=f"{rod_end.label}-section")


def threaded_link(size: str, length: float) -> Compound:
    """Two tapped rod ends on a threaded rod, assembled through their joints

    ``length`` is the rod itself. Neither the rod's thread nor the rod ends'
    is modelled, so the rod is drawn at the diameter of the tapped hole it
    screws into and the two simplified representations sit inside each other
    without overlapping.
    """
    ends = [FemaleThreadRodEnd(size), FemaleThreadRodEnd(size)]
    engagement = ends[0].thread_depth

    rod = Cylinder(ends[0].thread_minor_diameter / 2, length)
    rod.label = "ThreadedRod"

    # One joint near each end of the rod, both facing outwards along it, so
    # connecting them drives the two rod ends apart. Insetting them by the
    # thread depth screws the rod that far into each tapped hole.
    for name, direction in (("a", -1), ("b", 1)):
        station = direction * (length / 2 - engagement)
        facing_out = Rot(Y=180) if direction < 0 else Rot()
        RigidJoint(name, rod, Pos(Z=station) * facing_out)

    for name, rod_end in zip(("a", "b"), ends):
        rod.joints[name].connect_to(rod_end.joints["thread"])

    return Compound(children=[rod] + ends, label=f"link-{size}")


def screwed_pair(size: str) -> Compound:
    """A threaded stem rod end screwed into a tapped one of the same bore

    Both variants of a bore take the same pin but not the same thread, so this
    only goes together where the two agree - which they do on all but the
    20 mm bore, tapped M20 and stemmed M20x1.5.

    The stem is drawn at its nominal diameter and the tapped hole at its basic
    minor diameter, so the two simplified representations overlap where they
    engage. That is the usual consequence of not modelling thread form, and it
    is buried inside the joint.
    """
    tapped, stem = FemaleThreadRodEnd(size), MaleThreadRodEnd(size)
    if stem.thread_size != tapped.thread_size:
        raise ValueError(
            f"{size}: a {stem.thread_size} stem does not fit a "
            f"{tapped.thread_size} tapped hole"
        )
    engagement = min(tapped.thread_depth, stem.thread_length)

    # A joint at the far end of the engagement, facing back out of the hole,
    # so connecting the stem's own end joint to it screws the stem that far in.
    RigidJoint(
        "tapped_hole",
        tapped,
        Pos(Z=-tapped.center_to_end + engagement) * Rot(Y=180),
    )
    tapped.joints["tapped_hole"].connect_to(stem.joints["thread"])

    return Compound(children=[tapped, stem], label=f"pair-{size}")


def size_range(rod_end_class: type, label: str) -> Compound:
    """Every catalogued size of one variant, laid out in a row"""
    rod_ends = [rod_end_class(size) for size in rod_end_class.sizes("DIN648K")]
    return Compound(children=list(pack(rod_ends, padding=6, align_z=True)), label=label)


groups = [
    size_range(FemaleThreadRodEnd, "tapped"),
    size_range(MaleThreadRodEnd, "threaded-stem"),
    section(FemaleThreadRodEnd("M20")),
    section(MaleThreadRodEnd("M20")),
    threaded_link("M12", length=90),
    screwed_pair("M12"),
]

# Lay the groups out so they do not overlap in the viewer.
show(*pack(groups, padding=40), render_joints=True)
