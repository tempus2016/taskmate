"""WebSocket commands for surprise inspections (#981).

The admin panel's side of the feature: flag an approved chore, then pass,
fail or cancel the inspection. Admin-only like the rest of the panel's
commands (the same actions are ``taskmate.*`` services for parents and
automations, see ``inspection_services``).
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api

from .coord_inspections import INSPECTION_BONUS_MAX, INSPECTION_NOTE_MAX, INSPECTION_WINDOWS
from .websocket import _admin_only

WS_INSPECTION_START = "taskmate/inspection/start"
WS_INSPECTION_PASS = "taskmate/inspection/pass"
WS_INSPECTION_FAIL = "taskmate/inspection/fail"
WS_INSPECTION_CANCEL = "taskmate/inspection/cancel"

_BONUS = vol.All(vol.Coerce(int), vol.Range(min=0, max=INSPECTION_BONUS_MAX))
_NOTE = vol.All(str, vol.Length(max=INSPECTION_NOTE_MAX))


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_INSPECTION_START,
        vol.Required("completion_id"): str,
        vol.Optional("bonus"): _BONUS,
        vol.Optional("window"): vol.In(INSPECTION_WINDOWS),
        vol.Optional("tell_child"): bool,
    }
)
@websocket_api.async_response
@_admin_only
async def ws_inspection_start(hass, connection, msg, coordinator):
    record = await coordinator.async_start_inspection(
        msg["completion_id"],
        bonus=msg.get("bonus"),
        window=msg.get("window"),
        tell_child=msg.get("tell_child"),
    )
    connection.send_result(msg["id"], record)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_INSPECTION_PASS,
        vol.Required("inspection_id"): str,
        vol.Optional("bonus"): _BONUS,
        vol.Optional("note", default=""): _NOTE,
    }
)
@websocket_api.async_response
@_admin_only
async def ws_inspection_pass(hass, connection, msg, coordinator):
    record = await coordinator.async_pass_inspection(msg["inspection_id"], bonus=msg.get("bonus"), note=msg["note"])
    connection.send_result(msg["id"], record)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_INSPECTION_FAIL,
        vol.Required("inspection_id"): str,
        vol.Optional("redo"): bool,
        vol.Optional("note", default=""): _NOTE,
    }
)
@websocket_api.async_response
@_admin_only
async def ws_inspection_fail(hass, connection, msg, coordinator):
    record = await coordinator.async_fail_inspection(msg["inspection_id"], redo=msg.get("redo"), note=msg["note"])
    connection.send_result(msg["id"], record)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_INSPECTION_CANCEL,
        vol.Required("inspection_id"): str,
    }
)
@websocket_api.async_response
@_admin_only
async def ws_inspection_cancel(hass, connection, msg, coordinator):
    await coordinator.async_cancel_inspection(msg["inspection_id"])
    connection.send_result(msg["id"], {"inspection_id": msg["inspection_id"]})


INSPECTION_COMMANDS = (ws_inspection_start, ws_inspection_pass, ws_inspection_fail, ws_inspection_cancel)
