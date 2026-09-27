"""Children undoing their own chores inside an opt-in window (#918).

The window (``chore_undo_seconds``) is 0 by default, which must leave today's
behaviour untouched: only parents can undo. Above 0 a child may withdraw a
pending submission until a parent reviews it, and undo an auto-approved chore
until ``completed_at`` plus the window. A parent's review locks it for good,
and records written before the feature stay parent-only.

These drive the real coordinator against real storage, and the real
``taskmate.undo_chore`` service handler for the authorisation cases.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

import custom_components.taskmate as tm
from custom_components.taskmate.chore_undo import child_can_undo, child_undo_metadata, undo_window_seconds
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import BonusSubTask, ChoreCompletion
from custom_components.taskmate.sensor import _build_todays_completions
from custom_components.taskmate.storage import TaskMateStorage
from custom_components.taskmate.websocket import (
    _SUBKEY_SETTINGS,
    _UPDATE_SETTINGS_SCHEMA,
    _build_state_snapshot,
    _validate_chore_undo_seconds,
)
from tests.conftest import FakeHass, FakeServiceValidationError, FakeStore, FakeUnauthorized, dt_util_mock

START = dt_util_mock._now


@pytest.fixture
def clock(monkeypatch):
    """Move 'now' for every module that reads dt_util.now()."""

    class Clock:
        def set(self, when):
            monkeypatch.setattr(dt_util_mock, "_now", when)

        def advance(self, **kwargs):
            self.set(dt_util_mock._now + timedelta(**kwargs))

    c = Clock()
    c.set(START)
    return c


async def _make_system(window: int | None = None):
    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    await storage.async_load()
    storage.set_setting("weekend_multiplier", "1")
    storage.set_setting("streak_milestones_enabled", "false")
    if window is not None:
        storage.set_setting("chore_undo_seconds", window)

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = FakeHass()
    coord.hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()
    coord.data = {}
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    coord._async_notify_pending_approval = AsyncMock()
    coord.notifications = AsyncMock()
    coord.notifications._has_outstanding_chores_today = lambda _cid: True
    coord.async_record_audit = AsyncMock()
    return coord, storage


async def _chore(coord, child, *, approval=False, points=10, name="Dishes"):
    return await coord.async_add_chore(name, points=points, assigned_to=[child.id], requires_approval=approval)


def _get(storage, completion_id):
    return next((c for c in storage.get_completions() if c.id == completion_id), None)


def _fired(coord, event):
    return [c for c in coord.hass.bus.async_fire.call_args_list if c.args and c.args[0] == event]


# ── window 0: exactly today's behaviour ──────────────────────────────────────


def test_window_defaults_to_zero():
    async def scenario():
        _, storage = await _make_system()
        assert storage.get_chore_undo_seconds() == 0

    asyncio.run(scenario())


@pytest.mark.parametrize("approval", [False, True])
def test_window_zero_means_no_child_undo(clock, approval):
    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        chore = await _chore(coord, child, approval=approval)
        completion = await coord.async_complete_chore(chore.id, child.id)

        stored = _get(storage, completion.id)
        assert stored.child_undo_allowed is False, "nothing made while off may be undone later"
        assert "child_undo_allowed" not in stored.to_dict()

        with pytest.raises(ValueError):
            await coord.async_undo_chore(completion.id)
        assert _get(storage, completion.id) is not None
        assert storage.get_child(child.id).points == (0 if approval else 10)

    asyncio.run(scenario())


def test_turning_the_window_on_later_does_not_open_old_completions(clock):
    async def scenario():
        coord, storage = await _make_system()
        child = await coord.async_add_child("Alice")
        pending = await coord.async_complete_chore((await _chore(coord, child, approval=True)).id, child.id)
        storage.set_setting("chore_undo_seconds", 600)
        with pytest.raises(ValueError):
            await coord.async_undo_chore(pending.id)
        assert _get(storage, pending.id) is not None

    asyncio.run(scenario())


# ── pending withdrawal ───────────────────────────────────────────────────────


def test_pending_submission_can_be_withdrawn_until_reviewed(clock):
    async def scenario():
        coord, storage = await _make_system(window=30)
        child = await coord.async_add_child("Alice")
        chore = await _chore(coord, child, approval=True)
        completion = await coord.async_complete_chore(chore.id, child.id)
        assert _get(storage, completion.id).child_undo_allowed is True

        # Long past the window: a pending submission has no deadline.
        clock.advance(hours=3)
        assert child_undo_metadata(completion, storage.get_completions(), 30) == {"child_undo_pending": True}
        await coord.async_undo_chore(completion.id)

        assert _get(storage, completion.id) is None
        after = storage.get_child(child.id)
        assert after.points == 0
        assert after.total_chores_completed == 0
        assert _fired(coord, "taskmate_chore_undone")
        assert not _fired(coord, "taskmate_chore_rejected")

    asyncio.run(scenario())


# ── auto-approved, within and after the window ───────────────────────────────


def test_auto_approved_chore_undone_within_window_reverses_everything(clock):
    async def scenario():
        coord, storage = await _make_system(window=60)
        child = await coord.async_add_child("Alice")
        chore = await _chore(coord, child)
        completion = await coord.async_complete_chore(chore.id, child.id)
        paid = storage.get_child(child.id)
        assert (paid.points, paid.total_chores_completed, paid.current_streak) == (10, 1, 1)
        assert paid.career_score == 10

        clock.advance(seconds=59)
        await coord.async_undo_chore(completion.id)

        after = storage.get_child(child.id)
        assert after.points == 0
        assert after.total_points_earned == 0
        assert after.total_chores_completed == 0
        assert after.current_streak == 0
        assert after.career_score == 0
        assert after.last_completion_date is None
        assert _get(storage, completion.id) is None
        # The recurrence window reopens, so the chore can be done again.
        again = await coord.async_complete_chore(chore.id, child.id)
        assert _get(storage, again.id) is not None

    asyncio.run(scenario())


@pytest.mark.parametrize("elapsed", [60, 61, 3600])
def test_auto_approved_chore_locked_once_the_window_has_passed(clock, elapsed):
    async def scenario():
        coord, storage = await _make_system(window=60)
        child = await coord.async_add_child("Alice")
        completion = await coord.async_complete_chore((await _chore(coord, child)).id, child.id)

        clock.advance(seconds=elapsed)
        with pytest.raises(ValueError):
            await coord.async_undo_chore(completion.id)
        assert _get(storage, completion.id) is not None
        assert storage.get_child(child.id).points == 10

    asyncio.run(scenario())


def test_deadline_is_counted_from_completion_time(clock):
    async def scenario():
        coord, storage = await _make_system(window=90)
        child = await coord.async_add_child("Alice")
        completion = await coord.async_complete_chore((await _chore(coord, child)).id, child.id)
        meta = child_undo_metadata(_get(storage, completion.id), storage.get_completions(), 90)
        assert meta == {"child_undo_until": (START + timedelta(seconds=90)).isoformat()}

    asyncio.run(scenario())


def test_timed_session_stopped_by_the_child_is_undoable(clock):
    async def scenario():
        coord, storage = await _make_system(window=120)
        child = await coord.async_add_child("Alice")
        chore = await _chore(coord, child, name="Reading")
        chore.task_type = "timed"
        chore.timed_rate_minutes = 1
        chore.timed_rate_points = 1
        storage.update_chore(chore)
        await coord.async_start_timed_task(chore.id, child.id)
        clock.advance(minutes=5)
        await coord.async_stop_timed_task(chore.id, child.id)
        completion = next(c for c in storage.get_completions() if c.chore_id == chore.id)
        assert completion.child_undo_allowed is True
        assert storage.get_child(child.id).points == 5

        await coord.async_undo_chore(completion.id)
        assert storage.get_child(child.id).points == 0

    asyncio.run(scenario())


# ── a parent's review locks it ───────────────────────────────────────────────


def test_parent_approval_locks_child_undo(clock):
    async def scenario():
        coord, storage = await _make_system(window=3600)
        child = await coord.async_add_child("Alice")
        completion = await coord.async_complete_chore((await _chore(coord, child, approval=True)).id, child.id)
        await coord.async_approve_chore(completion.id)

        assert _get(storage, completion.id).child_undo_allowed is False
        with pytest.raises(ValueError):
            await coord.async_undo_chore(completion.id)
        assert storage.get_child(child.id).points == 10

    asyncio.run(scenario())


def test_parent_undoing_an_approval_keeps_child_undo_locked(clock):
    async def scenario():
        coord, storage = await _make_system(window=3600)
        child = await coord.async_add_child("Alice")
        completion = await coord.async_complete_chore((await _chore(coord, child)).id, child.id)
        await coord.async_undo_chore_approval(completion.id)

        back_to_pending = _get(storage, completion.id)
        assert back_to_pending.approved is False
        assert back_to_pending.child_undo_allowed is False
        with pytest.raises(ValueError):
            await coord.async_undo_chore(completion.id)

    asyncio.run(scenario())


def test_parent_can_still_reject_whatever_the_window(clock):
    async def scenario():
        coord, storage = await _make_system(window=0)
        child = await coord.async_add_child("Alice")
        completion = await coord.async_complete_chore((await _chore(coord, child)).id, child.id)
        await coord.async_reject_chore(completion.id)
        assert _get(storage, completion.id) is None
        assert storage.get_child(child.id).points == 0
        assert _fired(coord, "taskmate_chore_rejected")

    asyncio.run(scenario())


def test_completed_as_parent_is_not_the_childs_to_undo(clock):
    async def scenario():
        coord, storage = await _make_system(window=3600)
        child = await coord.async_add_child("Alice")
        completion = await coord.async_complete_chore(
            (await _chore(coord, child, approval=True)).id, child.id, as_parent=True
        )
        assert completion.child_undo_allowed is False
        with pytest.raises(ValueError):
            await coord.async_undo_chore(completion.id)

    asyncio.run(scenario())


# ── bonus sub-tasks ride with their chore ────────────────────────────────────


def test_undoing_a_chore_takes_its_bonus_subtasks_with_it(clock):
    async def scenario():
        coord, storage = await _make_system(window=300)
        child = await coord.async_add_child("Alice")
        chore = await _chore(coord, child)
        chore.bonus_subtasks = [BonusSubTask(id="dry", name="Dry up", points=4)]
        storage.update_chore(chore)
        main = await coord.async_complete_chore(chore.id, child.id)
        await coord.async_complete_bonus_subtask(chore.id, "dry", child.id)
        assert storage.get_child(child.id).points == 14

        await coord.async_undo_chore(main.id)
        assert storage.get_completions() == []
        after = storage.get_child(child.id)
        assert (after.points, after.total_chores_completed) == (0, 0)

    asyncio.run(scenario())


def test_bonus_ticked_from_the_panel_blocks_the_childs_undo_of_the_chore(clock):
    async def scenario():
        coord, storage = await _make_system(window=300)
        child = await coord.async_add_child("Alice")
        chore = await _chore(coord, child)
        chore.bonus_subtasks = [BonusSubTask(id="dry", name="Dry up", points=4)]
        storage.update_chore(chore)
        main = await coord.async_complete_chore(chore.id, child.id)
        await coord.async_complete_bonus_subtask(chore.id, "dry", child.id, by_child=False)

        with pytest.raises(ValueError):
            await coord.async_undo_chore(main.id)
        assert storage.get_child(child.id).points == 14

    asyncio.run(scenario())


def test_a_bonus_subtask_can_be_undone_on_its_own(clock):
    async def scenario():
        coord, storage = await _make_system(window=300)
        child = await coord.async_add_child("Alice")
        chore = await _chore(coord, child)
        chore.bonus_subtasks = [BonusSubTask(id="dry", name="Dry up", points=4)]
        storage.update_chore(chore)
        main = await coord.async_complete_chore(chore.id, child.id)
        bonus = await coord.async_complete_bonus_subtask(chore.id, "dry", child.id)

        await coord.async_undo_chore(bonus.id)
        assert [c.id for c in storage.get_completions()] == [main.id]
        assert storage.get_child(child.id).points == 10

    asyncio.run(scenario())


# ── legacy records ───────────────────────────────────────────────────────────


def test_legacy_record_loads_parent_only():
    legacy = {
        "id": "old",
        "chore_id": "c",
        "child_id": "k",
        "completed_at": START.isoformat(),
        "approved": False,
        "points_awarded": 0,
    }
    completion = ChoreCompletion.from_dict(legacy)
    assert completion.child_undo_allowed is False
    assert "child_undo_allowed" not in completion.to_dict()
    assert child_undo_metadata(completion, [completion], 3600) == {}
    assert child_can_undo(completion, [completion], 3600) is False


@pytest.mark.parametrize("raw", ["true", 1, "yes", None])
def test_only_a_real_true_flag_counts(raw):
    completion = ChoreCompletion.from_dict(
        {"id": "x", "chore_id": "c", "child_id": "k", "completed_at": START.isoformat(), "child_undo_allowed": raw}
    )
    assert completion.child_undo_allowed is False


def test_flag_round_trips():
    completion = ChoreCompletion(chore_id="c", child_id="k", completed_at=START, child_undo_allowed=True)
    assert ChoreCompletion.from_dict(completion.to_dict()).child_undo_allowed is True


def test_legacy_record_in_storage_cannot_be_undone_by_a_child(clock):
    async def scenario():
        coord, storage = await _make_system(window=3600)
        child = await coord.async_add_child("Alice")
        chore = await _chore(coord, child, approval=True)
        storage.add_completion(ChoreCompletion(chore_id=chore.id, child_id=child.id, completed_at=START))
        legacy = storage.get_completions()[0]
        with pytest.raises(ValueError):
            await coord.async_undo_chore(legacy.id)
        assert _get(storage, legacy.id) is not None

    asyncio.run(scenario())


# ── the service: authorisation from the stored completion ────────────────────


class _Services:
    def __init__(self):
        self.handlers = {}

    def async_register(self, domain, name, handler, schema=None):
        self.handlers[name] = handler


async def _service(coord, monkeypatch, *, user):
    monkeypatch.setattr(tm, "_get_coordinator", lambda hass: coord)
    services = _Services()
    hass = MagicMock()
    hass.services = services
    hass.auth.async_get_user = AsyncMock(return_value=user)
    await tm._async_register_services(hass)
    return services.handlers[tm.SERVICE_UNDO_CHORE]


def _call(user_id, **data):
    call = MagicMock()
    call.context.user_id = user_id
    call.data = data
    return call


async def _siblings(window=600):
    coord, storage = await _make_system(window=window)
    alice = await coord.async_add_child("Alice")
    bob = await coord.async_add_child("Bob")
    alice.linked_user_id = "uid-alice"
    bob.linked_user_id = "uid-bob"
    storage.update_child(alice)
    storage.update_child(bob)
    chore = await coord.async_add_chore("Dishes", points=10, assigned_to=[alice.id, bob.id], requires_approval=False)
    return coord, storage, alice, bob, chore


def test_service_is_unregistered_on_unload():
    hass = MagicMock()
    tm._async_unregister_services(hass)
    removed = {c.args[1] for c in hass.services.async_remove.call_args_list}
    assert tm.SERVICE_UNDO_CHORE == "undo_chore"
    assert "undo_chore" in removed


def test_child_undoes_their_own_chore_through_the_service(clock, monkeypatch):
    async def scenario():
        coord, storage, alice, _bob, chore = await _siblings()
        completion = await coord.async_complete_chore(chore.id, alice.id)
        assert storage.get_child(alice.id).points == 10
        undo = await _service(coord, monkeypatch, user=MagicMock(is_admin=False))

        await undo(_call("uid-alice", completion_id=completion.id))
        assert _get(storage, completion.id) is None
        assert storage.get_child(alice.id).points == 0

    asyncio.run(scenario())


def test_child_cannot_undo_a_siblings_chore(clock, monkeypatch):
    async def scenario():
        coord, storage, alice, _bob, chore = await _siblings()
        completion = await coord.async_complete_chore(chore.id, alice.id)
        undo = await _service(coord, monkeypatch, user=MagicMock(is_admin=False))

        with pytest.raises(FakeUnauthorized):
            await undo(_call("uid-bob", completion_id=completion.id))
        assert _get(storage, completion.id) is not None
        assert storage.get_child(alice.id).points == 10

    asyncio.run(scenario())


def test_caller_supplied_child_is_ignored(clock, monkeypatch):
    async def scenario():
        coord, storage, alice, bob, chore = await _siblings()
        completion = await coord.async_complete_chore(chore.id, alice.id)
        undo = await _service(coord, monkeypatch, user=MagicMock(is_admin=False))

        # Bob naming himself doesn't make Alice's completion his.
        with pytest.raises(FakeUnauthorized):
            await undo(_call("uid-bob", completion_id=completion.id, child_id=bob.id))
        assert _get(storage, completion.id) is not None

        # And Alice naming Bob still acts on her own stored completion only.
        await undo(_call("uid-alice", completion_id=completion.id, child_id=bob.id))
        assert _get(storage, completion.id) is None
        assert storage.get_child(alice.id).points == 0
        assert storage.get_child(bob.id).points == 0

    asyncio.run(scenario())


def test_sibling_linked_user_cannot_use_an_unlinked_child(clock, monkeypatch):
    async def scenario():
        coord, storage, alice, _bob, chore = await _siblings()
        alice.linked_user_id = ""
        storage.update_child(alice)
        completion = await coord.async_complete_chore(chore.id, alice.id)
        undo = await _service(coord, monkeypatch, user=MagicMock(is_admin=False))

        with pytest.raises(FakeUnauthorized):
            await undo(_call("uid-bob", completion_id=completion.id))
        assert _get(storage, completion.id) is not None

    asyncio.run(scenario())


def test_strict_linked_child_mode_blocks_an_unlinked_kiosk_user(clock, monkeypatch):
    async def scenario():
        coord, storage, alice, _bob, chore = await _siblings()
        alice.linked_user_id = ""
        storage.update_child(alice)
        storage.set_setting("require_linked_child", True)
        completion = await coord.async_complete_chore(chore.id, alice.id)
        undo = await _service(coord, monkeypatch, user=MagicMock(is_admin=False))

        with pytest.raises(FakeUnauthorized):
            await undo(_call("uid-tablet", completion_id=completion.id))
        assert _get(storage, completion.id) is not None

    asyncio.run(scenario())


def test_service_still_applies_the_window_to_an_admin(clock, monkeypatch):
    """undo_chore is the child's route: an admin passes the link check, not the window."""

    async def scenario():
        coord, storage, alice, _bob, chore = await _siblings(window=60)
        completion = await coord.async_complete_chore(chore.id, alice.id)
        undo = await _service(coord, monkeypatch, user=MagicMock(is_admin=True))
        clock.advance(seconds=120)

        with pytest.raises(FakeServiceValidationError):
            await undo(_call("uid-admin", completion_id=completion.id))
        assert _get(storage, completion.id) is not None

    asyncio.run(scenario())


