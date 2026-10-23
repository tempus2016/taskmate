const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// Reward extras: points-expiry warning, gifts, star ratings and the savings
// forecast on the child card (every design); limits, pictures and the gift
// picker on the rewards card; the panel's reward dialog, ratings, vouchers
// and settings.

const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const ENTITY = "sensor.taskmate_overview";
const IMG = "/api/taskmate/image/" + "a".repeat(32) + ".jpg?authSig=x";
const plain = (v) => JSON.parse(JSON.stringify(v));

function isoIn(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
const weekday = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { weekday: "long" });

function childCard({ design = "classic", child = {}, rewards = [] } = {}) {
  const ChildCard = loadCard("taskmate-child-card.js").get("taskmate-child-card");
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design });
  const calls = [];
  card.hass = {
    states: { [ENTITY]: { state: "ok", attributes: {
      children: [{ id: "kid1", name: "Vaiha", chore_order: [], points: 842, spendable_balance: 842, ...child }],
      chores: [{ id: "bed", name: "Make bed", points: 2, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", assignment_mode: "everyone" }],
      rewards,
      todays_completions: [], chore_availability: {}, today_day_of_week: "wednesday", points_icon: "mdi:star", points_name: "Stars",
    } } },
    callService: async (...args) => { calls.push(args); },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card._playSound = () => {};
  card._spawnConfetti = () => {};
  card._calls = calls;
  return card;
}

const LEGO = { id: "lego", name: "Lego set", cost: 1000, icon: "mdi:toy-brick", assigned_to: [], is_available: true, image_url: IMG };

for (const design of DESIGNS) {
  test(`child: ${design} shows expiry, gift, rating and forecast strips`, () => {
    const exp = isoIn(3);
    const card = childCard({
      design,
      rewards: [LEGO],
      child: {
        points_expiry: { points: 40, date: exp },
        gifts: [{ claim_id: "g1", reward_name: "Ice cream", reward_icon: "mdi:ice-cream", from_name: "Malia" }],
        rate_rewards: [{ claim_id: "c1", reward_name: "Cinema trip", reward_icon: "mdi:movie" }],
        earn_rate: 45,
      },
    });
    const { markup } = render(card.render());
    assert.ok(markup.includes(localize("child.expiry_title", { points: 40, points_name: "Stars", day: weekday(exp) })), "expiry");
    assert.ok(markup.includes(localize("child.gift_title", { name: "Malia", reward: "Ice cream" })), "gift");
    assert.ok(markup.includes(localize("child.gift_body")));
    assert.ok(markup.includes(localize("child.rate_title", { reward: "Cinema trip" })), "rating");
    assert.match(markup, /tm-care-forecast/);
    assert.ok(markup.includes("Lego set · 842/1000"));
    // (1000 - 842) / 45 → 4 days
    assert.ok(markup.includes(localize("child.forecast_body", { rate: 45, day: weekday(isoIn(4)) })), "forecast");
    assert.ok(markup.includes(`<img class="tm-reward-pic" src="${IMG}"`), "the reward picture replaces the icon");
  });
}

test("child: tapping a star rates the reward through the child-gated service", async () => {
  const card = childCard({ child: { rate_rewards: [{ claim_id: "c1", reward_name: "Cinema trip" }] } });
  const view = render(card.render());
  const stars = view.controls.filter((c) => c.attrs.includes("tm-rate-star"));
  assert.equal(stars.length, 3);
  await stars[1].click();
  assert.deepEqual(plain(card._calls), [["taskmate", "rate_reward", { child_id: "kid1", claim_id: "c1", stars: 2 }]]);
});

test("child: no forecast when earning ~0 or more than 60 days away, and nothing extra by default", () => {
  const slow = childCard({ rewards: [LEGO], child: { earn_rate: 2 } }); // 79 days
  assert.doesNotMatch(render(slow.render()).markup, /tm-care-forecast/);
  const none = childCard({ rewards: [LEGO], child: { earn_rate: 0.2 } });
  assert.doesNotMatch(render(none.render()).markup, /tm-care-forecast/);
  const plainCard = render(childCard({ rewards: [LEGO] }).render()).markup;
  assert.doesNotMatch(plainCard, /tm-care-(expiry|gift|rate|forecast)/);
});

test("child: the forecast skips jackpots, savings-jar rewards and other children's rewards", () => {
  const rewards = [
    { ...LEGO, id: "j", cost: 900, is_jackpot: true },
    { ...LEGO, id: "p", cost: 900, pool_enabled: true },
    { ...LEGO, id: "s", cost: 900, assigned_to: ["kid2"] },
    { ...LEGO, id: "ok", name: "Bike", cost: 950, image_url: "" },
  ];
  const { markup } = render(childCard({ rewards, child: { earn_rate: 20 } }).render());
  assert.ok(markup.includes("Bike · 842/950"));
  assert.match(markup, /<ha-icon icon="mdi:toy-brick">/);
});

test("child: an owed gift says who bought it", () => {
  const card = childCard({ child: { owed_rewards: [{ claim_id: "o1", reward_name: "Ice cream", reward_icon: "mdi:gift", days_owed: 0, from_name: "Malia" }] } });
  const { markup } = render(card.render());
  assert.ok(markup.includes(localize("child.gift_title", { name: "Malia", reward: "Ice cream" })));
});

// ── rewards card ────────────────────────────────────────────────────────

function rewardsCard({ gifting = false, children, selected = "kid1" } = {}) {
  const RewardsCard = loadCard("taskmate-rewards-card.js").get("taskmate-rewards-card");
  const card = new RewardsCard();
  card.config = { entity: ENTITY };
  const calls = [];
  card.hass = {
    states: { [ENTITY]: { attributes: { pending_reward_claims: [], children, ...(gifting ? { reward_gifting: true } : {}) } } },
    callService: async (...args) => { calls.push(args); },
  };
  card._selectedChildId = selected;
  card._calls = calls;
  return card;
}

const KIDS = [
  { id: "kid1", name: "Vaiha", points: 500, spendable_balance: 500 },
  { id: "kid2", name: "Malia", points: 100 },
  { id: "dad", name: "Dad", points: 0, is_adult: true },
];

function rows(card, reward) {
  const childMap = Object.fromEntries(KIDS.map((c) => [c.id, c]));
  return {
    classic: render(card._renderRewardRow(reward, "mdi:star", "Stars", childMap, KIDS)),
    designed: render(card._designRewardRow(reward, KIDS, "mdi:star", "Stars", "playroom")),
  };
}

test("rewards: a child at the limit sees 'again on' and a disabled claim button in every design", () => {
  const next = isoIn(5);
  const movie = { id: "movie", name: "Pick the movie", cost: 50, assigned_to: [], limit: { count: 1, period: "week" }, limit_reached: { kid1: next } };
  const { classic, designed } = rows(rewardsCard({ children: KIDS }), movie);
  const label = localize("rewards.limit_again", { day: weekday(next) });
  for (const view of [classic, designed]) {
    assert.ok(view.markup.includes(label));
    const claim = view.controls.find((c) => c.attrs.includes("claim-btn") || c.text === localize("rewards.claim_reward"));
    assert.ok(claim && claim.disabled, "claim is disabled");
  }
  // Another child is not limited.
  const other = rows(rewardsCard({ children: KIDS, selected: "kid2" }), movie);
  assert.ok(!other.classic.markup.includes(label));
});

test("rewards: a picture shows in both designs, falling back to the icon", () => {
  const card = rewardsCard({ children: KIDS });
  const withPic = rows(card, { id: "c", name: "Cinema", cost: 200, assigned_to: [], image_url: IMG });
  assert.ok(withPic.classic.markup.includes(`class="reward-pic" src="${IMG}"`));
  assert.ok(withPic.designed.markup.includes(`class="rw-pic" src="${IMG}"`));
  const foreign = rows(card, { id: "c", name: "Cinema", cost: 200, assigned_to: [], image_url: "https://evil.example/x.jpg" });
  assert.doesNotMatch(foreign.classic.markup + foreign.designed.markup, /evil\.example/);
  assert.match(foreign.designed.markup, /rw-emoji/);
});

test("rewards: with gifting on, the claim dialog asks who it is for and sends the recipient", async () => {
  const card = rewardsCard({ gifting: true, children: KIDS });
  const ice = { id: "ice", name: "Ice cream", cost: 60, assigned_to: [] };
  card._promptClaim(ice, KIDS[0]);
  let view = render(card._renderConfirmDialog("mdi:star", "Stars"));
  assert.ok(view.markup.includes(localize("rewards.gift_who")));
  assert.match(view.markup, /🎁 Malia/);
  assert.doesNotMatch(view.markup, /Dad/, "adults are never offered");
  assert.doesNotMatch(view.markup, /🎁 Vaiha/, "not yourself");
  await view.controls.find((c) => c.attrs.includes("gift-opt") && c.text === "🎁 Malia").click();
  view = render(card._renderConfirmDialog("mdi:star", "Stars"));
  assert.match(view.markup, /gift-opt on"[^>]*>🎁 Malia/);
  await card._confirmClaim();
  assert.deepEqual(plain(card._calls), [["taskmate", "claim_reward", { reward_id: "ice", child_id: "kid1", recipient_id: "kid2" }]]);
});

test("rewards: no gift picker when gifting is off or for a jackpot", () => {
  const off = rewardsCard({ children: KIDS });
  off._promptClaim({ id: "ice", name: "Ice cream", cost: 60, assigned_to: [] }, KIDS[0]);
  assert.doesNotMatch(render(off._renderConfirmDialog("mdi:star", "Stars")).markup, /gift-picker/);
  const jackpot = rewardsCard({ gifting: true, children: KIDS });
  jackpot._promptClaim({ id: "j", name: "Zoo", cost: 60, assigned_to: [], is_jackpot: true }, KIDS[0]);
  assert.doesNotMatch(render(jackpot._renderConfirmDialog("mdi:star", "Stars")).markup, /gift-picker/);
});

// ── panel ───────────────────────────────────────────────────────────────

// What window.open hands back in the panel's sandbox.
const popup = { win: null };

function panel(extra = {}) {
  const TaskMatePanel = loadCard("taskmate-panel.js", { window: { open: () => popup.win } }).get("taskmate-panel");
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => `${key}${Object.keys(params).length ? ":" + JSON.stringify(params) : ""}`;
  p._state = {
    children: [{ id: "kid1", name: "Vaiha" }, { id: "kid2", name: "Malia" }],
    rewards: [
      { id: "cinema", name: "Cinema trip", cost: 200, icon: "mdi:movie", assigned_to: [], image_url: IMG, limit_count: 1, limit_period: "week" },
      { id: "xbox", name: "30 min Xbox", cost: 40, icon: "mdi:controller", assigned_to: [] },
      { id: "pud", name: "Extra pudding", cost: 10, icon: "mdi:cupcake", assigned_to: [] },
    ],
    reward_claims: [
      { id: "a", reward_id: "cinema", child_id: "kid1", approved: true, rating: 3, approved_at: "2026-10-20T10:00:00Z" },
      { id: "b", reward_id: "cinema", child_id: "kid2", approved: true, rating: 2 },
      { id: "c", reward_id: "xbox", child_id: "kid1", approved: true },
      { id: "d", reward_id: "pud", child_id: "kid1", approved: false },
    ],
    owed_rewards: [{ claim_id: "a", child_id: "kid2", reward_name: "Cinema trip", days_owed: 1, from_name: "Vaiha" }],
    pool_allocations: [],
    settings: { points_name: "Stars", points_expiry_enabled: true, points_expiry_days: 60, reward_gifting_enabled: false },
    ...extra,
  };
  const sent = [];
  p._callWS = async (msg) => { sent.push(msg); return { ok: true, res: { html: "<p>voucher</p>" } }; };
  p._fetchState = async () => {};
  p._render = () => {};
  p._closeDialog = () => {};
  p._syncIconPickers = () => {};
  p._showToast = (kind, msg) => sent.push({ toast: kind, msg });
  p._sent = sent;
  return p;
}

test("panel: ratings table shows average, count and never-claimed rewards", () => {
  const p = panel();
  const html = p._renderRewardRatings(p._state.rewards);
  assert.match(html, /Cinema trip<\/td>\s*<td><span class="tm-rating-stars"[^>]*>★★★<\/span>/); // 2.5 rounds to 3
  assert.match(html, /panel\.ratings_claimed:\{&quot;count&quot;:2\}/);
  assert.match(html, /30 min Xbox<\/td>\s*<td>—<\/td>/);
  assert.match(html, /Extra pudding[\s\S]*panel\.ratings_claimed:\{&quot;count&quot;:0\}[\s\S]*panel\.ratings_retire/);
});

test("panel: the reward card shows the picture and the limit pill", () => {
  const p = panel();
  const html = p._renderRewardCard(p._state.rewards[0], "Stars");
  assert.match(html, /<img class="tm-reward-thumb" src="\/api\/taskmate\/image\/a+\.jpg\?authSig=x"/);
  assert.match(html, /panel\.reward_limit_pill_week:\{&quot;count&quot;:1\}/);
});

test("panel: the reward dialog has the picture well and the limit fields, and saves them", async () => {
  const p = panel();
  p._dialog = { kind: "reward", mode: "edit", data: { ...p._state.rewards[0], quantity_str: "", expires_at: "", available_days: [] } };
  const html = p._renderRewardDialog();
  assert.match(html, /data-act="chore-image-pick" data-field="image_url"/);
  assert.match(html, /data-section="limit" open/);
  assert.match(html, /data-field="limit_count"/);
  await p._doSaveReward();
  const msg = p._sent.find((m) => m.type === "taskmate/update_reward");
  assert.equal(msg.limit_count, 1);
  assert.equal(msg.limit_period, "week");
  assert.equal(msg.image_url, IMG, "the signed url goes back; the server strips the signature");
});

test("panel: owed rewards and the activity timeline offer a printable voucher", () => {
  const p = panel();
  const owed = p._renderOwedCard(p._state.children);
  assert.match(owed, /data-act="print-voucher" data-id="a"/);
  assert.match(owed, /panel\.reward_gift_from:\{&quot;name&quot;:&quot;Vaiha&quot;\}/);
  p._childInScope = () => true;
  p._inspections = () => [];
  p._inspectionEvents = () => [];
  p._timeAgo = () => "now";
  p._inspSlot = () => "";
  const html = p._timelineHtml(p._activityEvents());
  assert.match(html, /data-act="print-voucher" data-id="c"/);
});

test("panel: printing opens a tab and writes the server's page into it", async () => {
  const p = panel();
  const written = [];
  const win = { closed: false, close() { this.closed = true; }, document: { open() {}, write: (h) => written.push(h), close() {} } };
  popup.win = win;
  await p._printVoucher("a");
  const msg = p._sent[0];
  assert.equal(msg.type, "taskmate/print/reward_voucher");
  assert.equal(msg.claim_id, "a");
  assert.equal(msg.labels.for, "panel.voucher_for");
  assert.ok(msg.date_text);
  assert.deepEqual(written, ["<p>voucher</p>"]);
});

test("panel: a blocked pop-up or a failed print says so", async () => {
  const p = panel();
  popup.win = null;
  await p._printVoucher("a");
  assert.deepEqual(plain(p._sent), [{ toast: "err", msg: "panel.voucher_popup_blocked" }]);
  const win = { closed: false, close() { this.closed = true; }, document: {} };
  popup.win = win;
  p._sent.length = 0;
  p._callWS = async () => ({ ok: false, err: "Only an approved reward can be printed" });
  await p._printVoucher("d");
  assert.ok(win.closed, "the empty tab is closed again");
  assert.deepEqual(plain(p._sent), [{ toast: "err", msg: 'panel.voucher_failed:{"error":"Only an approved reward can be printed"}' }]);
});

test("panel: settings carry points expiry and gifting", () => {
  const p = panel();
  const html = p._renderRewardExtrasSettings(p._state.settings);
  assert.match(html, /data-setting="points_expiry_enabled" checked/);
  assert.match(html, /data-setting="points_expiry_days" value="60"/);
  assert.match(html, /data-setting="points_expiry_warn_days" value="7"/);
  assert.match(html, /data-setting="reward_gifting_enabled" >/);
});
