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

from .campaign import DIFFICULTIES, ENDINGS, STAGES, Stage, accept_line, people_line
from .crew import has
from .folk import PASSED, SKIPPED
from .folk_data import PEOPLE
from .game import COLORS
from .profiles import LESSON_REWARD, ProfileStore
from .proving import ProvingGround
from .roles import ROLE_STAGE, ROLES, apply_role
from .story import StoryArena
from .tickets import closed_by

MAX_MEMBERS = 4
CODE_LENGTH = 4
CODE_ALPHABET = "".join(c for c in string.ascii_uppercase if c not in "IO")
OFFLINE_GRACE = 90.0
WIPE_ESSENCE_SHARE = 0.5
DUTY_OPENS = 4
DUTY_BONUS = 20
DUTY_BONUS_PER_LEVEL = 15
DUTY_WIPE_SHARE = 0.5
ACCEPT_PENALTY = 0.05
ACCEPT_PENALTY_CAP = 8
# PGT reads out how often the button was pressed: after the reveal, and before the end.
ACCEPT_READOUTS = frozenset({8, len(STAGES) - 1})
# Everyone helped is a green test, and PGT's final form is that much weaker.
PEOPLE_RELIEF = 0.01

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
class DutyShift:
    """An on-call run: incidents one after another, and what they have earned so far."""

    level: int = 1
    tokens: int = 0
    last_stage: int = -1

    @property
    def closed(self) -> int:
        return self.level - 1

    def describe(self) -> dict[str, Any]:
        return {"level": self.level, "tokens": self.tokens, "closed": self.closed}


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
    duty: DutyShift | None = None
    closed_tickets: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    endings: dict[str, str] = field(default_factory=dict)
    shift_closed: int = 0

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
        if self.duty is not None:
            return "Идёт смена: сначала сдайте её."
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
        if self.duty is not None:
            self._start_incident(now)
            return
        stage = STAGES[self.stage_index]
        self.world = StoryArena(
            stage, len(self.online()), now=now, difficulty=self.difficulty, folk_known=self._known_people()
        )
        self._enter_world(stage.describe())

    def _enter_world(self, stage_view: dict[str, Any]) -> None:
        people = self.online()
        for seat in self.seats:
            seat.ready = False
            seat.player_id = None
        for seat in people:
            self.place(seat)
        self._send_crew(people)
        self.state = PLAYING
        self.changed = True
        self.outbox.append(
            {
                "t": "stage_start",
                "stage": stage_view,
                "config": self.world.world_config(),
            }
        )

    def _known_people(self) -> dict[str, str]:
        """Who is settled with everyone at the table: anyone still owed gets to meet them."""

        people = [self.store.get(seat.token).folk for seat in self.online()]
        if not people:
            return {}
        known: dict[str, str] = {}
        for key in people[0]:
            statuses = [entry.get(key) for entry in people]
            if all(statuses):
                known[key] = PASSED if all(status == PASSED for status in statuses) else SKIPPED
        return known

    def _passed(self, token: str) -> int:
        return sum(1 for status in self.store.get(token).folk.values() if status == PASSED)

    def _send_crew(self, people: list[Seat]) -> None:
        """Whoever lives at headquarters does their bit before the party leaves."""

        world = self.world
        cleared = [self.store.get(seat.token).cleared for seat in people]
        if world.life is not None:
            if any(has(count, "request") for count in cleared):
                world.scout()
            if any(has(count, "valera") for count in cleared):
                world.life.start_with_find()
        pressed = max((self.store.get(seat.token).accepted for seat in people), default=0)
        helped = max((self._passed(seat.token) for seat in people), default=0)
        world.pgt_boost = (1 + ACCEPT_PENALTY * min(pressed, ACCEPT_PENALTY_CAP)) * (1 - PEOPLE_RELIEF * helped)

    def readout(self, token: str, stage_index: int) -> list[list[str]]:
        """The extra line a mage hears before this stage, if any: it is about them."""

        if self.duty is not None or stage_index not in ACCEPT_READOUTS:
            return []
        lines = [list(accept_line(self.store.get(token).accepted))]
        if stage_index == len(STAGES) - 1:
            lines.append(list(people_line(self._passed(token), len(PEOPLE))))
        return lines

    # ---------------------------------------------------------- the proving ground
    def start_range(self, token: str, now: float) -> str | None:
        leader = self.leader
        if leader is None or leader.token != token:
            return "На полигон группу ведёт лидер."
        if self.state != CAMP:
            return "Группа уже в пути."
        stage = STAGES[self.stage_index]
        self.world = ProvingGround(stage, len(self.online()), now=now, difficulty=self.difficulty)
        self._enter_world(self.world.stage.describe())
        return None

    # ----------------------------------------------------------------- on-call
    def duty_open(self) -> bool:
        return self.stage_limit() >= DUTY_OPENS

    def start_duty(self, token: str, now: float) -> str | None:
        leader = self.leader
        if leader is None or leader.token != token:
            return "Смену начинает лидер."
        if self.state != CAMP:
            return "Группа уже в пути."
        if not self.duty_open():
            return "Дежурство откроется после первой главы."
        if self.duty is None:
            self.duty = DutyShift()
        self._start_incident(now)
        return None

    def _start_incident(self, now: float) -> None:
        shift = self.duty
        limit = self.stage_limit()
        pool = [
            stage
            for stage in STAGES
            if not stage.is_boss and stage.index < limit and stage.index != shift.last_stage
        ]
        stage = random.choice(pool)
        shift.last_stage = stage.index
        self.world = StoryArena(
            stage,
            len(self.online()),
            now=now,
            difficulty=self.difficulty,
            duty=shift.level,
            known_upto=limit - 1,
        )
        view = stage.describe()
        view["title"] = f"Инцидент {shift.level}: {stage.title}"
        view["chat"] = [["Ада", f"Смена, инцидент номер {shift.level}. Чем дальше, тем хуже: баги крепче и их больше."]]
        view["duty"] = shift.describe()
        self._enter_world(view)

    def end_duty(self, token: str) -> str | None:
        leader = self.leader
        if leader is None or leader.token != token:
            return "Смену сдаёт лидер."
        if self.state != CAMP or self.duty is None:
            return "Сейчас нечего сдавать."
        paid = self._close_shift(1.0)
        self.last_result = {
            "t": "stage_end",
            "result": "shift",
            "stage": STAGES[self.stage_index].describe(),
            "essence": paid,
            "duty_over": True,
            "closed": self.shift_closed,
        }
        self.outbox.append(self.last_result)
        self.changed = True
        return None

    def _close_shift(self, share: float) -> int:
        """Pay the shift out and put it on the board. The result is the party's base pay."""

        shift = self.duty
        self.shift_closed = shift.closed
        paid = round(shift.tokens * share)
        self.rewards = {}
        for seat in self.seats:
            profile = self.store.get(seat.token)
            reward = round(paid * profile.essence_rate())
            self.rewards[seat.token] = reward
            profile.essence += reward
            if shift.closed > profile.duty_best:
                profile.duty_best = shift.closed
                profile.duty_name = seat.name
        self.store.mark()
        self.duty = None
        return paid

    # ------------------------------------------------------------------- finale
    def pick_ending(self, token: str, key: str) -> str | None:
        if self.state != FINISHED:
            return "Финал ещё впереди."
        ending = ENDINGS.get(key)
        if ending is None:
            return "Такой команды нет."
        self.endings[token] = key
        profile = self.store.get(token)
        if key not in profile.endings:
            profile.endings.append(key)
            self.store.mark()
        self.changed = True
        return None

    def back_to_camp(self) -> None:
        if self.state == FINISHED:
            self.state = CAMP
            self.endings = {}
            self.last_result = None
            self.changed = True

    # ------------------------------------------------------------------ result
    def tick(self, now: float) -> None:
        if self.state == PLAYING and self.world is not None:
            self.world.update(now)
            self._keep_relics()
            self._keep_folk()
            self._keep_battle_accepts()
            if self.world.outcome is not None:
                self._finish_stage()
        if self.online():
            self.empty_since = None
        elif self.empty_since is None:
            self.empty_since = now

    def _keep_relics(self) -> None:
        """A relic goes to the archive of everyone at the table, the moment it is found."""

        life = self.world.life
        if life is None:
            return
        for key in life.take_relics():
            for seat in self.seats:
                profile = self.store.get(seat.token)
                if key not in profile.relics:
                    profile.relics.append(key)
            self.store.mark()

    def _keep_battle_accepts(self) -> None:
        """The button in the last fight counts like any other press of it."""

        pressed = self.world.accepted_in_battle
        if not pressed:
            return
        for seat in self.seats:
            if seat.player_id in pressed:
                self.store.get(seat.token).accepted += pressed.count(seat.player_id)
        pressed.clear()
        self.store.mark()

    def _keep_folk(self) -> None:
        """Whoever was at the table saw it: everyone gets the green test. Green stays green."""

        folk = self.world.folk
        if folk is None:
            return
        finished = folk.take_finished()
        for key, status in finished:
            for seat in self.seats:
                entry = self.store.get(seat.token).folk
                if entry.get(key) != PASSED:
                    entry[key] = status
        if finished:
            self.store.mark()

    def expired(self, now: float) -> bool:
        return self.empty_since is not None and now - self.empty_since > OFFLINE_GRACE

    def _finish_range(self) -> None:
        stage = self.world.stage
        self.world = None
        for seat in self.seats:
            seat.player_id = None
            seat.ready = False
        self.state = CAMP
        self.changed = True
        self.rewards = {}
        self.last_result = {
            "t": "stage_end",
            "result": "range",
            "stage": STAGES[stage.index].describe(),
            "essence": 0,
        }
        self.outbox.append(self.last_result)

    def _finish_incident(self) -> None:
        world = self.world
        shift = self.duty
        cleared = world.outcome == "cleared"
        stage = STAGES[world.stage.index]
        earned = world.essence
        if cleared:
            earned += DUTY_BONUS + DUTY_BONUS_PER_LEVEL * shift.level
        shift.tokens += round(earned * world.difficulty.reward)
        self.world = None
        for seat in self.seats:
            seat.player_id = None
            seat.ready = False
        self.state = CAMP
        self.changed = True
        if cleared:
            shift.level += 1
            self.rewards = {}
            self.last_result = {
                "t": "stage_end",
                "result": "incident",
                "stage": stage.describe(),
                "essence": 0,
                "duty": shift.describe(),
            }
        else:
            paid = self._close_shift(DUTY_WIPE_SHARE)
            self.last_result = {
                "t": "stage_end",
                "result": "shift_lost",
                "stage": stage.describe(),
                "essence": paid,
                "duty_over": True,
                "closed": self.shift_closed,
            }
        self.outbox.append(self.last_result)

    def _pay_tickets(self, world: StoryArena) -> None:
        """A ticket pays each mage once, whenever they personally close it first."""

        closed = closed_by(world)
        self.closed_tickets = {}
        for seat in self.seats:
            profile = self.store.get(seat.token)
            fresh = [ticket for ticket in closed if ticket.key not in profile.tickets]
            for ticket in fresh:
                profile.tickets.append(ticket.key)
                profile.essence += ticket.reward
            if fresh:
                self.closed_tickets[seat.token] = [ticket.describe() for ticket in fresh]

    def _finish_stage(self) -> None:
        world = self.world
        if isinstance(world, ProvingGround):
            self._finish_range()
            return
        if self.duty is not None:
            self._finish_incident()
            return
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
        self._pay_tickets(world)
        self.store.mark()
        self.world = None
        for seat in self.seats:
            seat.player_id = None
            seat.ready = False
        finale = cleared and stage.index == len(STAGES) - 1
        if cleared and not finale:
            self.stage_index = stage.index + 1
        self.state = FINISHED if finale else CAMP
        self.endings = {}
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
            "relics": list(self.store.get(token).relics),
            "folk": dict(self.store.get(token).folk),
            "ending": self.endings.get(token, ""),
            "duty": {
                "open": self.duty_open(),
                "shift": self.duty.describe() if self.duty is not None else None,
                "best": self.store.get(token).duty_best,
                "board": self.store.duty_board(),
            },
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
