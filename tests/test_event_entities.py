"""Event entities: the taskmate_* bus events, pickable in the UI automation editor."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

from custom_components.taskmate.models import Child

from .conftest import run_async


class _EventEntity:
    """Just enough of HA's EventEntity for the platform."""

    hass = None
    event_types: list[str] = []

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        if "_attr_event_types" in cls.__dict__:
            cls.event_types = cls._attr_event_types

    def _trigger_event(self, event_type, attributes=None):
        self.fired = (event_type, attributes)

    def async_write_ha_state(self):
        self.written = True


_event_mod = MagicMock()
_event_mod.EventEntity = _EventEntity
sys.modules["homeassistant.components.event"] = _event_mod

from custom_components.taskmate import event as tm_event  # noqa: E402


class _Bus:
    def __init__(self):
        self.listeners = {}

    def async_listen(self, name, cb):
        self.listeners.setdefault(name, []).append(cb)
        return lambda: None

    def fire(self, name, data):
        for cb in self.listeners.get(name, []):
            cb(MagicMock(data=data))


def _setup(children):
    hass = MagicMock()
    hass.bus = _Bus()
    coord = MagicMock()
    coord.data = {"children": children}
    listeners = []
    coord.async_add_listener = lambda cb: listeners.append(cb) or (lambda: None)
    hass.data = {"taskmate": {"e1": coord}}
    entry = MagicMock(entry_id="e1")
    added = []
    run_async(tm_event.async_setup_entry(hass, entry, lambda ents: added.extend(ents)))
    for ent in added:
        ent.hass = hass
    return hass, coord, listeners, added


def test_one_entity_per_child_plus_family():
    _hass, _coord, _l, added = _setup([Child(name="Malia", id="k1"), Child(name="Vaiha", id="k2")])
    assert len(added) == 3
    ids = {e._attr_unique_id for e in added}
    assert ids == {"e1_family_activity_event", "e1_k1_activity_event", "e1_k2_activity_event"}


def test_bus_event_triggers_the_right_child_only():
    hass, _c, _l, added = _setup([Child(name="Malia", id="k1"), Child(name="Vaiha", id="k2")])
    hass.bus.fire("taskmate_chore_approved", {"child_id": "k2", "chore_name": "Bins", "points": 5, "timestamp": "t"})
    by_id = {getattr(e, "child_id", "family"): e for e in added}
    assert by_id["k2"].fired == ("chore_approved", {"child_id": "k2", "chore_name": "Bins", "points": 5})
    assert not hasattr(by_id["k1"], "fired")


def test_gift_reaches_both_children_and_team_reaches_everyone():
    hass, _c, _l, added = _setup([Child(name="A", id="k1"), Child(name="B", id="k2")])
    hass.bus.fire("taskmate_points_gifted", {"from_child_id": "k1", "to_child_id": "k2", "points": 3})
    by_id = {getattr(e, "child_id", "family"): e for e in added}
    assert by_id["k1"].fired[0] == by_id["k2"].fired[0] == "points_gifted"
    hass.bus.fire("taskmate_team_chore_completed", {"child_ids": ["k1", "k2"], "chore_name": "Car"})
    assert by_id["k1"].fired[0] == by_id["k2"].fired[0] == "team_chore_completed"


def test_family_event_and_nested_payload_dropped():
    hass, _c, _l, added = _setup([Child(name="A", id="k1")])
    hass.bus.fire("taskmate_family_goal_reached", {"goal_name": "Film", "nested": {"x": 1}})
    family = next(e for e in added if not hasattr(e, "child_id"))
    assert family.fired == ("family_goal_reached", {"goal_name": "Film"})


def test_new_child_gets_an_entity_on_refresh():
    _hass, coord, listeners, added = _setup([Child(name="A", id="k1")])
    coord.data["children"].append(Child(name="New", id="k9"))
    for cb in listeners:
        cb()
    assert any(getattr(e, "child_id", "") == "k9" for e in added)


def test_every_event_type_has_a_translation():
    import json
    from pathlib import Path

    en = json.loads((Path(tm_event.__file__).parent / "translations" / "en.json").read_text())
    child = en["entity"]["event"]["child_activity"]["state_attributes"]["event_type"]["state"]
    family = en["entity"]["event"]["family_activity"]["state_attributes"]["event_type"]["state"]
    assert set(child) == set(tm_event.CHILD_EVENTS)
    assert set(family) == set(tm_event.FAMILY_EVENTS)
