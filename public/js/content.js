/* Spellbook defaults, example scrolls and persistent storage for Arcane 2D. */

const STORAGE_SPELLS = "arcane2d.spells.v1";
const STORAGE_NAME = "arcane2d.mage.v1";
const STORAGE_SOUND = "arcane2d.sound.v1";

export const DEFAULT_SPELLS = [
  {
    name: "Пламя охотника",
    code: `# aim() направлен туда, куда смотрит курсор
fireball(aim())

# ready() проверяет ману и перезарядку руны
if me().hp < 45 and ready("shield"):
    shield()
`,
  },
  {
    name: "Ледяной шаг",
    code: `# Ручной прицел: снаряд летит на курсор
frostbolt(aim())

if me().hp < 55 and ready("heal"):
    heal()
`,
  },
  {
    name: "Оберег",
    code: `# Щит и огонь по направлению прицела
if ready("shield"):
    shield()

fireball(aim())
`,
  },
];

const LEGACY_DEFAULT_CODES = [
  `target = nearest(760)

if target:
    aim_at = direction(target.x, target.y)
    fireball(aim_at)
    if target.dist < 210:
        dash(aim_at + PI, 150)
else:
    fireball(aim())
`,
  `target = nearest(700)

if target:
    frostbolt(direction(target.x, target.y))
    if target.dist < 230:
        nova(165)
    if me().hp < 55:
        heal()
else:
    frostbolt(aim())
`,
  `target = nearest(620)

if me().shield < 1:
    shield()

if target and target.dist < 430:
    ward(target.x, target.y)

if target:
    fireball(direction(target.x, target.y))
else:
    fireball(aim())
`,
];

const LEGACY_CODE_REPLACEMENTS = [
  {
    old: `# aim() направлен туда, куда смотрит курсор
fireball(aim())

if me().hp < 45:
    shield()
`,
    code: DEFAULT_SPELLS[0].code,
  },
  {
    old: `# Ручной прицел: снаряд летит на курсор
frostbolt(aim())

if me().hp < 55:
    heal()
`,
    code: DEFAULT_SPELLS[1].code,
  },
  {
    old: `# Щит и огонь по направлению прицела
if me().shield < 1:
    shield()

fireball(aim())
`,
    code: DEFAULT_SPELLS[2].code,
  },
  {
    old: `target = nearest(520)

if target:
    emp(target.x, target.y)
else:
    emp(me().x + cos(aim()) * 360, me().y + sin(aim()) * 360)
`,
    code: `point = cursor()

if point:
    emp(point.x, point.y)
else:
    emp(me().x + cos(aim()) * 360, me().y + sin(aim()) * 360)
`,
  },
];

