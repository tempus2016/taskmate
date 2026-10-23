"""Set times: the surfaces around the coordinator.

The per-time rules are covered in test_set_times.py. What breaks silently is
everything either side of them — a field the WebSocket schema drops never
reaches the chore, a refused edit that was already half-written onto the stored
record, a service field nobody declared, a setting the panel can't save, and a
card that ticks the chore without naming the time.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol
import yaml

from custom_components.taskmate import websocket as ws
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Chore, ChoreTime

INTEGRATION = Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
WWW = INTEGRATION / "www"
LOCALES = WWW / "locales"


def _read(name: str) -> str:
    return (WWW / name).read_text(encoding="utf-8")


# ── WebSocket surface ────────────────────────────────────────────────────────


@pytest.mark.parametrize("field", ["times", "times_bonus"])
def test_set_time_fields_are_editable_over_the_websocket(field):
    assert field in ws._CHORE_EDITABLE_FIELDS


def test_set_times_pass_the_payload_schema():
    schema = vol.Schema(ws._chore_payload_schema(require_name=False))
    out = schema({"times": [{"name": "Lunch", "start": "12:00", "end": "13:00", "points": 1}], "times_bonus": 2})
    assert out["times"][0]["start"] == "12:00" and out["times_bonus"] == 2


@pytest.mark.parametrize(
    "payload",
    [{"times": [{"name": "x"}]}, {"times": [{"start": "1", "end": "2", "points": -1}]}, {"times_bonus": -1}],
)
def test_bad_set_time_values_fail_the_payload_schema(payload):
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
async def test_ws_add_refuses_bad_times_before_creating_anything():
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.async_add_chore = AsyncMock()
    coordinator.async_record_audit = AsyncMock()
    connection = _connection()
    msg = {
        "id": 1,
        "type": ws.WS_ADD_CHORE,
        "name": "Wash hands",
        "times": [{"start": "07:00", "end": "09:00"}, {"start": "08:00", "end": "10:00"}],
    }
    await ws._ws_add_chore(_hass_with(coordinator), connection, msg)
    coordinator.async_add_chore.assert_not_awaited()
    assert connection.send_error.call_args.args[1] == "invalid"


@pytest.mark.asyncio
async def test_ws_update_with_bad_times_leaves_the_stored_chore_alone():
    chore = Chore(name="Wash hands", id="c1", times=[ChoreTime(name="Lunch", start="12:00", end="13:00", id="l")])
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.storage = MagicMock()
    coordinator.storage.get_chore = MagicMock(return_value=chore)
    coordinator.async_update_chore = AsyncMock()
    coordinator.async_record_audit = AsyncMock()
    connection = _connection()
    msg = {
        "id": 1,
        "type": ws.WS_UPDATE_CHORE,
        "chore_id": "c1",
        "name": "Renamed",
        "times": [{"start": "09:00", "end": "08:00"}],
    }
    await ws._ws_update_chore(_hass_with(coordinator), connection, msg)
    coordinator.async_update_chore.assert_not_awaited()
    assert chore.name == "Wash hands"
    assert [t.id for t in chore.times] == ["l"]


@pytest.mark.asyncio
async def test_ws_update_refuses_making_a_set_time_chore_timed():
    chore = Chore(name="Wash hands", id="c1", times=[ChoreTime(name="Lunch", start="12:00", end="13:00", id="l")])
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.storage = MagicMock()
    coordinator.storage.get_chore = MagicMock(return_value=chore)
    coordinator.async_update_chore = AsyncMock()
    coordinator.async_record_audit = AsyncMock()
    connection = _connection()
    msg = {"id": 1, "type": ws.WS_UPDATE_CHORE, "chore_id": "c1", "task_type": "timed"}
    await ws._ws_update_chore(_hass_with(coordinator), connection, msg)
    coordinator.async_update_chore.assert_not_awaited()
    assert chore.task_type == "standard"


@pytest.mark.asyncio
async def test_ws_update_stores_times_as_chore_times():
    chore = Chore(name="Wash hands", id="c1")
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.storage = MagicMock()
    coordinator.storage.get_chore = MagicMock(return_value=chore)
    coordinator.async_update_chore = AsyncMock()
    coordinator.async_record_audit = AsyncMock()
    msg = {
        "id": 1,
        "type": ws.WS_UPDATE_CHORE,
        "chore_id": "c1",
        "times": [{"name": "Dinner", "start": "17:30", "end": "19:00", "points": 2}],
    }
    await ws._ws_update_chore(_hass_with(coordinator), _connection(), msg)
    assert isinstance(chore.times[0], ChoreTime) and chore.times[0].points == 2


# ── settings ─────────────────────────────────────────────────────────────────


def test_the_layout_setting_is_accepted_and_routed():
    schema = vol.Schema(ws._UPDATE_SETTINGS_SCHEMA)
    assert schema({"type": ws.WS_UPDATE_SETTINGS, "set_times_layout": "pills"})["set_times_layout"] == "pills"
    with pytest.raises(vol.Invalid):
        schema({"type": ws.WS_UPDATE_SETTINGS, "set_times_layout": "grid"})
    assert "set_times_layout" in ws._SUBKEY_SETTINGS


def test_the_overview_sensor_publishes_the_layout():
    src = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    assert '"set_times_layout": "pills" if settings.get("set_times_layout") == "pills" else "rows"' in src


# ── declared service surface ─────────────────────────────────────────────────


def _services():
    return yaml.safe_load((INTEGRATION / "services.yaml").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "service,field", [("complete_chore", "time_id"), ("add_chore", "times"), ("add_chore", "times_bonus")]
)
def test_service_fields_are_declared_and_translated(service, field):
    assert field in _services()[service]["fields"]
    for path in [INTEGRATION / "strings.json", *sorted((INTEGRATION / "translations").glob("*.json"))]:
        entry = json.loads(path.read_text(encoding="utf-8"))["services"][service]["fields"][field]
        assert entry["name"] and entry["description"], path.name


# ── cards ────────────────────────────────────────────────────────────────────


def test_the_shared_helper_is_defined_before_any_card_loads():
    assert "window.__taskmate_set_times = {" in _read("taskmate-attr-resolver.js")


@pytest.mark.parametrize("card", ["taskmate-child-card.js", "taskmate-kiosk-card.js"])
def test_cards_name_the_time_when_they_tick(card):
    src = _read(card)
    assert "time_id: chore._setTime.id" in src
    assert "chore_id: chore._baseId || chore.id" in src
    # A button press can't carry the time, so set times skip it.
    assert (
        "chore._setTime"
        in src.split("__taskmate_find_button(this.hass, child.id")[0].rsplit("const buttonEntityId", 1)[1]
    )


def test_both_child_card_render_paths_show_the_time():
    # The two-render-paths rule: the classic row and the designed meta both
    # call the shared renderer, so the time shows under every design.
    src = _read("taskmate-child-card.js")
    assert "this._renderSetTimeInfo(chore, child, 'classic')" in src
    assert 'this._renderSetTimeInfo(r.chore, r.child, "designed")' in src


def test_both_child_card_render_paths_refuse_a_closed_time():
    src = _read("taskmate-child-card.js")
    assert "if (setTimeLocked) return;" in src
    assert "|| weeklyDone || stLocked) return;" in src


@pytest.mark.parametrize("card", ["taskmate-child-card.js", "taskmate-kiosk-card.js"])
def test_card_editors_offer_the_layout_override(card):
    src = _read(card)
    assert "set_times_layout" in src and "common.set_times.layout_family" in src


def test_the_weekly_card_counts_a_set_time_chore_once_a_day():
    src = _read("taskmate-weekly-card.js")
    assert src.count("this._countChores(") >= 3


@pytest.mark.parametrize(
    "key",
    ["child.set_time_open_until", "common.set_times.layout_label", "panel.st_freq_set", "panel.st_err_overlap"],
)
def test_new_strings_are_in_every_locale(key):
    for path in sorted(LOCALES.glob("*.json")):
        assert key in json.loads(path.read_text(encoding="utf-8")), path.name


def test_the_panel_editor_sends_and_keeps_the_time_ids():
    src = _read("taskmate-panel.js")
    # Opening a chore copies its times with their ids, editing a window only
    # changes start/end on that object, and the save sends the id back.
    assert "times: (c.times || []).map(t => ({ ...t }))," in src
    assert "...(t.id ? { id: t.id } : {})," in src
    assert 'data-field="times[${i}].start"' in src and 'data-field="times[${i}].end"' in src


@pytest.mark.asyncio
async def test_ws_update_without_ids_keeps_the_stored_ids():
    chore = Chore(
        name="Wash hands",
        id="c1",
        times=[
            ChoreTime(name="Before", start="14:27", end="15:27", id="old-b"),
            ChoreTime(name="Now", start="16:00", end="17:00", id="old-n"),
        ],
    )
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.storage = MagicMock()
    coordinator.storage.get_chore = MagicMock(return_value=chore)
    coordinator.async_update_chore = AsyncMock()
    coordinator.async_record_audit = AsyncMock()
    msg = {
        "id": 1,
        "type": ws.WS_UPDATE_CHORE,
        "chore_id": "c1",
        "times": [
            {"name": "Before", "start": "14:27", "end": "15:27", "points": 1},
            {"name": "Now", "start": "16:05", "end": "17:00", "points": 1},
        ],
    }
    await ws._ws_update_chore(_hass_with(coordinator), _connection(), msg)
    assert [t.id for t in chore.times] == ["old-b", "old-n"]


def test_a_finished_day_with_a_miss_is_not_shown_as_done():
    # The pills row acts on a missed time before falling back to the last
    # one, so 2-of-3-with-a-miss never reads as struck-through and done.
    src = _read("taskmate-attr-resolver.js")
    assert '|| entries.find((e) => e.state === "missed")\n      || entries[entries.length - 1];' in src


def test_the_mandatory_warning_is_only_on_an_open_or_missed_time():
    src = _read("taskmate-child-card.js")
    assert 'mandatory: !!chore.mandatory && (entry.state === "now" || entry.state === "missed"),' in src


def test_the_kiosk_puts_the_time_name_on_its_own_line():
    src = _read("taskmate-kiosk-card.js")
    assert '<div class="km-st-sub">' in src
    assert 'class="km-row-name">${chore.name}</div>' in src
