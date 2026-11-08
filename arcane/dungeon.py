"""Dungeon floors: rooms joined by corridors, on a grid of solid and open tiles.

A floor is a chain of rooms laid out by a short walk over a coarse lattice, so
every run differs but the path can never branch away from the exit.  Geometry
queries answer in world units, which is what the shared simulation speaks.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Iterable, Sequence

TILE = 48
CELL_W = 34
CELL_H = 28
CORRIDOR_WIDTH = 4
PILLAR_SIZE = 2
TORCH_SPACING = 7

WALL = "#"
FLOOR = "."
PILLAR = "o"
# Nobody walks over a pit, but everything flies across it.
PIT = "_"

ROOM_SIZES = {
    "start": (14, 12),
    "exit": (14, 12),
    "boss": (30, 24),
    "quest": (24, 18),
    "trap": (22, 11),
    "trial": (18, 14),
    "puzzle": (18, 14),
    "workshop": (20, 14),
    "secret": (10, 8),
    "range": (32, 22),
}
MAIN_KINDS = frozenset({"start", "combat", "quest", "exit", "boss", "range"})
SIDE_WIDTHS = (14, 17)
SIDE_HEIGHTS = (11, 13)
LAYOUT_TRIES = 60
# A side room can only hold another one behind it if nothing in it cuts the way.
BRANCH_HOSTS = frozenset({"vault", "cache", "rest", "deal"})
DOOR_CLEARANCE = 3
MIN_OPEN_SHARE = 0.42
# How each chapter likes its fighting rooms: its architecture, not only its colour.
SHAPES_BY_CHAPTER = (
    ("cross", "halls", "pillars"),
    ("halls", "plain", "cross"),
    ("islands", "pitring", "islands"),
    ("racks", "racks", "cross"),
    ("ring", "blocks", "plain"),
)

PILLAR_LAYOUTS = (
    (),
    ((-6, -3), (6, -3), (-6, 3), (6, 3)),
    ((-7, 0), (7, 0), (0, -4), (0, 4)),
    ((-5, -3), (5, 3), (5, -3), (-5, 3), (0, 0)),
    ((-3, -3), (3, -3), (-3, 3), (3, 3)),
)


@dataclass(slots=True)
class Room:
    index: int
    x: int
    y: int
    w: int
    h: int
    kind: str
    doors: list[tuple[int, int]] = field(default_factory=list)
    parent: int = -1
    dark: bool = False
    guarded: bool = False
    tag: str = ""
    shape: str = ""
    aisles: list[tuple[int, int, int, int]] = field(default_factory=list)

    @property
    def side(self) -> bool:
        """A branch off the way through: nothing forces anyone to look inside."""

        return self.parent >= 0

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x + self.w / 2) * TILE, (self.y + self.h / 2) * TILE)

    def holds(self, px: float, py: float, inset: float = 0.0) -> bool:
        """Whether a world point is inside the floor, ``inset`` tiles from its edge."""

        left = (self.x + inset) * TILE
        top = (self.y + inset) * TILE
        right = (self.x + self.w - inset) * TILE
        bottom = (self.y + self.h - inset) * TILE
        return left <= px <= right and top <= py <= bottom


@dataclass(frozen=True, slots=True)
class Corridor:
    """The stretch of passage between two rooms, outside both, in tiles."""

    x: int
    y: int
    w: int
    h: int
    a: int
    b: int
    gate: tuple[tuple[int, int], ...] = ()


class DungeonMap:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.grid = [[WALL] * width for _ in range(height)]
        self.rooms: list[Room] = []
        self.corridors: list[Corridor] = []
        self.closed: set[tuple[int, int]] = set()
        self.main = 0

    @property
    def path(self) -> list[Room]:
        """The rooms everyone must walk through, from the start to the way out."""

        return self.rooms[: self.main]

    @property
    def sides(self) -> list[Room]:
        return self.rooms[self.main :]

    def room_at(self, x: float, y: float, inset: float = 0.0) -> Room | None:
        for room in self.rooms:
            if room.holds(x, y, inset):
                return room
        return None

    # ---------------------------------------------------------------- carving
    def carve(self, x: int, y: int, w: int, h: int) -> None:
        for row in range(y, y + h):
            for column in range(x, x + w):
                self.grid[row][column] = FLOOR

    # ------------------------------------------------------------------ tiles
    def solid(self, tx: int, ty: int) -> bool:
        if not (0 <= tx < self.width and 0 <= ty < self.height):
            return True
        return self.grid[ty][tx] != FLOOR or (tx, ty) in self.closed

    def stops_shots(self, tx: int, ty: int) -> bool:
        """Like ``solid``, except that a shot sails over a pit."""

        if not (0 <= tx < self.width and 0 <= ty < self.height):
            return True
        return self.grid[ty][tx] not in (FLOOR, PIT) or (tx, ty) in self.closed

    def rows(self, hidden: Iterable[tuple[int, int, int, int]] = ()) -> list[str]:
        """The map as the client gets it, with anything still secret shown as wall."""

        grid = [list(row) for row in self.grid]
        for x, y, w, h in hidden:
            for row in range(y, y + h):
                for column in range(x, x + w):
                    grid[row][column] = WALL
        return ["".join(row) for row in grid]

    def set_closed(self, tiles: Iterable[tuple[int, int]]) -> None:
        self.closed = set(tiles)

    # -------------------------------------------------------------- world space
    def blocked(self, x: float, y: float, radius: float, shot: bool = False) -> bool:
        """Whether a circle, or with no radius a single point, touches a solid tile."""

        solid = self.stops_shots if shot else self.solid
        if radius <= 0:
            return solid(math.floor(x / TILE), math.floor(y / TILE))
        left = math.floor((x - radius) / TILE)
        right = math.floor((x + radius) / TILE)
        top = math.floor((y - radius) / TILE)
        bottom = math.floor((y + radius) / TILE)
        for ty in range(top, bottom + 1):
            for tx in range(left, right + 1):
                if not solid(tx, ty):
                    continue
                nearest_x = max(tx * TILE, min(x, (tx + 1) * TILE))
                nearest_y = max(ty * TILE, min(y, (ty + 1) * TILE))
                if (x - nearest_x) ** 2 + (y - nearest_y) ** 2 < radius * radius:
                    return True
        return False

    def path_clear(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        radius: float = 0.0,
        shot: bool = False,
    ) -> bool:
        length = math.hypot(x2 - x1, y2 - y1)
        steps = max(1, math.ceil(length / 16))
        for step in range(1, steps + 1):
            at = step / steps
            if self.blocked(x1 + (x2 - x1) * at, y1 + (y2 - y1) * at, radius, shot):
                return False
        return True

    def ray_end(
        self, x: float, y: float, dx: float, dy: float, length: float
    ) -> tuple[float, float]:
        travelled = 0.0
        while travelled < length:
            advance = min(12.0, length - travelled)
            if self.blocked(x + dx * (travelled + advance), y + dy * (travelled + advance), 0.0, True):
                break
            travelled += advance
        return x + dx * travelled, y + dy * travelled

    def open_point(
        self, room: Room, rng: random.Random, radius: float, margin: int = 2
    ) -> tuple[float, float]:
        """A free spot in a room, or its middle if the room is too crowded."""

        for _ in range(40):
            x = rng.uniform(room.x + margin, room.x + room.w - margin) * TILE
            y = rng.uniform(room.y + margin, room.y + room.h - margin) * TILE
            if not self.blocked(x, y, radius):
                return x, y
        return self.open_near(*room.center, radius)

    def open_near(self, x: float, y: float, radius: float = 20.0) -> tuple[float, float]:
        """The closest place to stand: a room's middle may be a wall these days."""

        if not self.blocked(x, y, radius):
            return x, y
        for reach in range(1, 40):
            for step in range(8 + reach * 2):
                angle = step / (8 + reach * 2) * math.tau
                px = x + math.cos(angle) * reach * TILE * 0.5
                py = y + math.sin(angle) * reach * TILE * 0.5
                if not self.blocked(px, py, radius):
                    return px, py
        return x, y

    def torches(self) -> list[list[float]]:
        """Sconces along the wall above each room, the face the camera can see."""

        lights: list[list[float]] = []
        for room in self.rooms:
            if room.dark:
                continue
            for tx in range(room.x + 3, room.x + room.w - 2, TORCH_SPACING):
                if self.grid[room.y - 1][tx] == WALL:
                    lights.append([(tx + 0.5) * TILE, (room.y - 0.5) * TILE])
        return lights


