const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, localize, render } = require("./harness.cjs");

// The child and kiosk card editors group their long option lists into
// collapsible sections, each with a one-line summary under its title. Every
// option must land in exactly one section, or it disappears from the editor.

class CustomEvent { constructor(type, init) { this.type = type; this.detail = init?.detail; } }
const ENTITY = "sensor.taskmate_overview";
const plain = (v) => JSON.parse(JSON.stringify(v));
// The form data object handed to the ha-forms, found anywhere in the template tree.
function formData(tree, key) {
  if (!tree || typeof tree !== "object") return undefined;
  if (!tree.__tmTemplate && !Array.isArray(tree) && tree[key] !== undefined) return tree;
  for (const v of tree.__tmTemplate ? tree.values : Array.isArray(tree) ? tree : []) {
    const found = formData(v, key);
    if (found) return found;
  }
  return undefined;
}

const EDITORS = {
  child: {
    file: "taskmate-child-card.js", tag: "taskmate-child-card-editor", schema: "_buildSchema",
    config: { entity: ENTITY, child_id: "c1" },
    top: ["entity", "child_id", "time_category"],
  },
  kiosk: {
    file: "taskmate-kiosk-card.js", tag: "taskmate-kiosk-card-editor", schema: "_schema",
    config: { entity: ENTITY },
    top: ["entity", "title"],
  },
};

function editor(kind, extra = {}) {
  const spec = EDITORS[kind];
  const loaded = loadCard(spec.file, { sandbox: { CustomEvent } });
  const el = new (loaded.get(spec.tag))();
  el.hass = { language: "en", states: { [ENTITY]: { attributes: { points_name: "Stars", children: [] } } }, callWS: () => Promise.resolve({}) };
  el.setConfig({ ...spec.config, ...extra });
  return el;
}

for (const [kind, spec] of Object.entries(EDITORS)) {
  test(`${kind} editor: every option sits in exactly one section`, () => {
    const el = editor(kind);
    const all = plain(el[spec.schema]().map((f) => f.name)).sort();
    const sections = el._sections();
    const placed = plain(Object.values(sections).flat().map((f) => f && f.name));
    assert.ok(!placed.includes(undefined), "a section names an option the schema doesn't have");
    assert.deepEqual([...placed].sort(), all);
    assert.deepEqual(plain(sections.top.map((f) => f.name)), spec.top);
  });

  test(`${kind} editor: four collapsible sections, only Appearance open, all translated`, () => {
    const el = editor(kind);
    const { markup } = render(el.render());
    const panels = markup.match(/<ha-expansion-panel/g) || [];
    assert.equal(panels.length, 4);
    assert.deepEqual(markup.match(/\.expanded=\w+/g), [".expanded=true", ".expanded=false", ".expanded=false", ".expanded=false"]);
    for (const key of ["section_appearance", "section_which_chores", "section_kid_features", "section_advanced"]) {
      assert.notEqual(localize(`common.editor.${key}`), `common.editor.${key}`, `${key} is not translated`);
    }
    const tree = el.render();
    const flat = JSON.stringify(tree, (k, v) => (typeof v === "function" ? undefined : v));
    assert.ok(flat.includes(localize("common.editor.section_appearance")));
  });
}

test("child editor summaries describe the current settings", () => {
  const el = editor("child", { density: "compact", header_color: "#123456", show_mood: false, debug: true, pre_reader: true });
  const data = formData(el.render(), "time_category");
  const s = el._summaries(data, el._sections());
  assert.equal(s.appearance, "Global design · Compact · Custom header colour · Seasonal on");
  assert.equal(s.which, "Available first · Not due: hide · Missed: dim · 4 more");
  // Pre-Reader Mode hides the help button by default, so 7 of the 9 are on.
  assert.match(s.kid, /^\d of 9 on · Picture mode on$/);
  assert.equal(s.advanced, "Parent actions on · Appeals on · Debug on");
});

test("kiosk editor summaries describe the current settings", () => {
  const el = editor("kiosk", { completed_mode: "hide", show_pet: false, timeout: 90, ambient_mode: "photos" });
  const data = formData(el.render(), "timeout");
  const s = el._summaries(data, el._sections());
  assert.equal(s.appearance, "Global design · Default header colour · Seasonal on");
  assert.equal(s.which, "Done: hide · Missed: show · 1 more");
  assert.equal(s.kid, "12 of 15 on");
  assert.equal(s.advanced, `Back to the picker after 90 s · ${localize("kiosk.editor.ambient_photos")}`);
});

test("child editor: names in picture mode sits under picture-only mode, off until it is on", () => {
  const off = editor("child");
  assert.deepEqual(plain(off._sections().kidNested.map((f) => f.name)), ["pre_reader_labels"]);
  const nested = (el) => render(el.render()).markup.match(/<div class="nested">\s*<ha-form([^>]*)>/)[1];
  assert.match(nested(off), /\.disabled=true\b/);
  assert.match(nested(editor("child", { pre_reader: true })), /\.disabled=false\b/);
  assert.equal(off._computeHelper({ name: "pre_reader_labels" }), localize("child.editor.pre_reader_labels_helper"));
});
