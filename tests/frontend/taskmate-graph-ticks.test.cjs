"use strict";
// The graph's y-axis ticks are evenly spaced, nice numbers (#771): rounding
// max/4 labelled a 0–10 axis 0 / 3 / 5 / 8 / 10.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

const { get } = loadCard("taskmate-graph-card.js");
const card = new (get("taskmate-graph-card"))();

for (const val of [1, 3, 7, 10, 11, 17, 21, 37, 41, 99, 101, 250, 999, 1234, 4321, 10000]) {
  test(`a chart up to ${val} gets even, nice ticks`, () => {
    const max = card._niceMax(val);
    const ticks = card._yTicks(max);
    assert.ok(max >= val, "the axis covers the data");
    assert.equal(ticks[0], 0);
    assert.equal(ticks.at(-1), max);
    const step = ticks[1] - ticks[0];
    ticks.forEach((t, i) => assert.equal(t, i * step, `tick ${i} of ${JSON.stringify(ticks)}`));
    assert.match(String(step / Math.pow(10, Math.floor(Math.log10(step)))), /^(1|2|5)$/, `step ${step} is 1, 2 or 5 × 10ⁿ`);
    assert.ok(ticks.length >= 3 && ticks.length <= 7, `${ticks.length} ticks`);
  });
}

test("a 0–10 chart is labelled 0, 2, 4, 6, 8, 10", () => {
  assert.deepEqual([...card._yTicks(card._niceMax(10))], [0, 2, 4, 6, 8, 10]);
});
