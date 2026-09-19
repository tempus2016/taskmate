"""Open-ended chores: the child describes what they did and suggests points (#832).

An open-ended chore is a placeholder the child taps for unlisted work ("I did
something extra"). The card prompts for a description and a suggested point
value; the parent reviews both and sets the real points when approving.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, ChoreCompletion


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(chore, child):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    coord.hass.data = {}
    added = []
    storage = MagicMock()
    storage.get_chore = MagicMock(return_value=chore)
    storage.get_completions = MagicMock(return_value=[])
    storage.get_last_completed = MagicMock(return_value=None)
    storage.add_completion = MagicMock(side_effect=lambda c: added.append(c))
    storage.set_last_completed = MagicMock()
    storage.update_chore = MagicMock()
    storage.update_completion = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord._added = added
    coord.get_child = MagicMock(return_value=child)
    coord.get_chore = MagicMock(return_value=chore)
    coord.effective_chore_points = MagicMock(return_value=10)
    coord._apply_time_adjustment = MagicMock(side_effect=lambda c, b, t: b)
    coord._is_rotation_done_today = MagicMock(return_value=False)
    coord._award_points = AsyncMock(return_value=10)
    coord.async_refresh = AsyncMock()
    coord.badges = None
    coord.notifications = MagicMock()
    coord.notifications.fire = AsyncMock()
    coord.notifications._has_outstanding_chores_today = MagicMock(return_value=True)
    return coord


def _open_ended(**kwargs):
    kwargs.setdefault("requires_approval", True)
    return Chore(name="Something extra", open_ended=True, assignment_mode="everyone", id="ch1", **kwargs)


# ── the flag itself ──────────────────────────────────────────────────────────


def test_chore_open_ended_defaults_to_false():
    assert Chore(name="Dishes", id="ch1").open_ended is False


def test_chore_open_ended_round_trips_through_storage():
    chore = _open_ended()
    assert Chore.from_dict(chore.to_dict()).open_ended is True


# ── what the child submits ───────────────────────────────────────────────────


def test_note_and_suggested_points_are_stored_on_the_completion():
    coord = _coord(_open_ended(), Child(name="Mia", id="c1"))
    run(coord.async_complete_chore("ch1", "c1", note="Tidied the porch", suggested_points=15))
    comp = coord._added[0]
    assert comp.note == "Tidied the porch"
    assert comp.suggested_points == 15


def test_completion_note_round_trips_through_storage():
    comp = ChoreCompletion(
        chore_id="ch1",
        child_id="c1",
        completed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        note="Swept the shed",
        suggested_points=8,
    )
    restored = ChoreCompletion.from_dict(comp.to_dict())
    assert restored.note == "Swept the shed"
    assert restored.suggested_points == 8


def test_open_ended_chore_needs_a_description_from_a_child():
    coord = _coord(_open_ended(), Child(name="Mia", id="c1"))
    with pytest.raises(ValueError):
        run(coord.async_complete_chore("ch1", "c1"))
    assert coord._added == []


def test_whitespace_only_description_is_not_a_description():
    coord = _coord(_open_ended(), Child(name="Mia", id="c1"))
    with pytest.raises(ValueError):
        run(coord.async_complete_chore("ch1", "c1", note="   \n  "))


def test_a_parent_completing_on_behalf_needs_no_description():
    coord = _coord(_open_ended(), Child(name="Mia", id="c1"))
    run(coord.async_complete_chore("ch1", "c1", as_parent=True))
    assert coord._added[0].note == ""


def test_an_ordinary_chore_needs_no_description():
    chore = Chore(name="Dishes", requires_approval=True, assignment_mode="everyone", id="ch1")
    coord = _coord(chore, Child(name="Mia", id="c1"))
    run(coord.async_complete_chore("ch1", "c1"))
    assert len(coord._added) == 1


# ── sanitising ───────────────────────────────────────────────────────────────


def test_note_is_trimmed():
    coord = _coord(_open_ended(), Child(name="Mia", id="c1"))
    run(coord.async_complete_chore("ch1", "c1", note="  Washed the car  "))
    assert coord._added[0].note == "Washed the car"


def test_overlong_note_is_truncated_not_rejected():
    coord = _coord(_open_ended(), Child(name="Mia", id="c1"))
    run(coord.async_complete_chore("ch1", "c1", note="x" * 900))
    assert len(coord._added[0].note) == 200


def test_absurd_suggested_points_are_clamped():
    coord = _coord(_open_ended(), Child(name="Mia", id="c1"))
    run(coord.async_complete_chore("ch1", "c1", note="Everything", suggested_points=999999))
    assert coord._added[0].suggested_points == 999


def test_negative_suggested_points_are_clamped_to_zero():
    coord = _coord(_open_ended(), Child(name="Mia", id="c1"))
    run(coord.async_complete_chore("ch1", "c1", note="Everything", suggested_points=-5))
    assert coord._added[0].suggested_points == 0


# ── approval routing ─────────────────────────────────────────────────────────


def test_open_ended_forces_pending_even_when_approval_is_off():
    # A child types their own point value, so it must never self-award.
    coord = _coord(_open_ended(requires_approval=False), Child(name="Mia", id="c1"))
    run(coord.async_complete_chore("ch1", "c1", note="Helped with the shopping"))
    comp = coord._added[0]
    assert comp.approved is False
    assert comp.points_awarded == 0
    coord._award_points.assert_not_awaited()


def test_a_parent_completion_still_auto_approves():
    coord = _coord(_open_ended(), Child(name="Mia", id="c1"))
    run(coord.async_complete_chore("ch1", "c1", as_parent=True))
    assert coord._added[0].approved is True


# ── the parent's approval push ───────────────────────────────────────────────


def test_approval_push_quotes_the_childs_suggestion():
    # An open-ended chore carries no points of its own, so a push built from
    # chore.points would always announce "0 pts".
    coord = _coord(_open_ended(points=0), Child(name="Mia", id="c1"))
    coord._async_notify_pending_approval = AsyncMock()
    run(coord.async_complete_chore("ch1", "c1", note="Washed the car", suggested_points=20))
    _args, _kwargs = coord._async_notify_pending_approval.call_args
    assert _args[2] == 20


def test_approval_push_for_an_ordinary_chore_still_quotes_the_chore():
    chore = Chore(name="Dishes", points=7, requires_approval=True, assignment_mode="everyone", id="ch1")
    coord = _coord(chore, Child(name="Mia", id="c1"))
    coord._async_notify_pending_approval = AsyncMock()
    run(coord.async_complete_chore("ch1", "c1"))
    _args, _kwargs = coord._async_notify_pending_approval.call_args
    assert _args[2] == 7
