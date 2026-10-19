const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// Appeals on the child card (every design) and the panel's Today page.

const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const ENTITY = "sensor.taskmate_overview";
const plain = (v) => JSON.parse(JSON.stringify(v));
const ITEM = { kind: "chore", target_id: "rej1", name: "Make bed", points: 5 };

function childCard({ design = "classic", child = {}, config = {} } = {}) {
  const ChildCard = loadCard("taskmate-child-card.js").get("taskmate-child-card");
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design, ...config });
  const calls = [];
  card.hass = {
    states: { [ENTITY]: { state: "ok", attributes: {
      children: [{ id: "kid1", name: "Mia", chore_order: [], ...child }], chores: [], todays_completions: [],
      chore_availability: {}, today_day_of_week: "wednesday", points_icon: "mdi:star",
    } } },
    callService: async (domain, service, data) => { calls.push({ domain, service, data }); },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card._playSound = () => {};
  card._spawnConfetti = () => {};
  return { card, calls };
}

for (const design of DESIGNS) {
  test(`child: ${design} offers an appeal and sends it with the message`, async () => {
    const { card, calls } = childCard({ design, child: { appealable: [ITEM] } });
    let out = render(card.render());
    assert.ok(out.markup.includes(localize("child.appeal_item_chore", { name: "Make bed", points: 5 })));
    await out.control(localize("child.appeal_button")).click();
    card._appealSheet.message = "I did make it!";
    out = render(card.render());
    await out.controls.find((c) => /photo-btn primary/.test(c.attrs)).click();
    assert.deepEqual(plain(calls), [{ domain: "taskmate", service: "appeal", data: { child_id: "kid1", kind: "chore", target_id: "rej1", message: "I did make it!" } }]);
  });

  test(`child: ${design} shows how an appeal went`, () => {
    const { card } = childCard({ design, child: { appeals: [{ id: "a1", kind: "chore", item_name: "Make bed", points: 5, status: "upheld", note: "Still messy" }] } });
    const { markup } = render(card.render());
    assert.ok(markup.includes(localize("child.appeal_upheld", { name: "Make bed" })));
    assert.ok(markup.includes("Still messy"));
  });
}

test("child: show_appeals false hides the lot", () => {
  const { card } = childCard({ child: { appealable: [ITEM] }, config: { show_appeals: false } });
  assert.ok(!render(card.render()).markup.includes(localize("child.appeal_button")));
});

test("panel: the Today appeals card offers uphold and the right overturn wording", () => {
  const TaskMatePanel = loadCard("taskmate-panel.js").get("taskmate-panel");
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => `${key}${Object.keys(params).length ? ":" + JSON.stringify(params) : ""}`;
  p._state = { children: [{ id: "kid1", name: "Mia" }], appeals: [
    { id: "a1", child_id: "kid1", child_name: "Mia", kind: "penalty", item_name: "Door", points: 5, message: "It was the wind", created_at: "2026-10-18T10:00:00Z" },
  ] };
  const html = p._renderAppealsCard([{ id: "kid1" }]);
  assert.match(html, /data-act="appeal-uphold" data-id="a1"/);
  assert.match(html, /data-act="appeal-overturn" data-id="a1">panel\.appeal_overturn_penalty/);
  assert.match(html, /It was the wind/);
  assert.equal(p._renderAppealsCard([{ id: "kid2" }]), "");
});
