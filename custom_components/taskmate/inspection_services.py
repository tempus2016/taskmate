"""``taskmate.*`` services for surprise inspections (#981).

Kept out of ``__init__.py`` like the wishlist services. Every one is a
parent action, so ``_async_register_services`` hands over its parent gate
(admins, listed parents and context-less automations) and audit trail.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coord_inspections import INSPECTION_BONUS_MAX, INSPECTION_NOTE_MAX, INSPECTION_WINDOWS

_LOGGER = logging.getLogger(__name__)

SERVICE_START_INSPECTION = "start_inspection"
SERVICE_PASS_INSPECTION = "pass_inspection"
SERVICE_FAIL_INSPECTION = "fail_inspection"
SERVICE_CANCEL_INSPECTION = "cancel_inspection"

INSPECTION_SERVICES: tuple[str, ...] = (
    SERVICE_START_INSPECTION,
    SERVICE_PASS_INSPECTION,
    SERVICE_FAIL_INSPECTION,
    SERVICE_CANCEL_INSPECTION,
)

_BONUS = vol.All(vol.Coerce(int), vol.Range(min=0, max=INSPECTION_BONUS_MAX))
_NOTE = vol.All(cv.string, vol.Length(max=INSPECTION_NOTE_MAX))

Handler = Callable[[ServiceCall], Awaitable[None]]
Wrapper = Callable[[Handler], Handler]


def async_register_inspection_services(
    hass: HomeAssistant,
    *,
    parent_action: Wrapper,
    get_coordinator: Callable[[], object],
) -> None:
    """Register the inspection services behind the caller's parent gate."""

    def _as_parent(action):
        async def handler(call: ServiceCall) -> None:
            coordinator = get_coordinator()
            if not coordinator:
                _LOGGER.error("No TaskMate coordinator available")
                return
            await action(coordinator, call)

        return parent_action(handler)

    async def start(coordinator, call):
        await coordinator.async_start_inspection(
            call.data["completion_id"],
            bonus=call.data.get("bonus"),
            window=call.data.get("window"),
            tell_child=call.data.get("tell_child"),
        )

    async def pass_(coordinator, call):
        await coordinator.async_pass_inspection(
            call.data["inspection_id"], bonus=call.data.get("bonus"), note=call.data.get("note", "")
        )

    async def fail(coordinator, call):
        await coordinator.async_fail_inspection(
            call.data["inspection_id"], redo=call.data.get("redo"), note=call.data.get("note", "")
        )

    async def cancel(coordinator, call):
        await coordinator.async_cancel_inspection(call.data["inspection_id"])

    registrations = (
        (
            SERVICE_START_INSPECTION,
            start,
            {
                vol.Required("completion_id"): cv.string,
                vol.Optional("bonus"): _BONUS,
                vol.Optional("window"): vol.In(INSPECTION_WINDOWS),
                vol.Optional("tell_child"): cv.boolean,
            },
        ),
        (
            SERVICE_PASS_INSPECTION,
            pass_,
            {
                vol.Required("inspection_id"): cv.string,
                vol.Optional("bonus"): _BONUS,
                vol.Optional("note", default=""): _NOTE,
            },
        ),
        (
            SERVICE_FAIL_INSPECTION,
            fail,
            {
                vol.Required("inspection_id"): cv.string,
                vol.Optional("redo"): cv.boolean,
                vol.Optional("note", default=""): _NOTE,
            },
        ),
        (SERVICE_CANCEL_INSPECTION, cancel, {vol.Required("inspection_id"): cv.string}),
    )
    for name, action, schema in registrations:
        hass.services.async_register(DOMAIN, name, _as_parent(action), schema=vol.Schema(schema))
