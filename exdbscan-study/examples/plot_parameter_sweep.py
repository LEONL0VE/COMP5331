"""Render Figures 1B and 1C: parameter sweep and DBSCAN limitations.

Run from the project root: python3 examples/plot_parameter_sweep.py
Matplotlib is only used for rendering. All clustering and explanations come from
our own implementation. Existing experiments and figures are not modified.

Figure 1B: how epsilon and MinPts change the clustering and the explanation on
           the recorded USGS snapshot.
Figure 1C: where DBSCAN struggles (varying density, chaining), shown with data.
"""

import hashlib
import json
import sys
from pathlib import Path

# Make the import below independent of module import order; scripts/ and src/ are
# also added by plot_results, but an import sorter may reorder these lines.
_ROOT = Path(__file__).resolve().parents[1]
for _path in (_ROOT / 'scripts', _ROOT / 'src'):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from _common import save_json, timestamp
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
from plot_results import (
    BLUE,
    DBSCAN,
    INK,
    ORANGE,
    OUT,
    RED,
    ROOT,
    TEAL,
    ExDBSCAN,
    axes_xy,
    finish,
    matplotlib,
    np,
    plt,
    point_legend,
    scatter_clusters,
    style,
)

EPS_KM = [1, 2, 3, 5, 8, 10, 15, 20]
MIN_PTS = [3, 5, 8, 10, 15, 20, 30]
MARKED = [((2, 5), RED, "Figure 5 setting"), ((5, 10), INK, "Interactive explorer default")]


def load_usgs():
    data_path = ROOT / "data/processed/usgs_southern_california_2024.npz"
    meta = json.loads((ROOT / "data/processed/usgs_southern_california_2024.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(data_path.read_bytes()).hexdigest() == meta["processed_sha256"]
    with np.load(data_path) as data:
        return data["X"]


def reference_events(X):
    """Fixed query set: the events that are noise at the interactive default."""
    r = DBSCAN(eps=5000, min_pts=10).fit(X).result_
    return np.flatnonzero(r.labels == -1)


def median_move_km(model, events):
    """Median move (km) for the same events under this clustering, k=1.

    Events that are no longer noise count as 0. Noise events are explained by
    ExDBSCAN toward the cluster of their nearest core point. For k=1 the result
    equals max(distance to that core - eps, 0), which is asserted below.
    """
    r = model.result_
    cores = np.flatnonzero(r.core_mask)
    if len(cores) == 0:
        return np.nan, 0
    explainer = ExDBSCAN(model)
    moves, answered = [], 0
    for i in events:
        if r.labels[i] != -1:
            moves.append(0.0)
            answered += 1
            continue
        d = np.linalg.norm(r.X[cores] - r.X[i], axis=1)
        result = explainer.explain(int(i), target_cluster=int(r.labels[cores[d.argmin()]]), k=1)
        if result.returned_k == 1:
            move = float(np.linalg.norm(result.changes[0]))
            assert abs(move - max(d.min() - model.eps, 0)) < 1e-4 * max(move, 1)
            moves.append(move / 1000)
            answered += 1
    return (float(np.median(moves)) if moves else np.nan), answered


def sweep(X):
    events = reference_events(X)
    shape = (len(MIN_PTS), len(EPS_KM))
    grid = {k: np.full(shape, np.nan) for k in ("clusters", "noise_pct", "move_km", "answered")}
    grid["asked"] = np.full(shape, float(len(events)))
    for a, mp in enumerate(MIN_PTS):
        for b, eps in enumerate(EPS_KM):
            model = DBSCAN(eps=eps * 1000, min_pts=mp).fit(X)
            labels = model.result_.labels
            grid["clusters"][a, b] = len(model.result_.cluster_ids)
            grid["noise_pct"][a, b] = 100 * np.mean(labels == -1)
            grid["move_km"][a, b], grid["answered"][a, b] = median_move_km(model, events)
    grid["events"] = events
    return grid


def heatmap(ax, values, title, color, fmt):
    cmap = LinearSegmentedColormap.from_list("w", ["#ffffff", color])
    finite = values[np.isfinite(values)]
    vmax = finite.max() if len(finite) else 1
    ax.imshow(np.nan_to_num(values), cmap=cmap, vmin=0, vmax=vmax, aspect="auto")
    for a in range(values.shape[0]):
        for b in range(values.shape[1]):
            v = values[a, b]
            text = "-" if not np.isfinite(v) else fmt(v)
            dark = np.isfinite(v) and v > 0.62 * vmax
            ax.text(b, a, text, ha="center", va="center", fontsize=10.5, color="white" if dark else INK)
    for (eps, mp), edge, _ in MARKED:
        ax.add_patch(
            Rectangle(
                (EPS_KM.index(eps) - 0.5, MIN_PTS.index(mp) - 0.5), 1, 1, fill=False, edgecolor=edge, lw=2.2, zorder=5
            )
        )
    ax.set_xticks(range(len(EPS_KM)), [str(e) for e in EPS_KM])
    ax.set_yticks(range(len(MIN_PTS)), [str(m) for m in MIN_PTS])
    ax.set(xlabel="epsilon (km)", ylabel="MinPts")
    ax.set_title(title, loc="left")
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)


def sweep_figure(X, grid):
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 5.4))
    heatmap(axes[0], grid["clusters"], "Clusters found", BLUE, lambda v: f"{v:.0f}")
    heatmap(axes[1], grid["noise_pct"], "Noise points (% of events)", ORANGE, lambda v: f"{v:.0f}")
    heatmap(axes[2], grid["move_km"], "Median move to the nearest cluster (km)", TEAL, lambda v: f"{v:.1f}")
    handles = [Rectangle((0, 0), 1, 1, fill=False, edgecolor=edge, lw=2, label=label) for _, edge, label in MARKED]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.075))
    fig.text(
        0.5,
        0.025,
        f"USGS Southern California 2024, {len(X):,} events. Reference events: the 449 that are noise at epsilon=5 km, MinPts=10.\n"
        "Move: ExDBSCAN, k=1, toward the nearest cluster; 0 if the event is no longer noise.",
        ha="center",
        fontsize=11,
        color="#536478",
    )
    finish(
        fig,
        "01b_parameter_sweep",
        "Epsilon and MinPts reshape both the clusters and the explanations",
        "Full sweep of 8 epsilon values x 7 MinPts values with our DBSCAN and ExDBSCAN. Larger epsilon or smaller MinPts: fewer noise points and shorter moves.",
        bottom=0.25,
    )
    # finish() leaves wide spacing for scatter panels; heatmaps want tighter columns.


