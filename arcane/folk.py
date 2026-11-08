"""Side stories: everyone along the way has a problem, and no two are solved alike.

A person is a Thing you can talk to.  Talking opens a panel with replies, and each
reply goes back through StageFolk.reply, which only accepts what was really offered.
An Errand is what happens after "yes": every kind has a verb no other one has.
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Mapping

from .dungeon import TILE, Room
from .folk_data import PEOPLE, PERSON_BY_KEY, Person
from .game import MOVE_SPEED, Player
from .life import FIND_BY_KEY
from .quests import USE_REACH, Thing

if TYPE_CHECKING:
    from .monsters import Monster
    from .story import StoryArena
    from .terrain import Prop

PASSED = "passed"
SKIPPED = "skipped"
SLOTS = 2
REPLY_REACH = USE_REACH * 2.2
CHATTER_REACH = 420.0
CHATTER_EVERY = 6.5
BUBBLE_TIME = 5.0
SHOUT_REACH = 460.0
BUG_TAG = "folk"
HINT_REACH = 340.0
REPEAT_PAY = 0.5
PGT_REPLY = "[Принять] Пусть PGT разберётся"
LATER_REPLY = "Потом"

SEAT_SPOT = 36.0
SEAT_CLEAR = USE_REACH * 1.8
QUIET_KINDS = ("rest", "cache", "vault", "deal")
WANDER_SPEED = 46.0
STILL_DRIFT = 1.5

HANDSHAKE_TIME = 8.0
HANDSHAKE_RING = 150.0
HANDSHAKE_SOUNDS = ("пш-ш-ш", "иииу-у-у", "кр-р-р", "дынь")
TROLL_RING = 430.0
TROLL_SILENCE = 14.0
TROLL_TAUNT_EVERY = 2.8
TROLL_SPEED = 44.0
TROLL_CLOSE = 130.0
TROLL_TAUNTS = (
    "Что, руны кончились?",
    "А fireball у вас на минималках?",
    "Кто так колдует? Четыре пробела!",
    "Я тебя по IP вычислю. По четвёртой версии.",
    "Ну давай, ответь. Или ты бот?",
    "Вот поэтому у тебя и нет репутации.",
    "ЛОЛ. Молчишь? Нечего сказать, да?",
    "Сколько можно молчать? Это не по правилам. Какие правила? Мои.",
)
RUNNERS = ("left-pad", "is-odd", "is-even", "lodash", "react")
RUNNER_SPEED = MOVE_SPEED * 0.78
RUNNER_FEAR = 300.0
RUNNER_TOUCH = 46.0
CAT_SPEED = MOVE_SPEED * 1.12
CAT_FEAR = 280.0
CAT_FROZEN = 4.5
CAT_PETS = 3
CAT_WARY = 2.6
CAT_FOLLOW = 92.0
FRAME_KILLS = 4
FRAME_W = 460.0
FRAME_H = 320.0
FRAME_SWAY = 0.45
FRAME_BUG_EVERY = 4.0
FRAME_MAX_BUGS = 3
HONEST_USERS = ("оля_1984", "дед_мороз", "vasya", "аноним", "ленка_2007", "кот_матроскин")
SPAM_USERS = ("КУПИ_АЙФОН", "заработок24", "ТОЛЬКО_СЕГОДНЯ")
BAD_BANS = 3
USER_SPEED = 56.0
SURPRISES = 5
RECOMMEND_REACH = 560.0
VERSIONS = ("12.06 23:59", "14.06 03:12", "14.06 03:07", "13.06 19:30")
TRUE_VERSION = "14.06 03:12"
HOTCOLD_EVERY = 1.2
HOTCOLD_SAME = 26.0
FLOWER_TOUCH = 66.0
LAG_TIME = 3.0
LAG_PLATE = 62.0
LAG_HOLD = 0.5
LAG_ROUNDS = (340.0, 520.0)
LAG_WALK = MOVE_SPEED * (LAG_TIME - 0.6)
TRASH_FILES = ("кэш.tmp", "error_2009.log", "старое.bak")
KEEP_FILES = ("кот.jpg", "реферат.docx", "main.py")
FIRE_KINDS = frozenset({"fire", "meteor"})
ENV_SWITCHES = 3
ENV_TIME_FLOOR = 18.0
ENV_TIME_SLACK = 1.7
WET_RADIUS = 50.0
WET_CLEAR = 130.0
WET_EVERY = 2.2
CRON_PERIOD = 2.6
CRON_WINDOW = 0.13
CRON_HITS = 3
PRINTER_FIXES = 4
PRINTER_ERRORS = (
    ("ПЕРЕГРЕВ ПЕЧКИ", "frost", "остудить: frostbolt"),
    ("ХОЛОДНЫЙ БАРАБАН", "fire", "согреть: fireball"),
    ("СТАТИКА НА ЛЕНТЕ", "shock", "разрядить: spark_volley"),
    ("ЗАМЯТИЕ БУМАГИ", "shake", "вытрясти: nova"),
)
SHOCK_KINDS = frozenset({"spark", "beam"})
SHAKE_KINDS = frozenset({"nova", "emp"})
CABLE_SLACK = 1.22
CABLE_SOCKET = 58.0
MINER_TRIES = 3
MINER_CRASH = (3.0, 16.0)

CHAIN_GOSSIP: dict[str, str] = {
    "atm": "Перешлите-е-е пять рублей! И припев!",
    "fridge": "Это фейк. Я читал первоисточник. Он у меня на дверце.",
    "clip": "Похоже, вы пересылаете письмо! Хотите добавить вложение?",
    "vendor": "Беру за три токена как базу для спама.",
    "calc": "Десять друзей минус семь это три. А плюс не работает.",
    "zina": "Пш-ш... Не могу прочитать. Вложение большое, загрузится к среде.",
    "senya": "ОГО! Можно я сниму реакцию на это письмо?",
    "petrovich": "Флуд. Предупреждение. Бабе Вале передайте: второе.",
    "rec": "Вам также понравится это письмо. Ой, оно уже у вас.",
    "gosha2": "А это надо было в .gitignore? Я уже закоммитил.",
    "cat": "Кот положил лапу на письмо и столкнул его со стола.",
}
CHAIN_FALLBACK = "Спасибо, не читаю. Но сохраню."


@dataclass(frozen=True, slots=True)
class Talk:
    text: str
    replies: tuple[tuple[str, str], ...] = ()
    code: str = ""


@dataclass(slots=True)
class Question:
    text: str
    replies: tuple[tuple[str, str], ...]
    right: str
    good: str = ""
    bad: str = ""
    code: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class Errand:
    """One person's whole side story on one stage."""

    wants_space = False

    def __init__(self, folk: "StageFolk", person: Person, thing: Thing) -> None:
        self.folk = folk
        self.person = person
        self.thing = thing
        self.arena = folk.arena
        self.quest = folk.quest
        self.rng = folk.rng
        self.room: Room = self.arena.dungeon.rooms[thing.room]
        self.started = False
        self.finished = False
        self.repeat = folk.known.get(person.key) == PASSED
        self.owner = 0
        self.parts: list[Thing] = []
        self.bodies: list[tuple["Prop", Thing]] = []
        self.setup()

    # ------------------------------------------------------------ for subclasses
    def setup(self) -> None:
        pass

    def begin(self, player: Player) -> Talk | None:
        return self.talk(player)

    def talk(self, player: Player) -> Talk | None:
        return Talk(self.status() or self.person.intro)

    def answer(self, key: str, player: Player) -> Talk | None:
        return None

    def update(self, now: float, dt: float) -> None:
        pass

    def use_part(self, part: Thing, player: Player) -> None:
        pass

    def spell_cast(self, player: Player, runes: Any, logs: list[str], ok: bool) -> None:
        pass

    def monster_died(self, monster: "Monster", killer: Player | None, kind: str) -> None:
        pass

    def status(self) -> str:
        return ""

    def bar(self) -> float | None:
        return None

    def marks(self) -> list[tuple[float, float, int]]:
        return []

    def cleanup(self) -> None:
        for part in self.parts:
            part.gone = True
        self.parts = []
        for prop, _ in self.bodies:
            self.arena.terrain.remove_prop(prop)
        self.bodies = []
        thing = self.thing
        thing.charge = 0.0
        thing.data.pop("hold", None)
        for key in ("ring", "clock", "rate", "frozen"):
            thing.data["view"].pop(key, None)

    # ------------------------------------------------------------------ dialogue
    @property
    def active(self) -> bool:
        return self.started and not self.finished

    def opening(self, player: Player) -> Talk | None:
        if self.finished:
            return Talk(self.person.after or self.person.thanks)
        if self.started:
            return self.talk(player)
        replies = [("start", self.person.accept)]
        if self.person.key not in self.folk.known:
            replies.append(("pgt", PGT_REPLY))
        replies.append(("later", LATER_REPLY))
        return Talk(self.person.intro, tuple(replies), self.person.code)

    def on_use(self, thing: Thing, player: Player) -> None:
        self.folk.show(thing, player, self.opening(player))

    def finish(self, text: str = "") -> Talk:
        self.finished = True
        self.cleanup()
        self.folk.pay(self)
        self._settle_down()
        return Talk(text or self.person.thanks)

    def complete(self, text: str = "") -> None:
        """The same, when nobody is in the middle of a conversation."""

        self.speak(self.finish(text).text)

    def accept_pgt(self, player: Player) -> Talk:
        self.started = True
        self.finished = True
        self.cleanup()
        self.folk.pay(self, status=SKIPPED)
        self._settle_down()
        return Talk(self.person.pgt_line)

    def _settle_down(self) -> None:
        self.refresh_mark()
        self.thing.data["use"] = f"поговорить: {self.person.name}"

    # ------------------------------------------------------------------- helpers
    @property
    def now(self) -> float:
        return self.arena.now

    def part(self, look: str, x: float, y: float, room: Room | None = None, *, kind: str = "folk", label: str = "", use: str = "", **view: Any) -> Thing:
        home = room or self.room
        data: dict[str, Any] = {"owner": self, "view": {"look": look, **view}}
        if use:
            data["use"] = use
        thing = self.quest._add(kind, x, y, home, label=label, data=data)
        self.parts.append(thing)
        return thing

    def body(self, thing: Thing, radius: float, on_hit: Callable[[Thing, Player | None, str], None]) -> "Prop":
        """Something spells can hit, though enemies() cannot see it."""

        prop = self.arena.terrain.add_prop(
            "body", thing.x, thing.y, radius, lambda _prop, source, kind: on_hit(thing, source, kind)
        )
        self.bodies.append((prop, thing))
        return prop

    def drop_body(self, thing: Thing) -> None:
        for entry in list(self.bodies):
            if entry[1] is thing:
                self.arena.terrain.remove_prop(entry[0])
                self.bodies.remove(entry)

    def tick(self, now: float, dt: float) -> None:
        for prop, thing in self.bodies:
            prop.x, prop.y = thing.x, thing.y
        self.update(now, dt)

    def note(self, x: float, y: float, text: str, good: bool = False) -> None:
        self.arena.emit({"e": "quest_note", "x": round(x, 1), "y": round(y, 1), "text": text, "good": good})

    def bubble(self, text: str, thing: Thing | None = None) -> None:
        who = thing or self.thing
        who.data["view"]["say"] = text
        who.data["chat_at"] = self.now + BUBBLE_TIME

    def hold(self, text: str) -> None:
        """Something to keep repeating until it changes: a forecast, an error on a screen."""

        self.thing.data["hold"] = text
        self.thing.data["view"]["say"] = text

    def speak(self, text: str) -> None:
        self.quest._say(((self.person.name, text),), urgent=True)

    def spot(self, room: Room | None = None, radius: float = 26.0) -> tuple[float, float]:
        return self.folk.spot(room or self.room, radius)

    def nearest(self, x: float, y: float) -> tuple[Player | None, float]:
        best: Player | None = None
        distance = math.inf
        for mage in self.arena.hunted():
            gap = math.hypot(mage.x - x, mage.y - y)
            if gap < distance:
                best, distance = mage, gap
        return best, distance

    def near(self, player: Player, reach: float = SHOUT_REACH) -> bool:
        return math.hypot(player.x - self.thing.x, player.y - self.thing.y) <= reach

    def bug(self, x: float | None = None, y: float | None = None) -> "Monster | None":
        """One of this chapter's bugs turns up, and it does not count as part of a fight."""

        point = (self.thing.x if x is None else x, self.thing.y if y is None else y)
        monster = self.quest._spawn_around(point, self.rng.choice(self.arena.stage.roster))
        if monster is not None:
            monster.quest = BUG_TAG
        return monster

    def step_towards(self, thing: Thing, x: float, y: float, speed: float, dt: float, room: Room | None = None, radius: float = 14.0) -> None:
        """Walk or flee: a wall in the way turns the walker aside instead of stopping it."""

        angle = math.atan2(y - thing.y, x - thing.x)
        for turn in (0.0, 0.7, -0.7, 1.4, -1.4, 2.2, -2.2):
            nx = thing.x + math.cos(angle + turn) * speed * dt
            ny = thing.y + math.sin(angle + turn) * speed * dt
            if room is not None and not room.holds(nx, ny, 1.0):
                continue
            if self.arena.can_stand(nx, ny, radius):
                thing.x, thing.y = nx, ny
                return

    def refresh_mark(self) -> None:
        view = self.thing.data["view"]
        view["mark"] = "✓" if self.finished else "…" if self.started else "!"
        if self.repeat and not self.started:
            view["mark"] = "?"


