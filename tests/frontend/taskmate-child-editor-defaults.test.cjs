const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

// The child card editor must show what the card does with an option left
// unset. It used to show "Morning" for an unset time_category while the card
// rendered Anytime, and dropped an explicit "morning" as if it were the
// default. The help button switch showed on for a pre-reader child, whose
// card hides it, and a parent could not switch it back on.

class CustomEvent { constructor(type, init) { this.type = type; this.detail = init?.detail; } }
const ENTITY = "sensor.taskmate_overview";
const plain = (v) => JSON.parse(JSON.stringify(v));

function setup(config, { children = [], familyStyle } = {}) {
  const window = familyStyle ? { __taskmate_family_style: () => familyStyle } : {};
  const loaded = loadCard("taskmate-child-card.js", { sandbox: { CustomEvent }, window });
  const Card = loaded.get("taskmate-child-card");
  const card = new Card();
  card.setConfig({ entity: ENTITY, child_id: "c1", ...config });
  const editor = new (loaded.get("taskmate-child-card-editor"))();
  editor.hass = { language: "en", states: { [ENTITY]: { attributes: { points_name: "Stars", children } } } };
  editor.setConfig({ entity: ENTITY, child_id: "c1", ...config });
  return { card, editor };
}
// The form data handed to ha-form, wherever it sits in the template tree.
function findData(tree) {
  if (!tree || typeof tree !== "object") return undefined;
  if (!tree.__tmTemplate && !Array.isArray(tree) && tree.time_category !== undefined) return tree;
  for (const v of tree.__tmTemplate ? tree.values : Array.isArray(tree) ? tree : []) {
    const found = findData(v);
    if (found) return found;
  }
  return undefined;
}
const formData = (el) => findData(el.render());
const lastConfig = (el) => plain(el.dispatched.at(-1).detail.config);

test("an unset time_category shows the card's own default", () => {
  const { card, editor } = setup({});
  assert.equal(card.config.time_category, "anytime");
  assert.equal(formData(editor).time_category, card.config.time_category);
});

test("choosing Morning is stored; choosing the default is not", () => {
  const { editor } = setup({});
  editor._formChanged({ detail: { value: { time_category: "morning" } } });
  assert.equal(lastConfig(editor).time_category, "morning");
  editor.setConfig(lastConfig(editor));
  editor._formChanged({ detail: { value: { time_category: "anytime" } } });
  assert.equal(lastConfig(editor).time_category, undefined);
});

test("the help button switch follows Pre-Reader Mode like the card", () => {
  assert.equal(formData(setup({}).editor).show_help_button, true);
  assert.equal(formData(setup({ pre_reader: true }).editor).show_help_button, false);
  // The 3-5 stage turns Pre-Reader Mode on when the YAML leaves it unset.
  const kids = [{ id: "c1", name: "Alex", age_group: "3_5" }];
  assert.equal(formData(setup({}, { children: kids }).editor).show_help_button, false);
  assert.equal(formData(setup({ pre_reader: false }, { children: kids }).editor).show_help_button, true);
  // Team style keeps the button in Pre-Reader Mode.
  assert.equal(formData(setup({ pre_reader: true }, { familyStyle: "team" }).editor).show_help_button, true);
  assert.equal(formData(setup({ pre_reader: true, show_help_button: true }).editor).show_help_button, true);
});

test("a parent can switch the help button on for a pre-reader", () => {
  const { editor } = setup({ pre_reader: true });
  editor._formChanged({ detail: { value: { show_help_button: true } } });
  assert.equal(lastConfig(editor).show_help_button, true);
  editor.setConfig(lastConfig(editor));
  editor._formChanged({ detail: { value: { show_help_button: false } } });
  assert.equal(lastConfig(editor).show_help_button, undefined, "off is the pre-reader default, so it is not stored");
  const { editor: plainEditor } = setup({});
  plainEditor._formChanged({ detail: { value: { show_help_button: true } } });
  assert.equal(lastConfig(plainEditor).show_help_button, undefined, "on is the default without Pre-Reader Mode");
});
