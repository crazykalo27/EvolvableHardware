# PicoIceProj status log

## 2026-11-17 — Repository

- The project is a git repository on `main`, with the remote at github.com/crazykalo27/EvolvableHardware. The virtual environment, workspace copies, logs, and the matplotlib font cache stay out. The Pico2-ICE vendor checkout is recorded as a submodule.

## 2026-11-16 — Gain against generations

- `report/figures/fitness_gain.png` puts the open-tile runs on one scale, the share of a perfect score. The closed masks and the 97-bit run are left out. The left panel is fitness gained from generation 0. The right panel is wider. Generations 0–40 are stretched, and the axis compresses after 40. The line slopes up to the generation the best score first appeared, then a horizontal bar for the generations it stayed there. The generation-300 SAGA log is not a second point.

## 2026-11-16 — SAGA sheets

- `report/figures/saga_row_sheet.png` is the row-scored SAGA run, generations 0–444. The generation-300 log is the first part of this same search. `saga_bit_sheet.png` is the separate bit-scored run, stopped at generation 210 of 300. `saga_overlay_sheet.png` puts both on the same axes. The dotted line at generation 300 is where the first log ends.

## 2026-11-16 — UCB comparison charts

- `report/figures/ucb_choice.png` is back to the first coloring. Gold is a flipped section whose own average is larger than its own bonus. Blue is a first visit, or a bonus at least as large as the average. Best and mean fitness are on the inner right axis. The flip count used for that generation is the purple line on the outer right axis.
- `report/figures/ucb_section_scores.png` is every visited section at the start, the middle, and the end of each run. Each column is one run, read from top to bottom. Gold is the average reward, blue is the exploration bonus stacked on it, highest score on the left. Unvisited sections are left out and counted in the title.
- `report/figures/ucb_fitness.png` is best and mean fitness for the three UCB runs. `ucb_rise_fall.png` adds the mean change and its straight fit. `ucb_sections.png` puts the most revisited sections on one visit scale, so a section UCB 1 flipped about 700 times is that long and the other runs stay near 20. `bandit_genotype.png` is the champion and the mean pairwise distance on one chart.

## 2026-11-16 — Placed adders, and six champion circuits

- `report/figures/adders_side_by_side.png` is the placed 2-bit adder and the placed 4-bit adder, from the spatial viewer.
- `report/figures/champion_circuits.png` is six best circuits, two across and three down: section crossover, inchworm, five hill climbers, the large-step 2-bit run, SAGA at generation 444, and the 32-flip XOR. Same viewer. The runs are not a comparison.

## 2026-11-16 — Named-bit fitness and Hamming charts

- `report/figures/named_bit_fitness.png` and `named_bit_hamming.png` are the four 807-bit runs: section crossover, one hill climber, five hill climbers, and inchworm. Same best and mean lines as the full-tile pair, a little wider and a little shorter.

## 2026-11-16 — Full-open fitness and Hamming as two tall charts

- The wide sheet is split. `report/figures/full_open_fitness.png` is the scores. `report/figures/full_open_hamming.png` is the distances. Each is a little wider than tall, about a third of a page.

## 2026-11-16 — Search-space graph for 4, 8, and 864 bits

- `report/figures/search_space.png` compares the closed masks, 16 and 256 genomes, with the full tile, \(2^{864}\). The axis is the number of doublings.

## 2026-11-16 — Full-open sheet for the two 864-bit runs

- `report/figures/full_open_sheet.png` is the 2-bit adder with every bit of tile (20, 20) free. Large step against one flip. Same fault and the same row score. The curves are the best score, the champion's distance, and the population spread.

## 2026-11-16 — Named-bit sheet for the four 807-bit runs

- `report/figures/named_bit_sheet.png` is the 2-bit adder on the 807 named bits: section crossover, one hill climber, five hill climbers, and inchworm. Same fault, same fitness. The curves are the best score, the champion's distance, and the population spread.

## 2026-11-16 — Open-mask sheet for the 97-bit run

- `report/figures/open_mask_sheet.png` is the 4-bit adder run whose genome was the 97 bits that start as 1. Generations 14–19 are the ones that were saved. The best stayed at 0.50 and 4 bits from the original.

## 2026-11-16 — XOR setup sheet

