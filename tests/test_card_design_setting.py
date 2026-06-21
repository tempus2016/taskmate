"""Tests for the global default card-design setting (per-card design styles)."""
from __future__ import annotations

from custom_components.taskmate.models import Child
from custom_components.taskmate.websocket import (
    _build_state_snapshot,
    _SUBKEY_SETTINGS,
    _ALLOWED_CARD_DESIGNS,
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
