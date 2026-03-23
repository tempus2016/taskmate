"""Data coordinator for TaskMate integration."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .models import Child, Chore, ChoreCompletion, Reward, RewardClaim, PointsTransaction
from .storage import TaskMateStorage

_LOGGER = logging.getLogger(__name__)


class TaskMateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage TaskMate data."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.storage = TaskMateStorage(hass, entry_id)
        self.entry_id = entry_id
        self._unsub_midnight: callable | None = None
        self._unsub_prune: callable | None = None

    async def async_initialize(self) -> None:
        """Initialize the coordinator."""
        await self.storage.async_load()
        await self.async_refresh()
        # Schedule midnight streak check at 00:00:05
        self._unsub_midnight = async_track_time_change(
            self.hass, self._async_midnight_streak_check, hour=0, minute=0, second=5
        )
        # Schedule daily history pruning at 00:01:00
        self._unsub_prune = async_track_time_change(
            self.hass, self._async_scheduled_prune, hour=0, minute=1, second=0
        )

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and clean up listeners."""
        if self._unsub_midnight:
            self._unsub_midnight()
            self._unsub_midnight = None
        if self._unsub_prune:
            self._unsub_prune()
            self._unsub_prune = None

    @callback
    def _async_midnight_streak_check(self, now: datetime) -> None:
        """Scheduled callback at midnight to check and reset streaks if needed."""
        self.hass.async_create_task(self._async_check_streaks())
        # Check for perfect week bonus every Monday at midnight
        if now.weekday() == 0:
            self.hass.async_create_task(self._async_check_perfect_week())

    @callback
    def _async_scheduled_prune(self, now: datetime) -> None:
        """Scheduled callback to prune old completion history."""
        days = int(self.storage.get_setting("history_days", "90"))
        self.hass.async_create_task(self.async_prune_history(days))

    async def _async_check_perfect_week(self) -> None:
        """Award perfect week bonus to children who completed at least one chore every day last week."""
        perfect_week_enabled = self.storage.get_setting("perfect_week_enabled", "true") == "true"
        if not perfect_week_enabled:
            return

        try:
            perfect_week_bonus = int(self.storage.get_setting("perfect_week_bonus", "50"))
        except (ValueError, TypeError):
            perfect_week_bonus = 50

        today = dt_util.now().date()
        # Should only run on Monday — last week is Mon(today-7) to Sun(today-1)
        if today.weekday() != 0:
            _LOGGER.debug("Perfect week check skipped (not Monday)")
            return

        last_monday = today - timedelta(days=7)
        last_week_dates = {(last_monday + timedelta(days=i)).isoformat() for i in range(7)}
        week_key = last_monday.isoformat()

        all_completions = self.storage.get_completions()
        children = self.storage.get_children()
        changed = False

        for child in children:
            awarded_weeks = list(getattr(child, 'awarded_perfect_weeks', None) or [])

            # Skip if already awarded for this week
            if week_key in awarded_weeks:
                continue

            # Get all days this child had at least one approved completion last week
            completed_days = set()
            for comp in all_completions:
                if comp.child_id != child.id or not comp.approved:
                    continue
                try:
                    comp_local = dt_util.as_local(comp.completed_at)
                    comp_date_str = comp_local.date().isoformat()
                    if comp_date_str in last_week_dates:
                        completed_days.add(comp_date_str)
                except Exception:
                    continue

            if completed_days == last_week_dates:
                # Perfect week!
                child.awarded_perfect_weeks = awarded_weeks + [week_key]
                child.points += perfect_week_bonus
                child.total_points_earned += perfect_week_bonus
                self.storage.update_child(child)

                transaction = PointsTransaction(
                    child_id=child.id,
                    points=perfect_week_bonus,
                    reason=f"Perfect week bonus! ({last_monday.strftime('%d %b')} – {(today - timedelta(days=1)).strftime('%d %b')})",
                    created_at=dt_util.now(),
                )
                self.storage.add_points_transaction(transaction)
                changed = True
                _LOGGER.info(
                    "Perfect week bonus (%d pts) awarded to %s for week of %s",
                    perfect_week_bonus, child.name, week_key,
                )

        if changed:
            await self.storage.async_save()
            await self.async_refresh()

    async def _async_check_streaks(self) -> None:
        """Check all children's streaks and reset/pause if they missed yesterday.

        Behaviour depends on streak_reset_mode setting:
        - "reset" (default): streak goes back to 0 on missed day
        - "pause": streak is preserved but not incremented until they complete again
        """
        today = dt_util.now().date()
        yesterday = today - timedelta(days=1)
        yesterday_str = yesterday.isoformat()
        today_str = today.isoformat()

        streak_mode = self.storage.get_setting("streak_reset_mode", "reset")

        children = self.storage.get_children()
        changed = False

        for child in children:
            last_date_str = getattr(child, "last_completion_date", None)
            if last_date_str is None:
                continue  # No completions yet, nothing to do

            # If last completion was today or yesterday, streak is fine
            if last_date_str in (yesterday_str, today_str):
                continue

            # They missed a day
            if (child.current_streak or 0) > 0:
                if streak_mode == "pause":
                    # Preserve the streak value but mark it as paused
                    # We do this by leaving current_streak as-is — _award_points
                    # will NOT increment it (gap detected) but won't reset either
                    # We need a flag so _award_points knows to resume not reset
                    child.streak_paused = True
                    _LOGGER.info(
                        "Streak paused for %s (last completion: %s, mode=pause)",
                        child.name, last_date_str
                    )
                else:
                    # Default: reset to 0
                    child.current_streak = 0
                    child.streak_paused = False
                    _LOGGER.info(
                        "Streak reset for %s (last completion: %s, mode=reset)",
                        child.name, last_date_str
                    )
                self.storage.update_child(child)
                changed = True

        if changed:
            await self.storage.async_save()
            await self.async_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from storage."""
        return {
            "children": self.storage.get_children(),
            "chores": self.storage.get_chores(),
            "rewards": self.storage.get_rewards(),
            "completions": self.storage.get_completions(),
            "pending_completions": self.storage.get_pending_completions(),
            "reward_claims": self.storage.get_reward_claims(),
            "pending_reward_claims": self.storage.get_pending_reward_claims(),
            "points_transactions": self.storage.get_points_transactions(),
            "points_name": self.storage.get_points_name(),
            "points_icon": self.storage.get_points_icon(),
            "settings": self.storage._data.get("settings", {}),
        }

    # Child operations
    async def async_add_child(self, name: str, avatar: str = "mdi:account-circle") -> Child:
        """Add a new child."""
        child = Child(name=name, avatar=avatar)
        self.storage.add_child(child)
        await self.storage.async_save()
        await self.async_refresh()
        return child

    async def async_update_child(self, child: Child) -> None:
        """Update a child."""
        self.storage.update_child(child)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_remove_child(self, child_id: str) -> None:
        """Remove a child."""
        self.storage.remove_child(child_id)
        await self.storage.async_save()
        await self.async_refresh()

    def get_child(self, child_id: str) -> Child | None:
        """Get a child by ID."""
        return self.storage.get_child(child_id)

    # Chore operations
    async def async_add_chore(
        self,
        name: str,
        points: int = 10,
        description: str = "",
        icon: str = "mdi:broom",
        due_days: list[str] | None = None,
        assigned_to: list[str] | None = None,
        requires_approval: bool = True,
        time_category: str = "anytime",
        daily_limit: int = 1,
        completion_sound: str = "coin",
        completion_percentage_per_month: int = 100,
    ) -> Chore:
        """Add a new chore."""
        chore = Chore(
            name=name,
            points=points,
            description=description,
            due_days=due_days or [],
            assigned_to=assigned_to or [],
            requires_approval=requires_approval,
            time_category=time_category,
            daily_limit=daily_limit,
            completion_sound=completion_sound,
            completion_percentage_per_month=completion_percentage_per_month,
        )
        self.storage.add_chore(chore)
        await self.storage.async_save()
        await self.async_refresh()
        return chore

    async def async_add_chores_bulk(
        self,
        chore_names: list[str],
        points: int = 10,
        icon: str = "mdi:broom",
        due_days: list[str] | None = None,
        assigned_to: list[str] | None = None,
        requires_approval: bool = True,
        time_category: str = "anytime",
        daily_limit: int = 1,
        completion_sound: str = "coin",
        completion_percentage_per_month: int = 100,
    ) -> list[Chore]:
        """Add multiple chores at once with shared settings."""
        chores = []
        for name in chore_names:
            name = name.strip()
            if not name:
                continue
            chore = Chore(
                name=name,
                points=points,
                description="",
                due_days=due_days or [],
                assigned_to=assigned_to or [],
                requires_approval=requires_approval,
                time_category=time_category,
                daily_limit=daily_limit,
                completion_sound=completion_sound,
                completion_percentage_per_month=completion_percentage_per_month,
            )
            self.storage.add_chore(chore)
            chores.append(chore)

        if chores:
            await self.storage.async_save()
            await self.async_refresh()
        return chores

    async def async_update_chore(self, chore: Chore) -> None:
        """Update a chore."""
        self.storage.update_chore(chore)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_remove_chore(self, chore_id: str) -> None:
        """Remove a chore."""
        self.storage.remove_chore(chore_id)
        await self.storage.async_save()
        await self.async_refresh()

    def get_chore(self, chore_id: str) -> Chore | None:
        """Get a chore by ID."""
        return self.storage.get_chore(chore_id)

    # Reward operations
    def calculate_dynamic_reward_costs(self, reward: Reward) -> dict[str, int]:
        """Calculate the dynamic cost of a reward for each child.

        By default, all rewards use dynamic pricing. If override_point_value is True,
        the manual cost is used instead.

        For non-jackpot rewards, each child has their own calculated cost based on
        their specific chores and completion rates.

        For jackpot rewards, all children share the same cost (sum of all daily points).

        Returns:
            Dict mapping child_id to their calculated cost for this reward.
            For jackpot rewards, all children have the same value.
        """
        result: dict[str, int] = {}

        # Get all children and chores
        all_children = self.storage.get_children()
        all_chores = self.storage.get_chores()

        _LOGGER.warning(
            "CALC_COSTS: reward=%s, override=%s, days_to_goal=%s, cost=%s, assigned_to=%s",
            reward.name,
            getattr(reward, 'override_point_value', False),
            getattr(reward, 'days_to_goal', 30),
            reward.cost,
            reward.assigned_to
        )
        _LOGGER.warning("CALC_COSTS: found %d children, %d chores", len(all_children), len(all_chores))

        # Determine which children are assigned to this reward
        if reward.assigned_to:
            assigned_children = [c for c in all_children if c.id in reward.assigned_to]
        else:
            assigned_children = all_children

        _LOGGER.debug("calculate_dynamic_reward_costs: assigned_children=%s", [c.name for c in assigned_children])

        if not assigned_children:
            _LOGGER.debug("calculate_dynamic_reward_costs: no assigned children, returning empty")
            return result

        # If override is enabled, use the manual cost for all children
        if getattr(reward, 'override_point_value', False):
            _LOGGER.debug("calculate_dynamic_reward_costs: override enabled, using manual cost %d", reward.cost)
            for child in assigned_children:
                result[child.id] = reward.cost
            return result

        # Get days_to_goal with a sensible default
        days_to_goal = getattr(reward, 'days_to_goal', 30)
        if days_to_goal <= 0:
            days_to_goal = 30

        if not all_chores:
            # Fall back to static cost if no chores
            _LOGGER.debug("calculate_dynamic_reward_costs: no chores, falling back to cost %d", reward.cost)
            for child in assigned_children:
                result[child.id] = reward.cost
            return result

        # Calculate daily expected points for each child
        child_daily_points: dict[str, float] = {}

        for child in assigned_children:
            daily_points = 0.0
            chores_counted = 0

            for chore in all_chores:
                # Check if this chore is assigned to this child
                # Empty assigned_to means all children can do it
                if chore.assigned_to and child.id not in chore.assigned_to:
                    continue

                chores_counted += 1
                # Get the completion percentage per month (default to 100% if not set)
                # completion_percentage_per_month: 100 = daily, 50 = every other day, etc.
                completion_pct = chore.completion_percentage_per_month

                # Calculate daily expected points for this chore
                # Formula: points * (completion_percentage / 100)
                daily_expected = chore.points * (completion_pct / 100)
                daily_points += daily_expected

            child_daily_points[child.id] = daily_points
            _LOGGER.warning(
                "CALC_COSTS: child=%s, chores_counted=%d, daily_points=%.2f",
                child.name, chores_counted, daily_points
            )

        # Calculate costs based on whether this is a jackpot reward
        if reward.is_jackpot:
            # Jackpot: sum of ALL children's daily points, same cost for everyone
            total_daily_points = sum(child_daily_points.values())
            jackpot_cost = max(1, round(total_daily_points * days_to_goal))
            _LOGGER.debug(
                "calculate_dynamic_reward_costs: jackpot total_daily=%.2f, cost=%d",
                total_daily_points, jackpot_cost
            )
            for child in assigned_children:
                result[child.id] = jackpot_cost
        else:
            # Non-jackpot: each child has their own cost based on their chores
            for child in assigned_children:
                daily_pts = child_daily_points.get(child.id, 0)
                if daily_pts > 0:
                    calculated = max(1, round(daily_pts * days_to_goal))
                    result[child.id] = calculated
                    _LOGGER.debug(
                        "calculate_dynamic_reward_costs: child=%s, daily=%.2f * days=%d = %d",
                        child.name, daily_pts, days_to_goal, calculated
                    )
                else:
                    result[child.id] = reward.cost  # Fall back to manual cost
                    _LOGGER.debug(
                        "calculate_dynamic_reward_costs: child=%s, no daily points, fallback to %d",
                        child.name, reward.cost
                    )

        _LOGGER.warning("CALC_COSTS: final result for %s = %s", reward.name, result)
        return result

    def get_child_daily_points(self, reward: Reward) -> dict[str, float]:
        """Get the daily expected points for each child assigned to a reward.

        This is used to calculate weighted contributions for jackpot rewards.
        Returns a dict mapping child_id to their daily expected points.
        """
        result: dict[str, float] = {}

        all_children = self.storage.get_children()
        all_chores = self.storage.get_chores()

        # Determine which children are assigned to this reward
        if reward.assigned_to:
            assigned_children = [c for c in all_children if c.id in reward.assigned_to]
        else:
            assigned_children = all_children

        if not assigned_children or not all_chores:
            return result

        for child in assigned_children:
            daily_points = 0.0

            for chore in all_chores:
                # Check if this chore is assigned to this child
                if chore.assigned_to and child.id not in chore.assigned_to:
                    continue

                completion_pct = chore.completion_percentage_per_month
                daily_expected = chore.points * (completion_pct / 100)
                daily_points += daily_expected

            result[child.id] = daily_points

        return result

    def calculate_dynamic_reward_cost(self, reward: Reward, child_id: str | None = None) -> int:
        """Calculate the dynamic cost of a reward.

        For backward compatibility. If child_id is provided, returns that child's cost.
        Otherwise returns the first child's cost or the manual cost.
        """
        costs = self.calculate_dynamic_reward_costs(reward)

        if child_id and child_id in costs:
            return costs[child_id]

        if costs:
            return list(costs.values())[0]

        return reward.cost

    async def async_add_reward(
        self,
        name: str,
        cost: int = 50,
        description: str = "",
        icon: str = "mdi:gift",
        assigned_to: list[str] | None = None,
        is_jackpot: bool = False,
        override_point_value: bool = False,
        days_to_goal: int = 30,
    ) -> Reward:
        """Add a new reward."""
        reward = Reward(
            name=name,
            cost=cost,
            description=description,
            icon=icon,
            assigned_to=assigned_to or [],
            is_jackpot=is_jackpot,
            override_point_value=override_point_value,
            days_to_goal=days_to_goal,
        )
        self.storage.add_reward(reward)
        await self.storage.async_save()
        await self.async_refresh()
        return reward

    async def async_update_reward(self, reward: Reward) -> None:
        """Update a reward."""
        self.storage.update_reward(reward)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_remove_reward(self, reward_id: str) -> None:
        """Remove a reward."""
        self.storage.remove_reward(reward_id)
        await self.storage.async_save()
        await self.async_refresh()

    def get_reward(self, reward_id: str) -> Reward | None:
        """Get a reward by ID."""
        return self.storage.get_reward(reward_id)

    # Chore completion operations
    async def _async_notify_pending_approval(self, child_name: str, chore_name: str, points: int) -> None:
        """Fire a persistent notification and optional notify service when approval is needed."""
        points_name = self.storage.get_points_name()
        message = f"{child_name} completed '{chore_name}' (+{points} {points_name}) and is waiting for your approval."

        # Always fire a persistent notification
        self.hass.async_create_task(
            self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "TaskMate — Approval Needed",
                    "message": message,
                    "notification_id": f"taskmate_approval_{child_name}_{chore_name}".replace(" ", "_").lower(),
                },
                blocking=False,
            )
        )

        # Fire optional notify service if configured
        notify_service = self.storage.get_setting("notify_service", "")
        if notify_service:
            # notify_service should be in format "notify.mobile_app_xxx"
            domain, service = notify_service.split(".", 1) if "." in notify_service else ("notify", notify_service)
            try:
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        domain,
                        service,
                        {
                            "title": "TaskMate ✅",
                            "message": message,
                        },
                        blocking=False,
                    )
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("TaskMate: failed to send notification via %s: %s", notify_service, err)

    async def async_complete_chore(self, chore_id: str, child_id: str) -> ChoreCompletion:
        """Mark a chore as completed by a child."""
        chore = self.get_chore(chore_id)
        if not chore:
            raise ValueError(f"Chore {chore_id} not found")

        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        # Check daily limit - count today's completions for this chore by this child
        # Both pending (unapproved) and approved completions count toward the limit
        now = dt_util.now()
        today = now.date()
        all_completions = self.storage.get_completions()
        todays_completions_count = 0
        for comp in all_completions:
            if comp.chore_id == chore_id and comp.child_id == child_id:
                # Convert to local timezone for date comparison
                comp_dt = comp.completed_at
                if hasattr(comp_dt, 'astimezone'):
                    comp_dt = dt_util.as_local(comp_dt)
                comp_date = comp_dt.date() if hasattr(comp_dt, 'date') else comp_dt
                if comp_date == today:
                    todays_completions_count += 1

        daily_limit = getattr(chore, 'daily_limit', 1)
        if todays_completions_count >= daily_limit:
            raise ValueError(
                f"Daily limit reached for chore '{chore.name}'. "
                f"Already completed {todays_completions_count} time(s) today (limit: {daily_limit})"
            )

        completion = ChoreCompletion(
            chore_id=chore_id,
            child_id=child_id,
            completed_at=now,
            approved=not chore.requires_approval,
            points_awarded=chore.points if not chore.requires_approval else 0,
        )

        # If no approval required, award points immediately
        if not chore.requires_approval:
            await self._award_points(child, chore.points)
            completion.approved = True
            completion.approved_at = dt_util.now()
            completion.points_awarded = chore.points

        self.storage.add_completion(completion)
        await self.storage.async_save()

        # Fire approval notification if chore requires parent sign-off
        if chore.requires_approval:
            await self._async_notify_pending_approval(child.name, chore.name, chore.points)

        await self.async_refresh()
        return completion

    async def async_approve_chore(self, completion_id: str) -> None:
        """Approve a chore completion."""
        completions = self.storage.get_completions()
        for completion in completions:
            if completion.id == completion_id:
                chore = self.get_chore(completion.chore_id)
                child = self.get_child(completion.child_id)

                if chore and child:
                    completion.approved = True
                    completion.approved_at = dt_util.now()
                    completion.points_awarded = chore.points
                    # Use completion date for weekend multiplier, not approval date
                    comp_date = dt_util.as_local(completion.completed_at).date()
                    await self._award_points(child, chore.points, completion_date=comp_date)
                    self.storage.update_completion(completion)
                    await self.storage.async_save()
                    await self.async_refresh()
                return

    async def async_reject_chore(self, completion_id: str) -> None:
        """Reject a chore completion and deduct points if they were already awarded."""
        completions = self.storage.get_completions()
        for completion in completions:
            if completion.id == completion_id:
                # If points were already awarded, deduct them
                if completion.points_awarded > 0:
                    child = self.get_child(completion.child_id)
                    if child:
                        child.points -= completion.points_awarded
                        # Ensure points don't go negative
                        if child.points < 0:
                            child.points = 0
                        self.storage.update_child(child)
                break

        self.storage.remove_completion(completion_id)
        await self.storage.async_save()
        await self.async_refresh()

    # Reward claim operations
    async def async_claim_reward(self, reward_id: str, child_id: str) -> RewardClaim:
        """Child claims a reward — creates a pending claim awaiting parent approval."""
        reward = self.get_reward(reward_id)
        if not reward:
            raise ValueError(f"Reward {reward_id} not found")

        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        # Get the effective cost for this child (dynamic or override)
        costs = self.calculate_dynamic_reward_costs(reward)
        effective_cost = costs.get(child_id, reward.cost)

        if child.points < effective_cost:
            raise ValueError(f"Not enough points. Need {effective_cost}, have {child.points}")

        # Points are NOT deducted here — they are deducted on parent approval
        # This mirrors the chore approval flow
        claim = RewardClaim(
            reward_id=reward_id,
            child_id=child_id,
            claimed_at=dt_util.now(),
        )

        self.storage.add_reward_claim(claim)
        await self.storage.async_save()
        await self.async_refresh()
        return claim

    async def async_approve_reward(self, claim_id: str) -> None:
        """Approve a reward claim and deduct points from the child."""
        claims = self.storage.get_reward_claims()
        for claim in claims:
            if claim.id == claim_id:
                reward = self.get_reward(claim.reward_id)
                child = self.get_child(claim.child_id)
                if not reward or not child:
                    raise ValueError(f"Reward or child not found for claim {claim_id}")

                # Deduct points now that parent has approved
                costs = self.calculate_dynamic_reward_costs(reward)
                effective_cost = costs.get(claim.child_id, reward.cost)

                if child.points < effective_cost:
                    raise ValueError(
                        f"Not enough points to approve. Need {effective_cost}, have {child.points}"
                    )

                child.points -= effective_cost
                self.storage.update_child(child)

                claim.approved = True
                claim.approved_at = dt_util.now()
                self.storage.update_reward_claim(claim)
                await self.storage.async_save()
                await self.async_refresh()
                return

    async def async_reject_reward(self, claim_id: str) -> None:
        """Reject a reward claim — no refund needed as points were never deducted."""
        self.storage._data["reward_claims"] = [
            c for c in self.storage._data.get("reward_claims", [])
            if c.get("id") != claim_id
        ]
        await self.storage.async_save()
        await self.async_refresh()

    # Points operations
    async def async_add_points(self, child_id: str, points: int, reason: str = "") -> None:
        """Add points to a child (bonus)."""
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")
        child.points += points
        child.total_points_earned += points
        self.storage.update_child(child)
        # Log the manual transaction
        transaction = PointsTransaction(
            child_id=child_id,
            points=points,
            reason=reason,
            created_at=dt_util.now(),
        )
        self.storage.add_points_transaction(transaction)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_remove_points(self, child_id: str, points: int, reason: str = "") -> None:
        """Remove points from a child (penalty)."""
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")
        actual_deducted = min(points, child.points)  # Can't go below 0
        child.points = max(0, child.points - points)
        self.storage.update_child(child)
        # Log the manual transaction (negative points)
        transaction = PointsTransaction(
            child_id=child_id,
            points=-actual_deducted,
            reason=reason,
            created_at=dt_util.now(),
        )
        self.storage.add_points_transaction(transaction)
        await self.storage.async_save()
        await self.async_refresh()

    # ── Bonus points constants ────────────────────────────────────────────────
    DEFAULT_STREAK_MILESTONES = "3:5, 7:10, 14:20, 30:50, 60:100, 100:200"

    @staticmethod
    def parse_milestone_setting(value: str) -> dict[int, int]:
        """Parse 'days:points, days:points' string into {days: points} dict."""
        if not value or not value.strip():
            return {}
        result = {}
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue
            if ":" not in part:
                raise ValueError(
                    f"Invalid format '{part}' — use 'days:points' pairs, e.g. '7:10, 14:20'"
                )
            days_str, points_str = part.split(":", 1)
            try:
                days = int(days_str.strip())
                points = int(points_str.strip())
            except ValueError:
                raise ValueError(
                    f"Invalid numbers in '{part}' — days and points must be whole numbers"
                )
            if days < 1:
                raise ValueError(f"Days must be at least 1, got {days}")
            if points < 1:
                raise ValueError(f"Points must be at least 1, got {points}")
            if days in result:
                raise ValueError(f"Duplicate milestone for {days} days")
            result[days] = points
        return result

    async def _award_points(
        self,
        child: Child,
        points: int,
        completion_date: date | None = None,
    ) -> None:
        """Award points to a child, update streak, and apply bonus systems."""
        now = dt_util.now()
        today = now.date()
        effective_date = completion_date or today
        today_str = today.isoformat()
        last_date_str = getattr(child, 'last_completion_date', None)

        # ── Weekend multiplier ──────────────────────────────────────────────
        # Applied to base chore points only, based on completion date
        try:
            multiplier = float(self.storage.get_setting("weekend_multiplier", "2.0"))
        except (ValueError, TypeError):
            multiplier = 2.0

        weekend_bonus = 0
        if effective_date.weekday() in (5, 6) and multiplier > 1.0:
            weekend_bonus = round(points * (multiplier - 1.0))

        total_points = points + weekend_bonus
        child.points += total_points
        child.total_points_earned += total_points
        child.total_chores_completed += 1

        if weekend_bonus > 0:
            _LOGGER.info(
                "Weekend multiplier (%.1fx) applied for %s: +%d bonus on top of %d",
                multiplier, child.name, weekend_bonus, points,
            )
            # Log weekend bonus as a separate transaction for activity history
            transaction = PointsTransaction(
                child_id=child.id,
                points=weekend_bonus,
                reason=f"Weekend bonus (×{multiplier:.0f})",
                created_at=now,
            )
            self.storage.add_points_transaction(transaction)

        # ── Streak tracking ─────────────────────────────────────────────────
        streak_mode = self.storage.get_setting("streak_reset_mode", "reset")
        streak_paused = getattr(child, "streak_paused", False)
        streak_before = child.current_streak or 0
        streak_reset_occurred = False

        if last_date_str is None:
            child.current_streak = 1
            child.streak_paused = False
        elif last_date_str == today_str:
            pass  # Already completed today — streak unchanged
        else:
            try:
                last_date = date.fromisoformat(last_date_str)
                yesterday = today - timedelta(days=1)
                if last_date == yesterday:
                    child.current_streak = streak_before + 1
                    child.streak_paused = False
                elif streak_mode == "pause" or streak_paused:
                    child.streak_paused = False
                    _LOGGER.debug("Streak resumed for %s at %d", child.name, child.current_streak)
                else:
                    child.current_streak = 1
                    child.streak_paused = False
                    streak_reset_occurred = True
            except (ValueError, TypeError):
                child.current_streak = 1
                child.streak_paused = False
                streak_reset_occurred = True

        child.last_completion_date = today_str

        if child.current_streak > (child.best_streak or 0):
            child.best_streak = child.current_streak

        # ── Streak milestone bonus ──────────────────────────────────────────
        milestones_enabled = self.storage.get_setting("streak_milestones_enabled", "true") == "true"
        if milestones_enabled and child.current_streak > 0:
            # Parse custom milestone config
            milestone_setting = self.storage.get_setting(
                "streak_milestones", self.DEFAULT_STREAK_MILESTONES
            )
            try:
                milestones = self.parse_milestone_setting(milestone_setting)
            except ValueError:
                milestones = self.parse_milestone_setting(self.DEFAULT_STREAK_MILESTONES)

            # Clear milestones on reset so kids can re-earn them
            if streak_reset_occurred:
                child.streak_milestones_achieved = []

            achieved = set(child.streak_milestones_achieved or [])
            milestone_bonus = 0
            for days, bonus_pts in milestones.items():
                if child.current_streak >= days and days not in achieved:
                    milestone_bonus += bonus_pts
                    achieved.add(days)
                    _LOGGER.info(
                        "Streak milestone %d days reached for %s: +%d bonus",
                        days, child.name, bonus_pts,
                    )

            child.streak_milestones_achieved = sorted(achieved)

            if milestone_bonus > 0:
                child.points += milestone_bonus
                child.total_points_earned += milestone_bonus
                transaction = PointsTransaction(
                    child_id=child.id,
                    points=milestone_bonus,
                    reason=f"Streak milestone bonus ({child.current_streak} day streak!)",
                    created_at=now,
                )
                self.storage.add_points_transaction(transaction)

        self.storage.update_child(child)

    async def async_prune_history(self, days: int = 90) -> None:
        """Prune completion history older than specified days."""
        cutoff = dt_util.now() - timedelta(days=days)
        all_completions = self.storage.get_completions()
        before = len(all_completions)

        # Keep completions newer than cutoff OR unapproved (pending)
        to_keep = [
            c for c in all_completions
            if c.completed_at >= cutoff or not c.approved
        ]

        if len(to_keep) < before:
            self.storage._data["completions"] = [c.to_dict() for c in to_keep]
            await self.storage.async_save()
            await self.async_refresh()
            _LOGGER.info(
                "Pruned %d completions older than %d days",
                before - len(to_keep), days
            )

    # Child chore order operations
    async def async_set_chore_order(self, child_id: str, chore_order: list[str]) -> None:
        """Set the chore order for a child."""
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        child.chore_order = chore_order
        self.storage.update_child(child)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_set_setting(self, key: str, value: str) -> None:
        """Update a generic setting."""
        self.storage.set_setting(key, value)
        await self.storage.async_save()
        await self.async_refresh()

    # Settings
    async def async_set_points_settings(self, name: str, icon: str) -> None:
        """Update points settings."""
        self.storage.set_points_name(name)
        self.storage.set_points_icon(icon)
        await self.storage.async_save()
        await self.async_refresh()
