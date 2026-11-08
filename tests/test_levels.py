"""Tests for what fills a stage: room shapes, chapter rules, things spells break,
spell workshops, residents, events, finds and relics."""

from __future__ import annotations

import json
import math
import random
import tempfile
import unittest
from pathlib import Path

from arcane.campaign import CHAPTERS, STAGES
from arcane.dungeon import PIT, SHAPES_BY_CHAPTER, TILE, build_dungeon
from arcane.game import TICK_RATE
from arcane.life import FINDS, RELICS, RESIDENTS
from arcane.party import Party
from arcane.profiles import ProfileStore
from arcane.story import StoryArena
from arcane.workshop import kind_for_stage

TICK = 1 / TICK_RATE
TOKEN = "a" * 32
ORDINARY = [stage for stage in STAGES if not stage.is_boss]


def advance(arena: StoryArena, seconds: float) -> list[dict]:
    events: list[dict] = []
    for _ in range(int(seconds * TICK_RATE)):
        arena.update(arena.now + TICK)
        events.extend(arena.drain_events())
    return events


def make(stage_index: int, mages: int = 1, seed: int = 3) -> tuple[StoryArena, list]:
    arena = StoryArena(STAGES[stage_index], mages, seed=seed, now=1.0)
    party = [arena.add_player(f"Маг {index + 1}") for index in range(mages)]
    for mage in party:
        mage.invuln_until = 0.0
    return arena, party


def safe(mage) -> None:
    mage.invuln_until = 1e9


def stand(mage, x: float, y: float) -> None:
    mage.x, mage.y = x, y


def cast(arena: StoryArena, mage, code: str, aim: float = 0.0) -> dict:
    mage.cast_ready_at = 0.0
    mage.mana = mage.max_mana
    return arena.cast(mage.id, code, 0, aim)


def bug(arena: StoryArena, x: float, y: float, key: str = "popup"):
    monster = arena.spawn_monster(key, x, y)
    monster.spawned_at = 0.0
    monster.next_attack = 1e9
    monster.next_contact = 1e9
    return monster


def fight_room(arena: StoryArena):
    return next(room for room in arena.dungeon.path if room.kind == "combat")


def side_room(arena: StoryArena, kind: str):
    return next(room for room in arena.dungeon.sides if room.kind == kind)


def inside(arena: StoryArena, room) -> tuple[float, float]:
    return arena.dungeon.open_point(room, random.Random(1), 24.0)


class ShapeTests(unittest.TestCase):
    def test_every_door_of_every_shaped_room_stays_reachable(self) -> None:
        for chapter in range(5):
            for seed in range(40):
                dungeon = build_dungeon(
                    ["start", "combat", "combat", "combat", "quest", "exit"],
                    random.Random(seed * 11 + chapter),
                    ["vault", "workshop", "secret"],
                    chapter,
                )
                first = dungeon.rooms[0]
                start = (first.x + 1, first.y + 1)
                seen = {start}
                frontier = [start]
                while frontier:
                    x, y = frontier.pop()
                    for tile in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if tile not in seen and not dungeon.solid(*tile):
                            seen.add(tile)
                            frontier.append(tile)
                for room in dungeon.rooms:
                    for door in room.doors:
                        self.assertIn(door, seen, f"chapter {chapter} seed {seed} room {room.kind}")

    def test_each_chapter_builds_its_own_rooms(self) -> None:
        for chapter, shapes in enumerate(SHAPES_BY_CHAPTER):
            found = set()
            for seed in range(30):
                dungeon = build_dungeon(["start", "combat", "exit"], random.Random(seed), (), chapter)
                found.add(dungeon.rooms[1].shape)
            self.assertTrue(found & set(shapes), chapter)

    def test_shots_fly_over_pits_and_feet_do_not(self) -> None:
        dungeon = build_dungeon(["start", "exit"], random.Random(1))
        room = dungeon.rooms[0]
        y = room.y + 5
        for x in range(room.x + 4, room.x + 8):
            dungeon.grid[y][x] = PIT
        ax, ay = (room.x + 2.5) * TILE, (y + 0.5) * TILE
        bx, by = (room.x + 10.5) * TILE, (y + 0.5) * TILE
        self.assertFalse(dungeon.path_clear(ax, ay, bx, by))
        self.assertTrue(dungeon.path_clear(ax, ay, bx, by, shot=True))

    def test_a_room_with_a_wall_for_a_middle_still_offers_a_place_to_stand(self) -> None:
        for seed in range(30):
            dungeon = build_dungeon(["start", "combat", "exit"], random.Random(seed), (), 4)
            room = dungeon.rooms[1]
            x, y = dungeon.open_near(*room.center, 20.0)
            self.assertFalse(dungeon.blocked(x, y, 20.0))
            self.assertTrue(room.holds(x, y, -1.0))

    def test_a_workshop_never_has_a_room_behind_it(self) -> None:
        for seed in range(60):
            dungeon = build_dungeon(
                ["start", "combat", "quest", "exit"],
                random.Random(seed),
                ["workshop", "secret", "trap", "trial", "vault", "cache", "rest"],
            )
            hosts = {room.parent for room in dungeon.sides}
            for room in dungeon.sides:
                if room.kind in ("workshop", "secret", "trap", "trial"):
                    self.assertNotIn(room.index, hosts)


class PropTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = make(1)
        self.terrain = self.arena.terrain
        safe(self.mage)

    def prop(self, kind: str):
        return next(p for p in self.terrain.props.values() if p.kind == kind)

    def test_spells_can_hit_furniture_but_cannot_aim_at_it(self) -> None:
        crate = self.prop("crate")
        self.assertIn(crate, self.arena.targets_for(self.mage.id))
        self.assertNotIn(crate, self.arena.foes_for(self.mage.id))
        result = cast(self.arena, self.mage, "log(len(enemies()))") if "enemies" in self.arena.known_runes else None
        if result is not None:
            self.assertEqual(result["log"], ["0"])

    def test_a_real_fireball_breaks_a_crate(self) -> None:
        crate = self.prop("crate")
        stand(self.mage, *self.arena.dungeon.open_near(crate.x - 120, crate.y, 20.0))
        self.assertTrue(cast(self.arena, self.mage, "fireball(direction(%f, %f))" % (crate.x, crate.y))["ok"])
        events = advance(self.arena, 1.0)
        self.assertNotIn(crate.id, self.terrain.props)
        self.assertIn(crate.id, self.terrain.snapshot()["gone"])
        self.assertIn("prop_break", [event["e"] for event in events])

    def test_a_battery_hurts_the_bugs_around_it_more_than_a_mage(self) -> None:
        battery = self.prop("battery")
        monster = bug(self.arena, battery.x + 60, battery.y)
        hp = monster.hp
        self.mage.invuln_until = 0.0
        stand(self.mage, battery.x - 60, battery.y)
        mage_hp = self.mage.hp
        self.terrain.prop_hit(battery, self.mage, "fire")
        self.assertLess(monster.hp, hp * 0.5 if monster.id in self.arena.monsters else 1)
        self.assertGreater(self.mage.hp, mage_hp - 30)
        self.assertLess(self.mage.hp, mage_hp)

    def test_batteries_set_each_other_off(self) -> None:
        first = self.prop("battery")
        second = self.terrain.add_prop("battery", first.x + 100, first.y, 20.0)
        self.terrain.prop_hit(first, self.mage, "fire")
        self.assertNotIn(second.id, self.terrain.props)
        events = advance(self.arena, 0.5)
        self.assertIn("prop_blast", [event["e"] for event in events])


class SurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = make(4)
        self.terrain = self.arena.terrain
        safe(self.mage)
        self.puddle = next(s for s in self.terrain.surfaces if s.kind == "puddle")
        self.cable = next(s for s in self.terrain.surfaces if s.kind == "cable")

    def shoot(self, kind: str, x: float, y: float) -> None:
        self.arena.cast  # keep the helper honest: shots are real projectiles below
        from arcane.game import Projectile

        self.arena.projectiles.append(
            Projectile(9999, self.mage.id, kind, x, y, 0.0, 1.0, 1.0, 4.0, 1.0, "#ffffff")
        )

    def test_frost_freezes_water_and_ice_slows_the_bugs_on_it(self) -> None:
        self.shoot("frost", self.puddle.x, self.puddle.y)
        advance(self.arena, 0.1)
        self.assertEqual(self.puddle.state, "ice")
        monster = bug(self.arena, self.puddle.x, self.puddle.y)
        advance(self.arena, 0.2)
        self.assertGreater(monster.slow_until, self.arena.now)

    def test_fire_melts_the_ice(self) -> None:
        self.shoot("frost", self.puddle.x, self.puddle.y)
        advance(self.arena, 0.05)
        self.arena.projectiles.clear()
        self.shoot("fire", self.puddle.x, self.puddle.y)
        advance(self.arena, 0.05)
        self.assertEqual(self.puddle.state, "")

    def test_lightning_in_water_strikes_everyone_standing_in_it(self) -> None:
        monster = bug(self.arena, self.puddle.x + 20, self.puddle.y)
        far = bug(self.arena, self.puddle.x + 400, self.puddle.y)
        hp, far_hp = monster.hp, far.hp
        self.terrain.on_damage("chain", self.puddle.x, self.puddle.y, self.mage)
        self.assertLess(monster.hp, hp)
        self.assertEqual(far.hp, far_hp)

    def test_a_cable_burns_the_bugs_on_it_and_stays_burnt(self) -> None:
        self.shoot("fire", self.cable.x, self.cable.y)
        advance(self.arena, 0.05)
        self.assertEqual(self.cable.state, "burn")
        self.arena.projectiles.clear()
        monster = bug(self.arena, self.cable.x, self.cable.y)
        monster.species = monster.species
        hp = monster.hp
        advance(self.arena, 1.1)
        self.assertLess(monster.hp, hp)
        advance(self.arena, 5)
        self.assertEqual(self.cable.state, "burnt")


