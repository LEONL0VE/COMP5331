"""Create English PNG/SVG figures from verified results and live algorithm outputs.

Optional plotting dependency: python3 -m pip install matplotlib
Run from the project root: python3 examples/plot_results.py
Matplotlib is used only for rendering, never for clustering or explanations.
"""

import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'exdbscan-matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME', str(Path(tempfile.gettempdir()) / 'exdbscan-render-cache'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle
import numpy as np

from _common import require_mock_success, save_json, source_fingerprint, timestamp
from density_explain import DBSCAN, ExDBSCAN
from density_explain.datasets import mock_blobs, mock_moons, mock_rings, mock_constraint_case
from density_explain.graph import CoreGraph
from density_explain.metrics import evaluate_explanation

OUT = ROOT / 'results' / 'figures'
INK = '#18283b'
BLUE = '#1976a3'
TEAL = '#168c7c'
ORANGE = '#df7b23'
PURPLE = '#8255a5'
GRAY = '#a5aeb9'
RED = '#c54848'
COLORS = [BLUE, TEAL, PURPLE, ORANGE, '#af637b']
CF_COLORS = [ORANGE, PURPLE, TEAL]
EVIDENCE = {}


def read(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))


def style():
    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': 10,
        'axes.titlesize': 12, 'axes.labelsize': 10,
        'figure.titlesize': 17, 'text.color': INK,
        'axes.labelcolor': INK, 'xtick.color': INK, 'ytick.color': INK,
        'axes.spines.top': False, 'axes.spines.right': False,
        'axes.edgecolor': '#c1cad3', 'axes.axisbelow': True,
        'grid.color': '#e7ebef', 'grid.linewidth': .7,
        'savefig.facecolor': 'white', 'svg.fonttype': 'none',
    })


def finish(fig, name, title, subtitle, bottom=.19):
    fig.suptitle(title, x=.055, y=.98, ha='left', fontweight='bold')
    fig.text(.055, .915, subtitle, ha='left', fontsize=10, color='#536478')
    fig.subplots_adjust(left=.07, right=.97, bottom=bottom, top=.80, wspace=.30)
    for ext in ('png', 'svg'):
        fig.savefig(OUT / f'{name}.{ext}', dpi=180)
    plt.close(fig)


def axes_xy(ax, xlabel='Feature 0', ylabel='Feature 1'):
    ax.set(xlabel=xlabel, ylabel=ylabel)
    ax.set_aspect('equal', adjustable='box')
    ax.grid(True)


def scatter_clusters(ax, model, scale=1, size=21):
    r = model.result_
    for label in r.cluster_ids:
        color = COLORS[label % len(COLORS)]
        for core in (True, False):
            keep = (r.labels == label) & (r.core_mask == core)
            ax.scatter(*((r.X[keep] / scale).T), s=size if core else size * 1.3,
                       facecolors=color if core else 'none', edgecolors=color,
                       linewidths=.7, alpha=.8, zorder=3)
    noise = r.labels == -1
    ax.scatter(*((r.X[noise] / scale).T), s=size * 1.1, marker='x',
               color=GRAY, linewidths=1, zorder=2)


def point_legend():
    return [
        Line2D([], [], marker='o', ls='', color=BLUE, label='Core point'),
        Line2D([], [], marker='o', ls='', markerfacecolor='none', color=BLUE, label='Border point'),
        Line2D([], [], marker='x', ls='', color=GRAY, label='Noise'),
    ]


def verified_example(key, X, saved):
    model = DBSCAN(eps=saved['eps'], min_pts=saved['min_pts']).fit(X)
    expected = saved['explanation']
    result = ExDBSCAN(model).explain(
        saved['point_index'], target_cluster=expected['target_cluster'],
        k=expected['requested_k'], immutable_features=expected['immutable_features'])
    np.testing.assert_allclose(result.counterfactuals, expected['counterfactuals'], rtol=1e-10, atol=1e-8)
    np.testing.assert_array_equal(result.reference_indices, expected['reference_indices'])
    metrics = evaluate_explanation(model.result_, result)
    assert metrics['valid_count'] == result.returned_k
    EVIDENCE[key] = {'saved_example_reproduced': True, 'parameters': {
        k: saved[k] for k in ('seed', 'eps', 'min_pts', 'point_index')},
        'explanation': result.to_dict(), 'metrics': metrics}
    return model, result


