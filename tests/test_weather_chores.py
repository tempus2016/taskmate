"""Weather-aware chores (#673).

The gate lives in ``is_chore_available_for_child`` so a rained-off chore also
stops counting as a mandatory miss and can't break a streak. Every path is
fail-open: a broken weather integration must never hide the family's chores.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.taskmate.models import Chore, optional_float

from .test_coordinator_logic import _make_coord


def _weather_state(condition="sunny", temperature=None, wind_speed=None):
    """A stand-in for a weather.* state object."""
    attrs = {}
    if temperature is not None:
        attrs["temperature"] = temperature
    if wind_speed is not None:
        attrs["wind_speed"] = wind_speed
    state = MagicMock()
    state.state = condition
    state.attributes = attrs
    return state


def _coord_with_weather(state):
    coord = _make_coord()
    coord.hass.states.get = MagicMock(return_value=state)
    return coord


def _chore(**kwargs):
    return Chore(name="Mow the lawn", weather_entity="weather.home", **kwargs)


class TestOptionalFloat:
    """0 is a real threshold, so it can't double as the "unset" sentinel."""

    @pytest.mark.parametrize("value", [None, "", "abc", [], {}])
    def test_unset_values_read_as_none(self, value):
        assert optional_float(value) is None

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0, 0.0),
            ("0", 0.0),
            (-5, -5.0),
            ("12.5", 12.5),
            (3, 3.0),
        ],
    )
    def test_numeric_values_survive(self, value, expected):
        assert optional_float(value) == expected


class TestWeatherBlockReason:
    def test_no_entity_configured_never_blocks(self):
        coord = _coord_with_weather(_weather_state("pouring"))
        chore = Chore(name="Wash up", weather_block_conditions=["pouring"])
        assert coord.weather_block_reason(chore) is None

    def test_blocking_condition_matches(self):
        coord = _coord_with_weather(_weather_state("pouring"))
        chore = _chore(weather_block_conditions=["rainy", "pouring"])
        assert coord.weather_block_reason(chore) == coord.WEATHER_REASON_CONDITION

    def test_non_blocking_condition_passes(self):
        coord = _coord_with_weather(_weather_state("sunny"))
        chore = _chore(weather_block_conditions=["rainy", "pouring"])
        assert coord.weather_block_reason(chore) is None

    def test_condition_match_is_case_insensitive(self):
        coord = _coord_with_weather(_weather_state("Rainy"))
        chore = _chore(weather_block_conditions=["rainy"])
        assert coord.weather_block_reason(chore) == coord.WEATHER_REASON_CONDITION

    def test_no_limits_set_never_blocks(self):
        coord = _coord_with_weather(_weather_state("pouring", temperature=-10, wind_speed=99))
        assert coord.weather_block_reason(_chore()) is None

    def test_temperature_below_minimum(self):
        coord = _coord_with_weather(_weather_state(temperature=2))
        chore = _chore(weather_temp_min=5)
        assert coord.weather_block_reason(chore) == coord.WEATHER_REASON_TEMP_LOW

    def test_temperature_at_minimum_is_allowed(self):
        coord = _coord_with_weather(_weather_state(temperature=5))
        assert coord.weather_block_reason(_chore(weather_temp_min=5)) is None

    def test_zero_minimum_still_applies(self):
        """A 0 °C threshold is real config, not "no threshold"."""
        coord = _coord_with_weather(_weather_state(temperature=-1))
        assert coord.weather_block_reason(_chore(weather_temp_min=0)) == coord.WEATHER_REASON_TEMP_LOW

    def test_temperature_above_maximum(self):
        coord = _coord_with_weather(_weather_state(temperature=31))
        chore = _chore(weather_temp_max=30)
        assert coord.weather_block_reason(chore) == coord.WEATHER_REASON_TEMP_HIGH

    def test_wind_above_maximum(self):
        coord = _coord_with_weather(_weather_state(wind_speed=45))
        chore = _chore(weather_wind_max=30)
        assert coord.weather_block_reason(chore) == coord.WEATHER_REASON_WIND

    def test_wind_at_maximum_is_allowed(self):
        coord = _coord_with_weather(_weather_state(wind_speed=30))
        assert coord.weather_block_reason(_chore(weather_wind_max=30)) is None

    def test_condition_takes_precedence_over_limits(self):
        coord = _coord_with_weather(_weather_state("pouring", temperature=-5, wind_speed=99))
        chore = _chore(
            weather_block_conditions=["pouring"],
            weather_temp_min=0,
            weather_wind_max=20,
        )
        assert coord.weather_block_reason(chore) == coord.WEATHER_REASON_CONDITION


