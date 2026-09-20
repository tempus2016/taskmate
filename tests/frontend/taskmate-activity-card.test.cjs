const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { loadCard, WWW } = require("./harness.cjs");

// Report the key and params rather than the English string: several reasons are
// stored in the same English the locale file returns, so a missing prefix
// mapping would otherwise look identical to a successful translation.
const { get } = loadCard("taskmate-activity-card.js", {
  window: { __taskmate_localize: (_hass, key, params = {}) => JSON.stringify({ key, params }) },
});
const ActivityCard = get("taskmate-activity-card");

const messages = JSON.parse(readFileSync(path.join(WWW, "locales/en.json"), "utf8"));

function translate(reason) {
  const card = new ActivityCard();
  card.hass = { states: {} };
  card.config = { entity: "sensor.taskmate_activity" };
  const out = card._translateReason(reason);
  try {
    return JSON.parse(out);
  } catch {
    return { untranslated: out };
  }
}

// Transaction reasons are written to storage in English. Every reason the
// coordinator can produce needs a prefix mapping, or it reaches the activity
// feed in English no matter what language the household uses.

const REASONS = [
  ["Allocated to pool: Trampoline", "activity.reason_allocated_to_pool", "Trampoline"],
  ["Pool refund (reward expired): Trampoline", "activity.reason_pool_refund_expired", "Trampoline"],
  ["Pool refund (reward sold out): Trampoline", "activity.reason_pool_refund_sold_out", "Trampoline"],
  ["Pool refund (reward cost reduced): Trampoline", "activity.reason_pool_refund_cost_reduced", "Trampoline"],
  ["Pool refund (reward deleted): Trampoline", "activity.reason_pool_refund_deleted", "Trampoline"],
  ["Pool refund (reward funding changed): Trampoline", "activity.reason_pool_refund_funding_changed", "Trampoline"],
  [
    "Pool refund (reward assignment changed): Trampoline",
    "activity.reason_pool_refund_assignment_changed",
    "Trampoline",
  ],
  ["Penalty: Messy room", "activity.reason_penalty", "Messy room"],
  ["Bonus: Helped out", "activity.reason_bonus", "Helped out"],
];

for (const [reason, key, name] of REASONS) {
  test(`"${reason}" is localised`, () => {
    assert.deepEqual(translate(reason), { key, params: { name } });
    assert.ok(messages[key], `${key} is missing from en.json`);
  });
}

test("an unmapped reason is passed through unchanged", () => {
  assert.deepEqual(translate("Something we do not map"), { untranslated: "Something we do not map" });
});

test("a blank reason is left alone", () => {
  assert.deepEqual(translate(""), { untranslated: "" });
});