def clustering_figure():
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 5.2))
    cases = [('Blobs + noise', mock_blobs, .25, 4),
             ('Two moons', mock_moons, .16, 3),
             ('Concentric rings', mock_rings, .3, 3)]
    # Use representative settings from the existing parameter grid.
    for ax, (name, generator, eps, min_pts) in zip(axes, cases):
        model = DBSCAN(eps=eps, min_pts=min_pts).fit(generator(seed=7))
        r = model.result_
        counts = {kind: int(np.sum(r.point_types == kind)) for kind in ('core', 'border', 'noise')}
        scatter_clusters(ax, model)
        ax.set_title(f'{name}\neps={eps}, MinPts={min_pts}', loc='left')
        axes_xy(ax)
        ax.text(.5, -.28, f'{len(r.cluster_ids)} clusters | {counts["core"]} core | '
                f'{counts["border"]} border | {counts["noise"]} noise',
                transform=ax.transAxes, ha='center', fontsize=9)
        EVIDENCE[name] = {'seed': 7, 'eps': eps, 'min_pts': min_pts,
                          'clusters': len(r.cluster_ids), 'point_types': counts}
    fig.legend(handles=point_legend(), loc='lower center', ncol=3, frameon=False,
               bbox_to_anchor=(.5, .015))
    finish(fig, '01_dbscan', 'DBSCAN: density, shape, and noise',
           'Actual outputs of our implementation. Colors indicate discovered clusters; shapes indicate point types.', bottom=.26)


def graph_path(graph, source, target):
    """Recover a path from our Dijkstra distance labels, without another graph package."""
    distances = graph.distances_from(source)
    assert np.isfinite(distances[target])
    path = [target]
    while path[-1] != source:
        current = path[-1]
        predecessors = [i for i, weight in graph.adjacency[current]
                        if distances[i] < distances[current]
                        and np.isclose(distances[i] + weight, distances[current], rtol=1e-10, atol=1e-12)]
        assert predecessors, 'Cannot recover shortest path from distance labels'
        path.append(min(predecessors, key=lambda i: distances[i]))
    return path[::-1]


