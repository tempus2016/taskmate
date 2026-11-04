// The Lovelace card picker in the user's language (v7.7.1 recheck).
//
// Every card's window.customCards entry had a hard-coded English name and
// description, and the `*.card_name` / `*.card_description` locale keys were
// never read. The entries now use getters (HA reads them each time the picker
// opens) that ask taskmate-localize.js for the current language.

const assert = require("node:assert/strict");
const { test } = require("node:test");
const { existsSync, readFileSync, readdirSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const { loadCard, WWW } = require("./harness.cjs");

const EN = JSON.parse(readFileSync(path.join(WWW, "locales/en.json"), "utf8"));
const DE = JSON.parse(readFileSync(path.join(WWW, "locales/de.json"), "utf8"));

const CARD_FILES = readdirSync(WWW).filter(f => /^taskmate-.*-card\.js$/.test(f) && f !== "taskmate-incentive-card.js"
  && readFileSync(path.join(WWW, f), "utf8").includes("window.customCards.push("));

function entriesOf(filename, transform) {
  const calls = [];
  const customCards = [];
  loadCard(filename, {
    topLevelAwait: true,
    transform,
    window: {
      customCards,
      __taskmate_suggest: () => ({}),
      __taskmate_picker_text: (key, en) => { calls.push([key, en]); return `T:${key}`; },
    },
  });
  return { customCards, calls };
}

test("every card registers a picker entry", () => {
  assert.ok(CARD_FILES.length >= 31, `${CARD_FILES.length} card files`);
});

for (const file of CARD_FILES) {
  test(`${file}: the picker name and description are translated getters`, () => {
    const { customCards, calls } = entriesOf(file);
    assert.equal(customCards.length, 1, "one picker entry");
    const entry = customCards[0];
    for (const field of ["name", "description"]) {
      assert.equal(typeof Object.getOwnPropertyDescriptor(entry, field).get, "function", `${field} is a getter`);
    }
    const name = entry.name; const description = entry.description;
    const [[nameKey, nameEn], [descKey, descEn]] = calls;
    assert.equal(name, `T:${nameKey}`);
    assert.equal(description, `T:${descKey}`);
    assert.match(nameKey, /^[a-z_]+\.card_name$/);
    assert.equal(descKey, nameKey.replace(".card_name", ".card_description"));
    assert.ok(EN[nameKey] && EN[descKey], `${nameKey} / ${descKey} exist in en.json`);
    assert.ok(DE[nameKey] && DE[descKey], `${nameKey} / ${descKey} exist in de.json`);
    assert.ok(nameEn.startsWith("TaskMate") && descEn.length > 10, "an English fallback is kept");
  });
}

test("bonuses and penalties: the shared incentive entry uses the card's own keys", () => {
  for (const i18n of ["bonuses", "penalties"]) {
    const tag = `taskmate-${i18n}-card`;
    const { customCards } = entriesOf("taskmate-incentive-card.js", (src) =>
      src.replace("export function createIncentiveCard", "function createIncentiveCard")
      + `\ncreateIncentiveCard({ tag: "${tag}", kind: "bonus", idKey: "bonus_id", i18n: "${i18n}", attr: "${i18n}",`
      + ` icon: "mdi:star", headerIcon: "mdi:star", applyIcon: "mdi:plus", sign: "+", dpts: (n) => "+" + n,`
      + ` accent: "#2e7d32", designHd: "#2e7d32", designIcons: {}, cardName: "English name", cardDesc: "English desc", bannerName: "X", bannerColor: "#000" });`);
    assert.equal(customCards[0].name, `T:${i18n}.card_name`);
    assert.equal(customCards[0].description, `T:${i18n}.card_description`);
    assert.ok(EN[`${i18n}.card_name`] && DE[`${i18n}.card_description`]);
  }
});

// The real helper in taskmate-localize.js: the signed-in user's language,
// English when there is no hass yet or the key is missing.
async function localizeModule(hass) {
  const locales = { de: DE, "en-GB": JSON.parse(readFileSync(path.join(WWW, "locales/en-GB.json"), "utf8")) };
  const window = {};
  const sandbox = {
    window,
    document: { querySelector: (sel) => (sel === "home-assistant" && hass ? { hass } : null) },
    // Serve whatever the loader asks for (a whole-language file or a per-screen
    // bundle such as locales/de/cards.json) straight from the shipped files.
    fetch: async (url) => {
      const rel = String(url).split("?")[0].replace(/^.*?\/locales\//, "locales/");
      const m = rel.match(/^locales\/([A-Za-z-]+)\.json$/);
      if (m) return locales[m[1]] ? { ok: true, json: async () => locales[m[1]] } : { ok: false, status: 404 };
      const file = path.join(WWW, rel);
      if (!rel.startsWith("locales/") || !existsSync(file)) return { ok: false, status: 404 };
      const body = readFileSync(file, "utf8");
      return { ok: true, json: async () => JSON.parse(body) };
    },
    setTimeout, console,
  };
  // The module reads its cache-busting version from import.meta.url (module
  // syntax a plain script can't parse), so give it a stand-in, as the harness does.
  const source = readFileSync(path.join(WWW, "taskmate-localize.js"), "utf8")
    .replaceAll("import.meta.url", JSON.stringify("http://localhost/taskmate-localize.js?v=test"));
  vm.runInNewContext(source, sandbox);
  if (hass) await window.__taskmate_loadTranslations(hass);
  return window;
}

test("the picker helper answers in the user's language, else English", async () => {
  const de = await localizeModule({ language: "de" });
  assert.equal(de.__taskmate_picker_text("activity.card_name", "TaskMate Activity Feed"), DE["activity.card_name"]);
  assert.equal(de.__taskmate_picker_text("kiosk.card_description", "x"), DE["kiosk.card_description"]);
  assert.equal(de.__taskmate_picker_text("nope.card_name", "Fallback"), "Fallback");

  const none = await localizeModule(null);
  assert.equal(none.__taskmate_picker_text("activity.card_name", "TaskMate Activity Feed"), "TaskMate Activity Feed");
});
