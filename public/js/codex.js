/* The handbook: enemies, bosses and everyone else, opened as the party gets to them. */

import { paintSprite } from "./dungeon-art.js";
import { PORTRAIT_GRID, paintPortrait } from "./portraits.js";

const THUMB_TIME = 1000;

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function paintArt(canvas, art, locked, now = THUMB_TIME) {
  if (art.type === "sprite") {
    paintSprite(canvas, art.key, locked);
    return;
  }
  canvas.width = PORTRAIT_GRID;
  canvas.height = PORTRAIT_GRID;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  if (locked) {
    ctx.fillStyle = "#14161f";
    ctx.fillRect(0, 0, PORTRAIT_GRID, PORTRAIT_GRID);
    ctx.fillStyle = "#3a3e4c";
    ctx.fillRect(10, 8, 12, 15);
    ctx.fillRect(5, 25, 22, 7);
    return;
  }
  paintPortrait(ctx, art.key, { now, tag: "" });
}

function statBar(label, value, ratio, shown = String(value)) {
  const row = el("div", "codex-stat");
  const track = el("i", "codex-track");
  const fill = el("i", "codex-fill");
  fill.style.width = `${Math.round(Math.max(0.03, Math.min(1, ratio)) * 100)}%`;
  track.append(fill);
  row.append(el("span", "", label), track, el("b", "", shown));
  return row;
}

export class Codex {
  constructor(root) {
    this.root = root;
    this.data = null;
    this.cleared = 0;
    this.folk = {};
    this.section = "enemies";
    this.selected = {};
    this.faceFrame = null;
    this.lastList = "";
  }

  setData(data) {
    this.data = data;
    this.lastList = "";
    this.render();
  }

  setProfile(profile) {
    if (!profile) return;
    const cleared = profile.cleared ?? 0;
    const folk = profile.folk || {};
    const changed = cleared !== this.cleared || JSON.stringify(folk) !== JSON.stringify(this.folk);
    this.cleared = cleared;
    this.folk = folk;
    if (changed) {
      this.lastList = "";
      this.render();
    }
  }

  isOpen(entry) {
    return this.cleared >= entry.opens;
  }

  sections() {
    return this.data?.sections || [];
  }

  current() {
    return this.sections().find((section) => section.key === this.section) || this.sections()[0];
  }

  allEntries(section) {
    return section.groups.flatMap((group) => group.entries);
  }

  selectedEntry(section) {
    const all = this.allEntries(section);
    return (
      all.find((entry) => entry.key === this.selected[section.key]) ||
      all.find((entry) => this.isOpen(entry)) ||
      all[0]
    );
  }

  render() {
    if (!this.root) return;
    if (!this.data) {
      // The page is served fresh from disk, but the server only learns new data on restart.
      this.root.replaceChildren(
        el("p", "codex-missing", "Сервер запущен со старым кодом и не прислал справочник. Перезапустите его: python3 server.py"),
      );
      return;
    }
    const section = this.current();
    if (!section) return;
    const head = el("div", "codex-head");
    const tabs = el("div", "codex-tabs");
    tabs.setAttribute("role", "tablist");
    for (const entry of this.sections()) {
      const all = this.allEntries(entry);
      const open = all.filter((item) => this.isOpen(item)).length;
      const tab = el("button", `codex-tab ${entry.key === section.key ? "active" : ""}`);
      tab.type = "button";
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-selected", String(entry.key === section.key));
      tab.append(el("span", "", entry.title), el("small", "", `${open} из ${all.length}`));
      tab.addEventListener("click", () => {
        this.section = entry.key;
        this.render();
      });
      tabs.append(tab);
    }
    head.append(tabs);

    const list = el("div", "codex-list");
    for (const group of section.groups) {
      list.append(el("h4", "codex-group", group.title));
      if (group.note) list.append(el("p", "codex-note", group.note));
      const grid = el("div", "codex-grid");
      for (const entry of group.entries) grid.append(this.renderItem(section, entry));
      list.append(grid);
    }
    list.append(el("p", "codex-note codex-foot", this.data.note));

    const detail = el("article", "codex-detail");
    this.renderDetail(detail, this.selectedEntry(section), section);
    const body = el("div", "codex-body");
    body.append(list, detail);
    const keep = this.root.querySelector(".codex-list")?.scrollTop || 0;
    this.root.replaceChildren(head, body);
    list.scrollTop = keep;
  }

