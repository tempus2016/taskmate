"""Size tests for the split TaskMate sensor attributes.

The overview sensor used to pack every data slice into a single attribute
payload, which Home Assistant's recorder drops once it exceeds 16 KB. This
test builds a stress fixture (4 children, 30 chores, 20 rewards, 200
completions, 50 transactions, 10 pending claims, penalties, bonuses) and
asserts that each of the five global sensors stays below the 16384-byte
limit for extra_state_attributes.
"""

from __future__ import annotations

import datetime as dt
import json
from datetime import timezone
from unittest.mock import MagicMock

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.models import (
    AwardedBadge,
    Badge,
    BadgeCriterion,
    Bonus,
    BonusSubTask,
    Child,
    Chore,
    ChoreCompletion,
    Penalty,
    PointsTransaction,
    PoolAllocation,
    Reward,
    RewardClaim,
)
from custom_components.taskmate.sensor import (
    ChildBadgesSensor,
    ChildStatsSensor,
    PendingApprovalsSensor,
)

from .conftest import dt_util_mock

MAX_ATTR_BYTES = 16384  # Home Assistant recorder limit
UTC = timezone.utc


def _stress_coordinator():
    """Build a coordinator with a deliberately large dataset."""
    children = [
        Child(
            name=f"Child {i}",
            avatar="mdi:face-man",
            points=250 + i,
            total_points_earned=1000 + i * 50,
            total_chores_completed=120 + i * 10,
            current_streak=5 + i,
            best_streak=20 + i,
            chore_order=[f"chore-{j:02d}" for j in range(30)],
            last_completion_date="2026-04-19",
            streak_milestones_achieved=[3, 7, 14],
            awarded_perfect_weeks=["2026-W15", "2026-W16"],
            id=f"child-{i}",
        )
        for i in range(4)
    ]

    chores = [
        Chore(
            name=f"Chore {i:02d}",
            description=f"Do chore number {i:02d} every day without fail",
            points=5 + (i % 10),
            time_category="anytime",
            daily_limit=1,
            assigned_to=[c.id for c in children],
            completion_sound="coin",
            due_days=["monday", "tuesday", "wednesday"],
            schedule_mode="specific_days",
            recurrence="weekly",
            recurrence_day="monday",
            recurrence_start="2026-01-01",
            first_occurrence_mode="available_immediately",
            visibility_entity="",
            visibility_operator="equals",
            visibility_state="on",
            enabled=True,
            disabled_for=[],
            created_date="2026-01-01",
            assignment_mode="everyone",
            assignment_rotation_anchor="2026-01-01",
            assignment_current_child_id=children[i % 4].id,
            publish_calendar_entities=[f"calendar.taskmate_child_{c.id}" for c in children],
            id=f"chore-{i:02d}",
        )
        for i in range(30)
    ]

    rewards = [
        Reward(
            name=f"Reward {i:02d}",
            cost=100 + i * 5,
            description=f"A nice reward labeled {i:02d}",
            icon="mdi:gift",
            assigned_to=[c.id for c in children],
            is_jackpot=(i % 5 == 0),
            pool_enabled=(i % 3 == 0),
            id=f"reward-{i:02d}",
        )
        for i in range(20)
    ]

    # Pin dt_util_mock._now so `_build_todays_completions` is deterministic
    # regardless of what previous tests in the session set it to.
    dt_util_mock._now = dt.datetime(2024, 4, 20, 9, 0, 0, tzinfo=UTC)
    now = dt.datetime(2024, 4, 20, 9, 0, 0, tzinfo=UTC)
    # Completions spread across ~17 days (~12 today, rest historical) so the
    # "todays_completions" slice reflects realistic single-day volume while
    # recent_completions still has plenty of history to exercise the cap.
    completions = [
        ChoreCompletion(
            chore_id=f"chore-{i % 30:02d}",
            child_id=children[i % 4].id,
            completed_at=now - dt.timedelta(hours=i * 2),
            approved=(i % 2 == 0),
            points_awarded=5 + (i % 10),
            id=f"completion-{i:04d}",
        )
        for i in range(200)
    ]

    points_transactions = [
        PointsTransaction(
            child_id=children[i % 4].id,
            points=(10 if i % 2 == 0 else -5),
            reason=f"Manual adjustment {i}",
            created_at=now - dt.timedelta(hours=i),
            id=f"tx-{i:03d}",
        )
        for i in range(50)
    ]

    pending_reward_claims = [
        RewardClaim(
            reward_id=f"reward-{i:02d}",
            child_id=children[i % 4].id,
            claimed_at=now - dt.timedelta(hours=i),
            approved=False,
            id=f"claim-{i:03d}",
        )
        for i in range(10)
    ]

    reward_claims = pending_reward_claims + [
        RewardClaim(
            reward_id=f"reward-{i:02d}",
            child_id=children[i % 4].id,
            claimed_at=now - dt.timedelta(days=i),
            approved=True,
            approved_at=now - dt.timedelta(days=i, hours=-1),
            id=f"approved-claim-{i:03d}",
        )
        for i in range(20)
    ]

    pool_allocations = [
        PoolAllocation(
            child_id=children[i % 4].id,
            reward_id=f"reward-{i % 20:02d}",
            allocated_points=25 + i,
            id=f"pool-{i:03d}",
        )
        for i in range(30)
    ]

    penalties = [
        Penalty(
            name=f"Penalty {i}",
            points=10 + i,
            description=f"Penalty description {i}",
            icon="mdi:alert",
            assigned_to=[c.id for c in children],
            id=f"pen-{i}",
        )
        for i in range(8)
    ]

    bonuses = [
        Bonus(
            name=f"Bonus {i}",
            points=15 + i,
            description=f"Bonus description {i}",
            icon="mdi:star",
            assigned_to=[c.id for c in children],
            id=f"bon-{i}",
        )
        for i in range(8)
    ]

    coord = MagicMock()
    coord.data = {
        "children": children,
        "chores": chores,
        "rewards": rewards,
        "completions": completions,
        "pending_completions": completions[:25],
        "reward_claims": reward_claims,
        "pending_reward_claims": pending_reward_claims,
        "points_transactions": points_transactions,
        "pool_allocations": pool_allocations,
        "penalties": penalties,
        "bonuses": bonuses,
        "points_name": "Stars",
        "points_icon": "mdi:star",
        "settings": {
            "streak_reset_mode": "reset",
            "weekend_multiplier": "2.0",
            "streak_milestones_enabled": "true",
            "streak_milestones": "3:5, 7:10, 14:20, 30:50, 60:100, 100:200",
            "perfect_week_enabled": "true",
            "perfect_week_bonus": "50",
        },
    }
    coord.is_pool_mode_claim = MagicMock(return_value=False)
    coord.is_chore_available_for_child = MagicMock(return_value=True)
    # Medium-difficulty chores award their base points (×1.0 baseline).
    coord.effective_chore_points = MagicMock(side_effect=lambda c: c.points)
    coord.level_info = MagicMock(
        side_effect=lambda c: {
            "level": (c.total_points_earned or 0) // 100 + 1,
            "progress": (c.total_points_earned or 0) % 100,
            "target": 100,
        }
    )
    coord.storage = MagicMock()
    coord.storage.get_last_completed = MagicMock(return_value={"current": "2026-04-20T08:00:00Z"})
    return coord


