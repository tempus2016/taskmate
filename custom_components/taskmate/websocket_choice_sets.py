"""WebSocket commands for choice sets (#1259), the admin panel's.

Admin-only like every panel command; automations use the
``add_choice_set`` / ``update_choice_set`` / ``remove_choice_set`` services.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api

from .coord_choice_sets import (
    CHOICE_SET_MAX_CHORES,
    CHOICE_SET_MAX_MIN,
    CHOICE_SET_MAX_PENALTY,
    CHOICE_SET_NAME_MAX,
)
from .websocket import _admin_only

WS_CHOICE_SET_CREATE = "taskmate/choice_sets/create"
WS_CHOICE_SET_UPDATE = "taskmate/choice_sets/update"
WS_CHOICE_SET_REMOVE = "taskmate/choice_sets/remove"

_FIELDS = {
    vol.Optional("description"): vol.All(str, vol.Length(max=500)),
    vol.Optional("icon"): vol.All(str, vol.Length(max=60)),
    vol.Optional("min_required"): vol.All(vol.Coerce(int), vol.Range(min=0, max=CHOICE_SET_MAX_MIN)),
    vol.Optional("assigned_to"): vol.All([str], vol.Length(max=50)),
    vol.Optional("penalty_points"): vol.All(vol.Coerce(int), vol.Range(min=0, max=CHOICE_SET_MAX_PENALTY)),
    vol.Optional("active"): bool,
}
_NAME = vol.All(str, vol.Length(min=1, max=CHOICE_SET_NAME_MAX))
_CHORES = vol.All([str], vol.Length(min=1, max=CHOICE_SET_MAX_CHORES))


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_CHOICE_SET_CREATE,
        vol.Required("name"): _NAME,
        vol.Required("chore_ids"): _CHORES,
        **_FIELDS,
    }
)
@websocket_api.async_response
@_admin_only
async def ws_choice_set_create(hass, connection, msg, coordinator):
    data = {k: v for k, v in msg.items() if k not in ("id", "type")}
    set_id = await coordinator.async_create_choice_set(**data)
    connection.send_result(msg["id"], {"id": set_id})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_CHOICE_SET_UPDATE,
        vol.Required("set_id"): str,
        vol.Optional("name"): _NAME,
        vol.Optional("chore_ids"): _CHORES,
        **_FIELDS,
    }
)
@websocket_api.async_response
@_admin_only
async def ws_choice_set_update(hass, connection, msg, coordinator):
    data = {k: v for k, v in msg.items() if k not in ("id", "type", "set_id")}
    await coordinator.async_update_choice_set(msg["set_id"], **data)
    connection.send_result(msg["id"], {"id": msg["set_id"]})


@websocket_api.websocket_command({vol.Required("type"): WS_CHOICE_SET_REMOVE, vol.Required("set_id"): str})
@websocket_api.async_response
@_admin_only
async def ws_choice_set_remove(hass, connection, msg, coordinator):
    await coordinator.async_remove_choice_set(msg["set_id"])
    connection.send_result(msg["id"], {"id": msg["set_id"]})


CHOICE_SET_COMMANDS = (ws_choice_set_create, ws_choice_set_update, ws_choice_set_remove)
