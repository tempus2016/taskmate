"use strict";
// Per-child stage (#1262): the child card's defaults follow the child's stage
// only where the card's YAML is unset, "Later" chores are hidden and
// "Practising" chores come first in their own section, in every design.
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

const ALIAS = { graphite: "cleanpro" };
const { get } = loadCard("taskmate-child-card.js", {
  window: {
    __taskmate_badge_id: (b) => b.badge_id,
    __taskmate_is_parent: () => false,
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

function chore(id, name) {
  return {
    id, name, points: 5, time_category: "anytime", assigned_to: [], due_days: [],
    schedule_mode: "specific_days", daily_limit: 1,
  };
}

function makeCard({ config = {}, child = {}, chores = [] } = {}) {
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", ...config });
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Isla", chore_order: [], weekly_chore_progress: {}, ...child }],
          chores,
          todays_completions: [],
          chore_availability: {},
          today_day_of_week: "wednesday",
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card.requestUpdate = () => {};
  return card;
}

test("stage defaults fill only options the YAML leaves unset", () => {
  const defaults = { show_countdown: true };
  assert.equal(ChildCard.stageConfig(defaults, {}, "3_5").pre_reader, true);
  assert.equal(ChildCard.stageConfig(defaults, { pre_reader: false }, "3_5").pre_reader, false);
  const teen = ChildCard.stageConfig(defaults, {}, "13_plus");
  assert.equal(teen.show_confetti, false);
  assert.equal(teen.show_roulette, false);
  assert.equal(ChildCard.stageConfig(defaults, { show_roulette: true }, "13_plus").show_roulette, true);
  assert.equal(ChildCard.stageConfig(defaults, {}, "6_8").show_description, true);
  assert.equal(ChildCard.stageConfig(defaults, { show_description: false }, "6_8").show_description, false);
  // No stage: the card's own defaults only.
  assert.equal(JSON.stringify(ChildCard.stageConfig(defaults, {}, "")), JSON.stringify({ show_countdown: true }));
});

test("the card picks up the child's stage, and follows a change", () => {
  const card = makeCard({ child: { age_group: "3_5" } });
  card.willUpdate(new Map());
  assert.equal(card.config.pre_reader, true);
  card.hass.states[ENTITY].attributes.children[0].age_group = "9_12";
  card.willUpdate(new Map());
  assert.equal(card.config.pre_reader, false);
  // Explicit YAML wins over the stage.
  const pinned = makeCard({ config: { pre_reader: false }, child: { age_group: "3_5" } });
  pinned.willUpdate(new Map());
  assert.equal(pinned.config.pre_reader, false);
});

test("no confetti at the Taking ownership stage", () => {
  const card = makeCard({ child: { age_group: "13_plus" } });
  card.willUpdate(new Map());
  card._confetti = [];
  card._spawnConfetti("confetti");
  assert.deepEqual(card._confetti, []);
});

test("Later chores are hidden and Practising ones come first", () => {
  const card = makeCard();
  const kid = { id: "kid1", chore_stage: { b: "later", c: "practising" } };
  card._filterAndSortChoresBase = (list) => list;
  card._expandSetTimeChores = (list) => list;
  card._availableFirst = (list) => list;
  const out = [...card._filterAndSortChores([chore("a", "A"), chore("b", "B"), chore("c", "C")], kid).map(c => c.id)];
  assert.deepEqual(out, ["c", "a"]);
});

for (const design of ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"]) {
  test(`${design}: practising section first, later chore gone`, () => {
    const card = makeCard({
      config: { card_design: design },
      child: { chore_stage: { b: "later", c: "practising" } },
      chores: [chore("a", "Put toys away"), chore("b", "Feed the cat"), chore("c", "Brush teeth")],
    });
    const markup = render(card.render()).markup;
    assert.ok(!markup.includes("Feed the cat"), "a Later chore is not on the card");
    const head = markup.indexOf("tm-practising-head");
    assert.ok(head >= 0, "the Practising section is shown");
    assert.ok(markup.includes("With help counts too"));
    const brush = markup.indexOf("Brush teeth", head);
    const toys = markup.indexOf("Put toys away");
    assert.ok(brush > head && toys > brush, "the practising chore sits under its heading, before the rest");
  });

  test(`${design}: pre-reader mode keeps the order but no words`, () => {
    const card = makeCard({
      config: { card_design: design, pre_reader: true },
      child: { chore_stage: { c: "practising" } },
      chores: [chore("a", "Put toys away"), chore("c", "Brush teeth")],
    });
    const markup = render(card.render()).markup;
    assert.ok(!markup.includes("tm-practising-head"));
    assert.ok(markup.indexOf("Brush teeth") < markup.indexOf("Put toys away"));
  });
}

// A practising chore (#1262) and a choice set (#1259) each draw their own
// section; the row numbers follow the drawn order, so they count up down the
// card and no two rows share one.
for (const design of ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"]) {
  test(`${design}: row numbers count up across Practising and a choice set`, () => {
    const card = makeCard({
      child: {
        chore_stage: { c: "practising" },
        choice_sets: [{ set_id: "s1", name: "Your part", min: 1, done: 0, fulfilled: false, chore_ids: ["a", "b"] }],
      },
      // The family order puts the practising chore last, as on a real card.
      config: { card_design: design },
      chores: [chore("a", "Put toys away"), chore("b", "Feed the cat"), chore("d", "Shoes away"), chore("c", "Brush teeth")],
    });
    card.hass.states[ENTITY].attributes.children[0].chore_order = ["d", "a", "b", "c"];
    const markup = render(card.render()).markup;
    const nums = [...markup.matchAll(/class="(?:chore-number-badge|num-badge|num q-num|num|c-num)(?:\s[^"]*)?"[^>]*>(?:\s|<!--[^>]*-->)*(\d+)(?:\s|<!--[^>]*-->)*</g)].map(m => Number(m[1]));
    // Playroom draws each list's first row as a numberless "up next" card.
    assert.ok(nums.length >= (design === "playroom" ? 1 : 4), `numbered rows found (got ${nums.join(",")})`);
    assert.deepEqual(nums, [...new Set(nums)].sort((x, y) => x - y), `numbers count up in the drawn order, none repeated (got ${nums.join(",")})`);
  });
}
