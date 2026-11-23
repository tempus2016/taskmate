// Surprise inspections on the Parent Dashboard Card (#1285).
//
// A parent standing in the child's room should be able to start an
// inspection on a recently approved chore and pass, fail or cancel an open
// one from the card, in every card look, without the admin panel. The tab
// only appears while the feature is on (the sensor publishes
// `inspection_settings`) and the card's show_inspections is not false.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// Objects built inside the card's sandbox come from another realm.
const plain = (value) => JSON.parse(JSON.stringify(value));

const ENTITY = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro"];

const confirms = [];
let confirmAnswer = true;
const Dash = loadCard("taskmate-parent-dashboard-card.js", {
  window: { confirm: (msg) => (confirms.push(msg), confirmAnswer) },
}).get("taskmate-parent-dashboard-card");

const SETTINGS = { bonus: 10, window: "2h", fail_mode: "redo", tell_child: true, bedtime: "20:00", bed_rule: { min_minutes: 30, fallback_hours: 1 } };
const inAnHour = () => new Date(Date.now() + 61 * 60000).toISOString();

function card({ design = "classic", config = {}, attrs = {} } = {}) {
  const c = new Dash();
  c.setConfig({ entity: ENTITY, card_design: design, ...config });
  c.calls = [];
  c.hass = {
    language: "en",
    callService: async (domain, service, data) => c.calls.push({ domain, service, data }),
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", points: 10 }],
          chores: [],
          todays_completions: [],
          chore_completions: [],
          inspection_settings: SETTINGS,
          open_inspections: [
            { id: "i1", completion_id: "c9", child_id: "kid1", child_name: "Mia", chore_name: "Tidy room", points: 5, bonus: 15, until: inAnHour(), tell_child: false, source: "random", can_redo: true },
          ],
          inspectable_completions: [
            { completion_id: "c1", child_id: "kid1", child_name: "Mia", chore_name: "Dishes", points: 3, approved_at: new Date().toISOString() },
          ],
          ...attrs,
        },
      },
    },
  };
  return c;
}

const view = (c) => render(c.render());
const onTab = (c) => { c._activeSection = "inspections"; return view(c); };
const tabLabel = localize("dashboard.tab_inspections");
// Console writes its tab labels in capitals.
const isTab = (b) => b.text.toLowerCase().startsWith(tabLabel.toLowerCase());

