"""WebSocket commands for chore auctions (#982).

Bids are sealed, so what a caller sees depends on who they are:

* ``taskmate/auctions/list`` with a ``child_id`` is the auction card's view of
  that child — the auctions they may bid on, the number of bids in, their own
  bid, and the result once closed. Reading it follows the linked-child rule the
  services use (``authz.async_context_allows_child``), so a child can't read a
  sibling's card either. It never carries another child's amount, whoever asks.
* The same command without a ``child_id`` is the parents' view, with every bid
  amount — for TaskMate parents and admins only (``authz.async_user_is_parent``).
* Bidding acts *as* a child, so it runs the same linked-child check.
* Opening, closing and cancelling are the admin panel's, admin-only like every
  other panel command.

The auctions sensor carries only a digest (counts, never amounts); the card
watches it to know when to re-fetch.
"""

from __future__ import annotations

import logging
from functools import wraps
from types import SimpleNamespace

import voluptuous as vol
from homeassistant.components import websocket_api

from . import authz
from .const import AUCTION_POINTS_MAX
from .websocket import _admin_only, _get_coordinator

_LOGGER = logging.getLogger(__name__)

WS_AUCTIONS_LIST = "taskmate/auctions/list"
WS_AUCTIONS_BID = "taskmate/auctions/bid"
WS_AUCTIONS_WITHDRAW = "taskmate/auctions/withdraw"
WS_AUCTIONS_START = "taskmate/auctions/start"
WS_AUCTIONS_CLOSE = "taskmate/auctions/close"
WS_AUCTIONS_CANCEL = "taskmate/auctions/cancel"
WS_AUCTIONS_OCCURRENCES = "taskmate/auctions/occurrences"


def _context(connection) -> SimpleNamespace:
    return SimpleNamespace(user_id=getattr(connection.user, "id", "") or "")


def _signed_in(handler):
    """Any signed-in user; the handler applies its own per-child/parent check."""

    @wraps(handler)
    async def wrapper(hass, connection, msg):
        coordinator = _get_coordinator(hass)
        if not coordinator:
            connection.send_error(msg["id"], "no_coordinator", "TaskMate not initialised")
            return
        try:
            await handler(hass, connection, msg, coordinator)
        except ValueError as err:
            connection.send_error(msg["id"], "invalid", str(err))
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("WS handler %s failed", msg.get("type"))
            connection.send_error(msg["id"], "handler_failed", str(err))

    return wrapper


async def _may_act_for(hass, connection, coordinator, child_id: str) -> bool:
    """The linked-child rule: may this user see / act as ``child_id``?"""
    if getattr(connection.user, "is_admin", False):
        return True
    return await authz.async_context_allows_child(hass, coordinator, _context(connection), child_id)


def _unauthorized(connection, msg) -> None:
    connection.send_error(msg["id"], websocket_api.const.ERR_UNAUTHORIZED, "Not allowed")


@websocket_api.websocket_command({vol.Required("type"): WS_AUCTIONS_LIST, vol.Optional("child_id"): str})
@websocket_api.async_response
@_signed_in
async def ws_auctions_list(hass, connection, msg, coordinator):
    """A child's auctions (no one else's amounts), or every auction for a parent."""
    child_id = msg.get("child_id")
    if child_id:
        if coordinator.get_child(child_id) is None:
            connection.send_error(msg["id"], "not_found", f"Child {child_id} not found")
            return
        if not await _may_act_for(hass, connection, coordinator, child_id):
            _unauthorized(connection, msg)
            return
        connection.send_result(msg["id"], {"auctions": coordinator.auctions_for_child(child_id)})
        return
    user_id = getattr(connection.user, "id", "") or ""
    if not getattr(connection.user, "is_admin", False) and not await authz.async_user_is_parent(
        hass, coordinator, user_id
    ):
        _unauthorized(connection, msg)
        return
    connection.send_result(msg["id"], {"auctions": coordinator.auctions_state()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_AUCTIONS_BID,
        vol.Required("auction_id"): str,
        vol.Required("child_id"): str,
        vol.Required("points"): vol.All(vol.Coerce(int), vol.Range(min=1, max=AUCTION_POINTS_MAX)),
    }
)
@websocket_api.async_response
@_signed_in
async def ws_auctions_bid(hass, connection, msg, coordinator):
    """Seal (or change) a child's bid."""
    if not await _may_act_for(hass, connection, coordinator, msg["child_id"]):
        _unauthorized(connection, msg)
        return
    await coordinator.async_place_bid(msg["auction_id"], msg["child_id"], msg["points"])
    connection.send_result(msg["id"], {"id": msg["auction_id"]})


