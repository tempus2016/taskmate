"""Choice sets (#1259): "do at least N of these chores", the child picks which.

Progress is counted from the day's completions (pending ones count, a
rejected one frees the slot, a chore done twice counts once). An unmet set
leaves one review item per set, child and day at midnight, never an automatic
deduction. For streaks and perfect weeks the set is one due item.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import pathlib
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol
import yaml

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.choice_set_services import CHOICE_SET_SERVICES
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.errors import TaskMateError
from custom_components.taskmate.models import ChoiceSet, Chore, MandatoryMiss
from custom_components.taskmate.storage import TaskMateStorage

from .conftest import FakeHass, FakeStore, dt_util_mock

UTC = dt.timezone.utc
NOW = dt.datetime(2024, 3, 20, 12, 0, tzinfo=UTC)  # a Wednesday
TODAY = NOW.date()
ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "custom_components" / "taskmate"


@pytest.fixture(autouse=True)
def _clock():
    saved = dt_util_mock._now
    dt_util_mock._now = NOW
    yield
    dt_util_mock._now = saved


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _system(settings: dict | None = None):
    hass = FakeHass()
    hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()
    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    await storage.async_load()
    for key, value in (settings or {}).items():
        storage.set_setting(key, value)
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.data = {}
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    coord._async_notify_pending_approval = AsyncMock()
    notifications = MagicMock()
    notifications.fire = AsyncMock()
    notifications.clear_approval = AsyncMock()
    notifications._has_outstanding_chores_today = lambda _cid: True
    coord.notifications = notifications
    return coord


async def _family(coord, n_chores=3, **chore_kw):
    child = await coord.async_add_child("Malia")
    chores = []
    for i in range(n_chores):
        chores.append(
            await coord.async_add_chore(
                f"Chore {i}",
                points=5,
                requires_approval=chore_kw.get("requires_approval", False),
                schedule_mode="specific_days",
                daily_limit=chore_kw.get("daily_limit", 1),
            )
        )
    return child, chores


def _events(coord, name):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == name]


def _status(coord, set_id, child_id, day=TODAY):
    return coord.choice_set_status(coord.storage.get_choice_set(set_id), child_id, day)


# ── model ────────────────────────────────────────────────────────────────


def test_model_round_trip_and_defaults():
    cs = ChoiceSet.from_dict({"name": "Your part", "chore_ids": ["a", "b", "a"]})
    assert cs.min_required == 1 and cs.penalty_points == 0 and cs.active is True
    assert cs.chore_ids == ["a", "b"]  # duplicates dropped
    again = ChoiceSet.from_dict(cs.to_dict())
    assert again == cs
    assert ChoiceSet.from_dict({"name": "x", "min_required": -3, "penalty_points": "bad"}).min_required == 0
    assert ChoiceSet.from_dict({"name": "x", "min_required": 0}).min_required == 0


def test_created_on_round_trips_and_falls_back_to_today():
    cs = ChoiceSet.from_dict({"name": "x", "created_on": "2024-01-02"})
    assert cs.created_on == "2024-01-02"
    assert ChoiceSet.from_dict(cs.to_dict()).created_on == "2024-01-02"
    # Saved before the field existed (or garbage): today, so nothing is backfilled.
    assert ChoiceSet.from_dict({"name": "x"}).created_on == TODAY.isoformat()
    assert ChoiceSet.from_dict({"name": "x", "created_on": "nope"}).created_on == TODAY.isoformat()


def test_storage_stamps_old_sets_once_on_load():
    async def go():
        storage = TaskMateStorage.__new__(TaskMateStorage)
        storage.entry_id = "test_entry"
        storage._store = FakeStore(None, 1, "test")
        storage._store._data = {"choice_sets": [{"id": "s1", "name": "Old", "chore_ids": ["a"]}]}
        storage._data = {}
        await storage.async_load()
        assert storage._data["choice_sets"][0]["created_on"] == TODAY.isoformat()
        # A later day still reads the stamped date, not "today".
        dt_util_mock._now = NOW + dt.timedelta(days=3)
        assert storage.get_choice_set("s1").created_on == TODAY.isoformat()

    run(go())


def test_restart_on_the_creation_day_backfills_nothing():
    async def go():
        coord = await _system()
        child, chores = await _family(coord, 3)
        set_id = await coord.async_create_choice_set(name="Set", chore_ids=[c.id for c in chores], min_required=1)
        assert coord.storage.get_choice_set(set_id).created_on == TODAY.isoformat()
        # HA restarts later the same day: the catch-up looks at yesterday.
        await coord.async_catchup_choice_set_misses()
        assert coord.storage.get_mandatory_misses() == []
        assert await coord.async_detect_choice_set_misses(TODAY - dt.timedelta(days=1)) == 0
        # Editing the set never moves its date.
        await coord.async_update_choice_set(set_id, created_on="2000-01-01", min_required=2)
        assert coord.storage.get_choice_set(set_id).created_on == TODAY.isoformat()

    run(go())


def test_a_set_created_yesterday_still_gets_its_miss_on_restart():
    async def go():
        coord = await _system()
        await _family(coord, 3)
        chores = coord.storage.get_chores()
        await coord.async_create_choice_set(name="Set", chore_ids=[c.id for c in chores], min_required=1)
        dt_util_mock._now = NOW + dt.timedelta(days=1)
        await coord.async_catchup_choice_set_misses()
        (miss,) = coord.storage.get_mandatory_misses()
        assert miss.due_date == TODAY.isoformat()

    run(go())


def test_a_member_chore_dated_after_the_day_is_not_on_offer():
    async def go():
        coord = await _system()
        child, chores = await _family(coord, 2)
        set_id = await coord.async_create_choice_set(name="Set", chore_ids=[c.id for c in chores], min_required=2)
        c = coord.storage.get_chore(chores[1].id)
        c.created_date = (TODAY + dt.timedelta(days=1)).isoformat()
        coord.storage.update_chore(c)
        assert _status(coord, set_id, child.id) == {"min": 1, "done": 0, "fulfilled": False}

    run(go())


def test_miss_carries_set_id_only_when_set():
    miss = MandatoryMiss(chore_id="", child_id="k", due_date="2024-03-19", period_id="anytime", set_id="s1")
    assert MandatoryMiss.from_dict(miss.to_dict()).set_id == "s1"
    plain = MandatoryMiss(chore_id="c", child_id="k", due_date="2024-03-19", period_id="anytime")
    assert "set_id" not in plain.to_dict()


# ── validation ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("change", "key"),
    [
        ({"mandatory": True}, "choice_set_mandatory_member"),
        ({"assignment_mode": "alternating"}, "choice_set_rotation_member"),
        ({"assignment_mode": "random"}, "choice_set_rotation_member"),
        ({"assignment_mode": "unassigned"}, "choice_set_rotation_member"),
        ({"assignment_mode": "first_come"}, "choice_set_first_come_member"),
    ],
)
def test_members_that_cannot_join_are_refused(change, key):
    async def go():
        coord = await _system()
        _child, chores = await _family(coord, 2)
        chore = coord.storage.get_chore(chores[0].id)
        for k, v in change.items():
            setattr(chore, k, v)
        coord.storage.update_chore(chore)
        with pytest.raises(TaskMateError) as err:
            await coord.async_create_choice_set(name="Set", chore_ids=[chores[0].id, chores[1].id])
        assert err.value.translation_key == key
        assert err.value.translation_placeholders["name"] == "Chore 0"
        assert coord.storage.get_choice_sets() == []

    run(go())


def test_a_chore_can_be_in_one_set_only():
    async def go():
        coord = await _system()
        _child, chores = await _family(coord, 2)
        first = await coord.async_create_choice_set(name="First", chore_ids=[chores[0].id])
        with pytest.raises(TaskMateError) as err:
            await coord.async_create_choice_set(name="Second", chore_ids=[chores[0].id, chores[1].id])
        assert err.value.translation_key == "choice_set_chore_in_other_set"
        # Saving the first set again with its own chore is fine.
        await coord.async_update_choice_set(first, min_required=1)

    run(go())


@pytest.mark.parametrize(
    "change",
    [
        {"mandatory": True},
        {"assignment_mode": "alternating"},
        {"assignment_mode": "random"},
        {"assignment_mode": "first_come"},
    ],
)
def test_a_member_chore_cannot_be_edited_into_a_forbidden_kind(change):
    async def go():
        coord = await _system()
        _child, chores = await _family(coord, 2)
        await coord.async_create_choice_set(name="Your part", chore_ids=[c.id for c in chores])
        edited = Chore.from_dict(coord.storage.get_chore(chores[0].id).to_dict())
        for k, v in change.items():
            setattr(edited, k, v)
        with pytest.raises(TaskMateError) as err:
            await coord.async_update_chore(edited)
        assert err.value.translation_key == "choice_set_member_locked"
        assert err.value.translation_placeholders == {"name": "Chore 0", "set": "Your part"}
        stored = coord.storage.get_chore(chores[0].id)
        assert stored.mandatory is False and stored.assignment_mode == "everyone"

    run(go())


def test_member_chores_still_take_ordinary_edits_and_non_members_are_free():
    async def go():
        coord = await _system()
        _child, chores = await _family(coord, 2)
        await coord.async_create_choice_set(name="Your part", chore_ids=[chores[0].id])
        member = Chore.from_dict(coord.storage.get_chore(chores[0].id).to_dict())
        member.points = 9
        await coord.async_update_chore(member)
        assert coord.storage.get_chore(chores[0].id).points == 9
        outsider = Chore.from_dict(coord.storage.get_chore(chores[1].id).to_dict())
        outsider.mandatory = True
        await coord.async_update_chore(outsider)
        assert coord.storage.get_chore(chores[1].id).mandatory is True

    run(go())


def test_name_and_chores_are_required():
    async def go():
        coord = await _system()
        _child, chores = await _family(coord, 1)
        with pytest.raises(TaskMateError) as err:
            await coord.async_create_choice_set(name="  ", chore_ids=[chores[0].id])
        assert err.value.translation_key == "choice_set_name_required"
        with pytest.raises(TaskMateError) as err:
            await coord.async_create_choice_set(name="Set", chore_ids=[])
        assert err.value.translation_key == "choice_set_needs_chore"
        with pytest.raises(TaskMateError) as err:
            await coord.async_update_choice_set("nope", name="x")
        assert err.value.translation_key == "choice_set_not_found"

    run(go())


def test_deleting_a_chore_drops_it_from_its_set():
    async def go():
        coord = await _system()
        _child, chores = await _family(coord, 2)
        set_id = await coord.async_create_choice_set(name="Set", chore_ids=[c.id for c in chores])
        coord.storage.remove_chore(chores[0].id)
        assert coord.storage.get_choice_set(set_id).chore_ids == [chores[1].id]

    run(go())


# ── progress ─────────────────────────────────────────────────────────────


def test_pending_completions_count_and_rejection_frees_the_slot():
    async def go():
        coord = await _system()
        child, chores = await _family(coord, 3, requires_approval=True)
        set_id = await coord.async_create_choice_set(name="Set", chore_ids=[c.id for c in chores], min_required=2)
        first = await coord.async_complete_chore(chores[0].id, child.id)
        assert not first.approved
        assert _status(coord, set_id, child.id) == {"min": 2, "done": 1, "fulfilled": False}
        await coord.async_complete_chore(chores[1].id, child.id)
        assert _status(coord, set_id, child.id)["fulfilled"] is True
        await coord.async_reject_chore(first.id)
        assert _status(coord, set_id, child.id) == {"min": 2, "done": 1, "fulfilled": False}

    run(go())


def test_a_chore_done_twice_counts_once():
    async def go():
        coord = await _system()
        child, chores = await _family(coord, 3, daily_limit=3)
        set_id = await coord.async_create_choice_set(name="Set", chore_ids=[c.id for c in chores], min_required=2)
        await coord.async_complete_chore(chores[0].id, child.id)
        await coord.async_complete_chore(chores[0].id, child.id)
        assert _status(coord, set_id, child.id)["done"] == 1
        assert _status(coord, set_id, child.id)["fulfilled"] is False

    run(go())


def test_effective_minimum_is_capped_by_the_chores_on_offer():
    async def go():
        coord = await _system()
        child, chores = await _family(coord, 3)
        other = await coord.async_add_child("Vaiha")
        # Two of the three are someone else's, so only one is on offer.
        for chore in chores[1:]:
            c = coord.storage.get_chore(chore.id)
            c.assigned_to = [other.id]
            coord.storage.update_chore(c)
        set_id = await coord.async_create_choice_set(name="Set", chore_ids=[c.id for c in chores], min_required=3)
        assert _status(coord, set_id, child.id) == {"min": 1, "done": 0, "fulfilled": False}
        # None on offer: nothing owed.
        c = coord.storage.get_chore(chores[0].id)
        c.enabled = False
        coord.storage.update_chore(c)
        assert _status(coord, set_id, child.id) == {"min": 0, "done": 0, "fulfilled": True}

    run(go())


def test_sensor_progress_is_compact_and_only_for_assigned_children():
    async def go():
        coord = await _system()
        child, chores = await _family(coord, 2)
        other = await coord.async_add_child("Vaiha")
        adult = await coord.async_add_child("Mum", is_adult=True)
        await coord.async_create_choice_set(name="Set", chore_ids=[c.id for c in chores], min_required=1)
        await coord.async_complete_chore(chores[0].id, child.id)
        (row,) = coord.choice_set_progress_for_child(child.id)
        assert set(row) == {"set_id", "name", "icon", "min", "done", "fulfilled", "chore_ids"}
        assert row["done"] == 1 and row["fulfilled"] is True
        assert coord.choice_set_progress_for_child(other.id)[0]["done"] == 0
        # Empty assigned_to means every child, never the grown-ups (#1061).
        assert coord.choice_set_progress_for_child(adult.id) == []

    run(go())


def test_fulfilled_event_fires_once_when_the_set_is_met():
    async def go():
        coord = await _system()
        child, chores = await _family(coord, 3, daily_limit=2)
        await coord.async_create_choice_set(name="Set", chore_ids=[c.id for c in chores], min_required=2)
        await coord.async_complete_chore(chores[0].id, child.id)
        assert _events(coord, "taskmate_choice_set_fulfilled") == []
        await coord.async_complete_chore(chores[1].id, child.id)
        await coord.async_complete_chore(chores[1].id, child.id)  # a second go: no repeat
        await coord.async_complete_chore(chores[2].id, child.id)  # beyond the minimum: no repeat
        (event,) = _events(coord, "taskmate_choice_set_fulfilled")
        assert event["child_id"] == child.id and event["done"] == 2 and event["min"] == 2

    run(go())


# ── end of day ───────────────────────────────────────────────────────────


async def _missed_yesterday(coord, *, min_required=2, penalty=5, done=1):
    child, chores = await _family(coord, 3)
    set_id = await coord.async_create_choice_set(
        name="Your part", chore_ids=[c.id for c in chores], min_required=min_required, penalty_points=penalty
    )
    for chore in chores[:done]:
        await coord.async_complete_chore(chore.id, child.id)
    # Midnight has passed.
    dt_util_mock._now = NOW + dt.timedelta(days=1)
    return child, chores, set_id


def test_one_miss_per_set_and_no_automatic_deduction():
    async def go():
        coord = await _system()
        child, _chores, set_id = await _missed_yesterday(coord)
        points_before = coord.storage.get_child(child.id).points
        assert await coord.async_detect_choice_set_misses(TODAY) == 1
        assert await coord.async_detect_choice_set_misses(TODAY) == 0  # idempotent
        (miss,) = coord.storage.get_mandatory_misses()
        assert miss.set_id == set_id and miss.chore_id == "" and miss.penalty_points == 5
        assert coord.storage.get_child(child.id).points == points_before
        (event,) = _events(coord, "taskmate_choice_set_missed")
        assert event["done"] == 1 and event["min"] == 2
        (state,) = coord.mandatory_misses_state()
        assert state["chore_name"] == "Your part" and state["set_done"] == 1 and state["set_min"] == 2
        # The midnight sweep owns it too.
        coord.async_detect_mandatory_misses = AsyncMock(return_value=0)
        coord.async_detect_set_time_misses = AsyncMock(return_value=0)
        await coord.async_detect_anytime_mandatory_misses()
        assert len(coord.storage.get_mandatory_misses()) == 1

    run(go())


def test_a_met_or_optional_set_is_never_missed():
    async def go():
        coord = await _system()
        await _missed_yesterday(coord, min_required=2, done=2)
        assert await coord.async_detect_choice_set_misses(TODAY) == 0

        coord = await _system()
        await _missed_yesterday(coord, min_required=0, done=0)
        assert await coord.async_detect_choice_set_misses(TODAY) == 0

    run(go())


def test_apply_penalty_deducts_only_on_the_parents_say():
    async def go():
        coord = await _system()
        child, _chores, _set_id = await _missed_yesterday(coord, penalty=4)
        await coord.async_detect_choice_set_misses(TODAY)
        (miss,) = coord.storage.get_mandatory_misses()
        before = coord.storage.get_child(child.id).points
        await coord.async_apply_mandatory_penalty(miss.id)
        assert coord.storage.get_child(child.id).points == before - 4
        assert coord.storage.get_mandatory_misses() == []
        tx = coord.storage.get_points_transactions()[-1]
        assert tx.reason_key == "penalty_missed_choice_set"
        # Handled: never raised again for that day.
        assert await coord.async_detect_choice_set_misses(TODAY) == 0

    run(go())


@pytest.mark.parametrize("action", ["async_postpone_mandatory_chore", "async_dismiss_mandatory_chore"])
def test_postpone_and_dismiss_clear_it_for_good(action):
    async def go():
        coord = await _system()
        await _missed_yesterday(coord)
        await coord.async_detect_choice_set_misses(TODAY)
        (miss,) = coord.storage.get_mandatory_misses()
        await getattr(coord, action)(miss.id)
        assert coord.storage.get_mandatory_misses() == []
        assert await coord.async_detect_choice_set_misses(TODAY) == 0

    run(go())


def test_rejection_after_the_day_ended_raises_the_miss():
    async def go():
        coord = await _system()
        child, chores = await _family(coord, 3, requires_approval=True)
        await coord.async_create_choice_set(name="Set", chore_ids=[c.id for c in chores], min_required=1)
        completion = await coord.async_complete_chore(chores[0].id, child.id)
        dt_util_mock._now = NOW + dt.timedelta(days=1)
        assert await coord.async_detect_choice_set_misses(TODAY) == 0  # pending counted
        await coord.async_reject_chore(completion.id)
        assert len([m for m in coord.storage.get_mandatory_misses() if m.set_id]) == 1

    run(go())


def test_removing_a_set_removes_its_open_misses():
    async def go():
        coord = await _system()
        _child, _chores, set_id = await _missed_yesterday(coord)
        await coord.async_detect_choice_set_misses(TODAY)
        await coord.async_remove_choice_set(set_id)
        assert coord.storage.get_mandatory_misses() == []

    run(go())


def test_set_misses_survive_the_mandatory_orphan_prune():
    async def go():
        coord = await _system()
        await _missed_yesterday(coord)
        await coord.async_detect_choice_set_misses(TODAY)
        await coord.async_prune_orphan_misses()
        assert len(coord.storage.get_mandatory_misses()) == 1

    run(go())


# ── streaks / perfect week ───────────────────────────────────────────────


def test_streak_treats_the_set_as_one_due_item():
    async def go():
        coord = await _system()
        child, chores = await _family(coord, 3)
        await coord.async_create_choice_set(name="Set", chore_ids=[c.id for c in chores], min_required=2)
        assert coord._all_due_chores_done(child.id, TODAY, include_rotation=True) is False
        await coord.async_complete_chore(chores[0].id, child.id)
        assert coord._all_due_chores_done(child.id, TODAY, include_rotation=True) is False
        await coord.async_complete_chore(chores[1].id, child.id)
        # The third member is never due on its own.
        assert coord._all_due_chores_done(child.id, TODAY, include_rotation=True) is True

    run(go())


# ── where misses are reviewed ────────────────────────────────────────────


def test_miss_review_location_default_and_sensor_flag():
    async def go():
        coord = await _system()
        assert coord.miss_review_location() == "card"
        sensor = sensor_module.PendingApprovalsSensor.__new__(sensor_module.PendingApprovalsSensor)
        sensor.coordinator = coord
        coord.data = coord._build_data_snapshot()
        assert "miss_review_location" not in sensor.extra_state_attributes
        coord.storage.set_setting("miss_review_location", "panel")
        assert coord.miss_review_location() == "panel"
        assert sensor.extra_state_attributes["miss_review_location"] == "panel"
        coord.storage.set_setting("miss_review_location", "bogus")
        assert coord.miss_review_location() == "card"

    run(go())


def test_settings_schema_accepts_only_the_three_locations():
    from custom_components.taskmate.websocket import _SUBKEY_SETTINGS, _UPDATE_SETTINGS_SCHEMA, WS_UPDATE_SETTINGS

    schema = vol.Schema(_UPDATE_SETTINGS_SCHEMA, extra=vol.ALLOW_EXTRA)
    for where in ("card", "panel", "both"):
        schema({"type": WS_UPDATE_SETTINGS, "id": 1, "miss_review_location": where})
    with pytest.raises(vol.Invalid):
        schema({"type": WS_UPDATE_SETTINGS, "id": 1, "miss_review_location": "kiosk"})
    assert "miss_review_location" in _SUBKEY_SETTINGS


def test_approvals_card_and_panel_follow_the_setting():
    card = (PKG / "www" / "taskmate-approvals-card.js").read_text()
    assert "miss_review_location === 'panel'" in card
    panel = (PKG / "www" / "taskmate-panel.js").read_text()
    assert 'where === "panel" || where === "both"' in panel
    assert "this._approvalQueue({ wishes: true, misses: true })" in panel


# ── overview size and plumbing ───────────────────────────────────────────


def test_overview_slice_stays_under_the_cap_with_sets():
    from .test_sensor_attributes import _assert_slice_under_limit, _stress_coordinator

    coord = _stress_coordinator()
    common = sensor_module._compute_common(coord)
    ids = [ch.id for ch in common["chores"]]
    sets = [
        {
            "set_id": f"{i:016x}",
            "name": f"Your part for the family {i}",
            "icon": "mdi:hand-heart-outline",
            "min": 2,
            "done": 1,
            "fulfilled": False,
            "chore_ids": ids[i * 10 : i * 10 + 10],
        }
        for i in range(3)
    ]
    coord.choice_set_progress_for_child = MagicMock(return_value=sets)
    children = sensor_module._build_children_summary(coord, common)
    assert children[0]["choice_sets"] == sets
    _assert_slice_under_limit("taskmate_overview", {"children": children})


def test_services_are_described_and_translated():
    services = yaml.safe_load((PKG / "services.yaml").read_text())
    strings = json.loads((PKG / "strings.json").read_text())["services"]
    for name in CHOICE_SET_SERVICES:
        assert name in services and name in strings
        assert set(services[name]["fields"]) == set(strings[name]["fields"])
    init = (PKG / "__init__.py").read_text()
    assert "CHOICE_SET_SERVICES" in init and "async_register_choice_set_services" in init
