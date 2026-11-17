# Evolution parameters

Settings live in a BitstreamEvolution `.ini` file. A run loads that file through `src/evolve.py --config <file>`. Missing keys are filled from `base_config`, then `data/default_config.ini`.

The toolkit itself may flip bits in every logic tile. Our runs will not. Mutation is limited to a rectangle of tiles, set in `xor/evolution/xor_area.ini` and read by `xor/evolution/tile_area.py`.

XOR truth-table fitness is not one of the built-in functions. The table below says how fitness is selected, and what we still have to add for XOR.

## Tile area

| Parameter | What it controls | Current value |
|---|---|---|
| `origin_x`, `origin_y` | Bottom-left logic tile of the allowed rectangle | 7, 1 |
| `width`, `height` | Size of that rectangle, in tiles | 5 × 5 |

That window is x = 7..11 and y = 1..5: **25 logic tiles**, including the XOR LUT at `logic_tile 8,1`. Column 6 is empty, so the rectangle starts at 7 instead of 6. Tiles outside it are not mutated. IO tiles (y = 0) are outside it, so pins A, B, and Y stay fixed.

Change the four numbers to move or resize the area. A window that covers column 6 or 19 simply has no tile there.

## Search space inside those tiles

| Parameter | Section | What it controls | Values | XOR note |
|---|---|---|---|---|
| `routing` | HARDWARE | Which rows inside each allowed tile may change | `MOORE` rows 1, 2, 13; `NEWSE` rows 1, 2; `ALL` rows 1–16 | Applied only inside the rectangle. Keep routing fixed for the first runs. |
| `accessed_columns` | HARDWARE | Which bit-columns in those rows may flip | Comma-separated column numbers, about 0–53 | Fault tests so far only used the 17 set bits in tile 8,1. |
| `configurable_io` | HARDWARE | Whether IO tiles can be rewritten | `true` / `false` | Leave `false`. |
| `input_pins` / `output_pins` | HARDWARE | Pins the toolkit’s own IO setup uses | Pin number lists | Our board uses GPIO2, GPIO3, GPIO33, not these defaults. |

## Fitness

Set the name in the ini. The code that reads it is `Config.get_fitness_func()`, and `CircuitPopulation` builds the matching class.

```ini
[FITNESS PARAMETERS]
fitness_func = TOLERANT_PULSE_COUNT
```

| `fitness_func` | Scores | Extra keys | Fits XOR? |
|---|---|---|---|
| `VARIANCE` | How much a waveform wiggles | none | No. This is the toolkit’s hello-world. |
| `TOLERANT_PULSE_COUNT` | Closeness to a target frequency, gentle slope | `desired_freq` (Hz) | No |
| `SENSITIVE_PULSE_COUNT` | Same, steep drop-off | `desired_freq` | No |
| `PULSE_CONSISTENCY` | Pulse count agrees across passes | `num_passes` > 1 | No |
| `COMBINED` | Mix of pulse and variance | `combined_mode` `ADD` or `MULT`, `pulse_weight`, `var_weight` | No |
| `TONE_DISCRIMINATOR` | High/low answer to two input tones | none | No |
| `XOR_TRUTH_TABLE` | Fraction of the 4 input rows correct | not implemented | This is the one we need. |

To add XOR fitness: a new class with the same interface as `src/Circuit/FitnessFunction.py` (`get_measurements`, `calculate_fitness`), a new allowed name in `Config.get_fitness_func()`, and a branch in `CircuitPopulation.__construct_circuit`. Score is the same number we already measure: matches / 20 on patterns 00, 01, 10, 11. Full recovery is 1.0.

`num_samples` and `num_passes` repeat a measurement and keep the worst score. For XOR, one pass of the 4 patterns × 5 repeats is enough.

## Population and search

| Parameter | Section | What it controls | Typical | XOR start |
|---|---|---|---|---|
| `population_size` | GA | Circuits alive each generation | 10–50 | 10 |
| `generations` | STOPPING | Stop after this many generations, or `IGNORE` | 50–500 | 30 |
| `target_fitness` | STOPPING | Stop when any circuit reaches this, or `IGNORE` | `IGNORE` | `1.0` |
| `mutation_probability` | GA | Chance each allowed bit flips | `0.0021` | Higher if only ~17 bits are allowed, otherwise almost nothing flips |
| `mutation_type` | GA | How that chance is scaled | `SIMPLE`, `RANK`, `PROPORTIONAL`, `CONVERGENCE` | `SIMPLE` |
| `crossover_probability` | GA | Chance a non-elite is crossed with a parent | 0.1–0.7 | `0.0` until mutation-only recovery is understood |
| `elitism_fraction` | GA | Fraction kept unchanged | `0.1` | `0.1` |
| `selection` | GA | Who gets mutated | `SINGLE_ELITE`, `FRAC_ELITE`, `CLASSIC_TOURN`, `FIT_PROP_SEL`, `RANK_PROP_SEL`, `MAP_ELITES` | `FIT_PROP_SEL` |
| `diversity_measure` | GA | Logged diversity, not the score | `NONE`, `UNIQUE`, `HAMMING_DIST` | `HAMMING_DIST` |
| `random_injection` | GA | Chance to insert a fresh random circuit | 0–0.15 | `0` |
| `chaos_injection` | GA | Extra mutation after 5 generations with no improvement | `0` or about `5` | `0` |

## Where the first generation comes from

| Parameter | What it controls | Values | XOR start |
|---|---|---|---|
| `init_mode` | How the population is created | `CLONE_SEED`, `CLONE_SEED_MUTATE`, `RANDOM`, `EXISTING_POPULATION` | `CLONE_SEED` of the damaged XOR, then inject the fault ourselves |
| `seed` | ASC file that clone modes copy | Path to an `.asc` | `xor/build/xor.asc` after the fault flips |
| `randomize_until` | Keep randomizing until a fitness bar is hit | `NO`, `PULSE`, `VARIANCE` | `NO` |
| `randomize_mode` | How that pre-search edits bits | `RANDOM`, `MUTATE` | unused if `randomize_until = NO` |
| `randomize_threshold` | Fitness bar for that pre-search | number | unused |

`RANDOM` throws away the XOR and fills every allowed bit at random. That is the “evolve from scratch” baseline in the proposal, not the recovery start.

## How a run is executed

| Parameter | What it controls | Values | XOR note |
|---|---|---|---|
| `simulation_mode` | Where fitness is measured | `FULLY_INTRINSIC` on hardware, `SIM_HARDWARE` compiles but scores on the host, `FULLY_SIM` fake waveforms, `REMOTE` via iCEFARM | `FULLY_INTRINSIC` once the XOR scorer is hooked up. `SIM_HARDWARE` does not know the truth table. |
| `usb_path` | Serial device | `/dev/ttyACM0` in the sample ini | Our board is `/dev/cu.usbmodem1101` and we load with `mpremote`, not this serial path. |

## Fault severity (our experiment, not an ini key)

The proposal’s severity levels are 1, 2, 4, and 8 flipped bits in the LUT, then evolution tries to get back to fitness 1.0. The 4-seed baseline already measured the damage before any evolution:

| Flips | Mean accuracy | Full pass |
|---|---|---|
| 0 | 100% | 100% |
| 1 | 81% | 50% |
| 2, 4, 8 | 50% | 0% |
