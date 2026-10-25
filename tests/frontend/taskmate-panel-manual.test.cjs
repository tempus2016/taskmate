// Admin panel → Manual: wiki/ bundled into the integration, read in the panel.
//
// Pins the Manual's place in the nav, that every admin page has a "?" that
// opens a manual page, the page view (contents, crumbs, previous/next, "On
// this page"), search, the side panel the "?" opens, and what shows when the
// bundle is missing.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, localize } = require("./harness.cjs");

const fetched = [];
let reply = null;
const loaded = loadCard("taskmate-panel.js", {
  sandbox: {
    fetch: (url) => { fetched.push(url); return reply(); },
    requestAnimationFrame: (fn) => fn(),
    navigator: { userAgent: "Mozilla/5.0 (X11; Linux x86_64)", platform: "Linux" },
  },
  transform: (src) => `${src}\nwindow.__man = { MANUAL_HELP, MANUAL_URL, MANUAL_SITE };`,
});
const Panel = loaded.get("taskmate-panel");
// Objects made inside the sandbox have its prototypes; compare them as data.
const plain = (v) => JSON.parse(JSON.stringify(v));
const { MANUAL_HELP, MANUAL_URL, MANUAL_SITE } = loaded.window.__man;

const BUNDLE = {
  version: "7.4.0",
  site: MANUAL_SITE,
  nav: [
    { title: "Home", page: "index" },
    { title: "Getting Started", children: [
      { title: "Installation", page: "Installation" },
      { title: "Admin Panel", page: "Admin-Panel" },
    ]},
    { title: "Chores", children: [
      { title: "Chores", page: "Chores" },
      { title: "Vacation Mode", page: "Vacation-Mode" },
    ]},
  ],
  pages: {
    index: { title: "TaskMate", html: '<h1 id="tmdoc-taskmate">TaskMate</h1><p>Welcome.</p>', toc: [] },
    Installation: { title: "Installation", html: '<h1 id="tmdoc-installation">Installation</h1><p>Use HACS.</p>', toc: [] },
    "Admin-Panel": { title: "Admin Panel", html: '<h1 id="tmdoc-admin-panel">Admin Panel</h1><h2 id="tmdoc-today-v600">Today</h2><p>Home page.</p>', toc: [{ id: "tmdoc-today-v600", text: "Today" }] },
    Chores: {
      title: "Chores",
      html: '<h1 id="tmdoc-chores">Chores</h1><h2 id="tmdoc-chore-fields">Chore Fields</h2><p>Points and days.</p><h2 id="tmdoc-vacation--pause-mode">Vacation / Pause Mode</h2><p>Pause chores while you are away.</p>',
      toc: [{ id: "tmdoc-chore-fields", text: "Chore Fields" }, { id: "tmdoc-vacation--pause-mode", text: "Vacation / Pause Mode" }],
    },
    "Vacation-Mode": { title: "Vacation Mode", html: '<h1 id="tmdoc-vacation-mode">Vacation Mode</h1><p>Mark date ranges as time off &amp; rest.</p>', toc: [] },
  },
};

function panel(tab = "chores") {
  const p = Object.create(Panel.prototype);
  p._t = (key, params) => localize(key, params);
  p._render = () => { p.renders = (p.renders || 0) + 1; };
  p._state = { children: [], chores: [], settings: {} };
  p._activeTab = tab;
  p._dialog = null;
  p._dialogInitialHash = null;
  p._hubTabs = {};
  p._man = { doc: "index", anchor: "", q: "", open: new Set(), contents: false };
  p._manual = null;
  p._manualState = "";
  p._manualText = null;
  p._zoneCache = {};
  p.querySelector = () => null;
  return p;
}

function withBundle(p) {
  p._manual = BUNDLE;
  return p;
}

// ── nav ─────────────────────────────────────────────────────────────────────

