/* Arcane 2D — browser client: local spellbook, networking, controls and UI. */

import { SoundEngine } from "./js/audio.js";
import { SpellEditor } from "./js/editor.js";
import { ArenaRenderer } from "./js/renderer.js";
import { StoryUi } from "./js/story.js";
import {
  EXAMPLES,
  SLOT_RUNES,
  SPELL_API,
  STORY_ONLY,
  loadMageName,
  loadMode,
  loadSoundEnabled,
  loadSpellbook,
  loadToken,
  saveMageName,
  saveMode,
  saveSoundEnabled,
  saveSpellbook,
  useSpellbook,
} from "./js/content.js";

const TAU = Math.PI * 2;
const DEFAULT_WORLD = {
  arena: { w: 1900, h: 1100, border: 46 },
  obstacles: [
    { x: 950, y: 550, r: 78, kind: "altar" },
    { x: 500, y: 330, r: 46, kind: "pillar" },
    { x: 1400, y: 330, r: 46, kind: "pillar" },
    { x: 500, y: 770, r: 46, kind: "pillar" },
    { x: 1400, y: 770, r: 46, kind: "pillar" },
    { x: 250, y: 550, r: 34, kind: "ruin" },
    { x: 1650, y: 550, r: 34, kind: "ruin" },
    { x: 950, y: 250, r: 30, kind: "crystal" },
    { x: 950, y: 850, r: 30, kind: "crystal" },
  ],
  spawns: [
    { x: 650, y: 360 },
    { x: 1250, y: 360 },
    { x: 650, y: 740 },
    { x: 1250, y: 740 },
    { x: 950, y: 330 },
    { x: 950, y: 770 },
  ],
  speed: 238,
  player_radius: 18,
  cast_lock: 0.72,
  respawn: 3,
  max_actions: 7,
  roll: { distance: 165, cooldown: 1.6, invuln: 0.22 },
  spell_costs: {
    fireball: 11,
    frostbolt: 9,
    dash: 10,
    blink: 17,
    shield: 17,
    heal: 24,
    nova: 21,
    ward: 15,
    beam: 50,
    spark_volley: 25,
    emp: 36,
    chain_lightning: 34,
    lightning_strike: 32,
    meteor: 38,
    siphon: 28,
    poison_cloud: 30,
  },
  tick_rate: 30,
};

const $ = (id) => document.getElementById(id);
const dom = {
  body: document.body,
  stage: $("stage"),
  canvas: $("gameCanvas"),
  loginForm: $("loginForm"),
  nameInput: $("nameInput"),
  joinButton: $("joinButton"),
  loginError: $("loginError"),
  lobbyStatus: $("lobbyStatus"),
  onlineCount: $("onlineCount"),
  onlinePill: $("onlinePill"),
  scoreList: $("scoreList"),
  killfeed: $("killfeed"),
  localHud: $("localHud"),
  hpFill: $("hpFill"),
  hpText: $("hpText"),
  manaFill: $("manaFill"),
  manaText: $("manaText"),
  hudName: $("hudName"),
  hudAlive: $("hudAlive"),
  respawnOverlay: $("respawnOverlay"),
  respawnTimer: $("respawnTimer"),
  hotbar: $("hotbar"),
  spellTabs: [...document.querySelectorAll(".spell-tab")],
  spellName: $("spellName"),
  codeInput: $("codeInput"),
  lineNumbers: $("lineNumbers"),
  codeLayer: $("codeLayer"),
  codeComplete: $("codeComplete"),
  codeCost: $("codeCost"),
  codeDiagnostic: $("codeDiagnostic"),
  pingValue: $("pingValue"),
  codeFilename: $("codeFilename"),
  spellsheetFilename: document.querySelector(".spell-file"),
  exampleSelect: $("exampleSelect"),
  apiButton: $("apiButton"),
  consoleOutput: $("consoleOutput"),
  consoleStatus: $("consoleStatus"),
  rollHint: $("rollHint"),
  cooldownLabel: $("cooldownLabel"),
  cooldownFill: $("cooldownFill"),
  castButton: $("castButton"),
  apiModal: $("apiModal"),
  codexModal: $("codexModal"),
  codexHost: $("codexHost"),
  codexRoot: $("codexRoot"),
  codexPanel: document.querySelector('[data-panel="codex"]'),
  codexToggle: $("codexToggle"),
  codexClose: $("codexClose"),
  apiClose: $("apiClose"),
  apiDone: $("apiDone"),
  loginApiButton: $("loginApiButton"),
  panelToggle: $("panelToggle"),
  panelClose: $("panelClose"),
  panelScrim: $("panelScrim"),
  grimoire: $("grimoire"),
  soundToggle: $("soundToggle"),
  connectionBanner: $("connectionBanner"),
  connectionText: $("connectionText"),
  toasts: $("toasts"),
  damageVignette: $("damageVignette"),
  loginOverlay: $("loginOverlay"),
  loginCard: $("loginCard"),
  modeCards: [...document.querySelectorAll(".mode-card")],
  loginFooterDot: document.querySelector(".login-footer .status-dot"),
  topbarDot: document.querySelector(".online-pill .status-dot"),
};

const client = {
  config: { ...DEFAULT_WORLD },
  joined: false,
  connected: false,
  selfId: null,
  selfName: "",
  selfColor: "#ffb86b",
  players: new Map(),
  projectiles: [],
  wards: [],
  emps: [],
  meteors: [],
  clouds: [],
  monsters: [],
  hazards: [],
  pickups: [],
  terminals: [],
  barriers: [],
  breakpoints: [],
  role: "",
  story: null,
  quest: null,
  terrainState: null,
  workshop: null,
  life: null,
  closedDoors: new Set(),
  mode: loadMode(),
  pointer: {
    x: window.innerWidth / 2,
    y: window.innerHeight / 2,
    inside: false,
    touch: false,
    joy: null,
  },
  aim: 0,
  prediction: { x: 950, y: 550, errorX: 0, errorY: 0, active: false, selfId: null },
  rtt: 0,
  spells: loadSpellbook(),
  checks: [{}, {}, {}],
  activeSlot: 0,
  cooldownEnd: 0,
  castPending: false,
  castIntent: null,
  rollCooldownEnd: 0,
  rollPending: false,
  lastStateAt: 0,
  hotCards: [],
};

const renderer = new ArenaRenderer(dom.canvas);
const sound = new SoundEngine(loadSoundEnabled());
const editor = new SpellEditor({
  input: dom.codeInput,
  layer: dom.codeLayer,
  gutter: dom.lineNumbers,
  popup: dom.codeComplete,
  costOf: (name) => client.config.spell_costs?.[name],
  isKnown: (name) => {
    const skill = client.config.skills?.[name];
    if (skill) return skill.open && skill.role === client.role;
    return client.config.runes ? client.config.runes.includes(name) : !STORY_ONLY.has(name);
  },
});
const story = new StoryUi({
  send: sendMessage,
  sound,
  toast: (text, kind) => showToast(text, kind),
  costOf: (name) => client.config.spell_costs?.[name],
  onTerminal: () => {
    client.castIntent = null;
    clearMovement();
  },
});

let socket = null;
let socketOpen = false;
let pendingJoinName = null;
let joinRequested = false;
let hasEnteredArena = false;
let fatalError = false;
let reconnectAttempts = 0;
let reconnectTimer = null;
let inputTimer = null;
let pingTimer = null;
let saveTimer = null;
let checkTimer = null;
let checkTicket = 0;
let consoleTimer = null;
let vignetteTimer = null;
let activeTouchId = null;
let modalReturnFocus = null;
let lastScoreSignature = "";
let lastCooldownSignature = "";
let lastHealthSignature = "";
let serverHello = null;
let hasShownWelcome = false;
let lastManaBand = "";
let pendingStoryName = "";
let partyCode = "";

// Local steps the server may not have applied yet: [{at, dx, dy}].
const moveLog = [];
const SNAP_DISTANCE = 170;
const TICK_MS = 1000 / 30;
const CAST_BUFFER_MS = 220;

const keyboardMove = { up: false, down: false, left: false, right: false };
const touchMove = { up: false, down: false, left: false, right: false };

const MOVE_KEYS = {
  KeyW: "up",
  ArrowUp: "up",
  KeyS: "down",
  ArrowDown: "down",
  KeyA: "left",
  ArrowLeft: "left",
  KeyD: "right",
  ArrowRight: "right",
};

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

function round(value, places = 0) {
  const factor = 10 ** places;
  return Math.round(value * factor) / factor;
}

