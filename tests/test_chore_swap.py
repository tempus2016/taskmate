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


def test_approve_removes_request():
    """Approval consumes the request, the same way rejection does (#783).

    Nothing reads a request once it leaves `pending` — both readers filter on
    it — so keeping the record would just grow the store forever. The approval
    is still observable via the `taskmate_swap_approved` event and the chore's
    own dated override.
    """
    chore = Chore(name="Bins", assignment_mode="alternating", assignment_current_child_id="a", id="ch1")
    coord = _coord(chore, [Child(name="A", id="a"), Child(name="B", id="b")])
    run(coord.async_request_swap("ch1", "b"))
    run(coord.async_approve_swap(coord._reqs[0]["id"]))
    assert coord._reqs == []


def test_approve_twice_is_rejected():
    """The second approval finds no pending request and raises, rather than
    re-firing the event or re-stamping the override."""
    chore = Chore(name="Bins", assignment_mode="alternating", assignment_current_child_id="a", id="ch1")
    coord = _coord(chore, [Child(name="A", id="a"), Child(name="B", id="b")])
    run(coord.async_request_swap("ch1", "b"))
    rid = coord._reqs[0]["id"]
    run(coord.async_approve_swap(rid))
    with pytest.raises(ValueError, match="not found"):
        run(coord.async_approve_swap(rid))


# ---------------------------------------------------------------------------
# Orphan cleanup (#785) — deleting a chore or child must take its pending swap
# requests with it, or the parent is left with an unclearable "? wants to swap
# ?" row in the approval queue.
# ---------------------------------------------------------------------------


def _real_system():
    """A coordinator over real storage — the mock storage above can't exercise
    the removal cascades, which touch several stores at once."""
    from tests.test_rotation_quota import _make_system

    return _make_system()


def _two_kids_and_chore(coord, _mod, now):
    from unittest.mock import patch

    with patch.object(_mod.dt_util, "now", return_value=now):
        alice = run(coord.async_add_child("Alice"))
        bob = run(coord.async_add_child("Bob"))
        chore = run(
            coord.async_add_chore(
                "Dishes",
                points=10,
                assignment_mode="alternating",
                assigned_to=[alice.id, bob.id],
            )
        )
        active = coord._compute_active_children(chore)[0]
        other = next(c.id for c in (alice, bob) if c.id != active)
        run(coord.async_request_swap(chore.id, other))
    return chore, active, other


def test_removing_chore_drops_its_pending_swap_requests():
    from tests.test_rotation_quota import _now

    coord, storage, _mod = _real_system()
    chore, _active, _other = _two_kids_and_chore(coord, _mod, _now())
    assert len(storage.get_swap_requests()) == 1

    run(coord.async_remove_chore(chore.id))
    assert storage.get_swap_requests() == []


def test_removing_child_drops_swap_requests_they_requested():
    from tests.test_rotation_quota import _now

    coord, storage, _mod = _real_system()
    _chore, _active, other = _two_kids_and_chore(coord, _mod, _now())
    assert len(storage.get_swap_requests()) == 1

    run(coord.async_remove_child(other))
    assert storage.get_swap_requests() == []


def test_removing_child_drops_swap_requests_aimed_away_from_them():
    """The swapped-*away* child matters too: `from_child_id` is rendered in the
    queue, and the request describes a handover that can no longer happen."""
    from tests.test_rotation_quota import _now

    coord, storage, _mod = _real_system()
    _chore, active, _other = _two_kids_and_chore(coord, _mod, _now())
    run(coord.async_remove_child(active))
    assert storage.get_swap_requests() == []


def test_removing_child_clears_a_swap_override_pointing_at_them():
    from unittest.mock import patch

    from tests.test_rotation_quota import _now

    coord, storage, _mod = _real_system()
    now = _now()
    chore, _active, other = _two_kids_and_chore(coord, _mod, now)
    with patch.object(_mod.dt_util, "now", return_value=now):
        run(coord.async_approve_swap(storage.get_swap_requests()[0]["id"]))
    assert storage.get_chore(chore.id).assignment_swap_child_id == other

    run(coord.async_remove_child(other))
    stored = storage.get_chore(chore.id)
    assert stored.assignment_swap_child_id == ""
    assert stored.assignment_swap_date == ""


def test_removing_an_unrelated_child_leaves_the_request_alone():
    from unittest.mock import patch

    from tests.test_rotation_quota import _now

    coord, storage, _mod = _real_system()
    now = _now()
    _chore, _active, _other = _two_kids_and_chore(coord, _mod, now)
    with patch.object(_mod.dt_util, "now", return_value=now):
        bystander = run(coord.async_add_child("Cara"))

    run(coord.async_remove_child(bystander.id))
    assert len(storage.get_swap_requests()) == 1
