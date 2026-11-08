"""A chore assigned to named children is never available to anyone else (#1240).

``is_chore_available_for_child`` only checked ``assigned_to`` for rotation
modes, so an "everyone" chore assigned to one child showed as available to
every child in the ``chore_availability`` matrix. The Routine card trusted that
matrix and offered a sibling's chore; roulette could hand one out too.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.taskmate import sensor as sensor_mod
from custom_components.taskmate.models import Chore

from .test_completion_eligibility import _make_system, _now, _two_children, run


def _system():
    coord, storage, mod = _make_system()
    with patch.object(mod.dt_util, "now", return_value=_now()):
        alice, bob = _two_children(coord)
    return coord, storage, mod, alice, bob


def _at(mod):
    return patch.object(mod.dt_util, "now", return_value=_now())


@pytest.mark.parametrize("schedule_mode", ["specific_days", "recurring", "one_shot"])
def test_everyone_chore_is_unavailable_to_a_child_not_assigned(schedule_mode):
    coord, storage, mod, alice, bob = _system()
    chore = Chore(name="Shower", schedule_mode=schedule_mode, recurrence="weekly", assigned_to=[alice.id])
    storage.add_chore(chore)
    with _at(mod):
        assert coord.is_chore_available_for_child(chore, alice.id) is True
        assert coord.is_chore_available_for_child(chore, bob.id) is False
        # A parent completing on behalf skips only the assignment check.
        assert coord.is_chore_available_for_child(chore, bob.id, ignore_assignment=True) is True


def test_an_unassigned_chore_stays_available_to_everyone():
    coord, storage, mod, alice, bob = _system()
    chore = Chore(name="Tidy up", assigned_to=[])
    storage.add_chore(chore)
    with _at(mod):
        assert coord.is_chore_available_for_child(chore, alice.id) is True
        assert coord.is_chore_available_for_child(chore, bob.id) is True


def test_an_open_make_it_right_offer_still_wins():
    coord, storage, mod, alice, bob = _system()
    chore = Chore(name="Shower", assigned_to=[alice.id])
    storage.add_chore(chore)
    with _at(mod), patch.object(coord, "open_redemption_for", return_value={"id": "offer"}):
        assert coord.is_chore_available_for_child(chore, bob.id) is True


def test_the_availability_matrix_marks_a_siblings_chore_false():
    coord, storage, mod, alice, bob = _system()
    chore = Chore(name="Shower", assigned_to=[alice.id])
    storage.add_chore(chore)
    common = {"chores": [chore], "children": [alice, bob]}
    with _at(mod):
        matrix = sensor_mod._build_chore_availability(coord, common)
    assert matrix == {chore.id: {alice.id: True, bob.id: False}}


def test_next_open_is_not_published_for_a_child_not_assigned():
    coord, storage, mod, alice, bob = _system()
    chore = Chore(name="Water plants", schedule_mode="recurring", recurrence="every_3_days", assigned_to=[alice.id])
    storage.add_chore(chore)
    common = {"chores": [chore], "children": [alice, bob]}
    with _at(mod):
        availability = sensor_mod._build_chore_availability(coord, common)
        out = sensor_mod._build_chore_next_open(coord, common, availability)
    # Alice's window is open, Bob's chore it isn't: nothing to publish for either.
    assert out == {}


def test_roulette_never_picks_a_siblings_chore():
    coord, storage, mod, alice, bob = _system()
    mine = Chore(name="Feed the cat", assigned_to=[bob.id])
    theirs = Chore(name="Shower", assigned_to=[alice.id])
    storage.add_chore(mine)
    storage.add_chore(theirs)
    with _at(mod):
        picks = [c.id for c in coord._roulette_candidates(bob.id)]
    assert picks == [mine.id]


def test_a_child_still_cannot_complete_a_siblings_chore():
    coord, storage, mod, alice, bob = _system()
    with _at(mod):
        chore = run(coord.async_add_chore("Shower", points=5, requires_approval=False, assigned_to=[alice.id]))
        assert run(coord.async_complete_chore(chore.id, bob.id)) is None
    assert storage.get_child(bob.id).points == 0
