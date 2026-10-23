"""Card looks: seasonal themes, a child's colour and their tick-off animation.

The overview sensor tells the cards which season to dress for (only while one
is on and in its window), each child's colour and, when it isn't confetti,
their tick-off animation. All three are conditional so they cost nothing on
the 16 KB recorder cap when unused.
"""

from __future__ import annotations

import datetime as dt
from datetime import date
from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from custom_components.taskmate import websocket as ws
from custom_components.taskmate.models import Child
from custom_components.taskmate.seasons import active_season
from custom_components.taskmate.sensor import TaskMateOverallStatsSensor

from .conftest import dt_util_mock
from .test_sensor_attributes import _stress_coordinator
from .test_setup_wizard import ROOT, _ws_env, coord, run  # noqa: F401  (coord is a fixture)

ALL_ON = {"seasonal_halloween": True, "seasonal_christmas": True, "seasonal_summer": True}


class TestActiveSeason:
    @pytest.mark.parametrize(
        ("day", "expected"),
        [
            (date(2026, 10, 23), ""),
            (date(2026, 10, 24), "halloween"),
            (date(2026, 10, 31), "halloween"),
            (date(2026, 11, 1), ""),
            (date(2026, 12, 1), "christmas"),
            (date(2026, 12, 26), "christmas"),
            (date(2026, 12, 27), ""),
            (date(2026, 6, 20), ""),
            (date(2026, 6, 21), "summer"),
            (date(2026, 8, 31), "summer"),
            (date(2026, 9, 1), ""),
        ],
    )
    def test_windows(self, day, expected):
        assert active_season(ALL_ON, day) == expected

    def test_off_by_default(self):
        assert active_season({}, date(2026, 10, 31)) == ""
        assert active_season({"seasonal_christmas": True}, date(2026, 10, 31)) == ""

    def test_string_true_counts(self):
        assert active_season({"seasonal_summer": "true"}, date(2026, 7, 1)) == "summer"


def _overview(settings=None, children=None, today=dt.datetime(2026, 10, 30, 9, 0, tzinfo=dt.UTC)):
    stress = _stress_coordinator()
    dt_util_mock._now = today
    if settings:
        stress.data["settings"] = {**stress.data.get("settings", {}), **settings}
    if children is not None:
        stress.data["children"] = children
    return TaskMateOverallStatsSensor(stress, MagicMock())._build_attributes()


def test_overview_names_the_season_only_while_on():
    assert "season" not in _overview()
    assert _overview({"seasonal_halloween": True})["season"] == "halloween"
    assert "season" not in _overview({"seasonal_christmas": True})


def test_summary_carries_colour_and_style_only_when_set():
    kids = [
        Child(name="Malia", id="k1", color="#e91e63", celebration_style="fireworks"),
        Child(name="Vaiha", id="k2"),
    ]
    by_id = {c["id"]: c for c in _overview(children=kids)["children"]}
    assert by_id["k1"]["color"] == "#e91e63"
    assert by_id["k1"]["celebration_style"] == "fireworks"
    assert "color" not in by_id["k2"]
    assert "celebration_style" not in by_id["k2"]


class TestCelebrationStyle:
    def test_model_round_trips_and_defaults(self):
        assert Child.from_dict(Child(name="A", celebration_style="stamp").to_dict()).celebration_style == "stamp"
        assert Child.from_dict({"name": "Old"}).celebration_style == "confetti"
        assert Child.from_dict({"name": "Odd", "celebration_style": "lasers"}).celebration_style == "confetti"

    def test_add_and_update_child(self, coord):  # noqa: F811
        hass, conn = _ws_env(coord)
        run(
            ws._ws_add_child(
                hass, conn, {"id": 1, "type": "taskmate/add_child", "name": "Isla", "celebration_style": "sticker"}
            )
        )
        kid = coord.storage.get_children()[0]
        assert kid.celebration_style == "sticker"
        run(
            ws._ws_update_child(
                hass,
                conn,
                {"id": 2, "type": "taskmate/update_child", "child_id": kid.id, "celebration_style": "stamp"},
            )
        )
        assert coord.storage.get_child(kid.id).celebration_style == "stamp"
        run(
            ws._ws_update_child(hass, conn, {"id": 3, "type": "taskmate/update_child", "child_id": kid.id, "name": "I"})
        )
        assert coord.storage.get_child(kid.id).celebration_style == "stamp"

    def test_both_child_commands_validate_it(self):
        src = (ROOT / "custom_components" / "taskmate" / "websocket.py").read_text(encoding="utf-8")
        assert src.count('vol.Optional("celebration_style", default="confetti"): vol.In(CELEBRATION_STYLES)') == 1
        assert src.count('vol.Optional("celebration_style"): vol.In(CELEBRATION_STYLES)') == 1


def test_seasonal_settings_are_accepted():
    schema = vol.Schema(ws._UPDATE_SETTINGS_SCHEMA, extra=vol.ALLOW_EXTRA)
    out = schema({"type": "taskmate/update_settings", **ALL_ON})
    assert all(out[k] is True for k in ALL_ON)
    assert set(ALL_ON) <= ws._SUBKEY_SETTINGS
    with pytest.raises(vol.Invalid):
        schema({"type": "taskmate/update_settings", "seasonal_summer": "yes"})
