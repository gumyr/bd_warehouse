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

import copy
import math
from build123d import *
from build123d import tuplify
from typing import Union, Literal
from bd_warehouse.fastener import SocketHeadCapScrew, ThreadedHole, HexNut
from bd_warehouse.bearing import SingleRowCappedDeepGrooveBallBearing

CAVITY_RADIUS = 2.3 * MM
FILLET_RADIUS = 1.5 * MM

m5 = SocketHeadCapScrew("M5-0.8", 20 * MM)  # Used to create threaded holes


class AcmeAntiBacklashNutBlock8mm(BasePartObject):
    """Part Object: OpenBuilds 8mm Acme Anti Backlash Nut Block

    This Anti-Backlash Nut Block for 8mm Lead Screw is a great choice for many build
    projects requiring lead screw linear motion where high precision and repeatability
    with zero play or slop is needed.

    Product Features:
        - Screw and nut for secure and precise backlash adjustment
        - Recesses screw holes for non obtrusive placement
        - Can be mounted on plates or V-Slot
        - Works best with OpenBuilds Lead Screw

    Specifications:
        - Tr8*8(p2) Metric Acme Tap (compatible with our customized 8mm Metric Acme Lead
          Screws)
        - Mounting Hole Spacing: 20mm
        - Pitch: 2mm
        - Lead: 8mm
        - Delrin
        - Color: Black
        - These Anti-Backlash Nut Blocks have been customized to work directly with the
          OpenBuilds system.

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

        with BuildPart() as block:
            with BuildSketch(Plane.XY.offset(-6)) as bs:
                RectangleRounded(34, 33, 3)
                with Locations((-9, 6)):
                    Circle(2.5, mode=Mode.SUBTRACT)
                    Rectangle(
                        26, 5, align=(Align.MIN, Align.CENTER), mode=Mode.SUBTRACT
                    )
                with Locations((10, -6.5), (-10, -6.5)):
                    Circle(2.55, mode=Mode.SUBTRACT)
            extrude(amount=12)
            with BuildSketch(Plane.XY.offset(6)) as bs:
                with Locations((10, -6.5), (-10, -6.5)) as mounts:
                    Circle(4.5)
            extrude(amount=-2, mode=Mode.SUBTRACT)
            with BuildSketch(Plane.XY.offset(-6)) as bs:
                with Locations((10, -6.5), (-10, -6.5)):
                    RegularPolygon(4.618802153517, 6, rotation=30)
            extrude(amount=5, mode=Mode.SUBTRACT)
            with Locations(Plane.XZ):
                Hole(4)
            with Locations(-Plane.XZ.offset(-17)):
                with Locations((10, 0)) as screw_hole:
                    ThreadedHole(m5, depth=10, counter_sunk=False)

        super().__init__(block.part, rotation=rotation, align=align, mode=mode)
        self.color = Color(0x030303)
        self.label = "AcmeAntiBacklashNutBlock8mm"
        for label, loc in zip(["a", "b"], mounts):
            RigidJoint(label, self, Pos(*(loc.position + Vector(0, 0, 6))))
        for label, loc in zip(["nut_a", "nut_b"], mounts):
            RigidJoint(label, self, loc * Location((0, 0, -6), (0, 0, 1), 30))
        RigidJoint("screw", self, screw_hole.locations[0])


class AcmeAntiBacklashNutBlock8mmAssembly(Compound):
    """Assembly: OpenBuilds 8mm Acme Anti Backlash Nut Block Assembly

    All of the components in anti backlash nut assembly:
        - AcmeAntiBacklashNutBlock8mm x 1
        - AluminumSpacer x 2
        - M5 HexNut x 2
        - SocketHeadCapScrew x 1

    The RigidJoint "a" or "b" - positioned at the top of the spaces - can be used to
    connect this assembly to a gantry plate.

    """

    def __init__(self):

        super().__init__()
        screw = SocketHeadCapScrew("M5-0.8", 13 * MM)
        nut0 = HexNut("M5-0.8")
        nut1 = copy.copy(nut0)
        acme_nut = Rot(Z=-90) * AcmeAntiBacklashNutBlock8mm()
        s0 = AluminumSpacer("6mm")
        s1 = copy.copy(s0)
        acme_nut.joints["a"].connect_to(s0.joints["a"])
        acme_nut.joints["b"].connect_to(s1.joints["a"])
        acme_nut.joints["nut_a"].connect_to(nut0.joints["a"])
        acme_nut.joints["nut_b"].connect_to(nut1.joints["a"])
        acme_nut.joints["screw"].connect_to(screw.joints["a"])

        self.children = [acme_nut, s0, s1, nut0, nut1, screw]
        self.label = "AcmeAntiBacklashNutBlock8mmAssembly"
        RigidJoint("a", self, s0.joints["b"].location * Rot(Z=90))
        RigidJoint("b", self, s1.joints["b"].location * Rot(Z=90))


class AluminumSpacer(BasePartObject):
    """Part Object: OpenBuilds AluminumSpacer

    Aluminum spacers used throughout our system to ensure precision alignment and spacing
    between components.

    Product Features:
        - Rigid to maintain stability during motion
        - Lightweight, non-magnetic and corrosion resistance

    Specifications:
        - M5 ID
        - Various Lengths
        - 10mm OD
        - Aluminum
        - Color: Silver

    Args:
        length (Literal['3mm', '1/8in', '6mm', '1/4in', '9mm', '10mm', '13.2mm', '20mm', '35mm', '1-1/2in', '40mm']):
            valid lengths
        rotation (RotationLike, optional): angles to rotate about axes. Defaults to (0, 0, 0).
        align (Union[Align, tuple[Align, Align, Align]], optional): align min, center,
            or max of object. Defaults to (Align.CENTER, Align.CENTER, Align.MIN).
        mode (Mode, optional): combine mode. Defaults to Mode.ADD.

    Raises:
        ValueError: Invalid shim_type
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        length: Literal[
            "3mm",
            "1/8in",
            "6mm",
            "1/4in",
            "9mm",
            "10mm",
            "13.2mm",
            "20mm",
            "35mm",
            "1-1/2in",
            "40mm",
        ],
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):

        valid_lengths = {
            "3mm": 3 * MM,
            "1/8in": IN / 8,
            "6mm": 6 * MM,
            "1/4in": IN / 4,
            "9mm": 9 * MM,
            "10mm": 10 * MM,
            "13.2mm": 13.2 * MM,
            "20mm": 20 * MM,
            "35mm": 35 * MM,
            "1-1/2in": 1.5 * IN,
            "40mm": 40 * MM,
        }
        try:
            spacer_length = valid_lengths[length]
        except KeyError:
            raise ValueError(
                f"{length} is an invalid length, must be one of {tuple(valid_lengths.keys())}"
            )

        with BuildPart() as spacer:
            with BuildSketch():
                Circle(5)
                Circle(2.6, mode=Mode.SUBTRACT)
            extrude(amount=spacer_length)

        super().__init__(spacer.part, rotation=rotation, align=align, mode=mode)
        self.color = Color(0xC0C0C0)
        self.label = f"AluminumSpacer-{length}"
        RigidJoint("a", self, Location())
        RigidJoint("b", self, Pos(Z=spacer_length))
        RigidJoint("center", self, Pos(Z=spacer_length))


