/* Static floor, ruins and atmospheric set dressing for the Arcane 2D arena. */

const GOLD = "#d9b56c";
const TAU = Math.PI * 2;

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

function rgba(hex, alpha) {
  const value = hex.replace("#", "");
  const expanded =
    value.length === 3
      ? value
          .split("")
          .map((char) => char + char)
          .join("")
      : value;
  const number = parseInt(expanded, 16);
  if (!Number.isFinite(number)) return `rgba(217,181,108,${alpha})`;
  return `rgba(${(number >> 16) & 255},${(number >> 8) & 255},${number & 255},${alpha})`;
}

function starPath(ctx, cx, cy, points, outer, inner, rotation = 0) {
  ctx.beginPath();
  for (let index = 0; index < points * 2; index += 1) {
    const radius = index % 2 === 0 ? outer : inner;
    const angle = rotation + (index * Math.PI) / points;
    const x = cx + Math.cos(angle) * radius;
    const y = cy + Math.sin(angle) * radius;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
}

function drawRuneTick(ctx, x, y, angle, length, color, width = 1) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.beginPath();
  ctx.moveTo(0, -length * 0.5);
  ctx.lineTo(0, length * 0.5);
  ctx.moveTo(0, -length * 0.15);
  ctx.lineTo(length * 0.25, -length * 0.38);
  ctx.moveTo(0, length * 0.2);
  ctx.lineTo(-length * 0.22, length * 0.42);
  ctx.stroke();
  ctx.restore();
}

function hexChannels(hex) {
  const number = parseInt(hex.replace("#", ""), 16);
  return [(number >> 16) & 255, (number >> 8) & 255, number & 255];
}

function mix(hex, target, amount) {
  const from = hexChannels(hex);
  const to = hexChannels(target);
  const channels = from.map((value, index) =>
    Math.round(value + (to[index] - value) * Math.max(0, Math.min(1, amount))),
  );
  return `#${channels.map((value) => value.toString(16).padStart(2, "0")).join("")}`;
}

/** Smooth value noise: large, soft patches that make the floor feel laid by hand. */
function makeNoise(seed) {
  const lattice = (x, y) => {
    const random = seededRandom(Math.imul(x, 73856093) ^ Math.imul(y, 19349663) ^ seed);
    return random();
  };
  const fade = (t) => t * t * (3 - 2 * t);
  return (x, y) => {
    const gridX = Math.floor(x);
    const gridY = Math.floor(y);
    const u = fade(x - gridX);
    const v = fade(y - gridY);
    const top = lattice(gridX, gridY) * (1 - u) + lattice(gridX + 1, gridY) * u;
    const bottom = lattice(gridX, gridY + 1) * (1 - u) + lattice(gridX + 1, gridY + 1) * u;
    return top * (1 - v) + bottom * v;
  };
}

const STONES = ["#57516e", "#5f5877", "#4f4a64", "#676082", "#48435c", "#5b5570"];
const PLAZA_STONES = ["#6b6078", "#74687f", "#625871", "#7a6d84", "#5b5168"];
const MORTAR = "#25212f";

function paintFlagstone(ctx, x, y, width, height, base, random) {
  ctx.fillStyle = base;
  ctx.fillRect(x + 1, y + 1, width - 2, height - 2);
  ctx.fillStyle = "rgba(255, 240, 220, 0.07)";
  ctx.fillRect(x + 1, y + 1, width - 2, 3);
  ctx.fillRect(x + 1, y + 1, 3, height - 2);
  ctx.fillStyle = "rgba(10, 6, 18, 0.3)";
  ctx.fillRect(x + 1, y + height - 4, width - 2, 3);
  ctx.fillRect(x + width - 4, y + 1, 3, height - 2);

  const specks = Math.floor(random() * 4);
  for (let index = 0; index < specks; index += 1) {
    ctx.fillStyle = random() > 0.5 ? "rgba(255, 245, 230, 0.05)" : "rgba(10, 6, 18, 0.14)";
    ctx.fillRect(
      x + 6 + Math.floor(random() * Math.max(1, width - 15)),
      y + 7 + Math.floor(random() * Math.max(1, height - 15)),
      3 + Math.floor(random() * 3) * 3,
      3,
    );
  }
  if (random() < 0.14) {
    const crackX = x + 10 + Math.floor(random() * Math.max(1, width - 22));
    const crackY = y + 7;
    ctx.strokeStyle = "rgba(11, 6, 18, 0.55)";
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(crackX, crackY);
    ctx.lineTo(crackX + 5, crackY + 9);
    ctx.lineTo(crackX + 1, crackY + 16);
    if (random() > 0.5) ctx.lineTo(crackX + 8, crackY + 24);
    ctx.stroke();
  }
}