  renderItem(section, entry) {
    const open = this.isOpen(entry);
    const chosen = this.selectedEntry(section)?.key === entry.key;
    const item = el("button", `codex-item ${open ? "" : "locked"} ${chosen ? "chosen" : ""}`);
    item.type = "button";
    if (entry.color && open) item.style.setProperty("--accent", entry.color);
    const canvas = el("canvas", "codex-thumb");
    paintArt(canvas, entry.art, !open);
    item.append(canvas, el("span", "", open ? entry.title : "???"));
    item.addEventListener("click", () => {
      this.selected[section.key] = entry.key;
      this.render();
      this.root.querySelector(".codex-detail")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
    return item;
  }

  renderDetail(detail, entry, section) {
    window.cancelAnimationFrame(this.faceFrame);
    this.faceFrame = null;
    if (!entry) return;
    const open = this.isOpen(entry);
    if (entry.color && open) detail.style.setProperty("--accent", entry.color);
    const top = el("header", "codex-top");
    const frame = el("div", `codex-art ${entry.art.type}`);
    const canvas = el("canvas");
    paintArt(canvas, entry.art, !open);
    frame.append(canvas);
    const names = el("div", "codex-names");
    if (!open) {
      names.append(el("h3", "", "Пока неизвестно"), el("p", "codex-sub", `Откроется: ${entry.where}`));
      top.append(frame, names);
      detail.append(top);
      return;
    }
    names.append(el("h3", "", entry.title));
    if (entry.subtitle) names.append(el("p", "codex-sub", entry.subtitle));
    if (entry.where) names.append(el("p", "codex-where", entry.where));
    top.append(frame, names);
    detail.append(top);
    if (entry.art.type === "portrait") this.animateFace(canvas, entry.art);
    if (entry.hint) detail.append(el("blockquote", "codex-hint", entry.hint));
    if (entry.perk) detail.append(el("p", "codex-perk", entry.perk));
    if (entry.lines) {
      const line = [...entry.lines].reverse().find(([at]) => this.cleared >= at);
      if (line) detail.append(el("blockquote", "codex-hint", line[1]));
    }
    if (entry.hp !== undefined) detail.append(this.renderStats(entry, section));
    if (entry.traits?.length) {
      const chips = el("div", "codex-chips");
      for (const trait of entry.traits) chips.append(el("span", "codex-chip", trait));
      detail.append(chips);
    }
    if (entry.weak?.length) detail.append(this.renderRunes("Уязвим, урон ×1,5:", entry.weak, "weak"));
    if (entry.immune?.length) detail.append(this.renderRunes("Не берёт:", entry.immune, "immune"));
    if (entry.moves?.length) detail.append(this.renderMoves(entry));
    if (entry.parts) detail.append(this.renderParts(entry));
    if (entry.code) {
      const code = el("p", "codex-code");
      code.append(el("span", "", "В заклинании:"), el("code", "", `if ${entry.code}:`));
      detail.append(code);
    }
  }

  renderStats(entry, section) {
    const stats = el("div", "codex-stats");
    const top = Math.max(...this.allEntries(section).map((item) => item.hp || 0), 1);
    stats.append(statBar("Здоровье", entry.hp, entry.hp / top));
    const mage = this.data.mage_speed;
    if (entry.speed > 0) {
      stats.append(statBar("Скорость", entry.speed, entry.speed / (mage * 1.1), `${entry.speed} (маг ${mage})`));
    } else {
      stats.append(statBar("Скорость", 0, 0, "стоит на месте"));
    }
    if (entry.contact) stats.append(statBar("Удар вплотную", entry.contact, entry.contact / 30));
    if (entry.shot) stats.append(statBar("Урон снаряда", entry.shot, entry.shot / 30));
    return stats;
  }

  renderRunes(label, runes, kind) {
    const row = el("p", `codex-runes ${kind}`);
    row.append(el("span", "", label));
    for (const rune of runes) row.append(el("code", "", rune));
    return row;
  }

  renderMoves(entry) {
    const box = el("div", "codex-moves");
    box.append(el("h4", "", "Что умеет"));
    for (const move of entry.moves) {
      const row = el("div", "codex-move");
      row.append(el("code", "", move.error), el("p", "", move.tip));
      box.append(row);
    }
    return box;
  }

  renderParts(entry) {
    const box = el("div", "codex-moves");
    const reached = entry.parts.filter((part) => this.cleared >= part.opens);
    box.append(el("h4", "", entry.parts.length > 1 ? `Истории: ${reached.length} из ${entry.parts.length}` : "Чем помочь"));
    for (const part of reached) {
      const row = el("div", `codex-move ${this.folk[part.key] || ""}`);
      const status = this.folk[part.key];
      const head = el("div", "codex-part-head");
      if (entry.parts.length > 1) head.append(el("b", "", part.title));
      if (status) head.append(el("span", "codex-status", status === "passed" ? "Помогли" : "За вас нажали «Принять»"));
      if (head.childElementCount) row.append(head);
      row.append(el("p", "", part.task), el("small", "", part.where));
      box.append(row);
    }
    return box;
  }

  /** Whoever is on the open page keeps blinking. */
  animateFace(canvas, art) {
    const ctx = canvas.getContext("2d");
    const paint = (now) => {
      if (!canvas.isConnected) {
        this.faceFrame = null;
        return;
      }
      if (canvas.offsetParent !== null && ctx) paintPortrait(ctx, art.key, { now, tag: "" });
      this.faceFrame = window.requestAnimationFrame(paint);
    };
    this.faceFrame = window.requestAnimationFrame(paint);
  }
}
