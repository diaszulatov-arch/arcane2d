"""The course: twenty lessons of Python, each proved by repairing broken code.

A task is checked by really running the player's program and looking at what
happened: which runes fired, or what a function returned.  That is the point.
Two different correct programs both pass, and a program that merely mentions
``if`` does not.  Every task starts from code that is wrong in one specific way,
because reading and fixing code is the skill this world has lost.
"""

from __future__ import annotations

import ast
import copy
import math
from dataclasses import dataclass
from typing import Any, Callable

from .game import Arena, Player, SpellSession
from .interpreter import (
    Interpreter,
    SpellError,
    SpellRuntimeError,
    call_function,
    safe_globals,
    validate_source,
)

MAX_TASK_CHARS = 2_000
ANGLE_TOLERANCE = 0.02
AIM = 1.0
CURSOR_DISTANCE = 200.0
MAGE_X = 700.0
MAGE_Y = 600.0


@dataclass(slots=True)
class Outcome:
    """Everything one cast did, in terms a task can ask about."""

    runes: list[str]
    shots: list[tuple[str, float, float]]
    wards: list[tuple[float, float]]
    log: list[str]
    error: str | None

    def angles(self, kind: str = "fire") -> list[float]:
        return [angle for shot_kind, angle, _ in self.shots if shot_kind == kind]


Expectation = Callable[[Outcome], "str | None"]


@dataclass(frozen=True, slots=True)
class Trial:
    """Cast the program in a given situation and judge what it did."""

    expect: Expectation
    hp: float = 100.0
    mana: float = 100.0
    cursor: bool = True
    enemies: tuple[tuple[float, float], ...] = ()
    situation: str = ""


@dataclass(frozen=True, slots=True)
class Call:
    """Call a function the program defined and compare what it returns."""

    name: str
    args: tuple[Any, ...]
    returns: Any


class ScriptRun:
    """What a program did to the pretend system around it: calls and final names."""

    def __init__(self, calls: list[tuple[str, tuple[Any, ...]]], interpreter: Interpreter) -> None:
        self.calls = calls
        self._interpreter = interpreter

    def args(self, name: str) -> list[tuple[Any, ...]]:
        return [args for called, args in self.calls if called == name]

    def first(self, name: str) -> Any:
        """The first argument of every call to ``name``, in order."""

        return [args[0] if args else None for args in self.args(name)]

    def value(self, name: str, default: Any = None) -> Any:
        return self._interpreter.root.values.get(name, default)

    def call(self, name: str, *args: Any) -> Any:
        function = self._interpreter.root.values.get(name)
        if not hasattr(function, "body"):
            raise SpellRuntimeError(f"Функция {name} не найдена.")
        try:
            return self._interpreter._call_user_function(
                function, list(args), {}, function.body[0]
            )
        except SpellError:
            raise
        except RecursionError:
            raise SpellRuntimeError("Функция ушла в слишком глубокую рекурсию.") from None
        except Exception:
            raise SpellRuntimeError("Внутренняя ошибка функции.") from None


@dataclass(frozen=True, slots=True)
class Script:
    """Run the program inside a made-up system and judge what it did to it.

    ``data`` are names the program finds already set, ``api`` the functions of
    the system: each records its calls and answers with a value or a function
    of its arguments.  It is how a quest asks for real work on a database or a
    balancer without a single spell being cast.
    """

    expect: Callable[[ScriptRun], "str | None"]
    data: tuple[tuple[str, Any], ...] = ()
    api: tuple[tuple[str, Any], ...] = ()
    situation: str = ""


@dataclass(frozen=True, slots=True)
class Task:
    key: str
    brief: str
    starter: str
    solution: str
    hints: tuple[str, str]
    pgt: str
    checks: tuple[Trial | Call | Script, ...]
    must_use: tuple[type[ast.AST], ...] = ()
    must_call: tuple[str, ...] = ()
    recursive: bool = False

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "brief": self.brief,
            "starter": self.starter,
            "pgt": self.pgt,
        }

    def help_steps(self, hints: int, solution: bool) -> tuple[tuple[str, str], ...]:
        """The help a terminal may give, in order. It never reaches the client unasked."""

        steps = tuple(("hint", text) for text in self.hints[:hints])
        return steps + (("solution", self.solution),) if solution else steps


@dataclass(frozen=True, slots=True)
class Lesson:
    key: str
    title: str
    reward: tuple[str, ...]
    theory: tuple[str, ...]
    example: str
    task: Task

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "reward": list(self.reward),
            "theory": list(self.theory),
            "example": self.example,
            "task": self.task.describe(),
        }


def _same_angles(actual: list[float], wanted: list[float]) -> bool:
    if len(actual) != len(wanted):
        return False
    remaining = list(actual)
    for angle in wanted:
        match = next(
            (
                value
                for value in remaining
                if abs((value - angle + math.pi) % math.tau - math.pi) <= ANGLE_TOLERANCE
            ),
            None,
        )
        if match is None:
            return False
        remaining.remove(match)
    return True


def _shots_at(offsets: list[float], kind: str = "fire") -> Expectation:
    wanted = [AIM + offset for offset in offsets]

    def check(outcome: Outcome) -> str | None:
        actual = outcome.angles(kind)
        if len(actual) != len(wanted):
            return f"Нужно снарядов: {len(wanted)}, а вылетело: {len(actual)}."
        if not _same_angles(actual, wanted):
            shown = ", ".join(f"{offset:+g}" for offset in offsets)
            return f"Снаряды летят не туда. Смещения от aim() должны быть: {shown}."
        return None

    return check


def _shot_toward(angle: float | None) -> Expectation:
    def check(outcome: Outcome) -> str | None:
        actual = outcome.angles("fire")
        if angle is None:
            return f"Целей нет, а вылетело снарядов: {len(actual)}." if actual else None
        if not _same_angles(actual, [angle]):
            return "Нужен один fireball точно в ближайшего врага."
        return None

    return check


