"""Tests for coord_badges."""
from __future__ import annotations

from unittest.mock import MagicMock
from datetime import datetime, timezone

from custom_components.taskmate.coord_badges import BUILTIN_CATALOGUE, resolve_metric, TRIGGER_METRICS, badge_relevant_to_trigger
from custom_components.taskmate.models import Badge, BadgeCriterion, Child, RewardClaim


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


class TestTriggerMap:
    def test_trigger_metrics_complete(self):
        assert "total_chores" in TRIGGER_METRICS["chore_completed"]
        assert "first_chore" in TRIGGER_METRICS["chore_completed"]
        assert "total_points" in TRIGGER_METRICS["points_changed"]
        assert "total_rewards" in TRIGGER_METRICS["reward_redeemed"]
        assert "first_reward" in TRIGGER_METRICS["reward_redeemed"]
        assert "current_streak" in TRIGGER_METRICS["streak_updated"]
        assert "best_streak" in TRIGGER_METRICS["streak_updated"]
        assert "perfect_weeks" in TRIGGER_METRICS["perfect_week"]

    def test_manual_trigger_includes_all(self):
        b = Badge(name="x", criteria=[BadgeCriterion("total_points", ">=", 5)])
        assert badge_relevant_to_trigger(b, "manual") is True

    def test_chore_trigger_skips_points_only_badge(self):
        b = Badge(name="x", criteria=[BadgeCriterion("total_points", ">=", 100)])
        assert badge_relevant_to_trigger(b, "chore_completed") is False

    def test_chore_trigger_matches_chore_badge(self):
        b = Badge(name="x", criteria=[BadgeCriterion("total_chores", ">=", 10)])
        assert badge_relevant_to_trigger(b, "chore_completed") is True

    def test_chore_trigger_matches_compound_badge(self):
        b = Badge(name="x", criteria=[
            BadgeCriterion("total_chores", ">=", 10),
            BadgeCriterion("total_points", ">=", 100),
        ])
        assert badge_relevant_to_trigger(b, "chore_completed") is True

    def test_no_criteria_only_matches_manual(self):
        b = Badge(name="x", criteria=[])
        assert badge_relevant_to_trigger(b, "chore_completed") is False
        assert badge_relevant_to_trigger(b, "manual") is True

    def test_unknown_trigger_no_match(self):
        b = Badge(name="x", criteria=[BadgeCriterion("total_points", ">=", 5)])
        assert badge_relevant_to_trigger(b, "made_up") is False


import pytest
from unittest.mock import AsyncMock, MagicMock
from custom_components.taskmate.coord_badges import BadgeCoordinator


@pytest.fixture
def coord():
    hass = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    storage = MagicMock()
    storage.async_save = AsyncMock()
    points_coord = MagicMock()
    points_coord.add_points = AsyncMock()
    points_coord.remove_points = AsyncMock()
    return BadgeCoordinator(hass, storage, points_coord)


class TestBadgeCoordinatorBasic:
    async def test_evaluate_no_child_returns_empty(self, coord):
        coord.storage.get_child.return_value = None
        result = await coord.evaluate_for_child("missing", "chore_completed")
        assert result == []


