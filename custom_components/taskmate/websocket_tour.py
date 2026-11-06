"""WebSocket commands for the kid onboarding tour.

* ``taskmate/tour/mark`` — the card says a child finished the tour or skipped
  it. It acts *as* the child, so it runs the linked-child rule every child
  action uses (``authz.async_context_allows_child``): a child can mark their
  own tour and nobody else's.
* ``taskmate/tour/speak`` — read one step aloud on the read-aloud speaker. Also
  a child action. The caller names a step, never the words: the text is built
  on the server from the locale catalogue.
* ``taskmate/tour/reset`` — "Show again" in the panel. Grown-ups only
  (admins and TaskMate parents).
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api

from . import authz
from .coord_tour import TOUR_MAX_STEP, TOUR_SPEAKABLE
from .errors import send_translated_error
from .websocket_auctions import _context, _may_act_for, _signed_in, _unauthorized

WS_TOUR_MARK = "taskmate/tour/mark"
WS_TOUR_SPEAK = "taskmate/tour/speak"
WS_TOUR_RESET = "taskmate/tour/reset"


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TOUR_MARK,
        vol.Required("child_id"): str,
        vol.Required("status"): vol.In(["done", "skipped"]),
        vol.Optional("step", default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=TOUR_MAX_STEP)),
    }
)
@websocket_api.async_response
@_signed_in
async def ws_tour_mark(hass, connection, msg, coordinator):
    """A child finished (or skipped) their tour."""
    if coordinator.get_child(msg["child_id"]) is None:
        send_translated_error(connection, msg["id"], "not_found", "child_not_found", child_id=msg["child_id"])
        return
    if not await _may_act_for(hass, connection, coordinator, msg["child_id"]):
        _unauthorized(connection, msg)
        return
    record = await coordinator.async_tour_mark(msg["child_id"], msg["status"], msg.get("step", 1))
    connection.send_result(msg["id"], {"child_id": msg["child_id"], "tour": record})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TOUR_SPEAK,
        vol.Required("child_id"): str,
        vol.Required("step"): vol.In(list(TOUR_SPEAKABLE)),
        vol.Optional("language", default=""): vol.All(str, vol.Length(max=12)),
    }
)
@websocket_api.async_response
@_signed_in
async def ws_tour_speak(hass, connection, msg, coordinator):
    """Read one tour step aloud for a child."""
    if coordinator.get_child(msg["child_id"]) is None:
        send_translated_error(connection, msg["id"], "not_found", "child_not_found", child_id=msg["child_id"])
        return
    if not await _may_act_for(hass, connection, coordinator, msg["child_id"]):
        _unauthorized(connection, msg)
        return
    said = await coordinator.async_tour_speak(
        msg["child_id"], msg["step"], msg.get("language", ""), context=_context(connection)
    )
    connection.send_result(msg["id"], {"message": said})


@websocket_api.websocket_command({vol.Required("type"): WS_TOUR_RESET, vol.Required("child_id"): str})
@websocket_api.async_response
@_signed_in
async def ws_tour_reset(hass, connection, msg, coordinator):
    """Show the tour again for a child (grown-ups only)."""
    user_id = getattr(connection.user, "id", "") or ""
    if not getattr(connection.user, "is_admin", False) and not await authz.async_user_is_parent(
        hass, coordinator, user_id
    ):
        _unauthorized(connection, msg)
        return
    if coordinator.get_child(msg["child_id"]) is None:
        send_translated_error(connection, msg["id"], "not_found", "child_not_found", child_id=msg["child_id"])
        return
    await coordinator.async_tour_reset(msg["child_id"])
    connection.send_result(msg["id"], {"child_id": msg["child_id"]})


TOUR_COMMANDS = (ws_tour_mark, ws_tour_speak, ws_tour_reset)
