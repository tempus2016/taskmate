// Missed mandatory chores (#1271): each miss says which day and window it was
// missed in and how far the child got, and the buttons say what they do
// instead of hiding it in a tooltip phones never show.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const ApprovalsCard = loadCard("taskmate-approvals-card.js").get("taskmate-approvals-card");
const ENTITY = "sensor.taskmate_pending_approvals";
const DESIGNS = ["classic", "playroom", "console", "cleanpro"];

const MISSES = [
  {
    id: "m1",
    chore_id: "hoover",
    child_id: "kid1",
    child_name: "Mia",
    chore_name: "Hoover",
    due_date: "2026-11-17",
    period_id: "anytime",
    penalty_points: 3,
    weekly_target: 2,
    weekly_done: 1,
  },
  {
    id: "m2",
    chore_id: "teeth",
    child_id: "kid1",
    child_name: "Mia",
    chore_name: "Teeth",
    due_date: "2026-11-16",
    period_id: "p1",
    period_name: "Before school",
    penalty_points: 0,
  },
];

function card(design) {
  const c = new ApprovalsCard();
  c.setConfig({ entity: ENTITY, card_design: design });
  c.hass = {
    states: { [ENTITY]: { state: "2", attributes: { chore_completions: [], mandatory_misses: MISSES } } },
    callService: async () => {},
  };
  c._loading = {};
  return c;
}

const fmt = (y, m, d, opts) => new Date(y, m - 1, d).toLocaleDateString(undefined, opts);
const DAY = { weekday: "short", day: "numeric", month: "short" };
const SHORT = { day: "numeric", month: "short" };

test("approvals card: a miss names the day it was missed, local to the browser", () => {
  const c = card("classic");
  const lines = c._missContext(MISSES[0]);
  assert.equal(lines[0], localize("approvals.missed_on_period", { date: fmt(2026, 11, 17, DAY), period: localize("common.anytime") }));
  // Never the day before: the ISO day is not parsed as UTC midnight.
  assert.equal(c._missDay("2026-11-17").getDate(), 17);
});

test("approvals card: a weekly-target miss shows that week's progress", () => {
  const lines = card("classic")._missContext(MISSES[0]);
  const week = `${fmt(2026, 11, 16, SHORT)}–${fmt(2026, 11, 22, SHORT)}`;
  assert.equal(lines[1], localize("approvals.weekly_target_missed", { done: "1", target: "2", week }));
});

test("approvals card: a renamed period uses its name; a set time adds none", () => {
  const c = card("classic");
  assert.ok(c._missContext(MISSES[1])[0].includes("Before school"));
  const setTime = { ...MISSES[1], period_id: "set_time", time_id: "t1", period_name: undefined };
  assert.equal(c._missContext(setTime)[0], localize("approvals.missed_on", { date: fmt(2026, 11, 16, DAY) }));
});

for (const design of DESIGNS) {
  test(`approvals card: ${design} shows the context and labelled miss buttons`, () => {
    const { markup, controls } = render(card(design).render());
    assert.ok(markup.includes(localize("approvals.weekly_target_missed", { done: "1", target: "2", week: `${fmt(2026, 11, 16, SHORT)}–${fmt(2026, 11, 22, SHORT)}` })), "weekly progress");
    assert.ok(markup.includes("Before school"), "renamed period");
    for (const key of ["approvals.apply_penalty", "approvals.postpone", "approvals.dismiss"]) {
      assert.ok(controls.some((b) => (b.text || "").includes(localize(key))), `${key} is a visible label`);
    }
  });
}

test("approvals card: classic explains the miss buttons once", () => {
  const { markup } = render(card("classic").render());
  assert.ok(markup.includes(localize("approvals.miss_help")));
});
