/* Spellbook defaults, example scrolls and persistent storage for Arcane 2D. */

const STORAGE_SPELLS = "arcane2d.spells.v1";
const STORAGE_NAME = "arcane2d.mage.v1";
const STORAGE_SOUND = "arcane2d.sound.v1";

export const DEFAULT_SPELLS = [
  {
    name: "Пламя охотника",
    code: `# aim() направлен туда, куда смотрит курсор
fireball(aim())

if me().hp < 45:
    shield()
`,
  },
  {
    name: "Ледяной шаг",
    code: `# Ручной прицел: снаряд летит на курсор
frostbolt(aim())

if me().hp < 55:
    heal()
`,
  },
  {
    name: "Оберег",
    code: `# Щит и огонь по направлению прицела
if me().shield < 1:
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

if me().hp < 50 and me().shield < 1:
    shield()

if me().hp < 35:
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

if me().hp < 45:
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
    code: `if me().hp < 58:
    heal()

if me().shield < 1:
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
    code: `if me().shield < 1:
    shield()

if me().hp < 48:
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
