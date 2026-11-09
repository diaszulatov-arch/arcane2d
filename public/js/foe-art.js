/* What the new bugs leave on the floor and carry around with them. As with the bosses'
 * tricks, each thing explains itself by looking like what it is a joke about. */

import { label } from "./quest-art.js";
import { pixelRing } from "./vfx.js";

const TAU = Math.PI * 2;
const QUOTE_TEXT = "Привет, мир! Это очень длинная строка";
const TONES = {
  sound: "#ff6b6b",
  pull: "#ff5ab0",
  stuffy: "#a8b06a",
  alert: "#ff4f4f",
  null: "#8a7fb0",
  warn: "#ffc23d",
  error: "#ff6a5a",
  fatal: "#ff2f4f",
  info: "#9ac8a0",
  pass: "#7fe08a",
  fail: "#ff5a5a",
};

function drawWip(ctx, field, t) {
  const fade = Math.min(1, (field.ttl ?? 1) * 1.5);
  ctx.save();
  ctx.beginPath();
  ctx.arc(field.x, field.y, field.r, 0, TAU);
  ctx.clip();
  ctx.globalAlpha = 0.34 * fade;
  ctx.fillStyle = "#1a1208";
  ctx.fillRect(field.x - field.r, field.y - field.r, field.r * 2, field.r * 2);
  ctx.fillStyle = "#ffc23d";
  const left = field.x - field.r * 2;
  for (let step = 0; step < 9; step += 1) {
    const x = left + step * 34 + ((t * 14) % 34);
    ctx.beginPath();
    ctx.moveTo(x, field.y + field.r);
    ctx.lineTo(x + 17, field.y + field.r);
    ctx.lineTo(x + 17 + field.r * 2, field.y - field.r);
    ctx.lineTo(x + field.r * 2, field.y - field.r);
    ctx.closePath();
    ctx.fill();
  }
  ctx.restore();
  pixelRing(ctx, field.x, field.y, field.r, 3, "#ffc23d", 0.55 * fade, { gap: 0.3, seed: field.id });
}

function drawString(ctx, field) {
  const dx = field.x2 - field.x;
  const dy = field.y2 - field.y;
  const length = Math.hypot(dx, dy) || 1;
  const count = Math.floor(length / 24);
  ctx.save();
  ctx.font = "bold 20px monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.globalAlpha = field.arming ? 0.35 : 0.95;
  for (let index = 1; index < count; index += 1) {
    const x = field.x + (dx / length) * index * 24;
    const y = field.y + (dy / length) * index * 24;
    ctx.fillStyle = "rgba(20, 12, 8, 0.8)";
    ctx.fillRect(x - 12, y - 13, 24, 26);
    ctx.fillStyle = field.arming ? "#a08068" : "#ff9a6a";
    ctx.fillText(QUOTE_TEXT[index % QUOTE_TEXT.length], x, y);
  }
  ctx.restore();
}

function drawEof(ctx, field, t) {
  ctx.save();
  ctx.fillStyle = "rgba(6, 4, 12, 0.9)";
  ctx.fillRect(field.x, field.y, field.x2 - field.x, field.y2 - field.y);
  ctx.fillStyle = `rgba(255, 90, 110, ${0.55 + Math.sin(t * 5) * 0.2})`;
  ctx.fillRect(field.x2 - 5, field.y, 5, field.y2 - field.y);
  ctx.font = "bold 22px monospace";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "#ff6a7a";
  for (let y = field.y + 60; y < field.y2; y += 120) ctx.fillText("EOF", field.x2 - 12, y);
  ctx.restore();
}

function drawWire(ctx, field) {
  const fade = Math.min(1, (field.ttl ?? 1) * 1.2);
  ctx.save();
  ctx.lineCap = "round";
  ctx.globalAlpha = fade;
  ctx.strokeStyle = "#0c0e14";
  ctx.lineWidth = 10;
  ctx.beginPath();
  ctx.moveTo(field.x, field.y);
  ctx.lineTo(field.x2, field.y2);
  ctx.stroke();
  ctx.strokeStyle = "#6a7284";
  ctx.lineWidth = 5;
  ctx.stroke();
  ctx.restore();
}

function drawPuddle(ctx, field, t) {
  ctx.save();
  ctx.globalAlpha = 0.42 * Math.min(1, (field.ttl ?? 1));
  ctx.fillStyle = "#2f6fa8";
  ctx.beginPath();
  ctx.ellipse(field.x, field.y, field.r, field.r * 0.72, 0, 0, TAU);
  ctx.fill();
  ctx.fillStyle = "#8fd8ff";
  ctx.globalAlpha *= 0.5;
  ctx.beginPath();
  ctx.ellipse(field.x - field.r * 0.25, field.y - field.r * 0.2, field.r * 0.3, field.r * 0.12, 0, 0, TAU);
  ctx.fill();
  ctx.restore();
  pixelRing(ctx, field.x, field.y, field.r * 0.86, 2, "#8fd8ff", 0.3 + Math.sin(t * 3 + field.id) * 0.08);
}

function drawCold(ctx, field) {
  pixelRing(ctx, field.x, field.y, field.r, 5, "#bff0ff", Math.min(0.9, (field.ttl ?? 1) * 1.4), { seed: field.id });
  pixelRing(ctx, field.x, field.y, field.r - 18, 3, "#6fc8ff", Math.min(0.5, (field.ttl ?? 1)), { gap: 0.4, seed: field.id });
}

