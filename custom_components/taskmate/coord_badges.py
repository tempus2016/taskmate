"""Badge evaluation engine and built-in catalogue."""
from __future__ import annotations

import logging

from .models import Badge, BadgeCriterion, Child

_LOGGER = logging.getLogger(__name__)


def _b(id_suffix: str, name: str, description: str, icon: str, tier: str,
       point_bonus: int, metric: str, value: int) -> Badge:
    """Helper to build a built-in badge."""
    criteria = [BadgeCriterion(metric=metric, operator=">=", value=value)] if metric else []
    badge = Badge(
        name=name,
        description=description,
        icon=icon,
        tier=tier,
        point_bonus=point_bonus,
        criteria=criteria,
        builtin=True,
        enabled=True,
        notify_on_earn=True,
    )
    badge.id = f"builtin.{id_suffix}"
    return badge


BUILTIN_CATALOGUE: list[Badge] = [
    # Bronze
    _b("first_chore", "First Chore", "Complete your very first chore",
       "mdi:check-circle", "bronze", 0, "first_chore", 1),
    _b("first_reward", "First Reward", "Claim your first reward",
       "mdi:gift", "bronze", 0, "first_reward", 1),
    _b("100_points", "100 Points", "Earn 100 lifetime points",
       "mdi:star", "bronze", 0, "total_points", 100),
    _b("10_chores", "10 Chores Completed", "Complete 10 chores",
       "mdi:checkbox-marked-circle", "bronze", 0, "total_chores", 10),
    # Silver
    _b("500_points", "500 Points", "Earn 500 lifetime points",
       "mdi:star-circle", "silver", 25, "total_points", 500),
    _b("50_chores", "50 Chores Completed", "Complete 50 chores",
       "mdi:checkbox-multiple-marked-circle", "silver", 25, "total_chores", 50),
    _b("3_day_streak", "3-Day Streak", "Complete chores 3 days in a row",
       "mdi:fire", "silver", 25, "current_streak", 3),
    _b("first_perfect_week", "First Perfect Week", "Complete a perfect week",
       "mdi:calendar-star", "silver", 50, "perfect_weeks", 1),
    # Gold
    _b("1000_points", "1000 Points", "Earn 1000 lifetime points",
       "mdi:trophy", "gold", 100, "total_points", 1000),
    _b("100_chores", "100 Chores Completed", "Complete 100 chores",
       "mdi:trophy-variant", "gold", 100, "total_chores", 100),
    _b("7_day_streak", "7-Day Streak", "Complete chores 7 days in a row",
       "mdi:lightning-bolt", "gold", 50, "current_streak", 7),
    _b("5_perfect_weeks", "5 Perfect Weeks", "Achieve 5 perfect weeks",
       "mdi:calendar-multiple-check", "gold", 100, "perfect_weeks", 5),
    # Platinum
    _b("5000_points", "5000 Points", "Earn 5000 lifetime points",
       "mdi:diamond-stone", "platinum", 250, "total_points", 5000),
    _b("30_day_streak", "30-Day Streak", "Complete chores 30 days in a row",
       "mdi:crown", "platinum", 250, "current_streak", 30),
    _b("10_perfect_weeks", "10 Perfect Weeks", "Achieve 10 perfect weeks",
       "mdi:rainbow", "platinum", 250, "perfect_weeks", 10),
]


def resolve_metric(metric: str, child: Child, storage) -> int:
    """Resolve a metric value for a child. Returns int (0 for unknown metrics)."""
    if metric == "total_points":
        return int(child.total_points_earned or 0)
    if metric == "total_chores":
        return int(child.total_chores_completed or 0)
    if metric == "current_streak":
        return int(child.current_streak or 0)
    if metric == "best_streak":
        return int(child.best_streak or 0)
    if metric == "perfect_weeks":
        return len(child.awarded_perfect_weeks or [])
    if metric == "first_chore":
        return 1 if (child.total_chores_completed or 0) >= 1 else 0
    if metric in ("total_rewards", "first_reward"):
        approved_count = sum(
            1 for c in storage.get_reward_claims()
            if c.child_id == child.id and c.approved
        )
        if metric == "first_reward":
            return 1 if approved_count >= 1 else 0
        return approved_count
    return 0


TRIGGER_METRICS: dict[str, set[str]] = {
    "chore_completed": {"total_chores", "first_chore"},
    "points_changed": {"total_points"},
    "reward_redeemed": {"total_rewards", "first_reward"},
    "streak_updated": {"current_streak", "best_streak"},
    "perfect_week": {"perfect_weeks"},
}


def criterion_met(value: int, operator: str, threshold: int) -> bool:
    """Evaluate a single badge criterion. Unknown operators default to >=."""
    op = operator or ">="
    if op == ">=":
        return value >= threshold
    if op == "==":
        return value == threshold
    if op == "<=":
        return value <= threshold
    if op == ">":
        return value > threshold
    if op == "<":
        return value < threshold
    if op == "!=":
        return value != threshold
    return value >= threshold


def badge_relevant_to_trigger(badge: Badge, trigger: str) -> bool:
    """Return True if any of the badge's criteria reference a metric in the trigger's set.

    'manual' trigger always returns True (re-evaluates everything).
    Badges with no criteria are manual-award-only and never auto-fire.
    """
    if trigger == "manual":
        return True
    if not badge.criteria:
        return False
    relevant = TRIGGER_METRICS.get(trigger, set())
    return any(c.metric in relevant for c in badge.criteria)


