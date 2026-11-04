"use strict";
// The activity list shows a transaction's reason in the reader's language
// (#771): rows with a reason_key render from the translation, older rows fall
// back to the English text (translated where its wording is known).

const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { loadCard, WWW } = require("./harness.cjs");

const de = JSON.parse(readFileSync(path.join(WWW, "locales", "de.json"), "utf8"));
const fill = (tpl, p) => tpl.replace(/\{(\w+)\}/g, (_, k) => (p[k] ?? ""));
// A German reader: look keys up in de.json.
const window = { __taskmate_localize: (_h, key, params = {}) => (de[key] !== undefined ? fill(de[key], params) : key) };

const A = loadCard("taskmate-activity-card.js", { window });
const P = loadCard("taskmate-panel.js", { window });

const card = new (A.get("taskmate-activity-card"))();
const panel = Object.create(P.get("taskmate-panel").prototype);
for (const [who, obj, win] of [["activity card", card, A.window], ["panel", panel, P.window]]) {
  test(`${who}: a keyed reason renders in the reader's language`, () => {
    const row = { reason: "Challenge reversed: E2E Test Challenge", reason_key: "challenge_reversed", reason_params: { name: "E2E Test Challenge" } };
    assert.equal(obj._reasonFor(row), fill(de["activity.reason_challenge_reversed"], { name: "E2E Test Challenge" }));
    assert.notEqual(obj._reasonFor(row), row.reason);
  });

  test(`${who}: an old row without a key is translated from its known wording`, () => {
    assert.equal(obj._reasonFor({ reason: "Quest complete: Spring clean" }), fill(de["activity.reason_quest_complete"], { name: "Spring clean" }));
    assert.equal(obj._reasonFor({ reason: "Surprise bonus 🎉" }), de["activity.reason_surprise_bonus"]);
  });

  test(`${who}: an unknown or custom reason is shown as stored`, () => {
    assert.equal(obj._reasonFor({ reason: "For helping grandma" }), "For helping grandma");
    assert.equal(obj._reasonFor({ reason: "x", reason_key: "not_a_real_key" }), "x");
  });

  test(`${who}: numbers in the reason follow HA's number format when the helper is loaded`, () => {
    win.__taskmate_numbers = { format: (_h, n) => `<${n}>` };
    try {
      const out = obj._reasonFor({ reason: "Weekly goal reached 🎯 (1500)", reason_key: "weekly_goal_reached", reason_params: { target: 1500 } });
      assert.equal(out, fill(de["activity.reason_weekly_goal_reached"], { target: "<1500>" }));
    } finally {
      delete win.__taskmate_numbers;
    }
  });
}

test("old rows with numbers in their reason are translated too", () => {
  for (const obj of [card, panel]) {
    assert.equal(obj._translateReason("Weekly goal reached 🎯 (1500)"), fill(de["activity.reason_weekly_goal_reached"], { target: "1500" }));
    assert.equal(obj._translateReason("Penalty: Bins (missed mandatory)"), fill(de["activity.reason_penalty_missed_mandatory"], { name: "Bins" }));
    assert.equal(obj._translateReason("Points decay (-10%), 5 from wish savings"), fill(de["activity.reason_points_decay_wish"], { pct: "10", wish: "5" }));
    assert.equal(obj._translateReason("Raffle tickets ×3: Lego"), fill(de["activity.reason_raffle_tickets"], { tickets: "3", name: "Lego" }));
  }
});

test("numbers in an old row's reason follow HA's number format too", () => {
  for (const [obj, win] of [[card, A.window], [panel, P.window]]) {
    win.__taskmate_numbers = { format: (_h, n) => `<${n}>` };
    try {
      assert.equal(obj._translateReason("Weekly goal reached 🎯 (1500)"), fill(de["activity.reason_weekly_goal_reached"], { target: "<1500>" }));
      assert.equal(obj._translateReason("Raffle tickets ×1200: Lego"), fill(de["activity.reason_raffle_tickets"], { tickets: "<1200>", name: "Lego" }));
    } finally {
      delete win.__taskmate_numbers;
    }
  }
});
