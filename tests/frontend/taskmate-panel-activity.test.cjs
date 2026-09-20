const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

const { get } = loadCard("taskmate-panel.js");
const TaskMatePanel = get("taskmate-panel");

function panelWith(claim, rewardCost = 20) {
  const panel = Object.create(TaskMatePanel.prototype);
  panel._t = (key, params = {}) => (params.name ? `${key}:${params.name}` : key);
  panel._state = {
    children: [{ id: "kid1", name: "Kid 1" }],
    rewards: [{ id: "prize", name: "Prize", cost: rewardCost }],
    reward_claims: [
      {
        id: "claim1",
        reward_id: "prize",
        child_id: "kid1",
        approved: true,
        claimed_at: "2026-09-18T12:00:00Z",
        approved_at: "2026-09-18T12:05:00Z",
        ...claim,
      },
    ],
  };
  return panel;
}

function pointsCell(panel) {
  const markup = panel._renderActivityTab();
  return markup.match(/class="tm-timeline-points [^"]*">([^<]+)</)?.[1];
}

// The reward's live cost is not the price a past purchase was approved at —
// re-pricing a reward must not rewrite what the history says it cost.

test("an approved claim shows the price it was approved at", () => {
  assert.equal(pointsCell(panelWith({ approved_cost: 50 }, 20)), "-50");
});

test("a free reward is shown as zero, not as its current price", () => {
  assert.equal(pointsCell(panelWith({ approved_cost: 0 }, 20)), "+0");
});

test("a claim with no recorded price falls back to the reward's cost", () => {
  assert.equal(pointsCell(panelWith({}, 20)), "-20");
});

test("a deleted reward with no recorded price contributes nothing", () => {
  const panel = panelWith({});
  panel._state.rewards = [];
  assert.equal(pointsCell(panel), "+0");
});
