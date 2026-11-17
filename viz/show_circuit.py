"""Draw a pico2-ice bitstream as the pads and the logic cells that use them.

Paste an ASC, or pass an ASC or packed BIN. Presets know this board's XOR
and adder pin maps. Empty fabric is left out. A marked gap is the real
tile distance, and each used logic cell is drawn large enough to show its
function and the wires that reach it.

    python viz/show_circuit.py adder4/build/adder4.asc --preset adder4
    python viz/show_circuit.py --preset xor --asc - < evolved.asc
    python viz/show_circuit.py best.asc --pcf adder4/rtl/adder4.pcf --tile 17,1 -o out.png
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]

PRESETS: dict[str, dict] = {
    "xor": {
        "pcf": ROOT / "xor" / "rtl" / "xor.pcf",
        "tile": (8, 1),
        "gpio": {"a": "GPIO2", "b": "GPIO3", "y": "GPIO33"},
    },
    "adder2": {
        "pcf": ROOT / "adder2" / "rtl" / "adder2.pcf",
        "tile": (20, 20),
        "gpio": {
            "a0": "GPIO20",
            "a1": "GPIO24",
            "b0": "GPIO30",
            "b1": "GPIO25",
            "s0": "GPIO22",
            "s1": "GPIO23",
            "cout": "GPIO27",
        },
    },
    "adder4": {
        "pcf": ROOT / "adder4" / "rtl" / "adder4.pcf",
        "tile": (17, 1),
        "gpio": {
            "a0": "GPIO20",
            "a1": "GPIO24",
            "a2": "GPIO30",
            "a3": "GPIO25",
            "b0": "GPIO28",
            "b1": "GPIO29",
            "b2": "GPIO2",
            "b3": "GPIO3",
            "s0": "GPIO22",
            "s1": "GPIO23",
            "s2": "GPIO27",
            "s3": "GPIO26",
            "cout": "GPIO33",
        },
    },
}

WIRE_COLORS = [
    "#1f4e79",
    "#c0392b",
    "#1e8449",
    "#b9770e",
    "#6c3483",
    "#0e6655",
    "#a93226",
    "#1a5276",
    "#9a7d0a",
    "#4a235a",
    "#117a65",
    "#ca6f1e",
    "#1b4f72",
    "#7b241c",
    "#196f3d",
    "#6e2c00",
]

RESOURCE_RE = re.compile(r"// \((\d+), (\d+), '([^']+)'\)")
ASSIGN_RE = re.compile(
    r"assign\s+(\w+)\s+=\s+/\*\s*(LUT|CARRY)\s+(\d+)\s+(\d+)\s+(\d+)\s*\*/\s*(.+?)\s*;"
)
FF_RE = re.compile(
    r"/\*\s*FF\s+(\d+)\s+(\d+)\s+(\d+)\s*\*/\s*assign\s+(\w+)\s+=\s+(\w+)\s*;"
)
ZERO_RE = re.compile(r"assign\s+(\w+)\s+=\s+0\s*;")
PAD_RE = re.compile(r"io_(\d+)/PAD")
LUT_IN_RE = re.compile(r"lutff_(\d+)/in_(\d+)")
LUT_OUT_RE = re.compile(r"lutff_(\d+)/out$")
COUT_RE = re.compile(r"lutff_(\d+)/cout")


@dataclass
class Signal:
    name: str
    direction: str
    pin: str
    gpio: str
    pad: tuple[int, int]
    lut: tuple[int, int]
    sinks: list[tuple[int, int]] = field(default_factory=list)
    sources: list[int] = field(default_factory=list)
    vertical: bool = False
    kinds: set[int] = field(default_factory=set)
    span_points: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class Cell:
    index: int
    used: bool = False
    equation: str = ""
    output: str = ""
    inputs: dict[int, str] = field(default_factory=dict)


def find_chipdb() -> Path:
    candidates: list[Path] = []
    exe = shutil.which("icebox_vlog")
    if exe:
        install = Path(exe).resolve().parent.parent
        candidates.append(install / "share" / "icestorm" / "chipdb" / "chipdb-5k.txt")
    candidates.extend(
        [
            Path("/opt/homebrew/share/icestorm/chipdb/chipdb-5k.txt"),
            Path("/usr/local/share/icestorm/chipdb/chipdb-5k.txt"),
            Path("/usr/share/icestorm/chipdb/chipdb-5k.txt"),
        ]
    )
    cellar = Path("/opt/homebrew/Cellar/icestorm")
    if cellar.is_dir():
        candidates.extend(sorted(cellar.glob("*/share/icestorm/chipdb/chipdb-5k.txt")))
    for path in candidates:
        if path.is_file():
            return path
    raise SystemExit("chipdb-5k.txt not found. Install Project IceStorm (icebox_vlog).")


def load_sg48(chipdb: Path) -> dict[tuple[int, int, int], str]:
    """Map (tile x, tile y, pio) to the sg48 package pin number."""
    lines = chipdb.read_text().splitlines()
    try:
        start = lines.index(".pins sg48") + 1
    except ValueError:
        raise SystemExit(f"No sg48 pin table in {chipdb}")
    pins: dict[tuple[int, int, int], str] = {}
    for line in lines[start:]:
        if not line or line.startswith("."):
            break
        num, x, y, pio = line.split()
        pins[(int(x), int(y), int(pio))] = num
    return pins


def load_pcf(path: Path | None) -> dict[str, str]:
    """Map package pin number to signal name."""
    if path is None or not path.is_file():
        return {}
    signals: dict[str, str] = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "set_io":
            signals[parts[2]] = parts[1]
    return signals


def run_vlog(asc: Path, pcf: Path | None) -> str:
    cmd = ["icebox_vlog", "-d", "sg48", str(asc)]
    if pcf is not None and pcf.is_file():
        cmd[1:1] = ["-p", str(pcf)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SystemExit(detail or "icebox_vlog failed")
    return result.stdout


def parse_groups(text: str) -> list[list[tuple[int, int, str]]]:
    groups: list[list[tuple[int, int, str]]] = []
    current: list[tuple[int, int, str]] = []
    for raw in text.splitlines():
        match = RESOURCE_RE.match(raw.strip())
        if match:
            current.append((int(match.group(1)), int(match.group(2)), match.group(3)))
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def axis_of(resource: str) -> str | None:
    if not resource.startswith(("sp4_", "sp12_", "span4_", "span12_")):
        return None
    if "vert" in resource or "_v_" in resource:
        return "v"
    if "horz" in resource or "_h_" in resource:
        return "h"
    return None


def span_len(resource: str) -> int | None:
    if resource.startswith(("sp12_", "span12_")):
        return 12
    if resource.startswith(("sp4_", "span4_")):
        return 4
    return None


def parse_vlog(text: str, pin_at: dict[tuple[int, int, int], str], pcf: dict[str, str], gpio: dict[str, str], focus: tuple[int, int] | None):
    ports: dict[str, str] = {}
    for match in re.finditer(r"\b(input|output)\s+(\w+)", text):
        ports[match.group(2)] = "IN" if match.group(1) == "input" else "OUT"

    wire_labels: dict[str, str] = {}
    lut_expr: dict[tuple[int, int, int], str] = {}
    ff_name: dict[tuple[int, int, int], str] = {}
    for match in ASSIGN_RE.finditer(text):
        wire, kind, xs, ys, lc, expr = match.groups()
        key = (int(xs), int(ys), int(lc))
        if kind == "LUT":
            lut_expr[key] = " ".join(expr.split())
        else:
            wire_labels[wire] = f"c{int(lc)}"
    for match in ZERO_RE.finditer(text):
        wire_labels[match.group(1)] = "0"
    for match in FF_RE.finditer(text):
        xs, ys, lc, name, _wire = match.groups()
        ff_name[(int(xs), int(ys), int(lc))] = name

    signals: list[Signal] = []
    carries: list[tuple[tuple[int, int], int, int]] = []
    for group in parse_groups(text):
        pads: list[tuple[int, int, int]] = []
        lut_ins: list[tuple[int, int, int, int]] = []
        lut_outs: list[tuple[int, int, int]] = []
        couts: list[tuple[int, int, int]] = []
        horiz: list[tuple[int, int, int]] = []
        vert: list[tuple[int, int, int]] = []
        for x, y, res in group:
            pad = PAD_RE.search(res)
            if pad:
                pads.append((x, y, int(pad.group(1))))
            inn = LUT_IN_RE.search(res)
            if inn:
                lut_ins.append((x, y, int(inn.group(1)), int(inn.group(2))))
            out = LUT_OUT_RE.search(res)
            if out:
                lut_outs.append((x, y, int(out.group(1))))
            cout = COUT_RE.search(res)
            if cout:
                couts.append((x, y, int(cout.group(1))))
            axis = axis_of(res)
            length = span_len(res)
            if axis == "h" and length:
                horiz.append((x, y, length))
            elif axis == "v" and length:
                vert.append((x, y, length))

        if couts and not pads:
            for tx, ty, src in couts:
                for dx, dy, dst, pin in lut_ins:
                    if pin == 3 and (dx, dy) == (tx, ty):
                        carries.append(((tx, ty), src, dst))
            continue
        if not pads or (not lut_ins and not lut_outs):
            continue

        px, py, pio = pads[0]
        pin = pin_at.get((px, py, pio), "?")
        name = pcf.get(pin, f"pin{pin}")
        direction = ports.get(name)
        if direction is None:
            direction = "OUT" if lut_outs and not lut_ins else "IN"

        if direction == "IN":
            tiles = [(x, y) for x, y, _lc, _pin in lut_ins]
            sinks = [(lc, in_pin) for _x, _y, lc, in_pin in lut_ins]
            sources: list[int] = []
        else:
            tiles = [(x, y) for x, y, _lc in lut_outs]
            sinks = []
            sources = [lc for _x, _y, lc in lut_outs]
        lut = _pick_tile(tiles, focus)
        if lut is None:
            continue

        x0, x1 = sorted((px, lut[0]))
        y0, y1 = sorted((py, lut[1]))

        def inside(pt: tuple[int, int, int]) -> bool:
            return x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1

        horiz_in = [pt for pt in horiz if inside(pt)]
        vert_in = [pt for pt in vert if inside(pt)]
        vertical = len(vert_in) >= len(horiz_in) if (vert_in or horiz_in) else abs(lut[1] - py) >= abs(lut[0] - px)
        chosen = vert_in if vertical else horiz_in
        kinds = {pt[2] for pt in chosen}
        signals.append(
            Signal(
                name=name,
                direction=direction,
                pin=pin,
                gpio=gpio.get(name, ""),
                pad=(px, py),
                lut=lut,
                sinks=_unique(sinks),
                sources=_unique(sources),
                vertical=vertical,
                kinds=kinds,
                span_points=[(pt[0], pt[1]) for pt in chosen],
            )
        )

    carries = _unique(carries)
    carries.sort(key=lambda item: (item[0], item[1], item[2]))
    signals.sort(key=lambda s: (s.direction != "IN", s.name))
    return signals, carries, lut_expr, ff_name, wire_labels


def _unique(items: list) -> list:
    seen = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def _pick_tile(tiles: list[tuple[int, int]], prefer: tuple[int, int] | None) -> tuple[int, int] | None:
    if not tiles:
        return None
    counts = Counter(tiles)
    best = counts.most_common()
    top = best[0][1]
    winners = [tile for tile, count in best if count == top]
    if prefer in winners:
        return prefer
    return winners[0]


def choose_tile(requested: tuple[int, int] | None, lut_expr: dict) -> tuple[int, int] | None:
    if requested is not None:
        return requested
    tiles = [key[:2] for key in lut_expr]
    if not tiles:
        return None
    return Counter(tiles).most_common(1)[0][0]


def span_name(kinds: set[int], run: int) -> str:
    if not kinds:
        return "local"
    if 12 in kinds and run >= 8:
        return "span-12"
    if 4 in kinds:
        return "span-4"
    if 12 in kinds:
        return "span-12"
    return "local"


def _tiles(n: int) -> str:
    return "1 tile" if n == 1 else f"{n} tiles"


def _way(axis: str, sign: int) -> str:
    if axis == "y":
        return "north" if sign > 0 else "south"
    return "east" if sign > 0 else "west"


def describe(src: tuple[int, int], dst: tuple[int, int], kinds: set[int]) -> str:
    dx = dst[0] - src[0]
    dy = dst[1] - src[1]
    if dx == 0 and dy == 0:
        return "same tile"
    span = span_name(kinds, max(abs(dx), abs(dy)))
    if abs(dx) == abs(dy):
        return f"{span}, {_tiles(abs(dx))} {_way('x', dx)} and {_tiles(abs(dy))} {_way('y', dy)}"
    if abs(dy) > abs(dx):
        return f"{span}, {_tiles(abs(dy))} {_way('y', dy)}"
    return f"{span}, {_tiles(abs(dx))} {_way('x', dx)}"


def signal_line(signal: Signal) -> str:
    gpio = f" {signal.gpio}" if signal.gpio else ""
    px, py = signal.pad
    lx, ly = signal.lut
    if signal.direction == "IN":
        ends = ", ".join(f"LC{lc} in_{pin}" for lc, pin in signal.sinks) or "LUT"
        trip = describe(signal.pad, signal.lut, signal.kinds)
        return (
            f"{signal.name:<5} IN   pin {signal.pin:<3}{gpio:<8}  "
            f"tile ({px},{py}) → {ends} at ({lx},{ly}), {trip}"
        )
    srcs = ", ".join(f"LC{lc}" for lc in signal.sources) or "LUT"
    trip = describe(signal.lut, signal.pad, signal.kinds)
    return (
        f"{signal.name:<5} OUT  pin {signal.pin:<3}{gpio:<8}  "
        f"{srcs} at ({lx},{ly}) → tile ({px},{py}), {trip}"
    )


def carry_line(tile: tuple[int, int], src: int, dst: int) -> str:
    return f"carry  LC{src} cout → LC{dst} in_3 inside tile ({tile[0]},{tile[1]})"


def cells_for(tile: tuple[int, int], signals: list[Signal], carries, lut_expr, ff_name, wire_labels) -> tuple[dict[int, Cell], list[tuple[int, int]]]:
    cells = {index: Cell(index=index) for index in range(8)}
    for key, expr in lut_expr.items():
        if key[:2] != tile:
            continue
        cell = cells[key[2]]
        cell.used = True
        cell.equation = _subst(expr, wire_labels)
        cell.output = ff_name.get(key, "")
    for signal in signals:
        if signal.lut != tile:
            continue
        if signal.direction == "IN":
            for lc, pin in signal.sinks:
                if pin == 3:
                    continue
                cells[lc].used = True
                cells[lc].inputs[pin] = signal.name
        else:
            for lc in signal.sources:
                cells[lc].used = True
                if not cells[lc].output:
                    cells[lc].output = signal.name
    local = []
    for where, src, dst in carries:
        if where != tile:
            continue
        local.append((src, dst))
        if 0 <= dst < 8:
            cells[dst].used = True
            cells[dst].inputs[3] = "carry"
        if 0 <= src < 8:
            cells[src].used = True
    return cells, local


def _subst(expr: str, labels: dict[str, str]) -> str:
    for name, label in sorted(labels.items(), key=lambda item: -len(item[0])):
        expr = re.sub(rf"\b{re.escape(name)}\b", label, expr)
    return " ".join(expr.split())


def _wrap(text: str, width: int = 36) -> str:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = word if not current else f"{current} {word}"
        if len(trial) > width and current:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return "\n".join(lines[:4])


CELL_H = 1.28
CELL_W = 3.2
PAD_SIZE = 0.82
BREAK = 1.7


def _wrapped(expr: str) -> bool:
    if not (expr.startswith("(") and expr.endswith(")")):
        return False
    depth = 0
    for index, char in enumerate(expr):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index == len(expr) - 1
    return False


def _unwrap(expr: str) -> str:
    expr = expr.strip()
    while _wrapped(expr):
        expr = expr[1:-1].strip()
    return expr


def _split_ternary(expr: str) -> tuple[str, str, str] | None:
    depth = 0
    question = None
    for index, char in enumerate(expr):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "?" and depth == 0 and question is None:
            question = index
        elif char == ":" and depth == 0 and question is not None:
            return expr[:question].strip(), expr[question + 1 : index].strip(), expr[index + 1 :].strip()
    return None


def _bare_not(expr: str) -> str | None:
    expr = _unwrap(expr)
    if expr.startswith("!"):
        return _unwrap(expr[1:])
    return None


def _pure_op(text: str) -> tuple[str, list[str]] | None:
    for op in ("xnor", "xor"):
        parts = [part.strip() for part in text.split(f" {op} ")]
        if len(parts) > 1 and all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) for part in parts):
            return op, parts
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", text):
        return "wire", [text]
    return None


def _join_xor(names: list[str]) -> str:
    ordered: list[str] = []
    for name in names:
        if name not in ordered:
            ordered.append(name)
    return " xor ".join(ordered)


def function_name(expr: str) -> str:
    """Short name for an icebox LUT expression. Falls back to the expression."""

    def rec(raw: str) -> str:
        text = _unwrap(raw)
        if text.startswith("!"):
            return f"not {rec(text[1:])}"
        parts = _split_ternary(text)
        if parts is None:
            if re.fullmatch(r"c\d+", text):
                return "carry"
            return text
        cond, yes, no = parts
        not_yes = _bare_not(yes)
        not_no = _bare_not(no)
        if not_yes is not None and _unwrap(not_yes) == _unwrap(no):
            return _flatten_xor(rec(cond), rec(no))
        if not_no is not None and _unwrap(not_no) == _unwrap(yes):
            return _flatten_xnor(rec(cond), rec(yes))
        folded = _fold_mux(rec(cond), rec(yes), rec(no))
        if folded:
            return folded
        return f"{rec(cond)} ? {rec(yes)} : {rec(no)}"

    return rec(expr)


def _flatten_xor(left: str, right: str) -> str:
    names: list[str] = []
    for piece in (left, right):
        kind = _pure_op(piece)
        if kind is None or kind[0] not in ("xor", "wire"):
            return f"{left} xor {right}"
        names.extend(kind[1])
    return _join_xor(names)


def _flatten_xnor(left: str, right: str) -> str:
    return f"{left} xnor {right}"


def _fold_mux(cond: str, yes: str, no: str) -> str | None:
    yes_op, no_op, cond_op = _pure_op(yes), _pure_op(no), _pure_op(cond)
    if not (yes_op and no_op and cond_op and cond_op[0] == "wire"):
        return None
    if sorted(yes_op[1]) != sorted(no_op[1]):
        return None
    if yes_op[0] == "xnor" and no_op[0] == "xor":
        return _join_xor([*no_op[1], cond_op[1][0]])
    if yes_op[0] == "xor" and no_op[0] == "xnor":
        return "not " + _join_xor([*yes_op[1], cond_op[1][0]])
    return None


def layout_axis(anchors: list[int], sizes: dict[int, float]) -> tuple[dict[int, tuple[float, float]], list[tuple[float, int]]]:
    """Place the used coordinates. A jump of more than one tile becomes a short gap."""
    ordered = sorted(set(anchors))
    boxes: dict[int, tuple[float, float]] = {}
    breaks: list[tuple[float, int]] = []
    cursor = 0.0
    previous = None
    for anchor in ordered:
        size = sizes.get(anchor, PAD_SIZE)
        if previous is not None:
            gap = anchor - previous
            if gap > 1:
                cursor += 0.5
                breaks.append((cursor + BREAK / 2, gap))
                cursor += BREAK
                cursor += 0.5
            else:
                cursor += 0.55
        boxes[anchor] = (cursor, size)
        cursor += size
        previous = anchor
    return boxes, breaks


def _dedupe(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    cleaned: list[tuple[float, float]] = []
    for point in points:
        if not cleaned or abs(cleaned[-1][0] - point[0]) > 0.01 or abs(cleaned[-1][1] - point[1]) > 0.01:
            cleaned.append(point)
    return cleaned


def route_around(
    pad: tuple[float, float],
    port: tuple[float, float],
    bounds: tuple[float, float, float, float],
    side: str,
    lane: int,
) -> list[tuple[float, float]]:
    """Wire from the pad to the cell port, staying outside the logic stack."""
    left, _bottom, right, top = bounds
    gutter = (left - 0.85 - lane * 0.16) if side == "left" else (right + 0.85 + lane * 0.16)
    px, py = pad
    qx, qy = port
    beside = (side == "left" and px < left - 0.08) or (side == "right" and px > right + 0.08)
    if beside:
        points = [(px, py), (px, qy), (qx, qy)]
    elif py > top + 0.05:
        sky = py + 0.72
        points = [(px, py), (px, sky), (gutter, sky), (gutter, qy), (qx, qy)]
    else:
        points = [(px, py), (gutter, py), (gutter, qy), (qx, qy)]
    return _dedupe(points)


def _axis_segments(points: list[tuple[float, float]]) -> list[tuple[str, float, float, float]]:
    """Axis-aligned spans, each ordered from low to high: ('h', y, x0, x1) or ('v', x, y0, y1)."""
    found = []
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if abs(y0 - y1) <= 0.01 and abs(x0 - x1) > 0.02:
            lo, hi = (x0, x1) if x0 < x1 else (x1, x0)
            found.append(("h", round((y0 + y1) / 2, 2), lo, hi))
        elif abs(x0 - x1) <= 0.01 and abs(y0 - y1) > 0.02:
            lo, hi = (y0, y1) if y0 < y1 else (y1, y0)
            found.append(("v", round((x0 + x1) / 2, 2), lo, hi))
    return found


def _covered_spans(intervals: list[tuple[float, float, str]]) -> list[tuple[float, float, list[str]]]:
    """Split a line into stretches and the wire colors on each stretch."""
    events: list[tuple[float, int, str]] = []
    for lo, hi, color in intervals:
        if hi - lo < 0.02:
            continue
        events.append((lo, 1, color))
        events.append((hi, -1, color))
    events.sort(key=lambda event: (event[0], event[1]))
    active: dict[str, int] = {}
    previous = None
    spans: list[tuple[float, float, list[str]]] = []
    for pos, kind, color in events:
        if previous is not None and pos - previous > 0.02 and len(active) >= 2:
            spans.append((previous, pos, list(active)))
        if kind > 0:
            active[color] = active.get(color, 0) + 1
        else:
            active[color] = active.get(color, 0) - 1
            if active[color] <= 0:
                del active[color]
        previous = pos
    return spans


def _paint_shared(ax, routes: list[tuple[list[tuple[float, float]], str]]) -> None:
    """Where two or more wires share a path, alternate their colors along it."""
    grouped: dict[tuple[str, float], list[tuple[float, float, str]]] = {}
    for points, color in routes:
        for orient, key, lo, hi in _axis_segments(points):
            grouped.setdefault((orient, key), []).append((lo, hi, color))
    for (orient, key), intervals in grouped.items():
        for lo, hi, colors in _covered_spans(intervals):
            length = hi - lo
            dash = 0.36
            if len(colors) * dash > length:
                dash = length / len(colors)
            cursor = lo
            index = 0
            while cursor < hi - 0.01:
                end = min(hi, cursor + dash)
                # Overlap the seams so the solid wire underneath cannot show through.
                draw_lo = lo if cursor <= lo else cursor - 0.02
                draw_hi = hi if end >= hi - 0.01 else end + 0.02
                if orient == "h":
                    segment = [(draw_lo, key), (draw_hi, key)]
                else:
                    segment = [(key, draw_lo), (key, draw_hi)]
                xs_line, ys_line = zip(*segment)
                ax.plot(xs_line, ys_line, color=colors[index % len(colors)], lw=2.6, solid_capstyle="butt", zorder=3.5)
                cursor = end
                index += 1


def draw_board(ax, signals: list[Signal], blocks: list[tuple[tuple[int, int], dict[int, Cell], list[tuple[int, int]]]]) -> None:
    xs = [signal.pad[0] for signal in signals]
    ys = [signal.pad[1] for signal in signals]
    for tile, _cells, _carries in blocks:
        xs.append(tile[0])
        ys.append(tile[1])
    if not xs:
        ax.axis("off")
        ax.text(0.1, 0.5, "No pads or logic in this bitstream.", fontsize=12)
        return

    x_sizes = {value: PAD_SIZE for value in xs}
    y_sizes = {value: PAD_SIZE for value in ys}
    for tile, cells, _carries in blocks:
        used = sum(1 for cell in cells.values() if cell.used)
        x_sizes[tile[0]] = max(x_sizes.get(tile[0], 0), CELL_W)
        y_sizes[tile[1]] = max(y_sizes.get(tile[1], 0), max(used, 1) * CELL_H)

    x_boxes, x_breaks = layout_axis(xs, x_sizes)
    y_boxes, y_breaks = layout_axis(ys, y_sizes)

    stacks: dict[tuple[int, int], dict] = {}
    for tile, cells, carries in blocks:
        x0, width = x_boxes[tile[0]]
        y0, height = y_boxes[tile[1]]
        used_index = [index for index in range(8) if cells[index].used]
        rects = {}
        if used_index:
            inner = height / len(used_index)
            for slot, index in enumerate(used_index):
                rects[index] = (x0 + 0.08, y0 + slot * inner + 0.06, width - 0.16, inner - 0.12)
        stacks[tile] = {"bounds": (x0, y0, x0 + width, y0 + height), "rects": rects, "cells": cells, "carries": carries}

    def center(boxes: dict[int, tuple[float, float]], coord: int) -> float:
        start, size = boxes[coord]
        return start + size / 2

    x_span = [start for start, _size in x_boxes.values()] + [start + size for start, size in x_boxes.values()]
    for mid, gap in x_breaks:
        ax.text(mid, -0.15, f"{gap} tiles", ha="center", va="bottom", fontsize=8, color="#7f8c8d")
    for mid, gap in y_breaks:
        ax.plot([min(x_span), max(x_span)], [mid, mid], color="#d5d0c8", lw=0.8, linestyle=(0, (3, 3)), zorder=1)
        ax.text(
            (min(x_span) + max(x_span)) / 2,
            mid,
            f"{gap} tiles",
            ha="center",
            va="center",
            fontsize=9,
            color="#666666",
            zorder=2,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="#f7f5f2", edgecolor="none"),
        )

    lanes: dict[int, int] = {}
    for side_name in ("left", "right"):
        group = []
        for signal in signals:
            stack = stacks.get(signal.lut)
            if stack is None:
                continue
            left, _bottom, right, _top = stack["bounds"]
            pad_x = center(x_boxes, signal.pad[0])
            side = "left" if pad_x <= (left + right) / 2 else "right"
            if side == side_name:
                group.append(signal)
        for slot, signal in enumerate(group):
            lanes[id(signal)] = slot

    routes: list[tuple[list[tuple[float, float]], str]] = []
    for index, signal in enumerate(signals):
        color = WIRE_COLORS[index % len(WIRE_COLORS)]
        stack = stacks.get(signal.lut)
        pad_xy = (center(x_boxes, signal.pad[0]), center(y_boxes, signal.pad[1]))
        if stack is None or not stack["rects"]:
            continue
        port, side = _port(signal, stack, pad_xy[0])
        if port is None:
            continue
        points = route_around(pad_xy, port, stack["bounds"], side, lanes[id(signal)] % 5)
        if signal.direction == "OUT":
            points.reverse()
        points = _trim_pad(points, pad_xy, signal.direction)
        routes.append((points, color))
        xs_line, ys_line = zip(*points)
        ax.plot(xs_line, ys_line, color=color, lw=1.7, solid_capstyle="round", zorder=3)
    _paint_shared(ax, routes)
    for points, color in routes:
        ax.annotate(
            "",
            xy=points[-1],
            xytext=points[-2],
            arrowprops=dict(arrowstyle="-|>", color=color, lw=1.3, mutation_scale=10),
            zorder=4,
        )

    for tile, stack in stacks.items():
        x0, y0, x1, y1 = stack["bounds"]
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (x0, y0),
                x1 - x0,
                y1 - y0,
                boxstyle="round,pad=0.02,rounding_size=0.08",
                facecolor="#f4f1ea",
                edgecolor="#1e8449",
                linewidth=1.2,
                zorder=2,
            )
        )
        ax.text((x0 + x1) / 2, y1 + 0.08, f"tile {tile[0]},{tile[1]}", ha="center", va="bottom", fontsize=8, color="#1e8449", zorder=6)
        for index, rect in stack["rects"].items():
            _draw_logic_cell(ax, rect, stack["cells"][index])
        _draw_carries(ax, stack["rects"], stack["carries"])

    by_tile: dict[tuple[int, int], list[Signal]] = {}
    for signal in signals:
        by_tile.setdefault(signal.pad, []).append(signal)
    for (x, y), group in by_tile.items():
        cx, cy = center(x_boxes, x), center(y_boxes, y)
        has_in = any(item.direction == "IN" for item in group)
        has_out = any(item.direction == "OUT" for item in group)
        if has_in and has_out:
            face = "#6b5b95"
        elif has_out:
            face = "#d4762c"
        else:
            face = "#2e5f8a"
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (cx - 0.4, cy - 0.34),
                0.8,
                0.68,
                boxstyle="round,pad=0.02,rounding_size=0.08",
                facecolor=face,
                edgecolor="#1c2833",
                linewidth=0.8,
                zorder=5,
            )
        )
        ax.text(cx, cy, "\n".join(item.name for item in group), ha="center", va="center", color="white", fontsize=8, zorder=6)

    xs_all = [start for start, _size in x_boxes.values()] + [start + size for start, size in x_boxes.values()]
    ys_all = [start for start, _size in y_boxes.values()] + [start + size for start, size in y_boxes.values()]
    ax.set_xlim(min(xs_all) - 2.4, max(xs_all) + 1.6)
    ax.set_ylim(min(ys_all) - 1.3, max(ys_all) + 1.3)
    ax.set_aspect("equal")
    ax.axis("off")


def _port(signal: Signal, stack: dict, pad_x: float) -> tuple[tuple[float, float] | None, str]:
    left, _bottom, right, _top = stack["bounds"]
    side = "left" if pad_x <= (left + right) / 2 else "right"
    if signal.direction == "IN":
        sinks = [(lc, pin) for lc, pin in signal.sinks if pin != 3 and lc in stack["rects"]]
        if not sinks:
            return None, side
        lc, pin = sinks[0]
        x, y, w, h = stack["rects"][lc]
        pins = [item for item in sorted(stack["cells"][lc].inputs) if item != 3]
        slot = pins.index(pin) if pin in pins else 0
        count = max(1, len(pins))
        yy = y + h * (count - slot) / (count + 1)
        return (x if side == "left" else x + w, yy), side
    sources = [lc for lc in signal.sources if lc in stack["rects"]]
    if not sources:
        return None, side
    x, y, w, h = stack["rects"][sources[0]]
    return (x if side == "left" else x + w, y + h / 2), side


def _trim_pad(points: list[tuple[float, float]], pad: tuple[float, float], direction: str) -> list[tuple[float, float]]:
    if len(points) < 2:
        return points
    end_at_pad = direction == "OUT"
    index = -1 if end_at_pad else 0
    other = -2 if end_at_pad else 1
    px, py = points[index]
    ox, oy = points[other]
    dx, dy = px - ox, py - oy
    length = abs(dx) + abs(dy)
    if length < 0.2:
        return points
    rim = 0.38
    if abs(dx) >= abs(dy):
        nx = px - (rim if dx > 0 else -rim)
        ny = py
    else:
        nx, ny = px, py - (rim if dy > 0 else -rim)
    updated = list(points)
    updated[index] = (nx, ny)
    return updated


def _draw_logic_cell(ax, rect: tuple[float, float, float, float], cell: Cell) -> None:
    x, y, w, h = rect
    ax.add_patch(
        mpatches.FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor="white",
            edgecolor="#1e8449",
            linewidth=1.3,
            zorder=4,
        )
    )
    title = cell.output or f"LC{cell.index}"
    function = function_name(cell.equation) if cell.equation else ""
    if function == title:
        function = ""
    ax.text(x + 0.12, y + h - 0.16, f"LC{cell.index}", ha="left", va="top", fontsize=7, color="#7f8c8d", zorder=5)
    ax.text(x + w / 2, y + h * (0.62 if function else 0.5), title, ha="center", va="center", fontsize=12, color="#1e8449", zorder=5)
    if function:
        ax.text(x + w / 2, y + h * 0.28, _wrap(function, 28), ha="center", va="center", fontsize=8, color="#1c2833", zorder=5)


def _draw_carries(ax, rects: dict[int, tuple[float, float, float, float]], carries: list[tuple[int, int]]) -> None:
    labeled = False
    for src, dst in carries:
        if src not in rects or dst not in rects:
            continue
        sx, sy, sw, sh = rects[src]
        _dx, dy, _dw, _dh = rects[dst]
        cx = sx + sw * 0.82
        start = sy + sh
        end = dy
        if end < start:
            start, end = end, start
            src, dst = dst, src
        ax.annotate(
            "",
            xy=(cx, end - 0.02),
            xytext=(cx, start + 0.02),
            arrowprops=dict(arrowstyle="-|>", color="#5b4b8a", lw=1.5),
            zorder=5,
        )
        if not labeled:
            ax.text(cx + 0.08, (start + end) / 2, "carry", color="#5b4b8a", fontsize=7, va="center", zorder=6)
            labeled = True



def materialize(source: str, tmp: Path) -> tuple[Path, str]:
    if source == "-":
        text = sys.stdin.read()
        if not text.strip():
            raise SystemExit("No ASC text on stdin.")
        if "\0" in text or ".logic_tile" not in text and ".device" not in text:
            raise SystemExit("Stdin was not ASC text. Pass a .asc file, or a .bin path to unpack.")
        path = tmp / "pasted.asc"
        path.write_text(text if text.endswith("\n") else text + "\n")
        return path, "stdin"
    path = Path(source)
    if not path.is_file():
        raise SystemExit(f"No such file: {path}")
    if path.suffix.lower() == ".bin":
        unpacked = tmp / "unpacked.asc"
        result = subprocess.run(["iceunpack", str(path), str(unpacked)], capture_output=True, text=True)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise SystemExit(detail or "iceunpack failed")
        return unpacked, path.name
    return path, path.name


def report(source_name: str, tile: tuple[int, int] | None, signals: list[Signal], carries) -> str:
    lines = [source_name]
    if tile is None:
        lines.append("no logic tile")
    else:
        lines.append(f"logic tile {tile[0]},{tile[1]}")
    lines.append("")
    if not signals and not carries:
        lines.append("No pad-to-LUT routes in this bitstream.")
    lines.extend(signal_line(signal) for signal in signals)
    if signals and carries:
        lines.append("")
    lines.extend(carry_line(where, src, dst) for where, src, dst in carries)
    return "\n".join(lines) + "\n"


def draw_legend(fig) -> None:
    handles = [
        mpatches.Patch(facecolor="#2e5f8a", edgecolor="#1c2833", label="Input"),
        mpatches.Patch(facecolor="#d4762c", edgecolor="#1c2833", label="Output"),
        mpatches.Patch(facecolor="#6b5b95", edgecolor="#1c2833", label="Input and output on one pad"),
        mpatches.Patch(facecolor="white", edgecolor="#1e8449", label="Logic cell"),
        Line2D([0], [0], color="#1f4e79", lw=1.7, label="Wire; a shared path alternates colors"),
        Line2D([0], [0], color="#5b4b8a", lw=1.6, label="Carry into the next cell"),
        Line2D([0], [0], color="#b0aaa2", lw=1.0, linestyle=(0, (3, 3)), label="Gap left out, distance in tiles"),
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=8,
        bbox_to_anchor=(0.5, 0.005),
    )


def render(asc: Path, source_name: str, pcf_path: Path | None, gpio: dict[str, str], requested: tuple[int, int] | None, out: Path) -> None:
    pin_at = load_sg48(find_chipdb())
    pcf = load_pcf(pcf_path)
    text = run_vlog(asc, pcf_path)
    signals, carries, lut_expr, ff_name, wire_labels = parse_vlog(text, pin_at, pcf, gpio, requested)
    tile = choose_tile(requested, lut_expr)
    tiles = sorted({key[:2] for key in lut_expr})
    blocks = []
    for candidate in tiles:
        cells, local_carries = cells_for(candidate, signals, carries, lut_expr, ff_name, wire_labels)
        if any(cell.used for cell in cells.values()):
            blocks.append((candidate, cells, local_carries))
    text_report = report(source_name, tile, signals, carries)

    fig = plt.figure(figsize=(13.5, 9.6), facecolor="#f7f5f2")
    ax = fig.add_axes([0.04, 0.12, 0.92, 0.78])
    ax.set_facecolor("#f7f5f2")
    draw_board(ax, signals, blocks)
    draw_legend(fig)
    fig.suptitle(f"{source_name}    pico2-ice  iCE40UP5K", fontsize=13, x=0.04, ha="left")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=140)
    plt.close(fig)
    txt = out.with_suffix(".txt")
    txt.write_text(text_report)
    print(text_report, end="")
    print(f"Wrote {out}")
    print(f"Wrote {txt}")


def parse_tile(text: str) -> tuple[int, int]:
    parts = text.replace(" ", "").split(",")
    if len(parts) != 2:
        raise SystemExit("--tile must look like 17,1")
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        raise SystemExit("--tile must look like 17,1")


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw a pico2-ice ASC on the UP5K, to scale.")
    parser.add_argument("asc_path", nargs="?", type=Path, help="ASC or BIN file")
    parser.add_argument("--asc", dest="asc_flag", help="ASC or BIN path, or - to read ASC text from stdin")
    parser.add_argument("--preset", choices=sorted(PRESETS), help="xor, adder2, or adder4 pin map")
    parser.add_argument("--pcf", type=Path, help="Pin constraint file. Overrides the preset PCF.")
    parser.add_argument("--tile", help="Logic tile to open, as X,Y. Overrides the preset tile.")
    parser.add_argument("-o", "--out", type=Path, help="PNG path. The connection list is written next to it as .txt")
    args = parser.parse_args()

    if args.asc_flag is not None:
        source = args.asc_flag
    elif args.asc_path is not None:
        source = str(args.asc_path)
    else:
        parser.error("pass an ASC path, or --asc - to paste one")

    preset = PRESETS[args.preset] if args.preset else None
    pcf_path = args.pcf if args.pcf is not None else (preset["pcf"] if preset else None)
    gpio = dict(preset["gpio"]) if preset else {}
    if args.tile:
        requested = parse_tile(args.tile)
    elif preset:
        requested = preset["tile"]
    else:
        requested = None

    if source == "-":
        default_out = Path("circuit_board.png")
    else:
        default_out = Path(source).with_name(Path(source).stem + "_board.png")
    out = args.out if args.out is not None else default_out

    with tempfile.TemporaryDirectory() as tmp:
        asc_path, source_name = materialize(source, Path(tmp))
        render(asc_path, source_name, pcf_path, gpio, requested, out)


if __name__ == "__main__":
    main()
