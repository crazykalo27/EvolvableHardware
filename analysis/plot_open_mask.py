"""Sheet for the one run whose genome was the 97 bits that start as 1.

Zeros in the tile, the other tiles, and the pins stayed fixed. Generations
0–13 were not retained. The history here is generations 14–19.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "adder4" / "evolution" / "out" / "open_4bit" / "recovery.json"
OUT = ROOT / "report" / "figures" / "open_mask_sheet.png"

LINES = (
    ("Circuit", "4-bit adder, tile (17, 1). Seed 42."),
    ("Genome", "The 97 bits that already start as 1. A starting 0 stays 0. Other tiles and pins stay as placed."),
    ("Fault", "4 of those 97 cleared. Gene indexes 3, 14, 81, and 94."),
    ("Search", "Population 10, 1 elite, no crossover. Each of the 97 genes flips with probability 1/97."),
    ("Fitness", "Correct rows out of 1280. A row counts only when s0, s1, s2, s3, and cout all match."),
    ("Saved", "Generations 14–19. Stopped during generation 20, after 102 board tests. Generations 0–13 were not kept."),
)


def main() -> None:
    data = json.loads(SOURCE.read_text())
    history = data["history"]
    generations = [row["generation"] for row in history]
    best = [row["best_fitness"] for row in history]
    mean = [row["mean_fitness"] for row in history]
    distance = [row["best_distance_to_original"] for row in history]
    hamming = [row["mean_pairwise_hamming"] for row in history]
    restores = data["fault_bit_restores_in_visible_evals"]
    indexes = [str(index) for index in restores]
    counts = [restores[index] for index in indexes]

    figure = plt.figure(figsize=(16.4, 7.2), facecolor="white")
    info = figure.add_axes([0.04, 0.70, 0.92, 0.27])
    info.set_axis_off()
    info.set_xlim(0, 1)
    info.set_ylim(0, len(LINES))
    for row, (label, text) in enumerate(reversed(LINES)):
        info.text(0.0, row + 0.5, label, ha="left", va="center", fontsize=10, fontweight="bold", color="#1a1a1a")
        info.text(0.09, row + 0.5, text, ha="left", va="center", fontsize=10, color="#1a1a1a")

    fitness = figure.add_axes([0.06, 0.38, 0.90, 0.26])
    fitness.plot(generations, best, color="#009E73", marker="o", linewidth=1.8, label="Best")
    fitness.plot(generations, mean, color="#56B4E9", marker="o", linewidth=1.5, label="Mean")
    fitness.axhline(0.5, color="#9a9a9a", linestyle="--", linewidth=1)
    fitness.set_xlim(13.6, 19.4)
    fitness.set_ylim(0, 1.05)
    fitness.set_ylabel("Fitness")
    fitness.set_title("Saved generations. Best stayed at 0.50, the damaged start.", loc="left", fontsize=11, pad=4)
    fitness.grid(True, axis="y", alpha=0.3)
    fitness.legend(frameon=False, fontsize=8, loc="upper right", ncol=2)
    fitness.tick_params(labelsize=8)

    spread = figure.add_axes([0.06, 0.08, 0.55, 0.22])
    spread.plot(generations, distance, color="#009E73", marker="o", linewidth=1.8, label="Champion, bits from the original")
    spread.plot(generations, hamming, color="#E69F00", marker="o", linewidth=1.5, label="Mean pairwise Hamming")
    spread.set_xlim(13.6, 19.4)
    spread.set_ylim(0, 8)
    spread.set_xlabel("Generation")
    spread.set_ylabel("Bits")
    spread.grid(True, axis="y", alpha=0.3)
    spread.legend(frameon=False, fontsize=8, loc="upper right")
    spread.tick_params(labelsize=8)

    bars = figure.add_axes([0.70, 0.08, 0.26, 0.22])
    bars.bar(indexes, counts, color="#009E73")
    bars.set_ylim(0, 5)
    bars.set_xlabel("Fault gene")
    bars.set_ylabel("Times restored")
    bars.set_title("In the 25 saved tests", loc="left", fontsize=11, pad=4)
    bars.tick_params(labelsize=8)
    for index, count in enumerate(counts):
        bars.text(index, count + 0.15, str(count), ha="center", va="bottom", fontsize=8)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
