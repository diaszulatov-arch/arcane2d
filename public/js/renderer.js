/* Canvas renderer: camera, mages, projectiles, wards, particles and HUD overlays. */

import {
  OBSTACLE_HEIGHT,
  buildFloorCanvas,
  collectWorldLights,
  drawAmbient,
  drawArenaBorder,
  drawObstacle,
  drawWallTorches,
} from "./world-art.js";

const TAU = Math.PI * 2;
const GOLD = "#d9b56c";
const VIOLET = "#a997ff";
const EMP_COLOR = "#b38cff";

// What a stone looks like with no light on it: the room is dim, not black, so
// nothing a player must read ever disappears.
const AMBIENT_LIGHT = "#6d6682";
const SELF_LIGHT = "#ffe6c4";
const LIGHT_SPRITE_SIZE = 96;
const BLOOM_STRENGTH = 0.42;
// Blasts open on the floor and mages stand over them, so a fight never hides them.
const GROUND_EFFECTS = new Set(["scorch", "explosion", "nova"]);
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
    this.visualProjectiles = new Map();
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

  ensureFloor(config) {
    const width = config?.arena?.w || 1900;
    const height = config?.arena?.h || 1100;
    const border = config?.arena?.border || 46;
    const key = `${width}x${height}x${border}`;
    if (key !== this.floorKey) {
      this.floorCanvas = buildFloorCanvas(config);
      this.floorKey = key;
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
      visual.moving = moved > 0.25;
      visual.step = (visual.step || 0) + Math.min(0.55, moved * 0.11);
      visual.hurt = Math.max(0, visual.hurt - dt);
      visual.cast = Math.max(0, visual.cast - dt);
      visual.roll = Math.max(0, (visual.roll || 0) - dt);
      visual.stunFlash = Math.max(0, (visual.stunFlash || 0) - dt);
      visual.dead = player.dead;
    }
    for (const id of this.visualPlayers.keys()) {
      if (!seen.has(id)) this.visualPlayers.delete(id);
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
      life: element === "frost" ? 0.72 : 0.88,
      age: 0,
    });
    this.effects.push({
      kind: "scorch",
      x,
      y,
      color,
      element,
      scale,
      life: element === "frost" ? 1.7 : 2.4,
      age: 0,
    });
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
        this.burst(event.x, event.y, color, 20, 170, {
          size: 2.8,
          life: 0.58,
          angle: null,
        });
        this.addRing(event.x, event.y, 4, 30, color, 0.36, 2.2);
        const visual = this.visualPlayers.get(event.id);
        if (visual) visual.cast = 0.4;
        break;
      }
      case "impact": {
        const shard = event.kind === "frost";
        const spark = event.kind === "spark";
        this.addExplosion(
          event.x,
          event.y,
          color,
          shard ? "frost" : "fire",
          spark ? 0.62 : shard ? 1.12 : 1.45,
        );
        this.burst(event.x, event.y, color, spark ? 18 : shard ? 34 : 40, 265, {
          size: spark ? 2.1 : shard ? 2.7 : 3.4,
          life: spark ? 0.48 : 0.72,
          kind: shard ? "shard" : "ember",
        });
        this.burst(event.x, event.y, "#fff4dc", spark ? 8 : 14, 160, {
          size: spark ? 1.4 : 1.8,
          life: 0.42,
          kind: "spark",
        });
        this.addRing(
          event.x,
          event.y,
          5,
          spark ? 28 : shard ? 52 : 66,
          color,
          spark ? 0.3 : 0.42,
          spark ? 1.8 : 2.8,
        );
        this.addRing(
          event.x,
          event.y,
          2,
          spark ? 18 : shard ? 30 : 38,
          "#ffffff",
          spark ? 0.22 : 0.28,
          1.2,
        );
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
        this.burst(event.x, event.y, color, 12, 140, {
          size: 2,
          life: 0.45,
          kind: "spark",
        });
        this.burst(event.x, event.y, "#ffe2c2", 5, 70, {
          size: 1,
          life: 0.28,
          kind: "ember",
        });
        const hitVisual = this.visualPlayers.get(event.id);
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
        this.addLine(
          event.x,
          event.y,
          event.x2,
          event.y2,
          rollColor,
          0.34,
          5,
        );
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
    applyCamera(worldCtx);
    if (this.floorCanvas) {
      worldCtx.drawImage(this.floorCanvas, 0, 0);
    }
    drawAmbient(worldCtx, client.config, now, zoom);
    this.drawEffects(worldCtx, now, zoom, true);
    drawArenaBorder(worldCtx, client.config, now, zoom);
    drawWallTorches(worldCtx, client.config, now);
    this.drawScene(worldCtx, client, now, zoom, labels);
    if (this.quality >= QUALITY_LIGHTS) {
      this.applyLighting(client, now, applyCamera);
    }

    // What gives light off: magic stays at full brightness on top of the room.
    applyCamera(worldCtx);
    this.drawWards(worldCtx, client, now, zoom);
    this.drawEmps(worldCtx, client, now, zoom);
    this.drawClouds(worldCtx, client, now, zoom);
    this.drawMeteors(worldCtx, client, now, zoom);
    this.drawEffects(worldCtx, now, zoom, false);
    this.drawProjectiles(worldCtx, now, zoom);
    this.drawParticles(worldCtx, now, zoom);
    worldCtx.setTransform(1, 0, 0, 1, 0, 0);
    if (this.quality >= QUALITY_FULL) this.drawBloom(worldCtx);

    const ctx = this.ctx;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(this.worldCanvas, 0, 0, this.width, this.height);
    ctx.imageSmoothingEnabled = true;

    this.drawNameplates(ctx, labels, client, now);
    this.drawFloaties(ctx);
    this.drawOffscreenTargets(ctx, client);
    this.drawAim(ctx, client, now);

    this.drawFrameVignette(ctx);
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
    collectWorldLights(client.config, now, lights);

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
      const radius = kind === "fire" ? 260 : kind === "frost" ? 190 : 130;
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
  applyLighting(client, now, applyCamera) {
    const ctx = this.lightCtx;
    this.collectLights(client, now);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
    ctx.fillStyle = AMBIENT_LIGHT;
    ctx.fillRect(0, 0, this.lightCanvas.width, this.lightCanvas.height);

    applyCamera(ctx);
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
    scene.sort((a, b) => a.depth - b.depth);
    for (const { obstacle, visual } of scene) {
      if (obstacle) drawObstacle(ctx, obstacle, now, this.obstacleAlpha(obstacle, self));
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

    const aim = visual.aim || 0;
    const dx = Math.cos(aim);
    const dy = Math.sin(aim);
    const sideX = Math.cos(aim + Math.PI / 2);
    const sideY = Math.sin(aim + Math.PI / 2);

    // Pixel-art staff, held toward the aim direction.
    const staffBaseX = sideX * 7;
    const staffBaseY = sideY * 7;
    const tipX = dx * 34 + sideX * 3;
    const tipY = dy * 34 + sideY * 3;
    ctx.lineCap = "butt";
    ctx.strokeStyle = "#120d18";
    ctx.lineWidth = 4.6;
    ctx.beginPath();
    ctx.moveTo(staffBaseX, staffBaseY);
    ctx.lineTo(tipX, tipY);
    ctx.stroke();
    ctx.strokeStyle = "#6f4b2c";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(staffBaseX, staffBaseY);
    ctx.lineTo(tipX, tipY);
    ctx.stroke();
    ctx.strokeStyle = "#c19158";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(staffBaseX, staffBaseY);
    ctx.lineTo(tipX, tipY);
    ctx.stroke();
    ctx.globalCompositeOperation = "lighter";
    const orbGlow = ctx.createRadialGradient(tipX, tipY, 0, tipX, tipY, 12);
    orbGlow.addColorStop(0, rgba(color, 0.95));
    orbGlow.addColorStop(0.28, rgba(color, 0.42));
    orbGlow.addColorStop(1, rgba(color, 0));
    ctx.fillStyle = orbGlow;
    ctx.beginPath();
    ctx.arc(tipX, tipY, 12, 0, TAU);
    ctx.fill();
    ctx.fillStyle = "#fff7df";
    ctx.fillRect(tipX - 2.6, tipY - 2.6, 5.2, 5.2);
    ctx.globalCompositeOperation = "source-over";

    this.drawPixelWizard(ctx, visual, color, t, zoom);
    ctx.lineCap = "round";

    if (player.shield > 0) {
      const strength = clamp(player.shield / 38, 0.2, 1);
      const shieldPulse = 0.72 + Math.sin(t * 2.8 + player.id) * 0.12;
      const bubble = 47;
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = `rgba(105, 178, 246, ${0.035 + strength * 0.045})`;
      ctx.beginPath();
      ctx.arc(0, 0, bubble, 0, TAU);
      ctx.fill();
      ctx.strokeStyle = `rgba(154, 214, 255, ${0.36 * strength * shieldPulse})`;
      ctx.lineWidth = 1.8 / zoom;
      ctx.beginPath();
      ctx.arc(0, 0, bubble, 0, TAU);
      ctx.stroke();
      ctx.strokeStyle = `rgba(199, 238, 255, ${0.42 * strength})`;
      ctx.lineWidth = 1 / zoom;
      for (let index = 0; index < 4; index += 1) {
        ctx.beginPath();
        ctx.arc(0, 0, bubble, index * 1.57 + t * 0.35, index * 1.57 + 0.58 + t * 0.35);
        ctx.stroke();
      }
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

  drawPixelWizard(ctx, visual, color, t, zoom) {
    const P = 3;
    const left = -8 * P;
    const top = 8 - 20 * P;
    const bob = visual.moving ? Math.sin(visual.step * 2) * 1.1 : 0;
    const outline = "#0a0711";
    const skin = "#e4a86f";
    const skinLight = "#ffd09a";
    const beard = "#d5cfdd";
    const beardDark = "#a79eb8";
    const gold = "#f3d27f";
    const robe = mixHex("#422b6e", color, 0.05);
    const robeLight = mixHex("#5a3e92", color, 0.08);
    const robeDark = "#211531";
    const hat = color;
    const hatLight = mixHex(color, "#ffffff", 0.34);
    const hatDark = mixHex(color, "#000000", 0.36);

    const block = (col, row, width, height, fill, withOutline = true) => {
      const x = left + col * P;
      const y = top + row * P + bob;
      const w = width * P;
      const h = height * P;
      if (withOutline) {
        ctx.fillStyle = outline;
        ctx.fillRect(x - 0.8, y - 0.8, w + 1.6, h + 1.6);
      }
      ctx.fillStyle = fill;
      ctx.fillRect(x, y, w, h);
    };

    // Robe, tattered hem and belt.
    block(3, 14, 10, 3, robeDark);
    block(2, 17, 4, 3, robeDark);
    block(4, 17, 8, 3, robe);
    block(11, 17, 3, 2, robeDark);
    block(4, 17, 2, 3, robeLight, false);
    block(4, 10, 8, 4, robe);
    block(4, 10, 2, 4, robeLight, false);
    block(4, 13, 8, 1, gold);
    block(7, 13, 2, 1, "#fff2b6", false);
    block(8, 15, 1, 1, gold, false);
    block(5, 16, 1, 1, gold, false);
    block(10, 15, 1, 1, mixHex(color, "#ffffff", 0.15), false);
    block(4, 19, 8, 1, "#b98b4a", false);

    // A five-pixel star on the chest.
    block(8, 11, 1, 1, gold, false);
    block(7, 11, 1, 1, gold, false);
    block(9, 11, 1, 1, gold, false);
    block(8, 10, 1, 1, gold, false);
    block(8, 12, 1, 1, gold, false);

    // Arms and hands.
    block(1, 11, 3, 3, robe);
    block(1, 13, 2, 2, skin);
    block(12, 11, 3, 3, robe);
    block(13, 13, 2, 2, skin);

    // Head and beard.
    block(5, 7, 6, 4, skin);
    block(6, 8, 1, 1, "#3a2433", false);
    block(9, 8, 1, 1, "#3a2433", false);
    block(8, 8, 1, 1, skinLight, false);
    block(5, 10, 6, 1, beard);
    block(6, 11, 4, 1, beard);
    block(7, 12, 2, 1, beardDark);

    // Crooked hat with a broad brim and gold stars.
    block(2, 6, 12, 2, hatDark);
    block(3, 6, 10, 1, hat);
    block(4, 5, 8, 1, gold);
    block(5, 4, 6, 1, hat);
    block(6, 3, 5, 1, hat);
    block(7, 2, 4, 1, hat);
    block(8, 1, 4, 1, hat);
    block(10, 0, 3, 1, hatDark);
    block(5, 4, 2, 1, hatLight, false);
    block(6, 3, 2, 1, hatLight, false);
    block(8, 2, 1, 1, "#ffe17a", false);
    block(10, 4, 1, 1, "#ffe17a", false);
    block(6, 5, 1, 1, "#fff2b6", false);

    // A tiny spark circling the hat tip.
    const sparkle = t * 1.8 + visual.data.id;
    const sx = Math.cos(sparkle) * 4;
    const sy = top - 10 + Math.sin(sparkle * 1.3) * 3;
    ctx.fillStyle = rgba(hatLight, 0.9);
    ctx.fillRect(sx - 1.2, sy - 1.2, 2.4, 2.4);
    ctx.fillStyle = rgba("#ffffff", 0.8);
    ctx.fillRect(sx - 0.5, sy - 0.5, 1, 1);
  }

  drawProjectiles(ctx, now, zoom) {
    const t = now / 1000;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const visual of this.visualProjectiles.values()) {
      const projectile = visual.data;
      const isFrost = projectile.kind === "frost";
      const isSpark = projectile.kind === "spark";
      const baseColor =
        projectile.color || (isSpark ? "#ffe17a" : isFrost ? "#7ce7ff" : "#ff9a4d");
      const trail = visual.trail;
      for (let index = 0; index < trail.length; index += 1) {
        const point = trail[index];
        const progress = index / trail.length;
        const radius = (isSpark ? 4.5 : isFrost ? 6 : 14) * (0.2 + progress * 0.9);
        ctx.fillStyle = rgba(
          baseColor,
          progress * (isSpark || isFrost ? 0.28 : 0.22),
        );
        ctx.beginPath();
        ctx.arc(point.x, point.y, radius, 0, TAU);
        ctx.fill();
        if (progress > 0.55) {
          ctx.fillStyle = rgba("#fff4dc", (progress - 0.55) * 0.4);
          ctx.beginPath();
          ctx.arc(point.x, point.y, radius * 0.38, 0, TAU);
          ctx.fill();
        }
      }

      const x = visual.x;
      const y = visual.y;
      const flicker = isFrost || isSpark
        ? 0.94 + Math.sin(t * 17 + projectile.id) * 0.06
        : 1 + Math.sin(t * 23 + projectile.id * 1.7) * 0.09;
      const haloRadius = (isSpark ? 36 : isFrost ? 46 : 72) * flicker;

      const glow = ctx.createRadialGradient(x, y, 0, x, y, haloRadius);
      glow.addColorStop(0, rgba(baseColor, isSpark ? 0.96 : isFrost ? 0.92 : 0.88));
      glow.addColorStop(0.16, rgba(baseColor, 0.72));
      glow.addColorStop(0.42, rgba(baseColor, 0.3));
      glow.addColorStop(0.72, rgba(baseColor, 0.1));
      glow.addColorStop(1, rgba(baseColor, 0));
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(x, y, haloRadius, 0, TAU);
      ctx.fill();

      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(visual.angle);
      if (isSpark) {
        ctx.fillStyle = rgba(baseColor, 0.3);
        ctx.beginPath();
        ctx.ellipse(-7, 0, 18, 5.5, 0, 0, TAU);
        ctx.fill();
        starPath(ctx, 0, 0, 4, 12, 3.4, 0);
        ctx.fillStyle = rgba(baseColor, 0.92);
        ctx.fill();
        starPath(ctx, 0, 0, 4, 7, 2.1, Math.PI / 4);
        ctx.fillStyle = "rgba(255, 252, 224, 0.94)";
        ctx.fill();
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(0, 0, 2.8, 0, TAU);
        ctx.fill();
      } else if (isFrost) {
        ctx.fillStyle = "rgba(124, 231, 255, 0.3)";
        ctx.beginPath();
        ctx.arc(0, 0, 21, 0, TAU);
        ctx.fill();
        for (const side of [-1, 1]) {
          ctx.save();
          ctx.rotate(side * 0.5);
          ctx.fillStyle = "rgba(214, 251, 255, 0.8)";
          ctx.beginPath();
          ctx.moveTo(7, 0);
          ctx.lineTo(-12, 4.5);
          ctx.lineTo(-7, 0);
          ctx.lineTo(-12, -4.5);
          ctx.closePath();
          ctx.fill();
          ctx.restore();
        }
        ctx.fillStyle = "#d6fbff";
        ctx.beginPath();
        ctx.moveTo(16, 0);
        ctx.lineTo(-8, 8.5);
        ctx.lineTo(-4, 0);
        ctx.lineTo(-8, -8.5);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = "rgba(255, 255, 255, 0.9)";
        ctx.lineWidth = 1.3 / zoom;
        ctx.beginPath();
        ctx.moveTo(10, 0);
        ctx.lineTo(-2, 0);
        ctx.stroke();
      } else {
        for (let index = 0; index < 10; index += 1) {
          const angle = (index / 10) * TAU + t * 0.9;
          const distance = 14 + Math.sin(t * 11 + index * 1.9) * 5;
          const radius = 6.5 + Math.sin(t * 9 + index) * 2.6;
          ctx.fillStyle = rgba(index % 2 === 0 ? "#ffd27a" : baseColor, 0.2);
          ctx.beginPath();
          ctx.arc(
            Math.cos(angle) * distance,
            Math.sin(angle) * distance,
            radius,
            0,
            TAU,
          );
          ctx.fill();
        }
        const body = ctx.createRadialGradient(-2, -3, 1, 0, 0, 19);
        body.addColorStop(0, "#fffbe5");
        body.addColorStop(0.18, "#ffe19a");
        body.addColorStop(0.55, "#ff9a3d");
        body.addColorStop(1, "#d93c1f");
        ctx.fillStyle = body;
        ctx.beginPath();
        ctx.arc(0, 0, 17.5, 0, TAU);
        ctx.fill();
        ctx.fillStyle = "rgba(255, 255, 255, 0.92)";
        ctx.beginPath();
        ctx.arc(-1.5, -2.5, 6.5, 0, TAU);
        ctx.fill();
      }
      ctx.restore();
    }
    ctx.restore();
  }

  drawWards(ctx, client, now, zoom) {
    const t = now / 1000;
    for (const ward of client.wards) {
      const armed = Boolean(ward.armed);
      const pulse = 0.5 + Math.sin(t * 2.6 + ward.id) * 0.5;
      const alpha = armed ? 0.68 : 0.28;
      ctx.save();
      ctx.translate(ward.x, ward.y);

      ctx.strokeStyle = `rgba(169, 151, 255, ${0.1 + pulse * 0.05})`;
      ctx.lineWidth = 0.8 / zoom;
      ctx.setLineDash([3, 8]);
      ctx.beginPath();
      ctx.arc(0, 0, 38, 0, TAU);
      ctx.stroke();
      ctx.setLineDash([]);

      const glow = ctx.createRadialGradient(0, 0, 1, 0, 0, 23);
      glow.addColorStop(0, `rgba(173, 143, 255, ${armed ? 0.26 : 0.12})`);
      glow.addColorStop(1, "rgba(173, 143, 255, 0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(0, 0, 23, 0, TAU);
      ctx.fill();

      ctx.rotate(t * (armed ? 0.28 : 0.1) + ward.id);
      ctx.strokeStyle = `rgba(217, 181, 108, ${alpha})`;
      ctx.lineWidth = 1.1 / zoom;
      ctx.beginPath();
      ctx.arc(0, 0, 14, 0, TAU);
      ctx.stroke();
      ctx.beginPath();
      for (let index = 0; index < 6; index += 1) {
        const angle = (index / 6) * TAU;
        const x = Math.cos(angle) * 14;
        const y = Math.sin(angle) * 14;
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = `rgba(169, 151, 255, ${alpha * 0.8})`;
      ctx.stroke();
      starPath(ctx, 0, 0, 3, 9, 3.2, -Math.PI / 2);
      ctx.fillStyle = `rgba(244, 217, 155, ${armed ? 0.34 : 0.13})`;
      ctx.fill();
      ctx.restore();

      if (armed) {
        ctx.strokeStyle = `rgba(169, 151, 255, ${0.16 + pulse * 0.12})`;
        ctx.lineWidth = 0.9 / zoom;
        ctx.beginPath();
        ctx.arc(ward.x, ward.y, 21 + pulse * 4, 0, TAU);
        ctx.stroke();
      }
      if (ward.ttl < 2.4) {
        ctx.fillStyle = `rgba(255, 140, 130, ${0.45 + pulse * 0.4})`;
        ctx.beginPath();
        ctx.arc(ward.x + 16, ward.y - 15, 1.5, 0, TAU);
        ctx.fill();
      }
    }
  }

  drawEmps(ctx, client, now, zoom) {
    const t = now / 1000;
    const emps = Array.isArray(client.emps) ? client.emps : [];
    for (const emp of emps) {
      const radius = Number(emp.radius) || 190;
      const delay = Math.max(0.1, Number(emp.delay) || 1.5);
      const ttl = Math.max(0, Number(emp.ttl) || 0);
      const pullTtl = Math.max(0, Number(emp.pull_ttl) || 0);
      const pulled = pullTtl <= 0.001;
      const progress = clamp(1 - ttl / delay, 0, 1);
      const pulse = 0.5 + Math.sin(t * 7.2 + emp.id) * 0.5;
      const color = emp.color || EMP_COLOR;
      ctx.save();
      ctx.translate(emp.x, emp.y);

      ctx.strokeStyle = rgba(color, 0.2 + progress * 0.38);
      ctx.lineWidth = (1.2 + progress * 0.8) / zoom;
      ctx.setLineDash([4, 7]);
      ctx.beginPath();
      ctx.arc(0, 0, radius, 0, TAU);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.strokeStyle = rgba(color, 0.32 + pulse * 0.18);
      ctx.lineWidth = 0.9 / zoom;
      ctx.beginPath();
      ctx.arc(0, 0, radius * (0.62 + progress * 0.3), 0, TAU);
      ctx.stroke();

      const orbRadius = 12 + progress * 12 + pulse * 2.2;
      const glow = ctx.createRadialGradient(0, 0, 0, 0, 0, orbRadius * 3.4);
      glow.addColorStop(0, rgba("#f0e8ff", 0.72 + progress * 0.2));
      glow.addColorStop(0.22, rgba(color, 0.55));
      glow.addColorStop(0.58, rgba(color, 0.2));
      glow.addColorStop(1, rgba(color, 0));
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(0, 0, orbRadius * 3.4, 0, TAU);
      ctx.fill();

      ctx.fillStyle = rgba("#f7f1ff", 0.86);
      ctx.beginPath();
      ctx.arc(0, 0, orbRadius, 0, TAU);
      ctx.fill();
      ctx.fillStyle = rgba(color, 0.42 + pulse * 0.2);
      ctx.beginPath();
      ctx.arc(0, 0, orbRadius * 1.45, 0, TAU);
      ctx.fill();

      if (pulled) {
        ctx.strokeStyle = rgba("#f1e9ff", 0.34 + pulse * 0.28);
        ctx.lineWidth = 1.5 / zoom;
        for (let index = 0; index < 8; index += 1) {
          const angle = (index / 8) * TAU + t * 0.8;
          const outer = radius * (0.48 + pulse * 0.1);
          const inner = 18;
          ctx.beginPath();
          ctx.moveTo(Math.cos(angle) * outer, Math.sin(angle) * outer);
          ctx.lineTo(Math.cos(angle) * inner, Math.sin(angle) * inner);
          ctx.stroke();
          ctx.fillStyle = rgba("#f6efff", 0.42 + pulse * 0.3);
          ctx.beginPath();
          ctx.arc(Math.cos(angle) * 11, Math.sin(angle) * 11, 1.6, 0, TAU);
          ctx.fill();
        }
      }

      ctx.rotate(t * (0.8 + progress * 1.8) + emp.id * 0.4);
      ctx.strokeStyle = rgba(color, 0.42 + progress * 0.32);
      ctx.lineWidth = 1.5 / zoom;
      for (let index = 0; index < 4; index += 1) {
        const start = (index / 4) * TAU;
        ctx.beginPath();
        ctx.arc(0, 0, radius * (0.38 + index * 0.1), start, start + 0.5);
        ctx.stroke();
      }

      for (let index = 0; index < 10; index += 1) {
        const angle = (index / 10) * TAU + t * 0.35;
        const outer = radius * (0.72 + Math.sin(t * 3 + index) * 0.04);
        const inner = outer - 18 - progress * 22;
        ctx.strokeStyle = rgba(index % 2 === 0 ? "#f0e8ff" : color, 0.28 + progress * 0.4);
        ctx.lineWidth = 1 / zoom;
        ctx.beginPath();
        ctx.moveTo(Math.cos(angle) * outer, Math.sin(angle) * outer);
        ctx.lineTo(Math.cos(angle) * inner, Math.sin(angle) * inner);
        ctx.stroke();
      }
      ctx.restore();
    }
  }

  drawClouds(ctx, client, now, zoom) {
    const t = now / 1000;
    const clouds = Array.isArray(client.clouds) ? client.clouds : [];
    for (const cloud of clouds) {
      const radius = Number(cloud.radius) || 110;
      const color = cloud.color || "#86e08a";
      const pulse = 0.5 + Math.sin(t * 2.2 + cloud.id) * 0.5;
      const ttl = Math.max(0, Number(cloud.ttl) || 0);
      const fade = clamp(ttl / 1.2, 0, 1);
      ctx.save();
      ctx.translate(cloud.x, cloud.y);
      ctx.globalCompositeOperation = "source-over";

      const haze = ctx.createRadialGradient(0, 0, radius * 0.08, 0, 0, radius);
      haze.addColorStop(0, rgba(color, 0.16 * fade));
      haze.addColorStop(0.58, rgba(color, 0.11 * fade));
      haze.addColorStop(1, rgba(color, 0));
      ctx.fillStyle = haze;
      ctx.beginPath();
      ctx.arc(0, 0, radius, 0, TAU);
      ctx.fill();

      for (let index = 0; index < 9; index += 1) {
        const angle =
          (index / 9) * TAU + t * (0.1 + (index % 3) * 0.025) + cloud.id * 0.7;
        const orbit = radius * (0.28 + (index % 4) * 0.11);
        const puff = radius * (0.24 + ((index * 5) % 4) * 0.035);
        const x = Math.cos(angle) * orbit;
        const y = Math.sin(angle * 0.85) * orbit * 0.55;
        const puffGradient = ctx.createRadialGradient(x, y, 0, x, y, puff);
        puffGradient.addColorStop(
          0,
          rgba(index % 2 === 0 ? "#c8ffd2" : color, (0.13 + pulse * 0.05) * fade),
        );
        puffGradient.addColorStop(1, rgba(color, 0));
        ctx.fillStyle = puffGradient;
        ctx.beginPath();
        ctx.arc(x, y, puff, 0, TAU);
        ctx.fill();
      }

      ctx.strokeStyle = rgba(color, 0.18 + pulse * 0.12);
      ctx.lineWidth = 1 / zoom;
      ctx.setLineDash([3, 8]);
      ctx.beginPath();
      ctx.arc(0, 0, radius, 0, TAU);
      ctx.stroke();
      ctx.setLineDash([]);

      for (let index = 0; index < 6; index += 1) {
        const angle = (index / 6) * TAU + t * 0.4;
        const drift = radius * (0.35 + Math.sin(t * 1.6 + index) * 0.2);
        ctx.fillStyle = rgba("#d5ffc9", 0.3 * fade);
        ctx.beginPath();
        ctx.arc(
          Math.cos(angle) * drift,
          Math.sin(angle) * drift * 0.6,
          1.5 + Math.sin(t * 2 + index) * 0.6,
          0,
          TAU,
        );
        ctx.fill();
      }
      ctx.restore();
    }
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

      const danger = ctx.createRadialGradient(0, 0, 0, 0, 0, radius);
      danger.addColorStop(
        0,
        rgba(color, (0.05 + progress * 0.1) * strength),
      );
      danger.addColorStop(
        0.72,
        rgba(color, (0.08 + progress * 0.14) * strength),
      );
      danger.addColorStop(1, rgba(color, 0));
      ctx.fillStyle = danger;
      ctx.beginPath();
      ctx.arc(0, 0, radius, 0, TAU);
      ctx.fill();

      ctx.strokeStyle = rgba(
        color,
        (0.3 + progress * 0.42) * strength,
      );
      ctx.lineWidth = (1.2 + progress * 1.2) / zoom;
      ctx.setLineDash([4, 7]);
      ctx.beginPath();
      ctx.arc(0, 0, radius, 0, TAU);
      ctx.stroke();
      ctx.setLineDash([]);

      if (isMain) {
        ctx.strokeStyle = rgba(color, 0.22 + pulse * 0.2);
        ctx.lineWidth = 0.9 / zoom;
        ctx.beginPath();
        ctx.arc(0, 0, radius * (0.54 + progress * 0.22), 0, TAU);
        ctx.stroke();
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
    ctx.globalCompositeOperation = "lighter";
    for (const effect of this.effects) {
      if (GROUND_EFFECTS.has(effect.kind) !== onGround) continue;
      const progress = clamp(effect.age / effect.life, 0, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const alpha = 1 - progress;
      if (effect.kind === "scorch") {
        const fade = 1 - progress;
        ctx.globalCompositeOperation = "source-over";
        const radius = (38 + progress * 18) * (effect.scale || 1);
        const scorch = ctx.createRadialGradient(
          effect.x,
          effect.y,
          0,
          effect.x,
          effect.y,
          radius,
        );
        if (effect.element === "frost") {
          scorch.addColorStop(0, `rgba(195, 247, 255, ${0.3 * fade})`);
          scorch.addColorStop(0.5, `rgba(94, 208, 255, ${0.14 * fade})`);
          scorch.addColorStop(1, "rgba(94, 208, 255, 0)");
        } else if (effect.element === "emp") {
          scorch.addColorStop(0, `rgba(220, 207, 255, ${0.32 * fade})`);
          scorch.addColorStop(0.45, `rgba(117, 82, 218, ${0.2 * fade})`);
          scorch.addColorStop(1, "rgba(45, 25, 95, 0)");
        } else {
          scorch.addColorStop(0, `rgba(255, 142, 65, ${0.32 * fade})`);
          scorch.addColorStop(0.45, `rgba(126, 54, 44, ${0.22 * fade})`);
          scorch.addColorStop(1, "rgba(40, 18, 20, 0)");
        }
        ctx.fillStyle = scorch;
        ctx.beginPath();
        ctx.arc(effect.x, effect.y, radius, 0, TAU);
        ctx.fill();
        ctx.globalCompositeOperation = "lighter";
      } else if (effect.kind === "beam") {
        const fade = 1 - progress;
        const x1 = effect.x1;
        const y1 = effect.y1;
        const x2 = effect.x2;
        const y2 = effect.y2;
        const width = effect.width * (0.8 + 0.2 * Math.sin(progress * Math.PI));
        ctx.lineCap = "square";
        const layers = [
          [width * 1.6, 0.08],
          [width, 0.16],
          [width * 0.55, 0.42],
          [width * 0.22, 0.9],
        ];
        for (const [lineWidth, layerAlpha] of layers) {
          ctx.strokeStyle = rgba(effect.color, fade * layerAlpha);
          ctx.lineWidth = lineWidth;
          ctx.beginPath();
          ctx.moveTo(x1, y1);
          ctx.lineTo(x2, y2);
          ctx.stroke();
        }
        ctx.strokeStyle = rgba("#ffffff", fade * 0.95);
        ctx.lineWidth = Math.max(1.5, width * 0.08);
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
        for (let index = 0; index < 7; index += 1) {
          const at = ((index / 7 + progress * 1.8) % 1) * 0.94 + 0.03;
          const px = x1 + (x2 - x1) * at;
          const py = y1 + (y2 - y1) * at;
          ctx.fillStyle = rgba("#ffffff", fade * 0.7);
          ctx.fillRect(px - width * 0.09, py - width * 0.09, width * 0.18, width * 0.18);
        }
        ctx.lineCap = "round";
      } else if (effect.kind === "explosion") {
        const scale = effect.scale || 1;
        const radius = (28 + eased * 72) * scale;
        const coreRadius = (16 + eased * 26) * scale;
        const flash = ctx.createRadialGradient(
          effect.x,
          effect.y,
          0,
          effect.x,
          effect.y,
          radius,
        );
        const hot = effect.element === "frost" ? "#e6fdff" : "#fff5d6";
        flash.addColorStop(0, rgba(hot, (1 - progress) * 0.72));
        flash.addColorStop(0.24, rgba(effect.color, (1 - progress) * 0.5));
        flash.addColorStop(0.56, rgba(effect.color, (1 - progress) * 0.18));
        flash.addColorStop(1, rgba(effect.color, 0));
        ctx.fillStyle = flash;
        ctx.beginPath();
        ctx.arc(effect.x, effect.y, radius, 0, TAU);
        ctx.fill();

        ctx.strokeStyle = rgba(effect.color, alpha * 0.9);
        ctx.lineWidth = 5.5 / zoom;
        ctx.beginPath();
        ctx.arc(effect.x, effect.y, coreRadius + 30 * eased, 0, TAU);
        ctx.stroke();
        ctx.strokeStyle = rgba(hot, alpha * 0.65);
        ctx.lineWidth = 2 / zoom;
        ctx.beginPath();
        ctx.arc(effect.x, effect.y, coreRadius + 52 * eased, 0, TAU);
        ctx.stroke();

        if (effect.element === "fire" || effect.element === "arcane") {
          const tongues = effect.element === "arcane" ? 10 : 8;
          ctx.fillStyle = rgba(effect.color, alpha * 0.34);
          for (let index = 0; index < tongues; index += 1) {
            const angle = (index / tongues) * TAU + progress * 0.8;
            const length = (16 + eased * 30) * scale;
            const ignite = Math.sin(Math.PI * progress) * 0.5 + 0.5;
            ctx.beginPath();
            ctx.arc(
              effect.x + Math.cos(angle) * radius * 0.58,
              effect.y + Math.sin(angle) * radius * 0.58,
              length * ignite,
              0,
              TAU,
            );
            ctx.fill();
          }
        }
      } else if (effect.kind === "ring") {
        const radius = effect.from + (effect.to - effect.from) * eased;
        if (radius <= 0) continue;
        ctx.strokeStyle = rgba(effect.color, alpha * 0.7);
        ctx.lineWidth = effect.width / zoom;
        ctx.beginPath();
        ctx.arc(effect.x, effect.y, radius, 0, TAU);
        ctx.stroke();
        if (effect.runes) {
          ctx.fillStyle = rgba(effect.color, alpha * 0.55);
          for (let index = 0; index < 8; index += 1) {
            const angle = (index / 8) * TAU + progress * 0.8;
            const x = effect.x + Math.cos(angle) * radius;
            const y = effect.y + Math.sin(angle) * radius;
            ctx.save();
            ctx.translate(x, y);
            ctx.rotate(angle + Math.PI / 2);
            ctx.fillRect(-0.7, -3, 1.4, 6);
            ctx.restore();
          }
        }
      } else if (effect.kind === "nova") {
        const radius = effect.radius * eased;
        ctx.strokeStyle = rgba(effect.color, alpha * 0.75);
        ctx.lineWidth = 3.2 / zoom;
        ctx.beginPath();
        ctx.arc(effect.x, effect.y, radius, 0, TAU);
        ctx.stroke();
        ctx.strokeStyle = rgba(effect.color, alpha * 0.28);
        ctx.lineWidth = 1.2 / zoom;
        ctx.beginPath();
        ctx.arc(effect.x, effect.y, radius * 0.72, 0, TAU);
        ctx.stroke();
        ctx.strokeStyle = rgba("#f4d99b", alpha * 0.35);
        for (let index = 0; index < 16; index += 1) {
          const angle = (index / 16) * TAU + progress * 0.9;
          ctx.beginPath();
          ctx.moveTo(
            effect.x + Math.cos(angle) * radius * 0.58,
            effect.y + Math.sin(angle) * radius * 0.58,
          );
          ctx.lineTo(
            effect.x + Math.cos(angle) * radius,
            effect.y + Math.sin(angle) * radius,
          );
          ctx.stroke();
        }
        const flash = ctx.createRadialGradient(
          effect.x,
          effect.y,
          0,
          effect.x,
          effect.y,
          Math.max(8, radius * 0.55),
        );
        flash.addColorStop(0, rgba(effect.color, alpha * 0.12));
        flash.addColorStop(1, rgba(effect.color, 0));
        ctx.fillStyle = flash;
        ctx.beginPath();
        ctx.arc(effect.x, effect.y, Math.max(8, radius * 0.55), 0, TAU);
        ctx.fill();
      } else if (effect.kind === "bolt") {
        const points = effect.points;
        if (!points || points.length < 2) continue;
        const width = effect.width || 4;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.strokeStyle = rgba(effect.color, alpha * 0.18);
        ctx.lineWidth = (width * 2.6) / zoom;
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let index = 1; index < points.length; index += 1) {
          ctx.lineTo(points[index].x, points[index].y);
        }
        ctx.stroke();
        ctx.strokeStyle = rgba(effect.color, alpha * 0.72);
        ctx.lineWidth = width / zoom;
        ctx.stroke();
        ctx.strokeStyle = rgba("#ffffff", alpha * 0.9);
        ctx.lineWidth = Math.max(0.8, width * 0.28) / zoom;
        ctx.stroke();
        for (let index = 1; index < points.length; index += 1) {
          const point = points[index];
          ctx.fillStyle = rgba("#ffffff", alpha * 0.8);
          ctx.beginPath();
          ctx.arc(point.x, point.y, (width * 0.42) / zoom, 0, TAU);
          ctx.fill();
        }
      } else if (effect.kind === "line") {
        ctx.strokeStyle = rgba(effect.color, alpha * 0.6);
        ctx.lineWidth = effect.width / zoom;
        ctx.beginPath();
        ctx.moveTo(effect.x1, effect.y1);
        ctx.lineTo(effect.x2, effect.y2);
        ctx.stroke();
        ctx.strokeStyle = rgba("#ffffff", alpha * 0.18);
        ctx.lineWidth = (effect.width * 0.34) / zoom;
        ctx.stroke();
      }
    }
    ctx.restore();
    void now;
  }

  drawParticles(ctx, now, zoom) {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const particle of this.particles) {
      const alpha = clamp(particle.life / particle.maxLife, 0, 1);
      if (alpha <= 0) continue;
      ctx.fillStyle = rgba(particle.color, alpha * 0.8);
      const size = Math.max(0.35, particle.size * (0.45 + alpha * 0.55));
      if (particle.kind === "spark") {
        ctx.strokeStyle = rgba(particle.color, alpha * 0.75);
        ctx.lineWidth = Math.max(0.5, size * 0.55);
        ctx.beginPath();
        ctx.moveTo(particle.x, particle.y);
        ctx.lineTo(
          particle.x - particle.vx * 0.02,
          particle.y - particle.vy * 0.02,
        );
        ctx.stroke();
      } else if (particle.kind === "shard") {
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
      } else if (particle.kind === "rune") {
        ctx.save();
        ctx.translate(particle.x, particle.y);
        ctx.rotate(particle.rotation);
        ctx.fillRect(-size * 0.45, -size, size * 0.9, size * 2);
        ctx.fillRect(-size, -size * 0.2, size * 2, size * 0.5);
        ctx.restore();
      } else if (particle.kind === "wisp") {
        ctx.globalAlpha = alpha * 0.7;
        ctx.beginPath();
        ctx.arc(particle.x, particle.y, size * 1.7, 0, TAU);
        ctx.fill();
        ctx.globalAlpha = 1;
      } else {
        ctx.beginPath();
        ctx.arc(particle.x, particle.y, size, 0, TAU);
        ctx.fill();
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
      const verticalOffset = 54 + 18 * zoom;
      const nameY = screenY - verticalOffset;
      if (nameY < 66 && screenY < 180) {
        // Keep labels clear of the top navigation while still drawing off-screen hints.
      }

      if (label.dead) {
        const respawn = Number(player.respawn_in || 0);
        ctx.fillStyle = "rgba(231, 105, 114, 0.7)";
        ctx.font = "13px 'Cozette', monospace";
        ctx.fillText(
          `ВОЗРОЖДЕНИЕ ${respawn.toFixed(1)}`,
          screenX,
          screenY - 46,
        );
        continue;
      }

      const color = player.color || VIOLET;
      const hp = clamp(Number(player.hp) || 0, 0, 100);
      const barWidth = self ? 60 : 50;
      const barY = nameY + 6;

      // Name and a colored identity gem.
      ctx.font = "13px 'Cozette', monospace";
      const suffix = self ? " · вы" : player.bot ? " · дух" : "";
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
