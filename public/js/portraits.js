/* Faces for whoever is talking: pixel busts on a 32x32 grid, scaled up by CSS.
 * They blink, look about and move their mouths while the words are coming. */

export const PORTRAIT_GRID = 32;

const BLINK_EVERY = 3200;
const BLINK_TIME = 130;
const MOUTH_TIME = 95;

const SKIN = "#f0c9a0";
const SKIN_SHADE = "#c99a74";
const INK = "#14161c";
const WHITE = "#f4f8ff";
const GREEN = "#4fe08a";
const RED = "#ff5a4f";
const GOLD = "#ffd27a";

function eyes(p, s, a = 11, b = 18, y = 13, white = WHITE, pupil = INK) {
  if (s.blink) {
    p(a, y + 1, 3, 1, pupil);
    p(b, y + 1, 3, 1, pupil);
    return;
  }
  p(a, y, 3, 2, white);
  p(b, y, 3, 2, white);
  p(a + 1 + s.look, y, 1, 2, pupil);
  p(b + 1 + s.look, y, 1, 2, pupil);
}

function mouth(p, s, x = 13, y = 19, w = 6, color = "#5a2018", lip = "#6a3424") {
  if (s.open) {
    p(x, y, w, 3, color);
    p(x + 1, y, w - 2, 1, WHITE);
  } else {
    p(x, y + 1, w, 1, lip);
  }
}

function head(p, s, { skin = SKIN, shade = SKIN_SHADE, shirt = "#3a4050", brow = INK } = {}) {
  p(3, 27, 26, 5, shirt);
  p(6, 25, 20, 2, shirt);
  p(13, 22, 6, 4, shade);
  p(9, 8, 14, 15, skin);
  p(10, 6, 12, 2, skin);
  p(10, 23, 12, 1, skin);
  p(8, 13, 1, 4, shade);
  p(23, 13, 1, 4, shade);
  eyes(p, s);
  p(11, 11, 3, 1, brow);
  p(18, 11, 3, 1, brow);
  p(15, 15, 2, 3, shade);
}

function glasses(p, color = INK) {
  for (const x of [10, 17]) {
    p(x, 12, 5, 1, color);
    p(x, 15, 5, 1, color);
    p(x, 12, 1, 4, color);
    p(x + 4, 12, 1, 4, color);
  }
  p(15, 13, 2, 1, color);
}

