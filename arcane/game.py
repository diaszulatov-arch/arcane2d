"""Authoritative 2D arena simulation for Arcane 2D."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from .interpreter import (
    OwnView,
    PointView,
    SpellError,
    SpellRuntimeError,
    execute_spell,
    safe_globals,
)

ARENA_W = 1900
ARENA_H = 1100
BORDER = 46
TICK_RATE = 30
PLAYER_RADIUS = 18
MOVE_SPEED = 238.0
MAX_HP = 100.0
MAX_MANA = 100.0
MANA_REGEN = 11.25
CAST_LOCK = 0.72
RESPAWN_TIME = 3.0
MAX_SPELL_ACTIONS = 7
MAX_SOURCE_CHARS = 12_000
BEAM_COLOR = "#5fd8ff"
BEAM_DAMAGE = 34.0
EMP_COLOR = "#b38cff"
EMP_DELAY = 1.5
EMP_RADIUS = 190.0
EMP_RANGE = 560.0
EMP_MAX_DRAIN = 35.0
EMP_DAMAGE_PER_MANA = 1.0
EMP_PULL_DISTANCE = 160.0
EMP_PULL_LEAD = 0.5
STRIKE_COLOR = "#9fd4ff"
STRIKE_DAMAGE = 28.0
STRIKE_STUN = 0.5
STRIKE_RANGE = 760.0
STRIKE_WIDTH = 55.0
CHAIN_COLOR = "#c9f6ff"
CHAIN_RANGE = 680.0
CHAIN_WIDTH = 90.0
CHAIN_JUMP_RANGE = 300.0
CHAIN_DAMAGE = (30.0, 24.0, 18.0)
CHAIN_TARGETS = 3
METEOR_COLOR = "#ff7b45"
METEOR_DELAY = 1.15
METEOR_RADIUS = 120.0
METEOR_RANGE = 620.0
METEOR_DAMAGE = 42.0
METEOR_COUNT = 3
METEOR_PUSH = 30.0
SIPHON_COLOR = "#ff6b9e"
SIPHON_RANGE = 380.0
SIPHON_WIDTH = 64.0
SIPHON_DAMAGE = 18.0
SIPHON_HEAL_RATIO = 0.6
SIPHON_MAX_HEAL = 18.0
POISON_COLOR = "#86e08a"
POISON_CLOUD_RANGE = 520.0
POISON_CLOUD_RADIUS = 110.0
POISON_CLOUD_DURATION = 4.2
POISON_TICK = 0.75
POISON_DAMAGE = 6.0
ROLL_DISTANCE = 165.0
ROLL_COOLDOWN = 1.6
ROLL_INVULN = 0.22

SPARK_COLORS = [
    "#ffe17a",  # yellow
    "#b596ff",  # purple
    "#6fdcff",  # blue
    "#7df0b1",  # green
    "#ff83b7",  # pink
    "#ffb86b",  # amber
    "#8f7bff",  # deep violet
    "#5ff0e0",  # cyan
]

COLORS = [
    "#ffb86b",
    "#6fdcff",
    "#b596ff",
    "#7df0b1",
    "#ff83b7",
    "#ffe17a",
    "#ff8d7a",
    "#8fb3ff",
]

OBSTACLES: list[dict[str, Any]] = [
    {"x": 950, "y": 550, "r": 78, "kind": "altar"},
    {"x": 500, "y": 330, "r": 46, "kind": "pillar"},
    {"x": 1400, "y": 330, "r": 46, "kind": "pillar"},
    {"x": 500, "y": 770, "r": 46, "kind": "pillar"},
    {"x": 1400, "y": 770, "r": 46, "kind": "pillar"},
    {"x": 250, "y": 550, "r": 34, "kind": "ruin"},
    {"x": 1650, "y": 550, "r": 34, "kind": "ruin"},
    {"x": 950, "y": 250, "r": 30, "kind": "crystal"},
    {"x": 950, "y": 850, "r": 30, "kind": "crystal"},
]

SPAWNS = [
    {"x": 650, "y": 360},
    {"x": 1250, "y": 360},
    {"x": 650, "y": 740},
    {"x": 1250, "y": 740},
    {"x": 950, "y": 330},
    {"x": 950, "y": 770},
]

SPELL_COSTS = {
    "fireball": 11,
    "frostbolt": 9,
    "dash": 10,
    "blink": 17,
    "shield": 17,
    "heal": 24,
    "nova": 21,
    "ward": 15,
    "beam": 50,
    "spark_volley": 25,
    "emp": 36,
    "chain_lightning": 34,
    "lightning_strike": 32,
    "meteor": 38,
    "siphon": 28,
    "poison_cloud": 30,
}


@dataclass(slots=True)
class Input:
    up: bool = False
    down: bool = False
    left: bool = False
    right: bool = False


@dataclass(slots=True)
class Player:
    id: int
    name: str
    color: str
    x: float
    y: float
    aim: float = 0.0
    hp: float = MAX_HP
    mana: float = MAX_MANA
    score: int = 0
    deaths: int = 0
    shield: float = 0.0
    shield_until: float = 0.0
    shield_ready_at: float = 0.0
    heal_ready_at: float = 0.0
    slow_until: float = 0.0
    stun_until: float = 0.0
    invuln_until: float = 0.0
    last_damage_at: float = -100.0
    last_cast_at: float = -100.0
    cast_ready_at: float = 0.0
    roll_ready_at: float = 0.0
    dead: bool = False
    respawn_at: float = 0.0
    is_bot: bool = False
    input: Input = field(default_factory=Input)
    next_bot_cast: float = 0.0
    bot_style: str = "fire"
    last_x: float = 0.0
    last_y: float = 0.0

    def __post_init__(self) -> None:
        self.last_x = self.x
        self.last_y = self.y


@dataclass(slots=True)
class Projectile:
    id: int
    owner: int
    kind: str
    x: float
    y: float
    angle: float
    speed: float
    damage: float
    radius: float
    life: float
    color: str
    slow_until: float = 0.0


@dataclass(slots=True)
class Ward:
    id: int
    owner: int
    x: float
    y: float
    armed_at: float
    expires_at: float
    trigger_radius: float = 74.0
    blast_radius: float = 118.0
    damage: float = 22.0


@dataclass(slots=True)
class Emp:
    id: int
    owner: int
    x: float
    y: float
    detonate_at: float
    pull_at: float = 0.0
    pulled: bool = False
    radius: float = EMP_RADIUS


@dataclass(slots=True)
class Meteor:
    id: int
    owner: int
    x: float
    y: float
    impact_at: float
    radius: float = METEOR_RADIUS
    damage: float = METEOR_DAMAGE
    push: float = METEOR_PUSH
    role: str = "main"
    variant: int = 0
    color: str = METEOR_COLOR


@dataclass(slots=True)
class PoisonCloud:
    id: int
    owner: int
    x: float
    y: float
    expires_at: float
    next_tick: float
    radius: float = POISON_CLOUD_RADIUS
    damage: float = POISON_DAMAGE
    color: str = POISON_COLOR


BOT_PROFILES = [
    {
        "name": "Игнис",
        "color": "#ff8a5c",
        "style": "fire",
        "interval": (1.35, 2.25),
    },
    {
        "name": "Нивара",
        "color": "#70dcff",
        "style": "frost",
        "interval": (1.55, 2.55),
    },
    {
        "name": "Орбис",
        "color": "#b9a1ff",
        "style": "arcane",
        "interval": (1.7, 2.7),
    },
]

BOT_SPELLS = {
    "fire": """
fireball(aim() + rand(-0.055, 0.055))

if me().hp < 36 and me().shield < 1:
    shield()
""",
    "frost": """
frostbolt(aim() + rand(-0.045, 0.045))

if me().shield < 1:
    shield()
if me().hp < 54:
    heal()
""",
    "arcane": """
fireball(aim() + rand(-0.08, 0.08))

if me().shield < 1:
    shield()