@websocket_api.websocket_command(
    {vol.Required("type"): WS_AUCTIONS_WITHDRAW, vol.Required("auction_id"): str, vol.Required("child_id"): str}
)
@websocket_api.async_response
@_signed_in
async def ws_auctions_withdraw(hass, connection, msg, coordinator):
    """Take a child's bid back while bidding is open."""
    if not await _may_act_for(hass, connection, coordinator, msg["child_id"]):
        _unauthorized(connection, msg)
        return
    await coordinator.async_withdraw_bid(msg["auction_id"], msg["child_id"])
    connection.send_result(msg["id"], {"id": msg["auction_id"]})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_AUCTIONS_START,
        vol.Required("chore_id"): str,
        vol.Required("occurrence"): str,
        vol.Required("max_points"): vol.All(vol.Coerce(int), vol.Range(min=1, max=AUCTION_POINTS_MAX)),
        vol.Required("closes_at"): str,
        vol.Optional("min_points", default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=AUCTION_POINTS_MAX)),
        vol.Optional("eligible_child_ids"): [str],
        vol.Optional("notify_children", default=True): bool,
    }
)
@websocket_api.async_response
@_admin_only
async def ws_auctions_start(hass, connection, msg, coordinator):
    """Open an auction on one occurrence of a chore."""
    auction = await coordinator.async_start_auction(
        msg["chore_id"],
        msg["occurrence"],
        msg["max_points"],
        msg["closes_at"],
        eligible_child_ids=msg.get("eligible_child_ids") or None,
        min_points=msg["min_points"],
        notify_children=msg["notify_children"],
    )
    connection.send_result(msg["id"], {"id": auction.id})


@websocket_api.websocket_command({vol.Required("type"): WS_AUCTIONS_CLOSE, vol.Required("auction_id"): str})
@websocket_api.async_response
@_admin_only
async def ws_auctions_close(hass, connection, msg, coordinator):
    """Close bidding now and settle the winner."""
    auction = await coordinator.async_close_auction(msg["auction_id"])
    connection.send_result(msg["id"], {"id": auction.id, "winner_id": auction.winner_id, "price": auction.price})


@websocket_api.websocket_command({vol.Required("type"): WS_AUCTIONS_CANCEL, vol.Required("auction_id"): str})
@websocket_api.async_response
@_admin_only
async def ws_auctions_cancel(hass, connection, msg, coordinator):
    """Call an auction off; the occurrence goes back to its normal assignment."""
    await coordinator.async_cancel_auction(msg["auction_id"])
    connection.send_result(msg["id"], {"id": msg["auction_id"]})


@websocket_api.websocket_command({vol.Required("type"): WS_AUCTIONS_OCCURRENCES, vol.Required("chore_id"): str})
@websocket_api.async_response
@_admin_only
async def ws_auctions_occurrences(hass, connection, msg, coordinator):
    """The chore's next occurrences a parent may auction (and why not, if none)."""
    chore = coordinator.get_chore(msg["chore_id"])
    if chore is None:
        connection.send_error(msg["id"], "not_found", f"Chore {msg['chore_id']} not found")
        return
    connection.send_result(
        msg["id"],
        {
            "occurrences": coordinator.auction_occurrences(chore.id),
            "refusal": coordinator.auction_refusal(chore),
            "pool": coordinator.auction_pool(chore),
            "normal_points": coordinator.effective_chore_points(chore),
        },
    )


AUCTION_COMMANDS = (
    ws_auctions_list,
    ws_auctions_bid,
    ws_auctions_withdraw,
    ws_auctions_start,
    ws_auctions_close,
    ws_auctions_cancel,
    ws_auctions_occurrences,
)
