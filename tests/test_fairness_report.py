"""Fairness report (#679).

Answers "am I dumping everything on the eldest?". Judged on chore count rather
than points, so a pricier chore can't hide an uneven split.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

from homeassistant.util import dt as dt_util

from custom_components.taskmate.coord_reports import (
    DEFAULT_WINDOW_DAYS,
    FAIR_SHARE_TOLERANCE,
    MAX_WINDOW_DAYS,
)
from custom_components.taskmate.models import Child

from .test_coordinator_logic import _make_coord


def _completion(child_id, *, days_ago=0, points=10, approved=True, bonus=""):
    comp = MagicMock()
    comp.child_id = child_id
    comp.chore_id = "chore"
    comp.approved = approved
    comp.bonus_subtask_id = bonus
    comp.points_awarded = points
    comp.completed_at = dt_util.now() - timedelta(days=days_ago)
    return comp


def _coord(children, completions):
    coord = _make_coord(children=children, completions=completions)
    coord.storage.get_completions = MagicMock(return_value=list(completions))
    coord.storage.get_children = MagicMock(return_value=list(children))
    return coord


KIDS = [Child(name="Ella", id="a"), Child(name="Sam", id="b")]


class TestWindow:
    def test_default_window(self):
        report = _coord(KIDS, []).fairness_report()
        assert report["days"] == DEFAULT_WINDOW_DAYS

    def test_window_is_clamped(self):
        coord = _coord(KIDS, [])
        assert coord.fairness_report(0)["days"] == 1
        assert coord.fairness_report(9999)["days"] == MAX_WINDOW_DAYS

    def test_garbage_window_falls_back(self):
        assert _coord(KIDS, []).fairness_report("lots")["days"] == DEFAULT_WINDOW_DAYS

    def test_completions_outside_the_window_are_ignored(self):
        coord = _coord(KIDS, [_completion("a", days_ago=30)])
        assert coord.fairness_report(7)["total_completions"] == 0

    def test_completions_inside_the_window_count(self):
        coord = _coord(KIDS, [_completion("a", days_ago=3)])
        assert coord.fairness_report(7)["total_completions"] == 1


class TestWhatCounts:
    def test_pending_completions_are_excluded(self):
        """Unapproved work isn't yet work the parent agreed happened."""
        coord = _coord(KIDS, [_completion("a", approved=False)])
        assert coord.fairness_report()["total_completions"] == 0

    def test_bonus_subtasks_are_excluded(self):
        """They hang off a chore already counted — including them double-counts."""
        coord = _coord(KIDS, [_completion("a"), _completion("a", bonus="sub1")])
        assert coord.fairness_report()["total_completions"] == 1

    def test_deleted_child_history_is_ignored(self):
        coord = _coord(KIDS, [_completion("gone"), _completion("a")])
        report = coord.fairness_report()
        assert report["total_completions"] == 1
        assert {r["id"] for r in report["children"]} == {"a", "b"}

    def test_unparseable_timestamp_is_skipped(self):
        bad = _completion("a")
        bad.completed_at = "not a date"
        coord = _coord(KIDS, [bad, _completion("b")])
        assert coord.fairness_report()["total_completions"] == 1


class TestBalance:
    def test_even_split_is_balanced(self):
        coord = _coord(KIDS, [_completion("a"), _completion("a"),
                              _completion("b"), _completion("b")])
        report = coord.fairness_report()
        assert report["balanced"] is True
        assert {r["status"] for r in report["children"]} == {"balanced"}

    def test_lopsided_split_is_flagged(self):
        coord = _coord(KIDS, [_completion("a")] * 9 + [_completion("b")])
        report = coord.fairness_report()
        assert report["balanced"] is False
        by_id = {r["id"]: r for r in report["children"]}
        assert by_id["a"]["status"] == "over"
        assert by_id["b"]["status"] == "under"

    def test_no_activity_reads_as_idle_not_unbalanced(self):
        report = _coord(KIDS, []).fairness_report()
        assert report["balanced"] is True
        assert {r["status"] for r in report["children"]} == {"idle"}

    def test_just_inside_tolerance_is_balanced(self):
        """60/40 with a 15-point tolerance is not worth nagging about."""
        coord = _coord(KIDS, [_completion("a")] * 6 + [_completion("b")] * 4)
        assert _status(coord, "a") == "balanced"

    def test_just_outside_tolerance_is_flagged(self):
        coord = _coord(KIDS, [_completion("a")] * 7 + [_completion("b")] * 3)
        assert _status(coord, "a") == "over"

    def test_tolerance_is_reported_so_the_ui_can_explain_itself(self):
        assert _coord(KIDS, []).fairness_report()["tolerance"] == FAIR_SHARE_TOLERANCE


class TestFigures:
    def test_points_and_counts_are_tracked_separately(self):
        """One child doing three quick jobs vs one doing a hard one is
        balanced by points and lopsided by count — show both."""
        coord = _coord(KIDS, [_completion("a", points=1)] * 3 + [_completion("b", points=30)])
        by_id = {r["id"]: r for r in coord.fairness_report()["children"]}
        assert by_id["a"]["completions"] == 3
        assert by_id["a"]["points"] == 3
        assert by_id["b"]["completions"] == 1
        assert by_id["b"]["points"] == 30
        assert by_id["b"]["share_points"] > by_id["a"]["share_points"]
        assert by_id["a"]["share_completions"] > by_id["b"]["share_completions"]

    def test_status_follows_count_not_points(self):
        coord = _coord(KIDS, [_completion("a", points=1)] * 9 + [_completion("b", points=500)])
        assert _status(coord, "a") == "over"

    def test_active_days_counts_distinct_days(self):
        coord = _coord(KIDS, [_completion("a", days_ago=0), _completion("a", days_ago=0),
                              _completion("a", days_ago=2)])
        by_id = {r["id"]: r for r in coord.fairness_report()["children"]}
        assert by_id["a"]["active_days"] == 2

    def test_rows_sorted_by_most_work_first(self):
        coord = _coord(KIDS, [_completion("b")] * 5 + [_completion("a")])
        assert [r["id"] for r in coord.fairness_report()["children"]] == ["b", "a"]

    def test_fair_share_reflects_family_size(self):
        three = [*KIDS, Child(name="Kit", id="c")]
        assert _coord(three, []).fairness_report()["fair_share"] == 33.3

    def test_no_children_does_not_divide_by_zero(self):
        report = _coord([], []).fairness_report()
        assert report["fair_share"] == 0.0
        assert report["children"] == []


def _status(coord, child_id):
    return {r["id"]: r for r in coord.fairness_report()["children"]}[child_id]["status"]
