const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const { WWW } = require("./harness.cjs");

// Switching HA between light and dark hands every card a new `hass` with the
// same `states` object, so the cards' update guard called it irrelevant. The
// designed styles stamp data-tm-dark during render, so they kept the old
// mode's colours until some TaskMate entity happened to change (found on the
// kiosk during the #771 phone sweep: cleanpro and console stayed light).

function loadResolver() {
  const window = {};
  const queueMicrotask = () => {};
  vm.runInNewContext(readFileSync(path.join(WWW, "taskmate-attr-resolver.js"), "utf8"), { window, queueMicrotask });
  return window.__taskmate_hasChanged;
}

const STATES = { "sensor.taskmate_overview": { state: "ok" }, "light.kitchen": { state: "on" } };
const hass = (darkMode, states = STATES) => ({ language: "en", states, themes: { theme: "default", darkMode } });

test("switching to dark or back re-renders the card even though no entity changed", () => {
  const hasChanged = loadResolver();
  assert.equal(hasChanged(hass(false), hass(true), "sensor.taskmate_overview"), true);
  assert.equal(hasChanged(hass(true), hass(false), undefined), true);
});

test("a hass without themes counts as light, so gaining a light theme is no change", () => {
  const hasChanged = loadResolver();
  const bare = { language: "en", states: STATES };
  assert.equal(hasChanged(bare, hass(false), "sensor.taskmate_overview"), false);
  assert.equal(hasChanged(bare, hass(true), "sensor.taskmate_overview"), true);
});

test("an unchanged mode with unchanged states still skips the render", () => {
  const hasChanged = loadResolver();
  assert.equal(hasChanged(hass(true), hass(true), "sensor.taskmate_overview"), false);
});
