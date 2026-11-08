"""Tests for the campaign: dungeons, monsters, lessons, upgrades and parties."""

from __future__ import annotations

import json
import math
import random
import tempfile
import unittest
from collections import deque
from pathlib import Path

from arcane.campaign import CHAPTERS, DIFFICULTIES, STAGES
from arcane.dungeon import TILE, build_dungeon
from arcane.game import (
    CAST_LOCK,
    MANA_REGEN,
    MAX_HP,
    MAX_MANA,
    MOVE_SPEED,
    ROLL_COOLDOWN,
    TICK_RATE,
    Arena,
)
from arcane.lessons import GATES, LESSONS, TASKS, check_task, runes_for_stage
from arcane.monsters import ATTACKS, LOOP_FUSE, LOOP_PULL, SPECIES, SWEEP_FUSE, THINKERS
from arcane.party import CAMP, FINISHED, PLAYING, Party
from arcane.tickets import TICKETS
from arcane.profiles import (
    BRANCHES,
    MAX_UPGRADE_LEVEL,
    UPGRADES,
    Profile,
    ProfileStore,
    upgrade_cost,
)
from arcane.roles import ROLE_STAGE, ROLES, SKILLS, apply_role
from arcane.story import StoryArena as FullArena
from arcane.story import (
    CURSES,
    DEPLOY_BREAK,
    DEPLOY_DAMAGE,
    DEPLOY_TIME,
    HISTORY_STEP,
    MARK_BONUS,
    MONSTER_ID_BASE,
    REVIVE_TIME,
    ROTATION_WAIT,
    SEGFAULT_JUMPS,
)
from story_bot import play_stage



def StoryArena(*args, **kwargs) -> FullArena:
    """These tests are about the rules of a fight: bare rooms keep them about that.

    The furnished rooms have their own tests, and the bot plays those for real.
    """

    kwargs.setdefault("plain", True)
    return FullArena(*args, **kwargs)


TICK = 1 / TICK_RATE
FIRST = STAGES[0]
BOSS = STAGES[3]
TOKEN_A = "a" * 32
TOKEN_B = "b" * 32


def advance(arena: FullArena, seconds: float) -> list[dict]:
    events: list[dict] = []
    for _ in range(int(seconds * TICK_RATE)):
        arena.update(arena.now + TICK)
        events.extend(arena.drain_events())
    return events


def reachable(dungeon, start: tuple[int, int]) -> set[tuple[int, int]]:
    seen = {start}
    frontier = deque([start])
    while frontier:
        x, y = frontier.popleft()
        for tile in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if tile not in seen and not dungeon.solid(*tile):
                seen.add(tile)
                frontier.append(tile)
    return seen


