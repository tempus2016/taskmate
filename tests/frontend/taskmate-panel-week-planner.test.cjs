// Week planner (admin panel): which chore falls on which day, what a drop
// plans, and how the planned changes become one taskmate/planner/apply call.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, localize } = require("./harness.cjs");

// The panel runs in its own vm realm: compare plain copies of its arrays/objects.
const same = (actual, expected, msg) => assert.deepEqual(JSON.parse(JSON.stringify(actual)), expected, msg);

const TaskMatePanel = loadCard("taskmate-panel.js").get("taskmate-panel");

// 2026-11-02 is a Monday; "today" is Tuesday 3 Nov.
const MON = "2026-11-02";
const TUE = "2026-11-03";
const WED = "2026-11-04";
const THU = "2026-11-05";
const FRI = "2026-11-06";
const SUN = "2026-11-08";
const TODAY = TUE;

function panel(chores = [], children = null) {
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => localize(key, params);
  p._hass = { locale: { language: "en-GB" } };
  p._scope = "";
  p._state = {
    children: children || [
      { id: "malia", name: "Malia", color: "#e53935" },
      { id: "vaiha", name: "Vaiha", color: "#1e88e5" },
      { id: "mum", name: "Mum", is_adult: true },
    ],
    chores,
    chore_display_order: [],
    settings: { points_name: "Stars" },
  };
  return p;
}

const walk = (extra = {}) => ({ id: "walk", name: "Walk dog", points: 5, schedule_mode: "specific_days", due_days: ["tuesday"], assigned_to: [], assignment_mode: "everyone", ...extra });

const onDays = (p, c) => p._plWeekDays(MON).filter(iso => p._plOccurs(c, iso, TODAY));

// ── Week occurrences ────────────────────────────────────────────────────────

test("dates: Monday-first weekdays and week starts", () => {
  const p = panel();
  assert.equal(p._plDow(MON), 0);
  assert.equal(p._plDow(SUN), 6);
  assert.equal(p._plWeekStart(THU), MON);
  assert.equal(p._plWeekStart(MON), MON);
  same(p._plWeekDays(MON), [MON, TUE, WED, THU, FRI, "2026-11-07", SUN]);
  assert.equal(p._plAddDays("2026-03-28", 2), "2026-03-30", "no DST slip");
});

test("specific days, daily, and a chore created later", () => {
  const p = panel();
  same(onDays(p, walk({ due_days: ["tuesday", "friday"] })), [TUE, FRI]);
  assert.equal(onDays(p, walk({ due_days: [] })).length, 7);
  same(onDays(p, walk({ due_days: [], created_date: THU })), [THU, FRI, "2026-11-07", SUN]);
  same(onDays(p, walk({ enabled: false })), []);
});

test("one-off chores sit on their date", () => {
  const p = panel();
  same(onDays(p, { id: "g", schedule_mode: "one_shot", created_date: WED }), [WED]);
  same(onDays(p, { id: "g", schedule_mode: "one_shot", created_date: "2026-11-20" }), []);
});

test("recurring: pinned weekday, every 2 weeks, every N days, monthly", () => {
  const p = panel();
  const rec = (extra) => ({ id: "r", schedule_mode: "recurring", ...extra });
  same(onDays(p, rec({ recurrence: "weekly", recurrence_day: "thursday" })), [THU]);
  // Every 2 weeks from 26 Oct (a Monday): on this week's Monday, not next week's.
  same(onDays(p, rec({ recurrence: "every_2_weeks", recurrence_day: "monday", recurrence_start: "2026-10-26" })), []);
  same(onDays(p, rec({ recurrence: "every_2_weeks", recurrence_day: "monday", recurrence_start: "2026-10-19" })), [MON]);
  same(onDays(p, rec({ recurrence: "every_3_days", recurrence_start: "2026-11-01" })), [WED, "2026-11-07"]);
  // No start date: created_date anchors the rhythm (ERR-2).
  same(onDays(p, rec({ recurrence: "every_2_days", created_date: MON })), [MON, WED, FRI, SUN]);
  same(onDays(p, rec({ recurrence: "monthly", recurrence_start: "2026-10-05" })), [THU]);
  // 31st in a 30-day month lands on the 30th.
  assert.equal(p._plOccurs(rec({ recurrence: "monthly", recurrence_start: "2026-01-31" }), "2026-11-30", TODAY), true);
  // Weekly with no day: the backend projects today's weekday.
  same(onDays(p, rec({ recurrence: "weekly" })), [TUE]);
});