# =========================================================== chapter one: the Old Web
class Calculator(Errand):
    """Go and find a lost key: the plain errand everyone starts with."""

    def setup(self) -> None:
        rooms = [
            room for room in self.arena.dungeon.rooms
            if room is not self.room and room.kind in ("combat", "vault", "cache")
        ]
        room = self.rng.choice(rooms or [self.room])
        x, y = self.spot(room)
        self.plus = self.quest._add("item", x, y, room, label="клавиша «+»", color="#ffd27a", data={"owner": self})
        self.parts.append(self.plus)

    def opening(self, player: Player) -> Talk | None:
        if not self.finished and self.plus.gone:
            self.started = True
            return Talk(
                "Это же он! Дайте вставлю. Так... Сейчас проверим. Сколько будет 2 + 2?",
                (("four", "4"), ("five", "5"), ("depends", "Смотря кто считает")),
            )
        return super().opening(player)

    def answer(self, key: str, player: Player) -> Talk | None:
        return self.finish(
            {
                "four": "2 + 2 = 4! Я снова складываю! Вот ваша награда, и я её пересчитал дважды.",
                "five": "При больших значениях двойки, да. Ты мне нравишься. Вот награда, плюс-минус.",
            }.get(key, "Бухгалтер, значит. Уважаю. Вот награда, в отчёте будет другая цифра.")
        )

    def update(self, now: float, dt: float) -> None:
        plus = self.plus
        if self.finished or plus.gone or self.quest._toucher(plus.x, plus.y, 48.0) is None:
            return
        plus.gone = True
        self.started = True
        self.refresh_mark()
        self.arena.emit({"e": "quest_item", "x": round(plus.x, 1), "y": round(plus.y, 1), "label": plus.label})

    def talk(self, player: Player) -> Talk | None:
        return Talk("Я потерял клавишу «+». Где-то в этих комнатах. Без неё я только вычитаю.")

    def status(self) -> str:
        return "отнесите клавишу «+» хозяину" if self.plus.gone else "найдите клавишу «+»"

    def marks(self) -> list[tuple[float, float, int]]:
        if self.plus.gone:
            return [(self.thing.x, self.thing.y, self.thing.room)]
        return [(self.plus.x, self.plus.y, self.plus.room)]


class Modem(Errand):
    """Hold still, and hold your spells, while a machine sings to itself."""

    def begin(self, player: Player) -> Talk | None:
        self.progress = 0.0
        self.sound = 0
        self.places: dict[int, tuple[float, float]] = {}
        self.thing.data["view"]["ring"] = HANDSHAKE_RING
        return Talk("Ну всё, набираю. Войдите в круг и замрите. Пш-ш-ш...")

    def talk(self, player: Player) -> Talk | None:
        return Talk("Я же говорю: в круг и не шевелиться! Пш-ш-ш...")

    def _hang_up(self, x: float, y: float) -> None:
        if self.progress > 0.4:
            self.note(x, y, "Мама сняла трубку!")
            self.bubble("Алло? АЛЛО?! Кто это?! Занято!")
        self.progress = 0.0
        self.sound = 0

    def update(self, now: float, dt: float) -> None:
        if not self.active:
            return
        thing = self.thing
        moved: Player | None = None
        inside = [m for m in self.arena.hunted() if math.hypot(m.x - thing.x, m.y - thing.y) <= HANDSHAKE_RING]
        for mage in inside:
            last = self.places.get(mage.id)
            if last is not None and math.hypot(mage.x - last[0], mage.y - last[1]) > STILL_DRIFT:
                moved = mage
        self.places = {mage.id: (mage.x, mage.y) for mage in self.arena.hunted()}
        if moved is not None:
            self._hang_up(moved.x, moved.y)
        elif inside:
            self.progress += dt
            beat = int(self.progress / HANDSHAKE_TIME * len(HANDSHAKE_SOUNDS))
            if beat > self.sound and beat < len(HANDSHAKE_SOUNDS):
                self.sound = beat
            if self.sound < len(HANDSHAKE_SOUNDS):
                thing.data["view"]["say"] = HANDSHAKE_SOUNDS[self.sound]
                thing.data["chat_at"] = now + 1.0
        thing.charge = self.progress / HANDSHAKE_TIME
        if self.progress >= HANDSHAKE_TIME:
            self.complete()

    def spell_cast(self, player: Player, runes: Any, logs: list[str], ok: bool) -> None:
        if self.active and runes and self.near(player, HANDSHAKE_RING):
            self._hang_up(player.x, player.y)

    def status(self) -> str:
        return "стоять в круге и не двигаться"

    def bar(self) -> float | None:
        return min(1.0, self.progress / HANDSHAKE_TIME)


class Webmaster(Errand):
    """Sign a guestbook with what your own spell prints."""

    ROUNDS = (
        ("Запись первая: любой текст. Выведите его через log().", 'log("Привет, Геннадий!")'),
        ("Запись вторая: почините счётчик. Было семь, вы восьмой. Пусть заклинание само посчитает.", "log(7 + 1)"),
        ("Запись третья: сразу три строки одним заклинанием, будто вас много.", 'log("Я посетитель")\nlog("И я")\nlog("И я тоже")'),
    )

    def begin(self, player: Player) -> Talk | None:
        self.round = 0
        return self.talk(player)

    def talk(self, player: Player) -> Talk | None:
        text, code = self.ROUNDS[self.round]
        return Talk(text, code=code)

    def spell_cast(self, player: Player, runes: Any, logs: list[str], ok: bool) -> None:
        if not self.active or not ok or not logs or not self.near(player):
            return
        if self.round == 0:
            self.bubble(f"«{logs[0][:44]}». Мне такого ещё не писали!")
        elif self.round == 1:
            if not any("8" in line for line in logs):
                self.bubble("Это не восемь. Пусть заклинание посчитает.")
                return
            self.bubble("Восемь посетителей! Счётчик работает!")
        elif len(logs) < 3:
            self.bubble(f"Это {len(logs)}. Я ждал три записи за раз.")
            return
        self.round += 1
        if self.round >= len(self.ROUNDS):
            self.complete()
            return
        self.speak(self.ROUNDS[self.round][0])

    def status(self) -> str:
        return f"гостевая книга, запись {self.round + 1} из {len(self.ROUNDS)}: {self.ROUNDS[self.round][1].splitlines()[0]}"

    def bar(self) -> float | None:
        return self.round / len(self.ROUNDS)


class NodeModules(Errand):
    """Play tag with a folder's worth of packages: spells do not help, legs do."""

    wants_space = True

    def begin(self, player: Player) -> Talk | None:
        for name in RUNNERS:
            x, y = self.spot(radius=16.0)
            self.part("runner", x, y, label=name)
        return Talk("Вон они! Разбегаются! Догоняйте и просто дотроньтесь, они маленькие.")

    def talk(self, player: Player) -> Talk | None:
        return Talk("Там ещё остались! Просто догоните.")

    def update(self, now: float, dt: float) -> None:
        if not self.active:
            return
        for part in self.parts:
            if part.gone:
                continue
            mage, gap = self.nearest(part.x, part.y)
            if mage is None:
                continue
            if gap <= RUNNER_TOUCH:
                part.gone = True
                self.note(part.x, part.y, f"{part.label}: пойман", good=True)
            elif gap <= RUNNER_FEAR:
                away_x = part.x * 2 - mage.x
                away_y = part.y * 2 - mage.y
                self.step_towards(part, away_x, away_y, RUNNER_SPEED, dt, self.room)
        self.parts = [part for part in self.parts if not part.gone]
        if not self.parts:
            self.complete()

    def status(self) -> str:
        return f"поймать сбежавшие пакеты: осталось {len(self.parts)}"

    def bar(self) -> float | None:
        return 1 - len(self.parts) / len(RUNNERS)


