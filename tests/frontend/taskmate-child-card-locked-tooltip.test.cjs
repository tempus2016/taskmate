"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// A locked classic row refuses the tap, so its tooltip must say why (or say
// nothing) — never "Click to complete" (#771). These render the real row
// through the real filter pass for every lock reason.

const { get } = loadCard("taskmate-child-card.js", {
  window: { __taskmate_badge_id: (b) => b.badge_id },
});
const ChildCard = get("taskmate-child-card");
const ENTITY = "sensor.taskmate_overview";

function chore(extra = {}) {
  return {
    id: "zz",
    name: "ZZ chore",
    points: 5,
    time_category: "anytime",
    assigned_to: [],
    due_days: [],
    schedule_mode: "specific_days",
    daily_limit: 1,
    ...extra,
  };
}

function makeCard({ chores, completions = [], availability = {}, weekly = {}, config = {} }) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: "kid1", ...config };
  const mia = { id: "kid1", name: "Mia", chore_order: [], weekly_chore_progress: weekly };
  const leo = { id: "kid2", name: "Leo", chore_order: [], weekly_chore_progress: {} };
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [mia, leo],
          chores,
          todays_completions: completions,
          chore_availability: availability,
          today_day_of_week: "wednesday",
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  return card;
}

function rowTitle(card) {
  const row = render(card.render()).control(/class="chore-card/);
  assert.ok(row, "the chore row should be on the card");
  assert.match(row.attrs, /aria-disabled="true"/, "the row is locked");
  return row.attr("title");
}

const CLICK = localize("child.click_to_complete");

const REASONS = [
  {
    name: "before its time period",
    args: { chores: [chore({ time_category: "evening" })], config: { debug_time_period: "morning" } },
    expect: localize("child.chore_locked_until", { time: "17:00" }),
  },
  {
    name: "past its time window",
    args: { chores: [chore({ time_category: "morning" })], config: { debug_time_period: "evening", time_category: "all" } },
    expect: localize("child.time_has_passed"),
  },
  {
    name: "not due today",
    args: { chores: [chore({ due_days: ["monday"] })], config: { due_days_mode: "dim" } },
    expect: localize("child.not_scheduled_for_today"),
  },
  {
    name: "in its recurrence cooldown",
    args: { chores: [chore({ schedule_mode: "recurring", recurrence: "every_3_days" })], availability: { zz: { kid1: false } } },
    expect: localize("child.recurrence_locked"),
  },
  {
    name: "in its recurrence cooldown (show mode)",
    args: {
      chores: [chore({ schedule_mode: "recurring", recurrence: "every_3_days" })],
      availability: { zz: { kid1: false } },
      config: { recurrence_done_mode: "show" },
    },
    expect: localize("child.recurrence_locked"),
  },
  {
    name: "waiting on a prerequisite",
    args: {
      chores: [chore({ depends_on: ["teeth"] }), chore({ id: "teeth", name: "Teeth", time_category: "night" })],
      config: { dependency_mode: "dim", debug_time_period: "morning", time_category: "morning" },
    },
    expect: localize("child.blocked_by_dependency", { chores: "Teeth" }),
  },
  {
    name: "claimed first by a sibling",
    args: {
      chores: [chore({ assignment_mode: "first_come", assigned_to: ["kid1", "kid2"] })],
      completions: [{ chore_id: "zz", child_id: "kid2", approved: true, completed_at: new Date().toISOString() }],
      config: { first_come_claimed_mode: "dim" },
    },
    expect: localize("child.claimed_by_another", { name: "Leo" }),
  },
  {
    name: "already at its weekly target",
    args: { chores: [chore({ weekly_target: 2 })], weekly: { zz: 2 } },
    expect: localize("child.weekly_target_done"),
  },
];

for (const { name, args, expect } of REASONS) {
  test(`classic tooltip: a chore ${name} gives the reason, not "Click to complete"`, () => {
    const title = rowTitle(makeCard(args));
    assert.notEqual(title, CLICK);
    assert.equal(title, expect);
  });
}

test("classic tooltip: a set time that hasn't opened says when it opens", () => {
  const card = makeCard({ chores: [chore()] });
  const filter = card._filterAndSortChores.bind(card);
  card._filterAndSortChores = (...a) =>
    filter(...a).map((c) => Object.assign(c, { _setTimeLocked: true, _setTimeState: "later", _setTimeEntry: { opens: "18:30" } }));
  assert.equal(rowTitle(card), localize("child.set_time_opens", { time: "18:30" }));
});

test("classic tooltip: a lock with no reason to give says nothing rather than invite a tap", () => {
  const card = makeCard({ chores: [chore()] });
  const filter = card._filterAndSortChores.bind(card);
  card._filterAndSortChores = (...a) => filter(...a).map((c) => Object.assign(c, { _setTimeLocked: true }));
  assert.equal(rowTitle(card), "");
});

test("classic tooltip: an open chore still invites the tap", () => {
  const row = render(makeCard({ chores: [chore()] }).render()).control(/class="chore-card/);
  assert.equal(row.attr("title"), CLICK);
});

test("child.recurrence_locked is translated in every locale", () => {
  const fs = require("node:fs");
  const path = require("node:path");
  const dir = path.join(__dirname, "../../custom_components/taskmate/www/locales");
  const en = JSON.parse(fs.readFileSync(path.join(dir, "en.json"), "utf8"))["child.recurrence_locked"];
  for (const f of fs.readdirSync(dir).filter((n) => n.endsWith(".json"))) {
    const v = JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"))["child.recurrence_locked"];
    assert.ok(v, `${f} is missing child.recurrence_locked`);
    if (!f.startsWith("en")) assert.notEqual(v, en, `${f} is still English`);
  }
});
