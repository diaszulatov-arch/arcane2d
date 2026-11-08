"""A room with no enemies, a locked way on, and a problem only a spell can solve.

The spell here is a tool: a mage writes it in the grimoire and casts it like any
other, but what it does is open a door, read a lamp, lay a bridge one piece at a
time or strike four targets at once.  Which problem a room holds depends on what
the party has been taught by that stage.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from .dungeon import FLOOR, PIT, TILE, Room
from .interpreter import SpellRuntimeError, UnitView

if TYPE_CHECKING:
    from .game import SpellSession
    from .story import StoryArena
    from .terrain import Prop

KNOCK_REACH = 1.0
LAMP_FLIP = (1.2, 2.3)
ZAP = 7.0
TARGET_WINDOW = 1.9
TARGET_COUNT = 4
BRIDGE_WIDTH = 3
BRIDGE_GLOW = 1.0
FAR_PART = 3

CARDS = {
    "knock": (
        "Мастерская: замок слушает",
        "# Замок откроется, если назвать ему\n# ваше здоровье прямо сейчас.\n# Запишите это в заклинание и сотворите:\n\nopen_door(me().hp)",
    ),
    "lamp": (
        "Мастерская: замок с лампой",
        "# lamp() говорит цвет: \"green\" или \"red\".\n# open_door() на зелёный открывает,\n# а на красный бьёт током.\n# Лампа мигает. Напишите условие\n# и держите каст.",
    ),
    "bridge": (
        "Мастерская: мост из кода",
        "# bridge(i) кладёт секцию номер i.\n# Секции держатся, только если весь мост\n# построен одним заклинанием.\n# Секций: {count}, номера с нуля.\n# Лишние строки не нужны: есть цикл.",
    ),
    "targets": (
        "Мастерская: четыре мишени",
        "# targets() возвращает список мишеней: .x .y\n# Замок откроется, если попасть во все\n# меньше чем за 2 секунды. Руками не успеть.\n# direction(x, y) даёт угол до точки.",
    ),
}
RUNE_NAMES = {
    "knock": ("open_door",),
    "lamp": ("open_door", "lamp"),
    "bridge": ("bridge",),
    "targets": ("targets",),
}


def kind_for_stage(index: int) -> str:
    """Only ask for what has been taught: loops come in chapter two, lists in three."""

    if index < 4:
        return "knock"
    if index < 8:
        return "lamp"
    if index < 12:
        return "bridge"
    return "targets"


class Workshop:
    def __init__(self, arena: "StoryArena", room: Room) -> None:
        self.arena = arena
        self.room = room
        self.kind = kind_for_stage(arena.stage.index)
        self.opened = False
        self.count = 0
        self.flip_at = 0.0
        self.pending: set[int] = set()
        self.pending_at = -1.0
        self.glow_until = 0.0
        self.segments: list[tuple[int, int, int, int]] = []
        self.targets: list["Prop"] = []
        self.hits: dict[int, float] = {}
        self.chest: Any = None
        self.lamp: Any = None
        self._lay_out()

    # ------------------------------------------------------------------- the room
    def _axis(self) -> tuple[bool, bool]:
        """Which way the room runs from its door, and whether the door is at the low end."""

        ux, uy = self.arena.quest._door_side(self.room)
        along_x = abs(ux) >= abs(uy)
        door_low = (ux < 0) if along_x else (uy < 0)
        return along_x, door_low

    def _band(self, thickness: int) -> list[tuple[int, int]]:
        """A strip across the room, near the far end, that cuts the reward off."""

        room = self.room
        along_x, door_low = self._axis()
        length = room.w if along_x else room.h
        start = length - FAR_PART - thickness if door_low else FAR_PART
        tiles = []
        for offset in range(start, start + thickness):
            for cross in range(room.h if along_x else room.w):
                tiles.append(
                    (room.x + offset, room.y + cross) if along_x else (room.x + cross, room.y + offset)
                )
        return tiles

    def _lay_out(self) -> None:
        quest = self.arena.quest
        room = self.room
        x, y = quest._far_end(room)
        self.chest = quest._add("chest", x, y, room, data={"use": "открыть тайник", "finds": True})
        if self.kind == "bridge":
            self._lay_bridge()
        else:
            self.arena.lock("workshop", self._band(1))
        if self.kind == "lamp":
            cx, cy = self._near_middle()
            self.lamp = quest._add("lamp", cx, cy, room)
        elif self.kind == "targets":
            self._hang_targets()

    def _near_middle(self) -> tuple[float, float]:
        ux, uy = self.arena.quest._door_side(self.room)
        cx, cy = self.room.center
        return cx + ux * 3 * TILE, cy + uy * 2 * TILE

    def _lay_bridge(self) -> None:
        room = self.room
        along_x, door_low = self._axis()
        cross = room.h if along_x else room.w
        length = room.w if along_x else room.h
        self.count = min(6, length // 2 - 2)
        for x, y in self._band(self.count):
            self.arena.dungeon.grid[y][x] = PIT
        first = (cross - BRIDGE_WIDTH) // 2
        start = length - FAR_PART - self.count if door_low else FAR_PART
        for index in range(self.count):
            # Section 0 is the one nearest the door, wherever the door is.
            step = start + index if door_low else start + self.count - 1 - index
            if along_x:
                self.segments.append((room.x + step, room.y + first, 1, BRIDGE_WIDTH))
            else:
                self.segments.append((room.x + first, room.y + step, BRIDGE_WIDTH, 1))

    def _hang_targets(self) -> None:
        terrain = self.arena.terrain
        cx, cy = self._near_middle()
        for index in range(TARGET_COUNT):
            angle = index / TARGET_COUNT * math.tau + 0.6
            x, y = self.arena.dungeon.open_near(cx + math.cos(angle) * 230, cy + math.sin(angle) * 150, 24.0)
            self.targets.append(
                terrain.add_prop("target", x, y, 26.0, self._target_hit, label=f"мишень {index + 1}")
            )

    # ---------------------------------------------------------------------- runes
    def runes(self, session: "SpellSession") -> dict[str, Any]:
        player = session.player

        def here() -> None:
            if not self.room.holds(player.x, player.y):
                raise SpellRuntimeError("Эта руна работает только в мастерской.")

        def open_door(value: Any = None) -> None:
            here()
            session._spend(0, "open_door")
            if self.kind == "knock":
                self._knock(player, value)
            elif self.kind == "lamp":
                self._try_lamp(player)
            else:
                raise SpellRuntimeError("В этой мастерской замок открывается иначе.")

        def lamp() -> str:
            here()
            if self.lamp is None:
                raise SpellRuntimeError("Лампы здесь нет.")
            return "green" if self.lamp.on else "red"

        def bridge(index: Any) -> None:
            here()
            session._spend(0, "bridge")
            self._lay_section(index)

        def targets() -> list[UnitView]:
            here()
            if self.kind != "targets":
                raise SpellRuntimeError("Мишеней здесь нет.")
            return [session._view(prop, "target", False) for prop in self.targets]

        return {"open_door": open_door, "lamp": lamp, "bridge": bridge, "targets": targets}

    def _knock(self, player: Any, value: Any) -> None:
        if self.opened:
            return
        if type(value) not in (int, float):
            raise SpellRuntimeError("Замок ждёт число: ваше здоровье.")
        if abs(value - player.hp) <= KNOCK_REACH:
            self._open()
            return
        self._zap(player, f"Это не ваше здоровье: у вас {round(player.hp)}.")

    def _try_lamp(self, player: Any) -> None:
        if self.opened:
            return
        if self.lamp.on:
            self._open()
        else:
            self._zap(player, "Красный! Замок бьёт током.")

    def _zap(self, player: Any, text: str) -> None:
        self.arena.emit({"e": "quest_note", "x": round(player.x, 1), "y": round(player.y, 1), "text": text})
        self.arena.damage(
            target=player, amount=ZAP, source=None, kind="zap", hit_x=player.x, hit_y=player.y
        )

    def _lay_section(self, index: Any) -> None:
        if self.kind != "bridge":
            raise SpellRuntimeError("Моста здесь нет.")
        if self.opened:
            return
        if type(index) is not int or not 0 <= index < self.count:
            raise SpellRuntimeError(f"Секции моста нумеруются от 0 до {self.count - 1}.")
        # A whole cast happens at one moment of the arena's clock.
        if self.pending_at != self.arena.now:
            self.pending.clear()
            self.pending_at = self.arena.now
        self.pending.add(index)
        self.glow_until = self.arena.now + BRIDGE_GLOW
        if len(self.pending) == self.count:
            self._complete_bridge()

    def _complete_bridge(self) -> None:
        grid = self.arena.dungeon.grid
        for x, y, w, h in self.segments:
            for row in range(y, y + h):
                for column in range(x, x + w):
                    grid[row][column] = FLOOR
        self.arena.emit({"e": "tiles", "rects": [list(segment) for segment in self.segments], "char": "."})
        self._open()

    def _target_hit(self, prop: "Prop", source: Any, kind: str) -> None:
        if self.opened:
            return
        now = self.arena.now
        self.hits = {key: at for key, at in self.hits.items() if now - at <= TARGET_WINDOW}
        self.hits[prop.id] = now
        terrain = self.arena.terrain
        terrain.lit = set(self.hits)
        self.arena.emit({"e": "quest_note", "x": round(prop.x, 1), "y": round(prop.y, 1), "text": "попадание", "good": True})
        if len(self.hits) >= TARGET_COUNT:
            terrain.lit = set()
            for target in self.targets:
                terrain.remove_prop(target)
            self._open()

    def _open(self) -> None:
        if self.opened:
            return
        self.opened = True
        self.arena.unlock("workshop")
        x, y = self.room.center
        self.arena.emit({"e": "workshop_open", "x": round(x, 1), "y": round(y, 1)})
        self.arena.quest._say((("Ада", "Вот так: код открыл то, что руками не открыть. Забирайте, что внутри."),), urgent=True)

    # --------------------------------------------------------------------- the tick
    def update(self, now: float) -> None:
        if self.lamp is not None and now >= self.flip_at:
            self.lamp.on = not self.lamp.on
            self.flip_at = now + self.arena.quest.rng.uniform(*LAMP_FLIP)
        if self.kind == "targets" and self.hits:
            live = {key for key, at in self.hits.items() if now - at <= TARGET_WINDOW}
            if live != set(self.hits):
                self.hits = {key: self.hits[key] for key in live}
                self.arena.terrain.lit = set(live)

    # -------------------------------------------------------------------- reports
    def sign(self) -> dict[str, Any]:
        title, code = CARDS[self.kind]
        room = self.room
        return {
            "room": room.index,
            "x": round(room.center[0], 1),
            "y": round(room.y * TILE + 34, 1),
            "title": title,
            "label": "мастерская",
            "code": code.format(count=self.count),
        }

    def rune_names(self) -> tuple[str, ...]:
        return RUNE_NAMES[self.kind]

    def snapshot(self) -> dict[str, Any] | None:
        if self.kind != "bridge" or self.opened:
            return None
        lit = [
            list(self.segments[index]) for index in sorted(self.pending)
        ] if self.glow_until > self.arena.now else []
        return {"glow": lit}