""",
}


class SpellSession:
    """The complete API exposed to one casting of player code."""

    def __init__(
        self,
        arena: "Arena",
        player: Player,
        now: float,
        *,
        cursor_x: float | None = None,
        cursor_y: float | None = None,
    ) -> None:
        self.arena = arena
        self.player = player
        self.now = now
        self.cursor_x = cursor_x
        self.cursor_y = cursor_y
        self.actions = 0
        self.logs: list[str] = []
        self.says = 0
        self.dashes = 0
        self.blinks = 0
        self.novas = 0
        self.wards_placed = 0
        self.beams = 0
        self.volleys = 0
        self.emps_placed = 0
        self.chains = 0
        self.strikes = 0
        self.meteors = 0
        self.siphons = 0
        self.clouds = 0

    # -------------------------------------------------------------- read side
    def me(self) -> OwnView:
        player = self.player
        return OwnView(
            name=player.name,
            x=round(player.x, 2),
            y=round(player.y, 2),
            hp=round(player.hp, 1),
            max_hp=MAX_HP,
            mana=round(player.mana, 1),
            max_mana=MAX_MANA,
            shield=round(player.shield, 1),
            aim=round(player.aim, 4),
        )

    def aim(self) -> float:
        return self.player.aim

    def cursor(self) -> PointView | None:
        if self.cursor_x is None or self.cursor_y is None:
            return None
        return PointView(
            x=round(self.cursor_x, 2),
            y=round(self.cursor_y, 2),
            dist=round(
                math.hypot(
                    self.cursor_x - self.player.x,
                    self.cursor_y - self.player.y,
                ),
                2,
            ),
        )

    def direction(self, x: Any, y: Any) -> float:
        target_x = _api_number(x, "x")
        target_y = _api_number(y, "y")
        return math.atan2(target_y - self.player.y, target_x - self.player.x)

    def distance(self, x1: Any, y1: Any, x2: Any, y2: Any) -> float:
        return math.hypot(
            _api_number(x2, "x2") - _api_number(x1, "x1"),
            _api_number(y2, "y2") - _api_number(y1, "y1"),
        )

    # ------------------------------------------------------------- write side
    def _check_alive(self) -> None:
        if self.player.dead:
            raise SpellRuntimeError("Маг мёртв и не может колдовать.")
        if self.arena.now - self.player.last_cast_at > 5.0:
            # Defensive: sessions are short-lived and run synchronously.
            raise SpellRuntimeError("Заклинание устарело.")

    def _spend(self, cost: int, action: str) -> None:
        self._check_alive()
        if self.actions >= MAX_SPELL_ACTIONS:
            raise SpellRuntimeError(
                f"Слишком много действий в одном заклинании (максимум {MAX_SPELL_ACTIONS})."
            )
        if self.player.mana + 1e-6 < cost:
            raise SpellRuntimeError(
                f"Не хватает маны для «{action}»: нужно {cost}, есть {int(self.player.mana)}."
            )
        self.player.mana -= cost
        self.actions += 1

    def fireball(self, angle: Any, speed: Any = 1.0) -> None:
        angle = _api_angle(angle)
        power = max(0.6, min(1.5, _api_number(speed, "speed")))
        self._spend(SPELL_COSTS["fireball"], "fireball")
        player = self.player
        px = player.x + math.cos(angle) * 28
        py = player.y + math.sin(angle) * 28
        self.arena.spawn_projectile(
            owner=player,
            kind="fire",
            x=px,
            y=py,
            angle=angle,
            speed=575.0 * power,
            damage=16.0,
            radius=7.0,
            life=1.65,
            color="#ff9a4d",
        )
        self.arena.emit(
            {
                "e": "cast",
                "id": player.id,
                "kind": "fire",
                "x": round(px, 1),
                "y": round(py, 1),
                "color": "#ff9a4d",
            }
        )

    def frostbolt(self, angle: Any) -> None:
        angle = _api_angle(angle)
        self._spend(SPELL_COSTS["frostbolt"], "frostbolt")
        player = self.player
        px = player.x + math.cos(angle) * 28
        py = player.y + math.sin(angle) * 28
        self.arena.spawn_projectile(
            owner=player,
            kind="frost",
            x=px,
            y=py,
            angle=angle,
            speed=640.0,
            damage=10.0,
            radius=6.0,
            life=1.5,
            color="#7ce7ff",
            slow_until=self.now + 2.4,
        )
        self.arena.emit(
            {
                "e": "cast",
                "id": player.id,
                "kind": "frost",
                "x": round(px, 1),
                "y": round(py, 1),
                "color": "#7ce7ff",
            }
        )

    def spark_volley(self, angle: Any, count: Any = 8, spread: Any = 1.1) -> None:
        if self.volleys >= 1:
            raise SpellRuntimeError("В одном заклинании возможен только один веер искр.")
        angle = _api_angle(angle)
        count = int(_api_number(count, "count"))
        if count < 1 or count > 8:
            raise SpellRuntimeError("Количество искр должно быть от 1 до 8.")
        spread = max(0.2, min(1.6, _api_number(spread, "spread")))
        self._spend(SPELL_COSTS["spark_volley"], "spark_volley")
        self.volleys += 1
        player = self.player
        origin_angle = angle
        origin_x = player.x + math.cos(origin_angle) * 26
        origin_y = player.y + math.sin(origin_angle) * 26

        for index in range(count):
            offset = 0.0
            if count > 1:
                offset = (index - (count - 1) / 2) * spread / (count - 1)
            spark_angle = angle + offset
            self.arena.spawn_projectile(
                owner=player,
                kind="spark",
                x=player.x + math.cos(spark_angle) * 26,
                y=player.y + math.sin(spark_angle) * 26,
                angle=spark_angle,
                speed=680.0,
                damage=5.0,
                radius=5.0,
                life=1.3,
                color=SPARK_COLORS[index % len(SPARK_COLORS)],
            )

        self.arena.emit(
            {
                "e": "cast",
                "id": player.id,
                "kind": "spark",
                "x": round(origin_x, 1),
                "y": round(origin_y, 1),
                "color": SPARK_COLORS[0],
                "count": count,
            }
        )

    def dash(self, angle: Any, distance: Any = 170) -> None:
        if self.dashes >= 1:
            raise SpellRuntimeError("В одном заклинании возможен только один рывок.")
        angle = _api_angle(angle)
        requested = max(60.0, min(260.0, _api_number(distance, "distance")))
        destination = self.arena.dash_destination(self.player, angle, requested)
        if destination is None:
            raise SpellRuntimeError("Путь рывка перекрыт.")
        self._spend(SPELL_COSTS["dash"], "dash")
        self.dashes += 1
        start_x, start_y = self.player.x, self.player.y
        self.player.x, self.player.y = destination
        self.arena.emit(
            {
                "e": "dash",
                "id": self.player.id,
                "from_x": round(start_x, 1),
                "from_y": round(start_y, 1),
                "to_x": round(self.player.x, 1),
                "to_y": round(self.player.y, 1),
                "color": self.player.color,
            }
        )

    def blink(self, x: Any, y: Any) -> None:
        if self.blinks >= 1:
            raise SpellRuntimeError("В одном заклинании возможен только один блинк.")
        target_x = _api_number(x, "x")
        target_y = _api_number(y, "y")
        if not self.arena.can_stand(target_x, target_y):
            raise SpellRuntimeError("Туда нельзя переместиться: препятствие или край арены.")
        self._spend(SPELL_COSTS["blink"], "blink")
        self.blinks += 1
        start_x, start_y = self.player.x, self.player.y
        self.player.x = target_x
        self.player.y = target_y
        self.arena.emit(
            {
                "e": "dash",
                "id": self.player.id,
                "kind": "blink",
                "from_x": round(start_x, 1),
                "from_y": round(start_y, 1),
                "to_x": round(target_x, 1),
                "to_y": round(target_y, 1),
                "color": "#b596ff",
            }
        )

    def shield(self) -> None:
        if self.now < self.player.shield_ready_at:
            raise SpellRuntimeError(
                f"Щит восстанавливается ещё {max(0.1, self.player.shield_ready_at - self.now):.1f} с."
            )
        if self.player.shield > 0.5:
            raise SpellRuntimeError("Щит уже активен.")
        self._spend(SPELL_COSTS["shield"], "shield")
        self.player.shield = 38.0
        self.player.shield_until = self.now + 4.2
        self.player.shield_ready_at = self.now + 3.0
        self.arena.emit({"e": "shield", "id": self.player.id})

    def heal(self) -> None:
        if self.now < self.player.heal_ready_at:
            raise SpellRuntimeError(
                f"Исцеление будет готово через {max(0.1, self.player.heal_ready_at - self.now):.1f} с."
            )
        if self.player.hp >= MAX_HP - 0.5:
            raise SpellRuntimeError("Здоровье уже полное.")
        self._spend(SPELL_COSTS["heal"], "heal")
        healed = min(30.0, MAX_HP - self.player.hp)
        self.player.hp += healed
        self.player.heal_ready_at = self.now + 4.5
        self.arena.emit(
            {
                "e": "heal",
                "id": self.player.id,
                "x": round(self.player.x, 1),
                "y": round(self.player.y, 1),
                "amount": round(healed, 1),
            }
        )

    def nova(self, radius: Any = 150) -> None:
        if self.novas >= 1:
            raise SpellRuntimeError("В одном заклинании возможна только одна нова.")
        radius = max(80.0, min(220.0, _api_number(radius, "radius")))
        self._spend(SPELL_COSTS["nova"], "nova")
        self.novas += 1
        player = self.player
        self.arena.emit(
            {
                "e": "nova",
                "id": player.id,
                "x": round(player.x, 1),
                "y": round(player.y, 1),
                "radius": round(radius, 1),
                "color": player.color,
            }
        )
        for other in list(self.arena.players.values()):
            if other.id == player.id or other.dead:
                continue
            distance = math.hypot(other.x - player.x, other.y - player.y)
            if distance <= radius:
                self.arena.damage(
                    target=other,
                    amount=15.0,
                    source=player,
                    kind="nova",
                    hit_x=other.x,
                    hit_y=other.y,
                )
                self.arena.displace(other, player.x, player.y, 42.0)

    def beam(self, angle: Any, length: Any = 780, width: Any = 96) -> None:
        if self.beams >= 1:
            raise SpellRuntimeError("В одном заклинании возможен только один луч.")
        angle = _api_angle(angle)
        length = max(300.0, min(1_000.0, _api_number(length, "length")))
        width = max(40.0, min(140.0, _api_number(width, "width")))
        self._spend(SPELL_COSTS["beam"], "beam")
        self.beams += 1
        player = self.player
        dx = math.cos(angle)
        dy = math.sin(angle)
        start_x = player.x + dx * (PLAYER_RADIUS + 6)
        start_y = player.y + dy * (PLAYER_RADIUS + 6)
        end_x, end_y = _ray_arena_end(start_x, start_y, dx, dy, length)

        self.arena.emit(
            {
                "e": "beam",
                "id": player.id,
                "x": round(start_x, 1),
                "y": round(start_y, 1),
                "x2": round(end_x, 1),
                "y2": round(end_y, 1),
                "width": round(width, 1),
                "color": BEAM_COLOR,
            }
        )
        half_width = width * 0.5 + PLAYER_RADIUS
        for other in list(self.arena.players.values()):
            if other.id == player.id or other.dead:
                continue
            if (
                _segment_circle_distance(
                    start_x, start_y, end_x, end_y, other.x, other.y
                )
                <= half_width
            ):
                self.arena.damage(
                    target=other,
                    amount=BEAM_DAMAGE,
                    source=player,
                    kind="beam",
                    hit_x=other.x,
                    hit_y=other.y,
                )
                self.arena.displace(other, start_x, start_y, 20.0)

    def emp(self, x: Any, y: Any) -> None:
        if self.emps_placed >= 1:
            raise SpellRuntimeError("В одном заклинании можно создать только один E.M.P.")
        target_x = _api_number(x, "x")
        target_y = _api_number(y, "y")
        if math.hypot(target_x - self.player.x, target_y - self.player.y) > EMP_RANGE:
            raise SpellRuntimeError(
                f"E.M.P. можно создать не дальше {int(EMP_RANGE)} единиц от себя."
            )
        if not (
            BORDER + 8 <= target_x <= ARENA_W - BORDER - 8
            and BORDER + 8 <= target_y <= ARENA_H - BORDER - 8
        ):
            raise SpellRuntimeError("E.M.P. нужно навести внутрь арены.")
        self._spend(SPELL_COSTS["emp"], "E.M.P.")
        self.emps_placed += 1
        self.arena.place_emp(self.player, target_x, target_y)

    def ward(self, x: Any = None, y: Any = None) -> None:
        if self.wards_placed >= 1:
            raise SpellRuntimeError("В одном заклинании можно поставить только одну руну.")
        target_x = self.player.x if x is None else _api_number(x, "x")
        target_y = self.player.y if y is None else _api_number(y, "y")
        if math.hypot(target_x - self.player.x, target_y - self.player.y) > 480:
            raise SpellRuntimeError("Руну можно поставить не дальше 480 единиц от себя.")
        if not self.arena.can_stand(target_x, target_y):
            raise SpellRuntimeError("Руна не помещается на это место.")
        owner_wards = [
            ward for ward in self.arena.wards if ward.owner == self.player.id
        ]
        if len(owner_wards) >= 2:
            raise SpellRuntimeError("У вас уже две активные руны.")
        self._spend(SPELL_COSTS["ward"], "ward")
        self.wards_placed += 1
        self.arena.place_ward(self.player, target_x, target_y)

    def chain_lightning(self, angle: Any, targets: Any = 3) -> None:
        if self.chains >= 1:
            raise SpellRuntimeError("В одном заклинании возможна только одна цепная молния.")
        angle = _api_angle(angle)
        count = int(_api_number(targets, "targets"))
        if count < 1 or count > CHAIN_TARGETS:
            raise SpellRuntimeError(
                f"Количество целей должно быть от 1 до {CHAIN_TARGETS}."
            )

        player = self.player
        dx = math.cos(angle)
        dy = math.sin(angle)
        start_x = player.x + dx * (PLAYER_RADIUS + 6)
        start_y = player.y + dy * (PLAYER_RADIUS + 6)
        first: Player | None = None
        best_projection = float("inf")
        for other in self.arena.players.values():
            if other.id == player.id or other.dead:
                continue
            offset_x = other.x - player.x
            offset_y = other.y - player.y
            distance = math.hypot(offset_x, offset_y)
            if distance > CHAIN_RANGE:
                continue
            projection = offset_x * dx + offset_y * dy
            if projection < 0:
                continue
            lateral = abs(offset_x * -dy + offset_y * dx)
            if lateral > CHAIN_WIDTH:
                continue
            if projection < best_projection:
                first = other
                best_projection = projection
        if first is None:
            raise SpellRuntimeError("В направлении нет цели для цепной молнии.")

        self._spend(SPELL_COSTS["chain_lightning"], "chain_lightning")
        self.chains += 1
        selected: list[Player] = [first]
        while len(selected) < count:
            previous = selected[-1]
            next_target: Player | None = None
            nearest = float("inf")
            for other in self.arena.players.values():
                if (
                    other.id == player.id
                    or other.dead
                    or other in selected
                ):
                    continue
                distance = math.hypot(other.x - previous.x, other.y - previous.y)
                if distance <= CHAIN_JUMP_RANGE and distance < nearest:
                    next_target = other
                    nearest = distance
            if next_target is None:
                break
            selected.append(next_target)

        points = [[round(start_x, 1), round(start_y, 1)]]
        for index, target in enumerate(selected):
            points.append([round(target.x, 1), round(target.y, 1)])
            self.arena.damage(
                target=target,
                amount=CHAIN_DAMAGE[min(index, len(CHAIN_DAMAGE) - 1)],
                source=player,
                kind="chain",
                hit_x=target.x,
                hit_y=target.y,
            )
        self.arena.emit(
            {
                "e": "chain_lightning",
                "id": player.id,
                "points": points,
                "hits": len(selected),
                "color": CHAIN_COLOR,
            }
        )

    def lightning_strike(self, angle: Any) -> None:
        if self.strikes >= 1:
            raise SpellRuntimeError("В одном заклинании возможна только одна небесная молния.")
        angle = _api_angle(angle)
        player = self.player
        dx = math.cos(angle)
        dy = math.sin(angle)
        target_player: Player | None = None
        best_projection = float("inf")
        for other in self.arena.players.values():
            if other.id == player.id or other.dead:
                continue
            offset_x = other.x - player.x
            offset_y = other.y - player.y
            distance = math.hypot(offset_x, offset_y)
            if distance > STRIKE_RANGE:
                continue
            projection = offset_x * dx + offset_y * dy
            if projection < 0:
                continue
            lateral = abs(offset_x * -dy + offset_y * dx)
            if lateral > STRIKE_WIDTH:
                continue
            if projection < best_projection:
                target_player = other
                best_projection = projection
        if target_player is None:
            raise SpellRuntimeError("В направлении нет цели для небесной кары.")

        self._spend(SPELL_COSTS["lightning_strike"], "lightning_strike")
        self.strikes += 1
        stunned = target_player.invuln_until <= self.now
        if stunned:
            target_player.stun_until = max(
                target_player.stun_until,
                self.now + STRIKE_STUN,
            )
        self.arena.damage(
            target=target_player,
            amount=STRIKE_DAMAGE,
            source=player,
            kind="lightning",
            hit_x=target_player.x,
            hit_y=target_player.y,
        )
        self.arena.emit(
            {
                "e": "lightning_strike",
                "id": player.id,
                "target_id": target_player.id,
                "x": round(target_player.x, 1),
                "y": round(target_player.y, 1),
                "damage": STRIKE_DAMAGE,
                "stun": STRIKE_STUN if stunned else 0.0,
                "color": STRIKE_COLOR,
            }
        )

    def meteor(self, x: Any, y: Any, radius: Any = METEOR_RADIUS) -> None:
        if self.meteors >= 1:
            raise SpellRuntimeError("В одном заклинании возможен только один метеорит.")
        target_x = _api_number(x, "x")
        target_y = _api_number(y, "y")
        if math.hypot(target_x - self.player.x, target_y - self.player.y) > METEOR_RANGE:
            raise SpellRuntimeError(
                f"Метеорит можно призвать не дальше {int(METEOR_RANGE)} единиц от себя."
            )
        if not (
            BORDER + 8 <= target_x <= ARENA_W - BORDER - 8
            and BORDER + 8 <= target_y <= ARENA_H - BORDER - 8
        ):
            raise SpellRuntimeError("Метеорит нужно навести внутрь арены.")
        radius = max(80.0, min(160.0, _api_number(radius, "radius")))
        self._spend(SPELL_COSTS["meteor"], "meteor")
        self.meteors += 1
        self.arena.place_meteor_volley(self.player, target_x, target_y, radius)

    def siphon(self, angle: Any, length: Any = SIPHON_RANGE, width: Any = SIPHON_WIDTH) -> None:
        if self.siphons >= 1:
            raise SpellRuntimeError("В одном заклинании возможно только одно похищение жизни.")
        angle = _api_angle(angle)
        length = max(160.0, min(520.0, _api_number(length, "length")))
        width = max(36.0, min(110.0, _api_number(width, "width")))
        self._spend(SPELL_COSTS["siphon"], "siphon")
        self.siphons += 1
        player = self.player
        dx = math.cos(angle)
        dy = math.sin(angle)
        start_x = player.x + dx * (PLAYER_RADIUS + 6)
        start_y = player.y + dy * (PLAYER_RADIUS + 6)
        end_x, end_y = _ray_arena_end(start_x, start_y, dx, dy, length)
        half_width = width * 0.5 + PLAYER_RADIUS
        total_lost = 0.0
        hits = 0
        for other in list(self.arena.players.values()):
            if other.id == player.id or other.dead:
                continue
            if (
                _segment_circle_distance(
                    start_x, start_y, end_x, end_y, other.x, other.y
                )
                <= half_width
            ):
                total_lost += self.arena.damage(
                    target=other,
                    amount=SIPHON_DAMAGE,
                    source=player,
                    kind="siphon",
                    hit_x=other.x,
                    hit_y=other.y,
                )
                hits += 1
        healed = min(SIPHON_MAX_HEAL, total_lost * SIPHON_HEAL_RATIO)
        if healed > 0.0:
            player.hp = min(MAX_HP, player.hp + healed)
        self.arena.emit(
            {
                "e": "siphon",
                "id": player.id,
                "x": round(start_x, 1),
                "y": round(start_y, 1),
                "x2": round(end_x, 1),
                "y2": round(end_y, 1),
                "width": round(width, 1),
                "healed": round(healed, 1),
                "hits": hits,
                "color": SIPHON_COLOR,
            }
        )

    def poison_cloud(self, x: Any, y: Any, radius: Any = POISON_CLOUD_RADIUS) -> None:
        if self.clouds >= 1:
            raise SpellRuntimeError("В одном заклинании возможно только одно ядовитое облако.")
        target_x = _api_number(x, "x")
        target_y = _api_number(y, "y")
        if math.hypot(target_x - self.player.x, target_y - self.player.y) > POISON_CLOUD_RANGE:
            raise SpellRuntimeError(
                f"Облако можно создать не дальше {int(POISON_CLOUD_RANGE)} единиц от себя."
            )
        if not (
            BORDER + 8 <= target_x <= ARENA_W - BORDER - 8
            and BORDER + 8 <= target_y <= ARENA_H - BORDER - 8
        ):
            raise SpellRuntimeError("Облако нужно навести внутрь арены.")
        radius = max(70.0, min(150.0, _api_number(radius, "radius")))
        self._spend(SPELL_COSTS["poison_cloud"], "poison_cloud")
        self.clouds += 1
        self.arena.place_poison_cloud(self.player, target_x, target_y, radius)

    # -------------------------------------------------------------- cosmetics
    def say(self, text: Any) -> None:
        if self.says >= 2:
            raise SpellRuntimeError("Нельзя произнести больше двух фраз за заклинание.")
        message = str(text).replace("\n", " ").strip()[:80]
        if not message:
            return
        self.says += 1
        self.arena.emit(
            {"e": "say", "id": self.player.id, "text": message}
        )

    def log(self, *values: Any) -> None:
        if len(self.logs) >= 6:
            return
        parts: list[str] = []
        for value in values:
            if isinstance(value, OwnView):
                parts.append(f"{value.name} ({value.hp:.0f} HP)")
            elif isinstance(value, PointView):
                parts.append(f"точка ({value.x:.1f}, {value.y:.1f})")
            else:
                parts.append(str(value))
        line = " ".join(parts)[:220]
        self.logs.append(line)

    def globals(self) -> dict[str, Any]:
        return safe_globals(
            {
                "me": self.me,
                "aim": self.aim,
                "cursor": self.cursor,
                "direction": self.direction,
                "distance": self.distance,
                "fireball": self.fireball,
                "frostbolt": self.frostbolt,
                "spark_volley": self.spark_volley,
                "dash": self.dash,
                "blink": self.blink,
                "shield": self.shield,
                "heal": self.heal,
                "nova": self.nova,
                "beam": self.beam,
                "emp": self.emp,
                "ward": self.ward,
                "chain_lightning": self.chain_lightning,
                "lightning_strike": self.lightning_strike,
                "meteor": self.meteor,
                "siphon": self.siphon,
                "poison_cloud": self.poison_cloud,
                "say": self.say,
                "log": self.log,
                "print": self.log,
                "ARENA_W": ARENA_W,
                "ARENA_H": ARENA_H,
            }
        )


def _api_number(value: Any, name: str) -> float:
    if type(value) not in (int, float):
        raise SpellRuntimeError(f"Аргумент «{name}» должен быть числом.")
    number = float(value)
    if not math.isfinite(number):
        raise SpellRuntimeError(f"Аргумент «{name}» должен быть конечным числом.")
    return number


def _api_angle(value: Any) -> float:
    return _api_number(value, "angle")


class Arena:
    def __init__(self, *, bots: int = 2) -> None:
        self.players: dict[int, Player] = {}
        self.projectiles: list[Projectile] = []
        self.wards: list[Ward] = []
        self.emps: list[Emp] = []
        self.meteors: list[Meteor] = []
        self.clouds: list[PoisonCloud] = []
        self.events: list[dict[str, Any]] = []
        self.now = 0.0
        self._next_player_id = 1
        self._next_projectile_id = 1
        self._next_ward_id = 1
        self._next_emp_id = 1
        self._next_meteor_id = 1
        self._next_cloud_id = 1
        self._last_tick = 0.0
        self.bots_wanted = max(0, min(6, bots))
        self._spawn_bots()

    # ------------------------------------------------------------------ setup
    def world_config(self) -> dict[str, Any]:
        return {
            "arena": {"w": ARENA_W, "h": ARENA_H, "border": BORDER},
            "obstacles": OBSTACLES,
            "spawns": SPAWNS,
            "speed": MOVE_SPEED,
            "player_radius": PLAYER_RADIUS,
            "cast_lock": CAST_LOCK,
            "respawn": RESPAWN_TIME,
            "max_actions": MAX_SPELL_ACTIONS,
            "spell_costs": SPELL_COSTS,
            "roll": {
                "distance": ROLL_DISTANCE,
                "cooldown": ROLL_COOLDOWN,
                "invuln": ROLL_INVULN,
            },
            "tick_rate": TICK_RATE,
        }

    def _spawn_bots(self) -> None:
        for index in range(self.bots_wanted):
            profile = BOT_PROFILES[index % len(BOT_PROFILES)]
            self.add_player(
                profile["name"],
                is_bot=True,
                color=profile["color"],
                bot_style=profile["style"],
            )

    def add_player(
        self,
        name: str,
        *,
        is_bot: bool = False,
        color: str | None = None,
        bot_style: str = "fire",
    ) -> Player:
        name = str(name).strip()[:16] or "Маг"
        base_name = name
        suffix = 2
        while any(p.name.casefold() == name.casefold() for p in self.players.values()):
            ending = f" {suffix}"
            name = base_name[: 16 - len(ending)] + ending
            suffix += 1

        if color is None:
            used = {p.color for p in self.players.values() if not p.is_bot}
            color = next((c for c in COLORS if c not in used), COLORS[0])
        spawn = self._choose_spawn()
        player = Player(
            id=self._next_player_id,
            name=name,
            color=color,
            x=spawn["x"],
            y=spawn["y"],
            is_bot=is_bot,
            bot_style=bot_style,
        )
        self._next_player_id += 1
        player.aim = math.atan2(ARENA_H / 2 - player.y, ARENA_W / 2 - player.x)
        player.invuln_until = self.now + 1.5
        if is_bot:
            player.next_bot_cast = self.now + random.uniform(0.8, 2.0)
        self.players[player.id] = player
        self.emit(
            {
                "e": "join",
                "id": player.id,
                "name": player.name,
                "color": player.color,
                "bot": player.is_bot,
                "x": round(player.x, 1),
                "y": round(player.y, 1),
            }
        )
        return player

    def remove_player(self, player_id: int) -> None:
        player = self.players.pop(player_id, None)
        if player is None:
            return
        self.projectiles = [p for p in self.projectiles if p.owner != player_id]
        self.wards = [w for w in self.wards if w.owner != player_id]
        self.emps = [e for e in self.emps if e.owner != player_id]
        self.meteors = [m for m in self.meteors if m.owner != player_id]
        self.clouds = [c for c in self.clouds if c.owner != player_id]
        self.emit({"e": "leave", "id": player.id, "name": player.name})

    def online_counts(self) -> dict[str, int]:
        humans = sum(1 for player in self.players.values() if not player.is_bot)
        bots = sum(1 for player in self.players.values() if player.is_bot)
        return {"humans": humans, "bots": bots, "online": humans + bots}

    # ------------------------------------------------------------------ input
    def set_input(
        self,
        player_id: int,
        *,
        up: bool,
        down: bool,
        left: bool,
        right: bool,
        aim: float | None = None,
    ) -> None:
        player = self.players.get(player_id)
        if player is None or player.dead:
            return
        player.input.up = bool(up)
        player.input.down = bool(down)
        player.input.left = bool(left)
        player.input.right = bool(right)
        if aim is not None and math.isfinite(aim):
            player.aim = float(aim) % math.tau

    def roll(self, player_id: int, aim: float | None = None) -> dict[str, Any]:
        """A free, cooldown-gated dodge roll. It is not the paid dash rune."""

        player = self.players.get(player_id)
        if player is None:
            return {"ok": False, "error": "Маг не найден на арене."}
        if player.dead:
            return {"ok": False, "error": "Дождитесь возрождения."}
        if player.stun_until > self.now:
            return {"ok": False, "error": "Оглушение: перекат недоступен."}
        if aim is not None and math.isfinite(aim):
            player.aim = float(aim) % math.tau
        remaining = player.roll_ready_at - self.now
        if remaining > 0.01:
            return {
                "ok": False,
                "error": f"Перекат восстанавливается: {remaining:.1f} с.",
                "cooldown": round(remaining, 2),
            }

        movement = player.input
        dx = float(movement.right) - float(movement.left)
        dy = float(movement.down) - float(movement.up)
        if dx or dy:
            length = math.hypot(dx, dy)
            dx /= length
            dy /= length
            angle = math.atan2(dy, dx)
        else:
            angle = player.aim
        destination = self.dash_destination(player, angle, ROLL_DISTANCE)
        if destination is None:
            return {"ok": False, "error": "Перекат заблокирован препятствием."}

        start_x, start_y = player.x, player.y
        player.x, player.y = destination
        player.roll_ready_at = self.now + ROLL_COOLDOWN
        player.invuln_until = max(player.invuln_until, self.now + ROLL_INVULN)
        self.emit(
            {
                "e": "roll",
                "id": player.id,
                "x": round(start_x, 1),
                "y": round(start_y, 1),
                "x2": round(player.x, 1),
                "y2": round(player.y, 1),
                "color": player.color,
                "distance": round(ROLL_DISTANCE, 1),
                "invuln": ROLL_INVULN,
            }
        )
        return {
            "ok": True,
            "cooldown": ROLL_COOLDOWN,
            "distance": ROLL_DISTANCE,
            "invuln": ROLL_INVULN,
        }

    # -------------------------------------------------------------- spells/net
    def cast(
        self,
        player_id: int,
        code: str,
        slot: int = 0,
        aim: float | None = None,
        target_x: float | None = None,
        target_y: float | None = None,
    ) -> dict[str, Any]:
        player = self.players.get(player_id)
        if player is None:
            return {"ok": False, "error": "Маг не найден на арене."}
        if player.dead:
            return {"ok": False, "error": "Дождитесь возрождения."}
        if player.stun_until > self.now:
            return {"ok": False, "error": "Вы оглушены и не можете колдовать."}
        if not isinstance(code, str):
            return {"ok": False, "error": "Код заклинания должен быть текстом."}
        if len(code) > MAX_SOURCE_CHARS:
            return {"ok": False, "error": "Слишком длинное заклинание."}
        remaining = player.cast_ready_at - self.now
        if remaining > 0.01:
            return {
                "ok": False,
                "error": f"Гримуар перезаряжается: {remaining:.1f} с.",
                "cooldown": round(remaining, 2),
            }
        target_angle: float | None = None
        cursor_x: float | None = None
        cursor_y: float | None = None
        if target_x is not None and target_y is not None:
            try:
                target_x_value = float(target_x)
                target_y_value = float(target_y)
            except (TypeError, ValueError):
                target_x_value = math.nan
                target_y_value = math.nan
            if math.isfinite(target_x_value) and math.isfinite(target_y_value):
                cursor_x = target_x_value
                cursor_y = target_y_value
                dx = target_x_value - player.x
                dy = target_y_value - player.y
                if math.hypot(dx, dy) > 0.001:
                    target_angle = math.atan2(dy, dx) % math.tau
        if target_angle is not None:
            player.aim = target_angle
        elif aim is not None:
            try:
                aim_value = float(aim)
                if math.isfinite(aim_value):
                    player.aim = aim_value % math.tau
            except (TypeError, ValueError):
                pass

        player.cast_ready_at = self.now + CAST_LOCK
        player.last_cast_at = self.now
        session = SpellSession(
            self,
            player,
            self.now,
            cursor_x=cursor_x,
            cursor_y=cursor_y,
        )
        globals_ = session.globals()
        error: str | None = None
        try:
            execute_spell(code, globals_)
        except SpellError as exc:
            error = str(exc)
        except Exception:
            error = "Внутренняя ошибка гримуара."
        return {
            "ok": error is None,
            "error": error,
            "log": session.logs,
            "actions": session.actions,
            "slot": int(slot) if isinstance(slot, int) else 0,
            "cooldown": CAST_LOCK,
        }

    def spawn_projectile(
        self,
        *,
        owner: Player,
        kind: str,
        x: float,
        y: float,
        angle: float,
        speed: float,
        damage: float,
        radius: float,
        life: float,
        color: str,
        slow_until: float = 0.0,
    ) -> None:
        self.projectiles.append(
            Projectile(
                id=self._next_projectile_id,
                owner=owner.id,
                kind=kind,
                x=x,
                y=y,
                angle=angle,
                speed=speed,
                damage=damage,
                radius=radius,
                life=life,
                color=color,
                slow_until=slow_until if slow_until > self.now else 0.0,
            )
        )
        self._next_projectile_id += 1

    def place_emp(self, owner: Player, x: float, y: float) -> None:
        self.emps.append(
            Emp(
                id=self._next_emp_id,
                owner=owner.id,
                x=x,
                y=y,
                detonate_at=self.now + EMP_DELAY,
                pull_at=self.now + EMP_DELAY - EMP_PULL_LEAD,
            )
        )
        self._next_emp_id += 1
        self.emit(
            {
                "e": "emp",
                "id": owner.id,
                "x": round(x, 1),
                "y": round(y, 1),
                "radius": EMP_RADIUS,
                "delay": EMP_DELAY,
                "pull_delay": EMP_PULL_LEAD,
                "color": EMP_COLOR,
            }
        )

    def place_ward(self, owner: Player, x: float, y: float) -> None:
        self.wards.append(
            Ward(
                id=self._next_ward_id,
                owner=owner.id,
                x=x,
                y=y,
                armed_at=self.now + 0.7,
                expires_at=self.now + 14.0,
            )
        )
        self._next_ward_id += 1
        self.emit(
            {
                "e": "ward",
                "id": owner.id,
                "x": round(x, 1),
                "y": round(y, 1),
                "color": owner.color,
            }
        )

    def place_meteor(
        self,
        owner: Player,
        x: float,
        y: float,
        radius: float,
        *,
        damage: float = METEOR_DAMAGE,
        push: float = METEOR_PUSH,
        role: str = "main",
        variant: int = 0,
        announce: bool = True,
    ) -> Meteor:
        meteor = Meteor(
            id=self._next_meteor_id,
            owner=owner.id,
            x=x,
            y=y,
            impact_at=self.now + METEOR_DELAY,
            radius=radius,
            damage=damage,
            push=push,
            role=role,
            variant=variant,
        )
        self.meteors.append(meteor)
        self._next_meteor_id += 1
        if announce:
            self.emit(
                {
                    "e": "meteor",
                    "id": owner.id,
                    "x": round(x, 1),
                    "y": round(y, 1),
                    "radius": round(radius, 1),
                    "delay": METEOR_DELAY,
                    "count": 1,
                    "color": METEOR_COLOR,
                }
            )
        return meteor

    def place_meteor_volley(
        self, owner: Player, x: float, y: float, radius: float
    ) -> None:
        """Drop a small cluster of meteors around the chosen point.

        The damage is split between the rocks, so a target that is hit by the
        whole cluster takes the same total damage as the old single meteor.
        Satellites do not push; the main rock applies the knockback.
        """

        spread = radius * 0.22
        low_x = BORDER + 8
        high_x = ARENA_W - BORDER - 8
        low_y = BORDER + 8
        high_y = ARENA_H - BORDER - 8
        rocks = (
            (-spread, spread * 0.55, 1),
            (spread * 0.9, -spread * 0.5, 2),
            (0.0, 0.0, 0),
        )
        for offset_x, offset_y, variant in rocks:
            rock_x = max(low_x, min(high_x, x + offset_x))
            rock_y = max(low_y, min(high_y, y + offset_y))
            self.place_meteor(
                owner,
                rock_x,
                rock_y,
                radius,
                damage=METEOR_DAMAGE / METEOR_COUNT,
                push=0.0 if variant else METEOR_PUSH,
                role="satellite" if variant else "main",
                variant=variant,
                announce=False,
            )
        self.emit(
            {
                "e": "meteor",
                "id": owner.id,
                "x": round(x, 1),
                "y": round(y, 1),
                "radius": round(radius, 1),
                "delay": METEOR_DELAY,
                "count": METEOR_COUNT,
                "color": METEOR_COLOR,
            }
        )

    def place_poison_cloud(
        self, owner: Player, x: float, y: float, radius: float
    ) -> None:
        self.clouds.append(
            PoisonCloud(
                id=self._next_cloud_id,
                owner=owner.id,
                x=x,
                y=y,
                expires_at=self.now + POISON_CLOUD_DURATION,
                next_tick=self.now + POISON_TICK,
                radius=radius,
            )
        )
        self._next_cloud_id += 1
        self.emit(
            {
                "e": "poison_cloud",
                "id": owner.id,
                "x": round(x, 1),
                "y": round(y, 1),
                "radius": round(radius, 1),
                "duration": POISON_CLOUD_DURATION,
                "color": POISON_COLOR,
            }
        )

    def emit(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    def drain_events(self) -> list[dict[str, Any]]:
        events = self.events
        self.events = []
        return events

    # ------------------------------------------------------------------ geometry
    def can_stand(self, x: float, y: float, radius: float = PLAYER_RADIUS) -> bool:
        if not (
            BORDER + radius <= x <= ARENA_W - BORDER - radius
            and BORDER + radius <= y <= ARENA_H - BORDER - radius
        ):
            return False
        for obstacle in OBSTACLES:
            if math.hypot(x - obstacle["x"], y - obstacle["y"]) < obstacle["r"] + radius:
                return False
        return True

    def dash_destination(
        self, player: Player, angle: float, distance: float
    ) -> tuple[float, float] | None:
        step = 8.0
        travelled = 0.0
        x, y = player.x, player.y
        dx = math.cos(angle)
        dy = math.sin(angle)
        while travelled < distance:
            advance = min(step, distance - travelled)
            nx = x + dx * advance
            ny = y + dy * advance
            if not self.can_stand(nx, ny):
                break
            x, y = nx, ny
            travelled += advance
        if travelled < 40.0:
            return None
        return (x, y)

    def try_move(self, player: Player, dx: float, dy: float) -> None:
        if dx:
            nx = max(BORDER + PLAYER_RADIUS, min(ARENA_W - BORDER - PLAYER_RADIUS, player.x + dx))
            if self.can_stand(nx, player.y):
                player.x = nx
        if dy:
            ny = max(BORDER + PLAYER_RADIUS, min(ARENA_H - BORDER - PLAYER_RADIUS, player.y + dy))
            if self.can_stand(player.x, ny):
                player.y = ny

    def displace(self, player: Player, from_x: float, from_y: float, amount: float) -> None:
        angle = math.atan2(player.y - from_y, player.x - from_x)
        if not math.isfinite(angle):
            return
        self.try_move(player, math.cos(angle) * amount, math.sin(angle) * amount)

    def _choose_spawn(self) -> dict[str, float]:
        players = [p for p in self.players.values() if not p.dead]
        if not players:
            spawn = random.choice(SPAWNS)
            return {"x": float(spawn["x"]), "y": float(spawn["y"])}
        scored: list[tuple[float, dict[str, float]]] = []
        for spawn in SPAWNS:
            closest = min(
                math.hypot(spawn["x"] - p.x, spawn["y"] - p.y) for p in players
            )
            scored.append((closest, spawn))
        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[:2]
        chosen = random.choice(top)[1]
        return {"x": float(chosen["x"]), "y": float(chosen["y"])}

    # ------------------------------------------------------------------- ticks
    def update(self, now: float) -> None:
        if now <= 0:
            now = self.now + 1 / TICK_RATE
        dt = min(0.08, max(0.0, now - self._last_tick)) if self._last_tick else 1 / TICK_RATE
        self.now = now
        self._last_tick = now

        self._update_statuses(dt)
        self._update_bots(now)
        self._move_players(dt)
        self._separate_players()
        self._update_projectiles(dt)
        self._update_emps()
        self._update_wards()
        self._update_meteors()
        self._update_clouds()
        self._remove_expired()
        self._sync_bot_roster()

    def _update_statuses(self, dt: float) -> None:
        for player in self.players.values():
            if player.dead:
                if self.now >= player.respawn_at:
                    self._respawn(player)
                continue
            player.mana = min(MAX_MANA, player.mana + MANA_REGEN * dt)
            if self.now - player.last_damage_at > 7.0:
                player.hp = min(MAX_HP, player.hp + 1.4 * dt)
            if player.shield_until and self.now >= player.shield_until:
                player.shield = 0.0
                player.shield_until = 0.0
            if player.slow_until and self.now >= player.slow_until:
                player.slow_until = 0.0
            if player.stun_until and self.now >= player.stun_until:
                player.stun_until = 0.0

    def _update_bots(self, now: float) -> None:
        for bot in self.players.values():
            if not bot.is_bot or bot.dead:
                continue
            if bot.stun_until > self.now:
                bot.input = Input()
                continue
            enemies = [
                p for p in self.players.values() if p.id != bot.id and not p.dead
            ]
            if not enemies:
                bot.input = Input()
                continue
            enemies.sort(
                key=lambda p: (p.x - bot.x) ** 2 + (p.y - bot.y) ** 2
            )
            target = enemies[0]
            distance = math.hypot(target.x - bot.x, target.y - bot.y)
            angle = math.atan2(target.y - bot.y, target.x - bot.x)
            bot.aim = angle

            desired = 295.0
            forward = 0.0
            strafe = 0.0
            if distance > desired + 95:
                forward = 1.0
            elif distance < desired - 110:
                forward = -1.0
            strafe = 0.65 if (bot.id % 2 == 0) else -0.65
            dx = math.cos(angle) * forward + math.cos(angle + math.pi / 2) * strafe
            dy = math.sin(angle) * forward + math.sin(angle + math.pi / 2) * strafe
            length = math.hypot(dx, dy) or 1.0
            dx, dy = dx / length, dy / length
            # Avoid running straight into architecture.
            probe_x = bot.x + dx * 56
            probe_y = bot.y + dy * 56
            if not self.can_stand(probe_x, probe_y):
                side = 1 if bot.id % 2 == 0 else -1
                dx = math.cos(angle + side * math.pi / 2)
                dy = math.sin(angle + side * math.pi / 2)
            bot.input.left = dx < -0.3
            bot.input.right = dx > 0.3
            bot.input.up = dy < -0.3
            bot.input.down = dy > 0.3

            if now >= bot.next_bot_cast and distance < 720:
                profile = next(
                    (p for p in BOT_PROFILES if p["style"] == bot.bot_style),
                    BOT_PROFILES[0],
                )
                low, high = profile["interval"]
                bot.next_bot_cast = now + random.uniform(low, high)
                if random.random() < 0.88:
                    self.cast(bot.id, BOT_SPELLS[bot.bot_style], 0, bot.aim)

    def _move_players(self, dt: float) -> None:
        for player in self.players.values():
            if player.dead:
                continue
            if player.stun_until > self.now:
                continue
            speed = MOVE_SPEED
            if player.slow_until > self.now:
                speed *= 0.58
            movement = player.input
            dx = float(movement.right) - float(movement.left)
            dy = float(movement.down) - float(movement.up)
            if dx or dy:
                length = math.hypot(dx, dy)
                dx /= length
                dy /= length
            self.try_move(player, dx * speed * dt, dy * speed * dt)
            if player.shield and player.shield_until <= self.now:
                player.shield = 0.0

    def _separate_players(self) -> None:
        players = [p for p in self.players.values() if not p.dead]
        for index, first in enumerate(players):
            for second in players[index + 1 :]:
                dx = second.x - first.x
                dy = second.y - first.y
                distance = math.hypot(dx, dy)
                min_distance = PLAYER_RADIUS * 2
                if 0.001 < distance < min_distance:
                    push = (min_distance - distance) / 2
                    nx = dx / distance
                    ny = dy / distance
                    self.try_move(first, -nx * push, -ny * push)
                    self.try_move(second, nx * push, ny * push)

    def _update_projectiles(self, dt: float) -> None:
        alive: list[Projectile] = []
        for projectile in self.projectiles:
            projectile.life -= dt
            if projectile.life <= 0:
                continue
            old_x, old_y = projectile.x, projectile.y
            new_x = old_x + math.cos(projectile.angle) * projectile.speed * dt
            new_y = old_y + math.sin(projectile.angle) * projectile.speed * dt

            hit_obstacle = any(
                _segment_circle_distance(
                    old_x, old_y, new_x, new_y, obstacle["x"], obstacle["y"]
                )
                <= obstacle["r"] + projectile.radius
                for obstacle in OBSTACLES
            )
            if (
                new_x < BORDER + 10
                or new_x > ARENA_W - BORDER - 10
                or new_y < BORDER + 10
                or new_y > ARENA_H - BORDER - 10
                or hit_obstacle
            ):
                self.emit(
                    {
                        "e": "impact",
                        "kind": projectile.kind,
                        "x": round(new_x, 1),
                        "y": round(new_y, 1),
                        "color": projectile.color,
                    }
                )
                continue

            target: Player | None = None
            best_distance = 1e9
            for candidate in self.players.values():
                if candidate.id == projectile.owner or candidate.dead:
                    continue
                distance = _segment_circle_distance(
                    old_x,
                    old_y,
                    new_x,
                    new_y,
                    candidate.x,
                    candidate.y,
                )
                if distance <= PLAYER_RADIUS + projectile.radius and distance < best_distance:
                    target = candidate
                    best_distance = distance
            if target is not None:
                if target.invuln_until > self.now:
                    continue
                owner = self.players.get(projectile.owner)
                self.damage(
                    target=target,
                    amount=projectile.damage,
                    source=owner,
                    kind=projectile.kind,
                    hit_x=new_x,
                    hit_y=new_y,
                )
                if projectile.slow_until:
                    target.slow_until = max(target.slow_until, projectile.slow_until)
                self.emit(
                    {
                        "e": "impact",
                        "kind": projectile.kind,
                        "x": round(new_x, 1),
                        "y": round(new_y, 1),
                        "color": projectile.color,
                    }
                )
                continue

            projectile.x = new_x
            projectile.y = new_y
            alive.append(projectile)
        self.projectiles = alive

    def _update_emps(self) -> None:
        remaining: list[Emp] = []
        for emp in self.emps:
            if not emp.pulled and self.now >= emp.pull_at:
                emp.pulled = True
                pull_hits = 0
                for candidate in list(self.players.values()):
                    if candidate.id == emp.owner or candidate.dead:
                        continue
                    if candidate.invuln_until > self.now:
                        continue
                    distance = math.hypot(candidate.x - emp.x, candidate.y - emp.y)
                    if distance > emp.radius:
                        continue
                    pull_hits += 1
                    if distance > 4.0:
                        pull = min(EMP_PULL_DISTANCE, distance - 4.0)
                        self.try_move(
                            candidate,
                            -((candidate.x - emp.x) / distance) * pull,
                            -((candidate.y - emp.y) / distance) * pull,
                        )
                self.emit(
                    {
                        "e": "emp_pull",
                        "id": emp.owner,
                        "x": round(emp.x, 1),
                        "y": round(emp.y, 1),
                        "radius": emp.radius,
                        "hits": pull_hits,
                        "color": EMP_COLOR,
                    }
                )

            if self.now < emp.detonate_at:
                remaining.append(emp)
                continue

            owner = self.players.get(emp.owner)
            total_drained = 0.0
            hit_count = 0
            for candidate in list(self.players.values()):
                if candidate.id == emp.owner or candidate.dead:
                    continue
                if candidate.invuln_until > self.now:
                    continue
                distance = math.hypot(candidate.x - emp.x, candidate.y - emp.y)
                if distance > emp.radius:
                    continue

                hit_count += 1
                drained = min(candidate.mana, EMP_MAX_DRAIN)
                if drained > 0.0:
                    candidate.mana = max(0.0, candidate.mana - drained)
                    total_drained += drained
                    self.damage(
                        target=candidate,
                        amount=drained * EMP_DAMAGE_PER_MANA,
                        source=owner,
                        kind="emp",
                        hit_x=candidate.x,
                        hit_y=candidate.y,
                    )

            self.emit(
                {
                    "e": "emp_blast",
                    "id": emp.owner,
                    "x": round(emp.x, 1),
                    "y": round(emp.y, 1),
                    "radius": emp.radius,
                    "drained": round(total_drained, 1),
                    "hits": hit_count,
                    "color": EMP_COLOR,
                }
            )
        self.emps = remaining

    def _update_wards(self) -> None:
        remaining: list[Ward] = []
        for ward in self.wards:
            if self.now >= ward.expires_at:
                self.emit(
                    {"e": "ward_fade", "x": round(ward.x, 1), "y": round(ward.y, 1)}
                )
                continue
            triggered = False
            if self.now >= ward.armed_at:
                for candidate in self.players.values():
                    if candidate.id == ward.owner or candidate.dead:
                        continue
                    if math.hypot(candidate.x - ward.x, candidate.y - ward.y) <= ward.trigger_radius:
                        triggered = True
                        break
            if triggered:
                owner = self.players.get(ward.owner)
                self.emit(
                    {
                        "e": "ward_blast",
                        "x": round(ward.x, 1),
                        "y": round(ward.y, 1),
                        "radius": ward.blast_radius,
                        "color": owner.color if owner else "#b596ff",
                    }
                )
                for candidate in list(self.players.values()):
                    if candidate.id == ward.owner or candidate.dead:
                        continue
                    distance = math.hypot(candidate.x - ward.x, candidate.y - ward.y)
                    if distance <= ward.blast_radius:
                        self.damage(
                            target=candidate,
                            amount=ward.damage,
                            source=owner,
                            kind="ward",
                            hit_x=candidate.x,
                            hit_y=candidate.y,
                        )
                        self.displace(candidate, ward.x, ward.y, 55.0)
                continue
            remaining.append(ward)
        self.wards = remaining

    def _update_meteors(self) -> None:
        remaining: list[Meteor] = []
        for meteor in self.meteors:
            if self.now < meteor.impact_at:
                remaining.append(meteor)
                continue
            owner = self.players.get(meteor.owner)
            hits = 0
            for candidate in list(self.players.values()):
                if candidate.id == meteor.owner or candidate.dead:
                    continue
                if math.hypot(candidate.x - meteor.x, candidate.y - meteor.y) > meteor.radius:
                    continue
                hits += 1
                self.damage(
                    target=candidate,
                    amount=meteor.damage,
                    source=owner,
                    kind="meteor",
                    hit_x=candidate.x,
                    hit_y=candidate.y,
                )
                if meteor.push > 0:
                    self.displace(candidate, meteor.x, meteor.y, meteor.push)
            self.emit(
                {
                    "e": "meteor_impact",
                    "id": meteor.owner,
                    "x": round(meteor.x, 1),
                    "y": round(meteor.y, 1),
                    "radius": round(meteor.radius, 1),
                    "hits": hits,
                    "role": meteor.role,
                    "color": METEOR_COLOR,
                }
            )
        self.meteors = remaining

    def _update_clouds(self) -> None:
        remaining: list[PoisonCloud] = []
        for cloud in self.clouds:
            if self.now >= cloud.expires_at:
                self.emit(
                    {
                        "e": "cloud_fade",
                        "x": round(cloud.x, 1),
                        "y": round(cloud.y, 1),
                        "radius": round(cloud.radius, 1),
                    }
                )
                continue
            if self.now >= cloud.next_tick:
                owner = self.players.get(cloud.owner)
                hits = 0
                for candidate in list(self.players.values()):
                    if candidate.id == cloud.owner or candidate.dead:
                        continue
                    if math.hypot(candidate.x - cloud.x, candidate.y - cloud.y) > cloud.radius:
                        continue
                    hits += 1
                    self.damage(
                        target=candidate,
                        amount=cloud.damage,
                        source=owner,
                        kind="poison",
                        hit_x=candidate.x,
                        hit_y=candidate.y,
                    )
                self.emit(
                    {
                        "e": "poison_tick",
                        "x": round(cloud.x, 1),
                        "y": round(cloud.y, 1),
                        "radius": round(cloud.radius, 1),
                        "hits": hits,
                        "color": POISON_COLOR,
                    }
                )
                cloud.next_tick += POISON_TICK
            remaining.append(cloud)
        self.clouds = remaining

    def _remove_expired(self) -> None:
        if len(self.projectiles) > 120:
            self.projectiles = self.projectiles[-120:]

    def _sync_bot_roster(self) -> None:
        current = sum(1 for player in self.players.values() if player.is_bot)
        if current < self.bots_wanted:
            for index in range(current, self.bots_wanted):
                profile = BOT_PROFILES[index % len(BOT_PROFILES)]
                self.add_player(
                    profile["name"],
                    is_bot=True,
                    color=profile["color"],
                    bot_style=profile["style"],
                )
        elif current > self.bots_wanted:
            for player in list(self.players.values()):
                if player.is_bot:
                    self.remove_player(player.id)
                    current -= 1
                    if current <= self.bots_wanted:
                        break

    # ------------------------------------------------------------------- combat
    def damage(
        self,
        *,
        target: Player,
        amount: float,
        source: Player | None,
        kind: str,
        hit_x: float,
        hit_y: float,
    ) -> float:
        if target.dead or target.invuln_until > self.now:
            return 0.0
        hp_before = target.hp
        absorbed = min(target.shield, amount)
        target.shield -= absorbed
        health_damage = max(0.0, amount - absorbed)
        target.hp = max(0.0, target.hp - health_damage)
        target.last_damage_at = self.now
        if target.shield <= 0.01:
            target.shield = 0.0
        self.emit(
            {
                "e": "hit",
                "id": target.id,
                "kind": kind,
                "x": round(hit_x, 1),
                "y": round(hit_y, 1),
                "amount": round(health_damage, 1),
                "absorbed": round(absorbed, 1),
                "color": source.color if source else "#e9d5ff",
            }
        )
        if target.hp <= 0:
            self._kill(target, source)
        return max(0.0, hp_before - target.hp)

    def _kill(self, target: Player, killer: Player | None) -> None:
        if target.dead:
            return
        target.dead = True
        target.hp = 0.0
        target.mana = 0.0
        target.shield = 0.0
        target.input = Input()
        target.deaths += 1
        target.respawn_at = self.now + RESPAWN_TIME
        if killer is not None and killer.id != target.id and not killer.dead:
            killer.score += 1
        self.emit(
            {
                "e": "death",
                "id": target.id,
                "name": target.name,
                "x": round(target.x, 1),
                "y": round(target.y, 1),
                "color": target.color,
                "killer_id": killer.id if killer else None,
                "killer": killer.name if killer else "Арена",
            }
        )

    def _respawn(self, player: Player) -> None:
        spawn = self._choose_spawn()
        player.x = spawn["x"]
        player.y = spawn["y"]
        player.last_x = player.x
        player.last_y = player.y
        player.hp = MAX_HP
        player.mana = MAX_MANA
        player.shield = 0.0
        player.shield_until = 0.0
        player.shield_ready_at = 0.0
        player.heal_ready_at = 0.0
        player.roll_ready_at = 0.0
        player.slow_until = 0.0
        player.stun_until = 0.0
        player.dead = False
        player.invuln_until = self.now + 2.0
        player.last_damage_at = -100.0
        player.input = Input()
        player.next_bot_cast = self.now + random.uniform(0.8, 1.8)
        player.aim = math.atan2(ARENA_H / 2 - player.y, ARENA_W / 2 - player.x)
        self.emit(
            {
                "e": "respawn",
                "id": player.id,
                "x": round(player.x, 1),
                "y": round(player.y, 1),
                "color": player.color,
            }
        )

    # ------------------------------------------------------------------ network
    def snapshot(self) -> dict[str, Any]:
        players = []
        for player in sorted(self.players.values(), key=lambda item: item.id):
            players.append(
                {
                    "id": player.id,
                    "name": player.name,
                    "x": round(player.x, 1),
                    "y": round(player.y, 1),
                    "aim": round(player.aim, 3),
                    "hp": round(player.hp, 1),
                    "mana": round(player.mana, 1),
                    "shield": round(player.shield, 1),
                    "score": player.score,
                    "deaths": player.deaths,
                    "color": player.color,
                    "dead": player.dead,
                    "respawn_in": round(max(0.0, player.respawn_at - self.now), 1)
                    if player.dead
                    else 0.0,
                    "bot": player.is_bot,
                    "slow": player.slow_until > self.now,
                    "stun": player.stun_until > self.now,
                    "invuln": player.invuln_until > self.now,
                    "roll_ready_in": round(max(0.0, player.roll_ready_at - self.now), 2),
                }
            )
        projectiles = [
            {
                "id": projectile.id,
                "kind": projectile.kind,
                "x": round(projectile.x, 1),
                "y": round(projectile.y, 1),
                "angle": round(projectile.angle, 3),
                "color": projectile.color,
            }
            for projectile in self.projectiles
        ]
        wards = [
            {
                "id": ward.id,
                "x": round(ward.x, 1),
                "y": round(ward.y, 1),
                "armed": ward.armed_at <= self.now,
                "ttl": round(max(0.0, ward.expires_at - self.now), 1),
            }
            for ward in self.wards
        ]
        emps = [
            {
                "id": emp.id,
                "x": round(emp.x, 1),
                "y": round(emp.y, 1),
                "radius": emp.radius,
                "ttl": round(max(0.0, emp.detonate_at - self.now), 2),
                "pull_ttl": round(max(0.0, emp.pull_at - self.now), 2),
                "delay": EMP_DELAY,
                "color": EMP_COLOR,
            }
            for emp in self.emps
        ]
        meteors = [
            {
                "id": meteor.id,
                "x": round(meteor.x, 1),
                "y": round(meteor.y, 1),
                "radius": round(meteor.radius, 1),
                "ttl": round(max(0.0, meteor.impact_at - self.now), 2),
                "delay": METEOR_DELAY,
                "role": meteor.role,
                "variant": meteor.variant,
                "color": METEOR_COLOR,
            }
            for meteor in self.meteors
        ]
        clouds = [
            {
                "id": cloud.id,
                "x": round(cloud.x, 1),
                "y": round(cloud.y, 1),
                "radius": round(cloud.radius, 1),
                "ttl": round(max(0.0, cloud.expires_at - self.now), 1),
                "color": POISON_COLOR,
            }
            for cloud in self.clouds
        ]
        counts = self.online_counts()
        return {
            "t": "state",
            "players": players,
            "projectiles": projectiles,
            "wards": wards,
            "emps": emps,
            "meteors": meteors,
            "clouds": clouds,
            "stats": counts,
        }


def _ray_arena_end(
    x: float, y: float, dx: float, dy: float, length: float
) -> tuple[float, float]:
    """Clip a ray to the playable rectangle so beams stop at the arena edge."""

    margin = BORDER + 8
    limit = length
    if dx > 1e-9:
        limit = min(limit, (ARENA_W - margin - x) / dx)
    elif dx < -1e-9:
        limit = min(limit, (margin - x) / dx)
    if dy > 1e-9:
        limit = min(limit, (ARENA_H - margin - y) / dy)
    elif dy < -1e-9:
        limit = min(limit, (margin - y) / dy)
    limit = max(0.0, limit)
    return x + dx * limit, y + dy * limit


def _segment_circle_distance(
    x1: float, y1: float, x2: float, y2: float, cx: float, cy: float
) -> float:
    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-9:
        return math.hypot(cx - x1, cy - y1)
    t = ((cx - x1) * dx + (cy - y1) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    nearest_x = x1 + t * dx
    nearest_y = y1 + t * dy
    return math.hypot(cx - nearest_x, cy - nearest_y)
