"""TaskMate - Family Chore Manager for Home Assistant."""
from __future__ import annotations

import copy
import logging
from functools import wraps
from pathlib import Path

import voluptuous as vol
import yaml
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_set_service_schema

from .const import (
    ATTR_AS_PARENT,
    ATTR_AWARDED_BADGE_ID,
    ATTR_BADGE_ASSIGNED_TO,
    ATTR_BADGE_COMBINATOR,
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
    CONF_TASK_GROUP_CHORE_IDS,
    CONF_TASK_GROUP_ID,
    CONF_TASK_GROUP_NAME,
    CONF_TASK_GROUP_POLICY,
    DEFAULT_DIFFICULTY,
    DIFFICULTY_TIERS,
    DOMAIN,
    EVENT_PREVIEW_SOUND,
    SERVICE_ADD_BONUS,
    SERVICE_ADD_CHORE,
    SERVICE_ADD_PENALTY,
    SERVICE_ADD_POINTS,
    SERVICE_ADD_TASK_GROUP,
    SERVICE_ALLOCATE_POINTS_TO_POOL,
    SERVICE_APPLY_BONUS,
    SERVICE_APPLY_MANDATORY_PENALTY,
    SERVICE_APPLY_PENALTY,
    SERVICE_APPROVE_CHORE,
    SERVICE_APPROVE_REWARD,
    SERVICE_CHOOSE_AVATAR,
    SERVICE_CLAIM_REWARD,
    SERVICE_COMPLETE_BONUS_SUBTASK,
    SERVICE_COMPLETE_CHORE,
    SERVICE_DISMISS_MANDATORY_CHORE,
    SERVICE_GIFT_POINTS,
    SERVICE_PAUSE_TIMED_TASK,
    SERVICE_POSTPONE_MANDATORY_CHORE,
    SERVICE_PREVIEW_SOUND,
    SERVICE_RECORD_ALLOWANCE_PAYOUT,
    SERVICE_REJECT_CHORE,
    SERVICE_REJECT_REWARD,
    SERVICE_REMOVE_BONUS,
    SERVICE_REMOVE_PENALTY,
    SERVICE_REMOVE_POINTS,
    SERVICE_REMOVE_TASK_GROUP,
    SERVICE_REQUEST_SWAP,
    SERVICE_SET_CHORE_MANUAL_START,
    SERVICE_SET_CHORE_ORDER,
    SERVICE_SKIP_CHORE,
    SERVICE_START_TIMED_TASK,
    SERVICE_STOP_TIMED_TASK,
    SERVICE_TEST_NOTIFICATION,
    SERVICE_UNDO_CHORE_APPROVAL,
    SERVICE_UNDO_TRANSACTION,
    SERVICE_UPDATE_BONUS,
    SERVICE_UPDATE_PENALTY,
    SERVICE_UPDATE_TASK_GROUP,
    TASK_GROUP_POLICIES,
    TIME_CATEGORIES,
)
from .coordinator import TaskMateCoordinator
from .frontend import async_register_cards, async_register_frontend
from .models import Badge, BadgeCriterion
from .panel import async_register_panel
from .websocket import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.NUMBER, Platform.SELECT, Platform.TODO]

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
    if not coordinator.storage.is_initial_setup_done():
        if entry.data.get("points_name"):
            coordinator.storage.set_points_name(entry.data["points_name"])
        if entry.data.get("points_icon"):
            coordinator.storage.set_points_icon(entry.data["points_icon"])
        coordinator.storage.mark_initial_setup_done()
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

    # Conversation/voice intents (FEAT-12). Lazy import so a missing conversation
    # stack never blocks setup.
    try:
        from .intents import async_setup_intents
        async_setup_intents(hass)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("TaskMate intents not registered: %s", err)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only once)
    if not hass.data[DOMAIN].get(SERVICES_REGISTERED):
        await _async_register_services(hass)
        hass.data[DOMAIN][SERVICES_REGISTERED] = True

    # Pre-load services.yaml off the event loop so the @callback below
    # never has to do blocking disk I/O.
    await hass.async_add_executor_job(_load_base_descriptions)

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

        # If no more entries, unregister services. Count only coordinator
        # instances — hass.data[DOMAIN] also holds bookkeeping flags.
        remaining_entries = [
            value for value in hass.data[DOMAIN].values()
            if isinstance(value, TaskMateCoordinator)
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

    # PERF-4: the dynamic selectors mirror children/chores/rewards/etc., which
    # only change via a save (bumping storage.data_version). Use that as the
    # fingerprint and short-circuit BEFORE hydrating every entity from its dict
    # + repr()-ing them — both of which previously ran on every listener fire.
    fingerprint = coordinator.storage.data_version
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("_service_desc_fingerprint") == fingerprint:
        return
    domain_data["_service_desc_fingerprint"] = fingerprint

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


async def _async_require_admin(hass: HomeAssistant, call: ServiceCall) -> None:
    """Reject user-initiated service calls that aren't from an admin.

    Calls without a user context (automations, scripts, schedules) pass
    through; user-initiated calls must come from an admin, matching the
    admin gate on the panel's WebSocket commands.
    """
    if call.context.user_id:
        user = await hass.auth.async_get_user(call.context.user_id)
        if user is None or not user.is_admin:
            raise Unauthorized(context=call.context)


_AUDIT_TARGET_KEYS = (
    "chore_id", "reward_id", "penalty_id", "bonus_id", "badge_id",
    "task_group_id", "miss_id", "claim_id", "transaction_id", "type_id",
)


async def _async_record_service_audit(hass: HomeAssistant, call: ServiceCall) -> None:
    """Record a mutating service call in the admin audit log (SEC-3).

    The panel's WebSocket path audits every config change; the equivalent
    ``taskmate.*`` services did not, so point/penalty/chore mutations made via
    Dev Tools or automations left no trail. Best-effort: never block the action.
    """
    coordinator = _get_coordinator(hass)
    if not coordinator:
        return
    user_id = call.context.user_id or ""
    user_name = ""
    if user_id:
        try:
            user = await hass.auth.async_get_user(user_id)
            user_name = user.name if user else ""
        except Exception:  # noqa: BLE001 - audit must never break the action
            user_name = ""
    target = ""
    cid = call.data.get(ATTR_CHILD_ID) or call.data.get("child_id") or call.data.get("to_child_id")
    if cid:
        child = coordinator.get_child(cid)
        target = getattr(child, "name", "") or str(cid)
    else:
        for key in _AUDIT_TARGET_KEYS:
            if call.data.get(key):
                target = f"{key}={call.data[key]}"
                break
    try:
        await coordinator.async_record_audit(
            user_id, user_name, f"service.{call.service}", target
        )
    except Exception:  # noqa: BLE001 - audit must never break the action
        _LOGGER.debug("Failed to record service audit for %s", call.service, exc_info=True)


def _safe(handler):
    """Surface coordinator validation errors as clean service errors.

    Coordinator methods raise ``ValueError`` for bad or rejected input (unknown
    id, locked avatar, insufficient balance, swap not allowed, ...). Left
    unhandled those reach the caller as an unhandled error + a full traceback in
    the log. Re-raise as ``ServiceValidationError`` so a frontend/WebSocket
    caller (the cards, the admin panel, Dev Tools) gets a clean failure result
    with the human-readable message and no traceback is logged.
    ``ServiceValidationError`` is not a ``ValueError``, so a handler that already
    raises it (e.g. complete_chore) passes through untouched.
    """
    @wraps(handler)
    async def wrapped(call: ServiceCall) -> None:
        try:
            await handler(call)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
    return wrapped


async def _async_require_linked_child(
    hass: HomeAssistant, call: ServiceCall, coordinator, child_id: str
) -> None:
    """Restrict a child's self-service call to that child's linked HA user.

    Opt-in: only enforced when the child has a ``linked_user_id`` set. Children
    with no link keep the default open/kiosk behaviour (any user, e.g. a shared
    tablet). Admins and context-less calls (automations, scripts) always pass.
    """
    user_id = call.context.user_id
    if not user_id:
        return
    child = coordinator.get_child(child_id)
    linked = getattr(child, "linked_user_id", "") if child else ""
    if linked == user_id:
        return
    user = await hass.auth.async_get_user(user_id)
    if user is not None and user.is_admin:
        return
    if linked:
        # Target child is linked to a different user and caller isn't admin.
        raise Unauthorized(context=call.context)
    # Target child is unlinked (kiosk). A user who is themselves linked to a
    # *different* child must not act through an unlinked child (SEC-4); truly
    # unlinked/anonymous callers keep the open kiosk behaviour.
    others = coordinator.storage.get_children() or []
    if any(getattr(c, "linked_user_id", "") == user_id for c in others):
        raise Unauthorized(context=call.context)


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register TaskMate services."""

    def _admin(handler):
        """Wrap a service handler so only admins (or context-less calls) run it."""
        @wraps(handler)
        async def wrapped(call: ServiceCall) -> None:
            await _async_require_admin(hass, call)
            await handler(call)
            await _async_record_service_audit(hass, call)
        # Compose with _safe so admin handlers also convert coordinator
        # ValueErrors into clean validation errors. The admin gate raises
        # Unauthorized (not ValueError), so it is unaffected and still 401s.
        return _safe(wrapped)

    async def handle_complete_chore(call: ServiceCall) -> None:
        """Handle the complete_chore service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        chore_id = call.data[ATTR_CHORE_ID]
        child_id = call.data[ATTR_CHILD_ID]
        as_parent = call.data.get(ATTR_AS_PARENT, False)
        if as_parent:
            # Completing on behalf of a child (auto-approve + instant award) is a
            # parent privilege. Enforce it on the backend, not just by hiding the
            # control in the UI — the service is callable by any authenticated
            # user. Normal child self-completion (as_parent omitted) stays open.
            await _async_require_admin(hass, call)
        else:
            await _async_require_linked_child(hass, call, coordinator, child_id)
        try:
            await coordinator.async_complete_chore(
                chore_id, child_id, as_parent=as_parent,
                photo_url=call.data.get("photo_url", ""),
            )
        except ValueError as err:
            # Only genuinely bad input (unknown chore/child) raises now — expected
            # soft rejections (daily limit, race lost, not-your-turn) are silent
            # no-ops inside the coordinator. Surface real errors as a clean
            # validation error rather than an unhandled 500 + traceback.
            raise ServiceValidationError(str(err)) from err

    async def handle_complete_bonus_subtask(call: ServiceCall) -> None:
        """Handle the complete_bonus_subtask service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        chore_id = call.data[ATTR_CHORE_ID]
        bonus_subtask_id = call.data[ATTR_BONUS_SUBTASK_ID]
        child_id = call.data[ATTR_CHILD_ID]
        await _async_require_linked_child(hass, call, coordinator, child_id)
        await coordinator.async_complete_bonus_subtask(chore_id, bonus_subtask_id, child_id)

    async def handle_start_timed_task(call: ServiceCall) -> None:
        """Handle the start_timed_task service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await _async_require_linked_child(hass, call, coordinator, call.data[ATTR_CHILD_ID])
        await coordinator.async_start_timed_task(
            call.data[ATTR_CHORE_ID], call.data[ATTR_CHILD_ID]
        )

    async def handle_pause_timed_task(call: ServiceCall) -> None:
        """Handle the pause_timed_task service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await _async_require_linked_child(hass, call, coordinator, call.data[ATTR_CHILD_ID])
        await coordinator.async_pause_timed_task(
            call.data[ATTR_CHORE_ID], call.data[ATTR_CHILD_ID]
        )

    async def handle_stop_timed_task(call: ServiceCall) -> None:
        """Handle the stop_timed_task service call."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await _async_require_linked_child(hass, call, coordinator, call.data[ATTR_CHILD_ID])
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

    async def handle_apply_mandatory_penalty(call: ServiceCall) -> None:
        """Handle apply_mandatory_penalty (deduct penalty for a missed mandatory chore)."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_apply_mandatory_penalty(call.data["miss_id"])

    async def handle_postpone_mandatory_chore(call: ServiceCall) -> None:
        """Handle postpone_mandatory_chore (give a missed mandatory chore another period)."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_postpone_mandatory_chore(call.data["miss_id"])

    async def handle_dismiss_mandatory_chore(call: ServiceCall) -> None:
        """Handle dismiss_mandatory_chore (clear a missed mandatory chore, no penalty)."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_dismiss_mandatory_chore(call.data["miss_id"])

    async def handle_undo_transaction(call: ServiceCall) -> None:
        """Handle undo_transaction (reverse a penalty/bonus/manual/gift)."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_undo_transaction(call.data["transaction_id"])

    async def handle_undo_chore_approval(call: ServiceCall) -> None:
        """Handle undo_chore_approval (revert an approved completion to pending)."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_undo_chore_approval(call.data["completion_id"])

    async def handle_test_notification(call: ServiceCall) -> None:
        """Send a sample notification of the given type to its enabled routes."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.notifications.send_test(call.data["type_id"])

    async def handle_gift_points(call: ServiceCall) -> None:
        """Transfer spendable points from one child to another."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_gift_points(
            call.data["from_child_id"], call.data["to_child_id"], call.data["points"],
        )

    async def handle_record_allowance_payout(call: ServiceCall) -> None:
        """Record a parent-confirmed allowance payout (deduct points, log cash)."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        await coordinator.async_record_allowance_payout(
            call.data["child_id"], call.data["points"],
        )

    async def handle_request_swap(call: ServiceCall) -> None:
        """A child requests to take over today's rotation assignment of a chore."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        requester_id = call.data["requester_id"]
        await _async_require_linked_child(hass, call, coordinator, requester_id)
        await coordinator.async_request_swap(call.data["chore_id"], requester_id)

    async def handle_choose_avatar(call: ServiceCall) -> None:
        """A child switches to an avatar they've unlocked."""
        coordinator = _get_coordinator(hass)
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        child_id = call.data[ATTR_CHILD_ID]
        await _async_require_linked_child(hass, call, coordinator, child_id)
        await coordinator.async_set_avatar(child_id, call.data["icon"], enforce_unlock=True)

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
        await _async_require_linked_child(hass, call, coordinator, child_id)
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
        await _async_require_linked_child(hass, call, coordinator, child_id)
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
            difficulty=call.data.get("difficulty", "medium"),
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
            combinator="OR" if str(call.data.get(ATTR_BADGE_COMBINATOR, "AND")).upper() == "OR" else "AND",
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
            if ATTR_BADGE_COMBINATOR in call.data:
                existing.combinator = "OR" if str(call.data[ATTR_BADGE_COMBINATOR]).upper() == "OR" else "AND"
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
                vol.Optional(ATTR_AS_PARENT, default=False): cv.boolean,
                vol.Optional("photo_url"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_COMPLETE_BONUS_SUBTASK,
        _safe(handle_complete_bonus_subtask),
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
        _safe(handle_start_timed_task),
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
        _safe(handle_pause_timed_task),
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
        _safe(handle_stop_timed_task),
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
        _admin(handle_approve_chore),
        schema=vol.Schema(
            {
                vol.Required("completion_id"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REJECT_CHORE,
        _admin(handle_reject_chore),
        schema=vol.Schema(
            {
                vol.Required("completion_id"): cv.string,
            }
        ),
    )

    _miss_schema = vol.Schema({vol.Required("miss_id"): cv.string})
    hass.services.async_register(
        DOMAIN, SERVICE_APPLY_MANDATORY_PENALTY,
        _admin(handle_apply_mandatory_penalty), schema=_miss_schema,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_POSTPONE_MANDATORY_CHORE,
        _admin(handle_postpone_mandatory_chore), schema=_miss_schema,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DISMISS_MANDATORY_CHORE,
        _admin(handle_dismiss_mandatory_chore), schema=_miss_schema,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UNDO_TRANSACTION,
        _admin(handle_undo_transaction),
        schema=vol.Schema(
            {
                vol.Required("transaction_id"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UNDO_CHORE_APPROVAL,
        _admin(handle_undo_chore_approval),
        schema=vol.Schema(
            {
                vol.Required("completion_id"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TEST_NOTIFICATION,
        _admin(handle_test_notification),
        schema=vol.Schema(
            {
                vol.Required("type_id"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GIFT_POINTS,
        _admin(handle_gift_points),
        schema=vol.Schema(
            {
                vol.Required("from_child_id"): cv.string,
                vol.Required("to_child_id"): cv.string,
                vol.Required("points"): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RECORD_ALLOWANCE_PAYOUT,
        _admin(handle_record_allowance_payout),
        schema=vol.Schema(
            {
                vol.Required("child_id"): cv.string,
                vol.Required("points"): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REQUEST_SWAP,
        _safe(handle_request_swap),
        schema=vol.Schema(
            {
                vol.Required("chore_id"): cv.string,
                vol.Required("requester_id"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CHOOSE_AVATAR,
        _safe(handle_choose_avatar),
        schema=vol.Schema(
            {
                vol.Required(ATTR_CHILD_ID): cv.string,
                vol.Required("icon"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLAIM_REWARD,
        _safe(handle_claim_reward),
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
        _admin(handle_reject_reward),
        schema=vol.Schema({ vol.Required("claim_id"): cv.string }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPROVE_REWARD,
        _admin(handle_approve_reward),
        schema=vol.Schema(
            {
                vol.Required("claim_id"): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ALLOCATE_POINTS_TO_POOL,
        _safe(handle_allocate_points_to_pool),
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
        _admin(handle_add_points),
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
        _admin(handle_remove_points),
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
        _safe(handle_preview_sound),
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
        _admin(handle_set_chore_order),
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
        _admin(handle_add_penalty),
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
        _admin(handle_update_penalty),
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
        _admin(handle_remove_penalty),
        schema=vol.Schema({vol.Required(ATTR_PENALTY_ID): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_PENALTY,
        _admin(handle_apply_penalty),
        schema=vol.Schema({
            vol.Required(ATTR_PENALTY_ID): cv.string,
            vol.Required(ATTR_CHILD_ID): cv.string,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_BONUS,
        _admin(handle_add_bonus),
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
        _admin(handle_update_bonus),
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
        _admin(handle_remove_bonus),
        schema=vol.Schema({vol.Required(ATTR_BONUS_ID): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_BONUS,
        _admin(handle_apply_bonus),
        schema=vol.Schema({
            vol.Required(ATTR_BONUS_ID): cv.string,
            vol.Required(ATTR_CHILD_ID): cv.string,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_CHORE,
        _admin(handle_add_chore),
        schema=vol.Schema({
            vol.Required(ATTR_CHORE_NAME): cv.string,
            vol.Optional(ATTR_CHORE_DESCRIPTION, default=""): cv.string,
            vol.Optional(ATTR_CHORE_POINTS, default=10): cv.positive_int,
            vol.Optional(ATTR_CHORE_ASSIGNED_TO, default=[]): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_CHORE_TIME_CATEGORY, default="anytime"): vol.In(TIME_CATEGORIES),
            vol.Optional("difficulty", default=DEFAULT_DIFFICULTY): vol.In(DIFFICULTY_TIERS),
            vol.Optional(ATTR_CHORE_ONE_SHOT, default=False): cv.boolean,
            vol.Optional(ATTR_CHORE_REQUIRES_APPROVAL, default=True): cv.boolean,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SKIP_CHORE,
        _admin(handle_skip_chore),
        schema=vol.Schema({vol.Required(ATTR_CHORE_ID): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CHORE_MANUAL_START,
        _admin(handle_set_chore_manual_start),
        schema=vol.Schema({
            vol.Required(ATTR_CHORE_ID): cv.string,
            vol.Required(ATTR_CHILD_ID): cv.string,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_TASK_GROUP,
        _admin(handle_add_task_group),
        schema=vol.Schema({
            vol.Required(CONF_TASK_GROUP_NAME): cv.string,
            vol.Required(CONF_TASK_GROUP_POLICY): vol.In(TASK_GROUP_POLICIES),
            vol.Optional(CONF_TASK_GROUP_CHORE_IDS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_TASK_GROUP,
        _admin(handle_update_task_group),
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
        _admin(handle_remove_task_group),
        schema=vol.Schema({vol.Required(CONF_TASK_GROUP_ID): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        "add_badge",
        _admin(handle_add_badge),
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
        _admin(handle_update_badge),
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
        _admin(handle_remove_badge),
        schema=vol.Schema({vol.Required(ATTR_BADGE_ID): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        "award_badge_manually",
        _admin(handle_award_badge_manually),
        schema=vol.Schema({
            vol.Required(ATTR_BADGE_ID): cv.string,
            vol.Required(ATTR_CHILD_ID): cv.string,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        "revoke_badge",
        _admin(handle_revoke_badge),
        schema=vol.Schema({vol.Required(ATTR_AWARDED_BADGE_ID): cv.string}),
    )

    hass.services.async_register(
        DOMAIN,
        "rebuild_badges",
        _admin(handle_rebuild_badges),
        schema=vol.Schema({}),
    )


def _async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister TaskMate services."""
    services = [
        SERVICE_COMPLETE_CHORE,
        SERVICE_COMPLETE_BONUS_SUBTASK,
        SERVICE_APPROVE_CHORE,
        SERVICE_REJECT_CHORE,
        SERVICE_UNDO_TRANSACTION,
        SERVICE_UNDO_CHORE_APPROVAL,
        SERVICE_TEST_NOTIFICATION,
        SERVICE_GIFT_POINTS,
        SERVICE_RECORD_ALLOWANCE_PAYOUT,
        SERVICE_REQUEST_SWAP,
        SERVICE_CHOOSE_AVATAR,
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