class CBeamEndMount(BasePartObject):
    """CBeamEndMount

    Ensure seamless integration of your motor with the C-Beam Linear Rail using the
    versatile C-Beam End Mount. Designed with pre-threaded holes and a bearing recess
    for lead screw transmission, this mount also features additional countersunk holes
    for flush mounting, making it an excellent choice for various projects.

    Product Features:
        - Pre-tapped holes
        - Countersunk holes
        - Bearing recess for lead screw transmission

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
        align: Union[None, Align, tuple[Align, Align, Align]] = (
            Align.CENTER,
            Align.CENTER,
            Align.MIN,
        ),
        mode: Mode = Mode.ADD,
    ):

        with BuildPart() as plate:
            Box(80, 50, 12)
            with Locations(Location((0, 7.4, -6), (0, 1, 0), 180)):
                CounterBoreHole(5.588, 8.05, 4.5)
            with Locations((0, 8.9 - 25, 6)):
                with GridLocations(47.14, 0, 2, 1):
                    ThreadedHole(m5, counter_sunk=False)
            with Locations((0, 10 - 25, 6)):
                with GridLocations(20, 0, 2, 1):
                    CounterBoreHole(2.6, 4.6, 1.55)
            with Locations((0, 5, 6)):
                with GridLocations(60, 0, 2, 1):
                    CounterBoreHole(2.6, 4.6, 1.55)
            with Locations(Plane(plate.faces().sort_by(Axis.Y)[-1], x_dir=(1, 0, 0))):
                with GridLocations(20, 0, 2, 1):
                    ThreadedHole(m5, counter_sunk=False, depth=14 * MM)

        super().__init__(plate.part, rotation, align, mode)
        self.label = "CBeamEndMount"
        self.color = Color(0x020202)


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


class CBeamLinearRail(BasePartObject):
    """Part Object: OpenBuilds C-Beam Linear Rail

    C-Beam Linear Rail aluminum extrusion profile is the ultimate solution combining both
    linear motion and a modular, structural framing system. It's lightweight yet rigid and
    provides an ultra smooth track for precise motion.

    OpenBuilds created C-Beam Linear Rail aluminum extrusion profile and has added a
    library of compatible modular Parts which today is known as the OpenBuilds System.
    We have shipped over a million feet of V-Slot/C-Beam and counting to businesses,
    classrooms, laboratories and makers all over the world!

    Much like working with lumber, you can cut C-Beam on a chop saw (using a metal blade)
    or even use a hacksaw. From there, you simply use a screw driver to make the
    connections.

    Product Features:
        - Lightweight and strong
        - Tee Nut channel
        - Smooth v-groove for linear motion
        - M5 tap-ready holes
        - Anodized 6035 T-5 aluminum
        - Available in Sleek Silver or Industrial Black
        - Sizes: 80x40

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
        self.label = "CBeamLinearRail"
        LinearJoint(
            "screw_axis", self, Axis((10, 0, 0), (0, 0, 1)), linear_range=(0, length)
        )


