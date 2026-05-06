"""Tests for badge storage layer."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from custom_components.taskmate.models import Badge, BadgeCriterion, AwardedBadge, Child
from custom_components.taskmate.storage import TaskMateStorage


@pytest.fixture
def storage():
    hass = MagicMock()
    s = TaskMateStorage(hass, "test_entry")
    s._data = {
        "badges": [],
        "awarded_badges": [],
        "children": [],
    }
    return s


class TestBadgeStorage:
    def test_get_badges_empty(self, storage):
        assert storage.get_badges() == []

    def test_add_and_get_badge(self, storage):
        b = Badge(name="Test", criteria=[BadgeCriterion("total_points", ">=", 50)])
        storage.add_badge(b)
        all_b = storage.get_badges()
        assert len(all_b) == 1
        assert all_b[0].name == "Test"

    def test_get_badge_by_id(self, storage):
        b = Badge(name="Test")
        storage.add_badge(b)
        found = storage.get_badge(b.id)
        assert found is not None
        assert found.name == "Test"

    def test_get_badge_missing_returns_none(self, storage):
        assert storage.get_badge("does-not-exist") is None

    def test_update_badge(self, storage):
        b = Badge(name="Original")
        storage.add_badge(b)
        b.name = "Updated"
        storage.update_badge(b)
        assert storage.get_badges()[0].name == "Updated"

    def test_remove_badge(self, storage):
        b = Badge(name="Test")
        storage.add_badge(b)
        storage.remove_badge(b.id)
        assert storage.get_badges() == []

    def test_remove_badge_cascades_awards(self, storage):
        b = Badge(name="Test")
        storage.add_badge(b)
        storage.add_awarded_badge(AwardedBadge(child_id="c1", badge_id=b.id))
        storage.add_awarded_badge(AwardedBadge(child_id="c2", badge_id=b.id))
        storage.add_awarded_badge(AwardedBadge(child_id="c1", badge_id="other"))
        storage.remove_badge(b.id)
        remaining = storage.get_awarded_badges()
        assert len(remaining) == 1
        assert remaining[0].badge_id == "other"

    def test_award_and_get(self, storage):
        a = AwardedBadge(child_id="c1", badge_id="b1")
        storage.add_awarded_badge(a)
        assert len(storage.get_awarded_badges()) == 1

    def test_get_awarded_badges_for_child(self, storage):
        storage.add_awarded_badge(AwardedBadge(child_id="c1", badge_id="b1"))
        storage.add_awarded_badge(AwardedBadge(child_id="c2", badge_id="b1"))
        c1_badges = storage.get_awarded_badges_for_child("c1")
        assert len(c1_badges) == 1
        assert c1_badges[0].child_id == "c1"

    def test_remove_awarded_badge(self, storage):
        a = AwardedBadge(child_id="c1", badge_id="b1")
        storage.add_awarded_badge(a)
        storage.remove_awarded_badge(a.id)
        assert storage.get_awarded_badges() == []

    def test_remove_awards_for_child_cascade(self, storage):
        storage.add_awarded_badge(AwardedBadge(child_id="c1", badge_id="b1"))
        storage.add_awarded_badge(AwardedBadge(child_id="c1", badge_id="b2"))
        storage.add_awarded_badge(AwardedBadge(child_id="c2", badge_id="b1"))
        storage.remove_awards_for_child("c1")
        remaining = storage.get_awarded_badges()
        assert len(remaining) == 1
        assert remaining[0].child_id == "c2"

    def test_has_awarded(self, storage):
        storage.add_awarded_badge(AwardedBadge(child_id="c1", badge_id="b1"))
        assert storage.has_awarded("c1", "b1") is True
        assert storage.has_awarded("c1", "b2") is False

    def test_remove_child_cascades_to_awards(self, storage):
        # remove_child should cascade-clean the child's awarded_badges
        child = Child(name="Mia")
        storage._data["children"].append(child.to_dict())
        storage.add_awarded_badge(AwardedBadge(child_id=child.id, badge_id="b1"))
        storage.add_awarded_badge(AwardedBadge(child_id="other", badge_id="b1"))
        storage.remove_child(child.id)
        remaining = storage.get_awarded_badges()
        assert len(remaining) == 1
        assert remaining[0].child_id == "other"
