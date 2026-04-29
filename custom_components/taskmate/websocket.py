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

Settings:
    taskmate/update_settings    — partial dict of {points_name, points_icon, history_days, streak_reset_mode, ...}

All commands require admin. Mutations write through coordinator methods so
TaskMate's existing business logic (refunds, cleanup, recompute) runs.
"""
from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Final

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import TaskMateCoordinator
from .models import Reward

_LOGGER = logging.getLogger(__name__)

WS_REGISTERED: Final = "ws_registered"

# --- command names ---------------------------------------------------------
WS_GET_STATE: Final           = "taskmate/get_state"

WS_ADD_CHILD: Final           = "taskmate/add_child"
WS_UPDATE_CHILD: Final        = "taskmate/update_child"
WS_REMOVE_CHILD: Final        = "taskmate/remove_child"

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
WS_APPROVE_CHORE: Final       = "taskmate/approve_chore"
WS_REJECT_CHORE: Final        = "taskmate/reject_chore"
WS_APPROVE_REWARD: Final      = "taskmate/approve_reward"
WS_REJECT_REWARD: Final       = "taskmate/reject_reward"
WS_SET_CHORE_ORDER: Final     = "taskmate/set_chore_order"
WS_ADD_CHORES_BULK: Final     = "taskmate/add_chores_bulk"


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
    return wrapper


# ---------------------------------------------------------------------------
# Validators / coercers
# ---------------------------------------------------------------------------

_str_list = vol.All(vol.Any([str], None), lambda v: list(v or []))


def _opt_str(v: Any) -> str:
    """Coerce optional string field to stripped str (or empty)."""
    if v is None:
        return ""
    return str(v).strip()


def _opt_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    return int(v)


# ---------------------------------------------------------------------------
# State snapshot
# ---------------------------------------------------------------------------

def _build_state_snapshot(coordinator: TaskMateCoordinator) -> dict[str, Any]:
    data = coordinator.storage.data
    completions = list(data.get("completions", []))
    reward_claims = list(data.get("reward_claims", []))
    transactions = list(data.get("points_transactions", []))
    return {
        "version": "2",
        "children":         list(data.get("children", [])),
        "chores":           list(data.get("chores", [])),
        "rewards":          list(data.get("rewards", [])),
        "penalties":        list(data.get("penalties", [])),
        "bonuses":          list(data.get("bonuses", [])),
        "task_groups":      list(data.get("task_groups", [])),
        "pool_allocations": list(data.get("pool_allocations", [])),
        # Operational state — used by the panel's Activity tab + approval banner
        "completions":          completions,           # all (panel slices for display)
        "pending_completions":  [c for c in completions if not c.get("approved")],
        "reward_claims":        reward_claims,
        "pending_reward_claims": [c for c in reward_claims if not c.get("approved")],
        "points_transactions":  transactions[-100:],   # most recent 100 for audit log
        "settings": {
            "points_name":       data.get("points_name", "Stars"),
            "points_icon":       data.get("points_icon", "mdi:star"),
            **(data.get("settings", {}) or {}),
        },
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


# ---------------------------------------------------------------------------
# Chores
# ---------------------------------------------------------------------------

# Fields the panel is allowed to set directly. Anything else (skip_date,
# assignment_current_child_id, publish_calendar_published_dates, etc.) is
# coordinator-managed runtime state and intentionally not exposed.
_CHORE_EDITABLE_FIELDS = {
    "name", "description", "points", "assigned_to", "requires_approval",
    "time_category", "claim_allowance_minutes", "daily_limit", "completion_sound",
    "schedule_mode", "due_days", "recurrence", "recurrence_day",
    "recurrence_start", "first_occurrence_mode", "visibility_entity",
    "visibility_state", "visibility_operator", "enabled",
    "assignment_mode", "assignment_rotation_anchor", "require_availability",
    "publish_calendar_entities",
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
        vol.Optional("assignment_mode"): vol.In(["everyone", "alternating", "random", "balanced"]),
        vol.Optional("assignment_rotation_anchor"): str,
        vol.Optional("require_availability"): bool,
        vol.Optional("publish_calendar_entities"): [str],
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
            if isinstance(value, list):
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
    "notify_service", "calendar_projection_days",
}

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
    vol.Optional("streak_milestones"): str,
    vol.Optional("notify_service"): str,
    vol.Optional("calendar_projection_days"): vol.All(int, vol.Range(min=1, max=90)),
})
@websocket_api.async_response
@_admin_only
async def _ws_update_settings(hass, connection, msg, coordinator):
    storage = coordinator.storage
    changed = []
    for k, v in msg.items():
        if k in {"id", "type"}:
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
# Registration
# ---------------------------------------------------------------------------

_COMMANDS = (
    _ws_get_state,
    _ws_add_child, _ws_update_child, _ws_remove_child,
    _ws_add_chore, _ws_update_chore, _ws_remove_chore,
    _ws_add_reward, _ws_update_reward, _ws_remove_reward,
    _ws_add_penalty, _ws_update_penalty, _ws_remove_penalty, _ws_apply_penalty,
    _ws_add_bonus, _ws_update_bonus, _ws_remove_bonus, _ws_apply_bonus,
    _ws_add_task_group, _ws_update_task_group, _ws_remove_task_group,
    _ws_update_settings,
    _ws_approve_chore, _ws_reject_chore, _ws_approve_reward, _ws_reject_reward,
    _ws_set_chore_order, _ws_add_chores_bulk,
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
