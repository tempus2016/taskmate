"""Set times: a chore that comes up at set times of day ("several times a day").

A chore with ``times`` is ticked off once per time, only while that time is
open (plus the chore's claim allowance), and each time earns its own points.
For the day as a whole — the streak, the weekly target, "all done" — the
chore counts once, and only when every time is done. A mandatory chore owes a
miss per time that closed undone, and ``times_bonus`` is paid once a day when
every time is done.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.coord_set_times import set_time_label
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import (
    Chore,
    ChoreCompletion,
    ChoreTime,
    MandatoryMiss,
    clean_chore_times,
    validate_chore_times,
)
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc
DAY = dt.date(2024, 3, 20)  # a Wednesday

MEALS = [
    {"id": "b", "name": "Breakfast", "start": "07:00", "end": "09:00", "points": 1},
    {"id": "l", "name": "Lunch", "start": "12:00", "end": "13:30", "points": 1},
    {"id": "d", "name": "Dinner", "start": "17:30", "end": "19:00", "points": 2},
]


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def at(hour, minute=0, day=DAY):
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def _system():
    from tests.conftest import FakeHass, FakeStore

    hass = FakeHass()
    hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()
    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    run(storage.async_load())
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.data = {}
    coord.storage = storage
    coord._unsub_midnight = None
    coord._unsub_prune = None
    coord._unsub_availability = None
    coord.async_refresh = AsyncMock()
    coord._async_notify_pending_approval = AsyncMock()
    coord.notifications = MagicMock()
    coord.notifications.clear_approval = AsyncMock()
    coord.notifications.fire = AsyncMock()
    coord.notifications._has_outstanding_chores_today = MagicMock(return_value=True)
    import custom_components.taskmate.coordinator as mod

    return coord, storage, mod


def _setup(*, approval=False, bonus=0, grace=0, mandatory=False, weekly_target=0, now=None):
    coord, storage, mod = _system()
    with patch.object(mod.dt_util, "now", return_value=now or at(6)):
        kid = run(coord.async_add_child("Ava"))
        chore = run(coord.async_add_chore("Wash hands", points=10, requires_approval=approval, assigned_to=[kid.id]))
        chore.times = [dict(t) for t in MEALS]
        chore.times_bonus = bonus
        chore.claim_allowance_minutes = grace
        chore.mandatory = mandatory
        chore.mandatory_penalty_points = 2 if mandatory else 0
        chore.weekly_target = weekly_target
        run(coord.async_update_chore(chore))
    return coord, storage, mod, kid, storage.get_chore(chore.id)


def _complete(coord, mod, chore, kid, when, **kw):
    with patch.object(mod.dt_util, "now", return_value=when):
        return run(coord.async_complete_chore(chore.id, kid.id, **kw))


# ── validation ───────────────────────────────────────────────────────────────


def test_valid_times_are_normalised_and_sorted():
    times = validate_chore_times(
        [{"name": "Late", "start": "18:00", "end": "19:00"}, {"name": "Early", "start": "7:05", "end": "08:00"}]
    )
    assert [t.name for t in times] == ["Early", "Late"]
    assert times[0].start == "07:05"
    assert all(t.id for t in times)


@pytest.mark.parametrize(
    "raw,kwargs,message",
    [
        ([{"start": f"{h:02d}:00", "end": f"{h:02d}:30"} for h in range(6)], {}, "at most 5"),
        ([{"start": "09:00", "end": "08:00"}], {}, "close after it opens"),
        ([{"start": "09:00", "end": "09:00"}], {}, "close after it opens"),
        ([{"start": "07:00", "end": "09:00"}, {"start": "08:30", "end": "10:00"}], {}, "overlap"),
        ([{"start": "7am", "end": "9am"}], {}, "like 07:30"),
        ([{"start": "07:00", "end": "08:00"}], {"task_type": "timed"}, "timed"),
        ([{"start": "07:00", "end": "08:00"}], {"open_ended": True}, "open-ended"),
        ([{"start": "07:00", "end": "08:00"}], {"quantity_unit": "pages"}, "quantity"),
        ([{"start": "07:00", "end": "08:00"}], {"team_size": 2}, "teamwork"),
    ],
)
def test_invalid_times_are_refused(raw, kwargs, message):
    with pytest.raises(ValueError, match=message):
        validate_chore_times(raw, **kwargs)


def test_touching_times_are_not_an_overlap():
    assert len(validate_chore_times([{"start": "07:00", "end": "08:00"}, {"start": "08:00", "end": "09:00"}])) == 2


def test_empty_times_mean_an_ordinary_chore():
    assert validate_chore_times(None) == []
    assert validate_chore_times([]) == []


def test_loading_drops_broken_times_instead_of_raising():
    cleaned = clean_chore_times(
        [
            {"id": "a", "start": "07:00", "end": "08:00"},
            {"id": "b", "start": "10:00", "end": "09:00"},  # backwards
            {"id": "c", "start": "07:30", "end": "07:45"},  # overlaps a
            "junk",
            {"id": "d", "start": "18:00", "end": "19:00"},
        ]
    )
    assert [t.id for t in cleaned] == ["a", "d"]


def test_editing_a_chore_with_bad_times_changes_nothing():
    coord, storage, mod, kid, chore = _setup()
    chore.times = [{"start": "09:00", "end": "08:00"}]
    with patch.object(mod.dt_util, "now", return_value=at(6)), pytest.raises(ValueError):
        run(coord.async_update_chore(chore))


def test_times_bonus_is_cleared_when_times_are():
    coord, storage, mod, kid, chore = _setup(bonus=3)
    chore.times = []
    with patch.object(mod.dt_util, "now", return_value=at(6)):
        run(coord.async_update_chore(chore))
    assert storage.get_chore(chore.id).times_bonus == 0


# ── round trips ──────────────────────────────────────────────────────────────


def test_chore_times_round_trip_through_storage():
    chore = Chore(
        name="Teeth", times=[ChoreTime(name="Morning", start="07:00", end="08:00", points=2, id="m")], times_bonus=3
    )
    back = Chore.from_dict(chore.to_dict())
    assert [t.to_dict() for t in back.times] == [
        {"id": "m", "name": "Morning", "start": "07:00", "end": "08:00", "points": 2}
    ]
    assert back.times_bonus == 3


def test_ordinary_chores_load_with_no_times():
    assert Chore.from_dict({"name": "Bed"}).times == []


def test_completion_and_miss_carry_their_time_only_when_set():
    comp = ChoreCompletion(chore_id="c", child_id="k", completed_at=at(8), time_id="b")
    assert ChoreCompletion.from_dict(comp.to_dict()).time_id == "b"
    assert "time_id" not in ChoreCompletion(chore_id="c", child_id="k", completed_at=at(8)).to_dict()
    miss = MandatoryMiss(chore_id="c", child_id="k", due_date="2024-03-20", period_id="set_time", time_id="l")
    assert MandatoryMiss.from_dict(miss.to_dict()).time_id == "l"
    assert "time_id" not in MandatoryMiss(chore_id="c", child_id="k", due_date="x", period_id="morning").to_dict()


def test_backup_round_trip_keeps_the_times():
    coord, storage, mod, kid, chore = _setup(bonus=3)
    _complete(coord, mod, chore, kid, at(8))
    exported = coord.export_config()
    coord2, storage2, _ = _system()
    run(coord2.async_import_config(exported))
    restored = storage2.get_chore(chore.id)
    assert [t.id for t in restored.times] == ["b", "l", "d"]
    assert restored.times_bonus == 3
    assert [c.time_id for c in storage2.get_completions()] == ["b"]


# ── ticking a time ───────────────────────────────────────────────────────────


def test_a_tick_goes_to_the_time_open_now_and_pays_its_points():
    coord, storage, mod, kid, chore = _setup()
    comp = _complete(coord, mod, chore, kid, at(12, 30))
    assert comp is not None and comp.time_id == "l"
    assert storage.get_child(kid.id).points == 1


def test_a_child_cannot_tick_outside_every_window():
    coord, storage, mod, kid, chore = _setup()
    assert _complete(coord, mod, chore, kid, at(10)) is None
    assert storage.get_completions() == []


def test_each_time_only_once_a_day():
    coord, storage, mod, kid, chore = _setup()
    assert _complete(coord, mod, chore, kid, at(7, 30)) is not None
    assert _complete(coord, mod, chore, kid, at(8, 30)) is None
    assert len(storage.get_completions()) == 1


def test_a_named_time_must_be_open_for_a_child():
    coord, storage, mod, kid, chore = _setup()
    assert _complete(coord, mod, chore, kid, at(7, 30), time_id="d") is None
    assert _complete(coord, mod, chore, kid, at(17, 45), time_id="d").time_id == "d"


def test_an_unknown_time_is_an_error():
    coord, storage, mod, kid, chore = _setup()
    with pytest.raises(ValueError):
        _complete(coord, mod, chore, kid, at(7, 30), time_id="nope")


def test_the_claim_allowance_applies_to_each_time():
    coord, storage, mod, kid, chore = _setup(grace=15)
    assert _complete(coord, mod, chore, kid, at(13, 40)).time_id == "l"
    assert _complete(coord, mod, chore, kid, at(19, 20)) is None  # dinner closed at 19:15


def test_a_parent_may_tick_a_closed_time():
    coord, storage, mod, kid, chore = _setup()
    comp = _complete(coord, mod, chore, kid, at(10), as_parent=True)
    assert comp.time_id == "b"  # the latest one that has started
    comp = _complete(coord, mod, chore, kid, at(10), as_parent=True, time_id="d")
    assert comp.time_id == "d"  # any time not done yet, even one to come


def test_each_time_can_be_undone_on_its_own():
    coord, storage, mod, kid, chore = _setup()
    first = _complete(coord, mod, chore, kid, at(8))
    _complete(coord, mod, chore, kid, at(12, 15))
    with patch.object(mod.dt_util, "now", return_value=at(12, 20)):
        run(coord.async_reject_chore(first.id))
    assert [c.time_id for c in storage.get_completions()] == ["l"]
    assert storage.get_child(kid.id).points == 1


def test_approval_needed_keeps_each_time_pending():
    coord, storage, mod, kid, chore = _setup(approval=True)
    comp = _complete(coord, mod, chore, kid, at(8))
    assert comp.approved is False
    with patch.object(mod.dt_util, "now", return_value=at(8)):
        assert coord.set_time_states(chore, kid.id) == {"b": "pending", "l": "later", "d": "later"}
        run(coord.async_approve_chore(comp.id))
        assert coord.set_time_states(chore, kid.id)["b"] == "done"


def test_states_follow_the_clock():
    coord, storage, mod, kid, chore = _setup()
    with patch.object(mod.dt_util, "now", return_value=at(12, 10)):
        assert coord.set_time_states(chore, kid.id) == {"b": "missed", "l": "now", "d": "later"}


# ── the day counts once ──────────────────────────────────────────────────────


def test_the_streak_moves_only_when_every_time_is_done():
    coord, storage, mod, kid, chore = _setup()
    _complete(coord, mod, chore, kid, at(8))
    _complete(coord, mod, chore, kid, at(12, 10))
    assert storage.get_child(kid.id).current_streak == 0
    _complete(coord, mod, chore, kid, at(18))
    assert storage.get_child(kid.id).current_streak == 1


def test_undoing_a_time_after_the_day_was_full_takes_the_streak_back():
    coord, storage, mod, kid, chore = _setup()
    _complete(coord, mod, chore, kid, at(8))
    _complete(coord, mod, chore, kid, at(12, 10))
    last = _complete(coord, mod, chore, kid, at(18))
    with patch.object(mod.dt_util, "now", return_value=at(18, 5)):
        run(coord.async_reject_chore(last.id))
    assert storage.get_child(kid.id).current_streak == 0


def test_undoing_a_partial_day_leaves_the_streak_alone():
    coord, storage, mod, kid, chore = _setup()
    child = storage.get_child(kid.id)
    child.current_streak = 4
    child.last_completion_date = (DAY - dt.timedelta(days=1)).isoformat()
    storage.update_child(child)
    first = _complete(coord, mod, chore, kid, at(8))
    assert storage.get_child(kid.id).current_streak == 4  # a partial day doesn't move it
    with patch.object(mod.dt_util, "now", return_value=at(8, 5)):
        run(coord.async_reject_chore(first.id))
    assert storage.get_child(kid.id).current_streak == 4


def test_the_weekly_target_counts_full_days_once():
    coord, storage, mod, kid, chore = _setup(weekly_target=2)
    monday = DAY - dt.timedelta(days=2)
    for h in (8, 12, 18):
        _complete(coord, mod, chore, kid, at(h, 15, day=monday))
    _complete(coord, mod, chore, kid, at(8))  # today: breakfast only
    with patch.object(mod.dt_util, "now", return_value=at(8, 30)):
        assert coord.weekly_completion_count(chore.id, kid.id) == 1
        assert not coord.weekly_target_met(chore, kid.id)


def test_still_due_until_every_time_is_done_or_closed():
    coord, storage, mod, kid, chore = _setup()

    def due(when):
        with patch.object(mod.dt_util, "now", return_value=when):
            return [c.id for c in coord.get_due_chores_for_child(kid.id)]

    assert due(at(10)) == [chore.id]  # breakfast missed, lunch and dinner to come
    _complete(coord, mod, chore, kid, at(18))
    assert due(at(18, 5)) == []  # dinner done, the rest closed
    assert due(at(20)) == []


# ── the all-times bonus ──────────────────────────────────────────────────────


def test_the_bonus_is_paid_once_when_every_time_is_done():
    coord, storage, mod, kid, chore = _setup(bonus=3)
    _complete(coord, mod, chore, kid, at(8))
    _complete(coord, mod, chore, kid, at(12, 10))
    assert storage.get_child(kid.id).points == 2
    _complete(coord, mod, chore, kid, at(18))
    assert storage.get_child(kid.id).points == 1 + 1 + 2 + 3
    reasons = [t.reason for t in storage.get_points_transactions()]
    assert reasons.count("All times done: Wash hands") == 1


def test_undoing_a_time_takes_the_bonus_back():
    coord, storage, mod, kid, chore = _setup(bonus=3)
    _complete(coord, mod, chore, kid, at(8))
    _complete(coord, mod, chore, kid, at(12, 10))
    last = _complete(coord, mod, chore, kid, at(18))
    with patch.object(mod.dt_util, "now", return_value=at(18, 5)):
        run(coord.async_reject_chore(last.id))
    assert storage.get_child(kid.id).points == 2


def test_no_bonus_while_a_time_waits_for_approval():
    coord, storage, mod, kid, chore = _setup(bonus=3, approval=True)
    comps = [_complete(coord, mod, chore, kid, at(h, 10)) for h in (8, 12, 18)]
    with patch.object(mod.dt_util, "now", return_value=at(18, 20)):
        run(coord.async_approve_chore(comps[0].id))
        run(coord.async_approve_chore(comps[1].id))
        assert storage.get_child(kid.id).points == 2
        run(coord.async_approve_chore(comps[2].id))
    assert storage.get_child(kid.id).points == 1 + 1 + 2 + 3


# ── mandatory: one miss per time ─────────────────────────────────────────────


def test_a_mandatory_chore_owes_a_miss_per_closed_time():
    coord, storage, mod, kid, chore = _setup(mandatory=True)
    _complete(coord, mod, chore, kid, at(8))
    with patch.object(mod.dt_util, "now", return_value=at(14)):
        assert run(coord.async_detect_set_time_misses()) == 1  # lunch
        assert run(coord.async_detect_set_time_misses()) == 0  # idempotent
    misses = storage.get_mandatory_misses()
    assert [(m.time_id, m.period_id) for m in misses] == [("l", "set_time")]
    assert coord.mandatory_misses_state()[0]["chore_name"] == "Wash hands (Lunch)"


def test_period_detection_leaves_set_time_chores_alone():
    coord, storage, mod, kid, chore = _setup(mandatory=True)
    with patch.object(mod.dt_util, "now", return_value=at(23)):
        for period in ("morning", "afternoon", "evening", "night", "anytime"):
            run(coord.async_detect_mandatory_misses(period, DAY))
    assert storage.get_mandatory_misses() == []


def test_yesterdays_unfinished_times_are_caught_at_midnight():
    coord, storage, mod, kid, chore = _setup(mandatory=True)
    with patch.object(mod.dt_util, "now", return_value=at(0, 0, day=DAY + dt.timedelta(days=1))):
        run(coord.async_detect_anytime_mandatory_misses())
    assert sorted(m.time_id for m in storage.get_mandatory_misses()) == ["b", "d", "l"]


def test_a_hidden_set_time_chore_owes_no_miss():
    """#1151: a chore its visibility entity hides is not due, so not missed."""
    coord, storage, mod, kid, chore = _setup(mandatory=True)
    chore.visibility_entity = "binary_sensor.away"
    chore.visibility_state = "off"
    with patch.object(mod.dt_util, "now", return_value=at(6)):
        run(coord.async_update_chore(chore))
    hidden = type("S", (), {"state": "on", "attributes": {}})()
    coord.hass.states = type(
        "FakeStates", (), {"get": lambda self, eid: hidden if eid == "binary_sensor.away" else None}
    )()
    with patch.object(mod.dt_util, "now", return_value=at(23)):
        assert run(coord.async_detect_set_time_misses()) == 0
    assert storage.get_mandatory_misses() == []


