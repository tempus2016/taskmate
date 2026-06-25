"""Tests for multi-day calendar projection publishing.

The calendar publishing pipeline writes a chore's assignment to every
configured HA calendar for the next N days (N = calendar_projection_days
setting, default 14). Days are filtered by the chore's schedule so the
HA calendar matches the in-card schedule view.
"""
from __future__ import annotations

import datetime as dt
from datetime import date, timezone

from custom_components.taskmate.models import Child, Chore

from .conftest import dt_util_mock, run_async
from .test_assignment_modes import _coord

UTC = timezone.utc


def test_schedule_helper_specific_days_matches_due_days():
    coord = _coord([Child(name="A")])
    chore = Chore(name="X", schedule_mode="specific_days", due_days=["monday", "wednesday"])
    # 2026-04-20 is a Monday, 21 Tue, 22 Wed, 23 Thu, …
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 20)) is True
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 21)) is False
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 22)) is True
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 23)) is False


def test_schedule_helper_empty_due_days_means_every_day():
    coord = _coord([Child(name="A")])
    chore = Chore(name="X", schedule_mode="specific_days", due_days=[])
    for offset in range(14):
        assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 20) + dt.timedelta(days=offset))


def test_schedule_helper_disabled_chore_never_scheduled():
    coord = _coord([Child(name="A")])
    chore = Chore(name="X", enabled=False, due_days=[])
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 20)) is False


def test_schedule_helper_one_shot_only_on_created_date():
    coord = _coord([Child(name="A")])
    chore = Chore(name="Move sofa", schedule_mode="one_shot", created_date="2026-04-20")
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 20)) is True
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 21)) is False


def test_schedule_helper_every_2_days_respects_anchor():
    coord = _coord([Child(name="A")])
    chore = Chore(
        name="Bin",
        schedule_mode="recurring",
        recurrence="every_2_days",
        recurrence_start="2026-04-20",
    )
    # Days matching anchor + 2k
    for offset in (0, 2, 4, 6, 8):
        assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 20) + dt.timedelta(days=offset))
    # Off-cycle days
    for offset in (1, 3, 5, 7):
        assert not coord._is_chore_scheduled_for_date(
            chore, date(2026, 4, 20) + dt.timedelta(days=offset)
        )


def test_schedule_helper_weekly_recurrence_day_filters_to_single_weekday():
    coord = _coord([Child(name="A")])
    chore = Chore(
        name="Swim",
        schedule_mode="recurring",
        recurrence="weekly",
        recurrence_day="wednesday",
    )
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 22)) is True  # Wed
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 23)) is False  # Thu
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 29)) is True  # next Wed


def test_schedule_helper_created_date_blocks_earlier_days():
    coord = _coord([Child(name="A")])
    chore = Chore(
        name="New",
        schedule_mode="specific_days",
        due_days=[],
        created_date="2026-04-22",
    )
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 20)) is False
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 22)) is True
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 25)) is True


def test_projection_publishes_full_horizon_for_daily_chore():
    a = Child(name="A")
    coord = _coord([a], projection_days=14)
    today = date(2026, 4, 20)
    dt_util_mock._now = dt.datetime.combine(today, dt.time(0, 0, 5), tzinfo=UTC)
    chore = Chore(
        name="Daily",
        assigned_to=[a.id],
        publish_calendar_entities=["calendar.family"],
    )
    run_async(coord._publish_chore_to_calendars(chore, today))
    # One event per day of the 14-day horizon.
    assert coord.hass.services.async_call.await_count == 14
    assert len(chore.publish_calendar_published_dates) == 14
    assert chore.publish_calendar_published_dates[0] == today.isoformat()
    assert chore.publish_calendar_published_dates[-1] == (today + dt.timedelta(days=13)).isoformat()


def test_projection_filters_by_schedule():
    a = Child(name="A")
    coord = _coord([a], projection_days=14)
    today = date(2026, 4, 20)  # Monday
    chore = Chore(
        name="Bin day",
        assigned_to=[a.id],
        schedule_mode="specific_days",
        due_days=["wednesday"],
        publish_calendar_entities=["calendar.bins"],
    )
    run_async(coord._publish_chore_to_calendars(chore, today))
    # 14 days starting Monday → Wed on day-2, day-9. So 2 events.
    assert coord.hass.services.async_call.await_count == 2
    iso = [d.isoformat() for d in (today + dt.timedelta(days=2), today + dt.timedelta(days=9))]
    assert chore.publish_calendar_published_dates == iso


