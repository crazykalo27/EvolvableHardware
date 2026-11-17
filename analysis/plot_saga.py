"""Plots for a SAGA run, including one stopped before the last generation.

The history rows already hold the population, the elite drift, the centroid
drift, the cluster width, and the fraction of children that tied the elite.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> tuple[dict, list]:
    saved = json.loads(path.read_text())
    return saved, saved["history"]


def write(history, out_dir: Path, title: str) -> None:
    gens = [row["generation"] for row in history]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot(gens, [row["best_fitness"] for row in history], color="#2a7a4b", marker="o", markersize=2.5, label="Best fitness")
    ax.plot(gens, [row["mean_fitness"] for row in history], color="#3a6ea5", marker="o", markersize=2.5, label="Mean fitness")
    ax.axhline(1.0, color="#888888", linestyle="--", linewidth=1, label="Perfect score")
    ax.set_ylim(-0.05, 1.05)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Truth-table fitness")
    ax.set_title(title)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "fitness_over_generations.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot(gens, [row["mean_pairwise_hamming"] for row in history], color="#6b5b95", marker="o", markersize=2.5, label="Cluster width")
    ax.plot(gens, [row["best_distance_to_original"] for row in history], color="#c45c12", marker="o", markersize=2.5, label="Elite vs original")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Hamming distance")
    ax.set_title(title)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "hamming_diversity.png", dpi=160)
    plt.close(fig)

    evals = [row["physical_evals"] for row in history]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot(evals, [row["best_fitness"] for row in history], color="#2a7a4b", marker="o", markersize=2.5, label="Best fitness")
    ax.axhline(1.0, color="#888888", linestyle="--", linewidth=1, label="Perfect score")
    ax.set_ylim(-0.05, 1.05)
    ax.set_xlabel("Physical board evaluations")
    ax.set_ylabel("Truth-table fitness")
    ax.set_title(title)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "fitness_vs_evals.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(5, 1, figsize=(8.2, 13.4), sharex=True)
    fig.suptitle(title, fontsize=14)
    axes[0].plot(gens, [row["best_fitness"] for row in history], color="#2a7a4b", label="Best")
    axes[0].plot(gens, [row["mean_fitness"] for row in history], color="#3a6ea5", label="Mean")
    axes[0].axhline(1.0, color="#888888", linestyle="--", linewidth=1)
    axes[0].set_ylim(-0.05, 1.05)
    axes[0].set_ylabel("Fitness")
    axes[0].set_title("Score")
    axes[0].legend(fontsize=8)
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(gens, [row["mean_pairwise_hamming"] for row in history], color="#6b5b95", label="Cluster width")
    axes[1].plot(gens, [row["elite_drift_from_start"] for row in history], color="#c45c12", label="Elite vs generation 0")
    axes[1].plot(gens, [row["elite_drift"] for row in history], color="#1a1a1a", label="Elite vs 10 generations ago")
    axes[1].plot(gens, [row["consensus_drift_from_start"] for row in history], color="#2a7a4b", label="Majority vs generation 0")
    axes[1].set_ylabel("Hamming bits")
    axes[1].set_title("How far the species has moved")
    axes[1].legend(fontsize=8)
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(gens, [row["centroid_drift_from_start"] for row in history], color="#3a6ea5", label="Centroid vs generation 0")
    axes[2].plot(gens, [row["centroid_drift"] for row in history], color="#c45c12", label="Centroid vs 10 generations ago")
    axes[2].set_ylabel("Euclidean")
    axes[2].set_title("Population centroid")
    axes[2].legend(fontsize=8)
    axes[2].grid(True, alpha=0.3)

    axes[3].plot(gens, [row["tie_fraction"] for row in history], color="#6b5b95", label="Children tying the elite")
    axes[3].set_ylim(-0.05, 1.05)
    axes[3].set_ylabel("Fraction")
    axes[3].set_title("Neutral ties")
    axes[3].legend(fontsize=8)
    axes[3].grid(True, alpha=0.3)

    axes[4].plot(gens, [row["schedule_flips"] for row in history], color="#1a1a1a", label="Rate for the next children")
    axes[4].set_ylabel("Expected flips")
    axes[4].set_xlabel("Generation")
    axes[4].set_title("Stalled mutation level")
    axes[4].legend(fontsize=8)
    axes[4].grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "species_traversal.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def main(path: Path) -> None:
    saved, history = load(path)
    if not history:
        raise SystemExit(f"No generations saved in {path}")
    last = history[-1]["generation"]
    title = f"2-bit adder SAGA, through generation {last}"
    write(history, path.parent, title)
    print(f"Wrote plots in {path.parent}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        ROOT / "adder2/evolution/out/saga_4bit_g300_m2_p21_e1_seed13/recovery.json"
    )
    main(target)
