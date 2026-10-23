const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// Per-chore streaks, the tomorrow preview, child-chosen reminders, praise
// notes, penalty warnings and sibling checks on the child card (every design),
// plus the panel, approvals, activity and heatmap cards.

const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const ENTITY = "sensor.taskmate_overview";
const plain = (v) => JSON.parse(JSON.stringify(v));

const CHORES = [
  { id: "bed", name: "Make bed", points: 2, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", assignment_mode: "everyone" },
  { id: "hoover", name: "Hoover the stairs", points: 5, time_category: "anytime", assigned_to: [], due_days: ["saturday"], schedule_mode: "specific_days", assignment_mode: "everyone" },
];

function childCard({ design = "classic", child = {}, attrs = {}, config = {} } = {}) {
  const ChildCard = loadCard("taskmate-child-card.js").get("taskmate-child-card");
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design, ...config });
  const calls = [];
  card.hass = {
    states: { [ENTITY]: { state: "ok", attributes: {
      children: [{ id: "kid1", name: "Vaiha", chore_order: [], ...child }],
      chores: CHORES,
      todays_completions: [], chore_availability: {}, today_day_of_week: "wednesday", points_icon: "mdi:star", points_name: "Stars",
      ...attrs,
    } } },
    callService: async (domain, service, data) => { calls.push({ domain, service, data }); },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card._playSound = () => {};
  card._spawnConfetti = () => {};
  card._calls = calls;
  return card;
}

const REMINDERS = { chore_reminders: { earliest: "15:00", latest: "20:00" } };

for (const design of DESIGNS) {
  test(`child: ${design} shows a chore's streak and its reminder time`, () => {
    const card = childCard({ design, child: { chore_streaks: { bed: 12 }, reminders: { bed: "17:30" } }, attrs: REMINDERS });
    const { markup } = render(card.render());
    assert.ok(markup.includes(`🔥 ${localize("child.chore_streak_days", { count: 12 })}`));
    assert.ok(markup.includes("🔔 17:30"));
  });

  test(`child: ${design} shows praise, the penalty warning and sibling checks`, async () => {
    const card = childCard({
      design,
      child: {
        praise: [{ chore_name: "Clean bathroom", note: "Great job on the bathroom!", by: "Dad" }, { chore_name: "Bins", note: "Thanks" }],
        penalty_warnings: [{ penalty_id: "p1", name: "Shouting at the table", points: 10 }],
        sibling_checks: [{ completion_id: "c9", child_id: "kid2", child_name: "Malia", chore_name: "Tidy room", completed_at: "2026-10-23T16:00:00Z", photo: true }],
      },
      attrs: { sibling_check_bonus: 1 },
    });
    const view = render(card.render());
    assert.ok(view.markup.includes("Dad:</b> Great job on the bathroom!"));
    assert.ok(view.markup.includes(`${localize("child.praise_grown_up")}:</b> Thanks`));
    assert.ok(view.markup.includes(localize("child.penalty_warning_title", { name: "Shouting at the table" })));
    assert.ok(view.markup.includes(localize("child.penalty_warning_body", { points: 10, points_name: "Stars" })));
    assert.ok(view.markup.includes(localize("child.sibling_check_title", { name: "Malia" })));
    assert.ok(view.markup.includes("Tidy room") && view.markup.includes("📷"));
    await view.controls.find((c) => c.text === localize("child.sibling_check_done_bonus", { bonus: 1 })).click();
    card._loading = {};
    await view.controls.find((c) => c.text === localize("child.sibling_check_not_yet")).click();
    assert.deepEqual(plain(card._calls), [
      { domain: "taskmate", service: "sibling_check", data: { child_id: "kid1", completion_id: "c9", verdict: "done" } },
      { domain: "taskmate", service: "sibling_check", data: { child_id: "kid1", completion_id: "c9", verdict: "not_yet" } },
    ]);
  });

  test(`child: ${design} has Today / Tomorrow tabs with read-only tomorrow rows`, () => {
    const card = childCard({ design, child: { tomorrow: ["hoover"] } });
    let view = render(card.render());
    assert.ok(view.markup.includes(localize("child.tab_today")));
    const tab = view.controls.find((c) => c.attrs.includes("tm-day-tab") && !c.attrs.includes(" on"));
    tab.click();
    view = render(card.render());
    assert.match(view.markup, /tm-tomorrow-row/);
    assert.ok(view.markup.includes("Hoover the stairs") && view.markup.includes("mdi:lock-outline"));
    assert.ok(view.markup.includes(localize("child.tomorrow_locked")));
    assert.ok(!view.controls.some((c) => c.attrs.includes("tm-tomorrow-row")), "tomorrow rows can't be tapped");
    assert.ok(!view.markup.includes("Make bed"), "today's list is swapped out");
  });
}

