"""Plots for one UCB bandit run, from its recovery.json.

Two sheets: fitness and Hamming distance, then the section choices,
rewards, and UCB scores. UCB is replayed from the offspring log in the
same order the run applied the rewards.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.tile_genome import genome_layout
from evolution.circuits import CIRCUITS
from evolution.run import write_plots

TOP = 8
PALETTE = (
    "#1d4e89",
    "#c45c12",
    "#2a7a4b",
    "#6b5b95",
    "#b03a4a",
    "#0e7c7b",
    "#c4a35a",
    "#5c4a3a",
)


# The original 2-bit adder uses three of the eight cells in the tile.
ADDER_CELL = {
    "LC0": "original low sum",
    "LC1": "original high sum",
    "LC2": "original carry out",
}

_SPAN = {
    "h_l": "horizontal, left side",
    "h_r": "horizontal, right side",
    "v_b": "vertical, bottom side",
    "v_t": "vertical, top side",
    "r_v_b": "vertical, right edge",
    "r_v_t": "vertical, right edge",
    "l_v_b": "vertical, left edge",
    "l_v_t": "vertical, left edge",
}


def net_phrase(net: str) -> str:
    """IceStorm net name as a short phrase."""
    cell = re.fullmatch(r"lutff_(\d+)/out", net)
    if cell:
        name = f"LC{cell.group(1)}"
        role = ADDER_CELL.get(name)
        if role:
            return f"{name} output ({role})"
        return f"{name} output (unused in the original adder)"
    pin = re.fullmatch(r"lutff_(\d+)/in_(\d+)", net)
    if pin:
        return f"LC{pin.group(1)} input {pin.group(2)}"
    local = re.fullmatch(r"local_g(\d+)_(\d+)", net)
    if local:
        return f"local track g{local.group(1)}_{local.group(2)}"
    span = re.fullmatch(r"sp(4|12)_([a-z_]+)_(\d+)", net)
    if span:
        length, path, index = span.groups()
        where = _SPAN.get(path, path.replace("_", " "))
        return f"span-{length} wire {index} ({where})"
    return net


def describe(section) -> str:
    """What one crossover section configures."""
    name = section.name
    bits = len(section.indexes)
    if section.kind == "lut":
        cell = name.split()[0]
        role = ADDER_CELL.get(cell)
        if role:
            return f"{bits}-bit truth table of {cell}, the {role}."
        return f"{bits}-bit truth table of {cell}."
    if section.kind == "ff":
        return f"{bits} bits configuring the flip-flop in {name.split()[0]}."
    if section.kind == "wire":
        src, dst = name.split(" -> ")
        return f"1 bit tying {net_phrase(src)} to {net_phrase(dst)}."
    parts = name.split()
    if section.kind == "mux" and len(parts) == 3 and parts[0] in ("buffer", "routing"):
        src, dst = net_phrase(parts[1]), net_phrase(parts[2])
        if parts[0] == "routing":
            return f"{bits}-bit switch between {src} and {dst}."
        if parts[2].startswith("local_g"):
            return f"{bits}-bit mux from {src} onto {dst}, which feeds LUT inputs in this tile."
        return f"{bits}-bit mux from {src} to {dst}."
    if section.kind == "clock":
        return f"{bits} bits of the tile clock setting."
    if section.kind == "carry":
        return f"{bits} bits of the carry chain into this tile."
    return f"{bits} configuration bits."


def _ink(color: str) -> str:
    value = color.lstrip("#")
    red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return "#1a1a1a" if 0.299 * red + 0.587 * green + 0.114 * blue > 150 else "white"


def _cell_label(net: str) -> str | None:
    match = re.fullmatch(r"lutff_(\d+)/out", net)
    if match:
        return f"LC{match.group(1)}"
    return None


def _track_label(net: str) -> str:
    local = re.fullmatch(r"local_g(\d+)_(\d+)", net)
    if local:
        return f"local g{local.group(1)}_{local.group(2)}"
    span = re.fullmatch(r"sp(4|12)_[a-z_]+_(\d+)", net)
    if span:
        return f"span{span.group(1)} {span.group(2)}"
    return net


def brief(name: str) -> str:
    """Short label for a section, short enough to sit inside a chart."""
    if name.endswith(" LUT"):
        return name
    text = name.replace("buffer ", "").replace("routing ", "")
    if "->" in text:
        src, dst = [part.strip() for part in text.split("->")]
        return f"{_cell_label(src) or src} → {_track_label(dst)}"
    parts = text.split()
    if len(parts) == 2:
        left = _cell_label(parts[0]) or _track_label(parts[0])
        return f"{left} → {_track_label(parts[1])}"
    return short(name)


def short(name: str) -> str:
    text = name.replace("buffer ", "").replace("routing ", "")
    if len(text) <= 34:
        return text
    return text[:32] + "…"


def replay(history):
    """Walk the offspring log the way the bandit did."""
    pulls: dict[str, int] = {}
    reward_sum: dict[str, float] = {}
    updates = 0
    flipped_total: Counter[str] = Counter()
    selected_total: Counter[str] = Counter()
    genes_total: Counter[str] = Counter()
    per_gen = []
    for row in history:
        kids = row.get("offspring") or []
        flipped = Counter()
        selected = Counter()
        genes = Counter()
        improved = 0
        worsened = 0
        delta_sum = 0.0
        for child in kids:
            delta = child["mutated_fitness"] - child["crossover_fitness"]
            delta_sum += delta
            if delta > 0:
                improved += 1
            elif delta < 0:
                worsened += 1
            for name in child["sections_selected"]:
                selected[name] += 1
                selected_total[name] += 1
            for name, count in child["genes_flipped_per_section"].items():
                flipped[name] += 1
                genes[name] += count
                flipped_total[name] += 1
                genes_total[name] += count
            for name in child["sections_flipped"]:
                pulls[name] = pulls.get(name, 0) + 1
                reward_sum[name] = reward_sum.get(name, 0.0) + child["reward"]
                updates += 1
        ucb = {}
        if updates:
            for name, count in pulls.items():
                mean = reward_sum[name] / count
                ucb[name] = mean + math.sqrt(math.log(updates) / count)
        per_gen.append({
            "generation": row["generation"],
            "flipped": flipped,
            "selected": selected,
            "genes": genes,
            "improved": improved,
            "worsened": worsened,
            "unchanged": len(kids) - improved - worsened,
            "mean_delta": delta_sum / len(kids) if kids else None,
            "ucb": ucb,
            "mean_reward": {name: reward_sum[name] / pulls[name] for name in pulls},
        })
    return per_gen, flipped_total, selected_total, genes_total


def focus_names(flipped_total: Counter[str]) -> list[str]:
    return [name for name, _count in flipped_total.most_common(TOP)]


def fitness_sheet(history, out: Path, title: str) -> None:
    gens = [row["generation"] for row in history]
    fig, axes = plt.subplots(2, 1, figsize=(11, 8.2), sharex=True)
    fig.suptitle(title, fontsize=14)

    ax = axes[0]
    ax.plot(gens, [row["best_fitness"] for row in history], color="#2a7a4b", marker="o", markersize=2.5, label="Best")
    ax.plot(gens, [row["mean_fitness"] for row in history], color="#3a6ea5", marker="o", markersize=2.5, label="Mean")
    ax.axhline(1.0, color="#888888", linestyle="--", linewidth=1, label="Recovery")
    ax.set_ylim(-0.05, 1.05)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Fitness")
    ax.set_title("Best and mean fitness")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    ax.plot(gens, [row["mean_pairwise_hamming"] for row in history], color="#6b5b95", marker="o", markersize=2.5, label="Mean pairwise")
    ax.plot(gens, [row["best_distance_to_original"] for row in history], color="#c45c12", marker="o", markersize=2.5, label="Best vs original")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Hamming distance")
    ax.set_title("Diversity and distance to the original")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)


def ucb_sheet(per_gen, flipped_total, selected_total, genes_total, sections, out: Path, title: str, adaptive: bool = False) -> None:
    names = focus_names(flipped_total)
    by_name = {section.name: section for section in sections}
    fig = plt.figure(figsize=(14.5, 19.4))
    grid = GridSpec(5, 2, figure=fig, height_ratios=[0.48, 0.82, 1, 1, 0.82], hspace=0.5, wspace=0.28, top=0.965)
    chosen = "the flips" if adaptive else "the 32 flips"
    fig.suptitle(title.replace("2-bit adder UCB", f"2-bit adder: how UCB chose {chosen}"), fontsize=15, y=0.988)

    ax = fig.add_subplot(grid[0, :])
    ax.axis("off")
    ax.text(
        0.0,
        1.0,
        "How UCB chooses which bits to flip",
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=12,
    )
    ax.text(
        0.0,
        0.72,
        (
            "Each named section is one choice. The flip count starts at 4. Half the children\n"
            "use half that count and half use double it. A tie keeps the smaller count, and the\n"
            "count stays between 1 and 32. One elite is copied. UCB adds the highest-scoring\n"
            "sections until they can hold that many bits, then flips them.\n"
            "A section scores higher when a flip raised the match count, and when tried less often.\n"
            "An untried section goes first. The reward is +1 only when the row count rises.\n"
            "A fall and an unchanged score both pay 0. Fitness decides who survives."
            if adaptive else
            "Each named section is one choice. For a child, UCB keeps adding the highest-scoring\n"
            "sections until they hold at least 32 bits, then flips exactly 32 of those bits.\n"
            "A section scores higher when its flips have changed the match count, and higher still\n"
            "when it has been tried less often. A section that has never been flipped is tried first.\n"
            "The reward is +1 when the number of correct rows changes and −1 when it stays the same.\n"
            "A higher score and a lower score are the same reward. Fitness still decides who survives."
        ),
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        linespacing=1.45,
        color="#222222",
    )

    ax = fig.add_subplot(grid[1, :])
    ax.axis("off")
    ax.set_title("What those sections configure", pad=8)
    rows = [[short(name), describe(by_name[name])] for name in names]
    table = ax.table(
        cellText=rows,
        colLabels=["Section", "What it does"],
        loc="upper center",
        cellLoc="left",
        colWidths=[0.28, 0.72],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.45)
    for index, color in enumerate(PALETTE[:len(names)]):
        swatch = table[index + 1, 0]
        swatch.set_facecolor(color)
        swatch.set_text_props(color=_ink(color))
    for (row, _col), cell in table.get_celld().items():
        cell.set_edgecolor("#d0d0d0")
        if row == 0:
            cell.set_facecolor("#f2f2f2")
        cell.PAD = 0.04

    ax = fig.add_subplot(grid[2, 0])
    gens = [item["generation"] for item in per_gen]
    child_counts = [
        item["improved"] + item["worsened"] + item["unchanged"] for item in per_gen
    ]
    n_children = max(child_counts) if child_counts else 1
    matrix = [[item["flipped"].get(name, 0) for item in per_gen] for name in names]
    image = ax.imshow(
        matrix,
        aspect="auto",
        cmap="Blues",
        vmin=0,
        vmax=n_children,
        interpolation="nearest",
        extent=(gens[0] - 0.5, gens[-1] + 0.5, len(names) - 0.5, -0.5),
    )
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels([brief(name) for name in names])
    for tick, color in zip(ax.get_yticklabels(), PALETTE):
        tick.set_color(color)
    ax.set_xlabel("Generation")
    ax.set_title(f"How many of the {n_children} children flipped a bit in this section")
    mid = n_children // 2
    bar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04, ticks=[0, mid, n_children])
    bar.ax.set_yticklabels(["0   none", str(mid), f"{n_children}   all"])
    bar.set_label("Children")

    ax = fig.add_subplot(grid[2, 1])
    gene_gens = [item["generation"] for item in per_gen]
    stacks = []
    labels = []
    for name in names:
        stacks.append([item["genes"].get(name, 0) for item in per_gen])
        labels.append(short(name))
    other = []
    for item in per_gen:
        other.append(sum(count for name, count in item["genes"].items() if name not in names))
    stacks.append(other)
    labels.append("all other sections")
    ax.stackplot(gene_gens, stacks, colors=[*PALETTE, "#d0d0d0"], labels=labels)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Genes flipped")
    ax.set_title("Where the flips landed (gray is every other section)" if adaptive else "Where the 32 flips landed (gray is every other section)")

    ax = fig.add_subplot(grid[3, 0])
    scored = [item for item in per_gen if item["improved"] or item["worsened"] or item["unchanged"]]
    score_gens = [item["generation"] for item in scored]
    improved = [item["improved"] for item in scored]
    worsened = [item["worsened"] for item in scored]
    unchanged = [item["unchanged"] for item in scored]
    down_base = [improved[i] + worsened[i] for i in range(len(scored))]
    ax.bar(score_gens, improved, width=0.9, color="#2a7a4b", label="Score went up")
    ax.bar(score_gens, worsened, width=0.9, bottom=improved, color="#b03a4a", label="Score went down")
    ax.bar(score_gens, unchanged, width=0.9, bottom=down_base, color="#d0d0d0", label="Score stayed the same")
    means = [item["mean_delta"] for item in scored]
    x_mean = sum(score_gens) / len(score_gens)
    y_mean = sum(means) / len(means)
    spread = sum((x - x_mean) ** 2 for x in score_gens)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(score_gens, means)) / spread
    intercept = y_mean - slope * x_mean
    fit = [slope * x + intercept for x in score_gens]
    right = ax.twinx()
    right.plot(score_gens, means, color="#1a1a1a", linewidth=1.0, label="Mean change in fitness")
    right.plot(score_gens, fit, color="#1a1a1a", linewidth=1.6, linestyle="--", label="Straight fit of that mean")
    right.axhline(0, color="#1a1a1a", linewidth=0.7, alpha=0.45)
    right.set_ylim(-0.28, 0.28)
    right.set_ylabel("Mean change in fitness")
    ax.set_ylim(0, 20)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Children")
    ax.set_title("Of each generation's children, did the score rise or fall?")
    left_handles, left_labels = ax.get_legend_handles_labels()
    right_handles, right_labels = right.get_legend_handles_labels()
    ax.legend(left_handles + right_handles, left_labels + right_labels, fontsize=7, loc="upper right")
    ax.grid(True, axis="y", alpha=0.3)

    ax = fig.add_subplot(grid[3, 1])
    for color, name in zip(PALETTE, names):
        series = [item["ucb"].get(name) for item in per_gen]
        ax.plot(gene_gens, series, color=color, linewidth=1.4, label=short(name))
    ax.set_xlabel("Generation")
    ax.set_ylabel("UCB")
    ax.set_title("Replayed UCB of the sections flipped most often")
    ax.grid(True, alpha=0.3)

    ax = fig.add_subplot(grid[4, :])
    ranked = sorted(names, key=lambda name: genes_total[name])
    y = list(range(len(ranked)))
    bar_colors = [PALETTE[names.index(name)] for name in ranked]
    ax.barh(y, [genes_total[name] for name in ranked], color=bar_colors, height=0.72)
    final_mean = per_gen[-1]["mean_reward"]
    longest = max(genes_total[name] for name in ranked)
    for index, name in enumerate(ranked):
        width = genes_total[name]
        reward = f"mean reward {final_mean.get(name, 0):+.2f}"
        if width > longest * 0.22:
            ax.text(longest * 0.012, index, brief(name), va="center", ha="left", fontsize=8, color=_ink(bar_colors[index]))
            ax.text(width + longest * 0.012, index, reward, va="center", ha="left", fontsize=8, color="#333333")
        else:
            ax.text(width + longest * 0.012, index, f"{brief(name)}    {reward}", va="center", ha="left", fontsize=8, color="#333333")
    ax.set_yticks([])
    ax.set_xlabel("Genes flipped")
    ax.set_title("Sections the search kept returning to, by bits actually flipped")
    ax.set_xlim(0, longest * 1.2)
    ax.tick_params(axis="y", length=0)

    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)


def main(path: Path) -> None:
    saved = json.loads(path.read_text())
    history = saved["history"]
    out_dir = path.parent
    per_gen, flipped_total, selected_total, genes_total = replay(history)
    _positions, sections = genome_layout()
    last = history[-1]["generation"]
    title = f"2-bit adder UCB, stopped after generation {last}"
    circuit = CIRCUITS[saved["circuit"]]
    search = SimpleNamespace(
        algorithm=saved["algorithm"],
        bandit_mode=saved["bandit"]["mode"],
        bits=saved["fault_bits"],
    )
    write_plots(history, out_dir, circuit, search, saved["operable_bits"])
    fitness_path = out_dir / "fitness_diversity.png"
    ucb_path = out_dir / "ucb_sheet.png"
    fitness_sheet(history, fitness_path, title)
    adaptive = (saved.get("bandit") or {}).get("rate") == "two_rate"
    ucb_sheet(per_gen, flipped_total, selected_total, genes_total, sections, ucb_path, title, adaptive)
    stale = out_dir / "bandit_sheet.png"
    if stale.exists():
        stale.unlink()
    print(f"Wrote {fitness_path}")
    print(f"Wrote {ucb_path}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        ROOT / "adder2/evolution/out/bandit_4bit_g200_m32_p15_e3_ucb/recovery.json"
    )
    main(target)
