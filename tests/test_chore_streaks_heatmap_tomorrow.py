"""Per-chore streaks, the completion heatmap and the tomorrow preview."""

from __future__ import annotations

import datetime as dt
import json
from types import SimpleNamespace
from unittest.mock import patch

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.models import ChoreCompletion

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


def _chore(coord, mod, name="Make bed", **kw):
    kw.setdefault("schedule_mode", "specific_days")
    with patch.object(mod.dt_util, "now", return_value=WED):
        chore = run(coord.async_add_chore(name, points=2, **kw))
    chore.created_date = "2024-01-01"
    coord.storage.update_chore(chore)
    return chore


def _done(storage, chore, child, *offsets, approved=True, bonus=""):
    for off in offsets:
        storage.add_completion(
            ChoreCompletion(
                chore_id=chore.id, child_id=child.id, completed_at=_day(off), approved=approved, bonus_subtask_id=bonus
            )
        )


def _streaks(coord, mod, today_offset=0):
    with patch.object(mod.dt_util, "now", return_value=_day(today_offset, 12)):
        return coord.chore_streaks(
            coord.storage.get_children(), coord.storage.get_chores(), coord.storage.get_completions()
        )


class TestPerChoreStreaks:
    def test_daily_chore_counts_consecutive_days_including_today(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -3, -2, -1, 0)
        assert _streaks(coord, mod)[kid.id] == {chore.id: 4}

    def test_today_not_done_yet_does_not_break_it(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -3, -2, -1)
        assert _streaks(coord, mod)[kid.id][chore.id] == 3

    def test_a_missed_due_day_breaks_it(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -5, -4, -2, -1)
        assert _streaks(coord, mod)[kid.id][chore.id] == 2

    def test_mon_wed_fri_chore_is_not_broken_on_tuesday(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod, due_days=["monday", "wednesday", "friday"])
        # Fri 15th, Mon 18th, Wed 20th (today) — Sat/Sun/Tue were never due.
        _done(storage, chore, kid, -5, -2, 0)
        assert _streaks(coord, mod)[kid.id][chore.id] == 3

    def test_a_single_day_is_not_published(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, 0)
        assert kid.id not in _streaks(coord, mod)

    def test_bonus_subtasks_and_unassigned_children_do_not_count(self):
        coord, storage, mod, kid, sib = _system()
        chore = _chore(coord, mod, assigned_to=[sib.id])
        _done(storage, chore, kid, -1, 0)
        assert kid.id not in _streaks(coord, mod)
        other = _chore(coord, mod, "Tidy room")
        _done(storage, other, sib, -1, 0, bonus="b1")
        assert other.id not in _streaks(coord, mod).get(sib.id, {})

    def test_pending_completions_count(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -1, 0, approved=False)
        assert _streaks(coord, mod)[kid.id][chore.id] == 2

    def test_a_sick_day_neither_counts_nor_breaks(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -3, -1, 0)
        storage.get_section("sick_days", dict)[kid.id] = [_day(-2).date().isoformat()]
        assert _streaks(coord, mod)[kid.id][chore.id] == 3

    def test_turn_taking_chore_skips_days_a_sibling_did_it(self):
        coord, storage, mod, kid, sib = _system()
        chore = _chore(coord, mod, assignment_mode="alternating")
        _done(storage, chore, kid, -4, -2, 0)
        _done(storage, chore, sib, -3, -1)
        assert _streaks(coord, mod)[kid.id][chore.id] == 3

    def test_weekly_target_chores_have_no_daily_streak(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        chore.weekly_target = 3
        storage.update_chore(chore)
        _done(storage, chore, kid, -2, -1, 0)
        assert kid.id not in _streaks(coord, mod)


class TestHeatmap:
    def test_counts_per_day_oldest_first_ending_today(self):
        coord, storage, mod, kid, sib = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -41, -1, 0, 0)
        _done(storage, chore, kid, -42)  # outside the six weeks
        _done(storage, chore, sib, 0, bonus="b")  # a bonus sub-task isn't a chore
        with patch.object(mod.dt_util, "now", return_value=WED):
            heat = coord.completion_heatmap(storage.get_completions())
        assert set(heat) == {kid.id}
        series = heat[kid.id]
        assert len(series) == 42 and series[0] == 1 and series[-2] == 1 and series[-1] == 2 and sum(series) == 4

    def test_report_lists_every_child_with_totals(self):
        coord, storage, mod, kid, sib = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, -1, 0, 0)
        with patch.object(mod.dt_util, "now", return_value=WED):
            report = coord.heatmap_report(28)
        assert report["days"] == 28 and report["end"] == "2024-03-20" and report["start"] == "2024-02-22"
        rows = {r["id"]: r for r in report["children"]}
        assert rows[kid.id]["total"] == 3 and rows[kid.id]["active_days"] == 2 and rows[kid.id]["best"] == 2
        assert rows[sib.id]["total"] == 0 and len(rows[sib.id]["counts"]) == 28


