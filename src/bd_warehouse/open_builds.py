"""

OpenBuilds Parts

name: open_builds.py
by:   Gumyr
date: June 27th 2024

desc: This python/build123d code is a parameterized set of models of parts from
      https://openbuildspartstore.com/.

license:

    Copyright 2024 Gumyr

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

from build123d import *
from build123d import tuplify
from typing import Union, Literal

CAVITY_RADIUS = 2.3 * MM
FILLET_RADIUS = 1.5 * MM


class _VSlotGroove(BaseSketchObject):
    """Sketch Object: OpenBuilds V Slot Linear Rail Groove

    Args:
        rotation (float, optional): angles to rotate objects. Defaults to 0.
        align (Union[Align, tuple[Align, Align]], optional): align min, center, or
            max of object. Defaults to (Align.CENTER, Align.CENTER).
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    _applies_to = [BuildSketch._tag]

    def __init__(
        self,
        rotation: float = 0,
        mode: Mode = Mode.ADD,
    ):
        with BuildSketch() as groove:
            with BuildLine():
                Polyline(
                    (3.69, 0),
                    (3.9, 0.21),
                    (3.9, 2.8393398282202034),
                    (6.560660171779773, 5.5),
                    (8.2, 5.5),
                    (8.2, 3.125),
                    (8.545, 3.125),
                    (10, 4.58),
                    (10, 0),
                )
                mirror(about=Plane.XZ)
            make_face()

        super().__init__(obj=groove.sketch, rotation=rotation, align=None, mode=mode)


