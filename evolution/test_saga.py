"""Offline checks for the SAGA schedule, elite rule, and recorded movement."""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolution.circuits import CIRCUITS
from evolution.run import check, command_line, output_dir, parser, resolve
from evolution.saga import (
    SAGA_BASE_FLIPS,
    SAGA_BOTTOM,
    SAGA_MAX_FLIPS,
    assign_rates,
    choose_elite,
    drift_record,
    initial_population,
    saga_flips,
    saga_next,
    stops_at_perfect,
    tie_fraction,
    update_stall,
)


def test_schedule_ramps_and_holds():
    assert [saga_flips(stall) for stall in range(3)] == [2, 2, 2]
    assert [saga_flips(stall) for stall in (3, 4, 5)] == [6, 6, 6]
    assert saga_flips(6) == 10
    assert saga_flips(21) == 30
    assert saga_flips(24) == 34
    assert saga_flips(25) == SAGA_MAX_FLIPS
    assert saga_flips(100) == 34
    levels = []
    for stall in range(0, 40):
        level = saga_flips(stall)
        if not levels or level != levels[-1]:
            levels.append(level)
    assert levels == [2, 6, 10, 14, 18, 22, 26, 30, 34]


def test_stall_resets_only_on_a_strict_gain():
    assert update_stall(None, 0.25, 4) == 0
    assert update_stall(0.25, 0.5, 4) == 0
    assert update_stall(0.5, 0.5, 4) == 5
    assert update_stall(0.5, 0.25, 4) == 5


def test_elite_rule():
    elite = (0, 0)
    copy = (0, 0)
    other = (1, 0)
    better = (1, 1)
    chosen, outcome = choose_elite(elite, 0.5, [copy, other], [0.5, 0.4], random.Random(0))
    assert chosen == elite and outcome == "kept"
    chosen, outcome = choose_elite(elite, 0.5, [copy, other], [0.5, 0.5], random.Random(0))
    assert chosen == other and outcome == "drifted"
    chosen, outcome = choose_elite(elite, 0.5, [other, better, better], [0.6, 0.7, 0.7], random.Random(1))
    assert chosen == better and outcome == "improved"


def test_initial_population_is_six_copies_and_fifteen_mutants():
    damaged = tuple(0 for _ in range(20))
    pop, strengths = initial_population(damaged, random.Random(0))
    assert len(pop) == 21
    assert pop[:6] == [damaged] * 6
    assert strengths == [0] * 6 + [4] * 15


def test_bottom_seven_get_the_stalled_rate():
    means = [0.9, 0.1, 0.4, 0.2, 0.8, 0.3, 0.7, 0.05, 0.6, 0.5]
    rates = assign_rates(means, 10, 2, 7)
    lowest = sorted(range(len(means)), key=lambda i: (means[i], i))[:7]
    assert {i for i, rate in enumerate(rates) if rate == 10} == set(lowest)
    assert rates.count(2) == 3
    assert assign_rates([0.2, 0.2, 0.2], 6, 2, 2) == [6, 6, 2]


def test_children_are_mutated_once_and_the_elite_is_copied():
    sections = []
    pop = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
    scores = [0.9, 0.2, 0.1]
    nxt, carried, rates = saga_next(pop, scores, random.Random(2), sections, 0.5, 10, 2, n_bottom=1)
    assert nxt[0] == pop[0]
    assert carried == {pop[0]: 0.9}
    assert len(nxt) == 3
    assert rates.count(10) == 1
    assert rates.count(2) == 1


def test_drift_uses_the_elite_at_the_front():
    past = [["000", "111"]]
    current = ["110", "100"]
    record = drift_record(past, current, window=10)
    assert record["elite_drift_from_start"] == 2
    assert record["drift_lag"] == 1
    assert record["consensus_drift_from_start"] == 1
    assert drift_record([], current)["elite_drift"] == 0
    assert tie_fraction([0.5, 0.5, 0.4, 0.5]) == 2 / 3


def test_a_perfect_score_does_not_stop_saga():
    assert stops_at_perfect("saga") is False
    assert stops_at_perfect("ea") is True


def test_prepared_run_matches_the_requested_settings():
    circuit = CIRCUITS["adder2"]
    search = resolve(parser(None).parse_args(["--circuit", "adder2", "--algorithm", "saga"]), circuit)
    check(search)
    command = command_line(circuit, search)
    assert search.population == 21
    assert search.elites == 1
    assert search.generations == 300
    assert search.seed == 13
    assert search.seed not in (7, 42)
    assert search.expected_flips == SAGA_BASE_FLIPS
    assert search.section_share == 0.5
    assert search.bits == 4
    assert "--bandit" not in command
    assert "--mutation" not in command
    assert command == (
        "python evolution/run.py --circuit adder2 --algorithm saga --bits 4 "
        "--generations 300 --expected-flips 2 --seed 13 --population 21 --elites 1 "
        "--section-share 0.5"
    )
    assert output_dir(circuit, search).name == "saga_4bit_g300_m2_p21_e1_seed13"
    assert SAGA_BOTTOM == 7


def main() -> None:
    tests = [
        test_schedule_ramps_and_holds,
        test_stall_resets_only_on_a_strict_gain,
        test_elite_rule,
        test_initial_population_is_six_copies_and_fifteen_mutants,
        test_bottom_seven_get_the_stalled_rate,
        test_children_are_mutated_once_and_the_elite_is_copied,
        test_drift_uses_the_elite_at_the_front,
        test_a_perfect_score_does_not_stop_saga,
        test_prepared_run_matches_the_requested_settings,
    ]
    for test in tests:
        test()
        print(test.__name__)


if __name__ == "__main__":
    main()
