"""Warning before a penalty: a yellow card first, the points the next time."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.models import Penalty

from .test_completion_eligibility import UTC, _make_system, run

WED = dt.datetime(2024, 3, 20, 12, 0, tzinfo=UTC)


def _system(warn=True, reset="daily"):
    coord, storage, mod = _make_system()
    coord.hass.bus = MagicMock()
    coord.badges = None
    coord.notifications = AsyncMock()
    with patch.object(mod.dt_util, "now", return_value=WED):
        kid = run(coord.async_add_child("Vaiha"))
    kid.points = 50
    storage.update_child(kid)
    pen = Penalty(name="Shouting at the table", points=10, warn_first=warn, warning_reset=reset)
    storage.add_penalty(pen)
    return coord, storage, mod, kid, pen


def _apply(coord, mod, pen, kid, when=WED):
    with patch.object(mod.dt_util, "now", return_value=when):
        return run(coord.async_apply_penalty(pen.id, kid.id))


def _fired(coord, name):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == name]


def test_first_time_is_a_warning_then_it_deducts():
    coord, storage, mod, kid, pen = _system()
    assert _apply(coord, mod, pen, kid) is True
    assert storage.get_child(kid.id).points == 50
    (evt,) = _fired(coord, "taskmate_penalty_warning")
    assert evt["penalty_name"] == "Shouting at the table" and evt["points"] == 10 and evt["resets"] == "daily"
    assert not _fired(coord, "taskmate_penalty_applied")
    with patch.object(mod.dt_util, "now", return_value=WED):
        assert coord.penalty_warnings_for_child(kid.id) == [
            {"penalty_id": pen.id, "name": "Shouting at the table", "points": 10}
        ]
    assert _apply(coord, mod, pen, kid) is False
    assert storage.get_child(kid.id).points == 40
    assert len(_fired(coord, "taskmate_penalty_applied")) == 1
    with patch.object(mod.dt_util, "now", return_value=WED):
        assert coord.penalty_warnings_for_child(kid.id) == []
    # Still the same day: no second warning, it keeps deducting.
    assert _apply(coord, mod, pen, kid) is False
    assert storage.get_child(kid.id).points == 30


def test_daily_warning_resets_the_next_day():
    coord, storage, mod, kid, pen = _system()
    _apply(coord, mod, pen, kid)
    assert _apply(coord, mod, pen, kid, WED + dt.timedelta(days=1)) is True
    assert storage.get_child(kid.id).points == 50


def test_weekly_warning_lasts_the_week():
    coord, storage, mod, kid, pen = _system(reset="weekly")
    _apply(coord, mod, pen, kid)  # Wednesday
    assert _apply(coord, mod, pen, kid, WED + dt.timedelta(days=3)) is False  # Saturday
    assert storage.get_child(kid.id).points == 40
    assert _apply(coord, mod, pen, kid, WED + dt.timedelta(days=5)) is True  # next Monday


def test_without_warn_first_it_deducts_straight_away():
    coord, storage, mod, kid, pen = _system(warn=False)
    assert _apply(coord, mod, pen, kid) is False
    assert storage.get_child(kid.id).points == 40
    assert not _fired(coord, "taskmate_penalty_warning")


def test_fields_round_trip_and_reach_the_cards():
    pen = Penalty.from_dict(Penalty(name="x", points=3, warn_first=True, warning_reset="weekly").to_dict())
    assert pen.warn_first is True and pen.warning_reset == "weekly"
    assert Penalty.from_dict({"name": "old", "points": 1}).warn_first is False
    assert Penalty.from_dict({"name": "odd", "points": 1, "warning_reset": "hourly"}).warning_reset == "daily"
    rows = sensor_module._build_penalties_list({"data": {"penalties": [pen, Penalty(name="y", points=1)]}})
    assert rows[0]["warn_first"] is True and "warn_first" not in rows[1]


def test_card_strip_comes_from_the_child_summary():
    coord, _storage, mod, kid, pen = _system()
    _apply(coord, mod, pen, kid)
    with patch.object(mod.dt_util, "now", return_value=WED):
        coord.data = run(coord._async_update_data())
        common = sensor_module._compute_common(coord)
        (child,) = sensor_module._build_children_summary(coord, common)
    assert child["penalty_warnings"][0]["points"] == 10


def test_ws_apply_reports_a_warning():
    from custom_components.taskmate import websocket as ws

    coord = MagicMock()
    coord.async_apply_penalty = AsyncMock(return_value=True)
    connection = MagicMock()
    handler = ws._ws_apply_penalty
    inner = getattr(handler, "__wrapped__", handler)
    while hasattr(inner, "__wrapped__"):
        inner = inner.__wrapped__
    run(inner(MagicMock(), connection, {"id": 1, "penalty_id": "p", "child_id": "c"}, coord))
    assert connection.send_result.call_args.args[1]["warning"] is True