function paintFlagstones(ctx, width, height, random, noise) {
  const rowHeight = 46;
  for (let row = 0; row * rowHeight < height; row += 1) {
    const y = row * rowHeight;
    let x = -Math.floor(random() * 60);
    while (x < width) {
      const stoneWidth = 46 + Math.floor(random() * 5) * 14;
      let base = STONES[Math.floor(random() * STONES.length)];
      const moss = noise(x / 300, y / 300);
      const damp = noise(x / 210 + 40, y / 210 + 9);
      if (moss > 0.6) base = mix(base, "#4c6a4e", (moss - 0.6) * 1.5);
      if (damp > 0.62) base = mix(base, "#3f5b78", (damp - 0.62) * 1.3);
      paintFlagstone(ctx, x, y, stoneWidth, rowHeight, base, random);
      x += stoneWidth;
    }
  }
}

function paintPlaza(ctx, cx, cy, random) {
  const ringDepth = 44;
  ctx.fillStyle = MORTAR;
  ctx.beginPath();
  ctx.arc(cx, cy, 96 + ringDepth * 7, 0, TAU);
  ctx.fill();
  for (let ring = 0; ring < 7; ring += 1) {
    const inner = 96 + ring * ringDepth + 2;
    const outer = inner + ringDepth - 3;
    const count = Math.round((TAU * inner) / 82);
    const step = TAU / count;
    const offset = (ring % 2) * step * 0.5;
    for (let index = 0; index < count; index += 1) {
      const from = offset + index * step + 0.012;
      const to = offset + (index + 1) * step - 0.012;
      ctx.fillStyle = PLAZA_STONES[Math.floor(random() * PLAZA_STONES.length)];
      ctx.beginPath();
      ctx.arc(cx, cy, outer, from, to);
      ctx.arc(cx, cy, inner, to, from, true);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = "rgba(255, 240, 220, 0.06)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cx, cy, outer - 1, from, to);
      ctx.stroke();
    }
  }
}

function paintSeal(ctx) {
  ctx.strokeStyle = "rgba(240, 202, 125, 0.62)";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.arc(0, 0, 392, 0, TAU);
  ctx.stroke();
  ctx.strokeStyle = "rgba(169, 151, 255, 0.34)";
  ctx.lineWidth = 12;
  ctx.beginPath();
  ctx.arc(0, 0, 367, 0, TAU);
  ctx.stroke();

  ctx.lineWidth = 2;
  ctx.setLineDash([4, 13]);
  ctx.strokeStyle = "rgba(240, 202, 125, 0.56)";
  ctx.beginPath();
  ctx.arc(0, 0, 324, 0, TAU);
  ctx.stroke();
  ctx.setLineDash([18, 9, 2, 9]);
  ctx.strokeStyle = "rgba(169, 151, 255, 0.5)";
  ctx.beginPath();
  ctx.arc(0, 0, 262, 0, TAU);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.strokeStyle = "rgba(240, 202, 125, 0.42)";
  ctx.beginPath();
  ctx.arc(0, 0, 186, 0, TAU);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(0, 0, 118, 0, TAU);
  ctx.stroke();

  for (let index = 0; index < 16; index += 1) {
    const angle = (index / 16) * TAU + 0.06;
    const inner = index % 2 === 0 ? 128 : 143;
    ctx.strokeStyle =
      index % 4 === 0 ? "rgba(240, 202, 125, 0.6)" : "rgba(169, 151, 255, 0.46)";
    ctx.lineWidth = index % 4 === 0 ? 2.4 : 1.6;
    ctx.beginPath();
    ctx.moveTo(Math.cos(angle) * inner, Math.sin(angle) * inner);
    ctx.lineTo(Math.cos(angle) * 247, Math.sin(angle) * 247);
    ctx.stroke();
    drawRuneTick(
      ctx,
      Math.cos(angle) * 350,
      Math.sin(angle) * 350,
      angle + Math.PI / 2,
      18,
      rgba(GOLD, 0.56),
      2,
    );
  }

  starPath(ctx, 0, 0, 7, 330, 145, -Math.PI / 2);
  ctx.strokeStyle = "rgba(169, 151, 255, 0.32)";
  ctx.lineWidth = 1.6;
  ctx.stroke();
  starPath(ctx, 0, 0, 5, 214, 81, Math.PI / 2);
  ctx.strokeStyle = "rgba(240, 202, 125, 0.42)";
  ctx.stroke();
}