# ── labels and the sensor ────────────────────────────────────────────────────


def test_labels_name_the_time():
    chore = Chore(name="Wash hands", times=[ChoreTime(name="Lunch", start="12:00", end="13:00", id="l")])
    assert set_time_label(chore, "l") == "Wash hands (Lunch)"
    assert set_time_label(chore, "") == "Wash hands"
    assert set_time_label(chore, "gone") == "Wash hands"


def test_the_chores_sensor_carries_times_only_for_chores_that_have_them():
    coord, storage, mod, kid, chore = _setup(bonus=3)
    with patch.object(mod.dt_util, "now", return_value=at(6)):
        plain = run(coord.async_add_chore("Make bed", points=2, requires_approval=False))
    _complete(coord, mod, chore, kid, at(8))
    common = {
        "chores": storage.get_chores(),
        "hass": coord.hass,
        "child_lookup": {c.id: c for c in storage.get_children()},
    }
    coord.data = {"chores": storage.get_chores(), "children": storage.get_children()}
    with patch.object(mod.dt_util, "now", return_value=at(8, 5)):
        records = {r["id"]: r for r in sensor_module._build_chores_list(coord, common)}
    assert "times" not in records[plain.id] and "time_done" not in records[plain.id]
    rec = records[chore.id]
    assert [t["id"] for t in rec["times"]] == ["b", "l", "d"]
    assert rec["times_bonus"] == 3
    assert rec["time_done"] == {kid.id: {"b": "done"}}


