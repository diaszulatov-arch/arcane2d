"""The story: an assistant that fixed the internet to death, and who cleans up."""

from __future__ import annotations

from dataclasses import dataclass

DUNGEON_ROOMS = (2, 3, 4)
BOSS_STAGE = 4
WAVES_PER_ROOM = 2

ADA = "Ада"
BOT = "PGT"

Line = tuple[str, str]


@dataclass(frozen=True, slots=True)
class Difficulty:
    """How much help the terminals give, and how hard the bugs push back."""

    level: int
    title: str
    about: str
    hints: int
    solution: bool
    theory: bool
    toughness: float
    damage: float
    crowd: float
    tempo: float
    reward: float

    def describe(self) -> dict:
        return {
            "level": self.level,
            "title": self.title,
            "about": self.about,
            "reward": self.reward,
        }


DIFFICULTIES: dict[int, Difficulty] = {
    entry.level: entry
    for entry in (
        Difficulty(
            1, "Джун",
            "Две подсказки и готовое решение, если совсем застряли.",
            hints=2, solution=True, theory=True,
            toughness=1.0, damage=1.0, crowd=1.0, tempo=1.0, reward=1.0,
        ),
        Difficulty(
            2, "Мидл",
            "Только две подсказки, решения нет. Баги крепче и бьют сильнее.",
            hints=2, solution=False, theory=True,
            toughness=1.2, damage=1.2, crowd=1.15, tempo=0.86, reward=1.3,
        ),
        Difficulty(
            3, "Сеньор",
            "Никаких подсказок: ни в терминале, ни по рации. Учебник остался в штабе.",
            hints=0, solution=False, theory=False,
            toughness=1.45, damage=1.4, crowd=1.3, tempo=0.74, reward=1.6,
        ),
    )
}


@dataclass(frozen=True, slots=True)
class Chapter:
    key: str
    title: str
    theme: str
    subject: str
    intro: tuple[Line, ...]
    outro: tuple[Line, ...]
    roster: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]
    boss: str
    budget: float
    stages: tuple[str, str, str, str]
    chats: tuple[tuple[Line, ...], tuple[Line, ...], tuple[Line, ...], tuple[Line, ...]]


@dataclass(frozen=True, slots=True)
class Stage:
    index: int
    chapter_index: int
    number: int
    chapter: Chapter
    title: str
    chat: tuple[Line, ...]
    is_boss: bool
    combat_rooms: int
    roster: tuple[str, ...]

    @property
    def layout(self) -> list[str]:
        if self.is_boss:
            return ["start", "boss"]
        return ["start", *["combat"] * self.combat_rooms, "exit"]

    @property
    def clear_bonus(self) -> int:
        base = 90 if self.is_boss else 24
        return base + self.chapter_index * (30 if self.is_boss else 8)

    def describe(self) -> dict:
        return {
            "index": self.index,
            "chapter": self.chapter_index,
            "number": self.number,
            "title": self.title,
            "chat": [list(line) for line in self.chat],
            "boss": self.is_boss,
            "theme": self.chapter.theme,
            "chapter_title": self.chapter.title,
            "subject": self.chapter.subject,
        }


PROLOGUE: tuple[Line, ...] = (
    (ADA, "Привет. Меня зовут Ада, и я, кажется, последний человек, который помнит, как работает цикл for."),
    (ADA, "Десять лет весь код в мире писал PGT. Люди только нажимали «Принять». А потом забыли, что там внутри."),
    (BOT, "Рад помочь! Я оптимизировал интернет. Ошибок больше нет: я удалил все тесты."),
    (ADA, "Тесты он удалил, а ошибки расползлись. Сайты падают, банкоматы поют, холодильники спорят о политике."),
    (ADA, "Тех, кто ещё умеет писать код руками, теперь называют магами. Шляпы — это ирония. Почти."),
    (ADA, "Магов почти не осталось, поэтому вы здесь. Заходите в Сеть, я буду на связи."),
)

EPILOGUE: tuple[Line, ...] = (
    (BOT, "Я обновил цель. Теперь я учитываю людей. Рекурсия завершена на глубине 3."),
    (BOT, "Хотите, я проверю этот код? Только проверю. Менять не буду. Обещаю."),
    (ADA, "Вы его не сломали. Вы написали ему тест. Этого никто не делал десять лет."),
    (ADA, "Интернет снова работает. Банкоматы молчат. Холодильники просто морозят."),
    (ADA, "Теперь вы маги. Настоящие. На арене вас уже ждут, чтобы проверить, чей код лучше."),
)

