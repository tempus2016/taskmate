"""Rotation chores share ONE daily quota across the pool (security finding #1).

Previously async_complete_chore only enforced the pool-wide rotation quota for
``first_come`` mode. For alternating/random/balanced a caller could award every
pool member by completing the chore once per child_id. These lock the fix:
- a non-active child cannot self-complete a rotation chore;
- once the rotation is done for the day no further pool member can complete;
- a parent (as_parent) may still complete on behalf of the off-rotation child.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _now():
    return dt.datetime(2024, 3, 20, 12, 0, 0, tzinfo=UTC)


def _make_system():
    from tests.conftest import FakeHass, FakeStore

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
    coord.async_refresh = AsyncMock()

    import custom_components.taskmate.coordinator as _mod

    return coord, storage, _mod


def _alternating_chore(coord, _mod, now):
    with patch.object(_mod.dt_util, "now", return_value=now):
        alice = run(coord.async_add_child("Alice"))
        bob = run(coord.async_add_child("Bob"))
        chore = run(
            coord.async_add_chore(
                "Dishes",
                points=10,
                requires_approval=False,
                assignment_mode="alternating",
                assigned_to=[alice.id, bob.id],
            )
        )
    active = coord._compute_active_children(chore)[0]
    inactive = next(c.id for c in (alice, bob) if c.id != active)
    return chore, active, inactive


def _parent_completions(storage):
    return [c for c in storage.get_completions() if not c.bonus_subtask_id]


class TestRotationQuota:
    def test_non_active_child_cannot_self_complete(self):
        coord, storage, _mod = _make_system()
        now = _now()
        chore, _active, inactive = _alternating_chore(coord, _mod, now)
        with patch.object(_mod.dt_util, "now", return_value=now):
            result = run(coord.async_complete_chore(chore.id, inactive, as_parent=False))
        assert result is None  # soft no-op: not this child's turn
        assert _parent_completions(storage) == []

    def test_quota_locks_after_one_completion(self):
        coord, storage, _mod = _make_system()
        now = _now()
        chore, active, inactive = _alternating_chore(coord, _mod, now)
        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_complete_chore(chore.id, active, as_parent=False))
            # The pool quota is now filled — a second pool member's completion is
            # a silent no-op (previously this awarded the inactive child too).
            result = run(coord.async_complete_chore(chore.id, inactive, as_parent=False))
        assert result is None
        comps = _parent_completions(storage)
        assert len(comps) == 1
        assert comps[0].child_id == active

    def test_parent_may_complete_off_rotation_child(self):
        coord, storage, _mod = _make_system()
        now = _now()
        chore, _active, inactive = _alternating_chore(coord, _mod, now)
        with patch.object(_mod.dt_util, "now", return_value=now):
            # as_parent bypasses the active-assignee restriction (parent ticks
            # it off for the off-rotation child) but still fills the one quota.
            run(coord.async_complete_chore(chore.id, inactive, as_parent=True))
        comps = _parent_completions(storage)
        assert len(comps) == 1
        assert comps[0].child_id == inactive
