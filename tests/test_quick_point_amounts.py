"""The family-wide quick point-adjustment amounts setting (#746)."""
from __future__ import annotations

import pathlib
import re

import pytest
import voluptuous as vol

from custom_components.taskmate.models import Child
from custom_components.taskmate.websocket import (
    _SUBKEY_SETTINGS,
    _UPDATE_SETTINGS_SCHEMA,
    _build_state_snapshot,
)

from .test_assignment_modes import _coord

WWW = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components" / "taskmate" / "www"
)
PANEL = (WWW / "taskmate-panel.js").read_text(encoding="utf-8")
ACTIVITY_CARD = (WWW / "taskmate-activity-card.js").read_text(encoding="utf-8")


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


def test_panel_has_the_amounts_parser():
    assert "_quickPointAmounts()" in PANEL


def test_parser_caps_at_three_amounts_and_defaults():
    block = re.search(r"_quickPointAmounts\(\) \{(.*?)\n  \}", PANEL, re.S)
    assert block, "could not find _quickPointAmounts"
    body = block.group(1)
    assert ".slice(0, 3)" in body, "must cap at three amounts"
    assert "[5, 10, 20]" in body, "must fall back to the default list"
    assert "10000" in body, "must bound amounts at 10000"


def test_settings_tab_exposes_the_amounts_field():
    assert 'data-setting="quick_point_amounts"' in PANEL
    assert "panel.settings_quick_points_label" in PANEL
    assert "panel.settings_quick_points_hint" in PANEL


def _strip_body() -> str:
    block = re.search(r"_renderAdjustStrip\(child, pointsName\) \{(.*?)\n  \}", PANEL, re.S)
    assert block, "could not find _renderAdjustStrip"
    return block.group(1)


def test_child_card_calls_the_adjust_strip():
    # The markup lives in _renderAdjustStrip; the card must actually invoke it,
    # or the strip exists but never renders.
    block = re.search(r"_renderChildCard\(child, pointsName\) \{(.*?)\n  \}", PANEL, re.S)
    assert block, "could not find _renderChildCard"
    assert "_renderAdjustStrip(child, pointsName)" in block.group(1)


def test_adjust_strip_renders_both_directions_and_the_custom_button():
    body = _strip_body()
    assert "tm-points-adjust" in body
    assert 'data-act="adjust-points"' in body
    assert 'data-act="adjust-points-custom"' in body
    assert "_quickPointAmounts()" in body, "the strip must read the configured amounts"


def test_adjust_actions_are_wired_into_the_click_dispatch():
    # A data-act with no dispatch entry is a dead button.
    assert re.search(r'act === "adjust-points"\s*\)', PANEL)
    assert re.search(r'act === "adjust-points-custom"\s*\)', PANEL)


def test_adjust_handler_picks_the_service_from_the_sign():
    block = re.search(r"async _doAdjustPoints\((.*?)\n  \}", PANEL, re.S)
    assert block, "could not find _doAdjustPoints"
    body = block.group(1)
    assert "add_points" in body and "remove_points" in body
    assert "Math.abs" in body, "the service takes a positive magnitude"
    assert "_adjustBusy" in body, "must guard against double-submit"


def test_adjust_buttons_are_labelled_for_screen_readers():
    # The visible text is only ever a signed number, so every button in the
    # strip needs a real label naming amount, direction and child.
    body = _strip_body()
    assert body.count("aria-label") >= 2, "both the amount buttons and ⋯ need labels"
    assert "panel.adjust_add_title" in body
    assert "panel.adjust_remove_title" in body
    assert "panel.adjust_custom_title" in body


def test_adjust_strip_has_styles():
    assert ".tm-points-adjust {" in PANEL
    # The set wrapper is what stops ⋯ orphaning onto its own row on a narrow card.
    assert ".tm-points-adjust-set {" in PANEL
    assert "tm-points-adjust-set" in _strip_body()


def test_adjust_dialog_is_registered_in_the_kind_dispatch():
    # A render function with no dispatch entry never opens.
    assert re.search(r'this\._dialog\.kind === "adjust"', PANEL)
    assert "_renderAdjustDialog()" in PANEL


def test_adjust_dialog_has_amount_and_reason_fields():
    block = re.search(r"_renderAdjustDialog\(\) \{(.*?)\n  \}", PANEL, re.S)
    assert block, "could not find _renderAdjustDialog"
    body = block.group(1)
    assert "panel.adjust_amount" in body
    assert "panel.adjust_reason" in body
    assert "panel.adjust_dialog_title" in body


def test_adjust_dialog_offers_both_directions():
    block = re.search(r"_renderAdjustDialog\(\) \{(.*?)\n  \}", PANEL, re.S)
    body = block.group(1)
    assert 'data-act="save-adjust-add"' in body
    assert 'data-act="save-adjust-remove"' in body
    assert re.search(r'act === "save-adjust-add"\s*\)', PANEL)
    assert re.search(r'act === "save-adjust-remove"\s*\)', PANEL)


def test_blank_reason_is_not_sent_as_an_empty_string():
    block = re.search(r"async _saveAdjustDialog\((.*?)\n  \}", PANEL, re.S)
    assert block, "could not find _saveAdjustDialog"
    body = block.group(1)
    assert "trim()" in body, "a whitespace-only reason must not be stored"


def test_both_readers_translate_the_stored_reason():
    # The panel and the Lovelace activity card each keep their own reason map;
    # a reason added to one and not the other renders as raw English.
    for name, src in (("panel", PANEL), ("activity-card", ACTIVITY_CARD)):
        assert "Admin panel adjustment" in src, f"{name} does not recognise the reason"
        assert "activity.reason_admin_adjustment" in src, f"{name} has no translation lookup"


def test_the_written_reason_matches_the_translated_reason():
    # The string _doAdjustPoints stores must be the string the readers match on.
    written = re.findall(r'reason = "([^"]+)"', PANEL)
    assert "Admin panel adjustment" in written


def test_manual_adjustments_stay_undoable():
    # _UNDO_DENY_PREFIXES is for derived transactions only. A manual adjustment
    # is exactly the kind of thing a parent needs to be able to reverse.
    block = re.search(r"_UNDO_DENY_PREFIXES\(\) \{(.*?)\n  \}", ACTIVITY_CARD, re.S)
    assert block, "could not find _UNDO_DENY_PREFIXES"
    assert "Admin panel" not in block.group(1)
