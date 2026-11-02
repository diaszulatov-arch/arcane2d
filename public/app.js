/* Arcane 2D — browser client: local spellbook, networking, controls and UI. */

import { SoundEngine } from "./js/audio.js";
import { ArenaRenderer } from "./js/renderer.js";
import {
  EXAMPLES,
  SLOT_RUNES,
  loadMageName,
  loadSoundEnabled,
  loadSpellbook,
  saveMageName,
  saveSoundEnabled,
  saveSpellbook,
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
  pointer: {
    x: window.innerWidth / 2,
    y: window.innerHeight / 2,
    inside: false,
    touch: false,
    joy: null,
  },
  aim: 0,
  prediction: { x: 950, y: 550, active: false, selfId: null },
  spells: loadSpellbook(),
  activeSlot: 0,
  cooldownEnd: 0,
  castPending: false,
  rollCooldownEnd: 0,
  rollPending: false,
  lastStateAt: 0,
  hotCards: [],
};

const renderer = new ArenaRenderer(dom.canvas);
const sound = new SoundEngine(loadSoundEnabled());

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
let consoleTimer = null;
let vignetteTimer = null;
let activeTouchId = null;
let modalReturnFocus = null;
let lastScoreSignature = "";
let lastCooldownSignature = "";
let lastHealthSignature = "";
let serverHello = null;
let hasShownWelcome = false;

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

