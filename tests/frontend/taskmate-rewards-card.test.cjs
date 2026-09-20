const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

const { get } = loadCard("taskmate-rewards-card.js");
const RewardsCard = get("taskmate-rewards-card");

const POINTS_ICON = "mdi:star";
const POINTS_NAME = "Stars";

function makeCard({ pendingClaims = [], config = {}, selectedChildId = null } = {}) {
  const card = new RewardsCard();
  card.config = { entity: "sensor.taskmate_rewards", ...config };
  card.hass = {
    states: {
      "sensor.taskmate_rewards": { attributes: { pending_reward_claims: pendingClaims } },
    },
  };
  card._selectedChildId = selectedChildId;
  return card;
}

/** Render one reward through both the classic row and the designed row. */
function renderRow(card, reward, children) {
  const childMap = Object.fromEntries(children.map((c) => [c.id, c]));
  return {
    classic: render(card._renderRewardRow(reward, POINTS_ICON, POINTS_NAME, childMap, children)),
    designed: render(card._designRewardRow(reward, children, POINTS_ICON, POINTS_NAME, "playroom")),
  };
}

function jackpot(cost, allocations) {
  const children = allocations.map((_, i) => ({ id: `kid${i + 1}`, name: `Kid ${i + 1}`, points: 999 }));
  const reward = {
    id: "jackpot",
    name: "Trampoline",
    icon: "mdi:gift",
    cost,
    is_jackpot: true,
    pool_enabled: true,
    assigned_to: [],
    pool_allocations: Object.fromEntries(children.map((c, i) => [c.id, allocations[i]])),
    jackpot_pool_total: allocations.reduce((sum, points) => sum + points, 0),
  };
  return { reward, children };
}

// ── Contribution bars ────────────────────────────────────────────────────
// Every segment is measured against the shared goal. Sizing a segment against
// an equal per-child share instead capped the over-contributor at their own
// slice, so a fully funded jackpot drew a part-empty bar (#874).

for (const { name, cost, allocations, widths } of [
  { name: "unequal contributions fill the shared goal", cost: 50, allocations: [40, 10], widths: [80, 20] },
  { name: "partial funding leaves only the unfunded portion empty", cost: 50, allocations: [30, 5], widths: [60, 10] },
  { name: "one child can fund the whole goal alone", cost: 50, allocations: [50, 0], widths: [100, 0] },
  { name: "three contributors have no equal-share rounding gap", cost: 50, allocations: [17, 17, 16], widths: [34, 34, 32] },
  { name: "an empty pool draws empty segments", cost: 50, allocations: [0, 0], widths: [0, 0] },
  { name: "a zero-cost jackpot never divides by zero", cost: 0, allocations: [0, 0], widths: [0, 0] },
]) {
  test(`jackpot bar: ${name}`, () => {
    const { reward, children } = jackpot(cost, allocations);
    const { classic, designed } = renderRow(makeCard(), reward, children);

    const segments = classic.all(/class="jackpot-segment color-(\d+)"\s+style="width:\s*([\d.]+)%"/g);
    assert.deepEqual(segments.map(([, width]) => Number(width)), widths);
    assert.deepEqual(segments.map(([color]) => Number(color)), allocations.map((_, i) => i));

    const percentages = classic.all(/class="jackpot-pct">\((\d+)%\)/g).map(Number);
    assert.deepEqual(percentages, cost > 0 ? widths : []);

    const designedWidths = designed.all(/<i style="width:([\d.]+)%;background:/g).map(Number);
    assert.deepEqual(designedWidths, widths, "every design measures contributions the same way");

    assert.doesNotMatch(classic.markup + designed.markup, /NaN|Infinity|undefined%/);
  });
}

test("jackpot bar: the selected child does not change the contributions shown", () => {
  const { reward, children } = jackpot(50, [40, 10]);
  const asFirst = renderRow(makeCard({ selectedChildId: "kid1" }), reward, children);
  const asSecond = renderRow(makeCard({ selectedChildId: "kid2" }), reward, children);

  const widths = (rendered) => rendered.all(/class="jackpot-segment color-\d+"\s+style="width:\s*([\d.]+)%"/g).map(Number);
  assert.deepEqual(widths(asFirst.classic), [80, 20]);
  assert.deepEqual(widths(asSecond.classic), widths(asFirst.classic));
  assert.match(asFirst.classic.markup, /50\/50/);
  assert.match(asSecond.classic.markup, /50\/50/);
});

// ── Shared jackpot lock ──────────────────────────────────────────────────
// A jackpot is one pool redeemed once per funding cycle, so a claim from any
// contributor puts it into "awaiting approval" for everyone (#873).

test("a sibling's pending jackpot claim locks the reward for every child", () => {
  const { reward, children } = jackpot(50, [40, 10]);
  const pendingClaims = [{ reward_id: "jackpot", child_id: "kid1", approved: false }];

  for (const childId of ["kid1", "kid2"]) {
    const card = makeCard({ pendingClaims, selectedChildId: childId });
    const { classic, designed } = renderRow(card, reward, children);

    assert.match(classic.markup, /pending-approval/, `${childId}: classic row should read as pending`);
    assert.ok(!classic.control(/class="[^"]*claim-btn/), `${childId}: classic Redeem should be gone`);
    assert.ok(!classic.control(/class="[^"]*pool-/), `${childId}: classic pool controls should be gone`);
    assert.match(designed.markup, /awaiting|pending/i, `${childId}: designed row should read as pending`);
  }
});

