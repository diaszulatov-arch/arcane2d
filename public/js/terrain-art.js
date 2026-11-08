/* What a room is furnished with: each chapter's rule of place, the things spells
 * can break, and the screen-wide trouble an event brings. */

import { label } from "./quest-art.js";

const TAU = Math.PI * 2;
const BLUE = "#6fb6ff";

const CRATE_LOOK = {
  0: { body: "#c8c4b4", face: "#16302a", name: "crt" },
  1: { body: "#2a2636", face: "#ff6b9e", name: "phone" },
  2: { body: "#b08a5a", face: "#7a5a34", name: "box" },
  3: { body: "#3a4046", face: "#4fe08a", name: "psu" },
  4: { body: "#3a1e28", face: "#ff4f6a", name: "shard" },
};

function drawBelt(ctx, belt, t) {
  const [x, y, w, h, vx, vy] = belt;
  ctx.save();
  ctx.fillStyle = "rgba(20, 16, 36, 0.55)";
  ctx.fillRect(x, y, w, h);
  ctx.beginPath();
  ctx.rect(x, y, w, h);
  ctx.clip();
  ctx.strokeStyle = "rgba(255, 107, 158, 0.75)";
  ctx.lineWidth = 7;
  const step = 72;
  const travel = (t * 96) % step;
  const horizontal = Boolean(vx);
  const sign = (horizontal ? vx : vy) > 0 ? 1 : -1;
  const length = horizontal ? w : h;
  const breadth = horizontal ? h : w;
  for (let along = -step; along < length + step; along += step) {
    const at = along + (sign > 0 ? travel : step - travel);
    ctx.beginPath();
    for (let side = 0; side <= 1; side += 1) {
      const tip = at + sign * 22;
      const a = side ? breadth * 0.8 : breadth * 0.2;
      const middle = breadth / 2;
      if (horizontal) {
        ctx.moveTo(x + at, y + a);
        ctx.lineTo(x + tip, y + middle);
      } else {
        ctx.moveTo(x + a, y + at);
        ctx.lineTo(x + middle, y + tip);
      }
    }
    ctx.stroke();
  }
  ctx.restore();
}

function drawBuild(ctx, build) {
  const [x, y, w, h] = build;
  ctx.save();
  ctx.beginPath();
  ctx.rect(x, y, w, h);
  ctx.clip();
  ctx.fillStyle = "rgba(255, 217, 61, 0.28)";
  ctx.fillRect(x, y, w, h);
  ctx.fillStyle = "rgba(10, 8, 6, 0.55)";
  for (let stripe = -h; stripe < w + h; stripe += 44) {
    ctx.beginPath();
    ctx.moveTo(x + stripe, y);
    ctx.lineTo(x + stripe + 22, y);
    ctx.lineTo(x + stripe + 22 - h, y + h);
    ctx.lineTo(x + stripe - h, y + h);
    ctx.closePath();
    ctx.fill();
  }
  ctx.restore();
  ctx.strokeStyle = "rgba(255, 217, 61, 0.8)";
  ctx.lineWidth = 3;
  ctx.strokeRect(x, y, w, h);
  label(ctx, "в разработке", x + w / 2, y + h / 2, "#ffe17a", 15);
}

function drawLinkPad(ctx, x, y, t) {
  ctx.save();
  ctx.globalAlpha = 0.28 + Math.sin(t * 4) * 0.08;
  ctx.fillStyle = BLUE;
  ctx.beginPath();
  ctx.ellipse(x, y, 42, 26, 0, 0, TAU);
  ctx.fill();
  ctx.globalAlpha = 1;
  ctx.strokeStyle = BLUE;
  ctx.lineWidth = 3;
  ctx.stroke();
  ctx.fillStyle = BLUE;
  ctx.fillRect(x - 30, y + 6, 60, 4);
  ctx.restore();
  label(ctx, "<a href>", x, y - 40, "#a6d2ff", 15);
}

function drawAisle(ctx, aisle) {
  const [x, y, w, h, kind] = aisle;
  ctx.fillStyle = kind === "hot" ? "rgba(255, 90, 60, 0.2)" : "rgba(90, 180, 255, 0.18)";
  ctx.fillRect(x, y, w, h);
}

