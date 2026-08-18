"""Chore dependencies are frontend-only broken (#793).

The backend has supported `depends_on` since FEAT-1: it is in the websocket
schema and `_CHORE_EDITABLE_FIELDS`, `is_chore_available_for_child()` gates on
it, and the result is published in the `chore_availability` matrix. Two
independent frontend gaps made the feature unusable:

1. The panel's `_doSaveChore` built its payload without `depends_on`, so the
   dependency was never sent. `_ws_update_chore` only applies fields present in
   the message, so it also could never be cleared once set by other means.
2. The child card re-implements every availability rule client-side and had no
   dependency check, so a blocked chore always rendered.

Reproduced on the dev instance before the fix: the panel dialog held the
dependency after the chip toggle, `_doSaveChore()` stored `[]`; and with a
dependency forced in server-side, `chore_availability` reported the chore
unavailable while the card still rendered it.
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
WWW = ROOT / "www"
PANEL = (WWW / "taskmate-panel.js").read_text(encoding="utf-8")
CARD = (WWW / "taskmate-child-card.js").read_text(encoding="utf-8")


def _save_chore_payload() -> str:
    """The base payload object built by the panel's chore save."""
    start = PANEL.index("  async _doSaveChore() {")
    return PANEL[start : PANEL.index("const payload = wasAdd", start)]


def _filter_source() -> str:
    start = CARD.index("  _filterAndSortChores(chores, child) {")
    return CARD[start : CARD.index("\n  _getTimeCategoryIcon(", start)]


class TestPanelSendsDependencies:
    def test_save_payload_includes_depends_on(self):
        """The dialog tracks it via toggle-depends; it has to be sent too."""
        assert "depends_on" in _save_chore_payload(), (
            "the chore save payload omits depends_on, so the dependency never persists"
        )

    def test_dialog_still_seeds_and_toggles_it(self):
        """Guards the other half of the round trip."""
        assert 'this._toggleArrayField("depends_on"' in PANEL
        assert "depends_on: [...(c.depends_on || [])]" in PANEL

    def test_backend_accepts_the_field(self):
        """If this ever stops being true the panel fix is silently pointless."""
        ws = (ROOT / "websocket.py").read_text(encoding="utf-8")
        assert 'vol.Optional("depends_on"): [str]' in ws
        block = re.search(r"_CHORE_EDITABLE_FIELDS = \{(.*?)\}", ws, re.S)
        assert block and '"depends_on"' in block.group(1)

    def test_cards_can_see_the_field(self):
        """Cards read chores from _build_chores_list, which omits most fields."""
        sensor = (ROOT / "sensor.py").read_text(encoding="utf-8")
        assert '"depends_on": depends_on,' in sensor


class TestCardGatesOnDependencies:
    def test_filter_checks_depends_on(self):
        assert "depends_on" in _filter_source(), (
            "the card filter has no dependency gate, so a blocked chore always renders"
        )

    def test_gate_mirrors_the_backend_rule(self):
        """Backend: an approved, non-bonus completion today by the SAME child.
        A looser client rule would unlock chores the backend then refuses."""
        src = _filter_source()
        assert "approved" in src
        assert "bonus_subtask_id" in src

    def test_blocked_state_is_recorded_on_the_chore(self):
        """Render paths need to know, not just the filter."""
        assert "_isDependencyBlocked" in _filter_source()

    def test_blocked_chore_is_not_completable(self):
        """Showing it under dim/show must not let a tap through — the backend
        would refuse the completion anyway."""
        start = CARD.index("  _renderChoreCard(chore, child, pointsIcon")
        row = CARD[start : CARD.index("\n  _renderTimedChoreCard(", start)]
        assert "_isDependencyBlocked" in row
        assert "isInteractive" in row

    def test_timed_chores_are_gated_too(self):
        start = CARD.index("  _renderTimedChoreCard(chore, child, pointsIcon")
        timed = CARD[start : CARD.index("\n  _renderBonusSubtasks(", start)]
        assert "_isDependencyBlocked" in timed

    def test_picture_mode_is_gated_too(self):
        start = CARD.index("  _renderPreReaderTile(chore, child, pointsIcon")
        tile = CARD[start : CARD.index("_renderChoreCard(chore, child, pointsIcon", start)]
        assert "_isDependencyBlocked" in tile


class TestDependencyMode:
    def test_defaults_to_hide(self):
        """Matches the backend, which simply reports the chore unavailable."""
        assert "this.config.dependency_mode || 'hide'" in CARD

    def test_all_three_modes_are_offered(self):
        assert "name: 'dependency_mode'" in CARD
        for mode in ("dependency_hide", "dependency_dim", "dependency_show"):
            assert f"child.editor.{mode}" in CARD, f"missing option {mode}"

    def test_editor_exposes_the_default(self):
        assert "dependency_mode: this.config.dependency_mode || 'hide'" in CARD

    def test_strings_exist_in_every_locale(self):
        keys = {
            "child.editor.dependency_mode",
            "child.editor.dependency_hide",
            "child.editor.dependency_dim",
            "child.editor.dependency_show",
            "child.blocked_by_dependency",
        }
        for path in sorted((WWW / "locales").glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            missing = sorted(k for k in keys if k not in data)
            assert missing == [], f"{path.name} missing {missing}"