def test_service_refuses_when_the_window_is_zero(clock, monkeypatch):
    async def scenario():
        coord, storage, alice, _bob, chore = await _siblings(window=0)
        completion = await coord.async_complete_chore(chore.id, alice.id)
        undo = await _service(coord, monkeypatch, user=MagicMock(is_admin=False))

        with pytest.raises(FakeServiceValidationError):
            await undo(_call("uid-alice", completion_id=completion.id))
        assert _get(storage, completion.id) is not None

    asyncio.run(scenario())


def test_service_unknown_completion_is_a_clean_error(clock, monkeypatch):
    async def scenario():
        coord, _storage, *_ = await _siblings()
        undo = await _service(coord, monkeypatch, user=MagicMock(is_admin=False))
        with pytest.raises(FakeServiceValidationError):
            await undo(_call("uid-alice", completion_id="nope"))

    asyncio.run(scenario())


def test_second_undo_of_the_same_completion_fails_cleanly(clock, monkeypatch):
    async def scenario():
        coord, storage, alice, _bob, chore = await _siblings()
        completion = await coord.async_complete_chore(chore.id, alice.id)
        undo = await _service(coord, monkeypatch, user=MagicMock(is_admin=False))
        await undo(_call("uid-alice", completion_id=completion.id))
        with pytest.raises(FakeServiceValidationError):
            await undo(_call("uid-alice", completion_id=completion.id))
        assert storage.get_child(alice.id).points == 0

    asyncio.run(scenario())


