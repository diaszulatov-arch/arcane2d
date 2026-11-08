/* What a stage's problem looks like: machines, lost files, circles, plates,
 * the odd rooms, and the green binary over everything nobody has loaded yet. */

const TAU = Math.PI * 2;
const FOG_SCALE = 2;
const FOG_COLOR = "#020b06";
const FOG_GREEN = "61, 255, 122";
const DIGIT_ART = [
  ["###", "#.#", "#.#", "#.#", "###"],
  [".#.", "##.", ".#.", ".#.", "###"],
];
const DIGIT_W = 3;
const DIGIT_H = 5;
const CELL_W = 5;
const CELL_H = 7;
const FIELD_COLS = 48;
const FIELD_ROWS = 34;
const RAIN_SHADES = ["#a6e8bd", "#5fd08f", "#32be6a", "#229c52", "#197a40", "#125e31", "#0d4624"];
const CYAN = "#7fe0ee";
const GREEN = "#4fe08a";
const RED = "#ff5a4f";
const GOLD = "#ffd27a";

const DEVICES = {
  nginx: { color: "#4fe08a", glyph: "N", shape: "rack" },
  db: { color: "#6fb6ff", glyph: "SQL", shape: "db" },
  dns: { color: "#7fe0ee", glyph: "DNS", shape: "rack" },
  balancer: { color: "#ffb347", glyph: "LB", shape: "rack" },
  gateway: { color: "#c86bff", glyph: "API", shape: "rack" },
  edge: { color: "#ffd93d", glyph: "CDN", shape: "rack" },
  bucket: { color: "#ff9a2f", glyph: "S3", shape: "bucket" },
  compose: { color: "#3aa7ff", glyph: "DKR", shape: "rack" },
  git: { color: "#f05033", glyph: "git", shape: "rack" },
  monitor: { color: "#ff6a7a", glyph: "°C", shape: "screen" },
  top: { color: "#5fd0ff", glyph: "PID", shape: "screen" },
  rack: { color: "#ffae5c", glyph: "42", shape: "rack" },
  journal: { color: "#b9a7e8", glyph: "LOG", shape: "screen" },
  ci: { color: "#4fe08a", glyph: "CI", shape: "rack" },
  filter: { color: "#ff4f6a", glyph: "SPAM", shape: "rack" },
};

/* Mirrored pixel art, the same convention as the bestiary. */
const PEOPLE = {
  request: {
    colors: { w: "#f4f8ff", b: "#4f8fff", k: "#0c1428", c: "#7fe0ee" },
    art: ["....cccc", "...cwwww", "..cwwwww", ".cwwkwww", ".cwwkwww", "cbbbbbbb", "cwwwwwww", "cwwwbwww", "cwwwwbbb", ".cwwwwww", "..cccccc", "...c...c"],
  },
  user: {
    colors: { s: "#f0c9a0", h: "#6a4a2a", b: "#4fd08a", k: "#1a1a22" },
    art: ["..hh", ".hhh", ".sss", ".sks", ".sss", "..ss", ".bbb", "bbbb", "sbbb", ".bbb", ".k.k", ".k.k"],
  },
  admin: {
    colors: { s: "#f0c9a0", h: "#4a3a2a", g: "#5a6070", k: "#1a1a22", m: "#c06a3a", b: "#3a6ab0" },
    art: ["..hhh", ".hhhh", ".ssss", ".skss", ".ssss", ".hhhh", "..hhh", "ggggg", "sgggb", "sgggg", "mgggg", ".kkkk", ".kk.k", ".kk.k"],
  },
  webmaster: {
    colors: { s: "#f0c9a0", h: "#3a2a1a", g: "#14161c", b: "#b89a5a", k: "#2a2a34" },
    art: ["..hhh", ".hhhh", ".ssss", ".gggs", ".ssss", "..sss", ".bbbb", "bbbbb", "sbbbb", ".bbbb", ".kkkk", ".kk.k", ".kk.k"],
  },
  gosha: {
    colors: { s: "#f0c9a0", h: "#c98a3a", g: "#4fd08a", k: "#2a2a34", e: "#14161c" },
    art: ["h.h.h", ".hhhh", ".ssss", ".sess", ".ssss", "..sss", ".gggg", "ggggg", "sgggg", ".gggg", ".kkkk", ".kk.k", ".kk.k"],
  },
  senya: {
    colors: { s: "#f0c9a0", c: "#ff6ec7", b: "#7f5fff", k: "#2a2a34", e: "#14161c" },
    art: ["..ccc", ".cccc", "ccccc", ".sess", ".ssss", "..sss", ".bbbb", "bbbbb", "sbbbb", ".bbbb", ".kkkk", ".kk.k", ".kk.k"],
  },
  petrovich: {
    colors: { s: "#e8c0a0", w: "#c8ccd4", u: "#3a4a6a", k: "#22242c", e: "#14161c" },
    art: ["..www", ".wwww", ".ssss", ".sess", ".wwww", ".wwww", "..www", ".uuuu", "uuuuu", "suuuu", ".kkkk", ".kk.k", ".kk.k"],
  },
  babka: {
    colors: { s: "#f0c9a0", f: "#d04a6a", d: "#a05ac0", k: "#2a2a34", e: "#14161c" },
    art: ["..fff", ".ffff", "fffss", "ffess", ".fsss", "..sss", ".dddd", "ddddd", "sdddd", "ddddd", "ddddd", ".kk.k"],
  },
  luba: {
    colors: { s: "#f0c9a0", h: "#7a5a3a", w: "#f4f8ff", a: "#5a9ad0", k: "#2a2a34", e: "#14161c" },
    art: ["..hhh", ".wwww", ".ssss", ".sess", ".ssss", "..sss", ".aaaa", "aaaaa", "saaaa", "aaaaa", ".aaaa", ".kk.k", ".kk.k"],
  },
  maria: {
    colors: { s: "#f0d0b0", w: "#d8dce4", p: "#8a7a9a", k: "#2a2a34", e: "#14161c" },
    art: ["...ww", "..www", ".wwww", ".ssss", ".sess", ".ssss", "..sss", ".pppp", "ppppp", "spppp", "ppppp", ".kk.k", ".kk.k"],
  },
  guard: {
    colors: { s: "#f0c9a0", n: "#2a3a5a", y: "#ffd27a", k: "#1a1a22", e: "#14161c" },
    art: ["..nnn", ".nnnn", "nnnnn", ".sess", ".ssss", "..sss", ".nnnn", "nnynn", "snnnn", ".nnnn", ".kkkk", ".kk.k", ".kk.k"],
  },
  miner: {
    colors: { s: "#f0c9a0", y: "#ffd93d", w: "#e8e8e8", o: "#7a5a3a", k: "#2a2a34", e: "#14161c" },
    art: ["..yyy", ".yyyy", ".ssss", ".sess", ".wwww", ".wwww", "..www", ".oooo", "ooooo", "soooo", ".oooo", ".kk.k", ".kk.k"],
  },
};

const peopleCache = new Map();

function bakePerson(kind) {
  const entry = PEOPLE[kind] || PEOPLE.request;
  const half = Math.max(...entry.art.map((row) => row.length));
  const canvas = document.createElement("canvas");
  canvas.width = half * 2;
  canvas.height = entry.art.length;
  const ctx = canvas.getContext("2d");
  entry.art.forEach((row, y) => {
    const padded = row.padStart(half, ".");
    for (let x = 0; x < half; x += 1) {
      const color = entry.colors[padded[x]];
      if (!color) continue;
      ctx.fillStyle = color;
      ctx.fillRect(x, y, 1, 1);
      ctx.fillRect(half * 2 - 1 - x, y, 1, 1);
    }
  });
  peopleCache.set(kind, canvas);
  return canvas;
}

function personSprite(kind) {
  return peopleCache.get(kind) || bakePerson(kind);
}

// ------------------------------------------------------------------- fog
/** Every tile somebody has loaded: rooms with their walls, and the halls beside them. */
export function seenMask(config, seen) {
  const rows = config?.tiles || [];
  const width = rows[0]?.length || 1;
  const height = rows.length || 1;
  const mask = new Uint8Array(width * height);
  const open = (x, y, w, h) => {
    for (let ty = Math.max(0, y); ty < Math.min(height, y + h); ty += 1) {
      for (let tx = Math.max(0, x); tx < Math.min(width, x + w); tx += 1) {
        mask[ty * width + tx] = 1;
      }
    }
  };
  const rooms = config?.rooms || [];
  for (const index of seen) {
    const room = rooms[index];
    if (room) open(room.x - 1, room.y - 2, room.w + 2, room.h + 3);
  }
  for (const [x, y, w, h, a, b] of config?.corridors || []) {
    if (seen.has(a) || seen.has(b)) open(x - 1, y - 1, w + 2, h + 2);
  }
  return { mask, width, height };
}

export function isSeen(fog, x, y, tile) {
  if (!fog) return true;
  const tx = Math.floor(x / tile);
  const ty = Math.floor(y / tile);
  if (tx < 0 || ty < 0 || tx >= fog.width || ty >= fog.height) return false;
  return fog.mask[ty * fog.width + tx] === 1;
}

/** The fog is cut along this mask: opaque wherever somebody has already been. */
export function buildFog(config, seen) {
  const { mask, width, height } = seenMask(config, seen);
  const canvas = document.createElement("canvas");
  canvas.width = width * FOG_SCALE;
  canvas.height = height * FOG_SCALE;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "#000000";
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        if (mask[y * width + x]) ctx.fillRect(x * FOG_SCALE, y * FOG_SCALE, FOG_SCALE, FOG_SCALE);
      }
    }
  }
  return { canvas, mask, width, height };
}

