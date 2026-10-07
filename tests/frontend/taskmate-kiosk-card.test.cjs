// Kiosk card (#930).
//
// A shared wall tablet: pick a face, optionally type a PIN (checked by the
// server), tick off your own chores, and the card returns to the picker after
// a spell without a tap. These pin down the flow, that the PIN is never
// checked or skipped on the client, that the linked-child rule is honoured
// rather than bypassed, that no parent action ever appears, and that it renders
// the same working controls under every design.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const plain = (value) => JSON.parse(JSON.stringify(value));

class CustomEvent {
  constructor(type, init = {}) {
    this.type = type;
    this.detail = init.detail;
  }
}

// Timers never fire on their own: the idle clock is driven by calling _tick().
const timers = [];
const sandbox = {
  CustomEvent,
  setTimeout: (fn, ms) => timers.push({ fn, ms }),
  clearTimeout: () => {},
  setInterval: () => 0,
  clearInterval: () => {},
};
const { get, window: cardWindow } = loadCard("taskmate-kiosk-card.js", { sandbox });
const KioskCard = get("taskmate-kiosk-card");
const KioskEditor = get("taskmate-kiosk-card-editor");

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const future = (s = 60) => new Date(Date.now() + s * 1000).toISOString();

function chore(id, extra = {}) {
  return { id, name: id[0].toUpperCase() + id.slice(1), points: 10, assigned_to: [], ...extra };
}

function makeCard({ config = {}, status, completions = [], chores, verify } = {}) {
  const card = new KioskCard();
  card.setConfig({ entity: ENTITY, ...config });
  card.calls = [];
  card.ws = [];
  const statusReply = status ?? {
    children: [
      { id: "malia", has_pin: true, can_act: true, due: ["dishes", "bins", "photo"] },
      { id: "vaiha", has_pin: false, can_act: true, due: ["dishes"] },
      { id: "isla", has_pin: false, can_act: false, due: ["dishes"] },
    ],
  };
  card.hass = {
    locale: { language: "en" },
    callService: async (domain, service, data) => card.calls.push({ domain, service, data }),
    callWS: async (msg) => {
      card.ws.push(msg);
      if (msg.type === "taskmate/kiosk/status") return statusReply;
      if (msg.type === "taskmate/kiosk/verify_pin") return verify ? verify(msg) : { ok: msg.pin === "1234" };
      throw new Error(`unexpected ${msg.type}`);
    },
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [
            { id: "malia", name: "Malia", points: 340, current_streak: 5, level: 6, level_progress: 3, level_target: 5, chore_order: [] },
            { id: "vaiha", name: "Vaiha", points: 215, current_streak: 2, chore_order: [] },
            { id: "isla", name: "Isla", points: 90, chore_order: [] },
            { id: "guest", name: "Guest", points: 0, is_guest: true, chore_order: [] },
          ],
          chores: chores ?? [
            chore("dishes"),
            chore("bins", { requires_approval: false }),
            chore("photo", { require_photo: true }),
            chore("bed"),
          ],
          todays_completions: completions,
          rewards: [
            { id: "cinema", name: "Cinema trip", cost: 500, assigned_to: [], icon: "mdi:movie" },
            { id: "sweet", name: "Sweet", cost: 50, assigned_to: [] },
          ],
          points_icon: "mdi:star",
        },
      },
    },
  };
  return card;
}

async function ready(opts) {
  const card = makeCard(opts);
  await card._refreshStatus();
  return card;
}

const view = (card) => render(card.render());
const key = (r, d) => r.controls.find((c) => c.attrs.includes("km-key") && c.text === String(d));

// ── picker ────────────────────────────────────────────────────────────────

