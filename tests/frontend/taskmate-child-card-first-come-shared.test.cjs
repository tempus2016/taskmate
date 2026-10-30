"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

const { get } = loadCard("taskmate-child-card.js", {
  window: { __taskmate_badge_id: (b) => b.badge_id },
});
const ChildCard = get("taskmate-child-card");

// first_come shares its daily_limit across the pool (#1159): "empty the
// dishwasher" twice a day, by whoever. Mia's card, with Leo as the sibling.

const ENTITY = "sensor.taskmate_overview";
const POINTS_ICON = "mdi:star";

function dishwasher(extra = {}) {
  return {
    id: "dish",
    name: "Empty the dishwasher",
    points: 3,
    time_category: "anytime",
    assigned_to: ["kid1", "kid2"],
    assignment_mode: "first_come",
    due_days: [],
    schedule_mode: "specific_days",
    daily_limit: 2,
    ...extra,
  };
}

function done(childId, n = 1) {
  return Array.from({ length: n }, (_, i) => ({
    chore_id: "dish",
    child_id: childId,
    approved: true,
    completed_at: new Date(Date.now() - (i + 1) * 60000).toISOString(),
  }));
}

function makeCard({ chore = dishwasher(), completions = [], config = {} } = {}) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: "kid1", ...config };
  const mia = { id: "kid1", name: "Mia", chore_order: [], weekly_chore_progress: {} };
  const leo = { id: "kid2", name: "Leo", chore_order: [], weekly_chore_progress: {} };
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [mia, leo],
          chores: [chore],
          todays_completions: completions,
          chore_availability: {},
          today_day_of_week: "wednesday",
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  return { card, child: mia };
}

/** Run the real filter pass, then render the classic row and the designed meta. */
function rows({ card, child }) {
  const attrs = card.hass.states[ENTITY].attributes;
  const chores = card._filterAndSortChores(attrs.chores, child);
  if (!chores.length) return null;
  const chore = chores[0];
  const todays = attrs.todays_completions;
  const state = card._isChoreDone(chore, child, todays);
  const firstComeLocked = !!chore._isFirstComeLocked && !state.done;
  const row = {
    chore, child, done: state.done, shared: state.shared, loading: false, onAct() {}, index: 0,
    dimmed: false, blocked: false, recLocked: false, firstComeLocked, weeklyDone: false,
    mandatory: false, photo: false, openEnded: false, design: "playroom",
  };
  return {
    state,
    chore,
    classic: render(card._renderChoreCard(chore, child, POINTS_ICON, todays, 0)),
    meta: render(card._designChoreMeta(row)),
  };
}

test("shared limit: a sibling's completion leaves the chore open, showing 1/2 on both paths", () => {
  const r = rows(makeCard({ completions: done("kid2") }));
  assert.ok(r, "one slot is left, so the chore stays on Mia's card");
  assert.equal(r.state.done, false);
  assert.equal(r.state.shared, 1);
  assert.match(r.classic.markup, /\(1\/2\)/);
  assert.doesNotMatch(r.classic.control(/chore-card/).attrs, /completed/);
  assert.match(r.meta.markup, /1\/2/);
});

test("shared limit: the same child may take both slots", () => {
  const r = rows(makeCard({ completions: done("kid1") }));
  assert.equal(r.state.done, false, "Mia's first go leaves the second slot open — for her too");
  assert.match(r.classic.markup, /\(1\/2\)/);
});

test("shared limit: once filled it hides for the whole pool by default", () => {
  assert.equal(rows(makeCard({ completions: [...done("kid1"), ...done("kid2")] })), null);
  assert.equal(rows(makeCard({ completions: done("kid2", 2) })), null);
});

test("shared limit: under dim, a child who took part sees it done", () => {
  const r = rows(makeCard({ completions: [...done("kid1"), ...done("kid2")], config: { first_come_claimed_mode: "dim" } }));
  assert.equal(r.state.done, true);
  assert.match(r.classic.control(/chore-card/).attrs, /completed/);
});

test("shared limit: under dim, a child who didn't take part is locked and told who did it", () => {
  const r = rows(makeCard({ completions: done("kid2", 2), config: { first_come_claimed_mode: "dim" } }));
  assert.equal(r.state.done, false);
  assert.equal(r.chore._isFirstComeLocked, true);
  assert.match(r.classic.markup, /Leo/);
  assert.doesNotMatch(r.meta.markup, /👥/, "a locked row carries no shared counter");
});

test("shared limit: a pool-wide parent completion uses a slot without counting as Mia's", () => {
  const parent = [{ chore_id: "dish", child_id: "__parent__", approved: true, completed_at: new Date().toISOString() }];
  const r = rows(makeCard({ completions: parent }));
  assert.equal(r.state.done, false);
  assert.equal(r.state.shared, 1);
});

test("shared limit: a limit of 1 is the classic race, with no counter", () => {
  const r = rows(makeCard({ chore: dishwasher({ daily_limit: 1 }) }));
  assert.doesNotMatch(r.classic.markup, /\(0\/1\)/);
  assert.doesNotMatch(r.meta.markup, /👥/);
  assert.equal(rows(makeCard({ chore: dishwasher({ daily_limit: 1 }), completions: done("kid2") })), null);
});
