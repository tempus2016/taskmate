"""Parent-audience notifications reach a parent, not the completer.

Two fixes:
- `fire()` no longer pops an unconditional instance-wide persistent_notification
  (which leaked parent-audience messages like "… awaiting approval" to whoever
  was viewing HA — typically the child on a kiosk who just completed the chore).
- adding/initialising parent recipients subscribes them to default-on
  parent-audience types whose routes are still empty, so the parent actually
  gets the notification.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.taskmate.coord_notifications import NotificationCoordinator
from custom_components.taskmate.models import NotificationRoute, ParentRecipient
from custom_components.taskmate.storage import TaskMateStorage


@pytest.fixture
async def coord(hass):
    storage = TaskMateStorage(hass, "parent_routing")
    await storage.async_load()
    return NotificationCoordinator(hass, storage)


@pytest.mark.asyncio
async def test_ensure_subscribes_parent_to_empty_parent_types(coord):
    p = ParentRecipient(name="John", notify_service="notify.mobile_app_john")
    coord.storage.upsert_parent_recipient(p)
    # pending_chore_approval starts with no routes
    assert coord.storage.get_notification_config("pending_chore_approval").routes == {}

    changed = coord.ensure_parent_default_routes()

    assert changed is True
    routes = coord.storage.get_notification_config("pending_chore_approval").routes
    assert p.id in routes and routes[p.id].enabled
    # child-audience types must NOT get a parent route
    assert p.id not in coord.storage.get_notification_config("bedtime_reminder").routes


@pytest.mark.asyncio
async def test_ensure_does_not_override_existing_routes(coord):
    # A type already configured (even to someone else) is left untouched.
    coord.storage.set_notification_route(
        "pending_chore_approval", "child:abc", NotificationRoute(enabled=True)
    )
    p = ParentRecipient(name="John", notify_service="notify.mobile_app_john")
    coord.storage.upsert_parent_recipient(p)

    coord.ensure_parent_default_routes()

    routes = coord.storage.get_notification_config("pending_chore_approval").routes
    assert p.id not in routes          # not forced in
    assert "child:abc" in routes        # existing route preserved


@pytest.mark.asyncio
async def test_upsert_parent_auto_subscribes(coord):
    p = ParentRecipient(name="John", notify_service="notify.mobile_app_john")
    await coord.upsert_parent(p)
    routes = coord.storage.get_notification_config("pending_chore_approval").routes
    assert p.id in routes and routes[p.id].enabled


@pytest.mark.asyncio
async def test_fire_does_not_leak_persistent_notification(coord, hass):
    """With no routes, fire() must notify nobody — no instance-wide persistent."""
    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = AsyncMock()
    coord.storage.set_notification_master("pending_chore_approval", True)

    await coord.fire("pending_chore_approval", {"child_name": "Malia", "chore_name": "Tidy"})

    persistent = [
        c for c in hass.services.async_call.call_args_list
        if c[0][0] == "persistent_notification"
    ]
    assert persistent == []            # the leak is gone
    hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_fire_routes_to_subscribed_parent(coord, hass):
    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = AsyncMock()
    p = ParentRecipient(name="John", notify_service="notify.mobile_app_john")
    await coord.upsert_parent(p)
    coord.storage.set_notification_master("pending_chore_approval", True)

    await coord.fire("pending_chore_approval", {"child_name": "Malia", "chore_name": "Tidy"})

    notify_calls = [
        c for c in hass.services.async_call.call_args_list if c[0][0] == "notify"
    ]
    assert len(notify_calls) == 1
    assert notify_calls[0][0][1] == "mobile_app_john"
