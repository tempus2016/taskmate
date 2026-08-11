"""Tests for chore difficulty tiers and their points multiplier.

Difficulty is a per-chore tier (easy/medium/hard). "medium" is the neutral
baseline (×1.0) so pre-existing chores — which default to medium — keep their
exact award value. The multiplier per tier is configurable via settings
(difficulty_multiplier_<tier>); defaults are easy 0.5, medium 1.0, hard 2.0.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Chore


def _make_coord(settings: dict | None = None) -> TaskMateCoordinator:
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.data = {}
    _settings = settings or {}
    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d="": _settings.get(k, d))
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    return coord


class TestDifficultyMultiplier:
    def test_defaults(self):
        coord = _make_coord()
        assert coord.difficulty_multiplier("easy") == 0.5
        assert coord.difficulty_multiplier("medium") == 1.0
        assert coord.difficulty_multiplier("hard") == 2.0

    def test_unknown_tier_falls_back_to_medium_baseline(self):
        coord = _make_coord()
        assert coord.difficulty_multiplier("") == 1.0
        assert coord.difficulty_multiplier("legendary") == 1.0

    def test_settings_override_defaults(self):
        coord = _make_coord(
            {
                "difficulty_multiplier_easy": "0.75",
                "difficulty_multiplier_hard": "3.0",
            }
        )
        assert coord.difficulty_multiplier("easy") == 0.75
        assert coord.difficulty_multiplier("hard") == 3.0
        # Untouched tier keeps its default.
        assert coord.difficulty_multiplier("medium") == 1.0

    def test_malformed_setting_falls_back_to_default(self):
        coord = _make_coord({"difficulty_multiplier_hard": "not-a-number"})
        assert coord.difficulty_multiplier("hard") == 2.0


class TestEffectiveChorePoints:
    def test_medium_is_unchanged(self):
        coord = _make_coord()
        chore = Chore(name="Tidy", points=10, difficulty="medium")
        assert coord.effective_chore_points(chore) == 10

    def test_legacy_chore_without_difficulty_defaults_to_medium(self):
        coord = _make_coord()
        chore = Chore(name="Legacy", points=10)
        assert chore.difficulty == "medium"
        assert coord.effective_chore_points(chore) == 10

    def test_hard_doubles(self):
        coord = _make_coord()
        chore = Chore(name="Mow lawn", points=15, difficulty="hard")
        assert coord.effective_chore_points(chore) == 30

    def test_easy_halves_and_rounds(self):
        coord = _make_coord()
        chore = Chore(name="Feed cat", points=5, difficulty="easy")
        # 5 * 0.5 = 2.5 -> round() -> 2
        assert coord.effective_chore_points(chore) == 2

    def test_custom_multiplier_applies(self):
        coord = _make_coord({"difficulty_multiplier_hard": "1.5"})
        chore = Chore(name="Dishes", points=10, difficulty="hard")
        assert coord.effective_chore_points(chore) == 15

    def test_never_negative(self):
        coord = _make_coord()
        chore = Chore(name="Zero", points=0, difficulty="hard")
        assert coord.effective_chore_points(chore) == 0


class TestDifficultyPersistence:
    def test_round_trips_through_serialization(self):
        chore = Chore(name="Vacuum", points=20, difficulty="hard")
        restored = Chore.from_dict(chore.to_dict())
        assert restored.difficulty == "hard"

    def test_missing_difficulty_in_stored_dict_defaults_to_medium(self):
        data = Chore(name="Old", points=10).to_dict()
        data.pop("difficulty", None)
        restored = Chore.from_dict(data)
        assert restored.difficulty == "medium"