class CBeamGantryPlate(BasePartObject):
    """Part Object: OpenBuilds C-Beam Gantry Plate

    Achieve a compact gantry cart footprint with the versatile C-Beam Gantry Plate. This
    plate accommodates up to 4 Mini V Wheels and can be easily configured to station wheels
    inside the C-Beam Linear Rail track. The plate features recessed and pre-tapped holes
    for professional flush mounts, making it a reliable component for various mounting
    configurations.

    Product Features:
        - Countersunk holes
        - Pre-tapped holes
        - Center recess
        - Multiple mounting configurations

    Specifications:
        - Size: 77.5 x 77.5mm
        - Thickness: 6mm
        - Material: 6061-T5 Aluminum
        - Finish: Brushed and Anodized
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
            with BuildSketch():
                RectangleRounded(38.575 * 2, 38.575 * 2, 4.635)
                with Locations((-5, 0)):
                    SlotCenterToCenter(10, 2.55 * 2, mode=Mode.SUBTRACT)
            extrude(amount=6)
            with BuildSketch(Plane.XY.offset(6)):
                RectangleRounded(29.9, 29.9, 4.92)
            extrude(amount=-1.5, mode=Mode.SUBTRACT)

            with Locations((0, 14.25, 6)):
                with GridLocations(60, 0, 2, 1):
                    CounterBoreHole(3.6, 6, 1.5)
            with Locations((0, -14.25, 6)):
                with GridLocations(60, 0, 2, 1):
                    CounterBoreHole(2.55, 4.5, 1.5)
            with Locations((0, 0, 6)):
                with GridLocations(40, 40, 2, 2):
                    ThreadedHole(m5, counter_sunk=False, depth=6 * MM)
                with GridLocations(20, 60, 2, 2):
                    ThreadedHole(m5, counter_sunk=False, depth=6 * MM)
            with GridLocations(60, 30, 2, 3):
                Hole(2.55)
            with GridLocations(20, 20, 3, 2):
                Hole(2.55)
            with GridLocations(0, 40, 1, 2):
                Hole(2.55)
            with Locations((-10, -10), (-10, 10), (10, 0)):
                Hole(2.55)

        super().__init__(plate.part, rotation=rotation, align=align, mode=mode)
        self.color = Color(0x020202)
        self.label = "CBeamGantryPlate"


class CBeamGantryPlateXLarge(BasePartObject):
    """Part Object: OpenBuilds C-Beam Gantry Plate X-Large

    Achieve unparalleled stability in your builds with the XLarge C-Beam Gantry Plate,
    designed to accommodate up to six wheels for an extremely stable gantry. This versatile
    plate is essential for both Belt and Pinion and Lead Screw transmissions. With recessed
    holes for professional flush mounts and tapped holes for a 90° connection, this plate is
    ideal for XY configurations, offering multiple mounting options to suit your project needs.

    Product Features:
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
                with GridLocations(20, 20, 2, 2) as nut_holes:
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
                with GridLocations(50.3, 0, 3, 1) as eccentric_mounts:
                    CounterBoreHole(3.6, 6.125, 1.6, 6)
            with Locations((0, 50.3, 6)):
                with GridLocations(50.3, 0, 3, 1) as fixed_mounts:
                    CounterBoreHole(2.55, 4.5675, 1.6, 6)

        super().__init__(plate.part, rotation=rotation, align=align, mode=mode)
        self.color = Color(0x020202)
        self.label = "CBeamGantryPlateXLarge"
        for label, loc in zip(["a", "b", "c"], eccentric_mounts):
            RigidJoint(label, self, Pos(*(loc.position - Vector(0, 0, 6))))
        for label, loc in zip(["d", "e", "f"], fixed_mounts):
            RigidJoint(label, self, Pos(*(loc.position - Vector(0, 0, 6))))
        for label, loc in zip(["a", "b", "c", "d"], nut_holes):
            RigidJoint(f"nut_{label}", self, loc)


