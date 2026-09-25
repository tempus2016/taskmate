"""Weekly target: the panel editor and the cards that render it (#883).

The backend cap is covered elsewhere. These guard the frontend half, which has
its own failure mode: a chore that the coordinator will refuse to complete but
that a card still offers a DONE button for, or a field the editor never sends
so the target can be set once and then never changed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

WWW = Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www"
LOCALES = WWW / "locales"

PANEL = (WWW / "taskmate-panel.js").read_text(encoding="utf-8")
DASHBOARD = (WWW / "taskmate-parent-dashboard-card.js").read_text(encoding="utf-8")


# ── the panel editor ─────────────────────────────────────────────────────────


def test_chore_dialog_seeds_a_weekly_target():
    # A key absent from the blank seed is undefined in the dialog, so the
    # input renders empty and saves as 0 even for a chore that had one.
    assert "weekly_target: 0" in PANEL


def test_chore_dialog_sends_the_weekly_target():
    # _ws_update_chore only applies fields present in the message — a field the
    # dialog never sends can be set once and then never cleared (#793).
    assert "weekly_target: Math.max(0, Number(d.weekly_target)" in PANEL


def test_chore_editor_offers_a_weekly_target_field():
    assert "panel.chore_weekly_target_label" in PANEL


# ── the parent dashboard ─────────────────────────────────────────────────────
# The child card and the overview card are covered for real in
# tests/frontend/taskmate-child-card.test.cjs. The dashboard builds its list
# inside a render method, so a source check is what's left.


def test_parent_dashboard_respects_the_weekly_target():
    # It filters on `doneToday < (c.daily_limit || 1)`. Without the weekly cap
    # it keeps offering a chore the backend will refuse.
    assert "weekly_chore_progress" in DASHBOARD


# ── strings ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("locale", ["en", "en-GB", "da", "de", "fr", "nb", "nn", "pt", "pt-BR"])
@pytest.mark.parametrize(
    "key",
    [
        "panel.chore_weekly_target_label",
        "panel.chore_weekly_target_hint",
        "panel.chore_weekly_target_pill",
        "child.weekly_target_progress",
        "child.weekly_target_done",
    ],
)
def test_new_strings_are_translated_everywhere(locale, key):
    strings = json.loads((LOCALES / f"{locale}.json").read_text(encoding="utf-8"))
    assert key in strings, f"{key} missing from {locale}.json"
    assert strings[key].strip(), f"{key} is empty in {locale}.json"
