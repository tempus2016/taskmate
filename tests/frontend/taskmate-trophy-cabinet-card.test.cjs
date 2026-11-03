const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { loadCard, render, localize, WWW } = require("./harness.cjs");

// The family trophy cabinet: season wins, personal bests, badges, finished
// quests, perfect weeks and legendary pets on shelves, newest first, with a
// New tag and a spotlight. Single layout, so every design renders the same
// template; the tests still run each one.

const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const ENTITY = "sensor.taskmate_overview";
const TODAY = "2026-11-02";
const plain = (value) => JSON.parse(JSON.stringify(value));

// The real adult filter, as the attribute resolver defines it.
const familyChildren = (children, config) => {
  const list = Array.isArray(children) ? children : [];
  if (!list.some((c) => c && c.is_adult) || (config && config.child_id)) return list;
  const kids = list.filter((c) => !c.is_adult);
  return config && config.show_adults === true ? kids.concat(list.filter((c) => c.is_adult)) : kids;
};

const BADGE_IDS = { m1: "sensor.kitchen_taskmate_malia_badges", v1: "sensor.kitchen_taskmate_vaiha_badges", dad: "sensor.taskmate_dad_badges" };

const Card = loadCard("taskmate-trophy-cabinet-card.js", {
  window: {
    __taskmate_family_children: familyChildren,
    __taskmate_badges_state: (hass, id) => hass.states[BADGE_IDS[id]] || null,
    __taskmate_badge_id: (b) => String(b.badge_id ?? b.id ?? ""),
  },
}).get("taskmate-trophy-cabinet-card");

function children() {
  return [
    {
      id: "m1", name: "Malia", color: "#e53935",
      personal_bests: {
        longest_streak: { value: 21, date: "2026-10-30" },
        best_day_points: { value: 40, date: "2026-09-01" },
        best_week_points: { value: 0, date: "" },
      },
      quests: [
        { quest_id: "q1", name: "Garden Rescue", icon: "mdi:flower", times_completed: 1, last_completed: "2026-09-14" },
        { quest_id: "q2", name: "Bedroom Blitz", icon: "mdi:bed", times_completed: 0 },
      ],
      awarded_perfect_weeks: ["2026-06-01", "2026-07-06", "2026-10-26"],
      pet: { adopted: true, species: "unicorn", name: "Sparkle", legendary: true, family: [{ species: "cat", name: "Tom", legendary: false }] },
    },
    {
      id: "v1", name: "Vaiha",
      personal_bests: { best_day_chores: { value: 9, date: "2026-08-03", previous: 7 }, new_today: ["best_day_chores"] },
      quests: [{ quest_id: "q1", name: "Garden Rescue", icon: "mdi:flower", times_completed: 2, last_completed: "2026-07-20" }],
      awarded_perfect_weeks: [],
    },
    {
      id: "dad", name: "Dad", is_adult: true,
      personal_bests: { longest_streak: { value: 99, date: "2026-11-01" } },
      quests: [{ quest_id: "q9", name: "Grown-up quest", times_completed: 1, last_completed: "2026-11-01" }],
      awarded_perfect_weeks: ["2026-10-26"],
    },
  ];
}

function hassFor({ kids = children(), champions, badges } = {}) {
  const states = {
    [ENTITY]: {
      entity_id: ENTITY,
      state: "ok",
      attributes: {
        points_name: "Stars",
        children: kids,
        season_champions: champions || [
          { month: "2026-10", child_id: "v1", child_name: "Vaiha", points: 312 },
          { month: "2026-08", child_id: "m1", child_name: "Malia", points: 280 },
          { month: "2026-09", child_id: "dad", child_name: "Dad", points: 999 },
        ],
      },
    },
  };
  const b = badges || {
    m1: [
      { badge_id: "b1", name: "Clean Machine", icon: "mdi:broom", tier: "gold", earned_at: "2026-10-31T09:00:00+00:00" },
      { badge_id: "b2", name: "Early Bird", icon: "🌅", tier: "bronze", earned_at: "2026-05-01T09:00:00+00:00" },
    ],
    v1: [{ badge_id: "b1", name: "Clean Machine", icon: "mdi:broom", tier: "gold", earned_at: "2026-06-01T09:00:00+00:00" }],
    dad: [{ badge_id: "b9", name: "Dad Badge", icon: "mdi:medal", earned_at: "2026-11-01T09:00:00+00:00" }],
  };
  for (const [kid, earned] of Object.entries(b)) {
    states[BADGE_IDS[kid]] = { entity_id: BADGE_IDS[kid], state: String(earned.length), attributes: { earned } };
  }
  return { states, language: "en", locale: { language: "en" } };
}