function paintDigit(ctx, digit, x, y) {
  DIGIT_ART[digit].forEach((row, dy) => {
    for (let dx = 0; dx < DIGIT_W; dx += 1) {
      if (row[dx] === "#") ctx.fillRect(x + dx, y + dy, 1, 1);
    }
  });
}

let digitField = null;
let fieldPattern = null;
let rainAtlas = null;
let fogLayer = null;

/** A sheet of dim digits that repeats across the whole fog. */
function bakeDigitField() {
  const canvas = document.createElement("canvas");
  canvas.width = FIELD_COLS * CELL_W;
  canvas.height = FIELD_ROWS * CELL_H;
  const ctx = canvas.getContext("2d");
  for (let row = 0; row < FIELD_ROWS; row += 1) {
    for (let col = 0; col < FIELD_COLS; col += 1) {
      const roll = Math.random();
      if (roll < 0.1) continue;
      let alpha = 0.13 + Math.random() * 0.09;
      if (roll > 0.97) alpha = 0.42 + Math.random() * 0.14;
      else if (roll > 0.72) alpha = 0.23 + Math.random() * 0.1;
      ctx.fillStyle = `rgba(${FOG_GREEN}, ${alpha})`;
      paintDigit(ctx, Math.random() < 0.5 ? 0 : 1, col * CELL_W, row * CELL_H);
    }
  }
  return canvas;
}

/** Both digits in every shade of a falling stream, from its head to its tail. */
function bakeRainAtlas() {
  const canvas = document.createElement("canvas");
  canvas.width = DIGIT_W * 2;
  canvas.height = DIGIT_H * RAIN_SHADES.length;
  const ctx = canvas.getContext("2d");
  RAIN_SHADES.forEach((shade, index) => {
    ctx.fillStyle = shade;
    paintDigit(ctx, 0, 0, index * DIGIT_H);
    paintDigit(ctx, 1, DIGIT_W, index * DIGIT_H);
  });
  return canvas;
}

function mixBits(a, b) {
  let hash = Math.imul(a, 73856093) ^ Math.imul(b, 19349663);
  hash ^= hash >>> 13;
  hash = Math.imul(hash, 1274126177);
  return (hash ^ (hash >>> 16)) >>> 0;
}

/** Streams of bright digits falling through the fog, on one column in three. */
function drawRain(layer, originX, originY, width, height, t) {
  rainAtlas ??= bakeRainAtlas();
  const firstRow = Math.floor(-originY / CELL_H);
  const lastRow = Math.floor((height - originY) / CELL_H);
  const lastCol = Math.floor((width - originX) / CELL_W);
  const flicker = Math.floor(t * 4);
  layer.fillStyle = FOG_COLOR;
  for (let col = Math.floor(-originX / CELL_W); col <= lastCol; col += 1) {
    const seed = mixBits(col, 7);
    if (seed % 3) continue;
    const speed = 5 + (seed >>> 4) % 9;
    const length = 7 + (seed >>> 9) % 12;
    const gap = 40 + (seed >>> 14) % 50;
    const head = Math.floor(t * speed) + (seed >>> 18) % gap;
    const x = originX + col * CELL_W;
    const lastStream = Math.floor((lastRow + length - head) / gap);
    for (let stream = Math.ceil((firstRow - head) / gap); stream <= lastStream; stream += 1) {
      const front = head + stream * gap;
      for (let back = 0; back < length; back += 1) {
        const row = front - back;
        if (row < firstRow || row > lastRow) continue;
        const cell = mixBits(col, row);
        const digit = (cell ^ (mixBits(cell, flicker) % 5 === 0 ? 1 : 0)) & 1;
        const shade = Math.floor((back / length) * RAIN_SHADES.length);
        const y = originY + row * CELL_H;
        layer.fillRect(x, y, DIGIT_W, DIGIT_H);
        layer.drawImage(
          rainAtlas, digit * DIGIT_W, shade * DIGIT_H, DIGIT_W, DIGIT_H, x, y, DIGIT_W, DIGIT_H,
        );
      }
    }
  }
}

/**
 * The digits are laid out in canvas pixels so they stay crisp at any zoom, but
 * anchored to the world so they do not swim as the camera moves.  ``view`` says
 * where world (0, 0) falls on this canvas and how large a world unit is there.
 */
export function drawFog(ctx, fog, config, view, now) {
  if (!fog) return;
  const { width, height } = ctx.canvas;
  if (!fogLayer) fogLayer = document.createElement("canvas").getContext("2d");
  if (!fogLayer) return;
  if (fogLayer.canvas.width !== width || fogLayer.canvas.height !== height) {
    fogLayer.canvas.width = width;
    fogLayer.canvas.height = height;
  }
  digitField ??= bakeDigitField();
  fieldPattern ??= fogLayer.createPattern(digitField, "repeat");
  const layer = fogLayer;
  const originX = Math.round(view.x);
  const originY = Math.round(view.y);
  const fieldW = digitField.width;
  const fieldH = digitField.height;

  layer.setTransform(1, 0, 0, 1, 0, 0);
  layer.globalCompositeOperation = "source-over";
  layer.imageSmoothingEnabled = false;
  layer.fillStyle = FOG_COLOR;
  layer.fillRect(0, 0, width, height);
  layer.setTransform(
    1, 0, 0, 1,
    ((originX % fieldW) + fieldW) % fieldW,
    ((originY % fieldH) + fieldH) % fieldH,
  );
  layer.fillStyle = fieldPattern;
  layer.fillRect(-fieldW, -fieldH, width + fieldW, height + fieldH);
  layer.setTransform(1, 0, 0, 1, 0, 0);
  if (view.rain) drawRain(layer, originX, originY, width, height, now / 1000);

  const tile = config.tile || 48;
  layer.globalCompositeOperation = "destination-out";
  layer.imageSmoothingEnabled = true;
  layer.drawImage(
    fog.canvas, view.x, view.y, fog.width * tile * view.scale, fog.height * tile * view.scale,
  );
  layer.globalCompositeOperation = "source-over";

  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(layer.canvas, 0, 0);
  ctx.restore();
}

export function buildFoggedMinimap(config, fog) {
  const rows = config?.tiles || [];
  const canvas = document.createElement("canvas");
  canvas.width = rows[0]?.length || 1;
  canvas.height = rows.length || 1;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;
  rows.forEach((row, y) => {
    for (let x = 0; x < row.length; x += 1) {
      if (row[x] !== ".") continue;
      if (fog && !fog.mask[y * fog.width + x]) continue;
      ctx.fillStyle = "rgba(220, 215, 235, 0.42)";
      ctx.fillRect(x, y, 1, 1);
    }
  });
  const tile = 1;
  for (const room of config.rooms || []) {
    if (!room.dark) continue;
    ctx.fillStyle = "rgba(10, 8, 18, 0.5)";
    ctx.fillRect(room.x * tile, room.y * tile, room.w * tile, room.h * tile);
  }
  return canvas;
}

export function darkRooms(config) {
  return (config?.rooms || []).filter((room) => room.dark);
}

// ------------------------------------------------------------- the labels
/* The world is drawn in low resolution, and these have to be read, sometimes to
 * the letter: they are queued during the world pass and drawn on the screen. */
const pendingLabels = [];

export function label(_ctx, text, x, y, color = "#e8e4f4", size = 13) {
  pendingLabels.push({ text, x, y, color, size });
}

export function flushLabels(ctx, toScreen, zoom, visible) {
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (const entry of pendingLabels) {
    if (!visible(entry.x, entry.y)) continue;
    const { x, y } = toScreen(entry.x, entry.y);
    const px = Math.max(13, Math.round(entry.size * zoom));
    ctx.font = `${px}px "Cozette", "JetBrains Mono", ui-monospace, monospace`;
    const width = ctx.measureText(entry.text).width + 10;
    ctx.fillStyle = "rgba(6, 7, 13, 0.8)";
    ctx.fillRect(x - width / 2, y - px / 2 - 3, width, px + 6);
    ctx.fillStyle = entry.color;
    ctx.fillText(entry.text, x, y + 1);
  }
  pendingLabels.length = 0;
}

// ------------------------------------------------------------- the floor
function drawZone(ctx, thing, t) {
  const { x, y } = thing;
  const on = Boolean(thing.on);
  const radius = 74;
  ctx.save();
  ctx.globalAlpha = on ? 0.32 : 0.16 + Math.sin(t * 3 + thing.id) * 0.05;
  ctx.fillStyle = on ? GREEN : CYAN;
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, TAU);
  ctx.fill();
  ctx.globalAlpha = 0.9;
  ctx.strokeStyle = on ? GREEN : CYAN;
  ctx.lineWidth = 3;
  ctx.setLineDash(on ? [] : [12, 8]);
  ctx.lineDashOffset = -t * 30;
  ctx.stroke();
  ctx.setLineDash([]);
  if (thing.charge && !on) {
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.arc(x, y, radius - 8, -Math.PI / 2, -Math.PI / 2 + TAU * thing.charge);
    ctx.stroke();
  }
  ctx.restore();
  if (thing.label) label(ctx, thing.label, x, y + radius + 18, on ? GREEN : "#d6f6fb", 19);
}

