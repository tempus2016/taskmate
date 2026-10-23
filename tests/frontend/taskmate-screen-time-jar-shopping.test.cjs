const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// Screen-time daily allowance and the weekend jar on the child card (every
// design) and in the panel; shopping-list jobs in the panel's Settings.

const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const ENTITY = "sensor.taskmate_overview";
const plain = (v) => JSON.parse(JSON.stringify(v));

function childCard({ design = "classic", screen_time } = {}) {
  const ChildCard = loadCard("taskmate-child-card.js").get("taskmate-child-card");
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design });
  const calls = [];
  card.hass = {
    states: { [ENTITY]: { state: "ok", attributes: {
      children: [{ id: "kid1", name: "Mia", chore_order: [], screen_time }],
      chores: [{ id: "bed", name: "Make bed", points: 2, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", assignment_mode: "everyone" }],
      todays_completions: [], chore_availability: {}, today_day_of_week: "wednesday", points_icon: "mdi:star",
    } } },
    callService: async (...args) => { calls.push(args); },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card._playSound = () => {};
  card._spawnConfetti = () => {};
  card._calls = calls;
  return card;
}

const JAR = { minutes: 70, cap: 120, day: 5, at: "08:00" };

for (const design of DESIGNS) {
  test(`child: ${design} shows today's allowance, the jar and Save`, () => {
    const card = childCard({ design, screen_time: { minutes: 25, active: false, low: false, allowance: 20, jar: JAR } });
    const view = render(card.render());
    assert.ok(view.markup.includes(localize("child.screen_time_allowance_part", { time: localize("child.screen_time_minutes", { m: 20 }) })));
    assert.ok(view.markup.includes(localize("child.screen_time_jar", { saved: 70, cap: 120 })));
    assert.match(view.markup, /aria-valuenow="58"/);
    assert.ok(view.markup.includes(localize("child.screen_time_save_hint")));
    assert.ok(view.control("tm-screen-save"), "Save button");
  });
}

test("child: Save opens a choice and sends what fits", async () => {
  const card = childCard({ screen_time: { minutes: 25, active: false, low: false, jar: JAR } });
  await render(card.render()).control("tm-screen-save").click();
  const view = render(card.render());
  const chips = view.controls.filter((c) => /tm-goal-chip/.test(c.attrs));
  assert.deepEqual(chips.map((c) => c.text), [
    localize("child.screen_time_minutes", { m: 10 }),
    localize("child.screen_time_save_all", { time: localize("child.screen_time_minutes", { m: 25 }) }),
  ]);
  await chips.at(-1).click();
  assert.deepEqual(plain(card._calls), [["taskmate", "save_screen_time", { child_id: "kid1", minutes: 25 }]]);
  assert.equal(card._screenSave, null);
});

test("child: a full jar or an empty balance hides Save", () => {
  const full = childCard({ screen_time: { minutes: 25, jar: { ...JAR, minutes: 120 } } });
  assert.equal(render(full.render()).control("tm-screen-save"), undefined);
  const empty = childCard({ screen_time: { minutes: 0, jar: JAR } });
  assert.equal(render(empty.render()).control("tm-screen-save"), undefined);
});

test("child: no jar, no allowance — the strip is as before", () => {
  const { markup } = render(childCard({ screen_time: { minutes: 30, active: false, low: false } }).render());
  assert.doesNotMatch(markup, /tm-screen-jar|tm-screen-save|tm-screen-allow/);
  assert.ok(markup.includes(localize("child.screen_time_hint")));
});

// ── panel ───────────────────────────────────────────────────────────────

function panel(settings = {}) {
  const TaskMatePanel = loadCard("taskmate-panel.js").get("taskmate-panel");
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => `${key}${Object.keys(params).length ? ":" + JSON.stringify(params) : ""}`;
  p._state = {
    children: [{ id: "kid1", name: "Malia" }, { id: "kid2", name: "Vaiha" }, { id: "dad", name: "Dad", is_adult: true }],
    screen_time: { kid1: { minutes: 45, allowance: 30, jar: 50, devices: [], active: false, log: [] } },
    settings: { screen_time_enabled: true, ...settings },
  };
  const sent = [];
  p._callWS = async (msg) => { sent.push(msg); return { ok: true, res: {} }; };
  p._fetchState = async () => {};
  p._render = () => {};
  p._showToast = (kind, msg) => sent.push({ toast: kind, msg });
  p._sent = sent;
  return p;
}

test("panel: allowance and jar settings rows", () => {
  const p = panel({ screen_time_allowance_school: 30, screen_time_allowance_unused: "carry", screen_time_jar_enabled: true });
  const html = p._renderScreenTimeSettings(p._state.settings);
  assert.match(html, /data-setting="screen_time_allowance_school" value="30"/);
  assert.match(html, /data-setting="screen_time_allowance_weekend" value="0"/);
  assert.match(html, /<option value="carry" selected>/);
  assert.match(html, /data-setting="screen_time_jar_enabled" checked/);
  assert.match(html, /data-setting="screen_time_jar_cap" value="120"/);
  assert.match(html, /<option value="5" selected>/);
  assert.match(html, /data-setting="screen_time_jar_open_time" value="08:00"/);
  assert.match(html, /panel\.screen_time_allowance_today/);
  assert.match(html, /data-act="st-jar-open" data-child="kid1"/);
  assert.doesNotMatch(html, /data-act="st-jar-open" data-child="kid2"/, "an empty jar has nothing to open");
});

test("panel: opening a jar goes over the websocket and shows errors", async () => {
  const p = panel();
  await p._openScreenJar("kid1");
  assert.deepEqual(plain(p._sent), [{ type: "taskmate/screen_time/jar", child_id: "kid1", action: "open" }]);
  p._callWS = async () => ({ ok: false, err: "Child nope not found" });
  await p._openScreenJar("nope");
  assert.deepEqual(plain(p._sent.at(-1)), { toast: "err", msg: "Child nope not found" });
});

test("panel: shopping-list jobs settings", () => {
  const p = panel({ shopping_jobs_enabled: true, shopping_jobs_children: ["kid2"], shopping_jobs_mode: "rotate" });
  const html = p._renderShoppingJobsSettings(p._state.settings);
  assert.match(html, /data-setting="shopping_jobs_enabled" checked/);
  assert.match(html, /data-ep-field="shopping_jobs_entity" data-ep-domains="todo"/);
  assert.match(html, /todo\.shopping_list/);
  assert.match(html, /data-setting="shopping_jobs_tag" value="#tm"/);
  assert.match(html, /data-setting="shopping_jobs_points" value="5"/);
  assert.match(html, /<option value="rotate" selected>/);
  assert.match(html, /panel\.shopping_jobs_mode_rotate_hint/);
  assert.match(html, /tm-chip-on" aria-pressed="true" data-act="shop-kid" data-shop-kid="kid2"/);
  assert.doesNotMatch(html, /data-shop-kid="dad"/);
});
