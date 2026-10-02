// Logging a past job from the admin panel (the sticker chart card in its
// past-day mode, mounted in the panel's dialog).
//
// The panel mounts the card inside its own render, so nothing there may throw:
// an error would leave the whole panel dead until a reload. And a grown-up
// ticking a past day must not get the child's coin chime or full-screen pop-up.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

const ENTITY = "sensor.taskmate_overview";

// ── The card, in past-day mode ───────────────────────────────────────────────

const played = [];
class CustomEvent {
  constructor(type, init = {}) {
    this.type = type;
    this.detail = init.detail;
  }
}

const loaded = loadCard("taskmate-sticker-chart-card.js", {
  topLevelAwait: true,
  sandbox: { CustomEvent },
  window: { __taskmate_sounds: { play: (name) => played.push(name) } },
});
const Card = loaded.get("taskmate-sticker-chart-card");

function cardFor(config) {
  const calls = [];
  const card = new Card();
  card.setConfig({ entity: ENTITY, child_id: "k1", ...config });
  card.hass = {
    language: "en",
    callService: async (domain, service, data) => { calls.push({ domain, service, data }); },
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          points_name: "Gems",
          children: [{ id: "k1", name: "Malia", points: 5 }],
          chores: [{ id: "bed", name: "Make bed", points: 2, enabled: true, requires_approval: false }],
          todays_completions: [],
        },
      },
    },
  };
  card.dayCompletions = [];
  return { card, calls };
}

async function tick(card) {
  const attrs = card._attrs();
  const child = attrs.children[0];
  const row = card._todaysChores(child, attrs)[0];
  await card._complete(child, row);
  return row;
}

test("ticking a past day logs it with completed_date and says the day changed", async () => {
  const { card, calls } = cardFor({ date: "2026-09-14" });
  let changed = 0;
  card.dispatchEvent = (e) => { if (e.type === "taskmate-day-changed") changed += 1; return true; };
  await tick(card);
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [
    { domain: "taskmate", service: "complete_chore", data: { chore_id: "bed", child_id: "k1", as_parent: true, completed_date: "2026-09-14" } },
  ]);
  assert.equal(changed, 1);
});

test("ticking a past day plays no sound and starts no celebration", async () => {
  played.length = 0;
  const { card } = cardFor({ date: "2026-09-14" });
  await tick(card);
  assert.deepEqual(played, []);
  assert.equal(card._celebrating, null);
  assert.equal(card._confetti.length, 0);
});

test("ticking today still plays the chime and celebrates", async () => {
  played.length = 0;
  const { card } = cardFor({});
  await tick(card);
  assert.deepEqual(played, ["coin"]);
  assert.ok(card._celebrating, "the pop-up shows");
});

test("undoing on a past day is silent too", async () => {
  played.length = 0;
  const { card } = cardFor({ date: "2026-09-14" });
  card.dayCompletions = [{ completion_id: "c1", chore_id: "bed", child_id: "k1", approved: true }];
  card.dispatchEvent = () => true;
  const attrs = card._attrs();
  const row = card._todaysChores(attrs.children[0], attrs)[0];
  await card._undo(row);
  assert.deepEqual(played, []);
});

// ── Which jobs are offered ───────────────────────────────────────────────────

function rowsFor(chores, { config = {}, child = {} } = {}) {
  const { card } = cardFor(config);
  const attrs = card._attrs();
  attrs.chores = chores.map((c) => ({ enabled: true, requires_approval: false, ...c }));
  const kid = { ...attrs.children[0], ...child };
  return card._todaysChores(kid, attrs);
}

test("an open-ended chore is not offered as a tile (its note can't be taken there)", () => {
  const rows = rowsFor([{ id: "a", name: "Make bed", points: 2 }, { id: "o", name: "Extra", points: 0, open_ended: true }]);
  assert.deepEqual([...rows.map((r) => r.chore.id)], ["a"]);
});

test("a weekly-target chore whose quota earlier days filled has nothing left to tick", () => {
  const chore = { id: "w", name: "Read", points: 2, weekly_target: 3 };
  assert.equal(rowsFor([chore], { child: { weekly_chore_progress: { w: 3 } } }).length, 0);
});

test("a weekly-target chore with quota left is offered, capped at what's left", () => {
  const chore = { id: "w", name: "Read", points: 2, weekly_target: 3, daily_limit: 5 };
  const rows = rowsFor([chore], { child: { weekly_chore_progress: { w: 2 } } });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].limit, 0 + 1, "one left in the week, however high the daily limit");
});

test("a past day does not offer a team chore, which can't be reconstructed", () => {
  const team = { id: "t", name: "Wash up", points: 2, team: { size: 2 } };
  assert.equal(rowsFor([team], { config: { date: "2026-09-14" } }).length, 0);
  assert.equal(rowsFor([team]).length, 1, "today it is still offered: tapping joins the team");
});

