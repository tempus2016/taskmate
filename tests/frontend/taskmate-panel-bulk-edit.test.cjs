"use strict";
// Edit selected chores (#1174): only switched-on settings are sent.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

const P = loadCard("taskmate-panel.js");
const panel = () => {
  const p = Object.create(P.get("taskmate-panel").prototype);
  // The panel runs in its own realm; compare plain copies.
  const real = p._bulkEditChanges;
  p._bulkEditChanges = (d) => JSON.parse(JSON.stringify(real.call(p, d)));
  return p;
};

const base = {
  ids: ["1", "2"], ch_points: false, points: 5, ch_assigned: false, assigned_to: ["a"],
  ch_approval: false, requires_approval: true, ch_period: false, time_category: "morning",
  ch_schedule: false, schedule_mode: "specific_days", due_days: ["monday"], recurrence: "weekly", recurrence_day: "",
};

test("nothing switched on sends nothing", () => {
  assert.deepEqual(panel()._bulkEditChanges(base), {});
});

test("only the switched-on settings are sent", () => {
  const c = panel()._bulkEditChanges({ ...base, ch_points: true, points: "8", ch_approval: true, requires_approval: false });
  assert.deepEqual(c, { points: 8, requires_approval: false });
});

test("a day-list schedule sends its days, a recurring one its recurrence", () => {
  const p = panel();
  assert.deepEqual(p._bulkEditChanges({ ...base, ch_schedule: true }), { schedule_mode: "specific_days", due_days: ["monday"] });
  assert.deepEqual(p._bulkEditChanges({ ...base, ch_schedule: true, schedule_mode: "recurring", recurrence: "monthly" }),
    { schedule_mode: "recurring", recurrence: "monthly", recurrence_day: "" });
});

test("children and time of day", () => {
  const c = panel()._bulkEditChanges({ ...base, ch_assigned: true, assigned_to: [], ch_period: true, time_category: "evening" });
  assert.deepEqual(c, { assigned_to: [], time_category: "evening" });
});