class Troll(Errand):
    """Whatever he says, do nothing: every spell feeds him."""

    def begin(self, player: Player) -> Talk | None:
        self.silence = 0.0
        self.fed = 0
        self.taunt_at = self.now + 1.0
        self.thing.data["view"]["ring"] = TROLL_RING
        return Talk("О, молчун! Ну-ну. Посмотрим, на сколько тебя хватит. Колдуй давай!")

    def talk(self, player: Player) -> Talk | None:
        return Talk("Чё смотришь? Сказать нечего? Так и думал. Заклинание покажи!")

    def update(self, now: float, dt: float) -> None:
        if not self.active:
            return
        thing = self.thing
        mage, gap = self.nearest(thing.x, thing.y)
        if mage is None or gap > TROLL_RING:
            return
        if gap > TROLL_CLOSE:
            self.step_towards(thing, mage.x, mage.y, TROLL_SPEED, dt, radius=24.0)
        self.silence += dt
        if now >= self.taunt_at:
            self.taunt_at = now + TROLL_TAUNT_EVERY
            self.bubble(self.rng.choice(TROLL_TAUNTS))
        if self.silence >= TROLL_SILENCE:
            self.complete()

    def spell_cast(self, player: Player, runes: Any, logs: list[str], ok: bool) -> None:
        if not self.active or not runes or not self.near(player, TROLL_RING):
            return
        self.silence = 0.0
        self.fed += 1
        self.thing.data["view"]["size"] = round(1 + 0.14 * min(self.fed, 6), 2)
        self.bubble("НЯМ! Вот, другое дело! ЕЩЁ!")
        self.note(player.x, player.y, "Тролль сыт. Заново")
        if self.fed % 3 == 0:
            self.speak("Пацаны, сюда! Тут один отвечает!")
            self.bug(player.x, player.y)
            self.bug(player.x, player.y)

    def finish(self, text: str = "") -> Talk:
        talk = super().finish(text)
        self.thing.gone = True
        return talk

    def accept_pgt(self, player: Player) -> Talk:
        talk = super().accept_pgt(player)
        self.thing.gone = True
        return talk

    def status(self) -> str:
        return "не кормить тролля: ни одного заклинания рядом с ним"

    def bar(self) -> float | None:
        return min(1.0, self.silence / TROLL_SILENCE)


# ==================================================== chapter two: the Endless Feed
class ChainLetter(Errand):
    """Be a nuisance on someone's behalf: go round the neighbours with a letter."""

    def begin(self, player: Player) -> Talk | None:
        self.told: set[int] = set()
        others = self._others()
        self.need = min(3, len(others))
        if not self.need:
            return self.finish("Никого нет? Ну и ладно, сама разошлю. Держи, внучек.")
        for thing in others:
            thing.data.setdefault("view", {})["use"] = "переслать письмо счастья"
        return Talk(f"Вот письмо. Покажи соседям, хотя бы {self.need}. Они возле тебя, просто подойди и нажми E.")

    def talk(self, player: Player) -> Talk | None:
        return Talk(f"Показал уже {len(self.told)} из {self.need}? Давай-давай, удача ждать не будет.")

    def _others(self) -> list[Thing]:
        return [thing for thing in self.folk.all_people() if thing is not self.thing and not thing.gone]

    def intercept(self, thing: Thing, player: Player) -> bool:
        if not self.active or thing.id in self.told:
            return False
        if not any(other is thing for other in self._others()):
            return False
        self.told.add(thing.id)
        thing.data["view"].pop("use", None)
        who = thing.data.get("resident") or thing.data.get("person", "")
        self.bubble(CHAIN_GOSSIP.get(who, CHAIN_FALLBACK), thing)
        self.note(thing.x, thing.y, f"Переслано: {len(self.told)} из {self.need}", good=True)
        if len(self.told) >= self.need:
            self.complete()
        return True

    def cleanup(self) -> None:
        super().cleanup()
        for thing in self.folk.all_people():
            thing.data.get("view", {}).pop("use", None)

    def status(self) -> str:
        return f"показать письмо соседям: {len(self.told)} из {self.need}"

    def bar(self) -> float | None:
        return len(self.told) / self.need


class Cat(Errand):
    """It will not be caught, only stopped: freeze it, then be quick."""

    wants_space = True

    def setup(self) -> None:
        self.frozen_until = 0.0
        self.wary_until = 0.0
        self.pets = 0
        self.thing.data["use"] = "посмотреть на кота"

    def begin(self, player: Player) -> Talk | None:
        self.body(self.thing, 30.0, self._hit)
        self.thing.data["use"] = "погладить кота"
        # He will be out of earshot before anyone reads a panel: this goes over the radio.
        self.speak("Кот заметил вашу руку и уже в другом конце комнаты. Нужен мороз: frostbolt, потом сразу E.")
        return None

    def on_use(self, thing: Thing, player: Player) -> None:
        if not self.active:
            super().on_use(thing, player)
            return
        if self.frozen_until <= self.now:
            self.note(thing.x, thing.y, "Кот увернулся")
            return
        self.pets += 1
        self.frozen_until = 0.0
        self.wary_until = self.now + CAT_WARY
        thing.data["view"].pop("frozen", None)
        self.note(thing.x, thing.y, f"Мр-р ({self.pets} из {CAT_PETS})", good=True)
        if self.pets >= CAT_PETS:
            self.complete()

    def _hit(self, thing: Thing, source: Player | None, kind: str) -> None:
        if kind == "frost" and self.wary_until > self.now:
            self.note(thing.x, thing.y, "Кот только что отряхнулся. Подождите")
        elif kind == "frost":
            self.frozen_until = self.now + CAT_FROZEN
            thing.data["view"]["frozen"] = True
            self.note(thing.x, thing.y, "Кот замер и обижен")
        else:
            self.note(thing.x, thing.y, "Кот ушёл от удара и презирает вас")

    def update(self, now: float, dt: float) -> None:
        thing = self.thing
        if self.finished and self.pets:
            mage, gap = self.nearest(thing.x, thing.y)
            if mage is not None and gap > CAT_FOLLOW:
                # A gif walks through walls if it wants to: it is a gif.
                pace = min(gap - CAT_FOLLOW, MOVE_SPEED * 1.2 * dt)
                thing.x += (mage.x - thing.x) / gap * pace
                thing.y += (mage.y - thing.y) / gap * pace
                room = self.arena.dungeon.room_at(thing.x, thing.y)
                if room is not None:
                    thing.room = room.index
            return
        if not self.active:
            return
        if self.frozen_until > now:
            return
        thing.data["view"].pop("frozen", None)
        mage, gap = self.nearest(thing.x, thing.y)
        if mage is not None and gap <= CAT_FEAR:
            self.step_towards(thing, thing.x * 2 - mage.x, thing.y * 2 - mage.y, CAT_SPEED, dt, self.room, 18.0)

    def status(self) -> str:
        return f"заморозить кота и погладить: {self.pets} из {CAT_PETS}"

    def bar(self) -> float | None:
        return self.pets / CAT_PETS


class Blogger(Errand):
    """Fight where the camera is, not where it suits you."""

    wants_space = True

    def begin(self, player: Player) -> Talk | None:
        self.views = 0
        self.bug_at = self.now + 1.0
        self.sway = 0.0
        cx, cy = self.room.center
        self.width = min(FRAME_W, self.room.w * TILE - 2 * TILE)
        self.height = min(FRAME_H, self.room.h * TILE - 2 * TILE)
        self.frame = self.part("frame", cx, cy, w=self.width, h=self.height)
        return Talk("Запись пошла! Баги сами сбегутся, у меня на канале всегда так. Бейте только внутри рамки!")

    def talk(self, player: Player) -> Talk | None:
        return Talk("Не отвлекайтесь, идёт запись! В кадре бейте, в кадре!")

    def update(self, now: float, dt: float) -> None:
        if not self.active:
            return
        cx, cy = self.room.center
        self.sway += dt
        reach = max(0.0, (self.room.w * TILE - self.width) / 2 - TILE)
        self.frame.x = cx + math.sin(self.sway * FRAME_SWAY) * reach
        self.frame.y = cy
        if now >= self.bug_at:
            self.bug_at = now + FRAME_BUG_EVERY
            near = [m for m in self.arena.monsters.values() if self.room.holds(m.x, m.y)]
            if len(near) < FRAME_MAX_BUGS:
                self.bug(self.frame.x, self.frame.y)

    def monster_died(self, monster: "Monster", killer: Player | None, kind: str) -> None:
        if not self.active or not self.room.holds(monster.x, monster.y):
            return
        frame = self.frame
        if abs(monster.x - frame.x) <= self.width / 2 and abs(monster.y - frame.y) <= self.height / 2:
            self.views += 1
            self.note(monster.x, monster.y, f"В кадре! {self.views} из {FRAME_KILLS}", good=True)
            if self.views >= FRAME_KILLS:
                self.complete()
        else:
            self.bubble("Вне кадра! Этого никто не увидит!")

    def status(self) -> str:
        return f"бить багов внутри рамки: {self.views} из {FRAME_KILLS}"

    def bar(self) -> float | None:
        return self.views / FRAME_KILLS


