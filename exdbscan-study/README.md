# DBSCAN / ExDBSCAN Algorithm Reproduction

This project implements and validates both algorithms. Its scope is algorithm
reproduction, without an interactive system, user interface, or integration layer.
The only runtime dependency is **NumPy**; tests use Python's standard-library
**unittest** framework. DBSCAN, the core-point graph, Dijkstra's algorithm, energy
optimization, and counterfactual generation are implemented in this project.
**The implementation never calls `sklearn.DBSCAN` and does not depend on
scikit-learn, SciPy, or NetworkX.**

## Quick Start

Requirements: Python 3.10+ and NumPy 1.24+. Run these commands from this directory:

```bash
# Only needed if NumPy is not already installed:
python3 -m pip install numpy

# Validate DBSCAN, graph algorithms, ExDBSCAN, constraints, and data processing
python3 scripts/run_validation.py

# Run small examples that can be checked manually
python3 examples/demo_dbscan.py
python3 examples/demo_exdbscan.py

# Run experiments on three types of mock data first
python3 scripts/run_experiments.py --dataset mock

# Prepare and evaluate real spatial data after mock validation succeeds
python3 scripts/prepare_real_data.py
python3 scripts/run_experiments.py --dataset real

# Generate the validation report from the saved results
python3 scripts/write_report.py
```

The scripts add `src/` to the import path automatically; installing this project
is optional. To import it from other programs:

```bash
python3 -m pip install -e .
```

When the real-data snapshot is already present, `prepare_real_data.py` checks its
hash and reuses the local files without a network request. Tests and mock
experiments require no network access. After changing source code or tests,
rerun validation and mock experiments; the real-data stage checks the current
source fingerprint.

## Usage

```python
from density_explain import DBSCAN, ExDBSCAN
from density_explain.datasets import mock_constraint_case
from density_explain.metrics import evaluate_explanation

X = mock_constraint_case()
model = DBSCAN(eps=1.0, min_pts=3).fit(X)

print(model.labels_)
print(model.point_types_)       # core / border / noise
print(model.neighbor_counts_)   # Includes the point itself

explainer = ExDBSCAN(model)

# Unconstrained: move a noise point into a specified target cluster
plain = explainer.explain(point_index=5, target_cluster=0, k=3)

# Constrained: keep dimension 1 (the second feature) exactly unchanged
fixed = explainer.explain(
    point_index=5, target_cluster=0, k=3, immutable_features=[1]
)

print(fixed.counterfactuals)
print(fixed.changes)
print(fixed.reference_indices)
print(evaluate_explanation(model.result_, fixed))
```

Additional options:

- `point=[...]`: explain an external query point. Supply either `point` or
  `point_index`, not both.
- `target_cluster=None`: select target core points from other clusters that are
  not already reachable from the query point.
- `normalization="none"`: use the unscaled energy equation. The default,
  `"paper"`, applies the paper's scale adjustment.
- `strategy="nearest"` / `"random"`: independently implemented baseline selection
  strategies that share the same geometric construction. The default,
  `"greedy"`, is ExDBSCAN. Set `random_state` for reproducible random selection.

## Results and Failure Semantics

`ExplanationResult` contains the original point, counterfactuals, target labels,
reference points, candidates, energy at each iteration, graph distances between
reference points, and all reachable clusters. `to_dict()` produces a structure
that can be saved as strict JSON.

| Status | Meaning |
|---|---|
| `ok` | The requested number of distinct explanations was returned. |
| `partial` | There are too few distinct core locations, or constrained projections coincide. Results are not padded with duplicates. |
| `infeasible` | No target core point is available, or immutable features make all target balls unreachable. |
| `already_reachable` | The query point is already within a target core neighborhood, so no position change is fabricated. |

Invalid inputs, such as a nonexistent target cluster, a target equal to the
source cluster, NaN values, or invalid feature indices, raise `ValueError`.
Infeasibility is a normal result status, not an exception.

Validity means that **the counterfactual lies within the epsilon neighborhood
of a target core point while the original clustering remains fixed**. This does
not imply the same assignment after changing the dataset and rerunning DBSCAN,
or a unique cluster label in an overlapping boundary region.
`reachable_clusters` reports all possible memberships; `unique_target_labels`
separately indicates unique membership.

## Project Layout

| File | Responsibility |
|---|---|
| `src/density_explain/dbscan.py` | DBSCAN cluster expansion using a queue |
| `src/density_explain/neighbors.py` | Neighborhood queries and membership queries against fixed core points |
| `src/density_explain/graph.py` | Core-point graph, Dijkstra's algorithm, and reference energy calculation |
| `src/density_explain/exdbscan.py` | Candidate filtering, incremental greedy selection, and counterfactual generation |
| `src/density_explain/constraints.py` | Reachability and projection with immutable features |
| `src/density_explain/metrics.py` | Independent endpoint validation and explanation quality metrics |
| `tests/` | Manual cases, independent oracles, geometry tests, and edge cases |
| `configs/` | Fixed experiment parameters for mock and real data |
| `docs/method_spec.md` | Correspondence with the papers, ambiguities, and numerical conventions |
| `docs/validation_report.md` | Summary of actual execution results |
| `docs/references.md` | Sources and implementation provenance |

## Validation and Experiment Results

For figures explaining the implemented functionality and the measured results,
see [Visual Results](docs/visual_results.md). The gallery covers DBSCAN clusters,
ExDBSCAN reference selection and projection, immutable-feature constraints,
experiment coverage, and a real-data example. All figures are available as PNG
and editable SVG files in `results/figures/`.

The complete report is also available as a
[LaTeX-rendered PDF](docs/visual_results_pdf/visual_results.pdf), with editable
[LaTeX source and compilation instructions](docs/visual_results_pdf/README.md).

To regenerate them after the validation and experiment commands above:

```bash
# Optional rendering dependency; the algorithms still require only NumPy
python3 -m pip install matplotlib
python3 examples/plot_results.py
```

`results/validation.log` and `results/validation.json` record test results.
Mock and real-data experiments each generate the following files, with
constrained results recorded separately:

```text
results/{mock,real}_unconstrained.csv
results/{mock,real}_immutable.csv
results/{mock,real}_summary.json
results/{mock,real}_examples.json
```

Both the validity of returned points and the coverage of the requested number
of explanations are reported. A query is not counted as fully successful merely
because its returned points are valid when fewer than the requested number are
available. Evaluation independently recomputes distances for every endpoint.

This project reproduces the algorithms and performs small-scale validation; it
does not reproduce the paper's complete experiments on 30 OpenML datasets and
all baselines. The implementation supports Euclidean space and equality
constraints on immutable features. It makes no claim to support categorical
variables, feasible road routes, or causal interventions.
