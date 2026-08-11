"""Points projection (#681).

"Show me next week": who gets which chore and what it's worth. A ceiling
rather than a forecast — shared-pool chores are credited to every eligible
child, because the schedule cannot know who will get there first.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

from homeassistant.util import dt as dt_util

from custom_components.taskmate.coord_reports import MAX_PROJECTION_DAYS, PROJECTION_DAYS
from custom_components.taskmate.models import Child, Chore

from .test_coordinator_logic import _make_coord

KIDS = [Child(name="Ella", id="a", points=100), Child(name="Sam", id="b", points=50)]


def _coord(chores=(), children=KIDS, assignments=None):
    coord = _make_coord(children=list(children))
    coord.storage.get_chores = MagicMock(return_value=list(chores))
    coord.storage.get_children = MagicMock(return_value=list(children))
    coord._compute_daily_assignments = MagicMock(return_value=dict(assignments or {}))
    return coord


def _today():
    return dt_util.as_local(dt_util.now()).date()


def _for(report, child_id):
    return next(r for r in report["children"] if r["id"] == child_id)


class TestWindow:
    def test_default_span(self):
        assert _coord().projection_report()["days"] == PROJECTION_DAYS

    def test_span_is_clamped(self):
        coord = _coord()
        assert coord.projection_report(0)["days"] == 1
        assert coord.projection_report(999)["days"] == MAX_PROJECTION_DAYS

    def test_garbage_span_falls_back(self):
        assert _coord().projection_report("soon")["days"] == PROJECTION_DAYS

    def test_day_rows_match_the_span(self):
        assert len(_coord().projection_report(5)["by_day"]) == 5

    def test_starts_today(self):
        assert _coord().projection_report()["start"] == _today().isoformat()


class TestScheduleMatching:
    def test_daily_chore_appears_every_day(self):
        chore = Chore(name="Daily", id="c", points=5, schedule_mode="specific_days", due_days=[])
        report = _coord([chore]).projection_report(3)
        assert _for(report, "a")["chores"] == 3
        assert _for(report, "a")["points"] == 15

    def test_specific_weekday_only_appears_then(self):
        target = _today() + timedelta(days=2)
        chore = Chore(
            name="Weekly", id="c", points=5, schedule_mode="specific_days", due_days=[target.strftime("%A").lower()]
        )
        report = _coord([chore]).projection_report(7)
        assert _for(report, "a")["chores"] == 1

    def test_disabled_chores_are_skipped(self):
        chore = Chore(name="Off", id="c", points=5, enabled=False, schedule_mode="specific_days", due_days=[])
        assert _for(_coord([chore]).projection_report(3), "a")["chores"] == 0

    def test_expired_chore_stops_appearing(self):
        yesterday = (_today() - timedelta(days=1)).isoformat()
        chore = Chore(name="Done", id="c", points=5, schedule_mode="specific_days", due_days=[], expires_on=yesterday)
        assert _for(_coord([chore]).projection_report(3), "a")["chores"] == 0

    def test_one_shot_only_on_its_created_date(self):
        chore = Chore(name="Once", id="c", points=5, schedule_mode="one_shot", created_date=_today().isoformat())
        assert _for(_coord([chore]).projection_report(5), "a")["chores"] == 1

    def test_recurring_every_two_days_from_an_anchor(self):
        chore = Chore(
            name="Rec",
            id="c",
            points=5,
            schedule_mode="recurring",
            recurrence="every_2_days",
            recurrence_start=_today().isoformat(),
        )
        # days 0, 2, 4, 6 of a 7-day window
        assert _for(_coord([chore]).projection_report(7), "a")["chores"] == 4

    def test_recurring_weekly_on_a_named_day(self):
        target = _today() + timedelta(days=3)
        chore = Chore(
            name="Rec",
            id="c",
            points=5,
            schedule_mode="recurring",
            recurrence="weekly",
            recurrence_day=target.strftime("%A").lower(),
        )
        assert _for(_coord([chore]).projection_report(7), "a")["chores"] == 1

    def test_malformed_dates_do_not_crash(self):
        chore = Chore(
            name="Odd", id="c", points=5, schedule_mode="recurring", recurrence="weekly", recurrence_start="not-a-date"
        )
        assert isinstance(_coord([chore]).projection_report(3)["children"], list)


class TestAssignment:
    def test_everyone_chore_credits_the_whole_pool(self):
        """A ceiling: the schedule can't know who gets there first."""
        chore = Chore(
            name="Open", id="c", points=10, assignment_mode="everyone", schedule_mode="specific_days", due_days=[]
        )
        report = _coord([chore]).projection_report(1)
        assert _for(report, "a")["points"] == 10
        assert _for(report, "b")["points"] == 10
        assert report["is_ceiling"] is True

    def test_everyone_chore_respects_an_explicit_pool(self):
        chore = Chore(
            name="Open",
            id="c",
            points=10,
            assignment_mode="everyone",
            assigned_to=["a"],
            schedule_mode="specific_days",
            due_days=[],
        )
        report = _coord([chore]).projection_report(1)
        assert _for(report, "a")["points"] == 10
        assert _for(report, "b")["points"] == 0

    def test_rotation_credits_only_the_days_assignee(self):
        chore = Chore(
            name="Rota", id="c", points=10, assignment_mode="alternating", schedule_mode="specific_days", due_days=[]
        )
        report = _coord([chore], assignments={"c": "b"}).projection_report(1)
        assert _for(report, "a")["points"] == 0
        assert _for(report, "b")["points"] == 10

    def test_rotation_with_no_assignee_counts_as_unassigned(self):
        chore = Chore(
            name="Rota", id="c", points=10, assignment_mode="alternating", schedule_mode="specific_days", due_days=[]
        )
        report = _coord([chore], assignments={}).projection_report(1)
        assert report["unassigned_points"] == 10

    def test_unassigned_mode_is_counted_separately(self):
        chore = Chore(
            name="Spare", id="c", points=7, assignment_mode="unassigned", schedule_mode="specific_days", due_days=[]
        )
        report = _coord([chore]).projection_report(1)
        assert report["unassigned_points"] == 7
        assert _for(report, "a")["points"] == 0


