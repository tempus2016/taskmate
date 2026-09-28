const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

// Values built inside the panel's sandbox have that realm's prototypes.
const deq = (actual, expected, msg) => assert.deepEqual(JSON.parse(JSON.stringify(actual)), expected, msg);

// Setup wizard (#980).

const store = new Map();
const localStorage = {
  getItem: k => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: k => store.delete(k),
};
const { get } = loadCard("taskmate-panel.js", { sandbox: { localStorage, history: { pushState() {} } } });
const TaskMatePanel = get("taskmate-panel");

const CATALOGUE = {
  age_groups: [
    { id: "3_5", color: "#1abc9c", icon: "mdi:toy-brick-outline" },
    { id: "6_8", color: "#3498db", icon: "mdi:bed-outline" },
    { id: "9_12", color: "#ff6b9d", icon: "mdi:dishwasher" },
    { id: "13_plus", color: "#9b59b6", icon: "mdi:pot-steam-outline" },
  ],
  chores: [
    ...["a", "b", "c", "d", "e", "f"].map((x, i) => ({ id: `little_${x}`, age_group: "3_5", points: 1, frequency: "daily", days: [], time_category: "evening", icon: "mdi:star", schedule: { schedule_mode: "specific_days", due_days: [] }, per_week: 7 + i * 0 })),
    { id: "make_bed", age_group: "6_8", points: 2, frequency: "daily", days: [], time_category: "morning", icon: "mdi:bed-outline", schedule: { schedule_mode: "specific_days", due_days: [] }, per_week: 7 },
    { id: "hoover_room", age_group: "9_12", points: 4, frequency: "days", days: ["saturday"], time_category: "anytime", icon: "mdi:vacuum-outline", schedule: { schedule_mode: "specific_days", due_days: ["saturday"] }, per_week: 1 },
    { id: "mow_lawn", age_group: "13_plus", points: 8, frequency: "every_2_weeks", days: ["saturday"], time_category: "anytime", icon: "mdi:mower", schedule: { schedule_mode: "recurring", due_days: [], recurrence: "every_2_weeks", recurrence_day: "saturday" }, per_week: 0.5 },
  ],
  reward_tiers: ["small", "big"],
  rewards: [
    { id: "screen_time", tier: "small", cost: 15, icon: "mdi:television-play", picked: true },
    { id: "sleepover", tier: "big", cost: 250, icon: "mdi:sleep", picked: false },
  ],
};

const NAMES = {
  "wizard.chore.make_bed": "Make bed",
  "wizard.chore.hoover_room": "Hoover a room",
  "wizard.chore.mow_lawn": "Mow the lawn",
  "wizard.reward.screen_time": "15 min extra screen time",
  "wizard.reward.sleepover": "Friend sleepover",
  "wizard.pname_stars": "Stars",
};

const TEMPLATES = [
  { id: "morning_routine", name: "Morning routine", builtin: true, chores: [
    { name: "Make bed", points: 2, time_category: "morning", schedule_mode: "specific_days", due_days: ["monday", "tuesday"] },
    { name: "Brush teeth", points: 1, time_category: "morning", schedule_mode: "specific_days", due_days: [] },
  ] },
  { id: "custom_pack", name: "Ours", builtin: false, chores: [{ name: "Custom", points: 1 }] },
];

function age(years, monthsAgo = 1) {
  const d = new Date();
  d.setMonth(d.getMonth() - monthsAgo);
  d.setFullYear(d.getFullYear() - years);
  return d.toISOString().slice(0, 10);
}

function panel(state = {}) {
  store.clear();
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => {
    if (key.startsWith("wizard.chore.") && !NAMES[key]) return key.slice(13);
    let s = NAMES[key] || key;
    for (const [k, v] of Object.entries(params)) s += `|${k}=${v}`;
    return s;
  };
  p._render = () => {};
  p._showToast = (kind, text) => { p._toasts.push([kind, text]); };
  p._toasts = [];
  p.querySelector = () => null;
  p.querySelectorAll = () => [];
  p._activeTab = "today";
  p._wzCatalogue = CATALOGUE;
  p._state = { children: [], chores: [], rewards: [], templates: TEMPLATES, settings: { points_name: "Stars", points_icon: "mdi:star" }, ...state };
  p._callWS = async () => ({ ok: true, res: {} });
  return p;
}

