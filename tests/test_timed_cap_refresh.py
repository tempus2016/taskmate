"""A timer reaching its daily cap mid-refresh, and a locked timer at its cap (#771).

1. The cap auto-stop runs inside the coordinator's own refresh
   (_async_update_data). It stopped the session through async_stop_timed_task,
   which ended with ``await self.async_refresh()`` — re-entering the refresh
   debouncer, which raises "Debouncer lock is not re-entrant" in Home
   Assistant and broke the refresh. The stop now takes ``refresh=False`` from
   there; the running update picks the change up in the same tick.

2. A running timer whose chore the child can no longer do (a prerequisite
   added after it started, say) still auto-completed at its cap and paid out.
   Completing that chore is refused, so the stopped time now goes to a parent
   to approve instead of being paid automatically.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import patch

from custom_components.taskmate.models import TimedSession

from .test_completion_eligibility import _make_system, _now, run

TIMED_NOW = "custom_components.taskmate.coord_timed.dt_util.now"


class ReentrantRefresh(RuntimeError):
    pass


def _system(*, requires_approval=False, cap=10):
    coord, storage, mod = _make_system()
    with patch.object(mod.dt_util, "now", return_value=_now()):
        kid = run(coord.async_add_child("Vaiha"))
        chore = run(
            coord.async_add_chore(
                "Reading", points=0, requires_approval=requires_approval, schedule_mode="specific_days"
            )
        )
    chore.task_type = "timed"
    chore.timed_rate_points = 2
    chore.timed_rate_minutes = 5
    chore.timed_max_daily_minutes = cap
    storage.update_chore(chore)
    started = _now() - dt.timedelta(minutes=cap + 1)
    storage.save_timed_session(
        TimedSession(
            chore_id=chore.id,
            child_id=kid.id,
            state="running",
            segments=[{"start": started.isoformat(), "end": None}],
            session_date=_now().date().isoformat(),
        )
    )
    return coord, storage, mod, kid, chore


def _reentrancy_guard(coord):
    """Fail the way HA's debouncer does when the refresh is re-entered."""

    async def refresh():
        raise ReentrantRefresh("Debouncer lock is not re-entrant")

    coord.async_refresh = refresh


def _update(coord, mod):
    with patch.object(mod.dt_util, "now", return_value=_now()), patch(TIMED_NOW, return_value=_now()):
        return run(coord._async_update_data())


def test_a_capped_timer_stops_inside_the_refresh_without_re_entering_it():
    coord, storage, mod, kid, chore = _system()
    _reentrancy_guard(coord)
    data = _update(coord, mod)  # raised ReentrantRefresh before the fix
    assert storage.get_timed_sessions() == []
    done = [c for c in storage.get_completions() if c.chore_id == chore.id]
    assert len(done) == 1 and done[0].approved and done[0].points_awarded == 4  # 10 min at 2 per 5 min
    # The running update returns the post-stop state: no stale session in it.
    assert data["timed_sessions"] == []


def test_a_parent_or_child_stop_outside_the_refresh_still_refreshes():
    coord, storage, mod, kid, chore = _system()
    calls = []

    async def refresh():
        calls.append(1)

    coord.async_refresh = refresh
    with patch.object(mod.dt_util, "now", return_value=_now()), patch(TIMED_NOW, return_value=_now()):
        run(coord.async_stop_timed_task(chore.id, kid.id))
    assert calls == [1]


def test_a_locked_timer_at_its_cap_goes_to_a_parent_instead_of_paying_out():
    coord, storage, mod, kid, chore = _system()
    with patch.object(mod.dt_util, "now", return_value=_now()):
        prereq = run(coord.async_add_chore("Brush teeth", points=1, schedule_mode="specific_days"))
    chore.depends_on = [prereq.id]  # added after the timer started
    storage.update_chore(chore)
    _reentrancy_guard(coord)
    _update(coord, mod)
    done = [c for c in storage.get_completions() if c.chore_id == chore.id]
    assert len(done) == 1
    assert done[0].approved is False and done[0].points_awarded == 0
    assert done[0].submitted_points == 4, "the child's time is kept for the parent to approve"
    assert storage.get_child(kid.id).points == 0
    coord._async_notify_pending_approval.assert_called_once()


def test_an_open_timer_at_its_cap_pays_as_before():
    coord, storage, mod, kid, chore = _system()
    _reentrancy_guard(coord)
    _update(coord, mod)
    assert storage.get_child(kid.id).points == 4


def test_the_stale_session_sweep_can_skip_its_refresh():
    coord, storage, mod, kid, chore = _system()
    _reentrancy_guard(coord)
    tomorrow = _now() + dt.timedelta(days=1)
    with patch.object(mod.dt_util, "now", return_value=tomorrow), patch(TIMED_NOW, return_value=tomorrow):
        run(coord._async_stop_stale_timed_sessions(refresh=False))
    assert storage.get_timed_sessions() == []
