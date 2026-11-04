const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { WWW } = require("./harness.cjs");

// With the chore editor open beside the page (1100 px and up) the Chores
// table has only ~350-470 px. Its name column was pinned and kept a long
// name on one line, so at 1280 px the pinned column took 205 of 346 px and
// the Schedule column could never be scrolled fully into view (and with a
// long name, no other column at all). Names now wrap within a cap, and the
// pin is dropped while the side panel is open so the table scrolls whole.

const SRC = readFileSync(path.join(WWW, "taskmate-panel.js"), "utf8");
const block = (q) => {
  const from = SRC.slice(SRC.indexOf(q));
  return from.slice(0, from.indexOf("\n      }\n") + 9);
};

test("a long name in a pinned column wraps within a cap on desktop", () => {
  const desk = block("@media (min-width: 901px) {\n        .tm-table td.tm-col-sticky .tm-name-main");
  assert.match(desk, /\.tm-table td\.tm-col-sticky \.tm-name-main \{[^}]*max-width: 280px/);
  assert.match(desk, /\.tm-table td\.tm-col-sticky \.tm-name-main \{[^}]*white-space: normal/);
  assert.match(desk, /\.tm-table td\.tm-col-sticky \.tm-name-main \{[^}]*min-width: 140px/, "a short floor so names don't break letter by letter");
  assert.doesNotMatch(desk, /overflow-wrap: anywhere/);
});

test("beside the side panel the name column is not pinned and is narrower", () => {
  const wide = block("@media (min-width: 1100px) {\n        .tm-scrim.tm-scrim-drawer");
  assert.match(wide, /\.tm-shell-drawer \.tm-table th\.tm-col-sticky,\s*\.tm-shell-drawer \.tm-table td\.tm-col-sticky \{ position: static; \}/);
  assert.match(wide, /\.tm-shell-drawer \.tm-table td\.tm-col-sticky \.tm-name-main \{[^}]*max-width: 160px/);
});
