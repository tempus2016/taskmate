// Wishlist card (#932): a child's wishes, their savings, the family's pledges.
//
// The card is single-layout and takes its look from the design tokens, so the
// same markup must come out under every design — rendered here for all six.
// Links are typed by a child, so the tests also pin that only an http(s) URL
// is ever rendered as one.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const ENTITY = "sensor.taskmate_overview";
const WISHLIST = "sensor.mia_wishlist";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];

const Card = loadCard("taskmate-wishlist-card.js").get("taskmate-wishlist-card");

const WISHES = [
  { id: "w1", name: "Lego treehouse", target: 600, status: "active", saved: 260, pledged: 100,
    pledges: [{ name: "Grandma", points: 60 }, { name: "Uncle Rob", points: 40 }], link: "https://www.lego.com/treehouse" },
  { id: "w2", name: "Roller skates", target: 400, status: "active", saved: 310, pledged: 90,
    pledges: [{ name: "Grandad", points: 90 }] },
  { id: "w3", name: "Hamster ball", target: 150, status: "pending", link: "javascript:alert(1)" },
  { id: "w4", name: "Drum kit", target: 900, status: "declined", decline_reason: "Too loud for the flat" },
  { id: "w5", name: "Kite", target: 80, status: "redeem_requested", saved: 80 },
];

function hassWith({ wishes = WISHES, spendable = 340, calls = [] } = {}) {
  return {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "mia", name: "Malia", points: spendable, spendable_balance: spendable }],
          points_icon: "mdi:star",
          points_name: "Stars",
        },
      },
      [WISHLIST]: {
        state: String(wishes.length),
        attributes: { wishlist_child_id: "mia", wishes, wish_max_open: 5 },
      },
      "sensor.leo_wishlist": {
        state: "1",
        attributes: { wishlist_child_id: "leo", wishes: [{ id: "x", name: "Sibling's bike", target: 5, status: "active" }] },
      },
    },
    // The card runs in a vm realm; a JSON copy makes its objects comparable here.
    callService: async (domain, service, data) => {
      calls.push(JSON.parse(JSON.stringify({ domain, service, data })));
    },
  };
}

// The sheet's scrim is itself clickable (tap outside to close) and contains
// every button in the sheet, so controls are matched as buttons by their text.
function button(rendered, label) {
  return rendered.controls.find((c) => c.tag === "button" && c.text === label);
}

function card(design = "classic", opts = {}) {
  const c = new Card();
  c.setConfig({ entity: ENTITY, child_id: "mia", card_design: design, ...(opts.config || {}) });
  c.hass = hassWith(opts);
  return c;
}

for (const design of DESIGNS) {
  test(`wishlist card — ${design} renders the child's wishes with the full-colour header`, () => {
    const { markup } = render(card(design).render());
    assert.ok(markup.includes(localize("wishlist.title", { name: "Malia" })));
    assert.ok(markup.includes('class="wl-header"'), "the header banner is there in every design");
    assert.ok(markup.includes("Lego treehouse") && markup.includes("Roller skates"));
    assert.ok(!markup.includes("Sibling's bike"), "only this child's wishlist sensor is read");
    assert.ok(markup.includes(localize("wishlist.saved_in_wishes", { points: 650 })), "saved = 260 + 310 + 80");
  });

  test(`wishlist card — ${design} splits savings from pledges and lists pledgers`, () => {
    const { markup } = render(card(design).render());
    assert.ok(markup.includes(localize("wishlist.legend_me", { points: 260 })));
    assert.ok(markup.includes(localize("wishlist.legend_family", { points: 100 })));
    assert.ok(markup.includes("Grandma +60") && markup.includes("Uncle Rob +40"));
    assert.match(markup, /class="wl-me" style="width:43\.3+\d*%"/);
  });
}

test("each status gets its own actions", () => {
  const rendered = render(card().render());
  const { markup } = rendered;
  assert.ok(button(rendered, localize("wishlist.move_points")), "an unfunded wish can be saved into");
  assert.ok(button(rendered, localize("wishlist.ask_redeem")), "a funded wish can be redeemed");
  assert.ok(markup.includes(localize("wishlist.status_pending")));
  assert.ok(button(rendered, localize("wishlist.withdraw")));
  assert.ok(markup.includes(localize("wishlist.status_declined")) && markup.includes("Too loud for the flat"));
  assert.ok(button(rendered, localize("wishlist.dismiss")));
  assert.ok(markup.includes(localize("wishlist.status_redeem_requested")));
});

test("only http(s) links become links, and they open safely", () => {
  const { markup } = render(card().render());
  assert.ok(markup.includes('href="https://www.lego.com/treehouse"'));
  assert.ok(markup.includes('rel="noopener noreferrer"'));
  assert.ok(markup.includes(">lego.com<") || markup.includes("lego.com</a>"), "the chip shows the site, not the URL");
  assert.ok(!markup.includes("javascript:"), "a javascript: link is never rendered");
});

