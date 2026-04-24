"""WebSocket API for the TaskMate admin panel.

The panel speaks to the integration via these commands rather than via HA
services — services are intended for automation/templating consumers and
would clutter the service registry with two dozen panel-only entries.

Stage 1 ships only the read command (taskmate/get_state). Mutation commands
land in subsequent stages alongside coordinator method coverage.
"""
from __future__ import annotations

import logging
from typing import Any, Final

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import TaskMateCoordinator

_LOGGER = logging.getLogger(__name__)

WS_REGISTERED: Final = "ws_registered"

WS_GET_STATE: Final = "taskmate/get_state"


def _get_coordinator(hass: HomeAssistant) -> TaskMateCoordinator | None:
    """Return the first available TaskMate coordinator, or None."""
    for key, value in hass.data.get(DOMAIN, {}).items():
        if isinstance(value, TaskMateCoordinator):
            return value
    return None


def _build_state_snapshot(coordinator: TaskMateCoordinator) -> dict[str, Any]:
    """Return the full editable state for the admin panel.

    Pulls straight from the storage layer — every list is already a list of
    plain dicts (dataclass.asdict shape) so no extra serialisation is needed.
    """
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


@websocket_api.websocket_command(
    {vol.Required("type"): WS_GET_STATE}
)
@websocket_api.async_response
async def _ws_get_state(hass, connection, msg):
    """Return the storage snapshot for admin users."""
    if not connection.user.is_admin:
        connection.send_error(msg["id"], websocket_api.const.ERR_UNAUTHORIZED, "Admin only")
        return
    coordinator = _get_coordinator(hass)
    if not coordinator:
        connection.send_error(msg["id"], "no_coordinator", "TaskMate not initialised")
        return
    connection.send_result(msg["id"], _build_state_snapshot(coordinator))


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register all TaskMate WebSocket commands. Idempotent."""
    if hass.data.get(DOMAIN, {}).get(WS_REGISTERED):
        _LOGGER.debug("TaskMate WS commands already registered, skipping")
        return
    websocket_api.async_register_command(hass, _ws_get_state)
    hass.data.setdefault(DOMAIN, {})[WS_REGISTERED] = True
    _LOGGER.info("Registered TaskMate WebSocket commands")
