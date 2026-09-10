import unittest

from cycloid_analyzer.cycloid import CycloidParameters, generate_cycloid_points


class CycloidTests(unittest.TestCase):
    def test_generated_cycloid_starts_and_ends_at_anchor_points(self):
        start = (0.0, 0.0)
        end = (100.0, 0.0)
        points = generate_cycloid_points(start, end, CycloidParameters(radius=10.0, frequency=2.0))
        self.assertEqual(points[0], start)
        self.assertAlmostEqual(points[-1][0], end[0], places=6)
        self.assertAlmostEqual(points[-1][1], end[1], places=6)

    def test_zero_length_drag_produces_single_point(self):
        start = (12.0, 8.0)
        points = generate_cycloid_points(start, start, CycloidParameters())
        self.assertEqual(points, [start])

    def test_frequency_changes_shape_but_not_sample_count(self):
        slow = generate_cycloid_points((0.0, 0.0), (100.0, 0.0), CycloidParameters(frequency=1.0))
        fast = generate_cycloid_points((0.0, 0.0), (100.0, 0.0), CycloidParameters(frequency=3.0))
        self.assertEqual(len(slow), len(fast))
        self.assertNotEqual(slow[10], fast[10])


if __name__ == "__main__":
    unittest.main()