const PORTRAITS = {
  /* ---- people from the campaign ---- */
  ada: {
    bg: "#123a3a",
    glitch: 0.015,
    voice: 392,
    soft: true,
    draw(p, s) {
      head(p, s, { shirt: "#1f4a5a", brow: "#123a3a", skin: "#d8f0e8", shade: "#9ec8c0" });
      p(8, 4, 16, 5, "#1f8a8a");
      p(8, 9, 3, 10, "#1f8a8a");
      p(21, 9, 3, 10, "#1f8a8a");
      p(8, 3, 16, 1, INK);
      p(6, 12, 2, 7, INK);
      p(24, 12, 2, 7, INK);
      p(24, 19, 1, 3, INK);
      p(20, 21, 5, 1, INK);
      mouth(p, s);
    },
  },
  pgt: {
    bg: "#3a0a14",
    glitch: 0.09,
    voice: 240,
    draw(p, s) {
      p(4, 4, 24, 20, "#22242c");
      p(6, 6, 20, 16, "#0a0408");
      const lit = s.blink ? "#801a24" : RED;
      p(10, 9, 3, 5, lit);
      p(19, 9, 3, 5, lit);
      p(9, 17, 2, 1, RED);
      p(21, 17, 2, 1, RED);
      p(11, 18, 10, s.open ? 2 : 1, RED);
      p(12, 25, 8, 2, "#22242c");
      p(7, 27, 18, 3, "#22242c");
    },
  },
  valera: {
    bg: "#3a2a12",
    voice: 300,
    draw(p, s) {
      head(p, s, { shirt: "#6a6e78", brow: "#2a2018" });
      p(9, 5, 14, 3, "#2a2018");
      p(9, 8, 2, 3, "#2a2018");
      p(21, 8, 2, 3, "#2a2018");
      p(10, 18, 12, 5, "#4a3a2a");
      mouth(p, s);
      p(24, 22, 6, 7, WHITE);
      p(30, 24, 1, 3, WHITE);
    },
  },
  queen: {
    bg: "#14102a",
    glitch: 0.05,
    voice: 340,
    draw(p, s) {
      head(p, s, { shirt: "#2a1f4a", skin: "#b8b4d4", shade: "#8a86a8", brow: "#2a1f4a" });
      p(9, 2, 14, 4, GOLD);
      p(9, 0, 2, 2, GOLD);
      p(15, 0, 2, 2, GOLD);
      p(21, 0, 2, 2, GOLD);
      p(10, 13, 4, 2, INK);
      p(18, 13, 4, 2, INK);
      mouth(p, s, 13, 19, 6, "#0a0a14", "#2a1f4a");
    },
  },
  request: {
    bg: "#123a5a",
    voice: 640,
    draw(p, s) {
      p(7, 3, 18, 27, WHITE);
      p(7, 3, 18, 2, "#7fe0ee");
      p(7, 16, 18, 2, "#4f8fff");
      eyes(p, s, 10, 18, 9);
      mouth(p, s, 13, 12, 6, INK, INK);
      p(10, 22, 12, 1, "#a8b0c4");
      p(10, 25, 8, 1, "#a8b0c4");
    },
  },
  note: {
    bg: "#2a2410",
    voice: 560,
    draw(p) {
      p(6, 4, 20, 24, "#efe6c8");
      for (let row = 0; row < 5; row += 1) p(9, 8 + row * 4, row % 2 ? 11 : 14, 1, "#5a5240");
    },
  },
  /* ---- side stories: people ---- */
  webmaster: {
    bg: "#10305a",
    voice: 420,
    draw(p, s) {
      head(p, s, { shirt: "#b89a5a", brow: "#3a2a1a" });
      p(9, 5, 14, 3, "#3a2a1a");
      p(9, 8, 4, 2, "#3a2a1a");
      glasses(p);
      mouth(p, s);
      p(14, 25, 4, 2, WHITE);
    },
  },
  gosha: {
    bg: "#123a24",
    voice: 620,
    draw(p, s) {
      head(p, s, { shirt: "#3aa86a", brow: "#c98a3a" });
      p(9, 5, 14, 3, "#c98a3a");
      p(9, 3, 2, 2, "#c98a3a");
      p(13, 2, 2, 3, "#c98a3a");
      p(17, 3, 2, 2, "#c98a3a");
      p(21, 4, 2, 2, "#c98a3a");
      p(6, 22, 6, 4, "#2f8a56");
      p(20, 22, 6, 4, "#2f8a56");
      p(13, 26, 1, 4, WHITE);
      p(18, 26, 1, 4, WHITE);
      mouth(p, s);
    },
  },
  senya: {
    bg: "#4a1040",
    voice: 680,
    draw(p, s) {
      head(p, s, { shirt: "#7f5fff", brow: "#3a2a1a" });
      p(8, 4, 16, 5, "#ff6ec7");
      p(6, 8, 18, 2, "#c83e98");
      mouth(p, s);
      p(25, 16, 3, 3, "#c8ccd4");
      p(26, 19, 1, 9, INK);
    },
  },
  petrovich: {
    bg: "#16224a",
    voice: 280,
    draw(p, s) {
      head(p, s, { shirt: "#3a4a6a", brow: "#c8ccd4" });
      p(9, 5, 14, 3, "#c8ccd4");
      p(9, 17, 14, 6, "#c8ccd4");
      p(10, 23, 12, 2, "#c8ccd4");
      mouth(p, s, 13, 18, 6);
      p(26, 12, 2, 16, "#6a5a4a");
      p(23, 7, 8, 6, "#5a606e");
    },
  },
  babka: {
    bg: "#4a1024",
    voice: 520,
    draw(p, s) {
      head(p, s, { shirt: "#a05ac0", brow: "#8a7a6a" });
      p(7, 4, 18, 6, "#d04a6a");
      p(7, 10, 3, 11, "#d04a6a");
      p(22, 10, 3, 11, "#d04a6a");
      p(10, 23, 12, 3, "#d04a6a");
      p(15, 25, 3, 3, "#a03050");
      p(10, 5, 2, 2, GOLD);
      p(19, 7, 2, 2, GOLD);
      p(10, 17, 2, 1, SKIN_SHADE);
      p(20, 17, 2, 1, SKIN_SHADE);
      mouth(p, s);
    },
  },
  luba: {
    bg: "#123a5a",
    voice: 460,
    draw(p, s) {
      head(p, s, { shirt: "#5a9ad0", brow: "#5a4a3a" });
      p(8, 5, 16, 4, WHITE);
      p(8, 9, 2, 3, WHITE);
      p(22, 9, 2, 3, WHITE);
      p(11, 10, 3, 1, "#5a4a3a");
      p(18, 10, 3, 1, "#5a4a3a");
      mouth(p, s);
      p(27, 4, 2, 26, "#8a6a3a");
    },
  },
  maria: {
    bg: "#2a1f3a",
    voice: 500,
    draw(p, s) {
      head(p, s, { shirt: "#8a7a9a", brow: "#b8bcc4", skin: "#f0d4b8" });
      p(12, 1, 8, 4, "#d8dce4");
      p(9, 5, 14, 4, "#d8dce4");
      p(8, 8, 2, 8, "#d8dce4");
      p(22, 8, 2, 8, "#d8dce4");
      glasses(p, "#8a7a6a");
      p(10, 18, 2, 1, SKIN_SHADE);
      p(20, 18, 2, 1, SKIN_SHADE);
      mouth(p, s);
      p(14, 26, 4, 3, "#a898b8");
    },
  },
  guard: {
    bg: "#101c3a",
    voice: 260,
    draw(p, s) {
      head(p, s, { shirt: "#2a3a5a", brow: "#3a2a1a" });
      p(7, 3, 18, 6, "#2a3a5a");
      p(6, 9, 20, 2, INK);
      p(14, 4, 4, 3, GOLD);
      mouth(p, s, 13, 19, 6);
      p(10, 17, 12, 2, "#3a2a1a");
      p(8, 28, 4, 2, GOLD);
    },
  },
  miner: {
    bg: "#3a2a10",
    voice: 250,
    draw(p, s) {
      head(p, s, { shirt: "#7a5a3a", brow: "#e8e8e8" });
      p(7, 4, 18, 5, "#ffd93d");
      p(6, 9, 20, 1, "#c9a820");
      p(13, 1, 6, 3, "#fff6b0");
      p(9, 17, 14, 6, "#e8e8e8");
      p(10, 23, 12, 2, "#e8e8e8");
      mouth(p, s, 13, 18, 6);
    },
  },
  /* ---- side stories: everything else ---- */
  calc: {
    bg: "#2a2a18",
    voice: 380,
    draw(p, s) {
      p(6, 2, 20, 29, "#c8bfa4");
      p(8, 4, 16, 10, "#1e2a1e");
      const lcd = "#8fe388";
      if (s.blink) {
        p(11, 7, 3, 1, lcd);
        p(18, 7, 3, 1, lcd);
      } else {
        p(11, 6, 3, 3, lcd);
        p(18, 6, 3, 3, lcd);
      }
      p(13, 11, 6, s.open ? 2 : 1, lcd);
      for (let row = 0; row < 3; row += 1) {
        for (let col = 0; col < 3; col += 1) {
          const missing = row === 0 && col === 2;
          p(9 + col * 5, 17 + row * 5, 4, 3, missing ? "#3a2420" : "#6a6658");
        }
      }
    },
  },
  modem: {
    bg: "#1a2a2a",
    voice: 700,
    draw(p, s) {
      p(3, 12, 26, 14, "#c8c4b4");
      p(3, 23, 26, 3, "#8a8678");
      eyes(p, s, 9, 20, 15);
      p(13, 19, 6, s.open ? 3 : 1, INK);
      for (let led = 0; led < 5; led += 1) {
        p(6 + led * 5, 24, 3, 1, Math.sin(s.t / 90 + led) > 0 ? GREEN : "#1f5a3a");
      }
      p(24, 4, 2, 8, INK);
      p(18, 3, 8, 2, INK);
    },
  },
  troll: {
    bg: "#14300f",
    voice: 330,
    draw(p, s) {
      const green = "#5a9a4a";
      p(6, 6, 20, 24, green);
      p(2, 9, 4, 6, green);
      p(26, 9, 4, 6, green);
      p(10, 10, 4, 1, "#2a5a1f");
      p(18, 10, 4, 1, "#2a5a1f");
      eyes(p, s, 10, 19, 12);
      p(8, 19, 16, s.open ? 8 : 5, INK);
      for (let tooth = 0; tooth < 5; tooth += 1) p(9 + tooth * 3, 19, 2, 3, WHITE);
      if (s.open) {
        for (let tooth = 0; tooth < 4; tooth += 1) p(10 + tooth * 3, 25, 2, 2, WHITE);
      }
    },
  },
  cat: {
    bg: "#4a2a10",
    voice: 820,
    draw(p, s) {
      const fur = "#e8903a";
      p(7, 10, 18, 16, fur);
      p(5, 26, 22, 6, fur);
      p(7, 5, 4, 5, fur);
      p(21, 5, 4, 5, fur);
      p(8, 7, 2, 3, "#ffb6c8");
      p(22, 7, 2, 3, "#ffb6c8");
      p(14, 10, 1, 4, "#b0601a");
      p(17, 10, 1, 4, "#b0601a");
      if (s.blink) {
        p(10, 15, 4, 1, INK);
        p(18, 15, 4, 1, INK);
      } else {
        p(10, 14, 4, 3, "#a8e870");
        p(18, 14, 4, 3, "#a8e870");
        p(11 + s.look, 14, 1, 3, INK);
        p(19 + s.look, 14, 1, 3, INK);
      }
      p(15, 19, 2, 1, "#ff8aa8");
      p(13, 21, 6, s.open ? 2 : 1, "#7a3a14");
      p(2, 19, 5, 1, WHITE);
      p(25, 19, 5, 1, WHITE);
    },
  },
  rec: {
    bg: "#3a1020",
    voice: 360,
    draw(p, s) {
      p(6, 5, 20, 22, "#3a4050");
      p(15, 1, 2, 4, "#6a7080");
      p(14, 0, 4, 2, RED);
      p(8, 8, 16, 10, INK);
      p(14 + Math.round(Math.sin(s.t / 700) * 5), 11, 4, 4, s.blink ? "#5a1a24" : "#ff4f6a");
      for (let bar = 0; bar < 4; bar += 1) p(9 + bar * 4, 21, 2, s.open ? 4 : 2, "#a8b0c4");
      p(3, 28, 26, 4, "#3a4050");
    },
  },
  diplom: {
    bg: "#10245a",
    voice: 540,
    draw(p, s) {
      p(7, 2, 18, 28, WHITE);
      p(20, 2, 5, 5, "#c8d4e4");
      p(10, 5, 8, 2, "#3a6ab0");
      eyes(p, s, 10, 18, 11);
      p(10, 9, 4, 1, "#8a94a8");
      p(18, 9, 4, 1, "#8a94a8");
      mouth(p, s, 13, 15, 6, INK, INK);
      for (let row = 0; row < 3; row += 1) p(10, 21 + row * 3, row === 2 ? 8 : 12, 1, "#a8b0c4");
    },
  },
  asya: {
    bg: "#0f3020",
    voice: 760,
    draw(p, s) {
      const petals = [[12, 2], [20, 5], [23, 13], [19, 21], [11, 22], [4, 17], [3, 8]];
      petals.forEach(([x, y], index) => p(x, y, 7, 7, index === 0 ? RED : GREEN));
      p(8, 7, 16, 16, "#ffd93d");
      eyes(p, s, 10, 18, 12);
      mouth(p, s, 13, 17, 6, "#7a5a10", "#7a5a10");
      p(15, 28, 2, 4, "#2a8a3a");
    },
  },
  bin: {
    bg: "#20242c",
    voice: 310,
    draw(p, s) {
      p(6, 11, 20, 20, "#6a7080");
      p(3, 5, 26, 5, "#8a92a4");
      p(12, 2, 8, 3, "#8a92a4");
      eyes(p, s, 10, 18, 13);
      p(9, 12, 5, 1, "#3a4050");
      p(18, 12, 5, 1, "#3a4050");
      mouth(p, s, 12, 18, 8, INK, INK);
      for (let rib = 0; rib < 3; rib += 1) p(10 + rib * 5, 24, 2, 6, "#3a4050");
    },
  },
  sync: {
    bg: "#10305a",
    voice: 600,
    draw(p, s) {
      p(5, 13, 22, 12, "#d6f6fb");
      p(8, 9, 8, 6, "#d6f6fb");
      p(14, 6, 10, 9, "#d6f6fb");
      p(2, 16, 4, 7, "#d6f6fb");
      p(26, 15, 4, 8, "#d6f6fb");
      eyes(p, s, 10, 18, 14, WHITE, "#3a6ab0");
      mouth(p, s, 13, 19, 6, "#3a6ab0", "#3a6ab0");
      const spin = Math.floor(s.t / 220) % 4;
      p(3 + spin * 7, 28, 5, 2, "#3aa7ff");
    },
  },
  cron: {
    bg: "#2a1c10",
    voice: 270,
    draw(p, s) {
      p(8, 1, 16, 30, "#6a5a4a");
      p(6, 1, 20, 3, "#3a3026");
      p(10, 6, 12, 14, "#e8e0c8");
      eyes(p, s, 11, 18, 10);
      p(12, 15, 8, s.open ? 3 : 1, "#3a3026");
      p(15, 23, 2, 5, GOLD);
      p(14, 27, 4, 3, GOLD);
    },
  },
  printer: {
    bg: "#2a2418",
    voice: 230,
    draw(p, s) {
      p(3, 12, 26, 14, "#c8c4b4");
      p(3, 24, 26, 3, "#8a8678");
      p(8, 3, 16, 9, WHITE);
      p(6, 15, 11, 5, INK);
      p(7, 16, 9, 1, RED);
      p(7, 18, 6, 1, RED);
      p(22, 15, 3, 3, Math.sin(s.t / 120) > 0 ? RED : "#5a1a18");
      p(9, 27, 14, s.open ? 5 : 2, WHITE);
    },
  },
  ac: {
    bg: "#10304a",
    voice: 290,
    draw(p, s) {
      p(3, 7, 26, 15, "#e4e8f0");
      eyes(p, s, 8, 21, 11, "#c0e8f4");
      p(7, 9, 5, 1, INK);
      p(20, 9, 5, 1, INK);
      p(13, 14, 6, s.open ? 3 : 1, INK);
      for (let vent = 0; vent < 2; vent += 1) p(5, 18 + vent * 2, 22, 1, "#b0b6c4");
      for (let flake = 0; flake < 4; flake += 1) p(6 + flake * 6, 24 + ((s.t / 60 + flake * 3) % 7), 2, 2, "#7fe0ee");
    },
  },
  sensor: {
    bg: "#3a1414",
    voice: 660,
    draw(p, s) {
      p(11, 2, 10, 22, "#e4e8f0");
      p(9, 22, 14, 9, RED);
      p(15, 12, 2, 12, RED);
      eyes(p, s, 11, 18, 6);
      p(13, 10, 6, s.open ? 2 : 1, INK);
    },
  },
  ghost: {
    bg: "#20103a",
    glitch: 0.12,
    voice: 450,
    draw(p, s) {
      const violet = "#c86bff";
      p(8, 5, 16, 20, violet);
      p(10, 3, 12, 2, violet);
      p(6, 25, 20, 7, violet);
      p(10, 11, 4, 6, s.blink ? violet : WHITE);
      p(18, 11, 4, 6, s.blink ? violet : WHITE);
      p(13, 20, 6, s.open ? 3 : 1, "#3a1a5a");
    },
  },
  /* ---- the regulars ---- */
  atm: {
    bg: "#123024",
    voice: 720,
    draw(p, s) {
      p(5, 2, 22, 29, "#5a6070");
      p(8, 5, 16, 11, "#123a2a");
      eyes(p, s, 10, 18, 7, GREEN, "#123a2a");
      p(12, 12, 8, s.open ? 3 : 1, GREEN);
      for (let row = 0; row < 3; row += 1) {
        for (let col = 0; col < 3; col += 1) p(8 + col * 4, 19 + row * 4, 3, 3, "#c8c4b4");
      }
      p(21, 20, 3, 9, INK);
    },
  },
  fridge: {
    bg: "#143044",
    voice: 330,
    draw(p, s) {
      p(6, 1, 20, 30, "#e4e8f0");
      p(6, 19, 20, 1, "#b0b6c4");
      p(22, 4, 2, 12, "#b0b6c4");
      eyes(p, s, 9, 16, 7);
      p(8, 5, 5, 1, INK);
      p(15, 6, 5, 1, INK);
      p(10, 13, 8, s.open ? 3 : 1, INK);
      p(22, 22, 2, 7, "#b0b6c4");
    },
  },
  clip: {
    bg: "#20242c",
    voice: 640,
    draw(p, s) {
      const steel = "#c0c8d8";
      p(8, 3, 2, 26, steel);
      p(8, 2, 16, 2, steel);
      p(22, 3, 2, 22, steel);
      p(12, 24, 12, 2, steel);
      p(12, 8, 2, 16, steel);
      p(12, 7, 8, 2, steel);
      p(18, 8, 2, 12, steel);
      p(4, 9, 8, 7, WHITE);
      p(16, 9, 8, 7, WHITE);
      if (s.blink) {
        p(4, 12, 8, 1, INK);
        p(16, 12, 8, 1, INK);
      } else {
        p(7 + s.look, 11, 3, 4, INK);
        p(19 + s.look, 11, 3, 4, INK);
      }
      p(10, 19, 8, s.open ? 3 : 1, INK);
    },
  },
  vendor: {
    bg: "#2a1a3a",
    voice: 300,
    draw(p, s) {
      p(6, 4, 20, 28, "#23202a");
      p(9, 2, 14, 3, "#23202a");
      p(9, 10, 14, 10, "#0a0a10");
      const lit = s.blink ? "#7a5a20" : GOLD;
      p(11, 13, 3, 2, lit);
      p(18, 13, 3, 2, lit);
      p(13, 17, 6, s.open ? 2 : 1, "#3a3040");
      p(4, 26, 6, 6, "#7fe0ee");
      p(22, 26, 6, 6, "#ff9ec7");
    },
  },
  /* Everyone else on the radio is a service, and a service is a terminal with a name. */
  machine: {
    bg: "#0f2a1c",
    voice: 340,
    draw(p, s, ctx, tag) {
      p(3, 3, 26, 21, "#3a4050");
      p(5, 5, 22, 17, "#07140d");
      p(12, 24, 8, 3, "#3a4050");
      p(7, 27, 18, 3, "#3a4050");
      ctx.fillStyle = GREEN;
      ctx.font = "bold 8px monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(tag || "?", 16, 12);
      p(7, 19, s.open ? 12 : 6, 1, GREEN);
    },
  },
};

