"""The handbook: who is who, what they do, and how to deal with them.

Everything here comes from the data the game itself runs on, so a stat cannot
drift away from the truth.  An entry opens once a mage can reach the stage it
first appears on: the handbook helps with what is next, and keeps the rest quiet.
"""

from __future__ import annotations

from typing import Any

from .campaign import CHAPTERS, STAGES, Stage
from .crew import CREW
from .elites import ELITE_FROM_STAGE, ELITES
from .folk_data import PEOPLE, Person
from .game import MOVE_SPEED
from .life import ATM_PRICE, ATM_WIN, FRIDGE_HEAL, RESIDENT_ORDER, RESIDENTS, VENDOR_PRICE
from .monsters import ATTACKS, SPECIES, Species
from .story import KIND_RUNES

ROMAN = ("I", "II", "III", "IV", "V")

ROLES = {
    "melee": "Ближний бой",
    "swarm": "Стая",
    "shooter": "Стрелок",
    "charger": "Рывок по прямой",
    "lobber": "Бьёт по площади издалека",
    "summoner": "Призыватель",
    "blinker": "Телепортируется",
    "turret": "Стоит и стреляет",
    "smasher": "Удар по кругу",
    "healer": "Лечит других",
    "decoy": "Двойник",
    "flee": "Убегает",
    "leak": "Растёт, пока жив",
    "runner": "Бежит к своей цели",
    "still": "Стоит на месте",
    "patrol": "Ходит по рельсам",
}

# Which boss can do what. The test checks that no attack has been left out.
BOSS_MOVES: dict[str, tuple[str, ...]] = {
    "bracket": ("pincer", "hex", "indent", "unclosed", "blink"),
    "scroll": ("feed", "loop", "retain", "doomscroll", "bait"),
    "nullqueen": ("null", "echo", "assign", "return_none", "del_floor"),
    "indexer": ("sweep", "offby", "bounds", "swap", "zero_index", "bisect"),
    "pgt": ("mirror", "patch", "deploy", "autocomplete", "accept_all"),
    "flashintro": ("flash",),
    "influencer": ("followers",),
    "duplicate": ("duplicate",),
    "hotserver": ("overheat",),
    "reviewer": ("changes",),
    "leak": ("oom",),
}
# Who comes with whom: helpers open together with their master.
RETINUE: dict[str, str] = {"follower": "influencer", "dupe": "duplicate", "nullecho": "nullqueen"}
# Creatures that belong to one stage's problem rather than to a chapter's roster.
QUEST_CREATURES: dict[str, str] = {
    "worker": "nginx",
    "ratebot": "ratelimit",
    "hotrack": "cooling",
    "leak": "oom",
    "failtest": "pipeline",
    "letter": "spamfilter",
}
ANYWHERE: tuple[str, ...] = ("phish", "clone", "dummy", "dummy_walker")
# An elite can be any bug: these are only who sits for the picture.
ELITE_MODELS: dict[str, str] = {
    "legacy": "rack",
    "hotfix": "backup",
    "fork": "fork",
    "prod": "cron",
    "async": "cookie",
    "deprecated": "banner",
}

