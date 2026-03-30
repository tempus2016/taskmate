"""Tests for custom_components.taskmate.storage.TaskMateStorage.

We use an in-memory FakeStore (defined in conftest) so no filesystem I/O
occurs and no real Home Assistant is required.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone

import pytest

from custom_components.taskmate.models import Child, Chore, ChoreCompletion, Reward
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_storage(initial_data: dict | None = None) -> TaskMateStorage:
    """Return a TaskMateStorage backed by an in-memory FakeStore."""
    # conftest.py has already swapped homeassistant.helpers.storage.Store with FakeStore
    from tests.conftest import FakeStore

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"

    fake_store = FakeStore(None, 1, "test")
    if initial_data is not None:
        # Simulate pre-existing saved data
        fake_store._data = initial_data

    storage._store = fake_store
    storage._data = {}
    return storage


# ---------------------------------------------------------------------------
# async_load — defaults and migration
# ---------------------------------------------------------------------------

class TestAsyncLoad:
    def test_fresh_load_creates_default_structure(self):
        storage = _make_storage(initial_data=None)
        run(storage.async_load())
        assert storage._data["children"] == []
        assert storage._data["chores"] == []
        assert storage._data["rewards"] == []
        assert storage._data["completions"] == []
        assert storage._data["reward_claims"] == []
        assert storage._data["points_transactions"] == []
        assert storage._data["points_name"] == "Stars"
        assert storage._data["points_icon"] == "mdi:star"
        assert "last_completed" in storage._data

    def test_existing_data_without_last_completed_gets_migrated(self):
        existing = {
            "children": [],
            "chores": [],
            "rewards": [],
            "completions": [],
            "reward_claims": [],
            "points_transactions": [],
            "points_name": "Coins",
            "points_icon": "mdi:coin",
            # intentionally missing "last_completed"
        }
        storage = _make_storage(initial_data=existing)
        run(storage.async_load())
        assert "last_completed" in storage._data

    def test_existing_data_preserved_on_load(self):
        existing = {
            "children": [{"name": "Alice", "id": "abc", "points": 100,
                           "total_points_earned": 100, "total_chores_completed": 5,
                           "current_streak": 2, "best_streak": 5, "avatar": "mdi:account-circle",
                           "pending_rewards": [], "chore_order": [],
                           "last_completion_date": "2024-03-19",
                           "streak_paused": False,
                           "streak_milestones_achieved": [], "awarded_perfect_weeks": []}],
            "chores": [],
            "rewards": [],
            "completions": [],
            "reward_claims": [],
            "points_transactions": [],
            "last_completed": {},
        }
        storage = _make_storage(initial_data=existing)
        run(storage.async_load())
        children = storage.get_children()
        assert len(children) == 1
        assert children[0].name == "Alice"
        assert children[0].points == 100


# ---------------------------------------------------------------------------
# _migrate_assigned_to_child_ids
# ---------------------------------------------------------------------------

class TestMigrateAssignedTo:
    def _build_storage_with_data(self, children_raw, chores_raw):
        storage = _make_storage()
        storage._data = {
            "children": children_raw,
            "chores": chores_raw,
            "rewards": [],
            "completions": [],
            "reward_claims": [],
            "points_transactions": [],
            "last_completed": {},
        }
        return storage

    def test_chore_with_valid_ids_unchanged(self):
        children = [{"id": "id1", "name": "Alice"}]
        chores = [{"id": "c1", "name": "Sweep", "assigned_to": ["id1"]}]
        storage = self._build_storage_with_data(children, chores)
        run(storage._migrate_assigned_to_child_ids())
        assert storage._data["chores"][0]["assigned_to"] == ["id1"]

    def test_chore_with_child_name_migrated_to_id(self):
        children = [{"id": "id1", "name": "Alice"}]
        chores = [{"id": "c1", "name": "Sweep", "assigned_to": ["Alice"]}]
        storage = self._build_storage_with_data(children, chores)
        run(storage._migrate_assigned_to_child_ids())
        assert storage._data["chores"][0]["assigned_to"] == ["id1"]

    def test_chore_with_no_children_skipped(self):
        storage = self._build_storage_with_data([], [{"id": "c1", "name": "Sweep", "assigned_to": []}])
        run(storage._migrate_assigned_to_child_ids())  # should not raise

    def test_empty_chores_and_children_skipped(self):
        storage = self._build_storage_with_data([], [])
        run(storage._migrate_assigned_to_child_ids())  # should not raise


# ---------------------------------------------------------------------------
# Children CRUD
# ---------------------------------------------------------------------------

class TestChildrenCrud:
    def _storage(self):
        s = _make_storage()
        s._data = {"children": [], "chores": [], "rewards": [],
                   "completions": [], "reward_claims": [], "points_transactions": [],
                   "last_completed": {}}
        return s

    def test_add_then_get(self):
        storage = self._storage()
        child = Child(name="Alice", id="alice1")
        storage.add_child(child)
        found = storage.get_child("alice1")
        assert found is not None
        assert found.name == "Alice"

    def test_get_unknown_id_returns_none(self):
        storage = self._storage()
        assert storage.get_child("unknown") is None

    def test_get_children_returns_all(self):
        storage = self._storage()
        storage.add_child(Child(name="Alice", id="a1"))
        storage.add_child(Child(name="Bob", id="b1"))
        children = storage.get_children()
        assert len(children) == 2

    def test_update_child_modifies_existing(self):
        storage = self._storage()
        child = Child(name="Alice", points=0, id="a1")
        storage.add_child(child)
        child.points = 50
        storage.update_child(child)
        assert storage.get_child("a1").points == 50

    def test_update_child_adds_if_not_found(self):
        storage = self._storage()
        child = Child(name="Alice", id="a1")
        storage.update_child(child)  # no prior add
        assert storage.get_child("a1") is not None

    def test_remove_child(self):
        storage = self._storage()
        storage.add_child(Child(name="Alice", id="a1"))
        storage.remove_child("a1")
        assert storage.get_child("a1") is None

    def test_remove_nonexistent_child_harmless(self):
        storage = self._storage()
        storage.remove_child("does-not-exist")  # should not raise


# ---------------------------------------------------------------------------
# last_completed store
# ---------------------------------------------------------------------------

class TestLastCompleted:
    def _storage(self):
        s = _make_storage()
        s._data = {"last_completed": {}}
        return s

    def test_get_returns_empty_dict_when_never_completed(self):
        storage = self._storage()
        result = storage.get_last_completed("chore1", "kid1")
        assert result == {}

    def test_set_then_get(self):
        storage = self._storage()
        storage.set_last_completed("chore1", "kid1", "2024-03-20T12:00:00+00:00")
        result = storage.get_last_completed("chore1", "kid1")
        assert result["current"] == "2024-03-20T12:00:00+00:00"
        assert result["previous"] is None

    def test_second_set_shifts_current_to_previous(self):
        storage = self._storage()
        storage.set_last_completed("chore1", "kid1", "2024-03-19T12:00:00+00:00")
        storage.set_last_completed("chore1", "kid1", "2024-03-20T12:00:00+00:00")
        result = storage.get_last_completed("chore1", "kid1")
        assert result["current"] == "2024-03-20T12:00:00+00:00"
        assert result["previous"] == "2024-03-19T12:00:00+00:00"

    def test_undo_restores_previous_as_current(self):
        storage = self._storage()
        storage.set_last_completed("chore1", "kid1", "2024-03-19T12:00:00+00:00")
        storage.set_last_completed("chore1", "kid1", "2024-03-20T12:00:00+00:00")
        storage.undo_last_completed("chore1", "kid1")
        result = storage.get_last_completed("chore1", "kid1")
        assert result["current"] == "2024-03-19T12:00:00+00:00"

    def test_undo_with_no_previous_removes_record(self):
        storage = self._storage()
        storage.set_last_completed("chore1", "kid1", "2024-03-20T12:00:00+00:00")
        storage.undo_last_completed("chore1", "kid1")
        result = storage.get_last_completed("chore1", "kid1")
        assert result == {}

    def test_undo_nonexistent_is_harmless(self):
        storage = self._storage()
        storage.undo_last_completed("chore1", "kid1")  # should not raise


# ---------------------------------------------------------------------------
# Points transactions — 200-item cap
# ---------------------------------------------------------------------------

class TestPointsTransactionCap:
    def _storage(self):
        s = _make_storage()
        s._data = {"points_transactions": []}
        return s

    def test_transactions_capped_at_200(self):
        from custom_components.taskmate.models import PointsTransaction
        storage = self._storage()
        for i in range(210):
            tx = PointsTransaction(
                child_id="kid1",
                points=1,
                reason=f"tx{i}",
                created_at=dt.datetime(2024, 1, 1, tzinfo=UTC),
            )
            storage.add_points_transaction(tx)
        assert len(storage._data["points_transactions"]) == 200

    def test_most_recent_transactions_kept(self):
        from custom_components.taskmate.models import PointsTransaction
        storage = self._storage()
        for i in range(205):
            tx = PointsTransaction(
                child_id="kid1",
                points=i,  # use points as a unique marker
                reason=f"tx{i}",
                created_at=dt.datetime(2024, 1, 1, tzinfo=UTC),
            )
            storage.add_points_transaction(tx)
        # The last 200 entries should be kept (indices 5..204)
        kept_points = [t["points"] for t in storage._data["points_transactions"]]
        assert kept_points[0] == 5   # oldest kept
        assert kept_points[-1] == 204  # most recent


# ---------------------------------------------------------------------------
# get_pending_completions
# ---------------------------------------------------------------------------

class TestGetPendingCompletions:
    def _storage(self):
        s = _make_storage()
        s._data = {"completions": []}
        return s

    def test_returns_only_unapproved(self):
        storage = self._storage()
        approved = ChoreCompletion(
            chore_id="c1", child_id="k1",
            completed_at=dt.datetime(2024, 3, 19, 12, 0, 0, tzinfo=UTC),
            approved=True, points_awarded=10,
        )
        pending = ChoreCompletion(
            chore_id="c1", child_id="k1",
            completed_at=dt.datetime(2024, 3, 20, 12, 0, 0, tzinfo=UTC),
            approved=False,
        )
        storage.add_completion(approved)
        storage.add_completion(pending)
        result = storage.get_pending_completions()
        assert len(result) == 1
        assert result[0].id == pending.id

    def test_empty_when_all_approved(self):
        storage = self._storage()
        comp = ChoreCompletion(
            chore_id="c1", child_id="k1",
            completed_at=dt.datetime(2024, 3, 20, 12, 0, 0, tzinfo=UTC),
            approved=True,
        )
        storage.add_completion(comp)
        assert storage.get_pending_completions() == []


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

class TestSettings:
    def _storage(self):
        s = _make_storage()
        s._data = {}
        return s

    def test_get_missing_setting_returns_default(self):
        storage = self._storage()
        assert storage.get_setting("nonexistent", "fallback") == "fallback"

    def test_set_then_get_setting(self):
        storage = self._storage()
        storage.set_setting("streak_reset_mode", "pause")
        assert storage.get_setting("streak_reset_mode") == "pause"

    def test_points_name_roundtrip(self):
        storage = self._storage()
        storage._data["points_name"] = "Stars"
        assert storage.get_points_name() == "Stars"
        storage.set_points_name("Coins")
        assert storage.get_points_name() == "Coins"

    def test_points_icon_roundtrip(self):
        storage = self._storage()
        storage._data["points_icon"] = "mdi:star"
        assert storage.get_points_icon() == "mdi:star"
        storage.set_points_icon("mdi:coin")
        assert storage.get_points_icon() == "mdi:coin"
