"""PERF-3: async_save debounces; async_save_now writes through."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.storage import TaskMateStorage


class _SpyStore:
    def __init__(self):
        self.delay_calls = []
        self.immediate_calls = []

    def async_delay_save(self, data_func, delay=0):
        self.delay_calls.append((data_func(), delay))

    async def async_save(self, data):
        self.immediate_calls.append(data)


@pytest.mark.asyncio
async def test_async_save_uses_delay_save():
    storage = object.__new__(TaskMateStorage)
    storage._data = {"x": 1}
    storage._store = _SpyStore()
    await storage.async_save()
    assert len(storage._store.delay_calls) == 1
    assert storage._store.delay_calls[0][0] == {"x": 1}
    assert storage._store.delay_calls[0][1] > 0  # non-zero debounce
    assert storage._store.immediate_calls == []  # no direct write
    assert storage.data_version == 1


@pytest.mark.asyncio
async def test_async_save_now_writes_through():
    storage = object.__new__(TaskMateStorage)
    storage._data = {"x": 2}
    storage._store = _SpyStore()
    await storage.async_save_now()
    assert storage._store.immediate_calls == [{"x": 2}]
    assert storage._store.delay_calls == []
    assert storage.data_version == 1


@pytest.mark.asyncio
async def test_repeated_saves_each_bump_version_and_debounce():
    storage = object.__new__(TaskMateStorage)
    storage._data = {}
    storage._store = _SpyStore()
    for _ in range(4):
        await storage.async_save()
    # Each call schedules a (coalescing) delayed write; HA collapses them to one
    # real disk write. Version still advances per logical save.
    assert len(storage._store.delay_calls) == 4
    assert storage.data_version == 4


@pytest.mark.asyncio
async def test_shutdown_flushes_pending_save():
    from custom_components.taskmate.coordinator import TaskMateCoordinator

    coord = object.__new__(TaskMateCoordinator)
    coord.storage = MagicMock()
    coord.storage.async_save_now = AsyncMock()
    coord.notifications = MagicMock()
    coord._unsub_midnight = None
    coord._unsub_prune = None
    coord._unsub_availability = None
    coord._unsub_surprise = None
    coord._unsub_weekly = None
    coord.disarm_mandatory_schedules = MagicMock()
    await coord.async_shutdown()
    coord.storage.async_save_now.assert_awaited_once()
    # Unload must also drop the scheduled notification time triggers, or they
    # keep firing against the dead coordinator after a reload.
    coord.notifications.cancel_schedules.assert_called_once()
