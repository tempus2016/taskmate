"""Tests for get_due_chores_for_child (FEAT-8 shared helper).

is_chore_available_for_child is mocked so these isolate the *added* filtering:
assigned_to membership, specific_days due_days, and the completed-today cap.
"""

from __future__ import annotations

import datetime as dt
from datetime import timezone
from unittest.mock import MagicMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, ChoreCompletion

UTC = timezone.utc
NOW = dt.datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC)  # Monday


def _coord(chores, completions=None, available=True):
    coord = object.__new__(TaskMateCoordinator)
    coord.storage = MagicMock()
    coord.storage.get_chores = MagicMock(return_value=chores)
    coord.storage.get_completions = MagicMock(return_value=completions or [])
    if callable(available):
        coord.is_chore_available_for_child = MagicMock(side_effect=available)
    else:
        coord.is_chore_available_for_child = MagicMock(return_value=available)
    return coord


def _due(coord, child_id="ch1"):
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        return [c.name for c in coord.get_due_chores_for_child(child_id)]


def test_includes_assigned_and_everyone_excludes_others():
    chores = [
        Chore(name="Everyone", assigned_to=[], id="a"),
        Chore(name="Mine", assigned_to=["ch1"], id="b"),
        Chore(name="Sibling", assigned_to=["ch2"], id="c"),
    ]
    assert _due(_coord(chores)) == ["Everyone", "Mine"]


def test_specific_days_due_filter():
    chores = [
        Chore(name="MonOnly", schedule_mode="specific_days", due_days=["monday"], id="a"),
        Chore(name="TueOnly", schedule_mode="specific_days", due_days=["tuesday"], id="b"),
        Chore(name="AnyDay", schedule_mode="specific_days", due_days=[], id="c"),
    ]
    assert _due(_coord(chores)) == ["MonOnly", "AnyDay"]


def test_excludes_completed_up_to_daily_limit():
    chores = [
        Chore(name="Once", daily_limit=1, id="a"),
        Chore(name="Twice", daily_limit=2, id="b"),
    ]
    comps = [
        ChoreCompletion(chore_id="a", child_id="ch1", completed_at=NOW),  # Once done -> excluded
        ChoreCompletion(chore_id="b", child_id="ch1", completed_at=NOW),  # Twice 1/2 -> still due
    ]
    assert _due(_coord(chores, comps)) == ["Twice"]


def test_completion_by_other_child_does_not_count():
    chores = [Chore(name="Once", daily_limit=1, id="a")]
    comps = [ChoreCompletion(chore_id="a", child_id="ch2", completed_at=NOW)]
    assert _due(_coord(chores, comps)) == ["Once"]


def test_bonus_subtask_completion_does_not_count():
    chores = [Chore(name="Once", daily_limit=1, id="a")]
    comps = [ChoreCompletion(chore_id="a", child_id="ch1", completed_at=NOW, bonus_subtask_id="bs1")]
    assert _due(_coord(chores, comps)) == ["Once"]


def test_unavailable_chores_excluded():
    chores = [Chore(name="A", id="a"), Chore(name="B", id="b")]
    avail = lambda chore, cid: chore.id == "a"  # only A available
    assert _due(_coord(chores, available=avail)) == ["A"]


# ---------------------------------------------------------------------------
# FEAT-1: chore dependency gating in is_chore_available_for_child
# ---------------------------------------------------------------------------


def _avail_coord(chore, child, completions):
    coord = object.__new__(TaskMateCoordinator)
    coord.storage = MagicMock()
    coord.storage.get_child = MagicMock(return_value=child)
    coord.storage.get_completions = MagicMock(return_value=completions)
    coord._is_child_on_vacation = MagicMock(return_value=False)
    coord._is_visibility_entity_active = MagicMock(return_value=True)
    return coord


def _avail(chore, child, completions):
    coord = _avail_coord(chore, child, completions)
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        return coord.is_chore_available_for_child(chore, child.id)


def _dep_chore():
    return Chore(
        name="B",
        id="B",
        depends_on=["A"],
        schedule_mode="specific_days",
        due_days=[],
        assignment_mode="everyone",
        enabled=True,
    )


def test_dependency_unmet_blocks_chore():
    child = Child(name="K", id="ch1")
    assert _avail(_dep_chore(), child, []) is False


def test_dependency_met_unlocks_chore():
    child = Child(name="K", id="ch1")
    comps = [ChoreCompletion(chore_id="A", child_id="ch1", approved=True, completed_at=NOW)]
    assert _avail(_dep_chore(), child, comps) is True


def test_dependency_unapproved_completion_does_not_unlock():
    child = Child(name="K", id="ch1")
    comps = [ChoreCompletion(chore_id="A", child_id="ch1", approved=False, completed_at=NOW)]
    assert _avail(_dep_chore(), child, comps) is False


def test_dependency_met_by_other_child_does_not_unlock():
    child = Child(name="K", id="ch1")
    comps = [ChoreCompletion(chore_id="A", child_id="ch2", approved=True, completed_at=NOW)]
    assert _avail(_dep_chore(), child, comps) is False
