"""Every new bug has one rule to learn. Each test here is that rule."""

from __future__ import annotations

import math
import re
import unittest
from pathlib import Path

from arcane import foes
from arcane.campaign import STAGES, STAGE_FOES
from arcane.dungeon import TILE
from arcane.game import TICK_RATE
from arcane.monsters import SPECIES, THINKERS
from arcane.story import StoryArena

TICK = 1 / TICK_RATE
PUBLIC = Path(__file__).parent.parent / "public" / "js"


def stage_of(key: str) -> int:
    for index, row in enumerate(STAGE_FOES):
        if key in row:
            return index
    return next(stage.index for stage in STAGES if stage.mini == key)


class Scene:
    """One mage in a fight room with the creature under test on the other side of it."""

    def __init__(self, key: str, *, stage: int | None = None, dx: float = 170.0) -> None:
        self.arena = StoryArena(
            STAGES[stage_of(key) if stage is None else stage], 1, seed=3, now=1.0, known_upto=19
        )
        self.mage = self.arena.add_player("Маг")
        self.mage.invuln_until = 1e9
        self.room = [room for room in self.arena.dungeon.path if room.kind in ("combat", "boss")][-1]
        self.arena.active_room = self.room
        cx, cy = self.room.center
        self.mage.x, self.mage.y = self.arena.dungeon.open_near(cx - 120, cy, 20.0)
        self.bug = self.spawn(key, dx)

    def spawn(self, key: str, dx: float = 170.0, dy: float = 0.0):
        radius = SPECIES[key].radius
        x, y = self.arena.dungeon.open_near(self.mage.x + dx, self.mage.y + dy, radius)
        monster = self.arena.spawn_monster(key, x, y)
        monster.spawned_at = 0.0
        return monster

    def run(self, seconds: float) -> list[dict]:
        events: list[dict] = []
        for _ in range(int(seconds * TICK_RATE)):
            self.arena.update(self.arena.now + TICK)
            self.arena.snapshot()
            events += self.arena.drain_events()
        return events

    def hit(self, monster, amount: float, kind: str = "fire") -> float:
        return self.arena.damage(
            target=monster, amount=amount, source=self.mage, kind=kind,
            hit_x=monster.x, hit_y=monster.y,
        )

    def kill(self, monster, kind: str = "fire") -> None:
        monster.invuln_until = 0.0
        self.hit(monster, monster.hp + 50, kind)

    def kin(self, key: str) -> list:
        return [m for m in self.arena.monsters.values() if m.species.key == key]

    def wake(self) -> None:
        """Whatever just arrived stops waiting to load."""

        for monster in self.arena.monsters.values():
            monster.spawned_at = 0.0

    def stand_still(self) -> None:
        self.arena.set_input(self.mage.id, up=False, down=False, left=False, right=False)


class RosterTests(unittest.TestCase):
    def test_every_stage_has_two_bugs_of_its_own_and_a_mini_boss(self) -> None:
        seen: set[str] = set()
        for stage in STAGES:
            self.assertEqual(len(stage.fresh), 2, stage.title)
            self.assertTrue(stage.mini, stage.title)
            self.assertTrue(SPECIES[stage.mini].boss)
            for key in stage.fresh:
                self.assertIn(key, stage.roster)
                self.assertNotIn(key, seen, "each pair belongs to one stage")
                self.assertFalse(SPECIES[key].boss)
                seen.add(key)

    def test_a_bug_stays_on_its_own_stage(self) -> None:
        for stage in STAGES:
            for other in STAGES:
                if other is not stage:
                    self.assertFalse(set(stage.fresh) & set(other.roster))

    def test_every_creature_has_a_brain_and_a_body(self) -> None:
        source = (PUBLIC / "foe-sprites.js").read_text(encoding="utf-8")
        drawn = set(re.findall(r"^  (\w+): \{$", source, re.MULTILINE))
        for stage in STAGES:
            for key in stage.fresh:
                self.assertIn(SPECIES[key].ai, THINKERS)
                self.assertIn(key, drawn)

    def test_sprites_only_use_their_own_colours(self) -> None:
        source = (PUBLIC / "foe-sprites.js").read_text(encoding="utf-8")
        for name, colors, art in re.findall(r"^  (\w+): \{\n    colors: \{([^}]*)\},\n    art: \[([^\]]*)\]", source, re.MULTILINE):
            known = set(re.findall(r"(\w): \"", colors)) | {"."}
            for row in re.findall(r'"([^"]*)"', art):
                self.assertLessEqual(set(row), known, name)

    def test_a_boss_stage_now_has_a_room_before_the_boss(self) -> None:
        for stage in STAGES:
            if stage.is_boss:
                self.assertEqual(stage.layout, ["start", "combat", "boss"])
                arena = StoryArena(stage, 1, seed=3, now=1.0)
                self.assertEqual(arena.mini_room.kind, "combat")

    def test_this_stages_own_bugs_are_met_in_the_first_waves(self) -> None:
        for stage in STAGES:
            if stage.is_boss:
                continue
            arena = StoryArena(stage, 1, seed=3, now=1.0)
            arena.add_player("Маг")
            room = next(r for r in arena.dungeon.path if r.kind == "combat")
            arena.active_room = room
            met: set[str] = set()
            for _ in range(3):
                arena._spawn_wave(room)
                met |= {m.species.key for m in arena.monsters.values()}
            self.assertLessEqual(set(stage.fresh), met, stage.title)


