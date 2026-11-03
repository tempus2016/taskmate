"""Alternating chores can stay with one child for a week or a month (#1171)."""

from __future__ import annotations

import datetime as dt
from datetime import date, timezone

import pytest
import voluptuous as vol

from custom_components.taskmate import chore_services as cs
from custom_components.taskmate.coord_assignments import rotation_period_steps
from custom_components.taskmate.models import Child, Chore, TaskGroup

from .conftest import dt_util_mock, run_async
from .test_assignment_modes import _coord

MONDAY = date(2026, 4, 20)


@pytest.fixture(autouse=True)
def _restore_clock():
    saved = dt_util_mock._now
    yield
    dt_util_mock._now = saved


def _kids(n):
    return [Child(name=chr(ord("A") + i)) for i in range(n)]


def _alt(kids, anchor=MONDAY, **kw):
    return Chore(
        name="Dog",
        assigned_to=[k.id for k in kids],
        assignment_mode="alternating",
        assignment_rotation_anchor=anchor.isoformat(),
        **kw,
    )


def _pick(coord, chore, day):
    return chore.assigned_to.index(coord._compute_active_children(chore, day)[0])


def test_no_period_keeps_the_old_rotation():
    chore = _alt(_kids(3))
    assert rotation_period_steps(chore, MONDAY, MONDAY + dt.timedelta(days=5)) is None


def test_daily_chore_stays_with_one_child_all_week():
    kids = _kids(3)
    coord = _coord(kids)
    chore = _alt(kids, assignment_rotation_period="week")
    week = [_pick(coord, chore, MONDAY + dt.timedelta(days=i)) for i in range(21)]
    assert week == [0] * 7 + [1] * 7 + [2] * 7
    assert _pick(coord, chore, MONDAY + dt.timedelta(weeks=3)) == 0


def test_weekly_handover_day_other_than_the_anchor_weekday():
    kids = _kids(2)
    coord = _coord(kids)
    # Anchored on a Monday, handing over on Saturdays: Mon–Fri is the first
    # (partial) turn, then each Saturday starts the next child's week.
    chore = _alt(kids, assignment_rotation_period="week", assignment_rotation_weekday="saturday")
    picks = [_pick(coord, chore, MONDAY + dt.timedelta(days=i)) for i in range(14)]
    assert picks == [0] * 5 + [1] * 7 + [0] * 2


def test_every_two_weeks():
    kids = _kids(2)
    coord = _coord(kids)
    chore = _alt(kids, assignment_rotation_period="week", assignment_rotation_every=2)
    picks = [_pick(coord, chore, MONDAY + dt.timedelta(weeks=w)) for w in range(6)]
    assert picks == [0, 0, 1, 1, 0, 0]


def test_monthly_handover_on_a_day_of_the_month():
    kids = _kids(3)
    coord = _coord(kids)
    chore = _alt(kids, anchor=date(2026, 1, 1), assignment_rotation_period="month", assignment_rotation_month_day=15)
    days = [date(2026, 1, 1), date(2026, 1, 14), date(2026, 1, 15), date(2026, 2, 14), date(2026, 2, 15)]
    # 1 Jan sits in the period that began 15 Dec, so 15 Jan is the first handover.
    assert [_pick(coord, chore, d) for d in days] == [0, 0, 1, 1, 2]


def test_monthly_handover_on_the_31st_uses_the_last_day_of_short_months():
    kids = _kids(2)
    coord = _coord(kids)
    chore = _alt(kids, anchor=date(2026, 1, 31), assignment_rotation_period="month", assignment_rotation_month_day=31)
    assert _pick(coord, chore, date(2026, 2, 27)) == 0
    assert _pick(coord, chore, date(2026, 2, 28)) == 1
    assert _pick(coord, chore, date(2026, 3, 30)) == 1
    assert _pick(coord, chore, date(2026, 3, 31)) == 0


def test_weekly_period_works_before_the_anchor():
    chore = _alt(_kids(2), assignment_rotation_period="week")
    assert rotation_period_steps(chore, MONDAY, MONDAY - dt.timedelta(days=1)) == -1


