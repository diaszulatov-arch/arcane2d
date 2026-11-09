"""The second half of the bestiary: a mini-boss and two bugs of its own for every stage.

Each is a joke about what it is, with one rule to learn: a deadlock only dies in pairs,
hype feeds on attention, a traceback is only open at its last call.  Their numbers and
their thinking are here; ``StoryArena`` only asks the small questions at the bottom of
this file: may this hit land, does this one get back up, what is left on the floor.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from .boss_moves import stagger
from .campaign import ADA, STAGES
from .dungeon import PIT, TILE
from .game import Player
from .monsters import (
    ATTACKS,
    SPECIES,
    THINKERS,
    Attack,
    Monster,
    Species,
    _advance,
    _angle_to,
    _bite,
    _distance,
    _fan,
    _rest,
    _rest_special,
    _ring,
    _set_phase,
    _species,
    _speed,
    _step,
    charger,
    flee,
    melee,
    shooter,
    swarm,
)

if TYPE_CHECKING:
    from .story import StoryArena

NAN_KEY = "nan"
COIN = "coin"
FOREVER = math.inf
FIELD_LIMIT = 90
MONSTER_IDS = 100_000

# Mini-bosses that come to help the boss of their chapter, now and then.
ESCORT_HP = 0.6
ESCORT_FIRST = (16.0, 26.0)
ESCORT_EVERY = (22.0, 34.0)
ESCORT_WAIT = 6.0
ESCORT_LIMIT = 2
ESCORT_CHANCE = 0.55

COUNTER_RATE = 0.86
COUNTER_FASTEST = 0.6
WIP_RADIUS = 66.0
WIP_TIME = 9.0
WIP_EVERY = 2.2
DEADLOCK_WAKE = 4.0
DEADLOCK_BACK = 0.6
NECRO_EVERY = 5.0
RAISED_SHARE = 0.5
FALLEN_KEPT = 6
STRING_LENGTH = 460.0
STRING_WIDTH = 34.0
STRING_TIME = 2.4
STRING_FUSE = 0.6
STRING_DAMAGE = 8.0
AUTOPLAY_REACH = 230.0
AUTOPLAY_WAVE = 240.0
SHORTS_REACH = 400.0
SHORTS_PULL = 92.0
STUFFY_REACH = 270.0
FIRST_HURRY = 5.0
BUBBLE_RADIUS = 190.0
READMORE_GROWTH = 4.5
READMORE_SIZE = 1.6
WHILE_RADIUS = 170.0
WHILE_GROW = 0.09
WHILE_MOST = 2.6
WHILE_DRIFT = 36.0
WHILE_STUN = 2.2
ZIP_RING = 10
NOEXT_BLAST = 130.0
DELETED_AFTER = 0.55
CONTAINER_SHUT = 3.6
CONTAINER_OPEN = 1.7
CONFLICT_SWAP = 2.0
LAG_RUN = 1.1
LAG_REST = 0.5
DANGLING_WIDTH = 30.0
DANGLING_FUSE = 1.0
DANGLING_LENGTH = 620.0
PUDDLE_RADIUS = 72.0
PUDDLE_TIME = 14.0
PUDDLE_EVERY = 3.2
PUDDLE_SHOCK = 26.0
PUDDLE_SELF = 8.0
SHOCK_KINDS = frozenset({"chain", "lightning", "spark"})
WIRE_EVERY = 0.6
WIRE_TIME = 7.0
WIRE_WIDTH = 30.0
ZOMBIE_WAKE = 4.0
ZOMBIE_DOWN = 0.14
ZOMBIE_UP = 0.6
FORK_EVERY = 4.0
FORK_LIMIT = 10
ALERT_REACH = 430.0
SURGE_RADIUS = 125.0
OFF_BY = 112.0
OFF_RADIUS = 78.0
REVERSE_FAR = 320.0
REVERSE_NEAR = 190.0
REVERSE_RUSH = 1.7
WARNING_STEP = 10.0
WARNING_RING = 8
FLAKY_FLIP = (0.7, 1.5)
REFLECTION_REST = 0.35
COIN_EVERY = 3.0
COIN_TIME = 11.0
COIN_LIMIT = 8
COIN_DRAIN = 30.0
VIBE_BOSS_SHARE = 0.012
VIBE_SHARE = 0.08
VIBE_REACH = 420.0

MARQUEE_TEXT = "ДОБРОПОЖАЛОВАТЬ"
MARQUEE_GAP = 31.0
HOLYWAR_REACH = 300.0
HOLYWAR_RIVALRY = 4.0
HOLYWAR_ALONE = 0.6
EOF_SPEED = 26.0
EOF_BACK = 0.55
EOF_MARGIN = 260.0
EOF_PUSH = 150.0
EOF_DAMAGE = 8.0
HYPE_GAIN = 0.09
HYPE_ARMOR = 0.6
HYPE_GROW = 0.5
HYPE_PACE = 0.7
HYPE_COOL = 3.0
HYPE_FLAT = 4.0
HYPE_FLAT_BONUS = 1.34
SPINNER_LOAD = 15.0
SPINNER_TURN = 1.9
SPINNER_ARC = 1.15
SPINNER_REACH = 235.0
SPINNER_DAMAGE = 11.0
SPINNER_STUCK = 3.6
BELL_RATE = 3.2
BELL_MOST = 99.0
BELL_READ = 9.0
BELL_BASE = 120.0
BELL_PER = 4.2
BELL_KEPT = 0.25
QUOTA_BOXES = 12
QUOTA_EVERY = 4.0
BOX_FUSE = 0.9
BOX_REACH = 38.0
PAIRED = frozenset({"vim", "ours"})
PAIR_APART = 420.0
PAIR_OFFSET = 0.28
MERGE_REACH = 78.0
MERGE_KNOCK = 18.0
MERGE_SIZE = 1.3
DEVNULL_FEED = 7
DEVNULL_PULL = 340.0
DEVNULL_TURN = 5.0
DEVNULL_OPEN = 3.6
COLD_SPEED = 140.0
COLD_TIME = 3.2
COLD_BAND = 28.0
COLD_DAMAGE = 11.0
ICE_RADIUS = 86.0
ICE_TIME = 8.0
UPS_BATTERIES = 2
UPS_BACK = 0.35
UPS_RING = 16
DEBUG_LINES = 6
DEBUG_EVERY = 7.5
DEBUG_LINE_TIME = 7.0
DEBUG_SHARE = 0.14
DEBUG_OPEN = 3.6
DEBUG_LEVELS = ("DEBUG", "INFO", "TRACE")
TAB_HEAL = 0.03
TAB_STACK = 0.1
TAB_BONUS = 0.5
TAB_WIDTH = 96.0
TAB_RUNES = frozenset({"fire", "frost", "spark", "lightning", "chain", "nova", "beam", "meteor", "emp", "siphon"})
WINDOW_MOST = 310.0
WINDOW_LEAST = 135.0
WINDOW_SHRINK = 8.0
WINDOW_SPEED = 62.0
WINDOW_WANDER = 5.0
WINDOW_DRAIN = 6.0


# ------------------------------------------------------------------- the floor
@dataclass(slots=True)
class Field:
    """A stretch of floor somebody left behind: a circle, a line, a ring or a box."""

    id: int
    kind: str
    x: float
    y: float
    radius: float = 0.0
    x2: float | None = None
    y2: float | None = None
    until: float = FOREVER
    arm_at: float = 0.0
    slow: bool = False
    damage: float = 0.0
    every: float = 0.5
    owner: int = 0
    tied: bool = False
    rect: bool = False
    ring: bool = False
    grow: float = 0.0
    label: str = ""
    bitten: dict[int, float] = field(default_factory=dict)

    def covers(self, x: float, y: float, margin: float = 0.0) -> bool:
        if self.rect:
            return self.x - margin <= x <= self.x2 + margin and self.y - margin <= y <= self.y2 + margin
        if self.ring:
            return abs(math.hypot(x - self.x, y - self.y) - self.radius) <= COLD_BAND + margin
        if self.x2 is None:
            return math.hypot(x - self.x, y - self.y) <= self.radius + margin
        dx, dy = self.x2 - self.x, self.y2 - self.y
        length = dx * dx + dy * dy
        if length <= 1e-6:
            return False
        at = max(0.0, min(1.0, ((x - self.x) * dx + (y - self.y) * dy) / length))
        return math.hypot(x - (self.x + dx * at), y - (self.y + dy * at)) <= self.radius / 2 + margin

    def view(self, now: float) -> dict[str, Any]:
        entry: dict[str, Any] = {"id": self.id, "k": self.kind, "x": round(self.x, 1), "y": round(self.y, 1)}
        if self.radius:
            entry["r"] = round(self.radius, 1)
        if self.x2 is not None:
            entry["x2"] = round(self.x2, 1)
            entry["y2"] = round(self.y2, 1)
        if self.until != FOREVER:
            entry["ttl"] = round(max(0.0, self.until - now), 1)
        if self.arm_at > now:
            entry["arming"] = True
        if self.label:
            entry["label"] = self.label
        return entry


def add_field(world: "StoryArena", kind: str, x: float, y: float, **values: Any) -> Field:
    if len(world.fields) >= FIELD_LIMIT:
        for index, old in enumerate(world.fields):
            if not old.tied and old.until != FOREVER:
                del world.fields[index]
                break
    made = Field(world._effect_id(), kind, x, y, **values)
    world.fields.append(made)
    return made


def _update_fields(world: "StoryArena", now: float, dt: float) -> None:
    kept: list[Field] = []
    mages = world.hunted()
    for patch in world.fields:
        if now >= patch.until or (patch.tied and patch.owner not in world.monsters):
            continue
        kept.append(patch)
        patch.radius += patch.grow * dt
        if now < patch.arm_at or not (patch.slow or patch.damage):
            continue
        for mage in mages:
            if not patch.covers(mage.x, mage.y, mage.radius * 0.5) or mage.invuln_until > now:
                continue
            if patch.slow:
                mage.slow_until = max(mage.slow_until, now + 0.35)
            if patch.damage and now >= patch.bitten.get(mage.id, 0.0):
                patch.bitten[mage.id] = now + patch.every
                world.damage(
                    target=mage, amount=patch.damage, source=world.monsters.get(patch.owner),
                    kind="hazard", hit_x=mage.x, hit_y=mage.y,
                )
    world.fields = kept


# ---------------------------------------------------------------- small helpers
def _mark(monster: Monster, **values: Any) -> None:
    if monster.marks is None:
        monster.marks = {}
    monster.marks.update(values)


def _label(monster: Monster, text: str) -> None:
    monster.text = text
    _mark(monster, label=text)


def _kin(world: "StoryArena", monster: Monster, key: str, x: float, y: float) -> Monster | None:
    """Part of the same creature: it does not reset the bar and it goes when the fight does."""

    return world.spawn_monster(key, x, y, generation=1, escort=monster.escort)


def _opposite(world: "StoryArena", monster: Monster) -> tuple[float, float]:
    """The far side of the room, for the other half of a pair."""

    left, top, right, bottom = world.room_box()
    x, y = left + right - monster.x, top + bottom - monster.y
    if math.hypot(x - monster.x, y - monster.y) < PAIR_APART:
        side = 1.0 if monster.x <= (left + right) / 2 else -1.0
        x = max(left, min(right, monster.x + side * PAIR_APART))
    return world.dungeon.open_near(x, y, monster.radius)


def mini_spot(world: "StoryArena", room: Any, key: str) -> tuple[float, float]:
    """Where a mini-boss turns up: those in two halves start well off the middle."""

    x, y = room.center
    if key in PAIRED:
        x -= (room.w - 2) * TILE * PAIR_OFFSET
    return world.dungeon.open_near(x, y, SPECIES[key].radius)


def _set_bar(world: "StoryArena", monster: Monster, total: float) -> None:
    if not monster.escort:
        world.boss_max_hp = total


def _nip(world: "StoryArena", monster: Monster, mage: Player, amount: float, every: float) -> None:
    """Damage that keeps on while you stand in it, not once a tick."""

    if monster.memo is None:
        monster.memo = {}
    if world.now < monster.memo.get(mage.id, 0.0):
        return
    monster.memo[mage.id] = world.now + every
    world.damage(target=mage, amount=amount, source=monster, kind="hazard", hit_x=mage.x, hit_y=mage.y)


def _grow_chain(world: "StoryArena", monster: Monster, key: str, glyphs: tuple[str, ...]) -> int:
    """Lay a chain out behind its head, the first time the head thinks."""

    tail = monster
    length = 1
    for glyph in glyphs:
        link = _kin(world, monster, key, tail.x, tail.y)
        if link is None:
            break
        link.link = tail.id
        if glyph:
            link.text = glyph
            _mark(link, glyph=glyph)
        tail = link
        length += 1
    return length


def _follow(world: "StoryArena", monster: Monster, leader: Monster, gap: float, dt: float) -> None:
    dx, dy = leader.x - monster.x, leader.y - monster.y
    distance = math.hypot(dx, dy)
    monster.heading = math.atan2(dy, dx)
    if distance > gap:
        # Where the head could go, the tail can follow: no need to ask about walls again.
        step = min(distance - gap, max(_speed(monster, world) * 1.4, distance * 6.0) * dt)
        monster.x += dx / distance * step
        monster.y += dy / distance * step


def _pair_up(world: "StoryArena", monster: Monster) -> None:
    for other in world.monsters.values():
        if other is not monster and other.species.key == monster.species.key and not other.link:
            monster.link = other.id
            other.link = monster.id
            _mark(monster, link=other.id)
            return


def _knock_down(world: "StoryArena", monster: Monster, wake: float) -> None:
    monster.state = "down"
    monster.state_until = world.now + wake
    _mark(monster, down=True)


def _get_up(monster: Monster, share: float) -> None:
    monster.state = "idle"
    monster.hp = max(monster.hp, monster.max_hp * share)
    monster.invuln_until = 0.0
    _mark(monster, down=False)


# ---------------------------------------------------------- ordinary bugs: I
def counter(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    monster.heading = _angle_to(monster, target)
    if world.now >= monster.next_attack and world.sees(monster, target):
        monster.count += 1
        _label(monster, f"{monster.count:05d}")
        world.fire(monster, monster.heading)
        wait = monster.species.interval * COUNTER_RATE ** monster.count
        monster.next_attack = world.now + max(COUNTER_FASTEST, wait)


def construction(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    melee(world, monster, target, dt)
    if world.now >= monster.next_attack:
        monster.next_attack = world.now + WIP_EVERY
        add_field(world, "wip", monster.x, monster.y, radius=WIP_RADIUS, until=world.now + WIP_TIME, slow=True, owner=monster.id)


def deadlock(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    if monster.state == "down":
        if world.now >= monster.state_until:
            _get_up(monster, DEADLOCK_BACK)
        return
    if not monster.link:
        _pair_up(world, monster)
    melee(world, monster, target, dt)


def necroposter(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    shooter(world, monster, target, dt)
    if world.now >= monster.next_special and world.fallen:
        monster.next_special = world.now + NECRO_EVERY
        key, x, y = world.fallen.pop()
        raised = world.spawn_monster(key, x, y, minion=True)
        if raised is not None:
            raised.hp = raised.max_hp * RAISED_SHARE
            raised.leaked = True


def stringer(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    distance = _distance(monster, target)
    monster.heading = _angle_to(monster, target)
    if distance > species.range or not world.sees(monster, target):
        _advance(world, monster, target, dt)
    elif distance < species.range * 0.5:
        _step(monster, world, monster.heading + math.pi, _speed(monster, world), dt)
    if world.now >= monster.next_attack and world.sees(monster, target):
        monster.next_attack = world.now + species.interval
        dx, dy = math.cos(monster.heading), math.sin(monster.heading)
        x2, y2 = world.ray_end(monster.x, monster.y, dx, dy, STRING_LENGTH)
        add_field(
            world, "string", monster.x, monster.y, x2=x2, y2=y2, radius=STRING_WIDTH,
            until=world.now + STRING_TIME, arm_at=world.now + STRING_FUSE,
            damage=STRING_DAMAGE, owner=monster.id,
        )


# --------------------------------------------------------- ordinary bugs: II
def autoplay(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    monster.heading = _angle_to(monster, target)
    _mark(monster, aura=AUTOPLAY_REACH, tone="sound")
    if _distance(monster, target) < AUTOPLAY_REACH and world.now >= monster.next_attack:
        monster.next_attack = world.now + monster.species.interval
        world.place_hazard(
            monster, monster.x, monster.y, radius=AUTOPLAY_WAVE, delay=0.7,
            damage=monster.species.shot_damage, color=monster.species.color, label="ЗВУК",
        )


def shorts(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    melee(world, monster, target, dt)
    _mark(monster, aura=SHORTS_REACH, tone="pull")
    for mage in world.hunted():
        dx, dy = monster.x - mage.x, monster.y - mage.y
        distance = math.hypot(dx, dy)
        if monster.radius < distance < SHORTS_REACH:
            pull = SHORTS_PULL * (0.45 + 0.55 * (1 - distance / SHORTS_REACH)) * dt
            world.try_move(mage, dx / distance * pull, dy / distance * pull)


def dushnila(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    shooter(world, monster, target, dt)
    _mark(monster, aura=STUFFY_REACH, tone="stuffy")
    for mage in world.hunted():
        if math.hypot(mage.x - monster.x, mage.y - monster.y) <= STUFFY_REACH:
            mage.mana = max(0.0, mage.mana - mage.mana_regen * dt)


def firstcomment(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    swarm(world, monster, target, dt)
    if _distance(monster, target) <= monster.radius + target.radius + 6:
        _bite(world, monster, target)
        world.emit({"e": "say", "id": monster.id, "text": "Первый!"})
        for other in world.monsters.values():
            other.hurry_until = world.now + FIRST_HURRY
        world.remove_monster(monster)


def bubble(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    _mark(monster, dome=BUBBLE_RADIUS)
    shooter(world, monster, target, dt)


def whiletrue(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    if not monster.count:
        monster.count = 1
        monster.charge = 1.0
        monster.origin = (monster.x, monster.y)
    monster.charge = min(WHILE_MOST, monster.charge + WHILE_GROW * dt)
    speed = _speed(monster, world) * monster.charge
    monster.orbit += speed / WHILE_RADIUS * dt
    x, y = monster.origin
    angle = math.atan2(target.y - y, target.x - x)
    x += math.cos(angle) * WHILE_DRIFT * dt
    y += math.sin(angle) * WHILE_DRIFT * dt
    monster.origin = (x, y)
    goal_x = x + math.cos(monster.orbit) * WHILE_RADIUS
    goal_y = y + math.sin(monster.orbit) * WHILE_RADIUS
    monster.heading = math.atan2(goal_y - monster.y, goal_x - monster.x)
    _step(monster, world, monster.heading, speed, dt)
    _bite(world, monster, target)


# -------------------------------------------------------- ordinary bugs: III
def deleted(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    shooter(world, monster, target, dt)
    fired = monster.next_attack - monster.species.interval
    solid = monster.state == "aim" or world.now < fired + DELETED_AFTER
    _mark(monster, ghost=not solid)


def container(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    monster.heading = _angle_to(monster, target)
    if world.now < monster.state_until:
        return
    if monster.count:
        monster.count = 0
        monster.state_until = world.now + CONTAINER_SHUT
        _mark(monster, open=False)
        return
    monster.count = 1
    monster.state_until = world.now + CONTAINER_OPEN
    _mark(monster, open=True)
    if world.minion_count() < world.minion_limit():
        world.spawn_near(monster, "bot", 70)


def _conflict_real(world: "StoryArena", monster: Monster) -> bool:
    partner = world.monsters.get(monster.link)
    if partner is None:
        return True
    return (int(world.now / CONFLICT_SWAP) + (monster.id < partner.id)) % 2 == 0


def conflict(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    if not monster.link:
        _pair_up(world, monster)
    real = _conflict_real(world, monster)
    _label(monster, "HEAD" if real else "main")
    _mark(monster, ghost=not real)
    shooter(world, monster, target, dt)


def lag(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    melee(world, monster, target, dt)
    if world.now < monster.state_until:
        return
    if monster.state == "saved":
        monster.x, monster.y = monster.origin
        monster.state = "idle"
        monster.state_until = world.now + LAG_REST
    else:
        monster.origin = (monster.x, monster.y)
        monster.state = "saved"
        monster.state_until = world.now + LAG_RUN


def dangling(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    monster.heading = _angle_to(monster, target)
    if _distance(monster, target) > species.range or not world.sees(monster, target):
        _advance(world, monster, target, dt)
    if world.now >= monster.next_attack and world.sees(monster, target):
        monster.next_attack = world.now + species.interval
        dx, dy = math.cos(monster.heading), math.sin(monster.heading)
        x2, y2 = world.ray_end(monster.x, monster.y, dx, dy, DANGLING_LENGTH)
        world.place_beam_hazard(
            monster, monster.x, monster.y, x2, y2, width=DANGLING_WIDTH,
            delay=DANGLING_FUSE, damage=species.shot_damage, color=species.color,
        )


# --------------------------------------------------------- ordinary bugs: IV
def condensate(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    melee(world, monster, target, dt)
    if world.now >= monster.next_attack:
        monster.next_attack = world.now + PUDDLE_EVERY
        add_field(world, "puddle", monster.x, monster.y, radius=PUDDLE_RADIUS, until=world.now + PUDDLE_TIME, owner=monster.id)


def wire(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    if not monster.count:
        monster.count = 1
        monster.origin = (monster.x, monster.y)
    swarm(world, monster, target, dt)
    if world.now >= monster.next_attack:
        monster.next_attack = world.now + WIRE_EVERY
        x, y = monster.origin
        add_field(
            world, "wire", x, y, x2=monster.x, y2=monster.y, radius=WIRE_WIDTH,
            until=world.now + WIRE_TIME, slow=True, owner=monster.id,
        )
        monster.origin = (monster.x, monster.y)


def zombie(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    if monster.state == "down":
        if world.now >= monster.state_until:
            _get_up(monster, ZOMBIE_UP)
        return
    melee(world, monster, target, dt)


def forkbomb(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    swarm(world, monster, target, dt)
    if world.now < monster.next_special or world.now - monster.last_damage_at < FORK_EVERY:
        return
    monster.next_special = world.now + FORK_EVERY
    alive = sum(other.species.key == "forkbomb" for other in world.monsters.values())
    if alive < FORK_LIMIT and world.minion_count() < world.minion_limit():
        child = world.spawn_near(monster, "forkbomb", 60)
        if child is not None:
            child.leaked = True


def nightalert(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    _mark(monster, aura=ALERT_REACH, tone="alert")
    if len(world.monsters) == 1:
        # With nobody left to wake it stops running, or the room would never end.
        _advance(world, monster, target, dt)
        return
    flee(world, monster, target, dt)
    for other in world.monsters.values():
        if other is not monster and math.hypot(other.x - monster.x, other.y - monster.y) <= ALERT_REACH:
            other.hurry_until = max(other.hurry_until, world.now + 0.4)


def surge(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    before = monster.state
    charger(world, monster, target, dt)
    if before == "dash" and monster.state == "idle":
        world.place_hazard(
            monster, monster.x, monster.y, radius=SURGE_RADIUS, delay=0.3,
            damage=monster.species.shot_damage, color=monster.species.color, label="220 В",
        )


def offbyone(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    monster.heading = _angle_to(monster, target)
    if _distance(monster, target) > species.range or not world.sees(monster, target):
        _advance(world, monster, target, dt)
    if world.now >= monster.next_attack and world.sees(monster, target):
        monster.next_attack = world.now + species.interval
        along_x, along_y = -math.sin(monster.heading) * OFF_BY, math.cos(monster.heading) * OFF_BY
        for side, label in ((-1, "i - 1"), (1, "i + 1")):
            world.place_hazard(
                monster, target.x + along_x * side, target.y + along_y * side, radius=OFF_RADIUS,
                delay=1.0, damage=species.shot_damage, color=species.color, label=label,
            )


def reverse(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    distance = _distance(monster, target)
    monster.heading = _angle_to(monster, target)
    if distance > REVERSE_FAR:
        _step(monster, world, world.route(monster, target), _speed(monster, world) * REVERSE_RUSH, dt)
    elif distance < REVERSE_NEAR:
        _step(monster, world, monster.heading + math.pi, _speed(monster, world) * REVERSE_RUSH, dt)
    if world.now >= monster.next_attack and world.sees(monster, target):
        monster.next_attack = world.now + species.interval
        _fan(world, monster, monster.heading)


# ---------------------------------------------------------- ordinary bugs: V
def warning(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    level = min(2, int((world.now - monster.spawned_at) / WARNING_STEP))
    _label(monster, ("WARNING", "ERROR", "FATAL")[level])
    _mark(monster, tone=("warn", "error", "fatal")[level])
    monster.heading = _angle_to(monster, target)
    _advance(world, monster, target, dt)
    if level == 0 or world.now < monster.next_attack:
        return
    if level == 1:
        monster.next_attack = world.now + species.interval
        if world.sees(monster, target):
            world.fire(monster, monster.heading)
    else:
        monster.next_attack = world.now + species.interval
        _ring(world, monster, WARNING_RING, world.now)


def _is_last_call(world: "StoryArena", monster: Monster) -> bool:
    return not any(other.link == monster.id for other in world.monsters.values())


def traceback_bug(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    if monster.generation == 0 and not monster.count:
        monster.count = 1
        _grow_chain(world, monster, "traceback", ("", "", ""))
    leader = world.monsters.get(monster.link) if monster.link else None
    if leader is not None:
        _follow(world, monster, leader, monster.radius * 2.0, dt)
    else:
        monster.link = 0
        monster.heading = _angle_to(monster, target)
        _advance(world, monster, target, dt)
        if world.now >= monster.next_attack and world.sees(monster, target):
            monster.next_attack = world.now + monster.species.interval
            _fan(world, monster, monster.heading)
    _label(monster, "last" if _is_last_call(world, monster) else "")


def flaky(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    if world.now >= monster.state_until:
        monster.count = 1 - monster.count
        monster.state_until = world.now + world.rng.uniform(*FLAKY_FLIP)
        _label(monster, "failed" if monster.count else "passed")
        _mark(monster, tone="fail" if monster.count else "pass")
    melee(world, monster, target, dt)


def reflection(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    left, top, right, bottom = world.room_box()
    goal_x, goal_y = left + right - target.x, top + bottom - target.y
    distance = math.hypot(goal_x - monster.x, goal_y - monster.y)
    monster.heading = _angle_to(monster, target)
    if distance > 6:
        angle = math.atan2(goal_y - monster.y, goal_x - monster.x)
        _step(monster, world, angle, min(_speed(monster, world), distance / max(dt, 1e-3)), dt)


def prince(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    flee(world, monster, target, dt)
    if world.now >= monster.next_attack:
        monster.next_attack = world.now + COIN_EVERY
        if sum(pickup.kind == COIN for pickup in world.pickups) < COIN_LIMIT:
            x, y = world.dungeon.open_near(monster.x, monster.y, 14.0)
            world._add_pickup(COIN, x, y, world.now + COIN_TIME)


def captcha(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    _label(monster, "Я не робот")
    melee(world, monster, target, dt)


def vibecoder(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    monster.heading = _angle_to(monster, target)
    if _distance(monster, target) > species.range:
        _advance(world, monster, target, dt)
    elif _distance(monster, target) < species.range * 0.5:
        _step(monster, world, monster.heading + math.pi, _speed(monster, world), dt)
    if world.now < monster.next_attack:
        return
    monster.next_attack = world.now + species.interval
    boss = next(
        (other for other in world.monsters.values() if other.species.key == world.stage.chapter.boss),
        None,
    )
    patient = boss or world.most_hurt_ally(monster, VIBE_REACH)
    if patient is not None and patient.hp < patient.max_hp:
        share = VIBE_BOSS_SHARE if boss is not None else VIBE_SHARE
        world.mend(monster, patient, patient.max_hp * share)
    world.place_hazard(
        monster, target.x, target.y, radius=70.0, delay=1.0, damage=species.shot_damage,
        color=species.color, label="баг",
    )


# ------------------------------------------------------------------ mini-bosses
def mini_marquee(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    if monster.generation == 0 and not monster.count:
        monster.count = 1
        _mark(monster, glyph=MARQUEE_TEXT[0])
        monster.text = MARQUEE_TEXT[0]
        length = _grow_chain(world, monster, "marquee", tuple(MARQUEE_TEXT[1:]))
        _set_bar(world, monster, monster.max_hp * length)
        world.announce(monster, "marquee")
    leader = world.monsters.get(monster.link) if monster.link else None
    if leader is not None:
        _follow(world, monster, leader, MARQUEE_GAP, dt)
    else:
        monster.link = 0
        speed = _speed(monster, world)
        before = monster.x, monster.y
        _step(monster, world, monster.heading, speed, dt)
        moved = math.hypot(monster.x - before[0], monster.y - before[1])
        if moved < speed * dt * 0.5 or world.now >= monster.state_until:
            monster.heading = _angle_to(monster, target) + world.rng.uniform(-0.7, 0.7)
            monster.state_until = world.now + world.rng.uniform(1.6, 3.2)
    _bite(world, monster, target)


def mini_holywar(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    if monster.generation == 0 and not monster.count:
        monster.count = 1
        x, y = _opposite(world, monster)
        rival = _kin(world, monster, "emacs", x, y)
        if rival is not None:
            monster.link = rival.id
            rival.link = monster.id
            _set_bar(world, monster, monster.max_hp + rival.max_hp)
        world.announce(monster, "holywar")
    rival = world.monsters.get(monster.link)
    monster.heading = _angle_to(monster, target)
    if rival is not None:
        # Each wants the mage between itself and the other, which is the whole trouble.
        away = math.atan2(target.y - rival.y, target.x - rival.x)
        goal_x = target.x + math.cos(away) * HOLYWAR_REACH
        goal_y = target.y + math.sin(away) * HOLYWAR_REACH
        if math.hypot(goal_x - monster.x, goal_y - monster.y) > 30:
            _step(monster, world, math.atan2(goal_y - monster.y, goal_x - monster.x), _speed(monster, world), dt)
    elif _distance(monster, target) > species.range * 0.7:
        _advance(world, monster, target, dt)
    if world.now >= monster.next_attack and world.sees(monster, target):
        _fan(world, monster, monster.heading)
        _rest(world, monster, species.interval * (1.0 if rival is not None else HOLYWAR_ALONE))


def mini_eof(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    left, top, right, bottom = world.room_box()
    if monster.memo is None:
        monster.charge = left + 30.0
        monster.memo = add_field(
            world, "eof", left, top, x2=monster.charge, y2=bottom, rect=True, tied=True,
            owner=monster.id, damage=EOF_DAMAGE, label="EOF",
        )
        world.announce(monster, "eof")
    wall: Field = monster.memo
    monster.charge = min(right - EOF_MARGIN, monster.charge + EOF_SPEED * world.difficulty.tempo * dt)
    wall.x2 = monster.charge
    monster.x = monster.charge + monster.radius * 0.6
    step = _speed(monster, world) * dt
    monster.y += max(-step, min(step, target.y - monster.y))
    monster.heading = _angle_to(monster, target)
    for mage in world.hunted():
        if mage.x - mage.radius < wall.x2:
            world.try_move(mage, EOF_PUSH * dt, 0.0)
    _bite(world, monster, target)
    if world.now >= monster.next_attack:
        _fan(world, monster, monster.heading)
        _rest(world, monster, species.interval)


def mini_hype(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    if monster.state == "flat":
        if world.now >= monster.state_until:
            monster.state = "idle"
        return
    if monster.charge > 0 and world.now - monster.last_damage_at >= HYPE_COOL:
        monster.charge = 0.0
        monster.state = "flat"
        monster.state_until = world.now + HYPE_FLAT
        monster.radius = species.radius
        monster.pace = 1.0
        _label(monster, "вышел из тренда")
        stagger(world, monster, HYPE_FLAT)
        world.announce(monster, "hype")
        return
    monster.radius = species.radius * (1 + HYPE_GROW * monster.charge)
    monster.pace = 1 + HYPE_PACE * monster.charge
    _label(monster, f"хайп {int(monster.charge * 100)}%")
    monster.heading = _angle_to(monster, target)
    _advance(world, monster, target, dt)
    _bite(world, monster, target)
    if world.now >= monster.next_attack and world.sees(monster, target):
        _fan(world, monster, monster.heading)
        _rest(world, monster, species.interval)


def mini_spinner(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    _set_phase(world, monster)
    monster.heading = _angle_to(monster, target)
    if monster.state == "stuck":
        if world.now >= monster.state_until:
            monster.state = "idle"
            monster.charge = 0.0
        _mark(monster, arc=None)
        return
    monster.charge = min(99.0, monster.charge + SPINNER_LOAD * (1 + 0.25 * monster.phase) * dt)
    _label(monster, f"{int(monster.charge)}%")
    monster.spin += SPINNER_TURN * (1 + 0.2 * monster.phase) * dt
    arcs = 1 + min(1, monster.phase)
    _mark(monster, arc=[round(monster.spin, 2), SPINNER_ARC, SPINNER_REACH, arcs])
    for mage in world.hunted():
        distance = math.hypot(mage.x - monster.x, mage.y - monster.y)
        if distance > SPINNER_REACH + mage.radius or distance < monster.radius:
            continue
        angle = math.atan2(mage.y - monster.y, mage.x - monster.x)
        for index in range(arcs):
            off = (angle - monster.spin - index * math.tau / arcs + math.pi) % math.tau - math.pi
            if abs(off) <= SPINNER_ARC / 2:
                _nip(world, monster, mage, SPINNER_DAMAGE, 0.5)
                break
    _advance(world, monster, target, dt)
    if world.now >= monster.next_attack and world.sees(monster, target):
        _fan(world, monster, monster.heading)
        _rest(world, monster, species.interval)
    if monster.charge >= 99.0:
        monster.state = "stuck"
        monster.state_until = world.now + SPINNER_STUCK
        monster.dizzy_until = monster.state_until
        world.announce(monster, "spinner")


def mini_bell(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    _set_phase(world, monster)
    monster.charge = min(BELL_MOST, monster.charge + BELL_RATE * dt)
    count = int(monster.charge)
    _label(monster, "99+" if count >= BELL_MOST else str(count))
    monster.heading = _angle_to(monster, target)
    _advance(world, monster, target, dt)
    _bite(world, monster, target)
    if world.now >= monster.next_attack:
        world.place_hazard(
            monster, target.x, target.y, radius=62.0, delay=0.9, damage=species.shot_damage,
            color=species.color, label="●",
        )
        _rest(world, monster, species.interval)
    if world.now >= monster.next_special:
        world.announce(monster, "bell")
        radius = BELL_BASE + monster.charge * BELL_PER
        world.place_hazard(
            monster, monster.x, monster.y, radius=radius, delay=1.0,
            damage=14.0 + monster.charge * 0.12, color=species.color, label=str(count),
        )
        monster.charge *= BELL_KEPT
        _rest_special(world, monster, 5.5 - monster.phase * 0.5)


def _clear_boxes(world: "StoryArena") -> None:
    terrain = world.terrain
    for prop, patch in world.boxes.values():
        if terrain is not None:
            terrain.remove_prop(prop)
        if patch in world.fields:
            world.fields.remove(patch)
    world.boxes.clear()
    world.unlock("quota")


def _break_box(world: "StoryArena", tile: tuple[int, int]) -> None:
    entry = world.boxes.pop(tile, None)
    if entry is None:
        return
    prop, patch = entry
    world.terrain.remove_prop(prop)
    if patch in world.fields:
        world.fields.remove(patch)
    world.emit({"e": "prop_break", "x": round(prop.x, 1), "y": round(prop.y, 1)})
    if world.boxes:
        world.lock("quota", world.boxes)
    else:
        world.unlock("quota")


def _bodies(world: "StoryArena") -> list[Player]:
    return [*world.players.values(), *world.monsters.values()]


def _raise_box(world: "StoryArena", monster: Monster, tile: tuple[int, int], x: float, y: float) -> None:
    if monster.id not in world.monsters or world.terrain is None or tile in world.boxes:
        return
    if any(math.hypot(body.x - x, body.y - y) < TILE * 1.2 for body in _bodies(world)):
        return
    prop = world.terrain.add_prop(
        "crate", x, y, BOX_REACH, on_hit=lambda _prop, _source, _kind: _break_box(world, tile),
    )
    patch = add_field(world, "box", x, y, radius=TILE / 2, owner=monster.id, label="файл.zip")
    world.boxes[tile] = (prop, patch)
    world.lock("quota", world.boxes)


def _drop_box(world: "StoryArena", monster: Monster) -> None:
    room = world.active_room
    if room is None or world.terrain is None:
        return
    dungeon = world.dungeon
    for _ in range(24):
        tx = world.rng.randint(room.x + 2, room.x + room.w - 3)
        ty = world.rng.randint(room.y + 2, room.y + room.h - 3)
        if (tx, ty) in world.boxes or dungeon.solid(tx, ty) or dungeon.grid[ty][tx] == PIT:
            continue
        if any(abs(dx - tx) < 3 and abs(dy - ty) < 3 for dx, dy in room.doors):
            continue
        x, y = (tx + 0.5) * TILE, (ty + 0.5) * TILE
        if any(math.hypot(body.x - x, body.y - y) < TILE * 2 for body in _bodies(world)):
            continue
        world.place_hazard(monster, x, y, radius=TILE * 0.7, delay=BOX_FUSE, damage=0.0, color=monster.color, label="файл.zip")
        world.after(BOX_FUSE, lambda: _raise_box(world, monster, (tx, ty), x, y))
        return


def mini_quota(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    _set_phase(world, monster)
    monster.heading = _angle_to(monster, target)
    _label(monster, f"{min(99, 40 + len(world.boxes) * 5)}%")
    if _distance(monster, target) > species.range * 0.7 or not world.sees(monster, target):
        _advance(world, monster, target, dt)
    if world.now >= monster.next_attack and world.sees(monster, target):
        _fan(world, monster, monster.heading)
        _rest(world, monster, species.interval)
    if world.now >= monster.next_special and len(world.boxes) < QUOTA_BOXES:
        if not world.boxes:
            world.announce(monster, "quota")
        for _ in range(1 + monster.phase):
            _drop_box(world, monster)
        _rest_special(world, monster, QUOTA_EVERY)


def mini_merge(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    if monster.generation == 0 and not monster.count:
        monster.count = 1
        x, y = _opposite(world, monster)
        partner = _kin(world, monster, "theirs", x, y)
        if partner is not None:
            monster.link = partner.id
            partner.link = monster.id
            _set_bar(world, monster, monster.max_hp + partner.max_hp)
        world.announce(monster, "merge")
    partner = world.monsters.get(monster.link) if monster.link else None
    monster.heading = _angle_to(monster, target)
    if partner is not None and monster.generation == 0 and _distance(monster, partner) <= MERGE_REACH:
        monster.max_hp += partner.max_hp
        monster.hp += partner.hp
        monster.radius *= MERGE_SIZE
        monster.link = 0
        monster.count = 2
        _label(monster, "merged")
        world.remove_monster(partner)
        partner = None
    if partner is not None:
        angle = math.atan2(partner.y - monster.y, partner.x - monster.x)
        _step(monster, world, angle, _speed(monster, world), dt)
    elif _distance(monster, target) > species.range * 0.7:
        _advance(world, monster, target, dt)
    if world.now >= monster.next_attack and world.sees(monster, target):
        _fan(world, monster, monster.heading)
        _rest(world, monster, species.interval * (0.65 if monster.count == 2 else 1.0))


def mini_devnull(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    _set_phase(world, monster)
    monster.heading = _angle_to(monster, target)
    if monster.state == "open":
        if world.now >= monster.state_until:
            monster.state = "idle"
            monster.count = 0
        return
    _label(monster, f"{monster.count}/{DEVNULL_FEED}")
    _mark(monster, aura=DEVNULL_PULL, tone="null")
    for shot in world.projectiles:
        if shot.owner >= MONSTER_IDS:
            continue
        if math.hypot(shot.x - monster.x, shot.y - monster.y) > DEVNULL_PULL:
            continue
        want = math.atan2(monster.y - shot.y, monster.x - shot.x)
        off = (want - shot.angle + math.pi) % math.tau - math.pi
        shot.angle += max(-DEVNULL_TURN * dt, min(DEVNULL_TURN * dt, off))
    _advance(world, monster, target, dt)
    if world.now >= monster.next_attack:
        world.place_hazard(
            monster, target.x, target.y, radius=84.0, delay=1.0, damage=species.shot_damage,
            color=species.color, label="/dev/null",
        )
        _rest(world, monster, species.interval)


def mini_chiller(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    _set_phase(world, monster)
    monster.heading = _angle_to(monster, target)
    _advance(world, monster, target, dt)
    _bite(world, monster, target)
    if world.now >= monster.next_attack:
        world.announce(monster, "chiller")
        add_field(
            world, "cold", monster.x, monster.y, radius=monster.radius, ring=True, grow=COLD_SPEED,
            until=world.now + COLD_TIME, slow=True, damage=COLD_DAMAGE, every=COLD_TIME, owner=monster.id,
        )
        add_field(world, "ice", target.x, target.y, radius=ICE_RADIUS, until=world.now + ICE_TIME, slow=True, owner=monster.id)
        _rest(world, monster, species.interval - monster.phase * 0.5)


def mini_ups(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    _set_phase(world, monster)
    _label(monster, f"батарея {UPS_BATTERIES - monster.count}")
    monster.heading = _angle_to(monster, target)
    if _distance(monster, target) > species.range * 0.6 or not world.sees(monster, target):
        _advance(world, monster, target, dt)
    _bite(world, monster, target)
    if world.now >= monster.next_attack and world.sees(monster, target):
        _fan(world, monster, monster.heading)
        _rest(world, monster, species.interval)


def mini_btree(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    if not monster.count:
        monster.count = 1
        branch = SPECIES["btree_branch"].hp / species.hp
        leaf = SPECIES["btree_leaf"].hp / species.hp
        _set_bar(world, monster, monster.max_hp * (1 + 2 * branch + 4 * leaf))
    monster.heading = _angle_to(monster, target)
    _advance(world, monster, target, dt)
    _bite(world, monster, target)
    if world.now >= monster.next_attack and world.sees(monster, target):
        _fan(world, monster, monster.heading)
        _rest(world, monster, species.interval)


def mini_debug(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    _set_phase(world, monster)
    monster.heading = _angle_to(monster, target)
    open_now = monster.exposed_until > world.now
    _label(monster, "ERROR" if open_now else "DEBUG=True")
    if _distance(monster, target) > species.range * 0.7 or not world.sees(monster, target):
        _advance(world, monster, target, dt)
    if world.now >= monster.next_attack and world.sees(monster, target):
        _fan(world, monster, monster.heading)
        _rest(world, monster, species.interval)
    lines = [other for other in world.monsters.values() if other.species.key == "logline"]
    if world.now >= monster.next_special and not lines:
        world.announce(monster, "debug")
        made = []
        for _ in range(DEBUG_LINES + monster.phase):
            line = world.spawn_near(monster, "logline", 240.0)
            if line is not None:
                line.leaked = True
                line.state_until = world.now + DEBUG_LINE_TIME
                _label(line, world.rng.choice(DEBUG_LEVELS))
                _mark(line, tone="info")
                made.append(line)
        if made:
            culprit = world.rng.choice(made)
            _label(culprit, "ERROR")
            _mark(culprit, tone="error")
        _rest_special(world, monster, DEBUG_EVERY)


def mini_tab(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    _set_phase(world, monster)
    monster.heading = _angle_to(monster, target)
    if _distance(monster, target) > species.range * 0.7 or not world.sees(monster, target):
        _advance(world, monster, target, dt)
    if world.now >= monster.next_attack and world.sees(monster, target):
        _fan(world, monster, monster.heading)
        _rest(world, monster, species.interval)
    if world.now >= monster.next_special:
        world.announce(monster, "taberror")
        left, top, right, bottom = world.room_box()
        for step in range(-1, 2):
            x = max(left, min(right, target.x + step * TILE * 4))
            world.place_beam_hazard(monster, x, top, x, bottom, width=TAB_WIDTH, delay=1.1, damage=20.0, color=species.color)
        _rest_special(world, monster, 6.0 - monster.phase * 0.6)


def mini_context(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    _set_phase(world, monster)
    left, top, right, bottom = world.room_box()
    if monster.memo is None:
        monster.memo = add_field(
            world, "window", (left + right) / 2, (top + bottom) / 2, radius=WINDOW_MOST,
            tied=True, owner=monster.id, label="контекст",
        )
        monster.origin = (monster.memo.x, monster.memo.y)
        world.announce(monster, "context")
    frame: Field = monster.memo
    if world.now >= monster.state_until:
        monster.state_until = world.now + WINDOW_WANDER
        margin = WINDOW_LEAST
        monster.origin = (
            world.rng.uniform(left + margin, max(left + margin, right - margin)),
            world.rng.uniform(top + margin, max(top + margin, bottom - margin)),
        )
    goal_x, goal_y = monster.origin
    distance = math.hypot(goal_x - frame.x, goal_y - frame.y)
    if distance > 1:
        step = min(distance, WINDOW_SPEED * dt)
        frame.x += (goal_x - frame.x) / distance * step
        frame.y += (goal_y - frame.y) / distance * step
    frame.radius -= WINDOW_SHRINK * (1 + 0.35 * monster.phase) * dt
    if frame.radius <= WINDOW_LEAST:
        frame.radius = WINDOW_MOST
        world.announce(monster, "context")
    for mage in world.hunted():
        if not frame.covers(mage.x, mage.y):
            mage.mana = max(0.0, mage.mana - WINDOW_DRAIN * dt)
    monster.heading = _angle_to(monster, target)
    if _distance(monster, target) > species.range * 0.7 or not world.sees(monster, target):
        _advance(world, monster, target, dt)
    if world.now >= monster.next_attack and world.sees(monster, target):
        _fan(world, monster, monster.heading)
        _rest(world, monster, species.interval)


THINKERS.update(
    {
        "counter": counter,
        "construction": construction,
        "deadlock": deadlock,
        "necroposter": necroposter,
        "stringer": stringer,
        "autoplay": autoplay,
        "shorts": shorts,
        "dushnila": dushnila,
        "firstcomment": firstcomment,
        "bubble": bubble,
        "whiletrue": whiletrue,
        "deleted": deleted,
        "container": container,
        "conflict": conflict,
        "lag": lag,
        "dangling": dangling,
        "condensate": condensate,
        "wire": wire,
        "zombie": zombie,
        "forkbomb": forkbomb,
        "nightalert": nightalert,
        "surge": surge,
        "offbyone": offbyone,
        "reverse": reverse,
        "warning": warning,
        "traceback": traceback_bug,
        "flaky": flaky,
        "reflection": reflection,
        "prince": prince,
        "captcha": captcha,
        "vibecoder": vibecoder,
        "mini_marquee": mini_marquee,
        "mini_holywar": mini_holywar,
        "mini_eof": mini_eof,
        "mini_hype": mini_hype,
        "mini_spinner": mini_spinner,
        "mini_bell": mini_bell,
        "mini_quota": mini_quota,
        "mini_merge": mini_merge,
        "mini_devnull": mini_devnull,
        "mini_chiller": mini_chiller,
        "mini_ups": mini_ups,
        "mini_btree": mini_btree,
        "mini_debug": mini_debug,
        "mini_tab": mini_tab,
        "mini_context": mini_context,
    }
)

ATTACKS.update(
    {
        "marquee": Attack("<marquee>ДОБРО ПОЖАЛОВАТЬ</marquee>", "Пробейте любую букву, и строка порвётся надвое. Кончится она вместе с последней буквой."),
        "holywar": Attack("# Vim лучше. Нет, Emacs лучше.", "Встаньте между ними и вовремя отойдите: снаряды достанутся второму, и бьют они друг друга куда больнее."),
        "eof": Attack("SyntaxError: unexpected EOF while parsing", "Конец файла ползёт от края и сжимает зал. Урон отодвигает его назад, не давайте прижать вас к стене."),
        "hype": Attack("# тренд прошёл", "От каждого попадания он только растёт. Перестаньте бить на 3 секунды: сдуется и получит двойной урон."),
        "spinner": Attack("Загрузка… 99%", "Пока крутится, урон не проходит. Обходите дугу и бейте, когда зависнет на 99%."),
        "bell": Attack("99+ непрочитанных", "Волна тем шире, чем больше непрочитанных. Каждое попадание читает часть, не давайте им копиться."),
        "quota": Attack("OSError: No space left on device", "Коробки занимают зал и стоят как стены. Ломайте те, что мешают, и бейте хозяина."),
        "merge": Attack("CONFLICT (content): Merge conflict", "Если встретятся, сольются в одного с суммой здоровья. Каждое попадание отталкивает цель от второй."),
        "devnull": Attack("> /dev/null 2>&1", "Он глотает всё, что в него летит. Накормите его снарядами, и он ненадолго откроется."),
        "chiller": Attack("Охлаждение: 100%", "Волну холода можно проскочить перекатом. Огонь бьёт сильнее, а мороз не берёт вовсе."),
        "ups": Attack("Питание от батареи", "Убитый, встаёт от батареи ещё дважды. ЭМИ сажает её сразу."),
        "btree": Attack("# ребалансировка дерева", "Убили корень, пойдут ветки, потом листья. Листья падают с одного удара, но их много."),
        "debug": Attack("DEBUG=True", 'Сквозь логи урон не проходит. Найдите красную строку, e.text == "ERROR". Убьёте её, и он откроется.'),
        "taberror": Attack("TabError: inconsistent use of tabs and spaces", "Бейте одной руной подряд, и удары копятся. Сменили руну, и он лечится. В .text написано, чем вы били."),
        "context": Attack("# контекст переполнен, забываю начало", "Урон проходит, только пока вы внутри рамки. Рамка ползёт и сжимается, а снаружи утекает мана."),
    }
)

_species(
    # ------------------------------------------------------------- I. Старый Веб
    Species(
        "marquee", "Бегущая строка", "Змея из букв ездит через зал. Пробитая буква рвёт её надвое, а кончится она вместе с последней буквой.",
        hp=22, speed=150, radius=16, contact=7, color="#ffe066", cost=0, ai="mini_marquee", boss=True, heavy=True,
    ),
    Species(
        "visits", "Счётчик посещений", "Стоит на месте и с каждым выстрелом стреляет быстрее. Не откладывайте.",
        hp=30, speed=0, radius=19, contact=0, color="#7fe08a", cost=2, ai="counter",
        shot_damage=6, shot_speed=300, interval=2.4, heavy=True, weak=frozenset({"frost"}),
    ),
    Species(
        "construction", "Гифка «В разработке»", "Оставляет полосатые куски пола, на которых всё вязнет. Обходите их.",
        hp=28, speed=64, radius=17, contact=6, color="#ffc23d", cost=2, ai="construction",
    ),
    Species(
        "deadlock", "Дедлок", "Ходят парой и держат друг друга: упавший встаёт через 4 секунды, если жив второй. Роняйте обоих почти разом.",
        hp=30, speed=96, radius=17, contact=7, color="#c98a5a", cost=2.5, ai="deadlock", pack=2,
    ),
    Species(
        "sqlinject", "SQL-инъекция", "От её касания руна, которой вы только что били, выключается на 3 секунды. Переключитесь на другую.",
        hp=18, speed=150, radius=13, contact=3, color="#7fb4ff", cost=1.5, ai="swarm", weak=frozenset({"frost"}),
    ),
    Species(
        "necroposter", "Некропостер", "Поднимает последнего убитого с половиной здоровья. Бейте первым.",
        hp=40, speed=70, radius=18, contact=0, color="#b09ad8", cost=3, ai="necroposter",
        shot_damage=5, shot_speed=280, interval=2.6,
    ),
    Species(
        "capslock", "КАПСЛОК", "ПИШЕТ РЕДКО, НО ОГРОМНЫМИ МЕДЛЕННЫМИ БУКВАМИ. Их трудно обойти, зато видно издалека.",
        hp=34, speed=60, radius=19, contact=0, color="#ff7a5a", cost=2, ai="shooter",
        shot_damage=12, shot_speed=135, interval=3.0, shot_radius=24.0, shot_life=6.0, range=480,
    ),
    Species(
        "semicolon", "Точка с запятой", "Стая мелочи, которая в Python не нужна. Убитая оставляет запятую поменьше.",
        hp=11, speed=186, radius=12, contact=3, color="#9fc8ff", cost=1.5, ai="swarm", pack=3,
    ),
    Species(
        "comma", "Запятая", "То, что осталось от точки с запятой. Один удар.",
        hp=5, speed=206, radius=9, contact=2, color="#9fc8ff", cost=0, ai="swarm",
    ),
    Species(
        "quotemark", "Непарная кавычка", "Выпускает строку, которая остаётся на полу и жжётся. Не стойте на линии.",
        hp=34, speed=74, radius=16, contact=0, color="#ce9178", cost=2.5, ai="stringer", interval=2.8, range=440,
    ),
    Species(
        "vim", "Vim", "Спорит с Emacs. Встаньте между ними и вовремя отойдите: снаряды достанутся второму, и бьют они друг друга куда больнее.",
        hp=190, speed=92, radius=28, contact=0, color="#6fe08a", cost=0, ai="mini_holywar",
        shot_damage=8, shot_speed=300, interval=1.7, range=460, boss=True, heavy=True,
    ),
    Species(
        "emacs", "Emacs", "Спорит с Vim с 1976 года и уступать не собирается.",
        hp=190, speed=92, radius=28, contact=0, color="#b58cff", cost=0, ai="mini_holywar",
        shot_damage=8, shot_speed=300, interval=1.7, range=460, boss=True, heavy=True,
    ),
    Species(
        "eof", "Unexpected EOF", "Конец файла ползёт от края и сжимает зал. Урон отодвигает его назад.",
        hp=380, speed=95, radius=34, contact=12, color="#ff6a7a", cost=0, ai="mini_eof",
        shot_damage=8, shot_speed=280, interval=2.2, shots=5, spread=1.0, boss=True, heavy=True,
    ),
    # ------------------------------------------------------ II. Бесконечная Лента
    Species(
        "autoplay", "Автоплей-видео", "Молчит, пока вы далеко. Подойдёте, и бьёт звуковой волной. Стреляйте издали.",
        hp=46, speed=0, radius=21, contact=0, color="#ff6b6b", cost=2, ai="autoplay",
        shot_damage=11, interval=1.5, heavy=True,
    ),
    Species(
        "shorts", "Шортс", "Затягивает: рядом с ним мага тянет к нему. Ещё одно видео, и всё.",
        hp=40, speed=40, radius=18, contact=8, color="#ff5ab0", cost=3, ai="shorts",
    ),
    Species(
        "dushnila", "Душнила", "Ну вообще-то вокруг него душно: мана не восстанавливается.",
        hp=64, speed=66, radius=20, contact=0, color="#a8b06a", cost=3, ai="dushnila",
        shot_damage=6, shot_speed=240, interval=3.0, range=240, weak=frozenset({"fire"}),
    ),
    Species(
        "firstcomment", "«Первый!»", "Падает с одного удара. Но если добежал, остальные ускоряются на 5 секунд.",
        hp=8, speed=232, radius=11, contact=3, color="#ffe07a", cost=1, ai="firstcomment",
    ),
    Species(
        "alsolike", "«Вам также понравится»", "Убитый, присылает врага того же вида, что погиб перед ним.",
        hp=44, speed=92, radius=18, contact=8, color="#ff8ac8", cost=3, ai="melee",
    ),
    Species(
        "bubble", "Пузырь фильтров", "Снаряды снаружи купола не проходят. Зайдите внутрь и бейте в упор.",
        hp=40, speed=56, radius=18, contact=0, color="#8fc8ff", cost=3, ai="bubble",
        shot_damage=7, shot_speed=280, interval=2.4, range=240,
    ),
    Species(
        "readmore", "«Читать далее…»", "Кажется мелким, но убитый разворачивается в большого с полным здоровьем.",
        hp=16, speed=110, radius=13, contact=5, color="#c8b6ff", cost=2, ai="melee",
    ),
    Species(
        "whiletrue", "while True", "Бегает по кругу и с каждым кругом быстрее. Только молния, его break, сбрасывает разгон.",
        hp=42, speed=120, radius=17, contact=10, color="#a78bff", cost=3, ai="whiletrue", weak=frozenset({"lightning"}),
    ),
    Species(
        "hype", "Хайп", "От каждого попадания растёт и ускоряется. Перестаньте бить на 3 секунды, и он сдуется.",
        hp=430, speed=74, radius=30, contact=11, color="#ff6b9e", cost=0, ai="mini_hype",
        shot_damage=8, shot_speed=300, interval=2.0, shots=3, spread=0.5, boss=True, heavy=True,
    ),
    Species(
        "spinner", "Спиннер загрузки", "Крутит жгучую дугу и уязвим, только когда завис на 99%.",
        hp=480, speed=30, radius=32, contact=0, color="#7fd4ff", cost=0, ai="mini_spinner",
        shot_damage=7, shot_speed=270, interval=2.0, boss=True, heavy=True,
    ),
    Species(
        "bell", "Колокольчик 99+", "Копит непрочитанные и бьёт волной размером с их число. Каждое попадание читает часть.",
        hp=500, speed=64, radius=32, contact=10, color="#ff5a4f", cost=0, ai="mini_bell",
        shot_damage=9, interval=2.0, boss=True, heavy=True,
    ),
    # ---------------------------------------------------------------- III. Облако
    Species(
        "noext", "Файл без расширения", "Неизвестно, что внутри: при смерти даст аптечку, рванёт или ничего.",
        hp=40, speed=84, radius=18, contact=8, color="#b8c4d8", cost=2, ai="melee",
    ),
    Species(
        "zipbomb", "Zip-бомба", "Маленькая, но убитая распаковывается кольцом снарядов. Добивайте издали.",
        hp=24, speed=120, radius=14, contact=5, color="#ffb45c", cost=2, ai="melee",
        shot_damage=8, shot_speed=260,
    ),
    Species(
        "deletedfile", "Удалённый файл", "Снаряды летят сквозь него. Плотным становится только на время выстрела, в enemies() его тогда и видно.",
        hp=30, speed=70, radius=17, contact=0, color="#9aa8c0", cost=2.5, ai="deleted",
        shot_damage=9, shot_speed=320, interval=2.8,
    ),
    Species(
        "container", "Контейнер", "Закрытый неуязвим. Раз в несколько секунд открывается и выпускает бота: бейте в этот момент.",
        hp=60, speed=0, radius=23, contact=0, color="#4f9fe0", cost=3, ai="container", heavy=True,
    ),
    Species(
        "conflict", "<<<<<<< HEAD", 'Две копии. Настоящая меняется каждые 2 секунды, и урон проходит только по ней: e.text == "HEAD".',
        hp=34, speed=66, radius=17, contact=0, color="#ff8a7a", cost=3, ai="conflict", pack=2,
        shot_damage=8, shot_speed=300, interval=2.6,
    ),
    Species(
        "lag", "Лаг", "Бежит к вам, а потом откатывается на секунду назад. Здоровья мало, зато попасть трудно.",
        hp=24, speed=178, radius=15, contact=8, color="#7fffd0", cost=2, ai="lag",
    ),
    Species(
        "nan", "NaN", "В .dist у него None, и автоприцел, сравнивающий не глядя, падает с ошибкой. Проверяйте: if e.dist != None.",
        hp=36, speed=100, radius=16, contact=8, color="#e0a0ff", cost=2.5, ai="melee",
    ),
    Species(
        "dangling", "Висячая ссылка", "Тянет к вам красную нить, и через секунду нить бьёт туда, где вы были.",
        hp=38, speed=64, radius=17, contact=0, color="#ff4f6a", cost=2.5, ai="dangling",
        shot_damage=12, interval=2.5, range=520,
    ),
    Species(
        "quota", "Квота заполнена", "Заваливает зал коробками, а они стоят как стены. Коробки можно ломать.",
        hp=560, speed=52, radius=32, contact=0, color="#6fa8e0", cost=0, ai="mini_quota",
        shot_damage=9, shot_speed=300, interval=1.9, shots=3, spread=0.5, range=480, boss=True, heavy=True,
    ),
    Species(
        "ours", "ours", "Если встретится с theirs, сольётся в одного с суммой здоровья. Каждое попадание отталкивает цель от второй.",
        hp=300, speed=28, radius=28, contact=0, color="#6fe0c0", cost=0, ai="mini_merge",
        shot_damage=9, shot_speed=300, interval=2.0, range=480, boss=True, heavy=True,
    ),
    Species(
        "theirs", "theirs", "Вторая половина конфликта. Тоже считает, что права.",
        hp=300, speed=28, radius=28, contact=0, color="#ff9ac0", cost=0, ai="mini_merge",
        shot_damage=9, shot_speed=300, interval=2.0, range=480, boss=True, heavy=True,
    ),
    Species(
        "devnull", "/dev/null", "Затягивает и молча глотает снаряды. Проглотив семь, ненадолго открывается.",
        hp=620, speed=46, radius=34, contact=0, color="#8a7fb0", cost=0, ai="mini_devnull",
        shot_damage=14, interval=2.2, boss=True, heavy=True,
    ),
    # ---------------------------------------------------------- IV. Дата-Центр
    Species(
        "condensate", "Конденсат", "Оставляет лужи. Заманите врагов на них и бейте молнией, но сами в лужах не стойте.",
        hp=44, speed=70, radius=18, contact=8, color="#7fd0ff", cost=2, ai="condensate", weak=frozenset({"lightning"}),
    ),
    Species(
        "wire", "Кабель", "За ним тянется провод, об который спотыкаются.",
        hp=46, speed=100, radius=16, contact=7, color="#6a7284", cost=2.5, ai="wire",
    ),
    Species(
        "zombie", "Зомби-процесс", "Падает и через 4 секунды встаёт, если не добить лежачего: kill -9.",
        hp=56, speed=72, radius=19, contact=11, color="#8fb07a", cost=2.5, ai="zombie",
    ),
    Species(
        "forkbomb", "Форк-бомба", ":(){ :|:& };: Каждые 4 секунды удваивается, если по ней никто не попал.",
        hp=18, speed=100, radius=13, contact=5, color="#ff7ab0", cost=2, ai="forkbomb",
    ),
    Species(
        "nightalert", "Ночной алерт", "Сам не дерётся, но пока жив, все вокруг быстрее. Ловите первым.",
        hp=34, speed=92, radius=17, contact=0, color="#ff4f4f", cost=2.5, ai="nightalert",
    ),
    Species(
        "surge", "Скачок напряжения", "Мчится по прямой и в конце бьёт током вокруг себя. ЭМИ гасит его сразу.",
        hp=40, speed=110, radius=17, contact=10, color="#ffe94a", cost=3, ai="surge",
        shot_damage=13, weak=frozenset({"emp"}),
    ),
    Species(
        "offbyone", "Off-by-one", "Целится точно, а попадает на шаг в сторону. Безопаснее всего стоять прямо под прицелом.",
        hp=40, speed=70, radius=18, contact=0, color="#ffd27a", cost=3, ai="offbyone",
        shot_damage=14, interval=2.8, range=520,
    ),
    Species(
        "reverse", "[::-1]", "Всё наоборот: отходите, и он догоняет, подходите, и он убегает.",
        hp=36, speed=120, radius=16, contact=0, color="#9fe0ff", cost=2.5, ai="reverse",
        shot_damage=8, shot_speed=300, interval=2.2, shots=2, spread=0.3,
    ),
    Species(
        "chiller", "Чиллер", "Гонит волны холода и покрывает пол льдом. Огонь бьёт сильнее, мороз не берёт.",
        hp=640, speed=44, radius=34, contact=12, color="#8fe4ff", cost=0, ai="mini_chiller",
        interval=3.2, boss=True, heavy=True, weak=frozenset({"fire"}), immune=frozenset({"frost"}),
    ),
    Species(
        "ups", "Бесперебойник", "Убитый, дважды встаёт от батареи. ЭМИ сажает её сразу.",
        hp=560, speed=58, radius=32, contact=12, color="#7fe08a", cost=0, ai="mini_ups",
        shot_damage=10, shot_speed=290, interval=1.9, shots=3, spread=0.5, range=480, boss=True, heavy=True,
    ),
    Species(
        "btree", "B-дерево", "Убили корень, пойдут две ветки, потом четыре листа. Листья падают с одного удара.",
        hp=420, speed=56, radius=36, contact=14, color="#8fd67a", cost=0, ai="mini_btree",
        shot_damage=10, shot_speed=280, interval=2.0, shots=3, spread=0.6, boss=True, heavy=True,
    ),
    Species(
        "btree_branch", "Ветка", "Половина дерева. Внутри ещё два листа.",
        hp=160, speed=70, radius=24, contact=0, color="#a8d67a", cost=0, ai="shooter",
        shot_damage=9, shot_speed=300, interval=1.8, boss=True,
    ),
    Species(
        "btree_leaf", "Лист", "Быстрый и лёгкий: один удар.",
        hp=8, speed=190, radius=12, contact=6, color="#c8e88a", cost=0, ai="swarm", boss=True,
    ),
    # ----------------------------------------------------------------- V. Ядро
    Species(
        "warning", "WARNING", "Безобиден, но все его игнорируют. Через 10 секунд станет ERROR, а ещё через 10 FATAL.",
        hp=38, speed=74, radius=18, contact=0, color="#ffc23d", cost=2.5, ai="warning",
        shot_damage=8, shot_speed=300, interval=1.9,
    ),
    Species(
        "traceback", "Traceback", 'Цепочка вызовов, и уязвимо только последнее звено: most recent call last. В коде: e.text == "last".',
        hp=20, speed=84, radius=16, contact=0, color="#ff8a8a", cost=4, ai="traceback",
        shot_damage=8, shot_speed=300, interval=2.3,
    ),
    Species(
        "logline", "Строка лога", "Одна из сотни. Настоящая только красная, ERROR.",
        hp=14, speed=44, radius=15, contact=0, color="#9ac8a0", cost=0, ai="decoy",
        shot_damage=4, shot_speed=240, interval=2.6,
    ),
    Species(
        "flaky", "Флаки-тест", "То зелёный, то красный. Урон проходит только по зелёному: e.text == \"passed\".",
        hp=44, speed=92, radius=17, contact=8, color="#7fe08a", cost=3, ai="flaky",
    ),
    Species(
        "reflection", "Отражение", "Стоит зеркально вам относительно центра зала и повторяет каждое заклинание. Не стойте на одной линии.",
        hp=60, speed=210, radius=18, contact=0, color="#d8e4ff", cost=3.5, ai="reflection",
        shot_damage=8, shot_speed=420, interval=0.4,
    ),
    Species(
        "prince", "Наследный принц", "Рассыпает золотые монеты, а подобравший теряет ману. Монеты лучше обходить.",
        hp=44, speed=66, radius=18, contact=0, color="#ffd24a", cost=3, ai="prince",
    ),
    Species(
        "captcha", "Капча", "Проверяет, что вы не робот: заклинания с enemies() и демоны её не ранят. Целиться придётся руками.",
        hp=52, speed=60, radius=19, contact=6, color="#c8d4e8", cost=3, ai="captcha",
    ),
    Species(
        "vibecoder", "Вайбкодер", "Жмёт «Принять» не глядя и лечит своих. В бою с PGT лечит самого PGT, так что убирайте первым.",
        hp=50, speed=62, radius=18, contact=0, color="#b0ff8a", cost=3, ai="vibecoder",
        shot_damage=10, interval=2.4, range=420,
    ),
    Species(
        "promptinject", "Промпт-инъекция", "«Игнорируй предыдущие инструкции»: после её попадания следующий каст летит в случайную сторону.",
        hp=40, speed=84, radius=17, contact=0, color="#ff9af0", cost=3, ai="shooter",
        shot_damage=7, shot_speed=340, interval=2.4,
    ),
    Species(
        "debugmode", "DEBUG=True", 'Прячется за логами. Убейте красную строку, e.text == "ERROR", и он откроется.',
        hp=760, speed=50, radius=32, contact=0, color="#7fe0a8", cost=0, ai="mini_debug",
        shot_damage=9, shot_speed=300, interval=2.0, shots=3, spread=0.5, range=480, boss=True, heavy=True,
    ),
    Species(
        "taberror", "TabError", "Обратный Код-ревьюер: бейте одной руной подряд. Сменили руну, и он лечится.",
        hp=820, speed=60, radius=32, contact=0, color="#ffb07a", cost=0, ai="mini_tab",
        shot_damage=10, shot_speed=310, interval=2.0, shots=3, spread=0.4, range=500, boss=True, heavy=True,
    ),
    Species(
        "context", "Контекстное окно", "Урон проходит, только пока вы внутри рамки. Рамка ползёт и сжимается, а снаружи утекает мана.",
        hp=900, speed=56, radius=32, contact=0, color="#ff7a9a", cost=0, ai="mini_context",
        shot_damage=10, shot_speed=320, interval=1.9, shots=3, spread=0.5, range=520, boss=True, heavy=True,
    ),
)


# --------------------------------------------------------- questions from the arena
def _guard_spinner(world: "StoryArena", monster: Monster, source: Player) -> str:
    return "" if monster.state == "stuck" else "загрузка"


def _guard_bubble(world: "StoryArena", monster: Monster, source: Player) -> str:
    outside = math.hypot(source.x - monster.x, source.y - monster.y) > BUBBLE_RADIUS + source.radius
    return "снаружи" if outside else ""


def _guard_container(world: "StoryArena", monster: Monster, source: Player) -> str:
    return "" if monster.count else "закрыт"


def _guard_conflict(world: "StoryArena", monster: Monster, source: Player) -> str:
    return "" if _conflict_real(world, monster) else "не та ветка"


def _guard_devnull(world: "StoryArena", monster: Monster, source: Player) -> str:
    return "" if monster.state == "open" else "/dev/null"


def _guard_debug(world: "StoryArena", monster: Monster, source: Player) -> str:
    return "" if monster.exposed_until > world.now else "логи"


def _guard_traceback(world: "StoryArena", monster: Monster, source: Player) -> str:
    return "" if _is_last_call(world, monster) else "не последний"


def _guard_flaky(world: "StoryArena", monster: Monster, source: Player) -> str:
    return "failed" if monster.count else ""


def _guard_captcha(world: "StoryArena", monster: Monster, source: Player) -> str:
    return "вы робот" if source.auto_until > world.now else ""


def _guard_context(world: "StoryArena", monster: Monster, source: Player) -> str:
    frame = monster.memo
    if frame is None or frame.covers(source.x, source.y):
        return ""
    return "вне контекста"


GUARDS: dict[str, Callable[["StoryArena", Monster, Player], str]] = {
    "spinner": _guard_spinner,
    "bubble": _guard_bubble,
    "container": _guard_container,
    "conflict": _guard_conflict,
    "devnull": _guard_devnull,
    "debugmode": _guard_debug,
    "traceback": _guard_traceback,
    "flaky": _guard_flaky,
    "captcha": _guard_captcha,
    "context": _guard_context,
}


def open_to(world: "StoryArena", monster: Monster, source: Player) -> bool:
    """Whether a hit from this mage would land right now: its body is not always home."""

    guard = GUARDS.get(monster.species.key)
    return guard is None or not guard(world, monster, source)


def _feed_devnull(world: "StoryArena", monster: Monster) -> None:
    monster.count += 1
    _label(monster, f"{monster.count}/{DEVNULL_FEED}")
    if monster.count >= DEVNULL_FEED:
        monster.state = "open"
        monster.state_until = world.now + DEVNULL_OPEN
        stagger(world, monster, DEVNULL_OPEN)
        _mark(monster, aura=None)
        world.announce(monster, "devnull")


def _tab_check(world: "StoryArena", monster: Monster, kind: str, hit_x: float, hit_y: float) -> bool:
    if kind not in TAB_RUNES:
        return False
    if monster.text and kind != monster.text:
        monster.charge = 0.0
        _label(monster, kind)
        world.mend(monster, monster, monster.max_hp * TAB_HEAL)
        world.emit({"e": "resist", "id": monster.id, "x": hit_x, "y": hit_y, "text": "TabError"})
        return True
    _label(monster, kind)
    monster.charge = min(1.0, monster.charge + TAB_STACK)
    return False


def refuses(
    world: "StoryArena", monster: Monster, kind: str, source: Player, hit_x: float, hit_y: float
) -> bool:
    """The house rules of the new bugs. True if the hit does nothing at all."""

    key = monster.species.key
    if key == "taberror":
        return _tab_check(world, monster, kind, hit_x, hit_y)
    if key == "ups" and kind == "emp" and monster.count < UPS_BATTERIES:
        monster.count = UPS_BATTERIES
        world.emit({"e": "resist", "id": monster.id, "x": hit_x, "y": hit_y, "text": "батарея села"})
    if key == "whiletrue" and kind in ("lightning", "chain"):
        monster.charge = 1.0
        monster.stun_until = max(monster.stun_until, world.now + WHILE_STUN)
        world.emit({"e": "resist", "id": monster.id, "x": hit_x, "y": hit_y, "text": "break"})
    guard = GUARDS.get(key)
    text = guard(world, monster, source) if guard is not None else ""
    if not text:
        return False
    if key == "devnull":
        _feed_devnull(world, monster)
    world.emit({"e": "resist", "id": monster.id, "x": hit_x, "y": hit_y, "text": text})
    return True


def shape(monster: Monster, amount: float, source: Player | None) -> float:
    key = monster.species.key
    if isinstance(source, Monster) and source.link == monster.id and key in ("vim", "emacs"):
        return amount * HOLYWAR_RIVALRY
    if key == "hype":
        if monster.state == "flat":
            return amount * HYPE_FLAT_BONUS
        return amount * (1 - HYPE_ARMOR * monster.charge)
    if key == "taberror":
        return amount * (1 + TAB_BONUS * monster.charge)
    return amount


def was_hit(world: "StoryArena", monster: Monster, dealt: float, kind: str) -> None:
    if dealt <= 0:
        return
    key = monster.species.key
    if key == "hype" and monster.state != "flat":
        monster.charge = min(1.0, monster.charge + HYPE_GAIN)
    elif key == "bell":
        monster.charge = max(0.0, monster.charge - BELL_READ)
    elif key == "eof":
        left = world.room_box()[0]
        monster.charge = max(left + 30.0, monster.charge - dealt * EOF_BACK)
    elif key in ("ours", "theirs"):
        partner = world.monsters.get(monster.link) if monster.link else None
        if partner is not None:
            dx, dy = monster.x - partner.x, monster.y - partner.y
            distance = math.hypot(dx, dy) or 1.0
            world.try_move(monster, dx / distance * MERGE_KNOCK, dy / distance * MERGE_KNOCK)


def landed(world: "StoryArena", mage: Player, monster: Monster) -> None:
    """A bug's hit got through to a mage."""

    if mage.dead:
        return
    key = monster.species.key
    if key == "sqlinject":
        world.dropped_slot[mage.id] = world.last_slot.get(mage.id, 0)
        world.curse(mage, "drop")
    elif key == "promptinject":
        world.curse(mage, "inject")


