"""Family style preset (#1260): Game, Team and Custom."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol

from custom_components.taskmate import websocket, websocket_family_style, websocket_setup
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.family_style import (
    STYLE_SNAPSHOT_KEY,
    STYLE_SWITCHES,
    apply_family_style,
    current_style,
    features_off,
    plan_family_style,
    switch_values,
)
from custom_components.taskmate.storage import TaskMateStorage

ROOT = Path(__file__).resolve().parent.parent
WWW = ROOT / "custom_components" / "taskmate" / "www"

TEAM = {
    "leaderboard_enabled": False,
    "penalties_enabled": False,
    "points_decay_enabled": False,
    "raffles_enabled": False,
    "roulette_enabled": False,
    "inspections_enabled": False,
    "family_goal_enabled": True,
}
DEFAULTS = {
    "leaderboard_enabled": True,
    "penalties_enabled": True,
    "points_decay_enabled": False,
    "raffles_enabled": True,
    "roulette_enabled": False,
    "inspections_enabled": True,
    "family_goal_enabled": False,
}


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def coord():
    hass = MagicMock()
    storage = TaskMateStorage(hass, "test_entry")
    storage._store = MagicMock()
    storage._store.async_load = AsyncMock(return_value=None)
    storage._store.async_save = AsyncMock()
    storage._store.async_delay_save = MagicMock()
    run(storage.async_load())
    c = object.__new__(TaskMateCoordinator)
    c.storage = storage
    c.async_refresh = AsyncMock()
    c.async_check_birthdays = AsyncMock(return_value=[])
    c.async_record_audit = AsyncMock()
    return c


def _ws(coord, admin=True):
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry": coord}}
    conn = MagicMock()
    conn.user = SimpleNamespace(is_admin=admin, id="u1", name="Parent")
    return hass, conn


# ── Defaults: a family that never picked a style ─────────────────────────────


def test_no_style_stored_reads_as_game_with_todays_defaults(coord):
    settings = coord.storage.get_settings()
    assert "family_style" not in settings
    assert current_style(settings) == "game"
    assert switch_values(settings) == DEFAULTS
    assert features_off(settings) == []


def test_switch_defaults_match_what_each_feature_reads(coord):
    # The coordinator's own readers agree with the style defaults.
    assert coord.inspections_enabled() is STYLE_SWITCHES["inspections_enabled"][0]
    assert coord.roulette_enabled() is STYLE_SWITCHES["roulette_enabled"][0]


def test_overview_adds_nothing_for_a_default_family():
    from custom_components.taskmate.sensor import TaskMateOverallStatsSensor

    from .test_sensor_attributes import _stress_coordinator

    attrs = TaskMateOverallStatsSensor(_stress_coordinator(), MagicMock())._build_attributes()
    assert "features_off" not in attrs
    assert "family_style" not in attrs


def test_overview_lists_features_off_and_team():
    from custom_components.taskmate.sensor import TaskMateOverallStatsSensor

    from .test_sensor_attributes import _stress_coordinator

    coord = _stress_coordinator()
    coord.data["settings"] = {
        **coord.data.get("settings", {}),
        "family_style": "team",
        "leaderboard_enabled": False,
        "raffles_enabled": False,
    }
    attrs = TaskMateOverallStatsSensor(coord, MagicMock())._build_attributes()
    assert attrs["features_off"] == ["leaderboard", "raffles"]
    assert attrs["family_style"] == "team"


# ── Applying a style ──────────────────────────────────────────────────────────


def test_team_switches_the_covered_options(coord):
    result = apply_family_style(coord.storage, "team")
    settings = coord.storage.get_settings()
    assert switch_values(settings) == TEAM
    assert settings["family_style"] == "team"
    assert result["previous"] is None
    changed = {c["key"]: (c["old"], c["new"]) for c in result["changes"]}
    assert changed == {
        "leaderboard_enabled": (True, False),
        "penalties_enabled": (True, False),
        "raffles_enabled": (True, False),
        "inspections_enabled": (True, False),
        "family_goal_enabled": (False, True),
    }
    assert settings["family_goal_achieved"] is False


def test_team_keeps_every_record(coord):
    coord.storage._data["penalties"] = [{"id": "p1", "name": "Rude", "points": 5}]
    coord.storage._data["raffles"] = [{"id": "r1", "name": "Cinema"}]
    apply_family_style(coord.storage, "team")
    assert coord.storage._data["penalties"] == [{"id": "p1", "name": "Rude", "points": 5}]
    assert coord.storage._data["raffles"] == [{"id": "r1", "name": "Cinema"}]


def test_game_restores_the_snapshot_taken_before_team(coord):
    coord.storage.set_setting("roulette_enabled", True)
    coord.storage.set_setting("points_decay_enabled", True)
    coord.storage.set_setting("inspections_enabled", False)
    before = switch_values(coord.storage.get_settings())
    apply_family_style(coord.storage, "team")
    assert coord.storage.get_settings()[STYLE_SNAPSHOT_KEY] == before
    result = apply_family_style(coord.storage, "game")
    settings = coord.storage.get_settings()
    assert switch_values(settings) == before
    assert settings["family_style"] == "game"
    assert STYLE_SNAPSHOT_KEY not in settings
    assert result["previous"] == "team"


def test_game_without_a_snapshot_uses_the_defaults(coord):
    coord.storage.set_setting("family_style", "custom")
    for key, value in TEAM.items():
        coord.storage.set_setting(key, value)
    apply_family_style(coord.storage, "game")
    assert switch_values(coord.storage.get_settings()) == DEFAULTS


def test_reapplying_team_keeps_the_first_snapshot(coord):
    coord.storage.set_setting("roulette_enabled", True)
    original = switch_values(coord.storage.get_settings())
    apply_family_style(coord.storage, "team")
    coord.storage.set_setting("family_style", "custom")
    coord.storage.set_setting("leaderboard_enabled", True)
    apply_family_style(coord.storage, "team")
    assert coord.storage.get_settings()[STYLE_SNAPSHOT_KEY] == original
    apply_family_style(coord.storage, "game")
    assert switch_values(coord.storage.get_settings()) == original


def test_custom_changes_nothing(coord):
    coord.storage.set_setting("roulette_enabled", True)
    before = switch_values(coord.storage.get_settings())
    result = apply_family_style(coord.storage, "custom")
    assert result["changes"] == []
    assert switch_values(coord.storage.get_settings()) == before
    assert coord.storage.get_settings()["family_style"] == "custom"


def test_plan_matches_apply_and_does_not_write(coord):
    plan = plan_family_style(coord.storage.get_settings(), "team")
    assert "family_style" not in coord.storage.get_settings()
    assert apply_family_style(coord.storage, "team")["changes"] == plan


def test_plan_refuses_an_unknown_style(coord):
    with pytest.raises(ValueError):
        plan_family_style(coord.storage.get_settings(), "chaos")


# ── Manual changes flip the style to Custom ──────────────────────────────────


def _update_settings(coord, **fields):
    hass, conn = _ws(coord)
    msg = {"id": 1, "type": websocket.WS_UPDATE_SETTINGS, **fields}
    run(websocket._ws_update_settings(hass, conn, msg))
    return conn


@pytest.mark.parametrize("style", ["game", "team"])
def test_changing_a_covered_option_by_hand_makes_it_custom(coord, style):
    apply_family_style(coord.storage, style)
    value = switch_values(coord.storage.get_settings())["roulette_enabled"]
    conn = _update_settings(coord, roulette_enabled=not value)
    assert coord.storage.get_settings()["family_style"] == "custom"
    assert "family_style" in conn.send_result.call_args.args[1]["updated"]


def test_saving_the_same_values_keeps_the_style(coord):
    apply_family_style(coord.storage, "team")
    _update_settings(coord, **TEAM, history_days=90)
    assert coord.storage.get_settings()["family_style"] == "team"


def test_an_uncovered_option_keeps_the_style(coord):
    apply_family_style(coord.storage, "team")
    _update_settings(coord, weekend_multiplier=1.5)
    assert coord.storage.get_settings()["family_style"] == "team"


def test_a_family_without_a_style_is_left_alone(coord):
    _update_settings(coord, penalties_enabled=False)
    settings = coord.storage.get_settings()
    assert "family_style" not in settings
    assert features_off(settings) == ["penalties"]


def test_update_settings_accepts_the_new_keys():
    schema = vol.Schema(websocket._UPDATE_SETTINGS_SCHEMA, extra=vol.ALLOW_EXTRA)
    msg = {"type": websocket.WS_UPDATE_SETTINGS, "id": 1}
    schema({**msg, "leaderboard_enabled": False, "penalties_enabled": False, "raffles_enabled": False})
    for scope in ("cards", "both"):
        schema({**msg, "style_hide_scope": scope})
    with pytest.raises(vol.Invalid):
        schema({**msg, "style_hide_scope": "panel"})
    for key in ("leaderboard_enabled", "penalties_enabled", "raffles_enabled", "style_hide_scope"):
        assert key in websocket._SUBKEY_SETTINGS
    # The style itself only changes through apply_family_style.
    assert "family_style" not in websocket._SUBKEY_SETTINGS


# ── WebSocket commands ────────────────────────────────────────────────────────


def test_apply_command_applies_and_returns_the_diff(coord):
    hass, conn = _ws(coord)
    coord.storage.async_save = AsyncMock()
    msg = {"id": 2, "type": websocket_family_style.WS_APPLY_FAMILY_STYLE, "style": "team"}
    run(websocket_family_style.ws_apply_family_style(hass, conn, msg))
    sent = conn.send_result.call_args.args[1]
    assert sent["style"] == "team"
    assert {c["key"] for c in sent["changes"]} == {
        "leaderboard_enabled",
        "penalties_enabled",
        "raffles_enabled",
        "inspections_enabled",
        "family_goal_enabled",
    }
    coord.storage.async_save.assert_awaited_once()
    coord.async_refresh.assert_awaited_once()


def test_apply_command_is_admin_only(coord):
    hass, conn = _ws(coord, admin=False)
    msg = {"id": 3, "type": websocket_family_style.WS_APPLY_FAMILY_STYLE, "style": "team"}
    run(websocket_family_style.ws_apply_family_style(hass, conn, msg))
    conn.send_error.assert_called_once()
    assert "family_style" not in coord.storage.get_settings()


def test_preview_command_changes_nothing(coord):
    hass, conn = _ws(coord)
    msg = {"id": 4, "type": websocket_family_style.WS_PREVIEW_FAMILY_STYLE, "style": "team"}
    run(websocket_family_style.ws_preview_family_style(hass, conn, msg))
    sent = conn.send_result.call_args.args[1]
    assert sent["previous"] == "game"
    assert len(sent["changes"]) == 5
    assert "family_style" not in coord.storage.get_settings()
    assert switch_values(coord.storage.get_settings()) == DEFAULTS
    # A read-only preview is not written to the audit log.
    assert websocket_family_style.WS_PREVIEW_FAMILY_STYLE in websocket._AUDIT_EXCLUDE


def test_commands_are_registered():
    src = (ROOT / "custom_components" / "taskmate" / "websocket.py").read_text(encoding="utf-8")
    assert "*FAMILY_STYLE_COMMANDS" in src


def test_setup_wizard_applies_the_chosen_style(coord):
    hass, conn = _ws(coord)
    msg = {
        "id": 5,
        "type": "taskmate/setup_wizard/apply",
        "children": [{"ref": "n", "name": "Isla"}],
        "child_updates": [],
        "chores": [],
        "rewards": [],
        "family_style": "team",
    }
    run(websocket_setup.ws_setup_apply(hass, conn, msg))
    sent = conn.send_result.call_args.args[1]
    assert sent["family_style"]["style"] == "team"
    assert coord.storage.get_settings()["family_style"] == "team"
    assert [c.name for c in coord.storage.get_children()] == ["Isla"]


def test_setup_wizard_without_a_style_leaves_it_unset(coord):
    hass, conn = _ws(coord)
    msg = {
        "id": 6,
        "type": "taskmate/setup_wizard/apply",
        "children": [{"ref": "n", "name": "Isla"}],
        "child_updates": [],
        "chores": [],
        "rewards": [],
    }
    run(websocket_setup.ws_setup_apply(hass, conn, msg))
    assert "family_style" not in conn.send_result.call_args.args[1]
    assert "family_style" not in coord.storage.get_settings()
