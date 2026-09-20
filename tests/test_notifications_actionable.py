"""Tests for actionable approval / reject flow."""

from __future__ import annotations

import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock

import pytest

from custom_components.taskmate.coord_notifications import NotificationCoordinator
from custom_components.taskmate.models import ChoreCompletion, RewardClaim
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc


class _StubCoordinator:
    def __init__(self):
        self.async_approve_chore = AsyncMock()
        self.async_reject_chore = AsyncMock()
        self.async_approve_reward = AsyncMock()
        self.async_reject_reward = AsyncMock()


@pytest.fixture
async def coord(hass):
    """A dispatcher over storage holding one completion and one claim.

    Both records are real: a chore completion id and a reward claim id are the
    same shape, so the only way to route a mobile action correctly is to look
    up which record it names.
    """
    storage = TaskMateStorage(hass, "actionable")
    await storage.async_load()
    now = dt.datetime(2024, 3, 20, 12, 0, tzinfo=UTC)
    storage.add_completion(ChoreCompletion(chore_id="cho1", child_id="kid1", completed_at=now, id="completion-123"))
    storage.add_reward_claim(RewardClaim(reward_id="rw1", child_id="kid1", claimed_at=now, id="claim-456"))
    notif = NotificationCoordinator(hass, storage)
    notif.coordinator = _StubCoordinator()
    return notif


def _evt(action: str):
    class _E:
        data = {"action": action}

    return _E()


@pytest.mark.asyncio
async def test_approve_chore_action_routes(coord):
    await coord.handle_mobile_action(_evt("TASKMATE_APPROVE_completion-123"))
    coord.coordinator.async_approve_chore.assert_called_once_with("completion-123")
    coord.coordinator.async_approve_reward.assert_not_called()


@pytest.mark.asyncio
async def test_reject_chore_action_routes(coord):
    await coord.handle_mobile_action(_evt("TASKMATE_REJECT_completion-123"))
    coord.coordinator.async_reject_chore.assert_called_once_with("completion-123")
    coord.coordinator.async_reject_reward.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_action_ignored(coord):
    await coord.handle_mobile_action(_evt("UNRELATED_ACTION"))
    coord.coordinator.async_approve_chore.assert_not_called()


@pytest.mark.asyncio
async def test_approve_reward_action_routes(coord):
    """Approving an unknown completion is a no-op, not an error, so routing
    cannot rely on the chore path failing first."""
    await coord.handle_mobile_action(_evt("TASKMATE_APPROVE_claim-456"))
    coord.coordinator.async_approve_reward.assert_called_once_with("claim-456")
    coord.coordinator.async_approve_chore.assert_not_called()


@pytest.mark.asyncio
async def test_reject_reward_action_routes(coord):
    await coord.handle_mobile_action(_evt("TASKMATE_REJECT_claim-456"))
    coord.coordinator.async_reject_reward.assert_called_once_with("claim-456")
    coord.coordinator.async_reject_chore.assert_not_called()


@pytest.mark.asyncio
async def test_an_id_that_names_nothing_is_dropped(coord):
    await coord.handle_mobile_action(_evt("TASKMATE_APPROVE_deleted-999"))
    coord.coordinator.async_approve_chore.assert_not_called()
    coord.coordinator.async_approve_reward.assert_not_called()


@pytest.mark.asyncio
async def test_a_refused_review_is_swallowed(coord):
    """A stale push — the claim was approved from the panel a moment ago."""
    coord.coordinator.async_reject_reward.side_effect = ValueError("already approved")
    await coord.handle_mobile_action(_evt("TASKMATE_REJECT_claim-456"))
    coord.coordinator.async_reject_reward.assert_called_once_with("claim-456")