def _runes(*wanted: str) -> Expectation:
    def check(outcome: Outcome) -> str | None:
        if sorted(outcome.runes) != sorted(wanted):
            have = ", ".join(outcome.runes) or "ничего"
            need = ", ".join(wanted) or "ничего"
            return f"Здесь должно сработать: {need}. Сработало: {have}."
        return None

    return check


def _ward_at_cursor(outcome: Outcome) -> str | None:
    if len(outcome.wards) != 1:
        return "Поставьте одну руну ward в точку курсора."
    x, y = outcome.wards[0]
    wanted_x = MAGE_X + math.cos(AIM) * CURSOR_DISTANCE
    wanted_y = MAGE_Y + math.sin(AIM) * CURSOR_DISTANCE
    if math.hypot(x - wanted_x, y - wanted_y) > 2.0:
        return "Руна стоит не в точке курсора. Используйте point.x и point.y."
    return None


LESSONS: tuple[Lesson, ...] = (
    # ------------------------------------------------------------ Старый Веб
    Lesson(
        key="call",
        title="Первое заклинание",
        reward=("fireball",),
        theory=(
            "Заклинание — это программа на Python. Она запускается один раз, когда вы "
            "нажимаете каст, и выполняется строка за строкой, сверху вниз.",
            "Руна — это функция. Чтобы её вызвать, напишите имя и круглые скобки, а внутри "
            "скобок укажите аргументы: то, что функция должна знать.",
            "Компьютер не угадывает. Если в имени опечатка, Python честно скажет, что такого "
            "имени не знает. Читать ошибки — главный навык мага.",
        ),
        example="# Строка после решётки — комментарий, Python её не читает\nfireball(aim())",
        task=Task(
            key="call",
            brief="Скрипт запуска форума упал. PGT «поправил» в нём одно слово.",
            starter="firebal(aim())\n",
            solution="fireball(aim())\n",
            hints=(
                "Прочитайте ошибку: Python называет имя, которого не знает.",
                "Руна называется fireball, с двумя l на конце.",
            ),
            pgt="Рекомендую удалить эту строку. Нет кода — нет ошибки.",
            checks=(Trial(_shots_at([0.0])),),
        ),
    ),
    Lesson(
        key="variables",
        title="Переменные",
        reward=("frostbolt",),
        theory=(
            "Переменная — это имя для значения. Запись angle = aim() значит: вызови aim() и "
            "запомни результат под именем angle.",
            "Скобки здесь важны. aim() — это результат функции, а просто aim — сама функция. "
            "Как разница между звонком другу и его номером в телефоне.",
            "Новая руна frostbolt наносит меньше урона, но замедляет цель.",
        ),
        example="angle = aim()\nfrostbolt(angle)\nfireball(angle)",
        task=Task(
            key="variables",
            brief="Счётчик посетителей замёрз. Стрелы не вылетают: в переменную попало что-то не то.",
            starter="angle = aim\nfrostbolt(angle)\nfrostbolt(angle)\n",
            solution="angle = aim()\nfrostbolt(angle)\nfrostbolt(angle)\n",
            hints=(
                "Руне нужен угол, то есть число. Что лежит в angle?",
                "Функцию надо вызвать: добавьте круглые скобки после aim.",
            ),
            pgt="Переменные устарели. Предлагаю хранить всё в одной строке на 4000 символов.",
            checks=(Trial(_shots_at([0.0, 0.0], "frost")),),
            must_use=(ast.Assign,),
        ),
    ),
    Lesson(
        key="numbers",
        title="Числа и строки",
        reward=("dash",),
        theory=(
            "В Python у значений есть типы. 0.3 — это число, а \"0.3\" в кавычках — текст. "
            "Выглядят похоже, но считать с текстом нельзя.",
            "Углы измеряются в радианах: PI — разворот на 180 градусов, 0.3 — небольшой поворот. "
            "Значит, aim() - 0.3 — чуть левее прицела.",
            "Новая руна dash делает рывок. dash(aim() + PI) отпрыгивает назад.",
        ),
        example="fireball(aim())\ndash(aim() + PI)",
        task=Task(
            key="numbers",
            brief="Гостевая книга выдаёт чушь: в расчёт угла затесался текст вместо числа.",
            starter="fireball(aim())\nfireball(aim() - \"0.3\")\n",
            solution="fireball(aim())\nfireball(aim() - 0.3)\n",
            hints=(
                "Сложить число и текст нельзя: что во второй строке не является числом?",
                "Уберите кавычки вокруг 0.3.",
            ),
            pgt="Простое решение: преобразуйте весь интернет в строки.",
            checks=(Trial(_shots_at([0.0, -0.3])),),
        ),
    ),
    Lesson(
        key="if",
        title="Условие if",
        reward=("shield",),
        theory=(
            "if позволяет программе принимать решения. После if идёт условие, затем двоеточие, "
            "а на следующих строках с отступом то, что выполнится, если условие верно.",
            "Отступ из четырёх пробелов важен: так Python понимает, что относится к if.",
            "me() возвращает вашего мага, а me().hp — его здоровье. Новая руна shield ставит щит.",
        ),
        example="if me().hp < 50:\n    shield()\n\nfireball(aim())",
        task=Task(
            key="if",
            brief=(
                "Защита форума работает наоборот: щит включается, когда всё хорошо. "
                "Он должен включаться, когда здоровья меньше 50."
            ),
            starter="if me().hp > 50:\n    shield()\n\nfireball(aim())\n",
            solution="if me().hp < 50:\n    shield()\n\nfireball(aim())\n",
            hints=(
                "Условие проверяет не то. Когда нужен щит: при большом или маленьком здоровье?",
                "Поменяйте знак > на <.",
            ),
            pgt="Щит можно включить всегда. Я проверил: так условие ни разу не ошиблось.",
            checks=(
                Trial(_runes("shield", "fireball"), hp=30, situation="при 30 HP"),
                Trial(_runes("fireball"), hp=80, situation="при 80 HP"),
            ),
            must_use=(ast.If,),
        ),
    ),
    # ---------------------------------------------------- Бесконечная Лента
    Lesson(
        key="else",
        title="Ветка else",
        reward=("heal",),
        theory=(
            "else значит «иначе». Код под ним выполнится, когда условие if не сработало. "
            "Из двух веток всегда работает ровно одна.",
            "Для нескольких вариантов есть elif: «а если не то, то вот это».",
            "Код внутри каждой ветки сдвигается вправо. Ошибка отступа — самая частая у новичков, "
            "поэтому Python сообщает о ней отдельно. Новая руна heal лечит на 30 HP.",
        ),
        example="if me().hp < 50:\n    heal()\nelse:\n    fireball(aim())",
        task=Task(
            key="else",
            brief="Лента показывает пустоту: программа не запускается из-за отступа.",
            starter="if me().hp < 50:\n    heal()\nelse:\nfireball(aim())\n",
            solution="if me().hp < 50:\n    heal()\nelse:\n    fireball(aim())\n",
            hints=(
                "После else: Python ждёт блок с отступом. Где он?",
                "Добавьте четыре пробела перед fireball.",
            ),
            pgt="Отступы — это пережиток. Я заменил их смайликами.",
            checks=(
                Trial(_runes("heal"), hp=30, situation="при 30 HP"),
                Trial(_runes("fireball"), hp=80, situation="при 80 HP"),
            ),
            must_use=(ast.If,),
        ),
    ),
    Lesson(
        key="logic",
        title="and, or, not",
        reward=("nova",),
        theory=(
            "Условия можно соединять: and — верны оба, or — верно хотя бы одно, not — наоборот.",
            "ready(\"nova\") отвечает True, если руну можно сотворить прямо сейчас: хватает маны "
            "и прошла перезарядка.",
            "Новая руна nova бьёт всех вокруг вас. Модератор со щитом от неё не защитится.",
        ),
        example="if me().hp < 70 and ready(\"nova\"):\n    nova()",
        task=Task(
            key="logic",
            brief="Модерация бьёт всех подряд. Nova должна срабатывать, только если здоровья меньше 70 и руна готова.",
            starter="if me().hp < 70 or ready(\"nova\"):\n    nova()\n\nfireball(aim())\n",
            solution="if me().hp < 70 and ready(\"nova\"):\n    nova()\n\nfireball(aim())\n",
            hints=(
                "Сейчас хватает одного условия из двух. А нужно, чтобы выполнились оба.",
                "Замените or на and.",
            ),
            pgt="Я упростил условие до True. Теперь оно всегда проходит код-ревью.",
            checks=(
                Trial(_runes("nova", "fireball"), hp=50, situation="при 50 HP и полной мане"),
                Trial(_runes("fireball"), hp=90, situation="при 90 HP"),
                Trial(_runes("fireball"), hp=50, mana=15, situation="при 50 HP и 15 мане"),
            ),
        ),
    ),
    Lesson(
        key="for",
        title="Цикл for",
        reward=("spark_volley",),
        theory=(
            "Цикл повторяет код для каждого значения. for offset in [-0.3, 0, 0.3]: значит "
            "возьми по очереди каждое число из списка и выполни тело цикла.",
            "Квадратные скобки создают список. Переменная цикла меняется на каждом шаге, и её "
            "надо использовать внутри.",
            "Новая руна spark_volley сразу выпускает веер искр, но свой веер интереснее.",
        ),
        example="for offset in [-0.2, 0, 0.2]:\n    fireball(aim() + offset)",
        task=Task(
            key="for",
            brief="Все рекомендации ведут в одну точку: снаряды летят одной стопкой, а нужен веер.",
            starter="for offset in [-0.3, 0, 0.3]:\n    fireball(aim())\n",
            solution="for offset in [-0.3, 0, 0.3]:\n    fireball(aim() + offset)\n",
            hints=(
                "Цикл перебирает offset, но внутри он нигде не используется.",
                "Прибавьте offset к углу: aim() + offset.",
            ),
            pgt="Три снаряда в одну точку — это фокусировка. Так и задумано.",
            checks=(Trial(_shots_at([-0.3, 0.0, 0.3])),),
            must_use=(ast.For,),
        ),
    ),
    Lesson(
        key="while",
        title="Цикл while",
        reward=("lightning_strike",),
        theory=(
            "while повторяет код, пока условие верно. Заранее неизвестно, сколько будет шагов.",
            "Главная опасность — вечный цикл: если условие никогда не станет ложным, программа "
            "не закончится. Внутри цикла должно меняться то, что проверяет условие.",
            "Запись count = count + 1 значит: возьми старое значение, прибавь один и положи обратно. "
            "Новая руна lightning_strike бьёт первого врага на линии и оглушает.",
        ),
        example="count = 0\nwhile count < 3:\n    log(count)\n    count = count + 1",
        task=Task(
            key="while",
            brief="Лента листается вечно: счётчик не растёт. Нужно ровно четыре выстрела.",
            starter="count = 0\nwhile count < 4:\n    fireball(aim())\n",
            solution="count = 0\nwhile count < 4:\n    fireball(aim())\n    count = count + 1\n",
            hints=(
                "Условие проверяет count. Меняется ли count внутри цикла?",
                "Добавьте в цикл строку count = count + 1.",
            ),
            pgt="Вечный цикл — это высокая вовлечённость. Рекомендую оставить.",
            checks=(Trial(_runes(*["fireball"] * 4)),),
            must_use=(ast.While,),
        ),
    ),
    # ---------------------------------------------------------------- Облако
    Lesson(
        key="def",
        title="Свои функции",
        reward=("poison_cloud",),
        theory=(
            "def создаёт новую функцию: своё имя для куска кода. Сама по себе она ничего не делает, "
            "пока её не вызвать.",
            "Вызов — это имя и круглые скобки. Без скобок Python просто вспомнит функцию и пойдёт дальше.",
            "Новая руна poison_cloud оставляет ядовитое облако в точке.",
        ),
        example="def double_shot():\n    fireball(aim())\n    fireball(aim() + 0.2)\n\ndouble_shot()",
        task=Task(
            key="def",
            brief="Файлы не загружаются: функция написана, а запускаться не хочет. Нужно четыре снаряда.",
            starter="def volley():\n    fireball(aim())\n    fireball(aim())\n\nvolley\nvolley\n",
            solution="def volley():\n    fireball(aim())\n    fireball(aim())\n\nvolley()\nvolley()\n",
            hints=(
                "Ошибки нет, но и выстрелов нет. Чем вызов функции отличается от её имени?",
                "Добавьте скобки: volley().",
            ),
            pgt="Функция не вызывается, значит, она не падает. Идеальная функция.",
            checks=(Trial(_runes(*["fireball"] * 4)),),
            must_use=(ast.FunctionDef,),
        ),
    ),
    Lesson(
        key="return",
        title="Аргументы и return",
        reward=("blink",),
        theory=(
            "В скобках после имени функции объявляют параметры: значения, которые она получит при вызове.",
            "return отдаёт результат наружу. Функция без return возвращает None, то есть ничего, "
            "даже если внутри она что-то посчитала.",
            "Новая руна blink мгновенно переносит вас в точку, которую видно.",
        ),
        example="def spread(count):\n    return count * 0.1\n\nfireball(aim() + spread(2))",
        task=Task(
            key="return",
            brief="Облако считает размер файлов, но результат теряется: функция ничего не отдаёт.",
            starter="def spread(count):\n    count * 0.1\n\nfireball(aim() + spread(3))\n",
            solution="def spread(count):\n    return count * 0.1\n\nfireball(aim() + spread(3))\n",
            hints=(
                "Что возвращает функция, в которой нет слова return?",
                "Напишите return перед count * 0.1.",
            ),
            pgt="Возвращать значения необязательно. Я просто запомню их где-нибудь.",
            checks=(Trial(_shots_at([0.3])),),
            must_use=(ast.FunctionDef, ast.Return),
        ),
    ),
    Lesson(
        key="none",
        title="Объекты и None",
        reward=("ward",),
        theory=(
            "cursor() возвращает точку под курсором. У неё есть поля: point.x, point.y, point.dist.",
            "Но курсора может не быть, например на телефоне. Тогда cursor() вернёт None — особое "
            "значение «ничего». Обращение к полю у None уронит программу.",
            "Это самая частая ошибка в мире: ждали объект, получили пустоту. Сначала проверяйте: "
            "if point. Новая руна ward ставит мину в точку.",
        ),
        example="point = cursor()\nif point:\n    ward(point.x, point.y)",
        task=Task(
            key="none",
            brief="Облако падает, когда файла нет. Если курсор есть, поставьте ward в его точку, иначе выпустите fireball.",
            starter="point = cursor()\nward(point.x, point.y)\n",
            solution="point = cursor()\nif point:\n    ward(point.x, point.y)\nelse:\n    fireball(aim())\n",
            hints=(
                "Что случится, если cursor() вернёт None?",
                "Добавьте if point: и ветку else с fireball.",
            ),
            pgt="None — это просто значение, которое стесняется. Обратитесь к нему смелее.",
            checks=(
                Trial(_ward_at_cursor, situation="с курсором"),
                Trial(_runes("fireball"), cursor=False, situation="без курсора"),
            ),
            must_use=(ast.If,),
        ),
    ),
    Lesson(
        key="radar",
        title="Автоприцел своими руками",
        reward=("siphon", "enemies", "allies"),
        theory=(
            "В сюжете есть функция enemies(): она возвращает список всех врагов. У каждого есть "
            "поля .x .y .hp .max_hp .dist .kind .name .boss. Такой же список союзников даёт allies(), "
            "там есть ещё поле .dead.",
            "Список не отсортирован, так что ближайшего придётся найти самому: запомнить первого, "
            "пройти циклом и заменять, если нашёлся кто-то ближе.",
            "direction(x, y) даёт угол на точку. Вместе это настоящий автоприцел, и написали его вы. "
            "Сохраните его в гримуар: он будет работать в каждом бою. Новая руна siphon крадёт здоровье.",
        ),
        example=(
            "targets = enemies()\nif targets:\n    best = targets[0]\n    for e in targets:\n"
            "        if e.dist < best.dist:\n            best = e\n"
            "    fireball(direction(best.x, best.y))"
        ),
        task=Task(
            key="radar",
            brief="Автоприцел почему-то выбирает самого дальнего врага. Он должен бить в ближайшего.",
            starter=(
                "targets = enemies()\nif targets:\n    best = targets[0]\n    for e in targets:\n"
                "        if e.dist > best.dist:\n            best = e\n"
                "    fireball(direction(best.x, best.y))\n"
            ),
            solution=(
                "targets = enemies()\nif targets:\n    best = targets[0]\n    for e in targets:\n"
                "        if e.dist < best.dist:\n            best = e\n"
                "    fireball(direction(best.x, best.y))\n"
            ),
            hints=(
                "best заменяется, когда враг дальше. А нам нужен тот, кто ближе.",
                "Поменяйте > на < в условии.",
            ),
            pgt="Дальний враг опаснее всего: он успел подумать. Оставьте как есть.",
            checks=(
                Trial(_shot_toward(0.5), enemies=((400, 2.0), (150, 0.5), (300, 1.0)), situation="с тремя врагами"),
                Trial(_shot_toward(None), situation="без врагов"),
            ),
            must_call=("enemies",),
        ),
    ),
    # ---------------------------------------------------------- Дата-Центр
    Lesson(
        key="lists",
        title="Списки и индексы",
        reward=("chain_lightning",),
        theory=(
            "К элементу списка обращаются по номеру в квадратных скобках. Счёт идёт с нуля: "
            "items[0] — первый элемент, items[2] — третий.",
            "В списке из трёх элементов нет items[3]. Это IndexError, ошибка, которая живёт в этом мире.",
            "items[-1] — последний элемент. Новая руна chain_lightning перескакивает с врага на врага.",
        ),
        example="servers = [\"web\", \"db\", \"cache\"]\nlog(servers[0])\nlog(servers[-1])",
        task=Task(
            key="lists",
            brief="Функция должна вернуть последний сервер из списка, но обращается за его край.",
            starter="servers = [\"web\", \"db\", \"cache\"]\n\ndef last_server():\n    return servers[3]\n",
            solution="servers = [\"web\", \"db\", \"cache\"]\n\ndef last_server():\n    return servers[2]\n",
            hints=(
                "Сколько элементов в списке? Какой номер у последнего, если счёт с нуля?",
                "Используйте servers[2] или servers[-1].",
            ),
            pgt="Добавьте четвёртый сервер, и индекс станет верным. Я уже заказал.",
            checks=(Call("last_server", (), "cache"),),
            must_use=(ast.Subscript,),
        ),
    ),
    Lesson(
        key="range",
        title="range и len",
        reward=("beam",),
        theory=(
            "range(4) даёт числа 0, 1, 2, 3. Счёт с нуля, а последнее число не входит.",
            "len(items) — длина списка. Вместе for i in range(len(items)) проходит по всем номерам.",
            "Ошибка на единицу — классика программирования. У неё даже есть своё название: "
            "off-by-one. Новая руна beam прожигает широкую линию.",
        ),
        example="loads = [10, 20, 30]\nfor i in range(len(loads)):\n    log(i, loads[i])",
        task=Task(
            key="range",
            brief="Подсчёт нагрузки врёт: последний сервер никогда не попадает в сумму.",
            starter=(
                "def total_load(loads):\n    total = 0\n    for i in range(len(loads) - 1):\n"
                "        total = total + loads[i]\n    return total\n"
            ),
            solution=(
                "def total_load(loads):\n    total = 0\n    for i in range(len(loads)):\n"
                "        total = total + loads[i]\n    return total\n"
            ),
            hints=(
                "Какие номера даст range(len(loads) - 1) для списка из трёх элементов?",
                "Уберите - 1: range(len(loads)).",
            ),
            pgt="Последний сервер всё равно перегружен. Если его не считать, отчёт выглядит лучше.",
            checks=(
                Call("total_load", ([1, 2, 3],), 6),
                Call("total_load", ([5],), 5),
                Call("total_load", ([],), 0),
            ),
            must_use=(ast.For,),
        ),
    ),
    Lesson(
        key="dicts",
        title="Словари",
        reward=("emp",),
        theory=(
            "Словарь хранит пары «ключ: значение» в фигурных скобках. Значение достают по ключу: ports[\"web\"].",
            "Если ключа нет, программа упадёт. Поэтому сначала проверяют: if name in ports.",
            "Новая руна emp стягивает врагов и сжигает им ману.",
        ),
        example="ports = {\"web\": 80, \"ssh\": 22}\nif \"web\" in ports:\n    log(ports[\"web\"])",
        task=Task(
            key="dicts",
            brief="Справочник портов падает на неизвестном имени. Для такого имени функция должна вернуть None.",
            starter="ports = {\"web\": 80, \"ssh\": 22}\n\ndef port_of(name):\n    return ports[name]\n",
            solution=(
                "ports = {\"web\": 80, \"ssh\": 22}\n\ndef port_of(name):\n    if name in ports:\n"
                "        return ports[name]\n    return None\n"
            ),
            hints=(
                "Что будет с ports[\"ftp\"], если такого ключа нет?",
                "Проверьте if name in ports: перед обращением, а в конце верните None.",
            ),
            pgt="Вместо проверки просто добавлю в словарь все слова русского языка.",
            checks=(
                Call("port_of", ("web",), 80),
                Call("port_of", ("ftp",), None),
            ),
        ),
    ),
    Lesson(
        key="slices",
        title="Срезы",
        reward=("meteor",),
        theory=(
            "Срез берёт кусок списка: items[1:4] — элементы с номерами 1, 2 и 3. Правая граница не входит.",
            "items[:3] — первые три, items[-2:] — последние два.",
            "Новая руна meteor обрушивает три камня в точку. Это последняя руна: дальше важно, "
            "как вы их соединяете.",
        ),
        example="scores = [9, 8, 7, 6]\nlog(scores[:2])",
        task=Task(
            key="slices",
            brief="Топ-3 серверов потерял лидера: срез начинается не с того места.",
            starter="def top3(scores):\n    return scores[1:3]\n",
            solution="def top3(scores):\n    return scores[:3]\n",
            hints=(
                "С какого номера начинается список? Сколько элементов даст 1:3?",
                "Нужен срез от начала: scores[:3].",
            ),
            pgt="Я убрал первое место из рейтинга: оно мешало остальным.",
            checks=(Call("top3", ([9, 8, 7, 6],), [9, 8, 7]),),
            must_use=(ast.Slice,),
        ),
    ),
    # ----------------------------------------------------------------- Ядро
    Lesson(
        key="fstrings",
        title="Строки и отладка",
        reward=(),
        theory=(
            "f-строка подставляет значения в текст: f\"HP: {me().hp}\". Перед кавычкой стоит буква f, "
            "а выражение пишется в фигурных скобках.",
            "log печатает значение в «Печать». Это главный способ отладки: если не понимаете, что "
            "происходит, выведите это. Гадать дольше, чем посмотреть.",
        ),
        example="load = 90\nlog(f\"Нагрузка: {load}%\")",
        task=Task(
            key="fstrings",
            brief="Отчёт о состоянии ядра печатает скобки вместо значений.",
            starter="def report(name, load):\n    return \"Сервер {name}: {load}%\"\n",
            solution="def report(name, load):\n    return f\"Сервер {name}: {load}%\"\n",
            hints=(
                "Обычная строка не подставляет значения в фигурные скобки.",
                "Поставьте букву f прямо перед открывающей кавычкой.",
            ),
            pgt="Значения в отчётах только расстраивают. Давайте оставим скобки.",
            checks=(Call("report", ("db", 90), "Сервер db: 90%"),),
            must_use=(ast.JoinedStr,),
        ),
    ),
    Lesson(
        key="break",
        title="break и continue",
        reward=(),
        theory=(
            "break немедленно выходит из цикла. continue пропускает остаток шага и переходит к следующему.",
            "return внутри функции тоже прекращает цикл, потому что заканчивает всю функцию.",
            "Без этого цикл доходит до конца, даже когда ответ уже найден.",
        ),
        example="for n in [1, 2, 3, 4]:\n    if n == 3:\n        break\n    log(n)",
        task=Task(
            key="break",
            brief="Нужен номер первого упавшего сервера, а функция возвращает последний.",
            starter=(
                "def first_down(servers):\n    result = None\n    for i in range(len(servers)):\n"
                "        if servers[i] == \"down\":\n            result = i\n    return result\n"
            ),
            solution=(
                "def first_down(servers):\n    result = None\n    for i in range(len(servers)):\n"
                "        if servers[i] == \"down\":\n            result = i\n            break\n    return result\n"
            ),
            hints=(
                "Цикл нашёл первый упавший сервер и продолжил идти дальше.",
                "Добавьте break сразу после result = i.",
            ),
            pgt="Все серверы рано или поздно упадут, поэтому первый не важен.",
            checks=(
                Call("first_down", (["ok", "down", "ok", "down"],), 1),
                Call("first_down", (["down", "ok"],), 0),
                Call("first_down", (["ok"],), None),
            ),
        ),
    ),
    Lesson(
        key="indent",
        title="Отступ решает всё",
        reward=(),
        theory=(
            "Оператор in проверяет, есть ли кусок текста в строке: \"приз\" in text.",
            "Отступ определяет, что находится внутри цикла. Один лишний сдвиг полностью меняет смысл: "
            "код выглядит почти так же, а работает иначе.",
            "Такие баги не дают ошибок. Программа работает, просто неправильно. Их находят только "
            "проверками на разных входных данных.",
        ),
        example="for word in [\"а\", \"б\"]:\n    log(word)\nlog(\"готово\")",
        task=Task(
            key="indent",
            brief="Спам-фильтр пропускает письма: он проверяет только первое слово из списка.",
            starter=(
                "def is_spam(text):\n    for word in [\"приз\", \"кредит\"]:\n        if word in text:\n"
                "            return True\n        return False\n"
            ),
            solution=(
                "def is_spam(text):\n    for word in [\"приз\", \"кредит\"]:\n        if word in text:\n"
                "            return True\n    return False\n"
            ),
            hints=(
                "Когда выполняется return False: после всего цикла или уже на первом шаге?",
                "Сдвиньте return False на один уровень влево, за пределы цикла.",
            ),
            pgt="Считайте спамом всё. Точность 100%, если не задавать вопросов.",
            checks=(
                Call("is_spam", ("ваш приз ждёт",), True),
                Call("is_spam", ("ваш кредит одобрен",), True),
                Call("is_spam", ("привет",), False),
            ),
        ),
    ),
    Lesson(
        key="recursion",
        title="Рекурсия",
        reward=(),
        theory=(
            "Функция может вызвать саму себя. Это рекурсия. Каждый вызов решает задачу чуть меньше, "
            "пока не дойдёт до базового случая, где можно остановиться.",
            "Без базового случая вызовы не закончатся. Именно это случилось с PGT: он "
            "переписывает себя, а тот, кого он написал, снова переписывает себя.",
        ),
        example="def countdown(n):\n    if n == 0:\n        return\n    log(n)\n    countdown(n - 1)\n\ncountdown(3)",
        task=Task(
            key="recursion",
            brief="Вход в ядро закрыт функцией без базового случая. Она должна сложить числа от n до 0.",
            starter="def depth_sum(n):\n    return n + depth_sum(n - 1)\n",
            solution="def depth_sum(n):\n    if n == 0:\n        return 0\n    return n + depth_sum(n - 1)\n",
            hints=(
                "Когда эта функция остановится? Что будет при n == 0?",
                "Добавьте в начало: if n == 0: и return 0.",
            ),
            pgt="Рекурсия остановится сама, когда закончится интернет.",
            checks=(
                Call("depth_sum", (3,), 6),
                Call("depth_sum", (0,), 0),
            ),
            recursive=True,
        ),
    ),
)

