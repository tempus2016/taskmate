// Chore auctions (#982): the admin panel's Auctions page and start sheet.

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard } = require("./harness.cjs");

const TaskMatePanel = loadCard("taskmate-panel.js").get("taskmate-panel");
const DAY = 86400e3;
const isoDate = (ms) => {
  const d = new Date(Date.now() + ms);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

function panelWith(auctions, extra = {}) {
  const panel = Object.create(TaskMatePanel.prototype);
  panel._t = (key, params = {}) => `${key}${Object.keys(params).length ? JSON.stringify(params) : ""}`;
  panel._state = {
    children: [{ id: "k1", name: "Malia" }, { id: "k2", name: "Vaiha" }],
    chores: [
      { id: "c1", name: "Clean the bathroom", enabled: true, assignment_mode: "everyone" },
      { id: "c2", name: "Team wash", enabled: true, team_size: 2 },
      { id: "c3", name: "Nobody's", enabled: true, assignment_mode: "unassigned" },
    ],
    auctions,
    ...extra,
  };
  return panel;
}

const live = (extra = {}) => ({
  id: "a1", chore_id: "c1", chore_name: "Clean the bathroom", icon: "", occurrence: isoDate(2 * DAY),
  max_points: 40, min_points: 1, normal_points: 6, closes_at: new Date(Date.now() + 3600e3).toISOString(),
  status: "open", eligible_child_ids: ["k1", "k2"], bid_count: 2,
  bids: [{ child_id: "k2", points: 17, at: "" }, { child_id: "k1", points: 31, at: "" }], ...extra,
});

test("the Auctions item sits in the Earn group after Bounties, with the live count", () => {
  const panel = panelWith([live(), live({ id: "a2", status: "closed", winner_id: "k1", price: 5 })]);
  const earn = panel._sidebarGroups().find((g) => g.key === "earn");
  const ids = earn.items.map((i) => i.id);
  assert.equal(ids[ids.indexOf("bounties") + 1], "auctions");
  assert.equal(earn.items.find((i) => i.id === "auctions").count, 1);
});

test("parents see the bid amounts, lowest first, and can hide them", () => {
  const panel = panelWith([live()]);
  const shown = panel._renderAuctionsTab();
  assert.match(shown, /17 ★[\s\S]*leading[\s\S]*31 ★/);
  panel._auctionReveal = false;
  const hidden = panel._renderAuctionsTab();
  assert.ok(!hidden.includes("17 ★") && hidden.includes("panel.auction_sealed"));
  assert.ok(hidden.includes('data-act="auction-close-now"') && hidden.includes('data-act="auction-cancel"'));
});

test("a no-bid auction offers a re-open, a won one shows the winner and the chore's status", () => {
  const panel = panelWith([
    live({ id: "nb", status: "closed", winner_id: "", price: 0, bids: [], closed_at: new Date().toISOString() }),
    live({ id: "won", status: "closed", winner_id: "k2", price: 17, chore_status: "done", points_awarded: 17, closed_at: new Date().toISOString() }),
  ]);
  panel._auctionSubTab = "closed";
  const markup = panel._renderAuctionsTab();
  assert.ok(markup.includes('data-act="auction-reopen" data-id="nb"'));
  assert.ok(markup.includes("Vaiha") && markup.includes('panel.auction_status_done{"points":17}'));
});

test("only chores that can go to one child at a price are offered", () => {
  const panel = panelWith([]);
  const offered = panel._state.chores.filter((c) => panel._auctionable(c)).map((c) => c.id);
  assert.deepEqual(JSON.parse(JSON.stringify(offered)), ["c1"]);
});

test("closing presets must land after now and before the chore's day", () => {
  const panel = panelWith([]);
  const d = { occurrence: isoDate(DAY) };
  assert.equal(panel._auctionCloseAt(d, "daybefore") === null, new Date(`${isoDate(0)}T18:00:00`) <= new Date());
  assert.equal(panel._auctionCloseAt(d, "tomorrow"), null); // 08:00 on the day itself: too late
  assert.equal(panel._auctionCloseAt({ occurrence: "" }, "tonight"), null);
  const far = { occurrence: isoDate(5 * DAY) };
  assert.ok(panel._auctionCloseAt(far, "tomorrow"));
  assert.ok(["tonight", "tomorrow", "daybefore"].includes(panel._auctionDefaultClose(far)));
});

test("the start sheet renders as a side drawer with the chosen occurrence", () => {
  const panel = panelWith([]);
  panel._dialog = { kind: "auction", mode: "add", data: {
    chore_id: "c1", occurrences: [isoDate(2 * DAY), isoDate(9 * DAY)], occurrence: isoDate(2 * DAY), pool: ["k1", "k2"],
    eligible_child_ids: ["k1"], normal_points: 6, max_points: 12, min_on: false, min_points: 1, close_mode: "daybefore",
    close_pick: "", notify_children: true, loading: false, refusal: "",
  } };
  const markup = panel._renderAuctionDialog();
  assert.ok(markup.includes("tm-drawer"));
  assert.ok(markup.includes('data-act="auction-occ"') && markup.includes('data-act="save-auction"'));
  assert.ok(markup.includes('data-act="auction-max-set" data-id="12"'));
  assert.match(markup, /tm-chip-on" data-act="toggle-auction-el" data-id="k1"/);
});
