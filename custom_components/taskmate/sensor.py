"""Sensor platform for TaskMate integration."""
from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util


import logging

from . import photos
from .const import DOMAIN
from .coordinator import TaskMateCoordinator
from .models import Child

_LOGGER = logging.getLogger(__name__)


def _safe_float(value, default: float) -> float:
    """Convert value to float, returning default on failure."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def _safe_int(value, default: int) -> int:
    """Convert value to int, returning default on failure."""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Shared attribute builders
#
# The overview sensor used to pack every data slice into one 16KB+ attribute
# payload, which Home Assistant's recorder refuses to store. The data is now
# split across five sensors (overview / chores / rewards / activity /
# incentives); the helpers below build each slice once per coordinator update
# and share intermediate lookups so all sensors stay cheap to render.
# ---------------------------------------------------------------------------


_COMMON_CACHE_ATTR = "_taskmate_sensor_common_cache"


def _compute_common(coordinator: TaskMateCoordinator) -> dict:
    """Build the per-update context shared by all TaskMate sensors.

    Cached on the coordinator so each sensor re-uses a single pass over
    completions / transactions / pool allocations.
    """
    data = coordinator.data
    data_id = id(data)
    cached = getattr(coordinator, _COMMON_CACHE_ATTR, None)
    if cached and cached.get("data_id") == data_id:
        return cached["common"]

    children = data.get("children", [])
    chores = data.get("chores", [])
    rewards = data.get("rewards", [])
    all_completions = data.get("completions", [])
    pending_completions = data.get("pending_completions", [])
    pending_reward_claim_objs = data.get("pending_reward_claims", [])
    pool_alloc_objs = data.get("pool_allocations", [])

    child_lookup = {c.id: c for c in children}
    chore_lookup = {c.id: c for c in chores}
    reward_lookup = {r.id: r for r in rewards}

    # Pending chore points per child (awaiting approval -> points to be earned).
    pending_points_by_child: dict[str, int] = {}
    for comp in pending_completions:
        chore = chore_lookup.get(comp.chore_id)
        if chore:
            pending_points_by_child[comp.child_id] = (
                pending_points_by_child.get(comp.child_id, 0) + chore.points
            )

    # Committed points per child (reward claims awaiting approval = points reserved).
    # Pool-mode pending claims are skipped because their cost was already deducted
    # from child.points at allocation time.
    committed_points_by_child: dict[str, int] = {}
    for rc in pending_reward_claim_objs:
        if coordinator.is_pool_mode_claim(rc):
            continue
        reward = reward_lookup.get(rc.reward_id)
        if reward:
            committed_points_by_child[rc.child_id] = (
                committed_points_by_child.get(rc.child_id, 0) + reward.cost
            )

    # Pool allocation lookups for v3.0 pool mode.
    pool_by_child_reward: dict[str, dict[str, int]] = {}
    pool_total_by_reward: dict[str, int] = {}
    total_allocated_by_child: dict[str, int] = {}
    for pa in pool_alloc_objs:
        pool_by_child_reward.setdefault(pa.child_id, {})[pa.reward_id] = pa.allocated_points
        pool_total_by_reward[pa.reward_id] = (
            pool_total_by_reward.get(pa.reward_id, 0) + pa.allocated_points
        )
        total_allocated_by_child[pa.child_id] = (
            total_allocated_by_child.get(pa.child_id, 0) + pa.allocated_points
        )

    common = {
        "data_id": data_id,
        "hass": coordinator.hass,
        "data": data,
        "children": children,
        "chores": chores,
        "rewards": rewards,
        "child_lookup": child_lookup,
        "chore_lookup": chore_lookup,
        "reward_lookup": reward_lookup,
        "all_completions": all_completions,
        "pending_completions": pending_completions,
        "pending_reward_claim_objs": pending_reward_claim_objs,
        "pool_alloc_objs": pool_alloc_objs,
        "pending_points_by_child": pending_points_by_child,
        "committed_points_by_child": committed_points_by_child,
        "pool_by_child_reward": pool_by_child_reward,
        "pool_total_by_reward": pool_total_by_reward,
        "total_allocated_by_child": total_allocated_by_child,
    }
    setattr(coordinator, _COMMON_CACHE_ATTR, {"data_id": data_id, "common": common})
    return common


def _build_children_summary(coordinator: TaskMateCoordinator, common: dict) -> list[dict]:
    """Build compact per-child summary used on the overview sensor."""
    children = common["children"]
    pending = common["pending_points_by_child"]
    committed = common["committed_points_by_child"]
    allocated = common["total_allocated_by_child"]
    summary = []
    for c in children:
        committed_amount = committed.get(c.id, 0)
        lvl = coordinator.level_info(c)
        summary.append({
            "level": lvl["level"],
            "level_progress": lvl["progress"],
            "level_target": lvl["target"],
            "id": c.id,
            "name": c.name,
            "points": c.points,
            "pending_points": pending.get(c.id, 0),
            "committed_points": committed_amount,
            "allocated_points": allocated.get(c.id, 0),
            # Allocations were deducted from child.points already, so spendable
            # only needs to account for pending-claim commitments.
            "spendable_balance": max(0, c.points - committed_amount),
            "chore_order": c.chore_order,
            "current_streak": getattr(c, 'current_streak', 0) or 0,
            "best_streak": getattr(c, 'best_streak', 0) or 0,
            "total_points_earned": getattr(c, 'total_points_earned', 0) or 0,
            "total_chores_completed": getattr(c, 'total_chores_completed', 0) or 0,
            "avatar": getattr(c, 'avatar', 'mdi:account-circle') or 'mdi:account-circle',
            "last_completion_date": getattr(c, 'last_completion_date', None),
            "streak_paused": getattr(c, 'streak_paused', False),
            "on_vacation": coordinator._is_child_on_vacation(c),
            "streak_milestones_achieved": getattr(c, 'streak_milestones_achieved', None) or [],
            "awarded_perfect_weeks": getattr(c, 'awarded_perfect_weeks', None) or [],
            "career_score": getattr(c, 'career_score', 0) or 0,
            "total_penalties_received": getattr(c, 'total_penalties_received', 0) or 0,
            "quests": coordinator.quest_progress_for_child(c.id),
            "avatar_options": coordinator.avatar_options_for_child(c),
            "challenges": coordinator.challenge_progress_for_child(c.id),
        })
    return summary


def _build_chores_list(coordinator: TaskMateCoordinator, common: dict) -> list[dict]:
    """Build the chores list, omitting rarely-used / empty fields.

    Fields dropped entirely (no frontend consumer):
      - publish_calendar_entities, last_completed_at,
        first_occurrence_mode, assignment_rotation_anchor.
    Optional fields are only emitted when they hold a non-default value so
    small / simple chores produce compact records and the slice stays under
    the 16KB recorder limit.
    Per-child availability is split into its own attribute (`chore_availability`)
    on the chore-availability sensor to keep this record compact.
    """
    chores = common["chores"]
    chores_list = []
    for c in chores:
        assigned_to = c.assigned_to if isinstance(c.assigned_to, list) else []
        record: dict = {
            "id": c.id,
            "name": c.name,
            "points": c.points,
            "time_category": c.time_category,
            "assigned_to": assigned_to,
            "schedule_mode": getattr(c, 'schedule_mode', 'specific_days'),
            "enabled": getattr(c, 'enabled', True),
            "assignment_mode": getattr(c, 'assignment_mode', 'everyone'),
        }
        # Difficulty tier + the points it actually awards. Emitted only when
        # non-default (medium / ×1.0) so simple chores stay compact.
        difficulty = getattr(c, 'difficulty', 'medium') or 'medium'
        if difficulty != 'medium':
            record["difficulty"] = difficulty
        effective_points = coordinator.effective_chore_points(c)
        if effective_points != c.points:
            record["effective_points"] = effective_points
        # Optional fields — emit only when non-default to save bytes.
        description = getattr(c, 'description', '') or ''
        if description:
            record["description"] = description
        daily_limit = getattr(c, 'daily_limit', 1)
        if daily_limit != 1:
            record["daily_limit"] = daily_limit
        claim_allowance_minutes = getattr(c, 'claim_allowance_minutes', 0) or 0
        if claim_allowance_minutes:
            record["claim_allowance_minutes"] = claim_allowance_minutes
        due_days = getattr(c, 'due_days', []) or []
        if due_days:
            record["due_days"] = due_days
        requires_approval = getattr(c, 'requires_approval', True)
        if not requires_approval:
            record["requires_approval"] = False
        # Mandatory chores (#532): emit only when set so the child card can
        # show the mandatory styling/badge. penalty rides along when non-zero.
        if getattr(c, 'mandatory', False):
            record["mandatory"] = True
            penalty = getattr(c, 'mandatory_penalty_points', 0) or 0
            if penalty:
                record["mandatory_penalty_points"] = penalty
        if getattr(c, 'require_photo', False):
            record["require_photo"] = True
        recurrence = getattr(c, 'recurrence', 'weekly')
        if recurrence != 'weekly':
            record["recurrence"] = recurrence
        recurrence_day = getattr(c, 'recurrence_day', '')
        if recurrence_day:
            record["recurrence_day"] = recurrence_day
        recurrence_start = getattr(c, 'recurrence_start', '')
        if recurrence_start:
            record["recurrence_start"] = recurrence_start
        visibility_entity = getattr(c, 'visibility_entity', '')
        if visibility_entity:
            record["visibility_entity"] = visibility_entity
            record["visibility_operator"] = getattr(c, 'visibility_operator', 'equals')
            record["visibility_state"] = getattr(c, 'visibility_state', 'on')
        disabled_for = getattr(c, 'disabled_for', [])
        if disabled_for:
            record["disabled_for"] = disabled_for
        created_date = getattr(c, 'created_date', '')
        if created_date:
            record["created_date"] = created_date
        assignment_current_child_id = getattr(c, 'assignment_current_child_id', '')
        if assignment_current_child_id:
            record["assignment_current_child_id"] = assignment_current_child_id
        completion_sound = getattr(c, 'completion_sound', 'coin')
        if completion_sound and completion_sound != 'coin':
            record["completion_sound"] = completion_sound
        task_type = getattr(c, 'task_type', 'standard')
        if task_type == "timed":
            record["task_type"] = "timed"
            record["timed_rate_points"] = getattr(c, 'timed_rate_points', 10)
            record["timed_rate_minutes"] = getattr(c, 'timed_rate_minutes', 5)
            record["timed_max_daily_minutes"] = getattr(c, 'timed_max_daily_minutes', 0)
        bonus_subtasks = getattr(c, 'bonus_subtasks', [])
        if bonus_subtasks:
            record["bonus_subtasks"] = [
                {"id": b.id, "name": b.name, "points": b.points}
                for b in bonus_subtasks
            ]
        chores_list.append(record)
    return chores_list


def _build_chore_availability(coordinator: TaskMateCoordinator, common: dict) -> dict:
    """Build the chore availability matrix: {chore_id: {child_id: bool}}.

    Extracted from the chores sensor so `sensor.taskmate_chores` carries only
    definitions and stays compact even for families with many chores/kids.
    """
    children = common["children"]
    chores = common["chores"]
    availability: dict[str, dict[str, bool]] = {}
    for c in chores:
        per_child = {}
        for child in children:
            per_child[child.id] = coordinator.is_chore_available_for_child(c, child.id)
        availability[c.id] = per_child
    return availability


def _build_todays_completions(common: dict) -> list[dict]:
    """Build today's completions (both approved and pending)."""
    now = dt_util.now()
    today = now.date()
    child_lookup = common["child_lookup"]
    chore_lookup = common["chore_lookup"]
    out = []
    for comp in common["all_completions"]:
        comp_dt = comp.completed_at
        if hasattr(comp_dt, 'astimezone'):
            comp_dt = dt_util.as_local(comp_dt)
        comp_date = comp_dt.date() if hasattr(comp_dt, 'date') else comp_dt
        if comp_date != today:
            continue
        matched_chore = chore_lookup.get(comp.chore_id)
        bonus_subtask_id = getattr(comp, "bonus_subtask_id", "") or ""
        if bonus_subtask_id and matched_chore:
            subtask = next((b for b in matched_chore.bonus_subtasks if b.id == bonus_subtask_id), None)
            display_name = f"{matched_chore.name} › {subtask.name}" if subtask else matched_chore.name
            display_points = subtask.points if subtask else 0
        else:
            display_name = matched_chore.name if matched_chore else ""
            display_points = matched_chore.points if matched_chore else 0
        timed_secs = getattr(comp, "timed_duration_seconds", 0) or 0
        if timed_secs > 0 and matched_chore and getattr(matched_chore, "task_type", "") == "timed":
            rate_seconds = matched_chore.timed_rate_minutes * 60
            if rate_seconds > 0:
                display_points = (timed_secs // rate_seconds) * matched_chore.timed_rate_points
        rec = {
            "completion_id": comp.id,
            "chore_id": comp.chore_id,
            "child_id": comp.child_id,
            "child_name": "Parent" if comp.child_id == "__parent__" else (child_lookup[comp.child_id].name if comp.child_id in child_lookup else ""),
            "chore_name": display_name,
            "points": display_points,
            "approved": comp.approved,
            "completed_at": comp.completed_at.isoformat() if hasattr(comp.completed_at, 'isoformat') else str(comp.completed_at),
            "bonus_subtask_id": bonus_subtask_id,
        }
        if timed_secs > 0:
            rec["timed_duration_seconds"] = timed_secs
        # Sign the evidence photo so a card's <img> (which carries no bearer
        # token) can load it from the auth-gated serve view.
        photo = getattr(comp, "photo_url", "") or ""
        if photo:
            rec["photo_url"] = photos.sign_photo_url(common["hass"], photo)
        out.append(rec)
    return out


def _build_active_timed_sessions(coordinator: TaskMateCoordinator) -> list[dict]:
    """Build active timed sessions for frontend consumption."""
    sessions = coordinator.data.get("timed_sessions", [])
    out = []
    for s in sessions:
        if hasattr(s, 'state'):
            state = s.state
            if state not in ("running", "paused"):
                continue
            segments = s.segments or []
            current_segment_start = ""
            if state == "running" and segments:
                last_seg = segments[-1]
                if isinstance(last_seg, dict) and last_seg.get("end") is None:
                    current_segment_start = last_seg.get("start", "")
            out.append({
                "chore_id": s.chore_id,
                "child_id": s.child_id,
                "state": state,
                "total_seconds_today": s.total_seconds_today,
                "current_segment_start": current_segment_start,
            })
        else:
            state = s.get("state", "stopped") if isinstance(s, dict) else "stopped"
            if state not in ("running", "paused"):
                continue
            segments = s.get("segments", []) if isinstance(s, dict) else []
            current_segment_start = ""
            if state == "running" and segments:
                last_seg = segments[-1]
                if isinstance(last_seg, dict) and last_seg.get("end") is None:
                    current_segment_start = last_seg.get("start", "")
            out.append({
                "chore_id": s.get("chore_id", "") if isinstance(s, dict) else "",
                "child_id": s.get("child_id", "") if isinstance(s, dict) else "",
                "state": state,
                "total_seconds_today": s.get("total_seconds_today", 0) if isinstance(s, dict) else 0,
                "current_segment_start": current_segment_start,
            })
    return out


def _build_rewards_list(common: dict) -> list[dict]:
    """Build the rewards list with calculated_costs and pool allocations."""
    rewards = common["rewards"]
    children = common["children"]
    pool_by_child_reward = common["pool_by_child_reward"]
    pool_total_by_reward = common["pool_total_by_reward"]
    today = dt_util.now().date()
    out = []
    for r in rewards:
        assigned = (
            r.assigned_to
            if isinstance(r.assigned_to, list) and r.assigned_to
            else [c.id for c in children]
        )
        calculated_costs = {child_id: r.cost for child_id in assigned}
        reward_pool_allocations = {
            cid: pool_by_child_reward.get(cid, {}).get(r.id, 0) for cid in assigned
        }
        jackpot_pool_total = (
            pool_total_by_reward.get(r.id, 0) if getattr(r, 'is_jackpot', False) else None
        )
        quantity = getattr(r, 'quantity', None)
        expires_at = getattr(r, 'expires_at', None)
        is_sold_out = quantity is not None and quantity <= 0
        is_expired = False
        days_until_expiry: int | None = None
        if expires_at:
            try:
                deadline = date.fromisoformat(expires_at)
                is_expired = deadline <= today
                days_until_expiry = (deadline - today).days
            except (TypeError, ValueError):
                pass
        out.append({
            "id": r.id,
            "name": r.name,
            "cost": r.cost,
            "description": getattr(r, 'description', ''),
            "icon": r.icon,
            "assigned_to": r.assigned_to if isinstance(r.assigned_to, list) else [],
            "is_jackpot": getattr(r, 'is_jackpot', False),
            "pool_enabled": getattr(r, 'pool_enabled', False),
            "calculated_costs": calculated_costs,
            "pool_allocations": reward_pool_allocations,
            "jackpot_pool_total": jackpot_pool_total,
            "quantity": quantity,
            "expires_at": expires_at,
            "is_sold_out": is_sold_out,
            "is_expired": is_expired,
            "is_available": not (is_sold_out or is_expired),
            "days_until_expiry": days_until_expiry,
        })
    return out


def _build_pending_reward_claims(common: dict) -> list[dict]:
    """Build enriched pending reward claims list."""
    reward_lookup = common["reward_lookup"]
    child_lookup = common["child_lookup"]
    out = []
    for rc in common["pending_reward_claim_objs"]:
        reward = reward_lookup.get(rc.reward_id)
        child = child_lookup.get(rc.child_id)
        if not reward or not child:
            continue
        out.append({
            "claim_id": rc.id,
            "reward_id": rc.reward_id,
            "child_id": rc.child_id,
            "child_name": child.name,
            "child_avatar": getattr(child, 'avatar', 'mdi:account-circle') or 'mdi:account-circle',
            "reward_name": reward.name,
            "reward_icon": reward.icon or 'mdi:gift',
            "cost": reward.cost,
            "claimed_at": rc.claimed_at.isoformat() if hasattr(rc.claimed_at, 'isoformat') else str(rc.claimed_at),
        })
    return out


def _build_recent_completions(common: dict, limit: int = 35) -> list[dict]:
    """Return the most recent completions, capped to `limit`.

    Lowered from 200 to 35 so the activity sensor's attribute payload stays
    under the 16KB recorder limit even for families with heavy chore activity.
    """
    child_lookup = common["child_lookup"]
    chore_lookup = common["chore_lookup"]
    recent = sorted(common["all_completions"], key=lambda c: c.completed_at, reverse=True)[:limit]
    out = []
    for comp in recent:
        matched_chore = chore_lookup.get(comp.chore_id)
        display_points = matched_chore.points if matched_chore else 0
        timed_secs = getattr(comp, "timed_duration_seconds", 0) or 0
        if timed_secs > 0 and matched_chore and getattr(matched_chore, "task_type", "") == "timed":
            rate_seconds = matched_chore.timed_rate_minutes * 60
            if rate_seconds > 0:
                display_points = (timed_secs // rate_seconds) * matched_chore.timed_rate_points
        out.append({
            "completion_id": comp.id,
            "chore_id": comp.chore_id,
            "child_id": comp.child_id,
            "child_name": "Parent" if comp.child_id == "__parent__" else (child_lookup[comp.child_id].name if comp.child_id in child_lookup else ""),
            "chore_name": matched_chore.name if matched_chore else "",
            "points": display_points,
            "approved": comp.approved,
            "completed_at": comp.completed_at.isoformat() if hasattr(comp.completed_at, 'isoformat') else str(comp.completed_at),
        })
    return out


def _build_recent_transactions(common: dict, limit: int = 20) -> list[dict]:
    """Unified activity feed of manual point adjustments and reward claims.

    Capped at 20 so the combined activity slice (completions + transactions)
    stays under the 16KB recorder limit.
    """
    data = common["data"]
    child_lookup = common["child_lookup"]
    reward_lookup = common["reward_lookup"]
    points_transactions = data.get("points_transactions", [])
    all_reward_claims = data.get("reward_claims", [])
    events = []

    for t in points_transactions:
        child = child_lookup.get(t.child_id)
        if not child:
            continue
        events.append({
            "transaction_id": t.id,
            "type": "points_added" if t.points > 0 else "points_removed",
            "child_id": t.child_id,
            "child_name": child.name,
            "points": t.points,
            "reason": t.reason or "",
            "created_at": t.created_at.isoformat() if hasattr(t.created_at, 'isoformat') else str(t.created_at),
        })

    for rc in all_reward_claims:
        child = child_lookup.get(rc.child_id)
        reward = reward_lookup.get(rc.reward_id)
        if not child or not reward:
            continue
        event_type = "reward_approved" if rc.approved else "reward_claimed"
        timestamp = rc.approved_at if rc.approved and rc.approved_at else rc.claimed_at
        events.append({
            "transaction_id": rc.id,
            "type": event_type,
            "child_id": rc.child_id,
            "child_name": child.name,
            "reward_id": rc.reward_id,
            "reward_name": reward.name,
            "reward_icon": reward.icon or "mdi:gift",
            "points": -reward.cost,
            "approved": rc.approved,
            "created_at": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
        })

    events.sort(key=lambda e: e["created_at"], reverse=True)
    return events[:limit]


def _build_penalties_list(common: dict) -> list[dict]:
    return [{
        "id": p.id,
        "name": p.name,
        "points": p.points,
        "description": p.description,
        "icon": p.icon,
        "assigned_to": p.assigned_to or [],
    } for p in common["data"].get("penalties", [])]


def _build_bonuses_list(common: dict) -> list[dict]:
    return [{
        "id": b.id,
        "name": b.name,
        "points": b.points,
        "description": b.description,
        "icon": b.icon,
        "assigned_to": b.assigned_to or [],
    } for b in common["data"].get("bonuses", [])]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaskMate sensors."""
    coordinator: TaskMateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    # Track child IDs that have sensors created
    tracked_child_ids: set[str] = set()

    # Add global sensors. The overview sensor is kept for backward compatibility
    # with existing Lovelace dashboards; its heavy attributes have been split
    # across four companion sensors to stay below the 16KB recorder limit.
    entities.append(TaskMateOverallStatsSensor(coordinator, entry))
    entities.append(TaskMateChoresSensor(coordinator, entry))
    entities.append(TaskMateChoreAvailabilitySensor(coordinator, entry))
    entities.append(TaskMateRewardsSensor(coordinator, entry))
    entities.append(TaskMateActivitySensor(coordinator, entry))
    entities.append(TaskMateIncentivesSensor(coordinator, entry))

    # Add sensors for each child
    for child in coordinator.data.get("children", []):
        entities.append(ChildPointsSensor(coordinator, entry, child))
        entities.append(ChildStatsSensor(coordinator, entry, child))
        entities.append(ChildBadgesSensor(coordinator, entry, child))
        tracked_child_ids.add(child.id)

    # Add pending approvals sensor
    entities.append(PendingApprovalsSensor(coordinator, entry))

    async_add_entities(entities)

    # Set up listener for new children
    @callback
    def async_add_child_sensors() -> None:
        """Add sensors for newly added children."""
        new_entities: list[SensorEntity] = []

        for child in coordinator.data.get("children", []):
            if child.id not in tracked_child_ids:
                new_entities.append(ChildPointsSensor(coordinator, entry, child))
                new_entities.append(ChildStatsSensor(coordinator, entry, child))
                new_entities.append(ChildBadgesSensor(coordinator, entry, child))
                tracked_child_ids.add(child.id)

        if new_entities:
            async_add_entities(new_entities)

    coordinator.async_add_listener(async_add_child_sensors)


class TaskMateBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for TaskMate sensors."""

    def __init__(
        self,
        coordinator: TaskMateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="TaskMate",
            manufacturer="TaskMate",
            model="Family Chore Manager",
        )


class _CachedAttrsSensor(TaskMateBaseSensor):
    """Base for sensors whose attributes are expensive to build."""

    def __init__(self, coordinator: TaskMateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._cached_attrs: dict | None = None
        self._cached_data_id: int | None = None

    @property
    def extra_state_attributes(self) -> dict:
        data_id = id(self.coordinator.data)
        if self._cached_data_id == data_id and self._cached_attrs is not None:
            return self._cached_attrs
        attrs = self._build_attributes()
        self._cached_attrs = attrs
        self._cached_data_id = data_id
        return attrs

    def _build_attributes(self) -> dict:  # pragma: no cover - abstract
        raise NotImplementedError


class TaskMateOverallStatsSensor(_CachedAttrsSensor):
    """Overview sensor — scalars plus the compact per-child summary.

    Heavy lists (chores/rewards/activity/incentives) live on companion
    sensors so this entity stays well under the 16KB recorder limit.
    """

    def __init__(
        self,
        coordinator: TaskMateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_overall_stats"
        self._attr_name = "TaskMate Overview"

    @property
    def native_value(self) -> int:
        """Return the total number of children."""
        return len(self.coordinator.data.get("children", []))

    @property
    def icon(self) -> str:
        return "mdi:clipboard-check-multiple"

    def _build_attributes(self) -> dict:
        common = _compute_common(self.coordinator)
        data = common["data"]
        children = common["children"]
        chores = common["chores"]
        rewards = common["rewards"]

        total_points = sum(c.points for c in children)
        total_chores_completed = sum(c.total_chores_completed for c in children)
        today_dow = dt_util.now().strftime("%A").lower()
        settings = data.get("settings", {})

        time_periods = self.coordinator.get_time_periods()
        period_by_id = {p["id"]: p for p in time_periods}
        active_vacation = self.coordinator.active_vacation()

        # Legacy shape kept for cards that still read the four fixed keys.
        legacy_defaults = {
            "morning": ("06:00", "12:00"), "afternoon": ("12:00", "17:00"),
            "evening": ("17:00", "21:00"), "night": ("21:00", "23:59"),
        }
        time_boundaries = {}
        for cat, (def_start, def_end) in legacy_defaults.items():
            period = period_by_id.get(cat)
            time_boundaries[f"{cat}_start"] = period["start"] if period else def_start
            time_boundaries[f"{cat}_end"] = period["end"] if period else def_end

        return {
            "today_day_of_week": today_dow,
            "streak_reset_mode": settings.get("streak_reset_mode", "reset"),
            "weekend_multiplier": _safe_float(settings.get("weekend_multiplier"), 2.0),
            "streak_milestones_enabled": settings.get("streak_milestones_enabled", "true") == "true",
            "streak_milestones": settings.get("streak_milestones", "3:5, 7:10, 14:20, 30:50, 60:100, 100:200"),
            "perfect_week_enabled": settings.get("perfect_week_enabled", "true") == "true",
            "perfect_week_bonus": _safe_int(settings.get("perfect_week_bonus"), 50),
            "streak_requires_all_chores": settings.get("streak_requires_all_chores", "false") in (True, "true"),
            "perfect_week_requires_all_chores": settings.get("perfect_week_requires_all_chores", "false") in (True, "true"),
            "total_children": len(children),
            "total_chores": len(chores),
            "total_rewards": len(rewards),
            "total_points_available": total_points,
            "total_chores_completed": total_chores_completed,
            "total_completions_all_time": len(common["all_completions"]),
            "total_pending_completions": len(common["pending_completions"]),
            "points_name": data.get("points_name", "Stars"),
            "points_icon": data.get("points_icon", "mdi:star"),
            # Global default card-design style; cards read this when no per-card override (#design).
            "card_design": settings.get("card_design", "classic"),
            "children": _build_children_summary(self.coordinator, common),
            "time_boundaries": time_boundaries,
            "time_periods": time_periods,
            "vacation_active": active_vacation is not None,
            "vacation_name": active_vacation.get("name", "") if active_vacation else "",
            "vacation_end": active_vacation.get("end", "") if active_vacation else "",
            "vacation_periods": self.coordinator.get_vacation_periods(),
        }


class TaskMateChoresSensor(_CachedAttrsSensor):
    """Chores catalog + today's completions."""

    def __init__(
        self,
        coordinator: TaskMateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_chores"
        self._attr_name = "TaskMate Chores"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("chores", []))

    @property
    def icon(self) -> str:
        return "mdi:format-list-checks"

    def _build_attributes(self) -> dict:
        common = _compute_common(self.coordinator)
        task_groups = [
            {
                "id": g.id,
                "name": g.name,
                "policy": g.policy,
                "chore_ids": list(g.chore_ids or []),
            }
            for g in self.coordinator.storage.get_task_groups()
        ]
        active_vacation = self.coordinator.active_vacation()
        return {
            "chores": _build_chores_list(self.coordinator, common),
            "todays_completions": _build_todays_completions(common),
            "task_groups": task_groups,
            "active_timed_sessions": _build_active_timed_sessions(self.coordinator),
            "vacation_active": active_vacation is not None,
            "vacation_name": active_vacation.get("name", "") if active_vacation else "",
            "vacation_end": active_vacation.get("end", "") if active_vacation else "",
        }


class TaskMateChoreAvailabilitySensor(_CachedAttrsSensor):
    """Per-chore × per-child availability matrix.

    Split off from the chores sensor so `sensor.taskmate_chores` can stay
    under the 16 KB recorder limit even for families with lots of chores.
    The map is `{chore_id: {child_id: bool}}`.
    """

    def __init__(
        self,
        coordinator: TaskMateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_chore_availability"
        self._attr_name = "TaskMate Chore Availability"

    @property
    def native_value(self) -> int:
        common = _compute_common(self.coordinator)
        total = 0
        availability = _build_chore_availability(self.coordinator, common)
        for per_child in availability.values():
            total += sum(1 for v in per_child.values() if v)
        return total

    @property
    def icon(self) -> str:
        return "mdi:calendar-check"

    def _build_attributes(self) -> dict:
        common = _compute_common(self.coordinator)
        return {
            "chore_availability": _build_chore_availability(self.coordinator, common),
        }


class TaskMateRewardsSensor(_CachedAttrsSensor):
    """Rewards catalog + pending claims + pool allocations."""

    def __init__(
        self,
        coordinator: TaskMateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_rewards"
        self._attr_name = "TaskMate Rewards"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("rewards", []))

    @property
    def icon(self) -> str:
        return "mdi:gift-outline"

    def _build_attributes(self) -> dict:
        common = _compute_common(self.coordinator)
        return {
            "rewards": _build_rewards_list(common),
            "pending_reward_claims": _build_pending_reward_claims(common),
            "pool_allocations": [pa.to_dict() for pa in common["pool_alloc_objs"]],
        }


class TaskMateActivitySensor(_CachedAttrsSensor):
    """Recent completions + recent points/reward transactions."""

    def __init__(
        self,
        coordinator: TaskMateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_activity"
        self._attr_name = "TaskMate Activity"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get("completions", []))

    @property
    def icon(self) -> str:
        return "mdi:history"

    def _build_attributes(self) -> dict:
        common = _compute_common(self.coordinator)
        children = common["children"]
        career_history = {}
        for c in children:
            career_history[c.id] = self.coordinator.storage.get_career_score_history(c.id)
        return {
            "recent_completions": _build_recent_completions(common),
            "recent_transactions": _build_recent_transactions(common),
            "career_score_history": career_history,
        }


class TaskMateIncentivesSensor(_CachedAttrsSensor):
    """Penalties + bonuses catalogue."""

    def __init__(
        self,
        coordinator: TaskMateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_incentives"
        self._attr_name = "TaskMate Incentives"

    @property
    def native_value(self) -> int:
        data = self.coordinator.data
        return len(data.get("penalties", [])) + len(data.get("bonuses", []))

    @property
    def icon(self) -> str:
        return "mdi:scale-balance"

    def _build_attributes(self) -> dict:
        common = _compute_common(self.coordinator)
        return {
            "penalties": _build_penalties_list(common),
            "bonuses": _build_bonuses_list(common),
        }


class ChildPointsSensor(TaskMateBaseSensor):
    """Sensor for a child's points."""

    def __init__(
        self,
        coordinator: TaskMateCoordinator,
        entry: ConfigEntry,
        child: Child,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self.child_id = child.id
        self._attr_unique_id = f"{entry.entry_id}_{child.id}_points"
        self._attr_name = f"{child.name} Points"
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> int:
        """Return the child's current points."""
        child = self.coordinator.get_child(self.child_id)
        return child.points if child else 0

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self.coordinator.data.get("points_name", "Stars")

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self.coordinator.data.get("points_icon", "mdi:star")

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        child = self.coordinator.get_child(self.child_id)
        if not child:
            return {}

        return {
            "child_id": child.id,
            "child_name": child.name,
            "avatar": child.avatar,
            "total_points_earned": child.total_points_earned,
            "total_chores_completed": child.total_chores_completed,
            "current_streak": child.current_streak,
            "best_streak": child.best_streak,
            "career_score": child.career_score,
            "total_penalties_received": child.total_penalties_received,
        }


class ChildStatsSensor(TaskMateBaseSensor):
    """Sensor for a child's statistics."""

    _attr_translation_key = "child_stats"

    def __init__(
        self,
        coordinator: TaskMateCoordinator,
        entry: ConfigEntry,
        child: Child,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self.child_id = child.id
        self._attr_unique_id = f"{entry.entry_id}_{child.id}_stats"
        self._attr_name = f"{child.name} Stats"
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> int:
        """Return the child's total chores completed."""
        child = self.coordinator.get_child(self.child_id)
        return child.total_chores_completed if child else 0

    @property
    def icon(self) -> str:
        """Return the icon."""
        child = self.coordinator.get_child(self.child_id)
        return child.avatar if child else "mdi:account-circle"

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        child = self.coordinator.get_child(self.child_id)
        if not child:
            return {}

        # Get chores assigned to this child. For alternating/random/balanced
        # assignment, only include a chore when this child is the active one
        # today. first_come is competitive: the whole pool sees it (no single
        # active child) until one member fills the shared quota. Either way,
        # drop it once any pool member has completed it today (so a parent
        # crediting the off-rotation child clears the chore for everyone).
        chores = self.coordinator.data.get("chores", [])
        def _included(c):
            if not (child.id in c.assigned_to or not c.assigned_to):
                return False
            mode = getattr(c, "assignment_mode", "everyone")
            if mode not in ("everyone", "first_come"):
                if getattr(c, "assignment_current_child_id", "") != child.id:
                    return False
            if mode != "everyone":
                if self.coordinator._is_rotation_done_today(c):
                    return False
            return True
        assigned_chores = [c for c in chores if _included(c)]

        return {
            "child_id": child.id,
            "child_name": child.name,
            "avatar": child.avatar,
            "points": child.points,
            "total_points_earned": child.total_points_earned,
            "total_chores_completed": child.total_chores_completed,
            "current_streak": child.current_streak,
            "best_streak": child.best_streak,
            "career_score": child.career_score,
            "total_penalties_received": child.total_penalties_received,
            "assigned_chores": [{"id": c.id, "name": c.name, "points": c.points, "time_category": c.time_category} for c in assigned_chores],
            "chore_order": child.chore_order,
        }


class ChildBadgesSensor(TaskMateBaseSensor):
    """Sensor exposing a child's earned and available badges."""

    _attr_icon = "mdi:trophy-award"
    _attr_translation_key = "child_badges"

    def __init__(
        self,
        coordinator: TaskMateCoordinator,
        entry: ConfigEntry,
        child: Child,
    ) -> None:
        super().__init__(coordinator, entry)
        self.child_id = child.id
        self._attr_unique_id = f"{entry.entry_id}_{child.id}_badges"
        self._attr_name = f"{child.name} Badges"

    @property
    def native_value(self) -> int:
        """Number of badges earned by this child."""
        return len(
            self.coordinator.storage.get_awarded_badges_for_child(self.child_id)
        )

    @property
    def extra_state_attributes(self) -> dict:
        from .coord_badges import resolve_metric

        storage = self.coordinator.storage
        child = storage.get_child(self.child_id)
        if child is None:
            return {"earned": [], "available": [], "total_badges": 0}

        all_badges = [b for b in storage.get_badges() if b.enabled]
        applicable = [
            b for b in all_badges
            if not b.assigned_to or self.child_id in b.assigned_to
        ]

        awarded_records = storage.get_awarded_badges_for_child(self.child_id)
        record_by_id = {a.badge_id: a for a in awarded_records}

        earned: list[dict] = []
        available: list[dict] = []
        for b in applicable:
            if b.id in record_by_id:
                rec = record_by_id[b.id]
                earned.append({
                    "badge_id": b.id,
                    "name": b.name,
                    "icon": b.icon,
                    "tier": b.tier,
                    "earned_at": rec.earned_at.isoformat() if rec.earned_at else None,
                    "manually_awarded": rec.manually_awarded,
                    "silent": rec.silent,
                })
            else:
                if not b.criteria:
                    progress_pct = 0
                else:
                    pcts = []
                    for c in b.criteria:
                        cur = resolve_metric(c.metric, child, storage)
                        target = max(c.value, 1)
                        pcts.append(min(100, int(100 * cur / target)))
                    progress_pct = min(pcts) if pcts else 0
                available.append({
                    "badge_id": b.id,
                    "name": b.name,
                    "icon": b.icon,
                    "tier": b.tier,
                    "progress_pct": progress_pct,
                    "criteria_summary": ", ".join(
                        f"{c.metric} >= {c.value}" for c in b.criteria
                    ),
                })

        earned.sort(key=lambda e: e.get("earned_at") or "", reverse=True)

        return {
            "earned": earned,
            "available": available,
            "total_badges": len(applicable),
        }


class PendingApprovalsSensor(TaskMateBaseSensor):
    """Sensor for pending approvals."""

    def __init__(
        self,
        coordinator: TaskMateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_pending_approvals"
        self._attr_name = "Pending Approvals"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the number of pending approvals."""
        pending_completions = self.coordinator.data.get("pending_completions", [])
        pending_rewards = self.coordinator.data.get("pending_reward_claims", [])
        return len(pending_completions) + len(pending_rewards)

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:clipboard-clock"

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        pending_completions = self.coordinator.data.get("pending_completions", [])
        pending_rewards = self.coordinator.data.get("pending_reward_claims", [])

        completion_details = []
        for comp in pending_completions:
            child = self.coordinator.get_child(comp.child_id)
            chore = self.coordinator.get_chore(comp.chore_id)
            if child and chore:
                # Bonus sub-task completions carry the sub-task's own name and
                # points; mirror _build_todays_completions so cards reading this
                # list render them identically.
                bonus_subtask_id = getattr(comp, "bonus_subtask_id", "") or ""
                if bonus_subtask_id:
                    subtask = next(
                        (b for b in chore.bonus_subtasks if b.id == bonus_subtask_id), None
                    )
                    chore_name = f"{chore.name} › {subtask.name}" if subtask else chore.name
                    pts = subtask.points if subtask else 0
                else:
                    chore_name = chore.name
                    pts = chore.points
                timed_secs = getattr(comp, "timed_duration_seconds", 0) or 0
                if timed_secs > 0 and getattr(chore, "task_type", "") == "timed":
                    rate_seconds = chore.timed_rate_minutes * 60
                    if rate_seconds > 0:
                        pts = (timed_secs // rate_seconds) * chore.timed_rate_points
                detail = {
                    "completion_id": comp.id,
                    "type": "chore",
                    "child_name": child.name,
                    "child_id": child.id,
                    "chore_name": chore_name,
                    "chore_id": chore.id,
                    "points": pts,
                    "time_category": chore.time_category,
                    "completed_at": comp.completed_at.isoformat(),
                    "bonus_subtask_id": bonus_subtask_id,
                }
                if timed_secs > 0:
                    detail["timed_duration_seconds"] = timed_secs
                photo = getattr(comp, "photo_url", "") or ""
                if photo:
                    detail["photo_url"] = photos.sign_photo_url(
                        self.coordinator.hass, photo
                    )
                completion_details.append(detail)

        reward_details = []
        for claim in pending_rewards:
            child = self.coordinator.get_child(claim.child_id)
            reward = self.coordinator.get_reward(claim.reward_id)
            if child and reward:
                reward_details.append({
                    "claim_id": claim.id,
                    "type": "reward",
                    "child_name": child.name,
                    "child_id": child.id,
                    "reward_name": reward.name,
                    "reward_id": reward.id,
                    "cost": reward.cost,
                    "claimed_at": claim.claimed_at.isoformat(),
                })

        mandatory_misses = self.coordinator.mandatory_misses_state()
        return {
            "pending_chore_completions": len(pending_completions),
            "pending_reward_claims": len(pending_rewards),
            "pending_mandatory_misses": len(mandatory_misses),
            "chore_completions": completion_details,
            "reward_claims": reward_details,
            "mandatory_misses": mandatory_misses,
        }
