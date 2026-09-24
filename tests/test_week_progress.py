"""This week's points earned vs. the most on offer, per child.

Feeds the sticker chart's weekly goal (`goal: week`), where the blocks fill
towards every star the week's jobs can give instead of a reward's cost, so
stars earned past the goal can't pile up unseen.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import custom_components.taskmate.coord_points as coord_points
from custom_components.taskmate.models import Child, Chore, ChoreCompletion

from .test_coordinator_logic import _make_coord

# Wednesday 16 Sept 2026: the week is Mon 14 to Sun 20.
NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
MILLIE = Child(name="Millie", id="millie")
EVIE = Child(name="Evie", id="evie")


def _chore(**kw):
    base = {"name": "Job", "points": 1, "schedule_mode": "specific_days", "due_days": []}
    base.update(kw)
    return Chore(**base)


def _done(child_id, when, points, approved=True, subtask=""):
    return ChoreCompletion(
        chore_id="c",
        child_id=child_id,
        completed_at=when,
        approved=approved,
        points_awarded=points,
        bonus_subtask_id=subtask,
    )


def _progress(chores, completions=(), settings=None, children=(MILLIE, EVIE)):
    coord = _make_coord(settings={"weekend_multiplier": "1.0", **(settings or {})}, children=list(children))
    with patch.object(coord_points.dt_util, "_now", NOW):
        return coord.week_progress(list(children), chores, list(completions))


def test_every_day_chore_offers_seven_days():
    assert _progress([_chore(points=2)])["millie"]["available"] == 14


def test_specific_days_only_count_their_days():
    chore = _chore(due_days=["monday", "wednesday", "friday"])
    assert _progress([chore])["millie"]["available"] == 3


def test_daily_limit_multiplies_what_is_on_offer():
    assert _progress([_chore(points=5, daily_limit=3)])["evie"]["available"] == 105


def test_weekend_multiplier_is_included():
    weekend = _chore(points=1, due_days=["saturday", "sunday"])
    assert _progress([weekend], settings={"weekend_multiplier": "2.0"})["millie"]["available"] == 4


def test_only_the_childs_own_chores_count():
    chores = [_chore(points=1, assigned_to=["evie"]), _chore(points=1, disabled_for=["evie"])]
    result = _progress(chores)
    assert result["evie"]["available"] == 7
    assert result["millie"]["available"] == 7


def test_rotation_chores_are_left_out():
    chore = _chore(points=3, assignment_mode="round_robin")
    assert _progress([chore])["millie"]["available"] == 0


def test_planned_vacation_days_are_left_out():
    settings = {"vacation_periods": [{"id": "v", "name": "Away", "start": "2026-09-18", "end": "2026-09-20"}]}
    assert _progress([_chore()], settings=settings)["millie"]["available"] == 4


def test_earned_counts_approved_points_since_monday_only():
    completions = [
        _done("millie", datetime(2026, 9, 14, 8, 0, tzinfo=UTC), 3),
        _done("millie", datetime(2026, 9, 16, 8, 0, tzinfo=UTC), 2),
        _done("millie", datetime(2026, 9, 13, 8, 0, tzinfo=UTC), 50),  # last Sunday
        _done("millie", datetime(2026, 9, 15, 8, 0, tzinfo=UTC), 9, approved=False),
        _done("millie", datetime(2026, 9, 15, 8, 0, tzinfo=UTC), 4, subtask="extra"),
        _done("evie", datetime(2026, 9, 15, 8, 0, tzinfo=UTC), 7),
    ]
    result = _progress([_chore()], completions)
    assert result["millie"]["earned"] == 5
    assert result["evie"]["earned"] == 7
