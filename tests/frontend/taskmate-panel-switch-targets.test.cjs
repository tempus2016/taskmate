const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");

const { WWW } = require("./harness.cjs");

// The panel's own on/off switches (setup wizard, badge catalogue,
// notification routes) drew a 36x20 or 38x22 control, too short for a finger.
// Each is now a 44x36 or 46x36 control whose track is drawn by ::before, with
// negative margins so the rows keep their spacing.

const SRC = readFileSync(path.join(WWW, "taskmate-panel.js"), "utf8");

function rule(selector) {
  const esc = selector.replace(/[.[\]():]/g, "\\$&");
  const m = SRC.match(new RegExp(`\\n\\s*${esc}\\s*\\{([^}]*)\\}`));
  assert.ok(m, `no ${selector} rule`);
  return m[1];
}
const px = (body, prop) => {
  const m = body.match(new RegExp(`(?:^|[;\\s])${prop}:\\s*(-?\\d+)px`));
  return m ? Number(m[1]) : null;
};

for (const [sw, on] of [
  [".tm-wz-sw", ".tm-wz-sw.tm-wz-on"],
  [".tm-badge-toggle", ".tm-badge-toggle-on"],
  [".tm-notif-switch", ".tm-notif-switch:checked"],
]) {
  test(`${sw} is at least 36px tall and wide, and keeps its small track`, () => {
    const box = rule(sw);
    assert.ok(px(box, "height") >= 36, `${sw} height ${px(box, "height")}`);
    assert.ok(px(box, "width") >= 44, `${sw} width ${px(box, "width")}`);
    assert.match(box, /background:\s*none/, `${sw} must not paint the whole hit area`);
    assert.match(box, /margin:\s*-\d+px -\d+px/, `${sw} needs negative margins to keep the row spacing`);
    const track = rule(`${sw}::before`);
    assert.ok(px(track, "height") <= 22 && px(track, "width") <= 38, `${sw} track grew`);
    assert.match(rule(`${on}::before`), /background:\s*var\(--tm-accent\)/, `${sw} on-state no longer colours the track`);
  });
}

test("no switch relies on a phone-only invisible margin any more", () => {
  assert.doesNotMatch(SRC, /\.tm-(wz-sw|badge-toggle)::before \{ content: ""; position: absolute; inset: -8px -4px; \}/);
});
