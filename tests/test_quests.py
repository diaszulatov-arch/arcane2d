"""Tests for each stage's problem: rooms that load, quests, odd side rooms."""

from __future__ import annotations

import json
import math
import random
import unittest

from arcane.campaign import STAGES
from arcane.dungeon import TILE, build_dungeon
from arcane.game import TICK_RATE
from arcane.lessons import check_task
from arcane.monsters import SPECIES
from arcane.profiles import Profile
from arcane.interpreter import validate_source
from arcane.quest_data import CONFLICTS, HAM_LETTERS, QUEST_TASKS, QUESTS, SPAM_LETTERS
from arcane.quests import QuestUnit, make_code
from arcane.story import StoryArena
from story_bot import play_stage

TICK = 1 / TICK_RATE


def advance(arena: StoryArena, seconds: float) -> list[dict]:
    events: list[dict] = []
    for _ in range(int(seconds * TICK_RATE)):
        arena.update(arena.now + TICK)
        events.extend(arena.drain_events())
    return events


def stage_with(quest: str):
    return next(stage for stage in STAGES if stage.quest == quest)


def arena_for(quest: str, mages: int = 1, seed: int = 3) -> tuple[StoryArena, list]:
    arena = StoryArena(stage_with(quest), mages, seed=seed, now=1.0)
    party = [arena.add_player(f"Маг {index + 1}") for index in range(mages)]
    for mage in party:
        mage.invuln_until = 1e9
    return arena, party


def stand(mage, x: float, y: float) -> None:
    mage.x, mage.y = x, y


def finish_step(arena: StoryArena) -> None:
    arena.quest._complete()


def to_step(arena: StoryArena, kind: str) -> None:
    while arena.quest.step.kind != kind:
        finish_step(arena)


def in_quest_room(arena: StoryArena, mage) -> None:
    """Into the room, off to one side: nothing in these games is at dead centre."""

    x, y = arena.quest.quest_room.center
    stand(mage, x + 40, y + 300)


def hit(arena: StoryArena, target, source, kind: str = "fire", amount: float = 1e6) -> float:
    return arena.damage(
        target=target, amount=amount, source=source, kind=kind, hit_x=target.x, hit_y=target.y
    )


class LayoutTests(unittest.TestCase):
    def test_side_rooms_are_dead_ends_off_the_way_through(self) -> None:
        for seed in range(40):
            layout = ["start", "combat", "combat", "quest", "exit"]
            dungeon = build_dungeon(layout, random.Random(seed), ["vault", "trap", "cache", "den"])
            self.assertEqual([room.kind for room in dungeon.path], layout)
            for room in dungeon.sides:
                self.assertNotEqual(room.parent, dungeon.main - 1, "nothing hangs off the exit")
                links = [hall for hall in dungeon.corridors if room.index in (hall.a, hall.b)]
                children = [other for other in dungeon.sides if other.parent == room.index]
                self.assertEqual(len(links), 1 + len(children))
            for hall in dungeon.corridors:
                self.assertGreater(hall.w, 0)
                self.assertGreater(hall.h, 0)

    def test_every_ordinary_stage_has_a_quest_and_a_quest_room(self) -> None:
        for stage in STAGES:
            if stage.is_boss:
                self.assertEqual(stage.quest, "")
                continue
            self.assertIn(stage.quest, QUESTS)
            self.assertEqual(stage.layout[-2:], ["quest", "exit"])
        self.assertEqual(len({stage.quest for stage in STAGES if stage.quest}), 15)

    def test_a_quest_gets_the_side_rooms_it_asked_for(self) -> None:
        arena, _ = arena_for("mysql")
        tags = {room.tag: room for room in arena.dungeon.sides if room.tag}
        self.assertEqual(tags["tape1"].kind, "trap")
        self.assertTrue(tags["tape2"].guarded)
        specials = [room.kind for room in arena.dungeon.sides if not room.tag]
        self.assertEqual(len(specials), 4)
        self.assertIn("workshop", specials)
        self.assertIn("secret", specials)

    def test_no_two_quests_play_the_same(self) -> None:
        plays = [
            tuple(step.kind for step in quest.steps if step.kind != "console")
            for quest in QUESTS.values()
        ]
        self.assertEqual(len(set(plays)), len(QUESTS), plays)
        main_games = [play[-1] for play in plays]
        self.assertEqual(len(set(main_games)), len(QUESTS) - 1, "only choice may close two quests")


class FogTests(unittest.TestCase):
    def test_only_the_start_is_loaded_at_first(self) -> None:
        arena, _ = arena_for("nginx")
        self.assertEqual(arena.revealed, {0})
        self.assertEqual(json.loads(json.dumps(arena.snapshot()))["story"]["seen"], [0])

    def test_a_room_loads_when_a_mage_reaches_its_doorway(self) -> None:
        arena, (mage,) = arena_for("nginx")
        room = arena.dungeon.rooms[1]
        stand(mage, *room.center)
        events = advance(arena, 0.3)
        self.assertIn(1, arena.revealed)
        self.assertIn({"e": "reveal", "room": 1, "kind": room.kind}, events)

    def test_the_config_tells_the_client_where_halls_and_dark_rooms_are(self) -> None:
        arena, _ = arena_for("logs")
        config = arena.world_config()
        self.assertEqual(len(config["corridors"]), len(arena.dungeon.corridors))
        self.assertTrue(any(room["dark"] for room in config["rooms"]))
        self.assertEqual(config["quest"]["key"], "logs")


