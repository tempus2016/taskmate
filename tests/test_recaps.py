"""Recaps (#929): Wrapped-style period summaries on a parent-chosen schedule.

Covers the calendar maths (weekly follows the first weekday, every 9 months is
anchored to 1 January 2026), the daily ledger that outlives history pruning,
building at the boundary with no back-fill, catch-up after downtime, retention,
the preview, the announcement (one push per child, one grouped parent message,
one event per child) and the card's websocket reads.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import voluptuous as vol
from homeassistant.util import dt as dt_util

from custom_components.taskmate import websocket as ws
from custom_components.taskmate import websocket_recaps as wsr
from custom_components.taskmate.coord_notifications import NotificationCoordinator
from custom_components.taskmate.coord_recaps import (
    completed_periods,
    period_for,
    period_label,
    week_start_for_country,
)
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import (
    AwardedBadge,
    Badge,
    Child,
    Chore,
    ChoreCompletion,
    ParentRecipient,
    PointsTransaction,
    Reward,
    RewardClaim,
)
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc


def _at(day: date, hour: int = 17) -> datetime:
    return datetime(day.year, day.month, day.day, hour, 0, tzinfo=UTC)


@pytest.fixture
def clock(monkeypatch):
    """Pin dt_util.now(); returns a setter taking a date (or datetime)."""

    def set_now(when):
        if isinstance(when, date) and not isinstance(when, datetime):
            when = datetime(when.year, when.month, when.day, 0, 1, tzinfo=UTC)
        monkeypatch.setattr(type(dt_util), "_now", when, raising=False)
        monkeypatch.setattr(dt_util, "_now", when, raising=False)

    return set_now


async def _make(hass, *, names=("Malia", "Vaiha"), country="GB"):
    hass.config = SimpleNamespace(country=country)
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.entry_id = "recap_test"
    coord.storage = TaskMateStorage(hass, "recap_test")
    await coord.storage.async_load()
    coord.notifications = NotificationCoordinator(hass, coord.storage)
    coord.notifications.coordinator = coord
    hass.auth = MagicMock()

    async def _get_user(_uid):
        return SimpleNamespace(is_admin=False)

    hass.auth.async_get_user = _get_user
    coord.kids = {}
    for name in names:
        child = Child(name=name)
        coord.storage.add_child(child)
        coord.kids[name] = child.id
    coord.chore = Chore(name="Feed the cat", icon="mdi:cat")
    coord.other = Chore(name="Make my bed", icon="mdi:bed")
    coord.storage.add_chore(coord.chore)
    coord.storage.add_chore(coord.other)
    return coord


def _done(coord, kid, day, chore=None, points=10, approved=True):
    coord.storage.add_completion(
        ChoreCompletion(
            chore_id=(chore or coord.chore).id,
            child_id=coord.kids[kid],
            completed_at=_at(day),
            approved=approved,
            points_awarded=points,
        )
    )


# ── calendar maths ───────────────────────────────────────────────────────


class TestPeriods:
    def test_week_follows_first_weekday(self):
        sunday = date(2026, 9, 27)
        assert period_for("weekly", sunday, 0) == (date(2026, 9, 21), date(2026, 9, 27))
        assert period_for("weekly", sunday, 6) == (date(2026, 9, 27), date(2026, 10, 3))
        assert period_for("weekly", sunday, 5) == (date(2026, 9, 26), date(2026, 10, 2))

    def test_country_decides_the_first_weekday(self):
        assert week_start_for_country("GB") == 0
        assert week_start_for_country("us") == 6
        assert week_start_for_country("EG") == 5
        assert week_start_for_country(None) == 0

    @pytest.mark.parametrize(
        ("freq", "day", "expected"),
        [
            ("monthly", date(2026, 2, 14), (date(2026, 2, 1), date(2026, 2, 28))),
            ("every_3_months", date(2026, 8, 31), (date(2026, 7, 1), date(2026, 9, 30))),
            ("every_6_months", date(2026, 7, 1), (date(2026, 7, 1), date(2026, 12, 31))),
            ("yearly", date(2026, 9, 27), (date(2026, 1, 1), date(2026, 12, 31))),
        ],
    )
    def test_calendar_aligned(self, freq, day, expected):
        assert period_for(freq, day) == expected

    @pytest.mark.parametrize(
        ("day", "expected"),
        [
            (date(2026, 9, 27), (date(2026, 1, 1), date(2026, 9, 30))),
            (date(2026, 10, 1), (date(2026, 10, 1), date(2027, 6, 30))),
            (date(2027, 7, 1), (date(2027, 7, 1), date(2028, 3, 31))),
            (date(2025, 12, 31), (date(2025, 4, 1), date(2025, 12, 31))),
        ],
    )
    def test_nine_months_anchored_to_1_january_2026(self, day, expected):
        assert period_for("every_9_months", day) == expected

    def test_completed_periods_newest_first(self):
        got = list(completed_periods("monthly", date(2026, 10, 1), limit=2))
        assert got == [(date(2026, 9, 1), date(2026, 9, 30)), (date(2026, 8, 1), date(2026, 8, 31))]
        # Mid-month the current month is not finished yet.
        assert next(completed_periods("monthly", date(2026, 10, 15)))[0] == date(2026, 9, 1)

    def test_labels(self):
        assert period_label("monthly", date(2026, 8, 1), date(2026, 8, 31)) == "August"
        assert period_label("yearly", date(2026, 1, 1), date(2026, 12, 31)) == "2026"
        assert period_label("every_3_months", date(2026, 7, 1), date(2026, 9, 30)) == "Jul–Sep"


# ── building ─────────────────────────────────────────────────────────────


async def test_monthly_recap_built_at_the_boundary(hass, clock):
    coord = await _make(hass)
    clock(date(2026, 9, 1))
    await coord.async_run_recaps(date(2026, 9, 1))  # monthly (the default) on since 1 Sep

    for day in (3, 4, 5, 6, 12, 12, 12):
        _done(coord, "Malia", date(2026, 9, day))
    _done(coord, "Malia", date(2026, 9, 7), chore=coord.other, points=5)
    _done(coord, "Malia", date(2026, 9, 8), approved=False)  # pending: not counted
    coord.storage.add_points_transaction(
        PointsTransaction(
            child_id=coord.kids["Malia"], points=15, reason="Bonus: helping", created_at=_at(date(2026, 9, 12))
        )
    )
    coord.storage.add_points_transaction(
        PointsTransaction(
            child_id=coord.kids["Malia"], points=50, reason="Gift from Vaiha", created_at=_at(date(2026, 9, 12))
        )
    )

    clock(date(2026, 9, 30))
    assert await coord.async_run_recaps(date(2026, 9, 30)) == []

    clock(date(2026, 10, 1))
    built = await coord.async_run_recaps(date(2026, 10, 1))
    mine = [r for r in built if r["child_id"] == coord.kids["Malia"]]
    assert len(mine) == 1
    recap = mine[0]
    assert (recap["frequency"], recap["start"], recap["end"]) == ("monthly", "2026-09-01", "2026-09-30")
    assert recap["chores"] == 8
    assert recap["chore_points"] == 75
    assert recap["bonus_points"] == 15  # the gift isn't earned
    assert recap["points"] == 90
    assert recap["days_active"] == 6
    assert recap["top_chore"] == {"name": "Feed the cat", "icon": "mdi:cat", "count": 7}
    assert recap["streak"] == {"days": 5, "start": "2026-09-03", "end": "2026-09-07"}
    assert recap["best_day"]["date"] == "2026-09-12"
    assert recap["best_day"]["chores"] == 3
    assert [n for _, n in recap["bars"]] == [5, 3, 0, 0, 0]
    assert recap["dow"][5] == 4  # Saturdays 5 and 12 September
    assert recap["notified"] is False

    # Idempotent: the same boundary is never built twice.
    assert await coord.async_run_recaps(date(2026, 10, 1)) == []


async def test_turning_a_frequency_on_does_not_back_fill(hass, clock):
    coord = await _make(hass, names=("Malia",))
    _done(coord, "Malia", date(2026, 8, 10))
    clock(date(2026, 9, 15))
    coord.storage.set_setting("recap_frequencies", ["weekly", "monthly"])
    await coord.async_recap_settings_changed()
    # August and the earlier September weeks are history already.
    assert await coord.async_run_recaps(date(2026, 9, 15)) == []
    built = await coord.async_run_recaps(date(2026, 9, 21))
    assert [(r["frequency"], r["start"]) for r in built] == [("weekly", "2026-09-14")]


async def test_catch_up_after_downtime(hass, clock):
    coord = await _make(hass, names=("Malia",))
    clock(date(2026, 9, 1))
    coord.storage.set_setting("recap_frequencies", ["weekly"])
    await coord.async_recap_settings_changed()
    await coord.async_run_recaps(date(2026, 9, 1))
    # HA off from 5 to 23 September: every missed week is built at startup.
    clock(date(2026, 9, 23))
    built = await coord.async_run_recaps(date(2026, 9, 23))
    assert [r["start"] for r in built] == ["2026-08-31", "2026-09-07", "2026-09-14"]
    assert await coord.async_run_recaps(date(2026, 9, 23)) == []


async def test_custom_override_and_off(hass, clock):
    coord = await _make(hass)
    clock(date(2026, 9, 1))
    coord.storage.set_setting("recap_child_frequencies", {coord.kids["Vaiha"]: []})
    await coord.async_recap_settings_changed()
    assert coord.recap_frequencies_for(coord.kids["Malia"]) == ["monthly"]  # default for new installs
    assert coord.recap_frequencies_for(coord.kids["Vaiha"]) == []
    built = await coord.async_run_recaps(date(2026, 10, 1))
    assert {r["child_id"] for r in built} == {coord.kids["Malia"]}


async def test_ledger_outlives_history_pruning(hass, clock):
    """A yearly recap still counts January after completions were pruned."""
    coord = await _make(hass, names=("Malia",))
    clock(date(2026, 1, 1))
    coord.storage.set_setting("recap_frequencies", ["yearly"])
    await coord.async_recap_settings_changed()
    _done(coord, "Malia", date(2026, 1, 5))
    _done(coord, "Malia", date(2026, 1, 6))
    clock(date(2026, 2, 1))
    await coord.async_run_recaps(date(2026, 2, 1))
    coord.storage.replace_completions([])  # history pruned
    _done(coord, "Malia", date(2026, 12, 30))
    clock(date(2027, 1, 1))
    built = await coord.async_run_recaps(date(2027, 1, 1))
    assert built[0]["chores"] == 3
    assert built[0]["streak"]["days"] == 2


async def test_late_approval_lands_on_the_day_it_was_done(hass, clock):
    coord = await _make(hass, names=("Malia",))
    clock(date(2026, 9, 1))
    await coord.async_run_recaps(date(2026, 9, 1))
    _done(coord, "Malia", date(2026, 9, 28), approved=False)
    await coord.async_run_recaps(date(2026, 9, 29))
    for comp in coord.storage.get_completions():
        comp.approved = True
        coord.storage.update_completion(comp)
    built = await coord.async_run_recaps(date(2026, 10, 1))
    assert built[0]["chores"] == 1


async def test_comparison_uses_previous_recap_or_nothing(hass, clock):
    coord = await _make(hass, names=("Malia",))
    clock(date(2026, 9, 1))
    await coord.async_run_recaps(date(2026, 9, 1))  # ledger starts 31 Aug: August unknown
    for day in (2, 3):
        _done(coord, "Malia", date(2026, 9, day))
    first = (await coord.async_run_recaps(date(2026, 10, 1)))[0]
    assert first["previous"] is None
    _done(coord, "Malia", date(2026, 10, 9))
    second = (await coord.async_run_recaps(date(2026, 11, 1)))[0]
    assert second["previous"]["chores"] == 2
    assert second["previous"]["start"] == "2026-09-01"


async def test_badges_and_rewards_in_the_period(hass, clock):
    coord = await _make(hass, names=("Malia",))
    clock(date(2026, 9, 1))
    await coord.async_run_recaps(date(2026, 9, 1))
    kid = coord.kids["Malia"]
    badge = Badge(name="Early Bird", icon="mdi:weather-sunset-up")
    coord.storage.add_badge(badge)
    coord.storage.add_awarded_badge(AwardedBadge(child_id=kid, badge_id=badge.id, earned_at=_at(date(2026, 9, 9))))
    coord.storage.add_awarded_badge(
        AwardedBadge(child_id=kid, badge_id=badge.id, earned_at=_at(date(2026, 9, 9)), silent=True)
    )
    reward = Reward(name="Cinema trip", cost=300)
    coord.storage.add_reward(reward)
    coord.storage.add_reward_claim(
        RewardClaim(
            reward_id=reward.id, child_id=kid, claimed_at=_at(date(2026, 9, 20)), approved=True, approved_cost=280
        )
    )
    coord.storage.add_reward_claim(RewardClaim(reward_id=reward.id, child_id=kid, claimed_at=_at(date(2026, 9, 21))))
    recap = (await coord.async_run_recaps(date(2026, 10, 1)))[0]
    assert recap["badges"] == [{"name": "Early Bird", "icon": "mdi:weather-sunset-up"}]
    assert recap["rewards"] == [{"name": "Cinema trip", "cost": 280, "icon": "mdi:gift"}]


async def test_retention_and_deleted_children(hass, clock):
    coord = await _make(hass)
    clock(date(2025, 1, 1))
    await coord.async_run_recaps(date(2025, 1, 1))
    await coord.async_run_recaps(date(2025, 2, 1))
    assert len(coord.storage.data["recaps"]) == 2
    coord.storage.set_setting("recap_retention", "1y")
    clock(date(2026, 3, 1))
    await coord.async_run_recaps(date(2026, 3, 1))
    assert all(r["start"] >= "2025-03-01" for r in coord.storage.data["recaps"])
    coord.storage.remove_child(coord.kids["Vaiha"])
    await coord.async_run_recaps(date(2026, 3, 2))
    assert {r["child_id"] for r in coord.storage.data["recaps"]} == {coord.kids["Malia"]}


async def test_preview_is_throw_away(hass, clock):
    coord = await _make(hass, names=("Malia",))
    clock(datetime(2026, 9, 27, 12, 0, tzinfo=UTC))
    _done(coord, "Malia", date(2026, 9, 27))  # today counts in a preview
    _done(coord, "Malia", date(2026, 8, 1))  # outside the 30 days
    first = await coord.async_build_recap_preview(coord.kids["Malia"])
    assert (first["start"], first["end"], first["chores"]) == ("2026-08-29", "2026-09-27", 1)
    assert first["preview"] is True and first["previous"] is None
    second = await coord.async_build_recap_preview(coord.kids["Malia"])
    listed = coord.recaps_for_child(coord.kids["Malia"])
    assert [r["id"] for r in listed] == [second["id"]]
    # Never announced, and gone after a day.
    assert await coord.async_send_recap_notifications() == 0
    clock(datetime(2026, 9, 28, 13, 0, tzinfo=UTC))
    assert coord.recaps_for_child(coord.kids["Malia"]) == []
    with pytest.raises(ValueError):
        await coord.async_build_recap_preview("nobody")


async def test_longest_period_first(hass, clock):
    coord = await _make(hass, names=("Malia",))
    clock(date(2026, 9, 1))
    coord.storage.set_setting("recap_frequencies", ["weekly", "monthly", "every_3_months", "yearly"])
    await coord.async_recap_settings_changed()
    built = await coord.async_run_recaps(date(2026, 10, 1))
    assert {r["frequency"] for r in built} == {"weekly", "monthly", "every_3_months"}
    listed = [r["frequency"] for r in coord.recaps_for_child(coord.kids["Malia"])]
    assert listed[:2] == ["every_3_months", "monthly"]


# ── announcing ───────────────────────────────────────────────────────────


async def _ready(hass, clock):
    coord = await _make(hass)
    clock(date(2026, 9, 1))
    coord.storage.data["children"][0]["notify_service"] = "notify.mobile_app_malia"
    parent = ParentRecipient(name="John", notify_service="notify.mobile_app_john")
    coord.storage.upsert_parent_recipient(parent)
    await coord.async_recap_settings_changed()
    clock(date(2026, 10, 1))
    await coord.async_run_recaps(date(2026, 10, 1))
    clock(datetime(2026, 10, 1, 8, 0, tzinfo=UTC))
    hass.services.async_call.reset_mock()
    hass.bus.async_fire.reset_mock()
    return coord


async def test_one_push_per_child_one_grouped_parent_message(hass, clock):
    coord = await _ready(hass, clock)
    assert await coord.async_send_recap_notifications() == 2

    calls = [c.args for c in hass.services.async_call.call_args_list]
    by_service = {c[1]: c[2] for c in calls}
    assert set(by_service) == {"mobile_app_malia", "mobile_app_john"}
    assert by_service["mobile_app_malia"]["message"] == "✨ Your September recap is ready, Malia! Tap to watch it."
    assert by_service["mobile_app_malia"]["data"]["tag"] == f"taskmate_recap_{coord.kids['Malia']}"
    assert (
        by_service["mobile_app_john"]["message"]
        == "✨ September recaps are ready for Malia and Vaiha. Tap to see them."
    )
    # No stats and no image in the push.
    assert "image" not in by_service["mobile_app_malia"]["data"]

    events = [c.args for c in hass.bus.async_fire.call_args_list if c.args[0] == "taskmate_recap_ready"]
    assert [e[1]["child_id"] for e in events] == [coord.kids["Malia"], coord.kids["Vaiha"]]
    assert events[0][1]["recaps"][0]["frequency"] == "monthly"

    hass.services.async_call.reset_mock()
    assert await coord.async_send_recap_notifications() == 0
    assert hass.services.async_call.call_count == 0


async def test_switches_and_quiet_hours(hass, clock):
    coord = await _ready(hass, clock)
    coord.storage.set_setting("recap_notify_parents", False)
    coord.storage.data["children"][0]["quiet_hours_start"] = "07:00"
    coord.storage.data["children"][0]["quiet_hours_end"] = "09:00"
    await coord.async_send_recap_notifications()
    assert hass.services.async_call.call_count == 0
    # The event still fires for automations.
    assert any(c.args[0] == "taskmate_recap_ready" for c in hass.bus.async_fire.call_args_list)


async def test_master_off_fires_event_only(hass, clock):
    coord = await _ready(hass, clock)
    coord.storage.set_notification_master("recap_ready", False)
    await coord.async_send_recap_notifications()
    assert hass.services.async_call.call_count == 0
    assert any(c.args[0] == "taskmate_recap_ready" for c in hass.bus.async_fire.call_args_list)


async def test_unticked_route_stays_unticked(hass, clock):
    coord = await _ready(hass, clock)
    from custom_components.taskmate.models import NotificationRoute

    rid = f"child:{coord.kids['Malia']}"
    coord.storage.set_notification_route("recap_ready", rid, NotificationRoute(enabled=False))
    coord.ensure_recap_routes()
    assert coord.storage.get_notification_config("recap_ready").routes[rid].enabled is False


async def test_stale_announcements_are_dropped(hass, clock):
    coord = await _ready(hass, clock)
    clock(datetime(2026, 10, 20, 8, 0, tzinfo=UTC))
    assert await coord.async_send_recap_notifications() == 0
    assert all(r["notified"] for r in coord.storage.data["recaps"])


# ── websocket ────────────────────────────────────────────────────────────


def _conn(user_id="u-kid", admin=False):
    connection = MagicMock()
    connection.user = SimpleNamespace(id=user_id, is_admin=admin)
    return connection


async def test_ws_list_and_get(hass, clock):
    from custom_components.taskmate.const import DOMAIN

    coord = await _ready(hass, clock)
    hass.data = {DOMAIN: {"recap_test": coord}}
    kid = coord.kids["Malia"]
    connection = _conn()
    await wsr.ws_recaps_list(hass, connection, {"id": 1, "type": wsr.WS_RECAPS_LIST, "child_id": kid})
    result = connection.send_result.call_args.args[1]
    assert [r["frequency"] for r in result["recaps"]] == ["monthly"]
    assert "bars" not in result["recaps"][0]  # the list is summaries only
    assert result["upcoming"][0]["ready_on"] == "2026-11-01"

    recap_id = result["recaps"][0]["id"]
    connection = _conn()
    await wsr.ws_recaps_get(
        hass, connection, {"id": 2, "type": wsr.WS_RECAPS_GET, "child_id": kid, "recap_id": recap_id}
    )
    recap = connection.send_result.call_args.args[1]["recap"]
    assert recap["bars"] and "notified" not in recap


async def test_ws_linked_child_rule(hass, clock):
    from custom_components.taskmate.const import DOMAIN

    coord = await _ready(hass, clock)
    hass.data = {DOMAIN: {"recap_test": coord}}
    coord.storage.data["children"][1]["linked_user_id"] = "u-vaiha"
    connection = _conn("u-vaiha")
    await wsr.ws_recaps_list(hass, connection, {"id": 3, "type": wsr.WS_RECAPS_LIST, "child_id": coord.kids["Malia"]})
    assert connection.send_error.called
    assert not connection.send_result.called


async def test_ws_compare_toggle_hides_previous(hass, clock):
    from custom_components.taskmate.const import DOMAIN

    coord = await _ready(hass, clock)
    hass.data = {DOMAIN: {"recap_test": coord}}
    recap = coord.storage.data["recaps"][0]
    recap["previous"] = {"chores": 1, "points": 1, "streak": 1, "days_active": 1}
    coord.storage.set_setting("recap_compare", False)
    connection = _conn()
    await wsr.ws_recaps_get(
        hass,
        connection,
        {"id": 4, "type": wsr.WS_RECAPS_GET, "child_id": recap["child_id"], "recap_id": recap["id"]},
    )
    assert connection.send_result.call_args.args[1]["recap"]["previous"] is None


async def test_ws_preview_is_admin_only(hass, clock):
    from custom_components.taskmate.const import DOMAIN

    coord = await _make(hass, names=("Malia",))
    clock(date(2026, 9, 27))
    hass.data = {DOMAIN: {"recap_test": coord}}
    msg = {"id": 5, "type": wsr.WS_RECAPS_PREVIEW, "child_id": coord.kids["Malia"]}
    connection = _conn(admin=False)
    await wsr.ws_recaps_preview(hass, connection, msg)
    assert connection.send_error.called
    connection = _conn(admin=True)
    await wsr.ws_recaps_preview(hass, connection, msg)
    assert connection.send_result.call_args.args[1]["recap"]["preview"] is True


def test_settings_validators():
    assert ws._validate_recap_frequencies(["yearly", "weekly"]) == ["weekly", "yearly"]
    with pytest.raises(vol.Invalid):
        ws._validate_recap_frequencies(["fortnightly"])
    assert ws._validate_recap_child_frequencies({"a": ["monthly"], "b": []}) == {"a": ["monthly"], "b": []}
    with pytest.raises(vol.Invalid):
        ws._validate_recap_child_frequencies({"a": "monthly"})
    for key in (
        "recap_frequencies",
        "recap_child_frequencies",
        "recap_notify_children",
        "recap_notify_parents",
        "recap_send_time",
        "recap_retention",
        "recap_compare",
    ):
        assert key in ws._SUBKEY_SETTINGS
        assert any(getattr(k, "schema", k) == key for k in ws._UPDATE_SETTINGS_SCHEMA)


def test_recap_ready_is_a_registered_notification_type():
    from custom_components.taskmate.coord_notifications import NOTIFICATION_TYPES_BY_ID

    meta = NOTIFICATION_TYPES_BY_ID["recap_ready"]
    assert meta.audience == "both"
    assert not meta.actionable


def test_schedule_lists_every_frequency(hass):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = SimpleNamespace(config=SimpleNamespace(country="US"))
    sched = coord.recap_schedule(date(2026, 9, 27))
    assert sched["week_start"] == 6
    assert sched["next"]["weekly"] == "2026-10-04"
    assert sched["next"]["every_9_months"] == "2026-10-01"
    assert sched["next"]["yearly"] == "2027-01-01"
    assert date.fromisoformat(sched["next"]["monthly"]) - timedelta(days=1) == date(2026, 9, 30)
