// Kid onboarding tour: the shared helpers in taskmate-tour.js (start rules,
// step selection, tooltip placement, the per-browser flag) and its wiring
// into BOTH child-card render paths (classic + every designed style) and the
// kiosk's child screen.

const assert = require("node:assert/strict");
const { test } = require("node:test");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const { loadCard, render, WWW } = require("./harness.cjs");

const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const ENTITY = "sensor.taskmate_overview";

function tourModule() {
  const store = {};
  const window = {
    localStorage: {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; },
    },
  };
  vm.runInNewContext(readFileSync(path.join(WWW, "taskmate-tour.js"), "utf8"), { window, console });
  return { T: window.__taskmate_tour, store };
}

// ── start rules ────────────────────────────────────────────────────────────

test("starts only while the setting is on and the child hasn't done it", () => {
  const { T } = tourModule();
  const child = { id: "k1", tour_done: false };
  assert.equal(T.shouldStart({ child, attrs: { tour: {} }, config: {} }), true);
  assert.equal(T.shouldStart({ child, attrs: {}, config: {} }), false, "tour off: no overview key");
  assert.equal(T.shouldStart({ child: { id: "k1", tour_done: true }, attrs: { tour: {} }, config: {} }), false);
  assert.equal(T.shouldStart({ child: { id: "k1" }, attrs: { tour: {} }, config: {} }), false, "no tour_done = not offered");
  assert.equal(T.shouldStart({ child, attrs: { tour: {} }, config: { show_tour: false } }), false);
  assert.equal(T.shouldStart({ child: { ...child, is_adult: true }, attrs: { tour: {} }, config: {} }), false);
  assert.equal(T.shouldStart({ child, attrs: { tour: {} }, config: {}, localFlag: { status: "done" } }), false);
});

test("a TaskMate parent's own account never gets a child's tour", () => {
  const { T } = tourModule();
  const child = { id: "k1", tour_done: false };
  const attrs = { tour: {}, parent_user_ids: ["u_mum"] };
  assert.equal(T.shouldStart({ child, attrs, config: {}, userId: "u_mum" }), false);
  assert.equal(T.shouldStart({ child, attrs, config: {}, userId: "u_tablet" }), true);
});

test("steps with nothing to point at are skipped, in order", () => {
  const { T } = tourModule();
  const has = new Set(["hello", "tick", "rewards"]);
  assert.deepEqual([...T.selectSteps(false, (k) => has.has(k))], ["hello", "tick", "rewards"]);
  assert.deepEqual([...T.selectSteps(false, () => true)], ["hello", "tick", "points", "streak", "rewards"]);
  const pre = new Set(["pre_tick", "pre_rewards"]);
  assert.deepEqual([...T.selectSteps(true, (k) => pre.has(k))], ["pre_tick", "pre_rewards"]);
  assert.deepEqual([...T.selectSteps(true, () => true)], ["pre_tick", "pre_points", "pre_rewards"]);
});

// ── placement ─────────────────────────────────────────────────────────────

test("the tooltip goes below the anchor when it fits", () => {
  const { T } = tourModule();
  const p = T.place({ top: 80, left: 16, width: 340, height: 60 }, { width: 300, height: 150 }, { width: 375, height: 600 });
  assert.equal(p.side, "below");
  assert.equal(p.top, 80 + 60 + 12);
  assert.ok(p.left >= 8 && p.left + p.width <= 375 - 8);
  assert.ok(p.arrow >= 18 && p.arrow <= p.width - 18);
});

test("it flips above when there's no room below", () => {
  const { T } = tourModule();
  const p = T.place({ top: 400, left: 16, width: 200, height: 60 }, { width: 300, height: 150 }, { width: 375, height: 520 });
  assert.equal(p.side, "above");
  assert.equal(p.top, 400 - 12 - 150);
});

test("on a short card it overlaps rather than leaving the card, with no arrow", () => {
  const { T } = tourModule();
  const p = T.place({ top: 60, left: 0, width: 300, height: 120 }, { width: 300, height: 170 }, { width: 320, height: 260 });
  assert.equal(p.side, "over");
  assert.equal(p.arrow, null);
  assert.ok(p.top >= 8 && p.top + 170 <= 260);
});

