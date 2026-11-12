import unittest
import numpy as np
from density_explain import DBSCAN, ExDBSCAN
from density_explain.robust import robust_explain, match_cluster, parameter_stability


class RobustTests(unittest.TestCase):
    def setUp(self):
        self.model = DBSCAN(1, 1).fit([[3, 0], [3, .5], [3, -.5]])

    def test_known_projection_and_certificate(self):
        r = robust_explain(self.model, [0, 0], 0, .25)
        np.testing.assert_allclose(r['counterfactual'], [2.25, 0])
        self.assertAlmostEqual(r['certified_radius'], .25)

    def test_zero_margin_agrees_with_original_unconstrained(self):
        old = ExDBSCAN(self.model).explain(point=[0, 0], target_cluster=0, k=1)
        new = robust_explain(self.model, [0, 0], 0)
        np.testing.assert_allclose(old.counterfactuals[0], new['counterfactual'])

    def test_sampled_entire_error_circle_stays_in_anchor_ball(self):
        r = robust_explain(self.model, [0, 0], 0, .3)
        angles = np.linspace(0, 2*np.pi, 2000)
        samples = np.asarray(r['counterfactual']) + r['certified_radius'] * np.column_stack([np.cos(angles), np.sin(angles)])
        self.assertTrue(np.all(np.linalg.norm(samples-self.model.X_[r['reference']], axis=1) <= 1+1e-12))

    def test_cost_monotone_with_radius(self):
        costs = [robust_explain(self.model, [0, 0], 0, rho)['distance'] for rho in (0, .1, .4, .9)]
        self.assertEqual(costs, sorted(costs))

    def test_fixed_coordinates_and_infeasible_slice(self):
        m = DBSCAN(1, 1).fit([[3, .8]])
        r = robust_explain(m, [0, 0], 0, .1, [1])
        self.assertEqual(r['counterfactual'][1], 0)
        self.assertAlmostEqual(r['counterfactual'][0], 3-np.sqrt(.9**2-.8**2))
        self.assertEqual(robust_explain(m, [0, 0], 0, .3, [1])['status'], 'infeasible')

    def test_already_safe_does_not_move(self):
        r = robust_explain(self.model, [3, 0], 0, .2, [0, 1])
        self.assertEqual(r['distance'], 0)
        self.assertEqual(r['certified_radius'], 1)

    def test_constrained_selection_uses_actual_move_not_core_distance(self):
        m = DBSCAN(1, 1).fit([[3, .8], [3.2, 0]])
        old = ExDBSCAN(m).explain(point=[0, 0], target_cluster=0, k=1, immutable_features=[1])
        new = robust_explain(m, [0, 0], 0, 0, [1])
        self.assertAlmostEqual(new['distance'], 2.2)
        self.assertLess(new['distance'], np.linalg.norm(old.counterfactuals[0]))

    def test_boundary_tolerance_is_shared_with_original(self):
        r = parameter_stability(self.model, [2-1e-12, 0], 0, [1], [1])
        self.assertEqual(r['passed'], 1)
        r = parameter_stability(self.model, [2-1e-5, 0], 0, [1], [1])
        self.assertEqual(r['passed'], 0)

    def test_invalid_inputs(self):
        for rho in (-1, 1, float('nan'), True):
            with self.assertRaises(ValueError): robust_explain(self.model, [0, 0], 0, rho)
        for target in (-1, [], True):
            with self.assertRaises(ValueError): robust_explain(self.model, [0, 0], target)

    def test_match_ignores_label_permutation(self):
        base = np.array([0,0,1,1,-1])
        new = np.array([8,8,3,3,-1])
        self.assertEqual(match_cluster(base,new,0)['cluster'],8)

    def test_split_merge_disappear_and_weak_overlap(self):
        base = np.array([0,0,1,1,-1,-1,-1])
        for new, status in [([2,3,1,1,-1,-1,-1],'split'),([2,2,2,2,-1,-1,-1],'merged'),([-1,-1,1,1,-1,-1,-1],'disappeared'),([2,2,1,1,2,2,2],'weak_overlap')]:
            self.assertEqual(match_cluster(base,np.array(new),0)['status'], status)

    def test_grid_same_parameters_pass_and_snapshot_unchanged(self):
        snapshot = self.model.X_.copy()
        r = parameter_stability(self.model, [2.4,0], 0, [.8,1,1.2], [1,2])
        self.assertEqual(r['passed'],6)
        np.testing.assert_array_equal(snapshot,self.model.X_)
        with self.assertRaises(ValueError): parameter_stability(self.model,[0,0],0,[],[1])

    def test_reported_margin_matches_independent_distance(self):
        rng = np.random.default_rng(29)
        for _ in range(50):
            p = rng.normal(size=2)*5
            r = robust_explain(self.model,p,0,.2)
            margin=1-np.linalg.norm(np.array(r['counterfactual'])-self.model.X_[r['reference']])
            self.assertAlmostEqual(r['certified_radius'],margin)
            self.assertLessEqual(r['numerical_shortfall'],1e-12)

if __name__ == '__main__': unittest.main()
