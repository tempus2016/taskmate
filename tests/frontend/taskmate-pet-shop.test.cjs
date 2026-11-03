const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// Pet shop: the pet card's Shop tab, the art for each slot, the editor options
// and the admin panel's catalogue.

const sandbox = {
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  setTimeout: () => 0,
  clearTimeout: () => {},
  DOMParser: class {
    parseFromString(markup) {
      const node = { cloneNode: () => node, toString: () => markup };
      return { documentElement: node };
    }
  },
};
const ENTITY = "sensor.taskmate_overview";
const petMod = loadCard("taskmate-pet-card.js", { sandbox });
const PetCard = petMod.get("taskmate-pet-card");
const Editor = petMod.get("taskmate-pet-card-editor");
const art = () => (petMod.window ? petMod.window.__taskmate_pet_art : sandbox.window?.__taskmate_pet_art);

const plain = (o) => JSON.parse(JSON.stringify(o));
const withArt = (markup) => markup
  + [...markup.matchAll(/src="?data:image\/svg\+xml;charset=utf-8,([^"\s>]*)/g)].map(m => decodeURIComponent(m[1])).join("");

const CATALOGUE = {
  enabled: true,
  items: [
    { id: "sunglasses", emoji: "🕶️", slot: "face", cost: 15, default: true },
    { id: "cap", emoji: "🧢", slot: "hat", cost: 20, default: true },
    { id: "rainbow", emoji: "🌈", slot: "colour", cost: 60, tint: "rainbow", default: true },
    { id: "wings", emoji: "🦋", slot: "back", cost: 80, level: 12, default: true },
    { id: "x1", name: "Party <hat>", emoji: "🥳", slot: "hat", cost: 500 },
  ],
  owned: ["cap"],
  pending: [],
  earned: ["bow", "top_hat"],
  spendable: 86,
  approve_over: 50,
  carry_over: true,
  level: 9,
};

function petCard(pet, config = {}, catalogue = CATALOGUE) {
  const calls = [];
  const card = new PetCard();
  card.setConfig({ entity: ENTITY, child_id: "malia", ...config });
  card.hass = {
    locale: { language: "en" },
    states: { [ENTITY]: { state: "ok", attributes: { points_icon: "mdi:star", points_name: "Stars",
      children: [{ id: "malia", name: "Malia", points: 86, level: 9, pet }] } } },
    callService: async (domain, service, data) => calls.push({ service, data }),
    callWS: async (msg) => { calls.push({ ws: msg }); return catalogue; },
  };
  return { card, calls };
}

const PET = { adopted: true, name: "Sparky", species: "dragon", stage: "teen", chores: 80, xp: 412, mood: "happy",
  accessories: ["bow", "top_hat"], goal: { kind: "stage", from: 200, at: 600 } };

test("no shop on the sensor: no tabs, and the art is exactly what it was", () => {
  const { card } = petCard(PET);
  const { markup } = render(card.render());
  assert.doesNotMatch(markup, /pt-tabs/);
  const { petScene, petWorn } = art();
  const legacy = petScene("dragon", "teen", { accessories: ["bow", "top_hat"] });
  const viaWorn = petScene("dragon", "teen", { accessories: ["bow", "top_hat"], worn: petWorn({ accessories: ["bow", "top_hat"] }) });
  assert.deepEqual(plain(viaWorn), plain(legacy));
  assert.match(legacy.pet, /🎩/);
  assert.match(legacy.pet, /🎀/);
});

test("the crown beats the top hat and the scarf beats the bow, as before", () => {
  const { petWorn } = art();
  const worn = petWorn({ accessories: ["bow", "top_hat", "scarf", "crown"] });
  assert.equal(worn.hat.id, "crown");
  assert.equal(worn.neck.id, "scarf");
});

test("shop open: a Shop tab appears, and show_shop: false hides it", () => {
  const pet = { ...PET, shop: { owned: ["cap"], approve_over: 50 }, worn: { hat: { id: "cap", emoji: "🧢" }, neck: { id: "bow" } } };
  assert.match(render(petCard(pet).card.render()).markup, /pt-tabs/);
  assert.doesNotMatch(render(petCard(pet, { show_shop: false }).card.render()).markup, /pt-tabs/);
});

