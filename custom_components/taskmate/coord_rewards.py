"""Reward operations mixin for TaskMateCoordinator."""
from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

from homeassistant.util import dt as dt_util

from .models import PointsTransaction, PoolAllocation, Reward, RewardClaim

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class RewardsMixin:
    """Mixin providing reward CRUD, claiming, and pool allocation logic."""

    def get_reward(self, reward_id: str) -> Reward | None:
        """Get a reward by ID."""
        return self.storage.get_reward(reward_id)

    def is_pool_mode_claim(self, claim: RewardClaim) -> bool:
        """True if the claim is covered by pool allocations (points already deducted).

        Pool-mode claims must NOT be counted against a child's spendable balance,
        because their cost was already removed from child.points at allocation time.
        """
        reward = self.get_reward(claim.reward_id)
        if not reward:
            return False
        if getattr(reward, "is_jackpot", False):
            return self.storage.get_total_allocated_for_reward(claim.reward_id) >= reward.cost
        alloc = self.storage.get_pool_allocation(claim.child_id, claim.reward_id)
        return bool(alloc and alloc.allocated_points >= reward.cost)

    async def async_add_reward(
        self,
        name: str,
        cost: int = 50,
        description: str = "",
        icon: str = "mdi:gift",
        assigned_to: list[str] | None = None,
        is_jackpot: bool = False,
        pool_enabled: bool = False,
        quantity: int | None = None,
        expires_at: str | None = None,
    ) -> Reward:
        """Add a new reward."""
        reward = Reward(
            name=name,
            cost=cost,
            description=description,
            icon=icon,
            assigned_to=assigned_to or [],
            is_jackpot=is_jackpot,
            pool_enabled=pool_enabled,
            quantity=quantity,
            expires_at=expires_at,
        )
        self.storage.add_reward(reward)
        await self.storage.async_save()
        await self.async_refresh()
        return reward

    async def async_update_reward(self, reward: Reward) -> None:
        """Update a reward.

        If the cost is reduced below any existing pool allocation, the excess is
        refunded to the contributing children's wallets so over-allocated pools
        can't appear as e.g. 11/10. If the edit makes the reward unavailable
        (quantity set to 0, or expires_at moved into the past) any pool
        allocations on that reward are refunded in full.
        """
        old = self.get_reward(reward.id)
        self.storage.update_reward(reward)
        if old and reward.cost < old.cost:
            self._refund_pool_excess(reward, "Pool refund (reward cost reduced)")
        became_unavailable = (
            self._reward_is_unavailable(reward)
            and old is not None
            and not self._reward_is_unavailable(old)
        )
        if became_unavailable:
            reason = (
                "Pool refund (reward expired)"
                if self._reward_is_expired(reward)
                else "Pool refund (reward sold out)"
            )
            self._refund_all_pool_allocations(reward, reason)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_remove_reward(self, reward_id: str) -> None:
        """Remove a reward and clean up any pending claims and pool allocations referencing it."""
        self.storage.remove_reward_claims_for_reward(reward_id)
        self.storage.remove_pool_allocations_for_reward(reward_id)
        self.storage.remove_reward(reward_id)
        await self.storage.async_save()
        await self.async_refresh()

    @staticmethod
    def _reward_is_sold_out(reward: Reward) -> bool:
        """True if the reward has a stock count and it's been exhausted."""
        return reward.quantity is not None and reward.quantity <= 0

    @staticmethod
    def _reward_is_expired(reward: Reward) -> bool:
        """True if the reward has an expiry date and it's on/before today."""
        if not reward.expires_at:
            return False
        try:
            deadline = date.fromisoformat(reward.expires_at)
        except (TypeError, ValueError):
            return False
        return deadline <= dt_util.now().date()

    @classmethod
    def _reward_is_unavailable(cls, reward: Reward) -> bool:
        """True if the reward cannot currently be claimed or allocated to."""
        return cls._reward_is_sold_out(reward) or cls._reward_is_expired(reward)

    def _refund_all_pool_allocations(self, reward: Reward, reason: str) -> None:
        """Refund every pool allocation on `reward` back to its contributor.

        Used when a reward becomes unavailable (sold out or expired) while
        children still have points earmarked for it. Reuses the existing
        per-allocation refund helper so the PointsTransaction audit trail
        stays consistent with cost-reduction refunds.
        """
        allocations = [
            a for a in self.storage.get_pool_allocations()
            if a.reward_id == reward.id and a.allocated_points > 0
        ]
        for alloc in allocations:
            self._apply_pool_refund(alloc, alloc.allocated_points, reward, reason)

    def _refund_pool_excess(self, reward: Reward, reason: str) -> None:
        """Trim any pool allocations on `reward` that exceed its cost.

        Non-jackpot: each allocation is capped at the reward's cost individually.
        Jackpot: allocations are trimmed starting from the newest contributor
        until the combined total matches the cost.
        """
        allocations = [
            a for a in self.storage.get_pool_allocations()
            if a.reward_id == reward.id and a.allocated_points > 0
        ]
        if not allocations:
            return

        if reward.is_jackpot:
            overshoot = sum(a.allocated_points for a in allocations) - reward.cost
            if overshoot <= 0:
                return
            for alloc in sorted(allocations, key=lambda a: a.id, reverse=True):
                if overshoot <= 0:
                    break
                refund = min(alloc.allocated_points, overshoot)
                self._apply_pool_refund(alloc, refund, reward, reason)
                overshoot -= refund
        else:
            for alloc in allocations:
                if alloc.allocated_points > reward.cost:
                    self._apply_pool_refund(
                        alloc, alloc.allocated_points - reward.cost, reward, reason
                    )

    def _apply_pool_refund(
        self, allocation: PoolAllocation, refund: int, reward: Reward, reason: str
    ) -> None:
        """Refund `refund` points from `allocation` back to the child's wallet.

        Updates or removes the allocation record and writes an audit transaction.
        """
        if refund <= 0:
            return
        child = self.get_child(allocation.child_id)
        if not child:
            return
        child.points += refund
        self.storage.update_child(child)

        remaining = allocation.allocated_points - refund
        if remaining <= 0:
            self.storage.remove_pool_allocation(allocation.child_id, allocation.reward_id)
        else:
            self.storage.upsert_pool_allocation(PoolAllocation(
                child_id=allocation.child_id,
                reward_id=allocation.reward_id,
                allocated_points=remaining,
                id=allocation.id,
            ))

        self.storage.add_points_transaction(PointsTransaction(
            child_id=allocation.child_id,
            points=refund,
            reason=f"{reason}: {reward.name}",
            created_at=dt_util.now(),
        ))

    async def async_claim_reward(self, reward_id: str, child_id: str) -> RewardClaim:
        """Child claims a reward — creates a pending claim awaiting parent approval.

        Two modes are supported:
          * Wallet mode (default): requires child.points (minus committed) to cover cost
          * Pool mode: if pool allocations exist for this (child, reward) and they fill the
            reward's cost, the claim is a "redeem" — no wallet check needed. For jackpot
            rewards the pool total across all contributing children must reach the cost.
        """
        reward = self.get_reward(reward_id)
        if not reward:
            raise ValueError(f"Reward {reward_id} not found")

        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        if self._reward_is_sold_out(reward):
            raise ValueError(f"Reward '{reward.name}' is sold out")
        if self._reward_is_expired(reward):
            raise ValueError(f"Reward '{reward.name}' has expired")

        # Cost is always static
        effective_cost = reward.cost

        # Detect pool mode: a filled pool allocation for this (child, reward) is sufficient,
        # or for jackpots the summed pool across all children reaches cost.
        pool_filled = False
        if reward.is_jackpot:
            pool_total = self.storage.get_total_allocated_for_reward(reward_id)
            if pool_total >= effective_cost:
                pool_filled = True
        else:
            allocation = self.storage.get_pool_allocation(child_id, reward_id)
            if allocation and allocation.allocated_points >= effective_cost:
                pool_filled = True

        if not pool_filled:
            # Wallet mode: verify child has enough uncommitted points.
            # Pool-mode pending claims already had their cost deducted at allocation time,
            # so they are skipped here to avoid double-counting against the wallet.
            pending_claims = self.storage.get_pending_reward_claims()
            committed = 0
            for c in pending_claims:
                if c.child_id == child_id and not self.is_pool_mode_claim(c):
                    pending_reward = self.get_reward(c.reward_id)
                    if pending_reward:
                        committed += pending_reward.cost
            available_points = child.points - committed

            if available_points < effective_cost:
                raise ValueError(
                    f"Not enough points. Need {effective_cost}, have {available_points} available"
                )

        claim = RewardClaim(
            reward_id=reward_id,
            child_id=child_id,
            claimed_at=dt_util.now(),
        )

        self.storage.add_reward_claim(claim)
        await self.storage.async_save()
        await self.async_refresh()
        await self._async_notify_pending_reward_claim(
            child.name, reward.name, reward.cost
        )
        return claim

    async def async_approve_reward(self, claim_id: str) -> None:
        """Approve a reward claim and deduct points from the child.

        If a pool allocation exists for this (child, reward) pair with enough points,
        the deduction consumes the pool allocation first (pool mode). Otherwise the
        wallet-mode path deducts directly from child.points.
        """
        claims = self.storage.get_reward_claims()
        for claim in claims:
            if claim.id == claim_id:
                if claim.approved:
                    _LOGGER.warning("Reward claim %s already approved, ignoring", claim_id)
                    return

                reward = self.get_reward(claim.reward_id)
                child = self.get_child(claim.child_id)
                if not reward or not child:
                    raise ValueError(f"Reward or child not found for claim {claim_id}")

                # Cost is always static
                effective_cost = reward.cost

                # Detect pool mode: either a direct allocation, or a filled jackpot pool.
                pool_alloc = self.storage.get_pool_allocation(claim.child_id, claim.reward_id)
                is_pool_mode = False
                if reward.is_jackpot:
                    pool_total = self.storage.get_total_allocated_for_reward(claim.reward_id)
                    if pool_total >= effective_cost:
                        is_pool_mode = True
                elif pool_alloc and pool_alloc.allocated_points >= effective_cost:
                    is_pool_mode = True

                if is_pool_mode:
                    # Pool mode: points were already deducted from child.points at allocation
                    # time — approving the redeem just clears the allocation record(s).
                    # Refund any over-allocation first (e.g. left over from a prior cost reduction)
                    # so the child doesn't lose points beyond the reward's actual cost.
                    self._refund_pool_excess(reward, "Pool refund on redeem")
                    if reward.is_jackpot:
                        jackpot_allocs = [
                            a for a in self.storage.get_pool_allocations()
                            if a.reward_id == claim.reward_id and a.allocated_points > 0
                        ]
                        for alloc in jackpot_allocs:
                            self.storage.remove_pool_allocation(alloc.child_id, alloc.reward_id)
                    else:
                        self.storage.remove_pool_allocation(claim.child_id, claim.reward_id)
                else:
                    # Wallet mode: deduct directly from child.points
                    if child.points < effective_cost:
                        raise ValueError(
                            f"Not enough points to approve. Need {effective_cost}, have {child.points}"
                        )
                    child.points -= effective_cost
                    self.storage.update_child(child)

                if reward.quantity is not None:
                    reward.quantity = max(0, reward.quantity - 1)
                    self.storage.update_reward(reward)
                    if reward.quantity == 0:
                        # Last unit claimed — refund any points other children
                        # still have earmarked for this reward's pool.
                        self._refund_all_pool_allocations(
                            reward, "Pool refund (reward sold out)"
                        )

                claim.approved = True
                claim.approved_at = dt_util.now()
                self.storage.update_reward_claim(claim)
                await self.storage.async_save()
                await self.async_refresh()
                return
        _LOGGER.warning("Reward claim %s not found for approval", claim_id)

    async def async_reject_reward(self, claim_id: str) -> None:
        """Reject a reward claim — no refund needed as points were never deducted."""
        self.storage.remove_reward_claim(claim_id)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_allocate_points_to_pool(
        self, child_id: str, reward_id: str, points: int
    ) -> PoolAllocation:
        """Move `points` from a child's spendable balance into a reward pool.

        Deducts immediately from child.points so the visible balance reflects the
        commitment. The matching PoolAllocation record tracks the earmarked total
        for each (child, reward) pair. Requested points are capped silently at the
        pool's remaining capacity and the child's spendable balance.
        Allocations are locked — there is no matching "withdraw" operation.
        """
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        reward = self.get_reward(reward_id)
        if not reward:
            raise ValueError(f"Reward {reward_id} not found")

        if self._reward_is_sold_out(reward):
            raise ValueError(f"Reward '{reward.name}' is sold out")
        if self._reward_is_expired(reward):
            raise ValueError(f"Reward '{reward.name}' has expired")

        if points < 1:
            raise ValueError("Points to allocate must be at least 1")

        # Spendable balance = child.points − points committed to other pending claims.
        # (Already-allocated points are no longer part of child.points, so we do NOT
        # subtract total_allocated here — they've been deducted at allocation time.)
        # Pool-mode pending claims are also skipped — their cost was already removed
        # from child.points at allocation time, so counting it again would block the
        # child from allocating to any other pool reward while one awaits approval.
        pending_claims = self.storage.get_pending_reward_claims()
        committed = 0
        for c in pending_claims:
            if c.child_id == child_id and not self.is_pool_mode_claim(c):
                pending_reward = self.get_reward(c.reward_id)
                if pending_reward:
                    committed += pending_reward.cost
        spendable = child.points - committed

        if spendable < 1:
            raise ValueError(f"No spendable points available for {child.name}")

        # Compute remaining pool capacity
        existing = self.storage.get_pool_allocation(child_id, reward_id)
        current_child_allocation = existing.allocated_points if existing else 0
        if reward.is_jackpot:
            room_left = reward.cost - self.storage.get_total_allocated_for_reward(reward_id)
        else:
            room_left = reward.cost - current_child_allocation

        if room_left <= 0:
            raise ValueError(f"Pool for reward '{reward.name}' is already full")

        capped_points = min(points, spendable, room_left)

        # Deduct from the visible balance; the allocation record holds the earmarked points.
        child.points -= capped_points
        self.storage.update_child(child)

        allocation = PoolAllocation(
            child_id=child_id,
            reward_id=reward_id,
            allocated_points=current_child_allocation + capped_points,
            id=existing.id if existing else PoolAllocation(child_id, reward_id).id,
        )
        self.storage.upsert_pool_allocation(allocation)

        # Audit trail: negative transaction showing the deduction
        transaction = PointsTransaction(
            child_id=child_id,
            points=-capped_points,
            reason=f"Allocated to pool: {reward.name}",
            created_at=dt_util.now(),
        )
        self.storage.add_points_transaction(transaction)

        await self.storage.async_save()
        await self.async_refresh()
        return allocation

    async def _async_expire_rewards(self) -> None:
        """Refund pool allocations on any reward whose expires_at is past.

        The reward row itself is kept in storage so the sensor can surface the
        "Expired" state and existing claim history stays intact.
        """
        changed = False
        for reward in self.storage.get_rewards():
            if not self._reward_is_expired(reward):
                continue
            allocations_before = [
                a for a in self.storage.get_pool_allocations()
                if a.reward_id == reward.id and a.allocated_points > 0
            ]
            if not allocations_before:
                continue
            self._refund_all_pool_allocations(reward, "Pool refund (reward expired)")
            changed = True
            _LOGGER.info(
                "Reward '%s' expired on %s — refunded %d pool allocation(s)",
                reward.name, reward.expires_at, len(allocations_before),
            )

        if changed:
            await self.storage.async_save()
            await self.async_refresh()
