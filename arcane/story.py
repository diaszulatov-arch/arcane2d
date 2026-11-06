"""One dungeon run: the shared simulation with rooms, monsters and a way out.

``StoryArena`` is an ``Arena`` with its geometry and its idea of "enemy" swapped.
Spells, projectiles, shields and damage all stay in ``game.py``; what lives here
is what a dungeon adds on top of them.
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from .campaign import DIFFICULTIES, WAVES_PER_ROOM, Stage
from .dungeon import TILE, DungeonMap, Room, build_dungeon
from .game import (
    PLAYER_RADIUS,
    POISON_CLOUD_DURATION,
    POISON_TICK,
    Arena,
    Input,
    Player,
    PoisonCloud,
    Projectile,
    SpellSession,
    SPELL_COSTS,
)
from .lessons import GATES, LESSONS, Task, check_task, runes_for_stage
from .monsters import ATTACKS, SPECIES, Monster, Species, first_strike_delay, think
from .profiles import Perks
from .roles import ROLES, SKILL_COSTS, SKILLS, SkillBook

MONSTER_ID_BASE = 100_000
MAX_MONSTERS = 48
MINION_LIMIT = 8
PICKUP_REACH = 46.0
PICKUP_PULL = 150.0
PICKUP_HEAL = 16.0
PICKUP_MANA = 30.0
REVIVE_REACH = 96.0
REVIVE_TIME = 2.4
PORTAL_REACH = 110.0
PORTAL_HOLD = 0.8
WIPE_DELAY = 1.6
ROOM_ENTRY_INSET = 1.6
GUARD_ARC = 1.15
GUARD_BLOCK = 0.12
WEAKNESS = 1.5
DIZZY_BONUS = 1.5
HP_PER_EXTRA_MAGE = 0.18
BOSS_HP_PER_EXTRA_MAGE = 0.7
BUDGET_PER_EXTRA_MAGE = 0.55
TERMINAL_REACH = 120.0
LINK_GRACE = 1.2
LINK_SHELTER = 0.4
GATE_THRESHOLDS = (0.66, 0.33)
GATE_STAGGER = 3.5
GATE_DAMAGE = 0.06
TRICKLE_EVERY = 7.0
TRICKLE_SHARE = 0.4
ROTATION_WAIT = 30.0
BARRIER_REACH = 95.0
BARRIER_LENGTH = 280.0
BARRIER_TIME = 6.0
REFLECT_SCALE = 1.5
REFLECT_LIFE = 2.2
SUDO_TIME = 5.0
SUDO_PULL = 560.0
SUDO_COVER = 300.0
SUDO_SHARE = 0.5
MARK_TIME = 6.0
MARK_BONUS = 1.35
SEGFAULT_RADIUS = 170.0
SEGFAULT_DAMAGE = 32.0
SEGFAULT_JUMPS = 3
SEGFAULT_LEAP = 340.0
HIJACK_TIME = 7.0
AURA_REACH = 280.0
HISTORY_STEP = 0.2
HISTORY_SIZE = 16
SCAN_TIME = 6.0
BREAKPOINT_TIME = 3.2
BREAKPOINT_RADIUS = 190.0
BREAKPOINT_RANGE = 640.0
KIND_RUNES = {
    "fire": "fireball",
    "frost": "frostbolt",
    "spark": "spark_volley",
    "nova": "nova",
    "beam": "beam",
    "chain": "chain_lightning",
    "lightning": "lightning_strike",
    "siphon": "siphon",
    "ward": "ward",
    "meteor": "meteor",
    "poison": "poison_cloud",
    "emp": "emp",
}
SHOT_WIDTH = 6.0
SETTLE_RINGS = (0.0, 44.0, 88.0, 132.0)
SETTLE_SPACING = 40.0
CRIT_MULTIPLIER = 2.0
WARD_SHIELD_TIME = 8.0
CORNER_SLIP = 12.0
CORNER_NUDGE = 2.0
FLOW_REFRESH = 0.3
ROUTE_REFRESH = 0.16
RECURSION_DEPTH = 2
RECURSION_SCALE = (1.0, 0.72, 0.5)
CURSES = {"syntax": 2.5, "null": 5.0, "mirror": 4.0}
SYNTAX_ERROR = "SyntaxError: Скобка сломала ваш синтаксис, заклинания не компилируются."
DEPLOY_TIME = 6.5
DEPLOY_EVERY = 24.0
DEPLOY_FIRST = 16.0
DEPLOY_BREAK = 0.14
DEPLOY_DAMAGE = 38.0
DEPLOY_HEAL = 0.07
DEPLOY_STAGGER = 2.6


@dataclass(slots=True)
class Hazard:
    """A marked patch of floor that will hurt once its fuse runs out."""

    id: int
    owner: int
    x: float
    y: float
    radius: float
    impact_at: float
    delay: float
    damage: float
    color: str
    x2: float | None = None
    y2: float | None = None
    effect: str = ""
    label: str = ""


@dataclass(slots=True)
class Terminal:
    """A broken program out in the world. Repairing it is how the party moves on."""

    id: int
    x: float
    y: float
    task: Task
    role: str
    solved: bool = False
    free_at: float = 0.0


@dataclass(slots=True)
class Barrier:
    """A wall of light that sends hostile shots back where they came from."""

    id: int
    owner: int
    x1: float
    y1: float
    x2: float
    y2: float
    expires_at: float
    color: str


@dataclass(slots=True)
class Breakpoint:
    """A patch of the world where enemy time has stopped."""

    id: int
    x: float
    y: float
    radius: float
    expires_at: float


@dataclass(slots=True)
class Pickup:
    id: int
    kind: str
    x: float
    y: float


ALL_COSTS = {**SPELL_COSTS, **SKILL_COSTS}


def _segments_cross(
    ax: float, ay: float, bx: float, by: float, cx: float, cy: float, dx: float, dy: float
) -> bool:
    def side(px: float, py: float, qx: float, qy: float, rx: float, ry: float) -> float:
        return (qx - px) * (ry - py) - (qy - py) * (rx - px)

    return (
        side(ax, ay, bx, by, cx, cy) * side(ax, ay, bx, by, dx, dy) < 0
        and side(cx, cy, dx, dy, ax, ay) * side(cx, cy, dx, dy, bx, by) < 0
    )


class StoryArena(Arena):
    radar = True

    def __init__(
        self,
        stage: Stage,
        party_size: int,
        *,
        seed: int | None = None,
        now: float = 0.0,
        difficulty: int = 1,
    ) -> None:
        self.stage = stage
        self.difficulty = DIFFICULTIES[difficulty]
        self.party_size = max(1, party_size)
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.rng = random.Random(self.seed)
        self.dungeon: DungeonMap = build_dungeon(stage.layout, self.rng)
        self.field_w = self.dungeon.width * TILE
        self.field_h = self.dungeon.height * TILE
        self.monsters: dict[int, Monster] = {}
        self.hazards: list[Hazard] = []
        self.pickups: list[Pickup] = []
        self.known_runes = runes_for_stage(stage.index)
        self.active_room: Room | None = None
        self.cleared_rooms: set[int] = set()
        self.wave = 0
        self.next_wave_at = 0.0
        # Her copies are a surprise: the attack names them when it comes.
        self.seen_species: set[str] = {"nullecho"}
        self.essence = 0
        self.outcome: str | None = None
        self.outcome_at = 0.0
        self.portal_ready = False
        self.portal_held = 0.0
        self.boss_max_hp = 0.0
        self.flow: dict[tuple[int, int], int] = {}
        self.flow_at = 0.0
        self.terminals: list[Terminal] = []
        self.linked: dict[int, Terminal] = {}
        self.gates_left = list(GATES.get(stage.chapter.boss, ())) if stage.is_boss else []
        self.gate_boss: Monster | None = None
        self.trickle_at = 0.0
        self.last_fixer: int | None = None
        self.barriers: list[Barrier] = []
        self.breakpoints: list[Breakpoint] = []
        self.sudo: dict[int, float] = {}
        self.history: dict[int, deque[tuple[float, float, float, float]]] = {}
        self.history_at = 0.0
        self.timers: list[tuple[float, Callable[[], None]]] = []
        self.told_attacks: set[str] = set()
        self.deploy_at = math.inf
        self._next_effect_id = 1
        self._next_monster_id = MONSTER_ID_BASE
        self._next_hazard_id = 1
        self._next_pickup_id = 1
        super().__init__(bots=0)
        self.now = now
        self.portal = self.dungeon.rooms[-1].center
        self._place_stage_terminal()

    # ------------------------------------------------------------- engine hooks
    def targets_for(self, owner_id: int) -> list[Player]:
        now = self.now
        if owner_id >= MONSTER_ID_BASE:
            owner = self.monsters.get(owner_id)
            hostile = [m for m in self.monsters.values() if not m.dead and m is not owner]
            if owner is not None and owner.hacked_until > now:
                return [m for m in hostile if m.hacked_until <= now]
            mages: list[Player] = [p for p in self.players.values() if not p.dead]
            return mages + [m for m in hostile if m.hacked_until > now]
        return [
            monster
            for monster in self.monsters.values()
            if not monster.dead and monster.spawned_at <= now and monster.hacked_until <= now
        ]

    def describe_target(self, target: Player) -> tuple[str, bool]:
        return target.species.key, target.species.boss

    def actor(self, actor_id: int) -> Player | None:
        if actor_id >= MONSTER_ID_BASE:
            return self.monsters.get(actor_id)
        return self.players.get(actor_id)

    def radar_jammed(self, player: Player) -> bool:
        return self.cursed(player, "null")

    def rune_known(self, name: str, player: Player | None = None) -> bool:
        skill = SKILLS.get(name)
        if skill is None:
            return name in self.known_runes
        return (
            player is not None
            and player.role == skill.role
            and self.stage.index >= skill.stage
        )

    def rune_costs(self) -> dict[str, int]:
        return ALL_COSTS

    def skill_wait(self, player: Player, name: str) -> float:
        return player.skill_ready.get(name, 0.0) - self.now

    def extra_runes(self, session: SpellSession) -> dict[str, Any]:
        return SkillBook(self, session).api()

    def shot_held(self, projectile: Projectile) -> bool:
        if not self.breakpoints or not self._hostile_shot(projectile):
            return False
        return any(
            math.hypot(projectile.x - zone.x, projectile.y - zone.y) <= zone.radius
            for zone in self.breakpoints
        )

    def shot_turned(
        self, projectile: Projectile, old_x: float, old_y: float, new_x: float, new_y: float
    ) -> bool:
        if not self.barriers or not self._hostile_shot(projectile):
            return False
        for barrier in self.barriers:
            if _segments_cross(
                old_x, old_y, new_x, new_y, barrier.x1, barrier.y1, barrier.x2, barrier.y2
            ):
                self._reflect(projectile, barrier)
                return True
        return False

    @staticmethod
    def _reflect_angle(angle: float, barrier: Barrier) -> float:
        wall = math.atan2(barrier.y2 - barrier.y1, barrier.x2 - barrier.x1)
        return (2 * wall - angle) % math.tau

    def _reflect(self, projectile: Projectile, barrier: Barrier) -> None:
        projectile.angle = self._reflect_angle(projectile.angle, barrier)
        projectile.owner = barrier.owner
        projectile.damage *= REFLECT_SCALE
        projectile.life = REFLECT_LIFE
        projectile.color = barrier.color
        projectile.slow_until = 0.0
        projectile.mana_burn = 0.0
        self.emit(
            {
                "e": "deflect",
                "x": round(projectile.x, 1),
                "y": round(projectile.y, 1),
                "color": barrier.color,
            }
        )

    def _hostile_shot(self, projectile: Projectile) -> bool:
        if projectile.owner < MONSTER_ID_BASE:
            return False
        owner = self.monsters.get(projectile.owner)
        return owner is None or owner.hacked_until <= self.now

    def inside_field(self, x: float, y: float) -> bool:
        return not self.dungeon.blocked(x, y, 8.0)

    def can_stand(self, x: float, y: float, radius: float = PLAYER_RADIUS) -> bool:
        return not self.dungeon.blocked(x, y, radius)

    def can_blink(self, player: Player, x: float, y: float) -> bool:
        return self.can_stand(x, y) and self.dungeon.path_clear(player.x, player.y, x, y)

    def ray_end(
        self, x: float, y: float, dx: float, dy: float, length: float
    ) -> tuple[float, float]:
        return self.dungeon.ray_end(x, y, dx, dy, length)

    def shot_blocked(
        self, old_x: float, old_y: float, new_x: float, new_y: float, radius: float
    ) -> bool:
        return not self.dungeon.path_clear(old_x, old_y, new_x, new_y, min(radius, SHOT_WIDTH))

    def try_move(self, player: Player, dx: float, dy: float) -> None:
        start_x, start_y = player.x, player.y
        super().try_move(player, dx, dy)
        if dx and player.x == start_x:
            self._slip_past_corner(player, dx, 0.0)
        if dy and player.y == start_y:
            self._slip_past_corner(player, 0.0, dy)

    def _slip_past_corner(self, player: Player, dx: float, dy: float) -> None:
        """Ease a mage around a corner they only just clipped, like a doorway edge."""

        for side in (-1.0, 1.0):
            shift_x = side * CORNER_SLIP if dy else 0.0
            shift_y = side * CORNER_SLIP if dx else 0.0
            if self.can_stand(player.x + dx + shift_x, player.y + dy + shift_y, player.radius):
                player.x += math.copysign(CORNER_NUDGE, shift_x) if shift_x else 0.0
                player.y += math.copysign(CORNER_NUDGE, shift_y) if shift_y else 0.0
                return

    def _clamp_x(self, x: float, radius: float) -> float:
        return x

    def _clamp_y(self, y: float, radius: float) -> float:
        return y

    def _choose_spawn(self) -> dict[str, float]:
        anchor = next(
            (player for player in self.players.values() if not player.dead), None
        )
        if anchor is not None:
            return {"x": anchor.x, "y": anchor.y}
        x, y = self.dungeon.rooms[0].center
        return {"x": x, "y": y}

    def _tick_dead(self, player: Player) -> None:
        """Nobody comes back on a timer here: it takes a friend or a cleared room."""

    def _separate_players(self) -> None:
        super()._separate_players()
        monsters = [monster for monster in self.monsters.values() if not monster.species.heavy]
        for index, first in enumerate(monsters):
            for second in monsters[index + 1 :]:
                dx = second.x - first.x
                dy = second.y - first.y
                distance = math.hypot(dx, dy)
                reach = first.radius + second.radius
                if 0.001 < distance < reach:
                    push = (reach - distance) / 4
                    self.try_move(first, -dx / distance * push, -dy / distance * push)
                    self.try_move(second, dx / distance * push, dy / distance * push)

    def add_player(self, name: str, **kwargs: Any) -> Player:
        player = super().add_player(name, **kwargs)
        player.perks = Perks()
        anchor = self.dungeon.rooms[0].center if self.active_room is None else self.active_room.center
        if len(self.players) == 1:
            player.x, player.y = anchor
        self._settle(player)
        return player

    def _settle(self, player: Player) -> None:
        """Find a free spot near here: never a wall, never on top of a friend."""

        others = [other for other in self.players.values() if other is not player]
        for ring in SETTLE_RINGS:
            for step in range(8):
                angle = step / 8 * math.tau
                x = player.x + math.cos(angle) * ring
                y = player.y + math.sin(angle) * ring
                if self.can_stand(x, y, player.radius) and all(
                    math.hypot(other.x - x, other.y - y) >= SETTLE_SPACING
                    for other in others
                ):
                    player.x, player.y = x, y
                    return

    # ------------------------------------------------------------------ damage
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
        if isinstance(target, Monster):
            if target.invuln_until <= self.now:
                amount = self._boosted_damage(target, amount, source, hit_x, hit_y)
                amount = self._shaped_damage(target, amount, source, kind, hit_x, hit_y)
                if amount <= 0:
                    return 0.0
        else:
            amount *= (1 - target.perks.armor) * self.difficulty.damage
            if self._covered_by_sudo(target):
                amount *= SUDO_SHARE
        return super().damage(
            target=target, amount=amount, source=source, kind=kind, hit_x=hit_x, hit_y=hit_y
        )

    def _boosted_damage(
        self, monster: Monster, amount: float, source: Player | None, hit_x: float, hit_y: float
    ) -> float:
        perks = getattr(source, "perks", None)
        if perks is None:
            return amount
        amount *= perks.power
        if perks.crit and self.rng.random() < perks.crit:
            amount *= CRIT_MULTIPLIER
            self.emit({"e": "crit", "id": monster.id, "x": round(hit_x, 1), "y": round(hit_y, 1)})
        return amount

    def _shaped_damage(
        self,
        monster: Monster,
        amount: float,
        source: Player | None,
        kind: str,
        hit_x: float,
        hit_y: float,
    ) -> float:
        species = monster.species
        perks = getattr(source, "perks", None)
        exposed = monster.exposed_until > self.now
        if kind in species.immune and not exposed:
            self.emit({"e": "resist", "id": monster.id, "x": hit_x, "y": hit_y, "text": "иммунитет"})
            return 0.0
        pierces = exposed or (perks is not None and perks.pierce_guard)
        if species.guard and not pierces and (hit_x, hit_y) != (monster.x, monster.y):
            from_hit = math.atan2(hit_y - monster.y, hit_x - monster.x)
            facing = (from_hit - monster.heading + math.pi) % math.tau - math.pi
            if abs(facing) < GUARD_ARC:
                self.emit({"e": "resist", "id": monster.id, "x": hit_x, "y": hit_y, "text": "щит"})
                amount *= GUARD_BLOCK
        if kind in species.weak:
            amount *= WEAKNESS * (perks.weak_scale if perks is not None else 1.0)
        if monster.dizzy_until > self.now:
            amount *= DIZZY_BONUS
        if monster.marked_until > self.now:
            amount *= MARK_BONUS
        return amount

    def _kill(self, target: Player, killer: Player | None, kind: str = "") -> None:
        if not isinstance(target, Monster):
            super()._kill(target, killer, kind)
            target.revive = 0.0
            target.curses.clear()
            self.linked.pop(target.id, None)
            return
        if target.dead:
            return
        target.dead = True
        target.hp = 0.0
        self.monsters.pop(target.id, None)
        species = target.species
        # A leak pays nothing, or an unpatched terminal would be a farm.
        if not target.leaked:
            self.essence += max(1, round(species.cost))
        if killer is not None:
            killer.score += 1
            perks = killer.perks
            if perks is not None and perks.kill_mana and not killer.dead:
                killer.mana = min(killer.max_mana, killer.mana + perks.kill_mana)
        self.emit(
            {
                "e": "monster_death",
                "id": target.id,
                "x": round(target.x, 1),
                "y": round(target.y, 1),
                "color": species.color,
                "boss": species.boss,
            }
        )
        self._drop_pickup(target)
        if target.marked_until > self.now:
            self._segfault(target)
        if species.on_death == "cloud":
            self.drop_cloud(target, target.x, target.y, 96)
        elif species.on_death == "split" and target.generation == 0:
            for _ in range(2):
                self.spawn_near(target, species.key, 40, generation=1, scale=0.55)
        elif species.on_death == "recurse" and target.generation < RECURSION_DEPTH:
            for _ in range(2):
                self.spawn_near(
                    target,
                    species.key,
                    90,
                    generation=target.generation + 1,
                    scale=RECURSION_SCALE[target.generation + 1],
                )

    def _drop_pickup(self, monster: Monster) -> None:
        roll = self.rng.random()
        if roll < 0.14:
            self._add_pickup("hp", monster.x, monster.y)
        elif roll < 0.34:
            self._add_pickup("mana", monster.x, monster.y)

    def _add_pickup(self, kind: str, x: float, y: float) -> None:
        self.pickups.append(Pickup(self._next_pickup_id, kind, x, y))
        self._next_pickup_id += 1

    # -------------------------------------------------- verbs monsters can use
    def spawn_monster(
        self,
        key: str,
        x: float,
        y: float,
        *,
        generation: int = 0,
        scale: float = 1.0,
        minion: bool = False,
    ) -> Monster | None:
        if len(self.monsters) >= MAX_MONSTERS:
            return None
        species = SPECIES[key]
        per_mage = BOSS_HP_PER_EXTRA_MAGE if species.boss else HP_PER_EXTRA_MAGE
        hp = species.hp * scale * (1 + per_mage * (self.party_size - 1)) * self.difficulty.toughness
        monster = Monster(
            id=self._next_monster_id,
            name=species.title,
            color=species.color,
            x=x,
            y=y,
            hp=hp,
            max_hp=hp,
            radius=species.radius * math.sqrt(scale),
            species=species,
            generation=generation,
            minion=minion,
            origin=self.active_room.center if self.active_room else (x, y),
        )
        self._next_monster_id += 1
        monster.spawned_at = self.now + 0.55
        monster.next_attack = self.now + first_strike_delay(species, self.rng)
        monster.next_special = self.now + 6.0
        self.monsters[monster.id] = monster
        if species.boss and generation == 0:
            self.boss_max_hp = self._expected_boss_hp(species, hp)
            if species.on_death == "recurse":
                self.deploy_at = self.now + DEPLOY_FIRST
        self.emit(
            {
                "e": "monster_spawn",
                "id": monster.id,
                "x": round(x, 1),
                "y": round(y, 1),
                "color": species.color,
            }
        )
        if key not in self.seen_species:
            self.seen_species.add(key)
            self.emit({"e": "intro", "kind": key})
        return monster

    @staticmethod
    def _expected_boss_hp(species: Species, hp: float) -> float:
        if species.on_death != "recurse":
            return hp
        return sum(hp * RECURSION_SCALE[depth] * 2**depth for depth in range(RECURSION_DEPTH + 1))

    def spawn_near(
        self,
        monster: Monster,
        key: str,
        distance: float,
        *,
        generation: int = 0,
        scale: float = 1.0,
    ) -> Monster | None:
        species = SPECIES[key]
        for _ in range(14):
            angle = self.rng.random() * math.tau
            x = monster.x + math.cos(angle) * distance
            y = monster.y + math.sin(angle) * distance
            if self.can_stand(x, y, species.radius):
                child = self.spawn_monster(
                    key, x, y, generation=generation, scale=scale,
                    minion=generation == 0,
                )
                if child is not None:
                    # A hacked process forks hacked children.
                    child.hacked_until = monster.hacked_until
                    child.hacked_by = monster.hacked_by
                return child
        return None

    def minion_count(self) -> int:
        return sum(1 for monster in self.monsters.values() if monster.minion)

    def minion_limit(self) -> int:
        return MINION_LIMIT + 2 * (self.party_size - 1)

    def fire(self, monster: Monster, angle: float) -> None:
        self.fire_from(
            monster,
            monster.x + math.cos(angle) * (monster.radius + 8),
            monster.y + math.sin(angle) * (monster.radius + 8),
            angle,
        )

    def fire_from(
        self,
        monster: Monster,
        x: float,
        y: float,
        angle: float,
        *,
        speed: float | None = None,
        life: float = 2.6,
    ) -> None:
        """A monster's shot from anywhere: bosses can open fire from across a room."""

        if self.dungeon.blocked(x, y, 8.0):
            return
        species = monster.species
        self.projectiles.append(
            Projectile(
                id=self._next_projectile_id,
                owner=monster.id,
                kind="orb",
                x=x,
                y=y,
                angle=angle,
                speed=speed or species.shot_speed,
                damage=species.shot_damage,
                radius=7.0,
                life=life,
                color=species.color,
                slow_until=self.now + 1.5 if species.slows else 0.0,
                mana_burn=species.mana_burn,
            )
        )
        self._next_projectile_id += 1

    def place_hazard(
        self,
        monster: Monster,
        x: float,
        y: float,
        *,
        radius: float,
        delay: float,
        damage: float,
        color: str,
        effect: str = "",
        label: str = "",
    ) -> None:
        self._add_hazard(
            Hazard(
                self._next_hazard_id, monster.id, x, y, radius, self.now + delay, delay, damage,
                color, effect=effect, label=label,
            )
        )

    def place_beam_hazard(
        self,
        monster: Monster,
        x: float,
        y: float,
        x2: float,
        y2: float,
        *,
        width: float,
        delay: float,
        damage: float,
        color: str,
        effect: str = "",
    ) -> None:
        self._add_hazard(
            Hazard(
                self._next_hazard_id, monster.id, x, y, width, self.now + delay, delay, damage,
                color, x2, y2, effect,
            )
        )

    def _add_hazard(self, hazard: Hazard) -> None:
        self.hazards.append(hazard)
        self._next_hazard_id += 1

    # --------------------------------------------------------- boss tricks
    def hunted(self) -> list[Player]:
        """Mages out on the field: dead ones and those in a terminal do not count."""

        return [
            player
            for player in self.players.values()
            if not player.dead and player.id not in self.linked
        ]

    def room_box(self) -> tuple[float, float, float, float]:
        """The walkable floor of the fight: left, top, right, bottom."""

        room = self.active_room or self.dungeon.rooms[-1]
        return (
            (room.x + 1) * TILE,
            (room.y + 1) * TILE,
            (room.x + room.w - 1) * TILE,
            (room.y + room.h - 1) * TILE,
        )

    def after(self, delay: float, action: Callable[[], None]) -> None:
        self.timers.append((self.now + delay, action))

    def _update_timers(self, now: float) -> None:
        due = [action for at, action in self.timers if at <= now]
        self.timers = [(at, action) for at, action in self.timers if at > now]
        for action in due:
            action()

    def announce(self, monster: Monster, key: str) -> None:
        """Name the attack out loud: the banner shows the real Python error behind it.

        The first time, Ada explains how to survive it, unless the party chose to
        play without hints.
        """

        attack = ATTACKS[key]
        first = key not in self.told_attacks
        self.told_attacks.add(key)
        self.emit(
            {
                "e": "boss_cast",
                "id": monster.id,
                "x": round(monster.x, 1),
                "y": round(monster.y, 1),
                "color": monster.color,
                "error": attack.error,
                "tip": attack.tip if first and self.difficulty.hints else "",
            }
        )

    def cursed(self, player: Player, kind: str) -> bool:
        return player.curses.get(kind, 0.0) > self.now

    def curse(self, player: Player, kind: str) -> None:
        player.curses[kind] = self.now + CURSES[kind]
        self.emit(
            {
                "e": "curse",
                "id": player.id,
                "x": round(player.x, 1),
                "y": round(player.y, 1),
                "kind": kind,
            }
        )

    def _update_curses(self, now: float) -> None:
        for player in self.players.values():
            if player.curses:
                player.curses = {kind: at for kind, at in player.curses.items() if at > now}

    def recall(self, mage: Player, x: float, y: float) -> None:
        """The loop body starts over: back to where this mage stood before."""

        if mage.dead or mage.id in self.linked or mage.id not in self.players:
            return
        self.emit(
            {
                "e": "recall",
                "id": mage.id,
                "from_x": round(mage.x, 1),
                "from_y": round(mage.y, 1),
                "x": round(x, 1),
                "y": round(y, 1),
            }
        )
        mage.x, mage.y = x, y

    def swap_places(self, first: Player, second: Player) -> bool:
        """Exchange two bodies, if both still fit where they are going."""

        for body in (first, second):
            if body.dead or (body.id in self.linked):
                return False
            if isinstance(body, Monster):
                if body.id not in self.monsters:
                    return False
            elif body.id not in self.players:
                return False
        if not (
            self.can_stand(first.x, first.y, second.radius)
            and self.can_stand(second.x, second.y, first.radius)
        ):
            return False
        self.emit(
            {
                "e": "swap",
                "x1": round(first.x, 1),
                "y1": round(first.y, 1),
                "x2": round(second.x, 1),
                "y2": round(second.y, 1),
            }
        )
        first.x, first.y, second.x, second.y = second.x, second.y, first.x, first.y
        return True

    def remove_monster(self, monster: Monster) -> None:
        """Take a monster off the field with no reward and no death rattle."""

        self.monsters.pop(monster.id, None)
        monster.dead = True
        self.emit(
            {
                "e": "monster_death",
                "id": monster.id,
                "x": round(monster.x, 1),
                "y": round(monster.y, 1),
                "color": monster.color,
                "boss": False,
            }
        )

    def start_deploy(self, monster: Monster) -> None:
        """PGT ships to production: enough damage breaks the build, or it lands."""

        monster.state = "deploy"
        monster.state_until = self.now + DEPLOY_TIME
        monster.deploy_hp = monster.hp
        self.deploy_at = self.now + DEPLOY_EVERY * self.difficulty.tempo + DEPLOY_TIME
        self.announce(monster, "deploy")

    def deploy_step(self, monster: Monster) -> bool:
        """Advance a running deploy. Returns whether the monster is still busy with it."""

        if monster.deploy_hp - monster.hp >= monster.max_hp * DEPLOY_BREAK:
            monster.state = "idle"
            monster.stun_until = self.now + DEPLOY_STAGGER
            monster.dizzy_until = self.now + DEPLOY_STAGGER
            self.emit(
                {"e": "deploy_broken", "x": round(monster.x, 1), "y": round(monster.y, 1)}
            )
            return False
        if self.now < monster.state_until:
            return True
        monster.state = "idle"
        monster.hp = min(monster.max_hp, monster.hp + monster.max_hp * DEPLOY_HEAL)
        self.emit({"e": "deploy_blast", "x": round(monster.x, 1), "y": round(monster.y, 1)})
        for mage in self.hunted():
            self.damage(
                target=mage,
                amount=DEPLOY_DAMAGE,
                source=monster,
                kind="deploy",
                hit_x=mage.x,
                hit_y=mage.y,
            )
        return False

    def _deploy_report(self) -> dict[str, Any] | None:
        for monster in self.monsters.values():
            if monster.state == "deploy":
                goal = monster.max_hp * DEPLOY_BREAK
                return {
                    "left": round(max(0.0, monster.state_until - self.now) / DEPLOY_TIME, 3),
                    "broken": round(min(1.0, (monster.deploy_hp - monster.hp) / goal), 3),
                }
        return None

    def drop_cloud(self, monster: Monster, x: float, y: float, radius: float) -> None:
        self.clouds.append(
            PoisonCloud(
                id=self._next_cloud_id,
                owner=monster.id,
                x=x,
                y=y,
                expires_at=self.now + POISON_CLOUD_DURATION,
                next_tick=self.now + POISON_TICK,
                radius=radius,
                damage=5.0,
            )
        )
        self._next_cloud_id += 1

    def blink_near(self, monster: Monster, target: Player, distance: float) -> None:
        for _ in range(12):
            angle = self.rng.random() * math.tau
            x = target.x + math.cos(angle) * distance
            y = target.y + math.sin(angle) * distance
            if self.can_stand(x, y, monster.radius):
                self.emit(
                    {
                        "e": "dash",
                        "id": monster.id,
                        "kind": "blink",
                        "from_x": round(monster.x, 1),
                        "from_y": round(monster.y, 1),
                        "to_x": round(x, 1),
                        "to_y": round(y, 1),
                        "color": monster.color,
                    }
                )
                monster.x, monster.y = x, y
                return

    def most_hurt_ally(self, monster: Monster, reach: float) -> Monster | None:
        patients = [
            ally
            for ally in self.monsters.values()
            if ally.id != monster.id
            and ally.hp < ally.max_hp
            and not ally.species.boss
            and ally.hacked_until <= self.now
            and monster.hacked_until <= self.now
            and math.hypot(ally.x - monster.x, ally.y - monster.y) <= reach
        ]
        return min(patients, key=lambda ally: ally.hp / ally.max_hp, default=None)

    def mend(self, monster: Monster, patient: Monster, amount: float) -> None:
        healed = min(amount, patient.max_hp - patient.hp)
        patient.hp += healed
        self.emit(
            {
                "e": "heal",
                "id": patient.id,
                "x": round(patient.x, 1),
                "y": round(patient.y, 1),
                "amount": round(healed, 1),
            }
        )

    # --------------------------------------------------------------- terminals
    def _place_stage_terminal(self) -> None:
        """Every stage holds its lesson's repair where the party has to pass."""

        task = LESSONS[self.stage.index].task
        if self.stage.is_boss:
            room = self.dungeon.rooms[0]
            self.dungeon.set_closed(room.doors)
            x, y = room.center
            self._add_terminal(x, y - 60, task, "door")
        else:
            x, y = self.dungeon.rooms[-1].center
            self._add_terminal(x, y - 110, task, "portal")

    def _add_terminal(self, x: float, y: float, task: Task, role: str) -> Terminal:
        terminal = Terminal(len(self.terminals) + 1, x, y, task, role)
        self.terminals.append(terminal)
        return terminal

    def terminal_near(self, player: Player) -> Terminal | None:
        for terminal in self.terminals:
            if not terminal.solved and (
                math.hypot(player.x - terminal.x, player.y - terminal.y) <= TERMINAL_REACH
            ):
                return terminal
        return None

    def operator_of(self, terminal: Terminal) -> Player | None:
        for player_id, held in self.linked.items():
            if held is terminal:
                return self.players.get(player_id)
        return None

    def _turn_wait(self, player: Player, terminal: Terminal) -> float:
        """Seconds this mage must leave the keyboard to someone else, or none.

        Whoever fixed the last terminal sits out the next one, so the best coder
        cannot do all the learning.  If nobody else comes, the clock lets them in.
        """

        if player.id != self.last_fixer:
            return 0.0
        if not any(p is not player and not p.dead for p in self.players.values()):
            return 0.0
        if not terminal.free_at:
            terminal.free_at = self.now + ROTATION_WAIT
        return terminal.free_at - self.now

    def link(self, player_id: int) -> tuple[Terminal | None, str | None]:
        """Plug into a nearby terminal, one mage at a time.

        Whoever is plugged in cannot be touched and monsters stop hunting them,
        which leaves everyone else to hold the line until the repair is done.
        """

        player = self.players.get(player_id)
        if player is None or player.dead:
            return None, "Павший маг не может работать с терминалом."
        terminal = self.terminal_near(player)
        if terminal is None:
            return None, "Рядом нет сломанного терминала."
        operator = self.operator_of(terminal)
        if operator is not None and operator is not player:
            return None, f"Терминал занят: {operator.name}."
        wait = self._turn_wait(player, terminal)
        if wait > 0:
            return None, (
                "Этот патч за другим магом: вы чинили прошлый. "
                f"Если никто не подойдёт, терминал откроется вам через {math.ceil(wait)} с."
            )
        self.linked[player_id] = terminal
        player.input = Input()
        return terminal, None

    def unlink(self, player_id: int) -> None:
        if self.linked.pop(player_id, None) is not None:
            player = self.players.get(player_id)
            if player is not None:
                player.invuln_until = max(player.invuln_until, self.now + LINK_GRACE)

    def remove_player(self, player_id: int) -> None:
        self.linked.pop(player_id, None)
        super().remove_player(player_id)

    def set_input(self, player_id: int, **movement: Any) -> None:
        if player_id not in self.linked:
            super().set_input(player_id, **movement)

    def roll(self, player_id: int, aim: float | None = None) -> dict[str, Any]:
        if player_id in self.linked:
            return {"ok": False, "error": "Вы подключены к терминалу."}
        return super().roll(player_id, aim)

    def cast(
        self,
        player_id: int,
        code: str,
        slot: int = 0,
        aim: float | None = None,
        target_x: float | None = None,
        target_y: float | None = None,
    ) -> dict[str, Any]:
        if player_id in self.linked:
            return {"ok": False, "error": "Вы подключены к терминалу."}
        player = self.players.get(player_id)
        if player is not None and not player.dead:
            if self.cursed(player, "syntax"):
                return {"ok": False, "error": SYNTAX_ERROR}
            if self.cursed(player, "mirror"):
                # The aim is "corrected"; what enemies() reports stays true.
                aim = None if aim is None else aim + math.pi
                if target_x is not None and target_y is not None:
                    target_x = 2 * player.x - target_x
                    target_y = 2 * player.y - target_y
        return super().cast(player_id, code, slot, aim, target_x, target_y)

    def help_plan(self) -> dict[str, Any]:
        """What the terminal's help panel should offer on this difficulty."""

        level = self.difficulty
        return {"hints": level.hints, "solution": level.solution, "theory": level.theory}

    def terminal_help(self, player_id: int, index: int) -> dict[str, str]:
        """One step of help, if this difficulty allows it. The client gets no more."""

        terminal = self.linked.get(player_id)
        if terminal is None:
            return {"kind": "", "text": ""}
        level = self.difficulty
        steps = terminal.task.help_steps(level.hints, level.solution)
        if not 0 <= index < len(steps):
            return {"kind": "", "text": ""}
        kind, text = steps[index]
        return {"kind": kind, "text": text}

    def submit_fix(self, player_id: int, code: str) -> dict[str, Any]:
        """Check a repair. On success the terminal does what it was holding back."""

        terminal = self.linked.get(player_id)
        if terminal is None or terminal.solved:
            return {"ok": False, "message": "Сначала подключитесь к терминалу."}
        result = check_task(terminal.task, code, self.known_runes)
        if result["ok"]:
            result["task"] = terminal.task.key
            self._apply_fix(terminal, self.players[player_id])
        return result

    def _apply_fix(self, terminal: Terminal, player: Player) -> None:
        terminal.solved = True
        self.last_fixer = player.id
        self.emit(
            {
                "e": "fix_done",
                "id": player.id,
                "name": player.name,
                "role": terminal.role,
                "x": round(terminal.x, 1),
                "y": round(terminal.y, 1),
            }
        )
        self.unlink(player.id)
        if terminal.role == "door":
            self.dungeon.set_closed(())
        elif terminal.role == "portal":
            self._purge_bugs()
            self.portal_ready = True
        else:
            self._lift_gate()

    def _purge_bugs(self) -> None:
        """A good patch takes everything it was feeding down with it."""

        for monster in list(self.monsters.values()):
            self.remove_monster(monster)

    def _open_gate(self, boss: Monster) -> None:
        """The boss retreats behind its bug until someone repairs the code."""

        self.gate_boss = boss
        boss.invuln_until = self.now + 3600.0
        if boss.state == "deploy":
            boss.state = "idle"
        task = self.gates_left.pop(0)
        room = self.active_room or self.dungeon.rooms[-1]
        x, y = self._gate_spot(room, boss)
        self._add_terminal(x, y, task, "gate")
        self.emit({"e": "gate_open", "id": boss.id, "x": round(x, 1), "y": round(y, 1)})

    def _gate_spot(self, room: Room, boss: Monster) -> tuple[float, float]:
        """The corner furthest from the boss, so reaching it is a run, not a step."""

        corners = [
            (room.x * TILE + 150, room.y * TILE + 150),
            ((room.x + room.w) * TILE - 150, room.y * TILE + 150),
            (room.x * TILE + 150, (room.y + room.h) * TILE - 150),
            ((room.x + room.w) * TILE - 150, (room.y + room.h) * TILE - 150),
        ]
        return max(corners, key=lambda corner: math.hypot(corner[0] - boss.x, corner[1] - boss.y))

    def _lift_gate(self) -> None:
        boss = self.gate_boss
        self.gate_boss = None
        if boss is None or boss.id not in self.monsters:
            return
        boss.invuln_until = 0.0
        boss.stun_until = self.now + GATE_STAGGER
        boss.dizzy_until = self.now + GATE_STAGGER
        boss.hp = max(1.0, boss.hp - boss.max_hp * GATE_DAMAGE)
        self.emit({"e": "gate_lift", "id": boss.id, "x": round(boss.x, 1), "y": round(boss.y, 1)})

    def _watch_gates(self) -> None:
        if not self.gates_left or self.gate_boss is not None:
            return
        for boss in self.monsters.values():
            if not boss.species.boss or boss.generation:
                continue
            threshold = GATE_THRESHOLDS[len(GATE_THRESHOLDS) - len(self.gates_left)]
            if boss.hp <= boss.max_hp * threshold:
                self._open_gate(boss)
                return

    def _update_trickle(self, now: float) -> None:
        """A broken node keeps leaking bugs until somebody patches it."""

        terminal = next((t for t in self.terminals if t.role == "portal"), None)
        if terminal is None or terminal.solved or now < self.trickle_at or self.monsters:
            return
        room = self.dungeon.rooms[-1]
        if not any(
            not player.dead and room.holds(player.x, player.y, 0.0)
            for player in self.players.values()
        ):
            return
        self.trickle_at = now + TRICKLE_EVERY
        budget = self._wave_budget() * TRICKLE_SHARE
        roster = [SPECIES[key] for key in self.stage.roster]
        cheapest = min(species.cost for species in roster)
        while budget >= cheapest:
            species = self.rng.choice([s for s in roster if s.cost <= budget])
            budget -= species.cost
            for _ in range(species.pack):
                leak = self._spawn_in_room(room, species)
                if leak is not None:
                    leak.leaked = True

    def _shelter_linked(self) -> None:
        for player_id in self.linked:
            player = self.players.get(player_id)
            if player is not None:
                player.invuln_until = max(player.invuln_until, self.now + LINK_SHELTER)

    # ------------------------------------------------------------- role skills
    def _effect_id(self) -> int:
        self._next_effect_id += 1
        return self._next_effect_id

    def raise_barrier(self, player: Player, angle: float) -> None:
        middle_x = player.x + math.cos(angle) * BARRIER_REACH
        middle_y = player.y + math.sin(angle) * BARRIER_REACH
        side_x = -math.sin(angle) * BARRIER_LENGTH / 2
        side_y = math.cos(angle) * BARRIER_LENGTH / 2
        self.barriers.append(
            Barrier(
                self._effect_id(),
                player.id,
                middle_x - side_x,
                middle_y - side_y,
                middle_x + side_x,
                middle_y + side_y,
                self.now + BARRIER_TIME,
                ROLES["admin"].color,
            )
        )

    def grant_sudo(self, player: Player) -> None:
        self.sudo[player.id] = self.now + SUDO_TIME
        player.invuln_until = max(player.invuln_until, self.now + SUDO_TIME)
        self.emit({"e": "sudo", "id": player.id, "x": round(player.x, 1), "y": round(player.y, 1)})

    def _sudo_active(self) -> list[Player]:
        admins = []
        for player_id, until in self.sudo.items():
            player = self.players.get(player_id)
            if player is not None and not player.dead and until > self.now:
                admins.append(player)
        return admins

    def _covered_by_sudo(self, target: Player) -> bool:
        return any(
            admin is not target
            and math.hypot(admin.x - target.x, admin.y - target.y) <= SUDO_COVER
            for admin in self._sudo_active()
        )

    def mark(self, monster: Monster, player: Player) -> None:
        monster.marked_until = self.now + MARK_TIME
        monster.marked_by = player.id
        monster.mark_jumps = 0
        self.emit({"e": "mark", "id": monster.id, "x": round(monster.x, 1), "y": round(monster.y, 1)})

    def _segfault(self, monster: Monster) -> None:
        """A marked process dies loudly and takes the mark to its neighbour."""

        source = self.players.get(monster.marked_by)
        self.emit({"e": "segfault", "x": round(monster.x, 1), "y": round(monster.y, 1)})
        neighbours = [
            other
            for other in list(self.monsters.values())
            if other.hacked_until <= self.now and other.spawned_at <= self.now
            and math.hypot(other.x - monster.x, other.y - monster.y) <= SEGFAULT_LEAP
        ]
        if monster.mark_jumps < SEGFAULT_JUMPS and neighbours:
            heir = min(neighbours, key=lambda other: math.hypot(other.x - monster.x, other.y - monster.y))
            heir.marked_until = self.now + MARK_TIME
            heir.marked_by = monster.marked_by
            heir.mark_jumps = monster.mark_jumps + 1
            self.emit(
                {
                    "e": "mark",
                    "id": heir.id,
                    "x": round(heir.x, 1),
                    "y": round(heir.y, 1),
                    "from_x": round(monster.x, 1),
                    "from_y": round(monster.y, 1),
                }
            )
        for other in neighbours:
            if (
                other.id in self.monsters
                and math.hypot(other.x - monster.x, other.y - monster.y) <= SEGFAULT_RADIUS
            ):
                self.damage(
                    target=other,
                    amount=SEGFAULT_DAMAGE,
                    source=source,
                    kind="segfault",
                    hit_x=other.x,
                    hit_y=other.y,
                )

    def hijack(self, monster: Monster, player: Player) -> None:
        monster.hacked_until = self.now + HIJACK_TIME
        monster.hacked_by = player.id
        self.emit({"e": "hijack", "id": monster.id, "x": round(monster.x, 1), "y": round(monster.y, 1)})

    def patch(self, player: Player, mate: Player, amount: float) -> None:
        healed = min(amount, mate.max_hp - mate.hp)
        mate.hp += healed
        mate.slow_until = 0.0
        mate.curses.clear()
        self.emit(
            {
                "e": "patch",
                "id": mate.id,
                "from_x": round(player.x, 1),
                "from_y": round(player.y, 1),
                "x": round(mate.x, 1),
                "y": round(mate.y, 1),
                "amount": round(healed, 1),
            }
        )

    def _record_history(self, now: float) -> None:
        """A rolling save of every living mage, so there is something to roll back to."""

        if now < self.history_at:
            return
        self.history_at = now + HISTORY_STEP
        for player in self.players.values():
            if not player.dead:
                states = self.history.setdefault(player.id, deque(maxlen=HISTORY_SIZE))
                states.append((player.x, player.y, player.hp, player.mana))

    def _safe_to_return(self, player: Player, x: float, y: float) -> bool:
        if player.id in self.linked or not self.can_stand(x, y, player.radius):
            return False
        room = self.active_room
        return room is None or room.holds(x, y, 0.5)

    def rollback(self, player: Player, mate: Player) -> None:
        x, y, hp, mana = self.history[mate.id][0]
        from_x, from_y = mate.x, mate.y
        if self._safe_to_return(mate, x, y):
            mate.x, mate.y = x, y
        if mate.dead:
            self._revive(mate, mate)
        mate.hp = max(mate.hp, min(hp, mate.max_hp))
        mate.mana = max(mate.mana, min(mana, mate.max_mana))
        mate.curses.clear()
        self.emit(
            {
                "e": "rollback",
                "id": mate.id,
                "from_x": round(from_x, 1),
                "from_y": round(from_y, 1),
                "x": round(mate.x, 1),
                "y": round(mate.y, 1),
            }
        )

    def scan(self, monster: Monster, player: Player) -> dict[str, Any]:
        species = monster.species
        monster.exposed_until = self.now + SCAN_TIME
        self.emit({"e": "scan", "id": monster.id, "x": round(monster.x, 1), "y": round(monster.y, 1)})
        return {
            "name": monster.name,
            "kind": species.key,
            "hp": round(monster.hp, 1),
            "max_hp": round(monster.max_hp, 1),
            "boss": species.boss,
            "guard": species.guard,
            "weak": sorted(KIND_RUNES[kind] for kind in species.weak),
            "immune": sorted(KIND_RUNES[kind] for kind in species.immune),
        }

    def place_breakpoint(self, player: Player, x: float, y: float) -> None:
        distance = math.hypot(x - player.x, y - player.y)
        if distance > BREAKPOINT_RANGE:
            share = BREAKPOINT_RANGE / distance
            x = player.x + (x - player.x) * share
            y = player.y + (y - player.y) * share
        self.breakpoints.append(
            Breakpoint(self._effect_id(), x, y, BREAKPOINT_RADIUS, self.now + BREAKPOINT_TIME)
        )
        self.emit({"e": "breakpoint", "x": round(x, 1), "y": round(y, 1), "radius": BREAKPOINT_RADIUS})

    def _frozen(self, monster: Monster) -> bool:
        return any(
            math.hypot(monster.x - zone.x, monster.y - zone.y) <= zone.radius
            for zone in self.breakpoints
        )

    def _update_role_effects(self, now: float, dt: float) -> None:
        self._record_history(now)
        self.barriers = [wall for wall in self.barriers if wall.expires_at > now]
        self.breakpoints = [zone for zone in self.breakpoints if zone.expires_at > now]
        self.sudo = {key: until for key, until in self.sudo.items() if until > now}
        for healer in self.players.values():
            aura = ROLES[healer.role].aura if healer.role and not healer.dead else 0.0
            if not aura:
                continue
            for mate in self.players.values():
                if not mate.dead and math.hypot(mate.x - healer.x, mate.y - healer.y) <= AURA_REACH:
                    mate.hp = min(mate.max_hp, mate.hp + aura * dt)

    def announce_dizzy(self, monster: Monster) -> None:
        self.emit({"e": "boss_dizzy", "id": monster.id, "x": round(monster.x, 1), "y": round(monster.y, 1)})

    # -------------------------------------------------------------------- tick
    def _update_world(self, now: float, dt: float) -> None:
        if self.outcome is not None:
            return
        self._shelter_linked()
        self._update_curses(now)
        self._update_role_effects(now, dt)
        self._update_timers(now)
        self._update_rooms(now)
        self._update_trickle(now)
        self._watch_gates()
        self._update_monsters(now, dt)
        self._update_hazards(now)
        self._update_pickups(dt)
        self._update_revives(dt)
        self._update_portal(dt)
        self._update_wipe(now)

    def _refresh_flow(self, now: float) -> None:
        """Distance in tiles from every open floor tile to the nearest mage."""

        if now < self.flow_at or not self.monsters:
            return
        self.flow_at = now + FLOW_REFRESH
        dungeon = self.dungeon
        flow: dict[tuple[int, int], int] = {}
        frontier: deque[tuple[int, int]] = deque()
        for player in self.players.values():
            if not player.dead and player.id not in self.linked:
                tile = (int(player.x // TILE), int(player.y // TILE))
                if tile not in flow:
                    flow[tile] = 0
                    frontier.append(tile)
        while frontier:
            x, y = frontier.popleft()
            next_distance = flow[(x, y)] + 1
            for tile in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if tile not in flow and not dungeon.solid(*tile):
                    flow[tile] = next_distance
                    frontier.append(tile)
        self.flow = flow

    def sees(self, monster: Monster, target: Player) -> bool:
        """Line of fire, as wide as a shot: a bolt that clips a pillar is a wasted bolt."""

        return self.dungeon.path_clear(monster.x, monster.y, target.x, target.y, SHOT_WIDTH)

    def route(self, monster: Monster, target: Player) -> float:
        """Which way to walk: straight at the target if open, else along the flow."""

        if self.now < monster.route_until:
            return monster.route_angle
        monster.route_until = self.now + ROUTE_REFRESH
        straight = math.atan2(target.y - monster.y, target.x - monster.x)
        if self.dungeon.path_clear(
            monster.x, monster.y, target.x, target.y, monster.radius * 0.85
        ):
            monster.route_angle = straight
            return straight
        x = int(monster.x // TILE)
        y = int(monster.y // TILE)
        here = self.flow.get((x, y), 1 << 30)
        best: tuple[int, int] | None = None
        for step_x in (-1, 0, 1):
            for step_y in (-1, 0, 1):
                tile = (x + step_x, y + step_y)
                distance = self.flow.get(tile, 1 << 30)
                if distance >= here:
                    continue
                # A diagonal squeezes past a corner only if both sides are open.
                if step_x and step_y and (
                    self.dungeon.solid(x + step_x, y) or self.dungeon.solid(x, y + step_y)
                ):
                    continue
                here = distance
                best = tile
        if best is None:
            monster.route_angle = straight
        else:
            monster.route_angle = math.atan2(
                (best[1] + 0.5) * TILE - monster.y, (best[0] + 0.5) * TILE - monster.x
            )
        return monster.route_angle

    def _update_rooms(self, now: float) -> None:
        if self.active_room is None:
            self._maybe_enter_room()
            return
        if self.monsters:
            return
        room = self.active_room
        if self.wave < self._waves_in(room):
            if now >= self.next_wave_at:
                self._spawn_wave(room)
            return
        self._clear_room(room)

    def _maybe_enter_room(self) -> None:
        for room in self.dungeon.rooms:
            if room.kind not in ("combat", "boss") or room.index in self.cleared_rooms:
                continue
            walkers = [
                player
                for player in self.players.values()
                if not player.dead and room.holds(player.x, player.y, ROOM_ENTRY_INSET)
            ]
            if walkers:
                self._enter_room(room, walkers[0])
                return

    def _enter_room(self, room: Room, leader: Player) -> None:
        self.active_room = room
        self.wave = 0
        self.next_wave_at = self.now + 0.9
        self.dungeon.set_closed(room.doors)
        # The party stays one party: whoever lagged behind joins the fight.
        for player in self.players.values():
            if not room.holds(player.x, player.y, 0.5):
                player.x, player.y = leader.x, leader.y
                self._settle(player)
                if not player.dead:
                    player.invuln_until = max(player.invuln_until, self.now + 1.0)
                self.emit({"e": "pull", "id": player.id, "x": round(player.x, 1), "y": round(player.y, 1)})
            if player.perks.ward_shield and not player.dead:
                player.shield = max(player.shield, player.perks.ward_shield)
                player.shield_until = self.now + WARD_SHIELD_TIME
                self.emit({"e": "shield", "id": player.id})
        self.emit({"e": "room_lock", "room": room.index, "boss": room.kind == "boss"})

    def _waves_in(self, room: Room) -> int:
        if room.kind == "boss":
            return 1
        return WAVES_PER_ROOM + (1 if room.index == len(self.dungeon.rooms) - 2 else 0)

    def _wave_budget(self) -> float:
        chapter = self.stage.chapter
        growth = 1 + (self.stage.number - 1) * 0.18
        party = 1 + BUDGET_PER_EXTRA_MAGE * (self.party_size - 1)
        return chapter.budget * growth * party * self.difficulty.crowd

    def _spawn_wave(self, room: Room) -> None:
        self.wave += 1
        self.next_wave_at = self.now + 1.1
        self.emit({"e": "wave", "wave": self.wave, "of": self._waves_in(room)})
        if room.kind == "boss":
            x, y = room.center
            self.spawn_monster(self.stage.chapter.boss, x, y - 100)
            return
        budget = self._wave_budget()
        roster = [SPECIES[key] for key in self.stage.roster]
        cheapest = min(species.cost for species in roster)
        while budget >= cheapest:
            species = self.rng.choice([s for s in roster if s.cost <= budget])
            budget -= species.cost
            for _ in range(species.pack):
                self._spawn_in_room(room, species)

    def _spawn_in_room(self, room: Room, species: Species) -> Monster | None:
        living = [player for player in self.players.values() if not player.dead]
        for _ in range(24):
            x, y = self.dungeon.open_point(room, self.rng, species.radius)
            if all(math.hypot(x - p.x, y - p.y) > 210 for p in living):
                break
        return self.spawn_monster(species.key, x, y)

    def _clear_room(self, room: Room) -> None:
        self.cleared_rooms.add(room.index)
        self.active_room = None
        self.dungeon.set_closed(())
        x, y = room.center
        for _ in range(max(1, self.party_size)):
            self._add_pickup("hp", x + self.rng.uniform(-60, 60), y + self.rng.uniform(-60, 60))
            self._add_pickup("mana", x + self.rng.uniform(-60, 60), y + self.rng.uniform(-60, 60))
        anchor = next((p for p in self.players.values() if not p.dead), None)
        for player in self.players.values():
            if player.dead and anchor is not None:
                self._revive(player, anchor)
        if room.kind == "boss":
            self.portal_ready = True
            self.portal = room.center
        self.emit({"e": "room_clear", "room": room.index, "portal": self.portal_ready})

    def _update_monsters(self, now: float, dt: float) -> None:
        # Whoever is at a terminal is not on the field: monsters hunt the rest.
        living = self.hunted()
        if not living:
            return
        self._refresh_flow(now)
        for monster in list(self.monsters.values()):
            if monster.id not in self.monsters or monster.spawned_at > now:
                continue
            monster.last_x, monster.last_y = monster.x, monster.y
            if monster.stun_until > now or self._frozen(monster):
                continue
            target = self._target_of(monster, living)
            if target is not None:
                think(self, monster, target, dt)

    def _target_of(self, monster: Monster, living: list[Player]) -> Player | None:
        """Who this monster goes for: the nearest enemy, unless sudo says otherwise."""

        now = self.now
        if monster.hacked_until > now:
            prey: list[Player] = [
                other
                for other in self.monsters.values()
                if other is not monster and other.hacked_until <= now and other.spawned_at <= now
            ]
        else:
            for admin in self._sudo_active():
                if math.hypot(admin.x - monster.x, admin.y - monster.y) <= SUDO_PULL:
                    return admin
            prey = living + [m for m in self.monsters.values() if m.hacked_until > now]
        return min(
            prey,
            key=lambda p: (p.x - monster.x) ** 2 + (p.y - monster.y) ** 2,
            default=None,
        )

    def _update_hazards(self, now: float) -> None:
        remaining: list[Hazard] = []
        for hazard in self.hazards:
            if now < hazard.impact_at:
                remaining.append(hazard)
                continue
            if not hazard.damage and not hazard.effect:
                # A bluff: the mark on the floor was the whole attack.
                continue
            owner = self.actor(hazard.owner)
            for player in self.targets_for(hazard.owner):
                if self._hazard_covers(hazard, player):
                    self._hazard_hit(hazard, player, owner)
            self.emit(
                {
                    "e": "hazard_blast",
                    "x": round(hazard.x, 1),
                    "y": round(hazard.y, 1),
                    "x2": hazard.x2,
                    "y2": hazard.y2,
                    "radius": hazard.radius,
                    "color": hazard.color,
                }
            )
        self.hazards = remaining

    def _hazard_hit(self, hazard: Hazard, player: Player, owner: Player | None) -> None:
        touched = player.invuln_until <= self.now
        self.damage(
            target=player,
            amount=hazard.damage,
            source=owner,
            kind="hazard",
            hit_x=player.x,
            hit_y=player.y,
        )
        if not touched or player.dead or isinstance(player, Monster):
            return
        if hazard.effect == "drain":
            player.mana = 0.0
        elif hazard.effect:
            self.curse(player, hazard.effect)

    @staticmethod
    def _hazard_covers(hazard: Hazard, player: Player) -> bool:
        if hazard.x2 is None:
            return math.hypot(player.x - hazard.x, player.y - hazard.y) <= hazard.radius + player.radius
        dx = hazard.x2 - hazard.x
        dy = hazard.y2 - hazard.y
        length_sq = dx * dx + dy * dy
        if length_sq <= 1e-6:
            return False
        at = max(0.0, min(1.0, ((player.x - hazard.x) * dx + (player.y - hazard.y) * dy) / length_sq))
        nearest_x = hazard.x + dx * at
        nearest_y = hazard.y + dy * at
        return math.hypot(player.x - nearest_x, player.y - nearest_y) <= hazard.radius / 2 + player.radius

    def _update_pickups(self, dt: float) -> None:
        remaining: list[Pickup] = []
        living = [player for player in self.players.values() if not player.dead]
        for pickup in self.pickups:
            nearest = min(
                living,
                key=lambda p: math.hypot(p.x - pickup.x, p.y - pickup.y),
                default=None,
            )
            if nearest is None:
                remaining.append(pickup)
                continue
            distance = math.hypot(nearest.x - pickup.x, nearest.y - pickup.y)
            if distance <= PICKUP_REACH:
                self._collect(pickup, nearest)
                continue
            if distance <= PICKUP_PULL + nearest.perks.pickup_reach:
                step = 300.0 * dt / distance
                pickup.x += (nearest.x - pickup.x) * step
                pickup.y += (nearest.y - pickup.y) * step
            remaining.append(pickup)
        self.pickups = remaining

    def _collect(self, pickup: Pickup, player: Player) -> None:
        if pickup.kind == "hp":
            player.hp = min(player.max_hp, player.hp + PICKUP_HEAL * player.perks.pickups)
        else:
            player.mana = min(player.max_mana, player.mana + PICKUP_MANA * player.perks.pickups)
        self.emit(
            {
                "e": "pickup",
                "id": player.id,
                "kind": pickup.kind,
                "x": round(pickup.x, 1),
                "y": round(pickup.y, 1),
            }
        )

    def _update_revives(self, dt: float) -> None:
        living = [player for player in self.players.values() if not player.dead]
        for player in self.players.values():
            if not player.dead:
                continue
            helper = next(
                (
                    friend
                    for friend in living
                    if math.hypot(friend.x - player.x, friend.y - player.y) <= REVIVE_REACH
                ),
                None,
            )
            if helper is None:
                player.revive = max(0.0, player.revive - dt)
                continue
            player.revive += dt * helper.perks.rescue
            if player.revive >= REVIVE_TIME:
                self._revive(player, player)

    def _revive(self, player: Player, near: Player) -> None:
        player.x, player.y = near.x, near.y
        self._settle(player)
        player.dead = False
        player.revive = 0.0
        player.hp = player.max_hp * 0.5
        player.mana = player.max_mana * 0.5
        player.input.up = player.input.down = player.input.left = player.input.right = False
        player.invuln_until = self.now + 2.0
        player.last_damage_at = -100.0
        self.emit(
            {
                "e": "respawn",
                "id": player.id,
                "x": round(player.x, 1),
                "y": round(player.y, 1),
                "color": player.color,
            }
        )

    def _update_portal(self, dt: float) -> None:
        if not self.portal_ready:
            return
        living = [player for player in self.players.values() if not player.dead]
        x, y = self.portal
        inside = sum(1 for p in living if math.hypot(p.x - x, p.y - y) <= PORTAL_REACH)
        if living and inside == len(living):
            self.portal_held += dt
            if self.portal_held >= PORTAL_HOLD:
                self.outcome = "cleared"
                self.outcome_at = self.now
        else:
            self.portal_held = 0.0

    def _update_wipe(self, now: float) -> None:
        if not self.players or any(not player.dead for player in self.players.values()):
            self.wipe_at = None
            return
        if self.wipe_at is None:
            self.wipe_at = now + WIPE_DELAY
        elif now >= self.wipe_at:
            self.outcome = "wiped"
            self.outcome_at = now

    wipe_at: float | None = None

    # ------------------------------------------------------------------ network
    def world_config(self) -> dict[str, Any]:
        config = super().world_config()
        config.update(
            {
                "mode": "story",
                "arena": {"w": self.field_w, "h": self.field_h, "border": 0},
                "obstacles": [],
                "spawns": [],
                "map_id": self.seed,
                "theme": self.stage.chapter.theme,
                "tile": TILE,
                "tiles": self.dungeon.rows(),
                "rooms": [
                    {"x": room.x, "y": room.y, "w": room.w, "h": room.h, "kind": room.kind}
                    for room in self.dungeon.rooms
                ],
                "torches": self.dungeon.torches(),
                "runes": sorted(self.known_runes),
                "difficulty": self.difficulty.level,
                "spell_costs": ALL_COSTS,
                "skills": {
                    name: {
                        "role": skill.role,
                        "open": self.stage.index >= skill.stage,
                        "cooldown": skill.cooldown,
                    }
                    for name, skill in SKILLS.items()
                },
                "bestiary": {
                    key: {"title": species.title, "hint": species.hint, "color": species.color}
                    for key, species in SPECIES.items()
                },
            }
        )
        return config

    def _monster_state(self, monster: Monster) -> str:
        if monster.dizzy_until > self.now:
            return "dizzy"
        return monster.state

    def snapshot(self) -> dict[str, Any]:
        state = super().snapshot()
        for entry in state["players"]:
            player = self.players[entry["id"]]
            entry["respawn_in"] = 0.0
            entry["revive"] = round(player.revive / REVIVE_TIME, 2)
            entry["speed"] = player.speed
            entry["cast_lock"] = round(player.cast_lock, 3)
            entry["roll_cooldown"] = round(player.roll_cooldown, 3)
            entry["linked"] = player.id in self.linked
            entry["role"] = player.role
            entry["sudo"] = player.id in self.sudo
            entry["curses"] = {
                kind: round(at - self.now, 1) for kind, at in player.curses.items()
            }
            entry["skills"] = {
                skill.name: round(max(0.0, self.skill_wait(player, skill.name)), 1)
                for skill in (ROLES[player.role].skills if player.role else ())
                if self.stage.index >= skill.stage
            }
        state["monsters"] = [
            {
                "id": monster.id,
                "kind": monster.species.key,
                "x": round(monster.x, 1),
                "y": round(monster.y, 1),
                "hp": round(monster.hp, 1),
                "max_hp": round(monster.max_hp, 1),
                "aim": round(monster.heading, 2),
                "state": self._monster_state(monster),
                "r": round(monster.radius, 1),
                "gen": monster.generation,
                "arriving": monster.spawned_at > self.now,
                "shielded": monster is self.gate_boss,
                "marked": monster.marked_until > self.now,
                "hacked": monster.hacked_until > self.now,
                "exposed": monster.exposed_until > self.now,
                "frozen": self._frozen(monster),
                "slow": monster.slow_until > self.now,
                "stun": monster.stun_until > self.now,
            }
            for monster in self.monsters.values()
        ]
        state["hazards"] = [
            {
                "id": hazard.id,
                "x": round(hazard.x, 1),
                "y": round(hazard.y, 1),
                "x2": hazard.x2,
                "y2": hazard.y2,
                "radius": hazard.radius,
                "ttl": round(max(0.0, hazard.impact_at - self.now), 2),
                "delay": hazard.delay,
                "color": hazard.color,
                "label": hazard.label,
            }
            for hazard in self.hazards
        ]
        state["pickups"] = [
            {"id": pickup.id, "kind": pickup.kind, "x": round(pickup.x, 1), "y": round(pickup.y, 1)}
            for pickup in self.pickups
        ]
        state["barriers"] = [
            {
                "id": wall.id,
                "x1": round(wall.x1, 1),
                "y1": round(wall.y1, 1),
                "x2": round(wall.x2, 1),
                "y2": round(wall.y2, 1),
                "color": wall.color,
                "ttl": round(wall.expires_at - self.now, 1),
            }
            for wall in self.barriers
        ]
        state["breakpoints"] = [
            {
                "id": zone.id,
                "x": round(zone.x, 1),
                "y": round(zone.y, 1),
                "radius": zone.radius,
                "ttl": round(zone.expires_at - self.now, 1),
            }
            for zone in self.breakpoints
        ]
        bosses = [monster for monster in self.monsters.values() if monster.species.boss]
        state["terminals"] = [
            {
                "id": terminal.id,
                "x": round(terminal.x, 1),
                "y": round(terminal.y, 1),
                "task": terminal.task.key,
                "role": terminal.role,
                "solved": terminal.solved,
                "operator": getattr(self.operator_of(terminal), "id", None),
            }
            for terminal in self.terminals
        ]
        state["story"] = {
            "doors": [list(tile) for tile in sorted(self.dungeon.closed)],
            "portal": [round(self.portal[0], 1), round(self.portal[1], 1)],
            "portal_ready": self.portal_ready,
            "portal_hold": round(self.portal_held / PORTAL_HOLD, 2),
            "rooms_left": sum(
                1
                for room in self.dungeon.rooms
                if room.kind in ("combat", "boss") and room.index not in self.cleared_rooms
            ),
            "fighting": self.active_room is not None,
            "wave": self.wave,
            "waves": self._waves_in(self.active_room) if self.active_room else 0,
            "essence": self.essence,
            "enemies": len(self.monsters),
            "last_fixer": self.last_fixer,
            "boss": {
                "name": bosses[0].name,
                "hp": round(sum(boss.hp for boss in bosses), 1),
                "max_hp": round(self.boss_max_hp, 1),
                "shielded": self.gate_boss is not None,
                "deploy": self._deploy_report(),
            }
            if bosses
            else None,
        }
        return state
