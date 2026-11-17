"""Named bits of one iCE40 logic tile, grouped into crossover sections.

The 57 configuration bits IceStorm does not name are left out. Everything
else in the 16-by-54 tile is one gene. A section is a set of genes that
belong together: one LUT, one flip-flop, one wire, one routing mux, the
global clock select, or a carry control. Crossover copies a whole section
from one parent.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_ICEBOX = Path("/opt/homebrew/share/icestorm/python")
if str(_ICEBOX) not in sys.path:
    sys.path.insert(0, str(_ICEBOX))

import icebox

# Probability that a section is copied from the fitter of the two parents.
# 0.5 gives each parent about half the sections. 0.7 would give the fitter
# about 70 percent of them.
FITTER_SECTION_SHARE = 0.5

LUT_BITS = (4, 14, 15, 5, 6, 16, 17, 7, 3, 13, 12, 2, 1, 11, 10, 0)
FF_BITS = (8, 9, 18, 19)


@dataclass(frozen=True)
class Section:
    name: str
    kind: str
    indexes: tuple[int, ...]


def _parse_bit(token: str) -> tuple[int, int] | None:
    if token.startswith("!"):
        token = token[1:]
    if not token.startswith("B") or "[" not in token:
        return None
    row = int(token[1:token.index("[")])
    col = int(token[token.index("[") + 1:-1])
    if row < 0 or row > 15 or col < 0 or col > 53:
        return None
    return row, col


def _lc_coord(cell: int, bitnum: int) -> tuple[int, int]:
    return cell * 2 + bitnum // 10, 36 + bitnum % 10


def _entry_coords(entry) -> list[tuple[int, int]]:
    coords = []
    for token in entry[0]:
        coord = _parse_bit(token)
        if coord is not None and coord not in coords:
            coords.append(coord)
    return coords


@lru_cache(maxsize=1)
def genome_layout() -> tuple[tuple[tuple[int, int], ...], tuple[Section, ...]]:
    """Tile-local (row, col) genes, and the sections that index them."""
    claimed: set[tuple[int, int]] = set()
    groups: list[tuple[str, str, list[tuple[int, int]]]] = []

    def take(name: str, kind: str, coords: list[tuple[int, int]]) -> None:
        fresh = [coord for coord in coords if coord not in claimed]
        if not fresh:
            return
        claimed.update(fresh)
        groups.append((name, kind, fresh))

    for cell in range(8):
        take(f"LC{cell} LUT", "lut", [_lc_coord(cell, bit) for bit in LUT_BITS])
        take(f"LC{cell} flip-flop", "ff", [_lc_coord(cell, bit) for bit in FF_BITS])

    wires: list[tuple[str, list[tuple[int, int]]]] = []
    muxes: list[tuple[str, list[tuple[int, int]]]] = []
    for entry in icebox.logictile_5k_db:
        kind = entry[1]
        coords = _entry_coords(entry)
        if not coords:
            continue
        if kind == "NegClk":
            take("tile clock polarity", "clock", coords)
        elif kind == "ColBufCtrl":
            continue
        elif kind == "CarryInSet":
            take("carry in set", "carry", coords)
        elif kind == "buffer" and entry[2] == "carry_in":
            take("carry in", "carry", coords)
        elif len(coords) == 1 and kind == "buffer":
            wires.append((f"{entry[2]} -> {entry[3]}", coords))
        else:
            label = " ".join(str(part) for part in entry[1:])
            muxes.append((label, coords))

    clock = []
    for entry in icebox.logictile_5k_db:
        if entry[1] == "ColBufCtrl":
            clock.extend(_entry_coords(entry))
    take("global clock select", "clock", clock)

    for name, coords in muxes:
        take(name, "mux", coords)
    for name, coords in wires:
        take(name, "wire", coords)

    named = set()
    for entry in icebox.logictile_5k_db:
        named.update(_entry_coords(entry))
    for coord in sorted(named - claimed):
        take(f"bit {coord[0]},{coord[1]}", "other", [coord])

    positions = tuple(sorted(claimed))
    index_of = {coord: i for i, coord in enumerate(positions)}
    sections = tuple(
        Section(name, kind, tuple(index_of[coord] for coord in coords))
        for name, kind, coords in groups
    )
    covered = [index for section in sections for index in section.indexes]
    if len(covered) != len(set(covered)) or set(covered) != set(range(len(positions))):
        raise RuntimeError("crossover sections do not partition the genome")
    return positions, sections


def load_tile(asc_lines: list[str], tile_x: int, tile_y: int):
    """ASC positions, the original gene values, and the crossover sections."""
    local, sections = genome_layout()
    start = asc_lines.index(f".logic_tile {tile_x} {tile_y}")
    positions = []
    values = []
    for row, col in local:
        text = asc_lines[start + 1 + row].strip()
        positions.append((start + 1 + row, col))
        values.append(int(text[col]))
    return positions, tuple(values), sections


def select_index(fitnesses, rng) -> int:
    total = sum(fitnesses)
    if total <= 0:
        return rng.randrange(len(fitnesses))
    pick = rng.random() * total
    acc = 0.0
    for index, fitness in enumerate(fitnesses):
        acc += fitness
        if acc >= pick:
            return index
    return len(fitnesses) - 1


def crossover(parent_a, score_a, parent_b, score_b, sections, rng, share=FITTER_SECTION_SHARE):
    """Copy each section from the fitter parent with probability `share`."""
    if score_b > score_a:
        parent_a, parent_b = parent_b, parent_a
    child = list(parent_a)
    for section in sections:
        if rng.random() >= share:
            for index in section.indexes:
                child[index] = parent_b[index]
    return tuple(child)


def mutate(genome, rng, probability):
    bits = []
    for bit in genome:
        if rng.random() < probability:
            bits.append(1 - bit)
        else:
            bits.append(bit)
    return tuple(bits)


def flip_exact(genome, indexes):
    """Flip each listed gene once. `indexes` are distinct positions."""
    bits = list(genome)
    for index in indexes:
        bits[index] = 1 - bits[index]
    return tuple(bits)


def mate(pop, scores, sections, rng, share=FITTER_SECTION_SHARE):
    """Two fitness-chosen parents and their section-crossover child, before mutation.

    The second value is the average of the two parents' fitness.
    """
    first = select_index(scores, rng)
    second = select_index(scores, rng)
    for _ in range(6):
        if pop[second] != pop[first]:
            break
        second = select_index(scores, rng)
    child = crossover(
        pop[first], scores[first], pop[second], scores[second], sections, rng, share
    )
    return child, (scores[first] + scores[second]) / 2


def breed(pop, scores, sections, rng, probability, share=FITTER_SECTION_SHARE):
    """Two fitness-chosen parents, section crossover, then mutation."""
    child, _expected = mate(pop, scores, sections, rng, share)
    return mutate(child, rng, probability)
