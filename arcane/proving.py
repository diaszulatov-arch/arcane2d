"""The proving ground: a hall of dummies, where every rune in the book can be tried.

Nothing here costs, pays or counts.  It exists so that a rune can be tested before
it is bought and a spell before it is trusted.
"""

from __future__ import annotations

from collections import deque
from dataclasses import replace
from typing import Any

from .book import BOOK
from .campaign import Stage
from .dungeon import TILE, DungeonMap, build_dungeon
from .game import SPELL_COSTS
from .monsters import Monster
from .story import StoryArena

DPS_WINDOW = 5.0
DUMMY_HP = 1_000_000.0
MANA_TOP_UP = 25.0
RANGE_CHAT = (
    ("Скрепка", "Похоже, вы проверяете заклинание! Здесь работают все руны Книги, даже некупленные. Манекенам всё равно."),
    ("Скрепка", "Выход — портал у левой стены. Встаньте на него, когда надоест."),
)


class ProvingGround(StoryArena):
    def __init__(self, stage: Stage, party_size: int, *, now: float, difficulty: int = 1) -> None:
        bare = replace(
            stage,
            title="Полигон",
            chat=RANGE_CHAT,
            is_boss=False,
            combat_rooms=0,
            quest="",
            mini="",
        )
        self.hits: deque[tuple[float, float]] = deque()
        self.total = 0.0
        self.dummies: list[Monster] = []
        super().__init__(bare, party_size, now=now, difficulty=difficulty, plain=True)
        self.trial_runes = True
        self.known_runes = {*SPELL_COSTS, "enemies", "allies"}
        room = self.dungeon.rooms[0]
        self.portal = ((room.x + 3) * TILE, (room.y + room.h / 2) * TILE)
        self.portal_ready = True
        self.revealed = {room.index}
        self._place_dummies(room)

    def _build_map(self, quest: Any) -> DungeonMap:
        return build_dungeon(["range"], self.rng)

    def _place_stage_terminal(self) -> None:
        """Nothing is broken here."""

    def _place_dummies(self, room: Any) -> None:
        right = (room.x + room.w * 0.72) * TILE
        for share, key in ((0.25, "dummy"), (0.5, "dummy_walker"), (0.75, "dummy")):
            dummy = self.spawn_monster(key, right, (room.y + room.h * share) * TILE)
            if dummy is not None:
                dummy.hp = dummy.max_hp = DUMMY_HP
                dummy.spawned_at = self.now
                dummy.text = "манекен"
                self.dummies.append(dummy)

    def _spawn_at(self) -> tuple[float, float]:
        room = self.dungeon.rooms[0]
        return (room.x + room.w * 0.35) * TILE, (room.y + room.h / 2) * TILE

    def add_player(self, name: str, **kwargs: Any) -> Any:
        player = super().add_player(name, **kwargs)
        player.x, player.y = self._spawn_at()
        self._settle(player)
        return player

    def damage(
        self,
        *,
        target: Any,
        amount: float,
        source: Any,
        kind: str,
        hit_x: float,
        hit_y: float,
    ) -> float:
        dealt = super().damage(
            target=target, amount=amount, source=source, kind=kind, hit_x=hit_x, hit_y=hit_y
        )
        if isinstance(target, Monster) and dealt > 0:
            self.hits.append((self.now, dealt))
            self.total += dealt
            target.hp = target.max_hp
        return dealt

    def _update_world(self, now: float, dt: float) -> None:
        for player in self.players.values():
            player.invuln_until = max(player.invuln_until, now + 1.0)
            player.mana = min(player.max_mana, player.mana + MANA_TOP_UP * dt)
        while self.hits and now - self.hits[0][0] > DPS_WINDOW:
            self.hits.popleft()
        super()._update_world(now, dt)

    def _waves_in(self, room: Any) -> int:
        return 0

    def world_config(self) -> dict[str, Any]:
        config = super().world_config()
        config["range"] = True
        config["runes"] = sorted(self.known_runes | set(BOOK))
        return config

    def snapshot(self) -> dict[str, Any]:
        state = super().snapshot()
        state["range"] = {
            "dps": round(sum(amount for _, amount in self.hits) / DPS_WINDOW, 1),
            "total": round(self.total),
        }
        return state
