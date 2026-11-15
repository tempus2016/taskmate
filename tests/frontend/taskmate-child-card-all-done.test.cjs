"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// The all-done moment: once every chore owed today is ticked off, the card
// says so ("All done, Mia!" + today's total), folds the finished rows under a
// real disclosure button, and the mood check-in follows the banner. Zero
// chores is "nothing to do", never all done. The celebration overlay names
// the chore it celebrates.

// graphite reuses the cleanpro layout (LAYOUT_ALIAS in taskmate-design.js).
const ALIAS = { graphite: "cleanpro" };
const { get } = loadCard("taskmate-child-card.js", {
  window: {
    __taskmate_badge_id: (b) => b.badge_id,
    __taskmate_localize: (_hass, key, params) => localize(key, params),
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
const NOW = new Date().toISOString();

function chore(id, extra = {}) {
  return {
    id,
    name: `${id} chore`,
    points: 5,
    time_category: "anytime",
    assigned_to: [],
    due_days: [],
    schedule_mode: "specific_days",
    daily_limit: 1,
    ...extra,
  };
}

function done(id, extra = {}) {
  return { chore_id: id, child_id: "kid1", points: 5, approved: true, completed_at: NOW, ...extra };
}

function makeCard({ chores, completions = [], config = {}, design }) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: "kid1", card_design: design, ...config };
  const mia = { id: "kid1", name: "Mia", chore_order: [], weekly_chore_progress: {} };
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
          points_name: "Stars",
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  return card;
}

const BANNER = /class="tm-alldone /;
const TITLE = localize("child.all_done_name", { name: "Mia" });

for (const design of DESIGNS) {
  test(`${design}: no chores at all is not "all done"`, () => {
    const { markup } = render(makeCard({ chores: [], design }).render());
    assert.doesNotMatch(markup, BANNER);
    assert.ok(!markup.includes(TITLE));
  });

  test(`${design}: chores still to do show no banner and keep every row`, () => {
    const card = makeCard({ chores: [chore("a"), chore("b")], completions: [done("a")], design });
    const { markup } = render(card.render());
    assert.doesNotMatch(markup, BANNER);
    assert.match(markup, /a chore/);
    assert.match(markup, /b chore/);
  });

  test(`${design}: everything done shows the banner, today's total, and folds the rows`, () => {
    const card = makeCard({
      chores: [chore("a"), chore("b")],
      completions: [done("a"), done("b", { points: 7 })],
      design,
    });
    const { markup, control } = render(card.render());
    assert.match(markup, BANNER);
    assert.ok(markup.includes(TITLE), "names the child");
    assert.ok(markup.includes(localize("child.all_done_earned", { points: "12", points_name: "Stars" })), "today's total");
    assert.doesNotMatch(markup, /a chore/, "finished rows are folded away");

    const toggle = control(/tm-alldone-toggle/);
    assert.ok(toggle, "the disclosure is a control");
    assert.equal(toggle.tag, "button");
    assert.match(toggle.attrs, /type="button"/);
    assert.match(toggle.attrs, /aria-expanded="false"/);
    assert.ok(toggle.text.includes(localize("child.all_done_show")));

    toggle.click();
    const opened = render(card.render());
    assert.match(opened.markup, /a chore/, "the rows come back");
    assert.match(opened.markup, /b chore/);
    assert.match(opened.control(/tm-alldone-toggle/).attrs, /aria-expanded="true"/);
    assert.ok(opened.control(/tm-alldone-toggle/).text.includes(localize("child.all_done_hide")));
  });

  test(`${design}: the mood check-in follows the banner`, () => {
    const card = makeCard({ chores: [chore("a")], completions: [done("a")], design });
    const { markup } = render(card.render());
    const banner = markup.search(BANNER);
    const mood = markup.indexOf("tm-mood");
    assert.ok(banner >= 0 && mood > banner, "mood strip sits after the banner");
    assert.ok(mood < markup.indexOf("tm-alldone-toggle"), "and before the disclosure");
    assert.equal(markup.split('class="tm-mood').length - 1, 1, "only one mood strip");
  });

  test(`${design}: points still waiting for a grown-up are not counted as earned`, () => {
    const card = makeCard({
      chores: [chore("a"), chore("b")],
      completions: [done("a"), done("b", { approved: false, points: 3 })],
      design,
    });
    const { markup } = render(card.render());
    assert.ok(markup.includes(localize("child.all_done_earned", { points: "5", points_name: "Stars" })));
    assert.ok(markup.includes(localize("child.all_done_pending", { points: "3", points_name: "Stars" })));
  });

  test(`${design}: the five mood faces are named buttons styled by the card's design`, () => {
    const card = makeCard({ chores: [chore("a")], completions: [done("a")], design });
    const { markup, controls } = render(card.render());
    const mode = design === "classic" ? "classic" : "tmd";
    assert.match(markup, new RegExp(`class="tm-mood ${mode}"`));
    const faces = controls.filter((c) => /class="face"/.test(c.attrs));
    assert.equal(faces.length, 5);
    const names = faces.map((f) => f.attr("aria-label"));
    assert.deepEqual(names, ["great", "good", "ok", "sad", "upset"].map((m) => localize(`child.mood_${m}`)));
    for (const f of faces) assert.match(f.attrs, /type="button"/);
  });
}

// The faces sit in a fixed five-column grid (54px down to the 44px target
// floor) so they never wrap 4+1, and a designed style paints the strip from
// its own tokens rather than HA's grey secondary background.
test("mood strip CSS: one row of five, 44px floor, designed styles use tokens", () => {
  const src = require("node:fs").readFileSync(
    require("node:path").join(__dirname, "../../custom_components/taskmate/www/taskmate-child-card.js"), "utf8");
  const rule = (sel) => {
    const m = src.match(new RegExp(`\\n\\s*${sel.replace(/[.()]/g, "\\$&")} \\{([^}]*)\\}`));
    assert.ok(m, `rule for ${sel}`);
    return m[1];
  };
  const faces = rule(".tm-mood .faces");
  assert.match(faces, /display: grid/);
  assert.match(faces, /grid-template-columns: repeat\(5, minmax\(44px, 54px\)\)/);
  assert.doesNotMatch(faces, /flex-wrap/);
  assert.match(rule(".tm-mood .face"), /min-block-size: 44px/);
  const tmd = rule(".tm-mood.tmd");
  assert.match(tmd, /background: var\(--tmd-surface-2\)/);
  assert.match(tmd, /border: 1px solid var\(--tmd-border\)/);
  assert.match(tmd, /border-radius: var\(--tmd-radius-sm\)/);
  assert.match(tmd, /font-family: var\(--tmd-font-body\)/);
  assert.doesNotMatch(tmd, /secondary-background-color/);
});

test("a chore from a later part of the day keeps the banner away", () => {
  const card = makeCard({
    chores: [chore("a", { time_category: "morning" }), chore("b", { time_category: "evening" })],
    completions: [done("a")],
    config: { debug_time_period: "morning" },
    design: "classic",
  });
  assert.doesNotMatch(render(card.render()).markup, BANNER);
});

test("an open-ended 'something extra' row stays out of the count and stays visible", () => {
  const card = makeCard({
    chores: [chore("a"), chore("x", { open_ended: true, name: "Something extra" })],
    completions: [done("a")],
    design: "playroom",
  });
  const { markup } = render(card.render());
  assert.match(markup, BANNER);
  assert.match(markup, /Something extra/);
  assert.doesNotMatch(markup, /a chore/);
});

test("the entrance plays only on the change to all done, not on load", () => {
  const card = makeCard({ chores: [chore("a")], completions: [done("a")], design: "classic" });
  assert.doesNotMatch(render(card.render()).markup, /tm-alldone classic enter/, "already done on load");

  const fresh = makeCard({ chores: [chore("a")], completions: [], design: "classic" });
  render(fresh.render());
  fresh.hass.states[ENTITY].attributes.todays_completions = [done("a")];
  assert.match(render(fresh.render()).markup, /tm-alldone classic enter/);
});

test("pre-reader tiles keep every tile and get no text disclosure", () => {
  const card = makeCard({ chores: [chore("a")], completions: [done("a")], config: { pre_reader: true }, design: "classic" });
  const { markup } = render(card.render());
  assert.match(markup, BANNER);
  assert.doesNotMatch(markup, /tm-alldone-toggle/);
  assert.match(markup, /a chore/);
});

test("the celebration names the chore", () => {
  const card = makeCard({ chores: [chore("a", { name: "Make bed" })], design: "classic" });
  const chores = card.hass.states[ENTITY].attributes.chores;
  assert.equal(card._celebrationTitle(chores, "a"), localize("child.celebration_chore_done", { chore: "Make bed" }));
  assert.equal(card._celebrationTitle(chores, "a@0800"), localize("child.celebration_chore_done", { chore: "Make bed" }),
    "a set-time row finds its chore");
  assert.equal(card._celebrationTitle(chores, "gone"), localize("child.celebration_title"), "unknown chore falls back");

  card._celebrating = "a";
  card._celebrationPoints = 5;
  const { markup } = render(card._renderCelebration());
  assert.ok(markup.includes(localize("child.celebration_chore_done", { chore: "Make bed" })));
});

test("a sick day never reads as all done", () => {
  const card = makeCard({ chores: [chore("a")], completions: [done("a")], design: "classic" });
  card.hass.states[ENTITY].attributes.children[0].sick_today = true;
  assert.doesNotMatch(render(card.render()).markup, BANNER);
});
