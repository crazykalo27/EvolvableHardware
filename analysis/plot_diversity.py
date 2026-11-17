"""Quantitative diversity plots from the finished recovery logs.

Pairwise Hamming is the mean number of bits that differ between two genomes
in the population. Champion distance is the best genome versus the original.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis"

XOR = (
    (1, "1 flip", "#1f77b4"),
    (4, "4 flips", "#ff7f0e"),
    (16, "16 flips", "#2ca02c"),
    (32, "32 flips", "#d62728"),
    (64, "64 flips", "#9467bd"),
)


def history(path: str):
    return json.loads((ROOT / path).read_text())["history"]


def late_hamming(rows) -> float:
    return statistics.mean(row["mean_pairwise_hamming"] for row in rows[-5:])


def stuck_window(rows):
    """Generation where the final best fitness first appears, through the end."""
    final = max(row["best_fitness"] for row in rows)
    start = next(row for row in rows if row["best_fitness"] >= final - 1e-9)
    end = rows[-1]
    return start, end


def save(fig, name: str):
    fig.savefig(OUT / name, dpi=160, bbox_inches="tight")
    plt.close(fig)


def xor_rate_response():
    points = []
    for flips, label, color in XOR:
        rows = history(f"xor/evolution/out/ea_4bit_g25_m{flips}_p10_e3/recovery.json")
        points.append((flips, late_hamming(rows), label, color))
    fit = [item for item in points if item[0] <= 32]
    xs = [item[0] for item in fit]
    ys = [item[1] for item in fit]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sum((x - mean_x) ** 2 for x in xs)
    intercept = mean_y - slope * mean_x

    heavy = history("xor/evolution/out/ea_4bit_g25_m1_p10_e3_heavy/recovery.json")
    drawn = [k for row in heavy if row.get("mutation_strengths") for k in row["mutation_strengths"]]
    heavy_k = statistics.mean(drawn)
    heavy_y = late_hamming(heavy)

    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    line_x = [0, 64]
    ax.plot(line_x, [intercept + slope * x for x in line_x], color="#bbbbbb", linewidth=1.2, label=f"Fit to 1–32 flips: {slope:.1f} bits per flip")
    for flips, y, label, color in points:
        ax.scatter([flips], [y], color=color, s=46, zorder=3)
        ax.annotate(f"{y:.0f}", (flips, y), textcoords="offset points", xytext=(6, 6), fontsize=8, color=color)
    ax.scatter([heavy_k], [heavy_y], color="#8c564b", marker="D", s=42, zorder=3, label="Power-law, at its mean draw")
    ax.annotate(f"{heavy_y:.0f}", (heavy_k, heavy_y), textcoords="offset points", xytext=(6, -12), fontsize=8, color="#8c564b")
    ax.set_xlim(-1, 70)
    ax.set_ylim(0, 340)
    ax.set_xlabel("Expected flips per child")
    ax.set_ylabel("Mean pairwise Hamming, last 5 generations")
    ax.set_title("XOR: late diversity versus a constant mutation rate")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    save(fig, "xor_diversity_vs_rate.png")
    print(f"slope {slope:.3f} intercept {intercept:.2f} heavy k {heavy_k:.2f} heavy y {heavy_y:.2f}")
    for flips, y, _label, _color in points:
        print(f"  {flips} -> {y:.2f}  line {intercept + slope * flips:.1f}")


def xor_progress():
    series = []
    for flips, label, color in XOR:
        rows = history(f"xor/evolution/out/ea_4bit_g25_m{flips}_p10_e3/recovery.json")
        series.append((label, color, late_hamming(rows), rows[-1]["best_fitness"]))
    for path, label, color in (
        ("xor/evolution/out/ea_4bit_g25_m1_p10_e3_heavy/recovery.json", "Power-law", "#8c564b"),
        ("xor/evolution/out/ea_4bit_g25_m1_p10_e3_tworate/recovery.json", "Half or double", "#e377c2"),
    ):
        rows = history(path)
        series.append((label, color, late_hamming(rows), rows[-1]["best_fitness"]))

    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    ax.axhline(1.0, color="#888888", linestyle="--", linewidth=1, label="Recovery (1.0)")
    for label, color, x, y in series:
        ax.scatter([x], [y], color=color, s=46, zorder=3, label=label)
    ax.set_xlim(-10, 420)
    ax.set_ylim(0.42, 1.05)
    ax.set_xlabel("Mean pairwise Hamming, last 5 generations")
    ax.set_ylabel("Final best fitness")
    ax.set_title("XOR: the most diverse runs were not the highest scoring")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="center left", bbox_to_anchor=(1.02, 0.5))
    save(fig, "xor_diversity_vs_fitness.png")
    for label, _color, x, y in series:
        print(f"  {label}: ham {x:.1f} fitness {y:.3f}")


def while_stuck():
    runs = [
        ("XOR, 1 flip", "xor/evolution/out/ea_4bit_g25_m1_p10_e3/recovery.json"),
        ("XOR, 4 flips", "xor/evolution/out/ea_4bit_g25_m4_p10_e3/recovery.json"),
        ("XOR, 16 flips", "xor/evolution/out/ea_4bit_g25_m16_p10_e3/recovery.json"),
        ("XOR, 32 flips", "xor/evolution/out/ea_4bit_g25_m32_p10_e3/recovery.json"),
        ("XOR, 64 flips", "xor/evolution/out/ea_4bit_g25_m64_p10_e3/recovery.json"),
        ("XOR, power-law", "xor/evolution/out/ea_4bit_g25_m1_p10_e3_heavy/recovery.json"),
        ("XOR, half or double", "xor/evolution/out/ea_4bit_g25_m1_p10_e3_tworate/recovery.json"),
        ("Adder, section crossover", "adder2/evolution/out/section_4bit_p23_g100/recovery.json"),
        ("Adder, inchworm", "adder2/evolution/out/inchworm_4bit_g500_m1_p20_e5/recovery.json"),
        ("Adder, UCB", "adder2/evolution/out/bandit_4bit_g200_m32_p15_e3_ucb/recovery.json"),
        ("Adder, no crossover, ~17 flips", "adder2/evolution/out/direct_4bit/recovery.json"),
        ("Adder, no crossover, 1 flip", "adder2/evolution/out/direct_4bit_p30_g50/recovery.json"),
        ("Adder, hill, 5 genomes", "adder2/evolution/out/hill_4bit_g100_m4_p5_neutral/recovery.json"),
        ("Adder, hill, 1 genome", "adder2/evolution/out/hill_4bit_g100_m4_neutral/recovery.json"),
    ]
    labels = []
    ham = []
    dist = []
    for label, path in runs:
        start, end = stuck_window(history(path))
        labels.append(label)
        ham.append(end["mean_pairwise_hamming"] - start["mean_pairwise_hamming"])
        dist.append(end["best_distance_to_original"] - start["best_distance_to_original"])
        print(f"  {label}: ham {ham[-1]:+.1f} dist {dist[-1]:+.0f} from gen {start['generation']}")

    fig, ax = plt.subplots(figsize=(8.4, 6.4))
    y = list(range(len(labels)))
    ax.barh([i + 0.16 for i in y], ham, height=0.32, color="#6b5b95", label="Population Hamming")
    ax.barh([i - 0.16 for i in y], dist, height=0.32, color="#c45c12", label="Champion vs original")
    ax.axvline(0, color="#444444", linewidth=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Change in bits while the best fitness stayed at its final value")
    ax.set_title("What kept moving after the best score stopped rising")
    ax.grid(True, axis="x", alpha=0.3)
    ax.legend(fontsize=8, loc="center left", bbox_to_anchor=(1.02, 0.5))
    ax.invert_yaxis()
    save(fig, "diversity_while_best_stuck.png")


def bandit_coverage():
    rows = history("adder2/evolution/out/bandit_4bit_g200_m32_p15_e3_ucb/recovery.json")
    seen = set()
    gens = []
    covered = []
    hamm = []
    for row in rows:
        for child in row.get("offspring") or []:
            seen.update(child.get("sections_flipped") or [])
        gens.append(row["generation"])
        covered.append(len(seen))
        hamm.append(row["mean_pairwise_hamming"])

    fig, axes = plt.subplots(2, 1, figsize=(8, 6.2), sharex=True)
    axes[0].plot(gens, covered, color="#3a6ea5", marker="o", markersize=2.5)
    axes[0].axhline(274, color="#888888", linestyle="--", linewidth=1)
    axes[0].text(102, 286, "all 274 sections", ha="right", va="bottom", fontsize=8, color="#666666")
    axes[0].set_ylabel("Sections flipped at least once")
    axes[0].set_ylim(0, 300)
    axes[0].set_title("Adder UCB: new sections, then genetic diversity")
    axes[0].grid(True, alpha=0.3)
    axes[1].plot(gens, hamm, color="#6b5b95", marker="o", markersize=2.5)
    axes[1].set_ylabel("Mean pairwise Hamming")
    axes[1].set_xlabel("Generation")
    axes[1].grid(True, alpha=0.3)
    save(fig, "bandit_section_coverage.png")
    print(f"  covered by gen 3: {covered[3]} hamming then {hamm[3]:.1f} end {hamm[-1]:.1f}")


def main():
    xor_rate_response()
    xor_progress()
    while_stuck()
    bandit_coverage()


if __name__ == "__main__":
    main()
