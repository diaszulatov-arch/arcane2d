/* The five chapters as pictures: tiles, weather, doors, portals and the bestiary. */

const TAU = Math.PI * 2;
// Pixels per tile in the baked floor: about one screen pixel at the game's zoom,
// and small enough that the largest floor stays well under 30 MB.
const BAKE = 16;
const LIFE_LIMIT = 420;

export const THEMES = {
  // Домашние страницы девяностых: бирюзовый фон, серые объёмные кнопки.
  oldweb: {
    ambient: "#6c7f88",
    floors: ["#2f6f78", "#357880", "#2a646d", "#3d8590", "#255a62"],
    grout: "#1c4a52",
    wallFace: ["#a8a8b0", "#9a9aa4", "#b6b6be"],
    wallTop: "#10262a",
    wallRim: "#e8e8ee",
    pillarTop: "#c0c0c8",
    pillarFace: "#70707c",
    accent: "#ffd93d",
    door: "#ff5a4f",
    lamp: "#ffd93d",
    lampLight: "#ffe9a8",
    specks: ["#ffd93d", "#7fe0ee"],
    weather: "stars",
  },
  // Лента в тёмной теме: карточки и неоновые сердечки.
  feed: {
    ambient: "#5f5a80",
    floors: ["#232640", "#292d4a", "#1f2239", "#303456", "#1b1e33"],
    grout: "#14162a",
    wallFace: ["#4a3f8a", "#5a45a0", "#6a4fb4"],
    wallTop: "#0c0d1a",
    wallRim: "#ff6b9e",
    pillarTop: "#7a5fd0",
    pillarFace: "#3a2f70",
    accent: "#ff6b9e",
    door: "#ff6b9e",
    lamp: "#ff6b9e",
    lampLight: "#ffa6c6",
    specks: ["#ff6b9e", "#7f9fff"],
    weather: "hearts",
  },
  // Над облаками: всё лёгкое, но пол не должен слепить.
  cloud: {
    ambient: "#7f93b4",
    floors: ["#6a8db4", "#7296bc", "#6182a8", "#7da2c8", "#587a9e"],
    grout: "#4a6a8e",
    wallFace: ["#dfe8f4", "#cfdbea", "#eef3fa"],
    wallTop: "#2f4768",
    wallRim: "#ffffff",
    pillarTop: "#f0f4fa",
    pillarFace: "#a8bcd4",
    accent: "#ffffff",
    door: "#6fd6ff",
    lamp: "#a6e4ff",
    lampLight: "#d6f0ff",
    specks: ["#e8f2fc", "#4a6a8e"],
    weather: "clouds",
  },
  // Фальшпол, стойки и индикаторы.
  datacenter: {
    ambient: "#56665c",
    floors: ["#2e3338", "#34393f", "#292d32", "#3b4046", "#25292d"],
    grout: "#16191c",
    wallFace: ["#1f2428", "#262c31", "#1a1e22"],
    wallTop: "#0a0c0e",
    wallRim: "#4fe08a",
    pillarTop: "#3a4046",
    pillarFace: "#1c2024",
    accent: "#4fe08a",
    door: "#ffae5c",
    lamp: "#4fe08a",
    lampLight: "#9ff0c0",
    specks: ["#4fe08a", "#555c62"],
    weather: "binary",
  },
  // Внутри PGT: чёрное стекло и красный свет.
  core: {
    ambient: "#5a3440",
    floors: ["#1f1218", "#26151d", "#1a0f14", "#2e1822", "#150c11"],
    grout: "#0c0609",
    wallFace: ["#4a1420", "#5a1826", "#3f111b"],
    wallTop: "#060304",
    wallRim: "#ff4f6a",
    pillarTop: "#6a1f30",
    pillarFace: "#2c0d15",
    accent: "#ff4f6a",
    door: "#ff4f6a",
    lamp: "#ff4f6a",
    lampLight: "#ff8fa0",
    specks: ["#ff4f6a", "#5a2a36"],
    weather: "glitch",
  },
};

