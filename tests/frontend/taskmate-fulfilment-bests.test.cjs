const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, render, localize } = require("./harness.cjs");

// Reward fulfilment (#1098) and personal bests (#1099), on every design
// (two-render-paths rule): the approvals card's "still to hand over" list,
// the child card's "you're owed" strip and new-record banner, the Personal
// Bests card, and the panel's Today page card.

const DESIGNS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];
const ENTITY = "sensor.taskmate_overview";
// Objects built inside the vm sandbox have foreign prototypes; compare by value.
const plain = (value) => JSON.parse(JSON.stringify(value));

const owed = (over = {}) => ({
  claim_id: "c1", child_id: "kid1", child_name: "Mia", reward_id: "r1", reward_name: "Movie night",
  reward_icon: "mdi:movie", cost: 40, approved_at: "2026-10-15T10:00:00+00:00", days_owed: 3, ...over,
});

// ── approvals card ────────────────────────────────────────────────────────

const ApprovalsCard = loadCard("taskmate-approvals-card.js").get("taskmate-approvals-card");

function approvalsCard({ design = "classic", owedList = [owed()], claims = [], childId } = {}) {
  const card = new ApprovalsCard();
  card.setConfig({ entity: ENTITY, card_design: design, ...(childId ? { child_id: childId } : {}) });
  const calls = [];
  card.hass = {
    states: {
      [ENTITY]: {
        state: "1",
        attributes: {
          children: [{ id: "kid1", name: "Mia" }, { id: "kid2", name: "Leo" }],
          chore_completions: [],
          reward_claims: claims,
          mandatory_misses: [],
          owed_rewards: owedList,
          points_icon: "mdi:star",
        },
      },
    },
    callService: async (domain, service, data) => { calls.push({ domain, service, data }); },
  };
  card._loading = {};
  return { card, calls };
}

for (const design of DESIGNS) {
  test(`approvals: ${design} lists an owed reward with a hand-over button`, async () => {
    const { card, calls } = approvalsCard({ design });
    const out = render(card.render());
    assert.ok(out.markup.includes("Movie night"));
    assert.ok(out.markup.includes(localize("approvals.owed_section")));
    assert.ok(out.markup.includes(localize("approvals.owed_days", { count: 3 })));
    const btn = out.control(localize("approvals.owed_delivered"));
    assert.ok(btn, "a Handed over button is drawn");
    await btn.click();
    assert.deepEqual(plain(calls), [{ domain: "taskmate", service: "mark_reward_delivered", data: { claim_id: "c1" } }]);
  });

  test(`approvals: ${design} owed rewards do not count as pending`, () => {
    const { card } = approvalsCard({ design });
    const { markup } = render(card.render());
    assert.doesNotMatch(markup, /class="(pending-count|cnt)"/, "no header badge for owed-only");
    assert.ok(markup.includes("Movie night"), "but the owed list itself is still drawn");
  });

  test(`approvals: ${design} hides owed rewards for other children when filtered`, () => {
    const { card } = approvalsCard({ design, childId: "kid2" });
    const { markup } = render(card.render());
    assert.ok(!markup.includes("Movie night"));
  });
}

test("approvals: classic says redeemed today for a fresh one", () => {
  const { card } = approvalsCard({ owedList: [owed({ days_owed: 0 })] });
  assert.ok(render(card.render()).markup.includes(localize("approvals.owed_today")));
});

test("approvals: nothing owed and nothing pending is the usual empty state", () => {
  const { card } = approvalsCard({ owedList: [] });
  const { markup } = render(card.render());
  assert.ok(markup.includes(localize("approvals.no_pending_approvals")) || markup.includes(localize("approvals.all_caught_up")));
  assert.ok(!markup.includes(localize("approvals.owed_section")));
});

// ── child card ────────────────────────────────────────────────────────────

const ChildCard = loadCard("taskmate-child-card.js").get("taskmate-child-card");

function childCard({ design = "classic", child = {}, config = {} } = {}) {
  const card = new ChildCard();
  card.setConfig({ entity: ENTITY, child_id: "kid1", card_design: design, ...config });
  const calls = [];
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          children: [{ id: "kid1", name: "Mia", chore_order: [], ...child }],
          chores: [{ id: "tidy", name: "Tidy room", points: 5, time_category: "anytime", assigned_to: [], due_days: [],
            schedule_mode: "specific_days", assignment_mode: "everyone" }],
          todays_completions: [],
          chore_availability: {},
          today_day_of_week: "wednesday",
          points_icon: "mdi:star",
          points_name: "Stars",
        },
      },
    },
    callService: async (domain, service, data) => { calls.push({ domain, service, data }); },
  };
  card._loading = {};
  card._optimisticCompletions = {};
  card._playSound = () => {};
  card._spawnConfetti = () => {};
  return { card, calls };
}

const OWED_CHILD = { owed_rewards: [{ claim_id: "c1", reward_name: "Movie night", reward_icon: "mdi:movie", days_owed: 2 }] };
const RECORD_CHILD = {
  personal_bests: {
    best_day_points: { value: 25, date: "2026-10-18", previous: 20 },
    longest_streak: { value: 9, date: "2026-10-10" },
    new_today: ["best_day_points"],
  },
};

