"""WebSocket API for the TaskMate admin panel.

The panel speaks to the integration via these commands rather than via HA
services — services are intended for automation/templating consumers and
would clutter the service registry with two dozen panel-only entries.

Read:
    taskmate/get_state          — full snapshot

Children:
    taskmate/add_child          — name, avatar?, availability_entity?
    taskmate/update_child       — child_id + any of the above
    taskmate/remove_child       — child_id

Chores:
    taskmate/add_chore          — name + many optional fields
    taskmate/update_chore       — chore_id + any of the above
    taskmate/remove_chore       — chore_id

Rewards:
    taskmate/add_reward         — name + cost + many optional fields
    taskmate/update_reward      — reward_id + any of the above
    taskmate/remove_reward      — reward_id

Penalties / Bonuses (same shape):
    taskmate/add_penalty        — name + points + optional
    taskmate/update_penalty     — penalty_id + any of the above
    taskmate/remove_penalty     — penalty_id
    taskmate/apply_penalty      — penalty_id + child_id (operational, exposed for convenience)
    (and the bonus equivalents)

Task groups:
    taskmate/add_task_group     — name, policy, chore_ids?
    taskmate/update_task_group  — group_id + any of the above
    taskmate/remove_task_group  — group_id

Ordering:
    taskmate/set_chore_order        — child_id + chore_order (per-child)
    taskmate/set_global_chore_order — chore_order (admin panel display order)

Settings:
    taskmate/update_settings    — partial dict of {points_name, points_icon, history_days, streak_reset_mode, ...}

All commands require admin. Mutations write through coordinator methods so
TaskMate's existing business logic (refunds, cleanup, recompute) runs.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from functools import wraps
from typing import Any, Final

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DEFAULT_TIME_PERIODS, DOMAIN, MAX_TIME_PERIODS, TIME_CATEGORY_ICONS
from .coordinator import TaskMateCoordinator
from .models import BonusSubTask, Reward

_LOGGER = logging.getLogger(__name__)

WS_REGISTERED: Final = "ws_registered"

# --- command names ---------------------------------------------------------
WS_GET_STATE: Final           = "taskmate/get_state"

WS_ADD_CHILD: Final           = "taskmate/add_child"
WS_UPDATE_CHILD: Final        = "taskmate/update_child"
WS_REMOVE_CHILD: Final        = "taskmate/remove_child"
WS_LIST_HA_USERS: Final       = "taskmate/list_ha_users"

WS_ADD_CHORE: Final           = "taskmate/add_chore"
WS_UPDATE_CHORE: Final        = "taskmate/update_chore"
WS_REMOVE_CHORE: Final        = "taskmate/remove_chore"

WS_ADD_REWARD: Final          = "taskmate/add_reward"
WS_UPDATE_REWARD: Final       = "taskmate/update_reward"
WS_REMOVE_REWARD: Final       = "taskmate/remove_reward"

WS_ADD_PENALTY: Final         = "taskmate/add_penalty"
WS_UPDATE_PENALTY: Final      = "taskmate/update_penalty"
WS_REMOVE_PENALTY: Final      = "taskmate/remove_penalty"
WS_APPLY_PENALTY: Final       = "taskmate/apply_penalty"

WS_ADD_BONUS: Final           = "taskmate/add_bonus"
WS_UPDATE_BONUS: Final        = "taskmate/update_bonus"
WS_REMOVE_BONUS: Final        = "taskmate/remove_bonus"
WS_APPLY_BONUS: Final         = "taskmate/apply_bonus"

WS_ADD_TASK_GROUP: Final      = "taskmate/add_task_group"
WS_UPDATE_TASK_GROUP: Final   = "taskmate/update_task_group"
WS_REMOVE_TASK_GROUP: Final   = "taskmate/remove_task_group"

WS_UPDATE_SETTINGS: Final     = "taskmate/update_settings"

# Operational
WS_COMPLETE_BONUS_SUBTASK: Final = "taskmate/complete_bonus_subtask"
WS_APPROVE_CHORE: Final       = "taskmate/approve_chore"
WS_REJECT_CHORE: Final        = "taskmate/reject_chore"
WS_APPROVE_REWARD: Final      = "taskmate/approve_reward"
WS_REJECT_REWARD: Final       = "taskmate/reject_reward"
WS_SET_CHORE_ORDER: Final     = "taskmate/set_chore_order"
WS_SET_GLOBAL_CHORE_ORDER: Final = "taskmate/set_global_chore_order"
WS_ADD_CHORES_BULK: Final     = "taskmate/add_chores_bulk"
WS_PARENT_COMPLETE_CHORE: Final = "taskmate/parent_complete_chore"

# Templates
WS_TEMPLATES_LIST: Final       = "taskmate/templates/list"
WS_TEMPLATES_GET: Final        = "taskmate/templates/get"
WS_TEMPLATES_APPLY: Final      = "taskmate/templates/apply"
WS_TEMPLATES_SAVE_FROM: Final  = "taskmate/templates/save_from_chores"
WS_TEMPLATES_CREATE: Final     = "taskmate/templates/create"
WS_TEMPLATES_UPDATE: Final     = "taskmate/templates/update"
WS_TEMPLATES_DELETE: Final     = "taskmate/templates/delete"

# Notifications
WS_NOTIF_GET_STATE: Final          = "taskmate/notifications/get_state"
WS_NOTIF_SET_MASTER: Final         = "taskmate/notifications/set_master_enabled"
WS_NOTIF_SET_ROUTE: Final          = "taskmate/notifications/set_route"
WS_NOTIF_SET_CHILD_NOTIFY: Final   = "taskmate/notifications/set_child_notify"
WS_NOTIF_UPSERT_PARENT: Final      = "taskmate/notifications/upsert_parent"
WS_NOTIF_DELETE_PARENT: Final      = "taskmate/notifications/delete_parent"
WS_NOTIF_UPSERT_CUSTOM: Final      = "taskmate/notifications/upsert_custom"
WS_NOTIF_DELETE_CUSTOM: Final      = "taskmate/notifications/delete_custom"
WS_NOTIF_LIST_NOTIFY: Final        = "taskmate/notifications/list_notify_services"
WS_NOTIF_SET_STREAK_CUTOFF: Final  = "taskmate/notifications/set_streak_cutoff"
WS_NOTIF_SEND_TEST: Final          = "taskmate/notifications/send_test"

# Admin audit log
WS_AUDIT_LIST: Final  = "taskmate/audit/list"
WS_AUDIT_CLEAR: Final = "taskmate/audit/clear"

# Undo / retract
WS_UNDO_TRANSACTION: Final = "taskmate/undo_transaction"

# Clone / duplicate
WS_CLONE_CHORE: Final = "taskmate/clone_chore"

# Backup / restore
WS_CONFIG_EXPORT: Final = "taskmate/config/export"
WS_CONFIG_IMPORT: Final = "taskmate/config/import"

# Read-only / audit-management commands that should NOT themselves be audited.
# Everything else routed through @_admin_only mutates state and is logged.
_AUDIT_EXCLUDE: Final = {
    WS_GET_STATE, WS_NOTIF_GET_STATE, WS_NOTIF_LIST_NOTIFY,
    WS_TEMPLATES_LIST, WS_TEMPLATES_GET, WS_AUDIT_LIST, WS_AUDIT_CLEAR,
    WS_CONFIG_EXPORT,
}


def _audit_target(coordinator, msg: dict) -> str:
    """Best-effort human-readable target for an admin action from its payload."""
    name = msg.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    for key, getter in (
        ("chore_id", coordinator.get_chore),
        ("child_id", coordinator.get_child),
        ("reward_id", coordinator.get_reward),
    ):
        val = msg.get(key)
        if val:
            obj = getter(val)
            return getattr(obj, "name", None) or str(val)
    for key in (
        "penalty_id", "bonus_id", "badge_id", "group_id", "template_id",
        "completion_id", "claim_id", "parent_id", "custom_id",
        "awarded_badge_id", "type_id", "transaction_id",
    ):
        if msg.get(key):
            return str(msg[key])
    return ""


def _get_coordinator(hass: HomeAssistant) -> TaskMateCoordinator | None:
    for value in hass.data.get(DOMAIN, {}).values():
        if isinstance(value, TaskMateCoordinator):
            return value
    return None


def _admin_only(handler):
    """Enforce admin + coordinator availability + uniform error reporting."""
    @wraps(handler)
    async def wrapper(hass, connection, msg):
        if not connection.user.is_admin:
            connection.send_error(msg["id"], websocket_api.const.ERR_UNAUTHORIZED, "Admin only")
            return
        coordinator = _get_coordinator(hass)
        if not coordinator:
            connection.send_error(msg["id"], "no_coordinator", "TaskMate not initialised")
            return
        try:
            await handler(hass, connection, msg, coordinator)
        except vol.Invalid as err:
            connection.send_error(msg["id"], "invalid_args", str(err))
        except ValueError as err:
            connection.send_error(msg["id"], "invalid", str(err))
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("WS handler %s failed", msg.get("type"))
            connection.send_error(msg["id"], "handler_failed", str(err))
        else:
            # Record successful mutating commands in the admin audit log.
            mtype = msg.get("type", "")
            if mtype not in _AUDIT_EXCLUDE:
                try:
                    user = connection.user
                    await coordinator.async_record_audit(
                        getattr(user, "id", ""),
                        getattr(user, "name", "") or "",
                        mtype.split("taskmate/", 1)[-1],
                        _audit_target(coordinator, msg),
                    )
                except Exception:  # noqa: BLE001
                    _LOGGER.debug("audit record failed for %s", msg.get("type"), exc_info=True)
    return wrapper


# ---------------------------------------------------------------------------
# Validators / coercers
# ---------------------------------------------------------------------------

def _opt_str(v: Any) -> str:
    """Coerce optional string field to stripped str (or empty)."""
    if v is None:
        return ""
    return str(v).strip()


# ---------------------------------------------------------------------------
# State snapshot
# ---------------------------------------------------------------------------

def _build_state_snapshot(coordinator: TaskMateCoordinator) -> dict[str, Any]:
    data = coordinator.storage.data
    completions = list(data.get("completions", []))
    reward_claims = list(data.get("reward_claims", []))
    transactions = list(data.get("points_transactions", []))

    parent_completable = {}
    for chore_dict in data.get("chores", []):
        chore_id = chore_dict.get("id")
        if not chore_id or not chore_dict.get("enabled", True):
            continue
        if chore_dict.get("schedule_mode", "specific_days") == "one_shot":
            continue
        parent_completable[chore_id] = True

    return {
        "version": "2",
        "children":         list(data.get("children", [])),
        "chores":           list(data.get("chores", [])),
        "chore_display_order": list(data.get("chore_display_order", [])),
        "rewards":          list(data.get("rewards", [])),
        "penalties":        list(data.get("penalties", [])),
        "bonuses":          list(data.get("bonuses", [])),
        "task_groups":      list(data.get("task_groups", [])),
        "pool_allocations": list(data.get("pool_allocations", [])),
        "timed_sessions":   list(data.get("timed_sessions", [])),
        "templates":        coordinator.get_all_templates(),
        # Operational state — used by the panel's Activity tab + approval banner
        "completions":          completions,           # all (panel slices for display)
        "pending_completions":  [c for c in completions if not c.get("approved")],
        "reward_claims":        reward_claims,
        "pending_reward_claims": [c for c in reward_claims if not c.get("approved")],
        "points_transactions":  transactions[-100:],   # most recent 100 for audit log
        "badges":        list(data.get("badges", [])),
        "awarded_badges": list(data.get("awarded_badges", [])),
        "audit_log":     coordinator.storage.get_audit_log()[:100],  # newest 100 for the panel
        "settings": {
            "points_name":       data.get("points_name", "Stars"),
            "points_icon":       data.get("points_icon", "mdi:star"),
            # Difficulty multiplier defaults; overridden by stored values below.
            "difficulty_multiplier_easy":   0.5,
            "difficulty_multiplier_medium": 1.0,
            "difficulty_multiplier_hard":   2.0,
            **(data.get("settings", {}) or {}),
        },
        "parent_completable": parent_completable,
    }


@websocket_api.websocket_command({vol.Required("type"): WS_GET_STATE})
@websocket_api.async_response
@_admin_only
async def _ws_get_state(hass, connection, msg, coordinator):
    connection.send_result(msg["id"], _build_state_snapshot(coordinator))


# ---------------------------------------------------------------------------
# Children
# ---------------------------------------------------------------------------

@websocket_api.websocket_command({
    vol.Required("type"): WS_ADD_CHILD,
    vol.Required("name"): vol.All(str, vol.Length(min=1, max=120)),
    vol.Optional("avatar", default="mdi:account-circle"): str,
    vol.Optional("availability_entity", default=""): str,
    vol.Optional("availability_inverted", default=False): bool,
    vol.Optional("unavailability_entity", default=""): str,
    vol.Optional("linked_user_id", default=""): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_add_child(hass, connection, msg, coordinator):
    child = await coordinator.async_add_child(
        name=msg["name"].strip(),
        avatar=msg.get("avatar") or "mdi:account-circle",
        availability_entity=_opt_str(msg.get("availability_entity")),
        availability_inverted=bool(msg.get("availability_inverted", False)),
        unavailability_entity=_opt_str(msg.get("unavailability_entity")),
        linked_user_id=_opt_str(msg.get("linked_user_id")),
    )
    connection.send_result(msg["id"], {"id": child.id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_UPDATE_CHILD,
    vol.Required("child_id"): str,
    vol.Optional("name"): vol.All(str, vol.Length(min=1, max=120)),
    vol.Optional("avatar"): str,
    vol.Optional("availability_entity"): str,
    vol.Optional("availability_inverted"): bool,
    vol.Optional("unavailability_entity"): str,
    vol.Optional("linked_user_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_update_child(hass, connection, msg, coordinator):
    existing = coordinator.storage.get_child(msg["child_id"])
    if not existing:
        connection.send_error(msg["id"], "not_found", f"Child {msg['child_id']} not found")
        return
    if "name" in msg:
        existing.name = msg["name"].strip()
    if "avatar" in msg:
        existing.avatar = msg["avatar"] or "mdi:account-circle"
    if "availability_entity" in msg:
        existing.availability_entity = _opt_str(msg["availability_entity"])
    if "availability_inverted" in msg:
        existing.availability_inverted = bool(msg["availability_inverted"])
    if "unavailability_entity" in msg:
        existing.unavailability_entity = _opt_str(msg["unavailability_entity"])
    if "linked_user_id" in msg:
        existing.linked_user_id = _opt_str(msg["linked_user_id"])
    await coordinator.async_update_child(existing)
    connection.send_result(msg["id"], {"id": existing.id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_REMOVE_CHILD,
    vol.Required("child_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_remove_child(hass, connection, msg, coordinator):
    if not coordinator.storage.get_child(msg["child_id"]):
        connection.send_error(msg["id"], "not_found", f"Child {msg['child_id']} not found")
        return
    await coordinator.async_remove_child(msg["child_id"])
    connection.send_result(msg["id"], {"id": msg["child_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): WS_LIST_HA_USERS,
})
@websocket_api.async_response
@_admin_only
async def _ws_list_ha_users(hass, connection, msg, coordinator):
    """Return selectable HA users for linking a child to an account.

    Admin-only — it exposes account names. Excludes system-generated accounts
    (e.g. Supervisor, Home Assistant Content) and inactive users.
    """
    users = await hass.auth.async_get_users()
    result = [
        {"id": u.id, "name": u.name or "(unnamed user)", "is_admin": bool(u.is_admin)}
        for u in users
        if u.is_active and not u.system_generated
    ]
    result.sort(key=lambda x: x["name"].lower())
    connection.send_result(msg["id"], {"users": result})


# ---------------------------------------------------------------------------
# Chores
# ---------------------------------------------------------------------------

# Fields the panel is allowed to set directly. Anything else (skip_date,
# assignment_current_child_id, publish_calendar_published_dates, etc.) is
# coordinator-managed runtime state and intentionally not exposed.
_CHORE_EDITABLE_FIELDS = {
    "name", "description", "points", "assigned_to", "requires_approval",
    "time_category", "claim_allowance_minutes", "daily_limit", "completion_sound",
    "difficulty",
    "schedule_mode", "due_days", "recurrence", "recurrence_day",
    "recurrence_start", "first_occurrence_mode", "visibility_entity",
    "visibility_state", "visibility_operator", "enabled",
    "assignment_mode", "assignment_rotation_anchor", "require_availability",
    "publish_calendar_entities", "bonus_subtasks",
    "task_type", "timed_rate_points", "timed_rate_minutes", "timed_max_daily_minutes",
}


def _chore_payload_schema(*, require_name: bool):
    """Build a vol.Schema for add/update chore. require_name=True for add."""
    name_field = vol.Required("name") if require_name else vol.Optional("name")
    return {
        name_field: vol.All(str, vol.Length(min=1, max=200)),
        vol.Optional("description"): str,
        vol.Optional("points"): vol.All(int, vol.Range(min=0)),
        vol.Optional("assigned_to"): [str],
        vol.Optional("requires_approval"): bool,
        vol.Optional("time_category"): str,
        vol.Optional("claim_allowance_minutes"): vol.All(int, vol.Range(min=0)),
        vol.Optional("daily_limit"): vol.All(int, vol.Range(min=1)),
        vol.Optional("completion_sound"): str,
        vol.Optional("difficulty"): vol.In(["easy", "medium", "hard"]),
        vol.Optional("schedule_mode"): vol.In(["specific_days", "recurring", "one_shot"]),
        vol.Optional("due_days"): [str],
        vol.Optional("recurrence"): str,
        vol.Optional("recurrence_day"): str,
        vol.Optional("recurrence_start"): str,
        vol.Optional("first_occurrence_mode"): str,
        vol.Optional("visibility_entity"): str,
        vol.Optional("visibility_state"): str,
        vol.Optional("visibility_operator"): str,
        vol.Optional("enabled"): bool,
        vol.Optional("assignment_mode"): vol.In(["everyone", "alternating", "random", "balanced", "first_come", "unassigned"]),
        vol.Optional("assignment_rotation_anchor"): str,
        vol.Optional("require_availability"): bool,
        vol.Optional("publish_calendar_entities"): [str],
        vol.Optional("bonus_subtasks"): [{
            vol.Required("name"): vol.All(str, vol.Length(min=1, max=200)),
            vol.Optional("points"): vol.All(int, vol.Range(min=0)),
            vol.Optional("description"): str,
            vol.Optional("id"): str,
        }],
        vol.Optional("task_type"): vol.In(["standard", "timed"]),
        vol.Optional("timed_rate_points"): vol.All(int, vol.Range(min=1)),
        vol.Optional("timed_rate_minutes"): vol.All(int, vol.Range(min=1)),
        vol.Optional("timed_max_daily_minutes"): vol.All(int, vol.Range(min=0)),
    }


async def _maybe_apply_manual_start(coordinator, chore_id: str, child_id: str | None) -> None:
    """If a manual rotation start was supplied, apply it via the coordinator.

    The coordinator handles the "alternating reorders the pool / random+balanced
    is ephemeral" semantics; we just pass through. Silently ignored for
    'everyone' mode chores (the coordinator raises ValueError).
    """
    if not child_id:
        return
    try:
        await coordinator.async_set_chore_manual_start(chore_id, child_id)
    except ValueError as err:
        _LOGGER.debug("manual start ignored for %s: %s", chore_id, err)


@websocket_api.websocket_command({
    vol.Required("type"): WS_ADD_CHORE,
    vol.Optional("manual_start_child_id"): vol.Any(str, None),
    **_chore_payload_schema(require_name=True),
})
@websocket_api.async_response
@_admin_only
async def _ws_add_chore(hass, connection, msg, coordinator):
    chore = await coordinator.async_add_chore(
        name=msg["name"].strip(),
        points=msg.get("points", 10),
        description=msg.get("description", ""),
        assigned_to=list(msg.get("assigned_to", []) or []),
        requires_approval=msg.get("requires_approval", True),
        time_category=msg.get("time_category", "anytime"),
        claim_allowance_minutes=msg.get("claim_allowance_minutes", 0),
        daily_limit=msg.get("daily_limit", 1),
        completion_sound=msg.get("completion_sound", "coin"),
        schedule_mode=msg.get("schedule_mode", "specific_days"),
    )
    extra_fields = (set(msg.keys()) & _CHORE_EDITABLE_FIELDS) - {
        "name", "points", "description", "assigned_to", "requires_approval",
        "time_category", "claim_allowance_minutes", "daily_limit",
        "completion_sound", "schedule_mode",
    }
    if extra_fields:
        for f in extra_fields:
            if f == "bonus_subtasks":
                setattr(chore, f, [BonusSubTask.from_dict(b) for b in (msg[f] or [])])
            else:
                setattr(chore, f, msg[f] if not isinstance(msg[f], list) else list(msg[f]))
        await coordinator.async_update_chore(chore)
    await _maybe_apply_manual_start(coordinator, chore.id, msg.get("manual_start_child_id"))
    connection.send_result(msg["id"], {"id": chore.id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_UPDATE_CHORE,
    vol.Required("chore_id"): str,
    vol.Optional("manual_start_child_id"): vol.Any(str, None),
    **_chore_payload_schema(require_name=False),
})
@websocket_api.async_response
@_admin_only
async def _ws_update_chore(hass, connection, msg, coordinator):
    existing = coordinator.storage.get_chore(msg["chore_id"])
    if not existing:
        connection.send_error(msg["id"], "not_found", f"Chore {msg['chore_id']} not found")
        return
    for field in _CHORE_EDITABLE_FIELDS:
        if field in msg:
            value = msg[field]
            if field == "bonus_subtasks":
                value = [BonusSubTask.from_dict(b) for b in (value or [])]
            elif isinstance(value, list):
                value = list(value)
            elif field == "name":
                value = value.strip()
            setattr(existing, field, value)
    await coordinator.async_update_chore(existing)
    await _maybe_apply_manual_start(coordinator, existing.id, msg.get("manual_start_child_id"))
    connection.send_result(msg["id"], {"id": existing.id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_REMOVE_CHORE,
    vol.Required("chore_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_remove_chore(hass, connection, msg, coordinator):
    if not coordinator.storage.get_chore(msg["chore_id"]):
        connection.send_error(msg["id"], "not_found", f"Chore {msg['chore_id']} not found")
        return
    await coordinator.async_remove_chore(msg["chore_id"])
    connection.send_result(msg["id"], {"id": msg["chore_id"]})


# ---------------------------------------------------------------------------
# Rewards
# ---------------------------------------------------------------------------

_REWARD_FIELDS = {"name", "cost", "description", "icon", "assigned_to",
                  "is_jackpot", "pool_enabled", "quantity", "expires_at"}


def _reward_payload_schema(*, require_name: bool):
    name_field = vol.Required("name") if require_name else vol.Optional("name")
    cost_field = vol.Required("cost") if require_name else vol.Optional("cost")
    return {
        name_field: vol.All(str, vol.Length(min=1, max=200)),
        cost_field: vol.All(int, vol.Range(min=0)),
        vol.Optional("description"): str,
        vol.Optional("icon"): str,
        vol.Optional("assigned_to"): [str],
        vol.Optional("is_jackpot"): bool,
        vol.Optional("pool_enabled"): bool,
        vol.Optional("quantity"): vol.Any(None, vol.All(int, vol.Range(min=0))),
        vol.Optional("expires_at"): vol.Any(None, str),
    }


@websocket_api.websocket_command({
    vol.Required("type"): WS_ADD_REWARD,
    **_reward_payload_schema(require_name=True),
})
@websocket_api.async_response
@_admin_only
async def _ws_add_reward(hass, connection, msg, coordinator):
    # coordinator.async_add_reward accepts a subset; build a Reward dataclass
    # to populate every editable field uniformly.
    reward = Reward(
        name=msg["name"].strip(),
        cost=msg["cost"],
        description=msg.get("description", ""),
        icon=msg.get("icon", "mdi:gift"),
        assigned_to=list(msg.get("assigned_to", []) or []),
        is_jackpot=msg.get("is_jackpot", False),
        pool_enabled=msg.get("pool_enabled", False),
        quantity=msg.get("quantity"),
        expires_at=msg.get("expires_at") or None,
    )
    coordinator.storage.add_reward(reward)
    await coordinator.storage.async_save()
    await coordinator.async_refresh()
    connection.send_result(msg["id"], {"id": reward.id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_UPDATE_REWARD,
    vol.Required("reward_id"): str,
    **_reward_payload_schema(require_name=False),
})
@websocket_api.async_response
@_admin_only
async def _ws_update_reward(hass, connection, msg, coordinator):
    existing = coordinator.storage.get_reward(msg["reward_id"])
    if not existing:
        connection.send_error(msg["id"], "not_found", f"Reward {msg['reward_id']} not found")
        return
    for field in _REWARD_FIELDS:
        if field in msg:
            value = msg[field]
            if field == "name" and value:
                value = value.strip()
            if field == "expires_at":
                value = value or None
            if isinstance(value, list):
                value = list(value)
            setattr(existing, field, value)
    await coordinator.async_update_reward(existing)
    connection.send_result(msg["id"], {"id": existing.id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_REMOVE_REWARD,
    vol.Required("reward_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_remove_reward(hass, connection, msg, coordinator):
    if not coordinator.storage.get_reward(msg["reward_id"]):
        connection.send_error(msg["id"], "not_found", f"Reward {msg['reward_id']} not found")
        return
    await coordinator.async_remove_reward(msg["reward_id"])
    connection.send_result(msg["id"], {"id": msg["reward_id"]})


# ---------------------------------------------------------------------------
# Penalties
# ---------------------------------------------------------------------------

@websocket_api.websocket_command({
    vol.Required("type"): WS_ADD_PENALTY,
    vol.Required("name"): vol.All(str, vol.Length(min=1, max=200)),
    vol.Required("points"): vol.All(int, vol.Range(min=1)),
    vol.Optional("description", default=""): str,
    vol.Optional("icon", default="mdi:alert-circle-outline"): str,
    vol.Optional("assigned_to", default=[]): [str],
})
@websocket_api.async_response
@_admin_only
async def _ws_add_penalty(hass, connection, msg, coordinator):
    pen = await coordinator.async_add_penalty(
        name=msg["name"].strip(),
        points=msg["points"],
        description=msg.get("description", ""),
        icon=msg.get("icon", "mdi:alert-circle-outline"),
        assigned_to=list(msg.get("assigned_to", []) or []),
    )
    connection.send_result(msg["id"], {"id": pen.id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_UPDATE_PENALTY,
    vol.Required("penalty_id"): str,
    vol.Optional("name"): vol.All(str, vol.Length(min=1, max=200)),
    vol.Optional("points"): vol.All(int, vol.Range(min=1)),
    vol.Optional("description"): str,
    vol.Optional("icon"): str,
    vol.Optional("assigned_to"): [str],
})
@websocket_api.async_response
@_admin_only
async def _ws_update_penalty(hass, connection, msg, coordinator):
    existing = coordinator.storage.get_penalty(msg["penalty_id"])
    if not existing:
        connection.send_error(msg["id"], "not_found", f"Penalty {msg['penalty_id']} not found")
        return
    for k in ("name", "points", "description", "icon", "assigned_to"):
        if k in msg:
            val = msg[k]
            if k == "name" and val:
                val = val.strip()
            if k == "assigned_to":
                val = list(val)
            setattr(existing, k, val)
    await coordinator.async_update_penalty(existing)
    connection.send_result(msg["id"], {"id": existing.id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_REMOVE_PENALTY,
    vol.Required("penalty_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_remove_penalty(hass, connection, msg, coordinator):
    if not coordinator.storage.get_penalty(msg["penalty_id"]):
        connection.send_error(msg["id"], "not_found", f"Penalty {msg['penalty_id']} not found")
        return
    await coordinator.async_remove_penalty(msg["penalty_id"])
    connection.send_result(msg["id"], {"id": msg["penalty_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): WS_APPLY_PENALTY,
    vol.Required("penalty_id"): str,
    vol.Required("child_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_apply_penalty(hass, connection, msg, coordinator):
    await coordinator.async_apply_penalty(
        penalty_id=msg["penalty_id"], child_id=msg["child_id"]
    )
    connection.send_result(msg["id"], {"penalty_id": msg["penalty_id"], "child_id": msg["child_id"]})


# ---------------------------------------------------------------------------
# Bonuses (mirror of penalties)
# ---------------------------------------------------------------------------

@websocket_api.websocket_command({
    vol.Required("type"): WS_ADD_BONUS,
    vol.Required("name"): vol.All(str, vol.Length(min=1, max=200)),
    vol.Required("points"): vol.All(int, vol.Range(min=1)),
    vol.Optional("description", default=""): str,
    vol.Optional("icon", default="mdi:star-circle-outline"): str,
    vol.Optional("assigned_to", default=[]): [str],
})
@websocket_api.async_response
@_admin_only
async def _ws_add_bonus(hass, connection, msg, coordinator):
    b = await coordinator.async_add_bonus(
        name=msg["name"].strip(),
        points=msg["points"],
        description=msg.get("description", ""),
        icon=msg.get("icon", "mdi:star-circle-outline"),
        assigned_to=list(msg.get("assigned_to", []) or []),
    )
    connection.send_result(msg["id"], {"id": b.id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_UPDATE_BONUS,
    vol.Required("bonus_id"): str,
    vol.Optional("name"): vol.All(str, vol.Length(min=1, max=200)),
    vol.Optional("points"): vol.All(int, vol.Range(min=1)),
    vol.Optional("description"): str,
    vol.Optional("icon"): str,
    vol.Optional("assigned_to"): [str],
})
@websocket_api.async_response
@_admin_only
async def _ws_update_bonus(hass, connection, msg, coordinator):
    existing = coordinator.storage.get_bonus(msg["bonus_id"])
    if not existing:
        connection.send_error(msg["id"], "not_found", f"Bonus {msg['bonus_id']} not found")
        return
    for k in ("name", "points", "description", "icon", "assigned_to"):
        if k in msg:
            val = msg[k]
            if k == "name" and val:
                val = val.strip()
            if k == "assigned_to":
                val = list(val)
            setattr(existing, k, val)
    await coordinator.async_update_bonus(existing)
    connection.send_result(msg["id"], {"id": existing.id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_REMOVE_BONUS,
    vol.Required("bonus_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_remove_bonus(hass, connection, msg, coordinator):
    if not coordinator.storage.get_bonus(msg["bonus_id"]):
        connection.send_error(msg["id"], "not_found", f"Bonus {msg['bonus_id']} not found")
        return
    await coordinator.async_remove_bonus(msg["bonus_id"])
    connection.send_result(msg["id"], {"id": msg["bonus_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): WS_APPLY_BONUS,
    vol.Required("bonus_id"): str,
    vol.Required("child_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_apply_bonus(hass, connection, msg, coordinator):
    await coordinator.async_apply_bonus(bonus_id=msg["bonus_id"], child_id=msg["child_id"])
    connection.send_result(msg["id"], {"bonus_id": msg["bonus_id"], "child_id": msg["child_id"]})


# ---------------------------------------------------------------------------
# Task groups
# ---------------------------------------------------------------------------

@websocket_api.websocket_command({
    vol.Required("type"): WS_ADD_TASK_GROUP,
    vol.Required("name"): vol.All(str, vol.Length(min=1, max=200)),
    vol.Required("policy"): vol.In(["sticky", "spread"]),
    vol.Optional("chore_ids", default=[]): [str],
})
@websocket_api.async_response
@_admin_only
async def _ws_add_task_group(hass, connection, msg, coordinator):
    g = await coordinator.async_add_task_group(
        name=msg["name"].strip(),
        policy=msg["policy"],
        chore_ids=list(msg.get("chore_ids", []) or []),
    )
    connection.send_result(msg["id"], {"id": g.id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_UPDATE_TASK_GROUP,
    vol.Required("group_id"): str,
    vol.Optional("name"): vol.All(str, vol.Length(min=1, max=200)),
    vol.Optional("policy"): vol.In(["sticky", "spread"]),
    vol.Optional("chore_ids"): [str],
})
@websocket_api.async_response
@_admin_only
async def _ws_update_task_group(hass, connection, msg, coordinator):
    g = await coordinator.async_update_task_group(
        group_id=msg["group_id"],
        name=msg["name"].strip() if "name" in msg else None,
        policy=msg.get("policy"),
        chore_ids=list(msg["chore_ids"]) if "chore_ids" in msg else None,
    )
    connection.send_result(msg["id"], {"id": g.id if g else msg["group_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): WS_REMOVE_TASK_GROUP,
    vol.Required("group_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_remove_task_group(hass, connection, msg, coordinator):
    if not coordinator.storage.get_task_group(msg["group_id"]):
        connection.send_error(msg["id"], "not_found", f"Group {msg['group_id']} not found")
        return
    await coordinator.async_remove_task_group(msg["group_id"])
    connection.send_result(msg["id"], {"id": msg["group_id"]})


# ---------------------------------------------------------------------------
# Settings — partial update of currency + the "settings" subkey
# ---------------------------------------------------------------------------

# Top-level fields stored at storage._data root
_TOP_LEVEL_SETTINGS = {"points_name", "points_icon"}
# Settings stored under storage._data["settings"][key]
_SUBKEY_SETTINGS = {
    "history_days", "streak_reset_mode",
    "weekend_multiplier", "streak_milestones_enabled", "perfect_week_enabled",
    "perfect_week_bonus", "streak_milestones",
    "difficulty_multiplier_easy", "difficulty_multiplier_medium", "difficulty_multiplier_hard",
    "surprise_bonus_enabled", "surprise_bonus_chance", "surprise_bonus_min", "surprise_bonus_max",
    "notify_service", "calendar_projection_days", "skip_confirmation_enabled",
    "time_morning_start", "time_morning_end",
    "time_afternoon_start", "time_afternoon_end",
    "time_evening_start", "time_evening_end",
    "time_night_start", "time_night_end",
}


def _slugify_period_id(label: str, taken: set[str]) -> str:
    """Derive a stable, unique slug id from a period label."""
    base = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "period"
    if base == "anytime":
        base = "period"
    slug = base
    n = 2
    while slug in taken:
        slug = f"{base}_{n}"
        n += 1
    return slug


def _validate_time_periods(raw: list, coordinator) -> tuple[list[dict] | None, str | None]:
    """Normalize and validate a time_periods payload.

    Returns (periods, None) on success or (None, error_message) on failure.
    Enforces: HH:MM times, start < end, non-empty labels for custom periods,
    unique ids, non-overlapping when sorted by start, and block-on-delete for
    periods still referenced by chores.
    """
    if not isinstance(raw, list) or not raw:
        return None, "time_periods must be a non-empty list"
    if len(raw) > MAX_TIME_PERIODS:
        return None, f"too many periods (max {MAX_TIME_PERIODS})"

    builtin_ids = {p["id"] for p in DEFAULT_TIME_PERIODS}
    time_re = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
    periods: list[dict] = []
    ids: set[str] = {"anytime"}

    for entry in raw:
        if not isinstance(entry, dict):
            return None, "each period must be an object"
        label = str(entry.get("label") or "").strip()[:60]
        pid = str(entry.get("id") or "").strip()
        if pid and pid != "anytime" and pid in ids:
            return None, f"duplicate period id: {pid}"
        if not pid or pid == "anytime":
            pid = _slugify_period_id(label, ids)
        if not label and pid not in builtin_ids:
            return None, "every custom period needs a name"
        start = str(entry.get("start") or "")
        end = str(entry.get("end") or "")
        if not time_re.match(start) or not time_re.match(end):
            return None, f"invalid time for period '{label or pid}' (use HH:MM)"
        if start >= end:
            return None, f"period '{label or pid}' must start before it ends"
        ids.add(pid)
        periods.append({
            "id": pid,
            "label": label,
            "start": start,
            "end": end,
            "icon": str(entry.get("icon") or "").strip()[:120]
                    or TIME_CATEGORY_ICONS.get(pid, "mdi:clock-outline"),
        })

    periods.sort(key=lambda p: p["start"])
    for prev, cur in zip(periods, periods[1:]):
        if cur["start"] < prev["end"]:
            return None, (
                f"'{cur['label'] or cur['id']}' overlaps "
                f"'{prev['label'] or prev['id']}' — periods cannot overlap"
            )

    removed = {p["id"] for p in coordinator.get_time_periods()} - {p["id"] for p in periods}
    if removed:
        in_use = sorted({
            chore.name or chore.id
            for chore in coordinator.storage.get_chores()
            if chore.time_category in removed
        })
        if in_use:
            return None, (
                "cannot delete a period still used by chores: "
                + ", ".join(in_use[:10])
                + ("…" if len(in_use) > 10 else "")
            )

    return periods, None


MAX_VACATION_PERIODS: Final = 50


def _validate_vacation_periods(raw: list) -> tuple[list[dict] | None, str | None]:
    """Normalise and validate a vacation_periods payload.

    Returns (periods, None) on success or (None, error_message) on failure.
    An empty list is valid (clears all vacations). Each entry needs valid ISO
    start/end dates; start/end are swapped if reversed; ids are generated when
    missing. Returns periods sorted by start.
    """
    if not isinstance(raw, list):
        return None, "vacation_periods must be a list"
    if len(raw) > MAX_VACATION_PERIODS:
        return None, f"too many vacation periods (max {MAX_VACATION_PERIODS})"
    periods: list[dict] = []
    taken: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            return None, "each vacation period must be an object"
        try:
            start = date.fromisoformat(str(entry.get("start")))
            end = date.fromisoformat(str(entry.get("end")))
        except (TypeError, ValueError):
            return None, "each vacation period needs valid start and end dates (YYYY-MM-DD)"
        if end < start:
            start, end = end, start
        pid = str(entry.get("id") or "").strip()
        if not pid or pid in taken:
            pid = f"{start.isoformat()}_{len(periods)}"
        taken.add(pid)
        periods.append({
            "id": pid,
            "name": str(entry.get("name") or "").strip(),
            "start": start.isoformat(),
            "end": end.isoformat(),
        })
    return sorted(periods, key=lambda p: p["start"]), None

@websocket_api.websocket_command({
    vol.Required("type"): WS_UPDATE_SETTINGS,
    vol.Optional("points_name"): vol.All(str, vol.Length(min=1, max=120)),
    vol.Optional("points_icon"): str,
    vol.Optional("history_days"): vol.All(int, vol.Range(min=30, max=365)),
    vol.Optional("streak_reset_mode"): vol.In(["reset", "pause"]),
    vol.Optional("weekend_multiplier"): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=5.0)),
    vol.Optional("streak_milestones_enabled"): bool,
    vol.Optional("perfect_week_enabled"): bool,
    vol.Optional("perfect_week_bonus"): vol.All(int, vol.Range(min=0)),
    vol.Optional("difficulty_multiplier_easy"): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10.0)),
    vol.Optional("difficulty_multiplier_medium"): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10.0)),
    vol.Optional("difficulty_multiplier_hard"): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10.0)),
    vol.Optional("surprise_bonus_enabled"): bool,
    vol.Optional("surprise_bonus_chance"): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=100.0)),
    vol.Optional("surprise_bonus_min"): vol.All(int, vol.Range(min=0, max=10000)),
    vol.Optional("surprise_bonus_max"): vol.All(int, vol.Range(min=0, max=10000)),
    vol.Optional("skip_confirmation_enabled"): bool,
    vol.Optional("streak_milestones"): str,
    vol.Optional("notify_service"): str,
    vol.Optional("calendar_projection_days"): vol.All(int, vol.Range(min=1, max=90)),
    vol.Optional("time_morning_start"): vol.Match(r"^\d{2}:\d{2}$"),
    vol.Optional("time_morning_end"): vol.Match(r"^\d{2}:\d{2}$"),
    vol.Optional("time_afternoon_start"): vol.Match(r"^\d{2}:\d{2}$"),
    vol.Optional("time_afternoon_end"): vol.Match(r"^\d{2}:\d{2}$"),
    vol.Optional("time_evening_start"): vol.Match(r"^\d{2}:\d{2}$"),
    vol.Optional("time_evening_end"): vol.Match(r"^\d{2}:\d{2}$"),
    vol.Optional("time_night_start"): vol.Match(r"^\d{2}:\d{2}$"),
    vol.Optional("time_night_end"): vol.Match(r"^\d{2}:\d{2}$"),
    vol.Optional("time_periods"): list,
    vol.Optional("vacation_periods"): list,
})
@websocket_api.async_response
@_admin_only
async def _ws_update_settings(hass, connection, msg, coordinator):
    storage = coordinator.storage
    changed = []
    if "time_periods" in msg:
        periods, err = _validate_time_periods(msg["time_periods"], coordinator)
        if err:
            connection.send_error(msg["id"], "invalid_time_periods", err)
            return
        storage.set_setting("time_periods", periods)
        changed.append("time_periods")
    if "vacation_periods" in msg:
        vacations, verr = _validate_vacation_periods(msg["vacation_periods"])
        if verr:
            connection.send_error(msg["id"], "invalid_vacation_periods", verr)
            return
        storage.set_setting("vacation_periods", vacations)
        changed.append("vacation_periods")
    for k, v in msg.items():
        if k in {"id", "type", "time_periods", "vacation_periods"}:
            continue
        if k == "points_name":
            storage.set_points_name(v.strip())
            changed.append(k)
        elif k == "points_icon":
            storage.set_points_icon(v or "mdi:star")
            changed.append(k)
        elif k in _SUBKEY_SETTINGS:
            storage.set_setting(k, v)
            changed.append(k)
    if changed:
        await storage.async_save()
        await coordinator.async_refresh()
    connection.send_result(msg["id"], {"updated": changed})


# ---------------------------------------------------------------------------
# Operational — approval / rejection / reorder / bulk add
# ---------------------------------------------------------------------------

@websocket_api.websocket_command({
    vol.Required("type"): WS_COMPLETE_BONUS_SUBTASK,
    vol.Required("chore_id"): str,
    vol.Required("bonus_subtask_id"): str,
    vol.Required("child_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_complete_bonus_subtask(hass, connection, msg, coordinator):
    completion = await coordinator.async_complete_bonus_subtask(
        msg["chore_id"], msg["bonus_subtask_id"], msg["child_id"]
    )
    connection.send_result(msg["id"], {"id": completion.id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_APPROVE_CHORE,
    vol.Required("completion_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_approve_chore(hass, connection, msg, coordinator):
    await coordinator.async_approve_chore(msg["completion_id"])
    connection.send_result(msg["id"], {"completion_id": msg["completion_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): WS_REJECT_CHORE,
    vol.Required("completion_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_reject_chore(hass, connection, msg, coordinator):
    await coordinator.async_reject_chore(msg["completion_id"])
    connection.send_result(msg["id"], {"completion_id": msg["completion_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): WS_APPROVE_REWARD,
    vol.Required("claim_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_approve_reward(hass, connection, msg, coordinator):
    await coordinator.async_approve_reward(msg["claim_id"])
    connection.send_result(msg["id"], {"claim_id": msg["claim_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): WS_REJECT_REWARD,
    vol.Required("claim_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_reject_reward(hass, connection, msg, coordinator):
    await coordinator.async_reject_reward(msg["claim_id"])
    connection.send_result(msg["id"], {"claim_id": msg["claim_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): WS_PARENT_COMPLETE_CHORE,
    vol.Required("chore_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_parent_complete_chore(hass, connection, msg, coordinator):
    await coordinator.async_parent_complete_chore(msg["chore_id"])
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({
    vol.Required("type"): WS_SET_CHORE_ORDER,
    vol.Required("child_id"): str,
    vol.Required("chore_order"): [str],
})
@websocket_api.async_response
@_admin_only
async def _ws_set_chore_order(hass, connection, msg, coordinator):
    await coordinator.async_set_chore_order(msg["child_id"], list(msg["chore_order"]))
    connection.send_result(msg["id"], {"child_id": msg["child_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): WS_SET_GLOBAL_CHORE_ORDER,
    vol.Required("chore_order"): [str],
})
@websocket_api.async_response
@_admin_only
async def _ws_set_global_chore_order(hass, connection, msg, coordinator):
    await coordinator.async_set_global_chore_order(list(msg["chore_order"]))
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({
    vol.Required("type"): WS_ADD_CHORES_BULK,
    vol.Required("chore_names"): [str],
    vol.Optional("points"): vol.All(int, vol.Range(min=0)),
    vol.Optional("assigned_to"): [str],
    vol.Optional("requires_approval"): bool,
    vol.Optional("time_category"): str,
    vol.Optional("schedule_mode"): vol.In(["specific_days", "recurring", "one_shot"]),
    vol.Optional("due_days"): [str],
    vol.Optional("daily_limit"): vol.All(int, vol.Range(min=1)),
    vol.Optional("completion_sound"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_add_chores_bulk(hass, connection, msg, coordinator):
    chore_names = [n.strip() for n in msg.get("chore_names", []) if n and n.strip()]
    if not chore_names:
        connection.send_error(msg["id"], "no_names", "At least one chore name is required")
        return
    chores = await coordinator.async_add_chores_bulk(
        chore_names=chore_names,
        points=msg.get("points", 10),
        due_days=list(msg.get("due_days", []) or []),
        assigned_to=list(msg.get("assigned_to", []) or []),
        requires_approval=msg.get("requires_approval", True),
        time_category=msg.get("time_category", "anytime"),
        daily_limit=msg.get("daily_limit", 1),
        schedule_mode=msg.get("schedule_mode", "specific_days"),
        completion_sound=msg.get("completion_sound", "coin"),
    )
    connection.send_result(msg["id"], {"created": [c.id for c in chores], "count": len(chores)})


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@websocket_api.websocket_command({vol.Required("type"): WS_TEMPLATES_LIST})
@websocket_api.async_response
@_admin_only
async def _ws_templates_list(hass, connection, msg, coordinator):
    connection.send_result(msg["id"], {"templates": coordinator.get_all_templates()})


@websocket_api.websocket_command({
    vol.Required("type"): WS_TEMPLATES_GET,
    vol.Required("template_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_templates_get(hass, connection, msg, coordinator):
    tpl = coordinator.get_template(msg["template_id"])
    if tpl is None:
        connection.send_error(msg["id"], "not_found", f"Template {msg['template_id']} not found")
        return
    connection.send_result(msg["id"], tpl)


@websocket_api.websocket_command({
    vol.Required("type"): WS_TEMPLATES_APPLY,
    vol.Required("chores"): [{
        vol.Required("name"): vol.All(str, vol.Length(min=1, max=200)),
        vol.Optional("points"): vol.All(int, vol.Range(min=0)),
        vol.Optional("description"): str,
        vol.Optional("assigned_to"): [str],
        vol.Optional("requires_approval"): bool,
        vol.Optional("time_category"): str,
        vol.Optional("daily_limit"): vol.All(int, vol.Range(min=1)),
        vol.Optional("completion_sound"): str,
        vol.Optional("schedule_mode"): vol.In(["specific_days", "recurring", "one_shot"]),
        vol.Optional("due_days"): [str],
        vol.Optional("recurrence"): str,
        vol.Optional("recurrence_day"): str,
        vol.Optional("recurrence_start"): str,
        vol.Optional("first_occurrence_mode"): str,
        vol.Optional("assignment_mode"): vol.In(["everyone", "alternating", "random", "balanced", "first_come", "unassigned"]),
        vol.Optional("require_availability"): bool,
        vol.Optional("visibility_entity"): str,
        vol.Optional("visibility_state"): str,
        vol.Optional("visibility_operator"): str,
        vol.Optional("task_type"): vol.In(["standard", "timed"]),
        vol.Optional("timed_rate_points"): vol.All(int, vol.Range(min=1)),
        vol.Optional("timed_rate_minutes"): vol.All(int, vol.Range(min=1)),
        vol.Optional("timed_max_daily_minutes"): vol.All(int, vol.Range(min=0)),
    }],
})
@websocket_api.async_response
@_admin_only
async def _ws_templates_apply(hass, connection, msg, coordinator):
    created_ids = await coordinator.async_apply_template(list(msg["chores"]))
    connection.send_result(msg["id"], {"created_ids": created_ids})


@websocket_api.websocket_command({
    vol.Required("type"): WS_TEMPLATES_SAVE_FROM,
    vol.Required("chore_ids"): vol.All([str], vol.Length(min=1)),
    vol.Required("name"): vol.All(str, vol.Length(min=1, max=200)),
    vol.Optional("icon", default="mdi:clipboard-list"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_templates_save_from(hass, connection, msg, coordinator):
    tpl_id = await coordinator.async_save_template_from_chores(
        chore_ids=list(msg["chore_ids"]),
        name=msg["name"],
        icon=msg.get("icon", "mdi:clipboard-list"),
    )
    connection.send_result(msg["id"], {"template_id": tpl_id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_TEMPLATES_CREATE,
    vol.Required("name"): vol.All(str, vol.Length(min=1, max=200)),
    vol.Optional("icon", default="mdi:clipboard-list"): str,
    vol.Required("chores"): vol.All(list, vol.Length(min=1)),
})
@websocket_api.async_response
@_admin_only
async def _ws_templates_create(hass, connection, msg, coordinator):
    tpl_id = await coordinator.async_create_template(
        name=msg["name"],
        icon=msg.get("icon", "mdi:clipboard-list"),
        chores=list(msg["chores"]),
    )
    connection.send_result(msg["id"], {"template_id": tpl_id})


@websocket_api.websocket_command({
    vol.Required("type"): WS_TEMPLATES_UPDATE,
    vol.Required("template_id"): str,
    vol.Optional("name"): vol.All(str, vol.Length(min=1, max=200)),
    vol.Optional("icon"): str,
    vol.Optional("chores"): vol.All(list, vol.Length(min=1)),
})
@websocket_api.async_response
@_admin_only
async def _ws_templates_update(hass, connection, msg, coordinator):
    await coordinator.async_update_template(
        msg["template_id"],
        name=msg.get("name"),
        icon=msg.get("icon"),
        chores=msg.get("chores"),
    )
    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command({
    vol.Required("type"): WS_TEMPLATES_DELETE,
    vol.Required("template_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_templates_delete(hass, connection, msg, coordinator):
    await coordinator.async_delete_template(msg["template_id"])
    connection.send_result(msg["id"], {"success": True})


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@websocket_api.websocket_command({vol.Required("type"): WS_NOTIF_GET_STATE})
@websocket_api.async_response
@_admin_only
async def ws_notif_get_state(hass, connection, msg, coordinator):
    from .coord_notifications import NOTIFICATION_TYPES
    c = coordinator
    state = {
        "recipients": {
            "children": [
                {
                    "id": f"child:{ch.id}",
                    "name": ch.name,
                    "notify_service": ch.notify_service,
                }
                for ch in c.storage.get_children()
            ],
            "parents": [p.to_dict() for p in c.storage.get_parent_recipients()],
        },
        "types": [
            {
                "id": t.id,
                "audience": t.audience,
                "time_gated": t.time_gated,
                "per_recipient_time": t.per_recipient_time,
                "actionable": t.actionable,
                "default_enabled": t.default_enabled,
            }
            for t in NOTIFICATION_TYPES
        ],
        "config": {
            tid: cfg.to_dict()
            for tid, cfg in c.storage.get_all_notification_configs().items()
        },
        "custom": [n.to_dict() for n in c.storage.get_custom_notifications()],
        "settings": {
            "streak_at_risk_cutoff_time": c.storage.get_streak_at_risk_cutoff(),
        },
    }
    connection.send_result(msg["id"], state)


@websocket_api.websocket_command({
    vol.Required("type"): WS_NOTIF_SET_MASTER,
    vol.Required("type_id"): str,
    vol.Required("enabled"): bool,
})
@websocket_api.async_response
@_admin_only
async def ws_notif_set_master(hass, connection, msg, coordinator):
    await coordinator.notifications.set_master_enabled(msg["type_id"], msg["enabled"])
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({
    vol.Required("type"): WS_NOTIF_SET_ROUTE,
    vol.Required("type_id"): str,
    vol.Required("recipient_id"): str,
    vol.Required("enabled"): bool,
    vol.Optional("time"): vol.Any(str, None),
})
@websocket_api.async_response
@_admin_only
async def ws_notif_set_route(hass, connection, msg, coordinator):
    from .models import NotificationRoute
    route = NotificationRoute(enabled=msg["enabled"], time=msg.get("time"))
    await coordinator.notifications.set_route(msg["type_id"], msg["recipient_id"], route)
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({
    vol.Required("type"): WS_NOTIF_SET_CHILD_NOTIFY,
    vol.Required("child_id"): str,
    vol.Required("notify_service"): vol.Any(str, None),
})
@websocket_api.async_response
@_admin_only
async def ws_notif_set_child_notify(hass, connection, msg, coordinator):
    c = coordinator
    child = c.storage.get_child(msg["child_id"])
    if child is None:
        connection.send_error(msg["id"], "not_found", "Child not found")
        return
    child.notify_service = msg["notify_service"] or None
    c.storage.update_child(child)
    await c.storage.async_save()
    await c.notifications.async_setup_schedules()
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({
    vol.Required("type"): WS_NOTIF_UPSERT_PARENT,
    vol.Optional("parent_id"): str,
    vol.Required("name"): str,
    vol.Required("notify_service"): str,
    vol.Optional("enabled", default=True): bool,
})
@websocket_api.async_response
@_admin_only
async def ws_notif_upsert_parent(hass, connection, msg, coordinator):
    from .models import ParentRecipient
    c = coordinator
    p_id = msg.get("parent_id")
    if p_id:
        existing = next(
            (p for p in c.storage.get_parent_recipients() if p.id == p_id), None
        )
        if existing is None:
            connection.send_error(msg["id"], "not_found", "Parent not found")
            return
        existing.name = msg["name"]
        existing.notify_service = msg["notify_service"]
        existing.enabled = msg["enabled"]
        await c.notifications.upsert_parent(existing)
        connection.send_result(msg["id"], existing.to_dict())
    else:
        p = ParentRecipient(
            name=msg["name"],
            notify_service=msg["notify_service"],
            enabled=msg["enabled"],
        )
        await c.notifications.upsert_parent(p)
        connection.send_result(msg["id"], p.to_dict())


@websocket_api.websocket_command({
    vol.Required("type"): WS_NOTIF_DELETE_PARENT,
    vol.Required("parent_id"): str,
})
@websocket_api.async_response
@_admin_only
async def ws_notif_delete_parent(hass, connection, msg, coordinator):
    await coordinator.notifications.delete_parent(msg["parent_id"])
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({
    vol.Required("type"): WS_NOTIF_UPSERT_CUSTOM,
    vol.Optional("custom_id"): str,
    vol.Required("name"): str,
    vol.Required("message_template"): str,
    vol.Required("time"): str,
    vol.Optional("day_mask", default=0b1111111): int,
    vol.Optional("recipient_ids", default=list): list,
    vol.Optional("enabled", default=True): bool,
})
@websocket_api.async_response
@_admin_only
async def ws_notif_upsert_custom(hass, connection, msg, coordinator):
    from .models import CustomNotification
    c = coordinator
    n = CustomNotification.from_dict({
        "id": msg.get("custom_id"),
        "name": msg["name"],
        "message_template": msg["message_template"],
        "time": msg["time"],
        "day_mask": int(msg["day_mask"]),
        "recipient_ids": list(msg["recipient_ids"]),
        "enabled": bool(msg["enabled"]),
    })
    await c.notifications.upsert_custom(n)
    connection.send_result(msg["id"], n.to_dict())


@websocket_api.websocket_command({
    vol.Required("type"): WS_NOTIF_DELETE_CUSTOM,
    vol.Required("custom_id"): str,
})
@websocket_api.async_response
@_admin_only
async def ws_notif_delete_custom(hass, connection, msg, coordinator):
    await coordinator.notifications.delete_custom(msg["custom_id"])
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({vol.Required("type"): WS_NOTIF_LIST_NOTIFY})
@websocket_api.async_response
@_admin_only
async def ws_notif_list_notify(hass, connection, msg, coordinator):
    services = [
        f"notify.{name}"
        for name in hass.services.async_services().get("notify", {})
    ]
    services.sort()
    connection.send_result(msg["id"], services)


@websocket_api.websocket_command({
    vol.Required("type"): WS_NOTIF_SET_STREAK_CUTOFF,
    vol.Required("time"): str,
})
@websocket_api.async_response
@_admin_only
async def ws_notif_set_streak_cutoff(hass, connection, msg, coordinator):
    await coordinator.notifications.set_streak_cutoff(msg["time"])
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({
    vol.Required("type"): WS_NOTIF_SEND_TEST,
    vol.Required("type_id"): str,
})
@websocket_api.async_response
@_admin_only
async def ws_notif_send_test(hass, connection, msg, coordinator):
    sent = await coordinator.notifications.send_test(msg["type_id"])
    connection.send_result(msg["id"], {"sent": sent})


# ---------------------------------------------------------------------------
# Admin audit log
# ---------------------------------------------------------------------------

@websocket_api.websocket_command({vol.Required("type"): WS_AUDIT_LIST})
@websocket_api.async_response
@_admin_only
async def _ws_audit_list(hass, connection, msg, coordinator):
    connection.send_result(msg["id"], {"entries": coordinator.storage.get_audit_log()})


@websocket_api.websocket_command({vol.Required("type"): WS_AUDIT_CLEAR})
@websocket_api.async_response
@_admin_only
async def _ws_audit_clear(hass, connection, msg, coordinator):
    coordinator.storage.clear_audit_log()
    await coordinator.storage.async_save()
    connection.send_result(msg["id"], {"cleared": True})


@websocket_api.websocket_command({
    vol.Required("type"): WS_UNDO_TRANSACTION,
    vol.Required("transaction_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_undo_transaction(hass, connection, msg, coordinator):
    await coordinator.async_undo_transaction(msg["transaction_id"])
    connection.send_result(msg["id"], {"undone": msg["transaction_id"]})


@websocket_api.websocket_command({
    vol.Required("type"): WS_CLONE_CHORE,
    vol.Required("chore_id"): str,
})
@websocket_api.async_response
@_admin_only
async def _ws_clone_chore(hass, connection, msg, coordinator):
    clone = await coordinator.async_clone_chore(msg["chore_id"])
    connection.send_result(msg["id"], {"id": clone.id})


@websocket_api.websocket_command({vol.Required("type"): WS_CONFIG_EXPORT})
@websocket_api.async_response
@_admin_only
async def _ws_config_export(hass, connection, msg, coordinator):
    connection.send_result(msg["id"], coordinator.export_config())


@websocket_api.websocket_command({
    vol.Required("type"): WS_CONFIG_IMPORT,
    vol.Required("payload"): dict,
})
@websocket_api.async_response
@_admin_only
async def _ws_config_import(hass, connection, msg, coordinator):
    await coordinator.async_import_config(msg["payload"])
    connection.send_result(msg["id"], {"imported": True})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_COMMANDS = (
    _ws_get_state,
    _ws_audit_list, _ws_audit_clear, _ws_undo_transaction,
    _ws_add_child, _ws_update_child, _ws_remove_child, _ws_list_ha_users,
    _ws_add_chore, _ws_update_chore, _ws_remove_chore, _ws_clone_chore,
    _ws_config_export, _ws_config_import,
    _ws_add_reward, _ws_update_reward, _ws_remove_reward,
    _ws_add_penalty, _ws_update_penalty, _ws_remove_penalty, _ws_apply_penalty,
    _ws_add_bonus, _ws_update_bonus, _ws_remove_bonus, _ws_apply_bonus,
    _ws_add_task_group, _ws_update_task_group, _ws_remove_task_group,
    _ws_update_settings,
    _ws_complete_bonus_subtask,
    _ws_approve_chore, _ws_reject_chore, _ws_approve_reward, _ws_reject_reward,
    _ws_parent_complete_chore,
    _ws_set_chore_order, _ws_set_global_chore_order, _ws_add_chores_bulk,
    _ws_templates_list, _ws_templates_get, _ws_templates_apply,
    _ws_templates_save_from, _ws_templates_create, _ws_templates_update,
    _ws_templates_delete,
    ws_notif_get_state, ws_notif_set_master, ws_notif_set_route,
    ws_notif_set_child_notify,
    ws_notif_upsert_parent, ws_notif_delete_parent,
    ws_notif_upsert_custom, ws_notif_delete_custom,
    ws_notif_list_notify, ws_notif_set_streak_cutoff, ws_notif_send_test,
)


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register all TaskMate WebSocket commands. Idempotent."""
    if hass.data.get(DOMAIN, {}).get(WS_REGISTERED):
        _LOGGER.debug("TaskMate WS commands already registered, skipping")
        return
    for cmd in _COMMANDS:
        websocket_api.async_register_command(hass, cmd)
    hass.data.setdefault(DOMAIN, {})[WS_REGISTERED] = True
    _LOGGER.info("Registered %d TaskMate WebSocket commands", len(_COMMANDS))
