"""Fitness and Hamming for the two fully open 2-bit adder runs."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "report" / "figures"

RUNS = (
    ("adder2/evolution/out/direct_4bit/recovery.json", "Large step", "#D55E00"),
    ("adder2/evolution/out/direct_4bit_p30_g50/recovery.json", "Small step", "#0072B2"),
)


def load(path: str):
    rows = json.loads((ROOT / path).read_text())["history"]
    return {
        "generation": [row["generation"] for row in rows],
        "best_rows": [row["best_fitness"] * 16 for row in rows],
        "mean_rows": [row["mean_fitness"] * 16 for row in rows],
        "best_bits": [row["best_distance_to_original"] for row in rows],
        "pairwise": [row["mean_pairwise_hamming"] for row in rows],
    }


def style(ax) -> None:
    ax.grid(True, axis="y", alpha=0.3)
    ax.tick_params(labelsize=9)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def chart(path: Path, title: str, ylabel: str, draw) -> None:
    figure, axis = plt.subplots(figsize=(6.4, 4.8), facecolor="white")
    draw(axis)
    axis.set_xlim(0, 50)
    axis.set_xlabel("Generation")
    axis.set_ylabel(ylabel)
    axis.set_title(title, loc="left", fontsize=12, pad=8)
    axis.legend(frameon=False, fontsize=8, loc="upper right")
    style(axis)
    figure.tight_layout()
    figure.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Wrote {path}")


def main() -> None:
    loaded = [(label, color, load(path)) for path, label, color in RUNS]
    FIGURES.mkdir(parents=True, exist_ok=True)

    def draw_fitness(axis) -> None:
        for label, color, rows in loaded:
            axis.plot(rows["generation"], rows["best_rows"], color=color, linewidth=1.8, label=f"{label}, best")
            axis.plot(rows["generation"], rows["mean_rows"], color=color, linewidth=1.4, linestyle="--", label=f"{label}, mean")
        axis.axhline(16, color="#9a9a9a", linestyle=":", linewidth=1)
        axis.set_ylim(-0.4, 17.4)

    def draw_hamming(axis) -> None:
        for label, color, rows in loaded:
            axis.plot(rows["generation"], rows["best_bits"], color=color, linewidth=1.8, label=f"{label}, best")
            axis.plot(rows["generation"], rows["pairwise"], color=color, linewidth=1.4, linestyle="--", label=f"{label}, mean pairwise")
        axis.set_ylim(-4, 150)

    chart(FIGURES / "full_open_fitness.png", "Fitness", "Correct rows", draw_fitness)
    chart(FIGURES / "full_open_hamming.png", "Hamming distance", "Bits", draw_hamming)


if __name__ == "__main__":
    main()
