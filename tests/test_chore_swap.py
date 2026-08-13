"""Tests for sibling chore swaps."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.util import dt as dt_util

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(chore, children):
    by_id = {c.id: c for c in children}
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    reqs = []
    storage = MagicMock()
    storage.get_chore = MagicMock(return_value=chore)
    storage.get_swap_requests = MagicMock(return_value=reqs)
    storage.add_swap_request = MagicMock(side_effect=lambda r: reqs.append(r))
    storage.update_swap_request = MagicMock(
        side_effect=lambda rid, **ch: [r.update(ch) for r in reqs if r["id"] == rid]
    )
    storage.remove_swap_request = MagicMock(
        side_effect=lambda rid: reqs.__setitem__(slice(None), [r for r in reqs if r["id"] != rid])
    )
    storage.update_chore = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord._reqs = reqs
    coord.get_chore = MagicMock(return_value=chore)
    coord.get_child = MagicMock(side_effect=lambda cid: by_id.get(cid))
    coord.async_refresh = AsyncMock()
    return coord


def test_request_creates_pending():
    chore = Chore(name="Bins", assignment_mode="alternating", assignment_current_child_id="a", id="ch1")
    coord = _coord(chore, [Child(name="A", id="a"), Child(name="B", id="b")])
    rid = run(coord.async_request_swap("ch1", "b"))
    assert coord._reqs[0]["status"] == "pending"
    assert coord._reqs[0]["requester_id"] == "b"
    assert coord._reqs[0]["from_child_id"] == "a"
    assert rid


def test_request_rejected_for_everyone_mode():
    chore = Chore(name="Bins", assignment_mode="everyone", id="ch1")
    coord = _coord(chore, [Child(name="A", id="a")])
    with pytest.raises(ValueError, match="rotation"):
        run(coord.async_request_swap("ch1", "a"))


def test_request_rejected_if_already_assignee():
    chore = Chore(name="Bins", assignment_mode="alternating", assignment_current_child_id="a", id="ch1")
    coord = _coord(chore, [Child(name="A", id="a")])
    with pytest.raises(ValueError, match="already assigned"):
        run(coord.async_request_swap("ch1", "a"))


def test_approve_reassigns_today():
    chore = Chore(name="Bins", assignment_mode="alternating", assignment_current_child_id="a", id="ch1")
    coord = _coord(chore, [Child(name="A", id="a"), Child(name="B", id="b")])
    run(coord.async_request_swap("ch1", "b"))
    run(coord.async_approve_swap(coord._reqs[0]["id"]))
    assert chore.assignment_current_child_id == "b"
    assert coord._reqs[0]["status"] == "approved"
    assert any(c[0][0] == "taskmate_swap_approved" for c in coord.hass.bus.async_fire.call_args_list)


def test_reject_removes_request():
    chore = Chore(name="Bins", assignment_mode="alternating", assignment_current_child_id="a", id="ch1")
    coord = _coord(chore, [Child(name="A", id="a"), Child(name="B", id="b")])
    run(coord.async_request_swap("ch1", "b"))
    rid = coord._reqs[0]["id"]
    run(coord.async_reject_swap(rid))
    assert coord._reqs == []
    assert chore.assignment_current_child_id == "a"  # unchanged


def test_approve_stamps_dated_swap_override():
    """Approval records a *dated* override, not just the cached current child.

    `assignment_current_child_id` is written from `_compute_active_children`
    at midnight, so it can't be the override's home — reading it back there
    would pin the rotation. The dated pair is what read-time gates consult.
    """
    chore = Chore(name="Bins", assignment_mode="alternating", assignment_current_child_id="a", id="ch1")
    coord = _coord(chore, [Child(name="A", id="a"), Child(name="B", id="b")])
    run(coord.async_request_swap("ch1", "b"))
    run(coord.async_approve_swap(coord._reqs[0]["id"]))
    assert chore.assignment_swap_child_id == "b"
    assert chore.assignment_swap_date == dt_util.now().date().isoformat()
