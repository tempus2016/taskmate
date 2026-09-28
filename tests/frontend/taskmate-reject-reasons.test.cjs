// Reject reasons (#976): a parent can say why a chore or reward was sent back,
// and the child sees it on their card and in the activity feed.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const ENTITY = "sensor.taskmate_overview";
const REASON = "Bed not made <b>";
const plain = (value) => JSON.parse(JSON.stringify(value));

// ── child card ────────────────────────────────────────────────────────────

const ChildCard = loadCard("taskmate-child-card.js").get("taskmate-child-card");

function childCard({ design = "classic", rejections, completions = [], chore = {} } = {}) {
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design });
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", chore_order: [], ...(rejections ? { rejections } : {}) }],
          chores: [
            {
              id: "bed",
              name: "Make the bed",
              points: 5,
              time_category: "anytime",
              assigned_to: [],
              due_days: [],
              schedule_mode: "specific_days",
              assignment_mode: "everyone",
              ...chore,
            },
          ],
          todays_completions: completions,
          chore_availability: {},
          today_day_of_week: "wednesday",
          points_icon: "mdi:star",
        },
      },
    },
    callService: async () => {},
  };
  card._loading = {};
  card._optimisticCompletions = {};
  return card;
}

const note = localize("child.rejected_note", { reason: REASON });

for (const design of DESIGNS) {
  test(`child card: ${design} shows why the chore was sent back`, () => {
    const card = childCard({ design, rejections: [{ kind: "chore", id: "bed", reason: REASON, at: "x" }] });
    const { markup } = render(card.render());
    assert.ok(markup.includes(note), "the reason is drawn on the chore");
  });

  test(`child card: ${design} shows nothing without a reason`, () => {
    const { markup } = render(childCard({ design }).render());
    assert.ok(!markup.includes("↩️"));
  });

  test(`child card: ${design} ignores a reason for another item`, () => {
    const card = childCard({ design, rejections: [{ kind: "reward", id: "bed", reason: REASON }] });
    assert.ok(!render(card.render()).markup.includes(note));
  });
}

test("child card: a timed chore shows the reason while idle", () => {
  const card = childCard({
    chore: { task_type: "timed", timed_rate_minutes: 5, timed_rate_points: 1 },
    rejections: [{ kind: "chore", id: "bed", reason: REASON }],
  });
  assert.ok(render(card.render()).markup.includes(note));
});

// ── rewards card ──────────────────────────────────────────────────────────

const RewardsCard = loadCard("taskmate-rewards-card.js").get("taskmate-rewards-card");

function rewardRows(config, rejections) {
  const card = new RewardsCard();
  card.config = { entity: "sensor.taskmate_rewards", ...config };
  card.hass = { states: { "sensor.taskmate_rewards": { attributes: { pending_reward_claims: [] } } } };
  const children = [{ id: "kid1", name: "Mia", points: 10, rejections }];
  const reward = { id: "ice", name: "Ice cream", icon: "mdi:gift", cost: 50, assigned_to: [] };
  const childMap = { kid1: children[0] };
  return [
    render(card._renderRewardRow(reward, "mdi:star", "Stars", childMap, children)).markup,
    render(card._designRewardRow(reward, children, "mdi:star", "Stars", "playroom")).markup,
  ];
}

test("rewards card: both paths show why the claim was turned down", () => {
  const rejections = [{ kind: "reward", id: "ice", reason: REASON }];
  const expected = localize("rewards.rejected_note", { reason: REASON });
  for (const markup of rewardRows({ child_id: "kid1" }, rejections)) assert.ok(markup.includes(expected));
});

test("rewards card: the reason stays private without a child in context", () => {
  const rejections = [{ kind: "reward", id: "ice", reason: REASON }];
  for (const markup of rewardRows({}, rejections)) assert.ok(!markup.includes("↩️"));
});

// ── approvals card ───────────────────────────────────────────────────────

const ApprovalsCard = loadCard("taskmate-approvals-card.js").get("taskmate-approvals-card");

function approvalsCard() {
  const card = new ApprovalsCard();
  card.config = { entity: "sensor.taskmate_pending_approvals" };
  const calls = [];
  card.hass = { states: {}, callService: async (domain, service, data) => calls.push({ domain, service, data }) };
  card._loading = {};
  card.updateComplete = Promise.resolve();
  return { card, calls };
}

function withInput(card, value) {
  const input = { value, focus() {} };
  card._rejectInput = () => input;
  return input;
}

test("approvals card: reject opens a sheet with quick-pick chips instead of rejecting", async () => {
  const { card, calls } = approvalsCard();
  card._handleReject({ completion_id: "c1", chore_name: "Make the bed", child_name: "Mia" });
  assert.equal(calls.length, 0, "nothing is rejected until the parent confirms");
  const { markup, controls } = render(card._renderRejectSheet());
  assert.ok(markup.includes(localize("reject.title", { name: "Make the bed" })));
  for (const key of ["reject.chip_not_finished", "reject.chip_redo", "reject.chip_not_today"]) {
    assert.ok(controls.some((c) => c.text === localize(key)), `${key} chip`);
  }
});

