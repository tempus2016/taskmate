"""Praise note with an approval: a short "well done" the child sees on their card."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate import websocket as ws
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import ChoreCompletion

from .test_completion_eligibility import _make_system, _now, run


def _system():
    coord, storage, mod = _make_system()
    coord.notifications = AsyncMock()
    coord.notifications._has_outstanding_chores_today = lambda _cid: True
    coord.hass.bus = MagicMock()
    coord.badges = None
    with patch.object(mod.dt_util, "now", return_value=_now()):
        kid = run(coord.async_add_child("Vaiha"))
        chore = run(coord.async_add_chore("Clean bathroom", points=8, requires_approval=True))
        run(coord.async_complete_chore(chore.id, kid.id))
    comp = storage.get_completions()[0]
    return coord, storage, mod, kid, chore, comp


def _approve(coord, mod, comp, **kw):
    with patch.object(mod.dt_util, "now", return_value=_now()):
        run(coord.async_approve_chore(comp.id, **kw))


def test_note_is_stored_with_the_approvers_name():
    coord, storage, mod, _kid, _chore, comp = _system()
    _approve(coord, mod, comp, note="  Great job on the   bathroom!  ", note_by="Dad")
    stored = storage.get_completions()[0]
    assert stored.approved and stored.praise_note == "Great job on the bathroom!" and stored.praise_by == "Dad"
    (evt,) = [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == "taskmate_chore_approved"]
    assert evt["praise_note"] == "Great job on the bathroom!"


def test_note_is_capped_and_optional():
    coord, storage, mod, _kid, _chore, comp = _system()
    _approve(coord, mod, comp, note="x" * 300)
    assert len(storage.get_completions()[0].praise_note) == 120
    coord2, storage2, mod2, _k, _c, comp2 = _system()
    _approve(coord2, mod2, comp2)
    data = storage2.get_completions()[0].to_dict()
    assert "praise_note" not in data and "praise_by" not in data


def test_child_summary_shows_todays_notes():
    coord, _storage, mod, kid, _chore, comp = _system()
    _approve(coord, mod, comp, note="Sparkling 🌟")
    with patch.object(mod.dt_util, "now", return_value=_now()):
        coord.data = run(coord._async_update_data())
        common = sensor_module._compute_common(coord)
        (child,) = sensor_module._build_children_summary(coord, common)
    # No approver name: the card says "Grown-up".
    assert child["praise"] == [{"chore_name": "Clean bathroom", "note": "Sparkling 🌟"}]


def test_yesterdays_notes_are_gone():
    common = {
        "all_completions": [
            ChoreCompletion(
                chore_id="c",
                child_id="k",
                completed_at=_now().replace(day=19),
                approved=True,
                approved_at=_now().replace(day=19),
                praise_note="Old news",
            )
        ],
        "chore_lookup": {},
    }
    with patch.object(sensor_module.dt_util, "now", return_value=_now()):
        assert sensor_module._todays_praise(common) == {}


def _ws_coordinator():
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.async_approve_chore = AsyncMock()
    coordinator.async_record_audit = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_ws_approve_carries_the_note_signed_by_the_user():
    coordinator = _ws_coordinator()
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry1": coordinator}}
    connection = MagicMock()
    connection.user.is_admin = True
    connection.user.name = "Dad"
    await ws._ws_approve_chore(
        hass, connection, {"id": 1, "type": ws.WS_APPROVE_CHORE, "completion_id": "x1", "note": "Well done!"}
    )
    coordinator.async_approve_chore.assert_awaited_once_with(
        "x1", points=None, rating=None, note="Well done!", note_by="Dad"
    )