async function opened(state, kids = []) {
  const p = panel(state);
  await p._wizardOpen();
  for (const k of kids) {
    Object.assign(p._wz.form, k);
    assert.ok(p._wizardAddKid(), `added ${k.name}`);
  }
  return p;
}

test("ages map onto the four age groups; under-3s get the youngest", () => {
  const p = panel();
  assert.equal(p._wizardGroupForAge(2), "3_5");
  assert.equal(p._wizardGroupForAge(5), "3_5");
  assert.equal(p._wizardGroupForAge(6), "6_8");
  assert.equal(p._wizardGroupForAge(12), "9_12");
  assert.equal(p._wizardGroupForAge(13), "13_plus");
  assert.equal(p._wizardGroupForAge(null), "");
});

test("a birthday gives an age that only goes up on the day", () => {
  const p = panel();
  assert.equal(p._wizardAgeOf({ mode: "bday", bday: age(9) }), 9);
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setFullYear(d.getFullYear() - 9);
  assert.equal(p._wizardAgeOf({ mode: "bday", bday: d.toISOString().slice(0, 10) }), 8);
  assert.equal(p._wizardAgeOf({ mode: "age", age: 6 }), 6);
  assert.equal(p._wizardAgeOf({ mode: "none", band: "6_8" }), null);
});

test("opens by itself only for a family with no children, once", async () => {
  const p = panel();
  let opens = 0;
  p._wizardOpen = async () => { opens++; };
  p._wizardMaybeAutoOpen();
  p._wizardMaybeAutoOpen();
  assert.equal(opens, 1);

  const q = panel({ children: [{ id: "k1", name: "Malia" }] });
  q._wizardOpen = async () => { opens++; };
  q._wizardMaybeAutoOpen();
  assert.equal(opens, 1);

  const r = panel();
  localStorage.setItem("taskmate-setup-skipped", "true");
  r._wizardOpen = async () => { opens++; };
  r._wizardMaybeAutoOpen();
  assert.equal(opens, 1);
});

test("the first five chores of a child's age group are ticked for them", async () => {
  const p = await opened({}, [{ name: "Isla", mode: "age", age: 4 }]);
  const little = CATALOGUE.chores.filter(s => s.age_group === "3_5");
  deq(little.map(s => p._wz.chores[s.id].on), [true, true, true, true, true, false]);
  deq(p._wz.chores.little_a.who, ["new1"]);
  assert.equal(p._wz.chores.make_bed.on, false);
});

test("older siblings can take a younger group's chore, never the other way round", async () => {
  const p = await opened({}, [{ name: "Malia", mode: "age", age: 10 }, { name: "Isla", mode: "age", age: 4 }]);
  deq(p._wizardEligible("3_5").map(k => k.name), ["Malia", "Isla"]);
  deq(p._wizardEligible("9_12").map(k => k.name), ["Malia"]);
  deq(p._wizardEligible("13_plus"), []);
  // Nobody old enough: the row can't be ticked.
  p._wizardAct({ dataset: { act: "wz-sg", id: "mow_lawn" } }, { stopPropagation() {} });
  assert.equal(p._wz.chores.mow_lawn.on, false);
});

test("taking every child off a chore unticks it (an empty list would mean everyone)", async () => {
  const p = await opened({}, [{ name: "Vaiha", mode: "age", age: 6 }]);
  assert.equal(p._wz.chores.make_bed.on, true);
  p._wizardAct({ dataset: { act: "wz-sg-who", id: "make_bed", k: "new1" } }, { stopPropagation() {} });
  assert.equal(p._wz.chores.make_bed.on, false);
  assert.ok(!p._wizardPlan().chores.some(c => c.name === "Make bed"));
});

