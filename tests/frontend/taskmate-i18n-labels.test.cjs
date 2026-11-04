const assert = require("node:assert/strict");
const { readFileSync, readdirSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { WWW } = require("./harness.cjs");

// #771 gate: the German Streak card was titled "Erfolge und Erfolge", and the
// admin panel's menu button said "Menu" to a screen reader in every language.

const LOCALES = path.join(WWW, "locales");
const read = (f) => readFileSync(path.join(WWW, f), "utf8");
const sources = readdirSync(LOCALES).filter((f) => f.endsWith(".json"));

test("the Streak card's default title does not repeat a word in any language", () => {
  for (const f of sources) {
    const title = JSON.parse(readFileSync(path.join(LOCALES, f), "utf8"))["streak.default_title"];
    const words = title.toLowerCase().match(/\p{L}+/gu).filter((w) => w.length > 3);
    assert.equal(new Set(words).size, words.length, `${f}: "${title}" repeats a word`);
  }
});

test("the panel's Home Assistant menu button is labelled in every language", () => {
  const src = read("taskmate-panel.js");
  assert.match(src, /data-act="toggle-ha-menu" aria-label="\$\{this\._esc\(this\._t\("panel\.ha_menu"\)\)\}"/);
  const en = JSON.parse(readFileSync(path.join(LOCALES, "en.json"), "utf8"))["panel.ha_menu"];
  for (const f of sources) {
    const v = JSON.parse(readFileSync(path.join(LOCALES, f), "utf8"))["panel.ha_menu"];
    assert.ok(v && v.trim(), `${f} lacks panel.ha_menu`);
    if (!f.startsWith("en")) assert.notEqual(v, en, `${f} leaves panel.ha_menu in English`);
  }
});

test("no card, editor or panel hardcodes an English aria-label, title or alt", () => {
  const files = [
    ...readdirSync(WWW).filter((f) => /^taskmate-.*\.js$/.test(f)),
    ...readdirSync(path.join(WWW, "editors")).map((f) => `editors/${f}`),
  ];
  const found = [];
  for (const f of files) {
    read(f).split("\n").forEach((line, i) => {
      // A literal attribute value with an English word in it (not a ${...} expression).
      for (const m of line.matchAll(/\b(aria-label|title|alt)="([^"$]*)"/g)) {
        if (/[A-Za-z]{3,}/.test(m[2]) && !/^TaskMate\b/.test(m[2])) found.push(`${f}:${i + 1} ${m[0]}`);
      }
      if (/setAttribute\("aria-label", [a-zA-Z]+ \|\| "[A-Z]/.test(line)) found.push(`${f}:${i + 1} English fallback`);
    });
  }
  assert.deepEqual(found, []);
});
