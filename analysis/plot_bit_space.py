"""Compare fault size and repair search space across XOR, adder2, and adder4."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "bit_space_scale.png"

CIRCUITS = ["XOR", "2-bit adder", "4-bit adder"]
SET_BITS = np.array([17, 61, 97])
TILE_BITS = 864
FAULTS = (4, 8)


def main() -> None:
    fig, (ax_fault, ax_space) = plt.subplots(
        1, 2, figsize=(12.2, 5.2), gridspec_kw={"width_ratios": [1.15, 1]}
    )

    y = np.arange(len(CIRCUITS))
    ax_fault.barh(y, SET_BITS, color="#d9e8d4", edgecolor="#2a7a4b", height=0.62, label="Set bits in the tile", zorder=1)
    ax_fault.barh(y - 0.16, [8] * len(CIRCUITS), color="#c45c12", height=0.16, label="8-bit fault", zorder=2)
    ax_fault.barh(y + 0.16, [4] * len(CIRCUITS), color="#1d4e89", height=0.16, label="4-bit fault", zorder=3)
    for i, n in enumerate(SET_BITS):
        ax_fault.text(
            n + 1.5,
            i,
            f"{n} set bits\n4 bits = {4 / n:.0%}    8 bits = {8 / n:.0%}",
            va="center",
            ha="left",
            fontsize=8,
            color="#333333",
        )
    ax_fault.set_yticks(y)
    ax_fault.set_yticklabels(CIRCUITS)
    ax_fault.set_xlabel("Bits")
    ax_fault.set_xlim(0, 145)
    ax_fault.set_title("How much of the used bits the fault flips")
    ax_fault.legend(loc="lower right", fontsize=8, frameon=False)
    ax_fault.grid(axis="x", alpha=0.3)

    # Repair space is 2^N because evolution may change only the faulted bits.
    # The full pool is every set bit in the tile, which we did not open.
    labels = ["4-bit repair\n(2^4)", "8-bit repair\n(2^8)", "Whole set-bit pool"]
    repair4 = np.full(len(CIRCUITS), 2**4)
    repair8 = np.full(len(CIRCUITS), 2**8)
    full = 2.0 ** SET_BITS
    x = np.arange(len(CIRCUITS))
    width = 0.26
    ax_space.bar(x - width, repair4, width, color="#1d4e89", label=labels[0])
    ax_space.bar(x, repair8, width, color="#c45c12", label=labels[1])
    ax_space.bar(x + width, full, width, color="#2a7a4b", label=labels[2])
    ax_space.set_yscale("log")
    ax_space.set_xticks(x)
    ax_space.set_xticklabels(CIRCUITS)
    ax_space.set_ylabel("Genotypes")
    ax_space.set_title("Space evolution can search")
    ax_space.legend(fontsize=8, frameon=False)
    ax_space.grid(axis="y", which="both", alpha=0.3)
    ax_space.set_ylim(8, 1e30)

    fig.suptitle(
        f"Each tile is {TILE_BITS} bits. A 4-bit fault is {4 / TILE_BITS:.1%} of a tile; an 8-bit fault is {8 / TILE_BITS:.1%}.",
        fontsize=11,
        x=0.02,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.92))
    fig.text(
        0.02,
        0.02,
        "Repair bars are identical because evolution was only allowed to change the bits that were faulted. "
        "The green bars are the space if every set bit in the tile could change.",
        fontsize=8,
        color="#333333",
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=160)
    plt.close(fig)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
