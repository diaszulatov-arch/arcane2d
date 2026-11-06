"""A party: up to four mages walking through the campaign together.

Between stages a party sits in camp, where people read the next lesson, spend
essence and say they are ready.  The party knows nothing about sockets; the
server reads ``outbox`` after each tick and delivers what is there.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from typing import Any

from .campaign import DIFFICULTIES, STAGES, Stage
from .game import COLORS
from .profiles import LESSON_REWARD, ProfileStore
from .roles import ROLE_STAGE, ROLES, apply_role
from .story import StoryArena

MAX_MEMBERS = 4
CODE_LENGTH = 4
CODE_ALPHABET = "".join(c for c in string.ascii_uppercase if c not in "IO")
OFFLINE_GRACE = 90.0
WIPE_ESSENCE_SHARE = 0.5

CAMP = "camp"
PLAYING = "playing"
FINISHED = "finished"


@dataclass(slots=True)
class Seat:
    token: str
    name: str
    color: str
    online: bool = True
    ready: bool = False
    player_id: int | None = None
    left_at: float = 0.0


@dataclass(slots=True)
class Party:
    code: str
    store: ProfileStore
    seats: list[Seat] = field(default_factory=list)
    state: str = CAMP
    stage_index: int = 0
    world: StoryArena | None = None
    outbox: list[dict[str, Any]] = field(default_factory=list)
    changed: bool = True
    empty_since: float | None = None
    last_result: dict[str, Any] | None = None
    rewards: dict[str, int] = field(default_factory=dict)
    last_fixer: str = ""
    difficulty: int = 1

    # ---------------------------------------------------------------- members
    def seat_of(self, token: str) -> Seat | None:
        return next((seat for seat in self.seats if seat.token == token), None)

    @property
    def leader(self) -> Seat | None:
        return next((seat for seat in self.seats if seat.online), None)

    def online(self) -> list[Seat]:
        return [seat for seat in self.seats if seat.online]

    def stage_limit(self) -> int:
        """The furthest stage this party may start: the leader's next unplayed one."""

        leader = self.leader
        cleared = self.store.get(leader.token).cleared if leader else 0
        return min(cleared, len(STAGES) - 1)

    def join(self, token: str, name: str) -> tuple[Seat | None, str | None]:
        seat = self.seat_of(token)
        if seat is None:
            if len(self.seats) >= MAX_MEMBERS:
                return None, "В группе уже четыре мага."
            if self.state == FINISHED:
                return None, "Эта группа уже закончила кампанию."
            used = {taken.color for taken in self.seats}
            color = next((c for c in COLORS if c not in used), COLORS[0])
            seat = Seat(token, name, color)
            self.seats.append(seat)
        seat.online = True
        seat.name = name
        self.empty_since = None
        self.changed = True
        if self.state == CAMP and len(self.seats) == 1:
            self.stage_index = self.stage_limit()
        return seat, None

    def leave(self, token: str) -> None:
        seat = self.seat_of(token)
        if seat is None:
            return
        self._withdraw(seat)
        self.seats.remove(seat)
        self.changed = True

    def disconnect(self, token: str, now: float) -> None:
        """Keep the seat warm: a dropped connection can come back to it."""

        seat = self.seat_of(token)
        if seat is None:
            return
        seat.online = False
        seat.ready = False
        seat.left_at = now
        self._withdraw(seat)
        self.changed = True

    def _withdraw(self, seat: Seat) -> None:
        if self.world is not None and seat.player_id is not None:
            self.world.remove_player(seat.player_id)
        seat.player_id = None

    def place(self, seat: Seat) -> None:
        """Put a mage into the running dungeon, with their upgrades applied."""

        if self.world is None or seat.player_id is not None:
            return
        player = self.world.add_player(seat.name, color=seat.color)
        profile = self.store.get(seat.token)
        profile.apply_to(player)
        if self.world.stage.index >= ROLE_STAGE:
            apply_role(player, profile.role)
        if seat.token == self.last_fixer:
            self.world.last_fixer = player.id
        seat.player_id = player.id

    # ------------------------------------------------------------------- camp
    def choose_stage(self, token: str, index: int) -> str | None:
        leader = self.leader
        if leader is None or leader.token != token:
            return "Этап выбирает лидер группы."
        if self.state != CAMP:
            return "Группа уже в пути."
        if not 0 <= index <= self.stage_limit():
            return "Этот этап ещё не открыт."
        self.stage_index = index
        self.changed = True
        return None

    def choose_difficulty(self, token: str, level: int) -> str | None:
        leader = self.leader
        if leader is None or leader.token != token:
            return "Сложность выбирает лидер группы."
        if self.state != CAMP:
            return "Группа уже в пути."
        if level not in DIFFICULTIES:
            return "Такой сложности нет."
        self.difficulty = level
        self.changed = True
        return None

    def pick_role(self, token: str, role: str) -> str | None:
        profile = self.store.get(token)
        if self.state != CAMP:
            return "Роль выбирают в штабе, между этапами."
        if self.stage_index < ROLE_STAGE and profile.cleared < ROLE_STAGE:
            return "Роли откроются после первой главы."
        if role not in ROLES:
            return "Такой роли нет."
        profile.role = role
        self.store.mark()
        self.changed = True
        return None

    def set_ready(self, token: str, ready: bool, now: float) -> None:
        seat = self.seat_of(token)
        if seat is None or self.state != CAMP:
            return
        seat.ready = ready
        self.changed = True
        people = self.online()
        if people and all(person.ready for person in people):
            self.start_stage(now)

    def start_stage(self, now: float) -> None:
        stage = STAGES[self.stage_index]
        people = self.online()
        self.world = StoryArena(stage, len(people), now=now, difficulty=self.difficulty)
        for seat in self.seats:
            seat.ready = False
            seat.player_id = None
        for seat in people:
            self.place(seat)
        self.state = PLAYING
        self.changed = True
        self.outbox.append(
            {
                "t": "stage_start",
                "stage": stage.describe(),
                "config": self.world.world_config(),
            }
        )

    # ------------------------------------------------------------------ result
    def tick(self, now: float) -> None:
        if self.state == PLAYING and self.world is not None:
            self.world.update(now)
            if self.world.outcome is not None:
                self._finish_stage()
        if self.online():
            self.empty_since = None
        elif self.empty_since is None:
            self.empty_since = now

    def expired(self, now: float) -> bool:
        return self.empty_since is not None and now - self.empty_since > OFFLINE_GRACE

    def _finish_stage(self) -> None:
        world = self.world
        stage = world.stage
        cleared = world.outcome == "cleared"
        fixer = next((seat for seat in self.seats if seat.player_id == world.last_fixer), None)
        if fixer is not None:
            self.last_fixer = fixer.token
        earned = world.essence + stage.clear_bonus if cleared else int(world.essence * WIPE_ESSENCE_SHARE)
        earned = round(earned * world.difficulty.reward)
        self.rewards = {}
        for seat in self.seats:
            profile = self.store.get(seat.token)
            reward = round(earned * profile.essence_rate())
            self.rewards[seat.token] = reward
            profile.essence += reward
            if cleared:
                profile.cleared = max(profile.cleared, stage.index + 1)
        self.store.mark()
        self.world = None
        for seat in self.seats:
            seat.player_id = None
            seat.ready = False
        finale = cleared and stage.index == len(STAGES) - 1
        if cleared and not finale:
            self.stage_index = stage.index + 1
        self.state = FINISHED if finale else CAMP
        self.changed = True
        self.last_result = {
            "t": "stage_end",
            "result": "cleared" if cleared else "wiped",
            "stage": stage.describe(),
            "essence": earned,
            "chapter_done": cleared and stage.is_boss,
            "finale": finale,
        }
        self.outbox.append(self.last_result)

    # ------------------------------------------------------------------ repairs
    def reward_fix(self, token: str, key: str) -> int:
        """Record a repaired task; the first time pays out, later times do not."""

        profile = self.store.get(token)
        if key in profile.lessons:
            return 0
        profile.lessons.append(key)
        profile.essence += LESSON_REWARD
        self.store.mark()
        return LESSON_REWARD

    # ------------------------------------------------------------------ report
    def describe(self, token: str) -> dict[str, Any]:
        leader = self.leader
        stage: Stage = STAGES[self.stage_index]
        return {
            "t": "party",
            "code": self.code,
            "state": self.state,
            "stage": stage.describe(),
            "stage_limit": self.stage_limit(),
            "difficulty": self.difficulty,
            "leader": leader is not None and leader.token == token,
            "seats": [
                {
                    "name": seat.name,
                    "color": seat.color,
                    "online": seat.online,
                    "ready": seat.ready,
                    "leader": seat is leader,
                    "you": seat.token == token,
                    "role": self.store.get(seat.token).role,
                }
                for seat in self.seats
            ],
        }


def new_code(taken: dict[str, Party] | set[str]) -> str:
    while True:
        code = "".join(random.choices(CODE_ALPHABET, k=CODE_LENGTH))
        if code not in taken:
            return code
