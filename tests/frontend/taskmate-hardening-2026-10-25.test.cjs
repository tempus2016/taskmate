// Hardening pass of 2026-10-25 — the frontend half.
//
//   1. The panel's undo deny-list carries every derived transaction reason the
//      backend refuses to reverse (the Python copy is pinned against this one
//      by tests/test_panel_undo_deny_list.py).
//   2. The Help & feedback issue title is redacted like the logs and the body
//      before it is sent to api.github.com as a search.
//   3. The shared child-avatar helper only turns allow-listed URLs into an
//      <img src>; anything else means "no picture".
//   4. A hostile-state render of every panel tab and dialog: a marker string
//      in every text field, javascript: in every URL field, and nothing may
//      come out unescaped or land in an href/src.

const assert = require("node:assert/strict");
const { test } = require("node:test");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const { loadCard, localize, WWW } = require("./harness.cjs");

const PANEL_SANDBOX = {
  navigator: { userAgent: "test", language: "en" },
  localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
};

function loadPanel(extraSandbox = {}, transform) {
  return loadCard("taskmate-panel.js", { sandbox: { ...PANEL_SANDBOX, ...extraSandbox }, transform });
}

// ── 1. undo deny-list ───────────────────────────────────────────────────────

// Reasons the backend writes for derived transactions. Undoing one of these
// on its own would leave the thing it paid for (a raffle, a quest, a payout)
// in place, so neither side offers undo for them.
const DERIVED_REASON_PREFIXES = [
  "Raffle tickets", "Raffle called off", "Allowance payout", "Made it right",
  "Quest complete", "Quest reversed", "Challenge complete", "Challenge reversed",
  "Weekly goal reached", "Weekly goal reversed", "All times done",
  "Appeal:", "Sibling check:", "Surprise bonus",
  "Perfect week bonus reversed", "Streak milestone reversed",
];

test("the panel refuses to undo every derived transaction reason", () => {
  const { get } = loadPanel();
  const p = Object.create(get("taskmate-panel").prototype);
  for (const prefix of DERIVED_REASON_PREFIXES) {
    assert.equal(p._txnReversible(`${prefix} something`), false, `"${prefix}…" must not be undoable`);
    assert.equal(p._txnReversible(prefix), false, `"${prefix}" must not be undoable`);
  }
  // The deny-list must stay a deny-list (#761): free-text and empty reasons are reversible.
  assert.equal(p._txnReversible("Penalty: Messy room"), true);
  assert.equal(p._txnReversible("Broke a window"), true);
  assert.equal(p._txnReversible(""), true);
});

// ── 2. feedback search redaction ────────────────────────────────────────────

function feedbackPanel() {
  const calls = [];
  const fetch = async (url) => {
    calls.push(String(url));
    return { ok: true, json: async () => ({ items: [] }) };
  };
  const { get } = loadPanel({ fetch });
  const p = Object.create(get("taskmate-panel").prototype);
  p._t = (key, params) => localize(key, params);
  p._state = { children: [{ id: "k1", name: "Malia Mackinnon" }, { id: "k2", name: "Vaiha" }], settings: {} };
  p._hass = { user: { name: "John Mackinnon" } };
  p._fbPaint = () => {};
  p._render = () => {};
  return { p, calls };
}

