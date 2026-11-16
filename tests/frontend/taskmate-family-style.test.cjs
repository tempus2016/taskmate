// Family style (#1260): the cards honour the family's leaderboard, penalties
// and raffles switches (published on the overview sensor only when off), the
// child card's help button follows Team style, and the admin panel offers the
// three styles, a "what will change" summary and the hide scope.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

const OVERVIEW = "sensor.taskmate_overview";
const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];

const resolver = loadCard("taskmate-attr-resolver.js", { sandbox: { queueMicrotask: () => {} } }).window;
const helpers = {
  __taskmate_feature_on: resolver.__taskmate_feature_on,
  __taskmate_family_style: resolver.__taskmate_family_style,
};

const CHILDREN = [{ id: "k1", name: "Ella", points: 40 }, { id: "k2", name: "Finn", points: 30 }];

function hass(extra = {}, admin = true) {
  return {
    language: "en",
    user: { is_admin: admin },
    states: { [OVERVIEW]: { state: "2", attributes: { children: CHILDREN, ...extra } } },
  };
}

// ── The shared helpers ───────────────────────────────────────────────────────

test("every feature is on, and no style is set, while the overview says nothing", () => {
  for (const f of ["leaderboard", "penalties", "raffles"]) assert.equal(helpers.__taskmate_feature_on(hass(), f), true);
  assert.equal(helpers.__taskmate_family_style(hass()), "");
  assert.equal(helpers.__taskmate_feature_on({}, "leaderboard"), true);
});

test("features_off and family_style come off the overview sensor", () => {
  const h = hass({ features_off: ["leaderboard", "raffles"], family_style: "team" });
  assert.equal(helpers.__taskmate_feature_on(h, "leaderboard"), false);
  assert.equal(helpers.__taskmate_feature_on(h, "penalties"), true);
  assert.equal(helpers.__taskmate_feature_on(h, "raffles"), false);
  assert.equal(helpers.__taskmate_family_style(h), "team");
});

// The off-state header: the card's title, its header colour, and the header
// block of that design (classic and designed paths differ).
function assertHeader(markup, design, title, colour, block) {
  assert.match(markup, block, `${design}: header block`);
  assert.ok(markup.includes(title), `${design}: title`);
  assert.ok(markup.includes(colour), `${design}: header colour`);
  const head = markup.search(block);
  assert.ok(head >= 0 && head < markup.indexOf(localize("common.feature_off_sub")), `${design}: header above the note`);
}

// ── Leaderboard ──────────────────────────────────────────────────────────────

const Leaderboard = loadCard("taskmate-leaderboard-card.js", { window: helpers }).get("taskmate-leaderboard-card");

function leaderboard(attrs, design = "classic", admin = true, config = {}) {
  const card = new Leaderboard();
  card.setConfig({ entity: OVERVIEW, card_design: design, ...config });
  card.hass = hass(attrs, admin);
  return render(card.render()).markup;
}

for (const design of DESIGNS) {
  test(`leaderboard (${design}): switched off shows a note and no ranking`, () => {
    const markup = leaderboard({ features_off: ["leaderboard"] }, design);
    assert.ok(markup.includes(localize("common.feature_off_leaderboard")));
    assert.ok(markup.includes(localize("common.feature_off_admin")));
    assert.doesNotMatch(markup, /🥇|Ella/);
  });

  test(`leaderboard (${design}): the off-state keeps the full-colour header`, () => {
    const markup = leaderboard({ features_off: ["leaderboard"] }, design, true, { title: "Our board", header_color: "#123456" });
    assertHeader(markup, design, "Our board", "#123456", design === "classic" ? /class="card-header"/ : /class="tmd-hd"/);
    const plain = leaderboard({ features_off: ["leaderboard"] }, design);
    assert.ok(plain.includes(localize("leaderboard.default_title")));
  });

  test(`leaderboard (${design}): a family that never switched it off still ranks`, () => {
    const markup = leaderboard({}, design);
    assert.ok(!markup.includes(localize("common.feature_off_leaderboard")));
    assert.match(markup, /Ella/);
  });
}

