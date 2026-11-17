"""Sheets for the two SAGA experiments.

The generation-300 log and the generation-444 log are one row-scored search.
The bit-scored search is a separate run and stays on its own sheet.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "report" / "figures"

ROW = ROOT / "adder2/evolution/out/saga_4bit_g500_m2_p21_e1_seed13/recovery.json"
BIT = ROOT / "adder2/evolution/out/saga_4bit_g300_m2_p21_e1_s70_seed13_adder_bit_score/recovery.json"

BEST = "#0072B2"
MEAN = "#E69F00"
DRIFT = "#009E73"
RATE = "#D55E00"
BIT_COLOR = "#D55E00"


def style(axis) -> None:
    axis.grid(True, axis="y", alpha=0.3)
    axis.tick_params(labelsize=8)
    for spine in ("top", "right"):
        axis.spines[spine].set_visible(False)


def sheet(history: list, xlim: float, scale: float, ylabel: str, title: str, out: Path, hamming_legend: str) -> None:
    gens = [row["generation"] for row in history]
    figure, axes = plt.subplots(2, 3, figsize=(13.4, 7.2), facecolor="white")

    fitness, hamming, rate = axes[0]
    elite, ties, centroid = axes[1]

    fitness.plot(gens, [row["best_fitness"] * scale for row in history], color=BEST, linewidth=1.7, label="Best")
    fitness.plot(gens, [row["mean_fitness"] * scale for row in history], color=MEAN, linewidth=1.3, linestyle="--", label="Mean")
    fitness.axhline(scale, color="#9a9a9a", linestyle=":", linewidth=1)
    fitness.set_ylim(-0.4, scale * 1.08)
    fitness.set_ylabel(ylabel)
    fitness.set_title(title, loc="left", fontsize=11, pad=4)
    fitness.legend(frameon=False, fontsize=8, loc="upper right")

    hamming.plot(gens, [row["best_distance_to_original"] for row in history], color=BEST, linewidth=1.7, label="Champion")
    hamming.plot(gens, [row["mean_pairwise_hamming"] for row in history], color=MEAN, linewidth=1.3, linestyle="--", label="Mean pairwise")
    hamming.set_ylabel("Bits")
    hamming.set_title("Hamming distance", loc="left", fontsize=11, pad=4)
    hamming.legend(frameon=False, fontsize=8, loc=hamming_legend)

    rate.plot(gens, [row["schedule_flips"] for row in history], color=RATE, linewidth=1.5)
    rate.set_ylim(-1, 40)
    rate.set_ylabel("Flips")
    rate.set_title("Rate for the weakest children", loc="left", fontsize=11, pad=4)

    elite.plot(gens, [row["elite_drift_from_start"] for row in history], color=BEST, linewidth=1.6, label="From generation 0")
    elite.plot(gens, [row["elite_drift"] for row in history], color=DRIFT, linewidth=1.3, label="From 10 generations ago")
    elite.set_ylabel("Bits")
    elite.set_title("Elite drift", loc="left", fontsize=11, pad=4)
    elite.legend(frameon=False, fontsize=8, loc="upper left")

    ties.plot(gens, [row["tie_fraction"] for row in history], color=BEST, linewidth=1.3)
    ties.set_ylim(-0.05, 1.08)
    ties.set_ylabel("Fraction")
    ties.set_title("Children tying the elite", loc="left", fontsize=11, pad=4)

    centroid.plot(gens, [row["centroid_drift_from_start"] for row in history], color=RATE, linewidth=1.5, label="From generation 0")
    centroid.plot(gens, [row["centroid_drift"] for row in history], color=DRIFT, linewidth=1.2, label="From 10 generations ago")
    centroid.set_ylabel("Distance")
    centroid.set_title("Population centroid", loc="left", fontsize=11, pad=4)
    centroid.legend(frameon=False, fontsize=8, loc="upper left")

    for axis in axes.ravel():
        axis.set_xlim(0, xlim)
        axis.set_xlabel("Generation")
        style(axis)
    figure.tight_layout()
    figure.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Wrote {out}")


def overlay(row: list, bit: list) -> None:
    figure, axes = plt.subplots(2, 3, figsize=(13.4, 7.4), facecolor="white")
    fitness, hamming, rate = axes[0]
    elite, ties, centroid = axes[1]
    series = (
        (row, BEST, "Row score"),
        (bit, BIT_COLOR, "Bit score"),
    )
    for history, color, label in series:
        gens = [item["generation"] for item in history]
        fitness.plot(gens, [item["best_fitness"] for item in history], color=color, linewidth=1.7, label=label)
        fitness.plot(gens, [item["mean_fitness"] for item in history], color=color, linewidth=1.2, linestyle="--")
        hamming.plot(gens, [item["best_distance_to_original"] for item in history], color=color, linewidth=1.7, label=f"{label}, champion")
        hamming.plot(gens, [item["mean_pairwise_hamming"] for item in history], color=color, linewidth=1.2, linestyle="--", label=f"{label}, pairwise")
        rate.plot(gens, [item["schedule_flips"] for item in history], color=color, linewidth=1.5, label=label)
        elite.plot(gens, [item["elite_drift_from_start"] for item in history], color=color, linewidth=1.6, label=f"{label}, from start")
        elite.plot(gens, [item["elite_drift"] for item in history], color=color, linewidth=1.2, linestyle="--", label=f"{label}, 10 ago")
        ties.plot(gens, [item["tie_fraction"] for item in history], color=color, linewidth=1.3, label=label)
        centroid.plot(gens, [item["centroid_drift_from_start"] for item in history], color=color, linewidth=1.5, label=f"{label}, from start")
        centroid.plot(gens, [item["centroid_drift"] for item in history], color=color, linewidth=1.2, linestyle="--", label=f"{label}, 10 ago")
    fitness.axhline(1, color="#9a9a9a", linestyle=":", linewidth=1)
    fitness.set_ylim(-0.04, 1.08)
    fitness.set_ylabel("Share of a perfect score")
    fitness.set_title("Score. Solid is best, dashed is mean", loc="left", fontsize=10, pad=4)
    hamming.set_ylabel("Bits")
    hamming.set_title("Hamming. Solid is the champion, dashed is pairwise", loc="left", fontsize=10, pad=4)
    rate.set_ylim(-1, 40)
    rate.set_ylabel("Flips")
    rate.set_title("Rate for the weakest children", loc="left", fontsize=11, pad=4)
    elite.set_ylabel("Bits")
    elite.set_title("Elite drift. Solid from the start, dashed from 10 ago", loc="left", fontsize=10, pad=4)
    ties.set_ylim(-0.05, 1.08)
    ties.set_ylabel("Fraction")
    ties.set_title("Children tying the elite", loc="left", fontsize=11, pad=4)
    centroid.set_ylabel("Distance")
    centroid.set_title("Centroid. Solid from the start, dashed from 10 ago", loc="left", fontsize=10, pad=4)
    for axis in axes.ravel():
        axis.axvline(300, color="#bbbbbb", linestyle=":", linewidth=0.8)
        axis.set_xlim(0, 500)
        axis.set_xlabel("Generation")
        style(axis)
    handles, labels = fitness.get_legend_handles_labels()
    figure.legend(handles, labels, frameon=False, fontsize=8, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 1.02))
    figure.tight_layout(rect=(0, 0, 1, 0.94))
    out = FIGURES / "saga_overlay_sheet.png"
    figure.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Wrote {out}")


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    row = json.loads(ROW.read_text())["history"]
    bit = json.loads(BIT.read_text())["history"]
    sheet(row, 500, 16, "Correct rows", "Row score, through generation 444", FIGURES / "saga_row_sheet.png", "center right")
    sheet(
        bit,
        300,
        48,
        "Correct bits",
        f"Bit score, through generation {bit[-1]['generation']}",
        FIGURES / "saga_bit_sheet.png",
        "upper right",
    )
    overlay(row, bit)


if __name__ == "__main__":
    main()
