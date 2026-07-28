"""Tests for notification storage migration + CRUD."""
from __future__ import annotations

import pytest

from custom_components.taskmate.models import (
    CustomNotification,
    NotificationRoute,
    ParentRecipient,
)
from custom_components.taskmate.storage import TaskMateStorage


@pytest.fixture
async def storage(hass):
    s = TaskMateStorage(hass, "test")
    await s.async_load()
    return s


@pytest.mark.asyncio
async def test_fresh_install_seeds_empty_lists(storage):
    assert storage.get_parent_recipients() == []
    assert storage.get_custom_notifications() == []
    # No legacy notify_service: defaults all-off for unmigrated types
    cfg = storage.get_notification_config("bedtime_reminder")
    assert cfg.master_enabled is False
    assert cfg.routes == {}


@pytest.mark.asyncio
async def test_migration_seeds_parent_from_legacy_notify_service(hass):
    s = TaskMateStorage(hass, "legacy")
    s._data = {"settings": {"notify_service": "notify.mobile_app_johns_iphone"}}
    s._run_notifications_migration()
    parents = s.get_parent_recipients()
    assert len(parents) == 1
    assert parents[0].notify_service == "notify.mobile_app_johns_iphone"
    assert parents[0].name == "Parent"

    # Pending-approval / reward-claim / badge defaults: master_enabled=True, parent enabled
    pid = parents[0].id
    for tid in ("pending_chore_approval", "pending_reward_claim", "badge_earned"):
        cfg = s.get_notification_config(tid)
        assert cfg.master_enabled is True, tid
        assert cfg.routes[pid].enabled is True, tid

    # New types stay off
    for tid in ("bedtime_reminder", "streak_at_risk", "all_chores_done"):
        cfg = s.get_notification_config(tid)
        assert cfg.master_enabled is False, tid


@pytest.mark.asyncio
async def test_migration_idempotent(hass):
    s = TaskMateStorage(hass, "idempotent")
    s._data = {"settings": {"notify_service": "notify.foo"}}
    s._run_notifications_migration()
    s._run_notifications_migration()  # second run no-op
    assert len(s.get_parent_recipients()) == 1


@pytest.mark.asyncio
async def test_parent_crud(storage):
    p = ParentRecipient(name="Lisa", notify_service="notify.lisas_phone")
    storage.upsert_parent_recipient(p)
    assert storage.get_parent_recipients()[0].name == "Lisa"

    p.name = "Lisa Mac"
    storage.upsert_parent_recipient(p)
    assert storage.get_parent_recipients()[0].name == "Lisa Mac"

    storage.delete_parent_recipient(p.id)
    assert storage.get_parent_recipients() == []


@pytest.mark.asyncio
async def test_notification_config_set_route(storage):
    storage.set_notification_route(
        "bedtime_reminder",
        "child:abc",
        NotificationRoute(enabled=True, time="19:30"),
    )
    cfg = storage.get_notification_config("bedtime_reminder")
    assert cfg.routes["child:abc"].time == "19:30"
    assert cfg.routes["child:abc"].enabled is True


@pytest.mark.asyncio
async def test_custom_notification_crud(storage):
    n = CustomNotification(
        name="Brush teeth",
        message_template="Brush, {child_name}!",
        time="20:30",
        recipient_ids=["child:abc"],
    )
    storage.upsert_custom_notification(n)
    assert len(storage.get_custom_notifications()) == 1

    storage.delete_custom_notification(n.id)
    assert storage.get_custom_notifications() == []


@pytest.mark.asyncio
async def test_set_notification_nav_url(storage):
    storage.set_notification_nav_url("badge_earned", "/taskmate")
    assert storage.get_notification_config("badge_earned").nav_url == "/taskmate"