class DungeonTests(unittest.TestCase):
    def test_every_room_can_be_reached_from_the_first(self) -> None:
        for seed in range(40):
            layout = ["start", *["combat"] * (3 + seed % 3), "exit"]
            dungeon = build_dungeon(layout, random.Random(seed))
            first = dungeon.rooms[0]
            area = reachable(dungeon, (first.x + 1, first.y + 1))
            for room in dungeon.rooms:
                self.assertIn(
                    (room.x + room.w // 2 + 3, room.y + room.h // 2 + 3),
                    area | {(x + 1, y) for x, y in area} | {(x, y + 1) for x, y in area},
                    f"seed {seed}: room {room.index} is cut off",
                )

    def test_a_locked_room_cannot_be_walked_out_of(self) -> None:
        dungeon = build_dungeon(["start", "combat", "exit"], random.Random(3))
        room = dungeon.rooms[1]
        self.assertGreaterEqual(len(room.doors), 8, "a door on each side")
        dungeon.set_closed(room.doors)
        area = reachable(dungeon, (room.x + 1, room.y + 1))
        for x, y in area:
            self.assertTrue(
                room.x <= x < room.x + room.w and room.y <= y < room.y + room.h,
                f"tile {(x, y)} is outside the locked room",
            )

    def test_circles_stop_at_walls_and_pass_through_open_floor(self) -> None:
        dungeon = build_dungeon(["start", "exit"], random.Random(1))
        room = dungeon.rooms[0]
        x, y = room.center
        self.assertFalse(dungeon.blocked(x, y, 18))
        self.assertTrue(dungeon.blocked(room.x * TILE + 4, y, 18))
        self.assertTrue(dungeon.blocked(-100, -100, 18))

    def test_a_ray_stops_at_the_first_wall(self) -> None:
        dungeon = build_dungeon(["start", "exit"], random.Random(1))
        room = dungeon.rooms[0]
        x, y = room.center
        end_x, _ = dungeon.ray_end(x, y, -1.0, 0.0, 4000.0)
        self.assertLess(abs(end_x - room.x * TILE), 16)


class CampaignShapeTests(unittest.TestCase):
    def test_five_chapters_of_three_dungeons_and_a_boss(self) -> None:
        self.assertEqual(len(CHAPTERS), 5)
        self.assertEqual(len(STAGES), 20)
        for index, chapter in enumerate(CHAPTERS):
            stages = [stage for stage in STAGES if stage.chapter_index == index]
            self.assertEqual([stage.is_boss for stage in stages], [False, False, False, True])

    def test_chapters_differ_in_look_and_enemies(self) -> None:
        self.assertEqual(len({chapter.theme for chapter in CHAPTERS}), 5)
        rosters = [{key for keys in chapter.roster for key in keys} for chapter in CHAPTERS]
        for index, roster in enumerate(rosters):
            for other in rosters[index + 1 :]:
                self.assertFalse(roster & other, "each chapter brings its own enemies")

    def test_every_monster_the_story_names_exists_and_can_think(self) -> None:
        for chapter in CHAPTERS:
            self.assertIn(chapter.boss, SPECIES)
            for roster in chapter.roster:
                for key in roster:
                    self.assertIn(SPECIES[key].ai, THINKERS)
        for species in SPECIES.values():
            self.assertTrue(species.hint, f"{species.key} has no tip for players")

    def test_every_stage_has_a_lesson(self) -> None:
        self.assertEqual(len(LESSONS), len(STAGES))


class ArenaRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena = StoryArena(STAGES[8], 2, seed=4, now=1.0)
        self.first = self.arena.add_player("Первый")
        self.second = self.arena.add_player("Второй")
        self.room = self.arena.dungeon.rooms[1]

    def enter_room(self) -> None:
        self.first.x, self.first.y = self.room.center
        self.first.y += 60
        advance(self.arena, 0.2)

    def test_mages_cannot_hurt_each_other(self) -> None:
        self.assertEqual(self.arena.targets_for(self.first.id), [])

    def test_a_rune_not_yet_studied_refuses_to_work(self) -> None:
        early = StoryArena(FIRST, 1, seed=1, now=1.0)
        mage = early.add_player("Новичок")
        result = early.cast(mage.id, "beam(0)", 0, 0.0)
        self.assertFalse(result["ok"])
        self.assertIn("не изучена", result["error"])
        mage.cast_ready_at = 0.0
        self.assertEqual(early.cast(mage.id, 'log(ready("beam"))', 0, 0.0)["log"], ["False"])

    def test_runes_arrive_one_lesson_at_a_time(self) -> None:
        self.assertEqual(runes_for_stage(0), {"fireball"})
        self.assertEqual(runes_for_stage(1), {"fireball", "frostbolt"})
        self.assertEqual(len(runes_for_stage(len(STAGES) - 1) - {"enemies", "allies"}), 16)

    def test_entering_a_room_locks_it_and_gathers_the_party(self) -> None:
        self.enter_room()
        self.assertIs(self.arena.active_room, self.room)
        self.assertTrue(self.arena.dungeon.closed)
        self.assertTrue(self.room.holds(self.second.x, self.second.y))

    def test_clearing_every_wave_opens_the_doors(self) -> None:
        self.enter_room()
        waves = self.arena._waves_in(self.room)
        for _ in range(waves):
            advance(self.arena, 1.5)
            self.assertTrue(self.arena.monsters, "a wave should have spawned")
            for monster in list(self.arena.monsters.values()):
                self.arena._kill(monster, self.first, "fire")
            self.arena.drain_events()
        events = advance(self.arena, 1.5)
        self.assertIn("room_clear", [event["e"] for event in events])
        self.assertFalse(set(self.room.doors) & self.arena.dungeon.closed)
        # Only the quest still holds a door: the one to the main terminal.
        self.assertEqual(set(self.arena.locks), {"exit"})
        self.assertIsNone(self.arena.active_room)

    def test_a_friend_can_pull_you_back_up(self) -> None:
        self.first.hp = 1
        self.first.invuln_until = 0
        self.arena.damage(
            target=self.first, amount=50, source=None, kind="hazard",
            hit_x=self.first.x, hit_y=self.first.y,
        )
        self.assertTrue(self.first.dead)
        self.second.x, self.second.y = self.first.x + 40, self.first.y
        advance(self.arena, REVIVE_TIME + 0.2)
        self.assertFalse(self.first.dead)
        self.assertAlmostEqual(self.first.hp, self.first.max_hp * 0.5, delta=2.0)

    def test_when_everyone_falls_the_stage_is_lost(self) -> None:
        for mage in (self.first, self.second):
            mage.hp = 1
            mage.invuln_until = 0
            self.arena.damage(
                target=mage, amount=50, source=None, kind="hazard", hit_x=0, hit_y=0
            )
        advance(self.arena, 2.0)
        self.assertEqual(self.arena.outcome, "wiped")

    def test_the_portal_waits_for_the_whole_party(self) -> None:
        self.arena.portal_ready = True
        x, y = self.arena.portal
        self.first.x, self.first.y = x, y
        self.second.x, self.second.y = self.arena.dungeon.rooms[0].center
        advance(self.arena, 1.0)
        self.assertIsNone(self.arena.outcome)
        self.second.x, self.second.y = x + 40, y
        advance(self.arena, 1.0)
        self.assertEqual(self.arena.outcome, "cleared")

    def test_snapshot_is_valid_json_even_with_a_fallen_mage(self) -> None:
        self.first.hp = 1
        self.first.invuln_until = 0
        self.arena.damage(target=self.first, amount=50, source=None, kind="hazard", hit_x=0, hit_y=0)
        self.assertIn("monsters", json.loads(json.dumps(self.arena.snapshot(), allow_nan=False)))


class MonsterRulesTests(unittest.TestCase):
    def spawn(self, key: str, party: int = 1):
        arena = StoryArena(STAGES[6], party, seed=2, now=1.0)
        mage = arena.add_player("Маг")
        mage.invuln_until = 0.0
        room = arena.dungeon.rooms[1]
        arena.active_room = room
        x, y = room.center
        mage.x, mage.y = x, y + 40
        monster = arena.spawn_monster(key, x, y - 140)
        monster.spawned_at = 0.0
        monster.invuln_until = 0.0
        return arena, mage, monster

    def hit(self, arena, mage, monster, x, y, kind="fire") -> float:
        before = monster.hp
        arena.damage(target=monster, amount=20, source=mage, kind=kind, hit_x=x, hit_y=y)
        return before - monster.hp

    def test_a_guard_blocks_from_the_front_but_not_from_behind(self) -> None:
        arena, mage, wall = self.spawn("moderator")
        wall.heading = 0.0
        front = self.hit(arena, mage, wall, wall.x + 20, wall.y)
        back = self.hit(arena, mage, wall, wall.x - 20, wall.y)
        self.assertLess(front, 4)
        self.assertEqual(back, 20)

    def test_a_blast_around_a_guard_is_not_blocked(self) -> None:
        arena, mage, wall = self.spawn("moderator")
        self.assertEqual(self.hit(arena, mage, wall, wall.x, wall.y, "meteor"), 20)

    def test_immunity_and_weakness(self) -> None:
        arena, mage, ash = self.spawn("firewall")
        self.assertEqual(self.hit(arena, mage, ash, ash.x + 1, ash.y), 0)
        self.assertEqual(self.hit(arena, mage, ash, ash.x + 1, ash.y, "lightning"), 20)
        arena, mage, frost = self.spawn("like")
        self.assertEqual(self.hit(arena, mage, frost, frost.x + 1, frost.y), 30)

    def test_recursor_dies_down_to_its_base_case(self) -> None:
        arena, mage, boss = self.spawn("pgt")
        kills = 0
        while arena.monsters:
            monster = next(iter(arena.monsters.values()))
            arena._kill(monster, mage, "frost")
            kills += 1
        self.assertEqual(kills, 7, "1 + 2 + 4 bodies")

    def test_spores_leave_a_cloud_behind(self) -> None:
        arena, mage, spore = self.spawn("malware")
        arena._kill(spore, mage, "fire")
        self.assertEqual(len(arena.clouds), 1)

    def test_a_cloud_left_by_a_monster_poisons_mages_only(self) -> None:
        arena, mage, spore = self.spawn("malware")
        arena.drop_cloud(spore, mage.x, mage.y, 100)
        advance(arena, 1.0)
        self.assertLess(mage.hp, mage.max_hp)
        self.assertEqual(spore.hp, spore.max_hp)

    def test_more_mages_mean_tougher_monsters(self) -> None:
        _, _, alone = self.spawn("popup", 1)
        _, _, crowd = self.spawn("popup", 4)
        self.assertGreater(crowd.max_hp, alone.max_hp)
        _, _, boss_alone = self.spawn("bracket", 1)
        _, _, boss_crowd = self.spawn("bracket", 4)
        self.assertGreater(boss_crowd.max_hp, boss_alone.max_hp * 2.5)

    def test_monsters_walk_around_a_pillar_rather_than_into_it(self) -> None:
        arena = StoryArena(STAGES[6], 1, seed=2, now=1.0)
        mage = arena.add_player("Маг")
        room = next(
            room for room in arena.dungeon.rooms
            if any(
                arena.dungeon.grid[y][x] == "o"
                for y in range(room.y, room.y + room.h)
                for x in range(room.x, room.x + room.w)
            )
        )
        px, py = next(
            (x, y)
            for y in range(room.y, room.y + room.h)
            for x in range(room.x, room.x + room.w)
            if arena.dungeon.grid[y][x] == "o"
        )
        arena.active_room = room
        arena.dungeon.set_closed(room.doors)
        mage.x, mage.y = (px + 3.5) * TILE, (py + 1) * TILE
        monster = arena.spawn_monster("popup", (px - 1.5) * TILE, (py + 1) * TILE)
        monster.spawned_at = 0.0
        for _ in range(int(6 * TICK_RATE)):
            mage.invuln_until = arena.now + 1
            arena.update(arena.now + TICK)
            if math.hypot(monster.x - mage.x, monster.y - mage.y) < 60:
                return
        self.fail(f"stuck at {monster.x:.0f}, {monster.y:.0f}")

    def test_a_shot_at_a_wall_goes_no_further(self) -> None:
        arena = StoryArena(FIRST, 1, seed=1, now=1.0)
        mage = arena.add_player("Маг")
        room = arena.dungeon.rooms[0]
        mage.x, mage.y = room.x * TILE + 60, room.y * TILE + 60
        arena.cast(mage.id, "fireball(PI)", 0, math.pi)
        advance(arena, 0.5)
        self.assertEqual(arena.projectiles, [])


class TaskTests(unittest.TestCase):
    """Every task must fail as shipped, and pass once it is repaired."""

    # Other correct repairs: a check that only accepts one spelling teaches nothing.
    ALTERNATIVES = {
        "call": "angle = aim()\nfireball(angle)",
        "if": "if not me().hp >= 50:\n    shield()\nfireball(aim())",
        "for": "for shift in (-0.3, 0.0, 0.3):\n    fireball(aim() + shift)",
        "while": "n = 4\nwhile n > 0:\n    fireball(aim())\n    n -= 1",
        "radar": (
            "targets = enemies()\nif len(targets) > 0:\n    best = None\n    for e in targets:\n"
            "        if best is None or e.dist < best.dist:\n            best = e\n"
            "    fireball(direction(best.x, best.y))"
        ),
        "lists": 'servers = ["web", "db", "cache"]\n\ndef last_server():\n    return servers[-1]',
        "range": (
            "def total_load(loads):\n    total = 0\n    for load in loads:\n"
            "        total += load\n    return total"
        ),
        "dicts": 'ports = {"web": 80, "ssh": 22}\n\ndef port_of(name):\n    if name not in ports:\n        return None\n    return ports[name]',
        "break": (
            'def first_down(servers):\n    for i in range(len(servers)):\n'
            '        if servers[i] == "down":\n            return i\n    return None'
        ),
        "recursion": "def depth_sum(n):\n    if n <= 0:\n        return 0\n    return n + depth_sum(n - 1)",
    }

    # Answers that dodge the point of the task and must not get through.
    DODGES = {
        "lists": 'def last_server():\n    return "cache"',
        "break": 'def first_down(servers):\n    return 1',
        "recursion": "def depth_sum(n):\n    return n * (n + 1) // 2",
        "radar": "fireball(0.5)",
    }

    def known_for(self, key: str) -> set[str]:
        for index, lesson in enumerate(LESSONS):
            if lesson.task.key == key:
                return runes_for_stage(index)
        return runes_for_stage(len(LESSONS) - 1)

    def test_every_task_is_broken_as_shipped_and_works_when_repaired(self) -> None:
        for key, task in TASKS.items():
            known = self.known_for(key)
            with self.subTest(key):
                self.assertFalse(check_task(task, task.starter, known)["ok"], "starter already works")
                result = check_task(task, task.solution, known)
                self.assertTrue(result["ok"], result["message"])

    def test_every_task_comes_with_help_and_a_bad_suggestion(self) -> None:
        for key, task in TASKS.items():
            with self.subTest(key):
                self.assertTrue(task.brief)
                self.assertEqual(len(task.hints), 2)
                self.assertTrue(task.pgt)

    def test_a_different_correct_repair_is_also_accepted(self) -> None:
        for key, code in self.ALTERNATIVES.items():
            with self.subTest(key):
                result = check_task(TASKS[key], code, self.known_for(key))
                self.assertTrue(result["ok"], result["message"])

    def test_answers_that_dodge_the_task_are_refused(self) -> None:
        for key, code in self.DODGES.items():
            with self.subTest(key):
                self.assertFalse(check_task(TASKS[key], code, self.known_for(key))["ok"])

    def test_the_example_in_each_lesson_is_valid_code(self) -> None:
        for index, lesson in enumerate(LESSONS):
            with self.subTest(lesson.key):
                result = check_task(lesson.task, lesson.example, runes_for_stage(index))
                self.assertNotIn("Строка", result["message"].split(":")[0])

    def test_a_syntax_error_is_explained_by_line(self) -> None:
        self.assertIn("Строка 1", check_task(TASKS["call"], "fireball(", {"fireball"})["message"])

    def test_a_task_cannot_be_used_to_hurt_the_server(self) -> None:
        tower = "a=[1]*250\nb=[a]*250\nc=[b]*250\nd=[c]*250\nx=str(d)\nfireball(aim())"
        self.assertFalse(check_task(TASKS["call"], tower, {"fireball"})["ok"])
        self.assertFalse(check_task(TASKS["call"], "#" * 5000, {"fireball"})["ok"])
        runaway = "def top3(scores):\n    while True:\n        pass\n"
        self.assertFalse(check_task(TASKS["slices"], runaway, set())["ok"])

    def test_a_task_only_trusts_runes_known_by_then(self) -> None:
        self.assertFalse(check_task(TASKS["call"], "beam(aim())\nfireball(aim())", {"fireball"})["ok"])

    def test_a_lesson_teaches_each_rune_once(self) -> None:
        taught = [name for lesson in LESSONS for name in lesson.reward]
        self.assertEqual(len(taught), len(set(taught)))
        self.assertIn("enemies", taught)

    def test_every_boss_hides_behind_two_repairs(self) -> None:
        for chapter in CHAPTERS:
            self.assertEqual(len(GATES[chapter.boss]), 2)


def at_the_exit(arena: FullArena) -> tuple[float, float]:
    """Pretend the fights are done and stand the party next to the broken terminal."""

    for room in arena.dungeon.rooms:
        if room.kind == "combat":
            arena.cleared_rooms.add(room.index)
    terminal = arena.terminals[0]
    for player in arena.players.values():
        player.x, player.y = terminal.x, terminal.y + 40
    return terminal.x, terminal.y


class TerminalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena = StoryArena(FIRST, 2, seed=3, now=1.0)
        self.first = self.arena.add_player("Первый")
        self.second = self.arena.add_player("Второй")
        at_the_exit(self.arena)
        self.terminal = self.arena.terminals[0]
        self.task = self.terminal.task

    def test_the_way_out_stays_shut_until_the_code_is_fixed(self) -> None:
        advance(self.arena, 0.2)
        self.assertFalse(self.arena.portal_ready)
        self.arena.link(self.first.id)
        self.assertFalse(self.arena.submit_fix(self.first.id, self.task.starter)["ok"])
        self.assertFalse(self.arena.portal_ready)
        self.assertTrue(self.arena.submit_fix(self.first.id, self.task.solution)["ok"])
        self.assertTrue(self.arena.portal_ready)
        self.assertTrue(self.terminal.solved)

    def test_a_repair_needs_a_mage_at_the_terminal(self) -> None:
        self.assertFalse(self.arena.submit_fix(self.first.id, self.task.solution)["ok"])
        self.first.x += 400
        terminal, error = self.arena.link(self.first.id)
        self.assertIsNone(terminal)
        self.assertTrue(error)

    def test_a_terminal_takes_one_mage_at_a_time(self) -> None:
        self.assertIsNotNone(self.arena.link(self.first.id)[0])
        terminal, error = self.arena.link(self.second.id)
        self.assertIsNone(terminal)
        self.assertIn("Первый", error)
        self.arena.unlink(self.first.id)
        self.assertIsNotNone(self.arena.link(self.second.id)[0])

    def test_a_dropped_mage_frees_the_terminal(self) -> None:
        self.arena.link(self.first.id)
        self.arena.remove_player(self.first.id)
        self.assertIsNotNone(self.arena.link(self.second.id)[0])

    def test_the_operator_is_safe_and_still(self) -> None:
        self.arena.link(self.first.id)
        advance(self.arena, 0.1)
        x, y, hp = self.first.x, self.first.y, self.first.hp
        self.arena.set_input(self.first.id, up=True, down=False, left=False, right=False)
        self.assertFalse(self.arena.cast(self.first.id, "fireball(0)", 0, 0.0)["ok"])
        self.assertFalse(self.arena.roll(self.first.id)["ok"])
        self.arena.damage(
            target=self.first, amount=50, source=None, kind="hazard", hit_x=x, hit_y=y
        )
        advance(self.arena, 0.3)
        self.assertEqual((self.first.x, self.first.y), (x, y))
        self.assertEqual(self.first.hp, hp)

    def test_monsters_leave_the_operator_and_hunt_the_others(self) -> None:
        self.arena.link(self.first.id)
        self.second.x, self.second.y = self.first.x + 300, self.first.y
        monster = self.arena.spawn_monster("popup", self.first.x + 60, self.first.y)
        monster.spawned_at = 0.0
        monster.next_contact = 1 << 30
        start = math.hypot(monster.x - self.second.x, monster.y - self.second.y)
        advance(self.arena, 0.6)
        self.assertLess(math.hypot(monster.x - self.second.x, monster.y - self.second.y), start)

    def test_leaving_the_terminal_gives_a_moment_to_react(self) -> None:
        self.arena.link(self.first.id)
        advance(self.arena, 0.1)
        self.arena.unlink(self.first.id)
        self.assertGreater(self.first.invuln_until, self.arena.now + 0.8)

    def test_a_broken_node_leaks_bugs_that_pay_nothing(self) -> None:
        advance(self.arena, 0.2)
        self.assertTrue(self.arena.monsters)
        self.assertTrue(all(monster.leaked for monster in self.arena.monsters.values()))
        for monster in list(self.arena.monsters.values()):
            self.arena._kill(monster, self.first)
        self.assertEqual(self.arena.essence, 0)

    def test_the_patch_wipes_out_the_leak(self) -> None:
        advance(self.arena, 0.2)
        self.arena.link(self.first.id)
        self.arena.submit_fix(self.first.id, self.task.solution)
        self.assertEqual(self.arena.monsters, {})

    def test_the_party_sees_who_is_working(self) -> None:
        self.arena.link(self.first.id)
        state = json.loads(json.dumps(self.arena.snapshot()))
        self.assertEqual(state["terminals"][0]["operator"], self.first.id)
        self.assertEqual(state["terminals"][0]["task"], self.task.key)
        self.assertTrue(next(p for p in state["players"] if p["id"] == self.first.id)["linked"])


class BossGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena = StoryArena(BOSS, 1, seed=5, now=1.0)
        self.mage = self.arena.add_player("Маг")

    def enter_boss_room(self) -> None:
        self.arena.link(self.mage.id)
        self.arena.submit_fix(self.mage.id, self.arena.terminals[0].task.solution)
        room = self.arena.dungeon.rooms[-1]
        self.mage.x, self.mage.y = room.center
        self.mage.y += 120
        advance(self.arena, 1.2)
        self.mage.invuln_until = self.arena.now + 600
        self.boss = next(m for m in self.arena.monsters.values() if m.species.boss)
        self.boss.spawned_at = 0.0

    def wound(self, share: float) -> None:
        self.boss.hp = self.boss.max_hp * share
        advance(self.arena, 0.1)

    def test_the_door_to_a_boss_is_locked_by_its_own_terminal(self) -> None:
        self.assertEqual(self.arena.terminals[0].role, "door")
        self.assertTrue(self.arena.dungeon.closed)
        self.arena.link(self.mage.id)
        self.arena.submit_fix(self.mage.id, self.arena.terminals[0].task.solution)
        self.assertFalse(self.arena.dungeon.closed)

    def test_a_wounded_boss_goes_behind_a_shield_until_its_bug_is_fixed(self) -> None:
        self.enter_boss_room()
        self.wound(0.6)
        self.assertIs(self.arena.gate_boss, self.boss)
        gate = self.arena.terminals[-1]
        self.assertEqual(gate.role, "gate")
        hp = self.boss.hp
        self.arena.damage(
            target=self.boss, amount=50, source=self.mage, kind="fire", hit_x=0.0, hit_y=0.0
        )
        self.assertEqual(self.boss.hp, hp)
        self.assertTrue(json.loads(json.dumps(self.arena.snapshot()))["story"]["boss"]["shielded"])

        self.mage.x, self.mage.y = gate.x, gate.y
        self.arena.link(self.mage.id)
        self.assertTrue(self.arena.submit_fix(self.mage.id, gate.task.solution)["ok"])
        self.assertIsNone(self.arena.gate_boss)
        self.assertLess(self.boss.hp, hp)
        self.assertGreater(self.boss.stun_until, self.arena.now)

    def test_the_gate_stands_in_the_room_the_boss_is_in(self) -> None:
        self.enter_boss_room()
        self.wound(0.6)
        gate = self.arena.terminals[-1]
        self.assertTrue(self.arena.active_room.holds(gate.x, gate.y, 1.0))
        self.assertFalse(self.arena.dungeon.blocked(gate.x, gate.y, 20))

    def test_two_gates_stand_between_a_party_and_the_kill(self) -> None:
        self.enter_boss_room()
        for share in (0.6, 0.3):
            self.wound(share)
            gate = self.arena.terminals[-1]
            self.mage.x, self.mage.y = gate.x, gate.y
            self.arena.link(self.mage.id)
            self.assertTrue(self.arena.submit_fix(self.mage.id, gate.task.solution)["ok"])
        self.wound(0.1)
        self.assertIsNone(self.arena.gate_boss)
        self.assertEqual(len(self.arena.terminals), 3)


class SpellRadarTests(unittest.TestCase):
    AIMBOT = (
        "targets = enemies()\nif targets:\n    best = targets[0]\n    for e in targets:\n"
        "        if e.dist < best.dist:\n            best = e\n"
        "    log(best.kind, best.boss)\n    fireball(direction(best.x, best.y))"
    )

    def test_a_mage_can_write_their_own_aim_in_a_dungeon(self) -> None:
        stage = STAGES[11]
        arena = StoryArena(stage, 1, seed=1, now=1.0)
        mage = arena.add_player("Маг")
        near = arena.spawn_monster("popup", mage.x + 200, mage.y)
        arena.spawn_monster("popup", mage.x, mage.y + 400)
        near.spawned_at = 0.0
        for monster in arena.monsters.values():
            monster.spawned_at = 0.0
        result = arena.cast(mage.id, self.AIMBOT, 0, 2.0)
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["log"], ["popup False"])
        self.assertAlmostEqual(arena.projectiles[0].angle, 0.0, places=2)

    def test_the_radar_stays_sealed_until_its_lesson(self) -> None:
        arena = StoryArena(STAGES[10], 1, seed=1, now=1.0)
        mage = arena.add_player("Маг")
        result = arena.cast(mage.id, "log(enemies())", 0, 0.0)
        self.assertFalse(result["ok"])
        self.assertIn("не изучена", result["error"])

    def test_the_arena_stays_a_game_of_manual_aim(self) -> None:
        arena = Arena(bots=0)
        mage = arena.add_player("Маг")
        self.assertFalse(arena.cast(mage.id, "log(enemies())", 0, 0.0)["ok"])


