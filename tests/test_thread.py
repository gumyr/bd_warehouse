"""

Thread Unit Tests

name: thread_tests.py
by:   Gumyr
date: June 22th 2023

desc: Unit tests for the fastener sub-package of bd_warehouse

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

import random
import unittest
from bd_warehouse.thread import *
from build123d import GeomType
from build123d.operations_part import section


class TestSupportFunctions(unittest.TestCase):
    def test_is_safe(self):
        self.assertTrue(is_safe("1 1/8"))
        self.assertFalse(is_safe("rm -rf *"))

    def test_imperial_str_to_float(self):
        self.assertAlmostEqual(imperial_str_to_float("1 1/2"), 1.5 * IN)
        self.assertEqual(imperial_str_to_float("rm -rf *"), "rm -rf *")


class TestThread(unittest.TestCase):
    def test_parsing(self):
        with self.assertRaises(ValueError):
            Thread(
                apex_radius=10,
                apex_width=2,
                root_radius=8,
                root_width=3,
                pitch=2,
                length=20,
                end_finishes=("not", "supported"),
            )

    def test_long_trapezoidal_thread_does_not_recurse(self):
        """A CNC-length detailed thread should not recurse while copying joints."""
        thread = TrapezoidalThread(
            7.8 * MM,
            2 * MM,
            30,
            2400,
            starts=4,
            end_finishes=("chamfer", "chamfer"),
        )

        self.assertTrue(thread.is_valid)


class TestWhitworthThread(unittest.TestCase):
    def test_full_form_profile(self):
        """Full-form profiles have the ISO Whitworth dimensions and three arcs."""
        pitch = 25.4 / 14
        for external in (True, False):
            with self.subTest(external=external):
                thread = WhitworthThread(
                    major_diameter=20.955,
                    pitch=pitch,
                    length=4 * pitch,
                    external=external,
                    simple=True,
                )
                self.assertAlmostEqual(
                    thread.fundamental_triangle_height, 0.960491 * pitch
                )
                self.assertAlmostEqual(thread.thread_height, 0.640327 * pitch)
                self.assertAlmostEqual(thread.rounding_radius, 0.137329 * pitch)
                circular_edges = [
                    edge
                    for edge in thread.thread_profile.edges()
                    if edge.geom_type == GeomType.CIRCLE
                ]
                self.assertEqual(len(circular_edges), 3)
                for edge in circular_edges:
                    self.assertAlmostEqual(edge.radius, thread.rounding_radius)

                profile_box = thread.thread_profile.bounding_box()
                profile_tip = profile_box.max.Y if external else profile_box.min.Y
                expected_tip = thread.thread_height * (1 if external else -1)
                self.assertAlmostEqual(profile_tip, expected_tip)

    def test_end_finishes(self):
        """All finishes support full/truncated orientations and thread hands."""
        pitch = 25.4 / 14
        for crest_truncation in (0.0, 0.2):
            for external in (True, False):
                for hand in ("right", "left"):
                    for finish in ("raw", "fade", "square", "chamfer"):
                        with self.subTest(
                            crest_truncation=crest_truncation,
                            external=external,
                            hand=hand,
                            end_finish=finish,
                        ):
                            thread = WhitworthThread(
                                major_diameter=20.955,
                                pitch=pitch,
                                length=3.2 * pitch,
                                external=external,
                                hand=hand,
                                end_finishes=(finish, finish),
                                crest_truncation=crest_truncation,
                            )
                            self.assertTrue(thread.is_valid)

    def test_truncated_profiles(self):
        """The profile split can cross either the crest arc or the flanks."""
        pitch = 25.4 / 14
        for external in (True, False):
            for crest_truncation, circular_edge_count in ((0.05, 4), (0.2, 2)):
                with self.subTest(external=external, crest_truncation=crest_truncation):
                    thread = WhitworthThread(
                        major_diameter=20.955,
                        pitch=pitch,
                        length=4 * pitch,
                        external=external,
                        crest_truncation=crest_truncation,
                        simple=True,
                    )
                    circular_edges = [
                        edge
                        for edge in thread.thread_profile.edges()
                        if edge.geom_type == GeomType.CIRCLE
                    ]
                    self.assertEqual(len(circular_edges), circular_edge_count)
                    profile_box = thread.thread_profile.bounding_box()
                    profile_tip = profile_box.max.Y if external else profile_box.min.Y
                    direction = 1 if external else -1
                    self.assertAlmostEqual(
                        profile_tip,
                        direction * (thread.thread_height - crest_truncation),
                    )
                    self.assertAlmostEqual(
                        thread.tooth_height,
                        thread.thread_height - crest_truncation,
                    )

    def test_parsing(self):
        with self.assertRaises(ValueError):
            WhitworthThread(20.955, 25.4 / 14, 10, hand="righty")
        with self.assertRaises(ValueError):
            WhitworthThread(20.955, 25.4 / 14, 10, end_finishes=("raw", "unsupported"))
        with self.assertRaises(ValueError):
            WhitworthThread(20.955, 25.4 / 14, 10, crest_truncation=-0.1)
        with self.assertRaises(ValueError):
            WhitworthThread(20.955, 1, 10, crest_truncation=0.640327)


class TestBSPPThread(unittest.TestCase):
    def test_sizes(self):
        """ISO 228-1 defines 24 G-series sizes from G1/16 through G6."""
        sizes = BSPPThread.sizes()
        self.assertEqual(len(sizes), 24)
        self.assertEqual(sizes[0], "G1/16")
        self.assertEqual(sizes[-1], "G6")
        for size in sizes:
            with self.subTest(size=size):
                thread = BSPPThread(size, length=5, simple=True)
                self.assertGreater(thread.major_diameter, thread.minor_diameter)
                self.assertGreater(thread.pitch, 0)

    def test_g_half_external_tolerances(self):
        """G1/2 external classes A and B use the ISO 228 limits."""
        class_a = BSPPThread("G1/2", length=8, simple=True)
        self.assertEqual(class_a.designation, "G1/2A")
        self.assertEqual(class_a.tpi, 14)
        self.assertAlmostEqual(class_a.pitch, 25.4 / 14)
        self.assertAlmostEqual(class_a.basic_major_diameter, 20.955)
        self.assertAlmostEqual(class_a.basic_pitch_diameter, 19.793)
        self.assertAlmostEqual(class_a.basic_minor_diameter, 18.631)
        self.assertEqual(class_a.pitch_diameter_limits, (19.651, 19.793))
        self.assertEqual(class_a.major_diameter_limits, (20.671, 20.955))
        self.assertIsNone(class_a.minor_diameter_limits)

        class_b = BSPPThread(
            "G 1/2", length=8, tolerance_class="b", hand="left", simple=True
        )
        self.assertEqual(class_b.designation, "G1/2B LH")
        self.assertEqual(class_b.pitch_diameter_limits, (19.509, 19.793))
        self.assertEqual(class_b.major_diameter_limits, (20.671, 20.955))

    def test_g_half_internal_tolerances(self):
        """Internal G threads have one positive tolerance class."""
        thread = BSPPThread('1/2"', length=8, external=False, simple=True)
        self.assertEqual(thread.designation, "G1/2")
        self.assertEqual(thread.pitch_diameter_limits, (19.793, 19.935))
        self.assertIsNone(thread.major_diameter_limits)
        self.assertEqual(thread.minor_diameter_limits, (18.631, 19.172))

    def test_thread_solids(self):
        """Truncated external and internal BSPP profiles produce valid solids."""
        for external in (True, False):
            with self.subTest(external=external):
                crest_diameter = 20.671 if external else 19.172
                thread = BSPPThread(
                    "G1/2",
                    length=8,
                    external=external,
                    end_finishes=("fade", "square"),
                    crest_diameter=crest_diameter,
                )
                self.assertTrue(thread.is_valid)
                self.assertAlmostEqual(thread.crest_diameter, crest_diameter)

    def test_parsing(self):
        with self.assertRaises(ValueError):
            BSPPThread("G7", length=8)
        with self.assertRaises(ValueError):
            BSPPThread("G1/2", length=8, tolerance_class="C")
        with self.assertRaises(ValueError):
            BSPPThread("G1/2", length=8, tolerance_class=1)
        with self.assertRaises(ValueError):
            BSPPThread("G1/2", length=8, external=False, tolerance_class="A")
        with self.assertRaises(ValueError):
            BSPPThread("G1/2", length=8, crest_diameter=20.670)
        with self.assertRaises(ValueError):
            BSPPThread("G1/2", length=8, external=False, crest_diameter=19.173)


class TestIsoThread(unittest.TestCase):
    end_finishes = ["raw", "fade", "square", "chamfer"]

    def test_exterior_thread(self):
        """Simple validity check for an exterior thread"""

        for end0 in TestIsoThread.end_finishes:
            for end1 in TestIsoThread.end_finishes:
                length = (1 + random.random() * 9) * MM
                with self.subTest(end0=end0, end1=end1, length=length):
                    thread = IsoThread(
                        major_diameter=6 * MM,
                        pitch=1 * MM,
                        length=length,
                        external=True,
                        end_finishes=(end0, end1),
                        hand="right",
                    )
                    self.assertTrue(thread.is_valid)

    def test_interior_thread(self):
        """Simple validity check for an interior thread"""

        for end0 in TestIsoThread.end_finishes:
            for end1 in TestIsoThread.end_finishes:
                with self.subTest(end0=end0, end1=end1):
                    thread = IsoThread(
                        major_diameter=6 * MM,
                        pitch=1 * MM,
                        length=8 * MM,
                        external=False,
                        end_finishes=(end0, end1),
                        hand="left" if end0 == end1 else "right",
                    )
                    self.assertTrue(thread.is_valid)

    def test_parsing(self):
        with self.assertRaises(ValueError):
            IsoThread(major_diameter=5, pitch=1, length=5, hand="righty")
        with self.assertRaises(ValueError):
            IsoThread(
                major_diameter=5, pitch=1, length=5, end_finishes=("not", "supported")
            )

    # def test_simple(self):
    #     thread = IsoThread(
    #         major_diameter=6 * MM, pitch=1 * MM, length=8 * MM, simple=True
    #     )
    #     self.assertTrue(thread.wrapped.IsNull())
    def test_simple(self):
        thread = IsoThread(
            major_diameter=6 * MM, pitch=1 * MM, length=8 * MM, simple=True
        )

        try:
            wrapped = thread.wrapped
        except AssertionError:
            # New build123d: wrapped asserts when no geometry exists
            self.assertTrue(True)
        else:
            # Old build123d: wrapped exists but is null
            self.assertTrue(wrapped.IsNull())


class TestAcmeThread(unittest.TestCase):
    def test_exterior_thread(self):
        """Simple validity check for an exterior thread"""

        acme_thread = AcmeThread(
            size="1 1/4",
            length=1 * IN,
            external=True,
        )
        self.assertTrue(acme_thread.is_valid)

    def test_interior_thread(self):
        """Simple validity check for an interior thread"""

        acme_thread = AcmeThread(
            size="1 1/4",
            length=1 * IN,
            external=False,
        )
        self.assertTrue(acme_thread.is_valid)

    def test_sizes(self):
        """Validate sizes list if created"""
        self.assertGreater(len(AcmeThread.sizes()), 0)

    def test_parsing(self):
        with self.assertRaises(ValueError):
            AcmeThread(size="1 1/4", length=1 * IN, external=False, hand="righty")
        with self.assertRaises(ValueError):
            AcmeThread(size="1.25", length=1 * IN)
        with self.assertRaises(ValueError):
            AcmeThread(size="1 1/4", length=1 * IN, end_finishes=("not", "supported"))


class TestMetricTrapezoidalThread(unittest.TestCase):
    def test_exterior_thread(self):
        """Simple validity check for an exterior thread"""

        trap_thread = MetricTrapezoidalThread(
            size="8x1.5",
            length=10 * MM,
            external=True,
        )
        self.assertTrue(trap_thread.is_valid)

    def test_interior_thread(self):
        """Simple validity check for an interior thread"""

        trap_thread = MetricTrapezoidalThread(
            size="95x18",
            length=100 * MM,
            external=False,
        )
        self.assertTrue(trap_thread.is_valid)

    def test_parsing(self):
        with self.assertRaises(ValueError):
            MetricTrapezoidalThread(size="8x1", length=50 * MM)

    def test_sizes(self):
        """Validate sizes list if created"""
        self.assertGreater(len(MetricTrapezoidalThread.sizes()), 0)

    def test_thread_angle(self):
        """Check that the thread angle is relative to thread axis"""
        mtt = MetricTrapezoidalThread("8x1.5", 2)
        sect = section(mtt, section_by=Plane.YZ)
        angled_edges = sect.edges().group_by(Axis.Y)[-2]
        angle = (angled_edges[0] % 0).get_signed_angle(angled_edges[1] % 0)
        self.assertAlmostEqual(angle, 150, 5)


class TestPlasticBottleThread(unittest.TestCase):
    def test_exterior_thread(self):
        """Simple validity check for an exterior thread"""

        bottle_thread = PlasticBottleThread(
            size="M38SP444",
            external=True,
        )
        self.assertTrue(bottle_thread.is_valid)

    def test_pco1881_threads(self):
        """PCO1881 supports both cap and bottle thread orientations."""
        for external in (True, False):
            bottle_thread = PlasticBottleThread(
                size="28", bottle_type="pco1881", external=external
            )
            self.assertTrue(bottle_thread.is_valid)
            self.assertEqual(bottle_thread.bottle_type, "pco1881")
            self.assertAlmostEqual(bottle_thread.pitch, 2.7)
            self.assertAlmostEqual(bottle_thread.diameter, 27.4)

    def test_bottle_type_parsing(self):
        """Reject unknown bottle thread standards and sizes."""
        with self.assertRaises(ValueError):
            PlasticBottleThread(size="28", bottle_type="unknown")
        with self.assertRaises(ValueError):
            PlasticBottleThread(size="30", bottle_type="pco1881")

    def test_exterior_left_thread(self):
        """Simple validity check for an exterior thread"""

        bottle_thread = PlasticBottleThread(size="M38SP444", external=True, hand="left")
        self.assertTrue(bottle_thread.is_valid)

    def test_interior_thread(self):
        """Simple validity check for an interior thread"""

        bottle_thread = PlasticBottleThread(
            size="L18SP400", external=False, manufacturing_compensation=0.2
        )
        self.assertTrue(bottle_thread.is_valid)

    def test_parsing(self):
        """Validate sizes"""
        with self.assertRaises(ValueError):
            PlasticBottleThread(size="Q12SP100")
        with self.assertRaises(ValueError):
            PlasticBottleThread(size="M37SP444")
        with self.assertRaises(ValueError):
            PlasticBottleThread(size="L12XX100")
        with self.assertRaises(ValueError):
            PlasticBottleThread(size="L12SP12")
        with self.assertRaises(ValueError):
            PlasticBottleThread(size="M38SP444", hand="righty")


if __name__ == "__main__":
    unittest.main(failfast=True)
