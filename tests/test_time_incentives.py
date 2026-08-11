"""Tests for chore early-bonus / late-penalty by completion time."""

from __future__ import annotations

import datetime as dt
from unittest.mock import patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Chore

UTC = dt.timezone.utc


def _coord():
    return object.__new__(TaskMateCoordinator)


def _at(h, m):
    return dt.datetime(2026, 6, 17, h, m, tzinfo=UTC)


def test_no_due_time_returns_base():
    c = Chore(name="A", due_time="", early_bonus=5, late_penalty=5)
    with patch("homeassistant.util.dt.as_local", side_effect=lambda d: d):
        assert _coord()._apply_time_adjustment(c, 10, _at(9, 0)) == 10


def test_early_gets_bonus():
    c = Chore(name="A", due_time="08:00", early_bonus=5, late_penalty=3)
    with patch("homeassistant.util.dt.as_local", side_effect=lambda d: d):
        assert _coord()._apply_time_adjustment(c, 10, _at(7, 30)) == 15


def test_exactly_on_time_counts_as_early():
    c = Chore(name="A", due_time="08:00", early_bonus=5, late_penalty=3)
    with patch("homeassistant.util.dt.as_local", side_effect=lambda d: d):
        assert _coord()._apply_time_adjustment(c, 10, _at(8, 0)) == 15


def test_late_gets_penalty():
    c = Chore(name="A", due_time="08:00", early_bonus=5, late_penalty=3)
    with patch("homeassistant.util.dt.as_local", side_effect=lambda d: d):
        assert _coord()._apply_time_adjustment(c, 10, _at(9, 0)) == 7


def test_late_penalty_floors_at_zero():
    c = Chore(name="A", due_time="08:00", early_bonus=0, late_penalty=50)
    with patch("homeassistant.util.dt.as_local", side_effect=lambda d: d):
        assert _coord()._apply_time_adjustment(c, 10, _at(9, 0)) == 0


def test_bad_due_time_returns_base():
    c = Chore(name="A", due_time="oops", early_bonus=5, late_penalty=5)
    with patch("homeassistant.util.dt.as_local", side_effect=lambda d: d):
        assert _coord()._apply_time_adjustment(c, 10, _at(9, 0)) == 10


def test_round_trips_serialization():
    c = Chore(name="A", due_time="07:30", early_bonus=4, late_penalty=6)
    r = Chore.from_dict(c.to_dict())
    assert r.due_time == "07:30" and r.early_bonus == 4 and r.late_penalty == 6
