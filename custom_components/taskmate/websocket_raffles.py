"""WebSocket commands for raffles — the admin panel's, admin-only like every panel command.

Children buy tickets through the ``buy_raffle_tickets`` service (linked-child
gate) and read raffles from the rewards sensor's ``raffles`` attribute.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api

from .coord_raffles import RAFFLE_MAX_TICKETS, RAFFLE_NAME_MAX, RAFFLE_PRIZE_MAX, RAFFLE_TICKET_COST_MAX
from .websocket import _admin_only

WS_RAFFLES_LIST = "taskmate/raffles/list"
WS_RAFFLES_CREATE = "taskmate/raffles/create"
WS_RAFFLES_UPDATE = "taskmate/raffles/update"
WS_RAFFLES_CANCEL = "taskmate/raffles/cancel"
WS_RAFFLES_REMOVE = "taskmate/raffles/remove"
WS_RAFFLES_DRAW = "taskmate/raffles/draw"

_FIELDS = {
    vol.Optional("prize"): vol.All(str, vol.Length(max=RAFFLE_PRIZE_MAX)),
    vol.Optional("icon"): vol.All(str, vol.Length(max=60)),
    vol.Optional("max_tickets"): vol.All(vol.Coerce(int), vol.Range(min=0, max=RAFFLE_MAX_TICKETS)),
    vol.Optional("assigned_to"): [str],
}


@websocket_api.websocket_command({vol.Required("type"): WS_RAFFLES_LIST})
@websocket_api.async_response
@_admin_only
async def ws_raffles_list(hass, connection, msg, coordinator):
    connection.send_result(msg["id"], {"raffles": coordinator.all_raffles()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_RAFFLES_CREATE,
        vol.Required("name"): vol.All(str, vol.Length(min=1, max=RAFFLE_NAME_MAX)),
        vol.Required("ticket_cost"): vol.All(vol.Coerce(int), vol.Range(min=1, max=RAFFLE_TICKET_COST_MAX)),
        vol.Required("draw_at"): str,
        **_FIELDS,
    }
)
@websocket_api.async_response
@_admin_only
async def ws_raffles_create(hass, connection, msg, coordinator):
    data = {k: v for k, v in msg.items() if k not in ("id", "type")}
    raffle = await coordinator.async_create_raffle(**data)
    connection.send_result(msg["id"], {"id": raffle["id"]})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_RAFFLES_UPDATE,
        vol.Required("raffle_id"): str,
        vol.Optional("name"): vol.All(str, vol.Length(min=1, max=RAFFLE_NAME_MAX)),
        vol.Optional("ticket_cost"): vol.All(vol.Coerce(int), vol.Range(min=1, max=RAFFLE_TICKET_COST_MAX)),
        vol.Optional("draw_at"): str,
        **_FIELDS,
    }
)
@websocket_api.async_response
@_admin_only
async def ws_raffles_update(hass, connection, msg, coordinator):
    data = {k: v for k, v in msg.items() if k not in ("id", "type", "raffle_id")}
    raffle = await coordinator.async_update_raffle(msg["raffle_id"], **data)
    connection.send_result(msg["id"], {"id": raffle["id"]})


@websocket_api.websocket_command({vol.Required("type"): WS_RAFFLES_CANCEL, vol.Required("raffle_id"): str})
@websocket_api.async_response
@_admin_only
async def ws_raffles_cancel(hass, connection, msg, coordinator):
    await coordinator.async_cancel_raffle(msg["raffle_id"])
    connection.send_result(msg["id"], {"id": msg["raffle_id"]})


@websocket_api.websocket_command({vol.Required("type"): WS_RAFFLES_REMOVE, vol.Required("raffle_id"): str})
@websocket_api.async_response
@_admin_only
async def ws_raffles_remove(hass, connection, msg, coordinator):
    await coordinator.async_remove_raffle(msg["raffle_id"])
    connection.send_result(msg["id"], {"id": msg["raffle_id"]})


@websocket_api.websocket_command({vol.Required("type"): WS_RAFFLES_DRAW, vol.Required("raffle_id"): str})
@websocket_api.async_response
@_admin_only
async def ws_raffles_draw(hass, connection, msg, coordinator):
    winner = await coordinator.async_draw_raffle(msg["raffle_id"])
    connection.send_result(msg["id"], {"id": msg["raffle_id"], "winner_id": winner})


RAFFLE_COMMANDS = (
    ws_raffles_list,
    ws_raffles_create,
    ws_raffles_update,
    ws_raffles_cancel,
    ws_raffles_remove,
    ws_raffles_draw,
)
