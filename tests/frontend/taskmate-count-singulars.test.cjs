const assert = require("node:assert/strict");
const { readFileSync, readdirSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { WWW } = require("./harness.cjs");

// #771 gate: the overview card's designed styles said "1 approvals waiting"
// ("1 Freigaben ausstehend", "1 validations en attente"). Every card count that
// can be 1 now has a `_one` string, as trophy.count / heatmap.cell already did;
// Polish keeps its "Label: {count}" form for the rest, so it never needs the
// few/many split.

const KEYS = {
  "overview.designed.approvals_waiting": "taskmate-overview-card.js",
  "overview.designed.waiting_for_you": "taskmate-overview-card.js",
  "activity.events_count": "taskmate-activity-card.js",
  "approvals.approve_all_confirm": "taskmate-approvals-card.js",
  "leaderboard.best_streak_value": "taskmate-leaderboard-card.js",
  "points_display.family_subtitle": "taskmate-points-display-card.js",
  "streak.freezes_aria": "taskmate-streak-card.js",
  "weekly.child_chores": "taskmate-weekly-card.js",
  "raffle.tickets_total": "taskmate-raffle-card.js",
  "raffle.your_tickets": "taskmate-raffle-card.js",
  "kiosk.raffle_tickets": "taskmate-kiosk-card.js",
};
const LOCALES = path.join(WWW, "locales");
const langs = readdirSync(LOCALES).filter((f) => f.endsWith(".json")).map((f) => f.slice(0, -5));
const loc = (l) => JSON.parse(readFileSync(path.join(LOCALES, `${l}.json`), "utf8"));

test("every count that can be 1 has a singular string in every language", () => {
  const en = loc("en");
  for (const lang of langs) {
    const d = loc(lang);
    for (const key of Object.keys(KEYS)) {
      const one = d[`${key}_one`];
      assert.ok(one && one.trim(), `${lang} lacks ${key}_one`);
      assert.match(one, /\b1\b|\{count\}/, `${lang} ${key}_one has neither 1 nor {count}`);
      for (const p of (d[key].match(/\{\w+\}/g) || []).filter((x) => x !== "{count}")) {
        assert.ok(one.includes(p), `${lang} ${key}_one drops ${p}`);
      }
      if (!lang.startsWith("en")) assert.notEqual(one, en[`${key}_one`], `${lang} ${key}_one left in English`);
    }
  }
});

test("each card picks the singular string when the count is 1", () => {
  for (const [key, file] of Object.entries(KEYS)) {
    const src = readFileSync(path.join(WWW, file), "utf8");
    const esc = key.replace(/[\\^$.*+?()[\]{}|]/g, "\\$&");
    const calls = src.match(new RegExp(`_t\\([^;]*?["']${esc}["']`, "g")) || [];
    assert.ok(calls.length, `${file} never uses ${key}`);
    for (const c of calls) assert.match(c, new RegExp(`=== 1 \\? ["']${esc}_one["']`), `${file}: ${c}`);
  }
  // The child card shares the streak-freeze label.
  assert.match(readFileSync(path.join(WWW, "taskmate-child-card.js"), "utf8"), /n === 1 \? "streak\.freezes_aria_one"/);
});

test("Polish streak title avoids the few/many noun forms", () => {
  assert.equal(loc("pl")["child.chore_streak_title"], "Zrobione w zaplanowane dni z rzędu: {count}");
});

// #771 re-check: the "(s)" convention ("1 chore(s)", "1 pendente(s)",
// "{count} Aufgabe(n)") is gone; each such string has a real singular and
// plural, and the panel picks between them with _tn().
const PANEL_KEYS = [
  "panel.boost_test_wake_sent", "panel.bulk_delete_confirm_restorable", "panel.bulk_done_toast",
  "panel.bulk_selected", "panel.fb_health_found", "panel.fb_logs_found", "panel.group_chore_count",
  "panel.health_issues", "panel.insights_friction_problems", "panel.notif_test_sent",
  "panel.pending_tooltip", "panel.sound_deleted_reset", "panel.template_confirm_bar",
  "panel.template_create_btn", "panel.template_pts_total", "panel.toast_bulk_added",
  "panel.toast_created_chores", "panel.toast_settings_saved", "panel.today_left",
  "panel.topbar_chore_count", "panel.topbar_pending", "panel.topbar_reward_count",
  "panel.topbar_swap_count", "panel.tp_in_use_hint", "panel.tp_in_use_title",
];

test('no count string uses the "(s)" plural convention in any language', () => {
  const bad = [];
  for (const lang of langs) {
    for (const [k, v] of Object.entries(loc(lang))) {
      if (typeof v === "string" && v.includes("{count}") && /\p{L}\((?:s|es|n|en|e|er|r|ar|i|os|as|ões)\)/u.test(v)) bad.push(`${lang} ${k}: ${v}`);
    }
  }
  assert.deepEqual(bad, []);
});

test("every panel count string has a singular, and the panel picks it with _tn()", () => {
  const src = readFileSync(path.join(WWW, "taskmate-panel.js"), "utf8");
  for (const key of PANEL_KEYS) {
    for (const lang of langs) assert.ok(loc(lang)[`${key}_one`], `${lang} lacks ${key}_one`);
    assert.ok(src.includes(`this._tn("${key}", `), `${key} is not looked up with _tn()`);
    assert.ok(!src.includes(`this._t("${key}"`), `${key} still looked up without its singular`);
  }
  assert.equal(loc("en")["panel.fb_logs_found_one"], "{count} recent warning or error from TaskMate. Names are replaced with placeholders.");
  for (const [key, file] of [["activity.rated", "taskmate-activity-card.js"], ["routine.skipped_note", "taskmate-routine-card.js"]]) {
    assert.match(readFileSync(path.join(WWW, file), "utf8"), new RegExp(`=== 1 \\? ['"]${key.replace(".", "\\.")}_one['"]`));
  }
});

test("_tn() picks the singular for 1 and keeps a caller's own {count}", () => {
  const { loadCard } = require("./harness.cjs");
  const Panel = loadCard("taskmate-panel.js").get("taskmate-panel");
  const p = Object.create(Panel.prototype);
  const seen = [];
  p._t = (key, params) => (seen.push([key, { ...params }]), key);
  p._tn("panel.topbar_chore_count", 1, { count: "<strong>1</strong>" });
  p._tn("panel.topbar_chore_count", 3);
  p._tn("panel.bulk_selected", "1");
  assert.deepEqual(JSON.parse(JSON.stringify(seen)), [
    ["panel.topbar_chore_count_one", { count: "<strong>1</strong>" }],
    ["panel.topbar_chore_count", { count: 3 }],
    ["panel.bulk_selected_one", { count: "1" }],
  ]);
});
