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

const ENTITY = "sensor.taskmate_overview";
const POINTS_ICON = "mdi:star";

/** A card wired to one child, one chore, and this week's progress so far. */
function makeWeeklyCard({ chore, weeklyProgress = {}, completionsToday = [], config = {} } = {}) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: "kid1", ...config };
  const child = { id: "kid1", name: "Mia", chore_order: [], weekly_chore_progress: weeklyProgress };
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [child],
          chores: [chore],
          todays_completions: completionsToday,
          chore_availability: {},
          today_day_of_week: "wednesday",
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  return { card, child };
}

function cello(extra = {}) {
  return {
    id: "cello",
    name: "Practise cello",
    points: 10,
    time_category: "anytime",
    assigned_to: [],
    due_days: [],
    schedule_mode: "specific_days",
    daily_limit: 1,
    weekly_target: 3,
    ...extra,
  };
}

/** Annotate through the real filter pass, then render both row shapes. */
function renderRow({ card, child }, { design = "playroom" } = {}) {
  const chores = card._filterAndSortChores(card.hass.states[ENTITY].attributes.chores, child);
  assert.equal(chores.length, 1, "the chore should still be on the card");
  const chore = chores[0];
  const todays = card.hass.states[ENTITY].attributes.todays_completions;
  const done = todays.some((c) => c.chore_id === chore.id && c.child_id === child.id);
  const row = {
    chore,
    child,
    done,
    loading: false,
    onAct() {
      row.acted = true;
    },
    index: 0,
    dimmed: false,
    blocked: false,
    recLocked: false,
    firstComeLocked: false,
    weeklyDone: !!chore._weeklyTargetMet && !done,
    mandatory: false,
    photo: false,
    openEnded: false,
    design,
  };
  return {
    chore,
    row,
    classic: render(card._renderChoreCard(chore, child, POINTS_ICON, todays, 0)),
    meta: render(card._designChoreMeta(row)),
    button: render(card._designDoneBtn(row, "DONE", "")),
  };
}

// ── progress is visible from the first tick ──────────────────────────────
// A quota the child can't see is just a chore that vanishes for no reason.

for (const { name, progress, expected } of [
  { name: "nothing done yet", progress: {}, expected: "0/3 this week" },
  { name: "part-way through", progress: { cello: 2 }, expected: "2/3 this week" },
  { name: "quota filled", progress: { cello: 3 }, expected: "3/3 this week" },
]) {
  test(`weekly target: ${name} reads the same on both render paths`, () => {
    const { classic, meta } = renderRow(makeWeeklyCard({ chore: cello(), weeklyProgress: progress }));
    assert.match(classic.markup, new RegExp(expected));
    assert.match(meta.markup, new RegExp(expected));
  });
}

test("weekly target: a chore without one shows no weekly counter", () => {
  const { classic, meta } = renderRow(makeWeeklyCard({ chore: cello({ weekly_target: 0 }) }));
  assert.doesNotMatch(classic.markup, /this week/);
  assert.doesNotMatch(meta.markup, /this week/);
});

// ── a filled quota stops being tappable ──────────────────────────────────
// The backend refuses the completion, so a live row would swallow the tap.

test("weekly target: a filled quota refuses the tap on the classic row", async () => {
  const card = makeWeeklyCard({ chore: cello(), weeklyProgress: { cello: 3 } });
  const { classic } = renderRow(card);
  const row = classic.control(/chore-card/);
  assert.ok(row, "the chore row should still be rendered");
  assert.match(row.attrs, /aria-disabled="true"/);
  assert.match(row.attrs, /recurrence-unavailable/, "and be dimmed so the reason is visible");
});

test("weekly target: a filled quota disables the designed DONE button", () => {
  const { button } = renderRow(makeWeeklyCard({ chore: cello(), weeklyProgress: { cello: 3 } }));
  assert.equal(button.controls[0].disabled, true);
});

