# PicoIceProj

Workspace for pico2-ice XOR bring-up, wiring diagnostics, and bitstream evolution experiments.

## Current evolution run — 4-bit adder

The genome is the active logic tile. A gene of 1 writes a 1 into the bitstream, and a gene of 0 writes a 0. The run starts from that tile’s real bits, with the fault bits already flipped. Other tiles and the pin tiles stay as placed.

| Parameter | Value |
|---|---|
| Circuit | 4-bit adder, `{cout,s3,s2,s1,s0} = a + b` |
| Seed bitstream | `adder4/build/adder4.asc` |
| Active tile | `logic_tile 17,1` (16 rows × 54 columns) |
| Genome | 807 named bits of the tile. The 57 unnamed bits stay fixed |
| Bits that start as 1 | 97 |
| What stays fixed | every other tile, and the IO tiles |
| Fault | 4 bits, then 8. Seed 42, sample 8 of the original 1s, take the first N |
| Evolution seed | 43 |
| Starting population | 1 damaged genome, plus 19 mutants of it |
| Population | 20 |
| Generations | 30, stop earlier if fitness hits 1.0 |
| Elitism | top 3 copied unchanged, and not scored again |
| Selection | fitness-proportional. A fitter parent is more likely to be picked |
| Crossover | every child has two parents. Each section comes from the fitter parent with probability 0.5 |
| Crossover sections | 16-bit LUT, 4-bit flip-flop, one wire, one routing mux, the global clock select, carry |
| Mutation | each gene flips with probability 1/807, after crossover. Elites are not mutated |
| Expected flips per child | about 1 |
| Fitness | correct truth-table rows / 256 |
| A row passes | `s0`, `s1`, `s2`, `s3`, and `cout` all match |
| Repeats | 1 |
| Target | 1.0 |
| Diversity logged | mean pairwise Hamming, and best vs the original tile |
| Output | `adder4/evolution/out/section_4bit_p20_g30/` |

The 2-bit adder uses this same crossover on `logic_tile 20,20`, with population 23, 3 elites, and 100 generations. Each gene flips with probability 4/807, so a child gets about 4 flips and some get none. Its fitness is correct rows / 16. Output is `adder2/evolution/out/section_4bit_p23_g100/`. The XOR run writes `xor/evolution/out/section_4bit/`.

Circuits, fitness scripts, and the two searches (the section-crossover EA, and a one-genome hill climber) are listed in `evolution/CONFIG.md`. A run is one command, and its `recovery.json` records that command.

```
python evolution/run.py --list
python evolution/run.py --circuit adder2 --algorithm ea --bits 4
python evolution/run.py --circuit adder2 --algorithm hill --bits 4 --generations 2000 --expected-flips 1
```

## What’s here

```
PicoIceProj/
├── xor/                         # Our baseline XOR design + board/host tests
│   ├── rtl/                     # xor.v, xor.pcf
│   ├── build/                   # yosys/nextpnr artifacts (.json/.asc/.bin)
│   ├── board/                   # MicroPython: load_xor.py, demo_xor.py, truth_table_score.py
│   ├── host/                    # Mac-side: graph_xor.py
│   └── fault_injection/         # Flip 1/2/4/8 config bits + score baseline
├── diagnostics/
│   └── xor_wiring_diagnostics/  # A/B-follow, XOR, constant-HIGH path tests
├── vendor/
│   └── BitstreamEvolutionPico2ice/  # Cloned evolvable-hardware toolkit (upstream)
├── firmware/                    # pico2_ice.uf2 board firmware
├── docs/pinout/                 # pico2-ice pinout diagram
├── python_tests/                # Early MicroPython smoke scripts
├── archives/                    # Zipped snapshots
├── PROJECT_LOG.md               # Running status notes
└── .venv/                       # Local Python (mpremote, matplotlib, …)
```

## Current wiring (assumed)

| Signal | RP2350 GPIO | FPGA header / package |
|--------|-------------|------------------------|
| A      | GPIO2       | ICE_2 / pin 2          |
| B      | GPIO3       | ICE_3 / pin 3          |
| Y      | GPIO33      | ICE_4 / pin 4          |

Keep logic at 3.3 V. Unplug USB before changing wires.

## Status snapshot

- Baseline XOR RTL + bitstream exist under `xor/`.
- Wiring diagnostics ran; constant-HIGH retest later showed **GPIO33 = 1** with CDONE set (output path OK at that time).
- Full A_FOLLOW / B_FOLLOW / XOR suite was **not** re-run after the HIGH retest.
- `BitstreamEvolutionPico2ice` is cloned under `vendor/` for inspection only — **examples not run yet**, XOR recovery experiment **not built yet**.

See `PROJECT_LOG.md` for dated notes.

---

## Making sense of `vendor/BitstreamEvolutionPico2ice`

