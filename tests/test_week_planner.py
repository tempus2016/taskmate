"""Week planner (admin panel): rotation picks for a week and saving a planned week.

What matters here: every change goes through ``async_update_chore`` with no
refresh per chore and one refresh at the end; a refused change touches
nothing while the others still land; and the commands are admin-only.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol

from custom_components.taskmate import websocket_planner as wp
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore
from custom_components.taskmate.storage import TaskMateStorage

from .conftest import dt_util_mock

UTC = dt.timezone.utc
# 2026-06-22 is a Monday.
MON = dt.date(2026, 6, 22)
TUE = dt.date(2026, 6, 23)
WED = dt.date(2026, 6, 24)
THU = dt.date(2026, 6, 25)


@pytest.fixture(autouse=True)
def _clock():
    saved = dt_util_mock._now
    dt_util_mock._now = dt.datetime.combine(TUE, dt.time(9, 0), tzinfo=UTC)
    yield
    dt_util_mock._now = saved


async def _coord(hass, chores=()):
    storage = TaskMateStorage(hass, "planner")
    await storage.async_load()
    storage.add_child(Child(name="Malia", id="malia"))
    storage.add_child(Child(name="Vaiha", id="vaiha"))
    for chore in chores:
        storage.add_chore(chore)
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.storage = storage
    coord.data = {}
    coord.async_refresh = AsyncMock()
    storage.async_save = AsyncMock()
    return coord


def _ws_env(coord, admin=True):
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry": coord}}
    conn = MagicMock()
    conn.user = SimpleNamespace(is_admin=admin, id="u1", name="Parent")
    coord.async_record_audit = AsyncMock()
    return hass, conn


# ── Saving a planned week ────────────────────────────────────────────────────


async def test_a_batch_saves_every_chore_with_one_refresh(hass):
    walk = Chore(name="Walk dog", id="walk", due_days=["tuesday"])
    bins = Chore(name="Bins out", id="bins", due_days=["monday"], assigned_to=["vaiha"])
    gift = Chore(name="Wrap gift", id="gift", schedule_mode="one_shot", created_date=THU.isoformat())
    coord = await _coord(hass, [walk, bins, gift])
    result = await coord.async_apply_week_plan(
        [
            {"chore_id": "walk", "due_days": ["wednesday", "tuesday"]},
            {"chore_id": "bins", "assigned_to": ["malia"]},
            {"chore_id": "gift", "created_date": WED.isoformat()},
        ]
    )
    assert result["applied"] == 3
    assert all(r["ok"] for r in result["results"])
    # Kept in week order, whatever order the panel sent.
    assert coord.storage.get_chore("walk").due_days == ["tuesday", "wednesday"]
    assert coord.storage.get_chore("bins").assigned_to == ["malia"]
    assert coord.storage.get_chore("gift").created_date == WED.isoformat()
    coord.async_refresh.assert_awaited_once()
    coord.storage.async_save.assert_awaited_once()


async def test_a_refused_change_touches_nothing_and_the_rest_still_apply(hass):
    walk = Chore(name="Walk dog", id="walk", due_days=["tuesday"])
    turn = Chore(
        name="Dishes", id="turn", due_days=["monday"], assignment_mode="alternating", assigned_to=["malia", "vaiha"]
    )
    coord = await _coord(hass, [walk, turn])
    result = await coord.async_apply_week_plan(
        [
            # A rotation chore keeps its rotation — and its day change with it.
            {"chore_id": "turn", "due_days": ["friday"], "assigned_to": ["malia"]},
            {"chore_id": "walk", "due_days": ["thursday"]},
            {"chore_id": "gone", "due_days": ["thursday"]},
        ]
    )
    by_id = {r["chore_id"]: r for r in result["results"]}
    assert by_id["turn"]["ok"] is False and by_id["turn"]["code"] == "rotation"
    assert by_id["gone"]["code"] == "not_found"
    assert by_id["walk"]["ok"] is True
    assert coord.storage.get_chore("turn").due_days == ["monday"]
    assert coord.storage.get_chore("turn").assigned_to == ["malia", "vaiha"]
    assert coord.storage.get_chore("walk").due_days == ["thursday"]
    assert result["applied"] == 1
    coord.async_refresh.assert_awaited_once()


async def test_nothing_applied_means_no_refresh(hass):
    coord = await _coord(hass, [Chore(name="Daily", id="daily", due_days=[])])
    result = await coord.async_apply_week_plan([{"chore_id": "daily", "created_date": WED.isoformat()}])
    assert result["results"][0]["code"] == "wrong_schedule"
    coord.async_refresh.assert_not_awaited()
    coord.storage.async_save.assert_not_awaited()


async def test_days_never_empty_into_every_day(hass):
    coord = await _coord(hass, [Chore(name="Walk", id="walk", due_days=["monday"])])
    result = await coord.async_apply_week_plan([{"chore_id": "walk", "due_days": []}])
    assert result["results"][0]["code"] == "empty_days"
    assert coord.storage.get_chore("walk").due_days == ["monday"]


async def test_a_one_off_cannot_go_into_the_past(hass):
    gift = Chore(name="Gift", id="gift", schedule_mode="one_shot", created_date=THU.isoformat())
    coord = await _coord(hass, [gift])
    result = await coord.async_apply_week_plan([{"chore_id": "gift", "created_date": MON.isoformat()}])
    assert result["results"][0]["code"] == "past_date"
    assert coord.storage.get_chore("gift").created_date == THU.isoformat()


async def test_moving_a_finished_one_off_gives_it_a_fresh_run(hass):
    # Done and approved today, so switched off for Malia; moved to Thursday it
    # must come back on, the same as a date change in the chore editor.
    gift = Chore(
        name="Gift",
        id="gift",
        schedule_mode="one_shot",
        created_date=TUE.isoformat(),
        assigned_to=["malia"],
        enabled=False,
        disabled_for=["malia"],
    )
    coord = await _coord(hass, [gift])
    result = await coord.async_apply_week_plan([{"chore_id": "gift", "created_date": THU.isoformat()}])
    assert result["applied"] == 1
    saved = coord.storage.get_chore("gift")
    assert saved.created_date == THU.isoformat()
    assert saved.enabled is True
    assert saved.disabled_for == []


async def test_a_one_off_kept_on_its_day_stays_finished(hass):
    gift = Chore(
        name="Gift",
        id="gift",
        schedule_mode="one_shot",
        created_date=THU.isoformat(),
        enabled=False,
        disabled_for=["malia"],
    )
    coord = await _coord(hass, [gift])
    await coord.async_apply_week_plan([{"chore_id": "gift", "created_date": THU.isoformat(), "assigned_to": ["vaiha"]}])
    saved = coord.storage.get_chore("gift")
    assert saved.enabled is False
    assert saved.disabled_for == ["malia"]


async def test_this_week_only_uses_the_calendar_move(hass):
    plants = Chore(
        name="Water plants",
        id="plants",
        schedule_mode="recurring",
        recurrence="every_3_days",
        recurrence_start=WED.isoformat(),
    )
    coord = await _coord(hass, [plants])
    result = await coord.async_apply_week_plan(
        [{"chore_id": "plants", "moves": [{"origin": WED.isoformat(), "date": THU.isoformat()}]}]
    )
    assert result["results"][0]["ok"] is True
    stored = coord.storage.get_chore("plants")
    assert stored.moved_occurrences == {WED.isoformat(): THU.isoformat()}
    assert coord._is_chore_scheduled_for_date(stored, THU)
    assert not coord._is_chore_scheduled_for_date(stored, WED)


async def test_this_week_only_refuses_the_past_and_an_occupied_day(hass):
    daily = Chore(
        name="Bed", id="bed", schedule_mode="recurring", recurrence="every_2_days", recurrence_start=MON.isoformat()
    )
    coord = await _coord(hass, [daily])
    result = await coord.async_apply_week_plan(
        [
            {"chore_id": "bed", "moves": [{"origin": MON.isoformat(), "date": TUE.isoformat()}]},
        ]
    )
    assert result["results"][0]["code"] == "past_date"
    result = await coord.async_apply_week_plan(
        [{"chore_id": "bed", "moves": [{"origin": WED.isoformat(), "date": dt.date(2026, 6, 26).isoformat()}]}]
    )
    assert result["results"][0]["code"] == "already_scheduled"
    assert coord.storage.get_chore("bed").moved_occurrences == {}


async def test_a_series_moves_by_its_day_and_start(hass):
    weekly = Chore(name="Hoover", id="hoover", schedule_mode="recurring", recurrence="weekly", recurrence_day="tuesday")
    coord = await _coord(hass, [weekly])
    result = await coord.async_apply_week_plan(
        [{"chore_id": "hoover", "recurrence_day": "wednesday", "recurrence_start": ""}]
    )
    assert result["results"][0]["ok"] is True
    stored = coord.storage.get_chore("hoover")
    assert stored.recurrence_day == "wednesday"
    assert coord._is_chore_scheduled_for_date(stored, WED)
    # Series fields belong to repeating chores only.
    coord2 = await _coord(hass, [Chore(name="Walk", id="walk", due_days=["monday"])])
    result = await coord2.async_apply_week_plan([{"chore_id": "walk", "recurrence_day": "friday"}])
    assert result["results"][0]["code"] == "wrong_schedule"


async def test_reassign_refuses_an_unknown_child(hass):
    coord = await _coord(hass, [Chore(name="Walk", id="walk", due_days=["monday"])])
    result = await coord.async_apply_week_plan([{"chore_id": "walk", "assigned_to": ["nobody"]}])
    assert result["results"][0]["code"] == "unknown_child"
    assert coord.storage.get_chore("walk").assigned_to == []


async def test_update_chore_without_refresh_skips_save_and_refresh(hass):
    coord = await _coord(hass, [Chore(name="Walk", id="walk", due_days=["monday"])])
    chore = coord.storage.get_chore("walk")
    chore.due_days = ["friday"]
    await coord.async_update_chore(chore, refresh=False)
    assert coord.storage.get_chore("walk").due_days == ["friday"]
    coord.async_refresh.assert_not_awaited()
    await coord.async_update_chore(chore)
    coord.async_refresh.assert_awaited_once()


# ── Rotation picks ───────────────────────────────────────────────────────────


async def test_week_plan_gives_seven_days_from_monday_with_rotation_picks(hass):
    turn = Chore(
        name="Dishes",
        id="turn",
        due_days=[],
        assignment_mode="alternating",
        assigned_to=["malia", "vaiha"],
        assignment_rotation_anchor=MON.isoformat(),
    )
    everyone = Chore(name="Bed", id="bed", due_days=[])
    coord = await _coord(hass, [turn, everyone])
    plan = coord.week_plan(THU)
    assert plan["start"] == MON.isoformat()
    assert plan["today"] == TUE.isoformat()
    assert [d["date"] for d in plan["days"]][0] == MON.isoformat() and len(plan["days"]) == 7
    picks = [d["picks"].get("turn") for d in plan["days"]]
    assert set(picks) == {"malia", "vaiha"}
    # Alternating: consecutive days differ.
    assert picks[0] != picks[1]
    assert all("bed" not in d["picks"] for d in plan["days"])


# ── WebSocket commands ───────────────────────────────────────────────────────


async def test_apply_command_reports_per_chore(hass):
    coord = await _coord(hass, [Chore(name="Walk", id="walk", due_days=["monday"])])
    ws_hass, conn = _ws_env(coord)
    msg = {"id": 1, "type": wp.WS_PLANNER_APPLY, "changes": [{"chore_id": "walk", "due_days": ["friday"]}]}
    await wp.ws_planner_apply(ws_hass, conn, msg)
    sent = conn.send_result.call_args.args[1]
    assert sent["applied"] == 1 and sent["results"] == [{"chore_id": "walk", "ok": True}]


async def test_both_commands_are_admin_only(hass):
    coord = await _coord(hass, [Chore(name="Walk", id="walk", due_days=["monday"])])
    ws_hass, conn = _ws_env(coord, admin=False)
    await wp.ws_planner_apply(
        ws_hass, conn, {"id": 2, "type": wp.WS_PLANNER_APPLY, "changes": [{"chore_id": "walk", "due_days": ["friday"]}]}
    )
    await wp.ws_planner_week(ws_hass, conn, {"id": 3, "type": wp.WS_PLANNER_WEEK})
    assert conn.send_error.call_count == 2
    conn.send_result.assert_not_called()
    assert coord.storage.get_chore("walk").due_days == ["monday"]


async def test_week_command_sends_the_plan(hass):
    coord = await _coord(hass)
    ws_hass, conn = _ws_env(coord)
    await wp.ws_planner_week(ws_hass, conn, {"id": 4, "type": wp.WS_PLANNER_WEEK, "week_start": "2026-06-24"})
    assert conn.send_result.call_args.args[1]["start"] == MON.isoformat()


def test_change_schema_rejects_bad_input():
    schema = wp._CHANGE_SCHEMA
    assert schema({"chore_id": "a", "due_days": ["monday"]})["due_days"] == ["monday"]
    assert schema({"chore_id": "a", "recurrence_day": ""})["recurrence_day"] == ""
    for bad in (
        {"chore_id": "a", "due_days": ["funday"]},
        {"chore_id": "a", "created_date": "tomorrow"},
        {"chore_id": "a", "moves": [{"origin": "2026-06-22"}]},
        {"chore_id": "a", "status": "done"},
        {"due_days": ["monday"]},
    ):
        with pytest.raises(vol.Invalid):
            schema(bad)


def test_commands_are_registered_and_the_read_is_not_audited():
    from custom_components.taskmate import websocket as ws

    assert "taskmate/planner/week" in ws._AUDIT_EXCLUDE
    assert wp.ws_planner_apply in wp.PLANNER_COMMANDS and wp.ws_planner_week in wp.PLANNER_COMMANDS
