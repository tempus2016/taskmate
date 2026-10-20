// Admin panel → Help & feedback: a pre-filled GitHub "new issue" link.
//
// Pins the link GitHub receives (template, field ids, the template's own
// option text), that it stays under GitHub's length limit by shedding the
// oldest log lines first, that names and secrets never leave in the logs,
// and that text a parent typed is escaped when the page is drawn.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, localize } = require("./harness.cjs");

function load(storage = {}, extra = {}) {
  const store = { ...storage };
  const localStorage = {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
  };
  const loaded = loadCard("taskmate-panel.js", {
    sandbox: { ...extra, localStorage, navigator: { userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36" } },
    transform: (src) => `${src}\nwindow.__fb = { feedbackRedact, feedbackLogEntries, feedbackIssueUrl, feedbackBrowser, FEEDBACK_URL_MAX, FEEDBACK_DRAFT_KEY };`,
  });
  return { Panel: loaded.get("taskmate-panel"), fb: loaded.window.__fb, store };
}

const INFO = {
  integration_version: "test", ha_version: "2026.10.2",
  installation_type: "container", installation_type_raw: "Home Assistant Container",
  install_method: "hacs_default", lovelace_mode: "storage", language: "en-GB",
  counts: { children: 2, adults: 1, chores: 42, rewards: 9 }, card_design: "graphite",
  health_codes: [], entry_id: "entry-1",
};

function panel(storage, info = INFO) {
  const { Panel, fb, store } = load(storage);
  const p = Object.create(Panel.prototype);
  p._t = (key, params) => localize(key, params);
  p._state = { children: [{ id: "k1", name: "Malia" }, { id: "k2", name: "Vaiha" }], settings: {} };
  p._fbInfo = info;
  p._fbLogs = [];
  p._render = () => {};
  return { p, fb, store };
}

function params(url) {
  return new URL(url).searchParams;
}

function fill(p, fields) {
  const d = p._fbDraft();
  Object.assign(d[d.type], fields);
}

const BUG = { title: "Points vanish", description: "Malia's points went to 0", expected: "They stay", steps: "1. Wait for midnight" };

// ── pure helpers ────────────────────────────────────────────────────────────

test("the issue link carries the template, the title and only non-empty fields", () => {
  const { fb } = load();
  const url = fb.feedbackIssueUrl("bug_report.yml", "[Bug]: A & B", { description: "x y", steps: "", logs: null });
  assert.ok(url.startsWith("https://github.com/tempus2016/taskmate/issues/new?"));
  const q = params(url);
  assert.equal(q.get("template"), "bug_report.yml");
  assert.equal(q.get("title"), "[Bug]: A & B");
  assert.equal(q.get("description"), "x y");
  assert.equal(q.has("steps"), false);
  assert.equal(q.has("logs"), false);
});

test("names are replaced with placeholders, whole words only, longest first", () => {
  const { fb } = load();
  const out = fb.feedbackRedact("Anna and ann; Annabel. MALIA's chore — Maliable stays", ["Ann", "Anna", "Malia", "", "x"]);
  assert.equal(out, "[name 2] and [name 3]; Annabel. [name 1]'s chore — Maliable stays");
});

test("non-Latin names are matched as whole words too", () => {
  const { fb } = load();
  assert.equal(fb.feedbackRedact("Zoë done, Zoëlle not", ["Zoë"]), "[name 1] done, Zoëlle not");
  assert.equal(fb.feedbackRedact("Łukasz: ok", ["łukasz"]), "[name 1]: ok");
});

test("signed URLs, bearer tokens and e-mail addresses are masked", () => {
  const { fb } = load();
  const out = fb.feedbackRedact("GET /api/taskmate/photo/a.jpg?authSig=abc.def&x=1 Bearer eyJ.abc-d mail john@example.co.uk password=hunter2", []);
  assert.ok(!out.includes("abc.def") && out.includes("authSig=[hidden]&x=1"));
  assert.ok(out.includes("Bearer [hidden]") && !out.includes("eyJ"));
  assert.ok(out.includes("[email]") && !out.includes("john@"));
  assert.ok(!out.includes("hunter2"));
});

test("an address holding a family name is still masked whole", () => {
  // Found on ha-dev: the signed-in user's name was swapped out of their own
  // e-mail first, which left "@example.com" behind.
  const { fb } = load();
  const out = fb.feedbackRedact("contact john@example.com or John", ["John"]);
  assert.equal(out, "contact [email] or [name 1]");
});

test("log entries keep TaskMate's own records, newest N, printed oldest first", () => {
  const { fb } = load();
  const records = [
    { name: "custom_components.taskmate.coordinator", level: "ERROR", message: ["Boom for Malia"], timestamp: 300, count: 3 },
    { name: "homeassistant.components.zha", level: "WARNING", message: ["not ours"], timestamp: 400 },
    { name: "homeassistant.helpers.entity", level: "WARNING", message: ["entity from us"], timestamp: 200,
      source: ["custom_components/taskmate/sensor.py", 10] },
    { name: "custom_components.taskmate", level: "WARNING", message: ["oldest"], timestamp: 100 },
  ];
  const lines = fb.feedbackLogEntries(records, ["Malia"], 2);
  assert.equal(lines.length, 2);
  assert.ok(lines[0].includes("entity from us"), "older of the two newest comes first");
  assert.ok(lines[1].includes("ERROR [custom_components.taskmate.coordinator] Boom for [name 1] (×3)"));
  assert.ok(!lines.join().includes("not ours") && !lines.join().includes("Malia"));
});

test("a long traceback keeps its last lines", () => {
  const { fb } = load();
  const exception = Array.from({ length: 30 }, (_, i) => `line ${i}`).join("\n");
  const [entry] = fb.feedbackLogEntries([{ name: "custom_components.taskmate", level: "ERROR", message: ["x"], timestamp: 1, exception }], []);
  assert.ok(entry.includes("line 29") && entry.includes("line 18") && !entry.includes("line 17\n"));
  assert.ok(entry.includes("  …"));
});

test("the browser is summarised, never sent as the raw user agent", () => {
  const { fb } = load();
  assert.equal(fb.feedbackBrowser("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36"), "Chrome 141 on Windows");
  assert.equal(fb.feedbackBrowser("Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 Version/18.1 Mobile/15E148 Safari/604.1"), "Safari 18.1 on iOS 18.1");
  assert.equal(fb.feedbackBrowser("Home Assistant/2025.1 (io.robbie.HomeAssistant; build:1; iOS 17.5.1) Mobile"), "Home Assistant app on iOS 17.5");
  assert.equal(fb.feedbackBrowser("Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0"), "Firefox 131 on Linux");
  assert.equal(fb.feedbackBrowser("Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36 Edg/130.0"), "Edge 130 on Android 14");
  assert.equal(fb.feedbackBrowser(""), "Unknown browser");
});

// ── the bug link ────────────────────────────────────────────────────────────

test("a bug link fills every text field the template has, with its own option text", () => {
  const { p } = panel();
  fill(p, { ...BUG, area: "Child Card", repro: "sometimes", console: "TypeError", config: "type: custom:x" });
  p._fbLogs = ["2026-10-20 ERROR [custom_components.taskmate] boom"];
  const q = params(p._fbBuild().url);
  assert.equal(q.get("template"), "bug_report.yml");
  assert.equal(q.get("title"), "[Bug]: Points vanish");
  assert.equal(q.get("taskmate_version"), "test");
  assert.equal(q.get("ha_version"), "2026.10.2");
  assert.equal(q.get("ha_install_type"), "Home Assistant Container (Docker)");
  assert.equal(q.get("install_method"), "HACS (default)");
  assert.equal(q.get("lovelace_mode"), "Storage (default — managed via UI)");
  assert.equal(q.get("reproducible"), "Sometimes — happens intermittently");
  assert.equal(q.get("affected_area"), "Child Card");
  assert.equal(q.get("description"), BUG.description);
  assert.equal(q.get("expected"), BUG.expected);
  assert.equal(q.get("steps"), BUG.steps);
  assert.equal(q.get("console_errors"), "TypeError");
  assert.equal(q.get("config"), "type: custom:x");
  assert.equal(q.get("logs"), "2026-10-20 ERROR [custom_components.taskmate] boom");
  const additional = q.get("additional");
  assert.ok(additional.includes("**Sent from the TaskMate panel**"));
  assert.ok(additional.includes("TaskMate installed via: HACS (default)"));
  assert.ok(additional.includes("Family: 2 children, 1 adults · 42 chores · 9 rewards"));
  assert.ok(additional.includes("Chrome 141 on Windows"));
});

test("unticking 'include these details' leaves the environment out", () => {
  const { p } = panel();
  fill(p, BUG);
  p._fbDraft().env.include = false;
  const q = params(p._fbBuild().url);
  for (const k of ["taskmate_version", "ha_version", "ha_install_type", "install_method", "lovelace_mode", "additional"]) {
    assert.equal(q.has(k), false, k);
  }
});

test("a parent's corrections to the detected answers win", () => {
  const { p } = panel();
  fill(p, BUG);
  Object.assign(p._fbDraft().env, { install_type: "haos", install_method: "manual", lovelace_mode: "yaml" });
  const q = params(p._fbBuild().url);
  assert.equal(q.get("ha_install_type"), "Home Assistant OS (HAOS)");
  assert.equal(q.get("install_method"), "Manual (copied files)");
  assert.equal(q.get("lovelace_mode"), "YAML (configuration.yaml)");
});

test("an install method HACS couldn't tell us is left for the parent to pick", () => {
  const { p } = panel(undefined, { ...INFO, install_method: "unknown" });
  fill(p, BUG);
  assert.equal(params(p._fbBuild().url).has("install_method"), false);
  const html = p._fbDetailsCard();
  assert.ok(html.includes(localize("panel.fb_pick_one")));
});

test("the oldest log lines are dropped to keep the link under GitHub's limit", () => {
  const { p, fb } = panel();
  fill(p, BUG);
  p._fbLogs = Array.from({ length: 20 }, (_, i) => `entry-${String(i).padStart(2, "0")} ${"x".repeat(400)}`);
  const built = p._fbBuild();
  assert.ok(built.url.length <= fb.FEEDBACK_URL_MAX);
  assert.ok(built.logsDropped > 0 && built.logsUsed > 0);
  assert.equal(built.logsUsed + built.logsDropped, 20);
  const logs = params(built.url).get("logs");
  assert.ok(logs.includes("entry-19"), "the newest entry survives");
  assert.ok(!logs.includes("entry-00"), "the oldest goes first");
  assert.equal(built.over, 0);
  assert.ok(p._fbLinkHtml().includes(localize("panel.fb_logs_trimmed", { used: built.logsUsed, dropped: built.logsDropped })));
});

test("text too long for any link withholds the link and says by how much", () => {
  const { p, fb } = panel();
  fill(p, { ...BUG, description: "é".repeat(3000) });
  const built = p._fbBuild();
  assert.ok(built.over > 0);
  assert.equal(built.url.length - fb.FEEDBACK_URL_MAX, built.over);
  const html = p._fbLinkHtml();
  assert.ok(html.includes('aria-disabled="true"') && html.includes('href="#"'));
  assert.ok(html.includes(localize("panel.fb_too_long", { count: built.over })));
});

test("unticking the logs leaves them out", () => {
  const { p } = panel();
  fill(p, BUG);
  p._fbLogs = ["boom"];
  p._fbDraft().env.logs = false;
  assert.equal(params(p._fbBuild().url).has("logs"), false);
});

// ── the feature link ────────────────────────────────────────────────────────

test("a feature link uses the feature template and its field ids", () => {
  const { p } = panel();
  const d = p._fbDraft();
  d.type = "feature";
  fill(p, { title: "Swap chores", summary: "S", problem: "P", solution: "So", alternatives: "A", area: "Settings / configuration", priority: "critical" });
  const q = params(p._fbBuild().url);
  assert.equal(q.get("template"), "feature_request.yml");
  assert.equal(q.get("title"), "[Feature]: Swap chores");
  assert.equal(q.get("summary"), "S");
  assert.equal(q.get("problem"), "P");
  assert.equal(q.get("solution"), "So");
  assert.equal(q.get("alternatives"), "A");
  assert.equal(q.get("area"), "Settings / configuration");
  assert.equal(q.get("priority"), "Critical — a blocker for me using TaskMate properly");
  assert.equal(q.get("children_count"), "2");
  assert.ok(q.get("use_case").includes("TaskMate test · Home Assistant 2026.10.2"));
  assert.equal(q.has("description"), false);
});

// ── required fields and the button ──────────────────────────────────────────

test("required fields are listed until filled, and the button stays off", () => {
  const { p } = panel();
  assert.deepEqual([...p._fbMissing()], ["Title", "What happened?", "What did you expect to happen?", "Steps to reproduce"]);
  assert.ok(p._fbLinkHtml().includes('aria-disabled="true"'));
  fill(p, BUG);
  assert.deepEqual([...p._fbMissing()], []);
  const html = p._fbLinkHtml();
  assert.ok(html.includes('aria-disabled="false"'));
  assert.ok(html.includes('href="https://github.com/tempus2016/taskmate/issues/new?template=bug_report.yml'));
  p._fbDraft().type = "feature";
  assert.deepEqual([...p._fbMissing()], ["Title", "Summary", "What problem would it solve?", "How would you like it to work?"]);
});

test("the button stays off until the setup details have loaded", () => {
  const { p } = panel(undefined, null);
  fill(p, BUG);
  assert.ok(p._fbLinkHtml().includes('aria-disabled="true"'));
});

// ── drawing the page ────────────────────────────────────────────────────────

test("the page draws every string translated and escapes what was typed", () => {
  const { p, fb } = panel({});
  p._fbLoading = true;
  fill(p, { ...BUG, title: '<img src=x onerror="alert(1)">', description: "</textarea><script>x</script>" });
  p._fbLogs = ["<b>log</b>"];
  const html = p._renderHelpTab();
  assert.ok(!/panel\.(fb_|tab_help)/.test(html), "no raw keys");
  assert.ok(!html.includes("<img src=x") && html.includes("&lt;img src=x"));
  assert.ok(!html.includes("</textarea><script>") && html.includes("&lt;/textarea&gt;&lt;script&gt;"));
  assert.ok(!html.includes("<b>log</b>") && html.includes("&lt;b&gt;log&lt;/b&gt;"));
  assert.ok(html.includes('data-act="fb-type" data-id="bug"') && html.includes('data-act="fb-type" data-id="feature"'));
  assert.ok(html.includes('data-act="fb-diagnostics"'));
  assert.ok(html.includes('data-fb-region="link"') && html.includes('data-fb-region="dupes"'));
  assert.ok(fb.FEEDBACK_DRAFT_KEY);
});

test("the feature page shows the children count but no logs or diagnostics", () => {
  const { p } = panel();
  p._fbDraft().type = "feature";
  const html = p._renderHelpTab();
  assert.ok(html.includes(localize("panel.fb_feat_heading")));
  assert.ok(!html.includes('data-act="fb-diagnostics"') && !html.includes(localize("panel.fb_logs_heading")));
  assert.ok(html.includes(localize("panel.fb_children_count")));
});

test("an old cached panel is called out before anyone reports a card bug", () => {
  const { p } = panel(undefined, { ...INFO, integration_version: "7.2.0" });
  const html = p._renderHelpTab();
  assert.ok(html.includes(localize("panel.fb_stale", { panel: "test", installed: "7.2.0" })));
  assert.ok(html.includes('data-act="fb-hard-refresh"'));
  const same = panel().p._renderHelpTab();
  assert.ok(!same.includes('data-act="fb-hard-refresh"'));
});

test("health check findings are pointed out on the bug page", () => {
  const { p } = panel(undefined, { ...INFO, health_codes: ["chore_orphan_assignee"] });
  const html = p._renderHelpTab();
  assert.ok(html.includes(localize("panel.fb_health_found", { count: 1 })));
  assert.ok(html.includes('data-act="fb-health"'));
});

test("a failed details load offers a retry instead of a broken page", () => {
  const { p } = panel(undefined, { error: "no_coordinator" });
  const html = p._fbDetailsCard();
  assert.ok(html.includes('data-act="fb-reload"'));
  assert.ok(html.includes("no_coordinator"));
});

test("the draft survives a reload and ignores junk in storage", () => {
  const saved = JSON.stringify({ type: "feature", feature: { title: "Kept" }, env: { include: false } });
  const { p } = panel({ "taskmate-feedback-draft": saved });
  const d = p._fbDraft();
  assert.equal(d.type, "feature");
  assert.equal(d.feature.title, "Kept");
  assert.equal(d.feature.priority, "nice", "missing fields fall back to defaults");
  assert.equal(d.env.include, false);
  assert.equal(d.bug.title, "");
  const junk = panel({ "taskmate-feedback-draft": "{not json" }).p._fbDraft();
  assert.equal(junk.type, "bug");
});

test("similar issues are escaped and only GitHub links are shown", () => {
  const { p } = panel();
  p._fbDupes = { q: "x", items: [{ number: 12, title: "<b>dup</b>", state: "open", url: "https://github.com/tempus2016/taskmate/issues/12" }] };
  const html = p._fbDupesHtml();
  assert.ok(html.includes("#12 &lt;b&gt;dup&lt;/b&gt;"));
  assert.ok(html.includes('href="https://github.com/tempus2016/taskmate/issues/12"'));
  p._fbDupes = { q: "x", items: [], failed: true };
  assert.equal(p._fbDupesHtml(), "");
});

test("the GitHub search keeps only github.com results", async () => {
  const items = [
    { number: 1, title: "ok", state: "open", html_url: "https://github.com/tempus2016/taskmate/issues/1" },
    { number: 2, title: "bad", state: "closed", html_url: "javascript:alert(1)" },
  ];
  const fetch = async (url) => {
    assert.ok(String(url).startsWith("https://api.github.com/search/issues?"));
    assert.ok(decodeURIComponent(String(url)).includes("repo:tempus2016/taskmate is:issue"));
    return { ok: true, json: async () => ({ items }) };
  };
  const { Panel } = load({}, { fetch });
  const p = Object.create(Panel.prototype);
  p._fbPaint = () => {};
  p._fbDraft().bug.title = "points vanish";
  await p._fbSearch("points vanish");
  assert.deepEqual([...p._fbDupes.items.map(i => i.number)], [1]);
  const failing = Object.create(load({}, { fetch: async () => ({ ok: false, status: 403 }) }).Panel.prototype);
  failing._fbPaint = () => {};
  failing._fbDraft().bug.title = "rate limited";
  await failing._fbSearch("rate limited");
  assert.equal(failing._fbDupes.failed, true);
});

test("Copy as Markdown carries the whole report, logs fenced", () => {
  const { p } = panel();
  fill(p, BUG);
  p._fbLogs = ["a", "b"];
  const md = p._fbMarkdown();
  assert.ok(md.startsWith("## [Bug]: Points vanish"));
  assert.ok(md.includes("### What happened?\n\nMalia's points went to 0"));
  assert.ok(md.includes("### Home Assistant Logs\n\n```text\na\nb\n```"));
  assert.ok(md.includes("- TaskMate: test"));
});

test("Help & feedback sits in the System group", () => {
  const { p } = panel();
  const system = p._sidebarGroups().find(g => g.key === "system");
  assert.deepEqual([...system.items.map(i => i.id)], ["notifications", "settings", "help"]);
  assert.equal(system.items[2].icon, "mdi:lifebuoy");
});

test("clearing the form forgets the saved draft", () => {
  const { p, store } = panel();
  fill(p, BUG);
  store["taskmate-feedback-draft"] = "{}";
  p._fbOpened = true;
  p._fbClick({ dataset: { act: "fb-clear" } }, {});
  assert.equal(store["taskmate-feedback-draft"], undefined);
  assert.equal(p._fbDraft().bug.title, "");
  assert.equal(p._fbOpened, false);
});

// ── review follow-ups ───────────────────────────────────────────────────────

test("phone and person ids are masked whole, whoever they're named after", () => {
  const { fb } = load();
  const out = fb.feedbackRedact("notify.mobile_app_johns_iphone failed; person.john_smith, device_tracker.malias_ipad", []);
  assert.equal(out, "notify.mobile_app_[device] failed; person.[device], device_tracker.[device]");
});

test("each part of a full name is hidden on its own too", () => {
  const { p } = panel();
  p._hass = { user: { name: "John Mackinnon" } };
  p._notifState = { recipients: { parents: [{ name: "Louise" }] } };
  const names = [...p._fbNames()];
  for (const n of ["Malia", "Vaiha", "Louise", "John Mackinnon", "John", "Mackinnon"]) assert.ok(names.includes(n), n);
  const { fb } = load();
  const out = fb.feedbackRedact("John here, Mackinnon there, John Mackinnon too", names);
  assert.ok(!/John|Mackinnon/.test(out), out);
});

test("a GitHub answer for an older title is thrown away", async () => {
  let release;
  const fetch = () => new Promise(r => { release = () => r({ ok: true, json: async () => ({ items: [{ number: 9, title: "old", state: "open", html_url: "https://github.com/tempus2016/taskmate/issues/9" }] }) }); });
  const { Panel } = load({}, { fetch });
  const p = Object.create(Panel.prototype);
  p._fbPaint = () => {};
  p._fbDraft().bug.title = "points vanish overnight";
  const pending = p._fbSearch("points vanish overnight");
  p._fbDraft().bug.title = "x";   // cleared while GitHub answers
  p._fbDupes = null;
  release();
  await pending;
  assert.equal(p._fbDupes, null);
});

test("when the integration can't answer, the browser's versions stand in and the report can still go", () => {
  const { p } = panel(undefined, { error: "no_coordinator" });
  p._hass = { config: { version: "2026.10.2" } };
  fill(p, BUG);
  const q = params(p._fbBuild().url);
  assert.equal(q.get("taskmate_version"), "test", "the panel's own build");
  assert.equal(q.get("ha_version"), "2026.10.2");
  assert.ok(q.get("additional").includes("Setup details: unavailable (no_coordinator)"));
  assert.ok(p._fbLinkHtml().includes('aria-disabled="false"'));
});

test("pressing the button while details load says so, not 'too long'", () => {
  const { p } = panel(undefined, null);
  fill(p, BUG);
  let toast = "";
  p._showToast = (_k, text) => { toast = text; };
  p.querySelectorAll = () => [];
  p._fbClick({ dataset: { act: "fb-open" }, getAttribute: () => "true" }, { preventDefault() {} });
  assert.equal(toast, localize("panel.fb_loading"));
});
