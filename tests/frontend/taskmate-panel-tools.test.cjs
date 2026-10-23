const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render } = require("./harness.cjs");

// Admin panel tools: recently deleted, Settings jump list / search / unsaved
// changes, reward order, child quick view, view as child, Economy insight.

const { get, elements } = loadCard("taskmate-panel.js");
// Objects made inside the card's sandbox have that realm's prototypes.
const plain = (x) => JSON.parse(JSON.stringify(x));
const TaskMatePanel = get("taskmate-panel");

function panel(extra = {}) {
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => (params && Object.keys(params).length ? `${key}:${JSON.stringify(params)}` : key);
  p._activeTab = "today";
  p._zoneCache = {};
  p._state = {
    children: [
      { id: "kid1", name: "Malia", points: 320, level: 12, current_streak: 6 },
      { id: "kid2", name: "Vaiha", points: 87, current_streak: 0 },
      { id: "dad", name: "Dad", points: 5, is_adult: true },
    ],
    chores: [
      { id: "bed", name: "Make bed" },
      { id: "teeth", name: "Teeth" },
      { id: "tidy", name: "Tidy room" },
    ],
    rewards: [
      { id: "cinema", name: "Cinema trip", cost: 200 },
      { id: "xbox", name: "30 min Xbox", cost: 40 },
      { id: "dinner", name: "Pick Friday dinner", cost: 60 },
    ],
    quests: [],
    pending_completions: [{ id: "p1", chore_id: "tidy", child_id: "kid1" }],
    pending_reward_claims: [{ id: "c1", reward_id: "xbox", child_id: "kid1" }],
    owed_rewards: [{ claim_id: "o1", child_id: "kid1", reward_name: "Cinema trip" }],
    screen_time: { kid1: { minutes: 45, devices: [] } },
    swap_requests: [],
    wishes: [],
    recently_deleted: [
      { kind: "chore", id: "plants", name: "Water the plants", deleted_at: "2026-10-23T18:02:00+01:00" },
      { kind: "quest", id: "q1", name: "Half-term quest", deleted_at: "2026-10-18T09:00:00+01:00" },
    ],
    settings: { points_name: "Stars", screen_time_enabled: true },
    today: {
      board: {
        children: [
          { child_id: "kid1", due: 3, done: 2, chores: [
            { chore_id: "bed", status: "done" },
            { chore_id: "teeth", status: "done" },
            { chore_id: "tidy", status: "pending" },
          ] },
        ],
      },
    },
    ...extra,
  };
  return p;
}

// ── Recently deleted ─────────────────────────────────────────────────────

test("Settings lists recently deleted items with Restore", () => {
  const html = panel()._renderRecentlyDeletedSection();
  assert.match(html, /panel\.trash_title/);
  assert.match(html, /Water the plants/);
  assert.match(html, /panel\.trash_kind_quest/);
  assert.match(html, /data-act="trash-restore" data-kind="chore" data-id="plants"/);
  assert.match(html, /data-act="trash-restore" data-kind="quest" data-id="q1"/);
});

test("an empty bin says so", () => {
  const html = panel({ recently_deleted: [] })._renderRecentlyDeletedSection();
  assert.match(html, /panel\.trash_empty/);
  assert.doesNotMatch(html, /trash-restore/);
});

test("deleting a chore offers Undo, which restores it by id", async () => {
  const p = panel();
  const calls = [];
  const toasts = [];
  p._callWS = async (msg) => { calls.push(msg); return { ok: true, res: { name: "Make bed" } }; };
  p._fetchState = async () => {};
  p._showToast = (kind, text, action) => toasts.push({ kind, text, action });
  await p._doRemove("chore", "bed");
  assert.deepEqual(plain(calls[0]), { type: "taskmate/remove_chore", chore_id: "bed" });
  const { text, action } = toasts[0];
  assert.match(text, /panel\.trash_deleted.*Make bed/);
  assert.equal(action.label, "panel.trash_undo");
  await action.run();
  assert.deepEqual(plain(calls[1]), { type: "taskmate/recently_deleted/restore", kind: "chore", item_id: "bed" });
  assert.match(toasts[1].text, /panel\.trash_restored/);
});

