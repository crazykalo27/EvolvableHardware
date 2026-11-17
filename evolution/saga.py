"""SAGA search: one drifting elite and an inchworm rate on the children.

The initial population is 6 copies of the damaged genome and 15 mutants at
4 expected flips. After that, one elite is kept and the other 20 slots are
section-crossover children. A strict gain replaces the elite and returns the
rate to 2/N. A tie that is not an exact copy can replace the elite without
resetting the rate. The 7 children with the lowest parent-score average use
the stalled rate. The other 13 stay at 2/N. The stalled rate is 2, 6, 10, ...
34. It first rises at stall 3 and every 3 generations after that, and it holds
at 34.
"""

from __future__ import annotations

import math

from analysis.tile_genome import mate, mutate

SAGA_POPULATION = 21
SAGA_ELITES = 1
SAGA_GENERATIONS = 300
SAGA_SEED = 13
SAGA_SEED_COPIES = 6
SAGA_INITIAL_FLIPS = 4
SAGA_BASE_FLIPS = 2
SAGA_STEP_FLIPS = 4
SAGA_MAX_FLIPS = 34
SAGA_FIRST_STALL = 3
SAGA_STALL_EVERY = 3
SAGA_BOTTOM = 7
SAGA_DRIFT_WINDOW = 10


def saga_flips(stall: int) -> int:
    """Expected flips for the weakest children after this many generations without a strict gain."""
    if stall < SAGA_FIRST_STALL:
        return SAGA_BASE_FLIPS
    steps = 1 + (stall - SAGA_FIRST_STALL) // SAGA_STALL_EVERY
    return min(SAGA_MAX_FLIPS, SAGA_BASE_FLIPS + SAGA_STEP_FLIPS * steps)


def update_stall(previous_score, new_score, stall: int) -> int:
    """Zero the clock when the elite score is first set or strictly rises. A tie keeps counting."""
    if previous_score is None or new_score > previous_score:
        return 0
    return stall + 1


def stops_at_perfect(algorithm: str) -> bool:
    """SAGA keeps going on a perfect score so the plateau itself can be watched."""
    return algorithm != "saga"


def initial_population(damaged, rng):
    """Six copies of the damaged genome, then 15 independent mutants at 4/N."""
    pop = [damaged] * SAGA_SEED_COPIES
    probability = SAGA_INITIAL_FLIPS / len(damaged)
    while len(pop) < SAGA_POPULATION:
        pop.append(mutate(damaged, rng, probability))
    strengths = [0] * SAGA_SEED_COPIES + [SAGA_INITIAL_FLIPS] * (SAGA_POPULATION - SAGA_SEED_COPIES)
    return pop, strengths


def choose_elite(elite, elite_score, children, child_scores, rng):
    """Return (genome, outcome). Outcome is improved, drifted, or kept.

    A strict gain takes the best score, with a random choice among ties at that
    score. Otherwise a child that matches the elite and differs in at least one
    bit can take its place. An exact copy never replaces it.
    """
    better = [(genome, score) for genome, score in zip(children, child_scores) if score > elite_score]
    if better:
        best = max(score for _genome, score in better)
        pool = [genome for genome, score in better if score == best]
        return rng.choice(pool), "improved"
    tied = [
        genome
        for genome, score in zip(children, child_scores)
        if score == elite_score and genome != elite
    ]
    if tied:
        return rng.choice(tied), "drifted"
    return elite, "kept"


def place_elite_first(pop, scores, elite):
    """Move the kept elite to index 0. Later drift measures read that position."""
    index = next(i for i, genome in enumerate(pop) if genome == elite)
    if index == 0:
        return list(pop), list(scores)
    order = [index] + [i for i in range(len(pop)) if i != index]
    return [pop[i] for i in order], [scores[i] for i in order]


def assign_rates(parent_means, level: float, base: float, n_bottom: int) -> list[float]:
    """Give the lowest parent-mean children the stalled rate. Earlier children win a tie."""
    n_bottom = min(n_bottom, len(parent_means))
    order = sorted(range(len(parent_means)), key=lambda i: (parent_means[i], i))
    boosted = set(order[:n_bottom])
    return [level if i in boosted else base for i in range(len(parent_means))]


def saga_next(pop, scores, rng, sections, share, level_flips: float, base_flips: float, n_bottom: int = SAGA_BOTTOM):
    """Copy the elite at index 0. Every other slot is one crossover child, mutated once."""
    elite = pop[0]
    carried = {elite: scores[0]}
    drafted = [mate(pop, scores, sections, rng, share) for _ in range(len(pop) - 1)]
    rates = assign_rates([average for _child, average in drafted], level_flips, base_flips, n_bottom)
    length = len(elite)
    children = []
    for (child, _average), flips in zip(drafted, rates):
        children.append(mutate(child, rng, flips / length))
    return [elite, *children], carried, rates


def _centroid(genomes: list[str]) -> list[float]:
    width = len(genomes[0])
    count = len(genomes)
    return [sum(genome[i] == "1" for genome in genomes) / count for i in range(width)]


def _consensus(genomes: list[str]) -> str:
    count = len(genomes)
    columns = zip(*genomes)
    return "".join("1" if sum(bit == "1" for bit in column) * 2 > count else "0" for column in columns)


def _hamming(left: str, right: str) -> int:
    return sum(a != b for a, b in zip(left, right))


def _euclidean(left: list[float], right: list[float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def drift_record(past: list[list[str]], current: list[str], window: int = SAGA_DRIFT_WINDOW) -> dict:
    """Distances from this population back to the start and to N generations ago.

    The elite is genome 0. The centroid is the per-bit fraction of ones.
    Consensus distance is the Hamming distance between majority genomes.
    """
    now_elite = current[0]
    now_centroid = _centroid(current)
    now_consensus = _consensus(current)
    if not past:
        return {
            "drift_lag": 0,
            "elite_drift": 0,
            "elite_drift_from_start": 0,
            "centroid_drift": 0.0,
            "centroid_drift_from_start": 0.0,
            "consensus_drift": 0,
            "consensus_drift_from_start": 0,
        }
    lag = min(window, len(past))
    ago = past[-lag]
    start = past[0]
    ago_centroid = _centroid(ago)
    start_centroid = _centroid(start)
    return {
        "drift_lag": lag,
        "elite_drift": _hamming(now_elite, ago[0]),
        "elite_drift_from_start": _hamming(now_elite, start[0]),
        "centroid_drift": _euclidean(now_centroid, ago_centroid),
        "centroid_drift_from_start": _euclidean(now_centroid, start_centroid),
        "consensus_drift": _hamming(now_consensus, _consensus(ago)),
        "consensus_drift_from_start": _hamming(now_consensus, _consensus(start)),
    }


def tie_fraction(scores) -> float:
    """Share of the non-elite genomes whose score matches the elite."""
    if len(scores) < 2:
        return 0.0
    elite = scores[0]
    return sum(score == elite for score in scores[1:]) / (len(scores) - 1)
