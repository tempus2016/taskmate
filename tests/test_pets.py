"""Virtual pets: adopt, grow with chores, mood from the last chore, accessories by level."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, patch

import pytest

from .test_completion_eligibility import _make_system, _now, run

PETS = "custom_components.taskmate.coord_pets.dt_util"


def _setup(enabled=True):
    coord, storage, mod = _make_system()
    coord.notifications = AsyncMock()
    storage.set_setting("pets_enabled", enabled)
    with patch.object(mod.dt_util, "now", return_value=_now()):
        kid = run(coord.async_add_child("Vaiha"))
    child = storage.get_child(kid.id)
    child.total_chores_completed = 40
    storage.update_child(child)
    return coord, storage, child


def _at(when=None):
    when = when or _now()
    return patch(f"{PETS}.now", return_value=when), patch(f"{PETS}.as_local", side_effect=lambda d: d)


def test_off_by_default_and_refuses_adoption():
    coord, storage, child = _setup(enabled=False)
    assert coord.pet_state(child) is None
    with pytest.raises(ValueError, match="off"):
        run(coord.async_adopt_pet(child.id, "cat", "Mimi"))


def test_unadopted_then_adopted_as_an_egg():
    coord, storage, child = _setup()
    assert coord.pet_state(child) == {"adopted": False}
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "dragon", "Sparky"))
        state = coord.pet_state(storage.get_child(child.id))
    assert state["name"] == "Sparky" and state["stage"] == "egg" and state["chores"] == 0
    assert state["next_at"] == 3


def test_grows_with_chores_since_adoption():
    coord, storage, child = _setup()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "cat", "Mimi"))
        child = storage.get_child(child.id)
        child.total_chores_completed += 16
        state = coord.pet_state(child)
    assert state["stage"] == "kid" and state["chores"] == 16 and state["stage_at"] == 15 and state["next_at"] == 40


def test_fully_grown_has_no_next_stage():
    coord, storage, child = _setup()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "dog", "Rex"))
        child = storage.get_child(child.id)
        child.total_chores_completed += 150
        state = coord.pet_state(child)
    assert state["stage"] == "grown" and "next_at" not in state


def test_mood_follows_the_last_chore():
    coord, storage, child = _setup()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "bunny", "Hop"))
    child = storage.get_child(child.id)
    today = _now().date()
    for last, streak, mood in (
        (today, 1, "happy"),
        (today, 9, "proud"),
        (today - dt.timedelta(days=1), 0, "content"),
        (today - dt.timedelta(days=3), 0, "sleepy"),
        (None, 0, "sleepy"),
    ):
        child.last_completion_date = last.isoformat() if last else None
        child.current_streak = streak
        a, b = _at()
        with a, b:
            assert coord.pet_state(child)["mood"] == mood, (last, streak)


def test_accessories_by_level():
    coord, storage, child = _setup()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "unicorn", "Star"))
    child = storage.get_child(child.id)
    child.level = 16
    with a, b:
        assert coord.pet_state(child)["accessories"] == ["bow", "top_hat", "scarf"]


def test_renaming_keeps_the_growth():
    coord, storage, child = _setup()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "dino", "Rex"))
        child = storage.get_child(child.id)
        child.total_chores_completed += 5
        storage.update_child(child)
        run(coord.async_adopt_pet(child.id, "dragon", "Blaze"))
        state = coord.pet_state(storage.get_child(child.id))
    assert state["name"] == "Blaze" and state["species"] == "dragon" and state["chores"] == 5


def test_validation():
    coord, _storage, child = _setup()
    with pytest.raises(ValueError):
        run(coord.async_adopt_pet(child.id, "griffin", "x"))
    with pytest.raises(ValueError):
        run(coord.async_adopt_pet(child.id, "cat", "  "))
