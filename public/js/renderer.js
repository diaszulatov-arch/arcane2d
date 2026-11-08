/* Canvas renderer: camera, mages, projectiles, wards, particles and HUD overlays. */

import { ROLE_TITLES } from "./content.js";
import { drawBossMoves } from "./boss-art.js";
import { drawMage, mageGhost } from "./mage-art.js";
import {
  blastFrame,
  drawGlyph,
  drawJaggedBolt,
  drawStar,
  flameFrame,
  frostShard,
  pixelLine,
  pixelRing,
  puffSprite,
  scorchSprite,
} from "./vfx.js";
import {
  OBSTACLE_HEIGHT,
  buildFloorCanvas,
  collectWorldLights,
  drawAmbient,
  drawArenaBorder,
  drawObstacle,
  drawWallTorches,
} from "./world-art.js";
import {
  buildDungeonCanvas,
  buildMinimap,
  collectDungeonLights,
  drawDoors,
  drawBarriers,
  drawBreakpoints,
  drawCables,
  drawFloorLife,
  drawHazards,
  drawLamps,
  drawMonster,
  drawMonsterBar,
  drawPickups,
  drawPortal,
  drawSudo,
  drawTerminals,
  drawWeather,
  spriteColors,
  themeOf,
} from "./dungeon-art.js";
import {
  buildFog,
  buildFoggedMinimap,
  darkRooms,
  drawFog,
  drawQuestFloor,
  drawQuestObjects,
  drawUnitBars,
  flushLabels,
  isSeen,
  label as questLabel,
  questLights,
} from "./quest-art.js";
import {
  drawGust,
  drawProps,
  drawSpamStorm,
  drawTerrainFloor,
  terrainLights,
} from "./terrain-art.js";

const TAU = Math.PI * 2;
const DUST_EVERY = 0.13;
const BAKE_TILE = 16;
const GOLD = "#d9b56c";
const VIOLET = "#a997ff";
const EMP_COLOR = "#b38cff";

// What a stone looks like with no light on it: the room is dim, not black, so
// nothing a player must read ever disappears.
const AMBIENT_LIGHT = "#6d6682";
const SELF_LIGHT = "#ffe6c4";
const LIGHT_SPRITE_SIZE = 96;
const BLOOM_STRENGTH = 0.42;
const MINIMAP_WIDTH = 170;
const MINIMAP_HEIGHT = 120;
// Blasts open on the floor and mages stand over them, so a fight never hides them.
const GROUND_EFFECTS = new Set(["scorch"]);
const SCORCH_LIMIT = 14;
const SAVE_DEPTH = 64;
const ROLE_BANDS = { admin: "#ffd93d", hacker: "#7fffb0", devops: "#6fd6ff", tester: "#e08cff" };
const QUALITY_FULL = 2;
const QUALITY_LIGHTS = 1;
const SLOW_FRAME = 1 / 28;

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

function rgba(hex, alpha) {
  const fallback = [217, 181, 108];
  if (typeof hex !== "string") {
    return `rgba(${fallback.join(",")},${alpha})`;
  }
  let value = hex.replace("#", "");
  if (value.length === 3) {
    value = value
      .split("")
      .map((char) => char + char)
      .join("");
  }
  const number = parseInt(value, 16);
  if (!Number.isFinite(number)) {
    return `rgba(${fallback.join(",")},${alpha})`;
  }
  return `rgba(${(number >> 16) & 255},${(number >> 8) & 255},${number & 255},${alpha})`;
}

