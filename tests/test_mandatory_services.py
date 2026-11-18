"""Tests for mandatory state exposure (#532)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, MandatoryMiss


def test_state_includes_enriched_misses():
    c = object.__new__(TaskMateCoordinator)
    s = MagicMock()
    s.get_mandatory_misses = MagicMock(
        return_value=[
            MandatoryMiss(
                chore_id="c1", child_id="k1", due_date="2026-06-21", period_id="morning", penalty_points=5, id="m1"
            ),
        ]
    )
    s.get_chores = MagicMock(return_value=[Chore(name="Homework", id="c1")])
    s.get_children = MagicMock(return_value=[Child(name="Kid", id="k1")])
    c.storage = s
    out = c.mandatory_misses_state()
    assert out[0]["chore_name"] == "Homework"
    assert out[0]["child_name"] == "Kid"
    assert out[0]["penalty_points"] == 5
    assert out[0]["id"] == "m1"


def test_state_handles_missing_refs():
    c = object.__new__(TaskMateCoordinator)
    s = MagicMock()
    s.get_mandatory_misses = MagicMock(
        return_value=[
            MandatoryMiss(chore_id="gone", child_id="gone", due_date="d", period_id="morning", id="m1"),
        ]
    )
    s.get_chores = MagicMock(return_value=[])
    s.get_children = MagicMock(return_value=[])
    c.storage = s
    out = c.mandatory_misses_state()
    assert out[0]["chore_name"] == ""
    assert out[0]["child_name"] == ""


def _coord_with(miss, chore, settings=None):
    c = object.__new__(TaskMateCoordinator)
    s = MagicMock()
    s.get_mandatory_misses = MagicMock(return_value=[miss])
    s.get_chores = MagicMock(return_value=[chore])
    s.get_children = MagicMock(return_value=[Child(name="Kid", id="k1")])
    s.get_choice_sets = MagicMock(return_value=[])
    s.get_setting = MagicMock(side_effect=lambda key, default=None: (settings or {}).get(key, default))
    c.storage = s
    return c


def test_state_adds_weekly_progress_for_the_missed_week():
    """#1271: a weekly-target miss says how far the child got that week."""
    miss = MandatoryMiss(chore_id="c1", child_id="k1", due_date="2026-11-17", period_id="anytime", id="m1")
    c = _coord_with(miss, Chore(name="Hoover", id="c1", weekly_target=2))
    seen = {}

    def count(chore_id, child_id, on=None):
        seen["args"] = (chore_id, child_id, on)
        return 1

    c.weekly_completion_count = count
    out = c.mandatory_misses_state()
    assert out[0]["weekly_target"] == 2
    assert out[0]["weekly_done"] == 1
    # Counted for the week of the miss, not the current week.
    assert seen["args"] == ("c1", "k1", date(2026, 11, 17))


def test_state_omits_weekly_fields_without_a_target():
    miss = MandatoryMiss(chore_id="c1", child_id="k1", due_date="2026-11-17", period_id="morning", id="m1")
    out = _coord_with(miss, Chore(name="Teeth", id="c1")).mandatory_misses_state()
    assert "weekly_target" not in out[0]
    assert "weekly_done" not in out[0]
    # A built-in period with no custom name: the card translates the id.
    assert "period_name" not in out[0]


def test_state_names_a_renamed_period():
    miss = MandatoryMiss(chore_id="c1", child_id="k1", due_date="2026-11-17", period_id="p1", id="m1")
    settings = {"time_periods": [{"id": "p1", "label": "Before school", "start": "07:00", "end": "08:30"}]}
    out = _coord_with(miss, Chore(name="Teeth", id="c1"), settings).mandatory_misses_state()
    assert out[0]["period_name"] == "Before school"
