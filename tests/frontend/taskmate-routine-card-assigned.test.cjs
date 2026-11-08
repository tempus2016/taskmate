const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

// #1240: the Routine card listed chores assigned to other children, because it
// trusted chore_availability alone and that said "available" for every child
// on an "everyone" chore. It now applies the child card's assigned_to filter.

const CustomEvent = class { constructor(type, init) { this.type = type; this.detail = init?.detail; } };
const RoutineCard = loadCard("taskmate-routine-card.js", { sandbox: { CustomEvent } }).get("taskmate-routine-card");
const ENTITY = "sensor.taskmate_overview";

const chore = (id, assigned_to) => ({ id, name: id, points: 5, time_category: "morning", assigned_to });

function routineFor(childId, chores) {
  const card = new RoutineCard();
  card.setConfig({ entity: ENTITY, child_id: childId, time_category: "morning" });
  const availability = Object.fromEntries(chores.map((c) => [c.id, { a: true, b: true }]));
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "a", name: "Ava", chore_order: [] }, { id: "b", name: "Ben", chore_order: [] }],
          chores,
          chore_availability: availability,
          todays_completions: [],
        },
      },
    },
  };
  return card;
}

test("a sibling's chore is left out even when availability says true", () => {
  const chores = [chore("shower", ["a"]), chore("teeth", ["b"]), chore("dress", [])];
  assert.deepEqual(routineFor("b", chores)._tasks().map((c) => c.id), ["dress", "teeth"]);
  assert.deepEqual(routineFor("a", chores)._tasks().map((c) => c.id), ["dress", "shower"]);
});

test("a chore with no assigned_to list belongs to everyone", () => {
  const chores = [{ ...chore("dress", []), assigned_to: undefined }];
  assert.deepEqual(routineFor("b", chores)._tasks().map((c) => c.id), ["dress"]);
});
