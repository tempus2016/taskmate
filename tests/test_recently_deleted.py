"""Recently deleted: a deleted chore, reward or quest can be restored for 7 days."""

from __future__ import annotations

import datetime as dt
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.taskmate.models import ChoreCompletion, PoolAllocation, Quest, RewardClaim

from .test_completion_eligibility import _make_system, _now, run

MODULES = ("coordinator", "coord_trash", "coord_chores", "coord_rewards", "coord_quests")


def _at(when):
    stack = ExitStack()
    for mod in MODULES:
        stack.enter_context(patch(f"custom_components.taskmate.{mod}.dt_util.now", return_value=when))
    return stack


def _system():
    coord, storage, _mod = _make_system()
    with _at(_now()):
        kid = run(coord.async_add_child("Vaiha"))
        other = run(coord.async_add_child("Leo"))
    return coord, storage, kid, other


def _chore(coord, name="Water the plants", image_url=""):
    with _at(_now()):
        chore = run(coord.async_add_chore(name, points=5))
    if image_url:
        chore.image_url = image_url
        coord.storage.update_chore(chore)
    return chore


class TestChore:
    def test_restore_brings_back_the_chore_and_what_its_delete_cleared(self):
        coord, storage, kid, other = _system()
        first = _chore(coord, "Make bed")
        chore = _chore(coord)
        storage.add_completion(
            ChoreCompletion(chore_id=chore.id, child_id=kid.id, completed_at=_now(), approved=True, points_awarded=5)
        )
        storage.set_last_completed(chore.id, kid.id, _now().isoformat())
        storage.set_weekly_target_bonus(chore.id, kid.id, {"week": "2024-W12", "points": 3})
        storage.set_chore_display_order([chore.id, first.id])
        storage.data["task_groups"] = [
            {"id": "g1", "name": "Morning", "policy": "sticky", "chore_ids": [first.id, chore.id]}
        ]
        with _at(_now()):
            run(coord.async_set_chore_order(kid.id, [chore.id, first.id]))
            run(coord.async_remove_chore(chore.id))

        assert storage.get_chore(chore.id) is None
        assert storage.get_completions() == []
        assert [e["id"] for e in coord.recently_deleted()] == [chore.id]
        assert coord.recently_deleted()[0]["name"] == "Water the plants"

        with _at(_now()):
            run(coord.async_restore_deleted("chore", chore.id))

        assert storage.get_chore(chore.id).name == "Water the plants"
        assert [c.chore_id for c in storage.get_completions()] == [chore.id]
        assert storage.get_last_completed(chore.id, kid.id)
        assert storage.get_weekly_target_bonus(chore.id, kid.id) == {"week": "2024-W12", "points": 3}
        assert storage.data["chore_display_order"] == [chore.id, first.id]
        assert storage.get_task_groups()[0].chore_ids == [first.id, chore.id]
        assert storage.get_child(kid.id).chore_order == [chore.id, first.id]
        assert coord.recently_deleted() == []

    def test_completions_of_a_child_deleted_since_stay_gone(self):
        coord, storage, kid, other = _system()
        chore = _chore(coord)
        for child in (kid, other):
            storage.add_completion(ChoreCompletion(chore_id=chore.id, child_id=child.id, completed_at=_now()))
        with _at(_now()):
            run(coord.async_remove_chore(chore.id))
        storage.remove_child(other.id)
        with _at(_now()):
            run(coord.async_restore_deleted("chore", chore.id))
        assert [c.child_id for c in storage.get_completions()] == [kid.id]

    def test_bulk_delete_is_kept_too(self):
        coord, storage, *_ = _system()
        a, b = _chore(coord, "A"), _chore(coord, "B")
        with _at(_now()):
            run(coord.async_bulk_chore_action("delete", [a.id, b.id]))
        assert {e["id"] for e in coord.recently_deleted()} == {a.id, b.id}

    def test_refuses_when_the_id_is_taken(self):
        coord, storage, *_ = _system()
        chore = _chore(coord)
        with _at(_now()):
            run(coord.async_remove_chore(chore.id))
        storage.add_chore(chore)
        with _at(_now()), pytest.raises(ValueError, match="already exists"):
            run(coord.async_restore_deleted("chore", chore.id))
        assert len(coord.recently_deleted()) == 1

    def test_unknown_item_is_refused(self):
        coord, *_ = _system()
        with _at(_now()), pytest.raises(ValueError, match="Nothing to restore"):
            run(coord.async_restore_deleted("chore", "nope"))

    def test_a_second_delete_replaces_the_first_snapshot(self):
        coord, *_ = _system()
        chore = _chore(coord)
        with _at(_now()):
            run(coord.async_remove_chore(chore.id))
            run(coord.async_restore_deleted("chore", chore.id))
            run(coord.async_remove_chore(chore.id))
        assert len(coord.recently_deleted()) == 1