def varying_density(seed=7):
    rng = np.random.default_rng(seed)
    return np.vstack([rng.normal((0, 0), 0.12, (100, 2)), rng.normal((1.5, 0), 0.55, (50, 2))])


def limitation_figure(X, grid):
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 5.6))
    V = varying_density()
    evidence = {"varying_density": {}}
    for ax, eps in zip(axes[:2], (0.2, 0.5)):
        model = DBSCAN(eps=eps, min_pts=5).fit(V)
        r = model.result_
        sparse_noise = int(np.sum(r.labels[100:] == -1))
        sparse_in_dense = int(np.sum(r.labels[100:] == r.labels[0]))
        scatter_clusters(ax, model, size=26)
        axes_xy(ax)
        ax.set(xlim=(-0.7, 3.2), ylim=(-1.5, 1.5))
        ax.set_title(f"Dense + sparse group, eps={eps}, MinPts=5", loc="left")
        ax.text(
            0.5,
            -0.3,
            f"{len(r.cluster_ids)} cluster(s); {sparse_noise} of 50 sparse points are noise;\n"
            f"{sparse_in_dense} of 50 sparse points sit in the dense cluster",
            transform=ax.transAxes,
            ha="center",
            va="top",
            fontsize=11,
            linespacing=1.6,
        )
        evidence["varying_density"][str(eps)] = {
            "clusters": len(r.cluster_ids),
            "sparse_noise": sparse_noise,
            "sparse_in_dense_cluster": sparse_in_dense,
        }
    ref = DBSCAN(eps=0.4, min_pts=5).fit(V).result_
    evidence["varying_density"]["0.4"] = {
        "clusters": len(ref.cluster_ids),
        "sparse_noise": int(np.sum(ref.labels[100:] == -1)),
        "sparse_in_dense_cluster": int(np.sum(ref.labels[100:] == ref.labels[0])),
    }

    ax = axes[2]
    eps_grid = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 20]
    noise, largest = [], []
    for e in eps_grid:
        labels = DBSCAN(eps=e * 1000, min_pts=10).fit(X).result_.labels
        noise.append(100 * np.mean(labels == -1))
        sizes = np.bincount(labels[labels >= 0])
        largest.append(100 * sizes.max() / len(X))
    ax.plot(eps_grid, noise, marker="o", color=ORANGE, lw=2, label="Noise points")
    ax.plot(eps_grid, largest, marker="s", color=BLUE, lw=2, label="Largest cluster")
    ax.set(xlabel="epsilon (km), MinPts=10", ylabel="Share of all events (%)", ylim=(0, 85))
    ax.grid(True)
    ax.set_title("USGS: chaining into one giant cluster", loc="left")
    ax.legend(frameon=False, loc="lower left")
    ax.annotate(
        f"{largest[eps_grid.index(10)]:.0f}% at 10 km",
        (10, largest[eps_grid.index(10)]),
        xytext=(10.5, 4),
        textcoords="data",
        fontsize=11,
        color=BLUE,
        arrowprops={"arrowstyle": "-", "color": BLUE, "lw": 0.7},
    )
    ax.annotate(
        f"{largest[-1]:.0f}% at 20 km",
        (20, largest[-1]),
        xytext=(10.5, 70),
        textcoords="data",
        fontsize=11,
        color=BLUE,
        arrowprops={"arrowstyle": "-", "color": BLUE, "lw": 0.7},
    )
    ax.text(
        0.5,
        -0.3,
        "No sharp break: one slow change in epsilon\nturns many local clusters into one dominant cluster.",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=11,
        linespacing=1.6,
    )
    evidence["usgs_chaining"] = {"min_pts": 10, "eps_km": eps_grid, "noise_pct": noise, "largest_cluster_pct": largest}
    fig.legend(handles=point_legend(), loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.015))
    finish(
        fig,
        "01c_limitations",
        "Where DBSCAN is fragile: one global density and one epsilon",
        "Left and middle: the same two-density data (seed 7) at two epsilon values. Right: the real USGS data as epsilon grows.",
        bottom=0.30,
    )
    return evidence