class Moderator(Errand):
    """Read before you shoot: spammers walk among people, and only names tell them apart."""

    wants_space = True

    def begin(self, player: Player) -> Talk | None:
        self._crowd()
        return Talk("Смотрите на ники. Трое из них спамеры. Хоть одно заклинание в честного, и он обидится.")

    def _crowd(self) -> None:
        self.banned = 0
        self.mistakes = 0
        names = [(name, False) for name in HONEST_USERS] + [(name, True) for name in SPAM_USERS]
        self.rng.shuffle(names)
        for name, spam in names:
            x, y = self.spot(radius=16.0)
            part = self.part("user", x, y, kind="walker", label=name)
            part.data["spam"] = spam
            part.data["heading"] = self.rng.uniform(0, math.tau)
            self.body(part, 22.0, self._hit)

    def talk(self, player: Player) -> Talk | None:
        return Talk(f"Забанено {self.banned} из {len(SPAM_USERS)}. Ошибок: {self.mistakes} из {BAD_BANS}. Читайте ники.")

    def _hit(self, thing: Thing, source: Player | None, kind: str) -> None:
        if thing.gone:
            return
        if thing.data["spam"]:
            thing.gone = True
            self.drop_body(thing)
            self.banned += 1
            self.note(thing.x, thing.y, "ЗАБАНЕН", good=True)
            if self.banned >= len(SPAM_USERS):
                self.complete()
            return
        self.mistakes += 1
        self.note(thing.x, thing.y, "За что?!")
        if self.mistakes >= BAD_BANS:
            self.cleanup()
            self.started = False
            self.refresh_mark()
            self.speak("Всё, хватит. Вы забанили троих честных людей. Они написали жалобу. Мне. Начинайте сначала, когда прочитаете правила.")

    def update(self, now: float, dt: float) -> None:
        if not self.active:
            return
        for part in self.parts:
            if part.gone:
                continue
            part.data["heading"] += self.rng.uniform(-1.2, 1.2) * dt
            heading = part.data["heading"]
            before = part.x, part.y
            self.step_towards(
                part, part.x + math.cos(heading) * 40, part.y + math.sin(heading) * 40,
                USER_SPEED, dt, self.room, 14.0,
            )
            if (part.x, part.y) == before:
                part.data["heading"] += math.pi

    def status(self) -> str:
        return f"забанить спамеров по никам: {self.banned} из {len(SPAM_USERS)}, ошибок {self.mistakes}"

    def bar(self) -> float | None:
        return self.banned / len(SPAM_USERS)


class Recommender(Errand):
    """Be unpredictable: whatever it expects from you is exactly what will not count."""

    def begin(self, player: Player) -> Talk | None:
        self.streak = 0
        self.recent: deque[str] = deque(maxlen=2)
        self._forecast()
        return Talk("Я считаю. Руны, которые вы применяли последними, я жду. Какие угодно другие, пять раз подряд, и я сломаюсь.")

    def talk(self, player: Player) -> Talk | None:
        return Talk(f"Прогноз: {self._guess()}. Удивлений подряд: {self.streak} из {SURPRISES}.")

    def _guess(self) -> str:
        return ", ".join(self.recent) if self.recent else "то, что вы любите"

    def _forecast(self) -> None:
        self.hold(f"Прогноз: {self._guess()}")

    def spell_cast(self, player: Player, runes: Any, logs: list[str], ok: bool) -> None:
        if not self.active or not ok or not runes or not self.near(player, RECOMMEND_REACH):
            return
        used = [str(rune) for rune in runes]
        if any(rune in self.recent for rune in used):
            if self.streak:
                self.note(player.x, player.y, "Так и знал", False)
            self.streak = 0
        else:
            self.streak += 1
            self.note(player.x, player.y, f"Не ожидал! {self.streak} из {SURPRISES}", good=True)
        for rune in used:
            self.recent.append(rune)
        if self.streak >= SURPRISES:
            self.complete()
        else:
            self._forecast()

    def status(self) -> str:
        return f"удивить алгоритм, прогноз: {self._guess()}. Подряд {self.streak} из {SURPRISES}"

    def bar(self) -> float | None:
        return self.streak / SURPRISES


class EnvLeak(Errand):
    """Beat the clock: every key turned, in every room, before anyone uses the old ones."""

    def begin(self, player: Player) -> Talk | None:
        self._arm()
        return Talk(
            f"Ключи! Их надо заменить, пока ими не воспользовались. Три щитка, и у нас {round(self.time_left)} секунд. Я... я подержу вам дверь. Морально."
        )

    def _arm(self) -> None:
        rooms = [
            room for room in self.arena.dungeon.rooms
            if room.index in self.arena.revealed
            and room.kind not in ("exit", "trap", "secret", "boss", "workshop", "puzzle", "trial")
            and (not (room.kind == "combat" or room.guarded) or room.index in self.arena.cleared_rooms)
        ]
        self.rng.shuffle(rooms)
        rooms.sort(key=lambda room: room is not self.room)
        chosen = (rooms * ENV_SWITCHES)[:ENV_SWITCHES] or [self.room] * ENV_SWITCHES
        travel = 0.0
        last = (self.thing.x, self.thing.y)
        for number, room in enumerate(chosen, 1):
            x, y = self.spot(room)
            self.part("switch", x, y, room, label=f"ключ {number}", use="сменить ключ")
            travel += self.quest._path_tiles(last, (x, y)) * TILE
            last = (x, y)
        self.time_left = max(ENV_TIME_FLOOR, travel / MOVE_SPEED * ENV_TIME_SLACK + 6.0)
        self.limit = self.time_left

    def talk(self, player: Player) -> Talk | None:
        if self.parts:
            return Talk(f"Быстрее! Осталось {round(self.time_left)} секунд!")
        self._arm()
        return Talk(f"Опять утекли, но я сгенерировал новые. Ещё раз: {round(self.time_left)} секунд.")

    def use_part(self, part: Thing, player: Player) -> None:
        if part.on:
            return
        part.on = True
        self.note(part.x, part.y, "Ключ заменён", good=True)
        if all(switch.on for switch in self.parts):
            self.complete()

    def update(self, now: float, dt: float) -> None:
        if not self.active or not self.parts:
            return
        self.time_left -= dt
        if self.time_left <= 0:
            self.cleanup()
            self.speak("Не успели. На мой ключ кто-то купил сервер в Панаме. Подойдите, начнём заново, пожалуйста.")
            self.bug()

    def status(self) -> str:
        if not self.parts:
            return "поговорить с Гошей: ключи снова утекли"
        left = sum(1 for part in self.parts if not part.on)
        return f"сменить ключи: осталось {left}, времени {round(self.time_left)} с"

    def bar(self) -> float | None:
        return max(0.0, self.time_left / self.limit) if self.parts else None

    def marks(self) -> list[tuple[float, float, int]]:
        return [(part.x, part.y, part.room) for part in self.parts if not part.on]


# ================================================================= the Cloud
class Versions(Errand):
    """Go round every copy, read the dates, and only then decide."""

    def begin(self, player: Player) -> Talk | None:
        rooms = [
            room for room in self.arena.dungeon.rooms
            if room.kind in ("start", "combat", "vault", "cache", "rest", "deal", "quest")
        ]
        self.rng.shuffle(rooms)
        dates = list(VERSIONS)
        self.rng.shuffle(dates)
        self.wrong = 0
        for date, room in zip(dates, rooms * len(dates)):
            x, y = self.spot(room)
            self.part("version", x, y, room, label=f"Диплом · {date}", use=f"объявить настоящей: {date}").data["date"] = date
        return Talk("Копии лежат по комнатам, и на каждой дата сохранения. Настоящая самая поздняя. Сначала обойдите всё, потом выбирайте!")

    def talk(self, player: Player) -> Talk | None:
        return Talk("Настоящая это самая поздняя правка. Дату смотрите внимательно, там и минуты важны.")

    def use_part(self, part: Thing, player: Player) -> None:
        if part.data.get("date") == TRUE_VERSION:
            self.complete()
            return
        part.gone = True
        self.wrong += 1
        self.note(part.x, part.y, "Это курсовая какого-то Коли!")
        self.bug(part.x, part.y)

    def status(self) -> str:
        return "обойти копии диплома и выбрать самую позднюю"

    def marks(self) -> list[tuple[float, float, int]]:
        return [(part.x, part.y, part.room) for part in self.parts if not part.gone]


class HotCold(Errand):
    """Nothing on the map: only a voice saying warmer or colder."""

    def begin(self, player: Player) -> Talk | None:
        rooms = [
            room for room in self.arena.dungeon.rooms
            if room is not self.room and room.kind in ("start", "combat", "vault", "cache", "rest", "deal", "quest")
        ]
        room = self.rng.choice(rooms or [self.room])
        self.flower = self.spot(room)
        self.flower_room = room
        self.owner = player.id
        self.say_at = self.now + HOTCOLD_EVERY
        self.last_gap = math.hypot(player.x - self.flower[0], player.y - self.flower[1])
        return Talk("Я его слышу! Идите, я подскажу. На карте его нет, он же цветочек.")

    def talk(self, player: Player) -> Talk | None:
        return Talk("Идите куда-нибудь! Я скажу, теплее или холоднее.")

    def update(self, now: float, dt: float) -> None:
        if not self.active:
            return
        mage = self.arena.players.get(self.owner)
        if mage is None or mage.dead:
            mage, _ = self.nearest(*self.flower)
        if mage is None:
            return
        gap = math.hypot(mage.x - self.flower[0], mage.y - self.flower[1])
        if gap <= FLOWER_TOUCH:
            x, y = self.flower
            self.note(x, y, "О-о! Цветочек!", good=True)
            self.complete()
            return
        if now < self.say_at:
            return
        self.say_at = now + HOTCOLD_EVERY
        if gap < self.last_gap - HOTCOLD_SAME:
            word, good = ("Горячо!" if gap < 220 else "Теплее"), True
        elif gap > self.last_gap + HOTCOLD_SAME:
            word, good = "Холоднее", False
        else:
            self.last_gap = gap
            return
        self.last_gap = gap
        self.note(mage.x, mage.y - 30, f"Ася: {word}", good)

    def status(self) -> str:
        return "искать цветочек: Ася говорит, теплее или холоднее"