- `report/figures/xor_setup_sheet.png` is a wide sheet with three short rows: the placed XOR, the live 80/80 trace, then the fault-baseline accuracy and full-pass charts. The circuit picture comes from `viz/show_circuit.py`. The live window was not saved, so the trace is the recorded passing run: 20 cycles of the four patterns, measured Y on the expected line. The baseline is the four-seed sweep already in `fault_baseline_results.json`.

## 2026-11-16 — Row-scored SAGA stopped at generation 444; bit-scored run started

- The continuation toward 500 was stopped during generation 445. Saved history runs through generation 444, best fitness 0.688, in `adder2/evolution/out/saga_4bit_g500_m2_p21_e1_seed13/`. Its traversal and cloud plots are in that folder.
- The new 300-generation run scores each output bit out of 48 and copies each section from the fitter parent with probability 0.7. Same fault seed 13. Output is `adder2/evolution/out/saga_4bit_g300_m2_p21_e1_s70_seed13_adder_bit_score/`.

## 2026-11-16 — Drift, Hamming distance, and fitness in one view

- `cloud_drift.png` puts each genome's distance from the generation-0 elite on x, its distance from that generation's elite on y, and its fitness on z. Color is the generation. The file is in the same cloud folder.

## 2026-11-15 — SAGA population cloud from each generation's own distances

- `analysis/plot_cloud.py` reads the genomes already stored in the 300-generation log. Each generation gets its own cross-section, rescaled so the width is in bits. Distance from the start stays exact Hamming. Plots are in `adder2/evolution/out/saga_4bit_g300_m2_p21_e1_seed13/cloud/`.

## 2026-11-15 — SAGA landscape plots from the finished 300 generations

- The 300-generation log already held every genome. `analysis/plot_landscape.py` draws the population cloud, the elite path, and the centroid in one shared genotype projection. `landscape_time.png` puts fitness, PC1, PC2, and cloud width on one generation axis. Plots are in `adder2/evolution/out/saga_4bit_g300_m2_p21_e1_seed13/landscape/`.

## 2026-11-15 — SAGA continued from generation 300 toward 500

- Generation 300 finished at fitness 0.688. Its plots stay in `adder2/evolution/out/saga_4bit_g300_m2_p21_e1_seed13/`.
- The same population, stall, and random state are now running toward generation 500 in `adder2/evolution/out/saga_4bit_g500_m2_p21_e1_seed13/`. Generation 300 was not scored again.

## 2026-11-15 — Report exported to Word for Google Docs

- `report/report.docx` is the report with the figures embedded, for upload to Google Drive and opening as a Google Doc.

## 2026-11-14 — Final report reframed around the search, not recovery success

- The Google Doc export is kept at `report/source/proposal-export.md`. The working report is the file that used to hold that export.
- The report asks which strategy climbs once the logic tile is open, how many rows come back before the score stalls, and what the genome does during that stall.
- Each experiment group now has one overlaid fitness figure, from `analysis/plot_report.py`, and the analysis under each group is left open.

## 2026-11-14 — SAGA run started

- The 300-generation adder SAGA run is going, population 21, one elite, fault seed 13. The damaged start scored 0.188. It is under `caffeinate -is`, so the display can sleep and the search keeps running.
- Output is `adder2/evolution/out/saga_4bit_g300_m2_p21_e1_seed13/`.

## 2026-11-14 — SAGA run prepared, not started

- The next adder search is population 21, one drifting elite, 300 generations, and fault seed 13. Generation 0 is 6 copies of the damaged circuit and 15 mutants at 4/N.
- Children use the inchworm rate from 2/N to 34/N. A tie can replace the elite without counting as progress. A perfect score does not stop the run. Each finished generation stores the population and how far the cluster has moved.

## 2026-11-14 — Seed-7 adder UCB stopped at generation 137

- The 200-generation adder UCB run was stopped during generation 138. Best fitness was 0.625 from generation 34. The flip count was 1. The checkpoint is still resumable.
- Plots are in `adder2/evolution/out/bandit_4bit_g200_m4_p15_e1_ucb_tworate_seed7/`.

## 2026-11-14 — Finished generations keep the whole population

- From the next run on, each scored generation stores every genome and its score in `recovery.json` and `checkpoint.json` before the next generation starts.
- The adder run already in progress keeps the history it started with.

## 2026-11-14 — 200-generation adder UCB started on a new fault

