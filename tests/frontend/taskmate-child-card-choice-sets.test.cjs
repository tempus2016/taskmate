"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

// Choice sets (#1259): a section per set with "Pick at least N", dots and
// "x of N". The set's chores appear only inside it, on the classic path AND
// every designed style (the two-render-paths trap), and in pre-reader mode
// the section keeps the dots only.

const ALIAS = { graphite: "cleanpro" };
const { get } = loadCard("taskmate-child-card.js", {
  window: {
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
const NOW = new Date().toISOString();

const chore = (id, name) => ({
  id, name, points: 5, time_category: "anytime", assigned_to: [], due_days: [], daily_limit: 1,
});
const done = (id) => ({
  completion_id: `k${id}`, id: `k${id}`, chore_id: id, chore_name: id, child_id: "kid1", completed_at: NOW, approved: true,
});

const CHORES = [
  chore("a", "Tidy your room"),
  chore("b", "Empty the dishwasher"),
  chore("c", "Fold the laundry"),
  chore("f", "Feed the cat"),
];

function makeCard(design, set, completions = [], config = {}) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: "kid1", card_design: design, show_badges: false, ...config };
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Malia", chore_order: [], ...(set ? { choice_sets: [set] } : {}) }],
          chores: CHORES,
          todays_completions: completions,
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card._resolveBadgesEntity = () => null;
  return card;
}

const SET = { set_id: "s1", name: "Your part for the family", icon: "mdi:hand-heart-outline", min: 2, done: 0, fulfilled: false, chore_ids: ["a", "b", "c"] };
const count = (text, needle) => text.split(needle).length - 1;

for (const design of ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"]) {
  test(`${design}: a set gets one section and its chores are listed once`, () => {
    const { markup } = render(makeCard(design, SET).render());
    const plain = render(makeCard(design, null).render()).markup;
    assert.equal(count(markup, 'class="tm-cs '), 1, "one set section");
    assert.match(markup, /Your part for the family/);
    assert.match(markup, /Pick at least 2/);
    assert.match(markup, /0 of 2/);
    for (const name of ["Tidy your room", "Empty the dishwasher", "Fold the laundry", "Feed the cat"]) {
      assert.ok(count(plain, name) > 0);
      assert.equal(count(markup, name), count(plain, name), `${name} is not repeated`);
    }
    assert.match(markup, /Other chores/);
    // Members sit inside the set group, before "Other chores".
    assert.ok(markup.indexOf("Fold the laundry") < markup.indexOf("Other chores"));
    assert.ok(markup.indexOf("Feed the cat") > markup.indexOf("Other chores"));
  });

  test(`${design}: a met set says so, without the mandatory look`, () => {
    const met = { ...SET, done: 2, fulfilled: true };
    const { markup } = render(makeCard(design, met, [done("a"), done("b")]).render());
    assert.match(markup, /class="tm-cs met"/);
    assert.match(markup, /Done! You can do more if you like\./);
    assert.match(markup, /2 of 2/);
  });

  test(`${design}: pre-reader keeps the dots and drops the words`, () => {
    const { markup } = render(makeCard(design, { ...SET, done: 1 }, [], { pre_reader: true }).render());
    assert.equal(count(markup, 'class="tm-cs '), 1);
    assert.doesNotMatch(markup, /class="tm-cs-name"/);
    assert.doesNotMatch(markup, /Other chores/);
    assert.match(markup, /class="tm-pre-dots"[^>]*aria-label="1 of 2"/);
  });
}

test("no sets: the card renders exactly as before", () => {
  const { markup } = render(makeCard("classic", null).render());
  assert.doesNotMatch(markup, /tm-cs/);
  assert.doesNotMatch(markup, /Other chores/);
});

test("an optional set (min 0) has no dots and says 'If you like'", () => {
  const { markup } = render(makeCard("classic", { ...SET, min: 0, fulfilled: true }).render());
  assert.match(markup, /If you like/);
  assert.doesNotMatch(markup, /class="tm-cs met"/);
  assert.doesNotMatch(markup, /tm-cs-count/);
});

test("both render paths go through the choice-set helper", () => {
  const src = fs.readFileSync(path.join(__dirname, "../../custom_components/taskmate/www/taskmate-child-card.js"), "utf8");
  const classic = src.slice(src.indexOf("  render() {"), src.indexOf("  _renderDesigned(design) {"));
  const designed = src.slice(src.indexOf("  _renderDesigned(design) {"), src.indexOf("  _designPlayroom("));
  assert.equal(count(classic, "this._renderChoiceSetGroups("), 2, "classic list + pre-reader grid");
  assert.equal(count(designed, "this._renderChoiceSetGroups("), 2, "designed list + pre-reader grid");
});