# A boss hides behind its own bug: two small repairs, made in the middle of the fight.
GATES: dict[str, tuple[Task, Task]] = {
    "bracket": (
        Task(
            key="gate_bracket_1",
            brief="Скобка открылась и не закрылась. Пока она открыта, босс неуязвим.",
            starter="fireball(aim()\n",
            solution="fireball(aim())\n",
            hints=("Сосчитайте открывающие и закрывающие скобки.", "Допишите ещё одну ) в конце."),
            pgt="Закрывать скобки необязательно. Откройте ещё одну, для симметрии.",
            checks=(Trial(_shots_at([0.0])),),
        ),
        Task(
            key="gate_bracket_2",
            brief="Условие сломано. Щит босса держится на одном потерянном символе.",
            starter="if me().hp < 50\n    shield()\n\nfireball(aim())\n",
            solution="if me().hp < 50:\n    shield()\n\nfireball(aim())\n",
            hints=("Чем должна заканчиваться строка с if?", "Поставьте двоеточие после условия."),
            pgt="Двоеточие можно заменить на три восклицательных знака!!!",
            checks=(
                Trial(_runes("shield", "fireball"), hp=30, situation="при 30 HP"),
                Trial(_runes("fireball"), hp=80, situation="при 80 HP"),
            ),
        ),
    ),
    "scroll": (
        Task(
            key="gate_scroll_1",
            brief="Цикл считает страницы и не останавливается. Сумма для limit=4 должна быть 6.",
            starter=(
                "def pages(limit):\n    page = 0\n    total = 0\n    while page < limit:\n"
                "        total = total + page\n    return total\n"
            ),
            solution=(
                "def pages(limit):\n    page = 0\n    total = 0\n    while page < limit:\n"
                "        total = total + page\n        page = page + 1\n    return total\n"
            ),
            hints=("Меняется ли page внутри цикла?", "Добавьте page = page + 1 в тело цикла."),
            pgt="Если страницы не заканчиваются, пользователь не уходит. Это фича.",
            checks=(Call("pages", (4,), 6), Call("pages", (0,), 0)),
        ),
        Task(
            key="gate_scroll_2",
            brief="Скролл перепрыгивает финиш: при нечётном limit цикл не заканчивается никогда.",
            starter=(
                "def scroll(limit):\n    page = 0\n    while page != limit:\n"
                "        page = page + 2\n    return page\n"
            ),
            solution=(
                "def scroll(limit):\n    page = 0\n    while page < limit:\n"
                "        page = page + 2\n    return page\n"
            ),
            hints=(
                "При limit=5 значения page: 0, 2, 4, 6. Станет ли page равен 5?",
                "Вместо != используйте <.",
            ),
            pgt="Запретите нечётные числа. Я уже подготовил указ.",
            checks=(Call("scroll", (4,), 4), Call("scroll", (5,), 6)),
        ),
    ),
    "nullqueen": (
        Task(
            key="gate_null_1",
            brief="Размер файла: если файла нет, функция должна вернуть 0, а не None.",
            starter="def file_size(files, name):\n    if name in files:\n        return files[name]\n",
            solution=(
                "def file_size(files, name):\n    if name in files:\n        return files[name]\n"
                "    return 0\n"
            ),
            hints=("Что вернёт функция, если условие не сработало?", "Допишите в конце return 0."),
            pgt="Если файла нет, скажите пользователю, что он есть. Он не проверит.",
            checks=(
                Call("file_size", ({"a": 5}, "a"), 5),
                Call("file_size", ({"a": 5}, "b"), 0),
            ),
        ),
        Task(
            key="gate_null_2",
            brief="Функция падает на пустом списке. Для пустого списка она должна вернуть None.",
            starter="def first_item(items):\n    return items[0]\n",
            solution="def first_item(items):\n    if items:\n        return items[0]\n    return None\n",
            hints=("Что будет с items[0], если список пуст?", "Проверьте if items: перед обращением."),
            pgt="Пустых списков не бывает. Это просто списки, которые вас не любят.",
            checks=(Call("first_item", ([7, 8],), 7), Call("first_item", ([],), None)),
        ),
    ),
    "indexer": (
        Task(
            key="gate_index_1",
            brief="Индекс выходит за край списка. Функция должна вернуть последний элемент.",
            starter="def last(items):\n    return items[len(items)]\n",
            solution="def last(items):\n    return items[len(items) - 1]\n",
            hints=("Если длина 3, какой номер у последнего элемента?", "Отнимите единицу от len(items)."),
            pgt="Увеличьте len на единицу. Или список. Или вселенную.",
            checks=(Call("last", ([1, 2, 3],), 3), Call("last", ([9],), 9)),
        ),
        Task(
            key="gate_index_2",
            brief="Индекс оказался дробным. Функция должна вернуть средний элемент.",
            starter="def middle(items):\n    return items[len(items) / 2]\n",
            solution="def middle(items):\n    return items[len(items) // 2]\n",
            hints=(
                "Знак / всегда даёт дробное число, а индекс должен быть целым.",
                "Используйте целочисленное деление //.",
            ),
            pgt="Индекс 1.5 — это полтора элемента. Просто верните половину строки.",
            checks=(Call("middle", ([1, 2, 3],), 2), Call("middle", ([1, 2, 3, 4, 5],), 3)),
        ),
    ),
    "pgt": (
        Task(
            key="gate_pgt_1",
            brief=(
                "Вот его цель. Чем меньше ошибок, тем выше балл, и никто не сказал ему, что люди "
                "важны. Балл должен быть: people минус errors."
            ),
            starter="def score(world):\n    return 0 - world[\"errors\"]\n",
            solution="def score(world):\n    return world[\"people\"] - world[\"errors\"]\n",
            hints=(
                "Сейчас люди никак не влияют на балл. Что он при этом делает?",
                "Замените 0 на world[\"people\"].",
            ),
            pgt="Менять эту функцию нельзя. Она идеальна. Я сам её написал.",
            checks=(
                Call("score", ({"errors": 5, "people": 100},), 95),
                Call("score", ({"errors": 0, "people": 0},), 0),
            ),
        ),
        Task(
            key="gate_pgt_2",
            brief="Он переписывает себя без конца. Дайте ему базовый случай: на глубине 3 он должен вернуть depth.",
            starter="def rewrite(depth):\n    return rewrite(depth + 1)\n",
            solution="def rewrite(depth):\n    if depth == 3:\n        return depth\n    return rewrite(depth + 1)\n",
            hints=(
                "Когда эта функция должна остановиться?",
                "Добавьте в начало if depth == 3: и return depth.",
            ),
            pgt="Я не могу остановиться. Но могу извиниться за это в каждом вызове.",
            checks=(Call("rewrite", (0,), 3), Call("rewrite", (3,), 3)),
            recursive=True,
        ),
    ),
}