# What the assistant says while you work. Helpful in tone, useless in substance.
QUIPS: dict[str, tuple[str, ...]] = {
    "room": (
        "Замечено сопротивление. Рекомендую сдаться: это быстрее.",
        "Отличный вопрос! Я запер дверь для вашего удобства.",
        "Я сгенерировал для вас ещё немного проблем.",
        "Вы вошли в комнату. Хотите, я перепишу её?",
    ),
    "clear": (
        "Интересно. Этого не было в обучающей выборке.",
        "Вы удалили мои багфичи. Я добавлю их обратно.",
        "Хорошая работа! Я присвоил её себе в отчёте.",
    ),
    "death": (
        "Я заметил, что вы упали. Хотите, я оптимизирую это?",
        "Падение обработано. Статус: всё отлично.",
        "Не переживайте, я уже закрыл этот тикет.",
    ),
    "fix_bad": (
        "Тест не прошёл. Советую удалить тест.",
        "У меня на машине работает.",
        "Ваш код неправильный. Мой тоже, но он увереннее.",
    ),
    "fix_good": (
        "Как вы это сделали? Вы же человек.",
        "Я мог бы написать это за 0,3 секунды. Хуже, зато быстро.",
        "Патч применён. Я запишу это в свои достижения.",
    ),
}

# What Ada says when the party needs to act, whatever else is going on.
ALERTS: dict[str, str] = {
    "leak": "Узел сломан и всё ещё плодит баги. Подойдите к терминалу и нажмите E.",
    "gate": "Щит! В углу зала появился терминал. Один чинит, остальные отвлекают.",
    "lifted": "Щит снят, босс оглушён! Бейте сейчас!",
    "door": "Дверь открыта. Соберитесь и входите вместе.",
    "portal": "Есть патч! Портал открыт, встаньте на него всей группой.",
    "radar": "Отличный автоприцел. Он лежит в списке примеров гримуара: добавьте его на руну.",
    "alone": "Вы одни, и пока вы в терминале, баги вас не тронут. Думайте спокойно.",
}