def _walk(count: int, rng: random.Random, height: int = 3) -> list[tuple[int, int]]:
    """A self-avoiding walk across the lattice that drifts toward the right."""

    while True:
        cells = [(0, rng.randrange(height))]
        while len(cells) < count:
            column, row = cells[-1]
            options = [(column + 1, row), (column + 1, row)]
            if row > 0:
                options.append((column, row - 1))
            if row < height - 1:
                options.append((column, row + 1))
            options = [cell for cell in options if cell not in cells]
            if not options:
                break
            cells.append(rng.choice(options))
        if len(cells) == count:
            return cells


def _room_size(kind: str, rng: random.Random) -> tuple[int, int]:
    if kind in ROOM_SIZES:
        return ROOM_SIZES[kind]
    if kind in MAIN_KINDS:
        return rng.randint(20, 26), rng.randint(15, 20)
    return rng.randint(*SIDE_WIDTHS), rng.randint(*SIDE_HEIGHTS)


def _branch_cells(
    cells: list[tuple[int, int]],
    kinds: Sequence[str],
    rng: random.Random,
    height: int,
    spare_columns: int = 0,
) -> list[tuple[tuple[int, int], int]] | None:
    """Free lattice cells beside the path for side rooms, each with its host room.

    A branch never hangs off the exit: whatever waits there is the end of the
    stage, and a dead end behind it would only be walked past.  Hosts with the
    fewest branches go first, so the side rooms spread along the whole path.
    """

    taken = set(cells)
    columns = max(column for column, _ in cells) + 1 + spare_columns
    layout = list(cells)
    hostable = [False] * len(cells)
    children = [0] * len(cells)
    placed: dict[int, tuple[tuple[int, int], int]] = {}
    # Rooms that can have others behind them go first, so the others have a place.
    order = sorted(range(len(kinds)), key=lambda index: kinds[index] not in BRANCH_HOSTS)
    for branch in order:
        best: list[tuple[tuple[int, int], int]] = []
        fewest = 1 << 30
        for host, (column, row) in enumerate(layout):
            if host == len(cells) - 1:
                continue
            if host >= len(cells) and not hostable[host]:
                continue
            # Side rooms may hang off side rooms, but only when the path is full.
            penalty = children[host] + (10 if host >= len(cells) else 0)
            for cell in ((column + 1, row), (column - 1, row), (column, row + 1), (column, row - 1)):
                if cell in taken or not (0 <= cell[0] < columns and 0 <= cell[1] < height):
                    continue
                if penalty < fewest:
                    fewest = penalty
                    best = []
                if penalty == fewest:
                    best.append((cell, host))
        if not best:
            return None
        cell, host = rng.choice(best)
        taken.add(cell)
        layout.append(cell)
        hostable.append(kinds[branch] in BRANCH_HOSTS)
        children[host] += 1
        children.append(0)
        placed[branch] = (cell, host)
    # A host found by its place in ``layout`` has to be told by its place in the rooms.
    room_of = {len(cells) + position: len(cells) + branch for position, branch in enumerate(order)}
    return [
        (placed[index][0], room_of.get(placed[index][1], placed[index][1]))
        for index in range(len(kinds))
    ]


