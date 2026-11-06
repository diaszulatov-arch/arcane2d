/* Spell editor: a coloured layer under the textarea, line marks and completion. */

import { CONSTANT_API, FIELD_API, SENSE_API, SPELL_API } from "./content.js";

const KEYWORDS = new Set(
  "if elif else for while in not and or is def return break continue pass".split(" "),
);
const LITERALS = new Set(["True", "False", "None"]);
const RUNES = new Map(SPELL_API.map((entry) => [entry.name, entry.element]));
const SENSES = new Set(SENSE_API.map((entry) => entry.name));
const CONSTANTS = new Set(CONSTANT_API);
const MAX_SUGGESTIONS = 7;

const TOKEN =
  /(#[^\n]*)|([fFrRbB]{0,2}(?:"""[\s\S]*?(?:"""|$)|'''[\s\S]*?(?:'''|$)|"(?:\\.|[^"\\\n])*"?|'(?:\\.|[^'\\\n])*'?))|(\b\d+\.?\d*(?:[eE][+-]?\d+)?\b|\.\d+\b)|([\p{L}_][\p{L}\p{N}_]*)/gu;

function classifyName(name, previous) {
  if (KEYWORDS.has(name)) return "kw";
  if (LITERALS.has(name)) return "lit";
  if (previous === "def") return "def";
  const element = RUNES.get(name);
  if (element) return `rune-${element}`;
  if (SENSES.has(name)) return "sense";
  if (CONSTANTS.has(name)) return "const";
  return "";
}

/** Split source into [{text, kind}] covering every character exactly once. */
function tokenize(source) {
  const tokens = [];
  let index = 0;
  let previous = "";
  for (const match of source.matchAll(TOKEN)) {
    if (match.index > index) {
      tokens.push({ text: source.slice(index, match.index), kind: "" });
    }
    const [text, comment, string, number, name] = match;
    let kind = "";
    if (comment !== undefined) kind = "comment";
    else if (string !== undefined) kind = "str";
    else if (number !== undefined) kind = "num";
    else if (name !== undefined) {
      const afterDot = source[match.index - 1] === ".";
      kind = afterDot ? "field" : classifyName(name, previous);
      previous = name;
    }
    tokens.push({ text, kind });
    index = match.index + text.length;
  }
  if (index < source.length) tokens.push({ text: source.slice(index), kind: "" });
  return tokens;
}

function lastWord(text) {
  return text.match(/[\p{L}_][\p{L}\p{N}_]*$/u)?.[0] ?? "";
}

/** True when the caret sits inside a comment or an open string on this line. */
function inProse(linePrefix) {
  let quote = "";
  for (let index = 0; index < linePrefix.length; index += 1) {
    const char = linePrefix[index];
    if (quote) {
      if (char === "\\") index += 1;
      else if (char === quote) quote = "";
    } else if (char === '"' || char === "'") {
      quote = char;
    } else if (char === "#") {
      return true;
    }
  }
  return Boolean(quote);
}

export class SpellEditor {
  constructor({ input, layer, gutter, popup, costOf }) {
    this.input = input;
    this.layer = layer;
    this.gutter = gutter;
    this.popup = popup;
    this.costOf = costOf;
    this.errorLine = null;
    this.items = [];
    this.selected = 0;
    this.wordStart = 0;
    this.charWidth = 0;
    this.renderedSource = null;

    input.addEventListener("scroll", () => this.syncScroll());
    input.addEventListener("blur", () => this.closeCompletion());
    input.addEventListener("click", () => this.closeCompletion());
    popup.addEventListener("pointerdown", (event) => {
      // Keep focus in the textarea, otherwise blur closes the list first.
      event.preventDefault();
      const row = event.target.closest?.("[data-index]");
      if (row) this.accept(Number(row.dataset.index));
    });
  }

  refresh() {
    this.render();
    this.syncScroll();
  }

  render() {
    const source = this.input.value;
    const lines = [[]];
    for (const token of tokenize(source)) {
      const parts = token.text.split("\n");
      parts.forEach((part, index) => {
        if (index > 0) lines.push([]);
        if (part) lines[lines.length - 1].push({ text: part, kind: token.kind });
      });
    }

    const code = document.createDocumentFragment();
    const numbers = document.createDocumentFragment();
    lines.forEach((tokens, index) => {
      const line = document.createElement("span");
      line.className = "code-line";
      const number = document.createElement("span");
      number.className = "code-line-number";
      number.textContent = String(index + 1);
      if (index + 1 === this.errorLine) {
        line.classList.add("has-error");
        number.classList.add("has-error");
      }
      for (const token of tokens) {
        if (!token.kind) {
          line.append(token.text);
          continue;
        }
        const span = document.createElement("span");
        span.className = `tok-${token.kind}`;
        span.textContent = token.text;
        line.append(span);
      }
      code.append(line);
      numbers.append(number);
    });
    this.layer.replaceChildren(code);
    this.gutter.replaceChildren(numbers);
    this.renderedSource = source;
  }

  syncScroll() {
    const { scrollTop, scrollLeft } = this.input;
    this.layer.style.transform = `translate(${-scrollLeft}px, ${-scrollTop}px)`;
    this.gutter.style.transform = `translateY(${-scrollTop}px)`;
    if (!this.popup.hidden) this.positionPopup();
  }

  setErrorLine(line) {
    const next = Number.isInteger(line) && line > 0 ? line : null;
    if (next === this.errorLine) return;
    this.errorLine = next;
    this.render();
  }

  // ---------------------------------------------------------------- editing
  /** Replace a range through the browser's edit stack, so Ctrl+Z still works. */
  replaceRange(start, end, text, selectionStart, selectionEnd) {
    const { input } = this;
    input.focus();
    input.setSelectionRange(start, end);
    const applied = text
      ? document.execCommand("insertText", false, text)
      : document.execCommand("delete");
    if (!applied) {
      input.setRangeText(text, start, end, "end");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
    const length = input.value.length;
    input.setSelectionRange(
      Math.min(selectionStart, length),
      Math.min(selectionEnd, length),
    );
  }

  // ------------------------------------------------------------- completion
  suggestionsFor(prefix, afterDot) {
    const needle = prefix.toLowerCase();
    if (afterDot) {
      return FIELD_API.filter((entry) => entry.name.startsWith(needle)).map((entry) => ({
        ...entry,
        label: entry.name,
        insert: entry.name,
      }));
    }
    if (!needle) return [];
    const functions = [...SPELL_API, ...SENSE_API]
      .filter((entry) => entry.name.startsWith(needle))
      .map((entry) => ({
        ...entry,
        label: `${entry.name}(${entry.args})`,
        insert: `${entry.name}()`,
        // With nothing to pass, the caret belongs after the brackets.
        caretBack: entry.args ? 1 : 0,
        cost: this.costOf(entry.name),
      }));
    const constants = CONSTANT_API.filter((name) =>
      name.toLowerCase().startsWith(needle),
    ).map((name) => ({ name, label: name, insert: name, about: "Константа" }));
    return [...functions, ...constants];
  }

  updateCompletion() {
    const { input } = this;
    if (input.selectionStart !== input.selectionEnd) return this.closeCompletion();
    const caret = input.selectionStart;
    const lineStart = input.value.lastIndexOf("\n", caret - 1) + 1;
    const linePrefix = input.value.slice(lineStart, caret);
    if (inProse(linePrefix)) return this.closeCompletion();

    const word = lastWord(linePrefix);
    const afterDot = linePrefix[linePrefix.length - word.length - 1] === ".";
    const items = this.suggestionsFor(word, afterDot).slice(0, MAX_SUGGESTIONS);
    // A finished word with nothing left to add is not worth a list.
    if (!items.length || (items.length === 1 && items[0].insert === word)) {
      return this.closeCompletion();
    }
    this.items = items;
    this.selected = 0;
    this.wordStart = caret - word.length;
    this.renderPopup();
    return undefined;
  }

  renderPopup() {
    const rows = this.items.map((item, index) => {
      const row = document.createElement("div");
      row.className = "complete-row";
      row.dataset.index = String(index);
      row.setAttribute("role", "option");
      row.setAttribute("aria-selected", String(index === this.selected));
      if (item.element) row.dataset.element = item.element;

      const label = document.createElement("span");
      label.className = "complete-label";
      label.textContent = item.label;
      const about = document.createElement("span");
      about.className = "complete-about";
      about.textContent = item.about || "";
      row.append(label, about);
      if (Number.isFinite(item.cost)) {
        const cost = document.createElement("span");
        cost.className = "complete-cost";
        cost.textContent = `${item.cost} ◆`;
        row.append(cost);
      }
      return row;
    });
    this.popup.replaceChildren(...rows);
    this.popup.hidden = false;
    this.positionPopup();
  }

  positionPopup() {
    const { input, popup } = this;
    const style = getComputedStyle(input);
    const lineHeight = parseFloat(style.lineHeight) || 20;
    const paddingTop = parseFloat(style.paddingTop) || 0;
    const paddingLeft = parseFloat(style.paddingLeft) || 0;
    const before = input.value.slice(0, this.wordStart);
    const line = before.split("\n").length - 1;
    const column = this.wordStart - (before.lastIndexOf("\n") + 1);

    if (!this.charWidth) {
      const probe = document.createElement("canvas").getContext("2d");
      probe.font = `${style.fontSize} ${style.fontFamily}`;
      this.charWidth = probe.measureText("0".repeat(20)).width / 20 || 7;
    }
    const box = input.getBoundingClientRect();
    const host = popup.offsetParent?.getBoundingClientRect() ?? box;
    const below = paddingTop + (line + 1) * lineHeight - input.scrollTop;
    const height = popup.offsetHeight;
    const fits = below + height < box.height;
    const top = fits ? below : Math.max(0, below - lineHeight - height);
    const left = Math.min(
      paddingLeft + column * this.charWidth - input.scrollLeft,
      box.width - popup.offsetWidth - 6,
    );
    popup.style.top = `${box.top - host.top + top}px`;
    popup.style.left = `${box.left - host.left + Math.max(0, left)}px`;
  }

  closeCompletion() {
    this.items = [];
    this.popup.hidden = true;
  }

  accept(index = this.selected) {
    const item = this.items[index];
    if (!item) return;
    const { input } = this;
    const caret = input.selectionStart;
    const start = this.wordStart;
    this.closeCompletion();
    // Do not double the brackets when the call is already written out.
    const hasCall = input.value[caret] === "(";
    const text = hasCall ? item.insert.replace(/\(\)$/, "") : item.insert;
    const back = hasCall ? 0 : item.caretBack || 0;
    const end = start + text.length - back;
    this.replaceRange(start, caret, text, end, end);
    this.closeCompletion();
  }

  /** Handle a key aimed at the open list; returns true when it was consumed. */
  handleKey(event) {
    if (this.popup.hidden) return false;
    const plain = !event.ctrlKey && !event.metaKey && !event.altKey;
    switch (event.key) {
      case "ArrowDown":
      case "ArrowUp": {
        const step = event.key === "ArrowDown" ? 1 : -1;
        this.selected = (this.selected + step + this.items.length) % this.items.length;
        this.renderPopup();
        break;
      }
      case "Tab":
        if (!plain) return false;
        this.accept();
        break;
      case "Enter":
        // Only Tab accepts: "y = a" + Enter must end the line, not become abs().
        this.closeCompletion();
        return false;
      case "Escape":
        this.closeCompletion();
        break;
      default:
        return false;
    }
    event.preventDefault();
    event.stopPropagation();
    return true;
  }
}
