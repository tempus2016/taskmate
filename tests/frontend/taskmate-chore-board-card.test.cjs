// Chore board card (#1017): the panel's Today-page board on a dashboard.
//
// One layout that reads the design tokens, so every design must render the
// same grid; a tap completes the chore for that child.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const TODAY = "2026-10-01";
const plain = (x) => JSON.parse(JSON.stringify(x));

const CHILDREN = [
  { id: "k1", name: "Malia", avatar: "mdi:account" },
  { id: "k2", name: "Vaiha" },
];

const CHORES = [
  { id: "bed", name: "Make bed", time_category: "morning", requires_approval: false },
  { id: "cat", name: "Feed the cat", time_category: "morning" },
  { id: "teeth", name: "Brush teeth", time_category: "evening", daily_limit: 2 },
  { id: "photo", name: "Tooth photo", time_category: "evening", require_photo: true },
  { id: "read", name: "Read", time_category: "anytime" },
];

const TIME_PERIODS = [
  // Deliberately out of order: the board sorts by start time.
  { id: "evening", label: "", icon: "mdi:weather-night", start: "17:00", end: "21:00" },
  { id: "morning", label: "", icon: "mdi:weather-sunset-up", start: "06:00", end: "12:00" },
];

function boardFor(children) {
  const week = (due, done) => [
    { date: "2026-09-25" }, { date: "2026-09-26", due: 4, done: 4 }, { date: "2026-09-27", due: 4, done: 2 },
    { date: "2026-09-28", due: 4, done: 3 }, { date: "2026-09-29", due: 4, done: 4 }, { date: "2026-09-30", due: 4, done: 1 },
    { date: TODAY, due, done },
  ];
  return {
    board: { date: TODAY, children },
    history: Object.fromEntries(children.map(e => [e.child_id, week(e.due, e.done)])),
  };
}

const DEFAULT_BOARD = boardFor([
  {
    child_id: "k1", due: 4, done: 1, chores: [
      { chore_id: "bed", status: "done", count: 1, limit: 1 },
      { chore_id: "teeth", status: "todo", count: 1, limit: 2 },
      { chore_id: "photo", status: "todo", count: 0, limit: 1 },
      { chore_id: "read", status: "missed", count: 0, limit: 1 },
    ],
  },
  {
    child_id: "k2", due: 2, done: 1, chores: [
      { chore_id: "bed", status: "pending", count: 1, limit: 1 },
      { chore_id: "cat", status: "todo", count: 0, limit: 1 },
    ],
  },
]);

function hassWith({ board = DEFAULT_BOARD, completions = [], extraStates = {} } = {}) {
  const calls = [];
  return {
    calls,
    language: "en",
    callService: async (domain, service, data) => { calls.push({ domain, service, data }); },
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: CHILDREN, chores: CHORES, time_periods: TIME_PERIODS,
          todays_completions: completions,
          ...(board ? { chore_board: board } : {}),
        },
      },
      ...extraStates,
    },
  };
}

function setup({ config = {}, hass = hassWith(), window = {} } = {}) {
  const loaded = loadCard("taskmate-chore-board-card.js", {
    window,
    sandbox: { CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init?.detail; } } },
  });
  const Card = loaded.get("taskmate-chore-board-card");
  const card = new Card();
  card.setConfig({ entity: ENTITY, ...config });
  card.hass = hass;
  return { card, hass, Card, Editor: loaded.get("taskmate-chore-board-card-editor") };
}

const chip = (view, name) => view.controls.find(c => c.tag === "button" && c.text.includes(name));

for (const design of DESIGNS) {
  test(`chore board — ${design} renders the grid by time period and child`, () => {
    const { card } = setup({ config: { card_design: design } });
    const view = render(card.render());
    assert.ok(view.markup.includes(localize("chore_board.title")));
    assert.ok(view.markup.includes("Malia") && view.markup.includes("Vaiha"));
    // Morning before Evening (sorted by start), Anytime last.
    const m = view.markup.indexOf(localize("common.morning"));
    const e = view.markup.indexOf(localize("common.evening"));
    const a = view.markup.indexOf(localize("common.anytime"));
    assert.ok(m > 0 && m < e && e < a, `order ${m} ${e} ${a}`);
    // Done/total per child in the column header.
    assert.ok(view.markup.includes("1/4") && view.markup.includes("1/2"));
    assert.ok(chip(view, "Feed the cat"), "a to-do chore is tappable");
    assert.ok(!chip(view, "Make bed"), "done and pending chores are not");
    assert.ok(view.markup.includes(localize("chore_board.status_missed")), "legend");
  });
}