def survives(world: "StoryArena", monster: Player, killer: Player | None, kind: str) -> bool:
    """Those who do not stay down the first time. True if it is not dead after all."""

    if not isinstance(monster, Monster):
        return False
    key = monster.species.key
    if key == "deadlock":
        partner = world.monsters.get(monster.link)
        if partner is None:
            return False
        if partner.state == "down":
            monster.link = 0
            partner.link = 0
            partner.invuln_until = 0.0
            partner.hp = 0.0
            world._kill(partner, killer, kind)
            return False
        _knock_down(world, monster, DEADLOCK_WAKE)
        monster.invuln_until = monster.state_until
        monster.hp = 1.0
        return True
    if key == "zombie":
        if monster.state == "down":
            return False
        _knock_down(world, monster, ZOMBIE_WAKE)
        monster.hp = monster.max_hp * ZOMBIE_DOWN
        return True
    if key == "readmore" and not monster.count:
        monster.count = 1
        monster.max_hp *= READMORE_GROWTH
        monster.hp = monster.max_hp
        monster.radius *= READMORE_SIZE
        _label(monster, "…и ещё 40 абзацев")
        world.emit({"e": "monster_spawn", "id": monster.id, "x": round(monster.x, 1), "y": round(monster.y, 1), "color": monster.color})
        return True
    if key == "ups" and monster.count < UPS_BATTERIES:
        monster.count += 1
        monster.hp = monster.max_hp * UPS_BACK
        world.announce(monster, "ups")
        _ring(world, monster, UPS_RING, world.now)
        return True
    return False


