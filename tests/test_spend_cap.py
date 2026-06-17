"""Tests for the per-period reward spending cap."""
from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Reward, RewardClaim

UTC = dt.timezone.utc


def _coord(settings, rewards, claims):
    coord = object.__new__(TaskMateCoordinator)
    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d="": settings.get(k, d))
    storage.get_rewards = MagicMock(return_value=rewards)
    storage.get_reward_claims = MagicMock(return_value=claims)
    coord.storage = storage
    return coord


def _approved_claim(child, reward_id, when):
    return RewardClaim(reward_id=reward_id, child_id=child, claimed_at=when,
                       approved=True, approved_at=when, id=f"cl-{reward_id}-{when.day}")


REWARDS = [Reward(name="Movie", cost=30, id="r1"), Reward(name="Toy", cost=50, id="r2")]


def test_disabled_never_raises():
    coord = _coord({"spend_cap_enabled": False, "spend_cap_amount": "10"}, REWARDS, [])
    coord._enforce_spend_cap("c1", 9999)  # no raise


def test_under_cap_ok():
    now = dt.datetime(2026, 6, 17, 12, tzinfo=UTC)  # Wednesday
    claims = [_approved_claim("c1", "r1", now)]  # spent 30 this week
    coord = _coord({"spend_cap_enabled": True, "spend_cap_period": "weekly",
                    "spend_cap_amount": "100"}, REWARDS, claims)
    with patch("homeassistant.util.dt.now", return_value=now), \
         patch("homeassistant.util.dt.as_local", side_effect=lambda d: d):
        coord._enforce_spend_cap("c1", 50)  # 30 + 50 = 80 <= 100 -> ok


def test_over_cap_raises():
    now = dt.datetime(2026, 6, 17, 12, tzinfo=UTC)
    claims = [_approved_claim("c1", "r2", now)]  # spent 50 this week
    coord = _coord({"spend_cap_enabled": True, "spend_cap_period": "weekly",
                    "spend_cap_amount": "60"}, REWARDS, claims)
    with patch("homeassistant.util.dt.now", return_value=now), \
         patch("homeassistant.util.dt.as_local", side_effect=lambda d: d):
        with pytest.raises(ValueError, match="cap reached"):
            coord._enforce_spend_cap("c1", 30)  # 50 + 30 = 80 > 60


def test_prior_period_not_counted():
    now = dt.datetime(2026, 6, 17, 12, tzinfo=UTC)        # this week (Mon=15th)
    old = dt.datetime(2026, 6, 1, 12, tzinfo=UTC)         # earlier, different week
    claims = [_approved_claim("c1", "r2", old)]           # 50 spent earlier
    coord = _coord({"spend_cap_enabled": True, "spend_cap_period": "weekly",
                    "spend_cap_amount": "60"}, REWARDS, claims)
    with patch("homeassistant.util.dt.now", return_value=now), \
         patch("homeassistant.util.dt.as_local", side_effect=lambda d: d):
        coord._enforce_spend_cap("c1", 30)  # only this week counts -> 0 + 30 ok


def test_other_child_not_counted():
    now = dt.datetime(2026, 6, 17, 12, tzinfo=UTC)
    claims = [_approved_claim("c2", "r2", now)]  # sibling spent
    coord = _coord({"spend_cap_enabled": True, "spend_cap_period": "weekly",
                    "spend_cap_amount": "60"}, REWARDS, claims)
    with patch("homeassistant.util.dt.now", return_value=now), \
         patch("homeassistant.util.dt.as_local", side_effect=lambda d: d):
        coord._enforce_spend_cap("c1", 30)  # c1 spent 0 -> ok
