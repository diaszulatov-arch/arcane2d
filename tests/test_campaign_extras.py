"""Tests for what surrounds the campaign: the rune book, elites, mini-bosses, tickets,
the crew, the proving ground, on-call shifts and the endings."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from arcane.book import BOOK, DAEMON_RUNS
from arcane.campaign import ACCEPT_LINES, CHAPTERS, ENDINGS, STAGES, accept_line
from arcane.crew import CREW, crew_of, has
from arcane.dungeon import TILE
from arcane.elites import ELITES, crown, elite_chance
from arcane.game import TICK_RATE, Arena
from arcane.life import RELICS
from arcane.monsters import SPECIES
from arcane.party import CAMP, FINISHED, PLAYING, Party
from arcane.profiles import Profile, ProfileStore
from arcane.proving import ProvingGround
from arcane.story import StoryArena
from arcane.tickets import TICKETS, closed_by, sla_minutes

TICK = 1 / TICK_RATE
TOKEN = "a" * 32
OTHER = "b" * 32
LAST = len(STAGES) - 1


def advance(arena: StoryArena, seconds: float) -> list[dict]:
    events: list[dict] = []
    for _ in range(int(seconds * TICK_RATE)):
        arena.update(arena.now + TICK)
        events.extend(arena.drain_events())
    return events


def make(stage_index: int, runes: tuple[str, ...] = (), seed: int = 3, plain: bool = True) -> tuple[StoryArena, object]:
    arena = StoryArena(STAGES[stage_index], 1, seed=seed, now=1.0, plain=plain)
    mage = arena.add_player("Маг")
    mage.invuln_until = 1e9
    mage.book = frozenset(runes)
    return arena, mage


def cast(arena: StoryArena, mage, code: str) -> dict:
    mage.cast_ready_at = 0.0
    mage.mana = mage.max_mana
    return arena.cast(mage.id, code, 0, 0.0)


def bug(arena: StoryArena, x: float, y: float, key: str = "popup"):
    monster = arena.spawn_monster(key, x, y)
    monster.spawned_at = 0.0
    monster.next_attack = 1e9
    monster.next_contact = 1e9
    monster.next_special = 1e9
    return monster


def spot(arena: StoryArena, mage, dx: float = 200.0, dy: float = 0.0) -> tuple[float, float]:
    return arena.dungeon.open_near(mage.x + dx, mage.y + dy, 20.0)


class RuneBookTests(unittest.TestCase):
    def test_a_rune_you_have_not_bought_refuses_with_a_reason(self) -> None:
        arena, mage = make(4)
        result = cast(arena, mage, "gc()")
        self.assertFalse(result["ok"])
        self.assertIn("Книге", result["error"])

    def test_buying_costs_tokens_and_cannot_be_done_twice_or_on_credit(self) -> None:
        profile = Profile("x", essence=200)
        self.assertIn("Нужно", profile.buy_rune("daemon"))
        self.assertIsNone(profile.buy_rune("gc"))
        self.assertEqual(profile.essence, 200 - BOOK["gc"].price)
        self.assertIn("уже", profile.buy_rune("gc"))
        self.assertEqual(profile.runes, ["gc"])

    def test_owned_runes_come_with_the_mage(self) -> None:
        arena, mage = make(4)
        Profile("x", runes=["gc"]).apply_to(mage)
        mage.invuln_until = 1e9
        self.assertTrue(cast(arena, mage, "gc()")["ok"])

    def test_the_arena_never_hears_of_them(self) -> None:
        arena = Arena(bots=0)
        mage = arena.add_player("Дуэлянт")
        mage.book = frozenset(BOOK)
        result = arena.cast(mage.id, "gc()", 0, 0.0)
        self.assertFalse(result["ok"])
        self.assertIn("Неизвестное", result["error"])

    def test_ping_counts_through_walls_and_loads_the_room(self) -> None:
        arena, mage = make(4, ("ping",))
        room = arena.dungeon.rooms[1]
        self.assertNotIn(room.index, arena.revealed)
        mage.x, mage.y = arena.dungeon.open_near(room.center[0] - 500, room.center[1], 20.0)
        bug(arena, *room.center)
        result = cast(arena, mage, f"log(ping({room.center[0]}, {room.center[1]}))")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["log"], ["1"])
        self.assertIn(room.index, arena.revealed)

    def test_ping_points_out_a_crack_but_never_loads_the_secret_room(self) -> None:
        arena, mage = make(2, ("ping",), plain=False)
        crack = next(p for p in arena.terrain.props.values() if p.kind == "crack")
        secret = arena.life.secret_room
        mage.x, mage.y = crack.x, crack.y + 80
        cast(arena, mage, f"ping({crack.x}, {crack.y})")
        events = arena.drain_events()
        ping = next(event for event in events if event["e"] == "ping")
        self.assertEqual(len(ping["cracks"]), 1)
        cast_x, cast_y = secret.center
        mage.skill_ready.clear()
        mage.x, mage.y = crack.x, crack.y
        cast(arena, mage, f"ping({cast_x}, {cast_y})")
        self.assertNotIn(secret.index, arena.revealed)

    def test_gc_gathers_spheres_and_clears_poison(self) -> None:
        arena, mage = make(4, ("gc",))
        mage.hp = 20.0
        x, y = spot(arena, mage, 300)
        arena._add_pickup("hp", x, y)
        monster = bug(arena, x, y)
        arena.drop_cloud(monster, mage.x, mage.y, 90)
        result = cast(arena, mage, "log(gc())")
        self.assertEqual(result["log"], ["1"])
        self.assertEqual(arena.clouds, [])
        advance(arena, 0.1)
        self.assertGreater(mage.hp, 20.0)

    def test_grep_hits_what_matches_and_nothing_else(self) -> None:
        arena, mage = make(4, ("grep",))
        cookie = bug(arena, *spot(arena, mage, 200), "cookie")
        popup = bug(arena, *spot(arena, mage, -200), "popup")
        cookie_hp, popup_hp = cookie.hp, popup.hp
        result = cast(arena, mage, 'log(grep("cook"))')
        self.assertEqual(result["log"], ["1"])
        self.assertLess(cookie.hp, cookie_hp)
        self.assertEqual(popup.hp, popup_hp)

    def test_grep_finds_by_the_russian_name_too(self) -> None:
        arena, mage = make(4, ("grep",))
        bug(arena, *spot(arena, mage, 200), "popup")
        self.assertEqual(cast(arena, mage, 'log(grep("Попап"))')["log"], ["1"])

    def test_grep_wants_a_real_string(self) -> None:
        arena, mage = make(4, ("grep",))
        self.assertFalse(cast(arena, mage, "grep(5)")["ok"])
        self.assertFalse(cast(arena, mage, 'grep("a")')["ok"])

    def test_undo_goes_back_three_seconds_and_gives_the_health_back(self) -> None:
        arena, mage = make(4, ("undo",))
        home = mage.x, mage.y
        advance(arena, 3.5)
        mage.x, mage.y = spot(arena, mage, 300)
        mage.hp = 10.0
        result = cast(arena, mage, "undo()")
        self.assertTrue(result["ok"], result)
        self.assertLess(abs(mage.x - home[0]) + abs(mage.y - home[1]), 40)
        self.assertGreater(mage.hp, 10.0)

    def test_undo_comes_with_a_cooldown(self) -> None:
        arena, mage = make(4, ("undo",))
        advance(arena, 0.5)
        cast(arena, mage, "undo()")
        result = cast(arena, mage, "undo()")
        self.assertFalse(result["ok"])
        self.assertIn("готова", result["error"])

    def test_a_cooldown_can_be_asked_about_instead_of_tripped_over(self) -> None:
        arena, mage = make(4, ("undo",))
        advance(arena, 0.5)
        cast(arena, mage, "undo()")
        self.assertEqual(cast(arena, mage, 'log(ready("undo"))')["log"], ["False"])

    def test_zip_bomb_goes_off_later_where_it_was_put(self) -> None:
        arena, mage = make(4, ("zip_bomb",))
        x, y = spot(arena, mage, 300)
        near = bug(arena, x, y)
        far = bug(arena, *spot(arena, mage, -300))
        near.stun_until = far.stun_until = 1e9
        near_hp, far_hp = near.hp, far.hp
        self.assertTrue(cast(arena, mage, f"zip_bomb({x}, {y})")["ok"])
        self.assertEqual(near.hp, near_hp)
        advance(arena, 1.4)
        self.assertLess(near.hp, near_hp)
        self.assertEqual(far.hp, far_hp)

    def test_zip_bomb_has_a_range(self) -> None:
        arena, mage = make(4, ("zip_bomb",))
        result = cast(arena, mage, f"zip_bomb({mage.x + 5000}, {mage.y})")
        self.assertFalse(result["ok"])
        self.assertEqual(mage.mana, mage.max_mana)

    def test_a_clone_fights_for_you_and_then_is_gone(self) -> None:
        arena, mage = make(4, ("clone",))
        foe = bug(arena, *spot(arena, mage, 250))
        foe.stun_until = 1e9
        hp = foe.hp
        self.assertTrue(cast(arena, mage, "clone()")["ok"])
        clone = next(m for m in arena.monsters.values() if m.species.key == "clone")
        self.assertNotIn(clone, arena.foes_for(mage.id))
        advance(arena, 3.0)
        self.assertLess(foe.hp, hp)
        advance(arena, 6.0)
        self.assertNotIn(clone.id, arena.monsters)

    def test_a_clone_does_not_keep_a_room_shut(self) -> None:
        arena, mage = make(4, ("clone",))
        room = arena.dungeon.path[1]
        arena.make_clone(mage, 8.0)
        clone = next(m for m in arena.monsters.values() if m.species.key == "clone")
        clone.x, clone.y = room.center
        self.assertFalse(arena._fighters(room))

    def test_later_calls_your_function_when_it_said_it_would(self) -> None:
        arena, mage = make(4, ("later",))
        mage.hp = 50.0
        x, y = spot(arena, mage, 200)
        foe = bug(arena, x, y)
        hp = foe.hp
        code = f"""
