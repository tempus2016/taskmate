"""WebSocket API for the TaskMate admin panel.

The panel speaks to the integration via these commands rather than via HA
services — services are intended for automation/templating consumers and
would clutter the service registry with two dozen panel-only entries.
"""
from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Final

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import TaskMateCoordinator

_LOGGER = logging.getLogger(__name__)

WS_REGISTERED: Final = "ws_registered"

# --- Read
WS_GET_STATE: Final = "taskmate/get_state"

# --- Children
WS_ADD_CHILD: Final = "taskmate/add_child"
WS_UPDATE_CHILD: Final = "taskmate/update_child"
WS_REMOVE_CHILD: Final = "taskmate/remove_child"


def _get_coordinator(hass: HomeAssistant) -> TaskMateCoordinator | None:
    """Return the first available TaskMate coordinator, or None."""
    for key, value in hass.data.get(DOMAIN, {}).items():
        if isinstance(value, TaskMateCoordinator):
            return value
    return None


def _admin_only(handler):
    """Enforce admin access + coordinator availability on a WS handler."""
    @wraps(handler)
    async def wrapper(hass, connection, msg):
        if not connection.user.is_admin:
            connection.send_error(msg["id"], websocket_api.const.ERR_UNAUTHORIZED, "Admin only")
            return
        coordinator = _get_coordinator(hass)
        if not coordinator:
            connection.send_error(msg["id"], "no_coordinator", "TaskMate not initialised")
            return
        try:
            await handler(hass, connection, msg, coordinator)
        except vol.Invalid as err:
            connection.send_error(msg["id"], "invalid_args", str(err))
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("WS handler %s failed", msg.get("type"))
            connection.send_error(msg["id"], "handler_failed", str(err))
    return wrapper


def _build_state_snapshot(coordinator: TaskMateCoordinator) -> dict[str, Any]:
    """Return the full editable state for the admin panel."""
    data = coordinator.storage.data
    return {
        "version": "1",
        "children":         list(data.get("children", [])),
        "chores":           list(data.get("chores", [])),
        "rewards":          list(data.get("rewards", [])),
        "penalties":        list(data.get("penalties", [])),
        "bonuses":          list(data.get("bonuses", [])),
        "task_groups":      list(data.get("task_groups", [])),
        "pool_allocations": list(data.get("pool_allocations", [])),
        "settings": {
            "points_name": data.get("points_name", "Stars"),
            "points_icon": data.get("points_icon", "mdi:star"),
        },
    }


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

@websocket_api.websocket_command({vol.Required("type"): WS_GET_STATE})
@websocket_api.async_response
@_admin_only
async def _ws_get_state(hass, connection, msg, coordinator):
    connection.send_result(msg["id"], _build_state_snapshot(coordinator))


# ---------------------------------------------------------------------------
# Children
# ---------------------------------------------------------------------------

@websocket_api.websocket_command({
    vol.Required("type"): WS_ADD_CHILD,
    vol.Required("name"): vol.All(str, vol.Length(min=1, max=120)),
    vol.Optional("avatar", default="mdi:account-circle"): str,
    vol.Optional("availability_entity", default=""): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_add_child(hass, connection, msg, coordinator):
    child = await coordinator.async_add_child(
        name=msg["name"].strip(),
        avatar=msg.get("avatar") or "mdi:account-circle",
        availability_entity=(msg.get("availability_entity") or "").strip(),
    )
    connection.send_result(msg["id"], {"id": child.id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_UPDATE_CHILD,
    vol.Required("child_id"): str,
    vol.Optional("name"): vol.All(str, vol.Length(min=1, max=120)),
    vol.Optional("avatar"): str,
    vol.Optional("availability_entity"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_update_child(hass, connection, msg, coordinator):
    existing = coordinator.storage.get_child(msg["child_id"])
    if not existing:
        connection.send_error(msg["id"], "not_found", f"Child {msg['child_id']} not found")
        return
    if "name" in msg:
        existing.name = msg["name"].strip()
    if "avatar" in msg:
        existing.avatar = msg["avatar"] or "mdi:account-circle"
    if "availability_entity" in msg:
        existing.availability_entity = (msg["availability_entity"] or "").strip()
    await coordinator.async_update_child(existing)
    connection.send_result(msg["id"], {"id": existing.id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_REMOVE_CHILD,
    vol.Required("child_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_remove_child(hass, connection, msg, coordinator):
    existing = coordinator.storage.get_child(msg["child_id"])
    if not existing:
        connection.send_error(msg["id"], "not_found", f"Child {msg['child_id']} not found")
        return
    await coordinator.async_remove_child(msg["child_id"])
    connection.send_result(msg["id"], {"id": msg["child_id"]})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register all TaskMate WebSocket commands. Idempotent."""
    if hass.data.get(DOMAIN, {}).get(WS_REGISTERED):
        _LOGGER.debug("TaskMate WS commands already registered, skipping")
        return
    for handler in (
        _ws_get_state,
        _ws_add_child,
        _ws_update_child,
        _ws_remove_child,
    ):
        websocket_api.async_register_command(hass, handler)
    hass.data.setdefault(DOMAIN, {})[WS_REGISTERED] = True
    _LOGGER.info("Registered TaskMate WebSocket commands")
