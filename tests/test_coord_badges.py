"""Tests for coord_badges."""
from __future__ import annotations

from custom_components.taskmate.coord_badges import BUILTIN_CATALOGUE
from custom_components.taskmate.models import Badge


class TestBuiltinCatalogue:
    def test_has_15_builtins(self):
        assert len(BUILTIN_CATALOGUE) == 15

    def test_all_marked_builtin(self):
        for b in BUILTIN_CATALOGUE:
            assert isinstance(b, Badge)
            assert b.builtin is True
            assert b.id.startswith("builtin.")

    def test_first_chore_present(self):
        ids = {b.id for b in BUILTIN_CATALOGUE}
        assert "builtin.first_chore" in ids
        assert "builtin.30_day_streak" in ids

    def test_tiers_distributed(self):
        tiers = {b.tier for b in BUILTIN_CATALOGUE}
        assert tiers == {"bronze", "silver", "gold", "platinum"}
