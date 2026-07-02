"""

Parametric Retaining Rings

name: retaining_ring.py
by:   Gumyr
date: June 27th 2026

desc: This python/build123d code provides parameterized retaining rings.

license:

    Copyright 2026 Gumyr

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

import csv
from abc import ABC, abstractmethod
from importlib import resources
from typing import ClassVar

from build123d.build_enums import Align, GeomType, Mode, Tangency
from build123d.geometry import Axis, Color, Location, Plane, Pos, RotationLike
from build123d.joints import RigidJoint
from build123d.objects_curve import (
    CenterArc,
    ConstrainedArcs,
    ConstrainedLines,
    Line,
    Polyline,
    RadiusArc,
    ThreePointArc,
)
from build123d.objects_part import BasePartObject
from build123d.objects_sketch import Circle, Rectangle, SlotOverall
from build123d.operations_generic import fillet, mirror, split
from build123d.operations_part import extrude
from build123d.topology import Edge, Face, Part, ShapeList, Solid, Wire

import bd_warehouse


def read_retaining_ring_parameters_from_csv(
    filename: str,
) -> dict[str, dict[str, float]]:
    """Parse a metric retaining ring CSV parameter file."""
    parameters = {}
    data_resource = resources.files(bd_warehouse) / f"data/{filename}"

    with data_resource.open(encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        if not reader.fieldnames:
            raise ValueError(f"No header found in {filename}")
        size_field = reader.fieldnames[0]
        for row in reader:
            size = row.pop(size_field)
            if not size:
                continue
            parameters[size] = {
                name: float(value)
                for name, value in row.items()
                if name is not None and value not in (None, "")
            }
            parameters[size][size_field] = float(size)
    return parameters


class RetainingRing(ABC, BasePartObject):
    """Base class for standardized retaining rings.

    Args:
        size: Nominal shaft or bore diameter as listed in the applicable standard.
        rotation: Sequence of angles about the X, Y, and Z axes. Defaults to (0, 0, 0).
        align: Align MIN, CENTER, or MAX of object. Defaults to None, which places
            the minimum Z face on the placement plane while remaining centered in XY.
        mode: Combination mode. Defaults to Mode.ADD.

    Raises:
        ValueError: Invalid retaining ring size.
    """

    ring_data: ClassVar[dict[str, dict[str, float]]]
    standard: ClassVar[str]

    @classmethod
    def sizes(cls) -> list[str]:
        """Return the available nominal sizes for this retaining ring class."""
        return list(cls.ring_data.keys())

    @classmethod
    def parameters(cls, size: str) -> dict[str, float]:
        """Return the evaluated metric parameters for a nominal size."""
        normalized_size = size.strip()
        try:
            parameters = cls.ring_data[normalized_size]
        except KeyError as e:
            raise ValueError(f"{size} invalid, must be one of {cls.sizes()}") from e
        return parameters.copy()

    @property
    def info(self) -> str:
        """Return identifying information for this retaining ring."""
        return f"{self.__class__.__name__}({self.standard}): {self.ring_size}"

    @classmethod
    def select_by_size(cls, size: str) -> dict[type["RetainingRing"], list[str]]:
        """Return retaining ring classes and standards available in the given size."""
        ring_classes = cls.__subclasses__() if cls is RetainingRing else [cls]
        return {
            ring_class: [ring_class.standard]
            for ring_class in ring_classes
            if size.strip() in ring_class.sizes()
        }

    @abstractmethod
    def make_ring(self) -> Part:
        """Create the retaining ring CAD object."""
        raise NotImplementedError  # pragma: no cover

    def __init__(
        self,
        size: str,
        rotation: RotationLike = (0, 0, 0),
        align: Align | tuple[Align, Align, Align] | None = None,
        mode: Mode = Mode.ADD,
    ):
        self.ring_size = size.strip()
        self.ring_dict = self.parameters(self.ring_size)

        super().__init__(
            part=self.make_ring(),
            rotation=rotation,
            align=align,
            mode=mode,
        )
        self.label = f"{self.__class__.__name__}-{self.ring_size}"
        self.color = Color(0xC0C0C0)
        # Fine the two largest planar faces at "top" and "bottom"
        top_bottom = self.faces().group_by(Face.area)[-1]
        center_index = -2 if isinstance(self, ExternalSnapRing) else -1
        center_locs = []
        for i, face in enumerate(top_bottom):
            arc_center = (
                face.edges()
                .filter_by(GeomType.CIRCLE)
                .sort_by(Edge.radius)[center_index]
                .arc_center
            )
            normal = face.normal_at(arc_center)
            center_locs.append(
                Location(Plane(arc_center, z_dir=(-1 if i == 0 else 1) * normal))
            )
        RigidJoint("a", self, center_locs[0])
        RigidJoint("b", self, center_locs[1])


class ExternalSnapRing(RetainingRing):
    """External retaining ring for shafts as defined by DIN 471."""

    standard = "DIN471"
    ring_data = read_retaining_ring_parameters_from_csv("din471.csv")

    def make_ring(self) -> Part:
        """Create the external retaining ring using the DIN 471 dimensions.

        DIN 471 specifies the critical dimensions but leaves the transitions between
        the ring body and lugs illustrative. This construction creates a smooth,
        symmetric approximation that honors ``d3``, ``a``, ``b``, ``d5``, and ``s``.
        """
        d3, b, a, d5, s = (self.ring_dict[p] for p in ["d3", "b", "a", "d5", "s"])

        # Sizes 3-9 need a compact overlapping-slot construction because their lug
        # proportions do not leave enough room for the general tangent-arc profile.
        if int(self.ring_size) <= 9:
            ring_plan = Pos(Y=b / 4) * Circle((d3 + 3 * b / 2) / 2)
            ring_plan += Pos(Y=-d3 / 2 - a / 2) * SlotOverall(3 * d5, a)
            ring_plan = fillet(ring_plan.vertices().group_by(Axis.Y)[1], 2 * d5)
            ring_plan -= Circle(d3 / 2)
            ring_plan -= Rectangle(d5, 2 * d3, align=(Align.CENTER, Align.MAX))
            ring_plan -= Pos(Y=-d3 / 2 - a / 2) * SlotOverall(2 * d5, d5)
        else:
            # The helper circles locate a smooth tangent transition from the ring body
            # to one plier lug. Only half is retained and mirrored for exact symmetry.
            c1_cntr = CenterArc((0, 0), d3 / 2 + b, 0, 90).intersect(
                Axis((d3 / 5, 0), (0, 1))
            )[0]
            c2_cntr = CenterArc((0, 0), d3 / 2 + a, 270, 90).intersect(
                Axis((a / 1.5 + 2.5 * d5, 0), (0, 1))
            )[0]
            cntr_path = ThreePointArc(c2_cntr, ((d3 + a + b) / 2, 0), c1_cntr)

            c1 = CenterArc(c1_cntr, b / 5, 0, 360)
            c2 = CenterArc(c2_cntr, a / 1.5, 0, 360)
            a1 = (
                ConstrainedArcs(
                    (c1, Tangency.OUTSIDE), c2, radius=cntr_path.radius - a / 2
                )
                .edges()
                .sort_by(Axis.X)[-1]
            )
            a1_top = a1.vertices().sort_by(Axis.Y)[-1]
            a1_bot = a1.vertices().sort_by(Axis.Y)[0]
            p = Polyline(
                a1_top,
                a1_top + (0, b),
                a1_top + (d3, b),
                a1_bot + (d3, -a),
                a1_bot + (0, -a),
                a1_bot,
            )
            ring_plan = Pos(Y=(b - a) / 2) * Circle((d3 + a + b) / 2)
            ring_plan -= [Face(Wire(c)) for c in (c1, c2)]
            ring_plan -= Face(Wire(p.edges() + [a1]))
            ring_plan = fillet(ring_plan.vertices().sort_by(Axis.Y)[0], a / 2)
            ring_plan -= Circle(d3 / 2)
            ring_plan -= Rectangle(d5, d3, align=(Align.CENTER, Align.MAX))
            ring_plan -= Pos(
                CenterArc((0, 0), (d3 + a) / 2, 270, 90).intersect(
                    Axis((1.5 * d5, 0), (0, 1))
                )[0]
            ) * Circle(d5 / 2)
            ring_plan = split(ring_plan, Plane.YZ)
            ring_plan += mirror(ring_plan, Plane.YZ)

        # Create the Solid
        ring = extrude(ring_plan, s)

        return ring


class InternalSnapRing(RetainingRing):
    """Internal retaining ring for bores as defined by DIN 472."""

    standard = "DIN472"
    ring_data = read_retaining_ring_parameters_from_csv("din472.csv")

    def make_ring(self) -> Part:
        """Create the canonical DIN 472 internal retaining ring.

        This uses the ``d1 <= 300 mm`` Detail X lug profile for every tabulated size.
        DIN 472's optional manufacturer-selected lug profiles are not modeled. The
        resulting symmetric approximation honors ``d3``, ``a``, ``b``, ``d5``, and
        ``s``.
        """
        d3, b, a, d5, s = (self.ring_dict[p] for p in ["d3", "b", "a", "d5", "s"])
        c1 = CenterArc((0, 0), (d3 - a) / 2, 270, 90)

        # Sizes 8-11 need the smaller offset to keep their compact lug connected;
        # larger rings have enough material for a two-hole-diameter offset.
        a1 = Axis((1.5 * d5 if int(self.ring_size) < 12 else 2 * d5, 0), (0, 1))
        i = c1.intersect(a1)[0]

        ring_plan = base = Circle(d3 / 2)
        ring_plan -= (hole := Pos(Y=-b / 4) * Circle((d3 - 3 * b / 2) / 2))
        ring_plan = split(ring_plan, -Plane((0, 0), x_dir=i, y_dir=(0, 0, 1)))
        ring_plan += (end_loop := Pos(i) * Circle(a / 2))

        # Fillet the internal sharp corner
        interior_corner = (end_loop & hole).vertices().sort_by(Axis.Y)[-1]
        ring_plan = fillet(
            ring_plan.vertices().sort_by_distance(interior_corner)[0], a / 3
        )

        # Build the squarish corner
        l1 = ConstrainedLines((0, 0), end_loop.edge()).edges().sort_by(Axis.X)
        i2 = ShapeList(Axis(l1[0]).intersect(base.edge())).sort_by(Axis.Y)[0]
        l2 = Line(i2, l1[0].vertices().sort_by(Axis.Y)[0])
        i3 = ShapeList(Axis(l1[1]).intersect(base.edge())).sort_by(Axis.X)[-1]
        a2 = RadiusArc(i2, i3, -d3 / 2)
        l3 = Line(i, i3)
        l4 = Line(l1[0] @ 0, i)
        ring_plan += -Face(Wire([l2, a2, l3, l4]))
        ring_plan -= Pos(i) * Circle(d5 / 2)

        # Create the other side
        ring_plan += mirror(ring_plan, Plane.YZ)

        # Create the Solid
        ring = extrude(ring_plan, s)
        return ring


class RetainingRingGroove(BasePartObject):
    """Groove cutter for a DIN 471 or DIN 472 retaining ring.

    The groove uses the nominal diameter ``d2`` and width ``m`` specified for the
    supplied ring. The standard's clearance diameter ``d4`` extends the cutter beyond
    the nominal shaft or bore surface to provide reliable Boolean overlap.

    Args:
        ring: External or internal retaining ring that defines the groove dimensions.
        rotation: Sequence of angles about the X, Y, and Z axes. Defaults to (0, 0, 0).
        align: Align MIN, CENTER, or MAX of the cutter. Defaults to None, which places
            the minimum Z face on the placement plane while remaining centered in XY.
        mode: Combination mode. Defaults to Mode.SUBTRACT.

    Raises:
        ValueError: ``ring`` is not an ExternalSnapRing or InternalSnapRing.
    """

    def __init__(
        self,
        ring: RetainingRing,
        rotation: RotationLike = (0, 0, 0),
        align: Align | tuple[Align, Align, Align] | None = None,
        mode: Mode = Mode.SUBTRACT,
    ):
        if not isinstance(ring, (ExternalSnapRing, InternalSnapRing)):
            raise ValueError(
                "RetainingRingGroove only accepts ExternalSnapRing or InternalSnapRing"
            )

        self.ring = ring
        self.groove_diameter = ring.ring_dict["d2"]
        self.groove_width = ring.ring_dict["m"]
        self.clearance_diameter = ring.ring_dict["d4"]

        if isinstance(ring, ExternalSnapRing):
            inner_diameter = self.groove_diameter
            outer_diameter = self.clearance_diameter
        else:
            inner_diameter = self.clearance_diameter
            outer_diameter = self.groove_diameter

        groove = Solid.make_cylinder(outer_diameter / 2, self.groove_width)
        groove -= Solid.make_cylinder(inner_diameter / 2, self.groove_width)

        super().__init__(
            part=groove,
            rotation=rotation,
            align=align,
            mode=mode,
        )
        self.label = f"RetainingRingGroove-{ring.standard}-{ring.ring_size}"


if __name__ == "__main__":
    from ocp_vscode import show_all

    external_ring = ExternalSnapRing("40")
    # rings = []
    # stack_height = 0.0
    # for size in reversed(ExternalSnapRing.sizes()):
    #     try:
    #         ring = Pos(Z=stack_height) * ExternalSnapRing(str(size))
    #         rings.append(ring)
    #         stack_height += ring.ring_dict["s"]
    #     except Exception as error:  # pylint: disable=broad-exception-caught
    #         print(f"{size} failed: {error}")

    internal_ring = InternalSnapRing("30")
    # for size in reversed(InternalSnapRing.sizes()):
    #     try:
    #         ring = Pos(Z=stack_height) * InternalSnapRing(str(size))
    #         rings.append(ring)
    #         stack_height += ring.ring_dict["s"]
    #     except Exception as error:  # pylint: disable=broad-exception-caught
    #         print(f"{size} failed: {error}")

    show_all()
