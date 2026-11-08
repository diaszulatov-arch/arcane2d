"""Tickets: what a stage still owes you after it has been cleared once.

Every stage has the same two promises to keep (nobody falls, the SLA holds), one
that is its own, and one for those who come back on Senior.  A ticket pays once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from .campaign import STAGES, Stage

if TYPE_CHECKING:
    from .story import StoryArena

SMASH_COUNT = 8
RESIDENTS_COUNT = 2
BOSS_REWARD = 2
SENIOR_REWARD = 2
SLA_MINUTES = (6.0, 7.0, 8.0, 4.0)
SLA_PER_CHAPTER = 0.5


@dataclass(slots=True)
class StageStats:
    """What the party did on this stage, as far as tickets care."""

    started: float = 0.0
    deaths: int = 0
    errors: int = 0
    hints: int = 0
    pgt: int = 0
    broken: int = 0
    residents: int = 0
    secret: bool = False
    runes: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class Check:
    title: str
    about: str
    passes: Callable[["StoryArena"], bool]


def _workshop(world: "StoryArena") -> bool:
    return world.workshop is not None and world.workshop.opened


CHECKS: dict[str, Check] = {
    "workshop": Check("Руками", "Решить задачу мастерской своим заклинанием", _workshop),
    "secret": Check("Археолог", "Найти тайную комнату за треснувшей стеной", lambda w: w.stats.secret),
    "smash": Check("Плановый снос", f"Разбить {SMASH_COUNT} мониторов и батарей", lambda w: w.stats.broken >= SMASH_COUNT),
    "residents": Check("Поддержка пользователей", f"Поговорить с {RESIDENTS_COUNT} жителями этапа", lambda w: w.stats.residents >= RESIDENTS_COUNT),
    "clean": Check("Чистые логи", "Ни одной ошибки в заклинаниях за весь этап", lambda w: w.stats.errors == 0),
    "no_fire": Check("Без огня", "Ни разу не сотворить fireball", lambda w: "fireball" not in w.stats.runes),
    "no_heal": Check("Без отката", "Ни разу не сотворить heal", lambda w: "heal" not in w.stats.runes),
    "no_hints": Check("Сам", "Не брать подсказок в терминале и не принимать помощь PGT", lambda w: not w.stats.hints and not w.stats.pgt),
}

# Whatever fits the stage: a boss has no workshop to solve, a first stage no fire to refuse.
OWN_CHECK: tuple[str, ...] = (
    "workshop", "secret", "smash", "no_hints",
    "clean", "workshop", "residents", "clean",
    "no_fire", "secret", "smash", "no_fire",
    "workshop", "clean", "secret", "no_heal",
    "no_hints", "residents", "no_fire", "clean",
)


@dataclass(frozen=True, slots=True)
class Ticket:
    key: str
    stage: int
    title: str
    about: str
    reward: int
    passes: Callable[["StoryArena"], bool]

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "stage": self.stage,
            "title": self.title,
            "about": self.about,
            "reward": self.reward,
        }


def sla_minutes(stage: Stage) -> float:
    return SLA_MINUTES[stage.number - 1] + SLA_PER_CHAPTER * stage.chapter_index


def _tickets_of(stage: Stage) -> tuple[Ticket, ...]:
    base = 20 + 8 * stage.chapter_index
    if stage.is_boss:
        base *= BOSS_REWARD
    minutes = sla_minutes(stage)
    limit = minutes * 60
    own = CHECKS[OWN_CHECK[stage.index]]
    entries = (
        ("clean_run", "Без падений", "Никто из группы не упал", base, lambda w: w.stats.deaths == 0),
        ("sla", f"SLA {minutes:g} мин", f"Закрыть этап быстрее, чем за {minutes:g} мин", base, lambda w: w.outcome_at - w.stats.started <= limit),
        ("own", own.title, own.about, base + 10, own.passes),
        ("senior", "Сеньор", "Пройти на сложности «Сеньор»", base * SENIOR_REWARD, lambda w: w.difficulty.level == 3),
    )
    return tuple(
        Ticket(f"{stage.index}:{key}", stage.index, title, about, reward, passes)
        for key, title, about, reward, passes in entries
    )


TICKETS: tuple[tuple[Ticket, ...], ...] = tuple(_tickets_of(stage) for stage in STAGES)


def describe_tickets() -> list[list[dict[str, Any]]]:
    return [[ticket.describe() for ticket in stage] for stage in TICKETS]


def closed_by(world: "StoryArena") -> list[Ticket]:
    """The tickets this finished run satisfied, whoever has already been paid for them."""

    if world.outcome != "cleared":
        return []
    return [ticket for ticket in TICKETS[world.stage.index] if ticket.passes(world)]
