"""Overlay the XOR mutation runs: fixed flip counts, power-law, and half-or-double."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis"

RUNS = (
    ("xor/evolution/out/ea_4bit_g25_m1_p10_e3/recovery.json", "1 expected flip", "#1f77b4"),
    ("xor/evolution/out/ea_4bit_g25_m4_p10_e3/recovery.json", "4 expected flips", "#ff7f0e"),
    ("xor/evolution/out/ea_4bit_g25_m16_p10_e3/recovery.json", "16 expected flips", "#2ca02c"),
    ("xor/evolution/out/ea_4bit_g25_m32_p10_e3/recovery.json", "32 expected flips", "#d62728"),
    ("xor/evolution/out/ea_4bit_g25_m64_p10_e3/recovery.json", "64 expected flips", "#9467bd"),
    ("xor/evolution/out/ea_4bit_g25_m1_p10_e3_heavy/recovery.json", "Power-law", "#8c564b"),
    ("xor/evolution/out/ea_4bit_g25_m1_p10_e3_tworate/recovery.json", "Half or double", "#e377c2"),
)


def load():
    series = []
    for path, label, color in RUNS:
        history = json.loads((ROOT / path).read_text())["history"]
        series.append((
            label,
            color,
            [row["generation"] for row in history],
            [row["best_fitness"] for row in history],
            [row["mean_pairwise_hamming"] for row in history],
        ))
    return series


def draw_fitness(ax, series):
    for label, color, gens, best, _hamming in series:
        ax.plot(gens, best, marker="o", markersize=3.5, linewidth=1.6, color=color, label=label)
    ax.axhline(1.0, color="#888888", linestyle="--", linewidth=1, label="Recovery (1.0)")
    ax.set_ylim(-0.05, 1.05)
    ax.set_ylabel("Best truth-table fitness")
    ax.grid(True, alpha=0.3)


def draw_hamming(ax, series):
    for label, color, gens, _best, hamming in series:
        ax.plot(gens, hamming, marker="o", markersize=3.5, linewidth=1.6, color=color, label=label)
    ax.set_ylabel("Mean pairwise Hamming distance")
    ax.grid(True, alpha=0.3)


def save(fig, path: Path):
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main():
    series = load()
    fig, ax = plt.subplots(figsize=(8, 4.6))
    draw_fitness(ax, series)
    ax.set_xlabel("Generation")
    ax.set_title("XOR — best fitness by mutation strategy")
    ax.legend(fontsize=8, loc="center left", bbox_to_anchor=(1.02, 0.5))
    save(fig, OUT / "xor_best_fitness.png")

    fig, ax = plt.subplots(figsize=(8, 4.6))
    draw_hamming(ax, series)
    ax.set_xlabel("Generation")
    ax.set_title("XOR — population diversity by mutation strategy")
    ax.legend(fontsize=8, loc="center left", bbox_to_anchor=(1.02, 0.5))
    save(fig, OUT / "xor_diversity.png")

    fig, axes = plt.subplots(2, 1, figsize=(8, 8.2), sharex=True)
    fig.suptitle("XOR — mutation strategies", fontsize=14)
    draw_fitness(axes[0], series)
    axes[0].set_title("Best fitness")
    draw_hamming(axes[1], series)
    axes[1].set_title("Mean pairwise Hamming distance")
    axes[1].set_xlabel("Generation")
    handles, labels = axes[0].get_legend_handles_labels()
    runs = [(handle, label) for handle, label in zip(handles, labels) if label != "Recovery (1.0)"]
    fig.legend(*zip(*runs), loc="center left", bbox_to_anchor=(0.90, 0.5), fontsize=8)
    fig.tight_layout(rect=(0, 0, 0.88, 1))
    save(fig, OUT / "xor_sheet.png")


if __name__ == "__main__":
    main()