function distanceBetween(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function localPlayer() {
  return client.selfId ? client.players.get(client.selfId) : null;
}

function isTypingTarget(target) {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

function socketIsOpen() {
  return Boolean(socket && socket.readyState === WebSocket.OPEN && socketOpen);
}

function mergeWorldConfig(config) {
  if (!config || typeof config !== "object") return;
  const next = { ...client.config, ...config };
  if (config.arena && typeof config.arena === "object") {
    next.arena = { ...client.config.arena, ...config.arena };
  }
  if (Array.isArray(config.obstacles)) next.obstacles = config.obstacles;
  if (Array.isArray(config.spawns)) next.spawns = config.spawns;
  if (config.spell_costs && typeof config.spell_costs === "object") {
    next.spell_costs = { ...client.config.spell_costs, ...config.spell_costs };
  }
  if (config.roll && typeof config.roll === "object") {
    next.roll = { ...client.config.roll, ...config.roll };
  }
  client.config = next;
}

/** The client's copy of the dungeon check, so walking feels instant. */
function canStandInDungeon(x, y, radius) {
  const { tiles, tile } = client.config;
  const left = Math.floor((x - radius) / tile);
  const right = Math.floor((x + radius) / tile);
  const top = Math.floor((y - radius) / tile);
  const bottom = Math.floor((y + radius) / tile);
  for (let ty = top; ty <= bottom; ty += 1) {
    for (let tx = left; tx <= right; tx += 1) {
      const open = tiles[ty]?.[tx] === "." && !client.closedDoors.has(`${tx},${ty}`);
      if (open) continue;
      const nearestX = clamp(x, tx * tile, (tx + 1) * tile);
      const nearestY = clamp(y, ty * tile, (ty + 1) * tile);
      if ((x - nearestX) ** 2 + (y - nearestY) ** 2 < radius * radius) return false;
    }
  }
  return true;
}

function canStand(x, y) {
  const arena = client.config.arena;
  const border = arena.border;
  const radius = client.config.player_radius || 18;
  if (client.config.tiles) return canStandInDungeon(x, y, radius);
  if (
    x < border + radius ||
    x > arena.w - border - radius ||
    y < border + radius ||
    y > arena.h - border - radius
  ) {
    return false;
  }
  for (const obstacle of client.config.obstacles || []) {
    if (Math.hypot(x - obstacle.x, y - obstacle.y) < obstacle.r + radius) {
      return false;
    }
  }
  return true;
}

// -------------------------------------------------------------------- network
function connect() {
  if (fatalError) return;
  if (socket && (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN)) {
    return;
  }
  if (reconnectTimer) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  updateLoginStatus("Портал открывается…", true);
  if (!hasEnteredArena) setLoginError("");
  let ws;
  try {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
  } catch {
    scheduleReconnect();
    return;
  }
  socket = ws;
  socketOpen = false;

  ws.addEventListener("open", () => {
    if (socket !== ws) return;
    socketOpen = true;
    client.connected = true;
    reconnectAttempts = 0;
    refreshJoinButton();
    updateLoginStatus("Портал открыт. Входите.", false);
    setTopbarConnection(true);
    sendPing();
    client.spells.forEach((_, slot) => sendCheck(slot));
    if (pendingStoryName) {
      sendProfile();
    } else if (hasEnteredArena) {
      showConnectionBanner("Портал найден. Возвращаюсь…");
      const name = client.selfName || loadMageName();
      if (name) sendJoinNow(name);
    } else if (pendingJoinName) {
      sendJoinNow(pendingJoinName);
    }
  });

  ws.addEventListener("message", (event) => {
    if (typeof event.data !== "string") return;
    let message;
    try {
      message = JSON.parse(event.data);
    } catch {
      return;
    }
    if (!message || typeof message !== "object") return;
    handleServerMessage(message);
  });

  ws.addEventListener("close", () => {
    if (socket !== ws) return;
    socket = null;
    socketOpen = false;
    client.connected = false;
    joinRequested = false;
    client.castPending = false;
    client.rollPending = false;
    client.rollCooldownEnd = 0;
    client.castIntent = null;
    client.rtt = 0;
    dom.pingValue.hidden = true;
    clearMovement(false);
    updateSelfHud(localPlayer());
    setTopbarConnection(false);
    refreshJoinButton();
    refreshCooldownUi(performance.now(), true);
    if (hasEnteredArena || pendingStoryName) {
      showConnectionBanner("Связь с ареной потеряна. Восстанавливаю портал…");
    } else {
      updateLoginStatus("Портал закрыт. Открываю заново…", true);
    }
    scheduleReconnect();
  });

  ws.addEventListener("error", () => {
    /* The close event carries the retry logic. */
  });
}

function sendMessage(message) {
  if (!socketIsOpen()) {
    showToast("Нет связи с порталом.", "error");
    return;
  }
  try {
    socket.send(JSON.stringify(message));
  } catch {
    /* The socket close handler will restore the portal. */
  }
}

function sendProfile() {
  sendMessage({ t: "profile", token: loadToken(), name: pendingStoryName });
}

function scheduleReconnect() {
  if (fatalError || reconnectTimer) return;
  const delay = Math.min(900 * 1.7 ** reconnectAttempts, 8000);
  reconnectAttempts += 1;
  if (hasEnteredArena) {
    showConnectionBanner(
      `Связь потеряна. Новая попытка через ${Math.max(1, Math.ceil(delay / 1000))} с…`,
    );
  }
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, delay);
}

function sendJoinNow(name) {
  if (!socketIsOpen() || joinRequested) return;
  const clean = String(name || "").trim().slice(0, 16);
  if (clean.length < 2) return;
  joinRequested = true;
  pendingJoinName = clean;
  setLoginError("");
  refreshJoinButton();
  try {
    socket.send(JSON.stringify({ t: "join", name: clean }));
  } catch {
    joinRequested = false;
    pendingJoinName = clean;
    try {
      socket.close();
    } catch {
      /* noop */
    }
  }
}

function handleServerMessage(message) {
  switch (message.t) {
    case "hello": {
      serverHello = message;
      client.connected = true;
      setTopbarConnection(true);
      const humans = Number(message.online) || 0;
      const bots = Number(message.bots) || 0;
      setTopbarOnline(humans + bots);
      updateLoginStatus(
        humans + bots > 0
          ? `Портал открыт · ${humans + bots} в сети`
          : "Портал открыт. Входите.",
        false,
      );
      refreshJoinButton();
      break;
    }
    case "welcome": {
      const returning = hasEnteredArena;
      hasEnteredArena = true;
      hasShownWelcome = true;
      joinRequested = false;
      pendingJoinName = null;
      client.joined = true;
      client.connected = true;
      client.selfId = Number(message.you) || null;
      client.selfName = String(message.name || "Маг");
      client.selfColor = String(message.color || "#ffb86b");
      mergeWorldConfig(message.config);
      saveMageName(client.selfName);
      dom.nameInput.value = client.selfName;
      dom.hudName.textContent = client.selfName;
      dom.body.classList.add("in-game");
      dom.loginOverlay.setAttribute("aria-hidden", "true");
      dom.connectionBanner.hidden = true;
      dom.loginError.textContent = "";
      setTopbarConnection(true);
      if (message.online) {
        setTopbarOnline(
          Number(message.online.online) || Number(message.online.humans) || 0,
        );
      }
      if (client.prediction.selfId !== client.selfId) {
        client.prediction.selfId = client.selfId;
        client.prediction.active = false;
      }
      client.castPending = false;
      client.cooldownEnd = 0;
      client.rollCooldownEnd = 0;
      client.rollPending = false;
      refreshJoinButton();
      refreshCooldownUi(performance.now(), true);
      addConsoleEntry(
        returning
          ? "Связь с ареной восстановлена. Ваш гримуар снова готов."
          : "Портал открыт. Гримуар готов к работе.",
        "system",
      );
      if (returning) showToast("Связь с ареной восстановлена.", "combat");
      sound.play("join");
      if (document.activeElement instanceof HTMLElement) {
        document.activeElement.blur();
      }
      break;
    }
    case "state": {
      client.connected = true;
      handleState(message);
      break;
    }
    case "cast_result": {
      handleCastResult(message);
      break;
    }
    case "check_result": {
      handleCheckResult(message);
      break;
    }
    case "profile": {
      handleProfile(message);
      break;
    }
    case "profile_update": {
      story.updateProfile(message.profile);
      if (message.error) showToast(message.error, "error");
      else sound.play("heal");
      break;
    }
    case "party": {
      partyCode = String(message.code || "");
      story.setParty(message);
      break;
    }
    case "party_left": {
      partyCode = "";
      story.clearParty();
      break;
    }
    case "party_error": {
      story.setError(String(message.error || "Портал не пропустил вас."));
      break;
    }
    case "stage_start": {
      enterDungeon(message);
      break;
    }
    case "stage_end": {
      leaveDungeon(message);
      break;
    }
    case "terminal_state": {
      story.terminalState(message);
      break;
    }
    case "terminal_help": {
      story.terminalHelp(message);
      break;
    }
    case "fix_result": {
      story.fixResult(message);
      break;
    }
    case "interact_result": {
      if (message.error) showToast(String(message.error), "error");
      break;
    }
    case "roll_result": {
      handleRollResult(message);
      break;
    }
    case "join_error": {
      joinRequested = false;
      client.castPending = false;
      client.rollPending = false;
      const text =
        typeof message.error === "string"
          ? message.error
          : "Портал не пропустил вас.";
      if (hasEnteredArena) {
        showToast(text, "error");
        showConnectionBanner("Не удалось вернуться. Обновите страницу.");
      } else {
        pendingJoinName = null;
        setLoginError(text);
        updateLoginStatus("Портал открыт. Входите.", false);
      }
      refreshJoinButton();
      break;
    }
    case "notice": {
      const text = String(message.text || "").slice(0, 220);
      if (text) showToast(text);
      break;
    }
    case "fatal": {
      fatalError = true;
      stopNetworkTimers();
      joinRequested = false;
      client.castPending = false;
      client.rollPending = false;
      pendingJoinName = null;
      const text =
        typeof message.error === "string"
          ? message.error
          : "Арена закрыла портал.";
      showToast(text, "error");
      setLoginError(text);
      showConnectionBanner(text);
      updateLoginStatus(text, true);
      refreshJoinButton();
      refreshCooldownUi(performance.now(), true);
      try {
        socket?.close(4000, "fatal");
      } catch {
        /* noop */
      }
      break;
    }
    case "pong": {
      if (typeof message.at !== "number") break;
      const sample = Math.max(0, performance.now() - message.at);
      client.rtt = client.rtt ? client.rtt * 0.7 + sample * 0.3 : sample;
      dom.pingValue.textContent = `${Math.round(client.rtt)} мс`;
      dom.pingValue.hidden = false;
      break;
    }
    default:
      break;
  }
}

function sendInputNow() {
  if (!socketIsOpen() || !client.joined) return;
  const movement = combinedMovement();
  try {
    socket.send(
      JSON.stringify({
        t: "input",
        up: movement.up,
        down: movement.down,
        left: movement.left,
        right: movement.right,
        aim: round(client.aim, 4),
      }),
    );
  } catch {
    /* The socket close handler will restore the portal. */
  }
}

function sendPing() {
  if (!socketIsOpen()) return;
  try {
    socket.send(JSON.stringify({ t: "ping", at: performance.now() }));
  } catch {
    /* noop */
  }
}

// ---------------------------------------------------------------- game state
function handleState(message) {
  client.connected = true;
  client.lastStateAt = performance.now();
  const nextPlayers = new Map();
  if (Array.isArray(message.players)) {
    for (const player of message.players) {
      if (!player || typeof player.id !== "number") continue;
      nextPlayers.set(player.id, player);
    }
  }
  client.players = nextPlayers;
  client.projectiles = Array.isArray(message.projectiles) ? message.projectiles : [];
  client.wards = Array.isArray(message.wards) ? message.wards : [];
  client.emps = Array.isArray(message.emps) ? message.emps : [];
  client.meteors = Array.isArray(message.meteors) ? message.meteors : [];
  client.clouds = Array.isArray(message.clouds) ? message.clouds : [];
  client.monsters = Array.isArray(message.monsters) ? message.monsters : [];
  client.hazards = Array.isArray(message.hazards) ? message.hazards : [];
  client.pickups = Array.isArray(message.pickups) ? message.pickups : [];
  client.terminals = Array.isArray(message.terminals) ? message.terminals : [];
  client.barriers = Array.isArray(message.barriers) ? message.barriers : [];
  client.breakpoints = Array.isArray(message.breakpoints) ? message.breakpoints : [];
  client.story = message.story || null;
  client.quest = message.quest || null;
  client.terrainState = message.terrain || null;
  client.workshop = message.workshop || null;
  client.life = message.life || null;
  client.bossMoves = message.boss_moves || [];
  if (client.story) {
    client.closedDoors = new Set(client.story.doors.map(([x, y]) => `${x},${y}`));
    story.updateHud(message, client.selfId);
  }

  if (message.stats && typeof message.stats === "object") {
    const online =
      Number(message.stats.online) ||
      (Number(message.stats.humans) || 0) + (Number(message.stats.bots) || 0);
    setTopbarOnline(online);
  }

  const me = localPlayer();
  if (me) {
    client.selfName = me.name || client.selfName;
    client.selfColor = me.color || client.selfColor;
    dom.hudName.textContent = client.selfName;
    const rollReadyIn = Number(me.roll_ready_in);
    if (Number.isFinite(rollReadyIn) && rollReadyIn > 0) {
      client.rollCooldownEnd = Math.max(
        client.rollCooldownEnd,
        performance.now() + rollReadyIn * 1000,
      );
    }
  }
  updateSelfHud(me);
  updateScoreboard([...client.players.values()]);
  processEvents(message.events);
  reconcilePrediction();
}

function processEvents(events) {
  if (!Array.isArray(events)) return;
  for (const event of events) {
    if (!event || typeof event !== "object") continue;
    renderer.handleEvent(event, client);
    handleEventFeedback(event);
    story.handleEvent(event, client.selfId);
  }
}

function eventPosition(event) {
  if (typeof event.x === "number" && typeof event.y === "number") {
    return { x: event.x, y: event.y };
  }
  const target = client.players.get(event.id);
  if (target) return { x: target.x, y: target.y };
  return null;
}

function isNearLocal(event, range = 950) {
  const local = localPlayer();
  if (!local) return false;
  if (event.id === client.selfId || event.killer_id === client.selfId) return true;
  const position = eventPosition(event);
  if (!position) return false;
  return Math.hypot(local.x - position.x, local.y - position.y) <= range;
}

function handleEventFeedback(event) {
  const kind = event.e;
  const selfId = client.selfId;
  const near = isNearLocal(event);

  switch (kind) {
    case "cast":
      if (near) sound.play(event.kind === "frost" ? "frost" : "fire");
      break;
    case "impact":
      if (near) sound.play("impact");
      break;
    case "fix_done":
      sound.play(event.pgt ? "error" : "respawn");
      break;
    case "folk_done":
      sound.play(event.status === "passed" ? "respawn" : "error");
      break;
    case "quest_item":
    case "quest_catch":
    case "plate_on":
    case "packet_take":
      sound.play("ward");
      break;
    case "zone_on":
    case "npc_found":
    case "unit_up":
      sound.play("shield");
      break;
    case "quest_burst":
      sound.play("poison");
      break;
    case "ns_forged":
      sound.play("error");
      break;
    case "quest_note":
      if (near) sound.play("click");
      break;
    case "memory_oom":
      sound.play("death-near");
      break;
    case "memory_free":
      sound.play("respawn");
      break;
    case "plate_fail":
    case "zones_fail":
      sound.play("error");
      break;
    case "quest_step":
    case "exit_open":
    case "reveal":
      if (kind !== "reveal" || near) sound.play(kind === "reveal" ? "click" : "join");
      break;
    case "quest_done":
    case "rest":
      sound.play("respawn");
      break;
    case "loot":
      sound.play("heal");
      break;
    case "unit_down":
      sound.play("death-near");
      break;
    case "deal":
      sound.play("emp");
      break;
    case "heat":
      sound.play("hurt");
      break;
    case "tiles":
      patchTiles(event.rects || [], String(event.char || "."));
      sound.play("respawn");
      break;
    case "link_jump":
      if (event.id === selfId) placePrediction(event.x, event.y);
      if (near) sound.play("dash");
      break;
    case "prop_break":
      if (near) sound.play("impact");
      break;
    case "prop_blast":
      if (near) sound.play("meteor_impact");
      break;
    case "surface_shock":
      if (near) sound.play("lightning");
      break;
    case "surface_ice":
      if (near) sound.play("frost");
      break;
    case "surface_burn":
      if (near) sound.play("fire");
      break;
    case "workshop_open":
    case "relic_found":
    case "find_taken":
      sound.play("respawn");
      break;
    case "finds_offered":
    case "event_start":
      sound.play("join");
      break;
    case "gust":
      sound.play("dash");
      break;
    case "rollback":
      if (event.id === selfId) placePrediction(event.x, event.y);
      sound.play("respawn");
      break;
    case "spell_log":
      if (event.id === selfId) showDaemonLog(event);
      break;
    case "daemon":
      if (event.id === selfId) {
        addConsoleEntry(`Демон запущен на ${event.time} с.`, "dim");
        sound.play("emp_pull");
      }
      break;
    case "daemon_end":
      if (event.id === selfId) addConsoleEntry("Демон завершил работу.", "dim");
      break;
    case "ping":
      if (event.id === selfId) sound.play("click");
      break;
    case "gc":
    case "grep":
      if (event.id === selfId) sound.play("emp_pull");
      break;
    case "caught":
      sound.play("respawn");
      break;
    case "patch":
      sound.play("heal");
      break;
    case "sudo":
      sound.play("shield");
      break;
    case "segfault":
      sound.play("nova");
      break;
    case "hijack":
    case "scan":
      sound.play("emp_pull");
      break;
    case "breakpoint":
      sound.play("frost");
      break;
    case "gate_open":
      sound.play("emp");
      break;
    case "gate_lift":
      sound.play("emp_blast");
      break;
    case "hit": {
      if (event.id === selfId) {
        if ((Number(event.amount) || 0) > 0) flashVignette("hit");
        sound.play("hurt");
        renderer.shake(4);
      } else if (near) {
        sound.play("hit");
      }
      break;
    }
    case "death": {
      addKillfeed(event);
      if (selfId && event.killer_id === selfId && event.id !== selfId) {
        const streak = Number(event.streak) || 0;
        showToast(
          streak >= 2
            ? `${event.name} повержен · серия ${streak}`
            : `${event.name} повержен`,
          "combat",
        );
      }
      if (event.id === selfId) {
        client.prediction.active = false;
        client.castIntent = null;
        clearMovement();
        flashVignette("hit");
        if (!client.story) updateRespawnOverlay(event.respawn_in ?? 3);
        showToast(`Вас поверг ${event.killer || "Арена"}.`, "error");
        sound.play("death");
      } else if (near) {
        sound.play("death-near");
      }
      break;
    }
    case "respawn": {
      if (event.id === selfId && typeof event.x === "number") {
        placePrediction(event.x, event.y);
        client.prediction.selfId = selfId;
        client.rollCooldownEnd = 0;
        client.rollPending = false;
        updateRespawnOverlay(0);
        sound.play("respawn");
      }
      break;
    }
    case "dash":
      if (event.id === selfId && typeof event.to_x === "number") {
        placePrediction(event.to_x, event.to_y);
      }
      if (near) sound.play("dash");
      break;
    case "roll":
      if (event.id === selfId && typeof event.x2 === "number") {
        placePrediction(event.x2, event.y2);
        client.rollPending = false;
      }
      if (near) sound.play("roll");
      break;
    case "shield":
      if (near) sound.play("shield");
      break;
    case "heal":
      if (event.id === selfId && Number(event.amount) > 0) flashVignette("heal");
      if (near) sound.play("heal");
      break;
    case "nova":
      if (near) sound.play("nova");
      break;
    case "beam":
      if (near) sound.play("beam");
      break;
    case "chain_lightning":
      if (near) sound.play("chain");
      break;
    case "lightning_strike":
      if (near) sound.play("lightning");
      break;
    case "meteor":
      if (near) sound.play("meteor");
      break;
    case "meteor_impact":
      if (near) sound.play("meteor_impact");
      break;
    case "siphon":
      if (near) sound.play("siphon");
      break;
    case "poison_cloud":
      if (near) sound.play("poison");
      break;
    case "poison_tick":
      if (near) sound.play("poison_tick");
      break;
    case "cloud_fade":
      if (near) sound.play("cloud_fade");
      break;
    case "emp":
      if (near) sound.play("emp");
      break;
    case "emp_pull":
      if (near) sound.play("emp_pull");
      break;
    case "emp_blast":
      if (near) sound.play("emp_blast");
      break;
    case "ward":
      if (near) sound.play("ward");
      break;
    case "ward_blast":
      if (near) sound.play("ward_blast");
      break;
    case "ward_fade":
      if (near) sound.play("ward_fade");
      break;
    case "say":
      if (event.id === selfId) sound.play("click");
      break;
    default:
      break;
  }
}

function showDaemonLog(event) {
  (event.log || []).forEach((line) => addConsoleEntry(String(line), "log"));
  if (event.error) {
    addConsoleEntry(String(event.error), "error");
    const tip = story.clipTip(event.error);
    if (tip) addConsoleEntry(tip, "dim");
  }
}

function handleCastResult(message) {
  client.castPending = false;
  const cooldown = Math.max(0, Number(message.cooldown) || 0);
  if (message.ok) {
    client.cooldownEnd = performance.now() + (cooldown ? cooldown * 1000 : castLockMs());
  } else if (cooldown > 0) {
    client.cooldownEnd = Math.max(
      client.cooldownEnd,
      performance.now() + cooldown * 1000,
    );
  }

  const logs = Array.isArray(message.log) ? message.log : [];
  for (const line of logs) {
    addConsoleEntry(String(line), "log");
  }
  if (message.ok) {
    setConsoleStatus("исполнено", "");
    const actions = Number(message.actions) || 0;
    if (!logs.length) {
      if (actions > 0) {
        addConsoleEntry(
          `Исполнено действий: ${actions}.`,
          "dim",
        );
      } else {
        addConsoleEntry("Заклинание не произвело действий.", "dim");
      }
    } else if (actions > 0) {
      addConsoleEntry(`Действий: ${actions}.`, "dim");
    }
  } else {
    const error = String(message.error || "Заклинание рассеялось.");
    // A held button must not keep firing a spell that just failed.
    client.castIntent = null;
    addConsoleEntry(error, "error");
    const tip = story.clipTip(error);
    if (tip) addConsoleEntry(tip, "dim");
    setConsoleStatus("ошибка", "error");
    showToast(error, "error");
    sound.play("error");
    if (message.slot === client.activeSlot) showDiagnostic(error);
  }
  refreshCooldownUi(performance.now(), true);
}

// --------------------------------------------------------------------- story
function chooseMode(mode) {
  client.mode = mode;
  saveMode(mode);
  dom.modeCards.forEach((card) => {
    const active = card.dataset.mode === mode;
    card.classList.toggle("active", active);
    card.setAttribute("aria-checked", String(active));
  });
  refreshJoinButton();
}

function setupModes() {
  dom.modeCards.forEach((card) => {
    card.addEventListener("click", () => {
      sound.unlock();
      sound.play("click");
      chooseMode(card.dataset.mode);
    });
  });
  chooseMode(client.mode);
}

function useModeSpellbook(mode) {
  saveSpellbookNow();
  useSpellbook(mode);
  client.spells = loadSpellbook();
  client.checks = [{}, {}, {}];
  selectSlot(0, { force: true, skipSave: true });
  renderHotbar();
  client.spells.forEach((_, slot) => sendCheck(slot));
}

function beginStory(name) {
  pendingStoryName = name;
  if (socketIsOpen()) sendProfile();
  else connect();
}

function handleProfile(message) {
  dom.connectionBanner.hidden = true;
  dom.body.classList.add("in-camp");
  useModeSpellbook("story");
  story.setProfile(message);
  for (const role of message.roles?.roles || []) {
    if (EXAMPLES.some((example) => example.role === role.key)) continue;
    EXAMPLES.push({ name: `Роль: ${role.title}`, code: role.example, role: role.key });
  }
  // A dropped connection walks straight back to its seat.
  if (partyCode) sendMessage({ t: "party_join", code: partyCode });
}

function enterDungeon(message) {
  client.config = { ...DEFAULT_WORLD };
  // The world's runes are the party's; what a mage bought is theirs alone.
  message.config.runes = [...new Set([...(message.config.runes || []), ...(message.book || [])])];
  mergeWorldConfig(message.config);
  client.selfId = Number(message.you) || null;
  client.joined = true;
  client.players = new Map();
  client.monsters = [];
  client.hazards = [];
  client.pickups = [];
  client.terminals = [];
  client.barriers = [];
  client.breakpoints = [];
  client.quest = null;
  client.terrainState = null;
  client.workshop = null;
  client.bossMoves = [];
  client.life = null;
  client.story = null;
  client.role = String(message.role || "");
  client.projectiles = [];
  client.wards = [];
  client.emps = [];
  client.meteors = [];
  client.clouds = [];
  client.closedDoors = new Set();
  client.prediction.active = false;
  client.prediction.selfId = null;
  moveLog.length = 0;
  lastScoreSignature = "";
  const start = message.config.rooms?.[0];
  if (start) {
    const { tile } = message.config;
    renderer.resetScene((start.x + start.w / 2) * tile, (start.y + start.h / 2) * tile);
  }
  dom.body.classList.remove("in-camp");
  dom.body.classList.add("in-game", "story-mode");
  dom.hudName.textContent = pendingStoryName || client.selfName;
  story.enterStage(message);
  rebuildExamples();
  editor.closeCompletion();
  refreshCooldownUi(performance.now(), true);
  sound.play("join");
}

function leaveDungeon(message) {
  client.joined = false;
  client.selfId = null;
  client.castIntent = null;
  client.cooldownEnd = 0;
  clearMovement(false);
  dom.body.classList.remove("in-game", "story-mode");
  dom.body.classList.add("in-camp");
  dom.respawnOverlay.hidden = true;
  story.leaveStage();
  story.setResult(message);
  story.showCamp();
  sound.play(message.result === "cleared" ? "respawn" : "death");
}

// ---------------------------------------------------------------- spell check
function errorLine(text) {
  const match = String(text || "").match(/^Строка (\d+):/);
  return match ? Number(match[1]) : null;
}

function showDiagnostic(error) {
  dom.codeDiagnostic.hidden = !error;
  dom.codeDiagnostic.textContent = error || "";
  editor.setErrorLine(errorLine(error));
}

function costLabel(cost) {
  if (!Array.isArray(cost)) return "";
  const [low, high] = cost;
  return low === high ? String(low) : `${low}–${high}`;
}

function sendCheck(slot) {
  const spell = client.spells[slot];
  if (!spell || !socketIsOpen()) return;
  checkTicket += 1;
  client.checks[slot].ticket = checkTicket;
  try {
    socket.send(
      JSON.stringify({ t: "check", slot, ticket: checkTicket, code: spell.code }),
    );
  } catch {
    /* The socket close handler will restore the portal. */
  }
}

function scheduleCheck() {
  if (checkTimer) window.clearTimeout(checkTimer);
  const slot = client.activeSlot;
  checkTimer = window.setTimeout(() => {
    checkTimer = null;
    sendCheck(slot);
  }, 280);
}

function handleCheckResult(message) {
  const check = client.checks[message.slot];
  if (!check || message.ticket !== check.ticket) return;
  check.ok = Boolean(message.ok);
  check.error = message.ok ? "" : String(message.error || "");
  if (message.ok) check.cost = message.cost;
  if (message.slot === client.activeSlot) showCheck();
  refreshHotbarCosts();
}

function showCheck() {
  const check = client.checks[client.activeSlot] || {};
  showDiagnostic(check.error);
  const label = costLabel(check.cost);
  dom.codeCost.textContent = label ? `${label} ◆` : "";
  dom.codeCost.classList.toggle("stale", Boolean(check.error));
}

function refreshHotbarCosts() {
  client.hotCards.forEach((card, index) => {
    const check = client.checks[index] || {};
    const cost = card.querySelector(".hot-cost");
    if (cost) cost.textContent = check.error ? "ошибка" : costLabel(check.cost);
    card.classList.toggle("broken", Boolean(check.error));
  });
  lastManaBand = "";
}

function castLockMs() {
  const lock = Number(localPlayer()?.cast_lock) || Number(client.config.cast_lock) || 0.72;
  return Math.max(0.1, lock) * 1000;
}

function handleRollResult(message) {
  client.rollPending = false;
  const cooldown = Math.max(0, Number(message.cooldown) || 0);
  if (message.ok) {
    if (cooldown > 0) {
      client.rollCooldownEnd = Math.max(
        client.rollCooldownEnd,
        performance.now() + cooldown * 1000,
      );
    }
  } else {
    const error = String(message.error || "Перекат не удался.");
    if (cooldown > 0) {
      client.rollCooldownEnd = Math.max(
        client.rollCooldownEnd,
        performance.now() + cooldown * 1000,
      );
    } else {
      client.rollCooldownEnd = 0;
    }
    if (!error.includes("восстанавливается")) {
      showToast(error, "error");
      sound.play("error");
    }
  }
  refreshCooldownUi(performance.now(), true);
}

function placePrediction(x, y) {
  const prediction = client.prediction;
  prediction.x = x;
  prediction.y = y;
  prediction.errorX = 0;
  prediction.errorY = 0;
  prediction.active = true;
  moveLog.length = 0;
}

/**
 * Compare the local mage with the server's, allowing for the steps still in
 * flight: a snapshot is one round trip old, so replaying what we did since
 * then shows where the server will have us. What remains is a real difference
 * (knockback, a pull, a shove from another mage) and is eased in by frames.
 */
function reconcilePrediction() {
  const me = localPlayer();
  if (!me || me.dead) {
    client.prediction.active = false;
    return;
  }
  const prediction = client.prediction;
  if (prediction.selfId !== client.selfId || !prediction.active) {
    placePrediction(me.x, me.y);
    prediction.selfId = client.selfId;
    return;
  }
  if (me.stun) {
    placePrediction(me.x, me.y);
    return;
  }
  const horizon = performance.now() - clamp(client.rtt + TICK_MS, TICK_MS, 400);
  while (moveLog.length && moveLog[0].at < horizon) moveLog.shift();

  let x = me.x;
  let y = me.y;
  for (const step of moveLog) {
    if (canStand(x + step.dx, y)) x += step.dx;
    if (canStand(x, y + step.dy)) y += step.dy;
  }
  const errorX = x - prediction.x;
  const errorY = y - prediction.y;
  if (Math.hypot(errorX, errorY) > SNAP_DISTANCE) {
    placePrediction(me.x, me.y);
  } else {
    prediction.errorX = errorX;
    prediction.errorY = errorY;
  }
}

function updatePrediction(dt) {
  if (!client.prediction.active || !client.connected || !client.joined) return;
  const me = localPlayer();
  if (!me || me.dead) {
    client.prediction.active = false;
    return;
  }
  const prediction = client.prediction;
  const pull = 1 - Math.exp(-dt * 10);
  prediction.x += prediction.errorX * pull;
  prediction.y += prediction.errorY * pull;
  prediction.errorX *= 1 - pull;
  prediction.errorY *= 1 - pull;
  if (me.stun) return;

  const movement = combinedMovement();
  const dx = Number(movement.right) - Number(movement.left);
  const dy = Number(movement.down) - Number(movement.up);
  rideBelts(prediction, dt);
  if (!dx && !dy) return;
  const length = Math.hypot(dx, dy) || 1;
  const speed = (Number(me.speed) || Number(client.config.speed) || 238) * (me.slow ? 0.58 : 1);
  const radius = client.config.player_radius || 18;
  const { arena } = client.config;
  const startX = prediction.x;
  const startY = prediction.y;

  const nextX = clamp(
    startX + (dx / length) * speed * dt,
    arena.border + radius,
    arena.w - arena.border - radius,
  );
  if (canStand(nextX, startY)) prediction.x = nextX;
  const nextY = clamp(
    startY + (dy / length) * speed * dt,
    arena.border + radius,
    arena.h - arena.border - radius,
  );
  if (canStand(prediction.x, nextY)) prediction.y = nextY;

  moveLog.push({
    at: performance.now(),
    dx: prediction.x - startX,
    dy: prediction.y - startY,
  });
}

/** A conveyor carries everyone, whether or not they are walking. */
function rideBelts(prediction, dt) {
  const belts = client.config.terrain?.belts;
  if (!belts?.length) return;
  for (const [x, y, w, h, vx, vy] of belts) {
    if (prediction.x < x || prediction.x > x + w || prediction.y < y || prediction.y > y + h) continue;
    const startX = prediction.x;
    const startY = prediction.y;
    if (canStand(startX + vx * dt, startY)) prediction.x = startX + vx * dt;
    if (canStand(prediction.x, startY + vy * dt)) prediction.y = startY + vy * dt;
    moveLog.push({ at: performance.now(), dx: prediction.x - startX, dy: prediction.y - startY });
  }
}

/** A wall gave way or a bridge was laid: the map changes, for walking and for the eye. */
function patchTiles(rects, char) {
  const rows = client.config.tiles;
  if (!rows) return;
  for (const [x, y, w, h] of rects) {
    for (let row = y; row < y + h; row += 1) {
      const line = rows[row];
      if (line === undefined) continue;
      rows[row] = line.slice(0, x) + char.repeat(w) + line.slice(x + w);
    }
  }
  client.config.tilesVersion = (client.config.tilesVersion || 0) + 1;
}

function updateAimFromPointer() {
  if (!client.joined) return;
  const me = localPlayer();
  if (!me || me.dead) return;
  const position = client.prediction.active ? client.prediction : me;
  if (client.pointer.touch) {
    const joy = client.pointer.joy;
    if (joy && joy.magnitude > 0.18) {
      client.aim = Math.atan2(joy.dy, joy.dx);
    }
  } else if (client.pointer.inside) {
    const point = renderer.screenToWorld(client.pointer.x, client.pointer.y);
    const angle = Math.atan2(point.y - position.y, point.x - position.x);
    if (Number.isFinite(angle)) client.aim = ((angle % TAU) + TAU) % TAU;
  }
}

function pointerWorldPoint() {
  if (!client.pointer.inside || client.pointer.touch) return null;
  return renderer.screenToWorld(client.pointer.x, client.pointer.y);
}

// ------------------------------------------------------------------------ UI
function updateSelfHud(me) {
  if (!me) {
    updateRespawnOverlay(0);
    return;
  }
  const hp = Math.max(0, Number(me.hp) || 0);
  const mana = Math.max(0, Number(me.mana) || 0);
  const hpShare = clamp((hp / (Number(me.max_hp) || 100)) * 100, 0, 100);
  const manaShare = clamp((mana / (Number(me.max_mana) || 100)) * 100, 0, 100);
  const dead = Boolean(me.dead);
  const stunned = Boolean(me.stun) && !dead;
  dom.hpFill.style.width = `${hpShare}%`;
  dom.manaFill.style.width = `${manaShare}%`;
  const healthSignature =
    `${Math.round(hp)}:${Math.round(mana)}:${dead}:${stunned}:${client.connected}`;
  if (healthSignature !== lastHealthSignature) {
    lastHealthSignature = healthSignature;
    dom.hpText.textContent = String(Math.round(hp));
    dom.manaText.textContent = String(Math.round(mana));
    dom.localHud.classList.toggle("low-health", !dead && hpShare < 36);
    dom.hudAlive.classList.toggle("dead", dead || !client.connected);
    dom.hudAlive.textContent = !client.connected
      ? "НЕТ СВЯЗИ"
      : dead
        ? "ПАЛ"
        : stunned
          ? "ОГЛУШЕН"
          : "В БОЮ";
  }
  dom.hudName.textContent = me.name || client.selfName || "Безымянный";
  if (dead && client.story) {
    updateRespawnOverlay(0);
  } else if (dead) {
    updateRespawnOverlay(Math.max(0, Number(me.respawn_in) || 0));
  } else {
    updateRespawnOverlay(0);
  }
}

function updateRespawnOverlay(seconds) {
  const active = Number(seconds) > 0;
  if (active) {
    dom.respawnOverlay.hidden = false;
    dom.respawnTimer.textContent = Number(seconds).toFixed(1);
  } else {
    dom.respawnOverlay.hidden = true;
  }
}

function updateScoreboard(players) {
  const sorted = [...players].sort((a, b) => {
    if ((b.score || 0) !== (a.score || 0)) return (b.score || 0) - (a.score || 0);
    if ((a.deaths || 0) !== (b.deaths || 0)) return (a.deaths || 0) - (b.deaths || 0);
    return String(a.name || "").localeCompare(String(b.name || ""), "ru");
  });
  const signature =
    `${client.selfId}|` +
    sorted
      .map((player) => `${player.id}:${player.score || 0}:${player.deaths || 0}:${player.name}`)
      .join("|");
  if (signature === lastScoreSignature) return;
  lastScoreSignature = signature;

  dom.scoreList.replaceChildren();
  if (!sorted.length) return;
  const entries = sorted.slice(0, 8).map((player, index) => ({ player, rank: index + 1 }));
  const selfEntry = sorted.find((player) => player.id === client.selfId);
  if (selfEntry && !entries.some((entry) => entry.player.id === selfEntry.id)) {
    entries.push({ player: selfEntry, rank: sorted.indexOf(selfEntry) + 1 });
  }

  const fragment = document.createDocumentFragment();
  for (const { player, rank } of entries) {
    const row = document.createElement("li");
    row.className = "score-row";
    if (player.id === client.selfId) row.classList.add("me");
    if (player.bot) row.classList.add("bot");
    row.title = `${player.name} · побед: ${player.score || 0} · смертей: ${player.deaths || 0}`;

    const rankElement = document.createElement("span");
    rankElement.className = "score-rank";
    rankElement.textContent = String(rank).padStart(2, "0");

    const nameElement = document.createElement("span");
    nameElement.className = "score-name";
    const color = document.createElement("span");
    color.className = "score-color";
    color.style.setProperty("--player-color", player.color || "#a997ff");
    const label = document.createElement("span");
    label.textContent = player.name || "Маг";
    nameElement.append(color, label);

    const scoreElement = document.createElement("span");
    scoreElement.className = "score-score";
    scoreElement.textContent = String(player.score || 0);

    row.append(rankElement, nameElement, scoreElement);
    fragment.append(row);
  }
  dom.scoreList.append(fragment);
}

const KILL_GLYPHS = {
  fire: "●",
  frost: "◆",
  spark: "✦",
  beam: "═",
  nova: "◎",
  emp: "⌁",
  chain: "⌁",
  lightning: "↯",
  meteor: "▼",
  siphon: "♥",
  poison: "☁",
  ward: "✶",
};

const KILL_COLORS = {
  fire: "#ff9a4d",
  frost: "#7ce7ff",
  spark: "#ffe17a",
  beam: "#5fd8ff",
  nova: "#b596ff",
  emp: "#b38cff",
  chain: "#c9f6ff",
  lightning: "#9fd4ff",
  meteor: "#ff7b45",
  siphon: "#ff6b9e",
  poison: "#86e08a",
  ward: "#b596ff",
};

function addKillfeed(event) {
  if (!event.name) return;
  const line = document.createElement("div");
  line.className = "feed-line";
  const killerName = event.killer || "Арена";
  const killer = event.killer_id ? client.players.get(event.killer_id) : null;
  const killerColor = event.killer_id ? killer?.color || "#f4d99b" : "rgba(255,255,255,0.5)";

  const killerElement = document.createElement("span");
  killerElement.className = "feed-name";
  killerElement.style.color = killerColor;
  killerElement.textContent = killerName;

  const sigil = document.createElement("span");
  sigil.className = "feed-accent";
  sigil.textContent = KILL_GLYPHS[event.kind] || "✦";
  sigil.style.color = KILL_COLORS[event.kind] || "";

  const victimElement = document.createElement("span");
  victimElement.className = "feed-name";
  victimElement.style.color = event.color || "#e9e3d3";
  victimElement.textContent = event.name;

  line.append(killerElement, sigil, victimElement);
  dom.killfeed.append(line);
  while (dom.killfeed.children.length > 5) {
    dom.killfeed.firstElementChild?.remove();
  }
  window.setTimeout(() => {
    if (!line.isConnected) return;
    line.classList.add("fading");
    window.setTimeout(() => line.remove(), 650);
  }, 5200);
}

function setTopbarOnline(count) {
  if (Number.isFinite(Number(count))) {
    dom.onlineCount.textContent = String(Math.max(0, Number(count)));
  }
}

function setTopbarConnection(connected) {
  dom.topbarDot?.classList.toggle("offline", !connected);
  dom.loginFooterDot?.classList.toggle("offline", !connected);
}

function updateLoginStatus(text, offline) {
  dom.lobbyStatus.textContent = text;
  if (!dom.loginFooterDot) return;
  dom.loginFooterDot.classList.toggle("offline", Boolean(offline));
}

function setLoginError(text) {
  dom.loginError.textContent = text || "";
}

function refreshJoinButton() {
  const waiting = Boolean(pendingJoinName) || joinRequested;
  dom.joinButton.disabled = Boolean(fatalError) || waiting;
  const label = dom.joinButton.querySelector("span");
  if (!label) return;
  if (fatalError) label.textContent = "Портал закрыт";
  else if (waiting) label.textContent = "Открываю портал…";
  else label.textContent = client.mode === "story" ? "Начать сюжет" : "Войти в арену";
}

function showConnectionBanner(text) {
  dom.connectionText.textContent = text;
  dom.connectionBanner.hidden = false;
}

function showToast(text, kind = "") {
  const message = String(text || "").trim().slice(0, 220);
  if (!message) return;
  const repeated = [...dom.toasts.children].find(
    (item) => item.dataset.message === message && !item.classList.contains("fading"),
  );
  if (repeated) {
    repeated.dataset.count = String(Number(repeated.dataset.count) + 1);
    repeated.textContent = `${message} ×${repeated.dataset.count}`;
    scheduleToastFade(repeated);
    return;
  }
  const toast = document.createElement("div");
  toast.className = `toast${kind ? ` ${kind}` : ""}`;
  toast.dataset.message = message;
  toast.dataset.count = "1";
  toast.textContent = message;
  dom.toasts.append(toast);
  while (dom.toasts.children.length > 4) {
    dom.toasts.firstElementChild?.remove();
  }
  scheduleToastFade(toast);
}

function scheduleToastFade(toast) {
  window.clearTimeout(Number(toast.dataset.timer));
  const timer = window.setTimeout(() => {
    if (!toast.isConnected) return;
    toast.classList.add("fading");
    window.setTimeout(() => toast.remove(), 420);
  }, 3800);
  toast.dataset.timer = String(timer);
}

function flashVignette(kind) {
  dom.damageVignette.classList.remove("hit", "heal");
  // Force a style flush so rapid hits restart the flash.
  void dom.damageVignette.offsetWidth;
  dom.damageVignette.classList.add(kind === "heal" ? "heal" : "hit");
  if (vignetteTimer) window.clearTimeout(vignetteTimer);
  vignetteTimer = window.setTimeout(
    () => {
      dom.damageVignette.classList.remove("hit", "heal");
    },
    kind === "heal" ? 760 : 210,
  );
}

function setConsoleStatus(text, mode = "") {
  dom.consoleStatus.textContent = text;
  dom.consoleStatus.classList.remove("error", "busy");
  if (mode) dom.consoleStatus.classList.add(mode);
  if (consoleTimer) {
    window.clearTimeout(consoleTimer);
    consoleTimer = null;
  }
}

function addConsoleEntry(text, kind = "log") {
  const idle = dom.consoleOutput.querySelector(".console-idle");
  idle?.remove();
  const line = document.createElement("p");
  line.className = "console-entry";
  if (kind === "error") line.classList.add("error");
  else if (kind === "system") line.classList.add("system");
  else if (kind === "dim") line.classList.add("dim");
  line.textContent = String(text).replace(/\s+/g, " ").slice(0, 260);
  dom.consoleOutput.append(line);
  while (dom.consoleOutput.children.length > 14) {
    dom.consoleOutput.firstElementChild?.remove();
  }
  dom.consoleOutput.scrollTop = dom.consoleOutput.scrollHeight;
}

/** Dim runes the mage cannot pay for right now; repaints only on a real change. */
function refreshManaBand(me) {
  const mana = Number(me?.mana) || 0;
  const band = client.checks
    .map((check) => (Array.isArray(check.cost) && mana + 0.5 < check.cost[0] ? 1 : 0))
    .join("");
  if (band === lastManaBand) return;
  lastManaBand = band;
  client.hotCards.forEach((card, index) => {
    card.classList.toggle("no-mana", band[index] === "1");
  });
}

function refreshCooldownUi(now, force = false) {
  const lock = castLockMs();
  const remaining = Math.max(0, client.cooldownEnd - now);
  const progress = clamp(1 - remaining / lock, 0, 1);
  const me = localPlayer();
  const stunned = Boolean(me?.stun);
  const available =
    client.connected &&
    socketIsOpen() &&
    client.joined &&
    Boolean(me) &&
    !me.dead &&
    !stunned &&
    !client.castPending &&
    remaining <= 0;
  const status = !client.connected
    ? "Нет связи"
    : !client.joined
      ? "Портал закрыт"
      : me?.dead
        ? "Душа вне тела"
        : stunned
          ? "Оглушение"
          : remaining > 0
            ? `Перезарядка ${(remaining / 1000).toFixed(1)} с`
            : "Гримуар готов";
  const signature = `${status}|${available}|${Math.ceil(progress * 50)}`;
  dom.castButton.disabled = !available;
  dom.cooldownFill.style.transform = `scaleX(${progress})`;
  if (force || signature !== lastCooldownSignature) {
    lastCooldownSignature = signature;
    dom.cooldownLabel.textContent = status;
  }
  const cooling = remaining > 0;
  const cd = clamp(remaining / lock, 0, 1);
  for (const card of client.hotCards) {
    card.classList.toggle("cooling", cooling || stunned);
    card.classList.toggle(
      "disabled",
      !client.connected || !client.joined || Boolean(me?.dead) || stunned,
    );
    card.style.setProperty("--cd", String(cd));
  }
  refreshManaBand(me);
  if (dom.rollHint) {
    const rollRemaining = Math.max(0, client.rollCooldownEnd - now);
    dom.rollHint.textContent = stunned
      ? "оглушение"
      : rollRemaining > 0
        ? `${(rollRemaining / 1000).toFixed(1)} с`
        : "готов";
    dom.rollHint.classList.toggle("cooling", stunned || rollRemaining > 0);
  }
}

// --------------------------------------------------------------- spellbook UI
function displaySpellName(spell) {
  return String(spell?.name || "").trim() || "Без имени";
}

function renderHotbar() {
  dom.hotbar.replaceChildren();
  client.hotCards = [];
  client.spells.forEach((spell, index) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "hot-card";
    card.dataset.slot = String(index);
    card.setAttribute("aria-label", `Сотворить: ${displaySpellName(spell)}`);

    const key = document.createElement("span");
    key.className = "hot-key";
    key.textContent = String(index + 1);
    const rune = document.createElement("span");
    rune.className = "hot-rune";
    rune.textContent = `РУНА ${SLOT_RUNES[index] || index + 1}`;
    const title = document.createElement("span");
    title.className = "hot-title";
    title.textContent = displaySpellName(spell);
    const cooldown = document.createElement("span");
    cooldown.className = "hot-cd";
    cooldown.setAttribute("aria-hidden", "true");
    const cost = document.createElement("span");
    cost.className = "hot-cost";
    cost.title = "Мана за каст";
    card.append(key, rune, title, cost, cooldown);

    card.addEventListener("click", () => {
      sound.unlock();
      sound.play("click");
      selectSlot(index);
      requestCast(index);
    });
    client.hotCards.push(card);
    dom.hotbar.append(card);
  });
  refreshSpellChrome();
  refreshHotbarCosts();
}