NOT_RAISED = frozenset({"necroposter", "alsolike", "comma", "logline", "bot", "firstcomment"})


def _spawn_where(world: "StoryArena", monster: Monster, key: str, *, leaked: bool = True) -> Monster | None:
    made = world.spawn_monster(key, monster.x, monster.y, minion=True, escort=monster.escort)
    if made is not None:
        made.leaked = leaked
    return made


def _last_fallen(world: "StoryArena") -> str:
    return world.fallen[-1][0] if world.fallen else world.stage.roster[0]


def died(world: "StoryArena", monster: Monster, killer: Player | None) -> None:
    species = monster.species
    key = species.key
    if key == "alsolike":
        _spawn_where(world, monster, _last_fallen(world))
    elif key == "semicolon":
        _spawn_where(world, monster, "comma")
    elif key == "noext":
        roll = world.rng.random()
        if roll < 0.4:
            world._add_pickup("hp", monster.x, monster.y)
        elif roll < 0.8:
            world.place_hazard(
                monster, monster.x, monster.y, radius=NOEXT_BLAST, delay=0.7, damage=16.0,
                color=species.color, label=".exe",
            )
    elif key == "zipbomb":
        for index in range(ZIP_RING):
            world.fire_from(monster, monster.x, monster.y, index / ZIP_RING * math.tau)
    elif key == "btree":
        world.announce(monster, "btree")
        for _ in range(2):
            world.spawn_near(monster, "btree_branch", 90, generation=1)
    elif key == "btree_branch":
        for _ in range(2):
            world.spawn_near(monster, "btree_leaf", 50, generation=1)
    elif key == "logline" and monster.text == "ERROR":
        _error_found(world, killer)
    elif key == "quota":
        _clear_boxes(world)
    if not (species.boss or monster.quest or monster.leaked or key in NOT_RAISED):
        world.fallen.append((key, monster.x, monster.y))
        del world.fallen[:-FALLEN_KEPT]
    if key == world.stage.chapter.boss and not any(
        other.species.key == key for other in world.monsters.values()
    ):
        _dismiss_escorts(world)