- The 2-bit adder UCB run is population 15, 1 elite, 200 generations, flip count starting at 4 and staying between 1 and 32. A rise scores +1. A drop and an unchanged score pay 0.
- Fault seed 7, instead of 42. The four cleared bits are genome indexes 74, 128, 139, and 236. Output is `adder2/evolution/out/bandit_4bit_g200_m4_p15_e1_ucb_tworate_seed7/`.

## 2026-11-14 — A rise is the only section reward

- A flipped section scores +1 only when fitness rises. A drop and an unchanged score pay 0, and the visit still counts.
- The bandit copies one elite, and the adaptive flip count stays at or above one flip.

## 2026-11-13 — Shrinking-flip UCB stopped at generation 70

- The 2-bit adder UCB run with the directional reward and the shrinking flip count was stopped at generation 70. Best fitness was 0.375 from generation 3. The flip count had been 0.5 since generation 7.
- Plots are in `adder2/evolution/out/bandit_4bit_g100_m4_p15_e3_ucb_tworate/`. `fitness_diversity.png` stacks best and mean fitness above Hamming distance. `ucb_sheet.png` explains the half-or-double flip count and the +1 / 0 / −1 reward, then shows which sections were flipped.

## 2026-11-13 — Adder UCB with a shrinking flip count

- A flipped section now scores +1 when fitness rises, 0 when it falls, and -1 when the score is unchanged. A drop still counts as a visit.
- The 2-bit adder UCB run uses population 15, 3 elites, and 100 generations. The flip count starts at 4. Half the children use half of it and half use double, a tie keeps the lower count, and the count stays between 0.5 and 32.

## 2026-11-13 — Diversity measured apart from the fitness curves

- On the XOR flip sweep, late pairwise Hamming rises by about 4.8 bits per expected flip from 1 through 32 flips. At 64 flips the population is less spread than that line. The power-law run, whose draws averaged 13 flips, ended nearer the diversity of a 4-flip run.
- After the best score stopped rising, elitist runs kept that champion at a fixed distance from the original. Population Hamming could still grow or shrink. The two hill climbers are the runs where the champion itself kept drifting.
- The adder UCB run had flipped every named section by generation 3. Pairwise Hamming then fell from about 134 to about 51.

## 2026-11-13 — XOR strategy charts include the variable rates

- `analysis/xor_best_fitness.png` and `analysis/xor_diversity.png` now include the power-law and half-or-double runs beside the five fixed flip counts. `analysis/xor_sheet.png` stacks best fitness above pairwise Hamming distance.

## 2026-11-13 — XOR variable-rate runs finished

- Both 25-generation XOR runs finished. The power-law run stayed at 10/20, same as the 1, 4, 16, and 64 flip baselines. The half-or-double run reached 12/20 at generation 4, then the rate climbed to the cap and the score stayed there. The 32-flip baseline still ended highest, at 13/20.

## 2026-11-13 — XOR EA with two variable mutation rates

- The plain EA can now draw each child's flip count from a power law (beta 1.5), or split each generation between half the current rate and double it and keep the rate whose children scored higher. A tie keeps the higher rate.
- The two XOR runs use the same 25-generation, population-10, 3-elite, 4-bit settings as the fixed-rate baselines. The half-or-double run starts at one expected flip. The bandit reward is unchanged.

## 2026-11-13 — One serial session for each board check

- A run keeps one raw-REPL connection open. Deleting the old bitstream, copying the next one, and scoring it happen on that connection. A dropped port opens the session again.

## 2026-11-13 — Adder UCB run stopped at generation 102

- The 2-bit adder UCB run (population 15, 3 elites, 32 flips) was stopped at generation 102. Best fitness was 0.375 from generation 12 on. The checkpoint is still resumable.
- Plots are in `adder2/evolution/out/bandit_4bit_g200_m32_p15_e3_ucb/`. `fitness_diversity.png` stacks best and mean fitness above Hamming distance. `ucb_sheet.png` opens with how UCB picks the 32 flips, then what the highlighted sections configure. The heatmap counts how many of the 12 children flipped each section. The rise-or-fall chart also shows the average fitness change of those children and a straight fit through it. A heatmap shows how many of the 12 children flipped each section. The section bars are sized by genes flipped, with the names inside the chart.

## 2026-11-13 — Runs can continue after a disconnect