function refreshSpellChrome() {
  const active = client.spells[client.activeSlot] || client.spells[0];
  dom.spellTabs.forEach((tab, index) => {
    const spell = client.spells[index];
    tab.classList.toggle("active", index === client.activeSlot);
    const label = tab.querySelector(".tab-label");
    if (label) label.textContent = displaySpellName(spell);
  });
  client.hotCards.forEach((card, index) => {
    const spell = client.spells[index];
    card.classList.toggle("active", index === client.activeSlot);
    const title = card.querySelector(".hot-title");
    if (title) title.textContent = displaySpellName(spell);
    card.setAttribute("aria-label", `Сотворить: ${displaySpellName(spell)}`);
  });
  const filename = `spell_0${client.activeSlot + 1}.py`;
  dom.codeFilename.textContent = filename;
  if (dom.spellsheetFilename) dom.spellsheetFilename.textContent = filename;
  void active;
}

function syncEditorState() {
  const spell = client.spells[client.activeSlot];
  if (!spell) return;
  spell.code = dom.codeInput.value.slice(0, 12000);
  spell.name = dom.spellName.value.slice(0, 28);
}

function selectSlot(index, options = {}) {
  if (!Number.isInteger(index) || index < 0 || index >= client.spells.length) return;
  if (!options.force) syncEditorState();
  client.activeSlot = index;
  const spell = client.spells[index];
  dom.spellName.value = typeof spell.name === "string" ? spell.name : "";
  dom.codeInput.value = spell.code;
  dom.codeInput.scrollTop = 0;
  dom.codeInput.scrollLeft = 0;
  editor.closeCompletion();
  editor.refresh();
  refreshSpellChrome();
  showCheck();
  if (!options.skipSave) scheduleSave();
  if (options.focus) dom.codeInput.focus();
}

