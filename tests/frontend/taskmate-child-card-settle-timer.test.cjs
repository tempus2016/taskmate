// The "available first" sort keeps a just-ticked chore in place for a few
// seconds with a real timer (_availableFirst's settle timer). A completion
// stamped ahead of the browser's clock (server clock skew, or a test fixture
// set later in the day) must not stretch that timer past the settle window:
// a timer hours long kept the card re-rendering late and kept Node test
// files from exiting until the stamp came round.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

const ENTITY = "sensor.taskmate_overview";

function cardWithTimers() {
  const delays = [];
  const { get } = loadCard("taskmate-child-card.js", {
    sandbox: {
      setTimeout: (_fn, ms) => { delays.push(ms); return delays.length; },
      clearTimeout: () => {},
      setInterval: () => 0,
      clearInterval: () => {},
    },
  });
  const ChildCard = get("taskmate-child-card");
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1" });
  card._loading = {};
  card._optimisticCompletions = {};
  return { card, delays };
}

function chore(id, name) {
  return { id, name, points: 2, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", assignment_mode: "everyone" };
}

function rankWith(completedAt) {
  const { card, delays } = cardWithTimers();
  const child = { id: "kid1", name: "Mia", chore_order: [] };
  card.hass = {
    states: { [ENTITY]: { state: "ok", attributes: {
      children: [child],
      chores: [chore("bed", "Make bed"), chore("dog", "Walk dog")],
      todays_completions: [{ chore_id: "bed", child_id: "kid1", approved: true, completed_at: completedAt }],
      chore_availability: {},
    } } },
  };
  const order = card._availableFirst([chore("bed", "Make bed"), chore("dog", "Walk dog")], child).map((c) => c.id);
  return { order, delays };
}

test("a completion stamped in the future settles within the settle window", () => {
  // Ninety seconds ahead keeps it "today" whenever the suite runs (bar the
  // last ninety seconds before midnight) while still being in the future.
  const later = new Date(Date.now() + 90 * 1000).toISOString();
  const { order, delays } = rankWith(later);
  assert.deepEqual(order, ["bed", "dog"], "the just-ticked row stays where it was");
  assert.ok(delays.length > 0, "a settle timer is set");
  const settle = 8000 + 50;
  assert.ok(Math.max(...delays) <= settle, `no timer longer than the settle window (got ${Math.max(...delays)} ms)`);
});

test("a completion ticked just now still holds its place for the settle window", () => {
  const { order, delays } = rankWith(new Date().toISOString());
  assert.deepEqual(order, ["bed", "dog"]);
  assert.ok(delays.some((d) => d > 7000 && d <= 8050), "the settle timer runs for about eight seconds");
});

test("an old completion drops to the bottom with no timer", () => {
  const { order, delays } = rankWith(new Date(Date.now() - 60 * 1000).toISOString());
  assert.deepEqual(order, ["dog", "bed"]);
  assert.equal(delays.length, 0);
});
