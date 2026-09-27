"""Bounty board: the surfaces around the coordinator (#931).

The lifecycle is covered in test_bounty_board.py. What breaks silently is
everything either side of it: a service nobody declared can't be called, a
sensor field the card needs never arrives, an approval row with no name, a
notification type with no label in the panel.
"""

from __future__ import annotations

import datetime as dt
import json
from datetime import timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol
import yaml

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate import websocket as ws
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coord_notifications import NOTIFICATION_TYPES_BY_ID
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Bounty, Child, ChoreCompletion

from .conftest import dt_util_mock

INTEGRATION = Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
UTC = timezone.utc
NOW = dt.datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC)
SERVICES = ("post_bounty", "update_bounty", "remove_bounty", "claim_bounty", "give_back_bounty", "complete_bounty")


@pytest.fixture(autouse=True)
def _clock():
    saved = dt_util_mock._now
    dt_util_mock._now = NOW
    yield
    dt_util_mock._now = saved


# ── declared service surface ─────────────────────────────────────────────────


def _services():
    return yaml.safe_load((INTEGRATION / "services.yaml").read_text(encoding="utf-8"))


def _strings():
    return json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("service", SERVICES)
def test_service_is_declared_and_documented(service):
    fields = _services()[service]["fields"]
    strings = _strings()["services"][service]
    assert strings["name"] and strings["description"]
    assert set(strings["fields"]) == set(fields)


@pytest.mark.parametrize("service", SERVICES)
def test_service_is_registered_and_unregistered(service):
    source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    const = "SERVICE_" + service.upper()
    assert source.count(f"{const},") >= 3  # import, register, unregister


def test_child_services_apply_the_linked_child_gate():
    # Claiming, giving back and completing act *as* a child, so each handler
    # must run the same linked-child check as complete_chore.
    source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    for handler in ("handle_claim_bounty", "handle_give_back_bounty", "handle_complete_bounty"):
        body = source.split(f"async def {handler}(")[1].split("async def ")[0]
        assert "_async_require_linked_child" in body, handler


def test_parent_services_use_the_parent_gate():
    source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    for handler in ("handle_post_bounty", "handle_update_bounty", "handle_remove_bounty"):
        assert f"_parent({handler})" in source, handler


# ── WebSocket surface (the panel) ────────────────────────────────────────────


def _connection():
    connection = MagicMock()
    connection.user.is_admin = True
    return connection


def _hass_with(coordinator):
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry1": coordinator}}
    return hass


@pytest.mark.asyncio
async def test_ws_post_passes_every_field_through():
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.async_post_bounty = AsyncMock(return_value=Bounty(title="Car", id="b1"))
    coordinator.async_record_audit = AsyncMock()
    connection = _connection()
    msg = {
        "id": 1,
        "type": ws.WS_BOUNTY_POST,
        "title": "Car",
        "points": 50,
        "expires_at": "2026-04-23T18:00:00Z",
        "eligible_child_ids": ["k1"],
        "require_photo": True,
        "notify_children": False,
    }
    await ws._ws_bounty_post(_hass_with(coordinator), connection, msg)
    args, kwargs = coordinator.async_post_bounty.await_args
    assert args == ("Car", 50)
    assert kwargs == {
        "expires_at": "2026-04-23T18:00:00Z",
        "eligible_child_ids": ["k1"],
        "require_photo": True,
        "notify_children": False,
        "claim_hours": 2,
    }
    connection.send_result.assert_called_once_with(1, {"id": "b1"})


@pytest.mark.asyncio
async def test_ws_update_sends_only_what_changed():
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.async_update_bounty = AsyncMock(return_value=Bounty(title="Car", id="b1"))
    coordinator.async_record_audit = AsyncMock()
    msg = {"id": 1, "type": ws.WS_BOUNTY_UPDATE, "bounty_id": "b1", "points": 70}
    await ws._ws_bounty_update(_hass_with(coordinator), _connection(), msg)
    coordinator.async_update_bounty.assert_awaited_once_with("b1", points=70)


