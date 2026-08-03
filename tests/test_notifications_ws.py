"""Tests for notification WebSocket commands."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.taskmate import websocket as ws
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator


@pytest.fixture
async def setup(hass):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.entry_id = "ws_test"
    from custom_components.taskmate.storage import TaskMateStorage
    coord.storage = TaskMateStorage(hass, "ws_test")
    await coord.storage.async_load()
    from custom_components.taskmate.coord_notifications import NotificationCoordinator
    coord.notifications = NotificationCoordinator(hass, coord.storage)
    coord.notifications.coordinator = coord
    hass.data = {DOMAIN: {"ws_test": coord}}
    return coord


@pytest.mark.asyncio
async def test_get_state_returns_full_snapshot(setup, hass):
    connection = MagicMock()
    msg = {"id": 1, "type": "taskmate/notifications/get_state"}
    await ws.ws_notif_get_state(hass, connection, msg)

    args, _ = connection.send_result.call_args
    assert args[0] == 1
    state = args[1]
    assert "recipients" in state
    assert "types" in state
    assert "config" in state
    assert "custom" in state
    assert "settings" in state
    assert any(t["id"] == "bedtime_reminder" for t in state["types"])


@pytest.mark.asyncio
async def test_set_master_enabled(setup, hass):
    coord = setup
    connection = MagicMock()
    msg = {"id": 2, "type": "taskmate/notifications/set_master_enabled",
           "type_id": "bedtime_reminder", "enabled": True}
    await ws.ws_notif_set_master(hass, connection, msg)

    args, _ = connection.send_result.call_args
    assert args[0] == 2
    assert args[1] == {"ok": True}
    assert coord.storage.get_notification_config("bedtime_reminder").master_enabled is True


@pytest.mark.asyncio
async def test_set_route(setup, hass):
    coord = setup
    connection = MagicMock()
    msg = {
        "id": 3, "type": "taskmate/notifications/set_route",
        "type_id": "bedtime_reminder",
        "recipient_id": "child:abc",
        "enabled": True,
        "time": "21:00",
    }
    await ws.ws_notif_set_route(hass, connection, msg)

    args, _ = connection.send_result.call_args
    assert args[0] == 3
    assert args[1] == {"ok": True}
    cfg = coord.storage.get_notification_config("bedtime_reminder")
    assert cfg.routes["child:abc"].enabled is True
    assert cfg.routes["child:abc"].time == "21:00"


@pytest.mark.asyncio
async def test_set_child_notify_not_found(setup, hass):
    connection = MagicMock()
    msg = {
        "id": 4, "type": "taskmate/notifications/set_child_notify",
        "child_id": "nonexistent",
        "notify_service": "notify.test",
    }
    await ws.ws_notif_set_child_notify(hass, connection, msg)
    connection.send_error.assert_called_once()
    args, _ = connection.send_error.call_args
    assert args[1] == "not_found"


@pytest.mark.asyncio
async def test_set_child_notify_success(setup, hass):
    coord = setup
    from custom_components.taskmate.models import Child
    c = Child(name="Maria")
    coord.storage.add_child(c)

    connection = MagicMock()
    msg = {
        "id": 5, "type": "taskmate/notifications/set_child_notify",
        "child_id": c.id,
        "notify_service": "notify.marias_phone",
    }
    await ws.ws_notif_set_child_notify(hass, connection, msg)

    args, _ = connection.send_result.call_args
    assert args[0] == 5
    assert args[1] == {"ok": True}
    updated = coord.storage.get_child(c.id)
    assert updated.notify_service == "notify.marias_phone"


@pytest.mark.asyncio
async def test_upsert_parent_create(setup, hass):
    coord = setup
    connection = MagicMock()
    msg = {
        "id": 6, "type": "taskmate/notifications/upsert_parent",
        "name": "John", "notify_service": "notify.johns_phone", "enabled": True,
    }
    await ws.ws_notif_upsert_parent(hass, connection, msg)

    args, _ = connection.send_result.call_args
    assert args[0] == 6
    result = args[1]
    assert result["name"] == "John"
    assert result["notify_service"] == "notify.johns_phone"
    assert len(coord.storage.get_parent_recipients()) == 1


@pytest.mark.asyncio
async def test_upsert_parent_update(setup, hass):
    coord = setup
    from custom_components.taskmate.models import ParentRecipient
    p = ParentRecipient(name="John", notify_service="notify.johns_phone")
    coord.storage.upsert_parent_recipient(p)

    connection = MagicMock()
    msg = {
        "id": 7, "type": "taskmate/notifications/upsert_parent",
        "parent_id": p.id, "name": "John Mac",
        "notify_service": "notify.johns_phone", "enabled": True,
    }
    await ws.ws_notif_upsert_parent(hass, connection, msg)

    args, _ = connection.send_result.call_args
    assert args[0] == 7
    assert args[1]["name"] == "John Mac"
    assert coord.storage.get_parent_recipients()[0].name == "John Mac"


@pytest.mark.asyncio
async def test_upsert_parent_update_not_found(setup, hass):
    connection = MagicMock()
    msg = {
        "id": 8, "type": "taskmate/notifications/upsert_parent",
        "parent_id": "parent:doesnotexist",
        "name": "Ghost", "notify_service": "notify.ghost", "enabled": True,
    }
    await ws.ws_notif_upsert_parent(hass, connection, msg)
    connection.send_error.assert_called_once()
    args, _ = connection.send_error.call_args
    assert args[1] == "not_found"


@pytest.mark.asyncio
async def test_delete_parent(setup, hass):
    coord = setup
    from custom_components.taskmate.models import ParentRecipient
    p = ParentRecipient(name="Lisa", notify_service="notify.lisas_phone")
    coord.storage.upsert_parent_recipient(p)

    connection = MagicMock()
    msg = {"id": 9, "type": "taskmate/notifications/delete_parent", "parent_id": p.id}
    await ws.ws_notif_delete_parent(hass, connection, msg)

    args, _ = connection.send_result.call_args
    assert args[0] == 9
    assert args[1] == {"ok": True}
    assert coord.storage.get_parent_recipients() == []


@pytest.mark.asyncio
async def test_upsert_custom_create(setup, hass):
    coord = setup
    connection = MagicMock()
    msg = {
        "id": 10, "type": "taskmate/notifications/upsert_custom",
        "name": "Brush teeth",
        "message_template": "Brush your teeth, {child_name}!",
        "time": "20:30",
        "day_mask": 0b1111111,
        "recipient_ids": [],
        "enabled": True,
    }
    await ws.ws_notif_upsert_custom(hass, connection, msg)

    args, _ = connection.send_result.call_args
    assert args[0] == 10
    result = args[1]
    assert result["name"] == "Brush teeth"
    assert result["time"] == "20:30"
    assert len(coord.storage.get_custom_notifications()) == 1


@pytest.mark.asyncio
async def test_upsert_custom_update(setup, hass):
    coord = setup
    from custom_components.taskmate.models import CustomNotification
    n = CustomNotification(
        name="Brush teeth",
        message_template="Brush!",
        time="20:00",
    )
    coord.storage.upsert_custom_notification(n)

    connection = MagicMock()
    msg = {
        "id": 11, "type": "taskmate/notifications/upsert_custom",
        "custom_id": n.id,
        "name": "Brush teeth updated",
        "message_template": "Brush your teeth, {child_name}!",
        "time": "20:30",
        "day_mask": 0b1111111,
        "recipient_ids": [],
        "enabled": True,
    }
    await ws.ws_notif_upsert_custom(hass, connection, msg)

    args, _ = connection.send_result.call_args
    assert args[0] == 11
    assert args[1]["name"] == "Brush teeth updated"
    assert coord.storage.get_custom_notifications()[0].name == "Brush teeth updated"


@pytest.mark.asyncio
async def test_delete_custom(setup, hass):
    coord = setup
    from custom_components.taskmate.models import CustomNotification
    n = CustomNotification(
        name="Brush teeth",
        message_template="Brush!",
        time="20:00",
    )
    coord.storage.upsert_custom_notification(n)

    connection = MagicMock()
    msg = {"id": 12, "type": "taskmate/notifications/delete_custom", "custom_id": n.id}
    await ws.ws_notif_delete_custom(hass, connection, msg)

    args, _ = connection.send_result.call_args
    assert args[0] == 12
    assert args[1] == {"ok": True}
    assert coord.storage.get_custom_notifications() == []


@pytest.mark.asyncio
async def test_list_notify_services(setup, hass):
    hass.services.async_services = MagicMock(
        return_value={"notify": {"mobile_app_johns_iphone": None, "fake_target": None}}
    )
    connection = MagicMock()
    msg = {"id": 13, "type": "taskmate/notifications/list_notify_services"}
    await ws.ws_notif_list_notify(hass, connection, msg)

    args, _ = connection.send_result.call_args
    assert args[0] == 13
    services = args[1]
    assert "notify.fake_target" in services
    assert "notify.mobile_app_johns_iphone" in services
    assert services == sorted(services)


@pytest.mark.asyncio
async def test_set_streak_cutoff(setup, hass):
    coord = setup
    connection = MagicMock()
    msg = {
        "id": 14, "type": "taskmate/notifications/set_streak_cutoff",
        "time": "19:45",
    }
    await ws.ws_notif_set_streak_cutoff(hass, connection, msg)

    args, _ = connection.send_result.call_args
    assert args[0] == 14
    assert args[1] == {"ok": True}
    assert coord.storage.get_streak_at_risk_cutoff() == "19:45"


@pytest.mark.asyncio
async def test_get_state_no_coordinator(hass):
    hass.data = {DOMAIN: {}}
    connection = MagicMock()
    msg = {"id": 99, "type": "taskmate/notifications/get_state"}
    await ws.ws_notif_get_state(hass, connection, msg)
    connection.send_error.assert_called_once()
    args, _ = connection.send_error.call_args
    assert args[1] == "no_coordinator"


@pytest.mark.asyncio
async def test_set_nav_url_global(setup, hass):
    coord = setup
    connection = MagicMock()
    msg = {"id": 20, "type": "taskmate/notifications/set_nav_url", "nav_url": "/taskmate"}
    await ws.ws_notif_set_nav_url(hass, connection, msg)
    args, _ = connection.send_result.call_args
    assert args[1] == {"ok": True}
    assert coord.storage.get_setting("notification_nav_url") == "/taskmate"


@pytest.mark.asyncio
async def test_set_nav_url_per_type(setup, hass):
    coord = setup
    connection = MagicMock()
    msg = {"id": 21, "type": "taskmate/notifications/set_nav_url",
           "type_id": "badge_earned", "nav_url": "/lovelace/x"}
    await ws.ws_notif_set_nav_url(hass, connection, msg)
    assert coord.storage.get_notification_config("badge_earned").nav_url == "/lovelace/x"


@pytest.mark.asyncio
async def test_set_nav_url_rejects_dangerous_schemes(setup, hass):
    coord = setup
    for bad in (
        "javascript:alert(1)",
        "intent://scan/#Intent;scheme=zxing;end",
        "app://com.evil.app",
        "homeassistant://call_service/light.turn_off",
        "//evil.example/phish",
        "ftp://evil.example",
    ):
        connection = MagicMock()
        msg = {"id": 23, "type": "taskmate/notifications/set_nav_url", "nav_url": bad}
        await ws.ws_notif_set_nav_url(hass, connection, msg)
        connection.send_result.assert_not_called()
        args, _ = connection.send_error.call_args
        assert args[1] == "invalid", bad
    assert not coord.storage.get_setting("notification_nav_url")


@pytest.mark.asyncio
async def test_set_nav_url_accepts_noaction_and_https(setup, hass):
    coord = setup
    connection = MagicMock()
    msg = {"id": 24, "type": "taskmate/notifications/set_nav_url",
           "nav_url": "noAction"}
    await ws.ws_notif_set_nav_url(hass, connection, msg)
    assert coord.storage.get_setting("notification_nav_url") == "noAction"

    connection = MagicMock()
    msg = {"id": 25, "type": "taskmate/notifications/set_nav_url",
           "nav_url": "https://example.com/dash"}
    await ws.ws_notif_set_nav_url(hass, connection, msg)
    assert coord.storage.get_setting("notification_nav_url") == "https://example.com/dash"


@pytest.mark.asyncio
async def test_set_nav_url_rejects_unknown_type_id(setup, hass):
    coord = setup
    connection = MagicMock()
    msg = {"id": 26, "type": "taskmate/notifications/set_nav_url",
           "type_id": "not_a_type", "nav_url": "/lovelace/x"}
    await ws.ws_notif_set_nav_url(hass, connection, msg)
    connection.send_result.assert_not_called()
    args, _ = connection.send_error.call_args
    assert args[1] == "invalid"
    assert "not_a_type" not in coord.storage.get_all_notification_configs()


@pytest.mark.asyncio
async def test_get_state_includes_nav_url(setup, hass):
    connection = MagicMock()
    msg = {"id": 22, "type": "taskmate/notifications/get_state"}
    await ws.ws_notif_get_state(hass, connection, msg)
    state = connection.send_result.call_args[0][1]
    assert state["settings"]["notification_nav_url"] == "/taskmate-admin"
