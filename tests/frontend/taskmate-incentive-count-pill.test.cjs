// Bonuses / penalties header count (v7.7.1 recheck).
//
// The count beside the manage button was stretched to the button's 36px height
// with the number stuck at the top. It is a centred pill now, in classic and in
// the designed styles' coloured header (where it used to be a bare subline).

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

const OVERVIEW = "sensor.taskmate_overview";

function incentiveCard(config) {
  const tag = "taskmate-bonuses-card";
  const loaded = loadCard("taskmate-incentive-card.js", {
    transform: (src) => src.replace("export function createIncentiveCard", "function createIncentiveCard")
      + `\ncreateIncentiveCard({ tag: "${tag}", kind: "bonus", idKey: "bonus_id", i18n: "bonuses", attr: "bonuses",`
      + ` icon: "mdi:star", headerIcon: "mdi:star", applyIcon: "mdi:plus", sign: "+", dpts: (n) => "+" + n,`
      + ` accent: "#2e7d32", designHd: "#2e7d32", designIcons: {}, cardName: "x", cardDesc: "x", bannerName: "X", bannerColor: "#000" });`,
    sandbox: { console: { info() {}, log() {}, warn() {}, error() {} } },
  });
  const Card = loaded.get(tag);
  const card = new Card();
  card.setConfig({ entity: OVERVIEW, ...config });
  card.hass = {
    language: "en", user: { is_admin: true },
    states: { [OVERVIEW]: { state: "ok", attributes: {
      children: [{ id: "k1", name: "Ella" }],
      bonuses: [{ id: "a", name: "Helped out", points: 5 }, { id: "b", name: "Kind", points: 3 }],
    } } },
  };
  return { card, Card };
}

test("classic: the count is a centred pill and the header row centres it", () => {
  const { card, Card } = incentiveCard({});
  assert.match(render(card.render()).markup, /<span class="bonus-count">2<\/span>/);
  const css = render(Card.styles).markup;
  assert.match(css, /\.header-actions \{ display: flex; align-items: center;/);
  const pill = css.slice(css.indexOf(".bonus-count {"), css.indexOf("}", css.indexOf(".bonus-count {")));
  assert.match(pill, /display: inline-flex; align-items: center; justify-content: center;/);
  assert.match(pill, /height: 28px/);
  assert.match(pill, /line-height: 1/);
});

for (const design of ["playroom", "console", "cleanpro", "accessible", "graphite"]) {
  test(`${design}: the count is its own pill in the header, not a line under the title`, () => {
    const { card, Card } = incentiveCard({ card_design: design });
    const markup = render(card.render()).markup;
    assert.match(markup, /<span class="inc-cnt">2<\/span>/);
    assert.doesNotMatch(markup, /<small>2<\/small>/);
    assert.match(render(Card.styles).markup, /\.tmd-hd \.inc-cnt \{[^}]*display: inline-flex; align-items: center; justify-content: center;/);
  });
}