test("child: no tabs when nothing is due tomorrow, and no tags when nothing is set", () => {
  const { markup } = render(childCard().render());
  assert.doesNotMatch(markup, /tm-day-tabs|tm-streak-tag|tm-remind-btn|tm-care-praise|tm-care-warning|tm-care-check/);
});

test("child: a one-day streak gets no tag; reminders hide when done or switched off in the card", () => {
  let { markup } = render(childCard({ child: { chore_streaks: { bed: 1 } } }).render());
  assert.doesNotMatch(markup, /tm-streak-tag/);
  ({ markup } = render(childCard({ attrs: REMINDERS, config: { show_reminders: false } }).render()));
  assert.doesNotMatch(markup, /tm-remind-btn/);
  ({ markup } = render(childCard({ attrs: { ...REMINDERS, todays_completions: [{ chore_id: "bed", child_id: "kid1", approved: true, completed_at: new Date().toISOString() }] } }).render()));
  assert.doesNotMatch(markup, /tm-remind-btn/, "a chore done today needs no reminder");
});

test("child: the reminder sheet offers presets inside the bounds and saves through the service", async () => {
  const card = childCard({ attrs: REMINDERS });
  let view = render(card.render());
  await view.controls.find((c) => c.attrs.includes("tm-remind-btn")).click();
  view = render(card.render());
  assert.ok(view.markup.includes(localize("child.reminder_title", { chore: "Make bed" })));
  assert.ok(view.markup.includes(localize("child.reminder_hint", { earliest: "15:00", latest: "20:00" })));
  const presets = view.controls.filter((c) => c.attrs.includes("tm-goal-chip")).map((c) => c.text);
  assert.deepEqual(plain(presets), ["15:00", "16:00", "17:00", "18:00", "19:00", "20:00"]);
  await view.controls.find((c) => c.text === "18:00").click();
  assert.deepEqual(plain(card._calls), [{ domain: "taskmate", service: "set_chore_reminder", data: { child_id: "kid1", chore_id: "bed", time: "18:00" } }]);
  assert.equal(card._reminderSheet, null);
});

test("child: a long reminder window steps every two hours", () => {
  const card = childCard();
  assert.deepEqual(plain(card._reminderPresets({ earliest: "08:30", latest: "20:00" })), ["09:00", "11:00", "13:00", "15:00", "17:00", "19:00"]);
});

test("child: a set reminder can be cleared", async () => {
  const card = childCard({ child: { reminders: { bed: "17:30" } }, attrs: REMINDERS });
  card._openReminderSheet(CHORES[0], card.hass.states[ENTITY].attributes.children[0]);
  const view = render(card.render());
  await view.controls.find((c) => c.text === localize("child.reminder_clear")).click();
  assert.equal(card._calls[0].data.time, "");
});

// ── panel ───────────────────────────────────────────────────────────────

