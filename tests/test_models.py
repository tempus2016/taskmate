"""Tests for custom_components.taskmate.models."""

from __future__ import annotations

import datetime as dt
from datetime import timezone

from custom_components.taskmate.models import (
    Bonus,
    Child,
    Chore,
    ChoreCompletion,
    PointsTransaction,
    PoolAllocation,
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

    def test_default_streak_milestones_serialises_to_empty_list(self):
        child = Child(name="Dana")
        data = child.to_dict()
        assert data["streak_milestones_achieved"] == []

    def test_default_awarded_perfect_weeks_serialises_to_empty_list(self):
        child = Child(name="Eve")
        data = child.to_dict()
        assert data["awarded_perfect_weeks"] == []

    def test_id_generated_when_missing(self):
        child = Child.from_dict({"name": "Frank"})
        assert len(child.id) > 0


# ---------------------------------------------------------------------------
# Child availability field
# ---------------------------------------------------------------------------


class TestChildAvailability:
    def test_default_is_empty(self):
        child = Child(name="Alice")
        assert child.availability_entity == ""

    def test_serialises_availability_entity(self):
        child = Child(name="Alice", availability_entity="binary_sensor.alice_home", id="kid1")
        restored = Child.from_dict(child.to_dict())
        assert restored.availability_entity == "binary_sensor.alice_home"

    def test_legacy_missing_availability_entity_backcompat(self):
        legacy = {"name": "Alice"}
        child = Child.from_dict(legacy)
        assert child.availability_entity == ""


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


class TestChoreRequireAvailability:
    def test_default_is_false(self):
        chore = Chore(name="Any")
        assert chore.require_availability is False

    def test_serialises_require_availability(self):
        chore = Chore(name="Dishes", require_availability=True, id="c1")
        restored = Chore.from_dict(chore.to_dict())
        assert restored.require_availability is True

    def test_legacy_missing_require_availability_backcompat(self):
        legacy = {"name": "Old chore"}
        chore = Chore.from_dict(legacy)
        assert chore.require_availability is False


class TestChoreSkipFields:
    def test_defaults(self):
        chore = Chore(name="Any")
        assert chore.skip_date == ""
        assert chore.skip_count == 0

    def test_roundtrip_preserves_skip_state(self):
        chore = Chore(name="Bins", skip_date="2026-04-24", skip_count=2, id="c1")
        restored = Chore.from_dict(chore.to_dict())
        assert restored.skip_date == "2026-04-24"
        assert restored.skip_count == 2

    def test_legacy_missing_skip_fields_backcompat(self):
        legacy = {"name": "Old chore"}
        chore = Chore.from_dict(legacy)
        assert chore.skip_date == ""
        assert chore.skip_count == 0


class TestTaskGroup:
    def test_defaults(self):
        from custom_components.taskmate.models import TaskGroup

        g = TaskGroup(name="Cat litter")
        assert g.policy == "sticky"
        assert g.chore_ids == []
        assert g.id  # generated

    def test_roundtrip(self):
        from custom_components.taskmate.models import TaskGroup

        g = TaskGroup(name="Cat litter", policy="spread", chore_ids=["c1", "c2"], id="g1")
        restored = TaskGroup.from_dict(g.to_dict())
        assert restored.name == g.name
        assert restored.policy == "spread"
        assert restored.chore_ids == ["c1", "c2"]
        assert restored.id == "g1"


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
        assert reward.pool_enabled is False

    def test_roundtrip(self):
        reward = Reward(
            name="Pizza dinner",
            cost=100,
            description="Any pizza you want",
            icon="mdi:pizza",
            assigned_to=["child1"],
            is_jackpot=True,
            pool_enabled=True,
            id="reward01",
        )
        restored = Reward.from_dict(reward.to_dict())
        assert restored.name == reward.name
        assert restored.cost == reward.cost
        assert restored.is_jackpot == reward.is_jackpot
        assert restored.pool_enabled is True
        assert restored.id == reward.id

    def test_legacy_missing_pool_enabled_defaults_to_false(self):
        legacy = {"name": "Old reward", "cost": 20, "id": "r1"}
        reward = Reward.from_dict(legacy)
        assert reward.pool_enabled is False

    def test_quantity_and_expires_at_defaults(self):
        reward = Reward(name="Ice cream")
        assert reward.quantity is None
        assert reward.expires_at is None

    def test_quantity_and_expires_at_roundtrip(self):
        reward = Reward(
            name="Movie tickets",
            cost=200,
            quantity=3,
            expires_at="2024-12-31",
            id="r_movie",
        )
        restored = Reward.from_dict(reward.to_dict())
        assert restored.quantity == 3
        assert restored.expires_at == "2024-12-31"

    def test_legacy_missing_quantity_and_expires_at_backcompat(self):
        legacy = {"name": "Old reward", "cost": 20, "id": "r1"}
        reward = Reward.from_dict(legacy)
        assert reward.quantity is None
        assert reward.expires_at is None


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


# ---------------------------------------------------------------------------
# Chore one-shot fields
# ---------------------------------------------------------------------------


class TestChoreOneShotFields:
    def test_new_fields_defaults(self):
        chore = Chore(name="Test")
        assert chore.enabled is True
        assert chore.disabled_for == []
        assert chore.created_date == ""

    def test_one_shot_roundtrip(self):
        chore = Chore(
            name="Wash car",
            schedule_mode="one_shot",
            daily_limit=1,
            enabled=True,
            disabled_for=["kid1"],
            created_date="2024-03-20",
        )
        d = chore.to_dict()
        assert d["enabled"] is True
        assert d["disabled_for"] == ["kid1"]
        assert d["created_date"] == "2024-03-20"
        assert d["schedule_mode"] == "one_shot"

        restored = Chore.from_dict(d)
        assert restored.enabled is True
        assert restored.disabled_for == ["kid1"]
        assert restored.created_date == "2024-03-20"
        assert restored.schedule_mode == "one_shot"

    def test_legacy_chore_missing_new_fields(self):
        """Old chore dicts without enabled/disabled_for/created_date should load with defaults."""
        legacy = {
            "name": "Old chore",
            "points": 5,
            "schedule_mode": "specific_days",
            "id": "legacy123",
        }
        chore = Chore.from_dict(legacy)
        assert chore.enabled is True
        assert chore.disabled_for == []
        assert chore.created_date == ""

    def test_disabled_chore_roundtrip(self):
        chore = Chore(
            name="Expired task",
            schedule_mode="one_shot",
            enabled=False,
            disabled_for=["kid1", "kid2"],
            created_date="2024-03-19",
        )
        restored = Chore.from_dict(chore.to_dict())
        assert restored.enabled is False
        assert restored.disabled_for == ["kid1", "kid2"]


# ---------------------------------------------------------------------------
# Bonus model
# ---------------------------------------------------------------------------


class TestBonus:
    def test_defaults(self):
        bonus = Bonus(name="Tidied bedroom", points=5)
        assert bonus.description == ""
        assert bonus.icon == "mdi:star-circle-outline"
        assert bonus.assigned_to == []
        assert bonus.id

    def test_roundtrip(self):
        bonus = Bonus(
            name="Helped with dishes",
            points=10,
            description="Cleared and washed up",
            icon="mdi:silverware-fork-knife",
            assigned_to=["kid1", "kid2"],
            id="bonus001",
        )
        restored = Bonus.from_dict(bonus.to_dict())
        assert restored.name == bonus.name
        assert restored.points == bonus.points
        assert restored.description == bonus.description
        assert restored.icon == bonus.icon
        assert restored.assigned_to == bonus.assigned_to
        assert restored.id == bonus.id

    def test_legacy_missing_fields(self):
        legacy = {"name": "Old bonus", "points": 3, "id": "legacy"}
        bonus = Bonus.from_dict(legacy)
        assert bonus.description == ""
        assert bonus.icon == "mdi:star-circle-outline"
        assert bonus.assigned_to == []
        assert bonus.id == "legacy"


# ---------------------------------------------------------------------------
# PoolAllocation (v3.0 pool mode)
# ---------------------------------------------------------------------------


class TestPoolAllocationModel:
    def test_defaults(self):
        pa = PoolAllocation(child_id="kid1", reward_id="reward1")
        assert pa.child_id == "kid1"
        assert pa.reward_id == "reward1"
        assert pa.allocated_points == 0
        assert pa.id  # auto-generated

    def test_roundtrip(self):
        pa = PoolAllocation(
            child_id="kid1",
            reward_id="rewardA",
            allocated_points=30,
            id="alloc001",
        )
        restored = PoolAllocation.from_dict(pa.to_dict())
        assert restored.child_id == pa.child_id
        assert restored.reward_id == pa.reward_id
        assert restored.allocated_points == pa.allocated_points
        assert restored.id == pa.id

    def test_legacy_missing_fields(self):
        legacy = {"child_id": "kid1", "reward_id": "reward1", "id": "legacy"}
        pa = PoolAllocation.from_dict(legacy)
        assert pa.allocated_points == 0
        assert pa.id == "legacy"


# ---------------------------------------------------------------------------
# Child notify_service field
# ---------------------------------------------------------------------------


def test_child_notify_service_round_trip():
    c = Child(name="Maria", notify_service="notify.mobile_app_marias_tablet")
    assert c.notify_service == "notify.mobile_app_marias_tablet"
    restored = Child.from_dict(c.to_dict())
    assert restored.notify_service == "notify.mobile_app_marias_tablet"


def test_child_notify_service_defaults_none():
    c = Child(name="Maria")
    assert c.notify_service is None
    restored = Child.from_dict(c.to_dict())
    assert restored.notify_service is None


# ---------------------------------------------------------------------------
# Notification dataclasses
# ---------------------------------------------------------------------------


def test_parent_recipient_round_trip():
    from custom_components.taskmate.models import ParentRecipient

    p = ParentRecipient(name="John", notify_service="notify.mobile_app_johns_iphone")
    assert p.id.startswith("parent:")
    assert p.enabled is True
    restored = ParentRecipient.from_dict(p.to_dict())
    assert restored.id == p.id
    assert restored.name == "John"
    assert restored.notify_service == "notify.mobile_app_johns_iphone"


def test_notification_route_round_trip():
    from custom_components.taskmate.models import NotificationRoute

    r = NotificationRoute(enabled=True, time="19:30")
    d = r.to_dict()
    assert d == {"enabled": True, "time": "19:30"}
    assert NotificationRoute.from_dict(d) == r
    assert NotificationRoute.from_dict({"enabled": False}).time is None


def test_notification_config_round_trip():
    from custom_components.taskmate.models import NotificationConfig, NotificationRoute

    cfg = NotificationConfig(
        type_id="bedtime_reminder",
        master_enabled=True,
        routes={"child:abc": NotificationRoute(enabled=True, time="19:30")},
    )
    restored = NotificationConfig.from_dict(cfg.to_dict())
    assert restored.master_enabled is True
    assert restored.routes["child:abc"].time == "19:30"


def test_custom_notification_round_trip():
    from custom_components.taskmate.models import CustomNotification

    n = CustomNotification(
        name="Brush teeth",
        message_template="Time to brush, {child_name}!",
        time="20:30",
        day_mask=0b1111111,
        recipient_ids=["child:abc", "parent:xyz"],
    )
    assert n.id  # uuid
    restored = CustomNotification.from_dict(n.to_dict())
    assert restored.id == n.id
    assert restored.day_mask == 0b1111111
    assert restored.recipient_ids == ["child:abc", "parent:xyz"]


def test_notification_config_nav_url_roundtrip():
    from custom_components.taskmate.models import NotificationConfig

    cfg = NotificationConfig(type_id="badge_earned", nav_url="/lovelace/parents")
    d = cfg.to_dict()
    assert d["nav_url"] == "/lovelace/parents"
    assert NotificationConfig.from_dict(d).nav_url == "/lovelace/parents"


def test_notification_config_nav_url_omitted_when_empty():
    from custom_components.taskmate.models import NotificationConfig

    cfg = NotificationConfig(type_id="badge_earned")
    assert "nav_url" not in cfg.to_dict()
    assert NotificationConfig.from_dict({"type_id": "x"}).nav_url == ""


def test_notification_config_group_roundtrip():
    from custom_components.taskmate.models import NotificationConfig

    cfg = NotificationConfig(type_id="badge_earned", group="taskmate-badges")
    d = cfg.to_dict()
    assert d["group"] == "taskmate-badges"
    assert NotificationConfig.from_dict(d).group == "taskmate-badges"


def test_notification_config_group_omitted_when_empty():
    from custom_components.taskmate.models import NotificationConfig

    cfg = NotificationConfig(type_id="badge_earned")
    assert "group" not in cfg.to_dict()
    assert NotificationConfig.from_dict({"type_id": "x"}).group == ""


def test_notification_config_from_dict_drops_non_string_group_and_nav_url():
    # Imported backups aren't field-validated, so a truthy non-string must
    # fall back to "" instead of crashing .strip() in dispatch later.
    from custom_components.taskmate.models import NotificationConfig

    for bad in ({"x": 1}, ["a"], 7, True):
        cfg = NotificationConfig.from_dict({"type_id": "badge_earned", "group": bad, "nav_url": bad})
        assert cfg.group == ""
        assert cfg.nav_url == ""
