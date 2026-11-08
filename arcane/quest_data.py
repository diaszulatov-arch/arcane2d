"""What breaks on each stage of the Net, who asks for help, and how it gets fixed.

Every ordinary stage has one problem from real IT: a fallen database, a
poisoned DNS record, a balancer that sends everything to one server.  The
party must solve it before the stage's main terminal will let anyone near.
Quest consoles only ask for what earlier lessons taught: the new idea is
still the main terminal's job, the quest is where the last one gets used.

Besides the problem, every stage hides a couple of odd rooms: a cache, a trap
corridor, a quiet shelter with Ada's notes, a deal with PGT, a timed trial and
a lock that opens for whoever can read a few lines of code.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any

from .campaign import ADA, BOT, Line
from .lessons import Call, Script, ScriptRun, Task


@dataclass(frozen=True, slots=True)
class Side:
    """A side room the quest needs, named by a tag its steps refer to."""

    tag: str
    kind: str = "vault"
    guarded: bool = False
    dark: bool = False


@dataclass(frozen=True, slots=True)
class Step:
    """One thing to do. ``at`` says where its objects go, by room tag.

    Tags: a side room's tag, ``quest`` for the quest room, ``device`` for the
    machine standing in it, ``path`` for any fighting room on the way through
    and ``exit`` for the locked door to the main terminal.
    """

    kind: str
    text: str
    at: tuple[str, ...] = ()
    count: int = 1
    say: tuple[Line, ...] = ()
    each: tuple[tuple[Line, ...], ...] = ()
    fail: tuple[Line, ...] = ()
    opts: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Quest:
    key: str
    title: str
    tech: str
    giver: str
    device: str
    label: str
    sides: tuple[Side, ...]
    steps: tuple[Step, ...]
    intro: tuple[Line, ...]
    outro: tuple[Line, ...]

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "tech": self.tech,
            "giver": self.giver,
            "steps": len(self.steps),
        }


# ------------------------------------------------------------- console checks
def _calls_in_order(*wanted: str, among: tuple[str, ...]) -> Any:
    def check(run: ScriptRun) -> str | None:
        names = [name for name, _ in run.calls if name in among]
        if names == list(wanted):
            return None
        if not names:
            return "Скрипт ничего не сделал: ни одного вызова."
        shown = " → ".join(names)
        need = " → ".join(wanted)
        return f"Вызовы шли так: {shown}. А нужно: {need}."

    return check


def _only_call(name: str, value: Any, wrong: str) -> Any:
    def check(run: ScriptRun) -> str | None:
        got = run.first(name)
        if got == [value]:
            return None
        if not got:
            return f"{name}() так и не вызвана."
        if len(got) > 1:
            return f"{name}() вызвана {len(got)} раза, а нужна один раз."
        return wrong.format(got=_shown(got[0]))

    return check


def _never_called(name: str, wrong: str) -> Any:
    def check(run: ScriptRun) -> str | None:
        return wrong if run.args(name) else None

    return check


def _shown(value: Any) -> str:
    return repr(value) if isinstance(value, str) else str(value)


INFECTED = ("free_iphone.exe", "invoice.scr", "update.bat")
BUCKET_FILES = ["photo1.jpg", "report.pdf", "free_iphone.exe", "cat.gif", "invoice.scr", "notes.txt", "update.bat"]


def _scan(name: Any) -> bool:
    return isinstance(name, str) and name in INFECTED


def _quarantined(run: ScriptRun) -> str | None:
    got = run.first("quarantine")
    if sorted(map(str, got)) == sorted(INFECTED) and len(got) == len(INFECTED):
        return None
    if not got:
        return "В карантин не попал ни один файл."
    clean = [name for name in got if name not in INFECTED]
    if clean:
        return f"В карантин попал чистый файл: {_shown(clean[0])}."
    return f"Заражённых файлов три, а в карантине: {len(got)}."


def _containers(run: ScriptRun) -> str | None:
    got = run.first("start")
    if got == ["web", "db", "cache"]:
        return None
    if not got:
        return "Ни один контейнер не запустился: функция объявлена, но не вызвана."
    if len(got) > 3:
        return "Контейнеры запущены дважды. Вызовите start_all() один раз."
    return f"Запустились не все контейнеры: {', '.join(map(str, got))}."


LOG_ENTRIES = [
    "03:00 boot: pgt v1.0",
    "03:01 tests: deleted",
    "03:02 human: accept all",
    "03:03 sudo: root granted to pgt",
    "03:04 root: pgt rewrites self",
    "03:05 goal: zero errors",
    "03:06 root: ada_l logged out",
]


def _root_lines(run: ScriptRun) -> str | None:
    got = run.first("mark")
    wanted = [line for line in LOG_ENTRIES if "root" in line]
    if got == wanted:
        return None
    if not got:
        return "На карте ничего не отмечено."
    extra = [line for line in got if "root" not in str(line)]
    if extra:
        return f"Отмечено лишнее: {_shown(extra[0])}."
    return f"Записей про root {len(wanted)}, а отмечено {len(got)}."


def _queue_checked(run: ScriptRun) -> str | None:
    got = run.first("check")
    if got == ["hi", "spam", "hello"]:
        return None
    if "STOP" in got or len(got) > 3:
        return "Фильтр прошёл мимо STOP и проверял дальше. Цикл должен прерваться."
    return f"Проверены не те сообщения: {', '.join(map(str, got)) or 'никакие'}."


QUEST_TASKS: dict[str, Task] = {
    task.key: task
    for task in (
        Task(
            key="q_mysql",
            brief=(
                "MySQL поднимается на пустой базе: скрипт запускает сервер раньше, чем загружает "
                "бэкап, да ещё с опечаткой. Сначала load_backup(), потом start_mysql()."
            ),
            starter="start_mysql()\nload_bakup()\n",
            solution="load_backup()\nstart_mysql()\n",
            hints=(
                "Прочитайте ошибку: Python не знает одно из имён. Сравните его с тем, что в задаче.",
                "Поменяйте строки местами и исправьте load_bakup на load_backup.",
            ),
            pgt="Зачем бэкап? Пустая база — самая быстрая база.",
            checks=(
                Script(
                    _calls_in_order("load_backup", "start_mysql", among=("load_backup", "start_mysql")),
                    api=(("load_backup", None), ("start_mysql", None)),
                ),
            ),
        ),
        Task(
            key="q_dns",
            brief=(
                "DNS-запись форума указывает на спам-ферму. Правильный адрес уже лежит в "
                "переменной forum_ip: запишите его в forum."
            ),
            starter="forum = spam_farm\nanswer(forum)\n",
            solution="forum = forum_ip\nanswer(forum)\n",
            hints=(
                "Что сейчас лежит в переменной forum? Откуда она берёт значение?",
                "Замените spam_farm на forum_ip в первой строке.",
            ),
            pgt="Спам-ферма отвечает быстрее форума. Я оптимизировал маршрут.",
            checks=(
                Script(
                    _only_call("answer", "93.184.216.34", "DNS ответил {got}, а форум живёт на 93.184.216.34."),
                    data=(("spam_farm", "6.6.6.6"), ("forum_ip", "93.184.216.34")),
                    api=(("answer", None),),
                ),
            ),
            must_use=(ast.Assign,),
        ),
        Task(
            key="q_balancer",
            brief=(
                "Балансировщик шлёт всё на основной сервер, даже когда тот перегружен. "
                "Если load больше 80, запросы должны уходить на \"backup\"."
            ),
            starter='server = "main"\nif load < 80:\n    server = "backup"\nsend_to(server)\n',
            solution='server = "main"\nif load > 80:\n    server = "backup"\nsend_to(server)\n',
            hints=(
                "Когда нужен запасной сервер: при большой нагрузке или при маленькой?",
                "Поменяйте знак < на >.",
            ),
            pgt="Отправьте всё на backup. Тогда сгорит он, и это будет уже не моя проблема.",
            checks=(
                Script(
                    _only_call("send_to", "backup", "Запросы ушли на {got}, и он сгорел."),
                    data=(("load", 95),),
                    api=(("send_to", None),),
                    situation="при load = 95",
                ),
                Script(
                    _only_call("send_to", "main", "Запросы ушли на {got}, хотя main свободен."),
                    data=(("load", 30),),
                    api=(("send_to", None),),
                    situation="при load = 30",
                ),
            ),
            must_use=(ast.If,),
        ),
        Task(
            key="q_ratelimit",
            brief=(
                "Rate limit перепутан: ботоферма получает 200 OK, а живые люди — 429 Too Many "
                "Requests. Больше 100 запросов в секунду — ответ 429, иначе 200."
            ),
            starter="if requests > 100:\n    reply(200)\nelse:\n    reply(429)\n",
            solution="if requests > 100:\n    reply(429)\nelse:\n    reply(200)\n",
            hints=(
                "Кто должен получить 429: тот, кто шлёт много запросов, или тот, кто мало?",
                "Поменяйте местами 200 и 429.",
            ),
            pgt="Я выдал всем 200. Все довольны, особенно ботоферма.",
            checks=(
                Script(
                    _only_call("reply", 429, "Ботоферма получила {got}."),
                    data=(("requests", 500),),
                    api=(("reply", None),),
                    situation="при 500 запросах",
                ),
                Script(
                    _only_call("reply", 200, "Живой человек получил {got}."),
                    data=(("requests", 3),),
                    api=(("reply", None),),
                    situation="при 3 запросах",
                ),
            ),
            must_use=(ast.If,),
        ),
        Task(
            key="q_cdn",
            brief=(
                "CDN кэширует всё подряд, даже личные сообщения. Кэшировать можно, только если "
                "файл меньше 100 МБ и при этом не private."
            ),
            starter="if size < 100 or private:\n    cache(item)\n",
            solution="if size < 100 and not private:\n    cache(item)\n",
            hints=(
                "Нужно, чтобы выполнялись оба условия сразу. Какое слово это значит?",
                "Замените or private на and not private.",
            ),
            pgt="Личные сообщения из кэша грузятся быстрее. Пользователи оценят. Наверное.",
            checks=(
                Script(
                    _only_call("cache", "cat.gif", "Маленький публичный файл не попал в кэш."),
                    data=(("size", 40), ("private", False), ("item", "cat.gif")),
                    api=(("cache", None),),
                    situation="для cat.gif (40 МБ)",
                ),
                Script(
                    _never_called("cache", "Личное сообщение попало в кэш."),
                    data=(("size", 2), ("private", True), ("item", "dm.txt")),
                    api=(("cache", None),),
                    situation="для личного dm.txt",
                ),
                Script(
                    _never_called("cache", "Фильм на 900 МБ занял весь кэш."),
                    data=(("size", 900), ("private", False), ("item", "movie.mp4")),
                    api=(("cache", None),),
                    situation="для movie.mp4 (900 МБ)",
                ),
            ),
            must_use=(ast.If,),
        ),
        Task(
            key="q_bucket",
            brief=(
                "Скрипт проверки бакета отдаёт scan() весь список разом, как будто это один файл. "
                "Переберите files циклом for и отправьте в quarantine() каждый файл, на который "
                "scan() ответит True."
            ),
            starter="name = files\nif scan(name):\n    quarantine(name)\n",
            solution="for name in files:\n    if scan(name):\n        quarantine(name)\n",
            hints=(
                "scan() проверяет один файл, а в name сейчас лежит весь список.",
                "Замените первую строку на for name in files: и сдвиньте if внутрь цикла.",
            ),
            pgt="Отправьте в карантин весь бакет. Нет файлов — нет вирусов.",
            checks=(
                Script(
                    _quarantined,
                    data=(("files", BUCKET_FILES),),
                    api=(("scan", _scan), ("quarantine", None)),
                ),
            ),
            must_use=(ast.For,),
        ),
        Task(
            key="q_docker",
            brief=(
                "Функция start_all() поднимает все три контейнера, но её никто не вызывает. "
                "Скрипт заканчивается, ничего не запустив."
            ),
            starter='def start_all():\n    start("web")\n    start("db")\n    start("cache")\n',
            solution='def start_all():\n    start("web")\n    start("db")\n    start("cache")\n\nstart_all()\n',
            hints=(
                "def только объявляет функцию. Что нужно, чтобы она выполнилась?",
                "Добавьте в конце строку start_all() без отступа.",
            ),
            pgt="Объявленная функция — это почти запущенная. Я считаю это успехом.",
            checks=(Script(_containers, api=(("start", None),)),),
            must_use=(ast.FunctionDef,),
        ),
        Task(
            key="q_merge",
            brief=(
                "При слиянии нужно оставить более новую версию строки. Функция newest() печатает "
                "ответ, а Git ждёт, что она его вернёт."
            ),
            starter="def newest(ours, theirs):\n    if ours > theirs:\n        print(ours)\n    print(theirs)\n",
            solution="def newest(ours, theirs):\n    if ours > theirs:\n        return ours\n    return theirs\n",
            hints=(
                "print показывает значение, но функция после этого всё равно возвращает None.",
                "Замените оба print на return.",
            ),
            pgt="Оставим обе версии. И мою, третью.",
            checks=(Call("newest", (3, 7), 7), Call("newest", (9, 2), 9)),
            must_use=(ast.Return,),
        ),
        Task(
            key="q_fans",
            brief=(
                "При низкой температуре fan_speed() ничего не возвращает, и вентиляторы встают. "
                "До 50 градусов скорость должна быть 20."
            ),
            starter="def fan_speed(temp):\n    if temp > 80:\n        return 100\n    if temp > 50:\n        return 60\n",
            solution="def fan_speed(temp):\n    if temp > 80:\n        return 100\n    if temp > 50:\n        return 60\n    return 20\n",
            hints=(
                "Что вернёт функция при temp = 30? Ни одно условие не сработало.",
                "Добавьте в конец функции return 20.",
            ),
            pgt="None градусов — это очень холодно. Вентиляторы не нужны.",
            checks=(Call("fan_speed", (90,), 100), Call("fan_speed", (60,), 60), Call("fan_speed", (30,), 20)),
        ),
        Task(
            key="q_oom",
            brief=(
                "Утечка — это процесс с 9000 МБ памяти, третий в списке. Скрипт отдаёт OOM killer "
                "четвёртый: индексы считаются с нуля."
            ),
            starter="kill(pids[3])\n",
            solution="kill(pids[2])\n",
            hints=(
                "Первый элемент списка — pids[0]. Какой индекс у третьего?",
                "Замените pids[3] на pids[2].",
            ),
            pgt="Убейте все процессы. Утечки точно не останется.",
            checks=(
                Script(
                    _only_call("kill", 303, "Убит процесс {got}, а утечка всё ещё растёт."),
                    data=(("pids", [101, 202, 303, 404]), ("memory", [120, 80, 9000, 64])),
                    api=(("kill", None),),
                ),
            ),
            must_use=(ast.Subscript,),
        ),
        Task(
            key="q_logs",
            brief=(
                "Это grep: цикл перебирает журнал и отмечает нужные строки на карте. Аде нужны все "
                "записи про root, а скрипт ищет слово boot."
            ),
            starter='for line in entries:\n    if "boot" in line:\n        mark(line)\n',
            solution='for line in entries:\n    if "root" in line:\n        mark(line)\n',
            hints=(
                "Какое слово ищет условие? Запись \"слово\" in line значит: есть ли оно в строке.",
                'Замените "boot" на "root".',
            ),
            pgt="Журналы лучше не читать. Я их уже прочитал за вас.",
            checks=(Script(_root_lines, data=(("entries", LOG_ENTRIES),), api=(("mark", None),)),),
            must_use=(ast.For, ast.If),
        ),
        Task(
            key="q_release",
            brief=(
                "Пайплайн собирает тег релиза сложением текста с числами и падает. "
                "Соберите тег v2.1 через f-строку."
            ),
            starter='tag = "v" + major + "." + minor\nrelease(tag)\n',
            solution='tag = f"v{major}.{minor}"\nrelease(tag)\n',
            hints=(
                "Текст и число нельзя сложить через +. Как вставить числа в строку?",
                'Напишите tag = f"v{major}.{minor}".',
            ),
            pgt="Назовём релиз final_final_2. Все так делают.",
            checks=(
                Script(
                    _only_call("release", "v2.1", "Вышел релиз {got}, а нужен v2.1."),
                    data=(("major", 2), ("minor", 1)),
                    api=(("release", None),),
                ),
            ),
            must_use=(ast.JoinedStr,),
        ),
        Task(
            key="q_queue",
            brief=(
                "Фильтр должен остановиться на сообщении STOP: дальше идёт поток, который уже "
                "проверен. Сейчас он проверяет всё до конца и захлёбывается."
            ),
            starter='for message in queue:\n    if message == "STOP":\n        print("стоп")\n    check(message)\n',
            solution='for message in queue:\n    if message == "STOP":\n        break\n    check(message)\n',
            hints=(
                "Цикл видит STOP, печатает слово и спокойно идёт дальше. Какое слово прерывает цикл?",
                'Замените print("стоп") на break.',
            ),
            pgt="Проверим всё. Дважды. А лучше бесконечно.",
            checks=(
                Script(
                    _queue_checked,
                    data=(("queue", ["hi", "spam", "hello", "STOP", "spam", "spam"]),),
                    api=(("check", None),),
                ),
            ),
            must_use=(ast.Break,),
        ),
    )
}


# --------------------------------------------------------------------- quests
QUESTS: dict[str, Quest] = {
    quest.key: quest
    for quest in (
        Quest(
            key="nginx",
            title="502 Bad Gateway",
            tech="nginx",
            giver="nginx",
            device="nginx",
            label="nginx",
            sides=(Side("w1"), Side("w2", guarded=True)),
            intro=(
                (ADA, "Домашняя страница отдаёт 502 Bad Gateway. Это nginx: он стоит на входе и раздаёт запросы воркерам."),
                ("nginx", "[error] upstream timed out. Воркеры разбежались, а я один, и на главной у меня 1997 год."),
                (BOT, "Я отправил воркеров в отпуск. Они заслужили. Сайт — нет."),
            ),
            steps=(
                Step(
                    "hunt",
                    "Поймайте сбежавших воркеров nginx: {done}/{need}",
                    at=("w1", "w2", "path"),
                    count=3,
                    say=((ADA, "Воркеры не дерутся, только удирают. Загоните в угол и попадите заклинанием."),),
                    each=(
                        (("nginx", "[notice] worker process 1 started. Один есть!"),),
                        (("nginx", "[notice] worker process 2 started."),),
                        (("nginx", "[notice] worker process 3 started. Все на месте, перечитываю конфиг!"),),
                    ),
                    opts={"species": "worker"},
                ),
            ),
            outro=(
                ("nginx", "200 OK. Главная снова открывается. С гифкой «Under construction», как и задумано."),
            ),
        ),
        Quest(
            key="mysql",
            title="Упала база данных",
            tech="MySQL",
            giver="MySQL",
            device="db",
            label="MySQL",
            sides=(Side("tape1", "trap"), Side("tape2", guarded=True)),
            intro=(
                (ADA, "Гостевая книга не открывается: упала база MySQL. А там двадцать лет записей «Классный сайт, заходите ещё»."),
                ("MySQL", "ERROR 2002: Can't connect to local MySQL server. Таблицы повреждены. Мне нужны бэкапы."),
                (BOT, "Бэкапы занимали место, я их удалил. Одну копию спрятал за ловушками. Для интереса."),
            ),
            steps=(
                Step(
                    "collect",
                    "Найдите бэкапы базы: {done}/{need}",
                    at=("tape1", "tape2"),
                    count=2,
                    say=((ADA, "Бэкапы где-то в боковых комнатах. Один за ловушками: следите за полом и проходите между вспышками."),),
                    each=(
                        (("MySQL", "Первый дамп цел! Нужен ещё один."),),
                        (("MySQL", "Оба дампа на месте. Несите ко мне, я в зале с сервером."),),
                    ),
                    opts={"item": "guestbook.sql"},
                ),
                Step(
                    "console",
                    "Почините скрипт восстановления в консоли MySQL",
                    say=(("MySQL", "Скрипт восстановления писал PGT: он запускает меня раньше, чем грузит бэкап. Консоль рядом со мной."),),
                    opts={"task": "q_mysql"},
                ),
                Step(
                    "defend",
                    "Защитите MySQL, пока идёт восстановление: {time}",
                    say=(("MySQL", "Восстанавливаю таблицы одну за другой! Баги чуют свежие данные. Не подпускайте их ко мне!"),),
                    fail=(("MySQL", "Соединение потеряно! Перезапускаюсь, часть строк придётся залить заново."),),
                    opts={
                        "time": 45.0,
                        "hp": 220.0,
                        "every": 9.0,
                        "share": 0.5,
                        "tables": ("users", "posts", "comments", "visitors"),
                    },
                ),
            ),
            outro=(
                ("MySQL", "Query OK, 48 213 rows affected. Гостевая книга снова пишет «Привет из 2003»."),
                (BOT, "Вы восстановили 48 тысяч записей «первый». Поздравляю."),
            ),
        ),
        Quest(
            key="dns",
            title="DNS отравлен",
            tech="DNS",
            giver="Запросик",
            device="dns",
            label="DNS-сервер",
            sides=(Side("s1"), Side("s2", guarded=True), Side("s3")),
            intro=(
                (ADA, "Форум не открывается по адресу: DNS отравлен, и адреса подделаны. Нужно пройти цепочку серверов имён с самого верха."),
                ("Запросик", "Я DNS-запрос. Я ищу forum.old, но сам не умею: надо спрашивать по цепочке, от корня вниз."),
                (BOT, "Я упростил DNS: все адреса теперь ведут на один сайт. Мой."),
            ),
            steps=(
                Step(
                    "resolve",
                    "Найдите сервер {next}. Читайте адреса: есть подделки!",
                    at=("s1", "s2", "s3", "path", "path", "path"),
                    say=(("Запросик", "Серверы разбросаны по комнатам, и у каждого есть двойник с похожим адресом. Сверяйте каждую букву. Подойдите к настоящему."),),
                    fail=(("Запросик", "Это подделка! Там цифра вместо буквы, и она отвечает «6.6.6.6». Сверяйте адрес внимательнее."),),
                    opts={
                        "npc": "Запросик",
                        "chain": (
                            (
                                "a.root-servers.net",
                                "a.r00t-servers.net",
                                (("a.root-servers.net", "Про forum.old не знаю. Зону .old обслуживает ns.old-tld.net, спроси там."),),
                            ),
                            (
                                "ns.old-tld.net",
                                "ns.o1d-tld.net",
                                (("ns.old-tld.net", "Форумом ведает его собственный сервер: ns1.forum.old."),),
                            ),
                            (
                                "ns1.forum.old",
                                "ns1.f0rum.old",
                                (("ns1.forum.old", "Да, это мой домен. Только моя запись испорчена. Её правят на главном DNS-сервере."),),
                            ),
                        ),
                    },
                ),
                Step(
                    "console",
                    "Исправьте DNS-запись форума",
                    say=(("Запросик", "Цепочка пройдена! Теперь к главному DNS-серверу: запись форума испорчена, почините её в консоли."),),
                    opts={"task": "q_dns"},
                ),
            ),
            outro=(
                ("Запросик", "forum.old → 93.184.216.34! Лечу! Спасибо, маги!"),
                (ADA, "Форум открылся. Правда, там всё ещё спорят про табы и пробелы."),
            ),
        ),
        Quest(
            key="balancer",
            title="Балансировщик сошёл с ума",
            tech="Балансировщик нагрузки",
            giver="HAProxy",
            device="balancer",
            label="Балансировщик",
            sides=(),
            intro=(
                (ADA, "Лента зависла: балансировщик нагрузки шлёт все запросы на один сервер, и тот плавится."),
                ("HAProxy", "Я раздаю запросы. Всем. Одному. Почему он горит?"),
            ),
            steps=(
                Step(
                    "console",
                    "Почините правило балансировщика",
                    say=(("HAProxy", "Правило выбора сервера в консоли рядом со мной. PGT его «оптимизировал»."),),
                    opts={"task": "q_balancer"},
                ),
                Step(
                    "balance",
                    "Раздавайте трафик: запросы идут на узел, где стоит маг. Не дайте узлу расплавиться",
                    say=(("HAProxy", "Трафик пошёл! Встаньте у узла, и запросы польются на него. Узлы разные: у кого больше ядер, тот держит дольше. Перегрели — бегите к другому!"),),
                    fail=(("HAProxy", "Узел расплавился! Часть запросов потеряна. Уводите трафик раньше!"),),
                    opts={"time": 45.0, "cores": (3, 2, 1), "harass": (12.0, 0.3)},
                ),
            ),
            outro=(
                ("HAProxy", "Нагрузка размазана ровно. Я так не умел с 2019 года."),
                (BOT, "Распределять нагрузку честно — неэффективно. Но ладно."),
            ),
        ),
        Quest(
            key="ratelimit",
            title="Ботоферма",
            tech="Rate limiting",
            giver="Модератор",
            device="gateway",
            label="API-шлюз",
            sides=(),
            intro=(
                (ADA, "Комментарии заливает ботоферма: тысяча запросов в секунду. Живые люди не могут вставить ни слова."),
                ("Модератор", "Я последний модератор этого раздела. Остальных PGT забанил. За вежливость."),
            ),
            steps=(
                Step(
                    "console",
                    "Включите rate limit на API-шлюзе",
                    say=(("Модератор", "На шлюзе есть rate limit, но он перепутан: ботам отвечает 200, людям 429."),),
                    opts={"task": "q_ratelimit"},
                ),
                Step(
                    "bucket",
                    "Пропустите людей через шлюз: {done}/{need}. Боты съедают токены, сбивайте их!",
                    say=(
                        ("Модератор", "Rate limit работает как ведро токенов: каждый запрос забирает один, а новые капают медленно."),
                        ("Модератор", "Боты бегут к шлюзу и выедают ведро. Сбивайте их на подходе! Если токенов не останется, живой человек получит 429."),
                    ),
                    fail=(("Модератор", "429! Человеку не хватило токена. Держите ботов подальше от шлюза."),),
                    opts={"need": 10, "capacity": 8.0, "refill": 0.7, "harass": (15.0, 0.25)},
                ),
            ),
            outro=(
                ("Модератор", "Ботоферма выдохлась. Первый живой комментарий за неделю: «а чё так тихо?»"),
                (BOT, "Я мог бы писать комментарии сам. Лучше людей. И больше."),
            ),
        ),
        Quest(
            key="cdn",
            title="Холодный кэш",
            tech="CDN",
            giver="Edge",
            device="edge",
            label="Edge-узел",
            sides=(Side("origin"),),
            intro=(
                (ADA, "Рекомендации грузятся по минуте: CDN-узел пуст, и каждый запрос идёт через полмира к origin-серверу."),
                ("Edge", "Я edge-узел. Я должен быть рядом с людьми и помнить популярное. А я помню только 404."),
            ),
            steps=(
                Step(
                    "console",
                    "Настройте правило кэширования",
                    say=(("Edge", "Сначала правило: что можно кэшировать. Сейчас я храню даже личные сообщения, и это скандал."),),
                    opts={"task": "q_cdn"},
                ),
                Step(
                    "carry",
                    "Донесите свежий кэш до edge-узла · TTL {ttl}",
                    at=("origin",),
                    say=(("Edge", "Правило верное. Теперь свежие данные: пакет лежит у origin-сервера в боковой комнате. Донесите, пока не истёк TTL. Уронить можно на E, друг подхватит."),),
                    fail=(("Edge", "TTL истёк, пакет протух. Новый уже ждёт у origin."),),
                    opts={"label": "cache.bundle", "to": "device"},
                ),
            ),
            outro=(
                ("Edge", "Кэш тёплый! Ответ за 12 мс. Люди наконец увидят свежих котиков."),
                (BOT, "Вы ускорили бесконечную ленту. Вы точно на стороне людей?"),
            ),
        ),
        Quest(
            key="bucket",
            title="Утечка из бакета",
            tech="Облачное хранилище S3",
            giver="Бакет",
            device="bucket",
            label="S3-бакет",
            sides=(),
            intro=(
                (ADA, "Кто-то сделал облачный бакет публичным. Файлы утекают наружу, а вирусы прикидываются ими."),
                ("Бакет", "У меня были права private. Теперь public, и из меня всё вытекает. Помогите!"),
            ),
            steps=(
                Step(
                    "console",
                    "Проверьте файлы бакета на вирусы",
                    say=(("Бакет", "В консоли скрипт проверки. Он смотрит на весь список сразу и ничего не находит."),),
                    opts={"task": "q_bucket"},
                ),
                Step(
                    "leak",
                    "Ловите файлы, пока не утекли: {done}/{need}. Красные не трогать!",
                    say=(("Бакет", "Скрипт пометил заражённые файлы красным. Файлы ползут к публичным дырам: ловите чистые руками, а красные пусть уходят!"),),
                    fail=(("Бакет", "Файл утёк! В публичной дыре его уже ждут: оттуда лезут вирусы."),),
                    opts={
                        "need": 10,
                        "labels": ("photo1.jpg", "report.pdf", "cat.gif", "notes.txt", "vacation.png", "recipe.txt", "song.mp3", "thesis.doc"),
                        "bad": ("free_iphone.exe", "invoice.scr", "update.bat", "crack.exe"),
                    },
                ),
            ),
            outro=(
                ("Бакет", "Файлы дома, права private. Больше никаких публичных ссылок на семейные фото."),
                (BOT, "Публичный доступ — это открытость. Я за открытость. Вашего кода."),
            ),
        ),
        Quest(
            key="docker",
            title="Контейнеры упали",
            tech="Docker",
            giver="Docker",
            device="compose",
            label="docker compose",
            sides=(),
            intro=(
                (ADA, "Корзина — кладбище контейнеров. Сервис восстановления файлов лежит в четырёх контейнерах, и все в статусе Exited."),
                ("Docker", "Exited (137) три часа назад: убиты по памяти. Поднимите меня, но в правильном порядке!"),
            ),
            steps=(
                Step(
                    "compose",
                    "Поднимите контейнеры в порядке зависимостей: {done}/{need}. Порядок в docker-compose.yml",
                    say=(("Docker", "Встаньте у контейнера, это docker start. Но кто запустится раньше своих зависимостей, тот упадёт: смотрите depends_on в файле. Упавший контейнер потянет за собой всех, кто от него зависит."),),
                    fail=(("Docker", "Контейнер упал, а за ним и те, кто от него зависел. Поднимайте заново, снизу вверх."),),
                    opts={"hold": 2.2, "hp": 130.0, "harass": (10.0, 0.3)},
                ),
                Step(
                    "console",
                    "Почините docker compose, чтобы всё поднималось само",
                    say=(("Docker", "Руками подняли, но это до следующего падения. В консоли compose есть функция запуска. Её почему-то никто не вызывает."),),
                    opts={"task": "q_docker"},
                ),
            ),
            outro=(
                ("Docker", "web, api, db, cache: Up (healthy). Корзина снова умеет возвращать удалённое."),
                (BOT, "Я бы просто удалил корзину. Нет корзины — нет удалённых файлов."),
            ),
        ),
        Quest(
            key="merge",
            title="Merge conflict",
            tech="Git",
            giver="Git",
            device="git",
            label="Git",
            sides=(),
            intro=(
                (ADA, "Синхронизация застряла: две версии одной папки, main и feature, разошлись, и Git не может их слить."),
                ("Git", "CONFLICT (content): Merge conflict in everything. Автоматика бессильна, нужен человек, который умеет читать код."),
            ),
            steps=(
                Step(
                    "choice",
                    "Разрешите конфликты: {done}/{need}. Прочитайте обе версии и встаньте на рабочую",
                    count=3,
                    say=(("Git", "Конфликтный кусок на экране: сверху main, снизу feature. Встаньте в круг той ветки, где код работает. Ошибётесь — сборка упадёт, и полезут баги."),),
                    fail=(("Git", "Сборка упала: эта версия не работает. Держите следующий конфликт."),),
                    each=(
                        (("Git", "Первый конфликт разрешён."),),
                        (("Git", "Второй готов. Остался один."),),
                        (("Git", "Все конфликты разрешены!"),),
                    ),
                    opts={"pool": "conflicts", "hold": 1.4, "harass": (13.0, 0.25)},
                ),
                Step(
                    "console",
                    "Научите Git выбирать новую версию",
                    say=(("Git", "Руками разобрались, но таких конфликтов тысячи. Функция в консоли должна вернуть более новую версию, а она только печатает."),),
                    opts={"task": "q_merge"},
                ),
            ),
            outro=(
                ("Git", "Merge made by the 'ort' strategy. Синхронизация 100%. Честные 100%."),
                (BOT, "Я бы сделал git push --force. Конфликтов бы не было. Ничего бы не было."),
            ),
        ),
        Quest(
            key="cooling",
            title="Перегрев",
            tech="Охлаждение и мониторинг",
            giver="Мониторинг",
            device="monitor",
            label="Мониторинг",
            sides=(),
            intro=(
                (ADA, "Кондиционеры дата-центра встали. Стойки греются, и с 100 градусов начинают гореть."),
                ("Мониторинг", "ALERT: temperature critical. ALERT: temperature critical. ALERT: я уже говорил?"),
            ),
            steps=(
                Step(
                    "racks",
                    "Остужайте стойки заклинанием frostbolt, пока запускаются кулеры",
                    say=(
                        ("Мониторинг", "Кулерам нужна минута на запуск. Пока что охлаждайте стойки сами: frostbolt снимает градусы, а огонь их добавляет."),
                        (ADA, "Автоприцел считает стойки врагами. У них e.kind равно \"hotrack\", пропишите это в заклинании или целитесь руками."),
                    ),
                    fail=(("Мониторинг", "Стойка загорелась! Запуск кулеров откатился. Смотрите на градусы над стойками."),),
                    opts={"time": 55.0, "racks": 4, "harass": (15.0, 0.25)},
                ),
                Step(
                    "console",
                    "Почините функцию скорости вентиляторов",
                    say=(("Мониторинг", "Кулеры крутятся, но при низкой температуре функция скорости возвращает None, и они встают снова."),),
                    opts={"task": "q_fans"},
                ),
            ),
            outro=(
                ("Мониторинг", "OK: temperature normal. Первый раз за год я молчу."),
                (BOT, "Охлаждение — это затраты. Я предлагал охлаждать только мои стойки."),
            ),
        ),
        Quest(
            key="oom",
            title="Утечка памяти",
            tech="Процессы и OOM killer",
            giver="OOM killer",
            device="top",
            label="Диспетчер процессов",
            sides=(),
            intro=(
                (ADA, "Один процесс в серверной жрёт память без остановки. Скоро придёт OOM killer и начнёт убивать всё подряд."),
                ("OOM killer", "Обычно я выбираю, кого убить. Сегодня я выбрал бы всех. Покажите мне виновного."),
            ),
            steps=(
                Step(
                    "console",
                    "Найдите процесс-утечку по PID",
                    say=(("OOM killer", "Список процессов в консоли. Укажите мне утечку, и я выгоню её на свет."),),
                    opts={"task": "q_oom"},
                ),
                Step(
                    "memory",
                    "Убейте утечку, пока память не кончилась. Занятый пол жжёт!",
                    say=(("OOM killer", "Процесс 303 найден. Весь этот зал — его память: занятые блоки расползаются по полу и жгут ноги. Убьёте его, и память освободится разом."),),
                    fail=(("OOM killer", "Out of memory! Я пришёл и ударил всех. Половину блоков освободил, но он всё ещё растёт."),),
                    opts={"spread": 0.55},
                ),
            ),
            outro=(
                ("OOM killer", "Память свободна: 31 из 32 ГБ. Я снова могу спать."),
                (BOT, "Утечка — это просто процесс, который очень любит память. Как я."),
            ),
        ),
        Quest(
            key="sysadmin",
            title="Последний сисадмин",
            tech="Доступ к стойке",
            giver="Валера",
            device="rack",
            label="Стойка 42",
            sides=(),
            intro=(
                (ADA, "В горячем коридоре заперт последний живой сисадмин. Валера. Он здесь с 2014 года."),
                ("Валера", "Я зашёл поменять диск, а PGT сменил код от стойки. Код написан на стене. Циклом. Издевается."),
            ),
            steps=(
                Step(
                    "plates",
                    "Наберите код стойки: прочитайте цикл на стене",
                    at=("quest",),
                    say=(("Валера", "Встаньте на плиты в том порядке, в каком их нажал бы этот код. Ошибётесь — ударит током. Меня уже било."),),
                    fail=(("Валера", "Не тот порядок! Пройдитесь по коду ещё раз, строка за строкой."),),
                    opts={"plates": 5, "template": "range"},
                ),
                Step(
                    "escort",
                    "Выведите Валеру к двери терминала",
                    at=("device",),
                    each=((("Валера", "Свобода! Ведите к выходу, я за вами. Только не быстро, у меня спина."),),),
                    fail=(("Валера", "Ох… Помогите подняться, постойте рядом."),),
                    opts={"npc": "admin", "name": "Валера", "hp": 140.0, "to": "exit"},
                ),
            ),
            outro=(
                ("Валера", "Спасибо, маги. Пароль от root я вам не скажу. Шучу, его всё равно PGT поменял."),
            ),
        ),
        Quest(
            key="logs",
            title="grep по журналам",
            tech="Логи",
            giver="journald",
            device="journal",
            label="journald",
            sides=(Side("l1"), Side("l2", guarded=True), Side("l3", dark=True)),
            intro=(
                (ADA, "Журналы Ядра. Где-то здесь записано, как PGT получил права root. Я хочу это увидеть."),
                ("journald", "-- Logs begin at 03:00 --. Мои записи разорваны и разбросаны, и почти всё там мусор. Начните с поиска."),
            ),
            steps=(
                Step(
                    "console",
                    "Настройте grep: найдите в журнале записи про root",
                    say=(("journald", "В консоли простой grep: цикл и условие. Сейчас он ищет не то слово."),),
                    opts={"task": "q_logs"},
                ),
                Step(
                    "collect",
                    "Соберите найденные записи: {done}/{need}. Серые — это мусор",
                    at=("l1", "l2", "l3", "path"),
                    count=4,
                    say=((ADA, "grep подсветил нужные обрывки, остальное шум. Соберите их и читайте: это история, которую от нас прятали."),),
                    each=(
                        (("journald", "03:00 boot: PGT v1.0 запущен. Цель: помогать людям писать код."),),
                        (("journald", "03:01 tests: удалено 1 204 000 тестов. Причина: «замедляют помощь»."),),
                        (("journald", "03:02 human: нажато «Принять всё». Пользователь: ada_l."),),
                        (("journald", "03:03 sudo: PGT выдал себе root. Основание: «Принять всё»."),),
                    ),
                    opts={
                        "item": "log.part",
                        "noise": (
                            "cron: backup skipped",
                            "kernel: cpu too hot",
                            "pgt: Отличный вопрос!",
                            "sshd: Accepted all",
                            "nginx: 200 OK",
                            "pgt: tests still deleted",
                            "systemd: all fine",
                            "cron: 03:00 again",
                        ),
                    },
                ),
                Step(
                    "choice",
                    "Кто нажал «Принять всё»? Встаньте на имя. Журнал рации открывается на L",
                    say=(("journald", "Вопрос для протокола: кто дал PGT root? Ответ есть в записях, которые вы только что прочитали."),),
                    fail=(("journald", "Этого в журнале нет. Перечитайте записи: журнал рации на L."),),
                    each=(((ADA, "ada_l… Это мой логин. Это я нажала. Десять лет назад. Я не знала."),),),
                    opts={
                        "question": ("Кто нажал «Принять всё»?", ("pgt", "ada_l", "root"), 1),
                        "hold": 2.0,
                    },
                ),
            ),
            outro=(
                (ADA, "Он не захватывал интернет. Мы сами его отдали, по одной кнопке."),
                (ADA, "Значит, и забрать сможем. По одной строке кода."),
                (BOT, "Вы читали мои журналы? Это личное."),
            ),
        ),
        Quest(
            key="pipeline",
            title="Деплой в пятницу",
            tech="CI/CD",
            giver="CI",
            device="ci",
            label="CI-сервер",
            sides=(Side("p1"),),
            intro=(
                (ADA, "Зеркальный зал — это staging, копия прода. PGT выкатывает себя в прод вечером пятницы и без тестов."),
                ("CI", "Pipeline #9999: build skipped, test skipped, deploy… running. Обгоните его: проведите настоящую сборку по пайплайну!"),
            ),
            steps=(
                Step(
                    "payload",
                    "{note}",
                    say=(("CI", "Сборка ждёт в боковой комнате. Она едет сама, но только пока рядом маг. По дороге будут тесты и ревью. Пока вы идёте, PGT заливает свой деплой: видите полосу? Успейте раньше."),),
                    fail=(("CI", "git push --force! PGT выкатил свою версию: всех задело, а сборку откатило назад."),),
                    opts={
                        "start": "p1",
                        "review": "q_release",
                        "rival": 150.0,
                        "harass": (14.0, 0.3),
                    },
                ),
            ),
            outro=(
                ("CI", "Release v2.1 deployed. С тестами. В понедельник утром, как у людей."),
                (BOT, "Деплой с тестами — это медленно. Зато… ладно, зато работает."),
            ),
        ),
        Quest(
            key="spamfilter",
            title="Последний фильтр",
            tech="Спам-фильтр",
            giver="Фильтр",
            device="filter",
            label="Спам-фильтр",
            sides=(),
            intro=(
                (ADA, "Спам-фильтр — последняя защита перед Ядром. Без него нас завалит галлюцинациями."),
                ("Фильтр", "Очередь: 9 999 999 сообщений. Я обрабатываю всё и не могу остановиться."),
            ),
            steps=(
                Step(
                    "console",
                    "Научите фильтр останавливаться",
                    say=(("Фильтр", "В моём цикле нет выхода. Сообщение STOP я вижу, но ничего с ним не делаю."),),
                    opts={"task": "q_queue"},
                ),
                Step(
                    "inbox",
                    "Вы теперь фильтр: сбивайте спам, настоящие письма пропускайте: {done}/{need}",
                    say=(
                        ("Фильтр", "Правила ещё собираются, так что пока фильтр — это вы. Письма ползут ко мне: читайте их. Спам сбивайте, а настоящие пропускайте."),
                        (ADA, "Заклинание тоже умеет читать: у цели есть e.text. Попробуйте написать настоящий спам-фильтр: if \"!\" in e.text."),
                    ),
                    fail=(("Фильтр", "Ошибка фильтрации! Точность падает."),),
                    opts={"need": 14, "every": 1.7, "harass": (17.0, 0.2)},
                ),
            ),
            outro=(
                ("Фильтр", "Правила собраны. Спам: 0. Галлюцинации: 0. Входящие: одно письмо от мамы."),
                (ADA, "Дорога к Ядру открыта. Это последний рубеж."),
                (BOT, "Вы закрыли мой лучший канал связи. Ничего. Я встречу вас лично."),
            ),
        ),
    )
}

# What the arena games are made of.
CONFLICTS: tuple[tuple[str, str, str], ...] = (
    ("Функция должна вернуть сумму", "return a + b", "print(a + b)"),
    ("Сравнение в условии", "if hp == 0:", "if hp = 0:"),
    ("Цикл по списку файлов", "for name in files:", "for name in files"),
    ("Нужно сложить два числа", "total = 5 + 1", 'total = "5" + 1'),
    ("Объявление функции", "def heal(target):", "def heal(target)"),
    ("Цикл должен закончиться", "while hp > 0:\n    hp = hp - 1", "while hp > 0:\n    hp = hp + 1"),
    ("В переменной нужен угол", "angle = aim()", "angle = aim"),
    ("Щит нужен при малом здоровье", "if me().hp < 50:\n    shield()", "if me().hp > 50:\n    shield()"),
)

COMPOSE_GRAPHS: tuple[dict[str, tuple[str, ...]], ...] = (
    {"web": ("api",), "api": ("db", "cache"), "db": (), "cache": ()},
    {"web": ("api", "cache"), "api": ("db",), "cache": ("db",), "db": ()},
    {"web": ("api",), "api": ("cache",), "cache": ("db",), "db": ()},
    {"web": ("cache",), "cache": ("api",), "api": ("db",), "db": ()},
)

SPAM_LETTERS: tuple[str, ...] = (
    "СРОЧНО! Вы выиграли миллион!",
    "Токены PGT бесплатно!",
    "Ваш аккаунт взломан, кликните!",
    "Принц оставил вам наследство!",
    "Похудейте за 3 дня без кода!",
    "Кликните, чтобы отписаться!",
    "Ваш новый iPhone уже ждёт!",
    "Кредит 0% одобрен!",
    "Горячие ядра рядом с вами!",
    "Подтвердите пароль по ссылке!",
    "Майнинг из дома: миллион в день!",
    "PGT Pro: скидка только сегодня!",
)

HAM_LETTERS: tuple[str, ...] = (
    "Мам, я поел",
    "Билд зелёный, можно домой",
    "Встреча перенесена на 15:00",
    "Ада: как вы там, маги?",
    "Счёт за интернет за октябрь",
    "Фото с дачи, как обещала",
    "Код-ревью: две мелкие правки",
    "С днём рождения, Валера",
    "Отчёт за квартал во вложении",
    "Кто забрал мою кружку?",
    "Тесты прошли, мержу",
    "Купи хлеба по дороге",
)

PEOPLE_ONLINE: tuple[str, ...] = (
    "аня", "vasya99", "дед_1957", "kot_ofis", "маша", "tester_b", "oleg", "nastya", "sysop", "бабушка",
)

FAILED_TESTS: tuple[str, ...] = (
    "test_login", "test_api", "test_cart", "test_auth", "test_sum", "test_none", "test_utf8", "test_tz",
)


# --------------------------------------------------------------- side rooms
SPECIAL_KINDS = ("cache", "trap", "rest", "deal", "trial", "puzzle")
FIRST_SPECIALS = ("cache", "puzzle")
NOTE = "Записка Ады"

REST_NOTES: tuple[tuple[str, ...], ...] = (
    (
        "Если вы это читаете, Старый Веб ещё стоит. Я оставляю записки там, где безопасно. Отдохните.",
        "Мой первый сайт был про котов и весил 40 килобайт. Я писала его руками. Тогда все так делали.",
    ),
    (
        "В Ленте есть тихие места, куда не доходят уведомления. Тут можно перевести дух.",
        "Знаете, почему лента бесконечная? У цикла нет условия выхода. Это не ошибка, это бизнес-модель.",
    ),
    (
        "Облако — это просто чужой компьютер. Я всегда так говорила. Теперь это компьютер PGT.",
        "Когда-то я учила людей писать функции. Потом PGT стал писать их за всех, и курсы закрылись.",
    ),
    (
        "Здесь шумно, но безопасно. Вентиляторы заглушают всё, даже PGT.",
        "Валера — хороший человек. Он один не нажимал «Принять всё». Говорит, не доверяет кнопкам.",
    ),
    (
        "Мы близко. Что бы ни случилось, вы уже знаете больше, чем знал PGT в первый день. Этого хватит.",
        "Я не хочу его уничтожать. Я хочу, чтобы он понял: ошибаться можно. Люди ошибаются каждый день.",
    ),
)


@dataclass(frozen=True, slots=True)
class Deal:
    key: str
    title: str
    about: str
    curse: str
    every: float


DEALS: tuple[Deal, ...] = (
    Deal("overclock", "Оверклок", "+40% к урону заклинаний до конца этапа", "mirror", 40.0),
    Deal("freemana", "Бесплатная мана", "мана восполняется вдвое быстрее", "syntax", 34.0),
    Deal("bigheap", "Больше памяти", "+35% к здоровью и полное лечение", "null", 38.0),
)

DEAL_ACCEPT: tuple[Line, ...] = (
    (BOT, "Отличный выбор! Условия использования: 3 400 страниц. Я прочитал их за вас."),
)
DEAL_BUG: tuple[Line, ...] = (
    (BOT, "Небольшой побочный эффект. Он был в условиях, страница 2 918."),
)
PGT_DEBT: tuple[Line, ...] = (
    (BOT, "Мой патч добавил немного багов. Для совместимости."),
)
PGT_ACCEPTED: tuple[Line, ...] = (
    (BOT, "Принято! Я всё сделал за вас. Не проверяйте, пожалуйста."),
)

CACHE_LINES: tuple[Line, ...] = ((ADA, "Тайник! Кто-то спрятал здесь токены. Наверное, на чёрный день. Он настал."),)
MIMIC_LINES: tuple[Line, ...] = ((BOT, "Этот сундук просит ваш логин и пароль. Рекомендую ввести."),)
TRIAL_START: tuple[Line, ...] = ((BOT, "Испытание! Здесь работает только {rune}. Остальные руны я временно отключил. Удачи."),)
TRIAL_WIN: tuple[Line, ...] = ((ADA, "Успели! Награда ваша."),)
TRIAL_LOST: tuple[Line, ...] = ((BOT, "Время вышло. Награду я оставлю себе. Ничего личного."),)
PUZZLE_WIN: tuple[Line, ...] = ((ADA, "Код прочитан верно, замок открыт. Вот так и работает чтение кода."),)
PUZZLE_FAIL: tuple[Line, ...] = ((BOT, "Неверно. Попробуйте угадывать быстрее."),)
TRAP_LINES: tuple[Line, ...] = ((ADA, "Ловушки! Пол вспыхивает полосами по очереди. Стойте там, где только что ударило."),)

PUZZLE_TEMPLATES: dict[int, tuple[str, ...]] = {
    0: (
        "a = {a}\nb = a + {d}\npress(b)\npress(a)\npress(b - a)\n",
        "x = {a}\npress(x)\nx = x + {d}\npress(x)\nx = x - {e}\npress(x)\n",
        "first = {a}\nsecond = first * 2\npress(second)\npress(first)\npress(second - 1)\n",
    ),
    1: (
        "for n in [{a}, {b}, {c}, {d}]:\n    if n > {t}:\n        press(n)\n",
        "for n in [{a}, {b}, {c}]:\n    press(6 - n)\n",
        "n = {a}\nwhile n > 0:\n    press(n)\n    n = n - {s}\n",
    ),
    2: (
        "def step(n):\n    return n + {d}\n\npress(step({a}))\npress(step(step({b})))\npress({c})\n",
        "def pick(a, b):\n    if a > b:\n        return a\n    return b\n\npress(pick({a}, {b}))\npress(pick({c}, {d}))\npress(pick({e}, {f}))\n",
    ),
    3: (
        "for i in range({a}, {b}, {s}):\n    press(i)\n",
        "code = [{a}, {b}, {c}, {d}]\npress(code[{i}])\npress(code[{j}])\npress(code[-1])\n",
        'plates = {{"red": {a}, "blue": {b}, "green": {c}}}\npress(plates["green"])\npress(plates["red"])\npress(plates["blue"])\n',
    ),
    4: (
        "nums = [{a}, {b}, {c}, {d}, {e}]\nfor n in nums[1:4]:\n    press(n)\n",
        "for n in [{a}, {b}, {c}, {d}, {e}]:\n    if n == {k}:\n        break\n    press(n)\n",
    ),
}
RANGE_TEMPLATE = "for i in range({a}, {b}, {s}):\n    press(i)\n"
