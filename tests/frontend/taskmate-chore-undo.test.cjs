// Child undo window (#918).
//
// The server marks each of today's completions a child may still take back
// (child_undo_pending / child_undo_until); the window is 0 by default, and then
// neither is ever set. These check the cards show an Undo action exactly while
// it's allowed, on the classic AND every designed render path and in picture
// mode, and that it goes through taskmate.undo_chore — never reject_chore,
// which stays the parent's route.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// The cards run in their own vm realm, so compare what they send as plain data.
const plain = (value) => JSON.parse(JSON.stringify(value));

class CustomEvent {
  constructor(type, init = {}) {
    this.type = type;
    this.detail = init.detail;
  }
}

let viewerIsParent = false;
const { get } = loadCard("taskmate-child-card.js", {
  window: { __taskmate_is_parent: () => viewerIsParent, __taskmate_badge_id: (b) => b.badge_id },
  sandbox: { CustomEvent },
});
const ChildCard = get("taskmate-child-card");
const RoutineCard = loadCard("taskmate-routine-card.js", { sandbox: { CustomEvent } }).get("taskmate-routine-card");

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const UNDO_LABEL = localize("child.undo_named", { name: "Dishes" });
const NOT_ALLOWED = localize("child.undo_not_allowed");

const future = (s = 60) => new Date(Date.now() + s * 1000).toISOString();
const past = (s = 60) => new Date(Date.now() - s * 1000).toISOString();

function dishes(extra = {}) {
  return {
    id: "dishes",
    name: "Dishes",
    points: 10,
    time_category: "anytime",
    assigned_to: [],
    due_days: [],
    schedule_mode: "specific_days",
    daily_limit: 1,
    ...extra,
  };
}

function completion(extra = {}) {
  return {
    completion_id: "comp1",
    chore_id: "dishes",
    child_id: "kid1",
    chore_name: "Dishes",
    approved: true,
    completed_at: new Date().toISOString(),
    bonus_subtask_id: "",
    ...extra,
  };
}

function makeCard({ completions = [], chores = [dishes()], config = {} } = {}) {
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", ...config });
  card.calls = [];
  card.hass = {
    callService: async (domain, service, data) => card.calls.push({ domain, service, data }),
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [
            { id: "kid1", name: "Mia", points: 10, chore_order: [] },
            { id: "kid2", name: "Leo", points: 0, chore_order: [] },
          ],
          chores,
          todays_completions: completions,
          chore_availability: {},
          today_day_of_week: "wednesday",
          points_icon: "mdi:star",
          points_name: "Stars",
        },
      },
    },
  };
  return card;
}

const undoButton = (card) => render(card.render()).control("tm-child-undo-btn");

// ── what shows ───────────────────────────────────────────────────────────

for (const design of DESIGNS) {
  test(`${design}: an auto-approved chore inside the window shows Undo`, () => {
    const card = makeCard({ completions: [completion({ child_undo_until: future() })], config: { card_design: design } });
    const button = undoButton(card);
    assert.ok(button, "the undo action is rendered");
    assert.match(button.text, new RegExp(UNDO_LABEL));
  });

  test(`${design}: a pending submission shows Undo until a parent reviews it`, () => {
    const card = makeCard({
      completions: [completion({ approved: false, child_undo_pending: true })],
      config: { card_design: design },
    });
    assert.ok(undoButton(card));
  });

  test(`${design}: window 0 (no undo fields) shows no Undo`, () => {
    const card = makeCard({ completions: [completion()], config: { card_design: design } });
    assert.equal(undoButton(card), undefined);
    assert.doesNotMatch(render(card.render()).markup, /tm-child-undo/);
  });

  test(`${design}: an expired window shows no Undo`, () => {
    const card = makeCard({ completions: [completion({ child_undo_until: past() })], config: { card_design: design } });
    assert.equal(undoButton(card), undefined);
  });

  test(`${design}: picture mode keeps the Undo action`, () => {
    const card = makeCard({
      completions: [completion({ child_undo_until: future() })],
      config: { card_design: design, pre_reader: true },
    });
    const { markup } = render(card.render());
    assert.match(markup, /pre-tile/, "picture tiles are what's rendered");
    assert.ok(undoButton(card));
  });
}

test("a sibling's undoable completion never shows on this child's card", () => {
  const card = makeCard({ completions: [completion({ child_id: "kid2", child_undo_until: future() })] });
  assert.equal(undoButton(card), undefined);
});

test("the Undo button calls undo_chore with only the completion id", async () => {
  const card = makeCard({ completions: [completion({ child_undo_until: future() })] });
  await undoButton(card).click();
  assert.deepEqual(plain(card.calls), [{ domain: "taskmate", service: "undo_chore", data: { completion_id: "comp1" } }]);
});