def _gap(first: Room, second: Room, horizontal: bool, offset: int) -> tuple[int, int, int, int]:
    if horizontal:
        left, right = sorted((first, second), key=lambda room: room.x)
        return left.x + left.w, offset, right.x - left.x - left.w, CORRIDOR_WIDTH
    top, bottom = sorted((first, second), key=lambda room: room.y)
    return offset, top.y + top.h, CORRIDOR_WIDTH, bottom.y - top.y - top.h


def _connect(dungeon: DungeonMap, first: Room, second: Room, rng: random.Random) -> None:
    ax, ay = first.x + first.w // 2, first.y + first.h // 2
    bx, by = second.x + second.w // 2, second.y + second.h // 2
    half = CORRIDOR_WIDTH // 2
    if abs(ax - bx) > abs(ay - by):
        slack = min(first.h, second.h) // 2 - half - 1
        shift = rng.randint(-slack, slack)
        y = (ay + by) // 2 + shift - half
        left, right = sorted((ax, bx))
        dungeon.carve(left, y, right - left, CORRIDOR_WIDTH)
        for room in (first, second):
            gate = room.x - 1 if room.x > left else room.x + room.w
            room.doors.extend((gate, y + offset) for offset in range(CORRIDOR_WIDTH))
        gate = first.x - 1 if first.x > left else first.x + first.w
        dungeon.corridors.append(
            Corridor(
                *_gap(first, second, True, y), first.index, second.index,
                tuple((gate, y + offset) for offset in range(CORRIDOR_WIDTH)),
            )
        )
    else:
        slack = min(first.w, second.w) // 2 - half - 1
        shift = rng.randint(-slack, slack)
        x = (ax + bx) // 2 + shift - half
        top, bottom = sorted((ay, by))
        dungeon.carve(x, top, CORRIDOR_WIDTH, bottom - top)
        for room in (first, second):
            gate = room.y - 1 if room.y > top else room.y + room.h
            room.doors.extend((x + offset, gate) for offset in range(CORRIDOR_WIDTH))
        gate = first.y - 1 if first.y > top else first.y + first.h
        dungeon.corridors.append(
            Corridor(
                *_gap(first, second, False, x), first.index, second.index,
                tuple((x + offset, gate) for offset in range(CORRIDOR_WIDTH)),
            )
        )


