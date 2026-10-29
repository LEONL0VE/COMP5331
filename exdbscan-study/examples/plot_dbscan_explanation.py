"""Render Figure 1A without modifying existing experiments or their figures.

Run from the project root: python3 examples/plot_dbscan_explanation.py
Matplotlib is an optional rendering dependency, not an algorithm dependency.
"""

import hashlib
from pathlib import Path
import sys

from plot_results import (
    OUT, ROOT, ORANGE, RED, TEAL, Circle, DBSCAN, axes_xy,
    finish, matplotlib, np, plt, point_legend, scatter_clusters, style,
)
from _common import save_json, timestamp


def main():
    # The existing one-dimensional hand-checkable test embedded in two dimensions.
    X = np.array([[1, 0], [0, 0], [.1, 0], [.2, 0], [3, 0]], dtype=float)
    model = DBSCAN(eps=.81, min_pts=3).fit(X)
    result = model.result_
    np.testing.assert_array_equal(result.labels, [0, 0, 0, 0, -1])
    np.testing.assert_array_equal(result.point_types, ['border', 'core', 'core', 'core', 'noise'])
    np.testing.assert_array_equal(result.neighbor_counts, [2, 3, 3, 4, 1])
    selected = 0
    neighbors = result.neighborhoods[selected]
    core_neighbors = neighbors[result.core_mask[neighbors]]
    np.testing.assert_array_equal(neighbors, [0, 3])
    np.testing.assert_array_equal(core_neighbors, [3])

    OUT.mkdir(parents=True, exist_ok=True)
    style()
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.8))
    for ax in axes:
        scatter_clusters(ax, model, size=65)
        axes_xy(ax)
        ax.set_ylabel('Feature 1 (all values = 0)')

    axes[0].set_title('All three DBSCAN point roles', loc='left')
    axes[0].set(xlim=(-.35, 3.35), ylim=(-1.05, 1.05))
    offsets = [(0, 14), (-27, 14), (0, 31), (27, 14), (0, 14)]
    for index, (point, kind) in enumerate(zip(X, result.point_types)):
        axes[0].annotate(f'{index}: {kind}', point, xytext=offsets[index],
                         textcoords='offset points', ha='center', fontsize=9)

    point = X[selected]
    axes[1].add_patch(Circle(point, model.eps, facecolor=ORANGE, edgecolor=ORANGE,
                             alpha=.10, lw=1.8))
    axes[1].scatter(*X[neighbors].T, s=150, facecolors='none', edgecolors=ORANGE,
                    linewidths=1.8, zorder=7)
    axes[1].scatter(*point, marker='D', s=90, color=RED, zorder=8)
    axes[1].scatter(*X[core_neighbors].T, marker='s', s=95, facecolors='none',
                    edgecolors=TEAL, linewidths=2, zorder=9)
    axes[1].plot(*np.vstack([point, X[3]]).T, color=TEAL, ls='--', lw=1.4)
    axes[1].annotate('selected point 0', point, xytext=(8, 12), textcoords='offset points', color=RED)
    axes[1].annotate('core neighbor 3', X[3], xytext=(-12, -24),
                     textcoords='offset points', color=TEAL, ha='center')
    axes[1].set_title('Why point 0 is a border point', loc='left')
    axes[1].set(xlim=(-.35, 1.95), ylim=(-1.05, 1.05))
    axes[1].text(.5, -.23,
                 '2 neighbors including itself < MinPts=3, so it is not core.\n'
                 "It has core point 3 within epsilon, so it is border.",
                 transform=axes[1].transAxes, ha='center', va='top', fontsize=9)
    fig.legend(handles=point_legend(), loc='lower center', ncol=3, frameon=False,
               bbox_to_anchor=(.5, .015))
    finish(fig, '01a_dbscan_explanation', 'DBSCAN local explanation: core, border, and noise',
           'A fixed five-point case. eps=0.81; MinPts=3; neighbors include the query point.', bottom=.27)

    # Matplotlib adds trailing spaces inside SVG path data; removing them is cosmetic.
    svg = OUT / '01a_dbscan_explanation.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())
                   + '\n', encoding='utf-8', newline='\n')
    save_json(ROOT / 'results' / 'dbscan_local_example.json', {
        'created_at': timestamp(), 'points': X.tolist(), 'eps': model.eps,
        'min_pts': model.min_pts, 'labels': result.labels.tolist(),
        'point_types': result.point_types.tolist(), 'neighbor_counts': result.neighbor_counts.tolist(),
        'selected_index': selected, 'selected_neighbors': neighbors.tolist(),
        'selected_core_neighbors': core_neighbors.tolist(),
        'runtime': {'python': sys.version.split()[0], 'numpy': np.__version__,
                    'matplotlib': matplotlib.__version__},
        'plot_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'figures': {f'01a_dbscan_explanation.{ext}': hashlib.sha256(
            (OUT / f'01a_dbscan_explanation.{ext}').read_bytes()).hexdigest() for ext in ('png', 'svg')},
    })
    print('Created Figure 1A (PNG/SVG) and results/dbscan_local_example.json')


if __name__ == '__main__':
    main()
