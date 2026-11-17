"""Gain and final fitness against generations for the open-tile experiments.

The closed masks and the 97-bit adder run are left out. The generation-300
SAGA log is the start of the run that reached generation 444, so that search
is one point. Fitness is the share of a perfect score, so rows out of 16,
XOR measurements out of 20, and adder bits out of 48 sit on one axis.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "report" / "figures"

RUNS = (
    ("adder2/evolution/out/direct_4bit/recovery.json", "Large step", "#D55E00", "o"),
    ("adder2/evolution/out/direct_4bit_p30_g50/recovery.json", "One flip", "#E69F00", "o"),
    ("adder2/evolution/out/section_4bit_p23_g100/recovery.json", "Section crossover", "#0072B2", "o"),
    ("adder2/evolution/out/hill_4bit_g100_m4_neutral/recovery.json", "One hill climber", "#56B4E9", "s"),
    ("adder2/evolution/out/hill_4bit_g100_m4_p5_neutral/recovery.json", "Five hill climbers", "#CC79A7", "s"),
    ("adder2/evolution/out/inchworm_4bit_g500_m1_p20_e5/recovery.json", "Inchworm", "#009E73", "o"),
    ("adder2/evolution/out/bandit_4bit_g200_m32_p15_e3_ucb/recovery.json", "UCB 1", "#7B4B94", "o"),
    ("adder2/evolution/out/bandit_4bit_g100_m4_p15_e3_ucb_tworate/recovery.json", "UCB 2", "#882255", "o"),
    ("adder2/evolution/out/bandit_4bit_g200_m4_p15_e1_ucb_tworate_seed7/recovery.json", "UCB 3", "#44AA99", "D"),
    ("adder2/evolution/out/saga_4bit_g500_m2_p21_e1_seed13/recovery.json", "SAGA", "#332288", "o"),
    ("adder2/evolution/out/saga_4bit_g300_m2_p21_e1_s70_seed13_adder_bit_score/recovery.json", "SAGA, bit score", "#AA4499", "D"),
    ("xor/evolution/out/ea_4bit_g25_m32_p10_e3/recovery.json", "XOR, 32 flips", "#117733", "o"),
    ("xor/evolution/out/ea_4bit_g25_m1_p10_e3_tworate/recovery.json", "XOR, half or double", "#88CCEE", "o"),
)

NO_GAIN = (
    "xor/evolution/out/ea_4bit_g25_m1_p10_e3/recovery.json",
    "xor/evolution/out/ea_4bit_g25_m4_p10_e3/recovery.json",
    "xor/evolution/out/ea_4bit_g25_m16_p10_e3/recovery.json",
    "xor/evolution/out/ea_4bit_g25_m64_p10_e3/recovery.json",
    "xor/evolution/out/ea_4bit_g25_m1_p10_e3_heavy/recovery.json",
)


def load(path: str):
    history = json.loads((ROOT / path).read_text())["history"]
    start = history[0]["best_fitness"]
    final = history[-1]["best_fitness"]
    arrived = next(row["generation"] for row in history if row["best_fitness"] >= final - 1e-12)
    return history[-1]["generation"], arrived, start, final


def axis_x(generation: float) -> float:
    """Stretch 0–40. Compress the sparse stretch after it, and the long tail most of all."""
    if generation <= 40:
        return generation
    if generation <= 120:
        return 40 + (generation - 40) * 0.18
    if generation <= 200:
        return 54.4 + (generation - 120) * 0.08
    return 60.8 + (generation - 200) * 0.045


def along(x0: float, y0: float, x1: float, y1: float):
    """Follow the compressed axis instead of cutting straight across a squeezed region."""
    knots = [x0]
    for knot in (40, 120, 200):
        if min(x0, x1) < knot < max(x0, x1):
            knots.append(knot)
    knots.append(x1)
    if x1 < x0:
        knots.reverse()
    span = x1 - x0
    xs = [axis_x(generation) for generation in knots]
    ys = [y0 if span == 0 else y0 + (y1 - y0) * (generation - x0) / span for generation in knots]
    return xs, ys


def style(axis) -> None:
    axis.grid(True, axis="y", alpha=0.3)
    axis.tick_params(labelsize=8)
    for spine in ("top", "right"):
        axis.spines[spine].set_visible(False)


def main() -> None:
    points = []
    for path, label, color, marker in RUNS:
        generation, arrived, start, final = load(path)
        points.append((label, color, marker, generation, arrived, start, final))
        print(f"{label:22} gen {generation:4} best at {arrived:4} stall {generation - arrived:4} start {start:.3f} final {final:.3f}")
    generation, arrived, start, final = load(NO_GAIN[0])
    points.append(("XOR, no gain", "#999999", "o", generation, arrived, start, final))
    print(f"{'XOR, no gain':22} gen {generation:4} best at {arrived:4} stall {generation - arrived:4} start {start:.3f} final {final:.3f}  (1, 4, 16, 64, power law)")

    lanes: dict[float, list[int]] = {}
    for index, point in enumerate(points):
        lanes.setdefault(round(point[6], 6), []).append(index)
    bar_at = [point[6] for point in points]
    for group in lanes.values():
        if len(group) == 1:
            continue
        middle = (len(group) - 1) / 2
        for slot, index in enumerate(group):
            bar_at[index] = points[index][6] + (slot - middle) * 0.02

    figure, axes = plt.subplots(
        1, 2, figsize=(13.6, 5.5), facecolor="white", gridspec_kw={"width_ratios": [1, 2.7]}
    )
    gained, finished = axes
    for index, (label, color, marker, generation, arrived, start, final) in enumerate(points):
        gained.scatter(generation, final - start, s=42, color=color, marker=marker, zorder=3, label=label)
        finished.plot(*along(0, start, arrived, final), color=color, linewidth=1.4, zorder=2)
        if generation > arrived:
            stall = bar_at[index]
            if stall != final:
                finished.plot([axis_x(arrived), axis_x(arrived)], [final, stall], color=color, linewidth=1.0, zorder=2)
            finished.plot(
                [axis_x(arrived), axis_x(generation)],
                [stall, stall],
                color=color,
                linewidth=1.3,
                alpha=0.55,
                solid_capstyle="butt",
                zorder=1,
            )
        finished.scatter(axis_x(arrived), final, s=42, color=color, marker=marker, zorder=3)
    gained.set_xlabel("Generations used")
    gained.set_ylabel("Fitness gained")
    gained.set_title("Gain from the generation-0 best", loc="left", fontsize=11, pad=4)
    finished.set_xlabel("Generations")
    finished.set_ylabel("Final fitness")
    finished.set_title("Slope to the best score, then the stall. 0–40 is stretched", loc="left", fontsize=11, pad=4)
    gained.set_xlim(-12, 480)
    gained.set_xticks([0, 150, 300, 450])
    finished.set_xlim(axis_x(-4), axis_x(470))
    tick_generations = (0, 10, 20, 30, 40, 80, 120, 200, 450)
    finished.set_xticks([axis_x(generation) for generation in tick_generations])
    finished.set_xticklabels([str(generation) for generation in tick_generations])
    for axis in axes:
        style(axis)
    gained.set_ylim(-0.03, 0.58)
    finished.set_ylim(-0.03, 1.05)
    handles, labels = gained.get_legend_handles_labels()
    figure.legend(handles, labels, frameon=False, fontsize=8, loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.02))
    figure.tight_layout(rect=(0, 0.10, 1, 1))
    path = FIGURES / "fitness_gain.png"
    FIGURES.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
