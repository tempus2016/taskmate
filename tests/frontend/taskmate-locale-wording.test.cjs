const assert = require("node:assert/strict");
const { readFileSync, readdirSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { loadCard, render, WWW } = require("./harness.cjs");

// #771 gate: the German Reorder card offered to "Bestellung speichern" (save
// the purchase order), showed points as a lower-case "punkte" instead of the
// family's points name, and the German parent dashboard called approvals
// "Zulassungen" (registrations) where the panel says "Genehmigungen".

const LOCALES = path.join(WWW, "locales");
const loc = (l) => JSON.parse(readFileSync(path.join(LOCALES, `${l}.json`), "utf8"));
const LANGS = readdirSync(LOCALES).filter((f) => f.endsWith(".json")).map((f) => f.slice(0, -5));

test("the reorder strings talk about a sequence, never a purchase order", () => {
  // Words for a shop order / commission / saving money, per language.
  const WRONG = { de: /bestell|auftrag|sparen/i, fr: /commande/i, nl: /bestelling/i, pl: /zamówieni/i, da: /bestilling/i, nb: /bestilling/i, nn: /bestilling/i, pt: /encomenda|pedido/i, "pt-BR": /encomenda|pedido/i };
  for (const lang of LANGS) {
    const d = loc(lang);
    for (const [k, v] of Object.entries(d)) {
      if (!k.startsWith("reorder.")) continue;
      if (WRONG[lang]) assert.doesNotMatch(v, WRONG[lang], `${lang} ${k}: "${v}"`);
    }
  }
  assert.equal(loc("de")["reorder.save_order"], "Reihenfolge speichern");
});

test("Brazilian Portuguese reorder strings are Brazilian, not European", () => {
  for (const [k, v] of Object.entries(loc("pt-BR"))) {
    if (k.startsWith("reorder.")) assert.doesNotMatch(v, /\bguardar|\bguardad|A guardar|\bgerir\b|\bTens\b|Arrasta\b/i, `pt-BR ${k}: "${v}"`);
  }
});

test("the parent dashboard's approvals tab uses the panel's word for approvals", () => {
  for (const lang of LANGS) {
    const d = loc(lang);
    const panelWord = d["panel.chore_table_approval"].toLowerCase().slice(0, 6);
    assert.ok(d["dashboard.tab_approvals"].toLowerCase().includes(panelWord.slice(0, 5)),
      `${lang}: "${d["dashboard.tab_approvals"]}" vs the panel's "${d["panel.chore_table_approval"]}"`);
  }
});

function reorderMarkup(design, pointsName) {
  const Card = loadCard("taskmate-reorder-card.js", {
    editor: false,
    window: { __taskmate_design: { apply: () => design, styles: () => null } },
  }).get("taskmate-reorder-card");
  const el = new Card();
  el.hass = {
    language: "en",
    states: {
      "sensor.taskmate_overview": {
        attributes: {
          ...(pointsName ? { points_name: pointsName } : {}),
          children: [{ id: "k1", name: "Malia" }],
          chores: [{ id: "c1", name: "Make bed", points: 2, time_category: "morning", assigned_to: ["k1"] }],
        },
      },
    },
  };
  el.setConfig({ entity: "sensor.taskmate_overview", child_id: "k1", card_design: design });
  return render(el.render()).markup;
}

test("the Reorder card shows the family's points name, as it is written", () => {
  for (const design of ["classic", "playroom"]) {
    const m = reorderMarkup(design, "Sterne");
    assert.match(m, /2 Sterne/, `${design}: points name missing`);
    assert.doesNotMatch(m, /2 sterne|2 [Pp]oints/, `${design}: lower-cased or generic points label`);
  }
  assert.match(reorderMarkup("classic", null), /2\s+Points/, "falls back to the translated word, capitalised");
});

test('German never calls the children "untergeordnete Elemente" (sub-elements)', () => {
  // A machine translation of "children" in the tree sense; the parent view was
  // "übergeordnet" (superordinate) for the same reason.
  for (const [k, v] of Object.entries(loc("de"))) {
    assert.doesNotMatch(v, /untergeordnet|übergeordnet/i, `de ${k}: "${v}"`);
  }
  assert.equal(loc("de")["points_display.empty_no_children"], "In den TaskMate-Daten wurden keine Kinder gefunden.");
});

test("the designed Points Display says no child is selected, as the classic one does", () => {
  for (const design of ["classic", "console", "playroom"]) {
    const Card = loadCard("taskmate-points-display-card.js", {
      editor: false,
      window: { __taskmate_design: { apply: () => design, styles: () => null } },
    }).get("taskmate-points-display-card");
    const el = new Card();
    el.hass = { language: "en", states: { "sensor.taskmate_overview": { attributes: { children: [{ id: "k1", name: "Malia", points: 5 }] } } } };
    el.setConfig({ entity: "sensor.taskmate_overview", mode: "single", card_design: design });
    const { markup } = render(el.render());
    assert.match(markup, /No child selected or child not found\./, `${design}: wrong empty message`);
    assert.doesNotMatch(markup, /No children found/, `${design}: claims there are no children`);
  }
});

test("the leaderboard's 'Ranked by' line is a sentence per sort, never a lower-cased label", () => {
  const src = readFileSync(path.join(WWW, "taskmate-leaderboard-card.js"), "utf8");
  assert.doesNotMatch(src, /periodLabel\.toLowerCase\(\)/);
  for (const lang of LANGS) {
    const d = loc(lang);
    assert.equal(d["leaderboard.ranked_by"], undefined, `${lang} still has the {period} template`);
    for (const k of ["points", "streak", "weekly", "career", "season"]) assert.ok(d[`leaderboard.ranked_by_${k}`], `${lang} lacks ranked_by_${k}`);
  }
  assert.equal(loc("de")["leaderboard.ranked_by_points"], "Geordnet nach Punkten insgesamt");
});

test("German speaks to everyone with du, and uses one word for chores and for streaks", () => {
  // The formal Sie crept in from machine translation ("Klicken Sie…",
  // "Verdienen Sie…") next to the du the rest of the file uses. A capital
  // "Sie" that means she/they ("Sie zählt für diesen Tag") is fine.
  const FORMAL = /\b\w+(?:en|ern|eln) Sie\b|\bSie (?:haben|können|möchten)\b|\b(?:Ihnen|Ihrem|Ihren|Ihrer|Ihres)\b|\bIhre (?:Familie|Kinder|Genehmigung|Bestätigung|Liste)\b/;
  const bad = [];
  // The Home Assistant side (services, selectors, config flow) too.
  const flat = (o, p = "") => Object.entries(o).flatMap(([k, v]) => (typeof v === "string" ? [[p + k, v]] : flat(v, `${p}${k}.`)));
  const ha = flat(JSON.parse(readFileSync(path.join(WWW, "..", "translations", "de.json"), "utf8"))).map(([k, v]) => [`translations:${k}`, v]);
  // Machine-translation howlers: "claimed" as behauptet (asserted), "tie" as
  // binden (to tie a knot), "a chore" as eine lästige Pflicht (a nuisance),
  // "applying to" as Beantragung (an application form), child as a tree node.
  const HOWLER = /\bbehauptet\b|\bBINDEN\b|\bvollendet\b|lästige|Beantragung|untergeordnet|Aufgabenverwaltungssystem|Bereit zum Anspruch/;
  for (const [k, v] of [...Object.entries(loc("de")), ...ha]) {
    if (HOWLER.test(v)) bad.push(`howler: ${k}: ${v}`);
    if (FORMAL.test(v)) bad.push(`formal: ${k}: ${v}`);
    if (/Hausarbeit/.test(v)) bad.push(`Hausarbeit: ${k}: ${v}`);
    if (/Strähne/.test(v)) bad.push(`Strähne: ${k}: ${v}`);
  }
  assert.deepEqual(bad, []);
  assert.equal(loc("de")["common.chores"], "Aufgaben");
  assert.equal(loc("de")["streak.day_streak"], "Tagesserie");
  assert.equal(loc("de")["points_display.family_subtitle"], "{count} Kinder · gesamt");
  assert.equal(loc("de")["leaderboard.tie"], "GLEICHSTAND");
  assert.ok(ha.length > 500, "translations/de.json was not read");
});
