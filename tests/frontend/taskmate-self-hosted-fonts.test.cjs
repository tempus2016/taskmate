const assert = require("node:assert/strict");
const { readFileSync, readdirSync, existsSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const { WWW } = require("./harness.cjs");

// The card designs' typefaces ship inside the integration and load from the
// /taskmate/ static path, so a dashboard view sends nothing to a font CDN and
// the cards look the same with no internet. Every face the design tokens name
// must be served from www/fonts/, with its licence beside it.

const SOURCE = readFileSync(path.join(WWW, "taskmate-design.js"), "utf8");
const FONTS = path.join(WWW, "fonts");
const FAMILIES = ["Baloo 2", "Nunito", "Space Grotesk", "Inter", "JetBrains Mono", "Manrope", "Atkinson Hyperlegible"];
const slug = (family) => family.toLowerCase().replace(/ /g, "-");

/** Run the design layer and capture the stylesheet it adds to the document head. */
function injectedFontCss() {
  const added = [];
  const window = { matchMedia: () => ({ matches: false }) };
  vm.runInNewContext(SOURCE, {
    window,
    document: {
      documentElement: { getAttribute: () => "" },
      getElementById: () => null,
      createElement: () => ({}),
      head: { appendChild: (el) => added.push(el) },
    },
    customElements: { get: () => undefined },
  });
  const fonts = added.find((el) => el.id === "taskmate-design-fonts");
  assert.ok(fonts, "the design layer must add a #taskmate-design-fonts stylesheet to the head");
  return fonts.textContent;
}

function fontFaces(cssText) {
  return [...cssText.matchAll(/@font-face\s*\{([^}]*)\}/g)].map((m) => {
    const body = m[1];
    const get = (prop) => (body.match(new RegExp(`${prop}\\s*:\\s*([^;]+);`)) || [])[1]?.trim();
    return { family: get("font-family")?.replace(/^["']|["']$/g, ""), weight: get("font-weight"), display: get("font-display"), range: get("unicode-range"), src: get("src") };
  });
}

test("the design layer never reaches out to a font CDN", () => {
  assert.doesNotMatch(SOURCE, /googleapis|gstatic|@import\s+url\(\s*['"]?https?:/i);
});

test("every design typeface is an @font-face served from /taskmate/fonts/", () => {
  const faces = fontFaces(injectedFontCss());
  assert.ok(faces.length >= FAMILIES.length, `expected at least ${FAMILIES.length} @font-face rules, found ${faces.length}`);
  for (const family of FAMILIES) {
    const mine = faces.filter((f) => f.family === family);
    assert.ok(mine.length > 0, `${family} has no @font-face`);
    for (const face of mine) {
      assert.equal(face.display, "swap", `${family}: font-display must be swap so text shows before the file lands`);
      assert.ok(face.range, `${family}: every subset carries a unicode-range so only the needed file is fetched`);
      const urls = [...face.src.matchAll(/url\(\s*['"]?([^'")]+)['"]?\s*\)/g)].map((m) => m[1]);
      assert.ok(urls.length > 0, `${family}: no url() in src`);
      for (const url of urls) {
        assert.match(url, /^\/taskmate\/fonts\/[a-z0-9-]+\.woff2$/, `${family}: ${url} is not a same-origin woff2 under /taskmate/fonts/`);
        const file = path.join(FONTS, path.basename(url));
        assert.ok(existsSync(file), `${family}: ${url} is referenced but ${file} is not shipped`);
        assert.equal(readFileSync(file).subarray(0, 4).toString("latin1"), "wOF2", `${file} is not a WOFF2 file`);
      }
    }
  }
});

test("every shipped font file is used and every family ships its licence", () => {
  const faces = fontFaces(injectedFontCss());
  const referenced = new Set(faces.flatMap((f) => [...f.src.matchAll(/\/taskmate\/fonts\/([a-z0-9-]+\.woff2)/g)].map((m) => m[1])));
  const shipped = readdirSync(FONTS);
  for (const name of shipped.filter((n) => n.endsWith(".woff2"))) {
    assert.ok(referenced.has(name), `${name} is shipped but no @font-face uses it`);
  }
  for (const family of FAMILIES) {
    const licence = `${slug(family)}-OFL.txt`;
    assert.ok(shipped.includes(licence), `${family}: ${licence} must ship beside the font files`);
    assert.match(readFileSync(path.join(FONTS, licence), "utf8"), /SIL OPEN FONT LICENSE/i);
  }
});