def _place_pillars(dungeon: DungeonMap, room: Room, rng: random.Random) -> None:
    middle_x = room.x + room.w // 2
    middle_y = room.y + room.h // 2
    for offset_x, offset_y in rng.choice(PILLAR_LAYOUTS):
        x = middle_x + offset_x
        y = middle_y + offset_y
        if any(
            abs(door_x - x) < 4 and abs(door_y - y) < 4 for door_x, door_y in room.doors
        ):
            continue
        for row in range(y, y + PILLAR_SIZE):
            for column in range(x, x + PILLAR_SIZE):
                dungeon.grid[row][column] = PILLAR


def _inner_door_tiles(room: Room) -> list[tuple[int, int]]:
    return [
        (
            min(max(x, room.x), room.x + room.w - 1),
            min(max(y, room.y), room.y + room.h - 1),
        )
        for x, y in room.doors
    ]


def _shape_tiles(room: Room, shape: str, rng: random.Random) -> list[tuple[int, int, str]]:
    """Which tiles of a room stop being floor, in room coordinates."""

    w, h = room.w, room.h
    tiles: list[tuple[int, int, str]] = []

    def block(x: int, y: int, bw: int, bh: int, kind: str = WALL) -> None:
        tiles.extend(
            (column, row, kind)
            for row in range(y, y + bh)
            for column in range(x, x + bw)
        )

    if shape == "cross":
        cw, ch = w // 4, h // 4
        for x, y in ((0, 0), (w - cw, 0), (0, h - ch), (w - cw, h - ch)):
            block(x, y, cw, ch)
    elif shape == "halls":
        for x, gap in ((w // 3, rng.randint(1, h - 6)), (w * 2 // 3, rng.randint(1, h - 6))):
            for row in range(h):
                if not gap <= row < gap + 5:
                    tiles.append((x, row, WALL))
    elif shape == "ring":
        block(w // 2 - w // 5, h // 2 - h // 5, w * 2 // 5, h * 2 // 5)
    elif shape == "pitring":
        block(w // 2 - w // 4, h // 2 - h // 4, w // 2, h // 2, PIT)
    elif shape == "islands":
        cw, ch = w // 2 - 4, h // 2 - 4
        for x, y in ((2, 2), (w - 2 - cw, 2), (2, h - 2 - ch), (w - 2 - cw, h - 2 - ch)):
            block(x, y, cw, ch, PIT)
    elif shape == "racks":
        for row in range(3, h - 2, 4):
            gap = rng.randint(2, w - 8)
            for column in range(2, w - 2):
                if not gap <= column < gap + 4:
                    tiles.append((column, row, WALL))
    elif shape == "blocks":
        for row in range(3, h - 4, 5):
            for column in range(3, w - 4, 6):
                block(column + rng.randint(0, 1), row, 2, 3)
    return tiles


def _shape_room(dungeon: DungeonMap, room: Room, shape: str, rng: random.Random) -> bool:
    """Stamp a shape into a room, or leave it alone if that would cut anyone off."""

    tiles = _shape_tiles(room, shape, rng)
    doors = _inner_door_tiles(room)
    changed: dict[tuple[int, int], str] = {}
    for column, row, kind in tiles:
        x, y = room.x + column, room.y + row
        near_door = any(
            abs(door_x - x) <= DOOR_CLEARANCE and abs(door_y - y) <= DOOR_CLEARANCE
            for door_x, door_y in doors
        )
        if not near_door:
            changed[(x, y)] = kind
    area = room.w * room.h
    if (area - len(changed)) / area < MIN_OPEN_SHARE or not doors:
        return False
    # Everything left open has to be reachable from the door, and from every door.
    seen = {doors[0]}
    frontier = [doors[0]]
    while frontier:
        x, y = frontier.pop()
        for tile in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if tile in seen or tile in changed:
                continue
            if not (room.x <= tile[0] < room.x + room.w and room.y <= tile[1] < room.y + room.h):
                continue
            seen.add(tile)
            frontier.append(tile)
    if any(door not in seen for door in doors):
        return False
    for row in range(room.y, room.y + room.h):
        for column in range(room.x, room.x + room.w):
            if (column, row) not in seen and (column, row) not in changed:
                changed[(column, row)] = WALL
    for (x, y), kind in changed.items():
        dungeon.grid[y][x] = kind
    room.shape = shape
    if shape == "racks":
        rows = sorted({row for _, row, _ in tiles})
        edges = [-1, *rows, room.h]
        room.aisles = [
            (room.x + 2, room.y + top + 1, room.w - 4, bottom - top - 1)
            for top, bottom in zip(edges, edges[1:])
            if bottom - top > 1
        ]
    return True


def build_dungeon(
    layout: list[str],
    rng: random.Random,
    branches: Sequence[str] = (),
    chapter: int | None = None,
) -> DungeonMap:
    """Lay rooms of the given kinds along one winding path, in that order.

    ``branches`` are side rooms: dead ends off the path, each behind one door.
    The path keeps its order in ``rooms`` and the branches follow it, so the
    first room is always the start and ``rooms[main - 1]`` the way out.
    """

    for attempt in range(LAYOUT_TRIES):
        rows = 3 if attempt < LAYOUT_TRIES - 20 else 4 if attempt < LAYOUT_TRIES - 10 else 5
        cells = _walk(len(layout), rng, rows)
        # Running out of luck, the map just grows sideways until everything fits.
        spare = max(0, attempt - (LAYOUT_TRIES - 10))
        placed = _branch_cells(cells, branches, rng, rows, spare)
        if placed is not None:
            break
    else:  # pragma: no cover - with enough spare columns there is always room
        raise RuntimeError("no room for the side branches")

    every = cells + [cell for cell, _ in placed]
    width = (max(column for column, _ in every) + 1) * CELL_W + 4
    height = rows * CELL_H + 4
    dungeon = DungeonMap(width, height)
    dungeon.main = len(layout)

    kinds = list(layout) + list(branches)
    parents = [-1] * len(layout) + [host for _, host in placed]
    for index, (kind, (column, row)) in enumerate(zip(kinds, every)):
        room_w, room_h = _room_size(kind, rng)
        x = column * CELL_W + 2 + (CELL_W - room_w) // 2
        y = row * CELL_H + 2 + (CELL_H - room_h) // 2
        room = Room(index, x, y, room_w, room_h, kind, parent=parents[index])
        dungeon.rooms.append(room)
        dungeon.carve(x, y, room_w, room_h)

    path = dungeon.rooms[: len(layout)]
    for first, second in zip(path, path[1:]):
        _connect(dungeon, first, second, rng)
    for room in dungeon.rooms[len(layout) :]:
        _connect(dungeon, dungeon.rooms[room.parent], room, rng)

    # Corridors run clean through the rooms they meet, so a door tile is only
    # a door once the room around it has walls to hold it.
    for room in dungeon.rooms:
        room.doors = sorted(set(room.doors))
        if room.kind != "combat":
            continue
        shape = "pillars"
        if chapter is not None:
            shape = rng.choice(SHAPES_BY_CHAPTER[chapter])
        if shape == "plain":
            room.shape = "plain"
        elif shape == "pillars" or not _shape_room(dungeon, room, shape, rng):
            _place_pillars(dungeon, room, rng)
    return dungeon
