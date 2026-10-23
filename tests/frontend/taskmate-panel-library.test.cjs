const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

// Values built inside the panel's sandbox have that realm's prototypes.
const deq = (actual, expected, msg) => assert.deepEqual(JSON.parse(JSON.stringify(actual)), expected, msg);

// 📚 Library: browse ~200 chores and 45 rewards by age, add them in one go.

const store = new Map();
const localStorage = {
  getItem: k => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: k => store.delete(k),
};
const { get } = loadCard("taskmate-panel.js", { sandbox: { localStorage, history: { pushState() {} } } });
const TaskMatePanel = get("taskmate-panel");

const sched = { schedule_mode: "specific_days", due_days: [] };
const lc = (id, category, min_age, max_age, points, extra = {}) => ({
  id, category, min_age, max_age, points, frequency: "daily", days: [], time_category: "anytime",
  icon: "mdi:star", top_pick: false, schedule: sched, per_week: 7, ...extra,
});

const LIBRARY = {
  categories: ["morning", "kitchen", "tidy"],
  chores: [
    lc("make_bed", "morning", 6, null, 2, { top_pick: true }),
    lc("toys_away", "tidy", 3, 8, 1, { top_pick: true }),
    lc("cook_meal", "kitchen", 13, null, 8, { frequency: "days", days: ["friday"], schedule: { schedule_mode: "specific_days", due_days: ["friday"] }, per_week: 1 }),
    lc("dishwasher", "kitchen", 9, null, 3),
    lc("wash_up", "kitchen", 10, null, 3),
    lc("mow_lawn", "tidy", 13, null, 8, { frequency: "every_2_weeks", schedule: { schedule_mode: "recurring", due_days: [], recurrence: "every_2_weeks", recurrence_day: "saturday" }, per_week: 0.5 }),
  ],
  rewards: [
    { id: "screen_time", tier: "small", cost: 15, icon: "mdi:television-play", min_age: 3, top_pick: true },
    { id: "phone_data", tier: "big", cost: 200, icon: "mdi:signal", min_age: 13, top_pick: false },
  ],
  packs: [
    { id: "pet_care", name: "Pet care", icon: "mdi:paw", chores: [
      { name: "Feed pet", points: 2, time_category: "morning", due_days: [] },
      { name: "Walk dog", points: 3, time_category: "afternoon", due_days: [] },
    ] },
  ],
};

const CATALOGUE = {
  age_groups: [
    { id: "3_5", color: "#1abc9c", icon: "mdi:toy-brick-outline" },
    { id: "6_8", color: "#3498db", icon: "mdi:bed-outline" },
    { id: "9_12", color: "#ff6b9d", icon: "mdi:dishwasher" },
    { id: "13_plus", color: "#9b59b6", icon: "mdi:pot-steam-outline" },
  ],
  chores: [
    { id: "make_bed", age_group: "6_8", points: 2, frequency: "daily", days: [], time_category: "morning", icon: "mdi:bed-outline", schedule: sched, per_week: 7 },
    { id: "toys_away", age_group: "3_5", points: 1, frequency: "daily", days: [], time_category: "evening", icon: "mdi:toy-brick-outline", schedule: sched, per_week: 7 },
  ],
  reward_tiers: ["small", "saving", "big"],
  rewards: [{ id: "screen_time", tier: "small", cost: 15, icon: "mdi:television-play", picked: true }],
  library: LIBRARY,
};

const NAMES = {
  "wizard.chore.make_bed": "Make bed",
  "wizard.chore.toys_away": "Put toys away",
  "wizard.chore.cook_meal": "Cook a meal",
  "wizard.chore.dishwasher": "Load the dishwasher",
  "wizard.chore.wash_up": "Wash up by hand",
  "wizard.chore.mow_lawn": "Mow the lawn",
  "wizard.reward.screen_time": "15 min extra screen time",
  "wizard.reward.phone_data": "Extra phone data",
  "wizard.pack.pet_care.name": "Pet care",
  "wizard.pack.pet_care.chore_0": "Feed pet",
  "wizard.pack.pet_care.chore_1": "Walk dog",
  "wizard.pname_stars": "Stars",
};

function age(years) {
  const d = new Date();
  d.setMonth(d.getMonth() - 1);
  d.setFullYear(d.getFullYear() - years);
  return d.toISOString().slice(0, 10);
}

const KIDS = [
  { id: "ava", name: "Ava", birthday: age(6) },
  { id: "leo", name: "Leo", birthday: age(10) },
  { id: "mia", name: "Mia", birthday: age(14) },
  { id: "mum", name: "Mum", is_adult: true },
  { id: "gran", name: "Gran", is_guest: true },
];

