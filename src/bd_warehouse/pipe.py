"""

Pipes

name: pipe.py
by:   Gumyr
date: May 23,  2023

desc:
    This python module is a CAD library of parametric pipes.

    The pipes created by this package are based off the following standards:

    * ASTM A312 is a standard specification issued by the American Society for
    Testing and Materials (ASTM) that covers seamless,  welded, and heavily
    cold-worked austenitic stainless steel pipe intended for high-temperature 
    and general corrosive service. The standard specifies various dimensions,  
    mechanical properties,  testing requirements,  and acceptable manufacturing 
    practices for stainless steel pipes.
    * ASME B36 is a standard issued by the American Society of Mechanical Engineers
    (ASME) that provides guidelines for the dimensions, tolerances, and related 
    requirements of steel pipes and fittings. It covers both seamless and welded 
    pipes made from various materials, including carbon steel, stainless steel, 
    and alloy steel. The standard specifies the nominal pipe sizes (NPS), outside 
    diameters (OD), wall thicknesses, and length dimensions. ASME B36 aims to ensure 
    consistency and compatibility in the design, manufacturing, and installation of 
    steel pipes, facilitating efficient piping system construction and operation in 
    various industries.
    * ASTM B88 is a standard specification issued by ASTM International for seamless 
    copper water tube used in plumbing applications. The standard defines the requirements 
    for copper water tube in terms of its dimensions, chemical composition, mechanical 
    properties, and permissible variations. It covers various sizes and types of copper 
    water tube, including both hard-drawn and annealed tempers. ASTM B88 ensures the 
    quality and reliability of copper water tube by providing specifications for its 
    manufacturing and performance. It serves as a reference for manufacturers, engineers, 
    and contractors involved in plumbing systems, ensuring compatibility, durability, 
    and safe water transportation.
    * ASTM F628 is a standard specification issued by ASTM International that pertains 
    to the installation and performance requirements of plastic pipes in non-pressure 
    applications. It specifically focuses on the installation of plastic pipes, such 
    as PVC (Polyvinyl Chloride) and CPVC (Chlorinated Polyvinyl Chloride), for drainage, 
    waste, and vent systems. The standard covers various aspects, including pipe sizes, 
    materials, dimensions, joint methods, and testing procedures. ASTM F628 ensures the 
    proper installation and performance of plastic pipes in non-pressure plumbing 
    applications, promoting safe and efficient drainage and waste disposal systems in 
    residential and commercial buildings.
    * ASTM D1785 is a standard specification issued by ASTM International for rigid 
    polyvinyl chloride (PVC) pipes used in pressure applications, primarily in potable
    water systems. The standard outlines the requirements for PVC pipes in terms of 
    their dimensions, material properties, and quality control procedures. It covers 
    various aspects, including pipe sizes, wall thicknesses, chemical composition, 
    hydrostatic pressure testing, and marking. ASTM D1785 ensures the durability, 
    strength, and safety of PVC pipes by establishing guidelines for their manufacturing, 
    performance, and testing. The standard serves as a reference for manufacturers, 
    engineers, and regulatory bodies to ensure the reliable and efficient use of PVC 
    pipes in pressure applications.
            
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
from __future__ import annotations
import csv
import importlib.resources as pkg_resources
from typing import Literal, Union
from build123d import *
from build123d import tuplify
import bd_warehouse


# fmt: off
Nps = Literal[
    "1/8", "1/4", "3/8", "1/2", "3/4", "1", "1 1/4", "1 1/2", "2", "2 1/2", "3", "4", "5",
    "6", "8", "10", "12", "14", "16", "18", "20", "22", "24", "30", "32", "34", "36", "42"
]
Identifier = Literal[
    "K", "L", "M", "STD", "XS", "XXS", "5S", "10", "10S", "20", "30", "40", "40S",
    "60", "80", "80S", "100", "120", "140", "160"
]
# fmt: on
Material = Literal["abs", "copper", "iron", "pvc", "stainless", "steel"]


class PipeSection(BaseSketchObject):
    """Pipe Section

    The cross section of a pipe with the given parameters.

    Args:
        nps (Nps): nominal pipe size
        material (Material,  optional): material type.
        identifier (Identifier): pipe identifier, i.e. schedule or type
        align (Union[None, Align,  tuple[Align,  Align]],  optional): alignment.
            Defaults to Align.CENTER.
        mode (Mode,  optional): combination mode. Defaults to Mode.ADD.

    Raises:
        ValueError: Invalid nps
        ValueError: Invalid identifier
        ValueError: Invalid material
    """

    # Read the pipe data
    pipe_data = {}
    with pkg_resources.open_text(bd_warehouse, "pipe.csv") as csvfile:
        reader = csv.reader(csvfile)
        next(reader, None)  # skip the header row
        for row in reader:
            if len(row) == 0:  # skip blank rows
                continue
            nps, material, identifier, od, thickness = row
            pipe_data[nps + material + identifier] = (float(od), float(thickness))

    def __init__(
        self,
        nps: Nps,
        material: Material,
        identifier: Identifier,
        align: Union[None, Align, tuple[Align, Align]] = Align.CENTER,
        mode: Mode = Mode.ADD,
    ):
        self.nps = nps
        self.sch = identifier
        self.material = material

        if nps not in Nps.__args__:
            raise ValueError(
                f"Invalid nps value - the valid values are: {Nps.__args__}"
            )
        if identifier not in Identifier.__args__:
            raise ValueError(
                f"Invalid identifier value - the valid values are: {Identifier.__args__}"
            )
        if material not in Material.__args__:
            raise ValueError(
                f"Invalid material value - the valid values are: {Material.__args__}"
            )

        try:
            od_in, thickness_in = PipeSection.pipe_data[nps + material + identifier]
        except:
            raise ValueError(f"No pipe data for {nps}, {material}, {identifier}")

        self.od = od_in * IN
        self.thickness = thickness_in * IN
        self.id = self.od - 2 * self.thickness

        with BuildSketch() as cross_section:
            Circle(radius=self.od / 2)
            Circle(radius=self.id / 2, mode=Mode.SUBTRACT)

        super().__init__(obj=cross_section.sketch, align=tuplify(align, 2), mode=mode)


class Pipe(BasePartObject):
    """Pipe

    Parametric Pipes of standard sizes and materials with its center
    following the provided path parameter.

    Args:
        nps (Nps): nominal pipe size
        material (Material,  optional): material type.
        identifier (Identifier): pipe identifier, i.e. schedule or type
        path (Union[Edge, Wire]): center line path of the pipe
        rotation (RotationLike,  optional): rotations about axes. Defaults to (0,  0,  0).
        align (Union[NOne, Align,  tuple[Align,  Align,  Align]],  optional): alignment.
            Defaults to None.
        mode (Mode,  optional): combination mode. Defaults to Mode.ADD.

    Joints:
        "inlet" (Rigid): inlet end of the pipe
        "outlet" (Rigid): outlet end of the pipe
    """

    def __init__(
        self,
        nps: Nps,
        material: Material,
        identifier: Identifier,
        path: Union[None, Edge, Wire] = None,
        rotation: RotationLike = (0, 0, 0),
        align: Union[None, Align, tuple[Align, Align, Align]] = None,
        mode: Mode = Mode.ADD,
    ):
        context: BuildPart = BuildPart._get_context()

        if path is None:
            if context is not None and context.pending_edges:
                # Get pending edges for the path
                path = context.pending_edges
                context.pending_edges = []
            else:
                raise ValueError("A path must be provided")
        elif isinstance(path, Wire):
            path = path.edges()
        elif isinstance(path, Edge):
            path = [path]
        else:
            raise ValueError("Invalid path type")

        section = PipeSection(nps, material, identifier)
        self.od = section.od
        self.id = section.id
        self.thickness = section.thickness
        self.length = (
            sum([p.length for p in path]) if isinstance(path, list) else path.length
        )

        with BuildPart() as pipe:
            for p in path:
                add(p)
                with BuildSketch(Plane(origin=p @ 0, z_dir=p % 0)):
                    add(section)
                sweep()

        super().__init__(
            solid=pipe.part, rotation=rotation, align=tuplify(align, 3), mode=mode
        )
        self.material = material

        # Add the joints
        RigidJoint("inlet", self, path[0].location_at(0))
        RigidJoint("outlet", self, path[-1].location_at(1))
