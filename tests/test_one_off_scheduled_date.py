"""A one-off chore can be set for a day ahead from the chore editor (#1169).

A one-off is only on the board on its ``created_date`` and is switched off the
night after. The calendar could already set that date, but the panel's add and
edit messages never carried it, so a one-off made in the editor was always for
today. The websocket now takes ``created_date`` and works out the day in one
place (``_one_off_date``) for both add and edit.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol

from custom_components.taskmate import websocket as ws
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Chore

from .conftest import dt_util_mock

# 2026-11-06 is a Friday; the parent plans Saturday's job the night before.
FRI = dt.date(2026, 11, 6)
SAT = "2026-11-07"
THU = "2026-11-05"

PANEL = Path(__file__).resolve().parents[1] / "custom_components" / "taskmate" / "www" / "taskmate-panel.js"


@pytest.fixture(autouse=True)
def _clock():
    saved = dt_util_mock._now
    dt_util_mock._now = dt.datetime.combine(FRI, dt.time(18, 0), tzinfo=dt.timezone.utc)
    yield
    dt_util_mock._now = saved


def _one_off(created_date: str) -> Chore:
    return Chore(name="Tidy the garden", id="c1", schedule_mode="one_shot", created_date=created_date)


# ── working out the day ──────────────────────────────────────────────────────


def test_new_one_off_takes_the_chosen_day():
    assert ws._one_off_date({"schedule_mode": "one_shot", "created_date": SAT}) == SAT


def test_new_one_off_without_a_date_is_for_today():
    assert ws._one_off_date({"schedule_mode": "one_shot"}) == FRI.isoformat()
    assert ws._one_off_date({"schedule_mode": "one_shot", "created_date": ""}) == FRI.isoformat()


def test_new_one_off_for_a_day_gone_is_refused():
    with pytest.raises(ValueError):
        ws._one_off_date({"schedule_mode": "one_shot", "created_date": THU})


def test_not_a_one_off_leaves_the_date_alone():
    assert ws._one_off_date({"schedule_mode": "specific_days", "created_date": SAT}) is None
    assert ws._one_off_date({}, Chore(name="Bins", schedule_mode="recurring")) is None


def test_editing_moves_the_day():
    assert ws._one_off_date({"created_date": SAT}, _one_off(FRI.isoformat())) == SAT


def test_editing_without_a_date_keeps_the_day():
    assert ws._one_off_date({"name": "Tidy up"}, _one_off(SAT)) == SAT


def test_an_older_one_off_still_saves_with_its_own_date():
    # The editor sends back the date it was given; a chore from a past day
    # must not become unsaveable just because that day has gone.
    assert ws._one_off_date({"created_date": THU}, _one_off(THU)) == THU


def test_editing_onto_a_day_gone_is_refused():
    with pytest.raises(ValueError):
        ws._one_off_date({"created_date": THU}, _one_off(SAT))


def test_switching_to_one_off_starts_today_not_on_a_stale_date():
    # A weekly chore switched to one-off used to keep an empty date and stay
    # on the board every day, never switched off.
    weekly = Chore(name="Bins", schedule_mode="specific_days", created_date="")
    assert ws._one_off_date({"schedule_mode": "one_shot"}, weekly) == FRI.isoformat()
    leftover = Chore(name="Bins", schedule_mode="specific_days", created_date=THU)
    assert ws._one_off_date({"schedule_mode": "one_shot"}, leftover) == FRI.isoformat()


def test_switching_to_one_off_can_pick_a_day_ahead():
    weekly = Chore(name="Bins", schedule_mode="specific_days")
    assert ws._one_off_date({"schedule_mode": "one_shot", "created_date": SAT}, weekly) == SAT


# ── the payload schema ───────────────────────────────────────────────────────


def test_schema_accepts_a_date_or_blank():
    schema = vol.Schema(ws._chore_payload_schema(require_name=False))
    assert schema({"created_date": SAT})["created_date"] == SAT
    assert schema({"created_date": ""})["created_date"] == ""


@pytest.mark.parametrize("bad", ["Saturday", "2026-13-01", "07/11/2026"])
def test_schema_refuses_a_bad_date(bad):
    schema = vol.Schema(ws._chore_payload_schema(require_name=False))
    with pytest.raises(vol.Invalid):
        schema({"created_date": bad})


# ── the websocket handlers ───────────────────────────────────────────────────


def _connection():
    connection = MagicMock()
    connection.user.is_admin = True
    return connection


def _hass_with(coordinator):
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry1": coordinator}}
    return hass


@pytest.mark.asyncio
async def test_ws_add_passes_the_day_to_the_coordinator():
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.async_add_chore = AsyncMock(return_value=_one_off(SAT))
    coordinator.async_update_chore = AsyncMock()
    connection = _connection()
    msg = {
        "id": 1,
        "type": ws.WS_ADD_CHORE,
        "name": "Tidy the garden",
        "schedule_mode": "one_shot",
        "created_date": SAT,
    }
    await ws._ws_add_chore(_hass_with(coordinator), connection, msg)
    assert coordinator.async_add_chore.call_args.kwargs["created_date"] == SAT
    connection.send_result.assert_called_once()


@pytest.mark.asyncio
async def test_ws_add_refuses_a_day_gone_before_creating_anything():
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.async_add_chore = AsyncMock()
    coordinator.async_record_audit = AsyncMock()
    connection = _connection()
    msg = {
        "id": 1,
        "type": ws.WS_ADD_CHORE,
        "name": "Tidy the garden",
        "schedule_mode": "one_shot",
        "created_date": THU,
    }
    await ws._ws_add_chore(_hass_with(coordinator), connection, msg)
    coordinator.async_add_chore.assert_not_awaited()
    assert connection.send_error.call_args.args[1] == "invalid"


@pytest.mark.asyncio
async def test_ws_update_moves_the_day():
    chore = _one_off(FRI.isoformat())
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.storage = MagicMock()
    coordinator.storage.get_chore.return_value = chore
    coordinator.async_update_chore = AsyncMock()
    connection = _connection()
    msg = {"id": 1, "type": ws.WS_UPDATE_CHORE, "chore_id": "c1", "created_date": SAT}
    await ws._ws_update_chore(_hass_with(coordinator), connection, msg)
    assert coordinator.async_update_chore.call_args.args[0].created_date == SAT


@pytest.mark.asyncio
async def test_ws_update_refused_day_changes_nothing():
    chore = _one_off(SAT)
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.storage = MagicMock()
    coordinator.storage.get_chore.return_value = chore
    coordinator.async_update_chore = AsyncMock()
    coordinator.async_record_audit = AsyncMock()
    connection = _connection()
    msg = {"id": 1, "type": ws.WS_UPDATE_CHORE, "chore_id": "c1", "name": "Renamed", "created_date": THU}
    await ws._ws_update_chore(_hass_with(coordinator), connection, msg)
    coordinator.async_update_chore.assert_not_awaited()
    assert chore.name == "Tidy the garden"
    assert chore.created_date == SAT
    assert connection.send_error.call_args.args[1] == "invalid"


@pytest.mark.asyncio
async def test_ws_update_switching_to_one_off_dates_it_today():
    chore = Chore(name="Bins", id="c1", schedule_mode="specific_days")
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.storage = MagicMock()
    coordinator.storage.get_chore.return_value = chore
    coordinator.async_update_chore = AsyncMock()
    msg = {"id": 1, "type": ws.WS_UPDATE_CHORE, "chore_id": "c1", "schedule_mode": "one_shot"}
    await ws._ws_update_chore(_hass_with(coordinator), _connection(), msg)
    saved = coordinator.async_update_chore.call_args.args[0]
    assert saved.schedule_mode == "one_shot"
    assert saved.created_date == FRI.isoformat()


# ── the panel ────────────────────────────────────────────────────────────────


def test_panel_sends_the_one_off_day():
    source = PANEL.read_text(encoding="utf-8")
    assert 'created_date: d.schedule_mode === "one_shot"' in source
    assert '"created_date"' in source  # the editor's date field
    assert "panel.chore_one_off_date_label" in source


@pytest.mark.asyncio
async def test_ws_update_moving_the_day_is_a_fresh_run():
    # Last week's one-off, done by Alex and then switched off overnight, is
    # planned again for Saturday: it must be back on, and Alex not done.
    chore = _one_off(THU)
    chore.enabled = False
    chore.disabled_for = ["alex"]
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.storage = MagicMock()
    coordinator.storage.get_chore.return_value = chore
    coordinator.async_update_chore = AsyncMock()
    msg = {"id": 1, "type": ws.WS_UPDATE_CHORE, "chore_id": "c1", "enabled": False, "created_date": SAT}
    await ws._ws_update_chore(_hass_with(coordinator), _connection(), msg)
    saved = coordinator.async_update_chore.call_args.args[0]
    assert saved.created_date == SAT
    assert saved.enabled is True
    assert saved.disabled_for == []


@pytest.mark.asyncio
async def test_ws_update_keeping_the_day_leaves_the_run_alone():
    chore = _one_off(SAT)
    chore.disabled_for = ["alex"]
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.storage = MagicMock()
    coordinator.storage.get_chore.return_value = chore
    coordinator.async_update_chore = AsyncMock()
    msg = {"id": 1, "type": ws.WS_UPDATE_CHORE, "chore_id": "c1", "enabled": False, "created_date": SAT}
    await ws._ws_update_chore(_hass_with(coordinator), _connection(), msg)
    saved = coordinator.async_update_chore.call_args.args[0]
    assert saved.enabled is False
    assert saved.disabled_for == ["alex"]
