const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const { loadCard, render, localize, WWW } = require("./harness.cjs");

// Season event packs: Settings → Seasons & events in the panel, and the
// advent calendar strip on the child card (both render paths) and the kiosk.

const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const LAYOUT = { graphite: "cleanpro" };
const ENTITY = "sensor.taskmate_overview";

function helpers() {
  const window = { matchMedia: () => ({ matches: false }) };
  vm.runInNewContext(readFileSync(path.join(WWW, "taskmate-design.js"), "utf8"), {
    window,
    document: { documentElement: { getAttribute: () => "" }, getElementById: () => ({}), createElement: () => ({}), head: { appendChild() {} } },
    customElements: { get: () => undefined },
  });
  return {
    __taskmate_fx: window.__taskmate_fx,
    __taskmate_season: window.__taskmate_season,
    __taskmate_design: {
      apply: (_card, _hass, config) => LAYOUT[config?.card_design] || config?.card_design || "classic",
      styles: () => null,
      editorOptions: () => [],
      isDark: () => false,
      childColour: window.__taskmate_design.childColour,
    },
  };
}

const DOORS = "oooooomo" + "t" + "l".repeat(15);
const ADVENT = { chore: "door9", door: 9, goal: 20, badge: "Little Elf" };
const CHORES = [
  { id: "bed", name: "Make bed", points: 2, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", assignment_mode: "everyone" },
  { id: "door9", name: "Door 9: Write a card for Granny", points: 5, time_category: "anytime", assigned_to: ["kid1"], due_days: [], schedule_mode: "one_shot", assignment_mode: "everyone" },
];

function childCard({ design = "classic", child = {}, attrs = {} } = {}) {
  const loaded = loadCard("taskmate-child-card.js", { window: helpers() });
  const card = new (loaded.get("taskmate-child-card"))();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design });
  card.hass = {
    states: { [ENTITY]: { state: "ok", attributes: {
      children: [{ id: "kid1", name: "Mia", points: 112, chore_order: [], ...child }],
      chores: CHORES,
      todays_completions: [], chore_availability: {}, today_day_of_week: "wednesday", points_icon: "mdi:star", points_name: "Stars",
      ...attrs,
    } } },
    callService: async () => {},
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card._playSound = () => {};
  return card;
}

