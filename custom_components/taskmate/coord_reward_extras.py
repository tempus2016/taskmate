"""Reward extras: per-child limits, gifts between children, star ratings and the savings forecast.

Per-child limit: a reward may carry ``limit_count`` claims per
``limit_period`` (day, week from Monday, or month) for each child. Pending
and approved claims made inside the current period count; a rejected claim
is deleted, so it never does. A gift counts against the child it is for.

Gifts: with ``reward_gifting_enabled`` on, a child may buy a reward for a
brother or sister. The buyer's ``child_id`` is on the claim and pays as on
any claim; ``recipient_id`` is who gets it. Everything that hands the reward
over — screen-time minutes, a timed unlock, the owed list, "Got it!", the
rating — follows the recipient. Shared jackpots, savings-jar (pool) rewards
and streak freezes can't be gifted: their points or tokens belong to the
child who saved them.

Ratings: once a reward is handed over (or approved, when fulfilment
tracking is off) the child it was for can give it 1-3 stars from their card
for ``REWARD_RATING_DAYS`` days.

Savings forecast: each child's average daily earning over the last
``EARN_RATE_DAYS`` days, so a card can say when the next reward is in reach.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

REWARD_RATING_DAYS = 3
EARN_RATE_DAYS = 14
# Positive transactions that hand points back rather than earn new ones.
_NOT_EARNINGS = ("Pool refund", "Wish", "Gift from", "Raffle called off")


def reward_limit_window(period: str, today: date) -> tuple[date, date]:
    """The first day of the current limit period and the first day of the next one."""
    if period == "day":
        return today, today + timedelta(days=1)
    if period == "month":
        start = today.replace(day=1)
        nxt = (start + timedelta(days=32)).replace(day=1)
        return start, nxt
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=7)


class RewardExtrasMixin:
    """Limits, gifts, ratings and the earning rate."""

    # ── gifts ────────────────────────────────────────────────────────────

    def reward_gifting_enabled(self) -> bool:
        v = self.storage.get_setting("reward_gifting_enabled", False)
        return v is True or str(v).lower() == "true"

    def validate_reward_gift(self, reward, buyer, recipient_id: str):
        """Check a gift may go to ``recipient_id``; returns the recipient."""
        if not self.reward_gifting_enabled():
            raise ValueError("Buying rewards for each other is switched off")
        recipient = self.get_child(recipient_id)
        if recipient is None:
            raise ValueError(f"Child {recipient_id} not found")
        if getattr(recipient, "is_adult", False):
            raise ValueError("Rewards can only be bought for children")
        if not self._reward_is_for_child(reward, recipient.id):
            raise ValueError(f"Reward '{reward.name}' is not available to {recipient.name}")
        if reward.is_jackpot or reward.pool_enabled or getattr(reward, "streak_freeze", False):
            raise ValueError(f"'{reward.name}' can't be bought for someone else")
        return recipient

    def incoming_gifts(self, child_id: str) -> list[dict[str, Any]]:
        """Gifts bought for this child that are still waiting for approval."""
        out = []
        for claim in self.storage.get_pending_reward_claims():
            if claim.recipient_id != child_id:
                continue
            buyer = self.get_child(claim.child_id)
            reward = self.get_reward(claim.reward_id)
            if buyer is None or reward is None:
                continue
            out.append(
                {
                    "claim_id": claim.id,
                    "reward_name": reward.name,
                    "reward_icon": reward.icon or "mdi:gift",
                    "from_name": buyer.name,
                }
            )
        return out

    # ── per-child limit ──────────────────────────────────────────────────

    def reward_limit_next(self, reward, holder_id: str, claims: list | None = None) -> date | None:
        """The day ``holder_id`` may have this reward again, or None if they still can now."""
        count = int(getattr(reward, "limit_count", 0) or 0)
        if count <= 0:
            return None
        today = dt_util.as_local(dt_util.now()).date()
        start, nxt = reward_limit_window(getattr(reward, "limit_period", "week"), today)
        if claims is None:
            claims = self.storage.get_reward_claims()
        used = sum(
            1
            for c in claims
            if c.reward_id == reward.id
            and c.holder_id == holder_id
            and not c.wish_id
            and dt_util.as_local(c.claimed_at).date() >= start
        )
        return nxt if used >= count else None

    def require_reward_limit(self, reward, holder) -> None:
        """Raise a clear error when the child has used this period's claims."""
        nxt = self.reward_limit_next(reward, holder.id)
        if nxt is None:
            return
        period = {"day": "day", "month": "month"}.get(reward.limit_period, "week")
        times = "once" if reward.limit_count == 1 else f"{reward.limit_count} times"
        raise ValueError(
            f"{holder.name} can have '{reward.name}' {times} a {period}. It's available again on {nxt.isoformat()}"
        )

    def reward_limit_blocks(self, reward, claims: list) -> dict[str, str]:
        """``{child_id: ISO date it opens again}`` for each child at the limit."""
        if int(getattr(reward, "limit_count", 0) or 0) <= 0:
            return {}
        out = {}
        for holder in {c.holder_id for c in claims if c.reward_id == reward.id}:
            nxt = self.reward_limit_next(reward, holder, claims)
            if nxt is not None:
                out[holder] = nxt.isoformat()
        return out

    # ── ratings ──────────────────────────────────────────────────────────

    @staticmethod
    def _rating_opened_at(claim) -> datetime | None:
        """When the child got the reward: handed over, or approved if untracked."""
        if not claim.approved or claim.wish_id:
            return None
        if getattr(claim, "needs_delivery", False):
            return claim.delivered_at
        return claim.approved_at

    def rewards_to_rate(self, child_id: str) -> list[dict[str, Any]]:
        """Recent rewards this child has had and not yet rated, newest first."""
        now = dt_util.now()
        out = []
        for claim in self.storage.get_reward_claims():
            if claim.holder_id != child_id or claim.rating:
                continue
            opened = self._rating_opened_at(claim)
            if opened is None or now - opened > timedelta(days=REWARD_RATING_DAYS):
                continue
            reward = self.get_reward(claim.reward_id)
            if reward is None:
                continue
            out.append(
                {
                    "claim_id": claim.id,
                    "reward_name": reward.name,
                    "reward_icon": reward.icon or "mdi:gift",
                    "_at": opened,
                }
            )
        out.sort(key=lambda r: r.pop("_at"), reverse=True)
        return out[:3]

    async def async_rate_reward(self, claim_id: str, child_id: str, stars: int) -> None:
        """The child gives a reward they've had 1-3 stars. Once only."""
        stars = int(stars)
        if not 1 <= stars <= 3:
            raise ValueError("Pick 1 to 3 stars")
        claim = next((c for c in self.storage.get_reward_claims() if c.id == claim_id), None)
        if claim is None or self._rating_opened_at(claim) is None:
            raise ValueError("That reward can't be rated yet")
        if claim.holder_id != child_id:
            raise ValueError("Only the child who had the reward can rate it")
        if claim.rating:
            raise ValueError("That reward has already been rated")
        claim.rating = stars
        self.storage.update_reward_claim(claim)
        await self.storage.async_save()
        child = self.get_child(child_id)
        reward = self.get_reward(claim.reward_id)
        self.hass.bus.async_fire(
            "taskmate_reward_rated",
            {
                "child_id": child_id,
                "child_name": getattr(child, "name", ""),
                "reward_id": claim.reward_id,
                "reward_name": getattr(reward, "name", ""),
                "claim_id": claim.id,
                "rating": stars,
                "timestamp": dt_util.now().isoformat(),
            },
        )
        await self.async_refresh()

    # ── savings forecast ─────────────────────────────────────────────────

    def earn_rates(self) -> dict[str, float]:
        """Each child's average points earned a day over the last ``EARN_RATE_DAYS`` days.

        Approved chore points plus bonuses and other positive adjustments;
        refunds and gifts from a sibling hand points back rather than earn
        them, so they are left out. One pass for the whole family.
        """
        since = dt_util.now() - timedelta(days=EARN_RATE_DAYS)
        totals: dict[str, int] = {}
        for comp in self.storage.get_completions():
            if comp.approved and comp.completed_at >= since:
                totals[comp.child_id] = totals.get(comp.child_id, 0) + (comp.points_awarded or 0)
        for txn in self.storage.get_points_transactions():
            if txn.points <= 0 or txn.created_at < since or (txn.reason or "").startswith(_NOT_EARNINGS):
                continue
            totals[txn.child_id] = totals.get(txn.child_id, 0) + txn.points
        return {cid: round(total / EARN_RATE_DAYS, 1) for cid, total in totals.items() if total > 0}
