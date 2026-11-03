"""A handled mandatory miss stays handled, and an away child owes none (#1161).

Every parent action on a miss (dismiss, apply penalty, postpone) removes it
from storage, and the detectors were only idempotent while it was still
there. The set-time check runs every 5 minutes, so a dismissed miss came
straight back — and a penalised one could be penalised again. The startup
catch-up did the same for period misses. Separately, neither detector looked
at whether the child was away, though their chores are hidden while they are.
"""

from __future__ import annotations

from unittest.mock import patch

from tests.test_set_times import DAY, _setup, _system, at, run


def _miss(storage, time_id):
    return next(m for m in storage.get_mandatory_misses() if m.time_id == time_id)


def _detect(coord, mod, when):
    with patch.object(mod.dt_util, "now", return_value=when):
        return run(coord.async_detect_set_time_misses())


def _away_entity(coord, state):
    obj = type("S", (), {"state": state, "attributes": {}})()
    coord.hass.states = type(
        "FakeStates", (), {"get": lambda self, eid: obj if eid == "input_boolean.home" else None}
    )()


# ── set times: a handled miss is not raised again ────────────────────────────


def test_a_dismissed_set_time_miss_stays_dismissed():
    coord, storage, mod, _kid, _chore = _setup(mandatory=True)
    assert _detect(coord, mod, at(10)) == 1
    with patch.object(mod.dt_util, "now", return_value=at(10)):
        run(coord.async_dismiss_mandatory_chore(_miss(storage, "b").id))
    assert storage.get_mandatory_misses() == []
    # The next 5-minute ticks, and the rest of the day.
    assert _detect(coord, mod, at(10, 5)) == 0
    assert _detect(coord, mod, at(11)) == 0
    assert storage.get_mandatory_misses() == []


def test_a_penalised_set_time_miss_is_charged_once():
    coord, storage, mod, kid, _chore = _setup(mandatory=True)
    kid = storage.get_child(kid.id)
    kid.points = 10
    storage.update_child(kid)
    before = 10
    _detect(coord, mod, at(10))
    with patch.object(mod.dt_util, "now", return_value=at(10)):
        run(coord.async_apply_mandatory_penalty(_miss(storage, "b").id))
    assert _detect(coord, mod, at(10, 5)) == 0
    assert storage.get_mandatory_misses() == []
    assert storage.get_child(kid.id).points == before - 2


def test_a_postponed_set_time_miss_is_not_raised_again():
    coord, storage, mod, _kid, _chore = _setup(mandatory=True)
    _detect(coord, mod, at(10))
    with patch.object(mod.dt_util, "now", return_value=at(10)):
        run(coord.async_postpone_mandatory_chore(_miss(storage, "b").id))
    assert _detect(coord, mod, at(10, 5)) == 0


def test_dismissing_one_time_leaves_the_others_owed():
    coord, storage, mod, _kid, _chore = _setup(mandatory=True)
    _detect(coord, mod, at(10))
    with patch.object(mod.dt_util, "now", return_value=at(10)):
        run(coord.async_dismiss_mandatory_chore(_miss(storage, "b").id))
    assert _detect(coord, mod, at(23)) == 2
    assert sorted(m.time_id for m in storage.get_mandatory_misses()) == ["d", "l"]


def test_the_handled_record_survives_a_restart():
    coord, storage, mod, _kid, _chore = _setup(mandatory=True)
    _detect(coord, mod, at(10))
    with patch.object(mod.dt_util, "now", return_value=at(10)):
        run(coord.async_dismiss_mandatory_chore(_miss(storage, "b").id))
    run(storage.async_load())
    with patch.object(mod.dt_util, "now", return_value=at(10, 5)):
        run(coord.async_catchup_mandatory_misses())
    assert storage.get_mandatory_misses() == []


def test_the_handled_record_is_pruned_after_two_days():
    from datetime import timedelta

    coord, storage, mod, _kid, _chore = _setup(mandatory=True)
    storage.add_handled_mandatory("old", (DAY - timedelta(days=5)).isoformat())
    storage.add_handled_mandatory("new", DAY.isoformat())
    assert storage.get_handled_mandatory_keys() == {"new"}


# ── set times: an away child owes nothing ────────────────────────────────────


def test_no_set_time_miss_while_the_child_is_away():
    coord, storage, mod, kid, _chore = _setup(mandatory=True)
    kid = storage.get_child(kid.id)
    kid.availability_entity = "input_boolean.home"
    kid.pause_streak_when_unavailable = True
    storage.update_child(kid)
    _away_entity(coord, "off")
    assert _detect(coord, mod, at(23)) == 0
    assert storage.get_mandatory_misses() == []


def test_set_time_misses_resume_once_the_child_is_home():
    coord, storage, mod, kid, _chore = _setup(mandatory=True)
    kid = storage.get_child(kid.id)
    kid.availability_entity = "input_boolean.home"
    kid.pause_streak_when_unavailable = True
    storage.update_child(kid)
    _away_entity(coord, "on")
    assert _detect(coord, mod, at(23)) == 3


def test_no_set_time_miss_on_a_family_vacation():
    coord, storage, mod, _kid, _chore = _setup(mandatory=True)
    storage.set_setting("vacation_periods", [{"start": DAY.isoformat(), "end": DAY.isoformat()}])
    assert _detect(coord, mod, at(23)) == 0


# ── period chores: the same two rules ────────────────────────────────────────


def _period_setup():
    coord, storage, mod = _system()
    with patch.object(mod.dt_util, "now", return_value=at(6)):
        kid = run(coord.async_add_child("Ava"))
        chore = run(coord.async_add_chore("Make bed", points=5, assigned_to=[kid.id], time_category="morning"))
        chore.mandatory = True
        run(coord.async_update_chore(chore))
    return coord, storage, mod, storage.get_child(kid.id), chore


def _detect_period(coord, mod):
    with patch.object(mod.dt_util, "now", return_value=at(13)):
        return run(coord.async_detect_mandatory_misses("morning", DAY))


def test_a_dismissed_period_miss_is_not_raised_again_by_the_catch_up():
    coord, storage, mod, _kid, _chore = _period_setup()
    assert _detect_period(coord, mod) == 1
    with patch.object(mod.dt_util, "now", return_value=at(13)):
        run(coord.async_dismiss_mandatory_chore(storage.get_mandatory_misses()[0].id))
    assert _detect_period(coord, mod) == 0


def test_no_period_miss_while_the_child_is_away():
    coord, storage, mod, kid, _chore = _period_setup()
    kid.availability_entity = "input_boolean.home"
    kid.pause_streak_when_unavailable = True
    storage.update_child(kid)
    _away_entity(coord, "off")
    assert _detect_period(coord, mod) == 0
