"""Tests for arena geometry, movement and snapshots."""

from __future__ import annotations

import math
import unittest
from unittest import mock

from arcane.game import (
    ARENA_H,
    ARENA_W,
    BORDER,
    BOT_SPELLS,
    MANA_REGEN,
    MAX_HP,
    MOVE_SPEED,
    PLAYER_RADIUS,
    ROLL_COOLDOWN,
    ROLL_DISTANCE,
    ROLL_INVULN,
    TICK_RATE,
    Arena,
)


class ArenaSetupTests(unittest.TestCase):
    def test_spawns_are_inside_the_arena_and_clear_of_obstacles(self) -> None:
        arena = Arena(bots=0)
        config = arena.world_config()
        self.assertEqual(len(config["spawns"]), 6)
        for spawn in config["spawns"]:
            self.assertTrue(
                arena.can_stand(spawn["x"], spawn["y"]),
                f"spawn {spawn} is blocked",
            )
            distances = [
                math.hypot(spawn["x"] - other["x"], spawn["y"] - other["y"])
                for other in config["spawns"]
                if other is not spawn
            ]
            self.assertGreater(min(distances), 2 * PLAYER_RADIUS + 20)

    def test_duplicate_names_get_a_suffix(self) -> None:
        arena = Arena(bots=0)
        first = arena.add_player("Мерлин")
        second = arena.add_player("Мерлин")
        self.assertEqual(first.name, "Мерлин")
        self.assertEqual(second.name, "Мерлин 2")

    def test_online_counts_include_bots(self) -> None:
        arena = Arena(bots=2)
        arena.add_player("Живой")
        self.assertEqual(arena.online_counts(), {"humans": 1, "bots": 2, "online": 3})

    def test_snapshot_has_network_fields(self) -> None:
        arena = Arena(bots=0)
        player = arena.add_player("Снапшот")
        snapshot = arena.snapshot()
        self.assertEqual(snapshot["t"], "state")
        self.assertEqual(snapshot["stats"]["online"], 1)
        entry = snapshot["players"][0]
        for field in (
            "id",
            "name",
            "x",
            "y",
            "aim",
            "hp",
            "mana",
            "shield",
            "score",
            "deaths",
            "color",
            "dead",
            "respawn_in",
            "bot",
            "slow",
            "stun",
            "invuln",
            "roll_ready_in",
        ):
            self.assertIn(field, entry)
        self.assertEqual(entry["id"], player.id)
        self.assertIn("meteors", snapshot)
        self.assertIn("clouds", snapshot)

    def test_mana_regenerates_at_boosted_rate(self) -> None:
        arena = Arena(bots=0)
        player = arena.add_player("Мана")
        player.mana = 0.0
        for _ in range(TICK_RATE):
            arena.update(arena.now + 1 / TICK_RATE)
        self.assertAlmostEqual(MANA_REGEN, 11.25)
        self.assertAlmostEqual(player.mana, MANA_REGEN, places=3)

    def test_snapshot_includes_emp_state(self) -> None:
        arena = Arena(bots=0)
        player = arena.add_player("Э.М.П.")
        arena.place_emp(player, player.x + 40, player.y)
        snapshot = arena.snapshot()
        self.assertEqual(len(snapshot["emps"]), 1)
        emp = snapshot["emps"][0]
        for field in (
            "id",
            "x",
            "y",
            "radius",
            "ttl",
            "pull_ttl",
            "delay",
            "color",
        ):
            self.assertIn(field, emp)

    def test_snapshot_includes_meteor_and_cloud_state(self) -> None:
        arena = Arena(bots=0)
        player = arena.add_player("Погода")
        arena.place_meteor(player, player.x + 40, player.y, 120.0)
        arena.place_poison_cloud(player, player.x + 80, player.y, 110.0)
        snapshot = arena.snapshot()
        self.assertEqual(len(snapshot["meteors"]), 1)
        self.assertEqual(len(snapshot["clouds"]), 1)
        for field in (
            "id",
            "x",
            "y",
            "radius",
            "ttl",
            "delay",
            "role",
            "variant",
            "color",
        ):
            self.assertIn(field, snapshot["meteors"][0])
        for field in ("id", "x", "y", "radius", "ttl", "color"):
            self.assertIn(field, snapshot["clouds"][0])

    def test_world_config_contains_roll_and_new_spells(self) -> None:
        arena = Arena(bots=0)
        config = arena.world_config()
        self.assertEqual(config["roll"]["distance"], ROLL_DISTANCE)
        self.assertEqual(config["roll"]["cooldown"], ROLL_COOLDOWN)
        self.assertEqual(config["roll"]["invuln"], ROLL_INVULN)
        for spell in (
            "chain_lightning",
            "lightning_strike",
            "meteor",
            "siphon",
            "poison_cloud",
        ):
            self.assertIn(spell, config["spell_costs"])


class RollTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena = Arena(bots=0)
        self.player = self.arena.add_player("Прыгун")
        self.player.invuln_until = 0.0
        self.player.x, self.player.y = 700.0, 600.0

    def test_roll_moves_with_input_and_starts_cooldown(self) -> None:
        self.arena.set_input(
            self.player.id, up=False, down=False, left=False, right=True
        )
        result = self.arena.roll(self.player.id)
        self.assertTrue(result["ok"], result)
        self.assertAlmostEqual(self.player.x, 700.0 + ROLL_DISTANCE, places=3)
        self.assertAlmostEqual(self.player.y, 600.0, places=3)
        self.assertAlmostEqual(
            self.player.roll_ready_at, ROLL_COOLDOWN, places=3
        )
        self.assertAlmostEqual(self.player.invuln_until, ROLL_INVULN, places=3)
        events = [event for event in self.arena.events if event["e"] == "roll"]
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0]["x2"], 700.0 + ROLL_DISTANCE, places=1)

    def test_roll_uses_aim_when_standing_still(self) -> None:
        self.player.aim = math.pi / 2
        result = self.arena.roll(self.player.id)
        self.assertTrue(result["ok"], result)
        self.assertAlmostEqual(self.player.x, 700.0, places=3)
        self.assertAlmostEqual(self.player.y, 600.0 + ROLL_DISTANCE, places=3)

    def test_roll_respects_cooldown_until_update(self) -> None:
        self.assertTrue(self.arena.roll(self.player.id)["ok"])
        second = self.arena.roll(self.player.id)
        self.assertFalse(second["ok"])
        self.assertGreater(second["cooldown"], 0.0)
        self.arena.update(self.arena.now + ROLL_COOLDOWN + 0.05)
        self.assertTrue(self.arena.roll(self.player.id)["ok"])

    def test_roll_is_blocked_by_the_altar(self) -> None:
        self.player.x, self.player.y = 950.0, 449.0
        self.player.aim = math.pi / 2
        result = self.arena.roll(self.player.id)
        self.assertFalse(result["ok"])
        self.assertIn("заблокирован", result["error"])
        self.assertAlmostEqual(self.player.x, 950.0, places=3)
        self.assertAlmostEqual(self.player.y, 449.0, places=3)
        self.assertEqual(self.player.roll_ready_at, 0.0)

    def test_roll_is_not_allowed_while_dead(self) -> None:
        self.player.dead = True
        result = self.arena.roll(self.player.id)
        self.assertFalse(result["ok"])
        self.assertIn("возрождения", result["error"])


class MovementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena = Arena(bots=0)
        self.player = self.arena.add_player("Ходок")
        self.player.invuln_until = 0.0

    def step(self) -> None:
        self.arena.now += 1 / TICK_RATE
        self.arena.update(self.arena.now)

    def test_movement_changes_position(self) -> None:
        self.player.x, self.player.y = 700.0, 600.0
        self.arena.set_input(
            self.player.id, up=False, down=False, left=False, right=True
        )
        self.step()
        self.assertAlmostEqual(self.player.x, 700.0 + MOVE_SPEED / TICK_RATE)

    def test_diagonal_movement_is_normalised(self) -> None:
        self.player.x, self.player.y = 700.0, 600.0
        self.arena.set_input(
            self.player.id, up=False, down=True, left=False, right=True
        )
        self.step()
        dx = self.player.x - 700.0
        dy = self.player.y - 600.0
        self.assertAlmostEqual(math.hypot(dx, dy), MOVE_SPEED / TICK_RATE, places=3)

    def test_arena_border_blocks_movement(self) -> None:
        self.player.x = BORDER + PLAYER_RADIUS
        self.player.y = 600.0
        self.arena.set_input(
            self.player.id, up=False, down=False, left=True, right=False
        )
        for _ in range(5):
            self.step()
        self.assertAlmostEqual(self.player.x, BORDER + PLAYER_RADIUS)

    def test_altar_blocks_movement(self) -> None:
        self.player.x, self.player.y = 950.0, 450.0
        self.arena.set_input(
            self.player.id, up=False, down=True, left=False, right=False
        )
        for _ in range(10):
            self.step()
        clearance = math.hypot(self.player.x - 950.0, self.player.y - 550.0)
        self.assertGreaterEqual(clearance, 78 + PLAYER_RADIUS - 0.01)
        self.assertLess(self.player.y, 550.0)

    def test_boundaries_cover_the_whole_playfield(self) -> None:
        self.assertGreater(ARENA_W, 2 * (BORDER + PLAYER_RADIUS))
        self.assertGreater(ARENA_H, 2 * (BORDER + PLAYER_RADIUS))


class ProjectileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena = Arena(bots=0)
        self.caster = self.arena.add_player("Лучник")
        self.dodger = self.arena.add_player("Ловкач")
        self.behind = self.arena.add_player("Сзади")
        for player, x in ((self.caster, 650.0), (self.dodger, 760.0), (self.behind, 860.0)):
            player.x, player.y = x, 600.0
            player.invuln_until = 0.0

    def fly(self, seconds: float = 0.6) -> None:
        for _ in range(int(seconds * TICK_RATE)):
            self.arena.update(self.arena.now + 1 / TICK_RATE)

    def test_a_bolt_flies_past_a_rolling_mage_and_hits_what_is_behind(self) -> None:
        self.dodger.invuln_until = 5.0
        self.assertTrue(self.arena.cast(self.caster.id, "fireball(0)")["ok"])
        self.fly()
        self.assertEqual(self.dodger.hp, MAX_HP)
        self.assertLess(self.behind.hp, MAX_HP)
        kinds = [event["e"] for event in self.arena.drain_events()]
        self.assertIn("impact", kinds, "the bolt must end visibly, not vanish")


class KillCreditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena = Arena(bots=0)
        self.killer = self.arena.add_player("Убийца")
        self.victim = self.arena.add_player("Жертва")
        self.victim.invuln_until = 0.0
        self.victim.hp = 1.0

    def strike(self) -> dict:
        self.arena.drain_events()
        self.arena.damage(
            target=self.victim,
            amount=50.0,
            source=self.killer,
            kind="meteor",
            hit_x=self.victim.x,
            hit_y=self.victim.y,
        )
        return next(e for e in self.arena.drain_events() if e["e"] == "death")

    def test_death_names_the_spell_and_the_streak(self) -> None:
        event = self.strike()
        self.assertEqual(event["kind"], "meteor")
        self.assertEqual(event["streak"], 1)

        self.arena.update(self.arena.now + 1)
        self.victim.dead = False
        self.victim.hp = 1.0
        self.victim.invuln_until = 0.0
        self.assertEqual(self.strike()["streak"], 2)

    def test_a_kill_from_beyond_the_grave_still_counts(self) -> None:
        self.killer.dead = True
        self.strike()
        self.assertEqual(self.killer.score, 1)

    def test_dying_ends_a_streak(self) -> None:
        self.victim.streak = 4
        self.strike()
        self.assertEqual(self.victim.streak, 0)