- Each generation is saved on the host in `recovery.json` and `checkpoint.json`. Scores already returned by the board are kept, so a restart continues instead of repeating them.
- The board only holds the score script and the bitstream being tested. The previous bitstream is removed before the next copy, and the rest of the board filesystem is cleared each generation.

## 2026-11-13 — Bandit mutation on named sections

- `bandit` keeps elitism, fitness-based parent selection, and named-section crossover, then flips an exact number of genes (default 32).
- `uniform` flips anywhere in the genome. `ucb` draws named sections until they can hold those flips, and updates only the sections that received a flip.
- The bandit reward is whether the mutant's fitness differs from the crossover child. A worse score and a better score are the same reward. Who survives is still decided by fitness.
- The search does not see the output vector, so that comparison is a match-count proxy. The same number of correct rows counts as no change.
- `ucb` evaluates the crossover child as well. When that genome is not cached, it costs an extra board evaluation. Compare the two modes by physical evaluations.

## 2026-11-12 — XOR mutation rates overlaid

- `analysis/xor_best_fitness.png` and `analysis/xor_diversity.png` put the five XOR expected-flip runs (1, 4, 16, 32, 64) on one fitness chart and one pairwise-Hamming chart. Only 32 flips left 0.500, ending at 0.650. Diversity rises with the mutation rate.

## 2026-11-12 — XOR 64-flip sweep run finished

- The 64-expected-flip XOR run was restarted after the serial port dropped. It finished all 25 generations at fitness 0.500. Plots are in `xor/evolution/out/ea_4bit_g25_m64_p10_e3/`.

## 2026-11-12 — Adder 2 strategies overlaid by generation

- `analysis/adder2_best_fitness.png` and `analysis/adder2_mean_fitness.png` overlay every 2-bit adder strategy. Each line ends at its last generation. The axis runs to generation 176.

## 2026-11-12 — One sheet of the unrecovered generation curves

- `analysis/unrecovered_generation_sheet.png` puts best fitness, mean fitness, pairwise Hamming, and distance to the original on one chart per unrecovered run, arranged together.

## 2026-11-12 — Unrecovered runs improved by a jump or a few added ones

- Across the runs that never recovered, a higher score arrived as either a 1–8 bit edit inside a tight population or a champion tens of bits from the previous best. Pairwise Hamming barely moved at those generations. The partial 4-bit log never rose at all.

## 2026-11-12 — Inchworm run saved at generation 176

- The 500-generation inchworm run was stopped during generation 176. Generations 0–176, 2642 board tests, and the plots are in `adder2/evolution/out/inchworm_4bit_g500_m1_p20_e5/`. Best fitness was 0.500.

## 2026-11-12 — Board port follows the plugged-in Pico

- The inchworm start failed because the serial port had moved from `usbmodem1101` to `usbmodem101`. The runner now uses whichever `/dev/cu.usbmodem` port is present.

## 2026-11-12 — Inchworm raises mutation on a stuck plateau

- `inchworm` is the genetic algorithm with population 20, 5 elites, and mutation 1/N. After the best score holds for 5 generations, the 5 children of the weakest parents mutate faster, adding 4/N every 3 generations up to 40/N. A new best score returns the rate to 1/N.

## 2026-11-11 — 100-generation runs sat on a flat score

- The section-crossover EA reached 10/16 at generation 16 and stayed there through 100. The two hill climbers reached 4/16 and 6/16 early, then accepted same-score mutants and drifted hundreds of bits away. Extra generations of these settings keep walking that plateau.

## 2026-11-11 — Circuit picture zooms to the live cells

- `viz/show_circuit.py` no longer draws the empty fabric or the unused logic cells. Pads and the cells that are actually used share one picture, with a gap label where a run of tiles was left out.
- Each cell is named (`s0`, `cout`, `y`) and shows a short function (`a0 xor b0`, `carry`). Wires run from the pad to that cell, and carry is an arrow between cells.
- Every picture has the same legend: input, output, shared pad, logic cell, wire, carry, and the tile-gap mark.
- Where two or more wires share a path, that stretch alternates their colors so each one stays visible.

## 2026-11-10 — Spatial bitstream viewer

- `viz/show_circuit.py` takes an ASC, a pasted ASC, or a packed BIN and draws this UP5K to scale. Presets cover XOR, the 2-bit adder, and the 4-bit adder.
- Each wire follows the span route between its pin and the logic tile, so a long run is actually long. The opened tile shows the cell equation, which LUT pin each signal uses, and the carry chain. A connection list names the pin, GPIO, and distance.
- Evolution now writes `final_circuit.png` from this viewer.

