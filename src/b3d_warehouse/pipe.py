"""

Pipes

name: pipe.py
by:   Gumyr
date: May 23,  2023

desc:
    This python module is a CAD library of parametric pipes.

    The pipes created by this package are based off the following standards:

    * ASTM A312 is a standard specification issued by the American Society for
    Testing and Materials (ASTM) that covers seamless,  welded,  and heavily
    cold-worked austenitic stainless steel pipe intended for
    high-temperature and general corrosive service. The standard specifies
    various dimensions,  mechanical properties,  testing requirements,  and
    acceptable manufacturing practices for stainless steel pipes.

license:

    Copyright 2023 Gumyr

    Licensed under the Apache License,  Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing,  software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,  either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

"""
from typing import Literal, Union
from build123d import *
from build123d import tuplify


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


# fmt: off
# ASTM A312 Table X1. Dimensions of welded & seamless stainless steel pipe
#               |           Wall thickness              |
#     |    OD   | sch 5S  | sch 10S | sch 40S | sch 80S |
# nps | in | mm | in | mm | in | mm | in | mm | in | mm |
pipe_sizes_stainless = {
    "1/8":[0.405, 10.29, None, None, 0.049, 1.24, 0.068, 1.73, 0.095, 2.41],
    "1/4":[0.54, 13.72, None, None, 0.065, 1.65, 0.088, 2.24, 0.119, 3.02],
    "3/8":[0.675, 17.15, None, None, 0.065, 1.65, 0.091, 2.31, 0.126, 3.2],
    "1/2":[0.84, 21.34, 0.065, 1.65, 0.083, 2.11, 0.109, 2.77, 0.147, 3.73],
    "3/4":[1.05, 26.67, 0.065, 1.65, 0.083, 2.11, 0.113, 2.87, 0.154, 3.91],
    "1":[1.315, 33.4, 0.065, 1.65, 0.109, 2.77, 0.133, 3.38, 0.179, 4.55],
    "1 1/4":[1.66, 42.16, 0.065, 1.65, 0.109, 2.77, 0.14, 3.56, 0.191, 4.85],
    "1 1/2":[1.9, 48.26, 0.065, 1.65, 0.109, 2.77, 0.145, 3.68, 0.2, 5.08],
    "2":[2.375, 60.33, 0.065, 1.65, 0.109, 2.77, 0.154, 3.91, 0.218, 5.54],
    "2 1/2":[2.875, 73.03, 0.083, 2.11, 0.12, 3.05, 0.203, 5.16, 0.276, 7.01],
    "3":[3.5, 88.9, 0.083, 2.11, 0.12, 3.05, 0.216, 5.49, 0.3, 7.62],
    "3 1/2":[4, 101.6, 0.083, 2.11, 0.12, 3.05, 0.226, 5.74, 0.318, 8.08],
    "4":[4.5, 114.3, 0.083, 2.11, 0.12, 3.05, 0.237, 6.02, 0.337, 8.56],
    "5":[5.563, 141.3, 0.109, 2.77, 0.134, 3.4, 0.258, 6.55, 0.375, 8.52],
    "6":[6.625, 168.28, 0.109, 2.77, 0.134, 3.4, 0.258, 7.11, 0.432, 10.97],
    "8":[8.625, 219.08, 0.109, 2.77, 0.148, 3.76, 0.322, 8.18, 0.5, 12.7],
    "10":[10.75, 273.05, 0.134, 3.4, 0.165, 4.19, 0.365, 9.27, 0.500, 12.70],
    "12":[12.75, 323.85, 0.156, 3.96, 0.18, 4.57, 0.375 , 9.52 , 0.500 , 12.70],
    "14":[14, 355.6, 0.156, 3.96, 0.188 , 4.78 , None, None, None, None],
    "16":[16, 406.4, 0.165, 4.19, 0.188 , 4.78 , None, None, None, None],
    "18":[18, 457.2, 0.165, 4.19, 0.188 , 4.78 , None, None, None, None],
    "20":[20, 508, 0.188, 4.78, 0.218 , 4.54 , None, None, None, None],
    "22":[22, 558.8, 0.188, 4.78, 0.218 , 4.54 , None, None, None, None],
    "24":[24, 609.6, 0.218, 5.54, 0.25, 6.35, None, None, None, None],
    "30":[30, 762, 0.25, 6.35, 0.312, 7.92, None, None, None, None],
}

