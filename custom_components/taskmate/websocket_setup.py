"""WebSocket commands for the setup wizard (#980).

``taskmate/setup_wizard/catalogue`` hands the panel the age-grouped chore
suggestions and starter rewards (setup_catalogue.py); the names are in the
panel's locale files. ``taskmate/setup_wizard/apply`` creates what the parent
picked in a single call and a single refresh (coord_setup.py). Both are
admin-only, like the rest of the panel's commands.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api

from .const import AGE_GROUPS, SCHEDULE_MODES
from .setup_catalogue import setup_catalogue
from .websocket import WS_SETUP_APPLY, WS_SETUP_CATALOGUE, _admin_only

# Generous ceilings: a wizard run is a handful of children and a few dozen
# chores; these only stop a runaway payload.
MAX_CHILDREN = 20
MAX_CHORES = 200
MAX_REWARDS = 50

_AGE_GROUP = vol.In(("", *AGE_GROUPS))
_NAME = vol.All(str, vol.Length(min=1, max=200))

_CHILD_SCHEMA = {
    vol.Required("ref"): vol.All(str, vol.Length(min=1, max=40)),
    vol.Required("name"): vol.All(str, vol.Length(min=1, max=120)),
    vol.Optional("avatar", default="mdi:account-circle"): vol.All(str, vol.Length(max=80)),
    vol.Optional("birthday", default=""): vol.All(str, vol.Length(max=10)),
    vol.Optional("age_group", default=""): _AGE_GROUP,
}

_CHILD_UPDATE_SCHEMA = {
    vol.Required("child_id"): str,
    vol.Optional("birthday", default=""): vol.All(str, vol.Length(max=10)),
    vol.Optional("age_group", default=""): _AGE_GROUP,
}

_CHORE_SCHEMA = {
    vol.Required("name"): _NAME,
    vol.Optional("points"): vol.All(int, vol.Range(min=0, max=10000)),
    vol.Optional("description"): vol.All(str, vol.Length(max=500)),
    vol.Optional("icon"): vol.All(str, vol.Length(max=80)),
    vol.Optional("assigned_to"): [str],
    vol.Optional("requires_approval"): bool,
    vol.Optional("time_category"): str,
    vol.Optional("daily_limit"): vol.All(int, vol.Range(min=1)),
    vol.Optional("schedule_mode"): vol.In(SCHEDULE_MODES),
    vol.Optional("due_days"): [str],
    vol.Optional("recurrence"): str,
    vol.Optional("recurrence_day"): str,
}

_REWARD_SCHEMA = {
    vol.Required("name"): _NAME,
    # A fixed cost, like every reward.
    vol.Required("cost"): vol.All(int, vol.Range(min=0, max=1000000)),
    vol.Optional("description"): vol.All(str, vol.Length(max=500)),
    vol.Optional("icon"): vol.All(str, vol.Length(max=80)),
}


@websocket_api.websocket_command({vol.Required("type"): WS_SETUP_CATALOGUE})
@websocket_api.async_response
@_admin_only
async def ws_setup_catalogue(hass, connection, msg, coordinator):
    connection.send_result(msg["id"], setup_catalogue())


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SETUP_APPLY,
        vol.Optional("children", default=[]): vol.All([_CHILD_SCHEMA], vol.Length(max=MAX_CHILDREN)),
        vol.Optional("child_updates", default=[]): vol.All([_CHILD_UPDATE_SCHEMA], vol.Length(max=MAX_CHILDREN)),
        vol.Optional("chores", default=[]): vol.All([_CHORE_SCHEMA], vol.Length(max=MAX_CHORES)),
        vol.Optional("rewards", default=[]): vol.All([_REWARD_SCHEMA], vol.Length(max=MAX_REWARDS)),
    }
)
@websocket_api.async_response
@_admin_only
async def ws_setup_apply(hass, connection, msg, coordinator):
    result = await coordinator.async_apply_setup_wizard(
        children=msg.get("children"),
        child_updates=msg.get("child_updates"),
        chores=msg.get("chores"),
        rewards=msg.get("rewards"),
    )
    connection.send_result(msg["id"], result)


SETUP_COMMANDS = (ws_setup_catalogue, ws_setup_apply)
