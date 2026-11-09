"""A scripted party that plays a dungeon the way a modest human would.

It walks to the nearest unfinished business and casts plain fireballs, because
the campaign must be beatable by someone who has only just learned to code.
"""

from __future__ import annotations

import math
from collections import deque

from arcane.campaign import Stage
from arcane.dungeon import TILE
from arcane.foes import open_to
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
# On these steps the quest wants things shot; on the others, it wants mages somewhere.
PAD_CLEARANCE = 72.0
SHOOTING_STEPS = frozenset({"hunt", "memory", "bucket", "racks", "inbox"})


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


PLAIN_BOLT = "if me().mana >= 11:\n    fireball(aim())\n"


def best_target(arena: StoryArena, mage: Player) -> Player | None:
    """The nearest enemy a hit would actually land on, as anyone would soon work out."""

    near = lambda m: math.hypot(m.x - mage.x, m.y - mage.y)
    enemies = arena.foes_for(mage.id)
    awake = [m for m in enemies if m.invuln_until <= arena.now and open_to(arena, m, mage)]
    return min(awake or enemies, key=near, default=None)


def where_it_opens(arena: StoryArena, enemy: Player, mage: Player) -> tuple[float, float] | None:
    """Some can only be hurt from a certain spot: under the dome, inside the frame."""

    if enemy is None or open_to(arena, enemy, mage):
        return None
    if enemy.species.key == "bubble":
        return enemy.x, enemy.y
    if enemy.species.key == "context":
        return enemy.memo.x, enemy.memo.y
    return None


def open_terminal(arena: StoryArena) -> Terminal | None:
    """A broken terminal that stands in the way right now, if there is one."""

    if arena.active_room is not None and arena.gate_boss is None:
        return None
    quest_open = arena.quest is None or arena.quest.done
    for terminal in arena.terminals:
        if terminal.solved:
            continue
        if terminal.role == "gate" and arena.gate_boss is None:
            continue
        if terminal.role == "portal" and not quest_open:
            continue
        return terminal
    return None


def quest_goal(arena: StoryArena, player: Player) -> tuple[float, float] | None:
    if arena.quest is None or arena.quest.done:
        return None
    return arena.quest.objective(player)


def walk_goal(arena: StoryArena, player: Player | None = None) -> tuple[float, float]:
    """What needs doing next: a terminal, the quest, an uncleared room, or the portal."""

    terminal = open_terminal(arena)
    if terminal is not None:
        return terminal.x, terminal.y
    if arena.portal_ready:
        return arena.portal
    if player is not None:
        goal = quest_goal(arena, player)
        if goal is not None:
            return goal
    for room in arena.dungeon.path:
        if room.kind in ("combat", "boss") and room.index not in arena.cleared_rooms:
            return arena.dungeon.open_near(*room.center)
    return arena.portal


def next_step(arena: StoryArena, player: Player, goal: tuple[float, float]) -> tuple[float, float]:
    """Breadth-first over open tiles, then the furthest point along it in plain view."""

    dungeon = arena.dungeon
    start = (int(player.x // TILE), int(player.y // TILE))
    finish = (int(goal[0] // TILE), int(goal[1] // TILE))
    # A person walks around a hyperlink on the floor; so does this.
    pads: set[tuple[int, int]] = set()
    centres: list[tuple[float, float]] = []
    if arena.terrain is not None:
        for x1, y1, x2, y2 in arena.terrain.links:
            for px, py in ((x1, y1), (x2, y2)):
                centres.append((px, py))
                tx, ty = int(px // TILE), int(py // TILE)
                pads |= {(tx + a, ty + b) for a in (-1, 0, 1) for b in (-1, 0, 1)}
    pads -= {start, finish}
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {finish: None}
    frontier = deque([finish])
    while frontier and start not in came_from:
        x, y = frontier.popleft()
        for step in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if step not in came_from and step not in pads and not dungeon.solid(*step):
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
        if any(_passes_near(player.x, player.y, point, centre) for centre in centres):
            break
        best = point
    return best


def _passes_near(x: float, y: float, point: tuple[float, float], centre: tuple[float, float]) -> bool:
    """Whether walking straight to ``point`` would clip a hyperlink pad."""

    dx, dy = point[0] - x, point[1] - y
    length = dx * dx + dy * dy
    if length == 0:
        return False
    along = max(0.0, min(1.0, ((centre[0] - x) * dx + (centre[1] - y) * dy) / length))
    return math.hypot(x + dx * along - centre[0], y + dy * along - centre[1]) < PAD_CLEARANCE


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
        for mage in mages:
            if mage.dead:
                continue
            goal = walk_goal(arena, mage)
            step = arena.quest.step if arena.quest is not None else None
            busy = (
                arena.active_room is None
                and step is not None
                and step.kind not in SHOOTING_STEPS
                and quest_goal(arena, mage) is not None
            )
            carrying = arena.quest is not None and arena.quest.carrier() == mage.id
            spell = spells[mage.id]
            order = arena.quest.bot_shot(mage) if arena.quest is not None else None
            if order is not None:
                enemy, wanted = order
                spell = wanted or spell
            else:
                enemy = best_target(arena, mage)
                # TabError punishes changing runes, and this spell has several.
                if enemy is not None and enemy.species.key == "taberror":
                    spell = PLAIN_BOLT
            distance = math.inf if enemy is None else math.hypot(enemy.x - mage.x, enemy.y - mage.y)
            near = distance < DANGER_RANGE
            fallen = next((p for p in mages if p.dead), None)
            clear = enemy is not None and arena.dungeon.path_clear(mage.x, mage.y, enemy.x, enemy.y, 8.0, shot=True)
            far = distance > FIRE_RANGE * 0.85
            chase = (enemy.x, enemy.y) if enemy is not None and (far or not clear) else None
            if carrying or (busy and distance > 360):
                chase = None
            chase = where_it_opens(arena, enemy, mage) or chase
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
                arena.cast(mage.id, spell, 0, None, lead_x, lead_y)
    return arena

