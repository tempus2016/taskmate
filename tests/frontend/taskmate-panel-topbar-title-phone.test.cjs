const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { WWW } = require("./harness.cjs");

// On a 360-375 px phone the top bar holds the menu, the page title, search,
// the child scope chips, "?" and "+". The chips group used to win the fight
// for width, so the title shrank to "Fa…". Hub titles are one short word, so
// the title keeps its natural width and the chip group is the part that
// gives way (it already scrolls sideways when squeezed).

const SRC = readFileSync(path.join(WWW, "taskmate-panel.js"), "utf8");
const phone = SRC.slice(SRC.indexOf("@media (max-width: 480px) {"));
const block = phone.slice(0, phone.indexOf("\n      }\n") + 9);

test("the phone top bar never shrinks the page title below its own width", () => {
  assert.match(block, /\.tm-topbar \.tm-crumbs \{[^}]*flex: 0 0 auto/, "the title must keep its natural width on phones");
  assert.match(block, /\.tm-topbar \.tm-crumbs \{[^}]*max-width/, "but with a cap so a long crumb can't push the buttons off");
});

test("the child scope chips are the part that gives way on phones", () => {
  assert.match(block, /\.tm-scope \{[^}]*flex: 0 1 auto/, "the chip group must be allowed to shrink");
  assert.match(block, /\.tm-scope \{[^}]*min-width: 0/, "and have no flex floor, so it scrolls rather than squeezing the title");
});
