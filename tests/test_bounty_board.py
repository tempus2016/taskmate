"""Bounty board: one-off jobs any eligible child can claim (#931).

A parent posts a bounty for fixed points; an eligible child claims it (one
claim at a time), which locks it to them for the claim period; Done submits a
completion into the ordinary approval queue. Approval pays it like a chore;
rejection hands it back to the same child with a fresh lock; a claim that runs
out returns it to the board, and an unclaimed bounty expires.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Bounty, Child, ChoreCompletion
from custom_components.taskmate.storage import TaskMateStorage

from .conftest import dt_util_mock

UTC = timezone.utc
NOW = dt.datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC)
PHOTO = "/api/taskmate/photo/" + "a" * 32 + ".jpg"
KIDS = [Child(name="Malia", id="k1"), Child(name="Vaiha", id="k2"), Child(name="Isla", id="k3")]


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _clock():
    saved = dt_util_mock._now
    dt_util_mock._now = NOW
    yield
    dt_util_mock._now = saved


def _at(**delta):
    dt_util_mock._now = NOW + dt.timedelta(**delta)


def _coord(children=KIDS):
    from tests.conftest import FakeStore

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {"children": [c.to_dict() for c in children], "chores": [], "completions": []}
    storage._data_version = 0

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.data = {}
    coord.storage = storage
    coord.notifications = MagicMock()
    coord.notifications.fire = AsyncMock()
    coord.notifications.clear_approval = AsyncMock()
    coord.notifications._has_outstanding_chores_today = MagicMock(return_value=True)
    coord.async_refresh = AsyncMock()
    coord._award_points = AsyncMock(side_effect=lambda child, pts, **kw: pts)
    coord._async_notify_pending_approval = AsyncMock()
    coord._async_advance_quests = AsyncMock()
    coord._async_evaluate_challenges = AsyncMock()
    coord._async_rewind_quests = AsyncMock()
    coord.async_recheck_mandatory_miss = AsyncMock()
    coord.badges = None
    return coord


def _post(coord, **kwargs):
    kwargs.setdefault("claim_hours", 2)
    return run(coord.async_post_bounty(kwargs.pop("title", "Wash the car"), kwargs.pop("points", 50), **kwargs))


def _bounty(coord, bounty_id):
    return coord.storage.get_bounty(bounty_id)


def _events(coord):
    return [c.args[0] for c in coord.hass.bus.async_fire.call_args_list]


# ── the model ────────────────────────────────────────────────────────────────


def test_bounty_round_trips_through_storage():
    b = Bounty(
        title="Wash the car",
        points=50,
        expires_at=NOW,
        eligible_child_ids=["k1"],
        claim_hours=3,
        require_photo=True,
        status="claimed",
        claimed_by="k1",
        claimed_at=NOW,
        claim_until=NOW + dt.timedelta(hours=3),
        lapse_count=2,
        claim_count=3,
    )
    back = Bounty.from_dict(b.to_dict())
    assert back == b


def test_a_minimal_record_loads_with_safe_defaults():
    back = Bounty.from_dict({"title": "Rake leaves", "id": "b1"})
    assert (back.status, back.points, back.claim_hours, back.eligible_child_ids) == ("open", 0, 2, [])
    assert back.expires_at is None and back.notify_children is True and back.require_photo is False


def test_an_unknown_status_loads_as_open():
    assert Bounty.from_dict({"title": "x", "status": "bogus"}).status == "open"


def test_completion_bounty_id_is_only_written_when_set():
    plain = ChoreCompletion(chore_id="c", child_id="k1", completed_at=NOW)
    assert "bounty_id" not in plain.to_dict()
    tagged = ChoreCompletion(chore_id="b", child_id="k1", completed_at=NOW, bounty_id="b")
    assert ChoreCompletion.from_dict(tagged.to_dict()).bounty_id == "b"


def test_storage_without_bounties_reads_as_empty():
    coord = _coord()
    assert coord.storage.get_bounties() == []
    assert coord.storage.get_bounty("nope") is None


# ── posting ──────────────────────────────────────────────────────────────────


def test_post_puts_an_open_bounty_on_the_board():
    coord = _coord()
    b = _post(coord, eligible_child_ids=["k1", "k2"], require_photo=True)
    stored = _bounty(coord, b.id)
    assert stored.status == "open" and stored.points == 50 and stored.eligible_child_ids == ["k1", "k2"]
    assert stored.require_photo is True and stored.created_at == NOW
    assert "taskmate_bounty_posted" in _events(coord)


def test_ticking_every_child_is_stored_as_all_children():
    coord = _coord()
    b = _post(coord, eligible_child_ids=["k1", "k2", "k3"])
    assert _bounty(coord, b.id).eligible_child_ids == []


@pytest.mark.parametrize(
    "kwargs",
    [{"title": "  "}, {"points": 0}, {"claim_hours": 0}, {"claim_hours": 49}, {"eligible_child_ids": ["ghost"]}],
)
def test_post_refuses_bad_input(kwargs):
    coord = _coord()
    with pytest.raises(ValueError):
        _post(coord, **kwargs)
    assert coord.storage.get_bounties() == []


def test_post_refuses_an_expiry_in_the_past():
    coord = _coord()
    with pytest.raises(ValueError):
        _post(coord, expires_at=(NOW - dt.timedelta(minutes=1)).isoformat())


def test_a_naive_expiry_is_read_as_local_time():
    coord = _coord()
    b = _post(coord, expires_at="2026-04-23T18:00:00")
    assert _bounty(coord, b.id).expires_at == dt.datetime(2026, 4, 23, 18, 0, tzinfo=UTC)


def test_post_notifies_only_the_eligible_children_when_asked():
    coord = _coord()
    _post(coord, eligible_child_ids=["k1", "k3"], notify_children=True)
    call = coord.notifications.fire.await_args
    assert call.args[0] == "bounty_posted"
    assert call.args[1]["bounty_name"] == "Wash the car" and call.args[1]["points"] == 50
    assert call.kwargs["only_recipients"] == {"child:k1", "child:k3"}


def test_post_stays_quiet_when_not_asked_to_notify():
    coord = _coord()
    _post(coord, notify_children=False)
    coord.notifications.fire.assert_not_awaited()


# ── claiming ─────────────────────────────────────────────────────────────────


def test_claim_locks_the_bounty_to_the_child_for_its_claim_period():
    coord = _coord()
    b = _post(coord, claim_hours=2)
    run(coord.async_claim_bounty(b.id, "k1"))
    stored = _bounty(coord, b.id)
    assert (stored.status, stored.claimed_by, stored.claimed_at) == ("claimed", "k1", NOW)
    assert stored.claim_until == NOW + dt.timedelta(hours=2)
    assert "taskmate_bounty_claimed" in _events(coord)


def test_a_claim_never_outlives_the_expiry():
    coord = _coord()
    b = _post(coord, claim_hours=3, expires_at=(NOW + dt.timedelta(minutes=45)).isoformat())
    run(coord.async_claim_bounty(b.id, "k1"))
    assert _bounty(coord, b.id).claim_until == NOW + dt.timedelta(minutes=45)


def test_a_child_not_on_the_list_cannot_claim():
    coord = _coord()
    b = _post(coord, eligible_child_ids=["k2"])
    with pytest.raises(ValueError, match="isn't for you"):
        run(coord.async_claim_bounty(b.id, "k1"))
    assert _bounty(coord, b.id).status == "open"


def test_a_claimed_bounty_cannot_be_claimed_again():
    coord = _coord()
    b = _post(coord)
    run(coord.async_claim_bounty(b.id, "k1"))
    with pytest.raises(ValueError):
        run(coord.async_claim_bounty(b.id, "k2"))
    assert _bounty(coord, b.id).claimed_by == "k1"


def test_one_active_claim_per_child():
    coord = _coord()
    first = _post(coord, title="Wash the car")
    second = _post(coord, title="Rake leaves")
    run(coord.async_claim_bounty(first.id, "k1"))
    with pytest.raises(ValueError, match="one bounty at a time"):
        run(coord.async_claim_bounty(second.id, "k1"))
    # Once the first is submitted, the child is free to take another.
    run(coord.async_complete_bounty(first.id, "k1"))
    run(coord.async_claim_bounty(second.id, "k1"))
    assert _bounty(coord, second.id).claimed_by == "k1"


def test_an_expired_but_unswept_bounty_cannot_be_claimed():
    coord = _coord()
    b = _post(coord, expires_at=(NOW + dt.timedelta(minutes=5)).isoformat())
    _at(minutes=6)
    with pytest.raises(ValueError):
        run(coord.async_claim_bounty(b.id, "k1"))


def test_give_back_returns_it_to_the_board():
    coord = _coord()
    b = _post(coord)
    run(coord.async_claim_bounty(b.id, "k1"))
    run(coord.async_give_back_bounty(b.id, "k1"))
    stored = _bounty(coord, b.id)
    assert stored.status == "open" and stored.claimed_by == "" and stored.claim_until is None


def test_only_the_claimer_can_give_it_back():
    coord = _coord()
    b = _post(coord)
    run(coord.async_claim_bounty(b.id, "k1"))
    with pytest.raises(ValueError):
        run(coord.async_give_back_bounty(b.id, "k2"))


def test_a_parent_can_release_a_claim():
    coord = _coord()
    b = _post(coord)
    run(coord.async_claim_bounty(b.id, "k1"))
    run(coord.async_release_bounty(b.id))
    assert _bounty(coord, b.id).status == "open"
    assert "taskmate_bounty_released" in _events(coord)


# ── done → the approval queue ────────────────────────────────────────────────


def _claimed(coord, child="k1", **kwargs):
    b = _post(coord, **kwargs)
    run(coord.async_claim_bounty(b.id, child))
    return b


def test_done_submits_a_pending_completion_into_the_approval_queue():
    coord = _coord()
    b = _claimed(coord)
    comp = run(coord.async_complete_bounty(b.id, "k1"))
    assert (comp.approved, comp.bounty_id, comp.chore_id, comp.submitted_points) == (False, b.id, b.id, 50)
    assert comp in coord.storage.get_pending_completions()
    stored = _bounty(coord, b.id)
    assert stored.status == "pending" and stored.completion_id == comp.id
    coord._async_notify_pending_approval.assert_awaited_once()
    assert coord._async_notify_pending_approval.await_args.args[:3] == ("Malia", "Wash the car", 50)


def test_done_needs_the_claim():
    coord = _coord()
    b = _claimed(coord, child="k2")
    with pytest.raises(ValueError):
        run(coord.async_complete_bounty(b.id, "k1"))


def test_done_after_the_lock_ran_out_is_refused():
    coord = _coord()
    b = _claimed(coord)
    _at(hours=2, seconds=1)
    with pytest.raises(ValueError, match="ran out"):
        run(coord.async_complete_bounty(b.id, "k1"))


def test_a_photo_bounty_needs_a_photo():
    coord = _coord()
    b = _claimed(coord, require_photo=True)
    with pytest.raises(ValueError, match="photo"):
        run(coord.async_complete_bounty(b.id, "k1"))
    # A foreign URL is dropped, so it can't satisfy the gate either.
    with pytest.raises(ValueError, match="photo"):
        run(coord.async_complete_bounty(b.id, "k1", photo_url="https://evil.example/x.jpg"))
    comp = run(coord.async_complete_bounty(b.id, "k1", photo_url=PHOTO))
    assert comp.photo_url == PHOTO


def test_approval_pays_it_like_a_chore_and_closes_the_bounty():
    coord = _coord()
    b = _claimed(coord)
    comp = run(coord.async_complete_bounty(b.id, "k1"))
    _at(minutes=30)
    run(coord.async_approve_chore(comp.id))
    # Paid through the shared award path — streaks, levels, weekend bonus.
    coord._award_points.assert_awaited_once()
    award = coord._award_points.await_args
    assert award.args[0].id == "k1" and award.args[1] == 50 and award.kwargs["chore_id"] == b.id
    stored = _bounty(coord, b.id)
    assert (stored.status, stored.points_awarded, stored.claimed_by) == ("completed", 50, "k1")
    assert stored.closed_at == NOW + dt.timedelta(minutes=30)
    approved = next(c for c in coord.storage.get_completions() if c.id == comp.id)
    assert approved.approved and approved.points_awarded == 50
    # Progression hooks run for it, as for any approved chore.
    coord._async_evaluate_challenges.assert_awaited_once_with("k1")
    assert "taskmate_bounty_approved" in _events(coord)


def test_a_changed_price_while_waiting_is_what_approval_pays():
    coord = _coord()
    b = _claimed(coord)
    comp = run(coord.async_complete_bounty(b.id, "k1"))
    run(coord.async_update_bounty(b.id, points=80))
    run(coord.async_approve_chore(comp.id))
    assert coord._award_points.await_args.args[1] == 80


def test_rejection_hands_it_back_to_the_same_child_with_a_fresh_lock():
    coord = _coord()
    b = _claimed(coord, expires_at=(NOW + dt.timedelta(hours=3)).isoformat())
    comp = run(coord.async_complete_bounty(b.id, "k1"))
    _at(hours=2, minutes=50)
    run(coord.async_reject_chore(comp.id))
    stored = _bounty(coord, b.id)
    assert (stored.status, stored.claimed_by, stored.completion_id) == ("claimed", "k1", "")
    # A full new lock, even though the bounty's own expiry is 10 minutes away.
    assert stored.claim_until == dt_util_mock._now + dt.timedelta(hours=2)
    assert coord.storage.get_pending_completions() == []
    assert "taskmate_bounty_rejected" in _events(coord)


def test_a_childs_own_undo_keeps_the_lock_they_had():
    coord = _coord()
    coord.storage._data["settings"] = {"chore_undo_seconds": 300}
    b = _claimed(coord)
    comp = run(coord.async_complete_bounty(b.id, "k1"))
    assert comp.child_undo_allowed
    _at(minutes=20)
    run(coord.async_undo_chore(comp.id))
    stored = _bounty(coord, b.id)
    assert stored.status == "claimed" and stored.claimed_by == "k1"
    assert stored.claim_until == NOW + dt.timedelta(hours=2)


def test_undoing_an_approval_puts_it_back_in_the_queue():
    coord = _coord()
    b = _claimed(coord)
    comp = run(coord.async_complete_bounty(b.id, "k1"))
    run(coord.async_approve_chore(comp.id))
    run(coord.async_undo_chore_approval(comp.id))
    stored = _bounty(coord, b.id)
    assert (stored.status, stored.points_awarded, stored.closed_at) == ("pending", 0, None)
    assert [c.id for c in coord.storage.get_pending_completions()] == [comp.id]


# ── lapses, expiry and the warning ───────────────────────────────────────────


def _sweep(coord):
    return run(coord.async_sweep_bounties(refresh=False))


def test_a_claim_that_runs_out_goes_back_on_the_board():
    coord = _coord()
    b = _claimed(coord)
    _at(hours=2)
    assert _sweep(coord) is True
    stored = _bounty(coord, b.id)
    assert (stored.status, stored.claimed_by, stored.lapse_count) == ("open", "", 1)
    assert "taskmate_bounty_claim_lapsed" in _events(coord)
    # No cool-down: the same child may claim it again straight away.
    run(coord.async_claim_bounty(b.id, "k1"))


def test_a_claim_that_runs_out_after_the_expiry_expires_the_bounty():
    coord = _coord()
    b = _claimed(coord, claim_hours=1, expires_at=(NOW + dt.timedelta(minutes=30)).isoformat())
    _at(minutes=31)
    _sweep(coord)
    stored = _bounty(coord, b.id)
    assert stored.status == "expired" and stored.closed_at == dt_util_mock._now


def test_an_unclaimed_bounty_expires():
    coord = _coord()
    b = _post(coord, expires_at=(NOW + dt.timedelta(hours=1)).isoformat())
    _at(minutes=59)
    assert _sweep(coord) is False
    _at(hours=1)
    assert _sweep(coord) is True
    assert _bounty(coord, b.id).status == "expired"
    assert "taskmate_bounty_expired" in _events(coord)


# ── the claim count (#961) ───────────────────────────────────────────────────


def test_every_claim_from_the_board_is_counted():
    coord = _coord()
    b = _claimed(coord)
    run(coord.async_give_back_bounty(b.id, "k1"))
    run(coord.async_claim_bounty(b.id, "k2"))
    run(coord.async_release_bounty(b.id))
    assert _bounty(coord, b.id).claim_count == 2


def test_a_rejection_is_the_same_claim_not_a_new_one():
    coord = _coord()
    b = _claimed(coord)
    comp = run(coord.async_complete_bounty(b.id, "k1"))
    run(coord.async_reject_chore(comp.id))
    assert _bounty(coord, b.id).claim_count == 1


def test_a_bounty_given_back_then_expired_remembers_it_was_claimed():
    coord = _coord()
    b = _claimed(coord, expires_at=(NOW + dt.timedelta(hours=1)).isoformat())
    run(coord.async_give_back_bounty(b.id, "k1"))
    _at(hours=1)
    _sweep(coord)
    stored = _bounty(coord, b.id)
    assert (stored.status, stored.claim_count, stored.lapse_count) == ("expired", 1, 0)


def test_a_failed_claim_is_not_counted():
    coord = _coord()
    b = _claimed(coord)
    with pytest.raises(ValueError):
        run(coord.async_claim_bounty(b.id, "k2"))
    assert _bounty(coord, b.id).claim_count == 1


def test_older_records_without_a_claim_count_load_safely():
    assert Bounty.from_dict({"title": "x", "status": "expired"}).claim_count == 0
    # Every lapse was a claim, and a bounty that is (or was) held was claimed.
    assert Bounty.from_dict({"title": "x", "status": "expired", "lapse_count": 2}).claim_count == 2
    for status in ("claimed", "pending", "completed"):
        assert Bounty.from_dict({"title": "x", "status": status}).claim_count == 1
    assert Bounty.from_dict({"title": "x", "claim_count": "junk"}).claim_count == 0


def test_a_waiting_bounty_neither_lapses_nor_expires():
    coord = _coord()
    b = _claimed(coord, expires_at=(NOW + dt.timedelta(hours=1)).isoformat())
    run(coord.async_complete_bounty(b.id, "k1"))
    _at(hours=5)
    assert _sweep(coord) is False
    assert _bounty(coord, b.id).status == "pending"


def test_the_claimer_is_warned_once_before_the_claim_lapses():
    coord = _coord()
    b = _claimed(coord, claim_hours=2)
    coord.notifications.fire.reset_mock()  # the "new bounty" push
    _at(hours=1, minutes=40)
    _sweep(coord)
    coord.notifications.fire.assert_not_awaited()
    _at(hours=1, minutes=46)
    _sweep(coord)
    call = coord.notifications.fire.await_args
    assert call.args[0] == "bounty_claim_lapsing"
    assert call.args[1]["bounty_name"] == "Wash the car" and call.args[1]["minutes"] == 14
    assert call.kwargs["only_recipients"] == {"child:k1"}
    _at(hours=1, minutes=50)
    _sweep(coord)
    assert coord.notifications.fire.await_count == 1
    assert _bounty(coord, b.id).lapse_warned is True


def test_no_warning_for_a_lock_the_expiry_cut_short():
    coord = _coord()
    _claimed(coord, claim_hours=2, expires_at=(NOW + dt.timedelta(minutes=10)).isoformat())
    coord.notifications.fire.reset_mock()  # the "new bounty" push
    _sweep(coord)
    coord.notifications.fire.assert_not_awaited()


def test_sweep_with_no_bounties_touches_nothing():
    coord = _coord()
    assert _sweep(coord) is False
    coord.async_refresh.assert_not_awaited()


def test_finished_bounties_are_pruned_with_the_completion_history():
    coord = _coord()
    old = _post(coord, title="Old", expires_at=(NOW + dt.timedelta(hours=1)).isoformat())
    _at(hours=2)
    _sweep(coord)
    _at(days=91)
    fresh = _post(coord, title="Fresh")
    run(coord.async_prune_bounties())
    ids = {b.id for b in coord.storage.get_bounties()}
    assert old.id not in ids and fresh.id in ids


# ── editing and removing ─────────────────────────────────────────────────────


def test_an_open_bounty_can_be_edited_freely():
    coord = _coord()
    b = _post(coord)
    run(coord.async_update_bounty(b.id, title="Wash both cars", points=90, claim_hours=4))
    stored = _bounty(coord, b.id)
    assert (stored.title, stored.points, stored.claim_hours) == ("Wash both cars", 90, 4)


def test_once_claimed_only_points_and_expiry_can_change():
    coord = _coord()
    b = _claimed(coord, claim_hours=3)
    with pytest.raises(ValueError, match="only its points and expiry"):
        run(coord.async_update_bounty(b.id, title="Something else"))
    # Re-sending an unchanged field is not an edit.
    run(coord.async_update_bounty(b.id, title="Wash the car", points=70))
    new_expiry = NOW + dt.timedelta(hours=1)
    run(coord.async_update_bounty(b.id, expires_at=new_expiry.isoformat()))
    stored = _bounty(coord, b.id)
    assert stored.points == 70
    # The claimer's lock is re-capped at the new expiry.
    assert stored.claim_until == new_expiry


def test_history_cannot_be_edited():
    coord = _coord()
    b = _post(coord, expires_at=(NOW + dt.timedelta(hours=1)).isoformat())
    _at(hours=2)
    _sweep(coord)
    with pytest.raises(ValueError):
        run(coord.async_update_bounty(b.id, points=10))


def test_removal_waits_for_the_approval_decision():
    coord = _coord()
    b = _claimed(coord)
    comp = run(coord.async_complete_bounty(b.id, "k1"))
    with pytest.raises(ValueError, match="Approve or reject"):
        run(coord.async_remove_bounty(b.id))
    run(coord.async_approve_chore(comp.id))
    run(coord.async_remove_bounty(b.id))
    assert coord.storage.get_bounties() == []


def test_unknown_bounty_raises():
    coord = _coord()
    with pytest.raises(ValueError):
        run(coord.async_claim_bounty("nope", "k1"))


# ── a deleted child ──────────────────────────────────────────────────────────


def test_a_deleted_childs_claim_goes_back_on_the_board():
    coord = _coord()
    claimed = _claimed(coord, child="k1", title="Car", eligible_child_ids=["k1", "k2"])
    only_theirs = _post(coord, title="Hamster", eligible_child_ids=["k1"])
    run(coord.async_remove_child("k1"))
    stored = _bounty(coord, claimed.id)
    assert stored.status == "open" and stored.claimed_by == "" and stored.eligible_child_ids == ["k2"]
    # Nobody is left who could do it.
    assert _bounty(coord, only_theirs.id) is None


# ── the health report ────────────────────────────────────────────────────────


def test_a_bounty_completion_is_not_an_orphan():
    coord = _coord()
    b = _claimed(coord)
    run(coord.async_complete_bounty(b.id, "k1"))
    coord.hass.states.get = MagicMock(return_value=None)
    coord.get_rewards = MagicMock(return_value=[])
    report = coord.health_report()
    assert not [i for i in report["issues"] if i["code"] == "completion_orphan"]
