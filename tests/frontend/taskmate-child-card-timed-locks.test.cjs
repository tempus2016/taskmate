"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// A timed chore's Start / Resume must obey every lock the classic row does
// (#771). The timed card only refused a prerequisite, so a timed chore in its
// cooldown, claimed first by a sibling, before its period, past its window,
// not due today, at its weekly target or at a closed set time could still be
// started. Pause / Done stay live so a running session can always be ended.
// Timed chores render through the same card in every design.

// graphite reuses the cleanpro layout (LAYOUT_ALIAS in taskmate-design.js).
const ALIAS = { graphite: "cleanpro" };
const { get } = loadCard("taskmate-child-card.js", {
  window: {
    __taskmate_badge_id: (b) => b.badge_id,
    __taskmate_design: {
      apply: (_card, _hass, config) => {
        const d = config?.card_design || "classic";
        return ALIAS[d] || d;
      },
      styles: () => null,
      editorOptions: () => [],
    },
  },
});
const ChildCard = get("taskmate-child-card");

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];

function chore(extra = {}) {
  return {
    id: "zz",
    name: "ZZ chore",
    points: 5,
    task_type: "timed",
    timed_rate_minutes: 5,
    timed_rate_points: 10,
    time_category: "anytime",
    assigned_to: [],
    due_days: [],
    schedule_mode: "specific_days",
    daily_limit: 1,
    ...extra,
  };
}

function makeCard({ chores, completions = [], availability = {}, weekly = {}, config = {}, design, session = null }) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: "kid1", card_design: design, ...config };
  const mia = { id: "kid1", name: "Mia", chore_order: [], weekly_chore_progress: weekly };
  const leo = { id: "kid2", name: "Leo", chore_order: [], weekly_chore_progress: {} };
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [mia, leo],
          chores,
          todays_completions: completions,
          chore_availability: availability,
          today_day_of_week: "wednesday",
          active_timed_sessions: session ? [{ chore_id: "zz", child_id: "kid1", state: session, total_seconds_today: 60 }] : [],
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card.calls = [];
  card.hass.callService = (domain, service, data) => {
    card.calls.push(service);
    return Promise.resolve();
  };
  return card;
}

const REASONS = [
  {
    name: "before its time period (locked preview)",
    args: { chores: [chore({ time_category: "evening" })], config: { debug_time_period: "morning" } },
  },
  {
    name: "past its time window (elapsed, dim)",
    args: { chores: [chore({ time_category: "morning" })], config: { debug_time_period: "evening", time_category: "all" } },
  },
  {
    name: "not due today (due_days_mode dim)",
    args: { chores: [chore({ due_days: ["monday"] })], config: { due_days_mode: "dim" } },
  },
  {
    name: "in its recurrence cooldown",
    args: {
      chores: [chore({ schedule_mode: "recurring", recurrence: "every_3_days" })],
      availability: { zz: { kid1: false } },
    },
  },
  {
    name: "in its recurrence cooldown (recurrence_done_mode show)",
    args: {
      chores: [chore({ schedule_mode: "recurring", recurrence: "every_3_days" })],
      availability: { zz: { kid1: false } },
      config: { recurrence_done_mode: "show" },
    },
  },
  {
    name: "waiting on a prerequisite (dependency_mode dim)",
    args: {
      chores: [chore({ depends_on: ["teeth"] }), chore({ id: "teeth", name: "Teeth", time_category: "night", task_type: undefined })],
      config: { dependency_mode: "dim", debug_time_period: "morning", time_category: "morning" },
    },
  },
  {
    name: "claimed first by a sibling (first-come)",
    args: {
      chores: [chore({ assignment_mode: "first_come", assigned_to: ["kid1", "kid2"] })],
      completions: [{ chore_id: "zz", child_id: "kid2", approved: true, completed_at: new Date().toISOString() }],
      config: { first_come_claimed_mode: "dim" },
    },
  },
  {
    name: "already at its weekly target",
    args: { chores: [chore({ weekly_target: 2 })], weekly: { zz: 2 } },
  },
];

const btn = (view, cls) => view.controls.find((c) => c.tag === "button" && new RegExp(`timer-btn ${cls}\\b`).test(c.attrs));

for (const design of DESIGNS) {
  for (const { name, args } of REASONS) {
    test(`${design}: a timed chore ${name} can't be started`, async () => {
      const card = makeCard({ ...args, design });
      const view = render(card.render());
      assert.match(view.markup, /timed-chore-card/, "the timed card is rendered");
      const start = btn(view, "start");
      assert.ok(start, "the Start button is there");
      assert.equal(start.disabled, true, "Start must be disabled");
      await assert.rejects(start.click(), /disabled/);
      assert.deepEqual(card.calls, []);
    });

    test(`${design}: a paused timed chore ${name} can't be resumed, but can be finished`, async () => {
      const card = makeCard({ ...args, design, session: "paused" });
      const view = render(card.render());
      assert.equal(btn(view, "resume").disabled, true, "Resume must be disabled");
      const stop = btn(view, "stop");
      assert.equal(stop.disabled, false, "Done stays live so the session can be ended");
      await stop.click();
      assert.deepEqual(card.calls, ["stop_timed_task"]);
    });
  }

  test(`${design}: a running timed chore can always be paused or finished`, async () => {
    const card = makeCard({ ...REASONS[3].args, design, session: "running" });
    const view = render(card.render());
    assert.equal(btn(view, "pause").disabled, false);
    assert.equal(btn(view, "stop").disabled, false);
  });

  test(`${design}: an open timed chore still starts`, async () => {
    const card = makeCard({ chores: [chore({ time_category: "morning" })], config: { debug_time_period: "morning" }, design });
    const start = btn(render(card.render()), "start");
    assert.equal(start.disabled, false);
    await start.click();
    assert.deepEqual(card.calls, ["start_timed_task"]);
  });
}