test("calendar moves outrank the schedule", () => {
  const p = panel();
  const c = walk({ moved_occurrences: { [TUE]: THU } });
  same(onDays(p, c), [THU]);
  assert.equal(p._plOrigin(c, THU), TUE);
  same(onDays(p, walk({ moved_occurrences: { [TUE]: "" } })), []);
});

test("the week view: rail, picks, colours, points and minutes per day", () => {
  const p = panel([
    walk({ due_days: ["monday"], assigned_to: ["malia"], estimated_minutes: 10 }),
    { id: "bed", name: "Make bed", points: 2, schedule_mode: "specific_days", due_days: [], assigned_to: [], estimated_minutes: 5 },
    { id: "dish", name: "Dishes", points: 3, schedule_mode: "specific_days", due_days: ["monday"], assignment_mode: "alternating", assigned_to: ["malia", "vaiha"] },
    { id: "win", name: "Windows", points: 8, schedule_mode: "recurring", recurrence: "monthly", recurrence_start: "2026-10-20" },
    { id: "gift", name: "Gift", points: 5, schedule_mode: "one_shot", created_date: "2026-11-20" },
    { id: "off", name: "Off", points: 1, schedule_mode: "specific_days", due_days: ["monday"], enabled: false },
  ]);
  const kids = p._plKids();
  same(kids.map(k => k.id), ["malia", "vaiha"], "adults are left out");
  const picks = { [MON]: { dish: "vaiha" } };
  const view = p._plWeekView(p._state.chores, MON, TODAY, picks, kids);
  const mon = view.days[0];
  same(mon.items.map(i => i.c.id), ["walk", "bed", "dish"]);
  same(mon.items.map(i => i.who), ["malia", "", "vaiha"]);
  // Make bed is everyone's: 2 each. Walk dog 5 to Malia, Dishes 3 to Vaiha.
  same(mon.points, { malia: 7, vaiha: 5 });
  // 10 for Malia's walk + 5 × 2 children for the beds.
  assert.equal(mon.minutes, 20);
  same(view.railOff.map(c => c.id), ["win"]);
  same(view.railOneOff.map(c => c.id), ["gift"]);
  assert.equal(p._plIsSeries(p._state.chores[1]), true, "daily is striped");
  assert.equal(p._plIsSeries(p._state.chores[0]), false);
});

// ── Drops become planned changes ────────────────────────────────────────────

test("moving a set-weekday chore moves that weekday; Alt copies it", () => {
  const p = panel();
  const c = walk({ due_days: ["tuesday", "saturday"] });
  const move = p._plDropOps({ c, from: TUE, to: WED, copy: false, toChild: "", today: TODAY });
  same(move.ops, [{ kind: "days", id: "walk", from: "tuesday", to: "wednesday", copy: false }]);
  same(p._plApplyOp(c, move.ops[0]).due_days, ["wednesday", "saturday"]);
  const copy = p._plDropOps({ c, from: TUE, to: MON, copy: true, toChild: "", today: TODAY });
  same(p._plApplyOp(c, copy.ops[0]).due_days, ["monday", "tuesday", "saturday"]);
  // A day it's already on is refused rather than merged away.
  assert.equal(p._plDropOps({ c, from: TUE, to: "2026-11-07", copy: false, toChild: "", today: TODAY }).error, "already");
});

