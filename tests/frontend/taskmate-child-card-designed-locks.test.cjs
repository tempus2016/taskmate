"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

// Every designed style must refuse a tap whenever the classic row does (#771).
// The designed rows used to grey out a chore before its time period, past its
// window or on a day it isn't due — but leave the Done button live, so a tap
// still completed it. These render the whole card through the real filter
// pass, in every design, and press the button.

// graphite reuses the cleanpro layout (LAYOUT_ALIAS in taskmate-design.js).
const ALIAS = { graphite: "cleanpro" };
const { get } = loadCard("taskmate-child-card.js", {
  window: {
    __taskmate_badge_id: (b) => b.badge_id,
    __taskmate_design: {
      apply: (_card, _hass, config) => {
        const d = config?.card_design || "classic";
        return ALIAS[d] || d;
      },
      styles: () => null,
      editorOptions: () => [],
    },
  },
});
const ChildCard = get("taskmate-child-card");

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];

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

function makeCard({ chores, completions = [], availability = {}, weekly = {}, config = {}, design }) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: "kid1", card_design: design, ...config };
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
  card.completed = [];
  card._handleComplete = (c) => card.completed.push(c.id);
  return card;
}

/** The control a child taps to complete the chore, in whichever design. */
function tapTarget(view, design) {
  if (design === "classic") return view.control(/class="chore-card/);
  return view.controls.find((c) => c.tag === "button" && /class="btn\b/.test(c.attrs));
}

async function assertBlocked(card, design) {
  const view = render(card.render());
  const target = tapTarget(view, design);
  assert.ok(target, `${design}: the chore row should be on the card`);
  if (design === "classic") {
    assert.match(target.attrs, /aria-disabled="true"/);
    await target.click();
  } else {
    assert.equal(target.disabled, true, `${design}: the Done button must be disabled`);
    await assert.rejects(target.click(), /disabled/);
  }
  assert.deepEqual(card.completed, [], `${design}: the tap must not complete the chore`);
}

async function assertLive(card, design) {
  const view = render(card.render());
  const target = tapTarget(view, design);
  assert.ok(target, `${design}: the chore row should be on the card`);
  if (design === "classic") assert.match(target.attrs, /aria-disabled="false"/);
  else assert.equal(target.disabled, false, `${design}: the Done button should be live`);
  await target.click();
  assert.deepEqual(card.completed, ["zz"], `${design}: the tap completes the chore`);
}

const REASONS = [
  {
    name: "before its time period (locked preview)",
    args: { chores: [chore({ time_category: "evening" })], config: { debug_time_period: "morning" } },
  },
  {
    name: "past its time window (elapsed, dim)",
    args: { chores: [chore({ time_category: "morning" })], config: { debug_time_period: "evening", time_category: "all" } },
  },
  {
    name: "not due today (due_days_mode dim)",
    args: { chores: [chore({ due_days: ["monday"] })], config: { due_days_mode: "dim" } },
  },
  {
    name: "in its recurrence cooldown",
    args: {
      chores: [chore({ schedule_mode: "recurring", recurrence: "every_3_days" })],
      availability: { zz: { kid1: false } },
    },
  },
  {
    name: "in its recurrence cooldown (recurrence_done_mode show)",
    args: {
      chores: [chore({ schedule_mode: "recurring", recurrence: "every_3_days" })],
      availability: { zz: { kid1: false } },
      config: { recurrence_done_mode: "show" },
    },
  },
  {
    name: "waiting on a prerequisite (dependency_mode dim)",
    args: {
      chores: [chore({ depends_on: ["teeth"] }), chore({ id: "teeth", name: "Teeth", time_category: "night" })],
      config: { dependency_mode: "dim", debug_time_period: "morning", time_category: "morning" },
    },
  },
  {
    name: "claimed first by a sibling (first-come)",
    args: {
      chores: [chore({ assignment_mode: "first_come", assigned_to: ["kid1", "kid2"] })],
      completions: [{ chore_id: "zz", child_id: "kid2", approved: true, completed_at: new Date().toISOString() }],
      config: { first_come_claimed_mode: "dim" },
    },
  },
  {
    name: "already at its weekly target",
    args: { chores: [chore({ weekly_target: 2 })], weekly: { zz: 2 } },
  },
];

for (const design of DESIGNS) {
  for (const { name, args } of REASONS) {
    test(`${design}: a chore ${name} can't be ticked`, async () => {
      const card = makeCard({ ...args, design });
      await assertBlocked(card, design);
    });
  }

  // A set time that hasn't opened (or closed undone). The set-times helper
  // annotates the row, so the flag is applied the way it would set it.
  test(`${design}: a set time that isn't open can't be ticked`, async () => {
    const card = makeCard({ chores: [chore()], design });
    const filter = card._filterAndSortChores.bind(card);
    card._filterAndSortChores = (...a) => filter(...a).map((c) => Object.assign(c, { _setTimeLocked: true }));
    await assertBlocked(card, design);
  });

  test(`${design}: an open chore with nothing in the way is still tickable`, async () => {
    await assertLive(makeCard({ chores: [chore({ time_category: "morning" })], config: { debug_time_period: "morning" }, design }), design);
  });

  test(`${design}: a chore inside its claim grace stays tickable`, async () => {
    // Morning chore, viewed at the start of the afternoon with a long grace.
    const card = makeCard({
      chores: [chore({ time_category: "morning", claim_allowance_minutes: 600 })],
      config: { debug_time_period: "afternoon" },
      design,
    });
    await assertLive(card, design);
  });
}

// The designed Done button and the classic row must read the same rule set:
// one helper, called from both, so they can't drift apart again.
test("both render paths take their locks from _choreLocks", () => {
  const src = require("node:fs").readFileSync(
    require("node:path").join(__dirname, "../../custom_components/taskmate/www/taskmate-child-card.js"),
    "utf8",
  );
  const body = (name) => {
    const start = src.indexOf(`\n  ${name}(`);
    assert.ok(start > 0, `${name} should exist`);
    return src.slice(start, src.indexOf("\n  }\n", start));
  };
  assert.match(body("_renderChoreCard"), /this\._choreLocks\(/);
  assert.match(body("_renderDesigned"), /this\._choreLocks\(/);
});

// A done row's undo chip stays live on the designed styles even when a lock
// would otherwise apply (here: the recurrence window it just opened).
for (const design of DESIGNS.filter((d) => d !== "classic")) {
  test(`${design}: a done chore can still be undone`, async () => {
    const card = makeCard({
      chores: [chore({ schedule_mode: "recurring", recurrence: "every_3_days" })],
      availability: { zz: { kid1: false } },
      completions: [{ chore_id: "zz", child_id: "kid1", approved: false, completed_at: new Date().toISOString() }],
      design,
    });
    let undone = 0;
    card._handleUndo = () => { undone += 1; };
    const chip = render(card.render()).controls.find((c) => /tmd-undochip/.test(c.attrs));
    assert.ok(chip, "the undo chip should be rendered");
    assert.equal(chip.disabled, false);
    await chip.click();
    assert.equal(undone, 1);
  });
}
