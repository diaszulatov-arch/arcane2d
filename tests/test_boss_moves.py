"""Every strange thing a boss can do: that it hurts, and that the way out really works."""

from __future__ import annotations

import contextlib
import io
import json
import math
import unittest

from arcane.boss_moves import (
    ACCEPT_HEAL,
    ACCEPT_TIME,
    BAIT_FAKES,
    BAIT_REAL,
    BISECT_FUSE,
    BLINK_BEAT,
    BLINK_RADIUS,
    BLINK_WARN,
    COLUMNS_REVEAL,
    COLUMNS_TIME,
    DEL_WARN,
    INDEX_PHRASES,
    MOVES,
    RETURN_TIME,
    SCROLL_TIME,
    STRING_TIME,
    AcceptAll,
    Bait,
    Bisect,
    Blink,
    DelFloor,
    DoomScroll,
    ReturnNone,
    UnclosedString,
    ZeroIndex,
    autocomplete,
    safe_rows,
)
from arcane.campaign import STAGES
from arcane.codex import BOSS_MOVES
from arcane.game import TICK_RATE
from arcane.monsters import ATTACKS
from arcane.party import PLAYING, Party
from arcane.profiles import ProfileStore
from arcane.story import StoryArena

TICK = 1 / TICK_RATE
BOSS_STAGE = {stage.chapter.boss: stage for stage in STAGES if stage.is_boss}


class Fight:
    def __init__(self, boss: str, mages: int = 1, seed: int = 3) -> None:
        self.arena = StoryArena(BOSS_STAGE[boss], mages, seed=seed, now=1.0)
        self.mages = [self.arena.add_player(f"Маг {index + 1}") for index in range(mages)]
        self.mage = self.mages[0]
        room = self.arena.dungeon.path[-1] if False else next(r for r in self.arena.dungeon.rooms if r.kind == "boss")
        self.arena.active_room = room
        self.boss = self.arena.spawn_monster(boss, *room.center)
        self.boss.spawned_at = 0.0
        self.boss.next_attack = 1e9
        self.boss.next_special = 1e9
        self.boss.next_contact = 1e9
        self.left, self.top, self.right, self.bottom = self.arena.room_box()
        self.middle = ((self.left + self.right) / 2, (self.top + self.bottom) / 2)
        self.mage.x, self.mage.y = self.left + 100, self.top + 100
        self.mage.invuln_until = 0.0
        self.mage.hp = self.mage.max_hp = 1000.0
        self.arena.drain_events()

    def start(self, key: str):
        self.arena.start_boss_move(self.boss, key)
        return self.arena.boss_moves[-1]

    def advance(self, seconds: float) -> None:
        for _ in range(max(1, round(seconds * TICK_RATE))):
            self.arena.update(self.arena.now + TICK)
            self.mage.invuln_until = 0.0

    def stand(self, x: float, y: float, mage=None) -> None:
        mage = mage or self.mage
        mage.x, mage.y = x, y

    @property
    def moves(self):
        return self.arena.boss_moves


class MeteorInADungeonTests(unittest.TestCase):
    def test_a_meteor_lands_where_it_was_aimed_however_far_from_the_old_arena(self) -> None:
        """Dungeons are far bigger than the arena: its edges must not pull the rocks back."""

        for stage in (STAGES[0], STAGES[9], STAGES[17]):
            arena = StoryArena(stage, 1, seed=3, now=1.0, known_upto=len(STAGES) - 1)
            mage = arena.add_player("Маг")
            room = max(arena.dungeon.rooms, key=lambda r: r.center[0] + r.center[1])
            mage.x, mage.y = room.center
            self.assertGreater(max(mage.x - 1900, mage.y - 1100), 0, "this has to be outside the old arena")
            target_x, target_y = mage.x + 150, mage.y
            result = arena.cast(mage.id, f"meteor({target_x}, {target_y})", 0, 0.0)
            self.assertTrue(result["ok"], result)
            self.assertTrue(arena.meteors)
            for rock in arena.meteors:
                self.assertLess(math.hypot(rock.x - target_x, rock.y - target_y), 60, stage.title)


