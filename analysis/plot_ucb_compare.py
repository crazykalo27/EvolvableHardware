"""The three UCB runs: fitness, rise or fall, and the sections they returned to."""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.plot_bandit import brief, replay
from analysis.tile_genome import genome_layout

FIGURES = ROOT / "report" / "figures"

RUNS = (
    ("UCB 1", "adder2/evolution/out/bandit_4bit_g200_m32_p15_e3_ucb/recovery.json", "#D55E00"),
    ("UCB 2", "adder2/evolution/out/bandit_4bit_g100_m4_p15_e3_ucb_tworate/recovery.json", "#0072B2"),
    ("UCB 3", "adder2/evolution/out/bandit_4bit_g200_m4_p15_e1_ucb_tworate_seed7/recovery.json", "#009E73"),
)
TOP = 4
UP = "#2a7a4b"
DOWN = "#b03a4a"
SAME = "#d0d0d0"


def load(path: str):
    saved = json.loads((ROOT / path).read_text())
    history = saved["history"]
    per_gen, flipped, _selected, _genes = replay(history)
    return history, per_gen, flipped


def style(ax) -> None:
    ax.grid(True, axis="y", alpha=0.3)
    ax.tick_params(labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def pretty(name: str) -> str:
    pin = re.fullmatch(r"buffer (local_g\d+_\d+) lutff_(\d+)/in_(\d+)", name)
    if pin:
        track = pin.group(1).replace("local_", "")
        return f"local {track} → LC{pin.group(2)} input {pin.group(3)}"
    route = re.fullmatch(r"routing sp4_[a-z_]+_(\d+) sp4_([a-z_]+)_(\d+)", name)
    if route:
        side = {"v_b": "bottom", "v_t": "top", "h_l": "left", "h_r": "right"}.get(route.group(2), route.group(2))
        return f"span4 {route.group(1)} → {side} span4 {route.group(3)}"
    text = brief(name)
    if text.startswith("glb2local_"):
        return text.replace("glb2local_", "clock ")
    return text


def section_labels(names: list[str]) -> dict[str, str]:
    return {name: pretty(name) for name in names}


def favorites(counts) -> list[str]:
    chosen = []
    seen = set()
    for _label, _path, _color in RUNS:
        for name, _n in counts[_label].most_common(TOP):
            if name not in seen:
                chosen.append(name)
                seen.add(name)
    return chosen


def distance(loaded) -> None:
    figure, axis = plt.subplots(figsize=(8.2, 5.0), facecolor="white")
    for label, _path, color in RUNS:
        history, _per, _flipped = loaded[label]
        gens = [row["generation"] for row in history]
        axis.plot(gens, [row["best_distance_to_original"] for row in history], color=color, linewidth=1.7, label=f"{label}, champion")
        axis.plot(gens, [row["mean_pairwise_hamming"] for row in history], color=color, linewidth=1.3, linestyle="--", label=f"{label}, mean")
    axis.set_xlim(0, 140)
    axis.set_ylim(-4, 175)
    axis.set_xlabel("Generation")
    axis.set_ylabel("Bits")
    axis.set_title("Hamming distance", loc="left", fontsize=12, pad=6)
    axis.legend(frameon=False, fontsize=8, ncol=2, loc="upper right")
    style(axis)
    figure.tight_layout()
    path = FIGURES / "bandit_genotype.png"
    figure.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Wrote {path}")


def fitness(loaded) -> None:
    figure, axis = plt.subplots(figsize=(7.2, 4.6), facecolor="white")
    for label, _path, color in RUNS:
        history, _per, _flipped = loaded[label]
        gens = [row["generation"] for row in history]
        axis.plot(gens, [row["best_fitness"] * 16 for row in history], color=color, linewidth=1.7, label=f"{label}, best")
        axis.plot(gens, [row["mean_fitness"] * 16 for row in history], color=color, linewidth=1.3, linestyle="--", label=f"{label}, mean")
    axis.axhline(16, color="#9a9a9a", linestyle=":", linewidth=1)
    axis.set_xlim(0, 140)
    axis.set_ylim(-0.4, 17.2)
    axis.set_xlabel("Generation")
    axis.set_ylabel("Correct rows")
    axis.set_title("Fitness", loc="left", fontsize=12, pad=6)
    axis.legend(frameon=False, fontsize=8, ncol=2, loc="upper right")
    style(axis)
    figure.tight_layout()
    path = FIGURES / "ucb_fitness.png"
    figure.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Wrote {path}")


def fit_line(xs, ys):
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    spread = sum((x - x_mean) ** 2 for x in xs)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / spread
    intercept = y_mean - slope * x_mean
    return [slope * x + intercept for x in xs]


def rise_fall(loaded) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(13.2, 4.5), facecolor="white", sharey=True)
    mean_line = None
    fit = None
    for axis, (label, _path, _color) in zip(axes, RUNS):
        _history, per_gen, _flipped = loaded[label]
        scored = [item for item in per_gen if item["improved"] or item["worsened"] or item["unchanged"]]
        gens = [item["generation"] for item in scored]
        improved = [item["improved"] for item in scored]
        worsened = [item["worsened"] for item in scored]
        unchanged = [item["unchanged"] for item in scored]
        base = [up + down for up, down in zip(improved, worsened)]
        axis.bar(gens, improved, width=1.0, color=UP, label="Rose")
        axis.bar(gens, worsened, width=1.0, bottom=improved, color=DOWN, label="Fell")
        axis.bar(gens, unchanged, width=1.0, bottom=base, color=SAME, label="Unchanged")
        means = [item["mean_delta"] for item in scored]
        right = axis.twinx()
        mean_line, = right.plot(gens, means, color="#1a1a1a", linewidth=1.0, label="Mean change")
        fit, = right.plot(gens, fit_line(gens, means), color="#1a1a1a", linewidth=1.5, linestyle="--", label="Straight fit")
        right.axhline(0, color="#1a1a1a", linewidth=0.6, alpha=0.4)
        right.set_ylim(-0.28, 0.28)
        right.tick_params(labelsize=7)
        right.set_ylabel("Mean change", fontsize=8)
        axis.set_xlim(gens[0] - 1, gens[-1] + 1)
        axis.set_xlabel("Generation")
        axis.set_title(label, loc="left", fontsize=11, pad=4)
        style(axis)
    axes[0].set_ylabel("Children")
    axes[0].set_ylim(0, 16)
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles + [mean_line, fit],
        labels + ["Mean change", "Straight fit"],
        frameon=False,
        fontsize=8,
        loc="upper center",
        ncol=5,
        bbox_to_anchor=(0.5, 1.02),
    )
    figure.tight_layout(rect=(0, 0, 1, 0.92))
    path = FIGURES / "ucb_rise_fall.png"
    figure.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Wrote {path}")