function drawPlate(ctx, thing, t) {
  const { x, y } = thing;
  const size = 58;
  ctx.save();
  ctx.fillStyle = "rgba(0, 0, 0, 0.45)";
  ctx.fillRect(x - size / 2 + 3, y - size / 2 + 5, size, size);
  ctx.fillStyle = thing.on ? "#1f5a3a" : "#2a2838";
  ctx.fillRect(x - size / 2, y - size / 2, size, size);
  ctx.strokeStyle = thing.on ? GREEN : "#8a86a8";
  ctx.lineWidth = 3;
  ctx.strokeRect(x - size / 2 + 2, y - size / 2 + 2, size - 4, size - 4);
  ctx.font = 'bold 26px "JetBrains Mono", ui-monospace, monospace';
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = thing.on ? "#bfffd8" : `rgba(240, 236, 255, ${0.75 + Math.sin(t * 2 + thing.n) * 0.15})`;
  ctx.fillText(String(thing.n), x, y + 1);
  ctx.restore();
}

function drawSign(ctx, sign) {
  const { x, y } = sign;
  const title = sign.label || "код на стене";
  ctx.save();
  ctx.fillStyle = "#14121e";
  ctx.fillRect(x - 110, y - 26, 220, 50);
  ctx.strokeStyle = GOLD;
  ctx.lineWidth = 3;
  ctx.strokeRect(x - 110, y - 26, 220, 50);
  ctx.restore();
  label(ctx, title, x, y, GOLD, 20);
}

function drawBeacon(ctx, thing, t) {
  const { x, y } = thing;
  ctx.save();
  ctx.globalAlpha = thing.on ? 0.25 : 0.45 + Math.sin(t * 2) * 0.15;
  ctx.strokeStyle = "#9ff0c0";
  ctx.lineWidth = 3;
  for (const reach of [40, 64]) {
    ctx.beginPath();
    ctx.arc(x, y, reach + Math.sin(t * 2 + reach) * 3, 0, TAU);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
  ctx.fillStyle = thing.on ? "#3a5a48" : "#9ff0c0";
  ctx.fillRect(x - 6, y - 16, 12, 32);
  ctx.fillRect(x - 16, y - 6, 32, 12);
  ctx.restore();
}

function drawTrial(ctx, thing, t) {
  const { x, y } = thing;
  ctx.save();
  ctx.globalAlpha = thing.on ? 0.3 : 0.7;
  ctx.strokeStyle = "#ffb347";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.arc(x, y, 46, 0, TAU);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x + Math.cos(t * 2) * 34, y + Math.sin(t * 2) * 34);
  ctx.stroke();
  ctx.restore();
  if (thing.label && !thing.on) label(ctx, `только ${thing.label}`, x, y + 70, "#ffd8a0", 20);
}

function drawHole(ctx, thing, t) {
  const { x, y } = thing;
  ctx.save();
  ctx.fillStyle = "#04030a";
  ctx.beginPath();
  ctx.ellipse(x, y, 44, 30, 0, 0, TAU);
  ctx.fill();
  ctx.strokeStyle = RED;
  ctx.lineWidth = 3;
  ctx.setLineDash([9, 7]);
  ctx.lineDashOffset = t * 30;
  ctx.stroke();
  ctx.restore();
  label(ctx, thing.label, x, y - 46, "#ffb0aa", 16);
}

function drawStation(ctx, thing) {
  const { x, y } = thing;
  ctx.save();
  ctx.strokeStyle = thing.on ? GREEN : "#ffd93d";
  ctx.lineWidth = 3;
  ctx.setLineDash([10, 8]);
  ctx.beginPath();
  ctx.arc(x, y, 58, 0, TAU);
  ctx.stroke();
  ctx.restore();
  label(ctx, thing.label, x, y + 76, "#ffe9a8", 18);
}

/** Traffic on its way to whichever nodes have a mage beside them. */
function drawTraffic(ctx, device, node, t) {
  ctx.save();
  ctx.strokeStyle = "rgba(127, 224, 238, 0.65)";
  ctx.lineWidth = 3;
  ctx.setLineDash([12, 12]);
  ctx.lineDashOffset = -t * 90;
  ctx.beginPath();
  ctx.moveTo(device.x, device.y);
  ctx.lineTo(node.x, node.y);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#d6f6fb";
  for (let index = 0; index < 4; index += 1) {
    const at = (t * 0.7 + index / 4) % 1;
    ctx.fillRect(device.x + (node.x - device.x) * at - 4, device.y + (node.y - device.y) * at - 4, 8, 8);
  }
  ctx.restore();
}

function drawNode(ctx, thing, t) {
  const { x, y } = thing;
  const load = thing.charge || 0;
  const melted = Boolean(thing.on);
  const hue = melted ? RED : load > 0.75 ? RED : load > 0.45 ? "#ffb347" : GREEN;
  ctx.save();
  ctx.globalAlpha = thing.route ? 0.3 : 0.12;
  ctx.fillStyle = thing.route ? CYAN : "#8a86a8";
  ctx.beginPath();
  ctx.arc(x, y, 84, 0, TAU);
  ctx.fill();
  ctx.globalAlpha = 0.9;
  ctx.strokeStyle = thing.route ? CYAN : "#5a5870";
  ctx.lineWidth = 3;
  ctx.stroke();
  ctx.globalAlpha = 1;
  ctx.fillStyle = "#1c1f26";
  ctx.fillRect(x - 24, y - 62, 48, 70);
  for (let row = 0; row < 5; row += 1) {
    ctx.fillStyle = "#15171c";
    ctx.fillRect(x - 19, y - 56 + row * 12, 38, 8);
    const lit = !melted && Math.sin(t * (4 + row) + row * 1.7 + thing.id) > -0.2;
    ctx.fillStyle = lit ? hue : "#3a2228";
    ctx.fillRect(x + 8, y - 54 + row * 12, 5, 4);
  }
  ctx.fillStyle = "rgba(4, 6, 10, 0.9)";
  ctx.fillRect(x - 40, y + 14, 80, 12);
  ctx.fillStyle = hue;
  ctx.fillRect(x - 38, y + 16, 76 * Math.min(1, load), 8);
  if (melted) {
    for (let spark = 0; spark < 4; spark += 1) {
      if (Math.sin(t * 17 + spark * 2.1) > 0.4) {
        ctx.fillStyle = "#ffe17a";
        ctx.fillRect(x - 22 + spark * 14, y - 60 + Math.sin(t * 9 + spark) * 24, 5, 5);
      }
    }
  }
  ctx.restore();
  label(ctx, melted ? "узел расплавлен" : thing.label, x, y + 44, melted ? "#ffb0aa" : "#d6f6fb", 16);
}

/** The memory the leak has taken: each block of floor it owns, in hot blue. */
function drawMemory(ctx, goo, tile, t) {
  if (!goo?.b) return;
  const cell = goo.s * tile;
  const pulse = 0.3 + Math.sin(t * 2.4) * 0.05;
  ctx.save();
  for (let index = 0; index < goo.b.length; index += 1) {
    if (goo.b[index] !== "1") continue;
    const px = (goo.x + (index % goo.c) * goo.s) * tile;
    const py = (goo.y + Math.floor(index / goo.c) * goo.s) * tile;
    ctx.fillStyle = `rgba(95, 208, 255, ${pulse})`;
    ctx.fillRect(px + 3, py + 3, cell - 6, cell - 6);
    ctx.fillStyle = "rgba(191, 240, 255, 0.45)";
    ctx.fillRect(px + 12, py + 14, cell * 0.5, 6);
    ctx.fillRect(px + 12, py + 28, cell * 0.3, 6);
  }
  ctx.restore();
}

/** The way a build still has to ride: to the deploy, past every stage. */
function drawRoute(ctx, route, t) {
  if (!route || route.length < 2) return;
  ctx.save();
  ctx.strokeStyle = "rgba(79, 224, 138, 0.7)";
  ctx.lineWidth = 5;
  ctx.setLineDash([14, 14]);
  ctx.lineDashOffset = -t * 40;
  ctx.beginPath();
  route.forEach(([x, y], index) => {
    if (index) ctx.lineTo(x, y);
    else ctx.moveTo(x, y);
  });
  ctx.stroke();
  ctx.restore();
}

/** What lies flat: circles, plates, the shelter mark, the code on the wall. */
export function drawQuestFloor(ctx, quest, config, now) {
  const t = now / 1000;
  for (const sign of config?.signs || []) drawSign(ctx, sign);
  if (!quest) return;
  drawMemory(ctx, quest.goo, config.tile || 48, t);
  drawRoute(ctx, quest.route, t);
  const device = (quest.units || []).find((unit) => DEVICES[unit.sprite]);
  for (const thing of quest.things || []) {
    if (thing.k === "zone") drawZone(ctx, thing, t);
    else if (thing.k === "plate") drawPlate(ctx, thing, t);
    else if (thing.k === "beacon") drawBeacon(ctx, thing, t);
    else if (thing.k === "trial") drawTrial(ctx, thing, t);
    else if (thing.k === "hole") drawHole(ctx, thing, t);
    else if (thing.k === "station") drawStation(ctx, thing);
    else if (thing.k === "node" && thing.route && device && !thing.on) drawTraffic(ctx, device, thing, t);
  }
  for (const thing of quest.things || []) {
    if (thing.k === "node") drawNode(ctx, thing, t);
  }
}

