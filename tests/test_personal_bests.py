"""Personal bests (#1099): a child's own records, and the moment they beat one."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, patch

from .test_completion_eligibility import _now, run
from .test_family_care import _at, _family, _fired

BESTS = "custom_components.taskmate.coord_bests.dt_util"
CHORES = "custom_components.taskmate.coord_chores.dt_util"
POINTS = "custom_components.taskmate.coord_points.dt_util"


def _clock(mod, when=None):
    when = when or _now()
    import contextlib

    stack = contextlib.ExitStack()
    for ctx in (
        _at(mod, when),
        patch(f"{BESTS}.now", return_value=when),
        patch(f"{CHORES}.now", return_value=when),
        patch(f"{POINTS}.now", return_value=when),
    ):
        stack.enter_context(ctx)
    return stack


def _setup(**chore_fields):
    coord, storage, mod, kid, chore = _family(requires_approval=False, daily_limit=5, **chore_fields)
    coord._celebrate = AsyncMock()
    coord.badges = None
    return coord, storage, mod, kid, chore


def _do(coord, chore, kid):
    return run(coord.async_complete_chore(chore.id, kid.id))


class TestRecords:
    def test_first_values_are_stored_quietly_as_the_baseline(self):
        coord, storage, mod, kid, chore = _setup()
        with _clock(mod):
            _do(coord, chore, kid)
        state = coord.personal_bests_state(storage.get_child(kid.id))
        assert state["best_day_points"]["value"] == 5
        assert state["best_day_chores"]["value"] == 1
        assert state["best_week_points"]["value"] == 5
        assert state["best_single_award"]["value"] == 5
        assert state["longest_streak"]["value"] == 1
        assert state["best_day_points"]["date"] == "2024-03-20"
        assert state["best_week_points"]["date"] == "2024-03-18"
        assert state.get("new_today", []) == []
        assert _fired(coord, "taskmate_personal_best") == []
        coord.notifications.fire.assert_not_called()
        coord._celebrate.assert_not_called()

    def test_beating_a_record_celebrates_once(self):
        coord, storage, mod, kid, chore = _setup()
        with _clock(mod):
            _do(coord, chore, kid)
        coord.notifications.fire.reset_mock()
        tomorrow = _now() + dt.timedelta(days=1)
        with _clock(mod, tomorrow):
            _do(coord, chore, kid)
        # Day one again (5 pts / 1 chore) ties the day records; the week total
        # and the streak are genuinely longer than before.
        events = _fired(coord, "taskmate_personal_best")
        assert {e["record"] for e in events} == {"longest_streak", "best_week_points"}
        coord.hass.bus.async_fire.reset_mock()
        coord.notifications.fire.reset_mock()
        coord._celebrate.reset_mock()
        with _clock(mod, tomorrow + dt.timedelta(hours=1)):
            _do(coord, chore, kid)  # day: 10 pts / 2 chores — beats both, and the week again
        events = _fired(coord, "taskmate_personal_best")
        assert {e["record"] for e in events} == {"best_day_points", "best_day_chores", "best_week_points"}
        day_pts = next(e for e in events if e["record"] == "best_day_points")
        assert day_pts["value"] == 10 and day_pts["previous"] == 5 and day_pts["child_id"] == kid.id
        fired_types = [c.args[0] for c in coord.notifications.fire.call_args_list]
        assert fired_types.count("personal_best") == 3
        ctx = next(c.args[1] for c in coord.notifications.fire.call_args_list if c.args[0] == "personal_best")
        assert ctx["child_name"] == "Vaiha" and ctx["record_label"] and ctx["value"]
        assert coord._celebrate.await_count == 3
        assert coord._celebrate.await_args.kwargs["tier"] == 2
        assert coord._celebrate.await_args.args[1] == "personal_best"
        with _clock(mod, tomorrow + dt.timedelta(hours=1)):
            state = coord.personal_bests_state(storage.get_child(kid.id))
        assert sorted(state["new_today"]) == [
            "best_day_chores",
            "best_day_points",
            "best_week_points",
            "longest_streak",
        ]
        assert state["best_day_points"] == {"value": 10, "date": "2024-03-21", "previous": 5}
        assert state["longest_streak"] == {"value": 2, "date": "2024-03-21", "previous": 1}
        # Ties never re-celebrate.
        coord.hass.bus.async_fire.reset_mock()
        with _clock(mod, tomorrow + dt.timedelta(hours=2)):
            run(coord.async_check_personal_bests(kid.id))
        assert _fired(coord, "taskmate_personal_best") == []

    def test_streak_record_seeds_from_best_streak_and_beats_it(self):
        coord, storage, mod, kid, chore = _setup()
        kid.best_streak = 7
        storage.update_child(kid)
        with _clock(mod):
            _do(coord, chore, kid)
        state = coord.personal_bests_state(storage.get_child(kid.id))
        assert state["longest_streak"] == {"value": 7, "date": ""}
        assert "longest_streak" not in {e["record"] for e in _fired(coord, "taskmate_personal_best")}
        # Walk the streak up to 8 days.
        for i in range(1, 8):
            with _clock(mod, _now() + dt.timedelta(days=i)):
                _do(coord, chore, kid)
        streak_events = [e for e in _fired(coord, "taskmate_personal_best") if e["record"] == "longest_streak"]
        assert [e["value"] for e in streak_events] == [8]
        assert streak_events[0]["previous"] == 7

    def test_no_state_until_there_is_something_to_show(self):
        coord, storage, _mod, kid, _chore = _setup()
        assert coord.personal_bests_state(storage.get_child(kid.id)) == {}


class TestReversals:
    def test_undoing_the_record_day_pulls_the_record_back(self):
        coord, storage, mod, kid, chore = _setup()
        storage.set_setting("chore_undo_seconds", 600)
        with _clock(mod):
            _do(coord, chore, kid)
        day2 = _now() + dt.timedelta(days=1)
        with _clock(mod, day2):
            _do(coord, chore, kid)
        with _clock(mod, day2 + dt.timedelta(hours=1)):
            comp = _do(coord, chore, kid)
        assert coord.personal_bests_state(storage.get_child(kid.id))["best_day_points"]["value"] == 10
        with _clock(mod, day2 + dt.timedelta(hours=1, minutes=1)):
            run(coord.async_undo_chore(comp.id))
            state = coord.personal_bests_state(storage.get_child(kid.id))
        # Day 2 is back to 5, which ties day 1: the record falls to 5 and stops being "new today".
        assert state["best_day_points"]["value"] == 5
        assert state["best_day_chores"]["value"] == 1
        assert not {"best_day_points", "best_day_chores"} & set(state.get("new_today", []))
        # The streak (2 days) still stands: one completion is left on day 2.
        assert state["longest_streak"]["value"] == 2

    def test_rejecting_an_approved_record_chore_recomputes_too(self):
        coord, storage, mod, kid, chore = _setup()
        chore.requires_approval = True
        storage.update_chore(chore)
        with _clock(mod):
            c1 = _do(coord, chore, kid)
            run(coord.async_approve_chore(c1.id))
            c2 = _do(coord, chore, kid)
            run(coord.async_approve_chore(c2.id))
        assert coord.personal_bests_state(storage.get_child(kid.id))["best_day_points"]["value"] == 10
        with _clock(mod):
            run(coord.async_reject_chore(c2.id))
        assert coord.personal_bests_state(storage.get_child(kid.id))["best_day_points"]["value"] == 5

    def test_a_record_older_than_kept_history_is_left_alone(self):
        coord, storage, mod, kid, chore = _setup()
        storage.get_section("personal_bests", dict)[kid.id] = {
            "best_day_points": {"value": 99, "date": "2020-01-01", "set_at": "2020-01-01T10:00:00+00:00"}
        }
        with _clock(mod):
            _do(coord, chore, kid)
            run(coord.async_recompute_personal_bests(kid.id))
        assert coord.personal_bests_state(storage.get_child(kid.id))["best_day_points"]["value"] == 99