def _bytes(obj) -> int:
    """Approximate HA's state-attributes byte size."""
    return len(json.dumps(obj, default=str).encode("utf-8"))


def _assert_slice_under_limit(name: str, attrs: dict) -> None:
    size = _bytes(attrs)
    assert size < MAX_ATTR_BYTES, (
        f"{name} attribute payload is {size} bytes — exceeds the {MAX_ATTR_BYTES}-byte recorder limit"
    )


def test_overview_slice_under_limit():
    coord = _stress_coordinator()
    common = sensor_module._compute_common(coord)
    scalars = {
        "today_day_of_week": "monday",
        "streak_reset_mode": "reset",
        "weekend_multiplier": 2.0,
        "streak_milestones_enabled": True,
        "streak_milestones": "3:5, 7:10, 14:20, 30:50, 60:100, 100:200",
        "perfect_week_enabled": True,
        "perfect_week_bonus": 50,
        "total_children": len(common["children"]),
        "total_chores": len(common["chores"]),
        "total_rewards": len(common["rewards"]),
        "total_points_available": sum(c.points for c in common["children"]),
        "total_chores_completed": sum(c.total_chores_completed for c in common["children"]),
        "total_completions_all_time": len(common["all_completions"]),
        "total_pending_completions": len(common["pending_completions"]),
        "points_name": "Stars",
        "points_icon": "mdi:star",
        "children": sensor_module._build_children_summary(coord, common),
    }
    _assert_slice_under_limit("taskmate_overview", scalars)


