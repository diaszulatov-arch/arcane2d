"""The handbook must not forget anybody, or promise a picture or a move that is not there."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from arcane.campaign import CHAPTERS, STAGES
from arcane.codex import (
    ANYWHERE,
    BOSS_MOVES,
    CAST,
    ELITE_MODELS,
    PERSON_TASKS,
    QUEST_CREATURES,
    RETINUE,
    ROLES,
    describe_codex,
)
from arcane.crew import CREW
from arcane.elites import ELITES
from arcane.folk_data import PEOPLE, PERSON_BY_KEY
from arcane.life import RESIDENTS
from arcane.monsters import ATTACKS, SPECIES

PUBLIC = Path(__file__).parent.parent / "public" / "js"
LAST = len(STAGES) - 1


def entries(section_key: str | None = None) -> list[dict]:
    found = []
    for section in describe_codex()["sections"]:
        if section_key in (None, section["key"]):
            for group in section["groups"]:
                found.extend(group["entries"])
    return found


def sprites() -> set[str]:
    source = (PUBLIC / "dungeon-art.js").read_text(encoding="utf-8")
    block = source[source.index("const SPRITES = {"):source.index("function bakeSprite")]
    names = set(re.findall(r"^  (\w+): \{$", block, re.MULTILINE))
    foes = (PUBLIC / "foe-sprites.js").read_text(encoding="utf-8")
    names |= set(re.findall(r"^  (\w+): \{$", foes, re.MULTILINE))
    return names | set(re.findall(r"^SPRITES\.(\w+) = ", block, re.MULTILINE))


def portraits() -> set[str]:
    source = (PUBLIC / "portraits.js").read_text(encoding="utf-8")
    return set(re.findall(r"^  (\w+): \{$", source, re.MULTILINE))


class EverybodyIsThereTests(unittest.TestCase):
    def test_every_creature_in_the_game_has_a_page(self) -> None:
        keys = {entry["key"] for entry in entries() if entry["kind"] in ("enemy", "boss", "mini", "special")}
        self.assertEqual(keys, set(SPECIES))

    def test_nobody_has_two_pages(self) -> None:
        keys = [entry["key"] for entry in entries()]
        self.assertEqual(len(keys), len(set(keys)))

    def test_every_boss_and_mini_boss_is_under_bosses(self) -> None:
        keys = {entry["key"] for entry in entries("bosses")}
        for chapter in CHAPTERS:
            self.assertIn(chapter.boss, keys)
            self.assertIn(chapter.mini, keys)

    def test_every_elite_is_there_with_a_model_to_show(self) -> None:
        keys = {entry["key"] for entry in entries("enemies") if entry["kind"] == "elite"}
        self.assertEqual(keys, {f"elite_{key}" for key in ELITES})
        self.assertEqual(set(ELITE_MODELS), set(ELITES))

    def test_every_npc_is_there(self) -> None:
        titles = {entry["title"] for entry in entries("npc")}
        for person in PEOPLE:
            self.assertIn(person.name, titles)
        for member in CREW:
            self.assertIn(member.name, titles)
        for resident in RESIDENTS.values():
            self.assertIn(resident.title, titles)
        for member in CAST:
            self.assertIn(member["title"], titles)

    def test_gosha_is_one_page_with_all_his_parts(self) -> None:
        gosha = next(entry for entry in entries("npc") if entry["title"] == "Стажёр Гоша")
        self.assertEqual(len(gosha["parts"]), 5)
        self.assertEqual([part["opens"] for part in gosha["parts"]], sorted(part["opens"] for part in gosha["parts"]))

    def test_everyone_has_a_task_written_down(self) -> None:
        self.assertEqual(set(PERSON_TASKS), set(PERSON_BY_KEY))
        for person in entries("npc"):
            for part in person.get("parts", []):
                self.assertTrue(part["task"], person["title"])


class FactsTests(unittest.TestCase):
    def test_every_boss_attack_is_described_exactly_once(self) -> None:
        listed = [move for moves in BOSS_MOVES.values() for move in moves]
        self.assertEqual(sorted(listed), sorted(ATTACKS))

    def test_a_boss_page_lists_its_moves_with_how_to_survive(self) -> None:
        for entry in entries("bosses"):
            if entry["kind"] in ("boss", "mini"):
                self.assertTrue(entry["moves"], entry["title"])
                for move in entry["moves"]:
                    self.assertTrue(move["error"])
                    self.assertTrue(move["tip"])

    def test_numbers_are_the_ones_the_game_runs_on(self) -> None:
        for entry in entries():
            species = SPECIES.get(entry["key"])
            if species is None:
                continue
            self.assertEqual(entry["hp"], round(species.hp))
            self.assertEqual(entry["speed"], round(species.speed))
            self.assertEqual(entry["hint"], species.hint)

    def test_every_ai_has_a_plain_word_for_it(self) -> None:
        for species in SPECIES.values():
            if not species.boss:
                self.assertIn(species.ai, ROLES, species.key)

    def test_weak_and_immune_name_runes_that_exist(self) -> None:
        source = (PUBLIC / "content.js").read_text(encoding="utf-8")
        for entry in entries():
            for rune in (*entry.get("weak", ()), *entry.get("immune", ())):
                self.assertIn(rune, source, entry["title"])

    def test_the_code_line_compares_what_the_game_really_reports(self) -> None:
        for entry in entries():
            if entry["key"] in SPECIES:
                self.assertIn(f'e.kind == "{entry["key"]}"', entry["code"])
        for key, elite in ELITES.items():
            page = next(entry for entry in entries() if entry["key"] == f"elite_{key}")
            self.assertEqual(page["code"], f'e.text == "{elite.title}"')

    def test_it_travels_as_json(self) -> None:
        self.assertTrue(json.dumps(describe_codex(), ensure_ascii=False))


class PictureTests(unittest.TestCase):
    def test_every_page_has_art_that_exists(self) -> None:
        drawn = sprites()
        faces = portraits()
        for entry in entries():
            art = entry["art"]
            self.assertIn(art["key"], drawn if art["type"] == "sprite" else faces, entry["title"])


class OpeningTests(unittest.TestCase):
    def test_every_page_opens_at_a_stage_that_exists(self) -> None:
        for entry in entries():
            self.assertTrue(0 <= entry["opens"] <= LAST + 1, entry["title"])

    def test_a_creature_opens_on_the_first_stage_it_can_be_met(self) -> None:
        for entry in entries():
            species = SPECIES.get(entry["key"])
            if species is None or entry["key"] in (*QUEST_CREATURES, *ANYWHERE, *RETINUE):
                continue
            stage = STAGES[entry["opens"]]
            met = (*stage.roster, stage.mini, stage.chapter.boss if stage.is_boss else "")
            self.assertIn(entry["key"], met, entry["title"])
            for earlier in STAGES[: entry["opens"]]:
                self.assertNotIn(entry["key"], earlier.roster)

    def test_quest_creatures_open_with_their_quest(self) -> None:
        for key, quest in QUEST_CREATURES.items():
            page = next(entry for entry in entries() if entry["key"] == key)
            self.assertEqual(STAGES[page["opens"]].quest, quest)

    def test_the_last_boss_stays_hidden_until_the_last_stage(self) -> None:
        pgt = next(entry for entry in entries("bosses") if entry["key"] == "pgt")
        self.assertEqual(pgt["opens"], LAST)

    def test_a_reveal_is_not_spoiled_before_the_story_gets_there(self) -> None:
        ada = next(entry for entry in entries("npc") if entry["key"] == "cast_ada")
        first_opening, first_words = ada["lines"][0]
        self.assertEqual(first_opening, 0)
        self.assertNotIn("ветк", first_words.lower())
        self.assertGreater(ada["lines"][1][0], 15, "only after the chapter that tells it")


if __name__ == "__main__":
    unittest.main()
