"""A child's face can come from any entity's picture — normally their person.

`Child.picture_entity` stores only the entity id; the picture URL is read from
that entity on every update, so a photo changed in Settings › People needs
nothing re-saved here and a deleted entity cannot leave a broken image behind.

It is deliberately independent of `linked_user_id`: a young child commonly has
a person entity with a photo but no Home Assistant login of their own.

Every lookup fails safe to "" and the caller falls back to the MDI avatar.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import custom_components.taskmate.coord_avatars as coord_avatars
from custom_components.taskmate.coord_avatars import AvatarsMixin
from custom_components.taskmate.models import Child

from .test_coordinator_logic import _make_coord

MILLIE_PIC = "/api/image/serve/millie/512x512"
EVIE_PIC = "/api/image/serve/evie/512x512"


def _state(picture=None, user_id=None):
    state = MagicMock()
    attrs = {}
    if picture is not None:
        attrs["entity_picture"] = picture
    if user_id is not None:
        attrs["user_id"] = user_id
    state.attributes = attrs
    return state


def _hass(states):
    hass = MagicMock()
    hass.states.get = MagicMock(side_effect=lambda eid: states.get(eid))
    return hass


def _coord(children, states):
    coord = _make_coord(children=list(children))
    coord.hass = _hass(states)
    return coord


class TestResolution:
    def test_uses_the_chosen_entitys_picture(self):
        child = Child(name="Millie", id="millie", picture_entity="person.millie")
        coord = _coord([child], {"person.millie": _state(MILLIE_PIC, user_id="uid-millie")})
        assert coord.child_avatar_image(child) == MILLIE_PIC

    def test_works_for_a_person_with_no_ha_login(self):
        """Evie's person has a photo but no linked user — the case that the
        account-based lookup could never have served."""
        child = Child(name="Evie", id="evie", picture_entity="person.evie")
        coord = _coord([child], {"person.evie": _state(EVIE_PIC, user_id=None)})
        assert coord.child_avatar_image(child) == EVIE_PIC

    def test_does_not_need_a_linked_account(self):
        child = Child(name="Evie", id="evie", picture_entity="person.evie", linked_user_id="")
        coord = _coord([child], {"person.evie": _state(EVIE_PIC)})
        assert coord.child_avatar_image(child) == EVIE_PIC

    def test_nothing_chosen_means_no_picture(self):
        child = Child(name="Millie", id="millie")
        assert _coord([child], {"person.millie": _state(MILLIE_PIC)}).child_avatar_image(child) == ""

    def test_entity_that_no_longer_exists(self):
        child = Child(name="Millie", id="millie", picture_entity="person.gone")
        assert _coord([child], {}).child_avatar_image(child) == ""

    def test_entity_without_a_picture(self):
        child = Child(name="Millie", id="millie", picture_entity="person.millie")
        assert _coord([child], {"person.millie": _state(None)}).child_avatar_image(child) == ""

    def test_surrounding_whitespace_is_ignored(self):
        child = Child(name="Millie", id="millie", picture_entity="  person.millie ")
        assert _coord([child], {"person.millie": _state(MILLIE_PIC)}).child_avatar_image(child) == MILLIE_PIC


class TestStorage:
    def test_round_trips(self):
        child = Child(name="Evie", id="evie", picture_entity="person.evie")
        assert Child.from_dict(child.to_dict()).picture_entity == "person.evie"

    def test_children_saved_before_the_feature_have_none(self):
        old = Child(name="Evie", id="evie").to_dict()
        del old["picture_entity"]
        assert Child.from_dict(old).picture_entity == ""


class TestSensorExposure:
    """Cards read `avatar_image`; `avatar` stays the MDI icon so the avatar
    picker's 'which one is selected' comparison keeps working."""

    def _summary(self, child, states):
        from custom_components.taskmate import sensor as sensor_module

        from .test_sensor_attributes import _stress_coordinator

        coord = _stress_coordinator()
        coord.data["children"] = [child]
        coord.hass = _hass(states)
        # The shared fixture is a MagicMock, so bind the real resolver: this
        # test is about the sensor publishing what the mixin actually returns.
        coord.child_avatar_image = lambda c: AvatarsMixin.child_avatar_image(coord, c)
        common = sensor_module._compute_common(coord)
        return sensor_module._build_children_summary(coord, common)[0]

    def test_publishes_the_picture_alongside_the_icon(self):
        child = Child(name="Evie", id="evie", avatar="mdi:rocket-launch", picture_entity="person.evie")
        row = self._summary(child, {"person.evie": _state(EVIE_PIC)})
        assert row["avatar_image"] == EVIE_PIC
        assert row["avatar"] == "mdi:rocket-launch"

    def test_empty_when_none_chosen(self):
        child = Child(name="Evie", id="evie", avatar="mdi:rocket-launch")
        row = self._summary(child, {"person.evie": _state(EVIE_PIC)})
        assert row["avatar_image"] == ""
        assert row["avatar"] == "mdi:rocket-launch"


