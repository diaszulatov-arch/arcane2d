"""A small, sandboxed interpreter for Python-flavoured battle spells.

Player code never reaches CPython's ``exec``/``eval``.  We parse it with the
standard library's AST parser and walk only a deliberately small language
subset.  Every evaluation consumes a step from a hard budget, and values that
can be touched from a spell are limited to numbers, strings, containers and
three tiny read-only view objects supplied by the game.

This is intentionally not a general Python sandbox.  It is a game language
that happens to look and feel like Python.
"""

from __future__ import annotations

import ast
import math
import random
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

MAX_SOURCE_CHARS = 12_000
MAX_STEPS = 6_000
MAX_LOOP_ITERATIONS = 300
MAX_TOTAL_LOOP_ITERATIONS = 1_000
MAX_CALL_DEPTH = 10
MAX_SEQUENCE = 250
MAX_STRING = 4_000
MAX_INT_BITS = 2_048
MAX_WEIGHT = 2_000
MAX_MANA_ESTIMATE = 999


class SpellError(Exception):
    """Base class for errors that are safe to show to the player."""


class SpellValidationError(SpellError):
    pass


class SpellRuntimeError(SpellError):
    def __init__(self, message: str, *, located: bool = False) -> None:
        super().__init__(message)
        self.located = located


@dataclass(frozen=True, slots=True)
class UnitView:
    """Read-only snapshot of an enemy or an ally, exposed inside spell code."""

    id: int
    name: str
    kind: str
    x: float
    y: float
    hp: float
    max_hp: float
    dist: float
    boss: bool
    dead: bool = False
    text: str = ""


@dataclass(frozen=True, slots=True)
class OwnView:
    """Read-only snapshot of the caster."""

    name: str
    x: float
    y: float
    hp: float
    max_hp: float
    mana: float
    max_mana: float
    shield: float
    aim: float


@dataclass(frozen=True, slots=True)
class PointView:
    """Read-only world point under the player's cursor."""

    x: float
    y: float
    dist: float


_UNIT_FIELDS = frozenset(UnitView.__dataclass_fields__)
_OWN_FIELDS = frozenset(OwnView.__dataclass_fields__)
_POINT_FIELDS = frozenset(PointView.__dataclass_fields__)


class _ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


class _BreakSignal(Exception):
    pass


class _ContinueSignal(Exception):
    pass


class _Environment:
    __slots__ = ("values", "parent")

    def __init__(self, parent: "_Environment | None" = None) -> None:
        self.values: dict[str, Any] = {}
        self.parent = parent

    def get(self, name: str) -> Any:
        env: _Environment | None = self
        while env is not None:
            if name in env.values:
                return env.values[name]
            env = env.parent
        raise KeyError(name)

    def set(self, name: str, value: Any) -> None:
        self.values[name] = value


class _UserFunction:
    __slots__ = ("name", "args", "defaults", "body", "closure")

    def __init__(
        self,
        name: str,
        args: list[str],
        defaults: list[Any],
        body: list[ast.stmt],
        closure: _Environment,
    ) -> None:
        self.name = name
        self.args = args
        self.defaults = defaults
        self.body = body
        self.closure = closure


_ALLOWED_NODES: set[type[ast.AST]] = {
    ast.Module,
    ast.Expr,
    ast.Assign,
    ast.AugAssign,
    ast.If,
    ast.For,
    ast.While,
    ast.Break,
    ast.Continue,
    ast.Pass,
    ast.FunctionDef,
    ast.Return,
    ast.arguments,
    ast.arg,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Constant,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.Call,
    ast.Attribute,
    ast.Subscript,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.IfExp,
    ast.JoinedStr,
    ast.FormattedValue,
    ast.Slice,
    ast.keyword,
    # operators
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.UAdd,
    ast.USub,
    ast.Not,
    ast.And,
    ast.Or,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.Is,
    ast.IsNot,
}

_BANNED_NAMES = {
    "__import__",
    "compile",
    "delattr",
    "eval",
    "exec",
    "getattr",
    "globals",
    "help",
    "input",
    "locals",
    "open",
    "setattr",
    "type",
    "vars",
}

_NODE_HINTS: dict[type[ast.AST], str] = {
    ast.Import: "Импорт запрещён: используйте встроенные функции заклинаний.",
    ast.ImportFrom: "Импорт запрещён: используйте встроенные функции заклинаний.",
    ast.ClassDef: "Классы недоступны в гримуаре.",
    ast.Lambda: "Лямбды недоступны — используйте def.",
    ast.ListComp: "Списковые включения недоступны — используйте цикл for.",
    ast.SetComp: "Списковые включения недоступны — используйте цикл for.",
    ast.DictComp: "Списковые включения недоступны — используйте цикл for.",
    ast.GeneratorExp: "Генераторы недоступны — используйте цикл for.",
    ast.Try: "try/except недоступен в песочнице заклинаний.",
    ast.Raise: "raise недоступен в песочнице заклинаний.",
    ast.With: "Конструкция with недоступна в песочнице заклинаний.",
    ast.AsyncFunctionDef: "Асинхронность недоступна в заклинаниях.",
    ast.Await: "Асинхронность недоступна в заклинаниях.",
    ast.Delete: "del недоступен в заклинаниях.",
    ast.Global: "global недоступен в заклинаниях.",
    ast.Nonlocal: "nonlocal недоступен в заклинаниях.",
    ast.Assert: "assert недоступен в заклинаниях.",
    ast.Yield: "Генераторы недоступны в заклинаниях.",
    ast.YieldFrom: "Генераторы недоступны в заклинаниях.",
    ast.Starred: "Распаковка * недоступна в заклинаниях.",
    ast.NamedExpr: "Оператор := недоступен в заклинаниях.",
    ast.Match: "match недоступен в заклинаниях.",
    ast.Set: "Множества недоступны — используйте списки.",
}


