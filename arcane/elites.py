"""Elite bugs: an ordinary bug with one thing wrong with it, named for that thing.

A title goes onto the bug's ``text``, so it shows above its head and code can read
it the same way: ``if e.text == "Хотфикс":``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .monsters import Monster
    from .story import StoryArena

ELITE_FROM_STAGE = 2
ELITE_CHANCE = 0.3
ELITE_CHANCE_PER_CHAPTER = 0.05
ELITE_CHANCE_PER_SHIFT = 0.06
HOTFIX_EVERY = 2.0
HOTFIX_REACH = 240.0
HOTFIX_SHARE = 0.08
FORK_SCALE = 0.55
PROD_RADIUS = 150.0
PROD_DELAY = 0.9
PROD_DAMAGE = 26.0
DEPRECATED_TIME = 12.0


@dataclass(frozen=True, slots=True)
class Elite:
    key: str
    title: str
    hint: str
    color: str
    hp: float = 1.0
    pace: float = 1.0
    size: float = 1.0
    pay: int = 3


ELITES: dict[str, Elite] = {
    entry.key: entry
    for entry in (
        Elite("legacy", "Легаси", "Никто не знает, как оно работает, и поэтому его не убить быстро. Втрое больше здоровья, медленный, платит щедро.", "#c9a26b", hp=3.0, pace=0.75, size=1.2, pay=5),
        Elite("hotfix", "Хотфикс", "Каждые две секунды лечит всех вокруг. Цельтесь в него первым.", "#7fe0a8", hp=1.4),
        Elite("fork", "Форк", "Убьёте одного, появятся два поменьше. Не бейте большими рунами последним.", "#b18cff", hp=1.3),
        Elite("prod", "Прод", "Когда падает, тянет за собой всё вокруг: через секунду взрыв. Добивайте издалека.", "#ff7a5a", hp=1.3),
        Elite("async", "Async", "Вдвое быстрее всех и никого не ждёт.", "#6fd3ff", hp=0.9, pace=1.9),
        Elite("deprecated", "Deprecated", "Не нападает, удирает и через 12 секунд удаляется сам. Успеете поймать, рассыплется токенами.", "#ffd86b", hp=0.7, pace=1.1, pay=14),
    )
}
_KEYS = tuple(ELITES)


def elite_chance(world: "StoryArena") -> float:
    if world.plain or world.stage.index < ELITE_FROM_STAGE and not world.duty:
        return 0.0
    return (
        ELITE_CHANCE
        + ELITE_CHANCE_PER_CHAPTER * world.stage.chapter_index
        + ELITE_CHANCE_PER_SHIFT * world.duty
    )


def crown(world: "StoryArena", monster: "Monster", key: str) -> None:
    elite = ELITES[key]
    monster.elite = key
    monster.pace = elite.pace
    monster.hp *= elite.hp
    monster.max_hp *= elite.hp
    monster.radius *= elite.size
    monster.text = elite.title
    if key == "deprecated":
        monster.state_until = world.now + DEPRECATED_TIME
    tag = f"elite_{key}"
    if tag not in world.seen_species:
        world.seen_species.add(tag)
        world.emit({"e": "intro", "kind": tag})


def maybe_crown(world: "StoryArena", wave: list["Monster"]) -> None:
    """At most one elite a wave, so that it is an event and not the weather."""

    if not wave or world.rng.random() >= elite_chance(world):
        return
    crown(world, world.rng.choice(wave), world.rng.choice(_KEYS))


def elite_tick(world: "StoryArena", monster: "Monster") -> bool:
    """Returns True if the monster is gone."""

    now = world.now
    if monster.elite == "deprecated" and now >= monster.state_until:
        world.remove_monster(monster)
        return True
    if monster.elite == "hotfix" and now >= monster.next_special:
        monster.next_special = now + HOTFIX_EVERY * world.difficulty.tempo
        for other in world.monsters.values():
            if other is monster or other.hp >= other.max_hp:
                continue
            if math.hypot(other.x - monster.x, other.y - monster.y) <= HOTFIX_REACH:
                world.mend(monster, other, other.max_hp * HOTFIX_SHARE)
    return False


def elite_died(world: "StoryArena", monster: "Monster") -> None:
    if monster.elite == "fork" and monster.generation == 0:
        for _ in range(2):
            world.spawn_near(monster, monster.species.key, 40, generation=1, scale=FORK_SCALE)
    elif monster.elite == "prod":
        world.place_hazard(
            monster, monster.x, monster.y,
            radius=PROD_RADIUS, delay=PROD_DELAY, damage=PROD_DAMAGE,
            color=ELITES["prod"].color, label="500",
        )
