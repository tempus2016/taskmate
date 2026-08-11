"""The chore Picture actually saves, and actually shows up (#745).

Two independent faults sat behind that issue:

1. The panel's chore save built an explicit payload and `icon` was missing from
   it, so the picked icon was dropped in the browser and never reached the
   backend. The backend has always accepted it.
2. Even once saved, no standard chore row rendered it. Classic showed a
   numbered badge; the designed styles showed an emoji guessed by regex from
   the chore *name*, so an explicit icon changed nothing.

The panel and the cards are JavaScript, so what Python can guard is the source
itself — these assertions are what stop either half silently regressing.
"""

from __future__ import annotations

import pathlib
import re

WWW = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www"
PANEL = (WWW / "taskmate-panel.js").read_text(encoding="utf-8")
CARD = (WWW / "taskmate-child-card.js").read_text(encoding="utf-8")


def _method_source(source: str, start_marker: str, end_marker: str) -> str:
    """Slice a method body out by its definition, not one of its call sites."""
    start = source.index(start_marker)
    return source[start : source.index(end_marker, start)]


def _save_chore_source() -> str:
    return _method_source(PANEL, "  async _doSaveChore() {", "  _addBonusSubtask() {")


def _chore_card_source() -> str:
    return _method_source(
        CARD,
        "  _renderChoreCard(chore, child, pointsIcon, todaysCompletions = [], choreIndex = 0) {",
        "  _renderTimedChoreCard(",
    )


class TestPanelSendsTheIcon:
    """The half that made the issue title true: it never saved."""

    def test_payload_carries_the_icon(self):
        assert "icon: d.icon" in _save_chore_source()

    def test_picker_is_synced_before_the_payload_is_built(self):
        """`ha-icon-picker` writes into the draft via a `value-changed` event.
        Every other dialog re-reads the live pickers first as a safety net; the
        chore dialog was the only one that did not."""
        save = _save_chore_source()
        assert "this._syncIconPickers();" in save
        assert save.index("this._syncIconPickers();") < save.index("icon: d.icon")

    def test_every_icon_picker_dialog_syncs_before_saving(self):
        """A blanket guard so no new dialog reintroduces this bug.

        The invariant is about the *widget*, not the field: only
        `_iconPickerField` renders an `<ha-icon-picker>`, and only those need
        `_syncIconPickers`. Two savers send an `icon` without one and are
        exempt — the bulk-add dialog has no picture field at all, and the
        template dialog uses a plain text input, which reports through the
        ordinary `input` handler.
        """
        no_picker = {"BulkChores", "CreatedTemplate", "EditedTemplate"}
        # Keep the exemption honest: the template dialog is exempt only for as
        # long as it really is a text input.
        assert 'data-field="icon" value="${this._esc(d.icon)}"' in PANEL
        savers = re.findall(r"  async _doSave(\w+)\(\) \{(.*?)\n  \}", PANEL, re.S)
        assert savers, "no _doSave* methods found — did the panel get restructured?"
        checked = 0
        for name, body in savers:
            if "icon: d.icon" in body and name not in no_picker:
                checked += 1
                assert "this._syncIconPickers();" in body, (
                    f"_doSave{name} sends an icon without syncing the pickers first"
                )
        assert checked, "no picker-backed savers matched — the guard has stopped guarding"


class TestClassicRowShowsTheIcon:
    """Option A: the icon takes the digit's place in the existing badge."""

    def _badge_source(self) -> str:
        return _method_source(
            CARD,
            "  _choreNumberBadge(chore, colorClass, choreNumber) {",
            "  _renderChoreCard(",
        )

    def test_badge_renders_the_icon_when_one_is_set(self):
        # #750 moved the icon/image/fallback decision into the shared resolver
        # window.__taskmate_chore_visual, so the badge no longer reads
        # chore.icon directly. The guarantee is unchanged: an icon still shows
        # when one is set. Precedence itself is pinned in
        # tests/test_chore_image_rendering.py.
        badge = self._badge_source()
        assert "__taskmate_chore_visual" in badge
        assert 'v.kind === "icon"' in badge
        assert "<ha-icon icon=" in badge

    def test_badge_falls_back_to_the_number(self):
        """Chores with no picture — i.e. every chore that exists today — must
        keep their number, or the fix is a visual regression for everyone."""
        badge = self._badge_source()
        assert "chore-number-badge" in badge
        assert "choreNumber" in badge

    def test_standard_and_timed_rows_share_the_badge(self):
        """Two copies is how a picture ends up working on one row type and
        invisible on the other."""
        assert CARD.count("this._choreNumberBadge(chore, colorClass, choreNumber)") == 2
        for marker, end in (
            ("  _renderChoreCard(chore, child, pointsIcon,", "  _renderTimedChoreCard("),
            ("  _renderTimedChoreCard(chore, child, pointsIcon,", "\n  _renderBonusSubtasks("),
        ):
            assert "this._choreNumberBadge(" in _method_source(CARD, marker, end)

    def test_the_dead_icon_container_css_is_gone(self):
        """`.chore-icon-container` styled an element removed long ago; leaving
        it behind is what made the row look intentionally icon-free."""
        assert ".chore-icon-container" not in CARD

    def test_icon_is_sized_for_the_badge(self):
        """ha-icon ignores the badge's font-size, so without an explicit size
        it renders at the 24px default and overflows the 30px mobile badge."""
        assert ".chore-number-badge ha-icon" in CARD


class TestDesignedRowsPreferTheExplicitIcon:
    """playroom / console / cleanpro rendered a guessed emoji regardless."""

    def test_rows_render_a_resolved_glyph(self):
        """All three designed renderers must go through the same resolver, or
        the icon works on one style and is invisible on the other two."""
        for cls in (".tmd-chore ", ".tmd-quest ", ".tmd-check "):
            assert cls in CARD
        assert CARD.count("r.glyph") >= 3

    def test_resolver_prefers_the_icon_over_the_guess(self):
        # As above: since #750 the icon arrives via __taskmate_chore_visual
        # rather than a direct chore.icon read. The ordering that matters —
        # icon beats the keyword-guessed emoji — is still asserted here, and
        # image-beats-icon is asserted in test_chore_image_rendering.py.
        assert "_choreGlyph(chore)" in CARD
        glyph = _method_source(CARD, "  _choreGlyph(chore) {", "  /** Mirror of _renderChoreCard")
        assert "__taskmate_chore_visual" in glyph
        assert 'v.kind === "icon"' in glyph
        assert glyph.index('v.kind === "icon"') < glyph.index("_choreEmoji(chore)")
        assert "_choreEmoji(chore)" in glyph

    def test_designed_icon_is_sized_per_row_type(self):
        """The emoji it replaces is sized by font-size, which ha-icon ignores."""
        for slot in (".ch-emoji .tmd-glyph-icon", ".q-emoji .tmd-glyph-icon", ".c-emoji .tmd-glyph-icon"):
            assert slot in CARD

    def test_emoji_guess_survives_as_the_fallback(self):
        """Existing chores have no icon, so the guess still has to run."""
        assert "_choreEmoji(chore) {" in CARD
        assert '"⭐"' in CARD