test("it never runs off the sides of a narrow card", () => {
  const { T } = tourModule();
  const p = T.place({ top: 10, left: 300, width: 40, height: 30 }, { width: 300, height: 100 }, { width: 320, height: 600 });
  assert.equal(p.width, 300);
  assert.equal(p.left, 12);
  assert.ok(p.arrow <= p.width - 18);
  const tiny = T.place({ top: 10, left: 0, width: 40, height: 30 }, { width: 300, height: 100 }, { width: 200, height: 600 });
  assert.equal(tiny.width, 184);
  assert.equal(tiny.left, 8);
});

test("no anchor centres the tooltip", () => {
  const { T } = tourModule();
  const p = T.place(null, { width: 300, height: 100 }, { width: 400, height: 500 });
  assert.equal(p.side, "center");
  assert.equal(p.left, 50);
  assert.equal(p.top, 200);
});

// ── the per-browser flag ──────────────────────────────────────────────────

test("the browser flag bridges a slow write, then gives way to the server", () => {
  const { T } = tourModule();
  const calls = [];
  const hass = { callWS: async (m) => { calls.push(m); return {}; } };
  T.writeFlag("k1", "skipped", 2);
  // Server hasn't caught up: the flag still blocks, and the write is retried once.
  assert.deepEqual({ ...T.syncFlag(hass, { id: "k1", tour_done: false }) }, { status: "skipped", step: 2 });
  T.syncFlag(hass, { id: "k1", tour_done: false });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].type, "taskmate/tour/mark");
  assert.equal(calls[0].status, "skipped");
  // Server has it: the flag is dropped, so a parent's "Show again" works here too.
  assert.equal(T.syncFlag(hass, { id: "k1", tour_done: true }), null);
  assert.equal(T.readFlag("k1"), null);
  assert.equal(T.syncFlag(hass, { id: "k1", tour_done: false }), null);
});

test("speak sends a step key and the language, never words", async () => {
  const { T } = tourModule();
  const calls = [];
  await T.speak({ locale: { language: "de" }, callWS: async (m) => { calls.push(m); } }, "k1", "tick");
  assert.deepEqual({ ...calls[0] }, { type: "taskmate/tour/speak", child_id: "k1", step: "tick", language: "de" });
});

// ── wiring: child card, both render paths ─────────────────────────────────

/** The `.opts` object bound to <taskmate-tour>, if the template has one. */
function findTour(tree) {
  if (!tree || typeof tree !== "object") return null;
  if (Array.isArray(tree)) {
    for (const t of tree) { const f = findTour(t); if (f) return f; }
    return null;
  }
  if (tree.__tmTemplate) {
    const at = tree.strings.findIndex((s) => s.includes("<taskmate-tour"));
    if (at !== -1) return tree.values[at];
    for (const v of tree.values) { const f = findTour(v); if (f) return f; }
  }
  return null;
}