// ----------------------------------------------------------- the things
function drawFile(ctx, thing, t) {
  const bob = Math.sin(t * 3 + thing.id) * 4;
  const x = thing.x;
  const y = thing.y - 12 + bob;
  const color = thing.bad ? RED : thing.color || CYAN;
  ctx.save();
  ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
  ctx.beginPath();
  ctx.ellipse(thing.x, thing.y + 16, 16, 6, 0, 0, TAU);
  ctx.fill();
  ctx.fillStyle = "#f4f2fa";
  ctx.beginPath();
  ctx.moveTo(x - 13, y - 17);
  ctx.lineTo(x + 5, y - 17);
  ctx.lineTo(x + 13, y - 9);
  ctx.lineTo(x + 13, y + 17);
  ctx.lineTo(x - 13, y + 17);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = color;
  ctx.fillRect(x - 9, y - 4, 18, 4);
  ctx.fillRect(x - 9, y + 3, 12, 4);
  if (thing.bad) {
    ctx.fillRect(x - 9, y + 10, 18, 4);
  }
  ctx.restore();
  if (thing.label) label(ctx, thing.label, x, y - 36, thing.bad ? "#ffb0aa" : "#d6f6fb", 17);
}

function drawChest(ctx, thing) {
  const { x, y } = thing;
  const open = Boolean(thing.on);
  ctx.save();
  ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
  ctx.fillRect(x - 30, y + 14, 60, 10);
  ctx.fillStyle = "#6a4420";
  ctx.fillRect(x - 28, y - 8, 56, 26);
  ctx.fillStyle = GOLD;
  ctx.fillRect(x - 28, y - 8, 56, 4);
  ctx.fillRect(x - 4, y - 2, 8, 10);
  ctx.fillStyle = "#8a5a2a";
  if (open) {
    ctx.fillRect(x - 28, y - 30, 56, 10);
    ctx.fillStyle = "rgba(255, 210, 122, 0.4)";
    ctx.fillRect(x - 24, y - 20, 48, 12);
  } else {
    ctx.fillRect(x - 28, y - 22, 56, 14);
    ctx.fillStyle = GOLD;
    ctx.fillRect(x - 28, y - 22, 56, 3);
  }
  ctx.restore();
}

function drawAltar(ctx, thing, t) {
  const { x, y } = thing;
  ctx.save();
  ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
  ctx.fillRect(x - 34, y + 20, 68, 10);
  ctx.fillStyle = "#2a2a36";
  ctx.fillRect(x - 30, y - 6, 60, 28);
  ctx.fillStyle = "#3e3e50";
  ctx.fillRect(x - 22, y - 34, 44, 30);
  const eye = thing.on ? 0.25 : 0.7 + Math.sin(t * 4) * 0.3;
  ctx.fillStyle = `rgba(255, 79, 106, ${eye})`;
  ctx.fillRect(x - 12, y - 24, 24, 10);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(x - 3, y - 22, 6, 6);
  ctx.restore();
  if (!thing.on) label(ctx, `PGT: ${thing.label}`, x, y - 56, "#ffb0bc", 18);
}

function drawPacket(ctx, thing, players, t) {
  let { x, y } = thing;
  const holder = thing.holder ? players.get(thing.holder) : null;
  if (holder) {
    x = holder.x;
    y = holder.y - 58;
  }
  const spin = t * 2;
  ctx.save();
  ctx.translate(x, y + Math.sin(t * 4) * 3);
  ctx.rotate(Math.sin(spin) * 0.2);
  ctx.fillStyle = "rgba(255, 217, 61, 0.25)";
  ctx.beginPath();
  ctx.arc(0, 0, 26, 0, TAU);
  ctx.fill();
  ctx.fillStyle = "#ffd93d";
  ctx.fillRect(-14, -14, 28, 28);
  ctx.fillStyle = "#8a6a10";
  ctx.fillRect(-14, -2, 28, 4);
  ctx.fillRect(-2, -14, 4, 28);
  ctx.restore();
  if (!holder && thing.label) label(ctx, thing.label, x, y - 40, "#fff0b0", 17);
}

function drawRack(ctx, style, down, t) {
  ctx.fillStyle = "#1c1f26";
  ctx.fillRect(-32, -88, 64, 100);
  ctx.fillStyle = "#2c3038";
  ctx.fillRect(-28, -84, 56, 92);
  for (let row = 0; row < 6; row += 1) {
    ctx.fillStyle = "#15171c";
    ctx.fillRect(-24, -78 + row * 14, 48, 10);
    const lit = !down && Math.sin(t * (3 + row) + row * 1.7) > -0.2;
    ctx.fillStyle = lit ? style.color : "#3a2228";
    ctx.fillRect(14, -75 + row * 14, 5, 4);
    if (lit && row % 2) {
      ctx.fillStyle = "#ffae5c";
      ctx.fillRect(6, -75 + row * 14, 4, 4);
    }
  }
}

function drawCylinder(ctx, style, down, t) {
  for (let band = 0; band < 3; band += 1) {
    const top = -86 + band * 32;
    ctx.fillStyle = "#1f2a3a";
    ctx.fillRect(-30, top, 60, 28);
    ctx.fillStyle = down ? "#2a2f3a" : style.color;
    ctx.beginPath();
    ctx.ellipse(0, top, 30, 9, 0, 0, TAU);
    ctx.fill();
    ctx.fillStyle = "#101820";
    ctx.beginPath();
    ctx.ellipse(0, top, 24, 6, 0, 0, TAU);
    ctx.fill();
    if (!down && Math.sin(t * 5 + band) > 0) {
      ctx.fillStyle = "#bfffd8";
      ctx.fillRect(18, top + 12, 5, 4);
    }
  }
}

function drawBucket(ctx, style, down) {
  ctx.fillStyle = down ? "#3a3030" : style.color;
  ctx.beginPath();
  ctx.moveTo(-34, -70);
  ctx.lineTo(34, -70);
  ctx.lineTo(24, 10);
  ctx.lineTo(-24, 10);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = "#2a1a08";
  ctx.beginPath();
  ctx.ellipse(0, -70, 34, 10, 0, 0, TAU);
  ctx.fill();
}

function drawScreen(ctx, style, down, t) {
  ctx.fillStyle = "#1c1f26";
  ctx.fillRect(-40, -84, 80, 60);
  ctx.fillStyle = down ? "#101014" : "#0a1410";
  ctx.fillRect(-35, -79, 70, 50);
  if (!down) {
    ctx.strokeStyle = style.color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let step = 0; step <= 14; step += 1) {
      const px = -32 + step * 4.6;
      const py = -54 + Math.sin(t * 3 + step * 0.9) * 12;
      if (step) ctx.lineTo(px, py);
      else ctx.moveTo(px, py);
    }
    ctx.stroke();
  }
  ctx.fillStyle = "#2c3038";
  ctx.fillRect(-8, -24, 16, 26);
  ctx.fillRect(-26, 0, 52, 8);
}

function drawNameServer(ctx, thing, t) {
  const { x, y } = thing;
  const dead = Boolean(thing.bad);
  ctx.save();
  ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
  ctx.beginPath();
  ctx.ellipse(x, y + 26, 30, 9, 0, 0, TAU);
  ctx.fill();
  ctx.fillStyle = "#23262e";
  ctx.fillRect(x - 22, y - 46, 44, 72);
  ctx.fillStyle = dead ? "#4a2028" : thing.on ? "#1f5a3a" : "#2e3440";
  ctx.fillRect(x - 17, y - 40, 34, 26);
  ctx.strokeStyle = "#8a90a0";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(x, y - 46);
  ctx.lineTo(x, y - 70);
  ctx.stroke();
  const blink = Math.sin(t * 5 + thing.id) > 0;
  ctx.fillStyle = dead ? RED : thing.on ? GREEN : blink ? "#ffd93d" : "#6a5a20";
  ctx.fillRect(x - 4, y - 76, 8, 8);
  for (let row = 0; row < 3; row += 1) {
    ctx.fillStyle = "#14161c";
    ctx.fillRect(x - 17, y - 8 + row * 11, 34, 7);
  }
  ctx.restore();
  const color = dead ? "#ffb0aa" : thing.on ? "#bfffd8" : "#ffffff";
  label(ctx, dead ? `${thing.label}: подделка` : thing.label, x, y - 96, color, 21);
}

function drawWalker(ctx, thing, t) {
  const sprite = personSprite("user");
  const scale = 3;
  const width = sprite.width * scale;
  const height = sprite.height * scale;
  const bob = Math.abs(Math.sin(t * 8 + thing.id)) * -3;
  ctx.save();
  ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
  ctx.beginPath();
  ctx.ellipse(thing.x, thing.y + 14, 14, 5, 0, 0, TAU);
  ctx.fill();
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(sprite, thing.x - width / 2, thing.y + 14 - height + bob, width, height);
  ctx.restore();
  label(ctx, thing.label, thing.x, thing.y - 46, "#bfffd8", 15);
}