class ExitTests(unittest.TestCase):
    def test_the_way_to_the_main_terminal_stays_shut_until_the_quest_is_done(self) -> None:
        arena, _ = arena_for("balancer")
        exit_doors = set(arena.exit_room.doors)
        self.assertTrue(exit_doors <= arena.dungeon.closed)
        while not arena.quest.done:
            finish_step(arena)
        events = arena.drain_events()
        self.assertFalse(exit_doors & arena.dungeon.closed)
        self.assertIn("exit_open", [event["e"] for event in events])
        self.assertIn("quest_done", [event["e"] for event in events])

    def test_solving_a_quest_pays_tokens(self) -> None:
        arena, _ = arena_for("dns")
        while not arena.quest.done:
            finish_step(arena)
        self.assertGreater(arena.essence, 0)


class ConsoleTests(unittest.TestCase):
    def test_every_quest_console_takes_its_fix_and_refuses_the_broken_code(self) -> None:
        for key, task in QUEST_TASKS.items():
            with self.subTest(task=key):
                self.assertTrue(check_task(task, task.solution, set())["ok"])
                self.assertFalse(check_task(task, task.starter, set())["ok"])

    def test_every_console_a_quest_names_exists(self) -> None:
        for quest in QUESTS.values():
            for step in quest.steps:
                if step.kind == "console":
                    self.assertIn(step.opts["task"], QUEST_TASKS)

    def test_a_quest_console_moves_the_quest_on(self) -> None:
        arena, (mage,) = arena_for("balancer")
        terminal = arena.quest.state["terminal"]
        stand(mage, terminal.x, terminal.y + 40)
        self.assertIsNotNone(arena.link(mage.id)[0])
        self.assertFalse(arena.submit_fix(mage.id, terminal.task.starter)["ok"])
        self.assertTrue(arena.submit_fix(mage.id, terminal.task.solution)["ok"])
        self.assertEqual(arena.quest.step.kind, "balance")

    def test_accepting_pgt_skips_the_step_but_bugs_come_later(self) -> None:
        arena, (mage,) = arena_for("balancer")
        terminal = arena.quest.state["terminal"]
        stand(mage, terminal.x, terminal.y + 40)
        arena.link(mage.id)
        self.assertTrue(arena.accept_pgt(mage.id)["ok"])
        self.assertEqual(arena.quest.step.kind, "balance")
        self.assertNotIn(mage.id, arena.linked)
        before = len(arena.monsters)
        advance(arena, 20)
        self.assertGreater(len(arena.monsters), before)

    def test_pgt_cannot_fix_a_main_terminal(self) -> None:
        arena, (mage,) = arena_for("balancer")
        portal = next(t for t in arena.terminals if t.role == "portal")
        stand(mage, portal.x, portal.y + 40)
        arena.link(mage.id)
        self.assertFalse(arena.accept_pgt(mage.id)["ok"])


class HuntTests(unittest.TestCase):
    def test_workers_appear_only_when_their_room_loads_and_flee(self) -> None:
        arena, (mage,) = arena_for("nginx")
        self.assertFalse(arena.monsters)
        room = arena.quest.state["pending"][0]
        stand(mage, *room.center)
        advance(arena, 0.4)
        workers = [m for m in arena.monsters.values() if m.species.key == "worker"]
        self.assertTrue(workers)
        worker = workers[0]
        stand(mage, worker.x + 120, worker.y)
        start = math.hypot(worker.x - mage.x, worker.y - mage.y)
        advance(arena, 0.6)
        self.assertGreater(math.hypot(worker.x - mage.x, worker.y - mage.y), start)

    def test_catching_every_worker_solves_the_problem(self) -> None:
        arena, (mage,) = arena_for("nginx")
        arena.revealed = set(range(len(arena.dungeon.rooms)))
        advance(arena, 0.2)
        for monster in [m for m in arena.monsters.values() if m.quest]:
            arena._kill(monster, mage)
        advance(arena, 0.1)
        self.assertTrue(arena.quest.done)

    def test_quest_creatures_do_not_hold_a_fight_room_shut(self) -> None:
        arena, (mage,) = arena_for("nginx")
        arena.revealed = set(range(len(arena.dungeon.rooms)))
        advance(arena, 0.2)
        self.assertTrue(arena.monsters)
        self.assertFalse(arena._fighters())


class CollectTests(unittest.TestCase):
    def test_walking_over_backups_counts_them(self) -> None:
        arena, (mage,) = arena_for("mysql")
        items = arena.quest.state["items"]
        for item in items:
            stand(mage, item.x, item.y)
            advance(arena, 0.1)
        self.assertEqual(arena.quest.step.kind, "console")

    def test_grep_noise_is_not_evidence(self) -> None:
        arena, (mage,) = arena_for("logs")
        to_step(arena, "collect")
        noise = next(i for i in arena.quest.state["items"] if i.data.get("noise"))
        stand(mage, noise.x, noise.y)
        events = advance(arena, 0.1)
        self.assertEqual(arena.quest.state["done"], 0)
        self.assertIn("quest_note", [event["e"] for event in events])
        self.assertEqual(
            len(arena.quest._marks_collect()), arena.quest.state["need"], "only the real ones are marked"
        )


class DefendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = arena_for("mysql")
        finish_step(self.arena)
        finish_step(self.arena)
        self.device = self.arena.quest.device
        stand(self.mage, self.device.x + 100, self.device.y + 100)

    def test_the_machine_can_be_hit_while_it_restores(self) -> None:
        self.assertIn(self.device, self.arena.targets_for(1 << 40))
        self.assertTrue(self.arena.locks.get("defend"))

    def test_bugs_go_for_the_machine(self) -> None:
        advance(self.arena, 3)
        self.assertTrue(any(m.focus == self.device.id for m in self.arena.monsters.values()))

    def test_a_crash_costs_progress(self) -> None:
        advance(self.arena, 6)
        before = self.arena.quest.state["elapsed"]
        self.arena.damage(
            target=self.device, amount=1e6, source=None, kind="bite",
            hit_x=self.device.x, hit_y=self.device.y,
        )
        self.assertLess(self.arena.quest.state["elapsed"], before)
        self.assertGreater(self.device.down_until, self.arena.now)

    def test_holding_out_finishes_the_quest(self) -> None:
        self.arena.quest.state["elapsed"] = self.arena.quest.state["time"]
        advance(self.arena, 0.1)
        self.assertTrue(self.arena.quest.done)
        self.assertFalse(self.arena.locks.get("defend"))


class EscortTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = arena_for("sysadmin")
        finish_step(self.arena)
        self.npc = next(u for u in self.arena.quest.units.values() if u.sprite == "admin")

    def test_valera_follows_and_gets_out(self) -> None:
        self.assertFalse(self.npc.targetable)
        stand(self.mage, self.npc.x + 100, self.npc.y)
        advance(self.arena, 0.2)
        self.assertTrue(self.arena.quest.state["found"])
        stand(self.mage, self.npc.x + 300, self.npc.y)
        start = math.hypot(self.npc.x - self.mage.x, self.npc.y - self.mage.y)
        advance(self.arena, 0.5)
        self.assertLess(math.hypot(self.npc.x - self.mage.x, self.npc.y - self.mage.y), start)
        stand(self.npc, *self.arena.quest.state["dest"])
        advance(self.arena, 0.1)
        self.assertTrue(self.arena.quest.done)

    def test_he_gets_back_up_with_a_friend_beside_him(self) -> None:
        stand(self.mage, self.npc.x + 60, self.npc.y)
        advance(self.arena, 0.2)
        hit(self.arena, self.npc, None, "bite")
        self.assertGreater(self.npc.down_until, self.arena.now)
        self.assertNotIn(self.npc, self.arena.quest.targets())
        advance(self.arena, 3)
        self.assertLessEqual(self.npc.down_until, self.arena.now)
        self.assertGreater(self.npc.hp, 0)


class ResolveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = arena_for("dns")
        self.state = self.arena.quest.state
        self.servers = self.state["servers"]

    def server(self, hop: int, forged: bool):
        return next(s for s in self.servers if s.data["hop"] == hop and s.data["forged"] == forged)

    def test_every_forgery_differs_by_a_character_or_two(self) -> None:
        for real, fake, _ in self.state["chain"]:
            self.assertEqual(len(real), len(fake))
            self.assertLessEqual(sum(a != b for a, b in zip(real, fake)), 2)
            self.assertNotEqual(real, fake)

    def test_the_client_cannot_tell_a_forgery_before_touching_it(self) -> None:
        for entry in self.arena.quest.snapshot()["things"]:
            if entry["k"] == "ns":
                self.assertNotIn("bad", entry)
                self.assertNotIn("forged", entry)

    def test_a_forged_server_ambushes_and_burns(self) -> None:
        fake = self.server(0, True)
        stand(self.mage, fake.x, fake.y)
        events = advance(self.arena, 0.1)
        self.assertIn("ns_forged", [event["e"] for event in events])
        self.assertTrue(fake.bad)
        self.assertEqual(self.state["hop"], 0)
        self.assertTrue(self.arena.monsters)

    def test_a_later_server_only_says_to_ask_first(self) -> None:
        later = self.server(1, False)
        stand(self.mage, later.x, later.y)
        events = advance(self.arena, 0.1)
        self.assertEqual(self.state["hop"], 0)
        self.assertIn("radio", [event["e"] for event in events])

    def test_walking_the_chain_reaches_the_console(self) -> None:
        for hop in range(len(self.state["chain"])):
            self.assertEqual(self.arena.quest.state["fmt"]["next"], self.state["chain"][hop][0])
            real = self.server(hop, False)
            stand(self.mage, real.x, real.y)
            advance(self.arena, 0.1)
        self.assertEqual(self.arena.quest.step.kind, "console")

    def test_the_request_flies_off_when_the_record_is_fixed(self) -> None:
        while not self.arena.quest.done:
            finish_step(self.arena)
        self.assertFalse(any(u.sprite == "request" for u in self.arena.quest.units.values()))


class BalanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = arena_for("balancer")
        to_step(self.arena, "balance")
        self.state = self.arena.quest.state
        self.nodes = self.state["nodes"]

    def test_the_problem_waits_for_the_party(self) -> None:
        stand(self.mage, *self.arena.dungeon.rooms[0].center)
        advance(self.arena, 1)
        self.assertEqual(self.state["served"], 0.0)

    def test_traffic_goes_where_a_mage_stands(self) -> None:
        node = self.nodes[2]
        stand(self.mage, node.x, node.y)
        advance(self.arena, 2)
        self.assertEqual(self.state["route"], [node])
        self.assertGreater(node.charge, 0.0)
        self.assertGreater(self.state["served"], 0.0)

    def test_a_node_with_more_cores_lasts_longer(self) -> None:
        strong, weak = self.nodes[0], self.nodes[2]
        self.assertGreater(strong.data["capacity"], weak.data["capacity"])
        stand(self.mage, strong.x, strong.y)
        advance(self.arena, 2)
        grown_strong = strong.charge
        stand(self.mage, weak.x, weak.y)
        advance(self.arena, 2)
        self.assertGreater(weak.charge, grown_strong)

    def test_the_whole_cluster_can_keep_up_if_traffic_is_shared(self) -> None:
        capacity = sum(node.data["capacity"] for node in self.nodes)
        self.assertLess(self.state["rate"], capacity)

    def test_an_overloaded_node_melts_and_costs_progress(self) -> None:
        node = self.nodes[0]
        stand(self.mage, node.x, node.y)
        self.state["served"] = 20.0
        node.charge = 0.999
        events = advance(self.arena, 0.5)
        self.assertTrue(node.on)
        self.assertLess(self.state["served"], 20.0)
        self.assertIn("unit_down", [event["e"] for event in events])

    def test_serving_long_enough_solves_it(self) -> None:
        in_quest_room(self.arena, self.mage)
        self.state["served"] = self.state["time"]
        advance(self.arena, 0.1)
        self.assertTrue(self.arena.quest.done)


class BucketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = arena_for("ratelimit")
        to_step(self.arena, "bucket")
        self.state = self.arena.quest.state
        in_quest_room(self.arena, self.mage)

    def test_bots_run_for_the_gate_and_eat_tokens(self) -> None:
        tokens = self.state["tokens"]
        self.state["refill"] = 0.0
        bot = self.arena.spawn_monster("ratebot", self.mage.x + 400, self.mage.y)
        bot.quest = "bucket"
        goal = self.arena.quest.runner_goal()
        stand(bot, goal[0] + 30, goal[1])
        bot.spawned_at = 0.0
        advance(self.arena, 0.1)
        self.assertNotIn(bot.id, self.arena.monsters)
        self.assertLess(self.state["tokens"], tokens)

    def test_bots_ignore_the_mages(self) -> None:
        self.assertEqual(SPECIES["ratebot"].contact, 0)
        self.assertEqual(SPECIES["ratebot"].shot_damage, 0)

    def test_a_person_with_a_token_gets_through(self) -> None:
        goal = self.arena.quest.runner_goal()
        person = self.arena.quest._add("walker", goal[0], goal[1], self.arena.quest.quest_room, label="аня")
        self.state["people"].append(person)
        advance(self.arena, 0.1)
        self.assertEqual(self.state["done"], 1)

    def test_a_person_without_one_gets_429(self) -> None:
        goal = self.arena.quest.runner_goal()
        self.state["tokens"] = 0.0
        self.state["refill"] = 0.0
        person = self.arena.quest._add("walker", goal[0], goal[1], self.arena.quest.quest_room, label="аня")
        self.state["people"].append(person)
        events = advance(self.arena, 0.1)
        self.assertEqual(self.state["done"], 0)
        self.assertTrue(any("429" in event.get("text", "") for event in events))

    def test_enough_people_through_solves_it(self) -> None:
        self.state["done"] = self.state["need"]
        advance(self.arena, 0.1)
        self.assertTrue(self.arena.quest.done)
        self.assertFalse(self.arena.quest._tagged("bucket"))


class LeakTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = arena_for("bucket")
        to_step(self.arena, "leak")
        self.state = self.arena.quest.state
        in_quest_room(self.arena, self.mage)
        self.quest = self.arena.quest

    def file(self, bad: bool = False):
        hole = self.state["holes"][0]
        extra = {"bad": True} if bad else {}
        item = self.quest._add("item", self.mage.x, self.mage.y, self.quest.quest_room, label="f", data={"hole": hole}, **extra)
        self.state["files"].append(item)
        return item

    def test_files_crawl_toward_a_public_hole(self) -> None:
        advance(self.arena, 2)
        item = next(f for f in self.state["files"] if not f.gone)
        hole = item.data["hole"]
        start = math.hypot(item.x - hole.x, item.y - hole.y)
        self.mage.x += 2000
        stand(self.mage, *self.arena.quest.quest_room.center)
        self.mage.y += 300
        advance(self.arena, 0.5)
        self.assertLess(math.hypot(item.x - hole.x, item.y - hole.y), start)

    def test_catching_a_clean_file_counts(self) -> None:
        self.file()
        advance(self.arena, 0.1)
        self.assertEqual(self.state["done"], 1)

    def test_an_infected_file_bursts(self) -> None:
        self.mage.invuln_until = 0.0
        hp = self.mage.hp
        self.file(bad=True)
        events = advance(self.arena, 0.1)
        self.assertLess(self.mage.hp, hp)
        self.assertEqual(self.state["done"], 0)
        self.assertIn("quest_burst", [event["e"] for event in events])

    def test_a_clean_file_can_get_away(self) -> None:
        item = self.file()
        hole = item.data["hole"]
        stand(item, hole.x, hole.y)
        advance(self.arena, 0.1)
        self.assertTrue(item.gone)
        self.assertEqual(self.state["leaks"], 1)
        self.assertEqual(self.state["done"], 0)


class ComposeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = arena_for("docker")
        self.state = self.arena.quest.state
        self.mage.invuln_until = 1e9
        in_quest_room(self.arena, self.mage)

    def order(self) -> list[str]:
        graph = self.state["graph"]
        done: list[str] = []
        while len(done) < len(graph):
            done += [n for n, needs in graph.items() if n not in done and all(x in done for x in needs)]
        return done

    def start(self, name: str) -> None:
        box = self.state["containers"][name]
        stand(self.mage, box.x, box.y)
        advance(self.arena, self.state["hold"] + 0.2)

    def test_the_file_on_screen_is_the_real_graph(self) -> None:
        code = self.arena.quest.snapshot()["card"]["code"]
        for name, needs in self.state["graph"].items():
            self.assertIn(f"{name}:", code)
            for need in needs:
                self.assertIn(need, code)

    def test_starting_before_a_dependency_crashes(self) -> None:
        top = self.order()[-1]
        self.mage.invuln_until = 0.0
        hp = self.mage.hp
        self.start(top)
        self.assertEqual(self.state["containers"][top].status, "exited")
        self.assertLess(self.mage.hp, hp)

    def test_the_right_order_brings_everything_up(self) -> None:
        for name in self.order():
            self.start(name)
        self.assertEqual(self.arena.quest.step.kind, "console")

    def test_a_fallen_dependency_takes_its_dependents_down(self) -> None:
        order = self.order()
        for name in order[:-1]:
            self.start(name)
        root = self.state["containers"][order[0]]
        root.invuln_until = 0.0
        hit(self.arena, root, None, "bite")
        graph = self.state["graph"]
        for name, needs in graph.items():
            if order[0] in needs:
                self.assertEqual(self.state["containers"][name].status, "exited")
        self.assertEqual(root.status, "exited")
        self.assertFalse(root.targetable)


class ChoiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = arena_for("merge")
        self.state = self.arena.quest.state
        in_quest_room(self.arena, self.mage)

    def pick(self, index: int) -> None:
        circle = self.arena.quest.state["circles"][index]
        stand(self.mage, circle.x, circle.y)
        advance(self.arena, self.state["hold"] + 0.2)

    def test_the_conflict_shows_both_versions(self) -> None:
        code = self.arena.quest.snapshot()["card"]["code"]
        self.assertIn("<<<<<<< main", code)
        self.assertIn(">>>>>>> feature", code)

    def test_the_right_version_moves_on_and_the_wrong_one_breaks_the_build(self) -> None:
        wrong = 1 - self.state["answer"]
        self.mage.invuln_until = 0.0
        hp = self.mage.hp
        self.pick(wrong)
        self.assertLess(self.mage.hp, hp)
        self.assertEqual(self.state["done"], 0)
        self.assertTrue(self.arena.monsters)
        self.mage.invuln_until = 1e9
        self.pick(self.state["answer"])
        self.assertEqual(self.state["done"], 1)

    def test_three_conflicts_lead_to_the_console(self) -> None:
        for _ in range(3):
            self.pick(self.arena.quest.state["answer"])
        self.assertEqual(self.arena.quest.step.kind, "console")

    def test_every_good_version_is_python_that_parses(self) -> None:
        for _, good, _bad in CONFLICTS:
            source = good
            if good.startswith(("def ", "if ", "for ")) and "\n" not in good:
                source = f"{good}\n    pass\n"
            if good.startswith("return"):
                source = f"def f(a, b):\n    {good}\n"
            validate_source(source)

    def test_only_ada_is_the_right_answer_in_the_journal(self) -> None:
        arena, (mage,) = arena_for("logs")
        to_step(arena, "choice")
        state = arena.quest.state
        self.assertEqual(state["circles"][state["answer"]].label, "ada_l")


class RackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = arena_for("cooling")
        self.state = self.arena.quest.state

    def powered(self) -> list:
        in_quest_room(self.arena, self.mage)
        advance(self.arena, 0.1)
        return self.arena.quest._tagged("racks")

    def test_racks_stay_cold_until_someone_walks_in(self) -> None:
        advance(self.arena, 1)
        self.assertFalse(self.arena.quest._tagged("racks"))
        self.assertTrue(self.powered())

    def test_frost_cools_fire_heats_and_nothing_hurts(self) -> None:
        rack = self.powered()[0]
        temps = self.state["temps"]
        temps[rack.id] = 70.0
        self.assertEqual(hit(self.arena, rack, self.mage, "frost"), 0.0)
        self.assertLess(temps[rack.id], 70.0)
        cooled = temps[rack.id]
        hit(self.arena, rack, self.mage, "fire")
        self.assertGreater(temps[rack.id], cooled)
        self.assertEqual(rack.hp, rack.max_hp)
        self.assertIn(rack.id, self.arena.monsters)

    def test_a_real_frostbolt_cools_a_rack(self) -> None:
        rack = self.powered()[0]
        self.state["temps"][rack.id] = 80.0
        stand(self.mage, rack.x - 150, rack.y)
        self.arena.known_runes = self.arena.known_runes | {"frostbolt"}
        self.mage.cast_ready_at = 0.0
        self.assertTrue(self.arena.cast(self.mage.id, "frostbolt(aim())", 0, 0.0)["ok"])
        advance(self.arena, 0.6)
        self.assertLess(self.state["temps"][rack.id], 80.0)

    def test_auto_aim_can_tell_a_rack_from_a_bug(self) -> None:
        self.powered()
        self.mage.cast_ready_at = 0.0
        result = self.arena.cast(self.mage.id, 'log(enemies()[0].kind)', 0, 0.0)
        self.assertEqual(result["log"], ["hotrack"])

    def test_a_rack_at_the_limit_catches_fire_and_costs_time(self) -> None:
        rack = self.powered()[0]
        self.state["elapsed"] = 30.0
        self.state["temps"][rack.id] = 99.99
        events = advance(self.arena, 0.2)
        self.assertLess(self.state["elapsed"], 30.0)
        self.assertLess(self.state["temps"][rack.id], 99.0)
        self.assertTrue(self.arena.hazards)
        self.assertIn("unit_down", [event["e"] for event in events])

    def test_outlasting_the_fans_moves_on(self) -> None:
        self.powered()
        self.state["elapsed"] = self.state["time"]
        advance(self.arena, 0.1)
        self.assertEqual(self.arena.quest.step.kind, "console")
        self.assertFalse(self.arena.quest._tagged("racks"))


class MemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = arena_for("oom")
        to_step(self.arena, "memory")
        self.state = self.arena.quest.state
        in_quest_room(self.arena, self.mage)
        advance(self.arena, 0.1)
        self.leak = self.arena.quest._tagged(self.state["tag"])[0]
        self.leak.spawned_at = 0.0

    def test_the_leak_eats_the_floor_and_grows(self) -> None:
        size = self.leak.radius
        advance(self.arena, 8)
        self.assertGreater(len(self.state["used"]), 3)
        self.assertGreater(self.leak.radius, size)
        goo = self.arena.quest.snapshot()["goo"]
        self.assertEqual(goo["b"].count("1"), len(self.state["used"]))

    def test_standing_on_taken_memory_burns(self) -> None:
        self.mage.invuln_until = 0.0
        self.state["used"].add(self.arena.quest._memory_cell(self.mage.x, self.mage.y))
        self.leak.x, self.leak.y = self.mage.x + 400, self.mage.y
        hp = self.mage.hp
        advance(self.arena, 1)
        self.assertLess(self.mage.hp, hp)
        self.assertGreater(self.mage.slow_until, self.arena.now)

    def test_out_of_memory_hits_everyone_and_frees_half(self) -> None:
        self.mage.invuln_until = 0.0
        hp = self.mage.hp
        for col in range(self.state["cols"]):
            for row in range(self.state["rows"]):
                self.state["used"].add((col, row))
        total = len(self.state["used"])
        advance(self.arena, 0.1)
        self.assertLess(len(self.state["used"]), total)
        self.assertLess(self.mage.hp, hp)

    def test_killing_the_leak_frees_it_all(self) -> None:
        self.state["used"].add((0, 0))
        self.arena._kill(self.leak, self.mage)
        events = advance(self.arena, 0.1)
        self.assertTrue(self.arena.quest.done)
        self.assertIn("memory_free", [event["e"] for event in events])


class PayloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = arena_for("pipeline")
        self.state = self.arena.quest.state
        self.cart = self.state["cart"]

    def beside(self) -> None:
        stand(self.mage, self.cart.x + 60, self.cart.y + 60)

    def roll_to_stop(self) -> None:
        self.state["pos"] = self.state["stops"][0][0] - 1.0
        self.cart.x, self.cart.y = self.arena.quest._cart_point(self.state["pos"])
        self.beside()
        advance(self.arena, 0.3)

    def test_the_build_rides_only_with_a_mage_beside_it(self) -> None:
        advance(self.arena, 1)
        self.assertEqual(self.state["pos"], 0.0)
        self.beside()
        advance(self.arena, 1)
        self.assertGreater(self.state["pos"], 0.0)

    def test_the_route_reaches_the_machine(self) -> None:
        route = self.state["route"]
        self.assertEqual(route[0], self.arena.quest.tagged["p1"].center)
        self.assertLess(math.hypot(route[-1][0] - self.arena.quest.device.x, route[-1][1] - self.arena.quest.device.y), 120)

    def test_failing_tests_stop_it_until_they_are_gone(self) -> None:
        self.roll_to_stop()
        self.assertEqual(self.state["mode"], "test")
        tests = self.arena.quest._tagged(self.state["tag"])
        self.assertTrue(tests)
        where = self.state["pos"]
        advance(self.arena, 1)
        self.assertEqual(self.state["pos"], where)
        for test in tests:
            self.arena._kill(test, self.mage)
        advance(self.arena, 0.5)
        self.assertEqual(self.state["mode"], "roll")
        self.assertGreater(self.state["pos"], where)

    def test_review_needs_the_console(self) -> None:
        self.state["stops"].pop(0)
        self.roll_to_stop()
        self.assertEqual(self.state["mode"], "review")
        terminal = self.state["terminal"]
        stand(self.mage, terminal.x, terminal.y + 40)
        self.arena.link(self.mage.id)
        self.assertTrue(self.arena.submit_fix(self.mage.id, terminal.task.solution)["ok"])
        self.assertEqual(self.state["mode"], "roll")
        self.assertFalse(self.arena.quest.done)

    def test_pgt_getting_there_first_pushes_it_back(self) -> None:
        self.beside()
        self.state["pos"] = 400.0
        self.state["rival"] = 0.9999
        events = advance(self.arena, 0.2)
        self.assertLess(self.state["pos"], 400.0)
        self.assertLess(self.state["rival"], 0.5)
        self.assertIn("boss_cast", [event["e"] for event in events])

    def test_it_never_rolls_back_past_a_passed_stage(self) -> None:
        self.beside()
        self.state["floor"] = 390.0
        self.state["pos"] = 400.0
        self.arena.quest._rival_ships(self.arena.quest.step)
        self.assertGreaterEqual(self.state["pos"], 390.0)

    def test_arriving_ships_the_build(self) -> None:
        self.state["stops"].clear()
        self.state["pos"] = self.state["total"] - 0.5
        self.cart.x, self.cart.y = self.arena.quest._cart_point(self.state["pos"])
        self.beside()
        advance(self.arena, 0.2)
        self.assertTrue(self.arena.quest.done)


class InboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = arena_for("spamfilter")
        to_step(self.arena, "inbox")
        self.state = self.arena.quest.state
        in_quest_room(self.arena, self.mage)
        self.state["next_letter"] = 1e9

    def letter(self, spam: bool):
        room = self.arena.quest.quest_room
        monster = self.arena.spawn_monster("letter", room.center[0] + 300, room.center[1] + 300)
        monster.quest = "inbox"
        monster.leaked = True
        monster.text = "Токены PGT бесплатно!" if spam else "Мам, я поел"
        monster.spawned_at = 0.0
        self.state["spam"][monster.id] = spam
        return monster

    def test_shooting_spam_counts_and_shooting_mail_costs(self) -> None:
        self.state["done"] = 3
        self.arena._kill(self.letter(True), self.mage)
        self.assertEqual(self.state["done"], 4)
        self.arena._kill(self.letter(False), self.mage)
        self.assertEqual(self.state["done"], 3)

    def test_real_mail_arriving_counts_and_spam_arriving_costs(self) -> None:
        self.state["done"] = 3
        self.arena.quest.runner_arrived(self.letter(False))
        self.assertEqual(self.state["done"], 4)
        self.arena.quest.runner_arrived(self.letter(True))
        self.assertEqual(self.state["done"], 3)

    def test_letters_walk_to_the_filter_by_themselves(self) -> None:
        letter = self.letter(False)
        goal = self.arena.quest.runner_goal()
        start = math.hypot(letter.x - goal[0], letter.y - goal[1])
        advance(self.arena, 1)
        self.assertLess(math.hypot(letter.x - goal[0], letter.y - goal[1]), start)

    def test_a_spell_can_read_the_mail(self) -> None:
        self.letter(True)
        self.mage.cast_ready_at = 0.0
        result = self.arena.cast(self.mage.id, 'log("!" in enemies()[0].text)', 0, 0.0)
        self.assertEqual(result["log"], ["True"])

    def test_the_text_travels_but_the_verdict_does_not(self) -> None:
        letter = self.letter(True)
        entry = next(m for m in self.arena.snapshot()["monsters"] if m["id"] == letter.id)
        self.assertEqual(entry["text"], letter.text)
        self.assertNotIn("spam", entry)

    def test_every_spam_letter_can_be_told_by_code(self) -> None:
        self.assertTrue(all("!" in text for text in SPAM_LETTERS))
        self.assertFalse(any("!" in text for text in HAM_LETTERS))

    def test_a_full_inbox_solves_it(self) -> None:
        self.state["done"] = self.state["need"]
        advance(self.arena, 0.1)
        self.assertTrue(self.arena.quest.done)


class CarryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arena, (self.mage,) = arena_for("cdn")
        finish_step(self.arena)
        self.packet = self.arena.quest.state["packet"]

    def test_the_packet_spoils_if_it_takes_too_long(self) -> None:
        stand(self.mage, self.packet.x, self.packet.y)
        advance(self.arena, 0.1)
        self.assertEqual(self.packet.holder, self.mage.id)
        self.assertFalse(self.arena.roll(self.mage.id)["ok"])
        stand(self.mage, *self.arena.quest.state["dest"])
        self.mage.x -= 400
        self.arena.quest.state["ttl"] = 0.05
        advance(self.arena, 0.2)
        self.assertEqual(self.packet.holder, 0)
        self.assertEqual((self.packet.x, self.packet.y), self.arena.quest.state["home"])

    def test_dropping_and_delivering(self) -> None:
        stand(self.mage, self.packet.x, self.packet.y)
        advance(self.arena, 0.1)
        self.assertTrue(self.arena.interact(self.mage.id)["ok"])
        self.assertEqual(self.packet.holder, 0)
        advance(self.arena, 1.5)
        self.assertEqual(self.packet.holder, self.mage.id)
        stand(self.mage, *self.arena.quest.state["dest"])
        advance(self.arena, 0.1)
        self.assertTrue(self.arena.quest.done)


class PlateTests(unittest.TestCase):
    def test_the_code_on_the_wall_says_the_order(self) -> None:
        rng = random.Random(1)
        for chapter in range(5):
            for _ in range(20):
                code, sequence = make_code(rng, chapter, 5)
                self.assertTrue(3 <= len(sequence) <= 4, code)
                self.assertEqual(len(set(sequence)), len(sequence))
        code, _ = make_code(rng, 3, 5, "range")
        self.assertIn("range", code)

    def test_the_right_order_opens_the_rack_and_a_wrong_plate_shocks(self) -> None:
        arena, (mage,) = arena_for("sysadmin")
        board = arena.quest.state["board"]
        wrong = next(p for p in board.plates if p.number != board.sequence[0])
        mage.invuln_until = 0.0
        hp = mage.hp
        stand(mage, wrong.x, wrong.y)
        advance(arena, 0.1)
        self.assertLess(mage.hp, hp)
        self.assertEqual(board.position, 0)
        mage.invuln_until = 1e9
        for number in board.sequence:
            stand(mage, *board.hub)
            advance(arena, 0.1)
            plate = next(p for p in board.plates if p.number == number)
            stand(mage, plate.x, plate.y)
            advance(arena, 0.1)
        advance(arena, 0.1)
        self.assertEqual(arena.quest.step.kind, "escort")