class CBeamRiserPlate(BasePartObject):
    """Part Object: OpenBuilds C-Beam Riser Plate

    A key component used to attach C-Beam Gantry Plates to a C-Beam Shield. Pre-threaded
    holes and center recess allow for flush mounting a top plate. Each set contains 2 riser
    plates.

    Product Features:
        - C-Beam and V-Slot 20x80mm compatible
        - Pre-tapped holes
        - Center recess

    Specifications:
        - Size: 77.5 x 14.874mm
        - Thickness: 8mm
        - Material: 6061-T5 Aluminum
        - Finish: Brushed and Anodized
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
            with BuildSketch() as sk:
                Rectangle(38.75 * 2, 7.437 * 2)
                fillet(sk.vertices().group_by(Axis.Y)[0], 1.2)
                fillet(sk.vertices().group_by(Axis.Y)[-1], 3.5)
                with Locations((0, -1.323)):
                    with GridLocations(20, 0, 2, 1):
                        Circle(2.55, mode=Mode.SUBTRACT)
            extrude(amount=8)
            with BuildSketch(Plane((0, -7.427, 8))):
                RectangleRounded(32.24, 2 * 11.86712, 0.75)
            extrude(amount=-2.1, mode=Mode.SUBTRACT)
            with Locations((0, -1.323, 8)):
                with GridLocations(60, 0, 2, 1):
                    ThreadedHole(m5, counter_sunk=False, depth=8 * MM)

        super().__init__(plate.part, rotation=rotation, align=align, mode=mode)
        self.color = Color(0x020202)
        self.label = "CBeamRiserPlate"


class EccentricSpacer(BasePartObject):
    """Part Object: OpenBuilds Eccentric Spacer

    These Eccentric Spacers are the perfect solution for creating a pre-load from the V-Wheels
    to the V-Slot Linear Rail.

    Pro-Tip: Eccentric Spacers comes with a divot/text on the outside which allows you to know
    at all times where the smallest part of the CAM hole is located.

    Product Features:
        - Up to 1.5mm off center adjustment
        - Tension wheel to v-slot for a snug, locked on fit
        - Wide stance for stability

    Specifications:
        - Version - V7
        - 6mm or 1/4" CAM Height
        - 5mm Bore
        - Rim fits into a 7.12mm Hole
        - Stainless Steel
        - Color: Steel

    Args:
        rotation (RotationLike, optional): angles to rotate about axes. Defaults to (0, 0, 0).
        align (Union[Align, tuple[Align, Align, Align]], optional): align min, center,
            or max of object. Defaults to (Align.CENTER, Align.CENTER, Align.MIN).
        mode (Mode, optional): combine mode. Defaults to Mode.ADD.
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        cam_height=Literal["6mm", "1/4in"],
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):

        valid_heights = {
            "6mm": 6 * MM,
            "1/4in": IN / 4,
        }
        try:
            cam_length = valid_heights[cam_height]
        except KeyError:
            raise ValueError(
                f"{cam_height} is an invalid cam height, must be one of {tuple(valid_heights.keys())}"
            )

        # 10mm across the flats
        hex_radius = (2 / 3) * 10 * MM * math.sin(math.radians(60))
        with BuildPart() as spacer:
            with BuildSketch():
                RegularPolygon(hex_radius, 6)
            extrude(amount=6)
            with BuildSketch(Plane.YZ) as chamf:
                Rectangle(hex_radius, cam_length, align=Align.MIN)
                chamfer(chamf.vertices().group_by(Axis.Y)[0], 0.6)
            revolve(mode=Mode.INTERSECT)
            with Locations((0, 0, cam_length)):
                Cylinder(
                    hex_radius + 0.25 * MM,
                    1 * MM,
                    align=(Align.CENTER, Align.CENTER, Align.MAX),
                )
            with BuildSketch():
                Circle(3.555)
            extrude(amount=cam_length + 2.5 * MM)
            with Locations((0, 0.79 * MM)):  # eccentric hole
                Hole(2.5)
            with BuildSketch(spacer.faces().filter_by(Axis.Y).sort_by(Axis.Y)[-1]):
                Text(cam_height, font_size=1.5 * MM, font_style=FontStyle.BOLD)
            extrude(amount=-0.1 * MM, mode=Mode.SUBTRACT)

        super().__init__(
            spacer.part.locate(Pos(0, -0.79 * MM, 0)),
            rotation=rotation,
            align=align,
            mode=mode,
        )
        self.color = Color(0xC0C0C0)
        self.label = f"EccentricSpacer-{cam_height}"
        RigidJoint("a", self, Location())
        RigidJoint("b", self, Pos(Z=2.5 * MM + cam_length))
        RigidJoint("center", self, Pos(0, -0.79 * MM, cam_length))


