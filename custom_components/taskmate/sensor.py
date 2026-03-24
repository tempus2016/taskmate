"""Sensor platform for TaskMate integration."""
from __future__ import annotations

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

from datetime import datetime

import logging

from .const import DOMAIN
from .coordinator import TaskMateCoordinator
from .models import Child, Chore, Reward

_LOGGER = logging.getLogger(__name__)


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

    # Add overall stats sensor
    entities.append(ChoremandorOverallStatsSensor(coordinator, entry))

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


class ChoremandorOverallStatsSensor(TaskMateBaseSensor):
    """Sensor for overall TaskMate statistics."""

    def __init__(
        self,
        coordinator: TaskMateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_overall_stats"
        self._attr_name = "TaskMate Overview"

    @property
    def native_value(self) -> int:
        """Return the total number of children."""
        return len(self.coordinator.data.get("children", []))

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        data = self.coordinator.data
        children = data.get("children", [])
        chores = data.get("chores", [])
        rewards = data.get("rewards", [])

        total_points = sum(c.points for c in children)
        total_chores_completed = sum(c.total_chores_completed for c in children)

        # Get all completions and pending completions
        all_completions = data.get("completions", [])
        pending_completions = data.get("pending_completions", [])

        # Build today's completions summary (both approved and pending)
        # Use HA timezone-aware datetime for proper date comparison
        now = dt_util.now()
        today = now.date()
        todays_completions = []
        # Build chore lookup for enriching completions
        chore_lookup = {c.id: c for c in chores}
        # Build child lookup for enriching completions
        child_lookup = {c.id: c for c in children}

        for comp in all_completions:
            # Convert completion time to HA timezone for proper date comparison
            comp_dt = comp.completed_at
            if hasattr(comp_dt, 'astimezone'):
                # If timezone-aware, convert to HA timezone
                comp_dt = dt_util.as_local(comp_dt)
            comp_date = comp_dt.date() if hasattr(comp_dt, 'date') else comp_dt
            matched_chore = chore_lookup.get(comp.chore_id)
            if comp_date == today:
                todays_completions.append({
                    "completion_id": comp.id,
                    "chore_id": comp.chore_id,
                    "child_id": comp.child_id,
                    "child_name": child_lookup.get(comp.child_id, None) and child_lookup[comp.child_id].name or "",
                    "chore_name": matched_chore.name if matched_chore else "",
                    "points": matched_chore.points if matched_chore else 0,
                    "approved": comp.approved,
                    "completed_at": comp.completed_at.isoformat() if hasattr(comp.completed_at, 'isoformat') else str(comp.completed_at),
                })

        # Calculate pending points per child (chores awaiting approval = points to be earned)
        pending_points_by_child = {}
        for comp in pending_completions:
            child_id = comp.child_id
            chore = next((c for c in chores if c.id == comp.chore_id), None)
            if chore:
                pending_points_by_child[child_id] = pending_points_by_child.get(child_id, 0) + chore.points

        # Calculate committed points per child (reward claims awaiting approval = points reserved)
        committed_points_by_child = {}
        pending_reward_claim_objs = data.get("pending_reward_claims", [])
        for rc in pending_reward_claim_objs:
            reward = next((r for r in rewards if r.id == rc.reward_id), None)
            if reward:
                # All reward costs are static
                cost = reward.cost
                committed_points_by_child[rc.child_id] = committed_points_by_child.get(rc.child_id, 0) + cost

        # Build chores list with recurrence fields and availability per child
        chores_list = []
        for c in chores:
            # Ensure assigned_to is always a list
            assigned_to = c.assigned_to if isinstance(c.assigned_to, list) else []

            # Build last_completed_at and is_available per child
            last_completed_at = {}
            is_available = {}
            for child in children:
                record = self.coordinator.storage.get_last_completed(c.id, child.id)
                if record.get('current'):
                    last_completed_at[child.id] = record['current']
                is_available[child.id] = self.coordinator.is_chore_available_for_child(c, child.id)

            chores_list.append({
                "id": c.id,
                "name": c.name,
                "description": getattr(c, 'description', '') or '',
                "points": c.points,
                "time_category": c.time_category,
                "daily_limit": getattr(c, 'daily_limit', 1),
                "assigned_to": assigned_to,
                "completion_sound": getattr(c, 'completion_sound', 'coin'),
                "due_days": getattr(c, 'due_days', []) or [],
                "requires_approval": getattr(c, 'requires_approval', True),
                "schedule_mode": getattr(c, 'schedule_mode', 'specific_days'),
                "recurrence": getattr(c, 'recurrence', 'weekly'),
                "recurrence_day": getattr(c, 'recurrence_day', ''),
                "recurrence_start": getattr(c, 'recurrence_start', ''),
                "first_occurrence_mode": getattr(c, 'first_occurrence_mode', 'available_immediately'),
                "last_completed_at": last_completed_at,
                "is_available": is_available,
            })

        # Build rewards list — all costs are static (fixed by parent)
        rewards_list = []
        for r in rewards:
            assigned = r.assigned_to if isinstance(r.assigned_to, list) and r.assigned_to else [c.id for c in children]
            # Static cost for all children
            calculated_costs = {child_id: r.cost for child_id in assigned}

            rewards_list.append({
                "id": r.id,
                "name": r.name,
                "cost": r.cost,
                "description": getattr(r, 'description', ''),
                "icon": r.icon,
                "assigned_to": r.assigned_to if isinstance(r.assigned_to, list) else [],
                "is_jackpot": getattr(r, 'is_jackpot', False),
                "calculated_costs": calculated_costs,
            })

        # Day of week for due_days filtering in frontend (lowercase, e.g. "monday")
        today_dow = dt_util.now().strftime("%A").lower()

        return {
            "today_day_of_week": today_dow,
            "streak_reset_mode": data.get("settings", {}).get("streak_reset_mode", "reset"),
            "weekend_multiplier": float(data.get("settings", {}).get("weekend_multiplier", "2.0") or "2.0"),
            "streak_milestones_enabled": data.get("settings", {}).get("streak_milestones_enabled", "true") == "true",
            "streak_milestones": data.get("settings", {}).get("streak_milestones", "3:5, 7:10, 14:20, 30:50, 60:100, 100:200"),
            "perfect_week_enabled": data.get("settings", {}).get("perfect_week_enabled", "true") == "true",
            "perfect_week_bonus": int(data.get("settings", {}).get("perfect_week_bonus", "50") or "50"),
            "total_children": len(children),
            "total_chores": len(chores),
            "total_rewards": len(rewards),
            "total_points_available": total_points,
            "total_chores_completed": total_chores_completed,
            "points_name": data.get("points_name", "Stars"),
            "points_icon": data.get("points_icon", "mdi:star"),
            "children": [{
                "id": c.id,
                "name": c.name,
                "points": c.points,
                "pending_points": pending_points_by_child.get(c.id, 0),
                "committed_points": committed_points_by_child.get(c.id, 0),
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
            } for c in children],
            "chores": chores_list,
            "rewards": rewards_list,
            "todays_completions": todays_completions,
            "total_completions_all_time": len(all_completions),
            "total_pending_completions": len(pending_completions),
            "pending_reward_claims": self._build_pending_reward_claims(
                data.get("pending_reward_claims", []), rewards, child_lookup
            ),
            "recent_completions": [{
                "completion_id": comp.id,
                "chore_id": comp.chore_id,
                "child_id": comp.child_id,
                "child_name": child_lookup.get(comp.child_id, None) and child_lookup[comp.child_id].name or "",
                "chore_name": chore_lookup.get(comp.chore_id, None) and chore_lookup[comp.chore_id].name or "",
                "points": chore_lookup.get(comp.chore_id, None) and chore_lookup[comp.chore_id].points or 0,
                "approved": comp.approved,
                "completed_at": comp.completed_at.isoformat() if hasattr(comp.completed_at, 'isoformat') else str(comp.completed_at),
            } for comp in sorted(all_completions, key=lambda c: c.completed_at, reverse=True)[:200]],
            "recent_transactions": self._build_recent_transactions(
                data.get("points_transactions", []),
                data.get("reward_claims", []),
                rewards,
                child_lookup,
            ),
        }

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:clipboard-check-multiple"


    def _build_recent_transactions(self, points_transactions, all_reward_claims, rewards, child_lookup):
        """Build unified activity feed of manual point adjustments and reward claims."""
        reward_lookup = {r.id: r for r in rewards}
        events = []

        # Manual points transactions
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

        # Reward claims — show both pending and approved
        for rc in all_reward_claims:
            child = child_lookup.get(rc.child_id)
            reward = reward_lookup.get(rc.reward_id)
            if not child or not reward:
                continue
            cost = reward.cost
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
                "points": -cost,  # negative — points spent
                "approved": rc.approved,
                "created_at": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
            })

        # Sort all events newest first, cap at 50
        events.sort(key=lambda e: e["created_at"], reverse=True)
        return events[:50]

    def _build_pending_reward_claims(self, pending_claims, rewards, child_lookup):
        """Build enriched pending reward claims list."""
        reward_lookup = {r.id: r for r in rewards}
        result = []
        for rc in pending_claims:
            reward = reward_lookup.get(rc.reward_id)
            child = child_lookup.get(rc.child_id)
            if not reward or not child:
                continue
            cost = reward.cost
            result.append({
                "claim_id": rc.id,
                "reward_id": rc.reward_id,
                "child_id": rc.child_id,
                "child_name": child.name,
                "child_avatar": getattr(child, 'avatar', 'mdi:account-circle') or 'mdi:account-circle',
                "reward_name": reward.name,
                "reward_icon": reward.icon or 'mdi:gift',
                "cost": cost,
                "claimed_at": rc.claimed_at.isoformat() if hasattr(rc.claimed_at, 'isoformat') else str(rc.claimed_at),
            })
        return result


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

        # Get chores assigned to this child
        chores = self.coordinator.data.get("chores", [])
        assigned_chores = [c for c in chores if child.id in c.assigned_to or not c.assigned_to]

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
