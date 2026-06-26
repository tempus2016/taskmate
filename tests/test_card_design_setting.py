"""Tests for the global default card-design setting (per-card design styles)."""
from __future__ import annotations

from custom_components.taskmate.models import Child
from custom_components.taskmate.websocket import (
    _ALLOWED_CARD_DESIGNS,
    _SUBKEY_SETTINGS,
    _build_state_snapshot,
)

from .test_assignment_modes import _coord


def test_card_design_is_whitelisted_setting():
    assert "card_design" in _SUBKEY_SETTINGS


def test_snapshot_defaults_card_design_to_classic():
    coord = _coord([Child(name="A")])
    # No stored setting → snapshot falls back to the "classic" default.
    coord.storage.data = {}
    snap = _build_state_snapshot(coord)
    assert snap["settings"]["card_design"] == "classic"


def test_snapshot_reflects_stored_card_design():
    coord = _coord([Child(name="A")])
    # A stored value overrides the default via the settings spread.
    coord.storage.data = {"settings": {"card_design": "console"}}
    snap = _build_state_snapshot(coord)
    assert snap["settings"]["card_design"] == "console"


def test_allowed_card_designs_set():
    assert _ALLOWED_CARD_DESIGNS == {"classic", "playroom", "console", "cleanpro"}


def test_overview_sensor_exposes_card_design_default():
    from unittest.mock import MagicMock

    from custom_components.taskmate.sensor import TaskMateOverallStatsSensor

    from .test_sensor_attributes import _stress_coordinator

    coord = _stress_coordinator()
    attrs = TaskMateOverallStatsSensor(coord, MagicMock())._build_attributes()
    assert attrs["card_design"] == "classic"


def test_overview_sensor_reflects_stored_card_design():
    from unittest.mock import MagicMock

    from custom_components.taskmate.sensor import TaskMateOverallStatsSensor

    from .test_sensor_attributes import _stress_coordinator

    coord = _stress_coordinator()
    coord.data["settings"] = {**coord.data.get("settings", {}), "card_design": "playroom"}
    attrs = TaskMateOverallStatsSensor(coord, MagicMock())._build_attributes()
    assert attrs["card_design"] == "playroom"


def _settings_schema():
    """The update_settings websocket schema, wrapped for direct validation."""
    import voluptuous as vol

    from custom_components.taskmate.websocket import _UPDATE_SETTINGS_SCHEMA, WS_UPDATE_SETTINGS
    return vol.Schema(_UPDATE_SETTINGS_SCHEMA, extra=vol.ALLOW_EXTRA), WS_UPDATE_SETTINGS


def test_update_settings_schema_accepts_card_design():
    # Regression: card_design was routed but missing from the WS schema, so the
    # panel's Save failed with "extra keys not allowed @ data['card_design']".
    schema, cmd = _settings_schema()
    for d in ("classic", "playroom", "console", "cleanpro"):
        schema({"type": cmd, "id": 1, "card_design": d})  # must not raise


def test_update_settings_schema_rejects_bad_card_design():
    import pytest
    import voluptuous as vol
    schema, cmd = _settings_schema()
    with pytest.raises(vol.Invalid):
        schema({"type": cmd, "id": 1, "card_design": "bogus"})


def test_every_routed_setting_is_in_the_schema():
    # Guards against the exact class of bug: a key handled by _ws_update_settings
    # (in _SUBKEY_SETTINGS / _TOP_LEVEL_SETTINGS) but absent from the schema, so
    # voluptuous rejects it before the handler runs.
    from custom_components.taskmate.websocket import (
        _SUBKEY_SETTINGS,
        _TOP_LEVEL_SETTINGS,
        _UPDATE_SETTINGS_SCHEMA,
    )
    schema_keys = {str(k) for k in _UPDATE_SETTINGS_SCHEMA}
    routed = _SUBKEY_SETTINGS | _TOP_LEVEL_SETTINGS
    missing = routed - schema_keys
    assert not missing, f"settings routed but missing from WS schema: {sorted(missing)}"