class ChapterOneTests(unittest.TestCase):
    def test_the_counter_shoots_faster_the_longer_it_lives(self) -> None:
        scene = Scene("visits")
        scene.bug.next_attack = 0.0
        scene.run(0.1)
        first = scene.bug.next_attack - scene.arena.now
        scene.bug.count = 8
        scene.bug.next_attack = 0.0
        scene.run(0.1)
        self.assertLess(scene.bug.next_attack - scene.arena.now, first)
        self.assertEqual(scene.bug.text, "00009")

    def test_the_construction_gif_leaves_floor_that_slows_you(self) -> None:
        scene = Scene("construction")
        scene.mage.invuln_until = 0.0
        scene.bug.next_attack = 0.0
        scene.run(0.1)
        patch = next(f for f in scene.arena.fields if f.kind == "wip")
        scene.mage.x, scene.mage.y = patch.x, patch.y
        scene.mage.slow_until = 0.0
        scene.run(0.1)
        self.assertGreater(scene.mage.slow_until, scene.arena.now)

    def test_a_deadlock_gets_up_if_its_partner_lives(self) -> None:
        scene = Scene("deadlock")
        other = scene.spawn("deadlock", 170, 60)
        scene.run(0.1)
        self.assertEqual(scene.bug.link, other.id)
        scene.kill(scene.bug)
        self.assertIn(scene.bug.id, scene.arena.monsters)
        self.assertEqual(scene.bug.state, "down")
        self.assertEqual(scene.hit(scene.bug, 500), 0.0, "nothing lands on it while it is down")
        scene.run(foes.DEADLOCK_WAKE + 0.2)
        self.assertEqual(scene.bug.state, "idle")
        self.assertGreater(scene.bug.hp, scene.bug.max_hp * 0.5)

    def test_a_deadlock_dies_when_both_go_down_together(self) -> None:
        scene = Scene("deadlock")
        other = scene.spawn("deadlock", 170, 60)
        scene.run(0.1)
        scene.kill(scene.bug)
        scene.kill(other)
        self.assertEqual(scene.kin("deadlock"), [])

    def test_a_deadlock_with_nobody_to_hold_just_dies(self) -> None:
        scene = Scene("deadlock")
        scene.run(0.1)
        scene.kill(scene.bug)
        self.assertEqual(scene.kin("deadlock"), [])

    def test_an_injection_wipes_only_the_rune_you_just_used(self) -> None:
        scene = Scene("sqlinject", dx=30)
        mage = scene.mage
        mage.invuln_until = 0.0
        mage.max_hp = mage.hp = 5000.0
        scene.arena.last_slot[mage.id] = 1
        for _ in range(200):
            scene.bug.x, scene.bug.y = mage.x + 20, mage.y
            scene.run(TICK * 2)
            if scene.arena.cursed(mage, "drop"):
                break
        self.assertTrue(scene.arena.cursed(mage, "drop"))
        mage.cast_lock = 0.0
        mage.mana = mage.max_mana
        refused = scene.arena.cast(mage.id, "fireball(aim())", 1, 0.0)
        self.assertFalse(refused["ok"])
        self.assertIn("DROP TABLE", refused["error"])
        self.assertTrue(scene.arena.cast(mage.id, "fireball(aim())", 0, 0.0)["ok"])

    def test_the_marquee_spells_itself_out_and_tears_where_it_is_hit(self) -> None:
        scene = Scene("marquee")
        scene.run(0.1)
        letters = scene.kin("marquee")
        self.assertEqual(len(letters), len(foes.MARQUEE_TEXT))
        self.assertEqual("".join(m.text for m in letters), foes.MARQUEE_TEXT)
        self.assertAlmostEqual(scene.arena.boss_max_hp, sum(m.max_hp for m in letters))
        scene.wake()
        middle = letters[7]
        behind = next(m for m in letters if m.link == middle.id)
        scene.kill(middle)
        scene.run(0.2)
        self.assertEqual(behind.link, 0, "the next letter leads what is left of the string")
        for letter in scene.kin("marquee"):
            scene.kill(letter)
        self.assertEqual(scene.kin("marquee"), [])

    def test_the_necroposter_raises_the_last_one_killed(self) -> None:
        scene = Scene("necroposter")
        victim = scene.spawn("popup", 200, 80)
        scene.kill(victim)
        self.assertEqual(scene.arena.fallen[-1][0], "popup")
        scene.bug.next_special = 0.0
        scene.run(0.1)
        raised = scene.kin("popup")
        self.assertEqual(len(raised), 1)
        self.assertAlmostEqual(raised[0].hp, raised[0].max_hp * foes.RAISED_SHARE)

    def test_capslock_fires_a_letter_you_cannot_miss(self) -> None:
        scene = Scene("capslock")
        scene.arena.fire(scene.bug, 0.0)
        shot = scene.arena.projectiles[-1]
        self.assertGreater(shot.radius, 16)
        self.assertEqual(scene.arena.snapshot()["projectiles"][-1]["radius"], shot.radius)

    def test_a_semicolon_leaves_a_comma(self) -> None:
        scene = Scene("semicolon")
        scene.kill(scene.bug)
        self.assertEqual(len(scene.kin("comma")), 1)

    def test_the_string_only_burns_once_it_has_landed(self) -> None:
        scene = Scene("quotemark")
        scene.mage.invuln_until = 0.0
        scene.bug.next_attack = 0.0
        scene.run(0.1)
        string = next(f for f in scene.arena.fields if f.kind == "string")
        scene.mage.x, scene.mage.y = (string.x + string.x2) / 2, (string.y + string.y2) / 2
        before = scene.mage.hp
        scene.bug.next_attack = 1e9
        self.assertGreater(string.arm_at, scene.arena.now)
        scene.run(TICK)
        self.assertEqual(scene.mage.hp, before, "the fuse is still burning")
        string.arm_at = scene.arena.now
        scene.run(0.1)
        self.assertLess(scene.mage.hp, before)

    def test_vim_and_emacs_hurt_each_other_far_more_than_you(self) -> None:
        scene = Scene("vim")
        scene.run(0.1)
        emacs = scene.kin("emacs")[0]
        scene.wake()
        self.assertEqual(emacs.link, scene.bug.id)
        self.assertIn(emacs, scene.arena.targets_for(scene.bug.id))
        self.assertAlmostEqual(scene.arena.boss_max_hp, scene.bug.max_hp + emacs.max_hp)
        hp = emacs.hp
        scene.arena.damage(target=emacs, amount=10, source=scene.bug, kind="orb", hit_x=emacs.x, hit_y=emacs.y)
        self.assertAlmostEqual(hp - emacs.hp, 10 * foes.HOLYWAR_RIVALRY)

    def test_unexpected_eof_pushes_you_on_and_is_pushed_back_by_damage(self) -> None:
        scene = Scene("eof")
        scene.run(1.0)
        wall = scene.bug.memo
        left = scene.arena.room_box()[0]
        self.assertGreater(wall.x2, left)
        scene.mage.x = wall.x2 - 6
        x = scene.mage.x
        scene.run(0.1)
        self.assertGreater(scene.mage.x, x, "it pushes you ahead of it")
        front = scene.bug.charge
        scene.hit(scene.bug, 60)
        self.assertLess(scene.bug.charge, front)
        scene.kill(scene.bug)
        scene.run(0.1)
        self.assertNotIn(wall, scene.arena.fields, "the wall goes with it")


