"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");

const { loadCard, render } = require("./harness.cjs");

// The designed styles reuse the classic timed card (_designTimed ->
// _renderTimedChoreCard), so it kept its light cyan classic look inside every
// designed style, dark variants included (#771). There is no layout engine
// here, so these pin the two halves of the fix: every designed style renders
// the timed card, and the card's surfaces, text and buttons are drawn from
// the shadow-scoped --tmd-* tokens rather than classic's fixed colours.

const SRC = fs.readFileSync(
  path.join(__dirname, "../../custom_components/taskmate/www/taskmate-child-card.js"),
  "utf8",
).replace(/\/\*[\s\S]*?\*\//g, "");
const D = ':host([data-tm-design]:not([data-tm-design="classic"]))';
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

function makeCard(design) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: "kid1", card_design: design };
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", chore_order: [], weekly_chore_progress: {} }],
          chores: [{
            id: "read", name: "Reading", points: 0, time_category: "anytime", assigned_to: [], due_days: [],
            schedule_mode: "specific_days", daily_limit: 1, task_type: "timed",
            timed_rate_minutes: 5, timed_rate_points: 2, timed_max_daily_minutes: 30,
          }],
          todays_completions: [],
          chore_availability: {},
          today_day_of_week: "wednesday",
          active_timed_sessions: [{ chore_id: "read", child_id: "kid1", state: "paused", total_seconds_today: 90 }],
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  return card;
}

/** Every CSS rule (selector + body) in the card's source that names `cls`. */
function rulesFor(selectorPart) {
  const out = [];
  const re = /([^{}]+)\{([^{}]*)\}/g;
  let m;
  while ((m = re.exec(SRC)) !== null) {
    const sel = m[1].trim();
    if (sel.includes(selectorPart)) out.push({ sel, body: m[2] });
  }
  return out;
}

for (const design of ["playroom", "console", "cleanpro", "accessible", "graphite"]) {
  test(`${design}: the timed card is rendered inside the designed list`, () => {
    const { markup } = render(makeCard(design).render());
    assert.match(markup, /class="tmd /, "the designed shell");
    assert.match(markup, /timed-chore-card/, "the timed card inside it");
    assert.match(markup, /timer-btn resume/);
  });
}

for (const part of [
  ".timed-chore-card {",
  ".timed-chore-card .chore-name",
  ".timed-rate",
  ".timer-display",
  ".timer-counter {",
  ".timer-btn.start",
  ".timer-btn.pause",
  ".timer-btn.stop",
  ".cap-track",
  ".cap-fill {",
]) {
  test(`designed styles draw "${part.replace(" {", "")}" from the design tokens`, () => {
    const designed = rulesFor(part.replace(" {", "")).filter((r) => r.sel.includes(D));
    assert.ok(designed.length, `no designed rule for ${part}`);
    assert.ok(designed.some((r) => /var\(--tmd-/.test(r.body)), `${part} must use --tmd-* tokens`);
  });
}

test("the designed timed card has no fixed light surface", () => {
  const card = rulesFor(".timed-chore-card").filter((r) => r.sel.startsWith(D) && r.sel.endsWith(".timed-chore-card"));
  assert.equal(card.length, 1);
  assert.match(card[0].body, /background:\s*var\(--tmd-surface-2\)/);
  assert.match(card[0].body, /color:\s*var\(--tmd-text\)/);
  assert.doesNotMatch(card[0].body, /#fff|white|--card-background-color|--fun-/);
});

test("classic keeps its own timed card styling", () => {
  const classic = rulesFor(".timed-chore-card").find((r) => r.sel === ".timed-chore-card");
  assert.ok(classic, "the classic rule is still there");
  assert.match(classic.body, /--fun-cyan/);
});

// A per-design override must out-rank the shared designed rule, or it is
// silently ignored (graphite's near-black buttons stayed green on ha-dev).
test("per-design timed-card overrides carry the same :not(classic) guard", () => {
  for (const d of ["console", "graphite", "accessible"]) {
    const rules = rulesFor(`:host([data-tm-design="${d}"]`).filter((r) => /timed-chore-card|timer-btn/.test(r.sel));
    assert.ok(rules.length, `${d} has timed-card overrides`);
    for (const r of rules) {
      for (const part of r.sel.split(",")) {
        assert.ok(
          part.includes(`:host([data-tm-design="${d}"]:not([data-tm-design="classic"]))`),
          `${d} override "${part.trim()}" would lose to the shared rule`,
        );
      }
    }
  }
});

// A long timed title cut off at "ZZ 771X timed ru…" on a phone while space
// was left beside it (#771): in the designed styles it wraps, and the rate
// chip drops under it when the row is narrow.
test("designed timed titles wrap instead of truncating", () => {
  const rule = rulesFor(".timed-chore-card .chore-name").find((r) => r.sel.startsWith(D));
  assert.match(rule.body, /white-space:\s*normal/);
  assert.match(rule.body, /text-overflow:\s*clip/);
  const row = rulesFor(".timed-top-row").find((r) => r.sel === `${D} .timed-top-row`);
  assert.match(row.body, /flex-wrap:\s*wrap/);
  // The chip stays beside a short title: the title column has no large basis.
  const details = rulesFor(".timed-top-row .chore-details").find((r) => r.sel.startsWith(D));
  assert.match(details.body, /flex:\s*1 1 0/);
  // Classic wraps a long title too.
  const classic = rulesFor(".timed-chore-card .chore-name").find((r) => r.sel === ".timed-chore-card .chore-name");
  assert.match(classic.body, /white-space:\s*normal/);
});
