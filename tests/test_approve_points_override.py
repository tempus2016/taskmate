"""A parent may set the points when approving a chore completion (#832).

The override replaces the chore's *base* points; every multiplier that
normally rides on an approval (streaks, level bonuses) still applies on top,
so an overridden approval behaves like any other approval.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc


def _now():
    return dt.datetime(2024, 3, 20, 12, 0, 0, tzinfo=UTC)


async def _make_system():
    from tests.conftest import FakeHass, FakeStore

    hass = FakeHass()
    hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    await storage.async_load()

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.data = {}
    coord.storage = storage
    coord._unsub_midnight = None
    coord._unsub_prune = None
    coord._unsub_availability = None
    coord._dt_now = _now()
    coord.async_refresh = AsyncMock()
    coord._async_notify_pending_approval = AsyncMock()
    notifications = AsyncMock()
    notifications._has_outstanding_chores_today = lambda _cid: True
    coord.notifications = notifications
    return coord, storage


def _run(coro_factory):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro_factory())
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def _stored(coord, completion_id):
    """Re-read a completion from storage — approval mutates the stored record."""
    return next(c for c in coord.storage.get_completions() if c.id == completion_id)


async def _pending_completion(coord, points=10, **chore_kwargs):
    """Add a child + chore and leave one completion sitting pending."""
    child = await coord.async_add_child("Alice")
    chore = await coord.async_add_chore(
        "Tidy up",
        points=points,
        requires_approval=True,
        schedule_mode="specific_days",
        assigned_to=[child.id],
        **chore_kwargs,
    )
    completion = await coord.async_complete_chore(chore.id, child.id)
    assert completion is not None and completion.approved is False
    return child, chore, completion


def test_override_awards_the_parents_number_not_the_chores():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _storage = await _make_system()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            child, _chore, completion = await _pending_completion(coord, points=10)
            await coord.async_approve_chore(completion.id, points=25)
            return coord.get_child(child.id).points, _stored(coord, completion.id).points_awarded

    points, awarded = _run(scenario)
    assert awarded == 25
    assert points == 25


def test_no_override_still_awards_the_chores_points():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _storage = await _make_system()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            child, _chore, completion = await _pending_completion(coord, points=10)
            await coord.async_approve_chore(completion.id)
            return coord.get_child(child.id).points, _stored(coord, completion.id).points_awarded

    points, awarded = _run(scenario)
    assert awarded == 10
    assert points == 10


def test_override_of_zero_awards_nothing():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _storage = await _make_system()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            child, _chore, completion = await _pending_completion(coord, points=10)
            await coord.async_approve_chore(completion.id, points=0)
            return coord.get_child(child.id).points, _stored(coord, completion.id).approved

    points, approved = _run(scenario)
    assert approved is True
    assert points == 0


def test_negative_override_is_clamped_to_zero():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _storage = await _make_system()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            child, _chore, completion = await _pending_completion(coord, points=10)
            await coord.async_approve_chore(completion.id, points=-50)
            return coord.get_child(child.id).points

    assert _run(scenario) == 0


def test_override_replaces_the_timed_rate_calculation():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _storage = await _make_system()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            child, chore, completion = await _pending_completion(coord, points=10)
            chore.task_type = "timed"
            chore.timed_rate_minutes = 10
            chore.timed_rate_points = 5
            coord.storage.update_chore(chore)
            completion.timed_duration_seconds = 1800
            coord.storage.update_completion(completion)
            await coord.async_approve_chore(completion.id, points=7)
            return coord.get_child(child.id).points

    assert _run(scenario) == 7


def test_bulk_approval_is_unaffected_by_the_new_argument():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _storage = await _make_system()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            child, _chore, completion = await _pending_completion(coord, points=10)
            count = await coord.async_approve_chores_bulk()
            return count, coord.get_child(child.id).points

    count, points = _run(scenario)
    assert count == 1
    assert points == 10
