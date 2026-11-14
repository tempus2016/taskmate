"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

// Long lists on the designed styles: a done/total bar under the section title,
// finished rows folded behind a "Show finished" disclosure past eight rows,
// the undo strip moved to the end of the card, and Playroom showing one
// leading mark per row (picture, or the number when there is none).

const ALIAS = { graphite: "cleanpro" };
const { get } = loadCard("taskmate-child-card.js", {
  window: {
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
const NOW = new Date().toISOString();
const SOON = new Date(Date.now() + 10 * 60000).toISOString();

const chore = (id, name, extra = {}) => ({
  id, name, points: 5, time_category: "anytime", assigned_to: [], due_days: [], daily_limit: 1, ...extra,
});
const done = (id, extra = {}) => ({
  completion_id: `k${id}`, id: `k${id}`, chore_id: id, chore_name: id, child_id: "kid1",
  completed_at: NOW, approved: true, ...extra,
});

function makeCard(design, chores, completions = [], config = {}) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: "kid1", card_design: design, show_badges: false, ...config };
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", chore_order: [] }],
          chores,
          todays_completions: completions,
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card._resolveBadgesEntity = () => null;
  return card;
}

const twelve = Array.from({ length: 12 }, (_, i) => chore(`c${i + 1}`, `Job ${i + 1}`));
// c1..c4 finished, c5 waiting for a grown-up.
const twelveDone = ["c1", "c2", "c3", "c4"].map((id) => done(id)).concat(done("c5", { approved: false }));

const ROW = { playroom: "tmd-chore", console: "tmd-quest", cleanpro: "tmd-check", accessible: "tmd-check", graphite: "tmd-check" };
const rowCount = (markup, design) => (markup.match(new RegExp(`class="${ROW[design]} `, "g")) || []).length;

for (const design of Object.keys(ROW)) {
  test(`${design}: a long list folds finished rows but keeps open and waiting ones`, async () => {
    const card = makeCard(design, twelve, twelveDone);
    let view = render(card.render());
    assert.equal(rowCount(view.markup, design), 8, "4 finished rows folded away");
    assert.ok(view.markup.includes("Job 5"), "waiting row stays visible");
    const toggle = view.control("tmd-finished-toggle");
    assert.ok(toggle, "disclosure rendered");
    assert.equal(toggle.text, "Show finished (4)");
    assert.match(toggle.attrs, /aria-expanded="false"/);
    await toggle.click();
    view = render(card.render());
    assert.equal(rowCount(view.markup, design), 12, "expanded shows every row");
    assert.equal(view.control("tmd-finished-toggle").text, "Hide finished");
  });

  test(`${design}: progress bar reports finished of total`, () => {
    const { markup } = render(makeCard(design, twelve, twelveDone).render());
    assert.match(markup, /class="tmd-progress" role="progressbar" aria-label="4 of 12 done, 1 waiting for a grown-up"/);
    assert.match(markup, /aria-valuemax="12" aria-valuenow="4"/);
  });

  test(`${design}: a short list never folds`, () => {
    const short = twelve.slice(0, 8);
    const { markup } = render(makeCard(design, short, twelveDone).render());
    assert.equal(rowCount(markup, design), 8);
    assert.ok(!markup.includes("tmd-finished-toggle"));
  });

  test(`${design}: the undo strip sits after the list`, () => {
    const comps = [done("c1", { child_undo_until: SOON })];
    const { markup } = render(makeCard(design, twelve.slice(0, 3), comps).render());
    const undo = markup.indexOf('class="tm-child-undo"');
    assert.ok(undo > 0, "undo strip rendered");
    assert.ok(undo > markup.lastIndexOf(`class="${ROW[design]} `), "after the last row");
  });
}

test("the awaiting-approval helper, when present, decides what is waiting", () => {
  const card = makeCard("playroom", twelve, ["c1", "c2", "c3", "c4", "c5"].map((id) => done(id)));
  // Stub of feat/child-card-awaiting-approval's helper: c1 still waits.
  card._isAwaitingApproval = (ch) => ch.id === "c1";
  const { markup, control } = render(card.render());
  assert.equal(control("tmd-finished-toggle").text, "Show finished (4)");
  assert.ok(markup.includes("Job 1"), "waiting row kept");
  assert.ok(!markup.includes("Job 2<"), "finished row folded");
});

test("pre-reader mode never folds", () => {
  const { markup } = render(makeCard("playroom", twelve, twelveDone, { pre_reader: true }).render());
  assert.ok(!markup.includes("tmd-finished-toggle"));
});

test("classic: undo strip moves to the end without reordering the other blocks", () => {
  const comps = [done("c1", { child_undo_until: SOON })];
  const { markup } = render(makeCard("classic", twelve.slice(0, 3), comps).render());
  const undo = markup.indexOf('class="tm-child-undo"');
  const list = markup.indexOf('class="chores-container"');
  assert.ok(list > 0 && undo > list, "undo strip after the chore list");
  assert.ok(!markup.includes("tmd-finished-toggle"), "classic keeps its flat list");
});

test("playroom: a row with a picture drops the number badge; one without keeps it", () => {
  const chores = [chore("p1", "Brush teeth"), chore("p2", "Zorble"), chore("p3", "Zorble two", { icon: "mdi:broom" })];
  const { markup } = render(makeCard("playroom", chores).render());
  const rows = markup.split('class="tmd-chore ').slice(1);
  assert.ok(!rows[0].includes("num-badge") && rows[0].includes("ch-emoji"), "guessed emoji, no number");
  assert.ok(rows[1].includes('class="num-badge"') && !rows[1].includes("ch-emoji"), "no picture: number only");
  assert.ok(!rows[2].includes("num-badge") && rows[2].includes("tmd-glyph-icon"), "icon, no number");
});

test("console keeps its quest numbers next to the picture", () => {
  const { markup } = render(makeCard("console", [chore("p1", "Brush teeth")]).render());
  assert.ok(markup.includes('class="num q-num"'));
  assert.ok(markup.includes('class="q-emoji"'));
});
