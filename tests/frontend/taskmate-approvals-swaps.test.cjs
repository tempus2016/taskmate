// Chore swap requests (#1275): every parent sees a pending swap in the
// approvals card and can approve or turn it down there, not only an admin in
// the panel. The parent dashboard counts it as waiting too.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const ApprovalsCard = loadCard("taskmate-approvals-card.js").get("taskmate-approvals-card");
const ENTITY = "sensor.taskmate_pending_approvals";
const DESIGNS = ["classic", "playroom", "console", "cleanpro"];

const SWAPS = [
  {
    request_id: "r1",
    type: "swap",
    child_id: "kid2",
    child_name: "Leo",
    from_child_id: "kid1",
    from_child_name: "Mia",
    chore_id: "bins",
    chore_name: "Bins",
    requested_at: "2026-11-19T07:30:00+00:00",
  },
];

function card(design, config = {}) {
  const calls = [];
  const c = new ApprovalsCard();
  c.setConfig({ entity: ENTITY, card_design: design, ...config });
  c.hass = {
    states: { [ENTITY]: { state: "1", attributes: { chore_completions: [], swap_requests: SWAPS } } },
    callService: async (domain, service, data) => calls.push({ domain, service, data }),
  };
  c._loading = {};
  return { c, calls };
}

const TEXT = () => localize("approvals.swap_request_text", { child: "Leo", chore: "Bins" });
const FROM = () => localize("approvals.swap_from", { name: "Mia" });

for (const design of DESIGNS) {
  test(`approvals card: ${design} lists a pending swap and who has the turn`, () => {
    const { markup } = render(card(design).c.render());
    assert.ok(markup.includes(TEXT()), "names the child and the chore");
    assert.ok(markup.includes(FROM()), "names who has the turn now");
    assert.ok(!markup.includes(localize("approvals.no_pending_approvals")), "not the empty state");
  });

  for (const [label, service] of [["approvals.approve", "approve_swap"], ["approvals.reject", "reject_swap"]]) {
    test(`approvals card: ${design} ${service} calls the parent service with the request id`, async () => {
      const { c, calls } = card(design);
      const { controls } = render(c.render());
      const btn = controls.find(
        (b) => (b.attr("title") || "") === localize(label) || (b.text || "").includes(localize(label)),
      );
      assert.ok(btn, `${label} button`);
      await btn.click();
      assert.equal(JSON.stringify(calls), JSON.stringify([{ domain: "taskmate", service, data: { request_id: "r1" } }]));
    });
  }
}

test("approvals card: a swap counts towards the pending badge", () => {
  const { markup } = render(card("classic").c.render());
  assert.match(markup, /class="pending-count"[^>]*>\s*1\s*</);
});

test("approvals card: a child-scoped card shows swaps either side of that child", () => {
  assert.equal(card("classic", { child_id: "kid1" }).c._swapRequests({ swap_requests: SWAPS }).length, 1);
  assert.equal(card("classic", { child_id: "kid2" }).c._swapRequests({ swap_requests: SWAPS }).length, 1);
  assert.equal(card("classic", { child_id: "kid3" }).c._swapRequests({ swap_requests: SWAPS }).length, 0);
});

test("approvals card: a swap with no current holder leaves the 'currently' line out", () => {
  const { c } = card("classic");
  assert.equal(c._swapFrom({ ...SWAPS[0], from_child_name: undefined }), "");
});

const Dash = loadCard("taskmate-parent-dashboard-card.js").get("taskmate-parent-dashboard-card");

for (const design of DESIGNS) {
  test(`parent dashboard: ${design} header counts a pending swap`, () => {
    const d = new Dash();
    d.setConfig({ entity: ENTITY, card_design: design });
    d.hass = {
      states: { [ENTITY]: { state: "1", attributes: { children: [], chores: [], chore_completions: [], swap_requests: SWAPS } } },
      callService: async () => {},
    };
    const { markup } = render(d.render());
    assert.match(markup, /class="(pending-badge|cnt)"[^>]*>(\s*<ha-icon[^>]*><\/ha-icon>)?\s*1\s*</);
  });
}

test("approvals card: classic lists swaps above missed chores (a swap only covers today)", () => {
  const c = new ApprovalsCard();
  c.setConfig({ entity: ENTITY, card_design: "classic" });
  const miss = { id: "m1", chore_id: "x", child_id: "kid1", child_name: "Mia", chore_name: "Hoover", due_date: "2026-11-17", period_id: "anytime", penalty_points: 0 };
  c.hass = { states: { [ENTITY]: { state: "2", attributes: { chore_completions: [], swap_requests: SWAPS, mandatory_misses: [miss] } } }, callService: async () => {} };
  c._loading = {};
  const { markup } = render(c.render());
  assert.ok(markup.indexOf(TEXT()) < markup.indexOf("Hoover"));
});
