"""

Parametric Bushings

name: bushing.py
by:   Gumyr
date: July 31st 2026

desc: This python/build123d code provides parameterized bushings.

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

from __future__ import annotations

import math

from bd_materials.materials.metals import stainless
from build123d.build_common import Locations
from build123d.build_enums import Align, Mode
from build123d.build_part import BuildPart
from build123d.build_sketch import BuildSketch
from build123d.geometry import Axis, Location, Plane, RotationLike
from build123d.joints import RigidJoint
from build123d.objects_part import BasePartObject, Cylinder, Hole
from build123d.objects_sketch import Rectangle, RegularPolygon
from build123d.operations_generic import chamfer
from build123d.operations_part import extrude, revolve


class HexFlangedEccentricBushing(BasePartObject):
    """A cylindrical eccentric bushing with a wrenchable hex flange.

    The cylindrical body and hex flange share the local Z axis. The bore is
    displaced from that axis by ``eccentricity`` along +X.

    This is a generic catalog-style component, not an implementation of an
    ISO, DIN, or other dimensional standard.

    Args:
        bore_diameter (float): Diameter of the through bore.
        body_diameter (float): Diameter of the cylindrical mounting body.
        body_length (float): Length of the cylindrical body below the flange.
        flange_height (float): Axial thickness of the hex flange.
        hex_size (float): Width across flats of the hex flange.
        eccentricity (float): Distance between the bore and body axes.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Align | tuple[Align, Align, Align], optional): object
            alignment. Defaults to Align.NONE.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.

    Attributes:
        overall_length: Sum of ``body_length`` and ``flange_height``.
        joints: An ``outer_center`` joint at the center of the underside of the hex
            flange and an ``ecc_top_center`` joint at the eccentric bore center on top.

    Raises:
        ValueError: If a dimension is invalid or the bore breaks through the
            cylindrical body.
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        bore_diameter: float,
        body_diameter: float,
        body_length: float,
        flange_height: float,
        hex_size: float,
        eccentricity: float,
        rotation: RotationLike = (0, 0, 0),
        align: Align | tuple[Align, Align, Align] = Align.NONE,
        mode: Mode = Mode.ADD,
    ):
        if eccentricity < 0:
            raise ValueError("eccentricity must be non-negative")

        if bore_diameter + 2 * eccentricity >= body_diameter:
            raise ValueError(
                "bore_diameter plus twice eccentricity must be less than "
                "body_diameter"
            )
        if hex_size < body_diameter:
            raise ValueError("hex_size must be at least body_diameter")

        self.bore_diameter = bore_diameter
        self.body_diameter = body_diameter
        self.body_length = body_length
        self.flange_height = flange_height
        self.hex_size = hex_size
        self.eccentricity = eccentricity
        self.overall_length = body_length + flange_height

        # Create a hexagonal prism and intersect it with the revolved screw-head
        # profile used by the fastener module to round off its top perimeter.
        hex_diagonal = hex_size / math.cos(math.pi / 6)
        with BuildPart() as bushing:
            with BuildSketch():
                RegularPolygon(hex_size / 2, 6, major_radius=False)
            extrude(amount=flange_height)
            with BuildSketch(Plane.XZ) as head_profile:
                Rectangle(hex_diagonal / 2, flange_height, align=Align.MIN)
                chamfer(
                    head_profile.vertices().group_by(Axis.Y)[-1].sort_by(Axis.X)[-1],
                    (hex_diagonal - hex_size) / 2,
                )
            revolve(mode=Mode.INTERSECT)
            Cylinder(
                body_diameter / 2,
                body_length,
                align=(Align.CENTER, Align.CENTER, Align.MAX),
            )
            with Locations((eccentricity, 0, 0)):
                Hole(bore_diameter / 2)

        assert bushing.part is not None

        super().__init__(
            bushing.part,
            rotation=rotation,
            align=align,
            mode=mode,
        )
        self.label = "HexFlangedEccentricBushing"
        self.material = stainless()
        RigidJoint("outer_center", self, Location())
        RigidJoint("ecc_top_center", self, Location((eccentricity, 0, flange_height)))