function panel(state = {}) {
  store.clear();
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => {
    let s = NAMES[key] || key;
    for (const [k, v] of Object.entries(params)) s += `|${k}=${v}`;
    return s;
  };
  p._render = () => {};
  p._toasts = [];
  p._showToast = (kind, text) => { p._toasts.push([kind, text]); };
  p.querySelector = () => null;
  p.querySelectorAll = () => [];
  p._activeTab = "chores";
  p._wzCatalogue = CATALOGUE;
  p._calls = [];
  p._callWS = async payload => { p._calls.push(payload); return { ok: true, res: { chores_added: (payload.chores || []).length, rewards_added: (payload.rewards || []).length, chores_skipped: 0, rewards_skipped: 0 } }; };
  p._fetchState = async () => {};
  p._childColor = () => "#3498db";
  // The built-in packs come with the state too, as in get_state.
  p._state = { children: KIDS, chores: [], rewards: [], templates: LIBRARY.packs.map(t => ({ ...t, builtin: true })), settings: { points_name: "Stars", points_icon: "mdi:star" }, ...state };
  return p;
}

const ids = list => list.map(x => x.id);
const act = (p, a, data = {}) => p._libAct({ dataset: { act: a, ...data }, classList: { contains: () => false } }, { target: null });

test("only children appear as filters: never adults or guests", async () => {
  const p = panel();
  await p._libOpen();
  deq(p._libKids().map(k => k.key), ["ava", "leo", "mia"]);
  deq(p._libKids().map(k => k.age), [6, 10, 14]);
});

test("a child filter shows what suits their age, by birthday or age group", async () => {
  const p = panel({ children: [...KIDS, { id: "kit", name: "Kit", age_group: "3_5" }] });
  await p._libOpen();
  p._lib.cat = "kitchen";
  act(p, "lib-kid", { k: "leo" });
  deq(ids(p._libShown()), ["dishwasher", "wash_up"]);
  act(p, "lib-kid", { k: "mia" });
  deq(ids(p._libShown()), ["cook_meal", "dishwasher", "wash_up"]);
  act(p, "lib-kid", { k: "" });
  p._lib.cat = "tidy";
  act(p, "lib-kid", { k: "kit" });
  deq(ids(p._libShown()), ["toys_away"]);
});

test("ones the family already has are hidden, by template id or by name", async () => {
  const p = panel({ chores: [{ id: "c1", name: "Bed!", template_id: "make_bed" }, { id: "c2", name: "put TOYS away" }] });
  await p._libOpen();
  deq(ids(p._libShown()), []);
  p._lib.hide = false;
  deq(ids(p._libShown()), ["make_bed", "toys_away"]);
  const html = p._libCard(LIBRARY.chores[0]);
  assert.match(html, /tm-lib-have/);
  assert.doesNotMatch(html, /data-act="lib-tpl"/, "an added chore can't be ticked again");
});

test("search looks across every category", async () => {
  const p = panel();
  await p._libOpen();
  p._lib.q = "LAWN";
  deq(ids(p._libShown()), ["mow_lawn"]);
  assert.match(p._libGrid(), /library\.results\|query=LAWN\|count=1/);
});

test("the search text is escaped where it is echoed back", async () => {
  const p = panel();
  await p._libOpen();
  p._lib.q = "<img src=x onerror=alert(1)>";
  assert.doesNotMatch(p._libGrid(), /<img src=x/);
  assert.doesNotMatch(p._renderLibraryDialog(), /<img src=x/);
});

test("adding sends one call with template ids, to the children each chore suits", async () => {
  const p = panel();
  await p._libOpen();
  act(p, "lib-tpl", { id: "dishwasher" });
  act(p, "lib-tpl", { id: "toys_away" });
  await p._libAdd();
  assert.equal(p._calls.length, 1);
  const call = p._calls[0];
  assert.equal(call.type, "taskmate/library/add");
  const byTpl = Object.fromEntries(call.chores.map(c => [c.template_id, c]));
  deq(byTpl.dishwasher.assigned_to, ["leo", "mia"]);
  deq(byTpl.toys_away.assigned_to, ["ava"]);
  assert.equal(byTpl.dishwasher.name, "Load the dishwasher");
  assert.equal(byTpl.dishwasher.requires_approval, false);
  assert.equal(byTpl.dishwasher.schedule_mode, "specific_days");
  deq(p._lib.sel.chores, {}, "the selection clears after adding");
  assert.equal(p._toasts.at(-1)[0], "ok");
});

