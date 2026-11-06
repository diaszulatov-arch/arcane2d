"""Dungeon floors: rooms joined by corridors, on a grid of solid and open tiles.

A floor is a chain of rooms laid out by a short walk over a coarse lattice, so
every run differs but the path can never branch away from the exit.  Geometry
queries answer in world units, which is what the shared simulation speaks.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Iterable

TILE = 48
CELL_W = 34
CELL_H = 28
CORRIDOR_WIDTH = 4
PILLAR_SIZE = 2
TORCH_SPACING = 7

WALL = "#"
FLOOR = "."
PILLAR = "o"

ROOM_SIZES = {
    "start": (14, 12),
    "exit": (14, 12),
    "boss": (30, 24),
}

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


class DungeonMap:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.grid = [[WALL] * width for _ in range(height)]
        self.rooms: list[Room] = []
        self.closed: set[tuple[int, int]] = set()

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

    def rows(self) -> list[str]:
        return ["".join(row) for row in self.grid]

    def set_closed(self, tiles: Iterable[tuple[int, int]]) -> None:
        self.closed = set(tiles)

    # -------------------------------------------------------------- world space
    def blocked(self, x: float, y: float, radius: float) -> bool:
        """Whether a circle, or with no radius a single point, touches a solid tile."""

        if radius <= 0:
            return self.solid(math.floor(x / TILE), math.floor(y / TILE))
        left = math.floor((x - radius) / TILE)
        right = math.floor((x + radius) / TILE)
        top = math.floor((y - radius) / TILE)
        bottom = math.floor((y + radius) / TILE)
        for ty in range(top, bottom + 1):
            for tx in range(left, right + 1):
                if not self.solid(tx, ty):
                    continue
                nearest_x = max(tx * TILE, min(x, (tx + 1) * TILE))
                nearest_y = max(ty * TILE, min(y, (ty + 1) * TILE))
                if (x - nearest_x) ** 2 + (y - nearest_y) ** 2 < radius * radius:
                    return True
        return False

    def path_clear(
        self, x1: float, y1: float, x2: float, y2: float, radius: float = 0.0
    ) -> bool:
        length = math.hypot(x2 - x1, y2 - y1)
        steps = max(1, math.ceil(length / 16))
        for step in range(1, steps + 1):
            at = step / steps
            if self.blocked(x1 + (x2 - x1) * at, y1 + (y2 - y1) * at, radius):
                return False
        return True

    def ray_end(
        self, x: float, y: float, dx: float, dy: float, length: float
    ) -> tuple[float, float]:
        travelled = 0.0
        while travelled < length:
            advance = min(12.0, length - travelled)
            if self.blocked(x + dx * (travelled + advance), y + dy * (travelled + advance), 0.0):
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
        return room.center

    def torches(self) -> list[list[float]]:
        """Sconces along the wall above each room, the face the camera can see."""

        lights: list[list[float]] = []
        for room in self.rooms:
            for tx in range(room.x + 3, room.x + room.w - 2, TORCH_SPACING):
                if self.grid[room.y - 1][tx] == WALL:
                    lights.append([(tx + 0.5) * TILE, (room.y - 0.5) * TILE])
        return lights


def _walk(count: int, rng: random.Random) -> list[tuple[int, int]]:
    """A self-avoiding walk across the lattice that drifts toward the right."""

    height = 3
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
    return rng.randint(20, 26), rng.randint(15, 20)


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
    else:
        slack = min(first.w, second.w) // 2 - half - 1
        shift = rng.randint(-slack, slack)
        x = (ax + bx) // 2 + shift - half
        top, bottom = sorted((ay, by))
        dungeon.carve(x, top, CORRIDOR_WIDTH, bottom - top)
        for room in (first, second):
            gate = room.y - 1 if room.y > top else room.y + room.h
            room.doors.extend((x + offset, gate) for offset in range(CORRIDOR_WIDTH))


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


def build_dungeon(layout: list[str], rng: random.Random) -> DungeonMap:
    """Lay rooms of the given kinds along one winding path, in that order."""

    cells = _walk(len(layout), rng)
    width = (max(column for column, _ in cells) + 1) * CELL_W + 4
    height = 3 * CELL_H + 4
    dungeon = DungeonMap(width, height)

    for index, (kind, (column, row)) in enumerate(zip(layout, cells)):
        room_w, room_h = _room_size(kind, rng)
        x = column * CELL_W + 2 + (CELL_W - room_w) // 2
        y = row * CELL_H + 2 + (CELL_H - room_h) // 2
        room = Room(index, x, y, room_w, room_h, kind)
        dungeon.rooms.append(room)
        dungeon.carve(x, y, room_w, room_h)

    for first, second in zip(dungeon.rooms, dungeon.rooms[1:]):
        _connect(dungeon, first, second, rng)

    # Corridors run clean through the rooms they meet, so a door tile is only
    # a door once the room around it has walls to hold it.
    for room in dungeon.rooms:
        room.doors = sorted(set(room.doors))
        if room.kind == "combat":
            _place_pillars(dungeon, room, rng)
    return dungeon
