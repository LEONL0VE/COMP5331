import unittest
import numpy as np
from density_explain import DBSCAN, ExDBSCAN
from density_explain.constraints import immutable_indices, project_to_core_ball
from density_explain.datasets import mock_constraint_case
from density_explain.metrics import evaluate_explanation


class ConstraintTests(unittest.TestCase):
    def test_analytic_slice_projection(self):
        point = project_to_core_ball([0, 0], [3, .6], 1, (1,))
        np.testing.assert_allclose(point, [2.2, 0], atol=1e-14)
        self.assertLessEqual(np.linalg.norm(point - [3, .6]), 1 + 1e-14)

    def test_tangent_slice(self):
        np.testing.assert_array_equal(project_to_core_ball([0, 0], [3, 1], 1, (1,)), [3, 0])

    def test_infeasible_slice(self):
        self.assertIsNone(project_to_core_ball([0, 0], [3, 1.1], 1, (1,)))

    def test_existing_member_stays_fixed(self):
        np.testing.assert_array_equal(project_to_core_ball([0, 0], [.2, .2], 1, (1,)), [0, 0])

    def test_full_constrained_explanation(self):
        model = DBSCAN(1, 3).fit(mock_constraint_case())
        explanation = ExDBSCAN(model).explain(5, target_cluster=0, k=3, immutable_features=[1])
        self.assertEqual(explanation.status, 'ok')
        np.testing.assert_array_equal(explanation.counterfactuals[:, 1], [0, 0, 0])
        metrics = evaluate_explanation(model.result_, explanation)
        self.assertEqual(metrics['requested_validity'], 1)
        self.assertTrue(metrics['immutable_preserved'])

    def test_immutable_features_can_make_query_infeasible(self):
        model = DBSCAN(1, 3).fit(mock_constraint_case())
        result = ExDBSCAN(model).explain(5, target_cluster=0, immutable_features=[0])
        self.assertEqual(result.status, 'infeasible')
        self.assertEqual(result.returned_k, 0)

    def test_all_features_immutable(self):
        model = DBSCAN(1, 3).fit(mock_constraint_case())
        result = ExDBSCAN(model).explain(5, target_cluster=0, immutable_features=[0, 1])
        self.assertEqual(result.status, 'infeasible')

    def test_identical_constrained_projections_are_not_padded(self):
        model = DBSCAN(1, 1).fit([[3, .6], [3, -.6], [3, 0]])
        result = ExDBSCAN(model).explain(point=[0, 0], target_cluster=0, k=3, immutable_features=[1])
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.returned_k, 2)

    def test_projected_point_is_closest_in_slice_by_sampling(self):
        p, q, eps = np.array([0., 0., .4]), np.array([3., 2., 1.]), 1.
        projected = project_to_core_ball(p, q, eps, (2,))
        rho = np.sqrt(1 - .6 ** 2)
        angle = np.linspace(0, 2 * np.pi, 10001)
        samples = np.column_stack([3 + rho * np.cos(angle), 2 + rho * np.sin(angle), np.full(len(angle), .4)])
        self.assertLessEqual(np.linalg.norm(projected - p), np.min(np.linalg.norm(samples - p, axis=1)) + 1e-12)

    def test_filtering_can_disconnect_a_target_core_graph(self):
        X = [[0, 0], [0, .9], [0, 1.8], [.9, 1.8], [1.8, 1.8], [1.8, .9], [1.8, 0]]
        model = DBSCAN(1, 1).fit(X)
        result = ExDBSCAN(model).explain(point=[4, 0], target_cluster=0, k=4, immutable_features=[1])
        self.assertEqual(result.status, 'ok')
        self.assertTrue(np.isinf(result.graph_distances).any())
        self.assertEqual(evaluate_explanation(model.result_, result)['requested_validity'], 1)

    def test_invalid_feature_indices(self):
        for indices in [[-1], [2], [True], [1.2], [1, 1]]:
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                immutable_indices(indices, 2)


if __name__ == '__main__':
    unittest.main()