test("leaderboard: a child's dashboard gets no admin hint", () => {
  const markup = leaderboard({ features_off: ["leaderboard"] }, "classic", false);
  assert.ok(!markup.includes(localize("common.feature_off_admin")));
});

// ── Points display: rank medals ──────────────────────────────────────────────

const PointsDisplay = loadCard("taskmate-points-display-card.js", { window: helpers }).get("taskmate-points-display-card");

test("points display: rank medals follow the leaderboard switch and show_rank", () => {
  const card = new PointsDisplay();
  card.setConfig({ entity: OVERVIEW, mode: "multi" });
  card.hass = hass();
  assert.equal(card._showRank(), true);
  card.hass = hass({ features_off: ["leaderboard"] });
  assert.equal(card._showRank(), false);
  card.setConfig({ entity: OVERVIEW, mode: "multi", show_rank: false });
  card.hass = hass();
  assert.equal(card._showRank(), false);
});

// ── Penalties (the shared incentive base) ───────────────────────────────────

function penalties(attrs, design = "classic", config = {}) {
  const tag = "taskmate-penalties-card";
  const loaded = loadCard("taskmate-incentive-card.js", {
    window: helpers,
    transform: (src) => src.replace("export function createIncentiveCard", "function createIncentiveCard")
      + `\ncreateIncentiveCard({ tag: "${tag}", kind: "penalty", feature: "penalties", idKey: "penalty_id", i18n: "penalties", attr: "penalties",`
      + ` addKey: "add_penalty", newKey: "new_penalty", icon: "mdi:alert", headerIcon: "mdi:alert", applyIcon: "mdi:minus", sign: "",`
      + ` dpts: (n) => "-" + n, accent: "#e74c3c", designHd: "#c0392b", designIcons: { playroom: "!" }, cardName: "x", cardDesc: "x", bannerName: "X", bannerColor: "#000" });`,
    sandbox: { console: { info() {}, log() {}, warn() {}, error() {} } },
  });
  const card = new (loaded.get(tag))();
  card.setConfig({ entity: OVERVIEW, card_design: design, ...config });
  card.hass = hass({ penalties: [{ id: "p1", name: "Shouting", points: 5 }], ...attrs });
  return render(card.render()).markup;
}

for (const design of DESIGNS) {
  test(`penalties (${design}): switched off hides the list behind a note`, () => {
    const markup = penalties({ features_off: ["penalties"] }, design);
    assert.ok(markup.includes(localize("common.feature_off_penalties")));
    assert.doesNotMatch(markup, /Shouting/);
  });

  test(`penalties (${design}): the off-state keeps the full-colour header`, () => {
    const markup = penalties({ features_off: ["penalties"] }, design, { title: "House rules", header_color: "#123456" });
    assertHeader(markup, design, "House rules", "#123456", design === "classic" ? /class="card-header"/ : /class="tmd-hd"/);
  });

  test(`penalties (${design}): on by default`, () => {
    const markup = penalties({}, design);
    assert.ok(!markup.includes(localize("common.feature_off_penalties")));
    assert.match(markup, /Shouting/);
  });
}

test("the penalties card asks for its switch, and bonuses have none", () => {
  const { readFileSync } = require("node:fs");
  const path = require("node:path");
  const { WWW } = require("./harness.cjs");
  assert.match(readFileSync(path.join(WWW, "taskmate-penalties-card.js"), "utf8"), /feature: "penalties"/);
  assert.doesNotMatch(readFileSync(path.join(WWW, "taskmate-bonuses-card.js"), "utf8"), /feature:/);
});

// ── Raffles ──────────────────────────────────────────────────────────────────

const Raffle = loadCard("taskmate-raffle-card.js", { window: helpers }).get("taskmate-raffle-card");

