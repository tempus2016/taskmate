"""Tests for badge storage layer."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.taskmate.coord_badges import BUILTIN_CATALOGUE
from custom_components.taskmate.models import AwardedBadge, Badge, BadgeCriterion, Child
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


class TestCatalogueSeeding:
    def test_seed_fresh_adds_all_builtins_and_sets_flag(self, storage):
        # Fresh install: badges key absent before seeding
        storage._data = {}
        storage._seed_builtin_badges(is_fresh=True)
        ids = {b.id for b in storage.get_badges()}
        assert ids == {b.id for b in BUILTIN_CATALOGUE}
        assert storage._data.get("badges_backfill_pending") is True

    def test_seed_existing_adds_missing_only_no_flag(self, storage):
        # Existing install: badges key present (may be empty)
        storage._data["badges"] = []
        storage._seed_builtin_badges(is_fresh=False)
        # All 15 added because none were present
        assert len(storage.get_badges()) == len(BUILTIN_CATALOGUE)
        # No backfill flag (this is not a fresh install)
        assert storage._data.get("badges_backfill_pending") is not True

    def test_seed_preserves_parent_customisations(self, storage):
        # Parent edited point_bonus on the first built-in
        first = BUILTIN_CATALOGUE[0]
        custom = first.to_dict()
        custom["point_bonus"] = 999
        storage._data["badges"] = [custom]
        storage._seed_builtin_badges(is_fresh=False)
        # Customisation preserved
        kept = next(b for b in storage.get_badges() if b.id == first.id)
        assert kept.point_bonus == 999
        # Other 14 added
        assert len(storage.get_badges()) == len(BUILTIN_CATALOGUE)

    def test_seed_idempotent(self, storage):
        storage._data = {}
        storage._seed_builtin_badges(is_fresh=True)
        first_count = len(storage.get_badges())
        storage._seed_builtin_badges(is_fresh=False)
        second_count = len(storage.get_badges())
        assert first_count == second_count


class TestBackfillFlagLifecycle:
    def test_backfill_flag_is_set_on_fresh_seed(self, storage):
        storage._data = {}
        storage._seed_builtin_badges(is_fresh=True)
        assert storage._data.get("badges_backfill_pending") is True

    def test_backfill_flag_can_be_popped(self, storage):
        storage._data = {"badges_backfill_pending": True, "badges": [], "awarded_badges": []}
        # Simulate the coordinator clearing it after rebuild_all
        storage._data.pop("badges_backfill_pending", None)
        assert "badges_backfill_pending" not in storage._data