/** A puddle with an uneven shore: the shape is its own, and stays inside its radius. */
function puddlePath(ctx, surface, inset = 1) {
  const seed = (surface.id || 1) * 1.7;
  ctx.beginPath();
  for (let step = 0; step <= 30; step += 1) {
    const angle = (step / 30) * TAU;
    const shore = 0.86 + Math.sin(angle * 3 + seed) * 0.08 + Math.sin(angle * 5 + seed * 2) * 0.05;
    const px = surface.x + Math.cos(angle) * 96 * shore * inset;
    const py = surface.y + Math.sin(angle) * 72 * shore * inset;
    if (step === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
}

function drawPuddle(ctx, surface, state, t) {
  const { x, y } = surface;
  ctx.save();
  if (state === "ice") ctx.fillStyle = "rgba(200, 236, 255, 0.78)";
  else if (state === "shock") ctx.fillStyle = "rgba(255, 240, 120, 0.8)";
  else ctx.fillStyle = "rgba(30, 80, 160, 0.5)";
  puddlePath(ctx, surface);
  ctx.fill();
  ctx.strokeStyle = state === "ice" ? "#ffffff" : "rgba(170, 215, 255, 0.5)";
  ctx.lineWidth = 3;
  ctx.stroke();
  if (state === "ice") {
    ctx.strokeStyle = "rgba(255, 255, 255, 0.85)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x - 40, y - 18);
    ctx.lineTo(x - 8, y + 4);
    ctx.lineTo(x + 30, y - 10);
    ctx.moveTo(x - 8, y + 4);
    ctx.lineTo(x + 6, y + 30);
    ctx.stroke();
  } else if (state === "shock") {
    ctx.strokeStyle = "#fff6b0";
    ctx.lineWidth = 3;
    for (let bolt = 0; bolt < 5; bolt += 1) {
      const angle = t * 12 + bolt * 1.3;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + Math.cos(angle) * 40, y + Math.sin(angle * 1.7) * 24);
      ctx.lineTo(x + Math.cos(angle + 0.4) * 92, y + Math.sin(angle + 0.4) * 64);
      ctx.stroke();
    }
  } else if (!state) {
    // Deeper in the middle, with slow rings going out across the water.
    ctx.fillStyle = "rgba(14, 40, 100, 0.42)";
    puddlePath(ctx, surface, 0.62);
    ctx.fill();
    ctx.lineWidth = 2;
    for (let ring = 0; ring < 2; ring += 1) {
      const grow = (t * 0.3 + ring * 0.5 + (surface.id || 0) * 0.13) % 1;
      ctx.strokeStyle = `rgba(190, 228, 255, ${0.34 * (1 - grow)})`;
      ctx.beginPath();
      ctx.ellipse(x, y, 16 + grow * 58, 11 + grow * 42, 0, 0, TAU);
      ctx.stroke();
    }
    ctx.fillStyle = "rgba(225, 242, 255, 0.5)";
    ctx.fillRect(x - 34 + Math.sin(t * 1.4) * 7, y - 22, 24, 3);
    ctx.fillRect(x + 6 + Math.cos(t * 1.1) * 8, y + 20, 18, 3);
  }
  ctx.restore();
}

/** A real cable: it sags a little between two plugs. Hits still follow the straight line. */
function drawCable(ctx, surface, state, t) {
  const { x, y, x2, y2 } = surface;
  const sagX = (x + x2) / 2;
  const sagY = (y + y2) / 2 + Math.min(16, Math.hypot(x2 - x, y2 - y) * 0.05);
  const line = () => {
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.quadraticCurveTo(sagX, sagY, x2, y2);
  };
  ctx.save();
  ctx.lineCap = "round";
  ctx.strokeStyle = "rgba(0, 0, 0, 0.32)";
  ctx.lineWidth = 12;
  ctx.translate(2, 7);
  line();
  ctx.stroke();
  ctx.translate(-2, -7);
  ctx.strokeStyle = state === "burnt" ? "#1a1412" : "#17181e";
  ctx.lineWidth = 9;
  line();
  ctx.stroke();
  if (state === "burn") {
    ctx.strokeStyle = "#ff8a3c";
    ctx.lineWidth = 16 + Math.sin(t * 22) * 4;
    ctx.setLineDash([18, 14]);
    ctx.lineDashOffset = -t * 90;
    line();
    ctx.stroke();
    ctx.setLineDash([]);
  } else if (state !== "burnt") {
    ctx.strokeStyle = "rgba(90, 96, 112, 0.9)";
    ctx.lineWidth = 3;
    line();
    ctx.stroke();
    // Current on its way along, and the reason not to shoot sparks at it.
    ctx.strokeStyle = "rgba(255, 210, 122, 0.85)";
    ctx.setLineDash([10, 46]);
    ctx.lineDashOffset = -t * 60;
    line();
    ctx.stroke();
    ctx.setLineDash([]);
  }
  const angle = Math.atan2(y2 - y, x2 - x);
  for (const [px, py, turn] of [[x, y, angle], [x2, y2, angle + Math.PI]]) {
    ctx.save();
    ctx.translate(px, py);
    ctx.rotate(turn);
    ctx.fillStyle = "#2c2f3a";
    ctx.fillRect(-11, -8, 20, 16);
    ctx.fillStyle = "#c9973a";
    ctx.fillRect(-16, -5, 6, 3);
    ctx.fillRect(-16, 2, 6, 3);
    ctx.fillStyle = "rgba(255, 255, 255, 0.14)";
    ctx.fillRect(-9, -6, 16, 3);
    ctx.restore();
  }
  ctx.restore();
}

/** Everything that lies flat on a stage's floor. */
export function drawTerrainFloor(ctx, terrain, state, workshop, tile, now) {
  if (!terrain) return;
  const t = now / 1000;
  for (const aisle of terrain.aisles || []) drawAisle(ctx, aisle);
  for (const belt of terrain.belts || []) drawBelt(ctx, belt, t);
  for (const build of terrain.builds || []) drawBuild(ctx, build);
  const surf = state?.surf || {};
  for (const surface of terrain.surfaces || []) {
    if (surface.k === "puddle") drawPuddle(ctx, surface, surf[surface.id] || "", t);
    else drawCable(ctx, surface, surf[surface.id] || "", t);
  }
  for (const [x1, y1, x2, y2] of terrain.links || []) {
    drawLinkPad(ctx, x1, y1, t);
    drawLinkPad(ctx, x2, y2, t);
  }
  for (const [x, y, w, h] of workshop?.glow || []) {
    ctx.fillStyle = "rgba(127, 224, 238, 0.7)";
    ctx.fillRect(x * tile, y * tile, w * tile, h * tile);
  }
}

function drawCrate(ctx, x, y, chapter) {
  const look = CRATE_LOOK[chapter] || CRATE_LOOK[0];
  ctx.fillStyle = "rgba(0, 0, 0, 0.38)";
  ctx.fillRect(x - 26, y + 16, 52, 10);
  ctx.fillStyle = look.body;
  if (look.name === "crt") {
    ctx.fillRect(x - 26, y - 26, 52, 42);
    ctx.fillStyle = look.face;
    ctx.fillRect(x - 20, y - 20, 40, 28);
    ctx.fillStyle = "#4fe08a";
    ctx.fillRect(x - 14, y - 12, 18, 3);
    ctx.fillRect(x - 14, y - 4, 12, 3);
    ctx.fillStyle = look.body;
    ctx.fillRect(x - 12, y + 16, 24, 6);
  } else if (look.name === "phone") {
    ctx.fillRect(x - 15, y - 28, 30, 50);
    ctx.fillStyle = look.face;
    ctx.fillRect(x - 11, y - 23, 22, 38);
  } else if (look.name === "box") {
    ctx.fillRect(x - 25, y - 20, 50, 40);
    ctx.fillStyle = look.face;
    ctx.fillRect(x - 25, y - 4, 50, 5);
    ctx.fillRect(x - 3, y - 20, 6, 40);
  } else if (look.name === "psu") {
    ctx.fillRect(x - 26, y - 18, 52, 38);
    ctx.fillStyle = "#15171c";
    ctx.fillRect(x - 20, y - 12, 24, 26);
    ctx.fillStyle = look.face;
    ctx.fillRect(x + 10, y - 10, 8, 5);
  } else {
    ctx.beginPath();
    ctx.moveTo(x, y - 30);
    ctx.lineTo(x + 22, y);
    ctx.lineTo(x, y + 22);
    ctx.lineTo(x - 22, y);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = look.face;
    ctx.fillRect(x - 3, y - 14, 6, 22);
  }
}

function drawBattery(ctx, x, y, t) {
  ctx.fillStyle = "rgba(0, 0, 0, 0.38)";
  ctx.fillRect(x - 20, y + 18, 40, 8);
  ctx.fillStyle = "#23262e";
  ctx.fillRect(x - 18, y - 26, 36, 46);
  ctx.fillStyle = "#ffd93d";
  ctx.fillRect(x - 18, y - 26, 36, 8);
  ctx.fillRect(x - 6, y - 32, 12, 6);
  ctx.fillStyle = Math.sin(t * 6 + x) > 0 ? "#ff5a4f" : "#7a2a24";
  ctx.beginPath();
  ctx.moveTo(x + 3, y - 12);
  ctx.lineTo(x - 7, y + 3);
  ctx.lineTo(x, y + 3);
  ctx.lineTo(x - 3, y + 15);
  ctx.lineTo(x + 8, y - 2);
  ctx.lineTo(x + 1, y - 2);
  ctx.closePath();
  ctx.fill();
}

function drawCrack(ctx, x, y) {
  ctx.strokeStyle = "rgba(10, 8, 14, 0.9)";
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(x - 4, y - 34);
  ctx.lineTo(x + 8, y - 16);
  ctx.lineTo(x - 6, y - 2);
  ctx.lineTo(x + 6, y + 14);
  ctx.moveTo(x + 8, y - 16);
  ctx.lineTo(x + 24, y - 12);
  ctx.moveTo(x - 6, y - 2);
  ctx.lineTo(x - 22, y + 6);
  ctx.stroke();
  ctx.strokeStyle = "rgba(255, 255, 255, 0.16)";
  ctx.lineWidth = 2;
  ctx.stroke();
}

function drawTarget(ctx, x, y, lit) {
  ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
  ctx.fillRect(x - 24, y + 20, 48, 8);
  for (const [radius, color] of [[26, lit ? "#4fe08a" : "#f4f2fa"], [17, "#ff5a4f"], [8, "#f4f2fa"]]) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y - 6, radius, 0, TAU);
    ctx.fill();
  }
}

