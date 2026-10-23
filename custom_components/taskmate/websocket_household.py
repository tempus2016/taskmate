"""WebSocket commands for the screen-time bank, its jar and bin-day chores (admin panel, admin-only)."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api

from .coord_screen_time import SCREEN_TIME_MAX_MINUTES
from .websocket import _admin_only

WS_SCREEN_TIME_ADJUST = "taskmate/screen_time/adjust"
WS_BIN_DAY_PREVIEW = "taskmate/bin_days/preview"
WS_SCREEN_TIME_JAR = "taskmate/screen_time/jar"


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SCREEN_TIME_ADJUST,
        vol.Required("child_id"): str,
        vol.Required("minutes"): vol.All(
            vol.Coerce(int), vol.Range(min=-SCREEN_TIME_MAX_MINUTES, max=SCREEN_TIME_MAX_MINUTES)
        ),
    }
)
@websocket_api.async_response
@_admin_only
async def ws_screen_time_adjust(hass, connection, msg, coordinator):
    balance = await coordinator.async_adjust_screen_time(msg["child_id"], msg["minutes"], "parent")
    connection.send_result(msg["id"], {"minutes": balance})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SCREEN_TIME_JAR,
        vol.Required("child_id"): str,
        vol.Required("action"): vol.In(("save", "open")),
        vol.Optional("minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=SCREEN_TIME_MAX_MINUTES)),
    }
)
@websocket_api.async_response
@_admin_only
async def ws_screen_time_jar(hass, connection, msg, coordinator):
    """A parent saves minutes into a child's jar, or opens it early."""
    if msg["action"] == "open":
        released = await coordinator.async_open_screen_time_jar(msg["child_id"])
        connection.send_result(msg["id"], {"released": released})
        return
    connection.send_result(msg["id"], await coordinator.async_save_screen_time(msg["child_id"], msg.get("minutes")))


@websocket_api.websocket_command({vol.Required("type"): WS_BIN_DAY_PREVIEW})
@websocket_api.async_response
@_admin_only
async def ws_bin_day_preview(hass, connection, msg, coordinator):
    connection.send_result(msg["id"], {"collections": await coordinator.async_bin_day_preview()})


HOUSEHOLD_COMMANDS = (ws_screen_time_adjust, ws_screen_time_jar, ws_bin_day_preview)
