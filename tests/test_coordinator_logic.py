"""Tests for the core business logic in TaskMateCoordinator.

We test pure logic methods (streak tracking, milestone bonuses, perfect week,
prune history, recurrence availability) by constructing a coordinator with a
fully mocked storage layer, avoiding any real Home Assistant dependencies.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from datetime import date, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, ChoreCompletion

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date(year: int, month: int, day: int) -> dt.datetime:
    return dt.datetime(year, month, day, 12, 0, 0, tzinfo=UTC)


def _make_child(
    *,
    points: int = 0,
    current_streak: int = 0,
    best_streak: int = 0,
    last_completion_date: str | None = None,
    streak_paused: bool = False,
    streak_milestones_achieved: list | None = None,
    awarded_perfect_weeks: list | None = None,
) -> Child:
    return Child(
        name="Test Child",
        points=points,
        total_points_earned=points,
        current_streak=current_streak,
        best_streak=best_streak,
        last_completion_date=last_completion_date,
        streak_paused=streak_paused,
        streak_milestones_achieved=streak_milestones_achieved or [],
        awarded_perfect_weeks=awarded_perfect_weeks or [],
    )


def _make_coord(
    *,
    settings: dict | None = None,
    children: list | None = None,
    completions: list | None = None,
) -> TaskMateCoordinator:
    """Build a coordinator with mocked storage for unit testing."""
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.data = {}
    coord._unsub_midnight = None
    coord._unsub_prune = None

    _settings = settings or {}
    _children = children or []
    _completions = completions or []

    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d="": _settings.get(k, d))
    storage.get_children = MagicMock(return_value=_children)
    storage.get_completions = MagicMock(return_value=_completions)
    storage.update_child = MagicMock()
    storage.add_points_transaction = MagicMock()
    storage.async_save = AsyncMock()
    # Provide a real _data dict so that async_prune_history (which writes to
    # storage._data["completions"] directly) can be tested without MagicMock absorbing writes.
    storage._data = {"completions": [c.to_dict() for c in _completions]}

    coord.storage = storage
    coord.async_refresh = AsyncMock()
    return coord


def run(coro):
    """Run a coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# parse_milestone_setting
# ---------------------------------------------------------------------------

class TestParseMilestoneSetting:
    def test_empty_string_returns_empty_dict(self):
        result = TaskMateCoordinator.parse_milestone_setting("")
        assert result == {}

    def test_whitespace_only_returns_empty_dict(self):
        result = TaskMateCoordinator.parse_milestone_setting("   ")
        assert result == {}

    def test_valid_single_milestone(self):
        result = TaskMateCoordinator.parse_milestone_setting("7:10")
        assert result == {7: 10}

    def test_valid_multiple_milestones(self):
        result = TaskMateCoordinator.parse_milestone_setting("3:5, 7:10, 14:20")
        assert result == {3: 5, 7: 10, 14: 20}

    def test_whitespace_around_values_handled(self):
        result = TaskMateCoordinator.parse_milestone_setting(" 7 : 10 ")
        assert result == {7: 10}

    def test_missing_colon_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid format"):
            TaskMateCoordinator.parse_milestone_setting("7-10")

    def test_non_integer_days_raises_value_error(self):
        with pytest.raises(ValueError):
            TaskMateCoordinator.parse_milestone_setting("week:10")

    def test_non_integer_points_raises_value_error(self):
        with pytest.raises(ValueError):
            TaskMateCoordinator.parse_milestone_setting("7:lots")

    def test_days_zero_raises_value_error(self):
        with pytest.raises(ValueError, match="at least 1"):
            TaskMateCoordinator.parse_milestone_setting("0:10")

    def test_points_zero_raises_value_error(self):
        with pytest.raises(ValueError, match="at least 1"):
            TaskMateCoordinator.parse_milestone_setting("7:0")

    def test_duplicate_days_raises_value_error(self):
        with pytest.raises(ValueError, match="Duplicate"):
            TaskMateCoordinator.parse_milestone_setting("7:10, 7:20")


