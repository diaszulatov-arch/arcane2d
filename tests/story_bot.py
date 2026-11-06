"""A scripted party that plays a dungeon the way a modest human would.

It walks to the nearest unfinished business and casts plain fireballs, because
the campaign must be beatable by someone who has only just learned to code.
"""

from __future__ import annotations

import math
from collections import deque

from arcane.campaign import Stage
from arcane.dungeon import TILE
from arcane.game import TICK_RATE, Player
from arcane.profiles import Profile
from arcane.roles import ROLES, apply_role
from arcane.story import MONSTER_ID_BASE, StoryArena, Terminal

FIRE_RANGE = 640.0
BOLT_SPEED = 575.0
LOOKAHEAD = 5
DANGER_RANGE = 170.0
SHELTER_REACHES = (60.0, 120.0, 180.0, 260.0, 340.0, 440.0, 560.0)
SHELTER_BEARINGS = 16
SHOT_NOTICE = 170.0
SHOT_WIDTH = 34.0
SHOT_STEP = 70.0


def spell_for(arena: StoryArena, role: str = "") -> str:
    """The best plain spell this stage's runes allow: guard, role, area, then bolts."""

    known = arena.known_runes
    lines = []
    if "heal" in known:
        lines.append('if me().hp < me().max_hp * 0.5 and ready("heal"):\n    heal()')
    if "shield" in known:
        lines.append('if me().hp < me().max_hp * 0.7 and ready("shield"):\n    shield()')
    if role:
        lines.append(ROLES[role].example.rsplit("fireball(aim())", 1)[0])
    if "nova" in known:
        lines.append('point = cursor()\nif point and point.dist < 170 and ready("nova"):\n    nova(190)')
    if "chain_lightning" in known:
        lines.append('if me().mana >= 50:\n    chain_lightning(aim())')
    elif "spark_volley" in known:
        lines.append('if me().mana >= 60:\n    spark_volley(aim(), 5, 0.5)')
    lines.append("if me().mana >= 11:\n    fireball(aim())")
    if "frostbolt" in known:
        lines.append("if me().mana >= 30:\n    frostbolt(aim())")
    return "\n".join(lines) + "\n"


def open_terminal(arena: StoryArena) -> Terminal | None:
    """A broken terminal that stands in the way right now, if there is one."""

    if arena.gate_boss is not None or arena.dungeon.closed and arena.active_room is None:
        return next((t for t in arena.terminals if not t.solved), None)
    if arena.active_room is not None:
        return None
    if all(
        room.index in arena.cleared_rooms
        for room in arena.dungeon.rooms
        if room.kind == "combat"
    ):
        return next((t for t in arena.terminals if not t.solved), None)
    return None


def walk_goal(arena: StoryArena) -> tuple[float, float]:
    """What needs doing next: a terminal, an uncleared room, or the portal."""

    terminal = open_terminal(arena)
    if terminal is not None:
        return terminal.x, terminal.y
    if arena.portal_ready:
        return arena.portal
    for room in arena.dungeon.rooms:
        if room.kind in ("combat", "boss") and room.index not in arena.cleared_rooms:
            return room.center
    return arena.portal


