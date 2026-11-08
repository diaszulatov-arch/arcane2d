"""The rune book: spells bought with tokens instead of earned by lessons.

Lessons stay free, because the campaign is built on what they teach.  What is
for sale goes further than the lessons do: searching by string, undoing a move,
passing a function around.  ``daemon`` is the top of the book and the point of
the game: code you wrote keeps fighting after you stopped typing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .game import SpellSession, _api_number
from .interpreter import SpellError, SpellRuntimeError, call_later, is_function

if TYPE_CHECKING:
    from .story import StoryArena

PING_RANGE = 1400.0
PING_RADIUS = 420.0
GC_REACH = 700.0
GC_CLEAN = 320.0
GREP_RANGE = 900.0
GREP_DAMAGE = 14.0
ZIP_RANGE = 640.0
ZIP_RADIUS = 170.0
ZIP_DELAY = 1.2
ZIP_DAMAGE = 58.0
CLONE_TIME = 8.0
LATER_MIN = 0.1
LATER_MAX = 10.0
LATER_LIMIT = 3
DAEMON_EVERY = 0.5
DAEMON_RUNS = 20
DAEMON_LOGS = 3


@dataclass(frozen=True, slots=True)
class BookRune:
    name: str
    title: str
    signature: str
    about: str
    idea: str
    example: str
    price: int
    cost: int
    cooldown: float
    tier: int

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "signature": self.signature,
            "about": self.about,
            "idea": self.idea,
            "example": self.example,
            "price": self.price,
            "cost": self.cost,
            "cooldown": self.cooldown,
            "tier": self.tier,
        }


BOOK: dict[str, BookRune] = {
    entry.name: entry
    for entry in (
        BookRune(
            "ping", "Пинг", "ping(x, y)",
            "Считает врагов вокруг точки, даже за стеной, и загружает комнату под ней. Трещины рядом подсвечиваются.",
            "Функция, которая возвращает значение",
            'p = cursor()\nif p and ping(p.x, p.y) > 3:\n    say("Там толпа")\n',
            price=150, cost=6, cooldown=1.5, tier=1,
        ),
        BookRune(
            "gc", "Сборщик мусора", "gc()",
            "Притягивает все сферы вокруг и убирает ядовитые облака. Возвращает, сколько сфер собрал.",
            "Побочный эффект без аргументов",
            'if me().mana < 30 and ready("gc"):\n    gc()\n',
            price=150, cost=14, cooldown=6.0, tier=1,
        ),
        BookRune(
            "grep", "Поиск по строке", 'grep("cookie")',
            f"Бьёт на {GREP_DAMAGE:.0f} всех врагов рядом, в чьём виде или имени есть эта строка, прямо сквозь стены. Возвращает число попаданий.",
            "Строки и поиск подстроки",
            'hits = grep("cookie")\nlog(f"Нашёл: {hits}")\n',
            price=400, cost=22, cooldown=5.0, tier=2,
        ),
        BookRune(
            "undo", "Отмена", "undo()",
            "Возвращает мага туда, где он был 3 секунды назад, и то здоровье, если оно было выше. Павших не поднимает.",
            "Условие: решить, когда откатываться",
            'if me().hp < me().max_hp * 0.3 and ready("undo"):\n    undo()\n',
            price=400, cost=20, cooldown=14.0, tier=2,
        ),
        BookRune(
            "zip_bomb", "Zip-бомба", "zip_bomb(x, y)",
            f"Через {ZIP_DELAY} с распаковывается в большой взрыв на {ZIP_DAMAGE:.0f} урона. Кто ушёл, тому повезло: цельтесь с упреждением.",
            "Расчёт координат",
            "e = enemies()\nif e:\n    zip_bomb(e[0].x, e[0].y)\n",
            price=400, cost=34, cooldown=4.0, tier=2,
        ),
        BookRune(
            "clone", "Клон", "clone()",
            f"Копия мага на {CLONE_TIME:.0f} с: сама стреляет по ближайшему врагу и оттягивает атаки на себя.",
            "Объекты: тот же класс, другой экземпляр",
            'if len(enemies()) > 4 and ready("clone"):\n    clone()\n',
            price=900, cost=30, cooldown=16.0, tier=3,
        ),
        BookRune(
            "later", "Отложенный вызов", "later(seconds, function, *args)",
            f"Вызовет функцию через {LATER_MIN}–{LATER_MAX:.0f} с. Функция здесь значение: её имя пишут без скобок. Ждать могут не больше {LATER_LIMIT} вызовов сразу.",
            "Функция как значение, колбэк",
            "def combo():\n    nova()\n    shield()\n\nblink(cursor().x, cursor().y)\nlater(0.5, combo)\n",
            price=900, cost=6, cooldown=0.0, tier=3,
        ),
        BookRune(
            "daemon", "Демон", "daemon(function)",
            f"Ваша функция сама запускается каждые {DAEMON_EVERY} с в течение {DAEMON_RUNS * DAEMON_EVERY:.0f} с, пока вы заняты другим. Руны внутри тратят вашу ману, ошибка останавливает демона.",
            "Автоматизация: код работает без вас",
            "def turret():\n    foes = enemies()\n    if foes and me().mana > 40:\n        fireball(direction(foes[0].x, foes[0].y))\n\ndaemon(turret)\n",
            price=1400, cost=30, cooldown=20.0, tier=3,
        ),
    )
}

BOOK_COSTS: dict[str, int] = {entry.name: entry.cost for entry in BOOK.values()}


def describe_book() -> list[dict[str, Any]]:
    return [entry.describe() for entry in BOOK.values()]


@dataclass(slots=True)
class Deferred:
    """A function waiting for its time: once for ``later``, again and again for ``daemon``."""

    session: SpellSession
    function: Any
    args: tuple[Any, ...]
    at: float
    runs: int = 1
    daemon: bool = False


class RuneShelf:
    """The bought runes of one casting, on top of what ``SpellSession`` offers."""

    def __init__(self, world: "StoryArena", session: SpellSession) -> None:
        self.world = world
        self.session = session
        self.player = session.player

    def api(self) -> dict[str, Any]:
        return {name: self._bound(name) for name in BOOK}

    def _bound(self, name: str) -> Any:
        method = getattr(self, name)

        def rune(*args: Any) -> Any:
            if not self.world.rune_known(name, self.player):
                raise SpellRuntimeError(f"Руны {name} нет в вашей Книге: она продаётся в штабе.")
            wait = self.world.skill_wait(self.player, name)
            if wait > 0:
                raise SpellRuntimeError(f"Руна {name} будет готова через {wait:.1f} с.")
            return method(*args)

        return rune

    def _pay(self, name: str) -> None:
        self.session._spend(BOOK[name].cost, name)
        self.player.skill_ready[name] = self.world.now + BOOK[name].cooldown

    def _reach(self, x: Any, y: Any, limit: float) -> tuple[float, float]:
        x_value = _api_number(x, "x")
        y_value = _api_number(y, "y")
        player = self.player
        distance = math.hypot(x_value - player.x, y_value - player.y)
        if distance > limit:
            raise SpellRuntimeError(f"Слишком далеко: до точки {distance:.0f}, можно {limit:.0f}.")
        return x_value, y_value

    # ------------------------------------------------------------------- runes
    def ping(self, x: Any, y: Any) -> int:
        x_value, y_value = self._reach(x, y, PING_RANGE)
        self._pay("ping")
        return self.world.ping(self.player, x_value, y_value, PING_RADIUS)

    def gc(self) -> int:
        self._pay("gc")
        return self.world.collect_garbage(self.player, GC_REACH, GC_CLEAN)

    def grep(self, text: Any) -> int:
        if not isinstance(text, str) or len(text.strip()) < 2:
            raise SpellRuntimeError("grep ищет строку, и в ней хотя бы две буквы.")
        self._pay("grep")
        return self.world.grep(self.player, text.strip().lower(), GREP_RANGE, GREP_DAMAGE)

    def undo(self) -> None:
        self._pay("undo")
        self.world.undo(self.player)

    def zip_bomb(self, x: Any, y: Any) -> None:
        x_value, y_value = self._reach(x, y, ZIP_RANGE)
        self._pay("zip_bomb")
        self.world.place_hazard(
            self.player, x_value, y_value,
            radius=ZIP_RADIUS, delay=ZIP_DELAY, damage=ZIP_DAMAGE,
            color=self.player.color, label="unzip…",
        )

    def clone(self) -> None:
        self._pay("clone")
        self.world.make_clone(self.player, CLONE_TIME)

    def later(self, seconds: Any, function: Any, *args: Any) -> None:
        delay = _api_number(seconds, "seconds")
        if not LATER_MIN <= delay <= LATER_MAX:
            raise SpellRuntimeError(f"later ждёт от {LATER_MIN} до {LATER_MAX:.0f} секунд.")
        self._check_function(function, "later")
        waiting = sum(
            1
            for entry in self.world.deferred
            if entry.session.player is self.player and not entry.daemon
        )
        if waiting >= LATER_LIMIT:
            raise SpellRuntimeError(f"Уже ждут {LATER_LIMIT} отложенных вызова. Хватит.")
        self._pay("later")
        self.world.deferred.append(Deferred(self.session, function, args, self.world.now + delay))

    def daemon(self, function: Any) -> None:
        self._check_function(function, "daemon")
        self.world.deferred[:] = [
            entry
            for entry in self.world.deferred
            if not (entry.daemon and entry.session.player is self.player)
        ]
        self._pay("daemon")
        self.world.deferred.append(
            Deferred(self.session, function, (), self.world.now + DAEMON_EVERY, DAEMON_RUNS, True)
        )
        self.world.emit({"e": "daemon", "id": self.player.id, "time": DAEMON_RUNS * DAEMON_EVERY})

    @staticmethod
    def _check_function(function: Any, rune: str) -> None:
        if not is_function(function):
            raise SpellRuntimeError(
                f"{rune} ждёт функцию. Её имя пишут без скобок: {rune}(..., turret), а не turret()."
            )


def run_deferred(world: "StoryArena", now: float) -> None:
    """Call whatever came due. Each call gets the budget of a fresh cast."""

    remaining: list[Deferred] = []
    due: list[Deferred] = []
    for entry in world.deferred:
        (due if now >= entry.at else remaining).append(entry)
    world.deferred = remaining
    for entry in due:
        player = entry.session.player
        if player.id not in world.players:
            continue
        again = _run_once(world, entry, now)
        entry.runs -= 1
        if again and entry.runs > 0:
            entry.at = now + DAEMON_EVERY
            world.deferred.append(entry)
        elif entry.daemon:
            world.emit({"e": "daemon_end", "id": player.id})


def _run_once(world: "StoryArena", entry: Deferred, now: float) -> bool:
    """Returns whether the entry may run again: a bug in a daemon ends the daemon."""

    player = entry.session.player
    if player.dead or player.id in world.linked or player.stun_until > now:
        return True
    session = entry.session
    session.rewind(now)
    error: str | None = None
    try:
        call_later(session.interpreter, entry.function, entry.args)
    except SpellError as exc:
        error = str(exc)
    except Exception:
        error = "Внутренняя ошибка гримуара."
    if error is not None:
        world.stats.errors += 1
    world.stats.runes.update(session.spent)
    logs = session.logs[:DAEMON_LOGS]
    if error is not None or logs:
        world.emit({"e": "spell_log", "id": player.id, "log": logs, "error": error})
    return error is None
