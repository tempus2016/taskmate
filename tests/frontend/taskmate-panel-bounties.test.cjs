// Admin panel → Bounties → History (#949, #961): an expired bounty that anyone
// ever claimed — whose claim ran out, or who gave it back — must not say
// "Nobody claimed".

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

const TaskMatePanel = loadCard("taskmate-panel.js").get("taskmate-panel");

function panel() {
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => [key, ...Object.values(params)].join(":");
  p._state = { children: [{ id: "mia", name: "Malia" }], completions: [], bounties: [], settings: {} };
  return p;
}

const base = {
  id: "b1", title: "Wash the car", points: 50, status: "expired", claim_hours: 2,
  eligible_child_ids: [], closed_at: "2026-09-27T18:00:00Z",
};

test("an expired bounty nobody claimed says so", () => {
  const html = panel()._renderBountyRow({ ...base, lapse_count: 0, claim_count: 0 }, {});
  assert.ok(html.includes("panel.bounty_expired_meta"));
  assert.ok(!html.includes("panel.bounty_expired_lapsed_meta"));
});

test("an expired bounty whose claim lapsed does not say nobody claimed", () => {
  const html = panel()._renderBountyRow({ ...base, lapse_count: 1, claim_count: 1 }, {});
  assert.ok(!html.includes("panel.bounty_expired_meta"), "a lapsed claim is not 'nobody claimed'");
  assert.ok(html.includes("panel.bounty_expired_lapsed_meta"));
  assert.ok(html.includes("panel.bounty_lapsed_meta:1"), "the lapse count still shows");
});

test("an expired bounty that was claimed and given back does not say nobody claimed", () => {
  const html = panel()._renderBountyRow({ ...base, lapse_count: 0, claim_count: 1 }, {});
  assert.ok(!html.includes("panel.bounty_expired_meta"), "a given-back claim is not 'nobody claimed'");
  assert.ok(html.includes("panel.bounty_expired_unfinished_meta"));
  assert.ok(!html.includes("panel.bounty_lapsed_meta"), "no lapse to report");
});

test("a lapse wins over a give-back in a mixed history", () => {
  const html = panel()._renderBountyRow({ ...base, lapse_count: 1, claim_count: 3 }, {});
  assert.ok(html.includes("panel.bounty_expired_lapsed_meta"));
  assert.ok(!html.includes("panel.bounty_expired_unfinished_meta"));
});

test("a bounty from before claims were counted still reads as nobody claimed", () => {
  const html = panel()._renderBountyRow({ ...base, lapse_count: 0 }, {});
  assert.ok(html.includes("panel.bounty_expired_meta"));
});
