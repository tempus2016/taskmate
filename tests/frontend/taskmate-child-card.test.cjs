const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const { get } = loadCard("taskmate-child-card.js", {
  window: { __taskmate_badge_id: (b) => b.badge_id },
});
const ChildCard = get("taskmate-child-card");

const NUDGE = localize("badges.one_more");

/** A badge the child has not earned yet, sitting `remaining` short of its target. */
function unearned(remaining, { target = 10, pct = 90 } = {}) {
  return {
    badge_id: "builtin.perfect_weeks_10",
    name: "10 Perfect Weeks",
    icon: "mdi:trophy",
    tier: "gold",
    progress_pct: pct,
    closest_criterion: { metric: "perfect_weeks", current: target - remaining, target },
  };
}

function makeCard({ available = [], config = {} } = {}) {
  const card = new ChildCard();
  card.setConfig({ entity: "sensor.taskmate_overview", child_id: "kid1", ...config });
  card.hass = {
    states: {
      "sensor.taskmate_overview": {
        attributes: {
          children: [{ id: "kid1", name: "Mia", points: 12 }],
          chores: [],
          points_icon: "mdi:star",
          points_name: "Stars",
        },
      },
      "sensor.taskmate_mia_badges": { attributes: { earned: [], available } },
    },
  };
  return card;
}

// ── The nudge itself ─────────────────────────────────────────────────────
// Distance is measured in remaining units, never percent: 90% of a 10-week
// badge is one week away, 90% of a 100-point badge is ten points away. Only
// the last one left earns the line, so it stays rare enough to mean something.

for (const { name, badge, config, expected } of [
  { name: "one away earns the line", badge: unearned(1), expected: true },
  { name: "two away stays quiet", badge: unearned(2), expected: false },
  { name: "a long way off stays quiet", badge: unearned(7, { pct: 30 }), expected: false },
  {
    name: "a high percentage on a big target is not one away",
    badge: unearned(10, { target: 100, pct: 90 }),
    expected: false,
  },
  {
    name: "a badge with no criteria never nudges",
    badge: { badge_id: "manual.helper", name: "Helper", tier: "bronze", progress_pct: 99, closest_criterion: null },
    expected: false,
  },
  { name: "show_badge_nudge: false turns it off", badge: unearned(1), config: { show_badge_nudge: false }, expected: false },
]) {
  test(`badge nudge — ${name}`, () => {
    const card = makeCard({ available: [badge], config });
    const nudge = card._badgeNudgeText(card._nextBadge(card._resolveBadgesEntity({ id: "kid1", name: "Mia" })));
    assert.equal(nudge, expected ? NUDGE : "");
  });
}

test("badge nudge — an already-met criterion does not nudge", () => {
  const card = makeCard({ available: [unearned(0)] });
  assert.equal(card._badgeNudgeText(card._nextBadge(card._resolveBadgesEntity({ id: "kid1", name: "Mia" }))), "");
});

// ── Both render paths ────────────────────────────────────────────────────
// The card draws itself twice: a classic path and a designed path shared by
// playroom/console/cleanpro/accessible. A feature added to one and not the
// other is invisible on four of the five designs, which has bitten this card
// before — so every design renders the line here.

for (const design of ["classic", "playroom", "console", "cleanpro", "accessible"]) {
  test(`badge nudge — ${design} shows the line when one away`, () => {
    const card = makeCard({ available: [unearned(1)], config: { card_design: design } });
    assert.match(render(card.render()).markup, new RegExp(NUDGE));
  });

  test(`badge nudge — ${design} omits the line when two away`, () => {
    const card = makeCard({ available: [unearned(2)], config: { card_design: design } });
    assert.doesNotMatch(render(card.render()).markup, new RegExp(NUDGE));
  });
}