function drawContainer(ctx, unit, t) {
  const up = unit.status === "up";
  const { x, y } = unit;
  ctx.save();
  ctx.fillStyle = "rgba(0, 0, 0, 0.45)";
  ctx.beginPath();
  ctx.ellipse(x, y + 34, 60, 13, 0, 0, TAU);
  ctx.fill();
  ctx.fillStyle = up ? "#1e5a90" : "#39414e";
  ctx.fillRect(x - 54, y - 34, 108, 66);
  ctx.fillStyle = up ? "#3aa7ff" : "#57606e";
  for (let rib = 0; rib < 6; rib += 1) {
    ctx.fillRect(x - 48 + rib * 17, y - 28, 8, 54);
  }
  ctx.fillStyle = up ? (Math.sin(t * 6 + unit.id) > -0.3 ? GREEN : "#1f5a3a") : RED;
  ctx.fillRect(x + 36, y - 44, 12, 8);
  if (unit.charge) {
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.arc(x, y, 76, -Math.PI / 2, -Math.PI / 2 + TAU * unit.charge);
    ctx.stroke();
  }
  ctx.restore();
  label(ctx, `${unit.label}: ${up ? "Up" : "Exited"}`, x, y - 62, up ? "#bfffd8" : "#ffb0aa", 19);
}

function drawCart(ctx, unit, t) {
  const { x, y } = unit;
  const spin = t * 5;
  ctx.save();
  ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
  ctx.beginPath();
  ctx.ellipse(x, y + 32, 46, 10, 0, 0, TAU);
  ctx.fill();
  ctx.fillStyle = "#c9973a";
  ctx.fillRect(x - 38, y - 34, 76, 54);
  ctx.fillStyle = "#8a5f18";
  ctx.fillRect(x - 38, y - 12, 76, 6);
  ctx.fillRect(x - 3, y - 34, 6, 54);
  ctx.fillStyle = "#1c1f26";
  for (const side of [-24, 24]) {
    ctx.beginPath();
    ctx.arc(x + side, y + 24, 10, 0, TAU);
    ctx.fill();
    ctx.fillStyle = "#6a7080";
    ctx.fillRect(x + side + Math.cos(spin) * 6 - 2, y + 24 + Math.sin(spin) * 6 - 2, 4, 4);
    ctx.fillStyle = "#1c1f26";
  }
  ctx.restore();
  label(ctx, unit.label, x, y - 60, "#ffe9a8", 18);
}

function drawResident(ctx, thing, t) {
  const { x, y, sprite } = thing;
  const bob = Math.sin(t * 2.4 + thing.id) * 2;
  ctx.save();
  ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
  ctx.beginPath();
  ctx.ellipse(x, y + 28, 38, 10, 0, 0, TAU);
  ctx.fill();
  if (sprite === "atm") {
    ctx.fillStyle = "#5a6070";
    ctx.fillRect(x - 28, y - 56, 56, 84);
    ctx.fillStyle = "#3a4050";
    ctx.fillRect(x - 28, y - 56, 56, 8);
    ctx.fillStyle = "#123a2a";
    ctx.fillRect(x - 20, y - 44, 40, 26);
    ctx.fillStyle = "#4fe08a";
    ctx.fillRect(x - 15, y - 38, 22, 3);
    ctx.fillRect(x - 15, y - 30, 14, 3);
    for (let row = 0; row < 3; row += 1) {
      for (let col = 0; col < 3; col += 1) {
        ctx.fillStyle = "#c8c4b4";
        ctx.fillRect(x - 18 + col * 9, y - 12 + row * 8, 6, 5);
      }
    }
    ctx.fillStyle = "#14161c";
    ctx.fillRect(x + 12, y - 12, 10, 22);
    if (thing.say) {
      ctx.fillStyle = "#ffd27a";
      ctx.fillRect(x + 32, y - 70 + bob * 3, 5, 12);
      ctx.fillRect(x + 37, y - 70 + bob * 3, 6, 3);
      ctx.beginPath();
      ctx.arc(x + 31, y - 57 + bob * 3, 4, 0, TAU);
      ctx.fill();
    }
  } else if (sprite === "fridge") {
    ctx.fillStyle = "#e4e8f0";
    ctx.fillRect(x - 26, y - 66, 52, 94);
    ctx.fillStyle = "#b0b6c4";
    ctx.fillRect(x - 26, y - 34, 52, 3);
    ctx.fillRect(x + 16, y - 56, 4, 14);
    ctx.fillRect(x + 16, y - 24, 4, 26);
    ctx.fillStyle = "#1a1a22";
    ctx.fillRect(x - 14, y - 54, 6, 6);
    ctx.fillRect(x - 1, y - 54, 6, 6);
    ctx.fillRect(x - 16, y - 60, 10, 3);
    ctx.fillRect(x - 3, y - 58, 10, 3);
    ctx.fillRect(x - 10, y - 42 + (thing.say ? bob : 0), 14, 3);
  } else if (sprite === "clip") {
    ctx.strokeStyle = "#c0c8d8";
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.moveTo(x - 12, y + 22);
    ctx.lineTo(x - 12, y - 34);
    ctx.arc(x, y - 34, 12, Math.PI, 0);
    ctx.lineTo(x + 12, y + 8);
    ctx.arc(x + 2, y + 8, 10, 0, Math.PI);
    ctx.lineTo(x - 8, y - 22);
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(x - 14, y - 22 + bob, 11, 11);
    ctx.fillRect(x + 2, y - 22 + bob, 11, 11);
    ctx.fillStyle = "#14161c";
    ctx.fillRect(x - 10, y - 18 + bob, 5, 5);
    ctx.fillRect(x + 6, y - 18 + bob, 5, 5);
  } else if (drawFolkSprite(ctx, thing, x, y, t, bob)) {
    // Drawn: the side-story people have a page of their own below.
  } else if (sprite === "calc") {
    ctx.fillStyle = "#c8bfa4";
    ctx.fillRect(x - 24, y - 44, 48, 72);
    ctx.fillStyle = "#1e2a1e";
    ctx.fillRect(x - 18, y - 38, 36, 14);
    ctx.fillStyle = "#8fe388";
    ctx.fillRect(x + 6, y - 34, 8, 7);
    for (let row = 0; row < 4; row += 1) {
      for (let col = 0; col < 3; col += 1) {
        ctx.fillStyle = row === 3 && col === 2 ? "#6a2a24" : "#6a6658";
        ctx.fillRect(x - 18 + col * 13, y - 18 + row * 11, 10, 8);
      }
    }
  } else {
    ctx.fillStyle = "#4a3a54";
    ctx.fillRect(x - 40, y - 2, 80, 28);
    ctx.fillStyle = "#6a5474";
    ctx.fillRect(x - 40, y - 8, 80, 8);
    ctx.fillStyle = "#23202a";
    ctx.beginPath();
    ctx.moveTo(x - 20, y - 8);
    ctx.lineTo(x, y - 62 + bob);
    ctx.lineTo(x + 20, y - 8);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "#ffd27a";
    ctx.fillRect(x - 8, y - 34 + bob, 5, 4);
    ctx.fillRect(x + 3, y - 34 + bob, 5, 4);
    ctx.fillStyle = "#7fe0ee";
    ctx.fillRect(x - 30, y - 18, 12, 10);
    ctx.fillStyle = "#ff9ec7";
    ctx.fillRect(x + 18, y - 16, 12, 8);
  }
  ctx.restore();
  drawTalkMarks(ctx, thing, t);
  label(ctx, thing.label, x, y + 44, "#e8e4f4", 15);
  if (thing.say) label(ctx, thing.say, x, y - 92, "#ffe9a8", 15);
  if (thing.rate) label(ctx, thing.rate, x, y - 116, "#4fe08a", 24);
  if (thing.mark) label(ctx, thing.mark, x, y - 72 + bob, MARK_COLORS[thing.mark] || "#ffe9a8", 26);
}

const MARK_COLORS = { "!": GOLD, "…": CYAN, "✓": GREEN, "?": "#a8b0c4" };

function drawFolkPerson(ctx, sprite, x, y, bob, scale = 3.4) {
  const art = personSprite(sprite);
  const width = art.width * scale;
  const height = art.height * scale;
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(art, x - width / 2, y + 28 - height + bob * 0.5, width, height);
}

