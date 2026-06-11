"""Admin gating on TaskMate WebSocket commands.

Every panel command — including the notification handlers — must reject
non-admin users with ERR_UNAUTHORIZED before touching any data.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate import websocket as ws


@pytest.fixture
async def setup(hass):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.entry_id = "ws_admin_test"
    from custom_components.taskmate.storage import TaskMateStorage
    coord.storage = TaskMateStorage(hass, "ws_admin_test")
    await coord.storage.async_load()
    from custom_components.taskmate.coord_notifications import NotificationCoordinator
    coord.notifications = NotificationCoordinator(hass, coord.storage)
    coord.notifications.coordinator = coord
    hass.data = {DOMAIN: {"ws_admin_test": coord}}
    return coord


def _non_admin_connection() -> MagicMock:
    connection = MagicMock()
    connection.user.is_admin = False
    return connection


def _admin_connection() -> MagicMock:
    connection = MagicMock()
    connection.user.is_admin = True
    return connection


NOTIF_HANDLERS = [
    ws.ws_notif_get_state,
    ws.ws_notif_set_master,
    ws.ws_notif_set_route,
    ws.ws_notif_set_child_notify,
    ws.ws_notif_upsert_parent,
    ws.ws_notif_delete_parent,
    ws.ws_notif_upsert_custom,
    ws.ws_notif_delete_custom,
    ws.ws_notif_list_notify,
    ws.ws_notif_set_streak_cutoff,
]


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", NOTIF_HANDLERS, ids=lambda h: h.__name__)
async def test_notification_handlers_reject_non_admin(setup, hass, handler):
    connection = _non_admin_connection()
    msg = {"id": 1, "type": "test"}
    await handler(hass, connection, msg)

    connection.send_error.assert_called_once()
    args, _ = connection.send_error.call_args
    assert args[0] == 1
    assert args[1] == ws.websocket_api.const.ERR_UNAUTHORIZED
    connection.send_result.assert_not_called()


@pytest.mark.asyncio
async def test_crud_handler_rejects_non_admin(setup, hass):
    connection = _non_admin_connection()
    msg = {"id": 2, "type": "taskmate/add_child", "name": "Intruder"}
    await ws._ws_add_child(hass, connection, msg)

    connection.send_error.assert_called_once()
    args, _ = connection.send_error.call_args
    assert args[1] == ws.websocket_api.const.ERR_UNAUTHORIZED
    connection.send_result.assert_not_called()


@pytest.mark.asyncio
async def test_notification_handler_allows_admin(setup, hass):
    coord = setup
    connection = _admin_connection()
    msg = {
        "id": 3, "type": "test",
        "type_id": "bedtime_reminder", "enabled": True,
    }
    await ws.ws_notif_set_master(hass, connection, msg)

    args, _ = connection.send_result.call_args
    assert args[0] == 3
    assert args[1] == {"ok": True}
    assert coord.storage.get_notification_config("bedtime_reminder").master_enabled is True