test("the Manual sits at the foot of the rail, in place of the old website link", () => {
  const p = panel();
  const html = p._sidebar();
  const foot = html.slice(html.indexOf("tm-rail-foot"));
  assert.match(foot, /data-act="hub" data-hub="manual"/);
  assert.match(foot, /data-hub="settings"/);
  assert.ok(foot.indexOf('data-hub="manual"') < foot.indexOf('data-hub="settings"'), "Manual comes before Settings");
  assert.doesNotMatch(html, /tm-brand-wiki/);
  assert.doesNotMatch(html.slice(0, html.indexOf("tm-rail-foot")), /data-hub="manual"/, "not among the main sections");
});

test("the Manual is one page with no tabs, and is listed in the phone's More sheet", () => {
  const p = panel("manual");
  assert.equal(p._hubOf("manual").key, "manual");
  assert.equal(p._subTabs(), "");
  p._mobileNavOpen = true;
  assert.match(p._mobileTabs(), /data-act="tab" data-tab="manual"/);
});

test("every admin page has a \"?\" that opens a manual page", () => {
  const p = panel();
  const tabs = p._sidebarGroups().flatMap((g) => g.items.map((it) => it.id)).filter((id) => id !== "manual");
  for (const tab of tabs) assert.ok(MANUAL_HELP[tab], `no manual page for the ${tab} page`);
  assert.ok(MANUAL_HELP.setup, "the setup wizard has one too");
});

test("the top bar has a \"?\" on admin pages and a website link on the Manual", () => {
  const chores = panel("chores");
  assert.match(chores._topbar(), /data-act="man-help"/);
  const manual = withBundle(panel("manual"));
  manual._man.doc = "Vacation-Mode";
  const bar = manual._topbar();
  assert.doesNotMatch(bar, /data-act="man-help"/);
  assert.match(bar, new RegExp(`href="${MANUAL_SITE}Vacation-Mode/" target="_blank" rel="noopener noreferrer"`));
});

test("website links point at the same page on GitHub Pages", () => {
  const p = panel();
  assert.equal(p._manualWebUrl("index"), MANUAL_SITE);
  assert.equal(p._manualWebUrl("Chores", "chore-fields"), `${MANUAL_SITE}Chores/#chore-fields`);
  assert.equal(p._manualWebUrl("Pool-Mode-(Savings Jars)"), `${MANUAL_SITE}Pool-Mode-(Savings%20Jars)/`);
});

// ── loading ─────────────────────────────────────────────────────────────────

test("the bundle loads once, versioned, the first time the Manual opens", async () => {
  fetched.length = 0;
  reply = () => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(BUNDLE) });
  const p = panel("manual");
  const first = p._renderBody();
  assert.match(first, new RegExp(localize("panel.manual_loading")));
  p._renderBody();
  assert.equal(fetched.length, 1, "a second render while loading does not fetch again");
  assert.ok(fetched[0].startsWith(`${MANUAL_URL}?v=`));
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(p._manual, BUNDLE);
  assert.match(p._renderBody(), /Welcome\./);
});

test("the Manual opens even when TaskMate's own state failed to load", () => {
  const p = withBundle(panel("manual"));
  p._state = null;
  p._error = "boom";
  assert.match(p._renderBody(), /Welcome\./);
});