/** Everyone from the side stories. Returns whether this sprite was one of them. */
function drawFolkSprite(ctx, thing, x, y, t, bob) {
  const { sprite } = thing;
  if (["webmaster", "gosha", "senya", "petrovich", "babka", "luba", "maria", "guard", "miner"].includes(sprite)) {
    drawFolkPerson(ctx, sprite, x, y, bob);
    if (sprite === "luba") {
      ctx.fillStyle = "#8a6a3a";
      ctx.fillRect(x + 26, y - 40, 5, 66);
      ctx.fillStyle = "#c8ccd4";
      ctx.fillRect(x + 18, y + 22, 22, 8);
    } else if (sprite === "petrovich") {
      ctx.fillStyle = "#6a5a4a";
      ctx.fillRect(x + 26, y - 26, 5, 40);
      ctx.fillStyle = "#3a3e48";
      ctx.fillRect(x + 16, y - 36, 25, 14);
    } else if (sprite === "senya") {
      ctx.strokeStyle = "#fff6d0";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(x, y - 22, 34, 0, TAU);
      ctx.stroke();
    } else if (sprite === "miner") {
      ctx.fillStyle = "#3a3e48";
      ctx.fillRect(x + 22, y - 2, 30, 20);
      ctx.fillStyle = (Math.sin(t * 5) > 0) ? GREEN : "#1f5a3a";
      ctx.fillRect(x + 26, y + 4, 8, 8);
    }
    return true;
  }
  switch (sprite) {
    case "modem":
      ctx.fillStyle = "#c8c4b4";
      ctx.fillRect(x - 40, y - 10, 80, 36);
      ctx.fillStyle = "#8a8678";
      ctx.fillRect(x - 40, y + 16, 80, 10);
      for (let led = 0; led < 5; led += 1) {
        ctx.fillStyle = Math.sin(t * 6 + led * 1.4) > 0 ? GREEN : "#1f5a3a";
        ctx.fillRect(x - 30 + led * 13, y + 2, 8, 6);
      }
      ctx.strokeStyle = "#14161c";
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.moveTo(x + 40, y + 10);
      ctx.bezierCurveTo(x + 70, y - 30, x + 30, y - 50, x + 10, y - 30 + bob);
      ctx.stroke();
      return true;
    case "troll": {
      const size = thing.size || 1;
      ctx.save();
      ctx.translate(x, y + 28);
      ctx.scale(size, size);
      ctx.fillStyle = "#5a9a4a";
      ctx.fillRect(-26, -62, 52, 62);
      ctx.fillStyle = "#3f7a34";
      ctx.fillRect(-26, -16, 52, 16);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(-16, -52, 12, 10);
      ctx.fillRect(4, -52, 12, 10);
      ctx.fillStyle = "#14161c";
      ctx.fillRect(-10, -48, 5, 6);
      ctx.fillRect(10, -48, 5, 6);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(-16, -34, 32, 8);
      ctx.fillStyle = "#14161c";
      for (let tooth = 1; tooth < 4; tooth += 1) ctx.fillRect(-16 + tooth * 8, -34, 2, 8);
      ctx.restore();
      return true;
    }
    case "cat": {
      ctx.save();
      if (thing.frozen) ctx.globalAlpha = 0.85;
      ctx.fillStyle = thing.frozen ? "#a8e4f4" : "#e8903a";
      ctx.fillRect(x - 24, y - 6, 48, 26);
      ctx.fillRect(x - 34, y - 26, 28, 26);
      ctx.fillRect(x - 34, y - 34, 8, 10);
      ctx.fillRect(x - 14, y - 34, 8, 10);
      ctx.fillRect(x - 24, y + 18, 8, 10);
      ctx.fillRect(x + 12, y + 18, 8, 10);
      ctx.fillRect(x + 22, y - 18 + Math.sin(t * 5) * 6, 6, 26);
      ctx.fillStyle = "#14161c";
      ctx.fillRect(x - 30, y - 18, 5, 5);
      ctx.fillRect(x - 16, y - 18, 5, 5);
      ctx.fillStyle = "#b0601a";
      for (let stripe = 0; stripe < 3; stripe += 1) ctx.fillRect(x - 12 + stripe * 12, y - 6, 5, 16);
      ctx.restore();
      return true;
    }
    case "rec":
      ctx.fillStyle = "#3a4050";
      ctx.fillRect(x - 28, y - 44, 56, 72);
      ctx.fillStyle = "#14161c";
      ctx.fillRect(x - 20, y - 36, 40, 32);
      ctx.fillStyle = "#ff4f6a";
      ctx.beginPath();
      ctx.arc(x + Math.sin(t * 1.3) * 10, y - 20, 8, 0, TAU);
      ctx.fill();
      ctx.fillStyle = "#6a7080";
      ctx.fillRect(x - 20, y + 4, 40, 5);
      ctx.fillRect(x - 20, y + 14, 26, 5);
      return true;
    case "diplom":
      ctx.fillStyle = "#f4f8ff";
      ctx.fillRect(x - 24, y - 50, 48, 76);
      ctx.fillStyle = "#c8d4e4";
      ctx.fillRect(x + 8, y - 50, 16, 16);
      ctx.fillStyle = "#3a6ab0";
      ctx.fillRect(x - 16, y - 40, 20, 5);
      for (let row = 0; row < 5; row += 1) {
        ctx.fillStyle = "#8a94a8";
        ctx.fillRect(x - 16, y - 28 + row * 10, row % 2 ? 26 : 32, 3);
      }
      ctx.fillStyle = "#14161c";
      ctx.fillRect(x - 9, y - 6 + bob, 5, 5);
      ctx.fillRect(x + 5, y - 6 + bob, 5, 5);
      return true;
    case "asya":
      ctx.fillStyle = "#2a8a3a";
      ctx.fillRect(x - 3, y - 10, 6, 38);
      for (let petal = 0; petal < 8; petal += 1) {
        const angle = (petal / 8) * TAU + t * 0.4;
        ctx.fillStyle = petal === 0 ? "#ff5a4f" : "#4fe08a";
        ctx.beginPath();
        ctx.ellipse(x + Math.cos(angle) * 22, y - 32 + Math.sin(angle) * 22, 13, 13, 0, 0, TAU);
        ctx.fill();
      }
      ctx.fillStyle = "#ffd93d";
      ctx.beginPath();
      ctx.arc(x, y - 32, 13, 0, TAU);
      ctx.fill();
      return true;
    case "bin":
      ctx.fillStyle = "#6a7080";
      ctx.fillRect(x - 28, y - 30, 56, 58);
      ctx.fillStyle = "#8a92a4";
      ctx.fillRect(x - 34, y - 40, 68, 10);
      ctx.fillRect(x - 10, y - 48, 20, 8);
      ctx.fillStyle = "#3a4050";
      for (let rib = 0; rib < 3; rib += 1) ctx.fillRect(x - 18 + rib * 15, y - 22, 6, 42);
      return true;
    case "sync":
      ctx.fillStyle = "#d6f6fb";
      ctx.beginPath();
      ctx.arc(x - 18, y - 16 + bob, 20, 0, TAU);
      ctx.arc(x + 4, y - 26 + bob, 24, 0, TAU);
      ctx.arc(x + 24, y - 12 + bob, 18, 0, TAU);
      ctx.fill();
      ctx.fillRect(x - 36, y - 16 + bob, 76, 22);
      ctx.strokeStyle = "#3aa7ff";
      ctx.lineWidth = 5;
      ctx.beginPath();
      ctx.arc(x + 2, y - 12 + bob, 12, t * 2, t * 2 + 4.6);
      ctx.stroke();
      return true;
    case "cron":
      ctx.fillStyle = "#6a5a4a";
      ctx.fillRect(x - 22, y - 44, 44, 72);
      ctx.fillStyle = "#3a3026";
      ctx.fillRect(x - 28, y - 50, 56, 8);
      ctx.fillStyle = "#e8e0c8";
      ctx.beginPath();
      ctx.arc(x, y - 18, 16, 0, TAU);
      ctx.fill();
      ctx.fillStyle = "#14161c";
      ctx.fillRect(x - 1, y - 30, 3, 12);
      return true;
    case "printer":
      ctx.fillStyle = "#c8c4b4";
      ctx.fillRect(x - 44, y - 20, 88, 48);
      ctx.fillStyle = "#8a8678";
      ctx.fillRect(x - 44, y + 18, 88, 10);
      ctx.fillStyle = "#f4f8ff";
      ctx.fillRect(x - 26, y - 44 + bob, 52, 28);
      ctx.fillStyle = "#14161c";
      ctx.fillRect(x - 36, y - 8, 30, 14);
      ctx.fillStyle = Math.sin(t * 8) > 0 ? RED : "#5a1a18";
      ctx.fillRect(x + 22, y - 6, 10, 10);
      return true;
    case "ac":
      ctx.fillStyle = "#e4e8f0";
      ctx.fillRect(x - 46, y - 34, 92, 42);
      ctx.fillStyle = "#b0b6c4";
      for (let vent = 0; vent < 4; vent += 1) ctx.fillRect(x - 38, y - 26 + vent * 8, 76, 3);
      ctx.fillStyle = "#7fe0ee";
      for (let flake = 0; flake < 4; flake += 1) {
        ctx.fillRect(x - 32 + flake * 20, y + 12 + ((t * 28 + flake * 9) % 20), 5, 5);
      }
      return true;
    case "sensor":
      ctx.fillStyle = "#e4e8f0";
      ctx.fillRect(x - 12, y - 46, 24, 66);
      ctx.fillStyle = "#ff5a4f";
      ctx.fillRect(x - 4, y - 36, 8, 46);
      ctx.beginPath();
      ctx.arc(x, y + 18, 14, 0, TAU);
      ctx.fill();
      return true;
    case "ghost": {
      ctx.save();
      ctx.globalAlpha = 0.55 + Math.sin(t * 9) * 0.25;
      const shift = Math.sin(t * 23) * 3;
      ctx.fillStyle = "#c86bff";
      ctx.fillRect(x - 22 + shift, y - 50, 44, 52);
      ctx.fillRect(x - 22 - shift, y - 4, 12, 30);
      ctx.fillRect(x - 5 + shift, y - 4, 12, 24);
      ctx.fillRect(x + 10 - shift, y - 4, 12, 30);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(x - 12 + shift, y - 38, 8, 12);
      ctx.fillRect(x + 6 + shift, y - 38, 8, 12);
      ctx.restore();
      return true;
    }
    default:
      return false;
  }
}