@pytest.mark.asyncio
async def test_ws_surfaces_a_refusal_as_an_error():
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.async_remove_bounty = AsyncMock(side_effect=ValueError("Approve or reject it first"))
    connection = _connection()
    await ws._ws_bounty_remove(_hass_with(coordinator), connection, {"id": 1, "bounty_id": "b1"})
    assert connection.send_error.call_args.args[1] == "invalid"


def test_ws_commands_are_registered():
    for handler in (ws._ws_bounty_post, ws._ws_bounty_update, ws._ws_bounty_remove, ws._ws_bounty_release):
        assert handler in ws._COMMANDS


@pytest.mark.parametrize("payload", [{"points": 0}, {"claim_hours": 49}, {"title": ""}])
def test_ws_post_schema_refuses_bad_values(payload):
    schema = vol.Schema(
        {
            vol.Required("title"): vol.All(str, vol.Length(min=1, max=120)),
            vol.Required("points"): vol.All(int, vol.Range(min=1, max=100000)),
            **ws._BOUNTY_EDITABLE,
        }
    )
    with pytest.raises(vol.Invalid):
        schema({"title": "Car", "points": 5, **payload})


def test_state_snapshot_carries_the_bounties():
    coordinator = MagicMock()
    coordinator.storage.data = {"bounties": [Bounty(title="Car", id="b1").to_dict()]}
    coordinator.storage.get_audit_log.return_value = []
    coordinator.storage.get_swap_requests.return_value = []
    coordinator.storage.get_allowance_payouts.return_value = []
    coordinator.get_all_templates.return_value = []
    coordinator.avatar_catalog.return_value = []
    coordinator.mandatory_misses_state.return_value = []
    coordinator.custom_sounds_state.return_value = []
    snapshot = ws._build_state_snapshot(coordinator)
    assert [b["id"] for b in snapshot["bounties"]] == ["b1"]


# ── the sensor the card reads ────────────────────────────────────────────────


def _common(bounties, completions=(), undo_seconds=0):
    return {
        "data": {"bounties": list(bounties)},
        "all_completions": list(completions),
        "chore_undo_seconds": undo_seconds,
    }


def _board(bounties, **kwargs):
    return sensor_module._build_bounties_list(MagicMock(), _common(bounties, **kwargs))


def test_an_open_bounty_is_compact():
    rec = _board([Bounty(title="Car", points=50, id="b1")])[0]
    assert rec == {
        "id": "b1",
        "title": "Car",
        "points": 50,
        "icon": "mdi:flag-outline",
        "status": "open",
        "claim_hours": 2,
    }


def test_a_claimed_bounty_carries_its_lock():
    b = Bounty(
        title="Car",
        id="b1",
        status="claimed",
        claimed_by="k1",
        claimed_at=NOW,
        claim_until=NOW + dt.timedelta(hours=2),
        eligible_child_ids=["k1", "k2"],
        expires_at=NOW + dt.timedelta(days=1),
        require_photo=True,
    )
    rec = _board([b])[0]
    assert rec["claimed_by"] == "k1" and rec["eligible"] == ["k1", "k2"] and rec["require_photo"] is True
    assert rec["claim_until"] == (NOW + dt.timedelta(hours=2)).isoformat()
    assert rec["expires_at"] == (NOW + dt.timedelta(days=1)).isoformat()


def test_a_waiting_bounty_offers_undo_only_inside_the_window():
    comp = ChoreCompletion(
        chore_id="b1", bounty_id="b1", child_id="k1", completed_at=NOW, child_undo_allowed=True, id="c1"
    )
    b = Bounty(title="Car", id="b1", status="pending", claimed_by="k1", completion_id="c1")
    assert _board([b], completions=[comp], undo_seconds=300)[0]["undo"] is True
    assert "undo" not in _board([b], completions=[comp], undo_seconds=0)[0]


def test_expired_and_old_completed_bounties_leave_the_board():
    recent = Bounty(title="New", id="b1", status="completed", claimed_by="k1", closed_at=NOW - dt.timedelta(hours=3))
    old = Bounty(title="Old", id="b2", status="completed", claimed_by="k1", closed_at=NOW - dt.timedelta(hours=25))
    gone = Bounty(title="Gone", id="b3", status="expired", closed_at=NOW)
    assert [r["id"] for r in _board([recent, old, gone])] == ["b1"]