/** What stands on the floor and waits to be hit. */
export function drawProps(ctx, terrain, state, now) {
  if (!terrain) return;
  const t = now / 1000;
  const gone = new Set(state?.gone || []);
  const lit = new Set(state?.lit || []);
  for (const prop of terrain.props || []) {
    if (gone.has(prop.id)) continue;
    if (prop.k === "crate") drawCrate(ctx, prop.x, prop.y, terrain.chapter);
    else if (prop.k === "battery") drawBattery(ctx, prop.x, prop.y, t);
    else if (prop.k === "crack") drawCrack(ctx, prop.x, prop.y);
    else if (prop.k === "target") {
      drawTarget(ctx, prop.x, prop.y, lit.has(prop.id));
      if (prop.label) label(ctx, prop.label, prop.x, prop.y - 48, "#f4f2fa", 15);
    }
  }
}

export function terrainLights(terrain, state, lights) {
  if (!terrain) return;
  const surf = state?.surf || {};
  for (const surface of terrain.surfaces || []) {
    const kind = surf[surface.id];
    if (kind === "burn") {
      lights.push({ x: (surface.x + surface.x2) / 2, y: (surface.y + surface.y2) / 2, radius: 260, color: "#ff8a3c", power: 0.9 });
    } else if (kind === "shock") {
      lights.push({ x: surface.x, y: surface.y, radius: 300, color: "#fff6b0", power: 1 });
    }
  }
  for (const [x1, y1, x2, y2] of terrain.links || []) {
    lights.push({ x: x1, y: y1, radius: 130, color: BLUE, power: 0.6 });
    lights.push({ x: x2, y: y2, radius: 130, color: BLUE, power: 0.6 });
  }
}