test("a delete that isn't kept (a penalty) has no Undo", async () => {
  const p = panel({ penalties: [{ id: "pen", name: "Rude" }] });
  const toasts = [];
  p._callWS = async () => ({ ok: true, res: {} });
  p._fetchState = async () => {};
  p._showToast = (kind, text, action) => toasts.push({ kind, text, action });
  await p._doRemove("penalty", "pen");
  assert.equal(toasts[0].text, "panel.toast_deleted");
  assert.equal(toasts[0].action, undefined);
});

test("a failed restore is reported", async () => {
  const p = panel();
  const toasts = [];
  p._callWS = async () => ({ ok: false, err: "Something with id bed already exists" });
  p._showToast = (kind, text) => toasts.push({ kind, text });
  await p._restoreDeleted("chore", "bed");
  assert.equal(toasts[0].kind, "err");
  assert.match(toasts[0].text, /already exists/);
});

// ── Settings: jump list and command search ───────────────────────────────

const FAKE_SETTINGS = `
  <div class="tm-toolbar"><h2>Settings</h2></div>
  <div class="tm-settings">
    <div class="tm-section tm-wz-settings"><div class="tm-setting-row"><span class="tm-wz-settings-t"><ha-icon></ha-icon>Setup wizard</span></div></div>
    <div class="tm-section">
      <div class="tm-section-head"><div><h3>Allowance</h3><p class="tm-meta">Points to money</p></div></div>
      <div class="tm-section-body"></div>
    </div>
    <div class="tm-section tm-insp-settings">
      <div class="tm-section-head"><div><h3><ha-icon icon="mdi:magnify-scan"></ha-icon> Spot &amp; check</h3></div></div>
    </div>
  </div>`;

