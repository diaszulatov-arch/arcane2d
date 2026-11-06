"""Tests for the safe spell language and its integration with the arena."""

from __future__ import annotations

import math
import time
import unittest

from arcane.game import (
    BEAM_COLOR,
    BEAM_DAMAGE,
    CAST_LOCK,
    CHAIN_DAMAGE,
    EMP_COLOR,
    EMP_DAMAGE_PER_MANA,
    EMP_DELAY,
    EMP_MAX_DRAIN,
    EMP_PULL_LEAD,
    MAX_HP,
    MAX_SPELL_ACTIONS,
    METEOR_DAMAGE,
    METEOR_DELAY,
    POISON_CLOUD_DURATION,
    POISON_DAMAGE,
    POISON_TICK,
    SIPHON_DAMAGE,
    SIPHON_MAX_HEAL,
    SPARK_COLORS,
    SPELL_COSTS,
    STRIKE_DAMAGE,
    STRIKE_STUN,
    Arena,
)
from arcane.interpreter import mana_estimate, validate_source


class SpellCastingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena = Arena(bots=0)
        self.player = self.arena.add_player("Тест")
        self.player.invuln_until = 0.0
        self.player.x = 700.0
        self.player.y = 600.0

    def cast(self, code: str, aim: float = 0.0) -> dict:
        return self.arena.cast(self.player.id, code, 0, aim)

    def test_fireball_spends_mana_and_creates_projectile(self) -> None:
        result = self.cast("fireball(0)")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["actions"], 1)
        self.assertEqual(len(self.arena.projectiles), 1)
        self.assertAlmostEqual(self.player.mana, 100 - SPELL_COSTS["fireball"])
        self.assertEqual(self.arena.projectiles[0].kind, "fire")

    def test_spark_volley_launches_eight_colored_sparks(self) -> None:
        result = self.cast("spark_volley(0, 8, 1.15)")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["actions"], 1)
        self.assertEqual(len(self.arena.projectiles), 8)
        self.assertEqual(
            {projectile.kind for projectile in self.arena.projectiles},
            {"spark"},
        )
        self.assertEqual(
            {projectile.color for projectile in self.arena.projectiles},
            set(SPARK_COLORS),
        )
        angles = sorted(projectile.angle for projectile in self.arena.projectiles)
        self.assertAlmostEqual(angles[-1] - angles[0], 1.15)
        self.assertAlmostEqual(
            self.player.mana, 100 - SPELL_COSTS["spark_volley"]
        )
        events = self.arena.drain_events()
        casts = [
            event
            for event in events
            if event["e"] == "cast" and event.get("kind") == "spark"
        ]
        self.assertEqual(len(casts), 1)
        self.assertEqual(casts[0]["count"], 8)

    def test_cast_target_point_overrides_stale_aim(self) -> None:
        result = self.arena.cast(
            self.player.id,
            "fireball(aim())",
            0,
            0.0,
            700.0,
            800.0,
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(self.arena.projectiles), 1)
        self.assertAlmostEqual(self.arena.projectiles[0].angle, math.pi / 2)
        self.assertAlmostEqual(self.player.aim, math.pi / 2)

    def test_cursor_exposes_manual_target_point(self) -> None:
        result = self.arena.cast(
            self.player.id,
            "point = cursor()\nlog(point.x, point.y, point.dist)\nemp(point.x, point.y)",
            0,
            0.0,
            900.0,
            600.0,
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["log"], ["900.0 600.0 200.0"])
        self.assertEqual(len(self.arena.emps), 1)
        self.assertAlmostEqual(self.arena.emps[0].x, 900.0)
        self.assertAlmostEqual(self.arena.emps[0].y, 600.0)

    def test_cursor_is_none_without_pointer_target(self) -> None:
        result = self.cast(
            "if cursor():\n    log('point')\nelse:\n    log('none')"
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["log"], ["none"])

    def test_math_logs_functions_and_loops(self) -> None:
        result = self.cast(
            """
def power(value):
    return value * 2

total = 0
for step in range(4):
    total += step
log("total", total)
log(f"mode={power(total) % 3}")
log(min(5, max(2, 4)))
"""
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["actions"], 0)
        self.assertEqual(
            result["log"],
            ["total 6", "mode=0", "4"],
        )

    def test_auto_target_helpers_are_not_available(self) -> None:
        for code in ("nearest()", "enemies()"):
            self.arena.now += CAST_LOCK + 0.01
            result = self.cast(code)
            self.assertFalse(result["ok"])
            self.assertIn("Неизвестное имя", result["error"])

    def test_manual_geometry_helpers_remain(self) -> None:
        result = self.cast(
            "log(round(direction(760, 600), 3))\n"
            "log(round(distance(700, 600, 760, 600), 1))"
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["log"], ["0.0", "60.0"])

    def test_import_is_rejected(self) -> None:
        result = self.cast("import os")
        self.assertFalse(result["ok"])
        self.assertIn("Импорт запрещён", result["error"])

    def test_private_attribute_is_rejected(self) -> None:
        result = self.cast("log(me().__class__)")
        self.assertFalse(result["ok"])
        self.assertIn("служебным атрибутам", result["error"])

    def test_banned_name_is_rejected(self) -> None:
        result = self.cast("eval('1 + 1')")
        self.assertFalse(result["ok"])
        self.assertIn("eval", result["error"])

    def test_infinite_loop_is_stopped(self) -> None:
        result = self.cast("while True:\n    pass")
        self.assertFalse(result["ok"])
        self.assertIn("лимит итераций", result["error"])

    def test_action_limit_is_enforced(self) -> None:
        self.player.mana = 500.0
        result = self.cast("for step in range(9):\n    fireball(0)")
        self.assertFalse(result["ok"])
        self.assertIn(str(MAX_SPELL_ACTIONS), result["error"])
        self.assertEqual(result["actions"], MAX_SPELL_ACTIONS)
        self.assertEqual(len(self.arena.projectiles), MAX_SPELL_ACTIONS)

    def test_mana_is_required(self) -> None:
        self.player.mana = 5.0
        result = self.cast("fireball(0)")
        self.assertFalse(result["ok"])
        self.assertIn("Не хватает маны", result["error"])

    def test_cast_lock(self) -> None:
        first = self.cast("log('first')")
        self.assertTrue(first["ok"], first)
        second = self.cast("log('second')")
        self.assertFalse(second["ok"])
        self.assertIn("перезаряжается", second["error"])
        self.assertAlmostEqual(second["cooldown"], CAST_LOCK, places=1)

    def test_heal_and_shield_apply_effects(self) -> None:
        self.player.hp = 40.0
        heal = self.cast("heal()")
        self.assertTrue(heal["ok"], heal)
        self.assertAlmostEqual(self.player.hp, 70.0)

        self.arena.now += CAST_LOCK + 0.01
        shield = self.cast("shield()")
        self.assertTrue(shield["ok"], shield)
        self.assertAlmostEqual(self.player.shield, 38.0)

    def test_syntax_errors_are_reported_with_line(self) -> None:
        result = self.cast("if me().hp < 50\n    heal()")
        self.assertFalse(result["ok"])
        self.assertIn("Строка 1", result["error"])


class CombatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena = Arena(bots=0)
        self.attacker = self.arena.add_player("Атакующий")
        self.target = self.arena.add_player("Цель")
        self.attacker.x, self.attacker.y = 700.0, 600.0
        self.target.x, self.target.y = 850.0, 600.0
        self.attacker.invuln_until = 0.0
        self.target.invuln_until = 0.0

    def test_projectile_damages_target(self) -> None:
        result = self.arena.cast(self.attacker.id, "fireball(0)", 0, 0.0)
        self.assertTrue(result["ok"], result)
        for _ in range(30):
            self.arena.now += 1 / 60
            self.arena.update(self.arena.now)
        self.assertLess(self.target.hp, MAX_HP)
        self.assertAlmostEqual(self.target.hp, MAX_HP - 16.0)

    def test_beam_pierces_a_wide_lane(self) -> None:
        near_line = self.arena.add_player("Рядом с лучом")
        far_from_line = self.arena.add_player("Вне луча")
        near_line.x, near_line.y = 820.0, 640.0
        far_from_line.x, far_from_line.y = 820.0, 700.0
        for player in (near_line, far_from_line):
            player.invuln_until = 0.0

        self.assertAlmostEqual(BEAM_DAMAGE, 34.0)
        self.assertEqual(SPELL_COSTS["beam"], 50)
        result = self.arena.cast(self.attacker.id, "beam(0)", 0, 0.0)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["actions"], 1)
        self.assertAlmostEqual(
            self.attacker.mana, 100 - SPELL_COSTS["beam"]
        )
        self.assertAlmostEqual(self.target.hp, MAX_HP - BEAM_DAMAGE)
        self.assertAlmostEqual(near_line.hp, MAX_HP - BEAM_DAMAGE)
        self.assertAlmostEqual(far_from_line.hp, MAX_HP)
        events = self.arena.drain_events()
        beams = [event for event in events if event["e"] == "beam"]
        self.assertEqual(len(beams), 1)
        self.assertEqual(beams[0]["color"], BEAM_COLOR)

    def test_chain_lightning_hits_and_jumps_between_targets(self) -> None:
        chained = self.arena.add_player("Второй")
        chained.x, chained.y = 1000.0, 600.0
        chained.invuln_until = 0.0

        result = self.arena.cast(
            self.attacker.id, "chain_lightning(0, 3)", 0, 0.0
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["actions"], 1)
        self.assertAlmostEqual(
            self.attacker.mana, 100 - SPELL_COSTS["chain_lightning"]
        )
        self.assertAlmostEqual(self.target.hp, MAX_HP - CHAIN_DAMAGE[0])
        self.assertAlmostEqual(chained.hp, MAX_HP - CHAIN_DAMAGE[1])

        events = self.arena.drain_events()
        bolts = [event for event in events if event["e"] == "chain_lightning"]
        self.assertEqual(len(bolts), 1)
        self.assertEqual(bolts[0]["hits"], 2)
        self.assertEqual(len(bolts[0]["points"]), 3)

    def test_lightning_strike_is_instant_hit_and_stuns(self) -> None:
        result = self.arena.cast(
            self.attacker.id,
            "lightning_strike(0)",
            0,
            0.0,
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["actions"], 1)
        self.assertAlmostEqual(
            self.attacker.mana, 100 - SPELL_COSTS["lightning_strike"]
        )
        self.assertAlmostEqual(self.target.hp, MAX_HP - STRIKE_DAMAGE)
        self.assertAlmostEqual(self.target.stun_until, STRIKE_STUN)
        self.assertEqual(self.arena.projectiles, [])

        events = self.arena.drain_events()
        strikes = [event for event in events if event["e"] == "lightning_strike"]
        self.assertEqual(len(strikes), 1)
        self.assertEqual(strikes[0]["target_id"], self.target.id)
        self.assertAlmostEqual(strikes[0]["stun"], STRIKE_STUN)
        hits = [event for event in events if event["e"] == "hit"]
        self.assertEqual(len(hits), 1)
        self.assertAlmostEqual(hits[0]["amount"], STRIKE_DAMAGE)

    def test_lightning_strike_does_not_stun_an_invulnerable_target(self) -> None:
        self.target.invuln_until = 0.5
        result = self.arena.cast(
            self.attacker.id,
            "lightning_strike(0)",
            0,
            0.0,
        )
        self.assertTrue(result["ok"], result)
        self.assertAlmostEqual(self.target.hp, MAX_HP)
        self.assertEqual(self.target.stun_until, 0.0)
        events = self.arena.drain_events()
        strikes = [event for event in events if event["e"] == "lightning_strike"]
        self.assertEqual(len(strikes), 1)
        self.assertEqual(strikes[0]["stun"], 0.0)

    def test_lightning_strike_misses_outside_aimed_lane(self) -> None:
        result = self.arena.cast(
            self.attacker.id,
            "lightning_strike(PI)",
            0,
            0.0,
        )
        self.assertFalse(result["ok"])
        self.assertIn("нет цели для небесной кары", result["error"])
        self.assertAlmostEqual(self.attacker.mana, 100.0)
        self.assertAlmostEqual(self.target.hp, MAX_HP)
        self.assertEqual(self.arena.projectiles, [])

    def test_stunned_mage_cannot_move_cast_or_roll(self) -> None:
        self.target.stun_until = 0.5
        start_x = self.target.x
        self.arena.set_input(
            self.target.id, up=False, down=False, left=False, right=True
        )
        self.arena.now = 0.2
        self.arena.update(self.arena.now)
        self.assertAlmostEqual(self.target.x, start_x)

        result = self.arena.cast(self.target.id, "fireball(0)", 0, 0.0)
        self.assertFalse(result["ok"])
        self.assertIn("оглушены", result["error"])
        roll = self.arena.roll(self.target.id)
        self.assertFalse(roll["ok"])
        self.assertIn("Оглушение", roll["error"])

    def test_meteor_lands_after_delay_and_damages_area(self) -> None:
        nearby = self.arena.add_player("Рядом")
        nearby.x, nearby.y = 900.0, 650.0
        nearby.invuln_until = 0.0

        result = self.arena.cast(self.attacker.id, "meteor(850, 600)", 0, 0.0)
        self.assertTrue(result["ok"], result)
        self.assertAlmostEqual(self.attacker.mana, 100 - SPELL_COSTS["meteor"])
        self.assertEqual(len(self.arena.meteors), 3)
        self.assertEqual(
            {meteor.role for meteor in self.arena.meteors},
            {"main", "satellite"},
        )

        self.arena.now = METEOR_DELAY - 0.1
        self.arena.update(self.arena.now)
        self.assertAlmostEqual(self.target.hp, MAX_HP)
        self.assertAlmostEqual(nearby.hp, MAX_HP)

        self.arena.now = METEOR_DELAY + 0.01
        self.arena.update(self.arena.now)
        self.assertAlmostEqual(self.target.hp, MAX_HP - METEOR_DAMAGE)
        self.assertAlmostEqual(nearby.hp, MAX_HP - METEOR_DAMAGE)
        self.assertEqual(self.arena.meteors, [])

        events = self.arena.drain_events()
        impacts = [event for event in events if event["e"] == "meteor_impact"]
        self.assertEqual(len(impacts), 3)
        self.assertEqual(sum(event["hits"] for event in impacts), 6)
        self.assertEqual(
            {event["role"] for event in impacts},
            {"main", "satellite"},
        )

    def test_siphon_damages_and_heals_from_actual_health_loss(self) -> None:
        self.attacker.hp = 50.0
        result = self.arena.cast(self.attacker.id, "siphon(0)", 0, 0.0)
        self.assertTrue(result["ok"], result)
        self.assertAlmostEqual(self.target.hp, MAX_HP - SIPHON_DAMAGE)
        expected_heal = min(SIPHON_MAX_HEAL, SIPHON_DAMAGE * 0.6)
        self.assertAlmostEqual(self.attacker.hp, 50.0 + expected_heal)

        events = self.arena.drain_events()
        siphons = [event for event in events if event["e"] == "siphon"]
        self.assertEqual(len(siphons), 1)
        self.assertAlmostEqual(siphons[0]["healed"], expected_heal)

    def test_siphon_does_not_heal_from_absorbed_damage(self) -> None:
        self.attacker.hp = 50.0
        self.target.shield = 10.0
        result = self.arena.cast(self.attacker.id, "siphon(0)", 0, 0.0)
        self.assertTrue(result["ok"], result)
        self.assertAlmostEqual(self.target.hp, MAX_HP - (SIPHON_DAMAGE - 10.0))
        self.assertAlmostEqual(self.attacker.hp, 50.0 + (SIPHON_DAMAGE - 10.0) * 0.6)

    def test_poison_cloud_ticks_and_expires(self) -> None:
        result = self.arena.cast(
            self.attacker.id, "poison_cloud(850, 600)", 0, 0.0
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(self.arena.clouds), 1)

        self.arena.now = POISON_TICK - 0.01
        self.arena.update(self.arena.now)
        self.assertAlmostEqual(self.target.hp, MAX_HP)

        self.arena.now = POISON_TICK + 0.01
        self.arena.update(self.arena.now)
        self.assertAlmostEqual(self.target.hp, MAX_HP - POISON_DAMAGE)
        events = self.arena.drain_events()
        ticks = [event for event in events if event["e"] == "poison_tick"]
        self.assertEqual(len(ticks), 1)

        self.arena.now = POISON_CLOUD_DURATION + 0.01
        self.arena.update(self.arena.now)
        self.assertEqual(self.arena.clouds, [])

    def test_new_spells_are_limited_to_one_per_cast(self) -> None:
        result = self.arena.cast(
            self.attacker.id,
            "meteor(800, 600)\nmeteor(820, 600)",
            0,
            0.0,
        )
        self.assertFalse(result["ok"])
        self.assertIn("только один метеорит", result["error"])

    def test_lightning_strike_is_limited_to_one_per_cast(self) -> None:
        result = self.arena.cast(
            self.attacker.id,
            "lightning_strike(0)\n"
            "lightning_strike(0)",
            0,
            0.0,
        )
        self.assertFalse(result["ok"])
        self.assertIn("только одна небесная молния", result["error"])

    def test_emp_delays_then_drains_and_pulls(self) -> None:
        self.target.x, self.target.y = 850.0, 600.0
        self.target.mana = 100.0
        outside = self.arena.add_player("Вне E.M.P.")
        outside.x, outside.y = 1050.0, 600.0
        outside.invuln_until = 0.0
        outside.mana = 100.0

        result = self.arena.cast(self.attacker.id, "emp(800, 600)", 0, 0.0)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["actions"], 1)
        self.assertAlmostEqual(self.attacker.mana, 100 - SPELL_COSTS["emp"])
        self.assertEqual(len(self.arena.emps), 1)

        self.arena.now = EMP_DELAY - EMP_PULL_LEAD - 0.01
        self.arena.update(self.arena.now)
        self.assertAlmostEqual(self.target.x, 850.0)
        self.assertAlmostEqual(self.target.hp, MAX_HP)

        self.arena.now = EMP_DELAY - EMP_PULL_LEAD + 0.01
        self.arena.update(self.arena.now)
        self.assertLess(self.target.x, 850.0)
        self.assertGreater(self.target.x, 800.0)
        self.assertAlmostEqual(self.target.hp, MAX_HP)
        self.assertAlmostEqual(self.target.mana, 100.0)
        self.assertAlmostEqual(outside.hp, MAX_HP)

        events = self.arena.drain_events()
        pulls = [event for event in events if event["e"] == "emp_pull"]
        self.assertEqual(len(pulls), 1)
        self.assertEqual(pulls[0]["color"], EMP_COLOR)
        self.assertEqual(pulls[0]["hits"], 1)

        self.arena.now = EMP_DELAY - 0.1
        self.arena.update(self.arena.now)
        self.assertAlmostEqual(self.target.hp, MAX_HP)
        self.assertAlmostEqual(self.target.mana, 100.0)
        self.assertAlmostEqual(outside.hp, MAX_HP)

        self.arena.now = EMP_DELAY + 0.01
        self.arena.update(self.arena.now)
        self.assertAlmostEqual(
            self.target.hp,
            MAX_HP - EMP_MAX_DRAIN * EMP_DAMAGE_PER_MANA,
        )
        self.assertAlmostEqual(self.target.mana, 100.0 - EMP_MAX_DRAIN)
        self.assertLess(self.target.x, 850.0)
        self.assertGreater(self.target.x, 800.0)
        self.assertAlmostEqual(outside.hp, MAX_HP)
        self.assertAlmostEqual(outside.mana, 100.0)
        self.assertEqual(self.arena.emps, [])

        events = self.arena.drain_events()
        blasts = [event for event in events if event["e"] == "emp_blast"]
        self.assertEqual(len(blasts), 1)
        self.assertEqual(blasts[0]["color"], EMP_COLOR)
        self.assertAlmostEqual(blasts[0]["drained"], EMP_MAX_DRAIN)

    def test_emp_is_limited_to_one_per_cast(self) -> None:
        result = self.arena.cast(
            self.attacker.id,
            "emp(800, 600)\nemp(820, 600)",
            0,
            0.0,
        )
        self.assertFalse(result["ok"])
        self.assertIn("только один E.M.P.", result["error"])

    def test_shield_absorbs_damage(self) -> None:
        self.target.shield = 20.0
        absorbed_only = self.arena.damage(
            target=self.target,
            amount=16.0,
            source=self.attacker,
            kind="fire",
            hit_x=self.target.x,
            hit_y=self.target.y,
        )
        self.assertAlmostEqual(self.target.hp, MAX_HP)
        self.assertAlmostEqual(self.target.shield, 4.0)
        self.assertAlmostEqual(absorbed_only, 0.0)

        health_loss = self.arena.damage(
            target=self.target,
            amount=10.0,
            source=self.attacker,
            kind="fire",
            hit_x=self.target.x,
            hit_y=self.target.y,
        )
        self.assertAlmostEqual(self.target.hp, MAX_HP - 6.0)
        self.assertAlmostEqual(health_loss, 6.0)

    def test_kill_scores_and_respawn_restores_health(self) -> None:
        self.target.hp = 5.0
        self.arena.damage(
            target=self.target,
            amount=20.0,
            source=self.attacker,
            kind="fire",
            hit_x=self.target.x,
            hit_y=self.target.y,
        )
        self.assertTrue(self.target.dead)
        self.assertEqual(self.attacker.score, 1)
        self.assertEqual(self.target.deaths, 1)

        self.arena.now = 4.0
        self.arena.update(self.arena.now)
        self.assertFalse(self.target.dead)
        self.assertAlmostEqual(self.target.hp, MAX_HP)
        self.assertGreater(self.target.invuln_until, self.arena.now)

    def test_ward_explodes_on_enemy(self) -> None:
        self.arena.place_ward(self.attacker, 780.0, 600.0)
        self.target.x, self.target.y = 790.0, 600.0
        self.arena.now = 1.0
        self.arena.update(self.arena.now)
        self.assertLess(self.target.hp, MAX_HP)
        self.assertEqual(self.arena.wards, [])