function drawIce(ctx, field) {
  ctx.save();
  ctx.globalAlpha = 0.3 * Math.min(1, (field.ttl ?? 1));
  ctx.fillStyle = "#c8f0ff";
  ctx.beginPath();
  ctx.arc(field.x, field.y, field.r, 0, TAU);
  ctx.fill();
  ctx.restore();
}

function drawBox(ctx, field) {
  const size = field.r;
  ctx.save();
  ctx.fillStyle = "#8a6a3a";
  ctx.fillRect(field.x - size, field.y - size, size * 2, size * 2);
  ctx.fillStyle = "#a8844a";
  ctx.fillRect(field.x - size + 3, field.y - size + 3, size * 2 - 6, size * 2 - 6);
  ctx.fillStyle = "#d8c078";
  ctx.fillRect(field.x - 4, field.y - size + 3, 8, size * 2 - 6);
  ctx.fillStyle = "#1a1208";
  ctx.font = "bold 11px monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(".zip", field.x, field.y);
  ctx.restore();
}

function drawWindow(ctx, field, t) {
  ctx.save();
  ctx.fillStyle = "rgba(255, 122, 154, 0.07)";
  ctx.beginPath();
  ctx.arc(field.x, field.y, field.r, 0, TAU);
  ctx.fill();
  ctx.restore();
  pixelRing(ctx, field.x, field.y, field.r, 4, "#ff7a9a", 0.85, { gap: 0.18, seed: field.id, turn: t * 0.25 });
  label(ctx, field.label || "контекст", field.x, field.y - field.r - 14, "#ff9ab4");
}

const FIELD_ART = {
  wip: drawWip,
  string: drawString,
  eof: drawEof,
  wire: drawWire,
  puddle: drawPuddle,
  cold: drawCold,
  ice: drawIce,
  box: drawBox,
  window: drawWindow,
};

export function drawFields(ctx, fields, now) {
  if (!fields?.length) return;
  const t = now / 1000;
  for (const field of fields) FIELD_ART[field.k]?.(ctx, field, t);
}

function drawArc(ctx, x, y, [spin, width, reach, count], t) {
  ctx.save();
  for (let index = 0; index < count; index += 1) {
    const middle = spin + (index / count) * TAU;
    ctx.fillStyle = `rgba(127, 212, 255, ${0.22 + Math.sin(t * 9) * 0.05})`;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.arc(x, y, reach, middle - width / 2, middle + width / 2);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "#bfeaff";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(x, y, reach, middle - width / 2, middle + width / 2);
    ctx.stroke();
  }
  ctx.restore();
}

function drawLink(ctx, visual, other) {
  ctx.save();
  ctx.strokeStyle = "#c98a5a";
  ctx.globalAlpha = 0.5;
  ctx.lineWidth = 3;
  ctx.setLineDash([9, 7]);
  ctx.beginPath();
  ctx.moveTo(visual.x, visual.y);
  ctx.lineTo(other.x, other.y);
  ctx.stroke();
  ctx.restore();
}

function drawGlyph(ctx, x, y, radius, glyph) {
  ctx.save();
  ctx.fillStyle = "#1a1208";
  ctx.font = `bold ${Math.round(radius * 1.45)}px monospace`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(glyph, x, y);
  ctx.restore();
}

/** Everything that hangs about a creature: its aura, dome, arc, chain and what it says. */
export function drawFoeMarks(ctx, monsters, now) {
  if (!monsters?.size) return;
  const t = now / 1000;
  for (const visual of monsters.values()) {
    const { data } = visual;
    const marks = data.marks;
    if (!marks) continue;
    const radius = Number(data.r) || 18;
    const tone = TONES[marks.tone] || data.color || "#e8e4f4";
    const { x, y } = visual;
    if (marks.aura) pixelRing(ctx, x, y, marks.aura, 3, tone, 0.26 + Math.sin(t * 3 + data.id) * 0.08, { gap: 0.35, seed: data.id, turn: t * 0.2 });
    if (marks.dome) {
      ctx.save();
      ctx.fillStyle = "rgba(143, 200, 255, 0.1)";
      ctx.beginPath();
      ctx.arc(x, y, marks.dome, 0, TAU);
      ctx.fill();
      ctx.restore();
      pixelRing(ctx, x, y, marks.dome, 3, "#bfe0ff", 0.7);
    }
    if (marks.arc) drawArc(ctx, x, y, marks.arc, t);
    if (marks.link) {
      const other = monsters.get(marks.link);
      if (other) drawLink(ctx, visual, other);
    }
    if (marks.open) pixelRing(ctx, x, y - radius * 0.3, radius * 1.35, 3, "#7fffb0", 0.9);
    if (marks.down) label(ctx, "zzz", x, y - radius * 1.2, tone);
    if (marks.glyph) drawGlyph(ctx, x, y - radius * 0.1, radius, marks.glyph);
    if (marks.label) label(ctx, marks.label, x, y - radius * 2.3, tone);
  }
}

/** КАПСЛОК's shot: a letter you can see from the other side of the room. */
export function drawCapsShot(ctx, visual, color) {
  const radius = Number(visual.data.radius) || 24;
  ctx.save();
  ctx.fillStyle = "rgba(30, 10, 6, 0.85)";
  ctx.fillRect(visual.x - radius, visual.y - radius, radius * 2, radius * 2);
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.strokeRect(visual.x - radius, visual.y - radius, radius * 2, radius * 2);
  ctx.fillStyle = color;
  ctx.font = `bold ${Math.round(radius * 1.5)}px monospace`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("А", visual.x, visual.y + 1);
  ctx.restore();
}
