"""Teamwork chores: the surfaces around the coordinator (#928).

The join/complete/leave behaviour is covered in test_teamwork_chores.py. What
breaks silently is everything either side of it — a field the WebSocket schema
drops never reaches the chore, a field missing from the sensor slice is
invisible to the card, and a service nobody declared can't be called.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol
import yaml

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate import websocket as ws
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Chore

INTEGRATION = Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
TEAM_FIELDS = ("team_size", "team_points_mode", "team_bonus")


# ── WebSocket surface ────────────────────────────────────────────────────────


@pytest.mark.parametrize("field", TEAM_FIELDS)
def test_team_fields_are_editable_over_the_websocket(field):
    assert field in ws._CHORE_EDITABLE_FIELDS


def test_team_fields_pass_the_payload_schema():
    schema = vol.Schema(ws._chore_payload_schema(require_name=False))
    out = schema({"team_size": 3, "team_points_mode": "split", "team_bonus": 2})
    assert out == {"team_size": 3, "team_points_mode": "split", "team_bonus": 2}


@pytest.mark.parametrize(
    "payload",
    [{"team_size": -1}, {"team_size": 11}, {"team_points_mode": "most"}, {"team_bonus": -3}],
)
def test_bad_team_values_fail_the_payload_schema(payload):
    schema = vol.Schema(ws._chore_payload_schema(require_name=False))
    with pytest.raises(vol.Invalid):
        schema(payload)


def _connection():
    connection = MagicMock()
    connection.user.is_admin = True
    return connection


def _hass_with(coordinator):
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry1": coordinator}}
    return hass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extra",
    [{"assignment_mode": "first_come"}, {"open_ended": True}, {"assignment_mode": "alternating"}],
)
async def test_ws_add_refuses_a_bad_team_before_creating_anything(extra):
    # The add handler creates the chore and then updates it with the rest of
    # the fields — so the refusal has to come first, or an ordinary chore is
    # left behind by a save the parent was told failed.
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.async_add_chore = AsyncMock()
    coordinator.async_record_audit = AsyncMock()
    connection = _connection()
    msg = {"id": 1, "type": ws.WS_ADD_CHORE, "name": "Wash the car", "team_size": 2, **extra}
    await ws._ws_add_chore(_hass_with(coordinator), connection, msg)
    coordinator.async_add_chore.assert_not_awaited()
    assert connection.send_error.call_args.args[1] == "invalid"


# ── declared service surface ─────────────────────────────────────────────────


def _services():
    return yaml.safe_load((INTEGRATION / "services.yaml").read_text(encoding="utf-8"))


def _strings():
    return json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("field", TEAM_FIELDS)
def test_add_chore_service_declares_the_team_fields(field):
    assert field in _services()["add_chore"]["fields"]
    entry = _strings()["services"]["add_chore"]["fields"][field]
    assert entry["name"] and entry["description"]


def test_leave_team_chore_service_is_declared_and_documented():
    fields = _services()["leave_team_chore"]["fields"]
    assert fields["chore_id"]["required"] and fields["child_id"]["required"]
    strings = _strings()["services"]["leave_team_chore"]
    assert strings["name"] and set(strings["fields"]) == {"chore_id", "child_id"}


def test_leave_team_chore_is_registered_and_unregistered():
    # A declared service that is never registered is a dead entry in the UI,
    # and one that isn't unregistered survives an entry reload.
    source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    assert source.count("SERVICE_LEAVE_TEAM_CHORE,") >= 3  # import, register, unregister


# ── the data the card reads ──────────────────────────────────────────────────


def _chores_coordinator(joined=()):
    coordinator = object.__new__(TaskMateCoordinator)
    coordinator.effective_chore_points = MagicMock(side_effect=lambda ch: ch.points)
    coordinator.team_joined_ids = MagicMock(return_value=list(joined))
    return coordinator


def _record(chore, joined=()):
    return sensor_module._build_chores_list(_chores_coordinator(joined), {"chores": [chore]})[0]


def test_chores_slice_carries_the_team():
    record = _record(Chore(name="Car", points=10, team_size=3, id="a"), joined=["k1"])
    assert record["team"] == {"size": 3, "joined": ["k1"]}


def test_chores_slice_flags_a_split_team_and_quotes_the_share():
    record = _record(Chore(name="Car", points=10, team_size=3, team_points_mode="split", team_bonus=1, id="a"))
    assert record["team"] == {"size": 3, "split": True}
    # What each child earns — the figure the card shows as "+N".
    assert record["effective_points"] == 4


def test_chores_slice_omits_the_team_on_an_ordinary_chore():
    record = _record(Chore(name="Dishes", points=10, id="a"))
    assert "team" not in record
    assert "effective_points" not in record


def test_chores_slice_omits_an_invalid_team():
    # A first-come "team" behaves as an ordinary chore, so the card mustn't
    # offer a Join button for it.
    record = _record(Chore(name="Car", points=10, team_size=2, assignment_mode="first_come", id="a"))
    assert "team" not in record
