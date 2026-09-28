// Chore auctions (#982): the auction card.
//
// The card has one layout that reads the design tokens, so every design must
// render the same lots and controls; this renders each of them. Bids are
// sealed: the card only ever gets this child's own bid from the WebSocket
// view, and must never ask for anyone else's.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const NOW = Date.now();
const iso = (ms) => new Date(NOW + ms).toISOString();
const H = 3600e3;
// Objects built inside the card's sandbox have that realm's prototypes.
const plain = (x) => JSON.parse(JSON.stringify(x));

const CHILDREN = [
  { id: "k1", name: "Malia" },
  { id: "k2", name: "Vaiha" },
];

const lot = (extra = {}) => ({
  id: "a1", chore_id: "c1", chore_name: "Clean the bathroom", icon: "mdi:shower", occurrence: "2026-10-04",
  max_points: 40, min_points: 1, normal_points: 6, closes_at: iso(2 * H), status: "open",
  eligible_child_ids: ["k1", "k2"], bid_count: 0, my_bid: null, ...extra,
});

function hassWith(auctions) {
  const sent = [];
  return {
    sent,
    states: { [ENTITY]: { state: "ok", attributes: { children: CHILDREN, auctions: [] } } },
    connection: {
      sendMessagePromise: async (msg) => {
        sent.push(msg);
        if (msg.type === "taskmate/auctions/list") return { auctions };
        return { id: msg.auction_id };
      },
    },
  };
}

const Card = loadCard("taskmate-auction-card.js").get("taskmate-auction-card");

async function cardFor(auctions, { child = "k1", design = "classic" } = {}) {
  const card = new Card();
  card.setConfig({ entity: ENTITY, child_id: child, card_design: design });
  card.hass = hassWith(auctions);
  await card._fetch();
  return card;
}

const button = (view, text) => view.controls.find((c) => c.tag === "button" && c.text.includes(text));

for (const design of DESIGNS) {
  test(`auction card — ${design} shows an open auction with the gauge and a bid button`, async () => {
    const view = render((await cardFor([lot()], { design })).render());
    assert.ok(view.markup.includes("Clean the bathroom"));
    assert.ok(view.markup.includes(localize("auction.open_count", { count: 1 })));
    assert.ok(view.markup.includes(localize("auction.up_to", { points: 40 })));
    assert.ok(view.markup.includes(localize("auction.gauge_hint", { points: 6 })));
    assert.ok(view.markup.includes(localize("auction.no_other_bids")));
    assert.ok(button(view, localize("auction.place_bid")));
  });

  test(`auction card — ${design} shows a sealed bid with Change and Withdraw`, async () => {
    const view = render((await cardFor([lot({ my_bid: 25, bid_count: 2 })], { design })).render());
    assert.ok(view.markup.includes(localize("auction.your_bid")));
    assert.ok(view.markup.includes("25 ★"));
    assert.ok(view.markup.includes(localize("auction.other_bids_one")));
    assert.ok(button(view, localize("auction.change")));
    assert.ok(button(view, localize("auction.withdraw")));
  });
}

test("the card asks the server for this child's view only", async () => {
  const card = await cardFor([lot()]);
  assert.deepEqual(plain(card.hass.sent), [{ type: "taskmate/auctions/list", child_id: "k1" }]);
});

test("bidding: open the sheet, key a number, seal it", async () => {
  const card = await cardFor([lot()]);
  await button(render(card.render()), localize("auction.place_bid")).click();
  assert.equal(card._sheet.id, "a1");
  let view = render(card.render());
  assert.ok(view.markup.includes(localize("auction.bid_label")));
  // The first key replaces the suggested number; later keys append.
  await button(view, "1").click();
  await button(render(card.render()), "8").click();
  assert.equal(card._sheet.value, 18);
  view = render(card.render());
  await button(view, localize("auction.seal", { points: 18 })).click();
  assert.deepEqual(plain(card.hass.sent.find((m) => m.type === "taskmate/auctions/bid")), {
    type: "taskmate/auctions/bid", auction_id: "a1", child_id: "k1", points: 18,
  });
  assert.equal(card._sheet, null);
});

