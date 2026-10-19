const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// Raffle card, pet card, and the kiosk's ambient mode, offline taps and
// raffle draws.

const store = new Map();
const localStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
};
const timers = [];
const sandbox = {
  localStorage,
  CustomEvent: class { constructor(type, init = {}) { this.type = type; this.detail = init.detail; } },
  setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
  clearTimeout: () => {},
  setInterval: () => 0,
  clearInterval: () => {},
  // The pet card turns its SVG markup into a node; here the node prints as that markup.
  DOMParser: class {
    parseFromString(markup) {
      const node = { cloneNode: () => node, toString: () => markup };
      return { documentElement: node };
    }
  },
};
const runTimers = (n = 200) => { for (let i = 0; i < n && timers.length; i++) timers.shift().fn(); };

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const future = (min) => new Date(Date.now() + min * 60000).toISOString();

const CHILDREN = [
  { id: "malia", name: "Malia", points: 100, chore_order: [] },
  { id: "vaiha", name: "Vaiha", points: 12, chore_order: [] },
];

function hassWith(attrs, calls) {
  return {
    locale: { language: "en" },
    states: { [ENTITY]: { state: "ok", attributes: { children: CHILDREN, points_icon: "mdi:star", ...attrs } } },
    callService: async (domain, service, data) => calls.push({ domain, service, data }),
    callWS: async (msg) => {
      calls.push({ ws: msg });
      if (msg.type === "taskmate/kiosk/status") {
        return { children: CHILDREN.map(c => ({ id: c.id, has_pin: false, can_act: true, due: ["dishes"] })) };
      }
      if (msg.type === "auth/sign_path") return { path: `${msg.path}?authSig=x` };
      return {};
    },
  };
}

// ── Raffle card ───────────────────────────────────────────────────────────

const raffleMod = loadCard("taskmate-raffle-card.js", { sandbox });
const RaffleCard = raffleMod.get("taskmate-raffle-card");

const OPEN = { id: "r1", name: "Cinema raffle", prize: "Cinema trip", icon: "mdi:ticket", cost: 5, draw_at: future(120), status: "open", tickets: { malia: 3, vaiha: 1 }, total: 4, max: 6 };

function raffleCard(config = {}, raffles = [OPEN]) {
  const calls = [];
  const card = new RaffleCard();
  card.setConfig({ entity: ENTITY, ...config });
  card.hass = hassWith({ raffles }, calls);
  return { card, calls };
}

for (const design of DESIGNS) {
  test(`raffle: ${design} shows the raffle, tickets and your chance`, () => {
    const { card } = raffleCard({ child_id: "malia", card_design: design });
    const { markup } = render(card.render());
    assert.match(markup, /Cinema raffle/);
    assert.ok(markup.includes(localize("raffle.your_tickets", { count: 3, chance: 75 })));
    assert.ok(markup.includes(localize("raffle.buy", { count: 1, cost: 5 })));
  });
}

test("raffle: buying calls the service for the card's child", async () => {
  const { card, calls } = raffleCard({ child_id: "malia" });
  card._setQty(OPEN, 2, CHILDREN[0]);
  await card._buy(OPEN, CHILDREN[0]);
  assert.equal(calls[0].service, "buy_raffle_tickets");
  assert.equal(calls[0].data.tickets, 2);
  assert.equal(calls[0].data.child_id, "malia");
});

test("raffle: the cap and the balance limit what can be bought", () => {
  const { card } = raffleCard({ child_id: "malia" });
  assert.equal(card._maxBuy(OPEN, CHILDREN[0]), 3, "6 cap minus 3 held");
  assert.equal(card._maxBuy(OPEN, CHILDREN[1]), 2, "12 points buys two 5-point tickets");
  const broke = { ...CHILDREN[1], points: 4 };
  assert.equal(card._maxBuy(OPEN, broke), 0);
});

test("raffle: the family view has no buy controls", () => {
  const { card } = raffleCard({});
  const { markup } = render(card.render());
  assert.match(markup, /Cinema raffle/);
  assert.ok(!markup.includes("rf-buy"));
});

