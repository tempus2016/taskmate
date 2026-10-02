// Companion sensors under ids other than the defaults (#1018).
//
// Since Home Assistant 2026.6 a new entity on a device with an area gets the
// area in front of its id, so the bounties sensor added in v6.0.0 came up as
// sensor.familie_taskmate_bounties on a family whose TaskMate device sits in
// "Familie" — and the bounty card, looking only for sensor.taskmate_bounties,
// showed an empty board. The overview now publishes the real ids.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

const OVERVIEW = "sensor.taskmate_overview";
const CHILDREN = [{ id: "k1", name: "Nils" }];
const BOUNTY = { id: "b1", title: "Rasen mähen", points: 50, icon: "mdi:mower", status: "open", claim_hours: 2 };

const resolver = loadCard("taskmate-attr-resolver.js", { sandbox: { queueMicrotask: () => {} } }).window;

function bountyCard(states) {
  const Card = loadCard("taskmate-bounty-card.js", {
    window: { __taskmate_attrs: resolver.__taskmate_attrs },
  }).get("taskmate-bounty-card");
  const card = new Card();
  card.setConfig({ entity: OVERVIEW, child_id: "k1" });
  card.hass = { states, callService: async () => {} };
  return render(card.render()).markup;
}

test("the bounty card finds an area-prefixed bounties sensor through the overview's map", () => {
  const text = bountyCard({
    [OVERVIEW]: {
      state: "1",
      attributes: { children: CHILDREN, companion_entities: { bounties: "sensor.familie_taskmate_bounties" } },
    },
    "sensor.familie_taskmate_bounties": { state: "1", attributes: { bounties: [BOUNTY] } },
  });
  assert.ok(text.includes("Rasen mähen"), text);
});

test("without the map the default ids still work", () => {
  const text = bountyCard({
    [OVERVIEW]: { state: "1", attributes: { children: CHILDREN } },
    "sensor.taskmate_bounties": { state: "1", attributes: { bounties: [BOUNTY] } },
  });
  assert.ok(text.includes("Rasen mähen"), text);
});

test("a renamed overview's map is still found", () => {
  const states = {
    "sensor.familie_taskmate_overview": {
      state: "1",
      attributes: { children: CHILDREN, companion_entities: { chores: "sensor.familie_taskmate_chores" } },
    },
    "sensor.familie_taskmate_chores": { state: "1", attributes: { chores: [{ id: "c1" }] } },
  };
  const attrs = resolver.__taskmate_attrs({ states }, "sensor.familie_taskmate_overview");
  assert.deepEqual(JSON.parse(JSON.stringify(attrs.chores)), [{ id: "c1" }]);
});

test("skip keys follow the role, not the id", () => {
  const states = {
    [OVERVIEW]: {
      state: "1",
      attributes: { companion_entities: { rewards: "sensor.x_rewards", pending_approvals: "sensor.x_approvals" } },
    },
    "sensor.x_rewards": { state: "1", attributes: { pending_reward_claims: [{ id: "r1" }] } },
    "sensor.x_approvals": { state: "1", attributes: { pending_reward_claims: 1 } },
  };
  const attrs = resolver.__taskmate_attrs({ states }, OVERVIEW);
  assert.ok(Array.isArray(attrs.pending_reward_claims), "the approvals count must not overwrite the claims list");
});

test("a moved companion counts as a relevant change", () => {
  const ov = { state: "1", attributes: { companion_entities: { bounties: "sensor.familie_taskmate_bounties" } } };
  const before = { states: { [OVERVIEW]: ov, "sensor.familie_taskmate_bounties": { state: "0", attributes: {} } } };
  const after = { states: { [OVERVIEW]: ov, "sensor.familie_taskmate_bounties": { state: "1", attributes: {} } } };
  assert.equal(resolver.__taskmate_hasChanged(before, after, OVERVIEW), true);
});

test("a child's badges sensor resolves by child id", () => {
  const badges = { state: "2", attributes: { earned: [] } };
  const states = {
    [OVERVIEW]: { state: "1", attributes: { companion_entities: {}, badge_entities: { k1: "sensor.familie_taskmate_nils_badges" } } },
    "sensor.familie_taskmate_nils_badges": badges,
  };
  assert.equal(resolver.__taskmate_badges_state({ states }, "k1"), badges);
  assert.equal(resolver.__taskmate_badges_state({ states }, "k2"), null);
});
