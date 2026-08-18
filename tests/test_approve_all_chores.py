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
        chore_id="ch1",
        child_id="k1",
        completed_at=datetime.now(timezone.utc),
        approved=approved,
        id=cid,
    )


def _coord(completions):
    coord = object.__new__(TaskMateCoordinator)
    storage = MagicMock()
    storage.get_completions = MagicMock(return_value=completions)
    coord.storage = storage
    approved = []

    async def _approve(cid, refresh=True):
        for c in completions:
            if c.id == cid and not c.approved:
                c.approved = True
                approved.append(cid)
        coord._refresh_flags.append(refresh)

    coord.async_approve_chore = AsyncMock(side_effect=_approve)
    coord.async_refresh = AsyncMock()
    coord._approved = approved
    coord._refresh_flags = []
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


class TestBulkApprovalRefreshesOnce:
    """Approve All rebuilt the whole coordinator once per completion (#794).

    ``async_approve_chore`` ends in ``await self.async_refresh()`` — a full
    rebuild plus a state write for every TaskMate entity. Reusing it per
    completion made "Approve All" cost O(N) refreshes: measured at ~0.13 s
    each on the dev instance, so 60 pending approvals blocked the websocket
    call for ~8 s with no intermediate state pushed to the frontend. The panel
    and the approvals card both look frozen for that whole window, which is
    indistinguishable from the button doing nothing.
    """

    def test_refresh_happens_once_not_per_completion(self):
        cs = [_completion(c) for c in "abcdefgh"]
        coord = _coord(cs)
        n = run(coord.async_approve_chores_bulk())
        assert n == 8
        assert coord.async_refresh.await_count == 1, (
            f"expected a single refresh for the whole batch, got "
            f"{coord.async_refresh.await_count} — one per completion is the #794 stall"
        )

    def test_per_completion_refresh_is_suppressed(self):
        cs = [_completion(c) for c in "abc"]
        coord = _coord(cs)
        run(coord.async_approve_chores_bulk())
        assert coord._refresh_flags == [False, False, False], (
            "each approval must be told not to refresh; the batch refreshes at the end"
        )

    def test_nothing_to_approve_skips_the_refresh_entirely(self):
        coord = _coord([_completion("a", approved=True)])
        assert run(coord.async_approve_chores_bulk()) == 0
        coord.async_refresh.assert_not_awaited()

    def test_single_approval_still_refreshes_by_default(self):
        """The default must stay refresh-on-approve — a lone approval from the
        card or a service call has nothing else to trigger the update."""
        import inspect

        from custom_components.taskmate.coord_chores import ChoresMixin

        sig = inspect.signature(ChoresMixin.async_approve_chore)
        assert sig.parameters["refresh"].default is True
