"""What a mage keeps between sessions: tokens, upgrades, and how far they got.

Tokens are what the assistant spent on all this; the code calls them essence,
which is also what the saves on disk are keyed by.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .game import CAST_LOCK, MANA_REGEN, MAX_HP, MAX_MANA, MOVE_SPEED, ROLL_COOLDOWN, Player

MAX_UPGRADE_LEVEL = 5
LESSON_REWARD = 12
TOP_TIER_PRICE = 1.5

BRANCHES: dict[str, str] = {
    "life": "Жизнь",
    "mana": "Мана",
    "might": "Мощь",
    "grace": "Ловкость",
    "bond": "Союз",
}

# Each branch is a ladder: a rung can never be taken higher than the one below
# it, so ``needs`` names that rung.  ``step`` is what one level gives, in ``unit``.
UPGRADES: dict[str, dict[str, Any]] = {
    "max_hp": {
        "title": "Крепость",
        "about": "Объём здоровья",
        "branch": "life",
        "step": 15.0,
        "unit": "HP",
    },
    "hp_regen": {
        "title": "Живучесть",
        "about": "Здоровье восстанавливается само, даже в бою",
        "branch": "life",
        "step": 0.6,
        "unit": "HP/с",
        "needs": "max_hp",
    },
    "armor": {
        "title": "Стойкость",
        "about": "Входящий урон меньше",
        "branch": "life",
        "step": 4.0,
        "unit": "% урона",
        "sign": "−",
        "needs": "hp_regen",
    },
    "max_mana": {
        "title": "Глубина",
        "about": "Объём маны",
        "branch": "mana",
        "step": 16.0,
        "unit": "маны",
    },
    "mana_regen": {
        "title": "Поток",
        "about": "Мана восстанавливается быстрее",
        "branch": "mana",
        "step": 1.6,
        "unit": "маны/с",
        "needs": "max_mana",
    },
    "kill_mana": {
        "title": "Прилив",
        "about": "Мана за каждого убитого врага",
        "branch": "mana",
        "step": 3.0,
        "unit": "маны",
        "needs": "mana_regen",
    },
    "spell_power": {
        "title": "Сила",
        "about": "Урон всех рун",
        "branch": "might",
        "step": 6.0,
        "unit": "%",
    },
    "crit": {
        "title": "Точность",
        "about": "Шанс нанести двойной урон",
        "branch": "might",
        "step": 5.0,
        "unit": "%",
        "needs": "spell_power",
    },
    "cast_speed": {
        "title": "Концентрация",
        "about": "Гримуар перезаряжается быстрее",
        "branch": "might",
        "step": 0.04,
        "unit": "с",
        "sign": "−",
        "needs": "crit",
    },
    "move_speed": {
        "title": "Лёгкость",
        "about": "Скорость бега",
        "branch": "grace",
        "step": 4.0,
        "unit": "%",
    },
    "roll_cd": {
        "title": "Кувырок",
        "about": "Перекат готов быстрее",
        "branch": "grace",
        "step": 0.14,
        "unit": "с",
        "sign": "−",
        "needs": "move_speed",
    },
    "alchemy": {
        "title": "Чутьё",
        "about": "Сферы лечат сильнее и притягиваются издалека",
        "branch": "grace",
        "step": 15.0,
        "unit": "%",
        "needs": "roll_cd",
    },
    "fortune": {
        "title": "Удача",
        "about": "Больше токенов за этап",
        "branch": "bond",
        "step": 5.0,
        "unit": "%",
    },
    "ward_shield": {
        "title": "Оберег",
        "about": "Щит в начале каждого боя в комнате",
        "branch": "bond",
        "step": 8.0,
        "unit": "щита",
        "needs": "fortune",
    },
    "rescue": {
        "title": "Спасатель",
        "about": "Вы поднимаете союзников быстрее",
        "branch": "bond",
        "step": 30.0,
        "unit": "%",
        "needs": "ward_shield",
    },
}

# Past the first two rungs every level costs half as much again.
_TOP_RUNGS = {
    stat
    for stat, upgrade in UPGRADES.items()
    if upgrade.get("needs") and UPGRADES[upgrade["needs"]].get("needs")
}


def upgrade_cost(level: int, stat: str | None = None) -> int:
    """Price of taking an upgrade from ``level`` to ``level + 1``."""

    base = 40 + level * 40
    return round(base * TOP_TIER_PRICE) if stat in _TOP_RUNGS else base


@dataclass(frozen=True, slots=True)
class Perks:
    """Campaign bonuses that have no meaning on the arena, read by ``StoryArena``."""

    armor: float = 0.0
    power: float = 1.0
    crit: float = 0.0
    kill_mana: float = 0.0
    rescue: float = 1.0
    pickups: float = 1.0
    pickup_reach: float = 0.0
    ward_shield: float = 0.0
    pierce_guard: bool = False
    weak_scale: float = 1.0


@dataclass(slots=True)
class Profile:
    token_hash: str
    essence: int = 0
    cleared: int = 0
    upgrades: dict[str, int] = field(default_factory=dict)
    lessons: list[str] = field(default_factory=list)
    role: str = ""

    def level(self, stat: str) -> int:
        return self.upgrades.get(stat, 0)

    def buy(self, stat: str) -> str | None:
        """Spend essence on one level. Returns why it was refused, if it was."""

        upgrade = UPGRADES.get(stat)
        if upgrade is None:
            return "Такого улучшения нет."
        level = self.level(stat)
        if level >= MAX_UPGRADE_LEVEL:
            return "Это улучшение уже на максимуме."
        needs = upgrade.get("needs")
        if needs and self.level(needs) <= level:
            return f"Сначала улучшите «{UPGRADES[needs]['title']}»."
        cost = upgrade_cost(level, stat)
        if self.essence < cost:
            return f"Нужно токенов: {cost}."
        self.essence -= cost
        self.upgrades[stat] = level + 1
        return None

    def bonus(self, stat: str) -> float:
        """The total an upgrade gives at its current level, in its own unit."""

        return self.level(stat) * UPGRADES[stat]["step"]

    def essence_rate(self) -> float:
        return 1.0 + self.bonus("fortune") / 100

    def apply_to(self, player: Player) -> None:
        player.max_hp = MAX_HP + self.bonus("max_hp")
        player.max_mana = MAX_MANA + self.bonus("max_mana")
        player.hp_regen = self.bonus("hp_regen")
        player.mana_regen = MANA_REGEN + self.bonus("mana_regen")
        player.speed = MOVE_SPEED * (1 + self.bonus("move_speed") / 100)
        player.cast_lock = CAST_LOCK - self.bonus("cast_speed")
        player.roll_cooldown = ROLL_COOLDOWN - self.bonus("roll_cd")
        player.perks = Perks(
            armor=self.bonus("armor") / 100,
            power=1 + self.bonus("spell_power") / 100,
            crit=self.bonus("crit") / 100,
            kill_mana=self.bonus("kill_mana"),
            rescue=1 + self.bonus("rescue") / 100,
            pickups=1 + self.bonus("alchemy") / 100,
            pickup_reach=self.level("alchemy") * 50.0,
            ward_shield=self.bonus("ward_shield"),
        )
        player.hp = player.max_hp
        player.mana = player.max_mana

    def describe(self) -> dict[str, Any]:
        return {
            "essence": self.essence,
            "cleared": self.cleared,
            "upgrades": dict(self.upgrades),
            "lessons": list(self.lessons),
            "role": self.role,
        }


def describe_upgrades() -> dict[str, Any]:
    return {
        "max_level": MAX_UPGRADE_LEVEL,
        "branches": BRANCHES,
        "stats": {
            stat: {
                **upgrade,
                "costs": [upgrade_cost(level, stat) for level in range(MAX_UPGRADE_LEVEL)],
            }
            for stat, upgrade in UPGRADES.items()
        },
    }


class ProfileStore:
    """One JSON file of profiles, keyed by a hash of each browser's secret token.

    With no path it lives in memory only, which is what tests want.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.profiles: dict[str, Profile] = {}
        self.dirty = False
        if path is not None and path.exists():
            self._load(path)

    def _load(self, path: Path) -> None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # A damaged save must never stop the server from starting.
            return
        for token_hash, entry in raw.items():
            self.profiles[token_hash] = Profile(
                token_hash=token_hash,
                essence=int(entry.get("essence", 0)),
                cleared=int(entry.get("cleared", 0)),
                upgrades=dict(entry.get("upgrades", {})),
                lessons=list(entry.get("lessons", [])),
                role=str(entry.get("role", "")),
            )

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def get(self, token: str) -> Profile:
        token_hash = self.hash_token(token)
        profile = self.profiles.get(token_hash)
        if profile is None:
            profile = Profile(token_hash)
            self.profiles[token_hash] = profile
        return profile

    def mark(self) -> None:
        self.dirty = True

    def save(self) -> None:
        """Write everything atomically, so a crash cannot leave half a file."""

        if self.path is None or not self.dirty:
            return
        self.dirty = False
        payload = {key: profile.describe() for key, profile in self.profiles.items()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False)
            os.replace(temporary, self.path)
        except OSError:
            try:
                os.unlink(temporary)
            except OSError:
                pass
