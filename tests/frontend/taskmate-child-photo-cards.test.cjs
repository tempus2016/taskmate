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
