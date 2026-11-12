"""Certified fixed-core reachability and finite-grid parameter sensitivity.

Only NumPy and our DBSCAN/projection implementations are used. Certificates
are sufficient single-ball certificates, not maximal radii for a union of balls.
"""
from numbers import Integral, Real
import numpy as np
from .constraints import immutable_indices, project_to_core_ball
from .dbscan import DBSCAN
from .neighbors import distances_to, numerical_tolerance


def robust_explain(model, point, target_cluster, rho=0.0, immutable_features=()):
    r = model.result_
    p = np.asarray(point, dtype=float)
    if p.shape != (r.X.shape[1],) or not np.isfinite(p).all():
        raise ValueError('point must be a finite vector of the fitted dimension')
    if isinstance(target_cluster, (bool, np.bool_)) or not isinstance(target_cluster, Integral) or target_cluster not in r.cluster_ids:
        raise ValueError('target_cluster must be an existing cluster')
    if isinstance(rho, (bool, np.bool_)) or not isinstance(rho, Real) or not np.isfinite(rho) or not 0 <= rho < r.eps:
        raise ValueError('rho must satisfy 0 <= rho < eps')
    fixed = immutable_indices(immutable_features, len(p))
    best = None
    for index in r.core_indices:
        if r.labels[index] != target_cluster:
            continue
        z = project_to_core_ball(p, r.X[index], r.eps - rho, fixed)
        if z is None:
            continue
        distance = float(distances_to(z[None, :], p)[0])
        margin = float(r.eps - distances_to(r.X[index:index+1], z)[0])
        # Report the actually computed margin, including floating-point residuals.
        candidate = (distance, int(index), z, max(0.0, margin))
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    if best is None:
        return dict(status='infeasible', reason='No shrunken target ball intersects the fixed-coordinate slice', rho=float(rho))
    distance, index, z, margin = best
    return dict(status='ok', original=p.tolist(), counterfactual=z.tolist(),
                distance=distance, reference=index, target=int(target_cluster),
                rho=float(rho), certified_radius=margin,
                numerical_shortfall=max(0.0, float(rho)-margin),
                immutable_features=list(fixed))


def match_cluster(base_labels, new_labels, target, min_jaccard=0.5):
    """Conservative identity matching; splits and merges are explicitly unresolved."""
    old = base_labels == target
    overlaps = [int(c) for c in np.unique(new_labels[old]) if c >= 0]
    if not overlaps:
        return dict(status='disappeared', cluster=None, jaccard=0.0)
    if len(overlaps) > 1:
        return dict(status='split', cluster=None, jaccard=None)
    c = overlaps[0]
    new = new_labels == c
    score = float(np.count_nonzero(old & new) / np.count_nonzero(old | new))
    other = np.unique(base_labels[new & ~old])
    if any(label >= 0 for label in other):
        return dict(status='merged', cluster=None, jaccard=score)
    if score < min_jaccard:
        return dict(status='weak_overlap', cluster=None, jaccard=score)
    return dict(status='matched', cluster=c, jaccard=score)


def parameter_stability(model, point, target_cluster, eps_values, min_pts_values):
    """Refit original data, match target, then query the SAME fixed endpoint.

    No query point is inserted or moved during refitting. Unresolved identity
    counts as not passed; the ratio is descriptive, not a probability.
    """
    r = model.result_
    if target_cluster not in r.cluster_ids:
        raise ValueError('Unknown target cluster')
    p = np.asarray(point, dtype=float)
    if p.shape != (r.X.shape[1],) or not np.isfinite(p).all():
        raise ValueError('Invalid endpoint')
    if not len(eps_values) or not len(min_pts_values):
        raise ValueError('Parameter grid must be nonempty')
    cells = []
    for min_pts in min_pts_values:
        for eps in eps_values:
            fitted = DBSCAN(eps=eps, min_pts=min_pts).fit(r.X)
            match = match_cluster(r.labels, fitted.labels_, target_cluster)
            passed = match['status'] == 'matched' and match['cluster'] in fitted.memberships(p, atol=numerical_tolerance(float(eps)))[0]
            cells.append(dict(eps=float(eps), min_pts=int(min_pts), **match, passed=bool(passed)))
    return dict(cells=cells, passed=sum(c['passed'] for c in cells), total=len(cells),
                policy='Jaccard >= 0.5; splits/merges/disappearance unresolved; original data refitted; reachability tolerance 1e-10*max(1,eps)')