function paintWalls(ctx, width, height, border, random) {
  ctx.fillStyle = "#1c1826";
  ctx.fillRect(0, 0, width, border);
  ctx.fillRect(0, height - border, width, border);
  ctx.fillRect(0, 0, border, height);
  ctx.fillRect(width - border, 0, border, height);

  // The north wall faces the camera, so it reads as masonry rather than a rim.
  const courses = 3;
  const course = (border - 8) / courses;
  for (let row = 0; row < courses; row += 1) {
    const y = 8 + row * course;
    let x = row % 2 === 0 ? 0 : -34;
    while (x < width) {
      const blockWidth = 68 + Math.floor(random() * 3) * 12;
      paintFlagstone(
        ctx,
        x,
        y,
        blockWidth,
        course,
        mix("#3d3750", "#2f2a40", random()),
        random,
      );
      x += blockWidth;
    }
  }
  ctx.fillStyle = "#6a6280";
  ctx.fillRect(0, 0, width, 5);
  ctx.fillStyle = "rgba(240, 202, 125, 0.34)";
  ctx.fillRect(0, 5, width, 2);

  // Soft contact shadow where the wall meets the floor.
  const shade = ctx.createLinearGradient(0, border, 0, border + 74);
  shade.addColorStop(0, "rgba(8, 5, 14, 0.62)");
  shade.addColorStop(1, "rgba(8, 5, 14, 0)");
  ctx.fillStyle = shade;
  ctx.fillRect(border, border, width - border * 2, 74);
}