class TestEvaluationCore:
    def _setup(self, coord, child_kwargs=None, badges=None, awarded=None):
        from custom_components.taskmate.models import Child
        kwargs = {
            "name": "Mia",
            "total_points_earned": 0,
            "total_chores_completed": 0,
            "current_streak": 0,
            "best_streak": 0,
            "awarded_perfect_weeks": [],
        }
        if child_kwargs:
            kwargs.update(child_kwargs)
        child = Child(**kwargs)
        child.id = "c1"
        coord.storage.get_child.return_value = child
        coord.storage.get_badges.return_value = badges or []
        coord.storage.get_reward_claims.return_value = []
        coord.storage.has_awarded.side_effect = lambda cid, bid: any(
            a.child_id == cid and a.badge_id == bid for a in (awarded or [])
        )
        coord.storage.get_awarded_badges_for_child.return_value = awarded or []
        return child

    async def test_passing_criterion_creates_award(self, coord):
        b = Badge(
            name="100 Points",
            criteria=[BadgeCriterion("total_points", ">=", 100)],
        )
        b.id = "b1"
        self._setup(coord, child_kwargs={"total_points_earned": 150}, badges=[b])

        awards = await coord.evaluate_for_child("c1", "points_changed")
        assert len(awards) == 1
        assert awards[0].badge_id == "b1"
        assert awards[0].child_id == "c1"
        assert awards[0].silent is False
        coord.storage.add_awarded_badge.assert_called_once()

    async def test_failing_criterion_no_award(self, coord):
        b = Badge(
            name="100 Points",
            criteria=[BadgeCriterion("total_points", ">=", 100)],
        )
        b.id = "b1"
        self._setup(coord, child_kwargs={"total_points_earned": 50}, badges=[b])

        awards = await coord.evaluate_for_child("c1", "points_changed")
        assert awards == []

    async def test_already_awarded_no_double_award(self, coord):
        from custom_components.taskmate.models import AwardedBadge
        b = Badge(
            name="100 Points",
            criteria=[BadgeCriterion("total_points", ">=", 100)],
        )
        b.id = "b1"
        prior = AwardedBadge(child_id="c1", badge_id="b1")
        self._setup(
            coord,
            child_kwargs={"total_points_earned": 150},
            badges=[b],
            awarded=[prior],
        )
        awards = await coord.evaluate_for_child("c1", "points_changed")
        assert awards == []

    async def test_disabled_badge_skipped(self, coord):
        b = Badge(
            name="100 Points",
            criteria=[BadgeCriterion("total_points", ">=", 100)],
            enabled=False,
        )
        b.id = "b1"
        self._setup(coord, child_kwargs={"total_points_earned": 150}, badges=[b])
        awards = await coord.evaluate_for_child("c1", "points_changed")
        assert awards == []

    async def test_assigned_to_filter(self, coord):
        b = Badge(
            name="100 Points",
            criteria=[BadgeCriterion("total_points", ">=", 100)],
            assigned_to=["c2"],
        )
        b.id = "b1"
        self._setup(coord, child_kwargs={"total_points_earned": 150}, badges=[b])
        awards = await coord.evaluate_for_child("c1", "points_changed")
        assert awards == []

    async def test_and_criteria_all_must_pass(self, coord):
        b = Badge(
            name="Two Conditions",
            criteria=[
                BadgeCriterion("total_chores", ">=", 50),
                BadgeCriterion("current_streak", ">=", 7),
            ],
        )
        b.id = "b1"
        self._setup(
            coord,
            child_kwargs={"total_chores_completed": 100, "current_streak": 5},
            badges=[b],
        )
        awards = await coord.evaluate_for_child("c1", "manual")
        assert awards == []

        self._setup(
            coord,
            child_kwargs={"total_chores_completed": 100, "current_streak": 10},
            badges=[b],
        )
        awards = await coord.evaluate_for_child("c1", "manual")
        assert len(awards) == 1

    async def test_trigger_optimisation_skips_irrelevant(self, coord):
        b = Badge(
            name="100 Points",
            criteria=[BadgeCriterion("total_points", ">=", 100)],
        )
        b.id = "b1"
        self._setup(coord, child_kwargs={"total_points_earned": 150}, badges=[b])
        awards = await coord.evaluate_for_child("c1", "chore_completed")
        assert awards == []

    async def test_point_bonus_credited_via_points_coord(self, coord):
        b = Badge(
            name="With Bonus",
            criteria=[BadgeCriterion("total_points", ">=", 100)],
            point_bonus=50,
        )
        b.id = "b1"
        self._setup(coord, child_kwargs={"total_points_earned": 150}, badges=[b])
        awards = await coord.evaluate_for_child("c1", "points_changed")
        assert awards[0].bonus_credited == 50
        coord.points_coord.add_points.assert_awaited_once()
        call = coord.points_coord.add_points.call_args
        assert "Badge: With Bonus" in str(call)

    async def test_silent_award_skips_bonus_and_event(self, coord):
        b = Badge(
            name="With Bonus",
            criteria=[BadgeCriterion("total_points", ">=", 100)],
            point_bonus=50,
        )
        b.id = "b1"
        self._setup(coord, child_kwargs={"total_points_earned": 150}, badges=[b])
        awards = await coord.evaluate_for_child("c1", "manual", silent=True)
        assert len(awards) == 1
        assert awards[0].silent is True
        assert awards[0].bonus_credited == 0
        coord.points_coord.add_points.assert_not_awaited()
        coord.hass.bus.async_fire.assert_not_called()

    async def test_event_fired_on_normal_award(self, coord):
        b = Badge(
            name="100 Points",
            criteria=[BadgeCriterion("total_points", ">=", 100)],
        )
        b.id = "b1"
        self._setup(coord, child_kwargs={"total_points_earned": 150}, badges=[b])
        await coord.evaluate_for_child("c1", "points_changed")
        coord.hass.bus.async_fire.assert_called_once()
        event_name = coord.hass.bus.async_fire.call_args[0][0]
        assert event_name == "taskmate_badge_earned"

    async def test_manual_only_badge_does_not_auto_fire(self, coord):
        # Empty criteria = manual-only; never fires from any auto trigger
        b = Badge(name="Manual Only", criteria=[])
        b.id = "b1"
        self._setup(coord, child_kwargs={"total_points_earned": 5000}, badges=[b])
        awards = await coord.evaluate_for_child("c1", "points_changed")
        assert awards == []


