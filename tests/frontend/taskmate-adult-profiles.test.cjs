// Adult profiles (#1061).
//
// Parents who log their own chores get a profile marked is_adult. Family-wide
// cards leave those profiles out unless the card sets show_adults, and then
// list them after the kids. A card pinned to one child_id is untouched, so an
// adult can still have a card of their own.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

const OVERVIEW = "sensor.taskmate_overview";
const CHILDREN = [
  { id: "mum", name: "Mum", points: 90, is_adult: true },
  { id: "k1", name: "Ella", points: 40 },
  { id: "k2", name: "Finn", points: 30 },
];

const resolver = loadCard("taskmate-attr-resolver.js", { sandbox: { queueMicrotask: () => {} } }).window;
const family = resolver.__taskmate_family_children;
const ids = (list) => list.map((c) => c.id);

test("adults are left out by default", () => {
  assert.deepEqual(ids(family(CHILDREN, {})), ["k1", "k2"]);
});

test("show_adults brings them back after the kids", () => {
  assert.deepEqual(ids(family(CHILDREN, { show_adults: true })), ["k1", "k2", "mum"]);
});

test("a card pinned to one child gets the full list to pick from", () => {
  assert.deepEqual(ids(family(CHILDREN, { child_id: "mum" })), ["mum", "k1", "k2"]);
});

test("a family with no adults keeps its list as it was", () => {
  const kids = CHILDREN.slice(1);
  assert.equal(family(kids, {}), kids);
});

test("the editor only offers the toggle once the family has an adult", () => {
  const hass = (children) => ({ states: { [OVERVIEW]: { state: "1", attributes: { children } } } });
  assert.equal(resolver.__taskmate_adults_field(hass(CHILDREN.slice(1)), { entity: OVERVIEW }).length, 0);
  assert.equal(resolver.__taskmate_adults_field(hass(CHILDREN), { entity: OVERVIEW })[0].name, "show_adults");
});

function leaderboard(config) {
  const Card = loadCard("taskmate-leaderboard-card.js", {
    window: { __taskmate_attrs: resolver.__taskmate_attrs, __taskmate_family_children: family },
  }).get("taskmate-leaderboard-card");
  const card = new Card();
  card.setConfig({ entity: OVERVIEW, ...config });
  card.hass = { states: { [OVERVIEW]: { state: "1", attributes: { children: CHILDREN } } } };
  return render(card.render()).markup;
}

test("the leaderboard hides an adult unless show_adults is set", () => {
  assert.ok(!leaderboard({}).includes("Mum"));
  assert.ok(leaderboard({ show_adults: true }).includes("Mum"));
});

// ── Family-wide cards that still listed adults (#1071) ─────────────────────
// Each card is loaded with the real family filter and editor field from the
// resolver, so these fail if a card stops calling them.

const ADULT_HELPERS = {
  __taskmate_attrs: resolver.__taskmate_attrs,
  __taskmate_family_children: family,
  __taskmate_adults_field: resolver.__taskmate_adults_field,
};
const hassWith = (attributes) => ({ states: { [OVERVIEW]: { state: "1", attributes: { children: CHILDREN, ...attributes } } } });
const DESIGNED = "playroom";
// Arrays built inside a card's sandbox have that realm's prototypes.
const plain = (x) => JSON.parse(JSON.stringify(x));

// Rewards card

const RewardsCard = loadCard("taskmate-rewards-card.js", { window: ADULT_HELPERS }).get("taskmate-rewards-card");
const RewardsEditor = loadCard("taskmate-rewards-card.js", { window: ADULT_HELPERS }).get("taskmate-rewards-card-editor");

const TV = { id: "tv", name: "Extra TV", cost: 20, assigned_to: [] };
const PIZZA = { id: "pizza", name: "Pizza night", cost: 30, assigned_to: ["mum", "k1"] };
const JACKPOT = (allocs) => ({
  id: "jp", name: "Trampoline", cost: 100, is_jackpot: true, assigned_to: [],
  pool_allocations: allocs, jackpot_pool_total: Object.values(allocs).reduce((a, b) => a + b, 0),
});

function rewardsCard(config, rewards = [TV, PIZZA]) {
  const card = new RewardsCard();
  card.config = { entity: OVERVIEW, ...config };
  card.hass = hassWith({ rewards });
  card.willUpdate();
  return card;
}

const rewardsMarkup = (card, design) => {
  card.config = { ...card.config, card_design: design };
  return render(card.render()).markup;
};

