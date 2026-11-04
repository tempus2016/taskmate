const assert = require("node:assert/strict");
const { readFileSync, readdirSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { loadCard, localize, render, WWW } = require("./harness.cjs");

// The Family Goal and Photo Gallery cards had no visual editor, so Home
// Assistant showed "Visual editor not supported" and they could only be set up
// in YAML. Each now opens an ha-form editor like the other TaskMate cards.

const CARDS = {
  "taskmate-family-goal-card": {
    entity: "sensor.taskmate_overview",
    fields: ["entity", "title", "card_design"],
    accent: "#16a085",
    full: { entity: "sensor.taskmate_overview", title: "Movie night", card_design: "playroom" },
  },
  "taskmate-photo-gallery-card": {
    entity: "sensor.taskmate_activity",
    fields: ["entity", "title", "max", "card_design"],
    accent: "#5d6d7e",
    full: { entity: "sensor.taskmate_activity", title: "Proof photos", max: 40, card_design: "console" },
  },
};
const plain = (v) => JSON.parse(JSON.stringify(v));

function editor(card, config) {
  const loaded = loadCard(`${card}.js`, {
    sandbox: { CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init?.detail; } } },
    window: { __taskmate_design: { apply: () => "classic", styles: () => null, editorOptions: () => [{ value: "global", label: "x" }] } },
  });
  const el = new (loaded.get(`${card}-editor`))();
  el.hass = { language: "en", states: {} };
  el.setConfig(config);
  return el;
}
const formData = (el) => el.render().values.find((v) => v && v.card_design !== undefined);

for (const [card, spec] of Object.entries(CARDS)) {
  test(`${card} opens its visual editor`, async () => {
    const loaded = loadCard(`${card}.js`, { editor: false, window: { __taskmate_loadTranslations: () => Promise.resolve() } });
    assert.equal(loaded.get(`${card}-editor`), undefined, "the editor must load only when asked for");
    await loaded.get(card).getConfigElement();
    assert.deepEqual(loaded.imports, [`./editors/${card}-editor.js?v=test`]);
    assert.ok(loaded.get(`${card}-editor`));
  });

  test(`${card} editor is an ha-form with every documented option, translated`, () => {
    const el = editor(card, { entity: spec.entity });
    const markup = render(el.render()).markup;
    assert.match(markup, /<ha-form/);
    assert.deepEqual(plain(el._buildSchema()).map((s) => s.name), spec.fields);
    for (const name of spec.fields) {
      const label = el._computeLabel({ name });
      assert.notEqual(label, name, `${name} has no label`);
      assert.doesNotMatch(label, /^[a-z_]+\.[a-z_.]+$/, `${name} label is a raw key: ${label}`);
    }
    assert.notEqual(el._computeHelper({ name: "title" }), "", "title has no helper");
  });

  test(`${card} editor shows stored values and round-trips, dropping defaults`, () => {
    const el = editor(card, { type: `custom:${card}`, ...spec.full });
    assert.deepEqual({ ...formData(el) }, spec.full);
    el._formChanged({ detail: { value: { ...spec.full } } });
    assert.deepEqual(plain(el.dispatched.at(-1).detail.config), { type: `custom:${card}`, ...spec.full });
    const cleared = Object.fromEntries(Object.keys(spec.full).filter((k) => k !== "entity").map((k) => [k, k === "card_design" ? "global" : undefined]));
    el._formChanged({ detail: { value: cleared } });
    assert.deepEqual(plain(el.dispatched.at(-1).detail.config), { type: `custom:${card}`, entity: spec.entity });
    const bare = formData(editor(card, { entity: spec.entity }));
    assert.equal(bare.card_design, "global");
    assert.equal(bare.max, undefined, "an unset photo limit stays empty, not 0");
  });

  test(`${card} editor sets the header colour, defaulting to the card's own`, () => {
    let seen = null;
    const designed = loadCard(`${card}.js`, {
      sandbox: { CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init?.detail; } } },
      window: { __taskmate_design: { apply: () => "classic", styles: () => null, editorOptions: () => [], colourPicker: (o) => { seen = o; return ""; } } },
    });
    const e2 = new (designed.get(`${card}-editor`))();
    e2.hass = { language: "en", states: {} };
    e2.setConfig({ entity: spec.entity });
    e2.render();
    assert.equal(seen.defaultValue, spec.accent);
    assert.equal(seen.current, spec.accent);
    seen.onPreset("#e74c3c");
    assert.equal(plain(e2.dispatched.at(-1).detail.config).header_color, "#e74c3c");
    assert.equal(localize("common.editor.header_colour"), seen.label);
  });
}