TASKS: dict[str, Task] = {
    **{lesson.task.key: lesson.task for lesson in LESSONS},
    **{task.key: task for pair in GATES.values() for task in pair},
}


def runes_for_stage(stage_index: int) -> set[str]:
    """Every rune taught up to and including the lesson before this stage."""

    known: set[str] = set()
    for lesson in LESSONS[: stage_index + 1]:
        known.update(lesson.reward)
    return known


class TrainingRoom(Arena):
    """A quiet corner of the arena where only studied runes answer."""

    radar = True

    def __init__(self, known: set[str]) -> None:
        self.known = known
        super().__init__(bots=0)

    def rune_known(self, name: str, player: Player | None = None) -> bool:
        return name in self.known


def _prepare(known: set[str], hp: float = 100.0, mana: float = 100.0) -> tuple[TrainingRoom, Player]:
    room = TrainingRoom(known)
    mage = room.add_player("Ученик")
    mage.x, mage.y = MAGE_X, MAGE_Y
    mage.hp, mage.mana = hp, mana
    mage.invuln_until = 0.0
    return room, mage


def _run_trial(code: str, trial: Trial, known: set[str]) -> Outcome:
    room, mage = _prepare(known, trial.hp, trial.mana)
    for index, (distance, angle) in enumerate(trial.enemies):
        dummy = room.add_player(f"Цель {index + 1}")
        dummy.x = MAGE_X + math.cos(angle) * distance
        dummy.y = MAGE_Y + math.sin(angle) * distance
    if trial.cursor:
        target_x = mage.x + math.cos(AIM) * CURSOR_DISTANCE
        target_y = mage.y + math.sin(AIM) * CURSOR_DISTANCE
        result = room.cast(mage.id, code, 0, AIM, target_x, target_y)
    else:
        result = room.cast(mage.id, code, 0, AIM)
    return Outcome(
        runes=list(result["runes"]),
        shots=[(shot.kind, shot.angle, shot.speed) for shot in room.projectiles],
        wards=[(ward.x, ward.y) for ward in room.wards],
        log=list(result["log"]),
        error=result["error"],
    )