test("raffles: switched off shows a note instead of the draws", () => {
  const card = new Raffle();
  card.setConfig({ entity: OVERVIEW, title: "Prize draw", header_color: "#123456" });
  card.hass = hass({ features_off: ["raffles"], raffles: [{ id: "r1", name: "Cinema night", status: "open", tickets: {}, total: 0 }] });
  const markup = render(card.render()).markup;
  assert.ok(markup.includes(localize("common.feature_off_raffles")));
  assert.doesNotMatch(markup, /Cinema night/);
  // The raffle card's header colour is set on the host, so check the header block and title.
  assert.match(markup, /class="rf-hd"/);
  assert.ok(markup.indexOf("Prize draw") >= 0 && markup.indexOf("Prize draw") < markup.indexOf(localize("common.feature_off_sub")));
  card.hass = hass({ raffles: [{ id: "r1", name: "Cinema night", status: "open", tickets: {}, total: 0 }] });
  assert.match(render(card.render()).markup, /Cinema night/);
});

// ── Child card: the help button under Team style ─────────────────────────────

const ChildCard = loadCard("taskmate-child-card.js", { window: helpers }).get("taskmate-child-card");

function helpOn(config, attrs = {}) {
  const card = new ChildCard();
  card.setConfig({ entity: OVERVIEW, child_id: "k1", ...config });
  card.hass = hass(attrs);
  return card._helpEnabled();
}

test("child card: help follows the YAML as before when no style is set", () => {
  assert.equal(helpOn({}), true);
  assert.equal(helpOn({ pre_reader: true }), false);
  assert.equal(helpOn({ show_help_button: false }), false);
});

test("child card: Team style shows help by default, even for pre-readers; explicit YAML wins", () => {
  const team = { family_style: "team" };
  assert.equal(helpOn({}, team), true);
  assert.equal(helpOn({ pre_reader: true }, team), true);
  assert.equal(helpOn({ show_help_button: false }, team), false);
  assert.equal(helpOn({ show_help_button: true, pre_reader: true }, team), false);
});

// ── Admin panel ──────────────────────────────────────────────────────────────

const Panel = loadCard("taskmate-panel.js").get("taskmate-panel");

function panel(settings = {}) {
  const p = Object.create(Panel.prototype);
  p._t = (key, params = {}) => (params && Object.keys(params).length ? `${key}:${JSON.stringify(params)}` : key);
  p._activeTab = "settings";
  p._state = { settings, children: [], penalties: [], raffles: [] };
  return p;
}

test("panel: Family style is the first Settings section, with Game marked as the default", () => {
  const p = panel({});
  const html = p._familyStyleSection(p._state.settings);
  assert.match(html, /panel\.style_title/);
  for (const k of ["game", "team", "custom"]) {
    assert.match(html, new RegExp(`data-act="style-pick" data-v="${k}"`));
    assert.match(html, new RegExp(`panel\\.style_${k}_fit`));
  }
  assert.match(html, /data-v="game" aria-pressed="true"/);
  assert.match(html, /panel\.style_default_tag/);
  assert.match(html, /data-setting="style_hide_scope" value="cards"/);
  for (const key of ["leaderboard_enabled", "penalties_enabled", "raffles_enabled"]) {
    assert.match(html, new RegExp(`<ha-switch data-setting="${key}" checked>`));
  }
  const { readFileSync } = require("node:fs");
  const path = require("node:path");
  const { WWW } = require("./harness.cjs");
  const src = readFileSync(path.join(WWW, "taskmate-panel.js"), "utf8");
  assert.match(src, /<div class="tm-settings">\s*\$\{this\._familyStyleSection\(s\)\}/);
});

test("panel: a stored style is shown as the current one, and switched-off features unchecked", () => {
  const p = panel({ family_style: "team", penalties_enabled: false, style_hide_scope: "both" });
  const html = p._familyStyleSection(p._state.settings);
  assert.match(html, /data-v="team" aria-pressed="true"/);
  assert.match(html, /<ha-switch data-setting="penalties_enabled" >/);
  assert.match(html, /data-setting="style_hide_scope" value="both"/);
});