def test_chores_slice_under_limit():
    coord = _stress_coordinator()
    common = sensor_module._compute_common(coord)
    attrs = {
        "chores": sensor_module._build_chores_list(coord, common),
        "todays_completions": sensor_module._build_todays_completions(common),
    }
    _assert_slice_under_limit("taskmate_chores", attrs)


def test_chore_availability_slice_under_limit():
    coord = _stress_coordinator()
    common = sensor_module._compute_common(coord)
    attrs = {
        "chore_availability": sensor_module._build_chore_availability(coord, common),
    }
    _assert_slice_under_limit("taskmate_chore_availability", attrs)


def test_rewards_slice_under_limit():
    coord = _stress_coordinator()
    common = sensor_module._compute_common(coord)
    attrs = {
        "rewards": sensor_module._build_rewards_list(common),
        "pending_reward_claims": sensor_module._build_pending_reward_claims(common),
        "pool_allocations": [pa.to_dict() for pa in common["pool_alloc_objs"]],
    }
    _assert_slice_under_limit("taskmate_rewards", attrs)


def test_activity_slice_under_limit():
    coord = _stress_coordinator()
    common = sensor_module._compute_common(coord)
    attrs = {
        "recent_completions": sensor_module._build_recent_completions(common),
        "recent_transactions": sensor_module._build_recent_transactions(common),
    }
    _assert_slice_under_limit("taskmate_activity", attrs)


def test_incentives_slice_under_limit():
    coord = _stress_coordinator()
    common = sensor_module._compute_common(coord)
    attrs = {
        "penalties": sensor_module._build_penalties_list(common),
        "bonuses": sensor_module._build_bonuses_list(common),
    }
    _assert_slice_under_limit("taskmate_incentives", attrs)


def test_common_context_is_cached_per_coordinator_update():
    coord = _stress_coordinator()
    first = sensor_module._compute_common(coord)
    second = sensor_module._compute_common(coord)
    # Same underlying coordinator.data id => cached dict is returned by reference
    assert first is second


def test_common_context_rebuilds_when_data_identity_changes():
    coord = _stress_coordinator()
    before = sensor_module._compute_common(coord)
    # Replace coordinator.data with a fresh dict to invalidate the cache
    coord.data = dict(coord.data)
    after = sensor_module._compute_common(coord)
    assert before is not after


class _MockEntry:
    entry_id = "test_entry"