class LagPlates(Errand):
    """Your three-second-old self is a separate person, and you need them both."""

    wants_space = True

    def begin(self, player: Player) -> Talk | None:
        self.round = 0
        self.held = 0.0
        self.owner = player.id
        self.trail: deque[tuple[float, float, float]] = deque()
        self.shadow = self.part("shadow", player.x, player.y, label="вы, 3 с назад")
        self._lay_plates()
        return Talk("Встаньте на золотую, дождитесь тень и бегите на голубую. Тень три секунды будет стоять там, где вы были.")

    def _lay_plates(self) -> None:
        for part in list(self.parts):
            if part is not self.shadow:
                part.gone = True
        self.parts = [self.shadow]
        (ax, ay), (bx, by) = self._plate_spots(LAG_ROUNDS[self.round])
        self.blue = self.part("ring", ax, ay, label="вы", r=LAG_PLATE, color="#7fe0ee")
        self.gold = self.part("ring", bx, by, label="ваша тень", r=LAG_PLATE, color="#ffd27a")

    def _plate_spots(self, wanted: float) -> tuple[tuple[float, float], tuple[float, float]]:
        """Far enough apart to be a problem, near enough to run: all you have is the lag."""

        best: tuple[tuple[float, float], tuple[float, float]] | None = None
        best_miss = math.inf
        for _ in range(60):
            first = self.spot(radius=40.0)
            second = self.spot(radius=40.0)
            if self.quest._path_tiles(first, second) * TILE > LAG_WALK:
                continue
            miss = abs(math.hypot(first[0] - second[0], first[1] - second[1]) - wanted)
            if miss < best_miss:
                best, best_miss = (first, second), miss
        if best is not None:
            return best
        x, y = self.thing.x, self.thing.y
        return (x, y), (x, y)

    def talk(self, player: Player) -> Talk | None:
        return Talk("Вы на голубой, тень на золотой, в одно и то же мгновение. Подождите... сейчас посмотрю, стоите ли вы там. Три секунды.")

    def update(self, now: float, dt: float) -> None:
        if not self.active:
            return
        mage = self.arena.players.get(self.owner)
        if mage is None or mage.dead:
            living = self.arena.hunted()
            if not living:
                return
            mage = living[0]
            self.owner = mage.id
        self.trail.append((now, mage.x, mage.y))
        while len(self.trail) > 1 and self.trail[1][0] <= now - LAG_TIME:
            self.trail.popleft()
        _, sx, sy = self.trail[0]
        self.shadow.x, self.shadow.y = sx, sy
        on_blue = math.hypot(mage.x - self.blue.x, mage.y - self.blue.y) <= LAG_PLATE
        on_gold = math.hypot(sx - self.gold.x, sy - self.gold.y) <= LAG_PLATE
        self.blue.on = on_blue
        self.gold.on = on_gold
        if not (on_blue and on_gold):
            self.held = 0.0
            return
        self.held += dt
        if self.held < LAG_HOLD:
            return
        self.held = 0.0
        self.round += 1
        self.note(mage.x, mage.y, "Синхронизировано!", good=True)
        if self.round >= len(LAG_ROUNDS):
            self.complete()
            return
        self._lay_plates()
        self.speak("Отлично! Теперь подальше: я отстаю всё так же, а плиты разъехались. Рассчитывайте.")

    def status(self) -> str:
        return f"вы на голубой плите, тень на золотой: {self.round} из {len(LAG_ROUNDS)}"

    def bar(self) -> float | None:
        return self.round / len(LAG_ROUNDS)


class Recycling(Errand):
    """Judge each file by its name, and pass sentence with the right rune."""

    wants_space = True

    def begin(self, player: Player) -> Talk | None:
        files = [(name, "fire") for name in TRASH_FILES] + [(name, "frost") for name in KEEP_FILES]
        self.rng.shuffle(files)
        self.total = len(files)
        for name, sentence in files:
            x, y = self.spot(radius=26.0)
            part = self.part("file", x, y, label=name)
            part.data["sentence"] = sentence
            self.body(part, 26.0, self._hit)
        return Talk("Вот они. .tmp, .log, .bak сжечь. .jpg, .docx, .py заморозить. Читайте названия, не стреляйте сгоряча.")

    def talk(self, player: Player) -> Talk | None:
        return Talk("Осталось разобрать: " + ", ".join(part.label for part in self.parts if not part.gone) + ".")

    def _hit(self, thing: Thing, source: Player | None, kind: str) -> None:
        if thing.gone or not self.active:
            return
        verdict = "fire" if kind in FIRE_KINDS else "frost" if kind == "frost" else ""
        if not verdict:
            self.note(thing.x, thing.y, "Ни то ни сё: огонь или мороз")
            return
        if verdict != thing.data["sentence"]:
            self.note(thing.x, thing.y, "Не то! Из файла что-то лезет")
            self.bug(thing.x, thing.y)
            return
        thing.gone = True
        self.drop_body(thing)
        self.parts = [part for part in self.parts if not part.gone]
        self.note(thing.x, thing.y, "Сожжён" if verdict == "fire" else "Восстановлен", good=True)
        if not self.parts:
            self.complete()

    def status(self) -> str:
        return f"сжечь мусор, заморозить ценное: осталось {len(self.parts)}"

    def bar(self) -> float | None:
        return 1 - len(self.parts) / self.total


# ================================================================ questions and answers
class Exam(Errand):
    """A conversation that goes on only when the answer is right."""

    retry_later = False

    def questions(self) -> list[Question]:
        return []

    def lead(self) -> str:
        return ""

    def begin(self, player: Player) -> Talk | None:
        self.rounds = self.questions()
        self.round = 0
        return self.ask(self.lead())

    def talk(self, player: Player) -> Talk | None:
        return self.ask()

    def asking(self, question: Question) -> None:
        pass

    def wrong(self, question: Question) -> None:
        self.bug()

    def ask(self, lead: str = "") -> Talk:
        question = self.rounds[self.round]
        self.asking(question)
        return Talk(f"{lead} {question.text}".strip(), question.replies, question.code)

    def answer(self, key: str, player: Player) -> Talk | None:
        question = self.rounds[self.round]
        if key == question.right:
            lead = question.good
            self.round += 1
        else:
            lead = question.bad
            self.wrong(question)
            if self.retry_later:
                self.rounds.append(self.rounds[self.round])
                self.round += 1
        if self.round >= len(self.rounds):
            return self.finish(f"{lead} {self.person.thanks}".strip())
        return self.ask(lead)

    def status(self) -> str:
        return f"поговорить: {self.round} из {len(self.rounds)}"

    def bar(self) -> float | None:
        return self.round / len(self.rounds)


class Reflog(Exam):
    """Read the history and find the last moment before it all went wrong."""

    LOG = (
        "a81f Гоша: fix\n"
        "7c20 Гоша: fix fix\n"
        "e9d1 pgt: оптимизация, удалил лишнее\n"
        "41bb ada: тесты зелёные, можно выкатывать\n"
        "09ac ada: первый релиз"
    )

    def questions(self) -> list[Question]:
        replies = (("a81f", "a81f"), ("7c20", "7c20"), ("e9d1", "e9d1"), ("41bb", "41bb"), ("09ac", "09ac"))
        return [
            Question(
                "Вот он. Самый верхний это самый свежий. Куда откатываемся?",
                replies, "41bb",
                bad="git reset --hard... Ой. Ой-ой. Там тоже всё сломано, и что-то вылезло. Давайте другой.",
                code=self.LOG,
            )
        ]


class CodeReview(Exam):
    """Find the bug in a Friday fix, by the line it lives on."""

    def questions(self) -> list[Question]:
        def lines(count: int) -> tuple[tuple[str, str], ...]:
            return tuple((str(number), f"Строка {number}") for number in range(1, count + 1))

        return [
            Question(
                "Первый фикс: сумма чеков. На тестовых данных у меня вышло правильно, там был один товар.",
                lines(5), "4",
                good="Точно, s = p затирает всё, что было. Надо s += p.",
                bad="Там всё нормально. Смотрите, что копится в s.",
                code="def total(prices):\n    s = 0\n    for p in prices:\n        s = p\n    return s",
            ),
            Question(
                "Второй: проверка возраста. Совершеннолетние проходят.",
                lines(4), "2",
                good="Да! Человеку ровно 18 лет, а его не пускает. Нужно >=.",
                bad="Нет, это верно. А если человеку ровно 18?",
                code="def is_adult(age):\n    if age > 18:\n        return True\n    return False",
            ),
            Question(
                "Третий: печать списка. Падает, только когда всё уже напечатал. Я думал, это нормально.",
                lines(3), "2",
                good="IndexError! Лишний проход. Просто range(len(items)).",
                bad="Нет. Посчитайте, какие значения примет i.",
                code="items = [1, 2, 3]\nfor i in range(len(items) + 1):\n    print(items[i])",
            ),
        ]

    def wrong(self, question: Question) -> None:
        """Nothing crawls out of a review: he is only a little embarrassed for you."""


class FactCheck(Exam):
    """A hallucination tells you things with total confidence. Some of them are even true."""

    retry_later = True
    CLAIMS = (
        ("len(\"кот\") вернёт 3.", True),
        ("[1, 2, 3][3] вернёт 3.", False),
        ("range(3) это числа 1, 2, 3.", False),
        ("HTTP 404 значит «не найдено».", True),
        ("bool([]) даёт True: список же есть.", False),
        ("В Python блоки кода определяются отступами.", True),
        ("DNS превращает имена сайтов в IP-адреса.", True),
        ("rm -rf обязательно спросит подтверждение, если файлов много.", False),
        ("\"5\" + 5 вернёт \"55\".", False),
        ("2 ** 3 равно 8.", True),
        ("git push --force ничего не может удалить: всё остаётся на сервере.", False),
        ("Порт 443 обычно занят HTTPS.", True),
    )

    def questions(self) -> list[Question]:
        claims = list(self.CLAIMS)
        self.rng.shuffle(claims)
        replies = (("true", "Правда"), ("false", "Выдумка"))
        return [
            Question(
                f"«{claim}» Это хорошо известный факт.",
                replies, "true" if fact else "false",
                good="Правда? Вы проверили? Как интересно.",
                bad="Вы мне поверили или нет? Так или иначе, это вы зря. Спросим ещё раз позже.",
            )
            for claim, fact in claims[:6]
        ]


class Guard(Exam):
    """Be the firewall: read a rule, and apply it to whoever is next in the queue."""

    retry_later = True
    RULE = 'def allow(user, port, day):\n    if user == "pgt":\n        return False\n    return port == 443 and day != "пт"'
    QUEUE = (
        ("оля", 443, "вт"), ("pgt", 443, "ср"), ("вася", 22, "пн"),
        ("ленка", 443, "пт"), ("дед_майнер", 80, "чт"), ("петрович", 443, "сб"),
    )

    def setup(self) -> None:
        self.visitor: Thing | None = None

    def questions(self) -> list[Question]:
        queue = list(self.QUEUE)
        self.rng.shuffle(queue)
        x, y = self.arena.dungeon.open_near(self.thing.x + 120, self.thing.y + 30, 18.0)
        self.visitor = self.part("user", x, y, kind="walker", label="")
        return [
            Question(
                f"Следующий: {user}, порт {port}, день {day}.",
                (("allow", "Пропустить"), ("deny", "Не пускать")),
                "allow" if user != "pgt" and port == 443 and day != "пт" else "deny",
                good="Верно.",
                bad="Куда?! Гляди, что наделал. Встанет в конец очереди.",
                code=self.RULE,
                data={"user": user},
            )
            for user, port, day in queue
        ]

    def asking(self, question: Question) -> None:
        if self.visitor is not None:
            self.visitor.label = question.data["user"]