function card({ design = "classic", config = {}, hass = hassFor(), narrow = false } = {}) {
  const c = new Card();
  c.setConfig({ entity: ENTITY, card_design: design, ...config });
  c.hass = hass;
  c._today = () => TODAY;
  c._narrow = narrow;
  return c;
}

const shelvesOf = (c) => {
  const attrs = c._attrs();
  return c._collect(attrs, c._kids(attrs));
};
const byShelf = (c) => Object.fromEntries(shelvesOf(c).map((s) => [s.key, s.items]));

test("collects every default shelf in order, pets only when asked", () => {
  assert.deepEqual(plain(shelvesOf(card()).map((s) => s.key)), ["seasons", "bests", "badges", "quests", "perfect_weeks"]);
  const withPets = card({ config: { shelves: ["pets", "badges", "nonsense", "badges"] } });
  assert.deepEqual(plain(shelvesOf(withPets).map((s) => s.key)), ["pets", "badges"]);
});

test("grown-up profiles never reach a shelf", () => {
  const s = byShelf(card());
  const all = Object.values(s).flat();
  assert.ok(all.every((it) => !it.who.includes("dad")), "no trophy is credited to the adult");
  assert.ok(!s.seasons.some((it) => it.id === "season:2026-09"), "the adult's season win is left out");
  assert.ok(!s.badges.some((it) => it.name === "Dad Badge"));
  assert.ok(!s.quests.some((it) => it.name === "Grown-up quest"));
  const { markup } = render(card().render());
  assert.ok(!markup.includes("Dad"), "the adult's name is nowhere on the card");
});

test("a children filter narrows the cabinet to the picked child", () => {
  const s = byShelf(card({ config: { children: ["v1"] } }));
  assert.ok(Object.values(s).flat().every((it) => plain(it.who).every((id) => id === "v1")));
  assert.equal(s.perfect_weeks, undefined, "Vaiha has no perfect weeks, so that shelf is gone");
});

test("seasons are dated the day after the month ends and sorted newest first", () => {
  const { seasons } = byShelf(card());
  assert.deepEqual(plain(seasons.map((i) => [i.id, i.date])), [["season:2026-10", "2026-11-01"], ["season:2026-08", "2026-09-01"]]);
  assert.equal(seasons[0].fresh, true, "won yesterday");
  assert.equal(seasons[1].fresh, false);
  assert.equal(seasons[0].value, "312 Stars");
});

test("personal bests: one tile per held record, zero records skipped, today's beaten ones are New", () => {
  const { bests } = byShelf(card());
  assert.deepEqual(plain(bests.map((i) => i.id)), ["best:m1:longest_streak", "best:m1:best_day_points", "best:v1:best_day_chores"]);
  assert.equal(bests[0].fresh, true, "set 3 days ago, inside the 7-day window");
  assert.equal(bests[1].fresh, false);
  assert.equal(bests[2].fresh, true, "beaten today, whatever its date says");
  assert.equal(bests[0].value, localize("trophy.best_value_longest_streak", { value: 21 }));
});

test("badges group by badge, carry every child who has one and the newest date", () => {
  const { badges } = byShelf(card());
  const clean = badges.find((b) => b.name === "Clean Machine");
  assert.deepEqual(plain(clean.who).sort(), ["m1", "v1"]);
  assert.equal(clean.date, "2026-10-31");
  assert.equal(clean.family, true, "both children have it, so it is a whole-family trophy");
  assert.equal(badges[0].name, "Clean Machine", "newest first");
  const early = badges.find((b) => b.name === "Early Bird");
  assert.equal(early.family, false);
});

test("badges are read from the sensors in the overview's badge_entities map", () => {
  // The sensors are area-prefixed; a default-id guess would find nothing.
  const { badges } = byShelf(card());
  assert.equal(badges.length, 2);
});

test("quests: only finished ones, grouped, dated by the latest finish", () => {
  const { quests } = byShelf(card());
  assert.equal(quests.length, 1);
  assert.equal(quests[0].name, "Garden Rescue");
  assert.equal(quests[0].date, "2026-09-14");
  assert.equal(quests[0].value, "×2");
  assert.equal(quests[0].family, true);
});

test("perfect weeks: one tile per child with the count, dated by the latest week's Sunday", () => {
  const { perfect_weeks: pw } = byShelf(card());
  assert.equal(pw.length, 1);
  assert.equal(pw[0].name, localize("trophy.perfect_weeks", { count: 3 }));
  assert.equal(pw[0].date, "2026-11-01");
  assert.equal(pw[0].fresh, true);
});

