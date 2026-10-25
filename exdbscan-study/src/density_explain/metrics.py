"""Independent endpoint validation and explicitly named quality measures."""

import numpy as np
from .neighbors import numerical_tolerance


def dpp_diversity(distances):
    """det(1 / (1 + distance)); +inf gives a zero off-diagonal kernel entry.

    Arbitrary graph-metric kernels need not be positive semidefinite. Report the
    signed determinant without silently clipping a negative value to zero.
    Empty sets have no meaningful diversity, represented by None.
    """
    distances = np.asarray(distances, dtype=float)
    if distances.size == 0:
        return None
    if distances.ndim != 2 or distances.shape[0] != distances.shape[1]:
        raise ValueError("Expected a square distance matrix")
    kernel = 1.0 / (1.0 + distances)
    np.fill_diagonal(kernel, 1.0)
    return float(np.linalg.det(kernel))


def evaluate_explanation(clustering, explanation):
    """Recompute validity from raw coordinates, independently of generation.

    Both returned-point validity and requested-k coverage are reported, so
    partial/infeasible queries cannot be disguised as 100% successful queries.
    """
    values = explanation.counterfactuals
    valid = []
    unique = []
    fixed_ok = []
    tolerance = numerical_tolerance(clustering.eps)
    for point, target in zip(values, explanation.target_labels):
        memberships = set()
        for index in np.flatnonzero(clustering.core_mask):
            if float(np.linalg.norm(point - clustering.X[index])) <= clustering.eps + tolerance:
                memberships.add(int(clustering.labels[index]))
        fixed = all(point[i] == explanation.original[i] for i in explanation.immutable_features)
        valid.append(int(target) in memberships and fixed)
        unique.append(memberships == {int(target)} and fixed)
        fixed_ok.append(fixed)
    count = len(values)
    proximity = np.linalg.norm(values - explanation.original, axis=1)
    euclidean = np.linalg.norm(values[:, None, :] - values[None, :, :], axis=2)
    graph = explanation.graph_distances
    upper = graph[np.triu_indices(count, 1)] if count else np.array([])
    finite = upper[np.isfinite(upper)]
    valid_proximity = proximity[np.asarray(valid, dtype=bool)]
    return {
        "status": explanation.status,
        "requested_k": explanation.requested_k,
        "returned_k": count,
        "valid_count": int(sum(valid)),
        "returned_validity": float(np.mean(valid)) if count else 0.0,
        "requested_validity": float(sum(valid) / explanation.requested_k),
        "complete": count == explanation.requested_k and all(valid),
        "unique_target_rate": float(np.mean(unique)) if count else 0.0,
        "immutable_preserved": all(fixed_ok),
        "mean_proximity": float(np.mean(valid_proximity)) if len(valid_proximity) else None,
        "dpp_euclidean": dpp_diversity(euclidean),
        "dpp_reference_graph": dpp_diversity(graph),
        "mean_finite_reference_graph_distance": float(np.mean(finite)) if len(finite) else None,
        "disconnected_reference_pairs": int(np.isinf(upper).sum()),
    }
