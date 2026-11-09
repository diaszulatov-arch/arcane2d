"""The bestiary: who lives in each chapter and how they fight.

Monsters think in plain Python here, not in the spell sandbox.  ``think`` runs
once a tick for each of them and only ever talks to the world through the small
set of verbs on ``StoryArena``, the same way a mage's spell talks to the arena.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from .boss_moves import autocomplete
from .game import PLAYER_RADIUS, Player

if TYPE_CHECKING:
    from .story import StoryArena


@dataclass(frozen=True, slots=True)
class Species:
    key: str
    title: str
    hint: str
    hp: float
    speed: float
    radius: float
    contact: float
    color: str
    cost: float
    ai: str
    shot_damage: float = 0.0
    shot_speed: float = 320.0
    interval: float = 2.2
    shots: int = 1
    spread: float = 0.0
    range: float = 420.0
    immune: frozenset[str] = frozenset()
    weak: frozenset[str] = frozenset()
    guard: bool = False
    slows: bool = False
    mana_burn: float = 0.0
    on_death: str = ""
    boss: bool = False
    heavy: bool = False
    pack: int = 1
    shot_radius: float = 7.0
    shot_life: float = 2.6


@dataclass(slots=True)
class Monster(Player):
    species: Species | None = None
    state: str = "idle"
    state_until: float = 0.0
    next_attack: float = 0.0
    next_contact: float = 0.0
    next_special: float = 0.0
    heading: float = 0.0
    generation: int = 0
    phase: int = 0
    spin: float = 0.0
    wobble: float = 0.0
    orbit: float = 0.0
    origin: tuple[float, float] = (0.0, 0.0)
    minion: bool = False
    leaked: bool = False
    marked_until: float = 0.0
    marked_by: int = 0
    mark_jumps: int = 0
    hacked_until: float = 0.0
    hacked_by: int = 0
    exposed_until: float = 0.0
    dizzy_until: float = 0.0
    strikes: int = 0
    specials: int = 0
    deploy_hp: float = 0.0
    route_until: float = 0.0
    route_angle: float = 0.0
    focus: int = 0
    quest: str = ""
    text: str = ""
    elite: str = ""
    pace: float = 1.0
    returning_until: float = 0.0
    tricks: int = 0
    link: int = 0
    charge: float = 0.0
    count: int = 0
    hurry_until: float = 0.0
    escort: bool = False
    marks: dict[str, Any] | None = None
    memo: Any = None


@dataclass(frozen=True, slots=True)
class Attack:
    """A boss move: the line of code it shouts, and how Ada says to survive it."""

    error: str
    tip: str


ATTACKS: dict[str, Attack] = {
    "flash": Attack(
        "LoadError: Flash Player is not installed",
        "В кольце есть проём. Смотрите, где он, и вставайте туда.",
    ),
    "followers": Attack(
        "201 Created: new followers",
        "Сначала подписчики! Пока они есть, урон до него не дойдёт.",
    ),
    "duplicate": Attack(
        "OSError: file already exists (copy)",
        "Настоящий один. Копии падают с одного удара, а в коде видно их .hp.",
    ),
    "overheat": Attack(
        "ThermalError: 95°C",
        "Сейчас рванёт! Уходите из круга. Мороз отодвигает следующий перегрев.",
    ),
    "unclosed": Attack(
        'print("Привет, мир!',
        "Он забыл закрыть строку, и она ползёт за вами. Закройте её сами: добегите до кавычки в другом конце зала, и Скобка оглохнет.",
    ),
    "blink": Attack(
        "<blink>",
        "Самый ненавистный тег девяностых: круги горят по очереди. Перебегайте в тот, что сейчас погас.",
    ),
    "doomscroll": Attack(
        "scrollTop += Infinity",
        "Пол сам едет вниз, а внизу страницы жжётся. Бегите против ленты и ищите проёмы в постах.",
    ),
    "bait": Attack(
        "<title>ВЫ НЕ ПОВЕРИТЕ</title>",
        "Читайте заголовки. Настоящая аптечка та, что не кричит. Всё, что кричит, взорвётся.",
    ),
    "return_none": Attack(
        "return None",
        "Всё, что вы в неё бросите, вернётся в вас. Не стреляйте, пока круг не погаснет: потом она уязвима.",
    ),
    "del_floor": Attack(
        "del floor[i]",
        "Куски пола удаляются. Мигающая клетка скоро станет None, а стоять на None больно.",
    ),
    "zero_index": Attack(
        "safe = rows[?]",
        "Безопасен один ряд из названных, и считает он с нуля! rows[0] это самый левый, rows[-1] самый правый.",
    ),
    "bisect": Attack(
        "bisect(mages, you)",
        "Двоичный поиск: он жжёт половину, где вы стоите, и ищет дальше только в ней. Перебегите через середину, и он вас не найдёт.",
    ),
    "accept_all": Attack(
        "accept_all()",
        "Он бьёт по всему залу. «Принять» рядом и спасёт, но вылечит его и запишется вам в счёт. «Отклонить» честнее, но бежать далеко.",
    ),
    "autocomplete": Attack(
        "# автодополнение: вы пойдёте сюда",
        "Он дописывает ваше движение и ждёт в конце. Резко сверните или остановитесь.",
    ),
    "changes": Attack(
        "Review: changes requested",
        "Лучи по линии! А урон проходит, только если руна не та же, что в прошлый раз.",
    ),
    "pincer": Attack(
        "SyntaxError: '(' was never closed",
        "Скобки смыкаются вокруг вас! Проём сверху и снизу.",
    ),
    "hex": Attack(
        "SyntaxError: invalid syntax",
        "Кого заденет этот круг, тот на пару секунд разучится колдовать. Уходите из него.",
    ),
    "indent": Attack(
        "IndentationError: unexpected indent",
        "Ступени идут к вам, и каждая сдвинута. Шагните вбок.",
    ),
    "feed": Attack(
        "while True: load_more()",
        "Стена постов через весь зал! В ней один проём, встаньте напротив него.",
    ),
    "loop": Attack(
        "continue",
        "Цикл вернёт вас туда, где вы стояли. Как только дёрнет назад, бегите из круга!",
    ),
    "retain": Attack(
        "while user.online: hold(user)",
        "Он тянет вас к себе. Бегите прочь, потом он выдохнется и станет уязвим.",
    ),
    "null": Attack(
        "TypeError: 'NoneType' object is not iterable",
        "Кого накроет, у того enemies(), allies() и cursor() вернут None. "
        "Проверяйте результат перед циклом: if targets:",
    ),
    "assign": Attack(
        "mana = None",
        "Этот луч обнуляет ману. Шаг в сторону!",
    ),
    "echo": Attack(
        "None is None",
        "Двойники! На вид не отличить, но в enemies() настоящая только у одной: e.boss равно True.",
    ),
    "sweep": Attack(
        "for row in rows: burn(row)",
        "Он перебирает зал рядами, но два ряда подряд пропустил. Бегите туда!",
    ),
    "offby": Attack(
        "rows[len(rows)]",
        "Вторая серия лучей бьёт на одну позицию дальше. Не прячьтесь в просвете первой.",
    ),
    "swap": Attack(
        "a[i], a[j] = a[j], a[i]",
        "Сейчас он поменяет вас местами. Сразу после обмена уходите из круга.",
    ),
    "bounds": Attack(
        "IndexError: list index out of range",
        "Края зала вне диапазона. Бегите к центру!",
    ),
    "mirror": Attack(
        "# поправил ваш прицел, не благодарите",
        "Кого заденет, тому автокоррекция перевернёт прицел. Но enemies() он не тронул: "
        "наводитесь через код, direction(e.x, e.y) не врёт.",
    ),
    "patch": Attack(
        "# применяю безопасный патч",
        "Он врёт! Зелёное бьёт, красное пустое. Стойте в красном!",
    ),
    "oom": Attack(
        "Out of memory: Killed process",
        "Утечка выросла до предела и бьёт кольцом. Уходите в просвет между снарядами и добивайте.",
    ),
    "deploy": Attack(
        "git push --force origin main",
        "Деплой! Бейте его всем, что есть, иначе он выкатит это на всю комнату и подлечится.",
    ),
}


SPECIES: dict[str, Species] = {}


def _species(*entries: Species) -> None:
    for entry in entries:
        SPECIES[entry.key] = entry


_species(
    # ------------------------------------------------------------- Старый Веб
    Species(
        "popup", "Попап", "Выскакивает и лезет в лицо. Держите дистанцию и стреляйте.",
        hp=34, speed=118, radius=17, contact=9, color="#e8e8f4", cost=1, ai="melee",
    ),
    Species(
        "cookie", "Куки", "Мелкие, быстрые и лезут всюду стаей. Вы их не принимали.",
        hp=13, speed=196, radius=12, contact=4, color="#d9a86a", cost=1, ai="swarm", pack=3,
        weak=frozenset({"fire"}),
    ),
    Species(
        "banner", "Баннер", "Висит поодаль и стреляет рекламой. Подойдите ближе.",
        hp=26, speed=78, radius=16, contact=0, color="#ffd93d", cost=2, ai="shooter",
        shot_damage=8, shot_speed=300, interval=2.3, weak=frozenset({"frost"}),
    ),
    Species(
        "bracket", "Незакрытая Скобка", "Живой SyntaxError. Смыкается вокруг вас, а задетые ею разучиваются колдовать.",
        hp=620, speed=78, radius=46, contact=16, color="#7fc4ff", cost=0, ai="boss_syntax",
        shot_damage=8, shot_speed=250, boss=True, heavy=True,
    ),
    # ------------------------------------------------------ Бесконечная Лента
    Species(
        "like", "Лайк", "Прилипнет, и вы замедлитесь: лента затягивает. Огонь бьёт сильнее.",
        hp=46, speed=112, radius=18, contact=9, color="#ff6b9e", cost=1.5, ai="melee",
        slows=True, weak=frozenset({"fire"}),
    ),
    Species(
        "toxic", "Токсик", "Бьёт веером из трёх комментариев. Отойдите в сторону.",
        hp=40, speed=84, radius=17, contact=0, color="#b5f26a", cost=2.5, ai="shooter",
        shot_damage=7, shot_speed=340, interval=2.5, shots=3, spread=0.5, slows=True,
        weak=frozenset({"fire"}),
    ),
    Species(
        "moderator", "Модератор", "Спереди щит блокирует снаряды. Бейте novой, зоной или сбоку.",
        hp=72, speed=88, radius=21, contact=11, color="#79a2ee", cost=3, ai="melee",
        guard=True, weak=frozenset({"nova", "lightning"}),
    ),
    Species(
        "clickbait", "Кликбейт", "Замирает, а потом бросается по прямой. Уходите вбок.",
        hp=32, speed=120, radius=15, contact=13, color="#ff5a4f", cost=2, ai="charger",
        weak=frozenset({"frost"}),
    ),
    Species(
        "scroll", "Вечный Скролл", "Кружит, сыплет спиралью и возвращает вас на шаг назад. Замрёт, только когда выдохнется.",
        hp=1150, speed=0, radius=44, contact=16, color="#a78bff", cost=0, ai="boss_loop",
        shot_damage=10, shot_speed=260, slows=True, boss=True, heavy=True,
    ),
    # ---------------------------------------------------------------- Облако
    Species(
        "malware", "Заражённый файл", "После смерти оставляет ядовитое облако. Не добивайте вплотную.",
        hp=44, speed=104, radius=18, contact=9, color="#8fe06a", cost=2, ai="melee",
        on_death="cloud", weak=frozenset({"fire"}),
    ),
    Species(
        "sync", "Синхронизатор", "Кидает файлы в точку, где вы стояли. Не стойте на месте.",
        hp=46, speed=72, radius=18, contact=0, color="#6fd6ff", cost=2.5, ai="lobber",
        shot_damage=14, interval=2.7, range=520, weak=frozenset({"lightning"}),
    ),
    Species(
        "botnet", "Ботнет", "Штампует ботов. Убейте его первым.",
        hp=78, speed=60, radius=24, contact=0, color="#9fb0c8", cost=4, ai="summoner",
        interval=4.6, weak=frozenset({"lightning", "chain"}),
    ),
    Species(
        "bot", "Бот", "Сам по себе слаб, опасен числом.",
        hp=14, speed=170, radius=11, contact=4, color="#c0ccd8", cost=1, ai="swarm",
    ),
    Species(
        "ghost404", "Ошибка 404", "Исчезает и возникает рядом. Следите за вспышкой.",
        hp=38, speed=90, radius=16, contact=0, color="#e6e0f6", cost=3, ai="blinker",
        shot_damage=10, shot_speed=330, interval=3.2, weak=frozenset({"beam"}),
    ),
    Species(
        "nullqueen", "Королева None", "Превращает ваши данные в None и прячется среди собственных копий.",
        hp=1300, speed=78, radius=42, contact=16, color="#c7a6e8", cost=0, ai="boss_null",
        shot_damage=10, shot_speed=310, boss=True, heavy=True,
    ),
    Species(
        "nullecho", "Королева None", "Двойник: выглядит как она, но .boss у него False.",
        hp=60, speed=60, radius=42, contact=0, color="#c7a6e8", cost=0, ai="decoy",
        shot_damage=6, shot_speed=280, interval=3.0, shots=3, spread=0.5, on_death="cloud",
        heavy=True,
    ),
    # ------------------------------------------------------------- Дата-Центр
    Species(
        "cooler", "Кулер", "Сорвался с креплений и катится по прямой. Уйдите с пути.",
        hp=58, speed=130, radius=19, contact=15, color="#8fd6e8", cost=2.5, ai="charger",
        weak=frozenset({"fire"}),
    ),
    Species(
        "rack", "Перегретая стойка", "Не двигается, бьёт кольцом искр. Ищите просвет.",
        hp=86, speed=0, radius=24, contact=0, color="#ffae5c", cost=3, ai="turret",
        shot_damage=8, shot_speed=240, interval=3.0, shots=10, heavy=True,
        weak=frozenset({"frost"}),
    ),
    Species(
        "cron", "Крон", "Бьёт строго по расписанию. Увидели круг на полу — бегите.",
        hp=128, speed=78, radius=25, contact=14, color="#c0a06a", cost=4, ai="smasher",
        shot_damage=24, interval=3.0, heavy=True, weak=frozenset({"lightning"}),
    ),
    Species(
        "backup", "Бэкап", "Восстанавливает остальных. Цельтесь в него первым.",
        hp=52, speed=96, radius=17, contact=6, color="#7fe0b0", cost=3, ai="healer",
        interval=2.6, weak=frozenset({"beam", "chain"}),
    ),
    Species(
        "indexer", "Индексатор", "Живой IndexError. Перебирает зал рядами, бьёт мимо на единицу и меняет магов местами.",
        hp=1800, speed=62, radius=48, contact=18, color="#ffd27a", cost=0, ai="boss_index",
        shot_damage=11, shot_speed=280, boss=True, heavy=True,
    ),
    # ----------------------------------------------------------------- Ядро
    Species(
        "fork", "Форк", "Убитый, делится надвое. Копии слабее, но их больше.",
        hp=70, speed=118, radius=21, contact=11, color="#a78bff", cost=3, ai="melee",
        on_death="split", weak=frozenset({"beam"}),
    ),
    Species(
        "firewall", "Файрвол", "Огонь его не берёт, как и положено. Нужны другие руны.",
        hp=96, speed=110, radius=20, contact=13, color="#ff8a5c", cost=3, ai="melee",
        immune=frozenset({"fire", "meteor"}), weak=frozenset({"frost"}),
    ),
    Species(
        "miner", "Криптомайнер", "Его снаряды сжигают ману. Уклоняйтесь и убивайте быстро.",
        hp=58, speed=84, radius=18, contact=0, color="#ffc24a", cost=3, ai="shooter",
        shot_damage=7, shot_speed=320, interval=2.2, mana_burn=18, weak=frozenset({"emp", "chain"}),
    ),
    Species(
        "hallucination", "Галлюцинация", "Появляется ниоткуда и уверенно врёт веером снарядов.",
        hp=74, speed=92, radius=19, contact=0, color="#e08cff", cost=4, ai="blinker",
        shot_damage=9, shot_speed=340, interval=2.8, shots=3, spread=0.4,
        weak=frozenset({"lightning"}),
    ),
    Species(
        "pgt", "PGT", "Вызывает сам себя, переворачивает ваш прицел и уверенно врёт. Деплой надо сорвать уроном.",
        hp=1000, speed=100, radius=44, contact=17, color="#ff4f6a", cost=0, ai="boss_recursor",
        shot_damage=11, shot_speed=300, boss=True, on_death="recurse",
    ),
)


# Mini-bosses: one for the second stage of each chapter, with their small retinues.
_species(
    Species(
        "flashintro", "Flash-заставка", "Кольца с проёмом, это её кнопка «Пропустить». Смотрите, где дыра, и вставайте туда.",
        hp=340, speed=60, radius=36, contact=10, color="#ff9a2f", cost=0, ai="mini_flash",
        shot_damage=7, shot_speed=210, boss=True, heavy=True,
    ),
    Species(
        "influencer", "Инфлюенсер", "Пока у него есть подписчики, урон до него не доходит. На 66% и 33% набирает новых.",
        hp=420, speed=84, radius=32, contact=0, color="#ff6b9e", cost=0, ai="mini_influencer",
        shot_damage=8, shot_speed=300, interval=1.8, shots=3, spread=0.5, range=520, boss=True, heavy=True,
    ),
    Species(
        "follower", "Подписчик", "Делает всё, что скажет Инфлюенсер. Один удар, и подписка отменена.",
        hp=22, speed=128, radius=13, contact=5, color="#ffb3cf", cost=0, ai="swarm",
    ),
    Species(
        "duplicate", "Файл (копия) (2)", "Копии выглядят так же, но ломаются от одного удара. У настоящего в .hp число побольше.",
        hp=520, speed=74, radius=30, contact=0, color="#9fd4ff", cost=0, ai="mini_duplicate",
        shot_damage=9, shot_speed=320, interval=2.0, range=480, boss=True, heavy=True,
    ),
    Species(
        "dupe", "Файл (копия) (2)", "Пустая копия: один удар, и её нет.",
        hp=1, speed=74, radius=30, contact=0, color="#9fd4ff", cost=0, ai="decoy",
        shot_damage=3, shot_speed=320, interval=2.4,
    ),
    Species(
        "hotserver", "Перегретая стойка", "Огонь не берёт. Мороз бьёт вдвое сильнее и отодвигает перегрев: пока держите её в холоде, зал цел.",
        hp=720, speed=46, radius=38, contact=18, color="#ff7a3c", cost=0, ai="mini_hotserver",
        shot_damage=9, shot_speed=270, interval=2.2, shots=3, spread=0.7, boss=True, heavy=True,
        immune=frozenset({"fire"}), weak=frozenset({"frost"}),
    ),
    Species(
        "reviewer", "Код-ревьюер", "Не принимает то, что только что видел. Чередуйте руны: в .text написано, что он видел последним.",
        hp=880, speed=66, radius=32, contact=0, color="#ffe07a", cost=0, ai="mini_reviewer",
        shot_damage=10, shot_speed=320, interval=2.2, shots=3, spread=0.4, range=560, boss=True, heavy=True,
    ),
)

# Not enemies at all: a mage's own copy, and what the proving ground is furnished with.
_species(
    Species(
        "clone", "Клон", "Ваша копия. Стреляет сама и оттягивает атаки на себя.",
        hp=90, speed=120, radius=16, contact=0, color="#9fe8ff", cost=0, ai="shooter",
        shot_damage=9, shot_speed=480, interval=0.9, range=520,
    ),
    Species(
        "dummy", "Манекен", "Стоит и терпит.",
        hp=1000, speed=0, radius=24, contact=0, color="#c9b48a", cost=0, ai="still", heavy=True,
    ),
    Species(
        "dummy_walker", "Манекен на рельсах", "Ходит туда-сюда: на нём тренируют упреждение.",
        hp=1000, speed=0, radius=24, contact=0, color="#8ac9b4", cost=0, ai="patrol", heavy=True,
    ),
)


# Quest creatures: they belong to one problem on one stage, not to a chapter.
_species(
    Species(
        "worker", "Воркер nginx", "Сбежавший процесс. Не дерётся, только удирает: загоните в угол и попадите.",
        hp=22, speed=205, radius=13, contact=0, color="#7fe0a8", cost=0, ai="flee",
    ),
    Species(
        "leak", "Утечка памяти", "Растёт, пока жива, а большая бьёт кольцом OOM. Бейте сразу.",
        hp=300, speed=62, radius=30, contact=14, color="#5fd0ff", cost=0, ai="leak",
        shot_damage=9, shot_speed=260,
    ),
    Species(
        "ratebot", "Бот-запрос", "Не воюет: мчится к шлюзу и съедает токен. Сбейте на подходе.",
        hp=12, speed=150, radius=12, contact=0, color="#c86bff", cost=0, ai="runner",
    ),
    Species(
        "hotrack", "Горячая стойка", "Не враг, а пациент: frostbolt остужает её, огонь греет.",
        hp=1000, speed=0, radius=30, contact=0, color="#ffae5c", cost=0, ai="still", heavy=True,
    ),
    Species(
        "failtest", "Упавший тест", "Красный тест стреляет ошибками. Пока он жив, сборка не поедет.",
        hp=46, speed=0, radius=18, contact=0, color="#ff4f6a", cost=0, ai="turret",
        shot_damage=8, shot_speed=280, interval=2.1, shots=5, heavy=True,
    ),
    Species(
        "letter", "Письмо", "Прочитайте его. Спам сбивайте, а настоящее письмо пусть дойдёт.",
        hp=1, speed=52, radius=17, contact=0, color="#e8e4f4", cost=0, ai="runner",
    ),
    Species(
        "phish", "Фишинговый сундук", "Сундук, который хотел ваши данные. Бросается с разбега.",
        hp=120, speed=120, radius=22, contact=16, color="#d9a441", cost=4, ai="charger",
    ),
)

HURRY = 1.35
FLEE_NOTICE = 430.0
RUNNER_ARRIVES = 48.0
LEAK_GROW_EVERY = 3.5
LEAK_GROWTH = 1.07
LEAK_MAX_RADIUS = 58.0


def _angle_to(monster: Monster, target: Player) -> float:
    return math.atan2(target.y - monster.y, target.x - monster.x)


def _distance(monster: Monster, target: Player) -> float:
    return math.hypot(target.x - monster.x, target.y - monster.y)


def _speed(monster: Monster, world: "StoryArena") -> float:
    species = monster.species
    slowed = monster.slow_until > world.now
    hurried = HURRY if monster.hurry_until > world.now else 1.0
    return species.speed * (0.58 if slowed else 1.0) * hurried * world.monster_pace * monster.pace


def _step(monster: Monster, world: "StoryArena", angle: float, speed: float, dt: float) -> None:
    world.try_move(
        monster, math.cos(angle) * speed * dt, math.sin(angle) * speed * dt
    )


def _advance(world: "StoryArena", monster: Monster, target: Player, dt: float, wander: float = 0.0) -> None:
    """Walk toward a target, around whatever stands in the way."""

    _step(monster, world, world.route(monster, target) + wander, _speed(monster, world), dt)


def _bite(world: "StoryArena", monster: Monster, target: Player) -> None:
    """Contact damage, on its own short clock so a hug does not melt anyone."""

    species = monster.species
    if not species.contact or world.now < monster.next_contact:
        return
    if _distance(monster, target) > monster.radius + PLAYER_RADIUS + 6:
        return
    monster.next_contact = world.now + 0.9
    world.damage(
        target=target,
        amount=species.contact,
        source=monster,
        kind="bite",
        hit_x=target.x,
        hit_y=target.y,
    )
    if species.slows and target.invuln_until <= world.now:
        target.slow_until = max(target.slow_until, world.now + 1.6)


def _fan(world: "StoryArena", monster: Monster, angle: float) -> None:
    species = monster.species
    for index in range(species.shots):
        offset = 0.0
        if species.shots > 1:
            offset = (index - (species.shots - 1) / 2) * species.spread / (species.shots - 1)
        world.fire(monster, angle + offset)


def _ring(world: "StoryArena", monster: Monster, count: int, offset: float = 0.0) -> None:
    for index in range(count):
        world.fire(monster, offset + index / count * math.tau)


def melee(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    monster.heading = _angle_to(monster, target)
    _advance(world, monster, target, dt)
    _bite(world, monster, target)


def swarm(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    """Melee that wanders, so a pack spreads out instead of queuing in a line."""

    monster.wobble += dt * 5.0
    monster.heading = _angle_to(monster, target)
    _advance(world, monster, target, dt, math.sin(monster.wobble + monster.id) * 0.7)
    _bite(world, monster, target)


def shooter(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    distance = _distance(monster, target)
    monster.heading = _angle_to(monster, target)
    sees = world.sees(monster, target)
    if distance > species.range or not sees:
        _advance(world, monster, target, dt)
    elif distance < species.range * 0.55:
        _step(monster, world, monster.heading + math.pi, _speed(monster, world), dt)
    else:
        side = 1 if monster.id % 2 else -1
        _step(monster, world, monster.heading + side * math.pi / 2, _speed(monster, world) * 0.6, dt)

    if monster.state == "aim":
        if world.now >= monster.state_until:
            monster.state = "idle"
            monster.next_attack = world.now + species.interval
            _fan(world, monster, monster.heading)
    elif world.now >= monster.next_attack and sees and distance < species.range * 1.3:
        monster.state = "aim"
        monster.state_until = world.now + 0.45


def charger(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    now = world.now
    if monster.state == "windup":
        if now >= monster.state_until:
            monster.state = "dash"
            monster.state_until = now + 0.55
        return
    if monster.state == "dash":
        before = monster.x, monster.y
        _step(monster, world, monster.heading, 620.0, dt)
        _bite(world, monster, target)
        stuck = (monster.x, monster.y) == before
        if now >= monster.state_until or stuck:
            monster.state = "idle"
            monster.next_attack = now + 1.8
        return
    monster.heading = _angle_to(monster, target)
    _advance(world, monster, target, dt)
    _bite(world, monster, target)
    if now >= monster.next_attack and _distance(monster, target) < 380 and world.sees(monster, target):
        monster.state = "windup"
        monster.state_until = now + 0.7


def lobber(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    monster.heading = _angle_to(monster, target)
    distance = _distance(monster, target)
    if distance > species.range:
        _advance(world, monster, target, dt)
    elif distance < 240:
        _step(monster, world, monster.heading + math.pi, _speed(monster, world), dt)
    if world.now >= monster.next_attack:
        monster.next_attack = world.now + species.interval
        world.place_hazard(
            monster, target.x, target.y, radius=78, delay=1.05,
            damage=species.shot_damage, color=species.color,
        )


def summoner(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    monster.heading = _angle_to(monster, target)
    if _distance(monster, target) < 300:
        _step(monster, world, monster.heading + math.pi, _speed(monster, world), dt)
    if world.now >= monster.next_attack:
        monster.next_attack = world.now + species.interval
        if world.minion_count() < world.minion_limit():
            for _ in range(2):
                world.spawn_near(monster, "bot", 70)


def blinker(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    monster.heading = _angle_to(monster, target)
    if world.now >= monster.next_attack:
        monster.next_attack = world.now + species.interval
        world.blink_near(monster, target, 230)
        monster.heading = _angle_to(monster, target)
        _fan(world, monster, monster.heading)


def turret(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    monster.heading = _angle_to(monster, target)
    if world.now >= monster.next_attack:
        monster.next_attack = world.now + species.interval
        monster.spin += 0.31
        _ring(world, monster, species.shots, monster.spin)


def smasher(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    now = world.now
    if monster.state == "slam":
        if now >= monster.state_until:
            monster.state = "idle"
        return
    monster.heading = _angle_to(monster, target)
    _advance(world, monster, target, dt)
    _bite(world, monster, target)
    if now >= monster.next_attack and _distance(monster, target) < 170:
        monster.next_attack = now + species.interval
        monster.state = "slam"
        monster.state_until = now + 0.85
        world.place_hazard(
            monster, monster.x, monster.y, radius=140, delay=0.85,
            damage=species.shot_damage, color="#ff9a4d",
        )


def healer(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    species = monster.species
    monster.heading = _angle_to(monster, target)
    if len(world.monsters) == 1:
        # With nobody left to mend it stops hiding, or the room would never end.
        _advance(world, monster, target, dt)
        _bite(world, monster, target)
        return
    if _distance(monster, target) < 340:
        _step(monster, world, monster.heading + math.pi, _speed(monster, world), dt)
    if world.now >= monster.next_attack:
        monster.next_attack = world.now + species.interval
        patient = world.most_hurt_ally(monster, 420)
        if patient is not None:
            world.mend(monster, patient, 26.0)


def decoy(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    """A copy with nothing inside: it lasts as long as the original does."""

    species = monster.species
    alone = not any(other.species.boss for other in world.monsters.values())
    if alone or world.now >= monster.state_until:
        world.remove_monster(monster)
        return
    monster.heading = _angle_to(monster, target)
    _advance(world, monster, target, dt)
    if world.now >= monster.next_attack:
        monster.next_attack = world.now + species.interval
        _fan(world, monster, monster.heading)


# ------------------------------------------------------------------- bosses
BRACKET_COLOR = "#ffb45c"
HEX_COLOR = "#7fc4ff"
LOOP_COLOR = "#a78bff"
NULL_COLOR = "#c7a6e8"
INDEX_COLOR = "#ffd27a"
TRUTH_COLOR = "#ff4f6a"
LIE_COLOR = "#4fe08a"

BRACKET_RADIUS = 340.0
BRACKET_SPEED = 190.0
FEED_SPACING = 44.0
FEED_GAP = 170.0
FEED_SPEED = 235.0
LOOP_RADIUS = 105.0
LOOP_PULL = 2.2
LOOP_FUSE = 3.1
RETAIN_TIME = 2.8
RETAIN_PULL = (130.0, 150.0, 170.0)
DIZZY_TIME = 2.6
ECHO_TIME = 8.0
SWEEP_LANE = 104.0
SWEEP_FUSE = 1.5
SWEEP_STEP = 0.09
BOUNDS_BAND = 170.0
SWAP_DELAY = 1.1
LIE_RING = 215.0


def _set_phase(world: "StoryArena", monster: Monster) -> None:
    """Bosses harden in step with their two gates: 66% and 33% of their health."""

    share = monster.hp / monster.max_hp
    monster.phase = max(monster.phase, 2 if share < 0.33 else 1 if share < 0.66 else 0)


def _rest(world: "StoryArena", monster: Monster, seconds: float) -> None:
    monster.next_attack = world.now + seconds * world.difficulty.tempo


def _rest_special(world: "StoryArena", monster: Monster, seconds: float) -> None:
    monster.next_special = world.now + seconds * world.difficulty.tempo


def _later(world: "StoryArena", monster: Monster, delay: float, action: Callable[[], None]) -> None:
    """Run the second half of an attack, unless its author died in the meantime."""

    def run() -> None:
        if monster.id in world.monsters:
            action()

    world.after(delay, run)


def _hex(
    world: "StoryArena", monster: Monster, *, radius: float, damage: float, color: str, effect: str
) -> None:
    for mage in world.hunted():
        world.place_hazard(
            monster, mage.x, mage.y, radius=radius, delay=1.1, damage=damage, color=color,
            effect=effect,
        )


def _brackets(world: "StoryArena", monster: Monster, target: Player, turn: float) -> None:
    """A ( and a ) slide together over the mage, open above and below.

    The shots fly side by side, not at one point: standing still costs a hit from
    each bracket, not all of them at once.
    """

    x, y = target.x, target.y
    life = BRACKET_RADIUS * 2 / BRACKET_SPEED
    for side in (0.0, math.pi):
        aim = side + turn + math.pi
        for step in range(-4, 5):
            angle = side + turn + step * 0.16
            world.fire_from(
                monster,
                x + math.cos(angle) * BRACKET_RADIUS,
                y + math.sin(angle) * BRACKET_RADIUS,
                aim,
                speed=BRACKET_SPEED,
                life=life,
            )


def _stairs(world: "StoryArena", monster: Monster) -> None:
    """A staircase of burning lines, each one indented further than the last."""

    forward_x, forward_y = math.cos(monster.heading), math.sin(monster.heading)
    side_x, side_y = -forward_y, forward_x
    for step in range(5):
        reach = 110 + step * 110
        shift = (step - 2) * 70
        x = monster.x + forward_x * reach + side_x * shift
        y = monster.y + forward_y * reach + side_y * shift
        world.place_beam_hazard(
            monster,
            x - side_x * 170,
            y - side_y * 170,
            x + side_x * 170,
            y + side_y * 170,
            width=70,
            delay=0.9 + step * 0.22,
            damage=16,
            color=BRACKET_COLOR,
        )


def boss_syntax(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    now = world.now
    _set_phase(world, monster)
    monster.heading = _angle_to(monster, target)
    _advance(world, monster, target, dt)
    _bite(world, monster, target)
    if now < monster.next_attack:
        return
    _rest(world, monster, (2.3, 1.9, 1.5)[monster.phase])
    monster.strikes += 1
    pattern = monster.strikes % 8
    if pattern in (6, 7):
        if not world.next_boss_move(monster):
            monster.spin += 0.4
            _ring(world, monster, 10 + monster.phase * 4, monster.spin)
    elif pattern == 1:
        monster.spin += 0.4
        _ring(world, monster, 10 + monster.phase * 4, monster.spin)
    elif pattern == 2:
        world.place_hazard(
            monster, target.x, target.y, radius=110, delay=1.1, damage=18, color=BRACKET_COLOR
        )
        if monster.phase:
            world.place_hazard(
                monster, target.x + 130, target.y, radius=90, delay=1.4, damage=16,
                color=BRACKET_COLOR,
            )
    elif pattern == 3:
        world.announce(monster, "pincer")
        _brackets(world, monster, target, 0.0)
        if monster.phase == 2:
            _later(world, monster, 0.9, lambda: _brackets(world, monster, target, math.pi / 2))
    elif pattern == 4 and world.minion_count() < 3 + monster.phase:
        for _ in range(2):
            world.spawn_near(monster, "popup", 120)
    elif pattern == 5:
        world.announce(monster, "hex")
        _hex(world, monster, radius=100, damage=10, color=HEX_COLOR, effect="syntax")
    elif pattern == 0:
        world.announce(monster, "indent")
        _stairs(world, monster)


def _feed(world: "StoryArena", monster: Monster) -> None:
    """A wall of posts from one side of the room to the other, with one way through."""

    left, top, right, bottom = world.room_box()
    rng = world.rng
    forward = rng.random() < 0.5
    along_x = rng.random() < 0.5
    low, high = (top, bottom) if along_x else (left, right)
    start, finish = (left, right) if along_x else (top, bottom)
    if not forward:
        start, finish = finish, start
    angle = math.atan2(0.0, finish - start) if along_x else math.atan2(finish - start, 0.0)
    gap = rng.uniform(low + FEED_GAP, high - FEED_GAP)
    life = abs(finish - start) / FEED_SPEED
    spot = low
    while spot <= high:
        if abs(spot - gap) > FEED_GAP / 2:
            x, y = (start, spot) if along_x else (spot, start)
            world.fire_from(monster, x, y, angle, speed=FEED_SPEED, life=life)
        spot += FEED_SPACING


def _loop_back(world: "StoryArena", monster: Monster) -> None:
    """Remember where everyone stands, drag them back there, then blow that spot up."""

    for mage in world.hunted():
        x, y = mage.x, mage.y
        world.place_hazard(
            monster, x, y, radius=LOOP_RADIUS, delay=LOOP_FUSE, damage=24, color=LOOP_COLOR
        )
        _later(
            world, monster, LOOP_PULL,
            lambda mage=mage, x=x, y=y: world.recall(mage, x, y),
        )


def _retain(world: "StoryArena", monster: Monster, dt: float) -> None:
    pull = RETAIN_PULL[monster.phase] * dt
    for mage in world.hunted():
        distance = _distance(monster, mage)
        if distance > monster.radius + 30:
            world.try_move(
                mage,
                (monster.x - mage.x) / distance * pull,
                (monster.y - mage.y) / distance * pull,
            )
    if world.now >= monster.state_until:
        monster.state = "idle"
        monster.dizzy_until = world.now + DIZZY_TIME
        world.announce_dizzy(monster)


def boss_loop(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    now = world.now
    _set_phase(world, monster)
    center_x, center_y = monster.origin
    if now < monster.dizzy_until:
        monster.heading += dt * 6.0
        return
    if monster.state == "retain":
        _retain(world, monster, dt)
    else:
        monster.orbit += dt * (0.7, 0.85, 1.0)[monster.phase]
        goal_x = center_x + math.cos(monster.orbit) * 300
        goal_y = center_y + math.sin(monster.orbit) * 210
        monster.heading = math.atan2(goal_y - monster.y, goal_x - monster.x)
        monster.x, monster.y = goal_x, goal_y
    _bite(world, monster, target)
    if now >= monster.next_attack:
        _rest(world, monster, 0.2)
        monster.spin += 0.42
        arms = monster.phase + 1
        for arm in range(arms):
            world.fire(monster, monster.spin + arm / arms * math.tau)
    if now < monster.next_special or monster.state == "retain":
        return
    _rest_special(world, monster, (6.5, 5.5, 4.5)[monster.phase])
    monster.specials += 1
    pattern = monster.specials % 5
    if pattern in (3, 4):
        world.next_boss_move(monster)
    elif pattern == 1:
        world.announce(monster, "feed")
        _feed(world, monster)
        if monster.phase == 2:
            _later(world, monster, 1.6, lambda: _feed(world, monster))
    elif pattern == 2:
        world.announce(monster, "loop")
        _loop_back(world, monster)
    else:
        world.announce(monster, "retain")
        monster.state = "retain"
        monster.state_until = now + RETAIN_TIME


def _echoes(world: "StoryArena", monster: Monster) -> None:
    for _ in range(2 + monster.phase):
        echo = world.spawn_near(monster, "nullecho", 240)
        if echo is not None:
            echo.leaked = True
            echo.state_until = world.now + ECHO_TIME


def _assign(world: "StoryArena", monster: Monster) -> None:
    """A line through every mage at once: whoever stays on it holds no mana."""

    for mage in world.hunted():
        angle = _angle_to(monster, mage)
        end_x, end_y = world.ray_end(
            monster.x, monster.y, math.cos(angle), math.sin(angle), 1300.0
        )
        world.place_beam_hazard(
            monster, monster.x, monster.y, end_x, end_y, width=64, delay=1.0, damage=16,
            color=NULL_COLOR, effect="drain",
        )


def boss_null(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    now = world.now
    _set_phase(world, monster)
    monster.heading = _angle_to(monster, target)
    if monster.state == "fade":
        if now >= monster.state_until:
            monster.state = "idle"
            world.blink_near(monster, target, 300)
            monster.heading = _angle_to(monster, target)
            count = 5 + monster.phase * 2
            for index in range(count):
                world.fire(monster, monster.heading + (index - (count - 1) / 2) * 0.24)
        return
    _step(monster, world, monster.heading, _speed(monster, world), dt)
    _bite(world, monster, target)
    if now >= monster.next_attack:
        _rest(world, monster, (3.0, 2.5, 2.0)[monster.phase])
        world.drop_cloud(monster, monster.x, monster.y, 120)
        if monster.phase == 2:
            for side in (-170, 170):
                world.drop_cloud(monster, target.x + side, target.y, 90)
        monster.state = "fade"
        monster.state_until = now + 0.7
        # A gate may already be holding her: its shield must outlast the fade.
        monster.invuln_until = max(monster.invuln_until, now + 0.7)
    if now < monster.next_special:
        return
    _rest_special(world, monster, (6.5, 5.5, 4.5)[monster.phase])
    monster.specials += 1
    pattern = monster.specials % 5
    if pattern in (3, 4):
        world.next_boss_move(monster)
    elif pattern == 1:
        world.announce(monster, "null")
        _hex(world, monster, radius=125, damage=10, color=NULL_COLOR, effect="null")
    elif pattern == 2:
        world.announce(monster, "assign")
        _assign(world, monster)
    elif world.minion_count() < world.minion_limit():
        world.announce(monster, "echo")
        _echoes(world, monster)


def _beams(world: "StoryArena", monster: Monster, count: int, turn: float, delay: float) -> None:
    for index in range(count):
        angle = turn + index / count * math.tau
        end_x, end_y = world.ray_end(
            monster.x, monster.y, math.cos(angle), math.sin(angle), 1200.0
        )
        world.place_beam_hazard(
            monster, monster.x, monster.y, end_x, end_y, width=46, delay=delay, damage=24,
            color=INDEX_COLOR,
        )


def _sweep(world: "StoryArena", monster: Monster, target: Player) -> None:
    """Every row of the room in turn, bar two neighbours: run for the gap."""

    left, top, right, bottom = world.room_box()
    rng = world.rng
    across = rng.random() < 0.5
    low, high = (left, right) if across else (top, bottom)
    other_low, other_high = (top, bottom) if across else (left, right)
    lanes = int((high - low) // SWEEP_LANE)
    here = int(((target.x if across else target.y) - low) // SWEEP_LANE)
    up_fits = here - 3 >= 0
    down_fits = here + 3 < lanes
    safe = here - 3 if up_fits and (not down_fits or rng.random() < 0.5) else here + 2
    safe = max(0, min(lanes - 2, safe))
    order = list(range(lanes))
    if rng.random() < 0.5:
        order.reverse()
    for turn, lane in enumerate(order):
        if lane in (safe, safe + 1):
            continue
        spot = low + (lane + 0.5) * SWEEP_LANE
        ends = (spot, other_low, spot, other_high) if across else (other_low, spot, other_high, spot)
        world.place_beam_hazard(
            monster, *ends, width=SWEEP_LANE, delay=SWEEP_FUSE + turn * SWEEP_STEP, damage=26,
            color=INDEX_COLOR,
        )


def _swap(world: "StoryArena", monster: Monster) -> None:
    """Trade the two mages furthest apart; a lone mage trades with the boss itself."""

    mages = world.hunted()
    if not mages:
        return
    first: Player = mages[0]
    second: Player = monster
    if len(mages) > 1:
        first, second = max(
            ((a, b) for a in mages for b in mages if a.id < b.id),
            key=lambda pair: math.hypot(pair[0].x - pair[1].x, pair[0].y - pair[1].y),
        )
    world.announce(monster, "swap")
    world.emit(
        {
            "e": "swap_warn",
            "x1": round(first.x, 1),
            "y1": round(first.y, 1),
            "x2": round(second.x, 1),
            "y2": round(second.y, 1),
        }
    )

    def trade() -> None:
        if not world.swap_places(first, second):
            return
        for body in (first, second):
            if not isinstance(body, Monster):
                world.place_hazard(
                    monster, body.x, body.y, radius=120, delay=0.85, damage=24,
                    color=INDEX_COLOR,
                )

    _later(world, monster, SWAP_DELAY, trade)


def _bounds(world: "StoryArena", monster: Monster) -> None:
    """Everything near a wall is out of range: the only safe floor is by the boss."""

    left, top, right, bottom = world.room_box()
    inset = BOUNDS_BAND / 2
    for ends in (
        (left, top + inset, right, top + inset),
        (left, bottom - inset, right, bottom - inset),
        (left + inset, top, left + inset, bottom),
        (right - inset, top, right - inset, bottom),
    ):
        world.place_beam_hazard(
            monster, *ends, width=BOUNDS_BAND, delay=1.4, damage=24, color=INDEX_COLOR
        )


def boss_index(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    now = world.now
    _set_phase(world, monster)
    monster.heading = _angle_to(monster, target)
    _step(monster, world, monster.heading, _speed(monster, world), dt)
    _bite(world, monster, target)
    if now >= monster.next_attack:
        _rest(world, monster, (2.8, 2.4, 2.0)[monster.phase])
        monster.spin += 0.38
        monster.strikes += 1
        beams = 4 + monster.phase * 2
        _beams(world, monster, beams, monster.spin, 1.05)
        if monster.phase and monster.strikes % 2 == 0:
            world.announce(monster, "offby")
            _beams(world, monster, beams, monster.spin + math.pi / beams, 1.75)
    if now < monster.next_special:
        return
    _rest_special(world, monster, (7.0, 6.0, 5.0)[monster.phase])
    monster.specials += 1
    pattern = monster.specials % 6
    if pattern in (4, 5):
        world.next_boss_move(monster)
    elif pattern == 1:
        world.announce(monster, "sweep")
        _sweep(world, monster, target)
    elif pattern == 2:
        _swap(world, monster)
    elif pattern == 3:
        world.announce(monster, "bounds")
        _bounds(world, monster)
    elif monster.phase and world.minion_count() < world.minion_limit():
        world.spawn_near(monster, "rack", 240)
    else:
        _ring(world, monster, 16, monster.spin)


def _false_patch(world: "StoryArena", monster: Monster) -> None:
    """Danger marked as safe and safety marked as danger, as is his way."""

    for mage in world.hunted():
        world.place_hazard(
            monster, mage.x, mage.y, radius=120, delay=1.4, damage=0.0, color=TRUTH_COLOR,
            label="ОПАСНО",
        )
        turn = world.rng.random() * math.tau
        for index in range(5):
            angle = turn + index / 5 * math.tau
            world.place_hazard(
                monster,
                mage.x + math.cos(angle) * LIE_RING,
                mage.y + math.sin(angle) * LIE_RING,
                radius=95,
                delay=1.4,
                damage=26,
                color=LIE_COLOR,
                label="безопасно",
            )


def boss_recursor(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    now = world.now
    monster.heading = _angle_to(monster, target)
    if monster.state == "deploy":
        world.deploy_step(monster)
        return
    if monster.state == "windup":
        if now >= monster.state_until:
            monster.state = "dash"
            monster.state_until = now + 0.6
        return
    if monster.state == "dash":
        _step(monster, world, monster.heading, 520.0, dt)
        _bite(world, monster, target)
        if now >= monster.state_until:
            monster.state = "idle"
        return
    _step(monster, world, monster.heading, _speed(monster, world), dt)
    _bite(world, monster, target)
    if now >= world.deploy_at and world.gate_boss is None:
        world.start_deploy(monster)
        return
    if now < monster.next_attack:
        return
    _rest(world, monster, 2.2 + monster.generation * 0.4)
    monster.strikes += 1
    pattern = monster.strikes % (7 if monster.generation == 0 else 5 if monster.generation < 2 else 3)
    if pattern == 5:
        world.announce(monster, "autocomplete")
        autocomplete(world, monster)
    elif pattern == 6:
        if world.gate_boss is None:
            world.next_boss_move(monster)
    elif pattern == 0:
        monster.state = "windup"
        monster.state_until = now + 0.8
    elif pattern == 1:
        monster.spin += 0.5
        _ring(world, monster, 14 - monster.generation * 3, monster.spin)
    elif pattern == 2:
        world.place_hazard(
            monster, target.x, target.y, radius=110, delay=1.0, damage=20, color="#f0a0ff"
        )
    elif pattern == 3:
        world.announce(monster, "mirror")
        _hex(world, monster, radius=110, damage=12, color=TRUTH_COLOR, effect="mirror")
    elif not any(hazard.label for hazard in world.hazards):
        world.announce(monster, "patch")
        _false_patch(world, monster)


def flee(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    """Never fights: shuffles about until a mage comes near, then runs along the halls."""

    if _distance(monster, target) > FLEE_NOTICE:
        monster.wobble += dt
        if math.sin(monster.wobble * 1.3 + monster.id) > 0.6:
            monster.heading += dt * 2.0
            _step(monster, world, monster.heading, _speed(monster, world) * 0.25, dt)
        return
    monster.heading = world.escape_route(monster, target)
    _step(monster, world, monster.heading, _speed(monster, world), dt)


def runner(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    """Pays no attention to anyone: it is going somewhere, and arriving is the attack."""

    goal = world.quest.runner_goal() if world.quest is not None else None
    if goal is None:
        return
    distance = math.hypot(goal[0] - monster.x, goal[1] - monster.y)
    if distance <= RUNNER_ARRIVES:
        world.quest.runner_arrived(monster)
        return
    monster.heading = math.atan2(goal[1] - monster.y, goal[0] - monster.x)
    _step(monster, world, monster.heading, _speed(monster, world), dt)


def still(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    """A thing, not a creature: it stands there and is shot at."""


def leak(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    """Crawls after the nearest mage and grows; at full size it frees memory the hard way."""

    melee(world, monster, target, dt)
    if world.now < monster.next_special or monster.generation:
        return
    monster.next_special = world.now + LEAK_GROW_EVERY
    if monster.radius < LEAK_MAX_RADIUS:
        monster.radius *= LEAK_GROWTH
        monster.max_hp *= LEAK_GROWTH
        monster.hp = min(monster.max_hp, monster.hp * LEAK_GROWTH)
        return
    world.announce(monster, "oom")
    _ring(world, monster, 12, monster.spin)
    monster.spin += 0.26


# --------------------------------------------------------------- mini-bosses
# Each teaches one thing the fights around it never asked for.
FLASH_RING = 22
FLASH_GAP = 4
INFLUENCER_FOLLOWERS = 4
INFLUENCER_GUARD = 0.25
DUPE_COUNT = 3
DUPE_EVERY = 7.0
DUPE_TIME = 7.0
HEAT_FUSE = 1.5
HEAT_RADIUS = 300.0
HEAT_DAMAGE = 34.0
HEAT_COOLED = 5.0
REVIEW_WIDTH = 60.0
REVIEW_LENGTH = 720.0


def mini_flash(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    """A ring of shots with a gap in it: the gap is the «Пропустить» nobody ever pressed."""

    species = monster.species
    _set_phase(world, monster)
    monster.heading = _angle_to(monster, target)
    _advance(world, monster, target, dt)
    _bite(world, monster, target)
    if world.now >= monster.next_attack:
        world.announce(monster, "flash")
        gap = monster.heading + world.rng.uniform(-1.0, 1.0)
        for index in range(FLASH_RING):
            angle = gap + (index + FLASH_GAP / 2) / (FLASH_RING + FLASH_GAP) * math.tau
            world.fire(monster, angle)
        _rest(world, monster, 3.2 - monster.phase * 0.5)
    if world.now >= monster.next_special and world.minion_count() < world.minion_limit():
        world.spawn_near(monster, "popup", 110)
        _rest_special(world, monster, 7.0)


def _followers(world: "StoryArena", monster: Monster) -> list[Monster]:
    return [other for other in world.monsters.values() if other.species.key == "follower"]


def mini_influencer(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    """Untouchable while anybody follows: at 66% and 33% it simply gets new followers."""

    species = monster.species
    before = monster.phase
    _set_phase(world, monster)
    if monster.strikes == 0 or monster.phase != before:
        monster.strikes = 1
        world.announce(monster, "followers")
        for _ in range(INFLUENCER_FOLLOWERS + monster.phase):
            world.spawn_near(monster, "follower", 150)
    if _followers(world, monster):
        monster.invuln_until = world.now + INFLUENCER_GUARD
    monster.heading = _angle_to(monster, target)
    if _distance(monster, target) > species.range * 0.7:
        _advance(world, monster, target, dt)
    else:
        _step(monster, world, monster.heading + math.pi / 2, _speed(monster, world) * 0.6, dt)
    if world.now >= monster.next_attack and world.sees(monster, target):
        _fan(world, monster, monster.heading)
        _rest(world, monster, species.interval)


def mini_duplicate(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    """Copies look the same, die at a touch and hurt little; only one of them has any hp."""

    species = monster.species
    _set_phase(world, monster)
    monster.heading = _angle_to(monster, target)
    if _distance(monster, target) > species.range * 0.7:
        _advance(world, monster, target, dt)
    if world.now >= monster.next_attack and world.sees(monster, target):
        _fan(world, monster, monster.heading)
        _rest(world, monster, species.interval)
    if world.now >= monster.next_special:
        world.announce(monster, "duplicate")
        world.blink_near(monster, target, 320.0)
        for _ in range(DUPE_COUNT + monster.phase):
            copy = world.spawn_near(monster, "dupe", 220)
            if copy is not None:
                copy.leaked = True
                copy.state_until = world.now + DUPE_TIME
        _rest_special(world, monster, DUPE_EVERY)


def mini_hotserver(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    """Vents the whole room on a fuse. Frost pushes the fuse back and stops it dead."""

    species = monster.species
    _set_phase(world, monster)
    monster.heading = _angle_to(monster, target)
    _advance(world, monster, target, dt)
    _bite(world, monster, target)
    if world.now >= monster.next_attack and world.sees(monster, target):
        _fan(world, monster, monster.heading)
        _rest(world, monster, species.interval)
    if world.now >= monster.next_special:
        world.announce(monster, "overheat")
        world.place_hazard(
            monster, monster.x, monster.y,
            radius=HEAT_RADIUS, delay=HEAT_FUSE, damage=HEAT_DAMAGE,
            color=species.color, label="ПЕРЕГРЕВ",
        )
        _rest_special(world, monster, 7.5 - monster.phase)


def cool_down(world: "StoryArena", monster: Monster) -> None:
    """What a frost hit does to the overheating rack, called from the damage path."""

    monster.next_special = max(monster.next_special, world.now + HEAT_COOLED)
    monster.stun_until = max(monster.stun_until, world.now + 0.5)


def mini_reviewer(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    """Rejects whatever it has just seen. ``.text`` says what that was, so code can branch."""

    species = monster.species
    _set_phase(world, monster)
    monster.heading = _angle_to(monster, target)
    if _distance(monster, target) > species.range * 0.7:
        _advance(world, monster, target, dt)
    if world.now >= monster.next_attack and world.sees(monster, target):
        _fan(world, monster, monster.heading)
        _rest(world, monster, species.interval)
    if world.now >= monster.next_special:
        world.announce(monster, "changes")
        for spread in (-0.5, 0.0, 0.5)[: 1 + 2 * min(1, monster.phase)]:
            angle = monster.heading + spread
            world.place_beam_hazard(
                monster, monster.x, monster.y,
                monster.x + math.cos(angle) * REVIEW_LENGTH,
                monster.y + math.sin(angle) * REVIEW_LENGTH,
                width=REVIEW_WIDTH, delay=1.0, damage=24.0, color=species.color,
            )
        _rest_special(world, monster, 5.0 - monster.phase * 0.6)


def patrol(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    """Up and down the hall, so that aiming with an offset has something to practise on."""

    monster.wobble += dt
    x, y = monster.origin
    monster.y = y + math.sin(monster.wobble * 0.8) * 160.0
    monster.x = x


THINKERS: dict[str, Callable[["StoryArena", Monster, Player, float], None]] = {
    "melee": melee,
    "swarm": swarm,
    "shooter": shooter,
    "charger": charger,
    "lobber": lobber,
    "summoner": summoner,
    "flee": flee,
    "runner": runner,
    "still": still,
    "leak": leak,
    "blinker": blinker,
    "turret": turret,
    "smasher": smasher,
    "healer": healer,
    "decoy": decoy,
    "boss_syntax": boss_syntax,
    "boss_loop": boss_loop,
    "boss_null": boss_null,
    "boss_index": boss_index,
    "boss_recursor": boss_recursor,
    "mini_flash": mini_flash,
    "mini_influencer": mini_influencer,
    "mini_duplicate": mini_duplicate,
    "mini_hotserver": mini_hotserver,
    "mini_reviewer": mini_reviewer,
    "patrol": patrol,
}


def think(world: "StoryArena", monster: Monster, target: Player, dt: float) -> None:
    if monster.elite == "deprecated":
        flee(world, monster, target, dt)
        return
    THINKERS[monster.species.ai](world, monster, target, dt)


def first_strike_delay(species: Species, rng: random.Random) -> float:
    """So a freshly spawned room does not fire one synchronised volley."""

    return rng.uniform(0.6, 1.6) if species.boss else rng.uniform(0.8, species.interval + 0.6)


# The second half of the bestiary adds itself to the tables above.
from . import foes  # noqa: E402,F401