function scheduleSave() {
  if (saveTimer) window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(() => {
    saveTimer = null;
    saveSpellbook(client.spells);
  }, 240);
}

function saveSpellbookNow() {
  if (saveTimer) {
    window.clearTimeout(saveTimer);
    saveTimer = null;
  }
  syncEditorState();
  saveSpellbook(client.spells);
}

const RUNE_NAMES = SPELL_API.map((entry) => entry.name);

/** In the campaign a scroll is only offered once its runes have been studied. */
function rebuildExamples() {
  const known = client.config.runes;
  const usesRadar = (example) => example.code.includes("enemies(");
  const usable = EXAMPLES.map((example, index) => ({ example, index })).filter(({ example }) => {
    if (example.role) return example.role === client.role;
    if (!known) return !usesRadar(example);
    return (
      RUNE_NAMES.every(
        (name) => known.includes(name) || !new RegExp(`\\b${name}\\(`).test(example.code),
      ) &&
      (!usesRadar(example) || known.includes("enemies"))
    );
  });
  const options = usable.map(({ example, index }) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = example.name;
    return option;
  });
  dom.exampleSelect.replaceChildren(dom.exampleSelect.options[0], ...options);
}

function setupEditor() {
  rebuildExamples();

  dom.spellTabs.forEach((tab, index) => {
    tab.addEventListener("click", () => {
      sound.unlock();
      sound.play("click");
      selectSlot(index);
    });
  });

  dom.spellName.addEventListener("input", () => {
    const spell = client.spells[client.activeSlot];
    if (!spell) return;
    spell.name = dom.spellName.value.slice(0, 28);
    refreshSpellChrome();
    scheduleSave();
  });
  dom.spellName.addEventListener("blur", () => {
    const spell = client.spells[client.activeSlot];
    if (!spell) return;
    if (!spell.name.trim()) {
      spell.name = "Безымянная руна";
      dom.spellName.value = spell.name;
      refreshSpellChrome();
      scheduleSave();
    }
  });
  dom.spellName.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.ctrlKey && !event.metaKey) {
      event.preventDefault();
      dom.spellName.blur();
    }
  });

  dom.codeInput.addEventListener("input", () => {
    const spell = client.spells[client.activeSlot];
    if (!spell) return;
    spell.code = dom.codeInput.value.slice(0, 12000);
    editor.refresh();
    editor.updateCompletion();
    scheduleSave();
    scheduleCheck();
  });
  dom.codeInput.addEventListener("keydown", handleEditorKeydown);
  dom.codeInput.addEventListener("focus", () => {
    clearMovement();
  });

  dom.exampleSelect.addEventListener("change", () => {
    const value = dom.exampleSelect.value;
    dom.exampleSelect.value = "";
    if (value === "") return;
    const example = EXAMPLES[Number(value)];
    if (!example) return;
    const spell = client.spells[client.activeSlot];
    if (!spell) return;
    spell.name = example.name;
    spell.code = example.code;
    dom.spellName.value = example.name;
    dom.codeInput.value = example.code;
    dom.codeInput.scrollTop = 0;
    dom.codeInput.scrollLeft = 0;
    editor.refresh();
    refreshSpellChrome();
    saveSpellbookNow();
    sendCheck(client.activeSlot);
    sound.play("click");
    addConsoleEntry(`Свиток «${example.name}» перенесён в руну.`, "system");
    showToast(`Свиток «${example.name}» загружен.`);
  });

  dom.castButton.addEventListener("click", () => {
    sound.unlock();
    requestCast(client.activeSlot);
  });

  renderHotbar();
  selectSlot(0, { force: true, skipSave: true });
}

