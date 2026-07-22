"""Friction report (#680).

Which chores aren't working, and what to do about each. Built only from
signals TaskMate actually retains — rejections delete the completion and
resolved mandatory misses are removed, so neither can be counted.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

from homeassistant.util import dt as dt_util

from custom_components.taskmate.coord_reports import (
    FRICTION_DEAD_RATE,
    FRICTION_STRUGGLING_RATE,
)
from custom_components.taskmate.models import Chore, MandatoryMiss

from .test_coordinator_logic import _make_coord


def _completion(chore_id, *, days_ago=0, approved=True):
    comp = MagicMock()
    comp.chore_id = chore_id
    comp.child_id = "kid1"
    comp.approved = approved
    comp.bonus_subtask_id = ""
    comp.points_awarded = 5
    comp.completed_at = dt_util.now() - timedelta(days=days_ago)
    return comp


def _coord(chores=(), completions=(), last_completed=None, misses=()):
    coord = _make_coord(completions=list(completions))
    coord.storage.get_chores = MagicMock(return_value=list(chores))
    coord.storage.get_completions = MagicMock(return_value=list(completions))
    coord.storage.get_mandatory_misses = MagicMock(return_value=list(misses))
    coord.storage.data = {"last_completed": last_completed or {}}
    return coord


def _lc(chore_id, days_ago):
    stamp = (dt_util.now() - timedelta(days=days_ago)).isoformat()
    return {chore_id: {"kid1": {"current": stamp}}}


def _row(report, chore_id):
    return next(r for r in report["chores"] if r["id"] == chore_id)


class TestExpectedOccurrences:
    def test_daily_chore_expects_one_per_day(self):
        coord = _coord()
        chore = Chore(name="Daily", id="a", schedule_mode="specific_days", due_days=[])
        start = date(2026, 1, 1)
        assert coord._expected_occurrences(chore, start, start + timedelta(days=6)) == 7

    def test_specific_days_counts_matching_weekdays(self):
        coord = _coord()
        chore = Chore(name="Mon/Fri", id="a", schedule_mode="specific_days",
                      due_days=["monday", "friday"])
        start = date(2026, 1, 5)  # a Monday
        assert coord._expected_occurrences(chore, start, start + timedelta(days=13)) == 4

    def test_weekly_recurring_over_four_weeks(self):
        coord = _coord()
        chore = Chore(name="Weekly", id="a", schedule_mode="recurring", recurrence="weekly")
        start = date(2026, 1, 1)
        assert coord._expected_occurrences(chore, start, start + timedelta(days=27)) == 4

    def test_one_shot_expects_one(self):
        coord = _coord()
        chore = Chore(name="Once", id="a", schedule_mode="one_shot")
        start = date(2026, 1, 1)
        assert coord._expected_occurrences(chore, start, start + timedelta(days=30)) == 1

    def test_unknown_weekday_names_fall_back_to_daily(self):
        coord = _coord()
        chore = Chore(name="Odd", id="a", schedule_mode="specific_days", due_days=["someday"])
        start = date(2026, 1, 1)
        assert coord._expected_occurrences(chore, start, start + timedelta(days=6)) == 7


class TestVerdicts:
    def test_never_completed_chore(self):
        coord = _coord([Chore(name="Ignored", id="a")])
        row = _row(coord.friction_report(), "a")
        assert row["verdict"] == "never"
        assert row["suggestion"] == "retire"
        assert row["days_since"] is None

    def test_well_done_chore_is_fine(self):
        chore = Chore(name="Daily", id="a", schedule_mode="specific_days", due_days=[])
        comps = [_completion("a", days_ago=i) for i in range(30)]
        coord = _coord([chore], comps, _lc("a", 0))
        row = _row(coord.friction_report(30), "a")
        assert row["verdict"] == "fine"
        assert row["suggestion"] == "keep"

    def test_patchy_chore_is_struggling(self):
        chore = Chore(name="Daily", id="a", schedule_mode="specific_days", due_days=[])
        comps = [_completion("a", days_ago=i) for i in range(12)]  # 12/30 = 40%
        coord = _coord([chore], comps, _lc("a", 0))
        row = _row(coord.friction_report(30), "a")
        assert row["verdict"] == "struggling"
        assert row["suggestion"] == "reprice"

    def test_barely_done_chore_is_stalling(self):
        chore = Chore(name="Daily", id="a", points=10, schedule_mode="specific_days", due_days=[])
        comps = [_completion("a", days_ago=i) for i in range(3)]  # 3/30 = 10%
        coord = _coord([chore], comps, _lc("a", 0))
        row = _row(coord.friction_report(30), "a")
        assert row["verdict"] == "stalling"

    def test_long_dead_chore_is_retired_not_repriced(self):
        """Unpopular and abandoned need different answers."""
        chore = Chore(name="Daily", id="a", schedule_mode="specific_days", due_days=[])
        coord = _coord([chore], [], _lc("a", 90))
        assert _row(coord.friction_report(30), "a")["suggestion"] == "retire"

    def test_cheap_stalling_chore_suggests_a_raise(self):
        chore = Chore(name="Daily", id="a", points=2, schedule_mode="specific_days", due_days=[])
        coord = _coord([chore], [_completion("a", days_ago=1)], _lc("a", 1))
        assert _row(coord.friction_report(30), "a")["suggestion"] == "reprice"

    def test_valuable_stalling_chore_suggests_reassigning(self):
        """If it already pays well, money isn't the problem."""
        chore = Chore(name="Daily", id="a", points=50, schedule_mode="specific_days", due_days=[])
        coord = _coord([chore], [_completion("a", days_ago=1)], _lc("a", 1))
        assert _row(coord.friction_report(30), "a")["suggestion"] == "reassign"

    def test_thresholds_are_the_documented_ones(self):
        assert FRICTION_STRUGGLING_RATE == 0.6
        assert FRICTION_DEAD_RATE == 0.2


