"""Datasets the explorer offers, and how their coordinates are placed on the map.

Each dataset keeps the coordinates the group's experiments cluster in: metres
east and north of 34°N, 118°W for the USGS catalogue, unitless values for the
synthetic shapes. The browser draws them through one affine map,
lon = lon0 + x * kx and lat = lat0 + y * ky. For USGS this is the exact inverse
of geographic_to_local_meters in density_explain.datasets, so an eps circle
drawn on the map is the same circle DBSCAN uses.
"""

from collections import Counter
import csv
from dataclasses import dataclass
import math
from pathlib import Path
import re

import numpy as np

from density_explain.datasets import mock_blobs, mock_moons, mock_rings

STUDY_DIR = Path(__file__).resolve().parents[2] / "exdbscan-study"
EARTH_RADIUS_M = 6_371_008.8   # same constant as density_explain.datasets
USGS_ORIGIN = (34.0, -118.0)   # same origin as configs/real.json


@dataclass(frozen=True)
class Dataset:
    id: str
    name: str
    summary: str
    kind: str           # "geo" sits on the basemap, "plane" on a blank canvas
    noun: tuple         # singular and plural, used in interface sentences
    X: np.ndarray
    unit: str           # "m" for metres, "" for unitless coordinates
    eps: dict           # default, min, max and step, in data units
    min_pts: dict       # default, min and max
    affine: dict
    moves: tuple        # (feature kept fixed, label) for each direction the interface offers
    meta: tuple = ()    # per-point details for geo data

    def describe(self):
        lon = self.affine["lon0"] + self.X[:, 0] * self.affine["kx"]
        lat = self.affine["lat0"] + self.X[:, 1] * self.affine["ky"]
        pad_lon = (lon.max() - lon.min()) * 0.04
        pad_lat = (lat.max() - lat.min()) * 0.04
        return {
            "id": self.id,
            "name": self.name,
            "summary": self.summary,
            "kind": self.kind,
            "noun": list(self.noun),
            "count": len(self.X),
            "unit": self.unit,
            "eps": self.eps,
            "minPts": self.min_pts,
            "affine": self.affine,
            "bounds": [[float(lon.min() - pad_lon), float(lat.min() - pad_lat)],
                       [float(lon.max() + pad_lon), float(lat.max() + pad_lat)]],
            "moves": [{"fixed": fixed, "label": label} for fixed, label in self.moves],
        }

    def points(self):
        decimals = 1 if self.unit == "m" else 6
        return {"xy": np.round(self.X, decimals).tolist(), "meta": list(self.meta) or None}


def _usgs():
    data = np.load(STUDY_DIR / "data" / "processed" / "usgs_southern_california_2024.npz", allow_pickle=False)
    ids = [str(i) for i in data["event_ids"]]
    with (STUDY_DIR / "data" / "raw" / "usgs_southern_california_2024.csv").open(newline="", encoding="utf-8-sig") as stream:
        rows = {row["id"]: row for row in csv.DictReader(stream)}
    meta = tuple(
        {"mag": round(float(rows[i]["mag"]), 1), "depth": round(float(rows[i]["depth"]), 1),
         "date": rows[i]["time"][:10], "place": rows[i]["place"]}
        for i in ids
    )
    lat0, lon0 = USGS_ORIGIN
    return Dataset(
        id="usgs",
        name="Southern California 2024",
        summary=f"{len(ids):,} earthquakes of magnitude 2 or more",
        kind="geo",
        noun=("quake", "quakes"),
        X=data["X"].astype(float),
        unit="m",
        eps={"default": 5000, "min": 1000, "max": 20000, "step": 500},
        min_pts={"default": 10, "min": 3, "max": 40},
        affine={"lon0": lon0, "lat0": lat0,
                "kx": math.degrees(1 / (EARTH_RADIUS_M * math.cos(math.radians(lat0)))),
                "ky": math.degrees(1 / EARTH_RADIUS_M)},
        moves=((1, "East–west"), (0, "North–south")),
        meta=meta,
    )


def _shape(id, name, X, eps, min_pts):
    return Dataset(
        id=id,
        name=name,
        summary=f"{len(X)} synthetic points",
        kind="plane",
        noun=("point", "points"),
        X=np.asarray(X, dtype=float),
        unit="",
        eps=eps,
        min_pts=min_pts,
        affine={"lon0": 0.0, "lat0": 0.0, "kx": 1.0, "ky": 1.0},
        moves=((1, "Sideways"), (0, "Up–down")),
    )


DATASETS = {d.id: d for d in (
    _usgs(),
    _shape("rings", "Rings", mock_rings(seed=7),
           {"default": 0.22, "min": 0.1, "max": 0.6, "step": 0.02}, {"default": 5, "min": 2, "max": 12}),
    _shape("moons", "Two moons", mock_moons(seed=7),
           {"default": 0.16, "min": 0.06, "max": 0.4, "step": 0.01}, {"default": 5, "min": 2, "max": 12}),
    _shape("blobs", "Blobs", mock_blobs(seed=7),
           {"default": 0.4, "min": 0.1, "max": 1.0, "step": 0.05}, {"default": 4, "min": 2, "max": 12}),
)}


def _town(place):
    """'24 km SW of Lamont, CA' -> 'Lamont'; '9 km NNW of Delta, B.C., MX' -> 'Delta, Mexico'."""
    match = re.search(r" of (.+)$", place)
    town = match.group(1) if match else place
    if town.endswith(", CA"):
        return town[:-4]
    if town.endswith(", MX"):
        return f"{town.split(', ')[0]}, Mexico"
    return town


def cluster_names(dataset, labels):
    """Readable cluster names: the most common nearby town for geo data, numbers otherwise."""
    ids = [int(c) for c in np.unique(labels) if c >= 0]
    if dataset.kind != "geo":
        return {c: f"Cluster {c + 1}" for c in ids}
    names = {c: Counter(_town(dataset.meta[i]["place"]) for i in np.flatnonzero(labels == c)).most_common(1)[0][0]
             for c in ids}
    by_name = {}
    for c in sorted(ids, key=lambda c: -int((labels == c).sum())):
        by_name.setdefault(names[c], []).append(c)
    for name, group in by_name.items():
        for rank, c in enumerate(group[1:], start=2):
            names[c] = f"{name} {rank}"
    return names