function handleEditorKeydown(event) {
  if (event.isComposing) return;
  if (editor.handleKey(event)) return;
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
    event.preventDefault();
    saveSpellbookNow();
    showToast("Гримуар сохранён в вашей башне.");
    return;
  }
  editor.handleEditingKey(event);
}

// --------------------------------------------------------------------- panels
function isDrawerLayout() {
  return window.matchMedia("(max-width: 1280px)").matches;
}

function panelIsOpen() {
  if (isDrawerLayout()) return dom.body.classList.contains("panel-open");
  return !dom.body.classList.contains("panel-collapsed");
}

function setPanelOpen(open) {
  if (isDrawerLayout()) {
    dom.body.classList.toggle("panel-open", open);
    dom.panelScrim.hidden = !open;
  } else {
    dom.body.classList.toggle("panel-collapsed", !open);
    dom.panelScrim.hidden = true;
  }
  dom.panelToggle.setAttribute("aria-expanded", String(open));
  dom.panelToggle.setAttribute(
    "aria-label",
    open ? "Закрыть гримуар" : "Открыть гримуар",
  );
}

function setupPanels() {
  dom.panelToggle.addEventListener("click", () => {
    sound.unlock();
    sound.play("click");
    setPanelOpen(!panelIsOpen());
  });
  dom.panelClose.addEventListener("click", () => {
    sound.play("click");
    setPanelOpen(false);
  });
  dom.panelScrim.addEventListener("click", () => setPanelOpen(false));
  window.addEventListener("resize", () => {
    if (!isDrawerLayout()) {
      dom.body.classList.remove("panel-open");
      dom.panelScrim.hidden = true;
      if (dom.panelToggle.getAttribute("aria-expanded") === null) {
        dom.panelToggle.setAttribute("aria-expanded", String(panelIsOpen()));
      }
    }
    renderer.resize();
  });
  setPanelOpen(!isDrawerLayout());
}