def main():
    X = load_usgs()
    if not OUT.exists():
        OUT.mkdir(parents=True)
    style()
    grid = sweep(X)
    # The Figure 5 setting must reproduce the saved result: 30 clusters at 2 km, MinPts=5.
    assert int(grid["clusters"][MIN_PTS.index(5), EPS_KM.index(2)]) == 30
    sweep_figure(X, grid)
    limits = limitation_figure(X, grid)
    names = ["01b_parameter_sweep", "01c_limitations"]
    for name in names:
        svg = OUT / f"{name}.svg"
        svg.write_text(
            "\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    save_json(
        ROOT / "results" / "parameter_sweep.json",
        {
            "created_at": timestamp(),
            "dataset": "usgs_southern_california_2024",
            "events": len(X),
            "eps_km": EPS_KM,
            "min_pts": MIN_PTS,
            "clusters": np.nan_to_num(grid["clusters"]).astype(int).tolist(),
            "noise_pct": np.round(grid["noise_pct"], 3).tolist(),
            "median_move_km": [
                [None if not np.isfinite(v) else round(float(v), 4) for v in row] for row in grid["move_km"]
            ],
            "queries_answered": grid["answered"].astype(int).tolist(),
            "queries_asked": grid["asked"].astype(int).tolist(),
            "move_definition": "Median over a fixed set of reference events (noise at eps=5000 m, MinPts=10); ExDBSCAN k=1 toward the cluster of the nearest core point; 0 if the event is no longer noise",
            "reference_event_count": len(grid["events"]),
            "limitations": limits,
            "runtime": {
                "python": sys.version.split()[0],
                "numpy": np.__version__,
                "matplotlib": matplotlib.__version__,
            },
            "plot_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "figures": {
                f"{n}.{ext}": hashlib.sha256((OUT / f"{n}.{ext}").read_bytes()).hexdigest()
                for n in names
                for ext in ("png", "svg")
            },
        },
    )
    print("Created Figures 1B and 1C (PNG/SVG) and results/parameter_sweep.json")


if __name__ == "__main__":
    main()