class ChapterTwoTests(unittest.TestCase):
    def test_hype_grows_when_hit_and_collapses_when_ignored(self) -> None:
        scene = Scene("hype")
        scene.run(0.1)
        scene.hit(scene.bug, 5)
        scene.hit(scene.bug, 5)
        self.assertGreater(scene.bug.charge, 0.1)
        full = scene.hit(scene.bug, 100)
        scene.run(foes.HYPE_COOL + 0.2)
        self.assertEqual(scene.bug.state, "flat")
        self.assertEqual(scene.bug.charge, 0.0)
        self.assertGreater(scene.hit(scene.bug, 100), full, "ignored for a while, it hurts more")

    def test_autoplay_is_only_dangerous_up_close(self) -> None:
        scene = Scene("autoplay", dx=scene_far())
        scene.bug.next_attack = 0.0
        scene.run(0.2)
        self.assertEqual(scene.arena.hazards, [])
        scene.mage.x, scene.mage.y = scene.bug.x - 60, scene.bug.y
        scene.run(0.2)
        self.assertTrue(scene.arena.hazards)

    def test_shorts_drag_you_in(self) -> None:
        scene = Scene("shorts", dx=260)
        far = math.hypot(scene.mage.x - scene.bug.x, scene.mage.y - scene.bug.y)
        scene.run(1.0)
        self.assertLess(math.hypot(scene.mage.x - scene.bug.x, scene.mage.y - scene.bug.y), far - 30)

    def test_no_mana_comes_back_in_a_stuffy_room(self) -> None:
        scene = Scene("dushnila", dx=120)
        scene.mage.mana = 10.0
        scene.run(1.0)
        self.assertAlmostEqual(scene.mage.mana, 10.0, delta=0.5)
        scene.mage.x = scene.bug.x - foes.STUFFY_REACH - 200
        scene.mage.mana = 10.0
        scene.bug.x, scene.bug.y = scene.mage.x + foes.STUFFY_REACH + 200, scene.mage.y
        scene.bug.stun_until = 1e9
        scene.run(1.0)
        self.assertGreater(scene.mage.mana, 10.5)

    def test_first_cries_out_hurries_the_rest_and_leaves(self) -> None:
        scene = Scene("firstcomment", dx=30)
        other = scene.spawn("popup", 300)
        events = scene.run(0.4)
        self.assertEqual(scene.kin("firstcomment"), [])
        self.assertGreater(other.hurry_until, scene.arena.now)
        self.assertTrue(any(e["e"] == "say" and e["text"] == "Первый!" for e in events))

    def test_the_spinner_cannot_be_hurt_until_it_hangs(self) -> None:
        scene = Scene("spinner")
        scene.run(0.1)
        self.assertEqual(scene.hit(scene.bug, 50), 0.0)
        scene.bug.charge = 99.0
        scene.run(0.1)
        self.assertEqual(scene.bug.state, "stuck")
        self.assertGreater(scene.hit(scene.bug, 50), 0.0)
        scene.run(foes.SPINNER_STUCK + 0.2)
        self.assertEqual(scene.bug.state, "idle")
        self.assertLess(scene.bug.charge, 10)

    def test_the_spinners_arc_burns_where_it_points_only(self) -> None:
        scene = Scene("spinner", dx=150)
        mage = scene.mage
        mage.invuln_until = 0.0
        scene.run(0.1)
        hp = mage.hp
        # Point the arc away from the mage: nothing.
        scene.bug.spin = math.atan2(scene.bug.y - mage.y, scene.bug.x - mage.x)
        scene.bug.next_attack = 1e9
        scene.run(TICK)
        self.assertEqual(mage.hp, hp)
        scene.bug.spin = math.atan2(mage.y - scene.bug.y, mage.x - scene.bug.x)
        scene.run(TICK)
        self.assertLess(mage.hp, hp)

    def test_hitting_the_bell_reads_its_notifications(self) -> None:
        scene = Scene("bell")
        scene.bug.charge = 50.0
        scene.hit(scene.bug, 5)
        self.assertLess(scene.bug.charge, 50.0)
        scene.bug.next_special = 0.0
        scene.bug.charge = 60.0
        scene.run(0.1)
        wave = next(h for h in scene.arena.hazards if h.radius > foes.BELL_BASE)
        self.assertGreater(wave.radius, foes.BELL_BASE + 200)
        self.assertLess(scene.bug.charge, 30)

    def test_you_also_liked_sends_what_died_before_it(self) -> None:
        scene = Scene("alsolike")
        victim = scene.spawn("toxic", 200, 90)
        scene.kill(victim)
        scene.kill(scene.bug)
        self.assertEqual(len(scene.kin("toxic")), 1)

    def test_the_filter_bubble_only_lets_in_those_inside(self) -> None:
        scene = Scene("bubble", dx=foes.BUBBLE_RADIUS + 150)
        self.assertEqual(scene.hit(scene.bug, 10), 0.0)
        scene.mage.x, scene.mage.y = scene.bug.x - 60, scene.bug.y
        self.assertGreater(scene.hit(scene.bug, 10), 0.0)

    def test_read_more_turns_out_to_be_long(self) -> None:
        scene = Scene("readmore")
        small = scene.bug.max_hp
        scene.kill(scene.bug)
        self.assertEqual(len(scene.kin("readmore")), 1)
        self.assertAlmostEqual(scene.bug.max_hp, small * foes.READMORE_GROWTH)
        self.assertEqual(scene.bug.hp, scene.bug.max_hp)
        scene.kill(scene.bug)
        self.assertEqual(scene.kin("readmore"), [], "and only once")

    def test_while_true_speeds_up_until_it_gets_a_break(self) -> None:
        scene = Scene("whiletrue")
        scene.run(3.0)
        self.assertGreater(scene.bug.charge, 1.2)
        scene.hit(scene.bug, 1, "fire")
        self.assertGreater(scene.bug.charge, 1.2, "fire is not a break")
        scene.hit(scene.bug, 1, "lightning")
        self.assertEqual(scene.bug.charge, 1.0)
        self.assertGreater(scene.bug.stun_until, scene.arena.now)


def scene_far() -> float:
    return foes.AUTOPLAY_REACH + 180.0


