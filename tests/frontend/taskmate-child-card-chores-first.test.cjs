"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

// Chores first: on every designed style today's list is the first thing under
// the header, and the badge strip + next-badge goal sit under the list. The
// classic style keeps its own order (badges above the chores).

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
const BADGES = {
  attributes: {
    earned: [{ badge_id: "b1", name: "First", icon: "mdi:medal", tier: "gold" }],
    available: [{ badge_id: "b2", name: "Next one", icon: "mdi:trophy", tier: "gold", progress_pct: 40, progress: 4, target: 10 }],
  },
};

function makeCard(design, config = {}) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: "kid1", card_design: design, ...config };
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", chore_order: [] }],
          chores: [{ id: "c1", name: "Feed the fish", points: 5, time_category: "anytime", assigned_to: [], due_days: [], daily_limit: 1 }],
          todays_completions: [],
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card._resolveBadgesEntity = () => BADGES;
  return card;
}

const ROW = { playroom: "tmd-chore", console: "tmd-quest", cleanpro: "tmd-check", accessible: "tmd-check", graphite: "tmd-check" };

for (const design of Object.keys(ROW)) {
  test(`${design}: the chore list comes before the badge strip and next-badge goal`, () => {
    const markup = render(makeCard(design).render()).markup;
    const row = markup.indexOf(`class="${ROW[design]}`);
    const strip = markup.indexOf('class="tmd-badges"');
    const next = markup.indexOf('class="tmd-next-badge"');
    assert.ok(row > 0, "chore row rendered");
    assert.ok(strip > row, "badge strip sits under the list");
    assert.ok(next > row, "next-badge goal sits under the list");
    assert.ok(markup.indexOf('class="tmd-section"') < row, "section line stays above the list");
  });

  test(`${design}: pre-reader tiles also lead the badge blocks`, () => {
    const markup = render(makeCard(design, { pre_reader: true }).render()).markup;
    const grid = markup.indexOf('class="pre-reader-grid"');
    assert.ok(grid > 0, "pre-reader grid rendered");
    // Pre-reader mode may add a modifier class (fix/child-card-pre-reader-tiles).
    assert.ok(markup.search(/class="tmd-badges[ "]/) > grid);
    assert.ok(markup.search(/class="tmd-next-badge[ "]/) > grid);
  });
}

test("classic keeps its badge strip above the chores", () => {
  const markup = render(makeCard("classic").render()).markup;
  const strip = markup.indexOf('class="badge-strip"');
  const row = markup.indexOf('class="chore-card');
  assert.ok(strip > 0 && row > 0);
  assert.ok(strip < row);
});