class TestTomorrow:
    def test_lists_chores_due_tomorrow_only(self):
        coord, _storage, mod, kid, _ = _system()
        daily = _chore(coord, mod, "Make bed")
        thursday = _chore(coord, mod, "Bins", due_days=["thursday"])
        friday = _chore(coord, mod, "Hoover", due_days=["friday"])
        with patch.object(mod.dt_util, "now", return_value=WED):
            ids = coord.tomorrow_chore_ids(kid.id)
        assert daily.id in ids and thursday.id in ids and friday.id not in ids

    def test_respects_assignment_and_turn_taking(self):
        coord, _storage, mod, kid, sib = _system()
        mine = _chore(coord, mod, "Mine", assigned_to=[sib.id])
        with patch.object(mod.dt_util, "now", return_value=WED):
            assert mine.id not in coord.tomorrow_chore_ids(kid.id)
            assert mine.id in coord.tomorrow_chore_ids(sib.id)

    def test_nothing_on_a_holiday(self):
        coord, storage, mod, kid, _ = _system()
        _chore(coord, mod)
        storage.set_setting("vacation_periods", [{"start": "2024-03-21", "end": "2024-03-22"}])
        with patch.object(mod.dt_util, "now", return_value=WED):
            assert coord.tomorrow_chore_ids(kid.id) == []

    def test_a_one_off_dated_tomorrow(self):
        coord, storage, mod, kid, _ = _system()
        once = _chore(coord, mod, "Once", schedule_mode="one_shot")
        once.created_date = "2024-03-21"
        storage.update_chore(once)
        with patch.object(mod.dt_util, "now", return_value=WED):
            assert coord.tomorrow_chore_ids(kid.id) == [once.id]


class TestSensor:
    def _summary(self, coord, mod):
        with patch.object(mod.dt_util, "now", return_value=WED):
            coord.data = run(coord._async_update_data())
            common = sensor_module._compute_common(coord)
            return {c["id"]: c for c in sensor_module._build_children_summary(coord, common)}

    def test_summary_carries_streaks_and_tomorrow_only_when_set(self):
        coord, storage, mod, kid, sib = _system()
        chore = _chore(coord, mod, assigned_to=[kid.id])
        _done(storage, chore, kid, -1, 0)
        summary = self._summary(coord, mod)
        assert summary[kid.id]["chore_streaks"] == {chore.id: 2}
        assert summary[kid.id]["tomorrow"] == [chore.id]
        assert "chore_streaks" not in summary[sib.id] and "tomorrow" not in summary[sib.id]

    def test_heatmap_is_on_the_activity_sensor(self):
        coord, storage, mod, kid, _ = _system()
        chore = _chore(coord, mod)
        _done(storage, chore, kid, 0)
        with patch.object(mod.dt_util, "now", return_value=WED):
            coord.data = run(coord._async_update_data())
            sensor = sensor_module.TaskMateActivitySensor(coord, SimpleNamespace(entry_id="e"))
            attrs = sensor._build_attributes()
        heat = attrs["completion_heatmap"]
        assert heat["end"] == "2024-03-20" and heat["children"][kid.id][-1] == 1
        assert "completion_heatmap" in sensor._unrecorded_attributes

    def test_streaks_and_tomorrow_stay_small_for_a_big_family(self):
        # 30 chores, four children: the per-child additions stay a few hundred bytes.
        streaks = {f"{i:016x}": 30 for i in range(30)}
        tomorrow = [f"{i:016x}" for i in range(30)]
        assert len(json.dumps({"chore_streaks": streaks, "tomorrow": tomorrow})) < 2000
