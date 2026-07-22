"""Accessible design style (#685).

A fourth per-card design: colour-blind safe, high contrast, dyslexia-friendly
type. The design ids live in THREE places — the JS design layer, the websocket
allowlist and the select entity — and a mismatch means a style that either
can't be chosen or can't be saved.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
DESIGN_JS = (ROOT / "www" / "taskmate-design.js").read_text(encoding="utf-8")
WEBSOCKET = (ROOT / "websocket.py").read_text(encoding="utf-8")
SELECT = (ROOT / "select.py").read_text(encoding="utf-8")


def _js_ids() -> list[str]:
    m = re.search(r"const IDS = \[(.*?)\];", DESIGN_JS)
    assert m
    return re.findall(r'"([a-z]+)"', m.group(1))


def _ws_ids() -> set[str]:
    m = re.search(r"_ALLOWED_CARD_DESIGNS = \{(.*?)\}", WEBSOCKET, re.S)
    assert m
    return set(re.findall(r'"([a-z]+)"', m.group(1)))


def _select_ids() -> list[str]:
    m = re.search(r'\("card_design", "card_design", \[(.*?)\]', SELECT)
    assert m
    return re.findall(r'"([a-z]+)"', m.group(1))


class TestIdsStayInSync:
    def test_websocket_matches_the_design_layer(self):
        """A style the backend rejects can be picked but never saved."""
        assert _ws_ids() == set(_js_ids())

    def test_select_entity_matches_the_design_layer(self):
        assert set(_select_ids()) == set(_js_ids())

    def test_accessible_is_registered_everywhere(self):
        assert "accessible" in _js_ids()
        assert "accessible" in _ws_ids()
        assert "accessible" in _select_ids()


class TestTokens:
    def test_light_and_dark_variants_both_exist(self):
        assert '[data-tm-design="accessible"]' in DESIGN_JS
        assert '[data-tm-design="accessible"][data-tm-dark]' in DESIGN_JS

    def test_uses_the_okabe_ito_colour_blind_safe_palette(self):
        """These specific hues are the point — they survive all three common
        forms of colour blindness."""
        block = _accessible_block()
        for colour in ("#0072B2", "#D55E00", "#009E73", "#E69F00", "#CC79A7", "#56B4E9"):
            assert colour in block, f"{colour} missing from the accessible palette"

    def test_text_is_near_black_on_white(self):
        block = _accessible_block()
        assert "--tmd-text:#111111" in block
        assert "--tmd-surface:#FFFFFF" in block

    def test_borders_carry_meaning_without_hue(self):
        """Colour alone must not be the only signal."""
        assert "--tmd-border:#111111" in _accessible_block()

    def test_dyslexia_friendly_font_is_used_throughout(self):
        block = _accessible_block()
        assert block.count("Atkinson Hyperlegible") >= 3  # display, body, mono

    def test_the_font_is_actually_loaded(self):
        assert "Atkinson+Hyperlegible" in DESIGN_JS

    def test_dark_variant_avoids_pure_black(self):
        """Pure black blooms on OLED and is harsh with astigmatism."""
        dark = _accessible_block(dark=True)
        assert "--tmd-bg:#0A0A0A" in dark
        assert "--tmd-text:#F5F5F5" in dark


class TestEditor:
    def test_offered_in_the_card_editor(self):
        m = re.search(r"function editorOptions\(t\) \{(.*?)\n  \}", DESIGN_JS, re.S)
        assert m and 'value: "accessible"' in m.group(1)

    def test_label_exists_in_every_locale(self):
        import json
        for path in sorted((ROOT / "www" / "locales").glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            assert "common.design.accessible" in data, f"{path.name} missing the label"


def _accessible_block(dark: bool = False) -> str:
    needle = ('[data-tm-design="accessible"][data-tm-dark]' if dark
              else ':host([data-tm-design="accessible"]),')
    start = DESIGN_JS.index(needle)
    return DESIGN_JS[start:DESIGN_JS.index("}", start)]
