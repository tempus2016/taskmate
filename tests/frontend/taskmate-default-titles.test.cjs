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

// v7.7.1 recheck: eight more cards put an English title in the stub the card
// picker saves ("Activity", "Points Graph" …), so a new card on a German
// dashboard kept an English header. The stub leaves the title out; each card
// falls back to its own translated default.
const STUB_CARDS = [
  { file: "taskmate-activity-card.js", key: "activity.default_title" },
  { file: "taskmate-calendar-card.js", key: "calendar.default_title" },
  { file: "taskmate-graph-card.js", key: "graph.default_title" },
  { file: "taskmate-leaderboard-card.js", key: "leaderboard.default_title" },
  { file: "taskmate-overview-card.js", key: "overview.default_title" },
  { file: "taskmate-reward-progress-card.js", key: "reward_progress.default_title" },
  { file: "taskmate-streak-card.js", key: "streak.default_title" },
  { file: "taskmate-weekly-card.js", key: "weekly.default_title" },
];

for (const { file, key } of STUB_CARDS) {
  const tag = file.replace(/\.js$/, "");
  const Card = loadCard(file).get(tag);

  test(`${tag}: the card picker stub saves no title`, () => {
    const stub = Card.getStubConfig();
    assert.equal(stub.entity, "sensor.taskmate_overview");
    assert.ok(!("title" in stub), `stub title: ${stub.title}`);
  });

  test(`${tag}: with no title it shows a default that every locale translates`, () => {
    const src = readFileSync(path.join(WWW, file), "utf8");
    assert.ok(src.includes(key), `${file} falls back to ${key}`);
    for (const locale of [...LOCALES, "nl", "pl"]) {
      const messages = JSON.parse(readFileSync(path.join(WWW, `locales/${locale}.json`), "utf8"));
      assert.ok(messages[key], `${locale} is missing ${key}`);
    }
  });
}

// Cards added before v7.7.1 saved those English stub titles. Exactly the old
// stub string counts as unset (as #1010 did for five other cards), so the
// translated default shows; any other title, including a near miss, is kept.
const OLD_STUB_TITLES = {
  "taskmate-activity-card.js": "Activity",
  "taskmate-calendar-card.js": "Task Calendar",
  "taskmate-graph-card.js": "Points Graph",
  "taskmate-leaderboard-card.js": "Leaderboard",
  "taskmate-overview-card.js": "TaskMate",
  "taskmate-reward-progress-card.js": "Reward Goal",
  "taskmate-streak-card.js": "Streaks & Achievements",
  "taskmate-weekly-card.js": "This Week",
};

for (const [file, legacy] of Object.entries(OLD_STUB_TITLES)) {
  const tag = file.replace(/\.js$/, "");
  const Card = loadCard(file).get(tag);
  const make = (title) => {
    const card = new Card();
    card.setConfig({ ...BASE_CONFIG, ...(title === undefined ? {} : { title }) });
    return card.config.title;
  };

  test(`${tag}: a saved "${legacy}" from the old stub is treated as unset`, () => {
    assert.ok(!make(legacy), `title: ${make(legacy)}`);
  });

  test(`${tag}: the user's own title is kept, even one close to the old default`, () => {
    assert.equal(make("Our house"), "Our house");
    assert.equal(make(`${legacy} `), `${legacy} `);
    assert.equal(make(legacy.toLowerCase()), legacy.toLowerCase());
  });
}

test("overview: the old stub title falls back to the translated default, an empty title stays empty", () => {
  const Card = loadCard("taskmate-overview-card.js").get("taskmate-overview-card");
  const card = new Card();
  card.setConfig({ ...BASE_CONFIG, title: "TaskMate" });
  assert.equal(card.config.title, undefined);
  const blank = new Card();
  blank.setConfig({ ...BASE_CONFIG, title: "" });
  assert.equal(blank.config.title, "");
});

test("German streak default title no longer repeats itself", () => {
  const de = JSON.parse(readFileSync(path.join(WWW, "locales/de.json"), "utf8"));
  assert.equal(de["streak.default_title"], "Serien und Erfolge");
});
