"""Tests for config export / import (backup & restore)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore
from custom_components.taskmate.storage import TaskMateStorage


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.mark.asyncio
async def test_storage_export_is_deep_copy(hass):
    storage = TaskMateStorage(hass, "exp")
    await storage.async_load()
    storage.add_child(Child(name="Mia", id="c1"))
    snap = storage.export_data()
    snap["children"].append({"name": "ghost"})
    # Mutating the export must not affect live data.
    assert all(c.name != "ghost" for c in storage.get_children())


@pytest.mark.asyncio
async def test_storage_import_replaces_and_ensures_keys(hass):
    storage = TaskMateStorage(hass, "imp")
    await storage.async_load()
    storage.add_child(Child(name="Old", id="old"))
    storage.import_data({"children": [Child(name="New", id="new").to_dict()]})
    names = [c.name for c in storage.get_children()]
    assert names == ["New"]
    # missing collections are backfilled
    assert storage.get_chores() == []
    assert isinstance(storage._data["settings"], dict)


@pytest.mark.asyncio
async def test_storage_import_rejects_non_dict(hass):
    storage = TaskMateStorage(hass, "imp2")
    await storage.async_load()
    with pytest.raises(ValueError):
        storage.import_data(["nope"])


def _coord():
    coord = object.__new__(TaskMateCoordinator)
    storage = MagicMock()
    storage.export_data = MagicMock(return_value={"children": [], "settings": {}})
    storage.import_data = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    return coord


def test_export_config_wraps_with_version():
    coord = _coord()
    payload = coord.export_config()
    assert payload["taskmate_export_version"] == TaskMateCoordinator.EXPORT_VERSION
    assert payload["data"] == {"children": [], "settings": {}}


def test_import_config_valid_payload():
    coord = _coord()
    run(coord.async_import_config({"taskmate_export_version": 1, "data": {"children": []}}))
    coord.storage.import_data.assert_called_once_with({"children": []})
    coord.storage.async_save.assert_awaited_once()


def test_import_config_rejects_bad_payload():
    coord = _coord()
    for bad in ({}, {"data": "x"}, "nope", {"taskmate_export_version": 1}):
        try:
            run(coord.async_import_config(bad))
            assert False, f"expected ValueError for {bad!r}"
        except ValueError:
            pass
    coord.storage.import_data.assert_not_called()


def test_export_import_round_trip(hass):
    async def _go():
        storage = TaskMateStorage(hass, "rt")
        await storage.async_load()
        storage.add_child(Child(name="Mia", id="c1"))
        storage.add_chore(Chore(name="Bin", points=5, id="ch1"))
        snap = storage.export_data()
        storage.add_child(Child(name="Extra", id="c2"))
        storage.import_data(snap)
        assert [c.id for c in storage.get_children()] == ["c1"]
        assert [c.id for c in storage.get_chores()] == ["ch1"]
    run(_go())