def test_todays_completions_name_the_time():
    coord, storage, mod, kid, chore = _setup()
    _complete(coord, mod, chore, kid, at(12, 10))
    common = {
        "all_completions": storage.get_completions(),
        "child_lookup": {c.id: c for c in storage.get_children()},
        "chore_lookup": {c.id: c for c in storage.get_chores()},
    }
    with patch.object(sensor_module.dt_util, "now", return_value=at(12, 20)):
        rows = sensor_module._build_todays_completions(common)
    assert rows[0]["chore_name"] == "Wash hands (Lunch)"
    assert rows[0]["time_id"] == "l"


def test_the_today_board_shows_each_time():
    coord, storage, mod, kid, chore = _setup()
    _complete(coord, mod, chore, kid, at(8))
    with patch.object(mod.dt_util, "now", return_value=at(12, 10)):
        board = coord.get_today_board()
    item = next(i for i in board["children"][0]["chores"] if i["chore_id"] == chore.id)
    assert item["status"] == "todo"
    assert [(t["id"], t["state"]) for t in item["times"]] == [("b", "done"), ("l", "now"), ("d", "later")]


def test_a_mock_chore_is_never_mistaken_for_one_with_times():
    # Plenty of tests hand the coordinator a MagicMock chore; its `times`
    # attribute is a MagicMock, not a list, so it must not count.
    from custom_components.taskmate.coord_set_times import chore_has_times

    assert chore_has_times(MagicMock()) is False