# ---------------------------------------------------------------------------
# _award_points — streak tracking
# ---------------------------------------------------------------------------

class TestAwardPointsStreakTracking:
    """dt_util.now() is patched to control the 'current date' seen by _award_points."""

    def _run_award(self, coord, child, points, now_dt, completion_date=None):
        import custom_components.taskmate.coordinator as _mod
        with patch.object(_mod.dt_util, "now", return_value=now_dt):
            run(coord._award_points(child, points, completion_date=completion_date))

    def test_first_completion_sets_streak_to_one(self):
        coord = _make_coord()
        child = _make_child()
        now = _date(2024, 3, 20)
        self._run_award(coord, child, 10, now)
        assert child.current_streak == 1
        assert child.last_completion_date == "2024-03-20"

    def test_completing_same_day_does_not_change_streak(self):
        coord = _make_coord()
        child = _make_child(current_streak=3, last_completion_date="2024-03-20")
        now = _date(2024, 3, 20)
        self._run_award(coord, child, 10, now)
        assert child.current_streak == 3  # unchanged

    def test_consecutive_day_increments_streak(self):
        coord = _make_coord()
        child = _make_child(current_streak=4, last_completion_date="2024-03-19")
        now = _date(2024, 3, 20)
        self._run_award(coord, child, 10, now)
        assert child.current_streak == 5

    def test_missed_day_in_reset_mode_resets_streak(self):
        coord = _make_coord(settings={"streak_reset_mode": "reset"})
        child = _make_child(current_streak=10, last_completion_date="2024-03-17")
        now = _date(2024, 3, 20)  # skipped the 18th and 19th
        self._run_award(coord, child, 10, now)
        assert child.current_streak == 1  # reset then incremented to 1

    def test_missed_day_in_pause_mode_resumes_streak(self):
        coord = _make_coord(settings={"streak_reset_mode": "pause"})
        child = _make_child(
            current_streak=10,
            last_completion_date="2024-03-17",
            streak_paused=True,
        )
        now = _date(2024, 3, 20)
        self._run_award(coord, child, 10, now)
        # Streak should be preserved (not reset), paused flag cleared
        assert child.current_streak == 10
        assert child.streak_paused is False

    def test_best_streak_updates_when_current_exceeds_it(self):
        coord = _make_coord()
        child = _make_child(current_streak=4, best_streak=4, last_completion_date="2024-03-19")
        now = _date(2024, 3, 20)
        self._run_award(coord, child, 10, now)
        assert child.current_streak == 5
        assert child.best_streak == 5

    def test_best_streak_not_reduced(self):
        coord = _make_coord()
        # streak reset from 10 to 1 — best_streak should stay 10
        child = _make_child(current_streak=10, best_streak=10, last_completion_date="2024-03-15")
        now = _date(2024, 3, 20)
        self._run_award(coord, child, 10, now)
        assert child.current_streak == 1
        assert child.best_streak == 10

    def test_points_awarded_to_child(self):
        coord = _make_coord()
        child = _make_child(points=50)
        now = _date(2024, 3, 20)
        self._run_award(coord, child, 10, now)
        assert child.points >= 60  # at least base points added

    def test_total_chores_completed_incremented(self):
        coord = _make_coord()
        child = _make_child()
        now = _date(2024, 3, 20)
        self._run_award(coord, child, 10, now)
        assert child.total_chores_completed == 1


# ---------------------------------------------------------------------------
# _award_points — weekend multiplier
# ---------------------------------------------------------------------------

