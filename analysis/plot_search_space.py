"""Search-space sizes for the closed fault masks and the full 864-bit tile.

The axis is log2 of the number of genomes, so each unit is one doubling.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "figures" / "search_space.png"

LABELS = ("4-bit genotype", "8-bit genotype", "864-bit genotype")
BITS = (4, 8, 864)


def main() -> None:
    figure, axis = plt.subplots(figsize=(12.6, 3.5), facecolor="white")
    positions = (0, 1, 2)
    axis.barh(positions, BITS, color="#0072B2", height=0.58)
    axis.set_yticks(positions, LABELS)
    axis.set_xlim(0, 1000)
    axis.set_ylim(-0.55, 2.55)
    axis.set_xlabel("Doublings from one genome    (log₂ of the search space)")
    axis.set_title("Search space", loc="left", fontsize=12, pad=8)
    axis.tick_params(labelsize=9)
    axis.grid(True, axis="x", alpha=0.3)
    for spine in ("top", "right"):
        axis.spines[spine].set_visible(False)

    axis.text(18, 0, r"$2^{4} = 16$ genomes", va="center", ha="left", fontsize=9, color="#1a1a1a")
    axis.text(22, 1, r"$2^{8} = 256$ genomes", va="center", ha="left", fontsize=9, color="#1a1a1a")
    axis.text(
        20,
        2,
        r"$2^{864}$ genomes      $2^{860}\times$ the 4-bit space      $2^{856}\times$ the 8-bit space",
        va="center",
        ha="left",
        fontsize=10,
        color="white",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
