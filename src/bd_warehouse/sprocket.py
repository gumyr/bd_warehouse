"""

Parametric Sprockets

name: sprocket.py
by:   Gumyr
date: February 13th 2026

desc:

    This python/build123d code is a parameterized chain sprocket generator.
    Given a chain pitch, a number of teeth and other optional parameters, a
    sprocket centered on the origin is generated.

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

from math import sin, asin, cos, pi, radians, sqrt
from build123d import *


#
#  =============================== CLASSES ===============================
#
class Sprocket(BasePartObject):
    """
    Create a new sprocket object as defined by the given parameters. The input parameter
    defaults are appropriate for a standard bicycle chain.

    Args:
        num_teeth (int): number of teeth on the perimeter of the sprocket
        chain_pitch (float): distance between the centers of two adjacent rollers.
            Defaults to 1/2 inch.
        roller_diameter (float): size of the cylindrical rollers within the chain.
            Defaults to 5/16 inch.
        clearance (float): size of the gap between the chain's rollers and the sprocket's teeth.
            Defaults to 0.
        thickness (float): thickness of the sprocket.
            Defaults to 0.084 inch.
        bolt_circle_diameter (float): diameter of the mounting bolt hole pattern.
            Defaults to 0.
        num_mount_bolts (int): number of bolt holes (default 0) - if 0, no bolt holes
            are added to the sprocket
        mount_bolt_diameter (float): size of the bolt holes use to mount the sprocket.
            Defaults to 0.
        bore_diameter (float): size of the central hole in the sprocket (default 0) - if 0,
            no bore hole is added to the sprocket

    **NOTE**: Default parameters are for standard single sprocket bicycle chains.

    Attributes:
        pitch_radius (float): radius of the circle formed by the center of the chain rollers
        outer_radius (float): size of the sprocket from center to tip of the teeth
        pitch_circumference (float): circumference of the sprocket at the pitch radius

    Example:

        .. doctest::

            >>> s = Sprocket(num_teeth=32)
            >>> print(s.pitch_radius)
            64.78458745735234
            >>> s.rotate((0,0,0),(0,0,1),10)

    """

    @property
    def pitch_radius(self):
        """The radius of the circle formed by the center of the chain rollers"""
        return Sprocket.sprocket_pitch_radius(self.num_teeth, self.chain_pitch)

    @property
    def outer_radius(self):
        """The size of the sprocket from center to tip of the teeth"""
        if self._flat_teeth:
            o_radius = self.pitch_radius + self.roller_diameter / 4
        else:
            o_radius = sqrt(self.pitch_radius**2 - (self.chain_pitch / 2) ** 2) + sqrt(
                (self.chain_pitch - self.roller_diameter / 2) ** 2
                - (self.chain_pitch / 2) ** 2
            )
        return o_radius

    @property
    def pitch_circumference(self):
        """The circumference of the sprocket at the pitch radius"""
        return Sprocket.sprocket_circumference(self.num_teeth, self.chain_pitch)

    def __init__(
        self,
        num_teeth: int,
        chain_pitch: float = (1 / 2) * IN,
        roller_diameter: float = (5 / 16) * IN,
        clearance: float = 0.0,
        thickness: float = 0.084 * IN,
        bolt_circle_diameter: float = 0.0,
        num_mount_bolts: int = 0,
        mount_bolt_diameter: float = 0.0,
        bore_diameter: float = 0.0,
        rotation: RotationLike = (0, 0, 0),
        align: None | Align | tuple[Align, Align, Align] = Align.CENTER,
        mode: Mode = Mode.ADD,
    ):
        """Validate inputs and create the chain assembly object"""
        self.num_teeth = num_teeth
        self.chain_pitch = chain_pitch
        self.roller_diameter = roller_diameter
        self.clearance = clearance
        self.thickness = thickness
        self.bolt_circle_diameter = bolt_circle_diameter
        self.num_mount_bolts = num_mount_bolts
        self.mount_bolt_diameter = mount_bolt_diameter
        self.bore_diameter = bore_diameter

        # Validate inputs
        """Ensure that the roller would fit in the chain"""
        if self.roller_diameter >= self.chain_pitch:
            raise ValueError(
                f"roller_diameter {self.roller_diameter} is too large for chain_pitch {self.chain_pitch}"
            )
        if not isinstance(num_teeth, int) or num_teeth <= 2:
            raise ValueError(
                f"num_teeth must be an integer greater than 2 not {num_teeth}"
            )
        # Create the sprocket ()
        sprocket = self._make_sprocket()

        # Remove an extraneous Compound wrapper
        if isinstance(sprocket, Compound):
            sprocket = sprocket.unwrap()

        super().__init__(sprocket, rotation, align, mode)

    def _make_sprocket(self) -> Compound:
        """Create a new sprocket object as defined by the class attributes"""
        tooth = Sprocket._make_tooth_outline(
            self.num_teeth, self.chain_pitch, self.roller_diameter, self.clearance
        )
        sprocket_tooth_wires = ShapeList(PolarLocations(0, self.num_teeth) * tooth)
        sprocket_perimeter = Wire(e for e in sprocket_tooth_wires.edges())
        sprocket_face = Pos(Z=-self.thickness / 2) * Face(sprocket_perimeter)
        sprocket = Rot(Z=90) * extrude(sprocket_face, self.thickness)

        # Chamfer the outside edges if the sprocket has "flat" teeth determined by ..
        # .. extracting all the unique radii
        arc_list = sprocket.edges().filter_by(GeomType.CIRCLE).group_by(Edge.radius)[2]
        self._flat_teeth = len(arc_list) == 3
        if self._flat_teeth:
            sprocket = chamfer(arc_list, self.thickness * 0.25, self.thickness * 0.5)

        #
        # Create bolt holes
        if (
            self.bolt_circle_diameter != 0
            and self.num_mount_bolts != 0
            and self.mount_bolt_diameter != 0
        ):
            sprocket -= PolarLocations(
                self.bolt_circle_diameter / 2, self.num_mount_bolts
            ) * Cylinder(self.mount_bolt_diameter / 2, self.thickness)

        #
        # Create a central bore
        if self.bore_diameter != 0:
            sprocket -= Cylinder(self.bore_diameter / 2, self.thickness)
        return sprocket

    @staticmethod
    def sprocket_pitch_radius(num_teeth: int, chain_pitch: float) -> float:
        """
        Calculate and return the pitch radius of a sprocket with the given number of teeth
                                and chain pitch

        Parameters
        ----------
        num_teeth : int
            the number of teeth on the perimeter of the sprocket
        chain_pitch : float
            the distance between two adjacent pins in a single link (default 1/2 inch)
        """
        return sqrt(chain_pitch * chain_pitch / (2 * (1 - cos(2 * pi / num_teeth))))

    @staticmethod
    def sprocket_circumference(num_teeth: int, chain_pitch: float) -> float:
        """
        Calculate and return the pitch circumference of a sprocket with the given number of
                                teeth and chain pitch

        Parameters
        ----------
        num_teeth : int
            the number of teeth on the perimeter of the sprocket
        chain_pitch : float
            the distance between two adjacent pins in a single link (default 1/2 inch)
        """
        return (
            2
            * pi
            * sqrt(chain_pitch * chain_pitch / (2 * (1 - cos(2 * pi / num_teeth))))
        )

    @staticmethod
    def _make_tooth_outline(
        num_teeth: int,
        chain_pitch: float,
        roller_diameter: float,
        clearance: float = 0.0,
    ) -> Wire:
        """
        Create a Wire in the shape of a single tooth of the sprocket defined by the input parameters

        There are two different shapes that the tooth could take:
        1) "Spiky" teeth: given sufficiently large rollers, there is no circular top
        2) "Flat" teeth: given smaller rollers, a circular "flat" section bridges the
        space between roller slots
        """

        roller_rad = roller_diameter / 2 + clearance
        tooth_a_degrees = 360 / num_teeth
        half_tooth_a = radians(tooth_a_degrees / 2)
        pitch_rad = sqrt(chain_pitch**2 / (2 * (1 - cos(radians(tooth_a_degrees)))))
        outer_rad = pitch_rad + roller_rad / 2

        # Calculate the angle at which the tooth arc intersects the outside edge arc
        outer_intersect_a_r = asin(
            (
                outer_rad**3 * (-(pitch_rad * sin(half_tooth_a)))
                + sqrt(
                    outer_rad**6 * (-((pitch_rad * cos(half_tooth_a)) ** 2))
                    + 2
                    * outer_rad**4
                    * (chain_pitch - roller_rad) ** 2
                    * (pitch_rad * cos(half_tooth_a)) ** 2
                    + 2 * outer_rad**4 * (pitch_rad * cos(half_tooth_a)) ** 4
                    + 2
                    * outer_rad**4
                    * (pitch_rad * cos(half_tooth_a)) ** 2
                    * (pitch_rad * sin(half_tooth_a)) ** 2
                    - outer_rad**2
                    * (chain_pitch - roller_rad) ** 4
                    * (pitch_rad * cos(half_tooth_a)) ** 2
                    + 2
                    * outer_rad**2
                    * (chain_pitch - roller_rad) ** 2
                    * (pitch_rad * cos(half_tooth_a)) ** 4
                    + 2
                    * outer_rad**2
                    * (chain_pitch - roller_rad) ** 2
                    * (pitch_rad * cos(half_tooth_a)) ** 2
                    * (pitch_rad * sin(half_tooth_a)) ** 2
                    - outer_rad**2 * (pitch_rad * cos(half_tooth_a)) ** 6
                    - 2
                    * outer_rad**2
                    * (pitch_rad * cos(half_tooth_a)) ** 4
                    * (pitch_rad * sin(half_tooth_a)) ** 2
                    - outer_rad**2
                    * (pitch_rad * cos(half_tooth_a)) ** 2
                    * (pitch_rad * sin(half_tooth_a)) ** 4
                )
                + outer_rad
                * (chain_pitch - roller_rad) ** 2
                * (pitch_rad * sin(half_tooth_a))
                - outer_rad
                * (pitch_rad * cos(half_tooth_a)) ** 2
                * (pitch_rad * sin(half_tooth_a))
                - outer_rad * (pitch_rad * sin(half_tooth_a)) ** 3
            )
            / (
                2
                * (
                    outer_rad**2 * (pitch_rad * cos(half_tooth_a)) ** 2
                    + outer_rad**2 * (pitch_rad * sin(half_tooth_a)) ** 2
                )
            )
        )

        # Bottom of the roller arc
        start_pt = Vector(pitch_rad - roller_rad).rotate(Axis.Z, tooth_a_degrees / 2)
        # Where the roller arc meets transitions to the top half of the tooth
        tangent_pt = Vector(0, -roller_rad).rotate(
            Axis.Z, -tooth_a_degrees / 2
        ) + Vector(pitch_rad, 0).rotate(Axis.Z, tooth_a_degrees / 2)
        # The intersection point of the tooth and the outer rad
        outer_pt = Vector(
            outer_rad * cos(outer_intersect_a_r), outer_rad * sin(outer_intersect_a_r)
        )
        # The location of the tip of the spike if there is no "flat" section
        spike_pt = Vector(
            sqrt(pitch_rad**2 - (chain_pitch / 2) ** 2)
            + sqrt((chain_pitch - roller_rad) ** 2 - (chain_pitch / 2) ** 2),
        )

        # Generate the tooth outline
        if outer_pt.Y > 0:  # "Flat" topped sprockets
            l1 = RadiusArc(start_pt, tangent_pt, -roller_rad)
            l2 = RadiusArc(l1 @ 1, outer_pt, chain_pitch - roller_rad)
            l3 = RadiusArc(l2 @ 1, (outer_pt.X, -outer_pt.Y), outer_rad)
            l4 = RadiusArc(
                l3 @ 1, (tangent_pt.X, -tangent_pt.Y), chain_pitch - roller_rad
            )
            l5 = RadiusArc(l4 @ 1, (start_pt.X, -start_pt.Y), -roller_rad)
            tooth_perimeter = Wire([l1, l2, l3, l4, l5])
        else:  # "Spiky" sprockets
            l1 = RadiusArc(start_pt, tangent_pt, -roller_rad)
            l2 = RadiusArc(l1 @ 1, spike_pt, chain_pitch - roller_rad)
            l3 = RadiusArc(
                l1 @ 2, (tangent_pt.X, -tangent_pt.Y), chain_pitch - roller_rad
            )
            l4 = RadiusArc(l1 @ 3, (start_pt.X, -start_pt.Y), -roller_rad)
            tooth_perimeter = Wire([l1, l2, l3, l4])

        return tooth_perimeter


from ocp_vscode import show_all, show, Camera, set_defaults

set_defaults(reset_camera=Camera.KEEP)


s = Sprocket(32)
# s = Sprocket(16, chain_pitch=0.5 * IN, roller_diameter=0.49 * IN)
show_all()