class TestAwardPointsWeekendMultiplier:
    def _run_award(self, coord, child, points, now_dt, completion_date=None):
        import custom_components.taskmate.coordinator as _mod
        with patch.object(_mod.dt_util, "now", return_value=now_dt):
            run(coord._award_points(child, points, completion_date=completion_date))

    def test_weekday_no_bonus(self):
        # Wednesday 2024-03-20
        coord = _make_coord(settings={"weekend_multiplier": "2.0"})
        child = _make_child(points=0)
        now = _date(2024, 3, 20)  # Wednesday
        self._run_award(coord, child, 10, now)
        assert child.points == 10  # no bonus

    def test_saturday_applies_multiplier(self):
        # Saturday 2024-03-23
        coord = _make_coord(settings={"weekend_multiplier": "2.0"})
        child = _make_child(points=0)
        now = _date(2024, 3, 23)  # Saturday
        self._run_award(coord, child, 10, now, completion_date=date(2024, 3, 23))
        # 10 base + 10 bonus (2x multiplier means +100% = +10 extra)
        assert child.points == 20

    def test_sunday_applies_multiplier(self):
        coord = _make_coord(settings={"weekend_multiplier": "2.0"})
        child = _make_child(points=0)
        now = _date(2024, 3, 24)  # Sunday
        self._run_award(coord, child, 10, now, completion_date=date(2024, 3, 24))
        assert child.points == 20

    def test_multiplier_one_no_bonus(self):
        coord = _make_coord(settings={"weekend_multiplier": "1.0"})
        child = _make_child(points=0)
        now = _date(2024, 3, 23)  # Saturday
        self._run_award(coord, child, 10, now, completion_date=date(2024, 3, 23))
        assert child.points == 10  # multiplier=1 means no extra bonus


# ---------------------------------------------------------------------------
# _award_points — streak milestone bonuses
# ---------------------------------------------------------------------------

class TestAwardPointsMilestoneBonuses:
    def _run_award(self, coord, child, points, now_dt):
        import custom_components.taskmate.coordinator as _mod
        with patch.object(_mod.dt_util, "now", return_value=now_dt):
            run(coord._award_points(child, points))

    def test_milestone_bonus_awarded_on_reaching_threshold(self):
        settings = {
            "streak_milestones_enabled": "true",
            "streak_milestones": "3:5, 7:10",
        }
        coord = _make_coord(settings=settings)
        # Streak is at 2, completing today puts it at 3
        child = _make_child(points=0, current_streak=2, last_completion_date="2024-03-19")
        now = _date(2024, 3, 20)
        self._run_award(coord, child, 10, now)
        # Should have received base 10 + milestone bonus 5 = 15
        assert child.points == 15
        assert 3 in child.streak_milestones_achieved

    def test_milestone_bonus_not_awarded_twice(self):
        settings = {
            "streak_milestones_enabled": "true",
            "streak_milestones": "3:5",
        }
        coord = _make_coord(settings=settings)
        # Streak is already 3, milestone already achieved
        child = _make_child(
            points=0,
            current_streak=3,
            last_completion_date="2024-03-19",
            streak_milestones_achieved=[3],
        )
        now = _date(2024, 3, 20)
        self._run_award(coord, child, 10, now)
        # Only base points, no milestone bonus
        assert child.points == 10

    def test_milestones_cleared_on_streak_reset(self):
        settings = {
            "streak_milestones_enabled": "true",
            "streak_milestones": "3:5, 7:10",
            "streak_reset_mode": "reset",
        }
        coord = _make_coord(settings=settings)
        child = _make_child(
            current_streak=7,
            best_streak=7,
            last_completion_date="2024-03-10",  # 10 days ago → missed
            streak_milestones_achieved=[3, 7],
        )
        now = _date(2024, 3, 20)
        self._run_award(coord, child, 10, now)
        # Streak reset, milestones cleared
        assert child.streak_milestones_achieved == []

    def test_milestones_disabled_no_bonus(self):
        settings = {
            "streak_milestones_enabled": "false",
            "streak_milestones": "3:5",
        }
        coord = _make_coord(settings=settings)
        child = _make_child(current_streak=2, last_completion_date="2024-03-19")
        now = _date(2024, 3, 20)
        self._run_award(coord, child, 10, now)
        assert child.points == 10


# ---------------------------------------------------------------------------
# _async_check_streaks
# ---------------------------------------------------------------------------