class TestPurge:
    def test_snapshots_go_after_seven_days_and_take_the_picture(self):
        coord, storage, *_ = _system()
        chore = _chore(coord, image_url="/api/taskmate/image/plants.jpg")
        with _at(_now()):
            run(coord.async_remove_chore(chore.id))
        deleted = []
        with patch(
            "custom_components.taskmate.coord_chores.images.async_delete_image",
            AsyncMock(side_effect=lambda h, u: deleted.append(u)),
        ):
            with _at(_now() + dt.timedelta(days=6, hours=23)):
                run(coord.async_purge_recently_deleted())
            assert coord.recently_deleted() and deleted == []
            with _at(_now() + dt.timedelta(days=7, minutes=1)):
                run(coord.async_purge_recently_deleted())
        assert coord.recently_deleted() == []
        assert deleted == ["/api/taskmate/image/plants.jpg"]

    def test_a_picture_another_snapshot_needs_is_kept(self):
        coord, storage, *_ = _system()
        a = _chore(coord, "A", image_url="/api/taskmate/image/shared.jpg")
        with _at(_now()):
            run(coord.async_remove_chore(a.id))
        b = _chore(coord, "B", image_url="/api/taskmate/image/shared.jpg")
        with _at(_now() + dt.timedelta(days=3)):
            run(coord.async_remove_chore(b.id))
        delete = AsyncMock()
        with (
            patch("custom_components.taskmate.coord_chores.images.async_delete_image", delete),
            _at(_now() + dt.timedelta(days=8)),
        ):
            run(coord.async_purge_recently_deleted())
        delete.assert_not_awaited()
        assert [e["id"] for e in coord.recently_deleted()] == [b.id]


CINEMA_IMG = "/api/taskmate/image/" + "c" * 32 + ".png"


class TestReward:
    def test_restore_brings_back_claims_and_moves_savings_back(self):
        coord, storage, kid, other = _system()
        with _at(_now()):
            first = run(coord.async_add_reward("Pick Friday dinner", cost=60))
            reward = run(coord.async_add_reward("Cinema trip", cost=200, pool_enabled=True))
            run(coord.async_add_reward("Xbox", cost=40))
        kid.points = 100
        storage.update_child(kid)
        storage.upsert_pool_allocation(PoolAllocation(child_id=kid.id, reward_id=reward.id, allocated_points=80))
        storage.add_reward_claim(
            RewardClaim(reward_id=reward.id, child_id=kid.id, claimed_at=_now(), approved=True, approved_cost=200)
        )
        with _at(_now()):
            run(coord.async_remove_reward(reward.id))
        assert storage.get_child(kid.id).points == 180  # savings refunded
        assert storage.get_reward_claims() == []

        kid = storage.get_child(kid.id)
        kid.points = 50  # spent some of the refund meanwhile
        storage.update_child(kid)
        with _at(_now()):
            run(coord.async_restore_deleted("reward", reward.id))

        assert [r.id for r in storage.get_rewards()][:2] == [first.id, reward.id]  # back in its old place
        assert [c.reward_id for c in storage.get_reward_claims()] == [reward.id]
        assert storage.get_pool_allocation(kid.id, reward.id).allocated_points == 50
        assert storage.get_child(kid.id).points == 0
        assert storage.get_points_transactions()[-1].points == -50

    def test_picture_waits_for_the_purge_so_restore_keeps_it(self):
        coord, storage, *_ = _system()
        with _at(_now()):
            reward = run(coord.async_add_reward("Cinema trip", cost=200))
        reward.image_url = CINEMA_IMG
        storage.update_reward(reward)
        delete = AsyncMock()
        with patch("custom_components.taskmate.images.async_delete_image", delete):
            with _at(_now()):
                run(coord.async_remove_reward(reward.id))
            delete.assert_not_awaited()  # still needed by the snapshot
            with _at(_now()):
                run(coord.async_restore_deleted("reward", reward.id))
            assert storage.get_reward(reward.id).image_url == CINEMA_IMG
            with _at(_now()):
                run(coord.async_remove_reward(reward.id))
            with _at(_now() + dt.timedelta(days=7, minutes=1)):
                run(coord.async_purge_recently_deleted())
        delete.assert_awaited_once()
        assert delete.await_args.args[1] == CINEMA_IMG


class TestQuest:
    def test_restore_brings_back_progress(self):
        coord, storage, kid, _other = _system()
        chore = _chore(coord)
        with _at(_now()):
            quest_id = run(coord.async_create_quest(name="Half-term quest", steps=[chore.id]))
        storage.set_quest_child_progress(quest_id, kid.id, {"step": 1, "completed_count": 2})
        with _at(_now()):
            run(coord.async_delete_quest(quest_id))
        assert storage.get_quest(quest_id) is None
        with _at(_now()):
            restored = run(coord.async_restore_deleted("quest", quest_id))
        assert restored == {"kind": "quest", "id": quest_id, "name": "Half-term quest"}
        assert isinstance(storage.get_quest(quest_id), Quest)
        assert storage.get_quest_child_progress(quest_id, kid.id) == {"step": 1, "completed_count": 2}


def test_list_is_newest_first_without_payloads():
    coord, *_ = _system()
    a, b = _chore(coord, "A"), _chore(coord, "B")
    with _at(_now()):
        run(coord.async_remove_chore(a.id))
    with _at(_now() + dt.timedelta(hours=1)):
        run(coord.async_remove_chore(b.id))
    listed = coord.recently_deleted()
    assert [e["name"] for e in listed] == ["B", "A"]
    assert set(listed[0]) == {"kind", "id", "name", "deleted_at"}


def test_restore_command_is_admin_only_and_registered():
    from custom_components.taskmate import websocket_panel_tools as tools

    assert tools.ws_trash_restore in tools.PANEL_TOOL_COMMANDS
    src = __import__("inspect").getsource(tools)
    assert src.count("@_admin_only") == len(tools.PANEL_TOOL_COMMANDS)