export function buildFloorCanvas(config) {
  const width = config?.arena?.w || 1900;
  const height = config?.arena?.h || 1100;
  const border = config?.arena?.border || 46;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;
  const random = seededRandom(1947);
  const noise = makeNoise(1947);
  const cx = width / 2;
  const cy = height / 2;

  ctx.fillStyle = MORTAR;
  ctx.fillRect(0, 0, width, height);
  paintFlagstones(ctx, width, height, random, noise);
  paintPlaza(ctx, cx, cy, random);

  ctx.save();
  ctx.translate(cx, cy);
  paintSeal(ctx);
  ctx.restore();

  // Hairline cracks wander out from the central seal.
  for (let index = 0; index < 26; index += 1) {
    const angle = random() * TAU;
    let x = cx + Math.cos(angle) * (80 + random() * 230);
    let y = cy + Math.sin(angle) * (80 + random() * 230);
    let direction = angle + (random() - 0.5) * 1.2;
    ctx.strokeStyle = `rgba(8, 5, 14, ${0.34 + random() * 0.2})`;
    ctx.lineWidth = 1.4 + random();
    ctx.beginPath();
    ctx.moveTo(x, y);
    const segments = 4 + Math.floor(random() * 6);
    for (let step = 0; step < segments; step += 1) {
      direction += (random() - 0.5) * 0.65;
      const length = 10 + random() * 31;
      x += Math.cos(direction) * length;
      y += Math.sin(direction) * length;
      ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  // Moss gathers where the damp patches are, thickest along the walls.
  const greens = ["#40603f", "#527349", "#35503a", "#6a8a55"];
  for (let index = 0; index < 900; index += 1) {
    const x = border + random() * (width - border * 2);
    const y = border + random() * (height - border * 2);
    const edge = Math.min(x - border, y - border, width - border - x, height - border - y);
    const chance = noise(x / 300, y / 300) - 0.46 + Math.max(0, 0.12 - edge / 900);
    if (random() > chance * 2.4 || Math.hypot(x - cx, y - cy) < 400) continue;
    ctx.fillStyle = greens[Math.floor(random() * greens.length)];
    const size = 3 + Math.floor(random() * 3) * 3;
    ctx.fillRect(Math.round(x / 3) * 3, Math.round(y / 3) * 3, size, 3 + (size > 6 ? 3 : 0));
  }

  // Worn summoning circles mark where mages arrive.
  for (const spawn of config?.spawns || []) {
    ctx.strokeStyle = "rgba(169, 151, 255, 0.3)";
    ctx.lineWidth = 2.4;
    ctx.setLineDash([8, 9]);
    ctx.beginPath();
    ctx.arc(spawn.x, spawn.y, 38, 0, TAU);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.strokeStyle = "rgba(240, 202, 125, 0.24)";
    ctx.beginPath();
    ctx.arc(spawn.x, spawn.y, 25, 0, TAU);
    ctx.stroke();
  }

  paintWalls(ctx, width, height, border, random);
  return canvas;
}

const MOTES = Array.from({ length: 86 }, (_, index) => {
  const random = seededRandom(9100 + index * 71);
  return {
    x: 70 + random() * 1760,
    y: 70 + random() * 960,
    size: 0.55 + random() * 1.45,
    speed: 0.25 + random() * 0.8,
    phase: random() * TAU,
    drift: 10 + random() * 38,
    violet: random() > 0.68,
  };
});

export function drawAmbient(ctx, config, now, zoom) {
  const width = config?.arena?.w || 1900;
  const height = config?.arena?.h || 1100;
  const cx = width / 2;
  const cy = height / 2;
  const t = now / 1000;

  ctx.save();
  ctx.globalCompositeOperation = "screen";

  const fogOne = ctx.createRadialGradient(
    cx + Math.sin(t * 0.045) * 210,
    cy + Math.cos(t * 0.037) * 110,
    30,
    cx + Math.sin(t * 0.045) * 210,
    cy + Math.cos(t * 0.037) * 110,
    520,
  );
  fogOne.addColorStop(0, "rgba(103, 84, 178, 0.09)");
  fogOne.addColorStop(1, "rgba(103, 84, 178, 0)");
  ctx.fillStyle = fogOne;
  ctx.fillRect(0, 0, width, height);

  const fogTwo = ctx.createRadialGradient(
    cx - 430 + Math.cos(t * 0.028) * 150,
    cy + 260 + Math.sin(t * 0.033) * 80,
    20,
    cx - 430 + Math.cos(t * 0.028) * 150,
    cy + 260 + Math.sin(t * 0.033) * 80,
    390,
  );
  fogTwo.addColorStop(0, "rgba(240, 202, 125, 0.065)");
  fogTwo.addColorStop(1, "rgba(240, 202, 125, 0)");
  ctx.fillStyle = fogTwo;
  ctx.fillRect(0, 0, width, height);

  ctx.lineWidth = Math.max(0.7, 1.1 / zoom);
  for (let index = 0; index < 3; index += 1) {
    const radius = 242 + index * 61;
    const start = t * (index % 2 === 0 ? 0.035 : -0.023) + index * 2.1;
    ctx.strokeStyle =
      index === 1
        ? `rgba(169, 151, 255, ${0.075 + Math.sin(t * 0.5) * 0.018})`
        : `rgba(217, 181, 108, ${0.07 + Math.sin(t * 0.4 + index) * 0.015})`;
    ctx.setLineDash(index === 1 ? [3, 16] : [29, 18]);
    ctx.beginPath();
    ctx.arc(cx, cy, radius, start, start + 1.6 + index * 0.38);
    ctx.stroke();
  }
  ctx.setLineDash([]);

  const altarGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 152);
  const pulse = 0.5 + Math.sin(t * 0.75) * 0.5;
  altarGlow.addColorStop(0, `rgba(169, 151, 255, ${0.08 + pulse * 0.025})`);
  altarGlow.addColorStop(0.5, "rgba(217, 181, 108, 0.03)");
  altarGlow.addColorStop(1, "rgba(217, 181, 108, 0)");
  ctx.fillStyle = altarGlow;
  ctx.fillRect(cx - 160, cy - 160, 320, 320);

  for (const mote of MOTES) {
    const x =
      mote.x +
      Math.sin(t * mote.speed + mote.phase) * mote.drift +
      Math.cos(t * 0.11 + mote.phase) * 9;
    const y =
      mote.y +
      Math.cos(t * mote.speed * 0.72 + mote.phase) * mote.drift * 0.58;
    const alpha =
      0.08 +
      Math.max(0, Math.sin(t * 0.6 + mote.phase * 1.7)) * 0.22;
    ctx.fillStyle = mote.violet
      ? `rgba(169, 151, 255, ${alpha})`
      : `rgba(232, 199, 130, ${alpha})`;
    ctx.beginPath();
    ctx.arc(x, y, mote.size, 0, TAU);
    ctx.fill();
    if (mote.size > 1.55) {
      ctx.fillStyle = mote.violet
        ? `rgba(169, 151, 255, ${alpha * 0.12})`
        : `rgba(232, 199, 130, ${alpha * 0.12})`;
      ctx.beginPath();
      ctx.arc(x, y, mote.size * 5, 0, TAU);
      ctx.fill();
    }
  }
  ctx.restore();
}

function disc(ctx, x, y, rx, ry, fill) {
  ctx.fillStyle = fill;
  ctx.beginPath();
  ctx.ellipse(x, y, rx, ry, 0, 0, TAU);
  ctx.fill();
}

/** A drum seen from above and in front; `shades` run from its left edge to its right. */
function cylinder(ctx, x, top, bottom, rx, ry, shades, cap) {
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(x - rx, top);
  ctx.lineTo(x - rx, bottom);
  ctx.ellipse(x, bottom, rx, ry, 0, Math.PI, 0, true);
  ctx.lineTo(x + rx, top);
  ctx.closePath();
  ctx.clip();
  const band = (rx * 2) / shades.length;
  shades.forEach((shade, index) => {
    ctx.fillStyle = shade;
    ctx.fillRect(x - rx + index * band, top - 2, Math.ceil(band) + 1, bottom - top + ry + 4);
  });
  ctx.restore();
  disc(ctx, x, top, rx, ry, cap);
}

const STONE_SHADES = ["#332e42", "#463f58", "#5c5470", "#6c6483", "#5a5270", "#413a53", "#2b2739"];
const DARK_SHADES = ["#26222f", "#332e40", "#423b52", "#4c4560", "#3f3950", "#2f2a3b", "#211d2a"];

function bakeSprite(width, height, anchorX, anchorY, paint) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.translate(anchorX, anchorY);
    paint(ctx);
  }
  return { canvas, anchorX, anchorY };
}

