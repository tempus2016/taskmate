const assert = require("node:assert/strict");
const { test } = require("node:test");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const { loadCard, render, localize, WWW } = require("./harness.cjs");

// Boost windows on the child card (every design), the kiosk card and the
// admin panel. The boost helpers come from the real taskmate-design.js.

const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const ENTITY = "sensor.taskmate_overview";
const plain = (v) => JSON.parse(JSON.stringify(v));

function designHelpers() {
  const store = {};
  const window = { matchMedia: () => ({ matches: false }), localStorage: { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v; } } };
  const el = () => ({ style: {}, setAttribute() {}, appendChild() {} });
  vm.runInNewContext(readFileSync(path.join(WWW, "taskmate-design.js"), "utf8"), {
    window,
    document: { documentElement: { getAttribute: () => "" }, getElementById: () => ({}), createElement: el, head: { appendChild() {} }, body: { appendChild() {} }, addEventListener() {} },
    customElements: { get: () => undefined },
  });
  const pick = {};
  for (const k of ["__taskmate_boosts", "__taskmate_boost_for", "__taskmate_boost_seen", "__taskmate_boost_mark", "__taskmate_clock"]) pick[k] = window[k];
  return pick;
}

const minutes = (n) => new Date(Date.now() + n * 60000).toISOString();
const liveBoost = (over = {}) => ({ id: "b1", name: "Guests at six", multiplier: 2, chore_ids: ["bins"], chore_names: ["Take the bins out"],
  child_ids: [], starts_at: minutes(-5), ends_at: minutes(40), minutes: 45, ...over });

// ── child card ────────────────────────────────────────────────────────────

