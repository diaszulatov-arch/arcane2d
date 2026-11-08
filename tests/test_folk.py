"""Tests for the people along the way: everyone's errand can be finished, and each
one is a different thing to do."""

from __future__ import annotations

import math
import re
import tempfile
import unittest
from pathlib import Path

from arcane.campaign import ADA, BOT, QUEEN, REQUEST, STAGES, VALERA, people_line
from arcane.folk import (
    BAD_BANS,
    CAT_PETS,
    CRON_HITS,
    CRON_PERIOD,
    ERRANDS,
    FRAME_KILLS,
    HANDSHAKE_TIME,
    LAG_ROUNDS,
    LAG_TIME,
    MINER_TRIES,
    PASSED,
    PGT_REPLY,
    PRINTER_FIXES,
    RUNNERS,
    SKIPPED,
    SPAM_USERS,
    SURPRISES,
    TROLL_SILENCE,
    TRUE_VERSION,
    Exam,
    Talk,
)
from arcane.folk_data import PEOPLE, PERSON_BY_KEY
from arcane.game import TICK_RATE
from arcane.life import RESIDENTS
from arcane.party import PEOPLE_RELIEF, PLAYING, Party
from arcane.profiles import ProfileStore
from arcane.story import StoryArena

TICK = 1 / TICK_RATE
TOKEN = "a" * 32
OTHER = "b" * 32
ORDINARY = [stage for stage in STAGES if not stage.is_boss]


def stage_of(person) -> int:
    """The ordinary stage this person is meant for."""

    chapter = [stage for stage in ORDINARY if stage.chapter_index == person.chapter]
    return chapter[person.position].index


class Scene:
    """One mage, one person, nobody else, and the means to talk to them."""

    def __init__(self, key: str, seed: int = 3, mages: int = 1) -> None:
        person = PERSON_BY_KEY[key]
        self.person = person
        self.arena = StoryArena(STAGES[stage_of(person)], mages, seed=seed, now=1.0, folk_known={})
        self.mages = [self.arena.add_player(f"Маг {index + 1}") for index in range(mages)]
        self.mage = self.mages[0]
        for mage in self.mages:
            mage.invuln_until = 1e9
        self.folk = self.arena.folk
        self.quest = self.arena.quest
        for monster in list(self.arena.monsters.values()):
            self.arena.remove_monster(monster)
        self.errand = next((e for e in self.folk.errands if e.person.key == key), None)
        if self.errand is None:
            room = next(r for r in self.arena.dungeon.path if r.kind == "combat")
            self.errand = self.folk.summon(key, room)
        # Nothing but this errand: a locked fight room would change what the test is about.
        for room in self.arena.dungeon.rooms:
            self.arena.cleared_rooms.add(room.index)
        self.arena.revealed = {room.index for room in self.arena.dungeon.rooms}
        self.life_off()
        self.go_to(self.errand.thing)
        self.events: list[dict] = []
        self.arena.drain_events()

    def life_off(self) -> None:
        self.arena.life.next_event = 1e12

    def go_to(self, thing, dx: float = 0.0, dy: float = 50.0, mage=None) -> None:
        mage = mage or self.mage
        mage.x, mage.y = thing.x + dx, thing.y + dy

    def advance(self, seconds: float) -> None:
        for _ in range(max(1, round(seconds * TICK_RATE))):
            self.arena.update(self.arena.now + TICK)
            self.events.extend(self.arena.drain_events())

    def press_e(self, thing=None, mage=None) -> dict:
        mage = mage or self.mage
        if thing is not None:
            self.go_to(thing, dy=0.0, mage=mage)
        result = self.arena.interact(mage.id)
        self.events.extend(self.arena.drain_events())
        return result

    def last_talk(self, mage=None) -> dict | None:
        mage = mage or self.mage
        for event in reversed(self.events):
            if event["e"] == "npc_talk" and event["to"] == mage.id:
                return event
        return None

    def say(self, key: str, mage=None) -> dict:
        mage = mage or self.mage
        talk = self.last_talk(mage)
        result = self.arena.npc_reply(mage.id, talk["thing"], key)
        self.events.extend(self.arena.drain_events())
        return result

    def start(self) -> None:
        self.press_e(self.errand.thing)
        talk = self.last_talk()
        assert talk is not None, self.person.key
        assert ["start", self.person.accept] in talk["replies"], talk
        self.say("start")

    def done(self) -> bool:
        return self.errand.finished

    def cast(self, code: str, aim: float = 0.0, mage=None) -> dict:
        mage = mage or self.mage
        mage.cast_ready_at = 0.0
        mage.mana = mage.max_mana
        mage.skill_ready = {}
        for key in list(getattr(mage, "rune_ready", {})):
            mage.rune_ready[key] = 0.0
        result = self.arena.cast(mage.id, code, 0, aim)
        self.events.extend(self.arena.drain_events())
        return result

    def hit(self, thing, kind: str) -> None:
        """A spell landing on something an errand made shootable."""

        prop = next(prop for prop, owner in self.errand.bodies if owner is thing)
        self.arena.terrain.prop_hit(prop, self.mage, kind)
        self.events.extend(self.arena.drain_events())


