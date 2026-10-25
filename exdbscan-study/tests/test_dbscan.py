import unittest
import numpy as np
from density_explain import DBSCAN


def component_oracle(X, eps, minimum):
    """Independent tiny-data oracle: core components first, then attach borders."""
    n = len(X)
    edges = [[float(np.linalg.norm(X[i] - X[j])) <= eps for j in range(n)] for i in range(n)]
    core = np.array([sum(row) >= minimum for row in edges])
    labels = np.full(n, -1)
    cluster = 0
    for seed in range(n):
        if not core[seed] or labels[seed] >= 0:
            continue
        stack = [seed]
        labels[seed] = cluster
        while stack:
            i = stack.pop()
            for j in range(n):
                if core[j] and edges[i][j] and labels[j] < 0:
                    labels[j] = cluster
                    stack.append(j)
        cluster += 1
    for i in range(n):
        if not core[i]:
            options = [labels[j] for j in range(n) if core[j] and edges[i][j]]
            labels[i] = min(options, default=-1)
    return core, labels


class DBSCANTests(unittest.TestCase):
    def test_manual_core_border_noise_and_noise_reassignment(self):
        model = DBSCAN(.81, 3).fit([[1], [0], [.1], [.2], [3]])
        np.testing.assert_array_equal(model.labels_, [0, 0, 0, 0, -1])
        np.testing.assert_array_equal(model.point_types_, ['border', 'core', 'core', 'core', 'noise'])
        np.testing.assert_array_equal(model.neighbor_counts_, [2, 3, 3, 4, 1])

    def test_border_cannot_merge_clusters(self):
        model = DBSCAN(.61, 4).fit([[-.8], [-.7], [-.6], [0], [.6], [.7], [.8]])
        np.testing.assert_array_equal(model.core_indices_, [2, 4])
        np.testing.assert_array_equal(model.labels_, [0, 0, 0, 0, 1, 1, 1])
        self.assertEqual(model.memberships([0]), ((0, 1),))

    def test_shared_border_order_is_documented(self):
        model = DBSCAN(.61, 4).fit([[0], [.6], [.7], [.8], [-.6], [-.7], [-.8]])
        self.assertEqual(model.labels_[0], model.labels_[1])
        self.assertNotEqual(model.labels_[1], model.labels_[-1])

    def test_closed_radius_and_chain_reachability(self):
        model = DBSCAN(1, 2).fit([[0], [1], [2]])
        np.testing.assert_array_equal(model.labels_, [0, 0, 0])
        self.assertTrue(model.core_mask_.all())

    def test_self_counts_and_singleton(self):
        self.assertEqual(DBSCAN(1, 1).fit([[0]]).labels_[0], 0)
        self.assertEqual(DBSCAN(1, 2).fit([[0]]).labels_[0], -1)

    def test_duplicates_count_for_density(self):
        model = DBSCAN(.1, 3).fit([[0], [0], [0], [2]])
        np.testing.assert_array_equal(model.labels_, [0, 0, 0, -1])

    def test_all_noise(self):
        model = DBSCAN(.1, 2).fit([[0], [1], [2]])
        self.assertEqual(model.result_.cluster_ids, ())
        self.assertEqual(model.memberships([[0], [10]]), ((), ()))

    def test_randomized_component_oracle(self):
        rng = np.random.default_rng(42)
        for _ in range(30):
            X = rng.normal(size=(35, 3))
            eps = float(rng.uniform(.25, 1.6))
            minimum = int(rng.integers(2, 8))
            core, labels = component_oracle(X, eps, minimum)
            model = DBSCAN(eps, minimum).fit(X)
            np.testing.assert_array_equal(model.core_mask_, core)
            np.testing.assert_array_equal(model.labels_, labels)

    def test_permutation_preserves_core_partition(self):
        rng = np.random.default_rng(13)
        X = np.vstack([rng.normal(-2, .15, (15, 2)), rng.normal(2, .15, (15, 2)), [[0, 0]]])
        permutation = rng.permutation(len(X))
        original = DBSCAN(.4, 4).fit(X)
        shuffled = DBSCAN(.4, 4).fit(X[permutation])
        inverse = np.argsort(permutation)
        np.testing.assert_array_equal(original.core_mask_, shuffled.core_mask_[inverse])
        cores = original.core_indices_
        a, b = original.labels_[cores], shuffled.labels_[inverse][cores]
        np.testing.assert_array_equal(a[:, None] == a[None, :], b[:, None] == b[None, :])

    def test_snapshot_does_not_alias_input(self):
        X = np.array([[0.], [.1]])
        model = DBSCAN(.2, 2).fit(X)
        X[:] = 10
        self.assertEqual(model.X_[0, 0], 0)
        with self.assertRaises(ValueError):
            model.labels_[0] = 9

    def test_invalid_parameters_and_data(self):
        for eps in [0, -1, np.nan, np.inf, True, [1]]:
            with self.subTest(eps=eps), self.assertRaises(ValueError):
                DBSCAN(eps, 2)
        for minimum in [0, -1, 2.5, True]:
            with self.subTest(minimum=minimum), self.assertRaises(ValueError):
                DBSCAN(1, minimum)
        for X in [[], [1, 2], [[np.nan]], [[np.inf]], [[], []], [[1], [1, 2]]]:
            with self.subTest(X=X), self.assertRaises(ValueError):
                DBSCAN().fit(X)

    def test_membership_input_validation(self):
        with self.assertRaises(ValueError):
            DBSCAN().memberships([0])
        model = DBSCAN(1, 1).fit([[0, 0]])
        for points in [[0], [np.nan, 0], [[[0, 0]]]]:
            with self.assertRaises(ValueError):
                model.memberships(points)


if __name__ == '__main__':
    unittest.main()