test("a pending jackpot claim is not confused with another reward's claim", () => {
  const { reward, children } = jackpot(50, [50, 0]);
  const card = makeCard({
    pendingClaims: [{ reward_id: "other-reward", child_id: "kid2", approved: false }],
    selectedChildId: "kid2",
  });
  const { classic } = renderRow(card, reward, children);

  assert.doesNotMatch(classic.markup, /pending-approval/);
});

test("an ordinary reward only locks for the child who claimed it", () => {
  const children = [
    { id: "kid1", name: "Kid 1", points: 100 },
    { id: "kid2", name: "Kid 2", points: 100 },
  ];
  const reward = { id: "ice-cream", name: "Ice cream", cost: 20, is_jackpot: false, assigned_to: [] };
  const pendingClaims = [{ reward_id: "ice-cream", child_id: "kid1", approved: false }];

  const claimer = renderRow(makeCard({ pendingClaims, selectedChildId: "kid1" }), reward, children);
  const sibling = renderRow(makeCard({ pendingClaims, selectedChildId: "kid2" }), reward, children);

  assert.match(claimer.classic.markup, /pending-approval/);
  assert.doesNotMatch(sibling.classic.markup, /pending-approval/);
  assert.ok(sibling.classic.control(/class="[^"]*claim-btn/), "the sibling can still claim");
});

// ── Claim button wiring ──────────────────────────────────────────────────

test("the classic Redeem button calls the claim handler with the reward and child", async () => {
  const children = [{ id: "kid1", name: "Kid 1", points: 100 }];
  const reward = { id: "ice-cream", name: "Ice cream", cost: 20, is_jackpot: false, assigned_to: [] };
  const card = makeCard({ selectedChildId: "kid1" });

  const calls = [];
  card._promptClaim = (reward, child) => calls.push([reward.id, child.id]);

  const { classic } = renderRow(card, reward, children);
  const claim = classic.control(/class="[^"]*claim-btn/);
  assert.ok(claim, "a claim button is rendered");
  assert.equal(claim.disabled, false);
  await claim.click();

  assert.deepEqual(calls, [["ice-cream", "kid1"]]);
});

test("the classic Redeem button is disabled when the child cannot afford it", () => {
  const children = [{ id: "kid1", name: "Kid 1", points: 5 }];
  const reward = { id: "ice-cream", name: "Ice cream", cost: 20, is_jackpot: false, assigned_to: [] };

  const { classic } = renderRow(makeCard({ selectedChildId: "kid1" }), reward, children);
  const claim = classic.control(/class="[^"]*claim-btn/);

  assert.ok(claim);
  assert.equal(claim.disabled, true);
  assert.match(claim.attrs, /cant-afford/);
});
