// Adult profiles (#1061).
//
// Parents who log their own chores get a profile marked is_adult. Family-wide
// cards leave those profiles out unless the card sets show_adults, and then
// list them after the kids. A card pinned to one child_id is untouched, so an
// adult can still have a card of their own.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

const OVERVIEW = "sensor.taskmate_overview";
const CHILDREN = [
  { id: "mum", name: "Mum", points: 90, is_adult: true },
  { id: "k1", name: "Ella", points: 40 },
  { id: "k2", name: "Finn", points: 30 },
];

const resolver = loadCard("taskmate-attr-resolver.js", { sandbox: { queueMicrotask: () => {} } }).window;
const family = resolver.__taskmate_family_children;
const ids = (list) => list.map((c) => c.id);

test("adults are left out by default", () => {
  assert.deepEqual(ids(family(CHILDREN, {})), ["k1", "k2"]);
});

test("show_adults brings them back after the kids", () => {
  assert.deepEqual(ids(family(CHILDREN, { show_adults: true })), ["k1", "k2", "mum"]);
});

test("a card pinned to one child gets the full list to pick from", () => {
  assert.deepEqual(ids(family(CHILDREN, { child_id: "mum" })), ["mum", "k1", "k2"]);
});

test("a family with no adults keeps its list as it was", () => {
  const kids = CHILDREN.slice(1);
  assert.equal(family(kids, {}), kids);
});

test("the editor only offers the toggle once the family has an adult", () => {
  const hass = (children) => ({ states: { [OVERVIEW]: { state: "1", attributes: { children } } } });
  assert.equal(resolver.__taskmate_adults_field(hass(CHILDREN.slice(1)), { entity: OVERVIEW }).length, 0);
  assert.equal(resolver.__taskmate_adults_field(hass(CHILDREN), { entity: OVERVIEW })[0].name, "show_adults");
});

function leaderboard(config) {
  const Card = loadCard("taskmate-leaderboard-card.js", {
    window: { __taskmate_attrs: resolver.__taskmate_attrs, __taskmate_family_children: family },
  }).get("taskmate-leaderboard-card");
  const card = new Card();
  card.setConfig({ entity: OVERVIEW, ...config });
  card.hass = { states: { [OVERVIEW]: { state: "1", attributes: { children: CHILDREN } } } };
  return render(card.render()).markup;
}

test("the leaderboard hides an adult unless show_adults is set", () => {
  assert.ok(!leaderboard({}).includes("Mum"));
  assert.ok(leaderboard({ show_adults: true }).includes("Mum"));
});
