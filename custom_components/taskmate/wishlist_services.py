"""``taskmate.*`` services for the wishlist (#932).

Kept out of ``__init__.py`` so the feature's service surface reads in one
place. ``_async_register_services`` hands over its own guard wrappers, so
these services go through exactly the same gates and audit trail as the rest:

* child actions (add a wish, move points, ask to redeem, …) use the
  linked-child rule, like ``claim_reward`` and ``allocate_points_to_pool`` —
  a child acts for themselves, a parent or admin for anyone;
* parent actions (approve, decline, pledge, remove) use the parent gate, like
  ``approve_reward``.

Which child owns a wish is checked by the coordinator, so a child can't touch
a sibling's wish by passing its id with their own ``child_id``.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CHILD_ID,
    ATTR_POINTS,
    DOMAIN,
    SERVICE_ADD_WISH,
    SERVICE_APPROVE_WISH,
    SERVICE_DECLINE_WISH,
    SERVICE_MOVE_POINTS_TO_WISH,
    SERVICE_PLEDGE_TO_WISH,
    SERVICE_REMOVE_WISH,
    SERVICE_REMOVE_WISH_PLEDGE,
    SERVICE_REQUEST_WISH_REDEEM,
    SERVICE_TAKE_POINTS_FROM_WISH,
    SERVICE_WITHDRAW_WISH,
    WISH_MAX_TARGET,
)
from .models import PLEDGE_MESSAGE_MAX, PLEDGE_NAME_MAX, WISH_DECLINE_REASON_MAX, WISH_LINK_MAX, WISH_NAME_MAX

_LOGGER = logging.getLogger(__name__)

ATTR_WISH_ID = "wish_id"

WISHLIST_SERVICES: tuple[str, ...] = (
    SERVICE_ADD_WISH,
    SERVICE_WITHDRAW_WISH,
    SERVICE_MOVE_POINTS_TO_WISH,
    SERVICE_TAKE_POINTS_FROM_WISH,
    SERVICE_REQUEST_WISH_REDEEM,
    SERVICE_APPROVE_WISH,
    SERVICE_DECLINE_WISH,
    SERVICE_PLEDGE_TO_WISH,
    SERVICE_REMOVE_WISH_PLEDGE,
    SERVICE_REMOVE_WISH,
)

_POINTS = vol.All(vol.Coerce(int), vol.Range(min=1, max=WISH_MAX_TARGET))

Handler = Callable[[ServiceCall], Awaitable[None]]
Wrapper = Callable[[Handler], Handler]


def async_register_wishlist_services(
    hass: HomeAssistant,
    *,
    child_action: Wrapper,
    parent_action: Wrapper,
    get_coordinator: Callable[[], object],
    require_linked_child: Callable[..., Awaitable[None]],
) -> None:
    """Register the wishlist services with the caller's guard wrappers."""

    def _coordinator():
        coordinator = get_coordinator()
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
        return coordinator

    def _as_child(action):
        """Build a child-facing handler: linked-child gate, then ``action``."""

        async def handler(call: ServiceCall) -> None:
            coordinator = _coordinator()
            if not coordinator:
                return
            child_id = call.data[ATTR_CHILD_ID]
            await require_linked_child(hass, call, coordinator, child_id)
            await action(coordinator, call, child_id)

        return child_action(handler)

    def _as_parent(action):
        async def handler(call: ServiceCall) -> None:
            coordinator = _coordinator()
            if not coordinator:
                return
            await action(coordinator, call)

        return parent_action(handler)

    async def add_wish(coordinator, call, child_id):
        await coordinator.async_add_wish(
            child_id,
            call.data["name"],
            call.data["target"],
            link=call.data.get("link", ""),
            photo_url=call.data.get("photo_url", ""),
        )

    async def withdraw_wish(coordinator, call, child_id):
        await coordinator.async_withdraw_wish(call.data[ATTR_WISH_ID], child_id)

    async def move_points(coordinator, call, child_id):
        await coordinator.async_move_points_to_wish(call.data[ATTR_WISH_ID], child_id, call.data[ATTR_POINTS])

    async def take_points(coordinator, call, child_id):
        await coordinator.async_take_points_from_wish(call.data[ATTR_WISH_ID], child_id, call.data[ATTR_POINTS])

    async def request_redeem(coordinator, call, child_id):
        await coordinator.async_request_wish_redeem(call.data[ATTR_WISH_ID], child_id)

    async def approve_wish(coordinator, call):
        await coordinator.async_approve_wish(call.data[ATTR_WISH_ID], call.data.get("target"))

    async def decline_wish(coordinator, call):
        await coordinator.async_decline_wish(call.data[ATTR_WISH_ID], call.data.get("reason", ""))

    async def pledge(coordinator, call):
        await coordinator.async_pledge_to_wish(
            call.data[ATTR_WISH_ID], call.data["name"], call.data[ATTR_POINTS], call.data.get("message", "")
        )

    async def remove_pledge(coordinator, call):
        await coordinator.async_remove_wish_pledge(call.data[ATTR_WISH_ID], call.data["pledge_id"])

    async def remove_wish(coordinator, call):
        await coordinator.async_remove_wish(call.data[ATTR_WISH_ID])

    _WISH_AND_CHILD = {vol.Required(ATTR_WISH_ID): cv.string, vol.Required(ATTR_CHILD_ID): cv.string}
    registrations = (
        (
            SERVICE_ADD_WISH,
            _as_child(add_wish),
            {
                vol.Required(ATTR_CHILD_ID): cv.string,
                vol.Required("name"): vol.All(cv.string, vol.Length(min=1, max=WISH_NAME_MAX)),
                vol.Required("target"): _POINTS,
                vol.Optional("link", default=""): vol.All(cv.string, vol.Length(max=WISH_LINK_MAX)),
                vol.Optional("photo_url", default=""): cv.string,
            },
        ),
        (SERVICE_WITHDRAW_WISH, _as_child(withdraw_wish), dict(_WISH_AND_CHILD)),
        (SERVICE_MOVE_POINTS_TO_WISH, _as_child(move_points), {**_WISH_AND_CHILD, vol.Required(ATTR_POINTS): _POINTS}),
        (
            SERVICE_TAKE_POINTS_FROM_WISH,
            _as_child(take_points),
            {**_WISH_AND_CHILD, vol.Required(ATTR_POINTS): _POINTS},
        ),
        (SERVICE_REQUEST_WISH_REDEEM, _as_child(request_redeem), dict(_WISH_AND_CHILD)),
        (
            SERVICE_APPROVE_WISH,
            _as_parent(approve_wish),
            {vol.Required(ATTR_WISH_ID): cv.string, vol.Optional("target"): _POINTS},
        ),
        (
            SERVICE_DECLINE_WISH,
            _as_parent(decline_wish),
            {
                vol.Required(ATTR_WISH_ID): cv.string,
                vol.Optional("reason", default=""): vol.All(cv.string, vol.Length(max=WISH_DECLINE_REASON_MAX)),
            },
        ),
        (
            SERVICE_PLEDGE_TO_WISH,
            _as_parent(pledge),
            {
                vol.Required(ATTR_WISH_ID): cv.string,
                vol.Required("name"): vol.All(cv.string, vol.Length(min=1, max=PLEDGE_NAME_MAX)),
                vol.Required(ATTR_POINTS): _POINTS,
                vol.Optional("message", default=""): vol.All(cv.string, vol.Length(max=PLEDGE_MESSAGE_MAX)),
            },
        ),
        (
            SERVICE_REMOVE_WISH_PLEDGE,
            _as_parent(remove_pledge),
            {vol.Required(ATTR_WISH_ID): cv.string, vol.Required("pledge_id"): cv.string},
        ),
        (SERVICE_REMOVE_WISH, _as_parent(remove_wish), {vol.Required(ATTR_WISH_ID): cv.string}),
    )
    for name, handler, schema in registrations:
        hass.services.async_register(DOMAIN, name, handler, schema=vol.Schema(schema))
