/**
 * Motion rules for the child card.
 *
 * Old iOS 15 iPads on kiosk walls struggle with animations that never stop, so
 * only busy spinners may loop. Every animation also needs a reduced-motion
 * fallback, and that block has to come last in the stylesheet or the earlier
 * rules of equal specificity win.
 */

const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");

const src = readFileSync(
  path.join(__dirname, "../../custom_components/taskmate/www/taskmate-child-card.js"), "utf8");

const BUSY_SPINNERS = ["tm-roulette-spin", "photo-spin", "spin"];

test("only busy spinners loop forever", () => {
  const loops = [...src.matchAll(/animation:\s*([\w-]+)[^;"]*\binfinite\b/g)].map((m) => m[1]);
  assert.ok(loops.length > 0, "the spinners are still found");
  for (const name of loops) assert.ok(BUSY_SPINNERS.includes(name), `${name} loops forever`);
});

test("no overshooting elastic easing", () => {
  assert.doesNotMatch(src, /cubic-bezier\(\s*0\.68,\s*-0\.55/);
});

test("the card has one reduced-motion block, after every animation rule", () => {
  const blocks = src.split("@media (prefers-reduced-motion: reduce)").length - 1;
  assert.equal(blocks, 1);
  const start = src.indexOf("static get styles()");
  const at = src.indexOf("@media (prefers-reduced-motion: reduce)");
  const stylesEnd = src.indexOf("`;", at);
  assert.ok(start < at, "the block is inside the base stylesheet");
  assert.doesNotMatch(src.slice(src.indexOf("}\n      }", at), stylesEnd), /animation|transition/,
    "nothing animates after the reduced-motion block");
  const block = src.slice(at, stylesEnd);
  for (const sel of [
    ".empty-state ha-icon", ".celebration-stars", ".chore-card.celebrating", ".badge-mini.just-earned",
    ".recording-dot", ".tm-boost-bolt", ".tm-boost-take-bolt", ".tm-screen-live", ".photo-spinner",
    ".roulette-btn.is-spinning ha-icon", 'ha-icon[icon="mdi:loading"]', ".photo-sheet", ".celebration-content",
  ]) {
    assert.ok(block.includes(sel), `${sel} has a reduced-motion fallback`);
  }
});
