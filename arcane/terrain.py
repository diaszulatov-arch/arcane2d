"""What a stage's rooms are made of, beyond walls: its rules and its breakable things.

Every chapter has one rule of place, because the places themselves are different:
the Old Web has hyperlinks and half-built pages, the Feed drags you along, the
Cloud has wind, the Data Centre has hot and cold aisles, and in the Core PGT
refactors the room around you.  On top of that, rooms hold things that answer
to spells: monitors break, batteries blow, water freezes or carries a shock,
cables burn.  None of it needs a hand-written fight to be interesting.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from .dungeon import FLOOR, PIT, TILE, Room
from .game import Player

if TYPE_CHECKING:
    from .story import StoryArena

PROP_ID_BASE = 80_000
FIGHT_KINDS = frozenset({"combat"})
QUIET_ROOMS = frozenset({"vault", "cache", "rest", "deal"})

CRATE_RADIUS = 24.0
BATTERY_RADIUS = 20.0
BLAST_RADIUS = 150.0
BLAST_DAMAGE = 70.0
BLAST_SELF = 12.0
CHAIN_DELAY = 0.14

PUDDLE_RADIUS = 96.0
CABLE_REACH = 34.0
ICE_TIME = 9.0
SHOCK_DAMAGE = 46.0
SHOCK_SELF = 10.0
SHOCK_REST = 3.0
BURN_TIME = 4.5
BURN_EVERY = 0.5
BURN_DAMAGE = 14.0
BURN_SELF = 5.0
SHOCK_KINDS = frozenset({"chain", "lightning", "spark"})

LINK_REACH = 40.0
LINK_REST = 1.4
BUILD_EVERY = (8.0, 13.0)
BUILD_FUSE = 1.5
BUILD_DAMAGE = 16.0
BELT_SPEED = 96.0
GUST_EVERY = (9.0, 14.0)
GUST_TIME = 3.5
GUST_PUSH = 62.0
GUST_DRIFT = 150.0
AISLE_EVERY = 0.5
AISLE_BURN = 2.2
AISLE_MANA = 3.5
REFACTOR_EVERY = 8.5
REFACTOR_FUSE = 1.3
REFACTOR_BLOCKS = 5

RULE_INTROS: tuple[tuple[tuple[str, str], ...], ...] = (
    (
        ("Ада", "Старый Веб держится на честном слове. Синие ссылки на полу — телепорты: встаньте, и вас перекинет на другой конец."),
        ("Ада", "А жёлтые полосы «в разработке» иногда проваливаются. Услышите треск — сойдите."),
    ),
    (("Ада", "Пол в Ленте сам куда-то едет. Конвейер тащит и вас, и багов: используйте это."),),
    (
        ("Ада", "В Облаке нет дна. По провалам не пройти, зато снаряды летят над ними свободно."),
        ("Ада", "И ветер: порыв сносит снаряды, причём и ваши тоже."),
    ),
    (("Ада", "В Дата-Центре между стойками чередуются горячие и холодные коридоры. В горячем жжёт, в холодном мана идёт быстрее."),),
    (("PGT", "Я рефакторю этот зал прямо сейчас. Стены будут появляться там, где я решу. Не благодарите."),),
)
PROP_TIP: tuple[tuple[str, str], ...] = (
    ("Ада", "Комнаты живые. Старые мониторы можно разбить, в них бывает полезное. Батареи взрываются и задевают багов."),
    ("Ада", "Лужу можно заморозить, и баги на льду замедлятся, а молния ударит всех, кто в ней стоит. Кабели горят от огня."),
)


@dataclass(slots=True)
class Prop(Player):
    """Something a spell can hit that is not an enemy: it never shows up in enemies()."""

    kind: str = "crate"
    on_hit: Callable[["Prop", Player | None, str], None] | None = None


@dataclass(slots=True)
class Surface:
    """A patch of the floor that reacts to magic passing over it."""

    id: int
    kind: str
    x: float
    y: float
    x2: float = 0.0
    y2: float = 0.0
    state: str = ""
    until: float = 0.0
    next_tick: float = 0.0
    source: Player | None = None

    def covers(self, x: float, y: float) -> bool:
        if self.kind == "puddle":
            return math.hypot(x - self.x, y - self.y) <= PUDDLE_RADIUS
        dx, dy = self.x2 - self.x, self.y2 - self.y
        length = dx * dx + dy * dy or 1.0
        at = max(0.0, min(1.0, ((x - self.x) * dx + (y - self.y) * dy) / length))
        return math.hypot(x - (self.x + dx * at), y - (self.y + dy * at)) <= CABLE_REACH


def _pad_tiles(spot: tuple[float, float]) -> set[tuple[int, int]]:
    """The tiles a hyperlink pad covers: touching any of them may set it off."""

    x, y = int(spot[0] // TILE), int(spot[1] // TILE)
    return {(x + a, y + b) for a in (-1, 0, 1) for b in (-1, 0, 1)}


class StageTerrain:
    def __init__(self, arena: "StoryArena") -> None:
        self.arena = arena
        self.chapter = arena.stage.chapter_index
        self.rng = random.Random(arena.seed ^ 0x7E44A1)
        self.props: dict[int, Prop] = {}
        self.all_props: list[dict[str, Any]] = []
        self.gone: list[int] = []
        self.lit: set[int] = set()
        self.surfaces: list[Surface] = []
        self.belts: list[tuple[float, float, float, float, float, float]] = []
        self.links: list[list[Any]] = []
        self.builds: list[dict[str, Any]] = []
        self.aisles: list[tuple[float, float, float, float, str]] = []
        self.link_rest: dict[int, float] = {}
        self.pad_tiles: set[tuple[int, int]] = set()
        self.gust: tuple[float, float] | None = None
        self.gust_at = arena.now + self.rng.uniform(*GUST_EVERY)
        self.gust_until = 0.0
        self.gust_told = False
        self.aisle_at = 0.0
        self.refactor_at = 0.0
        self._next_id = PROP_ID_BASE
        self._populate()

    # ------------------------------------------------------------ the furniture
    def add_prop(
        self,
        kind: str,
        x: float,
        y: float,
        radius: float,
        on_hit: Callable[["Prop", Player | None, str], None] | None = None,
        label: str = "",
    ) -> Prop:
        prop = Prop(
            id=self._next_id, name=label or kind, color="#ffd27a", x=x, y=y,
            radius=radius, hp=1.0, max_hp=1.0, kind=kind, on_hit=on_hit,
        )
        self._next_id += 1
        self.props[prop.id] = prop
        entry: dict[str, Any] = {"id": prop.id, "k": kind, "x": round(x, 1), "y": round(y, 1)}
        if label:
            entry["label"] = label
        self.all_props.append(entry)
        return prop

    def _spot(self, room: Room, taken: list[tuple[float, float]], radius: float = 30.0) -> tuple[float, float]:
        dungeon = self.arena.dungeon
        spot = dungeon.open_point(room, self.rng, radius)
        for _ in range(12):
            if all(math.hypot(spot[0] - x, spot[1] - y) > 110 for x, y in taken):
                break
            spot = dungeon.open_point(room, self.rng, radius)
        taken.append(spot)
        return spot

    def _populate(self) -> None:
        for room in self.arena.dungeon.rooms:
            taken: list[tuple[float, float]] = []
            if room.kind in FIGHT_KINDS:
                self._furnish_fight(room, taken)
                self._apply_rule(room, taken)
            elif room.kind in QUIET_ROOMS:
                for _ in range(self.rng.randint(1, 2)):
                    self.add_prop("crate", *self._spot(room, taken), CRATE_RADIUS)

    def _furnish_fight(self, room: Room, taken: list[tuple[float, float]]) -> None:
        rng = self.rng
        for _ in range(rng.randint(3, 5)):
            self.add_prop("crate", *self._spot(room, taken), CRATE_RADIUS)
        for _ in range(rng.randint(1, 2)):
            self.add_prop("battery", *self._spot(room, taken), BATTERY_RADIUS)
        x, y = self._spot(room, taken, 70.0)
        self.surfaces.append(Surface(len(self.surfaces) + 1, "puddle", x, y))
        x, y = self._spot(room, taken, 30.0)
        angle = rng.uniform(0, math.tau)
        reach = rng.uniform(220, 340)
        x2, y2 = self.arena.ray_end(x, y, math.cos(angle), math.sin(angle), reach)
        self.surfaces.append(Surface(len(self.surfaces) + 1, "cable", x, y, x2, y2))

    def _apply_rule(self, room: Room, taken: list[tuple[float, float]]) -> None:
        if self.chapter == 0:
            first = self._link_spot(room, taken)
            second = self._link_spot(room, taken)
            if first is not None and second is not None:
                self.links.append([*first, *second])
            for _ in range(self.rng.randint(1, 2)):
                x, y = self._spot(room, taken, 60.0)
                self.builds.append({
                    "x": x - 72, "y": y - 72, "w": 144.0, "h": 144.0,
                    "room": room, "at": self.arena.now + self.rng.uniform(*BUILD_EVERY),
                })
        elif self.chapter == 1:
            self._lay_belts(room)
        elif self.chapter == 3:
            for index, (x, y, w, h) in enumerate(room.aisles):
                self.aisles.append((x * TILE, y * TILE, w * TILE, h * TILE, "hot" if index % 2 else "cold"))

    def _link_spot(self, room: Room, taken: list[tuple[float, float]]) -> tuple[float, float] | None:
        """Well away from any door, and never in the only gap of a partition.

        Stepping on a pad throws you across the room. In a gap that would be a wall
        you can never get through, so a room with no good place simply has no link.
        """

        for _ in range(20):
            spot = self._spot(room, taken)
            clear = all(
                math.hypot((dx + 0.5) * TILE - spot[0], (dy + 0.5) * TILE - spot[1]) > 5 * TILE
                for dx, dy in room.doors
            )
            if clear and self._passable_with(room, _pad_tiles(spot)):
                self.pad_tiles |= _pad_tiles(spot)
                return spot
            taken.pop()
        return None

    def _passable_with(self, room: Room, pad: set[tuple[int, int]]) -> bool:
        """Whether the whole floor of the room, doors included, still connects around the pads."""

        grid = self.arena.dungeon.grid
        blocked = pad | self.pad_tiles
        doors = set(room.doors)
        if not doors:
            return True
        start = next(iter(doors))
        seen = {start}
        frontier = [start]
        while frontier:
            x, y = frontier.pop()
            for tile in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if tile in seen or tile in blocked:
                    continue
                inside = room.x <= tile[0] < room.x + room.w and room.y <= tile[1] < room.y + room.h
                if tile in doors or (inside and grid[tile[1]][tile[0]] == FLOOR):
                    seen.add(tile)
                    frontier.append(tile)
        if not doors <= seen:
            return False
        # No pockets either: a corner reachable only across a pad is a trap.
        return all(
            (x, y) in seen or (x, y) in blocked or grid[y][x] != FLOOR
            for y in range(room.y, room.y + room.h)
            for x in range(room.x, room.x + room.w)
        )

    def _lay_belts(self, room: Room) -> None:
        rng = self.rng
        for _ in range(rng.randint(1, 2)):
            sign = rng.choice((-1.0, 1.0))
            if rng.random() < 0.5:
                row = rng.randint(room.y + 2, room.y + room.h - 5)
                self.belts.append(
                    (room.x * TILE, row * TILE, room.w * TILE, 3 * TILE, BELT_SPEED * sign, 0.0)
                )
            else:
                column = rng.randint(room.x + 2, room.x + room.w - 5)
                self.belts.append(
                    (column * TILE, room.y * TILE, 3 * TILE, room.h * TILE, 0.0, BELT_SPEED * sign)
                )

    # ---------------------------------------------------------------- spells hit
    def prop_hit(self, prop: Prop, source: Player | None, kind: str) -> None:
        if prop.id not in self.props:
            return
        if prop.on_hit is not None:
            prop.on_hit(prop, source, kind)
            return
        self.remove_prop(prop)
        self.arena.stats.broken += 1
        if prop.kind == "battery":
            self._blast(prop, source)
        else:
            self._break_crate(prop)

    def remove_prop(self, prop: Prop) -> None:
        if self.props.pop(prop.id, None) is not None:
            self.gone.append(prop.id)

    def _break_crate(self, prop: Prop) -> None:
        arena = self.arena
        arena.emit({"e": "prop_break", "x": round(prop.x, 1), "y": round(prop.y, 1)})
        roll = self.rng.random()
        if roll < 0.2:
            arena._add_pickup("hp", prop.x, prop.y)
        elif roll < 0.42:
            arena._add_pickup("mana", prop.x, prop.y)
        elif roll < 0.56:
            arena.essence += 1
            arena.emit({"e": "loot", "x": round(prop.x, 1), "y": round(prop.y, 1), "amount": 1})

    def _blast(self, prop: Prop, source: Player | None) -> None:
        arena = self.arena
        x, y = prop.x, prop.y
        arena.emit({"e": "prop_blast", "x": round(x, 1), "y": round(y, 1), "radius": BLAST_RADIUS})
        for monster in list(arena.monsters.values()):
            if math.hypot(monster.x - x, monster.y - y) <= BLAST_RADIUS + monster.radius and not monster.quest:
                arena.damage(
                    target=monster, amount=BLAST_DAMAGE, source=source, kind="blast",
                    hit_x=monster.x, hit_y=monster.y,
                )
        for mage in arena.hunted():
            if math.hypot(mage.x - x, mage.y - y) <= BLAST_RADIUS + mage.radius:
                arena.damage(
                    target=mage, amount=BLAST_SELF, source=None, kind="blast",
                    hit_x=mage.x, hit_y=mage.y,
                )
        # One battery in a row of them is never just one battery.
        for other in list(self.props.values()):
            if other.kind == "battery" and math.hypot(other.x - x, other.y - y) <= BLAST_RADIUS:
                self.remove_prop(other)
                arena.after(CHAIN_DELAY, lambda other=other: self._blast(other, source))

    def on_damage(self, kind: str, x: float, y: float, source: Player | None) -> None:
        """Lightning that lands in water is everyone's problem."""

        if kind not in SHOCK_KINDS:
            return
        for surface in self.surfaces:
            if surface.kind == "puddle" and surface.state != "shock" and surface.covers(x, y):
                self._shock(surface, source)

    def _shock(self, surface: Surface, source: Player | None) -> None:
        arena = self.arena
        if surface.next_tick > arena.now:
            return
        surface.state = "shock"
        surface.until = arena.now + 0.7
        surface.next_tick = arena.now + SHOCK_REST
        arena.emit({"e": "surface_shock", "x": round(surface.x, 1), "y": round(surface.y, 1)})
        for monster in list(arena.monsters.values()):
            if surface.covers(monster.x, monster.y) and not monster.quest:
                arena.damage(
                    target=monster, amount=SHOCK_DAMAGE, source=source, kind="shock",
                    hit_x=monster.x, hit_y=monster.y,
                )
        for mage in arena.hunted():
            if surface.covers(mage.x, mage.y):
                arena.damage(
                    target=mage, amount=SHOCK_SELF, source=None, kind="shock",
                    hit_x=mage.x, hit_y=mage.y,
                )

    def _update_surfaces(self, now: float) -> None:
        arena = self.arena
        for surface in self.surfaces:
            if surface.state in ("ice", "shock", "burn") and now >= surface.until:
                surface.state = "burnt" if surface.state == "burn" else ""
            if surface.state == "ice":
                for monster in arena.monsters.values():
                    if surface.covers(monster.x, monster.y):
                        monster.slow_until = max(monster.slow_until, now + 0.5)
            elif surface.state == "burn" and now >= surface.next_tick:
                surface.next_tick = now + BURN_EVERY
                self._burn(surface)
        for shot in arena.projectiles:
            if shot.owner >= PROP_ID_BASE:
                continue
            for surface in self.surfaces:
                if not surface.covers(shot.x, shot.y):
                    continue
                self._shot_over(surface, shot, now)

    def _shot_over(self, surface: Surface, shot: Any, now: float) -> None:
        source = self.arena.players.get(shot.owner)
        if surface.kind == "cable":
            if shot.kind == "fire" and surface.state == "":
                surface.state = "burn"
                surface.until = now + BURN_TIME
                surface.next_tick = now
                surface.source = source
                self.arena.emit({
                    "e": "surface_burn", "x": round((surface.x + surface.x2) / 2, 1),
                    "y": round((surface.y + surface.y2) / 2, 1),
                })
        elif shot.kind == "frost" and surface.state == "":
            surface.state = "ice"
            surface.until = now + ICE_TIME
            self.arena.emit({"e": "surface_ice", "x": round(surface.x, 1), "y": round(surface.y, 1)})
        elif shot.kind == "fire" and surface.state == "ice":
            surface.state = ""
        elif shot.kind in SHOCK_KINDS and surface.state != "shock":
            self._shock(surface, source)

    def _burn(self, surface: Surface) -> None:
        arena = self.arena
        for monster in list(arena.monsters.values()):
            if surface.covers(monster.x, monster.y) and not monster.quest:
                arena.damage(
                    target=monster, amount=BURN_DAMAGE, source=surface.source, kind="burn",
                    hit_x=monster.x, hit_y=monster.y,
                )
        for mage in arena.hunted():
            if surface.covers(mage.x, mage.y):
                arena.damage(
                    target=mage, amount=BURN_SELF, source=None, kind="burn",
                    hit_x=mage.x, hit_y=mage.y,
                )

    # ------------------------------------------------------------ the chapter rule
    def update(self, now: float, dt: float) -> None:
        self._update_surfaces(now)
        if self.links:
            self._update_links(now)
        if self.builds:
            self._update_builds(now)
        if self.belts:
            self._update_belts(dt)
        if self.chapter == 2:
            self._update_wind(now, dt)
        if self.aisles and now >= self.aisle_at:
            self.aisle_at = now + AISLE_EVERY
            self._update_aisles()
        if self.chapter == 4:
            self._update_refactor(now)

    def _update_links(self, now: float) -> None:
        for mage in self.arena.hunted():
            if self.link_rest.get(mage.id, 0.0) > now:
                continue
            for x1, y1, x2, y2 in self.links:
                if math.hypot(mage.x - x1, mage.y - y1) <= LINK_REACH:
                    self._jump(mage, x2, y2, now)
                    break
                if math.hypot(mage.x - x2, mage.y - y2) <= LINK_REACH:
                    self._jump(mage, x1, y1, now)
                    break

    def _jump(self, mage: Player, x: float, y: float, now: float) -> None:
        self.link_rest[mage.id] = now + LINK_REST
        self.arena.emit({
            "e": "link_jump", "id": mage.id, "from_x": round(mage.x, 1), "from_y": round(mage.y, 1),
            "x": round(x, 1), "y": round(y, 1),
        })
        mage.x, mage.y = x, y

    def _update_builds(self, now: float) -> None:
        arena = self.arena
        for build in self.builds:
            if now < build["at"]:
                continue
            build["at"] = now + self.rng.uniform(*BUILD_EVERY)
            room: Room = build["room"]
            if not any(room.holds(m.x, m.y) for m in arena.hunted()):
                continue
            y = build["y"] + build["h"] / 2
            arena.trap_beam(build["x"], y, build["x"] + build["w"], y, build["h"], BUILD_FUSE, BUILD_DAMAGE)

    def _update_belts(self, dt: float) -> None:
        arena = self.arena
        bodies = [*arena.hunted(), *(m for m in arena.monsters.values() if not m.species.heavy)]
        for x, y, w, h, vx, vy in self.belts:
            for body in bodies:
                if x <= body.x <= x + w and y <= body.y <= y + h:
                    arena.try_move(body, vx * dt, vy * dt)

    def _update_wind(self, now: float, dt: float) -> None:
        if self.gust is None:
            if now < self.gust_at:
                return
            angle = self.rng.uniform(0, math.tau)
            self.gust = (math.cos(angle), math.sin(angle))
            self.gust_until = now + GUST_TIME
            self.arena.emit({"e": "gust"})
            return
        if now >= self.gust_until:
            self.gust = None
            self.gust_at = now + self.rng.uniform(*GUST_EVERY)
            return
        ux, uy = self.gust
        for shot in self.arena.projectiles:
            shot.x += ux * GUST_DRIFT * dt
            shot.y += uy * GUST_DRIFT * dt
        dungeon = self.arena.dungeon
        for mage in self.arena.hunted():
            room = dungeon.room_at(mage.x, mage.y)
            if room is not None and room.kind in FIGHT_KINDS:
                self.arena.try_move(mage, ux * GUST_PUSH * dt, uy * GUST_PUSH * dt)

    def _update_aisles(self) -> None:
        arena = self.arena
        for mage in arena.hunted():
            for x, y, w, h, kind in self.aisles:
                if not (x <= mage.x <= x + w and y <= mage.y <= y + h):
                    continue
                if kind == "hot":
                    arena.damage(
                        target=mage, amount=AISLE_BURN, source=None, kind="heat",
                        hit_x=mage.x, hit_y=mage.y,
                    )
                else:
                    mage.mana = min(mage.max_mana, mage.mana + AISLE_MANA)
                break

    def _update_refactor(self, now: float) -> None:
        arena = self.arena
        room = arena.active_room
        if room is None or room.kind not in FIGHT_KINDS:
            if "refactor" in arena.locks:
                arena.unlock("refactor")
            self.refactor_at = now + 3.0
            return
        if now < self.refactor_at:
            return
        self.refactor_at = now + REFACTOR_EVERY * arena.difficulty.tempo
        blocks = self._refactor_blocks(room)
        for x, y in blocks:
            arena.trap_mark((x + 1) * TILE, (y + 1) * TILE, 70.0, REFACTOR_FUSE, "refactor")
        arena.after(REFACTOR_FUSE, lambda: self._raise_blocks(room, blocks))

    def _refactor_blocks(self, room: Room) -> list[tuple[int, int]]:
        dungeon = self.arena.dungeon
        spots: list[tuple[int, int]] = []
        for _ in range(40):
            if len(spots) >= REFACTOR_BLOCKS:
                break
            x = self.rng.randint(room.x + 2, room.x + room.w - 4)
            y = self.rng.randint(room.y + 2, room.y + room.h - 4)
            near_door = any(abs(dx - x) < 4 and abs(dy - y) < 4 for dx, dy in room.doors)
            crowded = any(abs(ox - x) < 4 and abs(oy - y) < 4 for ox, oy in spots)
            if near_door or crowded:
                continue
            if any(dungeon.grid[y + b][x + a] == PIT or dungeon.solid(x + a, y + b) for a in (0, 1) for b in (0, 1)):
                continue
            spots.append((x, y))
        return spots

    def _raise_blocks(self, room: Room, blocks: list[tuple[int, int]]) -> None:
        arena = self.arena
        if arena.active_room is not room:
            return
        bodies = [*arena.players.values(), *arena.monsters.values()]
        tiles: set[tuple[int, int]] = set()
        for x, y in blocks:
            block = {(x + a, y + b) for a in (0, 1) for b in (0, 1)}
            occupied = any(
                (x - 1) * TILE <= body.x <= (x + 3) * TILE and (y - 1) * TILE <= body.y <= (y + 3) * TILE
                for body in bodies
            )
            if not occupied:
                tiles |= block
        arena.lock("refactor", tiles)

    # -------------------------------------------------------------------- reports
    def describe(self) -> dict[str, Any]:
        stage = self.arena.stage
        intro: list[list[str]] = []
        if stage.number == 1:
            intro += [list(line) for line in RULE_INTROS[self.chapter]]
        if stage.index == 0:
            intro += [list(line) for line in PROP_TIP]
        return {
            "chapter": self.chapter,
            "intro": intro,
            "props": self.all_props,
            "surfaces": [
                {"id": s.id, "k": s.kind, "x": round(s.x, 1), "y": round(s.y, 1), "x2": round(s.x2, 1), "y2": round(s.y2, 1)}
                for s in self.surfaces
            ],
            "belts": [[round(v, 1) for v in belt] for belt in self.belts],
            "links": [[round(v, 1) for v in link] for link in self.links],
            "builds": [[round(b["x"], 1), round(b["y"], 1), b["w"], b["h"]] for b in self.builds],
            "aisles": [[*(round(v, 1) for v in aisle[:4]), aisle[4]] for aisle in self.aisles],
        }

    def snapshot(self) -> dict[str, Any]:
        state: dict[str, Any] = {"gone": self.gone}
        heated = {s.id: s.state for s in self.surfaces if s.state}
        if heated:
            state["surf"] = heated
        if self.gust is not None:
            state["gust"] = [round(self.gust[0], 2), round(self.gust[1], 2)]
        if self.lit:
            state["lit"] = sorted(self.lit)
        return state
