"""
Draw an iCE40UP5K ASC as a fabric map plus a short netlist and config-bit view.

Works for the current XOR bitstream and for later evolved ASCs: any logic tile
icebox marks as configured (LUT or routing) is shown, and package pins are
labeled input vs output from the PCF + sg48 pin map.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASC = ROOT / "xor" / "build" / "xor.asc"
DEFAULT_PCF = ROOT / "xor" / "rtl" / "xor.pcf"
DEFAULT_OUT = ROOT / "xor" / "build" / "xor_fpga_layout.png"
CHIPDB = Path("/opt/homebrew/Cellar/icestorm/1.1_1/share/icestorm/chipdb/chipdb-5k.txt")

# Fallback if chipdb is not installed: sg48 pins used by this project.
FALLBACK_PINS = {
    "2": (8, 0, 0),
    "3": (9, 0, 1),
    "4": (9, 0, 0),
}

X_MAX, Y_MAX = 24, 30
MISSING_X = {6, 19}


def load_sg48_pins() -> dict[str, tuple[int, int, int]]:
    pins = dict(FALLBACK_PINS)
    if not CHIPDB.exists():
        return pins
    lines = CHIPDB.read_text().splitlines()
    try:
        start = lines.index(".pins sg48") + 1
    except ValueError:
        return pins
    for line in lines[start:]:
        if not line or line.startswith("."):
            break
        num, x, y, pio = line.split()
        pins[num] = (int(x), int(y), int(pio))
    return pins


def load_pcf(path: Path | None) -> dict[str, str]:
    """Map package pin number -> signal name."""
    if path is None or not path.exists():
        return {}
    signals = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "set_io":
            signals[parts[2]] = parts[1]
    return signals


def explain_asc(path: Path) -> str:
    result = subprocess.run(
        ["icebox_explain", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def parse_explain(text: str) -> tuple[dict, dict]:
    logic: dict[tuple[int, int], dict] = {}
    io: dict[tuple[int, int], dict] = {}
    header = None
    bucket: list[str] = []

    def flush():
        nonlocal header, bucket
        if header is None:
            bucket = []
            return
        kind, xs, ys = header.split()
        key = (int(xs), int(ys))
        lines = [ln for ln in bucket if ln.strip()]
        if kind == ".logic_tile":
            lcs = []
            routes = []
            for ln in lines:
                if ln.startswith("LC_"):
                    lcs.append(ln)
                elif ln.startswith("buffer "):
                    routes.append(ln)
            # Column-buffer defaults are not user logic.
            if lcs or routes:
                logic[key] = {"lcs": lcs, "routes": routes}
        elif kind == ".io_tile":
            inputs = set()
            outputs = set()
            for ln in lines:
                # io_N is the pad in this tile. D_OUT_0 is not the pad number.
                m = re.search(r"io_(\d+)/D_IN", ln)
                if m:
                    inputs.add(int(m.group(1)))
                m = re.search(r"io_(\d+)/D_OUT", ln)
                if m:
                    outputs.add(int(m.group(1)))
            if lines:
                io[key] = {"inputs": inputs, "outputs": outputs, "lines": lines}
        header = None
        bucket = []

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(".logic_tile") or line.startswith(".io_tile"):
            flush()
            header = line
            bucket = []
        elif header is not None:
            if line.startswith(".") and not line.startswith(".logic") and not line.startswith(".io"):
                flush()
            else:
                bucket.append(line)
    flush()
    return logic, io


def pin_roles(pcf: dict[str, str], pinmap: dict[str, tuple[int, int, int]], io: dict) -> list[dict]:
    roles = []
    for pin, (x, y, pio) in pinmap.items():
        if pin not in pcf:
            continue
        tile = io.get((x, y), {})
        lines = tile.get("lines", [])
        if pio in tile.get("outputs", set()):
            direction = "OUT"
        elif any(ln.startswith(f"IOB_{pio} ") for ln in lines):
            # Pad is configured and is not driving D_OUT, so it is an input.
            direction = "IN"
        else:
            direction = "?"
        roles.append(
            {
                "name": pcf[pin],
                "pin": pin,
                "tile": (x, y),
                "pio": pio,
                "direction": direction,
            }
        )
    roles.sort(key=lambda r: (r["direction"] != "IN", r["name"]))
    return roles


def parse_routes(asc: Path, pcf: Path | None) -> list[list[tuple[int, int, str]]]:
    """Each icebox_vlog comment block is one wire and the tiles it touches."""
    cmd = ["icebox_vlog", "-d", "sg48", str(asc)]
    if pcf and pcf.exists():
        cmd[1:1] = ["-p", str(pcf)]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    nets: list[list[tuple[int, int, str]]] = []
    current: list[tuple[int, int, str]] = []
    for line in result.stdout.splitlines():
        match = re.match(r"// \((\d+), (\d+), '([^']+)'\)", line.strip())
        if match:
            current.append((int(match.group(1)), int(match.group(2)), match.group(3)))
        elif current:
            nets.append(current)
            current = []
    if current:
        nets.append(current)
    return nets


def wire_edges(nets, roles) -> list[dict]:
    """Driver tile -> sink tile for each net that reaches a pin or a LUT pin."""
    edges = []
    for points in nets:
        drivers = []
        sinks = []
        kind = "internal"
        name = "net"
        for x, y, res in points:
            if "/out" in res or "D_IN" in res:
                drivers.append((x, y))
            if "/in_" in res or "D_OUT" in res:
                sinks.append((x, y))
            pad = re.search(r"io_(\d+)/D_(IN|OUT)", res)
            if pad:
                pio = int(pad.group(1))
                direction = "IN" if pad.group(2) == "IN" else "OUT"
                for role in roles:
                    if role["tile"] == (x, y) and role["pio"] == pio:
                        name = role["name"]
                        kind = direction
        for src in dict.fromkeys(drivers):
            for dst in dict.fromkeys(sinks):
                if src != dst:
                    edges.append({"src": src, "dst": dst, "name": name, "kind": kind})
    return edges


def draw_wires(ax, edges) -> None:
    """Route each wire in a gutter beside the tiles, arrow pointing at the sink."""
    colors = {"IN": "#1d4e89", "OUT": "#c45c12", "internal": "#2a7a4b"}
    rim = 0.46
    inside = 0.20
    used_gutters: list[float] = []

    def gutter_x(preferred: float) -> float:
        x = preferred
        while any(abs(x - other) < 0.25 for other in used_gutters):
            x += -0.28 if preferred < 0 else 0.28
        used_gutters.append(x)
        return x

    for index, edge in enumerate(edges):
        sx, sy = edge["src"]
        dx, dy = edge["dst"]
        kind = edge["kind"]
        if abs(sx - dx) < 0.1:
            side = -1 if kind != "OUT" else 1
            channel = gutter_x(sx + side * (0.85 + 0.15 * index))
            toward = 1 if dy > sy else -1
            points = [
                (sx, sy + toward * inside),
                (channel, sy + toward * inside),
                (channel, dy),
                (dx - rim if channel < dx else dx + rim, dy),
            ]
        elif kind == "OUT":
            # Start inside the logic tile, land on the edge of the output pin.
            points = [
                (sx + inside, sy - inside),
                (dx + 0.18, sy - inside),
                (dx + 0.18, dy + rim),
            ]
        else:
            # Start inside the pin, land on the edge of the logic tile.
            away = 1 if sx >= dx else -1
            outer = gutter_x(sx + away * (1.15 + 0.18 * index))
            points = [
                (sx + away * inside, sy + 0.12),
                (outer, sy + 0.12),
                (outer, dy),
                (dx + (rim if outer > dx else -rim), dy),
            ]
        color = colors[kind]
        xs, ys = zip(*points)
        ax.plot(xs, ys, color=color, linewidth=2.2, solid_capstyle="round", zorder=6)
        ax.annotate(
            "",
            xy=points[-1],
            xytext=points[-2],
            arrowprops=dict(arrowstyle="-|>", color=color, lw=1.8),
            zorder=6,
        )
        label_at = points[1]
        ax.text(
            label_at[0],
            label_at[1],
            edge["name"],
            color=color,
            fontsize=8,
            ha="center",
            va="bottom",
            zorder=7,
            bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor=color, linewidth=0.6),
        )


def parse_cells(info: dict) -> dict[int, dict]:
    """Eight logic cells in one tile. Missing cells are unused."""
    cells = {
        i: {"used": False, "init": None, "carry": False, "outs": [], "ins": []}
        for i in range(8)
    }
    for line in info.get("lcs", []):
        parts = line.split()
        if len(parts) < 2 or not parts[0].startswith("LC_"):
            continue
        index = int(parts[0].split("_")[1])
        init = parts[1]
        carry = "CarryEnable" in line
        # The placer's unused-LC default. A real function or carry marks the cell used.
        used = carry or init != "0000111100001111"
        cells[index] = {"used": used, "init": init, "carry": carry, "outs": [], "ins": []}
    return cells


def cell_links(nets, roles, tile: tuple[int, int], cells: dict[int, dict]) -> list[tuple[int, int]]:
    """Attach pin names to the cells they touch. Return carry pairs (src, dst)."""
    carries = []
    for points in nets:
        ins = []
        outs = []
        couts = []
        pins = []
        for x, y, res in points:
            if (x, y) == tile:
                inn = re.search(r"lutff_(\d+)/in_(\d+)", res)
                if inn:
                    ins.append((int(inn.group(1)), int(inn.group(2))))
                out = re.search(r"lutff_(\d+)/out", res)
                if out:
                    outs.append(int(out.group(1)))
                cout = re.search(r"lutff_(\d+)/cout", res)
                if cout:
                    couts.append(int(cout.group(1)))
            pad = re.search(r"io_(\d+)/D_(IN|OUT)", res)
            if pad:
                pio = int(pad.group(1))
                for role in roles:
                    if role["tile"] == (x, y) and role["pio"] == pio:
                        pins.append(role)
        for src in couts:
            for lc, pin in ins:
                if pin == 3:
                    carries.append((src, lc))
        for role in pins:
            if role["direction"] == "IN":
                for lc, pin in ins:
                    if pin == 3:
                        continue
                    cells[lc]["used"] = True
                    if role["name"] not in cells[lc]["ins"]:
                        cells[lc]["ins"].append(role["name"])
            elif role["direction"] == "OUT":
                for lc in outs:
                    cells[lc]["used"] = True
                    if role["name"] not in cells[lc]["outs"]:
                        cells[lc]["outs"].append(role["name"])
    return carries


def draw_tile_cells(ax, tile, cells, carries) -> None:
    """One logic tile opened up: LC0 at the bottom, carry flowing upward."""
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title(
        f"Inside logic tile {tile[0]},{tile[1]} — 8 cells",
        loc="left",
        fontsize=12,
    )
    ax.add_patch(
        mpatches.FancyBboxPatch(
            (2.7, 0.45),
            4.6,
            8.7,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            facecolor="#f6f3ec",
            edgecolor="#222222",
            linewidth=1.3,
            zorder=1,
        )
    )
    ax.text(5.0, 8.85, "logic tile", ha="center", va="center", fontsize=8, color="#666666")

    def cell_box(index: int):
        y = 0.7 + index * 1.0
        return 3.05, y, 3.9, 0.82

    for index in range(8):
        x, y, w, h = cell_box(index)
        cell = cells[index]
        face = "#2a7a4b" if cell["used"] else "#e4e1da"
        ink = "white" if cell["used"] else "#666666"
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (x, y),
                w,
                h,
                boxstyle="round,pad=0.02,rounding_size=0.08",
                facecolor=face,
                edgecolor="#1d4d30" if cell["used"] else "#b9b4aa",
                linewidth=1.1,
                zorder=3,
            )
        )
        if cell["used"]:
            outs = ", ".join(cell["outs"]) if cell["outs"] else "logic"
            extra = "  ·  carry" if cell["carry"] else ""
            label = f"LC{index}   {outs}{extra}"
        else:
            label = f"LC{index}   unused"
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", color=ink, fontsize=9, zorder=4)

    # Inputs on the left, outputs on the right, aligned to their cell.
    in_seen: dict[str, int] = {}
    for index in range(8):
        x, y, w, h = cell_box(index)
        for name in cells[index]["ins"]:
            slot = in_seen.get(index, 0)
            in_seen[index] = slot + 1
            yy = y + h * (0.7 - 0.35 * slot)
            ax.add_patch(
                mpatches.FancyBboxPatch(
                    (0.15, yy - 0.24),
                    1.55,
                    0.48,
                    boxstyle="round,pad=0.02,rounding_size=0.08",
                    facecolor="#d9e8f7",
                    edgecolor="#1d4e89",
                    linewidth=1.0,
                    zorder=3,
                )
            )
            ax.text(0.92, yy, name, ha="center", va="center", fontsize=8, color="#1d4e89", zorder=4)
            ax.annotate(
                "",
                xy=(x, yy),
                xytext=(1.7, yy),
                arrowprops=dict(arrowstyle="-|>", color="#1d4e89", lw=1.4),
                zorder=2,
            )
        for name in cells[index]["outs"]:
            ax.add_patch(
                mpatches.FancyBboxPatch(
                    (8.25, y + h / 2 - 0.24),
                    1.55,
                    0.48,
                    boxstyle="round,pad=0.02,rounding_size=0.08",
                    facecolor="#f7e2c4",
                    edgecolor="#c45c12",
                    linewidth=1.0,
                    zorder=3,
                )
            )
            ax.text(9.02, y + h / 2, name, ha="center", va="center", fontsize=8, color="#c45c12", zorder=4)
            ax.annotate(
                "",
                xy=(8.25, y + h / 2),
                xytext=(x + w, y + h / 2),
                arrowprops=dict(arrowstyle="-|>", color="#c45c12", lw=1.4),
                zorder=2,
            )

    for src, dst in carries:
        if not (0 <= src < 8 and 0 <= dst < 8):
            continue
        sx, sy, sw, sh = cell_box(src)
        _, dy, _, _ = cell_box(dst)
        cx = sx + sw / 2
        ax.annotate(
            "",
            xy=(cx, dy - 0.02),
            xytext=(cx, sy + sh + 0.02),
            arrowprops=dict(arrowstyle="-|>", color="#6b5b95", lw=1.8),
            zorder=5,
        )

    used = sum(1 for cell in cells.values() if cell["used"])
    ax.text(
        0.15,
        0.18,
        f"{used} of 8 cells used. Gray cells are in the tile and not part of this circuit. "
        "Carry runs from the cell below into the next.",
        fontsize=8,
        color="#333333",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot an iCE40 ASC fabric layout.")
    parser.add_argument("--asc", type=Path, default=DEFAULT_ASC)
    parser.add_argument("--pcf", type=Path, default=DEFAULT_PCF)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    logic, io = parse_explain(explain_asc(args.asc))
    roles = pin_roles(load_pcf(args.pcf), load_sg48_pins(), io)

    fig = plt.figure(figsize=(13.2, 7.4))
    ax_cells = fig.add_axes([0.02, 0.06, 0.50, 0.84])
    ax_map = fig.add_axes([0.54, 0.10, 0.43, 0.76])

    # --- Fabric ---
    routed_xy = [xy for xy, info in logic.items() if info["routes"] or not info["lcs"]]
    focus = routed_xy + [r["tile"] for r in roles]
    if not focus:
        focus = list(logic)
    xs = [xy[0] for xy in focus]
    ys = [xy[1] for xy in focus]
    if not xs:
        raise SystemExit(f"No configured tiles found in {args.asc}")
    pad = 2
    x0 = max(1, min(xs) - pad)
    x1 = min(X_MAX, max(xs) + pad)
    y0 = max(0, min(ys) - pad)
    y1 = min(Y_MAX, max(ys) + pad)

    for x in range(int(x0), int(x1) + 1):
        for y in range(max(1, int(y0)), int(y1) + 1):
            if x in MISSING_X:
                continue
            ax_map.add_patch(
                mpatches.Rectangle(
                    (x - 0.45, y - 0.45),
                    0.9,
                    0.9,
                    facecolor="#e6e6e6",
                    edgecolor="#ffffff",
                    linewidth=0.6,
                    zorder=1,
                )
            )

    for (x, y), info in logic.items():
        routed = bool(info["routes"])
        n_lc = len(info["lcs"])
        if n_lc and routed:
            color, edge, label = "#2a7a4b", "#1d4d30", f"LUT {x},{y}"
        elif n_lc:
            color, edge, label = "#9bbf9b", "#4d6b4d", f"set\n{x},{y}"
        else:
            color, edge, label = "#e0b84a", "#8a6a1a", f"route {x},{y}"
        ax_map.add_patch(
            mpatches.Rectangle(
                (x - 0.45, y - 0.45),
                0.9,
                0.9,
                facecolor=color,
                edgecolor=edge,
                linewidth=1.2,
                zorder=3,
            )
        )
        ax_map.text(x, y, label, ha="center", va="center", color="#1a1a1a" if not routed and n_lc else "white", fontsize=7, zorder=8)

    # Group pin labels per tile so a shared IN+OUT tile stays readable.
    by_tile: dict[tuple[int, int], list[dict]] = {}
    for role in roles:
        by_tile.setdefault(role["tile"], []).append(role)
    for (x, y), group in by_tile.items():
        has_out = any(r["direction"] == "OUT" for r in group)
        has_in = any(r["direction"] == "IN" for r in group)
        if has_in and has_out:
            face = "#6b5b95"
        elif has_out:
            face = "#d4762c"
        else:
            face = "#3a6ea5"
        ax_map.add_patch(
            mpatches.Rectangle(
                (x - 0.48, y - 0.48),
                0.96,
                0.96,
                facecolor=face,
                edgecolor="#222222",
                linewidth=1.1,
                zorder=5,
            )
        )
        text = "\n".join(f"{r['direction']} {r['name']}" for r in group)
        ax_map.text(x, y, text, ha="center", va="center", color="white", fontsize=6.5, zorder=8)

    edges = wire_edges(parse_routes(args.asc, args.pcf), roles)
    draw_wires(ax_map, edges)

    ax_map.set_xlim(x0 - 0.7, x1 + 0.7)
    ax_map.set_ylim(y0 - 0.8, y1 + 0.8)
    ax_map.set_aspect("equal")
    ax_map.set_xlabel("Tile X")
    ax_map.set_ylabel("Tile Y")
    ax_map.set_title("Where that tile sits")
    step_x = 1 if (x1 - x0) <= 12 else 2
    step_y = 1 if (y1 - y0) <= 16 else 5
    ax_map.set_xticks(range(int(x0), int(x1) + 1, step_x))
    ax_map.set_yticks(range(int(y0), int(y1) + 1, step_y))
    ax_map.text(
        0.0,
        -0.12,
        "Blue in, orange out, green logic, gold routing.",
        transform=ax_map.transAxes,
        fontsize=8,
        color="#333333",
    )

    lut_tiles = sorted(xy for xy, info in logic.items() if info["lcs"] and info["routes"])
    if lut_tiles:
        show = max(lut_tiles, key=lambda xy: len(logic[xy]["lcs"]))
        cells = parse_cells(logic[show])
        carries = cell_links(parse_routes(args.asc, args.pcf), roles, show, cells)
        draw_tile_cells(ax_cells, show, cells, carries)
    else:
        ax_cells.axis("off")
        ax_cells.text(0.1, 0.5, "No logic tile in this bitstream.", fontsize=11)

    fig.suptitle(args.asc.name, fontsize=13, x=0.04, ha="left")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=160)
    plt.close(fig)
    print(f"Wrote {args.out}")
    print(f"LUT tiles: {lut_tiles}")
    print("Pins: " + ", ".join(f"{r['direction']} {r['name']} pin {r['pin']} @ {r['tile']}" for r in roles))


if __name__ == "__main__":
    main()
