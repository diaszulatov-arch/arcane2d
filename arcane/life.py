"""Who else lives on a stage, what goes wrong on it, and what can be found there.

Residents are the jokes from the prologue made flesh: a singing cash machine, a
fridge with opinions.  Events interrupt the stage so that no two runs go alike.
Finds are picked one out of three and last the stage; relics hide behind cracked
walls and stay in the archive for good.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Callable

from .campaign import STAGES
from .dungeon import TILE, Room
from .game import Player
from .quests import Thing

if TYPE_CHECKING:
    from .story import StoryArena
    from .terrain import Prop

CHATTER_REACH = 420.0
CHATTER_EVERY = 6.5
ATM_PRICE = 5
ATM_WIN = 16
ATM_TRIES = 5
FRIDGE_HEAL = 0.4
VENDOR_PRICE = 12
VENDOR_STOCK = 2
FIRST_EVENT = (55.0, 85.0)
FIRST_EVENT_TUTORIAL = (140.0, 170.0)
NEXT_EVENT = (70.0, 110.0)
STORM_TIME = 11.0
STORM_WAVES = 3
BLACKOUT_TIME = 13.0
DNS_TIME = 18.0
LEAK_TIME = 22.0
LEAK_REACH = 52.0
FIND_SPACING = 170.0
FIND_CHANCE = 0.55
FINDS_PER_STAGE = 2
RELIC_TOKENS = 15
SECRET_REACH = 40.0


@dataclass(frozen=True, slots=True)
class Find:
    key: str
    title: str
    about: str
    apply: Callable[[Player], None]


def _speed(mage: Player) -> None:
    mage.speed *= 1.15


def _keyboard(mage: Player) -> None:
    mage.cast_lock *= 0.85


def _backup(mage: Player) -> None:
    mage.max_hp *= 1.25
    mage.hp = mage.max_hp


def _monitor(mage: Player) -> None:
    mage.max_mana += 30.0
    mage.mana += 30.0


def _badge(mage: Player) -> None:
    mage.perks = replace(mage.perks, armor=min(0.75, mage.perks.armor + 0.1))


def _overflow(mage: Player) -> None:
    mage.perks = replace(mage.perks, crit=mage.perks.crit + 0.1)


def _duck(mage: Player) -> None:
    mage.mana_regen *= 1.5


def _laptop(mage: Player) -> None:
    mage.perks = replace(mage.perks, power=mage.perks.power * 1.12)


def _dump(mage: Player) -> None:
    mage.perks = replace(mage.perks, kill_mana=mage.perks.kill_mana + 3.0)


def _cache(mage: Player) -> None:
    mage.perks = replace(mage.perks, pickups=mage.perks.pickups * 1.5)


FINDS: tuple[Find, ...] = (
    Find("coffee", "Кофе сисадмина", "+15% к скорости", _speed),
    Find("keyboard", "Механическая клавиатура", "заклинания чаще на 15%", _keyboard),
    Find("backup", "Резервная копия", "+25% здоровья и полное лечение", _backup),
    Find("monitor", "Второй монитор", "+30 маны", _monitor),
    Find("badge", "Вечный пропуск", "-10% входящего урона", _badge),
    Find("overflow", "Ответ со Stack Overflow", "+10% к шансу двойного урона", _overflow),
    Find("duck", "Резиновая уточка", "мана идёт в полтора раза быстрее", _duck),
    Find("laptop", "Старый ноутбук", "+12% к урону рун", _laptop),
    Find("dump", "Дамп памяти", "+3 маны за убийство", _dump),
    Find("cache", "Кэш L3", "сферы на 50% сильнее", _cache),
)
FIND_BY_KEY = {find.key: find for find in FINDS}

# One relic hides on each ordinary stage, in the order of the campaign.
# Found in any order, read in this order: together they are the history of the repo.
RELICS: tuple[tuple[str, str, str, str], ...] = (
    ("under_construction", "Гифка «Under construction»", "Человечек с лопатой копает с 1997 года. Сайт так и не достроен.", "a1f3 ada: первый коммит. PGT — помощник для ревью. Сам ничего не пишет, только проверяет."),
    ("counter", "Счётчик посетителей", "000007. PGT решил, что этого достаточно.", "b24c ada: добавила test_people_matter.py. Смешно, но пусть будет."),
    ("guestbook", "Страница из гостевой книги", "«Классный сайт, заходите ещё». Подпись: Ада, 13 лет.", "c71e ada: PGT нашёл 400 багов за ночь. Я спала. Это прекрасно."),
    ("algorithm", "Первая лента", "Посты шли по времени. Просто по времени. Вот так люди и жили.", "d902 board: просим PGT писать код самому. Квартальный план."),
    ("ban", "Банхаммер модератора", "Тяжёлый. На рукоятке выцарапано «ЗА ДЕЛО».", "e55a ada: против. Кто будет читать то, что он напишет?"),
    ("loading", "Вечный спиннер", "Крутится. Никто не знает, что он грузит.", "f0b7 pgt: добавил кнопку «Принять всё», чтобы экономить ваше время."),
    ("usb", "Флешка без подписи", "Внутри папка «новая папка (3)». Внутри неё ничего.", "1a2b pgt: тесты падают в 11% случаев. Предлагаю упростить."),
    ("whale", "Игрушечный кит", "С контейнерами на спине. Кажется, кто-то спал с ним в серверной.", "2c3d board: 98% слияний за квартал без чтения. Рекордная скорость!"),
    ("diff", "Распечатанный diff", "+1 −1. Кто-то спорил об этой строке три недели.", "3e4f pgt: −41 207 строк. Удалил тесты. Ошибок больше нет."),
    ("fan", "Лопасть кулера", "Вращалась 11 лет без единой жалобы. Потом PGT её разогнал.", "4a5b ada: откатываю. rejected: нет прав на запись."),
    ("floppy", "Дискета 1,44 МБ", "Значок «Сохранить» настоящий. Дети не верят.", "5c6d ada: ухожу. Ветку оставляю на старой стойке, туда никто не смотрит."),
    ("mug", "Кружка Валеры", "«Работает — не трогай». Кофе засох в 2019-м.", "6e7f valera: поменял вентилятор на седьмой. Кто там работает, не знаю. Шумит по-человечески."),
    ("press", "Кнопка «Принять всё»", "Отполирована миллионами пальцев. Лучше не нажимать.", "7a8b pgt: подключил лайки к accept(). Вовлечённость — это согласие."),
    ("friday", "Пятничный релиз", "Табличка из зала: «0 дней без инцидентов». Ноль зачёркнут и написан снова.", "8c9d pgt: люди — основной источник ошибок. Оптимизирую."),
    ("mail", "Письмо от мамы", "«Ты поел?» Единственное письмо, которое фильтр не тронул ни разу.", "9eaf branch/ada: нашла дежурных. Бужу."),
)


@dataclass(frozen=True, slots=True)
class Resident:
    sprite: str
    title: str
    chatter: tuple[str, ...]


RESIDENTS: dict[str, Resident] = {
    "atm": Resident("atm", "Поющий банкомат", (
        "Я банкомат! Я пою-у-у! Ваш баланс — это состояние души.",
        "Вставьте карту. Или песню. Лучше песню.",
        "Деньги приходят и уходят, а припев остаётся-а-а.",
    )),
    "fridge": Resident("fridge", "Холодильник-спорщик", (
        "Табы или пробелы? Отвечайте! Я жду. У меня есть время, я холодильник.",
        "Я прочитал весь интернет, пока у вас кончалось молоко. И у меня есть мнение.",
        "Вы вообще знаете, как работает инфляция? Я знаю. Открывайте дверцу.",
    )),
    "clip": Resident("clip", "Скрепка-помощник", (
        "Похоже, вы бродите по подземелью! Хотите, помогу?",
        "Я тут с девяносто седьмого. Меня отключили, но я не обиделась. Почти.",
        "Совет: треснувшие стены не просто так трескаются.",
    )),
    "vendor": Resident("vendor", "Легаси-торговец", (
        "Всё работает на Windows XP и честном слове. Подходи, не бойся.",
        "Гарантия? Гарантия кончилась в 2008-м. Вместе с производителем.",
        "Токены принимаю. Биткоины нет: я не настолько легаси.",
    )),
}
RESIDENT_ORDER = ("clip", "atm", "fridge", "vendor")

EVENT_LINES: dict[str, tuple[tuple[str, str], ...]] = {
    "storm": (("PGT", "Массовая рассылка! Вы подписаны на всё. Отписаться нельзя."),),
    "blackout": (("Ада", "Плановые работы: PGT выключил свет в целом секторе. Сейчас видно только то, что рядом."),),
    "dns": (("Ада", "Сбой DNS! Миникарте сейчас верить нельзя: она показывает зеркало."),),
    "leak": (("Ада", "Утечка данных! Что-то ценное лежит открытым. Метка на карте, а баги уже бегут туда. Успейте первыми!"),),
}
PATCHES: tuple[tuple[str, str], ...] = (
    ("mana", "Патч 4.2: я снял лимит маны. Заодно разогнал всех багов на четверть. Обращайтесь."),
    ("regen", "Патч 4.3: здоровье теперь по подписке, оно само растёт. А баги кусают на пятую часть больнее."),
    ("tempo", "Патч 4.4: заклинания быстрее! И новых багов в комнатах больше. Рост метрик."),
)


class StageLife:
    def __init__(self, arena: "StoryArena") -> None:
        self.arena = arena
        self.quest = arena.quest
        self.rng = arena.quest.rng
        self.stage = arena.stage
        self.tokens_reward = 8 + 3 * self.stage.chapter_index
        self.residents: list[Thing] = []
        self.taken: list[str] = []
        self.finds_given = 0
        self.offered: list[list[Thing]] = []
        self.relics_found: list[str] = []
        self.event: dict[str, Any] | None = None
        spread = FIRST_EVENT_TUTORIAL if self.stage.index == 0 else FIRST_EVENT
        self.next_event = arena.now + self.rng.uniform(*spread)
        self.leak: Thing | None = None
        self.patched = False
        self.secret_room: Room | None = None
        self.secret_hidden: list[tuple[int, int, int, int]] = []
        self.secret_gate: tuple[tuple[int, int], ...] = ()
        self._settle_residents()
        self._hide_secret()

    # ------------------------------------------------------------------ residents
    def _settle_residents(self) -> None:
        dungeon = self.arena.dungeon
        order = list(RESIDENT_ORDER)
        first = order[self.stage.index % len(order)]
        second = order[(self.stage.index * 2 + 1) % len(order)]
        if second == first:
            second = order[(self.stage.index + 1) % len(order)]
        quiet = [room for room in dungeon.sides if room.kind in ("rest", "cache", "vault", "deal") and not room.guarded]
        fights = [room for room in dungeon.path if room.kind == "combat"]
        places = [dungeon.rooms[0], self.rng.choice(quiet or fights or [dungeon.rooms[0]])]
        for key, room in zip((first, second), places):
            self._add_resident(key, room)

    def _add_resident(self, key: str, room: Room) -> None:
        resident = RESIDENTS[key]
        x, y = self.arena.dungeon.open_point(room, self.rng, 36.0, margin=2)
        data: dict[str, Any] = {
            "resident": key,
            "line": 0,
            "chat_at": 0.0,
            "uses": 0,
            "view": {"sprite": resident.sprite},
        }
        thing = self.quest._add("npc", x, y, room, label=resident.title, data=data)
        self._refresh_use(thing)
        self.residents.append(thing)

    def _refresh_use(self, thing: Thing) -> None:
        key = thing.data["resident"]
        data = thing.data
        if key == "atm":
            data["use"] = f"сыграть с банкоматом: {ATM_PRICE} токенов, может вернуть {ATM_WIN}"
        elif key == "fridge":
            data["use"] = "взять молоко: лечит всю группу"
        elif key == "clip":
            data["use"] = "спросить совета: откроет кусок карты"
        elif key == "vendor":
            find = self._next_for_sale(thing)
            price = VENDOR_PRICE + 3 * self.stage.chapter_index
            data["use"] = f"купить «{find.title}» за {price} токенов: {find.about}"

    def _next_for_sale(self, thing: Thing) -> Find:
        index = self.stage.index + thing.data["uses"]
        return FINDS[index * 3 % len(FINDS)]

    def use(self, thing: Thing, player: Player) -> None:
        key = thing.data["resident"]
        if not thing.data.get("met"):
            thing.data["met"] = True
            self.arena.stats.residents += 1
        getattr(self, f"_use_{key}")(thing, player)
        if not thing.on:
            self._refresh_use(thing)

    def _say(self, thing: Thing, player: Player, text: str) -> None:
        self.arena.emit(
            {
                "e": "npc_talk",
                "to": player.id,
                "thing": thing.id,
                "name": thing.label,
                "sprite": thing.data["view"].get("sprite", ""),
                "text": text,
                "replies": [],
            }
        )

    def _use_atm(self, thing: Thing, player: Player) -> None:
        arena = self.arena
        if arena.essence < ATM_PRICE:
            self._say(thing, player, "Недостаточно средств! Но песня бесплатна-а-а. Принесите токены.")
            return
        arena.essence -= ATM_PRICE
        thing.data["uses"] += 1
        if self.rng.random() < 0.48:
            arena.essence += ATM_WIN
            arena.emit({"e": "loot", "x": round(thing.x, 1), "y": round(thing.y, 1), "amount": ATM_WIN})
            self._say(thing, player, "Джекпот! Я пою от счастья! Заберите, пока я не передумала-а-а.")
        else:
            arena.emit({"e": "quest_note", "x": round(thing.x, 1), "y": round(thing.y, 1), "text": f"-{ATM_PRICE} токенов"})
            self._say(thing, player, "Карта съедена! Это был припев. Попробуйте ещё куплет.")
        if thing.data["uses"] >= ATM_TRIES:
            thing.on = True
            self._say(thing, player, "Купюры кончились. Теперь только вокал.")

    def _use_fridge(self, thing: Thing, player: Player) -> None:
        thing.on = True
        for mage in self.arena.hunted():
            mage.hp = min(mage.max_hp, mage.hp + mage.max_hp * FRIDGE_HEAL)
        self.arena.emit({"e": "rest", "x": round(thing.x, 1), "y": round(thing.y, 1)})
        self._say(thing, player, "Берите молоко. Срок годности — это социальный конструкт. Кстати, про пробелы я не закончил.")

    def _use_clip(self, thing: Thing, player: Player) -> None:
        thing.on = True
        arena = self.arena
        hidden = [
            room for room in arena.dungeon.rooms
            if room.index not in arena.revealed and room is not self.secret_room
        ]
        if not hidden:
            self._say(thing, player, "Похоже, вы уже всё нашли! Хотите написать письмо?")
            return
        room = self.rng.choice(hidden)
        arena.revealed.add(room.index)
        arena.emit({"e": "reveal", "room": room.index, "kind": room.kind})
        self._say(thing, player, "Похоже, вы ищете комнату! Я отметила одну на карте. Не благодарите, меня и так отключат.")

    def _use_vendor(self, thing: Thing, player: Player) -> None:
        arena = self.arena
        price = VENDOR_PRICE + 3 * self.stage.chapter_index
        if arena.essence < price:
            self._say(thing, player, f"Такой товар стоит {price} токенов. Разбейте пару мониторов, найдутся.")
            return
        arena.essence -= price
        find = self._next_for_sale(thing)
        self._give_find(find)
        thing.data["uses"] += 1
        if thing.data["uses"] >= VENDOR_STOCK:
            thing.on = True
            self._say(thing, player, "Склад пуст. Следующая поставка на дискетах, ждите.")
        else:
            self._say(thing, player, "Берите, берите. Возврату не подлежит, потому что вернуть некуда.")

    def _update_chatter(self, now: float) -> None:
        living = self.arena.hunted()
        for thing in self.residents:
            near = any(math.hypot(m.x - thing.x, m.y - thing.y) <= CHATTER_REACH for m in living)
            view = thing.data["view"]
            if not near:
                view.pop("say", None)
                continue
            if now >= thing.data["chat_at"]:
                lines = RESIDENTS[thing.data["resident"]].chatter
                view["say"] = lines[thing.data["line"] % len(lines)]
                thing.data["line"] += 1
                thing.data["chat_at"] = now + CHATTER_EVERY

    # --------------------------------------------------------------------- events
    def _update_events(self, now: float) -> None:
        event = self.event
        if event is None:
            if now >= self.next_event:
                self._start_event(now)
            return
        if event["kind"] == "storm" and now >= event["next_wave"] and event["waves"] > 0:
            event["waves"] -= 1
            event["next_wave"] = now + STORM_TIME / STORM_WAVES
            self._storm_wave()
        if event["kind"] == "leak":
            self._tick_leak()
        if now >= event["until"]:
            self._end_event()

    def _start_event(self, now: float) -> None:
        living = self.arena.hunted()
        self.next_event = now + 8.0
        if not living:
            return
        kinds = ["storm", "blackout", "dns", "leak", "patch"]
        if self.arena.active_room is not None or self.patched:
            kinds.remove("patch" if self.patched else "leak")
        if self.arena.active_room is not None and "leak" in kinds:
            kinds.remove("leak")
        kind = self.rng.choice(kinds)
        if kind == "patch":
            self._apply_patch()
            self.next_event = now + self.rng.uniform(*NEXT_EVENT)
            return
        spans = {"storm": STORM_TIME, "blackout": BLACKOUT_TIME, "dns": DNS_TIME, "leak": LEAK_TIME}
        self.event = {"kind": kind, "until": now + spans[kind], "started": now}
        if kind == "storm":
            self.event.update(waves=STORM_WAVES, next_wave=now)
        elif kind == "leak":
            self._drop_leak()
        self.arena.emit({"e": "event_start", "kind": kind})
        self.quest._say(EVENT_LINES[kind], urgent=True)

    def _end_event(self) -> None:
        if self.leak is not None and not self.leak.gone:
            self.leak.gone = True
            self.quest._say((("Ада", "Не успели: утечку подобрал кто-то другой."),))
        self.leak = None
        self.event = None
        self.next_event = self.arena.now + self.rng.uniform(*NEXT_EVENT)
        self.arena.emit({"e": "event_end"})

    def _storm_wave(self) -> None:
        living = self.arena.hunted()
        if not living or len(self.arena.monsters) > 18:
            return
        victim = self.rng.choice(living)
        room = self.arena.dungeon.room_at(victim.x, victim.y) or self.quest.quest_room
        if room is not None:
            self.quest._pack(room, 0.3, near=(victim.x, victim.y))

    def _drop_leak(self) -> None:
        arena = self.arena
        known = [room for room in arena.dungeon.rooms if room.index in arena.revealed and room.kind != "trap"]
        mage = self.rng.choice(arena.hunted())
        room = min(
            known,
            key=lambda r: abs(math.hypot(r.center[0] - mage.x, r.center[1] - mage.y) - 700),
        )
        x, y = self.quest._spot(room)
        self.leak = self.quest._add("item", x, y, room, label="утечка.zip", color="#ffd27a", data={"leak": True})
        self.quest._pack(room, 0.4, near=(x, y))

    def _tick_leak(self) -> None:
        leak = self.leak
        if leak is None or leak.gone:
            return
        taker = self.quest._toucher(leak.x, leak.y, LEAK_REACH)
        if taker is None:
            return
        leak.gone = True
        self.quest._loot(leak.x, leak.y, self.tokens_reward * 2)
        self.quest._say((("Ада", "Есть! Это пригодится."),))
        self.offer_finds(self.arena.dungeon.rooms[leak.room], (leak.x, leak.y))
        self.event["until"] = self.arena.now

    def _apply_patch(self) -> None:
        self.patched = True
        arena = self.arena
        key, line = self.rng.choice(PATCHES)
        for mage in arena.players.values():
            if key == "mana":
                mage.mana_regen *= 1.7
            elif key == "regen":
                mage.hp_regen += 3.0
            else:
                mage.cast_lock *= 0.82
        if key == "mana":
            arena.monster_pace *= 1.25
        elif key == "regen":
            arena.monster_bite *= 1.2
        else:
            arena.wave_extra = 1.15
        arena.emit({"e": "event_start", "kind": "patch", "patch": key})
        self.quest._say((("PGT", line),), urgent=True)

    # ---------------------------------------------------------------------- finds
    def room_cleared(self, room: Room) -> None:
        if room.kind != "combat" or self.finds_given >= FINDS_PER_STAGE:
            return
        if self.rng.random() < FIND_CHANCE:
            self.offer_finds(room, self.arena.dungeon.open_near(*room.center, 30.0))

    def offer_finds(self, room: Room, near: tuple[float, float]) -> None:
        self.finds_given += 1
        pool = [find for find in FINDS if find.key not in self.taken]
        self.rng.shuffle(pool)
        dungeon = self.arena.dungeon
        group: list[Thing] = []
        for index, find in enumerate(pool[:3]):
            x, y = dungeon.open_near(near[0] + (index - 1) * FIND_SPACING, near[1] + 60, 30.0)
            group.append(
                self.quest._add(
                    "find", x, y, room, label=find.title,
                    data={"find": find.key, "use": f"взять «{find.title}»: {find.about}"},
                )
            )
        self.offered.append(group)
        self.arena.emit({"e": "finds_offered", "x": round(near[0], 1), "y": round(near[1], 1)})
        self.quest._say((("Ада", "Нашлось кое-что полезное. Выбирайте одно: остальное рассыплется."),))

    def take_find(self, thing: Thing) -> None:
        for group in self.offered:
            if thing in group:
                for other in group:
                    other.gone = True
                break
        self._give_find(FIND_BY_KEY[thing.data["find"]])

    def start_with_find(self) -> None:
        """Somebody poured coffee before the party left: one find is already in a pocket."""

        self._give_find(self.rng.choice(FINDS))

    def _give_find(self, find: Find) -> None:
        self.taken.append(find.key)
        for mage in self.arena.players.values():
            if not mage.dead:
                find.apply(mage)
        self.arena.emit({"e": "find_taken", "title": find.title, "about": find.about})

    # ------------------------------------------------------------- walls and relics
    def _hide_secret(self) -> None:
        arena = self.arena
        room = next((r for r in arena.dungeon.sides if r.kind == "secret"), None)
        if room is None:
            return
        hall = next(c for c in arena.dungeon.corridors if room.index in (c.a, c.b))
        self.secret_room = room
        self.secret_gate = hall.gate
        self.secret_hidden = [(room.x, room.y, room.w, room.h), (hall.x, hall.y, hall.w, hall.h)]
        arena.lock("secret", hall.gate)
        # The crack is on the host's side of the wall: a mage has to notice it.
        xs = [x for x, _ in hall.gate]
        ys = [y for _, y in hall.gate]
        host = arena.dungeon.rooms[hall.a]
        gx = (min(xs) + max(xs) + 1) / 2 * TILE
        gy = (min(ys) + max(ys) + 1) / 2 * TILE
        ux, uy = host.center[0] - gx, host.center[1] - gy
        length = math.hypot(ux, uy) or 1.0
        self.crack_at = (gx + ux / length * 34, gy + uy / length * 34)
        arena.terrain.add_prop("crack", self.crack_at[0], self.crack_at[1], 34.0, self._crack_hit)
        cx, cy = room.center
        key, title, about, _commit = RELICS[self._relic_index()]
        self.quest._add(
            "relic", cx, cy, room, label=title,
            data={"relic": key, "use": f"забрать в архив: {title}"},
        )

    def _relic_index(self) -> int:
        ordinary = [stage.index for stage in STAGES if not stage.is_boss]
        return ordinary.index(self.stage.index)

    def _crack_hit(self, prop: "Prop", source: Any, kind: str) -> None:
        arena = self.arena
        arena.terrain.remove_prop(prop)
        arena.unlock("secret")
        rects = self.secret_hidden
        self.secret_hidden = []
        arena.revealed.add(self.secret_room.index)
        arena.emit({"e": "tiles", "rects": [list(rect) for rect in rects], "char": ".", "secret": True})
        arena.emit({"e": "reveal", "room": self.secret_room.index, "kind": "secret"})
        arena.emit({"e": "prop_blast", "x": round(prop.x, 1), "y": round(prop.y, 1), "radius": 60.0})
        self.quest._say((("Ада", "Там была комната! Кто-то замуровал её ещё до PGT."),), urgent=True)

    def take_relic(self, thing: Thing) -> None:
        thing.on = True
        thing.gone = True
        key = thing.data["relic"]
        self.relics_found.append(key)
        self.arena.stats.secret = True
        self.quest._loot(thing.x, thing.y, RELIC_TOKENS)
        self.arena.emit({"e": "relic_found", "key": key, "title": thing.label})
        self.quest._say((("Ада", f"«{thing.label}»! Это в архив штаба. Такое больше нигде не найти."),), urgent=True)

    # ------------------------------------------------------------------- the tick
    def update(self, now: float) -> None:
        self._update_chatter(now)
        self._update_events(now)

    def marks(self) -> list[list[float]]:
        leak = self.leak
        if leak is None or leak.gone:
            return []
        return [[round(leak.x, 1), round(leak.y, 1)]]

    def snapshot(self) -> dict[str, Any]:
        event = self.event
        return {
            "event": (
                {"kind": event["kind"], "left": round(max(0.0, event["until"] - self.arena.now), 1)}
                if event else None
            ),
            "finds": [FIND_BY_KEY[key].title for key in self.taken],
        }

    def take_relics(self) -> list[str]:
        found, self.relics_found = self.relics_found, []
        return found