## 2026-11-11 — Hill climber can start from a small population

- A hill climber with `--population 5` starts as the damaged genome plus 4 mutants. Each of the 5 then climbs alone: one mutant per generation, kept when the accept rule allows. They do not cross or compete.

## 2026-11-11 — One command for circuit, search, and fitness

- `evolution/run.py` runs XOR, the 2-bit adder, or the 4-bit adder with either the section-crossover EA or a one-genome hill climber. Flags override population, generations, elites, expected flips, section share, fault size, seed, and the fitness script. `evolution/CONFIG.md` lists the current defaults. Each `recovery.json` stores the command that produced it.

## 2026-11-11 — 2-bit adder section run sized for more flips

- Population 23, 3 elites, 100 generations. Mutation is an independent 4/807 chance per gene, so the expected flip count is 4 and some children still get zero. Output folder is `adder2/evolution/out/section_4bit_p23_g100/`.

## 2026-11-11 — Section crossover, unnamed bits held fixed

- The genome for XOR and both adders is the 807 named bits of the active logic tile. The 57 bits IceStorm cannot name stay as they are.
- A child has two fitness-chosen parents. Crossover keeps related bits together: a LUT, a flip-flop, a wire, a mux, the clock select, or a carry bit. Each section comes from the fitter parent with probability 0.5. Mutation is 1/807 and skips the three elites. The share lives in `analysis/tile_genome.py`.

## 2026-11-11 — 2-bit adder p30 run plateaued at 0.375

- 50 generations, 848 board tests, no recovery. Best reached 0.375 at generation 16 and stayed there. The mean caught up and sat just under it.
- The best circuit never restored the 4 fault bits. It is 22 bits from the original: those 4 still off, plus 18 zeros turned on. The decoded wiring lost `a0`, `b1`, and the LC0→LC1 carry. Plots: `adder2/evolution/out/direct_4bit_p30_g50/`.

## 2026-11-11 — 2-bit adder run sized up

- Next 2-bit adder run is population 30, 50 generations, mutation 1/864, top 3 kept and not rescored. Output is `adder2/evolution/out/direct_4bit_p30_g50/`, so the previous `direct_4bit` plots stay put.
- Start it under `caffeinate -is` so the Mac stays awake while the screen can still lock.

## 2026-11-11 — Smaller mutation, three elites

- Elitism keeps the top 3. Those exact genomes are not sent to the board again.
- Mutation is now 1/864 per bit, about one flip per child. The previous 1/50 rate changed about 17 bits and knocked good circuits off the score they had just earned.

## 2026-11-10 — 2-bit adder direct run stalled at 0.75

- 30 generations, 470 board tests, no recovery. Best fitness 0.750 from generation 16 on. Mean stayed near 0.4.
- The damaged start scored 0. The best circuit is 69 bits from the original: 2 of the 4 fault bits restored, and 65 bits that were 0 turned on. Each child flips about 17 bits, so the search never takes the small steps that would finish the repair.

## 2026-11-10 — 2-bit adder original and best, in the spatial viewer

- Drew `adder2/build/adder2.asc` and `adder2/evolution/out/direct_4bit/best.asc` with `viz/show_circuit.py`. Pictures: `original_circuit.png` and `best_circuit.png` in that output folder.
- The pin routes are the same. The original carry chain is LC0 → LC1 → LC2. The best circuit keeps only LC1 → LC2.

## 2026-11-10 — 2-bit adder uses the same evolution settings

- `adder2/evolution/run_recovery.py` now evolves all 864 bits of `logic_tile 20,20` with the same population, elitism, mutation rate, and one-pass fitness as the 4-bit adder. Fitness is correct rows / 16. Output is `adder2/evolution/out/direct_4bit/`.

## 2026-11-10 — Adder genome is the tile bits

- The 4-bit adder genome is now all 864 bits of `logic_tile 17,1`. A 1 writes a 1 and a 0 writes a 0, starting from the real bitstream. Faults still flip 4 or 8 of the original ones.
- Population 20, top 5 kept, mutation probability 1/50 per bit, fitness is one pass over the 256 sums. The population starts as one damaged tile plus 19 mutants. Parameters are at the top of `README.md`.
- Next results go to `adder4/evolution/out/direct_4bit/` and `direct_8bit/`. The interrupted `open_4bit` plots stay where they are.

