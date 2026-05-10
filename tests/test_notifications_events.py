"""Tests for taskmate_* event bus emissions."""
from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import MagicMock, patch

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _now(year=2024, month=3, day=20, hour=12):
    return dt.datetime(year, month, day, hour, 0, 0, tzinfo=UTC)


def _make_system(now=None):
    """Build a fully wired coordinator + storage using in-memory FakeStore."""
    from tests.conftest import FakeHass, FakeStore

    if now is None:
        now = _now()

    hass = FakeHass()
    hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    run(storage.async_load())

    from custom_components.taskmate.coord_notifications import NotificationCoordinator

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.data = {}
    coord.storage = storage
    coord.notifications = NotificationCoordinator(hass, storage)
    coord._unsub_midnight = None
    coord._unsub_prune = None
    coord._unsub_availability = None

    async def _noop_refresh():
        pass

    import custom_components.taskmate.coordinator as _mod
    coord._dt_now = now
    coord.async_refresh = _noop_refresh

    return coord, storage, _mod


class TestChoreCompletedEvent:
    """taskmate_chore_completed fires when a child marks a chore done."""

    def test_fires_on_auto_approved_completion(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(coord.async_add_chore(
                "Make bed", points=5, requires_approval=False
            ))

        coord.hass.bus.async_fire = MagicMock()

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_complete_chore(chore.id, child.id))

        fires = [
            c for c in coord.hass.bus.async_fire.call_args_list
            if c[0][0] == "taskmate_chore_completed"
        ]
        assert len(fires) >= 1
        payload = fires[0][0][1]
        assert payload["child_id"] == child.id
        assert payload["chore_id"] == chore.id
        assert payload["child_name"] == "Alice"
        assert payload["chore_name"] == "Make bed"
        assert payload["points"] == 5
        assert "timestamp" in payload

    def test_fires_on_approval_required_completion(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Bob"))
            chore = run(coord.async_add_chore(
                "Tidy room", points=10, requires_approval=True
            ))

        coord.hass.bus.async_fire = MagicMock()

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_complete_chore(chore.id, child.id))

        fires = [
            c for c in coord.hass.bus.async_fire.call_args_list
            if c[0][0] == "taskmate_chore_completed"
        ]
        assert len(fires) >= 1
        payload = fires[0][0][1]
        assert payload["child_id"] == child.id
        assert payload["chore_id"] == chore.id
        assert "timestamp" in payload


class TestChoreApprovedEvent:
    """taskmate_chore_approved fires when a parent approves a pending completion."""

    def test_fires_on_approval(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Carol"))
            chore = run(coord.async_add_chore(
                "Wash dishes", points=8, requires_approval=True
            ))
            completion = run(coord.async_complete_chore(chore.id, child.id))

        coord.hass.bus.async_fire = MagicMock()

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_approve_chore(completion.id))

        fires = [
            c for c in coord.hass.bus.async_fire.call_args_list
            if c[0][0] == "taskmate_chore_approved"
        ]
        assert len(fires) >= 1
        payload = fires[0][0][1]
        assert payload["child_id"] == child.id
        assert payload["chore_id"] == chore.id
        assert payload["completion_id"] == completion.id
        assert "timestamp" in payload

    def test_no_double_fire_of_completed_on_approval(self):
        """Approval must NOT re-fire taskmate_chore_completed."""
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Dave"))
            chore = run(coord.async_add_chore(
                "Feed dog", points=6, requires_approval=True
            ))
            completion = run(coord.async_complete_chore(chore.id, child.id))

        coord.hass.bus.async_fire = MagicMock()

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_approve_chore(completion.id))

        completed_fires = [
            c for c in coord.hass.bus.async_fire.call_args_list
            if c[0][0] == "taskmate_chore_completed"
        ]
        assert len(completed_fires) == 0


class TestRewardClaimedEvent:
    """taskmate_reward_claimed fires when a child redeems a reward."""

    def test_fires_on_claim(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Eve"))
            chore = run(coord.async_add_chore(
                "Homework", points=100, requires_approval=False
            ))
            run(coord.async_complete_chore(chore.id, child.id))
            reward = run(coord.async_add_reward("Movie night", cost=50))

        coord.hass.bus.async_fire = MagicMock()

        with patch.object(_mod.dt_util, "now", return_value=now):
            claim = run(coord.async_claim_reward(reward.id, child.id))

        fires = [
            c for c in coord.hass.bus.async_fire.call_args_list
            if c[0][0] == "taskmate_reward_claimed"
        ]
        assert len(fires) >= 1
        payload = fires[0][0][1]
        assert payload["child_id"] == child.id
        assert payload["reward_id"] == reward.id
        assert payload["claim_id"] == claim.id
        assert payload["cost"] == 50
        assert "timestamp" in payload


class TestStreakUpdatedEvent:
    """taskmate_streak_updated fires when streak state changes."""

    def test_fires_on_first_completion(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Faye"))
            chore = run(coord.async_add_chore(
                "Brush teeth", points=3, requires_approval=False
            ))

        coord.hass.bus.async_fire = MagicMock()

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_complete_chore(chore.id, child.id))

        fires = [
            c for c in coord.hass.bus.async_fire.call_args_list
            if c[0][0] == "taskmate_streak_updated"
        ]
        assert len(fires) >= 1
        payload = fires[0][0][1]
        assert payload["child_id"] == child.id
        assert "current_streak" in payload
        assert "best_streak" in payload
        assert "timestamp" in payload
        assert payload["current_streak"] == 1

    def test_fires_on_consecutive_day(self):
        coord, storage, _mod = _make_system()
        day1 = _now(day=20)
        day2 = _now(day=21)

        with patch.object(_mod.dt_util, "now", return_value=day1):
            child = run(coord.async_add_child("Grace"))
            chore = run(coord.async_add_chore(
                "Read book", points=4, requires_approval=False
            ))
            run(coord.async_complete_chore(chore.id, child.id))

        coord.hass.bus.async_fire = MagicMock()

        with patch.object(_mod.dt_util, "now", return_value=day2):
            run(coord.async_complete_chore(chore.id, child.id))

        fires = [
            c for c in coord.hass.bus.async_fire.call_args_list
            if c[0][0] == "taskmate_streak_updated"
        ]
        assert len(fires) >= 1
        payload = fires[0][0][1]
        assert payload["current_streak"] == 2
