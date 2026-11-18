"""Minimum days between completions (#1267).

"Twice a week, on days the child picks, but never two days in a row": after a
completion the chore rests for that child until ``min_days_between`` days
later, midnight-rounded. 0 and 1 both mean off.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import patch

import pytest
import voluptuous as vol

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.models import Chore, ChoreCompletion

from .test_completion_eligibility import UTC, _make_system, run

WED = dt.datetime(2024, 3, 20, 12, 0, tzinfo=UTC)  # a Wednesday


def _day(offset, hour=10):
    return WED.replace(hour=hour) + dt.timedelta(days=offset)


def _system():
    coord, storage, mod = _make_system()
    with patch.object(mod.dt_util, "now", return_value=WED):
        kid = run(coord.async_add_child("Malia"))
        sib = run(coord.async_add_child("Vaiha"))
    return coord, storage, mod, kid, sib


def _chore(coord, mod, gap=2, **kw):
    kw.setdefault("schedule_mode", "specific_days")
    with patch.object(mod.dt_util, "now", return_value=WED):
        chore = run(coord.async_add_chore("Hoover under the table", points=2, **kw))
    chore.created_date = "2024-01-01"
    chore.min_days_between = gap
    chore.requires_approval = False
    coord.storage.update_chore(chore)
    return chore


def _done(storage, chore, child, *offsets, approved=True, bonus="", child_id=None, for_child_id=""):
    for off in offsets:
        storage.add_completion(
            ChoreCompletion(
                chore_id=chore.id,
                child_id=child_id or child.id,
                for_child_id=for_child_id,
                completed_at=_day(off),
                approved=approved,
                bonus_subtask_id=bonus,
            )
        )


def _at(mod, offset=0):
    return patch.object(mod.dt_util, "now", return_value=_day(offset, 12))


# ── the field ────────────────────────────────────────────────────────────────


def test_defaults_to_off_and_round_trips():
    assert Chore(name="x", id="a").min_days_between == 0
    assert Chore.from_dict(Chore(name="x", id="a", min_days_between=3).to_dict()).min_days_between == 3


def test_editable_over_the_websocket():
    from custom_components.taskmate.websocket import _CHORE_EDITABLE_FIELDS, _chore_payload_schema

    assert "min_days_between" in _CHORE_EDITABLE_FIELDS
    schema = vol.Schema(_chore_payload_schema(require_name=False))
    assert schema({"min_days_between": 0})["min_days_between"] == 0
    assert schema({"min_days_between": 2})["min_days_between"] == 2
    for bad in (-1, 32):
        with pytest.raises(vol.Invalid):
            schema({"min_days_between": bad})


# ── availability today ───────────────────────────────────────────────────────


class TestAvailability:
    def test_rests_the_day_after_a_completion(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -1)
        with _at(mod):
            assert coord.is_chore_available_for_child(chore, kid.id) is False
            assert coord.min_gap_rest_until(chore, kid.id) == _day(1).date()

    def test_open_again_once_the_gap_has_passed(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -2)
        with _at(mod):
            assert coord.is_chore_available_for_child(chore, kid.id) is True

    def test_todays_own_completion_is_left_to_the_daily_limit(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, 0)
        with _at(mod):
            assert coord.min_gap_rest_until(chore, kid.id) is None

    def test_a_longer_gap(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod, gap=4)
        _done(storage, chore, kid, -3)
        with _at(mod):
            assert coord.min_gap_rest_until(chore, kid.id) == _day(1).date()
        with _at(mod, 1):
            assert coord.min_gap_rest_until(chore, kid.id) is None

    @pytest.mark.parametrize("gap", [0, 1])
    def test_zero_and_one_are_off(self, gap):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod, gap=gap)
        _done(storage, chore, kid, -1)
        with _at(mod):
            assert coord.is_chore_available_for_child(chore, kid.id) is True

    def test_per_child(self):
        coord, storage, mod, kid, sib = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -1)
        with _at(mod):
            assert coord.is_chore_available_for_child(chore, sib.id) is True

    def test_pending_completions_count(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -1, approved=False)
        with _at(mod):
            assert coord.is_chore_available_for_child(chore, kid.id) is False

    def test_bonus_subtasks_do_not_count(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -1, bonus="bs1")
        with _at(mod):
            assert coord.is_chore_available_for_child(chore, kid.id) is True

    def test_a_parent_completion_for_the_child_counts(self):
        coord, storage, mod, kid, sib = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -1, child_id="__parent__", for_child_id=kid.id)
        with _at(mod):
            assert coord.is_chore_available_for_child(chore, kid.id) is False
            assert coord.is_chore_available_for_child(chore, sib.id) is True


# ── completing ───────────────────────────────────────────────────────────────


class TestCompleting:
    def test_refused_while_resting(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -1)
        with _at(mod):
            assert run(coord.async_complete_chore(chore.id, kid.id)) is None
        assert len(storage.get_completions()) == 1

    def test_parents_are_held_to_it_too(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -1)
        with _at(mod):
            assert run(coord.async_complete_chore(chore.id, kid.id, as_parent=True)) is None

    def test_allowed_after_the_gap(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -2)
        with _at(mod):
            assert run(coord.async_complete_chore(chore.id, kid.id)) is not None


# ── tomorrow, and "due" days ────────────────────────────────────────────────


class TestDueDays:
    def test_tomorrow_preview_leaves_out_a_chore_still_resting(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod, gap=3)
        _done(storage, chore, kid, 0)
        with _at(mod):
            assert chore.id not in coord.tomorrow_chore_ids(kid.id)

    def test_tomorrow_preview_lists_it_when_the_rest_ends(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -1)
        with _at(mod):
            assert chore.id in coord.tomorrow_chore_ids(kid.id)

    def test_a_resting_day_is_not_owed(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -1)
        due = coord._due_chore_ids_for_child(kid.id, _day(0).date(), include_rotation=True)
        assert chore.id not in due
        assert chore.id in coord._due_chore_ids_for_child(kid.id, _day(1).date(), include_rotation=True)


# ── when it opens again ──────────────────────────────────────────────────────


class TestNextOpen:
    def test_set_days_chore(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod, gap=3)
        _done(storage, chore, kid, -1)
        with _at(mod):
            assert coord.chore_next_open(chore, kid.id) == _day(2).date()

    def test_recurring_chore_waits_for_both(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod, gap=5, schedule_mode="recurring", recurrence="every_2_days")
        _done(storage, chore, kid, -1)
        storage.set_last_completed(chore.id, kid.id, _day(-1).isoformat())
        with _at(mod):
            assert coord.chore_next_open(chore, kid.id) == _day(4).date()

    def test_sensor_carries_it_for_the_child_card(self):
        coord, storage, mod, kid, sib = _system()
        chore = _chore(coord, mod, gap=3)
        _done(storage, chore, kid, -1)
        common = {"chores": storage.get_chores(), "children": storage.get_children()}
        with _at(mod):
            availability = sensor_module._build_chore_availability(coord, common)
            out = sensor_module._build_chore_next_open(coord, common, availability)
        assert out == {chore.id: {kid.id: _day(2).date().isoformat()}}

    def test_chore_record_carries_the_gap_only_when_on(self):
        coord, storage, mod, kid, _ = _system()
        on = _chore(coord, mod, gap=2)
        off = _chore(coord, mod, gap=0)
        with _at(mod):
            records = {
                r["id"]: r for r in sensor_module._build_chores_list(coord, {"chores": [on, off], "hass": coord.hass})
            }
        assert records[on.id]["min_days_between"] == 2
        assert "min_days_between" not in records[off.id]


# ── logging a past day ───────────────────────────────────────────────────────


class TestBackdate:
    def test_refused_next_to_another_go(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -1)
        with _at(mod), pytest.raises(ValueError) as err:
            run(coord.async_complete_chore_on_date(chore.id, kid.id, _day(-2).date()))
        assert getattr(err.value, "translation_key", "") == "backdate_min_days_between"

    def test_refused_before_a_later_go_too(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -2)
        with _at(mod), pytest.raises(ValueError):
            run(coord.async_complete_chore_on_date(chore.id, kid.id, _day(-1).date()))

    def test_allowed_with_a_day_off_between(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -1)
        with _at(mod):
            assert run(coord.async_complete_chore_on_date(chore.id, kid.id, _day(-3).date())) is not None
