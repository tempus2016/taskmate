const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

const { get } = loadCard("taskmate-panel.js");
const TaskMatePanel = get("taskmate-panel");

// Admin panel Today page, child filter and command search (#966).

function panel(extra = {}) {
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => (params.name ? `${key}:${params.name}` : key);
  p._timeAgo = () => "just now";
  p._activeTab = "today";
  p._state = {
    children: [
      { id: "kid1", name: "Malia", points: 142, current_streak: 9 },
      { id: "kid2", name: "Vaiha", points: 87, current_streak: 0 },
    ],
    chores: [
      { id: "bed", name: "Make bed", time_category: "morning", assigned_to: [] },
      { id: "dishes", name: "Dishes", time_category: "afternoon", assigned_to: ["kid1"] },
      { id: "cat", name: "Feed cat", time_category: "custom-gone", assigned_to: ["kid2"] },
    ],
    rewards: [
      { id: "tv", name: "TV time", assigned_to: [] },
      { id: "lego", name: "Lego", assigned_to: ["kid2"] },
    ],
    pending_completions: [
      { id: "p1", chore_id: "dishes", child_id: "kid1", completed_at: "2026-04-20T10:00:00Z" },
    ],
    pending_reward_claims: [],
    swap_requests: [],
    wishes: [
      { id: "w1", child_id: "kid2", name: "Kite", status: "pending", target: 50, created_at: "2026-04-20T09:00:00Z" },
    ],
    settings: { points_name: "Stars" },
    today: {
      board: {
        date: "2026-04-20",
        children: [
          { child_id: "kid1", due: 2, done: 1, chores: [
            { chore_id: "bed", status: "done", count: 1, limit: 1 },
            { chore_id: "dishes", status: "pending", count: 1, limit: 1 },
          ] },
          { child_id: "kid2", due: 2, done: 0, chores: [
            { chore_id: "bed", status: "missed", count: 0, limit: 1 },
            { chore_id: "cat", status: "todo", count: 0, limit: 1 },
          ] },
        ],
      },
      history: {
        kid1: [{ date: "2026-04-19" }, { date: "2026-04-20", due: 2, done: 1 }],
        kid2: [{ date: "2026-04-19", due: 3, done: 3 }, { date: "2026-04-20", due: 2, done: 0 }],
      },
    },
    ...extra,
  };
  return p;
}

test("Today is the first section, and every section has a label and an icon", () => {
  const groups = panel()._sidebarGroups();
  assert.equal(groups[0].items[0].id, "today");
  assert.ok(groups.every(g => g.head && g.key && g.icon));
});

test("the Today count covers approvals and new wishes", () => {
  const today = panel()._sidebarGroups()[0].items[0];
  assert.equal(today.count, 2);
});

test("the child cards show done/total from the board", () => {
  const html = panel()._renderTodayTab();
  assert.match(html, /<span>1\/2<\/span>/);
  assert.match(html, /<span>0\/2<\/span>/);
  assert.match(html, /panel\.today_streak/);
});

