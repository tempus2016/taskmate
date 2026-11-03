"""Chore services for clients without the panel's WebSocket API (#1156).

``update_chore`` / ``delete_chore`` and the scheduling fields on ``add_chore``.
What breaks silently here is the edges: a name that quietly resolves to the
wrong child, a refused edit that half-lands, a delete without the safeguard,
and a field the schema accepts that services.yaml / the translations never
declared (so the UI hides it).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol
import yaml

import custom_components.taskmate as tm
from custom_components.taskmate import chore_services as cs
from custom_components.taskmate.models import Chore

INTEGRATION = Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"


def _child(cid, name):
    return SimpleNamespace(id=cid, name=name)


def _coordinator(chore=None, children=None):
    coordinator = MagicMock()
    coordinator.storage.get_children = MagicMock(
        return_value=children or [_child("c1", "Malia"), _child("c2", "Vaiha"), _child("c3", "Ella")]
    )
    coordinator.storage.get_chore = MagicMock(return_value=chore)
    coordinator.async_update_chore = AsyncMock()
    coordinator.async_remove_chore = AsyncMock()
    coordinator.async_add_chore = AsyncMock(return_value=Chore(name="x", id="new"))
    coordinator.async_record_audit = AsyncMock()
    return coordinator


# ── child resolution ─────────────────────────────────────────────────────────


def test_children_resolve_by_id_and_by_name_any_case():
    assert cs.resolve_children(_coordinator(), ["c2", " malia ", "ELLA"]) == ["c2", "c1", "c3"]


def test_a_single_name_and_duplicates_are_fine():
    assert cs.resolve_children(_coordinator(), "Vaiha") == ["c2"]
    assert cs.resolve_children(_coordinator(), ["Vaiha", "c2"]) == ["c2"]


def test_an_empty_list_means_everyone():
    assert cs.resolve_children(_coordinator(), []) == []


def test_an_unknown_name_is_refused_with_the_valid_ones():
    with pytest.raises(tm.ServiceValidationError) as err:
        cs.resolve_children(_coordinator(), ["Bob"])
    assert "Bob" in str(err.value) and "Ella, Malia, Vaiha" in str(err.value)


def test_an_ambiguous_name_is_refused_not_guessed():
    kids = [_child("a1", "Sam"), _child("a2", "sam")]
    with pytest.raises(tm.ServiceValidationError, match="a1, a2"):
        cs.resolve_children(_coordinator(children=kids), ["Sam"])


def test_an_id_wins_over_a_name_that_spells_it():
    kids = [_child("c1", "Malia"), _child("c2", "c1")]
    assert cs.resolve_children(_coordinator(children=kids), ["c1"]) == ["c1"]


# ── field validators ─────────────────────────────────────────────────────────


def _update(data):
    return vol.Schema(cs.UPDATE_FIELDS)({"chore_id": "ch1", **data})


def test_schedule_fields_normalise():
    out = _update(
        {
            "due_days": ["Monday", "friday"],
            "recurrence": "Every_10_Days",
            "recurrence_day": "Sunday",
            "recurrence_start": "2026-11-02",
            "due_time": "7:05:00",
            "daily_limit": "3",
            "requires_approval": "false",
        }
    )
    assert out["due_days"] == ["monday", "friday"]
    assert out["recurrence"] == "every_10_days"
    assert out["recurrence_day"] == "sunday"
    assert out["recurrence_start"] == "2026-11-02"
    assert out["due_time"] == "07:05"
    assert out["daily_limit"] == 3
    assert out["requires_approval"] is False


def test_blank_values_clear_the_optional_schedule_settings():
    out = _update({"due_time": "", "recurrence_start": "", "recurrence_day": ""})
    assert out == {"chore_id": "ch1", "due_time": "", "recurrence_start": "", "recurrence_day": ""}


@pytest.mark.parametrize(
    "data",
    [
        {"due_days": ["funday"]},
        {"recurrence": "fortnightly"},
        {"recurrence": "every_400_days"},
        {"recurrence_start": "02/11/2026"},
        {"due_time": "25:00"},
        {"daily_limit": 0},
        {"assignment_mode": "oldest_first"},
        {"schedule_mode": "sometimes"},
        {"name": "   "},
        {"not_a_field": 1},
    ],
)
def test_bad_values_fail_the_schema(data):
    with pytest.raises(vol.Invalid):
        _update(data)


def test_delete_needs_confirm():
    schema = vol.Schema(cs.DELETE_FIELDS)
    with pytest.raises(vol.Invalid):
        schema({"chore_id": "ch1"})
    assert schema({"chore_id": "ch1", "confirm": "true"})["confirm"] is True


# ── update_chore ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_changes_only_the_named_fields():
    chore = Chore(name="Bins", id="ch1", points=5, description="Out by 8")
    coordinator = _coordinator(chore)
    await cs.async_update_chore_from_call(
        coordinator,
        {
            "chore_id": "ch1",
            "points": 8,
            "assigned_to": ["Malia", "c2"],
            "assignment_mode": "alternating",
            "schedule_mode": "specific_days",
            "due_days": ["tuesday"],
            "due_time": "19:30",
        },
    )
    saved = coordinator.async_update_chore.await_args.args[0]
    assert saved.points == 8 and saved.assigned_to == ["c1", "c2"]
    assert saved.assignment_mode == "alternating" and saved.due_days == ["tuesday"] and saved.due_time == "19:30"
    assert saved.name == "Bins" and saved.description == "Out by 8"


@pytest.mark.asyncio
async def test_update_to_one_shot_is_for_today_once():
    chore = Chore(name="Bins", id="ch1", daily_limit=3, schedule_mode="specific_days", created_date="2025-01-01")
    coordinator = _coordinator(chore)
    await cs.async_update_chore_from_call(coordinator, {"chore_id": "ch1", "schedule_mode": "one_shot"})
    saved = coordinator.async_update_chore.await_args.args[0]
    assert saved.daily_limit == 1 and saved.created_date == cs._today()


@pytest.mark.asyncio
async def test_a_one_shot_chore_keeps_its_limit_of_one():
    chore = Chore(name="Bins", id="ch1", schedule_mode="one_shot", created_date="2026-10-29")
    coordinator = _coordinator(chore)
    await cs.async_update_chore_from_call(coordinator, {"chore_id": "ch1", "daily_limit": 4})
    saved = coordinator.async_update_chore.await_args.args[0]
    assert saved.daily_limit == 1 and saved.created_date == "2026-10-29"


@pytest.mark.asyncio
async def test_update_of_a_missing_chore_is_refused():
    coordinator = _coordinator(None)
    with pytest.raises(tm.ServiceValidationError, match="not found"):
        await cs.async_update_chore_from_call(coordinator, {"chore_id": "gone", "points": 1})
    coordinator.async_update_chore.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_with_nothing_to_change_is_refused():
    coordinator = _coordinator(Chore(name="Bins", id="ch1"))
    with pytest.raises(tm.ServiceValidationError, match="Nothing to update"):
        await cs.async_update_chore_from_call(coordinator, {"chore_id": "ch1"})


@pytest.mark.asyncio
async def test_update_with_an_unknown_child_changes_nothing():
    coordinator = _coordinator(Chore(name="Bins", id="ch1"))
    with pytest.raises(tm.ServiceValidationError, match="Unknown child"):
        await cs.async_update_chore_from_call(coordinator, {"chore_id": "ch1", "points": 3, "assigned_to": ["Bob"]})
    coordinator.async_update_chore.assert_not_awaited()


# ── delete_chore ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_uses_the_panels_removal():
    coordinator = _coordinator(Chore(name="Bins", id="ch1"))
    await cs.async_delete_chore_from_call(coordinator, {"chore_id": "ch1", "confirm": True})
    coordinator.async_remove_chore.assert_awaited_once_with("ch1")


@pytest.mark.asyncio
async def test_delete_without_confirm_is_refused():
    coordinator = _coordinator(Chore(name="Bins", id="ch1"))
    with pytest.raises(tm.ServiceValidationError, match="confirm"):
        await cs.async_delete_chore_from_call(coordinator, {"chore_id": "ch1", "confirm": False})
    coordinator.async_remove_chore.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_of_a_missing_chore_is_refused():
    coordinator = _coordinator(None)
    with pytest.raises(tm.ServiceValidationError, match="not found"):
        await cs.async_delete_chore_from_call(coordinator, {"chore_id": "gone", "confirm": True})


# ── registration, gate and audit ─────────────────────────────────────────────


async def _registered() -> dict:
    registered: dict = {}

    class _Services:
        def async_register(self, domain, name, handler, schema=None):
            registered[name] = (handler, schema)

    hass = SimpleNamespace(services=_Services())
    await tm._async_register_services(hass)
    return registered


def _call(service, data, user_id=None):
    return SimpleNamespace(service=service, data=data, context=SimpleNamespace(user_id=user_id))


@pytest.mark.asyncio
async def test_update_and_delete_are_registered_and_unregistered():
    registered = await _registered()
    assert {"update_chore", "delete_chore"} <= set(registered)
    removed = []
    hass = SimpleNamespace(services=SimpleNamespace(async_remove=lambda domain, name: removed.append(name)))
    tm._async_unregister_services(hass)
    assert {"update_chore", "delete_chore"} <= set(removed)


@pytest.mark.asyncio
async def test_automation_calls_run_and_are_audited(monkeypatch):
    coordinator = _coordinator(Chore(name="Bins", id="ch1"))
    monkeypatch.setattr(tm, "_get_coordinator", lambda hass: coordinator)
    handler, _ = (await _registered())["delete_chore"]
    await handler(_call("delete_chore", {"chore_id": "ch1", "confirm": True}))
    coordinator.async_remove_chore.assert_awaited_once_with("ch1")
    assert coordinator.async_record_audit.await_args.args[2] == "service.delete_chore"


@pytest.mark.asyncio
async def test_a_non_admin_user_is_refused_and_the_refusal_audited(monkeypatch):
    coordinator = _coordinator(Chore(name="Bins", id="ch1"))
    monkeypatch.setattr(tm, "_get_coordinator", lambda hass: coordinator)
    registered: dict = {}

    class _Services:
        def async_register(self, domain, name, handler, schema=None):
            registered[name] = handler

    hass = SimpleNamespace(services=_Services(), auth=SimpleNamespace())
    hass.auth.async_get_user = AsyncMock(return_value=SimpleNamespace(is_admin=False, name="Kid"))
    await tm._async_register_services(hass)
    with pytest.raises(tm.Unauthorized):
        await registered["update_chore"](_call("update_chore", {"chore_id": "ch1", "points": 1}, user_id="kid"))
    coordinator.async_update_chore.assert_not_awaited()
    assert coordinator.async_record_audit.await_args.args[2] == "service.update_chore (denied)"


@pytest.mark.asyncio
async def test_add_chore_passes_the_schedule_through_and_resolves_names(monkeypatch):
    coordinator = _coordinator()
    monkeypatch.setattr(tm, "_get_coordinator", lambda hass: coordinator)
    handler, _ = (await _registered())["add_chore"]
    await handler(
        _call(
            "add_chore",
            {
                "name": "Feed the cat",
                "assigned_to": ["malia", "Vaiha"],
                "assignment_mode": "alternating",
                "schedule_mode": "recurring",
                "recurrence": "every_2_weeks",
                "recurrence_day": "saturday",
                "recurrence_start": "2026-11-07",
                "due_time": "08:00",
                "daily_limit": 2,
            },
        )
    )
    kwargs = coordinator.async_add_chore.await_args.kwargs
    assert kwargs["assigned_to"] == ["c1", "c2"]
    assert kwargs["schedule_mode"] == "recurring" and kwargs["recurrence"] == "every_2_weeks"
    assert kwargs["recurrence_day"] == "saturday" and kwargs["recurrence_start"] == "2026-11-07"
    assert kwargs["assignment_mode"] == "alternating" and kwargs["due_time"] == "08:00" and kwargs["daily_limit"] == 2


@pytest.mark.asyncio
async def test_add_chore_one_shot_still_wins_and_old_calls_are_unchanged(monkeypatch):
    coordinator = _coordinator()
    monkeypatch.setattr(tm, "_get_coordinator", lambda hass: coordinator)
    handler, _ = (await _registered())["add_chore"]
    await handler(_call("add_chore", {"name": "Empty washer", "one_shot": True, "schedule_mode": "recurring"}))
    kwargs = coordinator.async_add_chore.await_args.kwargs
    assert kwargs["schedule_mode"] == "one_shot"
    assert not {"assignment_mode", "due_days", "recurrence", "due_time", "daily_limit"} & set(kwargs)


@pytest.mark.asyncio
async def test_add_chore_with_an_unknown_child_creates_nothing(monkeypatch):
    coordinator = _coordinator()
    monkeypatch.setattr(tm, "_get_coordinator", lambda hass: coordinator)
    handler, _ = (await _registered())["add_chore"]
    with pytest.raises(tm.ServiceValidationError, match="Unknown child"):
        await handler(_call("add_chore", {"name": "Feed the cat", "assigned_to": ["Bob"]}))
    coordinator.async_add_chore.assert_not_awaited()


# ── declared surface ─────────────────────────────────────────────────────────


def _schema_keys(schema) -> set[str]:
    return {str(getattr(marker, "schema", marker)) for marker in schema.schema}


def _locale_files():
    return [INTEGRATION / "strings.json", *sorted((INTEGRATION / "translations").glob("*.json"))]


@pytest.mark.asyncio
@pytest.mark.parametrize("service", ["add_chore", "update_chore", "delete_chore"])
async def test_every_schema_field_is_declared_and_translated(service):
    _, schema = (await _registered())[service]
    declared = yaml.safe_load((INTEGRATION / "services.yaml").read_text(encoding="utf-8"))[service]["fields"]
    keys = _schema_keys(schema)
    if service != "add_chore":
        # add_chore's older fields predate this; the new services are held to it fully.
        assert keys == set(declared)
    for path in _locale_files():
        entry = json.loads(path.read_text(encoding="utf-8"))["services"][service]
        assert entry["name"] and entry["description"], path.name
        for field in keys & {str(k.schema) for k in cs.SCHEDULE_FIELDS} | (keys if service != "add_chore" else set()):
            assert field in declared, field
            assert entry["fields"][field]["name"] and entry["fields"][field]["description"], (path.name, field)
