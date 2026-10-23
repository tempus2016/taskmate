"""Screen-time daily allowance (school day vs weekend) and the weekend jar."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from .test_completion_eligibility import _make_system, run

ST = "custom_components.taskmate.coord_screen_time.dt_util"


def _at(day=21, hour=12, minute=0):
    # 2026-10-21 is a Wednesday; the 24th a Saturday.
    return dt.datetime(2026, 10, day, hour, minute, tzinfo=dt.UTC)


def _system(school=30, weekend=90, unused="expire", jar=False, cap=120):
    coord, storage, mod = _make_system()
    coord.notifications = AsyncMock()
    coord.hass.bus = MagicMock()
    coord.hass.services = MagicMock()
    coord.hass.services.async_call = AsyncMock()
    coord.async_refresh = AsyncMock()
    states: dict[str, str] = {}
    coord.hass.states = MagicMock()
    coord.hass.states.get = lambda eid: SimpleNamespace(state=states[eid]) if eid in states else None
    storage.set_setting("screen_time_enabled", True)
    storage.set_setting("screen_time_allowance_school", school)
    storage.set_setting("screen_time_allowance_weekend", weekend)
    storage.set_setting("screen_time_allowance_unused", unused)
    storage.set_setting("screen_time_jar_enabled", jar)
    storage.set_setting("screen_time_jar_cap", cap)
    with patch.object(mod.dt_util, "now", return_value=_at()):
        kid = run(coord.async_add_child("Vaiha"))
        adult = run(coord.async_add_child("Dad"))
    adult.is_adult = True
    storage.update_child(adult)
    storage.set_setting("screen_time_devices", {kid.id: ["switch.tv"]})
    return coord, storage, kid, adult, states


def _tick(coord, when, n=1):
    with patch(f"{ST}.now", return_value=when):
        for _ in range(n):
            run(coord.async_check_screen_time())


def _fired(coord, name):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == name]


def _record(storage, kid):
    return storage.get_section("screen_time", dict)[kid.id]


class TestAllowance:
    def test_school_day_and_weekend_amounts(self):
        coord, _storage, kid, adult, _states = _system()
        _tick(coord, _at(day=21))
        assert coord.screen_time_balance(kid.id) == 30
        assert coord.screen_time_balance(adult.id) == 0, "adults get no allowance"
        _tick(coord, _at(day=24))
        assert coord.screen_time_balance(kid.id) == 90

    def test_granted_once_a_day(self):
        coord, _storage, kid, _adult, _states = _system()
        _tick(coord, _at(hour=0, minute=1))
        _tick(coord, _at(hour=8))
        _tick(coord, _at(hour=20))
        assert coord.screen_time_balance(kid.id) == 30

    def test_a_vacation_period_counts_as_a_holiday(self):
        coord, storage, kid, _adult, _states = _system()
        storage.set_setting(
            "vacation_periods", [{"id": "h", "name": "Half term", "start": "2026-10-19", "end": "2026-10-23"}]
        )
        _tick(coord, _at(day=21))
        assert coord.screen_time_balance(kid.id) == 90

    def test_the_vacation_calendar_counts_today(self):
        coord, storage, kid, _adult, _states = _system()
        storage.set_setting("vacation_calendar", "calendar.holidays")
        coord._read_entity_active = lambda eid: eid == "calendar.holidays"
        with patch(f"{ST}.now", return_value=_at(day=21)):
            assert coord.screen_time_is_holiday(dt.date(2026, 10, 21)) is True
            # The live calendar says nothing about another day.
            assert coord.screen_time_is_holiday(dt.date(2026, 10, 22)) is False

    def test_unused_allowance_expires_by_default(self):
        coord, storage, kid, _adult, _states = _system()
        _tick(coord, _at(day=21))
        _tick(coord, _at(day=22))
        assert coord.screen_time_balance(kid.id) == 30
        assert _record(storage, kid)["minutes"] == 0

    def test_unused_allowance_can_carry_over(self):
        coord, storage, kid, _adult, _states = _system(unused="carry")
        _tick(coord, _at(day=21))
        _tick(coord, _at(day=22))
        assert coord.screen_time_balance(kid.id) == 60
        assert coord.screen_time_allowance_left(kid.id) == 30
        assert _record(storage, kid)["minutes"] == 30

    def test_bought_minutes_always_carry_and_allowance_is_spent_first(self):
        coord, storage, kid, _adult, states = _system()
        with patch(f"{ST}.now", return_value=_at()):
            run(coord.async_adjust_screen_time(kid.id, 20))
        _tick(coord, _at(day=21, hour=1))
        states["switch.tv"] = "on"
        _tick(coord, _at(day=21, hour=18), n=10)
        assert coord.screen_time_allowance_left(kid.id) == 20
        assert _record(storage, kid)["minutes"] == 20
        states["switch.tv"] = "off"
        _tick(coord, _at(day=22))
        assert coord.screen_time_balance(kid.id) == 50, "yesterday's 20 allowance expired; 20 bought stayed"

    def test_old_single_balance_reads_as_bought(self):
        coord, storage, kid, _adult, _states = _system(school=0, weekend=0)
        storage.get_section("screen_time", dict)[kid.id] = {"minutes": 45, "warned": False, "out": False, "log": []}
        _tick(coord, _at(day=21))
        _tick(coord, _at(day=22))
        assert coord.screen_time_balance(kid.id) == 45

    def test_summary_shows_the_allowance_only_when_there_is_one(self):
        coord, _storage, kid, _adult, _states = _system()
        assert "allowance" not in coord.screen_time_summary(kid.id)
        _tick(coord, _at())
        summary = coord.screen_time_summary(kid.id)
        assert summary["minutes"] == 30 and summary["allowance"] == 30
        assert "jar" not in summary


class TestJar:
    def test_save_moves_allowance_first_up_to_the_cap(self):
        coord, storage, kid, _adult, _states = _system(jar=True, cap=50)
        with patch(f"{ST}.now", return_value=_at()):
            run(coord.async_adjust_screen_time(kid.id, 40))
        _tick(coord, _at(hour=1))
        with patch(f"{ST}.now", return_value=_at(hour=19)):
            result = run(coord.async_save_screen_time(kid.id, 35))
        assert result == {"saved": 35, "jar": 35, "minutes": 35}
        assert coord.screen_time_allowance_left(kid.id) == 0
        assert _record(storage, kid)["minutes"] == 35
        with patch(f"{ST}.now", return_value=_at(hour=19)):
            assert run(coord.async_save_screen_time(kid.id))["saved"] == 15, "only what fits under the cap"
            with pytest.raises(ValueError, match="full"):
                run(coord.async_save_screen_time(kid.id))
        (evt, _second) = _fired(coord, "taskmate_screen_time_saved")
        assert evt["minutes"] == 35 and evt["jar"] == 35

    def test_save_refuses_when_switched_off_or_nothing_to_save(self):
        coord, storage, kid, _adult, _states = _system(jar=False)
        with patch(f"{ST}.now", return_value=_at()), pytest.raises(ValueError, match="switched off"):
            run(coord.async_save_screen_time(kid.id))
        storage.set_setting("screen_time_jar_enabled", True)
        with patch(f"{ST}.now", return_value=_at()), pytest.raises(ValueError, match="No minutes"):
            run(coord.async_save_screen_time(kid.id))

    def test_jar_opens_at_saturday_eight_and_not_before(self):
        coord, storage, kid, _adult, _states = _system(school=0, weekend=0, jar=True)
        with patch(f"{ST}.now", return_value=_at(day=21)):
            run(coord.async_adjust_screen_time(kid.id, 30))
            run(coord.async_save_screen_time(kid.id))
        _tick(coord, _at(day=24, hour=7, minute=59))
        assert coord.screen_time_jar(kid.id) == 30 and coord.screen_time_balance(kid.id) == 0
        _tick(coord, _at(day=24, hour=8))
        assert coord.screen_time_jar(kid.id) == 0 and coord.screen_time_balance(kid.id) == 30
        (evt,) = _fired(coord, "taskmate_screen_time_jar_opened")
        assert evt["minutes"] == 30
        types = [c.args[0] for c in coord.notifications.fire.call_args_list]
        assert types == ["screen_time_jar_opened"]

    def test_minutes_saved_after_opening_wait_a_week(self):
        coord, _storage, kid, _adult, _states = _system(school=0, weekend=0, jar=True)
        with patch(f"{ST}.now", return_value=_at(day=24, hour=10)):
            run(coord.async_adjust_screen_time(kid.id, 20))
            run(coord.async_save_screen_time(kid.id))
        _tick(coord, _at(day=24, hour=11))
        _tick(coord, _at(day=30, hour=12))
        assert coord.screen_time_jar(kid.id) == 20
        _tick(coord, _at(day=31, hour=8))
        assert coord.screen_time_jar(kid.id) == 0 and coord.screen_time_balance(kid.id) == 20

    def test_a_missed_opening_still_opens_later(self):
        coord, _storage, kid, _adult, _states = _system(school=0, weekend=0, jar=True)
        with patch(f"{ST}.now", return_value=_at(day=21)):
            run(coord.async_adjust_screen_time(kid.id, 10))
            run(coord.async_save_screen_time(kid.id))
        _tick(coord, _at(day=26, hour=9))
        assert coord.screen_time_balance(kid.id) == 10

    def test_custom_opening_day_and_time(self):
        coord, storage, kid, _adult, _states = _system(school=0, weekend=0, jar=True)
        storage.set_setting("screen_time_jar_open_day", 4)
        storage.set_setting("screen_time_jar_open_time", "17:30")
        with patch(f"{ST}.now", return_value=_at(day=21)):
            run(coord.async_adjust_screen_time(kid.id, 10))
            run(coord.async_save_screen_time(kid.id))
        _tick(coord, _at(day=23, hour=17, minute=29))
        assert coord.screen_time_jar(kid.id) == 10
        _tick(coord, _at(day=23, hour=17, minute=30))
        assert coord.screen_time_jar(kid.id) == 0

    def test_parent_opens_the_jar_early(self):
        coord, _storage, kid, _adult, _states = _system(school=0, weekend=0, jar=True)
        with patch(f"{ST}.now", return_value=_at(day=21)):
            run(coord.async_adjust_screen_time(kid.id, 25))
            run(coord.async_save_screen_time(kid.id, 25))
            assert run(coord.async_open_screen_time_jar(kid.id)) == 25
            assert run(coord.async_open_screen_time_jar(kid.id)) == 0
        assert coord.screen_time_balance(kid.id) == 25

    def test_summary_carries_the_jar_for_the_card(self):
        coord, _storage, kid, _adult, _states = _system(jar=True, cap=90)
        assert coord.screen_time_summary(kid.id)["jar"] == {"minutes": 0, "cap": 90, "day": 5, "at": "08:00"}
        state = coord.screen_time_state()[kid.id]
        assert state["jar"] == 0 and state["allowance"] == 0


class TestServicesAndSettings:
    def test_save_service_is_child_gated(self):
        from custom_components.taskmate import family_services

        registered = {}
        hass = MagicMock()
        hass.services.async_register = lambda domain, name, handler, schema: registered.setdefault(name, handler)
        gate = AsyncMock()
        coord = MagicMock()
        coord.async_save_screen_time = AsyncMock()
        family_services.async_register_family_services(
            hass,
            child_action=lambda h: h,
            parent_action=lambda h: h,
            get_coordinator=lambda: coord,
            require_linked_child=gate,
        )
        call = SimpleNamespace(data={"child_id": "kid", "minutes": 15})
        run(registered["save_screen_time"](call))
        assert gate.await_args.args[3] == "kid"
        coord.async_save_screen_time.assert_awaited_once_with("kid", 15)

    def test_settings_schema_accepts_the_new_keys(self):
        from custom_components.taskmate.websocket import _UPDATE_SETTINGS_SCHEMA, WS_UPDATE_SETTINGS

        base = {"type": WS_UPDATE_SETTINGS, "id": 1}
        schema = vol.Schema(_UPDATE_SETTINGS_SCHEMA, extra=vol.ALLOW_EXTRA)
        ok = schema(
            {
                **base,
                "screen_time_allowance_school": 30,
                "screen_time_allowance_weekend": 90,
                "screen_time_allowance_unused": "carry",
                "screen_time_jar_enabled": True,
                "screen_time_jar_cap": 120,
                "screen_time_jar_open_day": "5",
                "screen_time_jar_open_time": "08:00",
            }
        )
        assert ok["screen_time_jar_open_day"] == 5
        with pytest.raises(vol.Invalid):
            schema({**base, "screen_time_allowance_unused": "bank"})
        with pytest.raises(vol.Invalid):
            schema({**base, "screen_time_jar_open_day": 7})