class RouterSpindleMount(BasePartObject):
    """RouterSpindleMount

    Ensure the secure mounting of your router or spindle with this robust and adjustable
    mount. The thick and hefty design provides a stable base, while the adjustable
    faceplate accommodates size variations. This mount features pre-tapped holes for
    easy installation and optional attachments like the OpenBuilds LED Light Ring.

    Product Features:
        - Removable faceplate for quick tool changes
        - Adjustable faceplate to accommodate various router sizes
        - Countersunk holes for a flush finish
        - Tapped holes for easy mounting
        - Flexible mounting options

    Args:
        parts (Literal["base", "faceplate", "both"], optional): parts to be created.
            Defaults to "both".
        rotation (RotationLike, optional): angles to rotate about axes. Defaults to (0, 0, 0).
        align (Union[Align, tuple[Align, Align, Align]], optional): align min, center,
            or max of object. Defaults to None.
        mode (Mode, optional): combine mode. Defaults to Mode.ADD.

    Raises:
        ValueError: invalid parts parameter
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        parts: Literal["base", "faceplate", "both"] = "both",
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        m5 = SocketHeadCapScrew("M5-0.8", 20 * MM)
        width = 90.8 * MM
        height = 30.6 * MM + 54.5 * MM
        thickness = 20 * MM
        if parts in ["base", "both"]:
            with BuildPart() as base:
                # Create the basic shape
                with BuildSketch(Plane.XY.offset(-thickness / 2)) as c:
                    with Locations((0, height / 2 - 54.5)):
                        Rectangle(width, height)
                    Circle(35.5, mode=Mode.SUBTRACT)
                    Rectangle(
                        28.15 * 2,
                        35.5,
                        align=(Align.CENTER, Align.MIN),
                        mode=Mode.SUBTRACT,
                    )
                    fillet(c.vertices().group_by(Axis.Y)[0], 5)
                    fillet(c.vertices().group_by(Axis.Y)[-2], 7.5)
                extrude(amount=thickness)

                # Create the holes
                with Locations(
                    (30.0, -44.2, thickness / 2),
                    (20.0, -44.2, thickness / 2),
                    (-20.0, -44.2, thickness / 2),
                    (-30.0, -44.2, thickness / 2),
                ) as top_mount_centers:
                    ThreadedHole(m5, counter_sunk=False)
                with Locations(base.faces().sort_by(Axis.Y)[0]):
                    with GridLocations(20, 0, 4, 1):
                        ThreadedHole(m5, counter_sunk=False, depth=7 * MM)
                with Locations(
                    -Plane.YZ.offset(-width / 2), Plane.YZ.offset(width / 2)
                ):
                    with Locations((10.6, 0), (-29.4, 0)):
                        ThreadedHole(m5, counter_sunk=False, depth=9 * MM)
                with Locations(-Plane.XZ.offset(-base.part.bounding_box().max.Y)):
                    with GridLocations(36.8 * 2, 0, 2, 1):
                        ThreadedHole(m5, counter_sunk=False, depth=13 * MM)

        if parts in ["faceplate", "both"]:
            with BuildPart() as faceplate:
                with BuildSketch(Plane.XY.offset(-thickness / 2)) as s:
                    # Create basic half shape
                    Rectangle(23.65, 48.2, align=Align.MIN)
                    with Locations((0, 48.2)):
                        Rectangle(45.4, 48.2 - 36.2, align=(Align.MIN, Align.MAX))
                    Circle(35.5, mode=Mode.SUBTRACT)

                    # Fillet corners
                    fillet(s.vertices().group_by(Axis.Y)[-1].sort_by(Axis.X)[-1], 1.4)
                    fillet(s.vertices().group_by(Axis.Y)[-3].sort_by(Axis.X)[0], 3)
                    fillet(s.vertices().sort_by(Axis.Y)[0], 1.3)

                    # Mirror
                    mirror(about=Plane.YZ)
                extrude(amount=thickness)

                # Holes
                with Locations(faceplate.faces().group_by(Axis.Y)[-1]):
                    with GridLocations(36.8 * 2, 0, 2, 1):
                        CounterBoreHole(3, 5.1, 1.5)

                # Sunken embossed text
                with BuildSketch(faceplate.faces().sort_by(Axis.Y)[-1]) as s2:
                    RectangleRounded(27.45 * 2, 13, 2.5)
                extrude(amount=-1 * MM, mode=Mode.SUBTRACT)
                with BuildSketch(
                    faceplate.faces().filter_by(Axis.Y).sort_by(Axis.Y)[-2]
                ) as s2:
                    Text("OPENBUILDS", 7.5 * MM, font_style=FontStyle.BOLD)
                extrude(amount=0.1 * MM)

        if parts == "both":
            mount = base.part + faceplate.part
        elif parts == "base":
            mount = base.part
        elif parts == "faceplate":
            mount == faceplate.part
        else:
            raise ValueError(
                f"the parts parameter must one of 'base', 'faceplate' or 'both' "
                f"not {parts}"
            )
        mount.label = "RouterSpindleMount"
        super().__init__(mount, rotation, align, mode)
        self.color = Color(0x020202)
        for label, pos in zip(["a", "b", "c", "d"], top_mount_centers):
            RigidJoint(f"top_{label}", self, -pos)
        for label, pos in zip(["a", "b", "c", "d"], top_mount_centers):
            RigidJoint(f"bottom_{label}", self, pos * Pos(0, 0, -thickness))


class ShimWasher(BasePartObject):
    """Part Object: OpenBuilds Shim/Washer

    Product Features:
        - Reduce wear and prevents binding
        - Creates a tighter fit among parts

    Args:
        shim_type (Literal['MiniVWheel', '10x5x1', '12x8x1', 'SlotWasher', 'FlatWasher']):
            shim / washer
        rotation (RotationLike, optional): angles to rotate about axes. Defaults to (0, 0, 0).
        align (Union[Align, tuple[Align, Align, Align]], optional): align min, center,
            or max of object. Defaults to (Align.CENTER, Align.CENTER, Align.MIN).
        mode (Mode, optional): combine mode. Defaults to Mode.ADD.

    Raises:
        ValueError: Invalid shim_type
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        shim_type: Literal[
            "MiniVWheel", "10x5x1", "12x8x1", "SlotWasher", "FlatWasher"
        ],
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        # OD, ID, Thickness
        dimensions = {
            "MiniVWheel": (8, 5, 1),
            "10x5x1": (10, 5, 1),
            "12x8x1": (12, 8, 1),
            "SlotWasher": (15, 5, 2),
            "FlatWasher": (0.75 * IN, 0.25 * IN, 0.08 * IN),
        }
        try:
            od, id, thickness = dimensions[shim_type]
        except KeyError:
            raise ValueError(
                f"Invalid shim_type {shim_type} must be one of {tuple(dimensions.keys())}"
            )

        with BuildPart() as shim:
            with BuildSketch():
                Circle(od / 2)
                Circle(id / 2, mode=Mode.SUBTRACT)
            extrude(amount=thickness)
            fillet(shim.edges().group_by(SortBy.LENGTH)[-1], thickness / 5)

        super().__init__(shim.part, rotation=rotation, align=align, mode=mode)
        self.color = Color(0xC0C0C0)
        self.label = f"ShimWasher-{shim_type}"
        RigidJoint("a", self, Location())
        RigidJoint("b", self, Pos(Z=thickness))


