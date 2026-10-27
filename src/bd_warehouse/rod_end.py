"""

Parametric Rod Ends

name: rod_end.py
by:   Gabriel Jesus
date: September 10th 2026

desc: This python/build123d code is a parameterized rod end generator.

    Rod ends - also called ball joint heads or spherical rod ends - carry a
    radial spherical plain bearing in an eye at one end and a threaded shank at
    the other, and are the standard way to terminate a link in a mechanism.

    Dimensions follow DIN ISO 12240-4 (DIN 648) dimension series K, in both
    the tapped and the threaded stem version.  Three independent sources were
    used and cross-checked against each other:

    * The tapped type's body, thread and collar come from the JW Winco /
      Ganter DIN 648 metric catalogue table (13 bore sizes, 5 mm to 35 mm),
      which prints d1, d2, b1, b2, d3, d4, d5, d6, l1, l2, A/F, t, w and C0.
    * The threaded stem version comes from the same catalogue's own sheet
      (12 bore sizes, 5 mm to 30 mm), which prints d1, d2, l3, b1, b2, d3,
      d4, l1, l2, w and C0.  It gives no shank diameter because there is
      nothing to give: the stem is threaded rod of diameter d2.
    * The spherical plain bearing inside comes from ISO 12240-1:1998 table 4,
      dimension series K, whose own note states that the bearings of that
      series are the ones incorporated in the rod ends of ISO 12240-4:1998
      table 5.  Its D is the eye's press-fit seat, and its B, C and d1 agree
      row for row with both sheets' b1, b2 and d3.

    The two sheets print the same eye and the same bearing for a given bore,
    and differ only past the head - as the parts do.  Two things are worth
    knowing about the tabulated data:

    * The tapped sheet's 35 mm bore row departs from ISO 12240-1 series K (a
      narrower outer ring and smaller inner-ring end faces), and the threaded
      stem has no 35 mm size at all.  The catalogue is what is manufactured,
      so it is what this module tabulates.
    * The threaded stem sheet prints d3 = 29.6 at the 25 mm bore where the
      tapped sheet and ISO 12240-1 both print 29.5.  It is the same ring in
      the same eye, so 29.5 is tabulated for both.

    Neither sheet dimensions how the eye is carried into the shank, but both
    draw it, and a third drawing - mbo Osswald's own for the series K male
    thread - draws it the same way.  The eye's flanks run the full height of
    the head, b2 apart; outside them the body is a cone of half angle
    ``BLEND_ANGLE`` tangent to the eye's outer circle, which is why the drawn
    flank is straight and carries no radius.  All three drawings measure that
    cone tangent to the circle to within the width of their own lines.
    Below the head the flanks flare out at the same angle where the shank is
    the thicker of the two.

    Four readings bear on the angle, and none of the sheets dimensions it:

    * the threaded stem's front view, drawn at the 12 mm bore size, measures
      30.0 deg, and puts the cone's junction with the stem within 0.1 mm of
      where a 30 deg cone puts it;
    * solving the threaded stem table's own l1 - l3 chain for the angle -
      the thread starts where the blend ends - gives 28.7 deg to 30.2 deg on
      ten of its twelve sizes, the two largest carrying extra thread;
    * the tapped type's front view, drawn at the 25 mm bore size, measures
      31.5 deg;
    * mbo Osswald's drawing measures 31.4 deg.

    The readings span about 1.5 deg either way, so 30 is taken as the value:
    it is the round number a draughtsman picks, it is what the sheet drawn at
    a known size measures, and it puts the cone's apex exactly one eye
    diameter below the ball centre.  ``BLEND_ANGLE`` is a class attribute for
    anyone who would rather match a particular manufacturer.

    The tapped sheet on its own does not settle the construction either: at
    its proportions a fixed angle and a cone through (d5/2, -d4/2) coincide
    to within a millimetre.  The threaded stem's thin stem separates the two
    by 5 mm and picks the fixed angle.

    Both variants are modelled as the self-lubricating, maintenance-free type
    - a sintered bronze socket, no lubrication port.  A manufacturer's
    "standard" greased version, such as the one mbo Osswald draws, carries a
    lubrication nipple on the head that is not modelled here.

    The height of the tapped type's wrench collar is dimensioned nowhere and
    is not derivable, so it is a parameter whose default is measured off its
    drawing.  The threaded stem needs no such parameter: it has no collar,
    and the sheet's photograph shows none.

    Neither variant's thread form is modelled - the tapped hole is drawn at
    its basic minor diameter and the stem at its nominal diameter.

TODO: DIN 648 series E; left hand threads (the catalogue lists them, as M5L);
    the CETOP thread variants; real thread forms via bd_warehouse.thread.

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

from abc import ABC, abstractmethod
from math import cos, hypot, radians, sin, tan
from typing import ClassVar

from bd_materials.finishes import zinc_plate
from bd_materials.materials.metals import (
    AlloySteel,
    Bronze,
    alloy_steel,
    bronze,
    mild_steel,
)
from build123d.build_enums import Align, Mode
from build123d.geometry import Axis, Plane, Pos
from build123d.joints import RevoluteJoint, RigidJoint
from build123d.objects_part import BasePartObject, Cone, Cylinder, Sphere
from build123d.objects_sketch import Polygon, RegularPolygon
from build123d.operations_part import extrude
from build123d.pack import pack
from build123d.topology import Compound, Part, Solid

from bd_warehouse.fastener import (
    evaluate_parameter_dict,
    isolate_fastener_type,
    read_fastener_parameters_from_csv,
)

_CENTERED = (Align.CENTER, Align.CENTER, Align.CENTER)
_HANGING = (Align.CENTER, Align.CENTER, Align.MAX)
_STANDING = (Align.CENTER, Align.CENTER, Align.MIN)

#: Included angle of a standard twist drill, used for the tapped hole's point.
DRILL_POINT_ANGLE = 118


class RodEnd(ABC, BasePartObject):
    """Parametric Rod End

    Base class used to create standard rod ends. The eye's bore axis is the X
    axis, the ball centre is the origin and the shank runs along -Z, so the
    far end of the shank lies at ``z = -center_to_end`` - the threaded face on
    the tapped type, the end of the stem on the threaded one.

    Everything down to the eye is common to both: the eye itself, the bearing
    socket and ball inside it, and the cone that carries the eye into the
    shank. A derived class provides its own table and its own ``shank``.

    Args:
        size (str): rod end size named by its bore, e.g. "M10"
        rod_end_type (str): type identifier - e.g. "DIN648K"

    Raises:
        ValueError: rod_end_type is invalid
        ValueError: size is invalid

    """

    rod_end_data: ClassVar[dict[str, dict[str, str]]]
    """Each derived class must provide a rod_end_data dictionary"""

    #: Half angle of the eye-to-shank blend cone, in degrees off the shank
    #: axis. Neither sheet dimensions it and it is not derivable; 30 is what
    #: three independent readings agree on - see the module docstring.
    BLEND_ANGLE = 30.0

    @classmethod
    def types(cls) -> set[str]:
        """Return a set of the rod end types"""
        return set(p.split(":")[0] for p in list(cls.rod_end_data.values())[0].keys())

    @classmethod
    def sizes(cls, rod_end_type: str) -> list[str]:
        """Return a list of the rod end sizes for the given type"""
        return list(isolate_fastener_type(rod_end_type, cls.rod_end_data).keys())

    @property
    def bore_diameter(self) -> float:
        """Bore of the internal ring, d1 - the pin size the rod end takes"""
        return self.rod_end_dict["d1"]

    @property
    def thread_size(self) -> str:
        """ISO designation of the shank thread, such as M24x2"""
        return self._thread_designation

    @property
    def thread_diameter(self) -> float:
        """Nominal major diameter of the shank thread, d2"""
        return self.rod_end_dict["d2"]

    @property
    def thread_pitch(self) -> float:
        """Pitch of the shank thread"""
        return self.rod_end_dict["p"]

    @property
    def thread_minor_diameter(self) -> float:
        """Basic minor diameter of the shank thread, D1 = d2 - 1.0825 * P

        The thread form is not modelled, so this is the diameter the tapped
        hole is drawn at, and the diameter to draw a mating rod at if it is to
        screw in without the two simplified representations overlapping.
        """
        return self.thread_diameter - 1.0825 * self.thread_pitch

    @property
    def width(self) -> float:
        """Width of the internal ring, b1 - the rod end's widest point"""
        return self.rod_end_dict["b1"]

    @property
    def eye_width(self) -> float:
        """Width of the housing eye, b2"""
        return self.rod_end_dict["b2"]

    @property
    def ring_face_diameter(self) -> float:
        """Diameter of the internal ring's flat end faces, d3"""
        return self.rod_end_dict["d3"]

    @property
    def eye_diameter(self) -> float:
        """Outside diameter of the housing eye, d4"""
        return self.rod_end_dict["d4"]

    @property
    def shank_diameter(self) -> float:
        """Diameter of the shank, d5"""
        return self.rod_end_dict["d5"]

    @property
    def socket_diameter(self) -> float:
        """Press-fit seat the bearing socket sits in, D"""
        return self.rod_end_dict["D"]

    @property
    def center_to_end(self) -> float:
        """Ball centre to the threaded face, l1"""
        return self.rod_end_dict["l1"]

    @property
    def overall_length(self) -> float:
        """Eye crown to the threaded face, l2"""
        return self.rod_end_dict["l2"]

    @property
    def tilt_angle(self) -> float:
        """Maximum angle the ball may tilt out of line, w, in degrees"""
        return self.rod_end_dict["w"]

    @property
    def static_load_rating(self) -> float:
        """Static radial load rating C0 in kN

        The admissible static axial load is a fraction of this; DIN 648
        series K allows Fa = p * C0 with p < 0.2.
        """
        return self.rod_end_dict["C0"]

    @property
    def ball_diameter(self) -> float:
        """Spherical diameter of the internal ring, dk

        Neither source prints dk for a rod end, but the ring is a sphere
        truncated to ``b1`` whose cut faces measure ``d3``, which closes it.
        The results agree with ISO 12240-1 table 4 to within its rounding.
        """
        return 2 * hypot(self.ring_face_diameter / 2, self.width / 2)

    @property
    def blend_tangent_station(self) -> float:
        """Station the blend cone touches the eye's outer circle at

        Above it the head is a plain circle of ``d4``; below it the blend cone
        stands outside the eye.  A cone of half angle ``BLEND_ANGLE`` tangent
        to a circle of radius d4/2 touches it here.
        """
        return -self.eye_diameter / 2 * sin(radians(self.BLEND_ANGLE))

    @property
    def blend_tangent_radius(self) -> float:
        """Radius of the blend cone where it touches the eye's outer circle"""
        return self.eye_diameter / 2 * cos(radians(self.BLEND_ANGLE))

    @property
    def blend_base(self) -> float:
        """Station the blend cone runs out onto the shank at

        The cone's own radius reaches the shank's here, so this is where the
        head ends: the flanks stop, and below it the shank is plain.  The
        catalogue closes an independent chain on it - see the module
        docstring's note on the threaded stem's l1 - l3.
        """
        blend = radians(self.BLEND_ANGLE)
        return (self.shank_diameter / 2 * cos(blend) - self.eye_diameter / 2) / sin(
            blend
        )

    @property
    def flank_flare_station(self) -> float:
        """Station the eye's flanks finish flaring out onto the shank at

        Where the shank is thicker than the eye is wide, the flanks open out
        at the blend's angle below ``blend_base`` until they run off it and
        the shank is round again.  Where the shank is the thinner of the two -
        which it is on the smaller threaded stem sizes - there is nothing to
        flare and this is ``blend_base`` itself.
        """
        if self.shank_diameter <= self.eye_width:
            return self.blend_base
        return self.blend_base - (self.shank_diameter - self.eye_width) / (
            2 * tan(radians(self.BLEND_ANGLE))
        )

    @property
    def bore_axis(self) -> Axis:
        """Axis the pin turns about"""
        return Axis.X

    @property
    def rod_end_class(self) -> str:
        """Which derived class created this rod end"""
        return type(self).__name__

    @property
    def info(self) -> str:
        """Return identifying information"""
        return f"{self.rod_end_class}({self.rod_end_type}): {self.rod_end_size}"

    def __init__(self, size: str, rod_end_type: str = "DIN648K"):
        """Parse RodEnd input parameters"""
        self.rod_end_size = size.strip()
        if rod_end_type not in self.types():
            raise ValueError(f"{rod_end_type} invalid, must be one of {self.types()}")
        self.rod_end_type = rod_end_type

        try:
            parameters = isolate_fastener_type(self.rod_end_type, self.rod_end_data)[
                self.rod_end_size
            ]
        except KeyError as e:
            raise ValueError(
                f"{size} invalid, must be one of {self.sizes(self.rod_end_type)}"
            ) from e

        # The thread designation is catalogue data rather than something to
        # derive, so it is tabulated as a string and read back out here.
        self._thread_designation: str = parameters.pop("Thread")
        self.rod_end_dict = evaluate_parameter_dict(parameters, is_metric=True)

        super().__init__(self.make_rod_end())

        RevoluteJoint("pin", self, axis=self.bore_axis)
        RigidJoint("thread", self, Pos(Z=-self.center_to_end))
        self.label = f"{self.rod_end_class}-{self.rod_end_size}"

    def make_rod_end(self) -> Compound:
        """Assemble the three parts a rod end is made of"""
        housing = self.housing()
        housing.label = "Housing"
        housing.material = mild_steel(finish=zinc_plate())

        socket = self.bearing_socket()
        socket.label = "BearingSocket"
        socket.material = bronze(grade=Bronze.C93200_BEARING)

        ring = self.internal_ring()
        ring.label = "InternalRing"
        ring.material = alloy_steel(grade=AlloySteel.G52100_HARDENED_LOW_TEMPERED)

        return Compound(children=[housing, socket, ring])

    @abstractmethod
    def shank(self) -> Part:
        """Each derived class must provide the threaded end, already positioned
        in the rod end's frame and with its thread already cut"""
        raise NotImplementedError  # pragma: no cover

    def housing(self) -> Solid:
        """The one piece steel body: the eye, the cone that carries it into
        the shank and the shank itself, held to the eye's width through the
        head and bored for the bearing socket

        The shank stands proud of the eye - d5 is larger than b2 on every
        size - so it is the flank envelope, not a relief cut, that keeps the
        body from spreading out alongside the eye.
        """
        body = (self.eye() + self.blend() + self.shank()) & self.flank_envelope()

        # The socket's press-fit seat is bored right through the eye. Nothing
        # else reaches in this far: every point of the blend cone's surface
        # lies d4/2 from the ball centre or more, which is the tangency the
        # cone is built on, so the ball's envelope is clear without relieving
        # it.
        body -= Cylinder(
            self.socket_diameter / 2,
            self.eye_width,
            rotation=(0, 90, 0),
            mode=Mode.PRIVATE,
        )
        return body.solid()

    def blend(self) -> Part:
        """The cone that carries the eye into the shank

        It rises from the shank's own diameter at ``blend_base`` and runs up
        tangent to the eye's outer circle, so eye and shank meet without a
        fillet - which is what both catalogue front views draw.
        """
        return Pos(Z=self.blend_base) * Cone(
            bottom_radius=self.shank_diameter / 2,
            top_radius=self.blend_tangent_radius,
            height=self.blend_tangent_station - self.blend_base,
            align=_STANDING,
            mode=Mode.PRIVATE,
        )

    def flank_envelope(self) -> Part:
        """The prism the body is held inside, not a piece of the rod end

        It is b2 thick over the head, flares out at the blend's angle below
        ``blend_base`` where the shank is the thicker of the two, and
        constrains nothing past ``flank_flare_station`` - leaving the shank
        round and, on the tapped type, the collar its full width.
        """
        half_eye = self.eye_width / 2
        # Comfortably outside the part in both directions: past the crown of
        # the eye at one end and past the threaded face at the other.
        clear = self.eye_diameter
        # Down the right hand flank: the eye's width over the head, the flare
        # if there is one, then out of the way.
        flank = [(half_eye, clear), (half_eye, self.blend_base)]
        if self.flank_flare_station < self.blend_base:
            flank.append((self.shank_diameter / 2, self.flank_flare_station))
        flank += [
            (clear, self.flank_flare_station),
            (clear, -self.overall_length - clear),
        ]
        profile = Polygon(
            *flank,
            *[(-x, z) for x, z in reversed(flank)],
            align=None,
            mode=Mode.PRIVATE,
        )
        return extrude(Plane.XZ * profile, amount=clear, both=True, mode=Mode.PRIVATE)

    def eye(self) -> Part:
        """The solid disc the eye is bored out of"""
        return Cylinder(
            self.eye_diameter / 2,
            self.eye_width,
            rotation=(0, 90, 0),
            align=_CENTERED,
            mode=Mode.PRIVATE,
        )

    def bearing_socket(self) -> Solid:
        """The self lubricating bronze shell between the housing and the ball"""
        socket = Cylinder(
            self.socket_diameter / 2,
            self.eye_width,
            rotation=(0, 90, 0),
            align=_CENTERED,
            mode=Mode.PRIVATE,
        )
        socket -= Sphere(self.ball_diameter / 2, mode=Mode.PRIVATE)
        return socket.solid()

    def internal_ring(self) -> Solid:
        """The hardened steel ball: a sphere truncated to b1 and bored to d1"""
        ball_radius = self.ball_diameter / 2
        ring = Sphere(ball_radius, mode=Mode.PRIVATE) & Cylinder(
            self.ball_diameter,
            self.width,
            rotation=(0, 90, 0),
            align=_CENTERED,
            mode=Mode.PRIVATE,
        )
        ring -= Cylinder(
            self.bore_diameter / 2,
            2 * self.ball_diameter,
            rotation=(0, 90, 0),
            align=_CENTERED,
            mode=Mode.PRIVATE,
        )
        return ring.solid()


