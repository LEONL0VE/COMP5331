"""What the explorer's API computes, on top of the group's density_explain package.

Nothing here re-implements DBSCAN or ExDBSCAN. Every answer comes from the
same DBSCAN and ExDBSCAN classes the experiments use; this module only
validates requests, caches fitted models and shapes results for the browser.
"""

from collections import OrderedDict, deque
from dataclasses import dataclass
from numbers import Integral, Real
import threading

import numpy as np

from density_explain import DBSCAN, ExDBSCAN
from density_explain.neighbors import distances_to

from datasets import DATASETS, cluster_names

ROLE_CODES = {"core": 0, "border": 1, "noise": 2}
# Counterfactuals sit exactly on an eps boundary, so a re-run of DBSCAN can miss
# them by one rounding error. verify() places the point this fraction inside.
NUDGE = 1e-9
CACHE_SIZE = 16

_lock = threading.Lock()
_fits = OrderedDict()


class RequestError(ValueError):
    """A request the API rejects with HTTP 400."""


@dataclass
class Fit:
    model: DBSCAN
    explainer: ExDBSCAN
    names: dict


def list_datasets():
    return [d.describe() for d in DATASETS.values()]


def points(dataset_id):
    if dataset_id not in DATASETS:
        raise RequestError("Unknown dataset")
    return DATASETS[dataset_id].points()


def cluster(body):
    dataset, eps, min_pts = _request(body)
    with _lock:
        fit = _fit(dataset, eps, min_pts)
    result = fit.model.result_
    labels = result.labels
    cores = result.core_indices
    return {
        "labels": labels.tolist(),
        "roles": [ROLE_CODES[t] for t in result.point_types],
        "order": _expansion_order(result),
        "clusters": [
            {"id": c, "name": fit.names[c], "size": int((labels == c).sum()),
             "core": cores[labels[cores] == c].tolist()}
            for c in result.cluster_ids
        ],
        "counts": {
            "clusters": len(result.cluster_ids),
            "core": int(result.core_mask.sum()),
            "border": int((result.point_types == "border").sum()),
            "noise": int((labels == -1).sum()),
        },
    }


def why(body):
    """Why a point is core, border or noise, and how far each other cluster is."""
    dataset, eps, min_pts = _request(body)
    index, point = _query(body, dataset)
    with _lock:
        fit = _fit(dataset, eps, min_pts)
    result = fit.model.result_
    cores = result.core_indices
    if index is not None:
        p = result.X[index]
        neighbors = [int(i) for i in result.neighborhoods[index] if i != index]
        role = str(result.point_types[index])
        cluster = int(result.labels[index]) if result.labels[index] >= 0 else None
        others = cores != index
    else:
        # An imagined point, judged as if it were added without refitting.
        p = point
        neighbors = np.flatnonzero(distances_to(result.X, p) <= eps).tolist()
        reachable = fit.model.memberships(p)[0]
        cluster = int(reachable[0]) if reachable else None
        role = "core" if len(neighbors) + 1 >= min_pts else ("border" if reachable else "noise")
        others = np.ones(len(cores), dtype=bool)

    core_distances = distances_to(result.X[cores], p) if len(cores) else np.empty(0)
    core_labels = result.labels[cores]

    def closest(mask):
        if not mask.any():
            return None
        j = int(np.argmin(np.where(mask, core_distances, np.inf)))
        return {"index": int(cores[j]), "distance": float(core_distances[j]), "cluster": int(core_labels[j])}

    host = None
    if role == "border" and cluster is not None:
        host = closest(others & (core_labels == cluster) & (core_distances <= eps))
    targets = []
    for c in result.cluster_ids:
        mask = others & (core_labels == c)
        if c == cluster or not mask.any():
            continue
        distance = float(core_distances[mask].min())
        targets.append({"cluster": c, "name": fit.names[c], "distance": distance, "gap": max(0.0, distance - eps)})
    targets.sort(key=lambda t: t["distance"])
    return {
        "role": role,
        "cluster": cluster,
        "count": len(neighbors) + 1,
        "neighbors": neighbors,
        "nearestCore": closest(others),
        "host": host,
        "targets": targets,
        "point": p.tolist(),
    }


def explain(body):
    """The smallest move that puts a point inside a target cluster (ExDBSCAN with k = 1)."""
    dataset, eps, min_pts = _request(body)
    index, point = _query(body, dataset)
    target = body.get("target")
    if isinstance(target, bool) or not isinstance(target, Integral):
        raise RequestError("target must be a cluster id")
    fixed = _fixed(body, dataset)
    with _lock:
        fit = _fit(dataset, eps, min_pts)
        try:
            res = fit.explainer.explain(point_index=index, point=point, target_cluster=int(target), k=1,
                                        immutable_features=() if fixed is None else (fixed,))
        except ValueError as exc:
            raise RequestError(str(exc)) from exc
    answer = {"status": res.status, "reason": res.reason, "target": int(target), "fixed": fixed,
              "original": res.original.tolist()}
    if res.returned_k:
        counterfactual = res.counterfactuals[0]
        reference = int(res.reference_indices[0])
        answer.update({
            "counterfactual": counterfactual.tolist(),
            "change": (counterfactual - res.original).tolist(),
            "distance": float(np.linalg.norm(counterfactual - res.original)),
            "reference": {"index": reference, "point": fit.model.result_.X[reference].tolist()},
        })
    return answer


