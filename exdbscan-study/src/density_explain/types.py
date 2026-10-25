"""Explicit result objects; arrays are detached and read-only snapshots."""

from dataclasses import dataclass
import numpy as np


def readonly(values, dtype=None):
    result = np.array(values, dtype=dtype, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class ClusteringResult:
    X: np.ndarray
    labels: np.ndarray
    core_mask: np.ndarray
    point_types: np.ndarray
    neighbor_counts: np.ndarray
    neighborhoods: tuple
    eps: float
    min_pts: int

    @property
    def core_indices(self):
        return np.flatnonzero(self.core_mask)

    @property
    def cluster_ids(self):
        return tuple(int(x) for x in np.unique(self.labels) if x >= 0)


@dataclass(frozen=True)
class SelectionStep:
    reference_index: int
    marginal_energy: float
    cumulative_energy: float


@dataclass(frozen=True)
class ExplanationResult:
    original: np.ndarray
    source_cluster: int
    requested_k: int
    target_cluster: int | None
    counterfactuals: np.ndarray
    reference_indices: np.ndarray
    target_labels: np.ndarray
    reachable_clusters: tuple
    unique_target_labels: np.ndarray
    immutable_features: tuple
    candidate_indices: np.ndarray
    selection_steps: tuple
    graph_distances: np.ndarray
    normalization_scale: float
    status: str
    reason: str

    @property
    def returned_k(self):
        return len(self.counterfactuals)

    @property
    def changes(self):
        return self.counterfactuals - self.original

    def to_dict(self):
        return {
            "original": self.original.tolist(),
            "source_cluster": self.source_cluster,
            "target_cluster": self.target_cluster,
            "requested_k": self.requested_k,
            "returned_k": self.returned_k,
            "counterfactuals": self.counterfactuals.tolist(),
            "changes": self.changes.tolist(),
            "reference_indices": self.reference_indices.tolist(),
            "target_labels": self.target_labels.tolist(),
            "reachable_clusters": [list(x) for x in self.reachable_clusters],
            "unique_target_labels": self.unique_target_labels.tolist(),
            "immutable_features": list(self.immutable_features),
            "candidate_indices": self.candidate_indices.tolist(),
            "selection_steps": [vars(s) for s in self.selection_steps],
            "graph_distances": [
                [float(x) if np.isfinite(x) else None for x in row]
                for row in self.graph_distances
            ],
            "normalization_scale": self.normalization_scale,
            "status": self.status,
            "reason": self.reason,
        }
