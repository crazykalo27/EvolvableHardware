"""Overlay figures for the final report. One fitness comparison per experiment group."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "figures"

NARROW = (
    ("xor/evolution/out/recovery_4bit/recovery.json", "XOR, 4-bit fault", "#0072B2"),
    ("xor/evolution/out/recovery_8bit/recovery.json", "XOR, 8-bit fault", "#56B4E9"),
    ("adder2/evolution/out/recovery_4bit/recovery.json", "2-bit adder, 4-bit fault", "#E69F00"),
    ("adder2/evolution/out/recovery_8bit/recovery.json", "2-bit adder, 8-bit fault", "#D55E00"),
    ("adder4/evolution/out/recovery_4bit/recovery.json", "4-bit adder, 4-bit fault", "#009E73"),
    ("adder4/evolution/out/recovery_8bit/recovery.json", "4-bit adder, 8-bit fault", "#CC79A7"),
)

OPEN = (
    ("adder2/evolution/out/direct_4bit/recovery.json", "2-bit adder, ~17 flips", "#D55E00"),
    ("adder2/evolution/out/direct_4bit_p30_g50/recovery.json", "2-bit adder, ~1 flip", "#0072B2"),
    ("adder4/evolution/out/open_4bit/recovery.json", "4-bit adder, open mask (saved gens)", "#009E73"),
)

NAMED = (
    ("adder2/evolution/out/section_4bit_p23_g100/recovery.json", "Section crossover", "#0072B2"),
    ("adder2/evolution/out/hill_4bit_g100_m4_neutral/recovery.json", "One hill climber", "#E69F00"),
    ("adder2/evolution/out/hill_4bit_g100_m4_p5_neutral/recovery.json", "Five hill climbers", "#D55E00"),
    ("adder2/evolution/out/inchworm_4bit_g500_m1_p20_e5/recovery.json", "Inchworm", "#009E73"),
)

XOR = (
    ("xor/evolution/out/ea_4bit_g25_m1_p10_e3/recovery.json", "1 expected flip", "#0072B2"),
    ("xor/evolution/out/ea_4bit_g25_m4_p10_e3/recovery.json", "4 expected flips", "#E69F00"),
    ("xor/evolution/out/ea_4bit_g25_m16_p10_e3/recovery.json", "16 expected flips", "#009E73"),
    ("xor/evolution/out/ea_4bit_g25_m32_p10_e3/recovery.json", "32 expected flips", "#D55E00"),
    ("xor/evolution/out/ea_4bit_g25_m64_p10_e3/recovery.json", "64 expected flips", "#CC79A7"),
    ("xor/evolution/out/ea_4bit_g25_m1_p10_e3_heavy/recovery.json", "Power law", "#7B4B94"),
    ("xor/evolution/out/ea_4bit_g25_m1_p10_e3_tworate/recovery.json", "Half or double", "#56B4E9"),
)

BANDIT = (
    ("adder2/evolution/out/bandit_4bit_g200_m32_p15_e3_ucb/recovery.json", "32 flips, seed 42", "#D55E00"),
    ("adder2/evolution/out/bandit_4bit_g100_m4_p15_e3_ucb_tworate/recovery.json", "Shrinking count, seed 42", "#0072B2"),
    ("adder2/evolution/out/bandit_4bit_g200_m4_p15_e1_ucb_tworate_seed7/recovery.json", "Floor of 1 flip, seed 7", "#009E73"),
)

ADDER_GAIN = (
    ("adder2/evolution/out/direct_4bit/recovery.json", "Large step", "#D55E00"),
    ("adder2/evolution/out/direct_4bit_p30_g50/recovery.json", "One flip", "#0072B2"),
    ("adder2/evolution/out/section_4bit_p23_g100/recovery.json", "Section crossover", "#56B4E9"),
    ("adder2/evolution/out/hill_4bit_g100_m4_neutral/recovery.json", "One hill climber", "#E69F00"),
    ("adder2/evolution/out/hill_4bit_g100_m4_p5_neutral/recovery.json", "Five hill climbers", "#CC79A7"),
    ("adder2/evolution/out/inchworm_4bit_g500_m1_p20_e5/recovery.json", "Inchworm", "#009E73"),
    ("adder2/evolution/out/bandit_4bit_g200_m32_p15_e3_ucb/recovery.json", "Bandit, 32 flips", "#7B4B94"),
    ("adder2/evolution/out/bandit_4bit_g100_m4_p15_e3_ucb_tworate/recovery.json", "Bandit, shrinking", "#8D6E00"),
    ("adder2/evolution/out/bandit_4bit_g200_m4_p15_e1_ucb_tworate_seed7/recovery.json", "Bandit, seed 7", "#000000"),
)


def load(path: str):
    data = json.loads((ROOT / path).read_text())
    return data, data["history"]


def summarize(path: str, label: str):
    data, rows = load(path)
    start = rows[0]
    peak = max(row["best_fitness"] for row in rows)
    first = next(row for row in rows if row["best_fitness"] >= peak - 1e-9)
    last = rows[-1]
    print(
        f"{label:42} gens {start['generation']}-{last['generation']} "
        f"start {start['best_fitness']:.3f} peak {peak:.3f} "
        f"gain {peak - start['best_fitness']:+.3f} "
        f"at gen {first['generation']} "
        f"dist {first['best_distance_to_original']}->{last['best_distance_to_original']} "
        f"ham {first['mean_pairwise_hamming']:.1f}->{last['mean_pairwise_hamming']:.1f} "
        f"evals {data.get('physical_evals', data.get('completed_physical_evals', '-'))}"
    )


def draw_lines(ax, runs, field, subtract_start=False):
    for path, label, color in runs:
        _data, rows = load(path)
        gens = [row["generation"] for row in rows]
        values = [row[field] for row in rows]
        if subtract_start:
            base = values[0]
            values = [value - base for value in values]
        ax.plot(gens, values, color=color, linewidth=1.8, marker="o", markersize=2.4, label=label)


def finish(fig, path: Path):
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {path.relative_to(ROOT)}")


def fitness_figure(runs, title, path: Path, ylabel="Best fitness"):
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    draw_lines(ax, runs, "best_fitness")
    ax.axhline(1.0, color="#9a9a9a", linestyle="--", linewidth=1)
    ax.set_ylim(-0.04, 1.06)
    ax.set_xlabel("Generation")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    finish(fig, path)


def fitness_and_gain(runs, title, path: Path):
    fig, axes = plt.subplots(2, 1, figsize=(9.2, 7.2), sharex=True)
    draw_lines(axes[0], runs, "best_fitness")
    axes[0].axhline(1.0, color="#9a9a9a", linestyle="--", linewidth=1)
    axes[0].set_ylim(-0.04, 1.06)
    axes[0].set_ylabel("Best fitness")
    axes[0].set_title(title)
    axes[0].grid(True, alpha=0.3)
    draw_lines(axes[1], runs, "best_fitness", subtract_start=True)
    axes[1].axhline(0.0, color="#9a9a9a", linestyle="--", linewidth=1)
    axes[1].set_ylabel("Gain from generation 0")
    axes[1].set_xlabel("Generation")
    axes[1].grid(True, alpha=0.3)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="center left", bbox_to_anchor=(0.90, 0.5), fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0, 0.88, 1))
    finish(fig, path)


def genotype_figure(runs, title, path: Path):
    fig, axes = plt.subplots(2, 1, figsize=(9.2, 7.2), sharex=True)
    draw_lines(axes[0], runs, "best_distance_to_original")
    axes[0].set_ylabel("Champion bits from the original")
    axes[0].set_title(title)
    axes[0].grid(True, alpha=0.3)
    draw_lines(axes[1], runs, "mean_pairwise_hamming")
    axes[1].set_ylabel("Mean pairwise Hamming")
    axes[1].set_xlabel("Generation")
    axes[1].grid(True, alpha=0.3)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="center left", bbox_to_anchor=(0.90, 0.5), fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0, 0.88, 1))
    finish(fig, path)


def gain_bars(runs, path: Path):
    labels = []
    gains = []
    colors = []
    for spec, label, color in runs:
        _data, rows = load(spec)
        peak = max(row["best_fitness"] for row in rows)
        gains.append((peak - rows[0]["best_fitness"]) * 16)
        labels.append(label)
        colors.append(color)
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    y = list(range(len(labels)))
    ax.barh(y, gains, color=colors, height=0.62)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Correct rows gained from the generation-0 best, out of 16")
    ax.set_title("Open-tile 2-bit adder: how far the score climbed")
    ax.set_xlim(0, 8)
    ax.grid(True, axis="x", alpha=0.3)
    for i, gain in enumerate(gains):
        ax.text(gain + 0.08, i, f"{gain:.0f}", va="center", fontsize=8, color="#333333")
    finish(fig, path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("narrow")
    for path, label, _color in NARROW:
        summarize(path, label)
    print("open")
    for path, label, _color in OPEN:
        summarize(path, label)
    print("named")
    for path, label, _color in NAMED:
        summarize(path, label)
    print("xor")
    for path, label, _color in XOR:
        summarize(path, label)
    print("bandit")
    for path, label, _color in BANDIT:
        summarize(path, label)

    fitness_figure(
        NARROW,
        "Narrow repair: best fitness when only the faulted bits can change",
        OUT / "narrow_fitness.png",
    )
    fitness_and_gain(
        OPEN,
        "Opening the tile: best fitness, and the climb from generation 0",
        OUT / "open_fitness.png",
    )
    genotype_figure(
        OPEN[:2],
        "Opening the tile: where the champion and the population sit",
        OUT / "open_genotype.png",
    )
    fitness_and_gain(
        NAMED,
        "Named-bit adder: best fitness, and the climb from generation 0",
        OUT / "named_fitness.png",
    )
    genotype_figure(
        NAMED,
        "Named-bit adder: champion distance and population spread",
        OUT / "named_genotype.png",
    )
    # Five of these runs never leave 0.50, so their lines sit on top of each other.
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    draw_lines(ax, XOR, "best_fitness")
    ax.axhline(1.0, color="#9a9a9a", linestyle="--", linewidth=1)
    ax.annotate(
        "1, 4, 16, and 64 flips, and the power law,\nstay on this line at 0.50",
        xy=(8, 0.50),
        xytext=(8, 0.78),
        fontsize=8,
        color="#444444",
        arrowprops={"arrowstyle": "-", "color": "#888888"},
        ha="left",
    )
    ax.set_ylim(-0.04, 1.06)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Best fitness")
    ax.set_title("XOR step size: best fitness under one shared setup")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    finish(fig, OUT / "xor_fitness.png")
    genotype_figure(
        XOR,
        "XOR step size: champion distance and population spread",
        OUT / "xor_genotype.png",
    )
    fitness_and_gain(
        BANDIT,
        "Section bandit: best fitness, and the climb from generation 0",
        OUT / "bandit_fitness.png",
    )
    # Champion and mean Hamming for these three runs are one chart,
    # written by analysis/plot_ucb_compare.py to report/figures/bandit_genotype.png.
    gain_bars(ADDER_GAIN, OUT / "adder_rows_gained.png")


if __name__ == "__main__":
    main()