test("from the rail a weekday is added; a one-off takes the date", () => {
  const p = panel();
  const c = walk({ due_days: ["saturday"], id: "sat" });
  const add = p._plDropOps({ c, from: null, to: WED, copy: false, toChild: "", today: TODAY });
  same(p._plApplyOp(c, add.ops[0]).due_days, ["wednesday", "saturday"]);
  const gift = { id: "gift", name: "Gift", schedule_mode: "one_shot", created_date: "2026-11-20" };
  same(p._plDropOps({ c: gift, from: null, to: THU, copy: false, toChild: "", today: TODAY }).ops,
    [{ kind: "date", id: "gift", from: "2026-11-20", to: THU }]);
  assert.equal(p._plDropOps({ c: gift, from: null, to: MON, copy: false, toChild: "", today: TODAY }).error, "past");
  assert.equal(p._plDropOps({ c: gift, from: null, to: THU, copy: true, toChild: "", today: TODAY }).error, "copy_one_off");
});

test("a repeating chore asks, and this-week-only is offered from today on", () => {
  const p = panel();
  const c = { id: "pl", name: "Plants", schedule_mode: "recurring", recurrence: "every_3_days", recurrence_start: "2026-11-01" };
  const ask = p._plDropOps({ c, from: WED, to: THU, copy: false, toChild: "", today: TODAY });
  assert.equal(ask.ask, "series");
  assert.equal(ask.onceOk, true);
  const once = p._plSeriesOps(c, "once", WED, THU, TODAY);
  same(once, [{ kind: "once", id: "pl", origin: WED, to: THU }]);
  same(onDays(p, p._plApplyOp(c, once[0])), [THU, "2026-11-07"]);
  const series = p._plSeriesOps(c, "series", WED, THU, TODAY);
  const shifted = p._plApplyOp(c, series[0]);
  assert.equal(shifted.recurrence_start, "2026-11-02");
  same(onDays(p, shifted), [MON, THU, SUN]);
  // A past occurrence can only move as a series.
  const past = p._plDropOps({ c: { ...c, recurrence_start: "2026-10-30" }, from: MON, to: WED, copy: false, toChild: "", today: TODAY });
  assert.equal(past.onceOk, false);
  assert.equal(p._plDropOps({ c, from: WED, to: THU, copy: true, toChild: "", today: TODAY }).error, "copy_series");
});

test("a weekly series moves its weekday, every 2 weeks keeps its fortnight", () => {
  const p = panel();
  const weekly = { id: "h", schedule_mode: "recurring", recurrence: "weekly", recurrence_day: "tuesday" };
  same(p._plSeriesPatch(weekly, TUE, WED), { recurrence_day: "wednesday" });
  const fort = { id: "f", schedule_mode: "recurring", recurrence: "every_2_weeks", recurrence_day: "monday", recurrence_start: "2026-10-19" };
  const moved = p._plApplyOp(fort, p._plSeriesOps(fort, "series", MON, WED, TODAY)[0]);
  same(onDays(p, moved), [WED]);
  assert.equal(p._plOccurs(moved, "2026-11-11", TODAY), false, "still every other week");
  // From the rail, the series starts on the drop day.
  const monthly = { id: "m", schedule_mode: "recurring", recurrence: "monthly", recurrence_start: "2026-10-20" };
  same(p._plSeriesPatch(monthly, null, FRI), { recurrence_start: FRI });
});

test("a change that wouldn't land on the day is refused", () => {
  const p = panel();
  // Created on Thursday: adding Wednesday this week can't show on Wednesday.
  const c = walk({ due_days: ["friday"], created_date: THU });
  assert.equal(p._plDropOps({ c, from: null, to: WED, copy: false, toChild: "", today: TODAY }).error, "no_land");
  // Daily: there's nowhere to move it.
  assert.equal(p._plDropOps({ c: walk({ due_days: [], moved_occurrences: { [WED]: "" } }), from: TUE, to: WED, copy: false, toChild: "", today: TODAY }).error, "daily");
});

