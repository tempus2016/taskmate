"""Tests for taskmate_* automation events added for penalties, bonuses,
reward approve/reject and chore reject."""
from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import (
    Bonus, Child, ChoreCompletion, Chore, Penalty, Reward, RewardClaim,
)

UTC = dt.timezone.utc


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _base_coord():
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    coord.storage = MagicMock()
    coord.storage.async_save = AsyncMock()
    coord.async_refresh = AsyncMock()
    return coord


def _fired(coord, name):
    return [c for c in coord.hass.bus.async_fire.call_args_list if c[0][0] == name]


def test_penalty_applied_event():
    coord = _base_coord()
    coord.async_remove_points = AsyncMock()
    coord.storage.get_penalty = MagicMock(return_value=Penalty(name="Mess", points=10, id="p1"))
    coord.get_child = MagicMock(return_value=Child(name="Mia", id="c1"))
    run(coord.async_apply_penalty("p1", "c1"))
    calls = _fired(coord, "taskmate_penalty_applied")
    assert len(calls) == 1
    payload = calls[0][0][1]
    assert payload["penalty_name"] == "Mess" and payload["child_id"] == "c1" and payload["points"] == 10


def test_bonus_applied_event():
    coord = _base_coord()
    coord.async_add_points = AsyncMock()
    coord.storage.get_bonus = MagicMock(return_value=Bonus(name="Helper", points=15, id="b1"))
    coord.get_child = MagicMock(return_value=Child(name="Mia", id="c1"))
    run(coord.async_apply_bonus("b1", "c1"))
    calls = _fired(coord, "taskmate_bonus_applied")
    assert len(calls) == 1
    assert calls[0][0][1]["bonus_name"] == "Helper"


def test_reward_rejected_event():
    coord = _base_coord()
    claim = RewardClaim(reward_id="r1", child_id="c1", claimed_at=dt.datetime(2024, 1, 1, tzinfo=UTC), id="cl1")
    coord.storage.get_reward_claims = MagicMock(return_value=[claim])
    coord.storage.remove_reward_claim = MagicMock()
    coord.get_reward = MagicMock(return_value=Reward(name="Ice cream", cost=50, id="r1"))
    coord.get_child = MagicMock(return_value=Child(name="Mia", id="c1"))
    run(coord.async_reject_reward("cl1"))
    calls = _fired(coord, "taskmate_reward_rejected")
    assert len(calls) == 1
    assert calls[0][0][1]["reward_name"] == "Ice cream"


def test_reward_approved_event_wallet_mode():
    coord = _base_coord()
    claim = RewardClaim(reward_id="r1", child_id="c1", claimed_at=dt.datetime(2024, 1, 1, tzinfo=UTC),
                        approved=False, id="cl1")
    coord.storage.get_reward_claims = MagicMock(return_value=[claim])
    coord.storage.get_pool_allocation = MagicMock(return_value=None)
    coord.storage.update_child = MagicMock()
    coord.storage.update_reward_claim = MagicMock()
    coord.get_reward = MagicMock(return_value=Reward(name="Movie", cost=20, id="r1"))
    coord.get_child = MagicMock(return_value=Child(name="Mia", points=100, id="c1"))
    coord.badges = None
    run(coord.async_approve_reward("cl1"))
    calls = _fired(coord, "taskmate_reward_approved")
    assert len(calls) == 1
    assert calls[0][0][1]["reward_name"] == "Movie" and calls[0][0][1]["cost"] == 20


def test_chore_rejected_event():
    coord = _base_coord()
    comp = ChoreCompletion(chore_id="ch1", child_id="c1",
                           completed_at=dt.datetime(2024, 1, 1, tzinfo=UTC),
                           approved=False, points_awarded=0, id="comp1")
    coord.storage.get_completions = MagicMock(return_value=[comp])
    coord.storage.undo_last_completed = MagicMock()
    coord.storage.remove_completion = MagicMock()
    coord.get_chore = MagicMock(return_value=Chore(name="Bin", id="ch1"))
    coord.get_child = MagicMock(return_value=Child(name="Mia", id="c1"))
    run(coord.async_reject_chore("comp1"))
    calls = _fired(coord, "taskmate_chore_rejected")
    assert len(calls) == 1
    assert calls[0][0][1]["chore_name"] == "Bin"
