"""#563: optional 'require ALL daily tasks' rule for streaks and perfect weeks.

Two independent settings:
- streak_requires_all_chores       — streak only advances once every chore
                                      DUE that day is done.
- perfect_week_requires_all_chores — a day counts toward a perfect week only
                                      when every chore due that day is done.

Both default off → today's "any one chore" behaviour is preserved.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, ChoreCompletion

UTC = timezone.utc


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _child(**kw):
    base = dict(name="Mia", id="kid", points=0, total_points_earned=0)
    base.update(kw)
    return Child(**base)


def _comp(chore_id, when, child_id="kid"):
    return ChoreCompletion(chore_id=chore_id, child_id=child_id, completed_at=when,
                           approved=True, points_awarded=5)


def _coord(*, settings=None, chores=None, completions=None, children=None):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    _settings = settings or {}
    _children = children or []
    _by_id = {c.id: c for c in _children}
    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d="": _settings.get(k, d))
    storage.get_chores = MagicMock(return_value=chores or [])
    storage.get_completions = MagicMock(return_value=completions or [])
    storage.get_children = MagicMock(return_value=_children)
    storage.get_child = MagicMock(side_effect=lambda cid: _by_id.get(cid))
    storage.update_child = MagicMock()
    storage.add_points_transaction = MagicMock()
    storage.append_career_score_snapshot = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    coord._maybe_level_up = AsyncMock()
    coord._celebrate = AsyncMock()
    coord.badges = None
    return coord


def _award(coord, child, *, chore_id, now):
    import custom_components.taskmate.coord_points as _mod
    with patch.object(_mod.dt_util, "now", return_value=now):
        return run(coord._award_points(child, 10, chore_id=chore_id))


NOW = dt.datetime(2024, 3, 20, 12, 0, tzinfo=UTC)
ALL = {"streak_requires_all_chores": "true"}


# ── Streak: all-chores mode ───────────────────────────────────────────────

def test_all_mode_streak_waits_until_all_chores_done():
    chores = [Chore(name="A", id="c1", assigned_to=["kid"]),
              Chore(name="B", id="c2", assigned_to=["kid"])]
    coord = _coord(settings=ALL, chores=chores, completions=[])
    child = _child()
    # Completing only the first of two due chores must NOT advance the streak.
    _award(coord, child, chore_id="c1", now=NOW)
    assert child.current_streak == 0
    assert child.last_completion_date is None


def test_all_mode_streak_advances_when_last_chore_done():
    chores = [Chore(name="A", id="c1", assigned_to=["kid"]),
              Chore(name="B", id="c2", assigned_to=["kid"])]
    # c1 already completed & stored; now completing c2 finishes the day.
    coord = _coord(settings=ALL, chores=chores, completions=[_comp("c1", NOW)])
    child = _child()
    _award(coord, child, chore_id="c2", now=NOW)
    assert child.current_streak == 1
    assert child.last_completion_date == "2024-03-20"


def test_all_mode_nothing_due_still_advances():
    # No chore is due today for this child → the day is vacuously satisfied.
    coord = _coord(settings=ALL, chores=[], completions=[])
    child = _child()
    _award(coord, child, chore_id="cX", now=NOW)
    assert child.current_streak == 1


def test_any_mode_first_completion_advances():
    # Setting OFF → existing behaviour: first completion of the day advances.
    chores = [Chore(name="A", id="c1", assigned_to=["kid"]),
              Chore(name="B", id="c2", assigned_to=["kid"])]
    coord = _coord(settings={}, chores=chores, completions=[])
    child = _child()
    _award(coord, child, chore_id="c1", now=NOW)
    assert child.current_streak == 1


# ── Perfect week: all-chores mode ─────────────────────────────────────────

# A Monday so _async_check_perfect_week runs (it only runs on Mondays); the
# "last week" it evaluates is the 7 days ending the day before.
MONDAY = dt.datetime(2024, 3, 18, 9, 0, tzinfo=UTC)        # today = Monday
LAST_WEEK = [dt.date(2024, 3, 11) + dt.timedelta(days=i) for i in range(7)]  # Mon..Sun


def _run_perfect_week(coord, now=MONDAY):
    import custom_components.taskmate.coord_points as _mod
    with patch.object(_mod.dt_util, "now", return_value=now):
        run(coord._async_check_perfect_week())


def _daily_chore(cid):
    # due every day (specific_days + empty due_days), created before last week
    return Chore(name=cid, id=cid, assigned_to=["kid"], created_date="2024-01-01")


def test_perfect_week_all_mode_not_awarded_when_a_day_missed_a_chore():
    chores = [_daily_chore("c1"), _daily_chore("c2")]
    # Every day last week: c1 done; c2 done on all days EXCEPT Wednesday(13th).
    comps = []
    for d in LAST_WEEK:
        when = dt.datetime(d.year, d.month, d.day, 10, 0, tzinfo=UTC)
        comps.append(_comp("c1", when))
        if d != dt.date(2024, 3, 13):
            comps.append(_comp("c2", when))
    child = _child()
    coord = _coord(
        settings={"perfect_week_enabled": "true", "perfect_week_requires_all_chores": "true"},
        chores=chores, completions=comps, children=[child],
    )
    _run_perfect_week(coord)
    assert child.awarded_perfect_weeks == []  # one chore missed on Wed → no bonus


def test_perfect_week_all_mode_awarded_when_every_chore_done_every_day():
    chores = [_daily_chore("c1"), _daily_chore("c2")]
    comps = []
    for d in LAST_WEEK:
        when = dt.datetime(d.year, d.month, d.day, 10, 0, tzinfo=UTC)
        comps.append(_comp("c1", when))
        comps.append(_comp("c2", when))
    child = _child()
    coord = _coord(
        settings={"perfect_week_enabled": "true", "perfect_week_bonus": "50",
                  "perfect_week_requires_all_chores": "true"},
        chores=chores, completions=comps, children=[child],
    )
    _run_perfect_week(coord)
    assert child.awarded_perfect_weeks == ["2024-03-11"]
    assert child.points == 50


def test_perfect_week_any_mode_awarded_with_partial_days():
    # Setting OFF → existing behaviour: ≥1 completion per required day is enough.
    chores = [_daily_chore("c1"), _daily_chore("c2")]
    comps = []
    for d in LAST_WEEK:
        when = dt.datetime(d.year, d.month, d.day, 10, 0, tzinfo=UTC)
        comps.append(_comp("c1", when))  # only c1 each day; c2 never done
    child = _child()
    coord = _coord(
        settings={"perfect_week_enabled": "true"},
        chores=chores, completions=comps, children=[child],
    )
    _run_perfect_week(coord)
    assert child.awarded_perfect_weeks == ["2024-03-11"]
