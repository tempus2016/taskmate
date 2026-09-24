"""A grown-up can log a job done on an earlier day that nobody ticked.

`complete_chore` with `completed_date` (parent-only) stamps the completion on
that day, so it counts towards that day's limit and that week's sticker-chart
bar, and it is approved straight away. The streak is left alone.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import custom_components.taskmate.coord_chores as coord_chores
from custom_components.taskmate.models import Child, Chore, ChoreCompletion

from .test_coordinator_logic import _make_coord

# Wednesday 16 Sept 2026.
NOW = datetime(2026, 9, 16, 18, 0, tzinfo=UTC)
MONDAY = date(2026, 9, 14)
MILLIE = Child(name="Millie", id="millie")


def _setup(chore, completions=()):
    coord = _make_coord(children=[MILLIE], completions=list(completions))
    stored = list(completions)
    coord.storage.get_chore = MagicMock(side_effect=lambda cid: chore if cid == chore.id else None)
    coord.storage.get_completions = MagicMock(side_effect=lambda: stored)
    coord.storage.add_completion = MagicMock(side_effect=stored.append)
    coord.storage.update_completion = MagicMock()
    coord._award_points = AsyncMock(side_effect=lambda child, pts, **kw: pts)
    return coord, stored


def _run(coord, chore_id="bed", day=MONDAY):
    with patch.object(coord_chores.dt_util, "_now", NOW):
        return asyncio.run(coord.async_complete_chore_on_date(chore_id, "millie", day))


def _bed(**kw):
    base = {"name": "Make bed", "id": "bed", "points": 2, "schedule_mode": "specific_days", "due_days": []}
    base.update(kw)
    return Chore(**base)


def test_logs_an_approved_completion_on_that_day():
    coord, stored = _setup(_bed())
    completion = _run(coord)
    assert completion.completed_at.date() == MONDAY
    assert completion.approved is True
    assert completion.points_awarded == 2
    assert stored == [completion]


def test_points_use_that_days_date_and_leave_the_streak_alone():
    coord, _ = _setup(_bed())
    _run(coord)
    kwargs = coord._award_points.await_args.kwargs
    assert kwargs["completion_date"] == MONDAY
    assert kwargs["skip_streak"] is True


@pytest.mark.parametrize("day", [date(2026, 9, 16), date(2026, 9, 17), date(2026, 9, 8)])
def test_only_the_last_seven_days_before_today(day):
    coord, _ = _setup(_bed())
    with pytest.raises(ValueError, match="last 7 days"):
        _run(coord, day=day)


def test_refuses_a_day_the_job_was_not_due():
    coord, _ = _setup(_bed(due_days=["saturday", "sunday"]))
    with pytest.raises(ValueError, match="wasn't due on Monday"):
        _run(coord)


def test_refuses_someone_elses_job():
    coord, _ = _setup(_bed(assigned_to=["evie"]))
    with pytest.raises(ValueError, match="isn't one of Millie's jobs"):
        _run(coord)


def test_refuses_rotation_chores():
    coord, _ = _setup(_bed(assignment_mode="round_robin"))
    with pytest.raises(ValueError, match="rotates"):
        _run(coord)


def test_that_days_limit_still_applies():
    done = ChoreCompletion(chore_id="bed", child_id="millie", completed_at=datetime(2026, 9, 14, 8, tzinfo=UTC))
    coord, _ = _setup(_bed(), [done])
    with pytest.raises(ValueError, match="already done 1/1 times on Monday"):
        _run(coord)


def test_a_completion_on_another_day_does_not_use_up_the_limit():
    other = ChoreCompletion(chore_id="bed", child_id="millie", completed_at=datetime(2026, 9, 15, 8, tzinfo=UTC))
    coord, stored = _setup(_bed(), [other])
    _run(coord)
    assert len(stored) == 2


def test_the_service_gates_past_days_to_parents():
    """Logging a past day is a grown-up's correction: the service must demand a
    parent before routing to the backdating path, whatever as_parent says."""
    from pathlib import Path

    src = (Path(__file__).parents[1] / "custom_components/taskmate/__init__.py").read_text()
    block = src[src.index('completed_date = call.data.get("completed_date")'):]
    block = block[: block.index("if as_parent:")]
    assert "await _async_require_parent(hass, call)" in block
    assert "async_complete_chore_on_date" in block
    assert 'vol.Optional("completed_date"): cv.date' in src


def test_the_panel_offers_it_on_each_child():
    from pathlib import Path

    panel = (Path(__file__).parents[1] / "custom_components/taskmate/www/taskmate-panel.js").read_text()
    assert 'data-act="backdate-open"' in panel
    assert "completed_date: d.day" in panel
    assert "as_parent: true" in panel


def test_completions_on_date_lists_only_that_day():
    rows = [
        ChoreCompletion(chore_id="bed", child_id="millie", completed_at=datetime(2026, 9, 14, 8, tzinfo=UTC), approved=True),
        ChoreCompletion(chore_id="bed", child_id="millie", completed_at=datetime(2026, 9, 15, 8, tzinfo=UTC)),
        ChoreCompletion(chore_id="bed", child_id="millie", completed_at=datetime(2026, 9, 14, 9, tzinfo=UTC), bonus_subtask_id="x"),
    ]
    coord, _ = _setup(_bed(), rows)
    out = coord.completions_on_date(MONDAY)
    assert [r["completion_id"] for r in out] == [rows[0].id]
    assert out[0]["approved"] is True and out[0]["chore_id"] == "bed"


def test_the_panel_shows_the_sticker_card_for_the_day():
    from pathlib import Path

    panel = (Path(__file__).parents[1] / "custom_components/taskmate/www/taskmate-panel.js").read_text()
    assert "taskmate-sticker-chart-card.js?v=${PANEL_VERSION}" in panel
    assert '"taskmate/day_completions"' in panel
    ws = (Path(__file__).parents[1] / "custom_components/taskmate/websocket.py").read_text()
    assert "_ws_day_completions,\n" in ws
