import unittest

from cycloid_analyzer.comparison import compare_paths


class ComparisonTests(unittest.TestCase):
    def test_identical_paths_compare_as_perfect_match(self):
        path = [(0.0, 0.0), (5.0, 5.0), (10.0, 10.0)]
        metrics = compare_paths(path, path)
        self.assertAlmostEqual(metrics["average_distance"], 0.0)
        self.assertAlmostEqual(metrics["rmse"], 0.0)
        self.assertAlmostEqual(metrics["max_distance"], 0.0)
        self.assertAlmostEqual(metrics["path_length_ratio"], 1.0)
        self.assertAlmostEqual(metrics["similarity_score"], 1.0)

    def test_offset_paths_produce_non_zero_distances(self):
        reference = [(0.0, 0.0), (10.0, 0.0)]
        candidate = [(0.0, 5.0), (10.0, 5.0)]
        metrics = compare_paths(reference, candidate)
        self.assertGreater(metrics["average_distance"], 0.0)
        self.assertGreater(metrics["rmse"], 0.0)
        self.assertGreater(metrics["max_distance"], 0.0)
        self.assertAlmostEqual(metrics["path_length_ratio"], 1.0)
        self.assertLess(metrics["similarity_score"], 1.0)

    def test_short_paths_return_zeroed_metrics(self):
        metrics = compare_paths([(0.0, 0.0)], [(1.0, 1.0)])
        self.assertEqual(
            metrics,
            {
                "average_distance": 0.0,
                "rmse": 0.0,
                "max_distance": 0.0,
                "path_length_ratio": 0.0,
                "similarity_score": 0.0,
            },
        )

    def test_small_sample_count_is_clamped(self):
        reference = [(0.0, 0.0), (10.0, 0.0)]
        candidate = [(0.0, 0.0), (10.0, 0.0)]
        metrics = compare_paths(reference, candidate, sample_count=1)
        self.assertAlmostEqual(metrics["average_distance"], 0.0)
        self.assertAlmostEqual(metrics["path_length_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
