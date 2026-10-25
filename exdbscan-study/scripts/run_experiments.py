"""Reproducible mock-first experiments; constrained and unconstrained CSVs are separate."""

import argparse
from collections import Counter
import csv
import hashlib
import json
from time import perf_counter
import numpy as np
from _common import ROOT, require_mock_success, require_validation, save_json, source_fingerprint, timestamp
from density_explain import DBSCAN, ExDBSCAN
from density_explain.datasets import mock_blobs, mock_moons, mock_rings
from density_explain.metrics import evaluate_explanation


def query_pairs(model, limit):
    """Up to two observations per source label, at most four target clusters."""
    pairs = []
    for source in np.unique(model.labels_):
        indices = np.flatnonzero(model.labels_ == source)
        selected = indices[np.unique(np.linspace(0, len(indices) - 1, min(2, len(indices)), dtype=int))]
        for index in selected:
            for target in model.result_.cluster_ids[:4]:
                if target != source:
                    pairs.append((int(index), int(target)))
    # Round-robin source labels prevents all-noise queries consuming the budget.
    buckets = {}
    for pair in pairs:
        source = int(model.labels_[pair[0]])
        buckets.setdefault(source, []).append(pair)
    ordered = []
    while buckets and len(ordered) < limit:
        for source in list(buckets):
            ordered.append(buckets[source].pop(0))
            if not buckets[source]:
                del buckets[source]
            if len(ordered) == limit:
                break
    return ordered


def summarize(rows):
    summaries = []
    groups = sorted({(r['dataset'], r['strategy'], r['constraint']) for r in rows})
    for dataset, strategy, constraint in groups:
        group = [r for r in rows if (r['dataset'], r['strategy'], r['constraint']) == (dataset, strategy, constraint)]
        returned, valid = sum(r['returned_k'] for r in group), sum(r['valid_count'] for r in group)
        requested = sum(r['requested_k'] for r in group)
        proximities = [r['mean_proximity'] for r in group if r['mean_proximity'] is not None]
        summaries.append({
            'dataset': dataset, 'strategy': strategy, 'constraint': constraint,
            'queries': len(group), 'requested': requested, 'returned': returned, 'valid': valid,
            'returned_validity': valid / returned if returned else 0,
            'requested_validity': valid / requested if requested else 0,
            'complete_queries': sum(r['complete'] for r in group),
            'status_counts': dict(Counter(r['status'] for r in group)),
            'mean_query_proximity': float(np.mean(proximities)) if proximities else None,
            'total_query_seconds': sum(r['elapsed_seconds'] for r in group),
        })
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', choices=['mock', 'real'], required=True)
    args = parser.parse_args()
    require_validation()
    if args.dataset == 'real':
        require_mock_success()
    config = json.loads((ROOT / 'configs' / f'{args.dataset}.json').read_text())
    if args.dataset == 'mock':
        generators = {'blobs': mock_blobs, 'moons': mock_moons, 'rings': mock_rings}
        datasets = [(name, seed, generator(seed), config['datasets'][name])
                    for name, generator in generators.items() for seed in config['seeds']]
    else:
        processed = ROOT / 'data' / 'processed' / 'usgs_southern_california_2024.npz'
        manifest = ROOT / 'data' / 'processed' / 'usgs_southern_california_2024.json'
        if not processed.exists():
            raise RuntimeError('Run python scripts/prepare_real_data.py first')
        metadata = json.loads(manifest.read_text())
        if hashlib.sha256(processed.read_bytes()).hexdigest() != metadata['processed_sha256']:
            raise RuntimeError('Processed data differs from its manifest')
        X = np.load(processed)['X']
        datasets = [(config['dataset'], config['seed'], X, config)]
    rows, fits, examples = [], [], {}
    for name, seed, X, parameters in datasets:
        for eps in parameters['eps']:
            for minimum in parameters['min_pts']:
                start = perf_counter()
                model = DBSCAN(eps, minimum).fit(X)
                elapsed_fit = perf_counter() - start
                pairs = query_pairs(model, config['max_queries_per_fit'])
                fits.append({'dataset': name, 'seed': seed, 'n': len(X), 'eps': eps, 'min_pts': minimum,
                             'clusters': len(model.result_.cluster_ids), 'core_points': int(model.core_mask_.sum()),
                             'noise_points': int((model.labels_ < 0).sum()), 'queries': len(pairs),
                             'fit_seconds': elapsed_fit})
                explainer = ExDBSCAN(model)
                for constraint, immutable in [('unconstrained', ()), ('immutable', tuple(config['immutable_features']))]:
                    for index, target in pairs:
                        for k in config['k']:
                            for strategy in config['strategies']:
                                start = perf_counter()
                                result = explainer.explain(index, target_cluster=target, k=k,
                                                           immutable_features=immutable, strategy=strategy,
                                                           random_state=seed)
                                seconds = perf_counter() - start
                                metrics = evaluate_explanation(model.result_, result)
                                if metrics['valid_count'] != result.returned_k or not metrics['immutable_preserved']:
                                    raise AssertionError('An independently verified endpoint is invalid')
                                rows.append({'dataset': name, 'seed': seed, 'eps': eps, 'min_pts': minimum,
                                             'point_index': index, 'source_cluster': result.source_cluster,
                                             'target_cluster': target, 'strategy': strategy, 'constraint': constraint,
                                             'elapsed_seconds': seconds, **metrics})
                                key = f'{name}_{constraint}'
                                if key not in examples and strategy == 'greedy' and k == 3 and result.status == 'ok':
                                    examples[key] = {'eps': eps, 'min_pts': minimum, 'seed': seed,
                                                     'point_index': index, 'explanation': result.to_dict()}
                print(f'{name} seed={seed} eps={eps} min_pts={minimum}: '
                      f'{len(model.result_.cluster_ids)} clusters, {len(pairs)} query pairs', flush=True)
    if not rows or not any(r['valid_count'] for r in rows):
        raise RuntimeError('No valid counterfactuals were exercised; cannot mark the experiment passed')
    for constraint in ['unconstrained', 'immutable']:
        selected = [r for r in rows if r['constraint'] == constraint]
        if not any(r['valid_count'] for r in selected):
            raise RuntimeError(f'No successful {constraint} query was exercised')
        path = ROOT / 'results' / f'{args.dataset}_{constraint}.csv'
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(selected[0]))
            writer.writeheader()
            writer.writerows(selected)
    save_json(ROOT / 'results' / f'{args.dataset}_summary.json', {
        'created_at': timestamp(), 'source_fingerprint': source_fingerprint(),
        'config': config, 'fits': fits, 'summaries': summarize(rows),
        'all_returned_points_valid': True,
        'note': 'Timing includes cache misses and is not a controlled performance benchmark. '
                'DPP reference-graph uses reference cores; Euclidean DPP uses endpoints.',
    })
    save_json(ROOT / 'results' / f'{args.dataset}_examples.json', examples)
    save_json(ROOT / 'results' / f'{args.dataset}_gate.json', {
        'status': 'passed', 'created_at': timestamp(), 'source_fingerprint': source_fingerprint(),
        'queries': len(rows), 'returned_counterfactuals': sum(r['returned_k'] for r in rows),
        'valid_counterfactuals': sum(r['valid_count'] for r in rows),
    })
    print(f'PASS: {len(rows)} queries, {sum(r["returned_k"] for r in rows)} valid returned points')


if __name__ == '__main__':
    main()
