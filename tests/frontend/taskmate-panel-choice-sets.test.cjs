"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

const { get } = loadCard("taskmate-panel.js");
const TaskMatePanel = get("taskmate-panel");

// Choice sets (#1259) in the admin panel: the Earn › Choice sets editor, and
// missed sets / mandatory chores on the Today page per miss_review_location.

const MISSES = [
  { id: "m1", chore_id: "", set_id: "s1", chore_name: "Your part", child_id: "kid1", due_date: "2026-04-19", penalty_points: 5, set_done: 1, set_min: 2 },
  { id: "m2", chore_id: "bed", child_id: "kid2", chore_name: "Make bed", due_date: "2026-04-20", penalty_points: 0 },
];

function panel(settings = {}, extra = {}) {
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => `${key}${Object.keys(params).length ? `(${Object.values(params).join(",")})` : ""}`;
  p._timeAgo = () => "just now";
  p._fmtIsoDate = (iso) => iso;
  p._activeTab = "today";
  p._filter = "";
  p._state = {
    children: [{ id: "kid1", name: "Malia" }, { id: "kid2", name: "Vaiha" }],
    chores: [
      { id: "bed", name: "Make bed", assignment_mode: "everyone" },
      { id: "dish", name: "Dishes", assignment_mode: "everyone" },
      { id: "must", name: "Homework", assignment_mode: "everyone", mandatory: true },
      { id: "rota", name: "Bins", assignment_mode: "alternating" },
      { id: "fc", name: "Car wash", assignment_mode: "first_come" },
    ],
    choice_sets: [{ id: "s1", name: "Your part", chore_ids: ["bed"], min_required: 1, penalty_points: 5, assigned_to: [], active: true }],
    pending_completions: [],
    pending_reward_claims: [],
    swap_requests: [],
    wishes: [],
    mandatory_misses: MISSES,
    settings: { points_name: "Stars", ...settings },
    ...extra,
  };
  return p;
}

test("misses stay off the Today queue while they are reviewed on the card", () => {
  const q = panel()._approvalQueue({ wishes: true, misses: true });
  assert.equal(q.kinds.miss, 0);
  assert.doesNotMatch(q.html, /data-kind="miss"/);
});

for (const where of ["panel", "both"]) {
  test(`miss_review_location=${where}: Today lists missed sets and chores with the three answers`, () => {
    const q = panel({ miss_review_location: where })._approvalQueue({ wishes: true, misses: true });
    assert.equal(q.kinds.miss, 2);
    assert.equal(q.count, 2);
    assert.match(q.html, /panel\.miss_set_text\(Malia,Your part\)/);
    assert.match(q.html, /panel\.miss_chore_text\(Vaiha,Make bed\)/);
    assert.match(q.html, /panel\.miss_set_progress\(1,2\)/);
    assert.match(q.html, /data-act="miss-penalty" data-id="m1"/);
    // The panel's danger style, not red text on the raised (primary) button.
    assert.match(q.html, /class="tm-btn tm-btn-sm tm-btn-danger" data-act="miss-penalty"/);
    assert.doesNotMatch(q.html, /data-act="miss-penalty" data-id="m2"/, "no penalty button without penalty points");
    for (const act of ["miss-postpone", "miss-dismiss"]) {
      assert.match(q.html, new RegExp(`data-act="${act}" data-id="m2"`));
    }
  });
}

test("the Activity queue never lists misses", () => {
  const q = panel({ miss_review_location: "both" })._approvalQueue();
  assert.equal(q.kinds.miss, undefined);
  assert.doesNotMatch(q.html, /data-kind="miss"/);
});

test("resolving a miss calls the mandatory-miss service", async () => {
  const p = panel({ miss_review_location: "panel" });
  const calls = [];
  p._callService = async (service, data) => { calls.push([service, data]); return { ok: true }; };
  p._fetchState = async () => {};
  p._showToast = () => {};
  await p._doResolveMiss("apply_mandatory_penalty", "m1");
  await p._doResolveMiss("dismiss_mandatory_chore", "m2");
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [["apply_mandatory_penalty", { miss_id: "m1" }], ["dismiss_mandatory_chore", { miss_id: "m2" }]]);
});

test("the editor greys out chores that can't join and keeps members removable", () => {
  const p = panel();
  p._dialog = { kind: "choice_set", mode: "add", data: { name: "", chore_ids: [], assigned_to: [], min_required: 1, penalty_points: 0, active: true } };
  p._iconPickerField = () => "";
  const html = p._renderChoiceSetDialog();
  const chip = (id) => html.match(new RegExp(`<button[^>]*data-act="toggle-cs-chore" data-id="${id}"[^>]*>`))[0];
  assert.doesNotMatch(chip("dish"), /disabled/);
  assert.match(chip("bed"), /disabled title="panel\.choice_set_blocked_other\(Your part\)"/);
  assert.match(chip("must"), /disabled title="panel\.choice_set_blocked_mandatory"/);
  assert.match(chip("rota"), /disabled title="panel\.choice_set_blocked_rotation"/);
  assert.match(chip("fc"), /disabled title="panel\.choice_set_blocked_first_come"/);
  assert.match(html, /data-act="cs-step" data-field="min_required"/);
  assert.match(html, /data-act="cs-step" data-field="penalty_points"/);
  // Editing the set that owns "bed": it stays a removable member.
  p._dialog = { kind: "choice_set", mode: "edit", data: { ...p._state.choice_sets[0] } };
  assert.doesNotMatch(p._renderChoiceSetDialog().match(/<button[^>]*data-id="bed"[^>]*>/)[0], /disabled/);
});

test("the stepper never goes below 0", () => {
  const p = panel();
  p._render = () => {};
  p.querySelector = () => null;
  p._dialog = { kind: "choice_set", data: { min_required: 1, penalty_points: 0 } };
  p._stepChoiceSetField("min_required", -1);
  p._stepChoiceSetField("min_required", -1);
  p._stepChoiceSetField("penalty_points", 1);
  assert.equal(p._dialog.data.min_required, 0);
  assert.equal(p._dialog.data.penalty_points, 1);
});

test("saving sends the create command with clean numbers", async () => {
  const p = panel();
  const sent = [];
  p._syncIconPickers = () => {};
  p._callWS = async (msg) => { sent.push(msg); return { ok: true }; };
  p._closeDialog = () => {};
  p._fetchState = async () => {};
  p._showToast = () => {};
  p._dialog = { kind: "choice_set", mode: "add", data: { name: " Your part ", chore_ids: ["dish"], assigned_to: [], min_required: "2", penalty_points: "-4", active: true } };
  await p._doSaveChoiceSet();
  assert.equal(sent[0].type, "taskmate/choice_sets/create");
  assert.equal(sent[0].name, "Your part");
  assert.equal(sent[0].min_required, 2);
  assert.equal(sent[0].penalty_points, 0);
});

test("the Earn hub lists the Choice sets tab", () => {
  const p = panel();
  p._activeTab = "choice_sets";
  const html = p._renderChoiceSetsTab();
  assert.match(html, /data-act="add-choice-set"/);
  assert.match(html, /data-act="edit-choice-set" data-id="s1"/);
});
