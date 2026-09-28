"""Watch complications (#978): the per-child watch sensor and complete_next_chore.

Drives the real coordinator against real storage (the same harness as
test_chore_undo) and the real ``taskmate.complete_next_chore`` handler.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import custom_components.taskmate as tm
from custom_components.taskmate.sensor import ChildWatchSensor, _async_watch_state_strings
from custom_components.taskmate.storage import TaskMateStorage
from custom_components.taskmate.watch import (
    DEFAULT_STATE_STRINGS,
    NEXT_CHORE_NAME_MAX,
    chore_needs_input,
    next_chore_for_child,
    watch_state,
    watch_summary,
)
from tests.conftest import FakeHass, FakeStore, FakeUnauthorized

TRANSLATIONS = Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "translations"


async def _make_system():
    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    await storage.async_load()
    storage.set_setting("weekend_multiplier", "1")
    storage.set_setting("streak_milestones_enabled", "false")

    from custom_components.taskmate.coordinator import TaskMateCoordinator

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = FakeHass()
    coord.hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()
    coord.data = {}
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    coord._async_notify_pending_approval = AsyncMock()
    coord.notifications = AsyncMock()
    coord.notifications._has_outstanding_chores_today = lambda _cid: True
    coord.async_record_audit = AsyncMock()
    return coord, storage


async def _chore(coord, child, name, *, approval=False, **attrs):
    chore = await coord.async_add_chore(name, points=5, assigned_to=[child.id], requires_approval=approval)
    if attrs:
        for key, value in attrs.items():
            setattr(chore, key, value)
        coord.storage.update_chore(chore)
    return chore


def _bump(coord):
    """A new data snapshot, as a coordinator refresh would give the sensors."""
    coord.data = {}


# ── which chore is "next" ────────────────────────────────────────────────────


def test_next_chore_follows_default_order():
    async def scenario():
        coord, _ = await _make_system()
        kid = await coord.async_add_child("Kid")
        await _chore(coord, kid, "First")
        await _chore(coord, kid, "Second")
        assert next_chore_for_child(coord, kid.id).name == "First"

    asyncio.run(scenario())


def test_next_chore_respects_custom_chore_order():
    async def scenario():
        coord, storage = await _make_system()
        kid = await coord.async_add_child("Kid")
        a = await _chore(coord, kid, "A")
        b = await _chore(coord, kid, "B")
        c = await _chore(coord, kid, "C")
        # C first, then B; A isn't in the list so it goes after them.
        kid.chore_order = [c.id, b.id]
        storage.update_child(kid)
        assert next_chore_for_child(coord, kid.id).id == c.id
        await coord.async_complete_chore(c.id, kid.id)
        assert next_chore_for_child(coord, kid.id).id == b.id
        await coord.async_complete_chore(b.id, kid.id)
        assert next_chore_for_child(coord, kid.id).id == a.id

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "attrs",
    [
        {"require_photo": True},
        {"open_ended": True},
        {"task_type": "timed"},
    ],
)
def test_next_chore_skips_chores_that_need_input(attrs):
    async def scenario():
        coord, _ = await _make_system()
        kid = await coord.async_add_child("Kid")
        awkward = await _chore(coord, kid, "Awkward", **attrs)
        easy = await _chore(coord, kid, "Easy")
        assert chore_needs_input(coord, awkward)
        assert not chore_needs_input(coord, easy)
        assert next_chore_for_child(coord, kid.id).id == easy.id

    asyncio.run(scenario())


def test_teamwork_chore_needs_input():
    coord = MagicMock()
    coord.teamwork_size = MagicMock(return_value=2)
    chore = MagicMock(require_photo=False, open_ended=False, task_type="standard")
    assert chore_needs_input(coord, chore)
    coord.teamwork_size.return_value = 0
    assert not chore_needs_input(coord, chore)


def test_no_next_chore_when_only_input_chores_left():
    async def scenario():
        coord, _ = await _make_system()
        kid = await coord.async_add_child("Kid")
        await _chore(coord, kid, "Photo", require_photo=True)
        assert next_chore_for_child(coord, kid.id) is None
        summary = watch_summary(coord, kid.id)
        # Still owed today — it just can't be ticked off from the watch.
        assert summary["left"] == 1
        assert "next_chore" not in summary

    asyncio.run(scenario())


def test_unknown_child_has_no_next_chore_or_summary():
    async def scenario():
        coord, _ = await _make_system()
        assert next_chore_for_child(coord, "nope") is None
        assert watch_summary(coord, "nope") is None

    asyncio.run(scenario())


# ── the summary / sensor ─────────────────────────────────────────────────────


def test_summary_counts_and_progress():
    async def scenario():
        coord, _ = await _make_system()
        kid = await coord.async_add_child("Kid")
        a = await _chore(coord, kid, "A")
        await _chore(coord, kid, "B", approval=True)
        await _chore(coord, kid, "C")
        await _chore(coord, kid, "D")
        await coord.async_complete_chore(a.id, kid.id)

        s = watch_summary(coord, kid.id)
        assert (s["left"], s["done"], s["total"]) == (3, 1, 4)
        assert s["progress"] == 0.25
        assert s["status"] == "to_do"
        assert s["next_chore"] == "B"
        stored = coord.get_child(kid.id)
        assert s["points"] == stored.points == 5
        assert s["streak"] == stored.current_streak
        assert watch_state(s, DEFAULT_STATE_STRINGS) == "3 left"

    asyncio.run(scenario())


def test_pending_approval_counts_as_done():
    async def scenario():
        coord, _ = await _make_system()
        kid = await coord.async_add_child("Kid")
        chore = await _chore(coord, kid, "Needs OK", approval=True)
        await coord.async_complete_chore(chore.id, kid.id)
        s = watch_summary(coord, kid.id)
        assert (s["left"], s["done"], s["progress"], s["status"]) == (0, 1, 1.0, "all_done")
        assert watch_state(s, DEFAULT_STATE_STRINGS) == "All done"

    asyncio.run(scenario())


def test_no_chores_today():
    async def scenario():
        coord, _ = await _make_system()
        kid = await coord.async_add_child("Kid")
        s = watch_summary(coord, kid.id)
        assert (s["status"], s["total"], s["progress"]) == ("no_chores", 0, 1.0)
        assert watch_state(s, DEFAULT_STATE_STRINGS) == "No chores"

    asyncio.run(scenario())


def test_long_chore_name_is_clipped():
    async def scenario():
        coord, _ = await _make_system()
        kid = await coord.async_add_child("Kid")
        await _chore(coord, kid, "x" * 200)
        assert len(watch_summary(coord, kid.id)["next_chore"]) == NEXT_CHORE_NAME_MAX

    asyncio.run(scenario())


def test_summary_attributes_stay_tiny():
    async def scenario():
        coord, _ = await _make_system()
        kid = await coord.async_add_child("Kid")
        for n in range(40):
            await _chore(coord, kid, f"Chore number {n} " + "y" * 60)
        assert len(json.dumps(watch_summary(coord, kid.id))) < 400

    asyncio.run(scenario())


def test_watch_state_uses_translated_template_and_survives_a_bad_one():
    summary = {"status": "to_do", "left": 2}
    assert watch_state(summary, {"left": "Noch {count}"}) == "Noch 2"
    assert watch_state(summary, {"left": "broken {nope}"}) == "2 left"
    assert watch_state({"status": "all_done", "left": 0}, {"all_done": "Alles erledigt"}) == "Alles erledigt"
    assert watch_state(None, DEFAULT_STATE_STRINGS) is None


def test_sensor_state_attributes_and_cache():
    async def scenario():
        coord, _ = await _make_system()
        kid = await coord.async_add_child("Kid")
        chore = await _chore(coord, kid, "Only")
        entry = MagicMock(entry_id="e1")
        sensor = ChildWatchSensor(coord, entry, kid)
        assert sensor._attr_unique_id == f"e1_{kid.id}_watch"
        assert sensor._attr_name == "Kid Watch"
        assert sensor.native_value == "1 left"
        assert sensor.extra_state_attributes["next_chore"] == "Only"

        await coord.async_complete_chore(chore.id, kid.id)
        # Same snapshot -> same cached answer; a new snapshot recomputes.
        assert sensor.native_value == "1 left"
        _bump(coord)
        assert sensor.native_value == "All done"
        assert "next_chore" not in sensor.extra_state_attributes

    asyncio.run(scenario())


def test_state_strings_come_from_entity_translations(monkeypatch):
    import sys
    import types

    prefix = "component.taskmate.entity.sensor.child_watch.state."
    fake = types.ModuleType("homeassistant.helpers.translation")
    fake.async_get_translations = AsyncMock(return_value={prefix + "left": "Noch {count}", prefix + "all_done": ""})
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.translation", fake)
    hass = MagicMock()
    hass.config.language = "de"
    strings = asyncio.run(_async_watch_state_strings(hass))
    assert strings["left"] == "Noch {count}"
    # Empty/missing phrases fall back to English.
    assert strings["all_done"] == "All done"
    assert strings["no_chores"] == "No chores"


def test_state_strings_fall_back_when_loading_fails(monkeypatch):
    import sys
    import types

    fake = types.ModuleType("homeassistant.helpers.translation")
    fake.async_get_translations = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.translation", fake)
    assert asyncio.run(_async_watch_state_strings(MagicMock())) == DEFAULT_STATE_STRINGS


@pytest.mark.parametrize("path", sorted(TRANSLATIONS.glob("*.json")), ids=lambda p: p.stem)
def test_every_locale_has_a_formattable_left_phrase(path):
    states = json.loads(path.read_text(encoding="utf-8"))["entity"]["sensor"]["child_watch"]["state"]
    assert set(states) == {"left", "all_done", "no_chores"}
    assert "3" in states["left"].format(count=3)


# ── the complete_next_chore service ──────────────────────────────────────────


class _Services:
    def __init__(self):
        self.handlers = {}

    def async_register(self, domain, name, handler, schema=None):
        self.handlers[name] = handler


async def _service(coord, monkeypatch, *, user=None):
    monkeypatch.setattr(tm, "_get_coordinator", lambda hass: coord)
    services = _Services()
    hass = MagicMock()
    hass.services = services
    hass.auth.async_get_user = AsyncMock(return_value=user)
    await tm._async_register_services(hass)
    return services.handlers[tm.SERVICE_COMPLETE_NEXT_CHORE]


def _call(user_id, **data):
    call = MagicMock()
    call.context.user_id = user_id
    call.data = data
    return call


def _done_ids(storage, child_id):
    return [c.chore_id for c in storage.get_completions() if c.child_id == child_id]


def test_service_completes_next_in_card_order(monkeypatch):
    async def scenario():
        coord, storage = await _make_system()
        kid = await coord.async_add_child("Kid")
        a = await _chore(coord, kid, "A")
        photo = await _chore(coord, kid, "Photo", require_photo=True)
        c = await _chore(coord, kid, "C")
        kid.chore_order = [photo.id, c.id, a.id]
        storage.update_child(kid)
        handler = await _service(coord, monkeypatch)

        await handler(_call(None, child_id=kid.id))
        assert _done_ids(storage, kid.id) == [c.id]
        await handler(_call(None, child_id=kid.id))
        assert _done_ids(storage, kid.id) == [c.id, a.id]
        # Only the photo chore is left: a quiet no-op, not an error.
        await handler(_call(None, child_id=kid.id))
        assert _done_ids(storage, kid.id) == [c.id, a.id]

    asyncio.run(scenario())


def test_service_keeps_normal_approval(monkeypatch):
    async def scenario():
        coord, storage = await _make_system()
        kid = await coord.async_add_child("Kid")
        await _chore(coord, kid, "Needs OK", approval=True)
        handler = await _service(coord, monkeypatch)
        await handler(_call(None, child_id=kid.id))
        (comp,) = storage.get_completions()
        assert comp.approved is False
        assert storage.get_child(kid.id).points == 0

    asyncio.run(scenario())


def test_service_respects_linked_child(monkeypatch):
    async def scenario():
        coord, storage = await _make_system()
        kid = await coord.async_add_child("Kid")
        kid.linked_user_id = "uid-kid"
        storage.update_child(kid)
        await _chore(coord, kid, "A")
        other = MagicMock(is_admin=False)
        handler = await _service(coord, monkeypatch, user=other)
        with pytest.raises(FakeUnauthorized):
            await handler(_call("uid-sibling", child_id=kid.id))
        assert storage.get_completions() == []
        await handler(_call("uid-kid", child_id=kid.id))
        assert len(storage.get_completions()) == 1

    asyncio.run(scenario())


def test_service_rejects_unknown_child(monkeypatch):
    async def scenario():
        coord, _ = await _make_system()
        handler = await _service(coord, monkeypatch)
        with pytest.raises(tm.ServiceValidationError):
            await handler(_call(None, child_id="ghost"))

    asyncio.run(scenario())


def test_service_is_unregistered_on_unload():
    hass = MagicMock()
    tm._async_unregister_services(hass)
    removed = {c.args[1] for c in hass.services.async_remove.call_args_list}
    assert "complete_next_chore" in removed