## 2026-11-10 — Open-mask 4-bit adder run stopped early

- The full-tile repair run (97 operable bits, 4 faults) was interrupted at generation 19. The next board call hung, then Ctrl+C. 102 candidates had been scored. Nothing was written until the end, so the plots were rebuilt from the terminal.
- Best fitness stayed 0.50 and the best circuit stayed 4 bits from the original. The population only differed by about 4–5 bits out of 97. The one-bit repair that worked in the narrow search did not show up in the retained candidates.
- Plots: `adder4/evolution/out/open_4bit/`. Generations 0–13 had scrolled out of the terminal.

## 2026-11-10 — Evolution mask matches the operable tile bits

- Faults still flip 4 or 8 bits. Repair may now change every set bit in the active logic tile (XOR 17, 2-bit adder 61, 4-bit adder 97), not only the bits that were flipped.
- That list is the current constraint. Zeros in the tile, other tiles, and pins stay fixed. Widening the fault region later widens repair with it. Shared definition: `analysis/operable_mask.py`.
- Previous board results are unchanged. The next run writes `out/open_4bit` and `out/open_8bit`.

## 2026-11-10 — Bit-space scale graph

- Compared XOR, 2-bit adder, and 4-bit adder: set bits in the active tile are 17, 61, and 97. A 4-bit fault is 24%, 7%, and 4% of those. An 8-bit fault is 47%, 13%, and 8%.
- Repair search stays 16 or 256 genotypes, because evolution may change only the faulted bits. Graph: `analysis/bit_space_scale.png`.

## 2026-11-10 — 4-bit adder recovery (4 and 8 bits)

- 4-bit adder fits in one tile, `logic_tile 17,1`, using 5 of 8 cells (one cell per sum bit, plus carry-out). 97 set bits in that tile.
- Known-good bitstream scored 256/256. Ten pins are onboard; `b2`, `b3`, and `cout` reuse the three XOR jumper wires.
- Same recovery loop. 4-bit fault scored 0.50 and recovered at generation 1 (`0001`, distance 3, 5 tests). 8-bit fault scored 0.09 and recovered at generation 7 (`00011111`, distance 3, 36 tests).
- Settings: `adder4/evolution/CONFIG.md`. Graphs under `adder4/evolution/out/`.

## 2026-11-10 — 2-bit adder recovery (4 and 8 bits)

- Same loop as XOR: fault and search share one seed-42 draw in `logic_tile 20,20`. Fitness is correct adder rows / 80.
- 4-bit fault scored 0.00 and recovered at generation 1 (`0110`, distance 2, 5 board tests).
- 8-bit fault scored 0.25 and recovered at generation 4 (`11101101`, distance 2, 21 board tests).
- Settings table: `adder2/evolution/CONFIG.md`. Graphs under `adder2/evolution/out/recovery_4bit/` and `recovery_8bit/`.

## 2026-11-10 — 2-bit adder on the shared pin bank

- Adder uses the on-board RP-ICE pins (no jumpers). Truth table on the board: **16/16**.
- It occupies one logic tile, `(20,20)`, and 3 of that tile's 8 cells: LC0 is the low sum bit, LC1 the high bit, LC2 the carry out. Carry links LC0 → LC1 → LC2.
- Layout picture: `adder2/build/adder2_fpga_layout.png`. The plotter now opens a tile into its 8 logic cells.

## 2026-11-10 — Shared RP-ICE connection check

- Added `diagnostics/connection_check/` with `check_connections.py` plus HIGH/FOLLOW bitstreams on the shared RP-ICE bank (no jumpers).
- Pin bank: IN ICE_27/26/25/23 ↔ GPIO20/24/30/25; OUT ICE_20/19/18/21 ↔ GPIO22/23/27/26.
- Board run: OUTPUT_HIGH, FOLLOW, and ONE_HOT all **PASS** (`OVERALL,PASS`). Shared bank is ready for the 2-bit adder.

## 2026-11-10 — XOR wiring diagnostics

- Built `diag_a.bin`, `diag_b.bin`, `xor.bin` from wiring diagnostics.
- Fixed `diagnose_wiring.py` FPGA load path to match `load_xor.py` (`ice.fpga(...)` + `start()` + `cram(file)`).
- Uploaded bitstreams + script via mpremote and ran on `/dev/cu.usbmodem1101`.

