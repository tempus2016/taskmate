const assert = require("node:assert/strict");
const { readFileSync, readdirSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { WWW } = require("./harness.cjs");

// #1234: the Bonuses and Penalties cards share taskmate-incentive-card.js and
// look every string up under their own prefix (P.i18n). The shared code asked
// for `add_bonus` / `new_bonus` / `toast_saved` on both, so the Penalties card
// showed "penalties.new_bonus" and "penalties.add_bonus" as raw keys. Every key
// the shared card and its editor ask for must exist under BOTH prefixes, in
// every locale, and in the bundle the card loads.

const LOCALES = path.join(WWW, "locales");
const langs = readdirSync(LOCALES).filter((f) => f.endsWith(".json")).map((f) => f.slice(0, -5));
const loc = (l) => JSON.parse(readFileSync(path.join(LOCALES, `${l}.json`), "utf8"));
const bundle = (l, b) => JSON.parse(readFileSync(path.join(LOCALES, l, `${b}.json`), "utf8"));

const src = (f) => readFileSync(path.join(WWW, f), "utf8");
const card = src("taskmate-incentive-card.js");
const editor = src("editors/taskmate-incentive-card-editor.js");

// The keys each wrapper passes in as P.addKey / P.newKey.
function wrapperKeys(file) {
  const s = src(file);
  const prefix = s.match(/i18n: "([a-z_]+)"/)[1];
  const add = s.match(/addKey: "([a-z_]+)"/);
  const neu = s.match(/newKey: "([a-z_]+)"/);
  assert.ok(add && neu, `${file} must set addKey and newKey`);
  return { prefix, keys: [add[1], neu[1]] };
}

const literal = (s) => [...s.matchAll(/_tp\('([a-z_.]+)'/g)].map((m) => m[1]);
const cardKeys = [...new Set(literal(card))];
const editorKeys = [...new Set(literal(editor))];

const WRAPPERS = ["taskmate-bonuses-card.js", "taskmate-penalties-card.js"].map(wrapperKeys);

test("the shared card only asks for keys through _tp literals or P.addKey / P.newKey", () => {
  // A computed _tp(...) other than these would slip past this test.
  const calls = [...card.matchAll(/_tp\(([^)]*)\)/g)].map((m) => m[1].split(",")[0].trim());
  const odd = calls.filter((a) => !/^'[a-z_.]+'$/.test(a) && a !== "P.addKey" && a !== "P.newKey" && a !== "key");
  assert.deepEqual(odd, []);
  assert.ok(!/_tp\('(add|new)_(bonus|penalty)'\)/.test(card), "add/new labels must come from P");
});

for (const { prefix, keys } of WRAPPERS) {
  test(`${prefix}: every key the card and editor ask for exists in every locale`, () => {
    const missing = [];
    for (const l of langs) {
      const d = loc(l);
      const cards = bundle(l, "cards");
      const ed = bundle(l, "editor");
      for (const k of [...cardKeys, ...keys]) {
        const full = `${prefix}.${k}`;
        if (typeof d[full] !== "string" || !d[full].trim()) missing.push(`${l}: ${full}`);
        else if (!(full in cards)) missing.push(`${l}/cards.json: ${full}`);
      }
      for (const k of editorKeys) {
        const full = `${prefix}.${k}`;
        if (typeof d[full] !== "string" || !d[full].trim()) missing.push(`${l}: ${full}`);
        else if (!(full in ed) && !(full in cards)) missing.push(`${l}/editor.json: ${full}`);
      }
    }
    assert.deepEqual(missing, []);
  });
}

test("the Penalties card's buttons say penalty, not bonus", () => {
  const pen = WRAPPERS.find((w) => w.prefix === "penalties");
  const en = loc("en");
  assert.deepEqual(pen.keys.map((k) => en[`penalties.${k}`]), ["Add Penalty", "New Penalty"]);
  assert.equal(en["penalties.toast_saved"], "Penalty saved");
});
