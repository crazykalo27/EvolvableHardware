"""The circuits a search can be pointed at.

A circuit is the original bitstream, the tile evolution may edit, and the
board script that turns a loaded bitstream into a fitness number. The script
must define score(bin_name) and print one line:

    RESULT,<name>,<matches>,<total>,<matches/total>

Fitness is matches / total. To try a different fitness, write another script
with that line and pass it with --score.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Circuit:
    name: str
    title: str
    asc: str
    tile: tuple[int, int]
    score_script: str
    preset: str
    fitness: str
    population: int
    generations: int
    elites: int
    expected_flips: float
    section_share: float = 0.5
    seed: int = 42
    bits: int = 4


CIRCUITS: dict[str, Circuit] = {
    "xor": Circuit(
        name="xor",
        title="XOR",
        asc="xor/build/xor.asc",
        tile=(8, 1),
        score_script="xor/board/truth_table_score.py",
        preset="xor",
        fitness="correct measurements / 20 (4 patterns, 5 repeats)",
        population=10,
        generations=30,
        elites=3,
        expected_flips=1,
    ),
    "adder2": Circuit(
        name="adder2",
        title="2-bit adder",
        asc="adder2/build/adder2.asc",
        tile=(20, 20),
        score_script="adder2/board/adder_score.py",
        preset="adder2",
        fitness="correct rows / 16 (s0, s1, and cout, 1 pass)",
        population=23,
        generations=100,
        elites=3,
        expected_flips=4,
    ),
    "adder4": Circuit(
        name="adder4",
        title="4-bit adder",
        asc="adder4/build/adder4.asc",
        tile=(17, 1),
        score_script="adder4/board/adder4_score.py",
        preset="adder4",
        fitness="correct rows / 256 (s0..s3 and cout, 1 pass)",
        population=20,
        generations=30,
        elites=3,
        expected_flips=1,
    ),
}
