/* Pixel magic: explosions as flipbooks, flames, ice, smoke and burnt floor.
 * Everything is baked on first use, so a frame costs one drawImage however fancy it looks. */

const TAU = Math.PI * 2;

function channels(hex) {
  const value = parseInt(String(hex).slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

function mix(a, b, amount) {
  const from = channels(a);
  const to = channels(b);
  const part = (index) => Math.round(from[index] + (to[index] - from[index]) * amount);
  return `#${[part(0), part(1), part(2)].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

function hash(x, y, seed = 0) {
  const value = Math.sin(x * 127.1 + y * 311.7 + seed * 74.7) * 43758.5453;
  return value - Math.floor(value);
}

function noise(x, y, seed = 0) {
  const left = Math.floor(x);
  const top = Math.floor(y);
  const fx = x - left;
  const fy = y - top;
  const ux = fx * fx * (3 - 2 * fx);
  const uy = fy * fy * (3 - 2 * fy);
  const a = hash(left, top, seed);
  const b = hash(left + 1, top, seed);
  const c = hash(left, top + 1, seed);
  const d = hash(left + 1, top + 1, seed);
  return a + (b - a) * ux + (c - a) * uy + (a - b - c + d) * ux * uy;
}

/** From the hottest colour to smoke, for whatever is burning. */
function rampFor(element, color) {
  let stops;
  if (element === "frost") stops = ["#ffffff", "#c8f6ff", "#6fd6ff", "#2f7fd0", "#1a3050"];
  else if (element === "emp") stops = ["#ffffff", "#e8dcff", "#b596ff", "#6a3fd0", "#241a40"];
  else if (element === "fire") stops = ["#fffbe6", "#ffd93d", "#ff8a1f", "#d9341a", "#35201c"];
  else stops = ["#ffffff", mix(color, "#ffffff", 0.55), color, mix(color, "#000000", 0.42), mix(color, "#000000", 0.8)];
  return stops.map(channels);
}

function bakeImage(width, height, paint) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;
  const image = ctx.createImageData(width, height);
  const put = (x, y, [r, g, b], alpha = 255) => {
    const at = (y * width + x) * 4;
    image.data[at] = r;
    image.data[at + 1] = g;
    image.data[at + 2] = b;
    image.data[at + 3] = alpha;
  };
  paint(put);
  ctx.putImageData(image, 0, 0);
  return canvas;
}

const CACHE_LIMIT = 500;
const cache = new Map();

function cached(key, make) {
  let value = cache.get(key);
  if (!value) {
    if (cache.size > CACHE_LIMIT) cache.clear();
    value = make();
    cache.set(key, value);
  }
  return value;
}

const BLAST_FRAMES = 11;
const BLAST_GRID = 60;

/** One frame of a blast: a lumpy ball that swells, hollows out and turns to smoke. */
export function blastFrame(element, color, progress) {
  const frame = Math.min(BLAST_FRAMES - 1, Math.floor(progress * BLAST_FRAMES));
  const tone = element === "fire" || element === "frost" || element === "emp" ? "" : color;
  return cached(`blast:${element}:${tone}:${frame}`, () => {
    const ramp = rampFor(element, color);
    const t = (frame + 0.5) / BLAST_FRAMES;
    const half = BLAST_GRID / 2;
    return bakeImage(BLAST_GRID, BLAST_GRID, (put) => {
      const swell = 0.3 + 0.7 * (1 - (1 - t) ** 2.2);
      const hollow = t < 0.42 ? 0 : ((t - 0.42) / 0.58) ** 1.35 * 0.92;
      for (let y = 0; y < BLAST_GRID; y += 1) {
        for (let x = 0; x < BLAST_GRID; x += 1) {
          const dx = (x + 0.5 - half) / half;
          const dy = (y + 0.5 - half) / half;
          const r = Math.hypot(dx, dy);
          if (r >= 1) continue;
          const big = noise(x * 0.16, y * 0.16, 3);
          const small = noise(x * 0.38, y * 0.38, 7);
          const outer = swell * (0.72 + big * 0.5) * 0.84;
          const inner = hollow * (0.72 + small * 0.55);
          if (r > outer || r < inner) continue;
          const heat = 1 - t * 1.25 + (1 - r / outer) * 0.55 - 0.12 + (small - 0.5) * 0.5;
          const index = heat > 1.05 ? 0 : heat > 0.8 ? 1 : heat > 0.55 ? 2 : heat > 0.3 ? 3 : 4;
          if (index === 4 && t > 0.55 && (x + y) % 2) continue;
          if (t > 0.8 && hash(x, y, frame) < (t - 0.8) * 4) continue;
          put(x, y, ramp[index]);
        }
      }
    });
  });
}

const FLAME_FRAMES = 6;

/** A fireball seen flying right: a hot nose and a torn tail. */
export function flameFrame(color, time) {
  const frame = Math.floor(time * 16) % FLAME_FRAMES;
  return cached(`flame:${color}:${frame}`, () => {
    const ramp = [
      channels("#fffbe6"),
      channels(mix(color, "#ffe9a8", 0.65)),
      channels(color),
      channels(mix(color, "#a01810", 0.6)),
    ];
    return bakeImage(34, 22, (put) => {
      for (let y = 0; y < 22; y += 1) {
        for (let x = 0; x < 34; x += 1) {
          const behind = x < 24;
          const u = (x - 24) / (behind ? 23 : 8);
          const taper = behind ? 1 - ((24 - x) / 30) * 0.8 : 1;
          const v = (y - 10.5) / (9 * taper);
          const d = Math.hypot(u, v);
          const churn = noise(x * 0.32 + frame * 1.5, y * 0.34 + frame * 0.6, 11);
          if (d > 0.72 + churn * 0.34) continue;
          const heat = 1 - d + (churn - 0.5) * 0.35 + (behind ? -0.08 : 0.18);
          put(x, y, ramp[heat > 0.68 ? 0 : heat > 0.44 ? 1 : heat > 0.22 ? 2 : 3]);
        }
      }
    });
  });
}

/** A shard of ice flying right, with one bright face and one in shadow. */
export function frostShard(color) {
  return cached(`shard:${color}`, () => {
    const light = channels("#f2fdff");
    const middle = channels(mix(color, "#ffffff", 0.55));
    const deep = channels(mix(color, "#103060", 0.3));
    return bakeImage(28, 15, (put) => {
      for (let x = 0; x < 28; x += 1) {
        const wide = x < 8 ? (x / 8) * 4 : x < 19 ? 4 + ((x - 8) / 11) * 3 : ((27 - x) / 8) * 7;
        for (let y = 0; y < 15; y += 1) {
          const off = y - 7;
          if (Math.abs(off) > wide) continue;
          const tone = off < -1 ? light : off < 2 ? middle : deep;
          put(x, y, x > 22 && Math.abs(off) < 2 ? light : tone);
        }
      }
    });
  });
}

/** A soft lump of gas: solid in the middle, dithered away at the edge. */
export function puffSprite(color, variant) {
  return cached(`puff:${color}:${variant}`, () => {
    const bright = channels(mix(color, "#ffffff", 0.3));
    const body = channels(color);
    const dark = channels(mix(color, "#000000", 0.4));
    return bakeImage(30, 30, (put) => {
      for (let y = 0; y < 30; y += 1) {
        for (let x = 0; x < 30; x += 1) {
          const r = Math.hypot(x - 14.5, y - 14.5) / 15;
          const lump = noise(x * 0.24, y * 0.24, variant + 20);
          const edge = 0.58 + lump * 0.42;
          if (r > edge) continue;
          if (r > edge * 0.78 && (x + y) % 2) continue;
          const shade = (y - 14.5) / 15 + (lump - 0.5);
          put(x, y, shade < -0.3 ? bright : shade < 0.35 ? body : dark);
        }
      }
    });
  });
}

/** What is left on the floor: a burn, a frosted patch, a violet scar. */
export function scorchSprite(element, color, variant) {
  const tone = element === "fire" || element === "frost" || element === "emp" ? "" : color;
  return cached(`scorch:${element}:${tone}:${variant}`, () => {
    const frost = element === "frost";
    const main = frost ? [205, 240, 255] : [10, 8, 10];
    const glowTone = frost ? "#ffffff" : element === "emp" ? "#b596ff" : element === "fire" ? "#ff8a1f" : color;
    const spark = channels(glowTone);
    return bakeImage(48, 48, (put) => {
      for (let y = 0; y < 48; y += 1) {
        for (let x = 0; x < 48; x += 1) {
          const r = Math.hypot(x - 23.5, y - 23.5) / 24;
          const lump = noise(x * 0.17, y * 0.17, variant + 40);
          const edge = 0.5 + lump * 0.55;
          if (r > edge) continue;
          const fine = hash(x, y, variant);
          if (r > edge * 0.72 && fine < 0.45) continue;
          if (fine > 0.985) {
            put(x, y, spark, 230);
          } else {
            put(x, y, main, frost ? 62 : Math.round(170 * (1 - r * 0.55)));
          }
        }
      }
      if (frost) {
        // Ice grows in straight lines from where it struck.
        for (let ray = 0; ray < 7; ray += 1) {
          const angle = (ray / 7) * TAU + variant;
          for (let step = 4; step < 20; step += 1) {
            put(Math.round(23.5 + Math.cos(angle) * step), Math.round(23.5 + Math.sin(angle) * step), [255, 255, 255], 96);
          }
        }
      }
    });
  });
}

/** A ring made of separate pixels, so it reads as magic rather than a drawn line. */
export function pixelRing(ctx, x, y, radius, cell, color, alpha, { gap = 0, seed = 0, squash = 1, turn = 0 } = {}) {
  if (radius <= 0 || alpha <= 0) return;
  const steps = Math.max(12, Math.min(140, Math.round((TAU * radius) / (cell * 1.4))));
  ctx.fillStyle = color;
  ctx.globalAlpha = Math.min(1, alpha);
  for (let step = 0; step < steps; step += 1) {
    if (gap && hash(step, seed) < gap) continue;
    const angle = (step / steps) * TAU + turn;
    ctx.fillRect(
      x + Math.cos(angle) * radius - cell / 2,
      y + Math.sin(angle) * radius * squash - cell / 2,
      cell,
      cell,
    );
  }
  ctx.globalAlpha = 1;
}

/** Straight pixels between two points: for rune lines that should not be antialiased mush. */
export function pixelLine(ctx, x1, y1, x2, y2, cell) {
  const steps = Math.max(1, Math.round(Math.hypot(x2 - x1, y2 - y1) / cell));
  for (let step = 0; step <= steps; step += 1) {
    const at = step / steps;
    ctx.fillRect(x1 + (x2 - x1) * at - cell / 2, y1 + (y2 - y1) * at - cell / 2, cell, cell);
  }
}

/** Lightning that keeps changing its mind: the path is fixed, the way along it is not. */
export function drawJaggedBolt(ctx, points, color, width, alpha, age, branchChance = 0.25) {
  if (points.length < 2 || alpha <= 0) return;
  const slot = Math.floor(age * 30);
  const path = [points[0]];
  const forks = [];
  for (let index = 1; index < points.length; index += 1) {
    const from = points[index - 1];
    const to = points[index];
    const length = Math.hypot(to.x - from.x, to.y - from.y);
    const pieces = Math.max(2, Math.min(9, Math.round(length / 34)));
    const nx = -(to.y - from.y) / (length || 1);
    const ny = (to.x - from.x) / (length || 1);
    for (let piece = 1; piece < pieces; piece += 1) {
      const at = piece / pieces;
      const swing = (hash(index, piece, slot) - 0.5) * Math.min(38, length * 0.2);
      const px = from.x + (to.x - from.x) * at + nx * swing;
      const py = from.y + (to.y - from.y) * at + ny * swing;
      path.push({ x: px, y: py });
      if (hash(piece, index, slot + 9) < branchChance) {
        const side = hash(piece, index, slot + 3) < 0.5 ? -1 : 1;
        const reach = 18 + hash(index, piece, slot + 5) * 36;
        forks.push([
          { x: px, y: py },
          { x: px + nx * side * reach * 0.6 + (ny * reach) / 2, y: py + ny * side * reach * 0.6 - (nx * reach) / 2 },
          { x: px + nx * side * reach + ny * reach, y: py + ny * side * reach - nx * reach },
        ]);
      }
    }
    path.push(to);
  }
  const trace = (line) => {
    ctx.beginPath();
    ctx.moveTo(line[0].x, line[0].y);
    for (let index = 1; index < line.length; index += 1) ctx.lineTo(line[index].x, line[index].y);
    ctx.stroke();
  };
  ctx.lineJoin = "miter";
  ctx.lineCap = "butt";
  ctx.strokeStyle = color;
  ctx.globalAlpha = alpha * 0.22;
  ctx.lineWidth = width * 3.2;
  trace(path);
  ctx.globalAlpha = alpha * 0.85;
  ctx.lineWidth = width;
  trace(path);
  ctx.lineWidth = width * 0.5;
  for (const fork of forks) trace(fork);
  ctx.strokeStyle = "#ffffff";
  ctx.globalAlpha = alpha;
  ctx.lineWidth = Math.max(1.2, width * 0.42);
  trace(path);
  ctx.globalAlpha = 1;
}

/** A four-armed star: the flash of something landing. */
export function drawStar(ctx, x, y, size, color, alpha, turn = 0) {
  if (alpha <= 0) return;
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(turn);
  ctx.globalAlpha = Math.min(1, alpha);
  ctx.fillStyle = color;
  const thin = Math.max(1.6, size * 0.14);
  ctx.fillRect(-size, -thin / 2, size * 2, thin);
  ctx.fillRect(-thin / 2, -size, thin, size * 2);
  ctx.fillStyle = "#ffffff";
  const core = Math.max(2, size * 0.3);
  ctx.fillRect(-core / 2, -core / 2, core, core);
  ctx.restore();
}

/* Python, as flying sparks: the mage is not chanting, the mage is typing. */
const GLYPHS = [
  ["##.", "#..", "##.", "#..", "##."],
  [".##", "..#", ".##", "..#", ".##"],
  [".#.", "#..", "#..", "#..", ".#."],
  [".#.", "..#", "..#", "..#", ".#."],
  ["...", "###", "...", "###", "..."],
  [".#.", "...", "...", ".#.", "..."],
  ["#.#", "#.#", "...", "...", "..."],
  ["..#", ".#.", "#..", ".#.", "..#"],
];

export function drawGlyph(ctx, x, y, cell, variant) {
  // Not every spark was told which symbol to be: any of them will do.
  const glyph = GLYPHS[Math.abs(Math.trunc(variant) || 0) % GLYPHS.length];
  for (let row = 0; row < glyph.length; row += 1) {
    for (let col = 0; col < glyph[row].length; col += 1) {
      if (glyph[row][col] === "#") ctx.fillRect(x + (col - 1.5) * cell, y + (row - 2.5) * cell, cell, cell);
    }
  }
}

export const VFX_TAU = TAU;
