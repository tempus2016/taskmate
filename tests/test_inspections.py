"""Surprise inspections (#981): spot-check a finished chore for a bonus.

A parent (or the random daily pick) flags an approved chore; inside the window
they pass it (a fixed bonus, paid as a normal transaction) or fail it (just
noted, or sent back to redo — the redo goes through the normal chore path but
pays nothing). An undecided inspection closes quietly, with a parent reminder
30 minutes before.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from custom_components.taskmate import coord_inspections as ci
from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate import websocket as ws
from custom_components.taskmate.coord_notifications import NOTIFICATION_TYPES_BY_ID
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.inspection_services import INSPECTION_SERVICES
from custom_components.taskmate.models import ChoreCompletion
from custom_components.taskmate.storage import TaskMateStorage

from .conftest import FakeHass, FakeStore, dt_util_mock

UTC = dt.timezone.utc
NOW = dt.datetime(2024, 3, 20, 12, 0, tzinfo=UTC)  # a Wednesday
ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "custom_components" / "taskmate"


@pytest.fixture(autouse=True)
def _clock():
    saved = dt_util_mock._now
    dt_util_mock._now = NOW
    yield
    dt_util_mock._now = saved


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _system(settings: dict | None = None):
    hass = FakeHass()
    hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()
    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    await storage.async_load()
    for key, value in (settings or {}).items():
        storage.set_setting(key, value)
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.data = {}
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    coord._async_notify_pending_approval = AsyncMock()
    notifications = MagicMock()
    notifications.fire = AsyncMock()
    notifications.clear_approval = AsyncMock()
    notifications._has_outstanding_chores_today = lambda _cid: True
    coord.notifications = notifications
    return coord


async def _approved(coord, *, points=3, requires_approval=False, name="Tidy bedroom", **chore_kw):
    """A child with one chore completed (auto-approved) just now."""
    child = await coord.async_add_child("Vaiha")
    chore = await coord.async_add_chore(
        name,
        points=points,
        requires_approval=requires_approval,
        schedule_mode=chore_kw.pop("schedule_mode", "specific_days"),
        assigned_to=[child.id],
        **chore_kw,
    )
    completion = await coord.async_complete_chore(chore.id, child.id)
    if requires_approval:
        await coord.async_approve_chore(completion.id)
    return child, chore, next(c for c in coord.storage.get_completions() if c.id == completion.id)


def _events(coord, name):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == name]


def _fired_types(coord):
    return [c.args[0] for c in coord.notifications.fire.await_args_list]


def _today_ids(coord):
    """Completion ids the child card sees as today's (the chores sensor)."""
    coord.data = coord._build_data_snapshot()
    if hasattr(coord, sensor_module._COMMON_CACHE_ATTR):
        delattr(coord, sensor_module._COMMON_CACHE_ATTR)
    common = sensor_module._compute_common(coord)
    return {r["completion_id"] for r in sensor_module._build_todays_completions(common)}


# ── starting ─────────────────────────────────────────────────────────────


def test_start_flags_an_approved_chore_with_the_settings_defaults():
    async def go():
        coord = await _system({"inspection_bonus": 15, "inspection_window": "4h"})
        child, chore, completion = await _approved(coord)
        with patch.object(ci, "async_track_point_in_time") as track:
            record = await coord.async_start_inspection(completion.id)
        assert record["status"] == "open" and record["bonus"] == 15 and record["tell_child"] is True
        assert record["chore_name"] == "Tidy bedroom" and record["points"] == 3
        assert ci._at(record["until"]) == NOW + dt.timedelta(hours=4)
        # The timer is armed for the reminder, 30 minutes before the end.
        assert track.call_args.args[2] == NOW + dt.timedelta(hours=3, minutes=30)
        assert _events(coord, "taskmate_inspection_started")[0]["chore_name"] == "Tidy bedroom"
        type_id, ctx = coord.notifications.fire.await_args.args
        assert type_id == "inspection_started" and ctx["bonus"] == 15
        assert coord.notifications.fire.await_args.kwargs["only_recipients"] == {f"child:{child.id}"}
        assert coord.storage.get_inspections() == [record]

    run(go())