test("raffle: a fresh draw spins to the winner, once per browser, and survives a re-attach", () => {
  store.clear();
  timers.length = 0;
  const drawn = { ...OPEN, status: "drawn", winner_id: "vaiha", drawn_at: new Date().toISOString() };
  const { card } = raffleCard({ child_id: "vaiha" }, [drawn]);
  card._maybeReveal();
  assert.ok(card._reveal && !card._reveal.done);
  // HA re-attaching the card mid-spin cancelled the timer before the fix.
  card.disconnectedCallback();
  card.connectedCallback();
  runTimers();
  assert.equal(card._reveal.done, true);
  assert.equal(card._reveal.shown, "vaiha");
  assert.ok(render(card._renderReveal()).markup.includes(localize("raffle.you_won")));
  const again = raffleCard({ child_id: "vaiha" }, [drawn]).card;
  again._maybeReveal();
  assert.equal(again._reveal, null, "already seen in this browser");
});

// ── Pet card ──────────────────────────────────────────────────────────────

const petMod = loadCard("taskmate-pet-card.js", { sandbox });
const PetCard = petMod.get("taskmate-pet-card");

function petCard(pet, design = "classic") {
  const calls = [];
  const card = new PetCard();
  card.setConfig({ entity: ENTITY, child_id: "vaiha", card_design: design });
  const kids = CHILDREN.map(c => (c.id === "vaiha" ? { ...c, ...(pet === undefined ? {} : { pet }) } : c));
  card.hass = hassWith({}, calls);
  card.hass.states[ENTITY].attributes.children = kids;
  return { card, calls };
}

test("pet: tells the child when pets are off", () => {
  const { markup } = render(petCard(undefined).card.render());
  assert.ok(markup.includes(localize("pet.off")));
});

test("pet: the adoption form adopts the picked creature", async () => {
  const { card, calls } = petCard({ adopted: false });
  assert.ok(render(card.render()).markup.includes(localize("pet.adopt_question", { name: "Vaiha" })));
  card._species = "unicorn";
  card.updateComplete = Promise.resolve();
  card.renderRoot = { querySelector: () => ({ value: "Sparkle" }) };
  await card._adopt(card._child());
  assert.equal(calls[0].service, "adopt_pet");
  assert.equal(calls[0].data.species, "unicorn");
  assert.equal(calls[0].data.name, "Sparkle");
});

for (const design of DESIGNS) {
  test(`pet: ${design} draws the pet, its mood and how close the next stage is`, () => {
    const pet = { adopted: true, name: "Sparkle", species: "unicorn", stage: "baby", chores: 5, xp: 115, goal: { kind: "stage", from: 30, at: 200 }, mood: "sleepy", accessories: ["bow"] };
    const { markup } = render(petCard(pet, design).card.render());
    assert.match(markup, /<svg[^>]*tm-pet-scene/);
    assert.ok(markup.includes(localize("pet.mood_sleepy", { name: "Sparkle" })));
    const stage = localize("pet.stage_kid", { species: localize("pet.species_unicorn") });
    assert.ok(markup.includes(localize("pet.goal_stage", { percent: 50, stage })));
    assert.match(markup, /aria-valuenow="50"/);
    assert.match(markup, /💤/);
    assert.match(markup, /🎀/);
  });
}

test("pet: an egg is an egg, a grown pet with nothing switched on says so", () => {
  const egg = render(petCard({ adopted: true, name: "E", species: "cat", stage: "egg", chores: 0, xp: 0, goal: { kind: "stage", from: 0, at: 30 }, mood: "happy", accessories: [] }).card.render()).markup;
  assert.match(egg, /tm-egg-cat/);
  const grown = render(petCard({ adopted: true, name: "G", species: "dog", stage: "grown", chores: 120, xp: 1700, mood: "proud", accessories: ["bow", "top_hat", "scarf", "crown"] }).card.render()).markup;
  assert.ok(grown.includes(localize("pet.fully_grown", { name: "G" })));
  assert.match(grown, /👑/);
  assert.doesNotMatch(grown, /role="progressbar"/);
});

