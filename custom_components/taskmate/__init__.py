"""TaskMate - Family Chore Manager for Home Assistant."""
from __future__ import annotations

import copy
import logging
from pathlib import Path

import yaml

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_set_service_schema

from .const import (
    ATTR_AWARDED_BADGE_ID,
    ATTR_BADGE_ASSIGNED_TO,
    ATTR_BADGE_CRITERIA,
    ATTR_BADGE_DESCRIPTION,
    ATTR_BADGE_ENABLED,
    ATTR_BADGE_ICON,
    ATTR_BADGE_ID,
    ATTR_BADGE_NAME,
    ATTR_BADGE_NOTIFY_ON_EARN,
    ATTR_BADGE_POINT_BONUS,
    ATTR_BADGE_TIER,
    ATTR_BONUS_ASSIGNED_TO,
    ATTR_BONUS_DESCRIPTION,
    ATTR_BONUS_ICON,
    ATTR_BONUS_ID,
    ATTR_BONUS_NAME,
    ATTR_BONUS_POINTS,
    ATTR_BONUS_SUBTASK_ID,
    ATTR_CHILD_ID,
    ATTR_CHORE_ASSIGNED_TO,
    ATTR_CHORE_DESCRIPTION,
    ATTR_CHORE_ID,
    ATTR_CHORE_NAME,
    ATTR_CHORE_ONE_SHOT,
    ATTR_CHORE_ORDER,
    ATTR_CHORE_POINTS,
    ATTR_CHORE_REQUIRES_APPROVAL,
    ATTR_CHORE_TIME_CATEGORY,
    ATTR_PENALTY_ASSIGNED_TO,
    ATTR_PENALTY_DESCRIPTION,
    ATTR_PENALTY_ICON,
    ATTR_PENALTY_ID,
    ATTR_PENALTY_NAME,
    ATTR_PENALTY_POINTS,
    ATTR_POINTS,
    ATTR_REASON,
    ATTR_REWARD_ID,
    ATTR_SOUND,
    DOMAIN,
    EVENT_PREVIEW_SOUND,
    SERVICE_ADD_BONUS,
    SERVICE_ADD_CHORE,
    SERVICE_ADD_PENALTY,
    SERVICE_ADD_POINTS,
    SERVICE_ALLOCATE_POINTS_TO_POOL,
    SERVICE_APPLY_BONUS,
    SERVICE_APPLY_PENALTY,
    SERVICE_APPROVE_CHORE,
    SERVICE_APPROVE_REWARD,
    SERVICE_CLAIM_REWARD,
    SERVICE_REJECT_REWARD,
    SERVICE_COMPLETE_BONUS_SUBTASK,
    SERVICE_COMPLETE_CHORE,
    SERVICE_START_TIMED_TASK,
    SERVICE_PAUSE_TIMED_TASK,
    SERVICE_STOP_TIMED_TASK,
    SERVICE_PREVIEW_SOUND,
    SERVICE_REJECT_CHORE,
    SERVICE_REMOVE_BONUS,
    SERVICE_REMOVE_PENALTY,
    SERVICE_REMOVE_POINTS,
    SERVICE_SET_CHORE_ORDER,
    SERVICE_UPDATE_BONUS,
    SERVICE_UPDATE_PENALTY,
    SERVICE_SKIP_CHORE,
    SERVICE_SET_CHORE_MANUAL_START,
    SERVICE_ADD_TASK_GROUP,
    SERVICE_UPDATE_TASK_GROUP,
    SERVICE_REMOVE_TASK_GROUP,
    CONF_TASK_GROUP_ID,
    CONF_TASK_GROUP_NAME,
    CONF_TASK_GROUP_POLICY,
    CONF_TASK_GROUP_CHORE_IDS,
    TASK_GROUP_POLICIES,
    TIME_CATEGORIES,
)
from .coordinator import TaskMateCoordinator
from .frontend import async_register_cards, async_register_frontend
from .models import Badge, BadgeCriterion
from .panel import async_register_panel
from .websocket import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.BINARY_SENSOR]

