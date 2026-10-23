"""Child-chosen reminder times: "remind me about homework at 17:30"."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taskmate import notify_strings
from custom_components.taskmate.coord_notifications import NOTIFICATION_TYPES_BY_ID

from .test_completion_eligibility import UTC, _make_system, run

WED = dt.datetime(2024, 3, 20, 12, 0, tzinfo=UTC)


def _at(hour, minute=0, day=20):
    return dt.datetime(2024, 3, day, hour, minute, tzinfo=UTC)


def _system(enabled=True):
    coord, storage, mod = _make_system()
    coord.notifications = AsyncMock()
    coord.notifications._has_outstanding_chores_today = lambda _cid: True
    coord.hass.bus = MagicMock()
    coord.badges = None
    with patch.object(mod.dt_util, "now", return_value=WED):
        kid = run(coord.async_add_child("Vaiha"))
        sib = run(coord.async_add_child("Malia"))
        chore = run(coord.async_add_chore("Homework", points=5, requires_approval=True))
    storage.set_setting("chore_reminders_enabled", enabled)
    storage.set_setting("chore_reminders_earliest", "15:00")
    storage.set_setting("chore_reminders_latest", "20:00")
    return coord, storage, mod, kid, sib, chore


def _set(coord, mod, kid, chore, time):
    with patch.object(mod.dt_util, "now", return_value=WED):
        run(coord.async_set_chore_reminder(kid.id, chore.id, time))


def _tick(coord, mod, when):
    with patch.object(mod.dt_util, "now", return_value=when):
        run(coord.async_check_chore_reminders())


class TestSetting:
    def test_set_and_clear(self):
        coord, _storage, mod, kid, _sib, chore = _system()
        _set(coord, mod, kid, chore, "17:30")
        assert coord.chore_reminders_for_child(kid.id) == {chore.id: "17:30"}
        _set(coord, mod, kid, chore, "")
        assert coord.chore_reminders_for_child(kid.id) == {}

    def test_must_be_inside_the_parents_bounds(self):
        coord, _storage, mod, kid, _sib, chore = _system()
        with pytest.raises(ValueError, match="between 15:00 and 20:00"):
            _set(coord, mod, kid, chore, "21:00")
        _set(coord, mod, kid, chore, "20:00")

    def test_refused_while_off_and_hidden_from_the_card(self):
        coord, storage, mod, kid, _sib, chore = _system()
        _set(coord, mod, kid, chore, "17:30")
        storage.set_setting("chore_reminders_enabled", False)
        assert coord.chore_reminders_for_child(kid.id) == {}
        assert coord.chore_reminder_settings() is None
        with pytest.raises(ValueError, match="off"):
            _set(coord, mod, kid, chore, "18:00")

    def test_only_for_the_childs_own_chores(self):
        coord, _storage, mod, kid, sib, chore = _system()
        chore.assigned_to = [sib.id]
        coord.storage.update_chore(chore)
        with pytest.raises(ValueError, match="isn't one of"):
            _set(coord, mod, kid, chore, "17:30")

    def test_bounds_fall_back_and_never_invert(self):
        coord, storage, *_ = _system()
        storage.set_setting("chore_reminders_earliest", "nonsense")
        storage.set_setting("chore_reminders_latest", "09:00")
        assert coord.chore_reminder_bounds() == ("09:00", "15:00")
        assert coord.chore_reminder_settings() == {"earliest": "09:00", "latest": "15:00"}


class TestTick:
    def test_sends_once_at_the_time_to_that_child_only(self):
        coord, _storage, mod, kid, _sib, chore = _system()
        _set(coord, mod, kid, chore, "17:30")
        _tick(coord, mod, _at(17, 29))
        coord.notifications.fire.assert_not_awaited()
        _tick(coord, mod, _at(17, 30))
        _tick(coord, mod, _at(17, 31))
        coord.notifications.fire.assert_awaited_once()
        args = coord.notifications.fire.await_args
        assert args.args[0] == "chore_self_reminder"
        assert args.args[1]["chore_name"] == "Homework" and args.args[1]["child_name"] == "Vaiha"
        assert args.kwargs["only_recipients"] == {f"child:{kid.id}"}

    def test_a_late_tick_still_sends(self):
        coord, _storage, mod, kid, _sib, chore = _system()
        _set(coord, mod, kid, chore, "17:30")
        _tick(coord, mod, _at(17, 33))
        coord.notifications.fire.assert_awaited_once()
        _tick(coord, mod, _at(17, 40))
        coord.notifications.fire.assert_awaited_once()

    def test_not_when_already_done_today(self):
        coord, _storage, mod, kid, _sib, chore = _system()
        _set(coord, mod, kid, chore, "17:30")
        with patch.object(mod.dt_util, "now", return_value=_at(16)):
            run(coord.async_complete_chore(chore.id, kid.id))
        _tick(coord, mod, _at(17, 30))
        coord.notifications.fire.assert_not_awaited()

    def test_not_on_a_day_the_chore_is_not_due(self):
        coord, storage, mod, kid, _sib, chore = _system()
        chore.due_days = ["monday"]
        storage.update_chore(chore)
        _set(coord, mod, kid, chore, "17:30")
        _tick(coord, mod, _at(17, 30))  # a Wednesday
        coord.notifications.fire.assert_not_awaited()

    def test_again_the_next_day(self):
        coord, _storage, mod, kid, _sib, chore = _system()
        _set(coord, mod, kid, chore, "17:30")
        _tick(coord, mod, _at(17, 30))
        _tick(coord, mod, _at(17, 30, day=21))
        assert coord.notifications.fire.await_count == 2

    def test_nothing_while_off(self):
        coord, storage, mod, kid, _sib, chore = _system()
        _set(coord, mod, kid, chore, "17:30")
        storage.set_setting("chore_reminders_enabled", False)
        _tick(coord, mod, _at(17, 30))
        coord.notifications.fire.assert_not_awaited()

    def test_runs_in_the_minutely_tick(self):
        import inspect

        from custom_components.taskmate.coordinator import TaskMateCoordinator

        assert "async_check_chore_reminders" in inspect.getsource(TaskMateCoordinator.async_run_minutely_checks)


def test_notification_type_is_child_only_and_opt_in():
    meta = NOTIFICATION_TYPES_BY_ID["chore_self_reminder"]
    assert meta.audience == "child" and meta.default_enabled is False
    assert "{chore_name}" in notify_strings.DEFAULTS["chore_self_reminder"]


def test_deleting_a_child_forgets_their_reminders():
    coord, storage, mod, kid, _sib, chore = _system()
    _set(coord, mod, kid, chore, "17:30")
    storage.remove_child_from_sections(kid.id)
    assert kid.id not in storage.get_section("chore_reminders", dict)


def test_service_is_child_gated():
    from custom_components.taskmate.family_services import async_register_family_services

    hass = MagicMock()
    registered = {}
    hass.services.async_register = lambda d, name, handler, schema=None: registered.setdefault(name, handler)
    coord = MagicMock()
    coord.async_set_chore_reminder = AsyncMock()
    gate = AsyncMock()
    async_register_family_services(
        hass,
        child_action=lambda h: h,
        parent_action=lambda h: h,
        get_coordinator=lambda: coord,
        require_linked_child=gate,
    )
    run(registered["set_chore_reminder"](MagicMock(data={"child_id": "k", "chore_id": "c", "time": "17:30"})))
    assert gate.await_args.args[3] == "k"
    coord.async_set_chore_reminder.assert_awaited_once_with("k", "c", "17:30")
