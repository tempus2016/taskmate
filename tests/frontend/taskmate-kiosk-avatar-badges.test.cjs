const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

// #1112: the kiosk child screen carries the child card's avatar picker and
// badges (earned strip + next-up progress), so it can stand in for it.

const ENTITY = "sensor.taskmate_overview";
const BADGES = "sensor.taskmate_mia_badges";
const OPTIONS = [
  { icon: "mdi:cat", label: "Cat", unlocked: true },
  { icon: "mdi:rocket", label: "Rocket", unlocked: true },
  { icon: "mdi:crown", label: "Crown", unlocked: false, requirement: "Level 5" },
];

function setup({ config = {}, child = {}, badges = null } = {}) {
  const kiosk = loadCard("taskmate-kiosk-card.js");
  const Kiosk = kiosk.get("taskmate-kiosk-card");
  const card = new Kiosk();
  card.setConfig({ entity: ENTITY, children: [{ child_id: "kid1" }], ...config });
  const calls = [];
  const states = { [ENTITY]: { state: "ok", attributes: {
    children: [{ id: "kid1", name: "Mia", points: 10, avatar: "mdi:cat", avatar_options: OPTIONS, ...child }],
    chores: [], todays_completions: [], points_icon: "mdi:star",
  } } };
  if (badges) states[BADGES] = { state: String((badges.earned || []).length), attributes: badges };
  card.hass = { locale: { language: "en" }, states, callService: async (...a) => { calls.push(a); } };
  return { card, calls };
}

const childScreen = (card) => {
  card._kid = "kid1";
  card._screen = "child";
  return render(card._renderChild(card._entry("kid1"), card._attrs())).markup;
};
const kid = (card) => card._attrs().children[0];

test("the head avatar is a button that opens the picker when more than one avatar is unlocked", () => {
  const { card } = setup();
  assert.match(childScreen(card), /km-av-btn/);
  assert.doesNotMatch(childScreen(card), /km-av-picker/);
  card._avatarPicker = true;
  const markup = childScreen(card);
  assert.match(markup, /km-av-picker/);
  assert.match(markup, /km-av-opt\s+current/);
  assert.match(markup, /km-av-opt locked/);
  assert.match(markup, /mdi:lock/);
});

test("no picker with one unlocked avatar, or when the card option says no", () => {
  const one = setup({ child: { avatar_options: OPTIONS.map((o, i) => ({ ...o, unlocked: i === 0 })) } }).card;
  assert.doesNotMatch(childScreen(one), /km-av-btn/);
  const off = setup({ config: { allow_avatar_change: false } }).card;
  assert.doesNotMatch(childScreen(off), /km-av-btn/);
  assert.match(childScreen(off), /km-face head/);
});

test("choosing an avatar calls choose_avatar for that child and closes the picker", async () => {
  const { card, calls } = setup();
  card._avatarPicker = true;
  await card._chooseAvatar(kid(card), "mdi:rocket");
  assert.equal(card._avatarPicker, false);
  assert.equal(JSON.stringify(calls), JSON.stringify([["taskmate", "choose_avatar", { child_id: "kid1", icon: "mdi:rocket" }]]));
});

test("picking the current avatar sends nothing", async () => {
  const { card, calls } = setup();
  await card._chooseAvatar(kid(card), "mdi:cat");
  assert.equal(calls.length, 0);
});

test("going back to the picker closes an open avatar picker", () => {
  const { card } = setup();
  card._avatarPicker = true;
  card._resetToPicker();
  assert.equal(card._avatarPicker, false);
});

test("the badges tile shows earned badges and the closest started badge", () => {
  const { card } = setup({ badges: {
    earned: [{ badge_id: "b1", name: "First", icon: "mdi:medal", tier: "gold" }],
    available: [
      { badge_id: "b2", name: "Untouched", progress_pct: 0 },
      { badge_id: "b3", name: "Ten chores", tier: "silver", progress_pct: 90, closest_criterion: { current: 9, target: 10 } },
      { badge_id: "b4", name: "Halfway", progress_pct: 50 },
    ],
  } });
  const markup = childScreen(card);
  assert.match(markup, /km-badges/);
  assert.match(markup, /km-badge-row/);
  assert.match(markup, /Ten chores/);
  assert.match(markup, /9 \/ 10/);
  assert.match(markup, /badges\.one_more|One more/);
  assert.doesNotMatch(markup, /Untouched|Halfway/);
});

test("more than five earned badges collapse into a +N count", () => {
  const earned = Array.from({ length: 8 }, (_, i) => ({ badge_id: `b${i}`, name: `B${i}`, tier: "bronze" }));
  const { card } = setup({ badges: { earned, available: [] } });
  assert.match(childScreen(card), /\+3/);
});

test("no badges tile without badges, or when the card option says no", () => {
  assert.doesNotMatch(childScreen(setup().card), /km-badges/);
  assert.doesNotMatch(childScreen(setup({ badges: { earned: [], available: [] } }).card), /km-badges/);
  const off = setup({ config: { show_badges: false }, badges: { earned: [{ badge_id: "b1", tier: "gold" }], available: [] } }).card;
  assert.doesNotMatch(childScreen(off), /km-badges/);
});
