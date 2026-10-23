const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// Screen-time bank on the child card (every design) and in the panel's
// Settings and reward dialog; bin-day chores in the panel's Settings.

const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const ENTITY = "sensor.taskmate_overview";
const plain = (v) => JSON.parse(JSON.stringify(v));

function childCard({ design = "classic", screen_time, config = {} } = {}) {
  const ChildCard = loadCard("taskmate-child-card.js").get("taskmate-child-card");
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design, ...config });
  card.hass = {
    states: { [ENTITY]: { state: "ok", attributes: {
      children: [{ id: "kid1", name: "Mia", chore_order: [], ...(screen_time ? { screen_time } : {}) }],
      chores: [{ id: "bed", name: "Make bed", points: 2, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", assignment_mode: "everyone" }],
      todays_completions: [], chore_availability: {}, today_day_of_week: "wednesday", points_icon: "mdi:star",
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
  test(`child: ${design} shows the screen-time balance`, () => {
    const { markup } = render(childCard({ design, screen_time: { minutes: 75, active: false, low: false } }).render());
    assert.match(markup, /tm-care-screen/);
    assert.ok(markup.includes(localize("child.screen_time_left", { time: localize("child.screen_time_hours", { h: 1, m: 15 }) })));
    assert.ok(markup.includes(localize("child.screen_time_hint")));
  });
}

test("child: a running device shows the live dot and the watching line", () => {
  const { markup } = render(childCard({ screen_time: { minutes: 8, active: true, low: true } }).render());
  assert.match(markup, /tm-care-screen low/);
  assert.match(markup, /tm-screen-live/);
  assert.ok(markup.includes(localize("child.screen_time_minutes", { m: 8 })));
  assert.ok(markup.includes(localize("child.screen_time_watching")));
});

test("child: at zero it says so and points at Rewards", () => {
  const { markup } = render(childCard({ screen_time: { minutes: 0, active: true, low: false } }).render());
  assert.match(markup, /tm-care-screen out/);
  assert.ok(markup.includes(localize("child.screen_time_out")));
  assert.ok(markup.includes(localize("child.screen_time_earn")));
  assert.doesNotMatch(markup, /tm-screen-live/);
});

test("child: nothing when the feature is off or hidden in the card options", () => {
  assert.doesNotMatch(render(childCard().render()).markup, /tm-care-screen/);
  const hidden = childCard({ screen_time: { minutes: 30 }, config: { show_screen_time: false } });
  assert.doesNotMatch(render(hidden.render()).markup, /tm-care-screen/);
});

// ── panel ───────────────────────────────────────────────────────────────

function panel(extra = {}) {
  const TaskMatePanel = loadCard("taskmate-panel.js").get("taskmate-panel");
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => `${key}${Object.keys(params).length ? ":" + JSON.stringify(params) : ""}`;
  p._state = {
    children: [{ id: "kid1", name: "Malia" }, { id: "kid2", name: "Vaiha" }, { id: "dad", name: "Dad", is_adult: true }],
    screen_time: { kid1: { minutes: 45, devices: ["switch.tv"], active: true, log: [] }, kid2: { minutes: 0, devices: [], active: false, log: [] } },
    settings: { screen_time_enabled: true, screen_time_devices: { kid1: ["switch.tv"] }, bin_day_calendars: ["calendar.bins"], bin_day_children: ["kid2"] },
    ...extra,
  };
  const sent = [];
  p._callWS = async (msg) => { sent.push(msg); return { ok: true, res: { collections: [{ date: "2026-10-21", summary: "Recycling", emoji: "♻️" }] } }; };
  p._fetchState = async () => {};
  p._render = () => {};
  p._showToast = (kind, msg) => sent.push({ toast: kind, msg });
  p._sent = sent;
  return p;
}

test("panel: screen-time settings show each child's balance, devices and the adjust buttons", () => {
  const p = panel();
  const html = p._renderScreenTimeSettings(p._state.settings);
  assert.match(html, /data-setting="screen_time_enabled" checked/);
  assert.match(html, /data-setting="screen_time_stop_at_zero" >/);
  assert.match(html, /panel\.screen_time_minutes:\{&quot;m&quot;:45\} · panel\.screen_time_watching/);
  assert.doesNotMatch(html, /Dad/);
  assert.match(html, /data-act="st-list-remove" data-field="_list:screen_time_devices:kid1" data-id="switch\.tv"/);
  assert.match(html, /data-ep-field="_list:screen_time_devices:kid2"/);
  assert.match(html, /panel\.screen_time_no_devices/);
  assert.match(html, /data-act="st-adjust" data-child="kid1" data-minutes="-15"/);
});

test("panel: adjusting and editing devices go over the websocket", async () => {
  const p = panel();
  await p._adjustScreenTime("kid1", 15);
  await p._editListSetting("_list:screen_time_devices:kid2", "media_player.xbox", true);
  await p._editListSetting("_list:screen_time_devices:kid1", "switch.tv", false);
  assert.deepEqual(plain(p._sent), [
    { type: "taskmate/screen_time/adjust", child_id: "kid1", minutes: 15 },
    { type: "taskmate/update_settings", screen_time_devices: { kid1: ["switch.tv"], kid2: ["media_player.xbox"] } },
    { type: "taskmate/update_settings", screen_time_devices: { kid1: [] } },
  ]);
});

test("panel: a failed adjust shows the error", async () => {
  const p = panel();
  p._callWS = async () => ({ ok: false, err: "Child nope not found" });
  await p._adjustScreenTime("nope", 15);
  assert.deepEqual(plain(p._sent), [{ toast: "err", msg: "Child nope not found" }]);
});

test("panel: bin-day settings list calendars, children (no adults) and the preview", async () => {
  const p = panel();
  let html = p._renderBinDaySettings(p._state.settings);
  assert.match(html, /data-act="st-list-remove" data-field="_list:bin_day_calendars" data-id="calendar\.bins"/);
  assert.match(html, /data-bin-kid="kid2"/);
  assert.match(html, /tm-chip-btn tm-chip-on" aria-pressed="true" data-act="bin-kid" data-bin-kid="kid2"/);
  assert.doesNotMatch(html, /data-bin-kid="dad"/);
  assert.match(html, /data-setting="bin_day_put_out_time" value="18:00"/);
  assert.match(html, /<option value="first_come" selected>/);
  await p._loadBinPreview();
  html = p._renderBinDaySettings(p._state.settings);
  assert.match(html, /♻️ <b>[^<]+<\/b> · Recycling/);
  await p._editListSetting("_list:bin_day_calendars", "calendar.garden", true);
  assert.deepEqual(plain(p._sent.at(-1)), { type: "taskmate/update_settings", bin_day_calendars: ["calendar.bins", "calendar.garden"] });
});

test("panel: the reward dialog offers screen minutes once the bank is on", () => {
  const p = panel();
  assert.match(p._renderRewardScreenTime({ screen_minutes: 30 }), /data-field="screen_minutes"\s+value="30"/);
  p._state.settings = {};
  assert.doesNotMatch(p._renderRewardScreenTime({ screen_minutes: 0 }), /screen_minutes/);
  assert.match(p._renderRewardScreenTime({ screen_minutes: 20 }), /data-field="screen_minutes"/, "an existing value stays editable");
});
