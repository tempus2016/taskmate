"""Tests for the test-notification (send_test) feature."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.taskmate.coord_notifications import NotificationCoordinator
from custom_components.taskmate.models import NotificationRoute, ParentRecipient
from custom_components.taskmate.storage import TaskMateStorage


@pytest.fixture
async def coord(hass):
    storage = TaskMateStorage(hass, "testsend")
    await storage.async_load()
    return NotificationCoordinator(hass, storage)


@pytest.mark.asyncio
async def test_send_test_ignores_master_and_prefixes(coord, hass):
    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = AsyncMock()
    p = ParentRecipient(name="John", notify_service="notify.john")
    coord.storage.upsert_parent_recipient(p)
    # Master OFF — send_test must still deliver.
    coord.storage.set_notification_master("badge_earned", False)
    coord.storage.set_notification_route("badge_earned", p.id, NotificationRoute(enabled=True))

    sent = await coord.send_test("badge_earned")
    assert p.id in sent
    notify_calls = [c for c in hass.services.async_call.call_args_list if c[0][0] == "notify"]
    assert len(notify_calls) == 1
    assert notify_calls[0][0][2]["message"].startswith("[TEST] ")


@pytest.mark.asyncio
async def test_send_test_no_bus_event(coord, hass):
    hass.services.async_call = AsyncMock()
    fire = AsyncMock()
    hass.bus.async_fire = fire
    await coord.send_test("badge_earned")
    # send_test must not emit a taskmate_* bus event (unlike fire()).
    assert not any(str(c[0][0]).startswith("taskmate_") for c in fire.call_args_list)


@pytest.mark.asyncio
async def test_send_test_unknown_type_raises(coord, hass):
    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = AsyncMock()
    with pytest.raises(ValueError, match="Unknown notification type"):
        await coord.send_test("not_a_type")


@pytest.mark.asyncio
async def test_send_test_always_fires_persistent(coord, hass):
    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = AsyncMock()
    # No routes configured — still creates the persistent notification.
    sent = await coord.send_test("streak_milestone")
    assert sent == []
    persistent = [c for c in hass.services.async_call.call_args_list if c[0][0] == "persistent_notification"]
    assert len(persistent) == 1


@pytest.mark.asyncio
async def test_send_test_carries_nav_url(coord, hass):
    hass.services.async_call = AsyncMock()
    p = ParentRecipient(name="John", notify_service="notify.mobile_app_johns_iphone")
    coord.storage.upsert_parent_recipient(p)
    coord.storage.set_notification_route("badge_earned", p.id, NotificationRoute(enabled=True))
    await coord.send_test("badge_earned")
    calls = [c for c in hass.services.async_call.call_args_list
             if c[0][0] == "notify" and c[0][1].startswith("mobile_app")]
    assert calls and calls[0][0][2]["data"]["clickAction"] == "/taskmate-admin"
