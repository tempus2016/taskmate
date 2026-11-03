"""WebSocket commands for the admin panel's week planner — admin-only like every panel command.

``taskmate/planner/week`` reads the rotation picks for a week;
``taskmate/planner/apply`` saves the parent's planned changes in one batch.
"""

from __future__ import annotations

from datetime import date

import voluptuous as vol
from homeassistant.components import websocket_api

from .coord_planner import PLANNER_MAX_CHANGES, WEEKDAYS
from .websocket import _admin_only

WS_PLANNER_WEEK = "taskmate/planner/week"
WS_PLANNER_APPLY = "taskmate/planner/apply"


def _iso_date(value):
    """An ISO date string (YYYY-MM-DD), checked and handed back as given."""
    if not isinstance(value, str):
        raise vol.Invalid("expected an ISO date")
    try:
        date.fromisoformat(value)
    except ValueError as err:
        raise vol.Invalid("expected an ISO date") from err
    return value


_MOVE_SCHEMA = vol.Schema({vol.Required("origin"): _iso_date, vol.Required("date"): _iso_date})

_CHANGE_SCHEMA = vol.Schema(
    {
        vol.Required("chore_id"): vol.All(str, vol.Length(min=1, max=64)),
        vol.Optional("due_days"): vol.All([vol.In(WEEKDAYS)], vol.Length(max=7)),
        vol.Optional("created_date"): _iso_date,
        vol.Optional("recurrence_day"): vol.Any("", vol.In(WEEKDAYS)),
        vol.Optional("recurrence_start"): vol.Any("", _iso_date),
        vol.Optional("assigned_to"): vol.All([vol.All(str, vol.Length(min=1, max=64))], vol.Length(max=50)),
        vol.Optional("moves"): vol.All([_MOVE_SCHEMA], vol.Length(max=31)),
    }
)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_PLANNER_WEEK,
        vol.Optional("week_start"): _iso_date,
    }
)
@websocket_api.async_response
@_admin_only
async def ws_planner_week(hass, connection, msg, coordinator):
    anchor = date.fromisoformat(msg["week_start"]) if msg.get("week_start") else None
    connection.send_result(msg["id"], coordinator.week_plan(anchor))


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_PLANNER_APPLY,
        vol.Required("changes"): vol.All([_CHANGE_SCHEMA], vol.Length(min=1, max=PLANNER_MAX_CHANGES)),
    }
)
@websocket_api.async_response
@_admin_only
async def ws_planner_apply(hass, connection, msg, coordinator):
    connection.send_result(msg["id"], await coordinator.async_apply_week_plan(msg["changes"]))


PLANNER_COMMANDS = (ws_planner_week, ws_planner_apply)
