"""Tests for orphan mandatory-miss pruning (#532)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Chore, MandatoryMiss


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(chores, misses):
    c = object.__new__(TaskMateCoordinator)
    s = MagicMock()
    s.get_chores = MagicMock(return_value=chores)
    s.get_mandatory_misses = MagicMock(return_value=misses)
    s.remove_mandatory_miss = MagicMock()
    s.async_save = AsyncMock()
    c.storage = s
    c.async_refresh = AsyncMock()
    return c


def _miss():
    return MandatoryMiss(chore_id="c1", child_id="k1", due_date="2026-06-21", period_id="morning", id="m1")


def test_prunes_miss_for_unmandatory_chore():
    coord = _coord([Chore(name="X", mandatory=False, enabled=True, id="c1")], [_miss()])
    assert run(coord.async_prune_orphan_misses()) == 1
    coord.storage.remove_mandatory_miss.assert_called_once_with("m1")


def test_prunes_miss_for_deleted_chore():
    coord = _coord([], [_miss()])
    assert run(coord.async_prune_orphan_misses()) == 1
    coord.storage.remove_mandatory_miss.assert_called_once_with("m1")


def test_prunes_miss_for_disabled_chore():
    coord = _coord([Chore(name="X", mandatory=True, enabled=False, id="c1")], [_miss()])
    assert run(coord.async_prune_orphan_misses()) == 1


def test_keeps_valid_miss():
    coord = _coord([Chore(name="X", mandatory=True, enabled=True, id="c1")], [_miss()])
    assert run(coord.async_prune_orphan_misses()) == 0
    coord.storage.remove_mandatory_miss.assert_not_called()
