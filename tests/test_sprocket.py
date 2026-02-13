"""
Parametric Sprockets Unit Tests

name: test_sprocket.py
by:   Gumyr
date: Feb 13th 2026

desc: Unit tests for the sprocket sub-package of bd_warehouse
"""

import unittest
from build123d.build_common import IN, MM
from bd_warehouse.sprocket import Sprocket


class TestParsing(unittest.TestCase):
    """Validate input parsing of the Sprocket and Chain classes"""

    def test_sprocket_input_parsing(self):
        """Validate Sprocket input validation"""
        with self.assertRaises(ValueError):  # Insufficient tooth count
            Sprocket(num_teeth=2)
        with self.assertRaises(ValueError):  # Invalid chain
            Sprocket(num_teeth=32, chain_pitch=4, roller_diameter=5)


class TestSprocketShape(unittest.TestCase):
    """Validate the Sprocket object"""

    def test_flat_sprocket_shape(self):
        """Normal Sprockets"""
        sprocket = Sprocket(
            num_teeth=32,
            bolt_circle_diameter=104 * MM,
            num_mount_bolts=4,
            mount_bolt_diameter=8 * MM,
            bore_diameter=80 * MM,
        )
        self.assertTrue(sprocket.is_valid)
        self.assertEqual(len(sprocket.edges()), 591)
        self.assertAlmostEqual(sprocket.pitch_radius, 64.78458745735234, 4)
        self.assertAlmostEqual(sprocket.outer_radius, 66.76896245735234, 4)
        self.assertAlmostEqual(sprocket.pitch_circumference, 407.0535680437272, 4)

    def test_spiky_sprocket_shape(self):
        """Create sprockets with no flat/chamfered top"""
        sprocket = Sprocket(
            num_teeth=16, chain_pitch=0.5 * IN, roller_diameter=0.49 * IN
        )
        self.assertTrue(sprocket.is_valid)
        self.assertEqual(len(sprocket.edges()), 144)
        self.assertAlmostEqual(sprocket.pitch_radius, 32.54902618631712, 4)
        self.assertAlmostEqual(sprocket.outer_radius, 33.19993997888148, 4)
        self.assertAlmostEqual(sprocket.pitch_circumference, 204.51156309687133, 4)


class TestSprocketMethods(unittest.TestCase):
    """Sprocket class methods"""

    def test_sprocket_pitch_radius(self):
        """Pitch radius verification"""
        self.assertAlmostEqual(
            Sprocket.sprocket_pitch_radius(32, 0.5 * IN), 64.78458745735234, 4
        )

    def test_sprocket_circumference(self):
        """Pitch circumference verification"""
        self.assertAlmostEqual(
            Sprocket.sprocket_circumference(32, 0.5 * IN), 407.0535680437272, 4
        )


if __name__ == "__main__":
    unittest.main()
