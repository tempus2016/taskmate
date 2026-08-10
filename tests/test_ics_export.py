"""Tests for ICS calendar export (FEAT-10)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from custom_components.taskmate import ics
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc
NOW = datetime(2026, 4, 1, 8, 0, 0, tzinfo=UTC)


def test_escape_special_chars():
    assert ics._escape("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"


def test_fold_long_line():
    folded = ics._fold("SUMMARY:" + "x" * 200)
    for physical in folded.split("\r\n"):
        assert len(physical.encode("utf-8")) <= 75 or physical.startswith(" ")
    assert folded.replace("\r\n ", "") == "SUMMARY:" + "x" * 200


def test_make_uid_stable_and_scoped():
    a = ics.make_uid("chore1", "kid1", "2026-04-01", "allday")
    b = ics.make_uid("chore1", "kid1", "2026-04-01", "allday")
    c = ics.make_uid("chore1", "kid2", "2026-04-01", "allday")
    assert a == b and a != c and a.endswith("@taskmate")


def test_build_calendar_allday_and_timed():
    events = [
        {
            "uid": "u1@taskmate",
            "summary": "Dishes — Alex",
            "description": "d",
            "start": date(2026, 4, 1),
            "end": date(2026, 4, 2),
            "all_day": True,
        },
        {
            "uid": "u2@taskmate",
            "summary": "Walk, dog",
            "description": "",
            "start": datetime(2026, 4, 1, 17, 0, tzinfo=UTC),
            "end": datetime(2026, 4, 1, 18, 0, tzinfo=UTC),
            "all_day": False,
        },
    ]
    out = ics.build_calendar(events, NOW)
    assert out.startswith("BEGIN:VCALENDAR\r\n")
    assert out.endswith("END:VCALENDAR\r\n")
    assert out.count("BEGIN:VEVENT") == 2
    assert "DTSTART;VALUE=DATE:20260401" in out
    assert "DTEND;VALUE=DATE:20260402" in out
    assert "DTSTART:20260401T170000Z" in out
    assert "SUMMARY:Walk\\, dog" in out  # comma escaped
    assert "UID:u1@taskmate" in out
    assert "DTSTAMP:20260401T080000Z" in out


def test_empty_calendar_has_no_events():
    out = ics.build_calendar([], NOW)
    assert "BEGIN:VEVENT" not in out
    assert "BEGIN:VCALENDAR" in out and "END:VCALENDAR" in out


@pytest.mark.asyncio
async def test_token_create_is_stable_then_regenerates(hass):
    storage = TaskMateStorage(hass, "ics")
    await storage.async_load()
    coord = object.__new__(TaskMateCoordinator)
    coord.storage = storage
    t1 = await coord.async_get_or_create_ics_token()
    assert t1 and storage.get_setting("ics_token") == t1
    t2 = await coord.async_get_or_create_ics_token()
    assert t2 == t1  # stable
    t3 = await coord.async_regenerate_ics_token()
    assert t3 and t3 != t1
    assert storage.get_setting("ics_token") == t3