test("the timed card takes its locks from _choreLocks", () => {
  const src = require("node:fs").readFileSync(
    require("node:path").join(__dirname, "../../custom_components/taskmate/www/taskmate-child-card.js"),
    "utf8",
  );
  const start = src.indexOf("\n  _renderTimedChoreCard(");
  assert.match(src.slice(start, src.indexOf("\n  _renderBonusSubtasks(", start)), /this\._choreLocks\(/);
});

// ── a locked timed chore says why, and dims like a locked row ─────────────
// Greying Start alone left the card looking live with no reason (#771).

const REASON_TEXT = {
  "before its time period (locked preview)": [localize("child.chore_locked_until", { time: "17:00" }), true],
  "past its time window (elapsed, dim)": [localize("child.time_has_passed"), true],
  "not due today (due_days_mode dim)": [localize("child.not_scheduled_for_today"), true],
  // The translated cadence (fix/recurrence-label-i18n), not the raw key.
  "in its recurrence cooldown": [localize("child.recurrence_every_n_days", { count: 3 }), true],
  "in its recurrence cooldown (recurrence_done_mode show)": [localize("child.recurrence_every_n_days", { count: 3 }), false],
  "waiting on a prerequisite (dependency_mode dim)": [localize("child.blocked_by_dependency", { chores: "Teeth" }), true],
  "claimed first by a sibling (first-come)": [localize("child.claimed_by_another", { name: "Leo" }), true],
  "already at its weekly target": [localize("child.weekly_target_done"), true],
};

for (const design of DESIGNS) {
  for (const { name, args } of REASONS) {
    const [text, dims] = REASON_TEXT[name];
    test(`${design}: a timed chore ${name} says why${dims ? " and is dimmed" : " (not dimmed under show)"}`, () => {
      const { markup } = render(makeCard({ ...args, design }).render());
      const card = markup.slice(markup.indexOf('class="timed-chore-card'));
      assert.match(card, /tm-timed-lock-reason/);
      assert.ok(card.includes(text), `expected "${text}"`);
      assert.equal(/class="timed-chore-card[^"]*tm-timed-locked/.test(markup), dims);
    });
  }

  test(`${design}: a set time that isn't open says when it opens`, () => {
    const card = makeCard({ chores: [chore()], design });
    const filter = card._filterAndSortChores.bind(card);
    card._filterAndSortChores = (...a) =>
      filter(...a).map((c) => Object.assign(c, { _setTimeLocked: true, _setTimeState: "later", _setTimeEntry: { opens: "18:30" } }));
    const { markup } = render(card.render());
    assert.ok(markup.includes(localize("child.set_time_opens", { time: "18:30" })));
    assert.match(markup, /tm-timed-locked/);
  });

  test(`${design}: a running session on a locked chore stays undimmed and live`, () => {
    const { markup } = render(makeCard({ ...REASONS[3].args, design, session: "running" }).render());
    assert.doesNotMatch(markup, /tm-timed-locked/);
  });

  test(`${design}: an open timed chore shows no lock reason`, () => {
    const { markup } = render(makeCard({ chores: [chore({ time_category: "morning" })], config: { debug_time_period: "morning" }, design }).render());
    assert.doesNotMatch(markup, /tm-timed-lock-reason|tm-timed-locked/);
  });
}

// The opening time follows HA's clock once the shared helper is loaded (#771).
test("a locked timed chore's opening time goes through HA's clock helper", () => {
  const seen = [];
  const { get: get2 } = loadCard("taskmate-child-card.js", {
    window: {
      __taskmate_badge_id: (b) => b.badge_id,
      __taskmate_dates: { args: (h, o) => [undefined, o], clock: (_h, t) => { seen.push(t); return `${t} (HA)`; } },
    },
  });
  const card = new (get2("taskmate-child-card"))();
  Object.assign(card, makeCard({ chores: [chore({ time_category: "evening" })], config: { debug_time_period: "morning" }, design: "classic" }));
  card.config = { ...card.config, card_design: "classic" };
  const { markup } = render(card.render());
  assert.ok(markup.includes(localize("child.chore_locked_until", { time: "17:00 (HA)" })));
  assert.ok(seen.includes("17:00"));
});