for (const design of ["classic", DESIGNED]) {
  test(`rewards (${design}): the child tabs hide an adult unless show_adults is set`, () => {
    const hidden = rewardsMarkup(rewardsCard({}), design);
    assert.ok(hidden.includes("Ella") && hidden.includes("Finn"));
    assert.ok(!hidden.includes("Mum"), "adult tab or badge leaked");
    assert.ok(rewardsMarkup(rewardsCard({ show_adults: true }), design).includes("Mum"));
  });

  test(`rewards (${design}): a card pinned to the adult still shows her`, () => {
    const card = rewardsCard({ child_id: "mum" });
    assert.ok(rewardsMarkup(card, design).includes("Mum"));
  });

  test(`rewards (${design}): the jackpot breakdown drops an adult with nothing in it`, () => {
    const card = rewardsCard({}, [JACKPOT({ k1: 10, k2: 5 })]);
    const d = card._rewardData(JACKPOT({ k1: 10, k2: 5 }), CHILDREN);
    assert.deepEqual(plain(d.childContributions.map((c) => c.child.id)), ["k1", "k2"]);
    const markup = rewardsMarkup(card, design);
    assert.ok(!markup.includes("Mum"));
    if (design !== "classic") assert.equal(markup.split('class="chip rw-contrib"').length - 1, 2);
  });

  test(`rewards (${design}): the jackpot breakdown keeps an adult who put points in`, () => {
    const card = rewardsCard({}, [JACKPOT({ mum: 40, k1: 10, k2: 5 })]);
    const d = card._rewardData(JACKPOT({ mum: 40, k1: 10, k2: 5 }), CHILDREN);
    assert.deepEqual(plain(d.childContributions.map((c) => c.child.id)), ["k1", "k2", "mum"]);
    assert.equal(d.currentStars, 55);
    const markup = rewardsMarkup(card, design);
    if (design === "classic") {
      assert.ok(markup.includes("<strong>Mum</strong>"));
      assert.ok(markup.includes("55/100"));
    } else {
      assert.equal(markup.split('class="chip rw-contrib"').length - 1, 3);
    }
  });
}

test("rewards: the default selection is the first kid, not the adult", () => {
  assert.equal(rewardsCard({})._selectedChildId, "k1");
  assert.equal(rewardsCard({ show_adults: true })._selectedChildId, "k1");
});

test("rewards: a selected adult moves back to a kid once show_adults is off", () => {
  const card = rewardsCard({ show_adults: true });
  card._selectedChildId = "mum";
  card.willUpdate();
  assert.equal(card._selectedChildId, "mum");
  card.config = { entity: OVERVIEW };
  card.willUpdate();
  assert.equal(card._selectedChildId, "k1");
});

test("rewards: a pinned card keeps the adult's badge on the reward", () => {
  const pinned = rewardsCard({ child_id: "k1" });
  assert.ok(render(pinned.render()).markup.includes("Mum"));
});

test("rewards: the editor offers the Show adults toggle", () => {
  const editor = new RewardsEditor();
  editor.setConfig({ entity: OVERVIEW });
  editor.hass = hassWith({});
  assert.ok(render(editor.render()).markup.length > 0);
  assert.equal(editor._computeLabel({ name: "show_adults" }), "Show adults");
  assert.equal(editor._computeHelper({ name: "show_adults" }), "Include adult profiles on this card");
});

// Bounty card — always pinned to one child, but its "who can claim" avatar
// row for an open-to-everyone bounty is family-wide.

const BountyCard = loadCard("taskmate-bounty-card.js", { window: ADULT_HELPERS }).get("taskmate-bounty-card");
const BountyEditor = loadCard("taskmate-bounty-card.js", { window: ADULT_HELPERS }).get("taskmate-bounty-card-editor");
const BOUNTY = { id: "b1", title: "Wash the car", points: 50, icon: "mdi:car-wash", status: "open", claim_hours: 2 };

function bountyCard(config) {
  const card = new BountyCard();
  card.setConfig({ entity: OVERVIEW, ...config });
  card.hass = hassWith({ bounties: [BOUNTY] });
  return card;
}

test("bounty: an open-to-everyone bounty hides the adult unless show_adults is set", () => {
  assert.deepEqual(plain(bountyCard({ child_id: "k1" })._everyoneIds()), ["k1", "k2"]);
  assert.ok(!render(bountyCard({ child_id: "k1" }).render()).markup.includes('title="Mum"'));
  assert.deepEqual(plain(bountyCard({ child_id: "k1", show_adults: true })._everyoneIds()), ["k1", "k2", "mum"]);
  assert.ok(render(bountyCard({ child_id: "k1", show_adults: true }).render()).markup.includes('title="Mum"'));
});

test("bounty: the adult's own card still lists her", () => {
  assert.deepEqual(plain(bountyCard({ child_id: "mum" })._everyoneIds()), ["k1", "k2", "mum"]);
});

