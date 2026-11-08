/*
 * Every event the game can send, through the real drawing code, with no browser.
 *
 * A single throw in a frame used to stop the picture for good. The stand-in canvas
 * refuses what a real one refuses, so a mistake shows up here and not in somebody's game.
 *
 * Reads {config, snapshot} from stdin, prints {frames, events, failures} as JSON.
 */

import { readFileSync } from "node:fs";

function finite(...values) {
  if (!values.every(Number.isFinite)) throw new TypeError("non-finite coordinate");
}

function fakeGradient() {
  return {
    addColorStop(offset, color) {
      if (!(offset >= 0 && offset <= 1)) throw new RangeError(`colour stop at ${offset}`);
      if (typeof color !== "string" || /NaN|undefined/.test(color)) {
        throw new SyntaxError(`not a colour: ${color}`);
      }
    },
  };
}

function imageData(width, height) {
  if (!width || !height) throw new RangeError("image data with no size");
  return { width, height, data: new Uint8ClampedArray(width * height * 4) };
}

function fakeContext(canvas) {
  const calls = {
    arc(x, y, radius) {
      if (radius < 0) throw new RangeError(`arc of radius ${radius}`);
    },
    ellipse(x, y, radiusX, radiusY) {
      if (radiusX < 0 || radiusY < 0) throw new RangeError("ellipse of negative radius");
    },
    createLinearGradient(...points) {
      finite(...points);
      return fakeGradient();
    },
    createRadialGradient(x0, y0, r0, x1, y1, r1) {
      finite(x0, y0, r0, x1, y1, r1);
      if (r0 < 0 || r1 < 0) throw new RangeError("gradient of negative radius");
      return fakeGradient();
    },
    createPattern: () => fakeGradient(),
    createImageData: imageData,
    getImageData: (x, y, width, height) => imageData(width, height),
    drawImage(source) {
      if (!source || source.width === 0 || source.height === 0) {
        throw new Error("drawImage of a canvas with no size");
      }
    },
    measureText: (text) => ({ width: String(text).length * 6 }),
  };
  const nothing = () => {};
  const state = { canvas, globalAlpha: 1, globalCompositeOperation: "source-over", lineWidth: 1 };
  return new Proxy(state, {
    get: (target, name) => (name in target ? target[name] : calls[name] ?? nothing),
  });
}

function fakeCanvas() {
  const canvas = {
    width: 300,
    height: 150,
    style: {},
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 1186, height: 900 }),
  };
  const ctx = fakeContext(canvas);
  canvas.getContext = () => ctx;
  return canvas;
}

globalThis.document = { createElement: fakeCanvas };
globalThis.window = {
  location: { search: "" },
  devicePixelRatio: 1,
  matchMedia: () => ({ matches: false }),
};

const { ArenaRenderer } = await import("../public/js/renderer.js");

// What it can be asked to draw, read from the handler itself so nothing new gets missed.
const source = readFileSync(new URL("../public/js/renderer.js", import.meta.url), "utf8");
const start = source.indexOf("  handleEvent(event, client) {");
const handler = source.slice(start, source.indexOf("\n  }\n", start));
const names = [...new Set([...handler.matchAll(/case "([a-z_]+)":/g)].map((match) => match[1]))];
const kinds = [
  undefined,
  ...new Set([...handler.matchAll(/event\.kind === "([a-z_]+)"/g)].map((match) => match[1])),
];

const { config, snapshot } = JSON.parse(readFileSync(0, "utf8"));
const me = snapshot.players[0];
const point = (x, y) => Object.assign([x, y], { x, y });

function makeClient() {
  return {
    config,
    joined: true,
    connected: true,
    selfId: me.id,
    selfName: me.name,
    selfColor: me.color,
    players: new Map(snapshot.players.map((player) => [player.id, player])),
    projectiles: snapshot.projectiles ?? [],
    wards: snapshot.wards ?? [],
    emps: snapshot.emps ?? [],
    meteors: snapshot.meteors ?? [],
    clouds: snapshot.clouds ?? [],
    monsters: [],
    hazards: [],
    pickups: [],
    terminals: [],
    barriers: [],
    breakpoints: [],
    bossMoves: [],
    role: "",
    story: null,
    quest: null,
    terrainState: null,
    workshop: null,
    life: null,
    closedDoors: new Set(),
    pointer: { x: 500, y: 400, inside: true, touch: false, joy: null },
    aim: 0,
    prediction: { x: me.x, y: me.y, errorX: 0, errorY: 0, active: false },
    rtt: 0,
    hotCards: [],
  };
}

function eventOf(e, kind) {
  const { x, y } = me;
  return {
    e,
    kind,
    x,
    y,
    id: me.id,
    target_id: me.id,
    from_x: x - 120,
    from_y: y - 80,
    to_x: x + 120,
    to_y: y + 80,
    x1: x - 120,
    y1: y - 80,
    x2: x + 120,
    y2: y + 80,
    color: "#ff7b45",
    amount: 12,
    absorbed: 4,
    drained: 3,
    healed: 5,
    count: 3,
    radius: 90,
    width: 40,
    good: true,
    boss: true,
    stun: true,
    role: "dps",
    label: "метка",
    text: "текст",
    points: [point(x, y), point(x + 60, y + 20), point(x + 120, y - 10)],
    cells: [[x, y]],
    cracks: [[x, y]],
    hits: [[x, y]],
  };
}

// A spark or a blast has to survive every moment of its life, not just the first.
const AGES = [0, 0.05, 0.2, 0.5, 1, 2];
const failures = new Map();
let frames = 0;
let now = 1000;

function attempt(label, action) {
  try {
    action();
  } catch (error) {
    if (!failures.has(label)) failures.set(label, `${error.name}: ${error.message}`);
  }
}

for (const quality of ["2", "1", "0"]) {
  window.location.search = `?fx=${quality}`;
  const renderer = new ArenaRenderer(fakeCanvas());
  const client = makeClient();
  attempt(`fx=${quality}, an empty frame`, () => renderer.draw(client, now));
  for (const name of names) {
    for (const kind of kinds) {
      const label = kind ? `${name}/${kind}` : name;
      attempt(label, () => renderer.handleEvent(eventOf(name, kind), client));
      for (const age of AGES) {
        now += 16;
        attempt(label, () => {
          renderer.updateEffects(age);
          renderer.draw(client, now);
        });
        frames += 1;
      }
      renderer.particles.length = 0;
      renderer.effects.length = 0;
    }
  }
}

console.log(
  JSON.stringify({ frames, events: names.length, failures: Object.fromEntries(failures) }),
);