def test_a_secret_inspection_does_not_tell_the_child():
    async def go():
        coord = await _system()
        child, _chore, completion = await _approved(coord)
        coord.notifications.fire.reset_mock()
        await coord.async_start_inspection(completion.id, tell_child=False, bonus=7, window="1h")
        assert "inspection_started" not in _fired_types(coord)
        assert coord.inspections_for_child(child.id) == []

    run(go())


@pytest.mark.parametrize(
    ("setup", "message"),
    [
        ("pending", "Only approved chores"),
        ("old", "last 24 hours"),
        ("twice", "already been inspected"),
        ("off", "switched off"),
    ],
)
def test_start_refuses(setup, message):
    async def go():
        coord = await _system({"inspections_enabled": setup != "off"})
        child = await coord.async_add_child("Vaiha")
        chore = await coord.async_add_chore(
            "Bed", points=2, requires_approval=setup == "pending", assigned_to=[child.id]
        )
        completion = await coord.async_complete_chore(chore.id, child.id)
        if setup == "old":
            dt_util_mock._now = NOW + dt.timedelta(hours=25)
        if setup == "twice":
            await coord.async_start_inspection(completion.id)
        with pytest.raises(ValueError, match=message):
            await coord.async_start_inspection(completion.id)

    run(go())


def test_until_bedtime_and_too_close_to_it():
    async def go():
        coord = await _system({"inspection_bedtime": "20:00"})
        assert coord.inspection_until("bed", NOW) == NOW.replace(hour=20, minute=0)
        late = NOW.replace(hour=19, minute=45)
        assert coord.inspection_until("bed", late) == late + dt.timedelta(hours=1)
        assert coord.inspection_until("2h", NOW) == NOW + dt.timedelta(hours=2)

    run(go())


