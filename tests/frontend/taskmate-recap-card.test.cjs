// Recap card (#929): tap-through story slides of a finished period.
//
// The card has one story body shared by every design; only the header shell
// differs. Rendering every design here guards the recurring "works on classic,
// missing elsewhere" bug.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];

const hass = {
  language: "en",
  states: {
    [ENTITY]: {
      state: "ok",
      attributes: {
        children: [{ id: "kid1", name: "Malia", avatar: "mdi:account" }],
        points_name: "Stars",
        points_icon: "mdi:star",
      },
    },
  },
};

const RECAP = {
  id: "r1",
  child_id: "kid1",
  frequency: "monthly",
  start: "2026-08-01",
  end: "2026-08-31",
  created_at: new Date().toISOString(),
  week_start: 0,
  chores: 64,
  points: 820,
  chore_points: 740,
  bonus_points: 80,
  days_active: 26,
  days: 31,
  bars: [["2026-08-01", 14], ["2026-08-08", 17], ["2026-08-15", 15], ["2026-08-22", 18], ["2026-08-29", 0]],
  dow: [8, 9, 7, 10, 9, 14, 7],
  top_chore: { name: "Feed the cat", icon: "mdi:cat", count: 28 },
  streak: { days: 12, start: "2026-08-03", end: "2026-08-14" },
  best_day: { date: "2026-08-16", chores: 7, points: 95 },
  badges: [{ name: "Early Bird", icon: "mdi:weather-sunset-up" }],
  rewards: [{ name: "Cinema trip", cost: 300, icon: "mdi:movie" }],
  previous: { start: "2026-07-01", end: "2026-07-31", chores: 52, points: 680, streak: 8, days_active: 28 },
};

const Card = loadCard("taskmate-recap-card.js").get("taskmate-recap-card");

function makeCard(design, recap = RECAP) {
  const card = new Card();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design });
  card.hass = hass;
  card._list = { recaps: [{ id: recap.id, frequency: recap.frequency, start: recap.start, end: recap.end, created_at: recap.created_at, chores: recap.chores, points: recap.points }], upcoming: [] };
  card._recap = recap;
  return card;
}

for (const design of DESIGNS) {
  test(`recap card — ${design} renders the full-colour header and the story`, () => {
    const view = render(makeCard(design).render());
    assert.ok(view.markup.includes('class="story"'), "the story is drawn");
    assert.ok(view.markup.includes("--hd:#9b59b6"), "the header colour reaches the card");
    if (design === "classic") assert.ok(view.markup.includes('class="card-header"'));
    else assert.ok(view.markup.includes('class="tmd-hd"'));
    assert.ok(view.control(localize("recap.older")), "Older opens the list of recaps");
  });

  test(`recap card — ${design} walks every slide to the finale`, async () => {
    const card = makeCard(design);
    const seen = [];
    for (let i = 0; i < 12; i++) {
      const view = render(card.render());
      seen.push(view.all(/class="story" data-k="(\w+)"/g)[0][0]);
      const next = view.controls.find((c) => c.attrs.includes('class="tapzone next"'));
      await next.click();
    }
    assert.deepEqual([...new Set(seen)], ["intro", "chores", "points", "top", "streak", "best", "badges", "cmp", "fin"]);
    const finale = render(card.render());
    assert.ok(finale.control(localize("recap.save_image")), "the finale offers Save as image");
    assert.ok(finale.markup.includes("Feed the cat"));
  });
}

test("recap card — empty slides are skipped", () => {
  const card = makeCard("classic", { ...RECAP, top_chore: null, badges: [], rewards: [], previous: null, points: 0 });
  assert.deepEqual([...card._slides(card._recap)], ["intro", "chores", "streak", "best", "fin"]);
});

test("recap card — both header shells share one story body", () => {
  const src = require("node:fs").readFileSync(require("node:path").join(__dirname, "../../custom_components/taskmate/www/taskmate-recap-card.js"), "utf8");
  const renderFn = src.slice(src.indexOf("  render() {"), src.indexOf("  _title() {"));
  assert.equal((renderFn.match(/\$\{body\}/g) || []).length, 2, "classic and designed both render the shared body");
});

test("recap card — no child picked asks for one instead of throwing", () => {
  const card = new Card();
  card.setConfig({ entity: ENTITY });
  card.hass = hass;
  assert.ok(render(card.render()).markup.includes(localize("recap.choose_child")));
});

test("recap card — the older sheet lists recaps and the next one", async () => {
  const card = makeCard("classic");
  card._list.upcoming = [{ frequency: "monthly", start: "2026-09-01", end: "2026-09-30", ready_on: "2026-10-01" }];
  await render(card.render()).control(localize("recap.older")).click();
  const view = render(card.render());
  assert.ok(view.markup.includes('class="sheet"'));
  assert.ok(view.markup.includes("Ready on"), "the next recap is shown locked");
});