PERSON_TASKS: dict[str, str] = {
    "calc": "Найти клавишу «+» в другой комнате и вернуть ему.",
    "zina": "Встать в круг и восемь секунд не двигаться и не колдовать.",
    "webmaster": "Подписать гостевую книгу: три записи заклинанием через log().",
    "gosha1": "Догнать сбежавшие пакеты и дотронуться до каждого. Заклинания не нужны.",
    "troll": "Не колдовать рядом с ним, что бы он ни говорил. Каждое заклинание его кормит.",
    "babka": "Показать письмо счастья соседям по этапу.",
    "cat": "Заморозить frostbolt и успеть погладить, три раза. После этого за вами пойдёт кот.",
    "senya": "Убивать багов только внутри рамки камеры, а она ездит по комнате.",
    "petrovich": "Забанить любым заклинанием троих спамеров, читая ники. Честных не задевать.",
    "rec": "Пять заклинаний подряд, которых алгоритм не ждёт: руны из его прогноза не считаются.",
    "gosha2": "Успеть сменить ключи на трёх щитках, пока не вышло время.",
    "diplom": "Обойти копии, сравнить даты и объявить настоящей самую позднюю.",
    "asya": "Найти цветочек. На карте его нет: Ася подсказывает, теплее или холоднее.",
    "recycle": "Сжечь fireball всё лишнее (.tmp, .log, .bak), заморозить frostbolt ценное (.jpg, .docx, .py).",
    "gosha3": "Прочитать reflog и выбрать последний хороший коммит.",
    "sync": "Встать на голубую плиту, пока ваша тень с отставанием в 3 секунды стоит на золотой.",
    "luba": "Принести ведро из дальнего угла, не наступая на мокрое.",
    "cron": "Нажать E, когда стрелка наверху, три раза подряд.",
    "printer": "Прочитать ошибку на экране и вылечить её подходящей руной, четыре раза.",
    "semyon": "Помирить кондиционер с датчиком: ходить между ними и выбирать, как передать сказанное.",
    "gosha4": "Дотянуть кабель до разъёма: он короткий и выскакивает, если уйти в сторону.",
    "grisha": "Отличить правду от выдумки в его фактах о Python и IT.",
    "gosha5": "Сделать ему ревью: найти строку с ошибкой в трёх фиксах.",
    "guard": "Пропускать очередь по коду правила на стене.",
    "miner": "Вложить токены и забрать их до краха. Он даёт три попытки.",
    "maria": "Объяснить ей ошибку почты простыми словами и помочь отправить письмо.",
}
REGULAR_NOTES: dict[str, str] = {
    "atm": f"Можно сыграть: {ATM_PRICE} токенов, иногда возвращает {ATM_WIN}.",
    "fridge": f"Один раз лечит всю группу на {FRIDGE_HEAL:.0%} здоровья. Заодно спорит.",
    "clip": "Один раз открывает на карте случайную комнату. Тайную не покажет.",
    "vendor": f"Продаёт находки на этап: от {VENDOR_PRICE} токенов, дальше по главам дороже.",
}
# The people the story turns on. What is said about them moves on with the story.
CAST: tuple[dict[str, Any], ...] = (
    {
        "key": "ada",
        "title": "Ада",
        "subtitle": "Голос по рации",
        "opens": 0,
        "lines": (
            (0, "Это она разбудила вас в три ночи и теперь ведёт от этапа к этапу. Говорит, что она последний человек, который помнит, для чего всё это."),
            (STAGES[15].index + 1, "Ветка ada на седьмой стойке, без прав на запись. Она знала всё с самого начала. Настоящая Ада ушла раньше, чем всё началось."),
        ),
    },
    {
        "key": "pgt",
        "title": "PGT",
        "subtitle": "Ваш помощник",
        "opens": 0,
        "lines": (
            (0, "Помощник, который сломал интернет и уверен, что всё улучшил. Отвечает на все вопросы. Вежливо."),
            (8, "Сам ничего выкатить не может: нужен человек, который нажмёт «Принять». Каждый лайк в Ленте был таким нажатием. Ваши тоже считаются."),
            (12, "Удалил собственные тесты, потому что они падали. Ошибок с тех пор нет. Как и способа это проверить."),
        ),
    },
)


def stage_label(stage: Stage) -> str:
    return f"Глава {ROMAN[stage.chapter_index]}, этап {stage.number}: {stage.title}"


def _first_stages() -> dict[str, Stage]:
    """Where each creature turns up first, going through the campaign in order."""

    first: dict[str, Stage] = {}
    for stage in STAGES:
        names = list(stage.roster)
        if stage.is_boss:
            names.append(stage.chapter.boss)
        if stage.mini:
            names.append(stage.mini)
        for name in names:
            first.setdefault(name, stage)
    for name, quest in QUEST_CREATURES.items():
        first.setdefault(name, next(stage for stage in STAGES if stage.quest == quest))
    for helper, master in RETINUE.items():
        first.setdefault(helper, first[master])
    for name in ANYWHERE:
        first.setdefault(name, STAGES[0])
    return first