test("with a child picked, a drop reassigns where the mode allows it", () => {
  const p = panel();
  const c = walk({ assigned_to: ["vaiha"] });
  const r = p._plDropOps({ c, from: TUE, to: WED, copy: false, toChild: "malia", today: TODAY });
  same(r.ops.map(op => op.kind), ["days", "assign"]);
  same(p._plWorking([c], r.ops)[0].assigned_to, ["malia"]);
  // Same day: reassign only.
  same(p._plDropOps({ c, from: TUE, to: TUE, copy: false, toChild: "malia", today: TODAY }).ops,
    [{ kind: "assign", id: "walk", from: ["vaiha"], to: "malia" }]);
  // Already theirs: nothing.
  same(p._plDropOps({ c, from: TUE, to: TUE, copy: false, toChild: "vaiha", today: TODAY }).ops, []);
  // A rotation chore moves but keeps its rotation, and says so.
  const turn = walk({ assignment_mode: "alternating", assigned_to: ["malia", "vaiha"] });
  const rot = p._plDropOps({ c: turn, from: TUE, to: WED, copy: false, toChild: "malia", today: TODAY });
  same(rot.ops.map(op => op.kind), ["days"]);
  assert.equal(rot.note, "keep_assign");
});

// ── Planned changes → the save payload ──────────────────────────────────────

test("changes merge per chore into taskmate/planner/apply payloads", () => {
  const base = [
    walk({ due_days: ["tuesday"], assigned_to: ["vaiha"] }),
    { id: "pl", name: "Plants", schedule_mode: "recurring", recurrence: "every_3_days", recurrence_start: "2026-11-01" },
    { id: "gift", name: "Gift", schedule_mode: "one_shot", created_date: "2026-11-20" },
  ];
  const p = panel(base);
  const ops = [
    { kind: "days", id: "walk", from: "tuesday", to: "wednesday", copy: false },
    { kind: "assign", id: "walk", from: ["vaiha"], to: "malia" },
    { kind: "once", id: "pl", origin: WED, to: THU },
    { kind: "date", id: "gift", from: "2026-11-20", to: FRI },
  ];
  same(p._plPatches(base, ops), [
    { chore_id: "walk", due_days: ["wednesday"], assigned_to: ["malia"] },
    { chore_id: "pl", moves: [{ origin: WED, date: THU }] },
    { chore_id: "gift", created_date: FRI },
  ]);
});

test("a series shift sends its fields; moving back cancels out", () => {
  const base = [{ id: "h", name: "Hoover", schedule_mode: "recurring", recurrence: "weekly", recurrence_day: "tuesday" }];
  const p = panel(base);
  const ops = [{ kind: "series", id: "h", from: TUE, to: WED }];
  same(p._plPatches(base, ops), [{ chore_id: "h", recurrence_day: "wednesday" }]);
  const back = [...ops, { kind: "series", id: "h", from: WED, to: TUE }];
  same(p._plPatches(base, back), []);
  same(p._plCompact(base, back), [], "a round trip leaves nothing to save");
});

test("moving an already-moved occurrence back home sends a move to its origin", () => {
  const base = [walk({ moved_occurrences: { [TUE]: THU } })];
  const p = panel(base);
  const r = p._plDropOps({ c: base[0], from: THU, to: TUE, copy: false, toChild: "", today: TODAY });
  same(r.ops, [{ kind: "once", id: "walk", origin: TUE, to: TUE }]);
  same(p._plPatches(base, r.ops), [{ chore_id: "walk", moves: [{ origin: TUE, date: TUE }] }]);
});

test("each change reads as words in the save bar", () => {
  const p = panel([walk()]);
  const c = p._state.chores[0];
  assert.equal(p._plDescribe({ kind: "days", id: "walk", from: "tuesday", to: "wednesday", copy: false }, c), "Walk dog: Tuesday → Wednesday, every week");
  assert.equal(p._plDescribe({ kind: "days", id: "walk", from: null, to: "friday", copy: true }, c), "Walk dog: added on Friday, every week");
  assert.equal(p._plDescribe({ kind: "assign", id: "walk", from: [], to: "malia" }, c), "Walk dog: everyone → Malia");
  assert.match(p._plDescribe({ kind: "once", id: "walk", origin: WED, to: THU }, c), /this week only$/);
});