test("every locale translates the new editor strings", () => {
  const LOCALES = path.join(WWW, "locales");
  const en = JSON.parse(readFileSync(path.join(LOCALES, "en.json"), "utf8"));
  const keys = Object.keys(en).filter((k) => k.startsWith("family_goal.editor.") || k.startsWith("gallery.editor."));
  assert.equal(keys.length, 6);
  for (const f of readdirSync(LOCALES).filter((n) => n.endsWith(".json"))) {
    const loc = JSON.parse(readFileSync(path.join(LOCALES, f), "utf8"));
    for (const k of keys) assert.ok(loc[k] && loc[k].trim(), `${f} lacks ${k}`);
    if (!f.startsWith("en")) {
      const same = keys.filter((k) => loc[k] === en[k]);
      assert.deepEqual(same, [], `${f} leaves English in ${same}`);
    }
    // The browser reads the editor bundle, not the source file.
    const bundle = JSON.parse(readFileSync(path.join(LOCALES, f.replace(/\.json$/, ""), "editor.json"), "utf8"));
    for (const k of keys) assert.equal(bundle[k], loc[k], `${f}: ${k} missing from the editor bundle`);
  }
});

// #771 gate: with no family goal set (or a wrong entity) the cards drew only a
// placeholder, so the title and header colour picked in the new editor never
// showed in its preview. Every state now draws the card's header.
function card(tag, config, states) {
  const loaded = loadCard(`${tag}.js`, { editor: false, window: { __taskmate_design: { apply: () => "classic", styles: () => null } } });
  const el = new (loaded.get(tag))();
  const props = {};
  el.style = { setProperty: (k, v) => { props[k] = v; }, removeProperty: (k) => { delete props[k]; } };
  el.hass = { language: "en", states };
  el.setConfig(config);
  return { markup: render(el.render()).markup, props };
}

test("the Family Goal card keeps its title and colour with no goal set", () => {
  const states = { "sensor.taskmate_overview": { attributes: { family_goal: { enabled: false } } } };
  const off = card("taskmate-family-goal-card", { entity: "sensor.taskmate_overview", title: "Movie night", header_color: "#e74c3c" }, states);
  assert.match(off.markup, /class="fg-head"[\s\S]*Movie night/);
  assert.match(off.markup, new RegExp(localize("family_goal.disabled")));
  assert.equal(off.props["--fg-accent"], "#e74c3c");
  const plainOff = card("taskmate-family-goal-card", { entity: "sensor.taskmate_overview" }, states);
  assert.match(plainOff.markup, new RegExp(`class="fg-title">${localize("family_goal.default_title")}<`));
  const missing = card("taskmate-family-goal-card", { entity: "sensor.nope", title: "Movie night" }, {});
  assert.match(missing.markup, /class="fg-head"[\s\S]*Movie night/);
});

test("the Photo Gallery card keeps its header with no photos or a wrong entity", () => {
  const empty = card("taskmate-photo-gallery-card", { entity: "sensor.taskmate_activity", title: "Proof" }, { "sensor.taskmate_activity": { attributes: { photo_gallery: [] } } });
  assert.match(empty.markup, /class="pg-head"[\s\S]*Proof/);
  assert.match(empty.markup, new RegExp(localize("gallery.empty")));
  const missing = card("taskmate-photo-gallery-card", { entity: "sensor.nope", title: "Proof", header_color: "#27ae60" }, {});
  assert.match(missing.markup, /class="pg-head"[\s\S]*Proof/);
  assert.equal(missing.props["--pg-accent"], "#27ae60");
});
