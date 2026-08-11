"""Tests for undoing an accidental chore approval (revert to pending).

Undo reverses the awards exactly like reject, but keeps the completion record
and flips it back to pending (so it returns to the approval queue), and does NOT
notify the child.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, ChoreCompletion

UTC = dt.timezone.utc
DAY = dt.datetime(2024, 1, 1, tzinfo=UTC)


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(child, chore, completions):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    storage = MagicMock()
    storage.get_completions = MagicMock(return_value=completions)
    storage.update_child = MagicMock()
    storage.update_completion = MagicMock()
    storage.remove_completion = MagicMock()
    storage.undo_last_completed = MagicMock()
    storage.update_chore = MagicMock()
    storage.get_children = MagicMock(return_value=[child])
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.get_child = MagicMock(return_value=child)
    coord.get_chore = MagicMock(return_value=chore)
    coord.async_refresh = AsyncMock()
    return coord


def _fired(coord, name):
    return [c for c in coord.hass.bus.async_fire.call_args_list if c[0][0] == name]


def test_undo_approval_reverts_to_pending_and_reverses_awards():
    child = Child(
        name="Mia",
        id="c1",
        points=50,
        total_points_earned=100,
        total_chores_completed=3,
        current_streak=4,
        last_completion_date="2024-01-01",
    )
    chore = Chore(name="Bin", id="ch1")
    comp = ChoreCompletion(
        chore_id="ch1", child_id="c1", completed_at=DAY, approved=True, approved_at=DAY, points_awarded=5, id="comp1"
    )
    coord = _coord(child, chore, [comp])

    run(coord.async_undo_chore_approval("comp1"))

    # Awards reversed
    assert child.points == 45  # 50 - 5
    assert child.total_points_earned == 95  # 100 - 5
    assert child.total_chores_completed == 2  # 3 - 1
    assert child.current_streak == 3  # sole completion that day
    assert child.last_completion_date is None  # no remaining completions

    # Reverted to pending, NOT removed
    assert comp.approved is False
    assert comp.points_awarded == 0
    assert comp.approved_at is None
    coord.storage.update_completion.assert_called_once()
    coord.storage.remove_completion.assert_not_called()


def test_undo_approval_fires_undone_not_rejected():
    child = Child(name="Mia", id="c1", points=10, total_points_earned=10, total_chores_completed=1, current_streak=1)
    chore = Chore(name="Bin", id="ch1")
    comp = ChoreCompletion(
        chore_id="ch1", child_id="c1", completed_at=DAY, approved=True, approved_at=DAY, points_awarded=10, id="comp1"
    )
    coord = _coord(child, chore, [comp])

    run(coord.async_undo_chore_approval("comp1"))

    assert len(_fired(coord, "taskmate_chore_approval_undone")) == 1
    assert _fired(coord, "taskmate_chore_rejected") == []


def test_undo_approval_one_shot_reenables():
    child = Child(name="Mia", id="c1", points=10, total_points_earned=10, total_chores_completed=1)
    chore = Chore(name="Bin", id="ch1", schedule_mode="one_shot", enabled=False, disabled_for=["c1"])
    comp = ChoreCompletion(
        chore_id="ch1", child_id="c1", completed_at=DAY, approved=True, approved_at=DAY, points_awarded=10, id="comp1"
    )
    coord = _coord(child, chore, [comp])

    run(coord.async_undo_chore_approval("comp1"))

    assert "c1" not in chore.disabled_for
    assert chore.enabled is True


def test_undo_unapproved_completion_raises():
    child = Child(name="Mia", id="c1")
    chore = Chore(name="Bin", id="ch1")
    comp = ChoreCompletion(
        chore_id="ch1", child_id="c1", completed_at=DAY, approved=False, points_awarded=0, id="comp1"
    )
    coord = _coord(child, chore, [comp])
    with pytest.raises(ValueError, match="not approved"):
        run(coord.async_undo_chore_approval("comp1"))
    coord.storage.update_completion.assert_not_called()


def test_undo_missing_completion_raises():
    child = Child(name="Mia", id="c1")
    chore = Chore(name="Bin", id="ch1")
    coord = _coord(child, chore, [])
    with pytest.raises(ValueError, match="not found"):
        run(coord.async_undo_chore_approval("nope"))
