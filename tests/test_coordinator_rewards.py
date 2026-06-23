"""Tests for reward workflow in TaskMateCoordinator.

Covers async_claim_reward, async_approve_reward, and async_reject_reward,
including the get_reward() method that was previously missing.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, PoolAllocation, Reward, RewardClaim


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_coord(*, children=None, rewards=None, claims=None):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.data = {}
    coord._unsub_midnight = None
    coord._unsub_prune = None

    _children = {c.id: c for c in (children or [])}
    _rewards = {r.id: r for r in (rewards or [])}
    _claims = list(claims or [])

    storage = MagicMock()
    storage.get_child = MagicMock(side_effect=lambda cid: _children.get(cid))
    storage.get_reward = MagicMock(side_effect=lambda rid: _rewards.get(rid))
    storage.get_reward_claims = MagicMock(return_value=_claims)
    storage.get_pending_reward_claims = MagicMock(
        return_value=[c for c in _claims if not c.approved]
    )
    storage.update_child = MagicMock()
    storage.update_reward_claim = MagicMock()
    storage.add_reward_claim = MagicMock()
    storage.async_save = AsyncMock()
    # v3.0 pool allocation mocks — default to "no allocations" for wallet-mode tests
    storage.get_pool_allocation = MagicMock(return_value=None)
    storage.get_pool_allocations = MagicMock(return_value=[])
    storage.get_total_allocated_for_child = MagicMock(return_value=0)
    storage.get_total_allocated_for_reward = MagicMock(return_value=0)
    storage.upsert_pool_allocation = MagicMock()
    storage.remove_pool_allocation = MagicMock()
    storage.add_points_transaction = MagicMock()
    storage._data = {"reward_claims": [c.to_dict() for c in _claims]}

    def _remove_reward_claim(claim_id):
        storage._data["reward_claims"] = [
            c for c in storage._data["reward_claims"] if c.get("id") != claim_id
        ]
    storage.remove_reward_claim = MagicMock(side_effect=_remove_reward_claim)

    coord.storage = storage
    coord.async_refresh = AsyncMock()
    notifications = MagicMock()
    notifications.fire = AsyncMock()
    coord.notifications = notifications
    return coord


def _child(points=100):
    c = Child(name="Alice", points=points, id="kid1")
    return c


def _reward(cost=50):
    return Reward(name="Movie night", cost=cost, id="reward1")


# ---------------------------------------------------------------------------
# get_reward
# ---------------------------------------------------------------------------

class TestGetReward:
    def test_returns_reward_when_found(self):
        reward = _reward()
        coord = _make_coord(rewards=[reward])
        assert coord.get_reward("reward1") is not None
        assert coord.get_reward("reward1").name == "Movie night"

    def test_returns_none_when_not_found(self):
        coord = _make_coord()
        assert coord.get_reward("nonexistent") is None


# ---------------------------------------------------------------------------
# async_claim_reward
# ---------------------------------------------------------------------------

class TestClaimReward:
    def test_claim_created_when_enough_points(self):
        child = _child(points=100)
        reward = _reward(cost=50)
        coord = _make_coord(children=[child], rewards=[reward])
        claim = run(coord.async_claim_reward("reward1", "kid1"))
        assert claim.reward_id == "reward1"
        assert claim.child_id == "kid1"
        assert claim.approved is False
        coord.storage.add_reward_claim.assert_called_once()

    def test_claim_raises_when_not_enough_points(self):
        child = _child(points=30)
        reward = _reward(cost=50)
        coord = _make_coord(children=[child], rewards=[reward])
        with pytest.raises(ValueError, match="Not enough points"):
            run(coord.async_claim_reward("reward1", "kid1"))

    def test_claim_raises_when_reward_not_found(self):
        child = _child()
        coord = _make_coord(children=[child])
        with pytest.raises(ValueError, match="not found"):
            run(coord.async_claim_reward("no_such_reward", "kid1"))

    def test_claim_raises_when_child_not_found(self):
        reward = _reward()
        coord = _make_coord(rewards=[reward])
        with pytest.raises(ValueError, match="not found"):
            run(coord.async_claim_reward("reward1", "no_such_child"))

    def test_points_not_deducted_on_claim(self):
        child = _child(points=100)
        reward = _reward(cost=50)
        coord = _make_coord(children=[child], rewards=[reward])
        run(coord.async_claim_reward("reward1", "kid1"))
        assert child.points == 100  # deducted only on approval


# ---------------------------------------------------------------------------
# async_approve_reward
# ---------------------------------------------------------------------------

class TestApproveReward:
    def test_approval_deducts_points(self):
        child = _child(points=100)
        reward = _reward(cost=50)
        claim = RewardClaim(reward_id="reward1", child_id="kid1",
                            claimed_at=__import__("datetime").datetime.now(
                                __import__("datetime").timezone.utc), id="claim1")
        coord = _make_coord(children=[child], rewards=[reward], claims=[claim])
        run(coord.async_approve_reward("claim1"))
        assert child.points == 50

    def test_approval_raises_when_not_enough_points(self):
        child = _child(points=20)
        reward = _reward(cost=50)
        claim = RewardClaim(reward_id="reward1", child_id="kid1",
                            claimed_at=__import__("datetime").datetime.now(
                                __import__("datetime").timezone.utc), id="claim1")
        coord = _make_coord(children=[child], rewards=[reward], claims=[claim])
        with pytest.raises(ValueError, match="Not enough points"):
            run(coord.async_approve_reward("claim1"))

    def test_approval_marks_claim_approved(self):
        child = _child(points=100)
        reward = _reward(cost=50)
        claim = RewardClaim(reward_id="reward1", child_id="kid1",
                            claimed_at=__import__("datetime").datetime.now(
                                __import__("datetime").timezone.utc), id="claim1")
        coord = _make_coord(children=[child], rewards=[reward], claims=[claim])
        run(coord.async_approve_reward("claim1"))
        coord.storage.update_reward_claim.assert_called_once()
        updated_claim = coord.storage.update_reward_claim.call_args[0][0]
        assert updated_claim.approved is True


# ---------------------------------------------------------------------------
# async_reject_reward
# ---------------------------------------------------------------------------

class TestRejectReward:
    def test_rejection_removes_claim(self):
        import datetime as dt
        claim = RewardClaim(reward_id="reward1", child_id="kid1",
                            claimed_at=dt.datetime.now(dt.timezone.utc), id="claim1")
        coord = _make_coord(claims=[claim])
        run(coord.async_reject_reward("claim1"))
        remaining = [c for c in coord.storage._data["reward_claims"]
                     if c.get("id") == "claim1"]
        assert remaining == []

    def test_rejection_does_not_deduct_points(self):
        import datetime as dt
        child = _child(points=100)
        claim = RewardClaim(reward_id="reward1", child_id="kid1",
                            claimed_at=dt.datetime.now(dt.timezone.utc), id="claim1")
        coord = _make_coord(children=[child], claims=[claim])
        run(coord.async_reject_reward("claim1"))
        assert child.points == 100  # points were never deducted


# ---------------------------------------------------------------------------
# async_allocate_points_to_pool (v3.0 pool mode)
# ---------------------------------------------------------------------------


class TestAllocatePointsToPool:
    def test_allocation_deducts_from_child_points(self):
        child = _child(points=100)
        reward = _reward(cost=50)
        coord = _make_coord(children=[child], rewards=[reward])
        alloc = run(coord.async_allocate_points_to_pool("kid1", "reward1", 30))
        assert alloc.child_id == "kid1"
        assert alloc.reward_id == "reward1"
        assert alloc.allocated_points == 30
        # Child's visible balance drops by the allocated amount
        assert child.points == 70
        coord.storage.upsert_pool_allocation.assert_called_once()
        coord.storage.add_points_transaction.assert_called_once()

    def test_allocation_raises_when_no_spendable(self):
        child = _child(points=0)
        reward = _reward(cost=50)
        coord = _make_coord(children=[child], rewards=[reward])
        with pytest.raises(ValueError, match="spendable"):
            run(coord.async_allocate_points_to_pool("kid1", "reward1", 5))

    def test_allocation_capped_at_spendable(self):
        # Child has 10, requests 30 — capped to 10
        child = _child(points=10)
        reward = _reward(cost=50)
        coord = _make_coord(children=[child], rewards=[reward])
        alloc = run(coord.async_allocate_points_to_pool("kid1", "reward1", 30))
        assert alloc.allocated_points == 10
        assert child.points == 0

    def test_allocation_capped_at_pool_capacity(self):
        child = _child(points=100)
        reward = _reward(cost=50)
        # Existing allocation of 40 — only 10 room left in the pool
        existing = PoolAllocation(child_id="kid1", reward_id="reward1", allocated_points=40)
        coord = _make_coord(children=[child], rewards=[reward])
        coord.storage.get_pool_allocation = MagicMock(return_value=existing)
        # Ask for 20 but only 10 room left
        alloc = run(coord.async_allocate_points_to_pool("kid1", "reward1", 20))
        assert alloc.allocated_points == 50  # 40 existing + 10 capped
        # Child only loses the 10 that actually went in
        assert child.points == 90

    def test_allocation_raises_when_pool_full(self):
        child = _child(points=100)
        reward = _reward(cost=50)
        existing = PoolAllocation(child_id="kid1", reward_id="reward1", allocated_points=50)
        coord = _make_coord(children=[child], rewards=[reward])
        coord.storage.get_pool_allocation = MagicMock(return_value=existing)
        with pytest.raises(ValueError, match="already full"):
            run(coord.async_allocate_points_to_pool("kid1", "reward1", 5))

    def test_allocation_requires_positive_points(self):
        child = _child(points=100)
        reward = _reward(cost=50)
        coord = _make_coord(children=[child], rewards=[reward])
        with pytest.raises(ValueError, match="at least 1"):
            run(coord.async_allocate_points_to_pool("kid1", "reward1", 0))


class TestPoolModeApproval:
    def test_approval_in_pool_mode_clears_allocation_without_double_deduction(self):
        """In beta2, allocations already deducted points at allocation time, so approval
        should NOT reduce child.points again — it only clears the allocation."""
        import datetime as dt
        # Simulate the state AFTER allocation: child.points already dropped to 50,
        # the allocation holds the 50 earmarked points.
        child = _child(points=50)
        reward = _reward(cost=50)
        existing = PoolAllocation(child_id="kid1", reward_id="reward1", allocated_points=50)
        claim = RewardClaim(
            reward_id="reward1", child_id="kid1",
            claimed_at=dt.datetime.now(dt.timezone.utc), id="claim1",
        )
        coord = _make_coord(children=[child], rewards=[reward], claims=[claim])
        coord.storage.get_pool_allocation = MagicMock(return_value=existing)
        run(coord.async_approve_reward("claim1"))
        # Child's balance stays at 50 — no double deduction
        assert child.points == 50
        # Allocation is cleared
        coord.storage.remove_pool_allocation.assert_called_once()


class TestPoolClaimDoesNotBlockOtherAllocations:
    """A pending claim on a filled pool reward must not stop the child from
    allocating points to other pool rewards. The pool claim's cost was already
    deducted from child.points at allocation time, so counting it again as
    "committed" would drive spendable to zero."""

    def test_allocation_to_other_pool_reward_while_first_awaits_approval(self):
        import datetime as dt
        # Child started with 100; 50 already allocated to reward1 (pool-filled).
        # Visible points dropped to 50, and reward1 is claimed but unapproved.
        child = _child(points=50)
        reward1 = Reward(name="Movie", cost=50, id="reward1")
        reward2 = Reward(name="Toy", cost=50, id="reward2")
        filled_alloc = PoolAllocation(
            child_id="kid1", reward_id="reward1", allocated_points=50
        )
        claim = RewardClaim(
            reward_id="reward1", child_id="kid1",
            claimed_at=dt.datetime.now(dt.timezone.utc), id="claim1",
        )
        coord = _make_coord(children=[child], rewards=[reward1, reward2], claims=[claim])

        def _get_alloc(child_id, reward_id):
            if reward_id == "reward1":
                return filled_alloc
            return None
        coord.storage.get_pool_allocation = MagicMock(side_effect=_get_alloc)

        # Allocating to a different pool reward should succeed — the pending
        # pool-mode claim on reward1 must not be counted as committed wallet points.
        alloc = run(coord.async_allocate_points_to_pool("kid1", "reward2", 20))
        assert alloc.reward_id == "reward2"
        assert alloc.allocated_points == 20
        assert child.points == 30  # 50 − 20

    def test_wallet_claim_still_blocks_pool_allocation(self):
        """Sanity check: a non-pool-mode pending claim should still reserve points."""
        import datetime as dt
        child = _child(points=50)
        reward1 = Reward(name="Movie", cost=40, id="reward1")
        reward2 = Reward(name="Toy", cost=30, id="reward2")
        # No allocation → claim is wallet-mode and its cost IS committed.
        claim = RewardClaim(
            reward_id="reward1", child_id="kid1",
            claimed_at=dt.datetime.now(dt.timezone.utc), id="claim1",
        )
        coord = _make_coord(children=[child], rewards=[reward1, reward2], claims=[claim])
        # spendable = 50 − 40 = 10, so requesting 30 is capped to 10.
        alloc = run(coord.async_allocate_points_to_pool("kid1", "reward2", 30))
        assert alloc.allocated_points == 10
        assert child.points == 40

    def test_is_pool_mode_claim_detects_filled_allocation(self):
        import datetime as dt
        reward = _reward(cost=50)
        coord = _make_coord(rewards=[reward])
        filled = PoolAllocation(child_id="kid1", reward_id="reward1", allocated_points=50)
        coord.storage.get_pool_allocation = MagicMock(return_value=filled)
        claim = RewardClaim(
            reward_id="reward1", child_id="kid1",
            claimed_at=dt.datetime.now(dt.timezone.utc), id="claim1",
        )
        assert coord.is_pool_mode_claim(claim) is True

    def test_is_pool_mode_claim_false_for_partial_allocation(self):
        import datetime as dt
        reward = _reward(cost=50)
        coord = _make_coord(rewards=[reward])
        partial = PoolAllocation(child_id="kid1", reward_id="reward1", allocated_points=20)
        coord.storage.get_pool_allocation = MagicMock(return_value=partial)
        claim = RewardClaim(
            reward_id="reward1", child_id="kid1",
            claimed_at=dt.datetime.now(dt.timezone.utc), id="claim1",
        )
        assert coord.is_pool_mode_claim(claim) is False

    def test_is_pool_mode_claim_false_without_allocation(self):
        import datetime as dt
        reward = _reward(cost=50)
        coord = _make_coord(rewards=[reward])
        claim = RewardClaim(
            reward_id="reward1", child_id="kid1",
            claimed_at=dt.datetime.now(dt.timezone.utc), id="claim1",
        )
        assert coord.is_pool_mode_claim(claim) is False


class TestPoolOverallocationRefund:
    """When a reward's cost is reduced (or when an over-allocated pool is
    redeemed) any pool allocation that exceeds the reward's cost must be
    trimmed and the excess refunded to the contributing child's wallet."""

    def test_update_reward_refunds_excess_when_cost_reduced(self):
        # Child started with 100, allocated 10 to a reward originally costing 10.
        child = _child(points=90)
        old_reward = Reward(name="Test", cost=10, id="reward1")
        existing = PoolAllocation(child_id="kid1", reward_id="reward1", allocated_points=10)
        coord = _make_coord(children=[child], rewards=[old_reward])
        coord.storage.get_pool_allocation = MagicMock(return_value=existing)
        coord.storage.get_pool_allocations = MagicMock(return_value=[existing])

        # Parent edits the cost down to 5 — 5 points should refund.
        new_reward = Reward(name="Test", cost=5, id="reward1")
        run(coord.async_update_reward(new_reward))

        assert child.points == 95  # 90 + 5 refunded
        # Allocation trimmed to the new cost
        upsert_args = coord.storage.upsert_pool_allocation.call_args[0][0]
        assert upsert_args.allocated_points == 5
        # Audit transaction recorded
        coord.storage.add_points_transaction.assert_called_once()
        txn = coord.storage.add_points_transaction.call_args[0][0]
        assert txn.points == 5
        assert "cost reduced" in txn.reason.lower()

    def test_update_reward_no_refund_when_cost_unchanged(self):
        child = _child(points=90)
        reward = Reward(name="Test", cost=10, id="reward1")
        existing = PoolAllocation(child_id="kid1", reward_id="reward1", allocated_points=10)
        coord = _make_coord(children=[child], rewards=[reward])
        coord.storage.get_pool_allocation = MagicMock(return_value=existing)
        coord.storage.get_pool_allocations = MagicMock(return_value=[existing])

        run(coord.async_update_reward(Reward(name="Test renamed", cost=10, id="reward1")))

        assert child.points == 90  # No refund
        coord.storage.add_points_transaction.assert_not_called()

    def test_update_reward_no_refund_when_cost_increased(self):
        child = _child(points=90)
        reward = Reward(name="Test", cost=10, id="reward1")
        existing = PoolAllocation(child_id="kid1", reward_id="reward1", allocated_points=10)
        coord = _make_coord(children=[child], rewards=[reward])
        coord.storage.get_pool_allocation = MagicMock(return_value=existing)
        coord.storage.get_pool_allocations = MagicMock(return_value=[existing])

        run(coord.async_update_reward(Reward(name="Test", cost=20, id="reward1")))

        assert child.points == 90
        coord.storage.add_points_transaction.assert_not_called()

    def test_update_reward_removes_allocation_when_cost_drops_to_zero(self):
        child = _child(points=90)
        reward = Reward(name="Test", cost=10, id="reward1")
        existing = PoolAllocation(child_id="kid1", reward_id="reward1", allocated_points=10)
        coord = _make_coord(children=[child], rewards=[reward])
        coord.storage.get_pool_allocation = MagicMock(return_value=existing)
        coord.storage.get_pool_allocations = MagicMock(return_value=[existing])

        run(coord.async_update_reward(Reward(name="Test", cost=0, id="reward1")))

        assert child.points == 100  # all 10 refunded
        coord.storage.remove_pool_allocation.assert_called_once_with("kid1", "reward1")

    def test_jackpot_cost_reduction_refunds_newest_first(self):
        # Two children each contributed to a 100-point jackpot. Newer allocation
        # (id sorts later) gets trimmed first when cost drops to 60 (overshoot 20).
        child_a = Child(name="A", points=0, id="kidA")
        child_b = Child(name="B", points=0, id="kidB")
        old_reward = Reward(name="Jackpot", cost=100, is_jackpot=True, id="rewardJ")
        alloc_a = PoolAllocation(child_id="kidA", reward_id="rewardJ", allocated_points=50, id="alloc_aaa")
        alloc_b = PoolAllocation(child_id="kidB", reward_id="rewardJ", allocated_points=30, id="alloc_zzz")
        coord = _make_coord(children=[child_a, child_b], rewards=[old_reward])
        coord.storage.get_pool_allocations = MagicMock(return_value=[alloc_a, alloc_b])

        run(coord.async_update_reward(Reward(name="Jackpot", cost=60, is_jackpot=True, id="rewardJ")))

        # Total was 80, cost dropped to 60 → overshoot 20 refunded from kidB (newer id).
        assert child_b.points == 20  # full refund of 20
        assert child_a.points == 0   # untouched

    def test_approve_refunds_overshoot_on_redeem(self):
        # Pre-existing over-allocation: child put 11 into a pool that costs 10.
        # On approval, the 1-point overshoot must be refunded to the wallet.
        import datetime as dt
        child = _child(points=89)  # 100 earned − 11 allocated = 89
        reward = _reward(cost=10)
        over_alloc = PoolAllocation(child_id="kid1", reward_id="reward1", allocated_points=11)
        claim = RewardClaim(
            reward_id="reward1", child_id="kid1",
            claimed_at=dt.datetime.now(dt.timezone.utc), id="claim1",
        )
        coord = _make_coord(children=[child], rewards=[reward], claims=[claim])
        coord.storage.get_pool_allocation = MagicMock(return_value=over_alloc)
        coord.storage.get_pool_allocations = MagicMock(return_value=[over_alloc])

        run(coord.async_approve_reward("claim1"))

        # 1 point refunded back to the wallet on redeem
        assert child.points == 90
        coord.storage.remove_pool_allocation.assert_called()


