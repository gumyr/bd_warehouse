"""

Parametric Threads

name: thread.py
by:   Gumyr
date: November 11th 2021
      June 19th 2023 - ported to bd_warehouse

desc: A parameterized thread generator.

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

# pylint has trouble with the OCP imports
# pylint: disable=no-name-in-module, import-error
# pylint: disable=too-many-lines

import copy
import re
from math import copysign, radians, tan
from typing import Literal, Optional, Tuple, Union

from build123d.build_common import IN, MM
from build123d.build_enums import Align, Keep, Mode, SortBy
from build123d.build_line import BuildLine
from build123d.build_part import BuildPart
from build123d.build_sketch import BuildSketch
from build123d.geometry import Axis, Location, Plane, RotationLike
from build123d.joints import RigidJoint
from build123d.objects_curve import Helix, Polyline
from build123d.objects_part import BasePartObject
from build123d.operations_generic import add, mirror, scale, split
from build123d.operations_part import loft
from build123d.operations_sketch import make_face
from build123d.topology import Compound, Face, Solid, Wire, tuplify
from OCP.TopoDS import TopoDS_Shape


def is_safe(value: str) -> bool:
    """Evaluate if the given string is a fractional number safe for eval()"""
    return len(value) <= 10 and all(c in "0123456789./ " for c in set(value))


def imperial_str_to_float(measure: str) -> float:
    """Convert an imperial measurement (possibly a fraction) to a float value"""
    if is_safe(measure):
        # pylint: disable=eval-used
        # Before eval() is called the string extracted from the csv file is verified as safe
        result = eval(measure.strip().replace(" ", "+")) * IN
    else:
        result = measure
    return result


class Thread(BasePartObject):
    """Helical thread

    The most general thread class used to build all of the other threads.
    Creates right or left hand helical thread with the given
    root and apex radii.

    Args:
        apex_radius: Radius at the narrow tip of the thread.
        apex_width: Width at the narrow tip of the thread.
        root_radius: Radius at the wide base of the thread.
        root_width: Thread base width.
        pitch: Length of 360° of thread rotation.
        length: End to end length of the thread.
        apex_offset: Asymmetric thread apex offset from center. Defaults to 0.0.
        interference: Amount the thread will overlap with nut or bolt core. Used
            to help create valid threaded objects where the thread must fuse
            with another object. For threaded objects built as Compounds, this
            value could be set to 0.0. Defaults to 0.2.
        hand: Twist direction. Defaults to "right".
        taper_angle: Cone angle for tapered thread. Defaults to None.
        end_finishes: Profile of each end, one of:

            "raw"
                unfinished which typically results in the thread
                extended below z=0 or above z=length
            "fade"
                the thread height drops to zero over 90° of arc
                (or 1/4 pitch)
            "square"
                clipped by the z=0 or z=length plane
            "chamfer"
                conical ends which facilitates alignment of a bolt
                into a nut

            Defaults to ("raw","raw").
        simple: Stop at thread calculation, don't create thread. Defaults to False.

    Raises:
        ValueError: if end_finishes not in ["raw", "square", "fade", "chamfer"]:
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        apex_radius: float,
        apex_width: float,
        root_radius: float,
        root_width: float,
        pitch: float,
        length: float,
        apex_offset: float = 0.0,
        interference: float = 0.2,
        hand: Literal["right", "left"] = "right",
        taper_angle: Optional[float] = None,
        end_finishes: Tuple[
            Literal["raw", "square", "fade", "chamfer"],
            Literal["raw", "square", "fade", "chamfer"],
        ] = ("raw", "raw"),
        simple: bool = False,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        """Store the parameters and create the thread object"""
        for finish in end_finishes:
            if finish not in ["raw", "square", "fade", "chamfer"]:
                raise ValueError(
                    'end_finishes invalid, must be tuple() of "raw, square, fade, or chamfer"'
                )
        if taper_angle is not None:
            raise ValueError("taper_angle is not currently supported")
        self.external = apex_radius > root_radius
        self.apex_radius = apex_radius
        self.apex_width = apex_width
        self.root_radius = root_radius
        self.root_width = root_width
        self.pitch = pitch
        self.length = length
        self.apex_offset = apex_offset
        self.interference = interference
        self.right_hand = hand == "right"
        self.end_finishes = end_finishes
        self.tooth_height = abs(self.apex_radius - self.root_radius)
        self.taper = 0 if taper_angle is None else taper_angle
        self.simple = simple
        self.thread_loops = None

        # Create the thread profile
        with BuildSketch(mode=Mode.PRIVATE) as thread_face:
            height = self.apex_radius - self.root_radius
            overlap = -interference * copysign(1, height)
            with BuildLine():  # thread profile
                Polyline(
                    (self.root_width / 2, overlap),
                    (self.root_width / 2, 0),
                    (self.apex_width / 2 + self.apex_offset, height),
                    (-self.apex_width / 2 + self.apex_offset, height),
                    (-self.root_width / 2, 0),
                    (-self.root_width / 2, overlap),
                    close=True,
                )
                if not self.right_hand:
                    mirror(about=Plane.XZ, mode=Mode.REPLACE)
            make_face()
        self.thread_profile = thread_face.sketch_local.faces()[0]

        if simple:
            # Initialize with a valid shape then nullify
            super().__init__(part=Solid.make_box(1, 1, 1))
            self.wrapped = TopoDS_Shape()
        else:
            # Create base cylindrical thread
            number_faded_ends = self.end_finishes.count("fade")
            cylindrical_thread_length = length + pitch * (1 - 1 * number_faded_ends)
            self.thread_loops = cylindrical_thread_length / pitch
            if self.end_finishes[0] == "fade":
                cylindrical_thread_displacement = pitch / 2
            else:
                cylindrical_thread_displacement = -pitch / 2

            loops = []
            if self.thread_loops >= 1.0:
                full_loop = self._make_thread_loop(1.0)
                full_loop.label = "loop"
                loops = [copy.copy(full_loop) for _i in range(int(self.thread_loops))]
            if self.thread_loops % 1 > 0.0:
                last_loop = self._make_thread_loop(self.thread_loops % 1)
                last_loop.label = "partial"
                loops.append(last_loop)
            loops[0].locate(Location((0, 0, cylindrical_thread_displacement)))
            for i in range(1, len(loops)):
                loops[i - 1].joints["1"].connect_to(loops[i].joints["0"])

            bd_object = Compound(label="thread", children=loops)

            # Apply the end finishes. Note that it's significantly faster
            # to just apply the end finish to a single loop then the entire Compound
            # Bottom
            if self.end_finishes.count("chamfer") != 0:
                chamfer_shape = self._make_chamfer_shape()
            if end_finishes[0] == "fade":
                start_tip = self._make_fade_end(True)
                start_tip.label = "bottom_tip"
                loops[0].joints["0"].connect_to(start_tip.joints["0"])
                bd_object.children = list(bd_object.children) + [start_tip]
            elif end_finishes[0] in ["square", "chamfer"]:
                children = list(bd_object.children)
                bottom_loop = children.pop(0)
                label = bottom_loop.label
                if end_finishes[0] == "square":
                    bottom_loop = split(bottom_loop, bisect_by=Plane.XY, keep=Keep.TOP)
                else:
                    bottom_loop = bottom_loop.intersect(chamfer_shape)
                bottom_loop.label = label
                bd_object.children = [bottom_loop] + children

            # Top
            if end_finishes[1] == "fade":
                end_tip = self._make_fade_end(False)
                end_tip.label = "top_tip"
                loops[-1].joints["1"].connect_to(end_tip.joints["1"])
                bd_object.children = list(bd_object.children) + [end_tip]
            elif end_finishes[1] in ["square", "chamfer"]:
                children = list(bd_object.children)
                top_loops = []
                last_square = False
                for _ in range(3):
                    if not children:
                        continue
                    top_loop = children.pop(-1)
                    label = top_loop.label
                    # If this loop is entirely ABOVE the cut plane
                    # Skip the operation and do not add it to top_loops
                    bbox = top_loop.bounding_box()
                    if bbox.min.Z > self.length:
                        continue
                    if end_finishes[1] == "square":
                        # If this loop is entirely BELOW the plane
                        # Keep without splitting, stop checking future loops
                        if bbox.max.Z < self.length:
                            last_square = True
                        else:
                            top_loop = split(
                                top_loop,
                                bisect_by=Plane.XY.offset(self.length),
                                keep=Keep.BOTTOM,
                            )
                    else:
                        top_loop = top_loop.intersect(chamfer_shape)
                    if top_loop.volume != 0:
                        top_loop.label = label
                        top_loops.append(top_loop)
                    if last_square:
                        break
                bd_object.children = children + top_loops

            super().__init__(
                part=bd_object,
                rotation=rotation,
                align=tuplify(align, 3),
                mode=mode,
            )

    def _make_thread_loop(self, loop_height: float) -> Solid:
        """make_thread_loop

        Args:
            loop_height (float): 0.0 < height <= 1.0

        Raises:
            ValueError: Invalid loop height

        Returns:
            Solid: One full or partial helical loop of thread
        """
        if not 0.0 < loop_height <= 1.0:
            raise ValueError(f"Invalid loop_height ({loop_height})")
        with BuildPart() as thread_loop:
            with BuildLine():  # thread path
                thread_path_wire = Helix(
                    pitch=self.pitch,
                    height=loop_height * self.pitch,
                    radius=self.root_radius,
                    lefthand=not self.right_hand,
                )

            for i in range(11):
                u_value = i / 10
                with BuildSketch(
                    Plane(
                        thread_path_wire @ u_value,
                        x_dir=(0, 0, 1),
                        z_dir=thread_path_wire % u_value,
                    )
                ):
                    add(self.thread_profile)
            loft()

        loop = thread_loop.part.solids()[0]
        for i in range(2):
            RigidJoint(str(i), loop, thread_path_wire.location_at(i))
        return loop

    def _make_fade_end(self, bottom: bool) -> Solid:
        """make_fade_end

        Args:
            bottom (bool): bottom or top of the thread

        Returns:
            Solid: The tip of the thread fading to almost nothing
        """
        dir = -1 if bottom else 1
        height = min(self.pitch / 4, self.length / 2)
        with BuildPart() as fade_tip:
            with BuildLine():
                fade_path_wire = Helix(
                    pitch=self.pitch,
                    height=dir * height,
                    radius=self.root_radius,
                    lefthand=not self.right_hand,
                )

            for i in range(11):
                u_value = i / 10
                z_dir = fade_path_wire % u_value
                if bottom:
                    z_dir = z_dir.reverse()
                with BuildSketch(
                    Plane(fade_path_wire @ u_value, x_dir=(0, 0, 1), z_dir=z_dir)
                ):
                    add(self.thread_profile)
                    scale(by=(11 - i) / 11)
            loft()

        tip = fade_tip.part.solids()[0]

        RigidJoint(
            "0",
            tip,
            fade_path_wire.location_at(0) * Location((0, 0, 0), (1, 0, 0), 180),
        )
        RigidJoint("1", tip, fade_path_wire.location_at(0))
        return tip

    def _make_chamfer_shape(self) -> Solid:
        """Create the shape that will intersect with the thread to chamfer ends"""
        inside_radius = min(self.apex_radius, self.root_radius)
        outside_radius = max(self.apex_radius, self.root_radius) + 0.001
        if self.external:
            chamfer_shape = Solid.extrude(
                Face.make_from_wires(Wire.make_circle(outside_radius)),
                (0, 0, self.length),
            )
        else:
            # Decreasing inside_radius fixes the broken/missing first row chamfer
            # 0.01 visually cleans up the threads more than 0.005 or 0.001 on threads up
            # to M100
            inside_radius -= 0.01
            chamfer_shape = Solid.extrude(
                Face.make_from_wires(
                    Wire.make_circle(2 * outside_radius),
                    [Wire.make_circle(inside_radius)],
                ),
                (0, 0, self.length),
            )
        thickness = outside_radius - inside_radius
        for i in range(2):
            if self.end_finishes[i] == "chamfer":
                chamfer_shape = chamfer_shape.chamfer(
                    thickness / 2,
                    thickness / 2,
                    chamfer_shape.edges()
                    .group_by(Axis.Z, reverse=i != 0)[0]
                    .sort_by(
                        SortBy.RADIUS,
                        reverse=self.apex_radius > self.root_radius,
                    )[0:1],
                )
        return chamfer_shape