class EveryoneTests(unittest.TestCase):
    def test_every_person_has_an_errand_and_every_errand_its_own_verb(self) -> None:
        self.assertEqual(set(ERRANDS), set(PERSON_BY_KEY))
        self.assertEqual(len(set(ERRANDS.values())), len(ERRANDS), "two people play the same")

    def test_each_is_a_different_test_case(self) -> None:
        tests = [person.test for person in PEOPLE]
        self.assertEqual(len(tests), len(set(tests)))
        for person in PEOPLE:
            self.assertTrue(person.test.startswith("test_"), person.key)

    def test_nobody_is_left_without_words(self) -> None:
        for person in PEOPLE:
            for text in (person.intro, person.accept, person.thanks, person.pgt_line, person.epilogue):
                self.assertTrue(text, person.key)
            self.assertGreaterEqual(len(person.chatter), 3, person.key)

    def test_chatter_fits_over_a_head(self) -> None:
        for person in PEOPLE:
            for line in person.chatter:
                self.assertLessEqual(len(line), 70, line)

    def test_chapters_have_someone_for_every_stage(self) -> None:
        for stage in ORDINARY:
            people = [p for p in PEOPLE if p.chapter == stage.chapter_index and p.position == stage.number - 1]
            self.assertTrue(people, stage.title)

    def test_every_stage_has_two_people_on_first_arrival(self) -> None:
        for stage in ORDINARY:
            arena = StoryArena(stage, 1, seed=5, now=1.0)
            self.assertEqual(len(arena.folk.errands), 2, stage.title)
            keys = [errand.person.key for errand in arena.folk.errands]
            self.assertEqual(len(set(keys)), 2)
            here = [p.key for p in PEOPLE if p.chapter == stage.chapter_index and p.position == stage.number - 1]
            self.assertIn(keys[0], here)

    def test_a_first_playthrough_meets_everybody(self) -> None:
        met: set[str] = set()
        known: dict[str, str] = {}
        for stage in ORDINARY:
            arena = StoryArena(stage, 1, seed=5, now=1.0, folk_known=known)
            for errand in arena.folk.errands:
                met.add(errand.person.key)
                known[errand.person.key] = PASSED
        self.assertEqual(met, set(PERSON_BY_KEY))

    def test_people_stand_on_floor_and_never_in_a_trap_or_behind_the_exit(self) -> None:
        for stage in ORDINARY:
            for seed in range(6):
                arena = StoryArena(stage, 1, seed=seed, now=1.0)
                for errand in arena.folk.errands:
                    thing = errand.thing
                    self.assertTrue(arena.can_stand(thing.x, thing.y, 20.0), (stage.title, seed))
                    self.assertNotIn(arena.dungeon.rooms[thing.room].kind, ("exit", "trap", "secret", "boss"))

    def test_walking_up_to_someone_means_talking_to_them(self) -> None:
        """A chest or a neighbour beside them must not answer instead."""

        for stage in ORDINARY:
            for seed in range(8):
                arena = StoryArena(stage, 1, seed=seed, now=1.0)
                mage = arena.add_player("Маг")
                for errand in arena.folk.errands:
                    thing = errand.thing
                    mage.x, mage.y = thing.x + 30, thing.y + 56
                    arena.drain_events()
                    arena.interact(mage.id)
                    talks = [e for e in arena.drain_events() if e["e"] == "npc_talk"]
                    self.assertEqual(len(talks), 1, (stage.title, seed, errand.person.key))
                    arena.folk.offered.clear()

    def test_no_people_on_boss_stages_or_on_shift(self) -> None:
        boss = next(stage for stage in STAGES if stage.is_boss)
        self.assertIsNone(StoryArena(boss, 1, seed=1, now=1.0).folk)
        self.assertIsNone(StoryArena(ORDINARY[0], 1, seed=1, now=1.0, duty=2).folk)

    def test_each_can_be_started_and_written_off_on_any_seed(self) -> None:
        """Set up on every map, not just the convenient one, nothing throws."""

        for person in PEOPLE:
            for seed in (1, 2, 3, 4):
                scene = Scene(person.key, seed=seed)
                scene.start()
                scene.advance(1.0)
                self.assertTrue(scene.errand.started or person.key == "semyon", person.key)
                self.assertIsNotNone(scene.errand.status() is not None)

    def test_everyone_stays_put_for_a_whole_stage_without_a_mage_near(self) -> None:
        for person in PEOPLE:
            scene = Scene(person.key)
            scene.mage.x, scene.mage.y = scene.arena.dungeon.rooms[0].center
            before = (scene.errand.thing.x, scene.errand.thing.y)
            scene.advance(2.0)
            self.assertEqual((scene.errand.thing.x, scene.errand.thing.y), before, person.key)


class TalkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scene = Scene("webmaster")

    def test_the_first_talk_offers_help_the_button_and_later(self) -> None:
        self.scene.press_e(self.scene.errand.thing)
        talk = self.scene.last_talk()
        self.assertEqual(talk["name"], "Вебмастер Геннадий")
        self.assertIn(["pgt", PGT_REPLY], talk["replies"])
        self.assertIn(["later", "Потом"], talk["replies"])

    def test_only_what_was_offered_can_be_answered(self) -> None:
        scene = self.scene
        thing = scene.errand.thing
        self.assertFalse(scene.arena.npc_reply(scene.mage.id, thing.id, "start")["ok"], "nothing was asked yet")
        scene.press_e(thing)
        self.assertFalse(scene.arena.npc_reply(scene.mage.id, thing.id, "win")["ok"])
        self.assertFalse(scene.errand.started)
        self.assertTrue(scene.arena.npc_reply(scene.mage.id, thing.id, "start")["ok"])
        self.assertTrue(scene.errand.started)

    def test_the_same_reply_is_not_accepted_twice(self) -> None:
        scene = self.scene
        thing = scene.errand.thing
        scene.press_e(thing)
        scene.arena.npc_reply(scene.mage.id, thing.id, "pgt")
        self.assertFalse(scene.arena.npc_reply(scene.mage.id, thing.id, "pgt")["ok"])

    def test_one_cannot_answer_from_across_the_map(self) -> None:
        scene = self.scene
        thing = scene.errand.thing
        scene.press_e(thing)
        scene.mage.x += 2000
        self.assertFalse(scene.arena.npc_reply(scene.mage.id, thing.id, "start")["ok"])
        self.assertFalse(scene.errand.started)

    def test_walking_off_ends_the_conversation(self) -> None:
        scene = self.scene
        scene.press_e(scene.errand.thing)
        scene.mage.x += 2000
        scene.advance(0.1)
        self.assertTrue(any(e["e"] == "npc_close" for e in scene.events))

    def test_someone_else_cannot_answer_for_you(self) -> None:
        scene = Scene("webmaster", mages=2)
        scene.press_e(scene.errand.thing)
        thing = scene.errand.thing
        scene.go_to(thing, mage=scene.mages[1])
        self.assertFalse(scene.arena.npc_reply(scene.mages[1].id, thing.id, "start")["ok"])

    def test_later_closes_and_leaves_them_waiting(self) -> None:
        scene = self.scene
        scene.press_e(scene.errand.thing)
        scene.say("later")
        self.assertFalse(scene.errand.started)
        self.assertEqual(scene.events[-1]["e"], "npc_close")

    def test_they_talk_only_when_someone_is_near(self) -> None:
        scene = self.scene
        thing = scene.errand.thing
        scene.advance(0.1)
        self.assertTrue(thing.view()["say"])
        scene.mage.x += 2000
        scene.advance(0.1)
        self.assertNotIn("say", thing.view())

    def test_a_mark_says_how_things_stand(self) -> None:
        scene = self.scene
        thing = scene.errand.thing
        self.assertEqual(thing.view()["mark"], "!")
        scene.start()
        self.assertEqual(thing.view()["mark"], "…")
        scene.errand.complete()
        self.assertEqual(thing.view()["mark"], "✓")

    def test_meeting_someone_counts_for_the_ticket(self) -> None:
        scene = self.scene
        scene.press_e(scene.errand.thing)
        scene.press_e(scene.errand.thing)
        self.assertEqual(scene.arena.stats.residents, 1)

    def test_a_running_errand_shows_on_the_hud(self) -> None:
        scene = self.scene
        self.assertEqual(scene.folk.snapshot()["active"], [])
        scene.start()
        entry = scene.folk.snapshot()["active"][0]
        self.assertEqual(entry["name"], "Вебмастер Геннадий")
        self.assertTrue(entry["text"])


