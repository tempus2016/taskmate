"""Alternating chores move on once per occurrence, not once per day (#1172)."""

from __future__ import annotations

import datetime as dt
from datetime import date, timezone

import pytest

from custom_components.taskmate.coord_assignments import rotation_anchor, rotation_steps
from custom_components.taskmate.models import Child, Chore

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


def _picks(coord, chore, days):
    names = {c: i for i, c in enumerate(chore.assigned_to)}
    return [names[coord._compute_active_children(chore, d)[0]] for d in days]


def _alt(kids, **kw):
    return Chore(
        name="Job",
        assigned_to=[k.id for k in kids],
        assignment_mode="alternating",
        assignment_rotation_anchor=MONDAY.isoformat(),
        **kw,
    )


def test_daily_chore_still_moves_every_day():
    kids = _kids(2)
    chore = _alt(kids)
    days = [MONDAY + dt.timedelta(days=i) for i in range(4)]
    assert _picks(_coord(kids), chore, days) == [0, 1, 0, 1]


def test_every_2_days_with_two_children_alternates():
    kids = _kids(2)
    chore = _alt(kids, schedule_mode="recurring", recurrence="every_2_days")
    days = [MONDAY + dt.timedelta(days=2 * i) for i in range(4)]
    assert _picks(_coord(kids), chore, days) == [0, 1, 0, 1]


def test_weekly_with_seven_children_reaches_everyone():
    kids = _kids(7)
    chore = _alt(kids, schedule_mode="recurring", recurrence="weekly", recurrence_day="monday")
    days = [MONDAY + dt.timedelta(weeks=i) for i in range(8)]
    assert _picks(_coord(kids), chore, days) == [0, 1, 2, 3, 4, 5, 6, 0]


def test_weekly_due_day_differs_from_anchor_weekday():
    kids = _kids(2)
    # Anchored on a Monday, due on Thursdays: each Thursday is a new turn.
    chore = _alt(kids, schedule_mode="recurring", recurrence="weekly", recurrence_day="thursday")
    days = [MONDAY + dt.timedelta(days=3 + 7 * i) for i in range(4)]
    assert _picks(_coord(kids), chore, days) == [0, 1, 0, 1]


def test_specific_days_counts_only_chosen_weekdays():
    kids = _kids(2)
    chore = _alt(kids, due_days=["monday", "wednesday", "friday"])
    # Mon, Wed, Fri, Mon — used to be A, A, A, B (day counts 0, 2, 4, 7).
    days = [MONDAY, MONDAY + dt.timedelta(days=2), MONDAY + dt.timedelta(days=4), MONDAY + dt.timedelta(days=7)]
    assert _picks(_coord(kids), chore, days) == [0, 1, 0, 1]


def test_monthly_moves_once_a_month():
    kids = _kids(3)
    chore = _alt(kids, schedule_mode="recurring", recurrence="monthly")
    days = [date(2026, 4, 20), date(2026, 5, 20), date(2026, 6, 20), date(2026, 7, 20)]
    assert _picks(_coord(kids), chore, days) == [0, 1, 2, 0]


def test_steps_are_symmetric_before_the_anchor():
    chore = Chore(name="x", due_days=["monday", "thursday"])
    later = MONDAY + dt.timedelta(days=10)
    assert rotation_steps(chore, MONDAY, later) == -rotation_steps(chore, later, MONDAY) == 3


def test_missing_anchor_still_rotates():
    kids = _kids(2)
    chore = Chore(name="Bins", assigned_to=[k.id for k in kids], assignment_mode="alternating")
    days = [MONDAY + dt.timedelta(days=i) for i in range(4)]
    assert _picks(_coord(kids), chore, days) == [0, 1, 0, 1]
    assert rotation_anchor(chore) == rotation_anchor(Chore(name="other"))


def test_add_chore_without_start_child_stamps_today():
    kids = _kids(2)
    coord = _coord(kids)
    dt_util_mock._now = dt.datetime.combine(MONDAY, dt.time(12, 0), tzinfo=timezone.utc)
    chore = run_async(
        coord.async_add_chore(name="Bins", assigned_to=[k.id for k in kids], assignment_mode="alternating")
    )
    assert chore.assignment_rotation_anchor == MONDAY.isoformat()
    assert chore.assignment_current_child_id == kids[0].id


def test_switching_to_alternating_stamps_today_but_edits_keep_the_anchor():
    kids = _kids(2)
    coord = _coord(kids)
    dt_util_mock._now = dt.datetime.combine(MONDAY, dt.time(12, 0), tzinfo=timezone.utc)
    added = run_async(coord.async_add_chore(name="Dog", assigned_to=[k.id for k in kids]))
    chore = Chore.from_dict(added.to_dict())  # an edit arrives as a fresh object
    chore.assignment_mode = "alternating"
    run_async(coord.async_update_chore(chore))
    assert chore.assignment_rotation_anchor == MONDAY.isoformat()

    # A legacy alternating chore with no anchor is left alone by an edit.
    legacy = Chore(name="Legacy", assigned_to=[k.id for k in kids], assignment_mode="alternating")
    coord.storage.add_chore(legacy)
    edited = Chore.from_dict(legacy.to_dict())
    edited.points = 20
    run_async(coord.async_update_chore(edited))
    assert edited.assignment_rotation_anchor == ""
