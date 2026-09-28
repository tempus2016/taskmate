// The browser's time zone is faked by pinning TZ before any Date is built, so
// the card sees a browser on UTC while Home Assistant runs somewhere else (#948).
process.env.TZ = "UTC";

const assert = require("node:assert/strict");
const { test } = require("node:test");

const { loadCard, localize } = require("./harness.cjs");

const { get } = loadCard("taskmate-child-card.js");
const ChildCard = get("taskmate-child-card");

function countdownAt(isoNow, haTimeZone) {
  const card = new ChildCard();
  card.setConfig({ entity: "sensor.taskmate_overview", child_id: "kid1" });
  card.hass = { config: { time_zone: haTimeZone }, states: {} };
  return card._getMidnightCountdown(new Date(isoNow));
}

const resetIn = (hours, mins) => localize("child.chores_reset_hours_mins", { hours, mins });

test("browser on UTC, HA on Europe/London, 00:10 BST counts to London midnight", () => {
  // 00:10 BST on 29 Sep is 23:10 UTC on the 28th; the next reset is 23h 50m away.
  assert.equal(countdownAt("2026-09-28T23:10:00Z", "Europe/London").label, resetIn(23, 50));
});

test("browser on UTC, HA on America/New_York, just after midnight", () => {
  // 00:05 EDT on 29 Sep is 04:05 UTC.
  assert.equal(countdownAt("2026-09-29T04:05:00Z", "America/New_York").label, resetIn(23, 55));
});

test("browser on UTC, HA on America/New_York, late evening", () => {
  // 23:30 EDT on 28 Sep is 03:30 UTC on the 29th — a UTC browser is already
  // past its own midnight, but HA's day still has 30 minutes to run.
  const countdown = countdownAt("2026-09-29T03:30:00Z", "America/New_York");
  assert.equal(countdown.label, localize("child.chores_reset_mins", { mins: 30 }));
  assert.equal(countdown.soon, true);
});

test("a 25-hour DST day in HA's zone is counted in full", () => {
  // London clocks go back at 02:00 BST on 25 Oct 2026, so the day that
  // starts at 00:00 BST (24 Oct 23:00 UTC) runs until 26 Oct 00:00 GMT.
  assert.equal(countdownAt("2026-10-24T23:10:00Z", "Europe/London").label, resetIn(24, 50));
});

test("same zone in browser and HA is unchanged", () => {
  assert.equal(countdownAt("2026-09-28T12:00:00Z", "UTC").label, resetIn(12, 0));
});