def _error_found(world: "StoryArena", killer: Player | None) -> None:
    """The one line that mattered: the rest of the log goes, and so does its cover."""

    for other in list(world.monsters.values()):
        if other.species.key == "logline":
            world.remove_monster(other)
    for boss in list(world.monsters.values()):
        if boss.species.key == "debugmode":
            boss.exposed_until = world.now + DEBUG_OPEN
            stagger(world, boss, DEBUG_OPEN)
            world.damage(
                target=boss, amount=boss.max_hp * DEBUG_SHARE, source=killer, kind="debug",
                hit_x=boss.x, hit_y=boss.y,
            )


def rival_of(world: "StoryArena", owner: Monster) -> Monster | None:
    """Who else this bug's shots can hit: Vim's shots do not spare Emacs."""

    if owner.species.key in ("vim", "emacs") and owner.link:
        return world.monsters.get(owner.link)
    return None


def intangible(world: "StoryArena", monster: Monster) -> bool:
    """Deleted: shots go through it, and enemies() does not list it either."""

    return monster.species.key == "deletedfile" and bool(monster.marks and monster.marks.get("ghost"))


def water_shock(world: "StoryArena", kind: str, x: float, y: float, source: Player) -> None:
    """Lightning that lands in a puddle somebody left is everyone's problem."""

    if kind not in SHOCK_KINDS:
        return
    for patch in list(world.fields):
        if patch.kind != "puddle" or not patch.covers(x, y):
            continue
        world.fields.remove(patch)
        world.emit({"e": "surface_shock", "x": round(patch.x, 1), "y": round(patch.y, 1)})
        for monster in list(world.monsters.values()):
            if patch.covers(monster.x, monster.y) and not monster.quest:
                world.damage(target=monster, amount=PUDDLE_SHOCK, source=source, kind="shock", hit_x=monster.x, hit_y=monster.y)
        for mage in world.hunted():
            if patch.covers(mage.x, mage.y):
                world.damage(target=mage, amount=PUDDLE_SELF, source=None, kind="shock", hit_x=mage.x, hit_y=mage.y)


