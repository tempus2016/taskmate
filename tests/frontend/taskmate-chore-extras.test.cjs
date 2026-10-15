const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// Estimated minutes ("about N min left") and quantity chores ("how many
// pages?") on the child card, on every design (two-render-paths rule), plus
// the reference photo beside the evidence on the approvals card.

const { get } = loadCard("taskmate-child-card.js");
const ChildCard = get("taskmate-child-card");

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];

function chore(over = {}) {
  return {
    id: "read", name: "Read", points: 2, time_category: "anytime", assigned_to: [], due_days: [],
    schedule_mode: "specific_days", assignment_mode: "everyone", ...over,
  };
}

function makeCard({ chores, design = "classic", completions = [] } = {}) {
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design });
  const calls = [];
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", chore_order: [] }],
          chores,
          todays_completions: completions,
          chore_availability: {},
          today_day_of_week: "wednesday",
          points_icon: "mdi:star",
        },
      },
    },
    callService: async (domain, service, data) => { calls.push({ domain, service, data }); },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card._playSound = () => {};
  card._spawnConfetti = () => {};
  return { card, calls };
}

for (const design of DESIGNS) {
  test(`minutes: ${design} adds up what is left today`, () => {
    const { card } = makeCard({
      design,
      chores: [chore({ id: "a", estimated_minutes: 10 }), chore({ id: "b", name: "Bins", estimated_minutes: 15 })],
      completions: [{ chore_id: "a", child_id: "kid1", approved: true, completed_at: new Date().toISOString() }],
    });
    const { markup } = render(card.render());
    assert.ok(markup.includes(localize("child.minutes_left", { minutes: 15 })), "only the outstanding chore counts");
    assert.ok(markup.includes(localize("child.minutes_tag", { minutes: 15 })), "the row carries its own estimate");
  });

  test(`quantity: ${design} shows the per-unit rate`, () => {
    const { card } = makeCard({ design, chores: [chore({ quantity_unit: "pages" })] });
    const { markup } = render(card.render());
    assert.ok(markup.includes(localize("child.quantity_rate", { points: 2, unit: "pages" })));
  });
}

test("minutes: nothing is drawn when no chore has an estimate", () => {
  const { card } = makeCard({ chores: [chore()] });
  const { markup } = render(card.render());
  assert.ok(!markup.includes("tm-minutes-left"));
});

test("minutes: the card option turns the line off", () => {
  const { card } = makeCard({ chores: [chore({ estimated_minutes: 5 })] });
  card.setConfig({ entity: ENTITY, child_id: "kid1", show_minutes_left: false });
  const { markup } = render(card.render());
  assert.ok(!markup.includes("tm-minutes-left"));
});

test("quantity: a tap asks how many instead of completing", async () => {
  const { card, calls } = makeCard({ chores: [chore({ quantity_unit: "pages", quantity_max: 30 })] });
  const attrs = card.hass.states[ENTITY].attributes;
  await card._handleComplete(attrs.chores[0], attrs.children[0]);
  assert.equal(calls.length, 0, "no service call before the child says how many");
  assert.ok(card._quantityCapture, "the sheet opens");
  card._setQuantity(12);
  const { markup } = render(card._renderQuantityCapture());
  assert.ok(markup.includes(localize("child.quantity_worth", { points: 24 })), "shows what 12 pages is worth");
  await card._submitQuantityCapture();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].service, "complete_chore");
  assert.equal(calls[0].data.quantity, 12);
});

test("quantity: the cap holds and zero is refused", async () => {
  const { card, calls } = makeCard({ chores: [chore({ quantity_unit: "laps", quantity_max: 5 })] });
  const attrs = card.hass.states[ENTITY].attributes;
  await card._handleComplete(attrs.chores[0], attrs.children[0]);
  card._setQuantity(50);
  assert.equal(card._quantityCapture.value, 5);
  card._setQuantity(0);
  await card._submitQuantityCapture();
  assert.equal(calls.length, 0);
  assert.ok(card._quantityCapture.error);
});

// ── Approvals card: the reference photo ────────────────────────────────────

const approvals = loadCard("taskmate-approvals-card.js");
const ApprovalsCard = approvals.get("taskmate-approvals-card");
const PENDING = "sensor.taskmate_pending_approvals";

function makeApprovals(design, completion) {
  const card = new ApprovalsCard();
  card.setConfig({ entity: PENDING, card_design: design });
  card.hass = {
    states: {
      [PENDING]: {
        state: "1",
        attributes: { chore_completions: [completion], reward_claims: [], mandatory_misses: [] },
      },
    },
    callService: async () => {},
  };
  return card;
}

const COMPLETION = {
  completion_id: "c1", type: "chore", child_name: "Mia", child_id: "kid1", chore_name: "Make bed", chore_id: "bed",
  points: 3, time_category: "anytime", completed_at: new Date().toISOString(),
  reference_image_url: "/api/taskmate/image/goal.jpg?authSig=x", quantity: 12, quantity_unit: "pages",
};

for (const design of DESIGNS) {
  test(`approvals: ${design} shows the reference picture and the quantity`, () => {
    const card = makeApprovals(design, COMPLETION);
    const { markup } = render(card.render());
    assert.match(markup, /\/api\/taskmate\/image\/goal\.jpg/, "reference picture drawn");
    assert.match(markup, /12 pages/, "quantity drawn");
  });
}

test("approvals: a foreign reference URL is never rendered", () => {
  const card = makeApprovals("classic", { ...COMPLETION, reference_image_url: "https://evil.example/x.jpg" });
  const { markup } = render(card.render());
  assert.ok(!markup.includes("evil.example"));
});

test("approvals: tapping opens the side-by-side comparison", () => {
  const card = makeApprovals("classic", { ...COMPLETION, photo_url: "/api/taskmate/photo/p.jpg" });
  card._openCompare(null, "/api/taskmate/image/goal.jpg", "/api/taskmate/photo/p.jpg", "Make bed");
  const { markup } = render(card._renderCompare());
  assert.ok(markup.includes(localize("approvals.reference_label")));
  assert.ok(markup.includes(localize("approvals.evidence_label")));
});