class FaceTests(unittest.TestCase):
    """Whoever opens their mouth has a face: a missing one falls back to a bare terminal."""

    @staticmethod
    def faces() -> set[str]:
        source = (Path(__file__).parent.parent / "public" / "js" / "portraits.js").read_text(encoding="utf-8")
        return set(re.findall(r"^  (\w+): \{$", source, re.MULTILINE))

    def test_everyone_with_a_story_has_a_portrait(self) -> None:
        faces = self.faces()
        for person in PEOPLE:
            self.assertIn(person.sprite, faces, person.key)
        self.assertIn("sensor", faces, "Tolya talks too")

    def test_the_regulars_have_portraits(self) -> None:
        faces = self.faces()
        for resident in RESIDENTS.values():
            self.assertIn(resident.sprite, faces, resident.title)

    def test_the_story_speakers_are_mapped_to_real_portraits(self) -> None:
        source = (Path(__file__).parent.parent / "public" / "js" / "story.js").read_text(encoding="utf-8")
        table = source[source.index("const SPEAKER_FACES = {"):source.index("const MACHINE_TAGS = {")]
        mapped = set(re.findall(r': "(\w+)",', table))
        self.assertTrue(mapped)
        self.assertLessEqual(mapped, self.faces())
        for name in (ADA, BOT, VALERA, QUEEN, REQUEST):
            self.assertIn(name, table)
        for resident in RESIDENTS.values():
            self.assertIn(resident.title, table)

    def test_a_conversation_says_whose_face_to_show(self) -> None:
        scene = Scene("zina")
        scene.press_e(scene.errand.thing)
        self.assertEqual(scene.last_talk()["sprite"], "modem")

    def test_his_partner_speaks_with_his_own_face(self) -> None:
        scene = Scene("semyon")
        scene.press_e(scene.errand.partner)
        self.assertEqual(scene.last_talk()["sprite"], "sensor")

    def test_the_regulars_talk_in_the_same_panel(self) -> None:
        scene = Scene("calc")
        resident = next(thing for thing in scene.arena.life.residents if thing.data["resident"] == "atm") if any(
            thing.data["resident"] == "atm" for thing in scene.arena.life.residents
        ) else None
        if resident is None:
            room = scene.arena.dungeon.rooms[0]
            scene.arena.life._add_resident("atm", room)
            resident = scene.arena.life.residents[-1]
        scene.press_e(resident)
        talk = scene.last_talk()
        self.assertEqual(talk["sprite"], "atm")
        self.assertEqual(talk["replies"], [])
        self.assertFalse(any(e["e"] == "radio" for e in scene.events), "not over the radio")

    def test_the_regulars_also_talk_on_a_shift_where_nobody_else_lives(self) -> None:
        arena = StoryArena(ORDINARY[0], 1, seed=3, now=1.0, duty=2)
        mage = arena.add_player("Маг")
        self.assertIsNone(arena.folk)
        thing = arena.life.residents[0]
        mage.x, mage.y = thing.x, thing.y
        arena.drain_events()
        arena.interact(mage.id)
        self.assertTrue(any(e["e"] == "npc_talk" for e in arena.drain_events()))


class PaymentTests(unittest.TestCase):
    def test_finishing_pays_and_is_remembered(self) -> None:
        scene = Scene("calc")
        before = scene.arena.essence
        scene.errand.finish()
        self.assertGreater(scene.arena.essence, before)
        self.assertEqual(scene.folk.take_finished(), [("calc", PASSED)])
        self.assertEqual(scene.folk.take_finished(), [])

    def test_a_find_comes_with_some_thanks(self) -> None:
        scene = Scene("zina")
        scene.errand.finish()
        self.assertIn("coffee", scene.arena.life.taken)

    def test_the_button_pays_but_passes_nothing_and_says_so(self) -> None:
        scene = Scene("zina")
        scene.press_e(scene.errand.thing)
        result = scene.say("pgt")
        self.assertTrue(result["accepted"])
        self.assertTrue(scene.errand.finished)
        self.assertEqual(scene.folk.take_finished(), [("zina", SKIPPED)])
        self.assertEqual(scene.arena.life.taken, [], "no thanks for that")
        self.assertEqual(scene.last_talk()["text"], scene.person.pgt_line)

    def test_a_person_already_helped_can_be_visited_for_half(self) -> None:
        stage = STAGES[stage_of(PERSON_BY_KEY["calc"])]
        known = {p.key: PASSED for p in PEOPLE if p.chapter == 0}
        arena = StoryArena(stage, 1, seed=3, now=1.0, folk_known=known)
        errand = next(e for e in arena.folk.errands if e.person.key == "calc")
        self.assertTrue(errand.repeat)
        self.assertEqual(errand.thing.view()["mark"], "?")
        before = arena.essence
        errand.finish()
        self.assertEqual(arena.essence - before, round(arena.folk.tokens / 2))
        self.assertEqual(arena.folk.take_finished(), [], "no second green test")

    def test_who_was_skipped_comes_back_but_without_the_button(self) -> None:
        stage = STAGES[stage_of(PERSON_BY_KEY["calc"])]
        arena = StoryArena(stage, 1, seed=3, now=1.0, folk_known={"calc": SKIPPED})
        mage = arena.add_player("Маг")
        errand = next(e for e in arena.folk.errands if e.person.key == "calc")
        self.assertNotIn("pgt", [key for key, _ in errand.opening(mage).replies])