class SpacerBlock(BasePartObject):
    """Part Object: OpenBuilds Spacer Block

    This Spacer Block allows you to raise the V-Slot Gantry Plate up away from the rail
    12mm so that you can run transmission components such as a Belt Drive or Threaded Rod
    underneath the V-Slot Gantry Plate.

    Product Features:
        - Adds transmission spacing to any V-Slot Liner Actuators
        - Compatible with multiple OpenBuilds plates

    Specifications:
        - Size: 86.4 x 20mm
        - Thickness: 12mm
        - M5 Tapped Holes to allow mounting to the V-Slot Gantry Plate
        - 3 Holes that allow for mounting of full size OpenBuilds Wheels
        - Anodized Aluminum
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
            with BuildSketch() as bs:
                RectangleRounded(86.4, 20, 3.36)
                with GridLocations(30, 0, 3, 1):
                    Circle(3.6, mode=Mode.SUBTRACT)
            extrude(amount=12)
            with Locations((0, 0, 12)):
                with GridLocations(40, 0, 2, 1):
                    ThreadedHole(m5, counter_sunk=False, depth=12)

        super().__init__(plate.part, rotation=rotation, align=align, mode=mode)
        self.color = Color(0x020202)
        self.label = "CBeamRiserPlate"


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


class VSlotLinearRail(BasePartObject):
    """Part Object: OpenBuilds V Slot Linear Rail

    V-Slot Linear Rail aluminum extrusion profile is the ultimate solution combining both
    linear motion and a modular, structural framing system. It's lightweight yet rigid and
    provides an ultra smooth track for precise motion.

    OpenBuilds created V-Slot Linear Rail aluminum extrusion profile and has added a
    library of compatible modular parts which today is known as the OpenBuilds System.
    We have shipped over one million feet of V-Slot and counting to businesses, classrooms,
    laboratories and makers all over the world!

    Much like working with lumber, you can cut V-Slot on a chop saw (using a metal blade)
    or even use a hacksaw. From there, you simply use a screw driver to make the connections.

    Product Features:
        - Lightweight and strong
        - Tee Nut channel
        - Smooth v-groove for linear motion
        - M5 tap-ready holes
        - Anodized 6035 T-5 aluminum
        - Available in Sleek Silver or Industrial Black
        - Sizes: 20x20, 20x40, 20x60, 20x80, and 40x40

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
        self.label = f"{rail_size} VSlot Rail"


