/* The five chapters as pictures: tiles, weather, doors, portals and the bestiary. */

const TAU = Math.PI * 2;
// Pixels per tile in the baked floor: about one screen pixel at the game's zoom,
// and small enough that the largest floor stays well under 30 MB.
const BAKE = 16;

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

/** Mostly the first two tones, so the floor reads as stone and not a checkerboard. */
function floorTone(theme, random) {
  const roll = random();
  if (roll < 0.42) return theme.floors[0];
  if (roll < 0.8) return theme.floors[1];
  return theme.floors[2 + Math.floor(random() * (theme.floors.length - 2))];
}

function paintFloorTile(ctx, x, y, theme, random) {
  ctx.fillStyle = floorTone(theme, random);
  ctx.fillRect(x, y, BAKE, BAKE);
  ctx.fillStyle = theme.grout;
  ctx.fillRect(x, y + BAKE - 1, BAKE, 1);
  ctx.fillRect(x + BAKE - 1, y, 1, BAKE);
  ctx.fillStyle = "rgba(255, 255, 255, 0.05)";
  ctx.fillRect(x, y, BAKE - 1, 1);
  const specks = Math.floor(random() * 3);
  for (let index = 0; index < specks; index += 1) {
    ctx.fillStyle = theme.specks[Math.floor(random() * theme.specks.length)];
    ctx.globalAlpha = 0.28 + random() * 0.3;
    ctx.fillRect(x + 2 + Math.floor(random() * 11), y + 2 + Math.floor(random() * 11), 2, 1);
    ctx.globalAlpha = 1;
  }
}

/** One signature of each chapter, scattered over the floor after it is laid. */
function paintFloorDecor(ctx, x, y, theme, kind, random) {
  const px = x + 2 + Math.floor(random() * 9);
  const py = y + 2 + Math.floor(random() * 9);
  if (kind === "oldweb") {
    // The tiled stars every home page had.
    ctx.fillStyle = "#ffd93d";
    ctx.fillRect(px + 1, py, 1, 3);
    ctx.fillRect(px, py + 1, 3, 1);
  } else if (kind === "feed") {
    ctx.fillStyle = "#ff6b9e";
    ctx.fillRect(px, py, 2, 2);
    ctx.fillRect(px + 3, py, 2, 2);
    ctx.fillRect(px, py + 2, 5, 1);
    ctx.fillRect(px + 1, py + 3, 3, 1);
    ctx.fillRect(px + 2, py + 4, 1, 1);
  } else if (kind === "cloud") {
    ctx.fillStyle = "rgba(240, 248, 255, 0.7)";
    ctx.fillRect(px, py + 1, 7, 2);
    ctx.fillRect(px + 1, py, 4, 1);
  } else if (kind === "datacenter") {
    // Perforated raised-floor tiles.
    ctx.fillStyle = "rgba(0, 0, 0, 0.5)";
    for (let row = 0; row < 3; row += 1) {
      for (let column = 0; column < 3; column += 1) {
        ctx.fillRect(x + 3 + column * 4, y + 3 + row * 4, 2, 2);
      }
    }
  } else {
    // Circuit traces running through black glass.
    ctx.fillStyle = "#ff4f6a";
    ctx.fillRect(px, py, 6, 1);
    ctx.fillRect(px + 5, py, 1, 4);
    ctx.fillRect(px + 5, py + 3, 3, 1);
  }
}

