"""External entity changes must invalidate the sensor attribute cache (#673).

The coordinator reuses a single data snapshot while ``storage.data_version`` is
unchanged (PERF-2), so ``id(coordinator.data)`` is stable across refreshes. Any
sensor that derives attributes from *live* entity state — chore visibility and
the weather gate — would otherwise serve attributes computed against the old
entity state until an unrelated TaskMate mutation happened to bump the version.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore
from custom_components.taskmate.sensor import _CachedAttrsSensor


def _coord(children=None, chores=None):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.storage = MagicMock()
    coord.storage.get_children = MagicMock(return_value=children or [])
    coord.storage.get_chores = MagicMock(return_value=chores or [])
    coord._tracked_availability_entities = set()
    coord._tracked_visibility_entities = set()
    coord.external_state_version = 0
    return coord


def _event(entity_id):
    event = MagicMock()
    event.data = {"entity_id": entity_id}
    return event


class TestTrackedEntities:
    def test_visibility_and_weather_entities_are_tracked(self):
        coord = _coord(
            chores=[
                Chore(name="Dishes", visibility_entity="binary_sensor.dishwasher"),
                Chore(name="Mow", weather_entity="weather.home"),
                Chore(name="Plain"),
            ]
        )
        coord._refresh_tracked_availability_entities()
        assert coord._tracked_visibility_entities == {
            "binary_sensor.dishwasher",
            "weather.home",
        }

    def test_child_availability_entities_stay_separate(self):
        coord = _coord(
            children=[Child(name="Kid", availability_entity="device_tracker.kid")],
            chores=[Chore(name="Mow", weather_entity="weather.home")],
        )
        coord._refresh_tracked_availability_entities()
        assert coord._tracked_availability_entities == {"device_tracker.kid"}
        assert coord._tracked_visibility_entities == {"weather.home"}


class TestVersionBumping:
    def test_weather_change_bumps_version(self):
        coord = _coord(chores=[Chore(name="Mow", weather_entity="weather.home")])
        coord._refresh_tracked_availability_entities()
        coord._availability_state_changed(_event("weather.home"))
        assert coord.external_state_version == 1

    def test_visibility_change_bumps_version(self):
        coord = _coord(chores=[Chore(name="Dishes", visibility_entity="binary_sensor.dw")])
        coord._refresh_tracked_availability_entities()
        coord._availability_state_changed(_event("binary_sensor.dw"))
        assert coord.external_state_version == 1

    def test_untracked_entity_is_ignored(self):
        coord = _coord(chores=[Chore(name="Mow", weather_entity="weather.home")])
        coord._refresh_tracked_availability_entities()
        coord._availability_state_changed(_event("light.kitchen"))
        assert coord.external_state_version == 0
        coord.hass.async_create_task.assert_not_called()

    def test_weather_change_does_not_trigger_reassignment(self):
        """A weather flip changes what's visible, not who a chore belongs to."""
        coord = _coord(chores=[Chore(name="Mow", weather_entity="weather.home")])
        coord._refresh_tracked_availability_entities()
        coord._availability_state_changed(_event("weather.home"))
        coord.hass.async_create_task.assert_not_called()

    def test_availability_change_still_triggers_reassignment(self):
        coord = _coord(children=[Child(name="Kid", availability_entity="device_tracker.kid")])
        coord._refresh_tracked_availability_entities()
        coord._async_reevaluate_availability = MagicMock()
        coord._availability_state_changed(_event("device_tracker.kid"))
        assert coord.external_state_version == 1
        coord.hass.async_create_task.assert_called_once()

    def test_event_without_entity_id_is_ignored(self):
        coord = _coord()
        event = MagicMock()
        event.data = {}
        coord._availability_state_changed(event)
        assert coord.external_state_version == 0


class _StubSensor(_CachedAttrsSensor):
    """Minimal subclass that records how often attributes were rebuilt."""

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._cached_attrs = None
        self._cached_key = None
        self.builds = 0

    def _build_attributes(self) -> dict:
        self.builds += 1
        return {"build": self.builds}


class TestAttrCacheInvalidation:
    def test_cache_is_reused_when_nothing_changed(self):
        coord = _coord()
        coord.data = {"snapshot": 1}
        sensor = _StubSensor(coord)
        assert sensor.extra_state_attributes == {"build": 1}
        assert sensor.extra_state_attributes == {"build": 1}
        assert sensor.builds == 1

    def test_external_state_change_rebuilds_attributes(self):
        """The regression: same snapshot object, but the world moved."""
        coord = _coord()
        coord.data = {"snapshot": 1}
        sensor = _StubSensor(coord)
        assert sensor.extra_state_attributes == {"build": 1}
        coord.external_state_version += 1
        assert sensor.extra_state_attributes == {"build": 2}
        assert sensor.builds == 2

    def test_new_snapshot_still_rebuilds(self):
        coord = _coord()
        coord.data = {"snapshot": 1}
        sensor = _StubSensor(coord)
        assert sensor.extra_state_attributes == {"build": 1}
        coord.data = {"snapshot": 2}
        assert sensor.extra_state_attributes == {"build": 2}