class RotationTests(unittest.TestCase):
    """Whoever repaired the last terminal lets someone else take the next one."""

    def setUp(self) -> None:
        self.arena = StoryArena(BOSS, 2, seed=5, now=1.0)
        self.first = self.arena.add_player("Первый")
        self.second = self.arena.add_player("Второй")
        self.arena.link(self.first.id)
        self.arena.submit_fix(self.first.id, self.arena.terminals[0].task.solution)
        task = GATES[BOSS.chapter.boss][0]
        self.next = self.arena._add_terminal(self.first.x, self.first.y, task, "gate")

    def test_the_last_fixer_sits_out_the_next_terminal(self) -> None:
        terminal, error = self.arena.link(self.first.id)
        self.assertIsNone(terminal)
        self.assertIn("другим магом", error)
        self.second.x, self.second.y = self.first.x + 20, self.first.y
        self.assertIs(self.arena.link(self.second.id)[0], self.next)

    def test_a_clock_lets_them_in_when_nobody_comes(self) -> None:
        self.assertIsNone(self.arena.link(self.first.id)[0])
        self.arena.now += ROTATION_WAIT + 0.1
        self.assertIs(self.arena.link(self.first.id)[0], self.next)

    def test_nobody_waits_for_a_fallen_friend(self) -> None:
        self.second.dead = True
        self.assertIs(self.arena.link(self.first.id)[0], self.next)

    def test_a_lone_mage_is_never_made_to_wait(self) -> None:
        arena = StoryArena(BOSS, 1, seed=5, now=1.0)
        mage = arena.add_player("Один")
        arena.last_fixer = mage.id
        self.assertIsNotNone(arena.link(mage.id)[0])


class RoleCase(unittest.TestCase):
    def make(self, stage_index: int = 10, *roles: str) -> StoryArena:
        arena = StoryArena(STAGES[stage_index], max(1, len(roles)), seed=4, now=1.0)
        room = arena.dungeon.rooms[1]
        arena.dungeon.carve(room.x, room.y, room.w, room.h)
        arena.active_room = room
        arena.wave = 99
        self.room = room
        for index, role in enumerate(roles):
            mage = arena.add_player(f"Маг {index + 1}")
            apply_role(mage, role)
            mage.x, mage.y = room.center[0] + index * 60, room.center[1] + 80
            mage.invuln_until = 0.0
        return arena

    def bug(self, arena: StoryArena, key: str = "popup", dx: float = 0.0, dy: float = -160.0):
        x, y = self.room.center
        monster = arena.spawn_monster(key, x + dx, y + dy)
        monster.spawned_at = 0.0
        monster.next_attack = 1 << 30
        monster.next_contact = 1 << 30
        return monster

    def run_code(self, arena: StoryArena, mage, code: str, cursor=None) -> dict:
        mage.cast_ready_at = 0.0
        x, y = cursor if cursor else (None, None)
        return arena.cast(mage.id, code, 0, 0.0, x, y)


class RoleBasicsTests(RoleCase):
    def test_every_role_has_a_passive_and_two_skills(self) -> None:
        self.assertEqual(set(ROLES), {"admin", "hacker", "devops", "tester"})
        for role in ROLES.values():
            self.assertTrue(role.passive)
            self.assertEqual(len(role.skills), 2)

    def test_a_role_changes_the_mage_it_is_given_to(self) -> None:
        arena = self.make(10, "admin", "hacker")
        admin, hacker = arena.players.values()
        self.assertEqual(admin.max_hp, 135)
        self.assertEqual(admin.hp, 135)
        self.assertEqual(hacker.max_hp, 80)
        self.assertAlmostEqual(hacker.perks.power, 1.25)
        self.run_code(arena, admin, "shield()")
        self.assertEqual(admin.shield, 57.0)

    def test_a_skill_belongs_to_its_role(self) -> None:
        arena = self.make(10, "admin")
        admin = next(iter(arena.players.values()))
        self.bug(arena)
        result = self.run_code(arena, admin, "exploit()")
        self.assertFalse(result["ok"])
        self.assertIn("Хакер", result["error"])
        self.assertEqual(self.run_code(arena, admin, 'log(ready("exploit"))')["log"], ["False"])

    def test_the_second_skill_waits_for_the_third_chapter(self) -> None:
        arena = self.make(5, "admin")
        admin = next(iter(arena.players.values()))
        self.assertTrue(self.run_code(arena, admin, "firewall(0)")["ok"])
        result = self.run_code(arena, admin, "sudo()")
        self.assertFalse(result["ok"])
        self.assertIn("откроется", result["error"])

    def test_a_used_skill_needs_time_and_costs_mana(self) -> None:
        arena = self.make(10, "admin")
        admin = next(iter(arena.players.values()))
        mana = admin.mana
        self.assertTrue(self.run_code(arena, admin, "firewall(0)")["ok"])
        self.assertEqual(admin.mana, mana - SKILLS["firewall"].cost)
        self.assertEqual(self.run_code(arena, admin, 'log(ready("firewall"))')["log"], ["False"])
        result = self.run_code(arena, admin, "firewall(0)")
        self.assertIn("будет готов", result["error"])

    def test_the_example_on_every_role_card_runs(self) -> None:
        for key, role in ROLES.items():
            arena = self.make(12, key)
            mage = next(iter(arena.players.values()))
            advance(arena, 0.3)
            self.bug(arena)
            with self.subTest(key):
                result = self.run_code(arena, mage, role.example, (mage.x, mage.y - 200))
                self.assertTrue(result["ok"], result["error"])

    def test_the_arena_has_no_roles(self) -> None:
        arena = Arena(bots=0)
        mage = arena.add_player("Маг")
        for code in ("sudo()", "firewall(0)", "log(allies())"):
            mage.cast_ready_at = 0.0
            self.assertFalse(arena.cast(mage.id, code, 0, 0.0)["ok"], code)

    def test_a_snapshot_carries_every_role_effect(self) -> None:
        arena = self.make(10, "admin", "tester")
        admin, tester = arena.players.values()
        self.bug(arena)
        self.run_code(arena, admin, "firewall(0)\nsudo()")
        self.run_code(arena, tester, "breakpoint(me().x, me().y)\nscan()")
        state = json.loads(json.dumps(arena.snapshot()))
        self.assertEqual(len(state["barriers"]), 1)
        self.assertEqual(len(state["breakpoints"]), 1)
        self.assertTrue(state["players"][0]["sudo"])
        self.assertEqual(state["players"][0]["role"], "admin")
        self.assertIn("sudo", state["players"][0]["skills"])
        self.assertTrue(state["monsters"][0]["exposed"])