class NobodyHomeTests(unittest.TestCase):
    """The server has one loop for everything: a trick must survive having no one to hit."""

    def play_out(self, boss: str, key: str, nobody: str) -> None:
        fight = Fight(boss)
        if nobody == "dead":
            fight.mage.dead = True
        else:
            fight.mage.x, fight.mage.y = fight.arena.dungeon.rooms[0].center
        fight.start(key)
        for _ in range(int(14 * TICK_RATE)):
            fight.arena.update(fight.arena.now + TICK)
            fight.arena.snapshot()
            fight.arena.drain_events()

    def test_no_trick_breaks_when_the_mage_is_dead_or_elsewhere(self) -> None:
        tricks = (
            ("bracket", "unclosed"), ("bracket", "blink"), ("scroll", "doomscroll"), ("scroll", "bait"),
            ("nullqueen", "return_none"), ("nullqueen", "del_floor"), ("indexer", "zero_index"),
            ("indexer", "bisect"), ("pgt", "accept_all"),
        )
        for boss, key in tricks:
            for nobody in ("dead", "elsewhere"):
                with self.subTest(key=key, nobody=nobody):
                    self.play_out(boss, key, nobody)

    def test_a_broken_trick_ends_itself_and_nothing_else(self) -> None:
        fight = Fight("bracket")
        move = fight.start("unclosed")
        move.update = lambda now, dt: 1 / 0
        with contextlib.redirect_stderr(io.StringIO()):
            fight.advance(0.1)
        self.assertEqual(fight.moves, [])


class AllMovesTests(unittest.TestCase):
    def test_every_move_is_a_real_attack_with_a_tip_and_in_the_handbook(self) -> None:
        listed = {move for moves in BOSS_MOVES.values() for move in moves}
        for key in (*MOVES, "autocomplete"):
            self.assertIn(key, ATTACKS)
            self.assertTrue(ATTACKS[key].tip)
            self.assertIn(key, listed)

    def test_a_move_ends_with_its_boss(self) -> None:
        fight = Fight("bracket")
        fight.start("unclosed")
        fight.arena.remove_monster(fight.boss)
        fight.advance(0.1)
        self.assertEqual(fight.moves, [])

    def test_a_move_can_be_sent_to_the_client(self) -> None:
        for boss, keys in (
            ("bracket", ("unclosed", "blink")),
            ("scroll", ("doomscroll", "bait")),
            ("nullqueen", ("return_none", "del_floor")),
            ("indexer", ("zero_index", "bisect")),
            ("pgt", ("accept_all",)),
        ):
            for key in keys:
                fight = Fight(boss)
                fight.start(key)
                fight.advance(0.2)
                state = json.loads(json.dumps(fight.arena.snapshot()))
                self.assertEqual(state["boss_moves"][0]["k"], MOVES[key].kind, key)

    def test_nothing_is_sent_when_nothing_is_happening(self) -> None:
        self.assertNotIn("boss_moves", Fight("bracket").arena.snapshot())

    def test_each_boss_comes_round_to_its_moves_on_its_own(self) -> None:
        """Left alone with a mage who cannot die, it gets to them in a real fight."""

        for boss, wanted in (
            ("bracket", {UnclosedString, Blink}),
            ("scroll", {DoomScroll, Bait}),
            ("nullqueen", {ReturnNone, DelFloor}),
            ("indexer", {ZeroIndex, Bisect}),
            ("pgt", {AcceptAll}),
        ):
            fight = Fight(boss)
            fight.boss.next_attack = 0.0
            fight.boss.next_special = 0.0
            fight.mage.max_hp = fight.mage.hp = 1e9
            seen = set()
            for _ in range(int(120 * TICK_RATE)):
                fight.arena.update(fight.arena.now + TICK)
                fight.mage.hp = fight.mage.max_hp
                fight.arena.gate_boss = None
                fight.arena.drain_events()
                fight.boss.hp = fight.boss.max_hp
                seen |= {type(move) for move in fight.moves}
                if wanted <= seen:
                    break
            self.assertLessEqual(wanted, seen, boss)


class UnclosedStringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fight = Fight("bracket")
        self.move = self.fight.start("unclosed")

    def test_it_follows_you_and_leaves_itself_behind(self) -> None:
        fight = self.fight
        start = math.hypot(self.move.head[0] - fight.mage.x, self.move.head[1] - fight.mage.y)
        fight.advance(1.0)
        self.assertLess(math.hypot(self.move.head[0] - fight.mage.x, self.move.head[1] - fight.mage.y), start)
        self.assertGreater(len(self.move.cells), 3)

    def test_standing_in_it_hurts(self) -> None:
        fight = self.fight
        hp = fight.mage.hp
        fight.stand(*self.move.head)
        fight.advance(0.2)
        self.assertLess(fight.mage.hp, hp)

    def test_touching_the_quote_closes_it_and_deafens_the_boss(self) -> None:
        fight = self.fight
        fight.advance(1.0)
        self.assertIsNotNone(self.move.quote)
        fight.stand(*self.move.quote)
        fight.advance(0.1)
        self.assertEqual(fight.moves, [])
        self.assertGreater(fight.boss.stun_until, fight.arena.now)
        self.assertGreater(fight.boss.dizzy_until, fight.arena.now)

    def test_the_quote_is_across_the_room(self) -> None:
        fight = self.fight
        fight.advance(1.0)
        distance = math.hypot(self.move.quote[0] - fight.mage.x, self.move.quote[1] - fight.mage.y)
        self.assertGreater(distance, 300)
        self.assertTrue(fight.arena.can_stand(self.move.quote[0], self.move.quote[1], 20))

    def test_left_alone_it_runs_out(self) -> None:
        self.fight.advance(STRING_TIME + 0.2)
        self.assertEqual(self.fight.moves, [])


class BlinkTests(unittest.TestCase):
    def test_only_the_lit_circles_burn_and_they_take_turns(self) -> None:
        fight = Fight("bracket")
        move = fight.start("blink")
        dark = next(c for c in move.cells if c[2] != move.on)
        fight.stand(dark[0], dark[1])
        hp = fight.mage.hp
        lit = move.on
        fight.advance(BLINK_BEAT)
        self.assertEqual(move.on, lit, "still the first beat")
        self.assertEqual(fight.mage.hp, hp, "you stood where it was off")
        fight.advance(BLINK_BEAT + 0.15)
        self.assertNotEqual(move.on, lit, "they take turns")
        self.assertLess(fight.mage.hp, hp, "and now it is your turn")

    def test_the_first_beat_gives_time_to_see(self) -> None:
        fight = Fight("bracket")
        move = fight.start("blink")
        lit = next(c for c in move.cells if c[2] == move.on)
        fight.stand(lit[0], lit[1])
        hp = fight.mage.hp
        fight.advance(BLINK_WARN + 0.1)
        self.assertEqual(fight.mage.hp, hp)

    def test_standing_in_the_lit_ring_when_it_fires_hurts(self) -> None:
        fight = Fight("bracket")
        move = fight.start("blink")
        lit = next(c for c in move.cells if c[2] == move.on)
        fight.stand(lit[0], lit[1])
        hp = fight.mage.hp
        fight.advance(BLINK_BEAT + 0.1)
        self.assertLess(fight.mage.hp, hp)

    def test_it_ends(self) -> None:
        fight = Fight("bracket")
        fight.start("blink")
        fight.advance(BLINK_BEAT * 7)
        self.assertEqual(fight.moves, [])


class DoomScrollTests(unittest.TestCase):
    def test_the_floor_carries_you_down(self) -> None:
        fight = Fight("scroll")
        fight.stand(*fight.middle)
        fight.start("doomscroll")
        y = fight.mage.y
        fight.advance(1.0)
        self.assertGreater(fight.mage.y, y + 40)

    def test_the_bottom_of_the_page_burns(self) -> None:
        fight = Fight("scroll")
        fight.stand(fight.middle[0], fight.bottom - 30)
        fight.start("doomscroll")
        hp = fight.mage.hp
        fight.advance(0.2)
        self.assertLess(fight.mage.hp, hp)

    def test_posts_keep_coming_with_a_gap(self) -> None:
        fight = Fight("scroll")
        fight.start("doomscroll")
        fight.advance(0.7)
        shots = [p for p in fight.arena.projectiles if p.owner == fight.boss.id]
        self.assertGreater(len(shots), 3)
        xs = sorted(p.x for p in shots)
        self.assertGreater(max(b - a for a, b in zip(xs, xs[1:])), 100, "a way through")

    def test_it_ends(self) -> None:
        fight = Fight("scroll")
        fight.start("doomscroll")
        fight.advance(SCROLL_TIME + 0.1)
        self.assertEqual(fight.moves, [])


class BaitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fight = Fight("scroll")
        self.move = self.fight.start("bait")

    def test_exactly_one_tells_the_truth_and_it_does_not_shout(self) -> None:
        real = [item for item in self.move.items if item["real"]]
        self.assertEqual(len(real), 1)
        self.assertEqual(real[0]["label"], BAIT_REAL)
        for item in self.move.items:
            if not item["real"]:
                self.assertIn(item["label"], BAIT_FAKES)

    def test_the_real_one_heals(self) -> None:
        fight = self.fight
        fight.mage.hp = 100.0
        item = next(item for item in self.move.items if item["real"])
        fight.stand(item["x"], item["y"])
        fight.advance(0.05)
        self.assertGreater(fight.mage.hp, 100.0)

    def test_a_fake_one_bites_and_slows(self) -> None:
        fight = self.fight
        item = next(item for item in self.move.items if not item["real"])
        hp = fight.mage.hp
        fight.stand(item["x"], item["y"])
        fight.advance(0.05)
        self.assertLess(fight.mage.hp, hp)
        self.assertGreater(fight.mage.slow_until, fight.arena.now)
        self.assertNotIn(item, self.move.items)


class ReturnNoneTests(unittest.TestCase):
    def test_she_takes_no_damage_and_sends_it_back(self) -> None:
        fight = Fight("nullqueen")
        fight.start("return_none")
        hp = fight.boss.hp
        fight.arena.damage(target=fight.boss, amount=100, source=fight.mage, kind="fire", hit_x=0.0, hit_y=0.0)
        self.assertEqual(fight.boss.hp, hp)
        back = [p for p in fight.arena.projectiles if p.owner == fight.boss.id]
        self.assertEqual(len(back), 1)
        self.assertAlmostEqual(
            back[0].angle % math.tau,
            math.atan2(fight.mage.y - fight.boss.y, fight.mage.x - fight.boss.x) % math.tau,
            places=2,
        )

    def test_a_barrage_does_not_become_a_wall_of_shots(self) -> None:
        fight = Fight("nullqueen")
        fight.start("return_none")
        for _ in range(10):
            fight.arena.damage(target=fight.boss, amount=5, source=fight.mage, kind="spark", hit_x=0.0, hit_y=0.0)
        self.assertEqual(len([p for p in fight.arena.projectiles if p.owner == fight.boss.id]), 1)

    def test_after_it_she_is_open(self) -> None:
        fight = Fight("nullqueen")
        fight.start("return_none")
        fight.advance(RETURN_TIME + 0.1)
        self.assertEqual(fight.moves, [])
        self.assertGreater(fight.boss.exposed_until, fight.arena.now)
        hp = fight.boss.hp
        fight.arena.damage(target=fight.boss, amount=100, source=fight.mage, kind="fire", hit_x=0.0, hit_y=0.0)
        self.assertLess(fight.boss.hp, hp)


class DelFloorTests(unittest.TestCase):
    def test_a_deleted_cell_warns_first_then_hurts(self) -> None:
        fight = Fight("nullqueen")
        move = fight.start("del_floor")
        fight.advance(TICK)
        cell = move.cells[0]
        x, y = cell["x"] + 40, cell["y"] + 40
        fight.stand(x, y)
        hp = fight.mage.hp
        fight.advance(DEL_WARN * 0.5)
        fight.stand(x, y)
        self.assertEqual(fight.mage.hp, hp, "there is time to step off")
        fight.advance(DEL_WARN * 0.7)
        self.assertLess(fight.mage.hp, hp)

    def test_some_floor_always_survives_and_it_comes_back(self) -> None:
        fight = Fight("nullqueen")
        move = fight.start("del_floor")
        total = len(move.grid)
        peak = 0
        for _ in range(int(14 * TICK_RATE)):
            fight.advance(TICK)
            if not fight.moves:
                break
            peak = max(peak, len(move.cells))
        self.assertLess(peak, total)
        self.assertEqual(fight.moves, [], "the floor returns")