class ChapterThreeTests(unittest.TestCase):
    def test_a_file_with_no_extension_can_be_anything(self) -> None:
        outcomes = set()
        for seed in range(12):
            scene = Scene("noext")
            scene.arena.rng.seed(seed)
            scene.arena._drop_pickup = lambda monster: None
            scene.kill(scene.bug)
            if scene.arena.pickups:
                outcomes.add("hp")
            elif scene.arena.hazards:
                outcomes.add("blast")
            else:
                outcomes.add("nothing")
        self.assertEqual(outcomes, {"hp", "blast", "nothing"})

    def test_a_zip_bomb_unpacks_into_a_ring(self) -> None:
        scene = Scene("zipbomb")
        scene.kill(scene.bug)
        self.assertEqual(len(scene.arena.projectiles), foes.ZIP_RING)
        scene.run(1.0)

    def test_a_deleted_file_is_not_there_except_when_it_shoots(self) -> None:
        scene = Scene("deletedfile")
        scene.bug.next_attack = scene.arena.now + 2.0
        scene.run(0.1)
        self.assertNotIn(scene.bug, scene.arena.foes_for(scene.mage.id))
        scene.bug.next_attack = 0.0
        scene.bug.state = "aim"
        scene.bug.state_until = scene.arena.now + 10
        scene.run(0.1)
        self.assertIn(scene.bug, scene.arena.foes_for(scene.mage.id))

    def test_a_container_opens_on_its_own_schedule(self) -> None:
        scene = Scene("container")
        scene.bug.count = 0
        scene.bug.state_until = scene.arena.now + 5
        self.assertEqual(scene.hit(scene.bug, 10), 0.0)
        scene.bug.state_until = 0.0
        scene.run(0.1)
        self.assertEqual(scene.bug.count, 1)
        self.assertEqual(len(scene.kin("bot")), 1)
        self.assertGreater(scene.hit(scene.bug, 10), 0.0)

    def test_only_head_of_a_conflict_can_be_hurt_and_it_keeps_changing(self) -> None:
        scene = Scene("conflict")
        other = scene.spawn("conflict", 170, 60)
        scene.run(0.1)
        real = [m for m in (scene.bug, other) if m.text == "HEAD"]
        self.assertEqual(len(real), 1)
        first = real[0]
        fake = other if first is scene.bug else scene.bug
        self.assertEqual(scene.hit(fake, 5), 0.0)
        self.assertGreater(scene.hit(first, 5), 0.0)
        scene.run(foes.CONFLICT_SWAP)
        self.assertEqual(first.text, "main")

    def test_lag_rolls_back_to_where_it_was(self) -> None:
        scene = Scene("lag", dx=300)
        scene.run(TICK * 2)
        saved = scene.bug.origin
        self.assertEqual(scene.bug.state, "saved")
        scene.run(foes.LAG_RUN + 0.1)
        self.assertLess(math.hypot(scene.bug.x - saved[0], scene.bug.y - saved[1]), 80)

    def test_nan_breaks_a_careless_autoaim_and_not_a_careful_one(self) -> None:
        scene = Scene("nan")
        scene.run(0.8)
        careless = (
            "targets = enemies()\nbest = targets[0]\nfor e in targets:\n"
            "    if e.dist < best.dist:\n        best = e\nfireball(direction(best.x, best.y))\n"
        )
        result = scene.arena.cast(scene.mage.id, careless, 0, 0.0)
        self.assertFalse(result["ok"])
        self.assertTrue(result["error"])
        scene.mage.cast_lock = 0.0
        careful = (
            "for e in enemies():\n    if e.dist != None:\n        fireball(direction(e.x, e.y))\n"
            "    else:\n        fireball(direction(e.x, e.y))\n"
        )
        scene.run(1.0)
        self.assertTrue(scene.arena.cast(scene.mage.id, careful, 0, 0.0)["ok"])

    def test_the_dangling_link_hits_where_you_were(self) -> None:
        scene = Scene("dangling")
        scene.bug.next_attack = 0.0
        scene.run(0.1)
        beam = scene.arena.hazards[-1]
        self.assertIsNotNone(beam.x2)
        self.assertAlmostEqual(beam.delay, foes.DANGLING_FUSE)

    def test_quota_fills_the_room_with_boxes_that_stand_like_walls_and_can_be_broken(self) -> None:
        scene = Scene("quota")
        for _ in range(40):
            scene.bug.next_special = 0.0
            scene.run(0.3)
            if len(scene.arena.boxes) >= 2:
                break
        self.assertGreaterEqual(len(scene.arena.boxes), 2)
        tile = next(iter(scene.arena.boxes))
        self.assertTrue(scene.arena.dungeon.solid(*tile), "you cannot walk through a box")
        prop, _patch = scene.arena.boxes[tile]
        scene.arena.damage(target=prop, amount=1, source=scene.mage, kind="fire", hit_x=prop.x, hit_y=prop.y)
        self.assertNotIn(tile, scene.arena.boxes)
        self.assertFalse(scene.arena.dungeon.solid(*tile), "and a broken one is gone")
        scene.kill(scene.bug)
        self.assertEqual(scene.arena.boxes, {})
        self.assertNotIn("quota", scene.arena.locks)

    def test_a_shot_really_breaks_a_box_though_it_stops_shots(self) -> None:
        scene = Scene("quota", dx=-200)
        scene.bug.next_special = 1e9
        scene.bug.stun_until = 1e9
        mage = scene.mage
        tx, ty = int((mage.x + 200) // TILE), int(mage.y // TILE)
        x, y = (tx + 0.5) * TILE, (ty + 0.5) * TILE
        foes._raise_box(scene.arena, scene.bug, (tx, ty), x, y)
        self.assertIn((tx, ty), scene.arena.boxes)
        mage.y = y
        self.assertTrue(scene.arena.cast(mage.id, "fireball(0)", 0, 0.0)["ok"])
        scene.run(1.0)
        self.assertNotIn((tx, ty), scene.arena.boxes)

    def test_ours_and_theirs_merge_when_they_meet(self) -> None:
        scene = Scene("ours")
        scene.run(0.1)
        theirs = scene.kin("theirs")[0]
        scene.wake()
        total = scene.bug.hp + theirs.hp
        theirs.x, theirs.y = scene.bug.x + 20, scene.bug.y
        scene.run(0.1)
        self.assertEqual(scene.kin("theirs"), [])
        self.assertAlmostEqual(scene.bug.hp, total, delta=1)
        self.assertEqual(scene.bug.text, "merged")

    def test_two_halves_start_far_apart_and_take_their_time_to_meet(self) -> None:
        for key, other in (("ours", "theirs"), ("vim", "emacs")):
            for seed in (1, 2, 3, 4):
                stage = STAGES[stage_of(key)]
                arena = StoryArena(stage, 1, seed=seed, now=1.0, known_upto=19)
                mage = arena.add_player("Маг")
                mage.invuln_until = 1e9
                room = arena.mini_room
                arena.active_room = room
                arena.wave = arena._waves_in(room) - 1
                mage.x, mage.y = arena.dungeon.open_near(room.center[0], room.center[1] + 200, 20.0)
                arena._spawn_wave(room)
                for _ in range(int(0.8 * TICK_RATE)):
                    arena.update(arena.now + TICK)
                first = next(m for m in arena.monsters.values() if m.species.key == key)
                second = next(m for m in arena.monsters.values() if m.species.key == other)
                self.assertGreater(math.hypot(first.x - second.x, first.y - second.y), 300, f"{key} {seed}")
                if key == "ours":
                    for _ in range(int(4 * TICK_RATE)):
                        arena.update(arena.now + TICK)
                    self.assertTrue(any(m.species.key == other for m in arena.monsters.values()), "not at once")

    def test_a_hit_pushes_ours_away_from_theirs(self) -> None:
        scene = Scene("ours")
        scene.run(0.1)
        theirs = scene.kin("theirs")[0]
        scene.wake()
        apart = math.hypot(scene.bug.x - theirs.x, scene.bug.y - theirs.y)
        scene.hit(scene.bug, 5)
        self.assertGreater(math.hypot(scene.bug.x - theirs.x, scene.bug.y - theirs.y), apart)

    def test_dev_null_swallows_shots_then_opens(self) -> None:
        scene = Scene("devnull")
        scene.run(0.1)
        for _ in range(foes.DEVNULL_FEED - 1):
            self.assertEqual(scene.hit(scene.bug, 40), 0.0)
        self.assertEqual(scene.bug.state, "idle")
        self.assertEqual(scene.hit(scene.bug, 40), 0.0)
        self.assertEqual(scene.bug.state, "open")
        self.assertGreater(scene.hit(scene.bug, 40), 0.0)
        scene.run(foes.DEVNULL_OPEN + 0.2)
        self.assertEqual(scene.bug.state, "idle")
        self.assertEqual(scene.bug.count, 0)

    def test_dev_null_bends_shots_towards_itself(self) -> None:
        scene = Scene("devnull", dx=240)
        scene.run(0.1)
        mage = scene.mage
        away = math.atan2(scene.bug.y - mage.y, scene.bug.x - mage.x) + 0.6
        self.assertTrue(scene.arena.cast(mage.id, f"fireball({away})", 0, 0.0)["ok"])
        scene.bug.next_attack = 1e9
        shot = scene.arena.projectiles[-1]
        start = shot.angle
        scene.run(0.1)
        self.assertNotAlmostEqual(shot.angle, start)


class ChapterFourTests(unittest.TestCase):
    def test_the_chillers_wave_spreads_and_a_roll_gets_you_through(self) -> None:
        scene = Scene("chiller", dx=260)
        mage = scene.mage
        mage.invuln_until = 0.0
        scene.bug.next_attack = 0.0
        scene.run(0.1)
        wave = next(f for f in scene.arena.fields if f.kind == "cold")
        radius = wave.radius
        scene.run(0.3)
        self.assertGreater(wave.radius, radius)
        mage.x, mage.y = wave.x + wave.radius, wave.y
        hp = mage.hp
        mage.invuln_until = scene.arena.now + 1
        scene.run(0.1)
        self.assertEqual(mage.hp, hp, "rolling through")
        mage.invuln_until = 0.0
        mage.x, mage.y = wave.x + wave.radius, wave.y
        scene.run(0.1)
        self.assertLess(mage.hp, hp)

    def test_fire_hurts_the_chiller_and_frost_does_not(self) -> None:
        scene = Scene("chiller")
        self.assertEqual(scene.hit(scene.bug, 20, "frost"), 0.0)
        self.assertGreater(scene.hit(scene.bug, 20, "fire"), 20)

    def test_lightning_in_a_puddle_gets_everyone_standing_in_it(self) -> None:
        scene = Scene("condensate", dx=200)
        other = scene.spawn("popup", 200, 20)
        puddle = foes.add_field(scene.arena, "puddle", other.x, other.y, radius=foes.PUDDLE_RADIUS, until=scene.arena.now + 9)
        hp = other.hp
        scene.bug.x, scene.bug.y = other.x, other.y
        scene.hit(scene.bug, 1, "lightning")
        self.assertLess(other.hp, hp)
        self.assertNotIn(puddle, scene.arena.fields, "the charge is spent")

    def test_a_cable_leaves_a_wire_you_trip_on(self) -> None:
        scene = Scene("wire")
        scene.run(1.4)
        wire = next(f for f in scene.arena.fields if f.kind == "wire")
        self.assertTrue(wire.slow)

    def test_a_zombie_has_to_be_finished_off(self) -> None:
        scene = Scene("zombie")
        scene.kill(scene.bug)
        self.assertEqual(scene.bug.state, "down")
        self.assertIn(scene.bug.id, scene.arena.monsters)
        scene.run(foes.ZOMBIE_WAKE + 0.2)
        self.assertEqual(scene.bug.state, "idle", "left alone, it gets up")
        scene.kill(scene.bug)
        scene.kill(scene.bug)
        self.assertEqual(scene.kin("zombie"), [])

    def test_a_fork_bomb_doubles_only_if_nobody_touches_it(self) -> None:
        scene = Scene("forkbomb", dx=400)
        scene.bug.next_special = 0.0
        scene.bug.last_damage_at = scene.arena.now
        scene.run(0.2)
        self.assertEqual(len(scene.kin("forkbomb")), 1)
        scene.bug.last_damage_at = -100.0
        scene.run(0.1)
        self.assertEqual(len(scene.kin("forkbomb")), 2)

    def test_a_fork_bomb_does_stop_somewhere(self) -> None:
        scene = Scene("forkbomb", dx=400)
        for _ in range(60):
            for bomb in scene.kin("forkbomb"):
                bomb.next_special = 0.0
                bomb.last_damage_at = -100.0
            scene.run(0.1)
        self.assertLessEqual(len(scene.kin("forkbomb")), foes.FORK_LIMIT)

    def test_a_ups_gets_up_twice_unless_its_battery_is_flat(self) -> None:
        scene = Scene("ups")
        scene.kill(scene.bug)
        scene.kill(scene.bug)
        self.assertEqual(len(scene.kin("ups")), 1)
        scene.kill(scene.bug)
        self.assertEqual(scene.kin("ups"), [])
        scene = Scene("ups")
        scene.hit(scene.bug, 1, "emp")
        scene.kill(scene.bug)
        self.assertEqual(scene.kin("ups"), [], "EMP saw to the battery")

    def test_the_night_alert_hurries_everyone_near(self) -> None:
        scene = Scene("nightalert")
        other = scene.spawn("popup", 200, 60)
        scene.run(0.1)
        self.assertGreater(other.hurry_until, scene.arena.now)

    def test_the_surge_ends_in_a_shock(self) -> None:
        scene = Scene("surge")
        scene.bug.state = "dash"
        scene.bug.state_until = 0.0
        scene.run(TICK)
        self.assertEqual(scene.arena.hazards[-1].label, "220 В")

    def test_the_b_tree_splits_into_branches_and_leaves(self) -> None:
        scene = Scene("btree")
        scene.run(0.1)
        total = scene.arena.boss_max_hp
        self.assertGreater(total, scene.bug.max_hp)
        scene.kill(scene.bug)
        branches = scene.kin("btree_branch")
        self.assertEqual(len(branches), 2)
        self.assertEqual(scene.arena.boss_max_hp, total)
        for branch in branches:
            scene.kill(branch)
        leaves = scene.kin("btree_leaf")
        self.assertEqual(len(leaves), 4)
        scene.wake()
        self.assertGreater(50, leaves[0].max_hp, "one hit each")

    def test_off_by_one_misses_on_purpose(self) -> None:
        scene = Scene("offbyone")
        scene.bug.next_attack = 0.0
        scene.run(TICK)
        marks = [h for h in scene.arena.hazards if h.label.startswith("i")]
        self.assertEqual(len(marks), 2)
        for mark in marks:
            self.assertFalse(scene.arena._hazard_covers(mark, scene.mage), "the safest place is the aim")

    def test_reverse_comes_when_you_leave_and_leaves_when_you_come(self) -> None:
        scene = Scene("reverse", dx=500)
        far = math.hypot(scene.bug.x - scene.mage.x, scene.bug.y - scene.mage.y)
        scene.run(0.3)
        self.assertLess(math.hypot(scene.bug.x - scene.mage.x, scene.bug.y - scene.mage.y), far)
        scene.bug.x, scene.bug.y = scene.mage.x + 100, scene.mage.y
        scene.run(0.3)
        self.assertGreater(math.hypot(scene.bug.x - scene.mage.x, scene.bug.y - scene.mage.y), 100)


class ChapterFiveTests(unittest.TestCase):
    def test_a_warning_ignored_becomes_an_error_and_then_fatal(self) -> None:
        scene = Scene("warning", dx=400)
        scene.bug.spawned_at = scene.arena.now
        scene.run(0.1)
        self.assertEqual(scene.bug.text, "WARNING")
        self.assertEqual(scene.arena.projectiles, [])
        scene.run(foes.WARNING_STEP)
        self.assertEqual(scene.bug.text, "ERROR")
        scene.run(foes.WARNING_STEP)
        self.assertEqual(scene.bug.text, "FATAL")

    def test_a_traceback_is_only_open_at_its_last_call(self) -> None:
        scene = Scene("traceback")
        scene.run(0.1)
        chain = scene.kin("traceback")
        self.assertEqual(len(chain), 4)
        scene.wake()
        scene.run(0.1)
        last = next(m for m in chain if m.text == "last")
        head = scene.bug
        self.assertEqual(scene.hit(head, 5), 0.0)
        self.assertGreater(scene.hit(last, 5), 0.0)
        scene.kill(last)
        scene.run(0.1)
        new_last = next(m for m in scene.kin("traceback") if m.text == "last")
        self.assertIsNot(new_last, last)
        self.assertGreater(scene.hit(new_last, 1), 0.0)

    def test_debug_mode_only_opens_when_its_error_line_is_killed(self) -> None:
        scene = Scene("debugmode")
        scene.run(0.1)
        self.assertEqual(scene.hit(scene.bug, 10), 0.0)
        scene.bug.next_special = 0.0
        scene.run(0.1)
        scene.wake()
        lines = scene.kin("logline")
        self.assertGreaterEqual(len(lines), foes.DEBUG_LINES)
        errors = [line for line in lines if line.text == "ERROR"]
        self.assertEqual(len(errors), 1)
        innocent = next(line for line in lines if line.text != "ERROR")
        hp = scene.bug.hp
        scene.kill(innocent)
        self.assertEqual(scene.bug.hp, hp)
        scene.kill(errors[0])
        self.assertLess(scene.bug.hp, hp)
        self.assertEqual(scene.kin("logline"), [])
        self.assertGreater(scene.hit(scene.bug, 10), 0.0)

    def test_a_flaky_test_can_only_be_hit_while_green(self) -> None:
        scene = Scene("flaky")
        for _ in range(60):
            scene.run(0.1)
            if scene.bug.text == "failed":
                self.assertEqual(scene.hit(scene.bug, 1), 0.0)
                break
        for _ in range(60):
            scene.run(0.1)
            if scene.bug.text == "passed":
                self.assertGreater(scene.hit(scene.bug, 1), 0.0)
                return
        self.fail("it never passed")

    def test_your_reflection_stands_opposite_and_casts_what_you_cast(self) -> None:
        scene = Scene("reflection")
        scene.stand_still()
        scene.run(2.0)
        left, top, right, bottom = scene.arena.room_box()
        self.assertLess(math.hypot(scene.bug.x - (left + right - scene.mage.x), scene.bug.y - (top + bottom - scene.mage.y)), 80)
        scene.bug.next_attack = 0.0
        scene.arena.projectiles.clear()
        self.assertTrue(scene.arena.cast(scene.mage.id, "fireball(aim())", 0, 0.0)["ok"])
        self.assertEqual(sum(s.owner == scene.bug.id for s in scene.arena.projectiles), 1)

    def test_tab_error_punishes_changing_runes(self) -> None:
        scene = Scene("taberror")
        self.assertGreater(scene.hit(scene.bug, 40, "fire"), 0.0)
        self.assertEqual(scene.bug.text, "fire")
        second = scene.hit(scene.bug, 40, "fire")
        self.assertGreater(second, 40, "the same rune adds up")
        hp = scene.bug.hp
        self.assertEqual(scene.hit(scene.bug, 40, "frost"), 0.0)
        self.assertGreater(scene.bug.hp, hp)
        self.assertEqual(scene.bug.charge, 0.0)

    def test_a_lingering_cloud_does_not_count_as_changing_runes(self) -> None:
        scene = Scene("taberror")
        scene.hit(scene.bug, 40, "fire")
        self.assertGreater(scene.hit(scene.bug, 5, "poison"), 0.0)
        self.assertEqual(scene.bug.text, "fire")

    def test_the_princes_coins_cost_mana_and_do_not_come_to_you(self) -> None:
        scene = Scene("prince", dx=320)
        scene.bug.next_attack = 0.0
        scene.run(TICK * 2)
        coin = next(p for p in scene.arena.pickups if p.kind == foes.COIN)
        scene.bug.next_attack = 1e9
        spot = coin.x, coin.y
        scene.mage.x, scene.mage.y = coin.x - 70, coin.y
        scene.run(0.3)
        self.assertEqual((coin.x, coin.y), spot)
        mana = scene.mage.mana = 80.0
        scene.mage.x, scene.mage.y = coin.x, coin.y
        scene.run(TICK * 2)
        self.assertNotIn(coin, scene.arena.pickups)
        self.assertLess(scene.mage.mana, mana - foes.COIN_DRAIN + 2)

    def test_coins_do_not_lie_about_for_ever(self) -> None:
        scene = Scene("prince", dx=320)
        scene.bug.next_attack = 1e9
        scene.arena._add_pickup(foes.COIN, scene.mage.x + 300, scene.mage.y, scene.arena.now + 0.1)
        scene.run(0.3)
        self.assertEqual([p for p in scene.arena.pickups if p.kind == foes.COIN], [])

    def test_a_captcha_can_tell_a_spell_that_asked_enemies(self) -> None:
        scene = Scene("captcha")
        self.assertGreater(scene.hit(scene.bug, 5), 0.0)
        scene.run(0.8)
        self.assertTrue(scene.arena.cast(scene.mage.id, "e = enemies()", 0, 0.0)["ok"])
        self.assertEqual(scene.hit(scene.bug, 5), 0.0, "you are a robot")
        scene.run(2.0)
        self.assertGreater(scene.hit(scene.bug, 5), 0.0, "for a moment, anyway")

    def test_the_context_window_decides_who_gets_through(self) -> None:
        scene = Scene("context")
        scene.run(0.1)
        frame = scene.bug.memo
        scene.mage.x, scene.mage.y = frame.x, frame.y
        self.assertGreater(scene.hit(scene.bug, 5), 0.0)
        scene.mage.x = frame.x + frame.radius + 80
        self.assertEqual(scene.hit(scene.bug, 5), 0.0)
        mana = scene.mage.mana = 50.0
        scene.mage.mana_regen = 0.0
        frame.radius = foes.WINDOW_LEAST + 1
        scene.mage.x, scene.mage.y = frame.x + 500, frame.y
        scene.run(0.5)
        self.assertLess(scene.mage.mana, mana)
        self.assertGreater(frame.radius, foes.WINDOW_MOST - 20, "and it starts all over")

    def test_the_vibe_coder_heals_pgt_when_pgt_is_there(self) -> None:
        scene = Scene("vibecoder", stage=19)
        boss = scene.spawn("pgt", 260, 40)
        boss.next_attack = boss.next_special = 1e9
        boss.hp = boss.max_hp * 0.5
        hp = boss.hp
        scene.bug.next_attack = 0.0
        scene.run(TICK)
        self.assertGreater(boss.hp, hp)

    def test_a_prompt_injection_sends_your_next_cast_astray_once(self) -> None:
        scene = Scene("promptinject")
        mage = scene.mage
        mage.invuln_until = 0.0
        scene.bug.next_attack = 1e9
        scene.arena.fire_from(scene.bug, mage.x + 20, mage.y, math.pi)
        scene.run(0.2)
        self.assertTrue(scene.arena.cursed(mage, "inject"))
        scene.arena.rng.seed(5)
        scene.bug.stun_until = 1e9
        self.assertTrue(scene.arena.cast(mage.id, "fireball(aim())", 0, 0.0)["ok"])
        self.assertFalse(scene.arena.cursed(mage, "inject"))
        self.assertGreater(abs(scene.arena.projectiles[-1].angle), 0.01)
        scene.run(0.8)
        mage.mana = mage.max_mana
        scene.arena.projectiles.clear()
        self.assertTrue(scene.arena.cast(mage.id, "fireball(aim())", 0, 0.0)["ok"])
        self.assertAlmostEqual(scene.arena.projectiles[-1].angle, 0.0, places=1)


class HelpForTheBossTests(unittest.TestCase):
    def fight(self, index: int = 3) -> tuple[StoryArena, object, object]:
        stage = STAGES[index]
        arena = StoryArena(stage, 1, seed=4, now=1.0, known_upto=19)
        mage = arena.add_player("Маг")
        mage.invuln_until = 1e9
        room = next(r for r in arena.dungeon.path if r.kind == "boss")
        arena.active_room = room
        arena.wave = 0
        mage.x, mage.y = arena.dungeon.open_near(room.center[0] - 180, room.center[1] + 120, 20.0)
        arena._spawn_wave(room)
        boss = next(m for m in arena.monsters.values() if m.species.key == stage.chapter.boss)
        boss.spawned_at = 0.0
        boss.next_attack = boss.next_special = 1e9
        return arena, mage, boss

    def call_help(self, arena) -> object:
        arena.rng.random = lambda: 0.0
        arena.escort_at = arena.now
        foes.update(arena, arena.now, TICK)
        return next(m for m in arena.monsters.values() if m.escort)

    def test_a_boss_fight_expects_help_to_come_at_some_point(self) -> None:
        arena, _, _ = self.fight()
        self.assertGreater(arena.escort_at, arena.now)
        self.assertEqual(arena.escorts_left, foes.ESCORT_LIMIT)

    def test_help_comes_from_the_bosses_own_chapter(self) -> None:
        for index in (3, 7, 11, 15, 19):
            arena, _, _ = self.fight(index)
            helper = self.call_help(arena)
            self.assertIn(helper.species.key, foes._chapter_helpers(STAGES[index].chapter_index))
            self.assertTrue(helper.species.boss)

    def test_helpers_are_weaker_than_when_they_are_the_main_event(self) -> None:
        arena, _, _ = self.fight()
        helper = self.call_help(arena)
        self.assertAlmostEqual(helper.max_hp, helper.species.hp * foes.ESCORT_HP * arena.difficulty.toughness)

    def test_the_boss_bar_is_still_the_bosses(self) -> None:
        arena, _, boss = self.fight()
        maximum = arena.boss_max_hp
        self.call_help(arena)
        report = arena.snapshot()["story"]["boss"]
        self.assertEqual(report["name"], boss.name)
        self.assertEqual(report["max_hp"], maximum)
        self.assertEqual(report["hp"], round(boss.hp, 1))

    def test_help_shows_it_is_help(self) -> None:
        arena, _, _ = self.fight()
        helper = self.call_help(arena)
        entry = next(e for e in arena.snapshot()["monsters"] if e["id"] == helper.id)
        self.assertTrue(entry["escort"])

    def test_when_the_boss_falls_its_help_leaves(self) -> None:
        arena, mage, boss = self.fight()
        helper = self.call_help(arena)
        arena.update(arena.now + TICK)
        boss.invuln_until = 0.0
        arena.gates_left = []
        arena.damage(target=boss, amount=boss.hp + 10, source=mage, kind="fire", hit_x=boss.x, hit_y=boss.y)
        self.assertNotIn(helper.id, arena.monsters)
        self.assertEqual(arena.monsters, {})

    def test_pgts_help_waits_until_the_last_pgt_is_down(self) -> None:
        arena, mage, boss = self.fight(19)
        helper = self.call_help(arena)
        arena.gates_left = []
        boss.invuln_until = 0.0
        arena.damage(target=boss, amount=boss.hp + 10, source=mage, kind="fire", hit_x=boss.x, hit_y=boss.y)
        self.assertIn(helper.id, arena.monsters, "it calls itself, so it is not over yet")

    def test_only_one_helper_at_a_time_and_never_more_than_the_limit(self) -> None:
        arena, _, _ = self.fight()
        arena.rng.random = lambda: 0.0
        helpers = []
        for _ in range(8):
            arena.escort_at = arena.now
            foes.update(arena, arena.now, TICK)
            present = [m for m in arena.monsters.values() if m.escort and m.species.boss and m.generation == 0]
            self.assertLessEqual(len(present), 1)
            for monster in present:
                if monster not in helpers:
                    helpers.append(monster)
                arena.remove_monster(monster)
        self.assertEqual(len(helpers), foes.ESCORT_LIMIT)

    def test_sometimes_it_is_only_this_stages_bugs(self) -> None:
        arena, _, _ = self.fight()
        arena.rng.random = lambda: 0.99
        arena.escort_at = arena.now
        foes.update(arena, arena.now, TICK)
        keys = {m.species.key for m in arena.monsters.values()}
        self.assertLessEqual(set(STAGES[3].fresh), keys)
        self.assertFalse(any(m.escort for m in arena.monsters.values()))

    def test_nobody_comes_while_a_mage_is_fixing_the_gate(self) -> None:
        arena, _, boss = self.fight()
        arena.gate_boss = boss
        arena.escort_at = arena.now
        foes.update(arena, arena.now, TICK)
        self.assertFalse(any(m.escort for m in arena.monsters.values()))

    def test_a_mini_boss_never_opens_the_gate_that_belongs_to_the_boss(self) -> None:
        scene = Scene("eof", stage=3)
        gates = list(scene.arena.gates_left)
        self.assertTrue(gates)
        scene.bug.hp = scene.bug.max_hp * 0.2
        scene.run(0.2)
        self.assertIsNone(scene.arena.gate_boss)
        self.assertEqual(scene.arena.gates_left, gates)

    def test_every_helper_can_fight_beside_every_boss(self) -> None:
        for index in (3, 7, 11, 15, 19):
            for key in foes._chapter_helpers(STAGES[index].chapter_index):
                arena, _, _ = self.fight(index)
                arena.spawn_monster(key, *arena.dungeon.open_near(*arena.active_room.center, 30.0), escort=True)
                for _ in range(int(8 * TICK_RATE)):
                    arena.update(arena.now + TICK)
                    arena.snapshot()
                    arena.drain_events()


class NobodyHomeTests(unittest.TestCase):
    """The server has one loop for everything: a new bug must not break it in any corner."""

    def test_none_of_them_breaks_with_a_dead_or_absent_mage(self) -> None:
        for stage in STAGES:
            for key in (stage.mini, *stage.fresh):
                for nobody in ("dead", "elsewhere"):
                    with self.subTest(key=key, nobody=nobody):
                        scene = Scene(key, stage=stage.index)
                        if nobody == "dead":
                            scene.mage.dead = True
                        else:
                            scene.mage.x, scene.mage.y = scene.arena.dungeon.rooms[0].center
                        scene.run(2.0)

    def test_killing_any_of_them_at_any_moment_is_safe(self) -> None:
        for stage in STAGES:
            for key in (stage.mini, *stage.fresh):
                with self.subTest(key=key):
                    scene = Scene(key, stage=stage.index)
                    scene.run(1.5)
                    scene.wake()
                    # Past every rule: whatever it takes to die, this is it having been done.
                    for _ in range(8):
                        for monster in list(scene.arena.monsters.values()):
                            monster.invuln_until = 0.0
                            monster.hp = 0.0
                            scene.arena._kill(monster, scene.mage, "fire")
                        scene.run(0.1)
                        scene.wake()
                    self.assertEqual(scene.arena.monsters, {}, key)

    def test_what_they_leave_on_the_floor_travels_as_json(self) -> None:
        import json

        for stage in STAGES:
            for key in (stage.mini, *stage.fresh):
                with self.subTest(key=key):
                    scene = Scene(key, stage=stage.index)
                    scene.run(3.0)
                    self.assertTrue(json.dumps(scene.arena.snapshot(), allow_nan=False))

    def test_the_floor_is_cleaned_when_the_fight_is_over(self) -> None:
        scene = Scene("construction")
        scene.bug.next_attack = 0.0
        scene.run(0.1)
        self.assertTrue(scene.arena.fields)
        scene.kill(scene.bug)
        scene.run(1.0)
        scene.arena.active_room = scene.room
        foes.room_cleared(scene.arena)
        self.assertEqual(scene.arena.fields, [])


if __name__ == "__main__":
    unittest.main()
