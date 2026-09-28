const assert = require("node:assert/strict");
const { readFileSync, readdirSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const { WWW } = require("./harness.cjs");

// Right-to-left support (#979). The cards and the panel lay out with logical
// CSS (inline-start / inline-end), so a physical left/right rule would stay put
// when HA switches to Arabic, Hebrew, Persian or Urdu.
//
// A line that genuinely has to stay physical carries an inline marker,
// `/* rtl-ok: <why> */`, next to the rule — e.g. `left: 50%` paired with
// translate(-50%) to centre something, which is symmetric either way.

const FILES = readdirSync(WWW).filter((f) => f.endsWith(".js"));

// Physical properties that aren't CSS at all, so can't carry a CSS comment.
const ALLOWLIST = [
  // Canvas plot padding in the graph card: canvas coordinates are physical, and
  // the time axis deliberately reads left to right in every language.
  { file: "taskmate-graph-card.js", text: "const PAD = { top: 16, right: 16, bottom: 28, left: 36 };" },
];

const PHYSICAL = [
  /(?<![-\w])(?:margin|padding)-(?:left|right)\s*:/,
  /(?<![-\w])border-(?:left|right)(?:-\w+)?\s*:/,
  /(?<![-\w])border-(?:top|bottom)-(?:left|right)-radius\s*:/,
  /(?<![-\w.$])(?:left|right)\s*:\s*[-\w.%(${]/,
  /text-align\s*:\s*(?:left|right)\b/,
  /(?<![-\w])float\s*:\s*(?:left|right)\b/,
  /(?<![-\w])clear\s*:\s*(?:left|right)\b/,
];

const VALUE = String.raw`(?:calc\([^)]*\)|var\([^)]*\)|[-\w.%]+)`;
// Four-value shorthands name the sides top/right/bottom/left, so a rule whose
// right and left differ is physical in disguise.
const SHORTHAND = new RegExp(
  String.raw`(?<![-\w])(margin|padding|inset|border-width|border-radius)\s*:\s*(${VALUE})\s+(${VALUE})\s+(${VALUE})\s+(${VALUE})\s*(?=[;"}\n\x60!])`,
  "g",
);

/** Source lines worth checking, minus the console.info version banners. */
function cssLines(file) {
  const out = [];
  let banner = false;
  readFileSync(path.join(WWW, file), "utf8").split("\n").forEach((line, i) => {
    // The "%c TASKMATE … CARD" banner styles the browser console, not the page.
    if (line.includes("console.info(")) banner = true;
    if (!banner) out.push({ n: i + 1, line });
    if (banner && line.trim().startsWith(");")) banner = false;
  });
  return out;
}

function allowed(file, line) {
  const marker = line.match(/\/\*\s*rtl-ok:\s*([^*]*?)\s*\*\//);
  if (marker) return marker[1].length > 0;
  return ALLOWLIST.some((a) => a.file === file && line.includes(a.text));
}

test("no physical left/right CSS is left in the cards, the panel or the design layer", () => {
  const offenders = [];
  for (const file of FILES) {
    for (const { n, line } of cssLines(file)) {
      if (allowed(file, line)) continue;
      if (PHYSICAL.some((re) => re.test(line))) offenders.push(`${file}:${n}: ${line.trim()}`);
      for (const m of line.matchAll(SHORTHAND)) {
        const [, prop, top, right, bottom, left] = m;
        const physical = prop === "border-radius" ? top !== right || bottom !== left : right !== left;
        if (physical) offenders.push(`${file}:${n}: ${m[0]}`);
      }
    }
  }
  assert.deepEqual(offenders, [], "use inline-start/inline-end (or mark the line /* rtl-ok: why */)");
});

test("every rtl-ok marker says why", () => {
  for (const file of FILES) {
    for (const { n, line } of cssLines(file)) {
      if (/rtl-ok/.test(line)) assert.match(line, /\/\*\s*rtl-ok:\s*\S[^*]*\*\//, `${file}:${n}`);
    }
  }
});

test("the allowlist has no stale entries", () => {
  for (const { file, text } of ALLOWLIST) {
    assert.ok(readFileSync(path.join(WWW, file), "utf8").includes(text), `${file}: ${text}`);
  }
});

test("icons that point along the reading direction turn round in RTL", () => {
  const directional = /<ha-icon\b[^>]*icon="mdi:(?:chevron-left|chevron-right|chevron-double-left|chevron-double-right|undo-variant|backspace-outline|send)"[^>]*>/g;
  const missing = [];
  for (const file of FILES) {
    const src = readFileSync(path.join(WWW, file), "utf8");
    for (const tag of src.match(directional) || []) {
      if (!tag.includes("tm-rtl-flip")) missing.push(`${file}: ${tag}`);
    }
  }
  assert.deepEqual(missing, []);
});

test("the design layer and the panel both define the flip rule", () => {
  assert.match(readFileSync(path.join(WWW, "taskmate-design.js"), "utf8"), /:host\(\[dir="rtl"\]\) \.tm-rtl-flip/);
  assert.match(readFileSync(path.join(WWW, "taskmate-panel.js"), "utf8"), /\[dir="rtl"\] \.tm-rtl-flip \{ transform: scaleX\(-1\); \}/);
});

// ── The shared direction helper ──────────────────────────────────────────

function loadDesign(rootDir = "") {
  const window = { matchMedia: () => ({ matches: false }) };
  const sandbox = {
    window,
    document: {
      documentElement: { dir: rootDir },
      getElementById: () => ({}),
      createElement: () => ({}),
      head: { appendChild() {} },
    },
    customElements: { get: () => undefined },
  };
  vm.runInNewContext(readFileSync(path.join(WWW, "taskmate-design.js"), "utf8"), sandbox);
  return window.__taskmate_design;
}

function host() {
  const attrs = {};
  return {
    attrs,
    setAttribute: (k, v) => { attrs[k] = v; },
    toggleAttribute: (k, on) => { if (on) attrs[k] = ""; else delete attrs[k]; },
  };
}

const META = { translations: { ar: { isRTL: true }, he: { isRTL: true }, en: {}, "en-GB": { isRTL: false } } };

test("direction follows HA's translation metadata", () => {
  const d = loadDesign();
  assert.equal(d.direction({ language: "ar", translationMetadata: META }), "rtl");
  assert.equal(d.direction({ language: "he", translationMetadata: META }), "rtl");
  assert.equal(d.direction({ language: "en", translationMetadata: META }), "ltr");
  assert.equal(d.direction({ language: "en-GB", translationMetadata: META }), "ltr");
});

test("with no metadata for the language, direction follows the page HA laid out", () => {
  assert.equal(loadDesign("rtl").direction({ language: "xx", translationMetadata: META }), "rtl");
  assert.equal(loadDesign("").direction({ language: "xx", translationMetadata: META }), "ltr");
  assert.equal(loadDesign("rtl").direction(undefined), "rtl");
  assert.equal(loadDesign().direction(null), "ltr");
});

test("apply() stamps dir on the card host alongside the design", () => {
  const d = loadDesign();
  const rtl = host();
  assert.equal(d.apply(rtl, { language: "ar", translationMetadata: META, states: {} }, { card_design: "playroom" }), "playroom");
  assert.equal(rtl.attrs.dir, "rtl");
  assert.equal(rtl.attrs["data-tm-design"], "playroom");

  const ltr = host();
  d.apply(ltr, { language: "en", translationMetadata: META, states: {} }, {});
  assert.equal(ltr.attrs.dir, "ltr");
  assert.equal(ltr.attrs["data-tm-design"], "classic");
});