test("the plan: approval for big jobs only, schedules passed through, age group stored", async () => {
  const p = await opened({}, [{ name: "Malia", mode: "bday", bday: age(10) }, { name: "Vaiha", mode: "age", age: 6 }]);
  assert.equal(p._wz.chores.hoover_room.on, true);
  const plan = p._wizardPlan();
  deq(plan.children.map(c => [c.name, c.age_group, c.birthday !== ""]), [["Malia", "9_12", true], ["Vaiha", "6_8", false]]);
  const bed = plan.chores.find(c => c.name === "Make bed");
  const hoover = plan.chores.find(c => c.name === "Hoover a room");
  assert.equal(bed.requires_approval, false);
  assert.equal(hoover.requires_approval, true);
  deq(hoover.due_days, ["saturday"]);
  deq(hoover.assigned_to, ["new1"]);
  p._wz.approval = "none";
  assert.ok(p._wizardPlan().chores.every(c => c.requires_approval === false));
  p._wz.approval = "all";
  assert.ok(p._wizardPlan().chores.every(c => c.requires_approval === true));
});

test("chores and rewards the family already has are left out", async () => {
  const p = await opened({
    children: [{ id: "k1", name: "Vaiha", birthday: age(6) }],
    chores: [{ id: "c1", name: "make BED" }],
    rewards: [{ id: "r1", name: "15 min extra screen time" }],
  });
  assert.equal(p._wz.mode, "existing");
  assert.equal(p._wz.chores.make_bed.on, false);
  const plan = p._wizardPlan();
  assert.ok(!plan.chores.some(c => c.name.toLowerCase() === "make bed"));
  assert.ok(!plan.rewards.some(r => r.name === "15 min extra screen time"));
  deq(plan.children, []);
});

test("an existing child without an age only gets a missing age group filled in", async () => {
  const p = await opened({ children: [
    { id: "k1", name: "Vaiha", birthday: "05-12" },
    { id: "k2", name: "Malia", birthday: age(10), age_group: "9_12" },
  ] });
  assert.equal(p._wizardBand(p._wz.kids[0]), "");
  p._wizardAct({ dataset: { act: "wz-kband", id: "k1", v: "6_8" } }, {});
  p._wizardAct({ dataset: { act: "wz-kband", id: "k2", v: "3_5" } }, {});
  deq(p._wizardPlan().child_updates, [{ child_id: "k1", age_group: "6_8" }]);
});

test("a pack chore named like a ticked suggestion is only added once", async () => {
  const p = await opened({}, [{ name: "Vaiha", mode: "age", age: 6 }]);
  p._wizardAct({ dataset: { act: "wz-pack", v: "morning_routine" } }, {});
  const names = p._wizardPlan().chores.map(c => c.name);
  assert.equal(names.filter(n => n === "Make bed").length, 1);
  assert.ok(names.includes("Brush teeth"));
  const teeth = p._wizardPlan().chores.find(c => c.name === "Brush teeth");
  deq(teeth.assigned_to, []);  // packs go to everyone
  // Only built-in packs are offered.
  deq(p._wizardPacks().map(t => t.id), ["morning_routine"]);
});

test("the weekly estimate follows the ticked chores and their frequency", async () => {
  const p = await opened({}, [{ name: "Vaiha", mode: "age", age: 6 }]);
  deq(p._wizardWeekly(p._wz.kids[0]), { n: 1, pts: 14 });
  p._wizardAct({ dataset: { act: "wz-sg-pts", id: "make_bed", d: "1" } }, { stopPropagation() {} });
  deq(p._wizardWeekly(p._wz.kids[0]), { n: 1, pts: 21 });
});

test("a birthday in the future is refused", async () => {
  const p = await opened({});
  const d = new Date();
  d.setDate(d.getDate() + 3);
  Object.assign(p._wz.form, { name: "Isla", mode: "bday", bday: d.toISOString().slice(0, 10) });
  assert.equal(p._wizardAddKid(), false);
  assert.equal(p._wz.kids.length, 0);
  assert.equal(p._toasts[0][0], "err");
});