export function hasPortrait(key) {
  return Object.hasOwn(PORTRAITS, key);
}

export function voiceOf(key) {
  return (PORTRAITS[key] || PORTRAITS.machine).voice;
}

export function hasSoftVoice(key) {
  return Boolean(PORTRAITS[key]?.soft);
}

/** One frame of someone's face. `talking` moves the mouth; everything else just lives. */
export function paintPortrait(ctx, key, { talking = false, now = 0, tag = "", seed = 0 } = {}) {
  const entry = PORTRAITS[key] || PORTRAITS.machine;
  const state = {
    t: now,
    open: talking && Math.floor(now / MOUTH_TIME) % 2 === 0,
    blink: (now + seed * 700) % BLINK_EVERY < BLINK_TIME,
    look: Math.floor((now + seed * 400) / 1900) % 3 === 0 ? -1 : 0,
  };
  const pixel = (x, y, w, h, color) => {
    ctx.fillStyle = color;
    ctx.fillRect(Math.round(x), Math.round(y), w, h);
  };
  ctx.fillStyle = entry.bg;
  ctx.fillRect(0, 0, PORTRAIT_GRID, PORTRAIT_GRID);
  ctx.fillStyle = "rgba(255, 255, 255, 0.06)";
  for (let band = 0; band < PORTRAIT_GRID; band += 8) ctx.fillRect(0, band, PORTRAIT_GRID, 4);
  entry.draw(pixel, state, ctx, tag);
  if (entry.glitch && Math.random() < entry.glitch) {
    const row = Math.floor(Math.random() * (PORTRAIT_GRID - 4));
    ctx.drawImage(ctx.canvas, 0, row, PORTRAIT_GRID, 3, Math.random() < 0.5 ? -2 : 2, row, PORTRAIT_GRID, 3);
  }
}
