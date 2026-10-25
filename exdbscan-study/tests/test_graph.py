import unittest
import numpy as np
from density_explain.graph import CoreGraph, dijkstra, inverse_distances


class GraphTests(unittest.TestCase):
    def test_u_shape_uses_graph_not_euclidean_distance(self):
        X = np.array([[0, 2], [0, 1], [0, 0], [1, 0], [2, 0], [2, 1], [2, 2]], float)
        graph = CoreGraph(X, np.arange(7), np.zeros(7, int), 1.01)
        self.assertEqual(graph.distances_from(0)[6], 6)
        self.assertEqual(np.linalg.norm(X[0] - X[6]), 2)
        self.assertEqual(graph.edge_count, 6)

    def test_dijkstra_matches_floyd_warshall(self):
        rng = np.random.default_rng(4)
        for _ in range(10):
            n = 9
            matrix = np.full((n, n), np.inf)
            np.fill_diagonal(matrix, 0)
            adjacency = [[] for _ in range(n)]
            for i in range(n):
                for j in range(i):
                    if rng.random() < .3:
                        weight = float(rng.uniform(.01, 3))
                        matrix[i, j] = matrix[j, i] = weight
                        adjacency[i].append((j, weight))
                        adjacency[j].append((i, weight))
            for middle in range(n):
                for i in range(n):
                    for j in range(n):
                        matrix[i, j] = min(matrix[i, j], matrix[i, middle] + matrix[middle, j])
            for source in range(n):
                np.testing.assert_allclose(dijkstra(adjacency, source), matrix[source])

    def test_zero_edges_disconnected_and_no_cross_cluster_edges(self):
        X = np.array([[0.], [0.], [2.]])
        graph = CoreGraph(X, [0, 1, 2], np.array([0, 0, 1]), 10)
        np.testing.assert_array_equal(graph.distances_from(0), [0, 0, np.inf])
        np.testing.assert_array_equal(inverse_distances([0, 2, np.inf], 2), [np.inf, .25, 0])

    def test_cache_is_bounded_and_readonly(self):
        graph = CoreGraph(np.arange(5.)[:, None], np.arange(5), np.zeros(5), 1, max_cached_rows=2)
        for i in range(5):
            graph.distances_from(i)
        self.assertEqual(len(graph._rows), 2)
        with self.assertRaises(ValueError):
            graph.distances_from(0)[0] = 99

    def test_negative_edges_rejected(self):
        with self.assertRaises(ValueError):
            dijkstra([[(1, -1)], []], 0)


if __name__ == '__main__':
    unittest.main()
