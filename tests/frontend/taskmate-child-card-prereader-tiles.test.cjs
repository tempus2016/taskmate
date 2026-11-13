"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

// Pre-reader tiles: the picture a chore gets when it has none, the padlock on
// a locked tile and the undo cue on a done one. Plus the keyword guess itself,
// which the designed rows share: ordering bugs ("Feed the cat" drew a dog,
// "wash the car" drew dishes) and coverage for every shipped locale.

const ALIAS = { graphite: "cleanpro" };
let parent = false;
const { get } = loadCard("taskmate-child-card.js", {
  window: {
    __taskmate_badge_id: (b) => b.badge_id,
    __taskmate_is_parent: () => parent,
    __taskmate_design: {
      apply: (_card, _hass, config) => {
        const d = config?.card_design || "classic";
        return ALIAS[d] || d;
      },
      styles: () => null,
      editorOptions: () => [],
    },
  },
});
const ChildCard = get("taskmate-child-card");

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];

function chore(extra = {}) {
  return {
    id: "zz",
    name: "ZZ chore",
    points: 5,
    time_category: "anytime",
    assigned_to: [],
    due_days: [],
    schedule_mode: "specific_days",
    daily_limit: 1,
    ...extra,
  };
}

function makeCard({ chores, completions = [], config = {}, design = "classic" }) {
  const card = new ChildCard();
  card.config = { entity: ENTITY, child_id: "kid1", card_design: design, pre_reader: true, ...config };
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", chore_order: [], weekly_chore_progress: {} }],
          chores,
          todays_completions: completions,
          chore_availability: {},
          today_day_of_week: "wednesday",
        },
      },
    },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  return card;
}

/** The markup of the tile whose aria-label is `name`. */
function tileMarkup(markup, name) {
  const start = markup.indexOf(`aria-label="${name}"`);
  assert.ok(start > 0, `tile "${name}" should be rendered`);
  return markup.slice(start, markup.indexOf("</button>", start));
}

const guess = (name) => ChildCard.prototype._choreEmoji.call(ChildCard.prototype, { name });

test("guesser: specific categories beat the catch-alls", () => {
  assert.equal(guess("Feed the cat"), "🐱");
  assert.equal(guess("Feed the dog"), "🐶");
  assert.equal(guess("Car wash"), "🚗");
  assert.equal(guess("Wash the car"), "🚗");
  assert.equal(guess("Wash the dishes"), "🍽️");
  assert.equal(guess("Wash clothes"), "🧺");
  assert.equal(guess("Bins"), "🗑️");
  assert.equal(guess("Plants"), "🪴");
});

test("guesser: whole words, so 'card' and 'bedroom' aren't a car and a bed", () => {
  assert.equal(guess("Make a birthday card"), "⭐");
  assert.equal(guess("Tidy bedroom"), "🧹");
  assert.equal(guess("Something new"), "⭐");
});

test("guesser: matches case- and accent-insensitively in every shipped locale", () => {
  const cases = {
    de: [["Zähne putzen", "🪥"], ["Katze füttern", "🐱"], ["Müll rausbringen", "🗑️"], ["AUTO WASCHEN", "🚗"], ["Staubsaugen", "🧽"], ["Wäsche falten", "🧺"]],
    fr: [["Brosser les dents", "🪥"], ["Nourrir le chat", "🐱"], ["Laver la voiture", "🚗"], ["Faire la vaisselle", "🍽️"], ["Arroser les plantes", "🪴"], ["Sortir les poubelles", "🗑️"]],
    nl: [["Tanden poetsen", "🪥"], ["Kat voeren", "🐱"], ["Afwassen", "🍽️"], ["Auto wassen", "🚗"], ["Stofzuigen", "🧽"], ["Huiswerk maken", "📚"]],
    da: [["Børste tænder", "🪥"], ["Fodre katten", "🐱"], ["Tage opvasken", "🍽️"], ["Støvsuge", "🧽"], ["Rydde op", "🧹"], ["Gå ud med skraldet", "🗑️"]],
    nb: [["Pusse tennene", "🪥"], ["Mate katten", "🐱"], ["Støvsuge stua", "🧽"], ["Ta ut søppel", "🗑️"], ["Vaske bilen", "🚗"], ["Re opp senga", "🛏️"]],
    nn: [["Pusse tennene", "🪥"], ["Mata hunden", "🐶"], ["Rydde rommet", "🧹"], ["Vatne blomstrane", "🪴"]],
    pl: [["Umyć zęby", "🪥"], ["Nakarmić kota", "🐱"], ["Ścielić łóżko", "🛏️"], ["Wynieść śmieci", "🗑️"], ["Odkurzanie", "🧽"], ["Umyć samochód", "🚗"]],
    pt: [["Escovar os dentes", "🪥"], ["Dar comida ao gato", "🐱"], ["Lavar a loiça", "🍽️"], ["Lavar o carro", "🚗"], ["Tirar o lixo", "🗑️"], ["Regar as plantas", "🪴"]],
    "pt-BR": [["Escovar os dentes", "🪥"], ["Alimentar o cachorro", "🐶"], ["Lavar a louça", "🍽️"], ["Arrumar a cama", "🛏️"], ["Lição de casa", "📚"], ["Passar o aspirador", "🧽"]],
  };
  for (const [lang, list] of Object.entries(cases)) {
    for (const [name, emoji] of list) assert.equal(guess(name), emoji, `${lang}: "${name}"`);
  }
});

