"""A reward's Claim button is offered exactly when claiming would work.

The button used to answer "can they afford it" from the wallet alone, which
disagreed with the claim itself in both directions: a jackpot and a filled
savings jar are not paid from the wallet, and a sold-out, expired, time-locked
or already-claimed reward cannot be claimed however many points a child has.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.button import ClaimRewardButton
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc


def _run(coro_factory):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro_factory())
    finally:
        loop.close()
        asyncio.set_event_loop(None)


async def _make_system():
    from tests.conftest import FakeHass, FakeStore

    hass = FakeHass()
    hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    await storage.async_load()

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.data = {}
    coord.storage = storage
    coord._unsub_midnight = None
    coord._unsub_prune = None
    coord._unsub_availability = None
    coord.async_refresh = AsyncMock()
    coord.notifications = AsyncMock()
    return coord


def _entry():
    entry = MagicMock()
    entry.entry_id = "entry1"
    return entry


def _button(coord, child, reward):
    button = object.__new__(ClaimRewardButton)
    button.coordinator = coord
    button._entry = _entry()
    button.child_id = child.id
    button.reward_id = reward.id
    return button


async def _setup(*, wallet=0, **reward_kwargs):
    coord = await _make_system()
    child = await coord.async_add_child("Alice")
    child.points = wallet
    coord.storage.update_child(child)
    reward = await coord.async_add_reward(name="Trampoline", cost=50, **reward_kwargs)
    return coord, child, reward


# ── a jackpot is paid from the shared pool ───────────────────────────────


def test_a_funded_jackpot_is_offered_to_a_child_with_an_empty_wallet():
    async def scenario():
        coord, child, reward = await _setup(wallet=0, is_jackpot=True)
        other = await coord.async_add_child("Bob")
        other.points = 50
        coord.storage.update_child(other)
        await coord.async_allocate_points_to_pool(other.id, reward.id, 50)
        button = _button(coord, child, reward)
        return button.available, button.extra_state_attributes

    available, attrs = _run(scenario)
    assert available is True
    assert attrs["can_afford"] is True
    assert attrs["points_needed"] == 0


def test_an_unfunded_jackpot_is_not_offered_to_a_rich_child():
    async def scenario():
        coord, child, reward = await _setup(wallet=500, is_jackpot=True)
        button = _button(coord, child, reward)
        return button.available, button.extra_state_attributes

    available, attrs = _run(scenario)
    assert available is False  # a jackpot never comes out of one wallet
    assert attrs["can_afford"] is False
    assert attrs["points_needed"] == 50


# ── an ordinary reward may be paid from a savings jar ────────────────────


def test_a_filled_savings_jar_is_offered_to_a_child_with_an_empty_wallet():
    async def scenario():
        coord, child, reward = await _setup(wallet=50, pool_enabled=True)
        await coord.async_allocate_points_to_pool(child.id, reward.id, 50)
        assert coord.get_child(child.id).points == 0  # it is all in the jar
        button = _button(coord, child, reward)
        return button.available, button.extra_state_attributes

    available, attrs = _run(scenario)
    assert available is True
    assert attrs["can_afford"] is True


def test_a_wallet_that_covers_the_cost_is_still_offered():
    async def scenario():
        coord, child, reward = await _setup(wallet=50)
        button = _button(coord, child, reward)
        return button.available, button.extra_state_attributes

    available, attrs = _run(scenario)
    assert available is True
    assert attrs["can_afford"] is True
    assert attrs["available_points"] == 50


def test_a_wallet_that_falls_short_is_not_offered():
    async def scenario():
        coord, child, reward = await _setup(wallet=49)
        button = _button(coord, child, reward)
        return button.available, button.extra_state_attributes

    available, attrs = _run(scenario)
    assert available is False
    assert attrs["points_needed"] == 1


# ── rules that have nothing to do with money ─────────────────────────────


def test_a_sold_out_reward_is_not_offered():
    async def scenario():
        coord, child, reward = await _setup(wallet=500, quantity=0)
        return _button(coord, child, reward).available

    assert _run(scenario) is False


def test_an_expired_reward_is_not_offered():
    async def scenario():
        from homeassistant.util import dt as dt_util

        gone = (dt_util.now().date() - dt.timedelta(days=1)).isoformat()
        coord, child, reward = await _setup(wallet=500, expires_at=gone)
        return _button(coord, child, reward).available

    assert _run(scenario) is False


def test_a_reward_assigned_to_a_sibling_is_not_offered():
    async def scenario():
        coord = await _make_system()
        child = await coord.async_add_child("Alice")
        child.points = 500
        coord.storage.update_child(child)
        sibling = await coord.async_add_child("Bob")
        reward = await coord.async_add_reward(name="Trampoline", cost=50, assigned_to=[sibling.id])
        return _button(coord, child, reward).available

    assert _run(scenario) is False


def test_a_reward_already_waiting_for_approval_is_not_offered_again():
    async def scenario():
        coord, child, reward = await _setup(wallet=500)
        await coord.async_claim_reward(reward.id, child.id)
        return _button(coord, child, reward).available

    assert _run(scenario) is False


def test_a_deleted_reward_leaves_the_button_unavailable():
    async def scenario():
        coord, child, reward = await _setup(wallet=500)
        button = _button(coord, child, reward)
        await coord.async_remove_reward(reward.id)
        return button.available, button.extra_state_attributes

    available, attrs = _run(scenario)
    assert available is False
    assert attrs == {}


# ── the button and the claim never disagree ──────────────────────────────


@pytest.mark.parametrize(
    "setup_kwargs",
    [
        {"wallet": 500},
        {"wallet": 49},
        {"wallet": 500, "quantity": 0},
        {"wallet": 500, "is_jackpot": True},
        {"wallet": 0},
    ],
)
def test_the_button_agrees_with_what_claiming_actually_does(setup_kwargs):
    async def scenario():
        coord, child, reward = await _setup(**setup_kwargs)
        button = _button(coord, child, reward)
        offered = button.available
        try:
            await coord.async_claim_reward(reward.id, child.id)
            claimable = True
        except ValueError:
            claimable = False
        return offered, claimable

    offered, claimable = _run(scenario)
    assert offered == claimable
