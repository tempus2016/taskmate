"""Tests for vacation / pause mode.

A vacation period is an inclusive date range during which chores are paused
(unavailable) and streaks are frozen — a missed day inside a vacation never
breaks a streak. Periods are stored as the ``vacation_periods`` setting.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child
from custom_components.taskmate.websocket import _validate_vacation_periods

UTC = dt.timezone.utc


def _make_coord(settings: dict | None = None, children: list | None = None) -> TaskMateCoordinator:
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.data = {}
    _settings = settings or {}
    _children = children or []
    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d="": _settings.get(k, d))
    storage.get_children = MagicMock(return_value=_children)
    storage.update_child = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    return coord


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


VAC = [{"id": "v1", "name": "Summer", "start": "2026-07-10", "end": "2026-07-20"}]


class TestVacationLookup:
    def test_no_periods(self):
        coord = _make_coord()
        assert coord.get_vacation_periods() == []
        assert coord.active_vacation(date(2026, 7, 15)) is None
        assert coord.is_vacation_day(date(2026, 7, 15)) is False

    def test_inside_range_inclusive_bounds(self):
        coord = _make_coord({"vacation_periods": VAC})
        assert coord.is_vacation_day(date(2026, 7, 10)) is True   # start
        assert coord.is_vacation_day(date(2026, 7, 20)) is True   # end
        assert coord.is_vacation_day(date(2026, 7, 15)) is True   # middle

    def test_outside_range(self):
        coord = _make_coord({"vacation_periods": VAC})
        assert coord.is_vacation_day(date(2026, 7, 9)) is False
        assert coord.is_vacation_day(date(2026, 7, 21)) is False

    def test_active_vacation_returns_period(self):
        coord = _make_coord({"vacation_periods": VAC})
        p = coord.active_vacation(date(2026, 7, 15))
        assert p and p["name"] == "Summer"

    def test_malformed_entries_ignored(self):
        coord = _make_coord({"vacation_periods": [
            {"name": "bad", "start": "not-a-date", "end": "2026-07-20"},
            "garbage",
            VAC[0],
        ]})
        periods = coord.get_vacation_periods()
        assert len(periods) == 1
        assert periods[0]["name"] == "Summer"

    def test_reversed_dates_are_swapped(self):
        coord = _make_coord({"vacation_periods": [
            {"id": "x", "name": "Oops", "start": "2026-07-20", "end": "2026-07-10"},
        ]})
        p = coord.get_vacation_periods()[0]
        assert p["start"] == "2026-07-10"
        assert p["end"] == "2026-07-20"


class TestStreakGapForgiveness:
    def test_no_gap_when_completed_yesterday(self):
        coord = _make_coord()
        today = date(2026, 7, 25)
        assert coord._streak_breaks_after_gap("2026-07-24", today) is False

    def test_break_on_missed_normal_day(self):
        coord = _make_coord()
        today = date(2026, 7, 25)
        # Last completion 3 days ago, no vacation -> missed.
        assert coord._streak_breaks_after_gap("2026-07-22", today) is True

    def test_vacation_gap_is_forgiven(self):
        coord = _make_coord({"vacation_periods": VAC})
        # Last completed the day before vacation; today is the day after it ends.
        today = date(2026, 7, 21)
        assert coord._streak_breaks_after_gap("2026-07-09", today) is False

    def test_partial_vacation_still_breaks_on_normal_missed_day(self):
        coord = _make_coord({"vacation_periods": VAC})
        # Gap includes 2026-07-22..24 which are NOT vacation -> breaks.
        today = date(2026, 7, 25)
        assert coord._streak_breaks_after_gap("2026-07-09", today) is True


class TestStreakCheckFreezes:
    def _run_check(self, coord, now_dt):
        import custom_components.taskmate.coord_points as _mod
        with patch.object(_mod.dt_util, "now", return_value=now_dt):
            run(coord._async_check_streaks())

    def test_no_reset_on_vacation_day(self):
        child = Child(name="A", current_streak=5, last_completion_date="2026-07-05")
        coord = _make_coord({"vacation_periods": VAC, "streak_reset_mode": "reset"}, [child])
        # 2026-07-15 is inside the vacation -> streak frozen (value preserved) and
        # marked paused so it resumes intact on return, even in reset mode.
        self._run_check(coord, dt.datetime(2026, 7, 15, 0, 0, 5, tzinfo=UTC))
        assert child.current_streak == 5
        assert child.streak_paused is True

    def test_reset_resumes_after_vacation_if_normal_day_missed(self):
        child = Child(name="A", current_streak=5, last_completion_date="2026-07-05")
        coord = _make_coord({"vacation_periods": VAC, "streak_reset_mode": "reset"}, [child])
        # Back from holiday and missed 21st onward -> normal miss, resets.
        self._run_check(coord, dt.datetime(2026, 7, 25, 0, 0, 5, tzinfo=UTC))
        assert child.current_streak == 0


class TestValidateVacationPeriods:
    def test_empty_list_ok(self):
        periods, err = _validate_vacation_periods([])
        assert err is None and periods == []

    def test_valid_entry(self):
        periods, err = _validate_vacation_periods([
            {"name": "Trip", "start": "2026-08-01", "end": "2026-08-05"},
        ])
        assert err is None
        assert periods[0]["name"] == "Trip"
        assert periods[0]["id"]  # generated

    def test_reversed_swapped(self):
        periods, err = _validate_vacation_periods([
            {"name": "x", "start": "2026-08-05", "end": "2026-08-01"},
        ])
        assert err is None
        assert periods[0]["start"] == "2026-08-01"
        assert periods[0]["end"] == "2026-08-05"

    def test_bad_date_rejected(self):
        periods, err = _validate_vacation_periods([{"start": "nope", "end": "2026-08-01"}])
        assert periods is None and err

    def test_not_a_list_rejected(self):
        periods, err = _validate_vacation_periods("nope")
        assert periods is None and err

    def test_sorted_by_start(self):
        periods, err = _validate_vacation_periods([
            {"name": "B", "start": "2026-09-01", "end": "2026-09-02"},
            {"name": "A", "start": "2026-08-01", "end": "2026-08-02"},
        ])
        assert err is None
        assert [p["name"] for p in periods] == ["A", "B"]
