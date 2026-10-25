from pathlib import Path
import tempfile
import unittest
import numpy as np
from density_explain.datasets import geographic_to_local_meters, load_usgs_csv, mock_blobs, mock_moons, mock_rings


class DatasetTests(unittest.TestCase):
    def test_mock_determinism_and_finite_shapes(self):
        for generator in [mock_blobs, mock_moons, mock_rings]:
            X = generator(7)
            np.testing.assert_array_equal(X, generator(7))
            self.assertEqual(X.shape[1], 2)
            self.assertTrue(np.isfinite(X).all())
            self.assertFalse(np.array_equal(X, generator(19)))

    def test_projection_origin_and_units(self):
        X = geographic_to_local_meters([34, 34.001], [-118, -118])
        np.testing.assert_array_equal(X[0], [0, 0])
        self.assertAlmostEqual(X[1, 1], 111.19508023, places=5)
        self.assertEqual(X[1, 0], 0)

    def test_projection_rejects_bad_coordinates(self):
        for lat, lon in [([91], [0]), ([0], [181]), ([np.nan], [0]), ([1, 2], [1])]:
            with self.assertRaises(ValueError):
                geographic_to_local_meters(lat, lon)

    def test_cleaning_preserves_distinct_colocated_events(self):
        text = 'time,id,latitude,longitude\n2024-01-02,b,34,-118\n2024-01-01,a,34,-118\n2024-01-01,a,34,-118\n2024-01-03,c,nan,-118\n2024-01-04,d,999,-118\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.csv'
            path.write_text(text)
            X, ids = load_usgs_csv(path)
            self.assertEqual(ids, ['a', 'b'])
            np.testing.assert_array_equal(X, np.zeros((2, 2)))

    def test_sampling_spans_time_order(self):
        text = 'time,id,latitude,longitude\n' + ''.join(f'2024-01-{i+1:02d},id{i},34.{i:03d},-118\n' for i in range(10))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.csv'
            path.write_text(text)
            X, ids = load_usgs_csv(path, max_points=3)
            self.assertEqual(ids, ['id0', 'id4', 'id9'])
            self.assertEqual(X.shape, (3, 2))

    def test_empty_data_and_invalid_sample_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.csv'
            path.write_text('time,id,latitude,longitude\n')
            with self.assertRaises(ValueError):
                load_usgs_csv(path)
            with self.assertRaises(ValueError):
                load_usgs_csv(path, max_points=0)


if __name__ == '__main__':
    unittest.main()
