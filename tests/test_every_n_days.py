"""Custom "every N days" recurrence (#1038).

Stored as ``every_<N>_days`` (every_2_days is the N=2 case) so availability,
calendar projection and reports all read one value with no extra field.
"""

from __future__ import annotations

import datetime as dt
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.taskmate.const import recurrence_interval_days, recurrence_period_days
from custom_components.taskmate.models import Child, Chore
from custom_components.taskmate.websocket import _recurrence

from .test_assignment_modes import _coord as _sched_coord
from .test_coordinator_logic import _date, _make_coord
from .test_projection_report import _coord as _report_coord
from .test_projection_report import _for, _today


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("every_2_days", 2),
        ("every_3_days", 3),
        ("every_365_days", 365),
        ("every_1_days", None),
        ("every_366_days", None),
        ("every_n_days", None),
        ("weekly", None),
        ("", None),
        (None, None),
    ],
)
def test_recurrence_interval_days(value, expected):
    assert recurrence_interval_days(value) == expected


def test_recurrence_period_days_uses_the_interval():
    assert recurrence_period_days("every_10_days") == 10
    assert recurrence_period_days("every_2_weeks") == 14
    assert recurrence_period_days("bogus") == 7


def test_ws_validator_rejects_out_of_range_intervals():
    assert _recurrence("every_5_days") == "every_5_days"
    assert _recurrence("weekly") == "weekly"
    for bad in ("every_1_days", "every_400_days", "every_n_days"):
        with pytest.raises(vol.Invalid):
            _recurrence(bad)


def _chore(**kw) -> Chore:
    return Chore(name="Towels", schedule_mode="recurring", recurrence="every_3_days", **kw)


def _available(coord, chore, now_dt) -> bool:
    import custom_components.taskmate.coordinator as _mod

    with patch.object(_mod.dt_util, "now", return_value=now_dt):
        return coord.is_chore_available_for_child(chore, "kid1")


class TestAvailability:
    def test_window_is_n_days_from_last_completion(self):
        coord = _make_coord()
        coord.storage.get_last_completed = MagicMock(return_value={"current": "2024-03-17T12:00:00+00:00"})
        chore = _chore()
        assert _available(coord, chore, _date(2024, 3, 19)) is False  # 2 days
        assert _available(coord, chore, _date(2024, 3, 20)) is True  # 3 days

    def test_anchor_aligns_to_every_nth_day(self):
        coord = _make_coord()
        coord.storage.get_last_completed = MagicMock(return_value={"current": "2024-03-01T12:00:00+00:00"})
        chore = _chore(recurrence_start="2024-03-10")
        assert _available(coord, chore, _date(2024, 3, 16)) is True  # anchor + 6
        assert _available(coord, chore, _date(2024, 3, 17)) is False  # anchor + 7

    def test_future_anchor_defers_first_occurrence(self):
        coord = _make_coord()
        coord.storage.get_last_completed = MagicMock(return_value={})
        chore = _chore(recurrence_start="2024-03-25")
        assert _available(coord, chore, _date(2024, 3, 20)) is False


def test_calendar_projection_falls_on_every_nth_day():
    coord = _sched_coord([Child(name="A")])
    chore = Chore(name="Plant", schedule_mode="recurring", recurrence="every_5_days", recurrence_start="2026-04-20")
    start = date(2026, 4, 20)
    on = [o for o in range(16) if coord._is_chore_scheduled_for_date(chore, start + dt.timedelta(days=o))]
    assert on == [0, 5, 10, 15]


def test_projection_report_counts_every_nth_day():
    chore = Chore(
        name="Plant",
        id="c",
        points=5,
        schedule_mode="recurring",
        recurrence="every_3_days",
        recurrence_start=_today().isoformat(),
    )
    # days 0, 3, 6 of a 7-day window
    assert _for(_report_coord([chore]).projection_report(7), "a")["chores"] == 3


def test_falls_on_without_anchor_uses_the_interval():
    coord = _report_coord()
    chore = Chore(name="Rec", id="c", schedule_mode="recurring", recurrence="every_4_days")
    today = _today()
    assert coord._chore_falls_on(chore, today) is True
    assert coord._chore_falls_on(chore, today + timedelta(days=2)) is False
    assert coord._chore_falls_on(chore, today + timedelta(days=4)) is True
