"""WebSocket command for the printable reward voucher (admin panel, admin-only).

Mirrors ``taskmate/print/weekly_chart``: admin-gated, returns a standalone
HTML page the panel opens in a new tab. The panel may pass its translated
labels and the date as its browser formats it; all of it is escaped.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.util import dt as dt_util

from . import voucher
from .websocket import _admin_only

WS_PRINT_VOUCHER = "taskmate/print/reward_voucher"


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_PRINT_VOUCHER,
        vol.Required("claim_id"): str,
        vol.Optional("labels"): {
            vol.Optional(key): vol.All(str, vol.Length(max=voucher.LABEL_MAX)) for key in voucher.LABEL_KEYS
        },
        vol.Optional("date_text"): vol.All(str, vol.Length(max=40)),
    }
)
@websocket_api.async_response
@_admin_only
async def ws_print_reward_voucher(hass, connection, msg, coordinator):
    claim = next((c for c in coordinator.storage.get_reward_claims() if c.id == msg["claim_id"]), None)
    if claim is None or not claim.approved or claim.wish_id:
        connection.send_error(msg["id"], "not_found", "Only an approved reward can be printed")
        return
    reward = coordinator.get_reward(claim.reward_id)
    holder = coordinator.get_child(claim.holder_id)
    if reward is None or holder is None:
        connection.send_error(msg["id"], "not_found", "That reward or child no longer exists")
        return
    buyer = coordinator.get_child(claim.child_id) if claim.recipient_id else None
    when = dt_util.as_local(claim.approved_at or claim.claimed_at)
    html = voucher.build_voucher(
        reward_name=reward.name,
        child_name=holder.name,
        cost=claim.approved_cost if claim.approved_cost is not None else reward.cost,
        date_text=msg.get("date_text") or when.strftime("%d %b %Y"),
        points_name=coordinator.storage.get_points_name(),
        buyer_name=buyer.name if buyer else "",
        labels=msg.get("labels"),
    )
    connection.send_result(msg["id"], {"html": html})


REWARD_EXTRA_COMMANDS = (ws_print_reward_voucher,)