function bakePillar(r) {
  const top = -116;
  return bakeSprite(Math.ceil(r * 2.5), Math.ceil(r * 1.2 + 156), Math.ceil(r * 1.25), 136, (ctx) => {
    disc(ctx, 10, 8, r * 1.14, r * 0.86, "rgba(4, 2, 8, 0.46)");
    cylinder(ctx, 0, -12, 0, r, r * 0.76, DARK_SHADES, "#4f4862");
    const shaft = r * 0.66;
    cylinder(ctx, 0, top + 14, -12, shaft, shaft * 0.56, STONE_SHADES, "#6b6382");
    // Mortar courses and a few weathered joints.
    const random = seededRandom(r * 31);
    for (let y = top + 34; y < -12; y += 22) {
      ctx.fillStyle = "rgba(14, 10, 22, 0.5)";
      ctx.fillRect(-shaft, y, shaft * 2, 2);
      ctx.fillStyle = "rgba(255, 240, 220, 0.07)";
      ctx.fillRect(-shaft, y + 2, shaft * 2, 2);
      ctx.fillStyle = "rgba(14, 10, 22, 0.42)";
      ctx.fillRect(-shaft * 0.6 + random() * shaft * 1.2, y - 20, 2, 20);
    }
    cylinder(ctx, 0, top, top + 14, r * 0.86, r * 0.46, STONE_SHADES, "#7a7290");
    ctx.fillStyle = "rgba(217, 181, 108, 0.75)";
    ctx.fillRect(-r * 0.86, top + 10, r * 1.72, 3);
    cylinder(ctx, 0, top - 12, top, r * 0.5, r * 0.26, DARK_SHADES, "#17131d");
    disc(ctx, 0, top - 12, r * 0.4, r * 0.2, "#c8491d");
    disc(ctx, 0, top - 12, r * 0.24, r * 0.12, "#ffb347");
  });
}

function bakeCrystal(r) {
  const shard = (ctx, x, base, wide, tall, lean, light, dark) => {
    ctx.fillStyle = light;
    ctx.beginPath();
    ctx.moveTo(x + lean, base - tall);
    ctx.lineTo(x - wide, base - tall * 0.26);
    ctx.lineTo(x, base);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = dark;
    ctx.beginPath();
    ctx.moveTo(x + lean, base - tall);
    ctx.lineTo(x + wide, base - tall * 0.3);
    ctx.lineTo(x, base);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "rgba(226, 255, 250, 0.82)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x + lean, base - tall);
    ctx.lineTo(x, base - 3);
    ctx.stroke();
  };
  return bakeSprite(Math.ceil(r * 4), Math.ceil(r * 5), Math.ceil(r * 2), Math.ceil(r * 3.9), (ctx) => {
    disc(ctx, 8, 8, r * 1.3, r * 0.74, "rgba(4, 2, 8, 0.44)");
    disc(ctx, 0, 4, r * 1.16, r * 0.72, "#2c2840");
    disc(ctx, 0, 2, r * 0.96, r * 0.56, "#3d3756");
    shard(ctx, -r * 0.66, 6, r * 0.42, r * 1.6, -r * 0.16, "#7fe6d4", "#3a7f90");
    shard(ctx, r * 0.62, 8, r * 0.46, r * 1.9, r * 0.2, "#93eedd", "#3f6f92");
    shard(ctx, 0, 12, r * 0.62, r * 3, -r * 0.05, "#b5fff0", "#4a8fa6");
  });
}

