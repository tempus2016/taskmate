"""Token-gated ICS calendar feed view (FEAT-10).

A calendar app subscribing to a URL can't send an HA bearer token, so this view
is public-by-URL and authenticated by an unguessable per-instance token in the
``?token=`` query param (compared in constant time). It serves a read-only feed
of upcoming chores; no mutation is possible.
"""

from __future__ import annotations

import hmac
import logging
from datetime import timedelta
from http import HTTPStatus

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import ics
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CALENDAR_URL = "/api/taskmate/calendar.ics"
HTTP_CAL_REGISTERED = "calendar_http_registered"


def _get_coordinator(hass: HomeAssistant):
    from .coordinator import TaskMateCoordinator

    for value in hass.data.get(DOMAIN, {}).values():
        if isinstance(value, TaskMateCoordinator):
            return value
    return None


class TaskMateCalendarFeedView(HomeAssistantView):
    """Serve an ICS feed of upcoming chores, gated by the instance token."""

    url = CALENDAR_URL
    name = "api:taskmate:calendar"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        coordinator = _get_coordinator(self.hass)
        if coordinator is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        expected = coordinator.storage.get_setting("ics_token", "")
        supplied = request.query.get("token", "")
        if not expected or not supplied or not hmac.compare_digest(str(expected), supplied):
            return web.Response(status=HTTPStatus.UNAUTHORIZED)

        days = coordinator._calendar_projection_days()
        start = dt_util.now().date()
        end = start + timedelta(days=days)
        events = ics.build_chore_events(coordinator, start, end)
        body = ics.build_calendar(events, dt_util.now())
        return web.Response(
            body=body.encode("utf-8"),
            content_type="text/calendar",
            charset="utf-8",
            headers={"Cache-Control": "private, max-age=3600"},
        )


def async_register_calendar_view(hass: HomeAssistant) -> None:
    """Register the ICS feed view once."""
    if hass.data.get(DOMAIN, {}).get(HTTP_CAL_REGISTERED):
        return
    hass.http.register_view(TaskMateCalendarFeedView(hass))
    hass.data.setdefault(DOMAIN, {})[HTTP_CAL_REGISTERED] = True
    _LOGGER.debug("Registered TaskMate calendar ICS view")
