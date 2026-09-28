// Surprise inspections (#981): the child card's banner, row tag, redo note and
// pass celebration in every design; the activity card's entries; the admin
// panel's queue rows, magnifier, dialogs and settings.

const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const ENTITY = "sensor.taskmate_overview";
const WWW = path.join(__dirname, "../../custom_components/taskmate/www");
const plain = (value) => JSON.parse(JSON.stringify(value));

// ── child card ────────────────────────────────────────────────────────────

const ChildCard = loadCard("taskmate-child-card.js").get("taskmate-child-card");
const UNTIL = new Date(Date.now() + 90 * 60000).toISOString();

function childCard({ design = "classic", inspections, completions = [] } = {}) {
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design });
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Vaiha", chore_order: [], ...(inspections ? { inspections } : {}) }],
          chores: [
            {
              id: "room",
              name: "Tidy bedroom",
              points: 3,
              time_category: "anytime",
              assigned_to: [],
              due_days: [],
              schedule_mode: "specific_days",
              assignment_mode: "everyone",
            },
          ],
          todays_completions: completions,
          chore_availability: {},
          today_day_of_week: "wednesday",
          points_icon: "mdi:star",
          points_name: "Stars",
        },
      },
    },
    callService: async () => {},
  };
  card._loading = {};
  card._optimisticCompletions = {};
  return card;
}

const OPEN = { id: "i1", chore_id: "room", status: "open", bonus: 10, until: UNTIL, name: "Tidy bedroom" };

for (const design of DESIGNS) {
  test(`child card: ${design} shows "Inspection coming" with the bonus and tags the row`, () => {
    const { markup } = render(childCard({ design, inspections: [OPEN] }).render());
    assert.ok(markup.includes(localize("inspection.coming_title")), "banner title");
    assert.ok(/\+10 Stars/.test(markup), "bonus on offer");
    assert.ok(markup.includes("tm-insp-banner") && markup.includes("is-open"));
    assert.ok(markup.includes(localize("inspection.tag_open")), "row tag");
    assert.ok(markup.includes("tm-insp-row-open"), "dashed row");
  });

  test(`child card: ${design} shows a pass, a redo with the parent's note, and a gentle fail`, () => {
    const passed = render(
      childCard({ design, inspections: [{ ...OPEN, status: "passed", note: "Brilliant" }] }).render(),
    ).markup;
    assert.ok(passed.includes(localize("inspection.passed_title", { bonus: 10, points_name: "Stars" })));
    assert.ok(passed.includes(localize("inspection.passed_sub_note", { name: "Tidy bedroom", note: "Brilliant" })));
    assert.ok(passed.includes(localize("inspection.tag_passed", { bonus: 10 })));

    const redo = render(
      childCard({ design, inspections: [{ ...OPEN, status: "redo", points: 3, note: "Clothes on the floor" }] }).render(),
    ).markup;
    assert.ok(redo.includes(localize("inspection.redo_title", { name: "Tidy bedroom" })));
    assert.ok(redo.includes(localize("inspection.redo_sub", { points: 3, points_name: "Stars" })));
    assert.ok(redo.includes("Clothes on the floor"), "the note is under the chore");
    assert.ok(redo.includes(localize("inspection.tag_redo")));

    const nope = render(childCard({ design, inspections: [{ ...OPEN, status: "failed" }] }).render()).markup;
    assert.ok(nope.includes(localize("inspection.nope_title")));
    assert.ok(!nope.includes("tm-insp-row-open"));
  });

  test(`child card: ${design} draws nothing without an inspection`, () => {
    const { markup } = render(childCard({ design }).render());
    assert.ok(!markup.includes("tm-insp-banner") && !markup.includes("tm-insp-tag"));
  });

  test(`child card: ${design} plays the pass celebration once, with the note`, () => {
    const card = childCard({ design, inspections: [{ ...OPEN, status: "passed", note: "Brilliant" }] });
    card._maybeInspectionCelebration(card.hass.states[ENTITY].attributes);
    assert.equal(card._inspCelebration && card._inspCelebration.id, "i1");
    const { markup, control } = render(card.render());
    assert.ok(markup.includes(localize("inspection.celebrate_title")) && markup.includes("“Brilliant”"));
    control(localize("inspection.celebrate_ok")).click();
    assert.equal(card._inspCelebration, null);
  });
}