class TestScope:
    def test_disabled_chores_are_excluded(self):
        coord = _coord([Chore(name="Off", id="a", enabled=False)])
        assert coord.friction_report()["chores"] == []

    def test_pending_completions_do_not_count_as_done(self):
        chore = Chore(name="Daily", id="a", schedule_mode="specific_days", due_days=[])
        coord = _coord([chore], [_completion("a", approved=False)], _lc("a", 0))
        assert _row(coord.friction_report(30), "a")["completed"] == 0

    def test_last_done_predates_the_window(self):
        """A chore last done months ago must read as stale, not 'never'."""
        chore = Chore(name="Old", id="a", schedule_mode="specific_days", due_days=[])
        coord = _coord([chore], [], _lc("a", 60))
        row = _row(coord.friction_report(30), "a")
        assert row["verdict"] == "stalling"
        assert row["days_since"] == 60

    def test_corrupt_last_completed_is_ignored(self):
        chore = Chore(name="Odd", id="a")
        coord = _coord([chore], [], {"a": {"kid1": {"current": "not a date"}}})
        assert _row(coord.friction_report(), "a")["verdict"] == "never"

    def test_latest_completion_across_children_wins(self):
        chore = Chore(name="Shared", id="a")
        recent = (dt_util.now() - timedelta(days=1)).isoformat()
        old = (dt_util.now() - timedelta(days=40)).isoformat()
        coord = _coord([chore], [], {"a": {"kid1": {"current": old}, "kid2": {"current": recent}}})
        assert _row(coord.friction_report(), "a")["days_since"] == 1


class TestMandatoryMisses:
    def test_outstanding_misses_are_surfaced(self):
        chore = Chore(name="Bins", id="a")
        misses = [
            MandatoryMiss(chore_id="a", child_id="k", due_date="2026-01-01", period_id="anytime"),
            MandatoryMiss(chore_id="a", child_id="k", due_date="2026-01-02", period_id="anytime"),
        ]
        coord = _coord([chore], [], None, misses)
        assert _row(coord.friction_report(), "a")["outstanding_misses"] == 2

    def test_escalated_misses_are_counted_as_chasing(self):
        chore = Chore(name="Bins", id="a")
        misses = [
            MandatoryMiss(chore_id="a", child_id="k", due_date="2026-01-01",
                          period_id="anytime", escalation_stage=3),
            MandatoryMiss(chore_id="a", child_id="k", due_date="2026-01-02",
                          period_id="anytime", escalation_stage=1),
        ]
        coord = _coord([chore], [], None, misses)
        row = _row(coord.friction_report(), "a")
        assert row["outstanding_misses"] == 2
        assert row["needed_chasing"] == 1


class TestShape:
    def test_worst_chores_come_first(self):
        good = Chore(name="Good", id="g", schedule_mode="specific_days", due_days=[])
        never = Chore(name="Never", id="n")
        comps = [_completion("g", days_ago=i) for i in range(30)]
        coord = _coord([good, never], comps, _lc("g", 0))
        assert coord.friction_report(30)["chores"][0]["id"] == "n"

    def test_problem_count_covers_never_and_stalling(self):
        never = Chore(name="Never", id="n")
        good = Chore(name="Good", id="g", schedule_mode="specific_days", due_days=[])
        comps = [_completion("g", days_ago=i) for i in range(30)]
        coord = _coord([never, good], comps, _lc("g", 0))
        assert coord.friction_report(30)["problem_count"] == 1

    def test_report_declares_that_rejections_are_not_tracked(self):
        """So the UI can explain the absence instead of the parent wondering."""
        assert _coord().friction_report()["tracks_rejections"] is False
