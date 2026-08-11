"""Tests for custom time-of-day periods (#391).

Covers the coordinator resolver fallback chain (time_periods setting →
legacy flat keys → defaults) and the websocket payload validation,
including the block-on-delete rule for periods still used by chores.
"""

from __future__ import annotations

from datetime import time
from unittest.mock import MagicMock

from custom_components.taskmate.models import Child, Chore
from custom_components.taskmate.websocket import _validate_time_periods

from .test_assignment_modes import _coord

# ---------------------------------------------------------------------------
# Resolver: coordinator.get_time_periods()
# ---------------------------------------------------------------------------


def test_resolver_defaults_when_no_settings():
    coord = _coord([Child(name="A")])
    periods = coord.get_time_periods()
    assert [p["id"] for p in periods] == ["morning", "afternoon", "evening", "night"]
    assert periods[0]["start"] == "06:00"
    assert periods[-1]["end"] == "23:59"
    assert periods[0]["icon"] == "mdi:weather-sunny"


def test_resolver_legacy_flat_keys_preserved():
    coord = _coord([Child(name="A")])
    coord.storage.set_setting("time_morning_start", "05:30")
    coord.storage.set_setting("time_morning_end", "11:00")
    periods = coord.get_time_periods()
    morning = next(p for p in periods if p["id"] == "morning")
    assert morning["start"] == "05:30"
    assert morning["end"] == "11:00"


def test_resolver_time_periods_setting_wins_and_sorts():
    coord = _coord([Child(name="A")])
    coord.storage.set_setting(
        "time_periods",
        [
            {"id": "night", "label": "", "start": "21:00", "end": "23:59", "icon": "mdi:weather-night"},
            {"id": "school_run", "label": "School run", "start": "08:00", "end": "09:00", "icon": "mdi:school"},
        ],
    )
    periods = coord.get_time_periods()
    assert [p["id"] for p in periods] == ["school_run", "night"]
    assert periods[0]["label"] == "School run"


def test_resolver_skips_garbage_entries():
    coord = _coord([Child(name="A")])
    coord.storage.set_setting(
        "time_periods",
        [
            "not-a-dict",
            {"id": "anytime", "start": "01:00", "end": "02:00"},  # reserved id
            {"id": "ok", "label": "OK", "start": "10:00", "end": "11:00", "icon": ""},
            {"id": "bad_time", "label": "Bad", "start": "xx:yy", "end": "11:00"},
        ],
    )
    periods = coord.get_time_periods()
    assert [p["id"] for p in periods] == ["ok"]
    assert periods[0]["icon"] == "mdi:clock-outline"  # empty icon falls back


def test_boundaries_built_from_periods():
    coord = _coord([Child(name="A")])
    coord.storage.set_setting(
        "time_periods",
        [
            {"id": "school_run", "label": "School run", "start": "08:00", "end": "09:15", "icon": "mdi:school"},
        ],
    )
    boundaries = coord._get_time_boundaries()
    assert boundaries["anytime"] is None
    assert boundaries["school_run"] == (time(8, 0), time(9, 15))


def test_time_category_window_for_custom_period():
    from datetime import date

    coord = _coord([Child(name="A")])
    coord.storage.set_setting(
        "time_periods",
        [
            {"id": "school_run", "label": "School run", "start": "08:00", "end": "09:15", "icon": "mdi:school"},
        ],
    )
    window = coord._time_category_window("school_run", date(2026, 6, 11))
    assert window is not None
    start, end = window
    assert (start.hour, start.minute) == (8, 0)
    assert (end.hour, end.minute) == (9, 15)
    assert coord._time_category_window("anytime", date(2026, 6, 11)) is None


# ---------------------------------------------------------------------------
# Validation: websocket._validate_time_periods()
# ---------------------------------------------------------------------------


def _valid_payload():
    return [
        {"id": "morning", "label": "", "start": "06:00", "end": "12:00", "icon": "mdi:weather-sunny"},
        {"id": "afternoon", "label": "", "start": "12:00", "end": "17:00", "icon": ""},
        {"label": "School run", "start": "05:00", "end": "06:00", "icon": "mdi:school"},
    ]


