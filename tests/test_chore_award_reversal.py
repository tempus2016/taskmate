"""Approval reversal keeps points, completion counters, and streaks consistent."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import BonusSubTask
from custom_components.taskmate.storage import TaskMateStorage

NOW = datetime.combine(date.today(), time(12), tzinfo=timezone.utc)


async def _make_system():
    from tests.conftest import FakeHass, FakeStore

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    await storage.async_load()
    storage.set_setting("weekend_multiplier", "1")
    storage.set_setting("streak_milestones_enabled", "false")

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = FakeHass()
    coord.hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()
    coord.data = {}
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    coord._async_notify_pending_approval = AsyncMock()
    coord.notifications = AsyncMock()
    coord.notifications._has_outstanding_chores_today = lambda _cid: True
    return coord, storage


async def _submit(coord, child, *, points=10, approved=True):
    chore = await coord.async_add_chore("Dishes", points=points, assigned_to=[child.id], requires_approval=True)
    completion = await coord.async_complete_chore(chore.id, child.id)
    if approved:
        await coord.async_approve_chore(completion.id)
    return chore, completion


def _run(scenario):
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        asyncio.run(scenario())


@pytest.mark.parametrize("action", ["async_undo_chore_approval", "async_reject_chore"])
@pytest.mark.parametrize("bonus_points", [0, 5])
def test_reversal_updates_career_score_and_cascaded_bonus_counters(action, bonus_points):
    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        child.points = 18
        child.total_points_earned = 25
        child.total_penalties_received = 7
        child.career_score = 18
        storage.update_child(child)
        chore, completion = await _submit(coord, child)
        chore.bonus_subtasks = [BonusSubTask(id="bonus", name="Dry dishes", points=bonus_points)]
        storage.update_chore(chore)
        bonus = await coord.async_complete_bonus_subtask(chore.id, "bonus", child.id)
        await coord.async_approve_chore(bonus.id)
        assert storage.get_child(child.id).total_chores_completed == 2

        await getattr(coord, action)(completion.id)

        after = storage.get_child(child.id)
        assert after.points == 18
        assert after.total_points_earned == 25
        assert after.career_score == 18
        assert after.total_chores_completed == 0
        assert storage.get_career_score_history(child.id) == [{"date": NOW.date().isoformat(), "score": 18}]
        if action == "async_undo_chore_approval":
            assert len(storage.get_pending_completions()) == 2
        else:
            assert storage.get_completions() == []

    _run(scenario)


@pytest.mark.parametrize("action", ["async_undo_chore_approval", "async_reject_chore"])
def test_reversal_of_zero_point_chore_reverses_count_and_streak(action):
    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        _, completion = await _submit(coord, child, points=0)
        assert storage.get_child(child.id).total_chores_completed == 1
        assert storage.get_child(child.id).current_streak == 1

        await getattr(coord, action)(completion.id)

        after = storage.get_child(child.id)
        assert after.points == 0
        assert after.total_chores_completed == 0
        assert after.current_streak == 0
        assert after.last_completion_date is None

    _run(scenario)


@pytest.mark.parametrize("action", ["async_undo_chore_approval", "async_reject_chore"])
def test_pending_submissions_do_not_preserve_an_undone_streak(action):
    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        _, completion = await _submit(coord, child)
        await _submit(coord, child, approved=False)

        await getattr(coord, action)(completion.id)

        after = storage.get_child(child.id)
        assert after.total_chores_completed == 0
        assert after.current_streak == 0
        assert after.last_completion_date is None

    _run(scenario)


def test_pending_submission_does_not_become_last_awarded_completion_date():
    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW - timedelta(days=2)):
            await _submit(coord, child, approved=False)
        with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW - timedelta(days=1)):
            _, completion = await _submit(coord, child)

        await coord.async_undo_chore_approval(completion.id)

        after = storage.get_child(child.id)
        assert after.current_streak == 0
        assert after.last_completion_date is None

    _run(scenario)


def test_another_approved_same_day_chore_preserves_the_streak():
    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        _, completion = await _submit(coord, child)
        await _submit(coord, child)

        await coord.async_undo_chore_approval(completion.id)

        after = storage.get_child(child.id)
        assert after.points == 10
        assert after.career_score == 10
        assert after.total_chores_completed == 1
        assert after.current_streak == 1
        assert after.last_completion_date == NOW.date().isoformat()

    _run(scenario)


def test_rejecting_pending_completion_does_not_reverse_other_awards():
    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        await _submit(coord, child)
        _, pending = await _submit(coord, child, approved=False)
        before = storage.get_child(child.id).to_dict()

        await coord.async_reject_chore(pending.id)

        assert storage.get_child(child.id).to_dict() == before

    _run(scenario)