def sections(loaded) -> None:
    counts = {label: flipped for label, (_history, _per, flipped) in loaded.items()}
    names = favorites(counts)
    labels = section_labels(names)
    names.sort(key=lambda name: counts["UCB 1"][name], reverse=True)
    figure, axis = plt.subplots(figsize=(10.2, 6.6), facecolor="white")
    positions = list(range(len(names)))
    height = 0.24
    for offset, (label, _path, color) in zip((-height, 0.0, height), RUNS):
        visits = [counts[label][name] for name in names]
        axis.barh([position + offset for position in positions], visits, height=height, color=color, label=label)
    axis.set_yticks(positions)
    axis.set_yticklabels([labels[name] for name in names], fontsize=8)
    axis.invert_yaxis()
    peak = max(counts[label][name] for label, _path, _color in RUNS for name in names)
    axis.set_xlim(0, peak * 1.05)
    axis.set_xlabel("Times flipped")
    axis.set_title("Sections revisited most often", loc="left", fontsize=12, pad=6)
    axis.legend(frameon=False, fontsize=8, loc="lower right")
    style(axis)
    axis.grid(True, axis="x", alpha=0.3)
    axis.grid(False, axis="y")
    path = FIGURES / "ucb_sections.png"
    figure.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Wrote {path}")


def reason(pulls, reward_sum, updates, name: str) -> str:
    """Gold when the average is larger than the bonus. Blue otherwise."""
    seen = pulls.get(name, 0)
    if seen == 0 or updates == 0:
        return "explore"
    average = reward_sum[name] / seen
    bonus = math.sqrt(math.log(updates) / seen)
    return "reward" if average > bonus else "explore"


