const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// Multipart chores (#1253): a chore row shows "n/N steps", a tap opens the
// checklist instead of completing, and ticking the last step completes the
// chore through the ordinary path. Every design and pre-reader mode.

const { get } = loadCard("taskmate-child-card.js");
const ChildCard = get("taskmate-child-card");

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const STEPS = [
  { id: "s1", name: "Clothes away" },
  { id: "s2", name: "Toys in the box" },
  { id: "s3", name: "Make the bed" },
];

function tidy(stepDone) {
  return {
    id: "tidy",
    name: "Tidy bedroom",
    points: 10,
    time_category: "anytime",
    assigned_to: [],
    due_days: [],
    schedule_mode: "specific_days",
    assignment_mode: "everyone",
    steps: STEPS,
    ...(stepDone ? { step_done: { kid1: stepDone } } : {}),
  };
}

function makeCard({ stepDone, design = "classic", preReader = false } = {}) {
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design, ...(preReader ? { pre_reader: true } : {}) });
  const calls = [];
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", chore_order: [] }],
          chores: [tidy(stepDone)],
          todays_completions: [],
          chore_availability: {},
          today_day_of_week: "wednesday",
          points_icon: "mdi:star",
        },
      },
    },
    callService: async (domain, service, data) => {
      calls.push({ domain, service, data });
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card._playSound = () => {};
  card._spawnConfetti = () => {};
  return { card, calls };
}

const progress = (done, total) => localize("child.steps_progress", { done, total });

for (const design of DESIGNS) {
  test(`steps: ${design} row shows the progress`, () => {
    const { card } = makeCard({ stepDone: ["s1"], design });
    const { markup } = render(card.render());
    assert.ok(markup.includes(progress(1, 3)), "n/N steps is drawn");
  });

  test(`steps: ${design} tap opens the checklist instead of completing`, async () => {
    const { card, calls } = makeCard({ design });
    const child = { id: "kid1", name: "Mia" };
    await card._handleComplete(tidy(), child);
    assert.equal(calls.length, 0, "nothing is sent");
    assert.ok(card._stepsSheet, "the sheet is open");
    const { markup } = render(card.render());
    for (const s of STEPS) assert.ok(markup.includes(s.name), `step ${s.name} is listed`);
    assert.match(markup, /tm-steps-sheet/);
  });
}

test("steps: pre-reader tile shows one dot per step and opens the checklist", async () => {
  const { card, calls } = makeCard({ stepDone: ["s1", "s2"], preReader: true });
  const { markup } = render(card.render());
  assert.equal((markup.match(/tm-step-dot/g) || []).length, 3);
  assert.equal((markup.match(/tm-step-dot on/g) || []).length, 2);
  await card._handleComplete(tidy(["s1", "s2"]), { id: "kid1", name: "Mia" });
  assert.equal(calls.length, 0);
  assert.ok(card._stepsSheet);
});

test("steps: ticking a step only records the step", async () => {
  const { card, calls } = makeCard();
  const chore = tidy();
  const child = { id: "kid1", name: "Mia" };
  card._openStepsSheet(chore, child);
  await card._toggleStep(chore, child, STEPS[0]);
  assert.deepEqual(calls.map(c => c.service), ["set_chore_step"]);
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0].data)), { chore_id: "tidy", child_id: "kid1", step_id: "s1", done: true });
  assert.ok(card._stepsSheet, "the sheet stays open");
});

test("steps: unticking sends done false", async () => {
  const { card, calls } = makeCard({ stepDone: ["s1"] });
  const chore = tidy(["s1"]);
  await card._toggleStep(chore, { id: "kid1", name: "Mia" }, STEPS[0]);
  assert.equal(calls[0].data.done, false);
});

test("steps: the last tick completes the chore through the normal path", async () => {
  const { card, calls } = makeCard({ stepDone: ["s1", "s2"] });
  const chore = tidy(["s1", "s2"]);
  const child = { id: "kid1", name: "Mia" };
  card._openStepsSheet(chore, child);
  await card._toggleStep(chore, child, STEPS[2]);
  assert.deepEqual(calls.map(c => c.service), ["set_chore_step", "complete_chore"]);
  assert.equal(card._stepsSheet, null, "the sheet closes");
  assert.equal(card._celebrating, "tidy", "the normal celebration runs");
});

test("steps: a chore with every step ticked completes on a plain tap", async () => {
  const { card, calls } = makeCard({ stepDone: ["s1", "s2", "s3"] });
  await card._handleComplete(tidy(["s1", "s2", "s3"]), { id: "kid1", name: "Mia" });
  assert.deepEqual(calls.map(c => c.service), ["complete_chore"]);
});

test("steps: an ordinary chore shows no step progress", () => {
  const { card } = makeCard();
  card.hass.states[ENTITY].attributes.chores = [{ ...tidy(), steps: undefined }];
  const { markup } = render(card.render());
  assert.ok(!markup.includes("tm-steps-tag"));
});
