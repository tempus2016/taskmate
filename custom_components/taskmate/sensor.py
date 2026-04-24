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


def _build_children_summary(common: dict) -> list[dict]:
    """Build compact per-child summary used on the overview sensor."""
    children = common["children"]
    pending = common["pending_points_by_child"]
    committed = common["committed_points_by_child"]
    allocated = common["total_allocated_by_child"]
    summary = []
    for c in children:
        committed_amount = committed.get(c.id, 0)
        summary.append({
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
            "streak_milestones_achieved": getattr(c, 'streak_milestones_achieved', None) or [],
            "awarded_perfect_weeks": getattr(c, 'awarded_perfect_weeks', None) or [],
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
        # Optional fields — emit only when non-default to save bytes.
        description = getattr(c, 'description', '') or ''
        if description:
            record["description"] = description
        daily_limit = getattr(c, 'daily_limit', 1)
        if daily_limit != 1:
            record["daily_limit"] = daily_limit
        due_days = getattr(c, 'due_days', []) or []
        if due_days:
            record["due_days"] = due_days
        requires_approval = getattr(c, 'requires_approval', True)
        if not requires_approval:
            record["requires_approval"] = False
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
        out.append({
            "completion_id": comp.id,
            "chore_id": comp.chore_id,
            "child_id": comp.child_id,
            "child_name": child_lookup[comp.child_id].name if comp.child_id in child_lookup else "",
            "chore_name": matched_chore.name if matched_chore else "",
            "points": matched_chore.points if matched_chore else 0,
            "approved": comp.approved,
            "completed_at": comp.completed_at.isoformat() if hasattr(comp.completed_at, 'isoformat') else str(comp.completed_at),
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
    return [{
        "completion_id": comp.id,
        "chore_id": comp.chore_id,
        "child_id": comp.child_id,
        "child_name": child_lookup[comp.child_id].name if comp.child_id in child_lookup else "",
        "chore_name": chore_lookup[comp.chore_id].name if comp.chore_id in chore_lookup else "",
        "points": chore_lookup[comp.chore_id].points if comp.chore_id in chore_lookup else 0,
        "approved": comp.approved,
        "completed_at": comp.completed_at.isoformat() if hasattr(comp.completed_at, 'isoformat') else str(comp.completed_at),
    } for comp in recent]


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

        return {
            "today_day_of_week": today_dow,
            "streak_reset_mode": settings.get("streak_reset_mode", "reset"),
            "weekend_multiplier": _safe_float(settings.get("weekend_multiplier"), 2.0),
            "streak_milestones_enabled": settings.get("streak_milestones_enabled", "true") == "true",
            "streak_milestones": settings.get("streak_milestones", "3:5, 7:10, 14:20, 30:50, 60:100, 100:200"),
            "perfect_week_enabled": settings.get("perfect_week_enabled", "true") == "true",
            "perfect_week_bonus": _safe_int(settings.get("perfect_week_bonus"), 50),
            "total_children": len(children),
            "total_chores": len(chores),
            "total_rewards": len(rewards),
            "total_points_available": total_points,
            "total_chores_completed": total_chores_completed,
            "total_completions_all_time": len(common["all_completions"]),
            "total_pending_completions": len(common["pending_completions"]),
            "points_name": data.get("points_name", "Stars"),
            "points_icon": data.get("points_icon", "mdi:star"),
            "children": _build_children_summary(common),
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
        return {
            "chores": _build_chores_list(self.coordinator, common),
            "todays_completions": _build_todays_completions(common),
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
        return {
            "recent_completions": _build_recent_completions(common),
            "recent_transactions": _build_recent_transactions(common),
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
        }


class ChildStatsSensor(TaskMateBaseSensor):
    """Sensor for a child's statistics."""

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
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "chores"

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

        # Get chores assigned to this child. For alternating/random assignment,
        # only include a chore when this child is the active one today — and
        # drop it once any pool member has completed it today (so a parent
        # crediting the off-rotation child clears the chore for everyone).
        chores = self.coordinator.data.get("chores", [])
        def _included(c):
            if not (child.id in c.assigned_to or not c.assigned_to):
                return False
            if getattr(c, "assignment_mode", "everyone") != "everyone":
                if getattr(c, "assignment_current_child_id", "") != child.id:
                    return False
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
            "assigned_chores": [{"id": c.id, "name": c.name, "points": c.points, "time_category": c.time_category} for c in assigned_chores],
            "chore_order": child.chore_order,
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
                completion_details.append({
                    "completion_id": comp.id,
                    "type": "chore",
                    "child_name": child.name,
                    "child_id": child.id,
                    "chore_name": chore.name,
                    "chore_id": chore.id,
                    "points": chore.points,
                    "time_category": chore.time_category,
                    "completed_at": comp.completed_at.isoformat(),
                })

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

        return {
            "pending_chore_completions": len(pending_completions),
            "pending_reward_claims": len(pending_rewards),
            "chore_completions": completion_details,
            "reward_claims": reward_details,
        }
