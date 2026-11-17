"""The SAGA population as a tube through time.

Each generation is drawn from its own Hamming distances. The cross-section is
centred on that generation and scaled so its average separation equals the real
mean pairwise Hamming distance. Distance from the start stays an exact Hamming
distance. Pooled PCA is not used.

    python analysis/plot_cloud.py --log adder2/evolution/out/saga_4bit_g300_m2_p21_e1_seed13/recovery.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT = Path(__file__).resolve().parents[1]
ELITE = "#c45c12"
CENTROID = "#2a7a4b"
SPREAD = "#6b5b95"
MEAN = "#3a6ea5"
TITLE_NAMES = {"adder2": "2-bit adder", "adder4": "4-bit adder", "xor": "XOR"}
FOOTER = "y/z directions are arbitrary; only cross-section radius and shape are meaningful."


def load_run(path: Path) -> dict:
    """Elite is population index 0. mutation_level is the rate those genomes received."""
    saved = json.loads(path.read_text())
    history = sorted(saved["history"], key=lambda row: row["generation"])
    if not history:
        raise SystemExit(f"No generations in {path}")
    counts = {len(row["population"]) for row in history}
    lengths = {len(genome) for row in history for genome in row["population"]}
    if len(counts) != 1 or len(lengths) != 1:
        raise SystemExit("Every generation needs the same population size and genotype length.")
    population = counts.pop()
    length = lengths.pop()
    blob = "".join(genome for row in history for genome in row["population"])
    bits = np.frombuffer(blob.encode("ascii"), dtype=np.uint8).copy()
    bits -= ord("0")
    if int(bits.min()) < 0 or int(bits.max()) > 1:
        raise SystemExit("Genotypes must be bit strings of 0 and 1.")
    genotypes = bits.reshape(len(history), population, length)
    elite_key = "".join(str(bit) for bit in history[0]["best_genome"])
    mismatches = sum(row["population"][0] != "".join(str(bit) for bit in row["best_genome"]) for row in history)
    if mismatches:
        raise SystemExit("The elite is not population index 0 in every generation.")
    circuit = saved.get("circuit", "adder2")
    return {
        "genotypes": genotypes,
        "fitness": np.array([row["scores"] for row in history], dtype=np.float64),
        "generations": np.array([row["generation"] for row in history], dtype=int),
        "mutation": np.array([row.get("mutation_level", row.get("schedule_flips", 0)) for row in history], dtype=np.float64),
        "logged_width": np.array([row.get("mean_pairwise_hamming", np.nan) for row in history], dtype=np.float64),
        "title": (
            f"{TITLE_NAMES.get(circuit, circuit)} — {saved.get('algorithm', 'saga')} — "
            f"{saved.get('fault_bits', 4)}-bit fault"
        ),
        "elite_key": elite_key,
    }


def hamming_matrices(genotypes: np.ndarray) -> np.ndarray:
    """Pairwise Hamming distance inside each generation. |a| + |b| - 2 a·b."""
    bits = genotypes.astype(np.float64)
    counts = bits.sum(axis=2)
    dots = np.einsum("gni,gmi->gnm", bits, bits)
    return counts[:, :, None] + counts[:, None, :] - 2.0 * dots


def distances_to(genotypes: np.ndarray, reference: np.ndarray) -> np.ndarray:
    bits = genotypes.astype(np.float64)
    ref = reference.astype(np.float64)
    return bits.sum(axis=2) + ref.sum() - 2.0 * np.einsum("gnl,l->gn", bits, ref)


def mean_upper(distance: np.ndarray) -> np.ndarray:
    index = np.triu_indices(distance.shape[-1], k=1)
    return distance[..., index[0], index[1]].mean(axis=-1)


def consensus_distance(genotypes: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Hamming distance of the majority genome to one reference genome."""
    ones = genotypes.sum(axis=1)
    majority = (ones * 2 > genotypes.shape[1]).astype(np.int16)
    return np.abs(majority - reference.astype(np.int16)).sum(axis=1)


def classical_mds(distance: np.ndarray) -> tuple[np.ndarray, float]:
    """Top two classical-MDS axes of one Hamming matrix, centred on the centroid."""
    squared = np.asarray(distance, dtype=np.float64) ** 2
    centered = squared - squared.mean(axis=1, keepdims=True) - squared.mean(axis=0, keepdims=True) + squared.mean()
    gram = -0.5 * centered
    values, vectors = np.linalg.eigh(gram)
    order = np.argsort(values)[::-1]
    values = values[order]
    vectors = vectors[:, order]
    positive = np.clip(values, 0.0, None)
    total = float(positive.sum())
    captured = float(positive[:2].sum() / total) if total > 0 else np.nan
    coords = vectors[:, :2] * np.sqrt(positive[:2])
    return coords, captured


