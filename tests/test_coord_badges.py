"""Tests for coord_badges."""
from __future__ import annotations

from unittest.mock import MagicMock
from datetime import datetime, timezone

from custom_components.taskmate.coord_badges import BUILTIN_CATALOGUE, resolve_metric
from custom_components.taskmate.models import Badge, Child, RewardClaim


class TestBuiltinCatalogue:
    def test_has_15_builtins(self):
        assert len(BUILTIN_CATALOGUE) == 15

    def test_all_marked_builtin(self):
        for b in BUILTIN_CATALOGUE:
            assert isinstance(b, Badge)
            assert b.builtin is True
            assert b.id.startswith("builtin.")

    def test_first_chore_present(self):
        ids = {b.id for b in BUILTIN_CATALOGUE}
        assert "builtin.first_chore" in ids
        assert "builtin.30_day_streak" in ids

    def test_tiers_distributed(self):
        tiers = {b.tier for b in BUILTIN_CATALOGUE}
        assert tiers == {"bronze", "silver", "gold", "platinum"}


class TestResolveMetric:
    def _child(self, **kwargs):
        defaults = {
            "name": "Mia",
            "total_points_earned": 0,
            "total_chores_completed": 0,
            "current_streak": 0,
            "best_streak": 0,
            "awarded_perfect_weeks": [],
        }
        defaults.update(kwargs)
        return Child(**defaults)

    def test_total_points(self):
        storage = MagicMock()
        child = self._child(total_points_earned=347)
        assert resolve_metric("total_points", child, storage) == 347

    def test_total_chores(self):
        storage = MagicMock()
        child = self._child(total_chores_completed=22)
        assert resolve_metric("total_chores", child, storage) == 22

    def test_current_streak(self):
        storage = MagicMock()
        child = self._child(current_streak=5)
        assert resolve_metric("current_streak", child, storage) == 5

    def test_best_streak(self):
        storage = MagicMock()
        child = self._child(best_streak=12)
        assert resolve_metric("best_streak", child, storage) == 12

    def test_perfect_weeks(self):
        storage = MagicMock()
        child = self._child(awarded_perfect_weeks=["2026-W17", "2026-W18"])
        assert resolve_metric("perfect_weeks", child, storage) == 2

    def test_first_chore_metric_truthy(self):
        storage = MagicMock()
        child = self._child(total_chores_completed=1)
        assert resolve_metric("first_chore", child, storage) == 1

    def test_first_chore_metric_falsy(self):
        storage = MagicMock()
        child = self._child(total_chores_completed=0)
        assert resolve_metric("first_chore", child, storage) == 0

    def test_total_rewards_counts_approved(self):
        storage = MagicMock()
        now = datetime.now(timezone.utc)
        storage.get_reward_claims.return_value = [
            RewardClaim(reward_id="r1", child_id="c1", claimed_at=now, approved=True),
            RewardClaim(reward_id="r2", child_id="c1", claimed_at=now, approved=False),
            RewardClaim(reward_id="r3", child_id="c2", claimed_at=now, approved=True),
        ]
        child = self._child()
        child.id = "c1"
        assert resolve_metric("total_rewards", child, storage) == 1

    def test_first_reward_present(self):
        storage = MagicMock()
        now = datetime.now(timezone.utc)
        storage.get_reward_claims.return_value = [
            RewardClaim(reward_id="r1", child_id="c1", claimed_at=now, approved=True),
        ]
        child = self._child()
        child.id = "c1"
        assert resolve_metric("first_reward", child, storage) == 1

    def test_first_reward_no_claims(self):
        storage = MagicMock()
        storage.get_reward_claims.return_value = []
        child = self._child()
        child.id = "c1"
        assert resolve_metric("first_reward", child, storage) == 0

    def test_unknown_metric_returns_zero(self):
        storage = MagicMock()
        child = self._child()
        assert resolve_metric("nonsense", child, storage) == 0
