"""TaskMate - Family Chore Manager for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CHILD_ID,
    ATTR_CHORE_ID,
    ATTR_CHORE_ORDER,
    ATTR_POINTS,
    ATTR_REASON,
    ATTR_REWARD_ID,
    ATTR_SOUND,
    DOMAIN,
    EVENT_PREVIEW_SOUND,
    SERVICE_ADD_POINTS,
    SERVICE_APPROVE_CHORE,
    SERVICE_APPROVE_REWARD,
    SERVICE_CLAIM_REWARD,
    SERVICE_REJECT_REWARD,
    SERVICE_COMPLETE_CHORE,
    SERVICE_PREVIEW_SOUND,
    SERVICE_REJECT_CHORE,
    SERVICE_REMOVE_POINTS,
    SERVICE_SET_CHORE_ORDER,
)
from .coordinator import TaskMateCoordinator
from .frontend import async_register_cards, async_register_frontend

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.BINARY_SENSOR]

# Track if services are registered
SERVICES_REGISTERED = "services_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TaskMate from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = TaskMateCoordinator(hass, entry.entry_id)
    await coordinator.async_initialize()

    # Store initial settings from config entry
    if entry.data.get("points_name"):
        coordinator.storage.set_points_name(entry.data["points_name"])
    if entry.data.get("points_icon"):
        coordinator.storage.set_points_icon(entry.data["points_icon"])
    await coordinator.storage.async_save()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register frontend static paths
    await async_register_frontend(hass)

    # Register and version-update Lovelace resources on every startup.
    # Only TaskMate's own resources (/taskmate/*) are ever touched.
    await async_register_cards(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only once)
    if not hass.data[DOMAIN].get(SERVICES_REGISTERED):
        await _async_register_services(hass)
        hass.data[DOMAIN][SERVICES_REGISTERED] = True

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        await coordinator.async_shutdown()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

        # If no more entries, unregister services
        remaining_entries = [
            key for key in hass.data[DOMAIN].keys() if key != SERVICES_REGISTERED
        ]
        if not remaining_entries:
            _async_unregister_services(hass)
            hass.data[DOMAIN][SERVICES_REGISTERED] = False

    return unload_ok


def _get_coordinator(hass: HomeAssistant) -> TaskMateCoordinator | None:
    """Get the first available coordinator."""
    for key, value in hass.data.get(DOMAIN, {}).items():
        if key != SERVICES_REGISTERED and isinstance(value, TaskMateCoordinator):
            return value
    return None


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register TaskMate services."""

    async def handle_complete_chore(call: ServiceCall) -> None:
        """Handle the complete_chore service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        chore_id = call.data[ATTR_CHORE_ID]
        child_id = call.data[ATTR_CHILD_ID]
        await coordinator.async_complete_chore(chore_id, child_id)

    async def handle_approve_chore(call: ServiceCall) -> None:
        """Handle the approve_chore service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        completion_id = call.data["completion_id"]
        await coordinator.async_approve_chore(completion_id)

    async def handle_reject_chore(call: ServiceCall) -> None:
        """Handle the reject_chore service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        completion_id = call.data["completion_id"]
        await coordinator.async_reject_chore(completion_id)

    async def handle_reject_reward(call: ServiceCall) -> None:
        """Handle the reject_reward service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        claim_id = call.data["claim_id"]
        await coordinator.async_reject_reward(claim_id)

    async def handle_claim_reward(call: ServiceCall) -> None:
        """Handle the claim_reward service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        reward_id = call.data[ATTR_REWARD_ID]
        child_id = call.data[ATTR_CHILD_ID]
        await coordinator.async_claim_reward(reward_id, child_id)

    async def handle_approve_reward(call: ServiceCall) -> None:
        """Handle the approve_reward service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        claim_id = call.data["claim_id"]
        await coordinator.async_approve_reward(claim_id)

    async def handle_add_points(call: ServiceCall) -> None:
        """Handle the add_points service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        child_id = call.data[ATTR_CHILD_ID]
        points = call.data[ATTR_POINTS]
        reason = call.data.get(ATTR_REASON, "")
        await coordinator.async_add_points(child_id, points, reason)

    async def handle_remove_points(call: ServiceCall) -> None:
        """Handle the remove_points service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        child_id = call.data[ATTR_CHILD_ID]
        points = call.data[ATTR_POINTS]
        reason = call.data.get(ATTR_REASON, "")
        await coordinator.async_remove_points(child_id, points, reason)

    async def handle_preview_sound(call: ServiceCall) -> None:
        """Handle the preview_sound service call — fires a browser event for the config-sounds card."""
        sound = call.data.get(ATTR_SOUND, "coin")
        hass.bus.async_fire(EVENT_PREVIEW_SOUND, {"sound": sound})

    async def handle_set_chore_order(call: ServiceCall) -> None:
        """Handle the set_chore_order service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        child_id = call.data[ATTR_CHILD_ID]
        chore_order = call.data[ATTR_CHORE_ORDER]
        await coordinator.async_set_chore_order(child_id, chore_order)

    # Register all services
    hass.services.async_register(
        DOMAIN,
        SERVICE_COMPLETE_CHORE,
        handle_complete_chore,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CHORE_ID): cv.string,
                vol.Required(ATTR_CHILD_ID): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPROVE_CHORE,
        handle_approve_chore,
        schema=vol.Schema(
            {
                vol.Required("completion_id"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REJECT_CHORE,
        handle_reject_chore,
        schema=vol.Schema(
            {
                vol.Required("completion_id"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLAIM_REWARD,
        handle_claim_reward,
        schema=vol.Schema(
            {
                vol.Required(ATTR_REWARD_ID): cv.string,
                vol.Required(ATTR_CHILD_ID): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REJECT_REWARD,
        handle_reject_reward,
        schema=vol.Schema({ vol.Required("claim_id"): cv.string }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPROVE_REWARD,
        handle_approve_reward,
        schema=vol.Schema(
            {
                vol.Required("claim_id"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_POINTS,
        handle_add_points,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CHILD_ID): cv.string,
                vol.Required(ATTR_POINTS): cv.positive_int,
                vol.Optional(ATTR_REASON, default=""): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_POINTS,
        handle_remove_points,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CHILD_ID): cv.string,
                vol.Required(ATTR_POINTS): cv.positive_int,
                vol.Optional(ATTR_REASON, default=""): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PREVIEW_SOUND,
        handle_preview_sound,
        schema=vol.Schema(
            {
                vol.Required(ATTR_SOUND): vol.In([
                    "none", "coin", "levelup", "fanfare", "chime", "powerup", "undo",
                    "fart1", "fart2", "fart3", "fart4", "fart5", "fart6", "fart7",
                    "fart8", "fart9", "fart10", "fart_random",
                ]),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CHORE_ORDER,
        handle_set_chore_order,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CHILD_ID): cv.string,
                vol.Required(ATTR_CHORE_ORDER): vol.All(cv.ensure_list, [cv.string]),
            }
        ),
    )


def _async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister TaskMate services."""
    services = [
        SERVICE_COMPLETE_CHORE,
        SERVICE_APPROVE_CHORE,
        SERVICE_REJECT_CHORE,
        SERVICE_CLAIM_REWARD,
        SERVICE_APPROVE_REWARD,
        SERVICE_REJECT_REWARD,
        SERVICE_ADD_POINTS,
        SERVICE_REMOVE_POINTS,
        SERVICE_SET_CHORE_ORDER,
        SERVICE_PREVIEW_SOUND,
    ]
    for service in services:
        hass.services.async_remove(DOMAIN, service)