function canStand(x, y) {
  const arena = client.config.arena;
  const border = arena.border;
  const radius = client.config.player_radius || 18;
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
    if (hasEnteredArena) {
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
    clearMovement(false);
    updateSelfHud(localPlayer());
    setTopbarConnection(false);
    refreshJoinButton();
    refreshCooldownUi(performance.now(), true);
    if (hasEnteredArena) {
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
    case "pong":
      break;
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
    socket.send(JSON.stringify({ t: "ping" }));
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
      if (event.id === selfId) {
        client.prediction.active = false;
        clearMovement();
        flashVignette("hit");
        updateRespawnOverlay(event.respawn_in ?? 3);
        showToast(`Вас поверг ${event.killer || "Арена"}.`, "error");
        sound.play("death");
      } else if (near) {
        sound.play("death-near");
      }
      break;
    }
    case "respawn": {
      if (event.id === selfId && typeof event.x === "number") {
        client.prediction.x = event.x;
        client.prediction.y = event.y;
        client.prediction.active = true;
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
        client.prediction.x = event.to_x;
        client.prediction.y = event.to_y;
        client.prediction.active = true;
      }
      if (near) sound.play("dash");
      break;
    case "roll":
      if (event.id === selfId && typeof event.x2 === "number") {
        client.prediction.x = event.x2;
        client.prediction.y = event.y2;
        client.prediction.active = true;
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

function handleCastResult(message) {
  client.castPending = false;
  const cooldown = Math.max(0, Number(message.cooldown) || 0);
  if (message.ok) {
    client.cooldownEnd = performance.now() + (cooldown || castLockMs());
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
    addConsoleEntry(error, "error");
    setConsoleStatus("ошибка", "error");
    showToast(error, "error");
    sound.play("error");
  }
  refreshCooldownUi(performance.now(), true);
}

function castLockMs() {
  return Math.max(0.1, Number(client.config.cast_lock) || 0.72) * 1000;
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

function reconcilePrediction() {
  const me = localPlayer();
  if (!me || me.dead) {
    client.prediction.active = false;
    return;
  }
  if (client.prediction.selfId !== client.selfId || !client.prediction.active) {
    client.prediction.x = me.x;
    client.prediction.y = me.y;
    client.prediction.active = true;
    client.prediction.selfId = client.selfId;
    return;
  }
  if (me.stun) {
    client.prediction.x = me.x;
    client.prediction.y = me.y;
    return;
  }
  const error = Math.hypot(me.x - client.prediction.x, me.y - client.prediction.y);
  if (error > 170) {
    client.prediction.x = me.x;
    client.prediction.y = me.y;
  } else if (!movementActive() && error < 46) {
    client.prediction.x += (me.x - client.prediction.x) * 0.32;
    client.prediction.y += (me.y - client.prediction.y) * 0.32;
  }
}

function updatePrediction(dt) {
  if (!client.prediction.active || !client.connected || !client.joined) return;
  const me = localPlayer();
  if (!me || me.dead) {
    client.prediction.active = false;
    return;
  }
  if (me.stun) return;
  const movement = combinedMovement();
  const dx = Number(movement.right) - Number(movement.left);
  const dy = Number(movement.down) - Number(movement.up);
  if (!dx && !dy) return;
  const length = Math.hypot(dx, dy) || 1;
  const speed = (Number(client.config.speed) || 238) * (me.slow ? 0.58 : 1);
  const stepX = (dx / length) * speed * dt;
  const stepY = (dy / length) * speed * dt;
  const prediction = client.prediction;

  if (stepX) {
    const nextX = clamp(
      prediction.x + stepX,
      client.config.arena.border + (client.config.player_radius || 18),
      client.config.arena.w -
        client.config.arena.border -
        (client.config.player_radius || 18),
    );
    if (canStand(nextX, prediction.y)) prediction.x = nextX;
  }
  if (stepY) {
    const nextY = clamp(
      prediction.y + stepY,
      client.config.arena.border + (client.config.player_radius || 18),
      client.config.arena.h -
        client.config.arena.border -
        (client.config.player_radius || 18),
    );
    if (canStand(prediction.x, nextY)) prediction.y = nextY;
  }
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
  const hp = clamp(Number(me.hp) || 0, 0, 100);
  const mana = clamp(Number(me.mana) || 0, 0, 100);
  const dead = Boolean(me.dead);
  const stunned = Boolean(me.stun) && !dead;
  dom.hpFill.style.width = `${hp}%`;
  dom.manaFill.style.width = `${mana}%`;
  const healthSignature =
    `${Math.round(hp)}:${Math.round(mana)}:${dead}:${stunned}:${client.connected}`;
  if (healthSignature !== lastHealthSignature) {
    lastHealthSignature = healthSignature;
    dom.hpText.textContent = String(Math.round(hp));
    dom.manaText.textContent = String(Math.round(mana));
    dom.localHud.classList.toggle("low-health", !dead && hp < 36);
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
  if (dead) {
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
  sigil.textContent = "✦";

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
  else label.textContent = "Войти в арену";
}

function showConnectionBanner(text) {
  dom.connectionText.textContent = text;
  dom.connectionBanner.hidden = false;
}

function showToast(text, kind = "") {
  const message = String(text || "").trim();
  if (!message) return;
  const toast = document.createElement("div");
  toast.className = `toast${kind ? ` ${kind}` : ""}`;
  toast.textContent = message.slice(0, 220);
  dom.toasts.append(toast);
  while (dom.toasts.children.length > 4) {
    dom.toasts.firstElementChild?.remove();
  }
  window.setTimeout(() => {
    if (!toast.isConnected) return;
    toast.classList.add("fading");
    window.setTimeout(() => toast.remove(), 420);
  }, 3800);
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
    card.append(key, rune, title, cooldown);

    card.addEventListener("click", () => {
      sound.unlock();
      sound.play("click");
      selectSlot(index);
      castSlot(index);
    });
    client.hotCards.push(card);
    dom.hotbar.append(card);
  });
  refreshSpellChrome();
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
  updateLineNumbers();
  refreshSpellChrome();
  if (!options.skipSave) scheduleSave();
  if (options.focus) dom.codeInput.focus();
}

function updateLineNumbers() {
  const lines = dom.codeInput.value.split("\n").length;
  const parts = new Array(lines);
  for (let index = 0; index < lines; index += 1) parts[index] = index + 1;
  dom.lineNumbers.textContent = parts.join("\n");
  dom.lineNumbers.scrollTop = dom.codeInput.scrollTop;
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

function dispatchEditorInput() {
  dom.codeInput.dispatchEvent(new Event("input", { bubbles: true }));
}

function setupEditor() {
  for (const [index, example] of EXAMPLES.entries()) {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = example.name;
    dom.exampleSelect.append(option);
  }

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
    updateLineNumbers();
    scheduleSave();
  });
  dom.codeInput.addEventListener("scroll", () => {
    dom.lineNumbers.scrollTop = dom.codeInput.scrollTop;
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
    updateLineNumbers();
    refreshSpellChrome();
    saveSpellbookNow();
    sound.play("click");
    addConsoleEntry(`Свиток «${example.name}» перенесён в руну.`, "system");
    showToast(`Свиток «${example.name}» загружен.`);
  });

  dom.castButton.addEventListener("click", () => {
    sound.unlock();
    castActive();
  });

  renderHotbar();
  selectSlot(0, { force: true, skipSave: true });
}

function handleEditorKeydown(event) {
  if (event.isComposing) return;
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
    event.preventDefault();
    saveSpellbookNow();
    showToast("Гримуар сохранён в вашей башне.");
    return;
  }
  if (event.key === "Tab") {
    event.preventDefault();
    applyTabKey(event.shiftKey);
    return;
  }
  if (
    event.key === "Enter" &&
    !event.shiftKey &&
    !event.ctrlKey &&
    !event.metaKey &&
    !event.altKey &&
    dom.codeInput.selectionStart === dom.codeInput.selectionEnd
  ) {
    event.preventDefault();
    applyAutoIndent();
  }
}

function applyEditorEdit(start, end, text, selectionStart, selectionEnd) {
  dom.codeInput.setRangeText(text, start, end, "end");
  dispatchEditorInput();
  dom.codeInput.setSelectionRange(
    clamp(selectionStart, 0, dom.codeInput.value.length),
    clamp(selectionEnd, 0, dom.codeInput.value.length),
  );
}

function applyTabKey(outdent) {
  const input = dom.codeInput;
  const value = input.value;
  const selectionStart = input.selectionStart;
  const selectionEnd = input.selectionEnd;

  if (selectionStart === selectionEnd) {
    if (!outdent) {
      applyEditorEdit(selectionStart, selectionEnd, "    ", selectionStart + 4, selectionStart + 4);
      return;
    }
    const lineStart = value.lastIndexOf("\n", selectionStart - 1) + 1;
    const linePrefix = value.slice(lineStart, selectionStart);
    const match = linePrefix.match(/^( {1,4}|\t)/);
    if (!match) return;
    const remove = match[0].length;
    applyEditorEdit(
      lineStart,
      lineStart + remove,
      "",
      Math.max(lineStart, selectionStart - remove),
      Math.max(lineStart, selectionEnd - remove),
    );
    return;
  }

  const lineStart = value.lastIndexOf("\n", selectionStart - 1) + 1;
  let lineEnd = value.indexOf("\n", selectionEnd);
  if (lineEnd === -1) lineEnd = value.length;
  const block = value.slice(lineStart, lineEnd);
  const lines = block.split("\n");
  let deltaFirst = 0;
  let deltaTotal = 0;
  let changed;
  if (outdent) {
    changed = lines
      .map((line, index) => {
        const match = line.match(/^( {1,4}|\t)/);
        const remove = match ? match[0].length : 0;
        if (index === 0) deltaFirst -= remove;
        deltaTotal -= remove;
        return line.slice(remove);
      })
      .join("\n");
  } else {
    changed = lines
      .map((line, index) => {
        if (index === 0) deltaFirst += 4;
        deltaTotal += 4;
        return `    ${line}`;
      })
      .join("\n");
  }
  applyEditorEdit(
    lineStart,
    lineEnd,
    changed,
    Math.max(lineStart, selectionStart + deltaFirst),
    Math.max(lineStart, selectionEnd + deltaTotal),
  );
}

function applyAutoIndent() {
  const input = dom.codeInput;
  const value = input.value;
  const position = input.selectionStart;
  const lineStart = value.lastIndexOf("\n", position - 1) + 1;
  const before = value.slice(lineStart, position);
  const indentMatch = before.match(/^[ \t]*/);
  const indent = indentMatch ? indentMatch[0] : "";
  const extra = before.trimEnd().endsWith(":") ? "    " : "";
  const insert = `\n${indent}${extra}`;
  applyEditorEdit(
    position,
    position,
    insert,
    position + insert.length,
    position + insert.length,
  );
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
  pendingJoinName = name;
  saveMageName(name);
  dom.nameInput.value = name;
  sound.unlock();
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
  if (client.castPending) return;
  if (now < client.cooldownEnd) {
    sound.play("error");
    return;
  }
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

function castActive() {
  castSlot(client.activeSlot);
}

function rollCooldownMs() {
  return Math.max(0.1, Number(client.config.roll?.cooldown) || 1.6) * 1000;
}

function requestRoll() {
  if (!client.joined || !socketIsOpen()) return;
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
    castActive();
    event.preventDefault();
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
      castActive();
      return;
    }
    if (event.key === "Escape") {
      if (!dom.apiModal.hidden) {
        closeApiModal();
        return;
      }
      if (isDrawerLayout() && panelIsOpen()) {
        setPanelOpen(false);
        return;
      }
    }
    if (event.defaultPrevented) return;
    if (!dom.apiModal.hidden) return;
    if (isTypingTarget(event.target)) return;
    if (!client.joined) return;

    if (event.key === "1" || event.key === "2" || event.key === "3") {
      event.preventDefault();
      const index = Number(event.key) - 1;
      sound.unlock();
      selectSlot(index);
      castSlot(index);
      return;
    }
    if (event.key === " " || event.code === "Space") {
      event.preventDefault();
      sound.unlock();
      castActive();
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
    const direction = MOVE_KEYS[event.code];
    if (!direction) return;
    if (keyboardMove[direction]) {
      keyboardMove[direction] = false;
      sendInputNow();
    }
  });

  window.addEventListener("blur", () => {
    clearMovement();
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
    pingTimer = window.setInterval(sendPing, 20000);
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

function animate(now) {
  const rawDt = lastAnimationAt ? (now - lastAnimationAt) / 1000 : 0.016;
  const dt = clamp(rawDt, 0.001, 0.05);
  lastAnimationAt = now;

  updateAimFromPointer();
  updatePrediction(dt);
  renderer.draw(client, now);
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

  window.requestAnimationFrame(animate);
}

// ----------------------------------------------------------------------- boot
let booted = false;

function boot() {
  if (booted) return;
  booted = true;

  setupLogin();
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