test("a chore that suits none of the chosen children still goes to them", async () => {
  const p = panel();
  await p._libOpen();
  act(p, "lib-tpl", { id: "cook_meal" });
  p._lib.assign = ["ava"];
  await p._libAdd();
  deq(p._calls[0].chores[0].assigned_to, ["ava"]);
});

test("Customise changes only the copy that is added", async () => {
  const p = panel();
  await p._libOpen();
  act(p, "lib-tpl", { id: "cook_meal" });
  act(p, "lib-edit", { id: "cook_meal" });
  deq(p._lib.edit.days, ["friday"]);
  p._lib.edit.name = "Cook Friday tea";
  p._lib.edit.pts = "10";
  p._lib.edit.time = "evening";
  act(p, "lib-e-day", { v: "monday" });
  act(p, "lib-e-save");
  assert.equal(p._lib.edit, null);
  await p._libAdd();
  const c = p._calls[0].chores[0];
  assert.equal(c.name, "Cook Friday tea");
  assert.equal(c.points, 10);
  assert.equal(c.requires_approval, true);
  assert.equal(c.time_category, "evening");
  deq(c.due_days, ["monday", "friday"]);
  assert.equal(c.template_id, "cook_meal");
});

test("a fortnightly chore keeps its own schedule; only daily-style ones get day picks", async () => {
  const p = panel();
  await p._libOpen();
  act(p, "lib-tpl", { id: "mow_lawn" });
  act(p, "lib-edit", { id: "mow_lawn" });
  act(p, "lib-e-save");
  await p._libAdd();
  const c = p._calls[0].chores[0];
  assert.equal(c.schedule_mode, "recurring");
  assert.equal(c.recurrence, "every_2_weeks");
});

test("a pack ticks all its chores, skipping the ones the family has", async () => {
  const p = panel({ chores: [{ id: "c1", name: "feed pet" }] });
  await p._libOpen();
  act(p, "lib-pack", { id: "pet_care" });
  deq(Object.keys(p._lib.sel.chores), ["pack.pet_care.1"]);
  assert.match(p._libPackCard(LIBRARY.packs[0]), /library\.pack_skip\|count=1/);
  await p._libAdd();
  const c = p._calls[0].chores[0];
  assert.equal(c.name, "Walk dog");
  assert.equal(c.template_id, "pack.pet_care.1");
  act(p, "lib-pack", { id: "pet_care" });
  act(p, "lib-pack", { id: "pet_care" });
  deq(Object.keys(p._lib.sel.chores), []);
});

test("rewards are added at a fixed cost", async () => {
  const p = panel();
  await p._libOpen({ kind: "rewards" });
  act(p, "lib-tpl", { id: "phone_data" });
  act(p, "lib-edit", { id: "phone_data" });
  p._lib.edit.pts = "250";
  act(p, "lib-e-save");
  await p._libAdd();
  deq(p._calls[0].rewards, [{ name: "Extra phone data", cost: 250, icon: "mdi:signal", template_id: "phone_data" }]);
  assert.equal(p._calls[0].chores, undefined);
});

test("nothing can be added for nobody", async () => {
  const p = panel();
  await p._libOpen();
  act(p, "lib-tpl", { id: "make_bed" });
  p._lib.assign = [];
  assert.match(p._libFoot(), /data-act="lib-add" disabled/);
});

test("a family with no children yet adds chores for everyone", async () => {
  const p = panel({ children: [] });
  await p._libOpen();
  act(p, "lib-tpl", { id: "make_bed" });
  await p._libAdd();
  deq(p._calls[0].chores[0].assigned_to, []);
});

test("See chore ideas opens the library on what newly suits the child", async () => {
  const p = panel({ children: [{ id: "leo", name: "Leo", birthday: age(10), age_group: "6_8" }] });
  p._wizardNudgeAct = TaskMatePanel.prototype._wizardNudgeAct;
  await p._wizardNudgeAct("leo", "9_12", true);
  assert.equal(p._calls[0].type, "taskmate/update_child");
  assert.equal(p._dialog.kind, "library");
  assert.equal(p._lib.cat, "new");
  deq(p._lib.kids, ["leo"]);
  // 9–12 is Leo's group now: the chores from 9 up that suit a 10-year-old.
  deq(ids(p._libShown()), ["dishwasher", "wash_up"]);
  assert.match(p._libRail(), /library\.cat_new\|name=Leo/);
});

