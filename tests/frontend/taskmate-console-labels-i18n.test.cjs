const assert = require("node:assert/strict");
const { readFileSync, readdirSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { WWW } = require("./harness.cjs");

// #771 gate: the console style's child header read "Stufe 29 · 15 ACTIVE"
// (ACTIVE hard-coded in English), its quest rows said "CLEARED" and the graph
// card's console pill said "LIVE" in every language.

const read = (f) => readFileSync(path.join(WWW, f), "utf8");
const LOCALES = path.join(WWW, "locales");

test("the console labels come from the locale files", () => {
  const child = read("taskmate-child-card.js");
  assert.doesNotMatch(child, /\} ACTIVE`|`\$\{remaining\} ACTIVE`/);
  assert.doesNotMatch(child, />CLEARED</);
  assert.match(child, /this\._t\("child\.console_active", \{ count: remaining \}\)/);
  assert.match(child, /this\._t\("child\.console_cleared"\)/);
  const graph = read("taskmate-graph-card.js");
  assert.doesNotMatch(graph, />LIVE</);
  assert.match(graph, /this\._t\('graph\.console_live'\)/);
});

test("no card hard-codes an all-caps English word in its markup", () => {
  // Allowed: units and names that are the same in every language.
  const ALLOWED = new Set(["XP", "DEBUG", "TASKMATE"]);
  const found = [];
  for (const f of readdirSync(WWW).filter((n) => /^taskmate-.*-card\.js$/.test(n))) {
    read(f).split("\n").forEach((line, i) => {
      for (const m of line.matchAll(/>([A-Z]{3,}(?: [A-Z]{2,})*)</g)) if (!ALLOWED.has(m[1])) found.push(`${f}:${i + 1} ${m[1]}`);
      for (const m of line.matchAll(/\$\{[^}]+\} ([A-Z]{4,})`/g)) if (!ALLOWED.has(m[1])) found.push(`${f}:${i + 1} ${m[1]}`);
    });
  }
  assert.deepEqual(found, []);
});

test("every language has the console labels", () => {
  for (const f of readdirSync(LOCALES).filter((n) => n.endsWith(".json"))) {
    const d = JSON.parse(readFileSync(path.join(LOCALES, f), "utf8"));
    for (const k of ["child.console_active", "child.console_cleared", "graph.console_live"]) assert.ok(d[k] && d[k].trim(), `${f} lacks ${k}`);
    assert.match(d["child.console_active"], /\{count\}/);
  }
});