test("each Settings section is tagged and named from its heading", () => {
  const { html, sections } = panel()._settingsSectionsFrom(FAKE_SETTINGS);
  assert.deepEqual(plain(sections), [
    { i: 0, title: "Setup wizard", hint: "" },
    { i: 1, title: "Allowance", hint: "Points to money" },
    { i: 2, title: "Spot & check", hint: "" },
  ]);
  assert.match(html, /<div data-sec="1" class="tm-section">/);
  assert.match(html, /<div data-sec="2" class="tm-section tm-insp-settings">/);
  assert.doesNotMatch(html, /data-sec="\d+" class="tm-section-/, "section heads and bodies are not sections");
});

test("the Settings page leads with a jump list and carries the unsaved bar", () => {
  const p = panel();
  p._renderSettingsTab = () => FAKE_SETTINGS;
  const html = p._renderSettingsPage();
  const jump = html.indexOf("tm-set-jump");
  assert.ok(jump > 0 && jump < html.indexOf('<div class="tm-settings">'));
  assert.match(html, /data-act="settings-jump" data-sec="1">Allowance</);
  assert.match(html, /class="tm-unsaved-bar" role="status" hidden/);
  assert.match(html, /data-act="settings-discard"/);
});

test("the command search finds a Settings section by heading or hint", () => {
  const p = panel();
  p._renderSettingsTab = () => FAKE_SETTINGS;
  p._sidebarGroups = () => [];
  p._newMenuItems = () => [];
  p._palette = { q: "money", hi: 0 };
  const hit = p._paletteResults().find(c => c.data.act === "settings-jump");
  assert.ok(hit, "a section is found by its hint");
  assert.equal(hit.label, "Allowance");
  assert.equal(hit.data.sec, 1);
  assert.equal(hit.group, "panel.tab_settings");
  p._palette = { q: "", hi: 0 };
  assert.ok(!p._paletteResults().some(c => c.data.act === "settings-jump"), "sections only show when searched");
});

test("the real Settings page yields named sections, including Recently deleted", () => {
  const p = panel({ settings: { points_name: "Stars" } });
  p._renderSettingsTab = TaskMatePanel.prototype._renderSettingsTab;
  const titles = p._settingsSections().map(s => s.title);
  assert.ok(titles.includes("panel.settings_currency_title"));
  assert.ok(titles.includes("panel.trash_title"));
  assert.equal(p._recapScheduleLoading, undefined, "the dry render starts no fetch");
  assert.equal(p._timePeriodsDraft, undefined, "nor seeds a draft");
});

// ── Settings: unsaved changes ────────────────────────────────────────────

test("leaving Settings with unsaved changes asks first", () => {
  const p = panel();
  p._renderedTab = "settings";
  p._activeTab = "rewards";
  p._settingsDirtyCount = () => 2;
  p._guardSettingsLeave();
  assert.equal(p._activeTab, "settings");
  assert.equal(p._dialog.kind, "leave-settings");
  assert.deepEqual(plain(p._dialog.data), { to: "rewards", count: 2 });
  const html = p._renderLeaveSettingsDialog();
  assert.match(html, /panel\.unsaved_leave_many/);
  assert.match(html, /data-act="leave-settings-go"/);
  assert.match(html, /data-act="leave-settings-stay"/);

  p._render = () => {};
  p._leaveSettings();
  assert.equal(p._activeTab, "rewards");
  assert.equal(p._dialog, null);
});

test("leaving a clean Settings page just goes", () => {
  const p = panel();
  p._renderedTab = "settings";
  p._activeTab = "rewards";
  p._settingsDirtyCount = () => 0;
  p._guardSettingsLeave();
  assert.equal(p._activeTab, "rewards");
  assert.equal(p._dialog, undefined);
});

test("a field's value is read the way Save reads it", () => {
  const p = panel();
  const el = (tagName, props) => ({ tagName, getAttribute: (a) => props[a] ?? null, ...props });
  assert.equal(p._settingValue(el("HA-SWITCH", { checked: true })), true);
  assert.equal(p._settingValue(el("INPUT", { type: "number", value: "1.5" })), 1.5);
  assert.equal(p._settingValue(el("INPUT", { type: "number", value: "" })), "");
  assert.equal(p._settingValue(el("HA-ICON-PICKER", { value: undefined })), "");
  assert.equal(p._settingValue(el("SELECT", { value: "reset" })), "reset");
});

// ── Reward order ─────────────────────────────────────────────────────────

test("reward cards are draggable and the page offers Reorder", () => {
  const p = panel();
  p._filterByName = (x) => x;
  p._searchBox = () => "";
  p._idBadge = () => "";
  const html = p._renderRewardsTab();
  assert.match(html, /data-act="reorder-rewards"/);
  assert.match(html, /draggable="true" data-drag-id="xbox" data-drag-kind="reward"/);
  assert.match(html, /tm-reorder-handle/);
});

test("dropping a reward on another saves the new order", async () => {
  const p = panel();
  const calls = [];
  p._render = () => {};
  p._showToast = () => {};
  p._callWS = async (msg) => { calls.push(msg); return { ok: true }; };
  await p._moveReward("dinner", "cinema");
  assert.deepEqual(plain(calls[0]), { type: "taskmate/rewards/set_order", reward_order: ["dinner", "cinema", "xbox"] });
  assert.deepEqual(p._state.rewards.map(r => r.id), ["dinner", "cinema", "xbox"]);
});

test("the reorder dialog also orders rewards (the touch path)", () => {
  const p = panel();
  p._dialog = { kind: "reorder", data: { rewards: true, order: ["xbox", "cinema", "dinner"] } };
  const html = p._renderReorderDialog();
  assert.match(html, /panel\.reward_reorder_title/);
  assert.ok(html.indexOf("30 min Xbox") < html.indexOf("Cinema trip"));
  assert.match(html, /data-act="save-reward-order"/);
  assert.doesNotMatch(html, /save-chore-order/);
});

// ── Child quick view ─────────────────────────────────────────────────────

test("a top-bar child chip opens the quick view rather than filtering", () => {
  const html = panel()._scopeChips();
  assert.match(html, /data-act="kid-drawer" data-child="kid1"/);
  assert.match(html, /data-act="scope" data-child=""/, "All still clears the filter");
});

test("the quick view shows the child's numbers, today and the actions", () => {
  const p = panel();
  p._dialog = { kind: "kid-drawer", data: { child_id: "kid1" } };
  const html = p._renderKidDrawer();
  assert.match(html, /tm-drawer/);
  assert.match(html, /panel\.kid_drawer_level/);
  assert.match(html, /panel\.today_streak/);
  // The name is the drawer's title; it isn't repeated beside the avatar.
  assert.doesNotMatch(html, /tm-kd-head[\s\S]*>Malia<[\s\S]*tm-kd-stats/, "the name is the title, not repeated beside the avatar");
  assert.match(html, /panel\.screen_time_title/);
  assert.match(html, /panel\.kid_drawer_waiting<\/div><strong class="tm-numeric">2</, "a chore and a reward claim wait");
  assert.match(html, /panel\.kid_drawer_owed<\/div><strong class="tm-numeric">1</);
  assert.match(html, /class="tm-kd-done"><span aria-hidden="true">✅<\/span> Make bed/);
  assert.match(html, /class="tm-kd-pending"><span aria-hidden="true">⏳<\/span> Tidy room/);
  assert.match(html, /data-act="adjust-points-custom" data-id="kid1"/);
  assert.match(html, /data-act="kid-drawer-scope" data-child="kid1"/);
  assert.match(html, /data-act="edit-child" data-id="kid1"/);
  assert.match(html, /data-act="view-as" data-id="kid1"/);
});

test("the quick view hides screen time when the bank is off, and offers to clear a filter", () => {
  const p = panel({ settings: { points_name: "Stars" } });
  p._scope = "kid1";
  p._dialog = { kind: "kid-drawer", data: { child_id: "kid1" } };
  const html = p._renderKidDrawer();
  assert.doesNotMatch(html, /panel\.screen_time_title/);
  assert.match(html, /data-act="kid-drawer-scope" data-child="">panel\.scope_clear/);
});

// ── View as child ────────────────────────────────────────────────────────

test("view as child previews behind a shield, with child and design pickers", () => {
  const p = panel();
  p._viewAsReady = true;
  p._dialog = { kind: "view-as", data: { child_id: "kid1", design: "playroom" } };
  const html = p._renderViewAsDialog();
  assert.match(html, /class="tm-viewas-host" inert/);
  assert.match(html, /tm-viewas-shield/);
  assert.match(html, /panel\.view_as_note/);
  assert.match(html, /data-act="view-as-child" data-id="kid2"/);
  assert.doesNotMatch(html, /data-id="dad"/, "adults have no child card");
  assert.match(html, /<option value="global"/);
});

test("view as child mounts the real child card with the chosen design", () => {
  const p = panel();
  const config = [];
  const host = { appended: null, appendChild(el) { this.appended = el; el.parentNode = this; } };
  p.querySelector = (sel) => (sel === ".tm-viewas-host" ? host : null);
  p._overviewEntity = () => "sensor.taskmate_overview";
  p._hass = { states: {} };
  p._dialog = { kind: "view-as", data: { child_id: "kid2", design: "console" } };
  const card = { setConfig: (c) => config.push(c) };
  p._viewAsCard = card;
  elements.set("taskmate-child-card", class {});
  try {
    p._mountViewAsCard();
  } finally {
    elements.delete("taskmate-child-card");
  }
  assert.deepEqual(plain(config), [{ entity: "sensor.taskmate_overview", child_id: "kid2", card_design: "console" }]);
  assert.equal(card.hass, p._hass);
  assert.equal(host.appended, card);
});

test("the Children page offers View as for children, not adults", () => {
  const p = panel();
  p._idBadge = () => "";
  p._renderAdjustStrip = () => "";
  assert.match(p._renderChildCard(p._state.children[0], "Stars"), /data-act="view-as" data-id="kid1"/);
  assert.doesNotMatch(p._renderChildCard(p._state.children[2], "Stars"), /data-act="view-as"/);
});

// ── Insights: Economy ────────────────────────────────────────────────────

function economy(extra = {}) {
  return {
    weeks: Array.from({ length: 8 }, (_, i) => ({
      start: `2026-09-${String(1 + i * 7).padStart(2, "0")}`,
      end: `2026-09-${String(7 + i * 7).padStart(2, "0")}`,
      earned: 100 + i * 20, spent: 90,
    })),
    recent_earned: 680, recent_spent: 360, prior_earned: 360, earned_growth_pct: 89,
    ratio: 1.5, min_earned: 50, inflating: true,
    candidates: [{ id: "cinema", name: "Cinema trip", cost: 200, claims: 3 }, { id: "xbox", name: "30 min Xbox", cost: 40, claims: 2 }],
    ...extra,
  };
}

test("Economy is an Insights view", () => {
  const p = panel();
  p._insightView = "economy";
  p._ratingOn = () => false;
  p._economy = economy();
  const html = p._renderInsightsTab();
  assert.match(html, /data-act="insights-view" data-id="economy"/);
  assert.match(html, /panel\.economy_title/);
});

test("Economy draws earned and spent lines and names rewards to reprice", () => {
  const p = panel();
  p._economy = economy();
  const html = p._renderEconomyReport();
  const lines = render(html).all(/<polyline class="tm-econ-(earned|spent)" fill="none" points="([^"]+)"/g);
  assert.equal(lines.length, 2);
  for (const [, points] of lines) assert.equal(points.split(" ").length, 8);
  assert.match(html, /tm-verdict-warn/);
  assert.match(html, /panel\.economy_growth/);
  assert.match(html, /panel\.economy_warn:.*<strong>Cinema trip<\/strong>, <strong>30 min Xbox<\/strong>/);
  assert.doesNotMatch(html, /NaN|undefined/);
});

