/* The second half of the bestiary, drawn the same way as the first: each row is the left
 * half of a creature, ending at its spine, and the other half is its mirror image. */

export const FOE_SPRITES = {
  // ------------------------------------------------------------ I. Старый Веб
  marquee: {
    colors: { k: "#1a1208", y: "#ffe066", o: "#d9a030" },
    art: ["kkkkkk", "kyyyyy", "kyyyyy", "kyyyyy", "kyyyyy", "kyyyyy", "kyyyyy", "kyyyyy", "kooooo", "kkkkkk"],
  },
  visits: {
    colors: { w: "#c8d0c8", k: "#0c120c", g: "#7fe08a", d: "#2c5a34", s: "#7a8278" },
    art: ["wwwwwwwww", "wkkkkkkkk", "wkggkggkg", "wkdgkdgkg", "wkggkggkg", "wkgdkgdkd", "wkggkggkg", "wkkkkkkkk", "wwwwwwwww", "....sss", "..sssss"],
  },
  construction: {
    colors: { y: "#ffc23d", k: "#1a1208", o: "#d98a1a", w: "#f4f4fa" },
    art: ["......yy", ".....yyy", ".....ykk", "....yykk", "....yykk", "...yyykk", "...yyyyy", "..yyyykk", "..yyyyyy", ".kkyykky", ".yykkyyk", "kkyykkyy", "ww....ww"],
  },
  deadlock: {
    colors: { g: "#d8d8e0", s: "#8a8a98", b: "#c98a5a", d: "#8a5a34", k: "#1a1208" },
    art: ["....gggg", "...ggggg", "...gg...", "...gs...", "...gs...", ".bbbbbbb", "bbbbbbbb", "bbbbbbkk", "bbbbbbkk", "bbbbbbbk", "dbbbbbbk", "dddddddd"],
  },
  sqlinject: {
    colors: { c: "#7fb4ff", b: "#3f6fc8", w: "#ffffff", k: "#12203a", r: "#ff5a4f" },
    art: [".....kkk", ".....kww", "...kkkkk", "....kccc", "....kcww", "....kcww", "....kccc", "....kbbb", "....kbbb", ".....kkk", "......rr", ".......r"],
  },
  necroposter: {
    colors: { p: "#6a4f98", d: "#3f2c5c", s: "#d8c8f0", k: "#120a1c", g: "#b0ff8a" },
    art: ["....pppp", "...ppppp", "..pppddd", "..ppdsss", "..ppskgs", "..ppssss", "..pppsks", "..pppdss", ".ppppppp", ".pppddpp", "ppppddpp", "pppddddd", "d.d.d.dd"],
  },
  capslock: {
    colors: { r: "#ff7a5a", d: "#b83f2c", w: "#ffffff", k: "#2a0c08" },
    art: ["rrrrrrrrr", "rwwwwwwww", "rwkkkkkkw", "rwkwwwwkw", "rwkkkkkkw", "rwkwwwwkw", "rwkwwwwkw", "rwwwwwwww", "ddddddddd", "..dd..dd."],
  },
  semicolon: {
    colors: { c: "#9fc8ff", d: "#5f88c8", k: "#0c1428" },
    art: ["...ccc", "..cccc", "..cckc", "..cccc", "...ccc", "......", "...ccc", "..cccc", "..ccck", "...ccc", "....dc", "...dd."],
  },
  comma: {
    colors: { c: "#9fc8ff", d: "#5f88c8", k: "#0c1428" },
    art: ["..cc", ".ccc", ".cck", ".ccc", "..dc", ".dd."],
  },
  quotemark: {
    colors: { o: "#ce9178", d: "#8a5a44", k: "#201008", y: "#ffd27a" },
    art: ["..oooo..", ".oooooo.", ".ookkoo.", ".ooyooo.", ".oooooo.", "..oooo..", "...ooo..", "....oo..", "....dd..", "...dd...", "..dd...."],
  },
  vim: {
    colors: { g: "#6fe08a", d: "#2f8a4f", k: "#08200f", w: "#ffffff" },
    art: ["ggggg..ggg", "gdddgg.gdd", ".gdddg.gdd", ".gdddggggd", "..gdddggdd", "..gdddgddd", "...gdddddd", "...gddddww", "....gddddk", "....gddddd", ".....gdddd", ".....gggdd", "......gggg"],
  },
  emacs: {
    colors: { p: "#b58cff", d: "#6a3fc8", k: "#120a2a", w: "#ffffff" },
    art: ["...ppppppp", "..pppddddd", ".ppddddddd", ".pddddddww", "pddwwwwwkk", "pddwwwwwww", "pdddddddww", ".pdddwwwww", ".pddwwkkkk", "..pddwwwww", "...pdddddd", "....pppppp"],
  },
  eof: {
    colors: { r: "#ff6a7a", d: "#a82f44", k: "#14060a", w: "#ffd0d6" },
    art: ["kkkkkkkkkk", "krrrrrrrrr", "krdddddddd", "krdrrrrrrd", "krdrrkkkkd", "krdrrrrrdd", "krdrrkkkkd", "krdrrrrrrd", "krdddddddd", "krrrrrrrrr", "kkkkkkkkkk", "..kk..kk.."],
  },
  // ------------------------------------------------------ II. Бесконечная Лента
  autoplay: {
    colors: { k: "#14141c", s: "#3a3a48", r: "#ff5a5a", w: "#ffffff" },
    art: ["sssssssss", "skkkkkkkk", "skkkkkkrr", "skkkkkrrr", "skkkkrrww", "skkkkrrww", "skkkkkrrr", "skkkkkkrr", "skkkkkkkk", "sssssssss", "skrrrrrss", "sssssssss"],
  },
  shorts: {
    colors: { p: "#ff5ab0", d: "#b82f7a", k: "#1a0a14", w: "#ffffff" },
    art: ["....pppp", "...ppppp", "...ppddd", "...pdddd", "...pdkkw", "...pdkww", "...pdkww", "...pdkkw", "...pdddd", "...ppddd", "...ppppp", "....pppp", "...dd.dd"],
  },
  dushnila: {
    colors: { s: "#e8c8a0", h: "#6a5a44", g: "#a8b06a", d: "#6a7040", k: "#14100a", w: "#f4f4e8" },
    art: ["...hhhhh", "..hhhhhh", "..hsssss", "..wwwkww", "..wwkwkw", "..hwwwww", "...sssss", "...sskkk", "..dgggww", ".ggggggw", ".ggdgggw", ".ggggggg", "..d...dd"],
  },
  firstcomment: {
    colors: { y: "#ffe07a", o: "#d9a030", k: "#1a1208" },
    art: ["..yyyy", ".yyyyy", "yyyyyk", "yyyyyk", "yyyyyk", "yyyyyk", ".yyyyy", "..oyyk", "...oyy", "...ooo"],
  },
  alsolike: {
    colors: { p: "#ff8ac8", d: "#c84f8a", w: "#ffffff", k: "#2a0a1c" },
    art: ["..ppp...", ".ppppp.p", "ppwppppp", "pppppppp", "ppkkpppp", "ppkkpppp", "pppppppk", ".pppppkk", "..ppppkk", "...ppppp", "....ppdd", ".....ddd", "......dd"],
  },
  bubble: {
    colors: { c: "#8fc8ff", d: "#4f7fc8", w: "#ffffff", k: "#0c1a30" },
    art: ["....cccc", "..cccccc", ".ccwwccc", ".cwwcccc", "cccccccc", "cccckkcc", "cccckwcc", "cccccccc", "cccccckk", ".ccccccc", ".ddccccc", "..dddddd", "....dddd"],
  },
  readmore: {
    colors: { w: "#f0ecff", g: "#c8b6ff", k: "#1a1430", d: "#8a78c8" },
    art: ["wwwwwwww", "wkkkkkkk", "wwwwwwww", "wkkkkkkk", "wwwwwwww", "wkkkkkww", "wwwwwwww", "gggggggg", "gkgkgkgk", "dddddddd"],
  },
  whiletrue: {
    colors: { p: "#a78bff", d: "#5f3fc8", y: "#ffe07a", k: "#120a2a" },
    art: ["....pppp", "..pppppp", ".pppddpp", ".ppd...p", "ppd....d", "ppd..kkk", "ppd..kyy", "ppd..kkk", "ppd....d", ".ppd...p", ".pppddpp", "..pppppp", "....pppp"],
  },
  hype: {
    colors: { p: "#ff6b9e", d: "#c23d78", y: "#ffe07a", k: "#2a0a1c", w: "#ffffff" },
    art: ["...y...y", "....y.yy", "..yyyyyy", ".ppppppp", "ppppwwpp", "pppwkkpp", "pppwkkpp", "pppppppp", "ppppkkkk", "pppkwwww", ".pppkkkk", "..dppppp", "...ddddd"],
  },
  spinner: {
    colors: { c: "#7fd4ff", d: "#3f8ac8", m: "#2c4a6a", k: "#0a1420" },
    art: ["....cccc", "..cccccc", ".ccc.mmm", ".cc..mmm", "cc....mm", "cc......", "dd......", "dd....mm", ".dd..mmm", ".ddd.mmm", "..dddmmm", "....mmmm"],
  },
  bell: {
    colors: { y: "#ffd24a", o: "#c88a1a", r: "#ff5a4f", w: "#ffffff", k: "#1a1208" },
    art: [".......y", "......yy", ".....yyy", "....yyyy", "...yyyyy", "...yyyyy", "...yyyyy", "..yyyyyy", "..yyyyyy", ".yyyyyyy", "oooooooo", "......kk", ".......k"],
  },
  // ---------------------------------------------------------------- III. Облако
  noext: {
    colors: { w: "#e8ecf4", g: "#b8c4d8", d: "#6a7890", k: "#1a2030" },
    art: ["wwwwwgg", "wwwwwwg", "wwwwwww", "wwkkkkw", "wkkwwkk", "wwwwwkk", "wwwwkkw", "wwwwkww", "wwwwwww", "wwwwkww", "wwwwwww", "gggdddd"],
  },
  zipbomb: {
    colors: { o: "#ffb45c", d: "#c8772f", k: "#1a1208", r: "#ff4f4f", y: "#ffe07a" },
    art: [".....ry", "......k", ".....kk", "..kkkkk", ".kooooo", "koooo.o", "koooodo", "kooookk", "kooooko", ".kdoooo", "..kkkkk"],
  },
  deletedfile: {
    colors: { w: "#c8d0e0", g: "#9aa8c0", r: "#ff5a6a", k: "#202838" },
    art: ["wwwwwgg", "wwwwwwg", "wwwwwww", "wrwwwww", "wwrwwww", "wwwrwww", "wwwwrww", "wwwwwrw", "wwwwwwr", "wwwwwww", "ggggggg"],
  },
  container: {
    colors: { b: "#4f9fe0", d: "#2f6fa8", l: "#8fc8ff", k: "#0c1a2a", w: "#ffffff" },
    art: ["llllllllll", "bbbbbbbbbb", "bdbdbdbdbd", "bdbdbdbdbd", "bdbdbdkkkk", "bdbdbdkwwk", "bdbdbdkwwk", "bdbdbdkkkk", "bdbdbdbdbd", "bbbbbbbbbb", "dddddddddd", "kk......kk"],
  },
  conflict: {
    colors: { r: "#ff8a7a", d: "#c84f44", w: "#ffffff", k: "#2a0c08" },
    art: ["rrrrrrrr", "rkkwkkwk", "rrrrrrrr", "rwwwwwww", "rwkkwkkw", "rwwwwwww", "dddddddd", "rwwwwwww", "rkwwkkww", "rwwwwwww", "rrrrrrrr", "..dd..dd"],
  },
  lag: {
    colors: { g: "#7fffd0", d: "#2fb88a", k: "#082018", w: "#ffffff" },
    art: ["gg.gg.gg", "gggggggg", "g.gkkggg", "ggggwkgg", "gggggggg", "..gggggg", "ggkkkk..", "gggggggg", ".g.gg.gg", "dd.dd.dd"],
  },
  nan: {
    colors: { p: "#e0a0ff", d: "#9a5fc8", k: "#1a0a2a", w: "#ffffff" },
    art: ["ppp...pp", "pkkp..pk", "pkpkp.pk", "pkppkppk", "pkp.pkpk", "pkp..pkk", "pkp...pk", "ppp...pp", "...ddddd", "..d.....", "dd.d.d.d"],
  },
  dangling: {
    colors: { r: "#ff4f6a", d: "#a82f44", k: "#1a060c", s: "#c8ccd8" },
    art: ["....ssss", "...sssss", "...ss...", "...ss.kk", "...ss.kr", "...sssss", "....ssss", "......rr", "......rr", ".....rr.", "....rr..", "...rr...", "..dd...."],
  },
  quota: {
    colors: { b: "#6fa8e0", d: "#3f6fa8", k: "#0c1a2a", w: "#e8f0ff", r: "#ff5a4f" },
    art: ["bbbbbbbbbb", "bdddddddbb", "bdkkkkkkbb", "bdkwwwwkbb", "bdkwwwwkbb", "bdkkkkkkbb", "bbbbbbbbbb", "brrrrrrrrr", "brrrrrrrrr", "brrrrrrrkk", "bbbbbbbbbb", "dddddddddd"],
  },
  ours: {
    colors: { g: "#6fe0c0", d: "#2fa888", k: "#08201a", w: "#ffffff" },
    art: ["kkkkkkkk", "kgggkggg", "kggkgggg", "kgkggggg", "kkggwwgg", "kgggwkgg", "kgkggggg", "kggkgggg", "kgggkggg", "kkkkkkkk", "..dd..dd"],
  },
  theirs: {
    colors: { p: "#ff9ac0", d: "#c85f88", k: "#200a14", w: "#ffffff" },
    art: ["kkkkkkkk", "pppkpppk", "ppppkppk", "pppppkpk", "ppwwppkk", "ppkwpppk", "pppppkpk", "ppppkppk", "pppkpppk", "kkkkkkkk", "dd..dd.."],
  },
  devnull: {
    colors: { k: "#07060c", p: "#8a7fb0", d: "#4f4670", w: "#d8d0f0" },
    art: ["....dddd", "..ddpppp", ".dppkkkk", ".dpkkkkk", "dpkkkkkk", "dpkkkkkk", "dpkkkkkk", "dpkkkkkk", ".dpkkkkk", ".dppkkkk", "..ddpppp", "....dddd"],
  },
  // ---------------------------------------------------------- IV. Дата-Центр
  condensate: {
    colors: { b: "#7fd0ff", d: "#3f8ac8", w: "#ffffff", k: "#0c1a2a" },
    art: [".......b", "......bb", ".....bbb", "....bbbb", "...bbbbb", "..bwbbbb", ".bwwbbbb", ".bbbkkbb", "bbbbkwbb", "bbbbbbbb", ".dbbbbbb", "..dddddd"],
  },
  wire: {
    colors: { s: "#6a7284", d: "#3a4050", y: "#ffd24a", k: "#0c0e14", c: "#c86a3a" },
    art: ["...ssss", "..sssss", "..ssykk", "..sssyy", "...ssss", "....sss", "...sss.", "..sss..", "..ss...", "..sss..", "...sss.", "....ccc"],
  },
  zombie: {
    colors: { g: "#8fb07a", d: "#5f7f4f", k: "#101a0a", r: "#ff5a4f", s: "#6a6a78" },
    art: ["...ggggg", "..gggggg", "..ggkrgg", "..gggggg", "..ggkkkk", "...ggggg", "..ssssss", ".sssdsss", "g.ssssss", "g.ssssss", "...ss.ss", "...dd.dd"],
  },
  forkbomb: {
    colors: { p: "#ff7ab0", d: "#c84f7a", k: "#1a0a10", y: "#ffe07a" },
    art: ["......yy", ".....k..", "...kkkkk", "..pppppp", ".pppkppp", ".ppkpkpp", ".pppppkk", ".ppppppk", "..dppppp", "...ddddd"],
  },
  nightalert: {
    colors: { r: "#ff4f4f", d: "#b82f2f", y: "#ffe07a", k: "#1a0606", s: "#3a3a48" },
    art: [".....yrr", "....rrrr", "...rrrrr", "...rrkkk", "..rrrkrr", "..rrrkrr", "..rrrkrr", "..rrrrrr", "..rrrkrr", ".ddddddd", ".sssssss", "ssssssss"],
  },
  surge: {
    colors: { y: "#ffe94a", o: "#d8a01a", w: "#ffffff", k: "#1a1404" },
    art: [".....yyy", "....yyyw", "....yyw.", "...yyw..", "...yywww", "..yyyyyy", "......yy", ".....yy.", "....yy..", "....y...", "...o....", "...o...."],
  },
  offbyone: {
    colors: { y: "#ffd27a", d: "#b88a3a", k: "#1a1208", r: "#ff5a5a" },
    art: ["yyyyyyyy", "ykkkkkkk", "ykyyyyyy", "ykyyyyyy", "ykyyrryy", "ykyyrryy", "ykyyyyyy", "ykyyyyyy", "ykkkkkkk", "yyyyyyyy", "..dd..dd"],
  },
  reverse: {
    colors: { c: "#9fe0ff", d: "#4f8ac8", k: "#0a1420", w: "#ffffff" },
    art: ["kkkk....", "kccc....", "kc..cc..", "kc.ccccc", "kc.cwkcc", "kc.ccccc", "kc..cc..", "kc......", "kccc....", "kkkk....", "..dd...d"],
  },
  chiller: {
    colors: { c: "#8fe4ff", d: "#3f8ac8", w: "#ffffff", s: "#5a6a7a", k: "#0a1420" },
    art: ["ssssssssss", "sccccccccc", "scdccdccdc", "scdccdccdc", "sccccccccw", "scdccdccww", "scdccdccww", "sccccccccw", "scdccdccdc", "sccccccccc", "ssssssssss", "kk..kk..kk"],
  },
  ups: {
    colors: { k: "#10141a", s: "#3a404c", g: "#7fe08a", y: "#ffd24a", w: "#e8ece8" },
    art: ["ssssssssss", "skkkkkkkkk", "skggggggkk", "skggggggkk", "skkkkkkkkk", "skkkkkkyyy", "skkkkkyyyk", "skkkkyyyyy", "skkkkkkyyk", "skkkkkyykk", "ssssssssss", "kk......kk"],
  },
  btree: {
    colors: { g: "#8fd67a", d: "#4f8a3f", b: "#8a6a3a", k: "#14200c", w: "#ffffff" },
    art: ["....gggg", "..gggggg", ".ggdgggg", ".gggggwk", "gggggggg", "ggdggggk", "gggggggg", ".gggdggg", "..gggggg", "....bbbb", ".....bbb", ".....bbb", "...bbbbb"],
  },
  btree_branch: {
    colors: { g: "#a8d67a", d: "#6f9a4f", b: "#8a6a3a", k: "#14200c" },
    art: ["...ggg", "..gggg", ".ggdgg", ".ggggk", ".ggggg", "..gggg", "...bbb", "...bbb", ".bbbbb"],
  },
  btree_leaf: {
    colors: { g: "#c8e88a", d: "#8ab85a", k: "#14200c" },
    art: ["....gg", "...ggg", "..gggd", ".ggkgd", ".ggggd", "..gggd", "....dd"],
  },
  // ----------------------------------------------------------------- V. Ядро
  warning: {
    colors: { y: "#ffc23d", d: "#c88a1a", k: "#1a1208" },
    art: ["......yy", ".....yyy", ".....ykk", "....yykk", "....yykk", "...yyykk", "...yyykk", "..yyyyyk", "..yyyyyy", ".yyyyykk", ".yyyyykk", "dddddddd"],
  },
  traceback: {
    colors: { r: "#ff8a8a", d: "#b84f4f", w: "#ffe8e8", k: "#200a0a" },
    art: ["rrrrrrrr", "rkkkkkkr", "rwwwwwwr", "rkkkkwwr", "rwwwwwwr", "rkkkkkwr", "rwwwwwwr", "rrrrrrrr", "...dd...", "...dd..."],
  },
  logline: {
    colors: { k: "#0c140e", g: "#9ac8a0", d: "#3f6a48" },
    art: ["kkkkkkkk", "kdggggdg", "kkkkkkkk", "kgggdggg", "kkkkkkkk", "kdggdggd", "kkkkkkkk"],
  },
  flaky: {
    colors: { g: "#7fe08a", d: "#3f8a4f", r: "#ff5a5a", k: "#0c1a10", w: "#ffffff" },
    art: ["....gggg", "..gggggg", ".gggkkgg", ".ggkkwwg", "ggggkwww", "gggggggg", "rrrrrrrr", "rrrrkkrr", ".rrrkrkr", ".rrrrrrr", "..rrrrrr", "....rrrr"],
  },
  reflection: {
    colors: { w: "#d8e4ff", c: "#9ab0e0", d: "#5f6f9a", k: "#101828", h: "#ffffff" },
    art: ["....cccc", "...ccwww", "...cwwww", "...cwkww", "...cwwww", "..ccccww", ".ccccccc", ".cwhhhcc", ".cwwhhhc", "..cccccc", "...cc.cc", "...dd.dd"],
  },
  prince: {
    colors: { y: "#ffd24a", o: "#c88a1a", s: "#e8c8a0", k: "#1a1208", p: "#7a3fc8", r: "#ff4f6a" },
    art: ["y..y..yy", "yyyyyyyy", "yryyyryy", "oooooooo", "..ssssss", "..sskssk", "..ssssss", "...skkkk", "..pppppp", ".ppyyppp", ".ppyyppp", ".ppppppp", "..oo..oo"],
  },
  captcha: {
    colors: { w: "#e8ecf4", g: "#c8d4e8", k: "#1a2030", b: "#4f8ae0", d: "#8a94a8" },
    art: ["wwwwwwwww", "wkkkkkkkk", "wkwwwwwww", "wkwwwwwbw", "wkwwwwbbw", "wkbwwbbww", "wkbbbbwww", "wkwbbwwww", "wkkkkkkkk", "wwwwwwwww", "ddddddddd"],
  },
  vibecoder: {
    colors: { s: "#e8c8a0", h: "#3a2c20", g: "#b0ff8a", d: "#5fa83f", k: "#14100a", w: "#ffffff" },
    art: ["...hhhhh", "..hhhhhh", "..kkkkkk", "..kgkgkk", "..sskkkk", "...sssss", "..dddddd", ".ddddggg", ".ddddggg", "..kkkkkk", "..kgggkg", "kkkkkkkk"],
  },
  promptinject: {
    colors: { p: "#ff9af0", d: "#c85fb8", k: "#200a1c", w: "#ffffff" },
    art: ["ppppppp", "pkkkkkk", "pkwwwww", "pkwkkkw", "pkwwwww", "pkwkkkk", "pkwwwww", "pkkkkkk", "ppppppp", "...dddd", "..dd..."],
  },
  debugmode: {
    colors: { g: "#7fe0a8", d: "#2f8a5f", k: "#08140e", w: "#ffffff", r: "#ff5a5a" },
    art: ["g......g", ".g....gg", "..g.gggg", "...ggggg", "gggggwwg", "...ggwkg", "..gggggg", "gggggggg", "...ggggd", "..gddggg", ".g.ddddd", "g.....dd"],
  },
  taberror: {
    colors: { o: "#ffb07a", d: "#c8773f", k: "#200f06", w: "#ffffff" },
    art: ["oooooooooo", "okkkkkkkko", "okwwwwwwko", "okkkwkkkko", "okwwwwwwwo", "okkkkkwkko", "okwwwwwwko", "okkkkkkkko", "oooooooooo", "dddddddddd", "...dd...dd"],
  },
  context: {
    colors: { r: "#ff7a9a", d: "#c84f6a", k: "#1a0810", w: "#ffffff" },
    art: ["rrrrrrrrrr", "r.........", "r..kkkkkkk", "r..kwwwwww", "r..kwkkkkw", "r..kwwwwww", "r..kwkkkkk", "r..kwwwwww", "r..kkkkkkk", "r.........", "rrrrrrrrrr", "dd......dd"],
  },
};
