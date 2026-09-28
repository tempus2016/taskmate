const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { loadCard, WWW } = require("./harness.cjs");

// Cards whose header falls back to a translated default title (#1010). Each
// used to bake the English default into its config, so the translation never
// showed and "Manage Points" appeared on German dashboards.
const CARDS = [
  { file: "taskmate-points-card.js", tag: "taskmate-points-card", legacy: "Manage Points", key: "points_card.default_title" },
  { file: "taskmate-approvals-card.js", tag: "taskmate-approvals-card", legacy: "Pending Approvals", key: "approvals.default_title" },
  { file: "taskmate-parent-dashboard-card.js", tag: "taskmate-parent-dashboard-card", legacy: "Parent Dashboard", key: "dashboard.default_title" },
  { file: "taskmate-reorder-card.js", tag: "taskmate-reorder-card", legacy: "Reorder Chores", key: "reorder.default_title" },
  { file: "taskmate-rewards-card.js", tag: "taskmate-rewards-card", legacy: "Rewards", key: "rewards.default_title" },
];

const BASE_CONFIG = { entity: "sensor.taskmate_overview", child_id: "kid1" };
const LOCALES = ["en", "en-GB", "da", "de", "fr", "nb", "nn", "pt", "pt-BR"];

for (const { file, tag, legacy, key } of CARDS) {
  const Card = loadCard(file).get(tag);

  test(`${tag}: no English title is filled in by default`, () => {
    const card = new Card();
    card.setConfig({ ...BASE_CONFIG });
    assert.ok(!card.config.title, `title: ${card.config.title}`);
  });

  test(`${tag}: a saved English default title is treated as unset`, () => {
    const card = new Card();
    card.setConfig({ ...BASE_CONFIG, title: legacy });
    assert.ok(!card.config.title, `title: ${card.config.title}`);
  });

  test(`${tag}: a custom title is kept`, () => {
    const card = new Card();
    card.setConfig({ ...BASE_CONFIG, title: "Our house" });
    assert.equal(card.config.title, "Our house");
  });

  test(`${tag}: the card picker stub doesn't save an English title`, () => {
    const stub = Card.getStubConfig ? Card.getStubConfig() : {};
    assert.ok(!stub.title, `stub title: ${stub.title}`);
  });

  test(`${tag}: the fallback title is translated in every locale`, () => {
    for (const locale of LOCALES) {
      const messages = JSON.parse(readFileSync(path.join(WWW, `locales/${locale}.json`), "utf8"));
      assert.ok(messages[key], `${locale} is missing ${key}`);
    }
  });
}