test("an install without the bundle says so and links to the website", async () => {
  reply = () => Promise.resolve({ ok: false, status: 404, json: () => Promise.reject(new Error("no")) });
  const p = panel("manual");
  p._renderBody();
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(p._manualState, "missing");
  const html = p._renderBody();
  assert.match(html, new RegExp(localize("panel.manual_missing").replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  assert.match(html, new RegExp(`href="${MANUAL_SITE}"`));
  assert.doesNotMatch(html, /man-retry/, "nothing to retry");
});

test("a failed load offers a retry", async () => {
  reply = () => Promise.reject(new Error("offline"));
  const p = panel("manual");
  p._renderBody();
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(p._manualState, "failed");
  assert.match(p._renderBody(), /data-act="man-retry"/);
});

// ── the page ────────────────────────────────────────────────────────────────

test("a page shows its section open in the contents, a crumb and previous/next", () => {
  const p = withBundle(panel("manual"));
  p._manualGo("Chores");
  const html = p._renderBody();
  assert.match(html, /<a class="tm-man-item  tm-man-item-on" href="[^"]+Chores\/" data-act="man-go" data-doc="Chores" aria-current="page">Chores<\/a>/);
  assert.match(html, /data-sec="Chores" aria-expanded="true"/);
  assert.match(html, /data-sec="Getting Started" aria-expanded="false"/);
  assert.match(html, /<span>›<\/span><span>Chores<\/span>/);
  assert.match(html, /tm-man-pn-prev[^>]*data-doc="Admin-Panel"/);
  assert.match(html, /tm-man-pn-next[^>]*data-doc="Vacation-Mode"/);
  assert.match(html, /<h4>On this page<\/h4>[\s\S]*data-doc="Chores" data-anchor="chore-fields"/);
  assert.match(html, /Pause chores while you are away\./);
  assert.match(html, /Docs for v7\.4\.0/);
});

test("an unknown page falls back to the home page", () => {
  const p = withBundle(panel("manual"));
  p._man.doc = "No-Such-Page";
  assert.match(p._renderBody(), /Welcome\./);
});

test("a manual link opens the page in the panel; Ctrl-click leaves it to the browser", () => {
  const p = withBundle(panel("chores"));
  let prevented = false;
  const link = { dataset: { act: "man-go", doc: "Chores", anchor: "chore-fields" }, closest: () => null };
  p._manualClick(link, { preventDefault: () => { prevented = true; } });
  assert.ok(prevented);
  assert.equal(p._activeTab, "manual");
  assert.deepEqual([p._man.doc, p._man.anchor], ["Chores", "chore-fields"]);

  prevented = false;
  p._manualClick({ ...link, dataset: { ...link.dataset, doc: "Installation" } }, { ctrlKey: true, preventDefault: () => { prevented = true; } });
  assert.ok(!prevented);
  assert.equal(p._man.doc, "Chores", "unchanged: the browser opens the website copy");
});

test("sections fold and unfold", () => {
  const p = withBundle(panel("manual"));
  p._manualClick({ dataset: { act: "man-sec", sec: "Chores" } }, {});
  assert.ok(p._man.open.has("Chores"));
  p._manualClick({ dataset: { act: "man-sec", sec: "Chores" } }, {});
  assert.ok(!p._man.open.has("Chores"));
});

// ── search ──────────────────────────────────────────────────────────────────

test("search needs every word, ranks titles first and jumps to the matching heading", () => {
  const p = withBundle(panel("manual"));
  const hits = p._manualSearch("vacation");
  assert.deepEqual(plain(hits.map((h) => h.doc)), ["Vacation-Mode", "Chores"]);
  assert.equal(hits[1].anchor, "vacation--pause-mode");
  assert.equal(p._manualSearch("vacation hacs").length, 0);
  assert.deepEqual(plain(p._manualSearch("time off rest").map((h) => h.doc)), ["Vacation-Mode"]);
  assert.equal(p._manualSearch("TaskMate").length, 0, "a page's own title heading is not searched as text");
});

test("search results are escaped and highlighted", () => {
  const p = withBundle(panel("manual"));
  const html = p._manualResults("off & rest");
  assert.match(html, /Pages found: 1/);
  assert.match(html, /<mark>off<\/mark> <mark>&amp;<\/mark> <mark>rest<\/mark>/);
  assert.match(p._manualResults("<img src=x>"), new RegExp(localize("panel.manual_no_results")));
});

test("typing in the search box updates the list without redrawing the page", () => {
  const p = withBundle(panel("manual"));
  const list = { innerHTML: "", scrollTop: 5 };
  p.querySelector = (sel) => (sel === ".tm-man .tm-man-list" ? list : null);
  p._manualSearchInput({ value: "vacation" });
  assert.equal(p._man.q, "vacation");
  assert.match(list.innerHTML, /data-doc="Vacation-Mode"/);
  assert.equal(p.renders || 0, 0, "no full render, so the caret stays put");
  assert.equal(p._zoneCache.body, p._renderBody(), "the next state push finds nothing to redraw");
});

test("Enter opens the first result; Escape clears the box", () => {
  const p = withBundle(panel("manual"));
  p._man.q = "vacation";
  p.querySelector = (sel) => (sel === ".tm-man .tm-man-hit" ? { dataset: { doc: "Vacation-Mode", anchor: "" } } : null);
  assert.ok(p._manualSearchKey({ key: "Enter", preventDefault() {} }));
  assert.equal(p._man.doc, "Vacation-Mode");
  const box = { value: "vacation" };
  p.querySelector = () => null;
  assert.ok(p._manualSearchKey({ key: "Escape", target: box, preventDefault() {}, stopPropagation() {} }));
  assert.equal(box.value, "");
  assert.equal(p._man.q, "");
  assert.ok(!p._manualSearchKey({ key: "Escape", target: box, preventDefault() {}, stopPropagation() {} }), "an empty box lets Escape through");
});

// ── "?" side panel ──────────────────────────────────────────────────────────

test("\"?\" opens the page's manual page in the side panel, and toggles it shut", () => {
  const p = withBundle(panel("chores"));
  p._manualClick({ dataset: { act: "man-help" } }, {});
  assert.deepEqual(plain(p._dialog), { kind: "manual-help", data: { doc: "Chores", anchor: "" } });
  const html = p._renderDialog();
  assert.match(html, /tm-scrim tm-scrim-drawer/);
  assert.match(html, /<h2>Chores<\/h2>/);
  assert.match(html, /<article class="tm-doc tm-man-drawer-doc">/);
  assert.match(html, /data-act="man-full"/);
  assert.match(p._topbar(), /tm-man-help-on/);
  p._manualClick({ dataset: { act: "man-help" } }, {});
  assert.equal(p._dialog, null);
});

test("\"?\" on Today opens the Today heading of the Admin Panel page", () => {
  const p = withBundle(panel("today"));
  p._manualClick({ dataset: { act: "man-help" } }, {});
  assert.deepEqual(plain(p._dialog.data), { doc: "Admin-Panel", anchor: "today-v600" });
});

test("links inside the side panel stay in the side panel, without an unsaved-changes prompt", () => {
  const p = withBundle(panel("chores"));
  p._manualClick({ dataset: { act: "man-help" } }, {});
  const inDrawer = { dataset: { act: "man-go", doc: "Vacation-Mode", anchor: "" }, closest: (sel) => (sel === ".tm-man-drawer-doc" ? {} : null) };
  p._manualClick(inDrawer, { preventDefault() {} });
  assert.equal(p._activeTab, "chores");
  assert.equal(p._dialog.data.doc, "Vacation-Mode");
  assert.ok(p._mayLeaveDialog(), "reading is not an unsaved change");
});

test("Open in Manual swaps the side panel for the full Manual page", () => {
  const p = withBundle(panel("chores"));
  p._manualClick({ dataset: { act: "man-help" } }, {});
  p._manualClick({ dataset: { act: "man-full" } }, {});
  assert.equal(p._dialog, null);
  assert.equal(p._activeTab, "manual");
  assert.equal(p._man.doc, "Chores");
  assert.ok(p._man.open.has("Chores"));
});

test("the side panel loads the bundle if the Manual was never opened", () => {
  fetched.length = 0;
  reply = () => new Promise(() => {});
  const p = panel("rewards");
  p._manualClick({ dataset: { act: "man-help" } }, {});
  assert.equal(fetched.length, 1);
  assert.match(p._renderDialog(), new RegExp(localize("panel.manual_loading")));
});
