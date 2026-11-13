const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

const plain = (v) => JSON.parse(JSON.stringify(v));

// Allowance payout from the admin panel: the dialog starts at the whole
// balance, refuses more than the balance, and records through
// record_allowance_payout exactly once even on a double tap.

function panel({ children, settings = {} } = {}) {
  const TaskMatePanel = loadCard("taskmate-panel.js").get("taskmate-panel");
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => `${key}${Object.keys(params).length ? ":" + JSON.stringify(params) : ""}`;
  p._state = {
    children: children || [{ id: "kid1", name: "Mia", points: 77 }, { id: "kid2", name: "Ola", points: 0 }],
    settings: { allowance_enabled: true, allowance_rate: 10, allowance_currency: "£", points_name: "Stars", ...settings },
  };
  const calls = [];
  const toasts = [];
  let release;
  p._callService = (service, data) => { calls.push({ service, data }); return new Promise((r) => { release = () => r({ ok: true }); }); };
  p._fetchState = async () => {};
  p._showToast = (kind, text) => toasts.push({ kind, text });
  p._openDialog = (d) => { p._dialog = d; };
  p._closeDialog = () => { p._dialog = null; };
  return { p, calls, toasts, done: () => release && release() };
}

test("panel: payout dialog starts at the child's whole balance", () => {
  const { p } = panel();
  p._openPayoutDialog("kid1");
  assert.deepEqual(plain(p._dialog), { kind: "payout", data: { child_id: "kid1", points: 77 } });
  const html = p._renderPayoutDialog();
  assert.match(html, /data-act="save-payout"/);
  assert.match(html, /data-role="payout-preview"/);
  assert.match(html, /7\.70/);
});

test("panel: payout dialog with no child asks for one and offers no save", () => {
  const { p } = panel();
  p._openPayoutDialog("");
  assert.equal(p._dialog.data.child_id, "");
  const html = p._renderPayoutDialog();
  assert.match(html, /panel\.payout_pick_child/);
  assert.doesNotMatch(html, /save-payout/);
});

test("panel: a single child is picked automatically", () => {
  const { p } = panel({ children: [{ id: "only", name: "Mia", points: 5 }] });
  p._openPayoutDialog("");
  assert.equal(p._dialog.data.child_id, "only");
});

test("panel: a child with nothing to pay out gets a message, not a form", () => {
  const { p } = panel();
  p._openPayoutDialog("kid2");
  const html = p._renderPayoutDialog();
  assert.match(html, /panel\.payout_none/);
  assert.doesNotMatch(html, /save-payout|data-field="points"/);
});

test("panel: payout above the balance is refused before calling Home Assistant", async () => {
  const { p, calls, toasts } = panel();
  p._openPayoutDialog("kid1");
  p._dialog.data.points = 78;
  await p._savePayoutDialog();
  assert.equal(calls.length, 0);
  assert.equal(toasts[0].kind, "err");
  assert.match(toasts[0].text, /panel\.payout_err_amount/);
});

test("panel: a double tap records the payout once", async () => {
  const { p, calls, toasts, done } = panel();
  p._openPayoutDialog("kid1");
  p._dialog.data.points = 30;
  const first = p._savePayoutDialog();
  const second = p._savePayoutDialog();
  done();
  await Promise.all([first, second]);
  assert.deepEqual(plain(calls), [{ service: "record_allowance_payout", data: { child_id: "kid1", points: 30 } }]);
  assert.equal(p._dialog, null);
  assert.equal(toasts[0].kind, "ok");
  assert.match(toasts[0].text, /panel\.payout_done/);
  assert.match(toasts[0].text, /\\"amount\\":\\"3\\"/);
});

test("panel: money shows two decimals only when it has pence", () => {
  const { p } = panel();
  assert.match(p._fmtMoney(76.9, "£"), /76\.90/);
  assert.match(p._fmtMoney(5, "£"), /"amount":"5"/);
});
