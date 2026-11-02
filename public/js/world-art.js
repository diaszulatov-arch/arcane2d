/* Static floor, ruins and atmospheric set dressing for the Arcane 2D arena. */

const GOLD = "#d9b56c";
const VIOLET = "#a997ff";
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

  ctx.fillStyle = "#120d1c";
  ctx.fillRect(0, 0, width, height);

  const baseGlow = ctx.createRadialGradient(
    width / 2,
    height / 2,
    40,
    width / 2,
    height / 2,
    width * 0.64,
  );
  baseGlow.addColorStop(0, "#302046");
  baseGlow.addColorStop(0.42, "#211830");
  baseGlow.addColorStop(1, "#120d1c");
  ctx.fillStyle = baseGlow;
  ctx.fillRect(0, 0, width, height);

  // Staggered chunky flagstones. The brick pattern avoids a graph-paper look.
  const blockW = 64;
  const blockH = 40;
  const stones = ["#35274e", "#3b2b56", "#2f2246", "#402f5c", "#2b1f40"];
  for (let row = 0; row * blockH < height + blockH; row += 1) {
    const y = row * blockH;
    const offset = row % 2 === 0 ? 0 : blockW / 2;
    for (let baseX = -offset; baseX < width + blockW; baseX += blockW) {
      const x = baseX + 2;
      const w = blockW - 4;
      const h = blockH - 4;
      const stone = stones[Math.floor(random() * stones.length)];
      ctx.fillStyle = "#1b1326";
      ctx.fillRect(baseX, y, blockW, blockH);
      ctx.fillStyle = stone;
      ctx.fillRect(x, y + 2, w, h);
      ctx.fillStyle = `rgba(255, 226, 186, ${0.035 + random() * 0.03})`;
      ctx.fillRect(x, y + 2, w, 2);
      ctx.fillRect(x, y + 2, 2, h);
      ctx.fillStyle = "rgba(10, 6, 18, 0.42)";
      ctx.fillRect(x, y + 2 + h - 2, w, 2);
      ctx.fillRect(x + w - 2, y + 2, 2, h);

      if (random() < 0.38) {
        const chipX = x + 6 + Math.floor(random() * (w - 18));
        const chipY = y + 7 + Math.floor(random() * (h - 14));
        ctx.fillStyle = random() > 0.55 ? "#463563" : "#21172f";
        ctx.fillRect(chipX, chipY, 4 + Math.floor(random() * 3) * 3, 3);
        ctx.fillStyle = "rgba(11, 6, 18, 0.45)";
        ctx.fillRect(chipX, chipY + 3, 4 + Math.floor(random() * 2) * 3, 2);
      }

      if (random() < 0.2) {
        const crackX = x + 8 + Math.floor(random() * (w - 16));
        const crackY = y + 8 + Math.floor(random() * (h - 16));
        ctx.strokeStyle = "rgba(11, 6, 18, 0.66)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(crackX, crackY);
        ctx.lineTo(crackX + 6, crackY + 5);
        ctx.lineTo(crackX + 2, crackY + 11);
        if (random() > 0.5) {
          ctx.lineTo(crackX + 9, crackY + 15);
        }
        ctx.stroke();
      }

      if (random() < 0.025) {
        ctx.fillStyle = "rgba(159, 128, 231, 0.2)";
        ctx.fillRect(x + 8, y + 10, 3, 3);
      }
    }
  }

  const cx = width / 2;
  const cy = height / 2;

  // Great ritual seal.
  ctx.save();
  ctx.translate(cx, cy);
  ctx.strokeStyle = "rgba(240, 202, 125, 0.34)";
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.arc(0, 0, 392, 0, TAU);
  ctx.stroke();
  ctx.strokeStyle = "rgba(169, 151, 255, 0.19)";
  ctx.lineWidth = 10;
  ctx.beginPath();
  ctx.arc(0, 0, 367, 0, TAU);
  ctx.stroke();

  ctx.setLineDash([4, 13]);
  ctx.strokeStyle = "rgba(240, 202, 125, 0.34)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(0, 0, 324, 0, TAU);
  ctx.stroke();
  ctx.setLineDash([18, 9, 2, 9]);
  ctx.strokeStyle = "rgba(169, 151, 255, 0.28)";
  ctx.beginPath();
  ctx.arc(0, 0, 262, 0, TAU);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.strokeStyle = "rgba(240, 202, 125, 0.24)";
  ctx.beginPath();
  ctx.arc(0, 0, 186, 0, TAU);
  ctx.stroke();
  ctx.strokeStyle = "rgba(240, 202, 125, 0.18)";
  ctx.beginPath();
  ctx.arc(0, 0, 118, 0, TAU);
  ctx.stroke();

  for (let index = 0; index < 16; index += 1) {
    const angle = (index / 16) * TAU + 0.06;
    const inner = index % 2 === 0 ? 128 : 143;
    ctx.strokeStyle =
      index % 4 === 0
        ? "rgba(240, 202, 125, 0.42)"
        : "rgba(169, 151, 255, 0.3)";
    ctx.lineWidth = index % 4 === 0 ? 1.5 : 1;
    ctx.beginPath();
    ctx.moveTo(Math.cos(angle) * inner, Math.sin(angle) * inner);
    ctx.lineTo(Math.cos(angle) * 247, Math.sin(angle) * 247);
    ctx.stroke();
    drawRuneTick(
      ctx,
      Math.cos(angle) * 350,
      Math.sin(angle) * 350,
      angle + Math.PI / 2,
      15,
      rgba(GOLD, 0.3),
      1.2,
    );
  }

  starPath(ctx, 0, 0, 7, 330, 145, -Math.PI / 2);
  ctx.strokeStyle = "rgba(169, 151, 255, 0.18)";
  ctx.lineWidth = 1;
  ctx.stroke();
  starPath(ctx, 0, 0, 5, 214, 81, Math.PI / 2);
  ctx.strokeStyle = "rgba(240, 202, 125, 0.24)";
  ctx.stroke();
  ctx.restore();

  // Hairline cracks wander out from the central seal.
  for (let index = 0; index < 26; index += 1) {
    const angle = random() * TAU;
    let x = cx + Math.cos(angle) * (80 + random() * 230);
    let y = cy + Math.sin(angle) * (80 + random() * 230);
    let direction = angle + (random() - 0.5) * 1.2;
    ctx.strokeStyle = `rgba(8, 5, 14, ${0.3 + random() * 0.18})`;
    ctx.lineWidth = 0.7 + random();
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

  // Fine constellations of dust and mica embedded in the floor.
  for (let index = 0; index < 360; index += 1) {
    const x = border + random() * (width - border * 2);
    const y = border + random() * (height - border * 2);
    const distance = Math.hypot(x - cx, y - cy);
    if (distance < 90 || random() < 0.36) continue;
    ctx.fillStyle =
      random() > 0.7
        ? `rgba(240, 202, 125, ${0.08 + random() * 0.16})`
        : `rgba(206, 214, 244, ${0.06 + random() * 0.12})`;
    ctx.beginPath();
    ctx.arc(x, y, 0.4 + random() * 1.1, 0, TAU);
    ctx.fill();
  }

  // A faded frame around the playable field.
  ctx.strokeStyle = "rgba(240, 202, 125, 0.24)";
  ctx.lineWidth = 1;
  ctx.strokeRect(border + 7, border + 7, width - border * 2 - 14, height - border * 2 - 14);

  const vignette = ctx.createRadialGradient(
    cx,
    cy,
    Math.min(width, height) * 0.2,
    cx,
    cy,
    Math.max(width, height) * 0.7,
  );
  vignette.addColorStop(0, "rgba(10, 6, 18, 0)");
  vignette.addColorStop(1, "rgba(10, 6, 18, 0.34)");
  ctx.fillStyle = vignette;
  ctx.fillRect(0, 0, width, height);

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

function drawPillar(ctx, obstacle, now, zoom) {
  const { x, y, r } = obstacle;
  const t = now / 1000;
  ctx.save();
  ctx.translate(x, y);

  ctx.fillStyle = "rgba(0, 0, 0, 0.42)";
  ctx.beginPath();
  ctx.ellipse(5, 9, r * 1.12, r * 0.92, 0.15, 0, TAU);
  ctx.fill();

  const base = ctx.createRadialGradient(-r * 0.32, -r * 0.35, r * 0.1, 0, 0, r);
  base.addColorStop(0, "#4a4652");
  base.addColorStop(0.6, "#302d38");
  base.addColorStop(1, "#17141f");
  ctx.fillStyle = base;
  ctx.beginPath();
  ctx.arc(0, 0, r, 0, TAU);
  ctx.fill();

  ctx.strokeStyle = "rgba(217, 181, 108, 0.22)";
  ctx.lineWidth = Math.max(0.8, 1.2 / zoom);
  ctx.beginPath();
  ctx.arc(0, 0, r - 3, 0, TAU);
  ctx.stroke();
  ctx.strokeStyle = "rgba(255, 255, 255, 0.055)";
  ctx.beginPath();
  ctx.arc(-1.5, -2.5, r * 0.7, 0.4, 5.2);
  ctx.stroke();

  const top = ctx.createRadialGradient(-r * 0.2, -r * 0.26, 2, 0, 0, r * 0.66);
  top.addColorStop(0, "#5c5664");
  top.addColorStop(0.7, "#3a3542");
  top.addColorStop(1, "#211c29");
  ctx.fillStyle = top;
  ctx.beginPath();
  ctx.arc(-1, -2, r * 0.63, 0, TAU);
  ctx.fill();

  for (let index = 0; index < 4; index += 1) {
    const angle = index * 1.57 + 0.4;
    const glow = 0.12 + Math.sin(t * 0.9 + index + x * 0.01) * 0.06;
    ctx.strokeStyle = `rgba(217, 181, 108, ${glow})`;
    ctx.lineWidth = Math.max(0.7, 1.1 / zoom);
    ctx.beginPath();
    ctx.moveTo(Math.cos(angle) * r * 0.2, Math.sin(angle) * r * 0.2);
    ctx.lineTo(Math.cos(angle + 0.2) * r * 0.54, Math.sin(angle + 0.2) * r * 0.54);
    ctx.lineTo(Math.cos(angle - 0.1) * r * 0.82, Math.sin(angle - 0.1) * r * 0.82);
    ctx.stroke();
  }

  ctx.fillStyle = `rgba(169, 151, 255, ${0.1 + Math.sin(t * 0.8 + y) * 0.035})`;
  ctx.beginPath();
  ctx.arc(0, 0, r * 0.19, 0, TAU);
  ctx.fill();
  ctx.restore();
}

function drawRuin(ctx, obstacle, now, zoom) {
  const { x, y, r } = obstacle;
  const random = seededRandom(Math.round(x * 7 + y * 13));
  ctx.save();
  ctx.translate(x, y);
  ctx.fillStyle = "rgba(0, 0, 0, 0.38)";
  ctx.beginPath();
  ctx.ellipse(6, 8, r * 1.1, r * 0.78, 0.3, 0, TAU);
  ctx.fill();

  ctx.beginPath();
  const sides = 7;
  for (let index = 0; index < sides; index += 1) {
    const angle = (index / sides) * TAU;
    const radius = r * (0.7 + random() * 0.45);
    const px = Math.cos(angle) * radius;
    const py = Math.sin(angle) * radius * 0.8;
    if (index === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
  const fill = ctx.createLinearGradient(-r, -r, r, r);
  fill.addColorStop(0, "#47414f");
  fill.addColorStop(0.55, "#2c2735");
  fill.addColorStop(1, "#17131f");
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.strokeStyle = "rgba(217, 181, 108, 0.18)";
  ctx.lineWidth = Math.max(0.7, 1 / zoom);
  ctx.stroke();

  ctx.strokeStyle = "rgba(217, 181, 108, 0.15)";
  for (let index = 0; index < 3; index += 1) {
    ctx.beginPath();
    ctx.moveTo(-r * 0.2 + index * 7, -r * 0.16);
    ctx.lineTo(r * 0.05 + index * 5, r * 0.08);
    ctx.lineTo(-r * 0.16 + index * 4, r * 0.36);
    ctx.stroke();
  }

  const glow = 0.1 + Math.sin(now / 1000 + x) * 0.04;
  ctx.fillStyle = `rgba(169, 151, 255, ${glow})`;
  ctx.beginPath();
  ctx.arc(r * 0.14, -r * 0.16, r * 0.25, 0, TAU);
  ctx.fill();
  ctx.restore();
}

function drawCrystal(ctx, obstacle, now, zoom) {
  const { x, y, r } = obstacle;
  const t = now / 1000;
  const pulse = 0.5 + Math.sin(t * 1.15 + x * 0.1) * 0.5;
  ctx.save();
  ctx.translate(x, y);

  ctx.globalCompositeOperation = "lighter";
  const aura = ctx.createRadialGradient(0, 0, 1, 0, 0, r * 3.3);
  aura.addColorStop(0, `rgba(110, 224, 205, ${0.13 + pulse * 0.06})`);
  aura.addColorStop(0.4, "rgba(112, 102, 220, 0.055)");
  aura.addColorStop(1, "rgba(112, 102, 220, 0)");
  ctx.fillStyle = aura;
  ctx.fillRect(-r * 3.4, -r * 3.4, r * 6.8, r * 6.8);
  ctx.globalCompositeOperation = "source-over";

  ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
  ctx.beginPath();
  ctx.ellipse(4, 8, r * 1.2, r * 0.62, 0.25, 0, TAU);
  ctx.fill();

  const points = 6;
  ctx.beginPath();
  for (let index = 0; index < points * 2; index += 1) {
    const angle = -Math.PI / 2 + (index * Math.PI) / points;
    const radius = index % 2 === 0 ? r * 1.25 : r * 0.46;
    const px = Math.cos(angle) * radius;
    const py = Math.sin(angle) * radius * 0.92;
    if (index === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
  const fill = ctx.createLinearGradient(0, -r, 0, r);
  fill.addColorStop(0, `rgba(190, 255, 244, ${0.75 + pulse * 0.12})`);
  fill.addColorStop(0.4, "#62cabb");
  fill.addColorStop(1, "#392e77");
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.strokeStyle = "rgba(207, 252, 255, 0.64)";
  ctx.lineWidth = Math.max(0.8, 1.1 / zoom);
  ctx.stroke();

  ctx.strokeStyle = "rgba(255, 255, 255, 0.28)";
  ctx.beginPath();
  ctx.moveTo(0, -r * 1.08);
  ctx.lineTo(0, r * 0.9);
  ctx.moveTo(0, -r * 0.2);
  ctx.lineTo(r * 0.4, r * 0.2);
  ctx.stroke();
  ctx.restore();
}

function drawAltar(ctx, obstacle, now, zoom) {
  const { x, y, r } = obstacle;
  const t = now / 1000;
  ctx.save();
  ctx.translate(x, y);

  ctx.fillStyle = "rgba(0, 0, 0, 0.48)";
  ctx.beginPath();
  ctx.ellipse(7, 10, r * 1.12, r * 0.96, 0.18, 0, TAU);
  ctx.fill();

  const base = ctx.createRadialGradient(-r * 0.3, -r * 0.34, 6, 0, 0, r);
  base.addColorStop(0, "#554c63");
  base.addColorStop(0.62, "#332c40");
  base.addColorStop(1, "#181322");
  ctx.fillStyle = base;
  ctx.beginPath();
  ctx.arc(0, 0, r, 0, TAU);
  ctx.fill();

  ctx.strokeStyle = "rgba(217, 181, 108, 0.38)";
  ctx.lineWidth = Math.max(0.9, 1.5 / zoom);
  ctx.beginPath();
  ctx.arc(0, 0, r - 4, 0, TAU);
  ctx.stroke();

  ctx.setLineDash([2, 9]);
  ctx.strokeStyle = "rgba(169, 151, 255, 0.34)";
  ctx.beginPath();
  ctx.arc(0, 0, r - 14, t * 0.08, t * 0.08 + TAU);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = "#0d0f18";
  ctx.beginPath();
  ctx.arc(0, 0, r * 0.68, 0, TAU);
  ctx.fill();
  ctx.strokeStyle = "rgba(217, 181, 108, 0.2)";
  ctx.beginPath();
  ctx.arc(0, 0, r * 0.68, 0, TAU);
  ctx.stroke();

  starPath(ctx, 0, 0, 8, r * 0.62, r * 0.24, t * 0.06);
  ctx.strokeStyle = "rgba(169, 151, 255, 0.24)";
  ctx.lineWidth = Math.max(0.6, 1 / zoom);
  ctx.stroke();

  const pulse = 0.5 + Math.sin(t * 0.85) * 0.5;
  const core = ctx.createRadialGradient(0, 0, 0, 0, 0, r * 0.63);
  core.addColorStop(0, `rgba(235, 213, 166, ${0.11 + pulse * 0.045})`);
  core.addColorStop(0.45, "rgba(169, 151, 255, 0.045)");
  core.addColorStop(1, "rgba(169, 151, 255, 0)");
  ctx.fillStyle = core;
  ctx.beginPath();
  ctx.arc(0, 0, r * 0.68, 0, TAU);
  ctx.fill();

  ctx.globalCompositeOperation = "lighter";
  ctx.fillStyle = `rgba(244, 217, 155, ${0.2 + pulse * 0.15})`;
  ctx.beginPath();
  ctx.arc(0, 0, 2.2 + pulse * 1.2, 0, TAU);
  ctx.fill();
  ctx.restore();
}

export function drawObstacles(ctx, config, now, zoom) {
  const obstacles = config?.obstacles || [];
  for (const obstacle of obstacles) {
    switch (obstacle.kind) {
      case "altar":
        drawAltar(ctx, obstacle, now, zoom);
        break;
      case "crystal":
        drawCrystal(ctx, obstacle, now, zoom);
        break;
      case "ruin":
        drawRuin(ctx, obstacle, now, zoom);
        break;
      default:
        drawPillar(ctx, obstacle, now, zoom);
        break;
    }
  }
}

export function drawArenaBorder(ctx, config, now, zoom) {
  const width = config?.arena?.w || 1900;
  const height = config?.arena?.h || 1100;
  const border = config?.arena?.border || 46;
  const line = Math.max(0.8, 1.1 / zoom);

  ctx.save();
  ctx.lineWidth = 18;
  ctx.strokeStyle = "rgba(10, 6, 18, 0.55)";
  ctx.strokeRect(border - 11, border - 11, width - (border - 11) * 2, height - (border - 11) * 2);

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
