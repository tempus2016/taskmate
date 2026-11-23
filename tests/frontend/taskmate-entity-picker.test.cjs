const assert = require("node:assert/strict");
const { readFileSync, readdirSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const { WWW } = require("./harness.cjs");

// Every card editor's entity picker used { entity: { domain: "sensor" } }, so
// the overview sensor was mixed in with every sensor in the house. The shared
// selector in taskmate-design.js lists only TaskMate's sensors with the card's
// role and pre-fills the only one when the card has none.

const plain = (v) => JSON.parse(JSON.stringify(v));

function designWindow() {
  const window = { matchMedia: () => ({ matches: false }), localStorage: { getItem: () => null, setItem() {} } };
  const el = () => ({ style: {}, setAttribute() {}, appendChild() {} });
  class CustomEvent { constructor(type, init) { this.type = type; this.detail = init?.detail; this.bubbles = init?.bubbles; this.composed = init?.composed; } }
  vm.runInNewContext(readFileSync(path.join(WWW, "taskmate-design.js"), "utf8"), {
    window, CustomEvent, Promise,
    document: { documentElement: { getAttribute: () => "" }, getElementById: () => ({}), createElement: el, head: { appendChild() {} }, body: { appendChild() {} }, addEventListener() {} },
    customElements: { get: () => undefined },
  });
  return window;
}

const overview = { points_name: "Stars", children: [] };
const activity = { recent_completions: [], photo_gallery: [] };
function hass(states, platforms = {}) {
  return {
    states: Object.fromEntries(Object.entries(states).map(([id, attributes]) => [id, { entity_id: id, attributes }])),
    entities: Object.fromEntries(Object.keys(states).map((id) => [id, { entity_id: id, platform: platforms[id] || "taskmate" }])),
  };
}
const HOUSE = {
  "sensor.taskmate_overview": overview,
  "sensor.taskmate_activity": activity,
  "sensor.taskmate_alex_points": { points: 3 },
  "sensor.hallway_temperature": {},
};
function fakeEditor(h, config) {
  const sent = [];
  return { hass: h, config, sent, dispatchEvent: (e) => sent.push(e) };
}
const tick = () => new Promise((r) => setImmediate(r));

test("the picker lists only TaskMate sensors with the card's role", () => {
  const w = designWindow();
  const h = hass(HOUSE);
  assert.deepEqual(plain(w.__taskmate_entity_selector(fakeEditor(h, { entity: "sensor.taskmate_overview" }))), {
    entity: { filter: { integration: "taskmate", domain: "sensor" }, include_entities: ["sensor.taskmate_overview"] },
  });
  assert.deepEqual(plain(w.__taskmate_entity_selector(fakeEditor(h, { entity: "sensor.taskmate_activity" }), "activity")).entity.include_entities, ["sensor.taskmate_activity"]);
});

test("a look-alike sensor from another integration is left out", () => {
  const w = designWindow();
  const h = hass({ ...HOUSE, "sensor.other_overview": overview }, { "sensor.other_overview": "template" });
  assert.deepEqual(plain(w.__taskmate_entity_candidates(h)), ["sensor.taskmate_overview"]);
});

test("with no overview sensor the picker still filters to TaskMate", () => {
  const w = designWindow();
  const sel = plain(w.__taskmate_entity_selector(fakeEditor(hass({ "sensor.hallway_temperature": {} }), {})));
  assert.deepEqual(sel, { entity: { filter: { integration: "taskmate", domain: "sensor" } } });
});

test("the only overview sensor fills an empty or missing entity, once", async () => {
  const w = designWindow();
  const h = hass(HOUSE);
  for (const config of [{ type: "custom:taskmate-points-card" }, { type: "custom:taskmate-points-card", entity: "sensor.gone" }]) {
    const ed = fakeEditor(h, config);
    w.__taskmate_entity_selector(ed);
    w.__taskmate_entity_selector(ed);
    await tick();
    assert.equal(ed.sent.length, 1);
    assert.equal(ed.sent[0].type, "config-changed");
    assert.ok(ed.sent[0].bubbles && ed.sent[0].composed);
    assert.deepEqual(plain(ed.sent[0].detail.config), { type: "custom:taskmate-points-card", entity: "sensor.taskmate_overview" });
  }
});

test("no pre-fill when the entity is set and present, or when there are two candidates", async () => {
  const w = designWindow();
  const set = fakeEditor(hass(HOUSE), { entity: "sensor.taskmate_overview" });
  w.__taskmate_entity_selector(set);
  const two = fakeEditor(hass({ ...HOUSE, "sensor.taskmate_overview_2": overview }), {});
  const sel = plain(w.__taskmate_entity_selector(two));
  await tick();
  assert.equal(set.sent.length, 0);
  assert.equal(two.sent.length, 0);
  assert.deepEqual(sel.entity.include_entities, ["sensor.taskmate_overview", "sensor.taskmate_overview_2"]);
});

test("every card editor's entity field uses the shared selector", () => {
  const dir = path.join(WWW, "editors");
  const files = readdirSync(dir).filter((f) => f.endsWith("-editor.js"));
  assert.equal(files.length, 32);
  for (const f of files) {
    const src = readFileSync(path.join(dir, f), "utf8");
    const role = f === "taskmate-photo-gallery-card-editor.js" ? `, "activity"` : "";
    assert.match(src, new RegExp(`name: ["']entity["'],\\s*selector: window\\.__taskmate_entity_selector\\?\\.\\(this${role.replace(/[()]/g, "\\$&")}\\)`), `${f} has its own entity selector`);
  }
});
