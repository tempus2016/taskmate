const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { WWW } = require("./harness.cjs");

// On a 360-393 px phone the top bar holds the menu, the page title, search,
// the child scope chips, "?" and "+". #1146 stopped the chips squeezing the
// English title to "Fa…", but it did so by letting the chip group shrink
// below its own width, which cut the last child's avatar in half on the
// Family, Review, Settings and Manual pages at 360 px (and on every page in
// German, Polish, Nynorsk...). Now the gaps are tighter below 400 px so All
// and two children sit beside every English hub title whole, and when the
// bar is still short the title (repeated as the page heading below) gives
// way with an ellipsis before any avatar is cut. The chips only scroll
// sideways when there are more children than fit.

const SRC = readFileSync(path.join(WWW, "taskmate-panel.js"), "utf8");
const blockAt = (q) => {
  const from = SRC.slice(SRC.indexOf(q));
  return from.slice(0, from.indexOf("\n      }\n") + 9);
};
const phone = blockAt("@media (max-width: 480px) {\n        /* The child chips come first");
const small = blockAt("@media (max-width: 400px) {\n        /* 360 px phones");

test("the page title gives way before the child chips on phones", () => {
  assert.match(phone, /\.tm-topbar \.tm-crumbs \{[^}]*flex: 0 1000 auto/, "the title takes nearly all of the shortfall");
  assert.match(phone, /\.tm-topbar \.tm-crumbs \{[^}]*min-width: 0/, "and may shrink to an ellipsis");
  assert.match(phone, /\.tm-topbar \.tm-crumbs \{[^}]*max-width/, "with a cap so a long crumb can't push the buttons off");
  assert.match(SRC, /\.tm-topbar \.tm-crumbs strong \{[^}]*text-overflow: ellipsis/, "a squeezed title ends in an ellipsis");
});

test("the child chips keep their width and only scroll when there are too many", () => {
  assert.match(phone, /\.tm-scope \{[^}]*flex: 0 1 auto/);
  assert.match(phone, /\.tm-scope \{[^}]*overflow-x: auto/, "more children than fit scroll sideways");
  assert.match(phone, /\.tm-scope \{[^}]*scroll-snap-type: x/, "and the strip settles on a whole chip");
  assert.match(phone, /\.tm-scope-btn \{[^}]*scroll-snap-align/);
  assert.doesNotMatch(phone, /\.tm-topbar \.tm-crumbs \{[^}]*flex: 0 0 auto/, "a rigid title is what clipped the avatars");
});

test("360 px phones get tighter gaps and a chip cap that leaves the title room", () => {
  assert.match(small, /\.tm-topbar \{ gap: 4px; \}/);
  assert.match(small, /\.tm-scope \{[^}]*max-width: calc\(100% - \d+px\)/);
  assert.match(small, /\.tm-scope-all \{ padding: 0 8px; \}/);
});

// With more children than fit, the strip scrolls; the edge with chips out
// of sight fades so the cut chip reads as "scroll for more".
const { loadCard } = require("./harness.cjs");
let dir = "ltr";
const TaskMatePanel = loadCard("taskmate-panel.js", { sandbox: { getComputedStyle: () => ({ direction: dir }) } }).get("taskmate-panel");

function fadeFor({ scrollWidth, clientWidth, scrollLeft, rtl = false }) {
  const sc = { scrollWidth, clientWidth, scrollLeft, dataset: {} };
  const p = Object.create(TaskMatePanel.prototype);
  p.querySelector = () => sc;
  dir = rtl ? "rtl" : "ltr";
  p._syncScopeFade();
  return sc.dataset.fade;
}

test("the chip strip fades the edge that has chips out of sight", () => {
  assert.equal(fadeFor({ scrollWidth: 120, clientWidth: 120, scrollLeft: 0 }), undefined, "everything fits: no fade");
  assert.equal(fadeFor({ scrollWidth: 160, clientWidth: 120, scrollLeft: 0 }), "right");
  assert.equal(fadeFor({ scrollWidth: 160, clientWidth: 120, scrollLeft: 20 }), "left right");
  assert.equal(fadeFor({ scrollWidth: 160, clientWidth: 120, scrollLeft: 40 }), "left");
  assert.equal(fadeFor({ scrollWidth: 160, clientWidth: 120, scrollLeft: 0, rtl: true }), "left", "RTL starts on the right");
});

test("the fade is drawn for each edge and kept in step with scrolling", () => {
  for (const f of ["right", "left", "left right"]) assert.match(phone, new RegExp(`\\.tm-scope\\[data-fade="${f}"\\] \\{[^}]*mask-image`));
  assert.match(SRC, /this\.addEventListener\("scroll", this\._onScopeScroll, true\)/);
  assert.match(SRC, /if \(name === "topbar"\) requestAnimationFrame\(\(\) => \{ if \(this\.isConnected\) this\._syncScopeFade\(\); \}\)/);
});