class TestWeatherFailsOpen:
    """A missing or broken weather entity must never hide a chore."""

    def test_missing_entity(self):
        coord = _coord_with_weather(None)
        chore = _chore(weather_block_conditions=["rainy"], weather_temp_min=5)
        assert coord.weather_block_reason(chore) is None

    @pytest.mark.parametrize("state", ["unavailable", "unknown", ""])
    def test_unusable_state(self, state):
        coord = _coord_with_weather(_weather_state(state))
        chore = _chore(weather_block_conditions=[state, "rainy"], weather_temp_min=5)
        assert coord.weather_block_reason(chore) is None

    def test_missing_temperature_attribute(self):
        coord = _coord_with_weather(_weather_state("sunny"))
        assert coord.weather_block_reason(_chore(weather_temp_min=5)) is None

    def test_non_numeric_temperature_attribute(self):
        coord = _coord_with_weather(_weather_state("sunny", temperature="n/a"))
        assert coord.weather_block_reason(_chore(weather_temp_min=5)) is None

    def test_missing_wind_attribute(self):
        coord = _coord_with_weather(_weather_state("sunny", temperature=12))
        assert coord.weather_block_reason(_chore(weather_wind_max=20)) is None


class TestWeatherGatesAvailability:
    """The gate must sit in the availability path, not just the card."""

    def _available(self, coord, chore):
        coord.storage.get_last_completed = MagicMock(return_value={})
        coord.storage.get_chore = MagicMock(return_value=chore)
        return coord.is_chore_available_for_child(chore, "kid1")

    def test_blocked_chore_is_unavailable(self):
        coord = _coord_with_weather(_weather_state("pouring"))
        chore = _chore(schedule_mode="specific_days", weather_block_conditions=["pouring"])
        assert self._available(coord, chore) is False

    def test_clear_weather_leaves_chore_available(self):
        coord = _coord_with_weather(_weather_state("sunny"))
        chore = _chore(schedule_mode="specific_days", weather_block_conditions=["pouring"])
        assert self._available(coord, chore) is True

    def test_unconfigured_chore_is_unaffected(self):
        coord = _coord_with_weather(_weather_state("pouring"))
        chore = Chore(name="Wash up", schedule_mode="specific_days")
        assert self._available(coord, chore) is True


class TestWeatherRoundTrip:
    def test_fields_survive_to_dict_from_dict(self):
        chore = _chore(
            weather_block_conditions=["rainy", "pouring"],
            weather_temp_min=0,
            weather_temp_max=30,
            weather_wind_max=25,
        )
        restored = Chore.from_dict(chore.to_dict())
        assert restored.weather_entity == "weather.home"
        assert restored.weather_block_conditions == ["rainy", "pouring"]
        assert restored.weather_temp_min == 0
        assert restored.weather_temp_max == 30
        assert restored.weather_wind_max == 25

    def test_legacy_chore_without_weather_fields(self):
        """Chores stored before #673 must load with the gate switched off."""
        restored = Chore.from_dict({"name": "Old chore", "points": 5})
        assert restored.weather_entity == ""
        assert restored.weather_block_conditions == []
        assert restored.weather_temp_min is None
        assert restored.weather_wind_max is None

    def test_string_limits_are_coerced(self):
        """The panel sends numbers, but hand-edited storage may hold strings."""
        restored = Chore.from_dict(
            {
                "name": "Chore",
                "weather_entity": "weather.home",
                "weather_temp_min": "5.5",
                "weather_temp_max": "",
                "weather_wind_max": None,
            }
        )
        assert restored.weather_temp_min == 5.5
        assert restored.weather_temp_max is None
        assert restored.weather_wind_max is None
