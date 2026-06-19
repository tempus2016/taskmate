"""Tests for per-child & calendar-synced vacation / streak pause (issue #525).

Three stacking "away" sources, all routed through
``TaskMateCoordinator._is_child_on_vacation``:

  1. global static ``vacation_periods`` range (covered by test_vacation_mode.py);
  2. global ``vacation_calendar`` entity (family calendar);
  3. per-child opt-in (``pause_streak_when_unavailable``) tied to the child's own
     availability / unavailability sensor — which may be a ``calendar.*`` entity.

While away: the streak is frozen (resumes intact on return, in BOTH reset and
pause modes) and chores are hidden for that child only.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child

UTC = dt.timezone.utc


def _make_coord(settings=None, children=None, states=None) -> TaskMateCoordinator:
    coord = object.__new__(TaskMateCoordinator)
    _settings = settings or {}
    _children = children or []
    _states = states or {}
    by_id = {c.id: c for c in _children}

    hass = MagicMock()
    hass.states.get = MagicMock(
        side_effect=lambda eid: SimpleNamespace(state=_states[eid], attributes={})
        if eid in _states else None
    )
    coord.hass = hass

    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d="": _settings.get(k, d))
    storage.get_children = MagicMock(return_value=_children)
    storage.get_child = MagicMock(side_effect=lambda cid: by_id.get(cid))
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


def _run_check(coord, now_dt):
    import custom_components.taskmate.coord_points as _mod
    with patch.object(_mod.dt_util, "now", return_value=now_dt):
        run(coord._async_check_streaks())


NOW = dt.datetime(2026, 7, 25, 0, 0, 5, tzinfo=UTC)  # a normal (non-static-vacation) day


class TestIsChildOnVacation:
    def test_false_when_nothing_configured(self):
        child = Child(name="A")
        coord = _make_coord(children=[child])
        assert coord._is_child_on_vacation(child) is False

    def test_global_calendar_active_freezes_everyone(self):
        child = Child(name="A")  # not opted in
        coord = _make_coord(
            {"vacation_calendar": "calendar.family"}, [child],
            {"calendar.family": "on"},
        )
        assert coord._is_child_on_vacation(child) is True

    def test_global_calendar_off_does_not_freeze(self):
        child = Child(name="A")
        coord = _make_coord(
            {"vacation_calendar": "calendar.family"}, [child],
            {"calendar.family": "off"},
        )
        assert coord._is_child_on_vacation(child) is False

    def test_broken_calendar_fails_open(self):
        child = Child(name="A")
        coord = _make_coord(
            {"vacation_calendar": "calendar.family"}, [child],
            {"calendar.family": "unavailable"},
        )
        assert coord._is_child_on_vacation(child) is False

    def test_per_child_calendar_via_unavailability(self):
        # Opted-in child whose unavailability entity is a calendar; "on" = away.
        child = Child(
            name="A", pause_streak_when_unavailable=True,
            unavailability_entity="calendar.alice_trips",
        )
        coord = _make_coord(children=[child], states={"calendar.alice_trips": "on"})
        assert coord._is_child_on_vacation(child) is True

    def test_per_child_ignored_when_not_opted_in(self):
        # Same entity, flag off -> availability still gates assignment elsewhere,
        # but it must NOT freeze the streak / hide chores.
        child = Child(
            name="A", pause_streak_when_unavailable=False,
            unavailability_entity="calendar.alice_trips",
        )
        coord = _make_coord(children=[child], states={"calendar.alice_trips": "on"})
        assert coord._is_child_on_vacation(child) is False

    def test_per_child_only_affects_that_child(self):
        away = Child(
            name="Away", pause_streak_when_unavailable=True,
            unavailability_entity="calendar.away",
        )
        home = Child(
            name="Home", pause_streak_when_unavailable=True,
            unavailability_entity="calendar.home",
        )
        coord = _make_coord(
            children=[away, home],
            states={"calendar.away": "on", "calendar.home": "off"},
        )
        assert coord._is_child_on_vacation(away) is True
        assert coord._is_child_on_vacation(home) is False

    def test_none_child_uses_global_only(self):
        coord = _make_coord(
            {"vacation_calendar": "calendar.family"}, [],
            {"calendar.family": "on"},
        )
        assert coord._is_child_on_vacation(None) is True


class TestStreakFreezeOnAway:
    def test_optin_away_freezes_and_marks_paused_reset_mode(self):
        child = Child(
            name="A", current_streak=5, last_completion_date="2026-07-05",
            pause_streak_when_unavailable=True, unavailability_entity="calendar.trip",
        )
        coord = _make_coord({"streak_reset_mode": "reset"}, [child], {"calendar.trip": "on"})
        _run_check(coord, NOW)
        assert child.current_streak == 5          # frozen, not reset
        assert child.streak_paused is True         # will resume on return

    def test_optout_away_resets_normally_reset_mode(self):
        # Flag off + a genuine non-vacation gap -> normal reset.
        child = Child(
            name="A", current_streak=5, last_completion_date="2026-07-22",
            pause_streak_when_unavailable=False, unavailability_entity="calendar.trip",
        )
        coord = _make_coord({"streak_reset_mode": "reset"}, [child], {"calendar.trip": "on"})
        _run_check(coord, NOW)
        assert child.current_streak == 0

    def test_global_calendar_freezes_uninvolved_child(self):
        child = Child(name="A", current_streak=3, last_completion_date="2026-07-05")
        coord = _make_coord(
            {"streak_reset_mode": "reset", "vacation_calendar": "calendar.family"},
            [child], {"calendar.family": "on"},
        )
        _run_check(coord, NOW)
        assert child.current_streak == 3
        assert child.streak_paused is True

    def test_already_paused_streak_resumes_not_resets_on_return(self):
        # Back home (available), but streak_paused was set during the absence.
        # In reset mode a normal gap would reset — but an already-paused streak
        # must be preserved so the next completion resumes it.
        child = Child(
            name="A", current_streak=7, last_completion_date="2026-07-05",
            streak_paused=True,
        )
        coord = _make_coord({"streak_reset_mode": "reset"}, [child])
        _run_check(coord, NOW)
        assert child.current_streak == 7
        assert child.streak_paused is True

    def test_idempotent_no_double_save_while_away(self):
        child = Child(
            name="A", current_streak=5, last_completion_date="2026-07-05",
            pause_streak_when_unavailable=True, unavailability_entity="calendar.trip",
            streak_paused=True,  # already frozen from a previous night
        )
        coord = _make_coord({"streak_reset_mode": "reset"}, [child], {"calendar.trip": "on"})
        _run_check(coord, NOW)
        coord.storage.update_child.assert_not_called()  # nothing changed


class TestChoreHidingWhileAway:
    def test_chore_hidden_for_away_child_only(self):
        from custom_components.taskmate.models import Chore
        away = Child(
            name="Away", pause_streak_when_unavailable=True,
            unavailability_entity="calendar.away",
        )
        home = Child(name="Home")
        coord = _make_coord(
            children=[away, home],
            states={"calendar.away": "on"},
        )
        chore = Chore(name="Tidy room", schedule_mode="specific_days", due_days=[])
        assert coord.is_chore_available_for_child(chore, away.id) is False
        assert coord.is_chore_available_for_child(chore, home.id) is True