def validate_source(source: str) -> ast.Module:
    if not isinstance(source, str):
        raise SpellValidationError("Код заклинания должен быть строкой.")
    if not source.strip():
        raise SpellValidationError("Гримуар пуст. Напишите заклинание.")
    if len(source) > MAX_SOURCE_CHARS:
        raise SpellValidationError(
            f"Слишком длинное заклинание (максимум {MAX_SOURCE_CHARS} символов)."
        )
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        line = exc.lineno or 1
        text = (exc.msg or "синтаксическая ошибка").capitalize()
        raise SpellValidationError(f"Строка {line}: {text}") from None
    except (RecursionError, MemoryError):
        raise SpellValidationError("Слишком сложная вложенность заклинания.") from None

    nodes = list(ast.walk(tree))
    if len(nodes) > 2_000:
        raise SpellValidationError("Заклинание слишком велико.")
    loop_depth = 0

    def visit(node: ast.AST, in_function: bool = False, loop: int = 0) -> None:
        nonlocal loop_depth

        if type(node) not in _ALLOWED_NODES:
            hint = _NODE_HINTS.get(type(node))
            if hint is None:
                hint = f"Конструкция {type(node).__name__} недоступна."
            raise SpellValidationError(f"Строка {getattr(node, 'lineno', 1)}: {hint}")

        if isinstance(node, ast.Name):
            if node.id.startswith("_"):
                raise SpellValidationError(
                    f"Строка {node.lineno}: имена с «_» запрещены."
                )
            if node.id in _BANNED_NAMES:
                raise SpellValidationError(
                    f"Строка {node.lineno}: имя «{node.id}» запрещено."
                )

        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                raise SpellValidationError(
                    f"Строка {node.lineno}: доступ к служебным атрибутам запрещён."
                )
            if isinstance(node.ctx, ast.Store):
                raise SpellValidationError(
                    f"Строка {node.lineno}: атрибуты нельзя изменять."
                )

        if isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, (bytes, complex)) or value is Ellipsis:
                raise SpellValidationError(
                    f"Строка {node.lineno}: этот тип значения недоступен."
                )
            if isinstance(value, str) and len(value) > MAX_STRING:
                raise SpellValidationError(
                    f"Строка {node.lineno}: строка слишком длинная."
                )
            if isinstance(value, int) and not isinstance(value, bool):
                if value.bit_length() > MAX_INT_BITS:
                    raise SpellValidationError(
                        f"Строка {node.lineno}: слишком большое число."
                    )

        if isinstance(node, ast.FunctionDef):
            if node.decorator_list:
                raise SpellValidationError(
                    f"Строка {node.lineno}: декораторы недоступны."
                )
            if getattr(node, "type_params", None):
                raise SpellValidationError(
                    f"Строка {node.lineno}: обобщённые типы недоступны."
                )
            if node.name.startswith("_"):
                raise SpellValidationError(
                    f"Строка {node.lineno}: имена с «_» запрещены."
                )
            if node.returns is not None:
                raise SpellValidationError(
                    f"Строка {node.lineno}: аннотации типов не поддерживаются."
                )
            args = node.args
            if args.vararg or args.kwarg or args.kwonlyargs or args.posonlyargs:
                raise SpellValidationError(
                    f"Строка {node.lineno}: используйте обычные аргументы функции."
                )
            if args.defaults and len(args.defaults) > len(args.args):
                raise SpellValidationError(
                    f"Строка {node.lineno}: некорректные значения аргументов."
                )
            for arg in args.args:
                if arg.arg.startswith("_"):
                    raise SpellValidationError(
                        f"Строка {node.lineno}: имена аргументов с «_» запрещены."
                    )
                if arg.annotation is not None:
                    raise SpellValidationError(
                        f"Строка {node.lineno}: аннотации типов не поддерживаются."
                    )
            for default in args.defaults:
                visit(default, in_function=True, loop=0)
            for child in node.body:
                visit(child, in_function=True, loop=0)
            return

        if isinstance(node, ast.Return):
            if not in_function:
                raise SpellValidationError(
                    f"Строка {node.lineno}: return допустим только внутри def."
                )

        if isinstance(node, (ast.For, ast.While)):
            # Iterate manually so break/continue can be checked against the
            # local loop depth.
            if isinstance(node, ast.For):
                visit(node.target, in_function, loop + 1)
                visit(node.iter, in_function, loop + 1)
            if isinstance(node, ast.While):
                visit(node.test, in_function, loop + 1)
            for child in node.body:
                visit(child, in_function, loop + 1)
            for child in node.orelse:
                visit(child, in_function, loop + 1)
            return

        if isinstance(node, (ast.Break, ast.Continue)) and loop <= 0:
            raise SpellValidationError(
                f"Строка {node.lineno}: break/continue вне цикла."
            )

        if isinstance(node, ast.FormattedValue):
            if node.format_spec is not None:
                raise SpellValidationError(
                    f"Строка {node.lineno}: форматирование f-строк не поддерживается."
                )
            if node.conversion not in (-1, 115):
                raise SpellValidationError(
                    f"Строка {node.lineno}: используйте f-строку без !r и формата."
                )

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    raise SpellValidationError(
                        f"Строка {node.lineno}: атрибуты нельзя изменять."
                    )

        if isinstance(node, ast.Call):
            if any(isinstance(arg, ast.Starred) for arg in node.args):
                raise SpellValidationError(
                    f"Строка {node.lineno}: распаковка аргументов запрещена."
                )
            for kw in node.keywords:
                if kw.arg is None:
                    raise SpellValidationError(
                        f"Строка {node.lineno}: **kwargs запрещены."
                    )

        for child in ast.iter_child_nodes(node):
            visit(child, in_function, loop)

    try:
        visit(tree)
    except RecursionError:
        raise SpellValidationError("Слишком сложная вложенность заклинания.") from None
    return tree


