// Points graph header on a narrow card (v7.7.1 recheck).
//
// At ~360px the title was cut short beside the Daily/Total/Growth toggle
// ("Punktediagr…", "Points Graph — V…"). The header now wraps: the toggle
// moves under the title, and the title itself wraps instead of an ellipsis.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

const Card = loadCard("taskmate-graph-card.js").get("taskmate-graph-card");
const css = () => render(Card.styles).markup;
const rule = (s, selector) => {
  const at = s.indexOf(`\n      ${selector} {`);
  assert.ok(at >= 0, `${selector} rule exists`);
  return s.slice(at, s.indexOf("}", at));
};

test("classic: the header wraps at any card width and the title is never truncated", () => {
  const s = css();
  assert.match(rule(s, ".card-header"), /flex-wrap: wrap/);
  assert.match(rule(s, ".header-left"), /flex: 1 1 auto/);
  const title = rule(s, ".header-title");
  assert.doesNotMatch(title, /nowrap|ellipsis/);
  assert.match(title, /overflow-wrap: break-word/);
});

test("designed styles: the header title wraps instead of an ellipsis", () => {
  assert.match(css(), /\.tmd-hd \.tt \{ white-space: normal; overflow-wrap: break-word; \}/);
});
