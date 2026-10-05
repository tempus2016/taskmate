const assert = require("node:assert/strict");
const { readFileSync, readdirSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const { loadCard, render, WWW } = require("./harness.cjs");

// Number runs in right-to-left text (#995). "3 / 1" is one unit, but inside an
// RTL paragraph the Unicode bidi algorithm lays its parts out right to left and
// it reads "1 / 3" ("3-Day Streak" likewise turns into "Day Streak-3"). The
// shared ltrNums() helper wraps each run in an invisible left-to-right isolate;
// these tests pin the helper and make sure every such template goes through it.

const LRI = String.fromCodePoint(0x2066);
const FSI = String.fromCodePoint(0x2068);
const PDI = String.fromCodePoint(0x2069);
/** What ltrNums makes of a label: the label first-strong isolated, each run LTR isolated. */
const label = (...parts) => FSI + parts.join("") + PDI;
const run = (s) => LRI + s + PDI;
const FILES = readdirSync(WWW).filter((f) => f.endsWith(".js"));

function loadDesign() {
  const window = { matchMedia: () => ({ matches: false }) };
  vm.runInNewContext(readFileSync(path.join(WWW, "taskmate-design.js"), "utf8"), {
    window,
    document: {
      documentElement: { dir: "" },
      getElementById: () => ({}),
      createElement: () => ({}),
      head: { appendChild() {} },
    },
    customElements: { get: () => undefined },
  });
  return window.__taskmate_design;
}

const META = { translations: { ar: { isRTL: true }, en: {} } };
const RTL = { language: "ar", translationMetadata: META };
const LTR = { language: "en", translationMetadata: META };

const design = loadDesign();
/** ltrNums as a card sees it once apply()/direction() has resolved `hass`. */
const ltrNums = (text, hass = RTL) => {
  design.direction(hass);
  return design.ltrNums(text);
};

test("ltrNums isolates ratios and number-word compounds", () => {
  assert.equal(ltrNums("3 / 1"), label(run("3 / 1")));
  assert.equal(ltrNums("2 / 0 joined"), label(run("2 / 0"), " joined"));
  assert.equal(ltrNums("1,200 / 5,000 chores, done"), label(run("1,200 / 5,000"), " chores, done"));
  assert.equal(ltrNums("After this pledge: 40 / 60"), label("After this pledge: ", run("40 / 60")));
  assert.equal(ltrNums("3-Day Streak"), label(run("3-Day"), " Streak"));
  assert.equal(ltrNums("12 / 30 min"), label(run("12 / 30"), " min"));
  assert.equal(ltrNums("2 of 5 done"), label("2 of 5 done"), "a label opening with a number keeps its order");
  const arabic = String.fromCodePoint(0x663) + " / " + String.fromCodePoint(0x661);
  assert.equal(ltrNums(arabic), label(run(arabic)), "Arabic-Indic digits too");
});

test("a number-word compound right after another letter or digit run splits the same way", () => {
  assert.equal(ltrNums("x12-day"), label("x1", run("2-day")));
  assert.equal(ltrNums("ab3-day"), "ab3-day");
  assert.equal(ltrNums("re-3-day"), "re-3-day");
  assert.equal(ltrNums("1 / 2 then 3-day, 4-week"), label(run("1 / 2"), " then ", run("3-day"), ", ", run("4-week")));
});

// iOS 15 / Safari < 16.4 can't compile a lookbehind: a SyntaxError in the
// design layer leaves window.__taskmate_chore_visual undefined and the child
// card blank (#1034). Keep every served file free of them.
test("no served file uses a regex lookbehind (Safari < 16.4 can't compile one)", () => {
  const offenders = [];
  for (const file of FILES) {
    for (const { n, line } of codeLines(file)) if (/\(\?<[=!]/.test(line)) offenders.push(`${file}:${n}`);
  }
  assert.deepEqual(offenders, []);
});

test("in a left-to-right page ltrNums changes nothing, so LTR renders exactly as before", () => {
  for (const s of ["3 / 1", "2 / 0 joined", "3-Day Streak", "After this pledge: 40 / 60"]) assert.equal(ltrNums(s, LTR), s);
  assert.equal(ltrNums(7, LTR), 7);
  assert.equal(ltrNums("3 / 1", RTL), label(run("3 / 1")), "and it follows the page back to RTL");
});

test("ltrNums leaves everything else alone", () => {
  for (const s of ["Step 1 of 3", "Stars", "", "every-2-days", "Streak Star", "Bonus +5"]) assert.equal(ltrNums(s), s);
  assert.equal(ltrNums(null), null);
  assert.equal(ltrNums(undefined), undefined);
  assert.equal(ltrNums(7), label("7"));
});

test("isolates are invisible: stripping them gives back the original text", () => {
  const s = "5 / 10 chores · 50% and a 3-day streak";
  assert.equal(ltrNums(s).split("").filter((c) => ![LRI, FSI, PDI].includes(c)).join(""), s);
});

// ── Every number-run template goes through the helper ────────────────────

/** Code lines only: comments can quote a ratio without rendering it. */
function codeLines(file) {
  return readFileSync(path.join(WWW, file), "utf8")
    .split("\n")
    .map((line, i) => ({ n: i + 1, line }))
    .filter(({ line }) => !/^\s*(\/\/|\*|\/\*)/.test(line));
}

const ISOLATED = /ltrNums\(|_ltrRatio\(|dir="ltr"/;

// The body of each card's _ltrRatio helper, which is where the isolate comes from.
const RATIO_HELPER = [
  "const _ltrRatio = (a, b) => {",
  "  const s = `${a} / ${b}`;",
  "  const r = _ltrNums(s);",
  "  return r === s ? html`${a} / ${b}` : r;",
  "};",
];

test('no "${a} / ${b}" template renders without an isolate', () => {
  const offenders = [];
  for (const file of FILES) {
    for (const { n, line } of codeLines(file)) {
      if (RATIO_HELPER.includes(line)) continue;
      if (/\}\s+\/\s*\$\{|\}\s*\/\s+\$\{/.test(line) && !ISOLATED.test(line)) offenders.push(`${file}:${n}: ${line.trim()}`);
    }
  }
  assert.deepEqual(offenders, [], "wrap the run in _ltrNums(...) (or <bdi dir=\"ltr\"> when it spans elements)");
});

test("messages whose placeholders form a number run are isolated where they are used", () => {
  const en = JSON.parse(readFileSync(path.join(WWW, "locales/en.json"), "utf8"));
  // Spaced ratios, "{n}-day", and visible "{x} of {y}" counts (aria-labels are
  // read aloud, not laid out, so the two that only feed one are left alone).
  const pattern = /\{\w+\}\s+\/\s*\{\w+\}|\{\w+\}\s*\/\s+\{\w+\}|\{\w+\}-\p{L}|^\{\w+\} of \{\w+\}/u;
  const ARIA_ONLY = ["panel.today_ring_label", "wishlist.progress_label"];
  const keys = Object.keys(en).filter((k) => pattern.test(en[k]) && !ARIA_ONLY.includes(k));
  for (const k of ["child.team_progress", "panel.today_streak", "kiosk.progress", "badges.count_label"]) assert.ok(keys.includes(k), k);

  const offenders = [];
  let uses = 0;
  for (const file of FILES) {
    for (const { n, line } of codeLines(file)) {
      for (const key of keys) {
        if (!line.includes(`_t("${key}"`) && !line.includes(`_t('${key}'`)) continue;
        uses += 1;
        if (!ISOLATED.test(line)) offenders.push(`${file}:${n}: ${key}`);
      }
    }
  }
  assert.ok(uses > 0);
  assert.deepEqual(offenders, []);
});

test('badge names ("3-Day Streak") go through the helper wherever a card or the panel shows them', () => {
  const read = (f) => readFileSync(path.join(WWW, f), "utf8");
  assert.match(read("taskmate-child-card.js"), /best\.name = _ltrNums\(this\._badgeName\(best\.badge\)\);/);
  assert.doesNotMatch(read("taskmate-badges-card.js"), /name">\$\{b\.name\}/);
  const panel = read("taskmate-panel.js");
  assert.equal((panel.match(/<strong>\$\{this\._esc\(this\._badgeName\(/g) || []).length, 0);
  assert.equal((panel.match(/<strong>\$\{this\._esc\(this\._ltrNums\(this\._badgeName\(/g) || []).length, 2);
});

test("each card's _ltrNums delegates to the design layer", () => {
  const def = "const _ltrNums = (s) => (window.__taskmate_design && window.__taskmate_design.ltrNums ? window.__taskmate_design.ltrNums(s) : s);";
  for (const file of FILES) {
    const src = readFileSync(path.join(WWW, file), "utf8");
    if (file === "taskmate-panel.js" || !src.includes("_ltrNums(")) continue;
    assert.ok(src.includes(def), `${file} calls _ltrNums without defining it`);
    if (src.includes("_ltrRatio(")) assert.ok(src.includes(RATIO_HELPER.join("\n")), `${file}: _ltrRatio differs`);
  }
  assert.match(readFileSync(path.join(WWW, "taskmate-panel.js"), "utf8"), /_ltrNums\(s\) \{\s*const design = window\.__taskmate_design;/);
});

// ── Rendered: the wishlist card's savings total ──────────────────────────

function wishlistMarkup(design) {
  const Card = loadCard("taskmate-wishlist-card.js", { window: { __taskmate_design: design } }).get("taskmate-wishlist-card");
  const card = new Card();
  card.setConfig({ entity: "sensor.taskmate_overview", child_id: "mia" });
  card.hass = {
    states: {
      "sensor.taskmate_overview": { state: "ok", attributes: { children: [{ id: "mia", name: "Malia", points: 50 }] } },
      "sensor.mia_wishlist": {
        state: "1",
        attributes: { wishlist_child_id: "mia", wishes: [{ id: "w1", name: "Kite", target: 80, status: "active", saved: 30, pledged: 10 }] },
      },
    },
  };
  return render(card.render()).markup;
}

test("a rendered card isolates its ratio in RTL, and renders it plain in LTR or before the design layer loads", () => {
  const base = { apply: () => "classic", styles: () => null, editorOptions: () => [] };
  design.direction(RTL);
  assert.ok(wishlistMarkup({ ...base, ltrNums: design.ltrNums }).includes(`<span class="wl-tot">${label(run("40 / 80"))}</span>`));
  assert.ok(wishlistMarkup(base).includes('<span class="wl-tot">40 / 80</span>'));
  design.direction(LTR);
  assert.ok(wishlistMarkup({ ...base, ltrNums: design.ltrNums }).includes('<span class="wl-tot">40 / 80</span>'));
});