test("the feedback search query carries no household names", async () => {
  const { p, calls } = feedbackPanel();
  const d = p._fbDraft();
  d.bug.title = "Malia points vanish overnight for Vaiha and Mackinnon";
  const q = p._fbSearchQuery();
  assert.ok(q, "a long enough title must still produce a search");
  for (const name of ["Malia", "Vaiha", "Mackinnon"]) {
    assert.ok(!q.includes(name), `search query leaked "${name}": ${q}`);
  }
  assert.ok(q.includes("points") && q.includes("vanish"), `the useful words survive: ${q}`);
  // Placeholders are not search terms either.
  assert.ok(!/\[name|\[email|\[hidden/.test(q), `placeholder leaked into the query: ${q}`);

  await p._fbSearch(q);
  assert.equal(calls.length, 1, "one request to GitHub");
  assert.ok(calls[0].startsWith("https://api.github.com/search/issues?"));
  const sent = decodeURIComponent(calls[0]);
  for (const name of ["Malia", "Vaiha", "Mackinnon"]) {
    assert.ok(!sent.includes(name), `request to GitHub leaked "${name}": ${sent}`);
  }
});

test("the feedback search query strips addresses and tokens too", () => {
  const { p } = feedbackPanel();
  const d = p._fbDraft();
  d.bug.title = "Notify fails for sam@example.com with token=abc123def";
  const q = p._fbSearchQuery();
  assert.doesNotMatch(q, /sam@example\.com|abc123def/, q);
  assert.ok(q.includes("Notify") && q.includes("fails"), q);
});

// ── 3. child avatar URL allow-list ──────────────────────────────────────────

// Objects born in the design layer's vm context have a foreign prototype, so
// they are flattened before a strict deep compare.
const plain = (v) => JSON.parse(JSON.stringify(v));

function designLayer() {
  const window = { matchMedia: () => ({ matches: false }) };
  vm.runInNewContext(readFileSync(path.join(WWW, "taskmate-design.js"), "utf8"), {
    window,
    document: { documentElement: { getAttribute: () => "" }, getElementById: () => ({}), createElement: () => ({}), head: { appendChild() {} } },
    customElements: { get: () => undefined },
  });
  return window;
}

const ALLOWED_AVATARS = [
  "/api/taskmate/image/" + "a".repeat(32) + ".jpg",
  "/api/image/serve/abc/512x512",
  "/local/a.png",
  "/hacsfiles/taskmate/kid.png",
  "data:image/png;base64,iVBORw0KGgo=",
  "https://example.com/kid.png",
];

const REJECTED_AVATARS = [
  "javascript:alert(1)",
  "JavaScript:alert(1)",
  "data:text/html,<script>alert(1)</script>",
  "http://example.com/kid.png",
  "//evil.example/kid.png",
  "vbscript:msgbox(1)",
  "../local/a.png",
  "local/a.png",
  "/api",
  "  /local/a.png",
];

test("child avatar: allow-listed URLs become a picture", () => {
  const layer = designLayer().__taskmate_child_visual;
  const visual = (...args) => plain(layer(...args));
  for (const url of ALLOWED_AVATARS) {
    assert.deepEqual(visual({ avatar: url }), { kind: "image", url }, url);
    assert.deepEqual(visual(url), { kind: "image", url }, `bare string ${url}`);
    assert.deepEqual(visual({ avatar_image: url }), { kind: "image", url }, `avatar_image ${url}`);
  }
  assert.deepEqual(visual({ avatar: "mdi:account" }), { kind: "icon", icon: "mdi:account" });
});

test("child avatar: anything else means no picture", () => {
  const layer = designLayer().__taskmate_child_visual;
  const visual = (...args) => plain(layer(...args));
  for (const url of REJECTED_AVATARS) {
    assert.deepEqual(visual({ avatar: url }), { kind: "none" }, url);
    assert.deepEqual(visual(url), { kind: "none" }, `bare string ${url}`);
    assert.deepEqual(visual({ avatar_image: url }), { kind: "none" }, `avatar_image ${url}`);
  }
  // A rejected photo falls back to the MDI avatar, as a missing photo would.
  assert.deepEqual(visual({ avatar_image: "javascript:alert(1)", avatar: "mdi:cat" }), { kind: "icon", icon: "mdi:cat" });
  assert.deepEqual(visual({}), { kind: "none" });
  assert.deepEqual(visual(null), { kind: "none" });
});

// ── 4. hostile-state render of the whole panel ──────────────────────────────
//
// This is a regression guard, not a bug fix: the panel passes it today. It
// exists because `_t()` splices its params into the string unescaped, so every
// call site that renders a stored name through a translation has to escape it
// first — and a single new call site can miss that. Rendering every tab and
// every dialog with a marker in every text field catches that at test time.

const H = (field) => `"'><img src=x onerror=F_${field}>`;
const RAW_MARKER = /<img src=x onerror=F_(\w+)>/g;
const ESCAPED_MARKER = /&lt;img src=x onerror=F_\w+&gt;/g;
// Links may point at the web (a wish's shop link, the Help tab's GitHub links)
// but never at a script or a protocol-relative host; a `src` may only point at
// TaskMate's own images or the inline SVG the panel draws its icons with.
const URL_SINK = /\b(href|src|data-photo|data-url|data-src)\s*=\s*["']\s*(javascript:|data:(?!image\/svg\+xml)|vbscript:|\/\/)/gi;
const SRC_ALLOWED = /^(\/api\/taskmate\/|data:image\/svg\+xml)/;

const NOW = "2026-10-20T10:00:00.000Z";
const LATER = "2999-01-01T00:00:00.000Z";

function kid(id, n) {
  return {
    id, name: H(`child_name_${n}`), avatar: H("child_avatar"), color: H("child_color"), points: 10,
    current_streak: 2, level: 1, linked_user_id: H("linked"), ha_user_id: H("hauser"), birthday: "2015-01-01",
    is_adult: false, avatar_image: H("avatar_image"), notes: H("child_notes"),
  };
}

const CHORE = {
  id: "ch1", name: H("chore_name"), description: H("chore_desc"), icon: H("chore_icon"), points: 5,
  assigned_to: ["k1", "k2"], tags: [H("chore_tag")],
  times: [{ id: "t1", name: H("time_name"), start: "08:00", end: "09:00", points: 1 }],
  bonus_subtasks: [{ id: "b1", name: H("subtask_name"), points: 1 }], subtasks: [{ id: "s1", name: H("subtask2") }],
  image_url: "javascript:alert(1)", reference_image_url: "/api/taskmate/image/x", notes: H("chore_notes"),
  quantity_unit: H("qunit"), time_category: "anytime", assignment_mode: "everyone", schedule_mode: "specific_days",
  due_days: ["monday"], enabled: true, visibility_entity: H("vis"), visibility_state: H("visstate"),
};

const REWARD = {
  id: "r1", name: H("reward_name"), description: H("reward_desc"), icon: H("reward_icon"), cost: 10,
  assigned_to: [], image_url: "javascript:alert(1)", quantity_str: H("qstr"),
};

function hostileState() {
  return {
    children: [kid("k1", 1), kid("k2", 2)], chores: [CHORE], rewards: [REWARD],
    wishes: [
      { id: "w1", child_id: "k1", name: H("wish_name"), link: "javascript:alert(1)", image_url: "javascript:x", status: "pending",
        target: 10, saved: 1, pledged: 1, note: H("wish_note"), description: H("wish_desc") },
      { id: "w2", child_id: "k1", name: H("wish2"), link: "https://e.x/" + H("wishlink"), status: "active", target: 10, saved: 1,
        pledged: 1, pledges: [{ id: "p1", name: H("pledger"), amount: 1, message: H("pledge_msg") }] },
      { id: "w3", child_id: "k2", name: H("wish3"), status: "redeemed", redeemed_at: NOW, target: 5 },
    ],
    bounties: [
      { id: "bo1", title: H("bounty_title"), description: H("bounty_desc"), icon: H("bounty_icon"), status: "open", points: 5, claimed_by: "k1" },
      { id: "bo2", title: H("bounty2"), status: "claimed", claimed_by: "k1", completion_id: "c1", claim_until: NOW },
      { id: "bo3", title: H("bounty3"), status: "expired", closed_at: NOW },
    ],
    templates: [{ id: "tp1", name: H("template_name"), chores: [{ name: H("tpl_chore"), points: 1 }] }],
    pending_completions: [{ id: "c1", chore_id: "ch1", child_id: "k1", completed_at: NOW, photo_url: "javascript:alert(1)",
      note: H("completion_note"), check_note: H("check_note"), checked_by: "k2", time_id: "t1", appeal: H("appeal_c") }],
    completions: [{ id: "c2", chore_id: "ch1", child_id: "k1", completed_at: NOW, approved: true, note: H("comp_note2"), rating: 3 }],
    pending_reward_claims: [{ id: "rc1", reward_id: "r1", child_id: "k1", claimed_at: NOW, note: H("claim_note"), recipient_id: "k2", from_name: H("from_name") }],
    reward_claims: [{ id: "rc2", reward_id: "r1", child_id: "k1", claimed_at: NOW, approved: true, approved_at: NOW, from_name: H("from_name2") }],
    auctions: [
      { id: "a1", chore_name: H("auction_chore"), chore_id: "ch1", status: "open", eligible_child_ids: ["k1"], max_points: 5, min_points: 2,
        closes_at: NOW, bids: [{ child_id: "k1", points: 3 }] },
      { id: "a2", chore_name: H("auction2"), status: "closed", winner_id: "k1", price: 3 },
    ],
    badges: [{ id: "bg1", name: H("badge_name"), description: H("badge_desc"), icon: H("badge_icon"),
      criteria: [{ metric: "total_points", operator: ">=", value: 1 }], tier: "gold" }],
    awarded_badges: [{ id: "ab1", badge_id: "bg1", child_id: "k1", awarded_at: NOW, note: H("award_note") }],
    task_groups: [{ id: "g1", name: H("group_name"), chore_ids: ["ch1", H("missing_id")], policy: "all" }],
    swap_requests: [{ id: "sw1", chore_id: "ch1", from_child_id: "k1", to_child_id: "k2", reason: H("swap_reason"), name: H("swap_name") }],
    raffles: [{ id: "ra1", name: H("raffle_name"), prize: H("raffle_prize"), status: "open", max_tickets: 3, entries: [{ child_id: "k1", tickets: 1 }] }],
    penalties: [{ id: "pe1", name: H("penalty_name"), description: H("pen_desc"), points: 2, icon: H("pen_icon") }],
    bonuses: [{ id: "bn1", name: H("bonus_name"), description: H("bon_desc"), points: 2, icon: H("bon_icon") }],
    quests: [{ id: "q1", name: H("quest_name"), description: H("quest_desc"), steps: [{ chore_id: "ch1", name: H("step") }],
      bonus_points: 5, active: true, icon: H("quest_icon") }],
    challenges: [{ id: "cg1", name: H("challenge_name"), description: H("chal_desc"), scope: "daily", metric: "chores", target: 2,
      bonus_points: 5, active: true, icon: H("chal_icon") }],
    points_transactions: [
      { id: "tx1", child_id: "k1", points: 5, reason: H("txn_reason"), created_at: NOW },
      { id: "tx2", child_id: "k1", points: -5, reason: "Penalty: " + H("txn_pen"), created_at: NOW },
    ],
    recently_deleted: [{ id: "d1", kind: "chore", name: H("deleted_name"), deleted_at: NOW }],
    appeals: [{ id: "ap1", child_id: "k1", kind: "rejection", text: H("appeal_text"), reason: H("appeal_reason"),
      chore_name: H("appeal_chore"), status: "pending", created_at: NOW }],
    help_requests: [{ id: "h1", child_id: "k1", chore_id: "ch1", message: H("help_msg"), text: H("help_text"), created_at: NOW }],
    inspections: [{ id: "i1", child_id: "k1", chore_name: H("insp_chore"), until: NOW, bonus: 2, note: H("insp_note"), tell_child: true }],
    inspectable_completions: [{ id: "c2", chore_name: H("insp_comp"), child_id: "k1" }],
    owed_rewards: [{ id: "o1", child_id: "k1", reward_name: H("owed_name"), name: H("owed2"), from_name: H("owed_from") }],
    moods_today: [{ child_id: "k1", mood: H("mood"), note: H("mood_note") }],
    audit_log: [{ ts: NOW, user_name: H("audit_user"), action: H("audit_action"), target: H("audit_target"), count: 1 }],
    custom_sounds: [{ file: H("sound_file"), name: H("sound_name"), url: "javascript:alert(1)" }],
    boosts: [{ id: "bs1", chore_ids: ["ch1"], child_ids: ["k1"], multiplier: 2, starts_at: NOW, ends_at: LATER }],
    boost_rules: [{ id: "br1", chore_ids: ["ch1"], child_ids: ["k1"], start: "08:00", end: "09:00", days: [1], multiplier: 2 }],
    scheduled_changes: [{ id: "sc1", chore_id: "ch1", field: "points", value: H("sched_val"), note: H("sched_note"), apply_on: "2030-01-01" }],
    avatar_catalog: [H("avatar_cat")],
    allowance_payouts: [], screen_time: [], pool_allocations: [], sick_today: [], parent_completable: [],
    chore_display_order: [], kiosk_pin_children: [],
    boost_wake_candidates: { screens: [{ entity_id: "media_player.x", name: H("screen_name") }], devices: [{ id: "d", name: H("device_name") }] },
    today: { children: [{ child_id: "k1", due: 2, done: 1, chores: [{ chore_id: "ch1", status: "pending" }] }] },
    settings: { points_name: H("points_name"), points_icon: H("points_icon") },
  };
}

const TABS = ("today children activity insights chores rewards wishlists penalties bonuses groups quests challenges"
  + " bounties raffles auctions badges templates notifications audit settings help setup").split(" ");

const DIALOG_KINDS = ("swap gift adjust backdate child chore reward penalty raffle bonus group quest avatar-catalog challenge"
  + " bounty boost boost-rule auction apply-penalty apply-bonus bulk-chore reorder kid-drawer view-as leave-settings"
  + " create-template edit-template badge award-badge wish-pledge wish-decline reject wizard-confirm library dash-create"
  + " insp-start insp-pass insp-fail manual-help").split(" ");

const CHROME = ["_sidebar", "_topbar", "_subTabs", "_mobileTabs", "_scopeBanner", "_approvalBanner", "_bottomNav",
  "_renderPalette", "_renderSaveTemplateDialog", "_scopeChips"];

const { get: getHostile } = loadPanel();
const HostilePanel = getHostile("taskmate-panel");

function hostilePanel() {
  const p = Object.create(HostilePanel.prototype);
  p._hass = { language: "en", user: { is_admin: true }, states: {}, locale: { language: "en" } };
  p._state = hostileState();
  p._zoneCache = {};
  p._bulkSel = new Set();
  p._man = { q: "", open: new Set(), doc: "index" };
  p._haUsers = [{ id: "u1", name: H("ha_user"), is_admin: false }];
  p._hubTabs = {};
  p._palette = { q: "", hi: 0 };
  p._scope = "k1";
  p.querySelector = () => null;
  p.querySelectorAll = () => [];
  p.appendChild = () => {};
  return p;
}

/** Everything wrong with a piece of rendered markup, as messages (empty = clean). */
function audit(html) {
  const problems = [];
  if (typeof html !== "string") return problems;
  for (const m of html.matchAll(RAW_MARKER)) problems.push(`unescaped text from field "${m[1]}"`);
  for (const m of html.matchAll(URL_SINK)) problems.push(`${m[1]} points off-origin or at a script: ${m[0]}`);
  for (const m of html.matchAll(/<(\w+)\b[^>]*\bsrc\s*=\s*["']([^"']*)["']/gi)) {
    if (!SRC_ALLOWED.test(m[2])) problems.push(`<${m[1]} src> outside TaskMate's own images: ${m[2].slice(0, 80)}`);
  }
  return problems;
}

function escapedCount(html) {
  return typeof html === "string" ? (html.match(ESCAPED_MARKER) || []).length : 0;
}

test("the hostile-state audit itself catches what it is meant to", () => {
  assert.deepEqual(audit("<p>&lt;img src=x onerror=F_name&gt;</p>"), []);
  assert.equal(audit(`<p>${H("name")}</p>`).length, 1);
  assert.equal(audit('<a href="javascript:alert(1)">x</a>').length, 1);
  assert.equal(audit('<img src="https://evil.example/t.png">').length, 1);
  assert.equal(audit('<audio src="javascript:alert(1)">').length, 2);
  assert.equal(audit('<a href="//evil.example/">x</a>').length, 1);
  assert.deepEqual(audit('<a href="https://github.com/tempus2016/taskmate">x</a>'), []);
  assert.equal(audit('<div data-photo="data:text/html,x"></div>').length, 1);
  assert.deepEqual(audit('<img src="/api/taskmate/image/abc.jpg">'), []);
});

const seenEscaped = { total: 0 };

for (const tab of TABS) {
  test(`hostile state: the ${tab} tab renders with nothing unescaped`, () => {
    const p = hostilePanel();
    p._activeTab = tab;
    const html = p._renderBody();
    assert.deepEqual(audit(html), [], `tab ${tab}`);
    seenEscaped.total += escapedCount(html);
  });
}

for (const kind of DIALOG_KINDS) {
  test(`hostile state: the ${kind} dialog renders with nothing unescaped`, () => {
    const state = hostileState();
    const items = {
      child: state.children[0], chore: state.chores[0], reward: state.rewards[0], penalty: state.penalties[0],
      bonus: state.bonuses[0], raffle: state.raffles[0], group: state.task_groups[0], quest: state.quests[0],
      challenge: state.challenges[0], bounty: state.bounties[0], auction: state.auctions[0], badge: state.badges[0],
    };
    for (const mode of ["edit", "add"]) {
      const p = hostilePanel();
      const base = items[kind] ? JSON.parse(JSON.stringify(items[kind])) : {};
      const data = Object.assign({
        id: "x", name: H(`dlg_name_${kind}`), child_id: "k1", child_name: H("dlg_child_name"), chore_name: H("dlg_chore_name"),
        chore_id: "ch1", badge_name: H("dlg_badge_name"), wish_id: "w2", kind: "chore", reason: H("dlg_reason"),
        message: H("dlg_msg"), title: H("dlg_title"), completion_id: "c1", rewards: false, order: ["ch1"],
        item: state.penalties[0], items: [], points: 2, chore_ids: ["ch1"], child_ids: ["k1"], days: [1], when: "now",
        multiplier: 2, minutes: 30, start: "08:00", end: "09:00", occurrences: [{ date: "2030-01-01", label: H("occ") }],
        normal_points: 5, url: "javascript:alert(1)", photo_url: "javascript:alert(1)", image_url: "javascript:alert(1)",
      }, base);
      p._dialog = { kind, mode, data, id: base.id || "x", item: base };
      const html = p._renderDialog();
      assert.deepEqual(audit(html), [], `dialog ${kind} (${mode})`);
      seenEscaped.total += escapedCount(html);
    }
  });
}

test("hostile state: the panel chrome renders with nothing unescaped", () => {
  for (const fn of CHROME) {
    const p = hostilePanel();
    p._activeTab = "chores";
    const html = p[fn]();
    assert.deepEqual(audit(html), [], fn);
    seenEscaped.total += escapedCount(html);
  }
});

test("hostile state: the marker actually reached the templates", () => {
  // If this drops to 0 the fixtures no longer line up with the panel's state
  // shape and the tests above are checking nothing.
  assert.ok(seenEscaped.total > 300, `only ${seenEscaped.total} escaped markers were rendered`);
});