class XLargeCBeamGantry(Compound):
    """XLargeCBeamGantry

    The C-Beam XLarge Gantry Set is ideal for high-performance demands. Tailored to
    excel in robust Linear Actuator gantries and CNC Machines, it fuses strength,
    resilience, and unwavering stability.

    Setting this Gantry kit apart are four robust Xtreme V Wheels. They shine under
    intense force and weight, delivering heightened accuracy and minimal compression
    for precision-driven tasks.

    Builders across various industries vouch for this Kit's reliability and consistent
    performance. Purpose-built for the X, Y, and Z axes of our OpenBuilds LEAD CNC Machine,
    elevate your projects with the proven versatility of the C-Beam XLargeGantry Set.

    Specifications:
        - Plate dimensions: 125mm x 125mm
        - Designed to be compatible with C-Beam Linear Rail
        - Specifically engineered for Lead Screw-driven systems

    Args:
        wheel_count (Literal[4, 6], optional): number of wheels. Defaults to 4.
        eccentric_angle (float, optional): angle of the eccentric spaces. Values
            less than 90 will tighten the wheels to the rail while values greater
            than 90 will loosen the fit. Defaults to 90.

    Raises:
        ValueError: Invalid wheel_count
    """

    def __init__(self, wheel_count: Literal[4, 6] = 4, eccentric_angle: float = 90):
        if wheel_count not in [4, 6]:
            raise ValueError(f"wheel_count of {wheel_count} must be either 4 or 6")
        plate = CBeamGantryPlateXLarge()
        w0 = XtremeSolidVWheelAssembly(True)
        w2 = copy.copy(w0)
        w3 = XtremeSolidVWheelAssembly(False)
        w5 = copy.copy(w3)
        wheels = [w0, w2, w3, w5]
        acme_nut_assembly = AcmeAntiBacklashNutBlock8mmAssembly()

        plate.joints["a"].connect_to(w0.joints["mount"], angle=eccentric_angle)
        plate.joints["c"].connect_to(w2.joints["mount"], angle=eccentric_angle)
        plate.joints["d"].connect_to(w3.joints["mount"])
        plate.joints["f"].connect_to(w5.joints["mount"])
        if wheel_count == 6:
            w1 = copy.copy(w0)
            w4 = copy.copy(w3)
            wheels.extend([w1, w4])
            plate.joints["b"].connect_to(w1.joints["mount"], angle=eccentric_angle)
            plate.joints["e"].connect_to(w4.joints["mount"])
        plate.joints["nut_a"].connect_to(acme_nut_assembly.joints["a"])

        super().__init__()
        self.label = "XLargeCBeamGantry"
        self.children = [plate, acme_nut_assembly] + wheels
        RigidJoint("nut", self, Location((0, 0, -12.5 * MM), (0, 1, 0), -90))


class XtremeSolidVWheel(BasePartObject):
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
            with BuildSketch(Plane.YZ) as x_section:
                with Locations((8, 0)):
                    Rectangle(3.95, 10.2, align=(Align.MIN, Align.CENTER))
                    Rectangle(2, 1)
                chamfer(x_section.vertices().group_by(Axis.X)[-1], 2.15)
            revolve()

        super().__init__(
            part=wheel.part, rotation=rotation, align=tuplify(align, 3), mode=mode
        )
        # self.color = Color(0xE0E0E0)
        self.color = Color(0xE0E0D8)
        self.label = "XtremeSolidVWHeel"
        RigidJoint("a", self, Pos(Z=-11 / 2))
        RigidJoint("b", self, Pos(Z=+11 / 2))