test("the board shows each chore's status and files unknown periods under any time", () => {
  const html = panel()._renderTodayBoard(panel()._state.children);
  assert.match(html, /tm-bchip-done" data-act="edit-chore" data-id="bed"/);
  assert.match(html, /tm-bchip-pending" data-act="edit-chore" data-id="dishes"/);
  assert.match(html, /tm-bchip-missed" data-act="edit-chore" data-id="bed"/);
  const anytime = html.indexOf("panel.time_anytime");
  assert.ok(anytime > 0 && html.indexOf('data-id="cat"') > anytime, "an unknown period falls back to any time");
});

test("the needs-you list includes a new wish with approve and decline", () => {
  const html = panel()._renderTodayTab();
  assert.match(html, /data-act="wish-approve" data-id="w1"/);
  assert.match(html, /data-act="approve-chore" data-id="p1"/);
});

test("the week view marks unrecorded days instead of inventing a number", () => {
  const html = panel()._renderTodayWeek(panel()._state.children);
  assert.match(html, /tm-week-none/);
  assert.match(html, />3\/3</);
  assert.match(html, /panel\.today_week_hint/);
});

test("a missing board says so rather than rendering empty", () => {
  const p = panel({ today: null });
  assert.match(p._renderTodayBoard(p._state.children), /panel\.today_board_unavailable/);
});

test("the child filter narrows chores, rewards and the approval queue", () => {
  const p = panel();
  p._scope = "kid2";
  assert.deepEqual(p._filterByName(p._state.chores).map(c => c.id), ["bed", "cat"]);
  assert.deepEqual(p._filterByName(p._state.rewards).map(r => r.id), ["tv", "lego"]);
  const queue = p._approvalQueue({ wishes: true });
  assert.equal(queue.count, 1);
  assert.doesNotMatch(queue.html, /approve-chore/);
});

test("a filter naming a deleted child falls back to everyone", () => {
  const p = panel();
  p._scope = "gone";
  assert.equal(p._scopeId(), "");
  assert.equal(p._filterByName(p._state.chores).length, 3);
});

test("command search finds chores by name and runs their edit action", () => {
  const p = panel();
  p._palette = { q: "dish", hi: 0 };
  const html = p._paletteListHtml();
  assert.match(html, /data-act="edit-chore" data-id="dishes"/);
  assert.doesNotMatch(html, /data-id="bed"/);
});

test("an empty search lists sections and actions but not every item", () => {
  const p = panel();
  p._palette = { q: "", hi: 0 };
  const html = p._paletteListHtml();
  assert.match(html, /data-act="tab" data-tab="chores"/);
  assert.match(html, /data-act="add-chore"/);
  assert.doesNotMatch(html, /data-act="edit-chore"/);
});

test("the rail lists sections, not pages, and marks the open one", () => {
  const p = panel();
  p._activeTab = "rewards";
  const html = p._sidebar();
  assert.doesNotMatch(html, /data-tab=/);
  for (const hub of ["today", "family", "earn", "spend", "points", "review", "settings"]) {
    assert.match(html, new RegExp(`data-act="hub" data-hub="${hub}"`));
  }
  assert.match(html, /tm-hub-on" data-act="hub" data-hub="spend"/);
});

test("the open section's pages are the tabs along the top", () => {
  const p = panel();
  p._hubTabs = {};
  p._activeTab = "rewards";
  const html = p._subTabs();
  assert.match(html, /data-tab="rewards"/);
  assert.match(html, /data-tab="wishlists"/);
  assert.match(html, /data-tab="raffles"/);
  assert.doesNotMatch(html, /data-tab="chores"/);
  assert.match(html, /tm-subtab-on" data-act="tab" data-tab="rewards"/);
});

test("Today has no tabs row, and its rail button shows what is waiting", () => {
  const p = panel();
  p._hubTabs = {};
  assert.equal(p._subTabs(), "");
  // One pending chore + one new wish.
  assert.match(p._sidebar(), /data-hub="today"[^]*?tm-hub-dot">2</);
});

test("a section reopens on the page last used in it", () => {
  const p = panel();
  p._hubTabs = {};
  p._activeTab = "raffles";
  p._subTabs();
  assert.equal(p._hubTabs.spend, "raffles");
});

test("Needs you offers filter chips once more than one kind is waiting", () => {
  const p = panel();
  const q = p._approvalQueue({ wishes: true });
  assert.deepEqual({ ...q.kinds }, { chore: 1, reward: 0, swap: 0, wish: 1 });
  const chips = p._needsFilterChips(q.kinds);
  assert.match(chips, /data-kind="all"/);
  assert.match(chips, /data-kind="chore"/);
  assert.match(chips, /data-kind="wish"/);
  assert.doesNotMatch(chips, /data-kind="reward"/, "no chip for a kind with nothing waiting");
  assert.match(q.html, /data-kind="chore"/);
  assert.match(q.html, /data-kind="wish"/);
});

test("one kind waiting needs no chips, and a stale filter falls back to all", () => {
  const p = panel({ wishes: [] });
  const q = p._approvalQueue({ wishes: true });
  assert.equal(p._needsFilterChips(q.kinds), "");
  p._needsFilter = "wish";
  assert.equal(p._needsFilterOn(q.kinds), "all");
});

test("an ordinary reward shows each child's progress towards it, and who can get it now", () => {
  const p = panel();
  p._childColor = () => "#f48fb1";
  const tv = p._rewardKidBars({ id: "tv", cost: 100, assigned_to: [] });
  assert.match(tv, /Malia: 142 \/ 100/);
  assert.match(tv, /Vaiha: 87 \/ 100/);
  assert.equal((tv.match(/panel\.reward_affordable/g) || []).length, 2, "one tick (title + screen-reader text), for Malia only");
  const lego = p._rewardKidBars({ id: "lego", cost: 100, assigned_to: ["kid2"] });
  assert.doesNotMatch(lego, /Malia/);
  assert.match(lego, /width:87%/);
});

test("reward progress leaves adult profiles out of 'everyone'", () => {
  const p = panel();
  p._childColor = () => "#000";
  p._state.children.push({ id: "mum", name: "Mum", points: 500, is_adult: true });
  assert.doesNotMatch(p._rewardKidBars({ id: "tv", cost: 100, assigned_to: [] }), /Mum/);
  assert.match(p._rewardKidBars({ id: "tv", cost: 100, assigned_to: ["mum"] }), /Mum/);
});