function seededRandom(seed) {
  let value = seed >>> 0;
  return () => {
    value += 0x6d2b79f5;
    let t = value;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function themeOf(config) {
  return THEMES[config?.theme] || THEMES.oldweb;
}

function hexChannels(hex) {
  const value = parseInt(hex.slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

function mix(a, b, amount) {
  const from = hexChannels(a);
  const to = hexChannels(b);
  const part = (index) => Math.round(from[index] + (to[index] - from[index]) * amount);
  return `rgb(${part(0)}, ${part(1)}, ${part(2)})`;
}

/** The same place always gets the same dice, so opening a wall does not repaint the room. */
function tileDice(seed, x, y, salt = 0) {
  return seededRandom((Math.imul(x, 73856093) ^ Math.imul(y, 19349663) ^ Math.imul(seed, 83492791) ^ salt) >>> 0);
}

/** Soft blotches several tiles wide: what keeps a floor from looking like a chessboard. */
function makeNoise(seed) {
  const corner = (x, y) => tileDice(seed, x, y, 0x51ed)();
  const ease = (value) => value * value * (3 - 2 * value);
  return (x, y) => {
    const left = Math.floor(x);
    const top = Math.floor(y);
    const fx = ease(x - left);
    const fy = ease(y - top);
    const a = corner(left, top) + (corner(left + 1, top) - corner(left, top)) * fx;
    const b = corner(left, top + 1) + (corner(left + 1, top + 1) - corner(left, top + 1)) * fx;
    return a + (b - a) * fy;
  };
}

/** A colour from the chapter's floor tones, dark to light, by a value from 0 to 1. */
function floorRamp(theme, value) {
  const [mid, light, dark, lightest, darkest] = theme.floors;
  const ramp = [darkest, dark, mid, light, lightest];
  const spot = Math.max(0, Math.min(0.999, value)) * (ramp.length - 1);
  const low = Math.floor(spot);
  return mix(ramp[low], ramp[low + 1], spot - low);
}

/** Home pages of the nineties: raised tiles, dotted wallpaper and stray links. */
function paintOldWebTile(ctx, px, py, theme, dice, tone) {
  ctx.fillStyle = floorRamp(theme, 0.25 + tone * 0.5);
  ctx.fillRect(px, py, BAKE, BAKE);
  ctx.fillStyle = "rgba(255, 255, 255, 0.09)";
  ctx.fillRect(px, py, BAKE - 1, 1);
  ctx.fillRect(px, py, 1, BAKE - 1);
  ctx.fillStyle = "rgba(0, 0, 0, 0.2)";
  ctx.fillRect(px, py + BAKE - 1, BAKE, 1);
  ctx.fillRect(px + BAKE - 1, py, 1, BAKE);
  ctx.fillStyle = "rgba(255, 255, 255, 0.07)";
  ctx.fillRect(px + 4, py + 4, 1, 1);
  ctx.fillRect(px + 11, py + 11, 1, 1);
  const roll = dice();
  if (roll < 0.05) {
    ctx.fillStyle = "rgba(255, 217, 61, 0.7)";
    ctx.fillRect(px + 7, py + 5, 1, 5);
    ctx.fillRect(px + 5, py + 7, 5, 1);
  } else if (roll < 0.09) {
    // A link nobody has clicked since 1999.
    ctx.fillStyle = "rgba(150, 200, 255, 0.4)";
    ctx.fillRect(px + 3, py + 6, 9, 2);
    ctx.fillRect(px + 3, py + 9, 9, 1);
  }
}

/** The Feed underfoot: endless posts, each with an avatar, some words and a heart. */
function paintFeedTile(ctx, x, y, px, py, theme, dice, tone) {
  const column = Math.floor(x / 5);
  const across = ((x % 5) + 5) % 5;
  const down = ((((y + column * 2) % 4) + 4) % 4);
  ctx.fillStyle = floorRamp(theme, 0.3 + tone * 0.28);
  ctx.fillRect(px, py, BAKE, BAKE);
  ctx.fillStyle = "rgba(255, 255, 255, 0.05)";
  if (down === 0) ctx.fillRect(px, py, BAKE, 1);
  if (across === 0) ctx.fillRect(px, py, 1, BAKE);
  ctx.fillStyle = "rgba(4, 4, 14, 0.55)";
  if (down === 3) ctx.fillRect(px, py + BAKE - 2, BAKE, 2);
  if (across === 4) ctx.fillRect(px + BAKE - 2, py, 2, BAKE);
  if (down === 0 && across === 0) {
    ctx.fillStyle = "rgba(127, 159, 255, 0.28)";
    ctx.fillRect(px + 4, py + 4, 7, 7);
    ctx.fillStyle = "rgba(255, 255, 255, 0.18)";
    ctx.fillRect(px + 6, py + 5, 3, 3);
  } else if (down === 0 && across === 1) {
    ctx.fillStyle = "rgba(205, 210, 245, 0.24)";
    ctx.fillRect(px, py + 5, BAKE - 2, 2);
  } else if (down === 1 || down === 2) {
    ctx.fillStyle = "rgba(205, 210, 245, 0.11)";
    const long = across < 4 ? BAKE : 6 + Math.floor(dice() * 8);
    ctx.fillRect(px, py + 4, long, 2);
    ctx.fillRect(px, py + 10, across < 4 ? BAKE : 4, 2);
  } else if (down === 3 && across === 0) {
    ctx.fillStyle = "rgba(255, 107, 158, 0.42)";
    ctx.fillRect(px + 4, py + 4, 2, 2);
    ctx.fillRect(px + 7, py + 4, 2, 2);
    ctx.fillRect(px + 4, py + 6, 5, 1);
    ctx.fillRect(px + 5, py + 7, 3, 1);
    ctx.fillRect(px + 6, py + 8, 1, 1);
  } else if (down === 3 && across === 1) {
    ctx.fillStyle = "rgba(255, 107, 158, 0.3)";
    ctx.fillRect(px, py + 5, 6, 2);
  }
}

/** Standing on a cloud: no tiles at all, only soft banks of white. */
function paintCloudTile(ctx, px, py, theme, wide, fine) {
  const step = 4;
  for (let row = 0; row < BAKE; row += step) {
    for (let col = 0; col < BAKE; col += step) {
      const big = wide((px + col) / 70, (py + row) / 70);
      const small = fine((px + col) / 22, (py + row) / 22);
      const value = big * 0.72 + small * 0.28;
      ctx.fillStyle = floorRamp(theme, value * 0.85);
      ctx.fillRect(px + col, py + row, step, step);
      if (value > 0.6) {
        ctx.fillStyle = `rgba(255, 255, 255, ${Math.min(0.34, (value - 0.6) * 1.5)})`;
        ctx.fillRect(px + col, py + row, step, step);
      }
    }
  }
}

/** Raised floor: panels two tiles wide, some of them perforated, all of them screwed down. */
function paintRackFloorTile(ctx, x, y, px, py, theme, seed) {
  const panelX = Math.floor(x / 2);
  const panelY = Math.floor(y / 2);
  const panel = tileDice(seed, panelX, panelY, 0xbeef);
  const across = ((x % 2) + 2) % 2;
  const down = ((y % 2) + 2) % 2;
  ctx.fillStyle = floorRamp(theme, 0.3 + panel() * 0.32);
  ctx.fillRect(px, py, BAKE, BAKE);
  const vented = panel() < 0.3;
  if (vented) {
    ctx.fillStyle = "rgba(0, 0, 0, 0.5)";
    for (let row = 2; row < BAKE; row += 4) {
      for (let col = 2; col < BAKE; col += 4) ctx.fillRect(px + col, py + row, 2, 2);
    }
  }
  ctx.fillStyle = "rgba(255, 255, 255, 0.07)";
  if (down === 0) ctx.fillRect(px, py, BAKE, 1);
  if (across === 0) ctx.fillRect(px, py, 1, BAKE);
  ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
  if (down === 1) ctx.fillRect(px, py + BAKE - 1, BAKE, 1);
  if (across === 1) ctx.fillRect(px + BAKE - 1, py, 1, BAKE);
  ctx.fillStyle = "rgba(180, 190, 200, 0.4)";
  ctx.fillRect(across === 0 ? px + 2 : px + BAKE - 4, down === 0 ? py + 2 : py + BAKE - 4, 2, 2);
}

/** Black glass with something moving behind it. */
function paintCoreTile(ctx, x, y, px, py, theme, tone) {
  ctx.fillStyle = floorRamp(theme, tone * 0.5);
  ctx.fillRect(px, py, BAKE, BAKE);
  const sheen = (((x + y) % 9) + 9) % 9;
  if (sheen < 2) {
    ctx.fillStyle = "rgba(255, 200, 215, 0.035)";
    ctx.fillRect(px, py, BAKE, BAKE);
  }
  ctx.fillStyle = "rgba(255, 79, 106, 0.1)";
  if (((x % 3) + 3) % 3 === 0) ctx.fillRect(px, py, 1, BAKE);
  if (((y % 3) + 3) % 3 === 0) ctx.fillRect(px, py, BAKE, 1);
}

/** Traces run from room to room under the glass, turning only at right angles. */
function paintCoreTraces(ctx, config, open, seed, life) {
  const rows = config.tiles;
  const dice = tileDice(seed, 7, 11, 0xc0de);
  const count = Math.round((rows.length * rows[0].length) / 70);
  for (let trace = 0; trace < count; trace += 1) {
    let x = Math.floor(dice() * rows[0].length);
    let y = Math.floor(dice() * rows.length);
    if (!open(x, y)) continue;
    let px = x * BAKE + 8;
    let py = y * BAKE + 8;
    let horizontal = dice() < 0.5;
    for (let leg = 0; leg < 4; leg += 1) {
      const sign = dice() < 0.5 ? -1 : 1;
      const length = 1 + Math.floor(dice() * 4);
      for (let step = 0; step < length; step += 1) {
        const nx = x + (horizontal ? sign : 0);
        const ny = y + (horizontal ? 0 : sign);
        if (!open(nx, ny)) break;
        ctx.fillStyle = "rgba(255, 79, 106, 0.07)";
        if (horizontal) ctx.fillRect(Math.min(px, px + sign * BAKE), py - 1, BAKE, 3);
        else ctx.fillRect(px - 1, Math.min(py, py + sign * BAKE), 3, BAKE);
        ctx.fillStyle = "rgba(255, 110, 135, 0.24)";
        if (horizontal) ctx.fillRect(Math.min(px, px + sign * BAKE), py, BAKE, 1);
        else ctx.fillRect(px, Math.min(py, py + sign * BAKE), 1, BAKE);
        x = nx;
        y = ny;
        px += horizontal ? sign * BAKE : 0;
        py += horizontal ? 0 : sign * BAKE;
      }
      ctx.fillStyle = "rgba(255, 143, 160, 0.42)";
      ctx.fillRect(px - 1, py - 1, 3, 3);
      if (life.length < LIFE_LIMIT) {
        life.push({ x: px - 1, y: py - 1, w: 3, h: 3, color: "#ff8fa0", phase: dice() * TAU, speed: 1.5 + dice() * 2 });
      }
      horizontal = !horizontal;
    }
  }
}

function dot(ctx, x, y, size, color) {
  ctx.fillStyle = color;
  ctx.fillRect(Math.round(x - size / 2), Math.round(y - size / 2), size, size);
}

function ring(ctx, cx, cy, rx, ry, color, size = 2, dash = 0) {
  const steps = Math.max(24, Math.round((rx + ry) * 1.6));
  for (let step = 0; step < steps; step += 1) {
    if (dash && step % (dash * 2) >= dash) continue;
    const angle = (step / steps) * TAU;
    dot(ctx, cx + Math.cos(angle) * rx, cy + Math.sin(angle) * ry, size, color);
  }
}

/** Something on the floor of each big room, so that no two look like the same hall. */
function paintEmblem(ctx, kind, room, dice) {
  const cx = (room.x + room.w / 2) * BAKE;
  const cy = (room.y + room.h / 2) * BAKE;
  const radius = Math.min(room.w, room.h) * BAKE * 0.3;
  if (kind === "oldweb") {
    // The spinning globe from every "best viewed in" badge.
    const color = "rgba(255, 233, 150, 0.15)";
    ring(ctx, cx, cy, radius, radius, color);
    ring(ctx, cx, cy, radius * 0.5, radius, color);
    for (const height of [-0.5, 0, 0.5]) {
      const half = radius * Math.sqrt(1 - height * height);
      for (let across = -half; across <= half; across += 3) dot(ctx, cx + across, cy + height * radius, 2, color);
    }
    for (let down = -radius; down <= radius; down += 3) dot(ctx, cx, cy + down, 2, color);
  } else if (kind === "feed") {
    const color = "rgba(255, 107, 158, 0.2)";
    for (let step = 0; step < 150; step += 1) {
      const angle = (step / 150) * TAU;
      const hx = 16 * Math.sin(angle) ** 3;
      const hy = -(13 * Math.cos(angle) - 5 * Math.cos(2 * angle) - 2 * Math.cos(3 * angle) - Math.cos(4 * angle));
      dot(ctx, cx + (hx * radius) / 16, cy + (hy * radius) / 16, 3, color);
    }
  } else if (kind === "cloud") {
    const color = "rgba(255, 255, 255, 0.24)";
    ring(ctx, cx, cy, radius, radius, color, 2, 4);
    ring(ctx, cx, cy, radius * 0.66, radius * 0.66, color, 2);
    for (let ray = 0; ray < 12; ray += 1) {
      const angle = (ray / 12) * TAU;
      for (let reach = 0.74; reach < 0.94; reach += 0.05) {
        dot(ctx, cx + Math.cos(angle) * radius * reach, cy + Math.sin(angle) * radius * reach, 2, color);
      }
    }
  } else if (kind === "datacenter") {
    // Keep out: the square around whatever used to stand here.
    const left = cx - radius;
    const top = cy - radius * 0.72;
    const wide = radius * 2;
    const tall = radius * 1.44;
    const band = 5;
    const stripe = (x, y, along) => {
      ctx.fillStyle = Math.floor((x + y) / 6) % 2 ? "rgba(255, 200, 60, 0.26)" : "rgba(0, 0, 0, 0.24)";
      ctx.fillRect(x, y, along ? 2 : band, along ? band : 2);
    };
    for (let x = left; x < left + wide; x += 2) {
      stripe(x, top, true);
      stripe(x, top + tall - band, true);
    }
    for (let y = top; y < top + tall; y += 2) {
      stripe(left, y, false);
      stripe(left + wide - band, y, false);
    }
  } else {
    const color = "rgba(255, 79, 106, 0.15)";
    ring(ctx, cx, cy, radius, radius * 0.56, color);
    ring(ctx, cx, cy, radius * 0.42, radius * 0.42, color);
    ring(ctx, cx, cy, radius * (dice() < 0.5 ? 0.14 : 0.18), radius * 0.36, "rgba(255, 140, 160, 0.26)", 3);
  }
}

function paintWallFace(ctx, x, y, theme, kind, dice, life) {
  if (kind === "oldweb") {
    // Raised grey panels, the look of every button in 1997.
    ctx.fillStyle = theme.wallFace[Math.floor(dice() * theme.wallFace.length)];
    ctx.fillRect(x, y, BAKE, BAKE);
    ctx.fillStyle = "#f4f4f8";
    ctx.fillRect(x, y, BAKE - 1, 1);
    ctx.fillRect(x, y, 1, BAKE - 1);
    ctx.fillStyle = "#55555f";
    ctx.fillRect(x, y + BAKE - 1, BAKE, 1);
    ctx.fillRect(x + BAKE - 1, y, 1, BAKE);
    if (dice() < 0.12) {
      ctx.fillStyle = "#2f6fe0";
      ctx.fillRect(x + 3, y + 5, 10, 2);
      ctx.fillRect(x + 3, y + 8, 7, 1);
    }
  } else if (kind === "datacenter") {
    // Rack fronts with rows of status lights.
    ctx.fillStyle = theme.wallFace[Math.floor(dice() * theme.wallFace.length)];
    ctx.fillRect(x, y, BAKE, BAKE);
    ctx.fillStyle = theme.wallRim;
    ctx.fillRect(x, y, BAKE, 1);
    for (let row = 0; row < 3; row += 1) {
      ctx.fillStyle = "#0c0e10";
      ctx.fillRect(x + 1, y + 2 + row * 5, BAKE - 2, 4);
      ctx.fillStyle = "#1f2428";
      ctx.fillRect(x + 8, y + 3 + row * 5, 6, 2);
      const ledX = x + 2 + Math.floor(dice() * 4);
      const ledY = y + 3 + row * 5;
      const color = dice() > 0.22 ? "#4fe08a" : "#ffae5c";
      ctx.fillStyle = color;
      ctx.fillRect(ledX, ledY, 2, 1);
      if (life.length < LIFE_LIMIT && dice() < 0.5) {
        life.push({ x: ledX, y: ledY, w: 2, h: 1, color: "#e8ffe8", phase: dice() * TAU, speed: 2 + dice() * 7 });
      }
    }
  } else if (kind === "cloud") {
    // Packed cloud rather than bricks.
    ctx.fillStyle = theme.wallFace[1];
    ctx.fillRect(x, y, BAKE, BAKE);
    for (let puff = 0; puff < 4; puff += 1) {
      ctx.fillStyle = theme.wallFace[Math.floor(dice() * theme.wallFace.length)];
      const size = 5 + Math.floor(dice() * 5);
      ctx.fillRect(x + Math.floor(dice() * (BAKE - size)), y + 2 + Math.floor(dice() * (BAKE - size - 2)), size, size - 1);
    }
    ctx.fillStyle = theme.wallRim;
    ctx.fillRect(x, y, BAKE, 1);
  } else {
    for (let row = 0; row < 3; row += 1) {
      const top = y + row * 5 + 1;
      const offset = row % 2 ? -4 : 0;
      for (let column = -1; column < 3; column += 1) {
        const left = x + column * 8 + offset;
        ctx.fillStyle = theme.wallFace[Math.floor(dice() * theme.wallFace.length)];
        ctx.fillRect(Math.max(x, left), top, Math.min(7, x + BAKE - Math.max(x, left)), 4);
      }
    }
    ctx.fillStyle = theme.wallRim;
    ctx.fillRect(x, y, BAKE, 1);
    if (life.length < LIFE_LIMIT && dice() < 0.1) {
      ctx.fillStyle = theme.accent;
      ctx.fillRect(x + 7, y + 5, 2, 6);
      life.push({ x: x + 7, y: y + 5, w: 2, h: 6, color: theme.accent, phase: dice() * TAU, speed: 1 + dice() * 2 });
    }
  }
  // The foot of the wall is in its own shadow, which is what makes it stand up.
  ctx.fillStyle = "rgba(0, 0, 0, 0.18)";
  ctx.fillRect(x, y + BAKE - 5, BAKE, 5);
  ctx.fillStyle = "rgba(0, 0, 0, 0.22)";
  ctx.fillRect(x, y + BAKE - 2, BAKE, 2);
}

function paintPillar(ctx, x, y, theme, dice) {
  const size = BAKE * 2;
  ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
  ctx.fillRect(x + 2, y + 6, size, size - 2);
  ctx.fillStyle = theme.pillarFace;
  ctx.fillRect(x, y + 8, size, size - 8);
  ctx.fillStyle = "rgba(0, 0, 0, 0.22)";
  ctx.fillRect(x + size - 7, y + 10, 7, size - 10);
  ctx.fillStyle = "rgba(255, 255, 255, 0.08)";
  ctx.fillRect(x, y + 10, 4, size - 10);
  ctx.fillStyle = theme.pillarTop;
  ctx.fillRect(x, y - 2, size, 12);
  ctx.fillStyle = "rgba(255, 255, 255, 0.28)";
  ctx.fillRect(x, y - 2, size, 1);
  ctx.fillRect(x, y - 2, 1, 12);
  ctx.fillStyle = "rgba(0, 0, 0, 0.3)";
  ctx.fillRect(x, y + size - 3, size, 3);
  ctx.fillStyle = theme.accent;
  ctx.globalAlpha = 0.55 + dice() * 0.3;
  ctx.fillRect(x + size / 2 - 1, y + 14, 2, 8);
  ctx.fillRect(x + size / 2 - 4, y + 17, 8, 2);
  ctx.globalAlpha = 1;
}

/** Each chapter has its own idea of what is under the floor. */
function paintPit(ctx, x, y, kind, dice, depth, noise) {
  const px = x * BAKE;
  const py = y * BAKE;
  const fade = Math.min(1, depth / 3);
  if (kind === "cloud") {
    // Sky, a long way down, with weather of its own.
    for (let row = 0; row < BAKE; row += 4) {
      const lower = Math.min(1, (depth * BAKE + row) / (BAKE * 3));
      for (let col = 0; col < BAKE; col += 4) {
        const dither = (Math.floor((px + col) / 4) + Math.floor((py + row) / 4)) % 2 ? 0.03 : 0;
        ctx.fillStyle = mix("#28507f", "#6ea6e0", Math.min(1, lower + dither));
        ctx.fillRect(px + col, py + row, 4, 4);
        const value = noise((px + col) / 30, (py + row) / 18);
        if (value > 0.56) {
          const white = Math.min(0.9, (value - 0.56) * 3.4) * (0.3 + lower * 0.7);
          ctx.fillStyle = `rgba(250, 252, 255, ${white})`;
          ctx.fillRect(px + col, py + row, 4, 4);
        }
      }
    }
  } else if (kind === "feed") {
    // The posts carry on down there, getting harder to read.
    ctx.fillStyle = "#07070f";
    ctx.fillRect(px, py, BAKE, BAKE);
    ctx.fillStyle = `rgba(90, 80, 170, ${0.2 - fade * 0.12})`;
    ctx.fillRect(px + 1, py + 2, BAKE - 2, 5);
    ctx.fillRect(px + 1, py + 9, BAKE - 2, 5);
    if (dice() < 0.1) {
      ctx.fillStyle = "rgba(255, 107, 158, 0.4)";
      ctx.fillRect(px + 6, py + 5, 3, 3);
    }
  } else if (kind === "datacenter") {
    // Under the raised floor: bundles of cable and the odd forgotten light.
    ctx.fillStyle = "#06080a";
    ctx.fillRect(px, py, BAKE, BAKE);
    const colors = ["#2a5fa0", "#a08a2a", "#2a8a5a", "#70707c"];
    for (let line = 0; line < 3; line += 1) {
      ctx.fillStyle = colors[Math.floor(noise(y * 0.7 + line * 5, line + 2) * colors.length)];
      ctx.globalAlpha = 0.5 - fade * 0.2;
      ctx.fillRect(px, py + 3 + line * 4, BAKE, 2);
      ctx.globalAlpha = 1;
    }
  } else if (kind === "core") {
    // Whatever PGT runs on, and it is warm.
    const heat = noise(px / 40, py / 40);
    ctx.fillStyle = mix("#0c0204", "#4a0c18", heat * (0.4 + fade * 0.6));
    ctx.fillRect(px, py, BAKE, BAKE);
    if (dice() < 0.25) {
      ctx.fillStyle = "rgba(255, 110, 90, 0.5)";
      ctx.fillRect(px + Math.floor(dice() * 13), py + Math.floor(dice() * 13), 2, 2);
    }
  } else {
    // Off the edge of the page.
    ctx.fillStyle = "#050814";
    ctx.fillRect(px, py, BAKE, BAKE);
    if (dice() < 0.32) {
      ctx.fillStyle = dice() < 0.2 ? "rgba(255, 233, 150, 0.8)" : "rgba(180, 210, 255, 0.6)";
      ctx.fillRect(px + Math.floor(dice() * (BAKE - 2)), py + Math.floor(dice() * (BAKE - 2)), 1, 1);
    }
  }
  if (depth === 0) {
    // The edge of the floor above, and its shadow across the drop.
    ctx.fillStyle = "rgba(0, 0, 0, 0.42)";
    ctx.fillRect(px, py, BAKE, 3);
    ctx.fillStyle = "rgba(0, 0, 0, 0.3)";
    ctx.fillRect(px, py + 3, BAKE, 5);
    ctx.fillStyle = "rgba(0, 0, 0, 0.14)";
    ctx.fillRect(px, py + 8, BAKE, 8);
  }
}

/** Soft dark where the floor meets anything taller than it. */
function paintContactShadows(ctx, width, height, open) {
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (!open(x, y)) continue;
      const px = x * BAKE;
      const py = y * BAKE;
      if (!open(x, y - 1)) {
        ctx.fillStyle = "rgba(0, 0, 0, 0.36)";
        ctx.fillRect(px, py, BAKE, 4);
        ctx.fillStyle = "rgba(0, 0, 0, 0.22)";
        ctx.fillRect(px, py + 4, BAKE, 4);
        ctx.fillStyle = "rgba(0, 0, 0, 0.1)";
        ctx.fillRect(px, py + 8, BAKE, 5);
      }
      if (!open(x, y + 1)) {
        ctx.fillStyle = "rgba(0, 0, 0, 0.24)";
        ctx.fillRect(px, py + BAKE - 2, BAKE, 2);
        ctx.fillStyle = "rgba(0, 0, 0, 0.1)";
        ctx.fillRect(px, py + BAKE - 5, BAKE, 3);
      }
      if (!open(x - 1, y)) {
        ctx.fillStyle = "rgba(0, 0, 0, 0.26)";
        ctx.fillRect(px, py, 2, BAKE);
        ctx.fillStyle = "rgba(0, 0, 0, 0.12)";
        ctx.fillRect(px + 2, py, 3, BAKE);
      }
      if (!open(x + 1, y)) {
        ctx.fillStyle = "rgba(0, 0, 0, 0.26)";
        ctx.fillRect(px + BAKE - 2, py, 2, BAKE);
        ctx.fillStyle = "rgba(0, 0, 0, 0.12)";
        ctx.fillRect(px + BAKE - 5, py, 3, BAKE);
      }
    }
  }
}

/** The whole floor baked once per dungeon; it changes only when a wall gives way. */
export function buildDungeonCanvas(config) {
  const rows = config?.tiles || [];
  const height = rows.length;
  const width = rows[0]?.length || 0;
  const canvas = document.createElement("canvas");
  canvas.width = width * BAKE;
  canvas.height = height * BAKE;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;
  const theme = themeOf(config);
  const kind = config.theme || "oldweb";
  const seed = Number(config.map_id) || 1;
  const open = (x, y) => rows[y]?.[x] === "." || rows[y]?.[x] === "o";
  const pit = (x, y) => rows[y]?.[x] === "_";
  const wide = makeNoise(seed);
  const fine = makeNoise(seed + 1);
  const life = [];

  ctx.fillStyle = theme.wallTop;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // First the floor, everywhere there is one.
  const pillars = [];
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (!open(x, y)) continue;
      const px = x * BAKE;
      const py = y * BAKE;
      const dice = tileDice(seed, x, y);
      const tone = wide(x / 5, y / 5);
      if (kind === "feed") paintFeedTile(ctx, x, y, px, py, theme, dice, tone);
      else if (kind === "cloud") paintCloudTile(ctx, px, py, theme, wide, fine);
      else if (kind === "datacenter") paintRackFloorTile(ctx, x, y, px, py, theme, seed);
      else if (kind === "core") paintCoreTile(ctx, x, y, px, py, theme, tone);
      else paintOldWebTile(ctx, px, py, theme, dice, tone);
      if (rows[y][x] === "o" && rows[y][x - 1] !== "o" && rows[y - 1]?.[x] !== "o") pillars.push([px, py]);
    }
  }
  // Then what is painted on it, which the walls below are free to cut off.
  if (kind === "core") paintCoreTraces(ctx, config, open, seed, life);
  (config.rooms || []).forEach((room, index) => {
    if (Math.min(room.w, room.h) >= 8) paintEmblem(ctx, kind, room, tileDice(seed, index, 3, 0xe11));
  });
  // Then everything that is not floor.
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (open(x, y)) continue;
      const px = x * BAKE;
      const py = y * BAKE;
      const dice = tileDice(seed, x, y, 0x77);
      if (pit(x, y)) {
        let depth = 0;
        while (depth < 3 && pit(x, y - depth - 1)) depth += 1;
        paintPit(ctx, x, y, kind, dice, depth, wide);
        continue;
      }
      ctx.fillStyle = theme.wallTop;
      ctx.fillRect(px, py, BAKE, BAKE);
      if (open(x, y + 1) || pit(x, y + 1)) {
        paintWallFace(ctx, px, py, theme, kind, dice, life);
      } else if (open(x, y - 1) || open(x - 1, y) || open(x + 1, y)) {
        ctx.fillStyle = theme.wallRim;
        ctx.globalAlpha = 0.55;
        if (open(x, y - 1)) ctx.fillRect(px, py, BAKE, 2);
        if (open(x - 1, y)) ctx.fillRect(px, py, 2, BAKE);
        if (open(x + 1, y)) ctx.fillRect(px + BAKE - 2, py, 2, BAKE);
        ctx.globalAlpha = 1;
      }
    }
  }
  paintContactShadows(ctx, width, height, open);
  for (const [x, y] of pillars) paintPillar(ctx, x, y, theme, tileDice(seed, x, y, 0x99));
  canvas.life = life;
  return canvas;
}

