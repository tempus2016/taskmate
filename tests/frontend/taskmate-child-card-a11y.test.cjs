"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// Screen-reader and keyboard reach on the child card: every Done button says
// which chore it is for, a locked classic row says why (in its name and on
// screen), the header avatar and the badge strip work from the keyboard, and
// a tap is announced through one polite live region.

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
const DESIGNED = ["playroom", "console", "cleanpro", "accessible", "graphite"];

function chore(extra = {}) {
  return {
    id: "zz",
    name: "Feed the cat",
    points: 5,
    time_category: "anytime",
    assigned_to: [],
    due_days: [],
    schedule_mode: "specific_days",
    daily_limit: 1,
    ...extra,
  };
}

function makeCard({ chores, completions = [], config = {}, design = "classic", child = {} }) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: "kid1", card_design: design, ...config };
  const mia = {
    id: "kid1", name: "Mia", chore_order: [], weekly_chore_progress: {},
    avatar_options: [{ id: "a", unlocked: true }, { id: "b", unlocked: true }],
    ...child,
  };
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: { children: [mia], chores, todays_completions: completions, today_day_of_week: "wednesday" },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  return card;
}

const doneToday = (id) => [{ completion_id: "c1", chore_id: id, child_id: "kid1", approved: true, completed_at: new Date().toISOString(), points: 5 }];

for (const design of DESIGNED) {
  test(`${design}: the Done button is named for its chore`, () => {
    const view = render(makeCard({ chores: [chore()], design }).render());
    const btn = view.controls.find((c) => c.tag === "button" && /class="btn\b/.test(c.attrs));
    assert.ok(btn, "the Done button renders");
    assert.equal(btn.attr("aria-label"), localize("child.done_chore_aria", { chore: "Feed the cat" }));
  });

  test(`${design}: a locked Done button also says why`, () => {
    const card = makeCard({ chores: [chore({ due_days: ["monday"] })], design, config: { due_days_mode: "dim" } });
    const btn = render(card.render()).controls.find((c) => c.tag === "button" && /class="btn\b/.test(c.attrs));
    assert.equal(btn.disabled, true);
    assert.equal(
      btn.attr("aria-label"),
      `${localize("child.done_chore_aria", { chore: "Feed the cat" })}. ${localize("child.not_scheduled_for_today")}`,
    );
  });
}

test("console: the bare undo arrow is named Undo {chore}", () => {
  const view = render(makeCard({ chores: [chore()], completions: doneToday("zz"), design: "console" }).render());
  const chip = view.control(/tmd-undochip/);
  assert.ok(chip, "the undo chip renders");
  assert.equal(chip.attr("aria-label"), localize("child.undo_named", { name: "Feed the cat" }));
});

test("playroom: the done chip keeps its visible word first in its name", () => {
  const view = render(makeCard({ chores: [chore()], completions: doneToday("zz"), design: "playroom" }).render());
  const label = view.control(/tmd-undochip/).attr("aria-label");
  assert.ok(label.startsWith(localize("child.done_chore_aria", { chore: "Feed the cat" })), label);
});

test("classic: a done row carries its state in its name", () => {
  const view = render(makeCard({ chores: [chore()], completions: doneToday("zz") }).render());
  const row = view.control(/class="chore-card/);
  assert.equal(row.attr("aria-label"), `Feed the cat. ${localize("child.done")}`);
});

test("classic: a locked row says why, in its name and as text on the row", () => {
  const card = makeCard({ chores: [chore({ due_days: ["monday"] })], config: { due_days_mode: "dim" } });
  const view = render(card.render());
  const row = view.control(/class="chore-card/);
  const why = localize("child.not_scheduled_for_today");
  assert.equal(row.attr("aria-label"), `Feed the cat. ${why}`);
  assert.match(row.content, /class="recurrence-label tm-lock-reason"/);
  assert.ok(row.text.includes(why), "the reason is visible, not only in title=");
});

test("classic: a lock the row already labels is not repeated", () => {
  const card = makeCard({
    chores: [chore({ depends_on: ["teeth"] }), chore({ id: "teeth", name: "Teeth", time_category: "night" })],
    config: { dependency_mode: "dim", debug_time_period: "morning", time_category: "morning" },
  });
  const row = render(card.render()).control(/aria-label="Feed the cat/);
  assert.ok(row, "the blocked row renders");
  assert.doesNotMatch(row.content, /tm-lock-reason/);
  assert.match(row.content, /class="dependency-label"/);
});

for (const design of ["classic", "playroom"]) {
  test(`${design}: the avatar picker and the badge strip are keyboard buttons`, () => {
    const card = makeCard({ chores: [chore()], design });
    card._resolveBadgesEntity = () => ({ attributes: { earned: [{ badge_id: "b1", tier: "gold", icon: "mdi:medal" }] } });
    const view = render(card.render());
    const avatar = view.control(/avatar-clickable/);
    assert.ok(avatar, "the avatar trigger renders");
    assert.match(avatar.attrs, /role="button"/);
    assert.match(avatar.attrs, /tabindex="0"/);
    assert.match(avatar.attrs, /aria-expanded="false"/);
    assert.match(avatar.attrs, /@keydown/);
    const strip = view.control(design === "classic" ? /class="badge-strip"/ : /class="tmd-badges"/);
    assert.ok(strip, "the badge strip renders");
    assert.match(strip.attrs, /role="button"/);
    assert.match(strip.attrs, /tabindex="0"/);
    assert.match(strip.attrs, /@keydown/);
  });

  test(`${design}: one polite live region is on the card`, () => {
    const { markup } = render(makeCard({ chores: [chore()], design }).render());
    assert.equal((markup.match(/aria-live="polite"/g) || []).length, 1);
  });
}

test("the avatar trigger opens the picker on Enter and Space", () => {
  const card = makeCard({ chores: [chore()] });
  card.requestUpdate = () => {};
  card._avatarPickerOpen = false;
  card._avatarKeydown({ key: "Enter", preventDefault() {} });
  assert.equal(card._avatarPickerOpen, true);
  card._avatarKeydown({ key: " ", preventDefault() {} });
  assert.equal(card._avatarPickerOpen, false);
  card._avatarKeydown({ key: "a", preventDefault() {} });
  assert.equal(card._avatarPickerOpen, false);
});

test("a completion is announced with the chore, points and points name", async () => {
  const card = makeCard({ chores: [chore()] });
  card.hass.states[ENTITY].attributes.points_name = "Stars";
  const region = { textContent: "old" };
  card.renderRoot = { querySelector: (sel) => (sel === ".tm-live" ? region : null) };
  card._announceCompleted(chore(), 5);
  assert.equal(region.textContent, "", "cleared first so a repeat is read again");
  await new Promise((r) => setTimeout(r, 200));
  assert.equal(region.textContent, localize("child.sr_completed", { chore: "Feed the cat", points: "5", points_name: "Stars" }));
});

test("a chore a grown-up still has to check is announced as pending, not earned", async () => {
  const card = makeCard({ chores: [chore()] });
  card.hass.states[ENTITY].attributes.points_name = "Stars";
  card._needsApproval = () => true;
  const region = { textContent: "" };
  card.renderRoot = { querySelector: (sel) => (sel === ".tm-live" ? region : null) };
  card._announceCompleted(chore(), 5, { id: "kid1" });
  await new Promise((r) => setTimeout(r, 200));
  assert.equal(region.textContent, localize("child.sr_completed_pending", { chore: "Feed the cat", points: "5", points_name: "Stars" }));
});
