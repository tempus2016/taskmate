const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { loadCard, WWW } = require("./harness.cjs");

const { get } = loadCard("taskmate-panel.js");
const TaskMatePanel = get("taskmate-panel");
const SRC = readFileSync(path.join(WWW, "taskmate-panel.js"), "utf8");

// Multipart chores (#1253): the chore editor's Steps list. Each step was a
// .tm-field-row (a two-column grid), so its ↑, ↓ and ✕ buttons wrapped onto
// rows of their own and a phone showed every step as four stacked rows. A
// step is now one flex row: number, name, three compact icon buttons.

function render(steps) {
  const p = Object.create(TaskMatePanel.prototype);
  p._esc = (s) => String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
  p._t = (k, params) => (params && params.n ? `${k}:${params.n}` : k);
  p._fmtNum = (n) => String(n);
  p._dialog = { data: { steps }, _openAdvanced: new Set() };
  return p._renderChoreSteps({ steps });
}

const rows = (html) => [...html.matchAll(/<div class="tm-step-row">([\s\S]*?)<\/div>/g)].map(m => m[1]);

test("each step is one row: number, name, then three icon buttons", () => {
  const html = render([{ id: "a", name: "Clothes away" }, { id: "b", name: "Toys in the box" }]);
  assert.doesNotMatch(html, /tm-field-row/, "no two-column grid that wraps the buttons");
  const rs = rows(html);
  assert.equal(rs.length, 2);
  for (const r of rs) {
    assert.match(r, /^\s*<span class="tm-step-num"/);
    assert.match(r, /<input class="tm-input tm-step-name"/);
    const buttons = [...r.matchAll(/<button type="button" class="tm-icon-btn[^"]*"[^>]*aria-label="([^"]+)"/g)].map(m => m[1]);
    assert.deepEqual(buttons, ["panel.chore_step_move_up", "panel.chore_step_move_down", "panel.tooltip_remove"]);
  }
});

test("the first step can't move up and the last can't move down", () => {
  const [first, last] = rows(render([{ id: "a", name: "A" }, { id: "b", name: "B" }]));
  assert.match(first, /data-dir="-1" disabled/);
  assert.doesNotMatch(first, /data-dir="1" disabled/);
  assert.match(last, /data-dir="1" disabled/);
});

test("the row never wraps and fits a 360px phone", () => {
  const row = SRC.match(/\.tm-step-row \{[^}]*\}/)[0];
  assert.match(row, /display: flex/);
  assert.doesNotMatch(row, /flex-wrap: wrap/);
  assert.match(SRC, /\.tm-step-row \.tm-step-name \{[^}]*flex: 1 1 auto;[^}]*min-width: 0/);
  assert.match(SRC, /\.tm-step-row \.tm-icon-btn \{[^}]*flex: 0 0 28px/);
  // Fixed parts: number (~1.4em ≈ 20px) + 3 × 28px buttons + 4 × 4px gaps.
  // The phone dialog's content is ~320px wide, so the name keeps ≥ 180px.
  const fixed = 20 + 3 * 28 + 4 * 4;
  assert.ok(320 - fixed >= 180, `the name keeps ${320 - fixed}px`);
});