class TestTotals:
    def test_projected_total_adds_to_the_current_balance(self):
        chore = Chore(name="Daily", id="c", points=5, schedule_mode="specific_days", due_days=[])
        row = _for(_coord([chore]).projection_report(2), "a")
        assert row["current_points"] == 100
        assert row["points"] == 10
        assert row["projected_total"] == 110

    def test_children_sorted_by_most_to_earn(self):
        chore = Chore(
            name="Rota", id="c", points=10, assignment_mode="alternating", schedule_mode="specific_days", due_days=[]
        )
        report = _coord([chore], assignments={"c": "b"}).projection_report(1)
        assert report["children"][0]["id"] == "b"

    def test_per_day_rows_carry_each_child(self):
        chore = Chore(name="Daily", id="c", points=5, schedule_mode="specific_days", due_days=[])
        day = _coord([chore]).projection_report(1)["by_day"][0]
        assert {c["id"] for c in day["children"]} == {"a", "b"}
        assert day["weekday"] == _today().strftime("%A").lower()

    def test_no_chores_produces_zeroes_not_an_error(self):
        report = _coord([]).projection_report(3)
        assert all(r["points"] == 0 for r in report["children"])
        assert report["unassigned_points"] == 0

    def test_difficulty_multiplier_is_applied(self):
        """Projection must value a chore the same way completion will."""
        chore = Chore(name="Hard", id="c", points=10, difficulty="hard", schedule_mode="specific_days", due_days=[])
        coord = _coord([chore])
        coord.effective_chore_points = MagicMock(return_value=20)
        assert _for(coord.projection_report(1), "a")["points"] == 20


class TestFallsOn:
    def test_recurring_without_anchor_or_day_uses_the_period(self):
        coord = _coord()
        chore = Chore(name="Rec", id="c", schedule_mode="recurring", recurrence="every_2_days")
        today = _today()
        assert coord._chore_falls_on(chore, today) is True
        assert coord._chore_falls_on(chore, today + timedelta(days=1)) is False

    def test_one_shot_without_a_created_date_never_falls(self):
        coord = _coord()
        assert coord._chore_falls_on(Chore(name="X", id="c", schedule_mode="one_shot"), date.today()) is False
