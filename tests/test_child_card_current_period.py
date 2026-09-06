"""Current-time-period filtering on the child card (#847).

A wall dashboard wants "chores due right now" without losing the child card's
layout. Two card options cover it:

* ``time_category: current`` resolves to whatever period is active at render
  time, so future-period chores stop leaking in as dimmed locked previews;
* ``include_anytime_chores: false`` suppresses the Anytime bucket, which
  otherwise matches every filter (including ``all``).

Both live entirely in the card. ``_filterAndSortChores`` is the single filter
used by the classic and the designed render paths, so one change covers all
five design styles.
"""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
WWW = ROOT / "www"
CARD = (WWW / "taskmate-child-card.js").read_text(encoding="utf-8")


def _section(start_marker: str, end_marker: str) -> str:
    start = CARD.index(start_marker)
    return CARD[start : CARD.index(end_marker, start)]


def _filter_source() -> str:
    return _section("  _filterAndSortChores(chores, child) {", "\n  _getTimeCategoryIcon(")


def _editor_options_source() -> str:
    return _section("  _timeCategoryEditorOptions(overviewEntity) {", "\n  _buildSchema(")


class TestEffectiveCategoryHelper:
    """`current` is resolved through one helper so every consumer agrees."""

    def test_helper_exists(self):
        assert "_effectiveTimeCategory(" in CARD

    def test_helper_resolves_current_to_the_live_period(self):
        src = _section("  _effectiveTimeCategory(", "\n  _getTimeCategoryIcon(")
        assert "'current'" in src or '"current"' in src
        # Must go through _getCurrentTimePeriod so user-defined periods work.
        assert "_getCurrentTimePeriod()" in src

    def test_helper_passes_other_categories_through(self):
        src = _section("  _effectiveTimeCategory(", "\n  _getTimeCategoryIcon(")
        assert "time_category" in src


class TestFilterUsesEffectiveCategory:
    """The filter must compare against the resolved period, not the raw config."""

    def test_filter_resolves_the_configured_category(self):
        assert "_effectiveTimeCategory()" in _filter_source()

    def test_filter_no_longer_compares_chores_to_raw_config(self):
        # Reading config.time_category to detect current mode is fine; matching a
        # chore against it directly is what broke `current`.
        assert "chore.time_category === this.config.time_category" not in _filter_source()


class TestFuturePreviewsSuppressed:
    """`current` mode is the whole point: no future-period chores."""

    def test_locked_preview_passthrough_is_conditional(self):
        src = _filter_source()
        # The preview pass-through leaked future chores in. It must survive only
        # on the non-current branch of an isCurrentMode ternary.
        assert "isCurrentMode" in src
        assert "? matchesCardFilter || inClaimWindow" in src
        assert ": matchesCardFilter || isLockedPreview || inClaimWindow" in src

    def test_preview_flag_cleared_in_current_mode(self):
        # Nothing should render as a dimmed preview when the card is "right now".
        assert "isCurrentMode ? false : isLockedPreview" in _filter_source()

    def test_claim_window_still_honoured_in_current_mode(self):
        # A chore inside its post-period grace stays actionable (elapsed_time_mode
        # keeps owning past periods).
        src = _filter_source()
        assert "inClaimWindow" in src


class TestAnytimeToggle:
    def test_filter_reads_include_anytime_chores(self):
        assert "include_anytime_chores" in _filter_source()

    def test_defaults_to_true_so_existing_cards_are_unchanged(self):
        # `!== false` is the house idiom for a default-on boolean.
        assert "include_anytime_chores !== false" in CARD

    def test_anytime_match_is_gated_on_the_toggle(self):
        src = _filter_source()
        assert 'chore.time_category === "anytime"' in src or "chore.time_category === 'anytime'" in src
        assert "includeAnytime" in src

    def test_opting_out_is_a_hard_gate_not_a_filter_clause(self):
        # Caught on ha-dev: _isChoreInClaimWindow() returns true for "anytime",
        # so gating only the matchesCardFilter clause let every anytime chore
        # back in through the claim-window branch. It has to be an early return.
        src = _filter_source()
        assert 'if (!includeAnytime && chore.time_category === "anytime") return false;' in src

    def test_claim_window_still_short_circuits_anytime(self):
        # Guards the trap above from regressing at its source.
        src = _section("  _isChoreInClaimWindow(chore) {", "\n  // Returns true when")
        assert "if (cat === 'anytime') return true;" in src

    def test_setconfig_declares_the_default(self):
        src = _section("  setConfig(config) {", "\n  getCardSize()")
        assert "include_anytime_chores: true" in src


class TestTitleAndIcon:
    """The header must follow the live period, not print 'current'."""

    def test_dynamic_title_resolves_current(self):
        src = _section("  _getDynamicTitle() {", "\n  _getTimezone()")
        assert "_effectiveTimeCategory()" in src

    def test_header_icon_resolves_current(self):
        # The render path must not pass the raw config value to the icon map.
        assert "_getTimeCategoryIcon(this.config.time_category)" not in CARD
        assert "_getTimeCategoryIcon(this._effectiveTimeCategory())" in CARD


class TestEditor:
    def test_current_is_offered_in_the_dropdown(self):
        src = _editor_options_source()
        assert "'current'" in src or '"current"' in src
        assert "child.editor.time_category_current" in src

    def test_include_anytime_chores_has_a_schema_entry(self):
        schema = _section("  _buildSchema() {", "\n  _computeLabel")
        assert "include_anytime_chores" in schema

    def test_editor_renders_the_toggle_state(self):
        src = _section("  render() {\n    if (!this.hass || !this.config) return html``;", "\n    return html`")
        assert "include_anytime_chores" in src


class TestTranslations:
    """New user-facing strings ship translated in every locale, same PR."""

    KEYS = (
        "child.editor.time_category_current",
        "child.editor.include_anytime_chores",
        "child.editor.include_anytime_chores_helper",
    )

    def test_every_locale_has_the_new_keys(self):
        locales = sorted(p for p in (WWW / "locales").glob("*.json"))
        assert locales, "no locale files found"
        for path in locales:
            data = json.loads(path.read_text(encoding="utf-8"))
            for key in self.KEYS:
                assert key in data, f"{path.name} missing {key}"
                assert data[key].strip(), f"{path.name} has an empty {key}"

    def test_non_english_locales_are_actually_translated(self):
        en = json.loads((WWW / "locales" / "en.json").read_text(encoding="utf-8"))
        for path in sorted((WWW / "locales").glob("*.json")):
            if path.stem in ("en", "en-GB"):
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            untranslated = [k for k in self.KEYS if data[k] == en[k]]
            assert not untranslated, f"{path.name} left English: {untranslated}"
