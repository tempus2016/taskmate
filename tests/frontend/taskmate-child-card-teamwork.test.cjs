const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// Teamwork chores (#928): the child card shows "N / M joined" with the
// joiners' avatars, a Done tap joins (or leaves, once in), and only the join
// that fills the team takes the ordinary completion path.

const { get } = loadCard("taskmate-child-card.js");
const ChildCard = get("taskmate-child-card");

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];

function carWash(team) {
  return {
    id: "car",
    name: "Wash the car",
    points: 10,
    time_category: "anytime",
    assigned_to: [],
    due_days: [],
    schedule_mode: "specific_days",
    assignment_mode: "everyone",
    ...(team ? { team } : {}),
  };
}

function makeCard({ team, design = "classic", completions = [] } = {}) {
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design });
  const calls = [];
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [
            { id: "kid1", name: "Mia", chore_order: [] },
            { id: "kid2", name: "Leo", chore_order: [], avatar: "mdi:robot" },
            { id: "kid3", name: "Ava", chore_order: [] },
          ],
          chores: [carWash(team)],
          todays_completions: completions,
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

const progress = (joined, size) => localize("child.team_progress", { joined, size });

for (const design of DESIGNS) {
  test(`teamwork: ${design} shows who has joined`, () => {
    const { card } = makeCard({ team: { size: 3, joined: ["kid2"] }, design });
    const { markup } = render(card.render());
    assert.match(markup, new RegExp(progress(1, 3).replace(/\//g, "\\/")));
    assert.match(markup, /tm-team-av/, "the joiner's avatar is drawn");
    assert.match(markup, /mdi:robot/);
  });

  test(`teamwork: ${design} says so once this child is in`, () => {
    const { card } = makeCard({ team: { size: 3, joined: ["kid1", "kid2"] }, design });
    const { markup } = render(card.render());
    assert.match(markup, new RegExp(localize("child.team_you_joined").replace("'", ".")));
  });

  test(`teamwork: ${design} shows nothing for an ordinary chore`, () => {
    const { card } = makeCard({ design });
    assert.doesNotMatch(render(card.render()).markup, /tm-team/);
  });
}

for (const design of DESIGNS.filter((d) => d !== "classic")) {
  test(`teamwork: ${design} labels the button Join, then Leave`, () => {
    const labels = (team) => render(makeCard({ team, design }).card.render()).controls.map((c) => c.text);
    assert.ok(labels({ size: 3 }).includes(localize("child.team_join")));
    assert.ok(labels({ size: 3, joined: ["kid1"] }).includes(localize("child.team_leave")));
  });
}

test("teamwork: a join that leaves the team short records no optimistic completion", async () => {
  const { card, calls } = makeCard({ team: { size: 3, joined: ["kid2"] } });
  const chore = card.hass.states[ENTITY].attributes.chores[0];
  await card._handleComplete(chore, { id: "kid1", name: "Mia" });
  assert.deepEqual(calls.map((c) => c.service), ["complete_chore"]);
  assert.equal(Object.keys(card._optimisticCompletions).length, 0, "nothing is done yet, so nothing turns green");
  assert.ok(!card._celebrating, "and no celebration for a job not yet done");
});

test("teamwork: the join that fills the team completes like any other tap", async () => {
  const { card, calls } = makeCard({ team: { size: 2, joined: ["kid2"] } });
  const chore = card.hass.states[ENTITY].attributes.chores[0];
  await card._handleComplete(chore, { id: "kid1", name: "Mia" });
  assert.deepEqual(calls.map((c) => c.service), ["complete_chore"]);
  assert.ok(card._optimisticCompletions["car_kid1"], "this child's completion is on its way");
});

test("teamwork: a child already in the team taps to leave", async () => {
  const { card, calls } = makeCard({ team: { size: 3, joined: ["kid1"] } });
  const chore = card.hass.states[ENTITY].attributes.chores[0];
  await card._handleComplete(chore, { id: "kid1", name: "Mia" });
  // The card runs in a sandbox realm, so compare by value rather than identity.
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [
    { domain: "taskmate", service: "leave_team_chore", data: { chore_id: "car", child_id: "kid1" } },
  ]);
});

test("teamwork: leaving needs no photo even on a photo chore", async () => {
  const { card, calls } = makeCard({ team: { size: 3, joined: ["kid1"] } });
  const chore = { ...card.hass.states[ENTITY].attributes.chores[0], require_photo: true };
  let opened = false;
  card._openPhotoCapture = () => { opened = true; };
  await card._handleComplete(chore, { id: "kid1", name: "Mia" });
  assert.equal(opened, false);
  assert.equal(calls[0].service, "leave_team_chore");
});

test("teamwork: joining a photo chore asks for the photo first", async () => {
  const { card, calls } = makeCard({ team: { size: 3 } });
  const chore = { ...card.hass.states[ENTITY].attributes.chores[0], require_photo: true };
  let opened = false;
  card._openPhotoCapture = () => { opened = true; };
  await card._handleComplete(chore, { id: "kid1", name: "Mia" });
  assert.equal(opened, true);
  assert.equal(calls.length, 0);
});

test("teamwork: the classic row's tap joins through the same handler", async () => {
  const { card, calls } = makeCard({ team: { size: 3 } });
  await render(card.render()).control(/chore-card/).click();
  assert.equal(calls[0].service, "complete_chore");
});

test("teamwork: a finished team's row shows done, not progress", () => {
  const { card } = makeCard({
    team: { size: 2 },
    completions: [{ chore_id: "car", child_id: "kid1", approved: true, completed_at: new Date().toISOString() }],
  });
  const { markup } = render(card.render());
  assert.doesNotMatch(markup, /tm-team/);
});