test("bounty: a bounty that names its claimers is shown as named", () => {
  const card = bountyCard({ child_id: "k1" });
  card.hass = hassWith({ bounties: [{ ...BOUNTY, eligible: ["mum", "k1"] }] });
  assert.ok(render(card.render()).markup.includes('title="Mum"'));
});

test("bounty: the editor offers the Show adults toggle", () => {
  const editor = new BountyEditor();
  editor.setConfig({ entity: OVERVIEW, child_id: "k1" });
  editor.hass = hassWith({});
  assert.equal(editor._computeLabel({ name: "show_adults" }), "Show adults");
  assert.equal(editor._computeHelper({ name: "show_adults" }), "Include adult profiles on this card");
});

// Bonuses / penalties — the shared incentive base's child picker.

function incentive(tag) {
  const loaded = loadCard("taskmate-incentive-card.js", {
    window: ADULT_HELPERS,
    transform: (src) => src.replace("export function createIncentiveCard", "function createIncentiveCard")
      + `\ncreateIncentiveCard({ tag: "${tag}", kind: "bonus", idKey: "bonus_id", i18n: "bonuses", attr: "bonuses",`
      + ` icon: "mdi:star", headerIcon: "mdi:star", applyIcon: "mdi:plus", sign: "+", dpts: (n) => "+" + n,`
      + ` accent: "#2e7d32", designHd: "#2e7d32", designIcons: {}, cardName: "x", cardDesc: "x", bannerName: "X", bannerColor: "#000" });`,
    sandbox: { console: { info() {}, log() {}, warn() {}, error() {} } },
  });
  return { Card: loaded.get(tag), Editor: loaded.get(`${tag}-editor`) };
}

const { Card: BonusCard, Editor: BonusEditor } = incentive("taskmate-bonuses-card");

function bonusCard(config) {
  const card = new BonusCard();
  card.setConfig({ entity: OVERVIEW, ...config });
  card.hass = hassWith({ bonuses: [{ id: "x", name: "Helped out", points: 5 }] });
  return card;
}

for (const design of ["classic", DESIGNED]) {
  test(`bonuses (${design}): the child picker hides an adult unless show_adults is set`, () => {
    const hidden = render(bonusCard({ card_design: design }).render()).markup;
    assert.ok(hidden.includes("Ella") && !hidden.includes("Mum"));
    assert.ok(render(bonusCard({ card_design: design, show_adults: true }).render()).markup.includes("Mum"));
  });
}

test("bonuses: the first kid is selected by default, and a stale adult selection falls back", () => {
  assert.equal(bonusCard({})._getSelectedChild().id, "k1");
  const card = bonusCard({});
  card._selectedChildId = "mum";
  assert.equal(card._getSelectedChild().id, "k1");
});

test("bonuses: the editor offers the Show adults toggle", () => {
  const editor = new BonusEditor();
  editor.setConfig({ entity: OVERVIEW });
  editor.hass = hassWith({});
  assert.equal(editor._computeLabel({ name: "show_adults" }), "Show adults");
  assert.equal(editor._computeHelper({ name: "show_adults" }), "Include adult profiles on this card");
});

// ── The editor toggle shows what the card has saved (#1071) ────────────────
// ha-form draws a field from its data object, so a card saved with
// show_adults: true has to hand that value back or the toggle reads off.

function formDataValues(tree, out = []) {
  if (Array.isArray(tree)) tree.forEach((v) => formDataValues(v, out));
  else if (tree && tree.__tmTemplate) tree.values.forEach((v) => formDataValues(v, out));
  else if (tree && typeof tree === "object") out.push(tree);
  return out;
}

for (const name of [
  "calendar", "graph", "leaderboard", "overview", "parent-dashboard", "points", "points-display",
  "reward-progress", "sticker-chart", "streak", "weekly", "rewards", "bonuses", "bounty",
]) {
  test(`${name}: the editor's Show adults toggle reflects a saved show_adults`, () => {
    const Editor = name === "bonuses"
      ? incentive("taskmate-bonuses-card").Editor
      : loadCard(`taskmate-${name}-card.js`, { window: ADULT_HELPERS, topLevelAwait: name === "sticker-chart" }).get(`taskmate-${name}-card-editor`);
    const editor = new Editor();
    editor.setConfig({ entity: OVERVIEW, show_adults: true, ...(name === "bounty" ? { child_id: "k1" } : {}) });
    editor.hass = hassWith({});
    const shown = formDataValues(editor.render()).some((v) => v.show_adults === true);
    assert.ok(shown, `${name} editor passes show_adults to ha-form`);
  });
}
