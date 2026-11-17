# Choosing a run

One command runs any circuit with either search. Unset flags use the defaults below. The output `recovery.json` starts with the exact command that produced it.

```
python evolution/run.py --list
python evolution/run.py --circuit adder2 --algorithm ea --bits 4
python evolution/run.py --circuit adder2 --algorithm hill --bits 4 --generations 2000 --expected-flips 1 --accept neutral
```

`--circuit`, `--algorithm`, and `--score` are the three swaps. The other flags are the parameters.

## Circuits and fitness

The fitness script runs on the board. It prints `RESULT,<name>,<matches>,<total>,<fraction>`. Fitness is matches / total. A different fitness is another script passed with `--score`.

| Circuit | Tile | Fitness | Script | EA defaults |
|---|---|---|---|---|
| `xor` | 8,1 | correct measurements / 20. 4 patterns, 5 repeats | `xor/board/truth_table_score.py` | population 10, 30 generations, 3 elites, 1 expected flip |
| `adder2` | 20,20 | correct rows / 16. `s0`, `s1`, and `cout`, one pass | `adder2/board/adder_score.py` | population 23, 100 generations, 3 elites, 4 expected flips |

`adder2/board/adder_bit_score.py` counts each output bit, so the score is correct bits / 48. Pass it with `--score`. `--section-share 0.7` copies each section from the fitter parent with probability 0.7.
| `adder4` | 17,1 | correct rows / 256. `s0` through `s3` and `cout`, one pass | `adder4/board/adder4_score.py` | population 20, 30 generations, 3 elites, 1 expected flip |

All three use the 807 named bits of that one tile. The 57 unnamed bits stay fixed. The fault is seed 42: sample 8 of the original 1s, then flip the first N. The evolution seed is 43.

## Algorithms

| Algorithm | What a step does |
|---|---|
| `ea` | Keep the top `--elites`. Fill the rest with children. Each child has two fitness-proportional parents. Each section comes from the fitter parent with probability `--section-share` (default 0.5). Then each gene flips with probability `--expected-flips` / 807. Elites are not mutated and not scored again. `--mutation heavy` draws a flip count from a power law (beta 1.5) instead of using one rate. `--mutation tworate` splits the children between half the current rate and double it, then keeps the rate whose children scored higher. A tie keeps the higher rate. That rate starts at `--expected-flips` and stays between 1 and N/2. |
| `inchworm` | The EA loop with population 20, 5 elites, and base mutation 1/N. After 5 generations at the same best score, the 5 children whose parents have the lowest average score mutate at 5/N. Every 3 further generations at that score adds 4/N, up to 40/N. A higher best score returns every child to 1/N. |
| `hill` | Each genome climbs alone. `--population 1` starts from the damaged circuit. A larger population starts as that circuit plus mutants of it, and each one is mutated and kept on its own. `--accept neutral` keeps a mutant when its fitness is at least as high. `--accept improve` keeps it only when the fitness is higher. No crossover. |
| `bandit` | The EA loop: same elites, same fitness-proportional parents, same named-section crossover. Each child then flips an exact number of genes, 32 unless `--expected-flips` says otherwise. `--bandit uniform` draws those genes from the whole genome. `--bandit ucb` (the default) keeps drawing named sections until they hold that many genes, then flips inside that pool. `--mutation tworate` starts at `--expected-flips` and gives half the children half that count and half double it. A tie keeps the lower count. The count stays between 1 and 32. A bandit run keeps 1 elite unless `--elites` says otherwise. |
| `saga` | Population 21 and 1 elite on the 2-bit adder, fault seed 13, 300 generations. Generation 0 is 6 copies of the damaged genome and 15 mutants at 4/N. Section crossover stays an even split. A strict gain replaces the elite and returns the child rate to 2/N. A different genome with the same score can replace the elite and does not reset the rate. The 7 children with the weakest parents step 2, 6, 10, ... 34, first at stall 3 and then every 3 generations, holding at 34. The other 13 stay at 2/N. A perfect score does not stop the run. Each generation records the population, elite drift, centroid drift, cluster width, and the share of children that tie the elite. |

For `ucb`, the board scores the crossover child and then the mutant. Every section that actually received a flip gets +1 only when the mutant scores higher. A lower score and an equal score both pay 0. That visit still counts, so the exploration term is what moves the search to another section. Parent selection and elitism use the mutant's fitness and do not read the reward.

That comparison is a proxy. The search stores `matches / total`, not the measured output on each row. A mutation that changes the outputs but keeps the same number of correct rows is treated as no change. `recovery.json` records this as `impact_basis: "fitness_proxy"`.

`ucb` spends one extra evaluation on the crossover child whenever that genome is not already cached. A cached genome does not add to `physical_evals`. Compare `uniform` and `ucb` on the same circuit, fault mask, seed, and initial population, and read best fitness against `physical_evals` (`fitness_vs_evals.png`). The two modes share that initial population: the damaged genome plus mutants that each flip the same exact count, 32 unless `--expected-flips` is set.

Each finished generation is written to `recovery.json` and `checkpoint.json` before the next generation is bred. The history row holds every genome in that generation and its score, in the same order, so the population can be rebuilt after a stop. A board evaluation updates the checkpoint too, so a disconnect does not repeat scores that already came back. The generation in progress is resumed from the checkpoint; its grouped population appears in the history once scoring finishes. Starting the same command again continues from the checkpoint. One serial session stays open for the run. Deleting the previous bitstream, copying the next one, and scoring it all use that session. Other board files are cleared each generation. The score script stays on the board. The results stay on the host.

`--generations` is the number of steps after the initial score. A run stops at fitness 1, except `saga`, which keeps going so a perfect score can still drift. After a SAGA run stops, `analysis/plot_saga.py` on its `recovery.json` writes the fitness, Hamming, and species-traversal plots from whatever generations were saved.

Changing a default for every future run of a circuit is a one-line edit in `evolution/circuits.py`. Changing it for one run is a flag, and the flag is what gets recorded.
