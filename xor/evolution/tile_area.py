"""Rectangle of logic tiles that evolution is allowed to change.

Columns 6 and 19 have no logic tiles on the UP5K, so a 5x5 coordinate
window can contain fewer than 25 real tiles. IO tiles (y = 0) stay outside
the area and are not mutated.
"""

from __future__ import annotations

from pathlib import Path

MISSING_X = {6, 19}
X_MIN, X_MAX = 1, 24
Y_MIN, Y_MAX = 1, 30


class TileArea:
    def __init__(self, origin_x: int, origin_y: int, width: int, height: int):
        if width < 1 or height < 1:
            raise ValueError("width and height must be at least 1")
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.width = width
        self.height = height

    @property
    def x1(self) -> int:
        return self.origin_x + self.width - 1

    @property
    def y1(self) -> int:
        return self.origin_y + self.height - 1

    def contains(self, x: int, y: int) -> bool:
        return (
            self.origin_x <= x <= self.x1
            and self.origin_y <= y <= self.y1
            and x not in MISSING_X
            and X_MIN <= x <= X_MAX
            and Y_MIN <= y <= Y_MAX
        )

    def tiles(self) -> list[tuple[int, int]]:
        found = []
        for y in range(self.origin_y, self.y1 + 1):
            for x in range(self.origin_x, self.x1 + 1):
                if self.contains(x, y):
                    found.append((x, y))
        return found


def load_area(path: Path) -> TileArea:
    values = {}
    for line in path.read_text().splitlines():
        line = line.split(";", 1)[0].strip()
        if not line or line.startswith("[") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = int(value.strip())
    return TileArea(
        values["origin_x"],
        values["origin_y"],
        values["width"],
        values["height"],
    )


if __name__ == "__main__":
    area = load_area(Path(__file__).with_name("xor_area.ini"))
    tiles = area.tiles()
    print(
        f"window x={area.origin_x}..{area.x1} y={area.origin_y}..{area.y1} "
        f"({area.width}x{area.height})"
    )
    print(f"real logic tiles: {len(tiles)}")
    for x, y in tiles:
        print(f"  logic_tile {x} {y}")
