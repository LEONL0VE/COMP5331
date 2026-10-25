"""Original queue-expansion DBSCAN, following Ester et al. (1996)."""

from collections import deque
import numpy as np
from .neighbors import feature_matrix, positive_integer, radius_neighbors, reachable_clusters
from .types import ClusteringResult, readonly


class DBSCAN:
    """Euclidean DBSCAN. Shared borders go to the first discovered cluster.

    ``min_pts`` includes the query point. Fit uses exact ``distance <= eps``.
    No standardization or other transformation is performed implicitly.
    """

    def __init__(self, eps=0.5, min_pts=5):
        if isinstance(eps, (bool, np.bool_)) or not np.isscalar(eps):
            raise ValueError("eps must be a finite positive number")
        try:
            self.eps = float(eps)
        except (TypeError, ValueError) as exc:
            raise ValueError("eps must be a finite positive number") from exc
        if not np.isfinite(self.eps) or self.eps <= 0:
            raise ValueError("eps must be a finite positive number")
        self.min_pts = positive_integer(min_pts, "min_pts")

    def fit(self, X):
        X = feature_matrix(X)
        neighborhoods = radius_neighbors(X, self.eps)
        counts = np.array([len(v) for v in neighborhoods], dtype=int)
        core_mask = counts >= self.min_pts
        labels = np.full(len(X), -2, dtype=int)  # -2 unvisited; -1 noise
        cluster = 0
        for seed in range(len(X)):
            if labels[seed] != -2:
                continue
            if not core_mask[seed]:
                labels[seed] = -1
                continue
            labels[seed] = cluster
            queue = deque([seed])
            while queue:
                current = queue.popleft()
                for neighbor in neighborhoods[current]:
                    if labels[neighbor] == -1:
                        labels[neighbor] = cluster  # previously visited noise becomes border
                    elif labels[neighbor] == -2:
                        labels[neighbor] = cluster
                        if core_mask[neighbor]:
                            queue.append(int(neighbor))
            cluster += 1
        point_types = np.where(core_mask, "core", np.where(labels >= 0, "border", "noise"))
        self.result_ = ClusteringResult(
            readonly(X), readonly(labels), readonly(core_mask), readonly(point_types),
            readonly(counts), tuple(readonly(v) for v in neighborhoods), self.eps, self.min_pts,
        )
        self.X_ = self.result_.X
        self.labels_ = self.result_.labels
        self.core_mask_ = self.result_.core_mask
        self.core_indices_ = self.result_.core_indices
        self.point_types_ = self.result_.point_types
        self.neighbor_counts_ = self.result_.neighbor_counts
        return self

    def fit_predict(self, X):
        return self.fit(X).labels_.copy()

    def memberships(self, points, *, atol=0.0):
        """All reachable fixed clusters; this is explicitly NOT a DBSCAN refit."""
        if not hasattr(self, "result_"):
            raise ValueError("Call fit before memberships")
        return reachable_clusters(self.result_, points, atol=atol)