class FemaleThreadRodEnd(RodEnd):
    """Rod End, Female Thread

    DIN ISO 12240-4 (DIN 648) series K rod end with a tapped shank - the
    "tapped type", which a male threaded rod or turnbuckle screws into. The
    shank carries a collar with wrench flats at its threaded end.

    The tapped hole is drawn at the thread's basic minor diameter with a
    drilled point beyond the usable depth; the thread form itself is not
    modelled.

    Args:
        size (str): rod end size named by its bore, e.g. "M10"
        rod_end_type (str): type identifier - e.g. "DIN648K"
        collar_height (float): height of the wrench collar. Defaults to
            ``COLLAR_HEIGHT_RATIO`` times the shank diameter.

    """

    rod_end_data = read_fastener_parameters_from_csv("rod_end_parameters.csv")

    #: Collar height as a fraction of the shank diameter. The catalogue drawing
    #: does not dimension it; 0.35 is measured off that drawing.
    COLLAR_HEIGHT_RATIO = 0.35

    def __init__(
        self,
        size: str,
        rod_end_type: str = "DIN648K",
        collar_height: float | None = None,
    ):
        """Parse FemaleThreadRodEnd input parameters"""
        # Stashed before the body is built, which is what consumes it.
        self._collar_height = collar_height
        super().__init__(size, rod_end_type)

    @property
    def collar_height(self) -> float:
        """Height of the wrench collar at the threaded end"""
        if self._collar_height is None:
            return self.COLLAR_HEIGHT_RATIO * self.shank_diameter
        return self._collar_height

    @property
    def collar_diameter(self) -> float:
        """Diameter of the wrench collar at the threaded end, d6"""
        return self.rod_end_dict["d6"]

    @property
    def collar_width(self) -> float:
        """Wrench opening across the collar's flats, A/F"""
        return self.rod_end_dict["AF"]

    @property
    def thread_depth(self) -> float:
        """Usable depth of the tapped hole, t"""
        return self.rod_end_dict["t"]

    def shank(self) -> Part:
        """The tapped shank: a stem, a wrench collar and the tapped hole"""
        threaded_face = -self.center_to_end

        # The stem reaches up to the ball centre, where the eye and the blend
        # cone stand outside it; the flank envelope holds whatever of it runs
        # alongside the eye to the eye's own width.
        stem = Cylinder(
            self.shank_diameter / 2,
            self.center_to_end - self.collar_height,
            align=_HANGING,
            mode=Mode.PRIVATE,
        )
        return stem + self._collar(threaded_face) - self._tapped_hole(threaded_face)

    def _collar(self, threaded_face: float) -> Part:
        """A boss of diameter d6 with wrench flats A/F across it

        The flats are the wrench opening, so on the smaller sizes they cut
        away less than the boss's full hexagon and leave its corners rounded.
        """
        boss = Pos(Z=threaded_face) * Cylinder(
            self.collar_diameter / 2,
            self.collar_height,
            align=_STANDING,
            mode=Mode.PRIVATE,
        )
        flats = extrude(
            Pos(Z=threaded_face)
            * RegularPolygon(
                self.collar_width / 2, 6, major_radius=False, mode=Mode.PRIVATE
            ),
            amount=self.collar_height,
            mode=Mode.PRIVATE,
        )
        return boss & flats

    def _tapped_hole(self, threaded_face: float) -> Part:
        """The tapped hole, at its basic minor diameter, plus a drill point"""
        minor_radius = self.thread_minor_diameter / 2
        tapped = Pos(Z=threaded_face) * Cylinder(
            minor_radius, self.thread_depth, align=_STANDING, mode=Mode.PRIVATE
        )
        point = Pos(Z=threaded_face + self.thread_depth) * Cone(
            bottom_radius=minor_radius,
            top_radius=0,
            height=minor_radius / tan(radians(DRILL_POINT_ANGLE / 2)),
            align=_STANDING,
            mode=Mode.PRIVATE,
        )
        return tapped + point


