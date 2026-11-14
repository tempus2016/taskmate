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
  // feat/child-card-all-done folds a fully finished list; keep the rows in view.
  card._allDoneOpen = true;
  return card;
}

// The harness's attr() stops at an apostrophe ("I'm stuck"); read
// double-quoted names directly.
const ariaLabel = (c) => (c.attrs.match(/aria-label="([^"]*)"/) || [])[1];

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

for (const design of DESIGNED) {
  test(`${design}: the undo chip says the chore, its state, then Undo`, () => {
    const card = makeCard({ chores: [chore()], completions: doneToday("zz"), design });
    const chip = render(card.render()).control(/tmd-undochip/);
    assert.ok(chip, "the undo chip renders");
    assert.equal(chip.attr("aria-label"), localize("child.undo_done_aria", { chore: "Feed the cat" }));
  });

  test(`${design}: an undo chip waiting for a grown-up says so`, () => {
    const card = makeCard({ chores: [chore()], completions: doneToday("zz"), design });
    // _isAwaitingApproval lives on feat/child-card-awaiting-approval.
    card._isAwaitingApproval = () => true;
    const chip = render(card.render()).control(/tmd-undochip/);
    assert.equal(chip.attr("aria-label"), localize("child.undo_waiting_aria", { chore: "Feed the cat" }));
  });

  test(`${design}: each I'm stuck button names its chore`, () => {
    const card = makeCard({ chores: [chore(), chore({ id: "yy", name: "Make bed" })], design });
    card._helpEnabled = () => true;
    const names = render(card.render()).controls
      .filter((c) => /tm-help-btn"/.test(c.attrs) && !/tm-remind-btn/.test(c.attrs))
      .map(ariaLabel);
    assert.deepEqual(names.sort(), [
      localize("child.help_ask_aria", { chore: "Feed the cat" }),
      localize("child.help_ask_aria", { chore: "Make bed" }),
    ].sort());
    assert.ok(names.every((n) => !n.includes("🙋")), "no emoji in the name");
  });
}

test("classic: a done row carries its state in its name", () => {
  const view = render(makeCard({ chores: [chore()], completions: doneToday("zz") }).render());
  const row = view.control(/class="chore-card/);
  assert.equal(row.attr("aria-label"), `Feed the cat. ${localize("child.done")}`);
});

test("classic: a done row waiting for a grown-up says so, not done", () => {
  const card = makeCard({ chores: [chore()], completions: doneToday("zz") });
  card._isAwaitingApproval = () => true;
  const row = render(card.render()).control(/class="chore-card/);
  assert.equal(row.attr("aria-label"), `Feed the cat, ${localize("child.awaiting_approval")}`);
});

test("classic: each I'm stuck button names its chore", () => {
  const card = makeCard({ chores: [chore()] });
  card._helpEnabled = () => true;
  const btn = render(card.render()).controls.find((c) => /tm-help-btn"/.test(c.attrs));
  assert.ok(btn, "the help button renders");
  assert.equal(ariaLabel(btn), localize("child.help_ask_aria", { chore: "Feed the cat" }));
});

test("pre-reader tiles carry done, waiting and locked in their names", () => {
  const card = makeCard({
    chores: [chore(), chore({ id: "yy", name: "Make bed" }), chore({ id: "xx", name: "Teeth", due_days: ["monday"] })],
    completions: [...doneToday("zz"), { ...doneToday("yy")[0], completion_id: "c2" }],
    config: { pre_reader: true, due_days_mode: "dim" },
  });
  card._isAwaitingApproval = (c) => c.id === "yy";
  const tiles = render(card.render()).controls.filter((c) => /class="pre-tile/.test(c.attrs));
  const names = tiles.map((t) => t.attr("aria-label"));
  assert.ok(names.includes(`Feed the cat, ${localize("child.done")}`), names.join(" | "));
  assert.ok(names.includes(`Make bed, ${localize("child.awaiting_approval")}`), names.join(" | "));
  assert.ok(names.includes(`Teeth, ${localize("child.chore_locked")}. ${localize("child.not_scheduled_for_today")}`), names.join(" | "));
});

test("without the awaiting-approval rule, nothing reads as waiting", () => {
  const card = makeCard({ chores: [chore()], completions: doneToday("zz"), design: "playroom" });
  card._isAwaitingApproval = () => false; // nothing is waiting, with or without feat/child-card-awaiting-approval
  const chip = render(card.render()).control(/tmd-undochip/);
  assert.equal(chip.attr("aria-label"), localize("child.undo_done_aria", { chore: "Feed the cat" }));
});

test("the pending header chip is named with the points name", () => {
  const card = makeCard({ chores: [chore()], design: "playroom", child: { pending_points: 10 } });
  card.hass.states[ENTITY].attributes.points_name = "Stars";
  const { markup } = render(card.render());
  const m = markup.match(/<span class="tmd-pending"[^>]*>/);
  assert.ok(m, "the pending chip renders");
  assert.match(m[0], /role="img"/);
  assert.ok(m[0].includes(`aria-label="${localize("child.pending_points_aria", { count: "10", points_name: "Stars" })}"`), m[0]);
});

test("graphite hides its row numbers from screen readers; cleanpro keeps them", () => {
  for (const [design, hidden] of [["graphite", "true"], ["cleanpro", "false"]]) {
    const card = makeCard({ chores: [chore()], design });
    card.getAttribute = (n) => (n === "data-tm-design" ? design : null);
    const { markup } = render(card.render());
    const m = markup.match(/<div class="c-num"[^>]*>/);
    assert.ok(m, `${design}: the number renders`);
    assert.match(m[0], new RegExp(`aria-hidden="${hidden}"`));
  }
});

test("accessible's badge discs use Okabe-Ito hues, not tier metals", () => {
  const card = makeCard({ chores: [chore()], design: "accessible" });
  const tiers = ["bronze", "silver", "gold", "platinum"];
  card._resolveBadgesEntity = () => ({ attributes: { earned: tiers.map((t, i) => ({ badge_id: `b${i}`, tier: t, icon: "mdi:medal" })) } });
  const { markup } = render(card.render());
  const fills = [...markup.matchAll(/class="tmd-badge-mini[^"]*"\s*style="--t:([^"]+)"/g)].map((m) => m[1]);
  assert.deepEqual(fills, ["#D55E00", "#56B4E9", "#E69F00", "#009E73"]);
  const pr = makeCard({ chores: [chore()], design: "playroom" });
  pr._resolveBadgesEntity = card._resolveBadgesEntity;
  assert.match(render(pr.render()).markup, /--t:#f1c40f/, "other styles keep the tier colours");
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
  card._needsApproval = () => false;
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