for (const design of DESIGNS) {
  test(`${design}: the Inspections tab shows while the feature is on, with the open count`, () => {
    const out = view(card({ design }));
    const tab = out.controls.find(isTab);
    assert.ok(tab, "Inspections tab");
    assert.match(tab.text, /1/);
  });

  test(`${design}: no tab when inspections are off or show_inspections is false`, () => {
    for (const c of [card({ design, attrs: { inspection_settings: undefined } }), card({ design, config: { show_inspections: false } })]) {
      c._activeSection = "inspections";
      const out = view(c);
      assert.ok(!out.controls.some(isTab));
      // The card falls back to the overview rather than an empty tab.
      assert.equal(c._activeSection, "overview");
    }
  });

  test(`${design}: an open inspection shows its bonus, time left and how it was started`, () => {
    const out = onTab(card({ design }));
    assert.match(out.markup, /Tidy room/);
    assert.match(out.markup, /\+15/);
    assert.match(out.markup, /1h 0[01]m/);
    assert.ok(out.markup.includes(localize("dashboard.insp_secret")));
    assert.ok(out.markup.includes(localize("dashboard.insp_random")));
    assert.ok(out.markup.includes(localize("dashboard.insp_open_heading")));
    assert.ok(out.markup.includes(localize("dashboard.insp_recent_heading")));
  });

  test(`${design}: passing pays the bonus the parent sets, with a note`, async () => {
    const c = card({ design });
    await onTab(c).control(localize("dashboard.insp_pass")).click();
    assert.equal(c._inspForm.kind, "pass");
    assert.equal(c._inspForm.bonus, 15);
    c._patchInspForm({ bonus: "20", note: "  Spotless  " });
    await onTab(c).control("pi-go").click();
    assert.deepEqual(plain(c.calls.map((x) => [x.service, x.data])), [["pass_inspection", { inspection_id: "i1", bonus: 20, note: "Spotless" }]]);
    assert.equal(c._inspForm, null);
  });

  test(`${design}: failing defaults to send back (fail_mode redo) and can just note it`, async () => {
    const c = card({ design });
    await onTab(c).control(localize("dashboard.insp_fail")).click();
    assert.equal(c._inspForm.mode, "redo");
    let out = onTab(c);
    assert.ok(out.control("pi-go").text.includes(localize("dashboard.insp_fail_send_back")));
    await out.control(localize("dashboard.insp_fail_note_label")).click();
    out = onTab(c);
    assert.ok(out.control("pi-go").text.includes(localize("dashboard.insp_fail_save")));
    await out.control("pi-go").click();
    assert.deepEqual(plain(c.calls[0]), { domain: "taskmate", service: "fail_inspection", data: { inspection_id: "i1", redo: false, note: "" } });
  });

  test(`${design}: send back is unavailable when the chore can't be redone`, async () => {
    const c = card({ design, attrs: { open_inspections: [{ id: "i2", child_id: "kid1", child_name: "Mia", chore_name: "Bins", bonus: 5, until: inAnHour(), can_redo: false }] } });
    await onTab(c).control(localize("dashboard.insp_fail")).click();
    assert.equal(c._inspForm.mode, "note");
    const out = onTab(c);
    const redo = out.control(localize("dashboard.insp_fail_redo_label"));
    assert.ok(redo.disabled);
    assert.ok(out.markup.includes(localize("dashboard.insp_fail_redo_unavailable")));
  });

  test(`${design}: cancelling asks first`, async () => {
    const c = card({ design });
    const cancel = () => onTab(c).control(`aria-label="${localize("dashboard.insp_cancel")}"`).click();
    confirmAnswer = false;
    await cancel();
    assert.equal(c.calls.length, 0);
    confirmAnswer = true;
    await cancel();
    assert.deepEqual(plain(c.calls.map((x) => [x.service, x.data])), [["cancel_inspection", { inspection_id: "i1" }]]);
    assert.ok(confirms.includes(localize("dashboard.insp_cancel_confirm")));
  });

  test(`${design}: starting uses the defaults, and the parent can change them`, async () => {
    const c = card({ design });
    await onTab(c).control(`aria-label="${localize("dashboard.insp_flag_tooltip")}"`).click();
    assert.deepEqual(plain({ window: c._inspForm.window, bonus: c._inspForm.bonus, tell: c._inspForm.tell }), { window: "2h", bonus: 10, tell: true });
    let out = onTab(c);
    assert.ok(out.markup.includes(localize("dashboard.insp_tell_label", { name: "Mia" })));
    await out.control(localize("dashboard.insp_window_4h")).click();
    c._patchInspForm({ bonus: "99999", tell: false });
    out = onTab(c);
    await out.control("pi-go").click();
    assert.deepEqual(plain(c.calls[0]), { domain: "taskmate", service: "start_inspection", data: { completion_id: "c1", bonus: 10000, window: "4h", tell_child: false } });
  });

  test(`${design}: the open inspections count towards the header badge`, () => {
    const out = view(card({ design, attrs: { chore_completions: [{ completion_id: "x", child_id: "kid1", chore_name: "A", completed_at: new Date().toISOString() }] } }));
    // 1 chore approval + 1 open inspection.
    assert.match(out.markup, design === "classic" ? /pending-badge[\s\S]*?2\s*<\/div>/ : /class="cnt">2</);
  });

  test(`${design}: an empty tab says what will show up there`, () => {
    const out = onTab(card({ design, attrs: { open_inspections: [], inspectable_completions: [] } }));
    assert.ok(out.markup.includes(localize("dashboard.insp_empty")));
  });
}

test("the editor offers show_inspections and drops the default", async () => {
  class CustomEvent {
    constructor(type, init = {}) { this.type = type; this.detail = init.detail; }
  }
  const Editor = loadCard("taskmate-parent-dashboard-card.js", { sandbox: { CustomEvent } }).get("taskmate-parent-dashboard-card-editor");
  const ed = new Editor();
  ed.hass = {};
  ed.setConfig({ entity: ENTITY, show_inspections: false });
  assert.ok(ed._buildSchema().some((f) => f.name === "show_inspections"));
  assert.equal(ed._computeLabel({ name: "show_inspections" }), localize("dashboard.editor.show_inspections"));
  const sent = [];
  ed.dispatchEvent = (e) => sent.push(e);
  ed._formChanged({ detail: { value: { entity: ENTITY, show_inspections: true } } });
  assert.ok(!("show_inspections" in sent[0].detail.config));
});
