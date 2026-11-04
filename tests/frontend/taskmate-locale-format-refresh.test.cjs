"use strict";
// A change to HA's number, date or time format re-renders the cards (#771).
// HA hands every card a new `hass` with the same `states` when only the
// profile's formats change, so the update guard called it irrelevant and the
// cards kept "1,234" / "05:00 PM" until some TaskMate entity changed.

const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const { WWW } = require("./harness.cjs");

function loadResolver() {
  const window = {};
  vm.runInNewContext(readFileSync(path.join(WWW, "taskmate-attr-resolver.js"), "utf8"), { window, queueMicrotask: () => {} });
  return window.__taskmate_hasChanged;
}

const STATES = { "sensor.taskmate_overview": { state: "ok" } };
const LOCALE = { language: "en", number_format: "language", time_format: "language", date_format: "language", time_zone: "local", first_weekday: "language" };
const hass = (locale = {}, config = { time_zone: "Europe/London" }) => ({
  language: "en", states: STATES, locale: { ...LOCALE, ...locale }, config,
});

for (const [field, value] of [
  ["number_format", "decimal_comma"],
  ["time_format", "24"],
  ["date_format", "DMY"],
  ["time_zone", "server"],
  ["first_weekday", "monday"],
]) {
  test(`changing ${field} alone re-renders the card`, () => {
    const hasChanged = loadResolver();
    assert.equal(hasChanged(hass(), hass({ [field]: value }), "sensor.taskmate_overview"), true);
  });
}

test("a new server time zone re-renders the card", () => {
  const hasChanged = loadResolver();
  assert.equal(hasChanged(hass(), hass({}, { time_zone: "Pacific/Auckland" }), "sensor.taskmate_overview"), true);
});

test("an equal locale in a new object, with the same states, is still no change", () => {
  const hasChanged = loadResolver();
  assert.equal(hasChanged(hass(), hass(), "sensor.taskmate_overview"), false);
});