def test_the_board_stays_small():
    bounties = [
        Bounty(
            title=f"A reasonably long bounty title number {i}",
            description="Bucket and sponge are in the garage, rinse it off afterwards",
            points=50,
            id=f"b{i:02d}",
            status="claimed",
            claimed_by="k1",
            claimed_at=NOW,
            claim_until=NOW + dt.timedelta(hours=2),
            expires_at=NOW + dt.timedelta(days=2),
            eligible_child_ids=["k1", "k2", "k3"],
        )
        for i in range(30)
    ]
    assert len(json.dumps(_board(bounties))) < 16384


def test_bounties_sensor_counts_open_bounties():
    coord = MagicMock()
    coord.data = {
        "bounties": [Bounty(title="a", id="1"), Bounty(title="b", id="2", status="claimed"), Bounty(title="c", id="3")]
    }
    sensor = sensor_module.TaskMateBountiesSensor(coord, MagicMock(entry_id="e1"))
    assert sensor.native_value == 2
    assert sensor._attr_unique_id == "e1_bounties"


def _approvals_coordinator(bounty, completion):
    coord = object.__new__(TaskMateCoordinator)
    coord.storage = MagicMock()
    coord.storage.get_chore.return_value = None
    coord.storage.get_bounty.return_value = bounty
    coord.storage.get_child.return_value = Child(name="Malia", id="k1")
    coord.data = {"pending_completions": [completion], "pending_reward_claims": []}
    coord.mandatory_misses_state = MagicMock(return_value=[])
    coord.quality_rating_enabled = MagicMock(return_value=False)
    return coord


def test_pending_approvals_list_the_bounty_by_name():
    bounty = Bounty(title="Wash the car", points=50, id="b1", status="pending")
    comp = ChoreCompletion(chore_id="b1", bounty_id="b1", child_id="k1", completed_at=NOW, submitted_points=50, id="c1")
    sensor = sensor_module.PendingApprovalsSensor(_approvals_coordinator(bounty, comp), MagicMock(entry_id="e1"))
    detail = sensor.extra_state_attributes["chore_completions"][0]
    assert (detail["chore_name"], detail["points"], detail["bounty_id"]) == ("Wash the car", 50, "b1")


def test_activity_names_a_bounty_completion():
    bounty = Bounty(title="Wash the car", points=50, id="b1")
    comp = ChoreCompletion(chore_id="b1", bounty_id="b1", child_id="k1", completed_at=NOW, approved=True, id="c1")
    common = {
        "child_lookup": {"k1": Child(name="Malia", id="k1")},
        "chore_lookup": {},
        "bounty_lookup": {"b1": bounty},
        "all_completions": [comp],
        "chore_undo_seconds": 0,
    }
    assert sensor_module._build_recent_completions(common)[0]["chore_name"] == "Wash the car"
    assert sensor_module._build_todays_completions(common)[0]["chore_name"] == "Wash the car"


# ── notifications, card and panel wiring ─────────────────────────────────────


@pytest.mark.parametrize("type_id", ["bounty_posted", "bounty_claim_lapsing"])
def test_notification_types_are_opt_in_child_types_with_labels(type_id):
    meta = NOTIFICATION_TYPES_BY_ID[type_id]
    assert meta.audience == "child" and meta.default_enabled is False
    locales = INTEGRATION / "www" / "locales"
    for path in locales.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data[f"notification.{type_id}.name"] and data[f"notification.{type_id}.description"], path.name


def test_the_card_is_registered_as_a_lovelace_resource():
    # frontend.py is stubbed under test, so read the list from its source.
    assert '"taskmate-bounty-card.js",' in (INTEGRATION / "frontend.py").read_text(encoding="utf-8")
    assert (INTEGRATION / "www" / "taskmate-bounty-card.js").is_file()


def test_the_resolver_merges_the_bounties_sensor():
    source = (INTEGRATION / "www" / "taskmate-attr-resolver.js").read_text(encoding="utf-8")
    assert '"sensor.taskmate_bounties"' in source