class _VSlotInternalCavity(BaseSketchObject):
    """Sketch Object: OpenBuilds V Slot Linear Rail Internal Cavity

    Args:
        rotation (float, optional): angles to rotate objects. Defaults to 0.
        align (Union[Align, tuple[Align, Align]], optional): align min, center, or
            max of object. Defaults to (Align.CENTER, Align.CENTER).
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    _applies_to = [BuildSketch._tag]

    def __init__(
        self,
        rotation: float = 0,
        mode: Mode = Mode.ADD,
    ):
        with BuildSketch() as cavity:
            with BuildLine():
                Polyline(
                    (-8.2, 0),
                    (-8.2, -2.7),
                    (-6.23933983, -2.7),
                    (-2.83933983, -6.1),
                    (0, -6.1),
                )
                mirror(about=Plane.XZ)
                mirror(about=Plane.YZ)
            make_face()

        super().__init__(obj=cavity.sketch, rotation=rotation, align=None, mode=mode)


class VSlotLinearRailProfile(BaseSketchObject):
    """Sketch Object: OpenBuilds V Slot Linear Rail Profile

    Args:
        rotation (float, optional): angles to rotate objects. Defaults to 0.
        align (Union[Align, tuple[Align, Align]], optional): align min, center, or
            max of object. Defaults to (Align.CENTER, Align.CENTER).
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    _applies_to = [BuildSketch._tag]

    def __init__(
        self,
        rail_size: Literal["20x20", "20x40", "20x60", "20x80", "40x40"] = "20x20",
        rotation: float = 0,
        align: tuple[Align, Align] = (Align.CENTER, Align.CENTER),
        mode: Mode = Mode.ADD,
    ):
        grooves: dict[str, list[tuple[tuple[int, int], list[int]]]] = {
            "20x20": ([(0, 0), (0, 0), (0, 0), (0, 0)], [0, 90, 180, 270]),
            "20x40": (
                [(0, 10), (0, 10), (0, 10), (0, -10), (0, -10), (0, -10)],
                [0, 90, 180, 180, 270, 0],
            ),
            "20x60": (
                [
                    (0, 0),
                    (0, 20),
                    (0, 20),
                    (0, 20),
                    (0, 0),
                    (0, -20),
                    (0, -20),
                    (0, -20),
                ],
                [0, 0, 90, 180, 180, 180, 270, 0],
            ),
            "20x80": (
                [
                    (0, 10),
                    (0, 30),
                    (0, 30),
                    (0, 30),
                    (0, 10),
                    (0, -10),
                    (0, -30),
                    (0, -30),
                    (0, -30),
                    (0, -10),
                ],
                [0, 0, 90, 180, 180, 180, 180, 270, 0, 0],
            ),
            "40x40": (
                [
                    (10, 10),
                    (10, 10),
                    (-10, 10),
                    (-10, 10),
                    (-10, -10),
                    (-10, -10),
                    (10, -10),
                    (10, -10),
                ],
                [0, 90, 90, 180, 180, 270, 270, 0],
            ),
        }
        with BuildSketch() as cavity_40x40:
            with BuildLine():
                l = Polyline(
                    (18.2, 2.7),
                    (16.239339828219503, 2.7),
                    (12.839339828219602, 6.1),
                    (7.1606601717797975, 6.1),
                    (6.1, 7.160660171780418),
                    (6.1, 12.839339828220236),
                    (2.7, 16.23933982822021),
                    (2.7, 18.2),
                    (-2.7, 18.2),
                )
                add(l.rotate(Axis.Z, 90))
                add(l.rotate(Axis.Z, 180))
                add(l.rotate(Axis.Z, 270))
            make_face()

        if rail_size in ["20x20", "20x40", "20x60", "20x80", "40x40"]:
            size = [int(v) for v in rail_size.split("x")]
        else:
            raise ValueError(
                f"The rail_size of {rail_size} isn't valid"
                f" - must be one of 20x20, 20x40, 20x60, 20x80, or 40x40"
            )
        with BuildSketch() as vslot:
            RectangleRounded(*size, FILLET_RADIUS)
            with GridLocations(20, 20, size[0] // 20, size[1] // 20):
                Circle(CAVITY_RADIUS, mode=Mode.SUBTRACT)
            for pos, angle in zip(*grooves[rail_size]):
                with Locations(pos):
                    _VSlotGroove(angle, mode=Mode.SUBTRACT)
            if rail_size in ["20x40", "20x60", "20x80"]:
                with GridLocations(0, 20, 1, size[1] // 20 - 1):
                    _VSlotInternalCavity(mode=Mode.SUBTRACT)
            elif rail_size == "40x40":
                add(cavity_40x40, mode=Mode.SUBTRACT)
        super().__init__(obj=vslot.sketch, rotation=rotation, align=align, mode=mode)


class CBeamLinearRailProfile(BaseSketchObject):
    """Sketch Object: OpenBuilds C Beam Linear Rail Profile

    Args:
        rotation (float, optional): angles to rotate objects. Defaults to 0.
        align (Union[Align, tuple[Align, Align]], optional): align min, center, or max
            of object. Defaults to (Align.CENTER, Align.CENTER).
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.
    """

    _applies_to = [BuildSketch._tag]

    def __init__(
        self,
        rotation: float = 0,
        align: tuple[Align, Align] = (Align.CENTER, Align.CENTER),
        mode: Mode = Mode.ADD,
    ):
        with BuildSketch():
            with BuildLine():
                Polyline(
                    (-2.7, 38.2),
                    (-2.7, 36.239339828220196),
                    (-6.1, 32.839339828220226),
                    (-6.1, 27.160660171779885),
                    (-0.7393398282202048, 21.8),
                    (2.7, 21.8),
                    (2.7, 23.76066017177987),
                    (6.1, 27.160660171779845),
                    (6.1, 32.83933982822018),
                    (2.7, 36.239339828220174),
                    (2.7, 38.2),
                    close=True,
                )
            cavity = make_face()

        with BuildSketch() as cbeam:
            with Locations((0, -30), (0, 30)):
                Rectangle(40, 20)
            with Locations((-10, 0)):
                Rectangle(20, 80)
            v = cbeam.vertices().filter_by(lambda v: v.X == 0, reverse=True)
            fillet(v, FILLET_RADIUS)
            with Locations(
                (10, 30), (-10, 30), (-10, 10), (-10, -10), (-10, -30), (10, -30)
            ):
                Circle(CAVITY_RADIUS, mode=Mode.SUBTRACT)
            with Locations((10, -30), (10, 30)):
                _VSlotGroove(mode=Mode.SUBTRACT)
                _VSlotGroove(90, mode=Mode.SUBTRACT)
                _VSlotGroove(-90, mode=Mode.SUBTRACT)
            with Locations((-10, -30)):
                _VSlotGroove(-90, mode=Mode.SUBTRACT)
            with Locations((-10, 30)):
                _VSlotGroove(90, mode=Mode.SUBTRACT)
            with Locations((-10, 0)):
                with GridLocations(0, 20, 1, 4):
                    _VSlotGroove(180, mode=Mode.SUBTRACT)
                with GridLocations(0, 20, 1, 2):
                    _VSlotGroove(mode=Mode.SUBTRACT)
            add(cavity, mode=Mode.SUBTRACT)
            add(cavity.mirror(Plane.XZ), mode=Mode.SUBTRACT)
            add(cavity.mirror(Plane((20, 0, 0), z_dir=(1, 1, 0))), mode=Mode.SUBTRACT)
            add(cavity.mirror(Plane((20, 0, 0), z_dir=(1, -1, 0))), mode=Mode.SUBTRACT)
            add(
                cavity.mirror(Plane.XZ).mirror(Plane((20, 0, 0), z_dir=(1, -1, 0))),
                mode=Mode.SUBTRACT,
            )
            with Locations((-10, 0)):
                _VSlotInternalCavity(mode=Mode.SUBTRACT)

        super().__init__(obj=cbeam.sketch, rotation=rotation, align=align, mode=mode)


class VSlotLinearRail(BasePartObject):
    """Part Object: OpenBuilds V Slot Linear Rail

    Args:
        rail_size (Literal["20x20", "20x40", "20x60", "20x80", "40x40"]): size in mm
        length (float): rail length
        rotation (RotationLike, optional): angles to rotate about axes. Defaults to (0, 0, 0).
        align (Union[Align, tuple[Align, Align, Align]], optional): align min, center,
            or max of object. Defaults to (Align.CENTER, Align.CENTER, Align.MIN).
        mode (Mode, optional): combine mode. Defaults to Mode.ADD.

    Raises:
            ValueError: Invalid rail_size
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        rail_size: Literal["20x20", "20x40", "20x60", "20x80", "40x40"],
        length: float,
        rotation: RotationLike = (0, 0, 0),
        align: Union[Align, tuple[Align, Align, Align]] = (
            Align.CENTER,
            Align.CENTER,
            Align.MIN,
        ),
        mode: Mode = Mode.ADD,
    ):
        if rail_size not in ["20x20", "20x40", "20x60", "20x80", "40x40"]:
            raise ValueError(
                f"The rail_size of {rail_size} isn't valid"
                f" - must be one of 20x20, 20x40, 20x60, 20x80, or 40x40"
            )
        rail = extrude(VSlotLinearRailProfile(rail_size), amount=length, dir=(0, 0, 1))
        super().__init__(
            part=rail, rotation=rotation, align=tuplify(align, 3), mode=mode
        )
        self.color = Color(0xC0C0C0)
        # RigidJoint("test1", self, Location((10, 0, 0), (0, 90, 0)))
        # RigidJoint("test2", self, Location((0, -10, 50), (90, 0, 0)))


class CBeamLinearRail(BasePartObject):
    """Part Object: OpenBuilds C-Beam Linear Rail

    Args:
        length (float): rail length
        rotation (RotationLike, optional): angles to rotate about axes. Defaults to (0, 0, 0).
        align (Union[Align, tuple[Align, Align, Align]], optional): align min, center,
            or max of object. Defaults to (Align.CENTER, Align.CENTER, Align.MIN).
        mode (Mode, optional): combine mode. Defaults to Mode.ADD.
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        length: float,
        rotation: RotationLike = (0, 0, 0),
        align: Union[Align, tuple[Align, Align, Align]] = (
            Align.CENTER,
            Align.CENTER,
            Align.MIN,
        ),
        mode: Mode = Mode.ADD,
    ):
        rail = extrude(CBeamLinearRailProfile(), amount=length, dir=(0, 0, 1))
        super().__init__(
            part=rail, rotation=rotation, align=tuplify(align, 3), mode=mode
        )
        self.color = Color(0xC0C0C0)
        # RigidJoint("test1", self, Location((10, 0, 0), (0, 90, 0)))
        # RigidJoint("test2", self, Location((0, -10, 50), (90, 0, 0)))


class CBeamGantryPlateXLarge(BasePartObject):
    """Part Object: OpenBuilds C-Beam Gantry Plate X-Large

    Achieve unparalleled stability in your builds with the XLarge C-Beam Gantry Plate,
    designed to accommodate up to six wheels for an extremely stable gantry. This versatile
    plate is essential for both Belt and Pinion and Lead Screw transmissions. With recessed
    holes for professional flush mounts and tapped holes for a 90° connection, this plate is
    ideal for XY configurations, offering multiple mounting options to suit your project needs.

    Features:
        - Wide stance for enhanced stability
        - Countersunk holes for a flush finish
        - Tapped holes for easy 90° connections
        - Center recess for additional mounting options
        - Supports multiple mounting configurations

    Specifications:
        - Size: 125 x 125mm
        - Thickness: 6mm
        - Material: 6061 – T5 Aluminum
        - Finish: Brushed and anodized
        - Color: Black

    Args:
        rotation (RotationLike, optional): angles to rotate about axes. Defaults to (0, 0, 0).
        align (Union[Align, tuple[Align, Align, Align]], optional): align min, center,
            or max of object. Defaults to (Align.CENTER, Align.CENTER, Align.MIN).
        mode (Mode, optional): combine mode. Defaults to Mode.ADD.
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        with BuildPart() as plate:
            with BuildSketch(Plane.XY) as plate_skt:
                RectangleRounded(125, 125, 10)
                with GridLocations(30, 30, 3, 3):
                    Circle(2.6, mode=Mode.SUBTRACT)
                with GridLocations(20, 80.6, 2, 2):
                    Circle(2.6, mode=Mode.SUBTRACT)
                with GridLocations(65, 80.6, 2, 2):
                    Circle(2.6, mode=Mode.SUBTRACT)
                with GridLocations(60, 20, 2, 2):
                    Circle(2.6, mode=Mode.SUBTRACT)
                with GridLocations(60, 100.6, 2, 2):
                    Circle(2.6, mode=Mode.SUBTRACT)
                with GridLocations(20, 20, 2, 2):
                    Circle(2.6, mode=Mode.SUBTRACT)
            extrude(amount=6)

            # Recess
            with BuildSketch(Plane.XY.offset(6)):
                RectangleRounded(35, 35, 2.8)
            extrude(amount=-1.6, mode=Mode.SUBTRACT)

            # Slots
            with BuildSketch(Plane.XY.offset(6)):
                with GridLocations(102.6, 20, 2, 2):
                    SlotOverall(11.135, 4.568 * 2)
            extrude(amount=-1.6, mode=Mode.SUBTRACT)
            with BuildSketch(Plane.XY):
                with GridLocations(102.6, 20, 2, 2):
                    SlotOverall(7.1, 2.55 * 2)
            extrude(amount=6, mode=Mode.SUBTRACT)

            # CounterSink - tapped holes (thread not modelled)
            with Locations((0, 0, 6)):
                with GridLocations(100.6, 60, 2, 2):
                    CounterSinkHole(2.1, 2.7, counter_sink_angle=90)

            # CounterBore
            with Locations((0, -50.3, 6)):
                with GridLocations(50.3, 0, 3, 1):
                    CounterBoreHole(3.6, 6.125, 1.6, 6)
            with Locations((0, 50.3, 6)):
                with GridLocations(50.3, 0, 3, 1):
                    CounterBoreHole(2.55, 4.5675, 1.6, 6)

        super().__init__(plate.part, rotation=rotation, align=align, mode=mode)
        self.color = Color(0x020202)


class XtremeSolidVWHeel(BasePartObject):
    """Part Object: OpenBuilds Xtreme Solid V Wheel

    A heavy-duty alternative to Delrin Wheels. Suitable during applications where substantial
    force and weight are introduced into the system.  Perfect when additional accuracy is
    needed and less compression than in the Delrin is desired. Flat profile designed to work
    effortlessly with a belt on a belt and pinion system as well as lead screw and belt driven
    systems.

    Product Features:
        - Heavy Duty
        - Long lasting solid construction
        - Ultra smooth finish for precise motion
        - Flat wheel surface for belt travel (belt & pinion option)
        - Self-Centering and Self- Lubricating
        - Even distribution of weight
        - Easily assembled and maintained

    Args:
        length (float): rail length
        rotation (RotationLike, optional): angles to rotate about axes. Defaults to (0, 0, 0).
        align (Union[Align, tuple[Align, Align, Align]], optional): align min, center,
            or max of object. Defaults to Align.CENTER.
        mode (Mode, optional): combine mode. Defaults to Mode.ADD.
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = Align.CENTER,
        mode: Mode = Mode.ADD,
    ):
        with BuildPart() as wheel:
            with BuildSketch() as x_section:
                with Locations((0, 8)):
                    Rectangle(10.2, 3.95, align=(Align.CENTER, Align.MIN))
                    Rectangle(1, 2)
                chamfer(x_section.vertices().group_by(Axis.Y)[-1], 2.15)
            revolve(axis=Axis.X)

        super().__init__(
            part=wheel.part, rotation=rotation, align=tuplify(align, 3), mode=mode
        )
        self.color = Color(0xE0E0E0)


if __name__ == "__main__":
    from ocp_vscode import show, set_defaults, Camera

    set_defaults(reset_camera=Camera.CENTER)

    show(
        pack(
            [
                CBeamLinearRail(25),
                VSlotLinearRail("20x20", 25),
                VSlotLinearRail("20x40", 25),
                VSlotLinearRail("20x60", 25),
                VSlotLinearRail("20x80", 25),
                VSlotLinearRail("40x40", 25),
                CBeamGantryPlateXLarge(),
                XtremeSolidVWHeel(),
            ],
            20,
        )
    )
