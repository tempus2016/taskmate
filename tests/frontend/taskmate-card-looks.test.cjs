const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const { loadCard, render, localize, WWW } = require("./harness.cjs");

// Card looks: compact density, seasonal themes, dark care strips, the child's
// own colour and their tick-off animation — on the child card under every
// design, the kiosk card and the admin panel. The effect engine, the season
// table and the colour helper come from the real taskmate-design.js.

const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const LAYOUT = { graphite: "cleanpro" };
const ENTITY = "sensor.taskmate_overview";
const plain = (v) => JSON.parse(JSON.stringify(v));

function designLayer({ reduced = false } = {}) {
  const window = { matchMedia: (q) => ({ matches: reduced && q.includes("reduced-motion") }) };
  vm.runInNewContext(readFileSync(path.join(WWW, "taskmate-design.js"), "utf8"), {
    window,
    document: { documentElement: { getAttribute: () => "" }, getElementById: () => ({}), createElement: () => ({}), head: { appendChild() {} } },
    customElements: { get: () => undefined },
  });
  return window;
}

function helpers({ dark = false, reduced = false } = {}) {
  const real = designLayer({ reduced });
  return {
    __taskmate_fx: real.__taskmate_fx,
    __taskmate_season: real.__taskmate_season,
    __taskmate_design: {
      // The real apply() stamps the host; the harness has no attributes, so
      // hand back the layout id the way apply() does.
      apply: (_card, _hass, config) => LAYOUT[config?.card_design] || config?.card_design || "classic",
      styles: () => null,
      editorOptions: () => [],
      isDark: () => dark,
      childColour: real.__taskmate_design.childColour,
    },
  };
}

function childCard({ design = "classic", child = {}, attrs = {}, config = {}, dark = false, reduced = false } = {}) {
  const loaded = loadCard("taskmate-child-card.js", { window: helpers({ dark, reduced }) });
  const card = new (loaded.get("taskmate-child-card"))();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design, ...config });
  card.hass = {
    states: { [ENTITY]: { state: "ok", attributes: {
      children: [{ id: "kid1", name: "Mia", points: 320, chore_order: [], ...child }],
      chores: [
        { id: "bed", name: "Make bed", points: 2, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", assignment_mode: "everyone", description: "Pull the duvet straight" },
        { id: "teeth", name: "Brush teeth", points: 1, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", assignment_mode: "everyone" },
      ],
      todays_completions: [], chore_availability: {}, today_day_of_week: "wednesday", points_icon: "mdi:star",
      ...attrs,
    } } },
    callService: async () => {},
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card._playSound = () => {};
  return card;
}

// ── 6. compact density ────────────────────────────────────────────────────

for (const design of DESIGNS) {
  test(`compact: ${design} marks the card compact, normal does not`, () => {
    const compact = render(childCard({ design, config: { density: "compact", show_description: true } }).render()).markup;
    assert.match(compact, /<ha-card class="[^"]*\bcompact\b/);
    assert.ok(compact.includes("Make bed") && compact.includes("Brush teeth"));
    const normal = render(childCard({ design }).render()).markup;
    assert.doesNotMatch(normal, /<ha-card class="[^"]*\bcompact\b/);
    if (design !== "classic") {
      assert.match(compact, /--av:28px/, "the designed header avatar shrinks");
      assert.match(normal, /--av:34px/);
    }
  });
}

test("compact: there is a compact rule for every row type, graphite included", () => {
  const Card = loadCard("taskmate-child-card.js").get("taskmate-child-card");
  const cssText = render(Card.styles).markup;
  for (const sel of [".compact .chore-card", ".compact .chore-checkbox", ".compact .card-header", ".compact .tmd-chore",
    ".compact .tmd-quest", ".compact .tmd-check", ".compact .tmd-hd", ':host([data-tm-design="graphite"]) .compact .tmd-check']) {
    assert.ok(cssText.includes(sel), sel);
  }
});

test("compact: the editor offers density, translated, and stores only compact", () => {
  const Editor = loadCard("taskmate-child-card.js").get("taskmate-child-card-editor");
  const ed = new Editor();
  ed.hass = { states: {} };
  ed.setConfig({ entity: ENTITY, child_id: "kid1" });
  const field = ed._buildSchema().find((f) => f.name === "density");
  assert.deepEqual(plain(field.selector.select.options), [
    { value: "normal", label: localize("child.editor.density_normal") },
    { value: "compact", label: localize("child.editor.density_compact") },
  ]);
  assert.equal(ed._computeLabel({ name: "density" }), localize("child.editor.density"));
  const sent = [];
  ed._dispatchConfig = (c) => sent.push(c);
  ed._formChanged({ detail: { value: { density: "compact" } } });
  ed._formChanged({ detail: { value: { density: "normal" } } });
  assert.equal(sent[0].density, "compact");
  assert.ok(!("density" in sent[1]));
});

