"""Tests for custom_components.taskmate.models."""
from __future__ import annotations

import datetime as dt
from datetime import timezone

import pytest

from custom_components.taskmate.models import (
    Child,
    Chore,
    ChoreCompletion,
    PointsTransaction,
    Reward,
    RewardClaim,
    format_datetime,
    parse_datetime,
)

UTC = timezone.utc


# ---------------------------------------------------------------------------
# parse_datetime
# ---------------------------------------------------------------------------

class TestParseDatetime:
    def test_none_returns_none(self):
        assert parse_datetime(None) is None

    def test_naive_datetime_gets_utc(self):
        naive = dt.datetime(2024, 1, 15, 10, 0, 0)
        result = parse_datetime(naive)
        assert result.tzinfo == UTC
        assert result.replace(tzinfo=None) == naive

    def test_aware_datetime_returned_unchanged(self):
        aware = dt.datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        assert parse_datetime(aware) is aware

    def test_naive_iso_string_gets_utc(self):
        result = parse_datetime("2024-01-15T10:00:00")
        assert result.tzinfo == UTC
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_aware_iso_string_with_z_offset(self):
        result = parse_datetime("2024-01-15T10:00:00+00:00")
        assert result.tzinfo is not None
        assert result.year == 2024

    def test_aware_iso_string_with_positive_offset(self):
        result = parse_datetime("2024-01-15T12:00:00+02:00")
        assert result.tzinfo is not None
        assert result.hour == 12


# ---------------------------------------------------------------------------
# format_datetime
# ---------------------------------------------------------------------------

class TestFormatDatetime:
    def test_none_returns_none(self):
        assert format_datetime(None) is None

    def test_utc_datetime_uses_z_suffix(self):
        d = dt.datetime(2024, 6, 1, 8, 30, 0, tzinfo=UTC)
        result = format_datetime(d)
        assert result == "2024-06-01T08:30:00Z"

    def test_naive_datetime_treated_as_utc(self):
        naive = dt.datetime(2024, 6, 1, 8, 30, 0)
        result = format_datetime(naive)
        assert result == "2024-06-01T08:30:00Z"

    def test_non_utc_datetime_converted_to_utc(self):
        tz_plus2 = timezone(dt.timedelta(hours=2))
        d = dt.datetime(2024, 6, 1, 10, 0, 0, tzinfo=tz_plus2)
        result = format_datetime(d)
        # 10:00+02:00 → 08:00 UTC
        assert result == "2024-06-01T08:00:00Z"

    def test_roundtrip(self):
        original = dt.datetime(2024, 3, 15, 14, 22, 45, tzinfo=UTC)
        assert parse_datetime(format_datetime(original)) == original


# ---------------------------------------------------------------------------
# Child
# ---------------------------------------------------------------------------

class TestChild:
    def test_defaults(self):
        child = Child(name="Alice")
        assert child.points == 0
        assert child.current_streak == 0
        assert child.best_streak == 0
        assert child.avatar == "mdi:account-circle"
        assert child.pending_rewards == []
        assert child.chore_order == []
        assert child.streak_paused is False

    def test_roundtrip(self):
        child = Child(
            name="Bob",
            avatar="mdi:robot-happy",
            points=120,
            total_points_earned=300,
            total_chores_completed=25,
            current_streak=7,
            best_streak=14,
            last_completion_date="2024-03-19",
            streak_milestones_achieved=[3, 7],
            awarded_perfect_weeks=["2024-03-11"],
            id="abc12345",
        )
        restored = Child.from_dict(child.to_dict())
        assert restored.name == child.name
        assert restored.points == child.points
        assert restored.current_streak == child.current_streak
        assert restored.best_streak == child.best_streak
        assert restored.streak_milestones_achieved == child.streak_milestones_achieved
        assert restored.awarded_perfect_weeks == child.awarded_perfect_weeks
        assert restored.id == child.id

    def test_from_dict_missing_fields_use_defaults(self):
        child = Child.from_dict({"name": "Charlie"})
        assert child.points == 0
        assert child.current_streak == 0
        assert child.streak_milestones_achieved == []
        assert child.awarded_perfect_weeks == []

    def test_none_streak_milestones_serialises_to_empty_list(self):
        child = Child(name="Dana", streak_milestones_achieved=None)
        data = child.to_dict()
        assert data["streak_milestones_achieved"] == []

    def test_none_awarded_perfect_weeks_serialises_to_empty_list(self):
        child = Child(name="Eve", awarded_perfect_weeks=None)
        data = child.to_dict()
        assert data["awarded_perfect_weeks"] == []

    def test_id_generated_when_missing(self):
        child = Child.from_dict({"name": "Frank"})
        assert len(child.id) > 0


# ---------------------------------------------------------------------------
# Chore
# ---------------------------------------------------------------------------

