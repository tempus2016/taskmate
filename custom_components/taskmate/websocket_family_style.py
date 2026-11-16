"""WebSocket commands for the family style preset (#1260), admin-only.

``taskmate/family_style/preview`` returns what a style would change without
touching anything (the panel's confirm dialog). ``taskmate/apply_family_style``
applies it in one save and one refresh, and returns the same diff.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api

from .family_style import FAMILY_STYLES, apply_family_style, current_style, plan_family_style
from .websocket import _admin_only

WS_APPLY_FAMILY_STYLE = "taskmate/apply_family_style"
WS_PREVIEW_FAMILY_STYLE = "taskmate/family_style/preview"


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_PREVIEW_FAMILY_STYLE,
        vol.Required("style"): vol.In(FAMILY_STYLES),
    }
)
@websocket_api.async_response
@_admin_only
async def ws_preview_family_style(hass, connection, msg, coordinator):
    settings = coordinator.storage.get_settings()
    connection.send_result(
        msg["id"],
        {
            "style": msg["style"],
            "previous": current_style(settings),
            "changes": plan_family_style(settings, msg["style"]),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_APPLY_FAMILY_STYLE,
        vol.Required("style"): vol.In(FAMILY_STYLES),
    }
)
@websocket_api.async_response
@_admin_only
async def ws_apply_family_style(hass, connection, msg, coordinator):
    result = apply_family_style(coordinator.storage, msg["style"])
    await coordinator.storage.async_save()
    await coordinator.async_refresh()
    connection.send_result(msg["id"], result)


FAMILY_STYLE_COMMANDS = (ws_preview_family_style, ws_apply_family_style)
