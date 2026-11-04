"use strict";
// Dates and times follow Home Assistant's language and time format (#771).
//
// The cards and the panel formatted dates with the browser's language
// (`toLocaleDateString(undefined | [])`), so a German HA on an English
// browser greeted "Tuesday, 3 November" and badges read "Verdient am Aug 18".
// Every display call now goes through one helper in taskmate-localize.js,
// window.__taskmate_dates.args(hass, opts, kind).

const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");

const { loadCard, render, WWW } = require("./harness.cjs");

// The real helper, evaluated the way the browser does (it also pre-loads the
// fallback locale, which needs a fetch that simply fails here).
const helper = loadCard("taskmate-localize.js", {
  sandbox: { fetch: () => Promise.reject(new Error("offline")) },
}).window.__taskmate_dates;
// Absent on main: every test below then fails on its own, not the whole file.
const args = helper ? helper.args : () => { throw new Error("window.__taskmate_dates is missing"); };

const hassFor = (language, extra = {}) => ({
  language,
  locale: { language, time_format: "language", date_format: "language", time_zone: "local", ...extra },
  config: { time_zone: "Pacific/Auckland" },
});
const AUG18 = new Date(2026, 7, 18, 12);
const EVENING = new Date(2026, 10, 3, 20, 5);

// ── the helper ────────────────────────────────────────────────────────────

test("helper: the language is HA's, not the browser's", () => {
  assert.equal(AUG18.toLocaleDateString(...args(hassFor("de"), { day: "numeric", month: "short" })), "18. Aug.");
  assert.equal(AUG18.toLocaleDateString(...args(hassFor("en-GB"), { day: "numeric", month: "short" })), "18 Aug");
  assert.equal(AUG18.toLocaleDateString(...args(hassFor("en"), { day: "numeric", month: "short" })), "Aug 18");
});

test("helper: hass.language is the fallback when hass.locale is missing", () => {
  assert.equal(args({ language: "fr" }, { weekday: "long" })[0], "fr");
});

test("helper: HA's pt is European Portuguese", () => {
  assert.equal(args(hassFor("pt"))[0], "pt-PT");
  assert.equal(args(hassFor("pt-BR"))[0], "pt-BR");
});

test("helper: time_format 12 / 24 forces the clock for times only", () => {
  const t = { hour: "2-digit", minute: "2-digit" };
  assert.match(EVENING.toLocaleTimeString(...args(hassFor("de", { time_format: "12" }), t, "time")), /^8:05\s?(PM|pm|nachm\.)$/i);
  assert.equal(EVENING.toLocaleTimeString(...args(hassFor("en", { time_format: "24" }), t, "time")), "20:05");
  assert.equal(EVENING.toLocaleTimeString(...args(hassFor("en"), t, "time")), "8:05 PM", "language keeps en's own 12-hour clock, without a leading zero");
  // (JSON: the helper's objects come from another vm context.)
  assert.equal(JSON.stringify(args(hassFor("de", { time_format: "24" }), { weekday: "long" })), '["de",{"weekday":"long"}]', "no clock on a date");
});

test("helper: system formats use the browser's locale for that part only", () => {
  assert.equal(args(hassFor("de", { time_format: "system" }), { hour: "2-digit" })[0], undefined);
  assert.equal(args(hassFor("de", { time_format: "system" }), { weekday: "long" })[0], "de");
  assert.equal(args(hassFor("de", { date_format: "system" }), { weekday: "long" })[0], undefined);
  assert.equal(args(hassFor("de", { date_format: "system" }), { hour: "2-digit" }, "time")[0], "de");
});

test("helper: time_zone server shows times in HA's zone, never overriding the caller's", () => {
  assert.equal(args(hassFor("en", { time_zone: "server" }), { hour: "2-digit" })[1].timeZone, "Pacific/Auckland");
  assert.equal(args(hassFor("en", { time_zone: "server" }), { hour: "2-digit", timeZone: "UTC" })[1].timeZone, "UTC");
  // A local-midnight date in another zone can be the day before: dates keep theirs.
  assert.equal(args(hassFor("en", { time_zone: "server" }), { weekday: "long" })[1].timeZone, undefined);
});

test("helper: a malformed language tag falls back to the browser instead of throwing", () => {
  assert.equal(args(hassFor("not a tag"), { weekday: "long" })[0], undefined);
});

// ── the cards and the panel use it ────────────────────────────────────────

const withHelper = { window: { __taskmate_dates: helper, __taskmate_badge_id: (b) => b.badge_id } };

test("badges card: the earned date is in HA's language", () => {
  const { get } = loadCard("taskmate-badges-card.js", withHelper);
  const card = new (get("taskmate-badges-card"))();
  card.hass = hassFor("de");
  assert.equal(card._formatDate("2026-08-18T12:00:00"), "18. Aug.");
  card.hass = hassFor("en-GB");
  assert.equal(card._formatDate("2026-08-18T12:00:00"), "18 Aug");
});

test("panel Today: the date line is built through the helper, in HA's language", () => {
  const src = fs.readFileSync(path.join(WWW, "taskmate-panel.js"), "utf8");
  assert.match(src, /const dateText = new Date\(\)\.toLocaleDateString\(\.\.\.__tmDateArgs\(this\._hass, \{ weekday: "long", day: "numeric", month: "long" \}, "now"\)\)/);
  const opts = { weekday: "long", day: "numeric", month: "long" };
  assert.equal(EVENING.toLocaleDateString(...args(hassFor("de"), opts)), "Dienstag, 3. November");
  assert.equal(EVENING.toLocaleDateString(...args(hassFor("en-GB"), opts)), "Tuesday 3 November");
  assert.equal(EVENING.toLocaleDateString(...args(hassFor("en"), opts)), "Tuesday, November 3");
});

