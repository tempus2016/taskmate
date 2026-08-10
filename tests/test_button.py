"""Tests for the button platform entities (TEST-1).

Buttons are thin wrappers over coordinator methods; we verify identity
(unique_id/name), icon resolution, attributes, and that a press dispatches
the right coordinator call. A stubbed coordinator avoids any HA runtime.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from custom_components.taskmate.button import ClaimRewardButton, CompleteChoreButton
from custom_components.taskmate.models import Child, Chore, Reward


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _entry():
    entry = MagicMock()
    entry.entry_id = "entry1"
    return entry


def _coord(child=None, chore=None, reward=None):
    coord = MagicMock()
    coord.get_child = MagicMock(return_value=child)
    coord.get_chore = MagicMock(return_value=chore)
    coord.get_reward = MagicMock(return_value=reward)
    coord.data = {"pending_reward_claims": []}
    coord.async_complete_chore = AsyncMock()
    coord.async_claim_reward = AsyncMock()
    return coord


def test_complete_chore_button_identity_and_icon():
    child = Child(name="Malia", id="ch1")
    chore = Chore(name="Dishes", points=5, id="cho1")
    coord = _coord(child=child, chore=chore)
    btn = CompleteChoreButton(coord, _entry(), child, chore)
    assert btn._attr_unique_id == "entry1_ch1_cho1_complete"
    assert btn._attr_name == "Malia: Complete Dishes"
    assert btn.icon == "mdi:check-circle"  # no picture set -> falls back
    attrs = btn.extra_state_attributes
    assert attrs["child_id"] == "ch1"
    assert attrs["chore_id"] == "cho1"
    assert attrs["points"] == 5


def test_complete_chore_button_press_dispatches():
    child = Child(name="Malia", id="ch1")
    chore = Chore(name="Dishes", id="cho1")
    coord = _coord(child=child, chore=chore)
    btn = CompleteChoreButton(coord, _entry(), child, chore)
    run(btn.async_press())
    coord.async_complete_chore.assert_awaited_once_with("cho1", "ch1")


def test_complete_chore_button_icon_fallback_when_chore_gone():
    child = Child(name="Malia", id="ch1")
    chore = Chore(name="Dishes", id="cho1")
    coord = _coord(child=child, chore=None)  # chore deleted
    btn = CompleteChoreButton(coord, _entry(), child, chore)
    assert btn.icon == "mdi:check-circle"


def test_complete_chore_button_press_swallows_value_error():
    child = Child(name="Malia", id="ch1")
    chore = Chore(name="Dishes", id="cho1")
    coord = _coord(child=child, chore=chore)
    coord.async_complete_chore = AsyncMock(side_effect=ValueError("nope"))
    btn = CompleteChoreButton(coord, _entry(), child, chore)
    run(btn.async_press())  # must not raise


def test_claim_reward_button_identity_and_press():
    child = Child(name="Leo", id="ch2")
    reward = Reward(name="Ice Cream", cost=30, icon="mdi:ice-cream", id="rw1")
    coord = _coord(child=child, reward=reward)
    btn = ClaimRewardButton(coord, _entry(), child, reward)
    assert btn._attr_unique_id == "entry1_ch2_rw1_claim"
    assert btn._attr_name == "Leo: Claim Ice Cream"
    assert btn.icon == "mdi:ice-cream"
    run(btn.async_press())
    coord.async_claim_reward.assert_awaited_once_with("rw1", "ch2")
