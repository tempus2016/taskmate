"""Tests for the mandatory_misses storage collection (#532)."""
from __future__ import annotations

from custom_components.taskmate.storage import TaskMateStorage
from custom_components.taskmate.models import MandatoryMiss


def _storage():
    s = object.__new__(TaskMateStorage)
    s._data = {}
    return s


def test_add_get_remove_miss():
    s = _storage()
    m = MandatoryMiss(chore_id="c1", child_id="k1", due_date="2026-06-21", period_id="morning", id="m1")
    s.add_mandatory_miss(m)
    got = s.get_mandatory_misses()
    assert len(got) == 1 and got[0].id == "m1"
    s.remove_mandatory_miss("m1")
    assert s.get_mandatory_misses() == []


def test_update_miss():
    s = _storage()
    m = MandatoryMiss(chore_id="c1", child_id="k1", due_date="2026-06-21", period_id="morning", id="m1")
    s.add_mandatory_miss(m)
    m.postpone_count = 2
    s.update_mandatory_miss(m)
    assert s.get_mandatory_misses()[0].postpone_count == 2


def test_replace_misses():
    s = _storage()
    s.add_mandatory_miss(MandatoryMiss(chore_id="c1", child_id="k1", due_date="d", period_id="morning", id="m1"))
    s.replace_mandatory_misses([
        MandatoryMiss(chore_id="c2", child_id="k2", due_date="d", period_id="evening", id="m2"),
    ])
    got = s.get_mandatory_misses()
    assert len(got) == 1 and got[0].id == "m2"
