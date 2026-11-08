/* What the bosses' tricks look like on the floor. Each one explains itself by looking
 * like the thing it is a joke about: a string, a tag, a page, a list. */

import { label } from "./quest-art.js";
import { pixelRing } from "./vfx.js";

const STRING_COLOR = "#ce9178";

function drawString(ctx, move, t) {
  ctx.save();
  ctx.font = "bold 26px monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (const [x, y, char] of move.cells) {
    ctx.fillStyle = "rgba(20, 12, 8, 0.82)";
    ctx.fillRect(x - 15, y - 16, 30, 32);
    ctx.fillStyle = STRING_COLOR;
    ctx.fillText(char, x, y);
  }
  // The cursor, which never got to the end of the line.
  const [hx, hy] = move.head;
  ctx.fillStyle = Math.sin(t * 14) > -0.2 ? "#fff1b8" : STRING_COLOR;
  ctx.fillRect(hx - 5, hy - 19, 10, 38);
  if (move.quote) {
    const [qx, qy] = move.quote;
    const pulse = 1 + Math.sin(t * 6) * 0.14;
    pixelRing(ctx, qx, qy, 54 * pulse, 4, "#ffd27a", 0.9, { turn: t });
    ctx.fillStyle = "rgba(20, 12, 8, 0.9)";
    ctx.fillRect(qx - 24, qy - 28, 48, 52);
    ctx.font = "bold 58px monospace";
    ctx.fillStyle = "#ffe9a8";
    ctx.fillText('"', qx, qy + 8);
    label(ctx, "закрыть строку", qx, qy - 74, "#ffe9a8", 16);
  }
  ctx.restore();
}

function drawBlink(ctx, move, t) {
  ctx.save();
  for (const [x, y, group] of move.cells) {
    const lit = group === move.on;
    if (lit) {
      const flicker = move.hot ? 0.62 : Math.sin(t * 32) > 0 ? 0.46 : 0.14;
      ctx.fillStyle = move.hot ? `rgba(255, 90, 60, ${flicker})` : `rgba(255, 217, 61, ${flicker})`;
      ctx.beginPath();
      ctx.arc(x, y, move.r, 0, Math.PI * 2);
      ctx.fill();
      pixelRing(ctx, x, y, move.r, 4, move.hot ? "#ffb0a0" : "#ffd93d", 0.95);
    } else {
      pixelRing(ctx, x, y, move.r, 2.6, "#6a7080", 0.4, { gap: 0.35, seed: x });
    }
    if (lit) label(ctx, "<blink>", x, y, "#fff6d0", 15);
  }
  ctx.restore();
}

function drawDoomScroll(ctx, move, t) {
  const [left, top, right, bottom] = move.box;
  ctx.save();
  // The floor is going down, and you can see it going.
  const spacing = 110;
  const offset = (t * 92) % spacing;
  ctx.fillStyle = "rgba(255, 107, 158, 0.13)";
  for (let y = top - spacing + offset; y < bottom; y += spacing) {
    for (let x = left + 40; x < right; x += 150) {
      for (let step = 0; step < 6; step += 1) {
        ctx.fillRect(x - 30 + step * 5, y + step * 4, 8, 8);
        ctx.fillRect(x + 30 - step * 5, y + step * 4, 8, 8);
      }
    }
  }
  const strip = bottom - move.strip;
  ctx.fillStyle = `rgba(255, 60, 90, ${0.3 + Math.sin(t * 7) * 0.08})`;
  ctx.fillRect(left, strip, right - left, move.strip);
  for (let x = left; x < right; x += 44) {
    ctx.fillStyle = (x / 44) % 2 < 1 ? "rgba(255, 220, 90, 0.7)" : "rgba(10, 8, 14, 0.7)";
    ctx.fillRect(x, strip - 6, 44, 6);
  }
  label(ctx, "конец страницы (загрузить ещё)", (left + right) / 2, bottom - move.strip / 2, "#ffd0da", 18);
  ctx.restore();
}

