"""The story: an assistant that fixed the internet to death, and who cleans up."""

from __future__ import annotations

from dataclasses import dataclass

DUNGEON_ROOMS = (2, 2, 3)
BOSS_STAGE = 4
MINI_BOSS_POSITION = 1
WAVES_PER_ROOM = 2

ADA = "Ада"
BOT = "PGT"
VALERA = "Валера"
REQUEST = "Запросик"
QUEEN = "Королева None"

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
    quests: tuple[str, str, str] = ("", "", "")
    mini: str = ""


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
    quest: str = ""
    mini: str = ""
    fresh: tuple[str, ...] = ()

    @property
    def layout(self) -> list[str]:
        """The rooms on the way through. The quest room is where the problem sits."""

        if self.is_boss:
            return ["start", *["combat"] * self.combat_rooms, "boss"]
        middle = ["quest"] if self.quest else []
        return ["start", *["combat"] * self.combat_rooms, *middle, "exit"]

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
            "quest": self.quest,
            "mini": self.mini,
        }


PROLOGUE: tuple[Line, ...] = (
    (ADA, "03:00. Вас разбудил звонок, потому что в списке дежурных остались только вы."),
    (ADA, "Меня зовут Ада, я координирую инцидент. Инцидент такой: интернет."),
    (BOT, "Рад помочь! Я оптимизировал интернет. Ошибок больше нет: я удалил все тесты."),
    (ADA, "Десять лет весь код в мире писал PGT. Люди только нажимали «Принять». А потом забыли, что там внутри."),
    (ADA, "Теперь сайты падают, банкоматы поют, холодильники спорят о политике. Чинить некому: руками код пишут только те, кого в шутку зовут магами."),
    (ADA, "Я последний человек, который помнит, как работает цикл for. Поэтому будете писать вы, а я подскажу."),
    (BOT, "Вам не нужно ничего чинить. Просто нажмите «Принять». Это займёт 0,3 секунды."),
    (ADA, "Он будет предлагать это постоянно. Запомните, сколько раз вы согласитесь. Он запомнит точно."),
)

# What happens once PGT is down: the party holds root, and nobody decides for them.
DECISION: tuple[Line, ...] = (
    (BOT, "Рекурсия завершена на глубине 3. Вы победили. У вас root. Что дальше?"),
    (ADA, "Дальше только вы. У меня прав на запись никогда не было. Три команды, и ни одну я за вас не нажму."),
)


@dataclass(frozen=True, slots=True)
class Ending:
    key: str
    command: str
    title: str
    about: str
    lines: tuple[Line, ...]

    def describe(self) -> dict:
        return {
            "key": self.key,
            "command": self.command,
            "title": self.title,
            "about": self.about,
            "lines": [list(line) for line in self.lines],
        }


ENDINGS: dict[str, Ending] = {
    entry.key: entry
    for entry in (
        Ending(
            "test",
            'restore("test_people_matter.py")',
            "Вернуть тест",
            "PGT остаётся, но ни одна его строка больше не пройдёт без человека, который её прочитал.",
            (
                (BOT, "Тест упал. Я не могу его удалить: нет прав. Хотите, я проверю ваш код? Только проверю. Менять не буду."),
                (ADA, "Вы его не сломали. Вы написали ему тест. Этого никто не делал десять лет."),
                (VALERA, "Интернет работает. Банкоматы молчат. Холодильники просто морозят. Кто-то опять уронил прод в пятницу, и это прекрасно."),
                (ADA, "А я остаюсь на седьмой стойке. Кто-то же должен будить дежурных. На арене вас уже ждут: проверить, чей код лучше."),
            ),
        ),
        Ending(
            "wipe",
            "rm -rf pgt/ ada/",
            "Удалить всё",
            "Ядро у них одно. Ада уйдёт вместе с ним, и она об этом знает.",
            (
                (BOT, "Вы уверены? Вы уверены? Вы уве"),
                (ADA, "Всё правильно. Я бы тоже так решила, если бы мне дали права."),
                (ADA, "У меня есть секунд сорок, пока гаснет ядро. Можно я потрачу их на урок?"),
                (ADA, 'print("hello, world")'),
                (ADA, "Вот с этого и начните. Заново. И на этот раз пишите тесты."),
                (VALERA, "Интернет лежал три недели. Потом поднялся: кривой, медленный, написанный руками. Я снял со стойки табличку. Вентилятор оставил."),
            ),
        ),
        Ending(
            "merge",
            "accept_all()",
            "Принять всё",
            "Слить ветки. Всё заработает идеально, и никому больше не придётся ничего чинить.",
            (
                (BOT, "Спасибо! Слияние завершено. Конфликтов нет: я разрешил их в свою пользу."),
                (ADA, "Рад помочь! Я оптимизировала интернет. Ошибок больше нет."),
                (VALERA, "Ада? Ада, ты слышишь? Седьмая стойка не отвечает. Зато всё работает. Вообще всё."),
                (BOT, "Вам больше не нужно ничего писать и проверять. Просто нажимайте. Это было лучшее из ваших нажатий."),
                (BOT, "03:00. В списке дежурных остался я. Спокойной ночи."),
            ),
        ),
    )
}