test("Economy in balance says so, and an empty one has no chart", () => {
  const p = panel();
  p._economy = economy({ inflating: false, candidates: [] });
  assert.match(p._renderEconomyReport(), /panel\.economy_ok/);
  p._economy = economy({ weeks: economy().weeks.map(w => ({ ...w, earned: 0, spent: 0 })), inflating: false });
  const empty = p._renderEconomyReport();
  assert.match(empty, /panel\.economy_none/);
  assert.doesNotMatch(empty, /<svg/);
});

// ── The rewards card follows the parent's order ─────────────────────────

const { get: getRewards } = loadCard("taskmate-rewards-card.js");
const RewardsCard = getRewards("taskmate-rewards-card");

function rewardsCard(design, ordered) {
  const card = new RewardsCard();
  card.config = { entity: "sensor.taskmate_overview", ...(design ? { card_design: design } : {}) };
  card.hass = {
    states: {
      "sensor.taskmate_overview": {
        state: "1",
        attributes: {
          children: [{ id: "kid1", name: "Malia", points: 30 }],
          rewards: [
            { id: "cinema", name: "Cinema trip", cost: 200, assigned_to: [] },
            { id: "xbox", name: "Xbox time", cost: 40, assigned_to: [] },
          ],
          ...(ordered ? { rewards_ordered: true } : {}),
        },
      },
    },
  };
  card._selectedChildId = "kid1";
  return render(card.render()).markup;
}

