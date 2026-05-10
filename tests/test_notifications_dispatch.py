"""Tests for NotificationCoordinator dispatch."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.taskmate.coord_notifications import (
    NOTIFICATION_TYPES_BY_ID, NotificationCoordinator,
)
from custom_components.taskmate.models import (
    Child, NotificationRoute, ParentRecipient,
)
from custom_components.taskmate.storage import TaskMateStorage


@pytest.fixture
async def coord(hass):
    storage = TaskMateStorage(hass, "test")
    await storage.async_load()
    return NotificationCoordinator(hass, storage)


@pytest.mark.asyncio
async def test_fire_skips_when_master_disabled(coord, hass):
    hass.services.async_call = AsyncMock()
    bus_fire = AsyncMock()
    hass.bus.async_fire = bus_fire
    coord.storage.set_notification_master("badge_earned", False)
    await coord.fire("badge_earned", {"child_name": "Maria", "badge_name": "Star"})
    hass.services.async_call.assert_not_called()
    bus_fire.assert_called_once()
    args = bus_fire.call_args[0]
    assert args[0] == "taskmate_badge_earned"
    assert args[1]["recipients"] == []


@pytest.mark.asyncio
async def test_fire_routes_only_to_enabled_recipients(coord, hass):
    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = AsyncMock()

    p1 = ParentRecipient(name="John", notify_service="notify.john")
    p2 = ParentRecipient(name="Lisa", notify_service="notify.lisa")
    coord.storage.upsert_parent_recipient(p1)
    coord.storage.upsert_parent_recipient(p2)
    coord.storage.set_notification_master("badge_earned", True)
    coord.storage.set_notification_route("badge_earned", p1.id, NotificationRoute(enabled=True))
    coord.storage.set_notification_route("badge_earned", p2.id, NotificationRoute(enabled=False))

    await coord.fire("badge_earned", {"child_name": "M", "badge_name": "Star"})

    notify_calls = [
        c for c in hass.services.async_call.call_args_list
        if c[0][0] == "notify"
    ]
    assert len(notify_calls) == 1
    assert notify_calls[0][0][1] == "john"


@pytest.mark.asyncio
async def test_fire_renders_template_safely_with_missing_key(coord, hass):
    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = AsyncMock()
    p = ParentRecipient(name="John", notify_service="notify.john")
    coord.storage.upsert_parent_recipient(p)
    coord.storage.set_notification_master("badge_earned", True)
    coord.storage.set_notification_route("badge_earned", p.id, NotificationRoute(enabled=True))

    # Missing badge_name key — should not raise; literal "{badge_name}" stays
    await coord.fire("badge_earned", {"child_name": "M"})

    msg = next(
        c for c in hass.services.async_call.call_args_list
        if c[0][0] == "notify"
    )[0][2]["message"]
    assert "{badge_name}" in msg
    assert "M" in msg


@pytest.mark.asyncio
async def test_fire_emits_bus_event_with_recipients(coord, hass):
    hass.services.async_call = AsyncMock()
    bus_fire = AsyncMock()
    hass.bus.async_fire = bus_fire
    p = ParentRecipient(name="John", notify_service="notify.john")
    coord.storage.upsert_parent_recipient(p)
    coord.storage.set_notification_master("badge_earned", True)
    coord.storage.set_notification_route("badge_earned", p.id, NotificationRoute(enabled=True))

    await coord.fire("badge_earned", {"child_name": "M", "badge_name": "Star"})

    bus_fire.assert_called_once()
    name, payload = bus_fire.call_args[0]
    assert name == "taskmate_badge_earned"
    assert p.id in payload["recipients"]


@pytest.mark.asyncio
async def test_unknown_type_is_logged_and_ignored(coord, hass, caplog):
    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = AsyncMock()
    await coord.fire("not_a_real_type", {})
    hass.services.async_call.assert_not_called()
    hass.bus.async_fire.assert_not_called()
    assert "Unknown notification type" in caplog.text
