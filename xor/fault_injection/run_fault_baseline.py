"""
XOR config-bit fault baseline.

Flips N bits among the non-zero bits in the active XOR logic tile
(.logic_tile 8 1 from nextpnr), packs each ASC, loads on pico2-ice,
and scores truth-table accuracy. Runs multiple seeds and averages
success per severity. Severities: 0 (original), 1, 2, 4, 8.
"""

from __future__ import annotations

import json
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ASC = ROOT / "xor" / "build" / "xor.asc"
OUT_DIR = Path(__file__).resolve().parent / "out"
MPREMOTE = ROOT / ".venv" / "bin" / "mpremote"
PORT = "/dev/cu.usbmodem1101"
SEEDS = [42, 7, 99, 123]
SEVERITIES = [0, 1, 2, 4, 8]
TILE_X, TILE_Y = 8, 1


def find_nonzero_bits(asc_lines: list[str], tile_x: int, tile_y: int):
    header = f".logic_tile {tile_x} {tile_y}"
    try:
        start = asc_lines.index(header)
    except ValueError as exc:
        raise SystemExit(f"Missing {header} in ASC") from exc

    bits = []
    for row in range(16):
        line_idx = start + 1 + row
        row_bits = asc_lines[line_idx].strip()
        for col, ch in enumerate(row_bits):
            if ch == "1":
                bits.append((line_idx, col))
    return start, bits


def flip_bits(asc_lines: list[str], positions: list[tuple[int, int]]) -> list[str]:
    out = asc_lines[:]
    for line_idx, col in positions:
        row = list(out[line_idx].rstrip("\n"))
        row[col] = "0" if row[col] == "1" else "1"
        out[line_idx] = "".join(row)
    return out


def icepack(asc_path: Path, bin_path: Path) -> None:
    subprocess.run(["icepack", str(asc_path), str(bin_path)], check=True)


def mpremote(*args: str, retries: int = 4) -> str:
    cmd = [str(MPREMOTE), "connect", PORT, *args]
    last = None
    for attempt in range(retries):
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout + result.stderr
        last = result
        time.sleep(1.0 + attempt)
    raise subprocess.CalledProcessError(
        last.returncode, last.args, output=last.stdout, stderr=last.stderr
    )


def upload(local: Path, remote: str) -> None:
    mpremote("fs", "cp", str(local), f":{remote}")


def score_on_board(remote_bin: str) -> dict:
    code = (
        "import truth_table_score\n"
        f"truth_table_score.score({remote_bin!r})\n"
        "print('SCORE_COMPLETE')\n"
    )
    out = mpremote("exec", code)
    matches = total = None
    per_pattern = {(0, 0): [], (0, 1): [], (1, 0): [], (1, 1): []}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("DATA,"):
            parts = line.split(",")
            if len(parts) == 6 and parts[1] != "A":
                _, a, b, expected, measured, match = parts
                a, b, expected, measured, match = map(
                    int, (a, b, expected, measured, match)
                )
                per_pattern[(a, b)].append(
                    {
                        "expected": expected,
                        "measured": measured,
                        "match": match,
                    }
                )
        elif line.startswith("RESULT,"):
            _, _name, m, t, _acc = line.split(",")
            matches, total = int(m), int(t)
    if matches is None or total is None:
        raise RuntimeError(f"Could not parse score output:\n{out}")
    return {
        "matches": matches,
        "total": total,
        "accuracy": matches / total,
        "passed": matches == total,
        "per_pattern": {
            f"{a}{b}": vals for (a, b), vals in per_pattern.items()
        },
        "raw": out,
    }


def run_seed(seed: int, asc_lines: list[str], ones: list[tuple[int, int]]) -> dict:
    rng = random.Random(seed)
    if len(ones) < max(SEVERITIES):
        raise SystemExit(f"Need at least {max(SEVERITIES)} ones; found {len(ones)}")
    chosen = rng.sample(ones, max(SEVERITIES))

    results = []
    for n in SEVERITIES:
        label = f"xor_s{seed}_f{n}"
        asc_path = OUT_DIR / f"{label}.asc"
        bin_path = OUT_DIR / f"{label}.bin"
        flipped = chosen[:n]
        damaged = flip_bits(asc_lines, flipped) if n else asc_lines
        asc_path.write_text("\n".join(damaged) + "\n")
        icepack(asc_path, bin_path)
        # Reuse one remote name so the board does not fill up mid-sweep.
        remote_bin = "candidate.bin"
        upload(bin_path, remote_bin)
        print(f"  seed={seed} flips={n} scoring...")
        score = score_on_board(remote_bin)
        entry = {
            "label": label,
            "seed": seed,
            "flips": n,
            "positions": [
                {"line": line, "col": col, "tile": f"{TILE_X},{TILE_Y}"}
                for line, col in flipped
            ],
            "accuracy": score["accuracy"],
            "matches": score["matches"],
            "total": score["total"],
            "passed": score["passed"],
            "per_pattern_summary": {
                key: {
                    "matches": sum(v["match"] for v in vals),
                    "total": len(vals),
                }
                for key, vals in score["per_pattern"].items()
            },
        }
        results.append(entry)
        status = "PASS" if entry["passed"] else "FAIL"
        print(
            f"    {status}  accuracy={entry['accuracy']:.2%}  "
            f"{entry['matches']}/{entry['total']}"
        )
    return {
        "seed": seed,
        "chosen_positions": [{"line": line, "col": col} for line, col in chosen],
        "results": results,
    }