test("worn items are drawn in their slots, and a taken-off accessory is not", () => {
  const { petScene } = art();
  const scene = petScene("cat", "kid", { worn: {
    hat: { id: "cap", emoji: "🧢" }, face: { id: "sunglasses", emoji: "🕶️" }, held: { id: "balloon", emoji: "🎈" },
    back: { id: "wings", emoji: "🦋" }, body: { id: "ghost_sheet", emoji: "👻" }, home: { id: "cosy_bed", emoji: "🛏️" },
    colour: { id: "dye", emoji: "🎨", tint: "#ff8800" },
  } });
  for (const glyph of ["🧢", "🕶️", "🎈", "🦋", "👻"]) assert.ok(scene.pet.includes(glyph), glyph);
  assert.ok(scene.back.includes("🛏️"), "the home item stands in the scene");
  assert.match(scene.pet, /feFlood flood-color="#ff8800"/);
  assert.doesNotMatch(scene.pet, /🎀|🎩/);
  // The wings sit behind the pet's body, the costume over it.
  assert.ok(scene.pet.indexOf("🦋") < scene.pet.indexOf("<ellipse"));
});

test("a parent's emoji is escaped before it goes into the SVG", () => {
  const { petScene } = art();
  const scene = petScene("dog", "grown", { worn: { held: { id: "x", emoji: "<b>&" } } });
  assert.ok(scene.pet.includes("&lt;b&gt;&amp;"));
  assert.ok(!scene.pet.includes("<b>&"));
});

