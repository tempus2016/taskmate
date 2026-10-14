// Cards that draw a child's face read it through the shared face helper
// (window.__taskmate_child_visual), so a child's photo shows there too and a
// child without one keeps their avatar (Copilot review on #1062).

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

const PHOTO = "/api/image/serve/abc/512x512";
const withPhoto = { id: "k1", name: "Millie", avatar: "mdi:account-child", avatar_image: PHOTO };
const withoutPhoto = { id: "k2", name: "Evie", avatar: "mdi:unicorn" };

class CustomEvent {
  constructor(type, init = {}) {
    this.type = type;
    this.detail = init.detail;
  }
}

function card(file, tag) {
  const loaded = loadCard(file, {
    sandbox: { CustomEvent, setTimeout: () => 0, clearTimeout() {}, setInterval: () => 0, clearInterval() {} },
  });
  return Object.create(loaded.get(tag).prototype);
}

const markup = (tree) => render(tree).markup;

test("the chore board shows a child's photo, and their avatar without one", () => {
  const board = card("taskmate-chore-board-card.js", "taskmate-chore-board-card");
  board._kidColour = () => "#000";
  assert.match(markup(board._avatar({}, withPhoto)), new RegExp(`<img src="${PHOTO}"`));
  assert.match(markup(board._avatar({}, withoutPhoto)), /<ha-icon icon="mdi:unicorn">/);
});

test("the kiosk shows a child's photo, and their avatar without one", () => {
  const kiosk = card("taskmate-kiosk-card.js", "taskmate-kiosk-card");
  assert.match(markup(kiosk._face(withPhoto, "#000")), new RegExp(`<img src="${PHOTO}"`));
  assert.match(markup(kiosk._face(withoutPhoto, "#000")), /<ha-icon icon="mdi:unicorn">/);
});

test("the recap shows a child's photo, and their avatar without one", () => {
  const recap = card("taskmate-recap-card.js", "taskmate-recap-card");
  assert.match(markup(recap._avatar(withPhoto)), new RegExp(`<img src="${PHOTO}"`));
  assert.match(markup(recap._avatar(withoutPhoto)), /<ha-icon icon="mdi:unicorn">/);
});

// Second Copilot review on #1062: bounty, auction and the child card's team row.

test("the bounty board shows a child's photo, and their initial without one", () => {
  const bounty = card("taskmate-bounty-card.js", "taskmate-bounty-card");
  bounty._children = () => [withPhoto, withoutPhoto];
  bounty._childName = (id) => (id === "k1" ? "Millie" : "Evie");
  assert.match(markup(bounty._avatar("k1")), new RegExp(`<img src="${PHOTO}"`));
  assert.match(markup(bounty._avatar("k2")), />E<\/span>/);
});

test("the auction card shows a child's photo, and their initial without one", () => {
  const auction = card("taskmate-auction-card.js", "taskmate-auction-card");
  auction._children = () => [withPhoto, withoutPhoto];
  auction._childName = (id) => (id === "k1" ? "Millie" : "Evie");
  assert.match(markup(auction._avatar("k1")), new RegExp(`<img src="${PHOTO}"`));
  assert.match(markup(auction._avatar("k2")), />E<\/span>/);
});

test("a teamwork chore's joined children show their photos on the child card", () => {
  const child = card("taskmate-child-card.js", "taskmate-child-card");
  child.config = { entity: "sensor.taskmate_overview" };
  child.hass = { states: { "sensor.taskmate_overview": { attributes: { children: [withPhoto, withoutPhoto] } } } };
  child._t = (key) => key;
  const out = markup(child._renderTeamProgress({ joined: ["k1", "k2"], size: 3, mine: false }));
  assert.match(out, new RegExp(`<img src="${PHOTO}"`));
  assert.match(out, /<ha-icon icon="mdi:unicorn">/);
});

// Third Copilot review on #1062: the badges header, and the photo picker.

test("the badges card shows the child's photo, and their avatar without one", () => {
  const badges = card("taskmate-badges-card.js", "taskmate-badges-card");
  assert.match(markup(badges._face({ avatar_image: PHOTO }, "mdi:unicorn")), new RegExp(`<img src="${PHOTO}"`));
  assert.match(markup(badges._face({}, "mdi:unicorn")), /<ha-icon icon="mdi:unicorn">/);
});

test("the photo picker offers any entity with a picture, not only people", () => {
  const src = require("node:fs").readFileSync(
    require("node:path").join(__dirname, "../../custom_components/taskmate/www/taskmate-panel.js"), "utf8");
  const call = src.slice(src.indexOf('"picture_entity", d.picture_entity,'));
  assert.match(call.slice(0, 200), /\[\], this\._t\("panel\.child_picture_entity_hint"\), \{ withPicture: true \}/);
  assert.match(src, /if \(picker\.dataset\.epPicture && !st\.attributes\?\.entity_picture\) return false;/);
});
