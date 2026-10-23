"""Reward fulfilment tracker (#1098): a redeemed reward stays owed until it is handed over.

Approving a claim spends the points; nothing used to record whether the
child ever got the thing. With ``reward_fulfilment_enabled`` on, every claim
approved for a reward a person has to hand over is marked ``needs_delivery``
and sits in the owed list until a parent marks it delivered (approvals card,
parent dashboard, panel Today page) or the child taps "Got it!" on their own
card. Parents are reminded after ``reward_fulfilment_reminder_days`` days,
and again every that-many days while it stays owed (0 = never).

Rewards the system fulfils on its own — streak freezes and timed unlocks —
and wishlist redemptions, which have their own hand-over step, are never
tracked. Claims approved while the tracker was off are not back-filled when
it is turned on.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_REWARD_FULFILMENT_REMINDER_DAYS,
    NOTIF_TYPE_REWARD_OWED,
    REWARD_FULFILMENT_REMINDER_MAX_DAYS,
)

_LOGGER = logging.getLogger(__name__)


class FulfilmentMixin:
    """Owed rewards and the hand-over step."""

    def reward_fulfilment_enabled(self) -> bool:
        v = self.storage.get_setting("reward_fulfilment_enabled", False)
        return v is True or str(v).lower() == "true"

    def reward_fulfilment_reminder_days(self) -> int:
        raw = self.storage.get_setting("reward_fulfilment_reminder_days", DEFAULT_REWARD_FULFILMENT_REMINDER_DAYS)
        try:
            days = int(raw)
        except (TypeError, ValueError):
            return 0
        return max(0, min(REWARD_FULFILMENT_REMINDER_MAX_DAYS, days))

    @staticmethod
    def reward_needs_delivery(reward) -> bool:
        """True for a reward a person has to hand over (not one TaskMate grants itself)."""
        if reward is None:
            return False
        if getattr(reward, "streak_freeze", False) or getattr(reward, "screen_minutes", 0):
            return False
        return not getattr(reward, "unlock_entity", "")

    def _track_fulfilment(self, claim, reward) -> None:
        """Called by the reward approval path once the claim is approved."""
        if self.reward_fulfilment_enabled() and self.reward_needs_delivery(reward):
            claim.needs_delivery = True

    def _owed_claims(self) -> list:
        if not self.reward_fulfilment_enabled():
            return []
        return [
            c
            for c in self.storage.get_reward_claims()
            if c.approved and getattr(c, "needs_delivery", False) and c.delivered_at is None
        ]

    def owed_rewards(self, child_id: str | None = None) -> list[dict[str, Any]]:
        """Approved rewards still to be handed over, oldest first.

        Each entry is what a card needs to draw the row and mark it done; the
        child's face comes from the overview's children list, not from here.
        A gift is owed to its recipient, and carries the buyer's name.
        """
        now = dt_util.now()
        out: list[dict[str, Any]] = []
        for claim in self._owed_claims():
            if child_id and claim.holder_id != child_id:
                continue
            child = self.get_child(claim.holder_id)
            reward = self.get_reward(claim.reward_id)
            if child is None or reward is None:
                continue
            since = claim.approved_at or claim.claimed_at
            days = max(0, (dt_util.as_local(now).date() - dt_util.as_local(since).date()).days)
            out.append(
                {
                    "claim_id": claim.id,
                    "child_id": child.id,
                    "child_name": child.name,
                    "reward_id": reward.id,
                    "reward_name": reward.name,
                    "reward_icon": reward.icon or "mdi:gift",
                    "cost": claim.approved_cost if claim.approved_cost is not None else reward.cost,
                    "approved_at": since.isoformat(),
                    "days_owed": days,
                }
            )
            if claim.recipient_id and (buyer := self.get_child(claim.child_id)):
                out[-1]["from_name"] = buyer.name
        out.sort(key=lambda o: o["approved_at"])
        return out

    async def async_mark_reward_delivered(self, claim_id: str, by: str = "parent", child_id: str | None = None) -> None:
        """Hand-over done. ``by`` is "parent" or "child"; a child may only confirm their own."""
        claim = next((c for c in self.storage.get_reward_claims() if c.id == claim_id), None)
        if claim is None or not claim.approved or not getattr(claim, "needs_delivery", False):
            raise ValueError("That reward is not waiting to be handed over.")
        if claim.delivered_at is not None:
            raise ValueError("That reward has already been marked as delivered.")
        if by == "child" and child_id != claim.holder_id:
            child = self.get_child(claim.holder_id)
            name = child.name if child else "someone else"
            raise ValueError(f"That reward belongs to {name}.")
        now = dt_util.now()
        claim.delivered_at = now
        claim.delivered_by = "child" if by == "child" else "parent"
        self.storage.update_reward_claim(claim)
        await self.storage.async_save()
        if getattr(self, "notifications", None):
            await self.notifications.clear_approval(NOTIF_TYPE_REWARD_OWED, claim.id)
        child = self.get_child(claim.holder_id)
        reward = self.get_reward(claim.reward_id)
        self.hass.bus.async_fire(
            "taskmate_reward_delivered",
            {
                "child_id": claim.holder_id,
                "child_name": getattr(child, "name", ""),
                "reward_id": claim.reward_id,
                "reward_name": getattr(reward, "name", ""),
                "claim_id": claim.id,
                "delivered_by": claim.delivered_by,
                "timestamp": now.isoformat(),
            },
        )
        await self.async_refresh()

    async def async_check_owed_rewards(self, refresh: bool = False) -> int:
        """Remind the parents about rewards owed for N days or more. Idempotent per period.

        Runs from the minutely tick. Returns how many reminders went out.
        """
        days = self.reward_fulfilment_reminder_days()
        if not days:
            return 0
        now = dt_util.now()
        gap = timedelta(days=days)
        sent = 0
        for claim in self._owed_claims():
            since = claim.approved_at or claim.claimed_at
            if now - since < gap:
                continue
            last = claim.owed_reminded_at
            if last is not None and now - last < gap:
                continue
            child = self.get_child(claim.holder_id)
            reward = self.get_reward(claim.reward_id)
            if child is None or reward is None:
                continue
            claim.owed_reminded_at = now
            self.storage.update_reward_claim(claim)
            await self.storage.async_save()
            await self.notifications.fire(
                NOTIF_TYPE_REWARD_OWED,
                {
                    "child_id": child.id,
                    "child_name": child.name,
                    "reward_id": reward.id,
                    "reward_name": reward.name,
                    "claim_id": claim.id,
                    "entry_id": claim.id,
                    "days": (dt_util.as_local(now).date() - dt_util.as_local(since).date()).days,
                    "points_name": self.storage.get_points_name(),
                },
            )
            sent += 1
        if sent and refresh:
            await self.async_refresh()
        return sent