class MaleThreadRodEnd(RodEnd):
    """Rod End, Male Thread

    DIN ISO 12240-4 (DIN 648) series K rod end with a threaded stem - the
    "male thread" version, which screws into a tapped part or takes a nut.
    The stem is plain threaded rod: the sheet prints no wrench flats and the
    catalogue photograph shows none, so there is nothing to grip but the
    thread itself.

    The thread form is not modelled - the stem is drawn at the thread's
    nominal diameter, with a lead-in chamfer at its end - so ``thread_length``
    is carried as data rather than cut.

    Args:
        size (str): rod end size named by its bore, e.g. "M10"
        rod_end_type (str): type identifier - e.g. "DIN648K"

    """

    rod_end_data = read_fastener_parameters_from_csv(
        "rod_end_with_threaded_stem_parameters.csv"
    )

    @property
    def shank_diameter(self) -> float:
        """Diameter of the stem, which is the thread's own nominal diameter

        The threaded stem sheet prints no separate shank dimension because
        there is nothing to print: the stem is threaded rod of diameter d2.
        Its front view measures the stem at d2, and the catalogue's own
        l1 - l3 chain closes on the blend that a d2 stem gives.
        """
        return self.thread_diameter

    @property
    def thread_length(self) -> float:
        """Length of thread at the end of the stem, l3

        Not cut, since the thread form is not modelled, but it is what a nut
        or a tapped part has to reach.  On all but the two largest sizes the
        thread starts within a millimetre of ``blend_base``.
        """
        return self.rod_end_dict["l3"]

    @property
    def thread_chamfer(self) -> float:
        """Lead-in chamfer at the end of the stem, at 45 degrees

        Undimensioned, but the sheet draws the end face at 9.9 mm on the
        12 mm bore size where the thread's basic minor diameter is 10.1, so
        the chamfer takes the crests down to the minor diameter - which is
        how a thread end is chamfered.  The sheet draws it a little longer
        axially than 45 degrees gives.
        """
        return (self.thread_diameter - self.thread_minor_diameter) / 2

    def shank(self) -> Part:
        """The threaded stem: a plain cylinder of d2 with a lead-in chamfer"""
        stem_radius = self.shank_diameter / 2
        # The stem reaches up to the ball centre, where the eye and the blend
        # cone stand outside it; the flank envelope holds whatever of it runs
        # alongside the eye to the eye's own width.
        stem = Cylinder(
            stem_radius,
            self.center_to_end - self.thread_chamfer,
            align=_HANGING,
            mode=Mode.PRIVATE,
        )
        lead_in = Pos(Z=-self.center_to_end) * Cone(
            bottom_radius=stem_radius - self.thread_chamfer,
            top_radius=stem_radius,
            height=self.thread_chamfer,
            align=_STANDING,
            mode=Mode.PRIVATE,
        )
        return stem + lead_in


if __name__ == "__main__":
    from ocp_vscode import Camera, set_defaults, show

    set_defaults(reset_camera=Camera.CENTER)

    rod_ends = [
        rod_end_class(size)
        for rod_end_class in (FemaleThreadRodEnd, MaleThreadRodEnd)
        for size in rod_end_class.sizes("DIN648K")
    ]
    show(pack(rod_ends, padding=5, align_z=True), render_joints=True)
