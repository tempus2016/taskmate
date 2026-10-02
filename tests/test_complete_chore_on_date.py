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
    # The follow-up an ordinary approval runs, so a test can see it happen.
    coord.storage.get_last_completed = MagicMock(return_value={})
    coord.storage.set_last_completed = MagicMock()
    coord.storage.update_chore = MagicMock()
    coord._async_advance_quests = AsyncMock()
    coord._async_evaluate_challenges = AsyncMock()
    coord.badges = MagicMock()
    coord.badges.evaluate_for_child = AsyncMock()
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
    block = src[src.index('completed_date = call.data.get("completed_date")') :]
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
        ChoreCompletion(
            chore_id="bed", child_id="millie", completed_at=datetime(2026, 9, 14, 8, tzinfo=UTC), approved=True
        ),
        ChoreCompletion(chore_id="bed", child_id="millie", completed_at=datetime(2026, 9, 15, 8, tzinfo=UTC)),
        ChoreCompletion(
            chore_id="bed", child_id="millie", completed_at=datetime(2026, 9, 14, 9, tzinfo=UTC), bonus_subtask_id="x"
        ),
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


# ── It is an ordinary approval, not a shortcut ───────────────────────────────


def test_runs_the_same_after_approval_hooks_as_any_approval():
    coord, _ = _setup(_bed())
    _run(coord)
    coord.badges.evaluate_for_child.assert_awaited_once_with("millie", "manual")
    coord._async_advance_quests.assert_awaited_once_with("millie", "bed")
    coord._async_evaluate_challenges.assert_awaited_once_with("millie")
    coord.storage.async_save.assert_awaited()
    coord.async_refresh.assert_awaited()


def test_it_is_marked_backdated_and_parent_made():
    coord, _ = _setup(_bed())
    completion = _run(coord)
    assert completion.backdated is True
    assert completion.child_undo_allowed is False
    assert ChoreCompletion.from_dict(completion.to_dict()).backdated is True
    # Written only when set, so ordinary completions keep their small records.
    assert "backdated" not in ChoreCompletion(chore_id="a", child_id="b", completed_at=NOW).to_dict()


def test_records_last_completed_when_it_is_the_latest():
    coord, _ = _setup(_bed())
    completion = _run(coord)
    coord.storage.set_last_completed.assert_called_once_with("bed", "millie", completion.completed_at.isoformat())


def test_does_not_pull_last_completed_back_behind_a_later_completion():
    coord, _ = _setup(_bed())
    coord.storage.get_last_completed = MagicMock(return_value={"current": "2026-09-15T08:00:00+00:00"})
    _run(coord)
    coord.storage.set_last_completed.assert_not_called()


def test_a_one_shot_job_is_disabled_for_that_child_like_any_approval():
    chore = _bed(schedule_mode="one_shot", created_date=MONDAY.isoformat())
    coord, _ = _setup(chore)
    _run(coord)
    assert "millie" in chore.disabled_for
    coord.storage.update_chore.assert_called()


# ── Chore kinds that can't (or must not) be logged afterwards ────────────────


def test_refuses_open_ended_chores():
    coord, _ = _setup(_bed(open_ended=True))
    with pytest.raises(ValueError, match="open-ended"):
        _run(coord)


def test_refuses_teamwork_chores():
    coord, _ = _setup(_bed(team_size=2))
    coord.teamwork_size = MagicMock(return_value=2)
    with pytest.raises(ValueError, match="needs a team"):
        _run(coord)


def test_refuses_a_day_won_at_auction():
    coord, _ = _setup(_bed())
    coord.auction_winner = MagicMock(return_value="evie")
    with pytest.raises(ValueError, match="won at auction"):
        _run(coord)


# ── Weekly targets (#883) ────────────────────────────────────────────────────


def _week_of(day, n, chore_id="bed"):
    return [
        ChoreCompletion(chore_id=chore_id, child_id="millie", completed_at=datetime(2026, 9, day, 8, tzinfo=UTC))
        for _ in range(n)
    ]


def test_a_weekly_target_chore_can_be_logged_on_any_day_while_the_quota_is_open():
    # Due only at weekends, but a weekly-target chore's days are the child's choice.
    coord, stored = _setup(_bed(weekly_target=2, due_days=["saturday"]), _week_of(15, 1))
    _run(coord)
    assert len(stored) == 2


def test_a_weekly_target_chore_refuses_once_that_weeks_quota_is_met():
    coord, _ = _setup(_bed(weekly_target=2, due_days=["saturday"]), _week_of(15, 1) + _week_of(16, 1))
    with pytest.raises(ValueError, match="already reached its 2"):
        _run(coord)


def test_the_quota_is_counted_for_the_week_of_the_day_being_logged():
    # Two completions last week fill last week's quota, not this week's.
    last_week = _week_of(9, 2)
    coord, stored = _setup(_bed(weekly_target=2, due_days=[]), last_week)
    _run(coord)  # Monday 14th: this week has none yet
    assert len(stored) == 3
    with pytest.raises(ValueError, match="already reached its 2"):
        _run(coord, day=date(2026, 9, 10))  # Thursday of last week: already 2


# ── Undoing one ──────────────────────────────────────────────────────────────


def _undo(completion, child, last_completed=None):
    coord = _make_coord(children=[child], completions=[completion])
    coord.storage.get_chore = MagicMock(return_value=None)
    coord.storage.get_last_completed = MagicMock(return_value=last_completed or {})
    coord.storage.undo_last_completed = MagicMock()
    with patch.object(coord_chores.dt_util, "_now", NOW):
        coord._reverse_completion_awards(completion, [completion])
    return coord


def _approved(backdated):
    return ChoreCompletion(
        chore_id="bed",
        child_id="millie",
        completed_at=datetime(2026, 9, 14, 12, tzinfo=UTC),
        approved=True,
        points_awarded=2,
        backdated=backdated,
    )


def test_undoing_a_backdated_job_leaves_the_streak_alone():
    child = Child(name="Millie", id="millie", points=10, current_streak=5, last_completion_date="2026-09-16")
    _undo(_approved(backdated=True), child)
    assert child.current_streak == 5
    assert child.last_completion_date == "2026-09-16"
    assert child.points == 8  # the points it paid are still taken back


def test_undoing_an_ordinary_approval_still_takes_a_day_off_the_streak():
    child = Child(name="Millie", id="millie", points=10, current_streak=5, last_completion_date="2026-09-14")
    _undo(_approved(backdated=False), child)
    assert child.current_streak == 4


def test_undoing_a_backdated_job_does_not_pop_a_later_last_completed():
    child = Child(name="Millie", id="millie", points=10)
    coord = _undo(_approved(backdated=True), child, {"current": "2026-09-15T08:00:00+00:00"})
    coord.storage.undo_last_completed.assert_not_called()


def test_undoing_a_backdated_job_that_set_last_completed_restores_it():
    child = Child(name="Millie", id="millie", points=10)
    coord = _undo(_approved(backdated=True), child, {"current": "2026-09-14T12:00:00+00:00"})
    coord.storage.undo_last_completed.assert_called_once_with("bed", "millie")