class TestChildBadgesSensor:
    def _coordinator_for(self, child, badges, awarded):
        coord = MagicMock()
        coord.storage.get_child.return_value = child
        coord.storage.get_badges.return_value = badges
        coord.storage.get_awarded_badges_for_child.return_value = awarded
        coord.storage.get_reward_claims.return_value = []
        coord.get_child = lambda cid: child if (child and child.id == cid) else None
        return coord

    def test_state_is_earned_count(self, hass):
        child = Child(name="Mia")
        child.id = "c1"
        b1 = Badge(name="A")
        b1.id = "b1"
        b2 = Badge(name="B")
        b2.id = "b2"
        awarded = [
            AwardedBadge(child_id="c1", badge_id="b1"),
            AwardedBadge(child_id="c1", badge_id="b2"),
        ]
        coord = self._coordinator_for(child, [b1, b2], awarded)
        sensor = ChildBadgesSensor(coord, _MockEntry(), child)
        assert sensor.native_value == 2

    def test_attrs_include_earned_and_available(self, hass):
        child = Child(name="Mia", total_chores_completed=5)
        child.id = "c1"
        earned = Badge(name="Earned")
        earned.id = "earned"
        locked = Badge(
            name="Locked",
            criteria=[BadgeCriterion("total_chores", ">=", 10)],
        )
        locked.id = "locked"
        awarded = [AwardedBadge(child_id="c1", badge_id="earned")]
        coord = self._coordinator_for(child, [earned, locked], awarded)
        sensor = ChildBadgesSensor(coord, _MockEntry(), child)
        attrs = sensor.extra_state_attributes
        assert attrs["total_badges"] == 2
        assert len(attrs["earned"]) == 1
        assert attrs["earned"][0]["badge_id"] == "earned"
        assert len(attrs["available"]) == 1
        assert attrs["available"][0]["badge_id"] == "locked"
        # Progress 5/10 = 50%
        assert attrs["available"][0]["progress_pct"] == 50
        assert attrs["available"][0]["closest_criterion"] == {
            "metric": "total_chores",
            "current": 5,
            "target": 10,
        }

    def test_and_badge_reports_weakest_criterion(self, hass):
        """AND badges are gated by their worst criterion — report that one."""
        child = Child(name="Mia", total_chores_completed=8, total_points_earned=10)
        child.id = "c1"
        locked = Badge(
            name="Both",
            criteria=[
                BadgeCriterion("total_chores", ">=", 10),
                BadgeCriterion("total_points", ">=", 100),
            ],
            combinator="AND",
        )
        locked.id = "locked"
        coord = self._coordinator_for(child, [locked], [])
        sensor = ChildBadgesSensor(coord, _MockEntry(), child)
        avail = sensor.extra_state_attributes["available"][0]
        # points is 10/100 = 10%, chores is 8/10 = 80% — AND takes the worse.
        assert avail["progress_pct"] == 10
        assert avail["closest_criterion"] == {
            "metric": "total_points",
            "current": 10,
            "target": 100,
        }

    def test_or_badge_reports_strongest_criterion(self, hass):
        """OR badges fire on any criterion, so progress is the best one (#780)."""
        child = Child(name="Mia", total_chores_completed=8, total_points_earned=10)
        child.id = "c1"
        locked = Badge(
            name="Either",
            criteria=[
                BadgeCriterion("total_chores", ">=", 10),
                BadgeCriterion("total_points", ">=", 100),
            ],
            combinator="OR",
        )
        locked.id = "locked"
        coord = self._coordinator_for(child, [locked], [])
        sensor = ChildBadgesSensor(coord, _MockEntry(), child)
        avail = sensor.extra_state_attributes["available"][0]
        assert avail["progress_pct"] == 80
        assert avail["closest_criterion"] == {
            "metric": "total_chores",
            "current": 8,
            "target": 10,
        }

    def test_criteria_free_badge_has_no_closest_criterion(self, hass):
        """Manual-award-only badges never auto-fire — no progress to show."""
        child = Child(name="Mia")
        child.id = "c1"
        manual = Badge(name="Manual", criteria=[])
        manual.id = "manual"
        coord = self._coordinator_for(child, [manual], [])
        sensor = ChildBadgesSensor(coord, _MockEntry(), child)
        avail = sensor.extra_state_attributes["available"][0]
        assert avail["progress_pct"] == 0
        assert avail["closest_criterion"] is None

    def test_excludes_disabled_badges(self, hass):
        child = Child(name="Mia")
        child.id = "c1"
        disabled = Badge(name="Disabled", enabled=False)
        disabled.id = "x"
        coord = self._coordinator_for(child, [disabled], [])
        sensor = ChildBadgesSensor(coord, _MockEntry(), child)
        attrs = sensor.extra_state_attributes
        assert attrs["total_badges"] == 0

    def test_filters_by_assigned_to(self, hass):
        child = Child(name="Mia")
        child.id = "c1"
        not_for_me = Badge(name="Other", assigned_to=["c2"])
        not_for_me.id = "x"
        for_all = Badge(name="All")
        for_all.id = "y"
        coord = self._coordinator_for(child, [not_for_me, for_all], [])
        sensor = ChildBadgesSensor(coord, _MockEntry(), child)
        attrs = sensor.extra_state_attributes
        assert attrs["total_badges"] == 1
        assert attrs["available"][0]["badge_id"] == "y"


