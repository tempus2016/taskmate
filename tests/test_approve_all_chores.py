"""Tests for bulk chore approval (Approve All)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import ChoreCompletion


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _completion(cid, approved=False):
    return ChoreCompletion(
        chore_id="ch1", child_id="k1",
        completed_at=datetime.now(timezone.utc), approved=approved, id=cid,
    )


def _coord(completions):
    coord = object.__new__(TaskMateCoordinator)
    storage = MagicMock()
    storage.get_completions = MagicMock(return_value=completions)
    coord.storage = storage
    approved = []

    async def _approve(cid):
        for c in completions:
            if c.id == cid and not c.approved:
                c.approved = True
                approved.append(cid)

    coord.async_approve_chore = AsyncMock(side_effect=_approve)
    coord._approved = approved
    return coord


def test_approve_all_when_no_ids_approves_every_pending():
    cs = [_completion("a"), _completion("b"), _completion("c", approved=True)]
    coord = _coord(cs)
    n = run(coord.async_approve_chores_bulk())
    assert n == 2
    assert coord._approved == ["a", "b"]


def test_approve_all_with_explicit_subset():
    cs = [_completion("a"), _completion("b"), _completion("c")]
    coord = _coord(cs)
    n = run(coord.async_approve_chores_bulk(["a", "c"]))
    assert n == 2
    assert coord._approved == ["a", "c"]


def test_already_approved_and_unknown_ids_ignored():
    cs = [_completion("a", approved=True), _completion("b")]
    coord = _coord(cs)
    n = run(coord.async_approve_chores_bulk(["a", "b", "missing"]))
    assert n == 1
    assert coord._approved == ["b"]


def test_empty_pending_returns_zero():
    coord = _coord([])
    n = run(coord.async_approve_chores_bulk())
    assert n == 0
    coord.async_approve_chore.assert_not_awaited()