for (const design of DESIGNS) {
  test(`advent: ${design} shows the 24 doors and today's door as the action`, () => {
    const { markup } = render(childCard({ design, child: { advent: DOORS }, attrs: { advent: ADVENT, season: "christmas" } }).render());
    assert.match(markup, /class="tm-advent/);
    assert.equal((markup.match(/class="tm-door /g) || []).length, 24);
    assert.match(markup, /class="tm-door t"/);
    assert.match(markup, /class="tm-door m"/);
    assert.match(markup, /class="tm-door l d24"/);
    assert.match(markup, /tm-advent-today[\s\S]*Door 9: Write a card for Granny[\s\S]*<button/);
    // Today's door is the strip's action, not a second row in the list.
    assert.equal((markup.match(/Door 9: Write a card for Granny/g) || []).length, 1);
    assert.ok(markup.includes("Make bed"));
    assert.ok(markup.includes(localize("child.advent_badge", { goal: 20, badge: "Little Elf" })));
  });

  test(`advent: ${design} shows nothing without the pack`, () => {
    const { markup } = render(childCard({ design }).render());
    assert.doesNotMatch(markup, /tm-advent/);
    assert.match(markup, /Door 9: Write a card for Granny/, "the door is an ordinary chore then");
  });
}

test("advent: the Done button completes today's door", async () => {
  const card = childCard({ child: { advent: DOORS }, attrs: { advent: ADVENT } });
  const done = [];
  card._handleComplete = (chore, child) => { done.push([chore.id, child.id]); };
  const { markup } = render(card._renderAdvent(card.hass.states[ENTITY].attributes.children[0], card.hass.states[ENTITY].attributes, CHORES, "classic"));
  assert.ok(markup.includes(localize("child.advent_opened", { done: 7, total: 9 })));
  const tpl = card._renderAdvent(card.hass.states[ENTITY].attributes.children[0], card.hass.states[ENTITY].attributes, CHORES, "classic");
  // Find the click handler lit-html carries for the button.
  const handlers = [];
  const walk = (v) => {
    if (!v) return;
    if (Array.isArray(v)) return v.forEach(walk);
    if (typeof v === "function") handlers.push(v);
    if (v.values) walk(v.values);
  };
  walk(tpl);
  handlers.forEach((fn) => fn());
  assert.deepEqual(done, [["door9", "kid1"]]);
});

test("advent: a door waiting for approval says so and has no button", () => {
  const doors = "oooooomo" + "p" + "l".repeat(15);
  const { markup } = render(childCard({ child: { advent: doors }, attrs: { advent: ADVENT } }).render());
  assert.ok(markup.includes(localize("child.advent_waiting")));
  assert.doesNotMatch(markup, /tm-advent-today[\s\S]*<button[^>]*>\s*Done/);
});

test("advent: both render paths call the strip", () => {
  const src = readFileSync(path.join(WWW, "taskmate-child-card.js"), "utf8");
  assert.equal((src.match(/this\._renderAdvent\(child, attrs, allChores, "(classic|tmd)"\)/g) || []).length, 2);
  assert.equal((src.match(/this\._withoutAdventDoor\(this\._filterAndSortChores\(allChores, child\), child, attrs\)/g) || []).length, 2);
});

// ── kiosk ─────────────────────────────────────────────────────────────────

test("kiosk: the child's screen shows the advent tile", async () => {
  const sandbox = { setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {} };
  const Kiosk = loadCard("taskmate-kiosk-card.js", { sandbox, window: helpers() }).get("taskmate-kiosk-card");
  const card = new Kiosk();
  card.setConfig({ entity: ENTITY });
  card.hass = {
    locale: { language: "en" },
    callService: async () => {},
    callWS: async () => ({ children: [{ id: "kid1", has_pin: false, can_act: true, due: ["bed"] }] }),
    states: { [ENTITY]: { state: "ok", attributes: {
      children: [{ id: "kid1", name: "Mia", points: 320, chore_order: [], advent: DOORS }],
      chores: [{ id: "bed", name: "Make bed", points: 2, assigned_to: [] }],
      todays_completions: [], points_icon: "mdi:star", advent: ADVENT,
    } } },
  };
  await card._refreshStatus();
  card._openKid(card._entry("kid1"));
  const { markup } = render(card.render());
  assert.match(markup, /km-tile km-advent/);
  assert.equal((markup.match(/class="km-door /g) || []).length, 24);
  delete card.hass.states[ENTITY].attributes.advent;
  assert.doesNotMatch(render(card.render()).markup, /km-advent/);
});

// ── panel ─────────────────────────────────────────────────────────────────

const PACKS = [
  { season: "halloween", emoji: "🎃", state: "installed", installed_on: "2026-10-24", window: ["2026-10-24", "2026-10-31"], items: 8, children: ["kid2"],
    contents: [{ kind: "quest", key: "pumpkin_patrol", steps: 5, items: ["carve_pumpkin"], points: 25 }, { kind: "chores", items: [{ key: "carve_pumpkin", points: 10 }] }, { kind: "reward", key: "pick_the_movie", points: 40 }, { kind: "badge", key: "ghostbuster", goal: 5, points: 10 }] },
  { season: "christmas", emoji: "🎄", state: "scheduled", window: ["2026-12-01", "2026-12-26"], items: 0, children: [],
    contents: [{ kind: "advent", count: 24, points: 5 }] },
  { season: "back_to_school", emoji: "🎒", state: "needs_date", items: 0, children: [], contents: [] },
];

let confirmAnswer = true;

function panel(settings = {}) {
  const Panel = loadCard("taskmate-panel.js", { sandbox: { confirm: () => confirmAnswer } }).get("taskmate-panel");
  const p = Object.create(Panel.prototype);
  p._t = (key, params) => (params ? `${key}${JSON.stringify(params)}` : key);
  p._state = {
    children: [{ id: "kid1", name: "Mia" }, { id: "kid2", name: "Leo" }, { id: "mum", name: "Mum", is_adult: true }],
    settings, season_packs: PACKS,
  };
  p._sent = [];
  p._callWS = async (msg) => { p._sent.push(msg); return { ok: true, res: {} }; };
  p._fetchState = async () => {};
  p._toasts = [];
  p._showToast = (kind, text) => p._toasts.push([kind, text]);
  return p;
}

test("panel: each season has a theme and a pack switch, a state chip and its contents", () => {
  const html = panel({ season_pack_halloween: true })._renderSeasonalSettings({ season_pack_halloween: true });
  for (const s of ["halloween", "christmas", "easter", "summer", "back_to_school"]) {
    assert.match(html, new RegExp(`data-setting="seasonal_${s}"`));
    assert.match(html, new RegExp(`data-setting="season_pack_${s}"`));
  }
  assert.match(html, /data-setting="season_pack_halloween" aria-label="[^"]*" checked/);
  assert.match(html, /tm-spack-chip tm-spack-ok">panel\.season_state_installed/);
  assert.match(html, /tm-spack-chip tm-spack-info">panel\.season_state_scheduled/);
  assert.match(html, /tm-spack-chip tm-spack-warn">panel\.season_state_needs_date/);
  assert.match(html, /season_pack\.halloween\.pick_the_movie · ⭐ 40/);
  assert.match(html, /data-setting="season_school_start"/);
  // Grown-ups are never offered.
  assert.doesNotMatch(html, /data-spack-kid="halloween:mum"/);
  assert.match(html, /tm-chip-btn tm-chip-on" aria-pressed="true" data-act="spack-kid" data-spack-kid="halloween:kid2"/);
  // Remove only where something is installed.
  assert.equal((html.match(/data-act="spack-remove"/g) || []).length, 1);
  assert.doesNotMatch(html, /Import a pack/i);
});

test("panel: Preview lists the advent doors with their points", () => {
  const p = panel();
  p._dialog = { kind: "spack-preview", data: { season: "christmas" } };
  const html = p._renderSeasonPackPreview();
  assert.equal((html.match(/season_pack\.door/g) || []).length, 24);
  assert.match(html, /tm-spack-pts">⭐ 5/);
});

test("panel: Remove pack asks, then removes and says so", async () => {
  const p = panel();
  confirmAnswer = true;
  await p._removeSeasonPack("halloween");
  assert.deepEqual(JSON.parse(JSON.stringify(p._sent)), [{ type: "taskmate/season_packs/remove", season: "halloween" }]);
  assert.equal(p._toasts[0][0], "ok");
  confirmAnswer = false;
  await p._removeSeasonPack("halloween");
  assert.equal(p._sent.length, 1);
});
