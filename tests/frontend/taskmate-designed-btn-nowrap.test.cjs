// Designed buttons keep their label on one line (v7.7.1 recheck).
//
// In the clean pro / graphite activity feed "↩ Rückgängig" broke over two
// lines beside a long row, and the same happened to "👍 Genehmigen" in
// playroom approvals and "‹ Vorheriger Tag" in the console calendar. The
// shared .btn no longer wraps; rows that hold several buttons wrap instead.

const assert = require("node:assert/strict");
const { test } = require("node:test");
const { readFileSync } = require("node:fs");
const path = require("node:path");

const { loadCard, render, WWW } = require("./harness.cjs");

test("the shared design kit's .btn never wraps its label", () => {
  const src = readFileSync(path.join(WWW, "taskmate-design.js"), "utf8");
  const rule = src.match(/\n\.btn\{[^}]*\}/)[0];
  assert.match(rule, /white-space:nowrap/);
});

test("activity: the designed Undo button keeps to one line and does not shrink", () => {
  const Card = loadCard("taskmate-activity-card.js").get("taskmate-activity-card");
  assert.match(render(Card.styles).markup, /\.tmd-undo \{ padding: 4px 11px; white-space: nowrap; flex-shrink: 0; \}/);
});

test("approvals: rows of designed action buttons wrap instead of running off the card", () => {
  const src = readFileSync(path.join(WWW, "taskmate-approvals-card.js"), "utf8");
  assert.match(src, /\.ap-cp-actions \{[^}]*flex-wrap: wrap;[^}]*max-width: 100%/);
  assert.match(src, /<div class="row" style="margin-top:11px;gap:8px;flex-wrap:wrap">\s*\$\{this\._designActions\(it, "full"\)\}/);
});
