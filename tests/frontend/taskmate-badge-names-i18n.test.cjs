const assert = require("node:assert/strict");
const { existsSync, readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const { loadCard, render, WWW } = require("./harness.cjs");

// #771 gate: the Badges card (and the trophy cabinet) showed built-in badge
// names in English on a German or French dashboard ("1000 Points", "First
// Reward"), while the child card translated them. Every card now reads a
// badge's name through one helper, window.__taskmate_badge_name, in
// taskmate-localize.js.

const LOCALES = path.join(WWW, "locales");
const de = JSON.parse(readFileSync(path.join(LOCALES, "de.json"), "utf8"));
const fr = JSON.parse(readFileSync(path.join(LOCALES, "fr.json"), "utf8"));

/** The real localize module, with its locale files served from disk. */
async function realLocalize(langs) {
  const window = {};
  const fetch = async (url) => {
    const file = path.join(LOCALES, url.split("?")[0].replace(/^\/taskmate\/locales\//, ""));
    if (!existsSync(file)) return { ok: false, status: 404 };
    const body = readFileSync(file, "utf8");
    return { ok: true, json: async () => JSON.parse(body) };
  };
  // The module reads its cache-busting version from import.meta.url (module
  // syntax a plain script can't parse), so give it a stand-in, as the harness does.
  const source = readFileSync(path.join(WWW, "taskmate-localize.js"), "utf8")
    .replaceAll("import.meta.url", JSON.stringify("http://localhost/taskmate-localize.js?v=test"));
  vm.runInNewContext(source, {
    window, fetch, document: {}, CustomEvent: class {}, console,
  });
  for (const language of langs) await window.__taskmate_loadTranslations({ language });
  return window;
}

/** A badge's {count} as the module writes it: through the shared number helper
 *  when that is loaded (it is once fix/numbers-follow-ha-language is in), else plain. */
const count = (w, language, n) => (w.__taskmate_numbers && w.__taskmate_numbers.format
  ? w.__taskmate_numbers.format({ language, locale: { language } }, n) : String(n));

const FIRST_REWARD = { badge_id: "builtin.first_reward", name: "First Reward", icon: "mdi:gift", tier: "bronze", earned_at: "2026-11-01T10:00:00Z" };
const POINTS_1000 = { badge_id: "builtin.1000_points", name: "1000 Points", icon: "mdi:star", tier: "gold", progress_pct: 40, progress_label: "400 / 1000" };
const CUSTOM = { badge_id: "custom_abc", name: "Tidy Room Hero", icon: "mdi:broom", tier: "silver", earned_at: "2026-11-02T10:00:00Z" };

test("the helper translates built-in badges and keeps a parent's own names", async () => {
  const w = await realLocalize(["de", "fr"]);
  const name = w.__taskmate_badge_name;
  assert.equal(name({ language: "de" }, FIRST_REWARD), de["badge.name_first_reward"]);
  assert.equal(name({ language: "fr" }, POINTS_1000), fr["badge.name_1000_points"].replace("{points_name}", fr["common.points"]).replace("{count}", count(w, "fr", 1000)));
  // The panel's spelling of the id works too.
  assert.equal(name({ language: "de" }, { id: "builtin.first_chore", name: "First Chore" }), de["badge.name_first_chore"]);
  assert.equal(name({ language: "de" }, CUSTOM), "Tidy Room Hero");
  assert.equal(name({ language: "de" }, { badge_id: "builtin.not_a_badge", name: "Mystery" }), "Mystery");
  assert.equal(name({ language: "de" }, null), "");
});

test("the Badges card shows translated badge names in every design", async () => {
  const w = await realLocalize(["de"]);
  for (const design of ["classic", "playroom", "console", "cleanpro", "accessible"]) {
    const Card = loadCard("taskmate-badges-card.js", {
      editor: false,
      window: {
        __taskmate_localize: w.__taskmate_localize,
        __taskmate_badge_name: w.__taskmate_badge_name,
        __taskmate_badge_id: (b) => String(b.badge_id ?? b.id ?? ""),
        __taskmate_design: { apply: () => design, styles: () => null, ltrNums: (s) => s },
      },
    }).get("taskmate-badges-card");
    const el = new Card();
    el.hass = { language: "de", states: { "sensor.malia_badges": { state: "2", attributes: { child_name: "Malia", earned: [FIRST_REWARD, CUSTOM], available: [POINTS_1000] } } } };
    el.setConfig({ entity: "sensor.malia_badges", card_design: design });
    const { markup } = render(el.render());
    assert.ok(markup.includes(de["badge.name_first_reward"]), `${design}: first reward not translated`);
    assert.ok(markup.includes(de["badge.name_1000_points"].replace("{points_name}", de["common.points"]).replace("{count}", count(w, "de", 1000))), `${design}: 1000 points not translated`);
    assert.ok(markup.includes("Tidy Room Hero"), `${design}: custom badge name lost`);
    assert.ok(!markup.includes(">First Reward<") && !markup.includes(">1000 Points<"), `${design}: English badge name shown`);
    const day = new Date(FIRST_REWARD.earned_at).toLocaleDateString("de", { day: "numeric", month: "short" });
    assert.ok(markup.includes(day), `${design}: earned date not in German (${day})`);
  }
});

test("every card that shows a badge name goes through the shared helper", () => {
  const read = (f) => readFileSync(path.join(WWW, f), "utf8");
  const ONE = 'return window.__taskmate_badge_name ? window.__taskmate_badge_name(this.hass, b) : (b && b.name) || "";';
  for (const f of ["taskmate-badges-card.js", "taskmate-child-card.js", "taskmate-kiosk-card.js", "taskmate-trophy-cabinet-card.js"]) {
    assert.ok(read(f).includes(ONE), `${f} has no _badgeName delegating to the helper`);
  }
  assert.doesNotMatch(read("taskmate-badges-card.js"), /_ltrNums\(b\.name\)|latestEarned\.name/);
  assert.match(read("taskmate-trophy-cabinet-card.js"), /name: this\._badgeName\(b\)/);
});

test("numbers in built-in badge names and descriptions are a {count}, never baked in", () => {
  // "1000 Punkte" read as a bare four-digit run. The number is now formatted
  // at render time (#771) — HA's number format, or the language's grouping —
  // so no badge.* string may carry its own copy of it.
  const { readdirSync } = require("node:fs");
  let checked = 0;
  for (const f of readdirSync(LOCALES).filter((n) => n.endsWith(".json"))) {
    const lang = f.slice(0, -5);
    const d = JSON.parse(readFileSync(path.join(LOCALES, f), "utf8"));
    for (const [k, v] of Object.entries(d)) {
      if (!/^badge\.(name|desc)_\d+_/.test(k)) continue;
      assert.match(v, /\{count\}/, `${lang} ${k}: "${v}"`);
      assert.doesNotMatch(v, /\d/, `${lang} ${k}: a number is still written into "${v}"`);
      checked += 1;
    }
  }
  assert.equal(checked, 24 * 11, "24 numbered badge strings × 11 languages");
});

test("the points badges use the family's own name for points", async () => {
  const w = await realLocalize(["de", "pl", "fr"]);
  // The shared number helper groups the way the language does (#771).
  w.__taskmate_numbers = { format: (h, n) => new Intl.NumberFormat(h.language).format(n) };
  const name = w.__taskmate_badge_name;
  const hass = (language) => ({ language, states: { "sensor.taskmate_overview": { attributes: { points_name: "Sterne" } } } });
  assert.equal(name(hass("de"), POINTS_1000), "1.000 Sterne");
  assert.equal(name(hass("pl"), POINTS_1000), "Sterne: 1000");
  // An explicit name wins; with none configured anywhere, the translated word.
  assert.equal(name(hass("de"), POINTS_1000, "Taler"), "1.000 Taler");
  assert.equal(name({ language: "de", states: {} }, POINTS_1000), `1.000 ${de["common.points"]}`);
  // A renamed overview is found by its companion map.
  const renamed = { language: "fr", states: { "sensor.kitchen_taskmate_overview": { attributes: { companion_entities: {}, points_name: "Étoiles" } } } };
  assert.equal(name(renamed, { badge_id: "builtin.5000_points", name: "5000 Points" }), `${new Intl.NumberFormat("fr").format(5000)} Étoiles`);
  for (const f of require("node:fs").readdirSync(LOCALES).filter((n) => n.endsWith(".json"))) {
    const d = JSON.parse(readFileSync(path.join(LOCALES, f), "utf8"));
    for (const n of [100, 500, 1000, 5000]) {
      for (const kind of ["name", "desc"]) assert.match(d[`badge.${kind}_${n}_points`], /\{points_name\}/, `${f} badge.${kind}_${n}_points`);
    }
  }
});

test("designed card header pills keep the translation's own casing", () => {
  // text-transform: capitalize turned "8 von 16 verdient" into "8 Von 16 Verdient".
  const kit = readFileSync(path.join(WWW, "taskmate-design.js"), "utf8");
  const rule = kit.match(/\.tmd-hd \.pill\{[^}]*\}/)[0];
  assert.doesNotMatch(rule, /text-transform/);
});

// The number in a built-in badge's name is written the HA way (#771): it is a
// {count} formatted at render time, not baked into the translation, so HA's
// number format setting (and the language's grouping) applies.
test("a points badge's number follows HA's number format", async () => {
  const w = await realLocalize(["de"]);
  w.__taskmate_numbers = { format: (_h, n) => `<${n}>` };
  assert.equal(w.__taskmate_badge_name({ language: "de" }, POINTS_1000), de["badge.name_1000_points"].replace("{points_name}", de["common.points"]).replace("{count}", "<1000>"));
  for (const lang of ["de", "fr", "en"]) {
    const loc = JSON.parse(readFileSync(path.join(LOCALES, `${lang}.json`), "utf8"));
    for (const [k, v] of Object.entries(loc)) {
      if (/^badge\.(name|desc)_\d+_/.test(k)) assert.match(v, /\{count\}/, `${lang} ${k} still bakes its number in`);
    }
  }
});