Nps = Literal[
    "1/8", "1/4", "3/8", "1/2", "3/4", "1", "1 1/4", "1 1/2", "2", "2 1/2", "3",
    "4", "5", "6", "8", "10", "12", "14", "16", "18", "20", "22", "24", "30"
]
# fmt: on
Sch = Literal["5S", "10S", "40S", "80S"]
Material = Literal["Stainless"]


class PipeSection(BaseSketchObject):
    """Pipe Section

    The cross section of a pipe with the given parameters.

    Args:
        nps (Nps): nominal pipe size
        sch (Sch): pipe schedule
        material (Material,  optional): material type. Defaults to "Stainless".
        align (Union[Align,  tuple[Align,  Align]],  optional): alignment.
            Defaults to Align.CENTER.
        mode (Mode,  optional): combination mode. Defaults to Mode.ADD.

    Raises:
        ValueError: Invalid nps
        ValueError: Invalid sch
        ValueError: Invalid material
    """

    def __init__(
        self,
        nps: Nps,
        sch: Sch,
        material: Material = "Stainless",
        align: Union[Align, tuple[Align, Align]] = Align.CENTER,
        mode: Mode = Mode.ADD,
    ):
        self.nps = nps
        self.sch = sch
        self.material = material

        if nps not in Nps.__args__:
            raise ValueError(
                f"Invalid nps value - the valid values are: {Nps.__args__}"
            )
        if sch not in Sch.__args__:
            raise ValueError(
                f"Invalid sch value - the valid values are: {Sch.__args__}"
            )
        if material not in Material.__args__:
            raise ValueError(
                f"Invalid material value - the valid values are: {Material.__args__}"
            )
        sch_index = 2 * list(Sch.__args__).index(sch) + 3
        if material == "Stainless":
            od = pipe_sizes_stainless[nps][1]
            thickness = pipe_sizes_stainless[nps][sch_index]

        if thickness is None:
            raise ValueError("Invalid sch value for this pipe")

        self.od = od
        self.thickness = thickness
        self.id = od - 2 * thickness

        with BuildSketch() as cross_section:
            Circle(radius=od / 2)
            Circle(radius=self.id / 2, mode=Mode.SUBTRACT)

        super().__init__(obj=cross_section.sketch, align=tuplify(align, 2), mode=mode)


class Pipe(BasePartObject):
    """Pipe

    Parametric Pipes of standard sizes and materials with its center
    following the provided path parameter.

    Joints:
        inlet (Rigid): set at the beginning of the path
        outlet (Rigid): set at the end of the path

    Args:
        nps (Nps): nominal pipe size
        sch (Sch): pipe schedule
        path (Union[Edge, Wire]): center line path of the pipe
        material (Material,  optional): material type. Defaults to "Stainless".
        rotation (RotationLike,  optional): rotations about axes. Defaults to (0,  0,  0).
        align (Union[Align,  tuple[Align,  Align,  Align]],  optional): alignment.
            Defaults to None.
        mode (Mode,  optional): combination mode. Defaults to Mode.ADD.

    Joints:
        "inlet" (Rigid): inlet end of the pipe
        "outlet" (Rigid): outlet end of the pipe
    """

    def __init__(
        self,
        nps: Nps,
        sch: Sch,
        path: Union[Edge, Wire],
        material: Material = "Stainless",
        rotation: RotationLike = (0, 0, 0),
        align: Union[Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        section = PipeSection(nps, sch, material)
        self.od = section.od
        self.id = section.id
        self.thickness = section.thickness
        self.length = path.length

        with BuildPart() as pipe:
            add(path)
            with BuildSketch(Plane(origin=path @ 0, z_dir=path % 0)):
                add(section)
            sweep()

        super().__init__(
            solid=pipe.part, rotation=rotation, align=tuplify(align, 3), mode=mode
        )

        # Add the joints
        RigidJoint("inlet", self, path.location_at(0))
        RigidJoint("outlet", self, path.location_at(1))
