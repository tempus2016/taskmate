"""WebSocket commands for recaps (#929).

Unlike the panel's commands these are not all admin-only: the recap card runs
on a child's own dashboard. Reading a child's recaps follows the linked-child
rule the services use (``authz.async_context_allows_child``), so a child linked
to one HA user can't read a sibling's. Recap content is fetched on demand
rather than carried on a sensor attribute — a year of recaps would blow the
16 KB attribute cap many times over.
"""

from __future__ import annotations

import logging
from functools import wraps
from types import SimpleNamespace

import voluptuous as vol
from homeassistant.components import websocket_api

from . import authz
from .websocket import _admin_only, _get_coordinator

_LOGGER = logging.getLogger(__name__)

WS_RECAPS_LIST = "taskmate/recaps/list"
WS_RECAPS_GET = "taskmate/recaps/get"
WS_RECAPS_SCHEDULE = "taskmate/recaps/schedule"
WS_RECAPS_PREVIEW = "taskmate/recaps/preview"


def _reader(check_child: bool):
    """Any signed-in user (optionally gated on the linked-child rule)."""

    def decorate(handler):
        @wraps(handler)
        async def wrapper(hass, connection, msg):
            coordinator = _get_coordinator(hass)
            if not coordinator:
                connection.send_error(msg["id"], "no_coordinator", "TaskMate not initialised")
                return
            if check_child:
                child_id = msg["child_id"]
                if coordinator.get_child(child_id) is None:
                    connection.send_error(msg["id"], "not_found", f"Child {child_id} not found")
                    return
                user = connection.user
                context = SimpleNamespace(user_id=getattr(user, "id", "") or "")
                if not getattr(user, "is_admin", False) and not await authz.async_context_allows_child(
                    hass, coordinator, context, child_id
                ):
                    connection.send_error(msg["id"], websocket_api.const.ERR_UNAUTHORIZED, "Not allowed")
                    return
            try:
                await handler(hass, connection, msg, coordinator)
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("WS handler %s failed", msg.get("type"))
                connection.send_error(msg["id"], "handler_failed", str(err))

        return wrapper

    return decorate


def _for_display(coordinator, recap: dict) -> dict:
    """A stored recap as the card should see it (comparison honours the toggle)."""
    out = dict(recap)
    out.pop("notified", None)
    if not coordinator.recap_compare_enabled():
        out["previous"] = None
    return out


@websocket_api.websocket_command({vol.Required("type"): WS_RECAPS_LIST, vol.Required("child_id"): str})
@websocket_api.async_response
@_reader(check_child=True)
async def ws_recaps_list(hass, connection, msg, coordinator):
    child_id = msg["child_id"]
    connection.send_result(
        msg["id"],
        {
            "recaps": [coordinator.recap_summary(r) for r in coordinator.recaps_for_child(child_id)],
            "upcoming": coordinator.recap_upcoming(child_id),
            "frequencies": coordinator.recap_frequencies_for(child_id),
        },
    )


@websocket_api.websocket_command(
    {vol.Required("type"): WS_RECAPS_GET, vol.Required("child_id"): str, vol.Required("recap_id"): str}
)
@websocket_api.async_response
@_reader(check_child=True)
async def ws_recaps_get(hass, connection, msg, coordinator):
    recap = next((r for r in coordinator.recaps_for_child(msg["child_id"]) if r.get("id") == msg["recap_id"]), None)
    if recap is None:
        connection.send_error(msg["id"], "not_found", "Recap not found")
        return
    connection.send_result(msg["id"], {"recap": _for_display(coordinator, recap)})


@websocket_api.websocket_command({vol.Required("type"): WS_RECAPS_SCHEDULE})
@websocket_api.async_response
@_reader(check_child=False)
async def ws_recaps_schedule(hass, connection, msg, coordinator):
    connection.send_result(msg["id"], coordinator.recap_schedule())


@websocket_api.websocket_command({vol.Required("type"): WS_RECAPS_PREVIEW, vol.Required("child_id"): str})
@websocket_api.async_response
@_admin_only
async def ws_recaps_preview(hass, connection, msg, coordinator):
    recap = await coordinator.async_build_recap_preview(msg["child_id"])
    connection.send_result(msg["id"], {"recap": coordinator.recap_summary(recap)})


RECAP_COMMANDS = (ws_recaps_list, ws_recaps_get, ws_recaps_schedule, ws_recaps_preview)
