// show_parent_actions: false (#1032).
//
// On a shared kids' dashboard a parent account often stays signed in, so the
// cards hand out parent controls to whoever taps them. With the option off a
// card must behave exactly as it does for a child: undo goes through the
// child's own window (undo_chore) instead of reject_chore, and the overview
// card's complete-on-behalf tiles stop expanding. The viewer here is always a
// parent.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const plain = (value) => JSON.parse(JSON.stringify(value));

class CustomEvent {
  constructor(type, init = {}) {
    this.type = type;
    this.detail = init.detail;
  }
}

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const NOT_ALLOWED = localize("child.undo_not_allowed");
const future = (s = 60) => new Date(Date.now() + s * 1000).toISOString();

// ── child card ───────────────────────────────────────────────────────────

const ChildCard = loadCard("taskmate-child-card.js", {
  window: { __taskmate_is_parent: () => true, __taskmate_badge_id: (b) => b.badge_id },
  sandbox: { CustomEvent },
}).get("taskmate-child-card");

const dishes = { id: "dishes", name: "Dishes", points: 10, time_category: "anytime", assigned_to: [], due_days: [], daily_limit: 1 };

function completion(extra = {}) {
  return {
    completion_id: "comp1", chore_id: "dishes", child_id: "kid1", chore_name: "Dishes",
    approved: true, completed_at: new Date().toISOString(), bonus_subtask_id: "", ...extra,
  };
}

function childCard(config = {}, completions = []) {
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", ...config });
  card.calls = [];
  card.hass = {
    callService: async (domain, service, data) => card.calls.push({ domain, service, data }),
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", points: 10, chore_order: [] }],
          chores: [dishes],
          todays_completions: completions,
          chore_availability: {},
          today_day_of_week: "wednesday",
        },
      },
    },
  };
  return card;
}

test("child card: a parent's tap rejects by default", async () => {
  const comp = completion();
  const card = childCard({}, [comp]);
  await card._handleUndo(dishes, { id: "kid1" }, [comp]);
  assert.deepEqual(plain(card.calls.map((c) => c.service)), ["reject_chore"]);
});

test("child card: with parent actions off, a parent's tap uses the child's undo window", async () => {
  const comp = completion({ child_undo_until: future() });
  const card = childCard({ show_parent_actions: false }, [comp]);
  await card._handleUndo(dishes, { id: "kid1" }, [comp]);
  assert.deepEqual(plain(card.calls), [{ domain: "taskmate", service: "undo_chore", data: { completion_id: "comp1" } }]);
});

test("child card: with parent actions off, a done chore outside the window can't be undone", async () => {
  const comp = completion();
  const card = childCard({ show_parent_actions: false }, [comp]);
  await card._handleUndo(dishes, { id: "kid1" }, [comp]);
  assert.deepEqual(card.calls, [], "no reject_chore");
  assert.equal(card.dispatched.at(-1)?.detail?.message, NOT_ALLOWED);
});

test("child card: with parent actions off, a locked bonus sub-task can't be undone", async () => {
  const bonus = completion({ completion_id: "b1", bonus_subtask_id: "dry" });
  const card = childCard({ show_parent_actions: false }, [bonus]);
  await card._handleUndoBonusSubtask(dishes, { id: "dry" }, { id: "kid1" }, [bonus]);
  assert.deepEqual(card.calls, []);
  assert.equal(card.dispatched.at(-1)?.detail?.message, NOT_ALLOWED);
});

// ── chore board ──────────────────────────────────────────────────────────

const ChoreBoard = loadCard("taskmate-chore-board-card.js", {
  window: { __taskmate_is_parent: () => true },
  sandbox: { CustomEvent },
});

function choreBoard(config, completions) {
  const card = new (ChoreBoard.get("taskmate-chore-board-card"))();
  card.setConfig({ entity: ENTITY, ...config });
  card.calls = [];
  card.hass = {
    callService: async (domain, service, data) => card.calls.push({ domain, service, data }),
    states: { [ENTITY]: { state: "ok", attributes: { todays_completions: completions } } },
  };
  return card;
}

test("chore board: with parent actions off, a parent's undo uses undo_chore inside the window", async () => {
  const comp = { completion_id: "c1", chore_id: "cat", child_id: "k2", completed_at: "2026-10-01T08:00:00Z", child_undo_pending: true };
  const card = choreBoard({ show_parent_actions: false }, [comp]);
  await card._undo({ chore_id: "cat", child_id: "k2" });
  assert.deepEqual(plain(card.calls), [{ domain: "taskmate", service: "undo_chore", data: { completion_id: "c1" } }]);
});

test("chore board: with parent actions off, a closed window refuses instead of rejecting", async () => {
  const comp = { completion_id: "c1", chore_id: "cat", child_id: "k2", completed_at: "2026-10-01T08:00:00Z" };
  const card = choreBoard({ show_parent_actions: false }, [comp]);
  await card._undo({ chore_id: "cat", child_id: "k2" });
  assert.deepEqual(card.calls, []);
});

test("chore board editor: the default (on) is saved as the absence of the key", () => {
  const Editor = ChoreBoard.get("taskmate-chore-board-card-editor");
  assert.equal(Editor._isDefault("show_parent_actions", true), true);
  assert.equal(Editor._isDefault("show_parent_actions", false), false);
});

// ── overview card ────────────────────────────────────────────────────────

const Overview = loadCard("taskmate-overview-card.js", {
  window: { __taskmate_is_parent: () => true },
  sandbox: { CustomEvent },
});

function overview(config) {
  const card = new (Overview.get("taskmate-overview-card"))();
  card.setConfig({ entity: ENTITY, ...config });
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", points: 10 }],
          chores: [dishes],
          todays_completions: [],
        },
      },
    },
  };
  return card;
}

for (const design of DESIGNS) {
  // Classic marks an expandable tile tm-expandable, the designed paths tm-clickable.
  const marker = design === "classic" ? "tm-expandable" : "tm-clickable";

  test(`overview — ${design}: a parent can expand a child for complete-on-behalf by default`, () => {
    assert.ok(render(overview({ card_design: design }).render()).markup.includes(marker));
  });

  test(`overview — ${design}: with parent actions off, child tiles don't expand`, () => {
    assert.ok(!render(overview({ card_design: design, show_parent_actions: false }).render()).markup.includes(marker));
  });
}

// ── editors ──────────────────────────────────────────────────────────────

for (const [file, tag] of [
  ["taskmate-child-card.js", "taskmate-child-card-editor"],
  ["taskmate-chore-board-card.js", "taskmate-chore-board-card-editor"],
  ["taskmate-overview-card.js", "taskmate-overview-card-editor"],
]) {
  test(`${tag} offers the show_parent_actions toggle, on by default`, () => {
    const Editor = loadCard(file, { sandbox: { CustomEvent } }).get(tag);
    const editor = new Editor();
    editor.setConfig({ entity: ENTITY });
    editor.hass = { states: {} };
    const field = editor._buildSchema().find((f) => f.name === "show_parent_actions");
    assert.ok(field, "toggle is in the schema");
    assert.equal(editor._computeLabel(field), localize("common.editor.show_parent_actions"));
    assert.equal(editor._computeHelper(field), localize("common.editor.show_parent_actions_helper"));
  });
}