def verify(body):
    """Move the point to its counterfactual, rerun DBSCAN, and report where it lands."""
    dataset, eps, min_pts = _request(body)
    index, point = _query(body, dataset)
    counterfactual = _vector(body.get("counterfactual"), "counterfactual")
    reference = body.get("reference")
    if isinstance(reference, bool) or not isinstance(reference, Integral) or not 0 <= reference < len(dataset.X):
        raise RequestError("reference must be a point index")
    fixed = _fixed(body, dataset)
    with _lock:
        fit = _fit(dataset, eps, min_pts)
    result = fit.model.result_
    anchor = result.X[reference]
    free = [j for j in range(len(counterfactual)) if j != fixed]
    moved = counterfactual.copy()
    moved[free] = anchor[free] + (counterfactual[free] - anchor[free]) * (1 - NUDGE)
    X = np.array(result.X, dtype=float)
    if index is not None:
        X[index] = moved
        mover = index
    else:
        X = np.vstack([X, moved])
        mover = len(result.X)
    refit = DBSCAN(eps=eps, min_pts=min_pts).fit(X)
    unchanged = np.ones(len(result.X), dtype=bool)
    if index is not None:
        unchanged[index] = False
    return {
        "joined": bool(refit.labels_[mover] >= 0 and refit.labels_[mover] == refit.labels_[reference]),
        "role": str(refit.point_types_[mover]),
        "changedRoles": int((refit.point_types_[:len(result.X)][unchanged] != result.point_types[unchanged]).sum()),
    }


def _fit(dataset, eps, min_pts):
    key = (dataset.id, eps, min_pts)
    if key in _fits:
        _fits.move_to_end(key)
        return _fits[key]
    model = DBSCAN(eps=eps, min_pts=min_pts).fit(dataset.X)
    fit = Fit(model, ExDBSCAN(model), cluster_names(dataset, model.labels_))
    _fits[key] = fit
    while len(_fits) > CACHE_SIZE:
        _fits.popitem(last=False)
    return fit


def _expansion_order(result):
    """Point indices in the order DBSCAN's queue expansion reaches them, noise last."""
    reached = np.zeros(len(result.X), dtype=bool)
    order = []
    for seed in range(len(result.X)):
        if reached[seed] or not result.core_mask[seed]:
            continue
        reached[seed] = True
        order.append(seed)
        queue = deque([seed])
        while queue:
            for neighbor in result.neighborhoods[queue.popleft()]:
                neighbor = int(neighbor)
                if not reached[neighbor]:
                    reached[neighbor] = True
                    order.append(neighbor)
                    if result.core_mask[neighbor]:
                        queue.append(neighbor)
    order.extend(np.flatnonzero(~reached).tolist())
    return order


def _request(body):
    dataset_id = body.get("dataset")
    if not isinstance(dataset_id, str):
        raise RequestError("dataset must be a string")
    dataset = DATASETS.get(dataset_id)
    if dataset is None:
        raise RequestError("Unknown dataset")
    eps, min_pts = body.get("eps"), body.get("minPts")
    if isinstance(eps, bool) or not isinstance(eps, Real) or not dataset.eps["min"] <= eps <= dataset.eps["max"]:
        raise RequestError(f"eps must be between {dataset.eps['min']} and {dataset.eps['max']}")
    if (isinstance(min_pts, bool) or not isinstance(min_pts, Integral)
            or not dataset.min_pts["min"] <= min_pts <= dataset.min_pts["max"]):
        raise RequestError(f"minPts must be an integer between {dataset.min_pts['min']} and {dataset.min_pts['max']}")
    return dataset, float(eps), int(min_pts)


def _fixed(body, dataset):
    """The coordinate a move must keep (0 = east or x, 1 = north or y), or None for any direction."""
    fixed = body.get("fixed")
    if fixed is None:
        return None
    if isinstance(fixed, bool) or not isinstance(fixed, Integral) or not 0 <= fixed < dataset.X.shape[1]:
        raise RequestError("fixed must be null or a feature index")
    return int(fixed)


def _query(body, dataset):
    """The point a request asks about: a dataset index, or a free position in data units."""
    index = body.get("index")
    if index is not None:
        if isinstance(index, bool) or not isinstance(index, Integral) or not 0 <= index < len(dataset.X):
            raise RequestError("index is out of range")
        return int(index), None
    return None, _vector(body.get("point"), "point")


def _vector(value, name):
    try:
        vector = np.array(value, dtype=float)
    except (TypeError, ValueError):
        raise RequestError(f"{name} must be two numbers") from None
    if vector.shape != (2,) or not np.isfinite(vector).all():
        raise RequestError(f"{name} must be two finite numbers")
    return vector
