"""A child's undo can never create points, and every derived bonus follows the
completion it was earned by when that completion is reversed.

These drive the real coordinator against real storage.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Challenge, Child, ChoreCompletion, PointsTransaction
from custom_components.taskmate.storage import TaskMateStorage
from tests.conftest import FakeHass, FakeStore, dt_util_mock

START = dt_util_mock._now
UTC = dt.timezone.utc


@pytest.fixture
def clock(monkeypatch):
    class Clock:
        def set(self, when):
            monkeypatch.setattr(dt_util_mock, "_now", when)

        def advance(self, **kwargs):
            self.set(dt_util_mock._now + timedelta(**kwargs))

    c = Clock()
    c.set(START)
    return c


async def _make_system(window: int = 60):
    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    await storage.async_load()
    storage.set_setting("weekend_multiplier", "1")
    storage.set_setting("streak_milestones_enabled", "false")
    storage.set_setting("chore_undo_seconds", window)

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = FakeHass()
    coord.hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()
    coord.data = {}
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    coord._async_notify_pending_approval = AsyncMock()
    coord.notifications = AsyncMock()
    coord.notifications._has_outstanding_chores_today = lambda _cid: True
    coord.async_record_audit = AsyncMock()
    return coord, storage


def _get(storage, completion_id):
    return next((c for c in storage.get_completions() if c.id == completion_id), None)


# ── the undo balance guard ───────────────────────────────────────────────────


def test_undo_refused_once_the_points_have_moved_on(clock):
    """Earn, move the points into a wish, undo: the undo must be refused."""

    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        chore = await coord.async_add_chore("Dishes", points=10, assigned_to=[child.id], requires_approval=False)
        wish = await coord.async_add_wish(child.id, "Lego", target=100)
        await coord.async_approve_wish(wish.id)

        completion = await coord.async_complete_chore(chore.id, child.id)
        assert storage.get_child(child.id).points == 10
        await coord.async_move_points_to_wish(wish.id, child.id, 10)
        assert storage.get_child(child.id).points == 0

        with pytest.raises(ValueError, match="already been spent"):
            await coord.async_undo_chore(completion.id)

        # Nothing was reversed: the completion stands and the balance is intact.
        assert _get(storage, completion.id) is not None
        assert storage.get_child(child.id).points == 0
        assert storage.get_wishes()[0].saved == 10

    asyncio.run(scenario())


def test_undo_still_allowed_while_the_points_are_there(clock):
    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        chore = await coord.async_add_chore("Dishes", points=10, assigned_to=[child.id], requires_approval=False)
        completion = await coord.async_complete_chore(chore.id, child.id)
        await coord.async_undo_chore(completion.id)
        assert _get(storage, completion.id) is None
        assert storage.get_child(child.id).points == 0

    asyncio.run(scenario())


def test_undo_allowed_after_a_partial_spend_when_enough_remains(clock):
    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        await coord.async_add_points(child.id, 50, "seed")
        chore = await coord.async_add_chore("Dishes", points=10, assigned_to=[child.id], requires_approval=False)
        wish = await coord.async_add_wish(child.id, "Lego", target=100)
        await coord.async_approve_wish(wish.id)
        completion = await coord.async_complete_chore(chore.id, child.id)
        await coord.async_move_points_to_wish(wish.id, child.id, 40)
        # 20 left, 10 owed: fine.
        await coord.async_undo_chore(completion.id)
        assert storage.get_child(child.id).points == 10

    asyncio.run(scenario())


def test_pending_submission_can_always_be_withdrawn(clock):
    """Nothing has been paid for a pending submission, so nothing is owed."""

    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        chore = await coord.async_add_chore("Dishes", points=10, assigned_to=[child.id], requires_approval=True)
        completion = await coord.async_complete_chore(chore.id, child.id)
        assert storage.get_child(child.id).points == 0
        await coord.async_undo_chore(completion.id)
        assert _get(storage, completion.id) is None

    asyncio.run(scenario())


def test_parent_reject_is_not_subject_to_the_balance_guard(clock):
    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        chore = await coord.async_add_chore("Dishes", points=10, assigned_to=[child.id], requires_approval=False)
        wish = await coord.async_add_wish(child.id, "Lego", target=100)
        await coord.async_approve_wish(wish.id)
        completion = await coord.async_complete_chore(chore.id, child.id)
        await coord.async_move_points_to_wish(wish.id, child.id, 10)
        await coord.async_reject_chore(completion.id)
        assert _get(storage, completion.id) is None

    asyncio.run(scenario())


def test_owed_includes_the_bonus_subtasks_of_the_day(clock):
    async def scenario():
        from custom_components.taskmate.models import BonusSubTask

        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        chore = await coord.async_add_chore("Dishes", points=10, assigned_to=[child.id], requires_approval=False)
        chore.bonus_subtasks = [BonusSubTask(name="Dry", points=5, id="sub1")]
        storage.update_chore(chore)
        completion = await coord.async_complete_chore(chore.id, child.id)
        await coord.async_complete_bonus_subtask(chore.id, "sub1", child.id)
        assert storage.get_child(child.id).points == 15
        wish = await coord.async_add_wish(child.id, "Lego", target=100)
        await coord.async_approve_wish(wish.id)
        await coord.async_move_points_to_wish(wish.id, child.id, 8)
        # 7 left but 15 owed.
        with pytest.raises(ValueError, match="already been spent"):
            await coord.async_undo_chore(completion.id)

    asyncio.run(scenario())


# ── challenge bonuses follow the completion ─────────────────────────────────


def _challenge_coord(challenges, child, completions):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    progress: dict = {}
    storage = MagicMock()
    storage.get_challenges = MagicMock(return_value=challenges)
    storage.get_completions = MagicMock(side_effect=lambda: list(completions))
    storage.get_challenge_child_progress = MagicMock(side_effect=lambda cid, kid: progress.get(cid, {}).get(kid, {}))
    storage.set_challenge_child_progress = MagicMock(
        side_effect=lambda cid, kid, p: progress.setdefault(cid, {}).__setitem__(kid, p)
    )
    storage.update_child = MagicMock()
    storage.add_points_transaction = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.get_child = MagicMock(return_value=child)
    coord.async_refresh = AsyncMock()
    coord.notifications = MagicMock()
    coord.notifications.fire = AsyncMock()
    coord._maybe_level_up = AsyncMock()
    coord._celebrate = AsyncMock()
    return coord


NOW = dt.datetime(2026, 6, 17, 10, tzinfo=UTC)


def _comp(child_id, pts=10, cid=None):
    return ChoreCompletion(chore_id="x", child_id=child_id, completed_at=NOW, approved=True, points_awarded=pts, id=cid)


def _run(coro):
    with (
        patch("homeassistant.util.dt.now", return_value=NOW),
        patch("homeassistant.util.dt.as_local", side_effect=lambda d: d),
    ):
        return asyncio.run(coro)


def test_challenge_bonus_is_taken_back_when_the_target_is_no_longer_met():
    ch = Challenge(name="3 today", scope="daily", metric="chores", target=3, bonus_points=15, id="c1")
    child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
    comps = [_comp("kid", cid="a"), _comp("kid", cid="b"), _comp("kid", cid="c")]
    coord = _challenge_coord([ch], child, comps)

    async def go():
        await coord._async_evaluate_challenges("kid")
        assert child.points == 15
        # The child undoes one; it leaves the metric.
        comps.pop()
        await coord._async_reverse_challenges("kid")

    _run(go())
    assert child.points == 0
    prog = coord.storage.get_challenge_child_progress("c1", "kid")
    assert prog["awarded"] is False
    txn = coord.storage.add_points_transaction.call_args_list[-1]
    assert txn.args[0].points == -15
    assert txn.kwargs.get("reverses_season") is True


def test_challenge_bonus_stays_while_the_target_still_holds():
    ch = Challenge(name="2 today", scope="daily", metric="chores", target=2, bonus_points=15, id="c1")
    child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
    comps = [_comp("kid", cid="a"), _comp("kid", cid="b"), _comp("kid", cid="c")]
    coord = _challenge_coord([ch], child, comps)

    async def go():
        await coord._async_evaluate_challenges("kid")
        comps.pop()
        await coord._async_reverse_challenges("kid")

    _run(go())
    assert child.points == 15


def test_challenge_can_be_earned_again_after_a_reversal():
    ch = Challenge(name="2 today", scope="daily", metric="chores", target=2, bonus_points=15, id="c1")
    child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
    comps = [_comp("kid", cid="a"), _comp("kid", cid="b")]
    coord = _challenge_coord([ch], child, comps)

    async def go():
        await coord._async_evaluate_challenges("kid")
        comps.pop()
        await coord._async_reverse_challenges("kid")
        assert child.points == 0
        comps.append(_comp("kid", cid="c"))
        await coord._async_evaluate_challenges("kid")

    _run(go())
    assert child.points == 15


def test_challenge_refund_owed_is_a_dry_run():
    ch = Challenge(name="3 today", scope="daily", metric="chores", target=3, bonus_points=15, id="c1")
    child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
    comps = [_comp("kid", cid="a"), _comp("kid", cid="b"), _comp("kid", cid="c")]
    coord = _challenge_coord([ch], child, comps)

    async def go():
        await coord._async_evaluate_challenges("kid")
        assert coord._challenge_refund_owed("kid", {"c"}) == 15
        assert coord._challenge_refund_owed("kid", set()) == 0

    _run(go())
    assert child.points == 15


def test_undo_through_the_coordinator_reverses_a_challenge_bonus(clock):
    """End to end: the farming loop (complete, collect, undo) nets zero."""

    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        chore = await coord.async_add_chore(
            "Dishes", points=10, assigned_to=[child.id], requires_approval=False, daily_limit=5
        )
        await coord.async_create_challenge(name="2 today", scope="daily", metric="chores", target=2, bonus_points=50)
        first = await coord.async_complete_chore(chore.id, child.id)
        second = await coord.async_complete_chore(chore.id, child.id)
        assert storage.get_child(child.id).points == 70
        await coord.async_undo_chore(second.id)
        assert storage.get_child(child.id).points == 10
        await coord.async_undo_chore(first.id)
        assert storage.get_child(child.id).points == 0
        assert storage.get_season_points(START.strftime("%Y-%m")).get(child.id, 0) == 0

    asyncio.run(scenario())


def test_undo_of_a_challenge_funded_completion_is_refused_once_spent(clock):
    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        chore = await coord.async_add_chore(
            "Dishes", points=10, assigned_to=[child.id], requires_approval=False, daily_limit=5
        )
        await coord.async_create_challenge(name="2 today", scope="daily", metric="chores", target=2, bonus_points=50)
        await coord.async_complete_chore(chore.id, child.id)
        second = await coord.async_complete_chore(chore.id, child.id)
        wish = await coord.async_add_wish(child.id, "Lego", target=100)
        await coord.async_approve_wish(wish.id)
        await coord.async_move_points_to_wish(wish.id, child.id, 55)
        # 15 left; undoing the second owes 10 + the 50 challenge bonus.
        with pytest.raises(ValueError, match="already been spent"):
            await coord.async_undo_chore(second.id)

    asyncio.run(scenario())


# ── quest bonuses are keyed on the completion that earned them ───────────────


def test_quest_rewinds_only_for_the_completion_that_advanced_it(clock):
    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        chore = await coord.async_add_chore(
            "Dishes", points=10, assigned_to=[child.id], requires_approval=False, daily_limit=3
        )
        await coord.async_create_quest(name="Q", steps=[chore.id], bonus_points=25, repeatable=False)
        first = await coord.async_complete_chore(chore.id, child.id)
        assert storage.get_child(child.id).points == 35
        second = await coord.async_complete_chore(chore.id, child.id)
        assert storage.get_child(child.id).points == 45
        # Undoing the second (which did not move the quest) leaves the bonus.
        await coord.async_undo_chore(second.id)
        assert storage.get_child(child.id).points == 35
        # Undoing the first takes the quest bonus with it.
        await coord.async_undo_chore(first.id)
        assert storage.get_child(child.id).points == 0

    asyncio.run(scenario())


def test_undo_owing_a_quest_bonus_is_refused_once_spent(clock):
    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        chore = await coord.async_add_chore("Dishes", points=10, assigned_to=[child.id], requires_approval=False)
        await coord.async_create_quest(name="Q", steps=[chore.id], bonus_points=25, repeatable=True)
        completion = await coord.async_complete_chore(chore.id, child.id)
        assert storage.get_child(child.id).points == 35
        wish = await coord.async_add_wish(child.id, "Lego", target=100)
        await coord.async_approve_wish(wish.id)
        await coord.async_move_points_to_wish(wish.id, child.id, 30)
        with pytest.raises(ValueError, match="already been spent"):
            await coord.async_undo_chore(completion.id)

    asyncio.run(scenario())


# ── season tally comes down with a reversal ──────────────────────────────────


@pytest.mark.asyncio
async def test_reversal_rows_reduce_the_season_tally(hass):
    s = TaskMateStorage(hass, "season-rev")
    await s.async_load()
    when = dt.datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
    s.add_points_transaction(PointsTransaction(child_id="k1", points=10, created_at=when))
    s.add_points_transaction(PointsTransaction(child_id="k1", points=-10, created_at=when), reverses_season=True)
    assert s.get_season_points("2026-04").get("k1", 0) == 0
    # A plain negative row (penalty, spend) still leaves the tally alone.
    s.add_points_transaction(PointsTransaction(child_id="k1", points=10, created_at=when))
    s.add_points_transaction(PointsTransaction(child_id="k1", points=-4, created_at=when))
    assert s.get_season_points("2026-04")["k1"] == 10
    # Never below zero.
    s.add_points_transaction(PointsTransaction(child_id="k1", points=-99, created_at=when), reverses_season=True)
    assert s.get_season_points("2026-04")["k1"] == 0


# ── roulette multiplier pays once ────────────────────────────────────────────


def test_roulette_multiplier_pays_once_per_day_and_returns_on_undo(clock):
    async def scenario():
        coord, storage = await _make_system()
        storage.set_setting("roulette_enabled", "true")
        storage.set_setting("roulette_multiplier", 2)
        child = await coord.async_add_child("Alice")
        chore = await coord.async_add_chore(
            "Dishes", points=10, assigned_to=[child.id], requires_approval=False, daily_limit=3
        )
        await coord.async_spin_roulette(child.id)
        first = await coord.async_complete_chore(chore.id, child.id)
        assert first.points_awarded == 20
        second = await coord.async_complete_chore(chore.id, child.id)
        assert second.points_awarded == 10
        await coord.async_undo_chore(first.id)
        third = await coord.async_complete_chore(chore.id, child.id)
        assert third.points_awarded == 20

    asyncio.run(scenario())


# ── bonus sub-tasks wait with their chore ────────────────────────────────────


def test_bonus_subtask_waits_when_the_chore_needs_a_photo(clock):
    async def scenario():
        from custom_components.taskmate.models import BonusSubTask

        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        chore = await coord.async_add_chore("Dishes", points=10, assigned_to=[child.id], requires_approval=False)
        chore.require_photo = True
        chore.bonus_subtasks = [BonusSubTask(name="Dry", points=5, id="sub1")]
        storage.update_chore(chore)
        await coord.async_complete_chore(chore.id, child.id, photo_url="/api/taskmate/photo/" + "a" * 32 + ".jpg")
        sub = await coord.async_complete_bonus_subtask(chore.id, "sub1", child.id)
        assert sub.approved is False
        assert storage.get_child(child.id).points == 0

    asyncio.run(scenario())
