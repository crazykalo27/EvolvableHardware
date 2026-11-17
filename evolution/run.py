"""Run one search on one circuit.

    python evolution/run.py --list
    python evolution/run.py --circuit adder2 --algorithm ea --bits 4
    python evolution/run.py --circuit adder2 --algorithm hill --bits 4 --generations 2000 --expected-flips 1 --accept neutral

Every flag falls back to the circuit's defaults in evolution/circuits.py.
The recovery.json in the output folder records the values that actually ran.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.operable_mask import split_fault
from analysis.tile_genome import load_tile, mutate
from evolution.bandit import DEFAULT_FLIPS, IMPACT_BASIS, UCB_C, MutationBandit, lookup_fitness
from evolution.circuits import CIRCUITS, Circuit
from evolution.saga import (
    SAGA_BASE_FLIPS,
    SAGA_BOTTOM,
    SAGA_DRIFT_WINDOW,
    SAGA_ELITES,
    SAGA_FIRST_STALL,
    SAGA_GENERATIONS,
    SAGA_INITIAL_FLIPS,
    SAGA_MAX_FLIPS,
    SAGA_POPULATION,
    SAGA_SEED,
    SAGA_SEED_COPIES,
    SAGA_STALL_EVERY,
    SAGA_STEP_FLIPS,
    choose_elite,
    drift_record,
    initial_population as saga_initial,
    place_elite_first,
    saga_flips,
    saga_next,
    stops_at_perfect,
    tie_fraction,
    update_stall,
)
from evolution.search import (
    INCHWORM_BASE_FLIPS,
    INCHWORM_BOOST_COUNT,
    INCHWORM_BOOST_EVERY,
    INCHWORM_BOOST_FLIPS,
    INCHWORM_ELITES,
    INCHWORM_MAX_FLIPS,
    INCHWORM_POPULATION,
    INCHWORM_STUCK_GENERATIONS,
    BANDIT_MAX_FLIPS,
    BANDIT_MIN_FLIPS,
    adopt_bandit_rate,
    adopt_tworate,
    bandit_child_rates,
    bandit_next,
    ea_next,
    heavy_initial,
    heavy_next,
    hill_keep,
    inchworm_boosted_flips,
    inchworm_next,
    initial_exact,
    initial_population,
    tworate_next,
)

PORT = ""
PLOT = ROOT / "viz" / "show_circuit.py"
TARGET = 1.0


@dataclass
class Search:
    algorithm: str
    bits: int
    population: int
    generations: int
    elites: int
    expected_flips: float
    section_share: float
    seed: int
    accept: str
    score_script: Path | None = None
    bandit_mode: str | None = None
    mutation: str = "fixed"


def describe() -> str:
    lines = [
        "Circuits (the fitness script is what the board runs):",
    ]
    for circuit in CIRCUITS.values():
        lines.append(
            f"  {circuit.name:7}  tile {circuit.tile[0]},{circuit.tile[1]}  "
            f"{circuit.fitness}"
        )
        lines.append(f"           score {circuit.score_script}")
        lines.append(
            f"           ea defaults: population {circuit.population}, "
            f"generations {circuit.generations}, elites {circuit.elites}, "
            f"expected flips {circuit.expected_flips:g}, "
            f"section share {circuit.section_share:g}, "
            f"fault bits {circuit.bits}, seed {circuit.seed}"
        )
    lines.append("")
    lines.append("Algorithms:")
    lines.append("  ea    population, two parents, section crossover, then mutation. Elites are copied.")
    lines.append("  inchworm  the EA loop with population 20, 5 elites, and base mutation 1/N.")
    lines.append("        After 5 generations at the same best score, the 5 children with the weakest")
    lines.append("        parents mutate faster. Every 3 more generations adds 4/N, up to 40/N.")
    lines.append("        A higher best score returns every child to 1/N.")
    lines.append("  saga  population 21, one elite, 300 generations, fault seed 13.")
    lines.append("        Generation 0 is 6 copies of the damaged genome and 15 mutants at 4/N.")
    lines.append("        Section crossover stays an even split. A strict gain replaces the elite and")
    lines.append("        returns the rate to 2/N. A different child with the same score can replace")
    lines.append("        the elite without resetting the rate. An exact copy cannot.")
    lines.append("        The 7 children with the weakest parents use 2, 6, 10, ... 34 flips. The first")
    lines.append("        rise is at stall 3, then every 3 generations, and 34 holds. The other 13")
    lines.append("        children stay at 2/N. A perfect score does not stop the run.")
    lines.append("  bandit  the EA loop. Crossover is unchanged. Each child then flips an exact number")
    lines.append("        of genes, 32 unless --expected-flips says otherwise.")
    lines.append("        --bandit uniform draws those genes from the whole genome.")
    lines.append("        --bandit ucb draws named sections until they can hold the flips, scores the")
    lines.append("        crossover child, flips, then scores the mutant. A flipped section gets +1 only")
    lines.append("        when fitness rises. A drop and an unchanged score both pay 0 and still count.")
    lines.append("        Selection uses the mutant's fitness and does not read the reward. The scalar")
    lines.append("        is a proxy: the search does not see the output")
    lines.append("        vector, so a different output with the same match count counts as no change.")
    lines.append("        --mutation tworate on the bandit starts at --expected-flips and splits the")
    lines.append("        children between half that count and double it. A tie keeps the lower count.")
    lines.append("        The count stays between 1 and 32. The bandit keeps one elite.")
    lines.append("  --mutation heavy  draws each child's flip count from a power law with beta 1.5,")
    lines.append("        then flips each gene with probability count/N. One flip is common. The count")
    lines.append("        never exceeds N.")
    lines.append("  --mutation tworate  splits the children between half the current rate and double it.")
    lines.append("        The next rate becomes whichever half scored higher, and stays between 1 and N/2.")
    lines.append("        It starts at --expected-flips. A tie keeps the higher rate.")
    lines.append("  hill  each genome climbs alone. A generation mutates each one and keeps the mutant by --accept.")
    lines.append("        Population 1 starts from the damaged genome. A larger population starts with that")
    lines.append("        genome plus mutants of it. neutral keeps a tie. improve keeps only a higher score.")
    lines.append("")
    lines.append("Flags override one circuit's defaults. --score replaces that circuit's fitness script.")
    lines.append("The script must print RESULT,<name>,<matches>,<total>,<fraction>.")
    return "\n".join(lines)


def parser(default_circuit: str | None) -> argparse.ArgumentParser:
    choices = list(CIRCUITS)
    argp = argparse.ArgumentParser(description="Run a search on one circuit.")
    argp.add_argument("--list", action="store_true", help="show circuits, fitness, and algorithms")
    argp.add_argument("--circuit", default=default_circuit, choices=choices)
    argp.add_argument("--algorithm", default="ea", choices=("ea", "hill", "inchworm", "bandit", "saga"))
    argp.add_argument("--bandit", default="ucb", choices=("uniform", "ucb"))
    argp.add_argument("--bits", type=int, default=None)
    argp.add_argument("--population", type=int, default=None)
    argp.add_argument("--generations", type=int, default=None)
    argp.add_argument("--elites", type=int, default=None)
    argp.add_argument("--expected-flips", type=float, default=None)
    argp.add_argument("--mutation", default="fixed", choices=("fixed", "heavy", "tworate"))
    argp.add_argument("--section-share", type=float, default=None)
    argp.add_argument("--seed", type=int, default=None)
    argp.add_argument("--accept", default="neutral", choices=("neutral", "improve"))
    argp.add_argument("--score", type=Path, default=None, help="fitness script, replacing the circuit default")
    return argp


def resolve(args, circuit: Circuit) -> Search:
    return Search(
        algorithm=args.algorithm,
        bits=circuit.bits if args.bits is None else args.bits,
        population=_algorithm_default(
            args.algorithm, args.population, circuit.population,
            hill=1, inchworm=INCHWORM_POPULATION, saga=SAGA_POPULATION,
        ),
        generations=(
            SAGA_GENERATIONS if args.algorithm == "saga" and args.generations is None
            else circuit.generations if args.generations is None else args.generations
        ),
        elites=_algorithm_default(
            args.algorithm, args.elites, circuit.elites,
            inchworm=INCHWORM_ELITES, bandit=1, saga=SAGA_ELITES,
        ),
        expected_flips=_algorithm_default(
            args.algorithm,
            args.expected_flips,
            circuit.expected_flips,
            inchworm=INCHWORM_BASE_FLIPS,
            bandit=DEFAULT_FLIPS,
            saga=SAGA_BASE_FLIPS,
        ),
        section_share=circuit.section_share if args.section_share is None else args.section_share,
        seed=SAGA_SEED if args.algorithm == "saga" and args.seed is None else (
            circuit.seed if args.seed is None else args.seed
        ),
        accept=args.accept,
        score_script=args.score,
        bandit_mode=args.bandit if args.algorithm == "bandit" else None,
        mutation=args.mutation,
    )


def _algorithm_default(algorithm, given, circuit_value, hill=None, inchworm=None, bandit=None, saga=None):
    if given is not None:
        return given
    if algorithm == "hill" and hill is not None:
        return hill
    if algorithm == "inchworm" and inchworm is not None:
        return inchworm
    if algorithm == "bandit" and bandit is not None:
        return bandit
    if algorithm == "saga" and saga is not None:
        return saga
    return circuit_value


def _num(value: float) -> str:
    if float(value) == int(value):
        return str(int(value))
    return str(value)


def output_dir(circuit: Circuit, search: Search) -> Path:
    """Folder name includes the knobs that distinguish one run from another."""
    if (
        circuit.name == "adder2"
        and search.algorithm == "ea"
        and search.bits == 4
        and search.population == 23
        and search.generations == 100
        and search.elites == 3
        and search.expected_flips == 4
        and search.section_share == 0.5
        and search.seed == 42
        and search.score_script is None
    ):
        name = "section_4bit_p23_g100"
    else:
        name = (
            f"{search.algorithm}_{search.bits}bit_g{search.generations}"
            f"_m{_num(search.expected_flips)}"
        )
        if search.algorithm in ("ea", "inchworm", "bandit", "saga"):
            name += f"_p{search.population}_e{search.elites}"
            if search.section_share != 0.5:
                name += f"_s{int(round(search.section_share * 100))}"
            if search.algorithm == "bandit":
                name += f"_{search.bandit_mode}"
            if search.mutation != "fixed":
                name += f"_{search.mutation}"
        else:
            if search.population != 1:
                name += f"_p{search.population}"
            name += f"_{search.accept}"
        if search.seed != 42:
            name += f"_seed{search.seed}"
        if search.score_script is not None:
            name += f"_{search.score_script.stem}"
    return ROOT / circuit.name / "evolution" / "out" / name


def command_line(circuit: Circuit, search: Search) -> str:
    parts = [
        "python evolution/run.py",
        f"--circuit {circuit.name}",
        f"--algorithm {search.algorithm}",
        f"--bits {search.bits}",
        f"--generations {search.generations}",
        f"--expected-flips {_num(search.expected_flips)}",
        f"--seed {search.seed}",
    ]
    if search.algorithm in ("ea", "inchworm", "bandit", "saga"):
        parts.append(f"--population {search.population}")
        parts.append(f"--elites {search.elites}")
        parts.append(f"--section-share {search.section_share:g}")
        if search.algorithm == "bandit":
            parts.append(f"--bandit {search.bandit_mode}")
        if search.mutation != "fixed":
            parts.append(f"--mutation {search.mutation}")
    else:
        parts.append(f"--population {search.population}")
        parts.append(f"--accept {search.accept}")
    if search.score_script is not None:
        parts.append(f"--score {search.score_script}")
    return " ".join(parts)


def check(search: Search) -> None:
    if search.bits < 1:
        raise SystemExit("--bits must be at least 1")
    if search.generations < 0:
        raise SystemExit("--generations must be at least 0")
    if search.expected_flips <= 0:
        raise SystemExit("--expected-flips must be above 0")
    if not 0 <= search.section_share <= 1:
        raise SystemExit("--section-share must be from 0 to 1")
    if search.population < 1:
        raise SystemExit("--population must be at least 1")
    if search.algorithm in ("ea", "inchworm", "bandit", "saga"):
        if search.population < 2:
            raise SystemExit("the EA needs a population of at least 2")
        if search.elites < 0 or search.elites >= search.population:
            raise SystemExit("--elites must be at least 0 and below the population")
    if search.algorithm == "saga":
        if search.mutation != "fixed":
            raise SystemExit("saga uses its own mutation schedule")
        if search.population != SAGA_POPULATION or search.elites != SAGA_ELITES:
            raise SystemExit("saga uses population 21 and 1 elite")
        if search.expected_flips != SAGA_BASE_FLIPS:
            raise SystemExit("saga keeps a base rate of 2 expected flips")
        if search.population - search.elites < SAGA_BOTTOM:
            raise SystemExit(f"saga needs at least {SAGA_BOTTOM} children below the elite")
    if search.algorithm == "bandit" and search.expected_flips != int(search.expected_flips):
        raise SystemExit("bandit --expected-flips is an exact bit count and must be a whole number")
    if search.mutation == "heavy" and search.algorithm != "ea":
        raise SystemExit("--mutation heavy is part of the EA")
    if search.mutation == "tworate" and search.algorithm not in ("ea", "bandit"):
        raise SystemExit("--mutation tworate is part of the EA or the bandit")
    if search.algorithm == "bandit" and search.mutation == "tworate":
        if not BANDIT_MIN_FLIPS <= search.expected_flips <= BANDIT_MAX_FLIPS:
            raise SystemExit("bandit two-rate starts between 1 and 32 expected flips")
    if search.algorithm == "inchworm" and search.population - search.elites < INCHWORM_BOOST_COUNT:
        raise SystemExit(
            f"inchworm needs at least {INCHWORM_BOOST_COUNT} children below the elites"
        )


def apply_genome(asc_lines, positions, genome):
    out = asc_lines[:]
    for bit, (line_idx, col) in zip(genome, positions):
        row = list(out[line_idx])
        row[col] = "1" if bit else "0"
        out[line_idx] = "".join(row)
    return out


def board_port() -> str:
    found = sorted(Path("/dev").glob("cu.usbmodem*"))
    if not found:
        raise SystemExit("No Pico is plugged in. Expected a /dev/cu.usbmodem port.")
    if len(found) > 1:
        print(f"Several serial ports; using {found[0]}")
    return str(found[0])


class BoardSession:
    """One raw-REPL connection shared by delete, upload, and score."""

    def __init__(self) -> None:
        self.transport = None

    def close(self) -> None:
        transport = self.transport
        self.transport = None
        if transport is None:
            return
        try:
            transport.close()
        except Exception:
            pass

    def call(self, action, retries: int = 8):
        """Run action on the open session. Reconnect after a dropped port."""
        global PORT
        last_detail = "no attempt"
        for attempt in range(retries):
            try:
                if self.transport is None:
                    PORT = board_port()
                    from mpremote.transport_serial import SerialTransport

                    self.transport = SerialTransport(PORT)
                    self.transport.enter_raw_repl(soft_reset=True)
                return action()
            except SystemExit as err:
                last_detail = str(err)
                print(f"Board port missing ({attempt + 1}/{retries}). Waiting.")
            except Exception as err:
                last_detail = str(err)
                print(f"Board call failed ({attempt + 1}/{retries}). Waiting.")
            self.close()
            time.sleep(min(15.0, 2.0 + attempt * 2))
        raise SystemExit(f"Board session failed on {PORT}:\n{last_detail}")


BOARD = BoardSession()


def upload(local: Path, remote: str) -> None:
    data = local.read_bytes()

    def action():
        BOARD.transport.fs_writefile(remote, data)

    BOARD.call(action)


def remove_remote(name: str) -> None:
    def action():
        try:
            BOARD.transport.fs_rmfile(name)
        except OSError:
            pass

    BOARD.call(action)


def free_board_space(keep_name: str) -> None:
    """Delete board files other than the score script. Evolution data stays on the host."""
    code = (
        "import os\n"
        f"keep={{{keep_name!r}}}\n"
        "for name in list(os.listdir()):\n"
        "    if name in keep or name.startswith('.'): continue\n"
        "    try:\n"
        "        os.remove(name)\n"
        "    except OSError:\n"
        "        pass\n"
        "info = os.statvfs('/')\n"
        "print('space', info[3] * info[0])\n"
    )
    print(BOARD.call(lambda: _exec(code)).strip())


def upload_bitstream(local: Path, remote: str, script: Path, script_name: str) -> None:
    """Copy a bitstream onto a filesystem that cannot hold two of them.

    The previous bitstream is removed first. If the board is still full, every
    other file except the score script is removed and the copy is tried once more.
    """
    remove_remote(remote)
    try:
        upload(local, remote)
    except SystemExit:
        print("Board upload failed. Clearing the filesystem and retrying.")
        free_board_space(script_name)
        upload(script, script_name)
        remove_remote(remote)
        upload(local, remote)


def genome_key(genome) -> str:
    return "".join(str(bit) for bit in genome)


def genome_from_key(text: str) -> tuple[int, ...]:
    return tuple(int(bit) for bit in text)


def rng_to_json(rng: random.Random) -> dict:
    version, state, gauss = rng.getstate()
    return {"version": version, "state": list(state), "gauss": gauss}


def rng_from_json(rng: random.Random, data: dict) -> None:
    rng.setstate((data["version"], tuple(data["state"]), data["gauss"]))


def atomic_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload))
    os.replace(tmp, path)


def _exec(code: str, timeout: int = 180) -> str:
    ret, ret_err = BOARD.transport.exec_raw(code, timeout=timeout)
    if ret_err:
        raise RuntimeError(ret_err.decode())
    return ret.decode()


def score_on_board(module: str, remote_bin: str) -> float:
    out = BOARD.call(lambda: _exec(f"import {module}\n{module}.score({remote_bin!r})\n"))
    for line in out.splitlines():
        if line.startswith("RESULT,"):
            _tag, _name, matches, total, _acc = line.split(",")
            return int(matches) / int(total)
    raise RuntimeError(f"No RESULT line:\n{out}")


def hamming(a, b) -> int:
    return sum(x != y for x, y in zip(a, b))


def mean_pairwise_hamming(pop) -> float:
    total = 0
    count = 0
    for i in range(len(pop)):
        for j in range(i + 1, len(pop)):
            total += hamming(pop[i], pop[j])
            count += 1
    return total / count if count else 0.0


def write_plots(history, out_dir: Path, circuit: Circuit, search: Search, mask_bits: int) -> None:
    import matplotlib.pyplot as plt

    gens = [row["generation"] for row in history]
    best = [row["best_fitness"] for row in history]
    mean = [row["mean_fitness"] for row in history]
    hamm = [row["mean_pairwise_hamming"] for row in history]
    dist = [row["best_distance_to_original"] for row in history]
    if search.algorithm == "bandit":
        label = f"{circuit.title} — bandit {search.bandit_mode} — {search.bits}-bit fault"
    else:
        label = f"{circuit.title} — {search.algorithm} — {search.bits}-bit fault"

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(gens, best, marker="o", color="#2a7a4b", label="Best fitness")
    ax.plot(gens, mean, marker="o", color="#3a6ea5", label="Mean fitness")
    ax.axhline(1.0, color="#888888", linestyle="--", linewidth=1, label="Recovery (1.0)")
    ax.set_ylim(-0.05, 1.05)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Truth-table fitness")
    ax.set_title(label)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "fitness_over_generations.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(gens, hamm, marker="o", color="#6b5b95", label="Mean pairwise Hamming")
    ax.plot(gens, dist, marker="o", color="#c45c12", label="Best vs original")
    hi = max(max(hamm), max(dist), 1)
    ax.set_ylim(-0.2, hi * 1.25)
    ax.set_xlabel("Generation")
    ax.set_ylabel(f"Hamming distance (genome length {mask_bits})")
    ax.set_title(label)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "hamming_diversity.png", dpi=160)
    plt.close(fig)

    if search.algorithm != "bandit":
        return
    evals = [row["physical_evals"] for row in history]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(evals, best, marker="o", color="#2a7a4b", label="Best fitness")
    ax.axhline(1.0, color="#888888", linestyle="--", linewidth=1, label="Recovery (1.0)")
    ax.set_ylim(-0.05, 1.05)
    ax.set_xlabel("Physical board evaluations")
    ax.set_ylabel("Truth-table fitness")
    ax.set_title(label)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "fitness_vs_evals.png", dpi=160)
    plt.close(fig)


def run(circuit: Circuit, search: Search) -> None:
    global PORT
    check(search)
    PORT = board_port()
    print(f"Board {PORT}")
    score_path = search.score_script if search.score_script is not None else ROOT / circuit.score_script
    if not score_path.is_file():
        raise SystemExit(f"Fitness script not found: {score_path}")
    module = score_path.stem
    out_dir = output_dir(circuit, search)
    out_dir.mkdir(parents=True, exist_ok=True)

    asc_path = ROOT / circuit.asc
    asc_lines = asc_path.read_text().splitlines()
    positions, original, sections = load_tile(asc_lines, *circuit.tile)
    ones = [pos for pos, bit in zip(positions, original) if bit == 1]
    _, fault_in_ones = split_fault(ones, search.bits, search.seed)
    fault_positions = {ones[i] for i in fault_in_ones}
    fault_indexes = {i for i, pos in enumerate(positions) if pos in fault_positions}
    damaged = tuple(0 if i in fault_indexes else bit for i, bit in enumerate(original))
    probability = search.expected_flips / len(positions)

    print(f"{circuit.title}  tile {circuit.tile[0]},{circuit.tile[1]}  {search.algorithm}")
    print(f"Fitness: {circuit.fitness if search.score_script is None else score_path}")
    print(
        f"{len(positions)} named genes, {sum(original)} start as 1, "
        f"{search.bits} of those flipped. {len(sections)} sections."
    )
    if search.algorithm == "bandit" and search.mutation == "tworate":
        print(
            f"Mutation starts at {search.expected_flips:g}/N ({search.bandit_mode}). "
            f"Half the children use half that count and half use double. A tie keeps the lower "
            f"count, and the count stays between {BANDIT_MIN_FLIPS:g}/N and {BANDIT_MAX_FLIPS:g}/N. "
            f"Seed {search.seed}."
        )
    elif search.algorithm == "bandit":
        print(
            f"Mutation flips exactly {int(search.expected_flips)} genes ({search.bandit_mode}). "
            f"Seed {search.seed}."
        )
    elif search.mutation == "heavy":
        print(
            f"Mutation draws a flip count from a power law (beta 1.5), then flips each gene "
            f"with probability count/N. Seed {search.seed}."
        )
    elif search.mutation == "tworate":
        print(
            f"Mutation starts at {search.expected_flips:g}/N. Each generation splits the children "
            f"between half that rate and double it, then keeps the rate whose children scored higher. "
            f"A tie keeps the higher rate. "
            f"Seed {search.seed}."
        )
    elif search.algorithm != "saga":
        print(
            f"Mutation p = {probability:.6f} per gene, about {search.expected_flips:g} flips. "
            f"Seed {search.seed}."
        )
    if search.algorithm == "ea":
        print(
            f"Population {search.population}, elites {search.elites}, "
            f"section share {search.section_share:g}, generations {search.generations}."
        )
    elif search.algorithm == "inchworm":
        print(
            f"Population {search.population}, elites {search.elites}, "
            f"section share {search.section_share:g}, generations {search.generations}."
        )
        print(
            f"Base mutation is {search.expected_flips:g}/N. After {INCHWORM_STUCK_GENERATIONS} "
            f"generations at one best score, the {INCHWORM_BOOST_COUNT} children with the weakest "
            f"parents gain {INCHWORM_BOOST_FLIPS}/N, then another {INCHWORM_BOOST_FLIPS}/N every "
            f"{INCHWORM_BOOST_EVERY} generations, up to {INCHWORM_MAX_FLIPS}/N."
        )
    elif search.algorithm == "saga":
        print(
            f"Population {search.population}, elites {search.elites}, "
            f"section share {search.section_share:g}, generations {search.generations}."
        )
        print(
            f"SAGA. Fault seed {search.seed}, evolution seed {search.seed + 1}. "
            f"Generation 0 is {SAGA_SEED_COPIES} copies of the damaged genome and "
            f"{SAGA_POPULATION - SAGA_SEED_COPIES} mutants at {SAGA_INITIAL_FLIPS}/N."
        )
        print(
            f"One elite. A strict gain replaces it and returns the rate to {SAGA_BASE_FLIPS}/N. "
            f"A different tie can replace it and does not reset the rate. "
            f"The {SAGA_BOTTOM} weakest-parent children use {SAGA_BASE_FLIPS}, then "
            f"+{SAGA_STEP_FLIPS} at stall {SAGA_FIRST_STALL} and every {SAGA_STALL_EVERY} "
            f"generations, holding at {SAGA_MAX_FLIPS}/N. The other children stay at "
            f"{SAGA_BASE_FLIPS}/N. A perfect score does not stop the run."
        )
    elif search.algorithm == "bandit":
        print(
            f"Population {search.population}, elites {search.elites}, "
            f"section share {search.section_share:g}, generations {search.generations}."
        )
        if search.bandit_mode == "ucb":
            print(
                "UCB reward is +1 only when the mutant scores higher than the crossover child. "
                "A drop and an unchanged score both pay 0, and the visit still counts. "
                "That scalar is a proxy for the output vector: "
                "a different output with the same match count counts as no change. "
                "Selection uses the mutant's fitness and does not read the reward. "
                "An uncached crossover child is an extra board evaluation."
            )
    else:
        print(
            f"Hill climber, population {search.population}, "
            f"{search.generations} steps, accept {search.accept}. "
            f"A tie is {'kept' if search.accept == 'neutral' else 'rejected'}."
        )
    for index in sorted(fault_indexes):
        line, col = positions[index]
        print(f"  fault bit {index}: line {line} col {col}")

    checkpoint_path = out_dir / "checkpoint.json"
    command = command_line(circuit, search)
    n_flips = int(search.expected_flips)
    cache: dict[tuple[int, ...], float] = {}
    physical_evals = 0

    def pack_cache() -> dict[str, float]:
        return {genome_key(genome): score for genome, score in cache.items()}

    def pack_carried(carried_now) -> dict[str, float]:
        return {genome_key(genome): score for genome, score in carried_now.items()}

    def write_checkpoint() -> None:
        atomic_json(checkpoint_path, saved)

    def write_recovery() -> None:
        payload = {
            "command": command,
            "circuit": circuit.name,
            "algorithm": search.algorithm,
            "tile": list(circuit.tile),
            "seed": search.seed,
            "evolution_seed": search.seed + 1,
            "fault_bits": search.bits,
            "fault_indexes": sorted(fault_indexes),
            "set_bits_in_tile": len(ones),
            "operable_bits": len(positions),
            "evolution_mask": "named bits in the active logic tile",
            "excluded_unnamed_bits": 57,
            "genome": "literal bitstream bit, 1 writes 1 and 0 writes 0",
            "init": (
                f"{SAGA_SEED_COPIES} copies of the damaged genome plus "
                f"{SAGA_POPULATION - SAGA_SEED_COPIES} mutants at {SAGA_INITIAL_FLIPS}/N"
                if search.algorithm == "saga"
                else "1 damaged genome plus exact-flip mutants of it"
                if search.algorithm == "bandit"
                else "damaged genome" if search.population == 1 else "1 damaged genome plus mutants of it"
            ),
            "crossover": None if search.algorithm == "hill" else "one section from one parent",
            "sections": len(sections),
            "fitter_section_share": None if search.algorithm == "hill" else search.section_share,
            "accept": search.accept if search.algorithm == "hill" else None,
            "positions": [{"line": line, "col": col} for line, col in positions],
            "mutation_type": (
                "SAGA" if search.algorithm == "saga"
                else "EXACT" if search.algorithm == "bandit"
                else "HEAVY_TAIL" if search.mutation == "heavy"
                else "TWO_RATE" if search.mutation == "tworate"
                else "SIMPLE"
            ),
            "mutation": search.mutation,
            "expected_flips": search.expected_flips,
            "mutation_probability_per_bit": None if search.algorithm == "bandit" else probability,
            "bandit": None if search.algorithm != "bandit" else {
                "mode": search.bandit_mode,
                "flips": n_flips,
                "rate": "two_rate" if search.mutation == "tworate" else "fixed",
                "min_flips": BANDIT_MIN_FLIPS if search.mutation == "tworate" else None,
                "max_flips": BANDIT_MAX_FLIPS if search.mutation == "tworate" else None,
                "tie": "lower" if search.mutation == "tworate" else None,
                "reward": "rise +1, otherwise 0",
                "ucb_c": None if search.bandit_mode == "uniform" else UCB_C,
                "impact_basis": None if search.bandit_mode == "uniform" else IMPACT_BASIS,
                "arms": None if search.bandit_mode == "uniform" else len(sections),
            },
            "selection": None if search.algorithm == "hill" else "FIT_PROP_SEL",
            "saga": None if search.algorithm != "saga" else {
                "seed": search.seed,
                "evolution_seed": search.seed + 1,
                "seed_copies": SAGA_SEED_COPIES,
                "initial_mutants": SAGA_POPULATION - SAGA_SEED_COPIES,
                "initial_flips": SAGA_INITIAL_FLIPS,
                "base_flips": SAGA_BASE_FLIPS,
                "step_flips": SAGA_STEP_FLIPS,
                "max_flips": SAGA_MAX_FLIPS,
                "first_stall": SAGA_FIRST_STALL,
                "stall_every": SAGA_STALL_EVERY,
                "bottom_children": SAGA_BOTTOM,
                "drift_window": SAGA_DRIFT_WINDOW,
                "stop_at_perfect": False,
                "elite": "strict gain, else a random different tie, else keep",
                "crossover": "one section from either parent with equal probability",
            },
            "inchworm": None if search.algorithm != "inchworm" else {
                "stuck_generations": INCHWORM_STUCK_GENERATIONS,
                "boost_every": INCHWORM_BOOST_EVERY,
                "boost_flips": INCHWORM_BOOST_FLIPS,
                "max_flips": INCHWORM_MAX_FLIPS,
                "boost_count": INCHWORM_BOOST_COUNT,
                "base_flips": search.expected_flips,
            },
            "population_size": search.population,
            "generations_budget": search.generations,
            "elitism_count": 0 if search.algorithm == "hill" else search.elites,
            "target_fitness": None if search.algorithm == "saga" else TARGET,
            "fitness": circuit.fitness if search.score_script is None else str(score_path),
            "score_script": str(score_path),
            "recovered": recovered_at is not None,
            "recovery": recovered_at,
            "physical_evals": physical_evals,
            "unique_genomes_tested": len(cache),
            "history": history,
            "cache": pack_cache(),
            "checkpoint": str(checkpoint_path),
        }
        atomic_json(out_dir / "recovery.json", payload)

    def fitness_of(genome) -> float:
        nonlocal physical_evals

        def evaluate(item):
            candidate_asc = out_dir / "candidate.asc"
            candidate_bin = out_dir / "candidate.bin"
            candidate_asc.write_text("\n".join(apply_genome(asc_lines, positions, item)) + "\n")
            subprocess.run(["icepack", str(candidate_asc), str(candidate_bin)], check=True)
            upload_bitstream(candidate_bin, "candidate.bin", score_path, f"{module}.py")
            return score_on_board(module, "candidate.bin")

        score, physical = lookup_fitness(genome, cache, evaluate)
        if physical:
            physical_evals += 1
            saved["cache"] = pack_cache()
            saved["physical_evals"] = physical_evals
            write_checkpoint()
            print(
                f"  eval dist={hamming(genome, original)} -> {score:.3f}  "
                f"(physical #{physical_evals})"
            )
        return score

    if checkpoint_path.is_file():
        saved = json.loads(checkpoint_path.read_text())
        if saved.get("command") != command:
            raise SystemExit(f"Checkpoint in {out_dir} belongs to a different command.")
        rng = random.Random()
        rng_from_json(rng, saved["rng"])
        pop = [genome_from_key(text) for text in saved["pop"]]
        carried = {genome_from_key(text): score for text, score in saved["carried"].items()}
        cache = {genome_from_key(text): score for text, score in saved["cache"].items()}
        physical_evals = saved["physical_evals"]
        history = saved["history"]
        born = saved["born"]
        plateau_best = saved["plateau_best"]
        generations_at_best = saved["generations_at_best"]
        recovered_at = saved["recovered_at"]
        bandit = None
        if search.algorithm == "bandit" and search.bandit_mode == "ucb":
            bandit = MutationBandit(sections, n_flips, UCB_C)
            if saved["bandit"] is not None:
                bandit.restore(saved["bandit"])
        print(
            f"Resuming at generation {saved['next_generation']} "
            f"({saved['phase']}), {physical_evals} physical evals already saved."
        )
    else:
        rng = random.Random(search.seed + 1)
        if search.algorithm == "bandit":
            pop = initial_exact(damaged, search.population, rng, n_flips)
            bandit = MutationBandit(sections, n_flips, UCB_C) if search.bandit_mode == "ucb" else None
        elif search.algorithm == "saga":
            pop, init_strengths = saga_initial(damaged, rng)
            bandit = None
        elif search.mutation == "heavy":
            pop, init_strengths = heavy_initial(damaged, search.population, rng)
            bandit = None
        else:
            pop = initial_population(search.algorithm, damaged, search.population, rng, probability)
            bandit = None
            init_strengths = None
        carried = {}
        history = []
        born = []
        recovered_at = None
        plateau_best = None
        generations_at_best = 0
        saved = {
            "command": command,
            "next_generation": 0,
            "phase": "ready",
            "pop": [genome_key(genome) for genome in pop],
            "scores": None,
            "carried": {},
            "born": [],
            "history": [],
            "cache": {},
            "physical_evals": 0,
            "rng": rng_to_json(rng),
            "bandit": None if bandit is None else bandit.snapshot(),
            "plateau_best": None,
            "generations_at_best": 0,
            "recovered_at": None,
            "done": False,
            "mutation_strength": search.expected_flips if search.mutation == "tworate" else None,
            "child_strengths": init_strengths if search.mutation == "heavy" or search.algorithm == "saga" else None,
            "saga_stall": 0,
            "saga_elite_score": None,
        }
        write_checkpoint()
        print(f"Checkpoint {checkpoint_path}")

    use_board = not saved.get("done")
    try:
        if use_board:
            print("Opening one serial session for upload and score.")
            BOARD.call(lambda: None)
            print("Clearing the board filesystem. Results stay in the output folder.")
            free_board_space(f"{module}.py")
            upload(score_path, f"{module}.py")

        while saved["next_generation"] <= search.generations and not saved.get("done"):
            generation = saved["next_generation"]
            if saved["phase"] == "ready":
                free_board_space(f"{module}.py")
                if search.algorithm == "hill" and generation > 0:
                    nxt = []
                    nxt_scores = []
                    for genome, score in zip(pop, saved["scores"]):
                        challenger = mutate(genome, rng, probability)
                        challenger_score = fitness_of(challenger)
                        if hill_keep(score, challenger_score, search.accept):
                            nxt.append(challenger)
                            nxt_scores.append(challenger_score)
                        else:
                            nxt.append(genome)
                            nxt_scores.append(score)
                    pop = nxt
                    scores = nxt_scores
                else:
                    kept = sum(genome in carried for genome in pop)
                    if kept:
                        print(f"kept {kept} unchanged elites")
                    scores = [carried[genome] if genome in carried else fitness_of(genome) for genome in pop]

                saga_outcome = None
                if search.algorithm == "saga":
                    elite, saga_outcome = choose_elite(pop[0], scores[0], pop[1:], scores[1:], rng)
                    pop, scores = place_elite_first(pop, scores, elite)
                    stall = update_stall(
                        saved.get("saga_elite_score"), scores[0], saved.get("saga_stall", 0)
                    )
                    saved["saga_stall"] = stall
                    saved["saga_elite_score"] = scores[0]

                best_i = 0 if search.algorithm == "saga" else max(range(len(pop)), key=lambda i: scores[i])
                best_f = scores[best_i]
                if plateau_best is None or best_f > plateau_best:
                    plateau_best = best_f
                    generations_at_best = 1
                else:
                    generations_at_best += 1
                if search.algorithm == "inchworm":
                    bottom_flips = inchworm_boosted_flips(generations_at_best, search.expected_flips)
                elif search.algorithm == "saga":
                    bottom_flips = saga_flips(saved["saga_stall"])
                else:
                    bottom_flips = search.expected_flips
                scored_strengths = saved.get("child_strengths")
                if search.mutation == "tworate" and scored_strengths:
                    if search.algorithm == "bandit":
                        saved["mutation_strength"] = adopt_bandit_rate(
                            scored_strengths, scores[search.elites:]
                        )
                    else:
                        saved["mutation_strength"] = adopt_tworate(
                            scored_strengths, scores[search.elites:], len(positions)
                        )
                row = {
                    "generation": generation,
                    "best_fitness": best_f,
                    "mean_fitness": sum(scores) / len(scores),
                    "mean_pairwise_hamming": mean_pairwise_hamming(pop),
                    "best_distance_to_original": hamming(pop[best_i], original),
                    "best_genome": list(pop[best_i]),
                    "population": [genome_key(genome) for genome in pop],
                    "scores": list(scores),
                    "physical_evals": physical_evals,
                    "generations_at_best": generations_at_best,
                    "bottom_expected_flips": bottom_flips,
                }
                if scored_strengths:
                    row["mutation_strengths"] = scored_strengths
                if search.algorithm == "saga":
                    current = row["population"]
                    row.update(drift_record([item["population"] for item in history], current))
                    row["tie_fraction"] = tie_fraction(scores)
                    row["stall"] = saved["saga_stall"]
                    row["schedule_flips"] = bottom_flips
                    row["elite_outcome"] = saga_outcome
                    row["mutation_level"] = max(scored_strengths) if scored_strengths else None
                if search.mutation == "tworate":
                    row["mutation_strength"] = saved["mutation_strength"]
                if born:
                    row["offspring"] = born
                    born = []
                history.append(row)
                extra = ""
                if search.algorithm == "saga":
                    extra = (
                        f" stall={saved['saga_stall']} next={bottom_flips}/N "
                        f"ties={row['tie_fraction']:.2f} "
                        f"elite_drift={row['elite_drift_from_start']} "
                        f"{saga_outcome}"
                    )
                elif search.algorithm == "inchworm":
                    extra = f" stuck={generations_at_best} bottom={bottom_flips:g}/N"
                elif search.mutation == "tworate":
                    extra = f" rate={saved['mutation_strength']:g}/N"
                elif search.mutation == "heavy" and scored_strengths:
                    extra = f" mean flips={sum(scored_strengths) / len(scored_strengths):.1f}"
                print(
                    f"gen {generation}: best={best_f:.3f} mean={row['mean_fitness']:.3f} "
                    f"hamming={row['mean_pairwise_hamming']:.2f} "
                    f"dist={row['best_distance_to_original']}{extra}"
                )
                if best_f >= TARGET and recovered_at is None:
                    recovered_at = row
                best_asc = out_dir / "best.asc"
                best_genome = tuple(max(history, key=lambda item: (item["best_fitness"], -item["best_distance_to_original"]))["best_genome"])
                best_asc.write_text("\n".join(apply_genome(asc_lines, positions, best_genome)) + "\n")
                saved.update({
                    "phase": "scored",
                    "scores": scores,
                    "pop": [genome_key(genome) for genome in pop],
                    "carried": pack_carried(carried),
                    "born": born,
                    "history": history,
                    "cache": pack_cache(),
                    "physical_evals": physical_evals,
                    "rng": rng_to_json(rng),
                    "bandit": None if bandit is None else bandit.snapshot(),
                    "plateau_best": plateau_best,
                    "generations_at_best": generations_at_best,
                    "recovered_at": recovered_at,
                    "mutation_strength": saved.get("mutation_strength"),
                    "child_strengths": saved.get("child_strengths"),
                })
                write_checkpoint()
                write_recovery()
            else:
                scores = saved["scores"]
                print(f"generation {generation} already scored; breeding its children")

            finished = generation == search.generations or (
                stops_at_perfect(search.algorithm) and recovered_at is not None
            )
            if finished:
                saved["done"] = True
                write_checkpoint()
                write_recovery()
                break

            if search.algorithm == "ea" and search.mutation == "heavy":
                pop, carried, strengths = heavy_next(
                    pop, scores, sections, rng, search.section_share, search.elites
                )
                saved["child_strengths"] = strengths
                born = []
            elif search.algorithm == "ea" and search.mutation == "tworate":
                pop, carried, strengths = tworate_next(
                    pop, scores, sections, rng, saved["mutation_strength"],
                    search.section_share, search.elites,
                )
                saved["child_strengths"] = strengths
                born = []
            elif search.algorithm == "ea":
                pop, carried = ea_next(
                    pop, scores, sections, rng, probability, search.section_share, search.elites
                )
                born = []
            elif search.algorithm == "saga":
                level = saga_flips(saved.get("saga_stall", 0))
                pop, carried, strengths = saga_next(
                    pop, scores, rng, sections, search.section_share, level, SAGA_BASE_FLIPS
                )
                saved["child_strengths"] = [0, *strengths]
                born = []
            elif search.algorithm == "inchworm":
                boosted = (
                    inchworm_boosted_flips(generations_at_best, search.expected_flips) / len(positions)
                )
                pop, carried = inchworm_next(
                    pop, scores, sections, rng, probability, boosted, search.section_share, search.elites
                )
                born = []
            elif search.algorithm == "bandit" and search.mutation == "tworate":
                rates = bandit_child_rates(search.population - search.elites, saved["mutation_strength"])
                pop, carried, born = bandit_next(
                    pop,
                    scores,
                    sections,
                    rng,
                    search.section_share,
                    search.elites,
                    n_flips,
                    bandit,
                    fitness_of,
                    lambda: physical_evals,
                    child_rates=rates,
                )
                saved["child_strengths"] = rates
            elif search.algorithm == "bandit":
                pop, carried, born = bandit_next(
                    pop,
                    scores,
                    sections,
                    rng,
                    search.section_share,
                    search.elites,
                    n_flips,
                    bandit,
                    fitness_of,
                    lambda: physical_evals,
                )
            saved.update({
                "next_generation": generation + 1,
                "phase": "ready",
                "pop": [genome_key(genome) for genome in pop],
                "scores": scores,
                "carried": pack_carried(carried),
                "born": born,
                "history": history,
                "cache": pack_cache(),
                "physical_evals": physical_evals,
                "rng": rng_to_json(rng),
                "bandit": None if bandit is None else bandit.snapshot(),
                "plateau_best": plateau_best,
                "generations_at_best": generations_at_best,
            "recovered_at": recovered_at,
            "done": False,
            "mutation_strength": saved.get("mutation_strength"),
            "child_strengths": saved.get("child_strengths"),
        })
            write_checkpoint()
            write_recovery()

    finally:
        if use_board:
            BOARD.close()

    if not history:
        raise SystemExit(f"No generations saved in {checkpoint_path}")
    best = max(history, key=lambda row: (row["best_fitness"], -row["best_distance_to_original"]))
    best_genome = tuple(best["best_genome"])
    best_asc = out_dir / "best.asc"
    best_asc.write_text("\n".join(apply_genome(asc_lines, positions, best_genome)) + "\n")
    subprocess.run(
        [
            str(ROOT / ".venv" / "bin" / "python"),
            str(PLOT),
            "--preset",
            circuit.preset,
            "--asc",
            str(best_asc),
            "--out",
            str(out_dir / "final_circuit.png"),
        ],
        check=True,
        env={**os.environ, "MPLCONFIGDIR": str(ROOT / ".mplconfig")},
    )
    write_plots(history, out_dir, circuit, search, len(positions))
    if search.algorithm == "saga":
        from analysis.plot_saga import write as write_saga

        write_saga(history, out_dir, f"{circuit.title} — saga — {search.bits}-bit fault")
    write_recovery()
    print(f"Wrote {out_dir}")
    if recovered_at:
        print(
            f"Recovered at generation {recovered_at['generation']} "
            f"after {recovered_at['physical_evals']} physical evals. "
            f"Best distance to original: {recovered_at['best_distance_to_original']}"
        )
    else:
        print(f"No recovery. Best fitness {best['best_fitness']:.3f}")


def main(default_circuit: str | None = None) -> None:
    args = parser(default_circuit).parse_args()
    if args.list:
        print(describe())
        return
    if args.circuit is None:
        print(describe())
        raise SystemExit("pass --circuit")
    run(CIRCUITS[args.circuit], resolve(args, CIRCUITS[args.circuit]))


if __name__ == "__main__":
    main()