test("a rainbow colour draws a rainbow glow, not a filter", () => {
  const { petScene } = art();
  const scene = petScene("bunny", "teen", { worn: { colour: { id: "rainbow", emoji: "🌈", tint: "rainbow" } } });
  assert.doesNotMatch(scene.pet, /<filter/);
  assert.match(scene.pet, /#ff6b6b/);
});

async function shopCard(pet, config) {
  const r = petCard(pet, config);
  await r.card._openTab("shop");
  return r;
}

const SHOP_PET = { ...PET, shop: { owned: ["cap"], approve_over: 50 }, worn: { hat: { id: "top_hat" }, neck: { id: "bow" } } };

test("the Shop tab lists earned accessories and the catalogue with fixed prices", async () => {
  const { card, calls } = await shopCard(SHOP_PET);
  assert.deepEqual(plain(calls[0].ws), { type: "taskmate/pet_shop/catalogue", child_id: "malia" });
  const { markup } = render(card.render());
  assert.ok(markup.includes(localize("pet.shop_earned")));
  assert.ok(markup.includes(localize("pet.item_sunglasses")));
  assert.ok(markup.includes("Party &lt;hat&gt;") || markup.includes("Party <hat>"));
  assert.ok(markup.includes(localize("pet.shop_level_short", { level: 15 })), "the scarf is still locked");
  assert.ok(markup.includes(localize("pet.shop_level_short", { level: 12 })), "the wings are level-gated");
  assert.ok(markup.includes(localize("pet.shop_owned")), "the cap is owned");
});

test("buying asks first, then calls the service for this child", async () => {
  const { card, calls } = await shopCard(SHOP_PET);
  const view = render(card.render());
  const buy = view.controls.find(c => c.text === localize("pet.shop_buy"));
  await buy.click();
  const sheet = render(card.render());
  assert.ok(sheet.markup.includes(localize("pet.shop_confirm_left", { remaining: 71 })));
  await sheet.control(localize("pet.shop_buy_it")).click();
  const call = calls.find(c => c.service === "buy_pet_item");
  assert.deepEqual(plain(call.data), { child_id: "malia", item_id: "sunglasses" });
});

test("over the approval limit the sheet offers to ask a parent", async () => {
  const { card } = await shopCard(SHOP_PET);
  card._confirm = CATALOGUE.items[2];
  const { markup } = render(card.render());
  assert.ok(markup.includes(localize("pet.shop_confirm_ask")));
  assert.ok(markup.includes(localize("pet.shop_ask_parent")));
});

test("items the child can't afford are disabled, or hidden with hide_unaffordable", async () => {
  const { card } = await shopCard(SHOP_PET);
  const view = render(card.render());
  const buttons = view.controls.filter(c => c.text === localize("pet.shop_buy"));
  assert.ok(buttons.some(b => b.disabled), "the 500-point hat can't be bought");
  const hidden = await shopCard(SHOP_PET, { hide_unaffordable: true });
  assert.doesNotMatch(render(hidden.card.render()).markup, /Party/);
});

test("Put on / Take off call equip_pet_item", async () => {
  const { card, calls } = await shopCard(SHOP_PET);
  const view = render(card.render());
  await view.controls.find(c => c.text === localize("pet.shop_put_on")).click();
  assert.deepEqual(plain(calls.find(c => c.service === "equip_pet_item").data), { child_id: "malia", item_id: "cap", wear: true });
  await view.controls.find(c => c.text === localize("pet.shop_take_off")).click();
  assert.equal(calls.filter(c => c.service === "equip_pet_item")[1].data.wear, false);
});

test("a pending purchase shows as waiting for a parent", async () => {
  const pet = { ...SHOP_PET, shop: { ...SHOP_PET.shop, pending: ["rainbow"] } };
  const { card } = await shopCard(pet);
  assert.ok(render(card.render()).markup.includes(localize("pet.shop_waiting")));
});

test("the editor offers show_shop and hide_unaffordable with translated labels", () => {
  const ed = new Editor();
  ed.hass = { locale: { language: "en" }, states: {} };
  ed.setConfig({ entity: ENTITY, child_id: "malia" });
  const names = ed._buildSchema().map(s => s.name);
  assert.ok(names.includes("show_shop") && names.includes("hide_unaffordable"));
  assert.equal(ed._computeLabel({ name: "show_shop" }), localize("pet.editor.show_shop"));
  assert.equal(ed._computeLabel({ name: "hide_unaffordable" }), localize("pet.editor.hide_unaffordable"));
});

// ── panel ────────────────────────────────────────────────────────────────

const panelMod = loadCard("taskmate-panel.js", { sandbox: { navigator: { userAgent: "test", language: "en" }, localStorage: sandbox.localStorage } });

test("the panel shows the catalogue and pending purchases in Settings → Virtual pets", () => {
  const P = panelMod.get("taskmate-panel");
  const p = Object.create(P.prototype);
  p._hass = { locale: { language: "en" } };
  p._state = { pet_shop: {
    items: [{ id: "cap", name: "", emoji: "🧢", slot: "hat", cost: 20, level: 0, shown: true },
      { id: "x", name: "<b>Bad</b>", emoji: "🥳", slot: "colour", cost: 9, level: 3, shown: false, tint: "#ff8800" }],
    pending: [{ id: "p1", child_name: "Malia", item_id: "cap", item_name: "", emoji: "🧢", cost: 60 }],
  }, settings: {} };
  p._pointsName = () => "Stars";
  const html = p._renderPetSettings({ pet_shop_enabled: true });
  assert.ok(html.includes('data-setting="pet_shop_enabled"'));
  assert.ok(html.includes('data-setting="pet_shop_approve_over"'));
  assert.ok(html.includes('data-setting="pet_shop_carry_over"'));
  assert.ok(html.includes('data-act="petshop-approve" data-id="p1"'));
  assert.ok(html.includes('data-act="petshop-reset"'));
  assert.ok(html.includes("&lt;b&gt;Bad&lt;/b&gt;"));
  assert.ok(!html.includes("<b>Bad</b>"));
});

test("the panel refuses to undo a pet shop purchase", () => {
  const P = panelMod.get("taskmate-panel");
  const p = Object.create(P.prototype);
  assert.equal(p._txnReversible("Pet shop: Sunglasses"), false);
});

// ── the accessory strip on the Pet tab ───────────────────────────────────

const strip = (markup) => [...markup.matchAll(/<span class="pt-acc-item ([^"]*)" title="([^"]*)"/g)].map(m => [m[2], m[1]]);

test("without a wardrobe the strip is exactly as before: unlocked means highlighted", () => {
  const { card } = petCard(PET);
  const rows = strip(render(card.render()).markup);
  assert.deepEqual(plain(rows), [
    [localize("pet.acc_bow"), "on"], [localize("pet.acc_top_hat"), "on"],
    [localize("pet.acc_scarf"), ""], [localize("pet.acc_crown"), ""],
  ]);
});

test("with a wardrobe only what is worn is highlighted; unlocked but off is plain", () => {
  const pet = { ...PET, shop: { owned: ["cap"] }, worn: { hat: { id: "cap", emoji: "🧢" }, neck: { id: "bow" } } };
  const rows = strip(render(petCard(pet).card.render()).markup);
  assert.deepEqual(plain(rows), [
    [localize("pet.acc_bow"), "on"], [localize("pet.acc_top_hat"), "earned"],
    [localize("pet.acc_scarf"), ""], [localize("pet.acc_crown"), ""],
  ]);
  const bare = { ...PET, shop: {}, worn: {} };
  const off = strip(render(petCard(bare).card.render()).markup);
  assert.deepEqual(plain(off.map(r => r[1])), ["earned", "earned", "", ""]);
});

test("Shop tab buttons are a child-sized tap target (at least 36px) in every design", () => {
  const css = render(PetCard.styles).markup;
  assert.match(css, /\.pt-btn-sm \{[^}]*min-height: 36px/);
  // No design re-pads the small button back down.
  assert.ok(!/data-tm-design[^{]*\.pt-btn-sm/.test(css));
});