test("approvals card: a chip fills the reason and confirm sends it", async () => {
  const { card, calls } = approvalsCard();
  card._handleReject({ completion_id: "c1", chore_name: "Make the bed" });
  const input = withInput(card, "stale");
  await card.updateComplete;
  await Promise.resolve();
  assert.equal(input.value, "", "opening the sheet clears the box");
  const chip = render(card._renderRejectSheet()).controls.find((c) => c.text === localize("reject.chip_redo"));
  await chip.click();
  assert.equal(input.value, localize("reject.chip_redo"));
  await card._confirmReject();
  assert.deepEqual(plain(calls), [
    { domain: "taskmate", service: "reject_chore", data: { completion_id: "c1", reason: localize("reject.chip_redo") } },
  ]);
  assert.equal(card._rejecting, null);
});

test("approvals card: an empty box is a plain reject", async () => {
  const { card, calls } = approvalsCard();
  card._handleRejectReward("claim-1", "Ice cream", "Mia");
  withInput(card, "   ");
  await card._confirmReject();
  assert.deepEqual(plain(calls), [{ domain: "taskmate", service: "reject_reward", data: { claim_id: "claim-1" } }]);
});

test("approvals card: typed text is trimmed and capped", async () => {
  const { card, calls } = approvalsCard();
  card._handleRejectReward("claim-1", "Ice cream");
  withInput(card, `  ${"x".repeat(300)} `);
  await card._confirmReject();
  assert.equal(calls[0].data.reason.length, 200);
});

test("approvals card: both render paths draw the reject sheet", () => {
  const src = require("node:fs").readFileSync(
    require("node:path").join(__dirname, "../../custom_components/taskmate/www/taskmate-approvals-card.js"),
    "utf8",
  );
  const classic = src.slice(src.indexOf("  render() {"), src.indexOf("  _designTone("));
  const designed = src.slice(src.indexOf("  _renderDesigned(design) {"), src.indexOf("  _designHeader("));
  assert.ok(classic.includes("this._renderRejectSheet()"));
  assert.ok(designed.includes("this._renderRejectSheet()"));
});

// ── activity card ────────────────────────────────────────────────────────

const ActivityCard = loadCard("taskmate-activity-card.js").get("taskmate-activity-card");

test("activity card: a rejection with a reason reads the same in every design", () => {
  const card = new ActivityCard();
  card.hass = { states: {} };
  card.config = { entity: ENTITY };
  card._loading = {};
  const item = {
    type: "chore_rejected",
    child_id: "kid1",
    chore_name: "Make the bed",
    reason: REASON,
    completed_at: "2026-09-28T10:00:00Z",
  };
  const why = localize("activity.rejected_reason", { reason: REASON });
  const classic = render(card._renderItem(item, { kid1: "Mia" }, "mdi:star", {})).markup;
  assert.ok(classic.includes(why) && classic.includes("Make the bed"));
  const d = card._describeEvent(item, { kid1: "Mia" }, "mdi:star", {});
  assert.ok(render(d.text).markup.includes(why), "playroom / cleanpro text");
  assert.ok(d.plain.includes(why), "console text");
  assert.equal(d.undo, null);
  assert.equal(card._eventBucket({ type: "reward_rejected" }), "rewards");
  assert.equal(card._eventBucket(item), "chores");
});

// ── admin panel ──────────────────────────────────────────────────────────

const TaskMatePanel = loadCard("taskmate-panel.js").get("taskmate-panel");

function panel() {
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => [key, ...Object.values(params)].join(":");
  p._state = {
    children: [{ id: "kid1", name: "Mia" }],
    chores: [{ id: "bed", name: "Make <the> bed" }],
    rewards: [{ id: "ice", name: "Ice cream" }],
    pending_completions: [{ id: "c1", chore_id: "bed", child_id: "kid1" }],
    pending_reward_claims: [{ id: "cl1", reward_id: "ice", child_id: "kid1" }],
    settings: {},
  };
  p._render = () => {};
  p._showToast = () => {};
  p._fetchState = async () => {};
  p.calls = [];
  p._callWS = async (msg) => {
    p.calls.push(msg);
    return { ok: true };
  };
  return p;
}

test("panel: reject opens a named dialog with chips, escaped", () => {
  const p = panel();
  p._openRejectDialog("chore", "c1");
  assert.equal(p._dialog.kind, "reject");
  const html = p._renderRejectDialog();
  assert.ok(html.includes("reject.title:Make &lt;the&gt; bed"));
  assert.ok(html.includes('data-act="reject-chip"') && html.includes('data-field="reason"'));
  assert.ok(html.includes('data-act="save-reject"'));
});

test("panel: the reason goes to the WS call, and is left out when empty", async () => {
  const p = panel();
  p._openRejectDialog("reward", "cl1");
  p._dialog.data.reason = "  Not today ";
  await p._doReject(p._dialog.data.kind, p._dialog.data.id, p._dialog.data.reason);
  await p._doReject("chore", "c1", "");
  assert.deepEqual(plain(p.calls), [
    { type: "taskmate/reject_reward", claim_id: "cl1", reason: "Not today" },
    { type: "taskmate/reject_chore", completion_id: "c1" },
  ]);
  assert.equal(p._dialog, null, "the dialog closes once rejected");
});