# Track if services are registered
SERVICES_REGISTERED = "services_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TaskMate from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = TaskMateCoordinator(hass, entry.entry_id)
    await coordinator.async_initialize()

    # Store initial settings from config entry only on first setup
    # (when storage has never been written yet). Once storage exists, the user
    # controls these values via Settings — never overwrite on restart.
    if not coordinator.storage._data.get("_initial_setup_done"):
        if entry.data.get("points_name"):
            coordinator.storage.set_points_name(entry.data["points_name"])
        if entry.data.get("points_icon"):
            coordinator.storage.set_points_icon(entry.data["points_icon"])
        coordinator.storage._data["_initial_setup_done"] = True
    await coordinator.storage.async_save()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    @callback
    def _on_mobile_action(event):
        hass.async_create_task(coordinator.notifications.handle_mobile_action(event))

    coordinator._unsub_mobile_action = hass.bus.async_listen(
        "mobile_app_notification_action", _on_mobile_action,
    )

    # Register frontend static paths
    await async_register_frontend(hass)

    # Register and version-update Lovelace resources on every startup.
    # Only TaskMate's own resources (/taskmate/*) are ever touched.
    await async_register_cards(hass)

    # Register the standalone admin panel (sidebar entry at /taskmate)
    # and the WebSocket commands it talks to.
    await async_register_panel(hass)
    async_register_websocket_commands(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only once)
    if not hass.data[DOMAIN].get(SERVICES_REGISTERED):
        await _async_register_services(hass)
        hass.data[DOMAIN][SERVICES_REGISTERED] = True

    _async_update_service_descriptions(hass)
    coordinator.async_add_listener(
        lambda: _async_update_service_descriptions(hass)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        if hasattr(coordinator, "_unsub_mobile_action") and coordinator._unsub_mobile_action:
            coordinator._unsub_mobile_action()
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


_DYNAMIC_SELECTOR_FIELDS: dict[str, str] = {
    "child_id": "get_children",
    "chore_id": "get_chores",
    "reward_id": "get_rewards",
    "penalty_id": "get_penalties",
    "bonus_id": "get_bonuses",
    "group_id": "get_task_groups",
}

_BASE_SERVICE_DESCRIPTIONS: dict | None = None


def _load_base_descriptions() -> dict:
    """Load and cache the static services.yaml descriptions."""
    global _BASE_SERVICE_DESCRIPTIONS
    if _BASE_SERVICE_DESCRIPTIONS is None:
        path = Path(__file__).parent / "services.yaml"
        with open(path, encoding="utf-8") as fh:
            _BASE_SERVICE_DESCRIPTIONS = yaml.safe_load(fh) or {}
    return _BASE_SERVICE_DESCRIPTIONS


@callback
def _async_update_service_descriptions(hass: HomeAssistant) -> None:
    """Patch service descriptions with dynamic select options from storage."""
    coordinator = _get_coordinator(hass)
    if not coordinator:
        return

    options: dict[str, list[dict[str, str]]] = {}
    for field, getter in _DYNAMIC_SELECTOR_FIELDS.items():
        entities = getattr(coordinator.storage, getter)()
        options[field] = [{"label": e.name, "value": e.id} for e in entities]

    base = _load_base_descriptions()

    for service_name, service_desc in base.items():
        fields = service_desc.get("fields", {})
        if not any(f in _DYNAMIC_SELECTOR_FIELDS for f in fields):
            continue

        patched = copy.deepcopy(service_desc)
        for field_name, field_desc in patched.get("fields", {}).items():
            if field_name in options and options[field_name]:
                field_desc["selector"] = {
                    "select": {
                        "options": options[field_name],
                        "custom_value": True,
                    }
                }

        async_set_service_schema(hass, DOMAIN, service_name, patched)


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

    async def handle_complete_bonus_subtask(call: ServiceCall) -> None:
        """Handle the complete_bonus_subtask service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        chore_id = call.data[ATTR_CHORE_ID]
        bonus_subtask_id = call.data[ATTR_BONUS_SUBTASK_ID]
        child_id = call.data[ATTR_CHILD_ID]
        await coordinator.async_complete_bonus_subtask(chore_id, bonus_subtask_id, child_id)

    async def handle_start_timed_task(call: ServiceCall) -> None:
        """Handle the start_timed_task service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_start_timed_task(
            call.data[ATTR_CHORE_ID], call.data[ATTR_CHILD_ID]
        )

    async def handle_pause_timed_task(call: ServiceCall) -> None:
        """Handle the pause_timed_task service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_pause_timed_task(
            call.data[ATTR_CHORE_ID], call.data[ATTR_CHILD_ID]
        )

    async def handle_stop_timed_task(call: ServiceCall) -> None:
        """Handle the stop_timed_task service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_stop_timed_task(
            call.data[ATTR_CHORE_ID], call.data[ATTR_CHILD_ID]
        )

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

    async def handle_allocate_points_to_pool(call: ServiceCall) -> None:
        """Handle the allocate_points_to_pool service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        child_id = call.data[ATTR_CHILD_ID]
        reward_id = call.data[ATTR_REWARD_ID]
        points = call.data[ATTR_POINTS]
        await coordinator.async_allocate_points_to_pool(child_id, reward_id, points)

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

    async def handle_add_penalty(call: ServiceCall) -> None:
        """Handle the add_penalty service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_add_penalty(
            name=call.data[ATTR_PENALTY_NAME],
            points=call.data[ATTR_PENALTY_POINTS],
            description=call.data.get(ATTR_PENALTY_DESCRIPTION, ""),
            icon=call.data.get(ATTR_PENALTY_ICON, "mdi:alert-circle-outline"),
            assigned_to=call.data.get(ATTR_PENALTY_ASSIGNED_TO, []),
        )

    async def handle_update_penalty(call: ServiceCall) -> None:
        """Handle the update_penalty service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        penalty_id = call.data[ATTR_PENALTY_ID]
        existing = coordinator.storage.get_penalty(penalty_id)
        if not existing:
            _LOGGER.error("Penalty %s not found", penalty_id)
            return
        existing.name = call.data.get(ATTR_PENALTY_NAME, existing.name)
        existing.points = call.data.get(ATTR_PENALTY_POINTS, existing.points)
        existing.description = call.data.get(ATTR_PENALTY_DESCRIPTION, existing.description)
        existing.icon = call.data.get(ATTR_PENALTY_ICON, existing.icon)
        existing.assigned_to = call.data.get(ATTR_PENALTY_ASSIGNED_TO, existing.assigned_to)
        await coordinator.async_update_penalty(existing)

    async def handle_remove_penalty(call: ServiceCall) -> None:
        """Handle the remove_penalty service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_remove_penalty(call.data[ATTR_PENALTY_ID])

    async def handle_apply_penalty(call: ServiceCall) -> None:
        """Handle the apply_penalty service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_apply_penalty(
            penalty_id=call.data[ATTR_PENALTY_ID],
            child_id=call.data[ATTR_CHILD_ID],
        )

    async def handle_add_bonus(call: ServiceCall) -> None:
        """Handle the add_bonus service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_add_bonus(
            name=call.data[ATTR_BONUS_NAME],
            points=call.data[ATTR_BONUS_POINTS],
            description=call.data.get(ATTR_BONUS_DESCRIPTION, ""),
            icon=call.data.get(ATTR_BONUS_ICON, "mdi:star-circle-outline"),
            assigned_to=call.data.get(ATTR_BONUS_ASSIGNED_TO, []),
        )

    async def handle_update_bonus(call: ServiceCall) -> None:
        """Handle the update_bonus service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        bonus_id = call.data[ATTR_BONUS_ID]
        existing = coordinator.storage.get_bonus(bonus_id)
        if not existing:
            _LOGGER.error("Bonus %s not found", bonus_id)
            return
        existing.name = call.data.get(ATTR_BONUS_NAME, existing.name)
        existing.points = call.data.get(ATTR_BONUS_POINTS, existing.points)
        existing.description = call.data.get(ATTR_BONUS_DESCRIPTION, existing.description)
        existing.icon = call.data.get(ATTR_BONUS_ICON, existing.icon)
        existing.assigned_to = call.data.get(ATTR_BONUS_ASSIGNED_TO, existing.assigned_to)
        await coordinator.async_update_bonus(existing)

    async def handle_remove_bonus(call: ServiceCall) -> None:
        """Handle the remove_bonus service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_remove_bonus(call.data[ATTR_BONUS_ID])

    async def handle_apply_bonus(call: ServiceCall) -> None:
        """Handle the apply_bonus service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_apply_bonus(
            bonus_id=call.data[ATTR_BONUS_ID],
            child_id=call.data[ATTR_CHILD_ID],
        )

    async def handle_skip_chore(call: ServiceCall) -> None:
        """Handle the skip_chore service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        try:
            await coordinator.async_skip_chore(call.data[ATTR_CHORE_ID])
        except ValueError as err:
            _LOGGER.warning("skip_chore rejected: %s", err)
            raise

    async def handle_set_chore_manual_start(call: ServiceCall) -> None:
        """Handle the set_chore_manual_start service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        try:
            await coordinator.async_set_chore_manual_start(
                call.data[ATTR_CHORE_ID], call.data[ATTR_CHILD_ID]
            )
        except ValueError as err:
            _LOGGER.warning("set_chore_manual_start rejected: %s", err)
            raise

    async def handle_add_task_group(call: ServiceCall) -> None:
        """Handle the add_task_group service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        try:
            await coordinator.async_add_task_group(
                name=call.data[CONF_TASK_GROUP_NAME],
                policy=call.data[CONF_TASK_GROUP_POLICY],
                chore_ids=call.data.get(CONF_TASK_GROUP_CHORE_IDS, []),
            )
        except ValueError as err:
            _LOGGER.warning("add_task_group rejected: %s", err)
            raise

    async def handle_update_task_group(call: ServiceCall) -> None:
        """Handle the update_task_group service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        try:
            await coordinator.async_update_task_group(
                group_id=call.data[CONF_TASK_GROUP_ID],
                name=call.data.get(CONF_TASK_GROUP_NAME),
                policy=call.data.get(CONF_TASK_GROUP_POLICY),
                chore_ids=call.data.get(CONF_TASK_GROUP_CHORE_IDS),
            )
        except ValueError as err:
            _LOGGER.warning("update_task_group rejected: %s", err)
            raise

    async def handle_remove_task_group(call: ServiceCall) -> None:
        """Handle the remove_task_group service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_remove_task_group(call.data[CONF_TASK_GROUP_ID])

    async def handle_add_chore(call: ServiceCall) -> None:
        """Handle the add_chore service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        schedule_mode = "one_shot" if call.data.get(ATTR_CHORE_ONE_SHOT, False) else "specific_days"
        await coordinator.async_add_chore(
            name=call.data[ATTR_CHORE_NAME],
            description=call.data.get(ATTR_CHORE_DESCRIPTION, ""),
            points=call.data.get(ATTR_CHORE_POINTS, 10),
            assigned_to=call.data.get(ATTR_CHORE_ASSIGNED_TO, []),
            time_category=call.data.get(ATTR_CHORE_TIME_CATEGORY, "anytime"),
            requires_approval=call.data.get(ATTR_CHORE_REQUIRES_APPROVAL, True),
            schedule_mode=schedule_mode,
        )

    async def handle_add_badge(call: ServiceCall) -> None:
        """Handle the add_badge service call (custom only)."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        criteria_data = call.data.get(ATTR_BADGE_CRITERIA, []) or []
        criteria = [BadgeCriterion.from_dict(c) for c in criteria_data]
        badge = Badge(
            name=call.data[ATTR_BADGE_NAME],
            description=call.data.get(ATTR_BADGE_DESCRIPTION, ""),
            icon=call.data.get(ATTR_BADGE_ICON, "mdi:trophy"),
            tier=call.data.get(ATTR_BADGE_TIER, "bronze"),
            point_bonus=int(call.data.get(ATTR_BADGE_POINT_BONUS, 0) or 0),
            criteria=criteria,
            assigned_to=list(call.data.get(ATTR_BADGE_ASSIGNED_TO, []) or []),
            notify_on_earn=bool(call.data.get(ATTR_BADGE_NOTIFY_ON_EARN, True)),
            builtin=False,
        )
        coordinator.storage.add_badge(badge)
        await coordinator.storage.async_save()
        await coordinator.async_refresh()

    async def handle_update_badge(call: ServiceCall) -> None:
        """Handle the update_badge service call.

        Built-ins: only point_bonus / tier / assigned_to / enabled / notify_on_earn editable.
        Custom: all fields editable.
        """
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        badge_id = call.data[ATTR_BADGE_ID]
        existing = coordinator.storage.get_badge(badge_id)
        if not existing:
            _LOGGER.error("Badge %s not found", badge_id)
            return

        if existing.builtin:
            existing.point_bonus = int(call.data.get(ATTR_BADGE_POINT_BONUS, existing.point_bonus) or 0)
            existing.tier = call.data.get(ATTR_BADGE_TIER, existing.tier)
            existing.assigned_to = list(call.data.get(ATTR_BADGE_ASSIGNED_TO, existing.assigned_to) or [])
            existing.enabled = bool(call.data.get(ATTR_BADGE_ENABLED, existing.enabled))
            existing.notify_on_earn = bool(call.data.get(ATTR_BADGE_NOTIFY_ON_EARN, existing.notify_on_earn))
        else:
            existing.name = call.data.get(ATTR_BADGE_NAME, existing.name)
            existing.description = call.data.get(ATTR_BADGE_DESCRIPTION, existing.description)
            existing.icon = call.data.get(ATTR_BADGE_ICON, existing.icon)
            existing.tier = call.data.get(ATTR_BADGE_TIER, existing.tier)
            existing.point_bonus = int(call.data.get(ATTR_BADGE_POINT_BONUS, existing.point_bonus) or 0)
            if ATTR_BADGE_CRITERIA in call.data:
                existing.criteria = [BadgeCriterion.from_dict(c) for c in (call.data[ATTR_BADGE_CRITERIA] or [])]
            existing.assigned_to = list(call.data.get(ATTR_BADGE_ASSIGNED_TO, existing.assigned_to) or [])
            existing.enabled = bool(call.data.get(ATTR_BADGE_ENABLED, existing.enabled))
            existing.notify_on_earn = bool(call.data.get(ATTR_BADGE_NOTIFY_ON_EARN, existing.notify_on_earn))

        coordinator.storage.update_badge(existing)
        await coordinator.storage.async_save()
        await coordinator.async_refresh()

    async def handle_remove_badge(call: ServiceCall) -> None:
        """Handle the remove_badge service call (custom only — built-ins protected)."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        badge_id = call.data[ATTR_BADGE_ID]
        existing = coordinator.storage.get_badge(badge_id)
        if not existing:
            _LOGGER.error("Badge %s not found", badge_id)
            return
        if existing.builtin:
            _LOGGER.warning("Refusing to remove built-in badge %s", badge_id)
            return
        coordinator.storage.remove_badge(badge_id)
        await coordinator.storage.async_save()
        await coordinator.async_refresh()

    async def handle_award_badge_manually(call: ServiceCall) -> None:
        """Handle the award_badge_manually service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.badges.award_manually(
            call.data[ATTR_CHILD_ID],
            call.data[ATTR_BADGE_ID],
        )
        await coordinator.async_refresh()

    async def handle_revoke_badge(call: ServiceCall) -> None:
        """Handle the revoke_badge service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.badges.revoke(call.data[ATTR_AWARDED_BADGE_ID])
        await coordinator.async_refresh()

    async def handle_rebuild_badges(call: ServiceCall) -> None:
        """Handle the rebuild_badges service call (silent retroactive sweep)."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        count = await coordinator.badges.rebuild_all()
        _LOGGER.info("rebuild_badges awarded %d retroactive badges", count)
        await coordinator.async_refresh()

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
        SERVICE_COMPLETE_BONUS_SUBTASK,
        handle_complete_bonus_subtask,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CHORE_ID): cv.string,
                vol.Required(ATTR_BONUS_SUBTASK_ID): cv.string,
                vol.Required(ATTR_CHILD_ID): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_TIMED_TASK,
        handle_start_timed_task,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CHORE_ID): cv.string,
                vol.Required(ATTR_CHILD_ID): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PAUSE_TIMED_TASK,
        handle_pause_timed_task,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CHORE_ID): cv.string,
                vol.Required(ATTR_CHILD_ID): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_TIMED_TASK,
        handle_stop_timed_task,
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
        SERVICE_ALLOCATE_POINTS_TO_POOL,
        handle_allocate_points_to_pool,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CHILD_ID): cv.string,
                vol.Required(ATTR_REWARD_ID): cv.string,
                vol.Required(ATTR_POINTS): cv.positive_int,
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


    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_PENALTY,
        handle_add_penalty,
        schema=vol.Schema({
            vol.Required(ATTR_PENALTY_NAME): cv.string,
            vol.Required(ATTR_PENALTY_POINTS): cv.positive_int,
            vol.Optional(ATTR_PENALTY_DESCRIPTION, default=""): cv.string,
            vol.Optional(ATTR_PENALTY_ICON, default="mdi:alert-circle-outline"): cv.string,
            vol.Optional(ATTR_PENALTY_ASSIGNED_TO, default=[]): vol.All(cv.ensure_list, [cv.string]),
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_PENALTY,
        handle_update_penalty,
        schema=vol.Schema({
            vol.Required(ATTR_PENALTY_ID): cv.string,
            vol.Optional(ATTR_PENALTY_NAME): cv.string,
            vol.Optional(ATTR_PENALTY_POINTS): cv.positive_int,
            vol.Optional(ATTR_PENALTY_DESCRIPTION): cv.string,
            vol.Optional(ATTR_PENALTY_ICON): cv.string,
            vol.Optional(ATTR_PENALTY_ASSIGNED_TO): vol.All(cv.ensure_list, [cv.string]),
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_PENALTY,
        handle_remove_penalty,
        schema=vol.Schema({vol.Required(ATTR_PENALTY_ID): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_PENALTY,
        handle_apply_penalty,
        schema=vol.Schema({
            vol.Required(ATTR_PENALTY_ID): cv.string,
            vol.Required(ATTR_CHILD_ID): cv.string,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_BONUS,
        handle_add_bonus,
        schema=vol.Schema({
            vol.Required(ATTR_BONUS_NAME): cv.string,
            vol.Required(ATTR_BONUS_POINTS): cv.positive_int,
            vol.Optional(ATTR_BONUS_DESCRIPTION, default=""): cv.string,
            vol.Optional(ATTR_BONUS_ICON, default="mdi:star-circle-outline"): cv.string,
            vol.Optional(ATTR_BONUS_ASSIGNED_TO, default=[]): vol.All(cv.ensure_list, [cv.string]),
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_BONUS,
        handle_update_bonus,
        schema=vol.Schema({
            vol.Required(ATTR_BONUS_ID): cv.string,
            vol.Optional(ATTR_BONUS_NAME): cv.string,
            vol.Optional(ATTR_BONUS_POINTS): cv.positive_int,
            vol.Optional(ATTR_BONUS_DESCRIPTION): cv.string,
            vol.Optional(ATTR_BONUS_ICON): cv.string,
            vol.Optional(ATTR_BONUS_ASSIGNED_TO): vol.All(cv.ensure_list, [cv.string]),
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_BONUS,
        handle_remove_bonus,
        schema=vol.Schema({vol.Required(ATTR_BONUS_ID): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_BONUS,
        handle_apply_bonus,
        schema=vol.Schema({
            vol.Required(ATTR_BONUS_ID): cv.string,
            vol.Required(ATTR_CHILD_ID): cv.string,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_CHORE,
        handle_add_chore,
        schema=vol.Schema({
            vol.Required(ATTR_CHORE_NAME): cv.string,
            vol.Optional(ATTR_CHORE_DESCRIPTION, default=""): cv.string,
            vol.Optional(ATTR_CHORE_POINTS, default=10): cv.positive_int,
            vol.Optional(ATTR_CHORE_ASSIGNED_TO, default=[]): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_CHORE_TIME_CATEGORY, default="anytime"): vol.In(TIME_CATEGORIES),
            vol.Optional(ATTR_CHORE_ONE_SHOT, default=False): cv.boolean,
            vol.Optional(ATTR_CHORE_REQUIRES_APPROVAL, default=True): cv.boolean,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SKIP_CHORE,
        handle_skip_chore,
        schema=vol.Schema({vol.Required(ATTR_CHORE_ID): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CHORE_MANUAL_START,
        handle_set_chore_manual_start,
        schema=vol.Schema({
            vol.Required(ATTR_CHORE_ID): cv.string,
            vol.Required(ATTR_CHILD_ID): cv.string,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_TASK_GROUP,
        handle_add_task_group,
        schema=vol.Schema({
            vol.Required(CONF_TASK_GROUP_NAME): cv.string,
            vol.Required(CONF_TASK_GROUP_POLICY): vol.In(TASK_GROUP_POLICIES),
            vol.Optional(CONF_TASK_GROUP_CHORE_IDS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_TASK_GROUP,
        handle_update_task_group,
        schema=vol.Schema({
            vol.Required(CONF_TASK_GROUP_ID): cv.string,
            vol.Optional(CONF_TASK_GROUP_NAME): cv.string,
            vol.Optional(CONF_TASK_GROUP_POLICY): vol.In(TASK_GROUP_POLICIES),
            vol.Optional(CONF_TASK_GROUP_CHORE_IDS): vol.All(cv.ensure_list, [cv.string]),
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_TASK_GROUP,
        handle_remove_task_group,
        schema=vol.Schema({vol.Required(CONF_TASK_GROUP_ID): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        "add_badge",
        handle_add_badge,
        schema=vol.Schema({
            vol.Required(ATTR_BADGE_NAME): cv.string,
            vol.Optional(ATTR_BADGE_DESCRIPTION, default=""): cv.string,
            vol.Optional(ATTR_BADGE_ICON, default="mdi:trophy"): cv.string,
            vol.Optional(ATTR_BADGE_TIER, default="bronze"): vol.In(["bronze", "silver", "gold", "platinum"]),
            vol.Optional(ATTR_BADGE_POINT_BONUS, default=0): vol.Coerce(int),
            vol.Optional(ATTR_BADGE_CRITERIA, default=[]): list,
            vol.Optional(ATTR_BADGE_ASSIGNED_TO, default=[]): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_BADGE_NOTIFY_ON_EARN, default=True): cv.boolean,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        "update_badge",
        handle_update_badge,
        schema=vol.Schema({
            vol.Required(ATTR_BADGE_ID): cv.string,
            vol.Optional(ATTR_BADGE_NAME): cv.string,
            vol.Optional(ATTR_BADGE_DESCRIPTION): cv.string,
            vol.Optional(ATTR_BADGE_ICON): cv.string,
            vol.Optional(ATTR_BADGE_TIER): vol.In(["bronze", "silver", "gold", "platinum"]),
            vol.Optional(ATTR_BADGE_POINT_BONUS): vol.Coerce(int),
            vol.Optional(ATTR_BADGE_CRITERIA): list,
            vol.Optional(ATTR_BADGE_ASSIGNED_TO): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_BADGE_ENABLED): cv.boolean,
            vol.Optional(ATTR_BADGE_NOTIFY_ON_EARN): cv.boolean,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        "remove_badge",
        handle_remove_badge,
        schema=vol.Schema({vol.Required(ATTR_BADGE_ID): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        "award_badge_manually",
        handle_award_badge_manually,
        schema=vol.Schema({
            vol.Required(ATTR_BADGE_ID): cv.string,
            vol.Required(ATTR_CHILD_ID): cv.string,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        "revoke_badge",
        handle_revoke_badge,
        schema=vol.Schema({vol.Required(ATTR_AWARDED_BADGE_ID): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        "rebuild_badges",
        handle_rebuild_badges,
        schema=vol.Schema({}),
    )


def _async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister TaskMate services."""
    services = [
        SERVICE_COMPLETE_CHORE,
        SERVICE_COMPLETE_BONUS_SUBTASK,
        SERVICE_APPROVE_CHORE,
        SERVICE_REJECT_CHORE,
        SERVICE_CLAIM_REWARD,
        SERVICE_APPROVE_REWARD,
        SERVICE_REJECT_REWARD,
        SERVICE_ALLOCATE_POINTS_TO_POOL,
        SERVICE_ADD_POINTS,
        SERVICE_REMOVE_POINTS,
        SERVICE_SET_CHORE_ORDER,
        SERVICE_PREVIEW_SOUND,
        SERVICE_ADD_PENALTY,
        SERVICE_UPDATE_PENALTY,
        SERVICE_REMOVE_PENALTY,
        SERVICE_APPLY_PENALTY,
        SERVICE_ADD_BONUS,
        SERVICE_UPDATE_BONUS,
        SERVICE_REMOVE_BONUS,
        SERVICE_APPLY_BONUS,
        SERVICE_ADD_CHORE,
        SERVICE_SKIP_CHORE,
        SERVICE_SET_CHORE_MANUAL_START,
        SERVICE_ADD_TASK_GROUP,
        SERVICE_UPDATE_TASK_GROUP,
        SERVICE_REMOVE_TASK_GROUP,
        SERVICE_START_TIMED_TASK,
        SERVICE_PAUSE_TIMED_TASK,
        SERVICE_STOP_TIMED_TASK,
        "add_badge",
        "update_badge",
        "remove_badge",
        "award_badge_manually",
        "revoke_badge",
        "rebuild_badges",
    ]
    for service in services:
        hass.services.async_remove(DOMAIN, service)