class TestRewardStockAndExpiration:
    """Quantity-based sold-out behaviour and expires_at expiration, plus the
    automatic refund that fires when either condition makes a reward
    unavailable while children still have points earmarked for it."""

    def test_approve_decrements_quantity(self):
        import datetime as dt
        child = _child(points=100)
        reward = Reward(name="Unique toy", cost=50, quantity=2, id="reward1")
        claim = RewardClaim(
            reward_id="reward1", child_id="kid1",
            claimed_at=dt.datetime.now(dt.timezone.utc), id="claim1",
        )
        coord = _make_coord(children=[child], rewards=[reward], claims=[claim])
        run(coord.async_approve_reward("claim1"))
        assert reward.quantity == 1
        coord.storage.update_reward.assert_called()

    def test_unlimited_quantity_not_decremented(self):
        import datetime as dt
        child = _child(points=100)
        reward = Reward(name="Ice cream", cost=50, quantity=None, id="reward1")
        claim = RewardClaim(
            reward_id="reward1", child_id="kid1",
            claimed_at=dt.datetime.now(dt.timezone.utc), id="claim1",
        )
        coord = _make_coord(children=[child], rewards=[reward], claims=[claim])
        run(coord.async_approve_reward("claim1"))
        assert reward.quantity is None

    def test_approve_sold_out_refunds_other_pool_allocations(self):
        """Non-jackpot reward with quantity 1: child A redeems, child B had
        pre-allocated points on the same reward. On approval the reward hits 0
        and child B's allocation must be refunded to their wallet."""
        import datetime as dt
        child_a = Child(name="A", points=100, id="kidA")
        child_b = Child(name="B", points=50, id="kidB")
        reward = Reward(name="Unique toy", cost=50, quantity=1, id="reward1")
        alloc_b = PoolAllocation(
            child_id="kidB", reward_id="reward1", allocated_points=20, id="alloc_b",
        )
        claim = RewardClaim(
            reward_id="reward1", child_id="kidA",
            claimed_at=dt.datetime.now(dt.timezone.utc), id="claim1",
        )
        coord = _make_coord(
            children=[child_a, child_b], rewards=[reward], claims=[claim],
        )
        # Child A is redeeming from their wallet; allocations belong to B.
        coord.storage.get_pool_allocation = MagicMock(return_value=None)
        coord.storage.get_pool_allocations = MagicMock(return_value=[alloc_b])

        run(coord.async_approve_reward("claim1"))

        assert reward.quantity == 0
        assert child_a.points == 50  # 100 − 50 cost
        assert child_b.points == 70  # 50 + 20 refunded
        coord.storage.remove_pool_allocation.assert_any_call("kidB", "reward1")

    def test_jackpot_sold_out_refunds_remaining_contributors(self):
        """Jackpot redeem of a quantity=1 reward: allocations are cleared by
        the pool-mode redeem path, so when quantity hits 0 there's nothing
        left to refund. Points stay spent on the reward."""
        import datetime as dt
        child_a = Child(name="A", points=0, id="kidA")
        child_b = Child(name="B", points=0, id="kidB")
        reward = Reward(name="Shared prize", cost=80, quantity=1, is_jackpot=True, id="rewardJ")
        alloc_a = PoolAllocation(child_id="kidA", reward_id="rewardJ", allocated_points=50, id="a1")
        alloc_b = PoolAllocation(child_id="kidB", reward_id="rewardJ", allocated_points=30, id="a2")
        claim = RewardClaim(
            reward_id="rewardJ", child_id="kidA",
            claimed_at=dt.datetime.now(dt.timezone.utc), id="claim1",
        )
        coord = _make_coord(
            children=[child_a, child_b], rewards=[reward], claims=[claim],
        )
        coord.storage.get_total_allocated_for_reward = MagicMock(return_value=80)

        # Stateful mock: allocations shrink as storage.remove_pool_allocation
        # is called, mirroring the real storage behaviour.
        allocs = {("kidA", "rewardJ"): alloc_a, ("kidB", "rewardJ"): alloc_b}
        coord.storage.get_pool_allocations = MagicMock(
            side_effect=lambda: list(allocs.values())
        )
        def _remove(child_id, reward_id):
            allocs.pop((child_id, reward_id), None)
        coord.storage.remove_pool_allocation = MagicMock(side_effect=_remove)

        run(coord.async_approve_reward("claim1"))

        assert reward.quantity == 0
        # Points stay spent — they were deducted at allocation time and the
        # redeem consumed them. No refund fires because allocations are gone
        # by the time the sold-out check runs.
        assert child_a.points == 0
        assert child_b.points == 0
        assert allocs == {}

    def test_claim_blocked_when_sold_out(self):
        child = _child(points=100)
        reward = Reward(name="Gone", cost=50, quantity=0, id="reward1")
        coord = _make_coord(children=[child], rewards=[reward])
        with pytest.raises(ValueError, match="sold out"):
            run(coord.async_claim_reward("reward1", "kid1"))

    def test_pool_allocation_blocked_when_sold_out(self):
        child = _child(points=100)
        reward = Reward(name="Gone", cost=50, quantity=0, id="reward1")
        coord = _make_coord(children=[child], rewards=[reward])
        with pytest.raises(ValueError, match="sold out"):
            run(coord.async_allocate_points_to_pool("kid1", "reward1", 10))

    def test_claim_blocked_when_expired(self):
        child = _child(points=100)
        # dt_util_mock returns 2024-03-20; use 2024-03-19 to be expired.
        reward = Reward(name="Old", cost=50, expires_at="2024-03-19", id="reward1")
        coord = _make_coord(children=[child], rewards=[reward])
        with pytest.raises(ValueError, match="expired"):
            run(coord.async_claim_reward("reward1", "kid1"))

    def test_pool_allocation_blocked_when_expired(self):
        child = _child(points=100)
        reward = Reward(name="Old", cost=50, expires_at="2024-03-19", id="reward1")
        coord = _make_coord(children=[child], rewards=[reward])
        with pytest.raises(ValueError, match="expired"):
            run(coord.async_allocate_points_to_pool("kid1", "reward1", 10))

    def test_expires_at_in_future_does_not_expire_yet(self):
        child = _child(points=100)
        reward = Reward(name="Future", cost=50, expires_at="2099-01-01", id="reward1")
        coord = _make_coord(children=[child], rewards=[reward])
        claim = run(coord.async_claim_reward("reward1", "kid1"))
        assert claim.reward_id == "reward1"

    def test_expiration_midnight_refunds_all_allocations(self):
        child_a = Child(name="A", points=10, id="kidA")
        child_b = Child(name="B", points=20, id="kidB")
        reward = Reward(name="Old", cost=100, expires_at="2024-03-19", id="reward1")
        alloc_a = PoolAllocation(child_id="kidA", reward_id="reward1", allocated_points=15, id="a1")
        alloc_b = PoolAllocation(child_id="kidB", reward_id="reward1", allocated_points=25, id="a2")
        coord = _make_coord(children=[child_a, child_b], rewards=[reward])
        coord.storage.get_rewards = MagicMock(return_value=[reward])
        coord.storage.get_pool_allocations = MagicMock(return_value=[alloc_a, alloc_b])

        run(coord._async_expire_rewards())

        assert child_a.points == 25  # 10 + 15 refund
        assert child_b.points == 45  # 20 + 25 refund

    def test_update_reward_to_quantity_zero_refunds_allocations(self):
        child = _child(points=50)
        reward = Reward(name="Limited", cost=100, quantity=2, id="reward1")
        alloc = PoolAllocation(child_id="kid1", reward_id="reward1", allocated_points=30, id="a1")
        coord = _make_coord(children=[child], rewards=[reward])
        coord.storage.get_pool_allocation = MagicMock(return_value=alloc)
        coord.storage.get_pool_allocations = MagicMock(return_value=[alloc])

        updated = Reward(name="Limited", cost=100, quantity=0, id="reward1")
        run(coord.async_update_reward(updated))

        assert child.points == 80  # 50 + 30 refund
        coord.storage.remove_pool_allocation.assert_called_with("kid1", "reward1")


class TestJackpotImpliesPoolMode:
    """Jackpots are inherently pooled — pool mode is forced on (#552)."""

    def test_add_jackpot_forces_pool_enabled(self):
        coord = _make_coord()
        reward = run(coord.async_add_reward(
            name="Family Trip", cost=100, is_jackpot=True, pool_enabled=False
        ))
        assert reward.pool_enabled is True
        assert coord.storage.add_reward.call_args.args[0].pool_enabled is True

    def test_update_jackpot_forces_pool_enabled(self):
        existing = Reward(name="Trip", cost=100, is_jackpot=True,
                          pool_enabled=False, id="rwJ")
        coord = _make_coord(rewards=[existing])
        edited = Reward(name="Trip", cost=100, is_jackpot=True,
                        pool_enabled=False, id="rwJ")
        run(coord.async_update_reward(edited))
        assert edited.pool_enabled is True
        assert coord.storage.update_reward.call_args.args[0].pool_enabled is True

    def test_non_jackpot_pool_flag_left_untouched(self):
        coord = _make_coord()
        reward = run(coord.async_add_reward(
            name="Ice cream", cost=10, is_jackpot=False, pool_enabled=False
        ))
        assert reward.pool_enabled is False
