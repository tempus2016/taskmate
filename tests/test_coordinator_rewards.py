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