# ── what the cards are told ──────────────────────────────────────────────────


def _common(storage):
    return {
        "child_lookup": {c.id: c for c in storage.get_children()},
        "chore_lookup": {c.id: c for c in storage.get_chores()},
        "all_completions": storage.get_completions(),
        "chore_undo_seconds": undo_window_seconds(storage),
    }


def test_sensor_publishes_undo_fields_only_while_allowed(clock):
    async def scenario():
        coord, storage = await _make_system(window=60)
        child = await coord.async_add_child("Alice")
        auto = await coord.async_complete_chore((await _chore(coord, child, name="Auto")).id, child.id)
        pending = await coord.async_complete_chore(
            (await _chore(coord, child, approval=True, name="Checked")).id, child.id
        )
        by_id = {r["completion_id"]: r for r in _build_todays_completions(_common(storage))}
        assert by_id[auto.id]["child_undo_until"] == (START + timedelta(seconds=60)).isoformat()
        assert "child_undo_pending" not in by_id[auto.id]
        assert by_id[pending.id]["child_undo_pending"] is True
        assert "child_undo_until" not in by_id[pending.id]

        await coord.async_approve_chore(pending.id)
        by_id = {r["completion_id"]: r for r in _build_todays_completions(_common(storage))}
        assert "child_undo_pending" not in by_id[pending.id]
        assert "child_undo_until" not in by_id[pending.id]

    asyncio.run(scenario())