BED_CASES = json.loads((ROOT / "tests" / "data" / "inspection_bed_cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", BED_CASES, ids=lambda c: f"{c['tz']}-{c['bedtime']}-{c['now']}")
def test_until_bedtime_matches_the_shared_cases(case, monkeypatch):
    """The panel's start dialog checks the same table (#997), so the two can't drift."""
    from zoneinfo import ZoneInfo

    zone = ZoneInfo(case["tz"])
    monkeypatch.setattr(dt_util_mock, "as_local", lambda value: value.astimezone(zone))

    async def go():
        coord = await _system({"inspection_bedtime": case["bedtime"]})
        now = dt.datetime.fromisoformat(case["now"].replace("Z", "+00:00"))
        until = dt.datetime.fromisoformat(case["until"].replace("Z", "+00:00"))
        assert coord.inspection_until("bed", now) == until

    run(go())


def test_panel_state_carries_the_bedtime_fallback_rule():
    async def go():
        coord = await _system()
        rule = coord.inspection_bed_rule()
        assert rule == {"min_minutes": ci._BEDTIME_MIN_MINUTES, "fallback_hours": ci._BEDTIME_FALLBACK_HOURS}
        # The shared cases assume these numbers; change them together.
        assert rule == {"min_minutes": 30, "fallback_hours": 1}
        src = (PKG / "websocket.py").read_text()
        assert '"inspection_bed_rule": coordinator.inspection_bed_rule()' in src

    run(go())


# ── passing ──────────────────────────────────────────────────────────────


def test_pass_pays_the_bonus_as_an_undoable_transaction_and_celebrates():
    async def go():
        coord = await _system()
        child, _chore, completion = await _approved(coord)
        before = coord.get_child(child.id).points
        record = await coord.async_start_inspection(completion.id, bonus=10)
        coord._celebrate = AsyncMock()
        done = await coord.async_pass_inspection(record["id"], bonus=12, note="  Brilliant,   even the desk ")
        assert done["status"] == "passed" and done["bonus"] == 12 and done["note"] == "Brilliant, even the desk"
        assert coord.get_child(child.id).points == before + 12
        txn = coord.storage.get_points_transactions()[-1]
        assert txn.reason == "Inspection passed: Tidy bedroom" and txn.points == 12
        assert done["bonus_txn_id"] == txn.id
        assert coord._celebrate.await_args.args[1] == "inspection_passed"
        assert "inspection_passed" in _fired_types(coord)
        # A normal bonus entry: the generic undo takes it back.
        await coord.async_undo_transaction(txn.id)
        assert coord.get_child(child.id).points == before

    run(go())


def _passed_with_bonus(coord, completion, **start_kw):
    async def go():
        record = await coord.async_start_inspection(completion.id, **start_kw)
        coord._celebrate = AsyncMock()
        await coord.async_pass_inspection(record["id"], note="Great")
        return coord._find_inspection(record["id"])

    return go()


def test_undoing_the_pass_bonus_reopens_an_inspection_still_in_its_window():
    """#996: the undo takes the pass back, so it's open to decide again."""

    async def go():
        coord = await _system()
        child, _chore, completion = await _approved(coord)
        record = await _passed_with_bonus(coord, completion, bonus=9, window="2h")
        dt_util_mock._now = NOW + dt.timedelta(minutes=20)
        with patch.object(ci, "async_track_point_in_time") as track:
            await coord.async_undo_transaction(record["bonus_txn_id"])
        undone = coord._find_inspection(record["id"])
        assert undone["status"] == "open" and undone["bonus"] == 9
        assert undone["decided_at"] is None and undone["note"] == "" and undone["bonus_txn_id"] == ""
        # The window timer is armed again for it.
        assert track.called
        # The child card shows it open again, not "passed +9".
        (item,) = coord.inspections_for_child(child.id)
        assert item["status"] == "open" and item["bonus"] == 9
        # The feed: started, and no pass (its transaction is gone).
        assert [e["type"] for e in coord.recent_inspection_events()] == ["inspection_started"]
        assert _events(coord, "taskmate_inspection_reopened")[0]["inspection_id"] == record["id"]
        # The parent can decide again: pass pays once more.
        before = coord.get_child(child.id).points
        await coord.async_pass_inspection(record["id"])
        assert coord.get_child(child.id).points == before + 9

    run(go())


def test_undoing_the_pass_bonus_after_the_window_closes_it_undecided():
    async def go():
        coord = await _system()
        child, _chore, completion = await _approved(coord)
        record = await _passed_with_bonus(coord, completion, bonus=9, window="1h")
        dt_util_mock._now = NOW + dt.timedelta(hours=3)
        await coord.async_undo_transaction(record["bonus_txn_id"])
        undone = coord._find_inspection(record["id"])
        assert undone["status"] == "expired" and undone["bonus_txn_id"] == "" and undone["note"] == ""
        assert undone["decided_at"] == ci.format_datetime(NOW + dt.timedelta(hours=3))
        assert coord.inspections_for_child(child.id) == []
        assert [e["type"] for e in coord.recent_inspection_events()] == ["inspection_started"]
        with pytest.raises(ValueError, match="already been decided"):
            await coord.async_pass_inspection(record["id"])

    run(go())


def test_undoing_the_pass_bonus_of_a_chore_since_undone_closes_it():
    """Nothing left to inspect: don't reopen it."""

    async def go():
        coord = await _system()
        _child, _chore, completion = await _approved(coord)
        record = await _passed_with_bonus(coord, completion, bonus=9)
        coord.storage._data["completions"] = [
            c for c in coord.storage._data.get("completions", []) if c.get("id") != completion.id
        ]
        await coord.async_undo_transaction(record["bonus_txn_id"])
        assert coord._find_inspection(record["id"])["status"] == "expired"

    run(go())


def test_undoing_an_unrelated_bonus_leaves_inspections_alone():
    async def go():
        coord = await _system()
        child, _chore, completion = await _approved(coord)
        record = await _passed_with_bonus(coord, completion, bonus=9)
        await coord.async_add_points(child.id, 5, reason="Bonus: helped out")
        other = coord.storage.get_points_transactions()[-1]
        await coord.async_undo_transaction(other.id)
        assert coord._find_inspection(record["id"])["status"] == "passed"

    run(go())


def test_a_zero_bonus_pass_pays_nothing_and_still_shows_in_the_feed():
    async def go():
        coord = await _system()
        child, _chore, completion = await _approved(coord)
        record = await coord.async_start_inspection(completion.id, bonus=0)
        before = len(coord.storage.get_points_transactions())
        await coord.async_pass_inspection(record["id"])
        assert len(coord.storage.get_points_transactions()) == before
        kinds = [e["type"] for e in coord.recent_inspection_events()]
        assert kinds == ["inspection_started", "inspection_passed"]

    run(go())


# ── failing ──────────────────────────────────────────────────────────────


def test_fail_just_noted_changes_nothing():
    async def go():
        coord = await _system()
        child, _chore, completion = await _approved(coord)
        points = coord.get_child(child.id).points
        record = await coord.async_start_inspection(completion.id)
        done = await coord.async_fail_inspection(record["id"], redo=False, note="Clothes on the floor")
        assert done["status"] == "failed"
        assert coord.get_child(child.id).points == points
        assert completion.id in _today_ids(coord)
        (item,) = coord.inspections_for_child(child.id)
        assert item["status"] == "failed" and item["note"] == "Clothes on the floor"

    run(go())


def test_ask_mode_defaults_a_fail_to_just_noted():
    async def go():
        coord = await _system({"inspection_fail_mode": "ask"})
        _child, _chore, completion = await _approved(coord)
        record = await coord.async_start_inspection(completion.id)
        assert (await coord.async_fail_inspection(record["id"]))["status"] == "failed"

    run(go())


def test_send_back_reopens_the_chore_and_the_redo_pays_nothing():
    async def go():
        coord = await _system({"inspection_fail_mode": "redo"})
        child, chore, completion = await _approved(coord, points=3)
        points = coord.get_child(child.id).points
        record = await coord.async_start_inspection(completion.id)
        done = await coord.async_fail_inspection(record["id"], note="Clothes by the wardrobe")
        assert done["status"] == "redo"
        # Not "done" any more: the card, the board and the to-do list agree.
        assert completion.id not in _today_ids(coord)
        assert chore.id in [c.id for c in coord.get_due_chores_for_child(child.id)]
        (item,) = coord.inspections_for_child(child.id)
        assert item["status"] == "redo" and item["points"] == 3 and item["note"] == "Clothes by the wardrobe"
        # The daily limit no longer blocks the redo; it pays nothing extra.
        redo = await coord.async_complete_chore(chore.id, child.id)
        assert redo is not None and redo.approved and redo.points_awarded == 0
        assert coord.get_child(child.id).points == points
        assert coord._find_inspection(record["id"])["redo_completion_id"] == redo.id
        assert completion.id in _today_ids(coord) and redo.id in _today_ids(coord)
        assert coord.inspections_for_child(child.id) == []
        # A third tap is the daily limit again.
        assert await coord.async_complete_chore(chore.id, child.id) is None

    run(go())


def test_a_redo_that_needs_approval_is_approved_for_nothing():
    async def go():
        coord = await _system()
        child, chore, completion = await _approved(coord, points=5, requires_approval=True)
        points = coord.get_child(child.id).points
        record = await coord.async_start_inspection(completion.id)
        await coord.async_fail_inspection(record["id"], redo=True)
        redo = await coord.async_complete_chore(chore.id, child.id)
        assert redo.approved is False and redo.submitted_points == 0
        await coord.async_approve_chore(redo.id)
        assert coord.get_child(child.id).points == points

    run(go())


def test_rejecting_the_redo_puts_the_chore_back_on_the_list():
    async def go():
        coord = await _system()
        child, chore, completion = await _approved(coord, requires_approval=True)
        record = await coord.async_start_inspection(completion.id)
        await coord.async_fail_inspection(record["id"], redo=True)
        redo = await coord.async_complete_chore(chore.id, child.id)
        await coord.async_reject_chore(redo.id)
        assert coord._find_inspection(record["id"])["redo_completion_id"] == ""
        assert completion.id not in _today_ids(coord)

    run(go())


def test_only_todays_plain_chore_can_be_sent_back():
    async def go():
        coord = await _system()
        _child, _chore, completion = await _approved(coord)
        record = await coord.async_start_inspection(completion.id, window="4h")
        dt_util_mock._now = NOW + dt.timedelta(hours=13)  # 01:00 the next day
        with pytest.raises(ValueError, match="finished today"):
            await coord.async_fail_inspection(record["id"], redo=True)
        assert coord._find_inspection(record["id"])["status"] == "open"

    run(go())


def test_rejecting_the_inspected_completion_voids_the_open_inspection():
    async def go():
        coord = await _system()
        _child, _chore, completion = await _approved(coord)
        await coord.async_start_inspection(completion.id)
        await coord.async_reject_chore(completion.id)
        assert coord.storage.get_inspections() == []

    run(go())


def test_cancel_forgets_it_and_it_can_be_flagged_again():
    async def go():
        coord = await _system()
        _child, _chore, completion = await _approved(coord)
        record = await coord.async_start_inspection(completion.id)
        await coord.async_cancel_inspection(record["id"])
        assert coord.storage.get_inspections() == []
        assert completion.id in coord.inspectable_completion_ids()
        await coord.async_start_inspection(completion.id)

    run(go())


# ── the window ───────────────────────────────────────────────────────────


def test_parent_is_reminded_then_the_inspection_closes_quietly():
    async def go():
        coord = await _system()
        child, _chore, completion = await _approved(coord)
        points = coord.get_child(child.id).points
        record = await coord.async_start_inspection(completion.id, window="2h")
        coord.notifications.fire.reset_mock()
        dt_util_mock._now = NOW + dt.timedelta(hours=1, minutes=31)
        assert await coord.async_sweep_inspections() is True
        type_id, ctx = coord.notifications.fire.await_args.args
        assert type_id == "inspection_reminder" and ctx["minutes"] == 29
        assert coord.notifications.fire.await_args.kwargs == {}
        assert await coord.async_sweep_inspections() is False  # reminded once
        dt_util_mock._now = NOW + dt.timedelta(hours=2)
        await coord.async_sweep_inspections()
        assert coord._find_inspection(record["id"])["status"] == "expired"
        assert _events(coord, "taskmate_inspection_expired")
        assert coord.get_child(child.id).points == points
        assert coord.inspections_for_child(child.id) == []

    run(go())


def test_a_short_window_is_not_reminded_the_moment_it_opens():
    async def go():
        coord = await _system({"inspection_bedtime": "12:20"})
        _child, _chore, completion = await _approved(coord)
        coord.inspection_until = lambda window, now: now + dt.timedelta(minutes=20)
        await coord.async_start_inspection(completion.id)
        coord.notifications.fire.reset_mock()
        await coord.async_sweep_inspections()
        assert "inspection_reminder" not in _fired_types(coord)

    run(go())


def test_startup_catches_up_on_what_came_due_while_ha_was_off():
    async def go():
        coord = await _system()
        _child, _chore, completion = await _approved(coord)
        record = await coord.async_start_inspection(completion.id, window="1h")
        dt_util_mock._now = NOW + dt.timedelta(hours=3)
        with patch.object(ci, "async_track_time_change") as daily:
            await coord.async_start_inspections()
        assert coord._find_inspection(record["id"])["status"] == "expired"
        assert daily.call_args.kwargs == {"hour": 17, "minute": 0, "second": 0}

    run(go())


# ── random daily pick ────────────────────────────────────────────────────


def test_random_pick_is_off_by_default():
    async def go():
        coord = await _system()
        await _approved(coord)
        assert await coord.async_run_inspection_pick() is None
        assert coord.storage.get_inspections() == []

    run(go())


def test_random_pick_flags_a_chore_approved_today_once_a_day():
    async def go():
        coord = await _system({"inspection_pick_enabled": True, "inspection_pick_chance": 100})
        child, _chore, completion = await _approved(coord)
        record = await coord.async_run_inspection_pick()
        assert record["completion_id"] == completion.id and record["source"] == "random"
        assert await coord.async_run_inspection_pick() is None  # rolled today already

    run(go())


def test_random_pick_never_picks_the_same_child_two_days_running():
    async def go():
        coord = await _system({"inspection_pick_enabled": True, "inspection_pick_chance": 100})
        child, chore, _completion = await _approved(coord)
        assert await coord.async_run_inspection_pick() is not None
        dt_util_mock._now = NOW + dt.timedelta(days=1)
        await coord.async_complete_chore(chore.id, child.id)
        assert await coord.async_run_inspection_pick() is None

    run(go())


def test_random_pick_respects_the_children_setting():
    async def go():
        coord = await _system(
            {"inspection_pick_enabled": True, "inspection_pick_chance": 100, "inspection_pick_children": ["nobody"]}
        )
        await _approved(coord)
        assert await coord.async_run_inspection_pick() is None

    run(go())


# ── what the child and the feeds see ─────────────────────────────────────


def test_child_view_shows_open_passed_and_nothing_expired():
    async def go():
        coord = await _system()
        child, _chore, completion = await _approved(coord)
        record = await coord.async_start_inspection(completion.id, bonus=10)
        (item,) = coord.inspections_for_child(child.id)
        assert item == {
            "id": record["id"],
            "chore_id": record["chore_id"],
            "status": "open",
            "bonus": 10,
            "until": record["until"],
            "name": "Tidy bedroom",
        }
        coord._celebrate = AsyncMock()
        await coord.async_pass_inspection(record["id"], note="Great")
        (item,) = coord.inspections_for_child(child.id)
        assert item["status"] == "passed" and item["note"] == "Great" and item["bonus"] == 10
        dt_util_mock._now = NOW + dt.timedelta(days=1)
        assert coord.inspections_for_child(child.id) == []

    run(go())


def test_overview_carries_inspections_only_when_there_are_some():
    async def go():
        coord = await _system()
        child, _chore, completion = await _approved(coord)
        coord.data = coord._build_data_snapshot()
        common = sensor_module._compute_common(coord)
        (row,) = sensor_module._build_children_summary(coord, common)
        assert "inspections" not in row
        await coord.async_start_inspection(completion.id)
        (row,) = sensor_module._build_children_summary(coord, common)
        assert row["inspections"][0]["status"] == "open"

    run(go())


def test_activity_feed_lists_inspection_steps_and_the_pass_transaction():
    async def go():
        coord = await _system()
        child, _chore, completion = await _approved(coord)
        record = await coord.async_start_inspection(completion.id)
        coord._celebrate = AsyncMock()
        await coord.async_pass_inspection(record["id"])
        coord.data = coord._build_data_snapshot()
        common = sensor_module._compute_common(coord)
        feed = sensor_module._build_recent_transactions(common, inspections=coord.recent_inspection_events())
        kinds = [(e["type"], e.get("reason", "")) for e in feed]
        assert ("inspection_started", "") in kinds
        assert ("points_added", "Inspection passed: Tidy bedroom") in kinds
        started = next(e for e in feed if e["type"] == "inspection_started")
        assert started["child_name"] == "Vaiha" and started["transaction_id"].endswith("_inspection_started")

    run(go())


def test_a_secret_inspection_stays_out_of_the_feed_until_decided():
    async def go():
        coord = await _system()
        _child, _chore, completion = await _approved(coord)
        record = await coord.async_start_inspection(completion.id, tell_child=False)
        assert coord.recent_inspection_events() == []
        await coord.async_fail_inspection(record["id"], redo=False)
        assert [e["type"] for e in coord.recent_inspection_events()] == ["inspection_started", "inspection_failed"]

    run(go())


def test_removing_a_child_drops_their_inspections():
    async def go():
        coord = await _system()
        child, _chore, completion = await _approved(coord)
        await coord.async_start_inspection(completion.id)
        coord.storage.remove_child(child.id)
        assert coord.storage.get_inspections() == []

    run(go())


def test_old_data_without_the_key_loads_empty():
    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage._data = {}
    assert storage.get_inspections() == []
    assert storage.get_inspection_meta("last_pick") == ""
    storage._data = {"inspections": "garbage"}
    assert storage.get_inspections() == []


def test_redo_ids_ignore_a_completion_from_another_day():
    async def go():
        coord = await _system()
        coord.storage.set_inspections(
            [{"id": "i1", "completion_id": "c1", "status": "redo", "completed_on": "2024-03-19", "chore_id": "x"}]
        )
        assert coord.inspection_redo_completion_ids() == set()
        coord.storage.set_inspections(
            [{"id": "i1", "completion_id": "c1", "status": "redo", "completed_on": "2024-03-20", "chore_id": "x"}]
        )
        assert coord.inspection_redo_completion_ids() == {"c1"}

    run(go())


def test_inspectable_ids_skip_parent_and_bonus_completions():
    async def go():
        coord = await _system()
        _child, chore, completion = await _approved(coord)
        coord.storage.add_completion(
            ChoreCompletion(chore_id=chore.id, child_id="__parent__", completed_at=NOW, approved=True, approved_at=NOW)
        )
        assert coord.inspectable_completion_ids() == [completion.id]

    run(go())


# ── plumbing ─────────────────────────────────────────────────────────────


def test_notification_types():
    started = NOTIFICATION_TYPES_BY_ID["inspection_started"]
    passed = NOTIFICATION_TYPES_BY_ID["inspection_passed"]
    reminder = NOTIFICATION_TYPES_BY_ID["inspection_reminder"]
    assert (started.audience, started.default_enabled) == ("child", False)
    assert (passed.audience, passed.default_enabled) == ("child", False)
    assert (reminder.audience, reminder.default_enabled) == ("parent", True)


def test_settings_keys_are_accepted_and_routed():
    schema = {str(k): v for k, v in ws._UPDATE_SETTINGS_SCHEMA.items()}
    for key in (
        "inspections_enabled",
        "inspection_bonus",
        "inspection_window",
        "inspection_bedtime",
        "inspection_fail_mode",
        "inspection_tell_child",
        "inspection_pick_enabled",
        "inspection_pick_time",
        "inspection_pick_chance",
        "inspection_pick_children",
    ):
        assert key in schema, key
        assert key in ws._SUBKEY_SETTINGS, key


def test_get_state_carries_the_inspections():
    async def go():
        coord = await _system()
        _child, _chore, completion = await _approved(coord)
        coord.hass.data = {}
        with patch.object(ws.photos, "sign_photo_url", side_effect=lambda _h, u: u):
            state = ws._build_state_snapshot(coord)
        assert state["inspectable_completions"] == [completion.id]
        await coord.async_start_inspection(completion.id)
        state = ws._build_state_snapshot(coord)
        assert state["inspections"][0]["can_redo"] is True
        assert state["inspectable_completions"] == []

    run(go())


def test_services_are_described_and_translated():
    services = yaml.safe_load((PKG / "services.yaml").read_text())
    strings = json.loads((PKG / "strings.json").read_text())["services"]
    for name in INSPECTION_SERVICES:
        assert name in services and name in strings
        assert set(services[name]["fields"]) == set(strings[name]["fields"])
    init = (PKG / "__init__.py").read_text()
    assert "INSPECTION_SERVICES" in init and "async_register_inspection_services" in init