export const EXAMPLES = [
  {
    name: "Веер пламени",
    description: "Пять огненных снарядов разворачиваются в дугу от прицела.",
    code: `base = aim()

for offset in [-0.24, -0.12, 0, 0.12, 0.24]:
    fireball(base + offset)
`,
  },
  {
    name: "Точный охотник",
    description: "Стреляет по прицелу, держит щит и лечится.",
    code: `fireball(aim())

if me().hp < 50 and ready("shield"):
    shield()

if me().hp < 35 and ready("heal"):
    heal()
`,
  },
  {
    name: "Энергетический луч",
    description: "Дорогой луч прожигает широкую полосу и пробивает укрытия.",
    code: `beam(aim())
`,
  },
  {
    name: "Э.М.П. Аганима",
    description: "Ставится в точку курсора, сжигает ману и стягивает врагов.",
    code: `point = cursor()

if point:
    emp(point.x, point.y)
else:
    emp(me().x + cos(aim()) * 360, me().y + sin(aim()) * 360)
`,
  },
  {
    name: "Рунная засада",
    description: "Ставит руну в точку прицела и бьёт по направлению.",
    code: `point = cursor()

if point:
    ward(point.x, point.y)
else:
    ward()

frostbolt(aim())

if me().hp < 45 and ready("heal"):
    heal()
`,
  },
  {
    name: "Нова при сближении",
    description: "Взрыв вокруг себя, отход и выстрел по прицелу.",
    code: `nova(190)
dash(aim() + PI, 175)
frostbolt(aim())
say("Слишком близко")
`,
  },
  {
    name: "Кровавый оберег",
    description: "Лечение, щит и огонь по прицелу.",
    code: `if me().hp < 58 and ready("heal"):
    heal()

if ready("shield"):
    shield()

fireball(aim())
`,
  },
  {
    name: "Стая искр",
    description: "Восемь разноцветных искр разлетаются веером от прицела.",
    code: `spark_volley(aim(), 8, 1.15)
`,
  },
  {
    name: "Магический страж",
    description: "Щит, лечение и снаряд для неторопливой осады.",
    code: `if ready("shield"):
    shield()

if me().hp < 48 and ready("heal"):
    heal()

if me().mana > 50:
    fireball(aim())
`,
  },
  {
    name: "Цепная молния",
    description: "Молния бьёт по направлению прицела и перескакивает на соседей.",
    code: `chain_lightning(aim(), 3)
`,
  },
  {
    name: "Небесная кара",
    description: "Молния по направлению прицела оглушает первого врага на 0,5 с.",
    code: `lightning_strike(aim())
`,
  },
  {
    name: "Метеоритный дождь",
    description: "Три метеора падают в точку курсора и накрывают площадь.",
    code: `point = cursor()

if point and point.dist <= 600:
    meteor(point.x, point.y)
else:
    meteor(me().x + cos(aim()) * 360, me().y + sin(aim()) * 360)
`,
  },
  {
    name: "Похищение жизни",
    description: "Луч урона по прицелу возвращает часть здоровья магу.",
    code: `siphon(aim())
`,
  },
  {
    name: "Ядовитое облако",
    description: "Оставляет область, которая отравляет врагов несколько секунд.",
    code: `point = cursor()

if point and point.dist <= 500:
    poison_cloud(point.x, point.y)
else:
    poison_cloud(me().x + cos(aim()) * 320, me().y + sin(aim()) * 320)
`,
  },
  {
    name: "Пустой гримуар",
    description: "Чистый лист для собственного эксперимента с ручным прицелом.",
    code: `fireball(aim())
`,
  },
];

function normalizeCode(value) {
  return String(value || "").replace(/\r\n/g, "\n").trim();
}

function cleanSpell(raw, index) {
  const fallback = DEFAULT_SPELLS[index] || DEFAULT_SPELLS[0];
  if (!raw || typeof raw !== "object") {
    return { name: fallback.name, code: fallback.code };
  }
  const name =
    typeof raw.name === "string" && raw.name.trim()
      ? raw.name.trim().slice(0, 28)
      : fallback.name;
  const code = typeof raw.code === "string" ? raw.code.slice(0, 12000) : fallback.code;
  const legacy = LEGACY_DEFAULT_CODES[index];
  if (legacy && normalizeCode(code) === normalizeCode(legacy)) {
    return { name, code: fallback.code };
  }
  const replacement = LEGACY_CODE_REPLACEMENTS.find(
    (entry) => normalizeCode(code) === normalizeCode(entry.old),
  );
  if (replacement) {
    return { name, code: replacement.code };
  }
  return { name, code };
}

export function loadSpellbook() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_SPELLS) || "null");
    if (Array.isArray(stored)) {
      return [0, 1, 2].map((index) => cleanSpell(stored[index], index));
    }
  } catch {
    /* A broken or blocked storage must never prevent the arena from opening. */
  }
  return DEFAULT_SPELLS.map((spell) => ({ ...spell }));
}

export function saveSpellbook(spells) {
  try {
    localStorage.setItem(STORAGE_SPELLS, JSON.stringify(spells));
  } catch {
    /* Private mode can reject storage writes. The game still works in memory. */
  }
}

export function loadMageName() {
  try {
    return (localStorage.getItem(STORAGE_NAME) || "").slice(0, 16);
  } catch {
    return "";
  }
}

export function saveMageName(name) {
  try {
    localStorage.setItem(STORAGE_NAME, name);
  } catch {
    /* Ignore storage quotas. */
  }
}

export function loadSoundEnabled() {
  try {
    return localStorage.getItem(STORAGE_SOUND) !== "off";
  } catch {
    return true;
  }
}

export function saveSoundEnabled(enabled) {
  try {
    localStorage.setItem(STORAGE_SOUND, enabled ? "on" : "off");
  } catch {
    /* Ignore storage quotas. */
  }
}

export const SLOT_RUNES = ["I", "II", "III"];

/* The spell language as the editor sees it: colours, completion and signatures.
 * Argument strings show the player what to fill in; `element` picks the colour. */
