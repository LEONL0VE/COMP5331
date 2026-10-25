# Experiment Scope

## Validation First

Validate DBSCAN, graph search, unconstrained ExDBSCAN, immutable-feature
constraints, dependency isolation, and data processing in that order.
DBSCAN tests use small cases with manually identifiable outcomes and an
independent oracle that first finds core connected components and then attaches
border points to check random data. Dijkstra results are compared with
Floyd-Warshall. Incremental greedy selection is compared with a version that
recomputes the full set energy at every iteration; combinations are also
enumerated on small graphs to check optimal energy. Projection residuals are
recomputed independently.

## Mock Data

- Three compact blobs with noise, two moons, and concentric rings.
- Fixed seeds 7 and 19; see `configs/mock.json` for epsilon and MinPts grids.
- k = 1, 3, and 5.
- Three selection strategies: ExDBSCAN greedy, nearest core points, and random
  core points with a fixed seed.
- Separate CSV exports for unconstrained queries and queries with dimension 1
  (the second feature) frozen.
- At most 12 query-point/target-cluster pairs per fit, sampled in round-robin
  order across source labels, with at most four target clusters.
- Queries made infeasible by constraints are part of the results; failed rows
  are retained.

## Real Spatial Data

- Historical USGS earthquake locations in Southern California, covering the
  full year 2024 with magnitude >= 2.
- Two features, (east_m, north_m), using a local equirectangular approximation
  with origin (34, -118).
- Explanations describe changes to a data point's location in clustering
  feature space; they are not recommendations for changing where a real
  earthquake occurs.
- Raw latitude and longitude are not used directly for Euclidean distances.
  The local approximation is not claimed to equal exact geodesic distance.
- epsilon = 2000, 5000, and 10000 meters; MinPts = 5, 10, and 20.
- k = 1, 3, and 5. Unconstrained results and mathematical constraint tests with
  north_m fixed are reported separately.
- Downloads are limited to 20 MB, with at most 2000 observations processed. If
  the service returns enough records to reach the query limit, the response is
  rejected as potentially incomplete. Actual record counts are recorded in the
  manifest produced by the preparation script.

## Success Criteria

1. All unit and property tests pass.
2. Every returned counterfactual independently passes target-reachability and
   immutable-feature checks.
3. Requested-explanation coverage is reported separately, including
   infeasibility, insufficient candidates, and overlapping boundaries.
4. Real-data validation follows successful mock validation.
5. Configurations, seeds, source fingerprints, data hashes, and per-query results
   are saved.

These experiments do not reproduce every numerical result in the paper.
Endpoint validity does not establish global optimality or general superiority
over baselines. Recorded timings mix cold-cache computation and cache reuse;
they are execution records, not a controlled performance benchmark.
