const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

// Values built inside the panel's sandbox have that realm's prototypes.
const deq = (actual, expected, msg) => assert.deepEqual(JSON.parse(JSON.stringify(actual)), expected, msg);

// Ready-made dashboards (#1053).

const store = new Map();
const localStorage = {
  getItem: k => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: k => store.delete(k),
};
const { get } = loadCard("taskmate-panel.js", { sandbox: { localStorage, history: { pushState() {} } } });
const TaskMatePanel = get("taskmate-panel");

const KIDS = [
  { id: "k1", name: "Malia", avatar: "mdi:star" },
  { id: "k2", name: "Vaiha", avatar: "mdi:heart" },
];

function panel(children = KIDS, panels = {}) {
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => {
    let s = key;
    for (const [k, v] of Object.entries(params)) s += `|${k}=${v}`;
    return s;
  };
  p._render = () => {};
  p._toasts = [];
  p._showToast = (kind, text) => { p._toasts.push([kind, text]); };
  p.querySelector = () => null;
  p.querySelectorAll = () => [];
  p._state = { children, chores: [], rewards: [], settings: {} };
  p._hass = { panels, states: { "sensor.taskmate_overview": { attributes: { points_name: "Stars", children: [], badge_entities: { k1: "sensor.area_malia_badges" } } } } };
  p._callWS = async () => ({ ok: true, res: [] });
  return p;
}

function specs(p, kind, extra = {}) {
  return p._dashSpecs({ ...p._dashDefaults(kind), ...extra }, p._dashKids());
}

test("Parents: today, points and insights tabs; admins-only is opt-in", () => {
  const p = panel();
  const [s] = specs(p, "parents");
  assert.equal(s.url_path, "taskmate-parents");
  assert.equal(s.require_admin, false);
  assert.equal(s.show_in_sidebar, true);
  deq(s.config.views.map(v => v.path), ["today", "points", "insights"]);
  deq(s.config.views[0].cards.map(c => c.type), ["custom:taskmate-approvals-card", "custom:taskmate-chore-board-card", "custom:taskmate-parent-dashboard-card"]);
  assert.equal(s.config.views[1].cards[0].mode, "multi");
  assert.ok(s.config.views.flatMap(v => v.cards).every(c => c.entity === "sensor.taskmate_overview"));
  assert.equal(specs(p, "parents", { admin: true })[0].require_admin, true);
  // Only the Parents preset can be locked to admins.
  assert.equal(specs(p, "kids", { admin: true })[0].require_admin, false);
});

test("Wall tablet: full-screen panel views, the board tab is optional, hidden from the sidebar", () => {
  const p = panel();
  const [s] = specs(p, "wall");
  assert.equal(s.show_in_sidebar, false);
  deq(s.config.views.map(v => [v.path, v.type, v.cards[0].type]), [
    ["kiosk", "panel", "custom:taskmate-kiosk-card"],
    ["board", "panel", "custom:taskmate-chore-board-card"],
  ]);
  deq(specs(p, "wall", { board: false })[0].config.views.map(v => v.path), ["kiosk"]);
});

test("Kids: one dashboard with a tab each, or a dashboard per child", () => {
  const p = panel();
  const [one] = specs(p, "kids");
  deq(one.config.views.map(v => v.path), ["malia", "vaiha", "family"]);
  deq(one.config.views[2].cards.map(c => c.type), ["custom:taskmate-leaderboard-card", "custom:taskmate-family-goal-card"]);
  // Badges read each child's own sensor, from the overview's map; no sensor, no card.
  const badge = one.config.views[0].cards.find(c => c.type === "custom:taskmate-badges-card");
  assert.equal(badge.entity, "sensor.area_malia_badges");
  assert.ok(!("child_id" in badge));
  assert.ok(!one.config.views[1].cards.some(c => c.type === "custom:taskmate-badges-card"));
  assert.equal(one.config.views[0].icon, "mdi:star");
  assert.equal(one.config.views[1].cards[0].header_color, p._childColor("k2"));
  assert.equal(one.config.views[0].cards[0].show_parent_actions, false);
  assert.equal(specs(p, "kids", { hide: false })[0].config.views[0].cards[0].show_parent_actions, undefined);

  const each = specs(p, "kids", { layout: "each" });
  deq(each.map(s => s.url_path), ["taskmate-kids-malia", "taskmate-kids-vaiha"]);
  deq(each.map(s => s.title), ["panel.dash_title_kids · Malia", "panel.dash_title_kids · Vaiha"]);
  deq(each[1].config.views.map(v => v.path), ["vaiha", "family"]);
  assert.ok(each[1].config.views[0].cards.every(c => c.child_id === "k2"));
});

test("every child gets an address of their own, whatever their name", () => {
  const p = panel([
    { id: "a", name: "Sam" }, { id: "b", name: "Sam" }, { id: "c", name: "Family" },
    { id: "d", name: "Zoë" }, { id: "e", name: "🦄" }, { id: "f", name: "Guest", is_guest: true },
  ]);
  const [s] = specs(p, "kids");
  deq(s.config.views.map(v => v.path), ["sam", "sam-2", "family-2", "zoe", "e", "family"]);
  // Not an mdi icon (or none at all): a plain person instead.
  assert.ok(s.config.views.slice(0, 5).every(v => v.icon === "mdi:account"));
  deq(specs(p, "kids", { layout: "each" }).map(x => x.url_path),
    ["taskmate-kids-sam", "taskmate-kids-sam-2", "taskmate-kids-family-2", "taskmate-kids-zoe", "taskmate-kids-e"]);
});