class XtremeSolidVWheelAssembly(Compound):
    """Assembly: OpenBuilds Xtreme Solid V Wheel Assembly

    All of the components in a Xtreme Solid V Wheel assembly:
        - Xtreme Solid V WHeel x 1
        - M5-16-5 bearing x 2
        - 10x5x1 Shim x 2
        - Aluminum Spacer or Eccentric Spacer
        - Hex Nut

    Note that the RevoluteJoint "mount" should be used to attach this wheel assembly
    to a gantry plate as it enables the eccentric spacer to precisely align the wheel
    to the rail by changing the joint angle.

    Args:
        eccentric (bool): Use an eccentric spacer.
    """

    def __init__(self, eccentric: bool):
        nut = HexNut("M5-0.8")
        b0 = SingleRowCappedDeepGrooveBallBearing("M5-16-5")
        b1 = copy.copy(b0)
        shim0 = ShimWasher("10x5x1")
        shim1 = copy.copy(shim0)
        spacer = EccentricSpacer("6mm") if eccentric else AluminumSpacer("6mm")
        tire = XtremeSolidVWheel()
        tire.joints["a"].connect_to(b0.joints["a"])
        b0.joints["b"].connect_to(shim0.joints["a"])
        b0.joints["a"].connect_to(nut.joints["b"])
        tire.joints["b"].connect_to(b1.joints["b"])
        b1.joints["b"].connect_to(shim1.joints["a"])
        shim1.joints["b"].connect_to(spacer.joints["a"])

        super().__init__()
        self.label = "XtremeSolidVWHeelAssembly"
        self.children = [tire, b0, shim0, shim1, b1, spacer, nut]
        RevoluteJoint(
            "mount", self, Axis(spacer.joints["center"].location.position, (0, 0, 1))
        )


if __name__ == "__main__":
    from ocp_vscode import show, set_defaults, Camera

    set_defaults(reset_camera=Camera.CENTER)

    # rail = CBeamLinearRail(30 * CM)
    # gantry = XLargeCBeamGantry(6)
    # rail.joints["screw_axis"].connect_to(gantry.joints["nut"], position=10 * CM)
    # print(gantry.show_topology())
    # show(rail, gantry)
    # exit()

    # show(
    #     pack(
    #         [
    #             CBeamLinearRailProfile(),
    #             VSlotLinearRailProfile("20x20"),
    #             VSlotLinearRailProfile("20x40"),
    #             VSlotLinearRailProfile("20x60"),
    #             VSlotLinearRailProfile("20x80"),
    #             VSlotLinearRailProfile("40x40"),
    #         ],
    #         10,
    #     )
    # )

    show(
        pack(
            [
                AcmeAntiBacklashNutBlock8mm(),
                AluminumSpacer("3mm"),
                AluminumSpacer("1/8in"),
                AluminumSpacer("6mm"),
                AluminumSpacer("1/4in"),
                AluminumSpacer("9mm"),
                AluminumSpacer("10mm"),
                AluminumSpacer("13.2mm"),
                AluminumSpacer("20mm"),
                AluminumSpacer("35mm"),
                AluminumSpacer("1-1/2in"),
                AluminumSpacer("40mm"),
                CBeamEndMount(),
                CBeamLinearRail(25),
                CBeamGantryPlate(),
                CBeamGantryPlateXLarge(),
                CBeamRiserPlate(),
                EccentricSpacer("6mm"),
                EccentricSpacer("1/4in"),
                RouterSpindleMount().rotate(Axis.Z, 180),
                ShimWasher("MiniVWheel"),
                ShimWasher("10x5x1"),
                ShimWasher("12x8x1"),
                ShimWasher("SlotWasher"),
                ShimWasher("FlatWasher"),
                SingleRowCappedDeepGrooveBallBearing("M5-10-4", "OpenBuilds"),
                SpacerBlock(),
                VSlotLinearRail("20x20", 25),
                VSlotLinearRail("20x40", 25),
                VSlotLinearRail("20x60", 25),
                VSlotLinearRail("20x80", 25),
                VSlotLinearRail("40x40", 25),
                XtremeSolidVWheel(),
            ],
            20,
        )
    )
    exit()

    # show(
    #     pack(
    #         [
    #             AcmeAntiBacklashNutBlock8mmAssembly(),
    #             XLargeCBeamGantry(4),
    #             XLargeCBeamGantry(6),
    #             XtremeSolidVWheelAssembly(True),
    #             XtremeSolidVWheelAssembly(False),
    #         ],
    #         20,
    #     )
    # )
