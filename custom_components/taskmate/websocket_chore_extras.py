"""WebSocket commands for the Insights calendar (admin panel, admin-only)."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api

from .coord_chore_insights import HEATMAP_DAYS, HEATMAP_MAX_DAYS
from .websocket import _admin_only

WS_REPORT_HEATMAP = "taskmate/reports/heatmap"


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_REPORT_HEATMAP,
        vol.Optional("days", default=HEATMAP_DAYS): vol.All(vol.Coerce(int), vol.Range(min=7, max=HEATMAP_MAX_DAYS)),
    }
)
@websocket_api.async_response
@_admin_only
async def ws_report_heatmap(hass, connection, msg, coordinator):
    connection.send_result(msg["id"], coordinator.heatmap_report(msg["days"]))


CHORE_EXTRA_COMMANDS = (ws_report_heatmap,)