/** The little that moves in a baked floor: status lights, pulses in the traces. */
export function drawFloorLife(ctx, life, scale, view, now) {
  if (!life?.length) return;
  const t = now / 1000;
  for (const spark of life) {
    const x = spark.x * scale;
    const y = spark.y * scale;
    if (x < view.left || x > view.right || y < view.top || y > view.bottom) continue;
    const glow = Math.sin(t * spark.speed + spark.phase);
    if (glow < 0.15) continue;
    ctx.globalAlpha = glow * 0.85;
    ctx.fillStyle = spark.color;
    ctx.fillRect(x, y, spark.w * scale, spark.h * scale);
  }
  ctx.globalAlpha = 1;
}

export function buildMinimap(config) {
  const rows = config?.tiles || [];
  const canvas = document.createElement("canvas");
  canvas.width = rows[0]?.length || 1;
  canvas.height = rows.length || 1;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;
  ctx.fillStyle = "rgba(220, 215, 235, 0.42)";
  rows.forEach((row, y) => {
    for (let x = 0; x < row.length; x += 1) {
      if (row[x] === ".") ctx.fillRect(x, y, 1, 1);
    }
  });
  return canvas;
}

export function drawDoors(ctx, doors, config, now) {
  if (!doors?.length) return;
  const theme = themeOf(config);
  const tile = config.tile || 48;
  const pulse = 0.6 + Math.sin(now / 160) * 0.2;
  for (const [x, y] of doors) {
    const px = x * tile;
    const py = y * tile;
    ctx.fillStyle = theme.wallTop;
    ctx.fillRect(px + 2, py + 2, tile - 4, tile - 4);
    ctx.globalAlpha = pulse;
    ctx.fillStyle = theme.door;
    for (let bar = 0; bar < 4; bar += 1) {
      ctx.fillRect(px + 4 + bar * 11, py + 3, 5, tile - 6);
    }
    ctx.globalAlpha = 1;
  }
}