class TestChildStatsAssignedChores:
    """`assigned_chores` drives which chores a child sees on their card.

    Regression for #540: `first_come` ("First come, first served") chores were
    invisible because the visibility filter treated every non-`everyone` mode as
    a single-active-child rotation. first_come has no single active child, so the
    chore was hidden from the whole pool. It must stay visible to every pool
    member until one child fills the shared (single-winner) quota.
    """

    def _coord(self, child, chores, *, rotation_done=False):
        coord = MagicMock()
        coord.get_child = lambda cid: child if (child and child.id == cid) else None
        coord.data = {"chores": chores}
        coord._is_rotation_done_today = MagicMock(return_value=rotation_done)
        return coord

    def _assigned_names(self, child, chores, *, rotation_done=False):
        coord = self._coord(child, chores, rotation_done=rotation_done)
        sensor = ChildStatsSensor(coord, _MockEntry(), child)
        return [c["name"] for c in sensor.extra_state_attributes["assigned_chores"]]

    def test_first_come_chore_visible_to_pool_member(self, hass):
        child = Child(name="Mia")
        child.id = "c1"
        chore = Chore(name="Race", assigned_to=["c1", "c2"], assignment_mode="first_come")
        assert "Race" in self._assigned_names(child, [chore], rotation_done=False)

    def test_first_come_chore_hidden_once_quota_filled(self, hass):
        child = Child(name="Mia")
        child.id = "c1"
        chore = Chore(name="Race", assigned_to=["c1", "c2"], assignment_mode="first_come")
        assert "Race" not in self._assigned_names(child, [chore], rotation_done=True)

    def test_rotation_chore_still_hidden_from_off_rotation_child(self, hass):
        # Guard: the fix must not over-expose single-assignee rotation modes.
        child = Child(name="Mia")
        child.id = "c1"
        chore = Chore(name="Rotate", assigned_to=["c1", "c2"], assignment_mode="alternating")
        chore.assignment_current_child_id = "c2"
        assert "Rotate" not in self._assigned_names(child, [chore], rotation_done=False)

    def test_rotation_chore_visible_to_active_child(self, hass):
        child = Child(name="Mia")
        child.id = "c1"
        chore = Chore(name="Rotate", assigned_to=["c1", "c2"], assignment_mode="alternating")
        chore.assignment_current_child_id = "c1"
        assert "Rotate" in self._assigned_names(child, [chore], rotation_done=False)


class TestPendingApprovalsSensor:
    """The pending-approvals list is the single source of truth for parent
    approval surfaces. It must NOT be filtered to today (a completion from a
    previous day stays pending until approved), and it must describe bonus
    sub-task completions correctly so cards can render them."""

    def _coord(self, children, chores, pending):
        coord = MagicMock()
        coord.data = {
            "pending_completions": pending,
            "pending_reward_claims": [],
        }
        by_child = {c.id: c for c in children}
        by_chore = {c.id: c for c in chores}
        coord.get_child = lambda cid: by_child.get(cid)
        coord.get_chore = lambda cid: by_chore.get(cid)
        coord.get_reward = lambda rid: None
        return coord

    def test_includes_pending_completion_from_previous_day(self, hass):
        # Daughter completed a daily chore yesterday; today it reset. The
        # still-unapproved completion must remain in the approvals list so the
        # parent can still approve it.
        dt_util_mock._now = dt.datetime(2026, 6, 7, 9, 0, 0, tzinfo=UTC)
        child = Child(name="Mia")
        child.id = "c1"
        chore = Chore(name="Make bed", points=10, requires_approval=True)
        chore.id = "ch1"
        yesterday = dt.datetime(2026, 6, 6, 18, 0, 0, tzinfo=UTC)
        comp = ChoreCompletion(
            chore_id="ch1",
            child_id="c1",
            completed_at=yesterday,
            approved=False,
            points_awarded=0,
            id="comp-yesterday",
        )
        coord = self._coord([child], [chore], [comp])
        sensor = PendingApprovalsSensor(coord, _MockEntry())
        attrs = sensor.extra_state_attributes
        ids = [d["completion_id"] for d in attrs["chore_completions"]]
        assert "comp-yesterday" in ids

    def test_bonus_subtask_completion_named_and_priced_correctly(self, hass):
        dt_util_mock._now = dt.datetime(2026, 6, 7, 9, 0, 0, tzinfo=UTC)
        child = Child(name="Mia")
        child.id = "c1"
        sub = BonusSubTask(name="Tidy toys", points=3)
        sub.id = "sub1"
        chore = Chore(name="Make bed", points=10, bonus_subtasks=[sub])
        chore.id = "ch1"
        comp = ChoreCompletion(
            chore_id="ch1",
            child_id="c1",
            completed_at=dt.datetime(2026, 6, 7, 8, 0, 0, tzinfo=UTC),
            approved=False,
            points_awarded=0,
            bonus_subtask_id="sub1",
            id="comp-bonus",
        )
        coord = self._coord([child], [chore], [comp])
        sensor = PendingApprovalsSensor(coord, _MockEntry())
        detail = sensor.extra_state_attributes["chore_completions"][0]
        assert detail["chore_name"] == "Make bed › Tidy toys"
        assert detail["points"] == 3
        assert detail["bonus_subtask_id"] == "sub1"