function drawBait(ctx, move, t) {
  ctx.save();
  for (const [x, y, text, real] of move.items) {
    if (real) {
      // Nothing to see here: a plain first aid kit.
      ctx.fillStyle = "#e4e8f0";
      ctx.fillRect(x - 20, y - 16, 40, 32);
      ctx.fillStyle = "#4fb878";
      ctx.fillRect(x - 4, y - 11, 8, 22);
      ctx.fillRect(x - 11, y - 4, 22, 8);
      label(ctx, text, x, y - 34, "#cfe8d8", 14);
      continue;
    }
    const pulse = 1 + Math.sin(t * 9 + x) * 0.14;
    pixelRing(ctx, x, y, 40 * pulse, 4, "#ffd93d", 0.9, { gap: 0.3, seed: y, turn: t * 2 });
    ctx.fillStyle = "#ffd93d";
    ctx.fillRect(x - 25, y - 21, 50, 42);
    ctx.fillStyle = "#ff3b5c";
    ctx.fillRect(x - 20, y - 16, 40, 32);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(x - 4, y - 11, 8, 15);
    ctx.fillRect(x - 4, y + 7, 8, 7);
    label(ctx, text, x, y - 52, "#ffe34d", 18);
  }
  ctx.restore();
}

function drawReturn(ctx, move, monsters, t) {
  const body = monsters.get(move.id);
  if (!body) return;
  const radius = (Number(body.data.r) || 36) + 22;
  ctx.save();
  ctx.fillStyle = "rgba(120, 110, 200, 0.14)";
  ctx.beginPath();
  ctx.arc(body.x, body.y, radius, 0, Math.PI * 2);
  ctx.fill();
  pixelRing(ctx, body.x, body.y, radius, 4.6, "#c8b8ff", 0.95, { turn: t * 1.4 });
  pixelRing(ctx, body.x, body.y, radius + 12, 2.6, "#ffffff", 0.55, { gap: 0.55, seed: move.id, turn: -t * 2 });
  label(ctx, `return None  ${move.left.toFixed(1)}`, body.x, body.y - radius - 26, "#e0d8ff", 18);
  ctx.restore();
}

function drawDel(ctx, move, t) {
  const { size } = move;
  ctx.save();
  for (const [x, y, gone] of move.cells) {
    if (gone) {
      ctx.fillStyle = "rgba(4, 4, 10, 0.86)";
      ctx.fillRect(x + 2, y + 2, size - 4, size - 4);
      ctx.fillStyle = "rgba(180, 170, 255, 0.5)";
      for (let speck = 0; speck < 6; speck += 1) {
        const px = x + 8 + ((speck * 37 + x) % (size - 16));
        const py = y + 8 + ((speck * 53 + y) % (size - 16));
        ctx.fillRect(px, py, 2, 2);
      }
      ctx.strokeStyle = "rgba(160, 150, 230, 0.8)";
      ctx.lineWidth = 2;
      ctx.strokeRect(x + 2, y + 2, size - 4, size - 4);
      label(ctx, "None", x + size / 2, y + size / 2, "#a89de8", 15);
    } else {
      const on = Math.sin(t * 22) > 0;
      ctx.fillStyle = on ? "rgba(255, 79, 106, 0.36)" : "rgba(255, 79, 106, 0.12)";
      ctx.fillRect(x + 2, y + 2, size - 4, size - 4);
      ctx.strokeStyle = "#ff4f6a";
      ctx.lineWidth = 3;
      ctx.strokeRect(x + 2, y + 2, size - 4, size - 4);
      label(ctx, "del", x + size / 2, y + size / 2, "#ffc0cc", 15);
    }
  }
  ctx.restore();
}

function drawColumns(ctx, move, t) {
  const [left, top, right, bottom] = move.box;
  const wide = (right - left) / move.n;
  ctx.save();
  for (let column = 0; column < move.n; column += 1) {
    const x = left + wide * column;
    const safe = move.safe?.includes(column);
    ctx.fillStyle = safe
      ? `rgba(79, 224, 138, ${0.34 + Math.sin(t * 16) * 0.1})`
      : column % 2
        ? "rgba(255, 150, 60, 0.13)"
        : "rgba(255, 190, 110, 0.24)";
    ctx.fillRect(x, top, wide, bottom - top);
    ctx.fillStyle = "rgba(255, 225, 180, 0.8)";
    ctx.fillRect(x - 1, top, 3, bottom - top);
    // The room is bigger than the screen: the number has to be wherever you are.
    for (let y = top + 70; y < bottom; y += 230) {
      label(ctx, `rows[${column}]`, x + wide / 2, y, safe ? "#bfffd8" : "#ffe2bd", 24);
    }
  }
  ctx.restore();
}

