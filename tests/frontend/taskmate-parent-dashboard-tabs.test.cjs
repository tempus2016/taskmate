// Parent Dashboard tab bars on narrow cards (v7.7.1 phone sweep).
//
// At 360px in graphite the Points tab was cut off at the card's edge: the
// underlined (graphite / clean pro) and segmented (console) bars keep one row
// and had nowhere to put a fourth tab. They now scroll sideways and fade the
// edge that has more tabs past it, for every locale's labels.

const assert = require("node:assert/strict");
const { test } = require("node:test");
const { readFileSync, readdirSync } = require("node:fs");
const path = require("node:path");

const { loadCard, render } = require("./harness.cjs");

const Dash = loadCard("taskmate-parent-dashboard-card.js").get("taskmate-parent-dashboard-card");
const css = () => render(Dash.styles).markup;

test("the one-row tab bars scroll sideways and their tabs never shrink or wrap", () => {
  const s = css();
  assert.match(s, /\.pd-tabs-cp, \.pd-tabs-cn \{[^}]*overflow-x: auto/);
  assert.match(s, /\.pd-tab-cp \{[^}]*flex: none; white-space: nowrap/);
  assert.match(s, /\.pd-tab-cn \{[^}]*flex: 1 0 auto; white-space: nowrap/);
  // The rule under the tabs is an inset shadow so the scroller can't clip it.
  assert.match(s, /\.pd-tabs-cp \{[^}]*box-shadow: inset 0 -1px 0/);
  for (const side of ["fade-r", "fade-l"]) {
    assert.match(s, new RegExp(`\\.pd-tabs-cp\\.${side}, \\.pd-tabs-cn\\.${side} \\{[^}]*mask-image: linear-gradient`));
  }
  // Playroom's pills keep wrapping onto a second row.
  assert.match(s, /\.pd-tabs \{[^}]*flex-wrap: wrap/);
});

// A stand-in bar: `tabs` are [left, right] pairs relative to a 0..width box.
function fakeBar(width, tabs, activeIndex = -1) {
  const cls = new Set();
  const bar = {
    scrollLeft: 0,
    clientWidth: width,
    scrollWidth: Math.max(width, ...tabs.map(([, r]) => r)),
    classList: { toggle: (c, on) => (on ? cls.add(c) : cls.delete(c)), has: c => cls.has(c) },
    getBoundingClientRect: () => ({ left: 0, right: width }),
    children: tabs.map(([l, r], i) => ({
      active: i === activeIndex,
      getBoundingClientRect: () => ({ left: l - bar.scrollLeft, right: r - bar.scrollLeft }),
    })),
    querySelector: () => bar.children.find(t => t.active) || null,
  };
  return { bar, cls };
}

function cardWith(bar) {
  const card = new Dash();
  Object.defineProperty(card, "shadowRoot", { value: { querySelector: () => bar } });
  return card;
}

test("the fade marks only the edge with tabs past it", () => {
  const fits = fakeBar(344, [[0, 80], [80, 170], [170, 240], [240, 300]]);
  cardWith(fits.bar)._syncTabFade();
  assert.deepEqual([...fits.cls], []);

  const cut = fakeBar(344, [[0, 90], [90, 200], [200, 288], [288, 354]]);
  const card = cardWith(cut.bar);
  card._syncTabFade();
  assert.deepEqual([...cut.cls], ["fade-r"]);

  cut.bar.scrollLeft = 10; // scrolled to the end
  card._syncTabFade();
  assert.deepEqual([...cut.cls], ["fade-l"]);

  cut.bar.scrollLeft = 5; // part way
  card._syncTabFade();
  assert.deepEqual([...cut.cls].sort(), ["fade-l", "fade-r"]);
});

test("switching to a tab past the edge scrolls it fully into view", () => {
  const { bar, cls } = fakeBar(344, [[0, 90], [90, 200], [200, 288], [288, 354]], 3);
  cardWith(bar)._syncTabFade(true);
  assert.ok(bar.scrollLeft >= 10, `scrolled ${bar.scrollLeft}`);
  assert.ok(!cls.has("fade-r"));
});

test("with no designed one-row bar on the card it does nothing", () => {
  const card = new Dash();
  Object.defineProperty(card, "shadowRoot", { value: { querySelector: () => null } });
  assert.doesNotThrow(() => card._syncTabFade(true));
});