test("the dialog checks everything before anything is written", async () => {
  const p = panel();
  const sent = [];
  p._callWS = async (msg) => { sent.push(msg); return { ok: true, res: msg.type === "lovelace/dashboards/list" ? [{ url_path: "taskmate-kids" }] : {} }; };
  p._dashNew("kids");
  const d = p._dialog.data;
  deq(d.kids, ["k1", "k2"]);

  d.path = "Kids Page";
  await p._dashSave();
  assert.equal(d.err, "panel.dash_path_invalid");
  d.path = "taskmate-kids";
  d.kids = [];
  await p._dashSave();
  assert.equal(d.err, "panel.dash_pick_child");
  deq(sent, []);

  d.kids = ["k1"];
  await p._dashSave();
  assert.equal(d.err, "panel.dash_path_taken|paths=/taskmate-kids");
  deq(sent.map(m => m.type), ["lovelace/dashboards/list"]);
  assert.equal(p._dialog.kind, "dash-create");

  // Per child: one taken address stops the lot.
  sent.length = 0;
  p._callWS = async (msg) => { sent.push(msg); return { ok: true, res: msg.type === "lovelace/dashboards/list" ? [{ url_path: "my-kids-vaiha" }] : {} }; };
  Object.assign(d, { path: "my-kids", layout: "each", kids: ["k1", "k2"] });
  await p._dashSave();
  assert.equal(d.err, "panel.dash_path_taken|paths=/my-kids-vaiha");
  deq(sent.map(m => m.type), ["lovelace/dashboards/list"]);
});

test("a free address is created, saved and the dialog closes", async () => {
  const p = panel();
  const sent = [];
  p._callWS = async (msg) => { sent.push(msg); return { ok: true, res: msg.type === "lovelace/dashboards/list" ? [] : {} }; };
  p._dashNew("parents");
  Object.assign(p._dialog.data, { title: " Mum & Dad ", path: "Our-Parents", admin: true });
  await p._dashSave();
  deq(sent.map(m => m.type), ["lovelace/dashboards/list", "lovelace/dashboards/create", "lovelace/config/save"]);
  const create = sent[1];
  deq({ url_path: create.url_path, title: create.title, mode: create.mode, require_admin: create.require_admin },
    { url_path: "our-parents", title: "Mum & Dad", mode: "storage", require_admin: true });
  assert.equal(sent[2].url_path, "our-parents");
  assert.equal(p._dialog, null);
  deq(p._toasts, [["ok", "panel.dash_toast_created|titles=Mum & Dad"]]);

  // The tile knows straight away, before Home Assistant's panel list catches up.
  p._dashNew("wall");
  await p._dashSave();
  assert.equal(p._dashFound("wall"), "taskmate-wall");
});

test("a failed save keeps the dialog open and says which", async () => {
  const p = panel();
  p._callWS = async (msg) => ({ ok: msg.type !== "lovelace/config/save", res: [] });
  p._dashNew("wall");
  await p._dashSave();
  assert.ok(p._dialog);
  assert.equal(p._dialog.data.busy, false);
  deq(p._toasts, [["err", "panel.dash_toast_failed|titles=panel.dash_title_wall"]]);
});

test("switching preset resets its options but keeps the picked children", () => {
  const p = panel();
  p._dashNew("kids");
  p._dashAct({ dataset: { act: "dash-kid", id: "k2" } });
  p._dashAct({ dataset: { act: "dash-layout", v: "each" } });
  p._dashAct({ dataset: { act: "dash-kind", v: "wall" } });
  const d = p._dialog.data;
  deq([d.kind, d.path, d.layout, d.sidebar, d.kids], ["wall", "taskmate-wall", "tabs", false, ["k1"]]);
});

test("Settings tiles: Open once made, and Kids needs a child first", () => {
  let html = panel(KIDS, { "taskmate-kids-malia": {} })._dashSettingsSection();
  assert.match(html, /data-act="dash-open" data-v="taskmate-kids-malia"/);
  assert.doesNotMatch(html, /data-act="dash-open" data-v="taskmate-parents"/);
  html = panel([])._dashSettingsSection();
  assert.match(html, /data-act="dash-new" data-v="kids" disabled/);
  assert.match(html, /data-act="dash-new" data-v="parents" >/);
  const p = panel([]);
  p._dashNew("kids");
  assert.equal(p._dialog, undefined);
  deq(p._toasts, [["err", "panel.dash_need_child"]]);
});

test("names are escaped in the dialog and its preview", () => {
  const p = panel([{ id: "x\"y", name: "<img src=x onerror=alert(1)>" }]);
  p._dashNew("kids");
  p._dialog.data.title = "<b>t</b>";
  const html = p._renderDashDialog();
  assert.doesNotMatch(html, /<img src=x/);
  assert.doesNotMatch(html, /<b>t<\/b>/);
  assert.match(html, /data-id="x&quot;y"/);
});

test("the command search offers each preset", () => {
  const p = panel();
  p._sidebarGroups = () => [];
  p._newMenuItems = () => [];
  const cmds = p._paletteCommands().filter(c => c.data.act === "dash-new");
  deq(cmds.map(c => c.data.v), ["kids", "parents", "wall"]);
});
