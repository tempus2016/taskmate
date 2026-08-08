"""Point-management strings must exist in every locale (#746)."""
from __future__ import annotations

import glob
import json
import os

KEYS = [
    "panel.settings_quick_points_label",
    "panel.settings_quick_points_hint",
    "panel.adjust_add_title",
    "panel.adjust_remove_title",
    "panel.adjust_custom_title",
    "panel.adjust_dialog_title",
    "panel.adjust_amount",
    "panel.adjust_reason",
    "panel.adjust_add",
    "panel.adjust_remove",
    "panel.adjust_err_amount",
    "panel.adjust_done",
    "activity.reason_admin_adjustment",
]

# Keys whose text must keep the placeholders the panel substitutes into.
PLACEHOLDERS = {
    "panel.adjust_add_title": ["{amount}", "{points}", "{child}"],
    "panel.adjust_remove_title": ["{amount}", "{points}", "{child}"],
    "panel.adjust_custom_title": ["{child}"],
    "panel.adjust_dialog_title": ["{name}"],
    "panel.adjust_done": ["{sign}", "{amount}", "{points}", "{child}"],
}

BASE = os.path.join(
    os.path.dirname(__file__), "..",
    "custom_components", "taskmate", "www", "locales",
)


def _locales():
    files = glob.glob(os.path.join(BASE, "*.json"))
    assert files, "no locale files found"
    for path in files:
        with open(path, encoding="utf-8") as fh:
            yield os.path.basename(path), json.load(fh)


def test_keys_present_and_non_empty_in_every_locale():
    for name, data in _locales():
        for key in KEYS:
            assert key in data and data[key].strip(), f"{key} missing/empty in {name}"


def test_placeholders_survive_translation():
    for name, data in _locales():
        for key, tokens in PLACEHOLDERS.items():
            for token in tokens:
                assert token in data[key], f"{key} lost {token} in {name}"


def test_all_locales_have_identical_key_sets():
    sets = {name: set(data) for name, data in _locales()}
    reference = sets["en.json"]
    for name, keys in sets.items():
        assert keys == reference, (
            f"{name} key set differs from en.json: "
            f"missing={sorted(reference - keys)} extra={sorted(keys - reference)}"
        )
