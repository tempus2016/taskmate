"""Approve All must acknowledge the tap while it runs (#799).

#794 made the batch fast (7.40s -> 0.21s for 60 approvals) but not instant.
A button that looks completely untouched while the call is in flight is what
made that bug report say "nothing happens" in the first place, so both
surfaces now show a busy state for the duration.
"""

from __future__ import annotations

import json
import pathlib

WWW = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www"
PANEL = (WWW / "taskmate-panel.js").read_text(encoding="utf-8")
CARD = (WWW / "taskmate-approvals-card.js").read_text(encoding="utf-8")

BUSY_KEYS = {"panel.activity_approve_all_busy", "approvals.approve_all_busy"}


def _panel_handler() -> str:
    start = PANEL.index("  async _doApproveAll() {")
    return PANEL[start : PANEL.index("\n  async _doReject(", start)]


def _card_handler() -> str:
    start = CARD.index("  async _handleApproveAll(completions) {")
    return CARD[start : CARD.index("\n  async _callService(", start)]


class TestPanelBusyState:
    def test_flag_is_set_before_the_call(self):
        h = _panel_handler()
        assert "this._approvingAll = true;" in h
        assert h.index("this._approvingAll = true;") < h.index("taskmate/approve_all_chores")

    def test_flag_is_cleared_even_when_the_call_throws(self):
        """A stuck busy button would be worse than no busy button at all."""
        h = _panel_handler()
        assert "finally {" in h, "the reset must be in a finally block"
        assert "this._approvingAll = false;" in h

    def test_setting_the_flag_triggers_a_render(self):
        """Without this the flag changes nothing on screen."""
        h = _panel_handler()
        after_set = h[h.index("this._approvingAll = true;"):]
        assert "this._render();" in after_set.split("taskmate/approve_all_chores")[0]

    def test_a_second_tap_is_ignored_while_running(self):
        assert "if (this._approvingAll) return;" in _panel_handler()

    def test_button_is_disabled_and_relabelled_while_busy(self):
        assert 'data-act="approve-all-chores"' in PANEL
        button = PANEL[PANEL.index('data-act="approve-all-chores"') - 400:]
        button = button[: button.index("</button>")]
        assert "_approvingAll" in button, "the button never consults the busy flag"
        assert "disabled" in button
        assert "panel.activity_approve_all_busy" in button

    def test_spinner_is_styled(self):
        assert ".tm-btn-spinner {" in PANEL
        assert "@keyframes tm-spin" in PANEL

    def test_disabled_buttons_are_visibly_disabled(self):
        assert ".tm-btn:disabled" in PANEL

    def test_spinner_respects_reduced_motion(self):
        """An indefinitely spinning element is exactly what that setting is for."""
        block = PANEL[PANEL.index(".tm-btn-spinner {"):]
        assert "prefers-reduced-motion" in block[:900]


class TestCardBusyState:
    def test_both_render_paths_show_the_busy_label(self):
        """Classic and designed each render their own Approve All button."""
        assert CARD.count("approvals.approve_all_busy") == 2, (
            "both approve-all buttons must show the busy label"
        )

    def test_button_stays_disabled_while_running(self):
        assert CARD.count("""?disabled="${this._loading['__all__']}\"""") == 2

    def test_spinner_is_styled(self):
        assert ".btn-spinner {" in CARD

    def test_loading_flag_is_cleared_in_a_finally(self):
        h = _card_handler()
        assert "finally {" in h
        assert "'__all__': false" in h


class TestBusyStringsAreTranslated:
    def test_every_locale_has_both_keys(self):
        for path in sorted((WWW / "locales").glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            missing = sorted(k for k in BUSY_KEYS if k not in data)
            assert missing == [], f"{path.name} missing {missing}"

    def test_no_locale_left_as_english_placeholder(self):
        """Shipping the English string in every file is the failure mode the
        translate-with-the-feature rule exists to prevent."""
        english = {}
        values = {}
        for path in sorted((WWW / "locales").glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            values[path.name] = {k: data[k] for k in BUSY_KEYS}
            if path.name in ("en.json", "en-GB.json"):
                english = values[path.name]
        non_english = [n for n in values if not n.startswith("en")]
        untranslated = [n for n in non_english if values[n] == english]
        assert untranslated == [], f"still English: {untranslated}"
