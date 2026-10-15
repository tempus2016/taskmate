"""A child's colour (#1078).

The setup wizard asked for a colour per child but never saved it, and the
Children dialog had nowhere to set one, so the panel coloured children by
their place in the list. The colour is now stored on the child.
"""

from __future__ import annotations

import pytest
import voluptuous as vol

from custom_components.taskmate import websocket as ws
from custom_components.taskmate import websocket_setup
from custom_components.taskmate.models import Child

from .test_setup_wizard import ROOT, _ws_env, coord, run  # noqa: F401  (coord is a fixture)


class TestModel:
    def test_round_trips(self):
        assert Child.from_dict(Child(name="Isla", color="#3498db").to_dict()).color == "#3498db"

    def test_children_saved_before_it_have_none(self):
        assert Child.from_dict({"name": "Old"}).color == ""


class TestValidator:
    @pytest.mark.parametrize(("value", "expected"), [("", ""), ("#3498DB", "#3498db"), (" #1abc9c ", "#1abc9c")])
    def test_accepts_hex_or_empty(self, value, expected):
        assert ws.validate_child_color(value) == expected

    @pytest.mark.parametrize("value", ["#fff", "red", "#12345g", "3498db", "#3498db;background:url(x)", '#3498db"x'])
    def test_rejects_anything_else(self, value):
        # The panel puts it straight into a style attribute.
        with pytest.raises(vol.Invalid):
            ws.validate_child_color(value)

    def test_every_child_command_validates_it(self):
        src = (ROOT / "custom_components" / "taskmate" / "websocket.py").read_text(encoding="utf-8")
        assert src.count('vol.Optional("color", default=""): validate_child_color') == 1  # add_child
        assert src.count('vol.Optional("color"): validate_child_color') == 1  # update_child
        child = vol.Schema(websocket_setup._CHILD_SCHEMA)
        assert child({"ref": "n", "name": "Isla"})["color"] == ""
        with pytest.raises(vol.Invalid):
            child({"ref": "n", "name": "Isla", "color": "red"})


def test_wizard_saves_the_picked_colour(coord):  # noqa: F811
    run(
        coord.async_apply_setup_wizard(
            children=[
                {"ref": "new1", "name": "Malia", "color": "#ff6b9d"},
                {"ref": "new2", "name": "Vaiha"},
            ]
        )
    )
    kids = {c.name: c for c in coord.storage.get_children()}
    assert kids["Malia"].color == "#ff6b9d"
    assert kids["Vaiha"].color == ""


def test_add_child_saves_the_colour(coord):  # noqa: F811
    hass, conn = _ws_env(coord)
    run(ws._ws_add_child(hass, conn, {"id": 1, "type": "taskmate/add_child", "name": "Isla", "color": "#9b59b6"}))
    assert coord.storage.get_children()[0].color == "#9b59b6"


def test_update_child_changes_and_clears_the_colour(coord):  # noqa: F811
    coord.storage._data["children"] = [Child(name="Malia", id="k1", color="#ff6b9d").to_dict()]
    hass, conn = _ws_env(coord)
    run(
        ws._ws_update_child(
            hass, conn, {"id": 1, "type": "taskmate/update_child", "child_id": "k1", "color": "#2ecc71"}
        )
    )
    assert coord.storage.get_child("k1").color == "#2ecc71"
    run(ws._ws_update_child(hass, conn, {"id": 2, "type": "taskmate/update_child", "child_id": "k1", "name": "Malia"}))
    assert coord.storage.get_child("k1").color == "#2ecc71"  # left alone when not sent
    run(ws._ws_update_child(hass, conn, {"id": 3, "type": "taskmate/update_child", "child_id": "k1", "color": ""}))
    assert coord.storage.get_child("k1").color == ""


def test_panel_uses_the_stored_colour_and_the_wizard_sends_it():
    src = (ROOT / "custom_components" / "taskmate" / "www" / "taskmate-panel.js").read_text(encoding="utf-8")
    assert "child.color" in src and "this._childColorAuto(childId)" in src
    assert 'data-act="child-color"' in src
    assert 'avatar: k.icon, color: k.color || ""' in src
