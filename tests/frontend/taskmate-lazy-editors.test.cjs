const assert = require("node:assert/strict");
const { readdirSync, readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { loadCard, render, template, WWW } = require("./harness.cjs");
const vm = require("node:vm");

// Every card's visual editor lives in www/editors/ and is imported only when
// someone opens the card editor, so a dashboard never downloads or parses the
// editors. These tests pin that split: the card files carry no editor class,
// getConfigElement() pulls in the right module with the card's ?v= version,
// and the few constants an editor shares with its card stay identical.

const EDITORS = path.join(WWW, "editors");
const editorFiles = readdirSync(EDITORS).filter((f) => f.endsWith("-editor.js")).sort();
const cardOf = (editorFile) => editorFile.replace(/-editor\.js$/, ".js");
const read = (rel) => readFileSync(path.join(WWW, rel), "utf8");

// Wrappers whose editor comes from a shared base.
const SHARED = { "taskmate-incentive-card-editor.js": ["taskmate-bonuses-card.js", "taskmate-penalties-card.js"] };

test("there is one editor module per card editor", () => {
  assert.equal(editorFiles.length, 30);
  for (const f of editorFiles) assert.ok(readdirSync(WWW).includes(cardOf(f)), `${f} has no card ${cardOf(f)}`);
});

test("no card file still carries an editor class or defines an editor element", () => {
  const cards = readdirSync(WWW).filter((f) => /^taskmate-.*-card\.js$/.test(f));
  for (const f of cards) {
    const src = read(f);
    assert.doesNotMatch(src, /class \w*Editor extends/, `${f} still defines an editor class`);
    assert.doesNotMatch(src, /customElements\.define\([^)]*-editor/, `${f} still defines an editor element`);
  }
});

test("each editor module defines its element once, guarded against a second copy", () => {
  for (const f of editorFiles) {
    const src = read(`editors/${f}`);
    if (SHARED[f]) {
      assert.match(src, /if \(customElements\.get\(tag\)\) return;/);
      continue;
    }
    const tag = f.replace(/\.js$/, "");
    assert.ok(src.includes(`if (!customElements.get("${tag}")) {`), `${f} define is not guarded`);
    assert.ok(src.includes(`customElements.define("${tag}", `), `${f} does not define <${tag}>`);
  }
});

for (const f of editorFiles.filter((e) => !SHARED[e])) {
  const card = cardOf(f);
  const tag = f.replace(/\.js$/, "");
  test(`${card}: getConfigElement() loads ${f} with the card's version and the editor strings`, async () => {
    const src = read(card);
    assert.ok(
      src.includes(`import(\`./editors/${f}\${new URL(import.meta.url).search}\`)`),
      "the editor import must be relative to the card and carry its ?v=",
    );
    const bundles = [];
    const loaded = loadCard(card, {
      editor: false,
      topLevelAwait: card === "taskmate-sticker-chart-card.js",
      window: { __taskmate_loadTranslations: (_hass, b) => (bundles.push([...b]), Promise.resolve()) },
    });
    assert.equal(loaded.get(tag), undefined, "the editor must not be defined until it is asked for");
    const Card = [...loaded.elements.values()].find((el) => typeof el.getConfigElement === "function");
    assert.ok(Card, "card class has no getConfigElement");
    assert.equal(typeof Card.getStubConfig === "function" || card === "taskmate-sticker-chart-card.js", true);
    await Card.getConfigElement();
    assert.deepEqual(loaded.imports, [`./editors/${f}?v=test`]);
    assert.ok(loaded.get(tag), `<${tag}> was not defined by getConfigElement()`);
    assert.deepEqual(bundles, [["editor"]]);
  });
}

test("bonuses and penalties: the shared editor gets the wrapper's versioned URL", async () => {
  for (const wrapper of SHARED["taskmate-incentive-card-editor.js"]) {
    assert.match(read(wrapper), /moduleUrl: import\.meta\.url,/, `${wrapper} must pass its own URL`);
  }
  const tag = "taskmate-bonuses-card";
  const loaded = loadCard("taskmate-incentive-card.js", {
    editor: false,
    window: { __taskmate_loadTranslations: () => Promise.resolve() },
    transform: (src) =>
      src.replace("export function createIncentiveCard", "function createIncentiveCard")
      + `\ncreateIncentiveCard({ moduleUrl: "http://localhost/taskmate-bonuses-card.js?v=7.8.0", tag: "${tag}",`
      + ` kind: "bonus", idKey: "bonus_id", i18n: "bonuses", attr: "bonuses", icon: "mdi:star", accent: "#2e7d32",`
      + ` cardName: "x", cardDesc: "x", bannerName: "X", bannerColor: "#000" });`,
  });
  const Card = loaded.get(tag);
  assert.equal(loaded.get(`${tag}-editor`), undefined);
  await Card.getConfigElement();
  assert.deepEqual(loaded.imports, ["http://localhost/editors/taskmate-incentive-card-editor.js?v=7.8.0"]);
  assert.ok(loaded.get(`${tag}-editor`), "the bonuses editor was not defined");
});

test("constants an editor shares with its card are identical copies", () => {
  let compared = 0;
  for (const f of editorFiles) {
    const editor = read(`editors/${f}`);
    const cards = SHARED[f] ? ["taskmate-incentive-card.js"] : [cardOf(f)];
    for (const card of cards) {
      const src = read(card);
      for (const [, name] of editor.matchAll(/^const (\w+) = /gm)) {
        if (["LitElement", "html", "css"].includes(name)) continue;
        const inEditor = editor.match(new RegExp(`^const ${name} = [^\\n]*`, "m"))[0];
        const inCard = src.match(new RegExp(`^const ${name} = [^\\n]*`, "m"));
        if (!inCard) continue; // editor-only
        assert.equal(inEditor, inCard[0], `${name} differs between ${card} and editors/${f}`);
        compared += 1;
      }
      for (const [block, name] of editor.matchAll(/^(?:function (\w+)\(|const (\w+) = \()[\s\S]*?^\};?$/gm)) {
        const fn = name || block.match(/^const (\w+)/)?.[1];
        const start = src.indexOf(block.split("\n")[0]);
        if (start < 0) continue;
        assert.equal(src.slice(start, start + block.length), block, `${fn} differs between ${card} and editors/${f}`);
        compared += 1;
      }
    }
  }
  assert.ok(compared >= 18, `expected to compare the shared constants, compared ${compared}`);
});

test("the header-colour picker carries its own styles, and no editor restyles it", () => {
  // The picker's markup and CSS both come from taskmate-design.js, so every
  // editor gets the same finger-sized targets. An editor's static styles are
  // adopted sheets, which beat the picker's own <style>: a stale copy of the
  // old 22px swatch rule in any editor would shrink the targets again.
  let users = 0;
  for (const f of editorFiles) {
    const src = read(`editors/${f}`);
    if (src.includes("colourPicker(")) users++;
    assert.doesNotMatch(src, /\.(colour-[a-z-]+|preset-swatch)[^{\n]*\{/, `${f} restyles the shared colour picker`);
  }
  assert.ok(users >= 27, `expected the shared picker in at least 27 editors, found ${users}`);
});

function renderPicker(current = "#7c3aed") {
  class Lit {}
  Lit.prototype.html = template;
  class View extends Lit {}
  const window = { matchMedia: () => ({ matches: false }) };
  vm.runInNewContext(read("taskmate-design.js"), {
    window,
    document: { documentElement: { getAttribute: () => "" }, getElementById: () => ({}), createElement: () => ({}), head: { appendChild() {} } },
    customElements: { get: (tag) => (tag === "hui-masonry-view" ? View : undefined) },
  });
  const calls = [];
  const out = render(window.__taskmate_design.colourPicker({
    defaultValue: "#7c3aed",
    current,
    label: "Header Colour",
    helper: "Card header background colour",
    resetLabel: "Reset",
    onInput: (v) => calls.push(["input", v]),
    onPreset: (v) => calls.push(["preset", v]),
    onReset: () => calls.push(["reset"]),
  }));
  return { out, calls };
}

test("every header-colour picker control is a 36px touch target", () => {
  const { out } = renderPicker();
  const css = out.markup.match(/<style>([\s\S]*?)<\/style>/)[1];
  const rule = (sel) => {
    const m = css.match(new RegExp(`(?:^|\\n)\\s*${sel.replace(/[\\^$.*+?()[\]{}|]/g, "\\$&")}\\s*\\{([^}]*)\\}`));
    assert.ok(m, `no ${sel} rule in the picker's styles`);
    return m[1];
  };
  const px = (body, prop) => {
    const m = body.match(new RegExp(`(?:^|;|\\s)${prop}:\\s*(\\d+)px`));
    return m ? Number(m[1]) : 0;
  };
  const swatch = rule(".preset-swatch");
  assert.ok(px(swatch, "width") >= 36 && px(swatch, "height") >= 36, "preset swatch button under 36px");
  const reset = rule(".colour-reset");
  assert.ok(px(reset, "min-height") >= 36, "Reset under 36px tall");
  const wrap = rule(".colour-swatch-wrapper");
  assert.ok(px(wrap, "width") >= 36 && px(wrap, "height") >= 36, "colour swatch under 36px");
  // A colour input keeps its own 50x27 box unless it is told to fill the swatch.
  const input = rule('.colour-swatch-wrapper input[type="color"]');
  assert.match(input, /width:\s*100%/);
  assert.match(input, /height:\s*100%/);
});

test("the header-colour picker still sets, presets and resets the colour", async () => {
  const { out, calls } = renderPicker("#E67E22");
  const swatches = out.controls.filter((c) => /preset-swatch/.test(c.attrs));
  assert.equal(swatches.length, 7);
  const active = swatches.filter((c) => /preset-swatch active/.test(c.attrs));
  assert.equal(active.length, 1, "exactly one swatch is marked as the current colour");
  assert.match(active[0].attrs, /title=#e67e22/);
  await swatches[2].click();
  await out.controls.find((c) => /colour-reset/.test(c.attrs)).click();
  assert.deepEqual(calls, [["preset", "#27ae60"], ["reset"]]);
});