class Mother(Exam):
    """Say it in plain words: nothing here can be solved by knowing more than she does."""

    def questions(self) -> list[Question]:
        return [
            Question(
                "Ошибка 550. Так кто такая Mailbox?",
                (
                    ("smtp", "SMTP-сервер вернул permanent failure"),
                    ("plain", "Ящик вашей дочки больше не принимает письма"),
                    ("again", "Нажмите ещё раз, посильнее"),
                ),
                "plain",
                good="Закрылся ящик? Так бы и сказали. А я думала, это какая-то женщина.",
                bad="Я нажала. И СМТП этот ваш я не знаю, он из Сбербанка? Вы мне попроще, как для мамы.",
            ),
            Question(
                "Она у меня программист, Ада зовут. Тут работала, на этих ваших серверах. Три года как не пишет. Но ведь это ничего? Занятая она.",
                (
                    ("truth", "Я знаю одну Аду. Но это, кажется, не она"),
                    ("lie", "Да, она очень занята"),
                ),
                "truth",
                good="Спасибо, что не стали придумывать. Мне тут уже один всё придумал. Давайте письмо отправим, может, дойдёт.",
                bad="Вот и он так говорил, этот ваш помощник. Очень вежливо. Вы мне правду скажите, я взрослый человек.",
            ),
            Question(
                "Я напишу коротко, она длинное не читает. Вот. Как отправить, чтобы фильтр этот ваш не съел?",
                (
                    ("header", "Добавьте SPF и DKIM-подпись"),
                    ("send", "Просто нажмите «Отправить». Такие письма он не трогает"),
                ),
                "send",
                good="Нажимаю.",
                bad="Это из какой области? Вы, главное, скажите, куда нажать.",
                code="Кому: ada\nТема: (без темы)\n\nТы поела?",
            ),
        ]

    def wrong(self, question: Question) -> None:
        """Nobody gets punished for talking down to her. She only asks again."""

    def finish(self, text: str = "") -> Talk:
        talk = super().finish(text)
        self.quest._say(
            (("Ада", "...Письмо пришло на ветку. Адресат не я, я только занимаю её адрес. Я сохраню его. Вы никому не говорите, ладно?"),),
        )
        return talk

    def status(self) -> str:
        return "помочь Марии Ивановне отправить письмо, говорите по-простому"