class ZeroIndexTests(unittest.TestCase):
    def test_every_phrase_means_what_python_says(self) -> None:
        for phrase, meaning in INDEX_PHRASES:
            for count in (5, 6, 7):
                rows = list(range(count))
                truth = eval(phrase, {"len": len}, {"rows": rows})  # noqa: S307 - our own constants
                self.assertEqual(safe_rows(meaning, count), truth if isinstance(truth, list) else [truth], phrase)

    def fight_with(self, phrase_index: int) -> tuple[Fight, ZeroIndex]:
        fight = Fight("indexer")
        move = fight.start("zero_index")
        move.phrase, meaning = INDEX_PHRASES[phrase_index]
        move.safe = safe_rows(meaning, move.count)
        return fight, move

    def column_center(self, fight: Fight, move: ZeroIndex, column: int) -> float:
        return fight.left + (fight.right - fight.left) / move.count * (column + 0.5)

    def test_it_counts_from_zero(self) -> None:
        fight, move = self.fight_with(2)  # rows[2]
        self.assertEqual(move.safe, [2])
        fight.stand(self.column_center(fight, move, 2), fight.middle[1])
        hp = fight.mage.hp
        fight.advance(COLUMNS_TIME + 0.1)
        self.assertEqual(fight.mage.hp, hp)
        self.assertEqual(fight.moves, [])

    def test_whoever_counts_from_one_is_in_the_wrong_row(self) -> None:
        fight, move = self.fight_with(2)  # the "second" row is rows[1], which is not safe
        fight.stand(self.column_center(fight, move, 1), fight.middle[1])
        hp = fight.mage.hp
        fight.advance(COLUMNS_TIME + 0.1)
        self.assertLess(fight.mage.hp, hp)

    def test_negative_index_is_from_the_right(self) -> None:
        fight, move = self.fight_with(4)  # rows[-1]
        self.assertEqual(move.safe, [move.count - 1])

    def test_a_slice_gives_two_rows(self) -> None:
        fight, move = self.fight_with(6)  # rows[1:3]
        self.assertEqual(move.safe, [1, 2])
        for column in move.safe:
            fight.stand(self.column_center(fight, move, column), fight.middle[1])
        hp = fight.mage.hp
        fight.advance(COLUMNS_TIME + 0.1)
        self.assertEqual(fight.mage.hp, hp)

    def test_the_answer_shows_only_at_the_last_moment(self) -> None:
        fight, move = self.fight_with(1)
        self.assertNotIn("safe", move.view())
        fight.advance(COLUMNS_TIME - COLUMNS_REVEAL + 0.05)
        self.assertEqual(move.view()["safe"], move.safe)

    def test_later_phases_know_harder_phrases(self) -> None:
        early = {Fight("indexer").start("zero_index").phrase for _ in range(30)}
        late = set()
        for seed in range(30):
            fight = Fight("indexer", seed=seed)
            fight.boss.phase = 2
            late.add(fight.start("zero_index").phrase)
        self.assertLessEqual(early, {phrase for phrase, _ in INDEX_PHRASES[:4]})
        self.assertTrue(late - {phrase for phrase, _ in INDEX_PHRASES[:4]})


class BisectTests(unittest.TestCase):
    def test_it_burns_the_half_you_are_in_and_narrows_there(self) -> None:
        fight = Fight("indexer")
        fight.stand(fight.left + 80, fight.middle[1])
        move = fight.start("bisect")
        self.assertEqual(move.side[0], fight.left)
        hp = fight.mage.hp
        fight.advance(BISECT_FUSE + 0.1)
        self.assertLess(fight.mage.hp, hp)
        self.assertLess(move.hi, fight.right, "it searches further in the half it burnt")

    def test_crossing_the_middle_makes_it_lose_you(self) -> None:
        fight = Fight("indexer")
        fight.stand(fight.left + 80, fight.middle[1])
        fight.start("bisect")
        hp = fight.mage.hp
        fight.stand(fight.right - 80, fight.middle[1])
        fight.advance(BISECT_FUSE + 0.1)
        self.assertEqual(fight.mage.hp, hp)
        self.assertEqual(fight.moves, [])
        self.assertGreater(fight.boss.stun_until, fight.arena.now, "ValueError: it stands there")


class AcceptAllTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fight = Fight("pgt")
        self.fight.boss.hp = self.fight.boss.max_hp * 0.5
        self.move = self.fight.start("accept_all")

    def test_it_hits_the_whole_room(self) -> None:
        fight = self.fight
        hp = fight.mage.hp
        fight.stand(fight.left + 40, fight.top + 40)
        if math.hypot(fight.mage.x - self.move.accept[0], fight.mage.y - self.move.accept[1]) < 200:
            fight.stand(fight.right - 40, fight.top + 40)
        fight.advance(ACCEPT_TIME + 0.1)
        self.assertLess(fight.mage.hp, hp)
        self.assertEqual(fight.arena.accepted_in_battle, [])

    def test_the_button_saves_you_heals_him_and_goes_on_your_record(self) -> None:
        fight = self.fight
        hp = fight.mage.hp
        boss_hp = fight.boss.hp
        fight.stand(*self.move.accept)
        fight.advance(ACCEPT_TIME + 0.1)
        self.assertEqual(fight.mage.hp, hp)
        self.assertAlmostEqual(fight.boss.hp, boss_hp + fight.boss.max_hp * ACCEPT_HEAL, delta=1.0)
        self.assertEqual(fight.arena.accepted_in_battle, [fight.mage.id])

    def test_rejecting_saves_you_for_nothing(self) -> None:
        fight = self.fight
        hp = fight.mage.hp
        boss_hp = fight.boss.hp
        fight.stand(*self.move.reject)
        fight.advance(ACCEPT_TIME + 0.1)
        self.assertEqual(fight.mage.hp, hp)
        self.assertEqual(fight.boss.hp, boss_hp)
        self.assertEqual(fight.arena.accepted_in_battle, [])

    def test_the_easy_way_is_nearer_than_the_honest_one(self) -> None:
        fight = self.fight
        to_accept = math.hypot(self.move.accept[0] - fight.mage.x, self.move.accept[1] - fight.mage.y)
        to_reject = math.hypot(self.move.reject[0] - fight.mage.x, self.move.reject[1] - fight.mage.y)
        self.assertLess(to_accept, to_reject)

    def test_a_party_writes_the_press_down(self) -> None:
        store = ProfileStore()
        party = Party("TEST", store)
        token = "a" * 32
        party.join(token, "Маг")
        party.stage_index = len(STAGES) - 1
        party.set_ready(token, True, 1.0)
        self.assertEqual(party.state, PLAYING)
        before = store.get(token).accepted
        party.world.accepted_in_battle.append(party.seats[0].player_id)
        party.tick(1.1)
        self.assertEqual(store.get(token).accepted, before + 1)
        self.assertEqual(party.world.accepted_in_battle, [])


class AutocompleteTests(unittest.TestCase):
    def test_it_waits_where_you_are_going(self) -> None:
        fight = Fight("pgt")
        fight.stand(*fight.middle)
        fight.mage.last_x = fight.mage.x - 200 / TICK_RATE
        fight.mage.last_y = fight.mage.y
        autocomplete(fight.arena, fight.boss)
        marks = [hazard for hazard in fight.arena.hazards if hazard.label]
        self.assertEqual(len(marks), 3)
        xs = [hazard.x for hazard in marks]
        self.assertEqual(xs, sorted(xs), "further ahead the later it lands")
        self.assertGreater(xs[0], fight.mage.x)

    def test_standing_still_it_finishes_nothing_but_your_spot(self) -> None:
        fight = Fight("pgt")
        fight.stand(*fight.middle)
        fight.mage.last_x, fight.mage.last_y = fight.mage.x, fight.mage.y
        autocomplete(fight.arena, fight.boss)
        for hazard in fight.arena.hazards:
            self.assertLess(math.hypot(hazard.x - fight.mage.x, hazard.y - fight.mage.y), 30)


if __name__ == "__main__":
    unittest.main()