def average_by_severity(seed_runs: list[dict]) -> list[dict]:
    averages = []
    for n in SEVERITIES:
        accs = []
        passes = []
        for run in seed_runs:
            for r in run["results"]:
                if r["flips"] == n:
                    accs.append(r["accuracy"])
                    passes.append(1.0 if r["passed"] else 0.0)
        averages.append(
            {
                "flips": n,
                "mean_accuracy": statistics.mean(accs),
                "stdev_accuracy": statistics.stdev(accs) if len(accs) > 1 else 0.0,
                "mean_pass_rate": statistics.mean(passes),
                "n_seeds": len(accs),
                "accuracies": accs,
                "passes": [bool(p) for p in passes],
            }
        )
    return averages


def write_plot(averages: list[dict], seed_runs: list[dict], png_path: Path) -> None:
    import matplotlib.pyplot as plt

    xs = [str(a["flips"]) for a in averages]
    means = [a["mean_accuracy"] * 100 for a in averages]
    stdevs = [a["stdev_accuracy"] * 100 for a in averages]
    pass_rates = [a["mean_pass_rate"] * 100 for a in averages]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    colors = ["#2a7a4b" if m >= 99.9 else "#b33a3a" for m in means]
    ax1.bar(xs, means, yerr=stdevs, capsize=5, color=colors, alpha=0.85, zorder=2)
    # overlay per-seed points
    for i, n in enumerate(SEVERITIES):
        for run in seed_runs:
            for r in run["results"]:
                if r["flips"] == n:
                    ax1.scatter(
                        i,
                        r["accuracy"] * 100,
                        color="#222222",
                        s=28,
                        zorder=3,
                    )
    ax1.set_ylim(0, 110)
    ax1.set_xlabel("Flipped config bits")
    ax1.set_ylabel("Truth-table accuracy (%)")
    ax1.set_title("Mean accuracy ± stdev (4 seeds)")
    for i, a in enumerate(averages):
        ax1.text(
            i,
            means[i] + stdevs[i] + 3,
            f"{means[i]:.0f}%",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    ax2.bar(xs, pass_rates, color="#3a6ea5", alpha=0.9)
    ax2.set_ylim(0, 110)
    ax2.set_xlabel("Flipped config bits")
    ax2.set_ylabel("Full-pass rate (%)")
    ax2.set_title("Fraction of seeds with 20/20 pass")
    for i, pr in enumerate(pass_rates):
        ax2.text(i, pr + 3, f"{pr:.0f}%", ha="center", va="bottom", fontsize=9)

    fig.suptitle(
        "XOR fault baseline — averaged over seeds "
        + ", ".join(str(s) for s in SEEDS),
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(png_path, dpi=160)
    plt.close(fig)


def main() -> int:
    if not MPREMOTE.exists():
        print(f"mpremote not found at {MPREMOTE}", file=sys.stderr)
        return 1
    if not SRC_ASC.exists():
        print(f"Missing ASC: {SRC_ASC}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    asc_lines = SRC_ASC.read_text().splitlines()
    _tile_start, ones = find_nonzero_bits(asc_lines, TILE_X, TILE_Y)
    print(
        f"Active tile .logic_tile {TILE_X} {TILE_Y}: {len(ones)} non-zero bits"
    )
    print(f"Seeds: {SEEDS}")

    upload(ROOT / "xor" / "board" / "truth_table_score.py", "truth_table_score.py")

    seed_runs = []
    checkpoint = OUT_DIR / "fault_baseline_partial.json"
    for seed in SEEDS:
        print(f"=== seed {seed} ===")
        seed_runs.append(run_seed(seed, asc_lines, ones))
        checkpoint.write_text(
            json.dumps({"seeds_done": [r["seed"] for r in seed_runs], "seed_runs": seed_runs}, indent=2)
        )

    averages = average_by_severity(seed_runs)
    print("\n=== averages ===")
    for a in averages:
        print(
            f"flips={a['flips']}: mean_accuracy={a['mean_accuracy']:.2%} "
            f"(stdev={a['stdev_accuracy']:.2%}), "
            f"pass_rate={a['mean_pass_rate']:.0%} "
            f"over {a['n_seeds']} seeds"
        )

    payload = {
        "seeds": SEEDS,
        "tile": [TILE_X, TILE_Y],
        "source_asc": str(SRC_ASC.relative_to(ROOT)),
        "nonzero_bits_in_tile": len(ones),
        "seed_runs": seed_runs,
        "averages": averages,
    }
    out_json = OUT_DIR / "fault_baseline_results.json"
    out_json.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {out_json}")

    png = OUT_DIR / "fault_baseline_accuracy.png"
    write_plot(averages, seed_runs, png)
    print(f"Wrote {png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
