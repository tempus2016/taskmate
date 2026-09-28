"""Chore auctions: children bid the fewest points they'd accept (#982).

A parent opens an auction on one occurrence of a chore; eligible children
place sealed bids; at closing the lowest bid wins (the earliest on a tie, and
changing a bid re-times it). The winner is assigned that occurrence at their
price — read at assignment time, never written onto the chore — and no bids
leaves the chore on its normal assignment.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Auction, Child, Chore, ChoreCompletion
from custom_components.taskmate.storage import TaskMateStorage

from .conftest import dt_util_mock

UTC = timezone.utc
NOW = dt.datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC)  # a Wednesday
TOMORROW = "2026-04-23"
CLOSES = "2026-04-22T19:00:00+00:00"
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


def _chore(**kw):
    kw.setdefault("name", "Clean the bathroom")
    kw.setdefault("points", 6)
    kw.setdefault("id", "c1")
    kw.setdefault("requires_approval", False)
    return Chore(**kw)


def _coord(chores=None, children=KIDS):
    from tests.conftest import FakeStore

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {
        "children": [c.to_dict() for c in children],
        "chores": [c.to_dict() for c in (chores if chores is not None else [_chore()])],
        "completions": [],
    }
    storage._data_version = 0

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.data = {}
    coord.hass.states.get = MagicMock(return_value=None)
    coord.storage = storage
    coord.notifications = MagicMock()
    coord.notifications.fire = AsyncMock()
    coord.notifications.clear_approval = AsyncMock()
    coord.async_refresh = AsyncMock()
    coord._award_points = AsyncMock(side_effect=lambda child, pts, **kw: pts)
    coord._async_notify_pending_approval = AsyncMock()
    coord._async_advance_quests = AsyncMock()
    coord._async_evaluate_challenges = AsyncMock()
    coord.badges = None
    return coord


def _start(coord, **kw):
    kw.setdefault("closes_at", CLOSES)
    return run(
        coord.async_start_auction(
            kw.pop("chore_id", "c1"),
            kw.pop("occurrence", TOMORROW),
            kw.pop("max_points", 40),
            kw.pop("closes_at"),
            **kw,
        )
    )


def _bid(coord, auction, child_id, points):
    return run(coord.async_place_bid(auction.id, child_id, points))


def _fired(coord, event):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == event]


def _notified(coord, type_id):
    return [c for c in coord.notifications.fire.call_args_list if c.args[0] == type_id]


def _numbers(obj) -> set:
    """Every number anywhere in a payload — ids and timestamps can contain
    any digits, so a secret amount is looked for as a value, not a substring."""
    if isinstance(obj, bool):
        return set()
    if isinstance(obj, (int, float)):
        return {obj}
    if isinstance(obj, dict):
        return set().union(*(_numbers(v) for v in obj.values())) if obj else set()
    if isinstance(obj, (list, tuple)):
        return set().union(*(_numbers(v) for v in obj)) if obj else set()
    return set()


def _day(iso):
    return dt.date.fromisoformat(iso)


# ── the model ────────────────────────────────────────────────────────────────


def test_auction_round_trips_through_storage():
    a = Auction(
        chore_id="c1",
        occurrence=TOMORROW,
        max_points=40,
        min_points=5,
        closes_at=NOW,
        eligible_child_ids=["k1", "k2"],
        status="closed",
        bids={"k1": {"points": 18, "at": "2026-04-22T08:00:00Z"}},
        winner_id="k1",
        price=18,
        chore_name="Clean the bathroom",
        chore_points=6,
        created_at=NOW,
        closed_at=NOW,
    )
    assert Auction.from_dict(a.to_dict()) == a


def test_a_minimal_record_loads_with_safe_defaults():
    back = Auction.from_dict({"chore_id": "c1", "occurrence": TOMORROW, "status": "bogus", "id": "a1"})
    assert (back.status, back.max_points, back.min_points, back.bids, back.winner_id) == ("open", 1, 1, {}, "")
    assert back.notify_children is True


def test_junk_bids_and_an_oversized_minimum_are_cleaned_on_load():
    back = Auction.from_dict(
        {
            "chore_id": "c1",
            "max_points": 10,
            "min_points": 50,
            "bids": {"k1": {"points": 0, "at": "2026-04-22T08:00:00Z"}, "k2": {"points": 4}, "k3": "x"},
        }
    )
    assert back.bids == {} and back.min_points == 10


def test_import_restores_an_auctions_list():
    coord = _coord()
    coord.storage.import_data({"children": []})
    assert coord.storage.data["auctions"] == []


# ── opening ──────────────────────────────────────────────────────────────────


def test_start_records_the_occurrence_the_pool_and_a_snapshot_of_the_chore():
    coord = _coord()
    auction = _start(coord)
    stored = coord.storage.get_auction(auction.id)
    assert stored.occurrence == TOMORROW and stored.status == "open"
    assert stored.eligible_child_ids == ["k1", "k2", "k3"]  # "everyone" chore -> every child
    assert (stored.chore_name, stored.chore_points) == ("Clean the bathroom", 6)
    assert _fired(coord, "taskmate_auction_opened")
    note = _notified(coord, "auction_opened")[0]
    assert note.kwargs["only_recipients"] == {"child:k1", "child:k2", "child:k3"}


def test_start_without_telling_the_children_sends_nothing():
    coord = _coord()
    _start(coord, notify_children=False)
    assert not _notified(coord, "auction_opened")


def test_eligible_children_must_be_in_the_chores_pool():
    coord = _coord([_chore(assigned_to=["k1", "k2"], assignment_mode="alternating")])
    with pytest.raises(ValueError, match="can do this chore"):
        _start(coord, eligible_child_ids=["k3"])
    auction = _start(coord, eligible_child_ids=["k2"])
    assert auction.eligible_child_ids == ["k2"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"occurrence": "2026-04-22"}, "tomorrow onwards"),
        ({"occurrence": "not-a-date"}, "Invalid date"),
        ({"closes_at": "2026-04-22T09:00:00+00:00"}, "already in the past"),
        ({"closes_at": "2026-04-23T08:00:00+00:00"}, "before the day of the chore"),
        ({"max_points": 0}, "maximum bid"),
        ({"min_points": 41}, "minimum bid"),
        ({"closes_at": ""}, "closing time"),
    ],
)
def test_start_refuses_bad_input(kwargs, message):
    coord = _coord()
    with pytest.raises(ValueError, match=message):
        _start(coord, **kwargs)


def test_an_occurrence_the_chore_does_not_have_cannot_be_auctioned():
    coord = _coord([_chore(due_days=["saturday"])])
    with pytest.raises(ValueError, match="isn't scheduled"):
        _start(coord)
    assert _start(coord, occurrence="2026-04-25").occurrence == "2026-04-25"


@pytest.mark.parametrize(
    ("chore", "message"),
    [
        (_chore(assignment_mode="unassigned"), "unassigned"),
        (_chore(team_size=2), "teamwork"),
        (_chore(task_type="timed"), "timed"),
        (_chore(open_ended=True), "open-ended"),
        (_chore(enabled=False), "switched off"),
    ],
)
def test_chores_that_cannot_be_given_to_one_child_at_a_price_are_refused(chore, message):
    coord = _coord([chore])
    with pytest.raises(ValueError, match=message):
        _start(coord)
    assert coord.auction_occurrences("c1") == []


def test_one_live_auction_per_occurrence_but_a_no_bid_one_can_be_reopened():
    coord = _coord()
    first = _start(coord)
    with pytest.raises(ValueError, match="already has an auction"):
        _start(coord)
    assert TOMORROW not in coord.auction_occurrences("c1")
    run(coord.async_close_auction(first.id))  # no bids
    assert TOMORROW in coord.auction_occurrences("c1")
    again = _start(coord, max_points=60)
    assert again.max_points == 60


def test_occurrences_offered_are_the_next_scheduled_dates():
    coord = _coord([_chore(due_days=["saturday", "sunday"])])
    assert coord.auction_occurrences("c1")[:3] == ["2026-04-25", "2026-04-26", "2026-05-02"]


# ── bidding ──────────────────────────────────────────────────────────────────


def test_a_bid_is_sealed_and_can_be_changed_or_withdrawn():
    coord = _coord()
    auction = _start(coord)
    _bid(coord, auction, "k1", 20)
    assert coord.storage.get_auction(auction.id).bids["k1"]["points"] == 20
    _bid(coord, auction, "k1", 15)
    assert coord.storage.get_auction(auction.id).bids["k1"]["points"] == 15
    run(coord.async_withdraw_bid(auction.id, "k1"))
    assert coord.storage.get_auction(auction.id).bids == {}
    with pytest.raises(ValueError, match="haven't bid"):
        run(coord.async_withdraw_bid(auction.id, "k1"))


@pytest.mark.parametrize("points", [0, 41])
def test_a_bid_must_sit_between_the_minimum_and_the_maximum(points):
    coord = _coord()
    auction = _start(coord)
    with pytest.raises(ValueError, match="Bid between"):
        _bid(coord, auction, "k1", points)


def test_the_minimum_bid_is_enforced():
    coord = _coord()
    auction = _start(coord, min_points=5)
    with pytest.raises(ValueError, match="Bid between 5 and 40"):
        _bid(coord, auction, "k1", 4)


def test_only_eligible_children_may_bid_and_only_while_it_is_open():
    coord = _coord()
    auction = _start(coord, eligible_child_ids=["k1"])
    with pytest.raises(ValueError, match="isn't for you"):
        _bid(coord, auction, "k2", 10)
    _at(hours=10)  # past the 19:00 close, before the sweep has run
    with pytest.raises(ValueError, match="closed"):
        _bid(coord, auction, "k1", 10)


def test_the_bid_event_never_carries_the_amount():
    coord = _coord()
    auction = _start(coord)
    _bid(coord, auction, "k1", 23)
    payload = _fired(coord, "taskmate_auction_bid")[0]
    assert payload["child_id"] == "k1" and payload["bid_count"] == 1
    assert 23 not in payload.values() and "price" not in payload


# ── closing ──────────────────────────────────────────────────────────────────


def test_the_lowest_bid_wins_at_closing_time():
    coord = _coord()
    auction = _start(coord)
    _bid(coord, auction, "k1", 25)
    _bid(coord, auction, "k2", 18)
    _at(hours=9)
    assert run(coord.async_sweep_auctions()) is True
    closed = coord.storage.get_auction(auction.id)
    assert (closed.status, closed.winner_id, closed.price) == ("closed", "k2", 18)
    assert _fired(coord, "taskmate_auction_closed")[0]["price"] == 18
    result = _notified(coord, "auction_result")[0]
    assert "Vaiha won" in result.args[1]["result_text"]


def test_a_tie_goes_to_the_earliest_bid_and_changing_a_bid_re_times_it():
    coord = _coord()
    auction = _start(coord)
    _bid(coord, auction, "k1", 20)
    _at(minutes=5)
    _bid(coord, auction, "k2", 20)
    _at(minutes=10)
    _bid(coord, auction, "k1", 21)  # k1 changes...
    _at(minutes=15)
    _bid(coord, auction, "k1", 20)  # ...and back: now the later bid of the two
    run(coord.async_close_auction(auction.id))
    assert coord.storage.get_auction(auction.id).winner_id == "k2"


def test_re_sealing_the_same_number_keeps_the_place_in_the_queue():
    coord = _coord()
    auction = _start(coord)
    _bid(coord, auction, "k1", 20)
    _at(minutes=5)
    _bid(coord, auction, "k2", 20)
    _at(minutes=10)
    _bid(coord, auction, "k1", 20)
    run(coord.async_close_auction(auction.id))
    assert coord.storage.get_auction(auction.id).winner_id == "k1"


def test_no_bids_closes_without_a_winner():
    coord = _coord()
    auction = _start(coord)
    run(coord.async_close_auction(auction.id))
    closed = coord.storage.get_auction(auction.id)
    assert (closed.status, closed.winner_id, closed.price) == ("closed", "", 0)
    assert "no bids" in _notified(coord, "auction_result")[0].args[1]["result_text"]
    with pytest.raises(ValueError, match="already closed"):
        run(coord.async_close_auction(auction.id))


def test_an_auction_that_closed_while_ha_was_off_is_settled_on_the_next_sweep():
    coord = _coord()
    auction = _start(coord)
    _bid(coord, auction, "k3", 12)
    _at(days=3)  # HA was down across the closing time and the occurrence
    coord.async_refresh.reset_mock()
    run(coord.async_sweep_auctions(refresh=False))  # as at startup
    assert coord.storage.get_auction(auction.id).winner_id == "k3"
    coord.async_refresh.assert_not_awaited()


def test_the_reminder_goes_out_once_within_the_last_hour():
    coord = _coord()
    auction = _start(coord)
    assert run(coord.async_sweep_auctions()) is False
    _at(hours=8, minutes=10)  # 50 minutes before the 19:00 close
    assert run(coord.async_sweep_auctions()) is True
    reminders = _notified(coord, "auction_closing")
    assert {c.kwargs["only_recipients"].pop() for c in reminders} == {"child:k1", "child:k2", "child:k3"}
    assert reminders[0].args[1]["minutes"] == 50
    assert run(coord.async_sweep_auctions()) is False
    assert coord.storage.get_auction(auction.id).reminder_sent is True


def test_no_reminder_for_a_short_auction_or_one_that_tells_nobody():
    coord = _coord()
    _at(hours=8, minutes=30)
    _start(coord)  # opens 30 minutes before it closes
    _start(coord, occurrence="2026-04-24", notify_children=False)
    _at(hours=8, minutes=45)
    run(coord.async_sweep_auctions())
    assert not _notified(coord, "auction_closing")


def test_the_timer_is_armed_for_the_next_deadline():
    coord = _coord()
    assert coord._next_auction_deadline() is None
    _start(coord)
    assert coord._next_auction_deadline() == dt.datetime(2026, 4, 22, 18, 0, tzinfo=UTC)  # the reminder
    _start(coord, occurrence="2026-04-24", notify_children=False, closes_at="2026-04-22T12:00:00+00:00")
    assert coord._next_auction_deadline() == dt.datetime(2026, 4, 22, 12, 0, tzinfo=UTC)


# ── cancelling ───────────────────────────────────────────────────────────────


def test_cancelling_a_live_auction_tells_only_the_bidders():
    coord = _coord()
    auction = _start(coord)
    _bid(coord, auction, "k1", 10)
    run(coord.async_cancel_auction(auction.id))
    assert coord.storage.get_auction(auction.id).status == "cancelled"
    note = _notified(coord, "auction_result")[0]
    assert note.kwargs["only_recipients"] == {"child:k1"} and "called off" in note.args[1]["result_text"]


def test_cancelling_a_won_auction_hands_the_occurrence_back():
    coord = _coord()
    auction = _start(coord)
    _bid(coord, auction, "k1", 10)
    run(coord.async_close_auction(auction.id))
    chore = coord.storage.get_chore("c1")
    assert coord.auction_winner(chore, _day(TOMORROW)) == "k1"
    run(coord.async_cancel_auction(auction.id))
    assert coord.auction_winner(chore, _day(TOMORROW)) == ""
    with pytest.raises(ValueError, match="already cancelled"):
        run(coord.async_cancel_auction(auction.id))


def test_a_past_occurrence_cannot_be_cancelled():
    coord = _coord()
    auction = _start(coord)
    _bid(coord, auction, "k1", 10)
    run(coord.async_close_auction(auction.id))
    _at(days=2)
    with pytest.raises(ValueError, match="already happened"):
        run(coord.async_cancel_auction(auction.id))


# ── the won occurrence ───────────────────────────────────────────────────────


def _won(coord, child_id="k2", points=9, occurrence=TOMORROW):
    auction = _start(coord, occurrence=occurrence)
    _bid(coord, auction, child_id, points)
    run(coord.async_close_auction(auction.id))
    return auction


@pytest.mark.parametrize("mode", ["everyone", "alternating", "random", "balanced", "first_come"])
def test_the_winner_is_the_only_active_child_on_that_day_in_every_mode(mode):
    coord = _coord([_chore(assignment_mode=mode, assigned_to=["k1", "k2", "k3"])])
    _won(coord)
    chore = coord.storage.get_chore("c1")
    assert coord._compute_active_children(chore, _day(TOMORROW)) == ["k2"]
    other_day = coord._compute_active_children(chore, _day("2026-04-24"))
    assert other_day != ["k2"] or mode in ("alternating", "random", "balanced")


def test_the_occurrence_is_hidden_from_everyone_but_the_winner_on_the_day():
    coord = _coord()  # an "everyone" chore
    _won(coord)
    chore = coord.storage.get_chore("c1")
    assert coord.is_chore_available_for_child(chore, "k1") is True  # today is untouched
    _at(days=1)
    assert coord.is_chore_available_for_child(chore, "k2") is True
    assert coord.is_chore_available_for_child(chore, "k1") is False
    assert [c.id for c in coord.get_due_chores_for_child("k1")] == []
    assert [c.id for c in coord.get_due_chores_for_child("k2")] == ["c1"]


def test_the_winner_is_paid_their_bid_and_nobody_else_can_complete_it():
    coord = _coord([_chore(points=6, difficulty="hard")])
    _won(coord, "k2", 9)
    _at(days=1)
    assert run(coord.async_complete_chore("c1", "k1")) is None
    completion = run(coord.async_complete_chore("c1", "k2"))
    assert completion.submitted_points == 9 and completion.points_awarded == 9
    coord._award_points.assert_awaited_with(coord.get_child("k2"), 9, chore_id="c1")


def test_a_pending_winners_completion_is_approved_at_the_bid():
    coord = _coord([_chore(points=6, requires_approval=True)])
    _won(coord, "k2", 9)
    _at(days=1)
    completion = run(coord.async_complete_chore("c1", "k2"))
    assert completion.approved is False and completion.submitted_points == 9
    run(coord.async_approve_chore(completion.id))
    approved = next(c for c in coord.storage.get_completions() if c.id == completion.id)
    assert approved.points_awarded == 9


def test_the_day_after_the_chore_is_back_on_its_normal_assignment():
    coord = _coord()
    _won(coord)
    _at(days=2)
    chore = coord.storage.get_chore("c1")
    assert coord.is_chore_available_for_child(chore, "k1") is True
    assert coord.auction_price_for(chore, "k2") is None


def test_the_winner_owes_a_mandatory_occurrence_and_nobody_else_does():
    coord = _coord([_chore(mandatory=True)])
    _won(coord)
    chore = coord.storage.get_chore("c1")
    assert coord._mandatory_owers(chore, _day(TOMORROW)) == ["k2"]
    assert coord._mandatory_owers(chore, _day("2026-04-24")) == ["k1", "k2", "k3"]


def test_the_streaks_due_set_follows_the_win():
    coord = _coord([_chore(assignment_mode="alternating", assigned_to=["k1", "k2"])])
    _won(coord, "k2")
    day = _day(TOMORROW)
    assert "c1" in coord._due_chore_ids_for_child("k2", day, include_rotation=False)
    assert "c1" not in coord._due_chore_ids_for_child("k1", day, include_rotation=True)


def test_a_deleted_winner_hands_the_occurrence_back():
    coord = _coord()
    _won(coord, "k2")
    coord.storage._data["children"] = [c for c in coord.storage._data["children"] if c["id"] != "k2"]
    chore = coord.storage.get_chore("c1")
    assert coord.auction_winner(chore, _day(TOMORROW)) == ""


def test_the_win_follows_its_occurrence_when_it_is_moved_on_the_calendar():
    coord = _coord()
    _won(coord, "k2")
    chore = coord.storage.get_chore("c1")
    chore.moved_occurrences = {TOMORROW: "2026-04-25"}
    assert coord.auction_winner(chore, _day("2026-04-25")) == "k2"


def test_a_won_chore_cannot_be_swapped_on_the_day():
    coord = _coord([_chore(assignment_mode="alternating", assigned_to=["k1", "k2"])])
    _won(coord, "k2")
    _at(days=1)
    with pytest.raises(ValueError, match="won at auction"):
        run(coord.async_request_swap("c1", "k1"))


def test_a_late_settlement_on_the_day_repoints_the_rotation():
    coord = _coord([_chore(assignment_mode="alternating", assigned_to=["k1", "k2", "k3"])])
    auction = _start(coord)
    _bid(coord, auction, "k3", 5)
    _at(days=1, hours=1)  # HA came back mid-morning on the day itself
    run(coord.async_sweep_auctions(refresh=False))
    assert coord.storage.get_chore("c1").assignment_current_child_id == "k3"


# ── what each audience sees ──────────────────────────────────────────────────


def test_a_child_sees_only_their_own_bid_and_the_count():
    coord = _coord()
    auction = _start(coord, eligible_child_ids=["k1", "k2"])
    _bid(coord, auction, "k1", 31)
    _bid(coord, auction, "k2", 17)
    view = coord.auctions_for_child("k1")
    assert [(a["my_bid"], a["bid_count"]) for a in view] == [(31, 2)]
    assert 17 not in _numbers(view) and "bids" not in view[0]
    assert coord.auctions_for_child("k3") == []  # not eligible: not shown at all


def test_the_public_digest_carries_counts_never_amounts():
    coord = _coord()
    auction = _start(coord)
    _bid(coord, auction, "k1", 31)
    digest = coord.auctions_public_state()
    assert digest[0]["bids"] == 1
    assert 31 not in _numbers(digest) and "bidders" not in digest[0]


def test_results_stay_on_the_card_for_a_day_then_leave():
    coord = _coord()
    auction = _start(coord)
    _bid(coord, auction, "k1", 11)
    run(coord.async_close_auction(auction.id))
    view = coord.auctions_for_child("k2")
    assert view[0]["winner_id"] == "k1" and view[0]["price"] == 11 and view[0]["my_bid"] is None
    _at(hours=25)
    assert coord.auctions_for_child("k2") == []


def test_parents_see_every_bid_ranked_and_how_the_chore_went():
    coord = _coord([_chore(requires_approval=True)])
    auction = _start(coord)
    _bid(coord, auction, "k1", 30)
    _bid(coord, auction, "k2", 12)
    state = coord.auctions_state()[0]
    assert [(b["child_id"], b["points"]) for b in state["bids"]] == [("k2", 12), ("k1", 30)]
    run(coord.async_close_auction(auction.id))
    assert coord.auctions_state()[0]["chore_status"] == "todo"
    _at(days=1)
    completion = run(coord.async_complete_chore("c1", "k2"))
    assert coord.auctions_state()[0]["chore_status"] == "pending"
    run(coord.async_approve_chore(completion.id))
    state = coord.auctions_state()[0]
    assert (state["chore_status"], state["points_awarded"]) == ("done", 12)


def test_an_undone_won_occurrence_reads_as_missed_afterwards():
    coord = _coord()
    _won(coord)
    _at(days=2)
    assert coord.auctions_state()[0]["chore_status"] == "missed"


# ── housekeeping ─────────────────────────────────────────────────────────────


def test_deleting_a_child_drops_their_bids_and_eligibility():
    coord = _coord()
    auction = _start(coord, eligible_child_ids=["k1", "k2"])
    only_k1 = _start(coord, occurrence="2026-04-24", eligible_child_ids=["k1"])
    _bid(coord, auction, "k1", 10)
    coord.remove_child_from_auctions("k1")
    assert coord.storage.get_auction(auction.id).eligible_child_ids == ["k2"]
    assert coord.storage.get_auction(auction.id).bids == {}
    assert coord.storage.get_auction(only_k1.id) is None


def test_deleting_a_chore_drops_its_live_auctions_but_keeps_history():
    coord = _coord()
    won = _won(coord, "k1")
    live = _start(coord, occurrence="2026-04-24")
    coord.remove_chore_from_auctions("c1")
    assert coord.storage.get_auction(live.id) is None
    assert coord.storage.get_auction(won.id).chore_name == "Clean the bathroom"


def test_finished_auctions_are_pruned_with_the_history():
    coord = _coord()
    old = _won(coord, "k1")
    live = _start(coord, occurrence="2026-04-24")
    _at(days=120)
    run(coord.async_prune_auctions())
    assert coord.storage.get_auction(old.id) is None
    assert coord.storage.get_auction(live.id) is not None


def test_the_winning_completion_is_a_normal_completion():
    """No auction marker on the completion: undo, reject and history treat it
    like any other."""
    coord = _coord()
    _won(coord, "k2", 7)
    _at(days=1)
    completion = run(coord.async_complete_chore("c1", "k2"))
    assert set(completion.to_dict()) == set(ChoreCompletion(chore_id="x", child_id="y", completed_at=NOW).to_dict())