### Results
- A_FOLLOW: 10/20 (Y stuck at 0 when A=1 expected)
- B_FOLLOW: 10/20 (Y stuck at 0 when B=1 expected)
- XOR: 10/20 (Y always measured 0)

### Interpretation
Scores of 10/20 match “Y stuck low” (expected zeros pass, expected ones fail). Does not isolate A vs B.

## 2026-11-10 — Constant-HIGH output path test

- Added `diag_y_high` circuit (`assign y = 1'b1`) and board reader.
- First run: CDONE=1, GPIO33 all zeros → suspect ICE4→GPIO33 / mapping.

## 2026-11-10 — Constant-HIGH retest

- Reloaded and reran: CDONE=1, GPIO33 **20/20 ones** → output path OK.
- Full A/B/XOR suite not re-run after this.

## 2026-11-10 — Live XOR graph (`graph_xor.py`)

- Host run completed successfully (~51s).
- Samples: 80, Matches: **80**, Mismatches: **0** — measured Y matched XOR truth table for all patterns.

## 2026-11-10 — 8-bit XOR recovery

- Same setup as the 4-bit run, but the fault and the search are the full 8-bit seed-42 sample in `logic_tile 8,1` (the 4-bit fault plus four more).
- Per-bit mutation probability 0.125. Recovered at generation 2 after 12 physical tests.
- Best genome `11001001` scores 1.0 and still differs from the original in 4 of those bits. Routing is unchanged.
- Graphs in `xor/evolution/out/recovery_8bit/`.

## 2026-11-10 — 4-bit XOR recovery

- Fault mask and evolution mask are the same 4 bits in `logic_tile 8,1` (seed 42).
- Population 10, per-bit mutation probability 0.25, no crossover, stop at fitness 1.0.
- Recovered at generation 1 after 5 physical evals. Best genome `0100` (3 bits still differ from the original) scores 1.0.
- Graphs in `xor/evolution/out/recovery_4bit/`: `fitness_over_generations.png`, `hamming_diversity.png`, `final_circuit.png`.

## 2026-11-10 — Evolution parameter notes

- Wrote `xor/evolution/PARAMETERS.md` for ini knobs and fitness.
- Tile constraint is a rectangle in `xor/evolution/xor_area.ini` (currently 5×5 at x=7..11, y=1..5, 25 tiles including the XOR LUT). `tile_area.py` lists the tiles.

## 2026-11-10 — XOR FPGA layout visual

- `xor/host/plot_xor_fpga_layout.py` draws any ASC (`--asc`, `--pcf`, `--out`).
- Inputs vs outputs come from the sg48 pin map plus whether the pad drives `D_OUT`.
- Map shows the routed circuit, with a labeled wire for each pin (arrow points at the sink). LUT init strings and a bit-column heatmap explain how a tile is set.
- Current XOR: IN a pin 2 tile 8,0; IN b pin 3 and OUT y pin 4 share tile 9,0; LUT at 8,1. Tile 14,8 is set but not routed.

## 2026-11-10 — XOR fault-injection baseline

- Script: `xor/fault_injection/run_fault_baseline.py`
- Flips among non-zero bits in active tile `.logic_tile 8 1` (17 ones); severities 0/1/2/4/8.
- Multi-seed run: seeds **42, 7, 99, 123** (board flash cleaned; uploads reuse `candidate.bin`).
- Mean accuracy / full-pass rate:
  - 0 flips: 100% / 100%
  - 1 flip: **81.25%** / **50%** (stdev ~24% — seed-dependent)
  - 2 / 4 / 8 flips: **50%** / **0%**
- Artifacts: `xor/fault_injection/out/fault_baseline_results.json`, `fault_baseline_accuracy.png`

## 2026-11-10 — Repo organize + clone evolution toolkit

- Cloned `evolvablehardware/BitstreamEvolutionPico2ice` → `vendor/BitstreamEvolutionPico2ice`.
- Reorganized local work into `xor/`, `diagnostics/`, `docs/`, `firmware/`, `python_tests/`, `archives/`.
- Added root `README.md` explaining layout and how upstream evolution code maps (mutation, load, fitness, variance-max example).
- **Not done:** run variance-max example; build XOR recovery experiment.
