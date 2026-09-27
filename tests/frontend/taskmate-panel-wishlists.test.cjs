// Admin panel → Wishlists (#932): approve, pledge, fulfil.
//
// Wish names, links and pledge names are typed by children and relatives and
// the panel builds its markup as strings, so these also pin the escaping and
// the http(s)-only rule for links.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

const TaskMatePanel = loadCard("taskmate-panel.js").get("taskmate-panel");

const IMG = "/api/taskmate/image/" + "a".repeat(32) + ".jpg?authSig=x";

function panelWith(wishes, extra = {}) {
  const panel = Object.create(TaskMatePanel.prototype);
  panel._t = (key, params = {}) => [key, ...Object.values(params)].join(":");
  panel._state = {
    children: [{ id: "mia", name: "Malia" }, { id: "leo", name: "Vaiha" }],
    rewards: [],
    settings: { points_name: "Stars" },
    wishes,
    ...extra,
  };
  return panel;
}

const pending = {
  id: "w1", child_id: "mia", name: "Hamster <ball>", target: 150, suggested_target: 150, status: "pending",
  link: "javascript:alert(1)", pledges: [], saved: 0, pledged: 0, remaining: 150, funded: false,
};
const saving = {
  id: "w2", child_id: "mia", name: "Lego", target: 600, status: "active", saved: 260, pledged: 60, remaining: 280,
  funded: false, link: "https://www.lego.com/x", image_url: IMG,
  pledges: [{ id: "p1", name: "Grandma <3", points: 60, message: "Well done", created_at: "2026-09-20T10:00:00Z" }],
};
const handover = {
  id: "w3", child_id: "leo", name: "Kite", target: 80, status: "redeem_requested", saved: 80, pledged: 0, remaining: 0,
  funded: true, claim_id: "claim-9", pledges: [],
};

test("the tab lists waiting, active and pledged wishes", () => {
  const html = panelWith([pending, saving, handover])._renderWishlistsTab();
  assert.ok(html.includes('data-act="wish-approve" data-id="w1"'));
  assert.ok(html.includes('data-wish-target="w1"'));
  assert.ok(html.includes('data-act="wish-pledge" data-id="w2"'));
  assert.ok(html.includes('data-act="wish-fulfil" data-id="claim-9"'), "fulfil approves the wish's reward claim");
  assert.ok(html.includes('data-act="wish-unpledge" data-id="w2" data-pledge="p1"'));
});

test("names are escaped and only http(s) links are emitted", () => {
  const html = panelWith([pending, saving])._renderWishlistsTab();
  assert.ok(html.includes("Hamster &lt;ball&gt;") && !html.includes("Hamster <ball>"));
  assert.ok(html.includes("Grandma &lt;3"));
  assert.ok(!html.includes("javascript:"));
  assert.ok(html.includes('href="https://www.lego.com/x" target="_blank" rel="noopener noreferrer"'));
  assert.ok(html.includes(`src="${IMG}"`));
});

test("a foreign picture URL is never used as an image source", () => {
  const html = panelWith([{ ...saving, image_url: "https://evil.example/x.png" }])._renderWishlistsTab();
  assert.ok(!html.includes("evil.example"));
});

test("the child filter narrows every section", () => {
  const panel = panelWith([pending, saving, handover]);
  panel._wishChild = "leo";
  const html = panel._renderWishlistsTab();
  assert.ok(html.includes("Kite") && !html.includes("Lego"));
});

test("the nav counts what waits on a parent", () => {
  const panel = panelWith([pending, saving, handover]);
  const item = panel._sidebarGroups().flatMap(g => g.items).find(i => i.id === "wishlists");
  assert.equal(item.count, 2);
});

test("the pledge dialog is capped at what the wish still needs", () => {
  const panel = panelWith([saving]);
  panel._dialog = { kind: "wish-pledge", data: { wish_id: "w2", name: "", points: 999, message: "" } };
  const html = panel._renderWishPledgeDialog();
  assert.ok(html.includes('data-act="wish-pledge-amt" data-points="280"'));
  assert.ok(html.includes('data-act="wish-pledge-who" data-name="Grandma &lt;3"'), "names used before are offered");
  assert.ok(html.includes("panel.wish_pledge_preview:600:600"));
});

test("a wishlist claim reads as the wish in the approvals list", () => {
  const panel = panelWith([handover], {
    reward_claims: [{ id: "claim-9", reward_id: "w3", wish_id: "w3", child_id: "leo", approved: false, claimed_at: "2026-09-27T10:00:00Z" }],
    pending_reward_claims: [{ id: "claim-9", reward_id: "w3", wish_id: "w3", child_id: "leo", approved: false, claimed_at: "2026-09-27T10:00:00Z" }],
  });
  panel._timeAgo = () => "now";
  const html = panel._renderActivityTab();
  assert.ok(html.includes("panel.activity_claimed_text:Vaiha:Kite"));
  assert.ok(!html.includes("panel.activity_deleted_reward"));
});