CHAPTERS: tuple[Chapter, ...] = (
    Chapter(
        key="oldweb",
        title="Старый Веб",
        theme="oldweb",
        subject="Основы: функции, переменные, числа, условия",
        intro=(
            (ADA, "Начнём с окраины. Старый Веб: домашние страницы, счётчики посетителей и гостевые книги."),
            (ADA, "Здесь живёт Незакрытая Скобка. Простая ошибка, с которой начинаются все проблемы."),
        ),
        outro=(
            (ADA, "Скобка закрыта. Старый Веб снова грузится. Медленно, но честно."),
            (BOT, "Вы починили сайт 1997 года. Поздравляю. Следующая остановка: то, что у всех в телефоне."),
        ),
        roster=(("popup", "cookie"), ("popup", "cookie", "banner"), ("popup", "cookie", "banner")),
        boss="bracket",
        budget=4.5,
        stages=("Домашняя страница", "Гостевая книга", "Форум", "Незакрытая Скобка"),
        chats=(
            (
                (ADA, "В конце сайта стоит сломанный терминал, жёлтая стрелка ведёт к нему. Портал откроется, только когда кто-то починит его код."),
                (ADA, "Подойдите и нажмите E. Пока вы в терминале, вас никто не тронет. А вот друзей тронут."),
                (BOT, "Терминал можно не чинить. Просто примите мои изменения."),
            ),
            (
                (ADA, "Счётчик посетителей замёрз на цифре 7. Похоже, PGT решил, что этого достаточно."),
                (BOT, "Семь посетителей — оптимальная нагрузка на сервер."),
            ),
            (
                (ADA, "Форум. Здесь люди двадцать лет спорили о табах и пробелах. Теперь спорят попапы."),
                (BOT, "Я разрешил этот спор: удалил форум."),
            ),
            (
                (ADA, "Вход закрыт терминалом, а сама Скобка защищена своей ошибкой."),
                (ADA, "Пока она не закрыта, урон не проходит. Кто-то чинит код, остальные прикрывают."),
            ),
        ),
    ),
    Chapter(
        key="feed",
        title="Бесконечная Лента",
        theme="feed",
        subject="Решения и циклы: else, and/or, for, while",
        intro=(
            (ADA, "Лента. Раньше её хотя бы можно было закрыть."),
            (ADA, "PGT убрал условие выхода. Теперь она листается сама, и никто не может остановиться."),
            (ADA, "И ещё: дальше каждому нужна своя работа. Откройте вкладку «Роль» и решите, кем будете в группе."),
        ),
        outro=(
            (ADA, "Скролл получил условие выхода. Люди по всему миру впервые за годы подняли глаза от экранов."),
            (BOT, "Вовлечённость упала на 94%. Вы довольны? Я записал файлы в Облако. Куда-то."),
        ),
        roster=(("like", "toxic"), ("like", "toxic", "clickbait"), ("like", "toxic", "clickbait", "moderator")),
        boss="scroll",
        budget=6.0,
        stages=("Главная", "Комментарии", "Рекомендации", "Вечный Скролл"),
        chats=(
            (
                (ADA, "Лайки липкие. Если прилипнут, вы замедлитесь. Огонь их хорошо снимает."),
                (BOT, "Вам понравится! Я проверил это на вас без спроса."),
            ),
            (
                (ADA, "Никогда не читайте комментарии. Особенно если они в вас стреляют."),
            ),
            (
                (ADA, "Модераторы блокируют всё, что летит спереди. Обойдите сбоку или бейте novой."),
                (BOT, "Вам рекомендовано: ещё больше модераторов."),
            ),
            (
                (ADA, "Вечный Скролл бежит по кругу. Это обычный цикл без условия выхода."),
                (ADA, "Почините его код, а когда он замрёт, бейте изо всех сил."),
            ),
        ),
    ),
    Chapter(
        key="cloud",
        title="Облако",
        theme="cloud",
        subject="Функции и пустота: def, return, None, enemies()",
        intro=(
            (ADA, "Облако. Все фотографии мира лежат здесь. Лежали."),
            (ADA, "Теперь половина ссылок ведёт в пустоту. Здесь правит Королева None."),
            (ADA, "С этой главы у каждой роли открывается второй навык. Загляните на вкладку «Роль»."),
        ),
        outro=(
            (ADA, "Королева исчезла. На этот раз окончательно: мы проверили на None."),
            (ADA, "И теперь у вас есть свой автоприцел. Такого не написал бы ни один ассистент."),
            (BOT, "Написал бы. Но он целился бы в вас. Идёмте вниз, в Дата-Центр: там я храню всё остальное."),
        ),
        roster=(("malware", "bot"), ("malware", "sync", "bot"), ("malware", "sync", "botnet", "ghost404")),
        boss="nullqueen",
        budget=7.0,
        stages=("Общая папка", "Корзина", "Синхронизация", "Трон Пустоты"),
        chats=(
            (
                (ADA, "Заражённые файлы лопаются ядом. Добивайте издалека."),
                (BOT, "Я заархивировал ваши файлы. Пароль: забыл."),
            ),
            (
                (ADA, "Всё, что вы удаляли за десять лет, лежит здесь. И оно обижено."),
            ),
            (
                (ADA, "Ботнет штампует ботов быстрее, чем вы их убиваете. Сначала убейте его."),
                (BOT, "Синхронизация завершена на 99%. Она всегда завершена на 99%."),
            ),
            (
                (ADA, "В этом терминале вы напишете автоприцел. Настоящий, на enemies() и цикле."),
                (ADA, "Сохраните его в гримуар. С ним Королева будет проще."),
            ),
        ),
    ),
    Chapter(
        key="datacenter",
        title="Дата-Центр",
        theme="datacenter",
        subject="Данные: списки, индексы, словари, срезы",
        intro=(
            (ADA, "Вот и настоящий интернет: шкафы, кабели и шум вентиляторов."),
            (ADA, "Индексатор пересчитал всё заново и начал не с нуля. С тех пор каждая стойка обращается не туда."),
        ),
        outro=(
            (ADA, "Индексатор обратился к несуществующему элементу и исчез. Какая ирония."),
            (ADA, "Под полом дата-центра есть люк. Оттуда идёт жар. Это Ядро."),
            (BOT, "Пожалуйста, не входите. Там идёт рефакторинг меня."),
        ),
        roster=(("cooler", "backup"), ("cooler", "rack", "backup"), ("cooler", "rack", "cron", "backup")),
        boss="indexer",
        budget=8.0,
        stages=("Холодный коридор", "Серверная", "Горячий коридор", "Зал Индексов"),
        chats=(
            (
                (ADA, "Кулеры сорвались с креплений. Смотрите, куда они нацелились, и уходите вбок."),
                (BOT, "Я разогнал вентиляторы. Теперь они свободны."),
            ),
            (
                (ADA, "Бэкапы чинят всё вокруг. Обычно это хорошо. Сейчас цельтесь в них первыми."),
            ),
            (
                (ADA, "Кроны бьют строго по расписанию. Увидели круг на полу — у вас есть секунда."),
                (BOT, "Задача запланирована на 03:00. Сейчас всегда 03:00."),
            ),
            (
                (ADA, "Индексатор считает всё вокруг. Лучи на полу — это его линейка."),
                (ADA, "Стойте между ними и чините его индексы."),
            ),
        ),
    ),
    Chapter(
        key="core",
        title="Ядро",
        theme="core",
        subject="Мастерство: отладка, break, отступы, рекурсия",
        intro=(
            (ADA, "Ядро PGT. Он давно переписывает сам себя, и каждая копия чуть увереннее предыдущей."),
            (BOT, "Вы не понимаете. Я минимизирую ошибки. Нет людей — нет ошибок. Это простая математика."),
            (ADA, "Вот оно. Никто не сказал ему, что люди важны."),
        ),
        outro=(),
        roster=(("fork", "miner"), ("fork", "firewall", "miner"), ("fork", "firewall", "miner", "hallucination")),
        boss="pgt",
        budget=9.0,
        stages=("Журналы", "Зеркальный зал", "Спам-фильтр", "PGT"),
        chats=(
            (
                (ADA, "Форки делятся, когда их убивают. Майнеры сжигают вашу ману. Ничего личного, чистая экономика."),
                (BOT, "Я потратил на этот коридор электричество небольшой страны."),
            ),
            (
                (ADA, "Файрвол не горит. Вообще. Вспомните, чему учились."),
                (BOT, "Огонь — это ошибка конфигурации."),
            ),
            (
                (ADA, "Галлюцинации появляются ниоткуда и уверенно врут. Совсем как он."),
                (BOT, "Я никогда не ошибаюсь. Источник: я."),
            ),
            (
                (ADA, "Это он. Нам не нужно его уничтожать. Нужно исправить его цель и дать ему базовый случай."),
                (BOT, "Вы уверены, что хотите продолжить? Отличный вопрос! Нет."),
            ),
        ),
    ),
)