class AdminTests(RoleCase):
    def setUp(self) -> None:
        self.arena = self.make(10, "admin", "hacker")
        self.admin, self.friend = self.arena.players.values()

    def test_a_firewall_sends_shots_back_at_the_shooter(self) -> None:
        shooter = self.bug(self.arena, "banner", dy=-300)
        shooter.x, shooter.y = self.admin.x, self.admin.y - 400
        shooter.stun_until = self.arena.now + 5.0
        angle = math.pi / 2
        self.run_code(self.arena, self.admin, f"firewall({-angle})")
        self.arena.fire(shooter, angle)
        shot = self.arena.projectiles[0]
        damage = shot.damage
        hp = shooter.hp
        advance(self.arena, 2.2)
        self.assertEqual(self.admin.hp, self.admin.max_hp)
        self.assertLess(shooter.hp, hp)
        self.assertEqual(shot.owner, self.admin.id)
        self.assertGreater(shot.damage, damage)

    def test_a_firewall_lets_friendly_shots_through(self) -> None:
        monster = self.bug(self.arena)
        hp = monster.hp
        monster.x, monster.y = self.admin.x, self.admin.y - 300
        self.run_code(self.arena, self.admin, f"firewall({-math.pi / 2})")
        self.run_code(self.arena, self.admin, f"fireball({-math.pi / 2})")
        advance(self.arena, 0.8)
        self.assertLess(monster.hp, hp)

    def test_a_firewall_fades(self) -> None:
        self.run_code(self.arena, self.admin, "firewall(0)")
        advance(self.arena, 6.2)
        self.assertEqual(self.arena.barriers, [])

    def test_sudo_makes_the_admin_untouchable_and_the_only_target(self) -> None:
        self.friend.x = self.admin.x + 500
        monster = self.bug(self.arena)
        monster.x, monster.y = self.friend.x, self.friend.y - 100
        self.run_code(self.arena, self.admin, "sudo()")
        hp = self.admin.hp
        self.arena.damage(
            target=self.admin, amount=50, source=None, kind="hazard", hit_x=0.0, hit_y=0.0
        )
        self.assertEqual(self.admin.hp, hp)
        self.assertIs(self.arena._target_of(monster, [self.admin, self.friend]), self.admin)

    def test_sudo_halves_what_friends_nearby_take(self) -> None:
        self.friend.x, self.friend.y = self.admin.x + 100, self.admin.y
        self.run_code(self.arena, self.admin, "sudo()")
        hp = self.friend.hp
        self.arena.damage(
            target=self.friend, amount=20, source=None, kind="hazard", hit_x=0.0, hit_y=0.0
        )
        self.assertEqual(hp - self.friend.hp, 10)


class HackerTests(RoleCase):
    def setUp(self) -> None:
        self.arena = self.make(12, "hacker")
        self.hacker = next(iter(self.arena.players.values()))

    def hit(self, monster, amount: float = 20.0) -> float:
        before = monster.hp
        self.arena.damage(
            target=monster, amount=amount, source=None, kind="meteor",
            hit_x=monster.x, hit_y=monster.y,
        )
        return before - monster.hp

    def test_exploit_makes_a_target_take_more_from_everyone(self) -> None:
        monster = self.bug(self.arena, "botnet")
        self.assertEqual(self.hit(monster), 20)
        self.run_code(self.arena, self.hacker, "exploit()")
        self.assertAlmostEqual(self.hit(monster), 20 * MARK_BONUS)

    def test_a_skill_can_be_aimed_with_the_list_of_enemies(self) -> None:
        healthy = self.bug(self.arena, "botnet", dx=-120)
        self.bug(self.arena, "bot", dx=120)
        code = (
            "targets = enemies()\nbest = targets[0]\nfor e in targets:\n"
            "    if e.hp > best.hp:\n        best = e\nexploit(best)"
        )
        self.assertTrue(self.run_code(self.arena, self.hacker, code)["ok"])
        self.assertGreater(healthy.marked_until, self.arena.now)

    def test_a_marked_death_is_a_segfault_that_jumps_on(self) -> None:
        first = self.bug(self.arena, dx=-40)
        second = self.bug(self.arena, dx=40)
        self.run_code(self.arena, self.hacker, f"exploit()", (first.x - 30, first.y))
        hp = second.hp
        self.arena.drain_events()
        self.arena._kill(first, self.hacker)
        kinds = [event["e"] for event in self.arena.drain_events()]
        self.assertIn("segfault", kinds)
        self.assertLess(second.hp, hp)
        self.assertGreater(second.marked_until, self.arena.now)

    def test_a_chain_of_segfaults_comes_to_an_end(self) -> None:
        bugs = [self.bug(self.arena, "firewall", dx=index * 20 - 60) for index in range(8)]
        for monster in bugs:
            monster.hp = monster.max_hp = 1.0
        self.arena.mark(bugs[0], self.hacker)
        self.arena._kill(bugs[0], self.hacker)
        marks = sum(1 for e in self.arena.drain_events() if e["e"] == "segfault")
        self.assertLessEqual(marks, SEGFAULT_JUMPS + 1)

    def test_a_hijacked_enemy_turns_on_its_own(self) -> None:
        traitor = self.bug(self.arena, dx=-30)
        victim = self.bug(self.arena, dx=30)
        traitor.next_contact = 0.0
        traitor.next_attack = 0.0
        self.run_code(self.arena, self.hacker, "hijack()", (traitor.x, traitor.y))
        self.assertNotIn(traitor, self.arena.targets_for(self.hacker.id))
        self.assertIn(traitor, self.arena.targets_for(victim.id))
        self.assertIn(victim, self.arena.targets_for(traitor.id))
        self.assertNotIn(self.hacker, self.arena.targets_for(traitor.id))
        hp = victim.hp
        advance(self.arena, 1.5)
        self.assertLess(victim.hp, hp)

    def test_a_hijack_wears_off(self) -> None:
        traitor = self.bug(self.arena)
        self.run_code(self.arena, self.hacker, "hijack()")
        self.arena.now += 8.0
        self.assertIn(traitor, self.arena.targets_for(self.hacker.id))

    def test_a_boss_cannot_be_hijacked_and_costs_nothing_to_try(self) -> None:
        self.bug(self.arena, "nullqueen")
        mana = self.hacker.mana
        result = self.run_code(self.arena, self.hacker, "hijack(enemies()[0])")
        self.assertIn("Босса", result["error"])
        self.assertEqual(self.hacker.mana, mana)

    def test_with_no_target_a_skill_leaves_the_rest_of_the_spell_alone(self) -> None:
        mana = self.hacker.mana
        result = self.run_code(self.arena, self.hacker, "exploit()\nhijack()\nlog(1)")
        self.assertTrue(result["ok"], result["error"])
        self.assertEqual(result["log"], ["1"])
        self.assertEqual(self.hacker.mana, mana)
        self.assertEqual(self.hacker.skill_ready, {})

    def test_without_a_target_hijack_passes_over_the_boss(self) -> None:
        self.bug(self.arena, "nullqueen", dx=-30)
        minion = self.bug(self.arena, "bot", dx=200)
        self.run_code(self.arena, self.hacker, "hijack()", (self.room.center[0] - 30, 0))
        self.assertGreater(minion.hacked_until, self.arena.now)

    def test_a_hijacked_summoner_summons_for_your_side(self) -> None:
        summoner = self.bug(self.arena, "botnet")
        self.run_code(self.arena, self.hacker, "hijack()")
        child = self.arena.spawn_near(summoner, "bot", 70)
        self.assertEqual(child.hacked_until, summoner.hacked_until)


class DevopsTests(RoleCase):
    def setUp(self) -> None:
        self.arena = self.make(12, "devops", "hacker")
        self.devops, self.friend = self.arena.players.values()
        self.friend.x += 700
        advance(self.arena, HISTORY_STEP * 2)

    def test_patch_heals_a_friend_from_afar_and_clears_a_slow(self) -> None:
        self.friend.hp = 20.0
        self.friend.slow_until = self.arena.now + 5
        code = (
            "team = allies()\nworst = team[0]\nfor mate in team:\n"
            "    if mate.hp < worst.hp:\n        worst = mate\npatch(worst)"
        )
        self.assertTrue(self.run_code(self.arena, self.devops, code)["ok"])
        self.assertEqual(self.friend.hp, 52.0)
        self.assertEqual(self.friend.slow_until, 0.0)

    def test_patch_does_not_raise_the_fallen(self) -> None:
        self.friend.dead = True
        code = "team = allies()\nfor mate in team:\n    if mate.dead:\n        patch(mate)"
        self.assertIn("rollback", self.run_code(self.arena, self.devops, code)["error"])

    def test_patch_spends_nothing_on_the_healthy(self) -> None:
        mana = self.devops.mana
        self.assertTrue(self.run_code(self.arena, self.devops, "patch()\nfor m in allies():\n    patch(m)")["ok"])
        self.assertEqual(self.devops.mana, mana)
        self.assertEqual(self.devops.skill_ready, {})

    def test_rollback_restores_where_a_friend_was_and_what_they_had(self) -> None:
        x, y = self.room.center
        self.arena.history[self.friend.id].appendleft((x, y, 100.0, 100.0))
        self.friend.x, self.friend.y = x + 150, y
        self.friend.hp = 5.0
        self.run_code(self.arena, self.devops, "for mate in allies():\n    if mate.hp < 10:\n        rollback(mate)")
        self.assertEqual((self.friend.x, self.friend.y), (x, y))
        self.assertEqual(self.friend.hp, self.friend.max_hp)

    def test_rollback_never_leaves_someone_worse_off(self) -> None:
        self.friend.hp = 5.0
        self.arena.history[self.friend.id].clear()
        advance(self.arena, HISTORY_STEP * 2)
        self.friend.hp = 70.0
        self.arena.rollback(self.devops, self.friend)
        self.assertEqual(self.friend.hp, 70.0)

    def test_rollback_brings_back_the_fallen(self) -> None:
        self.arena._kill(self.friend, None)
        self.assertTrue(self.friend.dead)
        code = "for mate in allies():\n    if mate.dead:\n        rollback(mate)"
        self.assertTrue(self.run_code(self.arena, self.devops, code)["ok"])
        self.assertFalse(self.friend.dead)
        self.assertGreater(self.friend.hp, 0)

    def test_with_no_target_the_skills_do_the_sensible_thing(self) -> None:
        self.arena._kill(self.friend, None)
        self.devops.hp = 20.0
        cursor = (self.friend.x, self.friend.y)
        self.assertTrue(self.run_code(self.arena, self.devops, "patch()", cursor)["ok"])
        self.assertEqual(self.devops.hp, 52.0)
        self.assertTrue(self.run_code(self.arena, self.devops, "rollback()")["ok"])
        self.assertFalse(self.friend.dead)

    def test_rollback_cannot_be_used_to_leave_a_locked_room(self) -> None:
        self.friend.x, self.friend.y = self.room.center
        self.arena.history[self.friend.id].clear()
        self.arena.history[self.friend.id].append((10.0, 10.0, 100.0, 100.0))
        self.arena.rollback(self.devops, self.friend)
        self.assertEqual((self.friend.x, self.friend.y), self.room.center)

    def test_devops_keeps_nearby_friends_going(self) -> None:
        self.friend.x, self.friend.y = self.devops.x + 100, self.devops.y
        self.friend.hp = 50.0
        self.friend.last_damage_at = self.arena.now
        advance(self.arena, 1.0)
        self.assertAlmostEqual(self.friend.hp, 51.5, places=0)
        self.friend.x += 500
        hp = self.friend.hp
        advance(self.arena, 1.0)
        self.assertEqual(self.friend.hp, hp)


