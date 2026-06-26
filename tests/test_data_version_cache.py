"""PERF-2: storage data_version + coordinator _async_update_data caching."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.storage import TaskMateStorage


@pytest.mark.asyncio
async def test_data_version_increments_on_save(hass):
    storage = TaskMateStorage(hass, "test")
    await storage.async_load()
    before = storage.data_version
    await storage.async_save()
    assert storage.data_version == before + 1
    await storage.async_save()
    assert storage.data_version == before + 2


def _coord():
    coord = object.__new__(TaskMateCoordinator)
    coord._data_snapshot_cache = None
    coord.storage = MagicMock()
    coord.storage.data_version = 1
    coord._async_auto_stop_capped_sessions = AsyncMock()
    coord._refresh_tracked_availability_entities = MagicMock()
    coord._build_data_snapshot = MagicMock(side_effect=lambda: {"built_at": coord.storage.data_version})
    return coord


@pytest.mark.asyncio
async def test_update_data_reuses_snapshot_when_version_unchanged():
    coord = _coord()
    r1 = await coord._async_update_data()
    r2 = await coord._async_update_data()
    assert r1 is r2  # identical object served from cache
    assert coord._build_data_snapshot.call_count == 1


@pytest.mark.asyncio
async def test_update_data_rebuilds_after_version_bump():
    coord = _coord()
    r1 = await coord._async_update_data()
    coord.storage.data_version = 2
    r2 = await coord._async_update_data()
    assert r1 is not r2
    assert coord._build_data_snapshot.call_count == 2
    assert r2["built_at"] == 2


@pytest.mark.asyncio
async def test_update_data_always_runs_side_effects():
    coord = _coord()
    await coord._async_update_data()
    await coord._async_update_data()  # cached path
    # Auto-stop + tracked-entity refresh must run every tick, cache or not.
    assert coord._async_auto_stop_capped_sessions.await_count == 2
    assert coord._refresh_tracked_availability_entities.call_count == 2
