/* Words do not appear all at once here. Each letter arrives as a green 0 or 1,
 * like the fog over an unloaded room, and only then turns into what it means. */

const DECODE_TIME = 75;
const PAUSES = { ".": 150, "!": 150, "?": 150, "…": 170, ",": 70, ":": 90, ";": 90 };
const LONG_WORD = 24;

const reduceMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Letters laid out at once and kept invisible, so that the lines never rewrap as they fill. */
function layOut(node, text) {
  const letters = [];
  const fragment = document.createDocumentFragment();
  text.split(/( +)/).forEach((piece) => {
    if (!piece) return;
    if (piece.trim() === "") {
      fragment.append(document.createTextNode(piece));
      return;
    }
    const word = document.createElement("span");
    word.className = piece.length > LONG_WORD ? "tw-word long" : "tw-word";
    for (const char of piece) {
      const letter = document.createElement("span");
      letter.className = "tw-char";
      letter.textContent = char;
      word.append(letter);
      letters.push(letter);
    }
    fragment.append(word);
  });
  node.replaceChildren(fragment);
  return letters;
}

export class TypeWriter {
  constructor(node, text, { speed = 58, onLetter = null, onDone = null } = {}) {
    this.letters = layOut(node, text);
    this.speed = speed;
    this.onLetter = onLetter;
    this.onDone = onDone;
    this.index = 0;
    this.decoding = [];
    this.credit = 0;
    this.wait = 0;
    this.last = performance.now();
    this.done = false;
    this.frame = null;
    node.setAttribute("aria-label", text);
    if (reduceMotion()) {
      this.skip();
      return;
    }
    this.frame = window.requestAnimationFrame((now) => this.tick(now));
  }

  tick(now) {
    if (this.done) return;
    const passed = Math.min(100, now - this.last);
    this.last = now;
    if (this.wait > 0) {
      this.wait -= passed;
    } else {
      this.credit += (passed / 1000) * this.speed;
      while (this.credit >= 1 && this.index < this.letters.length && this.wait <= 0) {
        this.credit -= 1;
        this.reveal(now);
      }
    }
    this.settle(now);
    if (this.index >= this.letters.length && !this.decoding.length) {
      this.finish();
      return;
    }
    this.frame = window.requestAnimationFrame((time) => this.tick(time));
  }

  reveal(now) {
    const letter = this.letters[this.index];
    this.index += 1;
    letter.dataset.bit = Math.random() < 0.5 ? "0" : "1";
    letter.classList.add("on", "decoding");
    this.decoding.push({ letter, until: now + DECODE_TIME });
    const char = letter.textContent;
    this.wait = PAUSES[char] || 0;
    this.onLetter?.(char, this.index);
  }

  settle(now) {
    while (this.decoding.length && this.decoding[0].until <= now) {
      this.decoding.shift().letter.classList.remove("decoding");
    }
  }

  /** Someone reads faster than this: all of it, right now. */
  skip() {
    for (const letter of this.letters) {
      letter.classList.remove("decoding");
      letter.classList.add("on", "still");
    }
    this.index = this.letters.length;
    this.decoding = [];
    this.finish();
  }

  finish() {
    if (this.done) return;
    this.done = true;
    window.cancelAnimationFrame(this.frame);
    this.onDone?.();
  }

  stop() {
    this.done = true;
    window.cancelAnimationFrame(this.frame);
  }
}
