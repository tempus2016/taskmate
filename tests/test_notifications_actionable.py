"""Tests for actionable approval / reject flow."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.taskmate.coord_notifications import NotificationCoordinator
from custom_components.taskmate.storage import TaskMateStorage


class _StubCoordinator:
    def __init__(self):
        self.async_approve_chore = AsyncMock()
        self.async_reject_chore = AsyncMock()
        self.async_approve_reward = AsyncMock()
        self.async_reject_reward = AsyncMock()


@pytest.fixture
async def coord(hass):
    storage = TaskMateStorage(hass, "actionable")
    await storage.async_load()
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


@pytest.mark.asyncio
async def test_reject_chore_action_routes(coord):
    await coord.handle_mobile_action(_evt("TASKMATE_REJECT_completion-123"))
    coord.coordinator.async_reject_chore.assert_called_once_with("completion-123")


@pytest.mark.asyncio
async def test_unknown_action_ignored(coord):
    await coord.handle_mobile_action(_evt("UNRELATED_ACTION"))
    coord.coordinator.async_approve_chore.assert_not_called()


@pytest.mark.asyncio
async def test_reward_claim_action_routes(coord):
    # Reward claim ids and chore completion ids are distinct namespaces.
    # The dispatcher tells them apart by attempting both and letting the
    # coordinator's "not found" path absorb the wrong one.
    coord.coordinator.async_approve_chore.side_effect = ValueError("not found")
    await coord.handle_mobile_action(_evt("TASKMATE_APPROVE_claim-456"))
    coord.coordinator.async_approve_reward.assert_called_once_with("claim-456")
