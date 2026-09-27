// Bounty board (#931): the bounty card and the panel's Bounties tab.
//
// The card has one layout that reads the design tokens, so every design must
// render the same rows and controls; this renders each of them.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const NOW = Date.now();
const iso = (ms) => new Date(NOW + ms).toISOString();
const H = 3600e3;
// Objects built inside the card's sandbox have that realm's prototypes.
const plain = (x) => JSON.parse(JSON.stringify(x));

const CHILDREN = [
  { id: "k1", name: "Malia" },
  { id: "k2", name: "Vaiha" },
  { id: "k3", name: "Isla" },
];

function hassWith(bounties) {
  const calls = [];
  return {
    calls,
    callService: async (domain, service, data) => { calls.push({ domain, service, data }); },
    states: {
      [ENTITY]: { state: "ok", attributes: { children: CHILDREN, bounties } },
    },
  };
}

const Card = loadCard("taskmate-bounty-card.js").get("taskmate-bounty-card");

function cardFor(bounties, { child = "k1", design = "classic" } = {}) {
  const card = new Card();
  card.setConfig({ entity: ENTITY, child_id: child, card_design: design });
  card.hass = hassWith(bounties);
  return card;
}

// The dialog's backdrop is itself clickable (it closes the dialog), and its
// markup contains every button inside it — so pick buttons by their own text.
const button = (view, text) => view.controls.find((c) => c.tag === "button" && c.text.includes(text));

const open = (extra = {}) => ({ id: "b1", title: "Wash the car", points: 50, icon: "mdi:car-wash", status: "open", claim_hours: 2, ...extra });

for (const design of DESIGNS) {
  test(`bounty card — ${design} shows an open bounty with a Claim button`, () => {
    const view = render(cardFor([open()], { design }).render());
    assert.ok(view.markup.includes("Wash the car"));
    assert.ok(view.markup.includes(localize("bounty.open_count", { count: 1 })));
    const claim = button(view, localize("bounty.claim"));
    assert.ok(claim && !claim.disabled, "Claim is offered");
    assert.ok(view.markup.includes(localize("bounty.claim_hint", { hours: 2 })));
  });

  test(`bounty card — ${design} shows my claim with Done and Give back`, () => {
    const b = open({ status: "claimed", claimed_by: "k1", claimed_at: iso(-H), claim_until: iso(H) });
    const view = render(cardFor([b], { design }).render());
    assert.ok(view.markup.includes("bb-row mine"));
    assert.ok(button(view, localize("bounty.done")));
    assert.ok(button(view, localize("bounty.give_back")));
  });
}

test("a bounty the child can't claim is hidden", () => {
  const view = render(cardFor([open({ eligible: ["k2"] })]).render());
  assert.ok(!view.markup.includes("Wash the car"));
  assert.ok(view.markup.includes(localize("bounty.empty")));
  assert.ok(view.markup.includes(localize("bounty.open_count", { count: 0 })));
});

test("a sibling's claim is dimmed with when it comes back", () => {
  const b = open({ status: "claimed", claimed_by: "k2", claimed_at: iso(-H), claim_until: iso(H) });
  const view = render(cardFor([b]).render());
  assert.ok(view.markup.includes("bb-row locked"));
  assert.ok(view.markup.includes(localize("bounty.sibling_on_it", { name: "Vaiha" })));
  assert.equal(button(view, localize("bounty.claim")), undefined, "nothing to claim");
});

test("holding a claim disables every other Claim button", () => {
  const mine = open({ id: "b2", title: "Rake leaves", status: "claimed", claimed_by: "k1", claimed_at: iso(-H), claim_until: iso(H) });
  const view = render(cardFor([mine, open()]).render());
  const claim = button(view, localize("bounty.claim"));
  assert.ok(claim.disabled);
  assert.ok(view.markup.includes(localize("bounty.finish_first")));
});

