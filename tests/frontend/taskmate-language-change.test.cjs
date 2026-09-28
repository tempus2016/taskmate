const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const { WWW } = require("./harness.cjs");

// A language change must re-render the cards (#994). HA hands every card a new
// `hass` whose `states` is the same object when only the profile language
// changed, so the cards' update guard used to call it irrelevant: they kept the
// old language's strings and dir="ltr" until some TaskMate entity changed.

function loadResolver() {
  const window = {};
  // The module ends by queueing a DOM walk; there is no DOM here to walk.
  const queueMicrotask = () => {};
  vm.runInNewContext(readFileSync(path.join(WWW, "taskmate-attr-resolver.js"), "utf8"), { window, queueMicrotask });
  return window.__taskmate_hasChanged;
}

const META = { en: { isRTL: false }, ar: { isRTL: true }, he: { isRTL: true } };
const STATES = { "sensor.taskmate_overview": { state: "ok" }, "light.kitchen": { state: "on" } };

function hass(language, states = STATES, translationMetadata = { translations: META }) {
  return { language, states, translationMetadata };
}

test("switching the language re-renders the card even though no entity changed", () => {
  const hasChanged = loadResolver();
  assert.equal(hasChanged(hass("en"), hass("ar"), "sensor.taskmate_overview"), true);
  assert.equal(hasChanged(hass("en"), hass("de"), "sensor.taskmate_overview"), true);
  assert.equal(hasChanged(hass("ar"), hass("en"), undefined), true);
});

test("a direction change from newly loaded translation metadata re-renders the card", () => {
  const hasChanged = loadResolver();
  const before = hass("ar", STATES, { translations: {} });
  assert.equal(hasChanged(before, hass("ar"), "sensor.taskmate_overview"), true);
});

test("an unchanged language with unchanged states still skips the render", () => {
  const hasChanged = loadResolver();
  assert.equal(hasChanged(hass("ar"), hass("ar"), "sensor.taskmate_overview"), false);
});

test("an unrelated entity change in the same language still skips the render", () => {
  const hasChanged = loadResolver();
  const next = { ...STATES, "light.kitchen": { state: "off" } };
  assert.equal(hasChanged(hass("en"), hass("en", next), "sensor.taskmate_overview"), false);
});