// ---------------------------------------------------------------------- modal
function openApiModal() {
  if (!dom.apiModal.hidden) return;
  modalReturnFocus =
    document.activeElement instanceof HTMLElement ? document.activeElement : null;
  clearMovement();
  client.pointer.inside = false;
  dom.apiModal.hidden = false;
  sound.play("click");
  window.setTimeout(() => dom.apiClose.focus(), 0);
}

function closeApiModal() {
  if (dom.apiModal.hidden) return;
  dom.apiModal.hidden = true;
  if (modalReturnFocus?.isConnected) {
    modalReturnFocus.focus();
  }
  modalReturnFocus = null;
}

/** The same handbook as in headquarters, carried into the dungeon for a moment. */
function openCodex() {
  if (!dom.codexModal.hidden || !client.story) return;
  clearMovement();
  client.pointer.inside = false;
  dom.codexHost.append(dom.codexRoot);
  dom.codexModal.hidden = false;
  sound.play("click");
  story.codex.render();
  window.setTimeout(() => dom.codexClose.focus(), 0);
}

function closeCodex() {
  if (dom.codexModal.hidden) return;
  dom.codexModal.hidden = true;
  dom.codexPanel.append(dom.codexRoot);
  document.activeElement?.blur?.();
}

function trapModalFocus(event) {
  const focusable = [
    ...dom.apiModal.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ].filter((element) => element instanceof HTMLElement && element.offsetParent !== null);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function setupModal() {
  dom.apiButton.addEventListener("click", openApiModal);
  dom.loginApiButton.addEventListener("click", openApiModal);
  dom.apiClose.addEventListener("click", closeApiModal);
  dom.apiDone.addEventListener("click", closeApiModal);
  dom.codexToggle.addEventListener("click", () => {
    if (dom.codexModal.hidden) openCodex();
    else closeCodex();
  });
  dom.codexClose.addEventListener("click", closeCodex);
  dom.codexModal.addEventListener("click", (event) => {
    if (event.target instanceof Element && event.target.closest("[data-close-codex]")) closeCodex();
  });
  dom.apiModal.addEventListener("click", (event) => {
    if (event.target instanceof Element && event.target.matches("[data-close-modal]")) {
      closeApiModal();
    }
  });
}

// ---------------------------------------------------------------------- sound
function updateSoundToggle() {
  dom.soundToggle.classList.toggle("muted", !sound.enabled);
  dom.soundToggle.setAttribute("aria-pressed", String(sound.enabled));
  dom.soundToggle.title = sound.enabled ? "Выключить звук" : "Включить звук";
}

function setupSound() {
  updateSoundToggle();
  dom.soundToggle.addEventListener("click", () => {
    sound.setEnabled(!sound.enabled);
    saveSoundEnabled(sound.enabled);
    updateSoundToggle();
    if (sound.enabled) sound.play("click");
  });
  document.addEventListener(
    "pointerdown",
    () => {
      sound.unlock();
    },
    { passive: true },
  );
  document.addEventListener("keydown", () => sound.unlock(), { passive: true });
}

// ---------------------------------------------------------------------- login
function handleLoginSubmit(event) {
  event.preventDefault();
  if (joinRequested) return;
  if (fatalError) {
    setLoginError("Портал закрыт. Обновите страницу, чтобы попробовать снова.");
    return;
  }
  const name = dom.nameInput.value.replace(/\s+/g, " ").trim();
  if (name.length < 2) {
    setLoginError("Имя мага должно быть не короче двух символов.");
    dom.nameInput.focus();
    return;
  }
  if (name.length > 16) {
    setLoginError("Имя мага не должно быть длиннее 16 символов.");
    dom.nameInput.focus();
    return;
  }
  setLoginError("");
  saveMageName(name);
  dom.nameInput.value = name;
  sound.unlock();
  if (client.mode === "story") {
    beginStory(name);
    return;
  }
  pendingJoinName = name;
  refreshJoinButton();
  if (socketIsOpen()) {
    sendJoinNow(name);
  } else {
    updateLoginStatus("Портал открывается…", true);
    connect();
  }
}

function setupLogin() {
  dom.nameInput.value = loadMageName();
  dom.loginForm.addEventListener("submit", handleLoginSubmit);
  dom.nameInput.addEventListener("input", () => setLoginError(""));
}

// --------------------------------------------------------------------- moving
function combinedMovement() {
  if (story.terminalTask) return { up: false, down: false, left: false, right: false };
  return {
    up: keyboardMove.up || touchMove.up,
    down: keyboardMove.down || touchMove.down,
    left: keyboardMove.left || touchMove.left,
    right: keyboardMove.right || touchMove.right,
  };
}

function movementActive() {
  const movement = combinedMovement();
  return movement.up || movement.down || movement.left || movement.right;
}

function clearMovement(send = true) {
  keyboardMove.up = false;
  keyboardMove.down = false;
  keyboardMove.left = false;
  keyboardMove.right = false;
  touchMove.up = false;
  touchMove.down = false;
  touchMove.left = false;
  touchMove.right = false;
  activeTouchId = null;
  client.pointer.joy = null;
  client.pointer.touch = false;
  if (send) sendInputNow();
}

// -------------------------------------------------------------------- casting
function castSlot(index) {
  if (!Number.isInteger(index) || index < 0 || index >= client.spells.length) return;
  const spell = client.spells[index];
  if (!spell) return;

  if (!client.joined || !socketIsOpen()) {
    showToast("Портал закрыт. Войдите на арену.", "error");
    return;
  }
  const me = localPlayer();
  if (!me) {
    showToast("Арена ещё не прислала вашего мага. Подождите миг.", "error");
    return;
  }
  if (me.dead) {
    showToast("Душа вне тела. Дождитесь возрождения.", "error");
    return;
  }

  const now = performance.now();
  if (client.castPending || now < client.cooldownEnd) return;
  if (index === client.activeSlot) syncEditorState();

  updateAimFromPointer();
  const cursorTarget = pointerWorldPoint();
  const payload = {
    t: "cast",
    code: String(spell.code || "").slice(0, 12000),
    slot: index,
    aim: round(client.aim, 4),
  };
  if (cursorTarget) {
    payload.target_x = round(cursorTarget.x, 1);
    payload.target_y = round(cursorTarget.y, 1);
  }

  client.castPending = true;
  client.cooldownEnd = now + castLockMs();
  lastCooldownSignature = "";
  refreshCooldownUi(now, true);
  setConsoleStatus("печать…", "busy");
  sound.play("cast");

  try {
    socket.send(JSON.stringify(payload));
  } catch {
    client.castPending = false;
    client.cooldownEnd = 0;
    setConsoleStatus("нет связи", "error");
    refreshCooldownUi(performance.now(), true);
    showToast("Портал не отвечает. Заклинание не отправлено.", "error");
  }
}

/** Ask for a cast: right now if the grimoire is ready, otherwise the moment it is. */
function requestCast(index, held = false) {
  if (story.terminalTask) return;
  const now = performance.now();
  client.castIntent = { slot: index, held, until: now + CAST_BUFFER_MS };
  if (now >= client.cooldownEnd && !client.castPending) castSlot(index);
}

function releaseCast() {
  const intent = client.castIntent;
  if (!intent) return;
  intent.held = false;
  intent.until = performance.now() + CAST_BUFFER_MS;
}

function runCastIntent(now) {
  const intent = client.castIntent;
  if (!intent) return;
  if (!intent.held && now > intent.until) {
    client.castIntent = null;
    return;
  }
  if (now < client.cooldownEnd || client.castPending) return;
  const me = localPlayer();
  if (!client.joined || !socketIsOpen() || !me || me.dead || me.stun) return;
  castSlot(intent.slot);
}

function rollCooldownMs() {
  const cooldown =
    Number(localPlayer()?.roll_cooldown) || Number(client.config.roll?.cooldown) || 1.6;
  return Math.max(0.1, cooldown) * 1000;
}

function requestRoll() {
  if (!client.joined || !socketIsOpen() || story.terminalTask) return;
  const me = localPlayer();
  if (!me || me.dead) return;
  if (me.stun) {
    sound.play("error");
    return;
  }
  const now = performance.now();
  if (client.rollPending) return;
  if (now < client.rollCooldownEnd) {
    sound.play("error");
    return;
  }
  updateAimFromPointer();
  sendInputNow();
  client.rollPending = true;
  client.rollCooldownEnd = now + rollCooldownMs();
  try {
    socket.send(JSON.stringify({ t: "roll", aim: round(client.aim, 4) }));
  } catch {
    client.rollPending = false;
    client.rollCooldownEnd = 0;
  }
}

// -------------------------------------------------------------------- pointer
const JOYSTICK_RADIUS = 54;

function canvasPoint(event) {
  const rect = dom.canvas.getBoundingClientRect();
  return { x: event.clientX - rect.left, y: event.clientY - rect.top };
}

function updatePointerPosition(event) {
  const point = canvasPoint(event);
  client.pointer.x = point.x;
  client.pointer.y = point.y;
  client.pointer.inside = true;
  client.pointer.touch = false;
}

function updateTouchJoystick(x, y) {
  const joy = client.pointer.joy;
  if (!joy) return;
  const rawX = x - joy.originX;
  const rawY = y - joy.originY;
  const length = Math.hypot(rawX, rawY);
  if (length > JOYSTICK_RADIUS) {
    joy.dx = rawX / length;
    joy.dy = rawY / length;
  } else {
    joy.dx = rawX / JOYSTICK_RADIUS;
    joy.dy = rawY / JOYSTICK_RADIUS;
  }
  joy.magnitude = clamp(length / JOYSTICK_RADIUS, 0, 1);
  touchMove.left = joy.dx < -0.3;
  touchMove.right = joy.dx > 0.3;
  touchMove.up = joy.dy < -0.3;
  touchMove.down = joy.dy > 0.3;
  if (joy.magnitude > 0.18) {
    client.aim = Math.atan2(joy.dy, joy.dx);
  }
}

function startTouchJoystick(event) {
  if (activeTouchId !== null) return;
  if (!client.joined) return;
  const point = canvasPoint(event);
  activeTouchId = event.pointerId;
  client.pointer.touch = true;
  client.pointer.inside = false;
  client.pointer.x = point.x;
  client.pointer.y = point.y;
  client.pointer.joy = {
    originX: point.x,
    originY: point.y,
    dx: 0,
    dy: 0,
    magnitude: 0,
  };
  try {
    dom.canvas.setPointerCapture(event.pointerId);
  } catch {
    /* Some browsers refuse capture for synthetic pointers. */
  }
  updateTouchJoystick(point.x, point.y);
  sendInputNow();
  event.preventDefault();
}

function endTouchJoystick(event) {
  if (event.pointerId !== activeTouchId) return;
  activeTouchId = null;
  touchMove.up = false;
  touchMove.down = false;
  touchMove.left = false;
  touchMove.right = false;
  client.pointer.joy = null;
  client.pointer.inside = false;
  try {
    if (dom.canvas.hasPointerCapture(event.pointerId)) {
      dom.canvas.releasePointerCapture(event.pointerId);
    }
  } catch {
    /* noop */
  }
  sendInputNow();
  event.preventDefault();
}

function setupPointer() {
  dom.canvas.addEventListener("pointerdown", (event) => {
    sound.unlock();
    if (event.pointerType === "touch") {
      startTouchJoystick(event);
      return;
    }
    if (event.button !== 0 && event.button !== 2) return;
    updatePointerPosition(event);
    updateAimFromPointer();
    requestCast(client.activeSlot, true);
    event.preventDefault();
  });
  window.addEventListener("pointerup", (event) => {
    if (event.pointerType !== "touch") releaseCast();
  });

  dom.canvas.addEventListener("pointermove", (event) => {
    if (event.pointerType === "touch") {
      if (event.pointerId !== activeTouchId) return;
      const point = canvasPoint(event);
      updateTouchJoystick(point.x, point.y);
      sendInputNow();
      event.preventDefault();
      return;
    }
    updatePointerPosition(event);
    updateAimFromPointer();
  });

  dom.canvas.addEventListener("pointerup", endTouchJoystick);
  dom.canvas.addEventListener("pointercancel", endTouchJoystick);
  dom.canvas.addEventListener("lostpointercapture", (event) => {
    if (event.pointerId !== activeTouchId) return;
    activeTouchId = null;
    touchMove.up = false;
    touchMove.down = false;
    touchMove.left = false;
    touchMove.right = false;
    client.pointer.joy = null;
    client.pointer.inside = false;
    sendInputNow();
  });

  dom.canvas.addEventListener("pointerleave", (event) => {
    if (event.pointerType === "mouse" && activeTouchId === null) {
      client.pointer.inside = false;
    }
  });

  dom.canvas.addEventListener("contextmenu", (event) => {
    event.preventDefault();
  });
}

// ------------------------------------------------------------------- keyboard
function setupKeyboard() {
  window.addEventListener("keydown", (event) => {
    if (event.isComposing) return;
    const withModifier = event.ctrlKey || event.metaKey;

    if (event.key === "Enter" && withModifier) {
      if (!client.joined) return;
      event.preventDefault();
      sound.unlock();
      requestCast(client.activeSlot);
      return;
    }
    if (event.key === "Escape") {
      if (story.closeLog()) return;
      if (story.terminalTask) {
        story.closeTerminal();
        return;
      }
      if (!dom.apiModal.hidden) {
        closeApiModal();
        return;
      }
      if (!dom.codexModal.hidden) {
        closeCodex();
        return;
      }
      if (isDrawerLayout() && panelIsOpen()) {
        setPanelOpen(false);
        return;
      }
    }
    if (event.defaultPrevented) return;
    if (!dom.apiModal.hidden) return;
    if (!dom.codexModal.hidden) {
      if (event.code === "KeyK" && !event.repeat) closeCodex();
      return;
    }
    if (isTypingTarget(event.target) || story.terminalTask) return;
    if (!client.joined) return;
    if (event.code === "KeyK" && !event.repeat && client.story) {
      openCodex();
      return;
    }

    if (story.talkOpen()) {
      const reply = ["1", "2", "3", "4", "5"].indexOf(event.key);
      if (reply >= 0 && !event.repeat) {
        story.chooseReply(reply);
        event.preventDefault();
        return;
      }
      if (event.key === "Escape") {
        story.closeTalk();
        event.preventDefault();
        return;
      }
      // Mid-conversation E never starts the same conversation over.
      if (event.code === "KeyE") {
        if (!event.repeat) story.talkKey();
        event.preventDefault();
        return;
      }
    }
    if (event.code === "KeyE" && !event.repeat && client.story) {
      if (story.openTerminal() || story.interact()) event.preventDefault();
      return;
    }
    if (event.code === "KeyL" && !event.repeat && client.story) {
      story.toggleLog();
      return;
    }
    if (event.key === "1" || event.key === "2" || event.key === "3") {
      event.preventDefault();
      if (event.repeat) return;
      const index = Number(event.key) - 1;
      sound.unlock();
      selectSlot(index);
      requestCast(index, true);
      return;
    }
    if (event.key === " " || event.code === "Space") {
      event.preventDefault();
      if (event.repeat) return;
      sound.unlock();
      requestCast(client.activeSlot, true);
      return;
    }
    if (
      event.key === "Shift" ||
      event.code === "ShiftLeft" ||
      event.code === "ShiftRight"
    ) {
      if (event.repeat) return;
      event.preventDefault();
      sound.unlock();
      requestRoll();
      return;
    }
    const direction = MOVE_KEYS[event.code];
    if (!direction) return;
    event.preventDefault();
    if (!client.joined) return;
    keyboardMove[direction] = true;
    sendInputNow();
  });

  window.addEventListener("keyup", (event) => {
    if (event.key === " " || ["1", "2", "3"].includes(event.key)) releaseCast();
    const direction = MOVE_KEYS[event.code];
    if (!direction) return;
    if (keyboardMove[direction]) {
      keyboardMove[direction] = false;
      sendInputNow();
    }
  });

  window.addEventListener("blur", () => {
    clearMovement();
    client.castIntent = null;
    client.pointer.inside = false;
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      clearMovement();
      saveSpellbookNow();
    } else if (client.connected) {
      // A frozen background tab can leave lastStateAt far behind. Give the
      // resumed page a fresh window before the silence watchdog considers it.
      client.lastStateAt = performance.now();
    }
  });
}

