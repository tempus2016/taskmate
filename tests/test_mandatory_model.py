"""Tests for mandatory-chore model fields and the MandatoryMiss model (#532)."""

from __future__ import annotations

from custom_components.taskmate.models import Chore, MandatoryMiss


def test_mandatory_defaults_off():
    c = Chore(name="Homework")
    assert c.mandatory is False
    assert c.mandatory_penalty_points == 0


def test_mandatory_round_trip():
    c = Chore(name="Homework", mandatory=True, mandatory_penalty_points=5, id="c1")
    d = c.to_dict()
    assert d["mandatory"] is True
    assert d["mandatory_penalty_points"] == 5
    c2 = Chore.from_dict(d)
    assert c2.mandatory is True
    assert c2.mandatory_penalty_points == 5


def test_mandatory_legacy_record_loads():
    # Old stored chore with no mandatory keys loads with safe defaults.
    c = Chore.from_dict({"name": "Old", "id": "c9"})
    assert c.mandatory is False
    assert c.mandatory_penalty_points == 0


def test_mandatory_miss_round_trip():
    m = MandatoryMiss(
        chore_id="c1",
        child_id="k1",
        due_date="2026-06-21",
        period_id="morning",
        penalty_points=5,
        postpone_count=1,
        created_at="2026-06-21T12:00:00",
        id="m1",
    )
    d = m.to_dict()
    m2 = MandatoryMiss.from_dict(d)
    assert m2 == m


def test_mandatory_miss_defaults():
    m = MandatoryMiss(chore_id="c1", child_id="k1", due_date="2026-06-21", period_id="morning")
    assert m.penalty_points == 0
    assert m.postpone_count == 0
    assert m.id  # auto-generated
