// Available chores first (#1231): what a child can do right now sits at the
// top, then the chores still to come today, then missed, then finished ones.
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

const { get } = loadCard("taskmate-child-card.js");
const ChildCard = get("taskmate-child-card");

const KID = { id: "kid1", name: "Ann" };

function card(config = {}, completions = []) {
  const c = new ChildCard();
  c.setConfig({ entity: "sensor.taskmate_overview", child_id: KID.id, ...config });
  c.hass = {
    config: { time_zone: "UTC" },
    states: { "sensor.taskmate_overview": { state: "ok", attributes: { todays_completions: completions } } },
  };
  c._filterCompletionsForToday = (list) => list;
  c.requestUpdate = () => {};
  return c;
}

const chores = () => [
  { id: "eve", name: "Wash up", _isLockedPreview: true },
  { id: "done", name: "Make bed" },
  { id: "missed", name: "Feed cat", _isTimeElapsed: true },
  { id: "now", name: "Read" },
  { id: "blocked", name: "Dry up", _isDependencyBlocked: true },
  { id: "cool", name: "Water plants", _isRecurrenceLocked: true },
];

const longAgo = new Date(Date.now() - 60 * 60 * 1000).toISOString();
const doneLongAgo = [{ id: "c1", chore_id: "done", child_id: KID.id, completed_at: longAgo }];

test("now first, then later, then missed, then finished; order kept within each", () => {
  const out = card({}, doneLongAgo)._availableFirst(chores(), KID).map(c => c.id);
  assert.deepEqual(out, ["now", "eve", "blocked", "missed", "done", "cool"]);
});

test("switched off, the list keeps its order", () => {
  const c = card({ sort_available_first: false }, doneLongAgo);
  const base = chores();
  c._filterAndSortChoresBase = () => base;
  c._expandSetTimeChores = (list) => list;
  assert.deepEqual(c._filterAndSortChores(base, KID).map(x => x.id), base.map(x => x.id));
});

test("a chore the child can still undo stays where it is", () => {
  const until = new Date(Date.now() + 5 * 60 * 1000).toISOString();
  const comps = [{ id: "c1", chore_id: "done", child_id: KID.id, completed_at: longAgo, child_undo_until: until }];
  const out = card({}, comps)._availableFirst(chores(), KID).map(c => c.id);
  // It keeps its place among the chores on offer (it came before "now").
  assert.deepEqual(out.slice(0, 2), ["done", "now"]);
});

test("a chore just ticked settles for a moment, then moves down", () => {
  const justNow = new Date(Date.now() - 1000).toISOString();
  const c = card({}, [{ id: "c1", chore_id: "done", child_id: KID.id, completed_at: justNow }]);
  const out = c._availableFirst(chores(), KID).map(x => x.id);
  assert.deepEqual(out.slice(0, 2), ["done", "now"]);
  assert.ok(c._settleTimer, "a re-render is scheduled for when it settles");
  clearTimeout(c._settleTimer);
});

test("set-time rows sort by their own state", () => {
  const rows = [
    { id: "h@1", _baseId: "h", _setTime: {}, _setTimeState: "done" },
    { id: "h@2", _baseId: "h", _setTime: {}, _setTimeState: "later", _isLockedPreview: true },
    { id: "h@3", _baseId: "h", _setTime: {}, _setTimeState: "now" },
  ];
  const out = card()._availableFirst(rows, KID).map(x => x.id);
  assert.deepEqual(out, ["h@3", "h@2", "h@1"]);
});
