// A one-off chore dated for another day (#992) — e.g. added from the HA
// calendar for later in the week. The backend marks it `occ_today: false` in
// the chores record, as it does for a calendar move, so it has to stay off
// every card's list for today while one dated today still shows.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

const ENTITY = "sensor.taskmate_overview";

function oneOff(extra = {}) {
  return {
    id: "party",
    name: "Tidy up after the party",
    points: 10,
    time_category: "anytime",
    assigned_to: ["kid1"],
    schedule_mode: "one_shot",
    enabled: true,
    created_date: "2026-06-26",
    ...extra,
  };
}

const later = () => oneOff({ occ_today: false });
const today = () => oneOff({ created_date: "2026-06-24" });

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

test("child card — a one-off dated later is filtered out, whatever the modes", () => {
  for (const due_days_mode of ["hide", "dim", "show"]) {
    const { card, child } = childCard(later(), { due_days_mode, recurrence_done_mode: "dim" });
    assert.equal(card._filterAndSortChores(card.hass.states[ENTITY].attributes.chores, child).length, 0, due_days_mode);
  }
});

for (const design of ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"]) {
  test(`child card — ${design} leaves out a one-off dated later`, () => {
    const { card } = childCard(later(), { card_design: design });
    assert.doesNotMatch(render(card.render()).markup, /Tidy up after the party/);
  });

  test(`child card — ${design} still shows today's one-off`, () => {
    const { card } = childCard(today(), { card_design: design });
    assert.match(render(card.render()).markup, /Tidy up after the party/);
  });
}

const attrs = { today_day_of_week: "wednesday", chore_availability: {} };
const kid = { id: "kid1", name: "Mia" };

test("overview card — a one-off dated later isn't one of today's chores", () => {
  const Overview = loadCard("taskmate-overview-card.js").get("taskmate-overview-card");
  const card = new Overview();
  const ids = (c) => card._childChoresToday(kid, [c], attrs).map((x) => x.id);
  assert.deepEqual(ids(later()), []);
  assert.deepEqual(ids(today()), ["party"]);
});

test("parent dashboard — a one-off dated later isn't counted in today's total", () => {
  const Dash = loadCard("taskmate-parent-dashboard-card.js").get("taskmate-parent-dashboard-card");
  const card = new Dash();
  const total = (c) => card._designChildProgress(kid, [c], [], attrs).total;
  assert.equal(total(later()), 0);
  assert.equal(total(today()), 1);
});