function mixHex(hex, target, amount) {
  const parse = (value) => {
    const raw = String(value || "").replace("#", "");
    const full =
      raw.length === 3
        ? raw
            .split("")
            .map((char) => char + char)
            .join("")
        : raw.padEnd(6, "0").slice(0, 6);
    const number = parseInt(full, 16);
    return Number.isFinite(number)
      ? [(number >> 16) & 255, (number >> 8) & 255, number & 255]
      : [217, 181, 108];
  };
  const from = parse(hex);
  const to = parse(target);
  const channels = from.map((channel, index) =>
    Math.round(channel + (to[index] - channel) * clamp(amount, 0, 1)),
  );
  return `#${channels.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}

function lerpAngle(current, target, amount) {
  let delta = ((target - current + Math.PI) % TAU + TAU) % TAU - Math.PI;
  return current + delta * amount;
}

function roundedRectPath(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}

function wrapText(ctx, text, maxWidth, maxLines = 3) {
  const words = String(text).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const lines = [];
  let line = "";
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (ctx.measureText(candidate).width <= maxWidth) {
      line = candidate;
      continue;
    }
    if (line) lines.push(line);
    line = word;
    if (lines.length === maxLines - 1) break;
  }
  if (line && lines.length < maxLines) lines.push(line);
  if (lines.length === maxLines) {
    const joined = lines.join(" ");
    if (joined.length < String(text).length) {
      let last = lines[maxLines - 1];
      while (last.length > 1 && ctx.measureText(`${last}…`).width > maxWidth) {
        last = last.slice(0, -1);
      }
      lines[maxLines - 1] = `${last}…`;
    }
  }
  return lines;
}

const CURSE_LABELS = { syntax: "SyntaxError", null: "None", mirror: "АВТОКОРРЕКЦИЯ" };

const ELITE_COLORS = {
  legacy: "#c9a26b",
  hotfix: "#7fe0a8",
  fork: "#b18cff",
  prod: "#ff7a5a",
  async: "#6fd3ff",
  deprecated: "#ffd86b",
};

export class ArenaRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d", { alpha: false });
    this.width = 0;
    this.height = 0;
    this.dpr = 1;
    this.pixelScale = 0.5;
    this.worldCanvas = document.createElement("canvas");
    this.worldCtx = this.worldCanvas.getContext("2d", { alpha: false });
    this.lightCanvas = document.createElement("canvas");
    this.lightCtx = this.lightCanvas.getContext("2d", { alpha: false });
    this.bloomCanvas = document.createElement("canvas");
    this.bloomCtx = this.bloomCanvas.getContext("2d", { alpha: false });
    this.softCanvas = document.createElement("canvas");
    this.softCtx = this.softCanvas.getContext("2d", { alpha: false });
    this.lightSprites = new Map();
    this.lights = [];
    // ?fx=0, 1 or 2 pins the effects; otherwise they step down on a slow machine.
    const pinned = new URLSearchParams(window.location.search).get("fx");
    this.qualityPinned = pinned === "0" || pinned === "1" || pinned === "2";
    this.quality = this.qualityPinned ? Number(pinned) : QUALITY_FULL;
    this.frameAverage = 1 / 60;
    this.qualityCheckedAt = performance.now();
    this.calmMotion =
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    this.camera = { x: 950, y: 550, zoom: 0.8 };
    this.visualPlayers = new Map();
    this.visualMonsters = new Map();
    this.visualProjectiles = new Map();
    this.minimap = null;
    this.particles = [];
    this.effects = [];
    this.floaters = [];
    this.speeches = [];
    this.shakeAmount = 0;
    this.floorCanvas = null;
    this.floorKey = "";
    this.lastFrame = performance.now();
    this.frame = 0;
    this.resize();
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    const width = Math.max(1, Math.round(rect.width || this.canvas.clientWidth || 960));
    const height = Math.max(1, Math.round(rect.height || this.canvas.clientHeight || 720));
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    if (width === this.width && height === this.height && dpr === this.dpr) return;
    this.width = width;
    this.height = height;
    this.dpr = dpr;
    this.canvas.width = Math.max(1, Math.round(width * dpr));
    this.canvas.height = Math.max(1, Math.round(height * dpr));

    const pixelSize = width < 720 ? 1.65 : 2.2;
    this.pixelScale = 1 / pixelSize;
    this.worldCanvas.width = Math.max(1, Math.round(width * this.pixelScale));
    this.worldCanvas.height = Math.max(1, Math.round(height * this.pixelScale));
    this.lightCanvas.width = this.worldCanvas.width;
    this.lightCanvas.height = this.worldCanvas.height;
    this.bloomCanvas.width = Math.max(1, Math.round(this.worldCanvas.width / 3));
    this.bloomCanvas.height = Math.max(1, Math.round(this.worldCanvas.height / 3));
    this.softCanvas.width = Math.max(1, Math.round(this.bloomCanvas.width / 3));
    this.softCanvas.height = Math.max(1, Math.round(this.bloomCanvas.height / 3));
  }

  screenToWorld(x, y) {
    const { zoom } = this.camera;
    return {
      x: this.camera.x + (x - this.width / 2) / zoom,
      y: this.camera.y + (y - this.height / 2) / zoom,
    };
  }

  worldToScreen(x, y) {
    const { zoom } = this.camera;
    return {
      x: (x - this.camera.x) * zoom + this.width / 2,
      y: (y - this.camera.y) * zoom + this.height / 2,
    };
  }

  /** Rooms nobody has entered stay static: rebuilt only when one loads. */
  ensureFog(client) {
    const config = client.config;
    if (config?.mode !== "story" || !client.story?.seen) {
      return;
    }
    const key = `${this.floorKey}|${client.story.seen.join(",")}`;
    if (key === this.fogKey) return;
    this.fogKey = key;
    this.fogTile = config.tile || 48;
    this.fog = buildFog(config, new Set(client.story.seen));
    this.minimap = buildFoggedMinimap(config, this.fog);
  }

  seen(x, y) {
    return isSeen(this.fog, x, y, this.fogTile || 48);
  }

  /** Whether a spot is out of every light in a room with none of its own. */
  inDark(x, y, client) {
    const tile = client.config?.tile || 48;
    const room = (this.darkRooms || []).find(
      (entry) => x >= entry.x * tile && x <= (entry.x + entry.w) * tile && y >= entry.y * tile && y <= (entry.y + entry.h) * tile,
    );
    if (!room) return false;
    for (const visual of this.visualPlayers.values()) {
      if (!visual.dead && Math.hypot(visual.x - x, visual.y - y) < 300) return false;
    }
    return true;
  }

  darkInView(client) {
    const tile = client.config?.tile || 48;
    const { zoom, x, y } = this.camera;
    const halfW = this.width / zoom / 2;
    const halfH = this.height / zoom / 2;
    return (this.darkRooms || []).some(
      (room) =>
        room.x * tile < x + halfW &&
        (room.x + room.w) * tile > x - halfW &&
        room.y * tile < y + halfH &&
        (room.y + room.h) * tile > y - halfH,
    );
  }

  ensureFloor(config) {
    if (config?.mode === "story") {
      const key = `map:${config.theme}:${config.map_id}:${config.tilesVersion || 0}`;
      if (key !== this.floorKey) {
        this.floorCanvas = buildDungeonCanvas(config);
        this.minimap = buildMinimap(config);
        this.floorKey = key;
        this.fog = null;
        this.fogKey = "";
        this.darkRooms = darkRooms(config);
      }
      return;
    }
    const width = config?.arena?.w || 1900;
    const height = config?.arena?.h || 1100;
    const border = config?.arena?.border || 46;
    const key = `${width}x${height}x${border}`;
    if (key !== this.floorKey) {
      this.floorCanvas = buildFloorCanvas(config);
      this.floorKey = key;
    }
  }

  /** Forget the last place: a new floor must not start with old sparks flying. */
  resetScene(x, y) {
    this.visualPlayers.clear();
    this.visualMonsters.clear();
    this.visualProjectiles.clear();
    this.particles = [];
    this.effects = [];
    this.floaters = [];
    this.speeches = [];
    this.shakeAmount = 0;
    if (Number.isFinite(x) && Number.isFinite(y)) {
      this.camera.x = x;
      this.camera.y = y;
    }
  }

  // ------------------------------------------------------------------ camera
  updateCamera(client, dt) {
    const arenaWidth = client?.config?.arena?.w || 1900;
    const arenaHeight = client?.config?.arena?.h || 1100;
    const joined = Boolean(client?.joined);
    const localSnapshot = client?.selfId ? client?.players?.get(client.selfId) : null;
    let targetX = arenaWidth / 2;
    let targetY = arenaHeight / 2;
    let targetZoom;

    if (!joined) {
      const fit = Math.min(
        (this.width - 70) / arenaWidth,
        (this.height - 70) / arenaHeight,
      );
      targetZoom = clamp(fit, 0.28, 1.02);
    } else {
      const predicted = client?.prediction;
      if (predicted?.active) {
        targetX = predicted.x;
        targetY = predicted.y;
      } else if (localSnapshot) {
        targetX = localSnapshot.x;
        targetY = localSnapshot.y;
      }
      if (client?.pointer?.inside && !client.pointer.touch) {
        targetX += clamp((client.pointer.x - this.width / 2) * 0.055, -54, 54);
        targetY += clamp((client.pointer.y - this.height / 2) * 0.055, -38, 38);
      }
      targetZoom = clamp(
        Math.min(this.width / 1500, this.height / 960),
        0.46,
        1.12,
      );
    }
    if (joined && this.height > this.width * 1.12) {
      // Portrait phones need a closer camera, otherwise the arena becomes a
      // thin letterboxed strip between the HUD and the hotbar.
      targetZoom = clamp(this.height / 1080, 0.6, 1.05);
    }

    const follow = 1 - Math.exp(-dt * (joined ? 5.6 : 2.4));
    this.camera.x += (targetX - this.camera.x) * follow;
    this.camera.y += (targetY - this.camera.y) * follow;
    this.camera.zoom += (targetZoom - this.camera.zoom) * (1 - Math.exp(-dt * 3.6));

    const zoom = this.camera.zoom;
    const halfWidth = this.width / (2 * zoom);
    const halfHeight = this.height / (2 * zoom);
    this.camera.x =
      arenaWidth > halfWidth * 2
        ? clamp(this.camera.x, halfWidth, arenaWidth - halfWidth)
        : arenaWidth / 2;
    this.camera.y =
      arenaHeight > halfHeight * 2
        ? clamp(this.camera.y, halfHeight, arenaHeight - halfHeight)
        : arenaHeight / 2;
  }

  shake(amount) {
    const scaled = this.calmMotion ? amount * 0.2 : amount;
    this.shakeAmount = Math.min(24, this.shakeAmount + scaled);
  }

  shakeNear(client, x, y, amount) {
    const local = client?.players?.get(client?.selfId);
    if (!local) {
      this.shake(amount * 0.4);
      return;
    }
    const distance = Math.hypot(local.x - x, local.y - y);
    const falloff = clamp(1 - distance / 1000, 0, 1);
    if (falloff > 0) this.shake(amount * falloff);
  }

  // ---------------------------------------------------------------- entities
  updateVisuals(client, dt) {
    const seen = new Set();
    for (const player of client.players.values()) {
      seen.add(player.id);
      let visual = this.visualPlayers.get(player.id);
      if (!visual) {
        visual = {
          x: player.x,
          y: player.y,
          aim: player.aim || 0,
          hurt: 0,
          cast: 0,
          roll: 0,
          data: player,
        };
        this.visualPlayers.set(player.id, visual);
      }
      visual.data = player;
      const previousX = visual.x;
      const previousY = visual.y;
      const isSelf = player.id === client.selfId;
      if (isSelf && client.prediction?.active && !player.dead) {
        visual.x = client.prediction.x;
        visual.y = client.prediction.y;
        visual.aim = client.aim || 0;
      } else {
        const smoothing = 1 - Math.exp(-dt * 22);
        visual.x += (player.x - visual.x) * smoothing;
        visual.y += (player.y - visual.y) * smoothing;
        visual.aim = lerpAngle(visual.aim, player.aim || 0, 1 - Math.exp(-dt * 20));
      }
      const moved = Math.hypot(visual.x - previousX, visual.y - previousY);
      const trailing = clamp(((previousX - visual.x) / dt) * 0.035, -9, 9);
      visual.cloak = (visual.cloak || 0) + (trailing - (visual.cloak || 0)) * (1 - Math.exp(-dt * 7));
      visual.moving = moved > 0.25;
      visual.step = (visual.step || 0) + Math.min(0.55, moved * 0.11);
      visual.dust = (visual.dust || 0) - dt;
      if (visual.moving && visual.dust <= 0 && !player.dead && this.quality >= QUALITY_LIGHTS) {
        visual.dust = DUST_EVERY;
        this.burst(visual.x + (Math.random() - 0.5) * 12, visual.y + 8, "#d8d4e4", 1, 22, {
          kind: "dust",
          size: 3,
          life: 0.42,
          drag: 3.5,
        });
      }
      visual.hurt = Math.max(0, visual.hurt - dt);
      visual.cast = Math.max(0, visual.cast - dt);
      visual.roll = Math.max(0, (visual.roll || 0) - dt);
      visual.stunFlash = Math.max(0, (visual.stunFlash || 0) - dt);
      visual.dead = player.dead;
    }
    for (const id of this.visualPlayers.keys()) {
      if (!seen.has(id)) this.visualPlayers.delete(id);
    }

    const seenMonsters = new Set();
    for (const monster of client.monsters || []) {
      seenMonsters.add(monster.id);
      let visual = this.visualMonsters.get(monster.id);
      if (!visual) {
        visual = { x: monster.x, y: monster.y, hurt: 0, data: monster, born: performance.now(), pace: 0, dirX: 0 };
        this.visualMonsters.set(monster.id, visual);
      }
      visual.data = monster;
      const smoothing = 1 - Math.exp(-dt * 20);
      const stepX = (monster.x - visual.x) * smoothing;
      const stepY = (monster.y - visual.y) * smoothing;
      visual.x += stepX;
      visual.y += stepY;
      const easing = 1 - Math.exp(-dt * 9);
      visual.pace += (Math.hypot(stepX, stepY) / dt - visual.pace) * easing;
      visual.dirX += (stepX / dt - visual.dirX) * easing;
      visual.hurt = Math.max(0, visual.hurt - dt);
    }
    for (const id of this.visualMonsters.keys()) {
      if (!seenMonsters.has(id)) this.visualMonsters.delete(id);
    }

    const seenProjectiles = new Set();
    for (const projectile of client.projectiles) {
      seenProjectiles.add(projectile.id);
      let visual = this.visualProjectiles.get(projectile.id);
      if (!visual) {
        visual = {
          x: projectile.x,
          y: projectile.y,
          angle: projectile.angle || 0,
          trail: [],
          data: projectile,
        };
        this.visualProjectiles.set(projectile.id, visual);
      }
      visual.data = projectile;
      // Fly on between snapshots at the bolt's own speed, so it moves every
      // frame rather than in 30 Hz hops, and only drift back toward the server.
      visual.angle = projectile.angle || 0;
      const speed = Number(projectile.speed) || 0;
      visual.x += Math.cos(visual.angle) * speed * dt;
      visual.y += Math.sin(visual.angle) * speed * dt;
      const correction = 1 - Math.exp(-dt * 14);
      visual.x += (projectile.x - visual.x) * correction;
      visual.y += (projectile.y - visual.y) * correction;
      visual.trail.push({ x: visual.x, y: visual.y });
      if (visual.trail.length > 20) visual.trail.shift();
    }
    for (const id of this.visualProjectiles.keys()) {
      if (!seenProjectiles.has(id)) this.visualProjectiles.delete(id);
    }
  }

  updateEffects(dt) {
    for (const effect of this.effects) effect.age += dt;
    this.effects = this.effects.filter((effect) => effect.age < effect.life);

    for (const particle of this.particles) {
      particle.life -= dt;
      particle.x += particle.vx * dt;
      particle.y += particle.vy * dt;
      particle.vx *= Math.exp(-dt * particle.drag);
      particle.vy *= Math.exp(-dt * particle.drag);
      particle.rotation += particle.spin * dt;
      if (particle.rise) particle.y -= particle.rise * dt;
      if (particle.gravity) {
        particle.vy += particle.gravity * dt;
        if (particle.y > particle.ground) {
          particle.y = particle.ground;
          particle.vy *= -0.38;
          particle.vx *= 0.62;
          particle.spin *= 0.5;
        }
      }
    }
    this.particles = this.particles.filter((particle) => particle.life > 0);

    for (const floater of this.floaters) floater.life -= dt;
    this.floaters = this.floaters.filter((floater) => floater.life > 0);

    for (const speech of this.speeches) speech.life -= dt;
    this.speeches = this.speeches.filter((speech) => speech.life > 0);
  }

  // ----------------------------------------------------------------- effects
  burst(x, y, color, count, speed, options = {}) {
    const {
      size = 2.2,
      life = 0.65,
      kind = "ember",
      angle = null,
      spread = Math.PI * 2,
      drag = 3,
      gravity = 0,
      ground = 0,
      rise = 0,
    } = options;
    for (let index = 0; index < count; index += 1) {
      const direction =
        angle === null ? Math.random() * TAU : angle + (Math.random() - 0.5) * spread;
      const velocity = speed * (0.25 + Math.random() * 0.9);
      this.particles.push({
        x,
        y,
        vx: Math.cos(direction) * velocity,
        vy: Math.sin(direction) * velocity,
        life: life * (0.55 + Math.random() * 0.75),
        maxLife: life,
        size: size * (0.5 + Math.random()),
        color,
        kind,
        drag,
        gravity,
        ground,
        rise,
        glyph: Math.floor(Math.random() * 8),
        rotation: Math.random() * TAU,
        spin: (Math.random() - 0.5) * 9,
      });
    }
    if (this.particles.length > 650) {
      this.particles.splice(0, this.particles.length - 650);
    }
  }

  addRing(x, y, from, to, color, life = 0.5, width = 2, options = {}) {
    this.effects.push({
      kind: "ring",
      x,
      y,
      from,
      to,
      color,
      life,
      width,
      age: 0,
      ...options,
    });
  }

  addNova(x, y, radius, color, life = 0.7) {
    this.effects.push({
      kind: "nova",
      x,
      y,
      radius,
      color,
      life,
      age: 0,
    });
  }

  addExplosion(x, y, color, element = "fire", scale = 1) {
    this.effects.push({
      kind: "explosion",
      x,
      y,
      color,
      element,
      scale,
      life: element === "frost" ? 0.5 : 0.62,
      age: 0,
    });
    const marks = this.effects.filter((effect) => effect.kind === "scorch");
    if (marks.length >= SCORCH_LIMIT) this.effects.splice(this.effects.indexOf(marks[0]), 1);
    this.effects.push({
      kind: "scorch",
      x,
      y,
      color,
      element,
      scale,
      variant: Math.floor(Math.random() * 4),
      life: element === "frost" ? 2.6 : 4.2,
      age: 0,
    });
    if (this.quality < QUALITY_LIGHTS) return;
    const smoke = element === "frost" ? "#c8e4f0" : element === "emp" ? "#2a2240" : "#26222a";
    const puffs = Math.round(5 * Math.min(2.4, scale));
    for (let puff = 0; puff < puffs; puff += 1) {
      this.burst(x + (Math.random() - 0.5) * 34 * scale, y + (Math.random() - 0.5) * 24 * scale, smoke, 1, 26, {
        kind: "smoke",
        size: (11 + Math.random() * 9) * scale,
        life: 0.9 + Math.random() * 0.7,
        drag: 1.5,
        rise: 42 + Math.random() * 34,
      });
    }
  }

  /**
   * After a frame that threw. Whatever could not be drawn is not worth another try,
   * and the canvases are still halfway through it: unbalanced save()s, additive
   * blending, a stray transform. Left alone, every later frame would come out wrong.
   */
  recoverFrame() {
    this.particles.length = 0;
    this.effects.length = 0;
    for (const ctx of [this.worldCtx, this.ctx]) {
      if (!ctx) continue;
      for (let depth = 0; depth < SAVE_DEPTH; depth += 1) ctx.restore();
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";
    }
  }

  /** The silhouettes a fast mover leaves behind. */
  addGhosts(id, x1, y1, x2, y2, count, color) {
    const visual = this.visualPlayers.get(id);
    if (!visual) return;
    const ghost = mageGhost(visual, color, this.bandOf(visual.data));
    for (let index = 0; index < count; index += 1) {
      const at = (index + 0.5) / count;
      this.effects.push({
        kind: "ghost",
        ghost,
        x: x1 + (x2 - x1) * at,
        y: y1 + (y2 - y1) * at,
        life: 0.22 + at * 0.26,
        age: 0,
      });
    }
  }

  bandOf(player) {
    return ROLE_BANDS[player?.role] || "#f3d27f";
  }

  addLine(x1, y1, x2, y2, color, life = 0.35, width = 3) {
    this.effects.push({
      kind: "line",
      x1,
      y1,
      x2,
      y2,
      color,
      life,
      width,
      age: 0,
    });
  }

  addBolt(points, color, life = 0.38, width = 4) {
    if (!Array.isArray(points) || points.length < 2) return;
    const path = points
      .map((point) =>
        Array.isArray(point)
          ? { x: Number(point[0]), y: Number(point[1]) }
          : { x: Number(point?.x), y: Number(point?.y) },
      )
      .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
    if (path.length < 2) return;
    this.effects.push({
      kind: "bolt",
      points: path,
      color,
      life,
      width,
      age: 0,
    });
  }

  addFloater(x, y, text, color, size = 12) {
    this.floaters.push({
      x,
      y,
      text: String(text),
      color,
      size,
      life: 1.05,
      maxLife: 1.05,
      drift: (Math.random() - 0.5) * 22,
    });
  }

  addSpeech(id, text) {
    const clean = String(text).slice(0, 80);
    if (!clean) return;
    const existing = this.speeches.find((speech) => speech.id === id);
    if (existing) {
      existing.text = clean;
      existing.life = 4.6;
      return;
    }
    this.speeches.push({ id, text: clean, life: 4.6 });
    if (this.speeches.length > 8) this.speeches.shift();
  }

  handleEvent(event, client) {
    if (!event || typeof event !== "object") return;
    const kind = event.e;
    const color = event.color || GOLD;
    switch (kind) {
      case "cast": {
        this.burst(event.x, event.y, color, 10, 150, { size: 2.6, life: 0.5, kind: "ember" });
        // The mage is typing: bits of syntax come off the staff.
        this.burst(event.x, event.y, color, 5, 66, { size: 3, life: 0.75, kind: "rune", rise: 26 });
        this.addRing(event.x, event.y, 4, 26, color, 0.28, 1.6);
        const visual = this.visualPlayers.get(event.id);
        if (visual) visual.cast = 0.4;
        break;
      }
      case "impact": {
        if (event.kind === "orb") {
          this.burst(event.x, event.y, color, 10, 150, { size: 2, life: 0.35, kind: "spark" });
          this.addRing(event.x, event.y, 3, 22, color, 0.24, 1.6);
          break;
        }
        const shard = event.kind === "frost";
        const spark = event.kind === "spark";
        if (spark) {
          this.effects.push({ kind: "star", x: event.x, y: event.y, size: 26, color, life: 0.2, age: 0, turn: Math.random() });
          this.burst(event.x, event.y, color, 12, 240, { size: 2.1, life: 0.42, kind: "spark" });
        } else {
          this.addExplosion(event.x, event.y, color, shard ? "frost" : "fire", shard ? 0.92 : 1.2);
          this.burst(event.x, event.y, shard ? "#e6fdff" : color, shard ? 22 : 26, 290, {
            size: shard ? 3 : 3.4,
            life: 0.7,
            kind: shard ? "shard" : "ember",
          });
        }
        this.shakeNear(client, event.x, event.y, spark ? 2.2 : shard ? 3.6 : 4.8);
        break;
      }
      case "hit": {
        const damage = Number(event.amount) || 0;
        const absorbed = Number(event.absorbed) || 0;
        if (damage > 0) {
          this.addFloater(
            event.x + (Math.random() - 0.5) * 12,
            event.y - 14,
            `−${Math.max(1, Math.round(damage))}`,
            event.id === client.selfId ? "#ff9aa0" : "#ffd7b0",
            16,
          );
        }
        if (absorbed > 0) {
          this.addFloater(event.x + 13, event.y - 6, `−${Math.round(absorbed)} щит`, "#a9c6ff", 13);
        }
        this.effects.push({ kind: "star", x: event.x, y: event.y, size: 18, color: "#ffe9c8", life: 0.13, age: 0, turn: Math.random() });
        this.burst(event.x, event.y, color, 9, 150, { size: 2, life: 0.38, kind: "spark" });
        const hitVisual =
          this.visualPlayers.get(event.id) || this.visualMonsters.get(event.id);
        if (hitVisual) hitVisual.hurt = 0.3;
        this.shakeNear(
          client,
          event.x,
          event.y,
          event.id === client.selfId ? 7 : 2.7,
        );
        break;
      }
      case "death": {
        this.burst(event.x, event.y, color, 38, 210, {
          size: 2.6,
          life: 1.05,
          kind: "ember",
        });
        this.burst(event.x, event.y, "#f6dfb0", 12, 90, {
          size: 1.6,
          life: 0.7,
          kind: "rune",
        });
        this.addRing(event.x, event.y, 10, 70, "#c8757c", 0.7, 2.2);
        this.addRing(event.x, event.y, 3, 44, color, 0.5, 1.2);
        this.shakeNear(client, event.x, event.y, event.id === client.selfId ? 11 : 4);
        break;
      }
      case "respawn": {
        this.burst(event.x, event.y, "#f4d99b", 24, 90, {
          size: 2,
          life: 1,
          kind: "rune",
         });
        this.addRing(event.x, event.y, 5, 50, "#f4d99b", 0.8, 2);
        this.addRing(event.x, event.y, 50, 12, VIOLET, 0.9, 1);
        break;
      }
      case "dash": {
        const dashColor = event.color || VIOLET;
        const blink = event.kind === "blink";
        this.addGhosts(event.id, event.from_x, event.from_y, event.to_x, event.to_y, blink ? 3 : 6, dashColor);
        this.addLine(
          event.from_x,
          event.from_y,
          event.to_x,
          event.to_y,
          dashColor,
          blink ? 0.3 : 0.46,
          blink ? 6 : 8,
        );
        const steps = blink ? 5 : 9;
        for (let index = 0; index <= steps; index += 1) {
          const at = index / steps;
          const x = event.from_x + (event.to_x - event.from_x) * at;
          const y = event.from_y + (event.to_y - event.from_y) * at;
          this.burst(x, y, dashColor, blink ? 2 : 3, 105, {
            size: 2.4,
            life: 0.42,
            kind: "wisp",
          });
        }
        this.addRing(event.to_x, event.to_y, 6, blink ? 42 : 34, dashColor, 0.45, 2);
        this.shakeNear(client, event.to_x, event.to_y, blink ? 3 : 2.2);
        break;
      }
      case "roll": {
        const rollColor = event.color || VIOLET;
        this.addGhosts(event.id, event.x, event.y, event.x2, event.y2, 4, rollColor);
        this.addRing(event.x2, event.y2, 4, 28, rollColor, 0.38, 1.8);
        for (let index = 0; index < 9; index += 1) {
          const at = index / 8;
          this.burst(
            event.x + (event.x2 - event.x) * at,
            event.y + (event.y2 - event.y) * at,
            rollColor,
            2,
            78,
            { size: 1.9, life: 0.4, kind: "wisp" },
          );
        }
        const roller = this.visualPlayers.get(event.id);
        if (roller) roller.roll = 0.32;
        this.shakeNear(client, event.x2, event.y2, 1.8);
        break;
      }
      case "chain_lightning": {
        const chainColor = event.color || "#c9f6ff";
        const points = Array.isArray(event.points) ? event.points : [];
        this.addBolt(points, chainColor, 0.42, 4.5);
        for (const point of points) {
          const x = Array.isArray(point) ? point[0] : point?.x;
          const y = Array.isArray(point) ? point[1] : point?.y;
          if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
          this.burst(x, y, chainColor, 10, 155, {
            size: 2.1,
            life: 0.4,
            kind: "spark",
          });
          this.addRing(x, y, 3, 24, chainColor, 0.32, 1.4);
        }
        if (points.length) {
          const end = points[points.length - 1];
          const x = Array.isArray(end) ? end[0] : end?.x;
          const y = Array.isArray(end) ? end[1] : end?.y;
          if (Number.isFinite(x) && Number.isFinite(y)) {
            this.shakeNear(client, x, y, 5);
          }
        }
        break;
      }
      case "lightning_strike": {
        const strikeX = Number(event.x) || 0;
        const strikeY = Number(event.y) || 0;
        const strikeColor = event.color || "#9fd4ff";
        const height = 390;
        const makePath = (spread, stepCount) => {
          const points = [];
          for (let index = 0; index <= stepCount; index += 1) {
            const at = index / stepCount;
            const envelope = 0.35 + Math.sin(at * Math.PI) * 0.65;
            const jitter =
              Math.sin(index * 2.7 + strikeX * 0.03) * spread * envelope;
            points.push({
              x: strikeX + jitter,
              y: strikeY - height * (1 - at),
            });
          }
          points[points.length - 1] = { x: strikeX, y: strikeY };
          return points;
        };
        const mainPath = makePath(19, 13);
        this.addLine(
          strikeX,
          strikeY - height,
          strikeX,
          strikeY,
          "#718cff",
          0.2,
          27,
        );
        this.addBolt(mainPath, "#7892ff", 0.52, 10);
        this.addBolt(mainPath, strikeColor, 0.44, 4.4);
        this.addBolt(mainPath, "#f4fbff", 0.27, 1.7);
        this.addBolt(
          [
            mainPath[3],
            { x: strikeX + 27, y: strikeY - height * 0.63 + 19 },
            { x: strikeX + 58, y: strikeY - height * 0.55 + 3 },
          ],
          "#b8a2ff",
          0.3,
          2.2,
        );
        this.addBolt(
          [
            mainPath[5],
            { x: strikeX - 44, y: strikeY - height * 0.5 + 23 },
            { x: strikeX - 64, y: strikeY - height * 0.42 + 8 },
          ],
          "#d8c7ff",
          0.28,
          1.8,
        );
        this.addBolt(
          [
            mainPath[7],
            { x: strikeX + 38, y: strikeY - height * 0.34 + 15 },
            { x: strikeX + 61, y: strikeY - height * 0.27 + 2 },
          ],
          "#b9dfff",
          0.24,
          1.4,
        );
        this.addExplosion(strikeX, strikeY, "#b78cff", "emp", 1.25);
        this.addNova(strikeX, strikeY, 118, "#b58dff", 0.72);
        this.addRing(strikeX, strikeY, 10, 96, "#a8c9ff", 0.58, 3.2);
        this.addRing(strikeX, strikeY, 4, 54, "#f2f8ff", 0.42, 1.6);
        this.burst(strikeX, strikeY, "#c6a6ff", 38, 285, {
          size: 3,
          life: 0.9,
          kind: "wisp",
        });
        this.burst(strikeX, strikeY, strikeColor, 28, 230, {
          size: 2.5,
          life: 0.72,
          kind: "spark",
        });
        this.burst(strikeX, strikeY, "#ffffff", 15, 105, {
          size: 1.5,
          life: 0.4,
          kind: "spark",
          angle: -Math.PI / 2,
          spread: 2.1,
        });
        const caster = this.visualPlayers.get(event.id);
        if (caster) caster.cast = 0.4;
        const stunDuration = Number(event.stun) || 0;
        const victim = this.visualPlayers.get(event.target_id);
        if (victim) {
          victim.hurt = 0.3;
          if (stunDuration > 0) victim.stunFlash = stunDuration;
        }
        if (event.target_id === client.selfId && stunDuration > 0) {
          this.addFloater(strikeX, strikeY - 52, "ОГЛУШЕНИЕ", "#dbeaff", 10);
        }
        this.shakeNear(client, strikeX, strikeY, 9);
        break;
      }
      case "meteor": {
        const meteorColor = event.color || "#ff7b45";
        const radius = event.radius || 120;
        this.addRing(event.x, event.y, 5, 36, meteorColor, 0.55, 2.4);
        this.addRing(event.x, event.y, radius, radius * 0.8, meteorColor, 1.15, 1.2);
        this.burst(event.x, event.y, meteorColor, 16, 75, {
          size: 1.8,
          life: 0.8,
          kind: "ember",
        });
        break;
      }
      case "meteor_impact": {
        const meteorColor = event.color || "#ff7b45";
        const radius = event.radius || 120;
        const isMain = event.role !== "satellite";
        const strength = isMain ? 1 : 0.46;
        this.addNova(event.x, event.y, radius * strength, meteorColor, 0.82);
        if (isMain) {
          this.addExplosion(event.x, event.y, meteorColor, "fire", 1.8);
        }
        this.addRing(
          event.x,
          event.y,
          radius * strength,
          4,
          meteorColor,
          0.62,
          3.2,
        );
        this.burst(
          event.x,
          event.y,
          meteorColor,
          isMain ? 46 : 22,
          isMain ? 330 : 180,
          {
            size: 3.4,
            life: 0.92,
            kind: "ember",
          },
        );
        this.burst(
          event.x,
          event.y,
          "#ffe9b0",
          isMain ? 18 : 8,
          isMain ? 185 : 110,
          {
            size: 2,
            life: 0.54,
            kind: "spark",
          },
        );
        this.shakeNear(client, event.x, event.y, isMain ? 11 : 4);
        break;
      }
      case "siphon": {
        const siphonColor = event.color || "#ff6b9e";
        this.effects.push({
          kind: "beam",
          x1: event.x,
          y1: event.y,
          x2: event.x2,
          y2: event.y2,
          width: event.width || 64,
          color: siphonColor,
          life: 0.48,
          age: 0,
          reverse: true,
        });
        this.burst(event.x2, event.y2, siphonColor, 22, 170, {
          size: 2.2,
          life: 0.55,
          kind: "wisp",
        });
        this.burst(event.x, event.y, "#ffd4e2", 12, 100, {
          size: 1.7,
          life: 0.42,
          kind: "spark",
        });
        if (Number(event.healed) > 0) {
          this.addFloater(
            event.x,
            event.y - 30,
            `+${Math.round(Number(event.healed))}`,
            "#7ce0b6",
            16,
          );
        }
        this.shakeNear(client, event.x, event.y, 3.4);
        break;
      }
      case "poison_cloud": {
        const poisonColor = event.color || "#86e08a";
        const radius = event.radius || 110;
        this.addRing(event.x, event.y, 5, radius, poisonColor, 0.7, 2);
        this.burst(event.x, event.y, poisonColor, 28, 105, {
          size: 2.6,
          life: 1.2,
          kind: "wisp",
        });
        break;
      }
      case "poison_tick": {
        const poisonColor = event.color || "#86e08a";
        const radius = event.radius || 110;
        this.addRing(event.x, event.y, radius * 0.88, radius, poisonColor, 0.4, 1.2);
        this.burst(event.x, event.y, poisonColor, 10, 68, {
          size: 2,
          life: 0.55,
          kind: "wisp",
        });
        break;
      }
      case "cloud_fade": {
        this.addRing(event.x, event.y, event.radius || 110, 4, "#86e08a", 0.65, 1);
        break;
      }
      case "shield": {
        const player = client.players.get(event.id);
        if (player) {
          this.addRing(player.x, player.y, 14, 54, "#83c9ff", 0.72, 2.4);
          this.addRing(player.x, player.y, 4, 38, "#e0f5ff", 0.5, 1.2);
          this.burst(player.x, player.y, "#9fd4ff", 22, 110, {
            size: 2,
            life: 0.8,
            kind: "wisp",
          });
        }
        break;
      }
      case "heal": {
        this.addRing(event.x, event.y, 7, 58, "#71e0b4", 0.78, 2.6);
        this.addRing(event.x, event.y, 3, 36, "#d8fff0", 0.55, 1.2);
        this.burst(event.x, event.y - 16, "#9dffcf", 9, 44, { size: 3, life: 1.05, kind: "plus", rise: 60, drag: 2.4 });
        for (let index = 0; index < 24; index += 1) {
          const angle = Math.random() * TAU;
          const startX = event.x + Math.cos(angle) * (8 + Math.random() * 16);
          const startY = event.y + Math.sin(angle) * (8 + Math.random() * 16);
          this.particles.push({
            x: startX,
            y: startY,
            vx: Math.cos(angle) * 8,
            vy: -20 - Math.random() * 44,
            life: 0.8 + Math.random() * 0.4,
            maxLife: 1.1,
            size: 1.5 + Math.random() * 1.5,
            color: "#80e7bd",
            kind: "rune",
            drag: 0.8,
            glyph: Math.floor(Math.random() * 8),
            rotation: Math.random() * TAU,
            spin: 2,
          });
        }
        if (event.amount) {
          this.addFloater(event.x, event.y - 28, `+${Math.round(event.amount)}`, "#7ce0b6", 16);
        }
        break;
      }
      case "beam": {
        const beamColor = "#5fd8ff";
        this.effects.push({
          kind: "beam",
          x1: event.x,
          y1: event.y,
          x2: event.x2,
          y2: event.y2,
          width: event.width || 96,
          color: beamColor,
          life: 0.46,
          age: 0,
        });
        this.addExplosion(event.x2, event.y2, beamColor, "arcane", 1.45);
        this.burst(event.x2, event.y2, beamColor, 28, 280, {
          size: 3,
          life: 0.7,
          kind: "spark",
        });
        this.burst(event.x, event.y, "#ffffff", 18, 190, {
          size: 2.4,
          life: 0.45,
          kind: "spark",
          angle: Math.atan2(event.y2 - event.y, event.x2 - event.x),
          spread: 0.7,
        });
        this.shakeNear(client, event.x, event.y, 10);
        break;
      }
      case "nova": {
        const radius = event.radius || 150;
        this.addNova(event.x, event.y, radius, color, 0.8);
        this.addExplosion(event.x, event.y, color, "arcane", 1.28);
        const count = Math.min(52, 20 + Math.round(radius / 9));
        for (let index = 0; index < count; index += 1) {
          const angle = (index / count) * TAU + Math.random() * 0.2;
          this.particles.push({
            x: event.x + Math.cos(angle) * 12,
            y: event.y + Math.sin(angle) * 12,
            vx: Math.cos(angle) * (190 + Math.random() * 190),
            vy: Math.sin(angle) * (190 + Math.random() * 190),
            life: 0.6 + Math.random() * 0.5,
            maxLife: 1.1,
            size: 2.2 + Math.random() * 2.6,
            color,
            kind: index % 3 === 0 ? "spark" : "wisp",
            drag: 2.1,
            rotation: angle,
            spin: 1.5,
          });
        }
        this.shakeNear(client, event.x, event.y, 9);
        break;
      }
      case "emp": {
        const empColor = event.color || EMP_COLOR;
        const radius = event.radius || 190;
        this.addRing(event.x, event.y, 5, 40, empColor, 0.62, 2.2);
        this.addRing(event.x, event.y, radius, radius * 0.72, empColor, 0.82, 1.4);
        this.burst(event.x, event.y, empColor, 24, 130, {
          size: 2.2,
          life: 0.85,
          kind: "wisp",
        });
        break;
      }
      case "emp_pull": {
        const empColor = event.color || EMP_COLOR;
        const radius = event.radius || 190;
        this.addRing(event.x, event.y, radius, radius * 0.22, empColor, 0.58, 3);
        this.addRing(event.x, event.y, radius * 0.7, 8, "#f2eaff", 0.4, 1.3);
        for (let index = 0; index < 30; index += 1) {
          const angle = (index / 30) * TAU + Math.random() * 0.12;
          const distance = radius * (0.58 + Math.random() * 0.42);
          this.particles.push({
            x: event.x + Math.cos(angle) * distance,
            y: event.y + Math.sin(angle) * distance,
            vx: -Math.cos(angle) * (220 + Math.random() * 180),
            vy: -Math.sin(angle) * (220 + Math.random() * 180),
            life: 0.34 + Math.random() * 0.24,
            maxLife: 0.58,
            size: 1.5 + Math.random() * 2,
            color: index % 3 === 0 ? "#f0e8ff" : empColor,
            kind: index % 2 === 0 ? "wisp" : "spark",
            drag: 1.2,
            rotation: angle,
            spin: 1.4,
          });
        }
        this.burst(event.x, event.y, empColor, 18, 120, {
          size: 2.1,
          life: 0.62,
          kind: "wisp",
        });
        this.shakeNear(client, event.x, event.y, Number(event.hits) > 0 ? 3.8 : 2);
        break;
      }
      case "emp_blast": {
        const empColor = event.color || EMP_COLOR;
        const radius = event.radius || 190;
        this.addRing(event.x, event.y, radius, 5, empColor, 0.58, 3.4);
        this.addRing(event.x, event.y, radius * 0.78, 2, "#efe6ff", 0.42, 1.4);
        this.addNova(event.x, event.y, radius, empColor, 0.82);
        this.addExplosion(event.x, event.y, empColor, "emp", 1.36);
        for (let index = 0; index < 26; index += 1) {
          const angle = (index / 26) * TAU + Math.random() * 0.16;
          const distance = radius * (0.52 + Math.random() * 0.46);
          this.particles.push({
            x: event.x + Math.cos(angle) * distance,
            y: event.y + Math.sin(angle) * distance,
            vx: -Math.cos(angle) * (170 + Math.random() * 130),
            vy: -Math.sin(angle) * (170 + Math.random() * 130),
            life: 0.4 + Math.random() * 0.34,
            maxLife: 0.74,
            size: 1.8 + Math.random() * 2.1,
            color: index % 3 === 0 ? "#efe6ff" : empColor,
            kind: index % 2 === 0 ? "spark" : "wisp",
            drag: 1.4,
            rotation: angle,
            spin: 1.3,
          });
        }
        if (Number(event.drained) > 0) {
          this.addFloater(
            event.x,
            event.y - 30,
            `−${Math.round(Number(event.drained))} маны`,
            "#d8c6ff",
            12,
          );
        }
        this.shakeNear(client, event.x, event.y, 8);
        break;
      }
      case "ward": {
        this.addRing(event.x, event.y, 4, 44, color, 0.62, 2.4);
        this.addRing(event.x, event.y, 38, 8, VIOLET, 0.78, 1.2);
        this.burst(event.x, event.y, VIOLET, 26, 125, {
          size: 2.2,
          life: 0.9,
          kind: "rune",
        });
        break;
      }
      case "ward_blast": {
        const blastColor = event.color || VIOLET;
        this.addNova(event.x, event.y, event.radius || 118, blastColor, 0.72);
        this.addExplosion(event.x, event.y, blastColor, "arcane", 1.32);
        for (let index = 0; index < 20; index += 1) {
          const angle = (index / 20) * TAU;
          this.burst(
            event.x + Math.cos(angle) * 20,
            event.y + Math.sin(angle) * 20,
            blastColor,
            3,
            190,
            { size: 2.6, life: 0.66, kind: "shard", angle, spread: 0.45 },
          );
        }
        this.shakeNear(client, event.x, event.y, 7);
        break;
      }
      case "ward_fade": {
        this.addRing(event.x, event.y, 24, 2, VIOLET, 0.55, 1.2);
        this.burst(event.x, event.y, VIOLET, 5, 40, {
          size: 1.2,
          life: 0.5,
          kind: "wisp",
        });
        break;
      }
      case "say": {
        this.addSpeech(event.id, event.text);
        break;
      }
      case "monster_spawn": {
        this.addRing(event.x, event.y, 30, 4, color, 0.5, 2.4);
        this.burst(event.x, event.y, color, 12, 90, { size: 2, life: 0.5, kind: "wisp" });
        break;
      }
      case "monster_death": {
        const big = Boolean(event.boss);
        const body = this.visualMonsters.get(event.id)?.data;
        if (body && this.quality >= QUALITY_LIGHTS) {
          const colors = spriteColors(body.kind);
          const radius = Number(body.r) || 18;
          const pieces = big ? 46 : 16;
          for (let piece = 0; piece < pieces; piece += 1) {
            this.burst(event.x, event.y - radius * 0.7, colors[piece % colors.length], 1, big ? 420 : 240, {
              kind: "chunk",
              size: big ? 7 : 5,
              life: big ? 1.5 : 0.95,
              drag: 1.1,
              gravity: 640,
              ground: event.y + radius * 0.6 + (Math.random() - 0.5) * radius,
            });
          }
        }
        this.addExplosion(event.x, event.y, color, "arcane", big ? 2.2 : 0.9);
        this.burst(event.x, event.y, color, big ? 70 : 24, big ? 340 : 190, {
          size: big ? 3.4 : 2.4,
          life: big ? 1.1 : 0.6,
          kind: "shard",
        });
        this.shakeNear(client, event.x, event.y, big ? 14 : 2.4);
        break;
      }
      case "string_closed": {
        // The closing quote goes off along the whole length of the string.
        for (const [x, y] of event.cells || []) {
          this.addExplosion(x, y, "#ce9178", "arcane", 0.42);
        }
        this.shakeNear(client, event.cells?.[0]?.[0] ?? 0, event.cells?.[0]?.[1] ?? 0, 8);
        break;
      }
      case "hazard_blast": {
        if (event.x2 === null || event.x2 === undefined) {
          this.addNova(event.x, event.y, event.radius, color, 0.5);
          this.burst(event.x, event.y, color, 26, 240, { size: 2.6, life: 0.55, kind: "ember" });
        } else {
          this.effects.push({
            kind: "beam",
            x1: event.x,
            y1: event.y,
            x2: event.x2,
            y2: event.y2,
            width: event.radius,
            color,
            life: 0.32,
            age: 0,
            flat: true,
          });
        }
        this.shakeNear(client, event.x, event.y, 4);
        break;
      }
      case "pickup": {
        const heal = event.kind === "hp";
        this.addFloater(event.x, event.y - 16, heal ? "+HP" : "+мана", heal ? "#ff9aa0" : "#9fc0ff", 13);
        this.burst(event.x, event.y, heal ? "#ff6b7a" : "#6fa8ff", 8, 90, {
          size: 1.8,
          life: 0.4,
          kind: "spark",
        });
        break;
      }
      case "crit": {
        this.addFloater(event.x, event.y - 34, "крит!", "#ffe17a", 16);
        this.burst(event.x, event.y, "#ffe17a", 12, 180, { size: 2, life: 0.35, kind: "spark" });
        break;
      }
      case "ping": {
        this.addRing(event.x, event.y, 20, event.radius, "#7fe0ee", 0.7, 2.6);
        this.addFloater(event.x, event.y - 30, `ping: ${event.count}`, "#9feeff", 18);
        for (const [x, y] of event.cracks || []) {
          this.addRing(x, y, 10, 90, "#ffd27a", 0.9, 3);
          this.addFloater(x, y - 34, "трещина!", "#ffd27a", 16);
        }
        break;
      }
      case "gc": {
        this.addRing(event.x, event.y, 160, 12, "#9fe8c8", 0.5, 2.4);
        if (event.count) this.addFloater(event.x, event.y - 46, `free: ${event.count}`, "#9fe8c8", 15);
        break;
      }
      case "grep": {
        for (const [x, y] of event.hits || []) {
          this.addRing(x, y, 6, 40, "#ffe07a", 0.35, 2);
          this.burst(x, y, "#ffe07a", 8, 120, { size: 2, life: 0.4, kind: "spark" });
        }
        break;
      }
      case "caught": {
        this.addRing(event.x, event.y, 20, 80, "#c7a6e8", 0.6, 3);
        this.addFloater(event.x, event.y - 50, "except: выжил", "#c7a6e8", 18);
        break;
      }
      case "resist": {
        this.addFloater(event.x, event.y - 18, event.text, "#d6dcea", 13);
        this.addRing(event.x, event.y, 4, 22, "#d6e6ff", 0.25, 1.6);
        break;
      }
      case "pull": {
        this.addRing(event.x, event.y, 40, 6, VIOLET, 0.5, 2.2);
        this.burst(event.x, event.y, VIOLET, 18, 120, { size: 2, life: 0.5, kind: "wisp" });
        break;
      }
      case "room_lock":
      case "room_clear": {
        this.shake(kind === "room_lock" ? 5 : 3);
        break;
      }
      case "fix_done": {
        this.addNova(event.x, event.y, 340, "#4fe08a", 0.9);
        this.addRing(event.x, event.y, 20, 240, "#ffffff", 0.7, 3);
        this.burst(event.x, event.y, "#4fe08a", 60, 320, { size: 2.6, life: 0.9, kind: "spark" });
        this.addFloater(event.x, event.y - 70, "ПАТЧ ПРИМЕНЁН", "#7fffb0", 18);
        this.shake(8);
        break;
      }
      case "deflect": {
        this.addRing(event.x, event.y, 6, 34, event.color, 0.28, 2.4);
        this.burst(event.x, event.y, event.color, 12, 200, { size: 2, life: 0.3, kind: "spark" });
        break;
      }
      case "sudo": {
        this.addRing(event.x, event.y, 30, 300, "#ffd93d", 0.6, 4);
        this.addFloater(event.x, event.y - 72, "SUDO", "#ffe17a", 18);
        this.shake(5);
        break;
      }
      case "mark": {
        if (typeof event.from_x === "number") {
          this.addLine(event.from_x, event.from_y, event.x, event.y, "#ff4f6a", 0.35, 3);
        }
        this.addRing(event.x, event.y, 50, 14, "#ff4f6a", 0.35, 2.4);
        break;
      }
      case "segfault": {
        this.addNova(event.x, event.y, 170, "#ff4f6a", 0.55);
        this.burst(event.x, event.y, "#ff8fa0", 34, 300, { size: 2.6, life: 0.5, kind: "spark" });
        this.addFloater(event.x, event.y - 40, "SEGFAULT", "#ff8fa0", 16);
        this.shake(6);
        break;
      }
      case "hijack": {
        this.addRing(event.x, event.y, 70, 16, "#7fffb0", 0.45, 3);
        this.burst(event.x, event.y, "#7fffb0", 24, 170, { size: 2, life: 0.6, kind: "spark" });
        this.addFloater(event.x, event.y - 48, "ВЗЛОМ", "#7fffb0", 16);
        break;
      }
      case "patch": {
        this.addLine(event.from_x, event.from_y, event.x, event.y, "#6fd6ff", 0.32, 4);
        this.addRing(event.x, event.y, 8, 46, "#6fd6ff", 0.4, 2.4);
        this.addFloater(event.x, event.y - 44, `+${Math.round(event.amount)}`, "#9fe6ff", 15);
        break;
      }
      case "quest_item":
      case "quest_catch":
      case "plate_on": {
        this.addRing(event.x, event.y, 6, 60, "#7fe0ee", 0.6, 3);
        this.burst(event.x, event.y, "#7fe0ee", 16, 140, { size: 2.2, life: 0.6, kind: "spark" });
        if (event.label) this.addFloater(event.x, event.y - 30, event.label, "#d6f6fb", 13);
        break;
      }
      case "prop_break": {
        this.burst(event.x, event.y, "#c8c4b4", 18, 170, { size: 2.6, life: 0.6, kind: "shard" });
        break;
      }
      case "prop_blast": {
        this.addExplosion(event.x, event.y, "#ffd93d", "arcane", (event.radius || 150) / 110);
        this.burst(event.x, event.y, "#ffb347", 40, 320, { size: 3, life: 0.8, kind: "shard" });
        this.shakeNear(client, event.x, event.y, 9);
        break;
      }
      case "surface_ice": {
        this.addRing(event.x, event.y, 20, 100, "#d6f0ff", 0.6, 3);
        this.addFloater(event.x, event.y - 40, "лёд", "#d6f0ff", 14);
        break;
      }
      case "surface_shock": {
        this.addRing(event.x, event.y, 20, 120, "#fff6b0", 0.5, 4);
        this.addFloater(event.x, event.y - 40, "разряд!", "#fff6b0", 16);
        this.shakeNear(client, event.x, event.y, 5);
        break;
      }
      case "surface_burn": {
        this.addFloater(event.x, event.y - 30, "кабель горит", "#ffb347", 14);
        break;
      }
      case "link_jump": {
        this.addLine(event.from_x, event.from_y, event.x, event.y, "#6fb6ff", 0.5, 4);
        this.addRing(event.x, event.y, 50, 8, "#6fb6ff", 0.45, 3);
        break;
      }
      case "workshop_open": {
        this.addRing(event.x, event.y, 20, 200, "#7fe0ee", 0.8, 4);
        this.addFloater(event.x, event.y - 40, "ЗАМОК ОТКРЫТ", "#bfffd8", 18);
        break;
      }
      case "finds_offered": {
        this.addRing(event.x, event.y, 10, 170, "#7fe0ee", 0.8, 3);
        break;
      }
      case "quest_note": {
        this.addFloater(event.x, event.y - 34, event.text, event.good ? "#bfffd8" : "#ffb0aa", 15);
        break;
      }
      case "ns_forged": {
        this.addExplosion(event.x, event.y, "#ff5a4f", "arcane", 0.9);
        this.addFloater(event.x, event.y - 60, "6.6.6.6", "#ff8f8f", 18);
        this.shakeNear(client, event.x, event.y, 4);
        break;
      }
      case "memory_oom": {
        this.shake(16);
        break;
      }
      case "memory_free": {
        this.shake(6);
        break;
      }
      case "npc_gone": {
        this.addRing(event.x, event.y, 8, 90, "#7fe0ee", 0.7, 3);
        this.burst(event.x, event.y, "#7fe0ee", 24, 200, { size: 2.2, life: 0.7, kind: "spark" });
        break;
      }
      case "quest_burst": {
        this.addExplosion(event.x, event.y, "#ff5a4f", "arcane", 1.2);
        this.burst(event.x, event.y, "#ff5a4f", 30, 220, { size: 2.6, life: 0.7, kind: "shard" });
        this.addFloater(event.x, event.y - 34, event.label ? `${event.label}: вирус!` : "вирус!", "#ffb0aa", 14);
        this.shakeNear(client, event.x, event.y, 6);
        break;
      }
      case "plate_fail": {
        this.addRing(event.x, event.y, 4, 80, "#ffe17a", 0.8, 4);
        this.addFloater(event.x, event.y - 34, "не тот порядок", "#ffe17a", 14);
        this.shakeNear(client, event.x, event.y, 4);
        break;
      }
      case "zone_on": {
        this.addRing(event.x, event.y, 74, 20, "#4fe08a", 0.7, 3);
        if (event.label) this.addFloater(event.x, event.y - 90, `${event.label}: OK`, "#bfffd8", 14);
        break;
      }
      case "loot":
      case "rest": {
        this.burst(event.x, event.y, "#ffd27a", 30, 160, { size: 2.4, life: 0.9, kind: "rune" });
        this.addRing(event.x, event.y, 10, 90, "#ffd27a", 0.7, 3);
        if (event.amount) this.addFloater(event.x, event.y - 40, `+${event.amount} токенов`, "#ffe9a8", 16);
        break;
      }
      case "unit_down": {
        this.addExplosion(event.x, event.y, "#ff5a4f", "arcane", 1);
        this.addFloater(event.x, event.y - 90, "СБОЙ", "#ff8f8f", 18);
        this.shakeNear(client, event.x, event.y, 6);
        break;
      }
      case "unit_up":
      case "npc_found": {
        this.addRing(event.x, event.y, 8, 70, "#9ff0c0", 0.7, 3);
        break;
      }
      case "deal": {
        this.addRing(event.x, event.y, 10, 140, "#ff4f6a", 0.9, 4);
        this.burst(event.x, event.y, "#ff4f6a", 40, 220, { size: 2.6, life: 1, kind: "shard" });
        break;
      }
      case "rollback": {
        this.addLine(event.from_x, event.from_y, event.x, event.y, "#a6e4ff", 0.6, 6);
        this.addRing(event.x, event.y, 90, 10, "#a6e4ff", 0.55, 3);
        this.addFloater(event.x, event.y - 56, "ОТКАТ", "#d6f0ff", 17);
        this.shake(4);
        break;
      }
      case "scan": {
        this.addRing(event.x, event.y, 10, 70, "#e08cff", 0.5, 2);
        this.addRing(event.x, event.y, 10, 44, "#e08cff", 0.36, 2);
        this.addFloater(event.x, event.y - 48, "СКАН", "#e8c6ff", 14);
        break;
      }
      case "breakpoint": {
        this.addRing(event.x, event.y, event.radius * 1.5, event.radius, "#d6f0ff", 0.4, 4);
        this.shake(3);
        break;
      }
      case "gate_open": {
        this.addRing(event.x, event.y, 200, 20, "#ff4f6a", 0.8, 3);
        this.shake(8);
        break;
      }
      case "gate_lift": {
        this.addNova(event.x, event.y, 280, "#ffffff", 0.8);
        this.addFloater(event.x, event.y - 80, "ЗАЩИТА СНЯТА", "#ffe17a", 18);
        this.shake(10);
        break;
      }
      case "boss_cast": {
        this.addRing(event.x, event.y, 30, 150, color, 0.45, 3);
        this.shake(3);
        break;
      }
      case "curse": {
        this.addRing(event.x, event.y, 60, 12, "#ff6a7a", 0.4, 3);
        this.addFloater(event.x, event.y - 54, CURSE_LABELS[event.kind] || "", "#ff9aa0", 15);
        break;
      }
      case "recall": {
        this.addLine(event.from_x, event.from_y, event.x, event.y, "#a78bff", 0.5, 5);
        this.addRing(event.x, event.y, 70, 12, "#a78bff", 0.45, 3);
        this.addFloater(event.x, event.y - 54, "continue", "#d6c6ff", 16);
        this.shake(4);
        break;
      }
      case "swap_warn": {
        this.addLine(event.x1, event.y1, event.x2, event.y2, "#ffd27a", 1.1, 2);
        this.addRing(event.x1, event.y1, 60, 24, "#ffd27a", 1.1, 2);
        this.addRing(event.x2, event.y2, 60, 24, "#ffd27a", 1.1, 2);
        break;
      }
      case "swap": {
        this.addLine(event.x1, event.y1, event.x2, event.y2, "#ffffff", 0.3, 6);
        this.addRing(event.x1, event.y1, 10, 90, "#ffd27a", 0.4, 3);
        this.addRing(event.x2, event.y2, 10, 90, "#ffd27a", 0.4, 3);
        this.shake(6);
        break;
      }
      case "deploy_blast": {
        this.addNova(event.x, event.y, 900, "#ff4f6a", 1);
        this.addFloater(event.x, event.y - 90, "ВЫКАТИЛ В ПРОД", "#ff9aa0", 20);
        this.shake(16);
        break;
      }
      case "deploy_broken": {
        this.addNova(event.x, event.y, 280, "#4fe08a", 0.7);
        this.addFloater(event.x, event.y - 90, "СБОРКА УПАЛА", "#9ff0c0", 20);
        this.shake(8);
        break;
      }
      case "boss_dizzy": {
        this.addRing(event.x, event.y - 30, 10, 60, "#ffe17a", 0.6, 2.4);
        this.addFloater(event.x, event.y - 70, "уязвим!", "#ffe17a", 16);
        break;
      }
      default:
        break;
    }
  }

  // ----------------------------------------------------------------- drawing
  draw(client, now = performance.now()) {
    if (!this.ctx) return;
    const rawDt = (now - this.lastFrame) / 1000;
    const dt = clamp(rawDt, 0.001, 0.05);
    this.lastFrame = now;
    this.frame += 1;
    this.trackPerformance(rawDt, now);
    this.resize();

    this.updateCamera(client, dt);
    this.updateVisuals(client, dt);
    this.updateEffects(dt);

    const worldCtx = this.worldCtx;
    const pixelScale = this.pixelScale;
    worldCtx.setTransform(1, 0, 0, 1, 0, 0);
    worldCtx.imageSmoothingEnabled = false;

    this.drawScreenBackdrop(
      worldCtx,
      this.worldCanvas.width,
      this.worldCanvas.height,
    );
    this.ensureFloor(client.config);
    this.ensureFog(client);

    this.shakeAmount *= Math.exp(-dt * 6.5);
    if (this.shakeAmount < 0.04) this.shakeAmount = 0;
    const shakeX = (Math.random() - 0.5) * this.shakeAmount;
    const shakeY = (Math.random() - 0.5) * this.shakeAmount;

    const { zoom, x: camX, y: camY } = this.camera;
    const labels = [];
    const worldWidth = this.worldCanvas.width;
    const worldHeight = this.worldCanvas.height;
    const applyCamera = (target) => {
      target.setTransform(1, 0, 0, 1, 0, 0);
      target.translate(
        worldWidth / 2 + shakeX * pixelScale,
        worldHeight / 2 + shakeY * pixelScale,
      );
      target.scale(zoom * pixelScale, zoom * pixelScale);
      target.translate(-camX, -camY);
    };

    // What light falls on: the room and everyone standing in it.
    const dungeon = client.config?.mode === "story";
    applyCamera(worldCtx);
    if (this.floorCanvas) {
      worldCtx.drawImage(
        this.floorCanvas,
        0,
        0,
        client.config.arena.w,
        client.config.arena.h,
      );
    }
    if (dungeon) {
      if (this.quality >= QUALITY_LIGHTS) {
        const halfW = worldWidth / (2 * zoom * pixelScale);
        const halfH = worldHeight / (2 * zoom * pixelScale);
        drawFloorLife(worldCtx, this.floorCanvas?.life, (client.config.tile || 48) / BAKE_TILE, {
          left: camX - halfW,
          right: camX + halfW,
          top: camY - halfH,
          bottom: camY + halfH,
        }, now);
      }
      drawDoors(worldCtx, client.story?.doors, client.config, now);
      drawTerrainFloor(worldCtx, client.config.terrain, client.terrainState, client.workshop, client.config.tile || 48, now);
      drawQuestFloor(worldCtx, client.quest, client.config, now);
      drawPortal(worldCtx, client.story, client.config, now);
      drawPickups(worldCtx, client.pickups, now);
      this.drawEffects(worldCtx, now, zoom, true);
      drawLamps(worldCtx, client.config, now);
      drawTerminals(worldCtx, client.terminals, now);
      drawCables(worldCtx, client.players, client.terminals, now);
      drawBreakpoints(worldCtx, client.breakpoints, now);
      drawBarriers(worldCtx, client.barriers, now);
      for (const visual of this.visualPlayers.values()) {
        if (visual.data.sudo) drawSudo(worldCtx, visual.x, visual.y, now);
      }
      drawProps(worldCtx, client.config.terrain, client.terrainState, now);
      drawQuestObjects(worldCtx, client.quest, this.visualPlayersById(), now);
    } else {
      drawAmbient(worldCtx, client.config, now, zoom);
      this.drawEffects(worldCtx, now, zoom, true);
      drawArenaBorder(worldCtx, client.config, now, zoom);
      drawWallTorches(worldCtx, client.config, now);
    }
    this.drawScene(worldCtx, client, now, zoom, labels);
    const eventKind = client.life?.event?.kind;
    const darkHere = dungeon && (eventKind === "blackout" || this.darkInView(client));
    if (this.quality >= QUALITY_LIGHTS || darkHere) {
      this.applyLighting(client, now, applyCamera, this.quality < QUALITY_LIGHTS);
    }

    // What gives light off: magic stays at full brightness on top of the room.
    applyCamera(worldCtx);
    if (dungeon) drawBossMoves(worldCtx, client.bossMoves, this.visualMonsters, now);
    drawHazards(worldCtx, client.hazards, now);
    this.drawWards(worldCtx, client, now, zoom);
    this.drawEmps(worldCtx, client, now, zoom);
    this.drawClouds(worldCtx, client, now, zoom);
    this.drawMeteors(worldCtx, client, now, zoom);
    this.drawEffects(worldCtx, now, zoom, false);
    this.drawProjectiles(worldCtx, now, zoom);
    this.drawParticles(worldCtx, now, zoom);
    if (dungeon) {
      worldCtx.setTransform(pixelScale, 0, 0, pixelScale, 0, 0);
      drawWeather(worldCtx, client.config, this.width, this.height, now, this.camera);
      applyCamera(worldCtx);
      drawFog(
        worldCtx,
        this.fog,
        client.config,
        {
          x: worldWidth / 2 + (shakeX - camX * zoom) * pixelScale,
          y: worldHeight / 2 + (shakeY - camY * zoom) * pixelScale,
          scale: zoom * pixelScale,
          rain: this.quality >= QUALITY_LIGHTS && !this.calmMotion,
        },
        now,
      );
    }
    worldCtx.setTransform(1, 0, 0, 1, 0, 0);
    if (this.quality >= QUALITY_FULL) this.drawBloom(worldCtx);

    const ctx = this.ctx;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(this.worldCanvas, 0, 0, this.width, this.height);
    ctx.imageSmoothingEnabled = true;

    if (dungeon) {
      this.drawMonsterBars(ctx, client);
      drawUnitBars(ctx, client.quest, (x, y) => this.worldToScreen(x, y), this.camera.zoom);
      this.queueMonsterLabels(ctx);
      flushLabels(
        ctx,
        (x, y) => this.worldToScreen(x, y),
        this.camera.zoom,
        (x, y) => this.seen(x, y) && !this.inDark(x, y, client),
      );
      this.drawHazardLabels(ctx, client.hazards);
      drawGust(ctx, client.terrainState?.gust, this.width, this.height, now);
      if (eventKind === "storm") drawSpamStorm(ctx, this.width, this.height, now);
    }
    this.drawNameplates(ctx, labels, client, now);
    this.drawFloaties(ctx);
    this.drawOffscreenTargets(ctx, client);
    if (dungeon) this.drawTerminalMarkers(ctx, client, now);
    if (dungeon) this.drawQuestMarks(ctx, client, now);
    this.drawAim(ctx, client, now);

    this.drawFrameVignette(ctx);
    if (dungeon) this.drawMinimap(ctx, client);
  }

  /** A pointer to broken terminals, on screen or off: they are where the story goes. */
  drawTerminalMarkers(ctx, client, now) {
    for (const terminal of client.terminals || []) {
      if (terminal.solved || !this.seen(terminal.x, terminal.y)) continue;
      const screen = this.worldToScreen(terminal.x, terminal.y);
      const inside =
        screen.x > 0 && screen.x < this.width && screen.y > 0 && screen.y < this.height;
      const bob = Math.sin(now / 180) * 5;
      ctx.save();
      if (inside) {
        ctx.translate(screen.x, screen.y - 76 * this.camera.zoom - 16 + bob);
        ctx.rotate(Math.PI / 2);
      } else {
        const dx = screen.x - this.width / 2;
        const dy = screen.y - this.height / 2;
        const scale = Math.min(
          (this.width / 2 - 34) / Math.max(1, Math.abs(dx)),
          (this.height / 2 - 34) / Math.max(1, Math.abs(dy)),
        );
        ctx.translate(this.width / 2 + dx * scale, this.height / 2 + dy * scale);
        ctx.rotate(Math.atan2(dy, dx));
      }
      ctx.fillStyle = terminal.role === "gate" ? "#ff4f6a" : "#ffd93d";
      ctx.strokeStyle = "#0a0810";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(12, 0);
      ctx.lineTo(-8, -10);
      ctx.lineTo(-3, 0);
      ctx.lineTo(-8, 10);
      ctx.closePath();
      ctx.stroke();
      ctx.fill();
      ctx.restore();
    }
  }

  /** PGT signs his lies: the words go on the screen layer so they stay readable. */
  drawHazardLabels(ctx, hazards) {
    ctx.save();
    ctx.font = "bold 14px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const hazard of hazards || []) {
      if (!hazard.label) continue;
      const screen = this.worldToScreen(hazard.x, hazard.y);
      ctx.fillStyle = "rgba(6, 7, 13, 0.75)";
      ctx.fillRect(screen.x - 42, screen.y - 11, 84, 22);
      ctx.fillStyle = hazard.color;
      ctx.fillText(hazard.label, screen.x, screen.y);
    }
    ctx.restore();
  }

  /** Where the quest wants the party: a cyan diamond, or an arrow at the edge. */
  drawQuestMarks(ctx, client, now) {
    const marks = client.quest?.marks || [];
    const self = client.players.get(client.selfId);
    for (const [x, y] of marks) {
      // Right next to it, the thing itself is the marker.
      if (self && Math.hypot(self.x - x, self.y - y) < 240) continue;
      const screen = this.worldToScreen(x, y);
      const inside =
        screen.x > 0 && screen.x < this.width && screen.y > 0 && screen.y < this.height;
      const bob = Math.sin(now / 200) * 4;
      ctx.save();
      ctx.fillStyle = "#7fe0ee";
      ctx.strokeStyle = "#06121a";
      ctx.lineWidth = 2;
      if (inside) {
        ctx.translate(screen.x, screen.y - 58 * this.camera.zoom - 14 + bob);
        ctx.beginPath();
        ctx.moveTo(0, -9);
        ctx.lineTo(8, 0);
        ctx.lineTo(0, 9);
        ctx.lineTo(-8, 0);
        ctx.closePath();
      } else {
        const dx = screen.x - this.width / 2;
        const dy = screen.y - this.height / 2;
        const scale = Math.min(
          (this.width / 2 - 34) / Math.max(1, Math.abs(dx)),
          (this.height / 2 - 34) / Math.max(1, Math.abs(dy)),
        );
        ctx.translate(this.width / 2 + dx * scale, this.height / 2 + dy * scale);
        ctx.rotate(Math.atan2(dy, dx));
        ctx.beginPath();
        ctx.moveTo(11, 0);
        ctx.lineTo(-6, -8);
        ctx.lineTo(-2, 0);
        ctx.lineTo(-6, 8);
        ctx.closePath();
      }
      ctx.stroke();
      ctx.fill();
      ctx.restore();
    }
  }

  visualPlayersById() {
    const players = new Map();
    for (const visual of this.visualPlayers.values()) {
      players.set(visual.data.id, { x: visual.x, y: visual.y });
    }
    return players;
  }

  /** A letter's text, a rack's temperature, the name of a failing test. */
  queueMonsterLabels(ctx) {
    for (const visual of this.visualMonsters.values()) {
      const { text, r, kind } = visual.data;
      if (!text || visual.data.arriving) continue;
      let color = "#f4f2fa";
      if (visual.data.elite) {
        color = ELITE_COLORS[visual.data.elite] || color;
      } else if (kind === "hotrack") {
        const degrees = Number.parseInt(text, 10);
        color = degrees >= 85 ? "#ff6a5a" : degrees >= 65 ? "#ffb347" : "#7fe0ee";
      } else if (kind === "failtest") {
        color = "#ff8f8f";
      }
      questLabel(ctx, text, visual.x, visual.y - (Number(r) || 18) * 2.2 - 8, color, kind === "letter" ? 20 : 18);
    }
  }

  drawMonsterBars(ctx, client) {
    for (const visual of this.visualMonsters.values()) {
      const { hp, max_hp: maxHp, r } = visual.data;
      if (!(hp < maxHp) || visual.data.arriving || r > 40) continue;
      if (!this.seen(visual.x, visual.y) || this.inDark(visual.x, visual.y, client)) continue;
      const screen = this.worldToScreen(visual.x, visual.y);
      const lift = (Number(r) || 18) * this.camera.zoom * 2.4 + 8;
      drawMonsterBar(ctx, screen.x, screen.y - lift, 34, clamp(hp / maxHp, 0, 1));
    }
  }

  drawMinimap(ctx, client) {
    const map = this.minimap;
    if (!map) return;
    const scale = Math.min(MINIMAP_WIDTH / map.width, MINIMAP_HEIGHT / map.height);
    const width = map.width * scale;
    const height = map.height * scale;
    const left = this.width - width - 14;
    const top = 76;
    const tile = client.config.tile || 48;
    // During a DNS failure the map still looks fine. It is simply a mirror.
    const lying = client.life?.event?.kind === "dns";
    const at = (x, y) => [
      lying ? left + width - (x / tile) * scale : left + (x / tile) * scale,
      top + (y / tile) * scale,
    ];
    ctx.save();
    ctx.fillStyle = "rgba(6, 7, 13, 0.62)";
    ctx.fillRect(left - 6, top - 6, width + 12, height + 12);
    ctx.imageSmoothingEnabled = false;
    if (lying) {
      ctx.save();
      ctx.translate(left + width, top);
      ctx.scale(-1, 1);
      ctx.drawImage(map, 0, 0, width, height);
      ctx.restore();
    } else {
      ctx.drawImage(map, left, top, width, height);
    }
    ctx.imageSmoothingEnabled = true;
    if (client.story?.portal && this.seen(client.story.portal[0], client.story.portal[1])) {
      const [x, y] = at(client.story.portal[0], client.story.portal[1]);
      ctx.fillStyle = client.story.portal_ready ? "#f4d99b" : "rgba(244, 217, 155, 0.35)";
      ctx.fillRect(x - 2, y - 2, 5, 5);
    }
    for (const terminal of client.terminals || []) {
      if (terminal.solved || !this.seen(terminal.x, terminal.y)) continue;
      const [x, y] = at(terminal.x, terminal.y);
      ctx.fillStyle = "#4fe08a";
      ctx.fillRect(x - 2, y - 2, 5, 5);
    }
    for (const [markX, markY] of client.quest?.marks || []) {
      const [x, y] = at(markX, markY);
      ctx.fillStyle = "#7fe0ee";
      ctx.fillRect(x - 2, y - 2, 5, 5);
    }
    for (const monster of client.monsters || []) {
      if (!this.seen(monster.x, monster.y) || this.inDark(monster.x, monster.y, client)) continue;
      const [x, y] = at(monster.x, monster.y);
      ctx.fillStyle = "#e76972";
      ctx.fillRect(x - 1, y - 1, 2, 2);
    }
    for (const player of client.players.values()) {
      const [x, y] = at(player.x, player.y);
      ctx.fillStyle = player.id === client.selfId ? "#ffffff" : player.color || VIOLET;
      ctx.fillRect(x - 1.5, y - 1.5, 4, 4);
    }
    ctx.restore();
  }

  /** Step the effects down, once and for good, if frames stay slow. */
  trackPerformance(rawDt, now) {
    if (this.qualityPinned || this.quality <= 0 || rawDt > 0.1) return;
    this.frameAverage += (rawDt - this.frameAverage) * 0.03;
    if (this.frameAverage > SLOW_FRAME && now - this.qualityCheckedAt > 3000) {
      this.quality -= 1;
      this.qualityCheckedAt = now;
      this.frameAverage = 1 / 60;
    }
  }

  // ---------------------------------------------------------------- lighting
  lightSprite(color) {
    let sprite = this.lightSprites.get(color);
    if (!sprite) {
      const size = LIGHT_SPRITE_SIZE;
      sprite = document.createElement("canvas");
      sprite.width = size;
      sprite.height = size;
      const ctx = sprite.getContext("2d");
      const middle = size / 2;
      const glow = ctx.createRadialGradient(middle, middle, 0, middle, middle, middle);
      glow.addColorStop(0, rgba(color, 1));
      glow.addColorStop(0.32, rgba(color, 0.62));
      glow.addColorStop(0.68, rgba(color, 0.2));
      glow.addColorStop(1, rgba(color, 0));
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, size, size);
      this.lightSprites.set(color, sprite);
    }
    return sprite;
  }

  collectLights(client, now) {
    const lights = this.lights;
    lights.length = 0;
    if (client.config?.mode === "story") {
      const zoom = this.camera.zoom;
      collectDungeonLights(client.config, now, lights, {
        x: this.camera.x,
        y: this.camera.y,
        reachX: this.width / zoom,
        reachY: this.height / zoom,
      });
      if (client.story?.portal_ready) {
        const [x, y] = client.story.portal;
        lights.push({ x, y, radius: 380, color: themeOf(client.config).accent, power: 1 });
      }
      for (const visual of this.visualMonsters.values()) {
        if (visual.data.r > 30) {
          lights.push({ x: visual.x, y: visual.y, radius: 260, color: "#ffffff", power: 0.5 });
        }
      }
      for (const terminal of client.terminals || []) {
        lights.push({
          x: terminal.x,
          y: terminal.y,
          radius: 230,
          color: terminal.solved ? "#4fe08a" : "#ff6a7a",
          power: 0.9,
        });
      }
      questLights(client.quest, lights);
      terrainLights(client.config.terrain, client.terrainState, lights);
    } else {
      collectWorldLights(client.config, now, lights);
    }

    for (const visual of this.visualPlayers.values()) {
      const color = visual.data.color || VIOLET;
      if (visual.dead) {
        lights.push({ x: visual.x, y: visual.y, radius: 90, color, power: 0.5 });
      } else if (visual.data.id === client.selfId) {
        lights.push({ x: visual.x, y: visual.y, radius: 360, color: SELF_LIGHT, power: 1 });
      } else {
        lights.push({ x: visual.x, y: visual.y, radius: 210, color, power: 0.85 });
      }
    }
    for (const visual of this.visualProjectiles.values()) {
      const { kind, color } = visual.data;
      const radius = kind === "fire" ? 260 : kind === "frost" ? 190 : kind === "orb" ? 110 : 130;
      lights.push({ x: visual.x, y: visual.y, radius, color: color || GOLD, power: 1 });
    }
    for (const ward of client.wards) {
      lights.push({
        x: ward.x,
        y: ward.y,
        radius: ward.armed ? 120 : 70,
        color: VIOLET,
        power: 0.7,
      });
    }
    for (const emp of client.emps || []) {
      lights.push({
        x: emp.x,
        y: emp.y,
        radius: (Number(emp.radius) || 190) * 1.3,
        color: emp.color || EMP_COLOR,
        power: 0.85,
      });
    }
    for (const cloud of client.clouds || []) {
      lights.push({
        x: cloud.x,
        y: cloud.y,
        radius: (Number(cloud.radius) || 110) * 1.5,
        color: cloud.color || "#86e08a",
        power: 0.6,
      });
    }
    for (const meteor of client.meteors || []) {
      const delay = Math.max(0.1, Number(meteor.delay) || 1.15);
      const nearing = clamp(1 - (Number(meteor.ttl) || 0) / delay, 0, 1);
      lights.push({
        x: meteor.x,
        y: meteor.y,
        radius: (Number(meteor.radius) || 120) * (0.9 + nearing),
        color: meteor.color || "#ff7b45",
        power: 0.35 + nearing * 0.55,
      });
    }
    for (const effect of this.effects) {
      const fade = 1 - clamp(effect.age / effect.life, 0, 1);
      if (effect.kind === "explosion") {
        lights.push({
          x: effect.x,
          y: effect.y,
          radius: 300 * (effect.scale || 1),
          color: effect.color,
          power: fade,
        });
      } else if (effect.kind === "nova") {
        lights.push({
          x: effect.x,
          y: effect.y,
          radius: effect.radius * 1.5,
          color: effect.color,
          power: fade,
        });
      } else if (effect.kind === "beam") {
        for (let step = 0; step <= 4; step += 1) {
          lights.push({
            x: effect.x1 + ((effect.x2 - effect.x1) * step) / 4,
            y: effect.y1 + ((effect.y2 - effect.y1) * step) / 4,
            radius: effect.width * 3.2,
            color: effect.color,
            power: fade,
          });
        }
      } else if (effect.kind === "bolt") {
        for (const point of effect.points) {
          lights.push({
            x: point.x,
            y: point.y,
            radius: 220,
            color: effect.color,
            power: fade,
          });
        }
      }
    }
    void now;
  }

  /** Multiply a map of everything that glows over the room behind the magic. */
  applyLighting(client, now, applyCamera, onlyDark = false) {
    const ctx = this.lightCtx;
    this.collectLights(client, now);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
    const story = client.config?.mode === "story";
    const blackout = story && client.life?.event?.kind === "blackout";
    if (blackout) ctx.fillStyle = "#08070e";
    else ctx.fillStyle = onlyDark ? "#ffffff" : story ? themeOf(client.config).ambient : AMBIENT_LIGHT;
    ctx.fillRect(0, 0, this.lightCanvas.width, this.lightCanvas.height);

    applyCamera(ctx);
    if (story && this.darkRooms?.length) {
      // A dark room has no lamps of its own: only what the party carries lights it.
      const tile = client.config.tile || 48;
      ctx.fillStyle = "#07060c";
      for (const room of this.darkRooms) {
        ctx.fillRect((room.x - 0.5) * tile, (room.y - 1.5) * tile, (room.w + 1) * tile, (room.h + 2) * tile);
      }
    }
    ctx.globalCompositeOperation = "lighter";
    for (const light of this.lights) {
      const { x, y, radius, power } = light;
      if (!(radius > 0) || !(power > 0)) continue;
      ctx.globalAlpha = Math.min(1, power);
      ctx.drawImage(this.lightSprite(light.color), x - radius, y - radius, radius * 2, radius * 2);
    }
    ctx.globalAlpha = 1;

    const world = this.worldCtx;
    world.setTransform(1, 0, 0, 1, 0, 0);
    world.globalCompositeOperation = "multiply";
    world.imageSmoothingEnabled = false;
    world.drawImage(this.lightCanvas, 0, 0);
    world.globalCompositeOperation = "source-over";
  }

  /**
   * Soft glow over the crisp pixels. Canvas has no threshold, but multiplying
   * an image by itself pushes everything except the brightest tones to black.
   * Shrinking twice and stretching back is the blur: it costs two small copies,
   * where a canvas filter costs a full convolution on every frame. It lands on
   * the low-res world, so the glow comes out as chunky as the art around it.
   */
  drawBloom(ctx) {
    const bloom = this.bloomCtx;
    const canvas = this.bloomCanvas;
    bloom.globalCompositeOperation = "copy";
    bloom.imageSmoothingEnabled = true;
    bloom.drawImage(this.worldCanvas, 0, 0, canvas.width, canvas.height);
    bloom.globalCompositeOperation = "multiply";
    bloom.drawImage(canvas, 0, 0);
    bloom.drawImage(canvas, 0, 0);

    const soft = this.softCtx;
    const small = this.softCanvas;
    soft.globalCompositeOperation = "copy";
    soft.imageSmoothingEnabled = true;
    soft.drawImage(canvas, 0, 0, small.width, small.height);

    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.imageSmoothingEnabled = true;
    ctx.globalAlpha = BLOOM_STRENGTH * 0.55;
    ctx.drawImage(canvas, 0, 0, this.worldCanvas.width, this.worldCanvas.height);
    ctx.globalAlpha = BLOOM_STRENGTH;
    ctx.drawImage(small, 0, 0, this.worldCanvas.width, this.worldCanvas.height);
    ctx.restore();
  }

  drawScreenBackdrop(ctx, width = this.width, height = this.height) {
    const gradient = ctx.createRadialGradient(
      width * 0.5,
      height * 0.46,
      20,
      width * 0.5,
      height * 0.46,
      Math.max(width, height) * 0.75,
    );
    gradient.addColorStop(0, "#241733");
    gradient.addColorStop(0.58, "#140f20");
    gradient.addColorStop(1, "#080711");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);
  }

  drawFrameVignette(ctx) {
    const gradient = ctx.createRadialGradient(
      this.width / 2,
      this.height / 2,
      Math.min(this.width, this.height) * 0.35,
      this.width / 2,
      this.height / 2,
      Math.max(this.width, this.height) * 0.78,
    );
    gradient.addColorStop(0, "rgba(0,0,0,0)");
    gradient.addColorStop(0.85, "rgba(8,5,16,0.12)");
    gradient.addColorStop(1, "rgba(8,5,16,0.32)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, this.width, this.height);
  }

  /** Mages and architecture share one depth order, so you can step behind a pillar. */
  drawScene(ctx, client, now, zoom, labels) {
    const self = this.visualPlayers.get(client.selfId);
    const scene = [];
    for (const obstacle of client.config?.obstacles || []) {
      scene.push({ depth: obstacle.y, obstacle });
    }
    for (const visual of this.visualPlayers.values()) {
      scene.push({ depth: visual.y, visual });
    }
    for (const creature of this.visualMonsters.values()) {
      scene.push({ depth: creature.y, creature });
    }
    scene.sort((a, b) => a.depth - b.depth);
    for (const { obstacle, visual, creature } of scene) {
      if (obstacle) drawObstacle(ctx, obstacle, now, this.obstacleAlpha(obstacle, self));
      else if (creature) drawMonster(ctx, creature, now);
      else this.drawPlayer(ctx, visual, client, now, zoom, labels);
    }
  }

  /** Thin out whatever stands in front of the player's own mage. */
  obstacleAlpha(obstacle, self) {
    if (!self || self.dead) return 1;
    const behind = obstacle.y - self.y;
    const height = OBSTACLE_HEIGHT[obstacle.kind] || 100;
    const hidden =
      behind > 0 &&
      behind < height &&
      Math.abs(self.x - obstacle.x) < obstacle.r * 1.1 + 14;
    return hidden ? 0.42 : 1;
  }

  drawPlayer(ctx, visual, client, now, zoom, labels) {
    const screen = this.worldToScreen(visual.x, visual.y);
    if (
      screen.x < -110 ||
      screen.x > this.width + 110 ||
      screen.y < -100 ||
      screen.y > this.height + 110
    ) {
      return;
    }
    this.drawPlayerBody(ctx, visual, client, now, zoom);
    labels.push({
      visual,
      player: visual.data,
      self: visual.data.id === client.selfId,
      screenX: screen.x,
      screenY: screen.y,
      dead: Boolean(visual.dead),
    });
  }

  drawPlayerBody(ctx, visual, client, now, zoom) {
    const player = visual.data;
    const color = player.color || VIOLET;
    const self = player.id === client.selfId;
    const t = now / 1000;
    ctx.save();
    ctx.translate(visual.x, visual.y);
    if (visual.roll > 0 && !player.dead) {
      const rollProgress = 1 - visual.roll / 0.32;
      ctx.rotate(rollProgress * TAU);
      ctx.scale(1, 1 - Math.sin(rollProgress * Math.PI) * 0.14);
    }

    const aura = ctx.createRadialGradient(0, 0, 1, 0, 0, 50);
    aura.addColorStop(0, rgba(color, player.dead ? 0.035 : 0.11));
    aura.addColorStop(0.6, rgba(color, player.dead ? 0.012 : 0.03));
    aura.addColorStop(1, rgba(color, 0));
    ctx.fillStyle = aura;
    ctx.beginPath();
    ctx.arc(0, 0, 50, 0, TAU);
    ctx.fill();

    ctx.fillStyle = "rgba(0, 0, 0, 0.42)";
    ctx.beginPath();
    ctx.ellipse(3, 10, 21, 10, 0.14, 0, TAU);
    ctx.fill();

    if (player.dead) {
      const pulse = 0.5 + Math.sin(t * 2.2 + player.id) * 0.5;
      ctx.globalCompositeOperation = "lighter";
      const soul = ctx.createRadialGradient(0, -10, 1, 0, -10, 18);
      soul.addColorStop(0, rgba(color, 0.32 + pulse * 0.14));
      soul.addColorStop(0.45, rgba(color, 0.12));
      soul.addColorStop(1, rgba(color, 0));
      ctx.fillStyle = soul;
      ctx.beginPath();
      ctx.arc(0, -10, 18, 0, TAU);
      ctx.fill();
      ctx.strokeStyle = rgba(color, 0.28);
      ctx.lineWidth = 1 / zoom;
      ctx.setLineDash([2, 5]);
      ctx.beginPath();
      ctx.arc(0, 0, 23, t * 0.2, t * 0.2 + TAU);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
      return;
    }

    if (player.slow) {
      ctx.strokeStyle = "rgba(124, 231, 255, 0.4)";
      ctx.lineWidth = 1.2 / zoom;
      for (let index = 0; index < 3; index += 1) {
        ctx.beginPath();
        ctx.arc(0, 0, 18 + index * 3.4, index * 2.1, index * 2.1 + 0.55);
        ctx.stroke();
      }
      ctx.fillStyle = "rgba(124, 231, 255, 0.06)";
      ctx.beginPath();
      ctx.arc(0, 0, 24, 0, TAU);
      ctx.fill();
    }

    if (player.stun || visual.stunFlash > 0) {
      const stunPulse = 0.72 + Math.sin(t * 24 + player.id) * 0.2;
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      const stunGlow = ctx.createRadialGradient(0, -2, 1, 0, -2, 31);
      stunGlow.addColorStop(0, `rgba(225, 242, 255, ${0.18 * stunPulse})`);
      stunGlow.addColorStop(0.5, `rgba(130, 157, 255, ${0.1 * stunPulse})`);
      stunGlow.addColorStop(1, "rgba(111, 124, 255, 0)");
      ctx.fillStyle = stunGlow;
      ctx.beginPath();
      ctx.arc(0, -2, 31, 0, TAU);
      ctx.fill();
      for (let arc = 0; arc < 4; arc += 1) {
        const start = t * 4.8 + arc * 1.57;
        ctx.strokeStyle =
          arc % 2 === 0
            ? `rgba(210, 235, 255, ${0.76 * stunPulse})`
            : `rgba(191, 166, 255, ${0.62 * stunPulse})`;
        ctx.lineWidth = 1.15 / zoom;
        ctx.beginPath();
        for (let step = 0; step <= 7; step += 1) {
          const angle = start + step * 0.12;
          const radius = 24 + Math.sin(t * 25 + arc * 2.4 + step * 1.9) * 2.8;
          const x = Math.cos(angle) * radius;
          const y = Math.sin(angle) * radius * 0.88 - 2;
          if (step === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
      for (let spark = 0; spark < 5; spark += 1) {
        const x = Math.sin(t * 15 + spark * 2.3 + player.id) * (7 + spark * 2.2);
        const y = -25 - ((t * 32 + spark * 9) % 17);
        ctx.fillStyle = `rgba(228, 245, 255, ${0.78 * stunPulse})`;
        ctx.fillRect(x - 0.8, y - 2.2, 1.6, 4.4);
      }
      ctx.restore();
    }

    if (self) {
      ctx.save();
      ctx.rotate(t * 0.24);
      ctx.strokeStyle = "rgba(217, 181, 108, 0.5)";
      ctx.lineWidth = 1 / zoom;
      ctx.setLineDash([5, 7]);
      ctx.beginPath();
      ctx.arc(0, 0, 33, 0, TAU);
      ctx.stroke();
      ctx.restore();
      ctx.save();
      ctx.rotate(-t * 0.16);
      ctx.strokeStyle = "rgba(169, 151, 255, 0.2)";
      ctx.lineWidth = 1 / zoom;
      for (let index = 0; index < 4; index += 1) {
        ctx.beginPath();
        ctx.arc(0, 0, 39, index * 1.57, index * 1.57 + 0.52);
        ctx.stroke();
      }
      ctx.restore();
    }

    if (visual.cast > 0) {
      const progress = 1 - visual.cast / 0.4;
      ctx.strokeStyle = rgba(color, (1 - progress) * 0.6);
      ctx.lineWidth = 1.3 / zoom;
      ctx.beginPath();
      ctx.arc(0, 0, 30 + progress * 18, 0, TAU);
      ctx.stroke();
    }

    drawMage(ctx, visual, color, this.bandOf(player), t);
    ctx.lineCap = "round";

    if (player.shield > 0) {
      const strength = clamp(player.shield / 38, 0.2, 1);
      const shieldPulse = 0.72 + Math.sin(t * 2.8 + player.id) * 0.12;
      const bubble = 50;
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = `rgba(105, 178, 246, ${0.04 + strength * 0.05})`;
      ctx.beginPath();
      ctx.arc(0, -8, bubble, 0, TAU);
      ctx.fill();
      pixelRing(ctx, 0, -8, bubble, 3, "#9ad6ff", 0.55 * strength * shieldPulse, { turn: t * 0.35 });
      pixelRing(ctx, 0, -8, bubble - 6, 2.2, "#e0f5ff", 0.4 * strength, { gap: 0.55, seed: player.id, turn: -t * 0.5 });
      ctx.globalCompositeOperation = "source-over";
    }

    if (player.invuln) {
      ctx.save();
      ctx.rotate(t * 1.4);
      ctx.strokeStyle = "rgba(244, 217, 155, 0.3)";
      ctx.lineWidth = 1 / zoom;
      ctx.setLineDash([2, 5]);
      ctx.beginPath();
      ctx.arc(0, 0, 32, 0, TAU);
      ctx.stroke();
      ctx.restore();
    }

    if (visual.hurt > 0) {
      const alpha = clamp(visual.hurt / 0.3, 0, 1);
      ctx.fillStyle = `rgba(255, 100, 105, ${alpha * 0.18})`;
      ctx.beginPath();
      ctx.arc(0, 0, 25, 0, TAU);
      ctx.fill();
    }

    if (player.bot) {
      ctx.fillStyle = rgba(GOLD, 0.45);
      ctx.save();
      ctx.rotate(Math.PI / 4);
      ctx.fillRect(-1.2, -1.2, 2.4, 2.4);
      ctx.restore();
    }
    ctx.restore();
  }

  drawProjectiles(ctx, now, zoom) {
    const t = now / 1000;
    ctx.save();
    ctx.imageSmoothingEnabled = false;
    for (const visual of this.visualProjectiles.values()) {
      const projectile = visual.data;
      ctx.globalCompositeOperation = "lighter";
      if (projectile.kind === "orb") {
        this.drawOrb(ctx, visual, projectile.color, t);
        continue;
      }
      const isFrost = projectile.kind === "frost";
      const isSpark = projectile.kind === "spark";
      const baseColor = projectile.color || (isSpark ? "#ffe17a" : isFrost ? "#7ce7ff" : "#ff9a4d");
      const { x, y, trail } = visual;
      const seed = projectile.id;

      if (isSpark) {
        // It crackles along where it has been.
        if (trail.length > 3) {
          const path = [];
          for (let index = 0; index < trail.length; index += 4) path.push(trail[index]);
          path.push({ x, y });
          drawJaggedBolt(ctx, path, baseColor, 2.4, 0.5, t + seed, 0);
        }
      } else if (isFrost) {
        for (let index = 0; index < trail.length; index += 2) {
          const point = trail[index];
          const progress = index / trail.length;
          const size = 1.5 + progress * 3.5;
          const drift = Math.sin(index * 1.7 + seed) * (1 - progress) * 9;
          ctx.globalAlpha = progress * 0.55;
          ctx.fillStyle = index % 4 ? baseColor : "#ffffff";
          ctx.fillRect(point.x + drift - size / 2, point.y - drift - size / 2, size, size);
        }
      } else {
        // Burning on the way, hottest next to the head and smoking at the tail.
        for (let index = 0; index < trail.length; index += 1) {
          const point = trail[index];
          const progress = index / trail.length;
          const size = 3 + 13 * progress ** 1.4;
          const shake = Math.sin(index * 7.1 + t * 31 + seed) * (1 - progress) * 7;
          ctx.globalAlpha = progress * 0.72;
          ctx.fillStyle = progress > 0.74 ? "#fff1b8" : progress > 0.42 ? baseColor : "#b02a14";
          ctx.fillRect(point.x + shake - size / 2, point.y - shake - size / 2, size, size);
        }
      }
      ctx.globalAlpha = 1;

      const haloRadius = isSpark ? 26 : isFrost ? 36 : 50;
      const glow = ctx.createRadialGradient(x, y, 0, x, y, haloRadius);
      glow.addColorStop(0, rgba(baseColor, 0.65));
      glow.addColorStop(0.45, rgba(baseColor, 0.2));
      glow.addColorStop(1, rgba(baseColor, 0));
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(x, y, haloRadius, 0, TAU);
      ctx.fill();

      ctx.save();
      ctx.translate(x, y);
      if (isSpark) {
        ctx.globalCompositeOperation = "source-over";
        drawStar(ctx, 0, 0, 13 + Math.sin(t * 30 + seed) * 3, baseColor, 1, t * 7 + seed);
      } else if (isFrost) {
        ctx.rotate(visual.angle);
        ctx.globalCompositeOperation = "source-over";
        ctx.drawImage(frostShard(baseColor), -30, -16, 56, 30);
      } else {
        ctx.rotate(visual.angle);
        ctx.globalCompositeOperation = "source-over";
        ctx.drawImage(flameFrame(baseColor, t + seed * 0.13), -52, -22, 68, 44);
      }
      ctx.restore();
    }
    ctx.restore();
    void zoom;
  }

  /** Enemy shots: small, hard-edged and ringed in dark so they read on any floor. */
  drawOrb(ctx, visual, color, t) {
    const pulse = 1 + Math.sin(t * 16 + visual.data.id) * 0.12;
    const { x, y } = visual;
    ctx.fillStyle = rgba(color, 0.34);
    ctx.beginPath();
    ctx.arc(x, y, 21 * pulse, 0, TAU);
    ctx.fill();
    ctx.globalCompositeOperation = "source-over";
    ctx.fillStyle = "#0b0812";
    ctx.beginPath();
    ctx.arc(x, y, 12.5, 0, TAU);
    ctx.fill();
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, 10, 0, TAU);
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(x - 2, y - 2, 4, 0, TAU);
    ctx.fill();
    ctx.globalCompositeOperation = "lighter";
  }

  drawWards(ctx, client, now, zoom) {
    const t = now / 1000;
    for (const ward of client.wards) {
      const armed = Boolean(ward.armed);
      const pulse = 0.5 + Math.sin(t * 2.6 + ward.id) * 0.5;
      const alpha = armed ? 0.85 : 0.35;
      ctx.save();
      ctx.translate(ward.x, ward.y);
      const glow = ctx.createRadialGradient(0, 0, 1, 0, 0, 34);
      glow.addColorStop(0, `rgba(173, 143, 255, ${armed ? 0.3 : 0.12})`);
      glow.addColorStop(1, "rgba(173, 143, 255, 0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(0, 0, 34, 0, TAU);
      ctx.fill();
      pixelRing(ctx, 0, 0, 38, 2.2, VIOLET, 0.2 + pulse * 0.14, { gap: 0.4, seed: ward.id, turn: t * 0.2 });
      const spin = t * (armed ? 0.5 : 0.14) + ward.id;
      pixelRing(ctx, 0, 0, 20, 2.6, "#f3d27f", alpha, { turn: spin });
      // A hexagram of two triangles, one turning against the other.
      ctx.globalAlpha = alpha;
      ctx.fillStyle = VIOLET;
      for (const [turn, tone] of [[spin, VIOLET], [-spin, "#f3d27f"]]) {
        ctx.fillStyle = tone;
        for (let corner = 0; corner < 3; corner += 1) {
          const from = turn + (corner / 3) * TAU;
          const to = turn + ((corner + 1) / 3) * TAU;
          pixelLine(ctx, Math.cos(from) * 18, Math.sin(from) * 18, Math.cos(to) * 18, Math.sin(to) * 18, 2);
        }
      }
      ctx.globalAlpha = 1;
      ctx.restore();
      if (armed) {
        pixelRing(ctx, ward.x, ward.y, 26 + pulse * 5, 2, VIOLET, 0.18 + pulse * 0.2, { gap: 0.5, seed: ward.id });
      }
      if (ward.ttl < 2.4) {
        ctx.fillStyle = `rgba(255, 140, 130, ${0.45 + pulse * 0.4})`;
        ctx.fillRect(ward.x + 15, ward.y - 17, 4, 4);
      }
    }
    void zoom;
  }

  drawEmps(ctx, client, now, zoom) {
    const t = now / 1000;
    const emps = Array.isArray(client.emps) ? client.emps : [];
    for (const emp of emps) {
      const radius = Number(emp.radius) || 190;
      const delay = Math.max(0.1, Number(emp.delay) || 1.5);
      const ttl = Math.max(0, Number(emp.ttl) || 0);
      const pulled = Math.max(0, Number(emp.pull_ttl) || 0) <= 0.001;
      const progress = clamp(1 - ttl / delay, 0, 1);
      const pulse = 0.5 + Math.sin(t * 7.2 + emp.id) * 0.5;
      const color = emp.color || EMP_COLOR;
      ctx.save();
      ctx.translate(emp.x, emp.y);
      // Where it will reach, and a second ring closing in as the moment comes.
      pixelRing(ctx, 0, 0, radius, 3, color, 0.3 + progress * 0.45, { gap: 0.3, seed: emp.id, turn: t * 0.15 });
      pixelRing(ctx, 0, 0, radius * (1 - progress * 0.9), 3.6, "#efe6ff", 0.3 + progress * 0.5, { gap: 0.2, seed: emp.id + 1 });
      const orb = 12 + progress * 12 + pulse * 2.2;
      ctx.globalCompositeOperation = "lighter";
      const glow = ctx.createRadialGradient(0, 0, 0, 0, 0, orb * 3.2);
      glow.addColorStop(0, rgba("#f0e8ff", 0.75));
      glow.addColorStop(0.3, rgba(color, 0.5));
      glow.addColorStop(1, rgba(color, 0));
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(0, 0, orb * 3.2, 0, TAU);
      ctx.fill();
      ctx.globalCompositeOperation = "source-over";
      this.drawPixelDisc(ctx, 0, 0, orb, ["#f7f1ff", "#d8c6ff", color, "#ffffff"], Math.floor(t * 9) + emp.id);
      ctx.globalCompositeOperation = "lighter";
      // Arcs reaching out from the middle, each lasting one flicker.
      const arcs = pulled ? 7 : 4;
      for (let arc = 0; arc < arcs; arc += 1) {
        const angle = (arc / arcs) * TAU + Math.floor(t * 7) * 1.3 + emp.id;
        const reach = radius * (0.34 + progress * 0.42);
        drawJaggedBolt(
          ctx,
          [
            { x: Math.cos(angle) * orb, y: Math.sin(angle) * orb },
            { x: Math.cos(angle) * reach, y: Math.sin(angle) * reach },
          ],
          color,
          2.2,
          0.5 + progress * 0.4,
          t + arc,
          0,
        );
      }
      ctx.restore();
    }
    void zoom;
  }

  drawClouds(ctx, client, now, zoom) {
    const t = now / 1000;
    const clouds = Array.isArray(client.clouds) ? client.clouds : [];
    for (const cloud of clouds) {
      const radius = Number(cloud.radius) || 110;
      const color = cloud.color || "#86e08a";
      const pulse = 0.5 + Math.sin(t * 2.2 + cloud.id) * 0.5;
      const fade = clamp(Math.max(0, Number(cloud.ttl) || 0) / 1.2, 0, 1);
      ctx.save();
      ctx.translate(cloud.x, cloud.y);
      ctx.imageSmoothingEnabled = false;
      for (let index = 0; index < 10; index += 1) {
        const angle = (index / 10) * TAU + t * (0.1 + (index % 3) * 0.03) + cloud.id * 0.7;
        const orbit = radius * (0.2 + (index % 4) * 0.16);
        const size = radius * (0.72 + (index % 3) * 0.16) + Math.sin(t * 1.4 + index) * 5;
        ctx.globalAlpha = (0.2 + pulse * 0.05) * fade;
        ctx.drawImage(
          puffSprite(color, index % 3),
          Math.cos(angle) * orbit - size / 2,
          Math.sin(angle * 0.85) * orbit * 0.62 - size / 2,
          size,
          size,
        );
      }
      // Bubbles that come up and pop.
      for (let index = 0; index < 8; index += 1) {
        const rise = (t * 0.45 + index * 0.37 + cloud.id * 0.2) % 1;
        const across = Math.sin(index * 2.4 + cloud.id) * radius * 0.7;
        const up = Math.cos(index * 1.3 + cloud.id) * radius * 0.42 - rise * 34;
        const size = 2 + (index % 3);
        ctx.globalAlpha = (1 - rise) * 0.75 * fade;
        ctx.fillStyle = "#d5ffc9";
        ctx.fillRect(across - size / 2, up - size / 2, size, size);
      }
      ctx.globalAlpha = 1;
      pixelRing(ctx, 0, 0, radius, 2.6, color, (0.2 + pulse * 0.16) * fade, { gap: 0.5, seed: cloud.id, turn: t * 0.1 });
      ctx.restore();
    }
    void zoom;
  }

  drawPixelDisc(ctx, x, y, radius, colors, seed) {
    const cell = Math.max(2, radius * 0.42);
    const span = Math.ceil(radius / cell);
    for (let gy = -span; gy <= span; gy += 1) {
      for (let gx = -span; gx <= span; gx += 1) {
        if (gx * gx + gy * gy > span * span + span * 0.8) continue;
        const noise = Math.abs(
          Math.sin((gx + seed * 3.1) * 12.9898 + (gy - seed * 1.7) * 78.233),
        );
        const index = Math.min(
          colors.length - 1,
          Math.floor(noise * colors.length),
        );
        ctx.fillStyle = colors[index];
        ctx.fillRect(
          Math.round(x + gx * cell - cell / 2),
          Math.round(y + gy * cell - cell / 2),
          Math.ceil(cell),
          Math.ceil(cell),
        );
      }
    }
  }

  drawPixelMeteor(ctx, headX, headY, backX, backY, size, variant) {
    const distance = Math.hypot(backX, backY) || 1;
    const ux = backX / distance;
    const uy = backY / distance;
    const steps = 9;
    const trailLength = size * 5.6;

    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    const glow = ctx.createRadialGradient(
      headX,
      headY,
      size * 0.2,
      headX,
      headY,
      size * 2.6,
    );
    glow.addColorStop(0, "rgba(255, 177, 46, 0.24)");
    glow.addColorStop(1, "rgba(255, 80, 20, 0)");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(headX, headY, size * 2.6, 0, TAU);
    ctx.fill();
    ctx.globalCompositeOperation = "source-over";

    for (let layer = 0; layer < 2; layer += 1) {
      for (let index = steps; index >= 0; index -= 1) {
        const fade = index / steps;
        const travel = fade * trailLength;
        const side =
          (((index + variant * 2) % 3) - 1) *
          size *
          (0.08 + layer * 0.025);
        const px = headX + ux * travel + uy * side;
        const py = headY + uy * travel - ux * side;
        const width =
          size * (layer === 0 ? 2.1 - fade * 1.15 : 1.12 - fade * 0.5);
        const height =
          size * (layer === 0 ? 1.5 - fade * 0.85 : 0.72 - fade * 0.3);
        let color;
        if (layer === 0) {
          color =
            fade > 0.72 ? "#b93c12" : fade > 0.42 ? "#ef6a19" : "#ffb12e";
        } else {
          color =
            fade > 0.7 ? "#ff7c20" : fade > 0.35 ? "#ffd44d" : "#fff4c2";
        }
        ctx.fillStyle = color;
        ctx.fillRect(
          Math.round(px - width / 2),
          Math.round(py - height / 2),
          Math.ceil(width),
          Math.ceil(height),
        );
      }
    }

    for (let index = 0; index < 6; index += 1) {
      const fade = (index + 1) / 7;
      const travel = fade * trailLength * 1.02;
      const side = Math.sin(index * 2.1 + variant) * size * 0.9;
      ctx.fillStyle = index % 2 ? "#ffd25a" : "#ff7a1f";
      const mote = index % 2 ? 2 : 3;
      ctx.fillRect(
        Math.round(headX + ux * travel + uy * side),
        Math.round(headY + uy * travel - ux * side),
        mote,
        mote,
      );
    }

    this.drawPixelDisc(
      ctx,
      headX,
      headY,
      size * 1.24,
      ["#ff7b18", "#ff9f22", "#ffc33a"],
      variant + 3,
    );
    this.drawPixelDisc(
      ctx,
      headX,
      headY,
      size * 1.02,
      ["#ffd04a", "#ffe16a", "#ffae25"],
      variant + 7,
    );
    this.drawPixelDisc(
      ctx,
      headX,
      headY,
      size * 0.82,
      ["#11171c", "#222d36", "#35434d", "#4b5c68", "#1a232b"],
      variant + 11,
    );

    ctx.fillStyle = "#8ea3af";
    ctx.fillRect(
      Math.round(headX - size * 0.34),
      Math.round(headY - size * 0.4),
      Math.max(2, Math.round(size * 0.2)),
      Math.max(2, Math.round(size * 0.2)),
    );
    ctx.fillStyle = "#5f7481";
    ctx.fillRect(
      Math.round(headX + size * 0.1),
      Math.round(headY + size * 0.18),
      Math.max(2, Math.round(size * 0.16)),
      Math.max(2, Math.round(size * 0.16)),
    );
    ctx.restore();
  }

  drawMeteors(ctx, client, now, zoom) {
    const t = now / 1000;
    const meteors = Array.isArray(client.meteors) ? client.meteors : [];
    const lanes = [
      { x: -175, y: -205, scale: 1 },
      { x: -255, y: -110, scale: 0.74 },
      { x: -60, y: -255, scale: 0.6 },
    ];
    for (const meteor of meteors) {
      const radius = Number(meteor.radius) || 120;
      const delay = Math.max(0.1, Number(meteor.delay) || 1.15);
      const ttl = Math.max(0, Number(meteor.ttl) || 0);
      const progress = clamp(1 - ttl / delay, 0, 1);
      const color = meteor.color || "#ff7b45";
      const isMain = meteor.role !== "satellite";
      const variant = Number(meteor.variant) || 0;
      const pulse = 0.5 + Math.sin(t * 8 + meteor.id) * 0.5;
      const strength = isMain ? 1 : 0.34;

      ctx.save();
      ctx.translate(meteor.x, meteor.y);

      ctx.fillStyle = rgba(color, (0.05 + progress * 0.13) * strength);
      ctx.beginPath();
      ctx.arc(0, 0, radius, 0, TAU);
      ctx.fill();
      pixelRing(ctx, 0, 0, radius, 3, color, (0.4 + progress * 0.5) * strength, { gap: 0.25, seed: meteor.id, turn: t * 0.2 });
      if (isMain) {
        // The closer ring is how long there is left to get out.
        pixelRing(ctx, 0, 0, radius * (1 - progress * 0.92), 3.6, "#fff1b8", 0.35 + pulse * 0.25 + progress * 0.3);
        ctx.fillStyle = rgba("#fff1b8", 0.5 + pulse * 0.3);
        ctx.fillRect(-14, -1.5, 28, 3);
        ctx.fillRect(-1.5, -14, 3, 28);
      }
      ctx.restore();

      const lane = isMain
        ? lanes[0]
        : lanes[Math.min(2, Math.max(1, variant))];
      const size = (isMain ? 1 : lane.scale) * clamp(radius * 0.18, 12, 28);
      const startX = meteor.x + lane.x;
      const startY = meteor.y + lane.y;
      const headX = startX + (meteor.x - startX) * progress;
      const headY = startY + (meteor.y - startY) * progress;
      this.drawPixelMeteor(
        ctx,
        headX,
        headY,
        startX - meteor.x,
        startY - meteor.y,
        size,
        variant,
      );
    }
  }

  /** One pass for what spreads along the floor, one for what hangs in the air. */
  drawEffects(ctx, now, zoom, onGround) {
    ctx.save();
    ctx.imageSmoothingEnabled = false;
    ctx.globalCompositeOperation = "lighter";
    for (const effect of this.effects) {
      if (GROUND_EFFECTS.has(effect.kind) !== onGround) continue;
      const progress = clamp(effect.age / effect.life, 0, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const alpha = 1 - progress;
      if (effect.kind === "scorch") {
        const size = 118 * (effect.scale || 1);
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = Math.min(1, alpha * 2.4);
        ctx.drawImage(
          scorchSprite(effect.element, effect.color, effect.variant || 0),
          effect.x - size / 2,
          effect.y - size / 2,
          size,
          size,
        );
        ctx.globalAlpha = 1;
        ctx.globalCompositeOperation = "lighter";
      } else if (effect.kind === "explosion") {
        const scale = effect.scale || 1;
        const hot = effect.element === "frost" ? "#e6fdff" : "#fff5d6";
        if (progress < 0.24) {
          const flash = ctx.createRadialGradient(effect.x, effect.y, 0, effect.x, effect.y, 92 * scale);
          flash.addColorStop(0, rgba(hot, (1 - progress / 0.24) * 0.85));
          flash.addColorStop(1, rgba(hot, 0));
          ctx.fillStyle = flash;
          ctx.beginPath();
          ctx.arc(effect.x, effect.y, 92 * scale, 0, TAU);
          ctx.fill();
        }
        const size = 142 * scale;
        ctx.globalCompositeOperation = "source-over";
        ctx.drawImage(blastFrame(effect.element, effect.color, progress), effect.x - size / 2, effect.y - size / 2, size, size);
        ctx.globalCompositeOperation = "lighter";
        pixelRing(ctx, effect.x, effect.y, (20 + eased * 92) * scale, 4.4 * Math.min(1.5, scale), hot, alpha ** 1.5 * 0.95, { gap: 0.18, seed: effect.x });
      } else if (effect.kind === "ring") {
        const radius = effect.from + (effect.to - effect.from) * eased;
        if (radius <= 0) continue;
        pixelRing(ctx, effect.x, effect.y, radius, Math.max(2.4, effect.width * 1.5), effect.color, alpha * 0.85, {
          gap: effect.runes ? 0.3 : 0.08,
          seed: effect.y,
        });
      } else if (effect.kind === "nova") {
        const radius = effect.radius * eased;
        if (progress < 0.2) {
          const flash = ctx.createRadialGradient(effect.x, effect.y, 0, effect.x, effect.y, effect.radius * 0.6);
          flash.addColorStop(0, rgba(effect.color, (1 - progress / 0.2) * 0.5));
          flash.addColorStop(1, rgba(effect.color, 0));
          ctx.fillStyle = flash;
          ctx.beginPath();
          ctx.arc(effect.x, effect.y, effect.radius * 0.6, 0, TAU);
          ctx.fill();
        }
        pixelRing(ctx, effect.x, effect.y, radius, 7 - progress * 4, effect.color, alpha, { turn: progress });
        pixelRing(ctx, effect.x, effect.y, radius - 11, 3.4, "#ffffff", alpha * 0.8, { gap: 0.35, seed: effect.x });
        pixelRing(ctx, effect.x, effect.y, radius * 0.72, 2.6, effect.color, alpha * 0.45, { gap: 0.5, seed: effect.y });
        // What the wave is throwing ahead of itself.
        ctx.fillStyle = rgba("#fff1c8", alpha * 0.8);
        for (let index = 0; index < 18; index += 1) {
          const angle = (index / 18) * TAU + 0.3;
          const reach = radius * (0.84 + ((index * 7) % 5) * 0.05);
          const size = 2.4 + (index % 3);
          ctx.fillRect(effect.x + Math.cos(angle) * reach - size / 2, effect.y + Math.sin(angle) * reach - size / 2, size, size);
        }
      } else if (effect.kind === "bolt") {
        drawJaggedBolt(ctx, effect.points, effect.color, (effect.width || 4) * 1.15, alpha, effect.age);
        const end = effect.points[effect.points.length - 1];
        drawStar(ctx, end.x, end.y, 20 * alpha + 6, effect.color, alpha);
      } else if (effect.kind === "line") {
        const across = Math.hypot(effect.x2 - effect.x1, effect.y2 - effect.y1);
        ctx.save();
        ctx.translate(effect.x1, effect.y1);
        ctx.rotate(Math.atan2(effect.y2 - effect.y1, effect.x2 - effect.x1));
        ctx.fillStyle = rgba(effect.color, alpha * 0.45);
        ctx.fillRect(0, -effect.width * 0.6, across, effect.width * 1.2);
        ctx.fillStyle = rgba("#ffffff", alpha * 0.5);
        ctx.fillRect(0, -effect.width * 0.16, across, effect.width * 0.32);
        ctx.restore();
      } else if (effect.kind === "beam") {
        const across = Math.hypot(effect.x2 - effect.x1, effect.y2 - effect.y1);
        const reached = across * Math.min(1, progress * 7);
        const width = effect.width * (1 - progress ** 2.4) * (0.86 + Math.sin(effect.age * 60) * 0.14);
        const flow = effect.reverse ? -1 : 1;
        ctx.save();
        ctx.translate(effect.x1, effect.y1);
        ctx.rotate(Math.atan2(effect.y2 - effect.y1, effect.x2 - effect.x1));
        ctx.fillStyle = rgba(effect.color, 0.2);
        ctx.fillRect(0, -width * 0.62, reached, width * 1.24);
        ctx.fillStyle = rgba(effect.color, 0.5);
        ctx.fillRect(0, -width * 0.36, reached, width * 0.72);
        ctx.fillStyle = "rgba(255, 255, 255, 0.95)";
        ctx.fillRect(0, -width * 0.14, reached, width * 0.28);
        // Packets of light running down it, and bits coming off the edges.
        ctx.fillStyle = "rgba(255, 255, 255, 0.75)";
        for (let packet = 0; packet < 16; packet += 1) {
          const along = (((packet * 58 + flow * effect.age * 1500) % reached) + reached) % reached;
          ctx.fillRect(along, -width * 0.26, 20, width * 0.52);
        }
        ctx.fillStyle = rgba(effect.color, 0.9);
        for (let bit = 0; bit < 22; bit += 1) {
          const along = (bit * 73 + Math.floor(effect.age * 40) * 41) % Math.max(1, reached);
          const off = ((bit * 37) % 100) / 100 - 0.5;
          ctx.fillRect(along, off * width * 1.5, 5, 5);
        }
        ctx.restore();
        if (!effect.flat) {
          drawStar(ctx, effect.x1, effect.y1, width * 0.7, effect.color, alpha + 0.3, effect.age * 5);
          if (progress * 7 >= 1) drawStar(ctx, effect.x2, effect.y2, width * 0.9, effect.color, alpha + 0.3, -effect.age * 5);
        }
      } else if (effect.kind === "ghost") {
        const { image, facing, left, top, width, height } = effect.ghost;
        ctx.save();
        ctx.translate(effect.x, effect.y);
        ctx.scale(facing, 1);
        ctx.globalAlpha = alpha * 0.55;
        ctx.drawImage(image, left, top, width, height);
        ctx.restore();
      } else if (effect.kind === "star") {
        drawStar(ctx, effect.x, effect.y, effect.size * (0.6 + eased * 0.6), effect.color, alpha, effect.turn || 0);
      }
    }
    ctx.restore();
    void now;
    void zoom;
  }

  drawParticles(ctx, now, zoom) {
    ctx.save();
    // Things with a body first: dust, smoke and debris do not glow.
    for (const particle of this.particles) {
      const { kind } = particle;
      if (kind !== "chunk" && kind !== "dust" && kind !== "smoke") continue;
      const alpha = clamp(particle.life / particle.maxLife, 0, 1);
      if (alpha <= 0) continue;
      ctx.fillStyle = particle.color;
      if (kind === "dust") {
        const puff = particle.size * (1.6 - alpha * 0.8);
        ctx.globalAlpha = alpha * 0.2;
        ctx.fillRect(particle.x - puff / 2, particle.y - puff / 2, puff, puff);
      } else if (kind === "smoke") {
        const puff = particle.size * (1.7 - alpha * 0.9);
        ctx.globalAlpha = Math.min(0.42, alpha * 0.55);
        ctx.fillRect(particle.x - puff / 2, particle.y - puff / 2, puff, puff);
        ctx.globalAlpha *= 0.55;
        ctx.fillRect(particle.x - puff * 0.7, particle.y - puff * 0.32, puff * 1.4, puff * 0.64);
      } else {
        ctx.globalAlpha = Math.min(1, alpha * 1.8);
        ctx.fillRect(particle.x - particle.size / 2, particle.y - particle.size / 2, particle.size, particle.size);
      }
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "lighter";
    for (const particle of this.particles) {
      const { kind } = particle;
      if (kind === "chunk" || kind === "dust" || kind === "smoke") continue;
      const alpha = clamp(particle.life / particle.maxLife, 0, 1);
      if (alpha <= 0) continue;
      const size = Math.max(0.8, particle.size * (0.5 + alpha * 0.6));
      ctx.globalAlpha = Math.min(1, alpha * 1.1);
      ctx.fillStyle = particle.color;
      if (kind === "spark") {
        ctx.strokeStyle = particle.color;
        ctx.lineWidth = Math.max(1, size * 0.7);
        ctx.beginPath();
        ctx.moveTo(particle.x, particle.y);
        ctx.lineTo(particle.x - particle.vx * 0.024, particle.y - particle.vy * 0.024);
        ctx.stroke();
      } else if (kind === "shard") {
        ctx.save();
        ctx.translate(particle.x, particle.y);
        ctx.rotate(particle.rotation);
        ctx.beginPath();
        ctx.moveTo(size * 2.4, 0);
        ctx.lineTo(0, size);
        ctx.lineTo(-size * 1.4, 0);
        ctx.lineTo(0, -size);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
      } else if (kind === "rune") {
        drawGlyph(ctx, particle.x, particle.y, Math.max(1.4, size * 0.75), particle.glyph);
      } else if (kind === "plus") {
        ctx.fillRect(particle.x - size * 1.5, particle.y - size * 0.5, size * 3, size);
        ctx.fillRect(particle.x - size * 0.5, particle.y - size * 1.5, size, size * 3);
      } else if (kind === "wisp") {
        ctx.globalAlpha = alpha * 0.55;
        ctx.fillRect(particle.x - size, particle.y - size, size * 2, size * 2);
      } else {
        // Embers start white-hot and cool down into their own colour.
        if (alpha > 0.72) ctx.fillStyle = "#fff4d0";
        ctx.fillRect(particle.x - size / 2, particle.y - size / 2, size, size);
      }
    }
    ctx.restore();
    void now;
    void zoom;
  }

  drawNameplates(ctx, labels, client, now) {
    const zoom = this.camera.zoom;
    ctx.save();
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";

    for (const label of labels) {
      const { visual, player, self, screenX, screenY } = label;
      if (screenX < -40 || screenX > this.width + 40) continue;
      const verticalOffset = 66 + 18 * zoom;
      const nameY = screenY - verticalOffset;
      if (nameY < 66 && screenY < 180) {
        // Keep labels clear of the top navigation while still drawing off-screen hints.
      }

      if (label.dead) {
        const respawn = Number(player.respawn_in || 0);
        const story = client.config?.mode === "story";
        ctx.fillStyle = "rgba(231, 105, 114, 0.8)";
        ctx.font = "13px 'Cozette', monospace";
        ctx.fillText(
          story ? `${player.name}: подойдите, чтобы поднять` : `ВОЗРОЖДЕНИЕ ${respawn.toFixed(1)}`,
          screenX,
          screenY - 46,
        );
        const revive = Number(player.revive) || 0;
        if (revive > 0) drawMonsterBar(ctx, screenX, screenY - 40, 60, clamp(revive, 0, 1));
        continue;
      }

      const color = player.color || VIOLET;
      const hp = clamp(((Number(player.hp) || 0) / (Number(player.max_hp) || 100)) * 100, 0, 100);
      const barWidth = self ? 60 : 50;
      const barY = nameY + 6;

      // Name and a colored identity gem.
      ctx.font = "13px 'Cozette', monospace";
      const job = ROLE_TITLES[player.role];
      const suffix = job ? ` · ${job}` : self ? " · вы" : player.bot ? " · дух" : "";
      const displayName = `${player.name}${suffix}`.toUpperCase();
      ctx.lineWidth = 3;
      ctx.strokeStyle = "rgba(3, 4, 8, 0.9)";
      ctx.strokeText(displayName, screenX, nameY);
      ctx.fillStyle = self ? GOLD : "rgba(233, 227, 211, 0.9)";
      ctx.fillText(displayName, screenX, nameY);

      ctx.fillStyle = "rgba(4, 6, 10, 0.85)";
      ctx.fillRect(screenX - barWidth / 2, barY, barWidth, 5);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.16)";
      ctx.lineWidth = 1;
      ctx.strokeRect(screenX - barWidth / 2 + 0.5, barY + 0.5, barWidth - 1, 4);
      const hpGradient = ctx.createLinearGradient(
        screenX - barWidth / 2,
        0,
        screenX + barWidth / 2,
        0,
      );
      hpGradient.addColorStop(0, self ? "#a98242" : "rgba(194, 80, 89, 0.92)");
      hpGradient.addColorStop(1, self ? "#f1d493" : "rgba(233, 113, 117, 0.9)");
      ctx.fillStyle = hpGradient;
      ctx.fillRect(
        screenX - barWidth / 2 + 1,
        barY + 1,
        Math.max(0.5, ((barWidth - 2) * hp) / 100),
        3,
      );

      if (player.shield > 0) {
        ctx.strokeStyle = "rgba(146, 205, 255, 0.8)";
        ctx.lineWidth = 1;
        ctx.strokeRect(screenX - barWidth / 2 - 1.5, barY - 1.5, barWidth + 3, 8);
      }

      const speech = this.speeches.find((item) => item.id === player.id);
      if (speech) {
        this.drawSpeechBubble(ctx, speech, screenX, nameY - 10);
      }

      if (self) {
        ctx.fillStyle = "rgba(217, 181, 108, 0.7)";
        ctx.beginPath();
        ctx.arc(screenX - ctx.measureText(displayName).width / 2 - 7, nameY - 3, 1.7, 0, TAU);
        ctx.fill();
      }
      void visual;
      void now;
    }
    ctx.restore();
  }

  drawSpeechBubble(ctx, speech, screenX, bottomY) {
    ctx.save();
    ctx.font = "13px 'Pixelify Sans', sans-serif";
    const lines = wrapText(ctx, speech.text, 200, 3);
    if (!lines.length) {
      ctx.restore();
      return;
    }
    const lineHeight = 16;
    const width =
      Math.max(...lines.map((line) => ctx.measureText(line).width)) + 20;
    const height = lines.length * lineHeight + 12;
    let x = clamp(screenX - width / 2, 8, this.width - width - 8);
    let y = bottomY - height - 8;
    const alpha = clamp(speech.life / 0.4, 0, 1);
    ctx.globalAlpha = alpha;
    ctx.fillStyle = "rgba(8, 10, 17, 0.9)";
    ctx.strokeStyle = "rgba(217, 181, 108, 0.34)";
    ctx.lineWidth = 1;
    roundedRectPath(ctx, x, y, width, height, 3);
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(screenX - 4, y + height);
    ctx.lineTo(screenX, y + height + 6);
    ctx.lineTo(screenX + 4, y + height);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = "rgba(239, 230, 211, 0.9)";
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    lines.forEach((line, index) => {
      ctx.fillText(line, x + 10, y + 7 + index * lineHeight);
    });
    ctx.restore();
  }

  drawFloaties(ctx) {
    if (!this.floaters.length) return;
    ctx.save();
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const floater of this.floaters) {
      const progress = 1 - floater.life / floater.maxLife;
      const point = this.worldToScreen(floater.x, floater.y);
      const rise = 8 + progress * 27;
      const alpha = clamp(floater.life / 0.35, 0, 1);
      ctx.font = `600 ${floater.size}px 'Pixelify Sans', sans-serif`;
      ctx.lineWidth = 3;
      ctx.strokeStyle = `rgba(3, 4, 8, ${alpha * 0.7})`;
      ctx.strokeText(floater.text, point.x + floater.drift * progress, point.y - rise);
      ctx.fillStyle = rgba(floater.color, alpha);
      ctx.fillText(floater.text, point.x + floater.drift * progress, point.y - rise);
    }
    ctx.restore();
  }

  drawOffscreenTargets(ctx, client) {
    if (!client.joined || !client.selfId) return;
    const self = client.players.get(client.selfId);
    if (!self || self.dead) return;
    const cx = this.width / 2;
    const cy = this.height / 2;
    const margin = 27;
    ctx.save();
    for (const player of client.players.values()) {
      if (player.id === client.selfId || player.dead) continue;
      const screen = this.worldToScreen(player.x, player.y);
      if (
        screen.x > -16 &&
        screen.x < this.width + 16 &&
        screen.y > -16 &&
        screen.y < this.height + 16
      ) {
        continue;
      }
      const dx = screen.x - cx;
      const dy = screen.y - cy;
      if (!dx && !dy) continue;
      const scale = Math.min(
        Math.abs(dx) > 0 ? (this.width / 2 - margin) / Math.abs(dx) : Infinity,
        Math.abs(dy) > 0 ? (this.height / 2 - margin) / Math.abs(dy) : Infinity,
      );
      const x = cx + dx * scale;
      const y = cy + dy * scale;
      const angle = Math.atan2(dy, dx);
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(angle);
      ctx.fillStyle = rgba(player.color || VIOLET, 0.55);
      ctx.beginPath();
      ctx.moveTo(7, 0);
      ctx.lineTo(-4, -4);
      ctx.lineTo(-2, 0);
      ctx.lineTo(-4, 4);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }
    ctx.restore();
  }

  drawAim(ctx, client, now) {
    const pointer = client.pointer;
    if (!pointer || !client.joined) return;

    if (pointer.touch && pointer.joy) {
      const joy = pointer.joy;
      ctx.save();
      ctx.strokeStyle = "rgba(217, 181, 108, 0.28)";
      ctx.fillStyle = "rgba(8, 10, 17, 0.45)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(joy.originX, joy.originY, 52, 0, TAU);
      ctx.fill();
      ctx.stroke();
      ctx.strokeStyle = "rgba(169, 151, 255, 0.18)";
      ctx.beginPath();
      ctx.arc(joy.originX, joy.originY, 33, 0, TAU);
      ctx.stroke();
      const knobX = joy.originX + joy.dx * 37;
      const knobY = joy.originY + joy.dy * 37;
      const knob = ctx.createRadialGradient(knobX, knobY, 0, knobX, knobY, 19);
      knob.addColorStop(0, "rgba(244, 217, 155, 0.34)");
      knob.addColorStop(1, "rgba(217, 181, 108, 0.06)");
      ctx.fillStyle = knob;
      ctx.beginPath();
      ctx.arc(knobX, knobY, 19, 0, TAU);
      ctx.fill();
      ctx.strokeStyle = "rgba(244, 217, 155, 0.52)";
      ctx.beginPath();
      ctx.arc(knobX, knobY, 19, 0, TAU);
      ctx.stroke();
      ctx.restore();
      return;
    }

    if (!pointer.inside) return;
    const t = now / 1000;
    const pulse = 1 + Math.sin(t * 3.2) * 0.08;
    const x = pointer.x;
    const y = pointer.y;

    const selfVisual = this.visualPlayers.get(client.selfId);
    if (selfVisual && !selfVisual.dead) {
      const selfScreen = this.worldToScreen(selfVisual.x, selfVisual.y);
      const aim = client.aim || 0;
      for (let index = 0; index < 5; index += 1) {
        const distance = 31 + index * 13;
        const alpha = 0.22 - index * 0.03;
        ctx.fillStyle = `rgba(244, 217, 155, ${alpha})`;
        ctx.beginPath();
        ctx.arc(
          selfScreen.x + Math.cos(aim) * distance,
          selfScreen.y + Math.sin(aim) * distance,
          1.1,
          0,
          TAU,
        );
        ctx.fill();
      }
    }

    ctx.save();
    ctx.translate(x, y);
    ctx.strokeStyle = "rgba(244, 217, 155, 0.74)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(0, 0, 9 * pulse, 0, TAU);
    ctx.stroke();
    ctx.strokeStyle = "rgba(169, 151, 255, 0.42)";
    ctx.rotate(t * 0.5);
    ctx.setLineDash([3, 6]);
    ctx.beginPath();
    ctx.arc(0, 0, 15, 0, TAU);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.strokeStyle = "rgba(244, 217, 155, 0.64)";
    for (let index = 0; index < 4; index += 1) {
      ctx.save();
      ctx.rotate(index * (Math.PI / 2));
      ctx.beginPath();
      ctx.moveTo(11, 0);
      ctx.lineTo(15, 0);
      ctx.stroke();
      ctx.restore();
    }
    ctx.fillStyle = "rgba(255, 247, 222, 0.92)";
    ctx.beginPath();
    ctx.arc(0, 0, 1.35, 0, TAU);
    ctx.fill();
    ctx.restore();
  }
}

