"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// The designed headers used to be titled "{name}'s Points" but never drew the
// balance (only classic did). Every designed style now shows the balance with
// the family's own points icon, and the row copy uses the family's points
// name instead of "XP", "+0" or an ambiguous "4 / 4".

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
const DESIGNED = ["playroom", "console", "cleanpro", "accessible", "graphite"];

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

function makeCard(design, chores) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: "kid1", card_design: design };
  const mia = { id: "kid1", name: "Mia", chore_order: [], points: 1234, level: 29 };
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [mia],
          chores,
          todays_completions: [],
          chore_availability: {},
          today_day_of_week: "wednesday",
          points_name: "Coins",
          points_icon: "mdi:cash",
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  return card;
}

const TWO = [chore({ id: "a", name: "Alpha" }), chore({ id: "b", name: "Beta", open_ended: true, points: 0 })];

for (const design of DESIGNED) {
  test(`${design}: the header shows the balance with the points icon`, () => {
    const { markup } = render(makeCard(design, TWO).render());
    const bal = markup.match(/<span class="tmd-bal"[^>]*>([\s\S]*?)<\/span>/);
    assert.ok(bal, "balance pill is in the header");
    assert.match(bal[0], /aria-label="1,234 Coins"/);
    assert.match(bal[1], /icon="mdi:cash"/);
    assert.match(bal[1], /1,234/);
  });

  test(`${design}: an open-ended chore names who sets the points, not +0`, () => {
    const { markup } = render(makeCard(design, TWO).render());
    assert.ok(markup.includes(localize("child.open_ended_points")));
    assert.doesNotMatch(markup, /\+0\b/);
  });
}

test("designed titles name the chores, not a points word", () => {
  const { markup } = render(makeCard("playroom", TWO).render());
  assert.ok(markup.includes(localize("child.chores_title", { name: "Mia" })));
});

test("cleanpro subtitle says how many are left out of how many", () => {
  const { markup } = render(makeCard("cleanpro", TWO).render());
  assert.ok(markup.includes(localize("child.remaining_of_total", { remaining: 2, total: 2 })));
});

test("with no chores the subtitle is left out, not \"0 of 0 left\"", () => {
  const { markup } = render(makeCard("cleanpro", []).render());
  assert.ok(!markup.includes(localize("child.remaining_of_total", { remaining: 0, total: 0 })));
  assert.match(markup, /class="tmd-bal"/, "the balance still shows");
});

test("console uses the family's points name and a readable level", () => {
  const { markup } = render(makeCard("console", TWO).render());
  assert.match(markup, /\+5 Coins/);
  assert.doesNotMatch(markup, /\bXP\b/);
  assert.ok(markup.includes(localize("child.level_label", { level: 29 })));
});

test("classic open-ended row names who sets the points", () => {
  const { markup } = render(makeCard("classic", TWO).render());
  assert.ok(markup.includes(localize("child.open_ended_points")));
});
