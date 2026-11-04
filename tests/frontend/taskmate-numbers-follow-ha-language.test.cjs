"use strict";
// Numbers follow Home Assistant's language and number format (#771).
//
// Point totals were formatted with the browser's locale (`n.toLocaleString()`,
// `new Intl.NumberFormat()`), so a German HA on an English browser showed
// "1,234" points. Every displayed number now goes through one helper in
// taskmate-localize.js, window.__taskmate_numbers.format(hass, value, opts),
// which also honours HA's number_format setting.

const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");

const { loadCard, render, WWW } = require("./harness.cjs");

const numbers = loadCard("taskmate-localize.js", {
  sandbox: { fetch: () => Promise.reject(new Error("offline")) },
}).window.__taskmate_numbers;
// Absent on main: every test below then fails on its own, not the whole file.
const fmt = numbers ? numbers.format : () => { throw new Error("window.__taskmate_numbers is missing"); };

const hassFor = (language, number_format = "language") => ({ language, locale: { language, number_format } });
const NBSP = /[   ]/;

// ── the helper ────────────────────────────────────────────────────────────

test("helper: grouping follows HA's language", () => {
  assert.equal(fmt(hassFor("de"), 1234), "1.234");
  assert.equal(fmt(hassFor("en-GB"), 1234), "1,234");
  assert.equal(fmt(hassFor("en"), 1234567), "1,234,567");
});

test("helper: HA's number_format setting wins over the language", () => {
  assert.equal(fmt(hassFor("en", "decimal_comma"), 1234.5), "1.234,5");
  assert.equal(fmt(hassFor("de", "comma_decimal"), 1234.5), "1,234.5");
  const space = fmt(hassFor("en", "space_comma"), 1234.5);
  assert.match(space, /^1.234,5$/);
  assert.match(space[1], NBSP);
  assert.equal(fmt(hassFor("de", "none"), 1234567), "1234567");
});

test("helper: decimals keep the language's separator", () => {
  const one = { minimumFractionDigits: 1, maximumFractionDigits: 1 };
  assert.equal(fmt(hassFor("de"), 2.25, one), "2,3");
  assert.equal(fmt(hassFor("en-GB"), 2.25, one), "2.3");
});

test("helper: non-numbers come back unchanged; nullish is empty", () => {
  assert.equal(fmt(hassFor("de"), "—"), "—");
  assert.equal(fmt(hassFor("de"), null), "");
  assert.equal(fmt(hassFor("de"), 0), "0");
});

// ── the cards, the panel and the kiosk use it ─────────────────────────────

const ENTITY = "sensor.taskmate_overview";
const withHelper = { window: { __taskmate_numbers: numbers, __taskmate_badge_id: (b) => b.badge_id } };

test("panel: _fmtNum uses HA's format", () => {
  const { get } = loadCard("taskmate-panel.js", withHelper);
  const panel = Object.create(get("taskmate-panel").prototype);
  panel._hass = hassFor("de");
  assert.equal(panel._fmtNum(12345), "12.345");
  panel._hass = hassFor("en");
  assert.equal(panel._fmtNum(12345), "12,345");
});

test("kiosk: a child's balance is grouped the HA way", () => {
  const { get } = loadCard("taskmate-kiosk-card.js", {
    ...withHelper,
    sandbox: { CustomEvent: class {}, setInterval: () => 0, clearInterval() {} },
  });
  const card = new (get("taskmate-kiosk-card"))();
  card.setConfig({ entity: ENTITY });
  card.hass = {
    ...hassFor("de"),
    callWS: async () => ({ children: [] }),
    states: { [ENTITY]: { attributes: { children: [{ id: "k1", name: "Mia", points: 12345, chore_order: [] }], chores: [] } } },
  };
  assert.match(render(card.render()).markup, /12\.345/);
});

for (const [file, tag] of [
  ["taskmate-leaderboard-card.js", "taskmate-leaderboard-card"],
  ["taskmate-overview-card.js", "taskmate-overview-card"],
  ["taskmate-points-display-card.js", "taskmate-points-display-card"],
]) {
  test(`${tag}: points are grouped the HA way (de, designed layout)`, () => {
    const { get } = loadCard(file, withHelper);
    const card = new (get(tag))();
    card.setConfig({ entity: ENTITY, card_design: "playroom", child_id: "k1", mode: "multi" });
    card.hass = {
      ...hassFor("de"),
      states: {
        [ENTITY]: {
          state: "ok",
          attributes: {
            children: [{ id: "k1", name: "Mia", points: 12345, total_points_earned: 23456, chore_order: [] }],
            chores: [],
            todays_completions: [],
          },
        },
      },
    };
    card._loading = {};
    const { markup } = render(card.render());
    assert.match(markup, /12\.345/);
    assert.doesNotMatch(markup, /12,345/);
  });
}

