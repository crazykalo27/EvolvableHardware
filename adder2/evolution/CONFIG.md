# 2-bit adder recovery — run configuration

The shared setup is `evolution/CONFIG.md`. This file is the 2-bit adder's current defaults. Change one run with flags on `evolution/run.py`. Change the defaults in `evolution/circuits.py`.

Two runs: 4 flipped bits, then 8. The 4-bit set is the first 4 of the 8-bit draw (seed 42).

## Search

| Setting | Value |
|---|---|
| Circuit | 2-bit adder, `{cout,s1,s0} = {a1,a0} + {b1,b0}` |
| Seed bitstream | `adder2/build/adder2.asc` |
| Active tile | `logic_tile 20,20` (3 of 8 cells used) |
| Genome | 807 named tile bits. `1` writes 1, `0` writes 0. 57 unnamed bits stay fixed |
| Bits that start as 1 | 61 |
| Fault pool | those 61 ones |
| Fault draw | seed 42, sample 8, then take the first N |
| Fault sizes | 4, then 8 |
| Evolution mask | the named bits. Crossover swaps whole LUT, flip-flop, wire, mux, clock, and carry sections |
| Starting population | 1 damaged genome, plus 22 mutants of it |

## Algorithm

| Setting | Value |
|---|---|
| Algorithm | genetic algorithm with section crossover |
| `init_mode` | one damaged tile, then mutants of that tile |
| `population_size` | 23 |
| `generations` | 100, stop earlier if fitness hits 1.0 |
| `target_fitness` | 1.0 |
| `mutation_type` | `SIMPLE` — each gene flips on its own, so the count varies around the expected value |
| `mutation_probability` | `4/807` per bit, after crossover |
| Expected flips per child | 4 |
| `crossover` | two fitness-chosen parents. Each section from the fitter parent with probability 0.5 |
| `elitism_count` | 3, not rescored |
| `selection` | `FIT_PROP_SEL` |
| `diversity_measure` | Hamming distance |
| Diversity logged | mean pairwise Hamming, and best vs the original genome |
| `random_injection` | 0 |
| `randomize_until` | `NO` |

## Fitness and hardware

| Setting | Value |
|---|---|
| Where it is scored | the pico2-ice, over `mpremote` |
| Not used | the toolkit `FULLY_INTRINSIC` loader |
| Input rows | all 16 sums |
| Repeats | 1 per row |
| Measurements | 16 |
| A row passes | `s0`, `s1`, and `cout` all match |
| Fitness | correct rows / 16 |
| Pins | shared RP-ICE bank, no jumpers |

| Signal | FPGA pin | RP GPIO |
|---|---|---|
| `a0` | ICE_27 | GPIO20 |
| `a1` | ICE_26 | GPIO24 |
| `b0` | ICE_25 | GPIO30 |
| `b1` | ICE_23 | GPIO25 |
| `s0` | ICE_20 | GPIO22 |
| `s1` | ICE_19 | GPIO23 |
| `cout` | ICE_18 | GPIO27 |
