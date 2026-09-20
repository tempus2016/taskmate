"""An approval pays what the submission was worth when it was made.

Approval used to re-derive the award from the chore, which reads the chore's
*current* points — so an edit made while the work sat in the review queue
changed the price after the fact — and silently dropped the speed bonus and
roulette multiplier that were already baked into the figure the child saw.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import BonusSubTask
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc


def _now():
    return dt.datetime(2024, 3, 20, 12, 0, 0, tzinfo=UTC)


async def _make_system():
    from tests.conftest import FakeHass, FakeStore

    hass = FakeHass()
    hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    await storage.async_load()

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.data = {}
    coord.storage = storage
    coord._unsub_midnight = None
    coord._unsub_prune = None
    coord._unsub_availability = None
    coord._dt_now = _now()
    coord.async_refresh = AsyncMock()
    coord._async_notify_pending_approval = AsyncMock()
    notifications = AsyncMock()
    notifications._has_outstanding_chores_today = lambda _cid: True
    coord.notifications = notifications
    return coord, storage


def _run(coro_factory):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro_factory())
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def _stored(coord, completion_id):
    return next(c for c in coord.storage.get_completions() if c.id == completion_id)


async def _pending(coord, points=10, **chore_kwargs):
    child = await coord.async_add_child("Alice")
    chore = await coord.async_add_chore(
        "Tidy up",
        points=points,
        requires_approval=True,
        schedule_mode="specific_days",
        assigned_to=[child.id],
        **chore_kwargs,
    )
    completion = await coord.async_complete_chore(chore.id, child.id)
    assert completion is not None and completion.approved is False
    return child, chore, completion


# ── the chore is edited while the work waits in the queue ────────────────


def test_a_chore_repriced_while_pending_still_pays_the_promised_award():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _storage = await _make_system()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            child, chore, completion = await _pending(coord, points=10)
            chore.points = 1
            await coord.async_update_chore(chore)
            await coord.async_approve_chore(completion.id)
            return coord.get_child(child.id).points, _stored(coord, completion.id).points_awarded

    points, awarded = _run(scenario)
    assert awarded == 10
    assert points == 10


def test_the_submission_records_what_it_was_worth():
    async def scenario():
        coord, _storage = await _make_system()
        import custom_components.taskmate.coordinator as _mod

        with patch.object(_mod.dt_util, "now", return_value=_now()):
            _child, _chore, completion = await _pending(coord, points=10)
            return _stored(coord, completion.id).submitted_points

    assert _run(scenario) == 10


# ── bonuses that were in the number the child saw ────────────────────────


def test_a_speed_bonus_earned_at_submission_survives_approval():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _storage = await _make_system()
        deadline = (_now() + dt.timedelta(hours=2)).isoformat()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            child, _chore, completion = await _pending(coord, points=10, deadline_at=deadline, speed_bonus_points=5)
            stored = _stored(coord, completion.id)
            await coord.async_approve_chore(completion.id)
            return stored.submitted_points, coord.get_child(child.id).points

    submitted, points = _run(scenario)
    assert submitted == 15  # 10 for the chore, 5 for beating the deadline
    assert points == 15


def test_a_roulette_multiplier_earned_at_submission_survives_approval():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _storage = await _make_system()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            child = await coord.async_add_child("Alice")
            chore = await coord.async_add_chore(
                "Tidy up",
                points=10,
                requires_approval=True,
                schedule_mode="specific_days",
                assigned_to=[child.id],
            )
            coord.storage.set_setting(
                "roulette_state",
                {child.id: {"chore_id": chore.id, "multiplier": 2.0, "date": _now().date().isoformat()}},
            )
            completion = await coord.async_complete_chore(chore.id, child.id)
            # The daily pick has moved on by the time the parent reviews it.
            coord.storage.set_setting("roulette_state", {})
            await coord.async_approve_chore(completion.id)
            return coord.get_child(child.id).points

    assert _run(scenario) == 20


# ── the parent still has the last word ───────────────────────────────────


def test_an_explicit_override_still_beats_the_recorded_award():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _storage = await _make_system()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            child, _chore, completion = await _pending(coord, points=10)
            await coord.async_approve_chore(completion.id, points=25)
            return coord.get_child(child.id).points

    assert _run(scenario) == 25


# ── records written before the award was stored ──────────────────────────


def test_a_completion_with_no_recorded_award_falls_back_to_the_chore():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _storage = await _make_system()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            child, _chore, completion = await _pending(coord, points=10)
            legacy = _stored(coord, completion.id)
            legacy.submitted_points = None
            coord.storage.update_completion(legacy)
            await coord.async_approve_chore(completion.id)
            return coord.get_child(child.id).points

    assert _run(scenario) == 10


def test_a_bonus_subtask_keeps_the_award_it_was_submitted_at():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _storage = await _make_system()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            child = await coord.async_add_child("Alice")
            chore = await coord.async_add_chore(
                "Tidy up",
                points=10,
                requires_approval=True,
                schedule_mode="specific_days",
                assigned_to=[child.id],
            )
            chore.bonus_subtasks = [BonusSubTask(id="sub1", name="Hoover too", points=7)]
            await coord.async_update_chore(chore)
            await coord.async_complete_chore(chore.id, child.id)
            bonus = await coord.async_complete_bonus_subtask(chore.id, "sub1", child.id)
            chore.bonus_subtasks[0].points = 1
            await coord.async_update_chore(chore)
            before = coord.get_child(child.id).points
            await coord.async_approve_chore(bonus.id)
            return before, coord.get_child(child.id).points

    before, after = _run(scenario)
    assert after - before == 7


# ── what the parent sees before approving ────────────────────────────────


def test_the_pending_review_shows_the_promised_award():
    """Through the real sensor builder, not just the helper behind it."""
    from homeassistant.util import dt as dt_util

    from custom_components.taskmate import sensor as sensor_module
    from custom_components.taskmate.models import Child, Chore, ChoreCompletion

    today = dt_util.now()
    chore = Chore(name="Tidy up", points=1, id="c")  # since re-priced down from 15
    child = Child(name="Alice", id="k")
    promised = ChoreCompletion(chore_id="c", child_id="k", completed_at=today, submitted_points=15, id="p1")
    legacy = ChoreCompletion(chore_id="c", child_id="k", completed_at=today, id="p2")
    approved = ChoreCompletion(
        chore_id="c", child_id="k", completed_at=today, approved=True, points_awarded=15, submitted_points=15, id="p3"
    )
    common = {
        "child_lookup": {"k": child},
        "chore_lookup": {"c": chore},
        "all_completions": [promised, legacy, approved],
    }

    by_id = {row["completion_id"]: row["points"] for row in sensor_module._build_todays_completions(common)}
    assert by_id["p1"] == 15  # what the child was promised
    assert by_id["p2"] == 1  # nothing recorded; fall back to the chore
    assert by_id["p3"] == 15  # already approved: what it actually paid

    recent = {row["completion_id"]: row["points"] for row in sensor_module._build_recent_completions(common)}
    assert recent["p1"] == 15
    assert recent["p2"] == 1


# ── an approved completion is worth what it paid ─────────────────────────


def test_history_shows_what_an_approved_completion_actually_paid():
    """Re-pricing a chore must not rewrite what past completions earned."""
    from homeassistant.util import dt as dt_util

    from custom_components.taskmate import sensor as sensor_module
    from custom_components.taskmate.models import Child, Chore, ChoreCompletion

    today = dt_util.now()
    chore = Chore(name="Tidy up", points=1, id="c")  # since re-priced down from 10
    child = Child(name="Alice", id="k")
    paid = ChoreCompletion(
        chore_id="c", child_id="k", completed_at=today, approved=True, points_awarded=20, submitted_points=10, id="p1"
    )
    legacy = ChoreCompletion(chore_id="c", child_id="k", completed_at=today, approved=True, points_awarded=7, id="p2")
    common = {
        "child_lookup": {"k": child},
        "chore_lookup": {"c": chore},
        "all_completions": [paid, legacy],
    }

    rows = {r["completion_id"]: r["points"] for r in sensor_module._build_recent_completions(common)}
    # 10 for the chore + 10 weekend bonus, not the 1 it costs today.
    assert rows["p1"] == 20
    assert rows["p2"] == 7  # no submitted award recorded, but it was still paid 7


def test_a_parent_completion_is_worth_nothing():
    """It suppresses the chore for the day rather than earning anything."""
    from homeassistant.util import dt as dt_util

    from custom_components.taskmate import sensor as sensor_module
    from custom_components.taskmate.models import Chore, ChoreCompletion

    today = dt_util.now()
    marker = ChoreCompletion(
        chore_id="c", child_id="__parent__", completed_at=today, approved=True, points_awarded=0, id="p1"
    )
    common = {
        "child_lookup": {},
        "chore_lookup": {"c": Chore(name="Tidy up", points=10, id="c")},
        "all_completions": [marker],
    }

    rows = {r["completion_id"]: r["points"] for r in sensor_module._build_todays_completions(common)}
    assert rows["p1"] == 0


def test_the_weekend_bonus_is_not_also_its_own_transaction():
    """It is inside points_awarded; a second row would be counted twice by
    every card that sums completions and transactions together."""

    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, storage = await _make_system()
        storage.set_setting("weekend_multiplier", "2.0")
        child = await coord.async_add_child("Alice")
        saturday = dt.datetime(2024, 3, 23, 12, 0, tzinfo=UTC)
        with patch.object(_mod.dt_util, "now", return_value=saturday):
            awarded = await coord._award_points(child, 10, completion_date=saturday.date())
        return awarded, coord.get_child(child.id).points, storage.get_points_transactions()

    awarded, balance, transactions = _run(scenario)
    assert awarded == 20  # 10 for the chore, 10 for the weekend
    assert balance == 20
    assert [t.reason for t in transactions if "Weekend" in (t.reason or "")] == []