class IsoThread(BasePartObject):
    # class IsoThread(Solid):
    """ISO Standard Thread

    Both external and internal ISO standard 60° threads as shown in
    the following diagram (from https://en.wikipedia.org/wiki/ISO_metric_screw_thread):

    .. image:: https://upload.wikimedia.org/wikipedia/commons/4/4b/ISO_and_UTS_Thread_Dimensions.svg

    The following is an example of an internal thread with a chamfered end as might
    be found inside a nut:

    .. image:: assets/internal_iso_thread.png

    Args:
        major_diameter (float): Primary thread diameter
        pitch (float): Length of 360° of thread rotation
        length (float): End to end length of the thread
        external (bool, optional): External or internal thread selector. Defaults to True.
        hand (Literal[, optional): Twist direction. Defaults to "right".
        end_finishes (Tuple[ Literal[, optional): Profile of each end, one of:

            "raw"
                unfinished which typically results in the thread
                extended below z=0 or above z=length
            "fade"
                the thread height drops to zero over 90° of arc
                (or 1/4 pitch)
            "square"
                clipped by the z=0 or z=length plane
            "chamfer"
                conical ends which facilitates alignment of a bolt
                into a nut

            Defaults to ("fade", "square").
        interference: Amount the thread will overlap with nut or bolt core. Used
            to help create valid threaded objects where the thread must fuse
            with another object. For threaded objects built as Compounds, this
            value could be set to 0.0. Defaults to 0.2.
        simple: Stop at thread calculation, don't create thread. Defaults to False.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional):
            object alignment. Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.

    Attributes:
        thread_angle (int): 60 degrees
        h_parameter (float): Value of `h` as shown in the thread diagram
        min_radius (float): Inside radius of the thread diagram

    Raises:
        ValueError: if hand not in ["right", "left"]:
        ValueError: end_finishes not in ["raw", "square", "fade", "chamfer"]

    """

    @property
    def h_parameter(self) -> float:
        """Calculate the h parameter"""
        return (self.pitch / 2) / tan(radians(self.thread_angle / 2))

    @property
    def min_radius(self) -> float:
        """The radius of the root of the thread"""
        return (self.major_diameter - 2 * (5 / 8) * self.h_parameter) / 2

    def __init__(
        self,
        major_diameter: float,
        pitch: float,
        length: float,
        external: bool = True,
        hand: Literal["right", "left"] = "right",
        end_finishes: Tuple[
            Literal["raw", "square", "fade", "chamfer"],
            Literal["raw", "square", "fade", "chamfer"],
        ] = ("fade", "square"),
        interference: float = 0.2,
        simple: bool = False,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        self.major_diameter = major_diameter
        self.pitch = pitch
        self.length = length
        self.external = external
        self.thread_angle = 60
        if hand not in ["right", "left"]:
            raise ValueError(f'hand must be one of "right" or "left" not {hand}')
        self.hand = hand
        for finish in end_finishes:
            if finish not in ["raw", "square", "fade", "chamfer"]:
                raise ValueError(
                    'end_finishes invalid, must be tuple() of "raw, square, fade, or chamfer"'
                )
        self.end_finishes = end_finishes
        self.interference = interference
        self.simple = simple
        self.apex_radius = self.major_diameter / 2 if external else self.min_radius
        apex_width = self.pitch / 8 if external else self.pitch / 4
        self.root_radius = self.min_radius if external else self.major_diameter / 2
        root_width = 3 * self.pitch / 4 if external else 7 * self.pitch / 8
        if simple:
            # Initialize with a valid shape then nullify
            super().__init__(part=Solid.make_box(1, 1, 1))
            self.wrapped = TopoDS_Shape()

        else:
            bd_object = Thread(
                apex_radius=self.apex_radius,
                apex_width=apex_width,
                root_radius=self.root_radius,
                root_width=root_width,
                pitch=self.pitch,
                length=self.length,
                end_finishes=self.end_finishes,
                hand=self.hand,
                simple=simple,
            )
            self.thread_profile = bd_object.thread_profile
            super().__init__(
                part=Compound.make_compound(bd_object.solids()),
                rotation=rotation,
                align=tuplify(align, 3),
                mode=mode,
            )


class TrapezoidalThread(BasePartObject):
    """Trapezoidal Thread Base Class

    Trapezoidal thread forms are screw thread profiles with trapezoidal outlines. They are
    the most common forms used for leadscrews (power screws). They offer high strength
    and ease of manufacture. They are typically found where large loads are required, as
    in a vise or the leadscrew of a lathe.

    Trapezoidal Thread is a base class for Metric and Acme derived classes, or can be used
    to create a trapezoidal thread with arbitrary properties.

    Args:
        thread_angle (int): thread angle in degrees
        diameter (float): thread diameter
        pitch (float): thread pitch
        size (str): specified by derived class
        length (float): thread length
        external (bool, optional): external or internal thread selector. Defaults to True.
        hand (Literal[, optional): twist direction. Defaults to "right".
        end_finishes (Tuple[ Literal[, optional): Profile of each end, one of:

            "raw"
                unfinished which typically results in the thread
                extended below z=0 or above z=length
            "fade"
                the thread height drops to zero over 90° of arc
                (or 1/4 pitch)
            "square"
                clipped by the z=0 or z=length plane
            "chamfer"
                conical ends which facilitates alignment of a bolt
                into a nut

            Defaults to ("fade", "fade").
        interference: Amount the thread will overlap with nut or bolt core. Used
            to help create valid threaded objects where the thread must fuse
            with another object. For threaded objects built as Compounds, this
            value could be set to 0.0. Defaults to 0.2.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional):
            object alignment. Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.

    Raises:
        ValueError: hand must be one of "right" or "left"
        ValueError: end_finishes invalid, must be tuple() of "raw, square, taper, or chamfer"

    Attributes:
        thread_angle (int): thread angle in degrees
        diameter (float): thread diameter
        pitch (float): thread pitch

    """

    def __init__(
        self,
        diameter: float,
        pitch: float,
        thread_angle: float,
        length: float,
        external: bool = True,
        hand: Literal["right", "left"] = "right",
        end_finishes: tuple[
            Literal["raw", "square", "fade", "chamfer"],
            Literal["raw", "square", "fade", "chamfer"],
        ] = ("fade", "fade"),
        interference: float = 0.2,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        self.thread_size = diameter
        self.external = external
        self.length = length
        self.diameter = diameter
        self.thread_angle = thread_angle
        self.pitch = pitch
        shoulder_width = (self.pitch / 2) * tan(radians(self.thread_angle / 2))
        apex_width = (self.pitch / 2) - shoulder_width
        root_width = (self.pitch / 2) + shoulder_width
        if self.external:
            self.apex_radius = self.diameter / 2
            self.root_radius = self.diameter / 2 - self.pitch / 2
        else:
            self.apex_radius = self.diameter / 2 - self.pitch / 2
            self.root_radius = self.diameter / 2

        if hand not in ["right", "left"]:
            raise ValueError(f'hand must be one of "right" or "left" not {hand}')
        self.hand = hand
        for finish in end_finishes:
            if not finish in ["raw", "square", "fade", "chamfer"]:
                raise ValueError(
                    'end_finishes invalid, must be tuple() of "raw, square, fade, or chamfer"'
                )
        self.end_finishes = end_finishes
        self.interference = interference
        bd_object = Thread(
            apex_radius=self.apex_radius,
            apex_width=apex_width,
            root_radius=self.root_radius,
            root_width=root_width,
            pitch=self.pitch,
            length=self.length,
            interference=interference,
            end_finishes=self.end_finishes,
            hand=self.hand,
        )
        self.thread_profile = bd_object.thread_profile
        super().__init__(
            part=bd_object,
            rotation=rotation,
            align=tuplify(align, 3),
            mode=mode,
        )


class AcmeThread(TrapezoidalThread):
    """ACME Thread

    The original trapezoidal thread form, and still probably the one most commonly encountered
    worldwide, with a 29° thread angle, is the Acme thread form.

    The following is the acme thread with faded ends:

    .. image:: assets/acme_thread.png

    Args:
        size (str): size as a string (i.e. "3/4" or "1 1/4")
        length (float): thread length
        external (bool, optional): external or internal thread selector. Defaults to True.
        hand (Literal[, optional): twist direction. Defaults to "right".
        end_finishes (Tuple[ Literal[, optional): Profile of each end, one of:

            "raw"
                unfinished which typically results in the thread
                extended below z=0 or above z=length
            "fade"
                the thread height drops to zero over 90° of arc
                (or 1/4 pitch)
            "square"
                clipped by the z=0 or z=length plane
            "chamfer"
                conical ends which facilitates alignment of a bolt
                into a nut

            Defaults to ("fade", "fade").
        interference: Amount the thread will overlap with nut or bolt core. Used
            to help create valid threaded objects where the thread must fuse
            with another object. For threaded objects built as Compounds, this
            value could be set to 0.0. Defaults to 0.2.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional):
            object alignment. Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.

    Raises:
        ValueError: hand must be one of "right" or "left"
        ValueError: end_finishes invalid, must be tuple() of "raw, square, taper, or chamfer"

    Attributes:
        thread_angle (int): thread angle in degrees
        diameter (float): thread diameter
        pitch (float): thread pitch

    """

    acme_pitch = {
        "1/4": (1 / 16) * IN,
        "5/16": (1 / 14) * IN,
        "3/8": (1 / 12) * IN,
        "1/2": (1 / 10) * IN,
        "5/8": (1 / 8) * IN,
        "3/4": (1 / 6) * IN,
        "7/8": (1 / 6) * IN,
        "1": (1 / 5) * IN,
        "1 1/4": (1 / 5) * IN,
        "1 1/2": (1 / 4) * IN,
        "1 3/4": (1 / 4) * IN,
        "2": (1 / 4) * IN,
        "2 1/2": (1 / 3) * IN,
        "3": (1 / 2) * IN,
    }

    thread_angle = 29.0  # in degrees

    @classmethod
    def sizes(cls) -> list[str]:
        """Return a list of the thread sizes"""
        return list(AcmeThread.acme_pitch.keys())

    def __init__(
        self,
        size: str,
        length: float,
        external: bool = True,
        hand: Literal["right", "left"] = "right",
        end_finishes: tuple[
            Literal["raw", "square", "fade", "chamfer"],
            Literal["raw", "square", "fade", "chamfer"],
        ] = ("fade", "fade"),
        interference: float = 0.2,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        diameter = imperial_str_to_float(size)
        pitch = AcmeThread.acme_pitch[size]
        super().__init__(
            diameter,
            pitch,
            self.thread_angle,
            length,
            external,
            hand,
            end_finishes,
            interference,
            rotation,
            align,
            mode,
        )


class MetricTrapezoidalThread(TrapezoidalThread):
    """Metric Trapezoidal Thread

    The ISO 2904 standard metric trapezoidal thread with a thread angle of 30°

    Args:
        size (str): specified as a sting with diameter x pitch in mm (i.e. "8x1.5")
        length (float): End to end length of the thread
        external (bool, optional): external or internal thread selector. Defaults to True.
        hand (Literal[, optional): twist direction. Defaults to "right".
        end_finishes (Tuple[ Literal[, optional): Profile of each end, one of:

            "raw"
                unfinished which typically results in the thread
                extended below z=0 or above z=length
            "fade"
                the thread height drops to zero over 90° of arc
                (or 1/4 pitch)
            "square"
                clipped by the z=0 or z=length plane
            "chamfer"
                conical ends which facilitates alignment of a bolt
                into a nut

            Defaults to ("fade", "fade").
        interference: Amount the thread will overlap with nut or bolt core. Used
            to help create valid threaded objects where the thread must fuse
            with another object. For threaded objects built as Compounds, this
            value could be set to 0.0. Defaults to 0.2.
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[None, Align, tuple[Align, Align, Align]], optional):
            object alignment. Defaults to None.
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.

    Raises:
        ValueError: hand must be one of "right" or "left"
        ValueError: end_finishes invalid, must be tuple() of "raw, square, taper, or chamfer"

    Attributes:
        thread_angle (int): thread angle in degrees
        diameter (float): thread diameter
        pitch (float): thread pitch
    """

    # Turn off black auto-format for this array as it will be spread over hundreds of lines
    # fmt: off
    standard_sizes = [
		"8x1.5","9x1.5","9x2","10x1.5","10x2","11x2","11x3","12x2","12x3","14x2",
		"14x3","16x2","16x3","16x4","18x2","18x3","18x4","20x2","20x3","20x4",
		"22x3","22x5","22x8","24x3","24x5","24x8","26x3","26x5","26x8","28x3",
		"28x5","28x8","30x3","30x6","30x10","32x3","32x6","32x10","34x3","34x6",
		"34x10","36x3","36x6","36x10","38x3","38x7","38x10","40x3","40x7","40x10",
		"42x3","42x7","42x10","44x3","44x7","44x12","46x3","46x8","46x12","48x3",
		"48x8","48x12","50x3","50x8","50x12","52x3","52x8","52x12","55x3","55x9",
		"55x14","60x3","60x9","60x14","65x4","65x10","65x16","70x4","70x10","70x16",
		"75x4","75x10","75x16","80x4","80x10","80x16","85x4","85x12","85x18","90x4",
		"90x12","90x18","95x4","95x12","95x18","100x4","100x12","100x20","105x4",
		"105x12","105x20","110x4","110x12","110x20","115x6","115x12","115x14",
		"115x22","120x6","120x12","120x14","120x22","125x6","125x12","125x14",
		"125x22","130x6","130x12","130x14","130x22","135x6","135x12","135x14",
		"135x24","140x6","140x12","140x14","140x24","145x6","145x12","145x14",
		"145x24","150x6","150x12","150x16","150x24","155x6","155x12","155x16",
		"155x24","160x6","160x12","160x16","160x28","165x6","165x12","165x16",
		"165x28","170x6","170x12","170x16","170x28","175x8","175x12","175x16",
		"175x28","180x8","180x12","180x18","180x28","185x8","185x12","185x18",
		"185x24","185x32","190x8","190x12","190x18","190x24","190x32","195x8",
		"195x12","195x18","195x24","195x32","200x8","200x12","200x18","200x24",
		"200x32","205x4","210x4","210x8","210x12","210x20","210x24","210x36","215x4",
		"220x4","220x8","220x12","220x20","220x24","220x36","230x4","230x8","230x12",
		"230x20","230x24","230x36","235x4","240x4","240x8","240x12","240x20",
		"240x22","240x24","240x36","250x4","250x12","250x22","250x24","250x40",
		"260x4","260x12","260x20","260x22","260x24","260x40","270x12","270x24",
		"270x40","275x4","280x4","280x12","280x24","280x40","290x4","290x12",
		"290x24","290x44","295x4","300x4","300x12","300x24","300x44","310x5","315x5"
    ]
    # fmt: on

    thread_angle = 30.0  # in degrees

    @classmethod
    def sizes(cls) -> list[str]:
        """Return a list of the thread sizes"""
        return MetricTrapezoidalThread.standard_sizes

    def __init__(
        self,
        size: str,
        length: float,
        external: bool = True,
        hand: Literal["right", "left"] = "right",
        end_finishes: tuple[
            Literal["raw", "square", "fade", "chamfer"],
            Literal["raw", "square", "fade", "chamfer"],
        ] = ("fade", "fade"),
        interference: float = 0.2,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        if not size in MetricTrapezoidalThread.standard_sizes:
            raise ValueError(
                f"size invalid, must be one of {MetricTrapezoidalThread.standard_sizes}"
            )
        (diameter, pitch) = (float(part) for part in size.split("x"))
        super().__init__(
            diameter,
            pitch,
            self.thread_angle,
            length,
            external,
            hand,
            end_finishes,
            interference,
            rotation,
            align,
            mode,
        )


class PlasticBottleThread(BasePartObject):
    """ASTM D2911 Plastic Bottle Thread

    The `ASTM D2911 Standard <https://www.astm.org/d2911-10.html>`_ Plastic Bottle Thread.

    L Style:
        All-Purpose Thread - trapezoidal shape with 30° shoulders, metal or platsic closures
    M Style:
        Modified Buttress Thread - asymmetric shape with 10° and 40/45/50°
        shoulders, plastic closures

    .. image:: assets/plastic_thread.png

    Args:
        size (str): as defined by the ASTM is specified as
            [L|M][diameter(mm)]SP[100|103|110|200|400|410|415|425|444]
        external (bool, optional): external or internal thread selector. Defaults to True.
        hand (Literal[, optional): twist direction. Defaults to "right".
        interference: Amount the thread will overlap with nut or bolt core. Used
            to help create valid threaded objects where the thread must fuse
            with another object. For threaded objects built as Compounds, this
            value could be set to 0.0. Defaults to 0.2.
        manufacturing_compensation (float, optional): used to compensate for over-extrusion of 3D
            printers. A value of 0.2mm will reduce the radius of an external thread by 0.2mm (and
            increase the radius of an internal thread) such that the resulting 3D printed part
            matches the target dimensions. Defaults to 0.0.
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,

    Raises:
        ValueError: hand must be one of "right" or "left"
        ValueError: size invalid, must match
            [L|M][diameter(mm)]SP[100|103|110|200|400|410|415:425|444]
        ValueError: finish invalid
        ValueError: diameter invalid

    Example:
        .. code-block:: python

            thread = PlasticBottleThread(
                size="M38SP444", external=False, manufacturing_compensation=0.2 * MM
            )

    """

    # {TPI: [root_width,thread_height]}
    _l_style_thread_dimensions = {
        4: [3.18, 1.57],
        5: [3.05, 1.52],
        6: [2.39, 1.19],
        8: [2.13, 1.07],
        12: [1.14, 0.76],
    }
    _m_style_thread_dimensions = {
        4: [3.18, 1.57],
        5: [3.05, 1.52],
        6: [2.39, 1.19],
        8: [2.13, 1.07],
        12: [1.29, 0.76],
    }

    _thread_angles = {
        "L100": [30, 30],
        "M100": [10, 40],
        "L103": [30, 30],
        "M103": [10, 40],
        "L110": [30, 30],
        "M110": [10, 50],
        "L200": [30, 30],
        "M200": [10, 40],
        "L400": [30, 30],
        "M400": [10, 45],
        "L410": [30, 30],
        "M410": [10, 45],
        "L415": [30, 30],
        "M415": [10, 45],
        "L425": [30, 30],
        "M425": [10, 45],
        "L444": [30, 30],
        "M444": [10, 45],
    }

    # {finish:[min turns,[diameters,...]]}
    # fmt: off
    _finish_data = {
        100: [1.125,[22,24,28,30,33,35,38]],
        103: [1.125,[26]],
        110: [1.125,[28]],
        200: [1.5,[24.28]],
        400: [1.0,[18,20,22,24,28,30,33,35,38,40,43,45,48,51,53,58,60,63,66,70,75,77,83,89,100,110,120]],
        410: [1.5,[18,20,22,24,28]],
        415: [2.0,[13,15,18,20,22,24,28,30,33]],
        425: [2.0,[13,15]],
        444: [1.125,[24,28,30,33,35,38,40,43,45,48,51,53,58,60,63,66,70,75,77,83]]
    }
    # fmt: on

    # {thread_size:[max,min,TPI]}
    _thread_dimensions = {
        13: [13.06, 12.75, 12],
        15: [14.76, 14.45, 12],
        18: [17.88, 17.47, 8],
        20: [19.89, 19.48, 8],
        22: [21.89, 21.49, 8],
        24: [23.88, 23.47, 8],
        26: [25.63, 25.12, 8],
        28: [27.64, 27.13, 6],
        30: [28.62, 28.12, 6],
        33: [32.13, 31.52, 6],
        35: [34.64, 34.04, 6],
        38: [37.49, 36.88, 6],
        40: [40.13, 39.37, 6],
        43: [42.01, 41.25, 6],
        45: [44.20, 43.43, 6],
        48: [47.50, 46.74, 6],
        51: [49.99, 49.10, 6],
        53: [52.50, 51.61, 6],
        58: [56.49, 55.60, 6],
        60: [59.49, 58.60, 6],
        63: [62.51, 61.62, 6],
        66: [65.51, 64.62, 6],
        70: [69.49, 68.60, 6],
        75: [73.99, 73.10, 6],
        77: [77.09, 76.20, 6],
        83: [83.01, 82.12, 5],
        89: [89.18, 88.29, 5],
        100: [100.00, 99.11, 5],
        110: [110.01, 109.12, 5],
        120: [119.99, 119.10, 5],
    }

    def __init__(
        self,
        size: str,
        external: bool = True,
        hand: Literal["right", "left"] = "right",
        interference: float = 0.2,
        manufacturing_compensation: float = 0.0,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        self.thread_size = size
        self.external = external
        if hand not in ["right", "left"]:
            raise ValueError(f'hand must be one of "right" or "left" not {hand}')
        self.hand = hand
        self.interference = interference
        size_match = re.match(r"([LM])(\d+)SP(\d+)", size)
        if not size_match:
            raise ValueError(
                "size invalid, must match \
                    [L|M][diameter(mm)]SP[100|103|110|200|400|410|415:425|444]"
            )
        self.style = size_match.group(1)
        self.diameter = int(size_match.group(2))
        self.finish = int(size_match.group(3))
        if self.finish not in PlasticBottleThread._finish_data:
            raise ValueError(
                f"finish ({self.finish}) invalid, must be one of"
                f" {list(PlasticBottleThread._finish_data.keys())}"
            )
        if not self.diameter in PlasticBottleThread._finish_data[self.finish][1]:
            raise ValueError(
                f"diameter ({self.diameter}) invalid, must be one"
                f" of {PlasticBottleThread._finish_data[self.finish][1]}"
            )
        (diameter_max, diameter_min, self.tpi) = PlasticBottleThread._thread_dimensions[
            self.diameter
        ]
        if self.style == "L":
            (
                self.root_width,
                thread_height,
            ) = PlasticBottleThread._l_style_thread_dimensions[self.tpi]
        else:
            (
                self.root_width,
                thread_height,
            ) = PlasticBottleThread._m_style_thread_dimensions[self.tpi]
        if self.external:
            self.apex_radius = diameter_min / 2 - manufacturing_compensation
            self.root_radius = (
                diameter_min / 2 - thread_height - manufacturing_compensation
            )
        else:
            self.root_radius = diameter_max / 2 + manufacturing_compensation
            self.apex_radius = (
                diameter_max / 2 - thread_height + manufacturing_compensation
            )
        self._thread_angles = PlasticBottleThread._thread_angles[
            self.style + str(self.finish)
        ]
        shoulders = [thread_height * tan(radians(a)) for a in self._thread_angles]
        self.apex_width = self.root_width - sum(shoulders)
        self.apex_offset = shoulders[0] + self.apex_width / 2 - self.root_width / 2
        if not self.external:
            self.apex_offset = -self.apex_offset
        self.pitch = 25.4 * MM / self.tpi
        self.length = (
            PlasticBottleThread._finish_data[self.finish][0] + 0.75
        ) * self.pitch
        bd_object = Thread(
            apex_radius=self.apex_radius,
            apex_width=self.apex_width,
            root_radius=self.root_radius,
            root_width=self.root_width,
            pitch=self.pitch,
            length=self.length,
            apex_offset=self.apex_offset,
            interference=interference,
            hand=self.hand,
            end_finishes=("fade", "fade"),
        )
        self.thread_profile = bd_object.thread_profile

        super().__init__(
            part=bd_object,
            rotation=rotation,
            align=tuplify(align, 3),
            mode=mode,
        )
