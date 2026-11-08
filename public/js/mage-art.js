/* The mages: baked once per colour, seen from the front, the side and the back.
 * A frame is a canvas of cells; the cloak and the staff move on their own, drawn over it. */

const TAU = Math.PI * 2;
const CELL = 2.7;
const COLS = 20;
const ROWS = 28;
const FEET_Y = 13;
const OUTLINE = "#0a0711";

/* Half a mage from the front or the back, drawn up to the spine; the rest is the mirror. */
const FRONT_HALF = [
  ".........d",
  "........dh",
  "........dh",
  ".......dhh",
  ".......dhH",
  "......dhhH",
  "......dhhh",
  ".....dhhhh",
  ".....bbBbb",
  "...ddhhhhh",
  "..dhhhhhhh",
  "...dddddSS",
  ".....SssSs",
  ".....sEEss",
  ".....ssSss",
  ".....wwwww",
  "..rr.wwwww",
  ".rRrrrwwWw",
  ".rRrrrrwWw",
  ".rRrrrrrww",
  ".ssrrrrrgg",
  "..ss.ggggG",
];
const BACK_HALF = [
  ".........d",
  "........dh",
  "........dh",
  ".......dhh",
  ".......dhH",
  "......dhhH",
  "......dhhh",
  ".....dhhhh",
  ".....bbbbb",
  "...ddhhhhh",
  "..dhhhhhhh",
  "...ddddddd",
  ".....wwwww",
  ".....wwWww",
  ".....wwwww",
  ".....wwwWw",
  "..rrrrrrrr",
  ".rRrrrrrrr",
  ".rRrrrrrrr",
  ".rRrrrrrrr",
  ".ssrrrrrrr",
  "..ss.ggggg",
];
/* The side view, facing right. Left is the same mage turned round. */
const SIDE = [
  "......dd............",
  "......dhhd..........",
  ".......dhhd.........",
  "........dhhd........",
  "........dhHhd.......",
  ".......dhhHhd.......",
  ".......dhhHhhd......",
  "......dhhhHhhd......",
  "......bbbBbbbb......",
  "....ddhhhhhhhhdd....",
  "...dhhhhhhhhhhhhhd..",
  "....ddddddddSSSdd...",
  ".......wsssssSs.....",
  ".......wssssEEs.....",
  ".......wsssssSSs....",
  ".......wwwwwwww.....",
  "......rrrwwwwwww....",
  ".....rRrrrrwwww.....",
  ".....rRrrrrrww......",
  ".....rRrrrrrrr......",
  ".....DRrrrrrss......",
  ".....ggggggGgg......",
];
const HEM_FRONT = [
  "...DrRrrrrrrrrRrD...",
  "...DrRrrrrrrrrRrD...",
  "..DDrRrrrrrrrrRrDD..",
  "..DDDrrrrDDrrrrDDD..",
];
const HEM_SIDE = [
  ".....DrRrrrrr.......",
  "....DDrRrrrrr.......",
  "....DDrRrrrrrr......",
  "...DDDDrrrrDDD......",
];

