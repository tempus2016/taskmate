"""A won auction occurrence shows the winning price before its day (#998).

The override was only read for today, so a future won occurrence showed the
chore's normal points on the HA calendar entity, the ICS feed and the calendar
card until the day itself. Every place that projects that occurrence's points
must price it at the winning bid — for the winner, the only child it lands on.
"""

from __future__ import annotations

import asyncio
import datetime as dt

import pytest

from custom_components.taskmate import calendar as cal_module
from custom_components.taskmate import ics as ics_module
from custom_components.taskmate import sensor as sensor_module

from .conftest import dt_util_mock
from .test_chore_auctions import CLOSES, NOW, TOMORROW, _chore, _coord

DAY = dt.date.fromisoformat(TOMORROW)


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _clock():
    saved = dt_util_mock._now
    dt_util_mock._now = NOW
    yield
    dt_util_mock._now = saved


def _won(price=9):
    """Vaiha (k2) wins tomorrow's 6-point bathroom for ``price``."""
    coord = _coord([_chore(points=6)])
    auction = run(coord.async_start_auction("c1", TOMORROW, 40, CLOSES))
    run(coord.async_place_bid(auction.id, "k2", price))
    run(coord.async_close_auction(auction.id))
    return coord


def _calendar_events(coord, child_id):
    entity = cal_module.TaskMateCalendar.__new__(cal_module.TaskMateCalendar)
    entity.coordinator = coord
    child = coord.storage.get_child(child_id)
    return entity._build_events(child, NOW.date(), DAY)


def _on(events, day):
    return [e for e in events if (e.start if isinstance(e.start, dt.date) else e.start.date()) == day]


def test_the_calendar_entity_prices_the_won_day_at_the_winning_bid():
    coord = _won()
    events = _calendar_events(coord, "k2")
    [won] = _on(events, DAY)
    assert won.description == "TaskMate chore · 9 pts"
    # Today is not won, so it keeps the chore's normal points.
    [today] = _on(events, NOW.date())
    assert today.description == "TaskMate chore · 6 pts"


def test_the_calendar_entity_gives_the_won_day_to_nobody_else():
    coord = _won()
    assert _on(_calendar_events(coord, "k1"), DAY) == []


def test_the_ics_feed_prices_the_won_day_at_the_winning_bid():
    coord = _won()
    events = ics_module.build_chore_events(coord, NOW.date(), DAY)
    won = [e for e in events if e["start"] == DAY]
    assert [e["summary"] for e in won] == ["Clean the bathroom — Vaiha"]
    assert won[0]["description"] == "TaskMate chore · 9 pts"
    today = [e for e in events if e["start"] == NOW.date()]
    assert today and all(e["description"] == "TaskMate chore · 6 pts" for e in today)


def test_the_chores_slice_carries_the_price_of_each_won_day():
    coord = _won()
    data = {"chores": coord.storage.get_chores(), "children": coord.storage.get_children()}
    coord.data = data
    common = {"chores": data["chores"], "hass": coord.hass}
    record = {c["id"]: c for c in sensor_module._build_chores_list(coord, common)}["c1"]
    assert record["auction_wins"] == {TOMORROW: "k2"}
    assert record["auction_prices"] == {TOMORROW: 9}
    # Not today's price: the chore still pays its normal points today.
    assert "effective_points" not in record or record["effective_points"] == 6


def test_an_ordinary_chore_carries_no_prices():
    coord = _coord([_chore(points=6)])
    coord.data = {"chores": coord.storage.get_chores(), "children": coord.storage.get_children()}
    common = {"chores": coord.data["chores"], "hass": coord.hass}
    record = sensor_module._build_chores_list(coord, common)[0]
    assert "auction_prices" not in record