// --------------------------------------------------------------------- timers
function startNetworkTimers() {
  if (!inputTimer) {
    inputTimer = window.setInterval(() => {
      if (!client.joined || !socketIsOpen()) return;
      updateAimFromPointer();
      sendInputNow();
    }, 120);
  }
  if (!pingTimer) {
    pingTimer = window.setInterval(sendPing, 2000);
  }
}

function stopNetworkTimers() {
  if (inputTimer) {
    window.clearInterval(inputTimer);
    inputTimer = null;
  }
  if (pingTimer) {
    window.clearInterval(pingTimer);
    pingTimer = null;
  }
}

// ----------------------------------------------------------------- world fetch
async function fetchWorldConfig() {
  try {
    const response = await fetch("/api/world", {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return;
    const config = await response.json();
    mergeWorldConfig(config);
  } catch {
    /* The welcome message carries the same configuration. */
  }
}

// ------------------------------------------------------------------ animation
let lastAnimationAt = 0;

const DRAW_ERROR_EVERY = 5000;
let lastDrawErrorAt = -DRAW_ERROR_EVERY;

function animate(now) {
  // First of all: whatever throws below, the next frame is already on its way.
  window.requestAnimationFrame(animate);

  const rawDt = lastAnimationAt ? (now - lastAnimationAt) / 1000 : 0.016;
  const dt = clamp(rawDt, 0.001, 0.05);
  lastAnimationAt = now;

  updateAimFromPointer();
  updatePrediction(dt);
  runCastIntent(now);
  try {
    renderer.draw(client, now);
  } catch (error) {
    if (now - lastDrawErrorAt > DRAW_ERROR_EVERY) {
      lastDrawErrorAt = now;
      console.error("Кадр не отрисован:", error);
    }
    renderer.recoverFrame();
  }
  refreshCooldownUi(now);

  if (
    client.joined &&
    client.lastStateAt &&
    socketIsOpen() &&
    now - client.lastStateAt > 15000
  ) {
    showConnectionBanner("Арена молчит. Восстанавливаю портал…");
    try {
      socket.close(4001, "arena silent");
    } catch {
      /* noop */
    }
    client.lastStateAt = now;
  }
}

// ----------------------------------------------------------------------- boot
let booted = false;

function boot() {
  if (booted) return;
  booted = true;

  setupLogin();
  setupModes();
  setupEditor();
  setupPanels();
  setupModal();
  setupSound();
  setupPointer();
  setupKeyboard();
  startNetworkTimers();

  window.addEventListener("beforeunload", saveSpellbookNow);
  window.addEventListener("pagehide", saveSpellbookNow);

  fetchWorldConfig();
  connect();
  window.requestAnimationFrame(animate);
}

boot();