class TestChore:
    def test_defaults(self):
        chore = Chore(name="Clean room")
        assert chore.points == 10
        assert chore.requires_approval is True
        assert chore.schedule_mode == "specific_days"
        assert chore.due_days == []
        assert chore.daily_limit == 1

    def test_roundtrip(self):
        chore = Chore(
            name="Wash dishes",
            points=15,
            description="After dinner",
            assigned_to=["child1", "child2"],
            requires_approval=False,
            time_category="evening",
            daily_limit=2,
            schedule_mode="specific_days",
            due_days=["monday", "wednesday", "friday"],
            id="chore001",
        )
        restored = Chore.from_dict(chore.to_dict())
        assert restored.name == chore.name
        assert restored.points == chore.points
        assert restored.assigned_to == chore.assigned_to
        assert restored.due_days == chore.due_days
        assert restored.id == chore.id

    def test_legacy_migration_due_days_without_schedule_mode(self):
        """Old data with due_days but no schedule_mode should default to specific_days."""
        data = {
            "name": "Old chore",
            "due_days": ["monday", "tuesday"],
            # intentionally no "schedule_mode" key
        }
        chore = Chore.from_dict(data)
        assert chore.schedule_mode == "specific_days"
        assert chore.due_days == ["monday", "tuesday"]

    def test_schedule_mode_recurring_preserved(self):
        chore = Chore(name="Exercise", schedule_mode="recurring", recurrence="weekly")
        restored = Chore.from_dict(chore.to_dict())
        assert restored.schedule_mode == "recurring"
        assert restored.recurrence == "weekly"


# ---------------------------------------------------------------------------
# Reward
# ---------------------------------------------------------------------------

class TestReward:
    def test_defaults(self):
        reward = Reward(name="Movie night")
        assert reward.cost == 50
        assert reward.icon == "mdi:gift"
        assert reward.assigned_to == []
        assert reward.is_jackpot is False

    def test_roundtrip(self):
        reward = Reward(
            name="Pizza dinner",
            cost=100,
            description="Any pizza you want",
            icon="mdi:pizza",
            assigned_to=["child1"],
            is_jackpot=True,
            id="reward01",
        )
        restored = Reward.from_dict(reward.to_dict())
        assert restored.name == reward.name
        assert restored.cost == reward.cost
        assert restored.is_jackpot == reward.is_jackpot
        assert restored.id == reward.id


# ---------------------------------------------------------------------------
# ChoreCompletion
# ---------------------------------------------------------------------------

class TestChoreCompletion:
    def test_roundtrip(self):
        comp = ChoreCompletion(
            chore_id="chore1",
            child_id="child1",
            completed_at=dt.datetime(2024, 3, 19, 15, 0, 0, tzinfo=UTC),
            approved=True,
            approved_at=dt.datetime(2024, 3, 19, 16, 0, 0, tzinfo=UTC),
            points_awarded=20,
            id="comp001",
        )
        restored = ChoreCompletion.from_dict(comp.to_dict())
        assert restored.chore_id == comp.chore_id
        assert restored.child_id == comp.child_id
        assert restored.approved == comp.approved
        assert restored.points_awarded == comp.points_awarded
        assert restored.id == comp.id

    def test_completed_at_datetime_preserved(self):
        original = dt.datetime(2024, 3, 19, 15, 30, 0, tzinfo=UTC)
        comp = ChoreCompletion(chore_id="c", child_id="k", completed_at=original)
        restored = ChoreCompletion.from_dict(comp.to_dict())
        assert restored.completed_at == original

    def test_approved_at_none(self):
        comp = ChoreCompletion(
            chore_id="c",
            child_id="k",
            completed_at=dt.datetime(2024, 3, 19, 0, 0, 0, tzinfo=UTC),
            approved=False,
        )
        data = comp.to_dict()
        assert data["approved_at"] is None
        restored = ChoreCompletion.from_dict(data)
        assert restored.approved_at is None

    def test_pending_completion_defaults(self):
        comp = ChoreCompletion.from_dict(
            {
                "chore_id": "c1",
                "child_id": "k1",
                "completed_at": "2024-03-19T10:00:00Z",
            }
        )
        assert comp.approved is False
        assert comp.points_awarded == 0


# ---------------------------------------------------------------------------
# RewardClaim
# ---------------------------------------------------------------------------

class TestRewardClaim:
    def test_roundtrip(self):
        claim = RewardClaim(
            reward_id="reward1",
            child_id="child1",
            claimed_at=dt.datetime(2024, 3, 19, 12, 0, 0, tzinfo=UTC),
            approved=True,
            approved_at=dt.datetime(2024, 3, 19, 13, 0, 0, tzinfo=UTC),
            id="claim01",
        )
        restored = RewardClaim.from_dict(claim.to_dict())
        assert restored.reward_id == claim.reward_id
        assert restored.child_id == claim.child_id
        assert restored.approved == claim.approved
        assert restored.id == claim.id

    def test_pending_claim_defaults(self):
        claim = RewardClaim.from_dict(
            {
                "reward_id": "r1",
                "child_id": "k1",
                "claimed_at": "2024-03-19T10:00:00Z",
            }
        )
        assert claim.approved is False
        assert claim.approved_at is None


# ---------------------------------------------------------------------------
# PointsTransaction
# ---------------------------------------------------------------------------

class TestPointsTransaction:
    def test_roundtrip(self):
        tx = PointsTransaction(
            child_id="child1",
            points=25,
            reason="Bonus for helping",
            created_at=dt.datetime(2024, 3, 19, 9, 0, 0, tzinfo=UTC),
            id="tx001",
        )
        restored = PointsTransaction.from_dict(tx.to_dict())
        assert restored.child_id == tx.child_id
        assert restored.points == tx.points
        assert restored.reason == tx.reason
        assert restored.id == tx.id

    def test_negative_points_preserved(self):
        tx = PointsTransaction(
            child_id="child1",
            points=-10,
            reason="Penalty",
            created_at=dt.datetime(2024, 3, 19, 9, 0, 0, tzinfo=UTC),
        )
        restored = PointsTransaction.from_dict(tx.to_dict())
        assert restored.points == -10
