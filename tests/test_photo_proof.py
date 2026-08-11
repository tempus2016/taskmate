"""Tests for photo-proof chores."""

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
    # A real dict, not a MagicMock: completion signs the evidence photo via
    # HA's async_sign_path, which reads hass.data[...]. Handed a mock it builds
    # an unserializable JWT payload — sign_photo_url swallows that and returns
    # the URL unsigned, but the test harness still flags the attempted mock
    # serialization at teardown. An empty dict makes the lookup miss cleanly.
    coord.hass.data = {}
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
    chore = Chore(name="Room", requires_approval=False, require_photo=True, assignment_mode="everyone", id="ch1")
    child = Child(name="Mia", id="c1")
    coord = _coord(chore, child)
    photo = "/api/taskmate/photo/" + "a" * 32 + ".jpg"
    run(coord.async_complete_chore("ch1", "c1", photo_url=photo))
    comp = coord._added[0]
    assert comp.approved is False
    assert comp.points_awarded == 0
    assert comp.photo_url == photo
    coord._award_points.assert_not_awaited()


def test_photo_stored_on_completion():
    chore = Chore(name="Room", requires_approval=True, require_photo=True, assignment_mode="everyone", id="ch1")
    coord = _coord(chore, Child(name="Mia", id="c1"))
    photo = "/api/taskmate/photo/" + "b" * 32 + ".png"
    run(coord.async_complete_chore("ch1", "c1", photo_url=photo))
    assert coord._added[0].photo_url == photo


def test_photo_required_blocks_completion_without_photo():
    # require_photo=True, child completing with no photo -> hard rejection (ValueError),
    # NOT a silent pending completion. This is the server-side guard mirroring the card.
    chore = Chore(name="Room", requires_approval=False, require_photo=True, assignment_mode="everyone", id="ch1")
    coord = _coord(chore, Child(name="Mia", id="c1"))
    with pytest.raises(ValueError):
        run(coord.async_complete_chore("ch1", "c1"))
    assert coord._added == []


def test_photo_required_blocks_blank_photo():
    # A whitespace-only photo_url is treated as no photo.
    chore = Chore(name="Room", requires_approval=False, require_photo=True, assignment_mode="everyone", id="ch1")
    coord = _coord(chore, Child(name="Mia", id="c1"))
    with pytest.raises(ValueError):
        run(coord.async_complete_chore("ch1", "c1", photo_url="   "))
    assert coord._added == []


def test_foreign_photo_url_is_rejected_not_stored():
    # Security: a crafted/foreign photo_url (javascript:, external https, traversal)
    # must never be stored — it would later render into an href/src in the parent's
    # approval views. The coordinator drops it to "" at the boundary. With an
    # approval-required (non-photo) chore the completion still proceeds, but with no
    # photo attached.
    chore = Chore(name="Room", requires_approval=True, require_photo=False, assignment_mode="everyone", id="ch1")
    coord = _coord(chore, Child(name="Mia", id="c1"))
    for bad in ("javascript:alert(1)", "https://evil.example/track.png", "/api/taskmate/photo/../../etc/passwd"):
        coord._added.clear()
        run(coord.async_complete_chore("ch1", "c1", photo_url=bad))
        assert coord._added[0].photo_url == ""


def test_foreign_photo_url_does_not_satisfy_require_photo():
    # A crafted photo_url must not satisfy a require_photo chore — once dropped to
    # "", the require_photo guard fires exactly as if no photo were sent.
    chore = Chore(name="Room", requires_approval=False, require_photo=True, assignment_mode="everyone", id="ch1")
    coord = _coord(chore, Child(name="Mia", id="c1"))
    with pytest.raises(ValueError):
        run(coord.async_complete_chore("ch1", "c1", photo_url="javascript:alert(1)"))
    assert coord._added == []


def test_parent_can_still_autocomplete_photo_chore():
    chore = Chore(name="Room", requires_approval=False, require_photo=True, assignment_mode="everyone", id="ch1")
    coord = _coord(chore, Child(name="Mia", id="c1"))
    run(coord.async_complete_chore("ch1", "c1", as_parent=True))
    assert coord._added[0].approved is True
    coord._award_points.assert_awaited_once()


def test_prune_deletes_orphaned_evidence_photos(monkeypatch):
    # Pruning old, approved completions must also delete their evidence photos so
    # the photos dir doesn't grow forever. Kept/pending completions keep theirs.
    import datetime as _dt

    from homeassistant.util import dt as dt_util

    from custom_components.taskmate import coord_points

    deleted = []
    monkeypatch.setattr(
        coord_points.photos,
        "async_delete_photo",
        AsyncMock(side_effect=lambda hass, url: deleted.append(url)),
    )

    # Derive dates from the (mockable, order-sensitive) stubbed clock so this
    # test doesn't depend on the global mock's current value.
    now = dt_util.now()
    old_with_photo = ChoreCompletion(
        chore_id="a",
        child_id="c",
        completed_at=now - _dt.timedelta(days=200),
        approved=True,
        photo_url="/api/taskmate/photo/" + "a" * 32 + ".jpg",
    )
    old_no_photo = ChoreCompletion(
        chore_id="b", child_id="c", completed_at=now - _dt.timedelta(days=200), approved=True, photo_url=""
    )
    recent = ChoreCompletion(
        chore_id="d",
        child_id="c",
        completed_at=now - _dt.timedelta(days=1),
        approved=True,
        photo_url="/api/taskmate/photo/" + "b" * 32 + ".jpg",
    )

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    storage = MagicMock()
    storage.get_completions = MagicMock(return_value=[old_with_photo, old_no_photo, recent])
    storage.replace_completions = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.async_refresh = AsyncMock()

    run(coord.async_prune_history(days=90))

    # Only the pruned (old) photo is deleted; the recent one survives.
    assert deleted == ["/api/taskmate/photo/" + "a" * 32 + ".jpg"]


def test_completion_photo_round_trips():
    c = ChoreCompletion(
        chore_id="x", child_id="y", completed_at=__import__("datetime").datetime(2026, 1, 1), photo_url="http://p"
    )
    assert ChoreCompletion.from_dict(c.to_dict()).photo_url == "http://p"


def test_chore_require_photo_round_trips():
    assert Chore.from_dict(Chore(name="A", require_photo=True).to_dict()).require_photo is True