class TestCheckStreaks:
    def _run_check(self, coord, now_dt):
        import custom_components.taskmate.coordinator as _mod
        with patch.object(_mod.dt_util, "now", return_value=now_dt):
            run(coord._async_check_streaks())

    def test_no_completions_skipped(self):
        child = _make_child(current_streak=5, last_completion_date=None)
        coord = _make_coord(children=[child])
        now = _date(2024, 3, 20)
        self._run_check(coord, now)
        assert child.current_streak == 5  # untouched

    def test_completed_today_streak_unchanged(self):
        child = _make_child(current_streak=5, last_completion_date="2024-03-20")
        coord = _make_coord(children=[child])
        now = _date(2024, 3, 20)
        self._run_check(coord, now)
        assert child.current_streak == 5

    def test_completed_yesterday_streak_unchanged(self):
        child = _make_child(current_streak=5, last_completion_date="2024-03-19")
        coord = _make_coord(children=[child])
        now = _date(2024, 3, 20)
        self._run_check(coord, now)
        assert child.current_streak == 5

    def test_missed_day_reset_mode_clears_streak(self):
        child = _make_child(current_streak=8, last_completion_date="2024-03-15")
        coord = _make_coord(
            settings={"streak_reset_mode": "reset"},
            children=[child],
        )
        now = _date(2024, 3, 20)
        self._run_check(coord, now)
        assert child.current_streak == 0
        assert child.streak_paused is False

    def test_missed_day_pause_mode_sets_paused_flag(self):
        child = _make_child(current_streak=8, last_completion_date="2024-03-15")
        coord = _make_coord(
            settings={"streak_reset_mode": "pause"},
            children=[child],
        )
        now = _date(2024, 3, 20)
        self._run_check(coord, now)
        # Streak value preserved but flagged as paused
        assert child.current_streak == 8
        assert child.streak_paused is True

    def test_zero_streak_not_modified(self):
        child = _make_child(current_streak=0, last_completion_date="2024-03-10")
        coord = _make_coord(children=[child])
        now = _date(2024, 3, 20)
        self._run_check(coord, now)
        # current_streak was 0, nothing to reset
        coord.storage.update_child.assert_not_called()


# ---------------------------------------------------------------------------
# _async_check_perfect_week
# ---------------------------------------------------------------------------

