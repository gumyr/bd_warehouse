########################################
bushing - parametric bushings
########################################

The ``bushing`` module provides generic parametric bushings whose dimensions are
supplied directly rather than selected from an ISO or DIN table.

Hex-Flanged Eccentric Bushings
==============================

``HexFlangedEccentricBushing`` creates a cylindrical mounting body with a
wrenchable hex flange and an eccentric through bore. ``hex_size`` is measured
across flats. ``body_length`` excludes the flange, so the overall length is
``body_length + flange_height``.

The body and flange are centered on the object's local Z axis and the bore is
offset in the positive X direction. The ``bottom`` rigid joint is at the center
of the underside of the hex flange. The ``top`` rigid joint is on the eccentric
bore axis at the top of the flange.

.. code-block:: python

    from bd_warehouse.bushing import HexFlangedEccentricBushing

    bushing = HexFlangedEccentricBushing(
        bore_diameter=8,
        body_diameter=12,
        body_length=16,
        flange_height=4,
        hex_size=17,
        eccentricity=1,
    )

This class describes a geometric component family and does not claim compliance
with an ISO, DIN, or manufacturer dimensional standard.

.. py:module:: bushing

.. autoclass:: HexFlangedEccentricBushing
