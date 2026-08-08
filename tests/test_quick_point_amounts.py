"""The family-wide quick point-adjustment amounts setting (#746)."""
from __future__ import annotations

import pytest
import voluptuous as vol

from custom_components.taskmate.models import Child
from custom_components.taskmate.websocket import (
    _SUBKEY_SETTINGS,
    _UPDATE_SETTINGS_SCHEMA,
    _build_state_snapshot,
)

from .test_assignment_modes import _coord


def test_quick_point_amounts_is_a_whitelisted_setting():
    # Must be in _SUBKEY_SETTINGS or _ws_update_settings silently drops it.
    assert "quick_point_amounts" in _SUBKEY_SETTINGS


def test_schema_accepts_a_comma_separated_string():
    schema = vol.Schema(_UPDATE_SETTINGS_SCHEMA)
    out = schema({"type": "taskmate/update_settings", "quick_point_amounts": "5, 10, 20"})
    assert out["quick_point_amounts"] == "5, 10, 20"


def test_schema_accepts_an_empty_string():
    # Clearing the field must be allowed; the panel falls back to its default.
    schema = vol.Schema(_UPDATE_SETTINGS_SCHEMA)
    out = schema({"type": "taskmate/update_settings", "quick_point_amounts": ""})
    assert out["quick_point_amounts"] == ""


def test_schema_rejects_an_over_long_value():
    schema = vol.Schema(_UPDATE_SETTINGS_SCHEMA)
    with pytest.raises(vol.Invalid):
        schema({"type": "taskmate/update_settings", "quick_point_amounts": "1," * 100})


def test_snapshot_omits_the_key_when_unset():
    coord = _coord([Child(name="A")])
    coord.storage.data = {}
    snap = _build_state_snapshot(coord)
    # No stored default — the panel owns the fallback.
    assert "quick_point_amounts" not in snap["settings"]


def test_snapshot_reflects_a_stored_value():
    coord = _coord([Child(name="A")])
    coord.storage.data = {"settings": {"quick_point_amounts": "2, 25, 100"}}
    snap = _build_state_snapshot(coord)
    assert snap["settings"]["quick_point_amounts"] == "2, 25, 100"