def strike(angle):
    fireball(angle)

later(0.5, strike, direction({x}, {y}))
"""
        self.assertTrue(cast(arena, mage, code)["ok"])
        self.assertEqual(foe.hp, hp)
        advance(arena, 1.4)
        self.assertLess(foe.hp, hp)

    def test_later_takes_a_bare_rune_as_well(self) -> None:
        arena, mage = make(8, ("later",))
        self.assertTrue(cast(arena, mage, "later(0.2, nova)")["ok"])
        mana_before = mage.mana
        advance(arena, 0.3)
        self.assertLess(mage.mana, mana_before)

    def test_later_will_not_queue_forever(self) -> None:
        arena, mage = make(4, ("later",))
        code = "def f():\n    log(1)\n\nfor i in range(5):\n    later(5, f)\n"
        result = cast(arena, mage, code)
        self.assertFalse(result["ok"])
        self.assertEqual(len(arena.deferred), 3)

    def test_later_says_so_when_it_is_handed_a_call_instead_of_a_function(self) -> None:
        arena, mage = make(4, ("later",))
        result = cast(arena, mage, "def f():\n    return 1\n\nlater(1, f())\n")
        self.assertFalse(result["ok"])
        self.assertIn("без скобок", result["error"])

    def test_a_daemon_keeps_shooting_while_you_do_something_else(self) -> None:
        arena, mage = make(11, ("daemon",))
        foe = bug(arena, *spot(arena, mage, 300))
        foe.stun_until = 1e9
        foe.max_hp = foe.hp = 5000.0
        code = """
