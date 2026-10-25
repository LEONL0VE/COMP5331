"""Brute-force radius queries. No clustering or neighbor-search package calls."""

from numbers import Integral
import numpy as np


def positive_integer(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def feature_matrix(X):
    try:
        values = np.array(X, dtype=float, copy=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("X must be a rectangular numeric matrix") from exc
    if values.ndim != 2 or 0 in values.shape or not np.isfinite(values).all():
        raise ValueError("X must be nonempty, two-dimensional and finite")
    return values


def distances_to(X, point):
    """Stable Euclidean norm; the input must use a meaningful feature scale."""
    with np.errstate(over="raise", invalid="raise"):
        try:
            return np.hypot.reduce(X - point, axis=1)
        except FloatingPointError as exc:
            raise ValueError("Coordinate range is too large; rescale the features") from exc


def radius_neighbors(X, eps):
    """Closed balls, including the query itself. O(n^2 d) time, no dense matrix."""
    return tuple(np.flatnonzero(distances_to(X, p) <= eps) for p in X)


def numerical_tolerance(eps):
    """Tolerance for checking constructed points, not for fitting DBSCAN."""
    return 1e-10 * max(1.0, float(eps))


def reachable_clusters(result, points, *, atol=0.0):
    points = np.asarray(points, dtype=float)
    if points.ndim == 1:
        points = points[None, :]
    if points.ndim != 2 or points.shape[1] != result.X.shape[1] or not np.isfinite(points).all():
        raise ValueError("Points must be finite and have the fitted feature dimension")
    if not np.isfinite(atol) or atol < 0:
        raise ValueError("atol must be finite and nonnegative")
    cores = result.core_indices
    return tuple(
        tuple(int(c) for c in np.unique(result.labels[cores[distances_to(result.X[cores], p) <= result.eps + atol]]))
        for p in points
    )