test("a perfect week still running is dated today, not in the future", () => {
  const kids = children();
  kids[0].awarded_perfect_weeks = ["2026-11-02"];
  const { perfect_weeks: pw } = byShelf(card({ hass: hassFor({ kids }) }));
  assert.equal(pw[0].date, TODAY);
});

test("legendary pets: the current pet and legendary family only", () => {
  const { pets } = byShelf(card({ config: { shelves: ["pets"] } }));
  assert.deepEqual(plain(pets.map((p) => [p.name, p.emoji])), [["Sparkle", "🦄"]]);
});

test("new_days sets the New window and 0 turns it off", () => {
  const wide = byShelf(card({ config: { new_days: 70 } }));
  assert.equal(wide.seasons[1].fresh, true, "won 62 days ago, inside a 70-day window");
  const off = byShelf(card({ config: { new_days: 0 } }));
  assert.ok(Object.values(off).flat().every((i) => !i.fresh || i.id === "best:v1:best_day_chores"),
    "only a record beaten today keeps its tag");
});

test("the spotlight is the most recent dated trophy", () => {
  const c = card();
  const latest = c._latest(shelvesOf(c));
  assert.equal(latest.id, "season:2026-10");
});

for (const design of DESIGNS) {
  test(`${design}: header, spotlight, legend, shelves and New tags render`, () => {
    const { markup } = render(card({ design }).render());
    assert.ok(markup.includes(localize("trophy.default_title")));
    assert.ok(markup.includes(localize("trophy.latest")));
    assert.ok(markup.includes(localize("trophy.spot_season", { name: "Vaiha", season: "October 2026" })));
    for (const key of ["seasons", "bests", "badges", "quests", "perfect_weeks"]) {
      assert.ok(markup.includes(localize(`trophy.shelf_${key}`)), key);
    }
    assert.ok(markup.includes(localize("trophy.new_tag")));
    assert.ok(markup.includes(localize("trophy.whole_family")));
    assert.ok(markup.includes("Malia") && markup.includes("Vaiha"));
    assert.ok(markup.includes(localize("trophy.since", { date: "May 2026" })));
  });

  test(`${design}: narrow drops the spotlight and caps shelves at three tiles`, () => {
    const many = { m1: Array.from({ length: 6 }, (_, i) => ({ badge_id: `b${i}`, name: `Badge ${i}`, icon: "mdi:star", earned_at: "2026-01-0" + (i + 1) })) };
    const c = card({ design, narrow: true, hass: hassFor({ badges: many }) });
    const { markup } = render(c.render());
    assert.ok(!markup.includes(localize("trophy.latest")));
    assert.ok(markup.includes(localize("trophy.more", { count: 4 })), "2 badges + a '4 more' tile");
    assert.ok(markup.includes("Badge 5") && markup.includes("Badge 4") && !markup.includes("Badge 3"));
  });
}

test("a long shelf shows badges_per_shelf then a 'more' tile that expands it", () => {
  const many = { m1: Array.from({ length: 8 }, (_, i) => ({ badge_id: `b${i}`, name: `Badge ${i}`, icon: "mdi:star", earned_at: `2026-01-1${i}` })) };
  const c = card({ config: { badges_per_shelf: 3, shelves: ["badges"] }, hass: hassFor({ badges: many }) });
  const out = render(c.render());
  assert.ok(out.markup.includes(localize("trophy.more", { count: 5 })));
  assert.ok(!out.markup.includes("Badge 0"));
  const more = out.control(localize("trophy.more", { count: 5 }));
  assert.ok(more, "the more tile is a button");
  more.click();
  const open = render(c.render()).markup;
  assert.ok(open.includes("Badge 0"), "expanded shows everything");
  assert.ok(open.includes(localize("trophy.show_less")));
});

test("show_spotlight: false hides the spotlight on a wide card", () => {
  const { markup } = render(card({ config: { show_spotlight: false } }).render());
  assert.ok(!markup.includes(localize("trophy.latest")));
});

test("an empty cabinet says so in a friendly way", () => {
  const kids = [{ id: "m1", name: "Malia" }, { id: "v1", name: "Vaiha" }];
  const { markup } = render(card({ hass: hassFor({ kids, champions: [], badges: {} }) }).render());
  assert.ok(markup.includes(localize("trophy.empty_title")));
  assert.ok(markup.includes(localize("trophy.empty")));
});