test("the chores step needs a child first, and a typed name is added on Next", async () => {
  const p = await opened({});
  p._wizardGo(2);
  assert.equal(p._wz.step, 1);
  p._wz.form.name = "Isla";
  p._wizardGo(2);
  assert.equal(p._wz.step, 2);
  deq(p._wz.kids.map(k => k.name), ["Isla"]);
});

test("the draft is kept in this browser and picked up again", async () => {
  const p = await opened({}, [{ name: "Isla", mode: "age", age: 4 }]);
  p._wizardGo(2);
  const saved = JSON.parse(localStorage.getItem("taskmate-setup-draft"));
  assert.equal(saved.step, 2);
  assert.equal(saved.busy, undefined);
  const q = panel();
  localStorage.setItem("taskmate-setup-draft", JSON.stringify(saved));
  await q._wizardOpen();
  assert.equal(q._wz.step, 2);
  deq(q._wz.kids.map(k => k.name), ["Isla"]);
});

test("every step renders, and the last one has no footer", async () => {
  const p = await opened({}, [{ name: "Isla", mode: "age", age: 4 }]);
  for (let step = 0; step <= 4; step++) {
    p._wz.step = step;
    const html = p._wizardBody();
    assert.match(html, /tm-wz-foot/);
    assert.match(html, new RegExp(`wizard\\.step_of\\|n=${step + 1}`));
  }
  p._wz.step = 5;
  p._wz.result = { children_added: 1, chores_added: 5, rewards_added: 1, dashboard: "created" };
  const done = p._wizardBody();
  assert.doesNotMatch(done, /tm-wz-foot/);
  assert.match(done, /data-act="wz-dashboard"/);
});

test("user text is escaped", async () => {
  const p = await opened({}, [{ name: "<img src=x onerror=alert(1)>", mode: "age", age: 4 }]);
  for (const step of [1, 2, 4]) {
    p._wz.step = step;
    assert.doesNotMatch(p._wizardBody(), /<img src=x/);
  }
});

test("the dashboard is never created over an existing one", async () => {
  const calls = [];
  const p = await opened({}, [{ name: "Isla", mode: "age", age: 4 }]);
  p._callWS = async (msg) => { calls.push(msg.type); return { ok: true, res: [{ url_path: "family-chores" }] }; };
  assert.equal(await p._wizardCreateDashboard({ new1: "id1" }), "exists");
  deq(calls, ["lovelace/dashboards/list"]);

  calls.length = 0;
  p._hass = { panels: { "family-chores": {} }, states: {} };
  assert.equal(await p._wizardCreateDashboard({}), "exists");
  deq(calls, []);
});

test("a new dashboard gets a child card per child and the rewards card", async () => {
  const sent = [];
  const p = await opened({ children: [{ id: "k1", name: "Malia", birthday: age(10) }] }, [{ name: "Isla", mode: "age", age: 4 }]);
  p._hass = { panels: {}, states: { "sensor.taskmate_overview": { attributes: { points_name: "Stars", children: [] } } } };
  p._callWS = async (msg) => { sent.push(msg); return { ok: true, res: msg.type === "lovelace/dashboards/list" ? [] : {} }; };
  assert.equal(await p._wizardCreateDashboard({ new1: "id1" }), "created");
  const create = sent.find(m => m.type === "lovelace/dashboards/create");
  assert.equal(create.url_path, "family-chores");
  assert.equal(create.mode, "storage");
  const save = sent.find(m => m.type === "lovelace/config/save");
  assert.equal(save.url_path, "family-chores");
  const cards = save.config.views[0].cards;
  deq(cards.map(c => c.type), ["custom:taskmate-child-card", "custom:taskmate-child-card", "custom:taskmate-rewards-card"]);
  deq(cards.slice(0, 2).map(c => c.child_id), ["k1", "id1"]);
  assert.ok(cards.every(c => c.entity === "sensor.taskmate_overview"));
  assert.equal(cards[1].time_category, "all");
});

