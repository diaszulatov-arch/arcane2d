"""Roles: what each mage brings to the party, called from their own code.

A role never takes a rune away and never makes anyone the party's programmer.
It adds a passive and two skills, each a real programming idea turned into a
fight: a rollback, a breakpoint, a process you hijack.  Skills are plain
functions, so choosing when and on whom to use them is itself Python.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from .game import Player, SpellSession, _api_angle, _api_number
from .interpreter import SpellRuntimeError, UnitView

if TYPE_CHECKING:
    from .monsters import Monster
    from .story import StoryArena

ROLE_STAGE = 4
SECOND_SKILL_STAGE = 8
SKILL_RANGE = 900.0

HEAL_AMOUNT = 32.0


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    role: str
    title: str
    signature: str
    about: str
    cost: int
    cooldown: float
    stage: int

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "title": self.title,
            "signature": self.signature,
            "about": self.about,
            "cost": self.cost,
            "cooldown": self.cooldown,
            "stage": self.stage,
        }


@dataclass(frozen=True, slots=True)
class Role:
    key: str
    title: str
    tagline: str
    passive: str
    skills: tuple[Skill, Skill]
    example: str
    color: str
    hp_scale: float = 1.0
    shield_scale: float = 1.0
    power: float = 1.0
    rescue: float = 1.0
    aura: float = 0.0
    pierce_guard: bool = False
    weak_scale: float = 1.0

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "tagline": self.tagline,
            "passive": self.passive,
            "color": self.color,
            "example": self.example,
            "skills": [skill.describe() for skill in self.skills],
        }


ROLES: dict[str, Role] = {
    "admin": Role(
        key="admin",
        title="Админ",
        tagline="У него root, и он этим пользуется.",
        passive="+35% здоровья, щит прочнее в полтора раза.",
        color="#ffd93d",
        hp_scale=1.35,
        shield_scale=1.5,
        skills=(
            Skill(
                "firewall", "admin", "Файрвол", "firewall(angle)",
                "Стена перед магом на 6 с. Вражеские снаряды отлетают от неё и бьют по врагам в полтора раза сильнее.",
                30, 9.0, ROLE_STAGE,
            ),
            Skill(
                "sudo", "admin", "sudo", "sudo()",
                "5 с неуязвимости. Враги рядом бросают всё и идут к админу, а союзники поблизости получают вдвое меньше урона.",
                45, 20.0, SECOND_SKILL_STAGE,
            ),
        ),
        example=(
            "# Стена туда, куда смотрит курсор\n"
            'if ready("firewall"):\n    firewall(aim())\n\n'
            "# Когда жарко, забираем удар на себя\n"
            'if me().hp < me().max_hp * 0.5 and ready("sudo"):\n    sudo()\n\n'
            "fireball(aim())\n"
        ),
    ),
    "hacker": Role(
        key="hacker",
        title="Хакер",
        tagline="Находит дыру и ломает всё вокруг неё.",
        passive="+25% урона рун, но на 20% меньше здоровья.",
        color="#7fffb0",
        hp_scale=0.8,
        power=1.25,
        skills=(
            Skill(
                "exploit", "hacker", "Эксплойт", "exploit(enemy)",
                "Метка на 6 с: цель получает на 35% больше урона от всех. Если она умрёт с меткой, будет segfault: взрыв вокруг, а метка прыгает на соседа, до трёх раз подряд.",
                20, 4.0, ROLE_STAGE,
            ),
            Skill(
                "hijack", "hacker", "Взлом", "hijack(enemy)",
                "Враг на 7 с переходит на вашу сторону и бьёт своих, а они бьют его. Босса взломать нельзя.",
                55, 22.0, SECOND_SKILL_STAGE,
            ),
        ),
        example=(
            "# С enemies() можно выбрать, кого метить: например, самого живучего\n"
            'if ready("exploit"):\n    exploit()\n\n'
            "# Без аргумента навык берёт врага у курсора\n"
            'if ready("hijack"):\n    hijack()\n\n'
            "fireball(aim())\n"
        ),
    ),
    "devops": Role(
        key="devops",
        title="Девопс",
        tagline="Пока он рядом, прод не падает.",
        passive="Союзники рядом восстанавливают 1,5 HP/с, а павших он поднимает в полтора раза быстрее.",
        color="#6fd6ff",
        rescue=1.5,
        aura=1.5,
        skills=(
            Skill(
                "patch", "devops", "Патч", "patch(ally)",
                "Лечит союзника на 32 HP на расстоянии, снимает замедление и проклятия босса. Здоровых не трогает и ману на них не тратит.",
                20, 2.0, ROLE_STAGE,
            ),
            Skill(
                "rollback", "devops", "Откат", "rollback(ally)",
                "Возвращает союзника на 3 с назад: на старое место, с прежним здоровьем и маной, если их было больше, и снимает проклятия. Поднимает даже павшего, а без аргумента его первым и выберет.",
                60, 28.0, SECOND_SKILL_STAGE,
            ),
        ),
        example=(
            "# Без аргумента навык берёт союзника у курсора.\n"
            "# С allies() можно найти самого раненого циклом\n"
            'if ready("patch"):\n    patch()\n\n'
            'if ready("rollback") and me().hp < 40:\n    rollback()\n\n'
            "fireball(aim())\n"
        ),
    ),
    "tester": Role(
        key="tester",
        title="Тестировщик",
        tagline="Воспроизвёл, задокументировал, сломал.",
        passive="Руны пробивают щиты модераторов, а удары по слабостям ещё на 40% сильнее.",
        color="#e08cff",
        pierce_guard=True,
        weak_scale=1.4,
        skills=(
            Skill(
                "scan", "tester", "Скан", "scan(enemy)",
                "Возвращает словарь с данными цели: weak, immune, guard, hp, а если целей нет, None. На 6 с снимает с неё иммунитет и щит, для всей группы.",
                12, 3.0, ROLE_STAGE,
            ),
            Skill(
                "breakpoint", "tester", "Брейкпоинт", "breakpoint(x, y)",
                "Останавливает в зоне на 3,2 с всех врагов и их снаряды. Ваши руны продолжают лететь.",
                50, 18.0, SECOND_SKILL_STAGE,
            ),
        ),
        example=(
            "# Сканируем врага у курсора и выбираем руну по его слабости\n"
            'if ready("scan"):\n    report = scan()\n    # Рядом никого? Тогда scan вернёт None\n'
            '    if report:\n        log(report["name"], report["weak"])\n'
            '        if "frostbolt" in report["weak"]:\n            frostbolt(aim())\n\n'
            'if ready("breakpoint"):\n    point = cursor()\n    if point:\n'
            "        breakpoint(point.x, point.y)\n\n"
            "fireball(aim())\n"
        ),
    ),
}

SKILLS: dict[str, Skill] = {
    skill.name: skill for role in ROLES.values() for skill in role.skills
}
SKILL_COSTS: dict[str, int] = {name: skill.cost for name, skill in SKILLS.items()}


def describe_roles() -> dict[str, Any]:
    return {
        "unlock": ROLE_STAGE,
        "second": SECOND_SKILL_STAGE,
        "roles": [role.describe() for role in ROLES.values()],
    }


def apply_role(player: Player, key: str) -> None:
    """Turn a mage with their upgrades into a mage with a job."""

    role = ROLES.get(key)
    if role is None:
        return
    player.role = key
    player.max_hp = round(player.max_hp * role.hp_scale)
    player.hp = player.max_hp
    player.shield_power *= role.shield_scale
    perks = player.perks
    player.perks = replace(
        perks,
        power=perks.power * role.power,
        rescue=perks.rescue * role.rescue,
        pierce_guard=role.pierce_guard,
        weak_scale=role.weak_scale,
    )


class SkillBook:
    """The role skills of one casting, on top of the runes in ``SpellSession``."""

    def __init__(self, world: "StoryArena", session: SpellSession) -> None:
        self.world = world
        self.session = session
        self.player = session.player

    def api(self) -> dict[str, Any]:
        return {name: self._bound(skill) for name, skill in SKILLS.items()}

    def _bound(self, skill: Skill) -> Any:
        method = getattr(self, skill.name)

        def rune(*args: Any) -> Any:
            self._check_allowed(skill)
            return method(*args)

        return rune

    def _check_allowed(self, skill: Skill) -> None:
        if self.player.role != skill.role:
            title = ROLES[skill.role].title
            raise SpellRuntimeError(f"{skill.name} — это навык роли «{title}».")
        if self.world.stage.index < skill.stage:
            raise SpellRuntimeError(f"Навык {skill.name} откроется в следующей главе.")
        wait = self.world.skill_wait(self.player, skill.name)
        if wait > 0:
            raise SpellRuntimeError(f"Навык {skill.name} будет готов через {wait:.1f} с.")

    def _pay(self, name: str) -> None:
        skill = SKILLS[name]
        self.session._spend(skill.cost, name)
        self.player.skill_ready[name] = self.world.now + skill.cooldown

    # --------------------------------------------------------------- targeting
    def _cursor(self) -> tuple[float, float]:
        session = self.session
        if session.cursor_x is not None and session.cursor_y is not None:
            return session.cursor_x, session.cursor_y
        player = self.player
        return (
            player.x + math.cos(player.aim) * 200,
            player.y + math.sin(player.aim) * 200,
        )

    def _in_range(self, monster: "Monster") -> bool:
        return math.hypot(monster.x - self.player.x, monster.y - self.player.y) <= SKILL_RANGE

    def _enemy(self, value: Any, *, bosses: bool = True) -> "Monster | None":
        """An enemy from ``enemies()``, or with no argument the best one near the cursor.

        Asked for nothing in particular and finding nothing, a skill does nothing,
        so one line about a skill cannot abort a spell in an empty corridor.  A bad
        target named on purpose is an error, because that is a bug in the code.
        """

        world = self.world
        targets = world.targets_for(self.player.id)
        if value is None:
            x, y = self._cursor()
            return min(
                (
                    target
                    for target in targets
                    if self._in_range(target) and (bosses or not target.species.boss)
                ),
                key=lambda target: math.hypot(target.x - x, target.y - y),
                default=None,
            )
        if not isinstance(value, UnitView):
            raise SpellRuntimeError("Цель должна быть врагом из enemies().")
        monster = world.monsters.get(value.id)
        if monster is None or monster not in targets:
            raise SpellRuntimeError("Этой цели больше нет.")
        if not self._in_range(monster):
            raise SpellRuntimeError("Цель слишком далеко.")
        return monster

    def _nearest_mate(self, mates: list[Player]) -> Player | None:
        x, y = self._cursor()
        return min(mates, key=lambda mate: math.hypot(mate.x - x, mate.y - y), default=None)

    def _ally(self, value: Any) -> Player:
        """A mate named by ``allies()``. Each skill picks its own when none is named."""

        if not isinstance(value, UnitView):
            raise SpellRuntimeError("Цель должна быть союзником из allies().")
        mate = self.world.players.get(value.id)
        if mate is None:
            raise SpellRuntimeError("Этого союзника больше нет.")
        return mate

    # ------------------------------------------------------------------- admin
    def firewall(self, angle: Any) -> None:
        heading = _api_angle(angle)
        self._pay("firewall")
        self.world.raise_barrier(self.player, heading)

    def sudo(self) -> None:
        self._pay("sudo")
        self.world.grant_sudo(self.player)

    # ------------------------------------------------------------------ hacker
    def exploit(self, enemy: Any = None) -> None:
        monster = self._enemy(enemy)
        if monster is not None:
            self._pay("exploit")
            self.world.mark(monster, self.player)

    def hijack(self, enemy: Any = None) -> None:
        monster = self._enemy(enemy, bosses=False)
        if monster is None:
            return
        if monster.species.boss:
            raise SpellRuntimeError("Босса взломать нельзя.")
        self._pay("hijack")
        self.world.hijack(monster, self.player)

    # ------------------------------------------------------------------ devops
    def patch(self, ally: Any = None) -> None:
        if ally is None:
            mate = self._nearest_mate(
                [m for m in self.world.players.values() if not m.dead and self._needs_patch(m)]
            )
            if mate is None:
                return
        else:
            mate = self._ally(ally)
            if mate.dead:
                raise SpellRuntimeError("Патч не поднимает павших. Для этого есть rollback.")
            if not self._needs_patch(mate):
                return
        self._pay("patch")
        self.world.patch(self.player, mate, HEAL_AMOUNT)

    def _needs_patch(self, mate: Player) -> bool:
        slowed = mate.slow_until > self.world.now
        return mate.hp < mate.max_hp - 0.5 or slowed or bool(mate.curses)

    def rollback(self, ally: Any = None) -> None:
        if ally is None:
            mates = list(self.world.players.values())
            mate = self._nearest_mate([m for m in mates if m.dead] or mates)
        else:
            mate = self._ally(ally)
        if mate.id not in self.world.history:
            raise SpellRuntimeError("Для отката пока нет сохранённого состояния.")
        self._pay("rollback")
        self.world.rollback(self.player, mate)

    # ------------------------------------------------------------------ tester
    def scan(self, enemy: Any = None) -> dict[str, Any] | None:
        monster = self._enemy(enemy)
        if monster is None:
            return None
        self._pay("scan")
        return self.world.scan(monster, self.player)

    def breakpoint(self, x: Any = None, y: Any = None) -> None:
        cursor_x, cursor_y = self._cursor()
        target_x = cursor_x if x is None else _api_number(x, "x")
        target_y = cursor_y if y is None else _api_number(y, "y")
        self._pay("breakpoint")
        self.world.place_breakpoint(self.player, target_x, target_y)
