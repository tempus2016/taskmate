"use strict";
// Per-child stage (#1262) in the child editor: stage tiles with their
// suggestions, a Can do / Practising / Later control per chore, and the
// confirm that changes the stage straight away (applying chore changes only
// when there are any).
const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, localize } = require("./harness.cjs");

const { get } = loadCard("taskmate-panel.js", { sandbox: { confirm: () => true } });
const TaskMatePanel = get("taskmate-panel");

function panel({ scope = "cards", mode = "edit", data = {} } = {}) {
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params) => localize(key, params);
  p._esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  p._fmtNum = (n) => String(n);
  p.renders = 0;
  p._render = () => { p.renders += 1; };
  p.querySelector = () => null;
  p._syncIconPickers = () => {};
  p._state = {
    settings: { stage_scope: scope },
    children: [{ id: "k1", name: "Isla" }],
    chores: [
      { id: "a", name: "Brush teeth", assigned_to: ["k1"] },
      { id: "b", name: "Feed the cat", assigned_to: [] },
      { id: "c", name: "Mow the lawn", assigned_to: ["k2"] },
    ],
  };
  p._dialog = { kind: "child", mode, data: { id: "k1", name: "Isla", age_group: "6_8", chore_stage: { a: "practising" }, ...data } };
  p._dialogInitialHash = p._hashDialog();
  return p;
}

test("stage tiles name every stage and the picked one's suggestions", () => {
  const html = panel()._childStageField(panel()._dialog.data);
  for (const name of ["Joining in", "Doing my part", "Contributing", "Taking ownership"]) assert.ok(html.includes(name), name);
  assert.ok(html.includes("Doing my part suggests:"));
  assert.ok(html.includes("Small tasks alone, taking turns"));
});