for (const design of DESIGNS) {
  test(`pre-reader ${design}: a chore with no picture gets the row's guess, not a clock`, () => {
    const card = makeCard({
      design,
      chores: [chore({ id: "a", name: "Bins" }), chore({ id: "b", name: "Plants" }), chore({ id: "c", name: "Mystery" })],
    });
    const { markup } = render(card.render());
    assert.match(tileMarkup(markup, "Bins"), /pre-tile-emoji[^>]*>🗑️/);
    assert.match(tileMarkup(markup, "Plants"), /pre-tile-emoji[^>]*>🪴/);
    // Nothing guessable: the time-of-day icon is still the last resort.
    assert.match(tileMarkup(markup, "Mystery"), /icon="mdi:clock-outline"/);
    assert.doesNotMatch(tileMarkup(markup, "Mystery"), /pre-tile-emoji/);
  });

  test(`pre-reader ${design}: an explicit icon still wins over the guess`, () => {
    const card = makeCard({ design, chores: [chore({ name: "Bins", icon: "mdi:delete-variant" })] });
    const t = tileMarkup(render(card.render()).markup, "Bins");
    assert.match(t, /icon="mdi:delete-variant"/);
    assert.doesNotMatch(t, /pre-tile-emoji/);
  });

  test(`pre-reader ${design}: a locked tile shows a padlock`, () => {
    const card = makeCard({ design, chores: [chore({ time_category: "evening" })], config: { debug_time_period: "morning" } });
    const t = tileMarkup(render(card.render()).markup, "ZZ chore");
    assert.match(t, /pre-tile-badge lock/);
    assert.match(t, /mdi:lock/);
  });

  test(`pre-reader ${design}: an open tile has no badge`, () => {
    const card = makeCard({ design, chores: [chore()] });
    assert.doesNotMatch(tileMarkup(render(card.render()).markup, "ZZ chore"), /pre-tile-badge/);
  });

  test(`pre-reader ${design}: a done tile shows the undo cue only when a tap will undo`, () => {
    const now = Date.now();
    const done = (extra) => [{ chore_id: "zz", child_id: "kid1", completion_id: "c1", approved: true, completed_at: new Date(now).toISOString(), ...extra }];
    const cue = (completions, isParent) => {
      parent = isParent;
      try {
        const t = tileMarkup(render(makeCard({ design, chores: [chore()], completions }).render()).markup, "ZZ chore");
        assert.match(t, /pre-tile-tick/, "a done tile keeps its tick");
        return /pre-tile-badge undo/.test(t);
      } finally {
        parent = false;
      }
    };
    assert.equal(cue(done({ child_undo_until: new Date(now + 60_000).toISOString() }), false), true, "child inside the undo window");
    assert.equal(cue(done({ child_undo_until: new Date(now - 60_000).toISOString() }), false), false, "child after the window closed");
    assert.equal(cue(done({}), true), true, "parent");
  });
}