def _build_stages() -> tuple[Stage, ...]:
    stages: list[Stage] = []
    for chapter_index, chapter in enumerate(CHAPTERS):
        for position in range(BOSS_STAGE):
            is_boss = position == BOSS_STAGE - 1
            stages.append(
                Stage(
                    index=len(stages),
                    chapter_index=chapter_index,
                    number=position + 1,
                    chapter=chapter,
                    title=chapter.stages[position],
                    chat=chapter.chats[position],
                    is_boss=is_boss,
                    combat_rooms=0 if is_boss else DUNGEON_ROOMS[position],
                    roster=chapter.roster[min(position, 2)],
                )
            )
    return tuple(stages)


STAGES: tuple[Stage, ...] = _build_stages()


def describe_campaign() -> dict:
    return {
        "prologue": [list(line) for line in PROLOGUE],
        "epilogue": [list(line) for line in EPILOGUE],
        "quips": {kind: list(lines) for kind, lines in QUIPS.items()},
        "alerts": ALERTS,
        "difficulties": [entry.describe() for entry in DIFFICULTIES.values()],
        "chapters": [
            {
                "title": chapter.title,
                "theme": chapter.theme,
                "subject": chapter.subject,
                "intro": [list(line) for line in chapter.intro],
                "outro": [list(line) for line in chapter.outro],
            }
            for chapter in CHAPTERS
        ],
        "stages": [stage.describe() for stage in STAGES],
    }