/** A circle to stand in, a clock to read: what an errand adds over someone's head. */
function drawTalkMarks(ctx, thing, t) {
  const { x, y } = thing;
  if (thing.ring) {
    ctx.save();
    ctx.strokeStyle = "rgba(127, 224, 238, 0.55)";
    ctx.lineWidth = 3;
    ctx.setLineDash([12, 10]);
    ctx.lineDashOffset = -t * 18;
    ctx.beginPath();
    ctx.arc(x, y, thing.ring, 0, TAU);
    ctx.stroke();
    ctx.setLineDash([]);
    if (thing.charge) {
      ctx.strokeStyle = GREEN;
      ctx.lineWidth = 6;
      ctx.beginPath();
      ctx.arc(x, y, thing.ring, -Math.PI / 2, -Math.PI / 2 + TAU * thing.charge);
      ctx.stroke();
    }
    ctx.restore();
  }
  if (thing.clock !== undefined) {
    const cx = x;
    const cy = y - 120;
    const hot = thing.clock <= 0.13 || thing.clock >= 0.87;
    ctx.save();
    ctx.fillStyle = "rgba(6, 9, 14, 0.85)";
    ctx.beginPath();
    ctx.arc(cx, cy, 38, 0, TAU);
    ctx.fill();
    ctx.fillStyle = "rgba(79, 224, 138, 0.55)";
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, 36, -Math.PI / 2 - TAU * 0.13, -Math.PI / 2 + TAU * 0.13);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = hot ? GREEN : "#ffffff";
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    const angle = -Math.PI / 2 + TAU * thing.clock;
    ctx.lineTo(cx + Math.cos(angle) * 32, cy + Math.sin(angle) * 32);
    ctx.stroke();
    ctx.restore();
  }
}

/** Floor first: puddles and frames should not sit on top of anybody. */
function drawFolkFloor(ctx, thing, t) {
  const { x, y, look } = thing;
  if (look === "wet") {
    ctx.save();
    ctx.fillStyle = "rgba(90, 170, 240, 0.38)";
    ctx.beginPath();
    ctx.ellipse(x, y, thing.r, thing.r * 0.9, 0, 0, TAU);
    ctx.fill();
    ctx.strokeStyle = "rgba(190, 230, 255, 0.7)";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = "rgba(235, 248, 255, 0.8)";
    ctx.fillRect(x - 20, y - 12 + Math.sin(t * 2 + thing.id) * 3, 14, 3);
    ctx.fillRect(x + 8, y + 10, 9, 3);
    ctx.restore();
  } else if (look === "frame") {
    const w = thing.w / 2;
    const h = thing.h / 2;
    const arm = 44;
    ctx.save();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 5;
    ctx.beginPath();
    for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      ctx.moveTo(x + sx * w, y + sy * (h - arm));
      ctx.lineTo(x + sx * w, y + sy * h);
      ctx.lineTo(x + sx * (w - arm), y + sy * h);
    }
    ctx.stroke();
    ctx.fillStyle = "rgba(255, 255, 255, 0.05)";
    ctx.fillRect(x - w, y - h, w * 2, h * 2);
    ctx.fillStyle = Math.sin(t * 5) > 0 ? RED : "#5a1a18";
    ctx.beginPath();
    ctx.arc(x - w + 20, y - h + 20, 8, 0, TAU);
    ctx.fill();
    ctx.restore();
    label(ctx, "REC", x - w + 52, y - h + 20, "#ffb0aa", 15);
  } else if (look === "ring") {
    const color = thing.color || CYAN;
    ctx.save();
    ctx.globalAlpha = thing.on ? 0.65 : 0.28;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, thing.r, 0, TAU);
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.restore();
    label(ctx, thing.label, x, y + thing.r + 16, color, 15);
  }
}

function drawFolkPart(ctx, thing, players, t) {
  const { x, y, look } = thing;
  switch (look) {
    case "runner": {
      const leg = Math.sin(t * 16 + thing.id) * 5;
      ctx.fillStyle = "#c9973a";
      ctx.fillRect(x - 14, y - 22, 28, 22);
      ctx.fillStyle = "#8a5f18";
      ctx.fillRect(x - 14, y - 16, 28, 4);
      ctx.fillStyle = "#14161c";
      ctx.fillRect(x - 9, y - 10, 4, 4);
      ctx.fillRect(x + 5, y - 10, 4, 4);
      ctx.fillRect(x - 11 + leg, y, 5, 9);
      ctx.fillRect(x + 6 - leg, y, 5, 9);
      label(ctx, thing.label, x, y - 36, "#ffe9a8", 15);
      break;
    }
    case "switch":
      ctx.fillStyle = "#23262e";
      ctx.fillRect(x - 20, y - 40, 40, 66);
      ctx.fillStyle = thing.on ? GREEN : RED;
      ctx.fillRect(x - 12, y - 32, 24, 14);
      ctx.fillStyle = "#a8b0c4";
      ctx.fillRect(x - 4, thing.on ? y - 12 : y - 2, 8, 22);
      label(ctx, thing.label, x, y - 56, thing.on ? "#bfffd8" : "#ffb0aa", 15);
      break;
    case "version":
      ctx.fillStyle = "#f4f8ff";
      ctx.fillRect(x - 18, y - 28 + Math.sin(t * 2 + thing.id) * 2, 36, 48);
      ctx.fillStyle = "#3a6ab0";
      ctx.fillRect(x - 11, y - 20, 20, 4);
      ctx.fillStyle = "#8a94a8";
      for (let row = 0; row < 3; row += 1) ctx.fillRect(x - 11, y - 10 + row * 8, 22, 3);
      label(ctx, thing.label, x, y - 44, "#f4f8ff", 16);
      break;
    case "shadow":
      ctx.save();
      ctx.globalAlpha = 0.55;
      ctx.fillStyle = "#6a5acd";
      ctx.beginPath();
      ctx.ellipse(x, y + 10, 18, 8, 0, 0, TAU);
      ctx.fill();
      ctx.fillRect(x - 13, y - 30, 26, 40);
      ctx.beginPath();
      ctx.arc(x, y - 36, 12, 0, TAU);
      ctx.fill();
      ctx.restore();
      label(ctx, thing.label, x, y - 58, "#c8b8ff", 14);
      break;
    case "file":
      ctx.fillStyle = thing.label.endsWith(".jpg") ? "#7fe0ee" : "#d8dce4";
      ctx.fillRect(x - 18, y - 24, 36, 46);
      ctx.fillStyle = "#8a94a8";
      ctx.fillRect(x + 6, y - 24, 12, 12);
      label(ctx, thing.label, x, y - 40, "#f4f8ff", 16);
      break;
    case "bucket": {
      const holder = thing.holder ? players.get(thing.holder) : null;
      const bx = holder ? holder.x + 24 : x;
      const by = holder ? holder.y - 8 : y;
      ctx.fillStyle = "#5a9ad0";
      ctx.fillRect(bx - 16, by - 14, 32, 30);
      ctx.fillStyle = "#3a6a9a";
      ctx.fillRect(bx - 18, by - 18, 36, 6);
      ctx.strokeStyle = "#c8ccd4";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(bx, by - 18, 15, Math.PI, 0);
      ctx.stroke();
      if (!holder) label(ctx, thing.label, x, y - 44, "#d6f6fb", 15);
      break;
    }
    case "socket":
      ctx.fillStyle = "#23262e";
      ctx.fillRect(x - 24, y - 34, 48, 62);
      ctx.fillStyle = "#14161c";
      ctx.fillRect(x - 12, y - 14, 24, 20);
      ctx.fillStyle = Math.sin(t * 6) > 0 ? RED : "#5a1a18";
      ctx.fillRect(x - 14, y - 28, 8, 8);
      label(ctx, thing.label, x, y - 50, "#ffb0aa", 15);
      break;
    case "plug": {
      const holder = thing.holder ? players.get(thing.holder) : null;
      const px = holder ? holder.x : x;
      const py = holder ? holder.y : y;
      const [ax, ay] = thing.anchor;
      ctx.strokeStyle = "#ffd93d";
      ctx.lineWidth = 5;
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(px, py);
      ctx.stroke();
      ctx.fillStyle = "#c9973a";
      ctx.fillRect(px - 8, py - 8, 16, 16);
      if (!holder) label(ctx, thing.label, x, y - 28, "#ffe9a8", 15);
      break;
    }
    default:
      break;
  }
}

function drawFind(ctx, thing, t) {
  const { x, y } = thing;
  const bob = Math.sin(t * 3 + thing.id) * 4;
  ctx.save();
  ctx.fillStyle = "#23262e";
  ctx.fillRect(x - 24, y, 48, 24);
  ctx.fillStyle = "#3a3e48";
  ctx.fillRect(x - 30, y + 20, 60, 8);
  ctx.globalAlpha = 0.3;
  ctx.fillStyle = CYAN;
  ctx.beginPath();
  ctx.arc(x, y - 18 + bob, 28, 0, TAU);
  ctx.fill();
  ctx.globalAlpha = 1;
  ctx.fillStyle = CYAN;
  ctx.fillRect(x - 11, y - 29 + bob, 22, 22);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(x - 6, y - 24 + bob, 7, 7);
  ctx.restore();
  label(ctx, thing.label, x, y - 56, "#d6f6fb", 16);
}

function drawRelic(ctx, thing, t) {
  const { x, y } = thing;
  const bob = Math.sin(t * 2) * 4;
  ctx.save();
  ctx.globalAlpha = 0.34;
  ctx.fillStyle = GOLD;
  ctx.beginPath();
  ctx.arc(x, y - 10 + bob, 38, 0, TAU);
  ctx.fill();
  ctx.globalAlpha = 1;
  ctx.fillStyle = GOLD;
  ctx.fillRect(x - 15, y - 25 + bob, 30, 30);
  ctx.fillStyle = "#8a5f18";
  ctx.fillRect(x - 15, y - 12 + bob, 30, 4);
  ctx.restore();
  label(ctx, thing.label, x, y - 58, "#ffe9a8", 16);
}