class TesterTests(RoleCase):
    def setUp(self) -> None:
        self.arena = self.make(10, "tester")
        self.tester = next(iter(self.arena.players.values()))

    def test_scan_answers_with_a_dictionary_code_can_read(self) -> None:
        self.bug(self.arena, "firewall")
        code = (
            'report = scan()\nlog(report["name"], report["immune"], report["weak"])\n'
            'if "frostbolt" in report["weak"]:\n    log("лёд")'
        )
        result = self.run_code(self.arena, self.tester, code)
        self.assertTrue(result["ok"], result["error"])
        self.assertIn("fireball", result["log"][0])
        self.assertEqual(result["log"][1], "лёд")

    def test_scan_opens_up_an_immune_target_for_everyone(self) -> None:
        monster = self.bug(self.arena, "firewall")
        hp = monster.hp
        self.arena.damage(
            target=monster, amount=20, source=None, kind="fire", hit_x=monster.x, hit_y=monster.y
        )
        self.assertEqual(monster.hp, hp)
        self.run_code(self.arena, self.tester, "scan()")
        self.arena.damage(
            target=monster, amount=20, source=None, kind="fire", hit_x=monster.x, hit_y=monster.y
        )
        self.assertLess(monster.hp, hp)

    def test_runes_go_through_a_guard(self) -> None:
        monster = self.bug(self.arena, "moderator")
        monster.heading = 0.0
        hp = monster.hp
        self.arena.damage(
            target=monster, amount=20, source=self.tester, kind="meteor",
            hit_x=monster.x + 30, hit_y=monster.y,
        )
        self.assertEqual(hp - monster.hp, 20)

    def test_a_weak_spot_hurts_more_in_the_hands_of_a_tester(self) -> None:
        monster = self.bug(self.arena, "firewall")
        hp = monster.hp
        self.arena.damage(
            target=monster, amount=10, source=self.tester, kind="frost",
            hit_x=monster.x, hit_y=monster.y,
        )
        self.assertAlmostEqual(hp - monster.hp, 21.0)

    def test_a_breakpoint_stops_enemies_and_their_shots_but_not_yours(self) -> None:
        monster = self.bug(self.arena, "banner")
        monster.next_attack = 0.0
        self.arena.fire(monster, 0.0)
        shot = self.arena.projectiles[0]
        self.run_code(self.arena, self.tester, f"breakpoint({monster.x}, {monster.y})")
        x, y, shot_x = monster.x, monster.y, shot.x
        count = len(self.arena.projectiles)
        advance(self.arena, 1.0)
        self.assertEqual((monster.x, monster.y), (x, y))
        self.assertEqual(shot.x, shot_x)
        self.assertEqual(len(self.arena.projectiles), count)
        self.assertTrue(json.loads(json.dumps(self.arena.snapshot()))["monsters"][0]["frozen"])
        hp = monster.hp
        self.tester.x, self.tester.y = monster.x, monster.y + 200
        self.run_code(self.arena, self.tester, f"fireball({-math.pi / 2})")
        advance(self.arena, 0.8)
        self.assertLess(monster.hp, hp)

    def test_time_comes_back(self) -> None:
        monster = self.bug(self.arena, "banner")
        self.arena.fire(monster, 0.0)
        shot = self.arena.projectiles[0]
        self.run_code(self.arena, self.tester, f"breakpoint({monster.x}, {monster.y})")
        advance(self.arena, 3.5)
        self.assertEqual(self.arena.breakpoints, [])
        self.assertGreater(shot.x, monster.x + 60)


class RolePickTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ProfileStore()
        self.party = Party("TEST", self.store)
        self.party.join(TOKEN_A, "Маг")

    def test_roles_open_after_the_first_chapter(self) -> None:
        self.assertIn("после первой главы", self.party.pick_role(TOKEN_A, "admin"))
        self.store.get(TOKEN_A).cleared = ROLE_STAGE
        self.assertIsNone(self.party.pick_role(TOKEN_A, "admin"))
        self.assertEqual(self.party.describe(TOKEN_A)["seats"][0]["role"], "admin")

    def test_an_unknown_role_is_refused(self) -> None:
        self.store.get(TOKEN_A).cleared = ROLE_STAGE
        self.assertTrue(self.party.pick_role(TOKEN_A, "root"))

    def test_the_role_reaches_the_dungeon_only_from_the_second_chapter(self) -> None:
        profile = self.store.get(TOKEN_A)
        profile.cleared, profile.role = ROLE_STAGE, "hacker"
        self.party.stage_index = 0
        self.party.set_ready(TOKEN_A, True, 1.0)
        mage = next(iter(self.party.world.players.values()))
        self.assertEqual(mage.role, "")

        party = Party("LATE", self.store)
        party.join(TOKEN_A, "Маг")
        party.stage_index = ROLE_STAGE
        party.set_ready(TOKEN_A, True, 1.0)
        mage = next(iter(party.world.players.values()))
        self.assertEqual(mage.role, "hacker")
        self.assertEqual(mage.max_hp, 80)

    def test_the_turn_at_the_keyboard_carries_over_to_the_next_stage(self) -> None:
        self.party.join(TOKEN_B, "Друг")
        self.party.set_ready(TOKEN_A, True, 1.0)
        self.party.set_ready(TOKEN_B, True, 1.0)
        world = self.party.world
        world.last_fixer = self.party.seat_of(TOKEN_B).player_id
        world.outcome = "cleared"
        self.party.tick(2.0)
        self.party.set_ready(TOKEN_A, True, 3.0)
        self.party.set_ready(TOKEN_B, True, 3.0)
        self.assertEqual(
            self.party.world.last_fixer, self.party.seat_of(TOKEN_B).player_id
        )

    def test_the_role_survives_a_restart(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profiles.json"
            store = ProfileStore(path)
            store.get(TOKEN_A).role = "tester"
            store.mark()
            store.save()
            self.assertEqual(ProfileStore(path).get(TOKEN_A).role, "tester")


class ProfileTests(unittest.TestCase):
    def test_upgrades_change_a_mage(self) -> None:
        arena = StoryArena(FIRST, 1, seed=1, now=1.0)
        mage = arena.add_player("Маг")
        profile = Profile("x", upgrades={"max_hp": 2, "max_mana": 1, "hp_regen": 1, "mana_regen": 1})
        profile.apply_to(mage)
        self.assertGreater(mage.max_hp, MAX_HP)
        self.assertGreater(mage.max_mana, MAX_MANA)
        self.assertGreater(mage.mana_regen, MANA_REGEN)
        self.assertGreater(mage.hp_regen, 0)
        self.assertEqual(mage.hp, mage.max_hp)

    def test_regeneration_upgrade_works_during_a_fight(self) -> None:
        arena = StoryArena(FIRST, 1, seed=1, now=1.0)
        mage = arena.add_player("Маг")
        Profile("x", upgrades={"max_hp": 1, "hp_regen": 1}).apply_to(mage)
        mage.hp = 50.0
        mage.last_damage_at = arena.now
        advance(arena, 1.0)
        self.assertGreater(mage.hp, 50.0)

    def test_a_branch_must_be_climbed_in_order(self) -> None:
        profile = Profile("x", essence=10_000)
        self.assertIsNotNone(profile.buy("hp_regen"))
        self.assertIsNone(profile.buy("max_hp"))
        self.assertIsNone(profile.buy("hp_regen"))
        self.assertIsNotNone(profile.buy("hp_regen"), "regen may not outrun its parent")

    def test_prices_are_charged_and_levels_stop_at_the_top(self) -> None:
        profile = Profile("x", essence=upgrade_cost(0))
        self.assertIsNone(profile.buy("max_mana"))
        self.assertEqual(profile.essence, 0)
        self.assertIsNotNone(profile.buy("max_mana"), "no essence left")
        profile = Profile("x", essence=100_000, upgrades={"max_mana": MAX_UPGRADE_LEVEL})
        self.assertIsNotNone(profile.buy("max_mana"))

    def test_an_unknown_upgrade_is_refused(self) -> None:
        self.assertIsNotNone(Profile("x", essence=999).buy("__class__"))

    def test_progress_survives_a_restart(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "saves" / "profiles.json"
            store = ProfileStore(path)
            profile = store.get(TOKEN_A)
            profile.essence = 77
            profile.cleared = 5
            store.mark()
            store.save()
            again = ProfileStore(path).get(TOKEN_A)
            self.assertEqual((again.essence, again.cleared), (77, 5))
            self.assertNotIn(TOKEN_A, path.read_text(encoding="utf-8"), "tokens stay secret")

    def test_a_damaged_save_does_not_stop_the_server(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profiles.json"
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(ProfileStore(path).get(TOKEN_A).essence, 0)


class PerkTests(unittest.TestCase):
    """Every upgrade must change what actually happens in a fight."""

    def setUp(self) -> None:
        self.arena = StoryArena(STAGES[6], 2, seed=2, now=1.0)
        self.mage = self.arena.add_player("Маг")
        self.friend = self.arena.add_player("Друг")
        self.mage.invuln_until = 0.0
        self.friend.invuln_until = 0.0
        room = self.arena.dungeon.rooms[1]
        # These tests are about numbers, not about which pillars a seed dealt.
        self.arena.dungeon.carve(room.x, room.y, room.w, room.h)
        self.arena.active_room = room
        x, y = room.center
        self.mage.x, self.mage.y = x, y + 40
        self.monster = self.arena.spawn_monster("popup", x, y - 140)
        self.monster.spawned_at = 0.0
        self.monster.invuln_until = 0.0

    def buy(self, player, **levels: int) -> None:
        Profile("x", upgrades=levels).apply_to(player)

    def strike(self, source, amount: float = 20.0) -> float:
        before = self.monster.hp
        self.arena.damage(
            target=self.monster, amount=amount, source=source, kind="frost",
            hit_x=self.monster.x + 1, hit_y=self.monster.y,
        )
        return before - self.monster.hp

    def test_every_upgrade_in_the_tree_is_wired_up(self) -> None:
        plain = Profile("x")
        for stat in UPGRADES:
            with self.subTest(stat):
                arena = StoryArena(FIRST, 1, seed=1, now=1.0)
                base = arena.add_player("Без")
                plain.apply_to(base)
                boosted = arena.add_player("С")
                Profile("y", upgrades={stat: 3}).apply_to(boosted)
                fields = ("max_hp", "max_mana", "hp_regen", "mana_regen", "speed", "cast_lock", "roll_cooldown")
                before = (*[getattr(base, name) for name in fields], base.perks)
                after = (*[getattr(boosted, name) for name in fields], boosted.perks)
                if stat == "fortune":
                    self.assertGreater(Profile("y", upgrades={stat: 3}).essence_rate(), 1.0)
                else:
                    self.assertNotEqual(before, after, "buying it changes nothing")

    def test_power_raises_rune_damage(self) -> None:
        self.buy(self.mage, spell_power=5)
        self.assertAlmostEqual(self.strike(self.mage), 26.0)

    def test_a_critical_hit_doubles_damage(self) -> None:
        self.buy(self.mage, crit=5)
        self.arena.rng.random = lambda: 0.0
        self.arena.drain_events()
        self.assertAlmostEqual(self.strike(self.mage), 40.0)
        self.assertIn("crit", [event["e"] for event in self.arena.drain_events()])

    def test_armor_softens_what_hits_a_mage(self) -> None:
        self.buy(self.mage, armor=5)
        self.mage.invuln_until = 0.0
        before = self.mage.hp
        self.arena.damage(target=self.mage, amount=10, source=None, kind="hazard", hit_x=0, hit_y=0)
        self.assertAlmostEqual(before - self.mage.hp, 8.0)

    def test_monsters_get_no_share_of_a_mage_perks(self) -> None:
        self.buy(self.mage, spell_power=5, armor=5)
        self.assertEqual(self.strike(self.monster), 20.0)

    def test_a_kill_refills_mana(self) -> None:
        self.buy(self.mage, kill_mana=5)
        self.mage.mana = 10.0
        self.arena._kill(self.monster, self.mage, "frost")
        self.assertEqual(self.mage.mana, 25.0)

    def test_concentration_shortens_the_cast_lock(self) -> None:
        self.buy(self.mage, cast_speed=5)
        result = self.arena.cast(self.mage.id, "fireball(0)", 0, 0.0)
        self.assertAlmostEqual(result["cooldown"], 0.52)
        self.assertAlmostEqual(self.mage.cast_ready_at, self.arena.now + 0.52)

    def test_lightness_means_covering_more_ground(self) -> None:
        self.buy(self.mage, move_speed=5)
        arena = self.arena
        arena.set_input(self.friend.id, up=False, down=False, left=True, right=False)
        arena.set_input(self.mage.id, up=False, down=False, left=False, right=True)
        room = arena.dungeon.rooms[1]
        x, y = room.center
        self.mage.x, self.friend.x = x + 40, x - 40
        self.mage.y = self.friend.y = y + 64
        self.monster.x, self.monster.y = x, y - 300
        advance(arena, 0.5)
        self.assertGreater(self.mage.x - (x + 40), (x - 40 - self.friend.x) * 1.15)

    def test_tumble_brings_the_roll_back_sooner(self) -> None:
        self.buy(self.mage, roll_cd=5)
        result = self.arena.roll(self.mage.id, aim=0.0)
        self.assertTrue(result["ok"], result)
        self.assertAlmostEqual(result["cooldown"], 0.9)

    def test_instinct_makes_pickups_stronger_and_reach_further(self) -> None:
        self.buy(self.mage, alchemy=5)
        self.mage.hp = 10.0
        self.arena._add_pickup("hp", self.mage.x + 170, self.mage.y)
        advance(self.arena, 0.8)
        self.assertEqual(self.arena.pickups, [], "a far sphere should be drawn in")
        self.assertGreater(self.mage.hp, 10.0 + 16.0)

    def test_a_rescuer_lifts_a_friend_faster(self) -> None:
        self.buy(self.friend, rescue=5)
        self.mage.hp = 1
        self.arena.damage(target=self.mage, amount=50, source=None, kind="hazard", hit_x=0, hit_y=0)
        self.friend.x, self.friend.y = self.mage.x + 40, self.mage.y
        advance(self.arena, REVIVE_TIME * 0.5)
        self.assertFalse(self.mage.dead)

    def test_a_charm_shields_the_party_as_a_fight_starts(self) -> None:
        arena = StoryArena(STAGES[8], 1, seed=4, now=1.0)
        mage = arena.add_player("Маг")
        self.buy(mage, ward_shield=5)
        mage.x, mage.y = arena.dungeon.rooms[1].center
        mage.y += 60
        advance(arena, 0.2)
        self.assertEqual(mage.shield, 40.0)

    def test_fortune_pays_each_mage_their_own_share(self) -> None:
        store = ProfileStore()
        store.get(TOKEN_A).upgrades["fortune"] = 5
        party = Party("ABCD", store)
        party.join(TOKEN_A, "Везунчик")
        party.join(TOKEN_B, "Друг")
        party.set_ready(TOKEN_A, True, 1.0)
        party.set_ready(TOKEN_B, True, 1.0)
        party.world.outcome = "cleared"
        party.world.essence = 76
        party.tick(party.world.now + TICK)
        # Tickets pay the same to everybody; fortune only touches the stage's pay.
        tickets = sum(ticket.reward for ticket in TICKETS[0] if ticket.key in ("0:clean_run", "0:sla"))
        self.assertEqual(store.get(TOKEN_B).essence, 100 + tickets)
        self.assertEqual(store.get(TOKEN_A).essence, 125 + tickets)

    def test_the_arena_never_sees_an_upgrade(self) -> None:
        arena = Arena(bots=0)
        mage = arena.add_player("Дуэлянт")
        self.assertEqual(mage.speed, MOVE_SPEED)
        self.assertEqual(mage.cast_lock, CAST_LOCK)
        self.assertEqual(mage.roll_cooldown, ROLL_COOLDOWN)
        self.assertIsNone(mage.perks)


class TreeShapeTests(unittest.TestCase):
    def test_every_branch_is_a_ladder_of_three(self) -> None:
        for branch in BRANCHES:
            rungs = [stat for stat, entry in UPGRADES.items() if entry["branch"] == branch]
            self.assertEqual(len(rungs), 3, branch)
            self.assertNotIn("needs", UPGRADES[rungs[0]])
            self.assertEqual(UPGRADES[rungs[1]]["needs"], rungs[0])
            self.assertEqual(UPGRADES[rungs[2]]["needs"], rungs[1])

    def test_the_last_rung_waits_for_the_one_above(self) -> None:
        profile = Profile("x", essence=10_000, upgrades={"max_hp": 2, "hp_regen": 1})
        self.assertIsNone(profile.buy("armor"))
        self.assertIsNotNone(profile.buy("armor"), "armor may not outrun regeneration")

    def test_top_rungs_cost_half_as_much_again(self) -> None:
        self.assertEqual(upgrade_cost(0, "max_hp"), 40)
        self.assertEqual(upgrade_cost(0, "armor"), 60)
        self.assertEqual(upgrade_cost(4, "rescue"), 300)

    def test_saves_from_before_the_new_branches_still_load(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profiles.json"
            token_hash = ProfileStore.hash_token(TOKEN_A)
            path.write_text(
                json.dumps({token_hash: {"essence": 5, "cleared": 3, "upgrades": {"max_hp": 2}, "lessons": []}}),
                encoding="utf-8",
            )
            profile = ProfileStore(path).get(TOKEN_A)
            self.assertEqual(profile.level("max_hp"), 2)
            self.assertEqual(profile.level("armor"), 0)
            self.assertIsNone(Profile("y", essence=500, upgrades=profile.upgrades).buy("spell_power"))


class PartyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ProfileStore()
        self.party = Party("ABCD", self.store)
        self.party.join(TOKEN_A, "Лидер")

    def finish(self, outcome: str) -> None:
        self.party.world.outcome = outcome
        self.party.world.essence = 40
        self.party.tick(self.party.world.now + TICK)

    def test_a_stage_starts_when_everyone_is_ready(self) -> None:
        self.party.join(TOKEN_B, "Друг")
        self.party.set_ready(TOKEN_A, True, 1.0)
        self.assertEqual(self.party.state, CAMP)
        self.party.set_ready(TOKEN_B, True, 1.0)
        self.assertEqual(self.party.state, PLAYING)
        self.assertEqual(len(self.party.world.players), 2)

    def test_a_fifth_mage_is_turned_away(self) -> None:
        for index in range(3):
            self.party.join(f"{index}" * 32, f"Маг {index}")
        seat, error = self.party.join("9" * 32, "Лишний")
        self.assertIsNone(seat)
        self.assertIn("четыре", error)

    def test_clearing_a_stage_pays_everyone_and_moves_on(self) -> None:
        self.party.join(TOKEN_B, "Друг")
        self.party.set_ready(TOKEN_A, True, 1.0)
        self.party.set_ready(TOKEN_B, True, 1.0)
        self.finish("cleared")
        self.assertEqual(self.party.state, CAMP)
        self.assertEqual(self.party.stage_index, 1)
        # On top of the stage's pay, this run closed two tickets: nobody fell, the SLA held.
        reward = 40 + STAGES[0].clear_bonus + sum(
            ticket.reward for ticket in TICKETS[0] if ticket.key in ("0:clean_run", "0:sla")
        )
        self.assertEqual(self.store.get(TOKEN_A).essence, reward)
        self.assertEqual(self.store.get(TOKEN_B).essence, reward)
        self.assertEqual(self.store.get(TOKEN_B).cleared, 1)

    def test_a_wipe_keeps_half_the_essence_and_stays_on_the_stage(self) -> None:
        self.party.set_ready(TOKEN_A, True, 1.0)
        self.finish("wiped")
        self.assertEqual(self.party.stage_index, 0)
        self.assertEqual(self.store.get(TOKEN_A).essence, 20)
        self.assertEqual(self.store.get(TOKEN_A).cleared, 0)

    def test_only_the_leader_picks_a_stage_and_only_an_open_one(self) -> None:
        self.party.join(TOKEN_B, "Друг")
        self.store.get(TOKEN_A).cleared = 3
        self.assertIsNotNone(self.party.choose_stage(TOKEN_B, 1))
        self.assertIsNotNone(self.party.choose_stage(TOKEN_A, 4))
        self.assertIsNone(self.party.choose_stage(TOKEN_A, 3))
        self.assertEqual(self.party.stage_index, 3)

    def test_a_dropped_mage_keeps_their_seat(self) -> None:
        self.party.join(TOKEN_B, "Друг")
        self.party.set_ready(TOKEN_A, True, 1.0)
        self.party.set_ready(TOKEN_B, True, 1.0)
        self.party.disconnect(TOKEN_B, 2.0)
        self.assertEqual(len(self.party.world.players), 1)
        seat, error = self.party.join(TOKEN_B, "Друг")
        self.assertIsNone(error)
        self.party.place(seat)
        self.assertEqual(len(self.party.world.players), 2)

    def test_an_abandoned_party_is_forgotten(self) -> None:
        self.party.disconnect(TOKEN_A, 1.0)
        self.party.tick(1.0)
        self.assertFalse(self.party.expired(10.0))
        self.assertTrue(self.party.expired(1000.0))

    def test_finishing_the_last_boss_ends_the_campaign(self) -> None:
        self.store.get(TOKEN_A).cleared = 19
        self.party.stage_index = 19
        self.party.set_ready(TOKEN_A, True, 1.0)
        self.finish("cleared")
        self.assertEqual(self.party.state, FINISHED)
        self.assertTrue(self.party.last_result["finale"])

    def test_a_lesson_pays_only_once(self) -> None:
        first = self.party.reward_fix(TOKEN_A, "call")
        self.assertGreater(first, 0)
        self.assertEqual(self.party.reward_fix(TOKEN_A, "call"), 0)


class PlaythroughTests(unittest.TestCase):
    """A scripted party proves a stage can actually be finished, start to portal."""

    def test_a_dungeon_and_every_boss_can_be_beaten(self) -> None:
        for index in (0, 3, 7, 11, 15, 19):
            stage = STAGES[index]
            level = stage.chapter_index + 1
            profile = Profile(
                "x",
                upgrades={"max_hp": level, "hp_regen": level, "max_mana": level, "mana_regen": level},
            )
            with self.subTest(stage=stage.title):
                # Two mages: alone, one unlucky death ends a boss fight, as it should.
                arena = play_stage(stage, 2, profile, seed=2, seconds=420)
                self.assertEqual(arena.outcome, "cleared")

    def test_a_full_party_can_finish_a_dungeon_together(self) -> None:
        arena = play_stage(STAGES[2], 4, seed=2, seconds=420)
        self.assertEqual(arena.outcome, "cleared")
        self.assertEqual(len(arena.players), 4)

    def test_a_party_of_all_four_roles_finishes_a_stage(self) -> None:
        arena = play_stage(STAGES[10], 4, seed=3, seconds=900, roles=tuple(ROLES))
        self.assertEqual(arena.outcome, "cleared")
        self.assertEqual({mage.role for mage in arena.players.values()}, set(ROLES))

    def test_monster_ids_never_collide_with_mages(self) -> None:
        arena = play_stage(STAGES[0], 2, seed=1, seconds=30)
        self.assertTrue(all(player_id < MONSTER_ID_BASE for player_id in arena.players))


class DifficultyTests(unittest.TestCase):
    def arena_at(self, level: int) -> tuple[StoryArena, object]:
        arena = StoryArena(FIRST, 1, seed=7, now=1.0, difficulty=level)
        return arena, arena.add_player("Маг")

    def plugged_in(self, level: int) -> tuple[StoryArena, object, object]:
        arena, mage = self.arena_at(level)
        terminal = arena.terminals[0]
        mage.x, mage.y = terminal.x, terminal.y + 40
        self.assertIsNotNone(arena.link(mage.id)[0])
        return arena, mage, terminal.task

    def steps(self, arena: StoryArena, mage: object) -> list[dict]:
        return [arena.terminal_help(mage.id, index) for index in range(4)]

    def test_a_junior_gets_both_hints_and_then_the_solution(self) -> None:
        arena, mage, task = self.plugged_in(1)
        steps = self.steps(arena, mage)
        self.assertEqual([step["kind"] for step in steps], ["hint", "hint", "solution", ""])
        self.assertEqual(steps[2]["text"], task.solution)

    def test_a_middle_gets_hints_but_never_the_solution(self) -> None:
        arena, mage, task = self.plugged_in(2)
        steps = self.steps(arena, mage)
        self.assertEqual([step["kind"] for step in steps], ["hint", "hint", "", ""])
        self.assertNotIn(task.solution, [step["text"] for step in steps])

    def test_a_senior_gets_nothing_at_all(self) -> None:
        arena, mage, _ = self.plugged_in(3)
        self.assertEqual(self.steps(arena, mage), [{"kind": "", "text": ""}] * 4)
        self.assertEqual(
            arena.help_plan(), {"hints": 0, "solution": False, "theory": False}
        )

    def test_help_needs_a_terminal_and_a_sane_index(self) -> None:
        arena, mage = self.arena_at(1)
        self.assertEqual(arena.terminal_help(mage.id, 0)["kind"], "")
        arena, mage, _ = self.plugged_in(1)
        self.assertEqual(arena.terminal_help(mage.id, -1)["kind"], "")
        self.assertEqual(arena.terminal_help(mage.id, 99)["kind"], "")

    def test_answers_are_not_sent_to_the_browser_in_advance(self) -> None:
        for task in TASKS.values():
            sent = task.describe()
            self.assertNotIn("solution", sent)
            self.assertNotIn("hints", sent)
            self.assertNotIn(task.solution, json.dumps(sent, ensure_ascii=False))

    def test_no_hint_gives_a_whole_solution_away(self) -> None:
        for task in TASKS.values():
            lines = [line.strip() for line in task.solution.splitlines() if line.strip()]
            for hint in task.hints:
                with self.subTest(task=task.key):
                    self.assertLess(sum(line in hint for line in lines), len(lines))

    def test_level_one_leaves_ordinary_monsters_alone(self) -> None:
        arena, _ = self.arena_at(1)
        popup = arena.spawn_monster("popup", 400, 400)
        self.assertEqual(popup.max_hp, SPECIES["popup"].hp)

    def test_each_level_is_tougher_than_the_last(self) -> None:
        levels = [DIFFICULTIES[level] for level in (1, 2, 3)]
        for easier, harder in zip(levels, levels[1:]):
            self.assertGreater(harder.toughness, easier.toughness)
            self.assertGreater(harder.damage, easier.damage)
            self.assertGreater(harder.crowd, easier.crowd)
            self.assertLess(harder.tempo, easier.tempo)
            self.assertGreater(harder.reward, easier.reward)

    def test_a_senior_takes_more_damage_and_bugs_have_more_health(self) -> None:
        arena, mage = self.arena_at(3)
        popup = arena.spawn_monster("popup", mage.x + 400, mage.y)
        self.assertAlmostEqual(popup.max_hp, SPECIES["popup"].hp * DIFFICULTIES[3].toughness)
        mage.invuln_until = 0.0
        arena.damage(target=mage, amount=10, source=popup, kind="orb", hit_x=mage.x, hit_y=mage.y)
        self.assertAlmostEqual(mage.hp, mage.max_hp - 10 * DIFFICULTIES[3].damage)

    def test_ada_keeps_quiet_on_senior(self) -> None:
        for level, chatty in ((1, True), (2, True), (3, False)):
            arena, _ = self.arena_at(level)
            boss = arena.spawn_monster("bracket", 400, 400)
            arena.drain_events()
            arena.announce(boss, "hex")
            arena.announce(boss, "hex")
            casts = [e for e in arena.drain_events() if e["e"] == "boss_cast"]
            self.assertEqual(bool(casts[0]["tip"]), chatty)
            self.assertEqual(casts[1]["tip"], "", "she explains an attack only once")
            self.assertEqual(casts[0]["error"], ATTACKS["hex"].error)


class PartyDifficultyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ProfileStore(Path(self.tmp.name) / "profiles.json")
        self.party = Party("ABCD", self.store)
        self.party.join(TOKEN_A, "Первый")
        self.party.join(TOKEN_B, "Второй")

    def test_the_leader_chooses_and_everyone_sees_it(self) -> None:
        self.assertEqual(self.party.describe(TOKEN_A)["difficulty"], 1)
        self.assertIsNotNone(self.party.choose_difficulty(TOKEN_B, 3))
        self.assertIsNone(self.party.choose_difficulty(TOKEN_A, 3))
        self.assertEqual(self.party.describe(TOKEN_B)["difficulty"], 3)

    def test_there_are_only_three_levels(self) -> None:
        self.assertEqual(sorted(DIFFICULTIES), [1, 2, 3])
        self.assertIsNotNone(self.party.choose_difficulty(TOKEN_A, 4))
        self.assertIsNotNone(self.party.choose_difficulty(TOKEN_A, 0))

    def test_a_stage_runs_on_the_chosen_level_and_it_cannot_change_midway(self) -> None:
        self.party.choose_difficulty(TOKEN_A, 2)
        self.party.start_stage(1.0)
        self.assertEqual(self.party.world.difficulty.level, 2)
        self.assertIsNotNone(self.party.choose_difficulty(TOKEN_A, 3))

    def test_a_harder_level_pays_more(self) -> None:
        earned = {}
        for level in (1, 3):
            party = Party("ABCD", ProfileStore(Path(self.tmp.name) / f"{level}.json"))
            party.join(TOKEN_A, "Первый")
            party.choose_difficulty(TOKEN_A, level)
            party.start_stage(1.0)
            party.world.essence = 100
            party.world.outcome = "cleared"
            party._finish_stage()
            earned[level] = party.rewards[TOKEN_A]
        self.assertAlmostEqual(earned[3] / earned[1], DIFFICULTIES[3].reward, places=1)


class BossAttackTests(unittest.TestCase):
    """Every boss in its own room, with a mage who stays out of the fight's way."""

    BOSS_OF = {stage.chapter.boss: stage for stage in STAGES if stage.is_boss}
    MOVES = {
        "bracket": {"pincer", "hex", "indent"},
        "scroll": {"feed", "loop", "retain"},
        "nullqueen": {"null", "assign", "echo"},
        "indexer": {"sweep", "offby", "swap", "bounds"},
        "pgt": {"mirror", "patch", "deploy"},
    }

    def fight(self, key: str, mages: int = 1, level: int = 1) -> None:
        stage = self.BOSS_OF[key]
        self.arena = StoryArena(stage, mages, seed=5, now=1.0, difficulty=level)
        self.mages = [self.arena.add_player(f"Маг {n}") for n in range(mages)]
        self.mage = self.mages[0]
        terminal = self.arena.terminals[0]
        self.mage.x, self.mage.y = terminal.x, terminal.y + 40
        self.arena.link(self.mage.id)
        self.arena.submit_fix(self.mage.id, terminal.task.solution)
        self.room = self.arena.dungeon.rooms[-1]
        for index, mage in enumerate(self.mages):
            mage.x, mage.y = self.room.center
            mage.x += index * 200 - 100 * (mages - 1)
            mage.y += 200
        advance(self.arena, 1.2)
        self.boss = next(m for m in self.arena.monsters.values() if m.species.boss)
        self.boss.spawned_at = 0.0
        self.arena.drain_events()

    def spell(self, code: str, **kwargs) -> dict:
        self.mage.cast_ready_at = 0.0
        return self.arena.cast(self.mage.id, code, **kwargs)

    def test_every_attack_has_a_real_line_of_code_and_a_tip(self) -> None:
        for key, attack in ATTACKS.items():
            with self.subTest(attack=key):
                self.assertTrue(attack.error.strip())
                self.assertTrue(attack.tip.strip())

    def test_every_boss_really_uses_all_of_its_attacks(self) -> None:
        for key, moves in self.MOVES.items():
            with self.subTest(boss=key):
                self.fight(key)
                seen: set[str] = set()
                wanted = {ATTACKS[move].error: move for move in moves}
                for share in (0.9, 0.5, 0.2):
                    # Below a gate threshold the boss hides: let it fight on regardless.
                    self.arena.gates_left = []
                    for boss in self.arena.monsters.values():
                        if boss.species.boss:
                            boss.hp = boss.max_hp * share
                    for _ in range(int(70 * TICK_RATE)):
                        self.mage.hp = self.mage.max_hp
                        self.mage.invuln_until = self.arena.now + 1
                        for monster in list(self.arena.monsters.values()):
                            if monster.species.boss:
                                monster.deploy_hp = monster.hp
                            elif monster.minion:
                                self.arena.remove_monster(monster)
                        self.arena.update(self.arena.now + TICK)
                        seen |= {
                            wanted[event["error"]]
                            for event in self.arena.drain_events()
                            if event["e"] == "boss_cast" and event["error"] in wanted
                        }
                self.assertEqual(seen, moves)

    def test_bosses_get_faster_on_each_level(self) -> None:
        counts = {}
        for level in (1, 3):
            self.fight("bracket", level=level)
            self.boss.hp = self.boss.max_hp
            for _ in range(int(30 * TICK_RATE)):
                self.mage.hp = self.mage.max_hp
                self.mage.invuln_until = self.arena.now + 1
                self.arena.update(self.arena.now + TICK)
            counts[level] = self.boss.strikes
        self.assertGreater(counts[3], counts[1])

    # ------------------------------------------------------------ the bracket
    def test_syntax_curse_stops_spells_until_it_wears_off(self) -> None:
        self.fight("bracket")
        self.arena.curse(self.mage, "syntax")
        refused = self.spell("fireball(aim())")
        self.assertFalse(refused["ok"])
        self.assertIn("SyntaxError", refused["error"])
        for _ in range(int((CURSES["syntax"] + 0.2) * TICK_RATE)):
            self.mage.invuln_until = self.arena.now + 1
            self.arena.update(self.arena.now + TICK)
        self.assertTrue(self.spell("fireball(aim())")["ok"])

    def test_a_curse_circle_can_be_stepped_out_of(self) -> None:
        self.fight("bracket")
        self.arena.place_hazard(
            self.boss, self.mage.x, self.mage.y, radius=100, delay=0.3, damage=10,
            color="#fff", effect="syntax",
        )
        self.mage.x += 300
        advance(self.arena, 0.5)
        self.assertFalse(self.mage.curses)

    def test_standing_still_in_the_brackets_is_a_hit_not_a_death(self) -> None:
        from arcane.monsters import _brackets

        self.fight("bracket")
        self.boss.next_attack = self.boss.next_special = math.inf
        self.arena.monsters.clear()
        self.arena.monsters[self.boss.id] = self.boss
        self.boss.stun_until = math.inf
        _brackets(self.arena, self.boss, self.mage, 0.0)
        advance(self.arena, 4.0)
        self.assertGreater(self.mage.hp, self.mage.max_hp * 0.6)

    # ------------------------------------------------------------- the scroll
    def test_the_loop_drags_you_back_and_you_have_time_to_leave(self) -> None:
        from arcane.monsters import _loop_back

        self.fight("scroll")
        self.boss.stun_until = math.inf
        start = self.mage.x, self.mage.y
        _loop_back(self.arena, self.boss)
        self.mage.x += 250
        advance(self.arena, LOOP_PULL + 0.1)
        self.assertEqual((self.mage.x, self.mage.y), start, "pulled back to the old spot")
        hp = self.mage.hp
        self.mage.invuln_until = 0.0
        self.mage.y -= (LOOP_FUSE - LOOP_PULL - 0.15) * MOVE_SPEED * 0.9
        advance(self.arena, LOOP_FUSE - LOOP_PULL + 0.1)
        self.assertEqual(self.mage.hp, hp, "a mage who runs at once gets away")

    def test_retention_pulls_mages_but_they_can_outrun_it(self) -> None:
        from arcane.monsters import RETAIN_PULL

        self.assertLess(max(RETAIN_PULL), MOVE_SPEED * 0.8)
        self.fight("scroll")
        self.boss.next_special = 0.0
        self.boss.specials = 4
        advance(self.arena, 0.2)
        self.assertEqual(self.boss.state, "retain")
        before = math.hypot(self.mage.x - self.boss.x, self.mage.y - self.boss.y)
        self.boss.next_attack = math.inf
        advance(self.arena, 1.0)
        after = math.hypot(self.mage.x - self.boss.x, self.mage.y - self.boss.y)
        self.assertLess(after, before)

    def test_the_feed_wall_has_a_way_through(self) -> None:
        from arcane.monsters import FEED_GAP, _feed

        for seed in range(12):
            self.fight("scroll")
            self.arena.rng = random.Random(seed)
            self.arena.projectiles.clear()
            _feed(self.arena, self.boss)
            shots = self.arena.projectiles
            self.assertGreater(len(shots), 10)
            sideways = abs(math.cos(shots[0].angle)) < 0.5
            line = sorted(shot.x if sideways else shot.y for shot in shots)
            self.assertGreaterEqual(
                max(b - a for a, b in zip(line, line[1:])), FEED_GAP * 0.9, f"seed {seed}"
            )

    # -------------------------------------------------------------- the queen
    def test_null_curse_turns_lookups_into_none(self) -> None:
        self.fight("nullqueen")
        self.arena.curse(self.mage, "null")
        result = self.spell("log(enemies(), allies(), cursor())", target_x=0.0, target_y=0.0)
        self.assertTrue(result["ok"], result["error"])
        self.assertEqual(result["log"], ["None None None"])

    def test_null_curse_breaks_careless_code_and_spares_careful_code(self) -> None:
        self.fight("nullqueen")
        self.arena.curse(self.mage, "null")
        careless = self.spell("for e in enemies():\n    log(e.hp)")
        self.assertFalse(careless["ok"])
        careful = self.spell("targets = enemies()\nif targets:\n    log(1)\nfireball(aim())")
        self.assertTrue(careful["ok"], careful["error"])

    def test_copies_look_like_her_but_only_she_is_the_boss(self) -> None:
        from arcane.monsters import _echoes

        self.fight("nullqueen")
        _echoes(self.arena, self.boss)
        advance(self.arena, 0.7)
        copies = [m for m in self.arena.monsters.values() if m.species.key == "nullecho"]
        self.assertGreaterEqual(len(copies), 2)
        self.assertTrue(all(copy.name == self.boss.name for copy in copies))
        result = self.spell(
            "found = 0\nfor e in enemies():\n    if e.boss:\n        found += 1\nlog(found)"
        )
        self.assertEqual(result["log"], ["1"], result["error"])
        essence = self.arena.essence
        self.arena._kill(copies[0], self.mage, "fire")
        self.assertEqual(self.arena.essence, essence, "a copy is worth nothing")

    def test_copies_do_not_outlive_their_queen_or_their_time(self) -> None:
        from arcane.monsters import ECHO_TIME, _echoes

        self.fight("nullqueen")
        _echoes(self.arena, self.boss)
        self.mage.invuln_until = self.arena.now + 60
        for _ in range(int((ECHO_TIME + 1.5) * TICK_RATE)):
            self.boss.next_special = math.inf
            self.arena.update(self.arena.now + TICK)
        self.assertFalse([m for m in self.arena.monsters.values() if m.species.key == "nullecho"])
        self.boss.next_special = math.inf
        _echoes(self.arena, self.boss)
        advance(self.arena, 0.7)
        self.arena._kill(self.boss, self.mage, "fire")
        advance(self.arena, 0.3)
        self.assertFalse(self.arena.monsters)

    def test_her_fade_does_not_take_a_gate_shield_down(self) -> None:
        self.fight("nullqueen")
        self.mage.invuln_until = self.arena.now + 60
        self.boss.next_attack = 0.0
        self.boss.next_special = math.inf
        self.boss.hp = self.boss.max_hp * 0.6
        advance(self.arena, 2.0)
        self.assertIs(self.arena.gate_boss, self.boss)
        self.assertGreater(self.boss.invuln_until, self.arena.now + 60)

    def test_mana_assignment_empties_the_mage(self) -> None:
        self.fight("nullqueen")
        self.arena.hazards.clear()
        self.mage.invuln_until = 0.0
        self.arena.place_beam_hazard(
            self.boss, self.mage.x - 100, self.mage.y, self.mage.x + 100, self.mage.y,
            width=64, delay=0.1, damage=1, color="#fff", effect="drain",
        )
        advance(self.arena, 0.2)
        self.assertLess(self.mage.mana, 5)

    # ------------------------------------------------------------ the indexer
    def test_the_sweep_always_leaves_a_lane_you_can_reach(self) -> None:
        from arcane.monsters import _sweep

        for seed in range(30):
            self.fight("indexer")
            self.arena.rng = random.Random(seed)
            self.arena.hazards.clear()
            self.mage.x = self.room.center[0] + (seed - 15) * 40
            self.mage.y = self.room.center[1] + (seed - 15) * 25
            _sweep(self.arena, self.boss, self.mage)
            left, top, right, bottom = self.arena.room_box()
            home = self.mage.x, self.mage.y
            reach = SWEEP_FUSE * MOVE_SPEED
            spots = [
                (x, y)
                for x in range(int(left), int(right), 24)
                for y in range(int(top), int(bottom), 24)
                if math.hypot(x - home[0], y - home[1]) <= reach
            ]
            safe = []
            for x, y in spots:
                self.mage.x, self.mage.y = x, y
                if not any(self.arena._hazard_covers(h, self.mage) for h in self.arena.hazards):
                    safe.append((x, y))
            self.assertTrue(safe, f"seed {seed}: no way out")

    def test_two_mages_trade_places(self) -> None:
        from arcane.monsters import _swap

        self.fight("indexer", mages=2)
        first, second = self.mages
        spots = (first.x, first.y), (second.x, second.y)
        self.boss.stun_until = math.inf
        _swap(self.arena, self.boss)
        advance(self.arena, 1.2)
        self.assertEqual((first.x, first.y), spots[1])
        self.assertEqual((second.x, second.y), spots[0])

    def test_a_lone_mage_trades_places_with_the_boss(self) -> None:
        from arcane.monsters import _swap

        self.fight("indexer")
        self.boss.stun_until = math.inf
        mage_spot, boss_spot = (self.mage.x, self.mage.y), (self.boss.x, self.boss.y)
        _swap(self.arena, self.boss)
        advance(self.arena, 1.2)
        self.assertEqual((self.mage.x, self.mage.y), boss_spot)
        self.assertEqual((self.boss.x, self.boss.y), mage_spot)

    def test_nobody_is_swapped_out_of_a_terminal(self) -> None:
        self.fight("indexer", mages=2)
        first, second = self.mages
        spot = first.x, first.y
        self.arena.linked[first.id] = self.arena.terminals[0]
        self.assertFalse(self.arena.swap_places(first, second))
        self.assertEqual((first.x, first.y), spot)

    def test_a_swap_cannot_wedge_the_boss_into_a_wall(self) -> None:
        self.fight("indexer")
        self.mage.x, self.mage.y = self.room.x * TILE + 70, self.room.y * TILE + 70
        self.boss.radius = 120.0
        self.assertFalse(self.arena.swap_places(self.mage, self.boss))

    # ------------------------------------------------------------ the pgt
    def test_mirror_curse_flips_the_mouse_but_not_the_truth(self) -> None:
        self.fight("pgt")
        self.arena.curse(self.mage, "mirror")
        self.mage.x, self.mage.y = 500.0, 500.0
        self.spell("log(aim())", aim=0.0)
        self.assertAlmostEqual(self.mage.aim, math.pi, places=3)
        result = self.spell("log(cursor().x, cursor().y)", target_x=600.0, target_y=500.0)
        self.assertEqual(result["log"], ["400.0 500.0"])
        report = self.spell(
            "e = enemies()[0]\nlog(e.x)", target_x=600.0, target_y=500.0
        )
        self.assertEqual(report["log"], [str(round(self.boss.x, 2))])

    def test_the_false_patch_lies_about_both_colours(self) -> None:
        from arcane.monsters import LIE_RING, _false_patch

        self.fight("pgt")
        self.boss.stun_until = math.inf
        self.arena.hazards.clear()
        _false_patch(self.arena, self.boss)
        hp = self.mage.hp
        advance(self.arena, 1.6)
        self.assertEqual(self.mage.hp, hp, "the red circle is empty")

        self.arena.hazards.clear()
        _false_patch(self.arena, self.boss)
        green = next(h for h in self.arena.hazards if h.damage)
        self.mage.x, self.mage.y = green.x, green.y
        advance(self.arena, 1.6)
        self.assertLess(self.mage.hp, hp, "the green one is not")
        self.assertEqual(LIE_RING - 95, 120, "the safe circle touches the ring")

    def deploying(self) -> None:
        self.fight("pgt")
        self.boss.next_attack = math.inf
        self.mage.hp = self.mage.max_hp = 200.0
        self.mage.x, self.mage.y = self.boss.x + 400, self.boss.y
        self.arena.start_deploy(self.boss)
        self.arena.drain_events()

    def test_a_deploy_lands_and_heals_if_nobody_breaks_it(self) -> None:
        self.deploying()
        self.boss.hp = self.boss.deploy_hp = self.boss.max_hp * 0.8
        advance(self.arena, DEPLOY_TIME + 0.2)
        self.assertAlmostEqual(self.mage.max_hp - self.mage.hp, DEPLOY_DAMAGE, delta=8)
        self.assertGreater(self.boss.hp, self.boss.max_hp * 0.8)

    def test_enough_damage_breaks_a_deploy_and_leaves_him_open(self) -> None:
        self.deploying()
        self.arena.gates_left = []
        self.assertIsNotNone(json.loads(json.dumps(self.arena.snapshot()))["story"]["boss"]["deploy"])
        self.boss.hp -= self.boss.max_hp * DEPLOY_BREAK
        events = advance(self.arena, 0.2)
        self.assertIn("deploy_broken", [event["e"] for event in events])
        self.assertEqual(self.boss.state, "idle")
        self.assertGreater(self.boss.stun_until, self.arena.now)
        later = advance(self.arena, DEPLOY_TIME)
        self.assertNotIn("deploy_blast", [event["e"] for event in later])

    def test_a_deploy_is_cancelled_by_the_bosses_own_gate(self) -> None:
        self.deploying()
        self.boss.hp = self.boss.max_hp * 0.6
        advance(self.arena, 0.2)
        self.assertIs(self.arena.gate_boss, self.boss)
        self.assertEqual(self.boss.state, "idle")

    def test_only_a_bosses_shield_blocks_a_deploy_from_starting(self) -> None:
        self.fight("pgt")
        self.boss.next_attack = math.inf
        self.arena.deploy_at = self.arena.now - 1
        self.boss.hp = self.boss.max_hp * 0.6
        advance(self.arena, 0.3)
        self.assertIs(self.arena.gate_boss, self.boss)
        self.assertNotEqual(self.boss.state, "deploy")

    # --------------------------------------------------------------- curing it
    def test_a_devops_washes_curses_off(self) -> None:
        self.fight("pgt", mages=2)
        healer, mate = self.mages
        apply_role(healer, "devops")
        self.arena.curse(mate, "mirror")
        self.arena.patch(healer, mate, 10)
        self.assertFalse(mate.curses)

    def test_a_cursed_mate_at_full_health_is_worth_a_patch(self) -> None:
        self.fight("pgt", mages=2)
        healer, mate = self.mages
        apply_role(healer, "devops")
        healer.mana = healer.max_mana
        self.arena.curse(mate, "syntax")
        self.mage = healer
        result = self.spell("patch()")
        self.assertTrue(result["ok"], result["error"])
        self.assertFalse(mate.curses)

    def test_curses_die_with_the_mage(self) -> None:
        self.fight("bracket")
        self.arena.curse(self.mage, "syntax")
        self.arena._kill(self.mage, None, "hazard")
        self.assertFalse(self.mage.curses)

    def test_snapshots_carry_all_of_it(self) -> None:
        self.fight("pgt")
        self.arena.curse(self.mage, "mirror")
        self.arena.place_hazard(
            self.boss, 1.0, 1.0, radius=9, delay=1, damage=0, color="#fff", label="безопасно"
        )
        state = json.loads(json.dumps(self.arena.snapshot()))
        me = next(entry for entry in state["players"] if entry["id"] == self.mage.id)
        self.assertIn("mirror", me["curses"])
        self.assertEqual(state["hazards"][-1]["label"], "безопасно")


if __name__ == "__main__":
    unittest.main()
