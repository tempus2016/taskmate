"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

// "I'm stuck" is only offered on a row the child can do right now (#771). It
// used to sit on locked rows too — a later part of the day, a passed window,
// a cooldown — and the server took the request. These render the whole card
// through the real filter pass, in every design.

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

const HELP = /tm-help-btn/;

for (const design of DESIGNS) {
  for (const { name, args } of REASONS) {
    test(`${design}: no "I'm stuck" on a chore ${name}`, () => {
      const { markup } = render(makeCard({ ...args, design }).render());
      assert.match(markup, /ZZ chore/, "the row is on the card");
      assert.doesNotMatch(markup, HELP);
    });
  }

  test(`${design}: no "I'm stuck" once its window has passed, even under elapsed_time_mode show`, () => {
    const card = makeCard({
      chores: [chore({ time_category: "morning" })],
      config: { debug_time_period: "evening", time_category: "all", elapsed_time_mode: "show" },
      design,
    });
    const { markup } = render(card.render());
    assert.match(markup, /ZZ chore/);
    assert.doesNotMatch(markup, HELP);
  });

  test(`${design}: an open chore still offers "I'm stuck"`, async () => {
    const card = makeCard({ chores: [chore({ time_category: "morning" })], config: { debug_time_period: "morning" }, design });
    const calls = [];
    card.hass.callService = async (...a) => calls.push(a);
    const view = render(card.render());
    const btn = view.controls.find((c) => HELP.test(c.attrs));
    assert.ok(btn, "the help button is offered");
    await btn.click();
    assert.equal(calls[0][1], "request_help");
  });

  test(`${design}: a help request already on its way still shows on a locked row`, () => {
    const card = makeCard({ chores: [chore({ time_category: "evening" })], config: { debug_time_period: "morning" }, design });
    card.hass.states[ENTITY].attributes.children[0].help = ["zz"];
    assert.match(render(card.render()).markup, /tm-help-on/);
  });
}