test("moving points opens a sheet and calls the service for this child", async () => {
  const calls = [];
  const c = card("classic", { calls });
  await button(render(c.render()), localize("wishlist.move_points")).click();
  assert.equal(c._sheet.kind, "move");
  const sheet = render(c.render());
  assert.ok(sheet.markup.includes(localize("wishlist.move_title", { name: "Lego treehouse" })));
  await button(sheet, localize("wishlist.move_confirm", { points: 50 })).click();
  assert.deepEqual(calls, [
    { domain: "taskmate", service: "move_points_to_wish", data: { child_id: "mia", wish_id: "w1", points: 50 } },
  ]);
  assert.equal(c._sheet, null, "the sheet closes once the call succeeds");
});

test("moving is capped at what the wish still needs", async () => {
  const c = card("classic", { spendable: 1000 });
  await button(render(c.render()), localize("wishlist.move_points")).click();
  const sheet = render(c.render());
  assert.ok(button(sheet, localize("wishlist.all_i_need", { points: 240 })), "600 - 260 - 100");
});

test("move points is disabled with nothing to spend", () => {
  const rendered = render(card("classic", { spendable: 0 }).render());
  assert.ok(button(rendered, localize("wishlist.move_points")).disabled);
});

test("taking points back offers only the child's own savings", async () => {
  const calls = [];
  const c = card("classic", { calls });
  await button(render(c.render()), localize("wishlist.take_back")).click();
  const sheet = render(c.render());
  assert.ok(button(sheet, localize("wishlist.take_all", { points: 260 })));
  await button(sheet, localize("wishlist.take_confirm", { points: 260 })).click();
  assert.equal(calls[0].service, "take_points_from_wish");
  assert.equal(calls[0].data.points, 260);
});

test("asking to redeem confirms first, then requests it", async () => {
  const calls = [];
  const c = card("classic", { calls });
  await button(render(c.render()), localize("wishlist.ask_redeem")).click();
  await button(render(c.render()), localize("wishlist.yes_please")).click();
  assert.deepEqual(calls[0], { domain: "taskmate", service: "request_wish_redeem", data: { child_id: "mia", wish_id: "w2" } });
});

test("adding a wish sends it to a grown-up", async () => {
  const calls = [];
  const c = card("classic", { calls, wishes: [] });
  const first = render(c.render());
  assert.ok(first.markup.includes(localize("wishlist.empty")));
  await button(first, localize("wishlist.add")).click();
  c._setSheet({ name: "  Hamster ball ", target: 150, link: "https://pets.example/ball" });
  await button(render(c.render()), localize("wishlist.send")).click();
  assert.deepEqual(calls[0], {
    domain: "taskmate",
    service: "add_wish",
    data: { child_id: "mia", name: "Hamster ball", target: 150, link: "https://pets.example/ball" },
  });
});

test("a link that isn't http(s) is refused before anything is sent", async () => {
  const calls = [];
  const c = card("classic", { calls, wishes: [] });
  await button(render(c.render()), localize("wishlist.add")).click();
  c._setSheet({ name: "Ball", target: 10, link: "javascript:alert(1)" });
  await button(render(c.render()), localize("wishlist.send")).click();
  assert.equal(calls.length, 0);
  assert.ok(render(c.render()).markup.includes(localize("wishlist.link_invalid")));
});

test("the add button is disabled once every slot is used", () => {
  const full = Array.from({ length: 5 }, (_, i) => ({ id: `f${i}`, name: `Wish ${i}`, target: 10, status: "active" }));
  const rendered = render(card("classic", { wishes: full }).render());
  assert.ok(button(rendered, localize("wishlist.add")).disabled);
});

test("a service error is shown in the sheet, which stays open", async () => {
  const c = card();
  c.hass.callService = async () => { throw new Error("No spendable points"); };
  await button(render(c.render()), localize("wishlist.move_points")).click();
  await button(render(c.render()), localize("wishlist.move_confirm", { points: 50 })).click();
  assert.equal(c._sheet.kind, "move");
  assert.ok(render(c.render()).markup.includes("No spendable points"));
});

test("without a child picked the card asks for one", () => {
  const c = new Card();
  c.setConfig({ entity: ENTITY });
  c.hass = hassWith();
  assert.ok(render(c.render()).markup.includes(localize("wishlist.pick_child")));
});

test("the visual editor offers the family's children and the design picker", () => {
  const loaded = loadCard("taskmate-wishlist-card.js", {
    window: { __taskmate_design: { apply: () => "classic", styles: () => null, editorOptions: () => [{ value: "global", label: "g" }] } },
  });
  const Editor = loaded.get("taskmate-wishlist-card-editor");
  const editor = new Editor();
  editor.hass = hassWith();
  editor.setConfig({ entity: ENTITY });
  const schema = editor._buildSchema();
  const child = schema.find((s) => s.name === "child_id");
  assert.deepEqual(JSON.parse(JSON.stringify(child.selector.select.options)), [{ value: "mia", label: "Malia" }]);
  assert.ok(schema.some((s) => s.name === "card_design"));
  assert.equal(editor._computeLabel({ name: "child_id" }), localize("wishlist.editor.child"));
});