class SideRoomTests(unittest.TestCase):
    def arena_with(self, kind: str) -> tuple[StoryArena, object]:
        for seed in range(200):
            arena = StoryArena(STAGES[4], 1, seed=seed, now=1.0)
            room = next((r for r in arena.dungeon.sides if r.kind == kind), None)
            if room is not None:
                mage = arena.add_player("Маг")
                mage.invuln_until = 1e9
                return arena, room
        self.fail(f"no {kind} room in 200 seeds")

    def test_a_cache_pays_out(self) -> None:
        arena, room = self.arena_with("cache")
        mage = next(iter(arena.players.values()))
        chest = next(t for t in arena.quest.things.values() if t.kind == "chest")
        chest.data["mimic"] = False
        stand(mage, chest.x, chest.y + 40)
        self.assertTrue(arena.interact(mage.id)["ok"])
        self.assertTrue(chest.on)
        self.assertGreater(arena.essence, 0)

    def test_a_phishing_chest_bites(self) -> None:
        arena, room = self.arena_with("cache")
        mage = next(iter(arena.players.values()))
        chest = next(t for t in arena.quest.things.values() if t.kind == "chest")
        chest.data["mimic"] = True
        stand(mage, chest.x, chest.y + 40)
        arena.interact(mage.id)
        self.assertTrue(any(m.species.key == "phish" for m in arena.monsters.values()))

    def test_a_shelter_heals_once(self) -> None:
        arena, room = self.arena_with("rest")
        mage = next(iter(arena.players.values()))
        mage.hp = 10
        stand(mage, *room.center)
        events = advance(arena, 0.2)
        self.assertEqual(mage.hp, mage.max_hp)
        self.assertIn("radio", [event["e"] for event in events])

    def test_a_deal_with_pgt_helps_now_and_bites_later(self) -> None:
        arena, room = self.arena_with("deal")
        mage = next(iter(arena.players.values()))
        altar = next(t for t in arena.quest.things.values() if t.kind == "altar")
        stand(mage, altar.x, altar.y + 40)
        arena.interact(mage.id)
        deal = arena.quest.deal
        self.assertIsNotNone(deal)
        advance(arena, deal.every + 0.5)
        self.assertIn(deal.curse, [event_kind for event_kind in mage.curses])

    def test_a_trial_seals_every_rune_but_one(self) -> None:
        arena, room = self.arena_with("trial")
        mage = next(iter(arena.players.values()))
        stand(mage, *room.center)
        advance(arena, 0.3)
        self.assertIsNotNone(arena.quest.trial)
        self.assertTrue(arena.locks.get("trial"))
        rune = arena.quest.trial["rune"]
        other = "frostbolt" if rune != "frostbolt" else "fireball"
        mage.cast_ready_at = 0.0
        result = arena.cast(mage.id, f"{other}(0)", 0, 0.0)
        self.assertFalse(result["ok"])
        self.assertIn("испытанием", result["error"])

    def test_a_trap_corridor_fires_while_someone_is_inside(self) -> None:
        arena, room = self.arena_with("trap")
        mage = next(iter(arena.players.values()))
        stand(mage, *room.center)
        advance(arena, 0.2)
        self.assertTrue(arena.hazards)


class SnapshotTests(unittest.TestCase):
    def test_the_quest_travels_as_plain_json(self) -> None:
        for quest in QUESTS:
            arena, _ = arena_for(quest)
            advance(arena, 0.2)
            state = json.loads(json.dumps(arena.snapshot()))
            self.assertTrue(state["quest"]["text"])
            config = json.loads(json.dumps(arena.world_config()))
            self.assertTrue(config["quest"]["intro"])

    def test_marks_only_point_into_loaded_rooms(self) -> None:
        arena, _ = arena_for("mysql")
        self.assertEqual(arena.snapshot()["quest"]["marks"], [])
        arena.revealed = set(range(len(arena.dungeon.rooms)))
        self.assertEqual(len(arena.snapshot()["quest"]["marks"]), 2)

    def test_quest_units_are_not_mages(self) -> None:
        arena, _ = arena_for("mysql")
        self.assertTrue(all(not isinstance(p, QuestUnit) for p in arena.players.values()))
        self.assertNotIn(arena.quest.device, arena.targets_for(1))


class BotPlaythroughTests(unittest.TestCase):
    """The scripted party solves quests of every kind, start to portal."""

    def test_every_quest_can_be_finished(self) -> None:
        for quest in QUESTS:
            stage = stage_with(quest)
            level = stage.chapter_index + 1
            profile = Profile(
                "x",
                upgrades={"max_hp": level, "hp_regen": level, "max_mana": level, "mana_regen": level},
            )
            with self.subTest(quest=quest):
                arena = play_stage(stage, 2, profile, seed=2, seconds=500)
                self.assertTrue(arena.quest.done)
                self.assertEqual(arena.outcome, "cleared")

    def test_quest_species_have_bestiary_entries(self) -> None:
        for key in ("worker", "leak", "phish", "ratebot", "hotrack", "failtest", "letter"):
            self.assertIn(key, SPECIES)
            self.assertTrue(SPECIES[key].hint)


if __name__ == "__main__":
    unittest.main()
