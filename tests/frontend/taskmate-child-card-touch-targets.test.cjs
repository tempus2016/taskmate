"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

// Touch targets on the child card. Classic's whole chore row is one big
// tap-to-complete button, so "I'm stuck" and the reminder bell used to sit
// on that surface: a near miss completed the chore. They now render in their
// own strip under the row. The designed rows keep the two side by side in one
// group so their grown hit areas can't stack on a wrapped line.

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

function makeCard(design, extraAttrs = {}) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: "kid1", card_design: design };
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", chore_order: [], reminders: { bed: "17:30" } }],
          chores: [{
            id: "bed", name: "Make bed", points: 5, time_category: "anytime", assigned_to: [],
            due_days: [], schedule_mode: "specific_days", daily_limit: 1,
          }],
          todays_completions: [],
          chore_availability: {},
          today_day_of_week: "wednesday",
          chore_reminders: { earliest: "15:00", latest: "20:00" },
          ...extraAttrs,
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card.completed = [];
  card.helped = [];
  card._handleComplete = (c) => card.completed.push(c.id);
  card._askForHelp = (c) => card.helped.push(c.id);
  card._openReminderSheet = () => {};
  return card;
}

test("classic: I'm stuck and the bell are outside the row's tap-to-complete surface", async () => {
  const card = makeCard("classic");
  const view = render(card.render());
  const row = view.controls.find((c) => /class="chore-card\b/.test(c.attrs));
  assert.ok(row, "the chore row is on the card");
  assert.doesNotMatch(row.content, /tm-help-btn/, "no help or bell button inside the row");
  assert.match(view.markup, /<span class="tm-row-acts">/);

  const help = view.controls.find((c) => c.attrs.includes("tm-help-btn") && !c.attrs.includes("tm-remind-btn"));
  const bell = view.controls.find((c) => c.attrs.includes("tm-remind-btn"));
  assert.ok(help && bell, "both buttons still render");
  await help.click();
  assert.deepEqual(card.helped, ["bed"]);
  assert.deepEqual(card.completed, [], "asking for help never completes the chore");
});

test("classic: no action strip on a chore that is done", () => {
  const card = makeCard("classic", {
    todays_completions: [{ chore_id: "bed", child_id: "kid1", approved: true, completed_at: new Date().toISOString() }],
  });
  const { markup } = render(card.render());
  assert.doesNotMatch(markup, /tm-row-acts/);
});

for (const design of ["playroom", "console", "cleanpro", "accessible", "graphite"]) {
  test(`${design}: the bell and I'm stuck share one group in the row's meta`, () => {
    const { markup } = render(makeCard(design).render());
    assert.match(markup, /<span class="tm-meta-acts">\s*<button[^>]*tm-remind-btn[\s\S]*?<\/button>\s*<button[^>]*tm-help-btn/,
      "bell then help inside .tm-meta-acts");
    assert.doesNotMatch(markup, /tm-row-acts/, "the classic strip is classic-only");
  });
}