test("only an adult's trophies is still an empty cabinet", () => {
  const kids = [children()[2], { id: "m1", name: "Malia" }];
  const { markup } = render(card({ hass: hassFor({ kids, champions: [], badges: { dad: [{ badge_id: "x", name: "Dad Badge", earned_at: "2026-11-01" }] } }) }).render());
  assert.ok(markup.includes(localize("trophy.empty_title")));
});

test("a missing overview entity shows the not-found message", () => {
  const c = card({ hass: { states: {} } });
  assert.ok(render(c.render()).markup.includes(localize("common.entity_not_found", { entity: ENTITY })));
});

test("stub config, required entity and the card registration", () => {
  assert.equal(Card.getStubConfig().entity, ENTITY);
  assert.throws(() => new Card().setConfig({}), /entity/i);
  const src = readFileSync(path.join(WWW, "taskmate-trophy-cabinet-card.js"), "utf8");
  assert.match(src, /type: "taskmate-trophy-cabinet-card"/);
  const fe = readFileSync(path.join(WWW, "../frontend.py"), "utf8");
  assert.match(fe, /"taskmate-trophy-cabinet-card\.js"/);
});

test("every trophy string is translated in every locale", () => {
  const en = JSON.parse(readFileSync(path.join(WWW, "locales/en.json"), "utf8"));
  const keys = Object.keys(en).filter((k) => k.startsWith("trophy."));
  assert.ok(keys.length > 30);
  for (const lang of ["da", "de", "fr", "nb", "nl", "nn", "pl", "pt", "pt-BR"]) {
    const loc = JSON.parse(readFileSync(path.join(WWW, `locales/${lang}.json`), "utf8"));
    const same = keys.filter((k) => loc[k] === en[k] && !/^\{|^Badges$|^New$|^Ny$/.test(en[k]));
    assert.ok(same.length <= 3, `${lang} copies English for ${same.join(", ")}`);
  }
});

test("a shelf only one over the limit is shown whole instead of swapping one trophy for a 'more' tile", () => {
  const six = { m1: Array.from({ length: 6 }, (_, i) => ({ badge_id: `b${i}`, name: `Badge ${i}`, icon: "mdi:star", earned_at: `2026-01-1${i}` })) };
  const { markup } = render(card({ config: { shelves: ["badges"] }, hass: hassFor({ badges: six }) }).render());
  for (let i = 0; i < 6; i++) assert.ok(markup.includes(`Badge ${i}`), `Badge ${i}`);
  assert.ok(!markup.includes(localize("trophy.more", { count: 1 })));
});

for (const design of DESIGNS) {
  test(`${design}: narrow tiles put each child's initial in the dot`, () => {
    const { markup } = render(card({ design, narrow: true }).render());
    // Names are dropped on a narrow card, so the dots carry who it is.
    assert.match(markup, /class="tc-dot tc-dot-mk"[^>]*>M<\/i>/);
    assert.match(markup, /class="tc-dot tc-dot-mk"[^>]*>V<\/i>/);
    assert.ok(markup.includes("mdi:account-group"), "the whole-family dot carries a group mark");
  });

  test(`${design}: wide tiles keep plain dots beside the names`, () => {
    const { markup } = render(card({ design }).render());
    assert.ok(!markup.includes("tc-dot-mk"));
  });
}

test("initials take two letters when two children share a first letter", () => {
  const c = card();
  const marks = c._initials([{ id: "a", name: "Malia" }, { id: "b", name: "Max" }, { id: "c", name: "vaiha" }]);
  assert.equal(marks.get("a"), "Ma");
  assert.equal(marks.get("b"), "Ma");
  assert.equal(marks.get("c"), "V");
});

test("the whole family is called 'Whole family' everywhere, never 'Everyone'", () => {
  const src = readFileSync(path.join(WWW, "taskmate-trophy-cabinet-card.js"), "utf8");
  assert.ok(!src.includes("trophy.everyone"));
  const en = JSON.parse(readFileSync(path.join(WWW, "locales/en.json"), "utf8"));
  assert.equal(en["trophy.everyone"], undefined);
  const c = card();
  const kids = c._kids(c._attrs());
  const fam = { family: true, who: kids.map((k) => String(k.id)) };
  assert.equal(c._whoNames(fam, new Map()), localize("trophy.whole_family"));
});

test("shelf headers are a 32px tap target", () => {
  const css = render(Card.styles).markup;
  assert.match(css, /\.tc-shelf-hd \{[^}]*min-height: 32px/);
});