# ======================================================== chapter four: the Data Centre
class Mopping(Errand):
    """The floor is wet, and it keeps on getting wet somewhere new."""

    wants_space = True

    def begin(self, player: Player) -> Talk | None:
        self.carrier = 0
        room = self.room
        corners = [
            (room.x + 2.5, room.y + 2.5), (room.x + room.w - 2.5, room.y + 2.5),
            (room.x + 2.5, room.y + room.h - 2.5), (room.x + room.w - 2.5, room.y + room.h - 2.5),
        ]
        far = max(corners, key=lambda c: math.hypot(c[0] * TILE - self.thing.x, c[1] * TILE - self.thing.y))
        x, y = self.arena.dungeon.open_near(far[0] * TILE, far[1] * TILE, 30.0)
        self.bucket = self.part("bucket", x, y, label="ведро", use="взять ведро")
        self.home = (self.thing.x, self.thing.y)
        self.wet: list[Thing] = []
        for _ in range(max(5, min(10, room.w * room.h // 40))):
            wx, wy = self._dry_spot()
            self.wet.append(self.part("wet", wx, wy, r=WET_RADIUS))
        self.mop_at = self.now + WET_EVERY
        return Talk("Вон оно, в углу. Мокрое обходи. Я тут ещё протру, пока ты ходишь.")

    def talk(self, player: Player) -> Talk | None:
        if self.carrier == player.id:
            return self.finish()
        if self.carrier:
            return Talk("Ведро уже несут. Не мешай.")
        return Talk("Ведро! В углу! И не топчи!")

    def _dry_spot(self) -> tuple[float, float]:
        points = [(self.thing.x, self.thing.y), (self.bucket.x, self.bucket.y)]
        points += [(mage.x, mage.y) for mage in self.arena.hunted()]
        for _ in range(30):
            x, y = self.arena.dungeon.open_point(self.room, self.rng, 20.0, margin=2)
            if all(math.hypot(x - px, y - py) >= WET_CLEAR for px, py in points):
                return x, y
        return self.arena.dungeon.open_point(self.room, self.rng, 20.0, margin=2)

    def use_part(self, part: Thing, player: Player) -> None:
        if part is self.bucket and not self.carrier:
            self.carrier = player.id
            part.holder = player.id
            part.data.pop("use", None)
            self.note(part.x, part.y, "Ведро у вас", good=True)

    def _drop_bucket(self) -> None:
        self.carrier = 0
        self.bucket.holder = 0
        self.bucket.data["use"] = "взять ведро"

    def update(self, now: float, dt: float) -> None:
        if not self.active:
            return
        if self.carrier:
            mage = self.arena.players.get(self.carrier)
            if mage is None or mage.dead:
                self._drop_bucket()
            else:
                self.bucket.x, self.bucket.y = mage.x, mage.y
        for mage in self.arena.hunted():
            if not self.room.holds(mage.x, mage.y):
                continue
            if any(math.hypot(mage.x - w.x, mage.y - w.y) <= WET_RADIUS for w in self.wet):
                self._yell(mage)
        if now >= self.mop_at and self.wet:
            self.mop_at = now + WET_EVERY
            patch = self.rng.choice(self.wet)
            patch.x, patch.y = self._dry_spot()

    def _yell(self, mage: Player) -> None:
        self.bubble("Я ЖЕ МЫЛА! Иди сюда, откуда пришёл!")
        self.note(mage.x, mage.y, "Я ЖЕ МЫЛА!")
        if self.carrier == mage.id:
            self._drop_bucket()
        mage.x, mage.y = self.arena.dungeon.open_near(self.home[0] + 70, self.home[1] + 30, mage.radius)
        self.arena.emit({"e": "pull", "id": mage.id, "x": round(mage.x, 1), "y": round(mage.y, 1)})

    def status(self) -> str:
        if self.carrier:
            return "отнести ведро тёте Любе, по мокрому не ходить"
        return "забрать ведро в дальнем углу, по мокрому не ходить"

    def marks(self) -> list[tuple[float, float, int]]:
        if self.carrier:
            return [(self.thing.x, self.thing.y, self.thing.room)]
        return [(self.bucket.x, self.bucket.y, self.bucket.room)]


class CronClock(Errand):
    """Press at the right moment. It is a matter of timing and nothing else."""

    def begin(self, player: Player) -> Talk | None:
        self.hits = 0
        self.spin = 0.0
        self.thing.data["view"]["clock"] = 0.5
        self.thing.data["use"] = "нажмите, когда стрелка наверху"
        return Talk("Смотрите на циферблат надо мной. Стрелка наверху, жмите E.")

    def on_use(self, thing: Thing, player: Player) -> None:
        if not self.active:
            super().on_use(thing, player)
            return
        phase = self.spin / CRON_PERIOD % 1.0
        if phase <= CRON_WINDOW or phase >= 1 - CRON_WINDOW:
            self.hits += 1
            self.note(thing.x, thing.y - 60, f"03:00:00 ({self.hits} из {CRON_HITS})", good=True)
            if self.hits >= CRON_HITS:
                self.complete()
        else:
            if self.hits:
                self.note(thing.x, thing.y - 60, "Рано или поздно, но не вовремя")
            self.hits = 0

    def update(self, now: float, dt: float) -> None:
        if self.active:
            self.spin += dt
            self.thing.data["view"]["clock"] = round(self.spin / CRON_PERIOD % 1.0, 3)

    def status(self) -> str:
        return f"E ровно в три: {self.hits} из {CRON_HITS} подряд"

    def bar(self) -> float | None:
        return self.hits / CRON_HITS


class Printer(Errand):
    """Read the error, then answer with the rune that actually treats it."""

    def begin(self, player: Player) -> Talk | None:
        self.fixes = 0
        self.body(self.thing, 44.0, self._hit)
        self.error = PRINTER_ERRORS[0]
        self._next_error()
        return Talk(f"{self.error[0]}. СТРЕЛЯЙТЕ ПО МНЕ. ЭТО НЕ ШУТКА. Это инструкция по эксплуатации.")

    def talk(self, player: Player) -> Talk | None:
        return Talk(f"{self.error[0]}. Нужно {self.error[2]}.")

    def _next_error(self) -> None:
        choices = [entry for entry in PRINTER_ERRORS if entry is not self.error]
        self.error = self.rng.choice(choices)
        self.hold(f"{self.error[0]}: {self.error[2]}")

    def _hit(self, thing: Thing, source: Player | None, kind: str) -> None:
        if not self.active:
            return
        cure = (
            "frost" if kind == "frost" else
            "fire" if kind in FIRE_KINDS else
            "shock" if kind in SHOCK_KINDS else
            "shake" if kind in SHAKE_KINDS else ""
        )
        if cure != self.error[1]:
            self.note(thing.x, thing.y - 40, "ПЕЧАТАЮ ТЕСТОВУЮ СТРАНИЦУ")
            self.bug()
            return
        self.fixes += 1
        self.note(thing.x, thing.y - 40, f"ОШИБКА СБРОШЕНА ({self.fixes} из {PRINTER_FIXES})", good=True)
        if self.fixes >= PRINTER_FIXES:
            self.complete()
        else:
            self._next_error()

    def status(self) -> str:
        return f"{self.error[0]}: {self.error[2]} ({self.fixes} из {PRINTER_FIXES})"

    def bar(self) -> float | None:
        return self.fixes / PRINTER_FIXES


class Mediator(Errand):
    """Walk back and forth between two machines, and choose how to tell each what the other said."""

    ROUNDS = (
        (
            0,
            "Скажите ему: в зале восемнадцать, а он врёт уже десять лет. Прямо так и скажите.",
            "Что он там опять просил передать? Я слушаю.",
            (("rude", "«Он сказал, ты врёшь уже десять лет»"), ("kind", "«У него по приборам восемнадцать. Может, сверитесь?»")),
            {"rude": "Я? ВРУ?! Ну всё, передайте, что у него фильтр не чистили с 2015-го!", "kind": "Сверимся? Хм. Я не против. Если он первый. Сходите к нему."},
        ),
        (
            1,
            "Передайте: ладно, пусть проверит свой термостат. Может, он и не виноват. Нет, этого не говорите. Скажите, что я жду.",
            "Ну? Что говорит градусник? Только не передавайте, если там гадости.",
            (("rude", "«Он сказал проверить термостат»"), ("kind", "«Он готов разобраться и признаёт, что, может, дело не в вас»")),
            {"rude": "Ах, МОЙ термостат! А давайте его калибровку проверим!", "kind": "Он так сказал? Толя? Десять лет... Ладно. Я тоже, может, погорячился. В смысле, поохладился."},
        ),
        (
            0,
            "Скажите, что я уменьшу мощность на два градуса. Но не потому что он прав! Скажите ему это обязательно.",
            "Он что-то ещё сказал?",
            (("rude", "«Он уступит, но ты всё равно неправ»"), ("kind", "«Он убавит на два градуса. Предлагает двадцать два обоим»")),
            {"rude": "Вот он всегда так. Всегда! Нет. Нет больше никаких двух градусов.", "kind": "Двадцать два... Двадцать два меня устроит. Скажите ему, что я... Скажите, что двадцать два."},
        ),
    )

    def setup(self) -> None:
        x, y = self.arena.dungeon.open_near(self.thing.x + 380, self.thing.y + 40, 30.0)
        self.partner = self.quest._add(
            "npc", x, y, self.room, label="Датчик Толя",
            data={"owner": self, "use": "поговорить с датчиком", "partner": True, "chat_at": 0.0, "view": {"sprite": "sensor", "say": "27 градусов. Я всё сказал."}},
        )
        self.round = 0
        self.kind = 0
        self.carrying = False

    def begin(self, player: Player) -> Talk | None:
        self.round = 0
        self.kind = 0
        self.carrying = True
        return Talk(self.ROUNDS[0][1])

    def _pair(self) -> tuple[Thing, Thing]:
        if self.ROUNDS[self.round][0] == 0:
            return self.thing, self.partner
        return self.partner, self.thing

    def on_use(self, thing: Thing, player: Player) -> None:
        if not self.active:
            if thing is self.partner:
                if self.finished:
                    self.folk.show(thing, player, Talk("Двадцать два. Семён подтверждает. Кто бы мог подумать."))
                else:
                    self.folk.show(thing, player, Talk("Двадцать семь градусов, и это медицинский факт. С кондиционером не разговариваю. Спросите его сами."))
                return
            super().on_use(thing, player)
            return
        source, target = self._pair()
        _, message, ask, replies, _reactions = self.ROUNDS[self.round]
        if not self.carrying:
            if thing is source:
                self.carrying = True
                self.folk.show(thing, player, Talk(message))
            else:
                self.folk.show(thing, player, Talk(f"Сходите сначала к другому: {source.label}. Он там что-то бурчит."))
            return
        if thing is target:
            self.folk.show(thing, player, Talk(ask, replies))
        else:
            self.folk.show(thing, player, Talk(f"Я уже всё сказал. Идите: {target.label} ждёт."))

    def answer(self, key: str, player: Player) -> Talk | None:
        _, _, _, _, reactions = self.ROUNDS[self.round]
        line = reactions[key]
        if key == "kind":
            self.kind += 1
        self.round += 1
        self.carrying = False
        if self.round < len(self.ROUNDS):
            return Talk(line)
        if self.kind >= 2:
            self.partner.data["view"]["say"] = "22 градуса. Я так и говорил."
            return self.finish(line + " Спасибо вам. Десять лет молчали.")
        self.started = False
        self.round = 0
        self.kind = 0
        self.refresh_mark()
        self.note(self.thing.x, self.thing.y, "Они поссорились снова")
        self.bug()
        return Talk(line + " ВСЁ. Разговор окончен. Придёте, когда научитесь говорить.")

    def status(self) -> str:
        source, target = self._pair()
        who = target if self.carrying else source
        return f"передавать сообщения, сейчас идти к: {who.label}"

    def bar(self) -> float | None:
        return self.round / len(self.ROUNDS)

    def marks(self) -> list[tuple[float, float, int]]:
        source, target = self._pair()
        who = target if self.carrying else source
        return [(who.x, who.y, who.room)]


class Cable(Errand):
    """Drag a cable to its socket: it is exactly long enough, if you do not wander."""

    wants_space = True

    def begin(self, player: Player) -> Talk | None:
        room = self.room
        self.anchor = self.arena.dungeon.open_near(self.thing.x + 60, self.thing.y, 20.0)
        ends = [
            (room.x + 2.5, room.center[1] / TILE), (room.x + room.w - 2.5, room.center[1] / TILE),
            (room.center[0] / TILE, room.y + 2.5), (room.center[0] / TILE, room.y + room.h - 2.5),
        ]
        far = max(ends, key=lambda c: math.hypot(c[0] * TILE - self.anchor[0], c[1] * TILE - self.anchor[1]))
        x, y = self.arena.dungeon.open_near(far[0] * TILE, far[1] * TILE, 28.0)
        self.socket = self.part("socket", x, y, label="разъём стойки 7")
        walk = self.quest._path_tiles(self.anchor, (x, y)) * TILE
        self.length = max(walk * CABLE_SLACK, math.hypot(x - self.anchor[0], y - self.anchor[1]) * CABLE_SLACK)
        self.holder = 0
        self.called = False
        self.plug = self.part(
            "plug", self.anchor[0], self.anchor[1], label="кабель", use="взять кабель",
            anchor=[round(self.anchor[0], 1), round(self.anchor[1], 1)],
        )
        return Talk("Вот конец. Как возьмёте, на шум сбегутся. Идите прямо, кабель короткий.")

    def talk(self, player: Player) -> Talk | None:
        return Talk("Кабель, разъём, прямо, не гулять. Я подержу. Морально.")

    def use_part(self, part: Thing, player: Player) -> None:
        if part is not self.plug:
            return
        if self.holder == player.id:
            self._snap("Положили кабель, и он уполз обратно")
            return
        if self.holder:
            return
        self.holder = player.id
        part.holder = player.id
        part.data["use"] = "бросить кабель"
        if not self.called:
            self.called = True
            self.bug(self.socket.x, self.socket.y)
            self.bug(self.socket.x, self.socket.y)

    def _snap(self, text: str) -> None:
        plug = self.plug
        self.note(plug.x, plug.y, text)
        self.holder = 0
        plug.holder = 0
        plug.x, plug.y = self.anchor
        plug.data["use"] = "взять кабель"

    def update(self, now: float, dt: float) -> None:
        if not self.active or not self.holder:
            return
        mage = self.arena.players.get(self.holder)
        if mage is None or mage.dead:
            self._snap("Кабель выпал и уполз обратно")
            return
        self.plug.x, self.plug.y = mage.x, mage.y
        if math.hypot(mage.x - self.socket.x, mage.y - self.socket.y) <= CABLE_SOCKET:
            self.complete()
            return
        if math.hypot(mage.x - self.anchor[0], mage.y - self.anchor[1]) > self.length:
            self._snap("Кабель выскочил! Короткий!")

    def status(self) -> str:
        return "дотянуть кабель до разъёма, не отходя в сторону"

    def marks(self) -> list[tuple[float, float, int]]:
        return [(self.socket.x, self.socket.y, self.socket.room)]


# ============================================================== the Core
class Miner(Errand):
    """Walk away while you can: the only rule is that nobody ever does."""

    def setup(self) -> None:
        self.tries = 0
        self.running = False
        self.stake = 15 + 5 * self.arena.stage.chapter_index
        self.rate = 1.0
        self.went_at = 0.0
        self.crash_after = 0.0

    def begin(self, player: Player) -> Talk | None:
        return self._offer()

    def _offer(self) -> Talk:
        return Talk(
            f"Вложение: {self.stake} токенов. Пошло в гору, жмёшь E, забираешь. Передержишь, ничего не получишь. Попыток у меня для тебя {MINER_TRIES - self.tries}.",
            (("stake", f"Вложить {self.stake} токенов"), ("later", LATER_REPLY)),
        )

    def talk(self, player: Player) -> Talk | None:
        return self._offer()

    def answer(self, key: str, player: Player) -> Talk | None:
        if key != "stake":
            return None
        if self.arena.essence < self.stake:
            return Talk("Нет токенов, нет и дохода. Сходи, разбей пару мониторов, и возвращайся.")
        self.arena.essence -= self.stake
        self.running = True
        self.rate = 1.0
        self.went_at = self.now
        self.crash_after = self.rng.uniform(*MINER_CRASH)
        self.thing.data["use"] = "забрать деньги"
        return None

    def on_use(self, thing: Thing, player: Player) -> None:
        if self.running:
            self._cash_out()
            return
        super().on_use(thing, player)

    def _cash_out(self) -> None:
        self.running = False
        amount = round(self.stake * self.rate)
        self.arena.essence += amount
        self.arena.emit({"e": "loot", "x": round(self.thing.x, 1), "y": round(self.thing.y, 1), "amount": amount})
        self.complete(f"Забрал на ×{self.rate:.2f}! И вышел! Я таких не видел. Я и сам так не умею. {self.person.thanks}")

    def update(self, now: float, dt: float) -> None:
        if not self.running:
            return
        passed = now - self.went_at
        self.rate = 1 + 0.11 * passed + 0.012 * passed * passed
        self.thing.data["view"]["rate"] = f"×{self.rate:.2f}"
        if passed < self.crash_after:
            return
        self.running = False
        self.tries += 1
        self.thing.data["view"].pop("rate", None)
        self.thing.data["use"] = f"поговорить: {self.person.name}"
        self.note(self.thing.x, self.thing.y - 50, f"КРАХ на ×{self.rate:.2f}")
        if self.tries >= MINER_TRIES:
            self.complete()
            return
        self.speak("Крах! Это коррекция. Сейчас отрастёт. Ну что, ещё разок?")

    def status(self) -> str:
        if self.running:
            return f"курс ×{self.rate:.2f}: E у деда, чтобы забрать"
        return "поговорить с дедом и вложиться"


ERRANDS: dict[str, type[Errand]] = {
    "calc": Calculator,
    "zina": Modem,
    "webmaster": Webmaster,
    "gosha1": NodeModules,
    "troll": Troll,
    "babka": ChainLetter,
    "cat": Cat,
    "senya": Blogger,
    "petrovich": Moderator,
    "rec": Recommender,
    "gosha2": EnvLeak,
    "diplom": Versions,
    "asya": HotCold,
    "recycle": Recycling,
    "gosha3": Reflog,
    "sync": LagPlates,
    "luba": Mopping,
    "cron": CronClock,
    "printer": Printer,
    "semyon": Mediator,
    "gosha4": Cable,
    "grisha": FactCheck,
    "gosha5": CodeReview,
    "guard": Guard,
    "miner": Miner,
    "maria": Mother,
}


class StageFolk:
    def __init__(self, arena: "StoryArena", known: Mapping[str, str] | None = None) -> None:
        self.arena = arena
        self.quest = arena.quest
        self.rng = random.Random(arena.seed ^ 0xF01C)
        self.known = dict(known or {})
        self.tokens = 10 + 4 * arena.stage.chapter_index
        self.errands: list[Errand] = []
        self.offered: dict[int, tuple[int, set[str]]] = {}
        self.finished: list[tuple[str, str]] = []
        self.hinted = arena.stage.index != 0
        self._settle()

    # ------------------------------------------------------------------- who and where
    def _choose(self) -> list[Person]:
        stage = self.arena.stage
        pool = [person for person in PEOPLE if person.chapter == stage.chapter_index]
        here = stage.number - 1
        waiting = [person for person in pool if self.known.get(person.key) != PASSED]
        waiting.sort(key=lambda person: (person.position != here, person.position > here))
        chosen = waiting[:SLOTS]
        if chosen:
            return chosen
        # Everyone is done: they can be visited again, for less.
        return sorted(pool, key=lambda person: person.position != here)[:SLOTS]

    def _settle(self) -> None:
        dungeon = self.arena.dungeon
        quiet = [room for room in dungeon.sides if room.kind in QUIET_KINDS and not room.guarded]
        fights = [room for room in dungeon.path if room.kind == "combat"]
        taken: set[int] = set()
        for person in self._choose():
            kind = ERRANDS[person.key]
            order = (fights + quiet) if kind.wants_space else (quiet + fights)
            room = next((r for r in order if r.index not in taken), None) or (order[0] if order else dungeon.rooms[0])
            taken.add(room.index)
            self.summon(person.key, room)

    def summon(self, key: str, room: Room) -> Errand:
        person = PERSON_BY_KEY[key]
        x, y = self._seat(room)
        data: dict[str, Any] = {
            "person": key,
            "line": 0,
            "chat_at": 0.0,
            "use": f"поговорить: {person.name}",
            "view": {"sprite": person.sprite},
        }
        thing = self.quest._add("npc", x, y, room, label=person.name, data=data)
        errand = ERRANDS[key](self, person, thing)
        thing.data["owner"] = errand
        errand.refresh_mark()
        self.errands.append(errand)
        return errand

    def _seat(self, room: Room) -> tuple[float, float]:
        """Clear of whatever else E might mean: a chest must not answer for a person."""

        others = [thing for thing in self.quest.things.values() if not thing.gone and thing.data.get("use")]
        best = self.arena.dungeon.open_point(room, self.rng, SEAT_SPOT, margin=2)
        best_gap = -1.0
        for _ in range(30):
            x, y = self.arena.dungeon.open_point(room, self.rng, SEAT_SPOT, margin=2)
            gap = min((math.hypot(x - other.x, y - other.y) for other in others), default=math.inf)
            if gap >= SEAT_CLEAR:
                return x, y
            if gap > best_gap:
                best, best_gap = (x, y), gap
        return best

    def spot(self, room: Room, radius: float = 26.0) -> tuple[float, float]:
        cx, cy = room.center
        for _ in range(40):
            x = cx + self.rng.uniform(-0.36, 0.36) * room.w * TILE
            y = cy + self.rng.uniform(-0.36, 0.36) * room.h * TILE
            if self.arena.can_stand(x, y, radius):
                return x, y
        return self.arena.dungeon.open_near(cx, cy, radius)

    def all_people(self) -> list[Thing]:
        """Everybody one could walk up to and bother, whether or not they have a story."""

        people = [errand.thing for errand in self.errands]
        people += [
            thing for errand in self.errands
            for thing in [getattr(errand, "partner", None)] if thing is not None
        ]
        life = self.arena.life
        if life is not None:
            people += life.residents
        return people

    # ----------------------------------------------------------------------- talking
    def intercept(self, thing: Thing, player: Player) -> bool:
        """Somebody on an errand can make E mean something else for a while."""

        return any(
            errand.intercept(thing, player)
            for errand in self.errands
            if isinstance(errand, ChainLetter)
        )

    def use(self, thing: Thing, player: Player) -> None:
        errand: Errand = thing.data["owner"]
        if thing.kind == "npc":
            if not thing.data.get("met"):
                thing.data["met"] = True
                self.arena.stats.residents += 1
            errand.on_use(thing, player)
        else:
            errand.use_part(thing, player)

    def show(self, thing: Thing, player: Player, talk: Talk | None) -> None:
        if talk is None:
            self.close(player)
            return
        self.offered[player.id] = (thing.id, {key for key, _ in talk.replies})
        event: dict[str, Any] = {
            "e": "npc_talk",
            "to": player.id,
            "thing": thing.id,
            "name": thing.label,
            "sprite": thing.data["view"].get("sprite", ""),
            "text": talk.text,
            "replies": [list(reply) for reply in talk.replies],
        }
        if talk.code:
            event["code"] = talk.code
        self.arena.emit(event)

    def close(self, player: Player) -> None:
        self.offered.pop(player.id, None)
        self.arena.emit({"e": "npc_close", "to": player.id})

    def reply(self, player_id: int, thing_id: int, key: str) -> dict[str, Any]:
        player = self.arena.players.get(player_id)
        offered = self.offered.get(player_id)
        if player is None or player.dead or offered is None:
            return {"ok": False, "error": "Вас уже никто не слушает."}
        wanted, keys = offered
        if wanted != thing_id or key not in keys:
            return {"ok": False, "error": "Вас уже никто не слушает."}
        thing = self.quest.things.get(thing_id)
        if thing is None or thing.gone or math.hypot(thing.x - player.x, thing.y - player.y) > REPLY_REACH:
            self.close(player)
            return {"ok": False, "error": "Вы отошли слишком далеко."}
        del self.offered[player_id]
        errand: Errand = thing.data["owner"]
        accepted = False
        if key == "later":
            talk = None
        elif key == "pgt":
            talk = errand.accept_pgt(player)
            accepted = True
        elif key == "start":
            errand.started = True
            errand.owner = player.id
            talk = errand.begin(player)
            errand.refresh_mark()
        else:
            talk = errand.answer(key, player)
        self.show(thing, player, talk)
        return {"ok": True, "accepted": accepted}

    def pay(self, errand: Errand, status: str = PASSED) -> None:
        amount = self.tokens
        if errand.repeat:
            amount = round(amount * REPEAT_PAY)
        thing = errand.thing
        self.quest._loot(thing.x, thing.y + 40, amount)
        person = errand.person
        if errand.repeat:
            return
        if person.find and status == PASSED and self.arena.life is not None:
            self.arena.life._give_find(FIND_BY_KEY[person.find])
        if status == PASSED or self.known.get(person.key) != PASSED:
            self.known[person.key] = status
        self.finished.append((person.key, status))
        self.arena.emit(
            {"e": "folk_done", "key": person.key, "name": person.name, "test": person.test, "status": status}
        )

    def take_finished(self) -> list[tuple[str, str]]:
        finished, self.finished = self.finished, []
        return finished

    # ------------------------------------------------------------------------ hooks
    def spell_cast(self, player: Player, runes: Any, logs: list[str], ok: bool) -> None:
        for errand in self.errands:
            errand.spell_cast(player, runes, logs, ok)

    def monster_died(self, monster: "Monster", killer: Player | None, kind: str) -> None:
        for errand in self.errands:
            errand.monster_died(monster, killer, kind)

    def update(self, now: float, dt: float) -> None:
        self._update_chatter(now)
        self._drop_strays()
        if not self.hinted:
            self._hint()
        for errand in list(self.errands):
            errand.tick(now, dt)

    def _hint(self) -> None:
        for errand in self.errands:
            if self.quest._toucher(errand.thing.x, errand.thing.y, HINT_REACH) is not None:
                self.hinted = True
                self.quest._say((("Ада", "Это местные. Им тоже плохо, но они не из тех, кто скажет первым. Подойдите и нажмите E. Мне они не отвечают."),))
                return

    def _drop_strays(self) -> None:
        """A conversation does not follow you across the room."""

        for player_id, (thing_id, _) in list(self.offered.items()):
            player = self.arena.players.get(player_id)
            thing = self.quest.things.get(thing_id)
            if player is None or thing is None or thing.gone:
                self.offered.pop(player_id, None)
            elif math.hypot(thing.x - player.x, thing.y - player.y) > REPLY_REACH:
                self.close(player)

    def _update_chatter(self, now: float) -> None:
        living = self.arena.hunted()
        for errand in self.errands:
            thing = errand.thing
            if thing.gone:
                continue
            view = thing.data["view"]
            near = any(math.hypot(m.x - thing.x, m.y - thing.y) <= CHATTER_REACH for m in living)
            if not near:
                view.pop("say", None)
                continue
            if thing.data.get("hold"):
                view["say"] = thing.data["hold"]
                continue
            if now >= thing.data["chat_at"]:
                lines = errand.person.chatter
                if errand.finished and errand.person.after:
                    lines = (errand.person.after,)
                view["say"] = lines[thing.data["line"] % len(lines)]
                thing.data["line"] += 1
                thing.data["chat_at"] = now + CHATTER_EVERY

    # ---------------------------------------------------------------------- reports
    def marks(self) -> list[list[float]]:
        revealed = self.arena.revealed
        return [
            [round(x, 1), round(y, 1)]
            for errand in self.errands if errand.active
            for x, y, room in errand.marks() if room in revealed
        ]

    def snapshot(self) -> dict[str, Any]:
        active = []
        for errand in self.errands:
            if not errand.active:
                continue
            entry: dict[str, Any] = {"name": errand.person.name, "text": errand.status()}
            bar = errand.bar()
            if bar is not None:
                entry["bar"] = round(bar, 3)
            active.append(entry)
        return {"active": active}
