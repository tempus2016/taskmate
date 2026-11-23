// Wish requests in the Parent Dashboard (#1284).
//
// A child's new wish waits for a parent, but the dashboard never showed it, so
// it sat unnoticed. The pending-approvals sensor now publishes
// `wish_requests`; the card lists them in the Approvals tab (every design),
// counts them in the tab and header badges, and approves at a chosen target
// or declines with an optional reason. show_wishes: false hides them.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const plain = (value) => JSON.parse(JSON.stringify(value));

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];

const WISHES = [
  {
    wish_id: "w1", type: "wish", child_id: "kid1", child_name: "Mia", wish_name: "Lego castle",
    target: 250, requested_at: "2026-11-20T08:00:00+00:00",
    link: "https://example.com/castle", image_url: "/api/taskmate/image/abc.jpg",
  },
  { wish_id: "w2", type: "wish", child_id: "kid1", child_name: "Mia", wish_name: "Bad link", target: 10,
    requested_at: "2026-11-20T09:00:00+00:00", link: "javascript:alert(1)", image_url: "https://evil.example/x.png" },
];

const Dash = loadCard("taskmate-parent-dashboard-card.js").get("taskmate-parent-dashboard-card");

function dash(design = "classic", config = {}, attrs = {}) {
  const d = new Dash();
  d.setConfig({ entity: ENTITY, card_design: design, ...config });
  d.calls = [];
  d.hass = {
    states: {
      [ENTITY]: {
        state: "2",
        attributes: { children: [{ id: "kid1", name: "Mia", points: 5 }], chores: [], chore_completions: [], wish_requests: WISHES, ...attrs },
      },
    },
    callService: async (domain, service, data) => d.calls.push({ domain, service, data }),
    callWS: async () => ({}),
  };
  d._activeSection = "approvals";
  return d;
}

for (const design of DESIGNS) {
  test(`${design}: pending wishes are listed in Approvals and counted`, () => {
    const { markup } = render(dash(design).render());
    assert.ok(markup.includes("Lego castle"));
    assert.ok(markup.includes(localize("dashboard.wishes_heading")));
    // The suggestion names the child; no placeholder is left raw.
    assert.ok(markup.includes(localize("dashboard.wish_suggested", { child: "Mia", points: "250", points_name: "Points" })));
    assert.doesNotMatch(markup, /\{[a-z_]+\}/);
    assert.ok(!markup.includes(localize("dashboard.empty_approvals")));
    // Header badge counts both wishes.
    assert.match(markup, /class="(pending-badge|cnt)"[^>]*>(\s*<ha-icon[^>]*><\/ha-icon>)?\s*2\s*</);
  });

  test(`${design}: show_wishes: false hides them and their count`, () => {
    const { markup } = render(dash(design, { show_wishes: false }).render());
    assert.ok(!markup.includes("Lego castle"));
    assert.ok(markup.includes(localize("dashboard.empty_approvals")));
    assert.doesNotMatch(markup, /class="(pending-badge|cnt)"/);
  });
}

test("only an http(s) link is rendered, and only our own images", () => {
  const d = dash("classic");
  d._signed = { "/api/taskmate/image/abc.jpg": "/api/taskmate/image/abc.jpg?authSig=x" };
  const { markup } = render(d.render());
  assert.ok(markup.includes('href="https://example.com/castle"'));
  assert.ok(!markup.includes("javascript:"));
  assert.ok(!markup.includes("evil.example"));
  assert.ok(markup.includes("authSig=x"));
});

test("approve opens a target form pre-filled with the child's suggestion, then calls approve_wish", async () => {
  const d = dash("playroom");
  let r = render(d.render());
  await r.control(`title="${localize("common.approve")}"`).click();
  assert.deepEqual(plain({ id: d._wishForm.id, mode: d._wishForm.mode, target: d._wishForm.target }), { id: "w1", mode: "approve", target: "250" });
  d._wishForm = { ...d._wishForm, target: "300" };
  r = render(d.render());
  await r.controls.find((c) => c.text === localize("common.approve")).click();
  assert.deepEqual(plain(d.calls), [{ domain: "taskmate", service: "approve_wish", data: { wish_id: "w1", target: 300 } }]);
  assert.equal(d._wishForm, null);
});

test("a bad target is refused in the card without calling the service", async () => {
  const d = dash("classic");
  d._wishForm = { id: "w1", mode: "approve", target: "2.5", reason: "", error: "" };
  await d._handleApproveWish(WISHES[0]);
  assert.deepEqual(plain(d.calls), []);
  assert.equal(d._wishForm.error, localize("dashboard.wish_err_target"));
});

test("decline sends the trimmed reason, or none when left empty", async () => {
  const d = dash("classic");
  d._wishForm = { id: "w1", mode: "decline", target: "", reason: "  Too dear  ", error: "" };
  await d._handleDeclineWish(WISHES[0]);
  d._wishForm = { id: "w2", mode: "decline", target: "", reason: "   ", error: "" };
  await d._handleDeclineWish(WISHES[1]);
  assert.deepEqual(plain(d.calls), [
    { domain: "taskmate", service: "decline_wish", data: { wish_id: "w1", reason: "Too dear" } },
    { domain: "taskmate", service: "decline_wish", data: { wish_id: "w2" } },
  ]);
});

test("tapping the same action again closes the form", () => {
  const d = dash("classic");
  d._openWishForm(WISHES[0], "decline");
  assert.equal(d._wishForm.mode, "decline");
  d._openWishForm(WISHES[0], "decline");
  assert.equal(d._wishForm, null);
});