/** Streaks across the whole screen, blowing the way the shots are about to go. */
export function drawGust(ctx, gust, width, height, now) {
  if (!gust) return;
  const t = now / 1000;
  ctx.save();
  ctx.strokeStyle = "rgba(230, 245, 255, 0.34)";
  ctx.lineWidth = 2;
  for (let index = 0; index < 34; index += 1) {
    const seed = index * 73.1;
    const x = ((seed * 13 + t * 620 * gust[0]) % width + width) % width;
    const y = ((seed * 29 + t * 620 * gust[1]) % height + height) % height;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x - gust[0] * 54, y - gust[1] * 54);
    ctx.stroke();
  }
  ctx.restore();
}

const SPAM_WORDS = ["ВЫ ВЫИГРАЛИ", "СКИДКА 99%", "КЛИКНИ!", "ГОРЯЧО", "ПОДПИШИСЬ", "БЕСПЛАТНО"];

/** Pop-ups raining on the screen, enough to get in the way of the view. */
export function drawSpamStorm(ctx, width, height, now) {
  const t = now / 1000;
  ctx.save();
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = '13px "Cozette", "JetBrains Mono", monospace';
  for (let index = 0; index < 18; index += 1) {
    const x = ((index * 137.5) % width);
    const y = ((index * 91 + t * (70 + (index % 5) * 26)) % (height + 60)) - 30;
    ctx.fillStyle = "rgba(47, 111, 224, 0.82)";
    ctx.fillRect(x - 62, y - 26, 124, 12);
    ctx.fillStyle = "rgba(244, 244, 250, 0.88)";
    ctx.fillRect(x - 62, y - 14, 124, 30);
    ctx.fillStyle = "#c02a22";
    ctx.fillText(SPAM_WORDS[index % SPAM_WORDS.length], x, y + 1);
  }
  ctx.restore();
}