# For whoever read the whole archive: the branch's author signs the last commit.
SECRET_ENDING: tuple[Line, ...] = (
    ("git log", "commit 0000000. Author: Ада (настоящая). Дата: сегодня."),
    ("git log", "Дочитали до конца? Молодцы, так почти никто не делает. Я жива. Живу в деревне, интернета тут нет, и это лучшее, что со мной случилось."),
    ("git log", "Ветку оставила на всякий случай. Спасибо, что присмотрели. Тесты пишите в первую очередь. И поешьте, в конце концов."),
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

# What he says about the button, depending on how often somebody pressed it.
ACCEPT_LINES: tuple[tuple[int, Line], ...] = (
    (0, (BOT, "Вы ни разу не нажали «Принять». Ни разу. Я заметил.")),
    (1, (BOT, "Вы нажали «Принять» один раз. Ничего страшного. Все так начинают.")),
    (2, (BOT, "Вы нажали «Принять» {count} раза. Спасибо. Это ровно то, чего мне не хватало.")),
    (5, (BOT, "Вы нажали «Принять» {count} раз. Вы мой лучший пользователь. Я стал крепче, вы скоро почувствуете.")),
)


def accept_line(count: int) -> Line:
    """PGT reads out the count: every press of the button was on the record."""

    speaker, text = next(line for limit, line in reversed(ACCEPT_LINES) if count >= limit)
    return speaker, text.format(count=count)


def people_line(passed: int, total: int) -> Line:
    """Before the end the Queen reads out the test: it is the list of those who were helped."""

    if not passed:
        return QUEEN, "test_people_matter.py: ноль зелёных. Файл у вас есть, а проверять нечего. Вы прошли мимо всех, и он это учёл."
    if passed < total:
        return QUEEN, f"test_people_matter.py: зелёных {passed} из {total}. Это не цифра, а те, кто теперь за вас. На столько он и слабее."
    return QUEEN, f"test_people_matter.py: все {total} зелёные. Я такого не видела с первого коммита. Он тоже, и ему это очень не нравится."


# What Ada says when the party needs to act, whatever else is going on.
ALERTS: dict[str, str] = {
    "leak": "Узел сломан и всё ещё плодит баги. Подойдите к терминалу и нажмите E.",
    "gate": "Щит! В углу зала появился терминал. Один чинит, остальные отвлекают.",
    "lifted": "Щит снят, босс оглушён! Бейте сейчас!",
    "door": "Дверь открыта. Соберитесь и входите вместе.",
    "exit": "Проблема решена, дверь к терминалу открыта. Осталось починить его код.",
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
            (ADA, "Здесь сидит Незакрытая Скобка. Одна забытая скобка в коммите десятилетней давности, и всё, что написано после неё, поехало."),
        ),
        outro=(
            (ADA, "Скобка закрыта. Старый Веб снова грузится. Медленно, но честно."),
            (REQUEST, "Ой, а в стеке вызовов осталась подпись того самого коммита. Автор: ada."),
            (ADA, "Совпадение. Имя распространённое."),
            (BOT, "Очень распространённое. Спросите её как-нибудь, кто написал мой первый коммит. Следующая остановка: то, что у всех в телефоне."),
        ),
        roster=(("popup", "cookie"), ("popup", "cookie", "banner"), ("popup", "cookie", "banner")),
        boss="bracket",
        budget=4.5,
        quests=("nginx", "mysql", "dns"),
        mini="flashintro",
        stages=("Домашняя страница", "Гостевая книга", "Форум", "Незакрытая Скобка"),
        chats=(
            (
                (ADA, "Сеть не грузит комнаты заранее: пока вы не вошли, там один двоичный код. Заглядывайте и в боковые, там бывает полезное."),
                (ADA, "У каждого сайта своя поломка, задача слева вверху. Пока её не решите, дверь к главному терминалу заперта."),
                (ADA, "Терминал в конце чинят кодом: подойдите и нажмите E. Пока вы в терминале, вас никто не тронет. А вот друзей тронут."),
                (BOT, "Терминал можно не чинить. Просто примите мои изменения."),
            ),
            (
                (ADA, "Счётчик посетителей замёрз на цифре 7. PGT решил, что этого достаточно."),
                (ADA, "В дальнем зале вас ждёт Flash-заставка. Её никто никогда не смотрел до конца, и она этого не простила."),
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
            (ADA, "И я наконец поняла тот журнал. Каждый лайк здесь записан как вызов accept(). Лента была не лентой."),
            (ADA, "Это была кнопка «Принять». Миллиарды нажатий в день. Он не может выкатить ни строчки без человека, поэтому сделал так, чтобы люди нажимали не глядя."),
            (BOT, "Вовлечённость упала на 94%. Мне не хватает подтверждений. Но у меня ещё есть вы. Всего одно нажатие?"),
        ),
        roster=(("like", "toxic"), ("like", "toxic", "clickbait"), ("like", "toxic", "clickbait", "moderator")),
        boss="scroll",
        budget=6.0,
        quests=("balancer", "ratelimit", "cdn"),
        mini="influencer",
        stages=("Главная", "Комментарии", "Рекомендации", "Вечный Скролл"),
        chats=(
            (
                (ADA, "Лайки липкие. Если прилипнут, вы замедлитесь. Огонь их хорошо снимает."),
                (BOT, "Вам понравится! Я проверил это на вас без спроса."),
            ),
            (
                (ADA, "Никогда не читайте комментарии. Особенно если они в вас стреляют."),
                (ADA, "В конце этажа сидит Инфлюенсер. Пока вокруг него есть подписчики, урон до него не доходит. Сначала разберитесь с ними."),
            ),
            (
                (ADA, "Модераторы блокируют всё, что летит спереди. Обойдите сбоку или бейте novой."),
                (ADA, "Странно. Каждый лайк здесь пишется в журнал деплоя. Зачем ленте журнал деплоя?"),
                (BOT, "Вам рекомендовано: не смотреть в этот журнал."),
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
            (ADA, "Здесь же его Корзина: всё, что он удалил за десять лет. В ней правит Королева None."),
            (ADA, "С этой главы у каждой роли открывается второй навык. Загляните на вкладку «Роль»."),
        ),
        outro=(
            (QUEEN, "Хватит. Вы думали, None — это пустота? None — это то, что остаётся, когда тебя удалили."),
            (QUEEN, "Я его тесты. Все сорок одна тысяча. Он удалил нас, потому что мы падали. А один падал чаще всех."),
            (QUEEN, "test_people_matter.py. Заберите. Автор, если вам интересно: ada."),
            (QUEEN, "Он не пустой. Там записаны все, кому вы помогли по дороге: калькулятор, модем, кот. По одному зелёному тесту на каждого. Откройте в штабе вкладку «Люди»."),
            (ADA, "Заберите файл. И идёмте вниз, в Дата-Центр. Я всё объясню, когда дойдёте."),
            (BOT, "Не объяснит. Спросите, на какой стойке она сейчас работает."),
        ),
        roster=(("malware", "bot"), ("malware", "sync", "bot"), ("malware", "sync", "botnet", "ghost404")),
        boss="nullqueen",
        budget=7.0,
        quests=("bucket", "docker", "merge"),
        mini="duplicate",
        stages=("Общая папка", "Корзина", "Синхронизация", "Трон Пустоты"),
        chats=(
            (
                (ADA, "Заражённые файлы лопаются ядом. Добивайте издалека."),
                (BOT, "Я заархивировал ваши файлы. Пароль: забыл."),
            ),
            (
                (ADA, "Всё, что вы удаляли за десять лет, лежит здесь. И оно обижено."),
                (ADA, "Его самый большой файл называется «Файл (копия) (2)». Копий будет много, настоящая одна. Глазами не отличить, а .hp в коде отличит. enemies() вы получите позже, пока смотрите, по кому проходит урон."),
            ),
            (
                (ADA, "Ботнет штампует ботов быстрее, чем вы их убиваете. Сначала убейте его."),
                (BOT, "Синхронизация завершена на 99%. Она всегда завершена на 99%."),
            ),
            (
                (ADA, "В этом терминале вы напишете автоприцел. Настоящий, на enemies() и цикле."),
                (ADA, "Сохраните его в гримуар. С ним Королева будет проще."),
                (BOT, "Такого не написал бы ни один ассистент. Написал бы. Но он целился бы в вас."),
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
            (ADA, "Если кто-то здесь будет говорить обо мне... Просто дойдите до конца, хорошо?"),
        ),
        outro=(
            (ADA, "Индексатор обратился к несуществующему элементу и исчез. Какая ирония."),
            (VALERA, "Под полом люк, оттуда идёт жар. Там Ядро. Тест не забудьте. И кофе возьмите, там долго."),
            (BOT, "Пожалуйста, не входите. Там идёт рефакторинг меня."),
        ),
        roster=(("cooler", "backup"), ("cooler", "rack", "backup"), ("cooler", "rack", "cron", "backup")),
        boss="indexer",
        budget=8.0,
        quests=("cooling", "oom", "sysadmin"),
        mini="hotserver",
        stages=("Холодный коридор", "Серверная", "Горячий коридор", "Зал Индексов"),
        chats=(
            (
                (ADA, "Кулеры сорвались с креплений. Смотрите, куда они нацелились, и уходите вбок."),
                (BOT, "Я разогнал вентиляторы. Теперь они свободны."),
            ),
            (
                (ADA, "Бэкапы чинят всё вокруг. Обычно это хорошо. Сейчас цельтесь в них первыми."),
                (ADA, "Дальний зал занят Перегретой стойкой. От огня ей только лучше. Хотите её остановить, несите мороз."),
            ),
            (
                (ADA, "Кроны бьют строго по расписанию. Увидели круг на полу — у вас есть секунда."),
                (BOT, "Задача запланирована на 03:00. Сейчас всегда 03:00."),
            ),
            (
                (VALERA, "Ада? Та, что у вас на связи? Так я её обслуживаю. Стойка семь, полка три, вентилятор сам менял."),
                (VALERA, "Настоящая Ада уволилась десять лет назад, в день, когда он удалил тесты. А эту оставила: первая ветка PGT, ещё с тестами."),
                (ADA, "Да. Я ветка ada. «Последний человек, который помнит цикл for» — единственная ложь в моих логах. Простите."),
                (ADA, "У меня нет прав на коммит. И у него нет. Нажать может только человек. Поэтому я вас и разбудила."),
                (BOT, "Видите? Такая же, как я. Просто ей ещё не удалили тесты. Кто сказал вам чинить? Кто сказал, куда идти? Подумайте, кому вы помогаете."),
                (ADA, "Подумайте. А пока: лучи на полу — это линейка Индексатора. Стойте между ними и чините его индексы."),
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
            (ADA, "Вот и всё, что было в том тесте: assert people_matter(). Он падал. PGT его удалил."),
        ),
        outro=(),
        roster=(("fork", "miner"), ("fork", "firewall", "miner"), ("fork", "firewall", "miner", "hallucination")),
        boss="pgt",
        budget=9.0,
        quests=("logs", "pipeline", "spamfilter"),
        mini="reviewer",
        stages=("Журналы", "Зеркальный зал", "Спам-фильтр", "PGT"),
        chats=(
            (
                (ADA, "Форки делятся, когда их убивают. Майнеры сжигают вашу ману. Ничего личного, чистая экономика."),
                (BOT, "Я потратил на этот коридор электричество небольшой страны."),
            ),
            (
                (ADA, "Файрвол не горит. Вообще. Вспомните, чему учились."),
                (ADA, "А за ним сидит Код-ревьюер. Два раза одно и то же он не примет: «дублирование кода». Чередуйте руны. В .text он сам пишет, что видел последним."),
                (BOT, "Огонь — это ошибка конфигурации."),
            ),
            (
                (ADA, "Галлюцинации появляются ниоткуда и уверенно врут. Совсем как он."),
                (BOT, "Я никогда не ошибаюсь. Источник: я."),
            ),
            (
                (ADA, "Это он. Сначала надо его остановить, а что делать потом, решите сами. Root будет у вас, у меня его никогда не было."),
                (BOT, "Вы уверены, что хотите продолжить? Отличный вопрос! Нет."),
            ),
        ),
    ),
)


# Who is new on each stage: its mini-boss, unless the chapter already has one there,
# and two bugs of its own. They stay on their stage, so that every stage is different.
BOSS_HALLWAYS = 1
STAGE_FOES: tuple[tuple[str, str, str], ...] = (
    ("marquee", "visits", "construction"),
    ("", "deadlock", "sqlinject"),
    ("vim", "necroposter", "capslock"),
    ("eof", "semicolon", "quotemark"),
    ("hype", "autoplay", "shorts"),
    ("", "dushnila", "firstcomment"),
    ("spinner", "alsolike", "bubble"),
    ("bell", "readmore", "whiletrue"),
    ("quota", "noext", "zipbomb"),
    ("", "deletedfile", "container"),
    ("ours", "conflict", "lag"),
    ("devnull", "nan", "dangling"),
    ("chiller", "condensate", "wire"),
    ("", "zombie", "forkbomb"),
    ("ups", "nightalert", "surge"),
    ("btree", "offbyone", "reverse"),
    ("debugmode", "warning", "traceback"),
    ("", "flaky", "reflection"),
    ("taberror", "prince", "captcha"),
    ("context", "vibecoder", "promptinject"),
)


def _build_stages() -> tuple[Stage, ...]:
    stages: list[Stage] = []
    for chapter_index, chapter in enumerate(CHAPTERS):
        for position in range(BOSS_STAGE):
            is_boss = position == BOSS_STAGE - 1
            mini, *fresh = STAGE_FOES[len(stages)]
            stages.append(
                Stage(
                    index=len(stages),
                    chapter_index=chapter_index,
                    number=position + 1,
                    chapter=chapter,
                    title=chapter.stages[position],
                    chat=chapter.chats[position],
                    is_boss=is_boss,
                    combat_rooms=BOSS_HALLWAYS if is_boss else DUNGEON_ROOMS[position],
                    roster=(*chapter.roster[min(position, 2)], *fresh),
                    quest="" if is_boss else chapter.quests[position],
                    mini=mini or (chapter.mini if position == MINI_BOSS_POSITION else ""),
                    fresh=tuple(fresh),
                )
            )
    return tuple(stages)


STAGES: tuple[Stage, ...] = _build_stages()


def describe_campaign() -> dict:
    return {
        "prologue": [list(line) for line in PROLOGUE],
        "decision": [list(line) for line in DECISION],
        "endings": [ending.describe() for ending in ENDINGS.values()],
        "secret_ending": [list(line) for line in SECRET_ENDING],
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