test("a bid over the maximum is clamped, and zero can't be sealed", async () => {
  const card = await cardFor([lot({ max_points: 20 })]);
  card._openSheet(card._auctions[0]);
  card._key("9", card._auctions[0]);
  card._key("9", card._auctions[0]);
  assert.equal(card._sheet.value, 20);
  card._key("c", card._auctions[0]);
  const seal = button(render(card.render()), localize("auction.seal", { points: 0 }));
  assert.ok(seal.disabled);
});

test("the minimum bid shows as a rule and gates the seal button", async () => {
  const card = await cardFor([lot({ min_points: 5 })]);
  card._openSheet(card._auctions[0]);
  card._setBid(3, card._auctions[0]);
  const view = render(card.render());
  assert.ok(view.markup.includes(localize("auction.rule_min", { points: 5 })));
  assert.ok(button(view, localize("auction.seal", { points: 3 })).disabled);
});

test("withdraw sends the withdraw command for this child", async () => {
  const card = await cardFor([lot({ my_bid: 12, bid_count: 1 })]);
  await button(render(card.render()), localize("auction.withdraw")).click();
  assert.deepEqual(plain(card.hass.sent.find((m) => m.type === "taskmate/auctions/withdraw")), {
    type: "taskmate/auctions/withdraw", auction_id: "a1", child_id: "k1",
  });
});

test("a win shows the price, the chore and the won-at-auction tag", async () => {
  const view = render((await cardFor([lot({ status: "closed", winner_id: "k1", price: 18, my_bid: 18, closed_at: iso(-H) })])).render());
  assert.ok(view.markup.includes(localize("auction.results")));
  assert.ok(view.markup.includes(localize("auction.you_won", { points: 18 })));
  assert.ok(view.markup.includes(localize("child.won_at_auction")));
  assert.equal(button(view, localize("auction.place_bid")), undefined);
});

test("a loss names the winner, the winning price and my own bid", async () => {
  const view = render((await cardFor([lot({ status: "closed", winner_id: "k2", price: 18, my_bid: 22, closed_at: iso(-H) })])).render());
  assert.ok(view.markup.includes(localize("auction.sibling_won", { name: "Vaiha" })));
  assert.ok(view.markup.includes(localize("auction.sibling_won_sub_bid", { points: 18, bid: 22 })));
});

test("no bids says the chore goes back to its normal assignment", async () => {
  const view = render((await cardFor([lot({ status: "closed", winner_id: "", price: 0, closed_at: iso(-H) })])).render());
  assert.ok(view.markup.includes(localize("auction.no_bids")));
  assert.ok(view.markup.includes(localize("auction.empty")));
});

test("a failed fetch says so instead of rendering an empty board", async () => {
  const card = new Card();
  card.setConfig({ entity: ENTITY, child_id: "k1" });
  card.hass = hassWith([]);
  card.hass.connection.sendMessagePromise = async () => { throw new Error("Not allowed"); };
  await card._fetch();
  const view = render(card.render());
  assert.ok(view.markup.includes(localize("auction.load_failed", { error: "Not allowed" })));
  assert.ok(!view.markup.includes(localize("auction.empty")));
});

test("the editor offers the child picker and the design picker", () => {
  const Editor = loadCard("taskmate-auction-card.js").get("taskmate-auction-card-editor");
  const editor = new Editor();
  editor.hass = { states: { [ENTITY]: { attributes: { children: CHILDREN } } } };
  editor.setConfig({ entity: ENTITY, child_id: "k1" });
  const names = editor._buildSchema().map((s) => s.name);
  assert.deepEqual(plain(names), ["entity", "child_id", "title", "card_design"]);
});