Upstream: [evolvablehardware/BitstreamEvolutionPico2ice](https://github.com/evolvablehardware/BitstreamEvolutionPico2ice)  
Project page: [Bitstream Evolution (v2 pico2-ice)](https://evolvablehardware.github.io/projects/bitstream_evolution_pico2-ice/)  
Software setup (still TBD upstream): [software setup](https://evolvablehardware.github.io/projects/bitstream_evolution_pico2-ice/software_setup/)

### What it is

A genetic-algorithm toolchain that mutates FPGA **ASC bitstreams**, loads them onto pico2-ice hardware (often via **iCEFARM**), and scores fitness. It is **not** an XOR fault-recovery demo out of the box. The intended “hello world” is **variance maximization** (evolve a circuit that wiggles an analog/digital readout a lot), not truth-table accuracy.

### Core pieces (where to look)

| Concern | Location | Role |
|---------|----------|------|
| Entry point | `src/evolve.py` → `src/Evolution.py` | Loads config, builds population, runs generations |
| Population loop | `src/CircuitPopulation.py` | Populate → evaluate → select → mutate/crossover |
| Mutation | `src/ga/mutation.py` (+ circuit `.mutate()`) | Bitstream flips; uses `ascutil` for speed |
| Crossover / selection | `src/ga/crossover.py`, `src/ga/selection/` | Standard GA operators |
| Fitness API | `src/Circuit/FitnessFunction.py` | Strategy interface: measure → score |
| Example fitness | `src/Circuit/VarMaxFitnessFunction.py` | Variance of MCU waveform samples |
| Other fitness | `PulseCountFitnessFunction`, `ToneDiscriminatorFitnessFunction` | Oscillator / tone style goals |
| Hardware load/eval | `src/Circuit/IntrinsicCircuit.py`, `RemoteCircuit.py`, `Microcontroller.py` | On-board / iCEFARM evaluation |
| Configs | `data/example_configs/`, `data/default_config.ini`, `CONFIG.md` | Experiment knobs |
| Simplest example config | `data/example_configs/variance_maximization.ini` | `fitness_func = VARIANCE`, random init |
| Docker | `docker/` | Recommended reproducible stack (often with iCEFARM) |

### Mental model

```
config.ini  →  Evolution  →  CircuitPopulation
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
                 mutate      evaluate     select
              (ASC bits)   (load FPGA +   (elites /
                            fitness fn)    tournaments)
```

Fitness today is mostly **waveform-oriented** (variance, pulse count). An XOR recovery experiment would need a **new fitness function**: drive A/B patterns, read Y, score truth-table accuracy — reusing mutation/loading/GA, not inventing a new engine from scratch.

### How our XOR work relates

| Our work (`xor/`, `diagnostics/`) | Upstream toolkit |
|----------------------------------|------------------|
| Explicit Verilog XOR + PCF pins 2/3/4 | Mutates ASC tiles; seeds often target ICE_27-style pins |
| Fitness = digital truth table via GPIO | Fitness = variance / pulses via MCU firmware |
| Direct `mpremote` + MicroPython `ice` | Docker + iCEFARM / Arduino-style measurement path |
| Bring-up & wiring confidence | Population evolution infrastructure |

**Recommended path (later, not done yet):**

1. Inspect mutation / load / fitness / experiment code in `vendor/BitstreamEvolutionPico2ice` (started conceptually above).
2. Run their simplest example (variance max) once software/iCEFARM stack is ready.
3. Build a controlled XOR recovery experiment: save known-good config → inject one understood fault → evolve with truth-table fitness.

---

## Local XOR commands (reference only — not run in this organize step)

Activate the venv, then use `mpremote` against `/dev/cu.usbmodem1101` (port may differ).

```bash
source .venv/bin/activate

# Upload bitstream + board scripts, then load FPGA
mpremote connect /dev/cu.usbmodem1101 fs cp xor/build/xor.bin :xor.bin
mpremote connect /dev/cu.usbmodem1101 fs cp xor/board/load_xor.py :load_xor.py
mpremote connect /dev/cu.usbmodem1101 fs cp xor/board/demo_xor.py :demo_xor.py
mpremote connect /dev/cu.usbmodem1101 exec "import load_xor"
mpremote connect /dev/cu.usbmodem1101 exec "import demo_xor"

# Live plot (host)
python xor/host/graph_xor.py
```

Diagnostics live under `diagnostics/xor_wiring_diagnostics/` (see that folder’s `README.txt`).

---

## Fault-injection baseline

```bash
source .venv/bin/activate
python xor/fault_injection/run_fault_baseline.py
```

Flips N bits in `.logic_tile 8 1` (XOR’s used logic tile), reloads each bitstream, scores the 4-row truth table. Results land in `xor/fault_injection/out/`.

## Next

- [ ] Run BitstreamEvolution variance-maximization example  
- [ ] Evolve recovery from damaged XOR configs (truth-table fitness)  
- [ ] Multi-trial sweeps over random fault seeds / severities  
