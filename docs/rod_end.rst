#############################
rod_end - parametric rod ends
#############################
A rod end - also called a ball joint head or a spherical rod end - carries a
radial spherical plain bearing in an eye at one end and a threaded shank at the
other, and is the standard way to terminate a link in a mechanism. The
``rod_end`` module creates them to DIN ISO 12240-4 (DIN 648) dimension
series K, in both the tapped and the threaded stem version.

Rod ends are created as build123d Compounds of three labelled solids -
``Housing``, ``BearingSocket`` and ``InternalRing`` - each carrying its
``bd_materials`` material, with accurate external dimensions and a simplified
interior. The ball's spherical seat is modelled, and so is the cone that
carries the eye into the shank, but neither variant's thread form is: the
tapped hole is drawn at its basic minor diameter and the stem at its nominal
diameter.

Here is a list of the classes (and rod end types) provided:

* :ref:`RodEnd <rod_end>` - the base rod end class
	* ``FemaleThreadRodEnd``: DIN648K
	* ``MaleThreadRodEnd``: DIN648K

See :ref:`Extending the fastener sub-package <extending>` (these instructions
apply to rod ends as well) for guidance on how to add new sizes or entirely
new types of rod ends.

The following example creates one of each and reports what they are:

.. code-block:: python

	from build123d import *
	from bd_warehouse.rod_end import FemaleThreadRodEnd, MaleThreadRodEnd

	tapped = FemaleThreadRodEnd(size="M10")
	print(tapped.thread_size)           # M10
	print(tapped.bore_diameter)         # 10.0
	print(tapped.overall_length)        # 57.0
	print(tapped.thread_depth)          # 20.0
	print(tapped.static_load_rating)    # 1.4 kN

	stem = MaleThreadRodEnd(size="M10")
	print(stem.overall_length)          # 62.0
	print(stem.shank_diameter)          # 10.0 - the stem is the thread
	print(stem.thread_length)           # 28.0

Sizes are named by the rod end's **bore**, following the convention the
``bearing`` module uses, so ``"M10"`` is the 10 mm bore size. The shank thread
does not always share that number - the 25 mm bore size is threaded M24x2 -
so read it from ``thread_size`` rather than from the size name. The two
variants share a bore's eye and bearing but not its thread: the 20 mm bore is
tapped M20 and stemmed M20x1.5. The tapped type runs from 5 mm to 35 mm bore,
the threaded stem from 5 mm to 30 mm.

**********
Geometry
**********
The origin is the ball centre, the bore runs along the X axis and the shank
runs along -Z, so the shank's far end lies at ``z = -center_to_end``. Two
joints are provided:

* ``pin`` - a ``RevoluteJoint`` on the bore axis, for the pin the rod end
  swivels on
* ``thread`` - a ``RigidJoint`` at the end of the shank: the tapped type's
  threaded face, or the end of the threaded stem

``examples/rod_ends.py`` shows both size ranges, a rod end cut open so the
socket and ball inside are visible, and a link assembled through these joints.
Run it with the OCP CAD Viewer running:

.. code-block:: bash

	python examples/rod_ends.py

.. _rod_end:

*******
RodEnd
*******
As the base class of all other rod end classes, all of the rod end classes
share the same interface as follows:

.. py:module:: rod_end

.. autoclass:: RodEnd

******************
FemaleThreadRodEnd
******************
.. autoclass:: FemaleThreadRodEnd

****************
MaleThreadRodEnd
****************
.. autoclass:: MaleThreadRodEnd

*******************
Dimensional sources
*******************
Three independent sources are used and cross-checked against each other:

* The tapped type's body, thread and collar come from the JW Winco / Ganter
  `DIN 648 rod end bearings, tapped type <https://www.jwwinco.com/en-us/products/Ball-joint-heads/Ball-joint-heads/DIN-648-Steel-Self-Lubricating-Rod-End-Bearings-Tapped-Type>`_
  metric catalogue table, which prints d1, d2, b1, b2, d3, d4, d5, d6, l1, l2,
  A/F, t, w and C0 for 13 bore sizes from 5 mm to 35 mm.
