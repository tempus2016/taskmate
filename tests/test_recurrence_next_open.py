"""When a recurring chore in its cooldown opens again (#771).

The child card said "every 3 days" — the raw recurrence key, in English, in
every language — and nothing about when the chore comes back. The backend now
works out the next open day from the same window maths as availability, and
publishes it on the availability sensor as ``chore_next_open``.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import patch

from custom_components.taskmate import sensor as sensor_mod
from custom_components.taskmate.models import Chore

from .test_completion_eligibility import _make_system, _now, run

TODAY = _now().date()  # 2024-03-20, a Wednesday


def _at():
    return patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=_now())


def _system():
    coord, storage, mod = _make_system()
    with patch.object(mod.dt_util, "now", return_value=_now()):
        kid = run(coord.async_add_child("Vaiha"))
    return coord, storage, kid


def _recurring(storage, **fields):
    chore = Chore(name="Water plants", schedule_mode="recurring", **fields)
    storage.add_chore(chore)
    return chore


def test_a_rolling_window_opens_n_days_after_the_last_completion():
    coord, storage, kid = _system()
    chore = _recurring(storage, recurrence="every_3_days")
    storage.set_last_completed(chore.id, kid.id, _now().isoformat())
    with _at():
        assert coord.recurrence_next_open(chore, kid.id) == TODAY + dt.timedelta(days=3)


def test_an_anchored_chore_opens_on_its_start_date():
    coord, storage, kid = _system()
    chore = _recurring(storage, recurrence="every_3_days", recurrence_start=(TODAY + dt.timedelta(days=2)).isoformat())
    with _at():
        assert coord.recurrence_next_open(chore, kid.id) == TODAY + dt.timedelta(days=2)


def test_monthly_counts_calendar_months():
    coord, storage, kid = _system()
    chore = _recurring(storage, recurrence="monthly")
    storage.set_last_completed(chore.id, kid.id, _now().isoformat())
    with _at():
        assert coord.recurrence_next_open(chore, kid.id) == dt.date(2024, 4, 20)


def test_open_today_or_not_recurring_has_no_next_day():
    coord, storage, kid = _system()
    open_now = _recurring(storage, recurrence="every_3_days")
    daily = Chore(name="Teeth", schedule_mode="specific_days")
    storage.add_chore(daily)
    with _at():
        assert coord.recurrence_next_open(open_now, kid.id) is None
        assert coord.recurrence_next_open(daily, kid.id) is None


def test_the_availability_sensor_publishes_it_only_for_locked_chores():
    coord, storage, kid = _system()
    locked = _recurring(storage, recurrence="every_3_days")
    storage.set_last_completed(locked.id, kid.id, _now().isoformat())
    open_now = _recurring(storage, recurrence="every_2_weeks")
    common = {"chores": [locked, open_now], "children": [kid]}
    availability = {locked.id: {kid.id: False}, open_now.id: {kid.id: True}}
    with _at():
        out = sensor_mod._build_chore_next_open(coord, common, availability)
    assert out == {locked.id: {kid.id: (TODAY + dt.timedelta(days=3)).isoformat()}}


def test_availability_still_agrees_with_the_window():
    """The refactor that let next-open ask about future days must not change today's answer."""
    coord, storage, kid = _system()
    chore = _recurring(storage, recurrence="every_3_days")
    storage.set_last_completed(chore.id, kid.id, (_now() - dt.timedelta(days=1)).isoformat())
    with _at():
        assert coord.is_chore_available_for_child(chore, kid.id) is False
    storage.set_last_completed(chore.id, kid.id, (_now() - dt.timedelta(days=3)).isoformat())
    with _at():
        assert coord.is_chore_available_for_child(chore, kid.id) is True
