from dataclasses import replace
from itertools import combinations
import json
import unittest
import numpy as np
from density_explain import DBSCAN, ExDBSCAN
from density_explain.constraints import project_to_core_ball
from density_explain.datasets import mock_blobs
from density_explain.graph import CoreGraph, set_energy
from density_explain.metrics import evaluate_explanation, dpp_diversity


class ExDBSCANTests(unittest.TestCase):
    def setUp(self):
        self.X = mock_blobs(n_per_cluster=12)
        self.model = DBSCAN(.45, 4).fit(self.X)
        self.explainer = ExDBSCAN(self.model)

    def test_analytic_unconstrained_projection(self):
        np.testing.assert_allclose(project_to_core_ball([0, 0], [3, 4], 1), [2.4, 3.2])

    def test_noise_to_cluster(self):
        result = self.explainer.explain(36, target_cluster=0, k=3)
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.source_cluster, -1)
        self.assertEqual(evaluate_explanation(self.model.result_, result)['requested_validity'], 1)

    def test_cluster_to_cluster(self):
        result = self.explainer.explain(0, target_cluster=1, k=5)
        self.assertEqual(result.status, 'ok')
        self.assertEqual(evaluate_explanation(self.model.result_, result)['requested_validity'], 1)

    def test_k_one_is_nearest_ball(self):
        p = self.X[36]
        result = self.explainer.explain(36, target_cluster=0, k=1)
        indices = self.model.core_indices_[self.model.labels_[self.model.core_indices_] == 0]
        optimum = min(np.linalg.norm(p - self.X[i]) for i in indices) - self.model.eps
        self.assertAlmostEqual(np.linalg.norm(result.counterfactuals[0] - p), optimum, places=12)

    def test_incremental_selection_equals_literal_greedy(self):
        X = np.array([[0, 2], [0, 1], [0, 0], [1, 0], [2, 0], [2, 1], [2, 2]], float)
        model = DBSCAN(1.01, 1).fit(X)
        p = np.array([-2., 2.])
        for normalization in ['none', 'paper']:
            answer = ExDBSCAN(model, normalization=normalization).explain(point=p, target_cluster=0, k=4)
            graph = CoreGraph(X, np.arange(7), model.labels_, model.eps)
            attraction = np.sum((X - p) ** 2, axis=1)
            chosen = []
            for _ in range(4):
                options = [(set_energy(chosen + [j], attraction, graph, answer.normalization_scale), j)
                           for j in range(7) if j not in chosen]
                _, best = min(options)
                chosen.append(best)
            np.testing.assert_array_equal(answer.reference_indices, chosen)
            energy = set_energy(chosen, attraction, graph, answer.normalization_scale)
            self.assertAlmostEqual(answer.selection_steps[-1].cumulative_energy, energy)
            exact = min(set_energy(s, attraction, graph, answer.normalization_scale) for s in combinations(range(7), 4))
            self.assertGreaterEqual(energy + 1e-12, exact)

    def test_normalization_matches_documented_edge_mean(self):
        model = DBSCAN(1.1, 1).fit([[0, 0], [1, 0], [2, 0]])
        result = ExDBSCAN(model).explain(point=[-2, 0], target_cluster=0, k=2)
        self.assertEqual(result.normalization_scale, 2.0)

    def test_no_target_and_seeded_baselines(self):
        for strategy in ['greedy', 'nearest', 'random']:
            a = self.explainer.explain(36, k=4, strategy=strategy, random_state=9)
            b = self.explainer.explain(36, k=4, strategy=strategy, random_state=9)
            np.testing.assert_array_equal(a.counterfactuals, b.counterfactuals)
            self.assertEqual(evaluate_explanation(self.model.result_, a)['requested_validity'], 1)

    def test_query_never_changes_training_state(self):
        original_X, original_labels = self.model.X_.copy(), self.model.labels_.copy()
        self.explainer.explain(36, target_cluster=0, k=3)
        np.testing.assert_array_equal(self.model.X_, original_X)
        np.testing.assert_array_equal(self.model.labels_, original_labels)
        self.model.fit([[99, 99]])
        self.assertEqual(self.explainer.explain(36, target_cluster=0, k=1).status, 'ok')

    def test_duplicate_reference_locations_and_shortage(self):
        model = DBSCAN(1, 3).fit([[3, 0]] * 5 + [[0, 0]])
        result = ExDBSCAN(model).explain(5, target_cluster=0, k=3)
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.returned_k, 1)
        metrics = evaluate_explanation(model.result_, result)
        self.assertEqual(metrics['returned_validity'], 1)
        self.assertAlmostEqual(metrics['requested_validity'], 1/3)

    def test_all_noise_is_explicitly_infeasible(self):
        model = DBSCAN(.1, 3).fit([[0], [1]])
        result = ExDBSCAN(model).explain(0, k=2)
        self.assertEqual(result.status, 'infeasible')
        self.assertEqual(result.counterfactuals.shape, (0, 1))
        self.assertEqual(evaluate_explanation(model.result_, result)['requested_validity'], 0)

    def test_existing_overlap_is_not_a_fabricated_change(self):
        model = DBSCAN(.61, 4).fit([[-.8], [-.7], [-.6], [0], [.6], [.7], [.8]])
        result = ExDBSCAN(model).explain(3, target_cluster=1, k=1)
        self.assertEqual(result.status, 'already_reachable')
        self.assertEqual(result.returned_k, 0)

    def test_new_endpoint_reports_nonunique_target_membership(self):
        model = DBSCAN(.61, 4).fit([[-.8], [-.7], [-.6], [0], [.6], [.7], [.8]])
        result = ExDBSCAN(model).explain(point=[-2], target_cluster=1, k=1)
        self.assertEqual(result.reachable_clusters, ((0, 1),))
        self.assertFalse(result.unique_target_labels[0])
        metrics = evaluate_explanation(model.result_, result)
        self.assertEqual(metrics['returned_validity'], 1)
        self.assertEqual(metrics['unique_target_rate'], 0)

    def test_metric_recomputes_validity_for_tampered_result(self):
        result = self.explainer.explain(36, target_cluster=0, k=2)
        tampered = replace(result, counterfactuals=np.full((2, 2), 999.))
        self.assertEqual(evaluate_explanation(self.model.result_, tampered)['valid_count'], 0)

    def test_projection_validity_over_random_geometry(self):
        rng = np.random.default_rng(91)
        for dimension in [1, 2, 5, 12]:
            for _ in range(25):
                p = rng.normal(size=dimension)
                q = rng.normal(size=dimension)
                radius = .25 * np.linalg.norm(q - p)
                cf = project_to_core_ball(p, q, radius)
                self.assertLessEqual(np.linalg.norm(cf - q), radius + 1e-12)
                self.assertAlmostEqual(np.linalg.norm(cf - p), np.linalg.norm(q - p) - radius, places=12)

    def test_result_serializes_strict_json(self):
        result = self.explainer.explain(36, k=4)
        json.dumps(result.to_dict(), allow_nan=False)
        json.dumps(evaluate_explanation(self.model.result_, result), allow_nan=False)

    def test_dpp_metrics_known_cases(self):
        self.assertIsNone(dpp_diversity(np.empty((0, 0))))
        self.assertEqual(dpp_diversity([[0]]), 1)
        self.assertAlmostEqual(dpp_diversity([[0, 1], [1, 0]]), .75)
        self.assertEqual(dpp_diversity([[0, np.inf], [np.inf, 0]]), 1)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            ExDBSCAN(DBSCAN())
        for arguments in [{}, {'point_index': 0, 'point': [0, 0]}, {'point_index': -1},
                          {'point_index': True}, {'point': [0]}, {'point': [np.nan, 0]},
                          {'point_index': 36, 'k': 0}, {'point_index': 36, 'k': 2.1},
                          {'point_index': 36, 'target_cluster': -1},
                          {'point_index': 0, 'target_cluster': 0},
                          {'point_index': 36, 'target_cluster': True},
                          {'point_index': 36, 'strategy': 'invalid'}]:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.explainer.explain(**arguments)


if __name__ == '__main__':
    unittest.main()
