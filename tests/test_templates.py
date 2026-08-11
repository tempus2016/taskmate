"""Tests for chore template CRUD and apply logic."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.storage import TaskMateStorage


def run(coro):
    """Run a coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def storage():
    """Create a storage instance with in-memory store."""
    hass = MagicMock()
    s = TaskMateStorage(hass, "test_entry")
    s._store = MagicMock()
    s._store.async_load = AsyncMock(return_value=None)
    s._store.async_save = AsyncMock()
    run(s.async_load())
    return s


class TestStorageTemplates:
    def test_templates_key_initialized_empty(self, storage):
        assert storage._data.get("templates") == []

    def test_get_custom_templates_empty(self, storage):
        assert storage.get_custom_templates() == []

    def test_add_custom_template(self, storage):
        tpl = {"id": "my_tpl", "name": "My Pack", "icon": "mdi:star", "builtin": False, "chores": []}
        storage.add_custom_template(tpl)
        assert len(storage.get_custom_templates()) == 1
        assert storage.get_custom_templates()[0]["id"] == "my_tpl"

    def test_update_custom_template(self, storage):
        tpl = {"id": "my_tpl", "name": "My Pack", "icon": "mdi:star", "builtin": False, "chores": []}
        storage.add_custom_template(tpl)
        storage.update_custom_template("my_tpl", {"name": "Renamed"})
        assert storage.get_custom_templates()[0]["name"] == "Renamed"

    def test_update_nonexistent_template_raises(self, storage):
        with pytest.raises(ValueError):
            storage.update_custom_template("nope", {"name": "X"})

    def test_remove_custom_template(self, storage):
        tpl = {"id": "my_tpl", "name": "My Pack", "icon": "mdi:star", "builtin": False, "chores": []}
        storage.add_custom_template(tpl)
        storage.remove_custom_template("my_tpl")
        assert storage.get_custom_templates() == []

    def test_remove_nonexistent_template_raises(self, storage):
        with pytest.raises(ValueError):
            storage.remove_custom_template("nope")

    def test_get_custom_template_by_id(self, storage):
        tpl = {
            "id": "my_tpl",
            "name": "My Pack",
            "icon": "mdi:star",
            "builtin": False,
            "chores": [{"name": "X", "points": 1}],
        }
        storage.add_custom_template(tpl)
        result = storage.get_custom_template("my_tpl")
        assert result is not None
        assert result["name"] == "My Pack"

    def test_get_custom_template_not_found(self, storage):
        assert storage.get_custom_template("nope") is None
