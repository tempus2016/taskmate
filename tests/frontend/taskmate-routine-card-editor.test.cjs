const assert = require("node:assert/strict");
const { readFileSync, readdirSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { loadCard, localize, render, WWW } = require("./harness.cjs");

// The Routine card shipped an editor that Home Assistant never opened (the card
// had no getConfigElement), with English-only labels and mwc-list-item options
// current Home Assistant no longer ships. It is now an ha-form like the other
// TaskMate editors, translated, and the card opens it.

const ENTITY = "sensor.taskmate_overview";
const CHILDREN = [{ id: "kid1", name: "Sam" }, { id: "kid2", name: "Alex" }];
const hass = { language: "en", states: { [ENTITY]: { attributes: { children: CHILDREN } } } };

function editor(config) {
  const loaded = loadCard("taskmate-routine-card.js", {
    sandbox: { CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init?.detail; } } },
    window: { __taskmate_design: { apply: () => "classic", styles: () => null, editorOptions: () => [{ value: "global", label: "x" }] } },
  });
  const Editor = loaded.get("taskmate-routine-card-editor");
  const el = new Editor();
  el.hass = hass;
  el.setConfig(config);
  return { el, loaded };
}

// The sandbox has its own Array/Object, so copy out before deepEqual.
const plain = (v) => JSON.parse(JSON.stringify(v));
const schemaOf = (el) => plain(el._buildSchema());

test("the card opens its visual editor", async () => {
  const loaded = loadCard("taskmate-routine-card.js", { editor: false, window: { __taskmate_loadTranslations: () => Promise.resolve() } });
  await loaded.get("taskmate-routine-card").getConfigElement();
  assert.deepEqual(loaded.imports, ["./editors/taskmate-routine-card-editor.js?v=test"]);
  assert.ok(loaded.get("taskmate-routine-card-editor"));
});

test("the editor is an ha-form with the child, routine, title and design fields", () => {
  const { el } = editor({ entity: ENTITY, child_id: "kid1", time_category: "morning" });
  const markup = render(el.render()).markup;
  assert.match(markup, /<ha-form/);
  assert.doesNotMatch(markup, /mwc-list-item|ha-select|ha-textfield/);
  assert.deepEqual(schemaOf(el).map((s) => s.name), ["entity", "child_id", "time_category", "title", "card_design"]);
  const kids = schemaOf(el).find((s) => s.name === "child_id").selector.select.options;
  assert.deepEqual(kids.map((o) => [o.value, o.label]), [["kid1", "Sam"], ["kid2", "Alex"]], "children by name, stored by id");
});

test("the routine options are the six the card accepts, with translated labels", () => {
  const { el } = editor({ entity: ENTITY, child_id: "kid1" });
  const opts = schemaOf(el).find((s) => s.name === "time_category").selector.select.options;
  assert.deepEqual(opts.map((o) => o.value), ["all", "morning", "afternoon", "evening", "night", "anytime"]);
  assert.deepEqual(opts.map((o) => o.label), ["Whole day", "Morning", "Afternoon", "Evening", "Night", "Anytime chores"]);
  for (const name of ["entity", "child_id", "time_category", "title", "card_design"]) {
    const label = el._computeLabel({ name });
    assert.notEqual(label, name, `${name} has no label`);
    assert.doesNotMatch(label, /\./, `${name} label is a raw key: ${label}`);
  }
  assert.equal(el._computeLabel({ name: "time_category" }), localize("routine.editor.time_category"));
});

test("the form shows the stored values, with the card's defaults when unset", () => {
  const { el } = editor({ entity: ENTITY, child_id: "kid2", time_category: "night", title: "Bedtime" });
  const tree = el.render();
  const data = tree.values.find((v) => v && v.child_id !== undefined);
  assert.deepEqual({ ...data }, { entity: ENTITY, child_id: "kid2", time_category: "night", title: "Bedtime", card_design: "global" });
  const bare = editor({ entity: ENTITY, child_id: "kid1" }).el.render().values.find((v) => v && v.child_id !== undefined);
  assert.equal(bare.time_category, "all");
});

test("changes are stored, and defaults are dropped from the YAML", () => {
  const { el } = editor({ type: "custom:taskmate-routine-card", entity: ENTITY, child_id: "kid1", time_category: "morning" });
  el._formChanged({ detail: { value: { entity: ENTITY, child_id: "kid2", time_category: "evening", title: "Tea time", card_design: "playroom" } } });
  assert.deepEqual(plain(el.dispatched.at(-1).detail.config), {
    type: "custom:taskmate-routine-card", entity: ENTITY, child_id: "kid2", time_category: "evening", title: "Tea time", card_design: "playroom",
  });
  el._formChanged({ detail: { value: { time_category: "all", title: "", card_design: "global" } } });
  assert.deepEqual(plain(el.dispatched.at(-1).detail.config), { type: "custom:taskmate-routine-card", entity: ENTITY, child_id: "kid1" });
});

test("every locale translates the routine editor strings", () => {
  const LOCALES = path.join(WWW, "locales");
  const en = JSON.parse(readFileSync(path.join(LOCALES, "en.json"), "utf8"));
  const keys = Object.keys(en).filter((k) => k.startsWith("routine.editor."));
  assert.equal(keys.length, 11);
  for (const f of readdirSync(LOCALES).filter((n) => n.endsWith(".json"))) {
    const loc = JSON.parse(readFileSync(path.join(LOCALES, f), "utf8"));
    for (const k of keys) assert.ok(loc[k] && loc[k].trim(), `${f} lacks ${k}`);
    if (!f.startsWith("en")) {
      const same = keys.filter((k) => loc[k] === en[k]);
      assert.deepEqual(same, [], `${f} leaves English in ${same}`);
    }
  }
});

