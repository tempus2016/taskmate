"""WebSocket commands for boost windows — the admin panel's, admin-only like every panel command.

Starting and ending a boost from the panel goes through the ``start_boost`` /
``end_boost`` services (parent gate), the same door automations use. These
commands cover what only the panel does: the recurring rules and a test wake
of the chosen tablets.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api

from .coord_boosts import BOOST_MAX_MULTIPLIER, BOOST_MIN_MULTIPLIER, BOOST_NAME_MAX
from .websocket import _admin_only

WS_BOOST_RULE_SAVE = "taskmate/boosts/save_rule"
WS_BOOST_RULE_DELETE = "taskmate/boosts/delete_rule"
WS_BOOST_TEST_WAKE = "taskmate/boosts/test_wake"


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_BOOST_RULE_SAVE,
        vol.Optional("rule_id"): str,
        vol.Optional("name", default=""): vol.All(str, vol.Length(max=BOOST_NAME_MAX)),
        vol.Required("days"): vol.All([vol.All(vol.Coerce(int), vol.Range(min=0, max=6))], vol.Length(max=7)),
        vol.Required("start"): vol.Match(r"^([01]\d|2[0-3]):[0-5]\d$"),
        vol.Required("end"): vol.Match(r"^([01]\d|2[0-3]):[0-5]\d$"),
        vol.Required("multiplier"): vol.All(
            vol.Coerce(float), vol.Range(min=BOOST_MIN_MULTIPLIER, max=BOOST_MAX_MULTIPLIER)
        ),
        vol.Optional("chore_ids", default=[]): [str],
        vol.Optional("child_ids", default=[]): [str],
        vol.Optional("notify", default=True): bool,
        vol.Optional("enabled", default=True): bool,
    }
)
@websocket_api.async_response
@_admin_only
async def ws_boost_rule_save(hass, connection, msg, coordinator):
    data = {k: v for k, v in msg.items() if k not in ("id", "type", "rule_id")}
    if msg.get("rule_id"):
        data["id"] = msg["rule_id"]
    rule = await coordinator.async_save_boost_rule(data)
    connection.send_result(msg["id"], {"rule": rule})


@websocket_api.websocket_command({vol.Required("type"): WS_BOOST_RULE_DELETE, vol.Required("rule_id"): str})
@websocket_api.async_response
@_admin_only
async def ws_boost_rule_delete(hass, connection, msg, coordinator):
    await coordinator.async_delete_boost_rule(msg["rule_id"])
    connection.send_result(msg["id"], {})


@websocket_api.websocket_command({vol.Required("type"): WS_BOOST_TEST_WAKE})
@websocket_api.async_response
@_admin_only
async def ws_boost_test_wake(hass, connection, msg, coordinator):
    sent = await coordinator.async_wake_boost_screens()
    connection.send_result(msg["id"], {"sent": sent})


BOOST_COMMANDS = (ws_boost_rule_save, ws_boost_rule_delete, ws_boost_test_wake)
