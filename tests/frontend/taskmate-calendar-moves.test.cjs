// Two-way calendar (#977): a chore occurrence moved or removed from the HA
// calendar. The backend settles today per chore as `occ_today` (true = moved
// onto today, false = moved away / removed) and ships the map itself as
// `moved_occurrences` for the calendar card. Every card that filters by
// weekday has to let those outrank `due_days`.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

const ENTITY = "sensor.taskmate_overview";

function chore(extra = {}) {
  return {
    id: "bins",
    name: "Put the bins out",
    points: 10,
    time_category: "anytime",
    assigned_to: [],
    schedule_mode: "specific_days",
    due_days: ["monday"],
    daily_limit: 1,
    ...extra,
  };
}

// ── Child card: one filter pass feeds every design ───────────────────────

const ChildCard = loadCard("taskmate-child-card.js", {
  window: { __taskmate_badge_id: (b) => b.badge_id },
}).get("taskmate-child-card");

function childCard(c, config = {}) {
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", ...config });
  const child = { id: "kid1", name: "Mia", points: 0, chore_order: [] };
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [child],
          chores: [c],
          todays_completions: [],
          chore_availability: {},
          today_day_of_week: "wednesday",
          points_icon: "mdi:star",
          points_name: "Stars",
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  return { card, child };
}

test("child card — a Monday chore moved onto today (Wednesday) is due", () => {
  const { card, child } = childCard(chore({ occ_today: true }));
  const [shown] = card._filterAndSortChores(card.hass.states[ENTITY].attributes.chores, child);
  assert.ok(shown, "the moved chore should be on the card");
  assert.equal(shown._isDueToday, true);
});

test("child card — without a move the Monday chore stays hidden on Wednesday", () => {
  const { card, child } = childCard(chore());
  assert.equal(card._filterAndSortChores(card.hass.states[ENTITY].attributes.chores, child).length, 0);
});

test("child card — today's occurrence removed from the calendar is hidden, even in dim/show modes", () => {
  for (const mode of ["hide", "dim", "show"]) {
    const { card, child } = childCard(chore({ due_days: ["wednesday"], occ_today: false }), { due_days_mode: mode });
    assert.equal(card._filterAndSortChores(card.hass.states[ENTITY].attributes.chores, child).length, 0, mode);
  }
});

for (const design of ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"]) {
  test(`child card — ${design} renders a chore moved onto today`, () => {
    const { card } = childCard(chore({ occ_today: true }), { card_design: design });
    assert.match(render(card.render()).markup, /Put the bins out/);
  });

  test(`child card — ${design} drops an occurrence removed from today`, () => {
    const { card } = childCard(chore({ due_days: ["wednesday"], occ_today: false }), { card_design: design });
    assert.doesNotMatch(render(card.render()).markup, /Put the bins out/);
  });
}

// ── Overview + parent dashboard: today's-chores counts ───────────────────

const attrs = { today_day_of_week: "wednesday", chore_availability: {} };
const kid = { id: "kid1", name: "Mia" };

test("overview card — occ_today outranks due_days", () => {
  const Overview = loadCard("taskmate-overview-card.js").get("taskmate-overview-card");
  const card = new Overview();
  const names = (c) => card._childChoresToday(kid, [c], attrs).map((x) => x.id);
  assert.deepEqual(names(chore()), []);
  assert.deepEqual(names(chore({ occ_today: true })), ["bins"]);
  assert.deepEqual(names(chore({ due_days: ["wednesday"], occ_today: false })), []);
});

test("parent dashboard — progress totals follow a moved or removed occurrence", () => {
  const Dash = loadCard("taskmate-parent-dashboard-card.js").get("taskmate-parent-dashboard-card");
  const card = new Dash();
  const total = (c) => card._designChildProgress(kid, [c], [], attrs).total;
  assert.equal(total(chore()), 0);
  assert.equal(total(chore({ occ_today: true })), 1);
  assert.equal(total(chore({ due_days: ["wednesday"], occ_today: false })), 0);
});

// ── Calendar card: any day, from the map ─────────────────────────────────

test("calendar card — places a moved occurrence on its new day only", () => {
  const Cal = loadCard("taskmate-calendar-card.js").get("taskmate-calendar-card");
  const card = new Cal();
  const tz = "UTC";
  const on = (c, iso, dow) => card._isChoreScheduledOn(c, dow, new Date(`${iso}T12:00:00Z`), "2026-06-22", tz);
  const moved = chore({ moved_occurrences: { "2026-06-22": "2026-06-24", "2026-06-29": "" } });
  assert.equal(on(moved, "2026-06-22", "monday"), false, "moved away");
  assert.equal(on(moved, "2026-06-24", "wednesday"), true, "moved onto");
  assert.equal(on(moved, "2026-06-29", "monday"), false, "removed");
  assert.equal(on(moved, "2026-07-06", "monday"), true, "the series carries on");
  assert.equal(on(chore(), "2026-06-24", "wednesday"), false, "no map, no change");
});