function drawLamp(ctx, thing) {
  const { x, y } = thing;
  const green = Boolean(thing.on);
  ctx.save();
  ctx.fillStyle = "#23262e";
  ctx.fillRect(x - 5, y - 40, 10, 66);
  ctx.fillRect(x - 22, y + 22, 44, 8);
  ctx.globalAlpha = 0.34;
  ctx.fillStyle = green ? GREEN : RED;
  ctx.beginPath();
  ctx.arc(x, y - 52, 44, 0, TAU);
  ctx.fill();
  ctx.globalAlpha = 1;
  ctx.beginPath();
  ctx.arc(x, y - 52, 20, 0, TAU);
  ctx.fill();
  ctx.restore();
  label(ctx, green ? "green" : "red", x, y - 88, green ? "#bfffd8" : "#ffb0aa", 18);
}

function drawDevice(ctx, unit, t) {
  const style = DEVICES[unit.sprite] || DEVICES.rack;
  const down = Boolean(unit.down);
  ctx.save();
  ctx.translate(unit.x, unit.y + 40);
  ctx.scale(1.35, 1.35);
  ctx.fillStyle = "rgba(0, 0, 0, 0.45)";
  ctx.beginPath();
  ctx.ellipse(0, 12, 44, 12, 0, 0, TAU);
  ctx.fill();
  if (style.shape === "db") drawCylinder(ctx, style, down, t);
  else if (style.shape === "bucket") drawBucket(ctx, style, down);
  else if (style.shape === "screen") drawScreen(ctx, style, down, t);
  else drawRack(ctx, style, down, t);
  if (unit.hit) {
    ctx.globalAlpha = 0.35 + Math.sin(t * 6) * 0.2;
    ctx.strokeStyle = style.color;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.ellipse(0, -36, 58, 72, 0, 0, TAU);
    ctx.stroke();
    ctx.globalAlpha = 1;
  }
  if (down) {
    for (let spark = 0; spark < 3; spark += 1) {
      if (Math.sin(t * 17 + spark * 2.1) > 0.6) {
        ctx.fillStyle = "#ffe17a";
        ctx.fillRect(-20 + spark * 18, -60 + Math.sin(t * 9 + spark) * 20, 4, 4);
      }
    }
  }
  ctx.restore();
  label(ctx, unit.label, unit.x, unit.y - 112, style.color, 21);
}

function drawPerson(ctx, unit, t) {
  const sprite = personSprite(unit.sprite);
  const scale = unit.sprite === "admin" ? 3.6 : 3.2;
  const width = sprite.width * scale;
  const height = sprite.height * scale;
  const down = Boolean(unit.down);
  ctx.save();
  ctx.translate(unit.x, unit.y);
  ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
  ctx.beginPath();
  ctx.ellipse(0, 16, 18, 7, 0, 0, TAU);
  ctx.fill();
  if (down) {
    ctx.rotate(Math.PI / 2);
    ctx.globalAlpha = 0.7;
  }
  ctx.imageSmoothingEnabled = false;
  const bob = down ? 0 : Math.abs(Math.sin(t * 6 + unit.id)) * -3;
  ctx.drawImage(sprite, -width / 2, 18 - height + bob, width, height);
  ctx.restore();
  if (down && unit.revive) {
    ctx.save();
    ctx.strokeStyle = GREEN;
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(unit.x, unit.y, 30, -Math.PI / 2, -Math.PI / 2 + TAU * unit.revive);
    ctx.stroke();
    ctx.restore();
  }
  label(ctx, unit.label, unit.x, unit.y - height - 2, down ? "#ffb0aa" : "#d6f6fb", 18);
}

/** What stands in the room: machines, people, files and boxes. */
export function drawQuestObjects(ctx, quest, players, now) {
  if (!quest) return;
  const t = now / 1000;
  for (const thing of quest.things || []) {
    if (thing.k === "folk") drawFolkFloor(ctx, thing, t);
  }
  for (const thing of quest.things || []) {
    if (thing.k === "folk") drawFolkPart(ctx, thing, players, t);
    else if (thing.k === "item") drawFile(ctx, thing, t);
    else if (thing.k === "chest") drawChest(ctx, thing);
    else if (thing.k === "altar") drawAltar(ctx, thing, t);
    else if (thing.k === "ns") drawNameServer(ctx, thing, t);
    else if (thing.k === "walker") drawWalker(ctx, thing, t);
    else if (thing.k === "npc") drawResident(ctx, thing, t);
    else if (thing.k === "find") drawFind(ctx, thing, t);
    else if (thing.k === "relic") drawRelic(ctx, thing, t);
    else if (thing.k === "lamp") drawLamp(ctx, thing, t);
  }
  for (const unit of quest.units || []) {
    if (unit.sprite === "container") drawContainer(ctx, unit, t);
    else if (unit.sprite === "artifact") drawCart(ctx, unit, t);
    else if (PEOPLE[unit.sprite]) drawPerson(ctx, unit, t);
    else drawDevice(ctx, unit, t);
  }
  for (const thing of quest.things || []) {
    if (thing.k === "packet") drawPacket(ctx, thing, players, t);
  }
}

export function questLights(quest, lights) {
  if (!quest) return;
  for (const unit of quest.units || []) {
    if (PEOPLE[unit.sprite]) {
      lights.push({ x: unit.x, y: unit.y, radius: 150, color: CYAN, power: 0.6 });
      continue;
    }
    if (unit.sprite === "container") {
      const up = unit.status === "up";
      lights.push({ x: unit.x, y: unit.y, radius: 190, color: up ? "#3aa7ff" : RED, power: 0.6 });
      continue;
    }
    if (unit.sprite === "artifact") {
      lights.push({ x: unit.x, y: unit.y, radius: 260, color: "#ffd93d", power: 0.8 });
      continue;
    }
    const style = DEVICES[unit.sprite] || DEVICES.rack;
    lights.push({ x: unit.x, y: unit.y, radius: unit.down ? 120 : 300, color: style.color, power: 0.85 });
  }
  for (const thing of quest.things || []) {
    if (thing.k === "zone") {
      lights.push({ x: thing.x, y: thing.y, radius: 170, color: thing.on ? GREEN : CYAN, power: 0.55 });
    } else if (thing.k === "item") {
      lights.push({ x: thing.x, y: thing.y, radius: 120, color: thing.bad ? RED : CYAN, power: 0.6 });
    } else if (thing.k === "beacon" && !thing.on) {
      lights.push({ x: thing.x, y: thing.y, radius: 260, color: "#9ff0c0", power: 0.8 });
    } else if (thing.k === "packet") {
      lights.push({ x: thing.x, y: thing.y, radius: 160, color: "#ffd93d", power: 0.7 });
    } else if (thing.k === "altar" && !thing.on) {
      lights.push({ x: thing.x, y: thing.y, radius: 190, color: "#ff4f6a", power: 0.7 });
    } else if (thing.k === "node") {
      const hot = thing.on || (thing.charge || 0) > 0.75;
      lights.push({ x: thing.x, y: thing.y, radius: 200, color: hot ? RED : CYAN, power: 0.6 });
    } else if (thing.k === "ns") {
      lights.push({ x: thing.x, y: thing.y, radius: 170, color: thing.bad ? RED : "#ffd93d", power: 0.6 });
    } else if (thing.k === "hole") {
      lights.push({ x: thing.x, y: thing.y, radius: 140, color: RED, power: 0.5 });
    } else if (thing.k === "npc") {
      lights.push({ x: thing.x, y: thing.y, radius: 220, color: "#ffe9a8", power: 0.65 });
    } else if (thing.k === "folk" && thing.look !== "wet" && thing.look !== "frame") {
      lights.push({ x: thing.x, y: thing.y, radius: 150, color: thing.color || GOLD, power: 0.55 });
    } else if (thing.k === "find") {
      lights.push({ x: thing.x, y: thing.y, radius: 170, color: CYAN, power: 0.8 });
    } else if (thing.k === "relic") {
      lights.push({ x: thing.x, y: thing.y, radius: 220, color: GOLD, power: 0.9 });
    } else if (thing.k === "lamp") {
      lights.push({ x: thing.x, y: thing.y - 50, radius: 240, color: thing.on ? GREEN : RED, power: 1 });
    }
  }
}

/** Health over whatever the bugs are going for right now. Screen space. */
export function drawUnitBars(ctx, quest, toScreen, zoom) {
  for (const unit of quest?.units || []) {
    if (!unit.hit && !unit.down) continue;
    const screen = toScreen(unit.x, unit.y);
    const small = PEOPLE[unit.sprite] || unit.sprite === "container";
    const lift = (unit.sprite === "container" ? 84 : small ? 62 : 128) * zoom;
    const width = small ? 56 : 76;
    const ratio = Math.max(0, Math.min(1, unit.hp / (unit.max_hp || 1)));
    ctx.fillStyle = "rgba(4, 6, 10, 0.85)";
    ctx.fillRect(screen.x - width / 2, screen.y - lift, width, 6);
    ctx.fillStyle = unit.down ? "#806068" : GREEN;
    ctx.fillRect(screen.x - width / 2 + 1, screen.y - lift + 1, Math.max(0.5, (width - 2) * ratio), 4);
    if (unit.down) {
      ctx.font = '12px "JetBrains Mono", ui-monospace, monospace';
      ctx.textAlign = "center";
      ctx.fillStyle = "#ffb0aa";
      ctx.fillText(PEOPLE[unit.sprite] ? "встаньте рядом" : "перезапуск…", screen.x, screen.y - lift - 8);
    }
  }
}