def method_figure():
    saved = read('results/mock_examples.json')['moons_unconstrained']
    model, result = verified_example('moons_counterfactuals', mock_moons(saved['seed']), saved)
    X, p = model.result_.X, result.original
    graph = CoreGraph(X, result.candidate_indices, model.labels_, model.eps)
    local = [int(np.flatnonzero(graph.indices == i)[0]) for i in result.reference_indices]
    path = graph_path(graph, local[0], local[1])
    path_points = X[graph.indices[path]]
    graph_distance = float(graph.distances_from(local[0])[local[1]])
    np.testing.assert_allclose(np.linalg.norm(np.diff(path_points, axis=0), axis=1).sum(), graph_distance)
    np.testing.assert_allclose(result.graph_distances[0, 1], graph_distance)
    straight_distance = float(np.linalg.norm(X[result.reference_indices[0]] - X[result.reference_indices[1]]))
    EVIDENCE['moons_counterfactuals']['path_comparison'] = {
        'reference_pair': result.reference_indices[:2].tolist(),
        'dijkstra_path_indices': graph.indices[path].tolist(),
        'graph_distance': graph_distance, 'euclidean_distance': straight_distance}
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 6.0))
    for ax in axes:
        other = model.labels_ != result.target_cluster
        ax.scatter(*X[other].T, s=15, color=GRAY, alpha=.45)
        ax.scatter(*X[result.candidate_indices].T, s=16, color=BLUE, alpha=.7)
        ax.scatter(*p, marker='D', s=70, color=RED, zorder=8)
        ax.annotate('Query p', p, xytext=(7, 10), textcoords='offset points', color=RED)
        axes_xy(ax)
        ax.set(xlim=(-.25, 2.28), ylim=(-1.62, 1.2))
    segments = [(X[graph.indices[i]], X[graph.indices[j]])
                for i, row in enumerate(graph.adjacency) for j, _ in row if i < j]
    axes[0].add_collection(LineCollection(segments, colors=GRAY, linewidths=.5, alpha=.45))
    axes[0].plot(*path_points.T, color=ORANGE, linewidth=2.6, zorder=4)
    axes[0].plot(*X[result.reference_indices[:2]].T, color=INK, ls=':', lw=1.2)
    axes[0].set_title('1. Select diverse reference cores', loc='left')
    axes[1].set_title('2. Project onto their epsilon balls', loc='left')
    for number, (index, cf, color) in enumerate(zip(result.reference_indices, result.counterfactuals, CF_COLORS), 1):
        q = X[index]
        axes[0].scatter(*q, s=90, marker='s', facecolors='none', edgecolors=color, linewidths=1.8, zorder=6)
        axes[0].annotate(f'q{number}', q, xytext=(-15, -19), textcoords='offset points', color=color, fontweight='bold')
        axes[1].add_patch(Circle(q, model.eps, fill=False, edgecolor=color, lw=1.4, alpha=.9))
        axes[1].scatter(*q, s=38, marker='s', color=color, zorder=6)
        axes[1].annotate('', xy=cf, xytext=p, arrowprops={'arrowstyle': '->', 'color': color, 'lw': 1.6})
        axes[1].scatter(*cf, s=140, marker='*', color=color, edgecolor='white', linewidth=.5, zorder=8)
        axes[1].annotate(f'CF{number}', cf, xytext=(8, 9), textcoords='offset points', color=color, fontweight='bold')
    axes[0].text(.5, -.19, f'q1 to q2: graph distance = {graph_distance:.2f}; straight-line distance = {straight_distance:.2f}',
                 ha='center', transform=axes[0].transAxes, fontsize=9)
    axes[1].text(.5, -.19, '3 requested / 3 returned / 3 independently valid', ha='center', transform=axes[1].transAxes, fontsize=9)
    fig.legend(handles=[Line2D([], [], color=ORANGE, lw=2, label='Dijkstra shortest path'),
                        Line2D([], [], color=INK, ls=':', label='Straight-line distance'),
                        Line2D([], [], marker='s', ls='', color=BLUE, label='Reference core'),
                        Line2D([], [], marker='*', ls='', color=ORANGE, markersize=10, label='Counterfactual')],
               loc='lower center', ncol=4, frameon=False, bbox_to_anchor=(.5, .005))
    finish(fig, '02_exdbscan', 'ExDBSCAN: from the core graph to counterfactuals',
           'Reproduces the saved two-moons example: seed=7, eps=0.16, MinPts=3, k=3, target cluster=1.', bottom=.23)


def constraints_figure():
    model = DBSCAN(eps=1, min_pts=3).fit(mock_constraint_case())
    X = model.result_.X
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 5.7))
    cases = [('Both features mutable', ()), ('Feature 1 fixed: y = 0', (1,)),
             ('Feature 0 fixed: x = 0', (0,))]
    for ax, (title, fixed) in zip(axes, cases):
        r = ExDBSCAN(model).explain(5, target_cluster=0, k=1, immutable_features=fixed)
        metrics = evaluate_explanation(model.result_, r)
        assert metrics['valid_count'] == r.returned_k and metrics['immutable_preserved']
        EVIDENCE[title] = {'explanation': r.to_dict(), 'metrics': metrics}
        for q in X[:5]:
            ax.add_patch(Circle(q, model.eps, facecolor=BLUE, edgecolor=BLUE, alpha=.055, lw=.6))
        ax.scatter(*X[:5].T, s=30, color=BLUE, zorder=5)
        ax.scatter(*r.original, s=75, marker='D', color=RED, zorder=7)
        ax.annotate('p = (0, 0)', r.original, xytext=(3, -22), textcoords='offset points', color=RED)
        if fixed == (1,):
            ax.axhline(0, ls='--', color=TEAL, lw=1.5)
        elif fixed == (0,):
            ax.axvline(0, ls='--', color=TEAL, lw=1.5)
        if r.returned_k:
            cf, q = r.counterfactuals[0], X[r.reference_indices[0]]
            ax.add_patch(Circle(q, model.eps, fill=False, edgecolor=BLUE, lw=1.3))
            ax.scatter(*q, s=95, marker='s', facecolors='none', edgecolors=BLUE, linewidths=1.5, zorder=6)
            ax.annotate('', xy=cf, xytext=r.original, arrowprops={'arrowstyle': '->', 'color': ORANGE, 'lw': 2})
            ax.scatter(*cf, marker='*', color=ORANGE, s=170, edgecolor='white', linewidth=.5, zorder=8)
            ax.annotate('CF', cf, xytext=(-10, 12), textcoords='offset points', color=ORANGE, fontweight='bold')
            text = f'CF = ({cf[0]:.3f}, {cf[1]:.3f})\nMovement = {np.linalg.norm(cf-r.original):.3f}; valid'
        else:
            text = 'No reachable target ball\nStatus: infeasible; 0 returned'
        ax.set_title(title, loc='left')
        ax.text(.5, -.36, text, transform=ax.transAxes, ha='center', va='top', fontsize=10, linespacing=1.6)
        axes_xy(ax)
        ax.set(xlim=(-.45, 4.25), ylim=(-.75, 1.9))
    fig.legend(handles=[Line2D([], [], marker='D', ls='', color=RED, label='Original query'),
                        Line2D([], [], color=BLUE, label='Target core neighborhoods'),
                        Line2D([], [], color=TEAL, ls='--', label='Allowed coordinate slice'),
                        Line2D([], [], marker='*', ls='', color=ORANGE, markersize=10, label='Counterfactual')],
               loc='lower center', ncol=4, frameon=False, bbox_to_anchor=(.5, .025))
    finish(fig, '03_constraints', 'Immutable features change the feasible counterfactual',
           'Same query, same target cluster, eps=1, MinPts=3, k=1. Only the immutable-feature constraint changes.', bottom=.28)


