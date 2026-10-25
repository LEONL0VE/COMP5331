"""Core adjacency construction and a heap-based Dijkstra implementation."""

from collections import OrderedDict
import heapq
import numpy as np
from .neighbors import distances_to


def dijkstra(adjacency, source):
    """Nonnegative weighted adjacency list -> shortest paths; unreachable = inf."""
    n = len(adjacency)
    if not 0 <= source < n:
        raise ValueError("source is outside the graph")
    result = np.full(n, np.inf)
    result[source] = 0.0
    frontier = [(0.0, int(source))]
    while frontier:
        cost, node = heapq.heappop(frontier)
        if cost > result[node]:
            continue
        for neighbor, weight in adjacency[node]:
            if weight < 0 or not np.isfinite(weight):
                raise ValueError("Dijkstra requires finite nonnegative edge weights")
            alternative = cost + weight
            if alternative < result[neighbor]:
                result[neighbor] = alternative
                heapq.heappush(frontier, (alternative, int(neighbor)))
    return result


class CoreGraph:
    """Only same-cluster eligible cores are connected, with closed epsilon edges."""

    def __init__(self, X, indices, labels, eps, max_cached_rows=16):
        self.indices = np.asarray(indices, dtype=int).copy()
        points = X[self.indices]
        cluster_labels = labels[self.indices]
        adjacency = [[] for _ in points]
        weights = []
        for i in range(len(points)):
            lengths = distances_to(points[i + 1:], points[i])
            for offset in np.flatnonzero(lengths <= eps):
                j = i + 1 + int(offset)
                if cluster_labels[i] != cluster_labels[j]:
                    continue
                weight = float(lengths[offset])
                adjacency[i].append((j, weight))
                adjacency[j].append((i, weight))
                if weight > 0:
                    weights.append(weight)
        self.adjacency = tuple(tuple(row) for row in adjacency)
        self.mean_positive_edge_weight = float(np.mean(weights)) if weights else None
        self.edge_count = sum(map(len, adjacency)) // 2
        self.max_cached_rows = max_cached_rows
        self._rows = OrderedDict()

    def distances_from(self, source):
        if source in self._rows:
            self._rows.move_to_end(source)
            return self._rows[source]
        row = dijkstra(self.adjacency, source)
        row.setflags(write=False)
        self._rows[source] = row
        while len(self._rows) > self.max_cached_rows:
            self._rows.popitem(last=False)
        return row


def inverse_distances(distances, scale=1.0):
    """1 / scaled path length; disconnected pairs have no repulsion penalty."""
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("Distance scale must be finite and positive")
    distances = np.asarray(distances, dtype=float)
    if np.any(distances < 0) or np.isnan(distances).any():
        raise ValueError("Distances must be nonnegative or +inf")
    result = np.zeros_like(distances)
    positive = np.isfinite(distances) & (distances > 0)
    result[positive] = 1.0 / distances[positive] / scale
    result[distances == 0] = np.inf
    return result


def set_energy(local_indices, attraction, graph, scale=1.0):
    """Reference objective, useful for exhaustive checks on tiny candidate sets."""
    selected = list(local_indices)
    value = float(np.sum(attraction[selected]))
    for pos, q in enumerate(selected):
        if pos:
            value += float(np.sum(inverse_distances(graph.distances_from(q)[selected[:pos]], scale)))
    return value
