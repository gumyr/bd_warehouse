..
    bd_warehouse/pipe

    by:   Gumyr
    date: June 11th 2023

    desc: This is the documentation for b3d_warehouse/pipe.

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

####################################
pipe - standardized parametric pipes
####################################

.. highlight:: python

.. image:: assets/pipe_logo.png
	:alt: pipe_logo

Pipes are a critical component of many industrial and chemical processing facilities.
The pipe sub-package provides Pipe and PipeSection classes that make the creation of
industry standard sized pipes easy by providing an API that just requires selection
from commonly used parameters.


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

.. _nps:

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

.. py:module:: pipe

.. autoclass:: Nps

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
