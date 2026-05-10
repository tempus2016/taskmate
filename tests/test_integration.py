"""Integration tests — full lifecycle through real coordinator + storage.

Unlike unit tests that mock the storage layer, these tests wire up a real
TaskMateStorage (backed by an in-memory FakeStore) and a real
TaskMateCoordinator, exercising the complete path:

  add child → add chore → complete chore → approve → points awarded
  add reward → claim reward → approve reward → points deducted
  template apply → chores created
"""
from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import patch

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.storage import TaskMateStorage
from custom_components.taskmate.templates import BUILT_IN_TEMPLATES

UTC = timezone.utc


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _now(year=2024, month=3, day=20, hour=12):
    return dt.datetime(year, month, day, hour, 0, 0, tzinfo=UTC)


def _make_system(now=None):
    """Build a fully wired coordinator + storage using in-memory FakeStore."""
    from tests.conftest import FakeHass, FakeStore

    if now is None:
        now = _now()

    hass = FakeHass()
    hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    run(storage.async_load())

    from custom_components.taskmate.coord_notifications import NotificationCoordinator

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.data = {}
    coord.storage = storage
    coord.notifications = NotificationCoordinator(hass, storage)
    coord._unsub_midnight = None
    coord._unsub_prune = None
    coord._unsub_availability = None

    async def _noop_refresh():
        pass

    import custom_components.taskmate.coordinator as _mod
    coord._dt_now = now
    coord.async_refresh = _noop_refresh

    return coord, storage, _mod


