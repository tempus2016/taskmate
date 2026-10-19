const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

// #1094: the kiosk card shows the child's pet in its side column, drawn by the
// real pet card in compact mode.

const ENTITY = "sensor.taskmate_overview";
const PET = { adopted: true, name: "Sparky", species: "dragon", stage: "kid", mood: "happy", xp: 12, accessories: ["bow"],
  goal: { kind: "stage", from: 10, at: 20 }, family: [{ species: "cat", name: "Old Tom" }] };

function setup({ pet = PET, config = {} } = {}) {
  const pets = loadCard("taskmate-pet-card.js", { sandbox: { DOMParser: class {
    parseFromString(markup) { const node = { cloneNode: () => node, toString: () => markup }; return { documentElement: node }; }
  } } });
  const PetCard = pets.get("taskmate-pet-card");
  const kiosk = loadCard("taskmate-kiosk-card.js");
  kiosk.elements.set("taskmate-pet-card", PetCard);
  const Kiosk = kiosk.get("taskmate-kiosk-card");
  const card = new Kiosk();
  card.setConfig({ entity: ENTITY, children: [{ child_id: "kid1" }], ...config });
  card.hass = { locale: { language: "en" }, states: { [ENTITY]: { state: "ok", attributes: {
    children: [{ id: "kid1", name: "Mia", points: 10, ...(pet ? { pet } : {}) }], chores: [], todays_completions: [], points_icon: "mdi:star",
  } } }, callService: async () => {} };
  return { card, PetCard };
}

const childScreen = (card) => {
  card._kid = "kid1";
  card._screen = "child";
  return card._renderChild(card._entry("kid1"), card._attrs());
};

test("the child screen carries a pet tile with a compact pet card for that child", () => {
  const { card, PetCard } = setup();
  const tile = card._petTile(card._attrs().children[0]);
  const el = tile.values.find(v => v instanceof PetCard);
  assert.ok(el, "a pet card element is embedded");
  assert.equal(el.config.child_id, "kid1");
  assert.equal(el.config.compact, true);
  assert.ok(render(childScreen(card)).markup.includes("km-pet"));
});

test("the compact pet card shows the pet but not the banner, accessories or family", () => {
  const { card, PetCard } = setup();
  const el = card._petTile(card._attrs().children[0]).values.find(v => v instanceof PetCard);
  el.hass = card.hass;
  el._applyDesign = () => {};
  const { markup } = render(el.render());
  assert.match(markup, /pt-compact/);
  assert.match(markup, /Sparky/);
  assert.match(markup, /pt-stage/);
  assert.doesNotMatch(markup, /pt-hd"|pt-acc"|pt-family"/);
});

test("no tile while pets are off, or when the card option says no", () => {
  assert.equal(setup({ pet: null }).card._petTile({ id: "kid1", name: "Mia" }), "");
  const { card } = setup({ config: { show_pet: false } });
  assert.equal(card._petTile(card._attrs().children[0]), "");
});

test("the same pet card element is reused across renders", () => {
  const { card, PetCard } = setup();
  const child = card._attrs().children[0];
  const a = card._petTile(child).values.find(v => v instanceof PetCard);
  const b = card._petTile(child).values.find(v => v instanceof PetCard);
  assert.equal(a, b);
});
