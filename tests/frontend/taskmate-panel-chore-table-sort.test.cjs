"use strict";
// Earn table (#1173): click-to-sort headings and the filter row. Both only
// change what the panel shows; the saved order is never written.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

const P = loadCard("taskmate-panel.js");

function panel(chores) {
  const p = Object.create(P.get("taskmate-panel").prototype);
  p._state = {
    chores,
    children: [{ id: "a", name: "Ann" }, { id: "b", name: "Ben" }],
    settings: {},
    chore_display_order: chores.map(c => c.id),
  };
  p._filter = "";
  p._choreSort = null;
  p._choreFilt = {};
  p._render = () => {};
  p._t = (k, params) => (params ? `${k}:${JSON.stringify(params)}` : k);
  p._effectiveTimePeriods = () => [{ id: "morning" }, { id: "afternoon" }, { id: "evening" }];
  return p;
}

const CHORES = [
  { id: "1", name: "Wash up", points: 5, time_category: "evening", assigned_to: [], requires_approval: true, schedule_mode: "specific_days", due_days: [] },
  { id: "2", name: "brush teeth", points: 1, time_category: "morning", assigned_to: ["a"], requires_approval: false, schedule_mode: "specific_days", due_days: ["monday"] },
  { id: "3", name: "Bins", points: 10, time_category: "anytime", assigned_to: ["b"], requires_approval: true, schedule_mode: "recurring", enabled: false },
  { id: "4", name: "Brush teeth", points: 1, time_category: "morning", assigned_to: [], assignment_mode: "unassigned", requires_approval: false, schedule_mode: "one_shot" },
];
const ids = list => list.map(c => c.id);
const byId = p => Object.fromEntries(p._state.children.map(c => [c.id, c]));

test("no sort and no filter keeps the saved order", () => {
  const p = panel(CHORES);
  assert.deepEqual(ids(p._choreView(CHORES, byId(p))), ["1", "2", "3", "4"]);
});

test("a heading click sorts ascending, then descending, then back to saved order", () => {
  const p = panel(CHORES);
  p._toggleChoreSort("points");
  assert.deepEqual(ids(p._choreView(CHORES, byId(p))), ["2", "4", "1", "3"]);
  p._toggleChoreSort("points");
  assert.deepEqual(ids(p._choreView(CHORES, byId(p))), ["3", "1", "2", "4"]);
  p._toggleChoreSort("points");
  assert.equal(p._choreSort, null);
});

test("name sort ignores case, so duplicates sit together", () => {
  const p = panel(CHORES);
  p._toggleChoreSort("name");
  assert.deepEqual(ids(p._choreView(CHORES, byId(p))), ["3", "2", "4", "1"]);
});

test("period sorts anytime first, then the day's periods in order", () => {
  const p = panel(CHORES);
  p._toggleChoreSort("period");
  assert.deepEqual(ids(p._choreView(CHORES, byId(p))), ["3", "2", "4", "1"]);
});

test("filters: child, schedule, approval and status", () => {
  const p = panel(CHORES);
  p._choreFilt = { child: "a" };
  assert.deepEqual(ids(p._choreView(CHORES, byId(p))), ["1", "2"]);
  p._choreFilt = { child: "__none__" };
  assert.deepEqual(ids(p._choreView(CHORES, byId(p))), ["4"]);
  p._choreFilt = { child: "__all__" };
  assert.deepEqual(ids(p._choreView(CHORES, byId(p))), ["1"]);
  p._choreFilt = { schedule: "daily" };
  assert.deepEqual(ids(p._choreView(CHORES, byId(p))), ["1"]);
  p._choreFilt = { schedule: "days" };
  assert.deepEqual(ids(p._choreView(CHORES, byId(p))), ["2"]);
  p._choreFilt = { approval: "no", period: "morning" };
  assert.deepEqual(ids(p._choreView(CHORES, byId(p))), ["2", "4"]);
  p._choreFilt = { status: "disabled" };
  assert.deepEqual(ids(p._choreView(CHORES, byId(p))), ["3"]);
});

test("the table shows Mode and Status columns with sortable headings", () => {
  const p = panel(CHORES);
  p._bulkMode = false; p._bulkSel = new Set();
  p._idBadge = () => ""; p._num = Number; p._fmtNum = String; p._esc = s => String(s);
  p._inScope = () => true; p._emptyState = () => ""; p._searchBox = () => "";
  p._recurrenceLabel = () => "weekly"; p._labelOf = (_l, v) => v; p._oneOffDaySuffix = () => "";
  p._timeCategoryLabel = c => c; p._timeCategoryOptions = () => [{ v: "anytime", l: "Anytime" }];
  p._tn = (k) => k;
  const html = p._renderChoresTab();
  assert.match(html, /data-act="chore-sort" data-key="mode"/);
  assert.match(html, /data-act="chore-sort" data-key="status"/);
  assert.match(html, /data-chore-filt="approval"/);
  assert.match(html, /panel\.chore_status_disabled/);
});