function bakeAltar(r) {
  return bakeSprite(Math.ceil(r * 2.5), Math.ceil(r * 2.4), Math.ceil(r * 1.25), Math.ceil(r * 1.45), (ctx) => {
    disc(ctx, 10, 10, r * 1.16, r * 0.92, "rgba(4, 2, 8, 0.5)");
    cylinder(ctx, 0, -14, 0, r * 1.06, r * 0.82, DARK_SHADES, "#544c66");
    cylinder(ctx, 0, -28, -14, r * 0.82, r * 0.62, STONE_SHADES, "#625a76");
    cylinder(ctx, 0, -42, -28, r * 0.58, r * 0.44, STONE_SHADES, "#2b2638");
    ctx.lineWidth = 2.4;
    ctx.strokeStyle = "rgba(217, 181, 108, 0.8)";
    ctx.beginPath();
    ctx.ellipse(0, -28, r * 0.72, r * 0.54, 0, 0, TAU);
    ctx.stroke();
    ctx.beginPath();
    ctx.ellipse(0, -14, r * 0.94, r * 0.72, 0, 0, TAU);
    ctx.stroke();
    ctx.strokeStyle = "rgba(169, 151, 255, 0.72)";
    ctx.beginPath();
    ctx.ellipse(0, -42, r * 0.46, r * 0.34, 0, 0, TAU);
    ctx.stroke();
    for (let index = 0; index < 8; index += 1) {
      const angle = (index / 8) * TAU;
      ctx.fillStyle = index % 2 === 0 ? "rgba(240, 202, 125, 0.9)" : "rgba(169, 151, 255, 0.86)";
      ctx.fillRect(Math.cos(angle) * r * 0.82 - 2, -14 + Math.sin(angle) * r * 0.62 - 2, 4, 4);
    }
  });
}

function bakeRuin(r) {
  return bakeSprite(Math.ceil(r * 3.6), Math.ceil(r * 3.4), Math.ceil(r * 1.7), Math.ceil(r * 2.3), (ctx) => {
    const random = seededRandom(r * 17);
    disc(ctx, 8, 8, r * 1.3, r * 0.86, "rgba(4, 2, 8, 0.42)");
    cylinder(ctx, 0, -8, 0, r, r * 0.74, DARK_SHADES, "#4a4358");
    const stub = r * 0.72;
    cylinder(ctx, 0, -52, -8, stub, stub * 0.56, STONE_SHADES, "#6b6382");
    // A snapped top: the jagged edge is what sells this as a broken column.
    ctx.fillStyle = "#231f2e";
    ctx.beginPath();
    ctx.moveTo(-stub - 2, -58);
    for (let index = 0; index <= 6; index += 1) {
      ctx.lineTo(-stub + (index / 6) * stub * 2, -52 + (index % 2 ? 12 : -2) + random() * 6);
    }
    ctx.lineTo(stub + 2, -58);
    ctx.lineTo(stub + 2, -74);
    ctx.lineTo(-stub - 2, -74);
    ctx.closePath();
    ctx.globalCompositeOperation = "destination-out";
    ctx.fill();
    ctx.globalCompositeOperation = "source-over";
    for (let index = 0; index < 5; index += 1) {
      const x = -r * 1.1 + random() * r * 2.3;
      const y = r * 0.1 + random() * r * 0.5;
      const size = 6 + Math.floor(random() * 4) * 3;
      ctx.fillStyle = "#17131d";
      ctx.fillRect(x + 2, y + 2, size, size * 0.7);
      ctx.fillStyle = index % 2 ? "#57506b" : "#403a50";
      ctx.fillRect(x, y, size, size * 0.7);
    }
  });
}

const OBSTACLE_BAKERS = { altar: bakeAltar, crystal: bakeCrystal, ruin: bakeRuin, pillar: bakePillar };
export const OBSTACLE_HEIGHT = { altar: 130, crystal: 90, ruin: 62, pillar: 150 };
const sprites = new Map();

function spriteFor(kind, r) {
  const key = `${kind}:${r}`;
  let sprite = sprites.get(key);
  if (!sprite) {
    sprite = (OBSTACLE_BAKERS[kind] || bakePillar)(r);
    sprites.set(key, sprite);
  }
  return sprite;
}