test("a daily-limit chore shows its count and stays tappable", () => {
  const { card } = setup();
  const view = render(card.render());
  assert.ok(chip(view, "Brush teeth").content.includes("1/2"));
});

test("tapping a to-do chore completes it for that child", async () => {
  const { card, hass } = setup();
  await chip(render(card.render()), "Feed the cat").click();
  assert.deepEqual(plain(hass.calls), [
    { domain: "taskmate", service: "complete_chore", data: { chore_id: "cat", child_id: "k2" } },
  ]);
  // Needs approval, so it shows as pending straight away and the toast says so.
  const view = render(card.render());
  assert.ok(!chip(view, "Feed the cat"));
  assert.ok(view.markup.includes(localize("chore_board.sent_for_approval", { name: "Vaiha", chore: "Feed the cat" })));
  assert.ok(view.controls.find(c => c.text === localize("chore_board.undo")));
});

test("a tap presses the chore's button entity when there is one", async () => {
  const { card, hass } = setup({
    window: { __taskmate_find_button: (_h, child, action, chore) => (child === "k1" && action === "complete" && chore === "teeth" ? "button.x" : null) },
  });
  await chip(render(card.render()), "Brush teeth").click();
  assert.deepEqual(plain(hass.calls), [{ domain: "button", service: "press", data: { entity_id: "button.x" } }]);
  // That was the second of two, and it needs approval: no longer tappable.
  assert.ok(!chip(render(card.render()), "Brush teeth"));
});

test("a missed chore can still be completed", async () => {
  const { card, hass } = setup();
  await chip(render(card.render()), "Read").click();
  assert.equal(hass.calls[0].data.chore_id, "read");
});

test("a photo chore points to the child's card instead of completing", async () => {
  const { card, hass } = setup();
  await chip(render(card.render()), "Tooth photo").click();
  assert.equal(hass.calls.length, 0);
  const view = render(card.render());
  assert.ok(view.markup.includes(localize("chore_board.finish_on_card", { chore: "Tooth photo", name: "Malia" })));
  assert.ok(!view.controls.find(c => c.text === localize("chore_board.undo")), "nothing to undo");
});

test("tap_to_complete: false makes a view-only board", () => {
  const { card } = setup({ config: { tap_to_complete: false } });
  const view = render(card.render());
  assert.ok(!chip(view, "Feed the cat"));
  assert.ok(view.markup.includes("Feed the cat"));
});

test("a failed completion rolls the chip back and says why", async () => {
  const { card, hass } = setup();
  hass.callService = async () => { throw new Error("Not today"); };
  await chip(render(card.render()), "Feed the cat").click();
  const view = render(card.render());
  assert.ok(chip(view, "Feed the cat"), "still to do");
  assert.ok(view.markup.includes("Not today"));
});

test("Undo as a parent rejects the newest completion of that chore", async () => {
  const completions = [
    { completion_id: "old", chore_id: "cat", child_id: "k2", completed_at: "2026-10-01T07:00:00Z" },
    { completion_id: "new", chore_id: "cat", child_id: "k2", completed_at: "2026-10-01T08:00:00Z" },
    { completion_id: "other", chore_id: "cat", child_id: "k1", completed_at: "2026-10-01T09:00:00Z" },
  ];
  const { card, hass } = setup({ hass: hassWith({ completions }) });
  await chip(render(card.render()), "Feed the cat").click();
  await render(card.render()).controls.find(c => c.text === localize("chore_board.undo")).click();
  assert.deepEqual(plain(hass.calls[1]), { domain: "taskmate", service: "reject_chore", data: { completion_id: "new" } });
});