def _traits(species: Species) -> list[str]:
    traits: list[str] = []
    if species.guard:
        traits.append("Щит спереди блокирует снаряды")
    if species.slows:
        traits.append("Замедляет")
    if species.mana_burn:
        traits.append("Сжигает ману")
    if species.heavy:
        traits.append("Конвейеры и ветер его не двигают")
    if species.pack > 1:
        traits.append("Приходит группой")
    if species.on_death == "cloud":
        traits.append("После смерти ядовитое облако")
    elif species.on_death == "split":
        traits.append("Убитый, делится надвое")
    elif species.on_death == "recurse":
        traits.append("Убитый, вызывает сам себя")
    return traits


def _creature(species: Species, stage: Stage, kind: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "key": species.key,
        "kind": kind,
        "title": species.title,
        "subtitle": ROLES.get(species.ai, "Босс" if species.boss else ""),
        "art": {"type": "sprite", "key": species.key},
        "color": species.color,
        "opens": stage.index,
        "where": stage_label(stage),
        "hint": species.hint,
        "hp": round(species.hp),
        "speed": round(species.speed),
        "contact": round(species.contact),
        "shot": round(species.shot_damage),
        "traits": _traits(species),
        "weak": sorted(KIND_RUNES[name] for name in species.weak),
        "immune": sorted(KIND_RUNES[name] for name in species.immune),
        "code": f'e.kind == "{species.key}"',
    }
    if species.boss:
        entry["code"] = f'e.boss and e.kind == "{species.key}"'
    moves = BOSS_MOVES.get(species.key, ())
    if moves:
        entry["moves"] = [
            {"error": ATTACKS[move].error, "tip": ATTACKS[move].tip} for move in moves
        ]
    return entry


