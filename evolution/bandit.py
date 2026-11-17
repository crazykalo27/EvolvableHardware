"""UCB over the named crossover sections.

Each arm is one section. For a child, the highest-UCB sections are drawn until
their genes can hold the flip budget, then exactly that many genes are flipped
inside the pool.

The reward pays +1 only when the mutant scores higher than the crossover
child. A drop and an unchanged score both pay 0. Either visit still counts,
so the exploration term is what brings other sections forward. Only sections
that received a flip are updated. Parent selection and elitism never read
this reward.

Fitness is a proxy for the output vector. The search sees matches/total, not
the measured outputs. Two different output patterns with the same match count
look unchanged. IMPACT_BASIS records that limit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

IMPACT_BASIS = "fitness_proxy"
UCB_C = 1.0
DEFAULT_FLIPS = 32


def impact_reward(baseline: float, mutated: float) -> tuple[int, bool]:
    """+1 when fitness rises, 0 when it falls or stays the same.

    The scalar is a proxy for the measured output. Two different outputs with
    the same match count look unchanged. A visit that pays 0 still counts, so
    the exploration term shrinks for that section.
    """
    if mutated > baseline:
        return 1, True
    return 0, mutated < baseline


def realized_flips(rng, expected: float) -> int:
    """Whole flips, plus one extra flip with probability equal to the fraction.

    An expected count of 4 flips 4 genes. An expected count of 0.5 flips one
    gene half the time and otherwise flips none.
    """
    whole = int(math.floor(expected + 1e-9))
    fraction = expected - whole
    if fraction > 1e-9 and rng.random() < fraction:
        return whole + 1
    return whole


def lookup_fitness(genome, cache, evaluate):
    """Return (score, counted_as_physical).

    A genome already in the cache is not a new board evaluation.
    """
    if genome in cache:
        return cache[genome], False
    score = evaluate(genome)
    cache[genome] = score
    return score, True


def flip_attribution(selected, genes):
    """Split a pool from the genes that were actually flipped.

    `selected` is (name, indexes) in the order the sections were admitted.
    A section in the pool that receives no flips is omitted from the flipped
    list and from the per-section counts.
    """
    owner = {}
    selected_names = []
    for name, indexes in selected:
        selected_names.append(name)
        for index in indexes:
            owner[index] = name
    counts = {}
    for gene in genes:
        name = owner[gene]
        counts[name] = counts.get(name, 0) + 1
    flipped = tuple(name for name in selected_names if counts.get(name, 0) > 0)
    per_section = {name: counts[name] for name in flipped}
    return tuple(selected_names), flipped, per_section


@dataclass(frozen=True)
class MutationRecord:
    genes: tuple[int, ...]
    sections_selected: tuple[str, ...]
    sections_flipped: tuple[str, ...]
    genes_flipped_per_section: dict[str, int]


class _Arm:
    def __init__(self, name: str, indexes: tuple[int, ...]):
        self.name = name
        self.indexes = indexes
        self.pulls = 0
        self.reward_sum = 0.0

    @property
    def mean(self) -> float:
        if self.pulls == 0:
            return 0.0
        return self.reward_sum / self.pulls


class MutationBandit:
    """One arm per named section. `updates` is the total of section rewards applied."""

    def __init__(self, sections, n_flips: int, c: float = UCB_C):
        if n_flips < 1:
            raise ValueError("n_flips must be at least 1")
        self.n_flips = n_flips
        self.c = c
        self.updates = 0
        self.arms = []
        self._by_name = {}
        seen = set()
        for section in sections:
            indexes = tuple(section.indexes)
            if not indexes:
                raise ValueError(f"section {section.name} has no genes")
            if section.name in self._by_name:
                raise ValueError(f"duplicate section name {section.name}")
            overlap = seen.intersection(indexes)
            if overlap:
                raise ValueError(f"section {section.name} repeats genes {sorted(overlap)}")
            seen.update(indexes)
            arm = _Arm(section.name, indexes)
            self.arms.append(arm)
            self._by_name[section.name] = arm
        if len(seen) < n_flips:
            raise ValueError(f"sections hold {len(seen)} genes, need {n_flips}")

    def arm(self, name: str) -> _Arm:
        return self._by_name[name]

    def propose(self, rng, n_flips=None) -> MutationRecord:
        """Draw sections until the pool can hold the flip budget, then sample it.

        `n_flips` defaults to the bandit's fixed budget. A fractional budget
        flips that many genes in expectation. A realized count of zero flips
        nothing and selects no section.
        """
        budget = self.n_flips if n_flips is None else n_flips
        count = budget if isinstance(budget, int) else realized_flips(rng, float(budget))
        if count < 1:
            return MutationRecord((), (), (), {})
        remaining = set(range(len(self.arms)))
        selected = []
        pool = []
        while len(pool) < count:
            if not remaining:
                raise RuntimeError(
                    f"selected sections hold {len(pool)} genes, need {count}"
                )
            pick = self._highest(remaining, rng)
            remaining.remove(pick)
            arm = self.arms[pick]
            selected.append((arm.name, arm.indexes))
            pool.extend(arm.indexes)
        genes = tuple(rng.sample(pool, count))
        names, flipped, per_section = flip_attribution(selected, genes)
        return MutationRecord(genes, names, flipped, per_section)

    def observe(self, sections_flipped, reward: int) -> None:
        """Apply one impact reward to each section that received a flip."""
        for name in sections_flipped:
            arm = self._by_name[name]
            arm.pulls += 1
            arm.reward_sum += reward
            self.updates += 1

    def snapshot(self) -> dict:
        """Pulls and rewards only. Section indexes are rebuilt from the tile."""
        return {
            "updates": self.updates,
            "arms": {
                arm.name: {"pulls": arm.pulls, "reward_sum": arm.reward_sum}
                for arm in self.arms
            },
        }

    def restore(self, saved: dict) -> None:
        self.updates = saved["updates"]
        for name, stats in saved["arms"].items():
            arm = self._by_name[name]
            arm.pulls = stats["pulls"]
            arm.reward_sum = stats["reward_sum"]

    def _highest(self, remaining, rng) -> int:
        ranking = []
        for index in remaining:
            arm = self.arms[index]
            if arm.pulls == 0:
                value = math.inf
            else:
                bonus = self.c * math.sqrt(math.log(self.updates) / arm.pulls)
                value = arm.mean + bonus
            ranking.append((value, rng.random(), index))
        ranking.sort(reverse=True)
        return ranking[0][2]