function paintWallFace(ctx, x, y, theme, kind, random) {
  if (kind === "oldweb") {
    // Raised grey panels, the look of every button in 1997.
    ctx.fillStyle = theme.wallFace[Math.floor(random() * theme.wallFace.length)];
    ctx.fillRect(x, y, BAKE, BAKE);
    ctx.fillStyle = "#f4f4f8";
    ctx.fillRect(x, y, BAKE - 1, 1);
    ctx.fillRect(x, y, 1, BAKE - 1);
    ctx.fillStyle = "#55555f";
    ctx.fillRect(x, y + BAKE - 1, BAKE, 1);
    ctx.fillRect(x + BAKE - 1, y, 1, BAKE);
    return;
  }
  if (kind === "datacenter") {
    // Rack fronts with a row of status lights.
    ctx.fillStyle = theme.wallFace[Math.floor(random() * theme.wallFace.length)];
    ctx.fillRect(x, y, BAKE, BAKE);
    ctx.fillStyle = theme.wallRim;
    ctx.fillRect(x, y, BAKE, 1);
    for (let row = 0; row < 3; row += 1) {
      ctx.fillStyle = "#0c0e10";
      ctx.fillRect(x + 1, y + 2 + row * 5, BAKE - 2, 4);
      ctx.fillStyle = random() > 0.2 ? "#4fe08a" : "#ffae5c";
      ctx.fillRect(x + 2 + Math.floor(random() * 10), y + 3 + row * 5, 2, 1);
    }
    return;
  }
  for (let row = 0; row < 3; row += 1) {
    const top = y + row * 5 + 1;
    const offset = row % 2 ? -4 : 0;
    for (let column = -1; column < 3; column += 1) {
      const left = x + column * 8 + offset;
      ctx.fillStyle = theme.wallFace[Math.floor(random() * theme.wallFace.length)];
      ctx.fillRect(Math.max(x, left), top, Math.min(7, x + BAKE - Math.max(x, left)), 4);
    }
  }
  ctx.fillStyle = theme.wallRim;
  ctx.fillRect(x, y, BAKE, 1);
}

function paintPillar(ctx, x, y, theme, random) {
  const size = BAKE * 2;
  ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
  ctx.fillRect(x + 2, y + 6, size, size - 2);
  ctx.fillStyle = theme.pillarFace;
  ctx.fillRect(x, y + 8, size, size - 8);
  ctx.fillStyle = theme.pillarTop;
  ctx.fillRect(x, y - 2, size, 12);
  ctx.fillStyle = "rgba(255, 255, 255, 0.22)";
  ctx.fillRect(x, y - 2, size, 1);
  ctx.fillRect(x, y - 2, 1, 12);
  ctx.fillStyle = "rgba(0, 0, 0, 0.3)";
  ctx.fillRect(x, y + size - 3, size, 3);
  ctx.fillStyle = theme.accent;
  ctx.globalAlpha = 0.5 + random() * 0.3;
  ctx.fillRect(x + size / 2 - 1, y + 14, 2, 8);
  ctx.fillRect(x + size / 2 - 4, y + 17, 8, 2);
  ctx.globalAlpha = 1;
}

/** The whole floor baked once per dungeon; it never changes during a run. */
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
  const random = seededRandom(Number(config.map_id) || 1);
  const open = (x, y) => rows[y]?.[x] === "." || rows[y]?.[x] === "o";

  ctx.fillStyle = theme.wallTop;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const pillars = [];
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const px = x * BAKE;
      const py = y * BAKE;
      const tile = rows[y][x];
      if (tile === "." || tile === "o") {
        paintFloorTile(ctx, px, py, theme, random);
        if (random() < 0.05) paintFloorDecor(ctx, px, py, theme, kind, random);
        if (tile === "o" && rows[y][x - 1] !== "o" && rows[y - 1]?.[x] !== "o") {
          pillars.push([px, py]);
        }
      } else if (open(x, y + 1)) {
        paintWallFace(ctx, px, py, theme, kind, random);
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

  // Walls throw a soft shadow onto the floor they stand on.
  for (let y = 1; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (open(x, y) && !open(x, y - 1)) {
        ctx.fillStyle = "rgba(0, 0, 0, 0.3)";
        ctx.fillRect(x * BAKE, y * BAKE, BAKE, 6);
        ctx.fillStyle = "rgba(0, 0, 0, 0.16)";
        ctx.fillRect(x * BAKE, y * BAKE + 6, BAKE, 5);
      }
    }
  }
  for (const [x, y] of pillars) paintPillar(ctx, x, y, theme, random);
  return canvas;
}

/** A tiny map of the floor: one pixel per tile, recoloured for the corner of the screen. */
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

const SNOW = Array.from({ length: 70 }, (_, index) => {
  const random = seededRandom(index * 97 + 13);
  return { x: random(), y: random(), speed: 0.3 + random() * 0.7, phase: random() * TAU };
});

