"""Daily / weekly challenges mixin for TaskMateCoordinator.

A challenge sets a per-period target — complete N chores today, or earn N
points this week — and awards a one-off bonus when a child hits it. Progress
and the award reset automatically when the period rolls over (a new day or a
new Monday-anchored week).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.util import dt as dt_util

from .models import Challenge, PointsTransaction

_LOGGER = logging.getLogger(__name__)


class ChallengesMixin:
    """Mixin providing challenge CRUD and per-period evaluation."""

    # ── CRUD ─────────────────────────────────────────────────────────────
    async def async_create_challenge(self, **fields) -> str:
        challenge = Challenge.from_dict(fields)
        if not challenge.name.strip():
            raise ValueError("Challenge name is required")
        if challenge.target <= 0:
            raise ValueError("Target must be at least 1")
        self.storage.add_challenge(challenge)
        await self.storage.async_save()
        await self.async_refresh()
        return challenge.id

    async def async_update_challenge(self, challenge_id: str, **fields) -> None:
        existing = self.storage.get_challenge(challenge_id)
        if not existing:
            raise ValueError(f"Challenge {challenge_id} not found")
        data = existing.to_dict()
        data.update(fields)
        data["id"] = challenge_id
        updated = Challenge.from_dict(data)
        if updated.target <= 0:
            raise ValueError("Target must be at least 1")
        self.storage.update_challenge(updated)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_delete_challenge(self, challenge_id: str) -> None:
        if not self.storage.get_challenge(challenge_id):
            raise ValueError(f"Challenge {challenge_id} not found")
        self.storage.remove_challenge(challenge_id)
        await self.storage.async_save()
        await self.async_refresh()

    # ── Period helpers ───────────────────────────────────────────────────
    def _challenge_applies_to(self, challenge: Challenge, child_id: str) -> bool:
        return not challenge.assigned_to or child_id in challenge.assigned_to

    def _period_start_key(self, scope: str):
        """Return (period_start_date, period_key) for the current period."""
        today = dt_util.now().date()
        if scope == "weekly":
            start = today - timedelta(days=today.weekday())
            return start, f"w:{start.isoformat()}"
        return today, f"d:{today.isoformat()}"

    def _metric_value(self, child_id: str, scope: str, metric: str) -> int:
        """Child's current metric value within the active period."""
        start, _ = self._period_start_key(scope)
        count = 0
        points = 0
        for comp in self.storage.get_completions():
            if comp.child_id != child_id or not comp.approved or comp.bonus_subtask_id:
                continue
            if dt_util.as_local(comp.completed_at).date() < start:
                continue
            count += 1
            points += comp.points_awarded or 0
        return points if metric == "points" else count

    def challenge_progress_for_child(self, child_id: str) -> list[dict]:
        """Snapshot of every active challenge assigned to ``child_id``."""
        out: list[dict] = []
        for ch in self.storage.get_challenges():
            if not ch.active or not self._challenge_applies_to(ch, child_id):
                continue
            value = self._metric_value(child_id, ch.scope, ch.metric)
            _, period_key = self._period_start_key(ch.scope)
            prog = self.storage.get_challenge_child_progress(ch.id, child_id)
            awarded = bool(prog.get("awarded")) and prog.get("period") == period_key
            out.append(
                {
                    "challenge_id": ch.id,
                    "name": ch.name,
                    "icon": ch.icon,
                    "scope": ch.scope,
                    "metric": ch.metric,
                    "target": ch.target,
                    "progress": min(value, ch.target),
                    "value": value,
                    "bonus_points": ch.bonus_points,
                    "complete": value >= ch.target,
                    "awarded": awarded,
                }
            )
        return out

    # ── Evaluation ───────────────────────────────────────────────────────
    async def _async_evaluate_challenges(self, child_id: str) -> None:
        """Award any challenge the child has now met for the current period."""
        child = self.get_child(child_id)
        if not child:
            return
        changed = False
        for ch in self.storage.get_challenges():
            if not ch.active or ch.target <= 0:
                continue
            if not self._challenge_applies_to(ch, child_id):
                continue
            _, period_key = self._period_start_key(ch.scope)
            prog = dict(self.storage.get_challenge_child_progress(ch.id, child_id))
            # New period → clear any stale award flag.
            if prog.get("period") != period_key:
                prog = {"period": period_key, "awarded": False}
            if prog.get("awarded"):
                continue
            value = self._metric_value(child_id, ch.scope, ch.metric)
            if value < ch.target:
                self.storage.set_challenge_child_progress(ch.id, child_id, prog)
                continue
            prog["awarded"] = True
            self.storage.set_challenge_child_progress(ch.id, child_id, prog)
            await self._award_challenge(ch, child)
            changed = True

        if changed:
            await self.storage.async_save()
            await self.async_refresh()

    async def _award_challenge(self, challenge: Challenge, child) -> None:
        bonus = int(challenge.bonus_points or 0)
        if bonus > 0:
            child.points += bonus
            child.total_points_earned += bonus
            child.career_score = child.total_points_earned - child.total_penalties_received
            self.storage.add_points_transaction(
                PointsTransaction(
                    child_id=child.id,
                    points=bonus,
                    reason=f"Challenge complete: {challenge.name}",
                    created_at=dt_util.now(),
                )
            )
            if hasattr(self, "_maybe_level_up"):
                await self._maybe_level_up(child)
            self.storage.update_child(child)

        self.hass.bus.async_fire(
            "taskmate_challenge_completed",
            {
                "child_id": child.id,
                "child_name": child.name,
                "challenge_id": challenge.id,
                "challenge_name": challenge.name,
                "scope": challenge.scope,
                "bonus": bonus,
                "timestamp": dt_util.now().isoformat(),
            },
        )
        if hasattr(self, "_celebrate"):
            await self._celebrate(
                child,
                "challenge_completed",
                f"{child.name} completed the challenge '{challenge.name}'!",
                tier=2,
                extra={"challenge_id": challenge.id, "bonus": bonus},
            )
        _LOGGER.info("Challenge '%s' completed by %s (+%d)", challenge.name, child.name, bonus)
