"""Tests for per-child quiet hours / do-not-disturb (FEAT-5)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from custom_components.taskmate.coord_notifications import (
    NotificationCoordinator,
    _is_within_quiet_hours,
)
from custom_components.taskmate.models import Child, NotificationRoute
from custom_components.taskmate.storage import TaskMateStorage

from .conftest import dt_util_mock


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 1, hour, minute, tzinfo=timezone.utc)


# --- pure window logic -----------------------------------------------------


def test_disabled_when_either_bound_blank():
    assert _is_within_quiet_hours("", "07:00", _at(3)) is False
    assert _is_within_quiet_hours("20:00", "", _at(3)) is False
    assert _is_within_quiet_hours("", "", _at(3)) is False


def test_disabled_when_bounds_equal():
    assert _is_within_quiet_hours("07:00", "07:00", _at(7)) is False


def test_disabled_when_malformed():
    assert _is_within_quiet_hours("notatime", "07:00", _at(3)) is False
    assert _is_within_quiet_hours("25:00", "07:00", _at(3)) is False


def test_daytime_window():
    # School hours 09:00-15:00
    assert _is_within_quiet_hours("09:00", "15:00", _at(8, 59)) is False
    assert _is_within_quiet_hours("09:00", "15:00", _at(9, 0)) is True  # start inclusive
    assert _is_within_quiet_hours("09:00", "15:00", _at(12, 0)) is True
    assert _is_within_quiet_hours("09:00", "15:00", _at(15, 0)) is False  # end exclusive
    assert _is_within_quiet_hours("09:00", "15:00", _at(16, 0)) is False


def test_overnight_window():
    # Bedtime 20:00-07:00
    assert _is_within_quiet_hours("20:00", "07:00", _at(19, 59)) is False
    assert _is_within_quiet_hours("20:00", "07:00", _at(20, 0)) is True  # start inclusive
    assert _is_within_quiet_hours("20:00", "07:00", _at(23, 30)) is True
    assert _is_within_quiet_hours("20:00", "07:00", _at(2, 0)) is True
    assert _is_within_quiet_hours("20:00", "07:00", _at(6, 59)) is True
    assert _is_within_quiet_hours("20:00", "07:00", _at(7, 0)) is False  # end exclusive
    assert _is_within_quiet_hours("20:00", "07:00", _at(12, 0)) is False


# --- dispatch integration --------------------------------------------------


@pytest.fixture
async def coord(hass):
    storage = TaskMateStorage(hass, "test")
    await storage.async_load()
    return NotificationCoordinator(hass, storage)


@pytest.mark.asyncio
async def test_fire_suppresses_child_during_quiet_hours(coord, hass, monkeypatch):
    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = AsyncMock()

    child = Child(
        name="Alex",
        notify_service="notify.alex",
        quiet_hours_start="20:00",
        quiet_hours_end="07:00",
    )
    coord.storage.add_child(child)
    coord.storage.set_notification_master("badge_earned", True)
    coord.storage.set_notification_route("badge_earned", f"child:{child.id}", NotificationRoute(enabled=True))

    # Pretend it is 22:00 — inside the window. The conftest dt_util mock is the
    # single source of "now" the integration sees.
    monkeypatch.setattr(dt_util_mock, "_now", _at(22))

    await coord.fire("badge_earned", {"child_name": "Alex", "badge_name": "Star"})

    notify_calls = [c for c in hass.services.async_call.call_args_list if c[0][0] == "notify"]
    assert notify_calls == []
    # Bus event still fires, but the suppressed child is not a recipient
    name, payload = hass.bus.async_fire.call_args[0]
    assert payload["recipients"] == []


@pytest.mark.asyncio
async def test_fire_delivers_child_outside_quiet_hours(coord, hass, monkeypatch):
    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = AsyncMock()

    child = Child(
        name="Alex",
        notify_service="notify.alex",
        quiet_hours_start="20:00",
        quiet_hours_end="07:00",
    )
    coord.storage.add_child(child)
    coord.storage.set_notification_master("badge_earned", True)
    coord.storage.set_notification_route("badge_earned", f"child:{child.id}", NotificationRoute(enabled=True))

    monkeypatch.setattr(dt_util_mock, "_now", _at(12))  # midday, outside window

    await coord.fire("badge_earned", {"child_name": "Alex", "badge_name": "Star"})

    notify_calls = [c for c in hass.services.async_call.call_args_list if c[0][0] == "notify"]
    assert len(notify_calls) == 1
    assert notify_calls[0][0][1] == "alex"


@pytest.mark.asyncio
async def test_quiet_hours_does_not_suppress_parents(coord, hass, monkeypatch):
    from custom_components.taskmate.models import ParentRecipient

    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = AsyncMock()

    p = ParentRecipient(name="John", notify_service="notify.john")
    coord.storage.upsert_parent_recipient(p)
    coord.storage.set_notification_master("badge_earned", True)
    coord.storage.set_notification_route("badge_earned", p.id, NotificationRoute(enabled=True))

    monkeypatch.setattr(dt_util_mock, "_now", _at(3))  # 3am — would be quiet for a child

    await coord.fire("badge_earned", {"child_name": "Alex", "badge_name": "Star"})

    notify_calls = [c for c in hass.services.async_call.call_args_list if c[0][0] == "notify"]
    assert len(notify_calls) == 1
    assert notify_calls[0][0][1] == "john"


def test_child_round_trips_quiet_hours():
    child = Child(name="Alex", quiet_hours_start="20:00", quiet_hours_end="07:00")
    restored = Child.from_dict(child.to_dict())
    assert restored.quiet_hours_start == "20:00"
    assert restored.quiet_hours_end == "07:00"