test("Undo for a child uses undo_chore inside the window, and refuses outside it", async () => {
  const pending = [{ completion_id: "c1", chore_id: "cat", child_id: "k2", completed_at: "2026-10-01T08:00:00Z", child_undo_pending: true }];
  let ctx = setup({ hass: hassWith({ completions: pending }), window: { __taskmate_is_parent: () => false } });
  await chip(render(ctx.card.render()), "Feed the cat").click();
  await render(ctx.card.render()).controls.find(c => c.text === localize("chore_board.undo")).click();
  assert.deepEqual(plain(ctx.hass.calls[1]), { domain: "taskmate", service: "undo_chore", data: { completion_id: "c1" } });

  const closed = [{ completion_id: "c1", chore_id: "cat", child_id: "k2", completed_at: "2026-10-01T08:00:00Z" }];
  ctx = setup({ hass: hassWith({ completions: closed }), window: { __taskmate_is_parent: () => false } });
  await chip(render(ctx.card.render()), "Feed the cat").click();
  await render(ctx.card.render()).controls.find(c => c.text === localize("chore_board.undo")).click();
  assert.equal(ctx.hass.calls.length, 1, "no undo call");
  assert.ok(render(ctx.card.render()).markup.includes(localize("child.undo_not_allowed")));
});

test("one child picked shows a simple list with progress", () => {
  const { card } = setup({ config: { children: ["k1"] } });
  const view = render(card.render());
  assert.ok(view.markup.includes("cb-list"));
  assert.ok(!view.markup.includes("Vaiha"));
  assert.ok(view.markup.includes("1/4"));
  assert.ok(chip(view, "Brush teeth"));
});

test("hide_done_periods drops a time period everyone has finished", () => {
  const board = boardFor([
    { child_id: "k1", due: 2, done: 1, chores: [{ chore_id: "bed", status: "done" }, { chore_id: "read", status: "todo" }] },
    { child_id: "k2", due: 1, done: 1, chores: [{ chore_id: "cat", status: "pending" }] },
  ]);
  const shown = render(setup({ hass: hassWith({ board }) }).card.render()).markup;
  assert.ok(shown.includes(localize("common.morning")));
  const hidden = render(setup({ hass: hassWith({ board }), config: { hide_done_periods: true } }).card.render()).markup;
  assert.ok(!hidden.includes(localize("common.morning")));
  assert.ok(hidden.includes(localize("common.anytime")));
});

test("the week view shows done/total per day with gaps and today", async () => {
  const { card } = setup();
  await render(card.render()).controls.find(c => c.text === localize("chore_board.this_week")).click();
  const view = render(card.render());
  assert.ok(view.markup.includes("cb-week"));
  assert.ok(view.markup.includes("4/4") && view.markup.includes("2/4"));
  assert.ok(view.markup.includes(localize("chore_board.not_recorded")));
  assert.ok(view.markup.includes(localize("chore_board.week_hint")));
});

test("default_view: week opens on the week; show_week: false hides the toggle", () => {
  assert.ok(render(setup({ config: { default_view: "week" } }).card.render()).markup.includes("cb-week"));
  const view = render(setup({ config: { default_view: "week", show_week: false } }).card.render());
  assert.ok(!view.markup.includes("cb-week"));
  assert.ok(!view.controls.find(c => c.text === localize("chore_board.this_week")));
});

test("an older backend without the board says so", () => {
  const view = render(setup({ hass: hassWith({ board: null }) }).card.render());
  assert.ok(view.markup.includes(localize("chore_board.unavailable")));
});

test("no English title is baked into the config or the picker stub", () => {
  const { card, Card } = setup();
  assert.ok(!card.config.title);
  assert.ok(!Card.getStubConfig().title);
  assert.ok(render(card.render()).markup.includes(localize("chore_board.title")));
});

test("the editor stores only options changed from their defaults", () => {
  const { Editor } = setup();
  const editor = new Editor();
  editor.setConfig({ entity: ENTITY, type: "custom:taskmate-chore-board-card" });
  editor._formChanged({
    detail: {
      value: {
        entity: ENTITY, title: "", children: [], default_view: "today", show_week: true,
        tap_to_complete: false, show_legend: true, hide_done_periods: true, card_design: "global",
      },
    },
  });
  assert.deepEqual(plain(editor.dispatched[0].detail.config), {
    entity: ENTITY, type: "custom:taskmate-chore-board-card", tap_to_complete: false, hide_done_periods: true,
  });
});
