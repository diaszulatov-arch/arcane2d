"""A stage's problem and its odd side rooms, played out inside a StoryArena.

``StageQuest`` owns everything a stage has besides fights and terminals: the
machine in the quest room, the things lying about (backups, files, a packet
with a TTL), circles to stand in, plates to step on, a lost DNS request to walk
home.  It moves the quest on step by step and tells the arena when the way to
the main terminal may open.

The arena stays the authority on bodies and damage.  A machine or a person
the party must protect is a ``QuestUnit``: a ``Player`` the way a monster is,
so bites and bolts reach it without special cases.
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from .campaign import ADA, Line
from .dungeon import FLOOR, TILE, Room
from .game import MOVE_SPEED, Player
from .interpreter import Interpreter, SpellError, safe_globals
from .monsters import SPECIES, Monster
from .quest_games import QuestGames
from .quest_data import (
    CACHE_LINES,
    DEAL_ACCEPT,
    DEAL_BUG,
    DEALS,
    MIMIC_LINES,
    NOTE,
    PGT_ACCEPTED,
    PGT_DEBT,
    PUZZLE_FAIL,
    PUZZLE_TEMPLATES,
    PUZZLE_WIN,
    QUEST_TASKS,
    RANGE_TEMPLATE,
    REST_NOTES,
    TRAP_LINES,
    TRIAL_LOST,
    TRIAL_START,
    TRIAL_WIN,
    Deal,
    Quest,
    Step,
)

if TYPE_CHECKING:
    from .story import StoryArena

UNIT_ID_BASE = 90_000
# Hazards from the room itself: an owner id past every monster, so they hit mages.
TRAP_OWNER = 1_000_000_000
USE_REACH = 96.0
ITEM_REACH = 48.0
PLATE_REACH = 40.0
PLATE_RING = 230.0
CONSOLE_OFFSET = 96.0
NPC_NOTICE = 230.0
NPC_GAP = 84.0
NPC_SPEED = 172.0
DEST_REACH = 120.0
REVIVE_REACH = 96.0
REVIVE_TIME = 2.4
FOCUS_BREAK = 130.0
DEVICE_REBOOT = 4.0
DEFEND_SETBACK = 0.2
DEFEND_FOCUS = 0.7
ESCORT_FOCUS = 0.4
UNIT_SCALE = 0.35
BURST_RADIUS = 104.0
BURST_DAMAGE = 16.0
CARRY_PACE = 1.9
CARRY_SPARE = 8.0
CARRY_CHASE = 7.0
DROP_GRACE = 1.2
DEBT_DELAY = 18.0
ZAP_DAMAGE = 8.0
TRAP_EVERY = 1.6
TRAP_FUSE = 1.0
TRAP_DAMAGE = 14.0
TRAP_WIDTH = 44.0
TRAP_SPACING = 144.0
TRIAL_TIME = 34.0
MIMIC_CHANCE = 0.3
PLATE_COUNT = 5

ATTACK_RUNES = (
    "fireball",
    "frostbolt",
    "spark_volley",
    "nova",
    "beam",
    "chain_lightning",
    "lightning_strike",
    "meteor",
    "poison_cloud",
    "siphon",
    "emp",
)


@dataclass(slots=True)
class QuestUnit(Player):
    """A machine or a person the party keeps alive. Monsters can reach it."""

    sprite: str = ""
    label: str = ""
    targetable: bool = False
    down_until: float = 0.0
    revive_left: float = 0.0
    status: str = ""
    charge: float = 0.0


@dataclass(slots=True)
class Thing:
    """Something lying in a room: an item, a circle, a plate, a chest, an altar."""

    id: int
    kind: str
    x: float
    y: float
    room: int
    label: str = ""
    color: str = ""
    bad: bool = False
    on: bool = False
    charge: float = 0.0
    until: float = 0.0
    number: int = 0
    holder: int = 0
    gone: bool = False
    data: dict[str, Any] = field(default_factory=dict)

    def view(self) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "id": self.id,
            "k": self.kind,
            "x": round(self.x, 1),
            "y": round(self.y, 1),
            "room": self.room,
        }
        if self.label:
            entry["label"] = self.label
        if self.color:
            entry["color"] = self.color
        if self.bad:
            entry["bad"] = True
        if self.on:
            entry["on"] = True
        if self.charge:
            entry["charge"] = round(min(1.0, self.charge), 2)
        if self.number:
            entry["n"] = self.number
        if self.holder:
            entry["holder"] = self.holder
        use = self.data.get("use")
        if use and not self.on:
            entry["use"] = use
        if self.data.get("view"):
            entry.update(self.data["view"])
        return entry


@dataclass(slots=True)
class PlateBoard:
    """Numbered plates and the code on the wall that says which order opens them."""

    room: Room
    plates: list[Thing]
    sequence: list[int]
    code: str
    sign: tuple[float, float]
    hub: tuple[float, float]
    radius: float = PLATE_RING
    active: bool = False
    position: int = 0
    solved: bool = False
    on_solved: Callable[[], None] | None = None
    fail_lines: tuple[Line, ...] = ()
    told_at: float = -100.0


def make_code(
    rng: random.Random, chapter: int, plates: int, template: str = ""
) -> tuple[str, list[int]]:
    """A few lines that press plates, and the order they really press them in.

    The order is found by running the code in the same sandbox as spells, so
    what the wall says and what the lock wants can never disagree.
    """

    if template == "range":
        pool = [RANGE_TEMPLATE]
    else:
        pool = [text for level in range(min(chapter, 4) + 1) for text in PUZZLE_TEMPLATES[level]]
        pool += list(PUZZLE_TEMPLATES[min(chapter, 4)])
    for _ in range(400):
        text = rng.choice(pool)
        values = {
            "a": rng.randint(1, plates),
            "b": rng.randint(-1, plates + 1),
            "c": rng.randint(1, plates),
            "d": rng.randint(1, plates),
            "e": rng.randint(1, plates),
            "f": rng.randint(1, plates),
            "s": rng.choice((-2, -1, 1, 2)),
            "t": rng.randint(1, plates - 1),
            "i": rng.randint(0, 3),
            "j": rng.randint(0, 3),
            "k": rng.randint(1, plates),
        }
        if "{s}" in text and "range" not in text:
            values["s"] = rng.randint(1, 2)
        code = text.format(**values)
        sequence = _pressed(code)
        if (
            sequence is not None
            and 3 <= len(sequence) <= 4
            and len(set(sequence)) == len(sequence)
            and all(1 <= number <= plates for number in sequence)
        ):
            return code, sequence
    return "press(1)\npress(3)\npress(2)\n", [1, 3, 2]


def _pressed(code: str) -> list[int] | None:
    pressed: list[Any] = []
    api = safe_globals({"press": pressed.append, "print": lambda *args: None})
    try:
        Interpreter(code, api).run()
    except SpellError:
        return None
    if not all(type(value) is int for value in pressed):
        return None
    return pressed


class StageQuest(QuestGames):
    """The problem of one stage, plus the odd rooms beside the way through."""

    def __init__(self, arena: "StoryArena", quest: Quest | None, chapter: int, first: bool) -> None:
        self.arena = arena
        self.quest = quest
        self.chapter = chapter
        self.first = first
        self.rng = random.Random(arena.seed ^ 0x5EED)
        self.things: dict[int, Thing] = {}
        self.units: dict[int, QuestUnit] = {}
        self.boards: list[PlateBoard] = []
        self.features: list[dict[str, Any]] = []
        self.index = 0
        self.done = quest is None
        self.state: dict[str, Any] = {}
        self.power = 1.0
        self.deal: Deal | None = None
        self.deal_bug_at = math.inf
        self.deal_told = False
        self.debts: list[float] = []
        self.trial: dict[str, Any] | None = None
        self._next_thing = 1
        self._next_unit = UNIT_ID_BASE
        dungeon = arena.dungeon
        self.tagged = {room.tag: room for room in dungeon.rooms if room.tag}
        self.quest_room = next((room for room in dungeon.path if room.kind == "quest"), None)
        self.device: QuestUnit | None = None
        if quest is not None and self.quest_room is not None:
            x, y = self.quest_room.center
            self.device = self._add_unit(quest.device, quest.label, x, y - 40, 200.0, 34.0)
            for step in quest.steps:
                if step.kind == "plates":
                    self.quest_board = self._make_board(
                        self.quest_room,
                        int(step.opts.get("plates", PLATE_COUNT)),
                        str(step.opts.get("template", "")),
                        step.fail,
                    )
        self._setup_features()
        if quest is not None:
            self._begin(0, quiet=True)

    # ---------------------------------------------------------------- helpers
    @property
    def step(self) -> Step | None:
        if self.quest is None or self.done:
            return None
        return self.quest.steps[self.index]

    @property
    def scale(self) -> float:
        return 1 + UNIT_SCALE * (self.arena.party_size - 1)

    def _add(self, kind: str, x: float, y: float, room: Room, **fields: Any) -> Thing:
        thing = Thing(self._next_thing, kind, x, y, room.index, **fields)
        self._next_thing += 1
        self.things[thing.id] = thing
        return thing

    def _add_unit(
        self, sprite: str, label: str, x: float, y: float, hp: float, radius: float
    ) -> QuestUnit:
        unit = QuestUnit(
            id=self._next_unit,
            name=label,
            color="#7fe0ee",
            x=x,
            y=y,
            hp=hp,
            max_hp=hp,
            radius=radius,
            sprite=sprite,
            label=label,
        )
        self._next_unit += 1
        self.units[unit.id] = unit
        return unit

    def _living(self) -> list[Player]:
        return self.arena.hunted()

    def _say(self, lines: tuple[Line, ...] | list[Line], urgent: bool = False) -> None:
        if lines:
            self.arena.emit({"e": "radio", "lines": [list(line) for line in lines], "urgent": urgent})

    def _toucher(self, x: float, y: float, reach: float, skip: int = 0) -> Player | None:
        best: Player | None = None
        best_distance = reach
        for player in self._living():
            if player.id == skip:
                continue
            distance = math.hypot(player.x - x, player.y - y)
            if distance <= best_distance:
                best, best_distance = player, distance
        return best

    def _inside(self, room: Room, inset: float = 0.0) -> list[Player]:
        return [player for player in self._living() if room.holds(player.x, player.y, inset)]

    def _room(self, tag: str, used: set[int]) -> Room:
        dungeon = self.arena.dungeon
        if tag in ("quest", "device") and self.quest_room is not None:
            return self.quest_room
        if tag in self.tagged:
            return self.tagged[tag]
        fights = [room for room in dungeon.path if room.kind == "combat"]
        fresh = [room for room in fights if room.index not in used] or fights
        if not fresh:
            return self.quest_room or dungeon.rooms[0]
        room = self.rng.choice(fresh)
        used.add(room.index)
        return room

    def _rooms(self, tags: tuple[str, ...], count: int) -> list[tuple[str, Room]]:
        used: set[int] = set()
        picked: list[tuple[str, Room]] = []
        for index in range(count):
            tag = tags[index % len(tags)] if tags else "path"
            picked.append((tag, self._room(tag, used)))
        return picked

    def _spot(self, room: Room, radius: float = 26.0) -> tuple[float, float]:
        """A free point near the middle of a room, or its far end for a trap corridor."""

        if room.kind == "trap":
            return self._far_end(room)
        cx, cy = room.center
        for _ in range(40):
            x = cx + self.rng.uniform(-0.28, 0.28) * room.w * TILE
            y = cy + self.rng.uniform(-0.28, 0.28) * room.h * TILE
            if self.arena.can_stand(x, y, radius):
                return x, y
        return self.arena.dungeon.open_near(cx, cy, radius)

    @staticmethod
    def _door_side(room: Room) -> tuple[float, float]:
        if not room.doors:
            return 0.0, 0.0
        dx = sum(x for x, _ in room.doors) / len(room.doors) + 0.5
        dy = sum(y for _, y in room.doors) / len(room.doors) + 0.5
        cx, cy = room.x + room.w / 2, room.y + room.h / 2
        length = math.hypot(dx - cx, dy - cy) or 1.0
        return (dx - cx) / length, (dy - cy) / length

    def _far_end(self, room: Room) -> tuple[float, float]:
        ux, uy = self._door_side(room)
        cx, cy = room.center
        reach_x = (room.w / 2 - 2.2) * TILE
        reach_y = (room.h / 2 - 2.2) * TILE
        return cx - ux * reach_x, cy - uy * reach_y

    def _ring(self, room: Room, count: int, radius: float = PLATE_RING) -> list[tuple[float, float]]:
        cx, cy = room.center
        turn = self.rng.uniform(0, math.tau)
        return [
            (
                cx + math.cos(turn + index / count * math.tau) * radius,
                cy + math.sin(turn + index / count * math.tau) * radius * 0.78,
            )
            for index in range(count)
        ]

    def _exit_point(self) -> tuple[float, float]:
        room = self.arena.exit_room
        ux, uy = self._door_side(room)
        cx, cy = room.center
        return cx + ux * ((room.w / 2 + 2.5) * TILE), cy + uy * ((room.h / 2 + 2.5) * TILE)

    def _target(self, name: str) -> tuple[float, float]:
        if name == "exit":
            return self._exit_point()
        if self.device is not None:
            return self.device.x, self.device.y
        return self.arena.exit_room.center

    def _path_tiles(self, start: tuple[float, float], end: tuple[float, float]) -> int:
        """Walking distance in tiles, through doors whether or not they are shut."""

        grid = self.arena.dungeon.grid
        first = (int(start[0] // TILE), int(start[1] // TILE))
        goal = (int(end[0] // TILE), int(end[1] // TILE))
        seen = {first: 0}
        frontier = deque([first])
        while frontier:
            x, y = frontier.popleft()
            if (x, y) == goal:
                return seen[(x, y)]
            for tile in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                tx, ty = tile
                if tile in seen or not (0 <= ty < len(grid) and 0 <= tx < len(grid[0])):
                    continue
                if grid[ty][tx] != FLOOR:
                    continue
                seen[tile] = seen[(x, y)] + 1
                frontier.append(tile)
        return int(math.hypot(end[0] - start[0], end[1] - start[1]) / TILE * 1.5)

    def _pack(
        self,
        room: Room,
        share: float,
        *,
        focus: QuestUnit | None = None,
        tag: str = "",
        near: tuple[float, float] | None = None,
    ) -> list[Monster]:
        """A handful of this chapter's bugs, sized like part of a wave."""

        arena = self.arena
        budget = arena._wave_budget() * share
        roster = [SPECIES[key] for key in arena.stage.roster]
        cheapest = min(species.cost for species in roster)
        spawned: list[Monster] = []
        while budget >= cheapest:
            species = self.rng.choice([entry for entry in roster if entry.cost <= budget])
            budget -= species.cost
            for _ in range(species.pack):
                monster = (
                    self._spawn_around(near, species.key)
                    if near is not None
                    else arena._spawn_in_room(room, species)
                )
                if monster is None:
                    continue
                if tag:
                    monster.quest = tag
                if focus is not None and self.rng.random() < DEFEND_FOCUS:
                    monster.focus = focus.id
                spawned.append(monster)
        return spawned

    def _spawn_around(self, point: tuple[float, float], key: str) -> Monster | None:
        arena = self.arena
        species = SPECIES[key]
        for _ in range(16):
            angle = self.rng.uniform(0, math.tau)
            reach = self.rng.uniform(260, 360)
            x = point[0] + math.cos(angle) * reach
            y = point[1] + math.sin(angle) * reach
            if arena.can_stand(x, y, species.radius) and arena.dungeon.path_clear(
                point[0], point[1], x, y, species.radius * 0.8
            ):
                return arena.spawn_monster(key, x, y)
        return None

    def _loot(self, x: float, y: float, amount: int) -> None:
        arena = self.arena
        arena.essence += amount
        for _ in range(max(1, arena.party_size)):
            arena._add_pickup("hp", x + self.rng.uniform(-50, 50), y + self.rng.uniform(-50, 50))
            arena._add_pickup("mana", x + self.rng.uniform(-50, 50), y + self.rng.uniform(-50, 50))
        arena.emit({"e": "loot", "x": round(x, 1), "y": round(y, 1), "amount": amount})

    # ----------------------------------------------------------------- steps
    def _begin(self, index: int, quiet: bool = False) -> None:
        step = self.quest.steps[index]
        self.index = index
        self.state = {"need": step.count, "done": 0}
        getattr(self, f"_begin_{step.kind}")(step)
        if not quiet:
            self.arena.emit({"e": "quest_step", "index": index, "text": self._text()})
            self._say(step.say, urgent=True)

    def _complete(self) -> None:
        if self.index + 1 < len(self.quest.steps):
            self._begin(self.index + 1)
            return
        self.done = True
        self.state = {}
        for unit in list(self.units.values()):
            if unit.sprite == "request":
                self.units.pop(unit.id)
                self.arena.emit({"e": "npc_gone", "x": round(unit.x, 1), "y": round(unit.y, 1)})
        reward = 14 + 5 * self.chapter
        self.arena.essence += reward
        self.arena.emit({"e": "quest_done", "title": self.quest.title, "amount": reward})
        self._say(self.quest.outro, urgent=True)
        self.arena.quest_solved()

    def _each(self, step: Step, number: int) -> None:
        if 0 < number <= len(step.each):
            self._say(step.each[number - 1])

    # hunt: catch or kill the creatures this problem is made of
    def _begin_hunt(self, step: Step) -> None:
        tag = f"{self.quest.key}:{self.index}"
        self.state.update(tag=tag, pending=[room for _, room in self._rooms(step.at, step.count)])

    def _tick_hunt(self, step: Step, now: float, dt: float) -> None:
        arena = self.arena
        species = str(step.opts["species"])
        for room in list(self.state["pending"]):
            if room.index not in arena.revealed:
                continue
            x, y = self._far_from_mages(room)
            monster = arena.spawn_monster(species, x, y)
            if monster is None:
                continue
            monster.quest = self.state["tag"]
            self.state["pending"].remove(room)
        alive = self._hunted()
        self.state["left"] = len(alive) + len(self.state["pending"])
        if not self.state["left"]:
            self._complete()

    def _hunted(self) -> list[Monster]:
        tag = self.state.get("tag")
        return [monster for monster in self.arena.monsters.values() if tag and monster.quest == tag]

    def _far_from_mages(self, room: Room) -> tuple[float, float]:
        living = self._living()
        best = room.center
        best_gap = -1.0
        for _ in range(10):
            x, y = self.arena.dungeon.open_point(room, self.rng, 34.0)
            gap = min((math.hypot(p.x - x, p.y - y) for p in living), default=1e9)
            if gap > best_gap:
                best, best_gap = (x, y), gap
        return best

    # collect: walk over the things the problem needs
    def _begin_collect(self, step: Step) -> None:
        item = str(step.opts.get("item", ""))
        labels = step.opts.get("labels") or (item,) * step.count
        items = []
        for index, (_, room) in enumerate(self._rooms(step.at, step.count)):
            x, y = self._spot(room)
            items.append(self._add("item", x, y, room, label=labels[index % len(labels)]))
        bad = step.opts.get("bad", ())
        for index, (_, room) in enumerate(self._rooms(tuple(step.opts.get("bad_at", ("path",))), len(bad))):
            x, y = self._spot(room)
            items.append(self._add("item", x, y, room, label=bad[index], bad=True, color="#ff5a4f"))
        noise = step.opts.get("noise", ())
        for index, (_, room) in enumerate(self._rooms(tuple(step.at) + ("path", "path"), len(noise))):
            x, y = self._spot(room)
            items.append(
                self._add("item", x, y, room, label="*.log", color="#5e6a64", data={"noise": noise[index]})
            )
        self.state["items"] = items

    def _tick_collect(self, step: Step, now: float, dt: float) -> None:
        for item in self.state["items"]:
            if item.gone:
                continue
            taker = self._toucher(item.x, item.y, ITEM_REACH)
            if taker is None:
                continue
            item.gone = True
            if item.bad:
                self._burst(item)
                continue
            if item.data.get("noise"):
                self.arena.emit({"e": "quest_note", "x": round(item.x, 1), "y": round(item.y, 1), "text": item.data["noise"]})
                continue
            self.state["done"] += 1
            self.arena.emit({"e": "quest_item", "id": taker.id, "x": round(item.x, 1), "y": round(item.y, 1), "label": item.label})
            self._each(step, self.state["done"])
        if self.state["done"] >= self.state["need"]:
            for item in self.state["items"]:
                item.gone = True
            self._complete()

    def _burst(self, item: Thing) -> None:
        arena = self.arena
        arena.emit({"e": "quest_burst", "x": round(item.x, 1), "y": round(item.y, 1), "label": item.label})
        for player in self._living():
            if math.hypot(player.x - item.x, player.y - item.y) <= BURST_RADIUS + player.radius:
                arena.damage(
                    target=player, amount=BURST_DAMAGE, source=None, kind="virus",
                    hit_x=player.x, hit_y=player.y,
                )

    # console: a short repair right next to the machine
    def _begin_console(self, step: Step) -> None:
        device = self.device
        task = QUEST_TASKS[str(step.opts["task"])]
        self.state["terminal"] = self.arena._add_terminal(
            device.x, device.y + CONSOLE_OFFSET, task, "quest"
        )

    def _tick_console(self, step: Step, now: float, dt: float) -> None:
        return

    def console_done(self, terminal: Any, by_pgt: bool = False) -> None:
        if self.state.get("terminal") is not terminal:
            return
        if by_pgt:
            self.debts.append(self.arena.now + DEBT_DELAY)
            self._say(PGT_ACCEPTED, urgent=True)
        if self.step.kind == "payload":
            self.state["terminal"] = None
            self.state["mode"] = "roll"
            return
        self._complete()

    # defend: keep the machine alive while it works
    def _begin_defend(self, step: Step) -> None:
        arena = self.arena
        device = self.device
        device.max_hp = device.hp = float(step.opts["hp"]) * self.scale
        device.targetable = True
        device.down_until = 0.0
        arena.lock("defend", self.quest_room.doors)
        arena.gather(self.quest_room)
        self.state.update(
            time=float(step.opts["time"]),
            elapsed=0.0,
            next_wave=arena.now + 1.5,
            spawned=[],
        )

    def _tick_defend(self, step: Step, now: float, dt: float) -> None:
        arena = self.arena
        device = self.device
        if device.down_until > now:
            return
        if device.hp <= 0:
            device.hp = device.max_hp * 0.6
            arena.emit({"e": "unit_up", "id": device.id, "x": round(device.x, 1), "y": round(device.y, 1)})
        if self._living():
            self.state["elapsed"] += dt
        if now >= self.state["next_wave"]:
            self.state["next_wave"] = now + float(step.opts["every"]) * arena.difficulty.tempo
            self.state["spawned"] += self._pack(self.quest_room, float(step.opts["share"]), focus=device)
        if self.state["elapsed"] >= self.state["time"]:
            device.targetable = False
            device.hp = device.max_hp
            for monster in self.state["spawned"]:
                if monster.id in arena.monsters:
                    arena.remove_monster(monster)
            arena.unlock("defend")
            x, y = device.x, device.y + 60
            self._loot(x, y, 0)
            self._complete()

    # escort: someone lost who follows the nearest mage home
    def _begin_escort(self, step: Step) -> None:
        tag = step.at[0] if step.at else "device"
        if tag == "device":
            x, y = self.device.x, self.device.y + 60
        else:
            x, y = self.tagged[tag].center
        npc = self._add_unit(
            str(step.opts["npc"]), str(step.opts["name"]), x, y,
            float(step.opts["hp"]) * self.scale, 16.0,
        )
        self.state.update(npc=npc, found=False, dest=self._target(str(step.opts["to"])))

    def _tick_escort(self, step: Step, now: float, dt: float) -> None:
        arena = self.arena
        npc: QuestUnit = self.state["npc"]
        living = self._living()
        if not self.state["found"]:
            if any(math.hypot(p.x - npc.x, p.y - npc.y) <= NPC_NOTICE for p in living):
                self.state["found"] = True
                npc.targetable = True
                arena.emit({"e": "npc_found", "id": npc.id, "x": round(npc.x, 1), "y": round(npc.y, 1)})
                self._each(step, 1)
            return
        if npc.down_until > now:
            helper = self._toucher(npc.x, npc.y, REVIVE_REACH)
            if helper is None:
                npc.revive_left = max(0.0, npc.revive_left - dt)
                return
            npc.revive_left += dt
            if npc.revive_left >= REVIVE_TIME:
                npc.down_until = 0.0
                npc.revive_left = 0.0
                npc.hp = npc.max_hp * 0.6
                npc.invuln_until = now + 1.5
                arena.emit({"e": "unit_up", "id": npc.id, "x": round(npc.x, 1), "y": round(npc.y, 1)})
            return
        nearest = min(living, key=lambda p: math.hypot(p.x - npc.x, p.y - npc.y), default=None)
        if nearest is not None and math.hypot(nearest.x - npc.x, nearest.y - npc.y) > NPC_GAP:
            angle = arena.walk_angle(npc, nearest)
            speed = NPC_SPEED * (0.85 if npc.sprite == "admin" else 1.0)
            arena.try_move(npc, math.cos(angle) * speed * dt, math.sin(angle) * speed * dt)
        dest = self.state["dest"]
        if math.hypot(npc.x - dest[0], npc.y - dest[1]) <= DEST_REACH:
            npc.targetable = False
            if npc.sprite == "request":
                self.units.pop(npc.id, None)
                arena.emit({"e": "npc_gone", "x": round(npc.x, 1), "y": round(npc.y, 1)})
            self._complete()

    # carry: a packet with a TTL from one room to another
    def _begin_carry(self, step: Step) -> None:
        room = self.tagged.get(step.at[0]) if step.at else None
        room = room or self.arena.dungeon.rooms[0]
        x, y = room.center
        packet = self._add("packet", x, y, room, label=str(step.opts.get("label", "")))
        dest = self._target(str(step.opts.get("to", "device")))
        tiles = self._path_tiles((x, y), dest)
        ttl = (tiles * TILE / MOVE_SPEED * CARRY_PACE + CARRY_SPARE) * (0.7 + 0.3 * self.arena.difficulty.tempo)
        self.state.update(
            packet=packet,
            home=(x, y),
            dest=dest,
            total=ttl,
            ttl=ttl,
            live=False,
            drop_by=0,
            drop_at=-100.0,
            chase_at=0.0,
        )

    def carrier(self) -> int:
        step = self.step
        if step is None or step.kind != "carry":
            return 0
        return self.state["packet"].holder

    def _tick_carry(self, step: Step, now: float, dt: float) -> None:
        arena = self.arena
        state = self.state
        packet: Thing = state["packet"]
        holder = arena.players.get(packet.holder) if packet.holder else None
        if holder is not None and (holder.dead or holder.id in arena.linked):
            self._drop(holder)
            holder = None
        if holder is not None:
            packet.x, packet.y = holder.x, holder.y
        else:
            skip = state["drop_by"] if now - state["drop_at"] < DROP_GRACE else 0
            picker = self._toucher(packet.x, packet.y, ITEM_REACH, skip)
            if picker is not None:
                packet.holder = picker.id
                state["live"] = True
                arena.emit({"e": "packet_take", "id": picker.id, "x": round(packet.x, 1), "y": round(packet.y, 1)})
                holder = picker
        if state["live"]:
            state["ttl"] -= dt
            if state["ttl"] <= 0:
                arena.emit({"e": "quest_burst", "x": round(packet.x, 1), "y": round(packet.y, 1), "label": packet.label})
                packet.holder = 0
                packet.x, packet.y = state["home"]
                state["live"] = False
                state["ttl"] = state["total"]
                self._say(step.fail, urgent=True)
                return
        if holder is None:
            return
        dest = state["dest"]
        if math.hypot(holder.x - dest[0], holder.y - dest[1]) <= DEST_REACH:
            packet.gone = True
            packet.holder = 0
            self._complete()
            return
        if now >= state["chase_at"]:
            state["chase_at"] = now + CARRY_CHASE * arena.difficulty.tempo
            if len(arena.monsters) < 12:
                self._pack(arena.dungeon.rooms[0], 0.3, near=(holder.x, holder.y))

    def _drop(self, player: Player) -> None:
        packet: Thing = self.state["packet"]
        packet.holder = 0
        packet.x, packet.y = player.x, player.y
        self.state["drop_by"] = player.id
        self.state["drop_at"] = self.arena.now
        self.arena.emit({"e": "packet_drop", "id": player.id, "x": round(player.x, 1), "y": round(player.y, 1)})

    # plates: read the code on the wall, step where it would step
    def _begin_plates(self, step: Step) -> None:
        board = self.quest_board
        board.active = True
        self.state["board"] = board

    def _tick_plates(self, step: Step, now: float, dt: float) -> None:
        if self.state["board"].solved:
            self._complete()

    def _make_board(
        self, room: Room, count: int, template: str, fail: tuple[Line, ...]
    ) -> PlateBoard:
        code, sequence = make_code(self.rng, self.chapter, count, template)
        numbers = list(range(1, count + 1))
        self.rng.shuffle(numbers)
        radius = min(room.w * TILE * 0.32, room.h * TILE * 0.3 / 0.78)
        plates = [
            self._add("plate", x, y, room, number=number)
            for (x, y), number in zip(self._ring(room, count, radius), numbers)
        ]
        cx, cy = room.center
        board = PlateBoard(
            room=room,
            plates=plates,
            sequence=sequence,
            code=code,
            sign=(cx, room.y * TILE + 34),
            hub=(cx, cy),
            radius=radius,
            fail_lines=fail,
        )
        self.boards.append(board)
        return board

    def _update_boards(self, now: float) -> None:
        living = self._living()
        for board in self.boards:
            if not board.active or board.solved:
                continue
            for plate in board.plates:
                presser = next(
                    (p for p in living if math.hypot(p.x - plate.x, p.y - plate.y) <= PLATE_REACH),
                    None,
                )
                was = plate.data.get("pressed", False)
                plate.data["pressed"] = presser is not None
                if presser is None or was or plate.on:
                    continue
                if plate.number == board.sequence[board.position]:
                    plate.on = True
                    board.position += 1
                    self.arena.emit({"e": "plate_on", "x": round(plate.x, 1), "y": round(plate.y, 1), "n": plate.number})
                    if board.position >= len(board.sequence):
                        board.solved = True
                        if board.on_solved is not None:
                            board.on_solved()
                    continue
                for other in board.plates:
                    other.on = False
                board.position = 0
                self.arena.emit({"e": "plate_fail", "x": round(plate.x, 1), "y": round(plate.y, 1)})
                self.arena.damage(
                    target=presser, amount=ZAP_DAMAGE, source=None, kind="zap",
                    hit_x=presser.x, hit_y=presser.y,
                )
                if now - board.told_at > 8.0:
                    board.told_at = now
                    self._say(board.fail_lines or PUZZLE_FAIL)

    # --------------------------------------------------------------- features
    def _setup_features(self) -> None:
        stage = self.arena.stage
        for room in self.arena.dungeon.sides:
            kind = room.kind
            feature: dict[str, Any] = {"kind": kind, "room": room}
            cx, cy = room.center
            if kind == "cache":
                mimic = not self.first and self.rng.random() < MIMIC_CHANCE
                feature["chest"] = self._add("chest", cx, cy, room, data={"use": "открыть тайник", "mimic": mimic})
            elif kind == "trap":
                feature.update(next_at=0.0, phase=0, told=False)
                if not room.tag:
                    x, y = self._far_end(room)
                    feature["chest"] = self._add("chest", x, y, room, data={"use": "открыть тайник"})
            elif kind == "rest":
                feature["beacon"] = self._add("beacon", cx, cy, room)
                notes = REST_NOTES[min(self.chapter, len(REST_NOTES) - 1)]
                feature["note"] = notes[stage.number % len(notes)]
            elif kind == "deal":
                deal = self.rng.choice(DEALS)
                feature["deal"] = deal
                feature["altar"] = self._add(
                    "altar", cx, cy, room, label=deal.title,
                    data={"use": f"принять «{deal.title}» от PGT: {deal.about}"},
                )
            elif kind == "trial":
                feature["banner"] = self._add("trial", cx, cy, room)
                feature["state"] = "idle"
            elif kind == "puzzle":
                board = self._make_board(room, PLATE_COUNT, "", ())
                board.active = True
                feature["board"] = board
                board.on_solved = lambda room=room: self._puzzle_solved(room)
            else:
                continue
            self.features.append(feature)

    def _puzzle_solved(self, room: Room) -> None:
        x, y = room.center
        self._loot(x, y, 12 + 4 * self.chapter)
        self._say(PUZZLE_WIN)

    def _update_features(self, now: float) -> None:
        for feature in self.features:
            kind = feature["kind"]
            if kind == "trap":
                self._update_trap(feature, now)
            elif kind == "rest":
                self._update_rest(feature)
            elif kind == "trial":
                self._update_trial(feature, now)

    def _trap_armed(self, feature: dict[str, Any]) -> bool:
        room: Room = feature["room"]
        chest = feature.get("chest")
        if chest is not None:
            return not chest.on
        return any(
            not thing.gone and thing.room == room.index and thing.kind == "item"
            for thing in self.things.values()
        )

    def _update_trap(self, feature: dict[str, Any], now: float) -> None:
        room: Room = feature["room"]
        if now < feature["next_at"] or not self._inside(room) or not self._trap_armed(feature):
            return
        if not feature["told"]:
            feature["told"] = True
            self._say(TRAP_LINES, urgent=True)
        feature["next_at"] = now + TRAP_EVERY
        feature["phase"] ^= 1
        ux, uy = self._door_side(room)
        left, top = room.x * TILE, room.y * TILE
        right, bottom = (room.x + room.w) * TILE, (room.y + room.h) * TILE
        across = abs(ux) >= abs(uy)
        start = TRAP_SPACING * (1.5 + feature["phase"] * 0.5)
        if across:
            span = right - left
            for offset in _steps(start, span - TRAP_SPACING, TRAP_SPACING):
                x = left + offset
                self.arena.trap_beam(x, top + 8, x, bottom - 8, TRAP_WIDTH, TRAP_FUSE, TRAP_DAMAGE)
        else:
            span = bottom - top
            for offset in _steps(start, span - TRAP_SPACING * 0.8, TRAP_SPACING):
                y = top + offset
                self.arena.trap_beam(left + 8, y, right - 8, y, TRAP_WIDTH, TRAP_FUSE, TRAP_DAMAGE)

    def _update_rest(self, feature: dict[str, Any]) -> None:
        beacon: Thing = feature["beacon"]
        room: Room = feature["room"]
        if beacon.on or not self._inside(room, 1.0):
            return
        beacon.on = True
        arena = self.arena
        living = self._living()
        for player in arena.players.values():
            if player.dead and living:
                arena._revive(player, living[0])
            if not player.dead:
                player.hp = player.max_hp
                player.mana = player.max_mana
        arena.emit({"e": "rest", "x": round(beacon.x, 1), "y": round(beacon.y, 1)})
        self._say(((NOTE, feature["note"]),), urgent=True)

    def _update_trial(self, feature: dict[str, Any], now: float) -> None:
        arena = self.arena
        room: Room = feature["room"]
        state = feature["state"]
        if state == "idle":
            if arena.active_room is not None or not self._inside(room, 1.6):
                return
            known = [rune for rune in ATTACK_RUNES if rune in arena.known_runes]
            rune = self.rng.choice(known) if known else "fireball"
            feature.update(state="on", rune=rune, wave=1, end_at=now + TRIAL_TIME + 4 * (arena.party_size - 1))
            arena.lock("trial", room.doors)
            arena.gather(room)
            self.trial = {"room": room.index, "rune": rune}
            feature["banner"].label = rune
            self._say(tuple((who, text.format(rune=rune)) for who, text in TRIAL_START), urgent=True)
            self._pack(room, 0.8, tag="trial")
            return
        if state != "on":
            return
        alive = [monster for monster in arena.monsters.values() if monster.quest == "trial"]
        if now >= feature["end_at"]:
            for monster in alive:
                arena.remove_monster(monster)
            self._end_trial(feature, won=False)
            return
        if alive:
            return
        if feature["wave"] < 2:
            feature["wave"] = 2
            self._pack(room, 0.8, tag="trial")
            return
        self._end_trial(feature, won=True)

    def _end_trial(self, feature: dict[str, Any], won: bool) -> None:
        room: Room = feature["room"]
        feature["state"] = "won" if won else "lost"
        feature["banner"].on = True
        self.trial = None
        self.arena.unlock("trial")
        if won:
            x, y = room.center
            self._loot(x, y, 16 + 5 * self.chapter)
            self._say(TRIAL_WIN)
        else:
            self._say(TRIAL_LOST)

    # ----------------------------------------------------------- arena hooks
    def update(self, now: float, dt: float) -> None:
        step = self.step
        if step is not None:
            getattr(self, f"_tick_{step.kind}")(step, now, dt)
        self._update_boards(now)
        self._update_features(now)
        self._update_deal(now)
        self._update_debts(now)

    def _update_deal(self, now: float) -> None:
        if self.deal is None or now < self.deal_bug_at:
            return
        self.deal_bug_at = now + self.deal.every
        living = self._living()
        if not living:
            return
        self.arena.curse(self.rng.choice(living), self.deal.curse)
        if not self.deal_told:
            self.deal_told = True
            self._say(DEAL_BUG, urgent=True)

    def _update_debts(self, now: float) -> None:
        due = [at for at in self.debts if at <= now]
        if not due:
            return
        self.debts = [at for at in self.debts if at > now]
        living = self._living()
        if not living:
            return
        victim = self.rng.choice(living)
        self._pack(self.arena.dungeon.rooms[0], 0.7, near=(victim.x, victim.y))
        self._say(PGT_DEBT, urgent=True)

    def needs_flow(self) -> bool:
        step = self.step
        return step is not None and step.kind == "escort" and self.state.get("found", False)

    def targets(self) -> list[QuestUnit]:
        now = self.arena.now
        return [unit for unit in self.units.values() if unit.targetable and unit.down_until <= now]

    def unit(self, unit_id: int) -> QuestUnit | None:
        unit = self.units.get(unit_id)
        if unit is None or not unit.targetable or unit.down_until > self.arena.now:
            return None
        return unit

    def adopt(self, monster: Monster) -> None:
        """Some of the bugs that turn up while someone is being escorted go for them."""

        step = self.step
        if step is None or step.kind != "escort" or not self.state.get("found"):
            return
        npc = self.state["npc"]
        room = self.arena.dungeon.room_at(npc.x, npc.y)
        if room is not None and room is self.arena.active_room and self.rng.random() < ESCORT_FOCUS:
            monster.focus = npc.id

    def unit_down(self, unit: QuestUnit) -> None:
        arena = self.arena
        if unit.down_until > arena.now:
            return
        unit.hp = 0.0
        unit.invuln_until = arena.now + DEVICE_REBOOT
        step = self.step
        if step is not None and step.kind == "compose" and unit.status:
            unit.invuln_until = arena.now + 1.0
            self._container_down(step, unit)
            for monster in arena.monsters.values():
                if monster.focus == unit.id:
                    monster.focus = 0
            return
        if unit is self.device:
            unit.down_until = arena.now + DEVICE_REBOOT
            if step is not None and step.kind == "defend":
                self.state["elapsed"] = max(0.0, self.state["elapsed"] - self.state["time"] * DEFEND_SETBACK)
        else:
            unit.down_until = math.inf
            unit.revive_left = 0.0
        arena.emit({"e": "unit_down", "id": unit.id, "x": round(unit.x, 1), "y": round(unit.y, 1)})
        if step is not None:
            self._say(step.fail, urgent=True)
        for monster in arena.monsters.values():
            if monster.focus == unit.id:
                monster.focus = 0

    def monster_died(self, monster: Monster) -> None:
        if monster.quest == "mimic":
            self._loot(monster.x, monster.y, 8 + 3 * self.chapter)
            return
        step = self.step
        if step is None:
            return
        died = getattr(self, f"_died_{step.kind}", None)
        if died is not None:
            died(monster)
            return
        if step.kind != "hunt" or monster.quest != self.state.get("tag"):
            return
        if monster.generation == 0:
            self.state["done"] += 1
            self.arena.emit({"e": "quest_catch", "x": round(monster.x, 1), "y": round(monster.y, 1)})
            self._each(step, self.state["done"])

    def sealed(self, name: str, player: Player | None) -> bool:
        trial = self.trial
        if trial is None or player is None or name not in ATTACK_RUNES or name == trial["rune"]:
            return False
        room = self.arena.dungeon.rooms[trial["room"]]
        return room.holds(player.x, player.y, 0.0)

    def interact(self, player: Player) -> dict[str, Any]:
        if self.carrier() == player.id:
            self._drop(player)
            return {"ok": True}
        best: Thing | None = None
        best_distance = USE_REACH
        for thing in self.things.values():
            if thing.gone or not self._usable(thing):
                continue
            distance = math.hypot(thing.x - player.x, thing.y - player.y)
            if distance <= best_distance:
                best, best_distance = thing, distance
        if best is None:
            return {"ok": False, "error": "Рядом нечего открыть."}
        folk = self.arena.folk
        if folk is not None and folk.intercept(best, player):
            return {"ok": True}
        if "owner" in best.data:
            folk.use(best, player)
        elif best.kind == "chest":
            self._open_chest(best)
        elif best.kind == "altar":
            self._accept_deal(best)
        elif self.arena.life is not None:
            if best.kind == "npc":
                self.arena.life.use(best, player)
            elif best.kind == "find":
                self.arena.life.take_find(best)
            elif best.kind == "relic":
                self.arena.life.take_relic(best)
        return {"ok": True}

    @staticmethod
    def _usable(thing: Thing) -> bool:
        """What a side errand offers counts even on someone who has run out of their own."""

        if thing.data.get("view", {}).get("use"):
            return True
        return bool(thing.data.get("use")) and not thing.on

    def _open_chest(self, chest: Thing) -> None:
        chest.on = True
        if chest.data.get("mimic"):
            chest.gone = True
            monster = self.arena.spawn_monster("phish", chest.x, chest.y)
            if monster is not None:
                monster.quest = "mimic"
                monster.spawned_at = self.arena.now + 0.2
            self._say(MIMIC_LINES, urgent=True)
            return
        self._loot(chest.x, chest.y, 8 + 3 * self.chapter)
        self._say(CACHE_LINES)
        if chest.data.get("finds") and self.arena.life is not None:
            room = self.arena.dungeon.rooms[chest.room]
            self.arena.life.offer_finds(room, (chest.x, chest.y))

    def _accept_deal(self, altar: Thing) -> None:
        feature = next(f for f in self.features if f.get("altar") is altar)
        deal: Deal = feature["deal"]
        altar.on = True
        self.deal = deal
        self.deal_bug_at = self.arena.now + deal.every
        for player in self._living():
            if deal.key == "overclock":
                self.power = 1.4
            elif deal.key == "freemana":
                player.mana_regen *= 2.0
            elif deal.key == "bigheap":
                player.max_hp *= 1.35
                player.hp = player.max_hp
        self.arena.emit({"e": "deal", "x": round(altar.x, 1), "y": round(altar.y, 1), "title": deal.title})
        self._say(DEAL_ACCEPT, urgent=True)

    # --------------------------------------------------------------- reports
    def _text(self) -> str:
        step = self.step
        if step is None:
            return "Проблема решена: дверь к терминалу открыта" if self.quest else ""
        state = self.state
        values = {
            "done": state.get("done", 0),
            "need": state.get("need", step.count),
            "left": state.get("left", step.count),
            "time": f"{max(0, math.ceil(state.get('time', 0) - state.get('elapsed', 0)))} с",
            "ttl": f"{max(0, math.ceil(state.get('ttl', 0)))} с" if state.get("live") else "ждёт",
            **state.get("fmt", {}),
        }
        return step.text.format(**values)

    def _report(self, prefix: str) -> Any:
        step = self.step
        report = getattr(self, f"{prefix}_{step.kind}", None) if step is not None else None
        return report() if report is not None else None

    def _bar_defend(self) -> dict[str, Any]:
        state = self.state
        value = state["elapsed"] / state["time"]
        tables = self.step.opts.get("tables", ())
        table = tables[min(len(tables) - 1, int(value * len(tables)))] if tables else ""
        label = f"{table}: {round(value * 100)}%" if table else f"{round(value * 100)}%"
        return {"value": round(value, 3), "label": label, "warn": self.device.down_until > self.arena.now}

    def _bar_carry(self) -> dict[str, Any] | None:
        state = self.state
        if not state["live"]:
            return None
        return {
            "value": round(state["ttl"] / state["total"], 3),
            "label": f"TTL {math.ceil(state['ttl'])} с",
            "warn": state["ttl"] < 6,
        }

    def _marks_collect(self) -> list[tuple[float, float, int]]:
        return [
            (t.x, t.y, t.room) for t in self.state["items"]
            if not t.gone and not t.bad and not t.data.get("noise")
        ]

    def _marks_carry(self) -> list[tuple[float, float, int]]:
        state = self.state
        packet = state["packet"]
        if packet.holder:
            room = self.arena.dungeon.room_at(*state["dest"])
            return [(*state["dest"], room.index if room else 0)]
        return [(packet.x, packet.y, packet.room)]

    def _marks_escort(self) -> list[tuple[float, float, int]]:
        state = self.state
        npc = state["npc"]
        room = self.arena.dungeon.room_at(npc.x, npc.y)
        here = room.index if room else 0
        if state["found"] and npc.down_until <= self.arena.now:
            dest_room = self.arena.dungeon.room_at(*state["dest"])
            return [(*state["dest"], dest_room.index if dest_room else here)]
        return [(npc.x, npc.y, here)]

    def _marks_defend(self) -> list[tuple[float, float, int]]:
        return self._mark_device()

    def _marks(self) -> list[list[float]]:
        points = self._report("_marks") or []
        revealed = self.arena.revealed
        return [[round(x, 1), round(y, 1)] for x, y, room in points if room in revealed]

    def signs(self) -> list[dict[str, Any]]:
        return [
            {"room": board.room.index, "x": round(board.sign[0], 1), "y": round(board.sign[1], 1), "code": board.code}
            for board in self.boards
        ]

    def describe(self) -> dict[str, Any] | None:
        quest = self.quest
        if quest is None:
            return None
        return {
            **quest.describe(),
            "intro": [list(line) for line in (*quest.intro, *quest.steps[0].say)],
        }

    def snapshot(self) -> dict[str, Any]:
        units = []
        for unit in self.units.values():
            entry = {
                "id": unit.id,
                "sprite": unit.sprite,
                "label": unit.label,
                "x": round(unit.x, 1),
                "y": round(unit.y, 1),
                "hp": round(unit.hp, 1),
                "max_hp": round(unit.max_hp, 1),
            }
            if unit.targetable:
                entry["hit"] = True
            if unit.status:
                entry["status"] = unit.status
            if unit.charge:
                entry["charge"] = round(min(1.0, unit.charge), 2)
            if unit.down_until > self.arena.now:
                entry["down"] = True
                if unit.revive_left:
                    entry["revive"] = round(unit.revive_left / REVIVE_TIME, 2)
            units.append(entry)
        state = {
            "step": self.index,
            "steps": len(self.quest.steps) if self.quest else 0,
            "done": self.done,
            "text": self._text(),
            "bar": self._report("_bar"),
            "things": [thing.view() for thing in self.things.values() if not thing.gone],
            "units": units,
            "marks": self._marks(),
            "trial": dict(self.trial) if self.trial else None,
            "card": self.state.get("card"),
        }
        state.update(self._report("_view") or {})
        return state

    def _aim_hunt(self, player: Player) -> tuple[float, float] | None:
        alive = self._hunted()
        if alive:
            target = min(alive, key=lambda m: math.hypot(m.x - player.x, m.y - player.y))
            return target.x, target.y
        if self.state["pending"]:
            return self.state["pending"][0].center
        return None

    def _aim_collect(self, player: Player) -> tuple[float, float] | None:
        left = [
            t for t in self.state["items"]
            if not t.gone and not t.bad and not t.data.get("noise")
        ]
        if not left:
            return None
        target = min(left, key=lambda t: math.hypot(t.x - player.x, t.y - player.y))
        return target.x, target.y

    def _aim_console(self, player: Player) -> tuple[float, float]:
        terminal = self.state["terminal"]
        return terminal.x, terminal.y

    def _aim_defend(self, player: Player) -> tuple[float, float]:
        return self.device.x, self.device.y + 40

    def _aim_escort(self, player: Player) -> tuple[float, float]:
        npc = self.state["npc"]
        if not self.state["found"] or npc.down_until > self.arena.now:
            return npc.x, npc.y
        return self.state["dest"]

    def _aim_carry(self, player: Player) -> tuple[float, float]:
        packet = self.state["packet"]
        if packet.holder == player.id:
            return self.state["dest"]
        return packet.x, packet.y

    def _aim_plates(self, player: Player) -> tuple[float, float] | None:
        board = self.state["board"]
        if board.solved:
            return None
        if math.hypot(player.x - board.hub[0], player.y - board.hub[1]) > board.radius + 70:
            return board.hub
        target = next(p for p in board.plates if p.number == board.sequence[board.position])
        return target.x, target.y

    def objective(self, player: Player) -> tuple[float, float] | None:
        """Where this mage should be for the quest to move on. Used by the test bot."""

        step = self.step
        if step is None:
            return None
        return getattr(self, f"_aim_{step.kind}")(player)

    def bot_shot(self, player: Player) -> tuple[Any, str | None] | None:
        """What the test bot should shoot, when "the nearest enemy" would be wrong."""

        step = self.step
        if step is None:
            return None
        if step.kind == "racks":
            return self.bot_racks(player)
        if step.kind == "inbox":
            return self.bot_inbox(player)
        return None


def _steps(start: float, stop: float, step: float) -> list[float]:
    values = []
    value = start
    while value <= stop:
        values.append(value)
        value += step
    return values