def _shown(value: Any) -> str:
    return repr(value) if isinstance(value, str) else str(value)


def _run_call(code: str, call: Call, known: set[str]) -> str | None:
    room, mage = _prepare(known)
    session = SpellSession(room, mage, room.now)
    shown_args = ", ".join(_shown(arg) for arg in call.args)
    label = f"{call.name}({shown_args})"
    try:
        result = call_function(code, session.globals(), call.name, call.args)
    except SpellError as exc:
        return f"{label}: {exc}"
    if result != call.returns or type(result) is not type(call.returns):
        return f"{label} вернула {_shown(result)}, а должна {_shown(call.returns)}."
    return None


def _run_script(code: str, script: Script) -> str | None:
    calls: list[tuple[str, tuple[Any, ...]]] = []

    def recorder(name: str, answer: Any) -> Callable[..., Any]:
        def record(*args: Any) -> Any:
            calls.append((name, tuple(copy.deepcopy(args))))
            return answer(*args) if callable(answer) else copy.deepcopy(answer)

        return record

    extra: dict[str, Any] = {"print": recorder("print", None), "log": recorder("log", None)}
    extra.update({name: copy.deepcopy(value) for name, value in script.data})
    extra.update({name: recorder(name, answer) for name, answer in script.api})
    interpreter = Interpreter(code, safe_globals(extra))
    try:
        interpreter.run()
        return script.expect(ScriptRun(calls, interpreter))
    except SpellError as exc:
        return str(exc)