def test_skip_moves_only_today():
    kids = _kids(3)
    coord = _coord(kids)
    chore = _alt(kids, assignment_rotation_period="week")
    wed = MONDAY + dt.timedelta(days=2)
    chore.skip_date, chore.skip_count = wed.isoformat(), 1
    assert _pick(coord, chore, wed) == 1
    assert _pick(coord, chore, wed + dt.timedelta(days=1)) == 0


def test_round_trips_through_storage_and_old_chores_default_to_no_period():
    chore = _alt(
        _kids(2), assignment_rotation_period="month", assignment_rotation_every=2, assignment_rotation_month_day=9
    )
    back = Chore.from_dict(chore.to_dict())
    assert (back.assignment_rotation_period, back.assignment_rotation_every, back.assignment_rotation_month_day) == (
        "month",
        2,
        9,
    )
    legacy = Chore.from_dict({"name": "Old"})
    assert legacy.assignment_rotation_period == ""
    assert legacy.assignment_rotation_every == 1
    assert legacy.assignment_rotation_weekday == "monday"


def test_setting_a_period_without_an_anchor_starts_today():
    kids = _kids(2)
    coord = _coord(kids)
    dt_util_mock._now = dt.datetime.combine(MONDAY, dt.time(12, 0), tzinfo=timezone.utc)
    added = run_async(
        coord.async_add_chore(name="Dog", assigned_to=[k.id for k in kids], assignment_mode="alternating")
    )
    chore = Chore.from_dict(added.to_dict())
    chore.assignment_rotation_period = "week"
    run_async(coord.async_update_chore(chore))
    assert chore.assignment_rotation_anchor == MONDAY.isoformat()


def test_service_schema_accepts_and_normalises_the_period():
    out = vol.Schema(cs.UPDATE_FIELDS)(
        {
            "chore_id": "c",
            "assignment_rotation_period": "Week",
            "assignment_rotation_every": "2",
            "assignment_rotation_weekday": "Sunday",
            "assignment_rotation_month_day": "31",
        }
    )
    assert out["assignment_rotation_period"] == "week"
    assert out["assignment_rotation_every"] == 2
    assert out["assignment_rotation_weekday"] == "sunday"
    assert out["assignment_rotation_month_day"] == 31
    each = vol.Schema(cs.UPDATE_FIELDS)({"chore_id": "c", "assignment_rotation_period": "each_time"})
    assert each["assignment_rotation_period"] == ""


@pytest.mark.parametrize(
    "data",
    [
        {"assignment_rotation_period": "fortnight"},
        {"assignment_rotation_every": 0},
        {"assignment_rotation_every": 13},
        {"assignment_rotation_weekday": "someday"},
        {"assignment_rotation_month_day": 32},
    ],
)
def test_service_schema_refuses_bad_values(data):
    with pytest.raises(vol.Invalid):
        vol.Schema(cs.UPDATE_FIELDS)({"chore_id": "c", **data})


def test_spread_group_of_weekly_chores_gives_each_child_a_different_job_all_week():
    """The #1171 family: dog (daily), bins (Mondays), house (daily), swapped weekly."""
    kids = _kids(3)
    coord = _coord(kids)
    jobs = [
        _alt(kids, assignment_rotation_period="week"),
        _alt(kids, assignment_rotation_period="week", due_days=["monday"]),
        _alt(kids, assignment_rotation_period="week"),
    ]
    for job in jobs:
        coord.storage.add_chore(job)
    coord.storage.add_task_group(TaskGroup(name="Jobs", policy="spread", chore_ids=[j.id for j in jobs]))
    by_week = []
    for week in range(3):
        days = {
            tuple(coord._compute_daily_assignments(MONDAY + dt.timedelta(weeks=week, days=d))[j.id] for j in jobs)
            for d in range(7)
        }
        assert len(days) == 1  # the same split every day of the week
        split = days.pop()
        assert len(set(split)) == 3  # everyone has a different job
        by_week.append(split)
    assert len(set(by_week)) == 3  # and the jobs change hands each week
