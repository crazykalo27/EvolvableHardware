"""Two pages from the spatial circuit viewer.

The placed 2-bit and 4-bit adders sit side by side.
Six champions from other runs sit two across and three down.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.lines import Line2D
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "figures"
PAIR = OUT / "adders_side_by_side.png"
GALLERY = OUT / "champion_circuits.png"

BG = "#f7f5f2"
INK = "#1c2833"


def _ink(rgb: np.ndarray) -> np.ndarray:
    bg = rgb[0, 0].astype(int)
    return np.abs(rgb.astype(int) - bg).sum(axis=2) > 24


def _bands(row_ink: np.ndarray) -> list[tuple[int, int]]:
    bands: list[tuple[int, int]] = []
    index = 0
    while index < len(row_ink):
        if not row_ink[index]:
            index += 1
            continue
        end = index
        while end < len(row_ink) and row_ink[end]:
            end += 1
        bands.append((index, end))
        index = end
    return bands


def drawing_only(image: Image.Image, pad: int = 18) -> np.ndarray:
    """Keep the pads, cells, and gap labels. Drop the title and the legend."""
    rgb = np.asarray(image.convert("RGB"))
    bands = _bands(_ink(rgb).any(axis=1))
    if not bands:
        return rgb
    main = max(bands, key=lambda band: band[1] - band[0])
    top = max(0, main[0] - pad)
    bottom = min(rgb.shape[0], main[1] + pad)
    cropped = rgb[top:bottom]
    cols = np.where(_ink(cropped).any(axis=0))[0]
    left = max(0, int(cols[0]) - pad)
    right = min(cropped.shape[1], int(cols[-1]) + pad + 1)
    return cropped[:, left:right]


def show(ax, pixels: np.ndarray) -> None:
    ax.imshow(pixels, interpolation="lanczos")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_facecolor(BG)


def legend(fig, y: float) -> None:
    handles = [
        mpatches.Patch(facecolor="#2e5f8a", edgecolor="#1c2833", label="Input"),
        mpatches.Patch(facecolor="#d4762c", edgecolor="#1c2833", label="Output"),
        mpatches.Patch(facecolor="#6b5b95", edgecolor="#1c2833", label="Input and output on one pad"),
        mpatches.Patch(facecolor="white", edgecolor="#1e8449", label="Logic cell"),
        Line2D([0], [0], color="#1f4e79", lw=1.7, label="Wire"),
        Line2D([0], [0], color="#5b4b8a", lw=1.6, label="Carry"),
        Line2D([0], [0], color="#b0aaa2", lw=1.0, linestyle=(0, (3, 3)), label="Gap left out"),
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=7,
        frameon=False,
        fontsize=8,
        borderaxespad=0.0,
        bbox_to_anchor=(0.5, y),
    )


def caption(fig, x: float, y: float, title: str, detail: str) -> None:
    fig.text(x, y, title, ha="left", va="bottom", fontsize=12, color=INK)
    fig.text(x, y - 0.016, detail, ha="left", va="top", fontsize=9, color="#4a4a4a")


def page_pair(adder2: np.ndarray, adder4: np.ndarray) -> None:
    figure = plt.figure(figsize=(16.4, 10.6), facecolor=BG)
    caption(
        figure,
        0.04,
        0.965,
        "2-bit adder",
        "Tile 20,20. Three cells. Carry runs LC0 into LC1 into LC2.",
    )
    caption(
        figure,
        0.52,
        0.965,
        "4-bit adder",
        "Tile 17,1. Five cells. The a inputs come from much farther away.",
    )
    left = figure.add_axes([0.03, 0.09, 0.45, 0.80])
    right = figure.add_axes([0.52, 0.09, 0.45, 0.80])
    show(left, adder2)
    show(right, adder4)
    legend(figure, 0.005)
    figure.savefig(PAIR, dpi=140, facecolor=BG)
    plt.close(figure)


def page_gallery(panels: list[tuple[np.ndarray, str, str]]) -> None:
    figure = plt.figure(figsize=(16.4, 20.4), facecolor=BG)
    figure.text(
        0.04,
        0.988,
        "Champions from other runs. Not a comparison. Each picture is the best circuit that run had when it stopped.",
        ha="left",
        va="top",
        fontsize=12,
        color=INK,
    )
    row_top = 0.940
    row_h = 0.292
    for index, (pixels, title, detail) in enumerate(panels):
        column = index % 2
        row = index // 2
        x = 0.04 if column == 0 else 0.52
        top = row_top - row * row_h
        caption(figure, x, top, title, detail)
        ax = figure.add_axes([x, top - 0.268, 0.44, 0.228])
        show(ax, pixels)
    legend(figure, 0.008)
    figure.savefig(GALLERY, dpi=130, facecolor=BG)
    plt.close(figure)


def main() -> None:
    import sys

    sys.path.insert(0, str(ROOT))
    from viz.show_circuit import PRESETS, render

    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        large = Path(tmp) / "large_step.png"
        preset = PRESETS["adder2"]
        render(
            ROOT / "adder2/evolution/out/direct_4bit/best.asc",
            "best.asc",
            preset["pcf"],
            dict(preset["gpio"]),
            preset["tile"],
            large,
        )
        sources = {
            "adder2": ROOT / "viz/preview/adder2.png",
            "adder4": ROOT / "viz/preview/adder4.png",
            "section": ROOT / "adder2/evolution/out/section_4bit_p23_g100/final_circuit.png",
            "inchworm": ROOT / "adder2/evolution/out/inchworm_4bit_g500_m1_p20_e5/final_circuit.png",
            "hill5": ROOT / "adder2/evolution/out/hill_4bit_g100_m4_p5_neutral/final_circuit.png",
            "large": large,
            "saga": ROOT / "adder2/evolution/out/saga_4bit_g500_m2_p21_e1_seed13/final_circuit.png",
            "xor": ROOT / "xor/evolution/out/ea_4bit_g25_m32_p10_e3/final_circuit.png",
        }
        pictures = {name: drawing_only(Image.open(path)) for name, path in sources.items()}

    page_pair(pictures["adder2"], pictures["adder4"])
    page_gallery(
        [
            (
                pictures["section"],
                "Section crossover    0.625",
                "Lost a1 and b1. Carry stayed. s1 is no longer a clean xor.",
            ),
            (
                pictures["inchworm"],
                "Inchworm    0.500",
                "Lost a1. b1 stayed. Extra cells turned on above the adder.",
            ),
            (
                pictures["hill5"],
                "Five hill climbers    0.375",
                "Lost a0. The carry is gone. cout is not b0.",
            ),
            (
                pictures["large"],
                "Large step, about 17 flips    0.750",
                "Inputs still arrive. Carry is only LC1 into LC2. Extra cells are on.",
            ),
            (
                pictures["saga"],
                "SAGA, generation 444    0.688",
                "The highest adder score. It is no longer one tile.",
            ),
            (
                pictures["xor"],
                "XOR, 32 flips    0.650",
                "b is gone. The other cells in the tile are constants.",
            ),
        ]
    )
    print(f"Wrote {PAIR}")
    print(f"Wrote {GALLERY}")


if __name__ == "__main__":
    main()