const FIRE = ["#d8391b", "#ff8a1f", "#ffcf4d", "#fff6cf"];

/** Layered pixel flame; `size` is its height in world units. */
export function drawFlame(ctx, x, y, size, t, seed, palette = FIRE) {
  const layers = [
    [palette[0], 1, 1],
    [palette[1], 0.72, 0.74],
    [palette[2], 0.46, 0.5],
    [palette[3], 0.22, 0.28],
  ];
  const blockSize = Math.max(3, size / 7);
  for (const [color, tall, wide] of layers) {
    ctx.fillStyle = color;
    const rows = Math.max(2, Math.round((size * tall) / blockSize));
    for (let row = 0; row < rows; row += 1) {
      const at = row / rows;
      const width = size * 0.6 * wide * (1 - at * at);
      const sway = Math.sin(t * 8 + seed + row * 0.9) * at * size * 0.16;
      const flicker = 1 + Math.sin(t * 13 + seed * 2 + row) * 0.12;
      ctx.fillRect(
        x + sway - (width * flicker) / 2,
        y - row * blockSize - blockSize,
        width * flicker,
        blockSize,
      );
    }
  }
}

function drawOrb(ctx, x, y, t) {
  const pulse = 0.5 + Math.sin(t * 1.6) * 0.5;
  const hover = y + Math.sin(t * 1.1) * 5;
  ctx.save();
  ctx.translate(x, hover);
  ctx.strokeStyle = `rgba(240, 202, 125, ${0.6 + pulse * 0.3})`;
  ctx.lineWidth = 2.2;
  for (let index = 0; index < 2; index += 1) {
    ctx.beginPath();
    ctx.ellipse(0, 0, 30, 11, t * (index ? -0.7 : 0.9) + index * 1.2, 0, TAU);
    ctx.stroke();
  }
  ctx.globalCompositeOperation = "lighter";
  disc(ctx, 0, 0, 24 + pulse * 5, 24 + pulse * 5, `rgba(150, 120, 255, ${0.14 + pulse * 0.1})`);
  disc(ctx, 0, 0, 15, 15, "rgba(190, 165, 255, 0.5)");
  ctx.globalCompositeOperation = "source-over";
  disc(ctx, 0, 0, 9, 9, "#efe6ff");
  disc(ctx, -2, -3, 3.5, 3.5, "#ffffff");
  ctx.restore();
}

function drawRisingMotes(ctx, x, y, color, t, seed) {
  ctx.fillStyle = color;
  for (let index = 0; index < 4; index += 1) {
    const rise = (t * 22 + index * 17 + seed * 7) % 52;
    ctx.globalAlpha = Math.max(0, 1 - rise / 52) * 0.9;
    ctx.fillRect(x + Math.sin(t * 1.4 + index * 2 + seed) * 16 - 1.5, y - rise, 3, 3);
  }
  ctx.globalAlpha = 1;
}

/** Draw one obstacle where it stands; `alpha` thins it when it hides the player. */
export function drawObstacle(ctx, obstacle, now, alpha = 1) {
  const { x, y, r, kind } = obstacle;
  const sprite = spriteFor(kind, r);
  const t = now / 1000;
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.drawImage(sprite.canvas, x - sprite.anchorX, y - sprite.anchorY);
  if (kind === "pillar") {
    drawFlame(ctx, x, y - 130, 34, t, x * 0.01 + y * 0.003);
  } else if (kind === "altar") {
    drawOrb(ctx, x, y - 92, t);
  } else if (kind === "crystal") {
    drawRisingMotes(ctx, x, y - r * 1.6, "#b5fff0", t, x * 0.02 + y * 0.01);
  }
  ctx.restore();
}

/** Sconces along the north wall, spaced to clear the centre of the view. */
function torchesFor(config) {
  const width = config?.arena?.w || 1900;
  const border = config?.arena?.border || 46;
  const span = (width - border * 2) / 6;
  return Array.from({ length: 6 }, (_, index) => ({
    x: border + span * (index + 0.5),
    y: border - 12,
  }));
}

export function drawWallTorches(ctx, config, now) {
  const t = now / 1000;
  for (const torch of torchesFor(config)) {
    ctx.fillStyle = "#17131d";
    ctx.fillRect(torch.x - 7, torch.y - 4, 14, 8);
    ctx.fillRect(torch.x - 3, torch.y + 2, 6, 12);
    ctx.fillStyle = "#6a5a43";
    ctx.fillRect(torch.x - 7, torch.y - 6, 14, 3);
    drawFlame(ctx, torch.x, torch.y - 4, 20, t, torch.x * 0.013);
  }
}

