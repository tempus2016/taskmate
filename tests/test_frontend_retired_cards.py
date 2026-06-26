"""Retired Lovelace card resources are deregistered on startup.

Cards removed in v4 (templates / reminders / task-groups) left their Lovelace
resource registrations behind, 404-ing on every dashboard load for upgraders.
`async_register_cards` now deletes those by exact URL — and ONLY those, never a
live card and never via heuristic diffing (which once wiped every resource).
"""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# conftest stubs the whole `custom_components.taskmate.frontend` module (its HA
# deps aren't stubbed suite-wide). To exercise the real cleanup logic, supply
# the two HA submodules frontend.py imports, drop the stub, and import the real
# module with its proper package context. Self-contained: nothing else imports
# this module after package init, so no other test is affected.
sys.modules.setdefault("homeassistant.components.http", MagicMock())
sys.modules.setdefault("homeassistant.components.frontend", MagicMock())
sys.modules.pop("custom_components.taskmate.frontend", None)

from custom_components.taskmate import frontend as fe  # noqa: E402


class FakeResources:
    """Minimal stand-in for HA's Lovelace ResourceStorageCollection."""

    def __init__(self, items):
        self._items = list(items)
        self.async_load = AsyncMock()
        self.async_get_info = AsyncMock()

    def async_items(self):
        return list(self._items)

    async def async_create_item(self, data):
        self._items.append({"id": f"id-{len(self._items)}", **data})

    async def async_update_item(self, item_id, data):
        for it in self._items:
            if it["id"] == item_id:
                it.update(data)

    async def async_delete_item(self, item_id):
        self._items = [it for it in self._items if it["id"] != item_id]


def _hass(resources):
    hass = MagicMock()
    lovelace = MagicMock()
    lovelace.mode = "storage"
    lovelace.resources = resources
    hass.data = {"lovelace": lovelace}
    # _async_get_version offloads manifest read to the executor — run inline.
    async def _exec(func, *args):
        return func(*args)
    hass.async_add_executor_job = _exec
    return hass


@pytest.mark.asyncio
async def test_retired_cards_deregistered_live_cards_kept():
    live = f"{fe.URL_BASE}/{fe.CARDS[0]}"
    retired = f"{fe.URL_BASE}/{fe.RETIRED_CARDS[0]}"
    other = "/local/some-other-card.js"  # non-taskmate, must be untouched
    res = FakeResources([
        {"id": "a", "url": f"{live}?v=1.0.0", "res_type": "module"},
        {"id": "b", "url": f"{retired}?v=1.0.0", "res_type": "module"},
        {"id": "c", "url": other, "res_type": "module"},
    ])
    await fe.async_register_cards(_hass(res))
    urls = [it["url"].split("?")[0] for it in res.async_items()]
    assert retired not in urls            # retired removed
    assert live in urls                   # live card preserved
    assert other in urls                  # foreign resource untouched


@pytest.mark.asyncio
async def test_no_retired_present_is_a_noop():
    """Nothing to clean up → live cards still present, no error."""
    live = f"{fe.URL_BASE}/{fe.CARDS[0]}"
    res = FakeResources([{"id": "a", "url": f"{live}?v=1.0.0", "res_type": "module"}])
    await fe.async_register_cards(_hass(res))
    assert any(it["url"].startswith(live) for it in res.async_items())