test("every locale has the tab labels the bar is sized for", () => {
  const dir = path.join(__dirname, "../../custom_components/taskmate/www/locales");
  for (const f of readdirSync(dir).filter(n => n.endsWith(".json"))) {
    const m = JSON.parse(readFileSync(path.join(dir, f), "utf8"));
    for (const k of ["overview", "approvals", "claims", "points"]) {
      assert.ok(m[`dashboard.tab_${k}`], `${f} dashboard.tab_${k}`);
    }
  }
});

test("in a right-to-left language the fade sits on the left at the start", () => {
  const Rtl = loadCard("taskmate-parent-dashboard-card.js", {
    sandbox: { getComputedStyle: () => ({ direction: "rtl" }) },
  }).get("taskmate-parent-dashboard-card");
  const { bar, cls } = fakeBar(344, [[0, 90], [90, 200], [200, 288], [288, 354]]);
  const card = new Rtl();
  Object.defineProperty(card, "shadowRoot", { value: { querySelector: () => bar } });
  card._syncTabFade();
  assert.deepEqual([...cls], ["fade-l"]);
  bar.scrollLeft = -10; // scrolled to the far (left) end
  card._syncTabFade();
  assert.deepEqual([...cls], ["fade-r"]);
});

// Final v7.7.1 sweep: at 360px in German the classic row (and English pills
// in playroom) wrapped with one tab alone on the second row. A wrapping bar
// is laid out as an even two-row grid instead.
function wrapBar(tops) {
  const cls = new Set(); const style = {};
  const bar = {
    classList: { add: c => cls.add(c), remove: c => cls.delete(c), contains: c => cls.has(c) },
    style: { setProperty: (k, v) => { style[k] = v; } },
    // Once the grid is on, every tab sits in one of two rows.
    children: tops.map((top, i) => ({ getBoundingClientRect: () => ({ top: cls.has("pd-even") ? (i < tops.length / 2 ? 0 : 40) : top }) })),
  };
  return { bar, cls, style };
}

test("a wrapping classic or pill tab row becomes an even grid, never an orphan", () => {
  const wraps = wrapBar([0, 0, 0, 40]);
  cardWith(wraps.bar)._balanceTabs();
  assert.ok(wraps.cls.has("pd-even"));
  assert.equal(wraps.style["--pd-cols"], "2");

  const five = wrapBar([0, 0, 0, 0, 40]);
  cardWith(five.bar)._balanceTabs();
  assert.equal(five.style["--pd-cols"], "3", "five tabs: three over two");

  const fits = wrapBar([0, 0, 0, 0]);
  fits.cls.add("pd-even"); // a wider card again: back to one row
  cardWith(fits.bar)._balanceTabs();
  assert.ok(!fits.cls.has("pd-even"));
});

test("the even grid is two rows of equal cells whose labels may wrap", () => {
  const s = css();
  assert.match(s, /\.tab-nav\.pd-even, \.pd-tabs\.pd-even \{[^}]*display: grid; grid-template-columns: repeat\(var\(--pd-cols, 2\), minmax\(0, 1fr\)\)/);
  assert.match(s, /\.tab-nav\.pd-even \.tab-btn, \.pd-tabs\.pd-even \.pd-tab \{[^}]*white-space: normal/);
});

// Last recheck: at 320px in German (accessible) "Genehmigungen 1" filled its
// grid cell edge to edge and the badge overlapped the border. In the even grid
// the badge may drop under the label, padding tightens, and a long word
// hyphenates in the card's language rather than overflow.
test("a long single-word label still fits its even-grid cell", () => {
  const s = css();
  const at = s.indexOf(".tab-nav.pd-even .tab-btn, .pd-tabs.pd-even .pd-tab {");
  const block = s.slice(at, s.indexOf("}", at));
  assert.match(block, /flex-wrap: wrap/);
  assert.match(block, /padding-inline: 8px/);
  assert.match(block, /hyphens: auto; overflow-wrap: anywhere/);
  assert.match(s, /@media \(max-width: 400px\) \{\s*\.pd-tabs\.pd-even \.pd-tab \{ font-size: 12px; \}/);

  const card = new Dash();
  card.setConfig({ entity: "sensor.taskmate_overview", card_design: "playroom" });
  card.hass = { language: "de", states: {} };
  assert.match(render(card._dTabsPlayroom([{ id: "overview", label: "Überblick" }])).markup, /<div class="pd-tabs" lang="de">/);
});
