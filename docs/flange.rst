..
    bd_warehouse/flange

    by:   Gumyr
    date: June 12th 2023

    desc: This is the documentation for b3d_warehouse/flange.

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

########################################
flange - standardized parametric flanges
########################################

.. highlight:: python

.. image:: assets/pipe_logo.png
	:alt: pipe_logo

Flanges are mechanical components used in piping systems to connect pipes,
valves, and equipment. They provide a secure and leak-tight connection by
bolting two flange faces together. Flanges allow for easy assembly and
disassembly, enabling maintenance and modifications in the system. They are
available in various materials, sizes, and pressure ratings to suit different
applications. Flanges also provide flexibility by allowing different types of
connections, such as welding, threaded, or flanged connections. They play a
critical role in industries like oil and gas, chemical, and power generation,
ensuring the safe and efficient operation of piping systems by facilitating
proper alignment, support, and sealing of the connected components.

.. code-block:: python

  from build123d import *
  from bd_warehouse.pipe import Pipe

  stainless_pipe = Pipe(
      nps="2 1/2",
      material="stainless",
      identifier="10S",
      path=Edge.make_line((0, 0, 0), (5 * FT, 0, 0)),
  )

  with BuildPart() as copper_pipes:
      with BuildLine(Plane.XZ):
          l1 = Line((0, 0), (0, 6 * FT))
          l2 = Line(l1 @ 1 + (0, -3 * IN), l1 @ 1 + (1 * FT, -3 * IN))
          l3 = RadiusArc(l2 @ 1, l2 @ 1 + (0, -3 * FT), 1.5 * FT)
          l4 = Line(l3 @ 1, l3 @ 1 + (-1 * FT, 0))
      Pipe(nps="6", material="copper", identifier="K")

There are three parameters that required to define a pipe: nps, material, and
identifier.

nps
---

NPS stands for "Nominal Pipe Size." It is a standard designation used to
indicate the approximate inside diameter (ID) of a pipe or fitting, typically
for industrial and plumbing applications. NPS is expressed as a numerical value
without any unit of measurement.

It's important to note that NPS does not directly correspond to the actual
physical dimensions of the pipe. Instead, it provides a convenient reference
for pipe sizing and selection purposes. The actual outside diameter (OD) and
wall thickness of a pipe can vary depending on the specific material,
manufacturing standards, and application requirements.

NPS values are based on a standardized system and are associated with a
specific set of dimensions and tolerances provided by various standards, such
as ASME B36.10 for carbon and alloy steel pipes and ASME B36.19 for stainless
steel pipes.

When specifying or discussing pipe sizes, NPS is commonly used to identify the
general size range of a pipe, and further details such as OD and wall thickness
are provided separately. It serves as a convenient way to communicate and
compare pipe sizes within the industry, facilitating the selection and
compatibility of pipes, fittings, and related components.

Valid NPS values are strings in the form: "1/8", "1/4", "3/8", "1/2", "3/4", "1", 
"1 1/4", "1 1/2", "2", "2 1/2", "3", "4", etc.

material & identifier
---------------------

The dimensions of pipes vary by the pipe material as described in the following
Specifications section.  

The following table defines the available materials and the valid identifier's
for each material:

+-------------+---------------------------------+----------------------------------------------------------------+
| material    | description                     | identifier or schedule                                         |
+=============+=================================+================================================================+
| "abs"       | drainage or vent pipes          | "40"                                                           |
+-------------+---------------------------------+----------------------------------------------------------------+
| "copper"    | plumbing pipes                  | "K", "L", "M"                                                  |
+-------------+---------------------------------+----------------------------------------------------------------+
| "iron"      | iron/steel pipes                | "STD", "XS", "XXS"                                             |
+-------------+---------------------------------+----------------------------------------------------------------+
| "pvc"       | water pipes                     | "40", "80"                                                     |
+-------------+---------------------------------+----------------------------------------------------------------+
| "stainless" | austenitic stainless steel pipe | "5S", "10S", "20S", "40S", "80S"                               |
+-------------+---------------------------------+----------------------------------------------------------------+
| "steel"     | steel pipes                     | "10", "20", "30", "40", "60", "80", "100", "120", "140", "160" |
+-------------+---------------------------------+----------------------------------------------------------------+

Joints
------

All pipes are created with two ``RigidJoint``: ``inlet`` and ``outlet``.  These joints 
are positioned in the center of the pipe and oriented such that connecting the outlet
of one pipe to the inlet of another will align them appropriately.


Specifications
--------------

The pipes created by this package are based off the following standards:

  * ASME B16.5 is a standard issued by the American Society of Mechanical Engineers
    (ASME) that provides specifications for pipe flanges and flanged fittings. It
    covers a wide range of flange types, sizes, materials, and pressure ratings.
    ASME B16.5 establishes the dimensions, tolerances, and technical requirements
    for flanges used in various industries, including oil and gas, chemical, and
    power generation. The standard ensures the compatibility, integrity, and
    performance of flanged connections, facilitating proper alignment, sealing, and
    strength of the joint. It serves as a reference for manufacturers, engineers,
    and designers in the selection, design, and installation of flanges, promoting
    safe and reliable operation of piping systems.
