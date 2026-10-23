"""WebSocket commands for admin-panel tools (admin-only, like every panel command).

Recently deleted (list + restore), the parent's reward order, and the
Economy insight.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api

from .coord_trash import TRASH_KINDS
from .websocket import _admin_only

WS_TRASH_LIST = "taskmate/recently_deleted/list"
WS_TRASH_RESTORE = "taskmate/recently_deleted/restore"
WS_REWARD_ORDER = "taskmate/rewards/set_order"
WS_REPORT_ECONOMY = "taskmate/reports/economy"


@websocket_api.websocket_command({vol.Required("type"): WS_TRASH_LIST})
@websocket_api.async_response
@_admin_only
async def ws_trash_list(hass, connection, msg, coordinator):
    connection.send_result(msg["id"], {"items": coordinator.recently_deleted()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TRASH_RESTORE,
        vol.Required("kind"): vol.In(TRASH_KINDS),
        vol.Required("item_id"): str,
    }
)
@websocket_api.async_response
@_admin_only
async def ws_trash_restore(hass, connection, msg, coordinator):
    restored = await coordinator.async_restore_deleted(msg["kind"], msg["item_id"])
    connection.send_result(msg["id"], restored)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_REWARD_ORDER,
        vol.Required("reward_order"): vol.All([str], vol.Length(max=1000)),
    }
)
@websocket_api.async_response
@_admin_only
async def ws_reward_order(hass, connection, msg, coordinator):
    await coordinator.async_set_reward_order(msg["reward_order"])
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({vol.Required("type"): WS_REPORT_ECONOMY})
@websocket_api.async_response
@_admin_only
async def ws_report_economy(hass, connection, msg, coordinator):
    connection.send_result(msg["id"], coordinator.economy_report())


PANEL_TOOL_COMMANDS = (ws_trash_list, ws_trash_restore, ws_reward_order, ws_report_economy)
