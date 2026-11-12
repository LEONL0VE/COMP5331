"""Render Figure 1D: the epsilon/MinPts sweep with one fixed coordinate.

Run from the project root: python3 examples/plot_constrained_sweep.py
Matplotlib is only used for rendering. Existing experiments and figures are not modified.

Question: if an event may only move east-west (north_m is immutable), how many
of the reference events can still be explained, and at what extra distance?
"""

import hashlib
import json
from pathlib import Path
import sys

# Make the import below independent of module import order; scripts/ and src/ are
# also added by plot_results, but an import sorter may reorder these lines.
_ROOT = Path(__file__).resolve().parents[1]
for _path in (_ROOT / 'scripts', _ROOT / 'src'):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from plot_results import (
    OUT, ROOT, BLUE, ORANGE, TEAL, RED, INK, DBSCAN, ExDBSCAN, finish, matplotlib, np, plt,
)
from plot_parameter_sweep import EPS_KM, MIN_PTS, MARKED, heatmap, load_usgs, reference_events
from matplotlib.patches import Rectangle
from _common import save_json, timestamp

FIXED = [1]  # feature 1 = north_m
MIN_PAIRS = 20  # medians need at least this many paired events
LINE_MIN_PTS = [5, 10, 20]


def explain_pair(model, events):
    """Per still-noise event: free move and fixed-north move (km), k=1, any reachable target."""
    r = model.result_
    explainer = ExDBSCAN(model)
    still = [int(i) for i in events if r.labels[i] == -1]
    feasible, free_moves, fixed_moves = 0, [], []
    for i in still:
        free = explainer.explain(i, target_cluster=None, k=1)
        fixed = explainer.explain(i, target_cluster=None, k=1, immutable_features=FIXED)
        if free.returned_k == 1:
            free_moves.append(float(np.linalg.norm(free.changes[0])) / 1000)
        else:
            free_moves.append(np.nan)
        if fixed.returned_k == 1:
            assert np.isclose(fixed.counterfactuals[0][1], r.X[i][1])  # north is unchanged
            feasible += 1
            fixed_moves.append(float(np.linalg.norm(fixed.changes[0])) / 1000)
        else:
            fixed_moves.append(np.nan)
    free_moves, fixed_moves = np.array(free_moves), np.array(fixed_moves)
    ok = np.isfinite(fixed_moves) & np.isfinite(free_moves)
    if ok.any():
        assert np.all(fixed_moves[ok] >= free_moves[ok] - 1e-6)  # a constraint never helps
    return len(still), feasible, fixed_moves[ok], free_moves[ok]


def sweep(X):
    events = reference_events(X)
    shape = (len(MIN_PTS), len(EPS_KM))
    grid = {k: np.full(shape, np.nan) for k in ('still_noise', 'feasible', 'feasible_pct', 'fixed_km', 'free_km', 'n_pair')}
    for a, mp in enumerate(MIN_PTS):
        for b, eps in enumerate(EPS_KM):
            model = DBSCAN(eps=eps * 1000, min_pts=mp).fit(X)
            n, feasible, fixed, free = explain_pair(model, events)
            grid['still_noise'][a, b], grid['feasible'][a, b] = n, feasible
            if n:
                grid['feasible_pct'][a, b] = 100 * feasible / n
            grid['n_pair'][a, b] = len(fixed)
            if len(fixed) >= MIN_PAIRS:
                grid['fixed_km'][a, b] = np.median(fixed)
                grid['free_km'][a, b] = np.median(free)
    grid['events'] = events
    return grid


def main():
    X = load_usgs()
    OUT.mkdir(parents=True, exist_ok=True)
    from plot_results import style
    style()
    grid = sweep(X)
    fig, axes = plt.subplots(1, 2, figsize=(13.8, 5.4), gridspec_kw={'width_ratios': [1, 1.05]})
    heatmap(axes[0], grid['feasible_pct'], 'Events still explainable with north fixed (%)', BLUE, lambda v: f'{v:.0f}')
    ax = axes[1]
    colors = {5: BLUE, 10: ORANGE, 20: TEAL}
    for mp in LINE_MIN_PTS:
        row = MIN_PTS.index(mp)
        x = np.array(EPS_KM, float)
        free, fixed = grid['free_km'][row], grid['fixed_km'][row]
        ax.plot(x, fixed, marker='o', lw=2, color=colors[mp], label=f'MinPts={mp}, north fixed')
        ax.plot(x, free, marker='o', lw=1.6, ls='--', color=colors[mp], alpha=.75, label=f'MinPts={mp}, free')
    ax.set(xlabel='epsilon (km)', ylabel='Median move of the same events (km)', xscale='log')
    ax.set_xticks(EPS_KM, [str(e) for e in EPS_KM])
    ax.minorticks_off()
    ax.set_ylim(0, 100)
    ax.grid(True)
    ax.set_title('Paired comparison: fixing north makes each move longer', loc='left')
    ax.legend(frameon=False, fontsize=10, ncol=2, loc='upper right')
    handles = [Rectangle((0, 0), 1, 1, fill=False, edgecolor=edge, lw=2, label=label) for _, edge, label in MARKED]
    fig.legend(handles=handles, loc='lower center', ncol=2, frameon=False, bbox_to_anchor=(.27, .075))
    fig.text(.5, .02, 'Reference events: the 449 that are noise at epsilon=5 km, MinPts=10; only events still noise are counted.\n'
             f'Right panel: events explainable in both modes; cells with fewer than {MIN_PAIRS} such events are omitted.',
             ha='center', fontsize=11, color='#536478')
    finish(fig, '01d_constrained_sweep', 'Fixing one coordinate removes explanations and lengthens the rest',
           'Same 8 x 7 grid as Figure 1B. ExDBSCAN, k=1, any reachable cluster, north_m immutable (east-west moves only).',
           bottom=.25)
    svg = OUT / '01d_constrained_sweep.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines()) + '\n',
                   encoding='utf-8', newline='\n')
    tolist = lambda a: [[None if not np.isfinite(v) else round(float(v), 4) for v in row] for row in a]
    save_json(ROOT / 'results' / 'constrained_sweep.json', {
        'created_at': timestamp(), 'dataset': 'usgs_southern_california_2024', 'events': int(len(X)),
        'eps_km': EPS_KM, 'min_pts': MIN_PTS, 'immutable_features': FIXED,
        'reference_event_count': int(len(grid['events'])),
        'still_noise': np.nan_to_num(grid['still_noise']).astype(int).tolist(),
        'explainable': np.nan_to_num(grid['feasible']).astype(int).tolist(),
        'explainable_pct': tolist(grid['feasible_pct']),
        'paired_events': np.nan_to_num(grid['n_pair']).astype(int).tolist(),
        'paired_median_fixed_move_km': tolist(grid['fixed_km']),
        'paired_median_free_move_km': tolist(grid['free_km']),
        'min_paired_events': MIN_PAIRS,
        'runtime': {'python': sys.version.split()[0], 'numpy': np.__version__, 'matplotlib': matplotlib.__version__},
        'plot_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'figures': {f'01d_constrained_sweep.{e}': hashlib.sha256((OUT / f'01d_constrained_sweep.{e}').read_bytes()).hexdigest()
                    for e in ('png', 'svg')},
    })
    print('Created Figure 1D (PNG/SVG) and results/constrained_sweep.json')


if __name__ == '__main__':
    main()