class TestPhotoChangesReachTheSensors:
    """A photo changed on the person entity must show without a TaskMate edit."""

    @staticmethod
    def _event(entity_id, old_picture, new_picture):
        def state(picture):
            return None if picture is None else _state(picture)

        event = MagicMock()
        event.data = {"entity_id": entity_id, "old_state": state(old_picture), "new_state": state(new_picture)}
        return event

    @staticmethod
    def _tracking_coord(entity="person.millie"):
        child = Child(name="Millie", id="millie", picture_entity=entity)
        coord = _coord([child], {})
        coord.external_state_version = 0
        coord.async_update_listeners = MagicMock()
        coord.storage.get_chores = MagicMock(return_value=[])
        coord._refresh_tracked_availability_entities()
        return coord

    def test_the_picture_entity_is_tracked(self):
        coord = self._tracking_coord()
        assert coord._tracked_picture_entities == {"person.millie"}

    def test_a_children_without_a_picture_entity_track_nothing(self):
        coord = self._tracking_coord(entity="")
        assert coord._tracked_picture_entities == set()

    def test_a_new_photo_refreshes_the_sensors(self):
        coord = self._tracking_coord()
        coord._availability_state_changed(self._event("person.millie", MILLIE_PIC, "/api/image/serve/new/512x512"))
        assert coord.external_state_version == 1
        coord.async_update_listeners.assert_called_once()

    def test_a_person_arriving_home_does_not(self):
        """The state flips constantly; the picture did not change."""
        coord = self._tracking_coord()
        coord._availability_state_changed(self._event("person.millie", MILLIE_PIC, MILLIE_PIC))
        assert coord.external_state_version == 0
        coord.async_update_listeners.assert_not_called()

    def test_a_photo_removed_is_a_change(self):
        coord = self._tracking_coord()
        coord._availability_state_changed(self._event("person.millie", MILLIE_PIC, None))
        assert coord.external_state_version == 1

    def test_other_entities_are_ignored(self):
        coord = self._tracking_coord()
        coord._availability_state_changed(self._event("person.someone_else", None, MILLIE_PIC))
        assert coord.external_state_version == 0

    def test_a_stray_space_in_the_stored_id_is_still_tracked(self):
        """Copilot review on #1062: the photo lookup trims the id, so tracking
        must too, or a change to that entity would never refresh the sensors."""
        coord = self._tracking_coord(entity=" person.millie ")
        assert coord._tracked_picture_entities == {"person.millie"}
        coord._availability_state_changed(self._event("person.millie", MILLIE_PIC, "/api/image/serve/new/512x512"))
        assert coord.external_state_version == 1


class TestOwnSensorsRefused:
    """A TaskMate child sensor shows the chosen photo, so it can't be the source."""

    def _registry(self, platform):
        entry = MagicMock()
        entry.platform = platform
        registry = MagicMock()
        registry.async_get = MagicMock(return_value=entry)
        return registry

    def test_a_taskmate_sensor_is_not_used_as_the_photo(self):
        child = Child(name="Millie", id="millie", picture_entity="sensor.millie_stats")
        coord = _coord([child], {"sensor.millie_stats": _state(MILLIE_PIC)})
        with patch.object(coord_avatars.er, "async_get", return_value=self._registry("taskmate")):
            assert coord.child_avatar_image(child) == ""

    def test_another_integrations_entity_is_used(self):
        child = Child(name="Millie", id="millie", picture_entity="person.millie")
        coord = _coord([child], {"person.millie": _state(MILLIE_PIC)})
        with patch.object(coord_avatars.er, "async_get", return_value=self._registry("person")):
            assert coord.child_avatar_image(child) == MILLIE_PIC