test("weekly target: below the quota the row is still live", () => {
  const card = makeWeeklyCard({ chore: cello(), weeklyProgress: { cello: 2 } });
  const { classic, button } = renderRow(card);
  assert.match(classic.control(/chore-card/).attrs, /aria-disabled="false"/);
  assert.equal(button.controls[0].disabled, false);
});

// ── today's own tick stays undoable ──────────────────────────────────────
// Filling the quota with today's completion must not lock the child out of
// undoing it, exactly as the recurrence window doesn't.

test("weekly target: the completion that filled the quota can still be undone", () => {
  const card = makeWeeklyCard({
    chore: cello(),
    weeklyProgress: { cello: 3 },
    completionsToday: [{ chore_id: "cello", child_id: "kid1", approved: false }],
  });
  const { chore, classic, button } = renderRow(card);
  assert.equal(chore._weeklyTargetMet, false, "today's tick keeps the row live for an undo");
  assert.match(classic.control(/chore-card/).attrs, /aria-disabled="false"/);
  assert.equal(button.controls[0].disabled, false);
});

// ── the overview card's own idea of what is outstanding ──────────────────
// It drives both the "complete on behalf" list and the progress ring, so a
// quota-filled chore left in there means the ring can never reach 100%.

const overview = loadCard("taskmate-overview-card.js");
const OverviewCard = overview.get("taskmate-overview-card");

function overviewChores(weeklyProgress) {
  const card = new OverviewCard();
  card.config = { entity: ENTITY };
  const child = { id: "kid1", name: "Mia", weekly_chore_progress: weeklyProgress };
  const chores = [cello(), { ...cello({ weekly_target: 0 }), id: "dishes", name: "Dishes" }];
  return card
    ._childChoresToday(child, chores, { today_day_of_week: "wednesday", chore_availability: {} })
    .map((c) => c.id);
}

test("weekly target: the overview drops a chore whose quota is filled", () => {
  assert.deepEqual(overviewChores({ cello: 3 }), ["dishes"]);
});

test("weekly target: the overview keeps a chore still short of its quota", () => {
  assert.deepEqual(overviewChores({ cello: 2 }), ["cello", "dishes"]);
});

// ── a quota filled by today's own completions ────────────────────────────
// Found on ha-dev, not in a unit test: with daily_limit above 1 the row was
// neither done nor locked, so it still offered a DONE button that
// complete_chore refuses (#805 all over again). The week's remaining
// allowance has to cap today's, the way first_come clamps it to 1.

test("weekly target: a quota filled today reads as done, with undo still live", () => {
  const card = makeWeeklyCard({
    chore: cello({ weekly_target: 2, daily_limit: 5 }),
    weeklyProgress: { cello: 2 },
    completionsToday: [
      { chore_id: "cello", child_id: "kid1", approved: false },
      { chore_id: "cello", child_id: "kid1", approved: false },
    ],
  });
  const { chore, child } = { chore: card.card.hass.states[ENTITY].attributes.chores[0], child: card.child };
  const { done } = card.card._isChoreDone(chore, child, card.card.hass.states[ENTITY].attributes.todays_completions);
  assert.equal(done, true, "the week's remaining allowance caps today's");

  const { classic } = renderRow(card);
  const row = classic.control(/chore-card/);
  assert.match(row.attrs, /completed/, "the row shows its done state");
  assert.match(row.attrs, /aria-disabled="false"/, "so the completion can still be undone");
});

test("weekly target: under the quota a multi-per-day chore stays outstanding", () => {
  const card = makeWeeklyCard({
    chore: cello({ weekly_target: 3, daily_limit: 5 }),
    weeklyProgress: { cello: 1 },
    completionsToday: [{ chore_id: "cello", child_id: "kid1", approved: false }],
  });
  const chore = card.card.hass.states[ENTITY].attributes.chores[0];
  const { done } = card.card._isChoreDone(chore, card.child, card.card.hass.states[ENTITY].attributes.todays_completions);
  assert.equal(done, false, "two of the three are still owed");
});
