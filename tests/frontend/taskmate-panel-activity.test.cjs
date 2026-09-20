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

// A pending completion was priced when the child submitted it. Recalculating
// from the chore shows the reviewing parent a different number from the one the
// child was promised, and from the one approval actually pays.

function pendingRowPoints(completion, chore = { id: "chore1", name: "Tidy up", points: 3 }) {
  const panel = Object.create(TaskMatePanel.prototype);
  panel._t = (key, params = {}) => (params.name ? `${key}:${params.name}` : key);
  panel._timeAgo = () => "just now";
  panel._esc = (value) => String(value ?? "");
  panel._safePhotoUrl = () => "";
  panel._state = {
    children: [{ id: "kid1", name: "Kid 1" }],
    chores: [chore],
    pending_completions: [
      { id: "p1", chore_id: chore.id, child_id: "kid1", completed_at: "2026-09-18T12:00:00Z", ...completion },
    ],
  };
  const markup = panel._renderActivityTab();
  return markup.match(/just now · (-?\d+) panel\.activity_points/)?.[1];
}

test("a pending completion shows the award it was submitted at", () => {
  // The chore has since been re-priced from 15 down to 3.
  assert.equal(pendingRowPoints({ submitted_points: 15 }), "15");
});

test("a pending completion with no recorded award falls back to the chore", () => {
  assert.equal(pendingRowPoints({}), "3");
});

test("a zero-point submission is shown as zero", () => {
  assert.equal(pendingRowPoints({ submitted_points: 0 }), "0");
});