test("the strip lists each undoable completion, newest first", () => {
  const card = makeCard({
    chores: [dishes(), dishes({ id: "bins", name: "Bins" })],
    completions: [
      completion({ completed_at: past(30), child_undo_until: future(30) }),
      completion({ completion_id: "comp2", chore_id: "bins", chore_name: "Bins", child_undo_pending: true, approved: false }),
    ],
  });
  const labels = render(card.render()).controls.filter((c) => c.attrs.includes("tm-child-undo-btn")).map((c) => c.text);
  assert.deepEqual(plain(labels), [localize("child.undo_named", { name: "Bins" }), UNDO_LABEL]);
});

// ── tapping a done row ───────────────────────────────────────────────────

test("child tapping an undoable done row goes through undo_chore", async () => {
  viewerIsParent = false;
  const comp = completion({ child_undo_until: future() });
  const card = makeCard({ completions: [comp] });
  await card._handleUndo(dishes(), { id: "kid1" }, [comp]);
  assert.deepEqual(plain(card.calls.map((c) => c.service)), ["undo_chore"]);
});

test("child tapping a done row outside the window keeps the parent-only message", async () => {
  viewerIsParent = false;
  for (const comp of [completion(), completion({ child_undo_until: past() })]) {
    const card = makeCard({ completions: [comp] });
    await card._handleUndo(dishes(), { id: "kid1" }, [comp]);
    assert.deepEqual(card.calls, [], "no service call is made");
    assert.equal(card.dispatched.at(-1)?.detail?.message, NOT_ALLOWED);
  }
});

test("a parent's tap still rejects, whatever the window", async () => {
  viewerIsParent = true;
  try {
    const comp = completion({ child_undo_until: future() });
    const card = makeCard({ completions: [comp] });
    await card._handleUndo(dishes(), { id: "kid1" }, [comp]);
    assert.deepEqual(plain(card.calls.map((c) => c.service)), ["reject_chore"]);
  } finally {
    viewerIsParent = false;
  }
});

test("child undoing a bonus sub-task inside the window uses undo_chore", async () => {
  viewerIsParent = false;
  const bonus = completion({ completion_id: "b1", bonus_subtask_id: "dry", child_undo_until: future() });
  const card = makeCard({ completions: [completion(), bonus] });
  await card._handleUndoBonusSubtask(dishes(), { id: "dry" }, { id: "kid1" }, [completion(), bonus]);
  assert.deepEqual(plain(card.calls), [{ domain: "taskmate", service: "undo_chore", data: { completion_id: "b1" } }]);
});

test("child undoing a locked bonus sub-task gets the parent-only message", async () => {
  viewerIsParent = false;
  const bonus = completion({ completion_id: "b1", bonus_subtask_id: "dry" });
  const card = makeCard({ completions: [bonus] });
  await card._handleUndoBonusSubtask(dishes(), { id: "dry" }, { id: "kid1" }, [bonus]);
  assert.deepEqual(card.calls, []);
  assert.equal(card.dispatched.at(-1)?.detail?.message, NOT_ALLOWED);
});

test("the card schedules a re-render for when the window closes", () => {
  const card = makeCard({ completions: [completion({ child_undo_until: future(5) })] });
  card._scheduleUndoExpiry(card.hass.states[ENTITY].attributes);
  assert.ok(card._undoExpiryTimer, "a timer is armed");
  card.disconnectedCallback();
  assert.equal(card._undoExpiryTimer, null);
});

// ── routine card ─────────────────────────────────────────────────────────

function makeRoutine(completions) {
  const card = new RoutineCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", time_category: "all" });
  card.calls = [];
  card.hass = {
    callService: async (domain, service, data) => card.calls.push({ domain, service, data }),
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", chore_order: [] }],
          chores: [dishes(), dishes({ id: "bins", name: "Bins" })],
          chore_availability: { dishes: { kid1: true }, bins: { kid1: true } },
          todays_completions: completions,
        },
      },
    },
  };
  // Dishes was ticked during this run and is the step on screen ("Bins"
  // sorts first).
  card._runCompleted.set("dishes", { points: 10, pending: false });
  card._index = 1;
  return card;
}

test("routine: a step just done shows Undo while the window is open", async () => {
  const card = makeRoutine([completion({ child_undo_until: future() })]);
  const undo = render(card.render()).control("rt-undo");
  assert.ok(undo, "the undo button is on the done step");
  await undo.click();
  assert.deepEqual(plain(card.calls), [{ domain: "taskmate", service: "undo_chore", data: { completion_id: "comp1" } }]);
  assert.equal(card._runCompleted.has("dishes"), false, "the step is open again");
});

test("routine: no Undo when the window is 0 or has passed", () => {
  for (const comp of [completion(), completion({ child_undo_until: past() })]) {
    const card = makeRoutine([comp]);
    assert.equal(render(card.render()).control("rt-undo"), undefined);
  }
});