function panel(extra = {}) {
  const TaskMatePanel = loadCard("taskmate-panel.js").get("taskmate-panel");
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => `${key}${Object.keys(params).length ? ":" + JSON.stringify(params) : ""}`;
  p._state = {
    children: [{ id: "kid1", name: "Vaiha" }, { id: "kid2", name: "Malia" }, { id: "dad", name: "Dad", is_adult: true }],
    chores: [{ id: "bath", name: "Clean bathroom", points: 8 }],
    pending_completions: [{ id: "c1", chore_id: "bath", child_id: "kid2", completed_at: "2026-10-23T10:00:00Z", checked_by: "kid1", check_note: "Towels on the floor" }],
    settings: { sibling_check_enabled: true, sibling_check_pairs: { kid1: ["kid2"] }, sibling_check_bonus: 2, chore_reminders_enabled: true },
    ...extra,
  };
  const sent = [];
  p._callWS = async (msg) => { sent.push(msg); return { ok: true, res: { warning: true } }; };
  p._fetchState = async () => {};
  p._render = () => {};
  p._showToast = (kind, msg) => sent.push({ toast: kind, msg });
  p._sent = sent;
  return p;
}

test("panel: approvals show a sibling's not-yet note and send a praise note with the approval", async () => {
  const p = panel();
  let html = p._approvalQueue().html ?? p._approvalQueue();
  html = typeof html === "string" ? html : JSON.stringify(html);
  assert.match(html, /panel\.sibling_check_not_yet_note:\{&quot;name&quot;:&quot;Vaiha&quot;\}/);
  assert.match(html, /Towels on the floor/);
  assert.match(html, /data-act="praise-toggle" data-id="c1"/);
  p._praiseOpen = new Set(["c1"]);
  html = p._praiseRow("c1");
  assert.match(html, /data-praise-for="c1"/);
  assert.match(html, /data-act="praise-chip" data-id="c1" data-text="praise\.chip_well_done"/);
  p._praiseText = { c1: "  Great job on the bathroom!  " };
  await p._doApprove("chore", "c1");
  assert.deepEqual(plain(p._sent[0]), { type: "taskmate/approve_chore", completion_id: "c1", note: "Great job on the bathroom!" });
  assert.equal(p._praiseText.c1, undefined);
});

test("panel: approving without a note sends none", async () => {
  const p = panel();
  await p._doApprove("chore", "c1");
  assert.deepEqual(plain(p._sent[0]), { type: "taskmate/approve_chore", completion_id: "c1" });
});

test("panel: the penalty dialog carries warn-first and the reset period", async () => {
  const p = panel();
  p._openDialog = (d) => { p._dialog = d; };
  p._syncIconPickers = () => {};
  p._closeDialog = () => {};
  p._openPenBonDialog("penalty", null);
  assert.equal(p._dialog.data.warn_first, false);
  assert.equal(p._dialog.data.warning_reset, "daily");
  p._dialog.data = { ...p._dialog.data, name: "Shouting", points: 10, warn_first: true, warning_reset: "weekly" };
  const markup = p._renderPenBonDialog("penalty");
  assert.match(markup, /panel\.penalty_warn_first/);
  assert.match(markup, /panel\.penalty_warn_reset_weekly/);
  await p._doSavePenBon("penalty");
  assert.equal(p._sent[0].warn_first, true);
  assert.equal(p._sent[0].warning_reset, "weekly");
});

test("panel: applying a warn-first penalty the first time says it was a warning", async () => {
  const p = panel();
  p._closeDialog = () => {};
  await p._doApplyPenBon("penalty", "p1", "kid1");
  assert.deepEqual(plain(p._sent.at(-1)), { toast: "ok", msg: "panel.toast_penalty_warning" });
});

test("panel: sibling-check settings list each checker with the other children (no adults)", () => {
  const p = panel();
  const html = p._renderSiblingCheckSettings(p._state.settings);
  assert.match(html, /data-setting="sibling_check_enabled" checked/);
  assert.match(html, /data-setting="sibling_check_bonus"[^>]*value="2"/);
  assert.match(html, /tm-chip-on" aria-pressed="true" data-act="check-pair" data-check-pair="kid1:kid2"/);
  assert.match(html, /aria-pressed="false" data-act="check-pair" data-check-pair="kid2:kid1"/);
  assert.doesNotMatch(html, /data-check-pair="[^"]*dad/);
  assert.doesNotMatch(html, /data-check-pair="kid1:kid1"/);
});

