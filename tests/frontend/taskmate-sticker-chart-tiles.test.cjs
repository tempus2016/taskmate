// Sticker chart tiles stay inside the card (v7.7.1 phone sweep).
//
// A finished tile is tilted and scaled up, so its corners reach past its grid
// cell. In the last column that ran 3px past a 377px card at 393px wide, in
// every design. The tile grid now has side padding that always covers the
// overhang; this pins the numbers the padding was sized from.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

const Card = loadCard("taskmate-sticker-chart-card.js", { topLevelAwait: true }).get("taskmate-sticker-chart-card");
const styles = () => render(Card.styles).markup;
const rule = (css, selector) => {
  const at = css.indexOf(`\n      ${selector} {`);
  assert.ok(at >= 0, `${selector} rule exists`);
  return css.slice(at, css.indexOf("}", at));
};

test("the tile grid pads its sides by at least 2% of the row", () => {
  assert.match(rule(styles(), ".tiles"), /padding-inline: max\(4px, 2%\)/);
});

test("a finished tile's tilt and scale fit inside that padding at any column count", () => {
  const done = rule(styles(), ".tile.done");
  const m = done.match(/transform: rotate\(-?([\d.]+)deg\) scale\(([\d.]+)\)/);
  assert.ok(m, done);
  const [deg, scale] = [Number(m[1]), Number(m[2])];
  assert.match(rule(styles(), ".tile"), /aspect-ratio: 1 \/ 1\.05/);
  const rad = (deg * Math.PI) / 180;
  // Extra width each side, as a share of the tile's own width (height 1.05w).
  const perSide = (scale * Math.cos(rad) + 1.05 * scale * Math.sin(rad) - 1) / 2;
  // Two columns (the fewest the card allows) give the widest tile: ~half the row.
  for (const cols of [2, 3, 4, 5, 6]) {
    const tileShare = 1 / cols;
    assert.ok(perSide * tileShare < 0.02, `${cols} columns: overhang ${(perSide * tileShare * 100).toFixed(2)}% of the row`);
  }
});
