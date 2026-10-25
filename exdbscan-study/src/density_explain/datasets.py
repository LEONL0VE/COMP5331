"""Deterministic mock generators and transparent latitude/longitude conversion."""

import csv
from pathlib import Path
import numpy as np
from .neighbors import positive_integer


def mock_blobs(seed=7, n_per_cluster=40):
    rng = np.random.default_rng(seed)
    groups = [rng.normal(center, 0.12, size=(n_per_cluster, 2)) for center in [(-2, 0), (2, 0), (0, 2)]]
    noise = np.array([[0, 0], [0, -2], [4, 4], [-4, -4]], dtype=float)
    return np.vstack([*groups, noise])


def mock_moons(seed=7, n_per_cluster=60):
    rng = np.random.default_rng(seed)
    theta = np.linspace(0, np.pi, n_per_cluster)
    first = np.column_stack([np.cos(theta), np.sin(theta)])
    second = np.column_stack([1 - np.cos(theta), -np.sin(theta) - 0.35])
    return np.vstack([first, second]) + rng.normal(0, 0.015, (2 * n_per_cluster, 2))


def mock_rings(seed=7, n_per_cluster=70):
    rng = np.random.default_rng(seed)
    theta = np.linspace(0, 2 * np.pi, n_per_cluster, endpoint=False)
    circle = np.column_stack([np.cos(theta), np.sin(theta)])
    return np.vstack([circle, 2.1 * circle]) + rng.normal(0, 0.01, (2 * n_per_cluster, 2))


def mock_constraint_case():
    """Target near (3, .6), source at (0, 0): freezing y remains feasible."""
    return np.array([[3, .6], [3.1, .6], [3, .7], [2.9, .6], [3, .5], [0, 0]], float)


def geographic_to_local_meters(latitude, longitude, *, origin=(34.0, -118.0)):
    """Local equirectangular approximation, not a geodesic/road distance model.

    Origin and Earth radius are fixed and recorded for reproducibility. Intended
    for regional experiments, never for global longitude/latitude clustering.
    """
    lat = np.asarray(latitude, dtype=float)
    lon = np.asarray(longitude, dtype=float)
    if lat.ndim != 1 or lon.shape != lat.shape or not np.isfinite(lat).all() or not np.isfinite(lon).all():
        raise ValueError('Latitude and longitude must be equally sized finite vectors')
    if np.any(np.abs(lat) > 90) or np.any(np.abs(lon) > 180):
        raise ValueError('Invalid latitude or longitude')
    if len(origin) != 2 or not np.isfinite(origin).all() or abs(origin[0]) >= 90 or abs(origin[1]) > 180:
        raise ValueError('Origin must be a valid non-polar latitude/longitude pair')
    lat0, lon0 = np.deg2rad(origin)
    radius = 6_371_008.8
    x = radius * np.cos(lat0) * (np.deg2rad(lon) - lon0)
    y = radius * (np.deg2rad(lat) - lat0)
    return np.column_stack([x, y])


def load_usgs_csv(path, *, max_points=2000, origin=(34.0, -118.0)):
    """Remove invalid rows and repeated event IDs; retain genuine co-locations."""
    max_points = positive_integer(max_points, 'max_points')
    rows = []
    seen = set()
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            try:
                lat, lon = float(row["latitude"]), float(row["longitude"])
                if not np.isfinite([lat, lon]).all() or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    continue
                identifier = row["id"]
                if not identifier or not row['time'] or identifier in seen:
                    continue
                seen.add(identifier)
                rows.append((row["time"], identifier, lat, lon))
            except (KeyError, ValueError):
                continue
    rows.sort()
    if not rows:
        raise ValueError("No valid earthquake records in CSV")
    if len(rows) > max_points:
        selected = np.linspace(0, len(rows) - 1, max_points, dtype=int)
        rows = [rows[i] for i in selected]
    X = geographic_to_local_meters([r[2] for r in rows], [r[3] for r in rows], origin=origin)
    return X, [r[1] for r in rows]
