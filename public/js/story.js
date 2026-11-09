/* The campaign's screens: headquarters, the radio, terminals and the dungeon HUD. */

import { Codex } from "./codex.js";
import { SpellEditor } from "./editor.js";
import { PORTRAIT_GRID, hasPortrait, hasSoftVoice, paintPortrait, voiceOf } from "./portraits.js";
import { TypeWriter } from "./typewriter.js";

const $ = (id) => document.getElementById(id);
const ROMAN = ["I", "II", "III", "IV", "V"];
const INTRO_TIME = 6500;
const COMMS_BASE = 2000;
const COMMS_PER_CHAR = 56;
const COMMS_GAP = 260;
const LOG_LIMIT = 300;
const LOG_STICK = 40;
const TALK_REACH = 205;
const TALK_LINGER = 9000;
const TALK_SPEED = 62;
const SHORT_REPLY = 12;
const RADIO_SPEED = 80;
const RADIO_VOLUME = 0.55;
const SPOKEN = /[\p{L}\p{N}]/u;
const RADIO_HOLD = 350;
const SPEAKER_FACES = {
  "Ада": "ada",
  "Записка Ады": "note",
  PGT: "pgt",
  "Валера": "valera",
  "Запросик": "request",
  "Королева None": "queen",
  "Поющий банкомат": "atm",
  "Холодильник-спорщик": "fridge",
  "Скрепка-помощник": "clip",
  "Легаси-торговец": "vendor",
};
const MACHINE_TAGS = {
  MySQL: "SQL",
  nginx: "ngx",
  HAProxy: "LB",
  Docker: "DKR",
  Git: "git",
  "git log": "git",
  CI: "CI",
  Edge: "CDN",
  "OOM killer": "OOM",
  journald: "LOG",
  "Бакет": "S3",
  "Мониторинг": "°C",
  "Модератор": "MOD",
  "Фильтр": "SPAM",
};
const TEST_OPENS = 12;
const PYTEST_WORD = { passed: "PASSED", skipped: "SKIPPED", none: "NOT RUN" };
const SHOUT_TIME = 3000;
const TERMINAL_REACH = 112;
const LEAK_NOTICE = 460;
const HELP_LINES = 4;
const ADA = "Ада";
const BOT = "PGT";
const SPEAKERS = { [ADA]: "ada", [BOT]: "pgt", "git log": "gitlog" };
const CLIP_FROM = 2;
// What the old paperclip says when a spell falls over. First match wins.
const CLIP_TIPS = [
  [/Не хватает маны/, "Похоже, кончилась мана! Проверьте me().mana перед дорогой руной или ready(\"имя\")."],
  [/Неизвестное имя/, "Похоже, опечатка в имени! Или эта руна вам ещё не знакома. Список есть в подсказке редактора."],
  [/не определена/, "Похоже, вы читаете переменную раньше, чем что-то в неё положили."],
  [/invalid syntax|expected ':'|expected an indented block|unexpected indent|unindent/i, "Похоже, что-то с синтаксисом! Двоеточие после if и for на месте? Отступы ровные?"],
  [/was never closed|unmatched/, "Похоже, скобка осталась незакрытой. Вы таких уже видели."],
  [/будет готов/, "Похоже, руна на перезарядке. ready(\"имя\") скажет об этом заранее и без ошибки."],
  [/Неверное количество или тип/, "Похоже, не те аргументы. Подсказка редактора покажет, что руна ждёт."],
  [/ждёт функцию/, "Функцию передают по имени без скобок: daemon(turret), а не daemon(turret())."],
  [/None/, "Похоже, тут None. Перед .x проверьте, что значение вообще есть: if p:."],
];
const STAGE_KIND = {
  door: "ЗАМОК ДВЕРИ",
  portal: "СЛОМАННЫЙ УЗЕЛ",
  gate: "ЩИТ БОССА",
  quest: "КОНСОЛЬ ЗАДАЧИ",
};
const USE_REACH = 96;
const EVENT_TEXT = {
  storm: "СПАМ-ШТОРМ",
  blackout: "ПЛАНОВЫЕ РАБОТЫ",
  dns: "СБОЙ DNS: карта врёт",
  leak: "УТЕЧКА ДАННЫХ",
};
const CURSE_TEXT = {
  syntax: "SyntaxError: заклинания не компилируются",
  null: "None: enemies(), allies() и cursor() пусты",
  mirror: "Автокоррекция: прицел перевёрнут",
  drop: "DROP TABLE: эта руна стёрта, бейте другой",
  inject: "Промпт-инъекция: следующий каст улетит куда угодно",
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function pick(items) {
  return items[Math.floor(Math.random() * items.length)];
}

function dialogueLine([speaker, text]) {
  const line = element("p", `dialogue ${SPEAKERS[speaker] || ""}`);
  line.append(element("b", "", speaker), element("span", "", text));
  return line;
}

/** A conversation: someone's name is only worth saying when the speaker changes. */
function dialogue(lines, before = null) {
  let speaker = before;
  return lines.map((entry) => {
    const line = dialogueLine(entry);
    line.classList.toggle("continued", entry[0] === speaker);
    [speaker] = entry;
    return line;
  });
}

export class StoryUi {
  constructor({ send, sound, toast, costOf, onTerminal }) {
    this.send = send;
    this.sound = sound;
    this.toast = toast;
    this.onTerminal = onTerminal;
    this.campaign = null;
    this.lessons = [];
    this.tasks = new Map();
    this.roles = null;
    this.upgrades = null;
    this.profile = null;
    this.party = null;
    this.result = null;
    this.tab = "story";
    this.drafts = new Map();
    this.lessonIndex = -1;
    this.bestiary = {};
    this.lastGoal = "";
    this.lastFrames = "";
    this.comms = [];
    this.commsTimer = null;
    this.terminalTask = null;
    this.nearTerminal = null;
    this.hintsShown = 0;
    this.help = { hints: 0, solution: false, theory: false };
    this.commsHistory = [];
    this.lastCurses = "";
    this.leakNoticed = false;
    this.toldAlone = false;
    this.partySize = 1;
    this.stageConfig = null;
    this.nearUse = false;
    this.lastQuest = "";
    this.lastCode = "";
    this.relics = [];
    this.folk = [];
    this.codex = new Codex($("codexRoot"));
    this.talk = null;
    this.talkTimer = null;
    this.talkWriter = null;
    this.radioWriter = null;
    this.radioFace = null;
    this.radioLine = null;
    this.faceFrame = null;
    this.lastFolk = "";
    this.book = [];
    this.tickets = [];
    this.crew = [];
    this.isRange = false;
    this.dom = {
      root: $("camp"),
      entry: $("campEntry"),
      main: $("campMain"),
      prologue: $("campPrologue"),
      create: $("partyCreate"),
      joinForm: $("partyJoinForm"),
      joinCode: $("partyJoinCode"),
      entryError: $("campEntryError"),
      back: $("campBack"),
      chapter: $("campChapter"),
      stage: $("campStage"),
      code: $("partyCode"),
      essence: $("campEssence"),
      banner: $("campBanner"),
      seats: $("campSeats"),
      map: $("campMap"),
      difficulty: $("campDifficulty"),
      difficultyAbout: $("campDifficultyAbout"),
      ready: $("campReady"),
      leave: $("campLeave"),
      tabs: [...document.querySelectorAll(".camp-tab")],
      panels: [...document.querySelectorAll(".camp-panel")],
      story: $("tabStory"),
      lessonTitle: $("lessonTitle"),
      lessonRune: $("lessonRune"),
      lessonTheory: $("lessonTheory"),
      lessonExample: $("lessonExample"),
      lessonTask: $("lessonTask"),
      tree: $("upgradeTree"),
      roleTab: $("roleTab"),
      roleIntro: $("roleIntro"),
      roleCards: $("roleCards"),
      roleBar: $("roleBar"),
      hud: $("storyHud"),
      hudStage: $("storyStage"),
      hudGoal: $("storyGoal"),
      bossBar: $("bossBar"),
      bossName: $("bossName"),
      bossFill: $("bossFill"),
      deployBar: $("deployBar"),
      deployTime: $("deployTime"),
      deployBreak: $("deployBreak"),
      bossShout: $("bossShout"),
      curseBar: $("curseBar"),
      frames: $("partyFrames"),
      commsBox: $("storyComms"),
      commsLog: $("commsLog"),
      commsLogBody: $("commsLogBody"),
      prompt: $("terminalPrompt"),
      intro: $("introCard"),
      introName: $("introName"),
      introHint: $("introHint"),
      terminal: $("terminal"),
      terminalKind: $("terminalKind"),
      terminalTitle: $("terminalTitle"),
      terminalClose: $("terminalClose"),
      terminalBrief: $("terminalBrief"),
      terminalTheoryBox: $("terminalTheoryBox"),
      terminalTheory: $("terminalTheory"),
      terminalExample: $("terminalExample"),
      terminalHelp: $("terminalHelp"),
      terminalHint: $("terminalHint"),
      terminalAsk: $("terminalAsk"),
      terminalInput: $("terminalInput"),
      terminalResult: $("terminalResult"),
      terminalApply: $("terminalApply"),
      terminalPgt: $("terminalPgt"),
      quest: $("questCard"),
      questTech: $("questTech"),
      questTitle: $("questTitle"),
      questText: $("questText"),
      questBar: $("questBar"),
      questFill: $("questFill"),
      questBarLabel: $("questBarLabel"),
      codeCard: $("codeCard"),
      eventChip: $("eventChip"),
      finds: $("questFinds"),
      range: $("campRange"),
      duty: $("campDuty"),
      dutyEnd: $("campDutyEnd"),
      dutyAbout: $("campDutyAbout"),
      book: $("bookList"),
      ticketBoard: $("ticketBoard"),
      ticketCount: $("ticketCount"),
      crew: $("crewList"),
      people: $("peopleList"),
      peopleIntro: $("peopleIntro"),
      folkList: $("folkList"),
      npcTalk: $("npcTalk"),
      npcDim: $("npcDim"),
      npcPortrait: $("npcPortrait"),
      npcName: $("npcName"),
      npcText: $("npcText"),
      npcCode: $("npcCode"),
      npcReplies: $("npcReplies"),
      rangeCard: $("rangeCard"),
      rangeDps: $("rangeDps"),
      rangeTotal: $("rangeTotal"),
      relics: $("relicList"),
      relicCount: $("relicCount"),
      codeCardTitle: $("codeCardTitle"),
      codeCardBody: $("codeCardBody"),
    };
    this.terminalEditor = new SpellEditor({
      input: this.dom.terminalInput,
      layer: $("terminalLayer"),
      gutter: $("terminalGutter"),
      popup: $("terminalComplete"),
      costOf,
      isKnown: (name) => this.knownRunes().has(name),
    });
    this.bind();
  }

  bind() {
    const { dom } = this;
    dom.create.addEventListener("click", () => this.send({ t: "party_create" }));
    dom.npcTalk.addEventListener("click", () => this.skipTalk());
    dom.joinForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const code = dom.joinCode.value.trim();
      if (code) this.send({ t: "party_join", code });
    });
    dom.back.addEventListener("click", () => window.location.reload());
    dom.leave.addEventListener("click", () => this.send({ t: "party_leave" }));
    ["commsToggle", "campLog", "terminalLog", "commsLogClose"].forEach((id) => {
      $(id).addEventListener("click", (event) => {
        // Focus left here would turn the next Space, a cast, into another click.
        event.currentTarget.blur();
        this.toggleLog();
      });
    });
    dom.range.addEventListener("click", () => this.send({ t: "party_range" }));
    dom.duty.addEventListener("click", () => this.send({ t: "party_duty" }));
    dom.dutyEnd.addEventListener("click", () => this.send({ t: "party_duty_end" }));
    dom.ready.addEventListener("click", () => {
      const seat = this.party?.seats.find((entry) => entry.you);
      this.send({ t: "party_ready", ready: !seat?.ready });
    });
    dom.tabs.forEach((tab) => {
      tab.addEventListener("click", () => this.showTab(tab.dataset.tab));
    });
    dom.prompt.addEventListener("click", () => {
      if (!this.openTerminal()) this.interact();
    });
    dom.terminalPgt.addEventListener("click", () => this.acceptPgt());
    dom.terminalClose.addEventListener("click", () => this.closeTerminal());
    dom.terminalApply.addEventListener("click", () => this.applyFix());
    dom.terminalHint.addEventListener("click", () => this.showHint());
    dom.terminalAsk.addEventListener("click", () => this.askPgt());
    dom.terminalInput.addEventListener("input", () => {
      this.drafts.set(this.terminalTask?.key, dom.terminalInput.value);
      this.terminalEditor.refresh();
      this.terminalEditor.updateCompletion();
    });
    dom.terminalInput.addEventListener("keydown", (event) => {
      if (event.isComposing) return;
      event.stopPropagation();
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        this.applyFix();
        return;
      }
      if (this.terminalEditor.handleKey(event)) return;
      if (event.key === "Escape") {
        if (!this.closeLog()) this.closeTerminal();
        return;
      }
      this.terminalEditor.handleEditingKey(event);
    });
  }

  knownRunes() {
    const index = this.party?.stage?.index ?? 0;
    const known = new Set();
    this.lessons.slice(0, index + 1).forEach((lesson) => {
      lesson.reward.forEach((name) => known.add(name));
    });
    return known;
  }

  // ------------------------------------------------------------------- state
  setProfile(message) {
    this.campaign = message.campaign;
    this.lessons = message.lessons;
    this.tasks = new Map();
    message.lessons.forEach((lesson) => {
      this.tasks.set(lesson.task.key, { task: lesson.task, lesson });
    });
    Object.values(message.quest_tasks || {}).forEach((task) => {
      this.tasks.set(task.key, { task, lesson: null });
    });
    this.relics = message.relics || [];
    this.book = message.book || [];
    this.tickets = message.tickets || [];
    this.crew = message.crew || [];
    this.folk = message.folk || [];
    this.codex.setData(message.codex);
    this.codex.setProfile(message.profile);
    Object.values(message.gates || {}).forEach((task) => {
      this.tasks.set(task.key, { task, lesson: null });
    });
    this.roles = message.roles;
    this.upgrades = message.upgrades;
    this.profile = message.profile;
    this.dom.prologue.replaceChildren(...dialogue(this.campaign.prologue));
    this.showCamp();
  }

  updateProfile(profile) {
    if (!profile) return;
    this.profile = profile;
    this.codex.setProfile(profile);
    this.renderEssence();
    this.renderTree();
    this.renderMap();
    if (this.party) {
      this.renderRoles();
      this.renderBook();
      this.renderTickets();
      this.renderCrew();
      this.renderPeople();
    }
  }

  setParty(party) {
    if (this.profile && party.relics) {
      this.profile.relics = party.relics;
    }
    if (this.profile && party.folk) {
      this.profile.folk = party.folk;
      this.codex.setProfile(this.profile);
    }
    this.party = party;
    this.render();
  }

  clearParty() {
    this.party = null;
    this.result = null;
    this.render();
  }

  setResult(message) {
    this.result = message;
    this.updateProfile(message.profile);
    this.render();
    if (message.finale || message.chapter_done) {
      this.showTab("story");
    } else if (message.duty_over) {
      this.showTab("tickets");
    } else if (message.result === "cleared" || message.result === "wiped") {
      this.showTab("lesson");
    }
  }

  setError(text) {
    this.dom.entryError.textContent = text;
    if (this.party) this.toast(text, "error");
  }

  // ---------------------------------------------------------------- rendering
  showCamp() {
    this.dom.root.hidden = false;
    this.render();
  }

  hideCamp() {
    this.dom.root.hidden = true;
  }

  render() {
    const { dom } = this;
    dom.entry.hidden = Boolean(this.party);
    dom.main.hidden = !this.party;
    if (!this.party) return;
    const { stage } = this.party;
    dom.chapter.textContent = `Глава ${ROMAN[stage.chapter]} · ${stage.chapter_title}`;
    dom.stage.textContent = `${stage.boss ? "Босс" : `Данж ${stage.number}`}: ${stage.title}`;
    dom.code.textContent = this.party.code;
    this.renderEssence();
    this.renderBanner();
    this.renderSeats();
    this.renderMap();
    this.renderDifficulty();
    this.renderStory();
    this.renderBriefing();
    this.renderRoles();
    this.renderTree();
    this.renderBook();
    this.renderTickets();
    this.renderCrew();
    this.renderPeople();
    this.renderExtras();
    this.renderRelics();
    this.showTab(this.tab);
  }

  renderEssence() {
    this.dom.essence.textContent = String(this.profile?.essence ?? 0);
  }

  renderBanner() {
    const { banner } = this.dom;
    const result = this.result;
    banner.hidden = !result;
    if (!result) return;
    const lost = result.result === "wiped" || result.result === "shift_lost";
    banner.classList.toggle("lost", lost);
    const tickets = (result.tickets || []).map((ticket) => `«${ticket.title}» +${ticket.reward}`);
    const closed = tickets.length ? ` Закрыты тикеты: ${tickets.join(", ")}.` : "";
    const texts = {
      cleared: `Этап пройден. Токены: +${result.essence}.${closed}`,
      wiped: `Группа пала. Токены: +${result.essence}. Попробуйте ещё раз.`,
      range: "С полигона вернулись. Манекены не пострадали. Почти.",
      incident: `Инцидент закрыт. На кону ${result.duty?.tokens ?? 0} токенов. Сдать смену или взять следующий?`,
      shift: `Смена сдана. Закрыто инцидентов: ${result.closed}. Токены: +${result.essence}.`,
      shift_lost: `Смену не удержали. Закрыто инцидентов: ${result.closed}. Осталась половина: +${result.essence}.`,
    };
    banner.textContent = texts[result.result] || "";
  }

  /** The way out of camp that is not the campaign: the proving ground and the shift. */
  renderExtras() {
    const { dom } = this;
    const duty = this.party.duty;
    const camp = this.party.state === "camp";
    const leader = this.party.leader;
    const shift = duty?.shift;
    dom.range.disabled = !camp || !leader;
    dom.duty.disabled = !camp || !leader || !duty?.open;
    dom.duty.textContent = shift ? "Следующий инцидент" : "Дежурство";
    dom.duty.title = duty?.open
      ? "Инцидент за инцидентом, каждый тяжелее. Токены копятся и выплачиваются, когда смена сдана. Пропустите удар в конце, потеряете половину."
      : "Откроется после первой главы.";
    dom.dutyEnd.hidden = !shift;
    dom.dutyEnd.disabled = !camp || !leader;
    dom.dutyAbout.hidden = !shift && !duty?.best;
    if (shift) {
      dom.dutyAbout.textContent = `Смена: закрыто ${shift.closed}, на кону ${shift.tokens} токенов.`;
    } else if (duty?.best) {
      dom.dutyAbout.textContent = `Ваш рекорд дежурства: ${duty.best}.`;
    }
  }

  /** What the paperclip has to say about an error, once she has moved in. */
  clipTip(error) {
    if ((this.profile?.cleared ?? 0) < CLIP_FROM) return "";
    const match = CLIP_TIPS.find(([pattern]) => pattern.test(String(error)));
    return match ? `Скрепка: ${match[1]}` : "";
  }

  renderSeats() {
    const { seats, ready } = this.dom;
    const you = this.party.seats.find((seat) => seat.you);
    seats.replaceChildren(
      ...this.party.seats.map((seat) => {
        const row = element("li", "camp-seat");
        row.classList.toggle("offline", !seat.online);
        row.classList.toggle("ready", seat.ready);
        const dot = element("span", "camp-seat-dot");
        dot.style.setProperty("--player-color", seat.color);
        const name = element("span", "camp-seat-name", `${seat.name}${seat.you ? " (вы)" : ""}`);
        const state = element(
          "span",
          "camp-seat-state",
          !seat.online ? "нет связи" : seat.ready ? "готов" : seat.leader ? "лидер" : "",
        );
        const role = this.roleOf(seat.role);
        const job = element("span", "camp-seat-role", role?.title || "");
        job.style.color = role?.color || "";
        row.append(dot, name, job, state);
        return row;
      }),
    );
    const alone = this.party.seats.filter((seat) => seat.online).length === 1;
    const finished = this.party.state === "finished";
    ready.disabled = finished;
    if (finished) {
      ready.textContent = "Кампания пройдена";
    } else if (you?.ready) {
      ready.textContent = "Жду остальных…";
    } else if (this.party.duty?.shift) {
      ready.textContent = "На инцидент";
    } else {
      ready.textContent = alone ? "В бой" : "Готов";
    }
  }

  renderMap() {
    const { map } = this.dom;
    if (!this.party || !this.campaign) return;
    const limit = this.party.stage_limit;
    const cleared = this.profile?.cleared ?? 0;
    const rows = this.campaign.chapters.map((chapter, chapterIndex) => {
      const row = element("div", "camp-chapter");
      row.dataset.theme = chapter.theme;
      row.append(element("span", "camp-chapter-title", `${ROMAN[chapterIndex]}. ${chapter.title}`));
      const dots = element("div", "camp-stages");
      this.campaign.stages
        .filter((stage) => stage.chapter === chapterIndex)
        .forEach((stage) => {
          const button = element("button", "camp-stage", stage.boss ? "♛" : String(stage.number));
          button.type = "button";
          const owed = this.tickets[stage.index] || [];
          const closed = owed.filter((ticket) => this.ticketClosed(ticket)).length;
          button.title = `${stage.title}. Тикетов закрыто: ${closed} из ${owed.length}`;
          button.disabled = stage.index > limit || !this.party.leader || Boolean(this.party.duty?.shift);
          if (owed.length) {
            const pips = element("span", "camp-stage-pips");
            pips.append(...owed.map((ticket) => element("i", this.ticketClosed(ticket) ? "on" : "")));
            button.append(pips);
          }
          button.classList.toggle("done", stage.index < cleared);
          button.classList.toggle("current", stage.index === this.party.stage.index);
          button.addEventListener("click", () => {
            this.send({ t: "party_stage", stage: stage.index });
          });
          dots.append(button);
        });
      row.append(dots);
      return row;
    });
    map.replaceChildren(...rows);
  }

  renderDifficulty() {
    const { difficulty, difficultyAbout } = this.dom;
    const levels = this.campaign?.difficulties || [];
    const chosen = levels.find((entry) => entry.level === this.party.difficulty);
    difficulty.replaceChildren(
      ...levels.map((entry) => {
        const button = element("button", "camp-difficulty-level", entry.title);
        button.type = "button";
        button.disabled = !this.party.leader;
        button.classList.toggle("active", entry === chosen);
        button.addEventListener("click", () => {
          this.send({ t: "party_difficulty", level: entry.level });
        });
        return button;
      }),
    );
    if (!chosen) return;
    const rate = String(chosen.reward).replace(".", ",");
    const bonus = chosen.reward > 1 ? ` Токены ×${rate}.` : "";
    const who = this.party.leader ? "" : " Выбирает лидер.";
    difficultyAbout.textContent = `${chosen.about}${bonus}${who}`;
  }

  renderStory() {
    const { story } = this.dom;
    const { stage } = this.party;
    const parts = [];
    const chapter = this.campaign.chapters[stage.chapter];
    if (this.party.state === "finished") {
      parts.push(...this.finaleParts());
    } else {
      if (this.result?.chapter_done) {
        const past = this.campaign.chapters[this.result.stage.chapter];
        parts.push(...dialogue(past.outro));
      }
      if (stage.index === 0) {
        parts.push(...dialogue(this.campaign.prologue));
      }
      if (stage.number === 1) {
        parts.push(element("h3", "", chapter.title));
        parts.push(...dialogue(chapter.intro));
      }
      parts.push(element("h3", "", stage.title));
      parts.push(element("p", "camp-subject", chapter.subject));
    }
    story.replaceChildren(...parts);
  }

  /** After PGT falls: first the choice, then what came of it, then the way back. */
  finaleParts() {
    const parts = [];
    const chosen = this.campaign.endings.find((entry) => entry.key === this.party.ending);
    if (!chosen) {
      parts.push(...dialogue(this.campaign.decision));
      const choices = element("div", "ending-choices");
      choices.append(
        ...this.campaign.endings.map((ending) => {
          const button = element("button", "ending-choice");
          button.type = "button";
          button.append(
            element("code", "", ending.command),
            element("b", "", ending.title),
            element("span", "", ending.about),
          );
          button.addEventListener("click", () => {
            this.send({ t: "ending_pick", ending: ending.key });
          });
          return button;
        }),
      );
      parts.push(choices);
      return parts;
    }
    parts.push(element("p", "ending-command", `$ ${chosen.command}`));
    parts.push(...dialogue(chosen.lines));
    parts.push(...this.pytestReport());
    const found = new Set(this.profile?.relics || []);
    if (this.relics.length && this.relics.every((relic) => found.has(relic.key))) {
      parts.push(element("h3", "", "git log --all"));
      parts.push(...dialogue(this.campaign.secret_ending));
    } else {
      parts.push(element("p", "camp-subject", "В архиве ещё есть непрочитанные коммиты. Говорят, там есть кое-что важное."));
    }
    const back = element("button", "text-button", "Вернуться в штаб");
    back.type = "button";
    back.addEventListener("click", () => this.send({ t: "party_continue" }));
    parts.push(back);
    return parts;
  }

  /** The test the real Ada wrote as a joke: by now it lists everyone who was helped. */
  pytestReport() {
    const done = this.profile?.folk || {};
    const counts = { passed: 0, skipped: 0, none: 0 };
    const rows = this.folk.map((person) => {
      const status = done[person.key] || "none";
      counts[status] += 1;
      const row = element("div", `pytest-row ${status}`);
      row.append(element("code", "", person.test), element("b", "", PYTEST_WORD[status]));
      if (status === "passed") row.append(element("p", "", person.epilogue));
      return row;
    });
    const summary = element(
      "p",
      "pytest-summary",
      `${counts.passed} passed, ${counts.skipped} skipped, ${counts.none} not run`,
    );
    return [element("h3", "pytest-head", "$ pytest test_people_matter.py -v"), ...rows, summary];
  }

  renderPeople() {
    const { people, peopleIntro } = this.dom;
    if (!people) return;
    const done = this.profile?.folk || {};
    const cleared = this.profile?.cleared ?? 0;
    const opened = cleared >= TEST_OPENS;
    const finished = (this.profile?.endings || []).length > 0;
    const passed = this.folk.filter((person) => done[person.key] === "passed").length;
    peopleIntro.textContent = opened
      ? `$ pytest test_people_matter.py. Зелёных ${passed} из ${this.folk.length}. Каждый зелёный тест делает финального босса слабее на 1%. «Принять» теста не проходит: он будет SKIPPED и усилит PGT.`
      : `Те, кто встретился по дороге. Помогли: ${passed} из ${this.folk.length}. На этапе подойдите к человеку с восклицательным знаком и нажмите E. Сюда можно вернуться: все ждут, пока им не помогут.`;
    people.replaceChildren(
      ...this.folk.map((person) => {
        const status = done[person.key] || "none";
        const card = element("article", `people-card ${status}`);
        if (status === "none") {
          card.append(
            element("h4", "", "Пока не встретили"),
            element("p", "people-title", `Где-то в главе «${person.chapter}»`),
          );
          if (opened) card.append(element("code", "", `${person.test}: NOT RUN`));
          return card;
        }
        card.append(element("h4", "", person.name), element("p", "people-title", person.title));
        if (opened) card.append(element("code", "", `${person.test}: ${PYTEST_WORD[status]}`));
        if (status === "skipped") {
          card.append(element("blockquote", "", "За него всё сделал PGT. Можно вернуться и помочь по-настоящему."));
        } else {
          const words = finished ? person.epilogue : person.after;
          if (words) card.append(element("blockquote", "", words));
        }
        return card;
      }),
    );
  }

  // ---------------------------------------------------------------- the book
  renderBook() {
    const owned = new Set(this.profile?.runes || []);
    const essence = this.profile?.essence ?? 0;
    this.dom.book.replaceChildren(
      ...this.book.map((rune) => {
        const have = owned.has(rune.name);
        const card = element("article", `book-card tier-${rune.tier} ${have ? "owned" : ""}`);
        const button = element(
          "button",
          "book-buy",
          have ? "В гримуаре" : essence >= rune.price ? `Купить за ${rune.price}` : `Нужно ${rune.price}`,
        );
        button.type = "button";
        button.disabled = have || essence < rune.price;
        button.addEventListener("click", () => this.send({ t: "rune_buy", name: rune.name }));
        const stats = [`мана ${rune.cost}`];
        if (rune.cooldown) stats.push(`перезарядка ${String(rune.cooldown).replace(".", ",")} с`);
        card.append(
          element("code", "book-sign", rune.signature),
          element("h4", "", rune.title),
          element("p", "", rune.about),
          element("p", "book-idea", `Учит: ${rune.idea}`),
          element("pre", "book-example", rune.example),
          element("p", "book-stats", stats.join(" · ")),
          button,
        );
        return card;
      }),
    );
  }

  // ------------------------------------------------------------------ tickets
  ticketClosed(ticket) {
    return (this.profile?.tickets || []).includes(ticket.key);
  }

  renderTickets() {
    const { ticketBoard, ticketCount } = this.dom;
    const all = this.tickets.flat();
    const closedCount = all.filter((ticket) => this.ticketClosed(ticket)).length;
    ticketCount.textContent = `Закрыто ${closedCount} из ${all.length}.`;
    const limit = this.party?.stage_limit ?? 0;
    const rows = this.campaign.stages
      .filter((stage) => stage.index <= limit)
      .map((stage) => {
        const row = element("article", "ticket-row");
        row.classList.toggle("current", stage.index === this.party?.stage?.index);
        row.append(
          element("h4", "", `${ROMAN[stage.chapter]}-${stage.number}. ${stage.title}`),
        );
        const list = element("div", "ticket-list");
        list.append(
          ...(this.tickets[stage.index] || []).map((ticket) => {
            const done = this.ticketClosed(ticket);
            const item = element("div", `ticket ${done ? "done" : ""}`);
            item.title = ticket.about;
            item.append(
              element("b", "", ticket.title),
              element("span", "", ticket.about),
              element("em", "", done ? "закрыт" : `+${ticket.reward}`),
            );
            return item;
          }),
        );
        row.append(list);
        return row;
      });
    const board = this.party?.duty?.board || [];
    const shift = element("article", "ticket-row duty-board");
    shift.append(element("h4", "", "Рекорды дежурства на этом сервере"));
    if (board.length) {
      const list = element("ol");
      list.append(
        ...board.map((entry) => element("li", "", `${entry.name}: инцидентов ${entry.score}`)),
      );
      shift.append(list);
    } else {
      shift.append(element("p", "camp-subject", "Пока никто не сдал смену."));
    }
    ticketBoard.replaceChildren(shift, ...rows);
  }

  // --------------------------------------------------------------------- crew
  renderCrew() {
    const cleared = this.profile?.cleared ?? 0;
    this.dom.crew.replaceChildren(
      ...this.crew.map((member) => {
        const here = cleared >= member.joins;
        const card = element("article", `crew-card ${here ? "" : "unknown"}`);
        if (!here) {
          card.append(
            element("h4", "", "Пока неизвестно кто"),
            element("p", "crew-title", `Этап ${member.joins} из ${this.campaign.stages.length}: кого-то ещё можно спасти.`),
          );
          return card;
        }
        const line = [...member.lines].reverse().find(([at]) => cleared >= at);
        card.append(
          element("h4", "", member.name),
          element("p", "crew-title", member.title),
          element("blockquote", "", `«${line[1]}»`),
          element("p", "crew-perk", member.perk),
        );
        return card;
      }),
    );
  }

  roleOf(key) {
    return this.roles?.roles.find((role) => role.key === key) || null;
  }

  rolesOpen() {
    const opensAt = this.roles?.unlock ?? 0;
    return this.party.stage.index >= opensAt || (this.profile?.cleared ?? 0) >= opensAt;
  }

  renderRoles() {
    const { dom } = this;
    if (!this.roles) return;
    const open = this.rolesOpen();
    const chosen = this.profile?.role || "";
    dom.roleTab.classList.toggle("attention", open && !chosen);
    dom.roleIntro.textContent = open
      ? "Роль добавляет способности, но ничего не отнимает: все руны остаются с вами. Навыки вызываются из кода, как и руны, поэтому когда и на кого их применять, решает ваша программа. Первый навык работает со второй главы, второй с третьей. Роль можно менять перед любым этапом."
      : "Роли откроются после первой главы.";
    dom.roleCards.replaceChildren(
      ...this.roles.roles.map((role) => this.roleCard(role, open, role.key === chosen)),
    );
  }

  roleCard(role, open, chosen) {
    const card = element("article", "role-card");
    card.classList.toggle("active", chosen);
    card.style.setProperty("--role-color", role.color);
    card.append(
      element("h4", "role-name", role.title),
      element("p", "role-tagline", role.tagline),
      element("p", "role-passive", role.passive),
    );
    role.skills.forEach((skill) => {
      const block = element("div", "role-skill");
      block.append(
        element("code", "", skill.signature),
        element("p", "", skill.about),
        element(
          "span",
          "role-skill-meta",
          `${skill.cost} маны · ${skill.cooldown} с · с главы ${ROMAN[skill.stage / 4]}`,
        ),
      );
      card.append(block);
    });
    const example = element("details", "role-example");
    example.append(element("summary", "", "Пример кода"), element("pre", "lesson-example", role.example));
    card.append(example);
    const button = element("button", "upgrade-buy", chosen ? "Ваша роль" : "Выбрать");
    button.type = "button";
    button.disabled = !open || chosen;
    button.addEventListener("click", () => this.send({ t: "role_pick", role: role.key }));
    card.append(button);
    return card;
  }

  renderBriefing() {
    const { dom } = this;
    const index = this.party.stage.index;
    const lesson = this.lessons[index];
    if (!lesson || index === this.lessonIndex) return;
    this.lessonIndex = index;
    dom.lessonTitle.textContent = lesson.title;
    dom.lessonRune.hidden = !lesson.reward.length;
    dom.lessonRune.textContent = lesson.reward
      .map((name) =>
        name === "enemies" || name === "allies" ? `Новая функция: ${name}()` : `Новая руна: ${name}`,
      )
      .join(" · ");
    dom.lessonTheory.replaceChildren(...lesson.theory.map((line) => element("p", "", line)));
    dom.lessonExample.textContent = lesson.example;
    dom.lessonTask.textContent = lesson.task.brief;
  }

  // --------------------------------------------------------------- terminals
  openTerminal() {
    const terminal = this.nearTerminal;
    if (!terminal || this.terminalTask || terminal.busy) return false;
    this.send({ t: "terminal_open" });
    return true;
  }

  // ------------------------------------------------------------ conversations
  talkOpen() {
    return this.talk !== null;
  }

  /** Which face goes with a name: the server says for those standing in a room. */
  faceOf(name, sprite = "") {
    if (sprite && hasPortrait(sprite)) return { key: sprite, tag: "" };
    if (SPEAKER_FACES[name]) return { key: SPEAKER_FACES[name], tag: "" };
    const person = this.folk.find((entry) => entry.name === name);
    if (person) return { key: person.sprite, tag: "" };
    return { key: "machine", tag: MACHINE_TAGS[name] || name.slice(0, 3) };
  }

  openTalk(event) {
    const { dom } = this;
    const replies = event.replies || [];
    this.talkWriter?.stop();
    window.clearTimeout(this.talkTimer);
    this.holdRadio();
    const face = this.faceOf(event.name, event.sprite);
    const fresh = this.talk?.thing !== event.thing;
    this.talk = { thing: event.thing, replies, face, talking: true };
    dom.npcName.textContent = event.name;
    dom.npcCode.textContent = event.code || "";
    dom.npcCode.hidden = !event.code;
    dom.npcTalk.classList.remove("ready");
    dom.npcDim.hidden = false;
    dom.npcTalk.hidden = false;
    if (fresh) {
      dom.npcTalk.classList.remove("arrive");
      void dom.npcTalk.offsetWidth;
      dom.npcTalk.classList.add("arrive");
    }
    this.remember({ line: [event.name, event.text] });
    this.renderReplies(replies);
    this.talkWriter = new TypeWriter(dom.npcText, event.text, {
      speed: TALK_SPEED,
      onLetter: this.voiced(face.key, 1),
      onDone: () => this.talkFinished(),
    });
    this.startFaces();
  }

  /** What a letter sounds like when this person says it. Punctuation is silence. */
  voiced(key, volume) {
    const voice = voiceOf(key);
    const speak = hasSoftVoice(key) ? "softBlip" : "blip";
    return (char) => {
      if (SPOKEN.test(char)) this.sound[speak](voice, volume);
    };
  }

  renderReplies(replies) {
    const { dom } = this;
    // Short answers go in a row: a tall panel would hide the mage it is talking to.
    dom.npcReplies.classList.toggle(
      "compact",
      replies.length > 1 && replies.every(([, text]) => text.length <= SHORT_REPLY),
    );
    if (replies.length) {
      dom.npcReplies.replaceChildren(
        ...replies.map(([, text], index) => {
          const button = element("button", "npc-reply");
          button.type = "button";
          button.style.setProperty("--order", index);
          button.append(element("kbd", "", String(index + 1)), element("span", "", text));
          button.addEventListener("click", () => this.chooseReply(index));
          return button;
        }),
      );
      return;
    }
    const close = element("button", "npc-reply");
    close.type = "button";
    close.append(element("kbd", "", "E"), element("span", "", "Понятно"));
    close.addEventListener("click", () => this.closeTalk());
    dom.npcReplies.replaceChildren(close);
  }

  /** The words are all there: now the replies, which were only waiting for them. */
  talkFinished() {
    if (!this.talk) return;
    this.talk.talking = false;
    this.dom.npcTalk.classList.add("ready");
    if (!this.talk.replies.length) {
      this.talkTimer = window.setTimeout(() => this.closeTalk(), TALK_LINGER);
    }
  }

  talkTyping() {
    return Boolean(this.talkWriter && !this.talkWriter.done);
  }

  skipTalk() {
    if (!this.talkTyping()) return false;
    this.talkWriter.skip();
    return true;
  }

  closeTalk() {
    window.clearTimeout(this.talkTimer);
    this.talkWriter?.stop();
    this.talkWriter = null;
    this.talk = null;
    this.dom.npcTalk.hidden = true;
    this.dom.npcDim.hidden = true;
  }

  chooseReply(index) {
    if (this.skipTalk()) return true;
    const reply = this.talk?.replies[index];
    if (!reply) return false;
    this.send({ t: "npc_reply", thing: this.talk.thing, reply: reply[0] });
    return true;
  }

  /** E: finish the sentence, then dismiss whatever needs no answer. */
  talkKey() {
    if (this.skipTalk()) return true;
    if (!this.talk?.replies.length) {
      this.closeTalk();
      return true;
    }
    return false;
  }

  // Faces only move while someone is looking at them.
  startFaces() {
    if (this.faceFrame !== null) return;
    const paint = (now) => {
      const { talk, radioFace } = this;
      if (!talk && !radioFace) {
        this.faceFrame = null;
        return;
      }
      if (talk) {
        const ctx = this.dom.npcPortrait.getContext("2d");
        paintPortrait(ctx, talk.face.key, { talking: talk.talking, now, tag: talk.face.tag, seed: talk.thing });
      }
      if (radioFace) {
        const talking = Boolean(this.radioWriter && !this.radioWriter.done);
        paintPortrait(radioFace.ctx, radioFace.key, { talking, now, tag: radioFace.tag, seed: 3 });
      }
      this.faceFrame = window.requestAnimationFrame(paint);
    };
    this.faceFrame = window.requestAnimationFrame(paint);
  }

  /** A conversation does not follow anyone across the room. */
  watchTalk(quest, me) {
    if (!this.talk || !me) return;
    const thing = (quest?.things || []).find((entry) => entry.id === this.talk.thing);
    if (thing && Math.hypot(thing.x - me.x, thing.y - me.y) > TALK_REACH) this.closeTalk();
  }

  /** E on a chest, an altar, or the packet in your hands. */
  interact() {
    if (!this.nearUse || this.terminalTask) return false;
    this.send({ t: "interact" });
    return true;
  }

  acceptPgt() {
    if (!this.terminalTask || this.terminalRole !== "quest") return;
    this.send({ t: "quest_pgt" });
  }

  terminalState(message) {
    if (!message.linked) {
      if (message.error) this.toast(message.error, "error");
      return;
    }
    const entry = this.tasks.get(message.task);
    if (!entry) return;
    this.showTerminal(entry, message.role, message.help);
  }

  helpSteps() {
    return this.help.hints + (this.help.solution ? 1 : 0);
  }

  showTerminal({ task, lesson }, role, help) {
    const { dom } = this;
    this.terminalTask = task;
    this.terminalRole = role;
    this.hintsShown = 0;
    this.help = help || { hints: 0, solution: false, theory: false };
    this.onTerminal(true);
    dom.prompt.hidden = true;
    dom.terminalKind.textContent = STAGE_KIND[role] || "ТЕРМИНАЛ";
    dom.terminalTitle.textContent = lesson?.title || task.title || "Баг босса";
    dom.terminalPgt.hidden = role !== "quest";
    dom.terminalBrief.textContent = task.brief;
    dom.terminalTheoryBox.hidden = !lesson || !this.help.theory;
    dom.terminalTheoryBox.open = false;
    dom.terminalTheory.replaceChildren(
      ...(lesson?.theory || []).map((line) => element("p", "", line)),
    );
    dom.terminalExample.textContent = lesson?.example || "";
    dom.terminalHelp.replaceChildren();
    dom.terminalHint.hidden = !this.helpSteps();
    dom.terminalHint.disabled = false;
    dom.terminalHint.textContent = "Подсказка";
    dom.terminalInput.value = this.drafts.get(task.key) ?? task.starter;
    this.showVerdict("", true);
    this.terminalEditor.setErrorLine(null);
    dom.terminal.hidden = false;
    this.terminalEditor.refresh();
    dom.terminalInput.focus();
    if (this.partySize === 1 && !this.toldAlone) {
      this.toldAlone = true;
      this.say([[ADA, this.campaign.alerts.alone]]);
    }
  }

  closeTerminal({ notify = true } = {}) {
    if (!this.terminalTask) return;
    const { dom } = this;
    this.terminalTask = null;
    this.terminalEditor.closeCompletion();
    dom.terminalInput.blur();
    dom.terminal.hidden = true;
    this.onTerminal(false);
    if (notify) this.send({ t: "terminal_close" });
  }

  showVerdict(text, ok) {
    const { terminalResult } = this.dom;
    terminalResult.textContent = text;
    terminalResult.className = `lesson-result ${text ? (ok ? "ok" : "bad") : ""}`;
  }

  applyFix() {
    if (!this.terminalTask) return;
    this.showVerdict("Запускаю тесты…", true);
    this.send({ t: "fix_submit", code: this.dom.terminalInput.value });
  }

  fixResult(message) {
    if (!this.terminalTask) return;
    if (message.pgt) {
      if (message.ok) {
        this.sound.play("error");
        this.closeTerminal({ notify: false });
        this.toast("PGT «починил» консоль. Токенов за это не будет.", "error");
      } else {
        this.showVerdict(String(message.message || "PGT здесь не поможет."), false);
      }
      return;
    }
    if (!message.ok) {
      this.sound.play("error");
      this.showVerdict(String(message.message), false);
      const line = String(message.message).match(/Строка (\d+):/);
      this.terminalEditor.setErrorLine(line ? Number(line[1]) : null);
      this.addHelp(dialogueLine([BOT, pick(this.campaign.quips.fix_bad)]));
      return;
    }
    const reward = Number(message.reward) || 0;
    this.sound.play("heal");
    this.updateProfile(message.profile);
    this.closeTerminal({ notify: false });
    this.toast(reward ? `Патч применён. Токены: +${reward}` : "Патч применён.");
    if (message.task === "radar") this.say([[ADA, this.campaign.alerts.radar]]);
    else this.quip("fix_good", 0.6);
  }

  /** Help lives on the server: what this difficulty forbids never reaches the browser. */
  showHint() {
    if (!this.terminalTask || this.hintsShown >= this.helpSteps()) return;
    this.dom.terminalHint.disabled = true;
    this.send({ t: "terminal_help", index: this.hintsShown });
  }

  terminalHelp(message) {
    const { dom } = this;
    if (!this.terminalTask || !message.kind) return;
    this.addHelp(
      message.kind === "hint"
        ? dialogueLine([ADA, message.text])
        : element("pre", "lesson-example", message.text),
    );
    this.hintsShown += 1;
    const left = this.helpSteps() - this.hintsShown;
    dom.terminalHint.disabled = left <= 0;
    if (left <= 0) dom.terminalHint.textContent = "Больше помочь нечем";
    else if (this.hintsShown >= this.help.hints) dom.terminalHint.textContent = "Показать решение";
    else dom.terminalHint.textContent = "Ещё подсказка";
  }

  askPgt() {
    const { terminalTask: task } = this;
    if (task) this.addHelp(dialogueLine([BOT, task.pgt]));
  }

  /** A short conversation, oldest on top: only the last few lines stay useful. */
  addHelp(node) {
    const { terminalHelp, terminalBrief } = this.dom;
    terminalHelp.append(node);
    while (terminalHelp.childElementCount > HELP_LINES) terminalHelp.firstElementChild.remove();
    terminalBrief.parentElement.scrollTop = terminalBrief.parentElement.scrollHeight;
  }

  /** Everything ever dug out from behind a cracked wall, and how much is still out there. */
  renderRelics() {
    const { relics, relicCount } = this.dom;
    const found = new Set(this.profile?.relics || []);
    relicCount.textContent = `Найдено ${[...this.relics].filter((r) => found.has(r.key)).length} из ${this.relics.length}`;
    relics.replaceChildren(
      ...this.relics.map((relic) => {
        const known = found.has(relic.key);
        const card = element("article", `relic-card ${known ? "" : "unknown"}`);
        card.append(
          element("h4", "", known ? relic.title : "???"),
          element("p", "", known ? relic.about : "Где-то за треснувшей стеной."),
        );
        if (known) card.append(element("code", "relic-commit", relic.commit));
        return card;
      }),
    );
  }

  renderTree() {
    const { tree } = this.dom;
    if (!this.upgrades || !this.profile) return;
    const { stats, branches } = this.upgrades;
    const columns = Object.entries(branches).map(([branch, title]) => {
      const column = element("section", `upgrade-branch ${branch}`);
      column.append(element("h4", "upgrade-branch-title", title));
      Object.entries(stats)
        .filter(([, stat]) => stat.branch === branch)
        .forEach(([key, stat]) => column.append(this.upgradeNode(key, stat)));
      return column;
    });
    tree.replaceChildren(...columns);
  }

  upgradeNode(key, stat) {
    const { stats, max_level: maxLevel } = this.upgrades;
    const owned = this.profile.upgrades;
    const level = owned[key] || 0;
    const sign = stat.sign || "+";
    const amount = (step) => `${sign}${Number(step.toFixed(2))} ${stat.unit}`;
    const node = element("article", "upgrade-node");
    node.classList.toggle("maxed", level >= maxLevel);
    node.append(
      element("strong", "upgrade-name", stat.title),
      element("p", "upgrade-about", stat.about),
    );
    const pips = element("div", "upgrade-pips");
    for (let index = 0; index < maxLevel; index += 1) {
      pips.append(element("i", index < level ? "on" : ""));
    }
    node.append(pips);
    if (level) node.append(element("p", "upgrade-bonus", amount(stat.step * level)));

    const blocked = stat.needs && (owned[stat.needs] || 0) <= level;
    const button = element("button", "upgrade-buy");
    button.type = "button";
    if (level >= maxLevel) {
      button.textContent = "Максимум";
      button.disabled = true;
    } else if (blocked) {
      button.textContent = `Сначала «${stats[stat.needs].title}»`;
      button.disabled = true;
    } else {
      const cost = stat.costs[level];
      button.textContent = `${amount(stat.step)} за ${cost}`;
      button.disabled = this.profile.essence < cost;
      button.addEventListener("click", () => this.send({ t: "upgrade", stat: key }));
    }
    node.append(button);
    return node;
  }

  showTab(name) {
    this.tab = name;
    this.dom.tabs.forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.tab === name);
    });
    this.dom.panels.forEach((panel) => {
      panel.hidden = panel.dataset.panel !== name;
    });
  }

  // ------------------------------------------------------------------ dungeon
  enterStage(message) {
    const { dom } = this;
    const { stage } = message;
    this.bestiary = message.config.bestiary || {};
    this.hideCamp();
    this.closeTerminal({ notify: false });
    this.leakNoticed = false;
    dom.hud.hidden = false;
    dom.bossBar.hidden = true;
    dom.intro.hidden = true;
    dom.prompt.hidden = true;
    const level = this.campaign?.difficulties.find(
      (entry) => entry.level === message.config.difficulty,
    );
    dom.hudStage.textContent = `${ROMAN[stage.chapter]}-${stage.number}. ${stage.title} · ${level?.title ?? ""}`;
    this.clearComms();
    this.remember({ stage: dom.hudStage.textContent });
    this.say(stage.chat);
    if (message.readout?.length) this.say(message.readout);
    this.stageConfig = message.config;
    this.isRange = Boolean(message.config.range);
    dom.rangeCard.hidden = !this.isRange;
    if (this.isRange) dom.hudStage.textContent = "Полигон";
    if (message.config.terrain?.intro?.length) this.say(message.config.terrain.intro);
    this.lastEvent = "";
    this.lastFinds = "";
    dom.eventChip.hidden = true;
    dom.finds.replaceChildren();
    const quest = message.config.quest;
    this.lastQuest = "";
    this.lastCode = "";
    dom.codeCard.hidden = true;
    dom.quest.hidden = !quest;
    if (quest) {
      dom.questTech.textContent = quest.tech;
      dom.questTitle.textContent = quest.title;
      dom.questText.textContent = "";
      dom.questBar.hidden = true;
      this.say(quest.intro);
    }
  }

  leaveStage() {
    this.dom.hud.hidden = true;
    this.dom.quest.hidden = true;
    this.dom.rangeCard.hidden = true;
    this.dom.codeCard.hidden = true;
    this.stageConfig = null;
    this.nearUse = false;
    this.dom.frames.replaceChildren();
    this.lastFrames = "";
    this.lastSkills = "";
    this.lastCurses = "";
    this.dom.roleBar.hidden = true;
    this.dom.curseBar.hidden = true;
    this.dom.bossShout.hidden = true;
    this.dom.deployBar.hidden = true;
    this.closeTerminal({ notify: false });
    this.closeTalk();
    this.lastFolk = "";
    this.dom.folkList.hidden = true;
    this.clearComms();
    this.nearTerminal = null;
    this.dom.prompt.hidden = true;
    this.dom.intro.hidden = true;
  }

  // ------------------------------------------------------------------- radio
  say(lines, urgent = false) {
    lines.forEach((line) => this.remember({ line }));
    if (urgent) {
      this.comms.unshift(...lines);
      window.clearTimeout(this.commsTimer);
      this.commsTimer = null;
      this.hideRadioLine();
    } else {
      this.comms.push(...lines);
    }
    if (this.commsTimer === null) this.nextComms();
  }

  /** Everything said on the radio stays here: a fight rarely leaves time to read. */
  remember(entry) {
    const history = this.commsHistory;
    history.push(entry);
    if (history.length > LOG_LIMIT) history.shift();
    if (!this.dom.commsLog.hidden) this.appendLog(entry);
  }

  logNode(entry, before) {
    if (entry.stage) return element("h4", "comms-log-stage", entry.stage);
    const line = dialogueLine(entry.line);
    line.classList.toggle("continued", before?.line?.[0] === entry.line[0]);
    return line;
  }

  appendLog(entry) {
    const { commsHistory: history } = this;
    const body = this.dom.commsLogBody;
    const atEnd = body.scrollHeight - body.scrollTop - body.clientHeight < LOG_STICK;
    body.append(this.logNode(entry, history[history.length - 2]));
    while (body.childElementCount > LOG_LIMIT) body.firstElementChild.remove();
    // Someone reading further up should not be yanked back down mid-sentence.
    if (atEnd) body.scrollTop = body.scrollHeight;
  }

  toggleLog() {
    const { commsLog, commsLogBody } = this.dom;
    commsLog.hidden = !commsLog.hidden;
    if (commsLog.hidden) return;
    const history = this.commsHistory;
    commsLogBody.replaceChildren(
      ...history.map((entry, index) => this.logNode(entry, history[index - 1])),
    );
    if (!history.length) {
      commsLogBody.append(element("p", "comms-log-empty", "Рация пока молчит."));
    }
    commsLogBody.scrollTop = commsLogBody.scrollHeight;
  }

  /** Returns whether there was a journal to close, so Esc does one thing at a time. */
  closeLog() {
    const { commsLog } = this.dom;
    if (commsLog.hidden) return false;
    commsLog.hidden = true;
    return true;
  }

  /** The assistant has an opinion on everything, but never talks over anyone. */
  quip(kind, chance = 1) {
    const lines = this.campaign?.quips[kind];
    if (!lines || this.commsTimer !== null || Math.random() > chance) return;
    this.say([[BOT, pick(lines)]]);
  }

  nextComms() {
    const { commsBox } = this.dom;
    if (this.talk) {
      this.commsTimer = window.setTimeout(() => this.nextComms(), RADIO_HOLD);
      return;
    }
    const line = this.comms.shift();
    if (!line) {
      commsBox.hidden = true;
      this.commsTimer = null;
      return;
    }
    this.showRadioLine(line);
    const time = COMMS_BASE + line[1].length * COMMS_PER_CHAR;
    this.commsTimer = window.setTimeout(() => {
      this.hideRadioLine();
      this.commsTimer = window.setTimeout(() => this.nextComms(), COMMS_GAP);
    }, time);
  }

  showRadioLine(line) {
    const { commsBox } = this.dom;
    const row = element("div", "comms-line");
    const canvas = element("canvas", "comms-face");
    canvas.width = PORTRAIT_GRID;
    canvas.height = PORTRAIT_GRID;
    const words = dialogueLine(line);
    row.append(canvas, words);
    commsBox.replaceChildren(row);
    commsBox.hidden = false;
    const face = this.faceOf(line[0]);
    this.radioFace = { ...face, ctx: canvas.getContext("2d") };
    this.radioLine = line;
    this.radioWriter?.stop();
    this.radioWriter = new TypeWriter(words.querySelector("span"), line[1], {
      speed: RADIO_SPEED,
      onLetter: this.voiced(face.key, RADIO_VOLUME),
    });
    this.startFaces();
  }

  hideRadioLine() {
    this.dom.commsBox.hidden = true;
    this.radioWriter?.stop();
    this.radioWriter = null;
    this.radioFace = null;
    this.radioLine = null;
  }

  /** A conversation takes the floor: whatever the radio was saying waits its turn. */
  holdRadio() {
    if (this.radioLine) this.comms.unshift(this.radioLine);
    this.hideRadioLine();
    window.clearTimeout(this.commsTimer);
    this.commsTimer = window.setTimeout(() => this.nextComms(), RADIO_HOLD);
  }

  clearComms() {
    window.clearTimeout(this.commsTimer);
    this.commsTimer = null;
    this.comms = [];
    this.hideRadioLine();
  }

  handleEvent(event, selfId) {
    const alerts = this.campaign?.alerts;
    if (!alerts) return;
    switch (event.e) {
      case "intro":
        this.introduce(event.kind);
        break;
      case "room_lock":
        this.quip("room", 0.4);
        break;
      case "room_clear":
        this.quip("clear", 0.4);
        break;
      case "death":
        if (event.id === selfId) this.quip("death");
        break;
      case "boss_cast":
        this.shout(event.error);
        if (event.tip) this.say([[ADA, event.tip]], true);
        break;
      case "gate_open":
        this.say([[ADA, alerts.gate]], true);
        break;
      case "gate_lift":
        this.say([[ADA, alerts.lifted]], true);
        break;
      case "fix_done":
        if (event.role === "door") this.say([[ADA, alerts.door]], true);
        else if (event.role === "portal") this.say([[ADA, alerts.portal]], true);
        break;
      case "radio":
        if (Array.isArray(event.lines)) this.say(event.lines, Boolean(event.urgent));
        break;
      case "npc_talk":
        if (event.to === selfId) this.openTalk(event);
        break;
      case "npc_close":
        if (event.to === selfId) this.closeTalk();
        break;
      case "folk_done":
        this.folkDone(event);
        break;
      case "find_taken":
        this.toast(`${event.title}: ${event.about}`);
        break;
      case "relic_found":
        this.toast(`В архив: ${event.title}`);
        if (this.profile && !this.profile.relics?.includes(event.key)) {
          this.profile.relics = [...(this.profile.relics || []), event.key];
          this.renderRelics();
        }
        break;
      case "exit_open":
        this.say([[ADA, alerts.exit]]);
        break;
      case "quest_done":
        this.toast(`Задача решена: ${event.title}. Токены: +${event.amount}`);
        break;
      case "loot":
        if (event.amount > 0) this.toast(`Находка! Токены: +${event.amount}`);
        break;
      case "deal":
        this.toast(`Сделка с PGT: «${event.title}»`, "error");
        break;
      default:
    }
  }

  /** The line of code behind an attack, up where the eye already is: over the boss bar. */
  shout(text) {
    const { bossShout } = this.dom;
    bossShout.textContent = text;
    bossShout.hidden = false;
    window.clearTimeout(this.shoutTimer);
    this.shoutTimer = window.setTimeout(() => {
      bossShout.hidden = true;
    }, SHOUT_TIME);
  }

  updateHud(state, selfId) {
    const story = state.story;
    if (!story) return;
    const { dom } = this;
    const broken = (state.terminals || []).find((terminal) => !terminal.solved);
    const quest = state.quest;
    this.partySize = state.players.length;
    let goal = `Идите дальше · комнат осталось: ${story.rooms_left}`;
    if (broken?.role === "gate") goal = "Щит босса: почините терминал в углу зала";
    else if (story.fighting) goal = `Волна ${story.wave} из ${story.waves} · врагов: ${story.enemies}`;
    else if (quest?.trial) goal = `Испытание: работает только ${quest.trial.rune}`;
    else if (quest && !quest.done) goal = "Решите задачу этапа, она слева";
    else if (state.range) goal = "Проверяйте руны на манекенах. Выход: портал у левой стены";
    else if (story.portal_ready) goal = "Портал открыт: соберитесь на нём всей группой";
    else if (broken?.role === "door") goal = "Дверь заперта: почините терминал";
    else if (broken && !story.rooms_left) goal = "Почините терминал, пока баги не задавили вас";
    if (goal !== this.lastGoal) {
      this.lastGoal = goal;
      dom.hudGoal.textContent = goal;
    }
    const boss = story.boss;
    dom.bossBar.hidden = !boss;
    if (boss) {
      dom.bossBar.classList.toggle("shielded", boss.shielded);
      dom.bossName.textContent = boss.shielded ? `${boss.name} · щит` : boss.name;
      dom.bossFill.style.width = `${Math.min(100, (boss.hp / boss.max_hp) * 100)}%`;
    }
    const deploy = boss?.deploy;
    dom.deployBar.hidden = !deploy;
    if (deploy) {
      dom.deployTime.style.width = `${deploy.left * 100}%`;
      dom.deployBreak.style.width = `${deploy.broken * 100}%`;
    }
    if (state.range) {
      dom.rangeDps.textContent = String(Math.round(state.range.dps));
      dom.rangeTotal.textContent = String(state.range.total);
    }
    this.updateFrames(state.players, selfId);
    this.updateQuest(quest);
    this.updateLife(state.life);
    this.updateFolk(state.folk);
    this.updateTerminalPrompt(state, selfId);
    const me = state.players.find((player) => player.id === selfId);
    this.watchTalk(quest, me);
    this.updateCodeCard(me, quest);
    this.updateRoleBar(me);
    this.updateCurses(me);
  }

  /** The stage's problem, top left: what it is, what to do now, how far along. */
  updateQuest(quest) {
    const { dom } = this;
    if (!quest) return;
    const bar = quest.bar;
    const signature = `${quest.text}|${bar ? `${bar.value}:${bar.label}:${bar.warn}` : ""}|${quest.done}`;
    if (signature === this.lastQuest) return;
    const stepChanged = !this.lastQuest.startsWith(quest.text.split(":")[0]);
    this.lastQuest = signature;
    dom.questText.textContent = quest.text;
    dom.quest.classList.toggle("done", Boolean(quest.done));
    if (stepChanged) {
      dom.quest.classList.remove("fresh");
      void dom.quest.offsetWidth;
      dom.quest.classList.add("fresh");
    }
    dom.questBar.hidden = !bar;
    if (bar) {
      dom.questFill.style.width = `${Math.max(0, Math.min(1, bar.value)) * 100}%`;
      dom.questBar.classList.toggle("warn", Boolean(bar.warn));
      dom.questBar.classList.toggle("hot", Boolean(bar.hot));
      dom.questBarLabel.textContent = bar.label;
    }
    window.requestAnimationFrame(() => this.placeIntro());
  }

  folkDone(event) {
    if (this.profile) {
      const known = this.profile.folk || {};
      if (known[event.key] !== "passed") known[event.key] = event.status;
      this.profile.folk = known;
      this.codex.setProfile(this.profile);
    }
    const opened = (this.profile?.cleared ?? 0) >= TEST_OPENS;
    if (event.status === "passed") {
      this.toast(opened ? `${event.test}: PASSED` : `Вы помогли: ${event.name}`);
    } else {
      this.toast(opened ? `${event.test}: SKIPPED` : `За вас всё сделал PGT: ${event.name}`);
    }
  }

  /** Side stories make the quest card taller: whatever sits below must not end up under it. */
  placeIntro() {
    const { intro, quest } = this.dom;
    if (window.innerWidth <= 900 || quest.hidden) {
      intro.style.top = "";
      return;
    }
    intro.style.top = `${quest.offsetTop + quest.offsetHeight + 8}px`;
  }

  /** Side stories in progress, under the stage's own problem. */
  updateFolk(folk) {
    const { folkList } = this.dom;
    const active = folk?.active || [];
    const signature = active.map((entry) => `${entry.name}|${entry.text}|${entry.bar ?? ""}`).join("\n");
    if (signature === this.lastFolk) return;
    this.lastFolk = signature;
    folkList.hidden = !active.length;
    window.requestAnimationFrame(() => this.placeIntro());
    folkList.replaceChildren(
      ...active.map((entry) => {
        const row = element("li", "");
        row.append(element("b", "", entry.name), element("span", "", entry.text));
        if (entry.bar !== undefined) {
          const bar = element("i", "folk-bar");
          const fill = element("i", "");
          fill.style.width = `${Math.round(entry.bar * 100)}%`;
          bar.append(fill);
          row.append(bar);
        }
        return row;
      }),
    );
  }

  /** Trouble in progress and what the party is carrying through this stage. */
  updateLife(life) {
    const { dom } = this;
    const event = life?.event;
    const text = event ? `${EVENT_TEXT[event.kind] || event.kind} · ${Math.ceil(event.left)} с` : "";
    if (text !== this.lastEvent) {
      this.lastEvent = text;
      dom.eventChip.hidden = !text;
      dom.eventChip.textContent = text;
    }
    const finds = (life?.finds || []).join("|");
    if (finds !== this.lastFinds) {
      this.lastFinds = finds;
      dom.finds.replaceChildren(
        ...(life?.finds || []).map((title) => element("span", "quest-find", title)),
      );
    }
  }

  /** Whatever has to be read here, big and sharp: only while you stand in that room. */
  updateCodeCard(me, quest) {
    const { dom } = this;
    const config = this.stageConfig;
    let title = "";
    let code = "";
    if (me && !me.dead && config) {
      const tile = config.tile || 48;
      const inRoom = (index) => {
        const room = config.rooms?.[index];
        return Boolean(room) &&
          me.x >= room.x * tile && me.x <= (room.x + room.w) * tile &&
          me.y >= room.y * tile && me.y <= (room.y + room.h) * tile;
      };
      for (const sign of config.signs || []) {
        if (inRoom(sign.room)) {
          title = sign.title || "Код на стене · встаньте на плиты в этом порядке";
          code = sign.code;
        }
      }
      if (quest?.card && inRoom(quest.card.room)) {
        title = quest.card.title;
        code = quest.card.code;
      }
    }
    const signature = `${title}|${code}`;
    if (signature === this.lastCode) return;
    this.lastCode = signature;
    dom.codeCard.hidden = !code;
    dom.codeCardTitle.textContent = title;
    dom.codeCardBody.textContent = code;
  }

  /** What the boss has done to this mage: without it a silent cast looks like a bug. */
  updateCurses(me) {
    const { curseBar } = this.dom;
    const curses = Object.entries(me?.curses || {});
    const signature = curses.map(([kind, left]) => `${kind}:${Math.ceil(left)}`).join("|");
    if (signature === this.lastCurses) return;
    this.lastCurses = signature;
    curseBar.hidden = !curses.length;
    curseBar.replaceChildren(
      ...curses.map(([kind, left]) => {
        return element("span", "curse-chip", `${CURSE_TEXT[kind] || kind} · ${Math.ceil(left)} с`);
      }),
    );
  }

  /** The two skills at a glance: they live in code, but their cooldowns live here. */
  updateRoleBar(me) {
    const { roleBar } = this.dom;
    const skills = Object.entries(me?.skills || {});
    const signature = skills.map(([name, wait]) => `${name}:${Math.ceil(wait)}`).join("|");
    if (signature === this.lastSkills) return;
    this.lastSkills = signature;
    roleBar.hidden = !skills.length;
    const color = this.roleOf(me?.role)?.color || "";
    roleBar.replaceChildren(
      ...skills.map(([name, wait]) => {
        const chip = element("span", "role-chip", wait > 0 ? `${name} ${Math.ceil(wait)}` : name);
        chip.classList.toggle("ready", wait <= 0);
        chip.style.setProperty("--role-color", color);
        return chip;
      }),
    );
  }

  updateTerminalPrompt(state, selfId) {
    const { prompt } = this.dom;
    const me = state.players.find((player) => player.id === selfId);
    const broken = (state.terminals || []).filter((terminal) => !terminal.solved);
    const distance = (terminal) => Math.hypot(terminal.x - me.x, terminal.y - me.y);
    if (!me || me.dead) {
      this.nearTerminal = null;
      prompt.hidden = true;
      return;
    }
    if (
      !this.leakNoticed &&
      broken.some((terminal) => terminal.role === "portal" && distance(terminal) < LEAK_NOTICE)
    ) {
      this.leakNoticed = true;
      this.say([[ADA, this.campaign.alerts.leak]], true);
    }
    const near = broken.find((terminal) => distance(terminal) <= TERMINAL_REACH);
    const waiting =
      state.story.last_fixer === selfId &&
      state.players.some((player) => player.id !== selfId && !player.dead);
    if (!near) {
      this.nearTerminal = null;
      const use = this.usable(state.quest, me);
      this.nearUse = Boolean(use);
      prompt.hidden = !use || Boolean(this.terminalTask) || this.talkOpen();
      if (use) {
        prompt.textContent = `E — ${use}`;
        prompt.disabled = false;
      }
      return;
    }
    this.nearUse = false;
    const operator = near.operator && near.operator !== selfId
      ? state.players.find((player) => player.id === near.operator)
      : null;
    this.nearTerminal = { busy: Boolean(operator) };
    if (this.terminalTask) return;
    prompt.textContent = operator
      ? `Терминал занят: ${operator.name}`
      : waiting
        ? "E — сейчас очередь другого мага"
        : "E — подключиться к терминалу";
    prompt.disabled = Boolean(operator);
    prompt.hidden = false;
  }

  usable(quest, me) {
    if (!quest || me.linked) return "";
    let best = "";
    let bestDistance = USE_REACH;
    for (const thing of quest.things || []) {
      if (thing.k === "packet" && thing.holder === me.id) return "уронить пакет (друг подхватит)";
      if (!thing.use) continue;
      const distance = Math.hypot(thing.x - me.x, thing.y - me.y);
      if (distance <= bestDistance) {
        best = thing.use;
        bestDistance = distance;
      }
    }
    return best;
  }

  updateFrames(players, selfId) {
    const others = players.filter((player) => player.id !== selfId);
    const signature = others
      .map((player) => `${player.id}:${Math.round(player.hp)}:${Math.round(player.mana)}:${player.dead}:${player.linked}`)
      .join("|");
    if (signature === this.lastFrames) return;
    this.lastFrames = signature;
    this.dom.frames.replaceChildren(
      ...others.map((player) => {
        const frame = element("div", "party-frame");
        frame.classList.toggle("dead", player.dead);
        const name = element(
          "span",
          "party-frame-name",
          player.linked ? `${player.name} · чинит код` : player.name,
        );
        name.style.color = player.color;
        const hp = element("span", "party-frame-bar hp");
        hp.style.setProperty("--fill", `${(player.hp / player.max_hp) * 100}%`);
        const mana = element("span", "party-frame-bar mana");
        mana.style.setProperty("--fill", `${(player.mana / player.max_mana) * 100}%`);
        frame.append(name, hp, mana);
        return frame;
      }),
    );
  }

  introduce(kind) {
    const entry = this.bestiary[kind];
    if (!entry) return;
    const { dom } = this;
    dom.introName.textContent = entry.title;
    dom.introName.style.color = entry.color;
    dom.introHint.textContent = entry.hint;
    dom.intro.hidden = false;
    window.clearTimeout(this.introTimer);
    this.introTimer = window.setTimeout(() => {
      dom.intro.hidden = true;
    }, INTRO_TIME);
  }
}
