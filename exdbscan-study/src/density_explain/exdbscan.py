"""ExDBSCAN: discrete reference-core selection followed by analytic projection.

Mathematical sources: Matthews et al. (2026), equations 2-4 and appendices.
This implementation is independently written; it does not load author code.
"""

from collections import OrderedDict
from numbers import Integral
import numpy as np
from .constraints import feasible_core_mask, immutable_indices, project_to_core_ball
from .graph import CoreGraph, inverse_distances
from .neighbors import distances_to, numerical_tolerance, positive_integer, reachable_clusters
from .types import ExplanationResult, SelectionStep, readonly


class ExDBSCAN:
    """Explain an already fitted DBSCAN snapshot without reclustering.

    ``normalization='paper'`` scales graph distances by d_c / mean_edge_weight.
    The interpretation of the paper's 'average graph weight' is documented in
    docs/method_spec.md. 'none' exposes the unscaled equation for verification.
    """

    def __init__(self, model, *, normalization="paper"):
        if not hasattr(model, "result_"):
            raise ValueError("ExDBSCAN requires a fitted DBSCAN instance")
        if normalization not in ("paper", "none"):
            raise ValueError("normalization must be 'paper' or 'none'")
        self.clustering = model.result_  # immutable snapshot, even if model is refitted
        self.normalization = normalization
        self._graphs = OrderedDict()

    def _get_graph(self, indices):
        key = tuple(int(i) for i in indices)
        if key in self._graphs:
            self._graphs.move_to_end(key)
            return self._graphs[key]
        result = self.clustering
        graph = CoreGraph(result.X, indices, result.labels, result.eps)
        self._graphs[key] = graph
        while len(self._graphs) > 4:
            self._graphs.popitem(last=False)
        return graph

    def explain(self, point_index=None, *, point=None, target_cluster=None, k=3,
                immutable_features=(), strategy="greedy", random_state=0):
        """Generate explanations for a training index OR an external query point.

        A missing target permits all non-source, not-already-reachable clusters.
        'nearest' and 'random' are independently implemented diagnostic baselines.
        Partial/infeasible queries return explicit status, never padded points.
        Validity means target reachability, not unique assignment in an overlap.
        """
        k = positive_integer(k, "k")
        result = self.clustering
        if (point_index is None) == (point is None):
            raise ValueError("Specify exactly one of point_index and point")
        if point_index is not None:
            if isinstance(point_index, (bool, np.bool_)) or not isinstance(point_index, Integral):
                raise ValueError("point_index must be an integer")
            if not 0 <= point_index < len(result.X):
                raise ValueError("point_index is out of range")
            p = result.X[point_index].copy()
            source = int(result.labels[point_index])
        else:
            p = np.asarray(point, dtype=float)
            if p.ndim != 1 or p.shape[0] != result.X.shape[1] or not np.isfinite(p).all():
                raise ValueError("point must be a finite vector of the fitted dimension")
            memberships = reachable_clusters(result, p)[0]
            source = memberships[0] if memberships else -1
        immutable = immutable_indices(immutable_features, result.X.shape[1])
        if strategy not in ("greedy", "nearest", "random"):
            raise ValueError("strategy must be 'greedy', 'nearest', or 'random'")
        if target_cluster is not None:
            if isinstance(target_cluster, (bool, np.bool_)) or not isinstance(target_cluster, Integral):
                raise ValueError("target_cluster must be an integer cluster ID")
            target_cluster = int(target_cluster)
            if target_cluster not in result.cluster_ids:
                raise ValueError("target_cluster must be an existing non-noise cluster")
            if target_cluster == source:
                raise ValueError("target_cluster must differ from the source cluster")

        def empty(status, reason, candidates=()):
            return ExplanationResult(
                original=readonly(p), source_cluster=source, requested_k=k,
                target_cluster=target_cluster,
                counterfactuals=readonly(np.empty((0, len(p)))),
                reference_indices=readonly([], int), target_labels=readonly([], int),
                reachable_clusters=(), unique_target_labels=readonly([], bool),
                immutable_features=immutable, candidate_indices=readonly(candidates, int),
                selection_steps=(), graph_distances=readonly(np.empty((0, 0))),
                normalization_scale=1.0, status=status, reason=reason,
            )

        already_reachable = set(reachable_clusters(result, p)[0])
        if target_cluster is not None and target_cluster in already_reachable:
            return empty("already_reachable", "Query already reaches the target under fixed-core membership")
        candidates = result.core_indices
        if target_cluster is not None:
            candidates = candidates[result.labels[candidates] == target_cluster]
        else:
            excluded = already_reachable | {source}
            candidates = candidates[~np.isin(result.labels[candidates], list(excluded))]
        if not len(candidates):
            return empty("infeasible", "No alternative cluster with eligible core points")
        eligible = feasible_core_mask(p, result.X[candidates], result.eps, immutable)
        candidates = candidates[eligible]
        if not len(candidates):
            return empty("infeasible", "No target core ball intersects the immutable-coordinate slice")

        # Duplicate observations count in DBSCAN density, but identical reference
        # locations add no alternative explanation and would cause 1 / 0 repulsion.
        distinct = []
        seen = set()
        for index in candidates:
            key = (int(result.labels[index]), tuple(result.X[index]))
            if key not in seen:
                seen.add(key)
                distinct.append(int(index))
        candidates = np.asarray(distinct, dtype=int)
        graph = self._get_graph(candidates)
        query_distances = distances_to(result.X[candidates], p)
        with np.errstate(over="ignore"):
            attraction = query_distances ** 2
        if not np.isfinite(attraction).all():
            raise ValueError("Squared distances overflow; rescale the features")
        scale = 1.0
        if self.normalization == "paper" and graph.mean_positive_edge_weight is not None:
            scale = float(query_distances.min() / graph.mean_positive_edge_weight)
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError("Invalid normalization scale; check feature magnitudes")

        scores = attraction.copy()
        selected = []
        steps = []
        total_energy = 0.0
        random_order = np.random.default_rng(random_state).permutation(len(candidates))
        for iteration in range(min(k, len(candidates))):
            if strategy == "greedy":
                chosen = int(np.argmin(scores))
            elif strategy == "nearest":
                nearest_scores = attraction.copy()
                nearest_scores[selected] = np.inf
                chosen = int(np.argmin(nearest_scores))
            else:
                chosen = int(random_order[iteration])
            marginal = float(scores[chosen])
            if not np.isfinite(marginal):
                raise ValueError("Non-finite energy; candidate geometry is numerically degenerate")
            total_energy += marginal
            steps.append(SelectionStep(int(candidates[chosen]), marginal, total_energy))
            selected.append(chosen)
            scores += inverse_distances(graph.distances_from(chosen), scale)
            scores[selected] = np.inf

        points = []
        kept = []
        labels = []
        duplicate_count = 0
        for local_index in selected:
            index = candidates[local_index]
            projected = project_to_core_ball(p, result.X[index], result.eps, immutable)
            if projected is None:
                raise RuntimeError("Internal error: selected an unreachable core")
            label = int(result.labels[index])
            if any(label == old_label and np.array_equal(projected, old) for old, old_label in zip(points, labels)):
                duplicate_count += 1
                continue
            points.append(projected)
            kept.append(local_index)
            labels.append(label)
        points = np.asarray(points, dtype=float).reshape(-1, len(p))
        memberships = reachable_clusters(result, points, atol=numerical_tolerance(result.eps))
        if not all(t in group for t, group in zip(labels, memberships)):
            raise RuntimeError("Constructed point failed the fixed-core reachability check")
        unique = [group == (t,) for t, group in zip(labels, memberships)]
        selected_distances = np.array([graph.distances_from(i)[kept] for i in kept])
        reasons = []
        if len(candidates) < k:
            reasons.append(f"Only {len(candidates)} distinct eligible reference locations for k={k}")
        if duplicate_count:
            reasons.append(f"Removed {duplicate_count} identical same-target projected alternatives")
        return ExplanationResult(
            original=readonly(p), source_cluster=source, requested_k=k,
            target_cluster=target_cluster, counterfactuals=readonly(points),
            reference_indices=readonly(candidates[kept], int), target_labels=readonly(labels, int),
            reachable_clusters=memberships, unique_target_labels=readonly(unique, bool),
            immutable_features=immutable, candidate_indices=readonly(candidates, int),
            selection_steps=tuple(steps), graph_distances=readonly(selected_distances),
            normalization_scale=scale, status="ok" if len(points) == k else "partial",
            reason="; ".join(reasons),
        )