def rotation_taking(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """2D rotation R with source @ R pointing along target."""
    left = np.linalg.norm(source)
    right = np.linalg.norm(target)
    if left < 1e-8 or right < 1e-8:
        return np.eye(2)
    a = source / left
    b = target / right
    cos = float(np.clip(a @ b, -1.0, 1.0))
    sin = float(a[0] * b[1] - a[1] * b[0])
    return np.array([[cos, sin], [-sin, cos]])


def reflect_across(coords: np.ndarray, axis: np.ndarray) -> np.ndarray:
    scale = np.linalg.norm(axis)
    if scale < 1e-8:
        flipped = coords.copy()
        flipped[:, 1] *= -1
        return flipped
    direction = axis / scale
    projected = coords @ direction
    return 2.0 * projected[:, None] * direction - coords


def principal_axis(coords: np.ndarray) -> np.ndarray:
    cov = np.cov(coords.T)
    if not np.isfinite(cov).all():
        return np.array([0.0, 1.0])
    values, vectors = np.linalg.eigh(cov)
    direction = vectors[:, int(np.argmax(values))]
    if direction[int(np.argmax(np.abs(direction)))] < 0:
        direction = -direction
    return direction


def perpendicular(coords: np.ndarray, axis: np.ndarray) -> np.ndarray:
    """A unit axis across the elite direction. Its sign follows the cloud's skew."""
    scale = np.linalg.norm(axis)
    if scale < 1e-8:
        direction = principal_axis(coords)
    else:
        unit = axis / scale
        direction = np.array([-unit[1], unit[0]])
    skew = float(np.sum((coords @ direction) ** 3))
    if skew < 0:
        direction = -direction
    return direction


def orthogonal_map(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """R with source @ R closest to target. Reflection is allowed."""
    factor = source.T @ target
    if np.linalg.norm(factor) < 1e-10:
        return np.eye(2)
    left, _, right = np.linalg.svd(factor)
    return left @ right


def shared_pairs(previous: np.ndarray, current: np.ndarray) -> list[tuple[int, int]]:
    lookup: dict[bytes, int] = {}
    for index, genome in enumerate(previous):
        lookup.setdefault(genome.tobytes(), index)
    pairs = []
    used = set()
    for index, genome in enumerate(current):
        key = genome.tobytes()
        if key in lookup and key not in used:
            pairs.append((lookup[key], index))
            used.add(key)
    return pairs


def align_to_previous(coords: np.ndarray, previous: np.ndarray | None, shared: list[tuple[int, int]]) -> np.ndarray:
    """Keep the cross-section from spinning. Shared genomes, otherwise the elite direction."""
    if previous is None:
        return coords @ rotation_taking(coords[0], np.array([0.0, 1.0]))
    if len(shared) >= 2:
        src = np.stack([coords[j] for _, j in shared])
        dst = np.stack([previous[i] for i, _ in shared])
        src = src - src.mean(axis=0)
        dst = dst - dst.mean(axis=0)
        if np.linalg.norm(src) > 1e-6 and np.linalg.norm(dst) > 1e-6:
            return coords @ orthogonal_map(src, dst)
    oriented = coords @ rotation_taking(coords[0], previous[0])
    old_perp = perpendicular(previous, previous[0])
    new_perp = perpendicular(oriented, oriented[0])
    if new_perp @ old_perp < 0:
        oriented = reflect_across(oriented, oriented[0])
    return oriented


def cross_sections(genotypes: np.ndarray) -> dict:
    distance = hamming_matrices(genotypes)
    width = mean_upper(distance)
    generations, population, _length = genotypes.shape
    coords = np.zeros((generations, population, 2), dtype=np.float64)
    captured = np.full(generations, np.nan)
    scales = np.ones(generations)
    upper = np.triu_indices(population, k=1)
    previous = None
    for index in range(generations):
        local, fraction = classical_mds(distance[index])
        captured[index] = fraction
        gaps = np.linalg.norm(local[:, None, :] - local[None, :, :], axis=2)
        mean_gap = float(gaps[upper].mean()) if population > 1 else 0.0
        scales[index] = (width[index] / mean_gap) if mean_gap > 1e-8 else 1.0
        local = local * scales[index]
        shared = [] if index == 0 else shared_pairs(genotypes[index - 1], genotypes[index])
        local = align_to_previous(local, previous, shared)
        coords[index] = local
        previous = local
    start = genotypes[0, 0]
    final = genotypes[-1, 0]
    return {
        "coords": coords,
        "width": width,
        "captured": captured,
        "scales": scales,
        "d0": distances_to(genotypes, start),
        "d_final": distances_to(genotypes, final),
        "centroid_d0": consensus_distance(genotypes, start),
    }


def movement(genotypes: np.ndarray, fitness: np.ndarray) -> dict[str, np.ndarray]:
    elite = genotypes[:, 0]
    score = fitness[:, 0]
    changed = np.zeros(len(score), dtype=bool)
    improved = np.zeros(len(score), dtype=bool)
    changed[1:] = np.any(elite[1:] != elite[:-1], axis=1)
    improved[1:] = score[1:] > score[:-1]
    return {"changed": changed, "improved": improved, "neutral": changed & ~improved}


def ellipse_ring(coords: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    if len(coords) < 3 or float(np.std(coords)) < 1e-8:
        return None
    cov = np.cov(coords.T)
    if not np.isfinite(cov).all():
        return None
    values, vectors = np.linalg.eigh(cov)
    values = np.clip(values, 0.0, None)
    theta = np.linspace(0, 2 * np.pi, 72)
    circle = np.stack([np.cos(theta), np.sin(theta)])
    offset = (vectors * np.sqrt(values)) @ circle
    return offset[0], offset[1]


def snapshot_plan(generations: np.ndarray, best: np.ndarray, level: np.ndarray) -> list[tuple[int, str]]:
    """Start, each gain, the generation bred after the rate falls back to 2/N, the long plateau, and the end."""
    tags: dict[int, list[str]] = {}

    def add(generation: int, tag: str) -> None:
        tags.setdefault(int(generation), [])
        if tag not in tags[int(generation)]:
            tags[int(generation)].append(tag)

    add(int(generations[0]), "start")
    for generation in generations[1:][np.diff(best) > 0]:
        add(int(generation), "gain")
    for index in range(1, len(level)):
        if level[index] <= 2 and level[index - 1] > 2:
            add(int(generations[index]), "rate 2/N")
    change_at = np.flatnonzero(np.diff(best) != 0) + 1
    starts = [0, *change_at.tolist()]
    ends = [*change_at.tolist(), len(best)]
    longest = max(range(len(starts)), key=lambda i: ends[i] - starts[i])
    midpoint = (starts[longest] + ends[longest] - 1) // 2
    add(int(generations[midpoint]), "plateau")
    add(int(generations[-1]), "end")
    return [(generation, ", ".join(tags[generation])) for generation in sorted(tags)]


def honesty(run: dict, cloud: dict) -> str:
    genotypes = run["genotypes"]
    generations, population, length = genotypes.shape
    captured = float(np.nanmedian(cloud["captured"]) * 100)
    scale = float(np.nanmedian(cloud["scales"]))
    return (
        f"L={length}   N={population} (1 elite + {population - 1} children)   "
        f"G={generations} (generations {run['generations'][0]}–{run['generations'][-1]})   "
        f"Median 2D cross-section captures {captured:.0f}% of within-generation distance. "
        f"Median rescale ×{scale:.2f}."
    )


def style_3d(ax) -> None:
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor((1, 1, 1, 0))
        axis.pane.set_edgecolor("#dddddd")
    ax.tick_params(labelsize=8)


def draw_tube(ax, run: dict, cloud: dict, fit_norm: Normalize) -> None:
    generations = run["generations"]
    coords = cloud["coords"]
    fitness = run["fitness"]
    count, population, _axes = coords.shape
    y_lo = float(coords[:, :, 0].min())
    y_hi = float(coords[:, :, 0].max())
    z_lo = float(coords[:, :, 1].min())
    z_hi = float(coords[:, :, 1].max())
    y_wall = y_lo - 0.14 * max(y_hi - y_lo, 1.0)
    z_fit = z_lo + fitness[:, 0] * (z_hi - z_lo)
    step_x = np.repeat(generations.astype(float), 2)[1:]
    step_z = np.repeat(z_fit, 2)[:-1]
    ax.plot(step_x, np.full(step_x.shape, y_wall), step_z, color="#2a7a4b", alpha=0.45, lw=1.3)
    for index in range(0, count, 10):
        ring = ellipse_ring(coords[index])
        if ring is None:
            continue
        y_ring, z_ring = ring
        x_ring = np.full(y_ring.shape, generations[index])
        verts = [list(zip(x_ring, y_ring, z_ring))]
        ax.add_collection3d(Poly3DCollection(
            verts, alpha=0.10, facecolor=SPREAD, edgecolor=SPREAD, linewidths=0.8,
        ))
    point_gen = np.repeat(generations, population)
    points = coords.reshape(-1, 2)
    ax.scatter(
        point_gen, points[:, 0], points[:, 1],
        c=fitness.ravel(), cmap="viridis", norm=fit_norm,
        s=9, alpha=0.72, linewidths=0, depthshade=False,
    )
    spine = cloud["centroid_d0"]
    spine_norm = Normalize(vmin=float(spine.min()), vmax=float(spine.max()))
    greens = plt.get_cmap("Greens")
    for index in range(count - 1):
        ax.plot(
            generations[index:index + 2], [0, 0], [0, 0],
            color=greens(0.35 + 0.65 * spine_norm(spine[index])), lw=2.0,
        )
    ax.plot(generations, coords[:, 0, 0], coords[:, 0, 1], color=ELITE, lw=2.2, zorder=5)
    ax.scatter(
        generations, coords[:, 0, 0], coords[:, 0, 1],
        c=fitness[:, 0], cmap="viridis", norm=fit_norm,
        s=28, edgecolors=ELITE, linewidths=0.7, depthshade=False, zorder=6,
    )
    ax.set_xlabel("Generation")
    ax.set_ylabel("Cross-section (bits)")
    ax.set_zlabel("Cross-section (bits)")
    style_3d(ax)


def tube_legend() -> list[Line2D]:
    return [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#3b528b", markeredgecolor=ELITE, markersize=7, label="Elite"),
        Line2D([0], [0], color=CENTROID, lw=2, label="Centroid spine"),
        Line2D([0], [0], color=SPREAD, lw=1.4, label="1-sigma ring"),
        Line2D([0], [0], color="#2a7a4b", lw=1.3, alpha=0.6, label="Best fitness on the side wall"),
    ]


def write_tube(run: dict, cloud: dict, out_dir: Path, note: str) -> None:
    fit_norm = Normalize(vmin=float(run["fitness"].min()), vmax=float(run["fitness"].max()))
    spine_norm = Normalize(vmin=float(cloud["centroid_d0"].min()), vmax=float(cloud["centroid_d0"].max()))
    views = (("oblique", 24, -58), ("side", 14, -90), ("end", 8, -12))
    for name, elev, azim in views:
        fig = plt.figure(figsize=(8.6, 6.8))
        ax = fig.add_subplot(111, projection="3d")
        draw_tube(ax, run, cloud, fit_norm)
        ax.view_init(elev=elev, azim=azim)
        ax.set_title(run["title"])
        fitness_bar = plt.cm.ScalarMappable(cmap="viridis", norm=fit_norm)
        fitness_bar.set_array([])
        fig.colorbar(fitness_bar, ax=ax, shrink=0.55, pad=0.02, label="Truth-table fitness")
        distance_bar = plt.cm.ScalarMappable(cmap="Greens", norm=spine_norm)
        distance_bar.set_array([])
        fig.colorbar(distance_bar, ax=ax, shrink=0.55, pad=0.10, label="Centroid Hamming to generation 0")
        ax.legend(handles=tube_legend(), fontsize=7, loc="upper left")
        fig.text(0.5, 0.062, FOOTER, ha="center", fontsize=7)
        fig.text(0.5, 0.038, note, ha="center", fontsize=7)
        fig.text(0.5, 0.014, "Side wall: best fitness stretched over the cross-section span.", ha="center", fontsize=7)
        fig.subplots_adjust(left=0.02, right=0.86, bottom=0.12, top=0.94)
        fig.savefig(out_dir / f"cloud_tube_{name}.png", dpi=300, bbox_inches="tight")
        plt.close(fig)


def distance_to_elite(genotypes: np.ndarray) -> np.ndarray:
    """Hamming distance of every genome to the elite of its own generation."""
    bits = genotypes.astype(np.float64)
    elite = bits[:, 0, :]
    return bits.sum(axis=2) + elite.sum(axis=1)[:, None] - 2.0 * np.einsum("gnl,gl->gn", bits, elite)


def write_drift(run: dict, out_dir: Path) -> None:
    """x is travel from generation 0, y is distance from the current elite, z is fitness."""
    genotypes = run["genotypes"]
    fitness = run["fitness"]
    generations = run["generations"]
    drift = distances_to(genotypes, genotypes[0, 0])
    hamming = distance_to_elite(genotypes)
    point_gen = np.repeat(generations, fitness.shape[1])
    gen_norm = Normalize(vmin=int(generations[0]), vmax=int(generations[-1]))
    fig = plt.figure(figsize=(8.2, 6.4))
    ax = fig.add_subplot(111, projection="3d")
    ax.scatter(
        drift.ravel(), hamming.ravel(), fitness.ravel(),
        c=point_gen, cmap="viridis", norm=gen_norm, s=8, alpha=0.4, linewidths=0, depthshade=False,
    )
    ax.plot(drift[:, 0], hamming[:, 0], fitness[:, 0], color=ELITE, lw=2.2)
    ax.scatter(drift[0, 0], hamming[0, 0], fitness[0, 0], s=90, c=ELITE, marker="*", depthshade=False)
    ax.scatter(drift[-1, 0], hamming[-1, 0], fitness[-1, 0], s=36, c=ELITE, marker="D", depthshade=False)
    ax.set_xlabel("Drift from the start (bits)")
    ax.set_ylabel("Hamming distance to current elite (bits)")
    ax.set_zlabel("Truth-table fitness")
    ax.set_zlim(-0.05, 1.05)
    ax.set_title(run["title"])
    ax.view_init(elev=22, azim=-58)
    style_3d(ax)
    bar = plt.cm.ScalarMappable(cmap="viridis", norm=gen_norm)
    bar.set_array([])
    fig.colorbar(bar, ax=ax, shrink=0.62, pad=0.08, label="Generation")
    ax.legend(handles=[
        Line2D([0], [0], color=ELITE, lw=2.2, label="Elite"),
        Line2D([0], [0], marker="*", color="none", markerfacecolor=ELITE, markersize=10, label="Start"),
        Line2D([0], [0], marker="D", color="none", markerfacecolor=ELITE, markersize=5, label="End"),
    ], fontsize=7, loc="upper left")
    fig.text(
        0.5, 0.01,
        "Drift is Hamming distance to the generation-0 elite. The elite of each generation sits at Hamming 0.",
        ha="center", fontsize=7,
    )
    fig.subplots_adjust(left=0.02, right=0.90, bottom=0.08, top=0.94)
    fig.savefig(out_dir / "cloud_drift.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    import plotly.graph_objects as go

    html = go.Figure()
    html.add_trace(go.Scatter3d(
        x=drift.ravel(), y=hamming.ravel(), z=fitness.ravel(), mode="markers",
        marker=dict(
            size=3, color=point_gen, colorscale="Viridis", opacity=0.55,
            colorbar=dict(title="Generation"),
            cmin=int(generations[0]), cmax=int(generations[-1]),
        ),
        customdata=np.column_stack([point_gen, fitness.ravel(), drift.ravel(), hamming.ravel()]),
        hovertemplate=(
            "generation %{customdata[0]:.0f}<br>fitness %{customdata[1]:.3f}<br>"
            "drift %{customdata[2]:.0f}<br>Hamming to elite %{customdata[3]:.0f}<extra></extra>"
        ),
        name="Population",
    ))
    html.add_trace(go.Scatter3d(
        x=drift[:, 0], y=hamming[:, 0], z=fitness[:, 0], mode="lines+markers",
        line=dict(color=ELITE, width=6),
        marker=dict(size=3, color=ELITE),
        name="Elite",
    ))
    html.update_layout(
        title=run["title"],
        scene=dict(
            xaxis_title="Drift from the start (bits)",
            yaxis_title="Hamming distance to current elite (bits)",
            zaxis_title="Truth-table fitness",
            zaxis=dict(range=[-0.05, 1.05]),
            aspectmode="manual", aspectratio=dict(x=1.2, y=0.8, z=0.7),
        ),
        margin=dict(l=0, r=0, t=60, b=0),
    )
    html.write_html(out_dir / "cloud_drift.html", include_plotlyjs=True, full_html=True)


def write_travel(run: dict, cloud: dict, moves: dict[str, np.ndarray], out_dir: Path, note: str) -> None:
    generations = run["generations"]
    fitness = run["fitness"]
    point_gen = np.repeat(generations, fitness.shape[1])
    gen_norm = Normalize(vmin=int(generations[0]), vmax=int(generations[-1]))
    fig = plt.figure(figsize=(8.2, 6.4))
    ax = fig.add_subplot(111, projection="3d")
    ax.scatter(
        cloud["d0"].ravel(), cloud["d_final"].ravel(), fitness.ravel(),
        c=point_gen, cmap="viridis", norm=gen_norm, s=8, alpha=0.35, linewidths=0, depthshade=False,
    )
    elite_x = cloud["d0"][:, 0]
    elite_y = cloud["d_final"][:, 0]
    elite_z = fitness[:, 0]
    ax.plot(elite_x, elite_y, elite_z, color=ELITE, lw=2.2)
    improved = moves["improved"]
    neutral = moves["neutral"]
    ax.scatter(elite_x[improved], elite_y[improved], elite_z[improved], s=36, c=ELITE, depthshade=False)
    ax.scatter(elite_x[neutral], elite_y[neutral], elite_z[neutral], s=10, c=ELITE, depthshade=False)
    ax.scatter([elite_x[0]], [elite_y[0]], [elite_z[0]], s=90, c=ELITE, marker="*", depthshade=False)
    ax.scatter([elite_x[-1]], [elite_y[-1]], [elite_z[-1]], s=36, c=ELITE, marker="D", depthshade=False)
    ax.set_xlabel("Hamming to generation-0 elite")
    ax.set_ylabel("Hamming to final elite")
    ax.set_zlabel("Truth-table fitness")
    ax.set_zlim(-0.05, 1.05)
    ax.set_title(run["title"])
    style_3d(ax)
    bar = plt.cm.ScalarMappable(cmap="viridis", norm=gen_norm)
    bar.set_array([])
    fig.colorbar(bar, ax=ax, shrink=0.62, pad=0.08, label="Generation")
    ax.legend(handles=[
        Line2D([0], [0], color=ELITE, lw=2.2, label="Elite"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=ELITE, markersize=7, label="Fitness increased"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=ELITE, markersize=4, label="Neutral move"),
        Line2D([0], [0], marker="*", color="none", markerfacecolor=ELITE, markersize=10, label="Start"),
        Line2D([0], [0], marker="D", color="none", markerfacecolor=ELITE, markersize=5, label="End"),
    ], fontsize=7, loc="upper left")
    fig.text(0.5, 0.01, note, ha="center", fontsize=7)
    fig.subplots_adjust(left=0.02, right=0.90, bottom=0.08, top=0.94)
    fig.savefig(out_dir / "cloud_travel.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def write_sections(run: dict, cloud: dict, out_dir: Path, note: str) -> None:
    plan = snapshot_plan(run["generations"], run["fitness"][:, 0], run["mutation"])
    coords = cloud["coords"]
    limit = float(np.max(np.abs(coords))) * 1.08
    if limit == 0:
        limit = 1.0
    columns = 5
    rows = int(np.ceil(len(plan) / columns))
    fig = plt.figure(figsize=(13.6, 3.05 * rows + 3.4))
    grid = fig.add_gridspec(rows + 2, columns, height_ratios=[1] * rows + [0.36, 0.36], hspace=1.35, wspace=0.34)
    fit_norm = Normalize(vmin=float(run["fitness"].min()), vmax=float(run["fitness"].max()))
    lookup = {int(generation): index for index, generation in enumerate(run["generations"])}
    panels = []
    for slot, (generation, tag) in enumerate(plan):
        ax = fig.add_subplot(grid[slot // columns, slot % columns])
        panels.append(ax)
        index = lookup[generation]
        block = coords[index]
        ax.scatter(
            block[:, 0], block[:, 1], c=run["fitness"][index], cmap="viridis", norm=fit_norm,
            s=18, linewidths=0, zorder=2,
        )
        ax.scatter(block[0, 0], block[0, 1], s=70, facecolors="none", edgecolors=ELITE, linewidths=1.2, zorder=4)
        ax.scatter([0], [0], s=28, c=CENTROID, marker="+", zorder=3)
        ring = ellipse_ring(block)
        if ring is not None:
            ax.plot(ring[0], ring[1], color=SPREAD, lw=1.0)
        ax.set_xlim(-limit, limit)
        ax.set_ylim(-limit, limit)
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=7)
        ax.set_xlabel("Cross-section (bits)", fontsize=7)
        ax.set_ylabel("Cross-section (bits)", fontsize=7)
        ax.set_title(
            f"Gen {generation} · {tag}\nbest {run['fitness'][index, 0]:.3f} · width {cloud['width'][index]:.0f}",
            fontsize=7.5, pad=2,
        )
    for slot in range(len(plan), rows * columns):
        fig.add_subplot(grid[slot // columns, slot % columns]).set_axis_off()
    bar = plt.cm.ScalarMappable(cmap="viridis", norm=fit_norm)
    bar.set_array([])
    fig.colorbar(bar, ax=panels, shrink=0.55, label="Truth-table fitness", pad=0.01)
    width_ax = fig.add_subplot(grid[rows, :])
    fit_ax = fig.add_subplot(grid[rows + 1, :], sharex=width_ax)
    generations = run["generations"]
    width_ax.plot(generations, cloud["width"], color=SPREAD, lw=1.5)
    fit_ax.plot(generations, run["fitness"][:, 0], color="#2a7a4b", lw=1.5)
    for generation, _tag in plan:
        width_ax.axvline(generation, color="#888888", lw=0.7, ls="--")
        fit_ax.axvline(generation, color="#888888", lw=0.7, ls="--")
    width_ax.set_ylabel("Width (bits)", fontsize=8)
    fit_ax.set_ylabel("Best fitness", fontsize=8)
    fit_ax.set_xlabel("Generation")
    fit_ax.set_ylim(-0.05, 1.05)
    width_ax.tick_params(labelsize=7)
    fit_ax.tick_params(labelsize=7)
    width_ax.grid(True, alpha=0.3)
    fit_ax.grid(True, alpha=0.3)
    fig.suptitle(run["title"], fontsize=14)
    fig.text(0.5, 0.01, f"{FOOTER}   {note}", ha="center", fontsize=7)
    fig.savefig(out_dir / "cloud_sections.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def write_html(run: dict, cloud: dict, moves: dict[str, np.ndarray], out_dir: Path, note: str) -> None:
    import plotly.graph_objects as go

    generations = run["generations"]
    fitness = run["fitness"]
    coords = cloud["coords"]
    count, population, _axes = coords.shape
    point_gen = np.repeat(generations, population)
    points = coords.reshape(-1, 2)
    point_fit = fitness.ravel()
    point_d0 = cloud["d0"].ravel()
    radius = np.linalg.norm(points, axis=1)
    roles = np.where(np.arange(count * population) % population == 0, "elite", "child")
    custom = np.column_stack([point_gen, point_fit, point_d0, radius])
    hover = (
        "generation %{customdata[0]:.0f}<br>fitness %{customdata[1]:.3f}<br>"
        "Hamming to gen 0 %{customdata[2]:.0f}<br>radius %{customdata[3]:.1f} bits<br>role %{text}<extra></extra>"
    )
    fit_span = [float(fitness.min()), float(fitness.max())]
    full = count - 1

    def shown_opacity(shown: int) -> list[float]:
        if shown <= 0:
            return [1.0] + [0.0] * full
        return [0.16 + 0.84 * (age / shown) if age <= shown else 0.0 for age in range(count)]

    opening = shown_opacity(full)
    tube = go.Figure()
    for index in range(count):
        sl = slice(index * population, (index + 1) * population)
        tube.add_trace(go.Scatter3d(
            x=point_gen[sl], y=points[sl, 0], z=points[sl, 1], mode="markers",
            marker=dict(
                size=3, color=point_fit[sl], colorscale="Viridis", cmin=fit_span[0], cmax=fit_span[1],
                opacity=opening[index], showscale=index == 0,
                colorbar=dict(title="Fitness", x=-0.08, len=0.6) if index == 0 else None,
            ),
            text=roles[sl], customdata=custom[sl],
            name="Population" if index == 0 else None,
            showlegend=index == 0, legendgroup="population", hovertemplate=hover,
        ))
    centroid_trace = count
    elite_trace = count + 1
    tube.add_trace(go.Scatter3d(
        x=generations, y=np.zeros(count), z=np.zeros(count), mode="markers+lines",
        marker=dict(
            size=3, color=cloud["centroid_d0"], colorscale="Greens",
            colorbar=dict(title="Centroid Hamming<br>to generation 0", x=1.02, len=0.6),
        ),
        line=dict(color=CENTROID, width=4), name="Centroid",
    ))
    tube.add_trace(go.Scatter3d(
        x=generations, y=coords[:, 0, 0], z=coords[:, 0, 1], mode="lines+markers",
        line=dict(color=ELITE, width=6),
        marker=dict(
            size=7, color=fitness[:, 0], colorscale="Viridis", cmin=fit_span[0], cmax=fit_span[1],
            showscale=False, line=dict(width=2, color=ELITE),
        ),
        name="Elite",
    ))
    frames = []
    names = [str(int(generation)) for generation in generations]
    centroid_d0 = cloud["centroid_d0"]
    for index, name in enumerate(names):
        opacity = shown_opacity(index)
        prefix = index + 1
        frames.append(go.Frame(
            name=name,
            traces=list(range(count)) + [centroid_trace, elite_trace],
            data=(
                [{"type": "scatter3d", "marker": {"opacity": value}} for value in opacity]
                + [{
                    "type": "scatter3d",
                    "x": generations[:prefix], "y": np.zeros(prefix), "z": np.zeros(prefix),
                    "marker": {"color": centroid_d0[:prefix]},
                }, {
                    "type": "scatter3d",
                    "x": generations[:prefix], "y": coords[:prefix, 0, 0], "z": coords[:prefix, 0, 1],
                    "marker": {"color": fitness[:prefix, 0]},
                }]
            ),
        ))
    tube.frames = frames
    y_lo = float(points[:, 0].min())
    y_hi = float(points[:, 0].max())
    z_lo = float(points[:, 1].min())
    z_hi = float(points[:, 1].max())
    y_wall = y_lo - 0.14 * max(y_hi - y_lo, 1.0)
    z_fit = z_lo + fitness[:, 0] * (z_hi - z_lo)
    step_x = np.repeat(generations.astype(float), 2)[1:]
    step_z = np.repeat(z_fit, 2)[:-1]
    tube.add_trace(go.Scatter3d(
        x=step_x, y=np.full(step_x.shape, y_wall), z=step_z, mode="lines",
        line=dict(color="#2a7a4b", width=3), name="Best fitness on the side wall", opacity=0.45,
    ))
    for index in range(0, count, 10):
        ring = ellipse_ring(coords[index])
        if ring is None:
            continue
        tube.add_trace(go.Scatter3d(
            x=np.full(ring[0].shape, generations[index]), y=ring[0], z=ring[1], mode="lines",
            line=dict(color=SPREAD, width=3), name="1-sigma ring", showlegend=index == 0, opacity=0.7,
        ))
    play = dict(
        type="buttons", showactive=False, x=0.02, y=0,
        buttons=[dict(
            label="Play", method="animate",
            args=[names, {"frame": {"duration": 40, "redraw": True}, "transition": {"duration": 0}, "fromcurrent": False}],
        )],
    )
    slider = dict(
        active=count - 1, pad=dict(t=28), currentvalue=dict(prefix="Generation "),
        steps=[dict(
            method="animate", label=name,
            args=[[name], {"mode": "immediate", "frame": {"duration": 0, "redraw": True}, "transition": {"duration": 0}}],
        ) for name in names],
    )
    tube.update_layout(
        title=dict(text=f"{run['title']}<br><sup>{FOOTER}<br>{note}</sup>"),
        scene=dict(
            xaxis_title="Generation", yaxis_title="Cross-section (bits)", zaxis_title="Cross-section (bits)",
            aspectmode="manual", aspectratio=dict(x=1.4, y=1, z=1),
        ),
        margin=dict(l=0, r=0, t=90, b=0),
        updatemenus=[play], sliders=[slider],
        legend=dict(font=dict(size=11)),
    )
    tube.write_html(out_dir / "cloud_tube.html", include_plotlyjs=True, full_html=True)

    travel = go.Figure()
    d0 = cloud["d0"].ravel()
    d_final = cloud["d_final"].ravel()
    flat_fit = fitness.ravel()
    travel_hover = (
        "generation %{customdata[0]:.0f}<br>fitness %{customdata[1]:.3f}<br>"
        "Hamming to gen 0 %{customdata[2]:.0f}<br>role %{text}<extra></extra>"
    )
    gen_span = [float(generations[0]), float(generations[-1])]
    for index in range(count):
        sl = slice(index * population, (index + 1) * population)
        travel.add_trace(go.Scatter3d(
            x=d0[sl], y=d_final[sl], z=flat_fit[sl], mode="markers",
            marker=dict(
                size=3, color=float(generations[index]), colorscale="Viridis",
                cmin=gen_span[0], cmax=gen_span[1], opacity=opening[index], showscale=index == 0,
                colorbar=dict(title="Generation") if index == 0 else None,
            ),
            text=roles[sl], customdata=custom[sl],
            name="Population" if index == 0 else None,
            showlegend=index == 0, legendgroup="population", hovertemplate=travel_hover,
        ))
    improved = moves["improved"]
    neutral = moves["neutral"]
    elite_size = np.full(count, 3.0)
    elite_size[neutral] = 5.0
    elite_size[improved] = 9.0
    elite_size[0] = 12.0
    elite_size[-1] = 8.0
    symbols = np.array(["circle"] * count, dtype=object)
    symbols[0] = "diamond-open"
    symbols[-1] = "diamond"
    travel.add_trace(go.Scatter3d(
        x=cloud["d0"][:, 0], y=cloud["d_final"][:, 0], z=fitness[:, 0],
        mode="lines+markers",
        line=dict(color=ELITE, width=6),
        marker=dict(size=elite_size, color=ELITE, symbol=symbols),
        name="Elite",
    ))
    travel_frames = []
    for index, name in enumerate(names):
        prefix = index + 1
        travel_frames.append(go.Frame(
            name=name,
            traces=list(range(count)) + [count],
            data=(
                [{"type": "scatter3d", "marker": {"opacity": value}} for value in shown_opacity(index)]
                + [{
                    "type": "scatter3d",
                    "x": cloud["d0"][:prefix, 0],
                    "y": cloud["d_final"][:prefix, 0],
                    "z": fitness[:prefix, 0],
                    "marker": {"size": elite_size[:prefix], "symbol": symbols[:prefix]},
                }]
            ),
        ))
    travel.frames = travel_frames
    travel.update_layout(
        title=dict(text=f"{run['title']}<br><sup>{note}</sup>"),
        scene=dict(
            xaxis_title="Hamming to generation-0 elite",
            yaxis_title="Hamming to final elite",
            zaxis_title="Truth-table fitness",
            zaxis=dict(range=[-0.05, 1.05]),
            aspectmode="manual", aspectratio=dict(x=1, y=1, z=0.7),
        ),
        margin=dict(l=0, r=0, t=80, b=0),
        updatemenus=[play], sliders=[slider],
    )
    travel.write_html(out_dir / "cloud_travel.html", include_plotlyjs=True, full_html=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw the SAGA population cloud from exact Hamming distances.")
    parser.add_argument("--log", type=Path, default=ROOT / "adder2/evolution/out/saga_4bit_g300_m2_p21_e1_seed13/recovery.json")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    np.random.seed(args.seed)
    run = load_run(args.log)
    cloud = cross_sections(run["genotypes"])
    comparable = np.isfinite(run["logged_width"])
    if comparable.any():
        gap = float(np.nanmax(np.abs(cloud["width"][comparable] - run["logged_width"][comparable])))
        if gap > 1e-6:
            raise SystemExit(f"Mean pairwise Hamming disagrees with the log by {gap}.")
    moves = movement(run["genotypes"], run["fitness"])
    out_dir = args.out if args.out is not None else args.log.resolve().parent / "cloud"
    out_dir.mkdir(parents=True, exist_ok=True)
    note = honesty(run, cloud)
    write_tube(run, cloud, out_dir, note)
    write_drift(run, out_dir)
    write_travel(run, cloud, moves, out_dir, note)
    write_sections(run, cloud, out_dir, note)
    write_html(run, cloud, moves, out_dir, note)
    print(note)
    print(FOOTER)
    print(
        f"cross-section capture {np.nanmin(cloud['captured']) * 100:.0f}–"
        f"{np.nanmax(cloud['captured']) * 100:.0f}%   "
        f"rescale ×{np.nanmin(cloud['scales']):.2f}–×{np.nanmax(cloud['scales']):.2f}"
    )
    print(f"Wrote {out_dir}")


if __name__ == "__main__":
    main()
