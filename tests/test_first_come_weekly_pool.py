"""A weekly first_come chore stays done for the whole pool (#1239).

first_come shares one job across its pool. The daily check only counted
today's completions, and a child's completion only stamped that child's own
recurrence record, so a weekly first_come chore closed for the child who did
it but came back for everyone else the next day. A parent's completion already
stamped the whole pool, so the two paths disagreed.

The recurrence window now reads the latest completion across the pool.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, patch

from .test_first_come_shared_limit import _make_system, _now, run

DAY = dt.timedelta(days=1)


def _at(mod, when):
    return patch.object(mod.dt_util, "now", return_value=when)


def _coop(coord, mod, *, mode="first_come", recurrence="weekly", requires_approval=False):
    coord.notifications = AsyncMock()
    with _at(mod, _now()):
        a = run(coord.async_add_child("Ava"))
        b = run(coord.async_add_child("Ben"))
        chore = run(
            coord.async_add_chore(
                "Clean the coop",
                points=5,
                requires_approval=requires_approval,
                assignment_mode=mode,
                assigned_to=[a.id, b.id],
                schedule_mode="recurring",
                recurrence=recurrence,
            )
        )
    return chore, a, b


def _complete(coord, mod, when, chore, child_id):
    with _at(mod, when):
        return run(coord.async_complete_chore(chore.id, child_id))


def _available(coord, mod, when, chore, child_id):
    with _at(mod, when):
        return coord.is_chore_available_for_child(chore, child_id)


def test_one_childs_completion_closes_the_week_for_the_pool():
    coord, _storage, mod = _make_system()
    chore, a, b = _coop(coord, mod)
    assert _complete(coord, mod, _now(), chore, a.id) is not None

    assert _available(coord, mod, _now() + DAY, chore, a.id) is False
    assert _available(coord, mod, _now() + DAY, chore, b.id) is False
    assert _available(coord, mod, _now() + 6 * DAY, chore, b.id) is False
    assert _complete(coord, mod, _now() + DAY, chore, b.id) is None


def test_it_reopens_for_everyone_when_the_window_ends():
    coord, _storage, mod = _make_system()
    chore, a, b = _coop(coord, mod)
    _complete(coord, mod, _now(), chore, a.id)

    assert _available(coord, mod, _now() + 7 * DAY, chore, a.id) is True
    assert _available(coord, mod, _now() + 7 * DAY, chore, b.id) is True


def test_every_two_weeks_shares_its_fortnight():
    coord, _storage, mod = _make_system()
    chore, a, b = _coop(coord, mod, recurrence="every_2_weeks")
    _complete(coord, mod, _now(), chore, a.id)

    assert _available(coord, mod, _now() + 13 * DAY, chore, b.id) is False
    assert _available(coord, mod, _now() + 14 * DAY, chore, b.id) is True


def test_a_completion_awaiting_approval_counts():
    coord, _storage, mod = _make_system()
    chore, a, b = _coop(coord, mod, requires_approval=True)
    completion = _complete(coord, mod, _now(), chore, a.id)
    assert completion is not None and not completion.approved

    assert _available(coord, mod, _now() + DAY, chore, b.id) is False


def test_rejecting_the_completion_reopens_it_for_the_pool():
    coord, _storage, mod = _make_system()
    chore, a, b = _coop(coord, mod, requires_approval=True)
    completion = _complete(coord, mod, _now(), chore, a.id)

    with _at(mod, _now() + DAY):
        run(coord.async_reject_chore(completion.id))
    assert _available(coord, mod, _now() + DAY, chore, b.id) is True
    assert _available(coord, mod, _now() + DAY, chore, a.id) is True


def test_the_latest_completion_in_the_pool_sets_the_window():
    """Ben did it two weeks ago; Ava did it yesterday. Ava's counts."""
    coord, storage, mod = _make_system()
    chore, a, b = _coop(coord, mod)
    storage.set_last_completed(chore.id, b.id, (_now() - 14 * DAY).isoformat())
    storage.set_last_completed(chore.id, a.id, (_now() - DAY).isoformat())

    assert _available(coord, mod, _now(), chore, b.id) is False
    assert _available(coord, mod, _now() + 6 * DAY, chore, b.id) is True


def test_everyone_mode_keeps_its_own_window_per_child():
    coord, _storage, mod = _make_system()
    chore, a, b = _coop(coord, mod, mode="everyone")
    _complete(coord, mod, _now(), chore, a.id)

    assert _available(coord, mod, _now() + DAY, chore, a.id) is False
    assert _available(coord, mod, _now() + DAY, chore, b.id) is True
