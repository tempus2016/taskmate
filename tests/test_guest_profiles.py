"""Guest child profiles (#690).

A visiting cousin gets a temporary child that expires on its own and stays out
of the family leaderboard. Archived rather than deleted, so the visit's
history survives and the same guest can come back next summer.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.util import dt as dt_util

from custom_components.taskmate.models import Child

from .test_coordinator_logic import _make_coord


def _today():
    return dt_util.as_local(dt_util.now()).date()


def _coord(children):
    coord = _make_coord(children=list(children))
    coord.storage.get_children = MagicMock(return_value=list(children))
    coord.storage.update_child = MagicMock()
    coord.storage.async_save = AsyncMock()
    coord.async_refresh = AsyncMock()
    coord.hass.bus.async_fire = MagicMock()
    return coord


def _guest(name="Cousin", days=None, **over):
    expires = "" if days is None else (_today() + timedelta(days=days)).isoformat()
    return Child(name=name, id=name.lower(), is_guest=True, guest_expires_on=expires, **over)


FAMILY = Child(name="Ella", id="ella")


class TestExpiry:
    def test_family_members_never_expire(self):
        assert _coord([FAMILY]).guest_has_expired(FAMILY) is False

    def test_guest_with_no_end_date_never_expires(self):
        """A parent may not know how long the visit is; archiving mid-stay
        would be worse than leaving the profile up."""
        assert _coord([]).guest_has_expired(_guest()) is False

    def test_guest_still_staying(self):
        assert _coord([]).guest_has_expired(_guest(days=3)) is False

    def test_guest_on_their_last_day_is_still_here(self):
        assert _coord([]).guest_has_expired(_guest(days=0)) is False

    def test_guest_past_their_end_date(self):
        assert _coord([]).guest_has_expired(_guest(days=-1)) is True

    def test_unparseable_expiry_is_treated_as_open_ended(self):
        assert _coord([]).guest_has_expired(_guest(name="Odd", days=0)) is False
        broken = Child(name="Broken", id="b", is_guest=True, guest_expires_on="soon")
        assert _coord([]).guest_has_expired(broken) is False


class TestLeaderboard:
    def test_guests_are_excluded(self):
        """A cousin here for a week shouldn't win the month."""
        coord = _coord([FAMILY, _guest()])
        assert [c.id for c in coord.leaderboard_children()] == ["ella"]

    def test_family_only_setup_is_unchanged(self):
        coord = _coord([FAMILY])
        assert len(coord.leaderboard_children()) == 1


class TestArchiving:
    @pytest.mark.asyncio
    async def test_expired_guest_is_archived(self):
        guest = _guest(days=-1)
        coord = _coord([FAMILY, guest])
        assert await coord.async_archive_expired_guests() == ["Cousin"]
        assert guest.availability_entity == "__guest_archived__"
        assert guest.pause_streak_when_unavailable is True
        coord.storage.async_save.assert_awaited()

    @pytest.mark.asyncio
    async def test_current_guest_is_left_alone(self):
        guest = _guest(days=5)
        coord = _coord([guest])
        assert await coord.async_archive_expired_guests() == []
        assert guest.availability_entity == ""

    @pytest.mark.asyncio
    async def test_archiving_is_idempotent(self):
        guest = _guest(days=-1, availability_entity="__guest_archived__")
        coord = _coord([guest])
        assert await coord.async_archive_expired_guests() == []
        coord.storage.async_save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_family_members_are_never_archived(self):
        coord = _coord([FAMILY])
        assert await coord.async_archive_expired_guests() == []

    @pytest.mark.asyncio
    async def test_archiving_fires_an_event(self):
        coord = _coord([_guest(days=-1)])
        await coord.async_archive_expired_guests()
        event, payload = coord.hass.bus.async_fire.call_args[0]
        assert event == "taskmate_guest_archived"
        assert payload["child_name"] == "Cousin"

    @pytest.mark.asyncio
    async def test_archiving_keeps_the_profile(self):
        """Deleting would take the visit's history with it."""
        coord = _coord([_guest(days=-1)])
        await coord.async_archive_expired_guests()
        coord.storage.remove_child = MagicMock()
        coord.storage.remove_child.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_refresh_when_asked_not_to(self):
        coord = _coord([_guest(days=-1)])
        await coord.async_archive_expired_guests(refresh=False)
        coord.async_refresh.assert_not_awaited()


class TestSetGuest:
    @pytest.mark.asyncio
    async def test_marking_a_child_as_a_guest(self):
        child = Child(name="Cousin", id="c1")
        coord = _coord([child])
        coord.storage.get_child = MagicMock(return_value=child)
        await coord.async_set_guest("c1", True, (_today() + timedelta(days=7)).isoformat())
        assert child.is_guest is True
        assert child.guest_expires_on

    @pytest.mark.asyncio
    async def test_promoting_a_guest_clears_the_expiry(self):
        child = _guest(days=3)
        coord = _coord([child])
        coord.storage.get_child = MagicMock(return_value=child)
        await coord.async_set_guest(child.id, False)
        assert child.is_guest is False
        assert child.guest_expires_on == ""

    @pytest.mark.asyncio
    async def test_promoting_un_archives(self):
        """Someone who moves in shouldn't stay invisible."""
        child = _guest(days=-1, availability_entity="__guest_archived__")
        coord = _coord([child])
        coord.storage.get_child = MagicMock(return_value=child)
        await coord.async_set_guest(child.id, False)
        assert child.availability_entity == ""

    @pytest.mark.asyncio
    async def test_bad_expiry_is_rejected(self):
        child = Child(name="Cousin", id="c1")
        coord = _coord([child])
        coord.storage.get_child = MagicMock(return_value=child)
        with pytest.raises(ValueError, match="ISO date"):
            await coord.async_set_guest("c1", True, "next week")

    @pytest.mark.asyncio
    async def test_unknown_child_is_rejected(self):
        coord = _coord([])
        coord.storage.get_child = MagicMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            await coord.async_set_guest("nope", True)


class TestModel:
    def test_guest_fields_round_trip(self):
        restored = Child.from_dict(_guest(days=5).to_dict())
        assert restored.is_guest is True
        assert restored.guest_expires_on

    def test_legacy_child_is_not_a_guest(self):
        restored = Child.from_dict({"name": "Old"})
        assert restored.is_guest is False
        assert restored.guest_expires_on == ""


class TestCardFiltering:
    def test_leaderboard_card_filters_guests(self):
        import pathlib

        card = (
            pathlib.Path(__file__).resolve().parent.parent
            / "custom_components"
            / "taskmate"
            / "www"
            / "taskmate-leaderboard-card.js"
        ).read_text(encoding="utf-8")
        assert card.count("filter(c => !c.is_guest)") == 2

    def test_sensor_exposes_the_flag(self):
        import pathlib

        sensor = (
            pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "sensor.py"
        ).read_text(encoding="utf-8")
        assert '"is_guest": True' in sensor
