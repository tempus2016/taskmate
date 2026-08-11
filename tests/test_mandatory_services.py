"""Tests for mandatory state exposure (#532)."""

from __future__ import annotations

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