class ErrandTests(unittest.TestCase):
    """Each person, played through by what that person really asks for."""

    def test_calculator(self) -> None:
        scene = Scene("calc")
        scene.start()
        plus = scene.errand.plus
        scene.go_to(plus, dy=0.0)
        scene.advance(0.1)
        self.assertTrue(plus.gone)
        scene.press_e(scene.errand.thing)
        self.assertEqual({key for key, _ in scene.last_talk()["replies"]}, {"four", "five", "depends"})
        scene.say("five")
        self.assertTrue(scene.done())

    def test_calculator_key_can_be_found_before_asking(self) -> None:
        scene = Scene("calc")
        scene.go_to(scene.errand.plus, dy=0.0)
        scene.advance(0.1)
        scene.press_e(scene.errand.thing)
        scene.say("four")
        self.assertTrue(scene.done())

    def test_modem_wants_stillness(self) -> None:
        scene = Scene("zina")
        scene.start()
        scene.go_to(scene.errand.thing, dy=40.0)
        scene.advance(HANDSHAKE_TIME * 0.6)
        self.assertFalse(scene.done())
        progress = scene.errand.progress
        self.assertGreater(progress, 0)
        scene.mage.x += 10
        scene.advance(0.1)
        self.assertLess(scene.errand.progress, progress, "someone picked up the phone")
        scene.advance(HANDSHAKE_TIME + 0.2)
        self.assertTrue(scene.done())

    def test_modem_is_interrupted_by_a_spell(self) -> None:
        scene = Scene("zina")
        scene.start()
        scene.go_to(scene.errand.thing, dy=40.0)
        scene.advance(2.0)
        self.assertTrue(scene.cast("fireball(0)")["ok"])
        scene.advance(0.05)
        self.assertLess(scene.errand.progress, 0.5)

    def test_modem_waits_for_someone_in_the_circle(self) -> None:
        scene = Scene("zina")
        scene.start()
        scene.mage.x += 800
        scene.advance(HANDSHAKE_TIME + 1)
        self.assertFalse(scene.done())

    def test_webmaster_reads_what_your_spell_prints(self) -> None:
        scene = Scene("webmaster")
        scene.start()
        self.assertTrue(scene.cast('log("Классный сайт")')["ok"])
        self.assertEqual(scene.errand.round, 1)
        self.assertIn("Классный сайт", scene.errand.thing.view()["say"])
        scene.cast('log("пять")')
        self.assertEqual(scene.errand.round, 1, "that is not eight")
        scene.cast("log(7 + 1)")
        self.assertEqual(scene.errand.round, 2)
        scene.cast('log("один")')
        self.assertEqual(scene.errand.round, 2, "one line is not a crowd")
        scene.cast('log("а")\nlog("б")\nlog("в")')
        self.assertTrue(scene.done())

    def test_webmaster_does_not_hear_you_from_afar(self) -> None:
        scene = Scene("webmaster")
        scene.start()
        scene.mage.x += 2000
        scene.cast('log("привет")')
        self.assertEqual(scene.errand.round, 0)

    def test_node_modules_are_caught_by_touching(self) -> None:
        scene = Scene("gosha1")
        scene.start()
        self.assertEqual(len(scene.errand.parts), len(RUNNERS))
        for part in list(scene.errand.parts):
            scene.go_to(part, dy=0.0)
            scene.advance(0.1)
        self.assertTrue(scene.done())

    def test_node_modules_run_and_stay_in_the_room(self) -> None:
        scene = Scene("gosha1")
        scene.start()
        part = scene.errand.parts[0]
        place = (part.x, part.y)
        scene.go_to(part, dx=120.0, dy=0.0)
        scene.advance(1.0)
        self.assertNotEqual((part.x, part.y), place)
        scene.advance(6.0)
        for runner in scene.errand.parts:
            self.assertTrue(scene.errand.room.holds(runner.x, runner.y, 0.5))
            self.assertTrue(scene.arena.can_stand(runner.x, runner.y, 10.0))

    def test_the_troll_starves_on_silence_and_grows_on_spells(self) -> None:
        scene = Scene("troll")
        scene.start()
        scene.advance(TROLL_SILENCE * 0.8)
        self.assertFalse(scene.done())
        scene.cast("fireball(0)")
        self.assertEqual(scene.errand.silence, 0.0)
        self.assertGreater(scene.errand.thing.view()["size"], 1.0)
        scene.advance(TROLL_SILENCE + 0.2)
        self.assertTrue(scene.done())
        self.assertTrue(scene.errand.thing.gone, "he went off to another thread")

    def test_the_troll_follows_you_and_silence_needs_an_audience(self) -> None:
        scene = Scene("troll")
        scene.start()
        scene.mage.x += 300
        start = math.hypot(scene.errand.thing.x - scene.mage.x, scene.errand.thing.y - scene.mage.y)
        scene.advance(2.0)
        self.assertLess(math.hypot(scene.errand.thing.x - scene.mage.x, scene.errand.thing.y - scene.mage.y), start)
        scene.mage.x += 3000
        silence = scene.errand.silence
        scene.advance(2.0)
        self.assertEqual(scene.errand.silence, silence)

    def test_chain_letter_goes_round_the_neighbours(self) -> None:
        scene = Scene("babka")
        scene.start()
        need = scene.errand.need
        self.assertGreaterEqual(need, 2)
        others = scene.errand._others()
        self.assertTrue(all(thing.view()["use"] == "переслать письмо счастья" for thing in others))
        for thing in others[:need]:
            scene.press_e(thing)
        self.assertTrue(scene.done())
        self.assertFalse(any("use" in thing.data["view"] for thing in others))

    def test_chain_letter_also_reaches_those_out_of_their_own_business(self) -> None:
        scene = Scene("babka")
        resident = scene.arena.life.residents[0]
        scene.start()
        resident.on = True
        scene.press_e(resident)
        self.assertEqual(len(scene.errand.told), 1)

    def test_cat_has_to_be_frozen_first(self) -> None:
        scene = Scene("cat")
        scene.start()
        cat = scene.errand.thing
        scene.go_to(cat, dy=30.0)
        scene.press_e()
        self.assertEqual(scene.errand.pets, 0, "it is gone before your hand arrives")
        for number in range(1, CAT_PETS + 1):
            scene.errand.wary_until = 0.0
            scene.hit(cat, "frost")
            self.assertTrue(cat.view()["frozen"])
            scene.go_to(cat, dy=30.0)
            scene.press_e()
            self.assertEqual(scene.errand.pets, number)
        self.assertTrue(scene.done())

    def test_cat_shakes_off_the_cold_after_being_petted(self) -> None:
        scene = Scene("cat")
        scene.start()
        cat = scene.errand.thing
        scene.hit(cat, "frost")
        scene.press_e(cat)
        self.assertEqual(scene.errand.pets, 1)
        scene.hit(cat, "frost")
        self.assertNotIn("frozen", cat.view(), "not so soon")

    def test_cat_runs_faster_than_a_mage_and_follows_only_once_won(self) -> None:
        scene = Scene("cat")
        scene.start()
        cat = scene.errand.thing
        scene.go_to(cat, dx=100.0, dy=0.0)
        place = cat.x, cat.y
        scene.advance(0.5)
        self.assertNotEqual((cat.x, cat.y), place)
        scene.errand.pets = CAT_PETS
        scene.errand.complete()
        scene.mage.x += 500
        before = math.hypot(cat.x - scene.mage.x, cat.y - scene.mage.y)
        scene.advance(1.0)
        self.assertLess(math.hypot(cat.x - scene.mage.x, cat.y - scene.mage.y), before)

    def test_fire_only_offends_the_cat(self) -> None:
        scene = Scene("cat")
        scene.start()
        scene.hit(scene.errand.thing, "fire")
        self.assertNotIn("frozen", scene.errand.thing.view())

    def test_blogger_counts_only_kills_in_frame(self) -> None:
        scene = Scene("senya")
        scene.start()
        frame = scene.errand.frame
        for number in range(1, FRAME_KILLS + 1):
            monster = scene.arena.spawn_monster(scene.arena.stage.roster[0], frame.x, frame.y)
            scene.arena._kill(monster, scene.mage, "fire")
            self.assertEqual(scene.errand.views, number)
        self.assertTrue(scene.done())

    def test_blogger_ignores_kills_out_of_frame_and_keeps_the_bugs_coming(self) -> None:
        scene = Scene("senya")
        scene.start()
        frame = scene.errand.frame
        room = scene.errand.room
        scene.advance(5.0)
        self.assertTrue(any(m.quest == "folk" for m in scene.arena.monsters.values()), "bugs come to a show")
        far = room.x * 48 + 30 if abs(frame.x - (room.x * 48 + 30)) > scene.errand.width / 2 else (room.x + room.w) * 48 - 30
        monster = scene.arena.spawn_monster(scene.arena.stage.roster[0], far, frame.y)
        scene.arena._kill(monster, scene.mage, "fire")
        self.assertEqual(scene.errand.views, 0)

    def test_moderator_bans_by_name(self) -> None:
        scene = Scene("petrovich")
        scene.start()
        spam = [part for part in scene.errand.parts if part.data["spam"]]
        honest = [part for part in scene.errand.parts if not part.data["spam"]]
        self.assertEqual(len(spam), len(SPAM_USERS))
        self.assertTrue(all(part.label in SPAM_USERS for part in spam))
        scene.hit(honest[0], "fire")
        self.assertEqual(scene.errand.mistakes, 1)
        self.assertFalse(honest[0].gone, "the person only complains")
        for part in spam:
            scene.hit(part, "fire")
        self.assertTrue(scene.done())

    def test_moderator_starts_over_after_too_many_wrong_bans(self) -> None:
        scene = Scene("petrovich")
        scene.start()
        honest = [part for part in scene.errand.parts if not part.data["spam"]]
        for part in honest[:BAD_BANS]:
            scene.hit(part, "fire")
        self.assertFalse(scene.errand.started)
        self.assertFalse(scene.done())
        self.assertEqual(scene.errand.parts, [])
        scene.start()
        self.assertEqual(scene.errand.mistakes, 0)
        self.assertTrue(scene.errand.parts)

    def test_moderator_crowd_is_not_a_list_of_enemies(self) -> None:
        scene = Scene("petrovich")
        scene.start()
        self.assertEqual(scene.arena.foes_for(scene.mage.id), [])

    def test_recommender_wants_the_unexpected(self) -> None:
        scene = Scene("rec")
        scene.start()
        order = ["fireball(0)", "frostbolt(0)", "nova()", "fireball(0)", "frostbolt(0)"]
        for number, code in enumerate(order, 1):
            self.assertTrue(scene.cast(code)["ok"], code)
            self.assertEqual(scene.errand.streak if number < SURPRISES else SURPRISES, number)
        self.assertTrue(scene.done())

    def test_recommender_sees_the_same_rune_coming(self) -> None:
        scene = Scene("rec")
        scene.start()
        scene.cast("fireball(0)")
        scene.cast("frostbolt(0)")
        self.assertEqual(scene.errand.streak, 2)
        scene.cast("fireball(0)")
        self.assertEqual(scene.errand.streak, 0)
        self.assertIn("fireball", scene.errand.thing.view()["say"])

    def test_recommender_does_not_count_a_failed_spell(self) -> None:
        scene = Scene("rec")
        scene.start()
        scene.cast("nope()")
        self.assertEqual(scene.errand.streak, 0)

    def test_env_leak_is_a_race(self) -> None:
        scene = Scene("gosha2")
        scene.start()
        switches = list(scene.errand.parts)
        self.assertEqual(len(switches), 3)
        for switch in switches:
            scene.press_e(switch)
        self.assertTrue(scene.done())

    def test_env_leak_time_runs_out_and_can_be_tried_again(self) -> None:
        scene = Scene("gosha2")
        scene.start()
        limit = scene.errand.limit
        scene.press_e(scene.errand.parts[0])
        scene.advance(limit + 0.5)
        self.assertFalse(scene.done())
        self.assertEqual(scene.errand.parts, [])
        scene.press_e(scene.errand.thing)
        switches = list(scene.errand.parts)
        self.assertEqual(len(switches), 3, "a fresh set")
        self.assertFalse(any(part.on for part in switches))

    def test_env_leak_gives_enough_time_to_walk_it(self) -> None:
        for seed in range(6):
            scene = Scene("gosha2", seed=seed)
            scene.start()
            walk = 0.0
            last = (scene.errand.thing.x, scene.errand.thing.y)
            for part in scene.errand.parts:
                walk += scene.quest._path_tiles(last, (part.x, part.y)) * 48
                last = (part.x, part.y)
            self.assertGreater(scene.errand.limit, walk / 238.0)

    def test_versions_only_the_latest_is_real(self) -> None:
        scene = Scene("diplom")
        scene.start()
        wrong = next(part for part in scene.errand.parts if part.data["date"] != TRUE_VERSION)
        scene.press_e(wrong)
        self.assertTrue(wrong.gone)
        self.assertFalse(scene.done())
        real = next(part for part in scene.errand.parts if part.data["date"] == TRUE_VERSION)
        scene.press_e(real)
        self.assertTrue(scene.done())

    def test_versions_the_true_date_really_is_the_latest(self) -> None:
        from arcane.folk import VERSIONS

        def order(date: str) -> tuple[int, int, int, int]:
            day, time = date.split()
            d, m = day.split(".")
            h, n = time.split(":")
            return int(m), int(d), int(h), int(n)

        self.assertEqual(max(VERSIONS, key=order), TRUE_VERSION)

    def test_hot_and_cold_says_which_way_and_finds_it(self) -> None:
        scene = Scene("asya")
        scene.start()
        fx, fy = scene.errand.flower
        scene.mage.x, scene.mage.y = fx + 900, fy
        scene.advance(1.5)
        scene.events.clear()
        scene.mage.x, scene.mage.y = fx + 400, fy
        scene.advance(1.5)
        self.assertTrue(any(e["e"] == "quest_note" and "Теплее" in e["text"] for e in scene.events))
        scene.events.clear()
        scene.mage.x, scene.mage.y = fx + 1300, fy
        scene.advance(1.5)
        self.assertTrue(any(e["e"] == "quest_note" and "Холоднее" in e["text"] for e in scene.events))
        scene.mage.x, scene.mage.y = fx + 30, fy
        scene.advance(0.1)
        self.assertTrue(scene.done())

    def test_hot_and_cold_keeps_it_off_the_map(self) -> None:
        scene = Scene("asya")
        scene.start()
        self.assertEqual(scene.errand.marks(), [])
        self.assertEqual(scene.errand.parts, [])

    def test_lag_plates_need_you_and_your_past(self) -> None:
        scene = Scene("sync")
        scene.start()
        for number in range(len(LAG_ROUNDS)):
            errand = scene.errand
            self.assertEqual(errand.round, number)
            scene.go_to(errand.gold, dy=0.0)
            scene.advance(LAG_TIME + 0.2)
            scene.go_to(errand.blue, dy=0.0)
            scene.advance(1.0)
        self.assertTrue(scene.done())

    def test_lag_plates_your_shadow_really_lags(self) -> None:
        scene = Scene("sync")
        scene.start()
        errand = scene.errand
        scene.go_to(errand.blue, dy=0.0)
        scene.advance(LAG_TIME + 0.5)
        self.assertLess(math.hypot(errand.shadow.x - errand.blue.x, errand.shadow.y - errand.blue.y), 5)
        scene.go_to(errand.gold, dy=0.0)
        scene.advance(LAG_TIME / 2)
        self.assertLess(math.hypot(errand.shadow.x - errand.blue.x, errand.shadow.y - errand.blue.y), 5)
        scene.advance(LAG_TIME)
        self.assertLess(math.hypot(errand.shadow.x - errand.gold.x, errand.shadow.y - errand.gold.y), 5)

    def test_lag_plates_are_within_a_run_on_any_map(self) -> None:
        for seed in range(10):
            scene = Scene("sync", seed=seed)
            scene.start()
            errand = scene.errand
            for _ in LAG_ROUNDS:
                walk = scene.quest._path_tiles((errand.blue.x, errand.blue.y), (errand.gold.x, errand.gold.y)) * 48
                self.assertLess(walk, 238.0 * LAG_TIME, seed)
                scene.go_to(errand.gold, dy=0.0)
                scene.advance(LAG_TIME + 0.2)
                scene.go_to(errand.blue, dy=0.0)
                scene.advance(1.0)

    def test_recycling_burn_the_junk_freeze_the_rest(self) -> None:
        scene = Scene("recycle")
        scene.start()
        for part in list(scene.errand.parts):
            scene.hit(part, part.data["sentence"])
        self.assertTrue(scene.done())

    def test_recycling_the_wrong_sentence_crawls_back(self) -> None:
        scene = Scene("recycle")
        scene.start()
        part = scene.errand.parts[0]
        wrong = "frost" if part.data["sentence"] == "fire" else "fire"
        scene.hit(part, wrong)
        self.assertFalse(part.gone)
        scene.hit(part, "nova")
        self.assertFalse(part.gone, "neither one thing nor the other")

    def test_recycling_rules_match_the_names(self) -> None:
        scene = Scene("recycle")
        scene.start()
        for part in scene.errand.parts:
            trash = part.label.endswith((".tmp", ".log", ".bak"))
            self.assertEqual(part.data["sentence"], "fire" if trash else "frost", part.label)

    def run_exam(self, key: str) -> Scene:
        """Answer every question right, whatever order it came in."""

        scene = Scene(key)
        scene.start()
        errand = scene.errand
        self.assertIsInstance(errand, Exam)
        guard = 0
        while not scene.done():
            guard += 1
            self.assertLess(guard, 40, key)
            scene.say(errand.rounds[errand.round].right)
        return scene

    def test_every_exam_can_be_passed(self) -> None:
        for key in ("gosha3", "gosha5", "grisha", "guard", "maria"):
            self.assertTrue(self.run_exam(key).done(), key)

    def test_every_exam_offers_what_it_expects(self) -> None:
        for key in ("gosha3", "gosha5", "grisha", "guard", "maria"):
            scene = Scene(key)
            scene.start()
            for question in scene.errand.rounds:
                self.assertIn(question.right, [reply for reply, _ in question.replies], (key, question.text))

    def test_reflog_a_wrong_commit_lets_something_out_and_asks_again(self) -> None:
        scene = Scene("gosha3")
        scene.start()
        scene.say("e9d1")
        self.assertFalse(scene.done())
        self.assertTrue(any(m.quest == "folk" for m in scene.arena.monsters.values()))
        scene.say("41bb")
        self.assertTrue(scene.done())

    def test_review_points_at_lines_that_are_there(self) -> None:
        scene = Scene("gosha5")
        scene.start()
        for question in scene.errand.rounds:
            count = len(question.code.splitlines())
            self.assertEqual(len(question.replies), count, question.text)

    def test_the_review_questions_really_contain_those_bugs(self) -> None:
        """Run Gosha's code: it had better be wrong the way the game says."""

        scene = Scene("gosha5")
        scene.start()
        total, adult, printing = [question.code for question in scene.errand.rounds]
        names: dict = {}
        exec(total, names)
        self.assertEqual(names["total"]([1, 2, 3]), 3, "should have been 6: line 4")
        exec(adult, names)
        self.assertFalse(names["is_adult"](18), "18 is an adult: line 2")
        with self.assertRaises(IndexError):
            exec(printing, {"print": lambda *_: None})

    def test_fact_check_claims_are_what_the_game_says_they_are(self) -> None:
        from arcane.folk import FactCheck

        checks = {
            'len("кот") вернёт 3.': len("кот") == 3,
            "[1, 2, 3][3] вернёт 3.": False,
            "range(3) это числа 1, 2, 3.": list(range(3)) == [1, 2, 3],
            "bool([]) даёт True: список же есть.": bool([]),
            "2 ** 3 равно 8.": 2 ** 3 == 8,
        }
        table = dict(FactCheck.CLAIMS)
        for claim, truth in checks.items():
            self.assertEqual(table[claim], truth, claim)

    def test_fact_check_a_wrong_answer_comes_back_later(self) -> None:
        scene = Scene("grisha")
        scene.start()
        errand = scene.errand
        count = len(errand.rounds)
        first = errand.rounds[0]
        scene.say("false" if first.right == "true" else "true")
        self.assertEqual(len(errand.rounds), count + 1)
        self.assertIs(errand.rounds[-1], first)

    def test_guard_answers_follow_the_rule_on_the_wall(self) -> None:
        from arcane.folk import Guard

        names: dict = {}
        exec(Guard.RULE, names)
        scene = Scene("guard")
        scene.start()
        by_user = {user: (port, day) for user, port, day in Guard.QUEUE}
        for question in scene.errand.rounds:
            user = question.data["user"]
            port, day = by_user[user]
            expected = "allow" if names["allow"](user, port, day) else "deny"
            self.assertEqual(question.right, expected, user)
        rights = {question.right for question in scene.errand.rounds}
        self.assertEqual(rights, {"allow", "deny"})

    def test_guard_shows_who_is_next(self) -> None:
        scene = Scene("guard")
        scene.start()
        errand = scene.errand
        self.assertEqual(errand.visitor.label, errand.rounds[0].data["user"])

    def test_maria_is_never_punished_for_and_never_gets_jargon(self) -> None:
        scene = Scene("maria")
        scene.start()
        before = len(scene.arena.monsters)
        scene.say("smtp")
        self.assertFalse(scene.done())
        self.assertEqual(scene.errand.round, 0)
        self.assertEqual(len(scene.arena.monsters), before, "nobody is punished for it")

    def test_marias_letter_reaches_ada(self) -> None:
        scene = self.run_exam("maria")
        said = [line for e in scene.events if e["e"] == "radio" for line in e["lines"]]
        self.assertTrue(any(who == "Ада" for who, _ in said))

    def test_mopping_a_wet_step_sends_you_back(self) -> None:
        scene = Scene("luba")
        scene.start()
        errand = scene.errand
        patch = errand.wet[0]
        errand.mop_at = 1e12
        scene.mage.x, scene.mage.y = patch.x, patch.y
        scene.advance(0.1)
        self.assertLess(math.hypot(scene.mage.x - errand.thing.x, scene.mage.y - errand.thing.y), 200)

    def test_mopping_bucket_there_and_back(self) -> None:
        scene = Scene("luba")
        scene.start()
        errand = scene.errand
        errand.mop_at = 1e12
        for patch in errand.wet:
            patch.x, patch.y = errand.thing.x + 900, errand.thing.y + 900
        scene.press_e(errand.bucket)
        self.assertEqual(errand.carrier, scene.mage.id)
        scene.advance(0.1)
        self.assertEqual((errand.bucket.x, errand.bucket.y), (scene.mage.x, scene.mage.y))
        scene.press_e(errand.thing)
        self.assertTrue(scene.done())

    def test_mopping_stepping_in_it_loses_the_bucket(self) -> None:
        scene = Scene("luba")
        scene.start()
        errand = scene.errand
        errand.mop_at = 1e12
        for patch in errand.wet:
            patch.x, patch.y = errand.thing.x + 900, errand.thing.y + 900
        scene.press_e(errand.bucket)
        errand.wet[0].x, errand.wet[0].y = scene.mage.x, scene.mage.y
        scene.advance(0.1)
        self.assertEqual(errand.carrier, 0)

    def test_mopping_new_wet_never_lands_on_a_mage_or_on_her(self) -> None:
        scene = Scene("luba")
        scene.start()
        errand = scene.errand
        errand.mop_at = 0.0
        for _ in range(40):
            scene.advance(0.5)
            errand.mop_at = 0.0
            for patch in errand.wet:
                self.assertGreater(math.hypot(patch.x - errand.thing.x, patch.y - errand.thing.y), 72.0)

    def test_cron_hits_only_on_time_and_in_a_row(self) -> None:
        scene = Scene("cron")
        scene.start()
        errand = scene.errand
        errand.spin = CRON_PERIOD / 2
        scene.press_e(errand.thing)
        self.assertEqual(errand.hits, 0)
        for number in range(1, CRON_HITS):
            errand.spin = 0.0
            scene.press_e(errand.thing)
            self.assertEqual(errand.hits, number)
        errand.spin = CRON_PERIOD / 2
        scene.press_e(errand.thing)
        self.assertEqual(errand.hits, 0, "in a row, or not at all")
        for _ in range(CRON_HITS):
            errand.spin = CRON_PERIOD * 3
            scene.press_e(errand.thing)
        self.assertTrue(scene.done())
        self.assertNotIn("clock", errand.thing.view())

    def test_printer_treated_by_its_error(self) -> None:
        scene = Scene("printer")
        scene.start()
        errand = scene.errand
        cures = {"frost": "frost", "fire": "fire", "shock": "spark", "shake": "nova"}
        for number in range(1, PRINTER_FIXES + 1):
            self.assertIn(errand.error[0], errand.thing.view()["say"])
            scene.hit(errand.thing, cures[errand.error[1]])
            self.assertEqual(errand.fixes, number)
        self.assertTrue(scene.done())
        self.assertFalse(errand.bodies)

    def test_printer_the_wrong_rune_prints_trouble(self) -> None:
        scene = Scene("printer")
        scene.start()
        errand = scene.errand
        wrong = "frost" if errand.error[1] != "frost" else "fire"
        scene.hit(errand.thing, wrong)
        self.assertEqual(errand.fixes, 0)
        self.assertTrue(any(m.quest == "folk" for m in scene.arena.monsters.values()))

    def play_mediator(self, choice: str) -> Scene:
        scene = Scene("semyon")
        scene.start()
        errand = scene.errand
        for _ in errand.ROUNDS:
            source, target = errand._pair()
            if not errand.carrying:
                scene.press_e(source)
            scene.press_e(target)
            scene.say(choice)
        return scene

    def test_mediator_kind_words_make_peace(self) -> None:
        scene = self.play_mediator("kind")
        self.assertTrue(scene.done())

    def test_mediator_the_plain_truth_starts_it_all_over(self) -> None:
        scene = self.play_mediator("rude")
        self.assertFalse(scene.done())
        self.assertFalse(scene.errand.started)
        self.assertTrue(any(m.quest == "folk" for m in scene.arena.monsters.values()))

    def test_mediator_tells_you_who_to_go_to(self) -> None:
        scene = Scene("semyon")
        scene.start()
        errand = scene.errand
        self.assertIn(errand.partner.label, errand.status())
        scene.press_e(errand.thing)
        self.assertEqual(scene.last_talk()["replies"], [], "he has said what he had to say")
        scene.press_e(errand.partner)
        self.assertEqual(len(scene.last_talk()["replies"]), 2)

    def test_cable_reaches_the_socket(self) -> None:
        scene = Scene("gosha4")
        scene.start()
        errand = scene.errand
        scene.press_e(errand.plug)
        self.assertEqual(errand.holder, scene.mage.id)
        scene.go_to(errand.socket, dy=0.0)
        scene.advance(0.1)
        self.assertTrue(scene.done())

    def test_cable_snaps_if_you_wander(self) -> None:
        scene = Scene("gosha4")
        scene.start()
        errand = scene.errand
        scene.press_e(errand.plug)
        scene.mage.x, scene.mage.y = errand.anchor[0] + errand.length + 200, errand.anchor[1]
        scene.advance(0.1)
        self.assertEqual(errand.holder, 0)
        self.assertEqual((errand.plug.x, errand.plug.y), errand.anchor)

    def test_cable_is_long_enough_on_any_map(self) -> None:
        for seed in range(8):
            scene = Scene("gosha4", seed=seed)
            scene.start()
            errand = scene.errand
            walk = scene.quest._path_tiles(errand.anchor, (errand.socket.x, errand.socket.y)) * 48
            self.assertGreaterEqual(errand.length, walk)

    def test_cable_can_be_put_down_and_only_once_calls_the_bugs(self) -> None:
        scene = Scene("gosha4")
        scene.start()
        errand = scene.errand
        scene.press_e(errand.plug)
        count = len(scene.arena.monsters)
        self.assertGreater(count, 0)
        scene.press_e()
        self.assertEqual(errand.holder, 0)
        scene.press_e(errand.plug)
        self.assertEqual(len(scene.arena.monsters), count)

    def test_miner_cash_out_pays_the_rate(self) -> None:
        scene = Scene("miner")
        scene.arena.essence = 100
        scene.start()
        scene.say("stake")
        errand = scene.errand
        self.assertEqual(scene.arena.essence, 100 - errand.stake)
        errand.crash_after = 100.0
        scene.advance(6.0)
        self.assertGreater(errand.rate, 1.5)
        before = scene.arena.essence
        scene.press_e(errand.thing)
        self.assertTrue(scene.done())
        self.assertGreater(scene.arena.essence, before + errand.stake)

    def test_miner_crash_takes_the_stake_and_gives_you_three_goes(self) -> None:
        scene = Scene("miner")
        scene.arena.essence = 1000
        scene.start()
        errand = scene.errand
        for attempt in range(1, MINER_TRIES + 1):
            if attempt > 1:
                scene.press_e(errand.thing)
            scene.say("stake")
            errand.crash_after = 0.1
            scene.advance(0.3)
            self.assertEqual(errand.tries, attempt)
        self.assertTrue(scene.done())

    def test_miner_will_not_take_what_you_do_not_have(self) -> None:
        scene = Scene("miner")
        scene.arena.essence = 0
        scene.start()
        scene.say("stake")
        self.assertFalse(scene.errand.running)