class BotTests(unittest.TestCase):
    def test_the_arena_fills_up_and_makes_room_for_people(self) -> None:
        arena = Arena(bots=0, fill_to=4)
        self.assertEqual(arena.online_counts()["bots"], 4)
        arena.add_player("Первый")
        arena.update(arena.now + 1 / TICK_RATE)
        self.assertEqual(arena.online_counts()["bots"], 3)

    def test_two_people_are_enough_to_send_the_spirits_away(self) -> None:
        arena = Arena(bots=0, fill_to=4)
        arena.add_player("Первый")
        second = arena.add_player("Второй")
        arena.update(arena.now + 1 / TICK_RATE)
        self.assertEqual(arena.online_counts(), {"humans": 2, "bots": 0, "online": 2})
        self.assertFalse([player for player in arena.players.values() if player.is_bot])
        arena.remove_player(second.id)
        arena.update(arena.now + 1 / TICK_RATE)
        self.assertEqual(arena.online_counts()["bots"], 3, "a mage left alone gets company")

    def test_a_fixed_count_holds_for_one_person_but_not_for_two(self) -> None:
        arena = Arena(bots=2)
        arena.add_player("Первый")
        arena.update(arena.now + 1 / TICK_RATE)
        self.assertEqual(arena.online_counts()["bots"], 2)
        arena.add_player("Второй")
        arena.update(arena.now + 1 / TICK_RATE)
        self.assertEqual(arena.online_counts()["bots"], 0)

    def test_every_bot_spell_is_valid_and_castable(self) -> None:
        arena = Arena(bots=0)
        target = arena.add_player("Цель")
        target.x, target.y = 1300.0, 700.0
        for style, code in BOT_SPELLS.items():
            for distance in (150.0, 300.0, 500.0):
                with self.subTest(style=style, distance=distance):
                    bot = arena.add_player(f"{style}{distance:.0f}"[:16], is_bot=True)
                    bot.x, bot.y = target.x - distance, target.y
                    result = arena.cast(
                        bot.id, code, 0, 0.0, bot.x + distance, bot.y
                    )
                    self.assertTrue(result["ok"], result)
                    arena.remove_player(bot.id)

    def test_bots_lead_a_moving_target(self) -> None:
        arena = Arena(bots=0)
        bot = arena.add_player("Дух", is_bot=True)
        target = arena.add_player("Бегун")
        bot.x, bot.y = 700.0, 600.0
        target.x, target.y = 1000.0, 600.0
        target.last_x, target.last_y = target.x, target.y - MOVE_SPEED / TICK_RATE
        _, lead_y = arena._bot_lead_point(bot, target, 300.0)
        self.assertGreater(lead_y, target.y)

    def test_bots_do_not_extrapolate_a_teleport(self) -> None:
        arena = Arena(bots=0)
        bot = arena.add_player("Дух", is_bot=True)
        target = arena.add_player("Бегун")
        target.last_x = target.x - 300.0
        self.assertEqual(
            arena._bot_lead_point(bot, target, 300.0), (target.x, target.y)
        )

    def test_bots_roll_out_of_the_way_of_a_bolt(self) -> None:
        arena = Arena(bots=0)
        caster = arena.add_player("Лучник")
        bot = arena.add_player("Дух", is_bot=True)
        caster.x, caster.y = 700.0, 650.0
        bot.x, bot.y = 800.0, 650.0
        arena.cast(caster.id, "fireball(0)", 0, 0.0)
        with mock.patch("arcane.game.random.random", return_value=0.0):
            arena._bot_dodge(bot, arena.now)
        self.assertGreater(bot.roll_ready_at, arena.now)
        self.assertNotEqual(bot.y, 650.0, "a roll along the bolt's path dodges nothing")


if __name__ == "__main__":
    unittest.main()