def _weigh(value: Any, limit: int = MAX_WEIGHT) -> int:
    """Count what a value reaches through its containers, stopping past ``limit``.

    One list can reference another 250 times, so a tower of four short lists
    stands for billions of elements.  ``str`` and ``==`` would walk all of them
    in C, out of reach of the step budget.  Shared references are counted again
    on purpose: that repetition is exactly what those operations pay for.
    """

    weight = 0
    pending = [value]
    while pending and weight <= limit:
        item = pending.pop()
        if isinstance(item, (list, tuple)):
            weight += len(item)
            pending.extend(item)
        elif isinstance(item, dict):
            weight += len(item)
            pending.extend(item.values())
        elif isinstance(item, str):
            weight += len(item) // 32
    return weight


def spell_text(value: Any) -> str:
    """``str(value)`` for spell data, refusing values too costly to render."""

    if _weigh(value) > MAX_WEIGHT:
        raise SpellRuntimeError("Коллекция слишком велика, чтобы превратить её в текст.")
    return str(value)


def _ordered_items(values: Iterable[Any], name: str) -> None:
    if not all(isinstance(value, (int, float, str)) for value in values):
        raise SpellRuntimeError(f"{name}() можно применять только к числам/строкам.")


def _loop_count(node: ast.expr) -> int | None:
    """How many times a ``for`` runs, when that is plain from its source."""

    if isinstance(node, (ast.List, ast.Tuple)):
        return len(node.elts)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "range"
        and not node.keywords
        and all(
            isinstance(arg, ast.Constant) and type(arg.value) is int
            for arg in node.args
        )
    ):
        try:
            return len(range(*(arg.value for arg in node.args)))
        except (TypeError, ValueError, OverflowError):
            return None
    return None