class TestCheckPerfectWeek:
    def _make_completion(self, child_id: str, date_str: str) -> ChoreCompletion:
        return ChoreCompletion(
            chore_id="chore1",
            child_id=child_id,
            completed_at=dt.datetime.fromisoformat(f"{date_str}T12:00:00+00:00"),
            approved=True,
            points_awarded=10,
        )

    def _run_check(self, coord, now_dt):
        import custom_components.taskmate.coordinator as _mod
        with patch.object(_mod.dt_util, "now", return_value=now_dt):
            run(coord._async_check_perfect_week())

    def test_perfect_week_awards_bonus(self):
        # Today is Monday 2024-03-18; last week = Mon 2024-03-11 … Sun 2024-03-17
        child = _make_child(points=50)
        child.id = "kid1"
        last_week_dates = [
            "2024-03-11", "2024-03-12", "2024-03-13",
            "2024-03-14", "2024-03-15", "2024-03-16", "2024-03-17",
        ]
        completions = [self._make_completion("kid1", d) for d in last_week_dates]

        coord = _make_coord(
            settings={
                "perfect_week_enabled": "true",
                "perfect_week_bonus": "50",
            },
            children=[child],
            completions=completions,
        )
        now = _date(2024, 3, 18)  # Monday
        self._run_check(coord, now)

        assert child.points == 100  # 50 + 50 bonus
        assert "2024-03-11" in child.awarded_perfect_weeks

    def test_perfect_week_not_awarded_twice(self):
        child = _make_child(points=50, awarded_perfect_weeks=["2024-03-11"])
        child.id = "kid1"
        last_week_dates = [
            "2024-03-11", "2024-03-12", "2024-03-13",
            "2024-03-14", "2024-03-15", "2024-03-16", "2024-03-17",
        ]
        completions = [self._make_completion("kid1", d) for d in last_week_dates]

        coord = _make_coord(
            settings={"perfect_week_enabled": "true", "perfect_week_bonus": "50"},
            children=[child],
            completions=completions,
        )
        now = _date(2024, 3, 18)
        self._run_check(coord, now)
        assert child.points == 50  # no bonus awarded again

    def test_incomplete_week_no_bonus(self):
        child = _make_child(points=50)
        child.id = "kid1"
        # Missing Sunday 2024-03-17
        completions = [
            self._make_completion("kid1", d)
            for d in ["2024-03-11", "2024-03-12", "2024-03-13",
                      "2024-03-14", "2024-03-15", "2024-03-16"]
        ]
        coord = _make_coord(
            settings={"perfect_week_enabled": "true", "perfect_week_bonus": "50"},
            children=[child],
            completions=completions,
        )
        now = _date(2024, 3, 18)
        self._run_check(coord, now)
        assert child.points == 50  # unchanged

    def test_feature_disabled_skips_check(self):
        child = _make_child(points=50)
        child.id = "kid1"
        last_week_dates = [
            "2024-03-11", "2024-03-12", "2024-03-13",
            "2024-03-14", "2024-03-15", "2024-03-16", "2024-03-17",
        ]
        completions = [self._make_completion("kid1", d) for d in last_week_dates]
        coord = _make_coord(
            settings={"perfect_week_enabled": "false"},
            children=[child],
            completions=completions,
        )
        now = _date(2024, 3, 18)
        self._run_check(coord, now)
        assert child.points == 50  # no change

    def test_not_monday_skips_check(self):
        child = _make_child(points=50)
        child.id = "kid1"
        coord = _make_coord(
            settings={"perfect_week_enabled": "true", "perfect_week_bonus": "50"},
            children=[child],
            completions=[],
        )
        now = _date(2024, 3, 20)  # Wednesday
        self._run_check(coord, now)
        assert child.points == 50


# ---------------------------------------------------------------------------
# async_prune_history
# ---------------------------------------------------------------------------

class TestPruneHistory:
    def _make_completion(
        self, *, approved: bool, days_old: int, now: dt.datetime
    ) -> ChoreCompletion:
        completed_at = now - dt.timedelta(days=days_old)
        return ChoreCompletion(
            chore_id="chore1",
            child_id="child1",
            completed_at=completed_at,
            approved=approved,
            points_awarded=10 if approved else 0,
        )

    def test_old_approved_completions_pruned(self):
        now = dt.datetime(2024, 3, 20, 12, 0, 0, tzinfo=UTC)
        old_approved = self._make_completion(approved=True, days_old=100, now=now)
        recent_approved = self._make_completion(approved=True, days_old=30, now=now)

        coord = _make_coord(completions=[old_approved, recent_approved])

        import custom_components.taskmate.coordinator as _mod
        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_prune_history(days=90))

        # The coordinator filters via storage._data; verify storage._data was set
        saved_data = coord.storage._data["completions"]
        ids_kept = {c["id"] for c in saved_data}
        assert old_approved.id not in ids_kept
        assert recent_approved.id in ids_kept

    def test_unapproved_completions_always_kept(self):
        now = dt.datetime(2024, 3, 20, 12, 0, 0, tzinfo=UTC)
        old_pending = self._make_completion(approved=False, days_old=200, now=now)
        coord = _make_coord(completions=[old_pending])

        import custom_components.taskmate.coordinator as _mod
        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_prune_history(days=90))

        saved_data = coord.storage._data["completions"]
        ids_kept = {c["id"] for c in saved_data}
        assert old_pending.id in ids_kept

    def test_no_pruning_needed_storage_not_written(self):
        now = dt.datetime(2024, 3, 20, 12, 0, 0, tzinfo=UTC)
        recent = self._make_completion(approved=True, days_old=10, now=now)
        coord = _make_coord(completions=[recent])

        import custom_components.taskmate.coordinator as _mod
        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_prune_history(days=90))

        coord.storage.async_save.assert_not_called()


