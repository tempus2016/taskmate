"""Tests for badge dataclasses."""
from __future__ import annotations

from custom_components.taskmate.models import AwardedBadge, Badge, BadgeCriterion


class TestBadgeCriterion:
    def test_round_trip(self):
        c = BadgeCriterion(metric="total_points", operator=">=", value=100)
        assert BadgeCriterion.from_dict(c.to_dict()) == c

    def test_defaults(self):
        c = BadgeCriterion(metric="total_chores")
        assert c.operator == ">="
        assert c.value == 0


class TestBadge:
    def test_defaults(self):
        b = Badge(name="Test")
        assert b.tier == "bronze"
        assert b.point_bonus == 0
        assert b.combinator == "AND"
        assert b.builtin is False
        assert b.enabled is True
        assert b.notify_on_earn is True
        assert b.criteria == []
        assert b.assigned_to == []

    def test_round_trip_with_criteria(self):
        b = Badge(
            name="100 Points",
            description="Earn 100 lifetime points",
            icon="mdi:star",
            tier="bronze",
            point_bonus=0,
            criteria=[BadgeCriterion(metric="total_points", value=100)],
            assigned_to=["child-1"],
            builtin=True,
        )
        round_trip = Badge.from_dict(b.to_dict())
        assert round_trip.name == b.name
        assert len(round_trip.criteria) == 1
        assert round_trip.criteria[0].metric == "total_points"
        assert round_trip.builtin is True


class TestAwardedBadge:
    def test_defaults(self):
        a = AwardedBadge(child_id="c1", badge_id="b1")
        assert a.manually_awarded is False
        assert a.silent is False
        assert a.bonus_credited == 0

    def test_round_trip(self):
        a = AwardedBadge(
            child_id="c1",
            badge_id="b1",
            manually_awarded=True,
            silent=False,
            bonus_credited=50,
        )
        round_trip = AwardedBadge.from_dict(a.to_dict())
        assert round_trip.child_id == "c1"
        assert round_trip.bonus_credited == 50
        assert round_trip.manually_awarded is True
