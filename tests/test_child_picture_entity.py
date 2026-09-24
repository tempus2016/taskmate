"""A child's face can come from any entity's picture — normally their person.

`Child.picture_entity` stores only the entity id; the picture URL is read from
that entity on every update, so a photo changed in Settings › People needs
nothing re-saved here and a deleted entity cannot leave a broken image behind.

It is deliberately independent of `linked_user_id`: a young child commonly has
a person entity with a photo but no Home Assistant login of their own.

Every lookup fails safe to "" and the caller falls back to the MDI avatar.
"""

from __future__ import annotations

from unittest.mock import MagicMock

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