test("claiming asks first, then calls claim_bounty for this child", async () => {
  const card = cardFor([open()]);
  await button(render(card.render()), localize("bounty.claim")).click();
  assert.equal(card._dialog.kind, "claim");
  const view = render(card.render());
  assert.ok(view.markup.includes(localize("bounty.claim_title", { title: "Wash the car" })));
  await button(view, localize("bounty.claim_it", { points: 50 })).click();
  assert.deepEqual(plain(card.hass.calls), [{ domain: "taskmate", service: "claim_bounty", data: { bounty_id: "b1", child_id: "k1" } }]);
  assert.equal(card._dialog, null);
});

test("Done submits the bounty and cheers", async () => {
  const card = cardFor([open({ status: "claimed", claimed_by: "k1", claimed_at: iso(-H), claim_until: iso(H) })]);
  await button(render(card.render()), localize("bounty.done")).click();
  assert.deepEqual(plain(card.hass.calls[0]), { domain: "taskmate", service: "complete_bounty", data: { bounty_id: "b1", child_id: "k1" } });
  assert.equal(card._dialog.kind, "yay");
});

test("a photo bounty asks for the photo instead of submitting", async () => {
  const card = cardFor([open({ require_photo: true, status: "claimed", claimed_by: "k1", claimed_at: iso(-H), claim_until: iso(H) })]);
  const view = render(card.render());
  assert.ok(view.markup.includes(localize("bounty.photo_tag")));
  await button(view, localize("bounty.done")).click();
  assert.equal(card.hass.calls.length, 0);
  assert.equal(card._dialog.kind, "photo");
  assert.ok(render(card.render()).markup.includes(localize("bounty.photo_title")));
});

test("give back calls give_back_bounty", async () => {
  const card = cardFor([open({ status: "claimed", claimed_by: "k1", claimed_at: iso(-H), claim_until: iso(H) })]);
  await button(render(card.render()), localize("bounty.give_back")).click();
  assert.equal(card.hass.calls[0].service, "give_back_bounty");
});

test("a submitted bounty waits for a grown-up, with undo while it's allowed", async () => {
  const b = open({ status: "pending", claimed_by: "k1", completion_id: "c1", undo: true });
  const card = cardFor([b]);
  const view = render(card.render());
  assert.ok(view.markup.includes(localize("bounty.waiting", { points: 50 })));
  await button(view, localize("bounty.undo")).click();
  assert.deepEqual(plain(card.hass.calls[0]), { domain: "taskmate", service: "undo_chore", data: { completion_id: "c1" } });
  delete b.undo;
  assert.equal(button(render(cardFor([b]).render()), localize("bounty.undo")), undefined);
});

test("a completed bounty shows under Recently completed", () => {
  const view = render(cardFor([open({ status: "completed", claimed_by: "k1", points_awarded: 60 })]).render());
  assert.ok(view.markup.includes(localize("bounty.recent")));
  assert.ok(view.markup.includes(localize("bounty.you_earned", { points: 60 })));
});

test("the expiry counts down, and says so when there is none", () => {
  const withExpiry = render(cardFor([open({ expires_at: iso(26 * H + 60e3) })]).render()).markup;
  assert.ok(withExpiry.includes(localize("bounty.left", { time: localize("bounty.dur_days", { d: 1, h: 2 }) })));
  const none = render(cardFor([open()]).render()).markup;
  assert.ok(none.includes(localize("bounty.no_expiry")));
});

test("the card asks for a child when none is configured", () => {
  const card = cardFor([open()], { child: "ghost" });
  assert.ok(render(card.render()).markup.includes(localize("bounty.no_child")));
});

test("the card needs a child_id", () => {
  assert.throws(() => new Card().setConfig({ entity: ENTITY }));
});

// ── panel: Bounties tab ─────────────────────────────────────────────────────

const Panel = loadCard("taskmate-panel.js").get("taskmate-panel");

function panelWith(bounties) {
  const panel = Object.create(Panel.prototype);
  panel._t = (key, params = {}) => localize(key, params);
  panel._timeAgo = () => "just now";
  panel._state = { children: CHILDREN, bounties, completions: [], settings: {} };
  return panel;
}