export function drawPortal(ctx, story, config, now) {
  if (!story?.portal) return;
  const [x, y] = story.portal;
  const theme = themeOf(config);
  const t = now / 1000;
  const ready = Boolean(story.portal_ready);
  ctx.save();
  ctx.translate(x, y);
  ctx.strokeStyle = ready ? theme.accent : "rgba(160, 150, 180, 0.34)";
  ctx.lineWidth = 3;
  ctx.setLineDash([9, 7]);
  ctx.beginPath();
  ctx.arc(0, 0, 66, t * 0.4, t * 0.4 + TAU);
  ctx.stroke();
  ctx.setLineDash([]);
  if (ready) {
    ctx.globalCompositeOperation = "lighter";
    for (let ring = 0; ring < 4; ring += 1) {
      const radius = 14 + ring * 13 + Math.sin(t * 3 + ring) * 3;
      ctx.strokeStyle = theme.accent;
      ctx.globalAlpha = 0.65 - ring * 0.12;
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(0, 0, radius, t * (ring + 1) * 0.7, t * (ring + 1) * 0.7 + 4.4);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(0, 0, 7 + Math.sin(t * 5) * 2, 0, TAU);
    ctx.fill();
    const hold = Number(story.portal_hold) || 0;
    if (hold > 0) {
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 5;
      ctx.beginPath();
      ctx.arc(0, 0, 80, -Math.PI / 2, -Math.PI / 2 + hold * TAU);
      ctx.stroke();
    }
  }
  ctx.restore();
}

export function drawLamps(ctx, config, now) {
  const theme = themeOf(config);
  const t = now / 1000;
  for (const [x, y] of config.torches || []) {
    ctx.fillStyle = "#0c0a10";
    ctx.fillRect(x - 9, y + 2, 18, 10);
    ctx.fillStyle = theme.lamp;
    ctx.globalAlpha = 0.72 + Math.sin(t * 3 + x) * 0.2;
    ctx.fillRect(x - 7, y + 4, 14, 6);
    ctx.globalAlpha = 1;
  }
}

/** A broken terminal in the world: red and flickering until somebody repairs it. */
export function drawTerminals(ctx, terminals, now) {
  const t = now / 1000;
  for (const terminal of terminals || []) {
    const { x, y, solved, role } = terminal;
    const urgent = role === "gate" && !solved;
    const blink = Math.sin(t * (urgent ? 9 : 4)) > 0;
    ctx.save();
    ctx.translate(x, y);
    ctx.fillStyle = "rgba(0, 0, 0, 0.45)";
    ctx.fillRect(-34, 30, 68, 10);
    ctx.fillStyle = "#3a3a46";
    ctx.fillRect(-14, 20, 28, 14);
    ctx.fillRect(-26, 30, 52, 6);
    ctx.fillStyle = "#0a0a10";
    ctx.fillRect(-36, -32, 72, 56);
    ctx.fillStyle = "#c8c8d4";
    ctx.fillRect(-33, -29, 66, 50);
    ctx.fillStyle = "#0c1412";
    ctx.fillRect(-27, -24, 54, 38);
    const ink = solved ? "#4fe08a" : blink ? "#ff4f6a" : "#a02838";
    ctx.fillStyle = ink;
    if (solved) {
      ctx.fillRect(-14, -6, 6, 6);
      ctx.fillRect(-8, 0, 6, 6);
      ctx.fillRect(-2, -6, 6, 6);
      ctx.fillRect(4, -12, 6, 6);
      ctx.fillRect(10, -18, 6, 6);
    } else {
      const width = [40, 26, 34, 18];
      width.forEach((length, row) => {
        ctx.fillRect(-23, -20 + row * 8, length, 4);
      });
    }
    ctx.restore();
  }
}

/** A cable from whoever is plugged in to the terminal they are working on. */
export function drawCables(ctx, players, terminals, now) {
  ctx.save();
  ctx.strokeStyle = "#4fe08a";
  ctx.lineWidth = 2;
  ctx.setLineDash([7, 6]);
  ctx.lineDashOffset = -now / 40;
  for (const terminal of terminals || []) {
    const player = terminal.operator ? players.get(terminal.operator) : null;
    if (!player) continue;
    ctx.beginPath();
    ctx.moveTo(player.x, player.y - 16);
    ctx.lineTo(terminal.x, terminal.y);
    ctx.stroke();
  }
  ctx.restore();
}

export function drawBarriers(ctx, barriers, now) {
  ctx.save();
  ctx.lineCap = "round";
  for (const wall of barriers || []) {
    const fading = Math.min(1, wall.ttl / 0.8);
    const pulse = 0.72 + Math.sin(now / 70) * 0.18;
    ctx.globalAlpha = fading * 0.3;
    ctx.strokeStyle = wall.color;
    ctx.lineWidth = 16;
    ctx.beginPath();
    ctx.moveTo(wall.x1, wall.y1);
    ctx.lineTo(wall.x2, wall.y2);
    ctx.stroke();
    ctx.globalAlpha = fading * pulse;
    ctx.lineWidth = 4;
    ctx.setLineDash([18, 6]);
    ctx.lineDashOffset = now / 30;
    ctx.stroke();
    ctx.setLineDash([]);
  }
  ctx.restore();
}

/** A stopped patch of the world: a pale disc with the mark a debugger leaves. */
export function drawBreakpoints(ctx, zones, now) {
  ctx.save();
  for (const zone of zones || []) {
    const fading = Math.min(1, zone.ttl / 0.5);
    ctx.globalAlpha = fading * 0.2;
    ctx.fillStyle = "#a6e4ff";
    ctx.beginPath();
    ctx.arc(zone.x, zone.y, zone.radius, 0, TAU);
    ctx.fill();
    ctx.globalAlpha = fading * 0.8;
    ctx.strokeStyle = "#d6f0ff";
    ctx.lineWidth = 3;
    ctx.setLineDash([12, 10]);
    ctx.lineDashOffset = now / 60;
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#d6f0ff";
    ctx.fillRect(zone.x - 16, zone.y - 20, 11, 40);
    ctx.fillRect(zone.x + 5, zone.y - 20, 11, 40);
  }
  ctx.restore();
}

/** The golden ring of someone running as root. */
export function drawSudo(ctx, x, y, now) {
  const t = now / 1000;
  ctx.save();
  ctx.translate(x, y);
  ctx.strokeStyle = "#ffd93d";
  ctx.lineWidth = 3;
  ctx.globalAlpha = 0.75 + Math.sin(t * 8) * 0.2;
  ctx.beginPath();
  ctx.arc(0, -8, 40 + Math.sin(t * 6) * 3, 0, TAU);
  ctx.stroke();
  ctx.fillStyle = "#ffd93d";
  for (let index = 0; index < 3; index += 1) {
    ctx.fillRect(-11 + index * 9, -66 + (index === 1 ? -5 : 0), 4, 9);
  }
  ctx.fillRect(-11, -58, 22, 4);
  ctx.restore();
}

/** What a role did to a monster, drawn around it in the monster's own space. */
function drawRoleMarks(ctx, data, radius, t) {
  if (data.frozen) {
    ctx.globalAlpha = 0.34;
    ctx.fillStyle = "#a6e4ff";
    ctx.beginPath();
    ctx.arc(0, -radius * 0.3, radius * 1.15, 0, TAU);
    ctx.fill();
  }
  if (data.hacked) {
    ctx.globalAlpha = 0.9;
    ctx.strokeStyle = "#7fffb0";
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 5]);
    ctx.lineDashOffset = t * 30;
    ctx.beginPath();
    ctx.arc(0, -radius * 0.3, radius * 1.3, 0, TAU);
    ctx.stroke();
    ctx.setLineDash([]);
  }
  if (data.marked) {
    const reach = radius * 1.35;
    ctx.globalAlpha = 0.95;
    ctx.fillStyle = "#ff4f6a";
    for (const [x, y] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
      ctx.fillRect(x * reach - (x > 0 ? 8 : 0), y * reach - radius * 0.3, 8, 2);
      ctx.fillRect(x * reach - (x > 0 ? 2 : 0), y * reach - radius * 0.3 - (y > 0 ? 8 : 0), 2, 8);
    }
  }
  if (data.exposed) {
    ctx.globalAlpha = 1;
    ctx.fillStyle = "#e08cff";
    ctx.fillRect(-2, -radius * 2.1, 4, 11);
    ctx.fillRect(-2, -radius * 2.1 + 13, 4, 4);
  }
  ctx.globalAlpha = 1;
}