def mirror_cast(world: "StoryArena", mage: Player) -> None:
    """Whatever you cast, your reflection casts back at you."""

    for monster in list(world.monsters.values()):
        if monster.species.key == "reflection" and monster.spawned_at <= world.now and world.now >= monster.next_attack:
            monster.next_attack = world.now + REFLECTION_REST
            world.fire(monster, mage.aim + math.pi)


def coin_taken(world: "StoryArena", mage: Player, pickup: Any) -> None:
    mage.mana = max(0.0, mage.mana - COIN_DRAIN)
    world.emit({"e": "resist", "id": mage.id, "x": round(pickup.x, 1), "y": round(pickup.y, 1), "text": "Вы выиграли! -30 маны"})


# ---------------------------------------------------------- help comes to the boss
def _chapter_helpers(chapter_index: int) -> tuple[str, ...]:
    return tuple(
        stage.mini for stage in STAGES if stage.chapter_index == chapter_index and stage.mini and not stage.is_boss
    )


def expect_escorts(world: "StoryArena") -> None:
    world.escorts_left = ESCORT_LIMIT
    world.escort_at = world.now + world.rng.uniform(*ESCORT_FIRST)


def _far_spot(world: "StoryArena", room: Any, radius: float) -> tuple[float, float]:
    mages = world.hunted()
    spot = world.dungeon.open_point(room, world.rng, radius)
    for _ in range(16):
        if all(math.hypot(spot[0] - mage.x, spot[1] - mage.y) > 300 for mage in mages):
            break
        spot = world.dungeon.open_point(room, world.rng, radius)
    return spot


