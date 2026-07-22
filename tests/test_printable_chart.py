"""Printable weekly chore chart (#689).

A sheet for the fridge. Pure string building, so the layout is testable
without a Home Assistant install.
"""
from __future__ import annotations

from datetime import date

from custom_components.taskmate import printable

MON = date(2026, 7, 20)  # a Monday


def _child(name="Ella", cid="a"):
    return {"id": cid, "name": name}


def _chore(name="Make bed", **over):
    chore = {"name": name, "enabled": True, "schedule_mode": "specific_days",
             "due_days": [], "assigned_to": []}
    chore.update(over)
    return chore


class TestWeekStart:
    def test_monday_start_from_midweek(self):
        assert printable.week_start(date(2026, 7, 22)) == MON

    def test_monday_start_on_a_monday_is_itself(self):
        assert printable.week_start(MON) == MON

    def test_sunday_start(self):
        assert printable.week_start(date(2026, 7, 22), "sunday") == date(2026, 7, 19)


class TestOrientation:
    def test_portrait_is_the_default(self):
        html = printable.build_chart([_child()], [_chore()], MON)
        assert "size: A4 portrait" in html

    def test_landscape_is_honoured(self):
        html = printable.build_chart([_child()], [_chore()], MON, orientation="landscape")
        assert "size: A4 landscape" in html

    def test_an_unknown_orientation_falls_back_to_portrait(self):
        html = printable.build_chart([_child()], [_chore()], MON, orientation="sideways")
        assert "size: A4 portrait" in html


class TestContent:
    def test_all_seven_days_are_columns(self):
        html = printable.build_chart([_child()], [_chore()], MON)
        for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"):
            assert f">{day}<" in html

    def test_child_names_appear(self):
        html = printable.build_chart([_child("Ella"), _child("Sam", "b")], [_chore()], MON)
        assert "Ella" in html and "Sam" in html

    def test_a_chore_is_shown_on_its_days_only(self):
        html = printable.build_chart([_child()], [_chore("Bins", due_days=["tuesday"])], MON)
        # One tick box for one day, not seven.
        assert html.count('class="tick"') == 1

    def test_a_daily_chore_appears_every_day(self):
        html = printable.build_chart([_child()], [_chore("Teeth")], MON)
        assert html.count('class="tick"') == 7

    def test_every_task_gets_a_box_to_tick(self):
        """The entire reason it's on paper."""
        html = printable.build_chart([_child()], [_chore("Bins", due_days=["monday"])], MON)
        assert 'class="tick"' in html

    def test_unassigned_chores_belong_to_everyone(self):
        html = printable.build_chart([_child("Ella"), _child("Sam", "b")],
                                     [_chore("Teeth", assigned_to=[])], MON)
        assert html.count("Teeth") == 14  # 7 days x 2 children

    def test_assigned_chores_only_reach_their_child(self):
        html = printable.build_chart([_child("Ella", "a"), _child("Sam", "b")],
                                     [_chore("Bins", assigned_to=["a"], due_days=["monday"])], MON)
        assert html.count("Bins") == 1

    def test_disabled_chores_are_omitted(self):
        html = printable.build_chart([_child()], [_chore("Old", enabled=False)], MON)
        assert "Old" not in html

    def test_one_shot_appears_only_on_its_date(self):
        html = printable.build_chart(
            [_child()],
            [_chore("Once", schedule_mode="one_shot", created_date=MON.isoformat())],
            MON)
        assert html.count("Once") == 1

    def test_children_with_no_chores_are_skipped(self):
        html = printable.build_chart([_child("Ella", "a"), _child("Sam", "b")],
                                     [_chore("Bins", assigned_to=["a"])], MON)
        assert "Sam" not in html

    def test_empty_chart_says_so(self):
        html = printable.build_chart([], [], MON)
        assert "No chores to show" in html

    def test_the_week_range_is_printed(self):
        html = printable.build_chart([_child()], [_chore()], MON)
        assert "20 Jul" in html and "26 Jul 2026" in html

    def test_points_name_is_used(self):
        html = printable.build_chart([_child()], [_chore()], MON, points_name="Gems")
        assert "Gems" in html


class TestSafety:
    def test_names_are_escaped(self):
        """A chore name is user input and lands in an HTML document."""
        html = printable.build_chart(
            [_child('<script>alert(1)</script>')],
            [_chore('<img src=x onerror=alert(1)>')], MON)
        # The payloads must survive only as inert text: no unescaped tag can
        # appear. "onerror=alert" still occurs as escaped text, which is fine —
        # what matters is that no "<img"/"<script" is emitted.
        assert "<script" not in html
        assert "<img" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "&lt;img src=x onerror=alert(1)&gt;" in html

    def test_output_is_a_standalone_document(self):
        """It gets opened in a new tab and printed — no external assets."""
        html = printable.build_chart([_child()], [_chore()], MON)
        assert html.startswith("<!DOCTYPE html>")
        assert "<style>" in html
        assert "http://" not in html and "https://" not in html
