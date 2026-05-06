"""Tests for badge dataclasses."""
from __future__ import annotations

from custom_components.taskmate.models import BadgeCriterion


class TestBadgeCriterion:
    def test_round_trip(self):
        c = BadgeCriterion(metric="total_points", operator=">=", value=100)
        assert BadgeCriterion.from_dict(c.to_dict()) == c

    def test_defaults(self):
        c = BadgeCriterion(metric="total_chores")
        assert c.operator == ">="
        assert c.value == 0
