"use strict";
// Long names and lock reasons wrap tidily on a phone-width card. A designed
// lock reason ("🔒 Do Tidy bedroom first") keeps its icon apart from the
// words so the icon stays on the first line, and a classic chore name wraps
// to two lines instead of ellipsising after one.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const ALIAS = { graphite: "cleanpro" };
const { get } = loadCard("taskmate-child-card.js", {
  window: {
    __taskmate_badge_id: (b) => b.badge_id,
    __taskmate_design: {
      apply: (_c, _h, config) => ALIAS[config?.card_design || "classic"] || config?.card_design || "classic",
      styles: () => null,
      editorOptions: () => [],
    },
  },
});
const ChildCard = get("taskmate-child-card");
const ENTITY = "sensor.taskmate_overview";
const SRC = fs.readFileSync(path.join(__dirname, "../../custom_components/taskmate/www/taskmate-child-card.js"), "utf8");

function card(design) {
  const c = new ChildCard();
  c.config = { entity: ENTITY, child_id: "kid1", card_design: design, dependency_mode: "dim" };
  const base = { points: 3, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", daily_limit: 1 };
  c.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", chore_order: [] }],
          chores: [
            { ...base, id: "tidy", name: "Tidy bedroom" },
            { ...base, id: "cat", name: "Feed the cat", depends_on: ["tidy"] },
          ],
          todays_completions: [],
        },
      },
    },
  };
  c._loading = {};
  c._optimisticCompletions = {};
  return render(c.render()).markup;
}

// The rule body for a selector, from the card's own stylesheet.
function rule(selector) {
  const at = SRC.indexOf(`      ${selector} {`);
  assert.ok(at >= 0, `${selector} rule exists`);
  return SRC.slice(at, SRC.indexOf("}", at));
}

for (const design of ["playroom", "console", "cleanpro", "accessible", "graphite"]) {
  test(`${design}: a lock reason keeps its icon and its words in separate boxes`, () => {
    const markup = card(design);
    const why = localize("child.blocked_by_dependency", { chores: "Tidy bedroom" });
    assert.match(markup, /class="tmd-tag tmd-why"><span class="tmd-why-ic">🔒<\/span><span class="tmd-why-tx">/);
    assert.ok(markup.includes(why), "the reason is shown");
  });
}

test("designed lock reasons align the icon to the first line and wrap prettily", () => {
  assert.match(rule(".tmd-why"), /align-items:\s*flex-start/);
  assert.match(rule(".tmd-why"), /text-wrap:\s*pretty/);
  assert.match(rule(".tmd-why-ic"), /flex:\s*none/);
});

test("classic lock labels align the icon to the first line and break long words", () => {
  const r = rule(".dependency-label, .recurrence-label, .first-come-label");
  assert.match(r, /align-items:\s*flex-start/);
  assert.match(r, /overflow-wrap:\s*anywhere/);
  assert.match(r, /text-wrap:\s*pretty/);
});

test("classic chore names wrap to two lines instead of one", () => {
  const r = rule(".chore-card .chore-details > .chore-name");
  assert.match(r, /-webkit-line-clamp:\s*2/);
  assert.match(r, /white-space:\s*normal/);
  assert.match(r, /overflow-wrap:\s*anywhere/);
  assert.match(card("classic"), /class="chore-name">Feed the cat/);
});
