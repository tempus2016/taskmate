"""The setup dialog suggests the points name in Home Assistant's language."""

from __future__ import annotations

from custom_components.taskmate.points_name import default_points_name as _default_points_name


def test_suggests_the_word_the_panel_wizard_uses():
    assert _default_points_name("de") == "Sterne"
    assert _default_points_name("fr") == "Étoiles"
    assert _default_points_name("pt-BR") == "Estrelas"
    assert _default_points_name("en") == "Stars"


def test_falls_back_to_the_base_language_then_english():
    assert _default_points_name("de-CH") == "Sterne"
    assert _default_points_name("xx") == "Stars"
    assert _default_points_name(None) == "Stars"