def test_projection_is_idempotent_across_reinvocation():
    a = Child(name="A")
    coord = _coord([a], projection_days=7)
    today = date(2026, 4, 20)
    chore = Chore(
        name="Daily",
        assigned_to=[a.id],
        publish_calendar_entities=["calendar.x"],
    )
    run_async(coord._publish_chore_to_calendars(chore, today))
    first = coord.hass.services.async_call.await_count
    run_async(coord._publish_chore_to_calendars(chore, today))
    assert coord.hass.services.async_call.await_count == first


def test_projection_advances_one_day_per_midnight_tick():
    a = Child(name="A")
    coord = _coord([a], projection_days=7)
    today = date(2026, 4, 20)
    chore = Chore(
        name="Daily",
        assigned_to=[a.id],
        publish_calendar_entities=["calendar.x"],
    )
    run_async(coord._publish_chore_to_calendars(chore, today))
    assert coord.hass.services.async_call.await_count == 7
    # Next day's tick: today-1 drops out of the window, day+7 is added.
    run_async(coord._publish_chore_to_calendars(chore, today + dt.timedelta(days=1)))
    assert coord.hass.services.async_call.await_count == 8
    # Published set reflects [today+1, today+7]; the stale today is pruned.
    assert today.isoformat() not in chore.publish_calendar_published_dates
    assert (today + dt.timedelta(days=7)).isoformat() in chore.publish_calendar_published_dates
    assert len(chore.publish_calendar_published_dates) == 7


def test_projection_alternating_names_correct_child_per_day():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b], projection_days=4)
    today = date(2026, 4, 20)
    chore = Chore(
        name="Dishes",
        assigned_to=[a.id, b.id],
        assignment_mode="alternating",
        assignment_rotation_anchor=today.isoformat(),
        publish_calendar_entities=["calendar.family"],
    )
    run_async(coord._publish_chore_to_calendars(chore, today))
    payloads = [c.args[2] for c in coord.hass.services.async_call.await_args_list]
    summaries = [p["summary"] for p in payloads]
    assert summaries == ["Dishes — A", "Dishes — B", "Dishes — A", "Dishes — B"]


def test_projection_horizon_honors_settings_clamp():
    a = Child(name="A")
    coord = _coord([a], projection_days=500)  # well above the 90-day cap
    today = date(2026, 4, 20)
    chore = Chore(
        name="Daily",
        assigned_to=[a.id],
        publish_calendar_entities=["calendar.x"],
    )
    run_async(coord._publish_chore_to_calendars(chore, today))
    # Horizon is clamped to MAX_CALENDAR_PROJECTION_DAYS=90.
    assert coord.hass.services.async_call.await_count == 90


# ---------------------------------------------------------------------------
# ERR-2: interval recurrences fall back to created_date when no recurrence_start
# ---------------------------------------------------------------------------

def test_schedule_helper_monthly_without_start_uses_created_date():
    coord = _coord([])
    chore = Chore(
        name="Pay allowance",
        schedule_mode="recurring",
        recurrence="monthly",
        created_date="2026-04-10",
    )
    # Projects on the created day-of-month, and the same day next month
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 10)) is True
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 5, 10)) is True
    # but not on other days
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 11)) is False
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 25)) is False


def test_schedule_helper_quarterly_without_start_projects():
    coord = _coord([])
    chore = Chore(
        name="Deep clean",
        schedule_mode="recurring",
        recurrence="every_3_months",
        created_date="2026-01-15",
    )
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 1, 15)) is True
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 15)) is True   # +3 months
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 2, 15)) is False  # +1 month
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 7, 15)) is True   # +6 months


def test_schedule_helper_every_2_days_without_start_uses_created_date():
    coord = _coord([])
    chore = Chore(
        name="Water plants",
        schedule_mode="recurring",
        recurrence="every_2_days",
        created_date="2026-04-20",
    )
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 20)) is True
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 22)) is True
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 21)) is False


def test_schedule_helper_explicit_start_overrides_created_date():
    coord = _coord([])
    # recurrence_start anchors the cadence, not created_date
    chore = Chore(
        name="Bins out",
        schedule_mode="recurring",
        recurrence="monthly",
        created_date="2026-04-01",
        recurrence_start="2026-04-03",
    )
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 3)) is True
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 5, 3)) is True
    # anchored to recurrence_start (3rd), not created_date (1st)
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 1)) is False
    assert coord._is_chore_scheduled_for_date(chore, date(2026, 4, 10)) is False
