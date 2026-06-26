"""The chores sensor list must carry the mandatory flag so the child card
can render the badge/styling (#532 regression guard)."""
from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.taskmate.models import Chore
from custom_components.taskmate.sensor import _build_chores_list


def _coord():
    c = MagicMock()
    c.effective_chore_points = MagicMock(side_effect=lambda ch: ch.points)
    return c


def test_mandatory_chore_emits_flag_and_penalty():
    chore = Chore(name="Homework", points=8, mandatory=True,
                  mandatory_penalty_points=10, id="c1")
    out = _build_chores_list(_coord(), {"chores": [chore]})
    rec = out[0]
    assert rec["mandatory"] is True
    assert rec["mandatory_penalty_points"] == 10


def test_non_mandatory_chore_omits_flag():
    chore = Chore(name="Tidy", points=5, mandatory=False, id="c2")
    rec = _build_chores_list(_coord(), {"chores": [chore]})[0]
    assert "mandatory" not in rec
    assert "mandatory_penalty_points" not in rec


def test_mandatory_with_zero_penalty_omits_penalty_key():
    chore = Chore(name="Brush teeth", points=3, mandatory=True,
                  mandatory_penalty_points=0, id="c3")
    rec = _build_chores_list(_coord(), {"chores": [chore]})[0]
    assert rec["mandatory"] is True
    assert "mandatory_penalty_points" not in rec