export function collectDungeonLights(config, now, lights, camera) {
  const theme = themeOf(config);
  const t = now / 1000;
  const tile = config.tile || 48;
  for (const [x, y] of config.torches || []) {
    if (Math.abs(x - camera.x) > camera.reachX || Math.abs(y - camera.y) > camera.reachY) continue;
    const flicker = 0.92 + Math.sin(t * 11 + x) * 0.08;
    lights.push({ x, y: y + tile, radius: 320 * flicker, color: theme.lampLight, power: 0.9 });
  }
}

export function drawHazards(ctx, hazards, now) {
  if (!hazards?.length) return;
  ctx.save();
  for (const hazard of hazards) {
    const delay = Math.max(0.1, Number(hazard.delay) || 1);
    const ready = Math.max(0, Math.min(1, 1 - (Number(hazard.ttl) || 0) / delay));
    const pulse = 0.5 + Math.sin(now / 70) * 0.5;
    ctx.strokeStyle = hazard.color;
    ctx.fillStyle = hazard.color;
    if (hazard.x2 === null || hazard.x2 === undefined) {
      ctx.globalAlpha = 0.14 + ready * 0.24;
      ctx.beginPath();
      ctx.arc(hazard.x, hazard.y, hazard.radius * ready, 0, TAU);
      ctx.fill();
      ctx.globalAlpha = 0.6 + pulse * 0.3;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(hazard.x, hazard.y, hazard.radius, 0, TAU);
      ctx.stroke();
    } else {
      ctx.lineCap = "butt";
      ctx.globalAlpha = 0.16 + ready * 0.3;
      ctx.lineWidth = hazard.radius;
      ctx.beginPath();
      ctx.moveTo(hazard.x, hazard.y);
      ctx.lineTo(hazard.x2, hazard.y2);
      ctx.stroke();
      ctx.globalAlpha = 0.5 + pulse * 0.4;
      ctx.lineWidth = 2 + ready * 4;
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }
  ctx.restore();
}

export function drawPickups(ctx, pickups, now) {
  if (!pickups?.length) return;
  const t = now / 1000;
  for (const pickup of pickups) {
    const color = pickup.kind === "hp" ? "#ff6b7a" : "#6fa8ff";
    const bob = Math.sin(t * 4 + pickup.id) * 3;
    ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
    ctx.fillRect(pickup.x - 7, pickup.y + 8, 14, 4);
    ctx.fillStyle = "#0d0a14";
    ctx.fillRect(pickup.x - 8, pickup.y - 8 + bob, 16, 16);
    ctx.fillStyle = color;
    ctx.fillRect(pickup.x - 6, pickup.y - 6 + bob, 12, 12);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(pickup.x - 4, pickup.y - 4 + bob, 4, 4);
  }
}

const MOTES = Array.from({ length: 64 }, (_, index) => {
  const random = seededRandom(index * 97 + 13);
  return { x: random(), y: random(), speed: 0.3 + random() * 0.7, phase: random() * TAU, depth: 0.25 + random() * 0.75 };
});
const CLOUD_COUNT = 9;
let cloudSprites = null;

/** Lumps of white at a low resolution: scaled up, they read as pixel-art cloud. */
function bakeClouds() {
  return Array.from({ length: 3 }, (_, index) => {
    const random = seededRandom(index * 41 + 5);
    const canvas = document.createElement("canvas");
    canvas.width = 64;
    canvas.height = 22;
    const ctx = canvas.getContext("2d");
    if (!ctx) return canvas;
    const lump = (fill, drop) => {
      ctx.fillStyle = fill;
      for (let puff = 0; puff < 7; puff += 1) {
        const size = 6 + Math.floor(puff === 3 ? 12 : random() * 8);
        const x = 4 + (puff / 6) * 44 + Math.floor(random() * 3);
        const y = 18 - size + drop;
        ctx.fillRect(x, y, size + 3, size);
      }
    };
    lump("#b8cde4", 2);
    lump("#ffffff", 0);
    return canvas;
  });
}

/**
 * Weather hangs above the room and below the fog, so a room nobody has loaded yet
 * has none. It leans a little against the camera, as anything between it and us would.
 */
export function drawWeather(ctx, config, width, height, now, camera = null) {
  const kind = themeOf(config).weather;
  const t = now / 1000;
  const panX = (camera?.x || 0) * 0.00025;
  const panY = (camera?.y || 0) * 0.00025;
  const wrap = (value) => ((value % 1) + 1) % 1;
  ctx.save();
  if (kind === "clouds") {
    cloudSprites ??= bakeClouds();
    ctx.imageSmoothingEnabled = false;
    for (let index = 0; index < CLOUD_COUNT; index += 1) {
      const mote = MOTES[index];
      const scale = 2.4 + mote.depth * 2.6;
      const sprite = cloudSprites[index % cloudSprites.length];
      const spanX = width + sprite.width * scale * 2;
      const x = wrap(mote.x + t * 0.006 * mote.speed - panX * mote.depth) * spanX - sprite.width * scale;
      const y = wrap(mote.y - panY * mote.depth) * height;
      ctx.globalAlpha = 0.05 + mote.depth * 0.09;
      ctx.drawImage(sprite, x, y, sprite.width * scale, sprite.height * scale);
    }
    ctx.restore();
    return;
  }
  for (const mote of MOTES) {
    const px = (value) => wrap(value - panX * mote.depth) * width;
    const py = (value) => wrap(value - panY * mote.depth) * height;
    if (kind === "hearts") {
      const x = px(mote.x + Math.sin(t * 0.5 + mote.phase) * 0.02);
      const y = py(mote.y - t * 0.03 * mote.speed);
      const size = mote.depth > 0.6 ? 2 : 1;
      ctx.globalAlpha = 0.2 + mote.depth * 0.32;
      ctx.fillStyle = "#ff6b9e";
      ctx.fillRect(x, y, size * 2, size * 2);
      ctx.fillRect(x + size * 3, y, size * 2, size * 2);
      ctx.fillRect(x, y + size * 2, size * 5, size);
      ctx.fillRect(x + size, y + size * 3, size * 3, size);
      ctx.fillRect(x + size * 2, y + size * 4, size, size);
    } else if (kind === "binary") {
      // Warm dust going up from the racks, and the odd spark.
      const x = px(mote.x + Math.sin(t * 0.7 + mote.phase) * 0.012);
      const y = py(mote.y - t * 0.05 * mote.speed);
      const spark = mote.phase > 5.2;
      ctx.globalAlpha = spark ? 0.65 + Math.sin(t * 7 + mote.phase) * 0.3 : 0.1 + mote.depth * 0.14;
      ctx.fillStyle = spark ? "#ffae5c" : "#c8d4cc";
      ctx.fillRect(x, y, spark ? 2 : 3, spark ? 2 : 3);
    } else if (kind === "glitch") {
      // Embers, and now and then the picture slips.
      const x = px(mote.x + Math.sin(t * 0.9 + mote.phase) * 0.01);
      const y = py(mote.y - t * 0.07 * mote.speed);
      ctx.globalAlpha = 0.25 + mote.depth * 0.4;
      ctx.fillStyle = "#ff4f6a";
      ctx.fillRect(x, y, 2, 2);
      const slot = Math.floor(t * 2.2 + mote.phase * 5);
      if (slot % 23 === 0) {
        ctx.globalAlpha = 0.07;
        ctx.fillStyle = slot % 2 ? "#ff4f6a" : "#ffffff";
        ctx.fillRect(0, py(mote.x * 3 + slot * 0.37), width, 2 + mote.depth * 2);
      }
    } else {
      // Twinkling stars, the kind that came with the wallpaper.
      const x = px(mote.x + t * 0.003 * mote.speed);
      const y = py(mote.y);
      const twinkle = Math.max(0, Math.sin(t * (1 + mote.speed * 1.4) + mote.phase));
      if (twinkle <= 0.05) continue;
      ctx.globalAlpha = twinkle * (0.3 + mote.depth * 0.45);
      ctx.fillStyle = "#ffe9a8";
      const arm = twinkle > 0.7 ? 3 : 1;
      ctx.fillRect(x - arm, y, arm * 2 + 1, 1);
      ctx.fillRect(x, y - arm, 1, arm * 2 + 1);
    }
  }
  ctx.restore();
}

/* Half of each creature, drawn from the left edge to its spine; the rest is the
 * mirror image. Symmetry is what makes a small sprite read as a body. */
const SPRITES = {
  popup: {
    colors: { b: "#2f6fe0", r: "#ff5a4f", w: "#f4f4fa", g: "#9aa0b4", k: "#1a1a2a" },
    art: ["bbbbbbbbb", "bbbbbbbbb", "rrbbbbbbb", "wwwwwwwww", "wwkkkwwww", "wwwkkwwww", "wwwwwwwww", "wwwwkkkkk", "wwwkwwwww", "wwwwwwwww", "ggggggggg"],
  },
  cookie: {
    colors: { a: "#d9a86a", b: "#b5834a", c: "#4a2c18", e: "#fff4dc" },
    art: ["....aaaa", "..aaabaa", ".aacaaaa", ".aaaaaba", "aaeeaaaa", "aaecaaaa", "aaaaaaac", ".abaaaaa", ".aaacaaa", "..aaaaab", "....aaaa"],
  },
  banner: {
    colors: { y: "#ffd93d", o: "#ff9a2f", k: "#1a1208", w: "#ffffff" },
    art: ["ooooooooo", "oyyyyyyyy", "oyywwyyyy", "oyywkyyyy", "oyyyyyyyy", "oykyyykyk", "oykykykyk", "oykkykkyk", "oyyyyyyyy", "ooooooooo", "...oo....", "...oo...."],
  },
  like: {
    colors: { a: "#ff6b9e", b: "#d83f78", w: "#ffffff", k: "#3a0f22" },
    art: ["..aaa...", ".aaaaa.a", "aawaaaaa", "aaaaaaaa", "aakwaaaa", "aakkaaaa", "baaaaaaa", ".baaaaaa", "..baaaaa", "...baaaa", "....baaa", ".....baa", "......ba"],
  },
  toxic: {
    colors: { a: "#b5f26a", b: "#7fc040", k: "#1a2c0c", r: "#ff5a4f" },
    art: ["..aaaaaa", ".aaaaaaa", "aaaaaaaa", "aaakkaaa", "aaaarkaa", "aaaaaaaa", "aaaakkkk", "aaakaaaa", ".aaaaaaa", "..bbbbbb", "...bb...", "..bb....", ".b......"],
  },
  moderator: {
    colors: { a: "#a6c6ff", b: "#5a84d0", c: "#2c4a8a", w: "#ffffff" },
    art: ["aaaaaaaa", "abbbbbbb", "abbbbbbb", "abbwwbbb", "abbbwwbb", "abbbbwwb", "abbbbbww", "abbbbwwb", "abbbwwbb", ".abwwbbb", ".abbbbbb", "..abbbbb", "...abbbb", "....abbb", ".....cbb"],
  },
  clickbait: {
    colors: { a: "#ff5a4f", b: "#c02a22", y: "#ffe17a", w: "#ffffff" },
    art: ["......aa", ".....aaa", "....aaay", "...aaaay", "..aaaaay", ".aaaaaay", "aaaaaaay", "bbbaaaay", "...aaaaa", "...aaaay", "...aaaay", "...aaaaa", "...bbbbb"],
  },
  malware: {
    colors: { a: "#ffd27a", b: "#c9973a", g: "#8fe06a", k: "#1a2c0c", w: "#e8ffe0" },
    art: ["aaaa....", "aaaaa...", "bbbbbbbb", "bggggggg", "bgwwgggg", "bgwkwggg", "bgwwgggg", "bggwgggg", "bggwwwgg", "bggggggg", "bbbbbbbb"],
  },
  sync: {
    colors: { a: "#d6f0ff", b: "#6fd6ff", c: "#2f7fb0", k: "#0c2a40" },
    art: ["....aaa.", "...aaaaa", ".aaaaaaa", "aaaaaaaa", "aaakaaaa", "aaakaaaa", "aaaaaaaa", ".bbbbbbb", "...bb..b", "..bbbb.b", "...bb..b", "...bb...", ".....ccc"],
  },
  botnet: {
    colors: { a: "#9fb0c8", b: "#6a7a92", c: "#3a4658", r: "#ff5a4f", k: "#101420" },
    art: ["..r....r", "..c....c", ".aaaaaaa", "abbbbbbb", "abkkkbbb", "abkrkbbb", "abkkkbbb", "abbbbbbb", "abcbcbcb", "abbbbbbb", "aaaaaaaa", ".cc...cc", "ccc...cc"],
  },
  bot: {
    colors: { a: "#c0ccd8", b: "#7a8a9c", k: "#101420", r: "#ff5a4f" },
    art: ["....r...", "...aaaaa", "..aaaaaa", "..akkaaa", "..aaaaaa", "..abbbbb", "..aaaaaa", "...b..bb"],
  },
  ghost404: {
    colors: { a: "#f0ecfa", b: "#b0a8d0", k: "#1c1830" },
    art: [".....aaa", "...aaaaa", "..aaaaaa", "..akakaa", "..aakaaa", "..akakaa", "..aaaaaa", "..aaakkk", "..aaaaaa", "..aaaaaa", "..baabaa", "..b..b.b"],
  },
  cooler: {
    colors: { a: "#d6eef6", b: "#8fd6e8", c: "#3a7a90", k: "#10202a", e: "#ff5a4f" },
    art: ["..cccccc", ".cbbbbbb", "cbbaabbb", "cbbbaabb", "cbbbbaab", "cbaabbbk", "cbbaakkk", "cbbbakke", "cbbbbkkk", "cbbaabbk", ".cbbaabb", "..cccccc"],
  },
  rack: {
    colors: { a: "#3a4046", b: "#23282c", g: "#4fe08a", o: "#ffae5c", r: "#ff5a4f" },
    art: ["aaaaaaaa", "abbbbbbb", "abgbogbb", "abbbbbbb", "abobgbbr", "abbbbbbb", "abgbbbob", "abbbbbbb", "abrbgbbg", "abbbbbbb", "abgbobbb", "abbbbbbb", "aaaaaaaa", ".aa.....", ".aa....."],
  },
  cron: {
    colors: { a: "#c0a06a", b: "#8a6a3a", w: "#f4ecd8", k: "#2a1c0c", r: "#ff5a4f" },
    art: ["....aaaa", "..aabbbb", ".abbwwww", ".abwwwkw", "abwwwwkw", "abwwwwkw", "abwwwwkk", "abwwwwww", "abwwwwww", ".abwwwww", ".abbwwww", "..aabbbb", "....aaaa", "...aa.aa"],
  },
  backup: {
    colors: { a: "#5fc49a", b: "#2f8a64", w: "#f4f4fa", k: "#123a2a", g: "#9aa0b4" },
    art: ["aaaaaaaa", "aabbbggg", "aabbbggg", "aabbbggk", "aabbbggg", "aaaaaaaa", "aaaaaaaa", "aawwwwww", "aawkkkkk", "aawwwwww", "aawkkkkk", "aawwwwww"],
  },
  fork: {
    colors: { a: "#c6b0ff", b: "#8a6cf0", c: "#4f3aa0", e: "#ffffff" },
    art: ["..aa....", "..aa....", ".abba...", "..bb....", "..bb....", "...bb...", "...bbbbb", "...bbecb", "...bbbbb", ".......b", ".......b", "......cc", "......cc"],
  },
  firewall: {
    colors: { a: "#ff8a5c", b: "#c04a2a", c: "#5a2018", y: "#ffe17a", k: "#1a0c08" },
    art: ["...y..y.", "..yyayya", "..aayaay", "bbbcbbbc", "bbbcbbbc", "ccccccc.", "cbbbcbbb", "cbkkcbbb", "cbkkcbbb", "ccccccc.", "bbbcbbbc", "bbbcbbbc", "cccccccc"],
  },
  miner: {
    colors: { a: "#ffd93d", b: "#c9973a", c: "#8a5f18", k: "#2a1c08", w: "#fff4c2" },
    art: ["....aaaa", "..aabbbb", ".abbaaaa", ".abaaaak", "abaaaaak", "abakkaak", "abaaaaak", "abaaaaak", "abaakkak", ".abaaaak", ".abbaaaa", "..aabbbb", "....aaaa"],
  },
  hallucination: {
    colors: { a: "#e8c6ff", b: "#b070e8", c: "#5a2a90", k: "#12061e", w: "#ffffff" },
    art: ["........", "....aaaa", "..aaabbb", ".aabbccc", "aabbckkk", "abbckkww", "abbckkwk", "aabbckkk", ".aabbccc", "..aaabbb", "....aaaa", ".....b.b", "....b..b"],
  },
  bracket: {
    colors: { a: "#d6ecff", b: "#7fc4ff", c: "#2f6fb0", e: "#ffd93d", k: "#0c1a2c" },
    art: [
      ".......bbbb.", ".....bbbaa..", "....bbaa....", "...bbaa.....", "...baa......", "..bbaa......", "..baa....kkk", "..baa...keek", "..baa...keek", "..baa....kkk", "..baa.......", "..baa.......", "..baa.....kk", "..bbaa....kk", "...baa......", "...bbaa.....", "....bbaa....", ".....bbbaa..", ".......bbbb.",
    ],
  },
  scroll: {
    colors: { a: "#d6c6ff", b: "#a78bff", c: "#5a3fb0", k: "#0c0a1c", w: "#ffffff", r: "#ff6b9e" },
    art: [
      "...ccccccccc", "..cbbbbbbbbb", "..cbkkkkkkkk", "..cbkaaaaaaa", "..cbkkkkkkkk", "..cbkrrkkkkk", "..cbkrrkkkkk", "..cbkkkkkkkk", "..cbkaaaaaaa", "..cbkkkkkkkk", "..cbkkkwkkkk", "..cbkkwkkkkk", "..cbkkkwkkkk", "..cbkkkkkkkk", "..cbkaaaaaaa", "..cbkkkkkkkk", "..cbbbbbaaaa", "..cbbbbbbbbb", "...ccccccccc",
    ],
  },
  nullqueen: {
    colors: { a: "#e6d6ff", b: "#a68ad8", c: "#5a4490", d: "#2a1f50", e: "#000000", f: "#ffe17a" },
    art: [
      ".....f...f..", ".....ff.ff.f", ".....fffffff", ".....aaaaaaa", "....aaaaaaaa", "....aaeeeaaa", "....aaeeeaaa", "....aaaaaaaa", ".....aaaaddd", "....bbaaaaaa", "...bbbbbbbbb", "..bbbcbbbbbb", ".bbbccbbbbbb", ".bbcccbbbcbb", "..bcccbbbcbb", "...ccbbbcccb", "...cbbbbcccc", "..cbbbcccccc", ".cbbcccccccc", "cddddddddddd",
    ],
  },
  indexer: {
    colors: { a: "#ffe17a", b: "#c9a24f", c: "#7a5a2c", d: "#3a2a14", e: "#ff5a4f", f: "#ffffff" },
    art: [
      ".......bbbbb", "......baaaab", "......baeeab", "......baeeab", "......bbbbbb", "..aa.ccbbbbb", ".abba.cbbbbb", ".abbabbbbbbb", "..aabbcccbbb", "...bbcdddcbb", "...bbcdfdcbb", "...bbcdddcbb", "...bbbcccbbb", "...bbbbbbbbb", "..aa.cbbbbbb", ".abba.cbbbbb", ".abba.cc.bbb", "..aa...c.ccc", ".......c.ddd",
    ],
  },
  pgt: {
    colors: { a: "#f0f0f6", b: "#c0c0d0", c: "#7a7a90", k: "#14141c", r: "#ff4f6a", w: "#ffffff" },
    art: [
      "...........r", "...........c", ".......ccccc", ".....ccaaaaa", "....caaaaaaa", "...caaaaaaaa", "...caakkkkaa", "...caakrrkaa", "...caakrrkaa", "...caakkkkaa", "...caaaaaaaa", "...caaaaaaaa", "...caakaaaaa", "...caaakkkkk", "....caaaaaaa", ".....ccccccc", "...bbaaaaaaa", "..bbaacaaaaa", "..baaaaaaaaa", "...cc...cccc",
    ],
  },
};

// Quest creatures: each belongs to one stage's problem.
Object.assign(SPRITES, {
  worker: {
    colors: { g: "#7fe0a8", d: "#3a9a68", k: "#0c1a12", w: "#ffffff" },
    art: ["...g....", "...gg...", "..gggggg", ".gggwwgg", ".ggwkwgg", "gggwwggg", "gggggggg", "dggggggg", ".ddggggg", "..d..d.g", "..d...d."],
  },
  leak: {
    colors: { a: "#5fd0ff", b: "#2f8ab8", c: "#bff0ff", k: "#06202c" },
    art: ["....aaaa", "..aaaaaa", ".aacaaaa", ".acaaaaa", "aaaakkaa", "aaaakkaa", "aaaaaaaa", "aaaaaaab", ".aaaaabb", ".baaaabb", "..bbbbbb", "...b.b.b"],
  },
  phish: {
    colors: { a: "#d9a441", b: "#8a5a2a", c: "#5a3a18", w: "#ffffff", r: "#ff5a4f", k: "#1a0c08" },
    art: ["bbbbbbbb", "baaaaaaa", "bkkkkkkk", "bwkwkwkw", "bkkrkkkk", "bwkwkwkw", "bkkkkkkk", "baaaaaaa", "bbbbbbbb", "bbbbaacc", ".cc....c"],
  },
});

Object.assign(SPRITES, {
  ratebot: {
    colors: { a: "#c86bff", b: "#7a3aa8", k: "#14081e", r: "#ff5a4f" },
    art: ["....b...", "...aaaaa", "..aaaaaa", "..akkaaa", "..arkaaa", "..aaaaaa", "...bbbbb", "....b..b"],
  },
  hotrack: {
    colors: { a: "#4a3a30", b: "#2c2320", g: "#ffae5c", o: "#ff7a3c", r: "#ff5a4f" },
    art: SPRITES.rack.art,
  },
  failtest: {
    colors: { r: "#ff4f6a", k: "#1a0a10" },
    art: ["rrkkkkkk", "krrkkkkk", "kkrrkkkk", "kkkrrkkk", "kkkkrrkk", "kkkkkrrr", "kkkkkrrr", "kkkkrrkk", "kkkrrkkk", "kkrrkkkk", "krrkkkkk", "rrkkkkkk"],
  },
  letter: {
    colors: { w: "#f4f2fa", g: "#a9a6b8" },
    art: ["wwwwwwww", "gwwwwwww", "wgwwwwww", "wwgwwwww", "wwwgwwww", "wwwwgwww", "wwwwwggg", "wwwwwwww", "wwwwwwww"],
  },
});

Object.assign(SPRITES, {
  flashintro: {
    colors: { k: "#1a1208", r: "#e8402f", o: "#ff9a2f", w: "#f4f4fa", g: "#7a7a88" },
    art: [
      "gggggggggggg", "gkkkkkkkkkkk", "gkkkkrrkkkkk", "gkkkrrrrkkkk", "gkkkrroorkkk", "gkkrrkkoorkk",
      "gkkrrkkkrrkk", "gkkkrrkkrrkk", "gkkkkrrrrkkk", "gkkkkkrrkkkk", "gkkkkkkkkkkk", "ggggggggggggg",
      "gwwwwwwwwkkk", "gooooowwwkkk", "ggggggggggggg",
    ],
  },
  influencer: {
    colors: { s: "#f2c9a0", h: "#ff6b9e", k: "#1a0a14", w: "#ffffff", p: "#c23d78", y: "#ffd93d" },
    art: [
      "...yy..hhhh.", "...yy.hhhhhh", "......hhhhhh", ".....hhsssss", ".....hsksksk", ".....hssssss",
      ".....hssswww", "......ssssss", "....pppppppp", "...ppppppppp", "..ppwppppppp", "..ppppppppps", "...ppppppps", "...pppppppp", "...pp....pp",
    ],
  },
  follower: {
    colors: { a: "#ffb3cf", b: "#d97ba0", k: "#3a0f22" },
    art: ["...aaaa", "..aaaaa", ".aakaak", ".aaaaaa", "..aaaaa", "...bbbb", "..bbbbb", "..bb.bb"],
  },
  duplicate: {
    colors: { a: "#9fd4ff", b: "#5f9fd8", w: "#eef6ff", k: "#12283c" },
    art: [
      ".....bbbbbbb", "....bwwwwwwb", "...bbwwwwwwb", "..aaaaaaaaab", "..awwwwwwwab", "..awkkwkkwab",
      "..awwwwwwwab", "..awkkkkkwab", "..awwwwwwwab", "..awkkwkkwab", "..awwwwwwwab", "..aaaaaaaaab", "...bbbbbbbbb",
    ],
  },
  hotserver: {
    colors: { a: "#4a3a30", b: "#2c2320", o: "#ff7a3c", y: "#ffd27a", r: "#ff4f3a" },
    art: [
      "...y..o..y..", "..o..yy..o..", "..aaaaaaaaaa", "..abbbbbbbba", "..abrrbbyyba", "..abbbbbbbba",
      "..aaaaaaaaaa", "..abbbbbbbba", "..aboobboora", "..abbbbbbbba", "..aaaaaaaaaa", "..abbbbbbbba",
      "..abyybbrrba", "..abbbbbbbba", "..aaaaaaaaaa", "..bb......bb",
    ],
  },
  reviewer: {
    colors: { s: "#e6c9a0", h: "#3a3a4a", k: "#10101a", w: "#ffffff", y: "#ffe07a", c: "#2a2a3a" },
    art: [
      "......hhhhhh", ".....hhhhhhh", ".....hssssss", ".....kkkskkk", ".....kwkkkwk", ".....hsssssk",
      ".....hsskkss", "......ssssss", "....cccccccc", "...ccccyyccc", "..cccccyyccc", "..ss.ccccccc", "..yy.ccccccc", "..yy.cccccc.", ".....cc..cc.",
    ],
  },
  clone: {
    colors: { a: "#9fe8ff", b: "#5fb8d8", w: "#f0fcff", k: "#123040" },
    art: ["....aaa.", "...aaaa.", "..aaaaaa", ".bbbbbbb", "....wwww", "....wkwk", "....wwww", "..aaaaaa", ".aaaaaaa", ".aaaaaaa", "..aaaaaa", "..aa..aa"],
  },
  dummy: {
    colors: { a: "#c9b48a", b: "#8f7c58", r: "#e8402f", w: "#f4f2e8" },
    art: ["....aaaa", "...aaaaa", "...aaaaa", "....aaaa", "bbb.bbbb", "bbbbaaaa", "...aaaaa", "...awwww", "...awrrw", "...awwww", "...aaaaa", "....bbbb", "....bbbb", "...bbbbb"],
  },
  dummy_walker: {
    colors: { a: "#8ac9b4", b: "#588f7c", r: "#e8402f", w: "#f4f2e8", k: "#333333" },
    art: ["....aaaa", "...aaaaa", "...aaaaa", "....aaaa", "bbb.bbbb", "bbbbaaaa", "...aaaaa", "...awwww", "...awrrw", "...awwww", "...aaaaa", "....bbbb", "...kkkkk", "..k.k.k."],
  },
});

// Her copies must not be told apart by eye: that is what enemies() is for.
SPRITES.nullecho = SPRITES.nullqueen;
SPRITES.dupe = SPRITES.duplicate;

const spriteCache = new Map();

function bakeSprite(kind) {
  const entry = SPRITES[kind] || SPRITES.popup;
  const rows = entry.art;
  const half = Math.max(...rows.map((row) => row.length));
  const canvas = document.createElement("canvas");
  canvas.width = half * 2;
  canvas.height = rows.length;
  const flash = document.createElement("canvas");
  flash.width = canvas.width;
  flash.height = canvas.height;
  const ctx = canvas.getContext("2d");
  const flashCtx = flash.getContext("2d");
  flashCtx.fillStyle = "#ffffff";
  rows.forEach((row, y) => {
    // Every row ends at the spine, so short rows are padded on the outside.
    const padded = row.padStart(half, ".");
    for (let x = 0; x < half; x += 1) {
      const color = entry.colors[padded[x]];
      if (!color) continue;
      ctx.fillStyle = color;
      ctx.fillRect(x, y, 1, 1);
      ctx.fillRect(half * 2 - 1 - x, y, 1, 1);
      flashCtx.fillRect(x, y, 1, 1);
      flashCtx.fillRect(half * 2 - 1 - x, y, 1, 1);
    }
  });
  // A dark rim all round, so that nobody gets lost against a busy floor.
  const outline = document.createElement("canvas");
  outline.width = canvas.width + 2;
  outline.height = canvas.height + 2;
  const outlineCtx = outline.getContext("2d");
  for (const [x, y] of [[0, 1], [2, 1], [1, 0], [1, 2]]) outlineCtx.drawImage(flash, x, y);
  outlineCtx.globalCompositeOperation = "source-in";
  outlineCtx.fillStyle = "#07060c";
  outlineCtx.fillRect(0, 0, outline.width, outline.height);
  const sprite = { canvas, flash, outline, width: canvas.width, height: canvas.height };
  spriteCache.set(kind, sprite);
  return sprite;
}

function spriteFor(kind) {
  return spriteCache.get(kind) || bakeSprite(kind);
}

/** What a creature is made of, for the bits that fly off when it goes. */
export function spriteColors(kind) {
  return Object.values((SPRITES[kind] || SPRITES.popup).colors);
}

export function hasSprite(kind) {
  return Boolean(SPRITES[kind]);
}

/** A creature for the handbook, in a square; someone not yet met is only an outline. */
export function paintSprite(canvas, kind, locked = false) {
  const sprite = spriteFor(kind);
  const size = Math.max(sprite.width, sprite.height) + 2;
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.imageSmoothingEnabled = false;
  const x = Math.floor((size - sprite.width) / 2);
  const y = Math.floor((size - sprite.height) / 2);
  ctx.drawImage(locked ? sprite.flash : sprite.canvas, x, y);
  if (locked) {
    ctx.globalCompositeOperation = "source-in";
    ctx.fillStyle = "#2a2d3a";
    ctx.fillRect(0, 0, size, size);
    ctx.globalCompositeOperation = "source-over";
  }
}

const ARRIVAL_TIME = 550;

/** Draw one monster at its feet. `visual` carries the smoothed position and flashes. */
/** The bubble a boss hides in while its bug stands unrepaired. */
function drawGateShield(ctx, radius, t) {
  const reach = radius * 1.75 + Math.sin(t * 5) * 3;
  ctx.globalAlpha = 0.16;
  ctx.fillStyle = "#ff4f6a";
  ctx.beginPath();
  ctx.arc(0, -radius * 0.4, reach, 0, TAU);
  ctx.fill();
  ctx.globalAlpha = 0.85;
  ctx.strokeStyle = "#ff8fa0";
  ctx.lineWidth = 3;
  ctx.setLineDash([14, 9]);
  ctx.lineDashOffset = t * 40;
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.globalAlpha = 1;
}

const ELITE_AURA = {
  legacy: "#c9a26b",
  hotfix: "#7fe0a8",
  fork: "#b18cff",
  prod: "#ff7a5a",
  async: "#6fd3ff",
  deprecated: "#ffd86b",
};

/** An elite is the same bug with a ring around it: the ring is how you notice in a crowd. */
function drawEliteAura(ctx, kind, radius, t) {
  ctx.save();
  ctx.globalAlpha = 0.55 + Math.sin(t * 5) * 0.2;
  ctx.strokeStyle = ELITE_AURA[kind] || "#ffffff";
  ctx.lineWidth = 2.5;
  ctx.setLineDash([radius * 0.5, radius * 0.3]);
  ctx.lineDashOffset = -t * 30;
  ctx.beginPath();
  ctx.arc(0, -radius * 0.2, radius * 1.45, 0, TAU);
  ctx.stroke();
  ctx.restore();
}

export function drawMonster(ctx, visual, now) {
  const data = visual.data;
  const radius = Number(data.r) || 18;
  const sprite = spriteFor(data.kind);
  const t = now / 1000;
  const scale = (radius * 2.9) / Math.max(sprite.width, sprite.height);
  const width = sprite.width * scale;
  const height = sprite.height * scale;
  const state = data.state;
  const walking = (visual.pace || 0) > 14 && state !== "dash";
  const beat = t * 9 + data.id;
  const hop = walking ? Math.abs(Math.sin(beat)) * radius * 0.2 : 0;
  // Breathing when still, and a little give every time it lands.
  const squash = walking ? 1 - Math.abs(Math.cos(beat)) * 0.07 : 1 + Math.sin(t * 2.6 + data.id) * 0.025;
  const lean = Math.max(-0.18, Math.min(0.18, (visual.dirX || 0) / 560));
  const shaking = state === "aim" || state === "windup" || state === "slam" || state === "deploy";
  const jitter = shaking ? Math.sin(t * 60) * 2 : 0;
  const stretch = state === "dash" ? 1.14 : 1;
  const flip = Math.cos(Number(data.aim) || 0) < 0 ? -1 : 1;
  const feet = radius * 0.86;
  const age = (now - (visual.born ?? now)) / ARRIVAL_TIME;
  const arriving = Boolean(data.arriving) && age < 1;

  ctx.save();
  ctx.translate(visual.x + jitter, visual.y);
  if (radius >= 34) {
    // Something this big lights the floor it stands on.
    const pulse = 0.2 + Math.sin(t * 2.4) * 0.06;
    const glow = ctx.createRadialGradient(0, feet * 0.8, 2, 0, feet * 0.8, radius * 2.1);
    glow.addColorStop(0, `rgba(255, 90, 110, ${pulse})`);
    glow.addColorStop(1, "rgba(255, 90, 110, 0)");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.ellipse(0, feet * 0.8, radius * 2.1, radius * 1.2, 0, 0, TAU);
    ctx.fill();
  }
  ctx.fillStyle = `rgba(0, 0, 0, ${0.42 - (hop / (radius * 0.2 + 1)) * 0.12})`;
  ctx.beginPath();
  ctx.ellipse(0, radius * 0.72, radius * (0.95 - hop * 0.008), radius * 0.36, 0, 0, TAU);
  ctx.fill();

  ctx.save();
  ctx.translate(0, feet - hop);
  ctx.rotate(lean);
  ctx.scale(flip * (stretch + (1 - squash) * 0.6), squash);
  ctx.imageSmoothingEnabled = false;
  const left = -width / 2;
  const top = -height;
  if (arriving) {
    // It loads from the feet up, like everything else on this network.
    const shown = Math.max(1, Math.ceil(sprite.height * Math.max(0.04, age)));
    const part = (shown / sprite.height) * height;
    ctx.drawImage(sprite.canvas, 0, sprite.height - shown, sprite.width, shown, left, -part, width, part);
    ctx.fillStyle = "#9ff0c0";
    ctx.globalAlpha = 0.8 * (1 - age);
    ctx.fillRect(left - 3, -part - 2, width + 6, 3);
    ctx.globalAlpha = 1;
  } else {
    ctx.drawImage(
      sprite.outline,
      left - scale,
      top - scale,
      (sprite.width + 2) * scale,
      (sprite.height + 2) * scale,
    );
    ctx.drawImage(sprite.canvas, left, top, width, height);
    const flashing = Math.max(visual.hurt * 3.4, shaking ? 0.35 : 0, state === "dizzy" ? 0.25 : 0);
    if (flashing > 0) {
      ctx.globalAlpha = Math.min(0.9, flashing);
      ctx.drawImage(sprite.flash, left, top, width, height);
      ctx.globalAlpha = 1;
    }
  }
  ctx.restore();

  ctx.scale(flip, 1);
  if (data.elite) drawEliteAura(ctx, data.elite, radius, t);
  if (data.shielded) drawGateShield(ctx, radius, t);
  drawRoleMarks(ctx, data, radius, t);
  ctx.restore();

  if (state === "deploy") {
    ctx.strokeStyle = "#ff4f6a";
    ctx.lineWidth = 3;
    ctx.globalAlpha = 0.5 + Math.sin(t * 14) * 0.4;
    for (const reach of [1.6, 2.3]) {
      ctx.beginPath();
      ctx.arc(visual.x, visual.y, radius * reach + Math.sin(t * 9) * 5, 0, TAU);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }
  if (data.slow) {
    ctx.strokeStyle = "rgba(124, 231, 255, 0.6)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(visual.x, visual.y, radius + 6, 0, TAU);
    ctx.stroke();
  }
}

export function drawMonsterBar(ctx, x, y, width, ratio) {
  ctx.fillStyle = "rgba(4, 6, 10, 0.85)";
  ctx.fillRect(x - width / 2, y, width, 4);
  ctx.fillStyle = "#e76972";
  ctx.fillRect(x - width / 2 + 1, y + 1, Math.max(0.5, (width - 2) * ratio), 2);
}