/** Every light the room itself provides, flickering, in world coordinates. */
export function collectWorldLights(config, now, lights) {
  const t = now / 1000;
  for (const obstacle of config?.obstacles || []) {
    const { x, y, kind } = obstacle;
    if (kind === "pillar") {
      const flicker = 0.9 + Math.sin(t * 9 + x) * 0.06 + Math.sin(t * 17 + y) * 0.05;
      lights.push({ x, y: y - 40, radius: 300 * flicker, color: "#ffab5e", power: 0.92 });
    } else if (kind === "altar") {
      const pulse = 0.9 + Math.sin(t * 1.6) * 0.1;
      lights.push({ x, y: y - 20, radius: 430 * pulse, color: "#a58cff", power: 0.8 });
      lights.push({ x, y, radius: 240, color: "#ffe2a8", power: 0.42 });
    } else if (kind === "crystal") {
      const pulse = 0.88 + Math.sin(t * 1.15 + x * 0.1) * 0.12;
      lights.push({ x, y: y - 26, radius: 270 * pulse, color: "#74e8d4", power: 0.85 });
    } else {
      lights.push({ x, y: y - 20, radius: 170, color: "#a58cff", power: 0.45 });
    }
  }
  for (const torch of torchesFor(config)) {
    const flicker = 0.92 + Math.sin(t * 11 + torch.x) * 0.08;
    lights.push({
      x: torch.x,
      y: torch.y + 26,
      radius: 250 * flicker,
      color: "#ffa95a",
      power: 0.88,
    });
  }
}

export function drawArenaBorder(ctx, config, now, zoom) {
  const width = config?.arena?.w || 1900;
  const height = config?.arena?.h || 1100;
  const border = config?.arena?.border || 46;
  const line = Math.max(0.8, 1.1 / zoom);

  ctx.save();
  ctx.lineWidth = line;
  ctx.strokeStyle = "rgba(240, 202, 125, 0.42)";
  ctx.strokeRect(border, border, width - border * 2, height - border * 2);
  ctx.strokeStyle = "rgba(169, 151, 255, 0.22)";
  ctx.strokeRect(border + 7, border + 7, width - border * 2 - 14, height - border * 2 - 14);

  ctx.lineWidth = Math.max(2, 4 / zoom);
  ctx.strokeStyle = "rgba(18, 12, 26, 0.9)";
  ctx.strokeRect(border - 2, border - 2, width - border * 2 + 4, height - border * 2 + 4);

  const corners = [
    [border, border, 0],
    [width - border, border, Math.PI / 2],
    [width - border, height - border, Math.PI],
    [border, height - border, -Math.PI / 2],
  ];
  ctx.strokeStyle = "rgba(240, 202, 125, 0.52)";
  ctx.lineWidth = line;
  for (const [x, y, angle] of corners) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(angle);
    ctx.beginPath();
    ctx.arc(0, 0, 25, 0, Math.PI / 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(13, 0);
    ctx.lineTo(13, 13);
    ctx.lineTo(0, 13);
    ctx.stroke();
    ctx.fillStyle = "rgba(240, 202, 125, 0.62)";
    ctx.beginPath();
    ctx.arc(21, 21, 1.4, 0, TAU);
    ctx.fill();
    ctx.restore();
  }

  const pulse = 0.11 + Math.sin(now / 1600) * 0.035;
  ctx.strokeStyle = `rgba(169, 151, 255, ${pulse})`;
  ctx.lineWidth = Math.max(0.7, line);
  for (let x = border + 95; x < width - border - 40; x += 132) {
    ctx.beginPath();
    ctx.moveTo(x, border - 3);
    ctx.lineTo(x + 18, border + 3);
    ctx.lineTo(x + 36, border - 3);
    ctx.moveTo(x, height - border + 3);
    ctx.lineTo(x + 18, height - border - 3);
    ctx.lineTo(x + 36, height - border + 3);
    ctx.stroke();
  }
  for (let y = border + 95; y < height - border - 40; y += 132) {
    ctx.beginPath();
    ctx.moveTo(border - 3, y);
    ctx.lineTo(border + 3, y + 18);
    ctx.lineTo(border - 3, y + 36);
    ctx.moveTo(width - border + 3, y);
    ctx.lineTo(width - border - 3, y + 18);
    ctx.lineTo(width - border + 3, y + 36);
    ctx.stroke();
  }
  ctx.restore();
}