export const SPELL_API = [
  { name: "fireball", args: "angle, speed=1.0", about: "Снаряд, 16 урона", element: "fire" },
  { name: "meteor", args: "x, y, radius=120", about: "Три метеора через 1,15 с", element: "fire" },
  { name: "frostbolt", args: "angle", about: "10 урона и замедление", element: "frost" },
  { name: "beam", args: "angle, length=780, width=96", about: "Луч сквозь укрытия, 34 урона", element: "frost" },
  { name: "chain_lightning", args: "angle, targets=3", about: "30 / 24 / 18 по цепочке", element: "storm" },
  { name: "lightning_strike", args: "angle", about: "28 урона и оглушение", element: "storm" },
  { name: "emp", args: "x, y", about: "Сжигает ману, стягивает врагов", element: "storm" },
  { name: "spark_volley", args: "angle, count=8, spread=1.1", about: "Веер из искр, по 5 урона", element: "arcane" },
  { name: "nova", args: "radius=150", about: "15 урона и отброс вокруг", element: "arcane" },
  { name: "ward", args: "x, y", about: "Мина: 22 урона, до двух", element: "arcane" },
  { name: "siphon", args: "angle, length=380, width=64", about: "18 урона и лечение", element: "blood" },
  { name: "poison_cloud", args: "x, y, radius=110", about: "Яд: 6 урона за тик", element: "nature" },
  { name: "heal", args: "", about: "+30 HP, перезарядка 4,5 с", element: "nature" },
  { name: "shield", args: "", about: "Щит на 38, перезарядка 3 с", element: "guard" },
  { name: "dash", args: "angle, dist=170", about: "Рывок на 60–260", element: "guard" },
  { name: "blink", args: "x, y", about: "Перенос в свободную точку", element: "guard" },
];

export const SENSE_API = [
  { name: "me", args: "", about: "Ваш маг: .hp .mana .shield .x .y" },
  { name: "aim", args: "", about: "Угол прицела в радианах" },
  { name: "cursor", args: "", about: "Точка под курсором: .x .y .dist" },
  { name: "ready", args: "rune", about: "Хватит ли маны и готова ли руна" },
  { name: "direction", args: "x, y", about: "Угол от мага к точке" },
  { name: "distance", args: "x1, y1, x2, y2", about: "Расстояние между точками" },
  { name: "log", args: "value", about: "Строка в «Печать»" },
  { name: "print", args: "value", about: "То же, что log" },
  { name: "say", args: "text", about: "Фраза над магом" },
  { name: "rand", args: "a, b", about: "Случайное дробное" },
  { name: "randi", args: "a, b", about: "Случайное целое" },
  { name: "clamp", args: "value, low, high", about: "Ограничить диапазоном" },
  { name: "sin", args: "a", about: "Синус" },
  { name: "cos", args: "a", about: "Косинус" },
  { name: "atan2", args: "y, x", about: "Угол по катетам" },
  { name: "hypot", args: "x, y", about: "Длина вектора" },
  { name: "sqrt", args: "x", about: "Квадратный корень" },
  { name: "range", args: "n", about: "Числа для цикла" },
  { name: "len", args: "items", about: "Длина коллекции" },
  { name: "abs", args: "x", about: "Модуль числа" },
  { name: "min", args: "a, b", about: "Меньшее" },
  { name: "max", args: "a, b", about: "Большее" },
  { name: "sum", args: "items", about: "Сумма списка" },
  { name: "round", args: "x, digits=0", about: "Округление" },
  { name: "int", args: "x", about: "К целому" },
  { name: "float", args: "x", about: "К дробному" },
  { name: "str", args: "x", about: "К строке" },
  { name: "bool", args: "x", about: "К логическому" },
];

export const CONSTANT_API = ["PI", "TAU", "ARENA_W", "ARENA_H"];

export const FIELD_API = [
  { name: "hp", about: "Здоровье" },
  { name: "max_hp", about: "Предел здоровья" },
  { name: "mana", about: "Мана" },
  { name: "max_mana", about: "Предел маны" },
  { name: "shield", about: "Прочность щита" },
  { name: "aim", about: "Угол прицела" },
  { name: "name", about: "Имя мага" },
  { name: "x", about: "Координата X" },
  { name: "y", about: "Координата Y" },
  { name: "dist", about: "Расстояние до курсора" },
];
