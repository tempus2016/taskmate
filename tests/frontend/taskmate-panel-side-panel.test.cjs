const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

// The panel reads `confirm` from its sandbox; each test sets the answer.
let answer = true;
const asked = [];
const { get } = loadCard("taskmate-panel.js", { sandbox: { confirm: (msg) => { asked.push(msg); return answer; } } });
const TaskMatePanel = get("taskmate-panel");

// Editors open as a side panel that leaves the page usable beside it, so a
// parent can move from one item to the next. Changes are never dropped
// without asking.

function panel(dialog) {
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key) => key;
  p._esc = (s) => String(s);
  p._render = () => { p.renders = (p.renders || 0) + 1; };
  p._activeTab = "chores";
  p._state = { children: [], chores: [] };
  p._dialog = dialog || null;
  p._dialogInitialHash = dialog ? p._hashDialog() : null;
  return p;
}

function withConfirm(reply, fn) {
  answer = reply;
  asked.length = 0;
  fn();
  return [...asked];
}

test("editing a thing opens a side panel that does not block the page", () => {
  for (const kind of ["child", "reward", "quest", "bounty", "penalty", "badge"]) {
    const p = panel({ kind, mode: "edit", data: { id: "x" } });
    const html = p._dialogShell("Edit", "body", "foot");
    assert.match(html, /tm-scrim tm-scrim-drawer/, kind);
    assert.match(html, /tm-dialog tm-drawer/, kind);
    assert.match(html, /aria-modal="false"/, kind);
  }
});

test("confirmations stay centred and modal", () => {
  for (const kind of ["reject", "wizard-confirm", "gift", "apply-bonus"]) {
    const p = panel({ kind, data: {} });
    const html = p._dialogShell("Sure?", "body", "foot");
    assert.doesNotMatch(html, /tm-drawer/, kind);
    assert.match(html, /aria-modal="true"/, kind);
  }
});

test("opening another item from the page replaces an unchanged editor without asking", () => {
  const p = panel({ kind: "chore", mode: "edit", data: { id: "c1", name: "Make bed" } });
  const asked = withConfirm(false, () => p._openDialog({ kind: "chore", mode: "edit", data: { id: "c2", name: "Dishes" } }));
  assert.deepEqual(asked, []);
  assert.equal(p._dialog.data.id, "c2");
});

test("opening another item with unsaved changes asks first, and keeps them if the parent says no", () => {
  const p = panel({ kind: "chore", mode: "edit", data: { id: "c1", name: "Make bed" } });
  p._dialog.data.name = "Make the bed";
  const asked = withConfirm(false, () => p._openDialog({ kind: "chore", mode: "edit", data: { id: "c2", name: "Dishes" } }));
  assert.deepEqual(asked, ["panel.confirm_unsaved"]);
  assert.equal(p._dialog.data.id, "c1");
  assert.equal(p._dialog.data.name, "Make the bed");
});

test("going to another page closes the editor, after asking if it has changes", () => {
  const p = panel({ kind: "reward", mode: "edit", data: { id: "r1", name: "TV" } });
  p._dialog.data.name = "TV time";
  const t = { dataset: { act: "tab", tab: "today" }, closest: () => t };
  const e = { target: t };
  withConfirm(false, () => p._onClick(e));
  assert.equal(p._activeTab, "chores", "cancelled: stays put");
  assert.equal(p._dialog.data.name, "TV time");
  withConfirm(true, () => p._onClick(e));
  assert.equal(p._activeTab, "today");
  assert.equal(p._dialog, null);
});
