"use strict";
// A recurring chore in its cooldown says its cadence in the child's language
// and when it opens again (#771) — not the raw "every 3 days" key.

const assert = require("node:assert/strict");
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
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const iso = (days) => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

function card(design, chore, nextOpen) {
  const c = new ChildCard();
  c.config = { entity: ENTITY, child_id: "kid1", card_design: design, recurrence_done_mode: "dim" };
  c.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", chore_order: [], weekly_chore_progress: {} }],
          chores: [{ id: "zz", name: "Water plants", points: 3, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "recurring", daily_limit: 1, ...chore }],
          todays_completions: [],
          chore_availability: { zz: { kid1: false } },
          chore_next_open: nextOpen ? { zz: { kid1: nextOpen } } : {},
          today_day_of_week: "wednesday",
        },
      },
    },
  };
  c._loading = {};
  c._optimisticCompletions = {};
  return render(c.render()).markup;
}

for (const design of DESIGNS) {
  test(`${design}: a cooldown shows the translated cadence and when it is next open`, () => {
    const markup = card(design, { recurrence: "every_3_days" }, iso(2));
    const day = new Date(`${iso(2)}T12:00:00`).toLocaleDateString(undefined, { weekday: "long" });
    assert.ok(markup.includes(localize("child.recurrence_every_n_days", { count: 3 })), "cadence");
    assert.ok(markup.includes(localize("child.recurrence_next", { day })), "next open day");
    assert.doesNotMatch(markup, /every 3 days/);
  });

  test(`${design}: the default weekly (omitted by the sensor) reads "Weekly"`, () => {
    const markup = card(design, {}, "");
    assert.ok(markup.includes(localize("child.recurrence_weekly")));
    assert.doesNotMatch(markup, new RegExp(localize("child.recurrence_next", { day: "" }).trim()));
  });
}

test("every recurrence the panel offers has a card label", () => {
  for (const [rec, key] of [["every_2_weeks", "child.recurrence_every_2_weeks"], ["monthly", "child.recurrence_monthly"],
    ["every_3_months", "child.recurrence_every_3_months"], ["every_6_months", "child.recurrence_every_6_months"]]) {
    assert.ok(card("classic", { recurrence: rec }, "").includes(localize(key)), rec);
  }
});

// "🕒 Every 3 days · Next: Friday" wraps on a phone-width card. The designed
// tag must then stay a clean rounded box (#771): a 999px pill radius pinched
// a two-line tag, and line-height 1 jammed its lines together.
test("designed tags wrap cleanly: fixed radius, room between lines", () => {
  const src = require("node:fs").readFileSync(require("node:path").join(__dirname, "../../custom_components/taskmate/www/taskmate-child-card.js"), "utf8");
  const rule = src.slice(src.indexOf("      .tmd-tag {"), src.indexOf("}", src.indexOf("      .tmd-tag {")));
  assert.doesNotMatch(rule, /border-radius:\s*999px/);
  assert.doesNotMatch(rule, /line-height:\s*1;/);
  assert.match(rule, /max-width:\s*100%/);
});