def _wired_stress_coordinator():
    """Stress coordinator with the extras the whole-entity sensors reach for."""
    coord = _stress_coordinator()
    coord.external_state_version = 0
    coord.hass = MagicMock()
    coord.storage.get_career_score_history = MagicMock(
        return_value=[{"date": f"2026-01-{(d % 28) + 1:02d}", "score": 100 + d} for d in range(90)]
    )
    coord.mandatory_misses_state = MagicMock(
        return_value=[
            {
                "id": f"miss-{i:03d}",
                "chore_id": f"chore-{i % 30:02d}",
                "child_id": f"child-{i % 4}",
                "date": "2026-04-20",
                "chore_name": f"Chore {i % 30:02d}",
                "child_name": f"Child {i % 4}",
                "resolved": False,
            }
            for i in range(120)
        ]
    )
    return coord


def _stress_sensors(coord, entry):
    """The six global sensors plus the pending-approvals sensor."""
    return [
        sensor_module.TaskMateOverallStatsSensor(coord, entry),
        sensor_module.TaskMateChoresSensor(coord, entry),
        sensor_module.TaskMateChoreAvailabilitySensor(coord, entry),
        sensor_module.TaskMateRewardsSensor(coord, entry),
        sensor_module.TaskMateActivitySensor(coord, entry),
        sensor_module.TaskMateIncentivesSensor(coord, entry),
        PendingApprovalsSensor(coord, entry),
    ]


def _recorder_payload(sensor_cls, attrs: dict) -> dict:
    """Mirror HA's recorder filter: drop `_unrecorded_attributes` first.

    ``StateAttributes.shared_attrs_bytes_from_event`` excludes an entity's
    unrecorded attributes *before* measuring against MAX_STATE_ATTRS_BYTES,
    so it is that subset which has to fit.
    """
    excluded = getattr(sensor_cls, "_unrecorded_attributes", frozenset())
    return {k: v for k, v in attrs.items() if k not in excluded}


def test_unrecorded_attribute_names_are_actually_published():
    """A typo'd name in `_unrecorded_attributes` silently excludes nothing (#817)."""
    coord = _wired_stress_coordinator()
    entry = _MockEntry()
    for sensor in _stress_sensors(coord, entry):
        published = set(sensor.extra_state_attributes)
        declared = set(getattr(type(sensor), "_unrecorded_attributes", frozenset()))
        assert declared <= published, (
            f"{type(sensor).__name__} declares unrecorded attributes it never publishes: {sorted(declared - published)}"
        )


def test_global_sensor_recorder_payloads_under_limit():
    """Every sensor's recorder-visible payload must fit in 16 KB (#817).

    The per-slice tests above assemble the attribute dicts by hand, so they
    miss whatever a sensor actually publishes (that is how `career_score_history`,
    `photo_gallery` and `mandatory_misses` slipped past). This one drives the
    real entities end to end.
    """
    coord = _wired_stress_coordinator()
    entry = _MockEntry()
    oversized = []
    for sensor in _stress_sensors(coord, entry):
        size = _bytes(_recorder_payload(type(sensor), sensor.extra_state_attributes))
        if size >= MAX_ATTR_BYTES:
            oversized.append(f"{sensor._attr_name}: {size} bytes")
    assert not oversized, "recorder payload over the 16384-byte limit: " + "; ".join(oversized)


def test_heavy_lists_are_still_published_to_the_frontend():
    """Excluding from the recorder must not remove data the cards read (#817)."""
    coord = _wired_stress_coordinator()
    entry = _MockEntry()
    activity = sensor_module.TaskMateActivitySensor(coord, entry).extra_state_attributes
    assert activity["recent_completions"]
    assert activity["recent_transactions"]
    assert activity["career_score_history"]
    approvals = PendingApprovalsSensor(coord, entry).extra_state_attributes
    assert approvals["chore_completions"]
    assert approvals["mandatory_misses"]
    # The scalar counters stay recorded so history/statistics keep working.
    recorded = _recorder_payload(PendingApprovalsSensor, approvals)
    assert recorded["pending_chore_completions"] == len(approvals["chore_completions"])
    assert recorded["pending_mandatory_misses"] == 120
