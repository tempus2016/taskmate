"""Chore-image strings must exist in every locale (#750)."""
from __future__ import annotations

import glob
import json
import os

KEYS = [
    "panel.chore_image_label",
    "panel.chore_image_hint",
    "panel.chore_image_upload",
    "panel.chore_image_remove",
    "panel.chore_image_empty",
    "panel.chore_image_uploading",
    "panel.chore_image_failed",
    "panel.chore_image_too_large",
    "panel.chore_image_bad_type",
]

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


def test_all_locales_have_identical_key_sets():
    sets = {name: set(data) for name, data in _locales()}
    reference = sets["en.json"]
    for name, keys in sets.items():
        assert keys == reference, (
            f"{name} key set differs from en.json: "
            f"missing={sorted(reference - keys)} extra={sorted(keys - reference)}"
        )