test("the Chores and Rewards tabs open the library", () => {
  const p = panel();
  p._sortChoresByDisplayOrder = list => list;
  p._filterByName = list => list;
  p._searchBox = () => "";
  p._emptyState = () => "";
  assert.match(p._renderChoresTab(), /data-act="lib-open" data-v="chores"/);
  assert.match(p._renderRewardsTab(), /data-act="lib-open" data-v="rewards"/);
});

test("the dialog renders the rail, the cards and the Add button", async () => {
  const p = panel();
  await p._libOpen();
  act(p, "lib-tpl", { id: "make_bed" });
  const html = p._renderLibraryDialog();
  assert.match(html, /data-act="lib-cat" data-v="top"/);
  assert.match(html, /data-act="lib-cat" data-v="packs"/);
  assert.match(html, /data-act="lib-tpl" data-id="toys_away"/);
  assert.match(html, /data-act="lib-edit" data-id="make_bed"/);
  assert.match(html, /library\.add\|count=1/);
});

// ── Over the setup wizard ────────────────────────────────────────────────────

async function wizard(kids) {
  const p = panel({ children: [] });
  await p._wizardOpen();
  for (const k of kids) {
    Object.assign(p._wz.form, k);
    assert.ok(p._wizardAddKid(), `added ${k.name}`);
  }
  return p;
}

test("over the wizard, picks join the wizard's list instead of being added", async () => {
  const p = await wizard([{ name: "Isla", mode: "age", age: 10 }]);
  assert.match(p._wizardStepChores(), /data-act="lib-open" data-v="chores" data-mode="wizard"/);
  await p._libOpen({ kind: "chores", mode: "wizard" });
  assert.equal(p._lib.mode, "wizard");
  act(p, "lib-tpl", { id: "wash_up" });
  act(p, "lib-pack", { id: "pet_care" });
  act(p, "lib-add");
  assert.equal(p._calls.filter(c => c.type === "taskmate/library/add").length, 0, "nothing is created yet");
  deq(Object.keys(p._wz.lib), ["wash_up"]);
  deq(p._wz.lib.wash_up.who, ["new1"]);
  deq(p._wz.packs, ["pet_care"]);
  const plan = p._wizardPlan();
  const wash = plan.chores.find(c => c.template_id === "wash_up");
  assert.ok(wash, "the library chore is in the plan");
  deq(wash.assigned_to, ["new1"]);
  assert.ok(plan.chores.some(c => c.template_id === "pack.pet_care.0"));
  assert.match(p._wizardStepChores(), /data-act="wz-lib-rm" data-id="wash_up"/);
  p._wizardAct({ dataset: { act: "wz-lib-rm", id: "wash_up" } });
  assert.equal(p._wizardPlan().chores.some(c => c.template_id === "wash_up"), false);
});

test("over the wizard, the library starts from the wizard's ticks and can untick them", async () => {
  const p = await wizard([{ name: "Isla", mode: "age", age: 7 }]);
  assert.equal(p._wz.chores.make_bed.on, true);
  await p._libOpen({ kind: "chores", mode: "wizard" });
  assert.ok(p._lib.sel.chores.make_bed, "the wizard's tick shows as selected");
  act(p, "lib-tpl", { id: "make_bed" });
  act(p, "lib-add");
  assert.equal(p._wz.chores.make_bed.on, false);
});

test("over the wizard, library rewards join the plan at their fixed cost", async () => {
  const p = await wizard([{ name: "Isla", mode: "age", age: 14 }]);
  await p._libOpen({ kind: "rewards", mode: "wizard" });
  act(p, "lib-tpl", { id: "phone_data" });
  act(p, "lib-add");
  const r = p._wizardPlan().rewards.find(x => x.template_id === "phone_data");
  deq(r, { name: "Extra phone data", cost: 200, icon: "mdi:signal", template_id: "phone_data" });
  assert.match(p._wizardStepRewards(), /data-act="wz-librw-rm" data-id="phone_data"/);
});

test("the wizard's own suggestions carry their template ids", async () => {
  const p = await wizard([{ name: "Isla", mode: "age", age: 7 }]);
  const plan = p._wizardPlan();
  assert.equal(plan.chores.find(c => c.name === "Make bed").template_id, "make_bed");
  assert.equal(plan.rewards.find(r => r.template_id === "screen_time").cost, 15);
});

test("a draft from before the library still loads", () => {
  const p = panel();
  localStorage.setItem("taskmate-setup-draft", JSON.stringify({ v: 1, kids: [], step: 1, dashOpts: {}, dash: {} }));
  const d = p._wizardLoadDraft();
  deq(d.lib, {});
  deq(d.libRewards, {});
});