test("create sends one apply call, then only changes what the parent changed", async () => {
  const sent = [];
  const p = await opened({}, [{ name: "Isla", mode: "age", age: 4 }]);
  p._fetchState = async () => {};
  p._notifState = { config: { pending_chore_approval: { master_enabled: true }, pending_reward_claim: { master_enabled: false } } };
  p._wz.dash = false;
  p._callWS = async (msg) => { sent.push(msg); return { ok: true, res: msg.type === "taskmate/setup_wizard/apply" ? { children: { new1: "id1" }, chores_added: 5 } : {} }; };
  await p._wizardCreate();
  deq(sent.map(m => m.type), ["taskmate/setup_wizard/apply", "taskmate/notifications/set_master_enabled"]);
  assert.equal(sent[1].type_id, "pending_reward_claim");
  assert.equal(p._wz.step, 5);
  assert.equal(localStorage.getItem("taskmate-setup-draft"), null);

  sent.length = 0;
  const q = await opened({}, [{ name: "Isla", mode: "age", age: 4 }]);
  q._fetchState = async () => {};
  q._wz.dash = false; q._wz.notify = false;
  q._wizardAct({ dataset: { act: "wz-pname", v: "coins" } }, {});
  q._callWS = p._callWS;
  await q._wizardCreate();
  deq(sent.map(m => m.type), ["taskmate/setup_wizard/apply", "taskmate/update_settings"]);
  assert.equal(sent[1].points_icon, "mdi:circle-multiple");
});

test("a failed create keeps the wizard on Review with the draft", async () => {
  const p = await opened({}, [{ name: "Isla", mode: "age", age: 4 }]);
  p._wizardGo(4);
  p._callWS = async () => ({ ok: false, err: "boom" });
  await p._wizardCreate();
  assert.equal(p._wz.step, 4);
  assert.equal(p._wz.busy, false);
  assert.ok(localStorage.getItem("taskmate-setup-draft"));
  assert.equal(p._toasts.at(-1)[0], "err");
});

test("a birthday that moves a child up an age group shows a one-time nudge", () => {
  const p = panel({ children: [
    { id: "k1", name: "Vaiha", birthday: age(9), age_group: "6_8" },
    { id: "k2", name: "Malia", birthday: age(10), age_group: "9_12" },
    { id: "k3", name: "Isla", birthday: age(9) },
  ] });
  p._childColor = () => "#3498db";
  const hit = p._wizardNudgeKid();
  assert.equal(hit.child.id, "k1");
  assert.equal(hit.group, "9_12");
  assert.match(p._wizardNudge(), /data-act="wz-nudge"[^>]*data-v="9_12"/);
  const none = panel({ children: [{ id: "k1", name: "Vaiha", birthday: age(9), age_group: "9_12" }] });
  assert.equal(none._wizardNudge(), "");
});

test("the entry points: Today with no children, Settings and the command search", () => {
  const p = panel();
  p._approvalQueue = () => ({ count: 0, html: "", chores: [] });
  assert.match(p._renderTodayTab(), /data-act="wz-open"/);
  assert.match(p._wizardSettingsSection(), /data-act="wz-open"/);
  p._newMenuItems = () => [];
  p._sidebarGroups = () => [];
  p._scopeId = () => "";
  assert.ok(p._paletteCommands().some(c => c.data.act === "wz-open"));
});

test("with a family already set up, the wizard asks first", () => {
  const p = panel({ children: [{ id: "k1", name: "Malia" }], chores: [{ id: "c" }] });
  let opened_ = false;
  p._wizardOpen = () => { opened_ = true; };
  p._openDialog = (d) => { p._dialog = d; };
  p._wizardRequestOpen();
  assert.equal(opened_, false);
  assert.equal(p._dialog.kind, "wizard-confirm");
  assert.match(p._renderWizardConfirmDialog(), /data-act="wz-open-confirmed"/);
});