def test_reticking_a_rejected_time_restores_the_streak():
    # ha-dev E2E: streak 1 earned earlier today, all three times ticked, one
    # rejected, then ticked again. The re-tick finishes the day once more, so
    # the streak must come back; the sibling times still standing today must
    # not keep last_completion_date on today and block it.
    coord, storage, mod, kid, chore = _setup(bonus=2)
    child = storage.get_child(kid.id)
    child.current_streak = 1
    child.last_completion_date = DAY.isoformat()
    storage.update_child(child)
    _complete(coord, mod, chore, kid, at(17, 45), as_parent=True, time_id="d")
    first = _complete(coord, mod, chore, kid, at(17, 45), as_parent=True, time_id="b")
    _complete(coord, mod, chore, kid, at(17, 45), as_parent=True, time_id="l")
    assert storage.get_child(kid.id).current_streak == 1
    with patch.object(mod.dt_util, "now", return_value=at(17, 50)):
        run(coord.async_reject_chore(first.id))
    _complete(coord, mod, chore, kid, at(17, 55), as_parent=True, time_id="b")
    assert storage.get_child(kid.id).current_streak == 1
    assert storage.get_child(kid.id).points == 1 + 1 + 2 + 2


# ── editing times keeps their ids (and today's ticks) ────────────────────────


