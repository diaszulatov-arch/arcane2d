"""Tests for arena geometry, movement and snapshots."""

from __future__ import annotations

import math
import unittest

from arcane.game import (
    ARENA_H,
    ARENA_W,
    BORDER,
    MANA_REGEN,
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


if __name__ == "__main__":
    unittest.main()