// ── The panel's dialog ───────────────────────────────────────────────────────

const panelLoaded = (() => {
  let created = 0;
  const makeCard = () => {
    created += 1;
    return {
      setConfig() { if (!this._ok) throw new Error("Please define an entity"); },
      addEventListener() {},
      _ok: true,
    };
  };
  const res = loadCard("taskmate-panel.js", {
    sandbox: {
      document: {
        createElement: () => makeCard(),
        querySelector: () => null,
        querySelectorAll: () => [],
        addEventListener() {},
        head: { appendChild() {} },
      },
    },
  });
  res.created = () => created;
  return res;
})();
const Panel = panelLoaded.get("taskmate-panel");

function panelWith({ hass, host = { parentNode: null, appendChild() {} } } = {}) {
  const panel = Object.create(Panel.prototype);
  panel._hass = hass || { language: "en", states: {} };
  panel._dialog = { kind: "backdate", data: { child_id: "k1", day: "2026-09-14", chore_id: "" } };
  panel._state = { children: [{ id: "k1", name: "Malia" }], chores: [] };
  panel._t = (key) => key;
  panel.querySelector = (sel) => (sel === ".tm-backdate-host" ? host : null);
  panel._refreshBackdateDay = () => {};
  panel._hashDialog = () => "h";
  return panel;
}

const withOverview = { language: "en", states: { [ENTITY]: { state: "ok", attributes: { points_name: "Gems", children: [] } } } };

test("mounting before the card module has loaded does nothing, and does not throw", () => {
  panelLoaded.elements.delete("taskmate-sticker-chart-card");
  const before = panelLoaded.created();
  const panel = panelWith({ hass: withOverview });
  assert.doesNotThrow(() => panel._mountBackdateCard());
  assert.equal(panelLoaded.created(), before, "no element is made for a module that isn't there");
  assert.equal(panel._backdateCard, undefined);
  assert.notEqual(panel._backdateUseList, true, "it's still loading, not failed");
});

test("a missing overview sensor drops the dialog to the plain list instead of throwing", async () => {
  panelLoaded.elements.set("taskmate-sticker-chart-card", function Card() {});
  const panel = panelWith({ hass: { language: "en", states: {} } });
  let rendered = 0;
  panel._render = () => { rendered += 1; };
  assert.doesNotThrow(() => panel._mountBackdateCard());
  assert.equal(panel._backdateUseList, true);
  await new Promise((resolve) => setTimeout(resolve, 5));
  assert.equal(rendered, 1, "re-rendered once, on the next turn, to show the list");
});

test("a card whose setConfig throws is handled the same way", () => {
  panelLoaded.elements.set("taskmate-sticker-chart-card", function Card() {});
  const panel = panelWith({ hass: withOverview });
  panel._backdateCard = { setConfig() { throw new Error("boom"); }, addEventListener() {} };
  panel._render = () => {};
  assert.doesNotThrow(() => panel._mountBackdateCard());
  assert.equal(panel._backdateUseList, true);
});

test("with the module and the sensor present the card is mounted and given its day", () => {
  panelLoaded.elements.set("taskmate-sticker-chart-card", function Card() {});
  const appended = [];
  const host = { parentNode: null, appendChild: (el) => appended.push(el) };
  const panel = panelWith({ hass: withOverview, host });
  panel._mountBackdateCard();
  assert.equal(panel._backdateUseList, undefined);
  assert.equal(appended.length, 1);
  assert.equal(panel._backdateKey, "k1|2026-09-14");
});

// ── The day picker follows Home Assistant's clock, not the browser's ────────

const dayBefore = (tz) => {
  const [y, m, d] = new Date().toLocaleDateString("en-CA", { timeZone: tz }).split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d - 1, 12)).toISOString().slice(0, 10);
};

for (const tz of ["Pacific/Kiritimati", "Pacific/Pago_Pago", "Europe/London"]) {
  test(`the day picker starts the day before today in ${tz}`, () => {
    const panel = panelWith({ hass: { language: "en", config: { time_zone: tz }, states: {} } });
    const days = panel._backdateDays();
    assert.equal(days.length, 7);
    assert.equal(days[0].v, dayBefore(tz));
    // Seven consecutive days, newest first, and never today itself.
    for (let i = 1; i < days.length; i++) {
      assert.equal(new Date(days[i - 1].v) - new Date(days[i].v), 86400e3);
    }
    assert.ok(!days.some((d) => d.v === new Date().toLocaleDateString("en-CA", { timeZone: tz })));
  });
}

test("each offered day carries the weekday the backend will check", () => {
  const panel = panelWith({ hass: { language: "en", config: { time_zone: "Europe/London" }, states: {} } });
  for (const day of panel._backdateDays()) {
    const weekday = new Date(`${day.v}T12:00:00Z`).toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" });
    assert.equal(day.dow, weekday.toLowerCase());
  }
});