class RealSpellTests(unittest.TestCase):
    """Nobody may be told to use a rune that cannot actually reach them."""

    def shoot(self, scene: Scene, thing, code: str, reach: float = 120.0) -> dict:
        mage = scene.mage
        mage.x, mage.y = scene.arena.dungeon.open_near(thing.x - reach, thing.y, 18.0)
        angle = math.atan2(thing.y - mage.y, thing.x - mage.x)
        result = scene.cast(code.replace("ANGLE", repr(angle)))
        scene.advance(1.6)
        return result

    def test_every_cure_the_printer_asks_for_is_a_rune_that_reaches_it(self) -> None:
        from arcane.folk import PRINTER_ERRORS

        codes = {"frost": "frostbolt(ANGLE)", "fire": "fireball(ANGLE)", "shock": "spark_volley(ANGLE)", "shake": "nova()"}
        self.assertEqual(set(codes), {entry[1] for entry in PRINTER_ERRORS})
        for entry in PRINTER_ERRORS:
            scene = Scene("printer")
            scene.start()
            errand = scene.errand
            errand.error = entry
            reach = 80.0 if entry[1] == "shake" else 120.0
            result = self.shoot(scene, errand.thing, codes[entry[1]], reach)
            self.assertTrue(result["ok"], result)
            self.assertGreaterEqual(errand.fixes, 1, entry[0])
            self.assertIn(codes[entry[1]].split("(")[0], entry[2] + " frostbolt fireball spark_volley nova")

    def test_a_real_frostbolt_stops_the_cat(self) -> None:
        scene = Scene("cat")
        scene.start()
        errand = scene.errand
        errand.thing.data["view"].pop("frozen", None)
        scene.mage.x, scene.mage.y = scene.arena.dungeon.open_near(errand.thing.x - 330, errand.thing.y, 18.0)
        angle = math.atan2(errand.thing.y - scene.mage.y, errand.thing.x - scene.mage.x)
        scene.cast(f"frostbolt({angle})")
        scene.advance(1.2)
        self.assertGreater(errand.frozen_until, scene.arena.now)

    def test_real_runes_pass_sentence_on_files(self) -> None:
        scene = Scene("recycle")
        scene.start()
        for part in list(scene.errand.parts):
            code = "fireball(ANGLE)" if part.data["sentence"] == "fire" else "frostbolt(ANGLE)"
            self.shoot(scene, part, code, reach=90.0)
            self.assertTrue(part.gone, part.label)
        self.assertTrue(scene.done())

    def test_a_real_fireball_bans_a_spammer(self) -> None:
        scene = Scene("petrovich")
        scene.start()
        spam = next(part for part in scene.errand.parts if part.data["spam"])
        self.shoot(scene, spam, "fireball(ANGLE)", reach=70.0)
        self.assertTrue(spam.gone or scene.errand.mistakes > 0, "the shot landed on someone")

    def test_every_rune_named_in_a_status_is_known_where_it_is_asked(self) -> None:
        known = StoryArena(STAGES[stage_of(PERSON_BY_KEY["printer"])], 1, seed=1, now=1.0).known_runes
        for rune in ("frostbolt", "fireball", "spark_volley", "nova"):
            self.assertIn(rune, known)
        for key, rune in (("recycle", "frostbolt"), ("recycle", "fireball"), ("cat", "frostbolt")):
            self.assertIn(rune, StoryArena(STAGES[stage_of(PERSON_BY_KEY[key])], 1, seed=1, now=1.0).known_runes, key)


class SavingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ProfileStore(Path(self.tmp.name) / "profiles.json")
        self.party = Party("TEST", self.store)
        self.party.join(TOKEN, "Первый")

    def enter(self) -> None:
        self.party.set_ready(TOKEN, True, 1.0)
        self.assertEqual(self.party.state, PLAYING)

    def test_a_green_test_goes_to_everyone_at_the_table(self) -> None:
        self.party.join(OTHER, "Второй")
        self.party.set_ready(TOKEN, True, 1.0)
        self.party.set_ready(OTHER, True, 1.0)
        errand = self.party.world.folk.errands[0]
        errand.finish()
        self.party.tick(1.1)
        self.assertEqual(self.store.get(TOKEN).folk[errand.person.key], PASSED)
        self.assertEqual(self.store.get(OTHER).folk[errand.person.key], PASSED)

    def test_green_stays_green_when_someone_else_presses_the_button(self) -> None:
        self.store.get(TOKEN).folk["calc"] = PASSED
        self.enter()
        folk = self.party.world.folk
        folk.finished.append(("calc", SKIPPED))
        self.party.tick(1.1)
        self.assertEqual(self.store.get(TOKEN).folk["calc"], PASSED)

    def test_a_real_pass_replaces_a_skip(self) -> None:
        self.store.get(TOKEN).folk["calc"] = SKIPPED
        self.enter()
        folk = self.party.world.folk
        folk.finished.append(("calc", PASSED))
        self.party.tick(1.1)
        self.assertEqual(self.store.get(TOKEN).folk["calc"], PASSED)

    def test_someone_new_at_the_table_means_the_person_is_still_owed(self) -> None:
        self.store.get(TOKEN).folk["calc"] = PASSED
        self.party.join(OTHER, "Второй")
        self.assertEqual(self.party._known_people(), {})
        self.store.get(OTHER).folk["calc"] = SKIPPED
        self.assertEqual(self.party._known_people(), {"calc": SKIPPED})
        self.store.get(OTHER).folk["calc"] = PASSED
        self.assertEqual(self.party._known_people(), {"calc": PASSED})

    def test_who_was_helped_changes_who_turns_up(self) -> None:
        first = PEOPLE[0].key
        self.store.get(TOKEN).folk[first] = PASSED
        self.enter()
        self.assertNotIn(first, [errand.person.key for errand in self.party.world.folk.errands])

    def test_a_save_survives_and_forgets_people_who_are_gone(self) -> None:
        profile = self.store.get(TOKEN)
        profile.folk.update({"calc": PASSED, "someone_old": PASSED})
        self.store.mark()
        self.store.save()
        again = ProfileStore(self.store.path)
        self.assertEqual(again.get(TOKEN).folk, {"calc": PASSED})

    def test_an_old_save_has_nobody_yet(self) -> None:
        self.assertEqual(self.store.get("c" * 32).folk, {})

    def test_the_final_boss_is_weaker_for_everyone_helped(self) -> None:
        self.party.stage_index = len(STAGES) - 1
        self.party.set_ready(TOKEN, True, 1.0)
        plain = self.party.world.pgt_boost
        self.assertEqual(plain, 1.0)
        self.party.world = None
        self.party.state = "camp"
        for person in PEOPLE[:10]:
            self.store.get(TOKEN).folk[person.key] = PASSED
        self.store.get(TOKEN).folk[PEOPLE[11].key] = SKIPPED
        self.party.set_ready(TOKEN, True, 1.0)
        self.assertAlmostEqual(self.party.world.pgt_boost, 1 - PEOPLE_RELIEF * 10)

    def test_the_queen_reads_the_test_before_the_end(self) -> None:
        last = len(STAGES) - 1
        lines = self.party.readout(TOKEN, last)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[1], list(people_line(0, len(PEOPLE))))
        self.assertEqual(len(self.party.readout(TOKEN, 8)), 1)

    def test_people_line_covers_none_some_and_all(self) -> None:
        total = len(PEOPLE)
        self.assertIn("ноль", people_line(0, total)[1])
        self.assertIn(f"3 из {total}", people_line(3, total)[1])
        self.assertIn(f"все {total}", people_line(total, total)[1])

    def test_the_profile_reports_who_was_helped(self) -> None:
        self.store.get(TOKEN).folk["calc"] = PASSED
        self.assertEqual(self.store.get(TOKEN).describe()["folk"], {"calc": PASSED})
        self.assertEqual(self.party.describe(TOKEN)["folk"], {"calc": PASSED})


if __name__ == "__main__":
    unittest.main()