# ---------------------------------------------------------------------------
# is_chore_available_for_child
# ---------------------------------------------------------------------------

class TestChoreAvailability:
    def _make_recurring_chore(
        self,
        recurrence: str = "weekly",
        recurrence_day: str = "",
        recurrence_start: str = "",
        first_occurrence_mode: str = "available_immediately",
    ) -> Chore:
        return Chore(
            name="Recurring chore",
            schedule_mode="recurring",
            recurrence=recurrence,
            recurrence_day=recurrence_day,
            recurrence_start=recurrence_start,
            first_occurrence_mode=first_occurrence_mode,
        )

    def _run(self, coord, chore, child_id, now_dt):
        import custom_components.taskmate.coordinator as _mod
        with patch.object(_mod.dt_util, "now", return_value=now_dt):
            return coord.is_chore_available_for_child(chore, child_id)

    def test_mode_a_always_available(self):
        coord = _make_coord()
        chore = Chore(name="Specific day chore", schedule_mode="specific_days")
        coord.storage.get_last_completed = MagicMock(return_value={})
        now = _date(2024, 3, 20)
        assert self._run(coord, chore, "kid1", now) is True

    def test_mode_b_never_completed_available_immediately(self):
        coord = _make_coord()
        coord.storage.get_last_completed = MagicMock(return_value={})
        chore = self._make_recurring_chore(first_occurrence_mode="available_immediately")
        now = _date(2024, 3, 20)
        assert self._run(coord, chore, "kid1", now) is True

    def test_mode_b_completed_within_window_not_available(self):
        coord = _make_coord()
        # Last completed 3 days ago, window is 7 days
        coord.storage.get_last_completed = MagicMock(
            return_value={"current": "2024-03-17T12:00:00+00:00"}
        )
        chore = self._make_recurring_chore(recurrence="weekly")
        now = _date(2024, 3, 20)  # 3 days after last completion
        assert self._run(coord, chore, "kid1", now) is False

    def test_mode_b_completed_outside_window_available(self):
        coord = _make_coord()
        # Last completed 8 days ago, window is 7 days
        coord.storage.get_last_completed = MagicMock(
            return_value={"current": "2024-03-12T12:00:00+00:00"}
        )
        chore = self._make_recurring_chore(recurrence="weekly")
        now = _date(2024, 3, 20)  # 8 days after
        assert self._run(coord, chore, "kid1", now) is True

    def test_mode_b_with_recurrence_day_wrong_day_not_available(self):
        coord = _make_coord()
        coord.storage.get_last_completed = MagicMock(
            return_value={"current": "2024-03-13T12:00:00+00:00"}  # 7 days ago
        )
        chore = self._make_recurring_chore(
            recurrence="weekly",
            recurrence_day="friday",  # only available on Fridays
        )
        # 2024-03-20 is a Wednesday — not the target day
        now = _date(2024, 3, 20)
        assert self._run(coord, chore, "kid1", now) is False

    def test_mode_b_with_recurrence_day_correct_day_available(self):
        coord = _make_coord()
        coord.storage.get_last_completed = MagicMock(
            return_value={"current": "2024-03-13T12:00:00+00:00"}  # 7 days ago
        )
        chore = self._make_recurring_chore(
            recurrence="weekly",
            recurrence_day="wednesday",  # 2024-03-20 is a Wednesday
        )
        now = _date(2024, 3, 20)
        assert self._run(coord, chore, "kid1", now) is True

    def test_every_2_days_recurrence(self):
        coord = _make_coord()
        # Last completed yesterday — not yet available (needs 2 days)
        coord.storage.get_last_completed = MagicMock(
            return_value={"current": "2024-03-19T12:00:00+00:00"}
        )
        chore = self._make_recurring_chore(recurrence="every_2_days")
        now = _date(2024, 3, 20)  # only 1 day since last — not available yet
        assert self._run(coord, chore, "kid1", now) is False
