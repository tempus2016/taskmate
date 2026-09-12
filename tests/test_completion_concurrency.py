"""Two requests landing together must not both be paid.

Awarding points can suspend (a level-up or streak milestone sends a
notification), while the duplicate/daily-limit checks read stored completions.
If the record is written *after* the award, both callers pass the same check
and the chore pays twice. These drive that interleaving deterministically by
making the award yield.
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
    """Run a coroutine factory on a fresh loop, returning its result."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro_factory())
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def test_two_concurrent_completions_pay_once():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, storage = await _make_system()
        now = _now()
        with patch.object(_mod.dt_util, "now", return_value=now):
            child = await coord.async_add_child("Alice")
            chore = await coord.async_add_chore(
                "Dishes",
                points=10,
                requires_approval=False,
                schedule_mode="specific_days",
                assigned_to=[child.id],
                daily_limit=1,
            )

            real_award = coord._award_points

            async def slow_award(*args, **kwargs):
                # Stand in for the notification await inside a real level-up.
                await asyncio.sleep(0)
                return await real_award(*args, **kwargs)

            coord._award_points = slow_award

            await asyncio.gather(
                coord.async_complete_chore(chore.id, child.id),
                coord.async_complete_chore(chore.id, child.id),
            )
            return storage, child.id

    storage, child_id = _run(scenario)

    assert len(storage.get_completions()) == 1, "daily limit was exceeded by a concurrent call"
    assert storage.get_child(child_id).points == 10, "the chore paid out twice"


def test_two_concurrent_approvals_pay_once():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, storage = await _make_system()
        now = _now()
        with patch.object(_mod.dt_util, "now", return_value=now):
            child = await coord.async_add_child("Alice")
            chore = await coord.async_add_chore(
                "Dishes",
                points=10,
                requires_approval=True,
                schedule_mode="specific_days",
                assigned_to=[child.id],
            )
            comp = await coord.async_complete_chore(chore.id, child.id)

            real_award = coord._award_points

            async def slow_award(*args, **kwargs):
                await asyncio.sleep(0)
                return await real_award(*args, **kwargs)

            coord._award_points = slow_award

            await asyncio.gather(
                coord.async_approve_chore(comp.id),
                coord.async_approve_chore(comp.id),
            )
            return storage, child.id

    storage, child_id = _run(scenario)

    assert storage.get_child(child_id).points == 10, "a double approval paid twice"


def test_two_concurrent_bonus_subtasks_pay_once():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod
        from custom_components.taskmate.models import BonusSubTask

        coord, storage = await _make_system()
        now = _now()
        with patch.object(_mod.dt_util, "now", return_value=now):
            child = await coord.async_add_child("Alice")
            chore = await coord.async_add_chore(
                "Tidy",
                points=10,
                requires_approval=False,
                schedule_mode="specific_days",
                assigned_to=[child.id],
            )
            chore.bonus_subtasks = [BonusSubTask(id="b1", name="Hoover", points=25)]
            storage.update_chore(chore)
            await coord.async_complete_chore(chore.id, child.id)

            real_award = coord._award_points

            async def slow_award(*args, **kwargs):
                await asyncio.sleep(0)
                return await real_award(*args, **kwargs)

            coord._award_points = slow_award

            results = await asyncio.gather(
                coord.async_complete_bonus_subtask(chore.id, "b1", child.id),
                coord.async_complete_bonus_subtask(chore.id, "b1", child.id),
                return_exceptions=True,
            )
            return storage, child.id, results

    storage, child_id, results = _run(scenario)

    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 1, "the duplicate bonus sub-task was not rejected"
    assert storage.get_child(child_id).points == 35, "the bonus paid twice"
