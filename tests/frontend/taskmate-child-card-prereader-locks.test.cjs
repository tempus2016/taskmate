"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

// Pre-reader picture tiles (`pre_reader: true`) must refuse a tap whenever the
// classic row does (#771). The tile read chore._isAvailableForChild, which
// nothing ever set, so a recurring chore in its cooldown — and a sibling's
// first-come claim, a filled weekly quota, a missed window, a closed set time —
// stayed tappable. These render the whole card through the real filter pass,
// in every design, and press the tile.

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
  card.config = { entity: ENTITY, child_id: "kid1", card_design: design, pre_reader: true, ...config };
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

/** The picture tile for the chore under test. */
function tile(view) {
  return view.controls.find((c) => c.tag === "button" && /class="pre-tile\b/.test(c.attrs) && /aria-label="ZZ chore"/.test(c.attrs));
}

async function assertBlocked(card, design) {
  const view = render(card.render());
  assert.match(view.markup, /pre-reader-grid/, `${design}: picture tiles are what's rendered`);
  const target = tile(view);
  assert.ok(target, `${design}: the tile should be on the card`);
  assert.equal(target.disabled, true, `${design}: the tile must be disabled`);
  assert.match(target.attrs, /\blocked\b/, `${design}: and styled as locked`);
  await assert.rejects(target.click(), /disabled/);
  assert.deepEqual(card.completed, [], `${design}: the tap must not complete the chore`);
}

async function assertLive(card, design) {
  const view = render(card.render());
  const target = tile(view);
  assert.ok(target, `${design}: the tile should be on the card`);
  assert.equal(target.disabled, false, `${design}: the tile should be live`);
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
    test(`pre-reader ${design}: a chore ${name} can't be tapped`, async () => {
      await assertBlocked(makeCard({ ...args, design }), design);
    });
  }

  // A set time that hasn't opened (or closed undone). The set-times helper
  // annotates the row, so the flag is applied the way it would set it.
  test(`pre-reader ${design}: a set time that isn't open can't be tapped`, async () => {
    const card = makeCard({ chores: [chore()], design });
    const filter = card._filterAndSortChores.bind(card);
    card._filterAndSortChores = (...a) => filter(...a).map((c) => Object.assign(c, { _setTimeLocked: true }));
    await assertBlocked(card, design);
  });

  test(`pre-reader ${design}: an open chore with nothing in the way is still tappable`, async () => {
    await assertLive(makeCard({ chores: [chore({ time_category: "morning" })], config: { debug_time_period: "morning" }, design }), design);
  });

  test(`pre-reader ${design}: a matrix-available recurring chore is still tappable`, async () => {
    const card = makeCard({
      chores: [chore({ schedule_mode: "recurring", recurrence: "every_3_days" })],
      availability: { zz: { kid1: true } },
      design,
    });
    await assertLive(card, design);
  });

  // Ticking a recurring chore makes the matrix report it unavailable at once;
  // the tile must keep its undo rather than lock the child out of it.
  test(`pre-reader ${design}: a recurring chore ticked today can still be undone`, async () => {
    const card = makeCard({
      chores: [chore({ schedule_mode: "recurring", recurrence: "every_3_days" })],
      availability: { zz: { kid1: false } },
      completions: [{ chore_id: "zz", child_id: "kid1", approved: false, completed_at: new Date().toISOString() }],
      design,
    });
    let undone = 0;
    card._handleUndo = () => { undone += 1; };
    const target = tile(render(card.render()));
    assert.ok(target, "the done tile should be rendered");
    assert.match(target.attrs, /\bdone\b/);
    assert.equal(target.disabled, false);
    await target.click();
    assert.equal(undone, 1);
    assert.deepEqual(card.completed, []);
  });
}

// Pre-reader tiles take their locks from the same helper as the classic row,
// and the flag nothing ever set is gone.
test("pre-reader tiles take their locks from _choreLocks", () => {
  const src = require("node:fs").readFileSync(
    require("node:path").join(__dirname, "../../custom_components/taskmate/www/taskmate-child-card.js"),
    "utf8",
  );
  const body = (name) => {
    const start = src.indexOf(`\n  ${name}(`);
    assert.ok(start > 0, `${name} should exist`);
    return src.slice(start, src.indexOf("\n  }\n", start));
  };
  assert.match(body("_renderPreReaderTile"), /this\._choreLocks\(/);
  assert.match(body("_renderChoreCard"), /this\._choreLocks\(/);
  assert.doesNotMatch(src, /_isAvailableForChild/);
});