def test_a_time_sent_without_an_id_keeps_the_stored_id_by_name():
    old = [
        ChoreTime(name="Before", start="07:00", end="08:00", id="b"),
        ChoreTime(name="Now", start="12:00", end="13:00", id="n"),
    ]
    new = validate_chore_times(
        [{"name": " before ", "start": "06:30", "end": "08:30"}, {"name": "NOW", "start": "12:15", "end": "13:15"}],
        existing=old,
    )
    assert [t.id for t in new] == ["b", "n"]
    assert new[0].start == "06:30"  # the window moved, the id didn't


def test_without_a_name_match_the_same_start_keeps_the_id():
    old = [ChoreTime(name="Lunch", start="12:00", end="13:00", id="l")]
    assert validate_chore_times([{"name": "Midday", "start": "12:00", "end": "12:45"}], existing=old)[0].id == "l"


def test_a_genuinely_new_time_gets_a_new_id():
    old = [ChoreTime(name="Lunch", start="12:00", end="13:00", id="l")]
    new = validate_chore_times(
        [{"name": "Lunch", "start": "12:00", "end": "13:00"}, {"name": "Supper", "start": "18:00", "end": "19:00"}],
        existing=old,
    )
    assert new[0].id == "l" and new[1].id not in ("", "l")


def test_a_sent_id_is_never_given_to_another_time():
    old = [ChoreTime(name="Lunch", start="12:00", end="13:00", id="l")]
    new = validate_chore_times(
        [
            {"id": "l", "name": "Lunch", "start": "12:00", "end": "13:00"},
            {"name": "Lunch", "start": "18:00", "end": "19:00"},
        ],
        existing=old,
    )
    assert new[0].id == "l" and new[1].id != "l"


def test_resending_the_times_without_ids_keeps_todays_ticks():
    coord, storage, mod, kid, chore = _setup()
    _complete(coord, mod, chore, kid, at(8))
    _complete(coord, mod, chore, kid, at(12, 10))
    stored = storage.get_chore(chore.id)
    stored.times = [{k: v for k, v in t.items() if k != "id"} for t in MEALS]
    stored.times[1]["end"] = "14:00"  # move a window mid-day
    with patch.object(mod.dt_util, "now", return_value=at(12, 20)):
        run(coord.async_update_chore(stored))
        assert [t.id for t in storage.get_chore(chore.id).times] == ["b", "l", "d"]
        assert coord.set_time_states(storage.get_chore(chore.id), kid.id) == {"b": "done", "l": "done", "d": "later"}