test("kiosk: the clock follows HA's 12/24-hour setting", () => {
  const { get } = loadCard("taskmate-kiosk-card.js", {
    ...withHelper,
    sandbox: { CustomEvent: class {}, setInterval: () => 0, clearInterval() {} },
  });
  const card = new (get("taskmate-kiosk-card"))();
  card.setConfig({ entity: "sensor.taskmate_overview" });
  card._now = EVENING;
  card.hass = { ...hassFor("en-GB", { time_format: "12" }), states: { "sensor.taskmate_overview": { attributes: { children: [] } } } };
  const twelve = render(card._renderAmbient({ children: [] })).markup;
  assert.match(twelve, /\b8:05\s?pm/i);
  assert.doesNotMatch(twelve, /08:05/);
  card.hass = { ...hassFor("en", { time_format: "24" }), states: card.hass.states };
  assert.match(render(card._renderAmbient({ children: [] })).markup, /20:05/);
});

// ── nothing formats a date with the browser's language any more ──────────

const DISPLAY_CALL = /\.(toLocaleDateString|toLocaleTimeString)\(([^)]*)\)|\.toLocaleString\((\[\]|undefined)|Date\([^()]*\)\.toLocaleString\(\)|new Intl\.DateTimeFormat\((?!["']en-(CA|US)["'])(?!\.\.\.__tmDateArgs)(?!\))/g;

test("every display date in the panel, cards and editors goes through the helper", () => {
  const offenders = [];
  for (const file of fs.readdirSync(WWW).filter((f) => f.endsWith(".js") && f !== "taskmate-localize.js")) {
    const src = fs.readFileSync(path.join(WWW, file), "utf8");
    for (const m of src.matchAll(DISPLAY_CALL)) {
      const call = m[0];
      // Machine keys (ISO days, English weekday names) are deliberately fixed.
      if (/\(["']en-(CA|US)["']/.test(call)) continue;
      if (call.includes("...__tmDateArgs(")) continue;
      offenders.push(`${file}:${src.slice(0, m.index).split("\n").length} ${call.slice(0, 60)}`);
    }
  }
  assert.deepEqual(offenders, []);
});

// ── wall-clock times ("Available at 17:00") and the greeting's hour ───────

const clock = helper && helper.clock ? helper.clock : () => { throw new Error("clock() is missing"); };
const hourNow = helper && helper.hourNow ? helper.hourNow : () => { throw new Error("hourNow() is missing"); };

test("clock: a stored H:MM follows HA's time format", () => {
  assert.equal(clock(hassFor("en-GB"), "17:00"), "17:00");
  assert.equal(clock(hassFor("de"), "7:05"), "07:05");
  assert.equal(clock(hassFor("en"), "17:00"), "5:00 PM", "en's own clock is 12-hour, no leading zero");
  assert.equal(clock(hassFor("en", { time_format: "24" }), "17:00"), "17:00");
  assert.match(clock(hassFor("de", { time_format: "12" }), "17:00"), /^5:00\s?(PM|pm|nachm\.)$/i);
  assert.equal(clock(hassFor("en"), "not a time"), "not a time");
  assert.equal(clock(hassFor("en"), null), "");
});

test("hourNow: the greeting's hour is HA's when HA shows server time", () => {
  const at = new Date(Date.UTC(2026, 10, 4, 23, 30));  // 12:30 next day in Auckland
  assert.equal(hourNow(hassFor("en", { time_zone: "server" }), at), 12);
  assert.equal(hourNow(hassFor("en", { time_zone: "local" }), at), at.getHours());
});

test("child card and kiosk print stored times through the clock helper", () => {
  for (const file of ["taskmate-child-card.js", "taskmate-kiosk-card.js"]) {
    const src = fs.readFileSync(path.join(WWW, file), "utf8");
    assert.doesNotMatch(src, /\{ time: (e\.opens|e\.closes|row\.setTime\.entry\.opens|chore\._setTime\.start|`\$\{String)/, file);
    assert.doesNotMatch(src, /\$\{(?:e|entry|row\.setTime\.entry)\.time\.name \|\| (?:e|entry|row\.setTime\.entry)\.opens\}/, file);
  }
  const panel = fs.readFileSync(path.join(WWW, "taskmate-panel.js"), "utf8");
  assert.doesNotMatch(panel, /const hour = new Date\(\)\.getHours\(\);/);
});

test("helper: today/now displays follow HA's server zone; stored dates don't shift", () => {
  const server = hassFor("en-GB", { time_zone: "server" });  // server zone: Pacific/Auckland
  assert.equal(args(server, { weekday: "long" }, "now")[1].timeZone, "Pacific/Auckland");
  assert.equal(args(server, { weekday: "long" })[1].timeZone, undefined, "a stored date keeps its own day");
  assert.equal(args(hassFor("en-GB"), { weekday: "long" }, "now")[1].timeZone, undefined, "local setting: the browser's day");
  // 23:30 UTC on the 4th is already the 5th in Auckland.
  const at = new Date(Date.UTC(2026, 10, 4, 23, 30));
  assert.equal(at.toLocaleDateString(...args(server, { day: "numeric" }, "now")), "5");
});

test("panel Today, kiosk and the tomorrow label are 'now' displays", () => {
  const panel = fs.readFileSync(path.join(WWW, "taskmate-panel.js"), "utf8");
  assert.match(panel, /const dateText = [^\n]*"now"\)\);/);
  const kiosk = fs.readFileSync(path.join(WWW, "taskmate-kiosk-card.js"), "utf8");
  assert.equal((kiosk.match(/this\._now\.toLocaleDateString\([^\n]*"now"\)\);/g) || []).length, 2);
});