// ── nothing formats a number with the browser's locale any more ──────────

test("no bare browser-locale number formatting remains in the frontend", () => {
  const BARE = /\.toLocaleString\(\)|new Intl\.NumberFormat\(\s*\)|new Intl\.NumberFormat\(\s*(undefined|\[\])/g;
  const offenders = [];
  for (const file of fs.readdirSync(WWW).filter((f) => f.endsWith(".js") && f !== "taskmate-localize.js")) {
    const src = fs.readFileSync(path.join(WWW, file), "utf8");
    for (const m of src.matchAll(BARE)) offenders.push(`${file}:${src.slice(0, m.index).split("\n").length} ${m[0]}`);
    // toFixed is fine for CSS/SVG values; a displayed one must go through the helper.
    for (const m of src.matchAll(/(tm-numeric">\$\{|average: |stars: |const kb = )[^\n]*toFixed\(/g)) {
      offenders.push(`${file}:${src.slice(0, m.index).split("\n").length} displayed toFixed`);
    }
  }
  assert.deepEqual(offenders, []);
});

// Raw numbers interpolated straight into a template showed "2867" next to a
// grouped "2.867" (#771). Point-like fields must go through the helper
// wherever they are printed as text (attribute values and CSS are exempt).
test("no point/stat field is printed into a template unformatted", () => {
  const FIELD = "(?:points|effective_points|total_points_earned|career_score|pending_points|points_awarded|cost|balance|bonus_points|max_points|ticket_cost|saved|pledged)";
  const RAW = new RegExp(`\\$\\{\\s*(?:[\\w$]+(?:\\??\\.[\\w$]+)*\\??\\.)?${FIELD}(?:\\s*(?:\\?\\?|\\|\\|)\\s*0)?\\s*\\}`, "g");
  const offenders = [];
  for (const file of fs.readdirSync(WWW).filter((f) => f.endsWith(".js") && f !== "taskmate-localize.js")) {
    const src = fs.readFileSync(path.join(WWW, file), "utf8");
    for (const m of src.matchAll(RAW)) {
      const before = src.slice(Math.max(0, m.index - 12), m.index);
      if (/(=\s*["']?|["']|:\s*)$/.test(before) && !before.endsWith('">')) continue; // attribute / CSS value
      if (src[m.index + m[0].length] === "%") continue;
      offenders.push(`${file}:${src.slice(0, m.index).split("\n").length} ${m[0]}`);
    }
    // A point field glued to text before printing ("12345 POINTS"), a
    // rounded figure printed raw, or a signed bare amount on a button
    // ("+250"): each skipped the helper in its own way.
    for (const re of [
      /\$\{\s*\(?[^{}]*\b(?:points|cost)\b\s*\+\s*['"`][^{}]*\}/g,
      /[>+−]\$\{\s*Math\.round\([^{}]*\)\s*\}/g,
      />\s*(?:[+−]|&#x2212;)\$\{\s*[A-Za-z_]\w*\s*\}/g,
      // Any signed figure, anywhere it is printed: "+${b.point_bonus}".
      /[+−]\$\{(?![^{}]*(?:__tmNum|_fmtNum|fmt\())[^{}]+\}/g,
    ]) {
      for (const m of src.matchAll(re)) {
        if (m[0].includes("__tmNum") || m[0].includes("_fmtNum")) continue;
        offenders.push(`${file}:${src.slice(0, m.index).split("\n").length} ${m[0].slice(0, 60)}`);
      }
    }
    // camelCase locals holding a point figure (earnedPoints, displayCost, …)
    for (const m of src.matchAll(/\$\{\s*[A-Za-z_.?]*[a-z](?:Points|Cost|Balance|Score|Earned)\s*\}/g)) {
      offenders.push(`${file}:${src.slice(0, m.index).split("\n").length} ${m[0]}`);
    }
  }
  assert.deepEqual(offenders, []);
});

test("negatives use the same minus as the cards (U+2212), not a hyphen", () => {
  assert.equal(fmt(hassFor("de"), -1500), "−1.500");
  assert.equal(fmt(hassFor("en"), -15), "−15");
  assert.equal(fmt(hassFor("en"), 0), "0");
});

test("balances in messages, weekly counts, calendar points and graph ticks are formatted", () => {
  const src = (f) => fs.readFileSync(path.join(WWW, f), "utf8");
  assert.doesNotMatch(src("taskmate-incentive-card.js"), /applying_to', \{[^}]*points: child\.points\b/);
  assert.doesNotMatch(src("taskmate-points-display-card.js"), /weekly_(?:pts|plus)", \{ count: (?:r\.)?weekly\b/);
  assert.match(src("taskmate-calendar-card.js"), /__tmNum\(this\.hass, this\._dayPoints\(/);
  assert.match(src("taskmate-graph-card.js"), /fillText\(__tmNum\(this\.hass, tick\)/);
});