function drawBisect(ctx, move, t) {
  const { lo, hi, top, bottom } = move;
  ctx.save();
  if (move.side) {
    const ready = 1 - move.ttl / move.fuse;
    ctx.fillStyle = `rgba(255, 90, 60, ${0.14 + ready * 0.34 + Math.sin(t * 24) * 0.05})`;
    ctx.fillRect(move.side[0], top, move.side[1] - move.side[0], bottom - top);
  }
  const mid = (lo + hi) / 2;
  ctx.fillStyle = "#ffd27a";
  ctx.fillRect(lo - 2, top, 4, bottom - top);
  ctx.fillRect(hi - 2, top, 4, bottom - top);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(mid - 2, top, 4, bottom - top);
  label(ctx, "lo", lo + 22, top + 34, "#ffe9a8", 22);
  label(ctx, "hi", hi - 22, top + 34, "#ffe9a8", 22);
  label(ctx, "mid", mid, top + 34, "#ffffff", 22);
  ctx.restore();
}

function drawAccept(ctx, move, t) {
  const [ax, ay, ar] = move.accept;
  const [rx, ry, rr] = move.reject;
  ctx.save();
  const danger = 0.12 + (1 - move.ttl / 4.2) * 0.22 + Math.sin(t * 9) * 0.03;
  ctx.fillStyle = `rgba(255, 40, 70, ${danger})`;
  ctx.fillRect(ax - 3000, ay - 3000, 6000, 6000);
  // What he wants you to press: enormous, green and terribly friendly.
  const pulse = 1 + Math.sin(t * 5) * 0.05;
  ctx.fillStyle = "rgba(79, 224, 138, 0.3)";
  ctx.beginPath();
  ctx.arc(ax, ay, ar * pulse, 0, Math.PI * 2);
  ctx.fill();
  pixelRing(ctx, ax, ay, ar * pulse, 5, "#9ff0c0", 1, { turn: t });
  ctx.fillStyle = "#2fb56a";
  ctx.fillRect(ax - 78, ay - 24, 156, 48);
  ctx.fillStyle = "#7ff0b0";
  ctx.fillRect(ax - 78, ay - 24, 156, 5);
  ctx.fillStyle = "#157a44";
  ctx.fillRect(ax - 78, ay + 19, 156, 5);
  label(ctx, "ПРИНЯТЬ", ax, ay, "#ffffff", 26);
  // And the other one, small and far away.
  ctx.fillStyle = "rgba(200, 200, 215, 0.14)";
  ctx.beginPath();
  ctx.arc(rx, ry, rr, 0, Math.PI * 2);
  ctx.fill();
  pixelRing(ctx, rx, ry, rr, 3, "#c8ccd8", 0.9, { gap: 0.25, seed: 3 });
  label(ctx, "отклонить", rx, ry, "#d8dce8", 15);
  label(ctx, `git push --force через ${move.ttl.toFixed(1)}`, ax, ay - ar - 28, "#ffb0b8", 20);
  ctx.restore();
}

/** Drawn after the lighting, so that a dark room cannot hide what is about to kill you. */
export function drawBossMoves(ctx, moves, monsters, now) {
  if (!moves?.length) return;
  const t = now / 1000;
  for (const move of moves) {
    if (move.k === "string") drawString(ctx, move, t);
    else if (move.k === "blink") drawBlink(ctx, move, t);
    else if (move.k === "doomscroll") drawDoomScroll(ctx, move, t);
    else if (move.k === "bait") drawBait(ctx, move, t);
    else if (move.k === "return") drawReturn(ctx, move, monsters, t);
    else if (move.k === "del") drawDel(ctx, move, t);
    else if (move.k === "columns") drawColumns(ctx, move, t);
    else if (move.k === "bisect") drawBisect(ctx, move, t);
    else if (move.k === "accept") drawAccept(ctx, move, t);
  }
}
