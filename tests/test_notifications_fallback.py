"""Tests for the non-mobile_app actionable-notification fallback.

Tap actions (Approve / Reject) only render on the HA mobile app. For any other
notify backend we must not send dead buttons — instead the message gets a hint
pointing the recipient at the TaskMate panel.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.taskmate.coord_notifications import (
    _APPROVE_IN_PANEL_HINT,
    NotificationCoordinator,
)
from custom_components.taskmate.models import NotificationRoute, ParentRecipient
from custom_components.taskmate.storage import TaskMateStorage


@pytest.fixture
async def coord(hass):
    storage = TaskMateStorage(hass, "fallback")
    await storage.async_load()
    return NotificationCoordinator(hass, storage)


async def _fire_pending(coord, hass, notify_service):
    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = AsyncMock()
    p = ParentRecipient(name="P", notify_service=notify_service)
    coord.storage.upsert_parent_recipient(p)
    coord.storage.set_notification_master("pending_chore_approval", True)
    coord.storage.set_notification_route(
        "pending_chore_approval",
        p.id,
        NotificationRoute(enabled=True),
    )
    await coord.fire(
        "pending_chore_approval",
        {"entry_id": "completion-1", "child_name": "Mia", "chore_name": "Bin", "points": 10, "points_name": "Stars"},
    )
    return next(c for c in hass.services.async_call.call_args_list if c[0][0] == "notify")[0][2]


@pytest.mark.asyncio
async def test_mobile_app_gets_actions_no_hint(coord, hass):
    data = await _fire_pending(coord, hass, "notify.mobile_app_phone")
    assert "data" in data and "actions" in data["data"]
    assert _APPROVE_IN_PANEL_HINT not in data["message"]


@pytest.mark.asyncio
async def test_non_mobile_app_gets_hint_no_actions(coord, hass):
    data = await _fire_pending(coord, hass, "notify.telegram")
    assert "data" not in data  # no dead buttons
    assert _APPROVE_IN_PANEL_HINT in data["message"]


@pytest.mark.asyncio
async def test_persistent_style_backend_gets_hint(coord, hass):
    data = await _fire_pending(coord, hass, "notify.family_email")
    assert "data" not in data
    assert data["message"].endswith(_APPROVE_IN_PANEL_HINT)
