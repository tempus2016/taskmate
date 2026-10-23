"""Points expiry: dated lots, spent oldest first, expired on the tick."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from .test_completion_eligibility import _make_system, _now, run

EXP = "custom_components.taskmate.coord_points_expiry.dt_util.now"


def _system(days=90, warn=7, points=100):
    coord, storage, mod = _make_system()
    coord.notifications = AsyncMock()
    coord.hass.bus = MagicMock()
    coord.badges = None
    coord.external_state_version = 0
    coord.async_update_listeners = MagicMock()
    with patch.object(mod.dt_util, "now", return_value=_now()):
        kid = run(coord.async_add_child("Malia"))
    kid.points = points
    storage.update_child(kid)
    storage.set_setting("points_expiry_enabled", True)
    storage.set_setting("points_expiry_days", days)
    storage.set_setting("points_expiry_warn_days", warn)
    return coord, storage, kid


def _set_points(storage, kid, points):
    child = storage.get_child(kid.id)
    child.points = points
    storage.update_child(child)


def _tick(coord, when):
    with patch(EXP, return_value=when):
        return run(coord.async_check_points_expiry())


def _lots(storage, kid):
    return storage.get_section("points_expiry", dict)[kid.id]["lots"]


def _fired(coord, name):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == name]


def test_switching_on_starts_the_existing_balance_as_one_lot_dated_today():
    coord, storage, kid = _system()
    _tick(coord, _now())
    assert _lots(storage, kid) == [{"d": "2024-03-20", "n": 100}]


def test_earnings_add_lots_and_spending_takes_the_oldest_first():
    coord, storage, kid = _system()
    _tick(coord, _now())
    _set_points(storage, kid, 150)
    _tick(coord, _now(day=25))
    assert _lots(storage, kid) == [{"d": "2024-03-20", "n": 100}, {"d": "2024-03-25", "n": 50}]
    _set_points(storage, kid, 120)  # spent 30: from the oldest lot
    _tick(coord, _now(day=26))
    assert _lots(storage, kid) == [{"d": "2024-03-20", "n": 70}, {"d": "2024-03-25", "n": 50}]
    _set_points(storage, kid, 40)  # a big penalty eats the first lot and part of the second
    _tick(coord, _now(day=26))
    assert _lots(storage, kid) == [{"d": "2024-03-25", "n": 40}]


def test_old_lots_expire_with_a_transaction_and_an_event():
    coord, storage, kid = _system(days=10)
    _tick(coord, _now())
    _set_points(storage, kid, 130)
    _tick(coord, _now(day=25))
    expired = _tick(coord, _now(day=30))  # 2024-03-20 + 10 days
    assert expired == 100
    assert storage.get_child(kid.id).points == 30
    assert _lots(storage, kid) == [{"d": "2024-03-25", "n": 30}]
    (txn,) = [t for t in storage.get_points_transactions() if t.reason == "Points expired"]
    assert txn.points == -100
    (evt,) = _fired(coord, "taskmate_points_expired")
    assert evt["points"] == 100 and evt["child_id"] == kid.id
    assert _tick(coord, _now(day=30)) == 0


def test_the_warning_shows_inside_the_window_and_notifies_once():
    coord, storage, kid = _system(days=10, warn=3)
    _tick(coord, _now())
    with patch(EXP, return_value=_now(day=26)):
        assert coord.points_expiry_summary(kid.id) is None  # expires on the 30th, 4 days away
    _tick(coord, _now(day=27))
    with patch(EXP, return_value=_now(day=27)):
        assert coord.points_expiry_summary(kid.id) == {"points": 100, "date": "2024-03-30"}
    _tick(coord, _now(day=28))
    (evt,) = _fired(coord, "taskmate_points_expiring")
    assert evt["date"] == "2024-03-30" and evt["points"] == 100
    coord.notifications.fire.assert_awaited_once()
    args = coord.notifications.fire.await_args
    assert args.args[0] == "points_expiring" and args.kwargs["only_recipients"] == {f"child:{kid.id}"}
    assert args.args[1]["points"] == 100


def test_no_warning_when_warn_days_is_zero():
    coord, storage, kid = _system(days=10, warn=0)
    _tick(coord, _now())
    with patch(EXP, return_value=_now(day=29)):
        assert coord.points_expiry_summary(kid.id) is None


def test_switching_off_forgets_the_lots_and_never_expires():
    coord, storage, kid = _system(days=1)
    _tick(coord, _now())
    storage.set_setting("points_expiry_enabled", False)
    assert _tick(coord, _now(day=28)) == 0
    assert storage.get_section("points_expiry", dict) == {}
    assert storage.get_child(kid.id).points == 100
    # Back on: a fresh lot from that day, nothing old to expire.
    storage.set_setting("points_expiry_enabled", True)
    _tick(coord, _now(day=28))
    assert _lots(storage, kid) == [{"d": "2024-03-28", "n": 100}]


def test_negative_balance_holds_no_lots():
    coord, storage, kid = _system()
    _tick(coord, _now())
    _set_points(storage, kid, -20)
    _tick(coord, _now(day=21))
    assert _lots(storage, kid) == []


def test_expired_points_cannot_be_undone():
    from custom_components.taskmate.coord_points import PointsMixin

    assert "Points expired".startswith(PointsMixin._UNDO_DENY_PREFIXES)


def test_removing_a_child_forgets_their_lots():
    coord, storage, kid = _system()
    _tick(coord, _now())
    storage.remove_child_from_sections(kid.id)
    assert kid.id not in storage.get_section("points_expiry", dict)


def test_settings_are_range_checked():
    from custom_components.taskmate.websocket import _UPDATE_SETTINGS_SCHEMA

    schema = vol.Schema(_UPDATE_SETTINGS_SCHEMA)
    base = {"type": "taskmate/update_settings"}
    out = schema({**base, "points_expiry_days": "90", "points_expiry_warn_days": 7})
    assert out["points_expiry_days"] == 90 and out["points_expiry_warn_days"] == 7
    with pytest.raises(vol.Invalid):
        schema({**base, "points_expiry_days": 0})
    with pytest.raises(vol.Invalid):
        schema({**base, "points_expiry_warn_days": 61})


def test_the_overview_summary_carries_the_warning_only_when_due():
    from custom_components.taskmate import sensor as sensor_module

    coord, storage, kid = _system(days=10, warn=3)
    _tick(coord, _now())
    coord.data = coord._build_data_snapshot()
    with (
        patch(EXP, return_value=_now(day=28)),
        patch("custom_components.taskmate.coord_reward_extras.dt_util.now", return_value=_now(day=28)),
    ):
        row = sensor_module._build_children_summary(coord, sensor_module._compute_common(coord))[0]
    assert row["points_expiry"] == {"points": 100, "date": "2024-03-30"}
    storage.set_setting("points_expiry_enabled", False)
    coord._data_snapshot_cache = None
    coord.data = coord._build_data_snapshot()
    with patch(EXP, return_value=_now(day=28)):
        row = sensor_module._build_children_summary(coord, sensor_module._compute_common(coord))[0]
    assert "points_expiry" not in row


def test_lot_dates_are_local_days():
    coord, storage, kid = _system()
    late = dt.datetime(2024, 3, 20, 23, 30, tzinfo=dt.UTC)
    _tick(coord, late)
    assert _lots(storage, kid)[0]["d"] == "2024-03-20"