LIST_TOWER = """
a = [1] * 250
b = [a] * 250
c = [b] * 250
d = [c] * 250
"""


class SandboxCostTests(unittest.TestCase):
    """Shared references make shallow data enormous; C code must not walk it."""

    def setUp(self) -> None:
        self.arena = Arena(bots=0)
        self.player = self.arena.add_player("Тест")

    def assert_stopped_quickly(self, code: str) -> dict:
        started = time.perf_counter()
        result = self.arena.cast(self.player.id, code, 0, 0.0)
        self.arena.players[self.player.id].cast_ready_at = 0.0
        self.assertLess(time.perf_counter() - started, 0.2, code)
        self.assertFalse(result["ok"], code)
        return result

    def test_stringifying_a_tower_of_lists_is_refused(self) -> None:
        for line in ('x = str(d)', 'x = f"{d}"', "log(d)", "print(d)", "say(d)"):
            with self.subTest(line):
                self.assert_stopped_quickly(LIST_TOWER + line)

    def test_comparing_two_towers_is_billed_as_steps(self) -> None:
        twin = LIST_TOWER.replace("a =", "e =").replace("[a]", "[e]")
        twin = twin.replace("b =", "f =").replace("[b]", "[f]")
        twin = twin.replace("c =", "g =").replace("[c]", "[g]")
        twin = twin.replace("d =", "h =")
        for line in ("x = d == h", "x = d != h", "x = d < h", "x = d in [h]"):
            with self.subTest(line):
                self.assert_stopped_quickly(LIST_TOWER + twin + line)

    def test_min_and_max_only_order_plain_values(self) -> None:
        self.assert_stopped_quickly(LIST_TOWER + "x = max([d, d])")
        self.assert_stopped_quickly("x = min([[1], [2]])")
        self.assertTrue(self.arena.cast(self.player.id, "x = min([1, 2.5, True])")["ok"])

    def test_hashing_a_nested_tuple_as_a_dict_key_is_refused(self) -> None:
        result = self.assert_stopped_quickly("a = {}\nx = a[(1, 2)]")
        self.assertIn("Ключ словаря", result["error"])

    def test_small_collections_still_print(self) -> None:
        result = self.arena.cast(self.player.id, 'log([1, [2, 3]], {"a": 1})')
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["log"], ["[1, [2, 3]] {'a': 1}"])

    def test_fractional_power_of_a_negative_stays_a_real_number(self) -> None:
        result = self.assert_stopped_quickly("x = (-8) ** 0.5")
        self.assertIn("степень", result["error"])


class ReadyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena = Arena(bots=0)
        self.player = self.arena.add_player("Тест")

    def ask(self, name: str) -> bool:
        self.player.cast_ready_at = 0.0
        result = self.arena.cast(self.player.id, f'log(ready("{name}"))', 0, 0.0)
        self.assertTrue(result["ok"], result)
        return result["log"] == ["True"]

    def test_mana_decides_for_an_ordinary_rune(self) -> None:
        self.assertTrue(self.ask("beam"))
        self.player.mana = SPELL_COSTS["beam"] - 1
        self.assertFalse(self.ask("beam"))

    def test_a_shield_on_cooldown_is_not_ready(self) -> None:
        self.assertTrue(self.ask("shield"))
        self.player.cast_ready_at = 0.0
        self.assertTrue(self.arena.cast(self.player.id, "shield()", 0, 0.0)["ok"])
        self.assertFalse(self.ask("shield"))
        self.player.shield = 0.0
        self.assertFalse(self.ask("shield"), "the shield itself is gone, its cooldown is not")
        self.arena.now = self.player.shield_ready_at + 0.1
        self.assertTrue(self.ask("shield"))

    def test_heal_is_not_ready_at_full_health(self) -> None:
        self.assertFalse(self.ask("heal"))
        self.player.hp = 50.0
        self.assertTrue(self.ask("heal"))

    def test_ready_guards_a_spell_against_its_own_cooldown_error(self) -> None:
        code = 'if ready("shield"):\n    shield()\nfireball(0)\n'
        for _ in range(3):
            self.player.cast_ready_at = 0.0
            self.player.mana = 100.0
            self.assertTrue(self.arena.cast(self.player.id, code, 0, 0.0)["ok"])

    def test_an_unknown_rune_name_is_an_error(self) -> None:
        result = self.arena.cast(self.player.id, 'ready("fireblast")', 0, 0.0)
        self.assertFalse(result["ok"])
        self.assertIn("fireblast", result["error"])


