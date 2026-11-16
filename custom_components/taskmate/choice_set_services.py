"""``taskmate.*`` services for choice sets (#1259).

Defining a set is structural config, so every one is an admin action, like
``add_task_group``. Kept out of ``__init__.py`` like the inspection services.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coord_choice_sets import (
    CHOICE_SET_MAX_CHORES,
    CHOICE_SET_MAX_MIN,
    CHOICE_SET_MAX_PENALTY,
    CHOICE_SET_NAME_MAX,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_ADD_CHOICE_SET = "add_choice_set"
SERVICE_UPDATE_CHOICE_SET = "update_choice_set"
SERVICE_REMOVE_CHOICE_SET = "remove_choice_set"

CHOICE_SET_SERVICES: tuple[str, ...] = (
    SERVICE_ADD_CHOICE_SET,
    SERVICE_UPDATE_CHOICE_SET,
    SERVICE_REMOVE_CHOICE_SET,
)

_NAME = vol.All(cv.string, vol.Length(min=1, max=CHOICE_SET_NAME_MAX))
_CHORES = vol.All(cv.ensure_list, [cv.string], vol.Length(min=1, max=CHOICE_SET_MAX_CHORES))
_FIELDS = {
    vol.Optional("description"): vol.All(cv.string, vol.Length(max=500)),
    vol.Optional("icon"): vol.All(cv.string, vol.Length(max=60)),
    vol.Optional("min_required"): vol.All(vol.Coerce(int), vol.Range(min=0, max=CHOICE_SET_MAX_MIN)),
    vol.Optional("assigned_to"): vol.All(cv.ensure_list, [cv.string], vol.Length(max=50)),
    vol.Optional("penalty_points"): vol.All(vol.Coerce(int), vol.Range(min=0, max=CHOICE_SET_MAX_PENALTY)),
    vol.Optional("active"): cv.boolean,
}

Handler = Callable[[ServiceCall], Awaitable[None]]
Wrapper = Callable[[Handler], Handler]


def async_register_choice_set_services(
    hass: HomeAssistant,
    *,
    admin_action: Wrapper,
    get_coordinator: Callable[[], object],
) -> None:
    """Register the choice-set services behind the caller's admin gate."""

    def _as_admin(action):
        async def handler(call: ServiceCall) -> None:
            coordinator = get_coordinator()
            if not coordinator:
                _LOGGER.error("No TaskMate coordinator available")
                return
            await action(coordinator, call)

        return admin_action(handler)

    async def add(coordinator, call):
        await coordinator.async_create_choice_set(**dict(call.data))

    async def update(coordinator, call):
        data = {k: v for k, v in call.data.items() if k != "set_id"}
        await coordinator.async_update_choice_set(call.data["set_id"], **data)

    async def remove(coordinator, call):
        await coordinator.async_remove_choice_set(call.data["set_id"])

    registrations = (
        (SERVICE_ADD_CHOICE_SET, add, {vol.Required("name"): _NAME, vol.Required("chore_ids"): _CHORES, **_FIELDS}),
        (
            SERVICE_UPDATE_CHOICE_SET,
            update,
            {
                vol.Required("set_id"): cv.string,
                vol.Optional("name"): _NAME,
                vol.Optional("chore_ids"): _CHORES,
                **_FIELDS,
            },
        ),
        (SERVICE_REMOVE_CHOICE_SET, remove, {vol.Required("set_id"): cv.string}),
    )
    for name, action, schema in registrations:
        hass.services.async_register(DOMAIN, name, _as_admin(action), schema=vol.Schema(schema))
