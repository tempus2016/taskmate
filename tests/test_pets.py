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
    child.total_points_earned = 400
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
    assert state["xp"] == 0 and state["goal"] == {"kind": "stage", "from": 0, "at": 30}


def _grow(coord, storage, child, chores, points):
    child = storage.get_child(child.id)
    child.total_chores_completed += chores
    child.total_points_earned += points
    storage.update_child(child)
    return child


def test_grows_on_chores_plus_points_since_adoption():
    coord, storage, child = _setup()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "cat", "Mimi"))
        # 14 chores x 10 + 70 points = 210 XP: a kid (200), teen at 600.
        state = coord.pet_state(_grow(coord, storage, child, 14, 70))
    assert state["stage"] == "kid" and state["chores"] == 14 and state["xp"] == 210
    assert state["goal"] == {"kind": "stage", "from": 200, "at": 600}


def test_bigger_jobs_grow_it_faster():
    coord, storage, child = _setup()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "cat", "Mimi"))
        # The same 2 chores: small ones leave an egg, big ones hatch it.
        assert coord.pet_state(_grow(coord, storage, child, 2, 2))["stage"] == "egg"
        assert coord.pet_state(_grow(coord, storage, child, 0, 20))["stage"] == "baby"


def test_parents_set_the_growth_per_chore_and_whether_points_count():
    coord, storage, child = _setup()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "dog", "Rex"))
        child = _grow(coord, storage, child, 10, 100)
        assert coord.pet_state(child)["xp"] == 200
        storage.set_setting("pet_xp_per_chore", 25)
        assert coord.pet_state(child)["xp"] == 350
        storage.set_setting("pet_points_count", False)
        assert coord.pet_state(child)["xp"] == 250


def test_parents_set_the_stage_thresholds():
    coord, storage, child = _setup()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "dog", "Rex"))
        child = _grow(coord, storage, child, 2, 0)
        assert coord.pet_state(child)["stage"] == "egg"
        storage.set_setting("pet_stage_baby", 20)
        state = coord.pet_state(child)
    assert state["stage"] == "baby" and state["goal"] == {"kind": "stage", "from": 20, "at": 200}


def test_thresholds_out_of_order_still_rise():
    coord, storage, _child = _setup()
    storage.set_setting("pet_stage_kid", 10)
    storage.set_setting("pet_stage_teen", 5)
    assert coord.pet_stage_thresholds() == (0, 30, 31, 32, 1500)


def test_raising_a_threshold_never_shrinks_a_pet():
    coord, storage, child = _setup()
    coord.async_refresh = AsyncMock()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "cat", "Mimi"))
        run(coord.async_check_pet_growth())
        child = _grow(coord, storage, child, 20, 20)
        run(coord.async_check_pet_growth())
        storage.set_setting("pet_stage_kid", 5000)
        assert coord.pet_state(child)["stage"] == "kid"


def test_spending_points_never_shrinks_it():
    coord, storage, child = _setup()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "dog", "Rex"))
        child = _grow(coord, storage, child, 10, 100)
        child.points = 0
        assert coord.pet_state(child)["xp"] == 200


def test_a_stage_reached_is_kept_after_an_undo():
    coord, storage, child = _setup()
    coord.async_refresh = AsyncMock()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "dog", "Rex"))
        run(coord.async_check_pet_growth())
        child = _grow(coord, storage, child, 20, 20)
        assert run(coord.async_check_pet_growth()) == 1
        child = _grow(coord, storage, child, -15, -15)
        state = coord.pet_state(child)
    assert state["stage"] == "kid" and state["xp"] == 55


def test_growing_up_is_announced_once():
    coord, storage, child = _setup()
    coord.async_refresh = AsyncMock()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "dragon", "Sparky"))
        assert run(coord.async_check_pet_growth()) == 0  # first look: no fanfare
        _grow(coord, storage, child, 3, 15)
        assert run(coord.async_check_pet_growth()) == 1
        assert run(coord.async_check_pet_growth()) == 0
    kind, ctx = coord.notifications.fire.call_args.args
    assert kind == "pet_evolved" and ctx["stage"] == "baby" and ctx["pet_name"] == "Sparky"


def test_old_pets_without_a_points_baseline_grow_on_chores_only():
    coord, storage, child = _setup()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "cat", "Mimi"))
        storage.get_section("pets", dict)[child.id].pop("base_points")
        state = coord.pet_state(_grow(coord, storage, child, 3, 500))
    assert state["xp"] == 30 and state["stage"] == "baby"


def test_fully_grown_has_no_next_stage():
    coord, storage, child = _setup()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "dog", "Rex"))
        state = coord.pet_state(_grow(coord, storage, child, 100, 500))
    assert state["stage"] == "grown" and state["goal"]["kind"] == "home"


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


def _grown(coord, storage, child, extra=0):
    """A fully grown pet with ``extra`` growth past fully grown (1500)."""
    coord.async_refresh = AsyncMock()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "dragon", "Sparky"))
        run(coord.async_check_pet_growth())
        return _grow(coord, storage, child, 100, 500 + extra)


