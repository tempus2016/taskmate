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


class TestSwappedRotation:
    """An approved sibling swap must move the *whole* eligibility, not just the
    card's view of it (#781). Before the fix the swapped-to child saw the chore
    (the sensor reads `assignment_current_child_id`) but `async_complete_chore`
    gated on `_compute_active_children`, which is pure date math — so the tap
    was a silent no-op: no points, no pending approval, and the chore returned
    on the next 30s coordinator refresh.
    """

    def _swapped(self, coord, _mod, now):
        chore, active, inactive = _alternating_chore(coord, _mod, now)
        with patch.object(_mod.dt_util, "now", return_value=now):
            req_id = run(coord.async_request_swap(chore.id, inactive))
            run(coord.async_approve_swap(req_id))
        return chore, active, inactive

    def test_swapped_to_child_can_complete(self):
        coord, storage, _mod = _make_system()
        now = _now()
        chore, _active, inactive = self._swapped(coord, _mod, now)
        with patch.object(_mod.dt_util, "now", return_value=now):
            result = run(coord.async_complete_chore(chore.id, inactive, as_parent=False))
        assert result is not None
        comps = _parent_completions(storage)
        assert len(comps) == 1
        assert comps[0].child_id == inactive
        assert coord.get_child(inactive).points > 0

    def test_swapped_away_child_can_no_longer_complete(self):
        coord, storage, _mod = _make_system()
        now = _now()
        chore, active, _inactive = self._swapped(coord, _mod, now)
        with patch.object(_mod.dt_util, "now", return_value=now):
            result = run(coord.async_complete_chore(chore.id, active, as_parent=False))
        assert result is None
        assert _parent_completions(storage) == []

    def test_swap_still_shares_one_quota(self):
        coord, storage, _mod = _make_system()
        now = _now()
        chore, active, inactive = self._swapped(coord, _mod, now)
        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_complete_chore(chore.id, inactive, as_parent=False))
            result = run(coord.async_complete_chore(chore.id, active, as_parent=False))
        assert result is None
        assert len(_parent_completions(storage)) == 1

    def test_swap_does_not_leak_into_later_days(self):
        coord, storage, _mod = _make_system()
        now = _now()
        chore, active, inactive = self._swapped(coord, _mod, now)
        stored = storage.get_chore(chore.id)
        # The override is stamped with today's date only. A 2-child pool
        # alternates daily, so day+2 must land back on the swapped-away child —
        # if the override leaked it would still be pinned to the requester.
        day_after = (now + dt.timedelta(days=2)).date()
        assert coord._compute_active_children(stored, day_after) == [active]
        with patch.object(_mod.dt_util, "now", return_value=now + dt.timedelta(days=2)):
            assert coord._compute_active_children(stored) == [active]

    def test_swapped_chore_is_available_to_new_assignee(self):
        coord, storage, _mod = _make_system()
        now = _now()
        chore, active, inactive = self._swapped(coord, _mod, now)
        stored = storage.get_chore(chore.id)
        with patch.object(_mod.dt_util, "now", return_value=now):
            assert coord.is_chore_available_for_child(stored, inactive) is True
            assert coord.is_chore_available_for_child(stored, active) is False


class _MockEntry:
    entry_id = "test_entry"


class TestRemovedChildLeavesRotationPointer:
    """#787 — deleting the child holding today's rotation slot left
    `assignment_current_child_id` pointing at them, and the child sensor
    filters on exactly that field, so the chore vanished for everyone left
    until the midnight pass recomputed it."""

    def test_pointer_is_repointed_at_a_surviving_child(self):
        coord, storage, _mod = _make_system()
        now = _now()
        chore, active, survivor = _alternating_chore(coord, _mod, now)
        assert storage.get_chore(chore.id).assignment_current_child_id == active

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_remove_child(active))

        stored = storage.get_chore(chore.id)
        assert stored.assignment_current_child_id == survivor
        assert stored.assigned_to == [survivor]

    def test_child_sensor_still_lists_the_chore_for_the_survivor(self):
        """Where the bug actually bit: the child sensor filters on the pointer,
        so a stale one hid the chore from the card even though the completion
        service, button entity and to-do list all still accepted it."""
        from custom_components.taskmate.sensor import ChildStatsSensor

        coord, storage, _mod = _make_system()
        now = _now()
        chore, active, survivor = _alternating_chore(coord, _mod, now)

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_remove_child(active))
            stored = storage.get_chore(chore.id)
            coord.data = {"chores": [stored]}
            coord.get_child = storage.get_child
            coord._is_rotation_done_today = lambda c: False
            sensor = ChildStatsSensor(coord, _MockEntry(), storage.get_child(survivor))
            listed = [c["id"] for c in sensor.extra_state_attributes["assigned_chores"]]

        assert listed == [chore.id]

    def test_pointer_is_cleared_when_nobody_is_left_in_the_pool(self):
        coord, storage, _mod = _make_system()
        now = _now()
        chore, active, survivor = _alternating_chore(coord, _mod, now)

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_remove_child(active))
            run(coord.async_remove_child(survivor))

        assert storage.get_chore(chore.id).assignment_current_child_id == ""

    def test_removing_an_off_rotation_child_leaves_the_pointer_alone(self):
        coord, storage, _mod = _make_system()
        now = _now()
        chore, active, inactive = _alternating_chore(coord, _mod, now)

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_remove_child(inactive))

        assert storage.get_chore(chore.id).assignment_current_child_id == active
