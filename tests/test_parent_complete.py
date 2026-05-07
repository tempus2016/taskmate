"""Tests for parent_complete_chore coordinator method."""
from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _now(year=2024, month=3, day=20, hour=12):
    return dt.datetime(year, month, day, hour, 0, 0, tzinfo=UTC)


def _make_system(now=None):
    from tests.conftest import FakeHass, FakeStore

    if now is None:
        now = _now()

    hass = FakeHass()
    hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    run(storage.async_load())

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.data = {}
    coord.storage = storage
    coord._unsub_midnight = None
    coord._unsub_prune = None
    coord._unsub_availability = None

    import custom_components.taskmate.coordinator as _mod
    coord._dt_now = now
    coord.async_refresh = AsyncMock()

    return coord, storage, _mod


class TestParentCompleteChore:
    def test_parent_complete_creates_completion_with_zero_points(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(coord.async_add_chore(
                "Vacuum", points=10, requires_approval=False,
                schedule_mode="recurring", recurrence="weekly",
                assigned_to=[child.id],
            ))

        with patch.object(_mod.dt_util, "now", return_value=now):
            result = run(coord.async_parent_complete_chore(chore.id))

        completions = storage.get_completions()
        assert len(completions) == 1
        assert completions[0].child_id == "__parent__"
        assert completions[0].points_awarded == 0
        assert completions[0].approved is True

    def test_parent_complete_updates_last_completed_for_all_children(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            alice = run(coord.async_add_child("Alice"))
            bob = run(coord.async_add_child("Bob"))
            chore = run(coord.async_add_chore(
                "Dishes", points=5, requires_approval=False,
                schedule_mode="recurring", recurrence="weekly",
                assigned_to=[alice.id, bob.id],
            ))

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))

        alice_lc = storage.get_last_completed(chore.id, alice.id)
        bob_lc = storage.get_last_completed(chore.id, bob.id)
        assert alice_lc.get("current") == now.isoformat()
        assert bob_lc.get("current") == now.isoformat()

    def test_parent_complete_rejects_one_shot_chore(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(coord.async_add_chore(
                "Special task", points=10, requires_approval=False,
                schedule_mode="one_shot",
                assigned_to=[child.id],
            ))

        with patch.object(_mod.dt_util, "now", return_value=now):
            with pytest.raises(ValueError, match="one.shot"):
                run(coord.async_parent_complete_chore(chore.id))

    def test_parent_complete_rejects_nonexistent_chore(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            with pytest.raises(ValueError, match="not found"):
                run(coord.async_parent_complete_chore("fake_id"))

    def test_parent_complete_rejects_disabled_chore(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(coord.async_add_chore(
                "Mop", points=5, requires_approval=False,
                schedule_mode="recurring", recurrence="weekly",
                assigned_to=[child.id],
            ))
            chore.enabled = False
            storage.update_chore(chore)

        with patch.object(_mod.dt_util, "now", return_value=now):
            with pytest.raises(ValueError, match="disabled"):
                run(coord.async_parent_complete_chore(chore.id))

    def test_parent_complete_does_not_award_points(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(coord.async_add_chore(
                "Sweep", points=15, requires_approval=False,
                schedule_mode="recurring", recurrence="weekly",
                assigned_to=[child.id],
            ))

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))

        updated_child = storage.get_child(child.id)
        assert updated_child.points == 0
        assert updated_child.current_streak == 0

    def test_parent_complete_suppresses_availability_for_children(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(coord.async_add_chore(
                "Laundry", points=5, requires_approval=False,
                schedule_mode="recurring", recurrence="weekly",
                assigned_to=[child.id],
            ))

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))

        with patch.object(_mod.dt_util, "now", return_value=now):
            available = coord.is_chore_available_for_child(chore, child.id)
        assert available is False

    def test_parent_complete_everyone_mode_updates_all_children(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            alice = run(coord.async_add_child("Alice"))
            bob = run(coord.async_add_child("Bob"))
            chore = run(coord.async_add_chore(
                "Tidy", points=5, requires_approval=False,
                schedule_mode="recurring", recurrence="weekly",
                assigned_to=[],  # empty = everyone
            ))

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))

        alice_lc = storage.get_last_completed(chore.id, alice.id)
        bob_lc = storage.get_last_completed(chore.id, bob.id)
        assert alice_lc.get("current") == now.isoformat()
        assert bob_lc.get("current") == now.isoformat()


class TestParentCompleteIntegration:
    """Full lifecycle: parent completes → chore becomes unavailable → next cycle it returns."""

    def test_chore_returns_after_recurrence_window(self):
        coord, storage, _mod = _make_system()
        now = _now(2024, 3, 20)  # Wednesday

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(coord.async_add_chore(
                "Weekly clean", points=10, requires_approval=False,
                schedule_mode="recurring", recurrence="weekly",
                assigned_to=[child.id],
            ))

        # Parent completes it
        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))

        # Same day: not available
        with patch.object(_mod.dt_util, "now", return_value=now):
            assert coord.is_chore_available_for_child(chore, child.id) is False

        # 6 days later: still not available
        six_days = _now(2024, 3, 26)
        with patch.object(_mod.dt_util, "now", return_value=six_days):
            assert coord.is_chore_available_for_child(chore, child.id) is False

        # 7 days later: available again
        seven_days = _now(2024, 3, 27)
        with patch.object(_mod.dt_util, "now", return_value=seven_days):
            assert coord.is_chore_available_for_child(chore, child.id) is True

    def test_parent_complete_does_not_change_rotation_pointer(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            alice = run(coord.async_add_child("Alice"))
            bob = run(coord.async_add_child("Bob"))
            chore = run(coord.async_add_chore(
                "Alternating chore", points=5, requires_approval=False,
                schedule_mode="recurring", recurrence="weekly",
                assigned_to=[alice.id, bob.id],
                assignment_mode="alternating",
            ))

        original_pointer = chore.assignment_current_child_id

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))

        updated_chore = storage.get_chore(chore.id)
        assert updated_chore.assignment_current_child_id == original_pointer
