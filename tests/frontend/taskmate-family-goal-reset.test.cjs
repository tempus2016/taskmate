const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, localize, render } = require("./harness.cjs");

// #1282: parents can start the Family Goal again at 0 from the card.

const ENTITY = "sensor.taskmate_overview";

function card({ parent = true, config = {}, confirmed = true, fail = null } = {}) {
  const loaded = loadCard("taskmate-family-goal-card.js", {
    editor: false,
    window: { __taskmate_is_parent: () => parent, confirm: () => confirmed },
  });
  const el = new (loaded.get("taskmate-family-goal-card"))();
  const calls = [];
  el.hass = {
    language: "en",
    states: {
      [ENTITY]: {
        attributes: { family_goal: { enabled: true, name: "Movie night", target: 500, progress: 50, reward: "popcorn" } },
      },
    },
    callService: async (domain, service, data) => {
      calls.push([domain, service, data]);
      if (fail && service === "reset_family_goal") throw new Error(fail);
    },
  };
  el.setConfig({ entity: ENTITY, ...config });
  return { el, calls };
}

test("a parent sees the Start again button", () => {
  const { el } = card();
  const button = render(el.render()).control("fg-reset");
  assert.ok(button, "no reset button");
  assert.match(button.text, new RegExp(localize("family_goal.reset")));
});

test("a child never sees the button", () => {
  const { el } = card({ parent: false });
  assert.equal(render(el.render()).control("fg-reset"), undefined);
});

test("show_parent_actions: false hides it for parents too", () => {
  const { el } = card({ config: { show_parent_actions: false } });
  assert.equal(render(el.render()).control("fg-reset"), undefined);
});

test("confirming calls taskmate.reset_family_goal", async () => {
  const { el, calls } = card();
  await render(el.render()).control("fg-reset").click();
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [["taskmate", "reset_family_goal", {}]]);
  assert.equal(el._resetting, false);
});

test("cancelling the confirmation does nothing", async () => {
  const { el, calls } = card({ confirmed: false });
  await render(el.render()).control("fg-reset").click();
  assert.deepEqual(calls, []);
});

test("a failed reset is reported, not swallowed", async () => {
  const { el, calls } = card({ fail: "nope" });
  await render(el.render()).control("fg-reset").click();
  assert.equal(calls.length, 2);
  assert.equal(calls[1][0], "persistent_notification");
  assert.match(calls[1][2].message, /nope/);
  assert.equal(el._resetting, false);
});