test("saving sends one batch, keeps refused changes and shows why", async () => {
  const base = [walk({ assigned_to: ["vaiha"] }), walk({ id: "bins", name: "Bins", due_days: ["monday"] })];
  const p = panel(base);
  const sent = [];
  let fetched = 0;
  p._plS().ops = [
    { kind: "days", id: "walk", from: "tuesday", to: "wednesday", copy: false },
    { kind: "days", id: "bins", from: "monday", to: "friday", copy: false },
  ];
  p._render = () => {};
  p._showToast = () => {};
  p._fetchState = async () => { fetched += 1; };
  p._callWS = async (msg) => {
    sent.push(msg);
    return { ok: true, res: { applied: 1, results: [{ chore_id: "walk", ok: true }, { chore_id: "bins", ok: false, code: "past_date", error: "x" }] } };
  };
  await p._plSave();
  assert.equal(sent.length, 1);
  assert.equal(sent[0].type, "taskmate/planner/apply");
  same(sent[0].changes.map(c => c.chore_id), ["walk", "bins"]);
  assert.equal(fetched, 1);
  same(p._plS().ops.map(op => op.id), ["bins"]);
  assert.equal(p._plS().errors.bins, localize("planner.save_err_past_date"));
});

test("the planner tab renders days, rail and the save bar", () => {
  const p = panel([walk({ due_days: ["tuesday"], assigned_to: ["malia"] }), { id: "gift", name: "Gift", points: 5, schedule_mode: "one_shot", created_date: "2026-11-20" }]);
  p._plTodayIso = () => TODAY;
  p._childColor = (id) => ({ malia: "#e53935", vaiha: "#1e88e5" })[id] || "#999";
  p._scopeId = () => "";
  p._sortChoresByDisplayOrder = (c) => c;
  p._fmtNum = (n) => String(n);
  p._pointsName = () => "Stars";
  p._esc = (s) => String(s);
  p._mdi = (i) => `<ha-icon icon="${i}"></ha-icon>`;
  p._plS().picks[MON] = {};
  p._plS().ops = [{ kind: "days", id: "walk", from: "tuesday", to: "wednesday", copy: false }];
  const html = p._renderPlannerTab();
  assert.equal((html.match(/data-pl-drop="day"/g) || []).length, 7);
  assert.match(html, /tm-pl-today/);
  // The pending move already shows on Wednesday, with Malia's colour.
  const wed = html.split('data-pl-drop="day" data-iso="2026-11-04"')[1].split("</section>")[0];
  assert.match(wed, /Walk dog/);
  assert.match(wed, /--kc:#e53935/);
  assert.match(html, /1 unsaved change/);
  assert.match(html, /Walk dog: Tuesday → Wednesday, every week/);
  assert.match(html.split("tm-pl-rail")[1].split("</aside>")[0], /Gift/);
});

test("the planner is a page in the Earn section with a manual page", () => {
  const p = panel();
  p._needsYouCount = () => 0;
  const earn = p._sidebarGroups().find(g => g.key === "earn");
  const ids = earn.items.map(i => i.id);
  assert.equal(ids[ids.indexOf("chores") + 1], "planner");
});

// ── Touch press-and-hold and auto-scroll ────────────────────────────────────

test("a mouse drags as soon as it moves a few px", () => {
  const p = panel();
  assert.equal(p._plGesture({ touch: false, held: false, dist: 3 }), "wait");
  assert.equal(p._plGesture({ touch: false, held: false, dist: 6 }), "drag");
});

test("touch and pen wait for a press-and-hold; moving first is a scroll", () => {
  const p = panel();
  // Before the hold: a little jitter waits, a real move gives the page back.
  assert.equal(p._plGesture({ touch: true, held: false, dist: 0 }), "wait");
  assert.equal(p._plGesture({ touch: true, held: false, dist: 8 }), "wait");
  assert.equal(p._plGesture({ touch: true, held: false, dist: 9 }), "cancel");
  assert.equal(p._plGesture({ touch: true, held: false, dist: 200 }), "cancel");
  // After the hold the card is lifted: any move drags.
  assert.equal(p._plGesture({ touch: true, held: true, dist: 0 }), "wait");
  assert.equal(p._plGesture({ touch: true, held: true, dist: 1 }), "drag");
});

test("a touch pointerdown lifts the card only after the hold time", async () => {
  // A panel whose document can take listeners, as the drag code adds them there.
  const doc = { addEventListener() {}, removeEventListener() {}, querySelector: () => null, querySelectorAll: () => [], createElement: () => ({ style: {} }) };
  const Panel = loadCard("taskmate-panel.js", { sandbox: { document: doc } }).get("taskmate-panel");
  const p = Object.create(Panel.prototype);
  p._state = { children: [], chores: [] };
  p.classList = { add() {}, remove() {} };
  p.querySelectorAll = () => [];
  p._activeTab = "planner";
  p._plPhone = () => false;
  const classes = new Set();
  const card = { dataset: { id: "walk", from: TUE }, classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c) } };
  const target = { closest: (sel) => (sel === ".tm-pl-card" ? card : null) };
  p._onPointerDown({ pointerType: "touch", button: 0, target, pointerId: 1, clientX: 10, clientY: 10 });
  assert.equal(p._plDrag.touch, true);
  assert.equal(p._plDrag.held, false);
  await new Promise(r => setTimeout(r, 150));
  assert.equal(p._plDrag.held, false, "not yet");
  await new Promise(r => setTimeout(r, 250));
  assert.equal(p._plDrag.held, true);
  assert.ok(classes.has("tm-pl-lifted"), "lifted cue");
  p._plEndDrag();
  assert.ok(!classes.has("tm-pl-lifted"));
  // A mouse never waits for a hold.
  p._onPointerDown({ pointerType: "mouse", button: 0, target, pointerId: 2, clientX: 10, clientY: 10 });
  assert.equal(p._plDrag.touch, false);
  assert.equal(p._plDrag.timer, null);
  p._plEndDrag();
});