// ── 7. seasonal themes ────────────────────────────────────────────────────

for (const design of DESIGNS) {
  test(`season: ${design} gets the gradient header and the season emoji`, () => {
    const { markup } = render(childCard({ design, attrs: { season: "halloween" } }).render());
    assert.match(markup, /linear-gradient\(135deg,#e8590c,#6a1b9a\)/);
    assert.match(markup, /tm-season-badge[^>]*>🎃/);
    const off = render(childCard({ design, attrs: { season: "halloween" }, config: { seasonal: false } }).render()).markup;
    assert.doesNotMatch(off, /linear-gradient|tm-season-badge/);
    assert.doesNotMatch(render(childCard({ design }).render()).markup, /tm-season-badge/);
  });
}

test("season: the classic header keeps its full-colour band, as a gradient", () => {
  const { markup } = render(childCard({ attrs: { season: "christmas" } }).render());
  assert.match(markup, /--taskmate-header-bg: linear-gradient\(135deg,#c62828,#2e7d32\)/);
  assert.match(markup, /stars-value my-stars">\s*<span aria-hidden="true">🎄<\/span>/);
});

test("season: the celebration follows the season unless the child picked their own", () => {
  const card = childCard({ attrs: { season: "christmas" } });
  card._spawnConfetti();
  assert.equal(card._fxEffect, "snow");
  assert.match(render(card._renderConfetti()).markup, /tm-fx tm-fx-snow[\s\S]*❄️/);
  card._spawnConfetti("fireworks");
  assert.equal(card._fxEffect, "fireworks");
  card._spawnConfetti("confetti");
  assert.equal(card._fxEffect, "snow", "confetti is the default, so the season dresses it");
});

test("season: the editor's seasonal switch is on by default and stores only off", () => {
  const Editor = loadCard("taskmate-child-card.js").get("taskmate-child-card-editor");
  const ed = new Editor();
  ed.setConfig({ entity: ENTITY, child_id: "kid1" });
  assert.ok(ed._buildSchema().some((f) => f.name === "seasonal"));
  assert.equal(ed._computeLabel({ name: "seasonal" }), localize("child.editor.seasonal"));
  const sent = [];
  ed._dispatchConfig = (c) => sent.push(c);
  ed._formChanged({ detail: { value: { seasonal: false } } });
  ed._formChanged({ detail: { value: { seasonal: true } } });
  assert.equal(sent[0].seasonal, false);
  assert.ok(!("seasonal" in sent[1]));
});

// ── 8. dark care strips ───────────────────────────────────────────────────

const CARE = { sick_today: true, redemptions: [{ id: "r", chore_name: "Bins", points: 5, expires: "2026-10-30" }] };

for (const design of DESIGNS) {
  test(`dark strips: ${design} marks the strips dark only in dark mode`, () => {
    const dark = render(childCard({ design, child: CARE, dark: true }).render()).markup;
    assert.match(dark, /class="tm-care-wrap (classic|tmd) dark"/);
    const light = render(childCard({ design, child: CARE }).render()).markup;
    assert.match(light, /class="tm-care-wrap (classic|tmd) "/);
  });
}

function contrast(a, b) {
  const lum = (hex) => {
    const [r, g, bl] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

test("dark strips: every coloured strip has a dark variant with AA text", () => {
  const Card = loadCard("taskmate-child-card.js").get("taskmate-child-card");
  const cssText = render(Card.styles).markup;
  const lightStrips = new Set(Array.from(cssText.matchAll(/^\s*\.(tm-care-[a-z-]+)(?:\.[a-z]+)? \{ background: #/gm), (m) => m[1]));
  assert.ok(lightStrips.size >= 9, [...lightStrips].join());
  for (const cls of lightStrips) {
    assert.ok(cssText.includes(`.tm-care-wrap.dark .${cls}`), `${cls} has no dark variant`);
  }
  const pairs = Array.from(cssText.matchAll(/\.tm-care-wrap\.dark [^{]+\{ background: (#[0-9a-f]{6}); color: (#[0-9a-f]{6})/g));
  assert.ok(pairs.length >= 9);
  for (const [rule, bg, fg] of pairs) assert.ok(contrast(bg, fg) >= 4.5, `${rule} is ${contrast(bg, fg).toFixed(2)}:1`);
});

// ── 9. the child's colour ─────────────────────────────────────────────────

for (const design of DESIGNS) {
  test(`colour: ${design} uses the child's colour for the header unless the card sets one`, () => {
    const own = render(childCard({ design, child: { color: "#1565c0" } }).render()).markup;
    const set = render(childCard({ design, child: { color: "#1565c0" }, config: { header_color: "#123456" } }).render()).markup;
    if (design === "classic") {
      assert.match(own, /--taskmate-header-bg: #1565c0/);
      assert.match(set, /--taskmate-header-bg: #123456/);
    } else {
      assert.match(own, /--hd:#1565c0/);
      assert.match(set, /--hd:#123456/);
    }
    assert.match(own, /--tm-child:#1565c0/, "progress bars and confetti take it too");
    assert.doesNotMatch(set, /--tm-child/);
  });
}

test("colour: a light colour is darkened until white header text reads", () => {
  const { childColour } = designLayer().__taskmate_design;
  assert.equal(childColour("#1e88e5", "classic"), "#1e88e5");
  const yellow = childColour("#f1c40f", "classic");
  assert.notEqual(yellow, "#f1c40f");
  assert.ok(contrast(yellow, "#ffffff") >= 3);
  const strict = childColour("#e91e63", "accessible");
  assert.ok(contrast(strict, "#ffffff") >= 4.5, "accessible asks for 4.5:1");
  assert.equal(childColour("red", "classic"), "");
  assert.equal(childColour("", "classic"), "");
});

test("colour: tick-off confetti is tinted with the child's colour", () => {
  const card = childCard({ child: { color: "#1e88e5" } });
  card._spawnConfetti();
  assert.equal(card._fxTint, "#1e88e5");
  assert.match(render(card._renderConfetti()).markup, /background:#1e88e5/);
});

test("colour: resetting the header colour in the editor drops the key", () => {
  const Editor = loadCard("taskmate-child-card.js").get("taskmate-child-card-editor");
  const ed = new Editor();
  ed.setConfig({ entity: ENTITY, child_id: "kid1", header_color: "#123456" });
  const sent = [];
  ed._dispatchConfig = (c) => sent.push(c);
  ed._updateConfig("header_color", undefined);
  assert.ok(!("header_color" in sent[0]));
});

// ── 10. done animation per child ──────────────────────────────────────────

test("fx: pick prefers the child's style, then the season, then confetti", () => {
  const { __taskmate_fx: fx, __taskmate_season: season } = designLayer();
  const halloween = season({ season: "halloween" }, {});
  assert.equal(fx.pick("stamp", halloween), "stamp");
  assert.equal(fx.pick("confetti", halloween), "bats");
  assert.equal(fx.pick(undefined, null), "confetti");
  assert.equal(fx.pick("lasers", null), "confetti");
  assert.equal(season({ season: "halloween" }, { seasonal: false }), null);
  assert.equal(season({}, {}), null);
});

test("fx: each style renders its own pieces", () => {
  const { __taskmate_fx: fx } = designLayer();
  const html = (strings, ...values) => ({ __tmTemplate: true, strings, values });
  const out = (effect) => render(fx.render(html, fx.spawn(effect), { label: "Done!" })).markup;
  assert.match(out("stamp"), /tm-fx-stamp-mark[^>]*>Done!/);
  assert.match(out("sticker"), /tm-fx-sticker-mark[^>]*>⭐/);
  assert.equal((out("fireworks").match(/--dx:/g) || []).length, 54);
  assert.equal((out("confetti").match(/tm-fx-p/g) || []).length, 50);
  assert.match(out("bats"), /🦇/);
});

test("fx: reduced motion plays nothing", () => {
  const { __taskmate_fx: fx } = designLayer({ reduced: true });
  assert.equal(fx.spawn("fireworks"), null);
  const card = childCard({ reduced: true });
  card._spawnConfetti("stamp");
  assert.equal(card._confetti.length, 0);
});

for (const design of DESIGNS) {
  test(`fx: ${design} plays the child's own style on a tick-off`, async () => {
    const card = childCard({ design, child: { celebration_style: "stamp" } });
    await card._handleComplete(card.hass.states[ENTITY].attributes.chores[1], card.hass.states[ENTITY].attributes.children[0]);
    assert.equal(card._fxEffect, "stamp");
    assert.match(render(card.render()).markup, new RegExp(`tm-fx-stamp-mark[^>]*>${localize("child.fx_stamp")}`));
  });
}

// ── kiosk card ────────────────────────────────────────────────────────────

async function kiosk({ child = {}, attrs = {}, config = {} } = {}) {
  const sandbox = { setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {} };
  const Kiosk = loadCard("taskmate-kiosk-card.js", { sandbox, window: helpers() }).get("taskmate-kiosk-card");
  const card = new Kiosk();
  card.setConfig({ entity: ENTITY, ...config });
  card.hass = {
    locale: { language: "en" },
    callService: async () => {},
    callWS: async () => ({ children: [{ id: "kid1", has_pin: false, can_act: true, due: ["bed"] }] }),
    states: { [ENTITY]: { state: "ok", attributes: {
      children: [{ id: "kid1", name: "Mia", points: 320, chore_order: [], ...child }],
      chores: [{ id: "bed", name: "Make bed", points: 2, assigned_to: [] }],
      todays_completions: [], points_icon: "mdi:star", ...attrs,
    } } },
  };
  await card._refreshStatus();
  card._openKid(card._entry("kid1"));
  return card;
}

test("kiosk: the child's screen takes their colour, the season and their style", async () => {
  const card = await kiosk({ child: { color: "#1e88e5", celebration_style: "sticker" }, attrs: { season: "summer" } });
  const { markup } = render(card.render());
  assert.match(markup, /km-child" style="--kc:#1e88e5"/);
  assert.match(markup, /km-head" style="background:linear-gradient\(135deg,#e65100,#0277bd\)"/);
  assert.match(markup, /tm-season-badge[^>]*>☀️/);
  await card._complete(card._entry("kid1").child, card.hass.states[ENTITY].attributes.chores[0]);
  assert.equal(card._fxEffect, "sticker");
  assert.match(render(card.render()).markup, /km-confetti tm-fx tm-fx-sticker/);
});

test("kiosk: seasonal: false and no colour leave the palette and plain header", async () => {
  const card = await kiosk({ attrs: { season: "summer" }, config: { seasonal: false } });
  const { markup } = render(card.render());
  assert.match(markup, /km-child" style="--kc:var\(--tmd-c1/);
  assert.match(markup, /km-head" style=""/);
  card._spawnConfetti(card._entry("kid1").child);
  assert.equal(card._fxEffect, "confetti");
});

// ── panel ─────────────────────────────────────────────────────────────────

function panel() {
  const Panel = loadCard("taskmate-panel.js").get("taskmate-panel");
  const p = Object.create(Panel.prototype);
  p._t = (key) => key;
  p._state = { children: [{ id: "kid1", name: "Mia", celebration_style: "fireworks" }], settings: {} };
  p._sent = [];
  p._callWS = async (msg) => { p._sent.push(msg); return { ok: true, res: { id: "kid1" } }; };
  p._syncIconPickers = () => {};
  p._closeDialog = () => {};
  p._fetchState = async () => {};
  p._showToast = () => {};
  return p;
}

test("panel: the child dialog shows a tile per style with the current one on", () => {
  const html = panel()._childCelebrationField({ celebration_style: "fireworks" });
  for (const v of ["confetti", "stamp", "fireworks", "sticker"]) {
    assert.match(html, new RegExp(`data-act="child-celebration" data-v="${v}"`));
    assert.ok(html.includes(`panel.celebration_${v}`) && html.includes(`panel.celebration_${v}_hint`));
  }
  assert.match(html, /tm-fx-pick tm-on"\s+data-act="child-celebration" data-v="fireworks" aria-checked="true"/);
});

test("panel: saving a child sends the style", async () => {
  const p = panel();
  p._dialog = { mode: "edit", data: { id: "kid1", name: "Mia", celebration_style: "stamp" } };
  await p._doSaveChild();
  assert.equal(p._sent[0].celebration_style, "stamp");
  p._dialog = { mode: "add", data: { name: "Isla" } };
  await p._doSaveChild();
  assert.equal(p._sent[1].celebration_style, "confetti");
});

test("panel: Settings has a switch per season, off until set", () => {
  const p = panel();
  const off = p._renderSeasonalSettings({});
  for (const s of ["halloween", "christmas", "summer"]) assert.match(off, new RegExp(`data-setting="seasonal_${s}" >`));
  assert.match(p._renderSeasonalSettings({ seasonal_christmas: true }), /data-setting="seasonal_christmas" checked/);
});

// The compact avatar icon rule also matched the pencil inside the edit dot,
// blowing it up over half the avatar; the dot's own rule must come after it.
test("compact: the avatar's edit pencil keeps its small size", () => {
  const src = require("node:fs").readFileSync(require("node:path").join(__dirname, "../../custom_components/taskmate/www/taskmate-child-card.js"), "utf8");
  const generic = src.indexOf(".compact .avatar-container ha-icon");
  const pencil = src.indexOf(".compact .avatar-edit-dot ha-icon");
  assert.ok(generic > 0 && pencil > generic);
});
