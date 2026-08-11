"""Tests for TaskMate conversation intents (FEAT-12)."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.taskmate import intents
from custom_components.taskmate.models import Child


def _coord(children, *, due=0, points_name="Stars"):
    c = MagicMock()
    c.storage.get_children = MagicMock(return_value=children)
    c.storage.get_points_name = MagicMock(return_value=points_name)
    c.get_due_chores_for_child = MagicMock(return_value=[object()] * due)
    return c


def test_find_child_case_insensitive():
    kids = [Child(name="Malia", id="k1"), Child(name="Alex", id="k2")]
    c = _coord(kids)
    assert intents._find_child(c, "malia").id == "k1"
    assert intents._find_child(c, "  ALEX ").id == "k2"
    assert intents._find_child(c, "nobody") is None


def test_chores_left_speech_variants():
    kids = [Child(name="Malia", id="k1")]
    assert "couldn't find" in intents.chores_left_speech(_coord(kids), "ghost")
    assert intents.chores_left_speech(_coord(kids, due=0), "Malia").startswith("Malia has finished")
    assert "1 chore left" in intents.chores_left_speech(_coord(kids, due=1), "Malia")
    assert "3 chores left" in intents.chores_left_speech(_coord(kids, due=3), "Malia")


def test_points_speech():
    kids = [Child(name="Alex", id="k2", points=42)]
    assert intents.points_speech(_coord(kids, points_name="Stars"), "Alex") == "Alex has 42 Stars."
    assert "couldn't find" in intents.points_speech(_coord(kids), "ghost")


def test_setup_registers_two_intents():
    hass = MagicMock()
    intents.intent.async_register.reset_mock()
    intents.async_setup_intents(hass)
    assert intents.intent.async_register.call_count == 2
    types = {type(call.args[1]).__name__ for call in intents.intent.async_register.call_args_list}
    assert types == {"ChoresLeftIntentHandler", "PointsIntentHandler"}
