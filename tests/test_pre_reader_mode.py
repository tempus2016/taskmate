"""Pre-reader mode and the chore icon it needs (#683).

A picture-only child card for children who can't read yet. The card itself is
JavaScript; what Python guards is the icon field it depends on — a chore with
no picture would leave a pre-reader looking at identical tiles.
"""
from __future__ import annotations

import json
import pathlib
import re

from custom_components.taskmate.models import Chore

WWW = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www"
CARD = (WWW / "taskmate-child-card.js").read_text(encoding="utf-8")


def _tile_source() -> str:
    """The tile method body — sliced from its definition, not its call site."""
    start = CARD.index("  _renderPreReaderTile(chore, child, todaysCompletions = [], choreIndex = 0) {")
    return CARD[start:CARD.index("_renderChoreCard(chore, child, pointsIcon", start)]


class TestChoreIcon:
    def test_defaults_to_empty(self):
        """Empty means "fall back to the time-of-day icon", not a bad default."""
        assert Chore(name="Chore").icon == ""

    def test_round_trips(self):
        restored = Chore.from_dict(Chore(name="Teeth", icon="mdi:tooth").to_dict())
        assert restored.icon == "mdi:tooth"

    def test_legacy_chore_without_an_icon(self):
        assert Chore.from_dict({"name": "Old"}).icon == ""

    def test_none_is_coerced_to_empty(self):
        assert Chore.from_dict({"name": "Odd", "icon": None}).icon == ""

    def test_icon_is_editable_over_the_websocket(self):
        ws = (WWW.parent / "websocket.py").read_text(encoding="utf-8")
        block = re.search(r"_CHORE_EDITABLE_FIELDS = \{(.*?)\}", ws, re.S)
        assert block and '"icon"' in block.group(1)

    def test_button_falls_back_when_no_picture_is_set(self):
        """The icon default is "", so a fallback keyed on the attribute being
        absent would leave every button blank."""
        button = (WWW.parent / "button.py").read_text(encoding="utf-8")
        assert "getattr(chore, 'icon', \"\") or \"mdi:check-circle\"" in button

    def test_icon_is_exposed_to_the_cards(self):
        """Cards read chores from the sensor, so an unexposed field is invisible."""
        sensor = (WWW.parent / "sensor.py").read_text(encoding="utf-8")
        assert 'record["icon"] = icon' in sensor


class TestPreReaderCard:
    def test_tile_renderer_exists(self):
        assert "_renderPreReaderTile" in CARD

    def test_grid_is_gated_behind_the_config_flag(self):
        """An existing dashboard must not suddenly turn into pictures."""
        assert "this.config.pre_reader === true" in CARD

    def test_labels_are_opt_in(self):
        """The whole point is no text, so names default to off."""
        assert "this.config.pre_reader_labels === true" in CARD

    def test_tile_falls_back_to_the_time_category_icon(self):
        assert "_getTimeCategoryIcon(chore.time_category)" in CARD

    def test_tile_uses_the_real_completion_handlers(self):
        assert "_handleComplete(chore, child)" in CARD
        assert "_handleUndo(chore, child, childCompletionsToday)" in CARD

    def test_done_tile_stays_tappable_for_undo(self):
        """A mis-tap must be recoverable, exactly as on the standard row."""
        tile = _tile_source()
        assert "?disabled=${isLoading || !available}" in tile

    def test_tile_shows_stars_rather_than_a_number(self):
        tile = _tile_source()
        assert "pre-tile-stars" in tile
        assert "mdi:star" in tile

    def test_editor_exposes_both_options(self):
        assert "name: 'pre_reader'" in CARD
        assert "name: 'pre_reader_labels'" in CARD

    def test_strings_exist_in_every_locale(self):
        keys = {"panel.chore_icon_label", "child.editor.pre_reader", "child.editor.pre_reader_labels"}
        for path in sorted((WWW / "locales").glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            missing = sorted(k for k in keys if k not in data)
            assert missing == [], f"{path.name} missing {missing}"


class TestPreReaderRendersOnEveryDesign:
    """Pre-reader mode was wired into the classic render path only.

    `render()` returns `_renderDesigned(design)` before reaching the classic
    branch, so `pre_reader: true` was silently ignored on playroom, console,
    cleanpro and accessible — and accessible is precisely the style a child who
    needs picture tiles is most likely to be using.
    """

    import pathlib as _pathlib

    SOURCE = (
        _pathlib.Path(__file__).resolve().parent.parent
        / "custom_components" / "taskmate" / "www" / "taskmate-child-card.js"
    ).read_text(encoding="utf-8")

    def _designed_region(self) -> str:
        start = self.SOURCE.index("_renderDesigned(design) {")
        end = self.SOURCE.index("\n  _designHeaderFull(", start)
        return self.SOURCE[start:end]

    def test_designed_styles_honour_pre_reader(self):
        region = self._designed_region()
        assert "pre_reader" in region, (
            "the designed render path never checks config.pre_reader, so "
            "pre-reader mode does nothing on any style but classic"
        )

    def test_designed_styles_render_the_picture_tiles(self):
        assert "_renderPreReaderTile(" in self._designed_region()