class ManaEstimateTests(unittest.TestCase):
    def estimate(self, source: str) -> tuple[int, int]:
        return mana_estimate(validate_source(source), SPELL_COSTS)

    def test_straight_line_spell_has_one_price(self) -> None:
        fire = SPELL_COSTS["fireball"]
        self.assertEqual(self.estimate("fireball(aim())"), (fire, fire))

    def test_a_branch_widens_the_range(self) -> None:
        fire, shield = SPELL_COSTS["fireball"], SPELL_COSTS["shield"]
        self.assertEqual(
            self.estimate("fireball(0)\nif me().hp < 45:\n    shield()\n"),
            (fire, fire + shield),
        )

    def test_counted_loops_multiply(self) -> None:
        fire = SPELL_COSTS["fireball"]
        self.assertEqual(
            self.estimate("for a in [1, 2, 3]:\n    fireball(a)\n"), (fire * 3, fire * 3)
        )
        self.assertEqual(
            self.estimate("for a in range(4):\n    fireball(a)\n"), (fire * 4, fire * 4)
        )

    def test_an_unknown_loop_may_not_run_at_all(self) -> None:
        fire = SPELL_COSTS["fireball"]
        self.assertEqual(
            self.estimate("for a in items:\n    fireball(a)\n"), (0, fire)
        )

    def test_helper_functions_count_where_they_are_called(self) -> None:
        heal = SPELL_COSTS["heal"]
        source = "def mend():\n    heal()\n"
        self.assertEqual(self.estimate(source), (0, 0))
        self.assertEqual(self.estimate(source + "mend()\nmend()\n"), (heal * 2, heal * 2))

    def test_recursion_does_not_hang_the_estimate(self) -> None:
        self.assertEqual(self.estimate("def f():\n    f()\nf()\n"), (0, 0))

    def test_helpers_calling_helpers_stay_linear(self) -> None:
        depth = 120
        source = "".join(
            f"def f{index}():\n    f{index + 1}()\n    f{index + 1}()\n"
            for index in range(depth)
        )
        source += f"def f{depth}():\n    fireball(0)\nf0()\n"
        started = time.perf_counter()
        low, high = self.estimate(source)
        self.assertLess(time.perf_counter() - started, 0.2)
        self.assertEqual((low, high), (999, 999), "a hint needs no 37-digit price tag")


if __name__ == "__main__":
    unittest.main()