* The threaded stem version comes from the same catalogue's
  `DIN 648 rod end bearings, with threaded stem <https://www.jwwinco.com/en-us/products/3.6-Moving-Transferring-Connecting-with-Joints-Couplings-and-Gears/Ball-joint-heads/DIN-648-Steel-Self-Lubricating-Rod-End-Bearings-With-Threaded-Stem>`_
  sheet, which prints d1, d2, l3, b1, b2, d3, d4, l1, l2, w and C0 for 12 bore
  sizes from 5 mm to 30 mm. It gives no shank diameter because there is
  nothing to give: the stem is threaded rod of diameter d2, which is what its
  front view measures and what the catalogue's own l1 - l3 chain confirms.
* The spherical plain bearing inside comes from ISO 12240-1:1998 table 4,
  dimension series K, whose own note states that the bearings of that series
  are the ones incorporated in the rod ends of ISO 12240-4:1998 table 5. Its
  D is the eye's press-fit seat, and its B, C and d1 agree row for row with
  both sheets' b1, b2 and d3.

No source prints the ball's spherical diameter dk for a rod end, but the
internal ring is a sphere truncated to b1 whose cut faces measure d3, which
closes it; the results agree with ISO 12240-1 table 4 to within its rounding.

Three things are worth knowing about the tabulated data:

* The tapped sheet's 35 mm bore row departs from ISO 12240-1 series K, with a
  narrower outer ring and smaller inner-ring end faces, and the threaded stem
  has no 35 mm size at all. The catalogue is what is manufactured, so it is
  what the module tabulates, and the test suite records the divergence rather
  than hiding it.
* The threaded stem sheet prints d3 = 29.6 at the 25 mm bore where the tapped
  sheet and ISO 12240-1 both print 29.5. It is the same ring in the same eye,
  so 29.5 is tabulated for both.
* The catalogue's CETOP thread variants (M4, M10x1.25, M12x1.25, M16x1.5,
  M20x1.5 and M27x2, available only in minimum quantities) are omitted; each
  shares its body with a standard size that is included.

The blend
=========
Neither sheet dimensions how the eye is carried into the shank, but both draw
it. The eye's flanks run the whole height of the head, b2 apart, so nothing
stands out alongside the eye; outside them the body is a cone of half angle
``BLEND_ANGLE`` tangent to the eye's outer circle. Tangency is why the drawn
flank is straight and carries no radius. Below the head the flanks flare out
at the same angle wherever the shank is the thicker of the two - which is
every tapped size, and the threaded stem's from the 14 mm bore up.
``blend_tangent_station``, ``blend_tangent_radius``, ``blend_base`` and
``flank_flare_station`` report the stations that follow.

A third drawing - `mbo Osswald's own for the series K male thread
<https://www.mbo-osswald.de/en/shop/rod-ends-din-iso-12240-4-din-648-k-series-standard-version-male-thread>`_
- draws the same construction, and all three measure the cone tangent to the
eye's circle to within the width of their own lines.

Four readings bear on the angle: the threaded stem's front view measures
30.0 deg, solving that sheet's own l1 - l3 chain for the angle gives 28.7 deg
to 30.2 deg on ten of its twelve sizes, the tapped type's front view measures
31.5 deg, and mbo's drawing measures 31.4 deg. They span about 1.5 deg either
way, so 30 is taken as the value - the round number a draughtsman picks, what
the sheet drawn at a known size measures, and the one that puts the cone's
apex exactly one eye diameter below the ball centre. ``BLEND_ANGLE`` is a
class attribute for anyone who would rather match a particular manufacturer.

The tapped sheet alone does not settle the construction either - at its
proportions a fixed angle and a cone through (d5/2, -d4/2) agree to within a
millimetre - but the threaded stem's thin stem separates the two by 5 mm and
picks the fixed angle.

Both variants are modelled as the self-lubricating, maintenance-free type: a
sintered bronze socket and no lubrication port. A manufacturer's "standard"
greased version, such as the one mbo Osswald draws, carries a lubrication
nipple on the head that is not modelled here.

That leaves the height of the tapped type's wrench collar, which nothing
dimensions and nothing derives. It is the constructor's ``collar_height``
parameter, with a default measured off the same drawing - override it if a
particular manufacturer's part needs to match more closely. The threaded stem
needs no such parameter: it has no collar, and the sheet's photograph shows
none.