class ChapterRuleTests(unittest.TestCase):
    def test_hyperlinks_carry_a_mage_across_and_rest_after(self) -> None:
        arena, (mage,) = make(0)
        safe(mage)
        x1, y1, x2, y2 = arena.terrain.links[0]
        stand(mage, x1, y1)
        events = advance(arena, 0.1)
        self.assertEqual((mage.x, mage.y), (x2, y2))
        self.assertIn("link_jump", [event["e"] for event in events])
        advance(arena, 0.1)
        self.assertEqual((mage.x, mage.y), (x2, y2), "landing on the far end must not bounce back")

    def test_a_half_built_page_falls_in(self) -> None:
        arena, (mage,) = make(0)
        build = arena.terrain.builds[0]
        safe(mage)
        stand(mage, build["x"] + build["w"] / 2, build["y"] + build["h"] / 2)
        build["at"] = arena.now
        advance(arena, 0.1)
        self.assertTrue(arena.hazards)
        mage.invuln_until = 0.0
        hp = mage.hp
        advance(arena, 1.6)
        self.assertLess(mage.hp, hp)

    def test_the_feed_drags_everyone_along(self) -> None:
        arena, (mage,) = make(4)
        safe(mage)
        x, y, w, h, vx, vy = arena.terrain.belts[0]
        cx, cy = arena.dungeon.open_near(x + w / 2, y + h / 2, 20.0)
        stand(mage, cx, cy)
        monster = bug(arena, cx, cy + 10 if vy == 0 else cy)
        monster.stun_until = 1e9
        before = (mage.x, mage.y, monster.x, monster.y)
        advance(arena, 0.3)
        self.assertNotEqual((mage.x, mage.y), before[:2])
        self.assertNotEqual((monster.x, monster.y), before[2:])

    def test_wind_carries_the_shots(self) -> None:
        from arcane.game import Projectile

        arena, (mage,) = make(8)
        safe(mage)
        arena.terrain.gust_at = arena.now
        advance(arena, 0.1)
        self.assertIsNotNone(arena.terrain.gust)
        x, y = arena.dungeon.open_near(*arena.dungeon.rooms[0].center, 30.0)
        shot = Projectile(9999, mage.id, "fire", x, y, 0.0, 0.0, 1.0, 4.0, 5.0, "#ffffff")
        arena.projectiles.append(shot)
        advance(arena, 0.3)
        self.assertNotEqual((shot.x, shot.y), (x, y))

    def test_hot_aisles_burn_and_cold_ones_restore_mana(self) -> None:
        for seed in range(40):
            arena, (mage,) = make(12, seed=seed)
            kinds = {aisle[4] for aisle in arena.terrain.aisles}
            if kinds == {"hot", "cold"}:
                break
        else:
            self.fail("no racks in 40 seeds")
        hot = next(a for a in arena.terrain.aisles if a[4] == "hot")
        cold = next(a for a in arena.terrain.aisles if a[4] == "cold")
        stand(mage, *arena.dungeon.open_near(hot[0] + hot[2] / 2, hot[1] + hot[3] / 2, 18.0))
        if not (hot[0] <= mage.x <= hot[0] + hot[2] and hot[1] <= mage.y <= hot[1] + hot[3]):
            self.skipTest("the hot aisle has no room to stand here")
        arena.active_room = fight_room(arena)
        hp = mage.hp
        advance(arena, 1.2)
        self.assertLess(mage.hp, hp)
        stand(mage, *arena.dungeon.open_near(cold[0] + cold[2] / 2, cold[1] + cold[3] / 2, 18.0))
        mage.mana = 1.0
        advance(arena, 1.2)
        self.assertGreater(mage.mana, 1.0)

    def test_pgt_refactors_the_room_mid_fight_and_gives_it_back(self) -> None:
        arena, (mage,) = make(16)
        safe(mage)
        room = fight_room(arena)
        stand(mage, *arena.dungeon.open_near(*room.center, 20.0))
        advance(arena, 1.5)
        self.assertIs(arena.active_room, room)
        arena.terrain.refactor_at = arena.now
        advance(arena, 2.0)
        self.assertTrue(arena.locks.get("refactor"))
        self.assertFalse(arena.dungeon.blocked(mage.x, mage.y, mage.radius))
        arena._clear_room(room)
        for monster in list(arena.monsters.values()):
            arena.remove_monster(monster)
        advance(arena, 0.1)
        self.assertNotIn("refactor", arena.locks)

    def test_rule_is_announced_once_a_chapter(self) -> None:
        for index, chapter in enumerate(CHAPTERS):
            first = next(s for s in ORDINARY if s.chapter_index == index and s.number == 1)
            later = next(s for s in ORDINARY if s.chapter_index == index and s.number == 2)
            self.assertTrue(StoryArena(first, 1, seed=1).terrain.describe()["intro"])
            self.assertFalse(StoryArena(later, 1, seed=1).terrain.describe()["intro"])


