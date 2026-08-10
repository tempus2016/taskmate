"""Tests for time-gated notification scheduling."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.taskmate.coord_notifications import NotificationCoordinator
from custom_components.taskmate.models import (
    Child,
    NotificationRoute,
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
    coord.storage.add_child(child) if hasattr(coord.storage, "add_child") else coord.storage._data.setdefault(
        "children", []
    ).append(child.to_dict())
    coord.storage.set_notification_master("bedtime_reminder", True)
    coord.storage.set_notification_route(
        "bedtime_reminder",
        f"child:{child.id}",
        NotificationRoute(enabled=True, time="19:30"),
    )

    with patch("custom_components.taskmate.coord_notifications.async_track_time_change") as track:
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


@pytest.mark.asyncio
async def test_bedtime_skips_when_no_outstanding_chores(coord, hass):
    from datetime import datetime

    child = Child(name="M", notify_service="notify.m")
    coord.storage._data.setdefault("children", []).append(child.to_dict())
    # No chores assigned to this child → no outstanding work
    coord.fire = AsyncMock()
    cb = coord._make_bedtime_callback(child.id)
    await cb(datetime.now())
    coord.fire.assert_not_called()


@pytest.mark.asyncio
async def test_streak_at_risk_skips_when_completed_today(coord, hass):
    from datetime import datetime

    from homeassistant.util import dt as dt_util

    today = dt_util.now().date().isoformat()
    child = Child(name="M", current_streak=5, last_completion_date=today)
    coord.storage._data.setdefault("children", []).append(child.to_dict())
    coord.fire = AsyncMock()
    await coord._streak_at_risk_callback(datetime.now())
    coord.fire.assert_not_called()


@pytest.mark.asyncio
async def test_streak_at_risk_skips_when_streak_below_two(coord, hass):
    from datetime import datetime

    child = Child(name="M", current_streak=1)
    coord.storage._data.setdefault("children", []).append(child.to_dict())
    coord.fire = AsyncMock()
    await coord._streak_at_risk_callback(datetime.now())
    coord.fire.assert_not_called()


@pytest.mark.asyncio
async def test_streak_at_risk_fires_when_streak_active_and_not_extended(coord, hass):
    from datetime import datetime

    child = Child(name="M", current_streak=5, last_completion_date="2024-01-01")
    coord.storage._data.setdefault("children", []).append(child.to_dict())
    coord.fire = AsyncMock()
    await coord._streak_at_risk_callback(datetime.now())
    coord.fire.assert_called_once()
    args, kwargs = coord.fire.call_args
    assert args[0] == "streak_at_risk"
    assert args[1]["streak"] == 5


@pytest.mark.asyncio
async def test_custom_skips_when_day_mask_excludes_today(coord, hass, monkeypatch):
    from datetime import datetime

    from custom_components.taskmate.models import CustomNotification

    # day_mask=0 means no day enabled
    n = CustomNotification(
        name="X",
        message_template="hi",
        time="20:00",
        day_mask=0,
        recipient_ids=["child:abc"],
    )
    coord.storage.upsert_custom_notification(n)

    hass.services.async_call = AsyncMock()
    cb = coord._make_custom_callback(n.id)
    await cb(datetime.now())
    hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_custom_fires_when_today_bit_set(coord, hass):
    from datetime import datetime

    from homeassistant.util import dt as dt_util

    from custom_components.taskmate.models import CustomNotification

    today_bit = 1 << dt_util.now().date().weekday()

    child = Child(name="M", notify_service="notify.m")
    coord.storage._data.setdefault("children", []).append(child.to_dict())

    n = CustomNotification(
        name="X",
        message_template="hi {child_name}",
        time="20:00",
        day_mask=today_bit,
        recipient_ids=[f"child:{child.id}"],
    )
    coord.storage.upsert_custom_notification(n)

    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = AsyncMock()
    cb = coord._make_custom_callback(n.id)
    await cb(datetime.now())
    notify_calls = [c for c in hass.services.async_call.call_args_list if c[0][0] == "notify"]
    assert len(notify_calls) == 1
    assert "M" in notify_calls[0][0][2]["message"]
