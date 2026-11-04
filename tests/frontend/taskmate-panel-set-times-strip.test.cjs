const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { loadCard, WWW } = require("./harness.cjs");

const { get } = loadCard("taskmate-panel.js");
const TaskMatePanel = get("taskmate-panel");
const SRC = readFileSync(path.join(WWW, "taskmate-panel.js"), "utf8");

// The chore editor's "At set times" strip drew each time's name inside its
// window. A window is drawn to scale, so a two-hour "Afternoon" was 44 px
// wide in the 1400 px side panel and showed as "After…" ("Eve…", "Ni…";
// worse still for "Nachmittag" or "Popołudnie"). Each time now has its own
// lane and its name runs on past the window instead of being cut to it.

function strip(times) {
  const p = Object.create(TaskMatePanel.prototype);
  p._esc = (s) => String(s);
  return p._choreTimesStrip(times);
}

const lanes = (html) => [...html.matchAll(/<div class="tm-st-lane"[\s\S]*?<\/span>\s*<\/div>/g)].map(m => m[0]);

test("each set time gets its own lane, with the name outside the window", () => {
  const html = strip([
    { name: "Morning", start: "06:30", end: "09:00" },
    { name: "Afternoon", start: "13:00", end: "15:00" },
    { name: "Night", start: "20:00", end: "21:00" },
  ]);
  const ls = lanes(html);
  assert.equal(ls.length, 3);
  for (const l of ls) {
    assert.match(l, /<div class="tm-st-blk" style="[^"]*"><\/div>/, "the window itself carries no text");
    assert.match(l, /<span class="tm-st-lbl"/);
  }
  assert.match(ls[1], />Afternoon<\/span>/);
});

test("a name starts at an early window and ends at a late one, so it stays in the strip", () => {
  const [early, late] = lanes(strip([
    { name: "Morning", start: "06:00", end: "09:00" },
    { name: "Night", start: "20:00", end: "21:00" },
  ]));
  assert.match(early, /class="tm-st-lbl" style="inset-inline-start:25\.00%;max-width:75\.00%"/);
  assert.match(late, /class="tm-st-lbl" style="inset-inline-end:12\.50%;max-width:87\.50%"/);
});

test("broken or reversed times are left off the strip", () => {
  assert.equal(lanes(strip([{ name: "x", start: "10:00", end: "09:00" }, { name: "y", start: "", end: "" }])).length, 0);
});

test("the window no longer clips its name", () => {
  const blk = SRC.match(/\.tm-st-blk \{[^}]*\}/)[0];
  assert.doesNotMatch(blk, /text-overflow|white-space/, "the window holds no text to clip");
  assert.match(SRC, /\.tm-st-lane \{[^}]*position: relative/);
  assert.match(SRC, /\.tm-st-lbl \{[^}]*white-space: nowrap/);
});