for (const design of [null, "playroom"]) {
  const label = design || "classic";
  test(`rewards card (${label}): sorts by price until a parent sets an order`, () => {
    const priced = rewardsCard(design, false);
    assert.ok(priced.indexOf("Xbox time") < priced.indexOf("Cinema trip"));
    const ordered = rewardsCard(design, true);
    assert.ok(ordered.indexOf("Cinema trip") < ordered.indexOf("Xbox time"));
  });
}

test("deleting a chore, reward or quest says it can be brought back; others still warn", () => {
  const asked = [];
  const Panel = loadCard("taskmate-panel.js", { sandbox: { confirm: (msg) => { asked.push(msg); return false; } } }).get("taskmate-panel");
  const p = Object.assign(Object.create(Panel.prototype), panel());
  p._state.quests = [{ id: "q1", name: "Half-term quest" }];
  p._state.penalties = [{ id: "pen1", name: "Shouting" }];
  p._confirmDelete("quest", "q1");
  p._confirmDelete("penalty", "pen1");
  assert.match(asked[0], /panel\.confirm_delete_suffix_restorable$/);
  assert.match(asked[1], /panel\.confirm_delete_suffix$/);
});

test("Economy week labels follow Home Assistant's language, not the browser's", () => {
  const p = panel();
  p._hass = { locale: { language: "de" } };
  p._economy = economy();
  const html = p._renderEconomyReport();
  assert.match(html, /1\. Sept\./, "German short month");
});