class TestFullChoreLifecycle:
    """Complete chore lifecycle: add child → add chore → complete → approve → points."""

    def test_complete_auto_approved_chore_awards_points(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(coord.async_add_chore(
                "Make bed", points=5, requires_approval=False
            ))

        assert child.points == 0

        with patch.object(_mod.dt_util, "now", return_value=now):
            completion = run(coord.async_complete_chore(chore.id, child.id))

        assert completion.approved is True
        assert completion.points_awarded == 5
        updated_child = storage.get_child(child.id)
        assert updated_child.points == 5
        assert updated_child.current_streak == 1

    def test_complete_approval_required_chore_holds_points(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Bob"))
            chore = run(coord.async_add_chore(
                "Tidy room", points=10, requires_approval=True
            ))
            completion = run(coord.async_complete_chore(chore.id, child.id))

        assert completion.approved is False
        assert completion.points_awarded == 0
        assert storage.get_child(child.id).points == 0

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_approve_chore(completion.id))

        updated_child = storage.get_child(child.id)
        assert updated_child.points == 10
        approved = next(
            c for c in storage.get_completions() if c.id == completion.id
        )
        assert approved.approved is True
        assert approved.points_awarded == 10

    def test_daily_limit_blocks_extra_completions(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Charlie"))
            chore = run(coord.async_add_chore(
                "Feed cat", points=3, requires_approval=False, daily_limit=1
            ))
            run(coord.async_complete_chore(chore.id, child.id))

        with pytest.raises(ValueError, match="Daily limit"):
            with patch.object(_mod.dt_util, "now", return_value=now):
                run(coord.async_complete_chore(chore.id, child.id))

    def test_streak_increments_across_days(self):
        coord, storage, _mod = _make_system()
        day1 = _now(day=20)
        day2 = _now(day=21)

        with patch.object(_mod.dt_util, "now", return_value=day1):
            child = run(coord.async_add_child("Dana"))
            chore = run(coord.async_add_chore(
                "Brush teeth", points=2, requires_approval=False
            ))
            run(coord.async_complete_chore(chore.id, child.id))

        assert storage.get_child(child.id).current_streak == 1

        with patch.object(_mod.dt_util, "now", return_value=day2):
            run(coord.async_complete_chore(chore.id, child.id))

        assert storage.get_child(child.id).current_streak == 2


class TestFullRewardLifecycle:
    """Complete reward lifecycle: earn points → claim → approve → deduct."""

    def test_claim_and_approve_reward_deducts_points(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Eve"))
            chore = run(coord.async_add_chore(
                "Hoover", points=20, requires_approval=False
            ))
            run(coord.async_complete_chore(chore.id, child.id))

        assert storage.get_child(child.id).points == 20

        with patch.object(_mod.dt_util, "now", return_value=now):
            reward = run(coord.async_add_reward("Ice cream", cost=15))
            claim = run(coord.async_claim_reward(reward.id, child.id))

        assert claim.approved is False

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_approve_reward(claim.id))

        updated_child = storage.get_child(child.id)
        assert updated_child.points == 5  # 20 - 15

    def test_cannot_claim_reward_with_insufficient_points(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Frank"))
            reward = run(coord.async_add_reward("Bike", cost=100))

        with pytest.raises(ValueError, match="[Nn]ot enough|[Ii]nsufficient"):
            with patch.object(_mod.dt_util, "now", return_value=now):
                run(coord.async_claim_reward(reward.id, child.id))


class TestTemplateApply:
    """Templates: apply built-in template → chores created."""

    def test_apply_built_in_template_creates_chores(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_add_child("Grace"))

        template = BUILT_IN_TEMPLATES[0]  # morning_routine
        chore_defs = template["chores"]

        with patch.object(_mod.dt_util, "now", return_value=now):
            created_ids = run(coord.async_apply_template(chore_defs))

        assert len(created_ids) == len(chore_defs)
        all_chores = storage.get_chores()
        created_names = {c.name for c in all_chores}
        for chore_def in chore_defs:
            assert chore_def["name"] in created_names

    def test_apply_template_chores_are_completable(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Henry"))

        template = BUILT_IN_TEMPLATES[0]
        chore_defs = template["chores"]

        with patch.object(_mod.dt_util, "now", return_value=now):
            created_ids = run(coord.async_apply_template(chore_defs))

        first_chore = storage.get_chore(created_ids[0])
        with patch.object(_mod.dt_util, "now", return_value=now):
            completion = run(coord.async_complete_chore(first_chore.id, child.id))

        assert completion is not None
        assert completion.points_awarded == first_chore.points


class TestCustomTemplateLifecycle:
    """Custom template lifecycle: save from chores → list → apply → delete."""

    def test_save_from_chores_and_reapply(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_add_child("Ivy"))
            chore1 = run(coord.async_add_chore("Task A", points=5))
            chore2 = run(coord.async_add_chore("Task B", points=8))

        with patch.object(_mod.dt_util, "now", return_value=now):
            template_id = run(coord.async_save_template_from_chores(
                [chore1.id, chore2.id], "My Pack", "mdi:broom"
            ))

        assert template_id is not None

        templates = coord.get_all_templates()
        custom = [t for t in templates if not t.get("builtin")]
        assert len(custom) == 1
        assert custom[0]["name"] == "My Pack"
        assert len(custom[0]["chores"]) == 2

        with patch.object(_mod.dt_util, "now", return_value=now):
            new_ids = run(coord.async_apply_template(custom[0]["chores"]))

        assert len(new_ids) == 2
        all_chores = storage.get_chores()
        assert len(all_chores) == 4  # 2 original + 2 from template

    def test_delete_custom_template(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            template_id = run(coord.async_create_template(
                "Temp Pack", "mdi:star", [{"name": "X", "points": 1}]
            ))

        assert len(storage.get_custom_templates()) == 1

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_delete_template(template_id))

        assert len(storage.get_custom_templates()) == 0

    def test_cannot_delete_builtin_template(self):
        coord, storage, _mod = _make_system()
        builtin_id = BUILT_IN_TEMPLATES[0]["id"]

        with pytest.raises(ValueError, match="[Bb]uilt.in"):
            run(coord.async_delete_template(builtin_id))


class TestOneShotChoreLifecycle:
    """One-shot chores: create → complete → expired next day."""

    def test_one_shot_completes_once_then_disabled(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Jack"))
            chore = run(coord.async_add_chore(
                "One-off task", points=5, requires_approval=False,
                schedule_mode="one_shot"
            ))
            run(coord.async_complete_chore(chore.id, child.id))

        updated_chore = storage.get_chore(chore.id)
        assert child.id in updated_chore.disabled_for

        with pytest.raises(ValueError, match="not available"):
            with patch.object(_mod.dt_util, "now", return_value=now):
                run(coord.async_complete_chore(chore.id, child.id))


class TestRemoveChildCascade:
    """Removing a child cleans up all associated data."""

    def test_remove_child_cleans_completions_and_claims(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Kate"))
            chore = run(coord.async_add_chore(
                "Wash hands", points=2, requires_approval=False
            ))
            run(coord.async_complete_chore(chore.id, child.id))

        assert len(storage.get_completions()) == 1

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_remove_child(child.id))

        assert storage.get_child(child.id) is None
        assert len(storage.get_completions()) == 0


class TestMultiChildInteraction:
    """Multiple children completing the same chore independently."""

    def test_two_children_same_chore_independent_points(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            alice = run(coord.async_add_child("Alice"))
            bob = run(coord.async_add_child("Bob"))
            chore = run(coord.async_add_chore(
                "Set table", points=3, requires_approval=False
            ))
            run(coord.async_complete_chore(chore.id, alice.id))
            run(coord.async_complete_chore(chore.id, bob.id))

        assert storage.get_child(alice.id).points == 3
        assert storage.get_child(bob.id).points == 3
        assert len(storage.get_completions()) == 2
