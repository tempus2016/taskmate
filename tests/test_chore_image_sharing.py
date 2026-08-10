"""A shared chore image survives until the last chore referencing it goes (#768).

`async_clone_chore` copies `image_url` verbatim, so a duplicated chore points at
the same file on disk as its source. Deleting or re-picturing either copy must
not unlink a file the other one is still showing.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Chore

IMAGE = "/api/taskmate/image/deadbeef.png"
OTHER = "/api/taskmate/image/cafebabe.png"


def run(coro):
    """Run a coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(chores: list[Chore]) -> TaskMateCoordinator:
    """A coordinator whose storage holds exactly `chores`."""
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.data = {}

    by_id = {c.id: c for c in chores}
    storage = MagicMock()
    storage.get_chores = MagicMock(return_value=chores)
    storage.get_chore = MagicMock(side_effect=by_id.get)
    storage.get_children = MagicMock(return_value=[])
    storage.async_save = AsyncMock()
    coord.storage = storage

    coord.async_refresh = AsyncMock()
    coord._compute_daily_assignments = MagicMock(return_value={})
    coord._compute_active_children = MagicMock(return_value=[])
    coord._publish_chore_to_calendars = AsyncMock()
    coord._cleanup_chore_from_calendars = AsyncMock()
    return coord


def _chore(chore_id: str, image_url: str = "") -> Chore:
    return Chore(id=chore_id, name=f"chore {chore_id}", points=1, image_url=image_url)


def test_removing_one_of_two_chores_sharing_an_image_keeps_the_file():
    a, b = _chore("a", IMAGE), _chore("b", IMAGE)
    coord = _coord([a, b])
    with patch(
        "custom_components.taskmate.coord_chores.images.async_delete_image",
        new=AsyncMock(),
    ) as delete:
        run(coord.async_remove_chore("a"))
    delete.assert_not_awaited()


def test_removing_the_last_chore_using_an_image_deletes_the_file():
    a = _chore("a", IMAGE)
    coord = _coord([a])
    with patch(
        "custom_components.taskmate.coord_chores.images.async_delete_image",
        new=AsyncMock(),
    ) as delete:
        run(coord.async_remove_chore("a"))
    delete.assert_awaited_once_with(coord.hass, IMAGE)


def test_replacing_an_image_still_used_elsewhere_keeps_the_file():
    a, b = _chore("a", IMAGE), _chore("b", IMAGE)
    coord = _coord([a, b])
    updated = _chore("a", OTHER)
    with patch(
        "custom_components.taskmate.coord_chores.images.async_delete_image",
        new=AsyncMock(),
    ) as delete:
        run(coord.async_update_chore(updated))
    delete.assert_not_awaited()


def test_replacing_the_only_reference_to_an_image_deletes_the_file():
    a = _chore("a", IMAGE)
    coord = _coord([a])
    updated = _chore("a", OTHER)
    with patch(
        "custom_components.taskmate.coord_chores.images.async_delete_image",
        new=AsyncMock(),
    ) as delete:
        run(coord.async_update_chore(updated))
    delete.assert_awaited_once_with(coord.hass, IMAGE)


def test_the_chore_being_updated_does_not_count_as_its_own_reference():
    # Storage already holds the *new* value by the time cleanup runs, so a naive
    # "is anyone using it?" scan must exclude the chore under edit or it would
    # never delete anything.
    a = _chore("a", IMAGE)
    coord = _coord([a])
    updated = _chore("a", "")
    with patch(
        "custom_components.taskmate.coord_chores.images.async_delete_image",
        new=AsyncMock(),
    ) as delete:
        run(coord.async_update_chore(updated))
    delete.assert_awaited_once_with(coord.hass, IMAGE)