function childCard({ design = "classic", child = {}, attrs = {}, config = {} } = {}) {
  const { T } = tourModule();
  const ws = [];
  const ChildCard = loadCard("taskmate-child-card.js", { window: { __taskmate_tour: T } }).get("taskmate-child-card");
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design, ...config });
  card.hass = {
    user: { id: "u_tablet" },
    callWS: async (m) => { ws.push(m); return {}; },
    states: { [ENTITY]: { state: "ok", attributes: {
      children: [{ id: "kid1", name: "Mia", points: 4, chore_order: [], tour_done: false, ...child }],
      chores: [{ id: "bed", name: "Make bed", points: 2, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", assignment_mode: "everyone" }],
      todays_completions: [], chore_availability: {}, today_day_of_week: "wednesday",
      points_icon: "mdi:coin", points_name: "Coins", tour: { speak: 1, auto: 1 }, ...attrs,
    } } },
    callService: async () => {},
  };
  card._loading = {};
  card._optimisticCompletions = {};
  return { card, ws, T };
}

for (const design of DESIGNS) {
  test(`child card (${design}) carries the tour while it's due`, () => {
    const { card } = childCard({ design });
    const tree = card.render();
    assert.match(render(tree).markup, /<taskmate-tour/);
    const opts = findTour(tree);
    assert.equal(opts.preReader, false);
    assert.equal(opts.speak, true);
    assert.equal(opts.params.name, "Mia");
    assert.equal(opts.params.points_name, "Coins", "the family's points name, not a hard-coded 'stars'");
    assert.equal(opts.pointsIcon, "mdi:coin");
  });

  test(`child card (${design}) pre-reader gets the pre-reader variant`, () => {
    const { card } = childCard({ design, config: { pre_reader: true } });
    assert.equal(findTour(card.render()).preReader, true);
  });
}

test("child card: no tour when done, when off, or when the card opts out", () => {
  for (const design of ["classic", "playroom"]) {
    assert.doesNotMatch(render(childCard({ design, child: { tour_done: true } }).card.render()).markup, /<taskmate-tour/);
    assert.doesNotMatch(render(childCard({ design, attrs: { tour: undefined } }).card.render()).markup, /<taskmate-tour/);
    assert.doesNotMatch(render(childCard({ design, config: { show_tour: false } }).card.render()).markup, /<taskmate-tour/);
  }
});

test("child card: finishing marks this child and remembers it in the browser", () => {
  const { card, ws, T } = childCard({ design: "cleanpro" });
  findTour(card.render()).onFinish("skipped", 2);
  assert.deepEqual({ ...ws[0] }, { type: "taskmate/tour/mark", child_id: "kid1", status: "skipped", step: 2 });
  assert.equal(T.readFlag("kid1").status, "skipped");
  assert.doesNotMatch(render(card.render()).markup, /<taskmate-tour/, "closed for the rest of the session");
});

test("child card editor offers show_tour, on by default", () => {
  const src = readFileSync(path.join(WWW, "editors/taskmate-child-card-editor.js"), "utf8");
  assert.match(src, /name: 'show_tour', selector: \{ boolean: \{\} \}/);
  assert.match(src, /show_tour: this\.config\.show_tour !== false/);
});

// ── wiring: kiosk ─────────────────────────────────────────────────────────

function kiosk() {
  const { T } = tourModule();
  const ws = [];
  const { get } = loadCard("taskmate-kiosk-card.js", {
    window: { __taskmate_tour: T },
    sandbox: { setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {} },
  });
  const KioskCard = get("taskmate-kiosk-card");
  const card = new KioskCard();
  card.setConfig({ entity: ENTITY });
  card.hass = {
    locale: { language: "en" },
    user: { id: "u_tablet" },
    callWS: async (m) => {
      ws.push(m);
      if (m.type === "taskmate/kiosk/status") return { children: [{ id: "malia", has_pin: false, can_act: true, due: ["dishes"] }] };
      return {};
    },
    callService: async () => {},
    states: { [ENTITY]: { state: "ok", attributes: {
      children: [{ id: "malia", name: "Malia", points: 3, chore_order: [], tour_done: false }],
      chores: [{ id: "dishes", name: "Dishes", points: 5, assigned_to: [] }],
      todays_completions: [], rewards: [], points_icon: "mdi:star", tour: {},
    } } },
  };
  return { card, ws };
}

test("kiosk: the tour shows on the child screen only, and holds the idle timer", async () => {
  const { card } = kiosk();
  await card._refreshStatus();
  assert.doesNotMatch(render(card.render()).markup, /<taskmate-tour/, "not on the picker");
  card._openKid(card._entry("malia"));
  const tree = card.render();
  const opts = findTour(tree);
  assert.ok(opts, "on the child screen");
  assert.equal(opts.speak, false, "no speaker without a read-aloud target");
  card._idle = 0;
  card._tick();
  assert.equal(card._idle, 0, "a child reading the tour isn't idle");
  opts.onFinish("done", 3);
  card._tick();
  assert.equal(card._idle, 1);
});

// ── old-iPad rules (#1126) ────────────────────────────────────────────────

test("the overlay has no animation, no backdrop-filter and no timers", () => {
  const src = readFileSync(path.join(WWW, "taskmate-tour.js"), "utf8");
  const code = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.doesNotMatch(code, /@keyframes|animation\s*:|backdrop-filter|setInterval/);
  assert.match(code, /box-shadow: 0 0 0 9999px/);
});

// ── celebrations come first ───────────────────────────────────────────────

test("kiosk: the tour steps aside while the completion popup or party is up", async () => {
  const { card } = kiosk();
  await card._refreshStatus();
  card._openKid(card._entry("malia"));
  assert.equal(findTour(card.render()).paused, false);
  card._popup = { points: 5 };
  assert.equal(findTour(card.render()).paused, true, "the AWESOME! popup is never dimmed under the scrim");
  card._popup = null;
  card._celebrating = true;
  assert.equal(findTour(card.render()).paused, true);
  card._celebrating = false;
  assert.equal(findTour(card.render()).paused, false, "and it comes back afterwards");
});

for (const design of ["classic", "playroom", "cleanpro"]) {
  test(`child card (${design}): the tour steps aside while the card celebrates`, () => {
    const { card } = childCard({ design });
    card._confetti = [];
    assert.equal(findTour(card.render()).paused, false);
    card._celebrating = "bed";
    assert.equal(findTour(card.render()).paused, true);
  });
}

// ── the "tick" step points at a chore that can be ticked now ─────────────
//
// The anchor is read off the card's rendered markup, so these tests build a
// tiny DOM from the harness's real output for every design: a selector
// engine just big enough for the compound selectors _tourAnchor uses.

function miniDom(markup) {
  const VOID = new Set(["img", "input", "br", "hr", "meta", "link", "source", "wbr"]);
  const root = { tag: "#root", attrs: {}, kids: [], parent: null, text: "" };
  let cur = root;
  const tagRe = /<(\/?)([a-zA-Z][\w-]*)((?:[^>"']|"[^"]*"|'[^']*')*)>/g;
  let last = 0;
  let m;
  const addText = (s) => { for (let n = cur; n; n = n.parent) n.text += s; };
  while ((m = tagRe.exec(markup)) !== null) {
    addText(markup.slice(last, m.index));
    last = tagRe.lastIndex;
    const [, close, rawTag, rawAttrs] = m;
    const tag = rawTag.toLowerCase();
    if (close) {
      let n = cur;
      while (n && n.tag !== tag) n = n.parent;
      if (n && n.parent) cur = n.parent;
      continue;
    }
    const attrs = {};
    for (const a of rawAttrs.matchAll(/([^\s=]+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s>]+))?/g)) {
      let [, name, val] = a;
      if (name === "/") continue;
      val = val === undefined ? "" : val.replace(/^["']|["']$/g, "");
      if (name.startsWith("?")) { if (val.trim() === "true") attrs[name.slice(1)] = ""; continue; }
      if (name.startsWith("@") || name.startsWith(".")) continue;
      attrs[name] = val;
    }
    const el = { tag, attrs, kids: [], parent: cur, text: "" };
    cur.kids.push(el);
    if (!VOID.has(tag) && !rawAttrs.trim().endsWith("/")) cur = el;
  }
  const classes = (n) => (n.attrs.class || "").split(/\s+/).filter(Boolean);
  const matchSimple = (n, part) => {
    const re = /^([a-z][\w-]*)?((?:\.[\w-]+|\[[^\]]+\]|:not\([^)]*\))*)$/;
    const mm = part.trim().match(re);
    if (!mm) throw new Error(`miniDom: unsupported selector "${part}"`);
    if (mm[1] && n.tag !== mm[1]) return false;
    for (const t of mm[2].matchAll(/\.([\w-]+)|\[([\w-]+)(?:="([^"]*)")?\]|:not\(([^)]*)\)/g)) {
      if (t[1] && !classes(n).includes(t[1])) return false;
      if (t[2] && (!(t[2] in n.attrs) || (t[3] !== undefined && n.attrs[t[2]] !== t[3]))) return false;
      if (t[4] && matchSimple(n, t[4])) return false;
    }
    return true;
  };
  const matches = (n, sel) => sel.split(",").some((p) => matchSimple(n, p));
  const all = (n, sel, out = []) => {
    for (const k of n.kids) { if (matches(k, sel)) out.push(wrap(k)); all(k, sel, out); }
    return out;
  };
  const wrap = (n) => ({
    node: n,
    get textContent() { return n.text; },
    classList: { contains: (c) => classes(n).includes(c) },
    getAttribute: (a) => (a in n.attrs ? n.attrs[a] : null),
    getClientRects: () => [{}],
    querySelectorAll: (sel) => all(n, sel),
    querySelector: (sel) => all(n, sel)[0] || null,
  });
  return wrap(root);
}

function anchorText(card, key) {
  const tree = card.render();
  Object.defineProperty(card, "shadowRoot", { configurable: true, value: miniDom(render(tree).markup) });
  const el = findTour(tree).resolve(key);
  return el ? `${el.getAttribute("aria-label") || ""} ${el.textContent}`.replace(/\s+/g, " ").trim() : null;
}

const LOCKED_CHORES = [
  { id: "bed", name: "Make bed", points: 2, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", assignment_mode: "everyone" },
  { id: "fish", name: "Feed fish", points: 1, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "recurring", recurrence: "every_2_days", assignment_mode: "everyone" },
  { id: "tidy", name: "Tidy room", points: 3, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", assignment_mode: "everyone", depends_on: ["walk"] },
  { id: "walk", name: "Walk dog", points: 3, time_category: "anytime", assigned_to: [], due_days: [], schedule_mode: "specific_days", assignment_mode: "everyone" },
];
// A completion stamped earlier today (local time), so "done today" checks hold
// whatever day the suite runs on.
const TODAY_8AM = (() => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T08:00:00`;
})();
const BED_DONE = [{ chore_id: "bed", child_id: "kid1", approved: true, completed_at: TODAY_8AM }];

for (const design of DESIGNS) {
  test(`child card (${design}): the tick step skips done, locked and blocked chores`, () => {
    const { card } = childCard({
      design,
      config: { dependency_mode: "dim", recurrence_done_mode: "dim" },
      attrs: { chores: LOCKED_CHORES, todays_completions: BED_DONE, chore_availability: { fish: { kid1: false } } },
    });
    const text = anchorText(card, "tick");
    assert.ok(text, "a chore that can be ticked is found");
    assert.match(text, /Walk dog/);
    assert.doesNotMatch(text, /Make bed|Feed fish|Tidy room/);
  });

  test(`child card (${design}): with nothing to tick, the tick step is left out`, () => {
    const { card } = childCard({
      design,
      config: { dependency_mode: "dim", recurrence_done_mode: "dim" },
      attrs: { chores: LOCKED_CHORES.slice(0, 3), todays_completions: BED_DONE, chore_availability: { fish: { kid1: false } } },
    });
    assert.equal(anchorText(card, "tick"), null, "never a done, locked or blocked row");
  });
}

test("child card pre-reader: the tick step skips done and locked tiles", () => {
  const cfg = { pre_reader: true, dependency_mode: "dim" };
  const chores = LOCKED_CHORES.filter((c) => c.id !== "fish");
  const live = childCard({ config: cfg, attrs: { chores, todays_completions: BED_DONE } }).card;
  assert.match(anchorText(live, "pre_tick"), /Walk dog/);
  const none = childCard({ config: cfg, attrs: { chores: chores.filter((c) => c.id !== "walk"), todays_completions: BED_DONE } }).card;
  assert.equal(anchorText(none, "pre_tick"), null);
});

test("kiosk: the tick step only points at a row with a live Done button", async () => {
  const { card } = kiosk();
  const attrs = card.hass.states[ENTITY].attributes;
  attrs.chores = [{ id: "dishes", name: "Dishes", points: 5, assigned_to: [] }, { id: "bins", name: "Bins", points: 2, assigned_to: [] }];
  attrs.todays_completions = [{ chore_id: "dishes", child_id: "malia", approved: true, completed_at: TODAY_8AM }];
  card.hass.callWS = async (m) => (m.type === "taskmate/kiosk/status"
    ? { children: [{ id: "malia", has_pin: false, can_act: true, due: ["bins"] }] } : {});
  await card._refreshStatus();
  card._openKid(card._entry("malia"));
  assert.match(anchorText(card, "tick"), /Bins/);
  attrs.chores = attrs.chores.slice(0, 1);
  assert.equal(anchorText(card, "tick"), null, "a done row is never the 'tap here' row");
});

test("the scrim stays under Home Assistant's toolbar (z-index 4) and dialogs", () => {
  const src = readFileSync(path.join(WWW, "taskmate-tour.js"), "utf8");
  const host = src.match(/:host \{[^}]*\}/);
  assert.ok(host, "the overlay's :host rule");
  const z = Number((host[0].match(/z-index:\s*(\d+)/) || [])[1]);
  assert.ok(z >= 1 && z < 4, `z-index ${z} must beat the card's rows but stay under HA's app toolbar`);
});
