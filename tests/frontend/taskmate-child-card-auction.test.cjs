// Chore auctions (#982): a won occurrence on the child card and the calendar.
//
// The chores slice carries `auction` ({child_id, points}) on a chore whose
// occurrence today was won at auction. The winner alone gets the chore — in
// every assignment mode, "everyone" included — at the winning price, tagged
// "Won at auction" on BOTH render paths (the classic row and the designed
// meta line shared by the other designs).

const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const ChildCard = loadCard("taskmate-child-card.js", {
  window: { __taskmate_badge_id: (b) => b.badge_id },
}).get("taskmate-child-card");
const CalendarCard = loadCard("taskmate-calendar-card.js").get("taskmate-calendar-card");

const ENTITY = "sensor.taskmate_overview";
const TAG = localize("child.won_at_auction");
const CHILDREN = [
  { id: "kid1", name: "Mia", chore_order: [] },
  { id: "kid2", name: "Leo", chore_order: [] },
];

function bathroom(extra = {}) {
  return {
    id: "bath",
    name: "Clean the bathroom",
    points: 6,
    effective_points: 9,
    time_category: "anytime",
    assigned_to: [],
    due_days: [],
    schedule_mode: "specific_days",
    assignment_mode: "everyone",
    auction: { child_id: "kid2", points: 9 },
    ...extra,
  };
}

function cardFor(childId, chore) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: childId };
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: CHILDREN,
          chores: [chore],
          todays_completions: [],
          chore_availability: {},
          today_day_of_week: "wednesday",
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  return card;
}

const filtered = (childId, chore) => {
  const card = cardFor(childId, chore);
  const child = CHILDREN.find((c) => c.id === childId);
  return { card, child, chores: card._filterAndSortChores([chore], child) };
};

for (const mode of ["everyone", "alternating", "first_come"]) {
  test(`won at auction: only the winner sees an ${mode} chore today`, () => {
    const chore = bathroom({ assignment_mode: mode, assignment_current_child_id: mode === "alternating" ? "kid1" : "" });
    assert.equal(filtered("kid1", chore).chores.length, 0);
    assert.equal(filtered("kid2", chore).chores.length, 1);
  });
}

test("won at auction: the classic row carries the tag and the winning price", () => {
  const { card, child, chores } = filtered("kid2", bathroom());
  const view = render(card._renderChoreCard(chores[0], child, "mdi:star", [], 0));
  assert.ok(view.markup.includes(TAG));
  assert.match(view.markup, /\+9\b/);
});

test("won at auction: the designed meta line carries the tag", () => {
  const { card, child, chores } = filtered("kid2", bathroom());
  const row = { chore: chores[0], child, done: false, auction: true, mandatory: false, photo: false, openEnded: false };
  assert.ok(render(card._designChoreMeta(row)).markup.includes(TAG));
  const plainRow = { ...row, auction: false };
  assert.ok(!render(card._designChoreMeta(plainRow)).markup.includes(TAG));
});

test("won at auction: the designed row model reads the win (both paths wired)", () => {
  const source = readFileSync(path.join(__dirname, "../../custom_components/taskmate/www/taskmate-child-card.js"), "utf8");
  assert.match(source, /auction: !!\(chore\.auction && chore\.auction\.child_id\)/);
  assert.match(source, /class="auction-badge"/);
});

test("won at auction: a won chore is not offered as a swap", () => {
  const chore = bathroom({ assignment_mode: "alternating", assignment_current_child_id: "kid2" });
  const card = cardFor("kid1", chore);
  assert.equal(card._renderSwappable([chore], CHILDREN[0], "mdi:star"), "");
});

test("won at auction: the calendar places a won day on the winner alone", () => {
  const card = new CalendarCard();
  const chore = bathroom({ assignment_mode: "alternating", auction_wins: { "2026-10-04": "kid2" } });
  assert.equal(card._rotationRenderMode(chore, "kid2", "2026-10-04", "2026-10-01"), "active");
  assert.equal(card._rotationRenderMode(chore, "kid1", "2026-10-04", "2026-10-01"), "hidden");
  assert.equal(card._rotationRenderMode(chore, "kid1", "2026-10-05", "2026-10-01"), "rotating");
});
