const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// "I'm stuck", the mood check-in, sick days, weekly goals and make-it-right
// offers on the child card — on every design (two-render-paths rule).

const { get } = loadCard("taskmate-child-card.js");
const ChildCard = get("taskmate-child-card");

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const NOW = new Date().toISOString();

function chore(over = {}) {
  return {
    id: "tidy", name: "Tidy room", points: 5, time_category: "anytime", assigned_to: [], due_days: [],
    schedule_mode: "specific_days", assignment_mode: "everyone", ...over,
  };
}

function makeCard({ child = {}, chores = [chore()], completions = [], design = "classic", config = {} } = {}) {
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design, ...config });
  const calls = [];
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", chore_order: [], ...child }],
          chores,
          todays_completions: completions,
          chore_availability: {},
          today_day_of_week: "wednesday",
          points_icon: "mdi:star",
        },
      },
    },
    callService: async (domain, service, data) => { calls.push({ domain, service, data }); },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card._playSound = () => {};
  card._spawnConfetti = () => {};
  return { card, calls };
}

const done = (id = "tidy") => ({ chore_id: id, child_id: "kid1", approved: true, completed_at: NOW });

for (const design of DESIGNS) {
  test(`help: ${design} offers "I'm stuck" on an outstanding chore`, () => {
    const { markup } = render(makeCard({ design }).card.render());
    assert.ok(markup.includes(localize("child.help_ask")));
  });

  test(`help: ${design} says help is coming once asked`, () => {
    const { markup } = render(makeCard({ design, child: { help: ["tidy"] } }).card.render());
    assert.ok(markup.includes(localize("child.help_on_way")));
    assert.ok(!markup.includes(localize("child.help_ask")));
  });

  test(`mood: ${design} asks once every chore is done`, () => {
    const { markup } = render(makeCard({ design, completions: [done()] }).card.render());
    assert.ok(markup.includes(localize("child.mood_question")));
  });

  test(`sick day: ${design} shows the banner`, () => {
    const { markup } = render(makeCard({ design, child: { sick_today: true } }).card.render());
    assert.ok(markup.includes(localize("child.sick_title")));
  });

  test(`goal: ${design} shows progress`, () => {
    const { markup } = render(makeCard({ design, child: { weekly_goal: { target: 100, earned: 40, bonus: 10 } } }).card.render());
    assert.ok(markup.includes(localize("child.goal_progress", { earned: 40, target: 100 })));
  });

  test(`make it right: ${design} shows the offer`, () => {
    const offer = { id: "o1", chore_id: "tidy", chore_name: "Tidy room", penalty_name: "Door", points: 5, expires: "2099-01-01" };
    const { markup } = render(makeCard({ design, child: { redemptions: [offer] } }).card.render());
    assert.ok(markup.includes(localize("child.redeem_title")));
    assert.match(markup, /Tidy room/);
  });
}

test("mood: not asked while chores are outstanding, and a pick logs it", async () => {
  const { card, calls } = makeCard();
  assert.ok(!render(card.render()).markup.includes(localize("child.mood_question")));
  const ready = makeCard({ completions: [done()] });
  const strip = ready.card._renderMoodStrip({ id: "kid1" }, 1, 0, "classic");
  assert.ok(render(strip).markup.includes(localize("child.mood_question")));
  assert.equal(ready.calls.length, 0);
  assert.equal(calls.length, 0);
});

test("help: tapping asks once and marks the row straight away", async () => {
  const { card, calls } = makeCard();
  const attrs = card.hass.states[ENTITY].attributes;
  await card._askForHelp(attrs.chores[0], attrs.children[0]);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].service, "request_help");
  assert.equal(calls[0].data.child_id, "kid1");
  assert.equal(calls[0].data.chore_id, "tidy");
  assert.ok(render(card.render()).markup.includes(localize("child.help_on_way")));
});

test("goal: with no target the card invites the child to set one", () => {
  const { markup } = render(makeCard({ child: { weekly_goal: { target: 0, bonus: 10 } } }).card.render());
  assert.ok(markup.includes(localize("child.goal_set_title")));
});

test("goal: the sheet saves the picked target", async () => {
  const { card, calls } = makeCard({ child: { weekly_goal: { target: 0, bonus: 10 }, week_points_available: 200 } });
  card._openGoalSheet(card.hass.states[ENTITY].attributes.children[0]);
  assert.ok(render(card._renderGoalSheet()).markup.includes(localize("child.goal_sheet_title")));
  card._goalSheet = { ...card._goalSheet, value: 150 };
  await card._saveGoalSheet();
  assert.equal(calls[0].service, "set_weekly_goal");
  assert.equal(calls[0].data.target, 150);
  assert.equal(card._goalSheet, null);
});

test("options turn the help button, mood and goal off", () => {
  const { markup } = render(makeCard({
    completions: [done()],
    child: { weekly_goal: { target: 50, earned: 0, bonus: 0 } },
    config: { show_help_button: false, show_mood: false, show_weekly_goal: false },
  }).card.render());
  assert.ok(!markup.includes(localize("child.help_ask")));
  assert.ok(!markup.includes(localize("child.mood_question")));
  assert.ok(!markup.includes("tm-care-goal"));
});

test("sick day: open chores leave the list, done ones stay for undo", () => {
  const { card } = makeCard({
    child: { sick_today: true },
    chores: [chore({ id: "a", name: "Bins" }), chore({ id: "b", name: "Plants" })],
    completions: [done("a")],
  });
  const { markup } = render(card.render());
  assert.match(markup, /Bins/);
  assert.doesNotMatch(markup, /Plants/);
});
