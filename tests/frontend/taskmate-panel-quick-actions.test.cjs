const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { WWW } = require("./harness.cjs");

// #771 gate: on Today, the Quick actions buttons ran out of their card at
// 1280px with Home Assistant's sidebar open (German, French, Polish labels):
// two `1fr` columns cannot shrink below their nowrap labels.

const SRC = readFileSync(path.join(WWW, "taskmate-panel.js"), "utf8");
const rule = (sel) => {
  const m = SRC.match(new RegExp(`\\n\\s*${sel.replace(/[\\^$.*+?()[\]{}|]/g, "\\$&")} \\{([^}]*)\\}`));
  assert.ok(m, `no ${sel} rule`);
  return m[1];
};

test("the quick-action grid's columns can shrink, and never exceed two", () => {
  const grid = rule(".tm-today-quick");
  assert.doesNotMatch(grid, /grid-template-columns:\s*1fr 1fr/);
  assert.match(grid, /minmax\(max\(min\(100%, 150px\), calc\(\(100% - 8px\) \/ 2\)\), 1fr\)/);
});

test("a long quick-action label wraps inside its button", () => {
  const btn = rule(".tm-today-quick .tm-btn");
  assert.match(btn, /min-width:\s*0/);
  assert.match(btn, /white-space:\s*normal/);
  assert.match(btn, /overflow-wrap:\s*anywhere/);
});