def choice(loaded) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(15.6, 4.7), facecolor="white")
    for axis, (label, _path, _color) in zip(axes, RUNS):
        history, _per, _flipped = loaded[label]
        pulls: dict[str, int] = {}
        reward_sum: dict[str, float] = {}
        updates = 0
        gens = []
        explore = []
        reward = []
        for row in history:
            kids = row.get("offspring") or []
            if not kids:
                continue
            counts = {"explore": 0, "reward": 0}
            for child in kids:
                names = child.get("sections_flipped") or []
                payoff = child.get("reward")
                if not names or payoff is None:
                    continue
                for name in names:
                    counts[reason(pulls, reward_sum, updates, name)] += 1
                for name in names:
                    pulls[name] = pulls.get(name, 0) + 1
                    reward_sum[name] = reward_sum.get(name, 0.0) + payoff
                    updates += 1
            gens.append(row["generation"])
            explore.append(counts["explore"])
            reward.append(counts["reward"])
        axis.bar(gens, explore, width=1.0, color="#0072B2", label="Exploration")
        axis.bar(gens, reward, width=1.0, bottom=explore, color="#E69F00", label="Fitness reward")
        fit_gens = [row["generation"] for row in history]
        right = axis.twinx()
        best_line, = right.plot(fit_gens, [row["best_fitness"] * 16 for row in history], color="#1a1a1a", linewidth=1.6, label="Best")
        mean_line, = right.plot(fit_gens, [row["mean_fitness"] * 16 for row in history], color="#1a1a1a", linewidth=1.2, linestyle="--", label="Mean")
        right.axhline(16, color="#9a9a9a", linestyle=":", linewidth=1)
        right.set_ylim(-0.4, 17.2)
        right.tick_params(labelsize=7)
        right.set_ylabel("Correct rows", fontsize=8)
        indexed = {row["generation"]: row for row in history}
        rates = []
        for generation in gens:
            previous = indexed.get(generation - 1, {})
            if "mutation_strength" in previous:
                rates.append(previous["mutation_strength"])
            else:
                rates.append(32)
        flips = axis.twinx()
        flip_line, = flips.plot(gens, rates, color="#882255", linewidth=1.6, label="Flip count")
        flips.set_ylim(-1, 48)
        flips.spines["right"].set_visible(False)
        flips.tick_params(axis="y", labelright=False)
        axis.set_xlim(gens[0] - 1, gens[-1] + 1)
        axis.set_ylim(0, max(e + r for e, r in zip(explore, reward)) * 1.08)
        axis.set_xlabel("Generation")
        axis.set_title(label, loc="left", fontsize=11, pad=4)
        style(axis)
        print(label, "explore", sum(explore), "reward", sum(reward))
    scale = axes[2].twinx()
    scale.set_ylim(-1, 48)
    scale.spines["right"].set_position(("outward", 40))
    scale.spines["right"].set_color("#882255")
    scale.tick_params(labelsize=7, colors="#882255")
    scale.set_ylabel("Flips", fontsize=8, color="#882255")
    axes[0].set_ylabel("Sections flipped")
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles + [best_line, mean_line, flip_line],
        labels + ["Best", "Mean", "Flip count"],
        frameon=False,
        fontsize=8,
        loc="upper center",
        ncol=5,
        bbox_to_anchor=(0.5, 1.02),
    )
    figure.tight_layout(rect=(0, 0, 1, 0.90))
    figure.subplots_adjust(wspace=0.42)
    path = FIGURES / "ucb_choice.png"
    figure.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Wrote {path}")


def section_state(pulls, reward_sum, updates):
    rows = []
    for name, seen in pulls.items():
        if seen == 0 or updates == 0:
            continue
        average = reward_sum.get(name, 0.0) / seen
        bonus = math.sqrt(math.log(updates) / seen)
        rows.append((average + bonus, average, bonus))
    rows.sort(reverse=True)
    return rows


def scores(loaded) -> None:
    total_sections = len(genome_layout()[1])
    figure, axes = plt.subplots(3, 3, figsize=(13.2, 9.2), facecolor="white", sharey="col")
    titles = ("Beginning", "Halfway", "End")
    for column, (label, _path, _color) in enumerate(RUNS):
        history, _per, _flipped = loaded[label]
        pulls: dict[str, int] = {}
        reward_sum: dict[str, float] = {}
        updates = 0
        saved = {}
        for generation in history:
            for child in generation.get("offspring") or []:
                names = child.get("sections_flipped") or []
                payoff = child.get("reward")
                if not names or payoff is None:
                    continue
                for name in names:
                    pulls[name] = pulls.get(name, 0) + 1
                    reward_sum[name] = reward_sum.get(name, 0.0) + payoff
                    updates += 1
            if updates:
                saved[generation["generation"]] = (updates, section_state(pulls, reward_sum, updates), len(pulls))
        marks = sorted(saved)
        targets = [marks[0], marks[len(marks) // 2], marks[-1]]
        for row_index, (generation, title) in enumerate(zip(targets, titles)):
            axis = axes[row_index][column]
            _updates, rows, visited = saved[generation]
            averages = [item[1] for item in rows]
            bonuses = [item[2] for item in rows]
            positions = list(range(len(rows)))
            axis.bar(positions, bonuses, width=1.0, bottom=averages, color="#0072B2", label="Exploration")
            axis.bar(positions, averages, width=1.0, color="#E69F00", label="Fitness reward")
            axis.axhline(0, color="#1a1a1a", linewidth=0.6)
            axis.set_xlim(-0.5, max(len(rows) - 0.5, 1))
            waiting = total_sections - visited
            heading = f"{label}, {title.lower()}, generation {generation}"
            if waiting:
                heading += f", {waiting} not yet visited"
            axis.set_title(heading, loc="left", fontsize=8, pad=3)
            style(axis)
            axis.tick_params(axis="x", labelbottom=False)
            if column == 0:
                axis.set_ylabel("Score")
        axes[2][column].set_xlabel("Sections, highest score on the left")
    handles, labels = axes[0][0].get_legend_handles_labels()
    figure.legend(handles, labels, frameon=False, fontsize=8, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.01))
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    path = FIGURES / "ucb_section_scores.png"
    figure.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Wrote {path}")


def main() -> None:
    loaded = {label: load(path) for label, path, _color in RUNS}
    FIGURES.mkdir(parents=True, exist_ok=True)
    fitness(loaded)
    distance(loaded)
    rise_fall(loaded)
    sections(loaded)
    choice(loaded)
    scores(loaded)


if __name__ == "__main__":
    main()