def summary_figure():
    summaries = []
    for dataset in ('mock', 'real'):
        summary = read(f'results/{dataset}_summary.json')
        assert summary['source_fingerprint'] == source_fingerprint()
        summaries.extend(r for r in summary['summaries'] if r['strategy'] == 'greedy')
        for constraint in ('unconstrained', 'immutable'):
            with (ROOT / 'results' / f'{dataset}_{constraint}.csv').open() as stream:
                rows = [r for r in csv.DictReader(stream) if r['strategy'] == 'greedy']
            for s in [r for r in summary['summaries'] if r['strategy'] == 'greedy' and r['constraint'] == constraint]:
                group = [r for r in rows if r['dataset'] == s['dataset']]
                assert len(group) == s['queries']
                assert sum(int(r['valid_count']) for r in group) == s['valid']
    keys = ['blobs', 'moons', 'rings', 'usgs_southern_california_2024']
    labels = ['Blobs', 'Moons', 'Rings', 'USGS']
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.8))
    x = np.arange(4)
    for constraint, offset, color, label in [('unconstrained', -.18, BLUE, 'Unconstrained'),
                                              ('immutable', .18, ORANGE, 'Feature 1 immutable')]:
        ordered = [next(r for r in summaries if r['dataset'] == k and r['constraint'] == constraint) for k in keys]
        measures = [[100 * r['valid'] / r['requested'] for r in ordered],
                    [100 * r['complete_queries'] / r['queries'] for r in ordered]]
        for ax, values in zip(axes, measures):
            bars = ax.bar(x + offset, values, .32, color=color, label=label)
            for bar, value in zip(bars, values):
                ax.text(bar.get_x()+bar.get_width()/2, value+2, f'{value:.1f}%', ha='center', fontsize=9)
    for ax, title, ylabel in zip(axes,
            ['Requested explanations covered', 'Queries completed in full'],
            ['Valid returned points / requested points (%)', 'Complete queries / all queries (%)']):
        ax.set_title(title, loc='left')
        ax.set(xticks=x, xticklabels=labels, ylim=(0, 115), yticks=[0, 25, 50, 75, 100], ylabel=ylabel)
        ax.grid(axis='y')
    fig.legend(*axes[0].get_legend_handles_labels(), loc='lower center', ncol=2,
               frameon=False, bbox_to_anchor=(.5, .055))
    fig.text(.5, .02, 'Greedy strategy only. Per condition: 288 blobs, 96 moons, 96 rings, 324 USGS queries. Failed queries retained.',
             ha='center', fontsize=9)
    EVIDENCE['greedy_summary'] = summaries
    total_valid = sum(row['valid'] for row in summaries)
    total_returned = sum(row['returned'] for row in summaries)
    assert total_valid == total_returned
    finish(fig, '04_validation', 'Valid returned points do not guarantee a complete request',
           f'All {total_valid:,} points returned by greedy ExDBSCAN are valid. Constraints reduce the number of feasible explanations.', bottom=.23)


