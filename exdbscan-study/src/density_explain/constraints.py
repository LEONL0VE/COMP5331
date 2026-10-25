"""Immutable-coordinate feasibility and analytic projection onto a ball slice."""

from numbers import Integral
import numpy as np


def immutable_indices(indices, dimension):
    if indices is None:
        return ()
    answer = []
    for index in indices:
        if isinstance(index, (bool, np.bool_)) or not isinstance(index, Integral):
            raise ValueError("immutable_features must contain integer feature indices")
        if index < 0 or index >= dimension:
            raise ValueError("immutable feature index is out of range")
        answer.append(int(index))
    if len(set(answer)) != len(answer):
        raise ValueError("immutable feature indices must be distinct")
    return tuple(sorted(answer))


def feasible_core_mask(point, cores, eps, immutable):
    if not immutable:
        return np.ones(len(cores), dtype=bool)
    fixed_gap = np.hypot.reduce(cores[:, immutable] - point[list(immutable)], axis=1)
    return fixed_gap <= eps


def project_to_core_ball(point, core, eps, immutable=()):
    """Closest point in the core ball with fixed coordinates; None if infeasible.

    The mutable section has radius sqrt(eps^2 - fixed_gap^2). Rounding moves
    one ulp inside that section. A point already in it is returned unchanged.
    """
    point = np.asarray(point, dtype=float)
    core = np.asarray(core, dtype=float)
    immutable = immutable_indices(immutable, len(point))
    mutable = np.ones(len(point), dtype=bool)
    mutable[list(immutable)] = False
    fixed_gap = float(np.linalg.norm(point[list(immutable)] - core[list(immutable)]))
    if fixed_gap > eps:
        return None
    radius = float(np.sqrt(max(0.0, (eps - fixed_gap) * (eps + fixed_gap))))
    length = float(np.linalg.norm(point[mutable] - core[mutable]))
    projected = point.copy()
    if length <= radius:
        return projected
    radius = float(np.nextafter(radius, 0.0))
    projected[mutable] = core[mutable] + radius / length * (point[mutable] - core[mutable])
    return projected
