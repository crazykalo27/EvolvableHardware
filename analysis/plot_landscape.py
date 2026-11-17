"""Where the SAGA population sits in genotype space.

The recovery log already stores each generation's full population. This script
only reads it. Squared Euclidean distance between binary vectors is their
Hamming distance, so the default PCA is one shared coordinate system for every
generation.

    python analysis/plot_landscape.py --log adder2/evolution/out/saga_4bit_g300_m2_p21_e1_seed13/recovery.json
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

ROOT = Path(__file__).resolve().parents[1]
ELITE = "#c45c12"
CENTROID = "#2a7a4b"
SPREAD = "#6b5b95"
TITLE_NAMES = {"adder2": "2-bit adder", "adder4": "4-bit adder", "xor": "XOR"}


def load_run(path: Path) -> dict:
    """Read one recovery. Elite is population index 0. schedule_flips is the next rate."""
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
    if bits.min() < 0 or bits.max() > 1:
        raise SystemExit("Genotypes must be bit strings of 0 and 1.")
    genotypes = bits.reshape(len(history), population, length)
    fitness = np.array([row["scores"] for row in history], dtype=np.float64)
    generations = np.array([row["generation"] for row in history], dtype=int)
    mutation = np.array(
        [
            row.get("schedule_flips", row.get("bottom_expected_flips", row.get("mutation_level", 0)))
            for row in history
        ],
        dtype=np.float64,
    )
    circuit = saved.get("circuit", "adder2")
    title = (
        f"{TITLE_NAMES.get(circuit, circuit)} - {saved.get('algorithm', 'saga')} - "
        f"{saved.get('fault_bits', 4)}-bit fault"
    )
    return {
        "genotypes": genotypes,
        "fitness": fitness,
        "generations": generations,
        "mutation": mutation,
        "title": title,
    }


def rankdata(values: np.ndarray) -> np.ndarray:
    """Average ranks for ties. The sort is stable so the result does not depend on order."""
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=np.float64)
    ordered = values[order]
    start = 0
    while start < len(values):
        stop = start + 1
        while stop < len(values) and ordered[stop] == ordered[start]:
            stop += 1
        ranks[order[start:stop]] = 0.5 * ((start + 1) + stop)
        start = stop
    return ranks


def spearman(left: np.ndarray, right: np.ndarray) -> float:
    left_rank = rankdata(left)
    right_rank = rankdata(right)
    left_rank -= left_rank.mean()
    right_rank -= right_rank.mean()
    denom = np.linalg.norm(left_rank) * np.linalg.norm(right_rank)
    if denom == 0:
        return 0.0
    return float(left_rank @ right_rank / denom)


def orient(vector: np.ndarray) -> np.ndarray:
    pivot = int(np.argmax(np.abs(vector)))
    if vector[pivot] < 0:
        return -vector
    return vector


def project_pca(flat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """One PCA of every individual. Sign of each axis is fixed by its largest loading."""
    centered = flat - flat.mean(axis=0)
    eigenvalues, vectors = np.linalg.eigh(centered.T @ centered)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = np.clip(eigenvalues[order], 0, None)
    vectors = vectors[:, order]
    vectors[:, 0] = orient(vectors[:, 0])
    vectors[:, 1] = orient(vectors[:, 1])
    total = float(eigenvalues.sum())
    explained = eigenvalues[:2] / total if total else np.zeros(2)
    return centered @ vectors[:, :2], explained


def project_pls(flat: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Axis 1 follows fitness. Axis 2 is the first principal direction of what remains."""
    centered = flat - flat.mean(axis=0)
    response = target - target.mean()
    weights = centered.T @ response
    scale = np.linalg.norm(weights)
    if scale == 0:
        weights = np.zeros(flat.shape[1])
        weights[0] = 1.0
    else:
        weights = weights / scale
    scores = centered @ weights
    if scores @ response < 0:
        weights = -weights
        scores = -scores
    denominator = float(scores @ scores)
    residual = centered
    if denominator > 0:
        loadings = centered.T @ scores / denominator
        residual = centered - np.outer(scores, loadings)
    _values, vectors = np.linalg.eigh(residual.T @ residual)
    direction = orient(vectors[:, int(np.argmax(_values))])
    return np.column_stack([scores, residual @ direction])


