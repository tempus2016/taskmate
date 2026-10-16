const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

const { get } = loadCard("taskmate-panel.js");
const TaskMatePanel = get("taskmate-panel");

// The panel renders with innerHTML, so every value that reaches a template
// must be escaped. The points name is settings text an import can carry.

const HOSTILE = '<img src=x onerror="alert(1)">';

function panel(extra = {}) {
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => Object.entries(params).reduce((s, [k, v]) => s.replace(`{${k}}`, v), `${key} {points_name}`);
  p._timeAgo = () => "just now";
  p._state = {
    children: [],
    chores: [],
    rewards: [{ id: "r1", name: "TV", cost: 10, assigned_to: [] }],
    quests: [{ id: "q1", name: "Q", steps: [], bonus_points: 5, active: true }],
    challenges: [{ id: "c1", name: "C", scope: "daily", metric: "chores", target: 2, bonus_points: 5, active: true }],
    pool_allocations: [],
    settings: { points_name: HOSTILE },
    ...extra,
  };
  return p;
}

for (const [label, render] of [
  ["reward card", (p) => p._renderRewardCard(p._state.rewards[0], p._state.settings.points_name)],
  ["quest card", (p) => p._renderQuestCard(p._state.quests[0], p._state.settings.points_name)],
  ["challenge card", (p) => p._renderChallengeCard(p._state.challenges[0], p._state.settings.points_name)],
]) {
  test(`${label} escapes the points name`, () => {
    const html = render(panel());
    assert.ok(!html.includes(HOSTILE), `${label} rendered the raw points name`);
    assert.ok(html.includes("&lt;img"), `${label} did not escape the points name`);
  });
}

test("chore picture thumbnail only shows TaskMate's own images", () => {
  const p = panel();
  p._choreImageBusy = false;
  const own = p._choreImageField("/api/taskmate/image/" + "a".repeat(32) + ".jpg");
  assert.ok(own.includes('src="/api/taskmate/image/'));
  const foreign = p._choreImageField("https://evil.example/track.png");
  assert.ok(!foreign.includes("evil.example"));
  assert.ok(!foreign.includes("<img"));
});

test("audit rows show a fold count", () => {
  const p = panel({ audit_log: [{ ts: "2026-10-16T10:00:00Z", user_name: "Kid", action: "service.choose_avatar", target: "Mia", count: 7 }] });
  const html = p._renderAuditTab();
  assert.ok(html.includes("×7"));
});
