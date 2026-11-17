"""Offline checks for heavy-tailed and two-rate mutation. No board."""

import random
import unittest

from evolution.circuits import CIRCUITS
from evolution.run import Search, command_line
from evolution.search import (
    adopt_tworate,
    clamp_strength,
    heavy_mutate,
    power_law_k,
    tworate_next,
    tworate_split,
)


class PowerLawTest(unittest.TestCase):
    def test_count_stays_inside_the_genome(self):
        rng = random.Random(0)
        for _ in range(500):
            k = power_law_k(rng, 40)
            self.assertGreaterEqual(k, 1)
            self.assertLessEqual(k, 40)

    def test_small_counts_are_more_common(self):
        rng = random.Random(1)
        small = large = 0
        for _ in range(4000):
            k = power_law_k(rng, 100)
            small += k == 1
            large += k >= 20
        self.assertGreater(small, large)

    def test_each_child_reports_the_count_it_drew(self):
        genome = (0,) * 30
        mutated, k = heavy_mutate(genome, random.Random(2))
        self.assertEqual(len(mutated), 30)
        self.assertGreaterEqual(k, 1)
        self.assertLessEqual(k, 30)


class TwoRateTest(unittest.TestCase):
    def test_odd_child_uses_the_lower_rate(self):
        low, high, n_low, n_high = tworate_split(7, 1.0, 807)
        self.assertEqual((low, high, n_low, n_high), (0.5, 2.0, 4, 3))

    def test_high_rate_cannot_exceed_the_genome(self):
        _low, high, _n_low, _n_high = tworate_split(4, 500.0, 807)
        self.assertEqual(high, 807.0)

    def test_winner_sets_the_next_rate_and_a_tie_stays_high(self):
        n = 100
        self.assertEqual(adopt_tworate([0.5, 0.5, 2.0], [0.2, 0.3, 0.9], n), 2.0)
        self.assertEqual(adopt_tworate([0.5, 2.0], [0.4, 0.4], n), 2.0)
        self.assertEqual(adopt_tworate([0.5, 2.0], [0.8, 0.1], n), 1.0)
        self.assertEqual(clamp_strength(807, 807), 403.5)

    def test_children_split_and_elites_are_copied(self):
        pop = [tuple(int(i == bit) for i in range(10)) for bit in range(10)]
        scores = [0.1 * i for i in range(10)]
        _nxt, carried, strengths = tworate_next(
            pop, scores, [], random.Random(3), 4.0, 0.5, 3
        )
        self.assertEqual(strengths, [2.0, 2.0, 2.0, 2.0, 8.0, 8.0, 8.0])
        self.assertEqual(len(carried), 3)
        self.assertIn(pop[9], carried)


class CommandTest(unittest.TestCase):
    def test_fixed_rate_command_is_unchanged(self):
        search = Search("ea", 4, 10, 25, 3, 1, 0.5, 42, "improve")
        self.assertNotIn("--mutation", command_line(CIRCUITS["xor"], search))

    def test_new_modes_are_recorded(self):
        search = Search("ea", 4, 10, 25, 3, 1, 0.5, 42, "improve", mutation="heavy")
        self.assertIn("--mutation heavy", command_line(CIRCUITS["xor"], search))


if __name__ == "__main__":
    unittest.main()