test("panel lists active bounties with Release on a claim", () => {
  const panel = panelWith([
    open(),
    open({ id: "b2", title: "Rake leaves", status: "claimed", claimed_by: "k2", claim_until: iso(H) }),
    open({ id: "b3", title: "Sort recycling", status: "pending", claimed_by: "k1", completion_id: "c9" }),
  ]);
  const markup = panel._renderBountiesTab();
  assert.ok(markup.includes("Wash the car") && markup.includes("Rake leaves"));
  assert.ok(!markup.includes("Sort recycling"), "waiting approval lives in its own tab");
  assert.ok(markup.includes('data-act="release-bounty" data-id="b2"'));
  assert.ok(markup.includes(localize("panel.bounty_tab_pending", { count: 1 })));
});

test("panel's Waiting approval tab approves through the chore approval", () => {
  const panel = panelWith([open({ id: "b3", status: "pending", claimed_by: "k1", completion_id: "c9" })]);
  panel._bountySubTab = "pending";
  const markup = panel._renderBountiesTab();
  assert.ok(markup.includes('data-act="approve-chore" data-id="c9"'));
  assert.ok(markup.includes('data-act="reject-chore" data-id="c9"'));
});

test("panel's approval queue names a bounty completion", () => {
  const panel = panelWith([open({ status: "pending", claimed_by: "k1", completion_id: "c9" })]);
  panel._esc = (v) => String(v ?? "");
  panel._safePhotoUrl = () => "";
  panel._state.chores = [];
  panel._state.pending_completions = [{ id: "c9", chore_id: "b1", bounty_id: "b1", child_id: "k1", submitted_points: 50, completed_at: iso(0) }];
  const markup = panel._renderActivityTab();
  assert.ok(markup.includes("Wash the car"));
  assert.ok(markup.includes("mdi:flag-outline"));
});

test("panel's post dialog offers the expiry quick picks and every child", () => {
  const panel = panelWith([]);
  panel._openDialog = (d) => { panel._dialog = d; };
  panel._openBountyDialog(null);
  const markup = panel._renderBountyDialog();
  for (const key of ["panel.bounty_exp_none", "panel.bounty_exp_tonight", "panel.bounty_exp_24h", "panel.bounty_exp_weekend", "panel.bounty_exp_pick"]) {
    assert.ok(markup.includes(localize(key)), key);
  }
  for (const c of CHILDREN) assert.ok(markup.includes(`data-act="toggle-bounty-el" data-id="${c.id}"`));
  assert.ok(markup.includes('data-act="save-bounty"'));
});

test("panel's edit dialog on a claimed bounty only offers points and expiry", () => {
  const panel = panelWith([open({ status: "claimed", claimed_by: "k1", claim_until: iso(H) })]);
  panel._openDialog = (d) => { panel._dialog = d; };
  panel._openBountyDialog("b1");
  const markup = panel._renderBountyDialog();
  assert.ok(markup.includes(localize("panel.bounty_claimed_lock_note")));
  assert.ok(!markup.includes('data-act="toggle-bounty-el"'));
  assert.ok(/data-field="title"[^>]*disabled/.test(markup));
  assert.ok(!/data-field="points"[^>]*disabled/.test(markup));
});

test("panel turns the expiry quick picks into future instants", () => {
  const panel = panelWith([]);
  const now = Date.now();
  assert.equal(panel._bountyExpiryIso({ exp_mode: "none" }), null);
  const day = Date.parse(panel._bountyExpiryIso({ exp_mode: "24h" }));
  assert.ok(Math.abs(day - (now + 24 * H)) < 5000);
  for (const mode of ["tonight", "weekend"]) {
    const t = new Date(panel._bountyExpiryIso({ exp_mode: mode }));
    assert.ok(t.getTime() > now && t.getHours() === 20, mode);
  }
  assert.equal(new Date(panel._bountyExpiryIso({ exp_mode: "weekend" })).getDay(), 0);
});