for (const design of DESIGNS) {
  test(`child: ${design} shows what is owed and "Got it!" confirms as the child`, async () => {
    const { card, calls } = childCard({ design, child: OWED_CHILD });
    const out = render(card.render());
    assert.ok(out.markup.includes(localize("child.owed_title")));
    assert.ok(out.markup.includes("Movie night"));
    assert.ok(out.markup.includes(localize("child.owed_days", { count: 2 })));
    const btn = out.control(localize("child.owed_got_it"));
    assert.ok(btn, "Got it! is drawn");
    await btn.click();
    assert.deepEqual(plain(calls), [{ domain: "taskmate", service: "mark_reward_delivered", data: { claim_id: "c1", child_id: "kid1" } }]);
  });

  test(`child: ${design} celebrates today's record and names it with the family's points`, () => {
    const { card } = childCard({ design, child: RECORD_CHILD });
    const { markup } = render(card.render());
    assert.ok(markup.includes(localize("child.record_title")));
    assert.ok(markup.includes(`${localize("child.record_best_day_points", { points_name: "Stars" })}: 25`));
    assert.ok(!markup.includes(localize("child.record_longest_streak")), "only today's records are announced");
  });

  test(`child: ${design} stays quiet with no owed reward or new record`, () => {
    const { card } = childCard({ design, child: { personal_bests: { longest_streak: { value: 9, date: "" } } } });
    const { markup } = render(card.render());
    assert.ok(!markup.includes(localize("child.owed_title")));
    assert.ok(!markup.includes(localize("child.record_title")));
  });
}

test("child: the record banner can be switched off per card", () => {
  const { card } = childCard({ child: RECORD_CHILD, config: { show_personal_bests: false } });
  assert.ok(!render(card.render()).markup.includes(localize("child.record_title")));
});

// ── personal bests card ───────────────────────────────────────────────────

const BestsCard = loadCard("taskmate-personal-bests-card.js").get("taskmate-personal-bests-card");

function bestsCard({ design = "classic", children, config = {} } = {}) {
  const card = new BestsCard();
  card.setConfig({ entity: ENTITY, card_design: design, ...config });
  card.hass = {
    states: {
      [ENTITY]: {
        state: "ok",
        attributes: {
          points_name: "Stars",
          children: children || [
            { id: "kid1", name: "Mia", ...RECORD_CHILD },
            { id: "kid2", name: "Leo" },
          ],
        },
      },
    },
  };
  return card;
}

for (const design of DESIGNS) {
  test(`bests card: ${design} draws every record tile, marks today's and shows the empty child`, () => {
    const { markup } = render(bestsCard({ design }).render());
    for (const key of ["longest_streak", "best_day_points", "best_day_chores", "best_week_points", "best_single_award"]) {
      assert.ok(markup.includes(localize(`bests.record_${key}`, { points_name: "Stars" })), key);
    }
    assert.ok(markup.includes(">25<") || markup.includes(">25</"), "the record value is shown");
    assert.ok(markup.includes(localize("bests.new_tag")));
    assert.ok(markup.includes(localize("bests.beat_previous", { previous: 20 })));
    assert.ok(markup.includes(localize("bests.new_count", { count: 1 })));
    assert.ok(markup.includes("Leo") && markup.includes(localize("bests.none_yet")));
  });

  test(`bests card: ${design} narrows to one child`, () => {
    const { markup } = render(bestsCard({ design, config: { child_id: "kid2" } }).render());
    assert.ok(markup.includes("Leo") && !markup.includes("Mia"));
    assert.ok(!markup.includes(localize("bests.new_tag")));
  });
}

test("bests card: the stub config points at the overview and the editor exists", () => {
  assert.equal(BestsCard.getStubConfig().entity, ENTITY);
  assert.throws(() => new BestsCard().setConfig({}), /entity/i);
});

// ── admin panel Today page ────────────────────────────────────────────────

const TaskMatePanel = loadCard("taskmate-panel.js").get("taskmate-panel");

function panel(extra = {}) {
  const p = Object.create(TaskMatePanel.prototype);
  p._t = (key, params = {}) => (params.count != null ? `${key}:${params.count}` : key);
  p._timeAgo = () => "just now";
  p._activeTab = "today";
  p._state = {
    children: [{ id: "kid1", name: "Malia", points: 10 }, { id: "kid2", name: "Vaiha", points: 5 }],
    chores: [], rewards: [], pending_completions: [], pending_reward_claims: [], swap_requests: [], wishes: [],
    settings: { points_name: "Stars" },
    today: { board: { date: "2026-10-18", children: [] }, history: {} },
    owed_rewards: [owed({ child_id: "kid2", child_name: "Vaiha" })],
    ...extra,
  };
  return p;
}

test("panel: the Today page lists owed rewards with a hand-over button", () => {
  const html = panel()._renderTodayTab();
  assert.match(html, /panel\.today_owed_title/);
  assert.match(html, /Vaiha/);
  assert.match(html, /Movie night/);
  assert.match(html, /panel\.today_owed_days:3/);
  assert.match(html, /data-act="reward-delivered" data-id="c1"/);
});

test("panel: the owed card follows the child filter and disappears when empty", () => {
  const p = panel();
  assert.equal(p._renderOwedCard([{ id: "kid1" }]), "");
  assert.equal(panel({ owed_rewards: [] })._renderOwedCard(p._state.children), "");
});

test("panel: the settings page offers the fulfilment switch and the reminder days", () => {
  const src = require("node:fs").readFileSync(
    require("node:path").join(__dirname, "../../custom_components/taskmate/www/taskmate-panel.js"), "utf8");
  assert.match(src, /data-setting="reward_fulfilment_enabled"/);
  assert.match(src, /data-setting="reward_fulfilment_reminder_days"/);
});
