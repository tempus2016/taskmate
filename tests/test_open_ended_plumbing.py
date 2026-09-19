"""The service / WebSocket surface for open-ended chores (#832).

The coordinator changes are covered in test_open_ended_chores.py and
test_approve_points_override.py. What breaks silently is the *declared*
surface: a field the coordinator accepts but the service schema drops never
reaches it, and an undocumented field is invisible in the HA service UI.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from custom_components.taskmate import websocket as ws
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator

INTEGRATION = Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"


def _services():
    return yaml.safe_load((INTEGRATION / "services.yaml").read_text(encoding="utf-8"))


def _strings():
    return json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))


# ── declared service surface ─────────────────────────────────────────────────


def test_approve_chore_service_accepts_a_points_override():
    fields = _services()["approve_chore"]["fields"]
    assert "points" in fields
    assert fields["points"].get("required") is not True


def test_complete_chore_service_accepts_a_note_and_a_suggestion():
    fields = _services()["complete_chore"]["fields"]
    assert "note" in fields
    assert "suggested_points" in fields


@pytest.mark.parametrize(
    ("service", "field"),
    [
        ("approve_chore", "points"),
        ("complete_chore", "note"),
        ("complete_chore", "suggested_points"),
    ],
)
def test_new_service_fields_are_documented(service, field):
    entry = _strings()["services"][service]["fields"].get(field)
    assert entry, f"{service}.{field} missing from strings.json"
    assert entry.get("name") and entry.get("description")


# ── websocket forwarding ─────────────────────────────────────────────────────


def _connection():
    connection = MagicMock()
    connection.user.is_admin = True
    return connection


def _hass_with(coordinator):
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry1": coordinator}}
    return hass


def _coordinator():
    # spec'd so _get_coordinator's isinstance check finds it in hass.data.
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.async_approve_chore = AsyncMock()
    coordinator.async_record_audit = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_ws_approve_forwards_the_points_override():
    coordinator = _coordinator()
    connection = _connection()
    await ws._ws_approve_chore(
        _hass_with(coordinator), connection, {"id": 1, "type": ws.WS_APPROVE_CHORE, "completion_id": "x1", "points": 25}
    )
    coordinator.async_approve_chore.assert_awaited_once_with("x1", points=25)
    connection.send_error.assert_not_called()


@pytest.mark.asyncio
async def test_ws_approve_without_an_override_leaves_the_chores_points_alone():
    coordinator = _coordinator()
    await ws._ws_approve_chore(
        _hass_with(coordinator), _connection(), {"id": 1, "type": ws.WS_APPROVE_CHORE, "completion_id": "x1"}
    )
    coordinator.async_approve_chore.assert_awaited_once_with("x1", points=None)


# ── the data cards actually read ─────────────────────────────────────────────


def _chores_coordinator():
    coordinator = MagicMock()
    coordinator.effective_chore_points = MagicMock(side_effect=lambda ch: ch.points)
    return coordinator


def test_chores_sensor_carries_the_open_ended_flag():
    from custom_components.taskmate.models import Chore
    from custom_components.taskmate.sensor import _build_chores_list

    chore = Chore(name="Something extra", points=0, open_ended=True, id="ch1")
    assert _build_chores_list(_chores_coordinator(), {"chores": [chore]})[0]["open_ended"] is True


def test_ordinary_chore_omits_the_open_ended_flag():
    from custom_components.taskmate.models import Chore
    from custom_components.taskmate.sensor import _build_chores_list

    chore = Chore(name="Dishes", points=5, id="ch1")
    assert "open_ended" not in _build_chores_list(_chores_coordinator(), {"chores": [chore]})[0]


def _pending_detail(comp):
    from custom_components.taskmate.models import Child, Chore
    from custom_components.taskmate.sensor import PendingApprovalsSensor

    child = Child(name="Mia", id="c1")
    chore = Chore(name="Something extra", points=0, open_ended=True, id="ch1")
    coordinator = MagicMock()
    coordinator.data = {"pending_completions": [comp], "pending_reward_claims": []}
    coordinator.get_child = lambda cid: child if cid == "c1" else None
    coordinator.get_chore = lambda cid: chore if cid == "ch1" else None
    coordinator.get_reward = lambda rid: None
    entry = MagicMock()
    entry.entry_id = "entry1"
    return PendingApprovalsSensor(coordinator, entry).extra_state_attributes["chore_completions"][0]


def _completion(**kwargs):
    import datetime as dt

    from custom_components.taskmate.models import ChoreCompletion

    return ChoreCompletion(
        chore_id="ch1",
        child_id="c1",
        completed_at=dt.datetime(2026, 9, 18, 9, 0, 0, tzinfo=dt.timezone.utc),
        approved=False,
        id="comp1",
        **kwargs,
    )


def test_approvals_queue_shows_the_note_and_the_suggestion(hass):
    detail = _pending_detail(_completion(note="Tidied the porch", suggested_points=15))
    assert detail["note"] == "Tidied the porch"
    assert detail["suggested_points"] == 15


def test_approvals_queue_omits_both_when_the_child_said_nothing(hass):
    detail = _pending_detail(_completion())
    assert "note" not in detail
    assert "suggested_points" not in detail


# ── the panel's editing surface ──────────────────────────────────────────────


def test_panel_may_set_open_ended_on_a_chore():
    assert "open_ended" in ws._CHORE_EDITABLE_FIELDS


def test_chore_payload_schema_accepts_open_ended():
    schema = ws._chore_payload_schema(require_name=False)
    assert "open_ended" in {str(k) for k in schema}
