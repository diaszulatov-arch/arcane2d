"""The strange things bosses do: each one a joke about what that boss really is.

A syntax error leaves a string open, a feed scrolls the floor out from under you,
None deletes the ground, an index counts from zero and PGT offers to make it all
stop.  Each lives here as a small object that the arena ticks until it is over.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from .dungeon import TILE
from .game import TICK_RATE, Player

if TYPE_CHECKING:
    from .monsters import Monster
    from .story import StoryArena

STRING_TEXT = 'print("Привет, мир! Это очень длинная строка, и она никогда не закончится '
STRING_TIME = 8.0
STRING_SPEED = 215.0
STRING_STEP = 30.0
STRING_MAX = 70
STRING_TOUCH = 26.0
STRING_DAMAGE = 7.0
STRING_HEAD = 13.0
STRING_BITE_EVERY = 0.5
QUOTE_DELAY = 0.8
QUOTE_REACH = 58.0
QUOTE_STUN = 2.6
BLINK_RADIUS = 92.0
BLINK_BEAT = 0.95
BLINK_WARN = 0.35
BLINK_BEATS = 5
BLINK_FIRST = 0.6
BLINK_DAMAGE = 14.0
SCROLL_TIME = 6.5
SCROLL_PULL = 92.0
SCROLL_STRIP = 96.0
SCROLL_DAMAGE = 7.0
SCROLL_BITE_EVERY = 0.5
SCROLL_WALL_EVERY = 1.75
SCROLL_WALL_SPEED = 190.0
SCROLL_WALL_SPACING = 58.0
SCROLL_GAP = 130.0
BAIT_TIME = 7.0
BAIT_REACH = 50.0
BAIT_HEAL = 30.0
BAIT_BLAST = 96.0
BAIT_DAMAGE = 15.0
BAIT_SLOW = 2.4
BAIT_FAKES = ("ВЫ НЕ ПОВЕРИТЕ!", "+100 HP БЕСПЛАТНО", "ЖМИ СЮДА", "МАГИ ЕГО НЕНАВИДЯТ")
BAIT_REAL = "аптечка"
RETURN_TIME = 3.6
RETURN_EVERY = 0.16
RETURN_SHOT = 360.0
RETURN_EXPOSED = 2.4
DEL_CELL = 2
DEL_WARN = 1.0
DEL_VOID = 3.6
DEL_WAVES = 4
DEL_WAVE_EVERY = 1.25
DEL_SHARE = 0.13
DEL_DAMAGE = 6.0
DEL_BITE_EVERY = 0.4
COLUMNS_TIME = 3.2
COLUMNS_REVEAL = 0.75
COLUMNS_DAMAGE = 30.0
BISECT_FUSE = 0.95
BISECT_STEPS = 4
BISECT_DAMAGE = 22.0
BISECT_MIN = 150.0
BISECT_STUN = 2.2
ACCEPT_TIME = 4.2
ACCEPT_DAMAGE = 48.0
ACCEPT_RADIUS = 92.0
ACCEPT_HEAL = 0.07
REJECT_RADIUS = 58.0
AUTOCOMPLETE_STEPS = (0.8, 1.15, 1.5)
AUTOCOMPLETE_RADIUS = 74.0
AUTOCOMPLETE_DAMAGE = 18.0


def stagger(world: "StoryArena", monster: "Monster", seconds: float) -> None:
    """Outplayed: it stands there, and hits to it land harder."""

    monster.stun_until = max(monster.stun_until, world.now + seconds)
    monster.dizzy_until = max(monster.dizzy_until, world.now + seconds)


class BossMove:
    """Something a boss set going, which goes on by itself until it is finished."""

    kind = ""

    def __init__(self, world: "StoryArena", monster: "Monster") -> None:
        self.world = world
        self.monster = monster
        self.bitten: dict[int, float] = {}

    def update(self, now: float, dt: float) -> bool:
        """One tick. False means it is over."""

        return False

    def view(self) -> dict[str, Any]:
        return {"k": self.kind}

    def bite(self, mage: Player, amount: float, every: float) -> None:
        """Damage that keeps on while you stand in it, not once a tick."""

        now = self.world.now
        if now < self.bitten.get(mage.id, 0.0):
            return
        self.bitten[mage.id] = now + every
        self.hit(mage, amount)

    def hit(self, mage: Player, amount: float) -> None:
        self.world.damage(target=mage, amount=amount, source=self.monster, kind="hazard", hit_x=mage.x, hit_y=mage.y)

    def box(self) -> tuple[float, float, float, float]:
        return self.world.room_box()

    def floor_spot(self, x: float, y: float, radius: float = 26.0) -> tuple[float, float]:
        return self.world.dungeon.open_near(x, y, radius)


class UnclosedString(BossMove):
    """A string nobody closed: it follows you and stays where it has been, until you close it."""

    kind = "string"

    def __init__(self, world: "StoryArena", monster: "Monster") -> None:
        super().__init__(world, monster)
        self.until = world.now + STRING_TIME
        self.head = (monster.x, monster.y)
        self.cells: list[tuple[float, float, str]] = []
        self.walked = 0.0
        self.index = 0
        self.quote: tuple[float, float] | None = None
        self.quote_at = world.now + QUOTE_DELAY

    def _place_quote(self, target: Player) -> None:
        left, top, right, bottom = self.box()
        # Across the room from the mage: closing it means crossing your own string.
        x = left + right - target.x
        y = top + bottom - target.y
        self.quote = self.floor_spot(x, y)

    def update(self, now: float, dt: float) -> bool:
        world = self.world
        living = world.hunted()
        if not living or now >= self.until:
            return False
        target = min(living, key=lambda mage: math.hypot(mage.x - self.head[0], mage.y - self.head[1]))
        if self.quote is None and now >= self.quote_at:
            self._place_quote(target)
        gap = math.hypot(target.x - self.head[0], target.y - self.head[1]) or 1.0
        step = STRING_SPEED * dt
        self.head = (
            self.head[0] + (target.x - self.head[0]) / gap * step,
            self.head[1] + (target.y - self.head[1]) / gap * step,
        )
        self.walked += step
        if self.walked >= STRING_STEP and len(self.cells) < STRING_MAX:
            self.walked = 0.0
            self.cells.append((self.head[0], self.head[1], STRING_TEXT[self.index % len(STRING_TEXT)]))
            self.index += 1
        for mage in living:
            if self.quote is not None and math.hypot(mage.x - self.quote[0], mage.y - self.quote[1]) <= QUOTE_REACH:
                self._close()
                return False
            if math.hypot(mage.x - self.head[0], mage.y - self.head[1]) <= STRING_TOUCH + mage.radius:
                self.bite(mage, STRING_HEAD, STRING_BITE_EVERY)
                continue
            if any(math.hypot(mage.x - x, mage.y - y) <= STRING_TOUCH for x, y, _ in self.cells):
                self.bite(mage, STRING_DAMAGE, STRING_BITE_EVERY)
        return True

    def _close(self) -> None:
        world = self.world
        monster = self.monster
        stagger(world, monster, QUOTE_STUN)
        world.emit({"e": "string_closed", "cells": [[round(x, 1), round(y, 1)] for x, y, _ in self.cells[::3]], "id": monster.id})
        world.announce_error(monster, 'print("...")  # строка закрыта')

    def view(self) -> dict[str, Any]:
        return {
            "k": self.kind,
            "head": [round(self.head[0], 1), round(self.head[1], 1)],
            "cells": [[round(x, 1), round(y, 1), char] for x, y, char in self.cells],
            "quote": [round(self.quote[0], 1), round(self.quote[1], 1)] if self.quote else None,
        }


class Blink(BossMove):
    """The tag everyone hated: circles of floor that take it in turns to be on fire."""

    kind = "blink"

    def __init__(self, world: "StoryArena", monster: "Monster") -> None:
        super().__init__(world, monster)
        left, top, right, bottom = self.box()
        self.cells: list[tuple[float, float, int]] = []
        step = BLINK_RADIUS * 2.15
        row = 0
        y = top + BLINK_RADIUS * 0.8
        while y < bottom:
            x = left + BLINK_RADIUS * 0.8 + (step / 2 if row % 2 else 0)
            column = 0
            while x < right:
                self.cells.append((x, y, (column + row) % 2))
                x += step
                column += 1
            y += step * 0.86
            row += 1
        self.beat = 0
        self.on = 0
        # A little longer the first time: nobody has yet seen which ones are lit.
        self.next_beat = world.now + BLINK_BEAT + BLINK_FIRST
        self.bit = False

    def update(self, now: float, dt: float) -> bool:
        if now >= self.next_beat:
            self.beat += 1
            self.on = 1 - self.on
            self.next_beat = now + BLINK_BEAT
            self.bit = False
            if self.beat > BLINK_BEATS:
                return False
        if not self.bit and now >= self.next_beat - BLINK_BEAT + BLINK_WARN:
            self.bit = True
            for mage in self.world.hunted():
                if any(group == self.on and math.hypot(mage.x - x, mage.y - y) <= BLINK_RADIUS for x, y, group in self.cells):
                    self.hit(mage, BLINK_DAMAGE)
        return True

    def view(self) -> dict[str, Any]:
        return {
            "k": self.kind,
            "r": BLINK_RADIUS,
            "cells": [[round(x, 1), round(y, 1), group] for x, y, group in self.cells],
            "on": self.on,
            "hot": self.bit,
        }


class DoomScroll(BossMove):
    """The floor itself scrolls. There is a bottom of the page, and it is unpleasant."""

    kind = "doomscroll"

    def __init__(self, world: "StoryArena", monster: "Monster") -> None:
        super().__init__(world, monster)
        self.until = world.now + SCROLL_TIME
        self.next_wall = world.now + 0.5

    def update(self, now: float, dt: float) -> bool:
        if now >= self.until:
            return False
        world = self.world
        left, top, right, bottom = self.box()
        for mage in world.hunted():
            world.try_move(mage, 0.0, SCROLL_PULL * dt)
            if mage.y >= bottom - SCROLL_STRIP:
                self.bite(mage, SCROLL_DAMAGE, SCROLL_BITE_EVERY)
        if now >= self.next_wall:
            self.next_wall = now + SCROLL_WALL_EVERY
            gap = world.rng.uniform(left + SCROLL_GAP, right - SCROLL_GAP)
            x = left
            life = (bottom - top) / SCROLL_WALL_SPEED
            while x <= right:
                if abs(x - gap) > SCROLL_GAP / 2:
                    world.fire_from(self.monster, x, top, math.pi / 2, speed=SCROLL_WALL_SPEED, life=life)
                x += SCROLL_WALL_SPACING
        return True

    def view(self) -> dict[str, Any]:
        left, top, right, bottom = self.box()
        return {"k": self.kind, "box": [left, top, right, bottom], "strip": SCROLL_STRIP}


class Bait(BossMove):
    """Headlines on the floor. The one that does not shout is the only one telling the truth."""

    kind = "bait"

    def __init__(self, world: "StoryArena", monster: "Monster") -> None:
        super().__init__(world, monster)
        self.until = world.now + BAIT_TIME
        left, top, right, bottom = self.box()
        labels = list(BAIT_FAKES)
        world.rng.shuffle(labels)
        labels = labels[:3] + [BAIT_REAL]
        world.rng.shuffle(labels)
        self.items: list[dict[str, Any]] = []
        for index, label in enumerate(labels):
            x = left + (right - left) * (0.2 + 0.6 * ((index % 2) + world.rng.random() * 0.2))
            y = top + (bottom - top) * (0.22 + 0.5 * (index // 2) + world.rng.random() * 0.1)
            spot = self.floor_spot(x, y)
            self.items.append({"x": spot[0], "y": spot[1], "label": label, "real": label == BAIT_REAL})

    def update(self, now: float, dt: float) -> bool:
        if now >= self.until or not self.items:
            return False
        world = self.world
        for mage in world.hunted():
            for item in list(self.items):
                if math.hypot(mage.x - item["x"], mage.y - item["y"]) > BAIT_REACH:
                    continue
                self.items.remove(item)
                if item["real"]:
                    mage.hp = min(mage.max_hp, mage.hp + BAIT_HEAL)
                    world.emit({"e": "heal", "id": mage.id, "x": round(mage.x, 1), "y": round(mage.y, 1), "amount": BAIT_HEAL})
                    world.emit({"e": "quest_note", "x": round(item["x"], 1), "y": round(item["y"], 1), "text": "Правда аптечка", "good": True})
                else:
                    world.emit({"e": "quest_note", "x": round(item["x"], 1), "y": round(item["y"], 1), "text": "Вы не поверите: это ловушка", "good": False})
                    world.emit({"e": "hazard_blast", "x": round(item["x"], 1), "y": round(item["y"], 1), "x2": None, "y2": None, "radius": BAIT_BLAST, "color": "#ff6b9e"})
                    for other in world.hunted():
                        if math.hypot(other.x - item["x"], other.y - item["y"]) <= BAIT_BLAST:
                            self.hit(other, BAIT_DAMAGE)
                            other.slow_until = max(other.slow_until, now + BAIT_SLOW)
        return True

    def view(self) -> dict[str, Any]:
        return {
            "k": self.kind,
            "items": [[round(i["x"], 1), round(i["y"], 1), i["label"], i["real"]] for i in self.items],
        }


class ReturnNone(BossMove):
    """For a while she gives back whatever she is given, and what she gives back is yours."""

    kind = "return"

    def __init__(self, world: "StoryArena", monster: "Monster") -> None:
        super().__init__(world, monster)
        self.until = world.now + RETURN_TIME
        monster.returning_until = self.until
        self.ready_at = 0.0

    def refuses(self, source: Player | None) -> None:
        now = self.world.now
        if source is None or now < self.ready_at:
            return
        self.ready_at = now + RETURN_EVERY
        monster = self.monster
        angle = math.atan2(source.y - monster.y, source.x - monster.x)
        self.world.fire_from(monster, monster.x, monster.y, angle, speed=RETURN_SHOT, life=2.0)
        self.world.emit({"e": "quest_note", "x": round(monster.x, 1), "y": round(monster.y - 50, 1), "text": "return None", "good": False})

    def update(self, now: float, dt: float) -> bool:
        if now < self.until:
            return True
        # Held her breath for too long: for a moment she can be hurt rather more than usual.
        self.monster.exposed_until = max(self.monster.exposed_until, now + RETURN_EXPOSED)
        return False

    def view(self) -> dict[str, Any]:
        return {"k": self.kind, "id": self.monster.id, "left": round(max(0.0, self.until - self.world.now), 2)}


class DelFloor(BossMove):
    """del floor[i]: bits of the room stop existing, and what stands there is None."""

    kind = "del"

    def __init__(self, world: "StoryArena", monster: "Monster") -> None:
        super().__init__(world, monster)
        left, top, right, bottom = self.box()
        self.size = DEL_CELL * TILE
        self.grid = [
            (x, y)
            for y in _steps(top, bottom, self.size)
            for x in _steps(left, right, self.size)
        ]
        world.rng.shuffle(self.grid)
        self.cells: list[dict[str, float]] = []
        self.waves = DEL_WAVES
        self.next_wave = world.now

    def update(self, now: float, dt: float) -> bool:
        if self.waves > 0 and now >= self.next_wave:
            self.waves -= 1
            self.next_wave = now + DEL_WAVE_EVERY
            for _ in range(max(1, round(len(self.grid) * DEL_SHARE))):
                if self.grid:
                    x, y = self.grid.pop()
                    self.cells.append({"x": x, "y": y, "from": now + DEL_WARN, "to": now + DEL_WARN + DEL_VOID})
        self.cells = [cell for cell in self.cells if now < cell["to"]]
        for mage in self.world.hunted():
            for cell in self.cells:
                if cell["from"] <= now and cell["x"] <= mage.x < cell["x"] + self.size and cell["y"] <= mage.y < cell["y"] + self.size:
                    self.bite(mage, DEL_DAMAGE, DEL_BITE_EVERY)
                    break
        return self.waves > 0 or bool(self.cells)

    def view(self) -> dict[str, Any]:
        now = self.world.now
        return {
            "k": self.kind,
            "size": self.size,
            "cells": [[c["x"], c["y"], 1 if now >= c["from"] else 0] for c in self.cells],
        }


def _steps(start: float, stop: float, step: float) -> list[float]:
    values = []
    value = start
    while value + step <= stop + 1:
        values.append(value)
        value += step
    return values


# What the Indexer can say, and what it means. A test asks Python if these are honest.
INDEX_PHRASES: tuple[tuple[str, Any], ...] = (
    ("rows[0]", lambda rows: rows[0]),
    ("rows[1]", lambda rows: rows[1]),
    ("rows[2]", lambda rows: rows[2]),
    ("rows[3]", lambda rows: rows[3]),
    ("rows[-1]", lambda rows: rows[-1]),
    ("rows[-2]", lambda rows: rows[-2]),
    ("rows[1:3]", lambda rows: rows[1:3]),
    ("rows[-2:]", lambda rows: rows[-2:]),
    ("rows[len(rows) - 1]", lambda rows: rows[len(rows) - 1]),
)


def safe_rows(meaning: Any, count: int) -> list[int]:
    picked = meaning(list(range(count)))
    return picked if isinstance(picked, list) else [picked]


class ZeroIndex(BossMove):
    """It names the one safe row in Python. Whoever counts from one is standing in the wrong one."""

    kind = "columns"

    def __init__(self, world: "StoryArena", monster: "Monster") -> None:
        super().__init__(world, monster)
        self.count = 5 + monster.phase
        self.phrase, meaning = world.rng.choice(INDEX_PHRASES[: 4 + monster.phase * 3 + (1 if monster.phase else 0)])
        self.safe = safe_rows(meaning, self.count)
        self.until = world.now + COLUMNS_TIME
        world.announce_error(monster, f"safe = {self.phrase}  # считаем с нуля")

    def _column(self, x: float) -> int:
        left, _, right, _ = self.box()
        return max(0, min(self.count - 1, int((x - left) / ((right - left) / self.count))))

    def update(self, now: float, dt: float) -> bool:
        if now < self.until:
            return True
        left, top, right, bottom = self.box()
        wide = (right - left) / self.count
        for column in range(self.count):
            if column in self.safe:
                continue
            x = left + wide * (column + 0.5)
            self.world.emit(
                {"e": "hazard_blast", "x": round(x, 1), "y": round(top, 1), "x2": round(x, 1), "y2": round(bottom, 1), "radius": wide, "color": "#ffae5c"}
            )
        for mage in self.world.hunted():
            if self._column(mage.x) not in self.safe:
                self.hit(mage, COLUMNS_DAMAGE)
        return False

    def view(self) -> dict[str, Any]:
        left, top, right, bottom = self.box()
        ttl = max(0.0, self.until - self.world.now)
        entry: dict[str, Any] = {
            "k": self.kind,
            "box": [left, top, right, bottom],
            "n": self.count,
            "phrase": self.phrase,
            "ttl": round(ttl, 2),
        }
        # In the last moment it shows its working, so that the lesson is learnt alive.
        if ttl <= COLUMNS_REVEAL:
            entry["safe"] = self.safe
        return entry


class Bisect(BossMove):
    """A binary search for you. Be where the answer is not, and it raises ValueError."""

    kind = "bisect"

    def __init__(self, world: "StoryArena", monster: "Monster") -> None:
        super().__init__(world, monster)
        self.lo, _, self.hi, _ = self.box()
        self.steps = BISECT_STEPS
        self.side: tuple[float, float] | None = None
        self.fuse_at = 0.0
        self._next(world.now)

    def _inside(self, low: float, high: float) -> list[Player]:
        return [mage for mage in self.world.hunted() if low <= mage.x <= high]

    def _next(self, now: float) -> bool:
        searched = self._inside(self.lo, self.hi)
        if not searched or self.steps <= 0 or self.hi - self.lo < BISECT_MIN:
            if not searched:
                # It looked everywhere it thought you could be.
                monster = self.monster
                stagger(self.world, monster, BISECT_STUN)
                self.world.announce_error(monster, "ValueError: mage is not in list")
            return False
        self.steps -= 1
        middle = (self.lo + self.hi) / 2
        low_side = (self.lo, middle)
        high_side = (middle, self.hi)
        self.side = low_side if len(self._inside(*low_side)) >= len(self._inside(*high_side)) else high_side
        self.fuse_at = now + BISECT_FUSE
        return True

    def update(self, now: float, dt: float) -> bool:
        if self.side is None:
            return False  # Nobody was in the room to search for when it began.
        if now < self.fuse_at:
            return True
        low, high = self.side
        _, top, _, bottom = self.box()
        x = (low + high) / 2
        self.world.emit(
            {"e": "hazard_blast", "x": round(x, 1), "y": round(top, 1), "x2": round(x, 1), "y2": round(bottom, 1), "radius": high - low, "color": "#ffae5c"}
        )
        for mage in self._inside(low, high):
            self.hit(mage, BISECT_DAMAGE)
        self.lo, self.hi = low, high
        return self._next(now)

    def view(self) -> dict[str, Any]:
        _, top, _, bottom = self.box()
        return {
            "k": self.kind,
            "lo": round(self.lo, 1),
            "hi": round(self.hi, 1),
            "side": [round(self.side[0], 1), round(self.side[1], 1)] if self.side else None,
            "top": top,
            "bottom": bottom,
            "ttl": round(max(0.0, self.fuse_at - self.world.now), 2),
            "fuse": BISECT_FUSE,
        }


class AcceptAll(BossMove):
    """Everything he has, on everyone. Unless you press the button. It is right there, and it is big."""

    kind = "accept"

    def __init__(self, world: "StoryArena", monster: "Monster") -> None:
        super().__init__(world, monster)
        self.until = world.now + ACCEPT_TIME
        left, top, right, bottom = self.box()
        mages = world.hunted()
        mage = mages[0] if mages else monster
        # The easy one is near you, and the honest one as far away as the room allows.
        angle = world.rng.uniform(0, math.tau)
        self.accept = self.floor_spot(
            max(left + 120, min(right - 120, mage.x + math.cos(angle) * 230)),
            max(top + 120, min(bottom - 120, mage.y + math.sin(angle) * 180)),
        )
        self.reject = self.floor_spot(left + right - mage.x, top + bottom - mage.y)

    def update(self, now: float, dt: float) -> bool:
        if now < self.until:
            return True
        world = self.world
        left, top, right, bottom = self.box()
        world.emit({"e": "deploy_blast", "x": round((left + right) / 2, 1), "y": round((top + bottom) / 2, 1)})
        for mage in world.hunted():
            if math.hypot(mage.x - self.accept[0], mage.y - self.accept[1]) <= ACCEPT_RADIUS + mage.radius:
                world.accepted_in_battle.append(mage.id)
                monster = self.monster
                monster.hp = min(monster.max_hp, monster.hp + monster.max_hp * ACCEPT_HEAL)
                world.emit({"e": "quest_note", "x": round(mage.x, 1), "y": round(mage.y - 50, 1), "text": "Принято. Спасибо!", "good": False})
                world.quest_say("PGT", "Принято. Видите, как просто? Я стал чуть лучше. Благодаря вам.")
                continue
            if math.hypot(mage.x - self.reject[0], mage.y - self.reject[1]) <= REJECT_RADIUS + mage.radius:
                world.emit({"e": "quest_note", "x": round(mage.x, 1), "y": round(mage.y - 50, 1), "text": "Отклонено", "good": True})
                continue
            self.hit(mage, ACCEPT_DAMAGE)
        return False

    def view(self) -> dict[str, Any]:
        return {
            "k": self.kind,
            "accept": [round(self.accept[0], 1), round(self.accept[1], 1), ACCEPT_RADIUS],
            "reject": [round(self.reject[0], 1), round(self.reject[1], 1), REJECT_RADIUS],
            "ttl": round(max(0.0, self.until - self.world.now), 2),
        }


def autocomplete(world: "StoryArena", monster: "Monster") -> None:
    """He finishes your movement for you, and is waiting at the end of it."""

    for mage in world.hunted():
        vx = (mage.x - mage.last_x) * TICK_RATE
        vy = (mage.y - mage.last_y) * TICK_RATE
        for delay in AUTOCOMPLETE_STEPS:
            x, y = world.dungeon.open_near(mage.x + vx * delay, mage.y + vy * delay, 20.0)
            world.place_hazard(
                monster, x, y, radius=AUTOCOMPLETE_RADIUS, delay=delay, damage=AUTOCOMPLETE_DAMAGE,
                color="#9aa0b4", label="вы пойдёте сюда",
            )


# Each boss takes its tricks in turn, so a long one cannot keep the other from ever coming up.
ROTATION: dict[str, tuple[str, ...]] = {
    "bracket": ("unclosed", "blink"),
    "scroll": ("doomscroll", "bait"),
    "nullqueen": ("return_none", "del_floor"),
    "indexer": ("zero_index", "bisect"),
    "pgt": ("accept_all",),
}

MOVES: dict[str, type[BossMove]] = {
    "unclosed": UnclosedString,
    "blink": Blink,
    "doomscroll": DoomScroll,
    "bait": Bait,
    "return_none": ReturnNone,
    "del_floor": DelFloor,
    "zero_index": ZeroIndex,
    "bisect": Bisect,
    "accept_all": AcceptAll,
}