test("the picker shows every non-guest child by default", async () => {
  const { markup } = view(await ready());
  assert.deepEqual(plain(Array.from(markup.matchAll(/data-kid="([^"]+)"/g), (m) => m[1])), ["malia", "vaiha", "isla"]);
  assert.match(markup, new RegExp(localize("kiosk.who").replace("?", "\\?")));
});

test("configured children appear in the configured order, others hidden", async () => {
  const card = await ready({ config: { children: [{ child_id: "vaiha" }, { child_id: "malia", require_pin: false }] } });
  const ids = Array.from(view(card).markup.matchAll(/data-kid="([^"]+)"/g), (m) => m[1]);
  assert.deepEqual(plain(ids), ["vaiha", "malia"]);
});

test("faces stay inert until the server has said who has a PIN", () => {
  const card = makeCard();
  const face = view(card).control('data-kid="malia"');
  assert.equal(face.disabled, true);
  card._openKid(card._entry("malia"));
  assert.equal(card._screen, "picker");
});

test("a lock marks a child whose PIN is set and required", async () => {
  const { markup } = view(await ready());
  const malia = markup.slice(markup.indexOf('data-kid="malia"'), markup.indexOf('data-kid="vaiha"'));
  const vaiha = markup.slice(markup.indexOf('data-kid="vaiha"'));
  assert.match(malia, /km-lock/);
  assert.doesNotMatch(vaiha.slice(0, vaiha.indexOf("</button>")), /km-lock/);
});

test("picker progress counts done and waiting chores against today's list", async () => {
  const card = await ready({
    status: { children: [{ id: "malia", has_pin: false, can_act: true, due: ["bins"] }] },
    completions: [{ completion_id: "c1", chore_id: "dishes", child_id: "malia", approved: false, completed_at: new Date().toISOString() }],
  });
  assert.match(view(card).markup, new RegExp(localize("kiosk.progress", { done: 1, total: 2 })));
});

// ── PIN ───────────────────────────────────────────────────────────────────

test("a child with a PIN gets the pad; the server decides, then their chores show", async () => {
  const card = await ready();
  await view(card).control('data-kid="malia"').click();
  assert.equal(card._screen, "pin");
  for (const d of ["1", "2", "3"]) await key(view(card), d).click();
  assert.equal(card._screen, "pin");
  await key(view(card), 4).click();
  await new Promise((r) => setImmediate(r));
  const verify = card.ws.filter((m) => m.type === "taskmate/kiosk/verify_pin");
  assert.deepEqual(plain(verify), [{ type: "taskmate/kiosk/verify_pin", child_id: "malia", pin: "1234" }]);
  assert.equal(card._screen, "child");
});

test("a wrong PIN shakes, clears and says try again", async () => {
  const card = await ready();
  card._openKid(card._entry("malia"));
  for (const d of [9, 9, 9, 9]) card._pressDigit(d);
  await new Promise((r) => setImmediate(r));
  assert.equal(card._screen, "pin");
  assert.equal(card._pin, "");
  assert.match(view(card).markup, new RegExp(localize("kiosk.pin_wrong")));
});

test("a locked pad disables the keys and shows the wait", async () => {
  const card = await ready({ verify: () => ({ ok: false, locked_for: 30, attempts_left: 0 }) });
  card._openKid(card._entry("malia"));
  for (const d of [1, 1, 1, 1]) card._pressDigit(d);
  await new Promise((r) => setImmediate(r));
  const r = view(card);
  assert.match(r.markup, /Too many tries/);
  assert.equal(key(r, 5).disabled, true);
});

test("require_pin: false lets a child with a PIN straight in", async () => {
  const card = await ready({ config: { children: [{ child_id: "malia", require_pin: false }] } });
  card._openKid(card._entry("malia"));
  assert.equal(card._screen, "child");
  assert.deepEqual(card.ws.filter((m) => m.type !== "taskmate/kiosk/status"), []);
});

test("a child without a PIN goes straight in", async () => {
  const card = await ready();
  card._openKid(card._entry("vaiha"));
  assert.equal(card._screen, "child");
});

// ── linked-child rule ─────────────────────────────────────────────────────

test("a child this tablet may not act for gets an explanation, not buttons", async () => {
  const card = await ready();
  card._openKid(card._entry("isla"));
  assert.equal(card._screen, "blocked");
  const { markup, controls } = view(card);
  assert.match(markup, new RegExp(localize("kiosk.blocked_title", { name: "Isla" })));
  assert.equal(controls.some((c) => c.attrs.includes("km-done")), false);
});

// ── child view ────────────────────────────────────────────────────────────

async function childView(opts, kid = "vaiha") {
  const card = await ready(opts);
  card._openKid(card._entry(kid));
  if (card._screen === "pin") {
    card._screen = "child";
  }
  return card;
}

test("Done completes through the button entity when there is one", async () => {
  const card = await childView();
  card.hass.states["button.taskmate_vaiha_complete_dishes"] = { attributes: { child_id: "vaiha", chore_id: "dishes" } };
  // The attr-resolver helper isn't loaded in the harness; mirror its lookup.
  cardWindow.__taskmate_find_button = (hass, childId, _action, target) =>
    Object.keys(hass.states).find((id) => id.startsWith("button.taskmate_")
      && hass.states[id].attributes.child_id === childId && hass.states[id].attributes.chore_id === target) || null;
  try {
    await view(card).control("km-done").click();
  } finally {
    delete cardWindow.__taskmate_find_button;
  }
  assert.deepEqual(plain(card.calls), [{ domain: "button", service: "press", data: { entity_id: "button.taskmate_vaiha_complete_dishes" } }]);
});

test("Done falls back to complete_chore — never as_parent", async () => {
  const card = await childView();
  await view(card).control("km-done").click();
  assert.deepEqual(plain(card.calls), [{ domain: "taskmate", service: "complete_chore", data: { chore_id: "dishes", child_id: "vaiha" } }]);
});

test("photo chores are greyed out with no Done button", async () => {
  const card = await childView({}, "malia");
  const { markup, controls } = view(card);
  assert.match(markup, /km-row elsewhere/);
  assert.match(markup, new RegExp(localize("kiosk.do_on_phone")));
  assert.equal(controls.filter((c) => c.attrs.includes('class="km-done"')).length, 2, "dishes and bins only");
});

test("done and waiting chores show their state; approval chores say a grown-up checks", async () => {
  const now = new Date().toISOString();
  const card = await childView({
    status: { children: [{ id: "vaiha", has_pin: false, can_act: true, due: ["dishes"] }] },
    completions: [
      { completion_id: "c1", chore_id: "bins", child_id: "vaiha", approved: true, completed_at: now },
      { completion_id: "c2", chore_id: "bed", child_id: "vaiha", approved: false, completed_at: now },
    ],
  });
  const { markup } = view(card);
  assert.match(markup, /km-row done/);
  assert.match(markup, /km-row wait/);
  assert.match(markup, new RegExp(localize("kiosk.waiting")));
  assert.match(markup, new RegExp(localize("kiosk.needs_check")));
});

test("undo follows the #918 window and goes through undo_chore", async () => {
  const card = await childView({
    status: { children: [{ id: "vaiha", has_pin: false, can_act: true, due: [] }] },
    completions: [
      { completion_id: "c1", chore_id: "bins", child_id: "vaiha", approved: true, completed_at: new Date().toISOString(), child_undo_until: future() },
      { completion_id: "c2", chore_id: "dishes", child_id: "vaiha", approved: true, completed_at: new Date().toISOString() },
    ],
  });
  const undos = view(card).controls.filter((c) => c.attrs.includes("km-undo"));
  assert.equal(undos.length, 1, "only the completion inside the window");
  await undos[0].click();
  assert.deepEqual(plain(card.calls), [{ domain: "taskmate", service: "undo_chore", data: { completion_id: "c1" } }]);
});

test("the next reward is the cheapest one not yet affordable", async () => {
  const card = await childView({}, "vaiha");
  const { markup } = view(card);
  assert.match(markup, /Cinema trip/);
  assert.match(markup, new RegExp(localize("kiosk.to_go", { points: 285 })));
});

test("no parent action exists anywhere in the card", async () => {
  const screens = [];
  const card = await ready();
  screens.push(view(card).markup);
  card._openKid(card._entry("malia"));
  screens.push(view(card).markup);
  card._screen = "child";
  screens.push(view(card).markup);
  card._openKid(card._entry("isla"));
  screens.push(view(card).markup);
  for (const markup of screens) {
    assert.doesNotMatch(markup, /approve|reject|as_parent|penalt|claim|adjust/i);
  }
});

// ── idle + celebration ────────────────────────────────────────────────────

test("inactivity returns to the picker and clears the unlocked child", async () => {
  const card = await childView({ config: { timeout: 20 } });
  for (let i = 0; i < 9; i += 1) card._tick();
  assert.doesNotMatch(view(card).markup, /km-idle/);
  card._tick();
  assert.match(view(card).markup, new RegExp(localize("kiosk.still_there", { name: "Vaiha" })));
  for (let i = 0; i < 10; i += 1) card._tick();
  assert.equal(card._screen, "picker");
  assert.equal(card._kid, null);
});

test("warn_before_return: false skips the countdown overlay", async () => {
  const card = await childView({ config: { timeout: 20, warn_before_return: false } });
  for (let i = 0; i < 15; i += 1) card._tick();
  assert.doesNotMatch(view(card).markup, /km-idle/);
});

test("the timeout is clamped to 15-600 seconds", () => {
  assert.equal(makeCard({ config: { timeout: 1 } })._timeout(), 15);
  assert.equal(makeCard({ config: { timeout: 9999 } })._timeout(), 600);
  assert.equal(makeCard()._timeout(), 60);
});

test("finishing the last chore here celebrates, then goes back to the picker", async () => {
  const card = await childView({ status: { children: [{ id: "vaiha", has_pin: false, can_act: true, due: ["dishes"] }] } });
  await view(card).control("km-done").click();
  card._status.vaiha.due = new Set();
  card.hass.states[ENTITY].attributes.todays_completions = [
    { completion_id: "c1", chore_id: "dishes", child_id: "vaiha", approved: false, completed_at: new Date().toISOString() },
  ];
  card._maybeCelebrate();
  assert.equal(card._celebrating, true);
  timers.at(-1).fn();
  assert.equal(card._screen, "picker");
});

// ── completion feedback (#1039) ─────────────────────────────────────────────

// Records what the shared sound engine was asked to play.
function withSounds(fn) {
  const played = [];
  cardWindow.__taskmate_sounds = { play: (name, custom) => played.push({ name, custom }) };
  return Promise.resolve(fn(played)).finally(() => { delete cardWindow.__taskmate_sounds; });
}

test("Done plays the chore's sound, drops confetti and pops up the points", () => withSounds(async (played) => {
  const card = await childView({
    chores: [chore("dishes", { completion_sound: "fanfare", effective_points: 15 })],
    status: { children: [{ id: "vaiha", has_pin: false, can_act: true, due: ["dishes"] }] },
  });
  card.hass.states[ENTITY].attributes.custom_sounds = [{ file: "x.mp3" }];
  await view(card).control("km-done").click();
  assert.deepEqual(plain(played), [{ name: "fanfare", custom: [{ file: "x.mp3" }] }]);
  assert.equal(card._confetti.length, 50);
  assert.match(view(card).markup, /km-confetti/);
  const { markup } = view(card);
  assert.match(markup, /km-pop/);
  assert.match(markup, new RegExp(localize("child.celebration_title")));
  assert.match(markup, /\+15/);
  // The popup closes itself.
  timers.findLast((t) => t.ms === 2500).fn();
  assert.equal(card._popup, null);
}));

test("without a chore sound, default_sound then coin; undo plays undo_sound", () => withSounds(async (played) => {
  const card = await childView({ status: { children: [{ id: "vaiha", has_pin: false, can_act: true, due: ["dishes"] }] } });
  await view(card).control("km-done").click();
  card.config = { ...card.config, default_sound: "chime", undo_sound: "fart3" };
  card._busy = "";
  await card._complete(card._entry("vaiha").child, chore("dishes"));
  await card._undo({ completion_id: "c1" });
  assert.deepEqual(plain(played.map((p) => p.name)), ["coin", "chime", "fart3"]);
}));

test("play_sounds, show_confetti and show_completion_popup: false switch each off", () => withSounds(async (played) => {
  const card = await childView({
    config: { play_sounds: false, show_confetti: false, show_completion_popup: false },
    status: { children: [{ id: "vaiha", has_pin: false, can_act: true, due: ["dishes"] }] },
  });
  await view(card).control("km-done").click();
  await card._undo({ completion_id: "c1" });
  assert.deepEqual(plain(played), []);
  assert.equal(card._confetti.length, 0);
  assert.equal(card._popup, null);
  assert.doesNotMatch(view(card).markup, /km-pop|km-confetti/);
}));

test("a failed completion doesn't celebrate", () => withSounds(async (played) => {
  const card = await childView({ status: { children: [{ id: "vaiha", has_pin: false, can_act: true, due: ["dishes"] }] } });
  card.hass.callService = async () => { throw new Error("nope"); };
  await view(card).control("km-done").click();
  assert.deepEqual(plain(played), []);
  assert.equal(card._popup, null);
}));

test("the all-done overlay replaces the chore popup; the picker clears both", () => withSounds(async () => {
  const card = await childView({ status: { children: [{ id: "vaiha", has_pin: false, can_act: true, due: ["dishes"] }] } });
  await view(card).control("km-done").click();
  assert.ok(card._popup);
  card._status.vaiha.due = new Set();
  card.hass.states[ENTITY].attributes.todays_completions = [
    { completion_id: "c1", chore_id: "dishes", child_id: "vaiha", approved: false, completed_at: new Date().toISOString() },
  ];
  card._maybeCelebrate();
  assert.equal(card._popup, null);
  assert.match(view(card).markup, /km-party/);
  card._toPicker();
  assert.equal(card._confetti.length, 0);
}));

test("the editor offers the three feedback switches, on by default", () => {
  const editor = new KioskEditor();
  editor.hass = makeCard().hass;
  editor.config = { entity: ENTITY };
  const names = editor._schema().map((f) => f.name);
  for (const n of ["play_sounds", "show_confetti", "show_completion_popup"]) assert.ok(names.includes(n), n);
});

// ── chores the kiosk can't complete (#952) ──────────────────────────────────

const PHONE_CHORES = [
  chore("dishes"),
  chore("photo", { require_photo: true }),
  chore("timer", { task_type: "timed" }),
  chore("open", { open_ended: true }),
];
const phoneStatus = (due) => ({ children: [{ id: "vaiha", has_pin: false, can_act: true, due }] });
const waiting = (id) => ({ completion_id: `c-${id}`, chore_id: id, child_id: "vaiha", approved: false, completed_at: new Date().toISOString() });

test("photo, timed and open-ended chores stay out of the done/total count", async () => {
  const card = await childView({ chores: PHONE_CHORES, status: phoneStatus(["dishes", "photo", "timer", "open"]) });
  const { done, total } = card._progress(card._entry("vaiha").child);
  assert.deepEqual([done, total], [0, 1]);
  assert.match(view(card).markup, /<b>0\/1<\/b>/);
});

test("they show greyed out in their own 'do these on your phone' group, below today's list", async () => {
  const card = await childView({ chores: PHONE_CHORES, status: phoneStatus(["dishes", "photo", "timer", "open"]) });
  const { markup, controls } = view(card);
  const group = markup.indexOf("km-phone-group");
  assert.ok(group > markup.indexOf("Dishes"), "the group comes after the kiosk's own chores");
  assert.match(markup.slice(group), new RegExp(localize("kiosk.phone_group")));
  for (const name of ["Photo", "Timer", "Open"]) assert.ok(markup.indexOf(name, group) > group, `${name} is in the group`);
  assert.equal((markup.match(/km-row elsewhere/g) || []).length, 3);
  assert.equal(controls.filter((c) => c.attrs.includes('class="km-done"')).length, 1, "only dishes gets a Done button");
});

test("finishing the last kiosk chore reaches all done even with phone chores still due", async () => {
  const card = await childView({ chores: PHONE_CHORES, status: phoneStatus(["dishes", "photo", "timer", "open"]) });
  await view(card).control("km-done").click();
  card._status.vaiha.due = new Set(["photo", "timer", "open"]);
  card.hass.states[ENTITY].attributes.todays_completions = [waiting("dishes")];
  assert.match(view(card).markup, new RegExp(localize("kiosk.all_done", { name: "Vaiha" })));
  card._maybeCelebrate();
  assert.equal(card._celebrating, true, "a chore waiting for approval counts: the child has done their part");
  timers.at(-1).fn();
  assert.equal(card._screen, "picker");
  assert.match(view(card).markup, new RegExp(localize("kiosk.all_done_short")));
});

test("a phone chore done on the phone keeps its state in the group, still outside the count", async () => {
  const card = await childView({
    chores: PHONE_CHORES,
    status: phoneStatus(["dishes", "timer", "open"]),
    completions: [waiting("photo")],
  });
  const { done, total } = card._progress(card._entry("vaiha").child);
  assert.deepEqual([done, total], [0, 1]);
  const { markup } = view(card);
  const group = markup.indexOf("km-phone-group");
  assert.ok(markup.indexOf("km-row wait", group) > group, "the photo chore shows as waiting inside the group");
});

test("a child with only phone chores isn't told there's nothing to do", async () => {
  const card = await childView({ chores: PHONE_CHORES, status: phoneStatus(["photo"]) });
  const child = view(card).markup;
  assert.doesNotMatch(child, new RegExp(localize("kiosk.nothing_today")));
  assert.match(child, new RegExp(localize("kiosk.nothing_here")));
  card._maybeCelebrate();
  assert.equal(card._celebrating, false);
  card._toPicker();
  const markup = view(card).markup;
  const at = markup.indexOf('data-kid="vaiha"');
  const picker = markup.slice(at, markup.indexOf("</button>", at));
  assert.doesNotMatch(picker, new RegExp(localize("kiosk.nothing_today")));
  assert.match(picker, new RegExp(localize("kiosk.nothing_here")));
});

// ── designs ───────────────────────────────────────────────────────────────

for (const design of DESIGNS) {
  test(`${design}: the picker and the child view render their controls`, async () => {
    const card = await childView({ config: { card_design: design } });
    const r = view(card);
    assert.ok(r.control("km-done"), "a Done button");
    assert.ok(r.control("km-switch"), "the Switch button");
    card._toPicker();
    assert.equal(view(card).controls.filter((c) => c.attrs.includes("data-kid")).length, 3);
  });
}

// ── editor ────────────────────────────────────────────────────────────────

test("the editor writes the ordered children list with require_pin", () => {
  const editor = new KioskEditor();
  const host = makeCard();
  editor.hass = host.hass;
  editor.setConfig({ entity: ENTITY });
  editor._pins = { malia: true };
  editor._move(1, -1);
  const written = editor.dispatched.at(-1).detail.config;
  assert.deepEqual(plain(written.children.map((c) => c.child_id)), ["vaiha", "malia", "isla"]);
  editor._toggleShown(2);
  assert.deepEqual(plain(editor.dispatched.at(-1).detail.config.children.map((c) => c.child_id)), ["vaiha", "malia"]);
  editor._togglePin(1);
  assert.equal(editor.dispatched.at(-1).detail.config.children[1].require_pin, false);
});