def test_sensor_publishes_nothing_when_the_window_is_zero(clock):
    async def scenario():
        coord, storage = await _make_system(window=60)
        child = await coord.async_add_child("Alice")
        await coord.async_complete_chore((await _chore(coord, child)).id, child.id)
        storage.set_setting("chore_undo_seconds", 0)
        for rec in _build_todays_completions(_common(storage)):
            assert "child_undo_until" not in rec
            assert "child_undo_pending" not in rec

    asyncio.run(scenario())


# ── the setting ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", [0, 1, 60, 3600])
def test_setting_accepts_whole_seconds_in_range(value):
    assert _validate_chore_undo_seconds(value) == value


@pytest.mark.parametrize("value", [-1, 3601, True, False, 1.5, "60", None])
def test_setting_rejects_anything_else(value):
    import voluptuous as vol

    with pytest.raises(vol.Invalid):
        _validate_chore_undo_seconds(value)


def test_setting_is_routed_to_the_settings_subkey():
    assert "chore_undo_seconds" in _SUBKEY_SETTINGS
    assert any(getattr(k, "schema", k) == "chore_undo_seconds" for k in _UPDATE_SETTINGS_SCHEMA)


@pytest.mark.parametrize(
    ("stored", "expected"),
    [(None, 0), (30, 30), (-5, 0), (99999, 3600), ("45", 45), ("junk", 0), (True, 0), (float("nan"), 0)],
)
def test_storage_getter_clamps_and_defaults(stored, expected):
    async def scenario():
        _, storage = await _make_system()
        if stored is not None:
            storage._data.setdefault("settings", {})["chore_undo_seconds"] = stored
        assert storage.get_chore_undo_seconds() == expected

    asyncio.run(scenario())


def test_panel_snapshot_defaults_the_window_to_zero():
    async def scenario():
        coord, storage = await _make_system()
        coord.mandatory_misses_state = lambda: []
        coord.custom_sounds_state = lambda: []
        snap = _build_state_snapshot(coord)
        assert snap["settings"]["chore_undo_seconds"] == 0
        storage.set_setting("chore_undo_seconds", 120)
        assert _build_state_snapshot(coord)["settings"]["chore_undo_seconds"] == 120

    asyncio.run(scenario())