test("pet: each stage looks different, and legendary turns it gold", () => {
  const art = petMod.window ? petMod.window.__taskmate_pet_art : sandbox.window?.__taskmate_pet_art;
  const { petArt } = art || {};
  assert.ok(petArt, "art helpers exposed");
  const looks = ["baby", "kid", "teen", "grown"].map(st => petArt("dragon", st));
  assert.equal(new Set(looks).size, 4);
  assert.match(petArt("dragon", "grown", true), /#f6c445/);
  assert.doesNotMatch(petArt("dragon", "grown"), /#f6c445/);
});

test("pet: after fully grown — home items, legendary, level and the goal", () => {
  const pet = { adopted: true, name: "Rex", species: "dino", stage: "grown", chores: 150, xp: 2200, legendary: true, home: 3, pet_level: 4,
    goal: { kind: "home", from: 2100, at: 2400 }, mood: "happy", accessories: [] };
  const { markup } = render(petCard(pet).card.render());
  assert.ok(markup.includes(localize("pet.stage_legendary", { species: localize("pet.species_dino") })));
  assert.ok(markup.includes(localize("pet.level", { level: 4 })));
  assert.ok(markup.includes(localize("pet.goal_home", { percent: 33, name: "Rex" })));
  assert.match(markup, /class="pt-stage has-home/);
  assert.match(markup, /#8fd16a/, "grass, the first home item, is drawn");
  assert.doesNotMatch(markup, /#e86f5a/, "the house (item 10) is not yet");
});

test("pet: an egg to hatch — the child picks the next pet and the old one joins the family", async () => {
  const pet = { adopted: true, name: "Sparky", species: "dragon", stage: "grown", chores: 200, xp: 3100, legendary: true, egg_ready: true,
    mood: "happy", accessories: [], family: [{ species: "cat", name: "Mimi", legendary: true }] };
  const { card, calls } = petCard(pet);
  let markup = render(card.render()).markup;
  assert.ok(markup.includes(localize("pet.egg_ready", { name: "Sparky" })));
  assert.match(markup, /tm-new-egg/);
  assert.ok(markup.includes(localize("pet.family_title")));
  assert.match(markup, /Mimi/);
  card._hatching = true;
  markup = render(card.render()).markup;
  assert.ok(markup.includes(localize("pet.hatch_question", { name: "Vaiha" })));
  card._species = "bunny";
  card.renderRoot = { querySelector: () => ({ value: "Hop" }) };
  await card._adopt(card._child(), true);
  assert.equal(JSON.stringify(calls[0].data), JSON.stringify({ child_id: "vaiha", species: "bunny", name: "Hop", hatch_egg: true }));
});

test("pet: growing up plays once on this device; the first look is quiet", () => {
  store.clear();
  const base = { adopted: true, name: "Sparky", species: "dragon", chores: 2, xp: 20, mood: "happy", accessories: [] };
  const { card } = petCard({ ...base, stage: "egg" });
  card._checkEvolve({ ...base, stage: "egg" });
  assert.equal(card._evolving, "");
  card._checkEvolve({ ...base, stage: "baby" });
  assert.equal(card._evolving, "stage");
  assert.ok(render(card.render()).markup.includes(localize("pet.evolve_stage", { name: "Sparky" })));
  card._evolving = "";
  card._checkEvolve({ ...base, stage: "baby" });
  assert.equal(card._evolving, "", "already seen");
  card._checkEvolve({ ...base, stage: "grown", legendary: true });
  assert.equal(card._evolving, "stage");
});

// ── Kiosk ─────────────────────────────────────────────────────────────────

const kioskMod = loadCard("taskmate-kiosk-card.js", { sandbox });
const KioskCard = kioskMod.get("taskmate-kiosk-card");

async function kiosk(config = {}, attrs = {}) {
  const calls = [];
  const card = new KioskCard();
  card.setConfig({ entity: ENTITY, ...config });
  card.hass = hassWith({ chores: [{ id: "dishes", name: "Dishes", points: 10, assigned_to: [] }], todays_completions: [], ...attrs }, calls);
  await card._refreshStatus();
  card.calls = calls;
  return card;
}

test("kiosk: ambient mode takes over after the picker sits idle, and a tap only wakes it", async () => {
  const card = await kiosk({ ambient_mode: "progress", ambient_after: 30 }, { raffles: [OPEN] });
  for (let i = 0; i < 29; i++) card._tick();
  assert.equal(card._ambient, false);
  card._tick();
  assert.equal(card._ambient, true);
  const { markup } = render(card.render());
  assert.ok(markup.includes(localize("kiosk.ambient_wake")));
  assert.match(markup, /Cinema raffle/);
  const ev = { stopPropagation() { this.stopped = true; }, preventDefault() {} };
  card._onActivity(ev);
  assert.equal(card._ambient, false);
  assert.equal(ev.stopped, true);
  const click = { stopPropagation() { this.stopped = true; }, preventDefault() {} };
  card._onClickCapture(click);
  assert.equal(click.stopped, true, "the click after a waking tap doesn't open a face");
});

test("kiosk: ambient mode is off unless asked for", async () => {
  const card = await kiosk();
  for (let i = 0; i < 400; i++) card._tick();
  assert.equal(card._ambient, false);
});

test("kiosk: photo ambient signs our own photos and shows one", async () => {
  const card = await kiosk({ ambient_mode: "photos", ambient_after: 30 }, {
    photo_gallery: [{ photo_url: "/api/taskmate/photo/a.jpg", child_name: "Malia", chore_name: "Bed" }, { photo_url: "https://evil.example/x.jpg" }],
  });
  card._ambient = true;
  card._ambientPhotos();
  await new Promise(r => setImmediate(r));
  const { markup } = render(card.render());
  assert.match(markup, /\/api\/taskmate\/photo\/a\.jpg\?authSig=x/);
  assert.ok(!markup.includes("evil.example"));
});

test("kiosk: a tap while offline is kept, shown as waiting, and sent when back online", async () => {
  kioskMod.window.__taskmate_kiosk_queue = [];
  const card = await kiosk();
  card._queue = [];
  card._screen = "child";
  card._kid = "malia";
  card.hass.connection = { connected: false };
  card._cheer = () => {};
  await card._complete(CHILDREN[0], { id: "dishes", name: "Dishes" });
  assert.equal(card.calls.filter(c => c.service).length, 0);
  assert.equal(card._queue.length, 1);
  assert.equal(kioskMod.window.__taskmate_kiosk_queue.length, 1, "kept on the page, not in browser storage");
  assert.ok(render(card.render()).markup.includes(localize("kiosk.queue_waiting", { count: 1 })));
  card.hass.connection = { connected: true };
  await card._flushQueue();
  const sent = card.calls.filter(c => c.service === "complete_chore");
  assert.equal(sent.length, 1);
  assert.equal(sent[0].data.child_id, "malia");
  assert.equal(card._queue.length, 0);
});

test("kiosk: a call that dies with the connection is queued, not lost", async () => {
  const card = await kiosk();
  card._queue = [];
  card._cheer = () => {};
  card.hass.callService = async () => { const e = new Error("Connection lost"); e.code = 3; throw e; };
  await card._complete(CHILDREN[0], { id: "dishes", name: "Dishes" });
  assert.equal(card._queue.length, 1);
});

test("kiosk: a raffle draw spins on the tablet once", async () => {
  kioskMod.window.__taskmate_kiosk_raffle_seen = [];
  timers.length = 0;
  const drawn = { ...OPEN, status: "drawn", winner_id: "malia", drawn_at: new Date().toISOString() };
  const card = await kiosk({}, { raffles: [drawn] });
  card._maybeRaffleReveal(card._attrs());
  runTimers();
  assert.equal(card._rafReveal.done, true);
  assert.ok(render(card.render()).markup.includes(localize("kiosk.raffle_winner", { name: "Malia" })));
  card._rafReveal = null;
  card._maybeRaffleReveal(card._attrs());
  assert.equal(card._rafReveal, null);
});