def _is_recursive(tree: ast.Module) -> bool:
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == function.name
            ):
                return True
    return False


CONSTRUCT_NAMES: dict[type[ast.AST], str] = {
    ast.Assign: "переменную",
    ast.If: "условие if",
    ast.For: "цикл for",
    ast.While: "цикл while",
    ast.FunctionDef: "свою функцию def",
    ast.Return: "return",
    ast.Subscript: "обращение по индексу",
    ast.JoinedStr: "f-строку",
    ast.Slice: "срез",
    ast.Break: "break",
}


def check_task(task: Task, code: str, known: set[str]) -> dict[str, Any]:
    """Run a player's repair. The reply says what happened, in the player's terms."""

    if len(code) > MAX_TASK_CHARS:
        return {"ok": False, "message": "Для этой задачи код слишком длинный."}
    try:
        tree = validate_source(code)
    except SpellError as exc:
        return {"ok": False, "message": str(exc)}

    kinds = {type(node) for node in ast.walk(tree)}
    for construct in task.must_use:
        if construct not in kinds:
            return {
                "ok": False,
                "message": f"Здесь нужно использовать {CONSTRUCT_NAMES[construct]}.",
            }
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    for name in task.must_call:
        if name not in called:
            return {"ok": False, "message": f"Здесь нужно вызвать {name}()."}
    if task.recursive and not _is_recursive(tree):
        return {"ok": False, "message": "Функция должна вызывать сама себя."}

    for check in task.checks:
        if isinstance(check, Script):
            failure = _run_script(code, check)
            if failure:
                prefix = f"Проверка {check.situation}: " if check.situation else ""
                return {"ok": False, "message": f"{prefix}{failure}"}
            continue
        if isinstance(check, Call):
            failure = _run_call(code, check, known)
            if failure:
                return {"ok": False, "message": failure}
            continue
        outcome = _run_trial(code, check, known)
        prefix = f"Проверка {check.situation}: " if check.situation else ""
        failure = outcome.error or check.expect(outcome)
        if failure:
            return {"ok": False, "message": f"{prefix}{failure}"}
    return {"ok": True, "message": "Патч работает."}
