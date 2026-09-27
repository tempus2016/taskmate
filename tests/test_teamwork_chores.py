"""Teamwork chores: a chore that needs two or more children together (#928).

Each child's Done tap joins the day's occurrence; once ``team_size`` different
children have joined, the chore submits for all of them at once through the
normal approval rules. ``team_points_mode`` "each" pays everyone the full
points, "split" divides them (rounded down), and ``team_bonus`` is added per
participant. A child can leave before the team fills, and joins reset when the
day rolls over.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taskmate.coord_teamwork import teamwork_config_error
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, ChoreCompletion
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc
NOW = dt.datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC)
TODAY = NOW.date().isoformat()
YESTERDAY = (NOW.date() - dt.timedelta(days=1)).isoformat()


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _storage(chores, children) -> TaskMateStorage:
    from tests.conftest import FakeStore

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {
        "chores": [c.to_dict() for c in chores],
        "children": [c.to_dict() for c in children],
        "completions": [],
    }
    return storage


def _team(**kwargs) -> Chore:
    kwargs.setdefault("team_size", 2)
    kwargs.setdefault("requires_approval", False)
    kwargs.setdefault("points", 10)
    return Chore(name="Wash the car", id="car", **kwargs)


KIDS = [Child(name="Mia", id="k1"), Child(name="Leo", id="k2"), Child(name="Ava", id="k3")]


def _coord(chore: Chore, children=KIDS):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    coord.hass.data = {}
    coord.storage = _storage([chore], children)
    # The eligibility gates are covered elsewhere; here every child may act.
    coord._is_chore_completable_by_child = MagicMock(return_value=True)
    coord.is_chore_available_for_child = MagicMock(return_value=True)
    coord.weekly_target_met = MagicMock(return_value=False)
    coord._is_rotation_done_today = MagicMock(return_value=False)
    coord._apply_roulette_multiplier = MagicMock(side_effect=lambda c, cid, b: b)
    coord.difficulty_multiplier = MagicMock(return_value=1.0)
    coord._award_points = AsyncMock(side_effect=lambda child, pts, **kw: pts)
    coord._async_notify_pending_approval = AsyncMock()
    coord.async_refresh = AsyncMock()
    coord.badges = None
    return coord


def _complete(coord, child_id, **kwargs):
    with (
        patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW),
        patch("custom_components.taskmate.coord_teamwork.dt_util.now", return_value=NOW),
    ):
        return run(coord.async_complete_chore("car", child_id, **kwargs))


def _leave(coord, child_id, chore_id="car"):
    with patch("custom_components.taskmate.coord_teamwork.dt_util.now", return_value=NOW):
        return run(coord.async_leave_team_chore(chore_id, child_id))


def _joined(coord):
    return [j["child_id"] for j in coord.storage.get_team_joins("car", TODAY)]


# ── the fields ───────────────────────────────────────────────────────────────


def test_teamwork_fields_default_to_an_ordinary_chore():
    chore = Chore(name="Dishes")
    assert (chore.team_size, chore.team_points_mode, chore.team_bonus) == (0, "each", 0)


def test_teamwork_fields_round_trip_through_storage():
    chore = _team(team_size=3, team_points_mode="split", team_bonus=2)
    back = Chore.from_dict(chore.to_dict())
    assert (back.team_size, back.team_points_mode, back.team_bonus) == (3, "split", 2)


def test_old_records_without_the_fields_load_as_ordinary_chores():
    data = Chore(name="Dishes").to_dict()
    for key in ("team_size", "team_points_mode", "team_bonus"):
        data.pop(key)
    back = Chore.from_dict(data)
    assert (back.team_size, back.team_points_mode, back.team_bonus) == (0, "each", 0)


def test_unknown_points_mode_loads_as_each():
    data = _team().to_dict()
    data["team_points_mode"] = "bogus"
    assert Chore.from_dict(data).team_points_mode == "each"


# ── what can be a teamwork chore ─────────────────────────────────────────────


def test_zero_is_an_ordinary_chore_whatever_else_is_set():
    assert teamwork_config_error(0, assignment_mode="first_come", open_ended=True) is None


def test_a_valid_team_is_accepted():
    assert teamwork_config_error(3) is None


@pytest.mark.parametrize("size", [1, 11])
def test_team_size_out_of_range_is_refused(size):
    assert teamwork_config_error(size)


def test_first_come_is_refused():
    assert "first-come" in teamwork_config_error(2, assignment_mode="first_come")


@pytest.mark.parametrize("mode", ["alternating", "random", "balanced"])
def test_rotation_modes_are_refused(mode):
    assert teamwork_config_error(2, assignment_mode=mode)


def test_open_ended_is_refused():
    assert "open-ended" in teamwork_config_error(2, open_ended=True)


def test_timed_task_is_refused():
    assert teamwork_config_error(2, task_type="timed")


def test_update_chore_refuses_a_first_come_team_before_storing_it():
    chore = _team()
    coord = _coord(chore)
    chore.assignment_mode = "first_come"
    with pytest.raises(ValueError):
        run(coord.async_update_chore(chore))
    assert coord.storage.get_chore("car").assignment_mode == "everyone"


def test_update_chore_refuses_an_open_ended_team():
    chore = _team()
    coord = _coord(chore)
    chore.open_ended = True
    with pytest.raises(ValueError):
        run(coord.async_update_chore(chore))
    assert coord.storage.get_chore("car").open_ended is False


def test_add_chore_refuses_a_bad_team_size():
    coord = _coord(_team())
    with pytest.raises(ValueError):
        run(coord.async_add_chore(name="Solo team", team_size=1))
    assert len(coord.storage.get_chores()) == 1


def test_a_stored_first_come_team_behaves_as_an_ordinary_chore():
    # Something that reached storage without going through validation (an old
    # backup, a template pack) must not become a team nobody can finish.
    coord = _coord(_team(assignment_mode="first_come"))
    comp = _complete(coord, "k1")
    assert comp is not None
    assert _joined(coord) == []


# ── joining ──────────────────────────────────────────────────────────────────


def test_a_join_records_no_completion():
    coord = _coord(_team(team_size=3))
    assert _complete(coord, "k1") is None
    assert coord.storage.get_completions() == []
    assert _joined(coord) == ["k1"]
    coord._award_points.assert_not_awaited()


def test_a_join_fires_a_joined_event():
    coord = _coord(_team(team_size=3))
    _complete(coord, "k1")
    name, data = coord.hass.bus.async_fire.call_args.args
    assert name == "taskmate_team_chore_joined"
    assert (data["child_id"], data["joined"], data["team_size"]) == ("k1", 1, 3)


def test_joining_twice_is_a_no_op():
    coord = _coord(_team(team_size=3))
    _complete(coord, "k1")
    _complete(coord, "k1")
    assert _joined(coord) == ["k1"]
    assert coord.storage.get_completions() == []


def test_the_join_that_fills_the_team_completes_it_for_everyone():
    coord = _coord(_team(team_size=2))
    _complete(coord, "k1")
    own = _complete(coord, "k2")
    comps = coord.storage.get_completions()
    assert sorted(c.child_id for c in comps) == ["k1", "k2"]
    assert own is not None and own.child_id == "k2"
    assert _joined(coord) == []
    assert all(c.approved and c.points_awarded == 10 for c in comps)


def test_a_filled_team_refreshes_once():
    coord = _coord(_team(team_size=3))
    _complete(coord, "k1")
    _complete(coord, "k2")
    coord.async_refresh.reset_mock()
    _complete(coord, "k3")
    assert coord.async_refresh.await_count == 1


def test_a_filled_team_fires_a_team_completed_event():
    coord = _coord(_team(team_size=2))
    _complete(coord, "k1")
    _complete(coord, "k2")
    names = [c.args[0] for c in coord.hass.bus.async_fire.call_args_list]
    assert names.count("taskmate_chore_completed") == 2
    assert "taskmate_team_chore_completed" in names


def test_a_non_participant_is_not_credited():
    coord = _coord(_team(team_size=2))
    _complete(coord, "k1")
    _complete(coord, "k2")
    assert not any(c.child_id == "k3" for c in coord.storage.get_completions())


def test_after_a_team_finishes_the_next_tap_starts_a_new_team():
    coord = _coord(_team(team_size=2))
    _complete(coord, "k1")
    _complete(coord, "k2")
    _complete(coord, "k3")
    assert _joined(coord) == ["k3"]


def test_joins_from_yesterday_do_not_count():
    coord = _coord(_team(team_size=2))
    coord.storage.set_team_joins("car", YESTERDAY, [{"child_id": "k1", "joined_at": "x"}])
    assert _complete(coord, "k2") is None
    assert _joined(coord) == ["k2"]
    assert coord.storage.get_completions() == []


def test_a_child_over_the_daily_limit_cannot_join():
    coord = _coord(_team(team_size=2))
    coord.storage.add_completion(ChoreCompletion(chore_id="car", child_id="k1", completed_at=NOW))
    assert _complete(coord, "k1") is None
    assert _joined(coord) == []


# ── approval and points ──────────────────────────────────────────────────────


def test_an_approval_chore_submits_pending_completions_for_the_team():
    coord = _coord(_team(team_size=2, requires_approval=True))
    _complete(coord, "k1")
    _complete(coord, "k2")
    comps = coord.storage.get_completions()
    assert len(comps) == 2
    assert not any(c.approved for c in comps)
    assert all(c.submitted_points == 10 for c in comps)
    assert coord._async_notify_pending_approval.await_count == 2
    coord._award_points.assert_not_awaited()


def test_a_parent_filling_the_team_approves_it():
    coord = _coord(_team(team_size=2, requires_approval=True))
    _complete(coord, "k1")
    _complete(coord, "k2", as_parent=True)
    assert all(c.approved for c in coord.storage.get_completions())


def test_split_mode_divides_the_points_rounding_down():
    coord = _coord(_team(team_size=3, team_points_mode="split"))
    for kid in ("k1", "k2", "k3"):
        _complete(coord, kid)
    assert [c.points_awarded for c in coord.storage.get_completions()] == [3, 3, 3]


def test_team_bonus_is_added_per_participant():
    coord = _coord(_team(team_size=2, team_bonus=4))
    _complete(coord, "k1")
    _complete(coord, "k2")
    assert [c.points_awarded for c in coord.storage.get_completions()] == [14, 14]


def test_split_and_bonus_combine():
    chore = _team(team_size=3, team_points_mode="split", team_bonus=2)
    assert _coord(chore).team_share_points(chore) == 5


def test_an_ordinary_chore_share_is_just_its_points():
    chore = Chore(name="Dishes", points=7)
    assert _coord(chore).team_share_points(chore) == 7


# ── photos ───────────────────────────────────────────────────────────────────


def test_a_photo_chore_needs_a_photo_to_join():
    coord = _coord(_team(team_size=2, require_photo=True))
    with pytest.raises(ValueError):
        _complete(coord, "k1")
    assert _joined(coord) == []


def test_each_childs_photo_lands_on_their_own_completion():
    coord = _coord(_team(team_size=2, require_photo=True))
    with patch("custom_components.taskmate.coord_chores.photos.is_taskmate_photo_url", return_value=True):
        _complete(coord, "k1", photo_url="/api/taskmate/photo/a.jpg")
        _complete(coord, "k2", photo_url="/api/taskmate/photo/b.jpg")
    by_child = {c.child_id: c.photo_url for c in coord.storage.get_completions()}
    assert by_child == {"k1": "/api/taskmate/photo/a.jpg", "k2": "/api/taskmate/photo/b.jpg"}


# ── leaving ──────────────────────────────────────────────────────────────────


def test_a_child_can_leave_before_the_team_fills():
    coord = _coord(_team(team_size=3))
    _complete(coord, "k1")
    _complete(coord, "k2")
    assert _leave(coord, "k1") is True
    assert _joined(coord) == ["k2"]


def test_leaving_without_having_joined_is_a_soft_no_op():
    coord = _coord(_team(team_size=3))
    assert _leave(coord, "k1") is False


def test_leaving_an_ordinary_chore_is_refused():
    coord = _coord(Chore(name="Wash the car", id="car"))
    with pytest.raises(ValueError):
        _leave(coord, "k1")


def test_leaving_an_unknown_chore_is_refused():
    coord = _coord(_team())
    with pytest.raises(ValueError):
        _leave(coord, "k1", chore_id="nope")


def test_the_team_needs_a_replacement_after_someone_leaves():
    coord = _coord(_team(team_size=2))
    _complete(coord, "k1")
    _leave(coord, "k1")
    assert _complete(coord, "k2") is None
    assert coord.storage.get_completions() == []


# ── storage housekeeping ─────────────────────────────────────────────────────


def test_prune_drops_other_days():
    storage = _storage([], [])
    storage.set_team_joins("a", YESTERDAY, [{"child_id": "k1"}])
    storage.set_team_joins("b", TODAY, [{"child_id": "k2"}])
    storage.prune_team_joins(TODAY)
    assert set(storage._data["team_joins"]) == {"b"}


def test_removing_a_child_takes_them_out_of_every_team():
    storage = _storage([], [])
    storage.set_team_joins("a", TODAY, [{"child_id": "k1"}, {"child_id": "k2"}])
    storage.set_team_joins("b", TODAY, [{"child_id": "k1"}])
    storage.remove_team_joins_for_child("k1")
    assert storage.get_team_joins("a", TODAY) == [{"child_id": "k2"}]
    assert "b" not in storage._data["team_joins"]


def test_removing_a_chore_drops_its_joins():
    storage = _storage([], [])
    storage.set_team_joins("a", TODAY, [{"child_id": "k1"}])
    storage.remove_team_joins_for_chore("a")
    assert storage.get_team_joins("a", TODAY) == []


def test_clearing_the_last_join_removes_the_entry():
    storage = _storage([], [])
    storage.set_team_joins("a", TODAY, [{"child_id": "k1"}])
    storage.set_team_joins("a", TODAY, [])
    assert "a" not in storage._data["team_joins"]


# ── interplay with neighbouring features ─────────────────────────────────────


def _scan(coord, child_id):
    from custom_components.taskmate import coord_tags

    coord.chores_for_tag = MagicMock(return_value=[coord.storage.get_chore("car")])
    coord._child_for_tag_user = MagicMock(side_effect=lambda uid: coord.storage.get_child(uid))
    coord._record_tag_audit = AsyncMock()
    coord._async_record_tag_audit = AsyncMock()
    with (
        patch.object(coord_tags.authz, "_context_user_id", side_effect=lambda ctx: ctx),
        patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW),
        patch("custom_components.taskmate.coord_teamwork.dt_util.now", return_value=NOW),
    ):
        return run(coord.async_handle_tag_scan("tag-1", context=child_id))


def test_a_tag_scan_counts_as_a_join():
    # NFC tags (#923) complete through async_complete_chore, so a scan is a
    # join: nothing recorded until the team fills, then everyone's credited.
    coord = _coord(_team(team_size=2))
    assert _scan(coord, "k1") == []
    assert _joined(coord) == ["k1"]
    done = _scan(coord, "k2")
    assert [c.child_id for c in done] == ["k2"]
    assert sorted(c.child_id for c in coord.storage.get_completions()) == ["k1", "k2"]


def test_a_repeat_scan_does_not_leave_the_team():
    coord = _coord(_team(team_size=3))
    _scan(coord, "k1")
    _scan(coord, "k1")
    assert _joined(coord) == ["k1"]


def test_a_childs_undo_takes_back_only_their_own_share():
    # Child undo (#918): once the team has submitted, a child undoing theirs
    # leaves the team after the fact — their teammates keep their credit.
    coord = _coord(_team(team_size=2, requires_approval=True))
    coord.async_recheck_mandatory_miss = AsyncMock()
    coord.notifications = MagicMock()
    coord.notifications.clear_approval = AsyncMock()
    coord.storage._data["settings"] = {"chore_undo_seconds": 300}
    _complete(coord, "k1")
    _complete(coord, "k2")
    mine = next(c for c in coord.storage.get_completions() if c.child_id == "k1")
    assert mine.child_undo_allowed is True
    run(coord.async_undo_chore(mine.id))
    assert [c.child_id for c in coord.storage.get_completions()] == ["k2"]


def test_each_participant_is_rated_on_their_own_approval():
    # Quality rating (#927) belongs to an approval, and a team is one
    # completion per child — so the parent can rate each child's part.
    coord = _coord(_team(team_size=2, requires_approval=True))
    coord.quality_rating_enabled = MagicMock(return_value=True)
    coord.quality_rating_multipliers = MagicMock(return_value={1: 0.5, 2: 0.75, 3: 1.0})
    coord.notifications = MagicMock()
    coord.notifications.clear_approval = AsyncMock()
    coord.notifications.fire = AsyncMock()
    coord.notifications._has_outstanding_chores_today = MagicMock(return_value=True)
    _complete(coord, "k1")
    _complete(coord, "k2")
    by_child = {c.child_id: c.id for c in coord.storage.get_completions()}
    run(coord.async_approve_chore(by_child["k1"], rating=1))
    run(coord.async_approve_chore(by_child["k2"], rating=3))
    paid = {c.child_id: (c.points_awarded, c.quality_rating) for c in coord.storage.get_completions()}
    assert paid == {"k1": (5, 1), "k2": (10, 3)}