test("only a lifted or dragging touch blocks scrolling", () => {
  const p = panel();
  let prevented = 0;
  const ev = { cancelable: true, preventDefault: () => { prevented += 1; } };
  p._plDrag = { held: false, started: false };
  p._plOnTouchMove(ev);
  assert.equal(prevented, 0);
  p._plDrag.held = true;
  p._plOnTouchMove(ev);
  assert.equal(prevented, 1);
  p._plDrag = null;
});

test("auto-scroll speeds up towards the edges and stops in the middle", () => {
  const p = panel();
  assert.equal(p._plEdgeSpeed(500, 0, 1000), 0);
  assert.ok(p._plEdgeSpeed(10, 0, 1000) < 0);
  assert.ok(p._plEdgeSpeed(990, 0, 1000) > 0);
  assert.ok(p._plEdgeSpeed(2, 0, 1000) < p._plEdgeSpeed(40, 0, 1000), "faster nearer the edge");
  assert.equal(p._plEdgeSpeed(-50, 0, 1000), -18, "capped beyond the edge");
  assert.equal(p._plEdgeSpeed(10, 0, 100), 0, "no auto-scroll in a tiny area");
});

test("a touch drag's hint offers ⋮ → Also on, never the Alt key", () => {
  const Panel = loadCard("taskmate-panel.js", { sandbox: { navigator: { platform: "Win32", userAgent: "" } } }).get("taskmate-panel");
  const p = Object.create(Panel.prototype);
  p._t = (key, params = {}) => localize(key, params);
  p._hass = { locale: { language: "en-GB" } };
  p._scope = "";
  p._state = { children: [], chores: [walk()] };
  const tip = { textContent: "" };
  const hint = (touch) => {
    p._plDrag = { id: "walk", from: TUE, over: { dataset: { iso: WED } }, overKid: "", alt: false, touch, tip };
    p._plHint();
    return tip.textContent;
  };
  const mouse = hint(false);
  assert.match(mouse, /Hold Alt to copy instead/);
  const touch = hint(true);
  assert.doesNotMatch(touch, /Alt/);
  assert.match(touch, /Moving Walk dog/);
  assert.ok(touch.includes(localize("planner.hint_touch")));
  assert.ok(localize("planner.hint_touch").includes(localize("planner.menu_copy")), "names the real menu item");
  p._plDrag = null;
});
