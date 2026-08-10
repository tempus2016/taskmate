"""Read-aloud (#684).

Speaks a child's outstanding chores to a media player. Wording comes from
parent-editable templates: the frontend locales don't reach the backend, and a
family may want phrasing that isn't one of the eight shipped languages.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coord_tts import (
    DEFAULT_DONE_TEMPLATE,
    DEFAULT_ONE_TEMPLATE,
    DEFAULT_TEMPLATE,
)
from custom_components.taskmate.models import Child, Chore

from .test_coordinator_logic import _make_coord


def _coord(due=(), settings=None, tts_entities=()):
    conf = dict(settings or {})
    kid = Child(name="Ella", id="kid1")
    coord = _make_coord(settings=conf, children=[kid])
    coord.storage.get_setting = MagicMock(side_effect=lambda k, d="": conf.get(k, d))
    coord.get_due_chores_for_child = MagicMock(return_value=list(due))
    coord.hass.services.async_call = AsyncMock()
    coord.hass.bus.async_fire = MagicMock()
    coord.hass.states.async_all = MagicMock(return_value=[MagicMock(entity_id=e) for e in tts_entities])
    return coord


def _chore(name):
    return Chore(name=name)


class TestMessage:
    def test_several_chores_are_listed_with_a_conjunction(self):
        coord = _coord([_chore("make your bed"), _chore("brush your teeth"), _chore("pack your bag")])
        msg = coord.build_read_aloud_message("kid1")
        assert msg == "Ella, you have 3 things left: make your bed, brush your teeth and pack your bag."

    def test_a_single_chore_uses_singular_wording(self):
        coord = _coord([_chore("make your bed")])
        assert coord.build_read_aloud_message("kid1") == "Ella, you have one thing left: make your bed."

    def test_nothing_left_is_congratulated(self):
        assert _coord([]).build_read_aloud_message("kid1") == "Ella, you're all done. Nice one!"

    def test_two_chores_need_no_comma(self):
        coord = _coord([_chore("a"), _chore("b")])
        assert "a and b" in coord.build_read_aloud_message("kid1")

    def test_templates_are_parent_editable(self):
        coord = _coord([_chore("a")], {"read_aloud_one_template": "Oi {name}! {chores}!"})
        assert coord.build_read_aloud_message("kid1") == "Oi Ella! a!"

    def test_joiner_is_parent_editable(self):
        """So a non-English household can say "og" or "et"."""
        coord = _coord([_chore("a"), _chore("b")], {"read_aloud_joiner": "og"})
        assert "a og b" in coord.build_read_aloud_message("kid1")

    def test_blank_template_falls_back_to_the_default(self):
        coord = _coord([], {"read_aloud_done_template": "   "})
        assert coord.build_read_aloud_message("kid1") == DEFAULT_DONE_TEMPLATE.format(name="Ella", count=0, chores="")

    def test_bad_placeholder_does_not_silence_the_feature(self):
        """A typo'd template should still speak, using the built-in wording."""
        coord = _coord([_chore("a"), _chore("b")], {"read_aloud_template": "{nmae} {oops}"})
        assert coord.build_read_aloud_message("kid1") == DEFAULT_TEMPLATE.format(name="Ella", count=2, chores="a and b")

    def test_unknown_child_is_rejected(self):
        coord = _coord([])
        coord.storage.get_child = MagicMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            coord.build_read_aloud_message("nope")


class TestSpeaking:
    @pytest.mark.asyncio
    async def test_speaks_blocking_so_failures_surface(self):
        """A parent invoked this deliberately; "it silently did nothing" is
        the worst possible answer."""
        coord = _coord([_chore("a")], {"read_aloud_media_player": "media_player.kitchen"}, tts_entities=["tts.piper"])
        await coord.async_read_aloud("kid1")
        assert coord.hass.services.async_call.await_args.kwargs["blocking"] is True

    @pytest.mark.asyncio
    async def test_speaks_through_tts(self):
        coord = _coord([_chore("a")], {"read_aloud_media_player": "media_player.kitchen"}, tts_entities=["tts.piper"])
        said = await coord.async_read_aloud("kid1")
        coord.hass.services.async_call.assert_awaited_with(
            "tts",
            "speak",
            {"entity_id": "tts.piper", "media_player_entity_id": "media_player.kitchen", "message": said},
            blocking=True,
        )

    @pytest.mark.asyncio
    async def test_explicit_arguments_win_over_settings(self):
        coord = _coord(
            [_chore("a")],
            {"read_aloud_media_player": "media_player.kitchen", "read_aloud_tts_entity": "tts.configured"},
            tts_entities=["tts.discovered"],
        )
        await coord.async_read_aloud("kid1", media_player="media_player.bedroom", tts_entity="tts.explicit")
        payload = coord.hass.services.async_call.await_args[0][2]
        assert payload["entity_id"] == "tts.explicit"
        assert payload["media_player_entity_id"] == "media_player.bedroom"

    @pytest.mark.asyncio
    async def test_configured_tts_beats_discovery(self):
        coord = _coord(
            [_chore("a")],
            {"read_aloud_media_player": "media_player.kitchen", "read_aloud_tts_entity": "tts.configured"},
            tts_entities=["tts.other"],
        )
        await coord.async_read_aloud("kid1")
        assert coord.hass.services.async_call.await_args[0][2]["entity_id"] == "tts.configured"

    @pytest.mark.asyncio
    async def test_single_tts_entity_is_picked_automatically(self):
        """Most households have exactly one — don't make them configure it."""
        coord = _coord(
            [_chore("a")], {"read_aloud_media_player": "media_player.kitchen"}, tts_entities=["tts.only_one"]
        )
        await coord.async_read_aloud("kid1")
        assert coord.hass.services.async_call.await_args[0][2]["entity_id"] == "tts.only_one"

    @pytest.mark.asyncio
    async def test_message_override_is_spoken_verbatim(self):
        coord = _coord([_chore("a")], {"read_aloud_media_player": "media_player.kitchen"}, tts_entities=["tts.piper"])
        said = await coord.async_read_aloud("kid1", message="Dinner is ready")
        assert said == "Dinner is ready"

    @pytest.mark.asyncio
    async def test_no_media_player_is_a_clear_error(self):
        coord = _coord([_chore("a")], {}, tts_entities=["tts.piper"])
        with pytest.raises(ValueError, match="No media player"):
            await coord.async_read_aloud("kid1")

    @pytest.mark.asyncio
    async def test_no_tts_entity_is_a_clear_error(self):
        coord = _coord([_chore("a")], {"read_aloud_media_player": "media_player.kitchen"})
        with pytest.raises(ValueError, match="text-to-speech"):
            await coord.async_read_aloud("kid1")

    @pytest.mark.asyncio
    async def test_speaking_fires_an_event(self):
        coord = _coord([_chore("a")], {"read_aloud_media_player": "media_player.kitchen"}, tts_entities=["tts.piper"])
        await coord.async_read_aloud("kid1")
        event, payload = coord.hass.bus.async_fire.call_args[0]
        assert event == "taskmate_read_aloud"
        assert payload["media_player"] == "media_player.kitchen"


class TestPreview:
    def test_preview_does_not_speak(self):
        coord = _coord([_chore("a")], {"read_aloud_media_player": "media_player.kitchen"}, tts_entities=["tts.piper"])
        preview = coord.read_aloud_preview("kid1")
        assert preview["message"] == DEFAULT_ONE_TEMPLATE.format(name="Ella", count=1, chores="a")
        assert preview["tts_entity"] == "tts.piper"
        coord.hass.services.async_call.assert_not_awaited()