class WorkshopTests(unittest.TestCase):
    def at_bench(self, stage_index: int) -> tuple[StoryArena, object, object]:
        arena, (mage,) = make(stage_index)
        safe(mage)
        room = arena.workshop.room
        arena.revealed.add(room.index)
        ux, uy = arena.quest._door_side(room)
        cx, cy = room.center
        stand(mage, *arena.dungeon.open_near(cx + ux * 3 * TILE, cy + uy * 2.5 * TILE, 20.0))
        return arena, mage, arena.workshop

    def test_each_part_of_the_campaign_gets_a_problem_it_can_solve(self) -> None:
        self.assertEqual(
            {kind_for_stage(stage.index) for stage in ORDINARY},
            {"knock", "lamp", "bridge", "targets"},
        )

    def test_every_ordinary_stage_has_one(self) -> None:
        for stage in ORDINARY:
            arena = StoryArena(stage, 1, seed=2)
            self.assertIsNotNone(arena.workshop, stage.title)
            self.assertTrue(arena.world_config()["signs"])

    def test_the_lock_is_really_shut(self) -> None:
        arena, mage, shop = self.at_bench(0)
        self.assertTrue(arena.locks.get("workshop"))
        x, y = arena.quest._far_end(shop.room)
        self.assertFalse(arena.dungeon.path_clear(mage.x, mage.y, x, y, 20.0))

    def test_a_workshop_rune_works_only_inside(self) -> None:
        arena, mage, shop = self.at_bench(0)
        stand(mage, *arena.dungeon.rooms[0].center)
        result = cast(arena, mage, "open_door(me().hp)")
        self.assertFalse(result["ok"])
        self.assertIn("мастерской", result["error"])

    def test_naming_your_own_health_opens_the_door(self) -> None:
        arena, mage, shop = self.at_bench(0)
        self.assertTrue(cast(arena, mage, "open_door(me().hp)")["ok"])
        self.assertTrue(shop.opened)
        self.assertNotIn("workshop", arena.locks)

    def test_a_wrong_number_shocks(self) -> None:
        arena, mage, shop = self.at_bench(0)
        mage.invuln_until = 0.0
        hp = mage.hp
        cast(arena, mage, "open_door(1)")
        self.assertFalse(shop.opened)
        self.assertLess(mage.hp, hp)

    def test_a_lamp_opens_on_green_only(self) -> None:
        arena, mage, shop = self.at_bench(4)
        code = 'if lamp() == "green":\n    open_door()\n'
        shop.lamp.on = False
        shop.flip_at = 1e9
        self.assertTrue(cast(arena, mage, code)["ok"])
        self.assertFalse(shop.opened)
        shop.lamp.on = True
        cast(arena, mage, code)
        self.assertTrue(shop.opened)

    def test_opening_on_red_shocks(self) -> None:
        arena, mage, shop = self.at_bench(4)
        shop.lamp.on = False
        shop.flip_at = 1e9
        mage.invuln_until = 0.0
        hp = mage.hp
        cast(arena, mage, "open_door()")
        self.assertLess(mage.hp, hp)
        self.assertFalse(shop.opened)

    def test_the_lamp_really_blinks(self) -> None:
        arena, mage, shop = self.at_bench(4)
        seen = set()
        for _ in range(8):
            advance(arena, 0.6)
            seen.add(shop.lamp.on)
        self.assertEqual(seen, {True, False})

    def test_half_a_bridge_is_no_bridge(self) -> None:
        arena, mage, shop = self.at_bench(8)
        self.assertTrue(cast(arena, mage, "bridge(0)\nbridge(1)")["ok"])
        self.assertFalse(shop.opened)
        advance(arena, 0.2)
        self.assertTrue(cast(arena, mage, "bridge(2)")["ok"])
        self.assertFalse(shop.opened, "sections from another cast do not hold")

    def test_a_loop_lays_the_whole_bridge_and_makes_it_walkable(self) -> None:
        arena, mage, shop = self.at_bench(8)
        x, y = arena.quest._far_end(shop.room)
        self.assertFalse(arena.dungeon.path_clear(mage.x, mage.y, x, y, 20.0))
        result = cast(arena, mage, f"for i in range({shop.count}):\n    bridge(i)\n")
        self.assertTrue(result["ok"], result)
        self.assertTrue(shop.opened)
        events = arena.drain_events()
        self.assertIn("tiles", [event["e"] for event in events])
        sx, sy, sw, sh = shop.segments[0]
        self.assertFalse(arena.dungeon.solid(sx, sy))
        self.assertEqual(arena.world_config()["tiles"][sy][sx], ".")

    def test_a_section_off_the_end_is_an_error(self) -> None:
        arena, mage, shop = self.at_bench(8)
        result = cast(arena, mage, f"bridge({shop.count})")
        self.assertFalse(result["ok"])

    def test_four_targets_fall_to_one_loop_but_not_to_slow_hands(self) -> None:
        arena, mage, shop = self.at_bench(12)
        terrain = arena.terrain
        # One at a time, too slowly:
        for target in shop.targets:
            terrain.prop_hit(target, mage, "fire")
            advance(arena, 1.0)
        self.assertFalse(shop.opened)
        for target in list(shop.targets):
            terrain.prop_hit(target, mage, "fire")
        self.assertTrue(shop.opened)

    def test_targets_are_visible_to_code_but_are_not_enemies(self) -> None:
        arena, mage, shop = self.at_bench(12)
        result = cast(arena, mage, "log(len(targets()))\nlog(len(enemies()))")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["log"], ["4", "0"])

    def test_the_chest_behind_the_lock_offers_finds(self) -> None:
        arena, mage, shop = self.at_bench(0)
        cast(arena, mage, "open_door(me().hp)")
        stand(mage, shop.chest.x, shop.chest.y + 40)
        self.assertTrue(arena.interact(mage.id)["ok"])
        self.assertTrue(shop.chest.on)
        self.assertEqual(len([t for t in arena.quest.things.values() if t.kind == "find" and not t.gone]), 3)

    def test_the_editor_only_offers_what_this_room_understands(self) -> None:
        config = StoryArena(STAGES[8], 1, seed=1).world_config()
        self.assertIn("bridge", config["runes"])
        self.assertNotIn("lamp", config["runes"])
        self.assertNotIn("bridge", StoryArena(STAGES[3], 1, seed=1).world_config()["runes"])


class ResidentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = make(0)
        safe(self.mage)
        self.life = self.arena.life

    def meet(self, key: str):
        room = self.arena.dungeon.rooms[0]
        self.life._add_resident(key, room)
        thing = self.life.residents[-1]
        stand(self.mage, thing.x, thing.y + 60)
        return thing

    def test_there_is_someone_to_meet_on_every_stage(self) -> None:
        for stage in ORDINARY:
            arena = StoryArena(stage, 1, seed=4)
            self.assertGreaterEqual(len(arena.life.residents), 2, stage.title)
            self.assertEqual(arena.dungeon.room_at(arena.life.residents[0].x, arena.life.residents[0].y).kind, "start")

    def test_all_kinds_of_resident_turn_up_over_the_campaign(self) -> None:
        met = set()
        for stage in ORDINARY:
            met |= {t.data["resident"] for t in StoryArena(stage, 1, seed=4).life.residents}
        self.assertEqual(met, set(RESIDENTS))

    def test_they_talk_when_someone_is_near(self) -> None:
        thing = self.meet("fridge")
        advance(self.arena, 0.1)
        self.assertTrue(thing.view()["say"])
        stand(self.mage, thing.x + 2000, thing.y)
        advance(self.arena, 0.1)
        self.assertNotIn("say", thing.view())

    def test_the_cash_machine_takes_tokens_and_sometimes_pays(self) -> None:
        thing = self.meet("atm")
        self.arena.interact(self.mage.id)
        self.assertEqual(self.arena.essence, 0, "nothing to take yet")
        self.arena.essence = 1000
        for _ in range(5):
            self.arena.interact(self.mage.id)
        self.assertTrue(thing.on)
        self.assertNotEqual(self.arena.essence, 1000)

    def test_the_fridge_heals_once(self) -> None:
        thing = self.meet("fridge")
        self.mage.hp = 10.0
        self.arena.interact(self.mage.id)
        self.assertGreater(self.mage.hp, 10.0)
        self.assertTrue(thing.on)

    def test_the_paperclip_shows_a_room_but_never_the_secret_one(self) -> None:
        self.meet("clip")
        before = set(self.arena.revealed)
        self.arena.interact(self.mage.id)
        fresh = self.arena.revealed - before
        self.assertEqual(len(fresh), 1)
        self.assertNotIn(self.life.secret_room.index, fresh)

    def test_the_vendor_sells_for_tokens_only(self) -> None:
        thing = self.meet("vendor")
        speed = self.mage.speed, self.mage.max_hp, self.mage.max_mana, self.mage.mana_regen
        self.arena.interact(self.mage.id)
        self.assertEqual(self.life.taken, [])
        self.arena.essence = 500
        self.arena.interact(self.mage.id)
        self.assertEqual(len(self.life.taken), 1)
        self.assertLess(self.arena.essence, 500)
        self.assertIsNotNone(speed)


class EventTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = make(4)
        safe(self.mage)
        self.life = self.arena.life

    def start(self, kind: str) -> list[dict]:
        original = self.life.rng.choice
        self.life.rng.choice = lambda seq: kind if kind in seq else original(seq)
        self.life._start_event(self.arena.now)
        del self.life.rng.choice
        return self.arena.drain_events()

    def test_nothing_happens_at_the_very_start(self) -> None:
        self.assertGreater(self.life.next_event, self.arena.now + 30)

    def test_something_does_happen_eventually(self) -> None:
        self.life.next_event = self.arena.now
        events = advance(self.arena, 0.1)
        self.assertIn("event_start", [event["e"] for event in events])

    def test_a_spam_storm_brings_bugs(self) -> None:
        self.start("storm")
        advance(self.arena, 4)
        self.assertTrue(self.arena.monsters)
        self.assertEqual(self.life.snapshot()["event"]["kind"], "storm")

    def test_events_end_on_their_own(self) -> None:
        self.start("blackout")
        self.assertEqual(self.arena.snapshot()["life"]["event"]["kind"], "blackout")
        events = advance(self.arena, 14)
        self.assertIn("event_end", [event["e"] for event in events])
        self.assertIsNone(self.life.event)

    def test_a_dns_failure_is_reported(self) -> None:
        self.start("dns")
        self.assertEqual(self.life.snapshot()["event"]["kind"], "dns")

    def test_a_data_leak_is_marked_and_pays_whoever_gets_there(self) -> None:
        self.start("leak")
        leak = self.life.leak
        self.assertIn([round(leak.x, 1), round(leak.y, 1)], self.arena.snapshot()["quest"]["marks"])
        stand(self.mage, leak.x, leak.y)
        advance(self.arena, 0.1)
        self.assertTrue(leak.gone)
        self.assertGreater(self.arena.essence, 0)
        self.assertTrue(any(t.kind == "find" and not t.gone for t in self.arena.quest.things.values()))

    def test_a_missed_leak_goes_away(self) -> None:
        self.start("leak")
        leak = self.life.leak
        advance(self.arena, 23)
        self.assertTrue(leak.gone)

    def test_no_leak_while_the_doors_are_shut(self) -> None:
        self.arena.active_room = fight_room(self.arena)
        for _ in range(30):
            self.life.event = None
            self.life.patched = True
            self.life._start_event(self.arena.now)
            if self.life.event:
                self.assertNotEqual(self.life.event["kind"], "leak")
        self.arena.drain_events()

    def test_a_patch_gives_and_takes(self) -> None:
        regen, hp_regen, lock = self.mage.mana_regen, self.mage.hp_regen, self.mage.cast_lock
        self.life._apply_patch()
        changed_mage = (self.mage.mana_regen, self.mage.hp_regen, self.mage.cast_lock) != (regen, hp_regen, lock)
        changed_world = (self.arena.monster_pace, self.arena.monster_bite, self.arena.wave_extra) != (1.0, 1.0, 1.0)
        self.assertTrue(changed_mage)
        self.assertTrue(changed_world)

    def test_faster_bugs_really_are_faster(self) -> None:
        self.arena.monster_pace = 2.0
        monster = bug(self.arena, *self.arena.dungeon.open_near(*self.arena.dungeon.rooms[0].center, 20.0))
        from arcane.monsters import _speed

        self.assertEqual(_speed(monster, self.arena), monster.species.speed * 2.0)


class FindTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = make(4)
        safe(self.mage)
        self.life = self.arena.life
        room = self.arena.dungeon.rooms[0]
        self.life.offer_finds(room, room.center)
        self.offer = self.life.offered[-1]

    def test_three_things_are_offered(self) -> None:
        self.assertEqual(len(self.offer), 3)
        self.assertEqual(len({thing.data["find"] for thing in self.offer}), 3)

    def test_taking_one_makes_the_others_crumble(self) -> None:
        chosen = self.offer[0]
        stand(self.mage, chosen.x, chosen.y + 30)
        self.assertTrue(self.arena.interact(self.mage.id)["ok"])
        self.assertTrue(all(thing.gone for thing in self.offer))
        self.assertEqual(self.life.taken, [chosen.data["find"]])

    def test_finds_stay_visible_on_the_card(self) -> None:
        self.life.take_find(self.offer[1])
        self.assertEqual(len(self.life.snapshot()["finds"]), 1)

    def test_every_find_actually_changes_a_mage(self) -> None:
        for find in FINDS:
            arena, (mage,) = make(4)
            before = (
                mage.speed, mage.cast_lock, mage.max_hp, mage.max_mana, mage.mana_regen,
                mage.perks.armor, mage.perks.crit, mage.perks.power, mage.perks.kill_mana, mage.perks.pickups,
            )
            find.apply(mage)
            after = (
                mage.speed, mage.cast_lock, mage.max_hp, mage.max_mana, mage.mana_regen,
                mage.perks.armor, mage.perks.crit, mage.perks.power, mage.perks.kill_mana, mage.perks.pickups,
            )
            self.assertNotEqual(before, after, find.key)

    def test_clearing_rooms_sometimes_offers_more_but_not_endlessly(self) -> None:
        arena, _ = make(4)
        room = fight_room(arena)
        for _ in range(30):
            arena.life.room_cleared(room)
        self.assertLessEqual(arena.life.finds_given, 2)


class SecretTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = make(2)
        safe(self.mage)
        self.life = self.arena.life
        self.room = self.life.secret_room
        self.crack = next(p for p in self.arena.terrain.props.values() if p.kind == "crack")

    def test_the_client_is_not_told_about_it(self) -> None:
        tiles = self.arena.world_config()["tiles"]
        for x, y, w, h in self.life.secret_hidden:
            for row in range(y, y + h):
                self.assertTrue(all(cell == "#" for cell in tiles[row][x : x + w]))
        doors = {tuple(door) for door in self.arena.snapshot()["story"]["doors"]}
        self.assertFalse(doors & set(self.life.secret_gate))

    def test_a_shut_fight_does_not_give_it_away(self) -> None:
        host = self.arena.dungeon.rooms[self.room.parent]
        self.arena.lock("fight", host.doors)
        doors = {tuple(door) for door in self.arena.snapshot()["story"]["doors"]}
        self.assertFalse(doors & set(self.life.secret_gate))

    def test_nobody_walks_in_before_the_wall_breaks(self) -> None:
        gate = self.life.secret_gate[0]
        self.assertTrue(self.arena.dungeon.solid(*gate))

    def test_a_spell_opens_the_crack(self) -> None:
        self.arena.terrain.prop_hit(self.crack, self.mage, "fire")
        events = self.arena.drain_events()
        kinds = [event["e"] for event in events]
        self.assertIn("tiles", kinds)
        self.assertIn(self.room.index, self.arena.revealed)
        self.assertFalse(self.arena.dungeon.solid(*self.life.secret_gate[0]))
        x, y, *_ = next(e for e in events if e["e"] == "tiles")["rects"][0]
        self.assertEqual(self.arena.world_config()["tiles"][y][x], ".")

    def test_the_relic_pays_and_is_remembered(self) -> None:
        self.arena.terrain.prop_hit(self.crack, self.mage, "fire")
        relic = next(t for t in self.arena.quest.things.values() if t.kind == "relic")
        stand(self.mage, relic.x, relic.y + 40)
        self.assertTrue(self.arena.interact(self.mage.id)["ok"])
        self.assertTrue(relic.gone)
        self.assertGreater(self.arena.essence, 0)
        self.assertEqual(self.life.take_relics(), [relic.data["relic"]])
        self.assertEqual(self.life.take_relics(), [])

    def test_there_is_one_relic_for_each_ordinary_stage(self) -> None:
        self.assertEqual(len(RELICS), len(ORDINARY))
        keys = set()
        for stage in ORDINARY:
            arena = StoryArena(stage, 1, seed=6)
            relic = next(t for t in arena.quest.things.values() if t.kind == "relic")
            keys.add(relic.data["relic"])
        self.assertEqual(len(keys), len(ORDINARY))


class ArchiveTests(unittest.TestCase):
    def test_a_relic_stays_in_the_archive_of_everyone_at_the_table(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profiles.json"
            store = ProfileStore(path)
            party = Party("ABCD", store)
            seat, error = party.join(TOKEN, "Маг")
            self.assertIsNone(error)
            party.start_stage(1.0)
            world = party.world
            world.terrain.prop_hit(
                next(p for p in world.terrain.props.values() if p.kind == "crack"), None, "fire"
            )
            relic = next(t for t in world.quest.things.values() if t.kind == "relic")
            world.life.take_relic(relic)
            party.tick(1.05)
            key = relic.data["relic"]
            self.assertIn(key, store.get(TOKEN).relics)
            self.assertIn(key, party.describe(TOKEN)["relics"])
            store.save()
            self.assertIn(key, ProfileStore(path).get(TOKEN).relics)


class LinkPlacementTests(unittest.TestCase):
    def test_a_pad_never_closes_the_only_way_through_a_room(self) -> None:
        for seed in range(50):
            for stage in (STAGES[0], STAGES[1], STAGES[2]):
                arena = StoryArena(stage, 1, seed=seed)
                terrain = arena.terrain
                grid = arena.dungeon.grid
                for room in arena.dungeon.path:
                    doors = set(room.doors)
                    if not doors:
                        continue
                    start = next(iter(doors))
                    seen = {start}
                    frontier = [start]
                    while frontier:
                        x, y = frontier.pop()
                        for tile in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                            if tile in seen or tile in terrain.pad_tiles:
                                continue
                            inside = room.x <= tile[0] < room.x + room.w and room.y <= tile[1] < room.y + room.h
                            if tile in doors or (inside and grid[tile[1]][tile[0]] == "."):
                                seen.add(tile)
                                frontier.append(tile)
                    self.assertTrue(doors <= seen, f"seed {seed} room {room.index}")


class WireTests(unittest.TestCase):
    def test_everything_travels_as_plain_json(self) -> None:
        for stage in STAGES:
            arena = StoryArena(stage, 2, seed=5, now=1.0)
            arena.add_player("А")
            arena.add_player("Б")
            advance(arena, 0.3)
            state = json.loads(json.dumps(arena.snapshot()))
            config = json.loads(json.dumps(arena.world_config()))
            self.assertIn("players", state)
            self.assertIn("tiles", config)

    def test_bosses_stay_bare_arenas(self) -> None:
        for stage in STAGES:
            if stage.is_boss:
                arena = StoryArena(stage, 1, seed=1)
                self.assertIsNone(arena.terrain)
                self.assertIsNone(arena.life)
                self.assertIsNone(arena.workshop)

    def test_a_plain_arena_has_none_of_it(self) -> None:
        arena = StoryArena(STAGES[4], 1, seed=1, plain=True)
        self.assertIsNone(arena.terrain)
        self.assertNotIn("workshop", [room.kind for room in arena.dungeon.rooms])


if __name__ == "__main__":
    unittest.main()
