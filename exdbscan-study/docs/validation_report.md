# Validation Report

Unit and property tests: **all 52 tests passed**.

Generated from saved execution results by `python3 scripts/write_report.py`.

## Validation Phases

| Phase | Tests | Result |
|---|---:|---|
| dbscan | 12 | PASS |
| graph | 5 | PASS |
| exdbscan | 17 | PASS |
| constraints | 11 | PASS |
| dependencies | 1 | PASS |
| datasets | 6 | PASS |

Coverage includes manual core/border/noise labels, 30 random graph-connectivity oracle cases,
Dijkstra versus Floyd-Warshall, full-energy recomputation versus incremental greedy selection,
combination enumeration, 100 random geometric projections, constrained ball cross-sections,
unreachable targets, insufficient candidates, coincident points, shared borders, multiple
cluster memberships, dependency blocking, and data cleaning.

The dependency test runs both algorithms in a subprocess that rejects imports of sklearn, scipy, and networkx.

## Experiment Counts

- mock: 2880 queries, 6318 counterfactuals returned, 6318 independently validated as valid. Includes greedy, nearest, and random strategies.
- real: 1944 queries, 3234 counterfactuals returned, 3234 independently validated as valid. Includes greedy, nearest, and random strategies.

## ExDBSCAN Greedy Results

| Dataset | Constraint | Queries | Complete Queries | Returned/Valid Points | Requested Coverage |
|---|---|---:|---:|---:|---:|
| blobs | immutable | 288 | 144 | 432/432 | 50.00% |
| blobs | unconstrained | 288 | 288 | 864/864 | 100.00% |
| moons | immutable | 96 | 0 | 0/0 | 0.00% |
| moons | unconstrained | 96 | 96 | 288/288 | 100.00% |
| rings | immutable | 96 | 76 | 234/234 | 81.25% |
| rings | unconstrained | 96 | 96 | 288/288 | 100.00% |
| usgs_southern_california_2024 | immutable | 324 | 33 | 106/106 | 10.91% |
| usgs_southern_california_2024 | unconstrained | 324 | 324 | 972/972 | 100.00% |

Valid returned points do not imply that every request can be completed. With immutable features,
there may be no reachable target ball, or fewer than k feasible reference locations. Failed rows
are retained. The two-moons tests with a fixed vertical coordinate are particularly prone to
infeasibility. These geometric outcomes must not be omitted or reported as 100% query success.

## Real-Data Snapshot

- Raw records: 1260; records used: 1260.
- Retrieved at (UTC): 2026-10-25T20:23:14.227418+00:00.
- USGS Southern California earthquake locations from 2024, with a two-dimensional local projection in meters.
- Raw SHA-256: `62b2b45b84da2d44355b4b54dbc58f4a9aa33ffedd71523672c8dc7e2539553e`.

## Reproducibility and Limitations

- Python: `3.12.14`; NumPy: `2.3.5`.
- Fingerprint of source code, tests, scripts, and configurations: `a5f287279c096457100a80c50c3f53bec59da51f2d4abf07178977c9e74df769`.
- Parameters, seeds, and per-query metrics are saved in `configs/` and `results/`.
- Greedy selection does not guarantee global optimality for k>1. Target-neighborhood reachability does not guarantee a unique label or the same assignment after reclustering.
- See `method_spec.md` for graph-distance normalization and the DPP graph-structure proxy.
- These runs validate algorithm correctness over a limited parameter grid; they do not reproduce the paper's complete datasets or performance conclusions.
- The authors' source code was not executed, and bitwise agreement with their implementation was not tested.