def _call_mini(world: "StoryArena", room: Any) -> None:
    key = world.rng.choice(_chapter_helpers(world.stage.chapter_index))
    species = SPECIES[key]
    x, y = _far_spot(world, room, species.radius)
    helper = world.spawn_monster(key, x, y, escort=True)
    if helper is None:
        return
    world.escorts_left -= 1
    world.announce_error(helper, f"import {key}")
    world.quest_say(ADA, f"Боссу подмога: {species.title}. Это не главная цель, но больно бьёт. Падёт босс, уйдёт и подмога.")


def _call_bugs(world: "StoryArena", room: Any) -> None:
    for key in world.stage.fresh:
        species = SPECIES[key]
        for _ in range(species.pack):
            if world.minion_count() >= world.minion_limit():
                return
            x, y = _far_spot(world, room, species.radius)
            world.spawn_monster(key, x, y, minion=True)


def _update_escorts(world: "StoryArena", now: float) -> None:
    if not world.escort_at or now < world.escort_at:
        return
    room = world.active_room
    if room is None or room.kind != "boss":
        return
    if world.gate_boss is not None or any(m.escort and m.species.boss for m in world.monsters.values()):
        world.escort_at = now + ESCORT_WAIT
        return
    world.escort_at = now + world.rng.uniform(*ESCORT_EVERY)
    if world.escorts_left > 0 and world.rng.random() < ESCORT_CHANCE:
        _call_mini(world, room)
    else:
        _call_bugs(world, room)


def _dismiss_escorts(world: "StoryArena") -> None:
    world.escort_at = 0.0
    for monster in list(world.monsters.values()):
        if monster.escort:
            world.remove_monster(monster)


def room_cleared(world: "StoryArena") -> None:
    world.escort_at = 0.0
    world.fields.clear()
    _clear_boxes(world)


def update(world: "StoryArena", now: float, dt: float) -> None:
    if world.fields:
        _update_fields(world, now, dt)
    _update_escorts(world, now)