def mana_estimate(tree: ast.Module, costs: Mapping[str, int]) -> tuple[int, int]:
    """Cheapest and dearest mana path through a spell, by reading its source.

    A hint for the editor, not a rule: conditions are not evaluated, so the
    range brackets what a cast may spend.  Runs on unsaved source from any
    visitor, so it must stay linear: each helper is priced once and remembered,
    or a chain of helpers calling the next one twice would take 2^n visits.
    """

    functions = {
        node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    priced: dict[str, tuple[int, int]] = {}

    def price(name: str) -> tuple[int, int]:
        if name not in priced:
            priced[name] = (0, 0)  # A recursive call adds nothing of its own.
            priced[name] = block(functions[name].body)
        return priced[name]

    def expression(node: ast.AST) -> tuple[int, int]:
        low = high = 0
        for child in ast.walk(node):
            if not (isinstance(child, ast.Call) and isinstance(child.func, ast.Name)):
                continue
            name = child.func.id
            if name in costs:
                low += costs[name]
                high += costs[name]
            elif name in functions:
                body_low, body_high = price(name)
                low += body_low
                high += body_high
        return low, high

    def statement(node: ast.stmt) -> tuple[int, int]:
        if isinstance(node, ast.FunctionDef):
            return 0, 0
        if isinstance(node, ast.If):
            test_low, test_high = expression(node.test)
            body_low, body_high = block(node.body)
            else_low, else_high = block(node.orelse)
            return test_low + min(body_low, else_low), test_high + max(body_high, else_high)
        if isinstance(node, ast.For):
            times = _loop_count(node.iter)
            body_low, body_high = block(node.body)
            if times is None:
                return 0, body_high
            return body_low * times, body_high * times
        if isinstance(node, ast.While):
            return 0, block(node.body)[1]
        return expression(node)

    def block(statements: list[ast.stmt]) -> tuple[int, int]:
        low = high = 0
        for node in statements:
            node_low, node_high = statement(node)
            low += node_low
            high += node_high
        return low, high

    low, high = block(tree.body)
    return min(low, MAX_MANA_ESTIMATE), min(high, MAX_MANA_ESTIMATE)


def safe_globals(extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return the immutable part of a spell's environment."""

    def _range(*args: Any) -> list[int]:
        if not args or len(args) > 3:
            raise SpellRuntimeError("range() принимает от 1 до 3 аргументов.")
        if any(type(v) is not int for v in args):
            raise SpellRuntimeError("range() принимает только целые числа.")
        try:
            length = len(range(*args))
        except (ValueError, OverflowError):
            raise SpellRuntimeError("Некорректный диапазон range().") from None
        if length > 1_000:
            raise SpellRuntimeError("range() слишком большой (максимум 1000 шагов).")
        return list(range(*args))

    def _len(value: Any) -> int:
        if isinstance(value, (str, list, tuple, dict)):
            return len(value)
        raise SpellRuntimeError("len() работает со строками, списками и словарями.")

    def _min(*args: Any) -> Any:
        values: Iterable[Any]
        if len(args) == 1:
            if not isinstance(args[0], (list, tuple)):
                raise SpellRuntimeError("min() ожидает список или несколько чисел.")
            values = args[0]
        else:
            values = args
        if not values:
            raise SpellRuntimeError("min() от пустого списка.")
        _ordered_items(values, "min")
        try:
            return min(values)
        except TypeError:
            raise SpellRuntimeError("min() можно применять только к числам/строкам.") from None

    def _max(*args: Any) -> Any:
        values: Iterable[Any]
        if len(args) == 1:
            if not isinstance(args[0], (list, tuple)):
                raise SpellRuntimeError("max() ожидает список или несколько чисел.")
            values = args[0]
        else:
            values = args
        if not values:
            raise SpellRuntimeError("max() от пустого списка.")
        _ordered_items(values, "max")
        try:
            return max(values)
        except TypeError:
            raise SpellRuntimeError("max() можно применять только к числам/строкам.") from None

    def _sum(values: Any, start: Any = 0) -> Any:
        if not isinstance(values, (list, tuple)):
            raise SpellRuntimeError("sum() ожидает список.")
        if type(start) not in (int, float) or any(
            type(value) not in (int, float) for value in values
        ):
            raise SpellRuntimeError("sum() работает только с числами.")
        total = sum(values, start)
        return _guard_number(total)

    def _clamp(value: Any, low: Any, high: Any) -> Any:
        if any(type(v) not in (int, float) for v in (value, low, high)):
            raise SpellRuntimeError("clamp() принимает только числа.")
        return max(low, min(value, high))

    def _abs(value: Any) -> Any:
        if type(value) not in (int, float):
            raise SpellRuntimeError("abs() принимает только число.")
        return _guard_number(abs(value))

    def _round(value: Any, digits: int = 0) -> Any:
        if type(value) not in (int, float) or type(digits) is not int:
            raise SpellRuntimeError("round() принимает число и количество знаков.")
        if digits < -6 or digits > 6:
            raise SpellRuntimeError("round(): слишком много знаков.")
        return round(value, digits)

    def _to_int(value: Any = 0) -> int:
        if type(value) not in (int, float, bool, str):
            raise SpellRuntimeError("int() не может преобразовать этот тип.")
        try:
            result = int(value)
        except (ValueError, OverflowError):
            raise SpellRuntimeError("int() не может преобразовать значение.") from None
        return _guard_number(result)

    def _to_float(value: Any = 0.0) -> float:
        if type(value) not in (int, float, bool, str):
            raise SpellRuntimeError("float() не может преобразовать этот тип.")
        try:
            result = float(value)
        except (ValueError, OverflowError):
            raise SpellRuntimeError("float() не может преобразовать значение.") from None
        return _guard_number(result)

    def _to_str(value: Any = "") -> str:
        if isinstance(value, (UnitView, OwnView, PointView)):
            raise SpellRuntimeError("Этот объект нельзя превратить в строку.")
        text = spell_text(value)
        if len(text) > MAX_STRING:
            raise SpellRuntimeError("Строка получилась слишком длинной.")
        return text

    def _to_bool(value: Any = False) -> bool:
        return bool(value)

    def _rand(low: float = 0.0, high: float = 1.0) -> float:
        if type(low) not in (int, float) or type(high) not in (int, float):
            raise SpellRuntimeError("rand() принимает только числа.")
        if high < low:
            low, high = high, low
        return random.uniform(float(low), float(high))

    def _randi(low: int = 0, high: int = 10) -> int:
        if type(low) is not int or type(high) is not int:
            raise SpellRuntimeError("randi() принимает только целые числа.")
        if abs(low) > 10**9 or abs(high) > 10**9:
            raise SpellRuntimeError("randi(): числа слишком большие.")
        low, high = min(low, high), max(low, high)
        return random.randint(low, high)

    def _math(fn: Callable[..., float]) -> Callable[..., float]:
        def wrapped(*args: Any) -> float:
            if any(type(arg) not in (int, float) for arg in args):
                raise SpellRuntimeError("Математическая функция принимает числа.")
            try:
                return _guard_number(fn(*args))
            except (ValueError, OverflowError):
                raise SpellRuntimeError("Математическая ошибка.") from None

        return wrapped

    globals_: dict[str, Any] = {
        "range": _range,
        "len": _len,
        "abs": _abs,
        "min": _min,
        "max": _max,
        "sum": _sum,
        "round": _round,
        "int": _to_int,
        "float": _to_float,
        "str": _to_str,
        "bool": _to_bool,
        "clamp": _clamp,
        "rand": _rand,
        "randi": _randi,
        "sin": _math(math.sin),
        "cos": _math(math.cos),
        "sqrt": _math(math.sqrt),
        "atan2": _math(math.atan2),
        "hypot": _math(math.hypot),
        "PI": math.pi,
        "TAU": math.tau,
    }
    if extra:
        globals_.update(extra)
    return globals_


def _guard_number(value: Any) -> Any:
    if type(value) is int:
        if value.bit_length() > MAX_INT_BITS:
            raise SpellRuntimeError("Слишком большое число.")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise SpellRuntimeError("Число вышло за допустимые пределы.")
        return value
    return value


def _check_sequence(value: Any) -> Any:
    if isinstance(value, (list, tuple, dict)) and len(value) > MAX_SEQUENCE:
        raise SpellRuntimeError("Слишком большая коллекция.")
    if isinstance(value, str) and len(value) > MAX_STRING:
        raise SpellRuntimeError("Слишком длинная строка.")
    return value


class Interpreter:
    def __init__(
        self,
        source: str,
        globals_: Mapping[str, Any],
        *,
        step_limit: int = MAX_STEPS,
    ) -> None:
        self.source = source
        self.step_limit = step_limit
        self.steps = 0
        self.loop_iterations = 0
        self.call_depth = 0
        self.tree = validate_source(source)
        self.root = _Environment()
        self.root.values.update(globals_)

    # ------------------------------------------------------------------ utils
    def _tick(self) -> None:
        self.steps += 1
        if self.steps > self.step_limit:
            raise SpellRuntimeError(
                "Заклинание оказалось слишком сложным и было остановлено."
            )

    def _charge(self, value: Any) -> None:
        """Bill a C-level walk over a container for every element it may touch."""

        if isinstance(value, (list, tuple, dict)):
            self.steps += _weigh(value, self.step_limit)
            if self.steps > self.step_limit:
                raise SpellRuntimeError(
                    "Заклинание оказалось слишком сложным и было остановлено."
                )

    def _rt(self, node: ast.AST, message: str) -> SpellRuntimeError:
        return SpellRuntimeError(
            f"Строка {getattr(node, 'lineno', 1)}: {message}", located=True
        )

    def _locate(self, node: ast.AST, exc: SpellError) -> SpellError:
        if getattr(exc, "located", False):
            return exc
        return self._rt(node, str(exc))

    def run(self) -> None:
        try:
            for statement in self.tree.body:
                self._exec_stmt(statement, self.root)
        except _ReturnSignal:
            raise SpellValidationError("return допустим только внутри def.") from None
        except _BreakSignal:
            raise SpellValidationError("break допустим только внутри цикла.") from None
        except _ContinueSignal:
            raise SpellValidationError("continue допустим только внутри цикла.") from None
        except SpellError:
            raise
        except RecursionError:
            raise SpellRuntimeError("Заклинание ушло в слишком глубокую рекурсию.") from None
        except (MemoryError, OverflowError):
            raise SpellRuntimeError("Заклинание потребовало слишком много ресурсов.") from None
        except Exception:  # A bug in a safe op must not crash the arena.
            raise SpellRuntimeError("Внутренняя ошибка заклинания.") from None

    # ------------------------------------------------------------- statements
    def _exec_block(self, statements: list[ast.stmt], env: _Environment) -> None:
        for statement in statements:
            self._exec_stmt(statement, env)

    def _exec_stmt(self, node: ast.stmt, env: _Environment) -> None:
        self._tick()
        if isinstance(node, ast.Expr):
            self._eval(node.value, env)
            return
        if isinstance(node, ast.Assign):
            value = self._eval(node.value, env)
            value = _check_sequence(value)
            for target in node.targets:
                self._assign(target, value, env)
            return
        if isinstance(node, ast.AugAssign):
            old = self._read_target(node.target, env)
            value = self._binop(node.op, old, self._eval(node.value, env), node)
            self._assign(node.target, value, env)
            return
        if isinstance(node, ast.If):
            if self._truthy(self._eval(node.test, env)):
                self._exec_block(node.body, env)
            else:
                self._exec_block(node.orelse, env)
            return
        if isinstance(node, ast.For):
            iterable = self._eval(node.iter, env)
            if isinstance(iterable, dict):
                items = list(iterable.keys())
            elif isinstance(iterable, (list, tuple, str)):
                items = list(iterable)
            else:
                raise self._rt(node, "Этот объект нельзя перебирать в for.")
            if len(items) > MAX_SEQUENCE:
                raise self._rt(node, "Слишком много элементов для перебора.")
            broke = False
            for item in items:
                self._loop_tick(node)
                self._assign(node.target, item, env)
                try:
                    self._exec_block(node.body, env)
                except _ContinueSignal:
                    continue
                except _BreakSignal:
                    broke = True
                    break
            if not broke:
                self._exec_block(node.orelse, env)
            return
        if isinstance(node, ast.While):
            broke = False
            iterations = 0
            while self._truthy(self._eval(node.test, env)):
                self._loop_tick(node)
                iterations += 1
                if iterations > MAX_LOOP_ITERATIONS:
                    raise self._rt(node, "Цикл while исчерпал лимит итераций.")
                try:
                    self._exec_block(node.body, env)
                except _ContinueSignal:
                    continue
                except _BreakSignal:
                    broke = True
                    break
            if not broke:
                self._exec_block(node.orelse, env)
            return
        if isinstance(node, ast.FunctionDef):
            arg_names = [arg.arg for arg in node.args.args]
            defaults = [self._eval(value, env) for value in node.args.defaults]
            env.set(
                node.name,
                _UserFunction(node.name, arg_names, defaults, node.body, env),
            )
            return
        if isinstance(node, ast.Return):
            raise _ReturnSignal(self._eval(node.value, env) if node.value else None)
        if isinstance(node, ast.Pass):
            return
        if isinstance(node, ast.Break):
            raise _BreakSignal
        if isinstance(node, ast.Continue):
            raise _ContinueSignal
        raise self._rt(node, "Эта конструкция недоступна.")

    def _loop_tick(self, node: ast.AST) -> None:
        self._tick()
        self.loop_iterations += 1
        if self.loop_iterations > MAX_TOTAL_LOOP_ITERATIONS:
            raise self._rt(node, "Слишком много итераций. Остановите заклинание.")

    # ------------------------------------------------------------- assignment
    def _assign(self, target: ast.AST, value: Any, env: _Environment) -> None:
        self._tick()
        if isinstance(target, ast.Name):
            env.set(target.id, value)
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            if not isinstance(value, (list, tuple)) or len(value) != len(target.elts):
                raise self._rt(target, "Не совпадает количество переменных при распаковке.")
            for subtarget, subvalue in zip(target.elts, value):
                self._assign(subtarget, subvalue, env)
            return
        if isinstance(target, ast.Subscript):
            container = self._eval(target.value, env)
            key = self._eval_slice_or_index(target.slice, env)
            try:
                if isinstance(container, list):
                    if type(key) is not int:
                        raise TypeError
                    container[key] = value
                elif isinstance(container, dict):
                    if not isinstance(key, (int, float, str, bool)):
                        raise TypeError
                    container[key] = value
                else:
                    raise TypeError
            except (IndexError, TypeError, KeyError):
                raise self._rt(target, "Индекс вне границ или контейнер неизменяем.") from None
            return
        raise self._rt(target, "Этой цели нельзя присвоить значение.")

    def _read_target(self, target: ast.AST, env: _Environment) -> Any:
        if isinstance(target, ast.Name):
            try:
                return env.get(target.id)
            except KeyError:
                raise self._rt(target, f"Переменная «{target.id}» не определена.") from None
        if isinstance(target, ast.Subscript):
            return self._eval(target, env)
        raise self._rt(target, "Некорректная цель для +=.")

    # ------------------------------------------------------------ expressions
    def _eval(self, node: ast.expr, env: _Environment) -> Any:
        self._tick()
        if isinstance(node, ast.Constant):
            return _check_sequence(node.value)
        if isinstance(node, ast.Name):
            try:
                return env.get(node.id)
            except KeyError:
                raise self._rt(node, f"Неизвестное имя «{node.id}».") from None
        if isinstance(node, ast.BinOp):
            return self._binop(node.op, self._eval(node.left, env), self._eval(node.right, env), node)
        if isinstance(node, ast.UnaryOp):
            value = self._eval(node.operand, env)
            if isinstance(node.op, ast.Not):
                return not self._truthy(value)
            if isinstance(node.op, ast.USub):
                if type(value) not in (int, float):
                    raise self._rt(node, "Унарный минус работает только с числами.")
                return _guard_number(-value)
            if isinstance(node.op, ast.UAdd):
                if type(value) not in (int, float):
                    raise self._rt(node, "Унарный плюс работает только с числами.")
                return value
            raise self._rt(node, "Недопустимая унарная операция.")
        if isinstance(node, ast.BoolOp):
            is_and = isinstance(node.op, ast.And)
            value: Any = None
            for item in node.values:
                value = self._eval(item, env)
                truth = self._truthy(value)
                if is_and and not truth:
                    return value
                if not is_and and truth:
                    return value
            return value
        if isinstance(node, ast.Compare):
            left = self._eval(node.left, env)
            for operator, comparator_node in zip(node.ops, node.comparators):
                right = self._eval(comparator_node, env)
                if not self._compare(operator, left, right, node):
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            if self._truthy(self._eval(node.test, env)):
                return self._eval(node.body, env)
            return self._eval(node.orelse, env)
        if isinstance(node, ast.Call):
            return self._call(node, env)
        if isinstance(node, ast.Attribute):
            value = self._eval(node.value, env)
            if isinstance(value, UnitView):
                fields = _UNIT_FIELDS
            elif isinstance(value, OwnView):
                fields = _OWN_FIELDS
            elif isinstance(value, PointView):
                fields = _POINT_FIELDS
            else:
                raise self._rt(node, "У этого объекта нет доступных атрибутов.")
            if node.attr not in fields:
                raise self._rt(node, f"У объекта нет атрибута «{node.attr}».")
            return getattr(value, node.attr)
        if isinstance(node, ast.Subscript):
            container = self._eval(node.value, env)
            key = self._eval_slice_or_index(node.slice, env)
            if isinstance(container, dict) and isinstance(key, (list, tuple, dict)):
                raise self._rt(node, "Ключ словаря должен быть числом или строкой.")
            try:
                value = container[key]
            except (IndexError, KeyError, TypeError):
                raise self._rt(node, "Элемент с таким индексом не найден.") from None
            return _check_sequence(value)
        if isinstance(node, ast.List):
            value = [self._eval(item, env) for item in node.elts]
            if len(value) > MAX_SEQUENCE:
                raise self._rt(node, "Слишком длинный список.")
            return value
        if isinstance(node, ast.Tuple):
            value = tuple(self._eval(item, env) for item in node.elts)
            if len(value) > MAX_SEQUENCE:
                raise self._rt(node, "Слишком длинный кортеж.")
            return value
        if isinstance(node, ast.Dict):
            result: dict[Any, Any] = {}
            if len(node.keys) > MAX_SEQUENCE:
                raise self._rt(node, "Слишком большой словарь.")
            for key_node, value_node in zip(node.keys, node.values):
                if key_node is None:
                    raise self._rt(node, "Распаковка ** в словаре недоступна.")
                key = self._eval(key_node, env)
                if not isinstance(key, (int, float, str, bool)) and key is not None:
                    raise self._rt(node, "Ключ словаря должен быть числом или строкой.")
                result[key] = self._eval(value_node, env)
            return result
        if isinstance(node, ast.JoinedStr):
            parts: list[str] = []
            total = 0
            for value_node in node.values:
                if isinstance(value_node, ast.Constant):
                    part = value_node.value
                elif isinstance(value_node, ast.FormattedValue):
                    inner = self._eval(value_node.value, env)
                    if isinstance(inner, (UnitView, OwnView, PointView)):
                        raise self._rt(node, "Этот объект нельзя вставить в строку.")
                    try:
                        part = spell_text(inner)
                    except SpellRuntimeError as exc:
                        raise self._locate(node, exc) from None
                else:
                    raise self._rt(node, "Некорректная f-строка.")
                total += len(part)
                if total > MAX_STRING:
                    raise self._rt(node, "Строка получилась слишком длинной.")
                parts.append(part)
            return "".join(parts)
        raise self._rt(node, "Эта конструкция недоступна.")

    def _eval_slice_or_index(self, node: ast.AST, env: _Environment) -> Any:
        if isinstance(node, ast.Slice):
            values = []
            for part in (node.lower, node.upper, node.step):
                if part is None:
                    values.append(None)
                else:
                    value = self._eval(part, env)
                    if value is not None and type(value) is not int:
                        raise self._rt(node, "Границы среза должны быть целыми.")
                    values.append(value)
            try:
                return slice(*values)
            except Exception:
                raise self._rt(node, "Некорректный срез.") from None
        return self._eval(node, env)

    def _truthy(self, value: Any) -> bool:
        if isinstance(value, (UnitView, OwnView, PointView)):
            return True
        return bool(value)

    def _compare(self, operator: ast.cmpop, left: Any, right: Any, node: ast.AST) -> bool:
        if not isinstance(operator, (ast.Is, ast.IsNot)):
            try:
                self._charge(left)
                self._charge(right)
            except SpellRuntimeError as exc:
                raise self._locate(node, exc) from None
        try:
            if isinstance(operator, ast.Eq):
                return left == right
            if isinstance(operator, ast.NotEq):
                return left != right
            if isinstance(operator, ast.Lt):
                return left < right
            if isinstance(operator, ast.LtE):
                return left <= right
            if isinstance(operator, ast.Gt):
                return left > right
            if isinstance(operator, ast.GtE):
                return left >= right
            if isinstance(operator, ast.In):
                if not isinstance(right, (str, list, tuple, dict)):
                    raise self._rt(node, "Оператор in работает со строками и коллекциями.")
                return left in right
            if isinstance(operator, ast.NotIn):
                if not isinstance(right, (str, list, tuple, dict)):
                    raise self._rt(node, "Оператор in работает со строками и коллекциями.")
                return left not in right
            if isinstance(operator, ast.Is):
                return left is right
            if isinstance(operator, ast.IsNot):
                return left is not right
        except TypeError:
            raise self._rt(node, "Нельзя сравнить эти значения.") from None
        raise self._rt(node, "Недопустимое сравнение.")

    def _binop(self, operator: ast.operator, left: Any, right: Any, node: ast.AST) -> Any:
        try:
            if isinstance(operator, ast.Add):
                result = left + right
            elif isinstance(operator, ast.Sub):
                result = left - right
            elif isinstance(operator, ast.Mult):
                if isinstance(left, (str, list, tuple)) and type(right) is int:
                    if right > 0 and len(left) * right > max(MAX_STRING, MAX_SEQUENCE * 2):
                        raise self._rt(node, "Результат умножения слишком большой.")
                if isinstance(right, (str, list, tuple)) and type(left) is int:
                    if left > 0 and len(right) * left > max(MAX_STRING, MAX_SEQUENCE * 2):
                        raise self._rt(node, "Результат умножения слишком большой.")
                if type(left) is int and type(right) is int:
                    if left.bit_length() + right.bit_length() > MAX_INT_BITS * 2:
                        raise self._rt(node, "Числа слишком большие.")
                result = left * right
            elif isinstance(operator, ast.Div):
                if type(left) not in (int, float) or type(right) not in (int, float):
                    raise self._rt(node, "Деление работает только с числами.")
                result = left / right
            elif isinstance(operator, ast.FloorDiv):
                if type(left) not in (int, float) or type(right) not in (int, float):
                    raise self._rt(node, "// работает только с числами.")
                result = left // right
            elif isinstance(operator, ast.Mod):
                if type(left) not in (int, float) or type(right) not in (int, float):
                    raise self._rt(node, "% работает только с числами.")
                result = left % right
            elif isinstance(operator, ast.Pow):
                if type(left) not in (int, float) or type(right) not in (int, float):
                    raise self._rt(node, "** работает только с числами.")
                if abs(right) > 64:
                    raise self._rt(node, "Слишком большая степень.")
                if abs(left) > 10**9:
                    raise self._rt(node, "Слишком большое основание степени.")
                result = left**right
                if isinstance(result, complex):
                    raise self._rt(node, "Дробная степень отрицательного числа недоступна.")
            else:
                raise self._rt(node, "Недопустимая операция.")
        except ZeroDivisionError:
            raise self._rt(node, "Деление на ноль.") from None
        except (TypeError, ValueError, OverflowError):
            raise self._rt(node, "Нельзя выполнить операцию с этими значениями.") from None
        result = _guard_number(result)
        _check_sequence(result)
        return result

    def _call(self, node: ast.Call, env: _Environment) -> Any:
        function = self._eval(node.func, env)
        args = [self._eval(arg, env) for arg in node.args]
        kwargs: dict[str, Any] = {}
        for kw in node.keywords:
            if kw.arg is None:
                raise self._rt(node, "**kwargs запрещены.")
            kwargs[kw.arg] = self._eval(kw.value, env)

        if len(args) + len(kwargs) > 12:
            raise self._rt(node, "Слишком много аргументов у функции.")

        if isinstance(function, _UserFunction):
            return self._call_user_function(function, args, kwargs, node)

        if not callable(function) or isinstance(function, (UnitView, OwnView, PointView)):
            raise self._rt(node, "Это значение нельзя вызвать.")

        try:
            result = function(*args, **kwargs)
        except SpellError as exc:
            raise self._locate(node, exc) from None
        except TypeError:
            raise self._rt(node, "Неверное количество или тип аргументов.") from None
        except (RecursionError, MemoryError):
            raise self._rt(node, "Заклинание потребовало слишком много ресурсов.") from None
        except Exception:
            raise self._rt(node, "Внутренняя ошибка при вызове функции.") from None

        if isinstance(
            result,
            (UnitView, OwnView, PointView, int, float, bool, str, list, tuple, dict),
        ) or result is None:
            return _check_sequence(result)
        # Module-level API helpers never return arbitrary objects; if one does,
        # hide it rather than letting a spell inspect the host.
        return None

    def _call_user_function(
        self,
        function: _UserFunction,
        args: list[Any],
        kwargs: dict[str, Any],
        node: ast.Call,
    ) -> Any:
        if self.call_depth >= MAX_CALL_DEPTH:
            raise self._rt(node, "Слишком глубокая рекурсия заклинания.")
        if len(args) > len(function.args):
            raise self._rt(node, "Слишком много аргументов у функции.")
        local = _Environment(function.closure)
        required = len(function.args) - len(function.defaults)
        for index, name in enumerate(function.args):
            if index < len(args):
                value = args[index]
            elif name in kwargs:
                value = kwargs.pop(name)
            elif index >= required:
                value = function.defaults[index - required]
            else:
                raise self._rt(node, f"Не хватает аргумента «{name}».")
            local.set(name, value)
        if kwargs:
            extra = next(iter(kwargs))
            raise self._rt(node, f"Неизвестный аргумент «{extra}».")
        self.call_depth += 1
        try:
            self._exec_block(function.body, local)
        except _ReturnSignal as returned:
            return _check_sequence(returned.value)
        finally:
            self.call_depth -= 1
        return None


def call_function(
    source: str, globals_: Mapping[str, Any], name: str, args: Iterable[Any]
) -> Any:
    """Run a program, then call one of the functions it defined.

    This is how a task checks real code: what a function returns for given
    input, under the same limits as a cast.
    """

    interpreter = Interpreter(source, globals_)
    interpreter.run()
    function = interpreter.root.values.get(name)
    if not isinstance(function, _UserFunction):
        raise SpellRuntimeError(f"Функция {name} не найдена.")
    try:
        return interpreter._call_user_function(
            function, list(args), {}, function.body[0]
        )
    except SpellError:
        raise
    except RecursionError:
        raise SpellRuntimeError("Заклинание ушло в слишком глубокую рекурсию.") from None
    except (MemoryError, OverflowError):
        raise SpellRuntimeError("Заклинание потребовало слишком много ресурсов.") from None
    except Exception:
        raise SpellRuntimeError("Внутренняя ошибка заклинания.") from None


def execute_spell(source: str, globals_: Mapping[str, Any], keeper: Any = None) -> int:
    """Run one spell and return the number of AST steps consumed.

    ``keeper`` receives the interpreter before anything runs, so a spell can leave
    a function behind that outlives the cast (see ``call_later``).
    """

    interpreter = Interpreter(source, globals_)
    if keeper is not None:
        keeper.interpreter = interpreter
    interpreter.run()
    return interpreter.steps


def is_function(value: Any) -> bool:
    """Whether a spell's value can be called: its own def, or a rune named without brackets."""

    if isinstance(value, _UserFunction):
        return True
    return callable(value) and not isinstance(value, (UnitView, OwnView, PointView))


def call_later(interpreter: Interpreter, function: Any, args: Iterable[Any]) -> Any:
    """Call a function a spell kept for later, on the budget of a fresh cast."""

    interpreter.steps = 0
    interpreter.loop_iterations = 0
    interpreter.call_depth = 0
    call_args = list(args)
    if isinstance(function, _UserFunction):
        try:
            return interpreter._call_user_function(function, call_args, {}, ast.Call(ast.Constant(None), [], []))
        except _BreakSignal:
            raise SpellRuntimeError("break допустим только внутри цикла.") from None
        except _ContinueSignal:
            raise SpellRuntimeError("continue допустим только внутри цикла.") from None
        except RecursionError:
            raise SpellRuntimeError("Заклинание ушло в слишком глубокую рекурсию.") from None
        except (MemoryError, OverflowError):
            raise SpellRuntimeError("Заклинание потребовало слишком много ресурсов.") from None
    try:
        return function(*call_args)
    except TypeError:
        raise SpellRuntimeError("Неверное количество или тип аргументов.") from None
