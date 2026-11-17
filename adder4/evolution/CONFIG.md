# 4-bit adder recovery — run configuration

The shared setup is `evolution/CONFIG.md`. This file is the 4-bit adder's defaults. Change one run with flags on `evolution/run.py`. Change the defaults in `evolution/circuits.py`.

The fault is injected first, by flipping N bits that were originally 1. Evolution then reads and writes every bit in the active logic tile: a gene of 1 is a bitstream 1, and a gene of 0 is a bitstream 0. Each candidate is scored on the board.

Two runs: 4 flipped bits, then 8. The 4-bit set is the first 4 of the 8-bit draw (seed 42).

## Search

| Setting | Value |
|---|---|
| Circuit | 4-bit adder, `{cout,s3,s2,s1,s0} = {a3,a2,a1,a0} + {b3,b2,b1,b0}` |
| Seed bitstream | `adder4/build/adder4.asc` |
| Active tile | `logic_tile 17,1` (5 of 8 cells used) |
| Genome | 807 named tile bits. `1` writes 1, `0` writes 0. 57 unnamed bits stay fixed |
| Bits that start as 1 | 97 |
| Fault pool | those 97 ones |
| Fault draw | seed 42, sample 8, take the first N |
| Fault sizes | 4, then 8 |
| Evolution mask | the named bits. Crossover swaps whole LUT, flip-flop, wire, mux, clock, and carry sections |
| Starting population | 1 damaged genome, plus 19 mutants of it |

## Algorithm

| Setting | Value |
|---|---|
| Algorithm | mutation-only genetic algorithm |
| `init_mode` | one damaged tile, then mutants of that tile |
| `population_size` | 20 |
| `generations` | 30, stop earlier if fitness hits 1.0 |
| `target_fitness` | 1.0 |
| `mutation_type` | `SIMPLE` — each tile bit flips on its own |
| `mutation_probability` | `1/807` per bit, after crossover |
| Expected flips per child | about 1 |
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
| Input rows | all 256 sums |
| Repeats | 1 per row |
| Measurements | 256 |
| A row passes | `s0`, `s1`, `s2`, `s3`, and `cout` all match |
| Fitness | correct rows / 256 |
| Known-good check | 256/256 before evolution |

| Signal | FPGA pin | RP GPIO | How it is connected |
|---|---|---|---|
| `a0` | ICE_27 | GPIO20 | on the board |
| `a1` | ICE_26 | GPIO24 | on the board |
| `a2` | ICE_25 | GPIO30 | on the board |
| `a3` | ICE_23 | GPIO25 | on the board |
| `b0` | ICE_9 | GPIO28 | on the board |
| `b1` | ICE_11 | GPIO29 | on the board |
| `b2` | ICE_2 | GPIO2 | jumper, same wire as XOR input A |
| `b3` | ICE_3 | GPIO3 | jumper, same wire as XOR input B |
| `s0` | ICE_20 | GPIO22 | on the board |
| `s1` | ICE_19 | GPIO23 | on the board |
| `s2` | ICE_18 | GPIO27 | on the board |
| `s3` | ICE_21 | GPIO26 | on the board |
| `cout` | ICE_4 | GPIO33 | jumper, same wire as XOR output Y |
