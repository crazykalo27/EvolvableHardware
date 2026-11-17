"""One operable region for both fault injection and evolution.

The region is every bit that is already 1 in the active logic tile.
Fault injection flips N of those bits. Evolution may flip any of them.
A later, wider region should be returned from this same place so both
sides stay matched.
"""

from __future__ import annotations

import random


def split_fault(
    operable: list[tuple[int, int]], n_faults: int, seed: int
) -> tuple[list[tuple[int, int]], set[int]]:
    """Return the operable bit list and the indexes that start flipped off.

    The flipped indexes are the first N of one seeded 8-draw, matching the
    earlier nested 4-bit and 8-bit faults when `operable` is in the same order.
    """
    if n_faults < 1:
        raise SystemExit("n_faults must be at least 1")
    draw = max(8, n_faults)
    if len(operable) < draw:
        raise SystemExit(f"Need at least {draw} operable bits; found {len(operable)}")
    chosen = set(random.Random(seed).sample(operable, draw)[:n_faults])
    fault_indexes = {i for i, pos in enumerate(operable) if pos in chosen}
    return operable, fault_indexes