def next_step(arena: StoryArena, player: Player, goal: tuple[float, float]) -> tuple[float, float]:
    """Breadth-first over open tiles, then the furthest point along it in plain view."""

    dungeon = arena.dungeon
    start = (int(player.x // TILE), int(player.y // TILE))
    finish = (int(goal[0] // TILE), int(goal[1] // TILE))
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {finish: None}
    frontier = deque([finish])
    while frontier and start not in came_from:
        x, y = frontier.popleft()
        for step in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if step not in came_from and not dungeon.solid(*step):
                came_from[step] = (x, y)
                frontier.append(step)
    tile = came_from.get(start)
    if tile is None:
        return goal
    best = ((tile[0] + 0.5) * TILE, (tile[1] + 0.5) * TILE)
    for _ in range(LOOKAHEAD):
        tile = came_from.get(tile)
        if tile is None:
            break
        point = ((tile[0] + 0.5) * TILE, (tile[1] + 0.5) * TILE)
        if not dungeon.path_clear(player.x, player.y, point[0], point[1], 20.0):
            break
        best = point
    return best


def unsafe(arena: StoryArena, player: Player, x: float, y: float) -> bool:
    """Whether this spot is under a mark that will really hurt."""

    home = player.x, player.y
    player.x, player.y = x, y
    covered = any(
        (hazard.damage or hazard.effect) and arena._hazard_covers(hazard, player)
        for hazard in arena.hazards
    )
    player.x, player.y = home
    return covered


def shelter(arena: StoryArena, player: Player) -> tuple[float, float] | None:
    """The closest floor no mark covers, if the mage is standing under one."""

    if not unsafe(arena, player, player.x, player.y):
        return None
    for reach in SHELTER_REACHES:
        for step in range(SHELTER_BEARINGS):
            angle = step / SHELTER_BEARINGS * math.tau
            x = player.x + math.cos(angle) * reach
            y = player.y + math.sin(angle) * reach
            if arena.can_stand(x, y, player.radius) and not unsafe(arena, player, x, y):
                return x, y
    return None


def sidestep(arena: StoryArena, player: Player) -> tuple[float, float] | None:
    """A step off the line of the nearest shot about to connect, as a person would."""

    closest = SHOT_NOTICE
    step = None
    for shot in arena.projectiles:
        if shot.owner < MONSTER_ID_BASE:
            continue
        along_x, along_y = math.cos(shot.angle), math.sin(shot.angle)
        dx, dy = player.x - shot.x, player.y - shot.y
        ahead = dx * along_x + dy * along_y
        off_line = dy * along_x - dx * along_y
        if 0 < ahead < closest and abs(off_line) < SHOT_WIDTH:
            closest = ahead
            side = 1.0 if off_line >= 0 else -1.0
            step = (
                player.x - along_y * side * SHOT_STEP,
                player.y + along_x * side * SHOT_STEP,
            )
    return step


def steer(arena: StoryArena, player: Player, goal: tuple[float, float], flee: Player | None) -> None:
    refuge = shelter(arena, player) or sidestep(arena, player)
    if refuge is not None:
        target = refuge
    elif flee is not None:
        target = (player.x * 2 - flee.x, player.y * 2 - flee.y)
    else:
        target = next_step(arena, player, goal)
    dx, dy = target[0] - player.x, target[1] - player.y
    arena.set_input(
        player.id,
        up=dy < -6,
        down=dy > 6,
        left=dx < -6,
        right=dx > 6,
    )


def nudged(player: Player, last: dict[int, tuple[float, float]]) -> bool:
    """Whether this mage has been pressing into something; if so, wiggle free."""

    stuck = last.get(player.id) == (player.x, player.y)
    last[player.id] = (player.x, player.y)
    return stuck and bool(player.input.up or player.input.down or player.input.left or player.input.right)


def play_stage(
    stage: Stage,
    party_size: int,
    profile: Profile | None = None,
    *,
    seed: int = 1,
    seconds: float = 900.0,
    roles: tuple[str, ...] = (),
    difficulty: int = 1,
) -> StoryArena:
    arena = StoryArena(stage, party_size, seed=seed, now=1.0, difficulty=difficulty)
    mages = [arena.add_player(f"Маг {index + 1}") for index in range(party_size)]
    if profile is not None:
        for mage in mages:
            profile.apply_to(mage)
    for mage, role in zip(mages, roles):
        apply_role(mage, role)
    spells = {mage.id: spell_for(arena, mage.role) for mage in mages}
    now = 1.0
    goal = walk_goal(arena)
    positions: dict[int, tuple[float, float]] = {}
    for tick in range(int(seconds * TICK_RATE)):
        now += 1 / TICK_RATE
        arena.update(now)
        arena.drain_events()
        arena.snapshot()
        if arena.outcome:
            break
        if tick % 6:
            continue
        goal = walk_goal(arena)
        for mage in mages:
            if mage.dead:
                continue
            enemy = min(
                arena.targets_for(mage.id),
                key=lambda m: math.hypot(m.x - mage.x, m.y - mage.y),
                default=None,
            )
            distance = math.inf if enemy is None else math.hypot(enemy.x - mage.x, enemy.y - mage.y)
            near = distance < DANGER_RANGE
            fallen = next((p for p in mages if p.dead), None)
            clear = enemy is not None and arena.dungeon.path_clear(mage.x, mage.y, enemy.x, enemy.y, 8.0)
            far = distance > FIRE_RANGE * 0.85
            chase = (enemy.x, enemy.y) if enemy is not None and (far or not clear) else None
            terminal = open_terminal(arena)
            if terminal is not None and math.hypot(mage.x - terminal.x, mage.y - terminal.y) < 110:
                if arena.link(mage.id)[0] is not None:
                    arena.submit_fix(mage.id, terminal.task.solution)
                    continue
            if nudged(mage, positions):
                side = tick / 40 + mage.id
                arena.set_input(
                    mage.id,
                    up=math.sin(side) > 0,
                    down=math.sin(side) < 0,
                    left=math.cos(side) < 0,
                    right=math.cos(side) > 0,
                )
                continue
            # Backing away from what it cannot even hit would just pace behind a pillar.
            flee = enemy if near and clear else None
            steer(arena, mage, (fallen.x, fallen.y) if fallen else chase or goal, flee)
            if near:
                arena.roll(mage.id)
            if clear and distance < FIRE_RANGE:
                flight = distance / BOLT_SPEED
                lead_x = enemy.x + (enemy.x - enemy.last_x) * TICK_RATE * flight
                lead_y = enemy.y + (enemy.y - enemy.last_y) * TICK_RATE * flight
                arena.cast(mage.id, spells[mage.id], 0, None, lead_x, lead_y)
    return arena