test("chore suggestions are struck through while stage_scope is cards", () => {
  const p = panel({ data: { age_group: "3_5" } });
  assert.match(p._childStageField(p._dialog.data), /tm-stage-off">No deadlines or deductions on chores only Isla does/);
  const all = panel({ scope: "all", data: { age_group: "3_5" } });
  assert.doesNotMatch(all._childStageField(all._dialog.data), /tm-stage-off/);
});

test("the chore list covers the child's chores with three states", () => {
  const p = panel();
  const html = p._childChoreStageField(p._dialog.data);
  assert.ok(html.includes("Chores for Isla"));
  assert.ok(html.includes("Brush teeth") && html.includes("Feed the cat"));
  assert.ok(!html.includes("Mow the lawn"), "another child's chore is not listed");
  assert.ok(html.includes("Practising: 1. Two or three at a time works best."));
  assert.equal((html.match(/data-act="child-chore-stage"/g) || []).length, 6);
});

test("moving up asks with a gaining title; the panel only applies when there is something to apply", async () => {
  const p = panel({ scope: "all", data: { age_group: "3_5" } });
  const calls = [];
  p._callWS = async (msg) => {
    calls.push(msg);
    return { ok: true, res: { chores: [], skipped_shared: [{ chore_id: "b", name: "Feed the cat" }], chore_items: [] } };
  };
  await p._pickChildStage("9_12");
  assert.equal(calls[0].preview, true);
  const html = p._renderStagePop();
  assert.ok(html.includes("Isla can try more now"));
  assert.ok(html.includes("Change stage"));
  assert.ok(!html.includes("Change and apply"), "no apply button when nothing would change");
});

test("moving down uses the neutral title and Change and apply shows with chore changes", async () => {
  const p = panel({ scope: "all" });
  p._callWS = async () => ({ ok: true, res: { chores: [{ chore_id: "a", name: "Brush teeth", changes: {} }], skipped_shared: [], chore_items: ["no_deadlines"] } });
  await p._pickChildStage("3_5");
  const html = p._renderStagePop();
  assert.ok(html.includes("Change Isla's stage"));
  assert.ok(html.includes("Change stage only") && html.includes("Change and apply"));
  assert.ok(html.includes("Brush teeth"));
});

test("confirming saves the stage at once and keeps the editor clean", async () => {
  const p = panel();
  const sent = [];
  p._callWS = async (msg) => { sent.push(msg); return { ok: true, res: { chores: [], skipped_shared: [], chore_items: [] } }; };
  p._fetchState = async () => {};
  p._showToast = () => {};
  await p._pickChildStage("9_12");
  await p._confirmChildStage(false);
  assert.equal(sent[1].type, "taskmate/apply_child_stage");
  assert.equal(sent[1].apply, false);
  assert.equal(p._dialog.data.age_group, "9_12");
  assert.equal(p._hashDialog(), p._dialogInitialHash);
  assert.equal(p._stagePop, null);
});

test("adding a child just records the stage", async () => {
  const p = panel({ mode: "add" });
  p._callWS = async () => { throw new Error("no call expected"); };
  await p._pickChildStage("13_plus");
  assert.equal(p._dialog.data.age_group, "13_plus");
  assert.ok(!p._stagePop);
});

// HAOS-Dev: the confirm opened behind the Edit child drawer (z-index 30 under
// the drawer's 100), so "Change and apply" could not be reached.
test("the stage confirm sits above the child drawer", async () => {
  const { readFileSync } = require("node:fs");
  const path = require("node:path");
  const src = readFileSync(path.join(__dirname, "../../custom_components/taskmate/www/taskmate-panel.js"), "utf8");
  const zOf = (selector) => {
    const m = src.match(new RegExp(`\\n\\s*${selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")} \\{[^}]*?z-index:\\s*(\\d+)`));
    assert.ok(m, `${selector} has a z-index`);
    return Number(m[1]);
  };
  // The shared summary dialog (#1260) opened from the drawer is "stacked":
  // still a .tm-scrim (fixed, full viewport) but above the drawer's.
  const pop = zOf(".tm-scrim.tm-scrim-stacked");
  assert.ok(pop > zOf(".tm-scrim"), "above the drawer's scrim");
  assert.ok(pop < zOf(".tm-toast"), "toasts still show on top");
  assert.match(src, /\n\s*\.tm-scrim \{\s*position: fixed; inset: 0;/);

  // Rendered in the same dialog zone, after the drawer, so equal stacking
  // contexts compare by z-index alone.
  const p = panel({ scope: "all" });
  p._callWS = async () => ({ ok: true, res: { chores: [{ chore_id: "a", name: "Brush teeth", changes: {} }], skipped_shared: [], chore_items: ["no_deadlines"] } });
  p._kioskPinField = () => "";
  p._entityPickerField = () => "";
  p._iconPickerField = () => "";
  p._childColorField = () => "";
  p._childCelebrationField = () => "";
  p._haUsers = [];
  await p._pickChildStage("3_5");
  const html = p._renderChildDialog();
  const drawer = html.indexOf("tm-scrim tm-scrim-drawer");
  const popAt = html.indexOf("tm-scrim tm-scrim-stacked");
  assert.ok(drawer >= 0 && popAt > drawer, "the confirm follows the drawer");
  const pop2 = html.slice(popAt);
  assert.match(pop2, /aria-modal="true"/);
  assert.ok(!pop2.includes('data-act="close-dialog"'), "closing the confirm never closes the editor");
  assert.ok(pop2.includes('data-act="stage-pop-cancel"'));
  // Content: title, intro, card and chore groups, the chores and both buttons.
  assert.ok(pop2.includes("<h2>Change Isla's stage</h2>"));
  assert.ok(pop2.includes("Move Isla to <b>Joining in</b>. Apply its suggestions too?"));
  assert.ok(pop2.includes("Pre-Reader Mode on (child card)"));
  assert.ok(pop2.includes("No deadlines or deductions on chores only Isla does"));
  assert.ok(pop2.includes("<li>Brush teeth</li>"));
  assert.ok(pop2.includes('data-act="stage-only"') && pop2.includes("Change stage only"));
  assert.ok(pop2.includes('data-act="stage-apply"') && pop2.includes("Change and apply"));
  assert.ok(!pop2.includes(localize("panel.btn_cancel") + "</button>"), "no Cancel next to the two choices");
});

test("stage confirm: shared chores are named, nothing-to-change is said, and cards scope hides chore items", async () => {
  const p = panel({ scope: "all" });
  p._callWS = async () => ({ ok: true, res: { chores: [], skipped_shared: [{ chore_id: "b", name: "Feed the cat" }], chore_items: ["no_deadlines"] } });
  await p._pickChildStage("3_5");
  const html = p._renderStagePop();
  assert.ok(html.includes("Nothing to change on Isla's own chores."));
  assert.ok(html.includes("Shared with other children, so left alone: Feed the cat"));
  assert.ok(html.includes('data-act="stage-pop-cancel"') && html.includes('data-act="stage-only"'));
  assert.ok(html.includes("Change stage<"));
  // Nothing to apply: a statement, not a question.
  assert.ok(html.includes("Move Isla to <b>Joining in</b>.</p>"));
  assert.ok(!html.includes("Apply its suggestions too?"));

  const cards = panel({ scope: "cards" });
  cards._callWS = async () => ({ ok: true, res: { chores: [], skipped_shared: [], chore_items: [] } });
  await cards._pickChildStage("3_5");
  const c = cards._renderStagePop();
  assert.ok(c.includes("Pre-Reader Mode on (child card)"));
  assert.ok(c.includes("Move Isla to <b>Joining in</b>.</p>"), "cards scope: the card list stays under a plain statement");
  assert.ok(!c.includes("Apply its suggestions too?"));
  assert.ok(!c.includes("No deadlines or deductions"));
});

test("stage confirm: while it checks the chores, only Cancel is offered", async () => {
  const p = panel();
  let release;
  p._callWS = () => new Promise((r) => { release = r; });
  const pending = p._pickChildStage("9_12");
  const html = p._renderStagePop();
  assert.ok(html.includes("Checking Isla's chores"));
  assert.ok(!html.includes('data-act="stage-only"'));
  release({ ok: true, res: { chores: [], skipped_shared: [], chore_items: [] } });
  await pending;
});
