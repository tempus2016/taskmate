"""Tests for the native per-child calendar platform (#529).

Each ``calendar.taskmate_<child>`` entity derives events live from the chore
recurrence/assignment engine + ``_is_child_on_vacation``. These tests drive a
real coordinator (mocked storage) so the actual scheduling logic runs, and
exercise the calendar's event builder directly.
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

from custom_components.taskmate.calendar import (
    TaskMateCalendar,
    _chore_applies_to_child,
)
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore


def _coord(children, chores, settings=None) -> TaskMateCoordinator:
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    _settings = settings or {}
    by_id = {c.id: c for c in children}
    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d="": _settings.get(k, d))
    storage.get_children = MagicMock(return_value=children)
    storage.get_child = MagicMock(side_effect=lambda cid: by_id.get(cid))
    storage.get_chores = MagicMock(return_value=chores)
    coord.storage = storage
    return coord


def _cal(coord, child) -> TaskMateCalendar:
    cal = object.__new__(TaskMateCalendar)
    cal.coordinator = coord
    cal._child_id = child.id
    cal._entry = MagicMock()
    return cal


# A Monday in June 2026 (2026-06-22 is a Monday).
MON = date(2026, 6, 22)
TUE = date(2026, 6, 23)


class TestChoreApplies:
    def test_specific_day_match(self):
        c = Child(name="A")
        chore = Chore(name="Bins", schedule_mode="specific_days", due_days=["monday"])
        coord = _coord([c], [chore])
        assert _chore_applies_to_child(coord, chore, c.id, MON) is True
        assert _chore_applies_to_child(coord, chore, c.id, TUE) is False

    def test_empty_due_days_is_every_day(self):
        c = Child(name="A")
        chore = Chore(name="Daily", schedule_mode="specific_days", due_days=[])
        coord = _coord([c], [chore])
        assert _chore_applies_to_child(coord, chore, c.id, MON) is True
        assert _chore_applies_to_child(coord, chore, c.id, TUE) is True

    def test_assigned_to_restricts(self):
        a, b = Child(name="A"), Child(name="B")
        chore = Chore(name="Dishes", due_days=[], assigned_to=[a.id])
        coord = _coord([a, b], [chore])
        assert _chore_applies_to_child(coord, chore, a.id, MON) is True
        assert _chore_applies_to_child(coord, chore, b.id, MON) is False

    def test_disabled_and_unassigned_excluded(self):
        c = Child(name="A")
        off = Chore(name="Off", due_days=[], enabled=False)
        un = Chore(name="Un", due_days=[], assignment_mode="unassigned")
        coord = _coord([c], [off, un])
        assert _chore_applies_to_child(coord, off, c.id, MON) is False
        assert _chore_applies_to_child(coord, un, c.id, MON) is False


class TestBuildEvents:
    def test_timed_vs_all_day(self):
        c = Child(name="A")
        timed = Chore(name="Make bed", due_days=[], time_category="morning")
        anytime = Chore(name="Tidy", due_days=[], time_category="anytime")
        coord = _coord([c], [timed, anytime])
        cal = _cal(coord, c)
        evs = cal._build_events(c, MON, MON)
        by_summary = {e.summary: e for e in evs}
        assert isinstance(by_summary["Make bed"].start, datetime)  # timed
        assert by_summary["Make bed"].start.tzinfo is not None
        assert isinstance(by_summary["Tidy"].start, date)
        assert not isinstance(by_summary["Tidy"].start, datetime)  # all-day

    def test_per_child_isolation(self):
        a, b = Child(name="A"), Child(name="B")
        chore_b = Chore(name="B chore", due_days=[], assigned_to=[b.id])
        coord = _coord([a, b], [chore_b])
        cal_a = _cal(coord, a)
        assert cal_a._build_events(a, MON, MON) == []
        cal_b = _cal(coord, b)
        assert [e.summary for e in cal_b._build_events(b, MON, MON)] == ["B chore"]

    def test_away_coalesced_and_hides_chores(self):
        c = Child(name="A")
        daily = Chore(name="Daily", due_days=[])
        vac = [{"id": "v1", "name": "Summer", "start": "2026-06-24", "end": "2026-06-26"}]
        coord = _coord([c], [daily], {"vacation_periods": vac})
        cal = _cal(coord, c)
        evs = cal._build_events(c, date(2026, 6, 22), date(2026, 6, 28))

        away = [e for e in evs if e.summary.startswith("Away")]
        assert len(away) == 1  # three away days coalesced into one block
        assert away[0].summary == "Away — Summer"
        assert away[0].start == date(2026, 6, 24)
        assert away[0].end == date(2026, 6, 27)  # exclusive end

        chore_days = {e.start for e in evs if e.summary == "Daily"}
        # present outside the vacation, absent inside it
        assert date(2026, 6, 23) in chore_days
        assert date(2026, 6, 27) in chore_days
        assert date(2026, 6, 24) not in chore_days
        assert date(2026, 6, 25) not in chore_days

    def test_away_without_name_falls_back(self):
        c = Child(name="A")
        vac = [{"id": "v1", "name": "", "start": "2026-06-24", "end": "2026-06-24"}]
        coord = _coord([c], [], {"vacation_periods": vac})
        cal = _cal(coord, c)
        evs = cal._build_events(c, date(2026, 6, 24), date(2026, 6, 24))
        assert len(evs) == 1
        assert evs[0].summary == "Away"