class BadgeCoordinator:
    """Evaluates badge criteria and emits awards."""

    def __init__(self, hass, storage, points_coord, notifications=None) -> None:
        self.hass = hass
        self.storage = storage
        self.points_coord = points_coord
        self.notifications = notifications

    async def evaluate_for_child(
        self,
        child_id: str,
        trigger: str,
        *,
        silent: bool = False,
    ) -> list:
        """Evaluate all enabled badges for this child given a trigger event.

        Returns the list of newly-created AwardedBadge instances.
        Set silent=True for retroactive backfill (suppresses notifications,
        events, and point bonuses).
        """
        from .models import AwardedBadge

        child = self.storage.get_child(child_id)
        if child is None:
            return []

        new_awards: list[AwardedBadge] = []

        for badge in self.storage.get_badges():
            if not badge.enabled:
                continue
            if badge.assigned_to and child_id not in badge.assigned_to:
                continue
            if not badge_relevant_to_trigger(badge, trigger):
                continue
            if self.storage.has_awarded(child_id, badge.id):
                continue
            if not badge.criteria:
                continue
            results = [
                criterion_met(resolve_metric(c.metric, child, self.storage), c.operator, c.value)
                for c in badge.criteria
            ]
            combinator = (getattr(badge, "combinator", "AND") or "AND").upper()
            passed = any(results) if combinator == "OR" else all(results)
            if not passed:
                continue

            bonus = 0 if silent else badge.point_bonus
            award = AwardedBadge(
                child_id=child_id,
                badge_id=badge.id,
                silent=silent,
                bonus_credited=bonus,
            )
            self.storage.add_awarded_badge(award)
            new_awards.append(award)

            if not silent:
                if bonus > 0:
                    await self.points_coord.async_add_points(
                        child_id,
                        bonus,
                        reason=f"Badge: {badge.name}",
                    )
                self.hass.bus.async_fire(
                    "taskmate_badge_earned",
                    {
                        "child_id": child_id,
                        "badge_id": badge.id,
                        "awarded_id": award.id,
                        "name": badge.name,
                        "icon": badge.icon,
                        "tier": badge.tier,
                        "point_bonus": bonus,
                    },
                )

        if new_awards:
            await self.storage.async_save()
            if not silent:
                await self._dispatch_notifications(new_awards)

        return new_awards

    async def award_manually(self, child_id: str, badge_id: str):
        """Manually award a badge to a child via parent action."""
        from .models import AwardedBadge

        child = self.storage.get_child(child_id)
        badge = self.storage.get_badge(badge_id)
        if child is None or badge is None:
            return None
        if self.storage.has_awarded(child_id, badge_id):
            return None

        bonus = badge.point_bonus
        award = AwardedBadge(
            child_id=child_id,
            badge_id=badge_id,
            manually_awarded=True,
            silent=False,
            bonus_credited=bonus,
        )
        self.storage.add_awarded_badge(award)
        if bonus > 0:
            await self.points_coord.async_add_points(
                child_id, bonus, reason=f"Badge: {badge.name}",
            )
        self.hass.bus.async_fire(
            "taskmate_badge_earned",
            {
                "child_id": child_id,
                "badge_id": badge_id,
                "awarded_id": award.id,
                "name": badge.name,
                "icon": badge.icon,
                "tier": badge.tier,
                "point_bonus": bonus,
            },
        )
        await self._dispatch_notifications([award])
        await self.storage.async_save()
        return award

    async def revoke(self, awarded_id: str) -> bool:
        """Revoke an awarded badge; reverse bonus_credited if > 0."""
        matching = [
            a for a in self.storage.get_awarded_badges() if a.id == awarded_id
        ]
        if not matching:
            return False
        award = matching[0]
        badge = self.storage.get_badge(award.badge_id)
        badge_name = badge.name if badge else "(removed)"

        self.storage.remove_awarded_badge(awarded_id)
        if award.bonus_credited > 0:
            await self.points_coord.async_remove_points(
                award.child_id,
                award.bonus_credited,
                reason=f"Badge revoked: {badge_name}",
            )
        await self.storage.async_save()
        return True

    async def rebuild_all(self) -> int:
        """Re-evaluate all enabled badges across all children, silently.

        Used by rebuild_badges service and one-time backfill.
        Returns total count of new silent awards.
        """
        total = 0
        for child in self.storage.get_children():
            new_awards = await self.evaluate_for_child(
                child.id, "manual", silent=True,
            )
            total += len(new_awards)
        return total

    async def _dispatch_notifications(self, awards: list) -> None:
        """Combine awards into one or per-badge ping(s) via the central dispatcher.

        Per-badge `notify_on_earn` still applies — badges with that flag off are
        excluded from the message but their event is still emitted by the badge
        coordinator's regular bus.fire.
        """
        per_child: dict[str, list] = {}
        for award in awards:
            badge = self.storage.get_badge(award.badge_id)
            if not badge or not badge.notify_on_earn:
                continue
            per_child.setdefault(award.child_id, []).append(badge)

        for child_id, badges in per_child.items():
            child = self.storage.get_child(child_id)
            if child is None or self.notifications is None:
                continue
            badge_name = badges[0].name if len(badges) == 1 else ", ".join(b.name for b in badges)
            await self.notifications.fire(
                "badge_earned",
                {
                    "child_name": child.name,
                    "badge_name": badge_name,
                    "badge_id": ",".join(b.id for b in badges),
                    "tier": badges[0].tier,
                },
            )
