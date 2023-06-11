"""

Flanges

name: flange.py
by:   Gumyr
date: May 23, 2023

desc:
    This python module is a CAD library of parametric flanges based off
    the following standard:

    ASME B16.5 is a standard published by the American Society of Mechanical
    Engineers (ASME) that covers the dimensions, materials, and testing
    requirements for pipe flanges and flanged fittings.

    Consulting the relevant codes, standards, and engineering specifications
    is essential to select the appropriate flange class for a given
    application to ensure safe and reliable operation.

Flange Types
------------

In ASME B16.5, there are several types of flanges specified. Here are the
flange types (classes) implemented by this package:

    * WeldNeckFlange: This type of flange is designed with a
    tapered hub and a neck that provides reinforcement and better
    structural integrity. It is typically used in high-pressure and
    high-temperature applications.

    * SlipOnFlange: Slip-On Flange: A slip-on flange has a flat face and is
    intended to slide over the pipe and then be welded in place. It is
    commonly used for low-pressure applications and non-critical systems.

Flange Classes
--------------

In ASME B16.5, the flange classes refer to different
pressure-temperature ratings for flanges. The flange classes specify the
maximum allowable working pressure at a given temperature for a
particular flange design and material.

Here are the key differences between the flange classes:

    * Pressure-Temperature Rating: Each flange class is assigned a specific
    pressure-temperature rating based on the materials, design, and intended
    application. Flange classes are designated by numbers such as 150, 300,
    600, 900, 1500, and 2500. The higher the class number, the higher the
    pressure rating.

    * Flange Thickness and Dimensions: Flange classes may have different
    thickness requirements to handle the specified pressure rating. Higher
    flange classes generally have thicker flanges to provide the necessary
    strength and rigidity.

    * Bolt Circle Diameter: The bolt circle diameter, which refers to the
    diameter of the circle formed by the centers of the bolt holes on the
    flange, can vary among flange classes. Higher flange classes often have
    larger bolt circle diameters to accommodate more and larger bolts for
    increased pressure capacity.

    * Number of Bolt Holes: Flange classes may have different numbers of bolt
    holes depending on their size and pressure rating. Smaller flanges
    typically have fewer bolt holes compared to larger ones.

    * Gasket Type: The flange class can also influence the type and size of
    gasket required for proper sealing. Higher pressure classes may require
    thicker or larger gaskets to ensure effective sealing under higher
    loads.

It's important to note that the specific design requirements and
dimensions for each flange class are outlined in the ASME B16.5
standard. The choice of flange class depends on the specific application
requirements, including the expected pressure, temperature, and fluid
being conveyed in the piping system.


Classes 150 and 300 pipe flanges and companion flanges of fittings
are regularly furnished with 2 mm (0.06 in.) raised
face, which is in addition to the minimum flange thickness,
tf. Classes 400, 600, 900, 1500, and 2500 pipe flanges and
companion flanges of fittings are regularly furnished with
7 mm (0.25 in.) raised face, which is in addition to the
minimum flange thickness, tf.

Face Types
----------

In ASME B16.5, there are several different types of flange faces
specified. The flange face refers to the sealing surface of the flange
that comes into contact with the gasket to achieve a secure and reliable
seal. Here are the key differences between the flange faces:

* Raised Face (RF): The raised face is the most commonly used flange face
type. It features a concentric raised surface around the bore hole,
providing an additional sealing surface. The height of the raised face
is typically 1/16 inch (1.6 mm) or 1/4 inch (6.4 mm).

* Flat Face (FF): The flat face is a smooth, flat surface without any
raised areas. It is used when a flat gasket is employed for sealing. The
flat face flange is primarily used for low-pressure applications or when
the mating flange face is also flat.

* Ring Joint (RJ): The ring joint face is a specially designed groove
machined into the flange. It is used with metal ring gaskets for
high-pressure and high-temperature applications. The ring joint face
provides a tight and reliable seal under extreme conditions.

* Tongue and Groove (TG): The tongue and groove face consists of a raised
ring (tongue) on one flange and a corresponding recess (groove) on the
other flange. This face type ensures proper alignment and prevents
lateral movement of the gasket.

* Male and Female (M&F): The male and female face features a protruding
"male" flange face that fits into a recessed "female" flange face. This
type is commonly used in applications where alignment and precise
fitting are important.

The choice of flange face type depends on various factors, such as the
operating conditions, pressure, temperature, and the type of gasket
used. It is important to follow the specified flange face requirements
to ensure proper sealing and avoid leakage in the piping system.

Use the face_type parameter when creating a flange to select the
appropriate face.  face_type is of type FaceType, a Literal with
the following values: "Flat", "Raised", "Lap", "Ring", "Tongue", "Groove",
"Male", or "Female".


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
from math import degrees, atan2
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


# Nominal pipe size (NPS) to nominal diameter
nps_to_dn = {
    "1/2": 15,
    "3/4": 20,
    "1": 25,
    "1 1/4": 32,
    "1 1/2": 40,
    "2": 50,
    "2 1/2": 65,
    "3": 80,
    "4": 100,
    "5": 125,
    "6": 150,
    "8": 200,
    "10": 250,
    "12": 300,
    "14": 350,
    "16": 400,
    "18": 450,
    "20": 500,
    "22": 550,
    "24": 600,
}
# fmt: off
# ASME 16.5 Table 7 Templates for Drilling Class 150 Pipe Flanges and Flanged Fittings
drilling_class_150 = {
    "1/2":[90,60.3,"5/8",4,"1/2",55,"…",50],
    "3/4":[100,69.9,"5/8",4,"1/2",65,"…",50],
    "1":[110,79.4,"5/8",4,"1/2",65,75,55],
    "1 1/4":[115,88.9,"5/8",4,"1/2",70,85,55],
    "1 1/2":[125,98.4,"5/8",4,"1/2",70,85,65],
    "2":[150,120.7,"3/4",4,"5/8",85,95,70],
    "2 1/2":[180,139.7,"3/4",4,"5/8",90,100,75],
    "3":[190,152.4,"3/4",4,"5/8",90,100,75],
    "3 1/2":[215,177.8,"3/4",8,"5/8",90,100,75],
    "4":[230,190.5,"3/4",8,"5/8",90,100,75],
    "5":[255,215.9,"7/8",8,"3/4",95,110,85 ],
    "6":[280,241.3,"7/8",8,"3/4",100,115,85],
    "8":[345,298.5,"7/8",8,"3/4",110,120,90],
    "10":[405,362.0,"1",12,"7/8",115,125,100],
    "12":[485,431.8,"1",12,"7/8",120,135,100],
    "14":[535,476.3,"1 1/8",12,1,"135",145,115],
    "16":[595,539.8,"1 1/8",16,"1",135,145,115],
    "18":[635,577.9,"1 1/4",16,"1 1/8",145,160,125],
    "20":[700,635.0,"1 1/4",20,"1 1/8",160,170,140],
    "22":[750,692.2,"1 3/8",20,"1 1/4",170,185,150],
    "24":[815,749.3,"1 3/8",20,"1 1/4",170,185,150],
}
# ASME 16.5 Table 9 Templates for Drilling Class 300 Pipe Flanges and Flanged Fittings
drilling_class_300 = {
    "1/2":[95,66.7,"5/8",4,"1/2",65,75,55],
    "3/4":[115,82.6,"3/4",4,"5/8",75,90,65],
    "1":[125,88.9,"3/4",4,"5/8",75,90,65],
    "1 1/4":[135,98.4,"3/4",4,"5/8",85,95,70],
    "1 1/2":[155,114.3,"7/8",4,"3/4",90,100,75],
    "2":[165,127.0,"3/4",8,"5/8",90,100,75],
    "2 1/2":[190,149.2,"7/8",8,"3/4",100,115,85],
    "3":[210,168.3,"7/8",8,"3/4",110,120,90],
    "3 1/2":[230,184.2,"7/8",8,"3/4",110,125,95],
    "4":[255,200.0,"7/8",8,"3/4",115,125,95],
    "5":[280,235.0,"7/8",8,"3/4",120,135,110],
    "6":[320,269.9,"7/8",12,"3/4",120,140,110],
    "8":[380,330.2,1,12,"7/8",140,150,120],
    "10":[445,387.4,"1 1/8",16,1,160,170,140],
    "12":[520,450.8,"1 1/4",16,"1 1/8",170,185,145],
    "14":[585,514.4,"1 1/4",20,"1 1/8",180,190,160],
    "16":[650,571.5,"1 3/8",20,"1 1/4",190,205,165],
    "18":[710,628.6,"1 3/8",24,"1 1/4",195,210,170],
    "20":[775,685.8,"1 3/8",24,"1 1/4",205,220,185],
    "22":[840,743.0,"1 5/8",24,"1 1/2",230,255,205],
    "24":[915,812.8,"1 5/8",24,"1 1/2",230,255,205],
}
# ASME 16.5 Table 8 Dimensions of Class 150 Flanges
flange_data_class_150 = {
    "1/2":[90,9.6,11.2,30,21.3,14,16,46,16,22.2,22.9,15.8,3,10],
    "3/4":[100,11.2,12.7,38,26.7,14,16,51,16,27.7,28.2,20.9,3,11],
    "1":[110,12.7,14.3,49,33.4,16,17,54,17,34.5,34.9,26.6,3,13],
    "1 1/4":[115,14.3,15.9,59,42.2,19,21,56,21,43.2,43.7,35.1,5,14],
    "1 1/2":[125,15.9,17.5,65,48.3,21,22,60,22,49.5,50.0,40.9,6,16],
    "2":[150,17.5,19.1,78,60.3,24,25,62,25,61.9,62.5,52.5,8,17,],
    "2 1/2":[180,20.7,22.3,90,73.0,27,29,68,29,74.6,75.4,62.7,8,19],
    "3":[190,22.3,23.9,108,88.9,29,30,68,30,90.7,91.4,77.9,10,21],
    "3 1/2":[215,22.3,23.9,122,101.6,30,32,70,32,103.4,104.1,90.1,10,"…"],
    "4":[230,22.3,23.9,135,114.3,32,33,75,33,116.1,116.8,102.3,11,"…"],
    "5":[255,22.3,23.9,164,141.3,35,36,87,36,143.8,144.4,128.2,11,"…"],
    "6":[280,23.9,25.4,192,168.3,38,40,87,40,170.7,171.4,154.1,13,"…"],
    "8":[345,27.0,28.6,246,219.1,43,44,100,44,221.5,222.2,202.7,13,"…"],
    "10":[405,28.6,30.2,305,273.0,48,49,100,49,276.2,277.4,254.6,13,"…"],
    "12":[485,30.2,31.8,365,323.8,54,56,113,56,327.0,328.2,304.8,13,"…"],
    "14":[535,33.4,35.0,400,355.6,56,79,125,57,359.2,360.2,"Note (8)",13,"…"],
    "16":[595,35.0,36.6,457,406.4,62,87,125,64,410.5,411.2,"Note (8)",13,"…"],
    "18":[635,38.1,39.7,505,457.0,67,97,138,68,461.8,462.3,"Note (8)",13,"…"],
    "20":[700,41.3,42.9,559,508.0,71,103,143,73,513.1,514.4,"Note (8)",13,"…"],
    "22":[750,44.5,46.1,610,558.8,78,108,148,"…",564.4,565.2,"Note (8)",13,"…"],
    "24":[815,46.1,47.7,663,610.0,81,111,151,83,616.0,616.0,"Note (8)",13,"…"],
}
# ASME 16.5 Table 10 Dimensions of Class 300 Flanges
flange_data_class_300 = {
    "1/2":[95,12.7,14.3,38,21.3,21,22,51,16,22.2,22.9,15.8,3,23.6,10],
    "3/4":[115,14.3,15.9,48,26.7,24,25,56,16,27.7,28.2,20.9,3,29.0,11],
    "1":[125,15.9,17.5,54,33.4,25,27,60,18,34.5,34.9,26.6,3,35.8,13],
    "1 1/4":[135,17.5,19.1,64,42.2,25,27,64,21,43.2,43.7,35.1,5,44.4,14],
    "1 1/2":[155,19.1,20.7,70,48.3,29,30,67,23,49.5,50.0,40.9,6,50.3,16],
    "2":[165,20.7,22.3,84,60.3,32,33,68,29,61.9,62.5,52.5,8,63.5,17],
    "2 1/2":[190,23.9,25.4,100,73.0,37,38,75,32,74.6,75.4,62.7,8,76.2,19],
    "3":[210,27.0,28.6,117,88.9,41,43,78,32,90.7,91.4,77.9,10,92.2,21],
    "3 1/2":[230,28.6,30.2,133,101.6,43,44,79,37,103.4,104.1,90.1,10,104.9,"…"],
    "4":[255,30.2,31.8,146,114.3,46,48,84,37,116.1,116.8,102.3,11,117.6,"…"],
    "5":[280,33.4,35.0,178,141.3,49,51,97,43,143.8,144.4,128.2,11,144.4,"…"],
    "6":[320,35.0,36.6,206,168.3,51,52,97,47,170.7,171.4,154.1,13,171.4,"…"],
    "8":[380,39.7,41.3,260,219.1,60,62,110,51,221.5,222.2,202.7,13,222.2,"…"],
    "10":[445,46.1,47.7,321,273.0,65,95,116,56,276.2,277.4,254.6,13,276.2,"…"],
    "12":[520,49.3,50.8,375,323.8,71,102,129,61,327.0,328.2,304.8,13,328.6,"…"],
    "14":[585,52.4,54.0,425,355.6,75,111,141,64,359.2,360.2,"Note (7)",13,360.4,"…"],
    "16":[650,55.6,57.2,483,406.4,81,121,144,69,410.5,411.2,"Note (7)",13,411.2,"…"],
    "18":[710,58.8,60.4,533,457.0,87,130,157,70,461.8,462.3,"Note (7)",13,462.0,"…"],
    "20":[775,62.0,63.5,587,508.0,94,140,160,74,513.1,514.4,"Note (7)",13,512.8,"…"],
    "22":[840,65.1,66.7,640,558.8,100,145,164,"…",564.4,565.2,"Note (7)",13,"…","…"],
    "24":[915,68.3,69.9,702,610.0,105,152,167,83,616.0,616.0,"Note (7)",13,614.4,"…"],
}
# nps |	Groove # | Pitch Dia, P	| Depth, E | Width, F | Rad at Bottom, R | Dia of Raised Portion, K | Distance Between Flanges |
ring_joint_facings_class_150 = {
    "1":[15,47.63,6.35,8.74,0.8,63.5,4],
    "1 1/4":[17,57.15,6.35,8.74,0.8,73,4],
    "1 1/2":[19,65.07,6.35,8.74,0.8,82.5,4],
    "2":[22,82.55,6.35,8.74,0.8,102,4],
    "2 1/2":[25,101.6,6.35,8.74,0.8,121,4],
    "3":[29,114.3,6.35,8.74,0.8,133,4],
    "3 1/2":[33,131.78,6.35,8.74,0.8,154,4],
    "4":[36,149.23,6.35,8.74,0.8,171,4],
    "5":[40,171.45,6.35,8.74,0.8,194,4],
    "6":[43,193.68,6.35,8.74,0.8,219,4],
    "8":[48,247.65,6.35,8.74,0.8,273,4],
    "10":[52,304.8,6.35,8.74,0.8,330,4],
    "12":[56,381,6.35,8.74,0.8,406,4],
    "14":[59,396.88,6.35,8.74,0.8,425,3],
    "16":[64,454.03,6.35,8.74,0.8,483,3],
    "18":[68,517.53,6.35,8.74,0.8,546,3],
    "20":[72,558.8,6.35,8.74,0.8,597,3],
    "22":[80,615.95,6.35,8.74,0.8,648,3],
    "24":[76,673.1,6.35,8.74,0.8,711,3],
}
ring_joint_facings_class_300 = {
    "1/2":[11,34.14,5.54,7.14,0.8,51,3],
    "3/4":[13,42.88,6.35,8.74,0.8,63.5,4],
    "1":[16,50.8,6.35,8.74,0.8,70,4],
    "1 1/4":[18,60.33,6.35,8.74,0.8,79.5,4],
    "1 1/2":[20,68.27,6.35,8.74,0.8,90.5,4],
    "2":[23,82.55,7.92,11.91,0.8,108,6],
    "2 1/2":[26,101.6,7.92,11.91,0.8,127,6],
    "3":[31,123.83,7.92,11.91,0.8,146,6],
    "3 1/2":[34,131.78,7.92,11.91,0.8,159,6],
    "4":[37,149.23,7.92,11.91,0.8,175,6],
    "5":[41,180.98,7.92,11.91,0.8,210,6],
    "6":[45,211.12,7.92,11.91,0.8,241,6],
    "8":[49,269.88,7.92,11.91,0.8,302,6],
    "10":[53,323.85,7.92,11.91,0.8,356,6],
    "12":[57,381,7.92,11.91,0.8,413,6],
    "14":[61,419.1,7.92,11.91,0.8,457,6],
    "16":[65,469.9,7.92,11.91,0.8,508,6],
    "18":[69,533.4,7.92,11.91,0.8,575,6],
    "20":[73,584.2,9.53,13.49,1.5,635,6],
    "22":[81,635,11.13,15.09,1.5,686,6],
    "24":[77,692.15,11.13,16.66,1.5,749,6],
}
# Note: ring joints with lapped flanges use the following for NPS 3 instead:
# "3":[30,117.48,7.92,11.91,0.8,…,…],

Nps = Literal[
    "1/2", "3/4", "1", "1 1/4", "1 1/2", "2", "2 1/2", "3", "4",
    "5", "6", "8", "10", "12", "14", "16", "18", "20", "22", "24",
]

# fmt: on
FaceType = Literal["Flat", "Raised", "Lap", "Ring", "Tongue", "Groove"]
FlangeClass = Literal[150, 300, 400, 600, 900, 1500, 2500]


class Flange(BasePartObject):
    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        flange_section: Union[Face, Sketch],
        bcd: float,
        bolt_hole_count: int,
        bolt_hole_diameter: float,
        rotation: RotationLike = (0, 0, 0),
        align: Union[Align, tuple[Align, Align, Align]] = (
            Align.CENTER,
            Align.CENTER,
            Align.MIN,
        ),
        mode: Mode = Mode.ADD,
    ):
        """Flange

        Base class for all the derived flange classes.

        Args:
            flange_section (Union[Face, Sketch]): 2D cross section
            bcd (float): bolt center diameter
            bolt_hole_count (int): number of bolt holes
            bolt_hole_diameter (float): bolt hole size
            rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
            align (Union[Align, tuple[Align, Align, Align]], optional):
                object alignment. Defaults to ( Align.CENTER, Align.CENTER, Align.MIN, ).
            mode (Mode, optional): combination mode. Defaults to Mode.ADD.
        """
        with BuildPart() as flange_builder:
            with BuildSketch(Plane.XZ):
                add(flange_section)
                split(bisect_by=Plane.YZ)
            revolve()
            with PolarLocations(bcd / 2, bolt_hole_count):
                Hole(bolt_hole_diameter / 2)

        super().__init__(
            solid=flange_builder.part,
            rotation=rotation,
            align=tuplify(align, 3),
            mode=mode,
        )

    @staticmethod
    def inputs_are_valid(
        nps: Nps,
        flange_class: FlangeClass,
        face_type: FaceType,
    ) -> bool:
        """inputs_are_valid

        Validate common flange inputs.

        Args:
            nps (Nps): nominal pipe size
            flange_class (FlangeClass): class
            face_type (FaceType): face options

        Raises:
            ValueError: Invalid nps
            ValueError: Invalid flange_class
            ValueError: Invalid face_type

        Returns:
            bool: inputs are valid
        """
        if nps not in Nps.__args__:
            raise ValueError(
                f"Invalid nps value - the valid values are: {Nps.__args__}"
            )
        if flange_class not in FlangeClass.__args__:
            raise ValueError(
                f"Invalid flange_class value - the valid values are: {FlangeClass.__args__}"
            )
        if face_type not in FaceType.__args__:
            raise ValueError(
                f"Invalid face_type value - the valid values are: {FaceType.__args__}"
            )
        return True

    @staticmethod
    def get_flange_data(
        nps: Nps, flange_class: FlangeClass, face_type: FaceType
    ) -> tuple[list, list]:
        """get_flange_data

        Return flange and bolt hole data

        Args:
            nps (Nps): nominal pipe size
            flange_class (FlangeClass): class
            face_type (FaceType): face options

        Raises:
            ValueError: Unsupported flange class

        Returns:
            tuple[list, list]: flange_data, bolt_data
        """

        # Read the data table and extract values
        if flange_class == 150:
            flange_data = flange_data_class_150[nps]
            bolt_data = drilling_class_150[nps]
            if face_type == "Raised":
                E = 2 * MM if flange_class <= 300 else 7 * MM
                face_data = [E]
            elif face_type == "Ring":
                face_data = ring_joint_facings_class_150[nps]
        elif flange_class == 300:
            flange_data = flange_data_class_300[nps]
            bolt_data = drilling_class_300[nps]
            face_data = ring_joint_facings_class_300[nps]
            if face_type == "Raised":
                E = 2 * MM if flange_class <= 300 else 7 * MM
                face_data.append([E])
            elif face_type == "Ring":
                face_data = ring_joint_facings_class_300[nps]
        else:
            raise ValueError("Unsupported flange class")

        return (flange_data, bolt_data)

    @staticmethod
    def get_face_section_data(
        nps: Nps, flange_class: FlangeClass, face_type: FaceType
    ) -> tuple[Union[Sketch, None], float]:
        """get_face_section_data

        Return the data required to create the face cross section.

        Args:
            nps (Nps): nominal pipe size
            flange_class (FlangeClass): class
            face_type (FaceType): face options

        Raises:
            ValueError: unsupported flange class
            ValueError: invalid face_type

        Returns:
            tuple[Union[Sketch, None], float]: face_section, height
        """
        if flange_class == 150:
            ring_data = ring_joint_facings_class_150[nps]
        elif flange_class == 300:
            ring_data = ring_joint_facings_class_300[nps]
        else:
            raise ValueError("Unsupported flange class")
        P, E, F, R, K = ring_data[1:6]

        if face_type == "Flat":
            E = 0
        elif face_type == "Raised":
            E = 2 * MM if flange_class <= 300 else 7 * MM
        elif face_type == "Ring":
            E = ring_data[2]
        else:
            raise ValueError(f"face_type {face_type} not supported")

        if face_type == "Flat":
            face_section = None
        else:
            with BuildSketch() as face_builder:
                if face_type in ["Raised", "Ring", "Groove"]:
                    Rectangle(K, E, align=(Align.CENTER, Align.MIN))
                if face_type == "Ring":
                    with BuildSketch(Plane.XZ, mode=Mode.SUBTRACT) as groove:
                        with Locations((P / 2, 0)):
                            Trapezoid(F, E, 90 - 23)
                        fillet(groove.vertices().group_by(Axis.Y)[-1], R)

            face_section = face_builder.sketch

        if face_section is None:
            height = 0.0
        else:
            height = face_section.bounding_box().max.Y

        return (face_section, height)


class SlipOnFlange(Flange):
    """SlipOnFlange

    Slip-On Flange: A slip-on flange has a flat face and is
    intended to slide over the pipe and then be welded in place. It is
    commonly used for low-pressure applications and non-critical systems.

    ASME B16.5 does not provide specific guidelines on the amount of space
    to be left for welding when inserting a pipe into a slip-on flange.
    However, industry best practices generally recommend leaving a gap or
    space of approximately 1/16 inch (1.6 mm) between the end of the pipe
    and the inside face of the slip-on flange.

    This gap allows room for the welding process, specifically for the weld
    bead that will be deposited to join the pipe and the flange. The gap
    provides a sufficient area for proper fusion and penetration during the
    welding process. It also helps prevent excessive buildup of weld
    material that could interfere with the proper fit-up and alignment of
    the pipe and flange.

    When creating pipe terminated with a slip-on flange, the pipe should
    be 1/16 inch shorter (for each end) than the desired end to end length.

    Args:
        nps (Nps): nominal pipe size
        flange_class (FlangeClass): class
        face_type (FaceType, optional): face options. Defaults to "Raised".
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[Align, tuple[Align, Align, Align]], optional):
            object alignment. Defaults to ( Align.CENTER, Align.CENTER, Align.MIN, ).
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.

    Joints:
        "pipe" (Rigid): attachment point for pipe attached to flange
        "face" (Rigid): attachment point on the flange face for other flanges

    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        nps: Nps,
        flange_class: FlangeClass,
        face_type: FaceType = "Raised",
        rotation: RotationLike = (0, 0, 0),
        align: Union[Align, tuple[Align, Align, Align]] = (
            Align.CENTER,
            Align.CENTER,
            Align.MIN,
        ),
        mode: Mode = Mode.ADD,
    ):
        self.nps = nps
        self.flange_class = flange_class
        self.face_type = face_type

        # Validate inputs
        Flange.inputs_are_valid(nps, flange_class, face_type)

        # Get the flange parameters
        flange_data, bolt_data = Flange.get_flange_data(nps, flange_class, face_type)
        O, tf, X, Y, B, r = (flange_data[i] for i in [0, 1, 3, 5, 9, 12])
        W, d_imp, n = bolt_data[1], bolt_data[2], bolt_data[3]
        d = imperial_str_to_float(d_imp)

        # Get the face profile if any
        face_profile, face_thickness = Flange.get_face_section_data(
            nps, flange_class, face_type
        )

        self.od = O  #: Outside diameter
        self.id = B  #: Inside diameter
        self.thickness = Y + face_thickness  #: Overall thickness

        # Create the profile
        with BuildSketch(Plane.XZ) as flange_profile:
            with Locations((0, face_thickness)):
                Rectangle(X, Y, align=(Align.CENTER, Align.MIN))
                Rectangle(O, tf, align=(Align.CENTER, Align.MIN))
            vertices = [
                v
                for v in flange_profile.vertices().group_by(Axis.Y)[-1]
                + flange_profile.vertices().group_by(Axis.Y)[-2]
            ]
            fillet(vertices, (Y - tf) / 4)
            if face_profile is not None:
                add(face_profile)
            Rectangle(
                B,
                Y + face_thickness,
                align=(Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT,
            )

        super().__init__(
            flange_profile.sketch, W, n, d, rotation, tuplify(align, 3), mode
        )

        # Add the joints
        RigidJoint("pipe", self, Location(Plane.YX.offset(-(1 / 16) * IN)))
        RigidJoint("face", self, Location(Plane.XY))


class WeldNeckFlange(Flange):
    """Weld Neck Flange

    Weld Neck Flange: This type of flange is designed with a
    tapered hub and a neck that provides reinforcement and better
    structural integrity. It is typically used in high-pressure and
    high-temperature applications.

    The overall thickness of the flange is stored in the `.thickness`
    instance variable. When sizing a pipe for a given overall length,
    reduce the pipe length by this value for each end with this
    flange type.

    Args:
        nps (Nps): nominal pipe size
        flange_class (FlangeClass): class
        face_type (FaceType, optional): face options. Defaults to "Raised".
        rotation (RotationLike, optional): object rotation. Defaults to (0, 0, 0).
        align (Union[Align, tuple[Align, Align, Align]], optional):
            object alignment. Defaults to ( Align.CENTER, Align.CENTER, Align.MIN, ).
        mode (Mode, optional): combination mode. Defaults to Mode.ADD.

    Joints:
        "pipe" (Rigid): attachment point for pipe attached to flange
        "face" (Rigid): attachment point on the flange face for other flanges
    """

    _applies_to = [BuildPart._tag]

    def __init__(
        self,
        nps: Nps,
        flange_class: FlangeClass,
        face_type: FaceType = "Raised",
        rotation: RotationLike = (0, 0, 0),
        align: Union[Align, tuple[Align, Align, Align]] = (
            Align.CENTER,
            Align.CENTER,
            Align.MIN,
        ),
        mode: Mode = Mode.ADD,
    ):
        self.nps = nps
        self.flange_class = flange_class
        self.face_type = face_type

        # Validate inputs
        Flange.inputs_are_valid(nps, flange_class, face_type)

        # Get the flange parameters
        flange_data, bolt_data = Flange.get_flange_data(nps, flange_class, face_type)
        O, tf, X, Ah, Y, B, r = [flange_data[i] for i in [0, 1, 3, 4, 7, 11, 12]]
        W, d_imp, n = bolt_data[1], bolt_data[2], bolt_data[3]
        d = imperial_str_to_float(d_imp)

        # Get the face profile if any
        face_profile, face_thickness = Flange.get_face_section_data(
            nps, flange_class, face_type
        )

        self.od = O  #: Outside diameter
        self.id = B  #: Inside diameter
        self.thickness = Y + face_thickness  #: Overall thickness

        trap_angle = degrees(atan2(Y - tf, (X - Ah) / 2))
        # Create the basic shape
        with BuildSketch(Plane.XZ) as flange_profile:
            with Locations((0, face_thickness)):
                Rectangle(O, tf, align=(Align.CENTER, Align.MIN))
            with Locations((0, face_thickness + tf)):
                Trapezoid(X, Y - tf, trap_angle, align=(Align.CENTER, Align.MIN))
            vertices = [v for v in flange_profile.vertices().group_by(Axis.Y)[-2]]
            fillet(vertices, tf / 6)  # What is the correct radius?
            vertices = flange_profile.vertices().group_by(Axis.Y)[-1]
            c = (Ah - B) / 2.5
            chamfer(vertices, c)
            add(face_profile)
            Rectangle(
                B,
                Y + face_thickness,
                align=(Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT,
            )

        super().__init__(
            flange_profile.sketch, W, n, d, rotation, tuplify(align, 3), mode
        )

        # Add the joints
        RigidJoint("pipe", self, Location(Plane.XY.offset(Y + face_thickness)))
        RigidJoint("face", self, Location(Plane.YX))
