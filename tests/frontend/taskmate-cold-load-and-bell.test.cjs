const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const ENTITY = "sensor.taskmate_overview";

// On a cold load a card can render before the attr resolver has defined
// window.__taskmate_badge_id. The badge tracking must not throw then.
test("badges card tracks earned badges before the attr resolver has loaded", () => {
  const Card = loadCard("taskmate-badges-card.js", { window: {} }).get("taskmate-badges-card");
  const card = new Card();
  card.setConfig({ entity: "sensor.kid_badges" });
  card.hass = { states: { "sensor.kid_badges": { state: "1", attributes: { earned: [{ badge_id: "b1", name: "First" }] } } } };
  card._seenBadgeIds = null;
  assert.doesNotThrow(() => card._trackEarnedBadges());
  assert.deepEqual([...card._seenBadgeIds], ["b1"]);
});

// A chore with no reminder shows a bare bell; one with a reminder shows the time.
test("child card: the reminder bell only shows text once a time is set", () => {
  const ChildCard = loadCard("taskmate-child-card.js").get("taskmate-child-card");
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1" });
  const chore = (id, name) => ({ id, name, points: 2, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", assignment_mode: "everyone" });
  card.hass = {
    states: { [ENTITY]: { state: "ok", attributes: {
      children: [{ id: "kid1", name: "Mia", chore_order: [], reminders: { homework: "17:30" } }],
      chores: [chore("bed", "Make bed"), chore("homework", "Homework")],
      chore_reminders: { earliest: "15:00", latest: "20:00" },
      todays_completions: [], chore_availability: {}, today_day_of_week: "wednesday", points_icon: "mdi:star",
    } } },
    callService: async () => {},
  };
  card._loading = {};
  card._optimisticCompletions = {};
  const { markup } = render(card.render());
  const bells = [...markup.matchAll(/tm-remind-btn[^>]*>([^<]*)</g)].map((m) => m[1].trim());
  assert.deepEqual(bells.sort(), ["🔔", "🔔 17:30"]);
  assert.ok(markup.includes(localize("child.reminder_title", { chore: "Make bed" })), "the bare bell keeps an accessible label");
});