test("panel: tabs leave the menu only when the scope is both and the feature is off", () => {
  const tabs = (p) => p._sidebarGroups().flatMap(g => g.items.map(it => it.id));
  let p = panel({ penalties_enabled: false, raffles_enabled: false });
  assert.ok(tabs(p).includes("penalties") && tabs(p).includes("raffles"));
  p = panel({ penalties_enabled: false, raffles_enabled: false, style_hide_scope: "both" });
  assert.ok(!tabs(p).includes("penalties") && !tabs(p).includes("raffles"));
  assert.ok(tabs(p).includes("bonuses"));
  p = panel({ style_hide_scope: "both" });
  assert.ok(tabs(p).includes("penalties") && tabs(p).includes("raffles"));
});

test("panel: the summary dialog lists turned off, turned on and unchanged", () => {
  const p = panel({});
  p._dialog = { kind: "family-style", data: { style: "team", changes: [
    { key: "leaderboard_enabled", old: true, new: false },
    { key: "inspections_enabled", old: true, new: false },
    { key: "family_goal_enabled", old: false, new: true },
  ] } };
  const html = p._renderDialog();
  assert.match(html, /<h2>panel\.style_dialog_title:\{&quot;style&quot;:&quot;panel\.style_team_title&quot;\}<\/h2>/);
  assert.match(html, /panel\.style_dialog_team_intro_cards/);
  const off = html.slice(html.indexOf("panel.style_group_off"), html.indexOf("panel.style_group_on"));
  assert.match(off, /panel\.style_opt_leaderboard/);
  assert.match(off, /panel\.style_opt_inspections/);
  assert.match(off, /panel\.style_on_off/);
  const on = html.slice(html.indexOf("panel.style_group_on"), html.indexOf("panel.style_group_same"));
  assert.match(on, /panel\.style_opt_family_goal/);
  assert.match(on, /panel\.style_opt_help_button/);
  const same = html.slice(html.indexOf("panel.style_group_same"));
  assert.match(same, /panel\.style_opt_roulette/);
  assert.match(same, /panel\.style_unchanged_rest/);
  assert.match(html, /data-act="style-apply"/);
});

test("panel: Custom shows only that nothing changes now", () => {
  const p = panel({ family_style: "team" });
  p._dialog = { kind: "family-style", data: { style: "custom", changes: [] } };
  const html = p._renderDialog();
  assert.match(html, /panel\.style_dialog_custom_intro/);
  assert.doesNotMatch(html, /panel\.style_group_off/);
});

test("panel: picking a style previews it first, and Apply applies it", async () => {
  const p = panel({});
  const sent = [];
  p._callWS = async (msg) => { sent.push(msg); return { ok: true, res: { changes: [] } }; };
  p._openDialog = (d) => { p._dialog = d; };
  p._closeDialog = () => {};
  p._fetchState = async () => {};
  p._showToast = () => {};
  await p._stylePick("game");
  assert.equal(sent.length, 0, "the current style is not re-applied");
  await p._stylePick("team");
  assert.deepEqual(JSON.parse(JSON.stringify(sent)), [{ type: "taskmate/family_style/preview", style: "team" }]);
  assert.equal(p._dialog.kind, "family-style");
  await p._styleApply();
  assert.deepEqual(JSON.parse(JSON.stringify(sent[1])), { type: "taskmate/apply_family_style", style: "team" });
});

test("panel: the family style summary stays a normal dialog with Cancel and Apply", () => {
  // The helper is shared with the child stage confirm (#1262), which stacks
  // above the child drawer; the Settings summary must not.
  const p = panel({});
  p._dialog = { kind: "family-style", data: { style: "team", changes: [{ key: "leaderboard_enabled", old: true, new: false }] } };
  const html = p._renderDialog();
  assert.doesNotMatch(html, /tm-scrim-stacked/);
  assert.match(html, /class="tm-scrim "/);
  assert.match(html, /data-act="close-dialog">panel\.btn_cancel<\/button>/);
  assert.match(html, /data-act="style-apply">/);
  assert.equal((html.match(/<button type="button" class="tm-btn/g) || []).length, 2);
});