def turret():
    foes = enemies()
    if foes:
        fireball(direction(foes[0].x, foes[0].y))

daemon(turret)
"""
        result = cast(arena, mage, code)
        self.assertTrue(result["ok"], result)
        self.assertEqual(foe.hp, 5000.0)
        advance(arena, 3.0)
        self.assertLess(foe.hp, 5000.0)

    def test_a_daemon_ends_on_its_own(self) -> None:
        arena, mage = make(4, ("daemon",))
        cast(arena, mage, "def f():\n    log(1)\n\ndaemon(f)\n")
        events = advance(arena, DAEMON_RUNS * 0.5 + 1.0)
        self.assertEqual(arena.deferred, [])
        self.assertIn("daemon_end", [event["e"] for event in events])

    def test_a_bug_in_a_daemon_stops_it_and_says_where(self) -> None:
        arena, mage = make(4, ("daemon",))
        cast(arena, mage, "def f():\n    return nothing_here\n\ndaemon(f)\n")
        events = advance(arena, 1.0)
        report = next(event for event in events if event["e"] == "spell_log")
        self.assertIn("nothing_here", report["error"])
        self.assertEqual(arena.deferred, [])
        self.assertEqual(arena.stats.errors, 1)

    def test_a_daemon_cannot_hang_the_server(self) -> None:
        arena, mage = make(4, ("daemon",))
        cast(arena, mage, "def f():\n    while True:\n        pass\n\ndaemon(f)\n")
        events = advance(arena, 1.0)
        report = next(event for event in events if event["e"] == "spell_log")
        self.assertIn("лимит", report["error"])

    def test_a_daemon_pays_with_your_own_mana(self) -> None:
        arena, mage = make(4, ("daemon",))
        foe = bug(arena, *spot(arena, mage, 300))
        foe.max_hp = foe.hp = 5000.0
        mage.mana_regen = 0.0
        cast(arena, mage, "def f():\n    fireball(0)\n\ndaemon(f)\n")
        before = mage.mana
        advance(arena, 1.2)
        self.assertLess(mage.mana, before)

    def test_a_daemon_rests_while_its_mage_is_at_a_terminal(self) -> None:
        arena, mage = make(4, ("daemon",))
        cast(arena, mage, "def f():\n    log(1)\n\ndaemon(f)\n")
        arena.linked[mage.id] = arena.terminals[0]
        events = advance(arena, 1.5)
        self.assertNotIn("spell_log", [event["e"] for event in events])

    def test_a_second_daemon_replaces_the_first(self) -> None:
        arena, mage = make(4, ("daemon",))
        code = "def f():\n    log(1)\n\ndaemon(f)\n"
        cast(arena, mage, code)
        mage.skill_ready.clear()
        cast(arena, mage, code)
        self.assertEqual(len(arena.deferred), 1)

    def test_a_daemon_outlives_nothing_when_the_mage_leaves(self) -> None:
        arena, mage = make(4, ("daemon",))
        cast(arena, mage, "def f():\n    log(1)\n\ndaemon(f)\n")
        arena.remove_player(mage.id)
        advance(arena, 1.0)
        self.assertEqual(arena.deferred, [])

    def test_a_kept_function_sees_fresh_state(self) -> None:
        arena, mage = make(4, ("later",))
        mage.hp = 50.0
        cast(arena, mage, "def f():\n    log(me().hp)\n\nlater(0.2, f)\n")
        mage.hp = 77.0
        events = advance(arena, 0.3)
        report = next(event for event in events if event["e"] == "spell_log")
        self.assertGreaterEqual(float(report["log"][0]), 77.0)


class EliteTests(unittest.TestCase):
    def test_every_elite_has_something_to_say_for_itself(self) -> None:
        arena = StoryArena(STAGES[4], 1, seed=1)
        bestiary = arena.world_config()["bestiary"]
        for key, elite in ELITES.items():
            self.assertEqual(bestiary[f"elite_{key}"]["title"], elite.title)
            self.assertTrue(elite.hint)

    def test_the_first_stages_stay_simple(self) -> None:
        self.assertEqual(elite_chance(StoryArena(STAGES[0], 1, seed=1)), 0.0)
        self.assertGreater(elite_chance(StoryArena(STAGES[4], 1, seed=1)), 0.0)

    def test_a_shift_brings_more_of_them(self) -> None:
        calm = StoryArena(STAGES[4], 1, seed=1)
        shift = StoryArena(STAGES[4], 1, seed=1, duty=4, known_upto=4)
        self.assertGreater(elite_chance(shift), elite_chance(calm))

    def test_legacy_is_thick_and_pays_well(self) -> None:
        arena, mage = make(4)
        monster = bug(arena, *spot(arena, mage))
        hp, cost = monster.hp, max(1, round(monster.species.cost))
        crown(arena, monster, "legacy")
        self.assertEqual(monster.hp, hp * ELITES["legacy"].hp)
        self.assertEqual(monster.text, "Легаси")
        monster.hp = 1.0
        arena.damage(target=monster, amount=5, source=mage, kind="fire", hit_x=monster.x, hit_y=monster.y)
        self.assertEqual(arena.essence, cost * ELITES["legacy"].pay)

    def test_hotfix_heals_its_neighbours(self) -> None:
        arena, mage = make(4)
        healer = bug(arena, *spot(arena, mage, 300))
        patient = bug(arena, healer.x + 60, healer.y)
        crown(arena, healer, "hotfix")
        healer.next_special = 0.0
        patient.hp = 1.0
        advance(arena, 0.2)
        self.assertGreater(patient.hp, 1.0)

    def test_fork_splits_once(self) -> None:
        arena, mage = make(4)
        arena.active_room = None
        monster = bug(arena, *spot(arena, mage, 300))
        crown(arena, monster, "fork")
        arena.damage(target=monster, amount=1e6, source=mage, kind="fire", hit_x=monster.x, hit_y=monster.y)
        children = list(arena.monsters.values())
        self.assertEqual(len(children), 2)
        self.assertTrue(all(child.generation == 1 for child in children))

    def test_prod_takes_the_room_with_it(self) -> None:
        arena, mage = make(4)
        monster = bug(arena, *spot(arena, mage, 300))
        crown(arena, monster, "prod")
        arena.damage(target=monster, amount=1e6, source=mage, kind="fire", hit_x=monster.x, hit_y=monster.y)
        self.assertEqual(len(arena.hazards), 1)

    def test_async_really_runs(self) -> None:
        from arcane.monsters import _speed

        arena, mage = make(4)
        monster = bug(arena, *spot(arena, mage))
        normal = _speed(monster, arena)
        crown(arena, monster, "async")
        self.assertGreater(_speed(monster, arena), normal * 1.5)

    def test_deprecated_runs_away_and_deletes_itself(self) -> None:
        arena, mage = make(4)
        monster = bug(arena, *spot(arena, mage, 200))
        crown(arena, monster, "deprecated")
        far = abs(monster.x - mage.x) + abs(monster.y - mage.y)
        advance(arena, 1.0)
        self.assertGreater(abs(monster.x - mage.x) + abs(monster.y - mage.y), far - 60)
        advance(arena, 12.0)
        self.assertNotIn(monster.id, arena.monsters)
        self.assertEqual(arena.essence, 0)

    def test_code_can_read_the_title(self) -> None:
        arena, mage = make(11)
        monster = bug(arena, *spot(arena, mage))
        crown(arena, monster, "hotfix")
        self.assertEqual(cast(arena, mage, "log(enemies()[0].text)")["log"], ["Хотфикс"])

    def test_clients_can_tell_them_apart(self) -> None:
        arena, mage = make(4)
        monster = bug(arena, *spot(arena, mage))
        crown(arena, monster, "async")
        entry = next(e for e in arena.snapshot()["monsters"] if e["id"] == monster.id)
        self.assertEqual(entry["elite"], "async")
        self.assertEqual(entry["text"], "Async")


class MiniBossTests(unittest.TestCase):
    def mini(self, stage_index: int) -> tuple[StoryArena, object, object]:
        arena, mage = make(stage_index, plain=False, seed=4)
        room = arena.mini_room
        self.assertIsNotNone(room)
        arena.active_room = room
        arena.wave = arena._waves_in(room) - 1
        mage.x, mage.y = arena.dungeon.open_near(room.center[0] - 150, room.center[1], 20.0)
        arena._spawn_wave(room)
        boss = next(m for m in arena.monsters.values() if m.species.key == STAGES[stage_index].mini)
        boss.spawned_at = 0.0
        return arena, mage, boss

    def test_every_stage_has_one(self) -> None:
        for chapter in CHAPTERS:
            self.assertIn(chapter.mini, SPECIES)
            self.assertTrue(SPECIES[chapter.mini].boss)
        for stage in STAGES:
            self.assertIn(stage.mini, SPECIES)
            self.assertTrue(SPECIES[stage.mini].boss)
            if stage.number == 2:
                self.assertEqual(stage.mini, stage.chapter.mini)

    def test_it_comes_in_the_last_wave_of_the_last_fight(self) -> None:
        arena, mage = make(1, plain=False, seed=4)
        fights = [room for room in arena.dungeon.path if room.kind == "combat"]
        self.assertIs(arena.mini_room, fights[-1])

    def test_nobody_meets_one_in_a_plain_room(self) -> None:
        arena, _ = make(1, plain=True)
        self.assertIsNone(arena.mini_room)

    def test_the_flash_ring_has_a_gap_in_it(self) -> None:
        arena, mage, boss = self.mini(1)
        arena.projectiles.clear()
        boss.next_attack = 0.0
        advance(arena, 0.05)
        shots = sorted(p.angle % 6.2832 for p in arena.projectiles if p.owner == boss.id)
        self.assertGreater(len(shots), 15)
        gaps = [b - a for a, b in zip(shots, shots[1:])] + [shots[0] + 6.2832 - shots[-1]]
        self.assertGreater(max(gaps), min(gaps) * 3)

    def test_nothing_reaches_the_influencer_while_it_has_followers(self) -> None:
        arena, mage, boss = self.mini(5)
        advance(arena, 0.2)
        followers = [m for m in arena.monsters.values() if m.species.key == "follower"]
        self.assertGreaterEqual(len(followers), 4)
        hp = boss.hp
        arena.damage(target=boss, amount=50, source=mage, kind="fire", hit_x=boss.x, hit_y=boss.y)
        self.assertEqual(boss.hp, hp)
        for follower in followers:
            arena.remove_monster(follower)
        advance(arena, 0.4)
        arena.damage(target=boss, amount=50, source=mage, kind="fire", hit_x=boss.x, hit_y=boss.y)
        self.assertLess(boss.hp, hp)

    def test_copies_die_at_a_touch_and_only_the_real_file_has_hp(self) -> None:
        arena, mage, boss = self.mini(9)
        boss.next_special = 0.0
        advance(arena, 0.1)
        copies = [m for m in arena.monsters.values() if m.species.key == "dupe"]
        self.assertTrue(copies)
        self.assertEqual({copy.name for copy in copies}, {boss.name})
        self.assertLess(copies[0].hp, boss.hp)
        arena.damage(target=copies[0], amount=5, source=mage, kind="fire", hit_x=copies[0].x, hit_y=copies[0].y)
        self.assertNotIn(copies[0].id, arena.monsters)
        self.assertEqual(arena.essence, 0)

    def test_the_rest_of_the_copies_go_with_the_original(self) -> None:
        arena, mage, boss = self.mini(9)
        boss.next_special = 0.0
        advance(arena, 0.1)
        arena.damage(target=boss, amount=1e7, source=mage, kind="frost", hit_x=boss.x, hit_y=boss.y)
        advance(arena, 1.0)
        self.assertFalse([m for m in arena.monsters.values() if m.species.key == "dupe"])

    def test_fire_does_nothing_to_the_hot_rack_and_frost_pushes_the_blast_back(self) -> None:
        arena, mage, boss = self.mini(13)
        hp = boss.hp
        arena.damage(target=boss, amount=50, source=mage, kind="fire", hit_x=boss.x, hit_y=boss.y)
        self.assertEqual(boss.hp, hp)
        boss.next_special = arena.now + 1.0
        arena.damage(target=boss, amount=50, source=mage, kind="frost", hit_x=boss.x, hit_y=boss.y)
        self.assertLess(boss.hp, hp)
        self.assertGreater(boss.next_special, arena.now + 3.0)

    def test_the_reviewer_refuses_what_it_has_just_seen(self) -> None:
        arena, mage, boss = self.mini(17)
        hp = boss.hp
        arena.damage(target=boss, amount=20, source=mage, kind="fire", hit_x=boss.x, hit_y=boss.y)
        after_fire = boss.hp
        self.assertLess(after_fire, hp)
        arena.damage(target=boss, amount=20, source=mage, kind="fire", hit_x=boss.x, hit_y=boss.y)
        self.assertEqual(boss.hp, after_fire)
        arena.damage(target=boss, amount=20, source=mage, kind="frost", hit_x=boss.x, hit_y=boss.y)
        self.assertLess(boss.hp, after_fire)

    def test_code_can_beat_the_reviewer_by_reading_it(self) -> None:
        arena, mage, boss = self.mini(17)
        boss.hp = boss.max_hp = 5000.0
        code = """
