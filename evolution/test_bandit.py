"""Offline checks for bandit mutation. No board, no bitstream packing."""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.tile_genome import Section, flip_exact, genome_layout
from evolution.bandit import MutationBandit, flip_attribution, impact_reward, lookup_fitness, realized_flips
from evolution.circuits import CIRCUITS
from evolution.run import parser, resolve, rng_from_json, rng_to_json
from evolution.search import adopt_bandit_rate, bandit_child_rates, bandit_next, initial_exact


def _sections(*sizes: int):
    sections = []
    start = 0
    for index, size in enumerate(sizes):
        sections.append(Section(f"s{index}", "lut", tuple(range(start, start + size))))
        start += size
    return tuple(sections), start


def _population(length: int):
    low = tuple(0 for _ in range(length))
    high = tuple(1 for _ in range(length))
    return [low, high], [0.1, 0.9]


def _hamming(a, b) -> int:
    return sum(x != y for x, y in zip(a, b))


def test_impact_reward_pays_only_a_rise():
    up, up_changed = impact_reward(0.25, 0.75)
    down, down_changed = impact_reward(0.75, 0.25)
    same, same_changed = impact_reward(0.5, 0.5)
    assert up == 1 and up_changed
    assert down == 0 and down_changed
    assert same == 0 and same_changed is False

    sections, length = _sections(4, 4)
    pop, scores = _population(length)

    def breed(values, seed):
        stream = iter(values)
        bandit = MutationBandit(sections, n_flips=4)
        _nxt, _carried, logs = bandit_next(
            pop, scores, sections, random.Random(seed), 1.0, 1, 4, bandit,
            score=lambda genome: next(stream),
            physical_evals=lambda: 0,
        )
        return bandit, logs

    risen, risen_logs = breed([0.2, 0.8], 1)
    fallen, fallen_logs = breed([0.8, 0.2], 1)
    assert risen_logs[0]["reward"] == 1
    assert fallen_logs[0]["reward"] == 0
    assert risen_logs[0]["behavior_changed"] is True
    assert fallen_logs[0]["behavior_changed"] is True
    for section in sections:
        if risen.arm(section.name).pulls:
            assert risen.arm(section.name).mean == 1
            assert fallen.arm(section.name).mean == 0

    _held, held_logs = breed([0.5, 0.5], 1)
    assert held_logs[0]["reward"] == 0
    assert held_logs[0]["behavior_changed"] is False


def test_exactly_32_flips_across_more_than_one_section():
    sections, length = _sections(16, 16, 16, 16)
    bandit = MutationBandit(sections, n_flips=32)
    record = bandit.propose(random.Random(0))
    assert len(record.genes) == 32
    assert len(set(record.genes)) == 32
    assert len(record.sections_selected) >= 2
    assert sum(record.genes_flipped_per_section.values()) == 32
    genome = tuple(0 for _ in range(length))
    mutated = flip_exact(genome, record.genes)
    assert _hamming(genome, mutated) == 32


def test_unflipped_section_is_not_updated():
    selected = [("s0", (0, 1)), ("s1", (2, 3, 4)), ("s2", (5,))]
    genes = (0, 1, 5)
    names, flipped, per_section = flip_attribution(selected, genes)
    assert names == ("s0", "s1", "s2")
    assert flipped == ("s0", "s2")
    assert per_section == {"s0": 2, "s2": 1}
    assert "s1" not in per_section

    sections, _length = _sections(2, 3, 1)
    bandit = MutationBandit(sections, n_flips=3)
    bandit.observe(flipped, 1)
    assert bandit.arm("s0").pulls == 1
    assert bandit.arm("s2").pulls == 1
    assert bandit.arm("s1").pulls == 0
    assert bandit.arm("s1").mean == 0.0


def test_elites_are_copied_and_children_flip_exact():
    sections, length = _sections(4, 4)
    pop, scores = _population(length)
    high = pop[1]
    rng = random.Random(2)
    nxt, carried, logs = bandit_next(
        pop, scores, sections, rng, 1.0, 1, 4, None,
        score=lambda genome: 0.3,
        physical_evals=lambda: 0,
    )
    assert nxt[0] is high
    assert carried[high] == 0.9
    assert high == tuple(1 for _ in range(length))
    assert logs == []
    assert _hamming(nxt[1], high) == 4

    calls = []

    def score(genome):
        calls.append(genome)
        return 0.3

    bandit = MutationBandit(sections, n_flips=4)
    nxt, carried, logs = bandit_next(
        pop, scores, sections, random.Random(2), 1.0, 1, 4, bandit,
        score=score,
        physical_evals=lambda: len(calls),
    )
    assert nxt[0] is high
    assert carried[high] == 0.9
    assert calls[0] != calls[1]
    assert nxt[1] == calls[1]
    assert _hamming(calls[1], calls[0]) == 4
    assert logs[0]["crossover_fitness"] == logs[0]["mutated_fitness"] == 0.3
    assert logs[0]["reward"] == 0
    assert sum(logs[0]["genes_flipped_per_section"].values()) == 4
    assert set(logs[0]["sections_flipped"]).issubset(logs[0]["sections_selected"])
    assert logs[0]["physical_evals"] == 2
    for name in logs[0]["sections_selected"]:
        if name not in logs[0]["sections_flipped"]:
            assert name not in logs[0]["genes_flipped_per_section"]
            assert bandit.arm(name).pulls == 0