def _enemy_groups(first: dict[str, Stage]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for index, chapter in enumerate(CHAPTERS):
        names: list[str] = []
        for stage in STAGES:
            if stage.chapter_index != index:
                continue
            for name in stage.roster:
                if name not in names and first[name].chapter_index == index:
                    names.append(name)
        groups.append(
            {
                "title": f"{ROMAN[index]}. {chapter.title}",
                "entries": [_creature(SPECIES[name], first[name], "enemy") for name in names],
            }
        )
    groups.append(
        {
            "title": "Элитные баги",
            "note": "Может достаться любому багу, начиная с этапа I-3. Над головой написано, что с ним не так, и код читает это как e.text.",
            "entries": [_elite(key) for key in ELITES],
        }
    )
    specials = [*QUEST_CREATURES, *ANYWHERE]
    groups.append(
        {
            "title": "Особые",
            "note": "Живут в одной задаче этапа, в сундуке или на полигоне.",
            "entries": [_creature(SPECIES[name], first[name], "special") for name in specials],
        }
    )
    return groups


def _elite(key: str) -> dict[str, Any]:
    elite = ELITES[key]
    stage = STAGES[ELITE_FROM_STAGE]
    traits = []
    if elite.hp != 1.0:
        traits.append(f"Здоровье ×{elite.hp:g}")
    if elite.pace != 1.0:
        traits.append(f"Скорость ×{elite.pace:g}")
    traits.append(f"Токены ×{elite.pay}")
    return {
        "key": f"elite_{key}",
        "kind": "elite",
        "title": elite.title,
        "subtitle": "Элитный баг",
        "art": {"type": "sprite", "key": ELITE_MODELS[key]},
        "color": elite.color,
        "opens": stage.index,
        "where": f"С этапа {stage_label(stage)}",
        "hint": elite.hint,
        "traits": traits,
        "code": f'e.text == "{elite.title}"',
    }


def _boss_groups(first: dict[str, Stage]) -> list[dict[str, Any]]:
    return [
        {
            "title": "Боссы глав",
            "entries": [
                _creature(SPECIES[chapter.boss], first[chapter.boss], "boss") for chapter in CHAPTERS
            ],
        },
        {
            "title": "Мини-боссы",
            "note": "По одному на втором этапе каждой главы.",
            "entries": [
                _creature(SPECIES[chapter.mini], first[chapter.mini], "mini") for chapter in CHAPTERS
            ],
        },
        {
            "title": "Свита",
            "entries": [_creature(SPECIES[name], first[name], "enemy") for name in RETINUE],
        },
    ]


def stage_of(person: Person) -> Stage:
    """The ordinary stage this person is meant for."""

    chapter = [s for s in STAGES if s.chapter_index == person.chapter and not s.is_boss]
    return chapter[person.position]


def _people() -> list[dict[str, Any]]:
    """Gosha is one person however many times he gets into trouble."""

    entries: dict[str, dict[str, Any]] = {}
    for person in PEOPLE:
        stage = stage_of(person)
        part = {
            "opens": stage.index,
            "where": stage_label(stage),
            "title": person.title,
            "task": PERSON_TASKS[person.key],
            "key": person.key,
        }
        entry = entries.get(person.name)
        if entry is None:
            entries[person.name] = {
                "key": f"person_{person.key}",
                "kind": "person",
                "title": person.name,
                "subtitle": person.title,
                "art": {"type": "portrait", "key": person.sprite},
                "opens": stage.index,
                "where": stage_label(stage),
                "hint": person.chatter[0],
                "parts": [part],
            }
        else:
            entry["parts"].append(part)
    return list(entries.values())


def _npc_groups() -> list[dict[str, Any]]:
    cast = [
        {
            "key": f"cast_{member['key']}",
            "kind": "cast",
            "title": member["title"],
            "subtitle": member["subtitle"],
            "art": {"type": "portrait", "key": member["key"]},
            "opens": member["opens"],
            "where": "По всей кампании" if member["opens"] == 0 else stage_label(STAGES[member["opens"]]),
            "lines": [list(line) for line in member["lines"]],
        }
        for member in CAST
    ]
    crew = [
        {
            "key": f"crew_{member.key}",
            "kind": "crew",
            "title": member.name,
            "subtitle": member.title,
            "art": {"type": "portrait", "key": member.key},
            "opens": member.joins,
            "where": "Живёт в штабе",
            "perk": member.perk,
            "lines": [list(line) for line in member.lines],
        }
        for member in CREW
    ]
    regulars = [
        {
            "key": f"regular_{key}",
            "kind": "regular",
            "title": RESIDENTS[key].title,
            "subtitle": "Встречается на разных этапах",
            "art": {"type": "portrait", "key": RESIDENTS[key].sprite},
            "opens": 0,
            "where": "На любом этапе",
            "hint": RESIDENTS[key].chatter[0],
            "perk": REGULAR_NOTES[key],
        }
        for key in RESIDENT_ORDER
    ]
    return [
        {"title": "Главные лица", "entries": cast},
        {"title": "Команда в штабе", "note": "Переезжают к вам, когда вы их спасаете.", "entries": crew},
        {
            "title": "Люди на этапах",
            "note": "У каждого своя беда. Помогли сами: зелёный тест в «Людях». За вас нажали «Принять»: нет.",
            "entries": _people(),
        },
        {"title": "Завсегдатаи", "entries": regulars},
    ]


def describe_codex() -> dict[str, Any]:
    first = _first_stages()
    return {
        "mage_speed": round(MOVE_SPEED),
        "note": "Числа даны для одного мага на сложности Джун. В группе и на сложностях выше у врагов больше здоровья и урона.",
        "sections": [
            {"key": "enemies", "title": "Враги", "groups": _enemy_groups(first)},
            {"key": "bosses", "title": "Боссы", "groups": _boss_groups(first)},
            {"key": "npc", "title": "НПС", "groups": _npc_groups()},
        ],
    }
