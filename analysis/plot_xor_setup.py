"""One sheet: the placed XOR, the live test that passed, and the fault baseline.

The live window from graph_xor.py was not saved. The log for that run is 80
matches and 0 mismatches, and demo_xor.py is the stimulus: 20 cycles of the
four input pairs, a sample 20 ms after each change, then 180 ms of hold.
Measured Y is drawn on top of expected Y.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from viz.show_circuit import PRESETS, render  # noqa: E402

OUT = ROOT / "report" / "figures"
CIRCUIT = OUT / "xor_loaded.png"
SHEET = OUT / "xor_setup_sheet.png"
BASELINE = ROOT / "xor" / "fault_injection" / "out" / "fault_baseline_results.json"


def live_trace():
    """The recorded passing run: every measured sample equals A xor B."""
    patterns = ((0, 0), (0, 1), (1, 0), (1, 1))
    times = []
    a_vals = []
    b_vals = []
    expected = []
    t = 20
    for _cycle in range(20):
        for a, b in patterns:
            times.append(t / 1000)
            a_vals.append(a)
            b_vals.append(b)
            expected.append(a ^ b)
            t += 200
    return times, a_vals, b_vals, expected


def _ink(rgb: np.ndarray) -> np.ndarray:
    bg = rgb[0, 0].astype(int)
    return np.abs(rgb.astype(int) - bg).sum(axis=2) > 24


def content_box(image: Image.Image, pad: int = 14) -> Image.Image:
    rgb = np.asarray(image.convert("RGB"))
    ink = _ink(rgb)
    rows = np.where(ink.any(axis=1))[0]
    cols = np.where(ink.any(axis=0))[0]
    top = max(0, int(rows[0]) - pad)
    bottom = min(rgb.shape[0], int(rows[-1]) + pad)
    left = max(0, int(cols[0]) - pad)
    right = min(rgb.shape[1], int(cols[-1]) + pad)
    cropped = rgb[top:bottom, left:right]
    # The legend sits under the largest blank band in the lower half. Drop it.
    row_ink = _ink(cropped).any(axis=1)
    widest = None
    index = 0
    while index < len(row_ink):
        end = index
        while end < len(row_ink) and row_ink[end] == row_ink[index]:
            end += 1
        if not row_ink[index] and index > len(row_ink) * 0.4:
            if widest is None or end - index > widest[1] - widest[0]:
                widest = (index, end)
        index = end
    if widest is not None and widest[1] < len(row_ink) - 8:
        cropped = cropped[: widest[0] + 6]
    # Blank rows between the title and the drawing are padding.
    # A row that crosses a wire or a cell border is kept, so the drawing is not rescaled.
    ink = _ink(cropped)
    row_ink = ink.any(axis=1)
    keep: list[int] = []
    index = 0
    max_gap = 22
    while index < len(row_ink):
        end = index
        while end < len(row_ink) and row_ink[end] == row_ink[index]:
            end += 1
        if row_ink[index] or end - index <= max_gap:
            keep.extend(range(index, end))
        else:
            mid = (index + end) // 2
            keep.extend(range(mid - max_gap // 2, mid + max_gap // 2))
        index = end
    return Image.fromarray(cropped[keep])


def draw_live(ax) -> None:
    times, a_vals, b_vals, expected = live_trace()
    lanes = (
        ("A", a_vals, "#1f4e79"),
        ("B", b_vals, "#c0392b"),
        ("Y", expected, "#1e8449"),
    )
    gap = 1.35
    centers = []
    for index, (name, values, color) in enumerate(lanes):
        base = (2 - index) * gap
        level = [base + 0.85 * value for value in values]
        ax.step(times, level, where="post", color=color, linewidth=1.35, label=name)
        if name == "Y":
            ax.plot(
                times,
                level,
                linestyle="none",
                marker="o",
                markersize=2.4,
                color="#1a1a1a",
                label="Measured Y",
                zorder=4,
            )
        centers.append(base + 0.42)
    ax.set_xlim(0, times[-1] + 0.2)
    ax.set_ylim(-0.25, 3 * gap - 0.35)
    ax.set_yticks(centers)
    ax.set_yticklabels([name for name, _values, _color in lanes])
    ax.tick_params(axis="y", length=0, labelsize=9, pad=1)
    ax.set_xlabel("Time (s)", fontsize=9, labelpad=1)
    ax.set_title("Live FPGA XOR test    80/80", loc="left", fontsize=11, pad=2)
    ax.grid(True, axis="x", alpha=0.25)
    ax.legend(
        frameon=False,
        fontsize=8,
        loc="lower right",
        bbox_to_anchor=(1.0, 1.02),
        ncol=4,
        borderaxespad=0.0,
    )
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)


def draw_fault(ax_acc, ax_pass, payload: dict) -> None:
    averages = payload["averages"]
    seed_runs = payload["seed_runs"]
    xs = [str(row["flips"]) for row in averages]
    means = [row["mean_accuracy"] * 100 for row in averages]
    stdevs = [row["stdev_accuracy"] * 100 for row in averages]
    passes = [row["mean_pass_rate"] * 100 for row in averages]
    colors = ["#2a7a4b" if mean >= 99.9 else "#b33a3a" for mean in means]

    ax_acc.bar(xs, means, yerr=stdevs, capsize=4, color=colors, alpha=0.9, zorder=2)
    for index, flips in enumerate(row["flips"] for row in averages):
        for run in seed_runs:
            for result in run["results"]:
                if result["flips"] == flips:
                    ax_acc.scatter(index, result["accuracy"] * 100, color="#222222", s=22, zorder=3)
    for index, mean in enumerate(means):
        ax_acc.text(index, min(112, mean + stdevs[index] + 2), f"{mean:.0f}%", ha="center", va="bottom", fontsize=8)
    ax_acc.set_ylim(0, 118)
    ax_acc.set_yticks([0, 50, 100])
    ax_acc.set_xlabel("Configuration bits flipped", fontsize=9)
    ax_acc.set_ylabel("Accuracy (%)", fontsize=9)
    ax_acc.set_title("Mean accuracy", loc="left", fontsize=11, pad=2)
    ax_acc.tick_params(labelsize=8)
    ax_acc.grid(True, axis="y", alpha=0.3)

    ax_pass.bar(xs, passes, color="#3a6ea5", alpha=0.9)
    for index, rate in enumerate(passes):
        ax_pass.text(index, rate + 2, f"{rate:.0f}%", ha="center", va="bottom", fontsize=8)
    ax_pass.set_ylim(0, 118)
    ax_pass.set_yticks([0, 50, 100])
    ax_pass.set_xlabel("Configuration bits flipped", fontsize=9)
    ax_pass.set_ylabel("Full pass (%)", fontsize=9)
    ax_pass.set_title("Full pass", loc="left", fontsize=11, pad=2)
    ax_pass.tick_params(labelsize=8)
    ax_pass.grid(True, axis="y", alpha=0.3)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    preset = PRESETS["xor"]
    render(
        ROOT / "xor" / "build" / "xor.asc",
        "xor.asc",
        preset["pcf"],
        dict(preset["gpio"]),
        preset["tile"],
        CIRCUIT,
    )
    payload = json.loads(BASELINE.read_text())

    pixels = np.asarray(content_box(Image.open(CIRCUIT)))

    fig_w, fig_h = 16.8, 7.1
    figure = plt.figure(figsize=(fig_w, fig_h), facecolor="white")
    left, right = 0.055, 0.99
    span = right - left
    top = 0.99
    circuit_h = 0.24
    circuit_bottom = top - circuit_h
    ax_circuit = figure.add_axes([left, circuit_bottom, span, circuit_h])
    ax_circuit.imshow(pixels, aspect="auto")
    ax_circuit.set_axis_off()

    live_h = 0.26
    live_bottom = circuit_bottom - 0.055 - live_h
    ax_live = figure.add_axes([left, live_bottom, span, live_h])

    chart_bottom = 0.10
    chart_h = live_bottom - 0.07 - chart_bottom
    chart_gap = 0.07
    chart_w = (span - chart_gap) / 2
    ax_acc = figure.add_axes([left, chart_bottom, chart_w, chart_h])
    ax_pass = figure.add_axes([left + chart_w + chart_gap, chart_bottom, chart_w, chart_h])

    draw_live(ax_live)
    draw_fault(ax_acc, ax_pass, payload)

    figure.savefig(SHEET, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Wrote {CIRCUIT}")
    print(f"Wrote {SHEET}")


if __name__ == "__main__":
    main()
