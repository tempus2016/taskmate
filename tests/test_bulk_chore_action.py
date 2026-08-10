"""Tests for bulk chore actions."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Chore


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(chores):
    by_id = {c.id: c for c in chores}
    coord = object.__new__(TaskMateCoordinator)
    storage = MagicMock()
    storage.get_chore = MagicMock(side_effect=lambda cid: by_id.get(cid))
    removed = []
    storage.remove_chore = MagicMock(side_effect=lambda cid: removed.append(cid))
    storage.update_chore = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord._removed = removed
    coord.async_refresh = AsyncMock()
    return coord


def test_bulk_disable():
    cs = [Chore(name="A", enabled=True, id="c1"), Chore(name="B", enabled=True, id="c2")]
    coord = _coord(cs)
    n = run(coord.async_bulk_chore_action("disable", ["c1", "c2"]))
    assert n == 2 and cs[0].enabled is False and cs[1].enabled is False


def test_bulk_enable_clears_disabled_for():
    c = Chore(name="A", enabled=False, disabled_for=["k1"], id="c1")
    coord = _coord([c])
    run(coord.async_bulk_chore_action("enable", ["c1"]))
    assert c.enabled is True and c.disabled_for == []


def test_bulk_delete():
    cs = [Chore(name="A", id="c1"), Chore(name="B", id="c2")]
    coord = _coord(cs)
    n = run(coord.async_bulk_chore_action("delete", ["c1", "c2"]))
    assert n == 2 and coord._removed == ["c1", "c2"]


def test_bulk_reassign():
    c = Chore(name="A", assigned_to=["k1"], id="c1")
    coord = _coord([c])
    run(coord.async_bulk_chore_action("reassign", ["c1"], assigned_to=["k2", "k3"]))
    assert c.assigned_to == ["k2", "k3"]


def test_bulk_reassign_all_children_empty_list():
    c = Chore(name="A", assigned_to=["k1"], id="c1")
    coord = _coord([c])
    run(coord.async_bulk_chore_action("reassign", ["c1"], assigned_to=[]))
    assert c.assigned_to == []


def test_unknown_ids_skipped_and_counted_correctly():
    c = Chore(name="A", enabled=True, id="c1")
    coord = _coord([c])
    n = run(coord.async_bulk_chore_action("disable", ["c1", "missing"]))
    assert n == 1


def test_empty_ids_noop():
    coord = _coord([])
    n = run(coord.async_bulk_chore_action("delete", []))
    assert n == 0
    coord.storage.async_save.assert_not_awaited()


def test_unknown_action_raises():
    coord = _coord([Chore(name="A", id="c1")])
    with pytest.raises(ValueError):
        run(coord.async_bulk_chore_action("frobnicate", ["c1"]))