def test_cache_does_not_count_as_a_physical_eval():
    cache = {}
    calls = []

    def evaluate(genome):
        calls.append(genome)
        return 0.5

    score, physical = lookup_fitness((1, 0), cache, evaluate)
    assert score == 0.5 and physical is True
    score, physical = lookup_fitness((1, 0), cache, evaluate)
    assert score == 0.5 and physical is False
    assert calls == [(1, 0)]


def test_uniform_and_ucb_share_the_initial_population():
    damaged = tuple(0 for _ in range(40))
    first = initial_exact(damaged, 5, random.Random(7), 8)
    second = initial_exact(damaged, 5, random.Random(7), 8)
    assert first == second
    assert first[0] == damaged
    assert _hamming(first[1], damaged) == 8


def test_higher_mean_section_is_preferred_once_both_are_known():
    sections = (
        Section("good", "lut", tuple(range(32))),
        Section("bad", "wire", tuple(range(32, 64))),
    )
    bandit = MutationBandit(sections, n_flips=32)
    bandit.observe(("good",), 1)
    bandit.observe(("bad",), -1)
    record = bandit.propose(random.Random(0))
    assert record.sections_selected == ("good",)
    assert record.sections_flipped == ("good",)

    fresh = MutationBandit(sections, n_flips=32)
    fresh.observe(("good",), 1)
    record = fresh.propose(random.Random(0))
    assert record.sections_selected == ("bad",)


def test_real_sections_need_more_than_one_for_32_flips():
    _positions, sections = genome_layout()
    assert sections
    assert all(len(section.indexes) < 32 for section in sections)
    bandit = MutationBandit(sections, n_flips=32)
    record = bandit.propose(random.Random(0))
    assert len(record.genes) == 32
    assert len(record.sections_selected) >= 2
    assert sum(record.genes_flipped_per_section.values()) == 32


def test_bandit_snapshot_and_rng_roundtrip():
    sections, _length = _sections(8, 8)
    bandit = MutationBandit(sections, n_flips=4)
    bandit.observe(("s0",), 1)
    bandit.observe(("s1",), -1)
    restored = MutationBandit(sections, n_flips=4)
    restored.restore(bandit.snapshot())
    assert restored.updates == bandit.updates == 2
    assert restored.arm("s0").mean == 1
    assert restored.arm("s1").mean == -1

    rng = random.Random(5)
    rng.random()
    copy = random.Random()
    rng_from_json(copy, rng_to_json(rng))
    assert [rng.random() for _ in range(4)] == [copy.random() for _ in range(4)]


def test_uniform_and_ucb_share_circuit_defaults():
    circuit = CIRCUITS["adder2"]
    uniform = resolve(
        parser(None).parse_args(["--circuit", "adder2", "--algorithm", "bandit", "--bandit", "uniform"]),
        circuit,
    )
    ucb = resolve(
        parser(None).parse_args(["--circuit", "adder2", "--algorithm", "bandit"]),
        circuit,
    )
    assert ucb.bandit_mode == "ucb"
    assert uniform.bandit_mode == "uniform"
    assert uniform.expected_flips == ucb.expected_flips == 32
    assert uniform.population == ucb.population == circuit.population
    assert uniform.elites == ucb.elites == 1
    assert uniform.seed == ucb.seed == circuit.seed
    assert uniform.bits == ucb.bits == circuit.bits
    assert uniform.section_share == ucb.section_share


def test_half_flip_is_one_gene_half_the_time():
    sections, _length = _sections(4, 4)
    bandit = MutationBandit(sections, n_flips=4)
    rng = random.Random(0)
    counts = [len(bandit.propose(rng, 0.5).genes) for _ in range(400)]
    assert set(counts) <= {0, 1}
    assert 150 < sum(counts) < 250
    assert realized_flips(random.Random(1), 4) == 4


def test_bandit_rate_shrinks_on_a_tie_and_stays_in_range():
    assert bandit_child_rates(12, 4) == [2.0] * 6 + [8.0] * 6
    assert bandit_child_rates(12, 1) == [1.0] * 6 + [2.0] * 6
    assert bandit_child_rates(12, 32) == [16.0] * 6 + [32.0] * 6
    assert adopt_bandit_rate([2.0, 2.0, 8.0], [0.4, 0.4, 0.4]) == 2.0
    assert adopt_bandit_rate([2.0, 8.0], [0.2, 0.9]) == 8.0
    assert adopt_bandit_rate([1.0, 2.0], [0.5, 0.1]) == 1.0


def main() -> None:
    tests = [
        test_impact_reward_pays_only_a_rise,
        test_exactly_32_flips_across_more_than_one_section,
        test_unflipped_section_is_not_updated,
        test_elites_are_copied_and_children_flip_exact,
        test_cache_does_not_count_as_a_physical_eval,
        test_uniform_and_ucb_share_the_initial_population,
        test_higher_mean_section_is_preferred_once_both_are_known,
        test_real_sections_need_more_than_one_for_32_flips,
        test_bandit_snapshot_and_rng_roundtrip,
        test_uniform_and_ucb_share_circuit_defaults,
        test_half_flip_is_one_gene_half_the_time,
        test_bandit_rate_shrinks_on_a_tie_and_stays_in_range,
    ]
    for test in tests:
        test()
        print(test.__name__)


if __name__ == "__main__":
    main()
