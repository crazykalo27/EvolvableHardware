"""Sheet for the four 807-bit runs on the 2-bit adder.

Same tile, same fault, same fitness. The move is what changes.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "figures" / "named_bit_sheet.png"

RUNS = (
    ("adder2/evolution/out/section_4bit_p23_g100/recovery.json", "Section crossover", "#0072B2"),
    ("adder2/evolution/out/hill_4bit_g100_m4_neutral/recovery.json", "One hill climber", "#E69F00"),
    ("adder2/evolution/out/hill_4bit_g100_m4_p5_neutral/recovery.json", "Five hill climbers", "#D55E00"),
    ("adder2/evolution/out/inchworm_4bit_g500_m1_p20_e5/recovery.json", "Inchworm", "#009E73"),
)

LINES = (
    ("Genome", "2-bit adder, tile (20, 20). 807 named bits. The 57 unnamed bits stay fixed."),
    ("Fault", "Seed 42. Genes 26, 41, 235, and 286 cleared. Fitness is correct rows out of 16."),
    ("A row", "s0, s1, and cout all match. Elites, where there are any, are copied and not scored again."),
    ("Section crossover", "Population 23, 3 elites, about 4 flips. Each of 274 sections comes from either parent half the time. 100 generations."),
    ("Hill climbers", "No crossover and no competition. About 4 flips. A tie is kept, so the genome can walk. One climber, and five."),
    ("Inchworm", "Population 20, 5 elites, about 1 flip. The 5 children of the weakest parents speed up while the best score is stuck, up to 40. Stopped during generation 176."),
)


def load(path: str):
    data = json.loads((ROOT / path).read_text())
    rows = data["history"]
    return (
        [row["generation"] for row in rows],
        [row["best_fitness"] * 16 for row in rows],
        [row["best_distance_to_original"] for row in rows],
        [row["mean_pairwise_hamming"] for row in rows],
    )


def style(ax) -> None:
    ax.grid(True, axis="y", alpha=0.3)
    ax.tick_params(labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def main() -> None:
    figure = plt.figure(figsize=(16.4, 8.4), facecolor="white")
    info = figure.add_axes([0.035, 0.72, 0.93, 0.26])
    info.set_axis_off()
    info.set_xlim(0, 1)
    info.set_ylim(0, len(LINES))
    for row, (label, text) in enumerate(reversed(LINES)):
        info.text(0.0, row + 0.5, label, ha="left", va="center", fontsize=9.5, fontweight="bold")
        info.text(0.115, row + 0.5, text, ha="left", va="center", fontsize=9.5)

    fitness = figure.add_axes([0.06, 0.40, 0.90, 0.27])
    distance = figure.add_axes([0.06, 0.08, 0.42, 0.25])
    spread = figure.add_axes([0.56, 0.08, 0.40, 0.25])

    for path, label, color in RUNS:
        generations, rows, bits, hamming = load(path)
        fitness.plot(generations, rows, color=color, linewidth=1.7, label=label)
        distance.plot(generations, bits, color=color, linewidth=1.7, label=label)
        spread.plot(generations, hamming, color=color, linewidth=1.7, label=label)

    fitness.axhline(16, color="#9a9a9a", linestyle="--", linewidth=1)
    fitness.set_xlim(0, 180)
    fitness.set_ylim(-0.4, 17)
    fitness.set_ylabel("Correct rows")
    fitness.set_title("Best score", loc="left", fontsize=11, pad=3)
    fitness.legend(frameon=False, fontsize=8, ncol=4, loc="upper right")
    style(fitness)

    distance.set_xlim(0, 180)
    distance.set_ylim(-5, 260)
    distance.set_xlabel("Generation")
    distance.set_ylabel("Bits from the original")
    distance.set_title("Champion", loc="left", fontsize=11, pad=3)
    style(distance)

    spread.set_xlim(0, 180)
    spread.set_ylim(-8, 370)
    spread.set_xlabel("Generation")
    spread.set_ylabel("Mean pairwise Hamming")
    spread.set_title("Population spread", loc="left", fontsize=11, pad=3)
    style(spread)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