test("panel: reminder settings carry the bounds", () => {
  const p = panel();
  const html = p._renderChoreReminderSettings({ chore_reminders_enabled: true, chore_reminders_latest: "19:30" });
  assert.match(html, /data-setting="chore_reminders_enabled" checked/);
  assert.match(html, /data-setting="chore_reminders_earliest" value="15:00"/);
  assert.match(html, /data-setting="chore_reminders_latest" value="19:30"/);
});

test("panel: Insights has a Calendar view drawn from the heatmap report", async () => {
  const p = panel();
  p._insightView = "calendar";
  p._hass = { locale: { language: "en" } };
  p._ltrNums = (s) => s;
  p._ratingOn = () => false;
  p._callWS = async (msg) => {
    p._sent.push(msg);
    return { ok: true, res: { days: 7, start: "2026-10-17", end: "2026-10-23", children: [
      { id: "kid1", name: "Vaiha", counts: [0, 1, 2, 0, 4, 1, 3], total: 11, active_days: 5, best: 4 },
      { id: "kid2", name: "Malia", counts: [0, 0, 0, 0, 0, 0, 0], total: 0, active_days: 0, best: 0 },
    ] } };
  };
  let html = p._renderInsightsTab();
  assert.match(html, /data-act="insights-view" data-id="calendar"/);
  await new Promise((r) => setTimeout(r, 0));
  assert.deepEqual(plain(p._sent[0]), { type: "taskmate/reports/heatmap", days: 42 });
  html = p._renderInsightsTab();
  assert.match(html, /tm-heat-grid/);
  assert.equal((html.match(/tm-heat-l4"/g) || []).length, 2, "the busiest day, plus the legend");
  assert.match(html, /panel\.insights_calendar_cell_one/);
  // 17 October 2026 is a Saturday: five blanks before it in a Monday-first week.
  assert.equal((html.match(/tm-heat-pad/g) || []).length, 5 * 2);
});

// ── approvals card ──────────────────────────────────────────────────────

test("approvals card: the review sheet offers praise chips and sends the note", async () => {
  const ApprovalsCard = loadCard("taskmate-approvals-card.js").get("taskmate-approvals-card");
  const card = new ApprovalsCard();
  card.config = { entity: "sensor.taskmate_pending_approvals" };
  const calls = [];
  card.hass = { states: {}, callService: async (domain, service, data) => calls.push({ domain, service, data }) };
  card._loading = {};
  card._ratings = {};
  card.updateComplete = Promise.resolve();
  const inputs = { "#tm-review-points": { value: "8", focus() {}, select() {} }, "#tm-review-praise": { value: "" } };
  card.renderRoot = { querySelector: (sel) => inputs[sel] || null };
  card._openReview({ completion_id: "c1", chore_name: "Clean bathroom", child_name: "Vaiha", points: 8 });
  const view = render(card._renderReview());
  assert.ok(view.markup.includes(localize("praise.label")));
  await view.controls.find((c) => c.text === localize("praise.chip_well_done")).click();
  assert.equal(inputs["#tm-review-praise"].value, localize("praise.chip_well_done"));
  await card._confirmReview();
  assert.deepEqual(plain(calls[0].data), { completion_id: "c1", points: 8, note: localize("praise.chip_well_done") });
});

// ── activity card ───────────────────────────────────────────────────────

test("activity card: sibling checks read the same in every design", () => {
  const ActivityCard = loadCard("taskmate-activity-card.js").get("taskmate-activity-card");
  const card = new ActivityCard();
  card.hass = { states: {} };
  card.config = { entity: ENTITY };
  card._loading = {};
  for (const [verdict, key] of [["done", "activity.sibling_check_done"], ["not_yet", "activity.sibling_check_not_yet"]]) {
    const item = { type: "sibling_check", verdict, child_id: "kid1", checked_child_name: "Malia", chore_name: "Tidy room", completed_at: "2026-10-23T10:00:00Z" };
    const expected = localize(key, { name: "Malia" });
    const classic = render(card._renderItem(item, { kid1: "Vaiha" }, "mdi:star", {})).markup;
    assert.ok(classic.includes(expected) && classic.includes("Tidy room") && classic.includes("mdi:eye-check-outline"));
    const d = card._describeEvent(item, { kid1: "Vaiha" }, "mdi:star", {});
    assert.ok(render(d.text).markup.includes(expected));
    assert.equal(d.emoji, "👀");
    assert.equal(card._classifyItem(item), verdict === "done" ? "approved" : "pending");
  }
  assert.equal(card._translateReason("Sibling check: Tidy room"), localize("activity.reason_sibling_check", { name: "Tidy room" }));
});

// ── heatmap card ────────────────────────────────────────────────────────

function heatmapCard(design = "classic", config = {}) {
  const { get, window } = loadCard("taskmate-heatmap-card.js");
  const Card = get("taskmate-heatmap-card");
  const card = new Card();
  card.setConfig({ entity: ENTITY, card_design: design, ...config });
  const counts = Array.from({ length: 42 }, (_, i) => (i % 7 === 0 ? 4 : i % 3));
  card.hass = { locale: { language: "en" }, states: { [ENTITY]: { state: "2", attributes: {
    children: [{ id: "kid1", name: "Malia" }, { id: "kid2", name: "Vaiha" }],
    completion_heatmap: { end: "2026-10-23", children: { kid1: counts } },
  } } } };
  return { card, window };
}

for (const design of DESIGNS) {
  test(`heatmap card: ${design} draws a six-week grid per child`, () => {
    const { card } = heatmapCard(design);
    const { markup } = render(card.render());
    assert.ok(markup.includes("Malia") && markup.includes("Vaiha"));
    assert.equal((markup.match(/<span class="hm-wd">/g) || []).length, 14, "weekday header per child");
    assert.match(markup, /class="l4 /);
    assert.ok(markup.includes(localize("heatmap.less")) && markup.includes(localize("heatmap.more")));
    assert.ok(markup.includes(localize("heatmap.default_title")));
  });
}

test("heatmap card: one child with child_id, and its card is registered with an editor", () => {
  const { card, window } = heatmapCard("classic", { child_id: "kid2" });
  const { markup } = render(card.render());
  assert.ok(markup.includes("Vaiha") && !markup.includes("Malia"));
  assert.ok(markup.includes(localize("heatmap.summary", { total: 0, active: 0, days: 42 })));
  assert.ok(window.customCards.some((c) => c.type === "taskmate-heatmap-card"));
  assert.ok(card.constructor.getConfigElement);
});

// Classic sets data-tm-design="classic" too but defines no --tmd-* tokens, so a
// bare :host([data-tm-design]) override blanks the classic look (the Today /
// Tomorrow switch and the heatmap's empty squares went transparent).
test("design overrides that read --tmd-* tokens skip the classic design", () => {
  const fs = require("node:fs");
  const path = require("node:path");
  for (const file of ["taskmate-child-card.js", "taskmate-heatmap-card.js"]) {
    const src = fs.readFileSync(path.join(__dirname, "../../custom_components/taskmate/www", file), "utf8");
    const bare = src.split("\n").filter(l => /:host\(\[data-tm-design\]\)[^{]*\{[^}]*var\(--tmd-/.test(l));
    assert.deepEqual(bare, [], `${file}: ${bare.join("\n")}`);
  }
});

// An empty day was a fixed light grey, glaring on a dark Home Assistant theme.
test("heatmap card: an empty day follows the theme's background", () => {
  const src = require("node:fs").readFileSync(require("node:path").join(__dirname, "../../custom_components/taskmate/www/taskmate-heatmap-card.js"), "utf8");
  assert.match(src, /\.hm-grid i, \.hm-legend i \{[^}]*background: var\(--hm-0, var\(--secondary-background-color/);
});
