// Streak freeze tokens (#925): the streak and child cards show "❄️ N".
//
// Both cards draw themselves on more than one path (classic, and a designed
// path shared by the other styles). A feature added to one path only is
// invisible on the rest with no error, so every design is rendered here.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const TOOLTIP = localize("streak.freezes_tooltip");

function hassWith(child) {
  return {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [child],
          chores: [],
          recent_completions: [],
          todays_completions: [],
          chore_availability: {},
          points_icon: "mdi:star",
          points_name: "Stars",
          today_day_of_week: "wednesday",
        },
      },
    },
  };
}

const kid = (extra = {}) => ({ id: "kid1", name: "Mia", points: 12, current_streak: 9, best_streak: 9, chore_order: [], ...extra });

// ── Streak card ──────────────────────────────────────────────────────────

const StreakCard = loadCard("taskmate-streak-card.js").get("taskmate-streak-card");

function streakMarkup(child, design) {
  const card = new StreakCard();
  card.setConfig({ entity: ENTITY, card_design: design });
  card.hass = hassWith(child);
  return render(card.render()).markup;
}

for (const design of DESIGNS) {
  test(`streak card — ${design} shows the token count`, () => {
    const markup = streakMarkup(kid({ streak_freezes: 2 }), design);
    assert.match(markup, /❄️ 2/);
    assert.ok(markup.includes(TOOLTIP), "the chip explains itself on hover");
  });

  test(`streak card — ${design} still shows a count of zero while the feature is on`, () => {
    assert.match(streakMarkup(kid({ streak_freezes: 0 }), design), /❄️ 0/);
  });

  test(`streak card — ${design} shows nothing when the feature is off`, () => {
    assert.doesNotMatch(streakMarkup(kid(), design), /❄️/);
  });
}

// ── Child card ───────────────────────────────────────────────────────────

const ChildCard = loadCard("taskmate-child-card.js", {
  window: { __taskmate_badge_id: (b) => b.badge_id },
}).get("taskmate-child-card");

function childMarkup(child, design) {
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design });
  card.hass = hassWith(child);
  card._loading = {};
  card._optimisticCompletions = {};
  return render(card.render()).markup;
}

for (const design of DESIGNS) {
  test(`child card — ${design} shows the token count in the header`, () => {
    assert.match(childMarkup(kid({ streak_freezes: 1 }), design), /❄️ 1/);
  });

  test(`child card — ${design} keeps the header clean with no tokens`, () => {
    assert.doesNotMatch(childMarkup(kid({ streak_freezes: 0 }), design), /❄️/);
    assert.doesNotMatch(childMarkup(kid(), design), /❄️/);
  });
}

test("child card — classic shows the count with or without a level", () => {
  assert.match(childMarkup(kid({ streak_freezes: 2, level: 3 }), "classic"), /❄️ 2/);
  assert.match(childMarkup(kid({ streak_freezes: 2 }), "classic"), /❄️ 2/);
});

// ── Activity card: zero-point token rows ─────────────────────────────────

const ActivityCard = loadCard("taskmate-activity-card.js").get("taskmate-activity-card");

function activityCard(design = "classic") {
  const card = new ActivityCard();
  card.hass = { states: {} };
  card.config = { entity: ENTITY, card_design: design };
  return card;
}

const FREEZE_ROW = {
  type: "points_removed",
  transaction_id: "t1",
  child_id: "kid1",
  child_name: "Mia",
  points: 0,
  reason: "Streak freeze used (2026-07-15)",
  completed_at: "2026-07-16T00:00:05Z",
};

for (const [reason, key, params] of [
  ["Streak freeze used (2026-07-15)", "activity.reason_streak_freeze_used", { date: "2026-07-15" }],
  ["Streak freeze earned (14 day streak!)", "activity.reason_streak_freeze_earned", { days: "14" }],
  ["Streak freezes adjusted (+2)", "activity.reason_streak_freeze_adjusted", { delta: "+2" }],
  ["Streak freezes adjusted (-1)", "activity.reason_streak_freeze_adjusted", { delta: "-1" }],
  ["Streak freeze reversed", "activity.reason_streak_freeze_reversed", {}],
]) {
  test(`activity — "${reason}" is localised`, () => {
    assert.equal(activityCard()._translateReason(reason), localize(key, params));
    assert.notEqual(localize(key, params), key, `${key} is missing from en.json`);
  });
}

test("activity — classic token row names the reason and never says 'lost 0'", () => {
  const markup = render(activityCard()._renderItem(FREEZE_ROW, { kid1: "Mia" }, "mdi:star", {})).markup;
  assert.ok(markup.includes(localize("activity.reason_streak_freeze_used", { date: "2026-07-15" })));
  assert.ok(markup.includes("mdi:snowflake"));
  assert.ok(!markup.includes(localize("activity.lost")), "a token row is not a points loss");
  assert.ok(!markup.includes("undo"), "a token row cannot be undone");
});

test("activity — designed token row has no points and no undo", () => {
  const d = activityCard("playroom")._describeEvent(FREEZE_ROW, { kid1: "Mia" }, "mdi:star", {});
  assert.equal(d.emoji, "❄️");
  assert.equal(`${d.sign}${d.pts}`, "");
  assert.equal(d.undo, null);
  assert.ok(render(d.text).markup.includes(localize("activity.reason_streak_freeze_used", { date: "2026-07-15" })));
});

test("activity — a real zero-point adjustment keeps its normal row", () => {
  const d = activityCard("playroom")._describeEvent(
    { ...FREEZE_ROW, reason: "Admin panel adjustment" },
    { kid1: "Mia" },
    "mdi:star",
    {},
  );
  assert.notEqual(d.emoji, "❄️");
});