test("child card: every inspection helper is called from both render paths", () => {
  const src = readFileSync(path.join(WWW, "taskmate-child-card.js"), "utf8");
  const classic = src.slice(src.indexOf("  render() {"), src.indexOf("  _renderDesigned(design) {"));
  const designed = src.slice(src.indexOf("  _renderDesigned(design) {"), src.indexOf("  _renderSwappable("));
  const classicRow = src.slice(src.indexOf("  _renderChoreCard(chore, child"), src.indexOf("  _renderCelebration("));
  for (const helper of ["_renderInspectionBanners(", "_renderInspectionCelebration("]) {
    assert.ok(classic.includes(helper), `classic ${helper}`);
    assert.ok(designed.includes(helper), `designed ${helper}`);
  }
  for (const helper of ["_renderInspectionTag(", "_renderInspectionNote(", "_inspectionRowClass("]) {
    assert.ok(classicRow.includes(helper), `classic row ${helper}`);
    assert.ok(designed.includes(helper), `designed rows ${helper}`);
  }
  assert.equal((designed.match(/_inspectionRowClass\(/g) || []).length, 3, "playroom, console and cleanpro rows");
  // The celebration is triggered from updated(), which runs for every design.
  const updated = src.slice(src.indexOf("  updated(changedProperties) {"), src.indexOf("  _stopTimerTick() {"));
  assert.ok(updated.includes("this._maybeInspectionCelebration(attrs)"));
});

// ── activity card ────────────────────────────────────────────────────────

const ActivityCard = loadCard("taskmate-activity-card.js").get("taskmate-activity-card");

function activityCard() {
  const card = new ActivityCard();
  card.hass = { states: {} };
  card.config = { entity: ENTITY };
  card._loading = {};
  return card;
}

test("activity card: inspection steps read the same in every design", () => {
  const card = activityCard();
  for (const [type, key] of [
    ["inspection_started", "activity.inspection_started"],
    ["inspection_failed", "activity.inspection_failed"],
    ["inspection_redo", "activity.inspection_redo"],
  ]) {
    const item = { type, child_id: "kid1", chore_name: "Tidy bedroom", note: "Clothes", completed_at: "2026-09-28T10:00:00Z" };
    const classic = render(card._renderItem(item, { kid1: "Vaiha" }, "mdi:star", {})).markup;
    assert.ok(classic.includes(localize(key)) && classic.includes("Tidy bedroom"), `${type} classic`);
    assert.ok(classic.includes("“Clothes”"));
    const d = card._describeEvent(item, { kid1: "Vaiha" }, "mdi:star", {});
    assert.ok(render(d.text).markup.includes(localize(key)), `${type} designed`);
    assert.ok(d.plain.includes("Tidy bedroom"));
    assert.equal(d.undo, null);
    assert.equal(card._eventBucket(item), "chores");
  }
});

test("activity card: the pass bonus is a translated, undoable bonus entry", () => {
  const card = activityCard();
  const item = {
    type: "points_added",
    points: 10,
    reason: "Inspection passed: Tidy bedroom",
    child_id: "kid1",
    transaction_id: "t1",
    completed_at: "2026-09-28T10:00:00Z",
  };
  assert.equal(card._classifyItem(item), "bonus");
  assert.equal(card._translateReason(item.reason), localize("activity.reason_inspection_passed", { name: "Tidy bedroom" }));
  const classic = render(card._renderItem(item, { kid1: "Vaiha" }, "mdi:star", {})).markup;
  assert.ok(classic.includes("mdi:magnify-scan"));
  const d = card._describeEvent(item, { kid1: "Vaiha" }, "mdi:star", {});
  assert.equal(d.emoji, "🔍");
  assert.ok(d.undo && d.undo.id === "t1", "undoable like any bonus");
});

// ── admin panel ──────────────────────────────────────────────────────────

const TaskMatePanel = loadCard("taskmate-panel.js").get("taskmate-panel");

function panel(extra = {}) {
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => [key, ...Object.values(params)].join(":");
  p._timeAgo = () => "just now";
  p._state = {
    children: [{ id: "kid1", name: "Vaiha <b>" }],
    chores: [{ id: "room", name: "Tidy bedroom" }],
    rewards: [],
    completions: [
      { id: "c1", chore_id: "room", child_id: "kid1", approved: true, approved_at: "2026-09-28T14:10:00Z", points_awarded: 3 },
      { id: "c2", chore_id: "room", child_id: "kid1", approved: true, approved_at: "2026-09-28T08:05:00Z", points_awarded: 3 },
    ],
    pending_completions: [],
    pending_reward_claims: [],
    swap_requests: [],
    wishes: [],
    points_transactions: [],
    inspections: [],
    inspectable_completions: ["c1"],
    settings: { points_name: "Stars", inspection_bonus: 10, inspection_window: "2h" },
    ...extra,
  };
  p._render = () => {};
  p._showToast = (kind, text) => (p.toast = [kind, text]);
  p._fetchState = async () => {};
  p.calls = [];
  p._callWS = async (msg) => {
    p.calls.push(msg);
    return { ok: true };
  };
  return p;
}

const OPEN_RECORD = {
  id: "i1",
  completion_id: "c2",
  child_id: "kid1",
  chore_id: "room",
  chore_name: "Tidy bedroom",
  status: "open",
  bonus: 10,
  tell_child: true,
  until: new Date(Date.now() + 118 * 60000).toISOString(),
  points: 3,
  can_redo: true,
};

test("panel: the magnifier is on inspectable approved rows only, and a tag on inspected ones", () => {
  const p = panel({ inspections: [OPEN_RECORD] });
  const html = p._timelineHtml(p._activityEvents());
  assert.ok(html.includes('data-act="insp-flag" data-id="c1"'));
  assert.ok(!html.includes('data-id="c2"') || !html.includes('data-act="insp-flag" data-id="c2"'));
  assert.ok(html.includes("panel.insp_tag_open"), "the inspected row shows its countdown tag");
});

test("panel: an open inspection sits in Needs you with pass / fail / cancel", () => {
  const p = panel({ inspections: [OPEN_RECORD] });
  assert.equal(p._needsYouCount(), 1);
  const queue = p._approvalQueue({ wishes: true });
  assert.equal(queue.count, 1);
  assert.ok(queue.html.includes("panel.insp_needs_line:Vaiha &lt;b&gt;:Tidy bedroom"), "names are escaped");
  for (const act of ["insp-pass", "insp-fail", "insp-cancel"]) assert.ok(queue.html.includes(`data-act="${act}" data-id="i1"`));
});

test("panel: start dialog sends the window, bonus and secret switch", async () => {
  const p = panel();
  p._onInspectionAction("insp-flag", { dataset: { id: "c1" } });
  assert.equal(p._dialog.kind, "insp-start");
  const html = p._renderInspectionStartDialog();
  assert.ok(html.includes('data-act="insp-window" data-window="bed"') && html.includes('data-field="bonus"'));
  p._onInspectionAction("insp-window", { dataset: { window: "4h" } });
  p._onInspectionAction("insp-bonus", { dataset: { d: "5" } });
  p._dialog.data.tell = false;
  p._onInspectionAction("insp-start-save", { dataset: {} });
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(plain(p.calls), [
    { type: "taskmate/inspection/start", completion_id: "c1", bonus: 15, window: "4h", tell_child: false },
  ]);
  assert.equal(p._dialog, null);
});

test("panel: pass and fail dialogs send what the parent chose", async () => {
  const p = panel({ inspections: [OPEN_RECORD], settings: { points_name: "Stars", inspection_fail_mode: "redo" } });
  p._onInspectionAction("insp-pass", { dataset: { id: "i1" } });
  assert.ok(p._renderInspectionPassDialog().includes('data-act="insp-pass-save"'));
  p._dialog.data.note = "  Brilliant ";
  p._onInspectionAction("insp-pass-save", { dataset: {} });
  await new Promise((r) => setImmediate(r));
  p._onInspectionAction("insp-fail", { dataset: { id: "i1" } });
  assert.equal(p._dialog.data.mode, "redo", "the Settings default");
  assert.ok(p._renderInspectionFailDialog().includes("panel.insp_fail_send_back"));
  p._onInspectionAction("insp-fail-mode", { dataset: { mode: "note" } });
  p._dialog.data.note = "Clothes";
  p._onInspectionAction("insp-fail-save", { dataset: {} });
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(plain(p.calls), [
    { type: "taskmate/inspection/pass", inspection_id: "i1", bonus: 10, note: "Brilliant" },
    { type: "taskmate/inspection/fail", inspection_id: "i1", redo: false, note: "Clothes" },
  ]);
});

test("panel: redo can't be chosen when the chore can't be sent back", () => {
  const p = panel({ inspections: [{ ...OPEN_RECORD, can_redo: false }], settings: { inspection_fail_mode: "redo" } });
  p._onInspectionAction("insp-fail", { dataset: { id: "i1" } });
  assert.equal(p._dialog.data.mode, "note");
  p._onInspectionAction("insp-fail-mode", { dataset: { mode: "redo" } });
  assert.equal(p._dialog.data.mode, "note");
  assert.ok(p._renderInspectionFailDialog().includes("panel.insp_fail_redo_unavailable"));
});

test("panel: settings section carries every inspection setting", () => {
  const p = panel();
  const html = p._renderInspectionsSection();
  for (const key of [
    "inspections_enabled",
    "inspection_bonus",
    "inspection_window",
    "inspection_bedtime",
    "inspection_fail_mode",
    "inspection_tell_child",
    "inspection_pick_enabled",
    "inspection_pick_time",
    "inspection_pick_chance",
  ]) {
    assert.ok(html.includes(`data-setting="${key}"`), key);
  }
  assert.ok(html.includes('data-insp-kid="kid1"'));
  const settings = readFileSync(path.join(WWW, "taskmate-panel.js"), "utf8");
  assert.ok(settings.includes("${this._renderInspectionsSection()}"), "wired into the Settings tab");
  assert.ok(settings.includes("payload.inspection_pick_children"), "the children chips are saved");
});
