"""A one-off chore dated for another day stays off today's cards (#992).

A one-off chore added from the HA calendar for a date ahead is only available
on that date, but the cards filter today's list from the chores record, which
said nothing about the date. The record now carries ``occ_today: False`` for a
one-off that isn't today's — the same flag every card already honours for a
calendar move — so the cards agree with ``is_chore_available_for_child``.
"""

from __future__ import annotations

import datetime as dt

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore
from custom_components.taskmate.sensor import _build_chores_list
from custom_components.taskmate.storage import TaskMateStorage

from .conftest import dt_util_mock

# 2026-06-22 is a Monday.
MON = dt.date(2026, 6, 22)


@pytest.fixture(autouse=True)
def _clock():
    saved = dt_util_mock._now
    dt_util_mock._now = dt.datetime.combine(MON, dt.time(9, 0), tzinfo=dt.timezone.utc)
    yield
    dt_util_mock._now = saved


async def _coord(hass, chores):
    storage = TaskMateStorage(hass, "oneoff992")
    await storage.async_load()
    storage.add_child(Child(name="Alex", id="alex"))
    for chore in chores:
        storage.add_chore(chore)
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.storage = storage
    coord.data = {}
    return coord


def _records(coord, hass):
    return {r["name"]: r for r in _build_chores_list(coord, {"chores": coord.storage.get_chores(), "hass": hass})}


def _one_off(name, created_date, **kw):
    return Chore(name=name, schedule_mode="one_shot", created_date=created_date, assigned_to=["alex"], **kw)


async def test_future_one_off_is_flagged_not_today(hass):
    chore = _one_off("Party", "2026-06-25")
    coord = await _coord(hass, [chore])
    assert coord.is_chore_available_for_child(chore, "alex") is False
    assert _records(coord, hass)["Party"]["occ_today"] is False


async def test_todays_one_off_carries_no_flag(hass):
    chore = _one_off("Party", "2026-06-22")
    coord = await _coord(hass, [chore])
    assert coord.is_chore_available_for_child(chore, "alex") is True
    assert "occ_today" not in _records(coord, hass)["Party"]


async def test_past_one_off_still_enabled_is_flagged(hass):
    # Before the midnight sweep switches it off, yesterday's one-off is
    # already unavailable; the card must not offer it either.
    chore = _one_off("Party", "2026-06-21")
    coord = await _coord(hass, [chore])
    assert coord.is_chore_available_for_child(chore, "alex") is False
    assert _records(coord, hass)["Party"]["occ_today"] is False


async def test_flag_stays_off_where_it_costs_bytes_for_nothing(hass):
    # Disabled one-offs are dropped by every card already; undated ones and
    # an unparsable date read as available on the backend, so they stay so.
    disabled = _one_off("Old", "2026-06-01", enabled=False)
    undated = _one_off("Undated", "")
    garbled = _one_off("Garbled", "not-a-date")
    weekly = Chore(name="Bins", due_days=["monday"], created_date="2026-06-01")
    coord = await _coord(hass, [disabled, undated, garbled, weekly])
    records = _records(coord, hass)
    for name in ("Old", "Undated", "Garbled", "Bins"):
        assert "occ_today" not in records[name], name
    assert coord.is_chore_available_for_child(garbled, "alex") is True
    assert coord.is_chore_available_for_child(undated, "alex") is True


async def test_record_agrees_with_backend_availability_across_dates(hass):
    chores = [_one_off(f"D{d}", (MON + dt.timedelta(days=d)).isoformat()) for d in range(-3, 8)]
    coord = await _coord(hass, chores)
    records = _records(coord, hass)
    for chore in chores:
        on_card = records[chore.name].get("occ_today", True) is not False
        assert on_card is coord.is_chore_available_for_child(chore, "alex"), chore.name
