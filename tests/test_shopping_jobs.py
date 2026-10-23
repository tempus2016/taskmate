"""Shopping-list jobs: a "#tm ..." to-do item becomes a chore, and back again."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.taskmate.coord_shopping_jobs import shopping_job_name
from custom_components.taskmate.models import ChoreCompletion

from .test_completion_eligibility import _make_system, run

SHOP = "custom_components.taskmate.coord_shopping_jobs.dt_util"


def _when(day=21, hour=17, minute=0):
    return dt.datetime(2026, 10, day, hour, minute, tzinfo=dt.UTC)


def _system(items=None, mode="first_come", fail=False):
    coord, storage, mod = _make_system()
    coord.hass.bus = MagicMock()
    coord.badges = None
    todo = {"items": list(items if items is not None else [])}
    calls = []

    async def fake_call(domain, service, data, blocking=False, return_response=False):
        calls.append((domain, service, data))
        if fail and service == "get_items":
            raise RuntimeError("no such entity")
        if service == "update_item":
            for i in todo["items"]:
                if i["uid"] == data["item"]:
                    i["status"] = data["status"]
        if service == "get_items":
            return {data["entity_id"]: {"items": [i for i in todo["items"] if i.get("status") == "needs_action"]}}
        return None

    coord.hass.services = MagicMock()
    coord.hass.services.async_call = AsyncMock(side_effect=fake_call)
    storage.set_setting("shopping_jobs_enabled", True)
    storage.set_setting("shopping_jobs_points", 4)
    storage.set_setting("shopping_jobs_mode", mode)
    with patch.object(mod.dt_util, "now", return_value=_when()):
        kid = run(coord.async_add_child("Vaiha"))
        leo = run(coord.async_add_child("Leo"))
    return coord, storage, mod, kid, leo, calls, todo


def _item(uid, summary, status="needs_action"):
    return {"uid": uid, "summary": summary, "status": status}


def _tick(coord, mod, when):
    with patch(f"{SHOP}.now", return_value=when), patch.object(mod.dt_util, "now", return_value=when):
        return run(coord.async_check_shopping_jobs())


def _jobs(storage):
    return [c for c in storage.get_chores() if c.name.startswith("🛒")]


def _fired(coord):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == "taskmate_shopping_job"]


class TestName:
    def test_only_items_starting_with_the_tag(self):
        assert shopping_job_name("#tm fetch logs from the shed", "#tm") == "🛒 Fetch logs from the shed"
        assert shopping_job_name("#TM: tidy the car", "#tm") == "🛒 Tidy the car"
        assert shopping_job_name("Milk", "#tm") == ""
        assert shopping_job_name("#tmp thing", "#tm") == ""
        assert shopping_job_name("#tm", "#tm") == ""
        assert shopping_job_name("buy #tm stuff", "#tm") == ""


class TestSync:
    def test_a_tagged_item_becomes_a_chore_once(self):
        coord, storage, mod, kid, leo, calls, _todo = _system(
            items=[_item("a", "Milk"), _item("b", "#tm fetch logs from the shed")]
        )
        assert _tick(coord, mod, _when()) == 1
        (chore,) = _jobs(storage)
        assert chore.name == "🛒 Fetch logs from the shed"
        assert chore.points == 4 and chore.schedule_mode == "one_shot"
        assert chore.assignment_mode == "first_come" and sorted(chore.assigned_to) == sorted([kid.id, leo.id])
        assert calls[0] == ("todo", "get_items", {"entity_id": "todo.shopping_list", "status": ["needs_action"]})
        assert _tick(coord, mod, _when(minute=5)) == 0
        assert len(_jobs(storage)) == 1
        assert [e["kind"] for e in _fired(coord)] == ["added"]

    def test_the_list_is_read_every_two_minutes_at_most(self):
        coord, _storage, mod, *_rest, calls, _todo = _system()
        _tick(coord, mod, _when(minute=0))
        _tick(coord, mod, _when(minute=1))
        _tick(coord, mod, _when(minute=2))
        assert len(calls) == 2

    def test_done_and_approved_ticks_the_item_off(self):
        coord, storage, mod, kid, _leo, calls, _todo = _system(items=[_item("b", "#tm sweep the path")])
        _tick(coord, mod, _when())
        (chore,) = _jobs(storage)
        storage.add_completion(
            ChoreCompletion(chore_id=chore.id, child_id=kid.id, completed_at=_when(), approved=False)
        )
        _tick(coord, mod, _when(minute=5))
        assert not [c for c in calls if c[1] == "update_item"], "waits for approval"
        completion = next(c for c in storage.get_completions() if c.chore_id == chore.id)
        completion.approved = True
        storage.update_completion(completion)
        _tick(coord, mod, _when(minute=10))
        assert ("todo", "update_item", {"entity_id": "todo.shopping_list", "item": "b", "status": "completed"}) in calls
        assert storage.get_chore(chore.id).enabled is False
        _tick(coord, mod, _when(minute=15))
        assert storage.get_section("shopping_jobs", dict)["items"] == {}
        assert len(_jobs(storage)) == 1
        assert [e["kind"] for e in _fired(coord)] == ["added", "done"]

    def test_a_failed_tick_off_never_raises_the_job_twice(self):
        coord, storage, mod, kid, _leo, _calls, _todo = _system(items=[_item("b", "#tm sweep the path")])
        _tick(coord, mod, _when())
        (chore,) = _jobs(storage)
        storage.add_completion(ChoreCompletion(chore_id=chore.id, child_id=kid.id, completed_at=_when(), approved=True))
        coord.hass.services.async_call.side_effect = None
        coord.hass.services.async_call.return_value = {
            "todo.shopping_list": {"items": [_item("b", "#tm sweep the path")]}
        }
        _tick(coord, mod, _when(minute=5))
        _tick(coord, mod, _when(minute=10))
        assert len(_jobs(storage)) == 1

    def test_ticked_off_first_removes_the_chore_nobody_did(self):
        coord, storage, mod, *_rest, todo = _system(items=[_item("b", "#tm sweep the path")])
        _tick(coord, mod, _when())
        todo["items"][0]["status"] = "completed"
        _tick(coord, mod, _when(minute=5))
        assert _jobs(storage) == []
        assert [e["kind"] for e in _fired(coord)] == ["added", "removed"]
        # Nobody deleted it, so it isn't offered back in Recently deleted.
        assert coord.recently_deleted() == []

    def test_deleted_after_a_child_did_it_keeps_the_chore_for_the_parent(self):
        coord, storage, mod, kid, _leo, _calls, todo = _system(items=[_item("b", "#tm sweep the path")])
        _tick(coord, mod, _when())
        (chore,) = _jobs(storage)
        storage.add_completion(
            ChoreCompletion(chore_id=chore.id, child_id=kid.id, completed_at=_when(), approved=False)
        )
        todo["items"].clear()
        _tick(coord, mod, _when(minute=5))
        assert len(_jobs(storage)) == 1

    def test_a_failed_read_never_removes_chores(self):
        coord, storage, mod, *_rest, todo = _system(items=[_item("b", "#tm sweep the path")])
        _tick(coord, mod, _when())
        coord.hass.services.async_call.side_effect = RuntimeError("list gone")
        _tick(coord, mod, _when(minute=5))
        assert len(_jobs(storage)) == 1

    def test_an_undone_job_carries_over_to_the_next_day(self):
        coord, storage, mod, *_rest = _system(items=[_item("b", "#tm sweep the path")])
        _tick(coord, mod, _when(day=21))
        (chore,) = _jobs(storage)
        chore.enabled = False  # the midnight one-off sweep
        storage.update_chore(chore)
        _tick(coord, mod, _when(day=22, hour=0, minute=3))
        chore = storage.get_chore(chore.id)
        assert chore.enabled is True and chore.created_date == "2026-10-22"

    def test_rotate_hands_each_job_to_the_next_child(self):
        coord, storage, mod, kid, leo, _calls, todo = _system(mode="rotate", items=[_item("a", "#tm one")])
        _tick(coord, mod, _when())
        todo["items"].append(_item("b", "#tm two"))
        _tick(coord, mod, _when(minute=5))
        assert [c.assigned_to for c in _jobs(storage)] == [[kid.id], [leo.id]]

    def test_custom_tag_and_list(self):
        coord, storage, mod, *_rest, calls, _todo = _system(items=[_item("a", "!job wash the car")])
        storage.set_setting("shopping_jobs_tag", "!job")
        storage.set_setting("shopping_jobs_entity", "todo.jobs")
        _tick(coord, mod, _when())
        assert calls[0][2]["entity_id"] == "todo.jobs"
        assert [c.name for c in _jobs(storage)] == ["🛒 Wash the car"]

    def test_switched_off_does_nothing(self):
        coord, storage, mod, *_rest, calls, _todo = _system(items=[_item("a", "#tm x")])
        storage.set_setting("shopping_jobs_enabled", False)
        assert _tick(coord, mod, _when()) == 0
        assert calls == []


def test_settings_schema():
    from custom_components.taskmate.websocket import _SUBKEY_SETTINGS, _UPDATE_SETTINGS_SCHEMA, WS_UPDATE_SETTINGS

    base = {"type": WS_UPDATE_SETTINGS, "id": 1}
    schema = vol.Schema(_UPDATE_SETTINGS_SCHEMA, extra=vol.ALLOW_EXTRA)
    schema(
        {
            **base,
            "shopping_jobs_entity": "todo.shopping_list",
            "shopping_jobs_tag": "#tm",
            "shopping_jobs_mode": "rotate",
        }
    )
    with pytest.raises(vol.Invalid):
        schema({**base, "shopping_jobs_entity": "calendar.bins"})
    with pytest.raises(vol.Invalid):
        schema({**base, "shopping_jobs_tag": "two words"})
    assert {"shopping_jobs_enabled", "shopping_jobs_children"} <= _SUBKEY_SETTINGS