def real_figure():
    saved = read('results/real_examples.json')['usgs_southern_california_2024_unconstrained']
    data_path = ROOT / 'data/processed/usgs_southern_california_2024.npz'
    metadata = read('data/processed/usgs_southern_california_2024.json')
    assert hashlib.sha256(data_path.read_bytes()).hexdigest() == metadata['processed_sha256']
    with np.load(data_path) as data:
        X = data['X']
    model, r = verified_example('usgs_counterfactuals', X, saved)
    q = X[r.reference_indices] / 1000
    cf = r.counterfactuals / 1000
    p = r.original / 1000
    target = X[model.labels_ == r.target_cluster] / 1000
    eps = model.eps / 1000
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 6.1))
    scatter_clusters(axes[0], model, scale=1000, size=10)
    axes[0].scatter(*p, marker='D', s=65, color=RED, zorder=8)
    axes[0].annotate('Query', p, xytext=(5, 9), textcoords='offset points', color=RED)
    axes[0].annotate('', xy=cf[0], xytext=p, arrowprops={'arrowstyle': '->', 'lw': 1.7, 'color': ORANGE})
    lo = np.minimum(target.min(axis=0), cf.min(axis=0)) - eps * 1.4
    hi = np.maximum(target.max(axis=0), cf.max(axis=0)) + eps * 1.4
    axes[0].add_patch(Rectangle(lo, *(hi-lo), fill=False, edgecolor=RED, linewidth=1.5))
    axes[0].set_title(f'{len(X):,} events; {len(model.result_.cluster_ids)} clusters', loc='left')
    axes[1].scatter(*target.T, s=35, color=BLUE)
    for number, (ref, point, color) in enumerate(zip(q, cf, CF_COLORS), 1):
        axes[1].add_patch(Circle(ref, eps, fill=False, edgecolor=color, lw=1.3))
        axes[1].scatter(*ref, marker='s', s=50, color=color, zorder=5)
        axes[1].scatter(*point, marker='*', s=145, color=color, edgecolor='white', linewidth=.5, zorder=6)
        shifts = [(-36, 12), (-37, -20), (8, 14)]
        axes[1].annotate(f'CF{number}', point, xytext=shifts[number-1], textcoords='offset points',
                         color=color, fontweight='bold', arrowprops={'arrowstyle': '-', 'color': color, 'lw': .7})
    axes[1].set(xlim=(lo[0], hi[0]), ylim=(lo[1], hi[1]))
    axes[1].set_title('Target-cluster detail: 3 valid counterfactuals', loc='left')
    for ax in axes:
        axes_xy(ax, 'Local east (km)', 'Local north (km)')
    fig.text(.5, .08, 'Target cluster 0 is specified; it is not necessarily the nearest alternative cluster. Squares: reference cores; stars: counterfactuals.',
             ha='center', fontsize=9)
    fig.text(.5, .04, 'Feature-space locations in a local planar approximation; not a geographic basemap or a physical intervention on earthquakes.',
             ha='center', fontsize=9, color='#536478')
    finish(fig, '05_real_data', 'Real-data check: USGS Southern California, 2024',
           f'Reproduces a saved example from the {len(X):,}-event snapshot. DBSCAN eps=2,000 m, MinPts=5; ExDBSCAN k=3.', bottom=.22)


def main():
    require_mock_success()
    gate = read('results/real_gate.json')
    assert gate['status'] == 'passed' and gate['source_fingerprint'] == source_fingerprint()
    OUT.mkdir(parents=True, exist_ok=True)
    style()
    clustering_figure()
    method_figure()
    constraints_figure()
    summary_figure()
    real_figure()
    save_json(ROOT / 'results/visual_examples.json', {
        'created_at': timestamp(), 'source_fingerprint': source_fingerprint(),
        'plot_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'runtime': {'python': sys.version.split()[0], 'numpy': np.__version__, 'matplotlib': matplotlib.__version__},
        'note': 'Figures use actual implementation outputs. Saved examples are reproduced and independently validated. Aggregate statistics are checked against query CSVs.',
        'examples': EVIDENCE,
        'figures': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob('*')) if p.is_file()},
    })
    print(f'Created 5 figures in PNG/SVG formats: {OUT}')
    print('Reproduced saved examples and validated all displayed counterfactuals.')


if __name__ == '__main__':
    main()
