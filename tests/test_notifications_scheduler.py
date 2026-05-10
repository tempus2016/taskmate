"""Tests for time-gated notification scheduling."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.taskmate.coord_notifications import NotificationCoordinator
from custom_components.taskmate.models import (
    Child, NotificationRoute, ParentRecipient,
)
from custom_components.taskmate.storage import TaskMateStorage


@pytest.fixture
async def coord(hass):
    storage = TaskMateStorage(hass, "scheduler")
    await storage.async_load()
    return NotificationCoordinator(hass, storage)


@pytest.mark.asyncio
async def test_async_setup_registers_one_callback_per_enabled_bedtime_route(coord, hass):
    child = Child(name="Maria")
    child.notify_service = "notify.maria"
    coord.storage.add_child(child) if hasattr(coord.storage, "add_child") else coord.storage._data.setdefault("children", []).append(child.to_dict())
    coord.storage.set_notification_master("bedtime_reminder", True)
    coord.storage.set_notification_route(
        "bedtime_reminder", f"child:{child.id}",
        NotificationRoute(enabled=True, time="19:30"),
    )

    with patch(
        "custom_components.taskmate.coord_notifications.async_track_time_change"
    ) as track:
        track.return_value = lambda: None
        await coord.async_setup_schedules()
        assert track.called
        # One bedtime callback for the enabled child
        bedtime_calls = [c for c in track.call_args_list if c.kwargs.get("hour") == 19]
        assert len(bedtime_calls) == 1
        assert bedtime_calls[0].kwargs == {"hour": 19, "minute": 30, "second": 0}


@pytest.mark.asyncio
async def test_async_reload_schedules_cancels_old_and_re_registers(coord, hass):
    cancelled = []
    coord._scheduled_unsubs = [lambda: cancelled.append(1) for _ in range(3)]

    with patch(
        "custom_components.taskmate.coord_notifications.async_track_time_change",
        return_value=lambda: None,
    ):
        await coord.async_setup_schedules()

    assert len(cancelled) == 3