def test_validate_accepts_and_normalizes():
    coord = _coord([Child(name="A")])
    periods, err = _validate_time_periods(_valid_payload(), coord)
    assert err is None
    # Sorted by start: school_run first
    assert [p["id"] for p in periods] == ["school_run", "morning", "afternoon"]
    # Missing id generated from label
    assert periods[0]["id"] == "school_run"
    # Empty icon falls back to the built-in map
    assert periods[2]["icon"] == "mdi:white-balance-sunny"


def test_validate_rejects_overlap():
    coord = _coord([Child(name="A")])
    payload = [
        {"id": "morning", "label": "", "start": "06:00", "end": "12:00"},
        {"label": "Brunch", "start": "11:00", "end": "13:00"},
    ]
    periods, err = _validate_time_periods(payload, coord)
    assert periods is None
    assert "overlap" in err.lower()


def test_validate_allows_gaps():
    coord = _coord([Child(name="A")])
    payload = [
        {"id": "morning", "label": "", "start": "06:00", "end": "08:00"},
        {"label": "Bedtime", "start": "20:00", "end": "21:00"},
    ]
    periods, err = _validate_time_periods(payload, coord)
    assert err is None
    assert len(periods) == 2


def test_validate_rejects_start_after_end():
    coord = _coord([Child(name="A")])
    periods, err = _validate_time_periods([{"label": "Backwards", "start": "10:00", "end": "09:00"}], coord)
    assert periods is None and "start before" in err


def test_validate_rejects_bad_time_format():
    coord = _coord([Child(name="A")])
    periods, err = _validate_time_periods([{"label": "Bad", "start": "25:00", "end": "26:00"}], coord)
    assert periods is None and "HH:MM" in err


def test_validate_rejects_blank_custom_label():
    coord = _coord([Child(name="A")])
    periods, err = _validate_time_periods([{"label": "  ", "start": "10:00", "end": "11:00"}], coord)
    assert periods is None and "name" in err


def test_validate_rejects_duplicate_ids():
    coord = _coord([Child(name="A")])
    payload = [
        {"id": "x", "label": "One", "start": "06:00", "end": "07:00"},
        {"id": "x", "label": "Two", "start": "08:00", "end": "09:00"},
    ]
    periods, err = _validate_time_periods(payload, coord)
    assert periods is None and "duplicate" in err


def test_validate_rejects_empty_list():
    coord = _coord([Child(name="A")])
    periods, err = _validate_time_periods([], coord)
    assert periods is None


def test_validate_slug_collision_gets_suffix():
    coord = _coord([Child(name="A")])
    payload = [
        {"label": "Quiet Time", "start": "06:00", "end": "07:00"},
        {"label": "Quiet time!", "start": "08:00", "end": "09:00"},
    ]
    periods, err = _validate_time_periods(payload, coord)
    assert err is None
    ids = {p["id"] for p in periods}
    assert ids == {"quiet_time", "quiet_time_2"}


def test_validate_blocks_deleting_period_in_use():
    coord = _coord([Child(name="A")])
    coord.storage.get_chores = MagicMock(
        return_value=[
            Chore(name="Brush teeth", time_category="night"),
        ]
    )
    # Payload drops the built-in "night" period
    payload = [{"id": "morning", "label": "", "start": "06:00", "end": "12:00"}]
    periods, err = _validate_time_periods(payload, coord)
    assert periods is None
    assert "Brush teeth" in err


def test_validate_allows_deleting_unused_period():
    coord = _coord([Child(name="A")])
    coord.storage.get_chores = MagicMock(
        return_value=[
            Chore(name="Brush teeth", time_category="anytime"),
        ]
    )
    payload = [{"id": "morning", "label": "", "start": "06:00", "end": "12:00"}]
    periods, err = _validate_time_periods(payload, coord)
    assert err is None
    assert [p["id"] for p in periods] == ["morning"]
