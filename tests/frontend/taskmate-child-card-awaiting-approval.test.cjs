"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// A completion a parent still has to approve used to look exactly like a paid
// one on the child card. Every render path now shows a third row state,
// "Waiting for a grown-up", with an hourglass; the celebration no longer
// claims points that haven't been paid; and an empty list says "All Done!"
// only when the child actually finished something today.

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
const WAITING = localize("child.awaiting_approval");

function chore(extra = {}) {
  return {
    id: "zz",
    name: "ZZ chore",
    points: 5,
    time_category: "anytime",
    assigned_to: [],
    due_days: [],
    schedule_mode: "specific_days",
    daily_limit: 1,
    ...extra,
  };
}

function done(approved, extra = {}) {
  return { chore_id: "zz", child_id: "kid1", approved, completed_at: new Date().toISOString(), ...extra };
}

function makeCard({ chores = [chore()], completions = [], config = {}, design, adult = false }) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: "kid1", card_design: design, ...config };
  const mia = { id: "kid1", name: "Mia", chore_order: [], weekly_chore_progress: {}, ...(adult ? { is_adult: true } : {}) };
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [mia],
          chores,
          todays_completions: completions,
          chore_availability: {},
          today_day_of_week: "wednesday",
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card.undone = [];
  card._handleUndo = (c) => card.undone.push(c.id);
  return card;
}

for (const design of DESIGNS) {
  test(`${design}: a completion awaiting approval shows the waiting state`, () => {
    const { markup } = render(makeCard({ design, completions: [done(false)] }).render());
    assert.ok(markup.includes(WAITING), "the row says it is waiting for a grown-up");
    assert.match(markup, /mdi:timer-sand/, "with an hourglass");
    assert.match(markup, /class="[^"]*\bawaiting\b/, "and the awaiting row class");
  });

  test(`${design}: an approved completion looks done, not waiting`, () => {
    const { markup } = render(makeCard({ design, completions: [done(true)] }).render());
    assert.ok(!markup.includes(WAITING));
    assert.doesNotMatch(markup, /class="[^"]*\bawaiting\b/);
  });

  test(`${design}: pre-reader tile shows the hourglass and still undoes`, async () => {
    const card = makeCard({ design, completions: [done(false)], config: { pre_reader: true } });
    const view = render(card.render());
    const tile = view.controls.find((c) => c.tag === "button" && /class="pre-tile\b/.test(c.attrs));
    assert.ok(tile, "the tile is on the card");
    assert.match(tile.attrs, /\bawaiting\b/);
    assert.ok(tile.attrs.includes(WAITING), "its name says it is waiting");
    assert.match(view.markup, /mdi:timer-sand/);
    await tile.click();
    assert.deepEqual(card.undone, ["zz"], "tapping a waiting tile still undoes it");
  });

  test(`${design}: no chores at all says "nothing to do", not "All Done"`, () => {
    const { markup } = render(makeCard({ design, chores: [] }).render());
    assert.ok(markup.includes(localize("child.nothing_to_do")));
    assert.ok(!markup.includes(localize("child.all_done")));
  });

  test(`${design}: an empty list after finishing something still says "All Done"`, () => {
    // The chore is someone else's turn now, so the list is empty, but Mia
    // ticked a different chore today.
    const card = makeCard({
      design,
      chores: [],
      completions: [{ chore_id: "other", child_id: "kid1", approved: true, completed_at: new Date().toISOString() }],
    });
    const { markup } = render(card.render());
    assert.ok(markup.includes(localize("child.all_done")));
    assert.ok(!markup.includes(localize("child.nothing_to_do")));
  });
}

test("classic: undo on a waiting row works exactly as before", async () => {
  const card = makeCard({ design: "classic", completions: [done(false)] });
  const view = render(card.render());
  const row = view.controls.find((c) => /class="chore-card\b/.test(c.attrs));
  assert.ok(row);
  await row.click();
  assert.deepEqual(card.undone, ["zz"]);
});

test("a tap still in flight is judged by the chore's approval rule", () => {
  const now = Date.now();
  const opt = { zz_kid1: { timestamp: now, timestamps: [now], count: 1 } };
  const needs = makeCard({ design: "playroom" });
  needs._optimisticCompletions = opt;
  assert.ok(render(needs.render()).markup.includes(WAITING), "requires approval by default");

  const auto = makeCard({ design: "playroom", chores: [chore({ requires_approval: false })] });
  auto._optimisticCompletions = opt;
  assert.ok(!render(auto.render()).markup.includes(WAITING), "auto-approved chore pays at once");
});

test("_needsApproval mirrors the backend auto-approve rule", () => {
  const card = makeCard({ design: "classic" });
  const kid = { id: "kid1" };
  assert.equal(card._needsApproval(chore(), kid), true);
  assert.equal(card._needsApproval(chore({ requires_approval: false }), kid), false);
  assert.equal(card._needsApproval(chore({ requires_approval: false, require_photo: true }), kid), true);
  assert.equal(card._needsApproval(chore({ requires_approval: false, open_ended: true }), kid), true);
  assert.equal(card._needsApproval(chore({ requires_approval: false, quantity_unit: "pages" }), kid), true);
  assert.equal(card._needsApproval(chore({ requires_approval: false, quantity_unit: "pages", quantity_max: 20 }), kid), false);
  assert.equal(card._needsApproval(chore(), { id: "kid1", is_adult: true }), false);
});

test("celebration: approval chores don't claim the points as earned", () => {
  const card = makeCard({ design: "classic" });
  card._celebrating = "zz";
  const pending = render(card._renderCelebration()).markup;
  assert.ok(pending.includes(localize("child.celebration_pending_note")));

  const auto = makeCard({ design: "classic", chores: [chore({ requires_approval: false })] });
  auto._celebrating = "zz";
  const paid = render(auto._renderCelebration()).markup;
  assert.ok(!paid.includes(localize("child.celebration_pending_note")));
  assert.match(paid, /\+5/);
});
