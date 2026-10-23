const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

// A beaten record's confetti plays once, even where browser storage is
// blocked (some private-browsing modes), instead of on every update.

test("record confetti plays once when localStorage throws", () => {
  const window = {
    localStorage: { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } },
    matchMedia: () => ({ matches: false }),
  };
  const ChildCard = loadCard("taskmate-child-card.js", { window }).get("taskmate-child-card");
  const card = new ChildCard();
  card.setConfig({ entity: "sensor.taskmate_overview", child_id: "kid1" });
  let played = 0;
  card._spawnConfetti = () => { played += 1; };
  const attrs = { children: [{ id: "kid1", personal_bests: { new_today: ["longest_streak"], longest_streak: { value: 9, date: "2026-10-23" } } }] };
  for (let i = 0; i < 5; i++) card._maybeRecordConfetti(attrs);
  assert.equal(played, 1);
});