for e in enemies():
    if e.kind == "reviewer":
        log(e.text)
"""
        arena.damage(target=boss, amount=20, source=mage, kind="fire", hit_x=boss.x, hit_y=boss.y)
        self.assertEqual(cast(arena, mage, code)["log"], ["fire"])


class TicketTests(unittest.TestCase):
    def test_every_stage_owes_four_and_the_keys_are_unique(self) -> None:
        self.assertEqual(len(TICKETS), len(STAGES))
        keys = [ticket.key for stage in TICKETS for ticket in stage]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all(len(stage) == 4 for stage in TICKETS))

    def test_no_ticket_asks_for_what_a_stage_cannot_have(self) -> None:
        for stage, tickets in zip(STAGES, TICKETS):
            own = tickets[2]
            if stage.is_boss:
                self.assertNotIn(own.title, ("Руками", "Археолог", "Плановый снос", "Поддержка пользователей"))
            if stage.index < 6:
                self.assertNotIn(own.title, ("Без отката",))

    def finished(self, **stats) -> StoryArena:
        arena = StoryArena(STAGES[0], 1, seed=1, now=1.0)
        arena.outcome = "cleared"
        arena.outcome_at = 2.0
        for key, value in stats.items():
            setattr(arena.stats, key, value)
        return arena

    def keys(self, arena: StoryArena) -> set[str]:
        return {ticket.key.split(":")[1] for ticket in closed_by(arena)}

    def test_nothing_closes_on_a_wipe(self) -> None:
        arena = self.finished()
        arena.outcome = "wiped"
        self.assertEqual(closed_by(arena), [])

    def test_a_fall_loses_the_clean_run(self) -> None:
        self.assertIn("clean_run", self.keys(self.finished()))
        self.assertNotIn("clean_run", self.keys(self.finished(deaths=1)))

    def test_the_sla_has_a_limit(self) -> None:
        arena = self.finished()
        self.assertIn("sla", self.keys(arena))
        arena.outcome_at = arena.stats.started + sla_minutes(STAGES[0]) * 60 + 1
        self.assertNotIn("sla", self.keys(arena))

    def test_senior_is_for_senior(self) -> None:
        self.assertNotIn("senior", self.keys(self.finished()))
        arena = StoryArena(STAGES[0], 1, seed=1, now=1.0, difficulty=3)
        arena.outcome = "cleared"
        arena.outcome_at = 2.0
        self.assertIn("senior", self.keys(arena))

    def test_a_failed_spell_counts_and_a_cooldown_does_not(self) -> None:
        arena, mage = make(0)
        arena.cast(mage.id, "fireball(aim())", 0, 0.0)
        self.assertEqual(arena.stats.errors, 0)
        self.assertEqual(arena.stats.runes, {"fireball"})
        arena.cast(mage.id, "fireball(aim())", 0, 0.0)
        self.assertEqual(arena.stats.errors, 0)
        mage.cast_ready_at = 0.0
        arena.cast(mage.id, "nope()", 0, 0.0)
        self.assertEqual(arena.stats.errors, 1)

    def test_hints_and_help_from_pgt_are_counted(self) -> None:
        arena, mage = make(0)
        terminal = arena.terminals[0]
        mage.x, mage.y = terminal.x, terminal.y + 40
        arena.link(mage.id)
        arena.terminal_help(mage.id, 0)
        self.assertEqual(arena.stats.hints, 1)

    def test_breaking_things_and_visiting_people_are_counted(self) -> None:
        arena, mage = make(1, plain=False)
        crate = next(p for p in arena.terrain.props.values() if p.kind == "crate")
        arena.terrain.prop_hit(crate, mage, "fire")
        self.assertEqual(arena.stats.broken, 1)
        thing = arena.life.residents[0]
        arena.life.use(thing, mage)
        arena.life.use(thing, mage)
        self.assertEqual(arena.stats.residents, 1)

    def test_a_ticket_pays_once_and_each_mage_for_themselves(self) -> None:
        store = ProfileStore()
        party = Party("ABCD", store)
        party.join(TOKEN, "Первый")
        party.join(OTHER, "Второй")
        store.get(OTHER).tickets.append("0:clean_run")
        party.set_ready(TOKEN, True, 1.0)
        party.set_ready(OTHER, True, 1.0)
        party.world.outcome = "cleared"
        party.tick(party.world.now + TICK)
        first = {t["key"] for t in party.closed_tickets[TOKEN]}
        second = {t["key"] for t in party.closed_tickets[OTHER]}
        self.assertIn("0:clean_run", first)
        self.assertNotIn("0:clean_run", second)
        self.assertIn("0:sla", second)
        self.assertEqual(store.get(TOKEN).tickets.count("0:sla"), 1)
        party.set_ready(TOKEN, True, 2.0)
        party.set_ready(OTHER, True, 2.0)


class CrewTests(unittest.TestCase):
    def test_everyone_shows_up_in_time(self) -> None:
        self.assertEqual(crew_of(0), [])
        self.assertEqual(len(crew_of(len(STAGES))), len(CREW))
        for member in CREW:
            self.assertTrue(has(member.joins, member.key))
            self.assertFalse(has(member.joins - 1, member.key))

    def test_they_always_have_something_to_say(self) -> None:
        for member in CREW:
            for cleared in range(member.joins, len(STAGES) + 1):
                self.assertTrue(member.line(cleared))

    def run_with(self, cleared: int, stage: int = 2) -> tuple[Party, ProfileStore]:
        store = ProfileStore()
        store.get(TOKEN).cleared = cleared
        party = Party("ABCD", store)
        party.join(TOKEN, "Маг")
        party.stage_index = stage
        party.set_ready(TOKEN, True, 1.0)
        return party, store

    def test_the_lost_request_runs_ahead(self) -> None:
        with_him, _ = self.run_with(1)
        self.assertGreater(len(with_him.world.revealed), 1)

    def test_nobody_runs_ahead_before_he_is_rescued(self) -> None:
        without, _ = self.run_with(0, stage=0)
        self.assertEqual(without.world.revealed, {0})

    def test_the_cash_machine_pays_interest(self) -> None:
        self.assertEqual(Profile("x", cleared=3).essence_rate(), 1.0)
        self.assertAlmostEqual(Profile("x", cleared=4).essence_rate(), 1.1)

    def test_the_fridge_feeds_you(self) -> None:
        party, store = self.run_with(8, stage=2)
        mage = party.world.players[party.seats[0].player_id]
        self.assertEqual(mage.max_hp, 115.0)
        self.assertEqual(mage.hp, 115.0)

    def test_the_queen_catches_one_fall_a_stage(self) -> None:
        party, _ = self.run_with(12, stage=2)
        world = party.world
        mage = world.players[party.seats[0].player_id]
        mage.invuln_until = 0.0
        world.damage(target=mage, amount=1e6, source=None, kind="orb", hit_x=mage.x, hit_y=mage.y)
        self.assertFalse(mage.dead)
        self.assertGreater(mage.hp, 0)
        self.assertEqual(world.stats.deaths, 0)
        mage.invuln_until = 0.0
        world.damage(target=mage, amount=1e6, source=None, kind="orb", hit_x=mage.x, hit_y=mage.y)
        self.assertTrue(mage.dead)
        self.assertEqual(world.stats.deaths, 1)

    def test_valera_pours_coffee(self) -> None:
        party, _ = self.run_with(15, stage=2)
        self.assertEqual(len(party.world.life.taken), 1)


class ProvingGroundTests(unittest.TestCase):
    def enter(self) -> tuple[Party, ProvingGround, object]:
        store = ProfileStore()
        party = Party("ABCD", store)
        party.join(TOKEN, "Маг")
        self.assertIsNone(party.start_range(TOKEN, 1.0))
        world = party.world
        return party, world, world.players[party.seats[0].player_id]

    def test_every_rune_in_the_book_works_here_unbought(self) -> None:
        _, world, mage = self.enter()
        mage.skill_ready.clear()
        self.assertTrue(cast(world, mage, "gc()")["ok"])
        self.assertIn("daemon", world.world_config()["runes"])
        self.assertIn("meteor", world.world_config()["runes"])

    def test_every_rune_taught_works_here_too(self) -> None:
        _, world, mage = self.enter()
        self.assertTrue(cast(world, mage, "meteor(me().x + 100, me().y)")["ok"])

    def test_the_dummies_never_fall_and_the_damage_is_counted(self) -> None:
        _, world, mage = self.enter()
        dummy = world.dummies[0]
        dealt = world.damage(target=dummy, amount=40, source=mage, kind="fire", hit_x=dummy.x, hit_y=dummy.y)
        self.assertGreater(dealt, 0)
        self.assertEqual(dummy.hp, dummy.max_hp)
        state = world.snapshot()["range"]
        self.assertEqual(state["total"], round(dealt))
        self.assertGreater(state["dps"], 0)

    def test_nothing_hurts_here(self) -> None:
        _, world, mage = self.enter()
        advance(world, 0.1)
        hp = mage.hp
        world.damage(target=mage, amount=500, source=None, kind="orb", hit_x=mage.x, hit_y=mage.y)
        self.assertEqual(mage.hp, hp)

    def test_nothing_is_earned_and_no_progress_is_made(self) -> None:
        party, world, mage = self.enter()
        store = party.store
        mage.x, mage.y = world.portal
        for _ in range(40):
            party.tick(world.now + TICK)
            if party.world is None:
                break
        self.assertIsNone(party.world)
        self.assertEqual(party.state, CAMP)
        self.assertEqual(store.get(TOKEN).essence, 0)
        self.assertEqual(store.get(TOKEN).cleared, 0)
        self.assertEqual(party.outbox[-1]["result"], "range")

    def test_nobody_starts_on_the_way_out(self) -> None:
        party, world, mage = self.enter()
        for _ in range(60):
            party.tick(world.now + TICK)
        self.assertIsNotNone(party.world)
        self.assertEqual(party.state, PLAYING)

    def test_only_the_leader_leads_there(self) -> None:
        party = Party("ABCD", ProfileStore())
        party.join(TOKEN, "Лидер")
        party.join(OTHER, "Второй")
        self.assertIsNotNone(party.start_range(OTHER, 1.0))


class DutyTests(unittest.TestCase):
    def party(self, cleared: int = 8) -> tuple[Party, ProfileStore]:
        store = ProfileStore()
        store.get(TOKEN).cleared = cleared
        party = Party("ABCD", store)
        party.join(TOKEN, "Дежурный")
        return party, store

    def finish(self, party: Party, outcome: str) -> None:
        party.world.outcome = outcome
        party.tick(party.world.now + TICK)

    def test_it_opens_after_the_first_chapter(self) -> None:
        party, _ = self.party(3)
        self.assertIsNotNone(party.start_duty(TOKEN, 1.0))
        party, _ = self.party(4)
        self.assertIsNone(party.start_duty(TOKEN, 1.0))

    def test_an_incident_is_an_ordinary_stage_from_what_you_have_cleared(self) -> None:
        party, _ = self.party(8)
        party.start_duty(TOKEN, 1.0)
        self.assertFalse(party.world.stage.is_boss)
        self.assertLess(party.world.stage.index, 8)
        self.assertEqual(party.world.duty, 1)

    def test_runes_are_everything_you_know_not_what_the_stage_taught(self) -> None:
        party, _ = self.party(8)
        party.start_duty(TOKEN, 1.0)
        self.assertIn("lightning_strike", party.world.known_runes)

    def test_it_gets_harder(self) -> None:
        calm = StoryArena(STAGES[4], 1, seed=1, duty=0)
        late = StoryArena(STAGES[4], 1, seed=1, duty=6, known_upto=4)
        self.assertGreater(late.monster_bite, calm.monster_bite)
        self.assertGreater(late._wave_budget(), calm._wave_budget())
        self.assertGreater(
            late.spawn_monster("popup", 0, 0).max_hp, calm.spawn_monster("popup", 0, 0).max_hp
        )

    def test_no_pay_until_the_shift_is_handed_over(self) -> None:
        party, store = self.party()
        party.start_duty(TOKEN, 1.0)
        self.finish(party, "cleared")
        self.assertEqual(party.state, CAMP)
        self.assertEqual(store.get(TOKEN).essence, 0)
        self.assertEqual(party.duty.level, 2)
        self.assertGreater(party.duty.tokens, 0)

    def test_ready_means_the_next_incident(self) -> None:
        party, _ = self.party()
        party.start_duty(TOKEN, 1.0)
        first = party.world.stage.index
        self.finish(party, "cleared")
        party.set_ready(TOKEN, True, 5.0)
        self.assertEqual(party.world.duty, 2)
        self.assertNotEqual(party.world.stage.index, first)

    def test_handing_over_pays_in_full_and_makes_the_board(self) -> None:
        party, store = self.party()
        party.start_duty(TOKEN, 1.0)
        self.finish(party, "cleared")
        tokens = party.duty.tokens
        self.assertIsNone(party.end_duty(TOKEN))
        self.assertIsNone(party.duty)
        self.assertEqual(store.get(TOKEN).essence, round(tokens * store.get(TOKEN).essence_rate()))
        self.assertEqual(store.duty_board(), [{"name": "Дежурный", "score": 1}])

    def test_falling_on_shift_costs_half(self) -> None:
        party, store = self.party()
        party.start_duty(TOKEN, 1.0)
        self.finish(party, "cleared")
        tokens = party.duty.tokens
        party.set_ready(TOKEN, True, 5.0)
        party.world.essence = 0
        self.finish(party, "wiped")
        self.assertIsNone(party.duty)
        self.assertEqual(store.get(TOKEN).essence, round(round(tokens / 2) * store.get(TOKEN).essence_rate()))
        self.assertEqual(store.get(TOKEN).duty_best, 1)

    def test_a_shift_does_not_touch_campaign_progress(self) -> None:
        party, store = self.party(8)
        party.start_duty(TOKEN, 1.0)
        self.finish(party, "cleared")
        self.assertEqual(store.get(TOKEN).cleared, 8)
        self.assertEqual(store.get(TOKEN).tickets, [])

    def test_the_map_is_shut_during_a_shift(self) -> None:
        party, _ = self.party()
        party.start_duty(TOKEN, 1.0)
        self.finish(party, "cleared")
        self.assertIsNotNone(party.choose_stage(TOKEN, 0))

    def test_only_a_better_shift_changes_the_record(self) -> None:
        party, store = self.party()
        store.get(TOKEN).duty_best = 5
        party.start_duty(TOKEN, 1.0)
        self.finish(party, "cleared")
        party.end_duty(TOKEN)
        self.assertEqual(store.get(TOKEN).duty_best, 5)


class EndingTests(unittest.TestCase):
    def finale(self) -> tuple[Party, ProfileStore]:
        store = ProfileStore()
        store.get(TOKEN).cleared = LAST
        party = Party("ABCD", store)
        party.join(TOKEN, "Маг")
        party.stage_index = LAST
        party.set_ready(TOKEN, True, 1.0)
        party.world.outcome = "cleared"
        party.tick(party.world.now + TICK)
        return party, store

    def test_three_endings_are_on_offer(self) -> None:
        self.assertEqual(set(ENDINGS), {"test", "wipe", "merge"})
        for ending in ENDINGS.values():
            self.assertTrue(ending.lines and ending.command and ending.about)

    def test_nothing_is_decided_until_somebody_decides(self) -> None:
        party, _ = self.finale()
        self.assertEqual(party.state, FINISHED)
        self.assertEqual(party.describe(TOKEN)["ending"], "")

    def test_the_choice_is_remembered(self) -> None:
        party, store = self.finale()
        self.assertIsNone(party.pick_ending(TOKEN, "wipe"))
        self.assertEqual(party.describe(TOKEN)["ending"], "wipe")
        self.assertEqual(store.get(TOKEN).endings, ["wipe"])

    def test_there_is_no_fourth_choice(self) -> None:
        party, _ = self.finale()
        self.assertIsNotNone(party.pick_ending(TOKEN, "nope"))

    def test_no_ending_before_the_end(self) -> None:
        party = Party("ABCD", ProfileStore())
        party.join(TOKEN, "Маг")
        self.assertIsNotNone(party.pick_ending(TOKEN, "test"))

    def test_the_party_can_go_back_to_camp_and_play_on(self) -> None:
        party, _ = self.finale()
        party.pick_ending(TOKEN, "test")
        party.back_to_camp()
        self.assertEqual(party.state, CAMP)
        party.set_ready(TOKEN, True, 2.0)
        self.assertEqual(party.state, PLAYING)

    def test_each_time_is_a_new_decision(self) -> None:
        party, store = self.finale()
        party.pick_ending(TOKEN, "test")
        party.back_to_camp()
        party.stage_index = LAST
        party.set_ready(TOKEN, True, 2.0)
        party.world.outcome = "cleared"
        party.tick(party.world.now + TICK)
        self.assertEqual(party.describe(TOKEN)["ending"], "")
        party.pick_ending(TOKEN, "merge")
        self.assertEqual(store.get(TOKEN).endings, ["test", "merge"])


class AcceptTests(unittest.TestCase):
    def test_pgt_reads_out_the_count_in_his_own_words(self) -> None:
        self.assertIn("ни разу", accept_line(0)[1].lower())
        self.assertIn("один раз", accept_line(1)[1])
        self.assertIn("3 раза", accept_line(3)[1])
        self.assertIn("7 раз", accept_line(7)[1])
        self.assertEqual(ACCEPT_LINES[0][0], 0)

    def test_the_readout_comes_after_the_reveal_and_before_the_end(self) -> None:
        party = Party("ABCD", ProfileStore())
        party.join(TOKEN, "Маг")
        self.assertEqual(party.readout(TOKEN, 3), [])
        self.assertTrue(party.readout(TOKEN, 8))
        self.assertTrue(party.readout(TOKEN, LAST))

    def test_every_press_makes_the_final_boss_stronger(self) -> None:
        store = ProfileStore()
        store.get(TOKEN).accepted = 4
        store.get(TOKEN).cleared = LAST
        party = Party("ABCD", store)
        party.join(TOKEN, "Маг")
        party.stage_index = LAST
        party.set_ready(TOKEN, True, 1.0)
        boosted = party.world.pgt_boost
        self.assertAlmostEqual(boosted, 1.2)
        world = party.world
        room = world.exit_room
        strong = world.spawn_monster("pgt", *room.center)
        plain = StoryArena(STAGES[LAST], 1, seed=1).spawn_monster("pgt", 0, 0)
        self.assertAlmostEqual(strong.max_hp, plain.max_hp * boosted)

    def test_the_penalty_has_a_ceiling(self) -> None:
        store = ProfileStore()
        store.get(TOKEN).accepted = 500
        party = Party("ABCD", store)
        party.join(TOKEN, "Маг")
        party.set_ready(TOKEN, True, 1.0)
        self.assertLessEqual(party.world.pgt_boost, 1.4)


class StoryTests(unittest.TestCase):
    def test_every_relic_carries_a_commit_and_hashes_do_not_repeat(self) -> None:
        hashes = [relic[3].split()[0] for relic in RELICS]
        self.assertEqual(len(hashes), len(set(hashes)))

    def test_the_twists_are_all_there(self) -> None:
        text = " ".join(line for chapter in CHAPTERS for _, line in (*chapter.intro, *chapter.outro))
        self.assertIn("accept()", text)
        self.assertIn("test_people_matter.py", text)
        boss_chat = " ".join(line for _, line in STAGES[15].chat)
        self.assertIn("ветка ada", boss_chat)


class SaveTests(unittest.TestCase):
    def test_all_of_it_survives_a_restart(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profiles.json"
            store = ProfileStore(path)
            profile = store.get(TOKEN)
            profile.runes = ["gc", "daemon"]
            profile.tickets = ["0:sla"]
            profile.accepted = 3
            profile.endings = ["test"]
            profile.duty_best = 7
            profile.duty_name = "Дежурный"
            store.mark()
            store.save()
            again = ProfileStore(path).get(TOKEN)
            self.assertEqual(again.runes, ["gc", "daemon"])
            self.assertEqual(again.tickets, ["0:sla"])
            self.assertEqual(again.accepted, 3)
            self.assertEqual(again.endings, ["test"])
            self.assertEqual(again.duty_best, 7)
            self.assertEqual(again.duty_name, "Дежурный")

    def test_an_old_save_loads_as_it_is(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profiles.json"
            path.write_text('{"abc": {"essence": 5, "cleared": 3}}', encoding="utf-8")
            profile = ProfileStore(path).profiles["abc"]
            self.assertEqual(profile.essence, 5)
            self.assertEqual(profile.runes, [])
            self.assertEqual(profile.accepted, 0)

    def test_a_rune_withdrawn_from_the_book_is_dropped_on_load(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profiles.json"
            path.write_text('{"abc": {"runes": ["gc", "gone"]}}', encoding="utf-8")
            self.assertEqual(ProfileStore(path).profiles["abc"].runes, ["gc"])


if __name__ == "__main__":
    unittest.main()
