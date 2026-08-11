"""Tests for mandatory reminder escalation (FEAT-6)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from custom_components.taskmate.coord_notifications import NotificationCoordinator
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import (
    Child,
    Chore,
    MandatoryMiss,
    NotificationRoute,
    ParentRecipient,
)
from custom_components.taskmate.storage import TaskMateStorage

DAY = "2024-03-20"  # matches the conftest dt_util mock's frozen "today"


def _now(hour: int, minute: int = 0) -> datetime:
    return datetime(2024, 3, 20, hour, minute, tzinfo=timezone.utc)


@pytest.fixture
async def coord(hass):
    storage = TaskMateStorage(hass, "test")
    await storage.async_load()
    c = object.__new__(TaskMateCoordinator)
    c.storage = storage
    c.hass = hass
    c.notifications = NotificationCoordinator(hass, storage)
    return c


def _setup(coord, *, with_parent=True):
    child = Child(name="Alex", notify_service="notify.alex")
    coord.storage.add_child(child)
    chore = Chore(name="Homework", mandatory=True)
    coord.storage.add_chore(chore)

    coord.storage.set_notification_master("mandatory_reminder", True)
    coord.storage.set_notification_route("mandatory_reminder", f"child:{child.id}", NotificationRoute(enabled=True))
    parent = None
    if with_parent:
        parent = ParentRecipient(name="John", notify_service="notify.john")
        coord.storage.upsert_parent_recipient(parent)
        coord.storage.set_notification_master("mandatory_parent_alert", True)
        coord.storage.set_notification_route("mandatory_parent_alert", parent.id, NotificationRoute(enabled=True))

    miss = MandatoryMiss(
        chore_id=chore.id,
        child_id=child.id,
        due_date=DAY,
        period_id="morning",
        created_at="2024-03-20T09:00:00+00:00",
    )
    coord.storage.add_mandatory_miss(miss)
    return child, chore, miss, parent


def _notify_services(call_list):
    return [c[0][1] for c in call_list if c[0][0] == "notify"]


@pytest.mark.asyncio
async def test_full_escalation_ladder(coord, hass):
    from unittest.mock import AsyncMock

    hass.services.async_call = AsyncMock()
    child, chore, miss, parent = _setup(coord)

    # 60 min in: reminder threshold (30) crossed, parent (120) not -> stage 2,
    # child reminded (stages 1 + 2 both fire mandatory_reminder).
    n = await coord.async_escalate_mandatory_misses(_now(10, 0))
    assert n == 1
    services = _notify_services(hass.services.async_call.call_args_list)
    assert services == ["alex", "alex"]
    assert coord.storage.get_mandatory_misses()[0].escalation_stage == 2

    # 180 min in: parent threshold crossed -> stage 3, parent alerted.
    hass.services.async_call.reset_mock()
    n = await coord.async_escalate_mandatory_misses(_now(12, 0))
    assert n == 1
    assert _notify_services(hass.services.async_call.call_args_list) == ["john"]
    assert coord.storage.get_mandatory_misses()[0].escalation_stage == 3

    # No further advance.
    hass.services.async_call.reset_mock()
    n = await coord.async_escalate_mandatory_misses(_now(12, 30))
    assert n == 0
    assert _notify_services(hass.services.async_call.call_args_list) == []


@pytest.mark.asyncio
async def test_nudge_only_before_reminder_threshold(coord, hass):
    from unittest.mock import AsyncMock

    hass.services.async_call = AsyncMock()
    _setup(coord)

    # 10 min in: only stage 1 (nudge) -> single child reminder.
    n = await coord.async_escalate_mandatory_misses(_now(9, 10))
    assert n == 1
    assert _notify_services(hass.services.async_call.call_args_list) == ["alex"]
    assert coord.storage.get_mandatory_misses()[0].escalation_stage == 1


@pytest.mark.asyncio
async def test_completed_chore_is_not_escalated(coord, hass):
    from unittest.mock import AsyncMock

    from custom_components.taskmate.models import ChoreCompletion

    hass.services.async_call = AsyncMock()
    child, chore, miss, parent = _setup(coord)
    coord.storage.add_completion(
        ChoreCompletion(
            chore_id=chore.id,
            child_id=child.id,
            completed_at=_now(9, 30),
            approved=True,
        )
    )

    n = await coord.async_escalate_mandatory_misses(_now(12, 0))
    assert n == 0
    assert _notify_services(hass.services.async_call.call_args_list) == []


@pytest.mark.asyncio
async def test_other_day_miss_is_skipped(coord, hass):
    from unittest.mock import AsyncMock

    hass.services.async_call = AsyncMock()
    _setup(coord)
    # Now is the next day — the miss's due_date no longer matches "today".
    n = await coord.async_escalate_mandatory_misses(datetime(2024, 3, 21, 12, 0, tzinfo=timezone.utc))
    assert n == 0


@pytest.mark.asyncio
async def test_reminder_targets_only_the_owing_child(coord, hass):
    from unittest.mock import AsyncMock

    hass.services.async_call = AsyncMock()
    _setup(coord, with_parent=False)
    # A second child is also routed for mandatory_reminder, but the miss is
    # Alex's — only_recipients must keep the nudge from fanning out to them.
    other = Child(name="Sam", notify_service="notify.sam")
    coord.storage.add_child(other)
    coord.storage.set_notification_route("mandatory_reminder", f"child:{other.id}", NotificationRoute(enabled=True))

    await coord.async_escalate_mandatory_misses(_now(9, 10))
    services = _notify_services(hass.services.async_call.call_args_list)
    assert services == ["alex"]
    assert "sam" not in services


def test_miss_round_trips_escalation_stage():
    m = MandatoryMiss(chore_id="c", child_id="k", due_date=DAY, period_id="morning", escalation_stage=2)
    assert MandatoryMiss.from_dict(m.to_dict()).escalation_stage == 2