function channels(hex) {
  const value = parseInt(hex.slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

function mix(a, b, amount) {
  const from = channels(a);
  const to = channels(b);
  const part = (index) => Math.round(from[index] + (to[index] - from[index]) * amount);
  return `#${[part(0), part(1), part(2)].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

function palette(color, band) {
  return {
    h: color,
    H: mix(color, "#ffffff", 0.36),
    d: mix(color, "#000000", 0.42),
    b: band,
    B: mix(band, "#ffffff", 0.5),
    s: "#e4a86f",
    S: "#b57d4c",
    E: mix(color, "#ffffff", 0.6),
    w: "#dcd6e4",
    W: "#a79eb8",
    r: mix("#3a2a66", color, 0.14),
    R: mix("#5a4296", color, 0.2),
    D: mix("#1e1432", color, 0.1),
    g: "#f3d27f",
    G: "#fff2b6",
    m: "#2a1a24",
  };
}

function mirrored(half) {
  return half.map((row) => row + [...row].reverse().join(""));
}

/** Which rows and feet a frame uses. Walking has four beats, standing has two. */
const FRAMES = [
  { hem: 0, body: 0, left: 0, right: 0 },
  { hem: 0, body: 1, left: 0, right: 0 },
  { hem: -1, body: 0, left: 1, right: 0 },
  { hem: 0, body: -1, left: 0, right: 0 },
  { hem: 1, body: 0, left: 0, right: 1 },
  { hem: 0, body: -1, left: 0, right: 0 },
];

function paintFrame(ctx, side, body, hem, colors, beat) {
  const put = (row, y, shift = 0) => {
    for (let x = 0; x < row.length; x += 1) {
      const color = colors[row[x]];
      if (!color) continue;
      ctx.fillStyle = color;
      ctx.fillRect(x + shift + 1, y + 1, 1, 1);
    }
  };
  // Feet first, so the hem hangs over them.
  ctx.fillStyle = colors.m;
  if (side) {
    const front = beat.right ? 14 : beat.left ? 11 : 12;
    const back = beat.right ? 6 : beat.left ? 9 : 8;
    ctx.fillRect(front + 1, 26 + 1, 3, 2);
    ctx.fillRect(back + 1, 26 + 1 - (beat.left ? 0 : beat.right ? 1 : 0), 3, 2);
  } else {
    ctx.fillRect(6 + 1, 26 + 1 - beat.left, 3, 2);
    ctx.fillRect(11 + 1, 26 + 1 - beat.right, 3, 2);
  }
  hem.forEach((row, index) => put(row, 22 + index, beat.hem));
  body.forEach((row, index) => put(row, index + beat.body));
}

function bakeFrame(body, hem, colors, tint, beat, side) {
  const canvas = document.createElement("canvas");
  canvas.width = COLS + 2;
  canvas.height = ROWS + 3;
  const ctx = canvas.getContext("2d");
  paintFrame(ctx, side, body, hem, colors, beat);

  const silhouette = document.createElement("canvas");
  silhouette.width = canvas.width;
  silhouette.height = canvas.height;
  const shape = silhouette.getContext("2d");
  shape.drawImage(canvas, 0, 0);
  shape.globalCompositeOperation = "source-in";
  shape.fillStyle = "#ffffff";
  shape.fillRect(0, 0, canvas.width, canvas.height);

  const ghost = document.createElement("canvas");
  ghost.width = canvas.width;
  ghost.height = canvas.height;
  const ghostCtx = ghost.getContext("2d");
  ghostCtx.drawImage(silhouette, 0, 0);
  ghostCtx.globalCompositeOperation = "source-in";
  ghostCtx.fillStyle = tint;
  ghostCtx.fillRect(0, 0, canvas.width, canvas.height);

  // A dark rim all round, so a mage never melts into a busy floor.
  const framed = document.createElement("canvas");
  framed.width = canvas.width;
  framed.height = canvas.height;
  const framedCtx = framed.getContext("2d");
  for (const [x, y] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) framedCtx.drawImage(silhouette, x, y);
  framedCtx.globalCompositeOperation = "source-in";
  framedCtx.fillStyle = OUTLINE;
  framedCtx.fillRect(0, 0, canvas.width, canvas.height);
  framedCtx.globalCompositeOperation = "source-over";
  framedCtx.drawImage(canvas, 0, 0);
  return { canvas: framed, flash: silhouette, ghost };
}

const sets = new Map();

function mageSet(color, band) {
  const key = `${color}|${band}`;
  const cached = sets.get(key);
  if (cached) return cached;
  const colors = palette(color, band);
  const front = mirrored(FRONT_HALF);
  const back = mirrored(BACK_HALF);
  const set = {
    front: FRAMES.map((beat) => bakeFrame(front, HEM_FRONT, colors, color, beat, false)),
    back: FRAMES.map((beat) => bakeFrame(back, HEM_FRONT, colors, color, beat, false)),
    side: FRAMES.map((beat) => bakeFrame(SIDE, HEM_SIDE, colors, color, beat, true)),
    cloak: mix(color, "#000000", 0.5),
    cloakLight: mix(color, "#000000", 0.28),
    crystal: mix(color, "#ffffff", 0.5),
  };
  sets.set(key, set);
  return set;
}

function viewOf(aim) {
  const across = Math.cos(aim);
  if (Math.abs(across) >= 0.62) return { view: "side", facing: across < 0 ? -1 : 1 };
  return { view: Math.sin(aim) > 0 ? "front" : "back", facing: 1 };
}

function frameOf(visual, t) {
  if (!visual.moving) return Math.floor(t * 1.6 + visual.data.id) % 2;
  return 2 + (Math.floor(((visual.step || 0) * 2) / Math.PI + 4000) % 4);
}

/** Cells to world units, with the feet where the mage really stands. */
const WIDTH = (COLS + 2) * CELL;
const HEIGHT = (ROWS + 3) * CELL;
const LEFT = -WIDTH / 2;
const TOP = FEET_Y - HEIGHT + CELL;
const cellX = (col) => LEFT + (col + 1) * CELL;
const cellY = (row) => TOP + (row + 1) * CELL;

function drawCloak(ctx, set, view, facing, lag, t, moving) {
  const flap = Math.sin(t * (moving ? 11 : 2.4)) * (moving ? 0.9 : 0.35);
  ctx.save();
  ctx.scale(facing, 1);
  const local = lag * facing;
  const rows = view === "side" ? [[16, 3, 5], [18, 3, 6], [20, 3, 6], [22, 2, 7], [24, 2, 7], [26, 1, 8]] : [[16, 5, 10], [18, 4, 12], [20, 4, 12], [22, 4, 12], [24, 3, 14], [26, 3, 14]];
  rows.forEach(([row, col, wide], index) => {
    const reach = (index / rows.length) * (local + flap);
    ctx.fillStyle = OUTLINE;
    ctx.fillRect(cellX(col) + reach - 1, cellY(row) - 1, wide * CELL + 2, CELL * 2 + 3);
  });
  rows.forEach(([row, col, wide], index) => {
    const reach = (index / rows.length) * (local + flap);
    ctx.fillStyle = set.cloak;
    ctx.fillRect(cellX(col) + reach, cellY(row), wide * CELL, CELL * 2 + 1);
    // One fold down the middle, and the light along one edge.
    ctx.fillStyle = set.cloakLight;
    ctx.fillRect(cellX(col) + reach + CELL, cellY(row), CELL, CELL * 2 + 1);
    ctx.fillRect(cellX(col + Math.floor(wide / 2)) + reach, cellY(row), CELL, CELL * 2 + 1);
  });
  ctx.restore();
}

function lerpAngle(from, to, amount) {
  const delta = ((to - from + Math.PI) % TAU + TAU) % TAU - Math.PI;
  return from + delta * amount;
}

function drawStaff(ctx, set, color, view, facing, aim, casting, t, seed) {
  const handX = view === "side" ? cellX(14) * facing : view === "back" ? cellX(3) : cellX(16);
  const handY = cellY(20);
  const rest = -Math.PI / 2 + (view === "back" ? -0.2 : 0.2) * facing;
  const angle = lerpAngle(rest, aim, casting > 0 ? 0.65 + casting * 0.35 : 0.2);
  const dx = Math.cos(angle);
  const dy = Math.sin(angle);
  const reach = 44 + casting * 9;
  const tipX = handX + dx * reach;
  const tipY = handY + dy * reach;
  const buttX = handX - dx * 15;
  const buttY = handY - dy * 15;
  ctx.save();
  ctx.lineCap = "butt";
  const stroke = (width, style) => {
    ctx.strokeStyle = style;
    ctx.lineWidth = width;
    ctx.beginPath();
    ctx.moveTo(buttX, buttY);
    ctx.lineTo(tipX, tipY);
    ctx.stroke();
  };
  stroke(6, OUTLINE);
  stroke(3.6, "#6f4b2c");
  stroke(1.1, "#c19158");

  // A claw holding a crystal: the part the spell comes out of.
  ctx.save();
  ctx.translate(tipX, tipY);
  ctx.rotate(angle);
  ctx.fillStyle = OUTLINE;
  ctx.fillRect(-6, -7, 8, 14);
  ctx.fillStyle = "#f3d27f";
  ctx.fillRect(-5, -6, 6, 2.6);
  ctx.fillRect(-5, 3.4, 6, 2.6);
  ctx.restore();

  const glow = 15 + casting * 12 + Math.sin(t * 5 + seed) * 2;
  ctx.globalCompositeOperation = "lighter";
  const halo = ctx.createRadialGradient(tipX, tipY, 0, tipX, tipY, glow);
  const [r, g, b] = channels(color);
  halo.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.85)`);
  halo.addColorStop(0.35, `rgba(${r}, ${g}, ${b}, 0.3)`);
  halo.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
  ctx.fillStyle = halo;
  ctx.beginPath();
  ctx.arc(tipX, tipY, glow, 0, TAU);
  ctx.fill();
  ctx.globalCompositeOperation = "source-over";

  ctx.translate(tipX, tipY);
  ctx.rotate(Math.PI / 4 + Math.sin(t * 2.4 + seed) * 0.25);
  ctx.fillStyle = OUTLINE;
  ctx.fillRect(-5.4, -5.4, 10.8, 10.8);
  ctx.fillStyle = set.crystal;
  ctx.fillRect(-4.2, -4.2, 8.4, 8.4);
  ctx.fillStyle = color;
  ctx.fillRect(-0.2, -0.2, 4.4, 4.4);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(-4.2, -4.2, 3.2, 3.2);
  ctx.restore();
}

/** The mage at their own feet: the caller has already moved the context there. */
export function drawMage(ctx, visual, color, band, t) {
  const aim = visual.aim || 0;
  const { view, facing } = viewOf(aim);
  const set = mageSet(color, band);
  const frame = set[view][frameOf(visual, t)];
  const casting = Math.min(1, Math.max(0, (visual.cast || 0) / 0.2));
  const lag = visual.cloak || 0;
  ctx.save();
  ctx.translate(Math.cos(aim) * casting * 3.5, Math.sin(aim) * casting * 2);
  if (view === "back") drawStaff(ctx, set, color, view, facing, aim, casting, t, visual.data.id);
  if (view !== "back") drawCloak(ctx, set, view, facing, lag, t, visual.moving);
  ctx.save();
  ctx.scale(facing, 1);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(frame.canvas, LEFT, TOP, WIDTH, HEIGHT);
  if (visual.hurt > 0) {
    ctx.globalAlpha = Math.min(0.85, visual.hurt * 3.2);
    ctx.drawImage(frame.flash, LEFT, TOP, WIDTH, HEIGHT);
    ctx.globalAlpha = 1;
  }
  ctx.restore();
  if (view === "back") drawCloak(ctx, set, view, facing, lag, t, visual.moving);
  if (view !== "back") drawStaff(ctx, set, color, view, facing, aim, casting, t, visual.data.id);
  ctx.restore();
}

/** A see-through copy left behind by a dash: the frame, its size and which way it faced. */
export function mageGhost(visual, color, band) {
  const { view, facing } = viewOf(visual.aim || 0);
  const set = mageSet(color, band);
  return { image: set[view][0].ghost, facing, left: LEFT, top: TOP, width: WIDTH, height: HEIGHT };
}

/** How high above their feet a mage reaches: nameplates go above this. */
export const MAGE_TOP = TOP;
