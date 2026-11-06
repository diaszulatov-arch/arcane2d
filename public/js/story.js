/* The campaign's screens: headquarters, the radio, terminals and the dungeon HUD. */

import { SpellEditor } from "./editor.js";

const $ = (id) => document.getElementById(id);
const ROMAN = ["I", "II", "III", "IV", "V"];
const INTRO_TIME = 6500;
const COMMS_BASE = 2000;
const COMMS_PER_CHAR = 56;
const COMMS_GAP = 260;
const LOG_LIMIT = 300;
const LOG_STICK = 40;
const SHOUT_TIME = 3000;
const TERMINAL_REACH = 112;
const LEAK_NOTICE = 460;
const HELP_LINES = 4;
const ADA = "Ада";
const BOT = "PGT";
const SPEAKERS = { [ADA]: "ada", [BOT]: "pgt" };
const STAGE_KIND = { door: "ЗАМОК ДВЕРИ", portal: "СЛОМАННЫЙ УЗЕЛ", gate: "ЩИТ БОССА" };
const CURSE_TEXT = {
  syntax: "SyntaxError: заклинания не компилируются",
  null: "None: enemies(), allies() и cursor() пусты",
  mirror: "Автокоррекция: прицел перевёрнут",
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
    dom.ready.addEventListener("click", () => {
      const seat = this.party?.seats.find((entry) => entry.you);
      this.send({ t: "party_ready", ready: !seat?.ready });
    });
    dom.tabs.forEach((tab) => {
      tab.addEventListener("click", () => this.showTab(tab.dataset.tab));
    });
    dom.prompt.addEventListener("click", () => this.openTerminal());
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
    this.renderEssence();
    this.renderTree();
    this.renderMap();
    if (this.party) this.renderRoles();
  }

  setParty(party) {
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
    this.showTab(message.finale || message.chapter_done ? "story" : "lesson");
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
    const won = result.result === "cleared";
    banner.classList.toggle("lost", !won);
    banner.textContent = won
      ? `Этап пройден. Токены: +${result.essence}`
      : `Группа пала. Токены: +${result.essence}. Попробуйте ещё раз.`;
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
    ready.textContent = finished
      ? "Кампания пройдена"
      : you?.ready
        ? "Жду остальных…"
        : alone
          ? "В бой"
          : "Готов";
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
          button.title = stage.title;
          button.disabled = stage.index > limit || !this.party.leader;
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
      parts.push(...dialogue(this.campaign.epilogue));
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
    this.hintsShown = 0;
    this.help = help || { hints: 0, solution: false, theory: false };
    this.onTerminal(true);
    dom.prompt.hidden = true;
    dom.terminalKind.textContent = STAGE_KIND[role] || "ТЕРМИНАЛ";
    dom.terminalTitle.textContent = lesson?.title || "Баг босса";
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
  }

  leaveStage() {
    this.dom.hud.hidden = true;
    this.dom.frames.replaceChildren();
    this.lastFrames = "";
    this.lastSkills = "";
    this.lastCurses = "";
    this.dom.roleBar.hidden = true;
    this.dom.curseBar.hidden = true;
    this.dom.bossShout.hidden = true;
    this.dom.deployBar.hidden = true;
    this.closeTerminal({ notify: false });
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
    const line = this.comms.shift();
    if (!line) {
      commsBox.hidden = true;
      this.commsTimer = null;
      return;
    }
    commsBox.replaceChildren(dialogueLine(line));
    commsBox.hidden = false;
    const time = COMMS_BASE + line[1].length * COMMS_PER_CHAR;
    this.commsTimer = window.setTimeout(() => {
      commsBox.hidden = true;
      this.commsTimer = window.setTimeout(() => this.nextComms(), COMMS_GAP);
    }, time);
  }

  clearComms() {
    window.clearTimeout(this.commsTimer);
    this.commsTimer = null;
    this.comms = [];
    this.dom.commsBox.hidden = true;
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
    this.partySize = state.players.length;
    let goal = `Идите дальше · комнат осталось: ${story.rooms_left}`;
    if (broken?.role === "gate") goal = "Щит босса: почините терминал в углу зала";
    else if (story.fighting) goal = `Волна ${story.wave} из ${story.waves} · врагов: ${story.enemies}`;
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
    this.updateFrames(state.players, selfId);
    this.updateTerminalPrompt(state, selfId);
    const me = state.players.find((player) => player.id === selfId);
    this.updateRoleBar(me);
    this.updateCurses(me);
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
      prompt.hidden = true;
      return;
    }
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