/** Screen-space weather: it hangs in front of everything and costs almost nothing. */
export function drawWeather(ctx, config, width, height, now) {
  const kind = themeOf(config).weather;
  const t = now / 1000;
  ctx.save();
  for (const flake of SNOW) {
    let x = flake.x;
    let y = flake.y;
    let wide = 2;
    let tall = 2;
    if (kind === "hearts") {
      x = flake.x + Math.sin(t * 0.5 + flake.phase) * 0.02;
      y = flake.y - t * 0.05 * flake.speed + 4;
      ctx.fillStyle = "rgba(255, 107, 158, 0.42)";
      wide = 3;
      tall = 3;
    } else if (kind === "clouds") {
      x = flake.x + t * 0.008 * flake.speed;
      ctx.fillStyle = "rgba(240, 248, 255, 0.12)";
      wide = 70;
      tall = 18;
    } else if (kind === "binary") {
      y = flake.y + t * 0.16 * flake.speed;
      ctx.fillStyle = "rgba(79, 224, 138, 0.3)";
      wide = 2;
      tall = 7;
    } else if (kind === "glitch") {
      const slot = Math.floor(t * 3 + flake.phase * 4);
      x = (flake.x * 7.3 * (slot % 5 + 1)) % 1;
      y = (flake.y * 5.1 * (slot % 7 + 1)) % 1;
      ctx.fillStyle = slot % 3 ? "rgba(255, 79, 106, 0.28)" : "rgba(255, 255, 255, 0.1)";
      wide = 26;
      tall = 2;
    } else {
      x = flake.x + t * 0.004 * flake.speed;
      ctx.fillStyle = `rgba(255, 217, 61, ${0.14 + Math.max(0, Math.sin(t * 2 + flake.phase)) * 0.4})`;
    }
    ctx.fillRect(((x % 1) + 1) % 1 * width, ((y % 1) + 1) % 1 * height, wide, tall);
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

// Her copies must not be told apart by eye: that is what enemies() is for.
SPRITES.nullecho = SPRITES.nullqueen;

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
  const sprite = { canvas, flash, width: canvas.width, height: canvas.height };
  spriteCache.set(kind, sprite);
  return sprite;
}

function spriteFor(kind) {
  return spriteCache.get(kind) || bakeSprite(kind);
}

export function hasSprite(kind) {
  return Boolean(SPRITES[kind]);
}

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

export function drawMonster(ctx, visual, now) {
  const data = visual.data;
  const radius = Number(data.r) || 18;
  const sprite = spriteFor(data.kind);
  const t = now / 1000;
  const scale = (radius * 2.9) / Math.max(sprite.width, sprite.height);
  const width = sprite.width * scale;
  const height = sprite.height * scale;
  const state = data.state;
  const bob = Math.sin(t * 7 + data.id) * 2;
  const shaking = state === "aim" || state === "windup" || state === "slam" || state === "deploy";
  const jitter = shaking ? Math.sin(t * 60) * 2 : 0;
  const stretch = state === "dash" ? 1.14 : 1;
  const flip = Math.cos(Number(data.aim) || 0) < 0 ? -1 : 1;

  ctx.save();
  ctx.translate(visual.x + jitter, visual.y);
  ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
  ctx.beginPath();
  ctx.ellipse(0, radius * 0.72, radius * 0.95, radius * 0.38, 0, 0, TAU);
  ctx.fill();

  if (data.arriving) ctx.globalAlpha = 0.4 + Math.sin(t * 30) * 0.2;
  ctx.scale(flip, 1);
  ctx.imageSmoothingEnabled = false;
  const left = (-width * stretch) / 2;
  const top = radius * 0.86 - height + (state === "dash" ? 0 : bob * 0.5);
  ctx.drawImage(sprite.canvas, left, top, width * stretch, height);
  const flashing = Math.max(visual.hurt * 3.4, shaking ? 0.35 : 0, state === "dizzy" ? 0.25 : 0);
  if (flashing > 0) {
    ctx.globalAlpha = Math.min(0.9, flashing);
    ctx.drawImage(sprite.flash, left, top, width * stretch, height);
  }
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