def project_umap(flat: np.ndarray, seed: int) -> np.ndarray:
    try:
        import umap
    except ImportError as error:
        raise SystemExit("umap-learn is not installed. pca, ref, and pls run without it.") from error
    model = umap.UMAP(n_components=2, metric="hamming", random_state=seed)
    return np.asarray(model.fit_transform(flat.astype(np.float32)), dtype=np.float64)


def hamming_to(genotypes: np.ndarray, reference: np.ndarray) -> np.ndarray:
    return np.abs(genotypes.astype(np.int16) - reference.astype(np.int16)).sum(axis=2)


def sample_distances(flat: np.ndarray, coords: np.ndarray, pairs: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Hamming via the binary identity |a| + |b| - 2 a·b, against embedded Euclidean distance."""
    rng = np.random.default_rng(seed)
    count = flat.shape[0]
    left = rng.integers(0, count, size=pairs)
    right = rng.integers(0, count - 1, size=pairs)
    right = right + (right >= left)
    a = flat[left]
    b = flat[right]
    hamming = a.sum(axis=1) + b.sum(axis=1) - 2 * np.einsum("ij,ij->i", a, b)
    euclidean = np.linalg.norm(coords[left] - coords[right], axis=1)
    return hamming, euclidean


def ellipse(points: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """1-sigma covariance ellipse in the plotting plane."""
    if len(points) < 3:
        return None
    center = points.mean(axis=0)
    cov = np.cov(points, rowvar=False)
    if not np.isfinite(cov).all():
        return None
    values, vectors = np.linalg.eigh(cov)
    values = np.clip(values, 0, None)
    theta = np.linspace(0, 2 * np.pi, 80)
    circle = np.stack([np.cos(theta), np.sin(theta)])
    offset = (vectors * np.sqrt(values)) @ circle
    return center[0] + offset[0], center[1] + offset[1]


def padded_limits(values: np.ndarray) -> tuple[float, float]:
    low = float(values.min())
    high = float(values.max())
    pad = 0.05 * (high - low if high > low else 1.0)
    return low - pad, high + pad


def embed(run: dict, mode: str, seed: int) -> tuple[np.ndarray, str, str, str]:
    genotypes = run["genotypes"]
    generations, population, _length = genotypes.shape
    flat = genotypes.reshape(generations * population, -1).astype(np.float64)
    fitness = run["fitness"].ravel()
    start = genotypes[0, 0]
    final = genotypes[-1, 0]
    to_start = hamming_to(genotypes, start)
    to_final = hamming_to(genotypes, final)
    warning = ""
    if mode == "pca":
        coords, explained = project_pca(flat)
        xlabel = f"PC1 ({100 * explained[0]:.1f}% variance)"
        ylabel = f"PC2 ({100 * explained[1]:.1f}% variance)"
    elif mode == "pls":
        coords = project_pls(flat, fitness)
        xlabel = "PLS fitness direction"
        ylabel = "PC1 of the residual"
    elif mode == "ref":
        coords = np.column_stack([to_start.ravel(), to_final.ravel()])
        xlabel = "Hamming to generation-0 elite"
        ylabel = "Hamming to final elite"
    elif mode == "umap":
        coords = project_umap(flat, seed)
        xlabel = "UMAP 1"
        ylabel = "UMAP 2"
        warning = "UMAP distances are not faithful Hamming distances."
    else:
        raise SystemExit(f"Unknown embedding {mode}")
    return coords.reshape(generations, population, 2), xlabel, ylabel, warning, to_start, to_final


def movement(genotypes: np.ndarray, fitness: np.ndarray) -> dict[str, np.ndarray]:
    elite = genotypes[:, 0]
    score = fitness[:, 0]
    changed = np.zeros(len(score), dtype=bool)
    improved = np.zeros(len(score), dtype=bool)
    worsened = np.zeros(len(score), dtype=bool)
    changed[1:] = np.any(elite[1:] != elite[:-1], axis=1)
    improved[1:] = score[1:] > score[:-1]
    worsened[1:] = score[1:] < score[:-1]
    return {
        "changed": changed,
        "improved": improved,
        "neutral": changed & ~improved & ~worsened,
        "worsened": worsened,
    }


def snapshot_indexes(generations: np.ndarray, improved: np.ndarray, count: int) -> np.ndarray:
    spaced = np.unique(np.round(np.linspace(0, len(generations) - 1, count)).astype(int))
    gains = np.flatnonzero(improved)
    return np.unique(np.concatenate([spaced, gains]))


def footer(run: dict, rho: float, extra: str) -> str:
    genotypes = run["genotypes"]
    generations, population, length = genotypes.shape
    children = population - 1
    text = (
        f"L={length}   N={population} (1 elite + {children} children)   "
        f"G={generations} (generations {run['generations'][0]}–{run['generations'][-1]})   "
        f"Spearman(Hamming, embedded distance)={rho:.3f} on 5000 pairs"
    )
    if extra:
        text = f"{text}   {extra}"
    return text


def style_3d(ax) -> None:
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor((1, 1, 1, 0))
        axis.pane.set_edgecolor("#dddddd")
    ax.tick_params(labelsize=8)
    ax.set_zlabel("Truth-table fitness")
    ax.set_zlim(-0.12, 1.05)


def draw_surface(ax, coords: np.ndarray, fitness: np.ndarray) -> None:
    """Optional kernel smooth. It is fit only to genotypes the search actually scored."""
    flat = coords.reshape(-1, 2)
    values = fitness.ravel()
    width = max(float(np.std(flat, axis=0).mean()) * 0.35, 1e-6)
    grid = 36
    x = np.linspace(flat[:, 0].min(), flat[:, 0].max(), grid)
    y = np.linspace(flat[:, 1].min(), flat[:, 1].max(), grid)
    xx, yy = np.meshgrid(x, y)
    points = np.column_stack([xx.ravel(), yy.ravel()])
    weights = np.exp(-0.5 * ((points[:, None, :] - flat[None, :, :]) ** 2).sum(axis=2) / width**2)
    total = weights.sum(axis=1)
    total[total == 0] = 1
    zz = ((weights @ values) / total).reshape(grid, grid)
    ax.plot_surface(xx, yy, zz, color="#9aa0a6", alpha=0.18, linewidth=0, antialiased=False)


def draw_landscape(ax, run, coords, moves, snapshots, color_elite: str, surface: bool) -> None:
    generations = run["generations"]
    fitness = run["fitness"]
    count = len(generations)
    population = fitness.shape[1]
    xy = coords.reshape(-1, 2)
    point_gen = np.repeat(generations, population)
    point_fit = fitness.ravel()
    norm = Normalize(vmin=generations[0], vmax=generations[-1])
    ax.scatter(
        xy[:, 0], xy[:, 1], point_fit,
        c=point_gen, cmap="viridis", norm=norm, s=7, alpha=0.16, linewidths=0, depthshade=False,
    )
    for index in snapshots:
        block = coords[index]
        ax.scatter(
            block[:, 0], block[:, 1], fitness[index],
            c=np.full(population, generations[index]), cmap="viridis", norm=norm,
            s=18, alpha=0.9, linewidths=0, depthshade=False,
        )
        oval = ellipse(block)
        if oval is not None:
            ax.plot(oval[0], oval[1], np.full(len(oval[0]), fitness[index].mean()), color=SPREAD, lw=1.3)
    elite_xy = coords[:, 0, :]
    elite_fit = fitness[:, 0]
    centroid_xy = coords.mean(axis=1)
    centroid_z = fitness.mean(axis=1)
    if color_elite == "mutation":
        cmap = plt.get_cmap("cividis")
        low = float(run["mutation"].min())
        high = float(run["mutation"].max())
        scale = Normalize(vmin=low, vmax=high if high > low else low + 1)
        for index in range(count - 1):
            ax.plot(
                elite_xy[index:index + 2, 0], elite_xy[index:index + 2, 1], elite_fit[index:index + 2],
                color=cmap(scale(run["mutation"][index])), lw=2.4,
            )
    else:
        ax.plot(elite_xy[:, 0], elite_xy[:, 1], elite_fit, color=ELITE, lw=2.4)
    ax.plot(
        elite_xy[:, 0], elite_xy[:, 1], np.full(count, -0.08),
        color=ELITE, alpha=0.28, lw=1.1,
    )
    ax.plot(centroid_xy[:, 0], centroid_xy[:, 1], centroid_z, color=CENTROID, lw=1.2, ls="--")
    improved = moves["improved"]
    neutral = moves["neutral"]
    ax.scatter(elite_xy[improved, 0], elite_xy[improved, 1], elite_fit[improved], s=36, c=ELITE, depthshade=False)
    ax.scatter(elite_xy[neutral, 0], elite_xy[neutral, 1], elite_fit[neutral], s=10, c=ELITE, depthshade=False)
    if moves["worsened"].any():
        lost = moves["worsened"]
        ax.scatter(elite_xy[lost, 0], elite_xy[lost, 1], elite_fit[lost], s=28, c="#1a1a1a", marker="x", depthshade=False)
    ax.scatter([elite_xy[0, 0]], [elite_xy[0, 1]], [elite_fit[0]], s=90, c=ELITE, marker="*", depthshade=False)
    ax.scatter([elite_xy[-1, 0]], [elite_xy[-1, 1]], [elite_fit[-1]], s=36, c=ELITE, marker="D", depthshade=False)
    if surface:
        draw_surface(ax, coords, fitness)
    style_3d(ax)


def legend_handles(color_elite: str, surface: bool) -> list[Line2D]:
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#3b528b", markersize=5, label="Population"),
        Line2D([0], [0], color=ELITE, lw=2.4, label="Elite" if color_elite == "constant" else "Elite, colored by expected flips"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=ELITE, markersize=7, label="Fitness increased"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=ELITE, markersize=4, label="Neutral move"),
        Line2D([0], [0], marker="*", color="none", markerfacecolor=ELITE, markersize=10, label="Start"),
        Line2D([0], [0], marker="D", color="none", markerfacecolor=ELITE, markersize=5, label="End"),
        Line2D([0], [0], color=CENTROID, lw=1.2, ls="--", label="Centroid"),
        Line2D([0], [0], color=SPREAD, lw=1.3, label="1-sigma spread"),
    ]
    if surface:
        handles.append(Line2D([0], [0], color="#9aa0a6", lw=4, alpha=0.5, label="Kernel smooth, visited points only"))
    return handles


def write_angles(run, coords, moves, snapshots, out_dir: Path, xlabel: str, ylabel: str, note: str, color_elite: str, surface: bool) -> None:
    views = (("oblique", 22, -58), ("side", 12, 24), ("high", 72, -90))
    norm = Normalize(vmin=run["generations"][0], vmax=run["generations"][-1])
    for name, elev, azim in views:
        fig = plt.figure(figsize=(8.4, 6.6))
        ax = fig.add_subplot(111, projection="3d")
        draw_landscape(ax, run, coords, moves, snapshots, color_elite, surface)
        ax.view_init(elev=elev, azim=azim)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(run["title"])
        mappable = plt.cm.ScalarMappable(cmap="viridis", norm=norm)
        mappable.set_array([])
        fig.colorbar(mappable, ax=ax, shrink=0.62, pad=0.08, label="Generation")
        if color_elite == "mutation":
            low = float(run["mutation"].min())
            high = float(run["mutation"].max())
            flip = plt.cm.ScalarMappable(cmap="cividis", norm=Normalize(vmin=low, vmax=high if high > low else low + 1))
            flip.set_array([])
            fig.colorbar(flip, ax=ax, shrink=0.62, pad=0.14, label="Expected flips")
        ax.legend(handles=legend_handles(color_elite, surface), fontsize=7, loc="upper left")
        fig.text(0.5, 0.01, note, ha="center", va="bottom", fontsize=7)
        if surface:
            fig.text(0.5, 0.035, "kernel-smoothed from visited points only", ha="center", va="bottom", fontsize=7)
        fig.subplots_adjust(left=0.02, right=0.88, bottom=0.08, top=0.94)
        fig.savefig(out_dir / f"landscape_3d_{name}.png", dpi=300)
        plt.close(fig)


def write_hamming(run, to_start, to_final, moves, out_dir: Path, note: str) -> None:
    fitness = run["fitness"]
    generations = run["generations"]
    point_gen = np.repeat(generations, fitness.shape[1])
    norm = Normalize(vmin=generations[0], vmax=generations[-1])
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.8), sharey=True)
    series = (
        (axes[0], to_start, "Hamming to generation-0 elite"),
        (axes[1], to_final, "Hamming to final elite"),
    )
    for ax, distance, label in series:
        ax.scatter(
            distance.ravel(), fitness.ravel(), c=point_gen, cmap="viridis", norm=norm,
            s=8, alpha=0.35, linewidths=0,
        )
        ax.plot(distance[:, 0], fitness[:, 0], color=ELITE, lw=2.0, label="Elite")
        improved = moves["improved"]
        neutral = moves["neutral"]
        ax.scatter(distance[improved, 0], fitness[improved, 0], s=28, c=ELITE, label="Fitness increased", zorder=4)
        ax.scatter(distance[neutral, 0], fitness[neutral, 0], s=10, c=ELITE, label="Neutral move", zorder=4)
        ax.scatter(distance[0, 0], fitness[0, 0], s=70, c=ELITE, marker="*", label="Start", zorder=5)
        ax.scatter(distance[-1, 0], fitness[-1, 0], s=28, c=ELITE, marker="D", label="End", zorder=5)
        ax.set_xlabel(label)
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=8)
    axes[0].set_ylabel("Truth-table fitness")
    axes[0].legend(fontsize=7, loc="upper left")
    fig.suptitle(run["title"])
    mappable = plt.cm.ScalarMappable(cmap="viridis", norm=norm)
    mappable.set_array([])
    fig.colorbar(mappable, ax=axes, label="Generation", shrink=0.85)
    fig.text(0.5, 0.01, f"{note}   Axes are exact Hamming distances, with no projection.", ha="center", fontsize=7)
    fig.subplots_adjust(left=0.06, right=0.90, bottom=0.16, top=0.88, wspace=0.16)
    fig.savefig(out_dir / "landscape_hamming.png", dpi=300)
    plt.close(fig)


def write_frames(run, coords, out_dir: Path, xlabel: str, ylabel: str, note: str) -> None:
    chosen = np.unique(np.round(np.linspace(0, len(run["generations"]) - 1, 6)).astype(int))
    fig, axes = plt.subplots(2, 3, figsize=(11.2, 7.2), sharex=True, sharey=True)
    xlim = padded_limits(coords[:, :, 0])
    ylim = padded_limits(coords[:, :, 1])
    for ax, index in zip(axes.ravel(), chosen):
        block = coords[index]
        ax.scatter(block[:, 0], block[:, 1], s=16, c=SPREAD, alpha=0.75, linewidths=0, label="Population")
        oval = ellipse(block)
        if oval is not None:
            ax.plot(oval[0], oval[1], color=SPREAD, lw=1.2, label="1-sigma spread")
        ax.plot(coords[: index + 1, 0, 0], coords[: index + 1, 0, 1], color=ELITE, lw=1.4, alpha=0.8, label="Elite path")
        ax.plot(
            coords[: index + 1].mean(axis=1)[:, 0], coords[: index + 1].mean(axis=1)[:, 1],
            color=CENTROID, lw=1.0, ls="--", label="Centroid",
        )
        ax.scatter(block[0, 0], block[0, 1], s=70, c=ELITE, marker="*", zorder=5, label="Elite")
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.set_title(f"Generation {run['generations'][index]}", fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=7)
    for ax in axes[1]:
        ax.set_xlabel(xlabel, fontsize=8)
    for ax in axes[:, 0]:
        ax.set_ylabel(ylabel, fontsize=8)
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.suptitle(run["title"], y=0.98, fontsize=14)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.94), ncol=5, fontsize=8, frameon=False)
    fig.text(0.5, 0.01, note, ha="center", fontsize=7)
    fig.tight_layout(rect=(0, 0.045, 1, 0.86))
    fig.savefig(out_dir / "landscape_frames.png", dpi=300)
    plt.close(fig)


def color_rgb(fraction: float) -> str:
    red, green, blue, _alpha = plt.get_cmap("viridis")(fraction)
    return f"rgb({int(red * 255)},{int(green * 255)},{int(blue * 255)})"


def pairwise_width(genotypes: np.ndarray) -> np.ndarray:
    """Mean Hamming distance between the genomes alive in each generation."""
    bits = genotypes.astype(np.float64)
    counts = bits.sum(axis=2)
    dots = np.einsum("gni,gmi->gnm", bits, bits)
    distance = counts[:, :, None] + counts[:, None, :] - 2 * dots
    upper = np.triu_indices(genotypes.shape[1], k=1)
    return distance[:, upper[0], upper[1]].mean(axis=1)


def write_time(run: dict, moves: dict[str, np.ndarray], out_dir: Path) -> None:
    """Fitness, location, and cloud width on one generation axis."""
    flat = run["genotypes"].reshape(-1, run["genotypes"].shape[-1]).astype(np.float64)
    projected, explained = project_pca(flat)
    coords = projected.reshape(run["genotypes"].shape[0], run["genotypes"].shape[1], 2)
    generations = run["generations"]
    fitness = run["fitness"]
    width = pairwise_width(run["genotypes"])
    gains = generations[moves["improved"]]
    fig, axes = plt.subplots(4, 1, figsize=(8.2, 10.4), sharex=True)
    for ax in axes:
        for generation in gains:
            ax.axvline(generation, color=ELITE, alpha=0.18, lw=1, zorder=0)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=8)

    axes[0].plot(generations, fitness[:, 0], color="#2a7a4b", lw=1.8, label="Best fitness")
    axes[0].plot(generations, fitness.mean(axis=1), color="#3a6ea5", lw=1.4, label="Mean fitness")
    axes[0].set_ylim(-0.05, 1.05)
    axes[0].set_ylabel("Truth-table fitness")
    axes[0].legend(fontsize=7, loc="upper left")

    labels = (
        f"PC1 ({100 * explained[0]:.1f}% variance)",
        f"PC2 ({100 * explained[1]:.1f}% variance)",
    )
    for ax, axis, label in zip(axes[1:3], (0, 1), labels):
        for index in range(coords.shape[1]):
            ax.scatter(
                generations, coords[:, index, axis], s=8, c=SPREAD, alpha=0.22,
                linewidths=0, zorder=2, label="Each genome" if index == 0 else None,
            )
        ax.plot(generations, coords[:, 0, axis], color=ELITE, lw=1.8, zorder=3, label="Elite")
        ax.plot(generations, coords[:, :, axis].mean(axis=1), color=CENTROID, lw=1.2, ls="--", zorder=3, label="Centroid")
        ax.set_ylabel(label)
        ax.legend(fontsize=7, loc="best")

    axes[3].plot(generations, width, color=SPREAD, lw=1.8, label="Mean pairwise Hamming")
    axes[3].set_ylabel("Hamming distance")
    axes[3].set_xlabel("Generation")
    axes[3].legend(fontsize=7, loc="best")
    fig.suptitle(run["title"], fontsize=14)
    length = run["genotypes"].shape[-1]
    population = run["genotypes"].shape[1]
    fig.text(
        0.5, 0.005,
        f"L={length}   N={population} (1 elite + {population - 1} children)   "
        f"G={len(generations)} (generations {generations[0]}–{generations[-1]})   "
        "Vertical lines mark a higher elite score. PC1 and PC2 match the landscape.",
        ha="center", va="bottom", fontsize=7,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    fig.savefig(out_dir / "landscape_time.png", dpi=300)
    plt.close(fig)


def write_html(run, coords, moves, snapshots, out_dir: Path, xlabel: str, ylabel: str, note: str, surface: bool) -> None:
    import plotly.graph_objects as go

    generations = run["generations"]
    fitness = run["fitness"]
    count, population, _length = run["genotypes"].shape
    start = run["genotypes"][0, 0]
    to_start = hamming_to(run["genotypes"], start)
    xy = coords.reshape(-1, 2)
    point_gen = np.repeat(generations, population)
    point_fit = fitness.ravel()
    roles = np.where(np.arange(count * population) % population == 0, "elite", "child")
    custom = np.column_stack([point_gen, point_fit, to_start.ravel()])
    figure = go.Figure()
    figure.add_trace(go.Scatter3d(
        x=xy[:, 0], y=xy[:, 1], z=point_fit, mode="markers",
        marker=dict(size=2, color=point_gen, colorscale="Viridis", opacity=0.35, colorbar=dict(title="Generation")),
        text=roles, customdata=custom, name="Population",
        hovertemplate=(
            "generation %{customdata[0]:.0f}<br>fitness %{customdata[1]:.3f}<br>"
            "Hamming to gen 0 %{customdata[2]:.0f}<br>%{text}<extra></extra>"
        ),
    ))
    highlight = coords[0]
    figure.add_trace(go.Scatter3d(
        x=highlight[:, 0], y=highlight[:, 1], z=fitness[0], mode="markers",
        marker=dict(size=4, color=color_rgb(0), opacity=0.95),
        text=["elite"] + ["child"] * (population - 1),
        customdata=np.column_stack([np.full(population, generations[0]), fitness[0], to_start[0]]),
        name="This generation",
        hovertemplate=(
            "generation %{customdata[0]:.0f}<br>fitness %{customdata[1]:.3f}<br>"
            "Hamming to gen 0 %{customdata[2]:.0f}<br>%{text}<extra></extra>"
        ),
    ))
    elite_xy = coords[:, 0, :]
    elite_fit = fitness[:, 0]
    centroid_xy = coords.mean(axis=1)
    figure.add_trace(go.Scatter3d(
        x=elite_xy[:, 0], y=elite_xy[:, 1], z=elite_fit, mode="lines+markers",
        line=dict(color=ELITE, width=6),
        marker=dict(size=3, color=ELITE),
        name="Elite",
    ))
    figure.add_trace(go.Scatter3d(
        x=centroid_xy[:, 0], y=centroid_xy[:, 1], z=fitness.mean(axis=1), mode="lines",
        line=dict(color=CENTROID, width=3, dash="dash"), name="Centroid",
    ))
    figure.add_trace(go.Scatter3d(
        x=elite_xy[:, 0], y=elite_xy[:, 1], z=np.full(count, -0.08), mode="lines",
        line=dict(color=ELITE, width=2), opacity=0.3, name="Elite on the floor",
    ))
    shown = False
    for index in snapshots:
        oval = ellipse(coords[index])
        if oval is None:
            continue
        figure.add_trace(go.Scatter3d(
            x=oval[0], y=oval[1], z=np.full(len(oval[0]), fitness[index].mean()), mode="lines",
            line=dict(color=SPREAD, width=3), name="1-sigma spread", showlegend=not shown,
        ))
        shown = True
    frames = []
    names = []
    for index in range(count):
        fraction = 0 if count == 1 else index / (count - 1)
        name = str(int(generations[index]))
        names.append(name)
        block = coords[index]
        frames.append(go.Frame(
            name=name,
            traces=[1, 2, 3, 4],
            data=[
                go.Scatter3d(
                    x=block[:, 0], y=block[:, 1], z=fitness[index],
                    marker=dict(size=4, color=color_rgb(fraction), opacity=0.95),
                    text=["elite"] + ["child"] * (population - 1),
                    customdata=np.column_stack([
                        np.full(population, generations[index]), fitness[index], to_start[index],
                    ]),
                ),
                go.Scatter3d(x=elite_xy[: index + 1, 0], y=elite_xy[: index + 1, 1], z=elite_fit[: index + 1]),
                go.Scatter3d(
                    x=centroid_xy[: index + 1, 0], y=centroid_xy[: index + 1, 1],
                    z=fitness[: index + 1].mean(axis=1),
                ),
                go.Scatter3d(
                    x=elite_xy[: index + 1, 0], y=elite_xy[: index + 1, 1],
                    z=np.full(index + 1, -0.08),
                ),
            ],
        ))
    figure.frames = frames
    steps = [
        dict(
            method="animate",
            label=name,
            args=[[name], {"mode": "immediate", "frame": {"duration": 0, "redraw": True}, "transition": {"duration": 0}}],
        )
        for name in names
    ]
    figure.update_layout(
        title=dict(text=f"{run['title']}<br><sup>{note}</sup>"),
        scene=dict(
            xaxis_title=xlabel, yaxis_title=ylabel, zaxis_title="Truth-table fitness",
            aspectmode="manual", aspectratio=dict(x=1, y=1, z=0.65),
            zaxis=dict(range=[-0.12, 1.05]),
        ),
        legend=dict(font=dict(size=11)),
        margin=dict(l=0, r=0, t=80, b=0),
        updatemenus=[dict(
            type="buttons", showactive=False, x=0.05, y=0,
            buttons=[dict(
                label="Play",
                method="animate",
                args=[names, {"frame": {"duration": 60, "redraw": True}, "transition": {"duration": 0}, "fromcurrent": False}],
            )],
        )],
        sliders=[dict(active=0, pad=dict(t=30), currentvalue=dict(prefix="Generation "), steps=steps)],
    )
    figure.write_html(out_dir / "landscape_3d.html", include_plotlyjs=True, full_html=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot the SAGA population in genotype space.")
    parser.add_argument("--log", type=Path, default=ROOT / "adder2/evolution/out/saga_4bit_g300_m2_p21_e1_seed13/recovery.json")
    parser.add_argument("--embedding", choices=("pca", "ref", "pls", "umap"), default="pca")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--elite-color", choices=("constant", "mutation"), default="constant")
    parser.add_argument("--surface", action="store_true")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    np.random.seed(args.seed)
    run = load_run(args.log)
    coords, xlabel, ylabel, warning, to_start, to_final = embed(run, args.embedding, args.seed)
    flat = run["genotypes"].reshape(-1, run["genotypes"].shape[-1]).astype(np.float64)
    hamming, euclidean = sample_distances(flat, coords.reshape(-1, 2), 5000, args.seed)
    rho = spearman(hamming, euclidean)
    moves = movement(run["genotypes"], run["fitness"])
    snapshots = snapshot_indexes(run["generations"], moves["improved"], 8)
    out_dir = args.out if args.out is not None else args.log.resolve().parent / "landscape"
    out_dir.mkdir(parents=True, exist_ok=True)
    note = footer(run, rho, warning)
    write_angles(run, coords, moves, snapshots, out_dir, xlabel, ylabel, note, args.elite_color, args.surface)
    write_hamming(run, to_start, to_final, moves, out_dir, footer(run, rho, ""))
    write_frames(run, coords, out_dir, xlabel, ylabel, note)
    write_time(run, moves, out_dir)
    write_html(run, coords, moves, snapshots, out_dir, xlabel, ylabel, note, args.surface)
    length = run["genotypes"].shape[-1]
    population = run["genotypes"].shape[1]
    print(f"L={length} N={population} (1 elite + {population - 1} children) G={len(run['generations'])}")
    print(f"embedding {args.embedding}: {xlabel} | {ylabel}")
    print(f"Spearman(Hamming, embedded Euclidean)={rho:.3f} on 5000 pairs, seed {args.seed}")
    print(
        f"elite steps: {int(moves['improved'].sum())} improvements, "
        f"{int(moves['neutral'].sum())} neutral, {int(moves['worsened'].sum())} drops, "
        f"{int((~moves['changed'][1:]).sum())} unchanged"
    )
    if warning:
        print(warning)
    if args.surface:
        print("Surface is kernel-smoothed from visited points only.")
    print(f"Wrote {out_dir}")


if __name__ == "__main__":
    main()
