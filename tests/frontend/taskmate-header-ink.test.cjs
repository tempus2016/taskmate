const assert = require("node:assert/strict");
const { readFileSync, readdirSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const { WWW } = require("./harness.cjs");

// Banner ink: every full-colour header picks white or near-black text from
// the colour actually painted there (APCA lightness contrast). The header
// colour itself never changes; only --tmd-hd-text / -ink / -scrim do.

function designLayer() {
  const window = { matchMedia: () => ({ matches: false }) };
  vm.runInNewContext(readFileSync(path.join(WWW, "taskmate-design.js"), "utf8"), {
    window,
    document: { documentElement: { getAttribute: () => "" }, getElementById: () => ({}), createElement: () => ({}), head: { appendChild() {} } },
    customElements: { get: () => undefined },
  });
  return window.__taskmate_design;
}

function fakeHost() {
  const props = {};
  const attrs = {};
  return {
    props,
    style: {
      setProperty: (k, v) => { props[k] = v; },
      removeProperty: (k) => { delete props[k]; },
    },
    setAttribute: (k, v) => { attrs[k] = String(v); },
    getAttribute: (k) => (k in attrs ? attrs[k] : null),
    hasAttribute: (k) => k in attrs,
    toggleAttribute: (k, on) => { if (on) attrs[k] = ""; else delete attrs[k]; },
  };
}

const d = designLayer();

test("light header colours get dark ink", () => {
  for (const c of ["#f1c40f", "#ffeb3b", "#a5d6a7", "#fff", "#FFFFFF", "#ffc23c", "#2ecc71"]) {
    assert.equal(d.headerInkFor(c, "classic"), "dark", c);
  }
});

test("mid and dark header colours keep white ink, including every stock default", () => {
  // The card defaults were all chosen for white text; APCA keeps them white
  // where the WCAG 2 ratio would have turned the mid greens/oranges dark.
  const defaults = ["#27ae60", "#e67e22", "#b7950b", "#8e44ad", "#3498db", "#e74c3c", "#d35400",
    "#9b59b6", "#2471a3", "#16a085", "#c0392b", "#00897b", "#2e7d32", "#5b7fb9", "#ff7043",
    "#5e35b1", "#6c5ce7", "#3f51b5", "#5d6d7e", "#7c3aed", "#8d6e63", "#e91e63", "#03a9f4"];
  for (const c of [...defaults, "#7e57c2", "#1f3864", "#000"]) {
    assert.equal(d.headerInkFor(c, "classic"), "light", c);
  }
});

test("Playroom's band fades toward white, so its lighter end is judged", () => {
  assert.equal(d.headerInkFor("#27ae60", "cleanpro"), "light");
  assert.equal(d.headerInkFor("#27ae60", "playroom"), "dark");
  // Deep colours stay white even at the faded end.
  assert.equal(d.headerInkFor("#1f3864", "playroom"), "light");
});

test("gradients are judged on their lightest stop", () => {
  assert.equal(d.headerInkFor("linear-gradient(135deg,#1565c0,#f9a825)", "classic"), "dark");
  assert.equal(d.headerInkFor("linear-gradient(135deg,#c62828,#2e7d32)", "classic"), "light");
});

test("colours it cannot read leave the ink alone", () => {
  for (const c of ["", undefined, null, "var(--primary-color)", "red", "#12345"]) {
    assert.equal(d.headerInkFor(c, "classic"), "", String(c));
  }
});

test("APCA contrast has the right sign and size", () => {
  assert.ok(d.apcaContrast([0, 0, 0], [255, 255, 255]) > 100, "black on white");
  assert.ok(d.apcaContrast([255, 255, 255], [0, 0, 0]) < -100, "white on black");
  assert.equal(d.apcaContrast([128, 128, 128], [128, 128, 128]), 0);
});

test("headerInk sets dark ink on the host and clears it again", () => {
  const host = fakeHost();
  assert.equal(d.headerInk(host, "#ffeb3b", "classic"), "dark");
  assert.equal(host.props["--tmd-hd-text"], "#1a1a1a");
  assert.equal(host.props["--tmd-hd-ink"], "0,0,0");
  assert.equal(host.props["--tmd-hd-scrim"], "255,255,255");
  assert.equal(d.headerInk(host, "#1f3864", "classic"), "light");
  assert.deepEqual(host.props, {});
});

test("apply() inks the host from header_color, else the card's default", () => {
  const hass = { states: {}, themes: { darkMode: false } };
  const host = fakeHost();
  d.apply(host, hass, { header_color: "#f1c40f", card_design: "classic" }, "sensor.x", "#8e44ad");
  assert.equal(host.props["--tmd-hd-text"], "#1a1a1a");
  d.apply(host, hass, { card_design: "classic" }, "sensor.x", "#8e44ad");
  assert.equal(host.props["--tmd-hd-text"], undefined);
  d.apply(host, hass, { card_design: "playroom" }, "sensor.x", "#27ae60");
  assert.equal(host.props["--tmd-hd-text"], "#1a1a1a", "Playroom default green fades light");
});

test("headerInkCSS is always explicit, and reads palette tokens' fallbacks", () => {
  assert.match(d.headerInkCSS("#ffeb3b", "", null), /--tmd-hd-text:#1a1a1a;--tmd-hd-ink:0,0,0;--tmd-hd-scrim:255,255,255;/);
  assert.match(d.headerInkCSS("#1f3864", "", null), /--tmd-hd-text:#fff;--tmd-hd-ink:255,255,255;--tmd-hd-scrim:0,0,0;/);
  assert.match(d.headerInkCSS("var(--tmd-c5, #ffa726)", "", null), /--tmd-hd-text:#1a1a1a/);
  assert.match(d.headerInkCSS("var(--tmd-c1, #1565c0)", "", null), /--tmd-hd-text:#fff/);
});

test("the kit header and its chips follow the ink variables", () => {
  const css = d.cssText;
  assert.match(css, /\.tmd-hd\{[^}]*color:var\(--tmd-hd-text,#fff\)/);
  assert.match(css, /\.tmd-hd \.ic\{[^}]*background:rgba\(var\(--tmd-hd-ink,255,255,255\),\.22\)/);
  assert.match(css, /\.tmd-hd \.pill\{[^}]*background:rgba\(var\(--tmd-hd-ink,255,255,255\),\.25\)/);
});

test("every card that paints header_color as a banner ink-checks its header text", () => {
  // A classic .card-header painted from --taskmate-header-bg must take its
  // text colour from --tmd-hd-text, or a light header_color strands white text.
  const offenders = [];
  for (const f of readdirSync(WWW).filter((n) => /^taskmate-.*-card\.js$/.test(n))) {
    const src = readFileSync(path.join(WWW, f), "utf8");
    const re = /background:\s*var\(--taskmate-header-bg[^;]*;\s*(?:[^{}]*?)color:\s*([^;]+);/g;
    let m;
    while ((m = re.exec(src))) {
      if (!/--tmd-hd-text/.test(m[1])) offenders.push(`${f}: ${m[1].trim()}`);
    }
  }
  assert.deepEqual(offenders, []);
});
