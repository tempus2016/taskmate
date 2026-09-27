"""Tests for presence-aware reminders (#926).

A child linked to a person/device_tracker entity only gets nagged while home:
reminders and escalations are held while they're out, and a single
"you're home — N chores left" nudge replaces them on arrival.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol

from custom_components.taskmate import coord_notifications as cn
from custom_components.taskmate.coord_notifications import NotificationCoordinator
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import (
    Child,
    Chore,
    CustomNotification,
    MandatoryMiss,
    NotificationRoute,
    ParentRecipient,
)
from custom_components.taskmate.storage import TaskMateStorage
from custom_components.taskmate.websocket import _validate_presence_entity

from .conftest import dt_util_mock

NOW = datetime(2024, 3, 20, 12, 0, tzinfo=timezone.utc)  # conftest's frozen "now"
PRESENCE = "person.alex"


def _states(hass, mapping: dict[str, str], last_changed: datetime | None = None) -> None:
    """Point hass.states.get at a {entity_id: state} map (mutable by the test)."""

    def _get(entity_id):
        if entity_id not in mapping:
            return None
        return SimpleNamespace(state=mapping[entity_id], last_changed=last_changed or NOW)

    hass.states = MagicMock()
    hass.states.get = MagicMock(side_effect=_get)


@pytest.fixture
async def notif(hass):
    storage = TaskMateStorage(hass, "test")
    await storage.async_load()
    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = MagicMock()
    return NotificationCoordinator(hass, storage)


def _add_child(notif, **kw) -> Child:
    child = Child(name="Alex", notify_service="notify.alex", presence_entity=PRESENCE, **kw)
    notif.storage.add_child(child)
    return child


def _route(notif, type_id: str, recipient_id: str) -> None:
    notif.storage.set_notification_master(type_id, True)
    notif.storage.set_notification_route(type_id, recipient_id, NotificationRoute(enabled=True))


def _notify_calls(hass) -> list[tuple[str, dict]]:
    return [(c[0][1], c[0][2]) for c in hass.services.async_call.call_args_list if c[0][0] == "notify"]


# --- model / storage --------------------------------------------------------


def test_child_presence_entity_round_trips():
    child = Child(name="Alex", presence_entity=PRESENCE)
    assert Child.from_dict(child.to_dict()).presence_entity == PRESENCE


def test_old_child_data_defaults_to_no_presence():
    child = Child.from_dict({"name": "Alex", "id": "c1"})
    assert child.presence_entity == ""


@pytest.mark.asyncio
async def test_min_away_setting_defaults_and_clamps(notif):
    assert notif.storage.get_presence_arrival_min_away() == 30
    notif.storage.set_presence_arrival_min_away(45)
    assert notif.storage.get_presence_arrival_min_away() == 45
    notif.storage.set_presence_arrival_min_away(-5)
    assert notif.storage.get_presence_arrival_min_away() == 0
    notif.storage._data["settings"]["presence_arrival_min_away"] = "junk"
    assert notif.storage.get_presence_arrival_min_away() == 30


def test_ws_validator_accepts_person_and_device_tracker_only():
    assert _validate_presence_entity("") == ""
    assert _validate_presence_entity(None) == ""
    assert _validate_presence_entity(" person.alex ") == "person.alex"
    assert _validate_presence_entity("device_tracker.alex_phone") == "device_tracker.alex_phone"
    with pytest.raises(vol.Invalid):
        _validate_presence_entity("binary_sensor.alex_home")


def test_arrival_type_is_registered_for_children():
    meta = cn.NOTIFICATION_TYPES_BY_ID["presence_arrival"]
    assert meta.audience == "child"
    assert meta.default_enabled is False
    assert meta.actionable is False


# --- deferral in fire() -----------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("type_id", ["mandatory_reminder", "bedtime_reminder", "streak_at_risk"])
async def test_reminders_held_while_child_away(notif, hass, type_id):
    child = _add_child(notif)
    _route(notif, type_id, f"child:{child.id}")
    _states(hass, {PRESENCE: "not_home"})

    await notif.fire(type_id, {"child_name": "Alex", "chore_name": "Homework", "streak": 3})

    assert _notify_calls(hass) == []
    assert child.id in notif._presence_deferred
    # The bus event still fires for automations, with no recipients.
    payload = hass.bus.async_fire.call_args[0][1]
    assert payload["recipients"] == []


@pytest.mark.asyncio
async def test_reminder_delivered_while_child_home(notif, hass):
    child = _add_child(notif)
    _route(notif, "mandatory_reminder", f"child:{child.id}")
    _states(hass, {PRESENCE: "home"})

    await notif.fire("mandatory_reminder", {"child_name": "Alex", "chore_name": "Homework"})

    assert [s for s, _ in _notify_calls(hass)] == ["alex"]
    assert notif._presence_deferred == set()


@pytest.mark.asyncio
async def test_zone_name_counts_as_away(notif, hass):
    child = _add_child(notif)
    _route(notif, "mandatory_reminder", f"child:{child.id}")
    _states(hass, {PRESENCE: "School"})

    await notif.fire("mandatory_reminder", {"child_name": "Alex", "chore_name": "Homework"})

    assert _notify_calls(hass) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["unavailable", "unknown", None])
async def test_broken_tracker_fails_open(notif, hass, state):
    child = _add_child(notif)
    _route(notif, "mandatory_reminder", f"child:{child.id}")
    _states(hass, {} if state is None else {PRESENCE: state})

    await notif.fire("mandatory_reminder", {"child_name": "Alex", "chore_name": "Homework"})

    assert [s for s, _ in _notify_calls(hass)] == ["alex"]


@pytest.mark.asyncio
async def test_good_news_is_never_held(notif, hass):
    child = _add_child(notif)
    _route(notif, "badge_earned", f"child:{child.id}")
    _states(hass, {PRESENCE: "not_home"})

    await notif.fire("badge_earned", {"child_name": "Alex", "badge_name": "Star"})

    assert [s for s, _ in _notify_calls(hass)] == ["alex"]
    assert notif._presence_deferred == set()


@pytest.mark.asyncio
async def test_child_without_presence_entity_is_unaffected(notif, hass):
    child = Child(name="Sam", notify_service="notify.sam")
    notif.storage.add_child(child)
    _route(notif, "mandatory_reminder", f"child:{child.id}")
    _states(hass, {})

    await notif.fire("mandatory_reminder", {"child_name": "Sam", "chore_name": "Homework"})

    assert [s for s, _ in _notify_calls(hass)] == ["sam"]


@pytest.mark.asyncio
async def test_custom_reminder_held_for_away_child_only(notif, hass):
    away = _add_child(notif)
    home = Child(name="Sam", notify_service="notify.sam")
    notif.storage.add_child(home)
    custom = CustomNotification(
        name="Homework",
        message_template="{child_name}, homework time",
        time="17:00",
        day_mask=0b1111111,
        recipient_ids=[f"child:{away.id}", f"child:{home.id}"],
    )
    notif.storage.upsert_custom_notification(custom)
    _states(hass, {PRESENCE: "not_home"})

    await notif._make_custom_callback(custom.id)(NOW)

    assert [s for s, _ in _notify_calls(hass)] == ["sam"]
    assert away.id in notif._presence_deferred


# --- subscription lifecycle ---------------------------------------------------


@pytest.mark.asyncio
async def test_sync_subscribes_and_is_idempotent(notif, hass, monkeypatch):
    unsub = MagicMock()
    track = MagicMock(return_value=unsub)
    monkeypatch.setattr(cn, "async_track_state_change_event", track)
    _states(hass, {PRESENCE: "home"})
    _add_child(notif)

    notif.sync_presence_tracking()
    notif.sync_presence_tracking()  # nothing changed -> no resubscribe

    assert track.call_count == 1
    assert track.call_args[0][1] == [PRESENCE]
    unsub.assert_not_called()


@pytest.mark.asyncio
async def test_sync_resubscribes_on_change_and_unsubscribes_on_removal(notif, hass, monkeypatch):
    unsubs = [MagicMock(), MagicMock()]
    track = MagicMock(side_effect=unsubs)
    monkeypatch.setattr(cn, "async_track_state_change_event", track)
    _states(hass, {PRESENCE: "home", "device_tracker.alex_phone": "home"})
    child = _add_child(notif)
    notif.sync_presence_tracking()

    child.presence_entity = "device_tracker.alex_phone"
    notif.storage.update_child(child)
    notif.sync_presence_tracking()
    unsubs[0].assert_called_once()
    assert track.call_args[0][1] == ["device_tracker.alex_phone"]

    child.presence_entity = ""
    notif.storage.update_child(child)
    notif.sync_presence_tracking()
    unsubs[1].assert_called_once()
    assert track.call_count == 2  # nothing left to track -> no new subscription
    assert notif._presence_unsub is None


@pytest.mark.asyncio
async def test_cancel_presence_tracking_is_idempotent(notif, hass, monkeypatch):
    unsub = MagicMock()
    monkeypatch.setattr(cn, "async_track_state_change_event", MagicMock(return_value=unsub))
    _states(hass, {PRESENCE: "home"})
    _add_child(notif)
    notif.sync_presence_tracking()

    notif.cancel_presence_tracking()
    notif.cancel_presence_tracking()

    unsub.assert_called_once()


@pytest.mark.asyncio
async def test_sync_seeds_an_absence_already_under_way(notif, hass, monkeypatch):
    monkeypatch.setattr(cn, "async_track_state_change_event", MagicMock())
    left = NOW - timedelta(hours=2)
    _states(hass, {PRESENCE: "not_home"}, last_changed=left)
    child = _add_child(notif)

    notif.sync_presence_tracking()

    assert notif._presence_away_since[child.id] == left


# --- arrival -------------------------------------------------------------------


def _event(entity_id: str, state: str | None):
    new_state = None if state is None else SimpleNamespace(state=state)
    return SimpleNamespace(data={"entity_id": entity_id, "new_state": new_state})


@pytest.fixture
def tracked(notif, hass, monkeypatch):
    """A tracked away-capable child, with async_create_task captured."""
    monkeypatch.setattr(cn, "async_track_state_change_event", MagicMock())
    _states(hass, {PRESENCE: "home"})
    child = _add_child(notif)
    notif.sync_presence_tracking()
    tasks: list = []

    def _capture(coro):
        tasks.append(coro)

    hass.async_create_task = _capture
    notif.async_arrival_nudge = MagicMock(side_effect=lambda *a: ("nudge", a))
    return child, tasks


def test_leaving_starts_an_absence_and_zone_hops_keep_it(notif, tracked, monkeypatch):
    child, _ = tracked
    monkeypatch.setattr(dt_util_mock, "_now", NOW)
    notif._presence_state_changed(_event(PRESENCE, "not_home"))
    monkeypatch.setattr(dt_util_mock, "_now", NOW + timedelta(minutes=20))
    notif._presence_state_changed(_event(PRESENCE, "School"))

    assert notif._presence_away_since[child.id] == NOW


def test_arrival_schedules_one_nudge_despite_jitter(notif, tracked, monkeypatch):
    child, tasks = tracked
    monkeypatch.setattr(dt_util_mock, "_now", NOW)
    notif._presence_state_changed(_event(PRESENCE, "not_home"))
    arrived = NOW + timedelta(minutes=45)
    monkeypatch.setattr(dt_util_mock, "_now", arrived)

    notif._presence_state_changed(_event(PRESENCE, "home"))
    notif._presence_state_changed(_event(PRESENCE, "home"))  # GPS update while home

    assert len(tasks) == 1
    notif.async_arrival_nudge.assert_called_once_with(child.id, NOW, False, arrived)
    assert child.id not in notif._presence_away_since


def test_unavailable_neither_starts_nor_ends_an_absence(notif, tracked):
    child, tasks = tracked
    notif._presence_state_changed(_event(PRESENCE, "unavailable"))
    assert child.id not in notif._presence_away_since

    notif._presence_away_since[child.id] = NOW
    notif._presence_state_changed(_event(PRESENCE, "unavailable"))
    assert notif._presence_away_since[child.id] == NOW
    assert tasks == []


def test_untracked_entity_is_ignored(notif, tracked):
    _, tasks = tracked
    notif._presence_state_changed(_event("person.someone_else", "home"))
    assert tasks == []


def test_arrival_passes_on_the_deferred_flag_once(notif, tracked):
    child, tasks = tracked
    notif._presence_deferred.add(child.id)

    notif._presence_state_changed(_event(PRESENCE, "home"))
    notif._presence_state_changed(_event(PRESENCE, "home"))

    assert len(tasks) == 1
    assert notif.async_arrival_nudge.call_args[0][2] is True
    assert notif._presence_deferred == set()


@pytest.fixture
def nudge_setup(notif, hass):
    child = _add_child(notif)
    _route(notif, "presence_arrival", f"child:{child.id}")
    _states(hass, {PRESENCE: "home"})
    notif.coordinator = SimpleNamespace(get_due_chores_for_child=MagicMock(return_value=["a", "b"]))
    return child


@pytest.mark.asyncio
async def test_nudge_after_a_long_absence(notif, hass, nudge_setup):
    child = nudge_setup
    fired = await notif.async_arrival_nudge(child.id, NOW - timedelta(minutes=45), False, NOW)

    assert fired is True
    calls = _notify_calls(hass)
    assert [s for s, _ in calls] == ["alex"]
    assert "2 chores left" in calls[0][1]["message"]
    assert "Alex" in calls[0][1]["message"]


@pytest.mark.asyncio
async def test_no_nudge_after_a_short_trip(notif, hass, nudge_setup):
    child = nudge_setup
    fired = await notif.async_arrival_nudge(child.id, NOW - timedelta(minutes=10), False, NOW)

    assert fired is False
    assert _notify_calls(hass) == []


@pytest.mark.asyncio
async def test_min_away_is_configurable(notif, hass, nudge_setup):
    child = nudge_setup
    notif.storage.set_presence_arrival_min_away(5)
    assert await notif.async_arrival_nudge(child.id, NOW - timedelta(minutes=10), False, NOW) is True


@pytest.mark.asyncio
async def test_held_reminder_nudges_even_after_a_short_trip(notif, hass, nudge_setup):
    child = nudge_setup
    assert await notif.async_arrival_nudge(child.id, NOW - timedelta(minutes=5), True, NOW) is True
    assert len(_notify_calls(hass)) == 1


@pytest.mark.asyncio
async def test_no_nudge_when_nothing_is_outstanding(notif, hass, nudge_setup):
    child = nudge_setup
    notif.coordinator.get_due_chores_for_child.return_value = []
    assert await notif.async_arrival_nudge(child.id, NOW - timedelta(hours=3), True, NOW) is False
    assert _notify_calls(hass) == []


@pytest.mark.asyncio
async def test_nudge_respects_quiet_hours(notif, hass, nudge_setup, monkeypatch):
    child = nudge_setup
    child.quiet_hours_start = "20:00"
    child.quiet_hours_end = "07:00"
    notif.storage.update_child(child)
    late = datetime(2024, 3, 20, 22, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(dt_util_mock, "_now", late)

    await notif.async_arrival_nudge(child.id, late - timedelta(hours=3), True, late)

    assert _notify_calls(hass) == []


@pytest.mark.asyncio
async def test_nudge_only_reaches_the_arriving_child(notif, hass, nudge_setup):
    child = nudge_setup
    sibling = Child(name="Sam", notify_service="notify.sam")
    notif.storage.add_child(sibling)
    notif.storage.set_notification_route("presence_arrival", f"child:{sibling.id}", NotificationRoute(enabled=True))

    await notif.async_arrival_nudge(child.id, NOW - timedelta(hours=1), False, NOW)

    assert [s for s, _ in _notify_calls(hass)] == ["alex"]


# --- mandatory escalation ladder ------------------------------------------------


@pytest.fixture
async def mcoord(hass):
    storage = TaskMateStorage(hass, "test")
    await storage.async_load()
    hass.services.async_call = AsyncMock()
    c = object.__new__(TaskMateCoordinator)
    c.storage = storage
    c.hass = hass
    c.notifications = NotificationCoordinator(hass, storage)
    return c


def _mandatory_setup(coord):
    child = Child(name="Alex", notify_service="notify.alex", presence_entity=PRESENCE)
    coord.storage.add_child(child)
    chore = Chore(name="Homework", mandatory=True)
    coord.storage.add_chore(chore)
    coord.storage.set_notification_master("mandatory_reminder", True)
    coord.storage.set_notification_route("mandatory_reminder", f"child:{child.id}", NotificationRoute(enabled=True))
    parent = ParentRecipient(name="John", notify_service="notify.john")
    coord.storage.upsert_parent_recipient(parent)
    coord.storage.set_notification_master("mandatory_parent_alert", True)
    coord.storage.set_notification_route("mandatory_parent_alert", parent.id, NotificationRoute(enabled=True))
    miss = MandatoryMiss(
        chore_id=chore.id,
        child_id=child.id,
        due_date="2024-03-20",
        period_id="morning",
        created_at="2024-03-20T09:00:00+00:00",
    )
    coord.storage.add_mandatory_miss(miss)
    return child, miss


def _at(hour: int) -> datetime:
    return datetime(2024, 3, 20, hour, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_escalation_held_while_away_then_resumes(mcoord, hass):
    child, miss = _mandatory_setup(mcoord)
    states = {PRESENCE: "not_home"}
    _states(hass, states)

    # 3 h in: past the parent threshold, but the child is out.
    await mcoord.async_escalate_mandatory_misses(_at(12))
    assert _notify_calls(hass) == []  # no child reminder, no parent alert
    assert mcoord.storage.get_mandatory_misses()[0].escalation_stage == 2
    assert child.id in mcoord.notifications._presence_deferred

    # Home again: the held reminders are NOT replayed; only the parent alert
    # (the one stage still owed) goes out.
    states[PRESENCE] = "home"
    await mcoord.async_escalate_mandatory_misses(_at(13))
    assert [s for s, _ in _notify_calls(hass)] == ["john"]
    assert mcoord.storage.get_mandatory_misses()[0].escalation_stage == 3
