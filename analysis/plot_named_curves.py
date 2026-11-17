"""Fitness and Hamming for the four 807-bit 2-bit adder runs."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "report" / "figures"

RUNS = (
    ("adder2/evolution/out/section_4bit_p23_g100/recovery.json", "Section crossover", "#0072B2"),
    ("adder2/evolution/out/hill_4bit_g100_m4_neutral/recovery.json", "One hill climber", "#E69F00"),
    ("adder2/evolution/out/hill_4bit_g100_m4_p5_neutral/recovery.json", "Five hill climbers", "#D55E00"),
    ("adder2/evolution/out/inchworm_4bit_g500_m1_p20_e5/recovery.json", "Inchworm", "#009E73"),
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
    ax.tick_params(labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def chart(path: Path, title: str, ylabel: str, draw, legend) -> None:
    figure, axis = plt.subplots(figsize=(6.9, 4.35), facecolor="white")
    draw(axis)
    axis.set_xlim(0, 180)
    axis.set_xlabel("Generation")
    axis.set_ylabel(ylabel)
    axis.set_title(title, loc="left", fontsize=12, pad=6)
    axis.legend(frameon=False, fontsize=7.5, **legend)
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
            axis.plot(rows["generation"], rows["best_rows"], color=color, linewidth=1.7, label=f"{label}, best")
            axis.plot(rows["generation"], rows["mean_rows"], color=color, linewidth=1.3, linestyle="--", label=f"{label}, mean")
        axis.axhline(16, color="#9a9a9a", linestyle=":", linewidth=1)
        axis.set_ylim(-0.4, 17.4)

    def draw_hamming(axis) -> None:
        for label, color, rows in loaded:
            axis.plot(rows["generation"], rows["best_bits"], color=color, linewidth=1.7, label=f"{label}, best")
            axis.plot(rows["generation"], rows["pairwise"], color=color, linewidth=1.3, linestyle="--", label=f"{label}, mean pairwise")
        axis.set_ylim(-8, 390)

    chart(
        FIGURES / "named_bit_fitness.png",
        "Fitness",
        "Correct rows",
        draw_fitness,
        {"loc": "upper right", "ncol": 2},
    )
    chart(
        FIGURES / "named_bit_hamming.png",
        "Hamming distance",
        "Bits",
        draw_hamming,
        {"loc": "upper right", "ncol": 1},
    )


if __name__ == "__main__":
    main()