def test_after_grown_defaults_home_legendary_and_eggs_on_levels_off():
    coord, storage, child = _setup()
    child = _grown(coord, storage, child, extra=650)
    a, b = _at()
    with a, b:
        state = coord.pet_state(child)
    assert state["stage"] == "grown" and state["home"] == 2 and "pet_level" not in state
    assert "legendary" not in state and "egg_ready" not in state
    assert state["goal"] == {"kind": "home", "from": 2100, "at": 2400}


def test_home_items_cap_and_follow_their_interval():
    coord, storage, child = _setup()
    storage.set_setting("pet_home_every", 50)
    child = _grown(coord, storage, child, extra=10000)
    a, b = _at()
    with a, b:
        assert coord.pet_state(child)["home"] == 10


def test_legendary_and_the_egg_arrive_together_and_are_announced():
    coord, storage, child = _setup()
    child = _grown(coord, storage, child, extra=1500)
    a, b = _at()
    with a, b:
        assert run(coord.async_check_pet_growth()) == 3  # grown, legendary, egg
        state = coord.pet_state(child)
    kinds = [c.args[1]["kind"] for c in coord.notifications.fire.call_args_list]
    assert kinds == ["stage", "legendary", "egg"]
    assert all(c.args[0] == "pet_evolved" for c in coord.notifications.fire.call_args_list)
    assert "legendary" in coord.notifications.fire.call_args_list[1].args[1]["news"]
    assert state["legendary"] is True and state["egg_ready"] is True


def test_egg_without_legendary_uses_its_own_number():
    coord, storage, child = _setup()
    storage.set_setting("pet_legendary_enabled", False)
    storage.set_setting("pet_egg_at", 2000)
    child = _grown(coord, storage, child, extra=400)
    a, b = _at()
    with a, b:
        state = coord.pet_state(child)
        assert "egg_ready" not in state and state["goal"]["kind"] in ("egg", "home")
        child = _grow(coord, storage, child, 0, 100)
        assert coord.pet_state(child)["egg_ready"] is True


def test_hatching_starts_a_new_pet_and_keeps_the_family():
    coord, storage, child = _setup()
    child = _grown(coord, storage, child, extra=1500)
    a, b = _at()
    with a, b:
        run(coord.async_check_pet_growth())
        run(coord.async_adopt_pet(child.id, "bunny", "Hop", hatch_egg=True))
        state = coord.pet_state(storage.get_child(child.id))
    assert state["name"] == "Hop" and state["stage"] == "egg" and state["xp"] == 0
    assert state["family"] == [{"species": "dragon", "name": "Sparky", "legendary": True}]
    assert "egg_ready" not in state


def test_no_egg_to_hatch_is_refused():
    coord, storage, child = _setup()
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "cat", "Mimi"))
        with pytest.raises(ValueError, match="egg"):
            run(coord.async_adopt_pet(child.id, "dog", "Rex", hatch_egg=True))


def test_a_full_family_lays_no_more_eggs():
    coord, storage, child = _setup()
    storage.set_setting("pet_family_max", 2)
    child = _grown(coord, storage, child, extra=1500)
    a, b = _at()
    with a, b:
        run(coord.async_adopt_pet(child.id, "bunny", "Hop", hatch_egg=True))
        child = _grow(coord, storage, child, 100, 3000)
        state = coord.pet_state(child)
    assert state["legendary"] is True and "egg_ready" not in state


def test_pet_levels_when_switched_on():
    coord, storage, child = _setup()
    storage.set_setting("pet_levels_enabled", True)
    storage.set_setting("pet_legendary_enabled", False)
    storage.set_setting("pet_eggs_enabled", False)
    storage.set_setting("pet_home_enabled", False)
    child = _grown(coord, storage, child, extra=650)
    a, b = _at()
    with a, b:
        state = coord.pet_state(child)
        assert state["pet_level"] == 3 and state["goal"] == {"kind": "level", "from": 2100, "at": 2400}
        run(coord.async_check_pet_growth())
        child = _grow(coord, storage, child, 0, 300)
        assert run(coord.async_check_pet_growth()) == 1
    assert coord.notifications.fire.call_args.args[1]["pet_level"] == 4


def test_switching_an_option_off_hides_it_and_back_on_restores_it():
    coord, storage, child = _setup()
    child = _grown(coord, storage, child, extra=1500)
    a, b = _at()
    with a, b:
        run(coord.async_check_pet_growth())
        storage.set_setting("pet_legendary_enabled", False)
        assert "legendary" not in coord.pet_state(child)
        child = _grow(coord, storage, child, 0, -1400)
        storage.set_setting("pet_legendary_enabled", True)
        assert coord.pet_state(child)["legendary"] is True


def test_everything_switched_off_has_no_goal_after_grown():
    coord, storage, child = _setup()
    for key in ("pet_home_enabled", "pet_legendary_enabled", "pet_eggs_enabled"):
        storage.set_setting(key, False)
    child = _grown(coord, storage, child, extra=50)
    a, b = _at()
    with a, b:
        state = coord.pet_state(child)
    assert state["stage"] == "grown" and "goal" not in state and "home" not in state
