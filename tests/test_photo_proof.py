"""Tests for photo-proof chores."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

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
    coord.hass.bus = MagicMock(); coord.hass.bus.async_fire = MagicMock()
    added = []
    storage = MagicMock()
    storage.get_chore = MagicMock(return_value=chore)
    storage.get_completions = MagicMock(return_value=[])
    storage.get_last_completed = MagicMock(return_value=None)
    storage.add_completion = MagicMock(side_effect=lambda c: added.append(c))
    storage.set_last_completed = MagicMock()
    storage.update_chore = MagicMock()
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


def test_photo_required_forces_pending_even_if_no_approval():
    # require_photo=True, requires_approval=False -> still NOT auto-approved
    chore = Chore(name="Room", requires_approval=False, require_photo=True,
                  assignment_mode="everyone", id="ch1")
    child = Child(name="Mia", id="c1")
    coord = _coord(chore, child)
    run(coord.async_complete_chore("ch1", "c1", photo_url="http://x/p.jpg"))
    comp = coord._added[0]
    assert comp.approved is False
    assert comp.points_awarded == 0
    assert comp.photo_url == "http://x/p.jpg"
    coord._award_points.assert_not_awaited()


def test_photo_stored_on_completion():
    chore = Chore(name="Room", requires_approval=True, require_photo=True,
                  assignment_mode="everyone", id="ch1")
    coord = _coord(chore, Child(name="Mia", id="c1"))
    run(coord.async_complete_chore("ch1", "c1", photo_url="http://x/snap.png"))
    assert coord._added[0].photo_url == "http://x/snap.png"


def test_parent_can_still_autocomplete_photo_chore():
    chore = Chore(name="Room", requires_approval=False, require_photo=True,
                  assignment_mode="everyone", id="ch1")
    coord = _coord(chore, Child(name="Mia", id="c1"))
    run(coord.async_complete_chore("ch1", "c1", as_parent=True))
    assert coord._added[0].approved is True
    coord._award_points.assert_awaited_once()


def test_completion_photo_round_trips():
    c = ChoreCompletion(chore_id="x", child_id="y",
                        completed_at=__import__("datetime").datetime(2026, 1, 1),
                        photo_url="http://p")
    assert ChoreCompletion.from_dict(c.to_dict()).photo_url == "http://p"


def test_chore_require_photo_round_trips():
    assert Chore.from_dict(Chore(name="A", require_photo=True).to_dict()).require_photo is True