function childCard({ design = "classic", boosts = [liveBoost()], config = {} } = {}) {
  const ChildCard = loadCard("taskmate-child-card.js", { window: designHelpers() }).get("taskmate-child-card");
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design, ...config });
  card.hass = {
    states: { [ENTITY]: { state: "ok", attributes: {
      children: [{ id: "kid1", name: "Mia", chore_order: [] }],
      chores: [
        { id: "bins", name: "Take the bins out", points: 5, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", assignment_mode: "everyone" },
        { id: "bed", name: "Make bed", points: 2, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", assignment_mode: "everyone" },
      ],
      todays_completions: [], chore_availability: {}, today_day_of_week: "wednesday", points_icon: "mdi:star", boosts,
    } } },
    callService: async () => {},
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card._playSound = () => {};
  card._spawnConfetti = () => {};
  return card;
}

for (const design of DESIGNS) {
  test(`child: ${design} shows the live boost banner and the boosted chore`, () => {
    const { markup } = render(childCard({ design }).render());
    assert.ok(markup.includes(localize("child.boost_title_named", { multiplier: "2", name: "Guests at six" })));
    assert.match(markup, /tm-boost-clock/);
    assert.ok(markup.includes("×2"), "the chore carries the ×2 chip");
    assert.match(markup, /\+10|>10</, "boosted points are shown");
  });

  test(`child: ${design} shows nothing when no boost covers the child`, () => {
    const { markup } = render(childCard({ design, boosts: [liveBoost({ child_ids: ["someone-else"] })] }).render());
    assert.doesNotMatch(markup, /tm-care-boost|tm-boost-x|tm-boost-tag/);
  });
}

test("child: an upcoming boost is announced as the next one", () => {
  const { markup } = render(childCard({ boosts: [liveBoost({ starts_at: minutes(60), ends_at: minutes(120) })] }).render());
  assert.match(markup, /tm-care-boost-next/);
  assert.doesNotMatch(markup, /tm-boost-x/);
});

test("child: the takeover shows once, and Let's go dismisses it for good", () => {
  const card = childCard();
  const attrs = card.hass.states[ENTITY].attributes;
  card._maybeBoostTakeover(attrs);
  let out = render(card.render());
  assert.ok(out.markup.includes(localize("child.boost_takeover_title")));
  out.control(localize("child.boost_takeover_go")).click();
  card._maybeBoostTakeover(attrs);
  out = render(card.render());
  assert.ok(!out.markup.includes(localize("child.boost_takeover_title")));
});

test("child: the takeover can be switched off per card", () => {
  const card = childCard({ config: { show_boost_alert: false } });
  card._maybeBoostTakeover(card.hass.states[ENTITY].attributes);
  assert.ok(!render(card.render()).markup.includes(localize("child.boost_takeover_title")));
});

// ── kiosk card ────────────────────────────────────────────────────────────

function kiosk(boosts = [liveBoost({ chore_ids: [], chore_names: [] })], config = {}) {
  const Kiosk = loadCard("taskmate-kiosk-card.js", { window: designHelpers() }).get("taskmate-kiosk-card");
  const card = new Kiosk();
  card.setConfig({ entity: ENTITY, children: [{ child_id: "kid1" }], ambient_mode: "progress", ...config });
  card.hass = { locale: { language: "en" }, states: { [ENTITY]: { state: "ok", attributes: {
    children: [{ id: "kid1", name: "Mia", points: 10 }], chores: [], todays_completions: [], points_icon: "mdi:star", boosts,
  } } }, callService: async () => {} };
  return card;
}

test("kiosk: a live boost wakes the ambient screen and fills it until tapped", () => {
  const card = kiosk();
  card._ambient = true;
  card._screen = "picker";
  card._tick();
  assert.equal(card._ambient, false, "ambient mode is left");
  let out = render(card.render());
  assert.ok(out.markup.includes(localize("kiosk.boost_title")));
  out.control(localize("kiosk.boost_go")).click();
  card._tick();
  out = render(card.render());
  assert.ok(!out.markup.includes(localize("kiosk.boost_title")));
  assert.match(out.markup, /km-boost-strip/, "the countdown strip stays");
});

test("kiosk: boost_alert off keeps the strip but no takeover", () => {
  const card = kiosk(undefined, { show_boost_alert: false });
  card._tick();
  const { markup } = render(card.render());
  assert.ok(!markup.includes(localize("kiosk.boost_title")));
  assert.match(markup, /km-boost-strip/);
});

// ── panel ─────────────────────────────────────────────────────────────────

function panel(extra = {}) {
  const TaskMatePanel = loadCard("taskmate-panel.js", { window: designHelpers() }).get("taskmate-panel");
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => `${key}${Object.keys(params).length ? ":" + JSON.stringify(params) : ""}`;
  p._state = {
    children: [{ id: "kid1", name: "Malia" }, { id: "kid2", name: "Vaiha" }],
    chores: [{ id: "bins", name: "Bins" }, { id: "dish", name: "Dishwasher" }],
    boosts: [liveBoost({ chore_ids: ["bins"] }), liveBoost({ id: "rule:r1:2026-10-18", rule_id: "r1", starts_at: minutes(90), ends_at: minutes(150), name: "Sat" })],
    boost_rules: [{ id: "r1", name: "Sat", days: [5], start: "09:00", end: "11:00", multiplier: 2, chore_ids: [], child_ids: [], enabled: true }],
    boost_wake_candidates: { screens: [{ entity_id: "switch.kitchen_screen", name: "Kitchen screen" }], devices: [{ service: "mobile_app_wall", name: "Wall" }] },
    settings: { boost_wake_screens: ["switch.kitchen_screen"], boost_wake_devices: [] },
    ...extra,
  };
  return p;
}

test("panel: the Today boosts card lists live and upcoming with the right buttons", () => {
  const html = panel()._renderBoostsCard();
  assert.match(html, /data-act="boost-end" data-id="b1">panel\.boost_end_now/);
  assert.match(html, /data-act="boost-end" data-id="rule:r1:2026-10-18">panel\.boost_skip/);
  assert.match(html, /data-act="boost-open"/);
  assert.equal(panel({ boosts: [] })._renderBoostsCard(), "");
});

test("panel: Start a boost sends start_boost with the chosen chips", async () => {
  const p = panel();
  const calls = [];
  p._callService = async (service, data) => { calls.push({ service, data }); return { ok: true }; };
  p._render = () => {};
  p._fetchState = async () => {};
  p._showToast = () => {};
  p._closeDialog = () => {};
  p._openDialog = (d) => { p._dialog = d; };
  p._boostClick("boost-open", { dataset: {} });
  for (const [act, id] of [["boost-mult", "3"], ["boost-len", "30"], ["boost-chore", "dish"], ["boost-kid", "kid2"]]) p._boostClick(act, { dataset: { id } });
  p._dialog.data.name = "Tidy up";
  assert.match(p._renderBoostDialog(), /panel\.boost_preview_now/);
  await p._startBoostFromDialog();
  assert.deepEqual(plain(calls), [{ service: "start_boost", data: { multiplier: 3, minutes: 30, chore_ids: ["dish"], child_ids: ["kid2"], name: "Tidy up", notify: true } }]);
});

test("panel: settings offer stacking, the wake lists and the rules", () => {
  const html = panel()._renderBoostSettings({ boost_wake_screens: ["switch.kitchen_screen"], boost_wake_devices: [] });
  assert.match(html, /name="boost_stacking" value="highest" checked/);
  assert.match(html, /data-boost-screen="switch\.kitchen_screen" checked/);
  assert.match(html, /data-boost-device="mobile_app_wall" >/);
  assert.match(html, /data-act="boost-test-wake"/);
  assert.match(html, /data-act="boost-rule-edit" data-id="r1"/);
  assert.match(html, /data-act="boost-rule-add"/);
});

test("panel: a recurring boost is saved over the websocket", async () => {
  const p = panel();
  const sent = [];
  p._callWS = async (msg) => { sent.push(msg); return { ok: true, res: {} }; };
  p._render = () => {};
  p._fetchState = async () => {};
  p._showToast = () => {};
  p._closeDialog = () => {};
  p._openDialog = (d) => { p._dialog = d; };
  p._boostClick("boost-rule-add", { dataset: {} });
  p._boostClick("boost-day", { dataset: { id: "6" } });
  p._dialog.data.name = "Weekend";
  await p._saveBoostRule(p._dialog.data, true);
  assert.equal(sent[0].type, "taskmate/boosts/save_rule");
  assert.deepEqual(plain(sent[0].days), [5, 6]);
  assert.equal(sent[0].name, "Weekend");
});

test("panel: a failed rule save shows the error and keeps the dialog open", async () => {
  const p = panel();
  const toasts = [];
  let closed = false;
  p._callWS = async () => ({ ok: false, err: "Pick at least one day." });
  p._render = () => {};
  p._fetchState = async () => {};
  p._showToast = (kind, text) => toasts.push([kind, text]);
  p._closeDialog = () => { closed = true; };
  p._openDialog = (d) => { p._dialog = d; };
  p._boostClick("boost-rule-add", { dataset: {} });
  await p._saveBoostRule(p._dialog.data, true);
  assert.deepEqual(toasts, [["err", "Pick at least one day."]]);
  assert.equal(closed, false);
});

test("panel: test wake reports how many screens were woken", async () => {
  const p = panel();
  const toasts = [];
  p._callWS = async () => ({ ok: true, res: { sent: 3 } });
  p._showToast = (kind, text) => toasts.push([kind, text]);
  await p._boostTestWake();
  assert.deepEqual(toasts, [["ok", 'panel.boost_test_wake_sent:{"count":3}']]);
});