class TestManualOps:
    async def test_award_manually_creates_award(self, coord):
        from custom_components.taskmate.models import Child
        child = Child(name="Mia")
        child.id = "c1"
        coord.storage.get_child.return_value = child
        b = Badge(name="Custom", point_bonus=30)
        b.id = "b1"
        coord.storage.get_badge.return_value = b
        coord.storage.has_awarded.return_value = False

        award = await coord.award_manually("c1", "b1")
        assert award is not None
        assert award.manually_awarded is True
        assert award.bonus_credited == 30
        coord.points_coord.add_points.assert_awaited_once()

    async def test_award_manually_blocks_double(self, coord):
        coord.storage.has_awarded.return_value = True
        coord.storage.get_badge.return_value = Badge(name="x")
        from custom_components.taskmate.models import Child
        child = Child(name="Mia"); child.id = "c1"
        coord.storage.get_child.return_value = child
        award = await coord.award_manually("c1", "b1")
        assert award is None

    async def test_award_manually_missing_badge_returns_none(self, coord):
        from custom_components.taskmate.models import Child
        child = Child(name="Mia"); child.id = "c1"
        coord.storage.get_child.return_value = child
        coord.storage.get_badge.return_value = None
        award = await coord.award_manually("c1", "missing")
        assert award is None

    async def test_revoke_with_bonus_credited_reverses_points(self, coord):
        from custom_components.taskmate.models import AwardedBadge
        a = AwardedBadge(child_id="c1", badge_id="b1", bonus_credited=50)
        coord.storage.get_awarded_badges.return_value = [a]
        coord.storage.get_badge.return_value = Badge(name="X")

        result = await coord.revoke(a.id)
        assert result is True
        coord.storage.remove_awarded_badge.assert_called_once_with(a.id)
        coord.points_coord.remove_points.assert_awaited_once()

    async def test_revoke_zero_bonus_no_points_change(self, coord):
        from custom_components.taskmate.models import AwardedBadge
        a = AwardedBadge(child_id="c1", badge_id="b1", bonus_credited=0)
        coord.storage.get_awarded_badges.return_value = [a]
        coord.storage.get_badge.return_value = Badge(name="X")

        await coord.revoke(a.id)
        coord.points_coord.remove_points.assert_not_awaited()

    async def test_revoke_missing_returns_false(self, coord):
        coord.storage.get_awarded_badges.return_value = []
        result = await coord.revoke("nothing-here")
        assert result is False

    async def test_rebuild_walks_all_children_silently(self, coord):
        from custom_components.taskmate.models import Child
        c1 = Child(name="Mia"); c1.id = "c1"
        c2 = Child(name="Leo"); c2.id = "c2"
        coord.storage.get_children.return_value = [c1, c2]
        coord.storage.get_child.side_effect = lambda i: {"c1": c1, "c2": c2}.get(i)
        coord.storage.get_badges.return_value = []

        total = await coord.rebuild_all()
        assert total == 0
        assert coord.storage.get_child.call_count == 2
