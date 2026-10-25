"""Generate a readable report from actual validation/experiment evidence."""

import json
from _common import ROOT, require_mock_success, source_fingerprint


def read(name):
    return json.loads((ROOT / name).read_text())


def main():
    require_mock_success()
    validation = read('results/validation.json')
    rows = []
    evidence = []
    for name in ['mock', 'real']:
        gate = read(f'results/{name}_gate.json')
        summary = read(f'results/{name}_summary.json')
        if gate['source_fingerprint'] != source_fingerprint() or gate['status'] != 'passed':
            raise RuntimeError(f'{name} results are stale or failed')
        evidence.append((name, gate))
        rows.extend(s for s in summary['summaries'] if s['strategy'] == 'greedy')
    data = read('data/processed/usgs_southern_california_2024.json')
    lines = [
        '# Validation Report', '',
        f'Unit and property tests: **all {validation["tests_run"]} tests passed**.', '',
        'Generated from saved execution results by `python3 scripts/write_report.py`.', '',
        '## Validation Phases', '', '| Phase | Tests | Result |', '|---|---:|---|',
    ]
    for phase in validation['phases']:
        lines.append(f'| {phase["phase"]} | {phase["tests"]} | {"PASS" if phase["passed"] else "FAIL"} |')
    lines += ['', 'Coverage includes manual core/border/noise labels, 30 random graph-connectivity oracle cases,',
              'Dijkstra versus Floyd-Warshall, full-energy recomputation versus incremental greedy selection,',
              'combination enumeration, 100 random geometric projections, constrained ball cross-sections,',
              'unreachable targets, insufficient candidates, coincident points, shared borders, multiple',
              'cluster memberships, dependency blocking, and data cleaning.', '',
              'The dependency test runs both algorithms in a subprocess that rejects imports of sklearn, scipy, and networkx.', '',
              '## Experiment Counts', '']
    for name, gate in evidence:
        lines.append(f'- {name}: {gate["queries"]} queries, {gate["returned_counterfactuals"]} counterfactuals returned, '
                     f'{gate["valid_counterfactuals"]} independently validated as valid. Includes greedy, nearest, and random strategies.')
    lines += ['', '## ExDBSCAN Greedy Results', '',
              '| Dataset | Constraint | Queries | Complete Queries | Returned/Valid Points | Requested Coverage |',
              '|---|---|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f'| {row["dataset"]} | {row["constraint"]} | {row["queries"]} | '
                     f'{row["complete_queries"]} | {row["returned"]}/{row["valid"]} | '
                     f'{100 * row["requested_validity"]:.2f}% |')
    lines += ['', 'Valid returned points do not imply that every request can be completed. With immutable features,',
              'there may be no reachable target ball, or fewer than k feasible reference locations. Failed rows',
              'are retained. The two-moons tests with a fixed vertical coordinate are particularly prone to',
              'infeasibility. These geometric outcomes must not be omitted or reported as 100% query success.', '',
              '## Real-Data Snapshot', '',
              f'- Raw records: {data["raw_records"]}; records used: {data["processed_records"]}.',
              f'- Retrieved at (UTC): {data["retrieved_at"]}.',
              '- USGS Southern California earthquake locations from 2024, with a two-dimensional local projection in meters.',
              f'- Raw SHA-256: `{data["raw_sha256"]}`.', '',
              '## Reproducibility and Limitations', '',
              f'- Python: `{validation["python"].split()[0]}`; NumPy: `{validation["numpy"]}`.',
              f'- Fingerprint of source code, tests, scripts, and configurations: `{source_fingerprint()}`.',
              '- Parameters, seeds, and per-query metrics are saved in `configs/` and `results/`.',
              '- Greedy selection does not guarantee global optimality for k>1. Target-neighborhood reachability does not guarantee a unique label or the same assignment after reclustering.',
              '- See `method_spec.md` for graph-distance normalization and the DPP graph-structure proxy.',
              '- These runs validate algorithm correctness over a limited parameter grid; they do not reproduce the paper\'s complete datasets or performance conclusions.',
              '- The authors\' source code was not executed, and bitwise agreement with their implementation was not tested.', '']
    target = ROOT / 'docs' / 'validation_report.md'
    target.write_text('\n'.join(lines), encoding='utf-8')
    print(target)


if __name__ == '__main__':
    main()
