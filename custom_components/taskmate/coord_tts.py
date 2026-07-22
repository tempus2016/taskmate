"""Read-aloud (#684).

Speak a child's outstanding chores to a media player: "Ella, you have three
things left: make your bed, brush your teeth and pack your bag."

The sentence is built from parent-editable templates rather than translated
strings. TaskMate's frontend locales don't reach the backend, and a family may
well want wording that isn't any of the eight shipped languages — so the
templates are settings, documented with their placeholders.
"""
from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

DEFAULT_TEMPLATE = "{name}, you have {count} things left: {chores}."
DEFAULT_ONE_TEMPLATE = "{name}, you have one thing left: {chores}."
DEFAULT_DONE_TEMPLATE = "{name}, you're all done. Nice one!"
DEFAULT_JOINER = "and"


class ReadAloudMixin:
    """Mixin providing the spoken outstanding-chore summary."""

    def _tts_setting(self, key: str, default: str) -> str:
        value = self.storage.get_setting(key, "")
        return str(value).strip() or default

    def _join_chore_names(self, names: list[str]) -> str:
        """"a, b and c" — spoken lists need a conjunction, not commas."""
        joiner = self._tts_setting("read_aloud_joiner", DEFAULT_JOINER)
        if not names:
            return ""
        if len(names) == 1:
            return names[0]
        return f"{', '.join(names[:-1])} {joiner} {names[-1]}"

    def build_read_aloud_message(self, child_id: str) -> str:
        """The sentence to speak for a child. Raises ValueError if unknown."""
        child = self.storage.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        chores = self.get_due_chores_for_child(child_id)
        names = [c.name for c in chores]

        if not names:
            template = self._tts_setting("read_aloud_done_template", DEFAULT_DONE_TEMPLATE)
        elif len(names) == 1:
            template = self._tts_setting("read_aloud_one_template", DEFAULT_ONE_TEMPLATE)
        else:
            template = self._tts_setting("read_aloud_template", DEFAULT_TEMPLATE)

        try:
            return template.format(
                name=child.name, count=len(names), chores=self._join_chore_names(names),
            )
        except (KeyError, IndexError, ValueError):
            # A parent-edited template with a bad placeholder must not silence
            # the feature — fall back to the built-in wording.
            _LOGGER.warning(
                "read-aloud template %r has an unknown placeholder; using the default",
                template,
            )
            fallback = (
                DEFAULT_DONE_TEMPLATE if not names
                else DEFAULT_ONE_TEMPLATE if len(names) == 1
                else DEFAULT_TEMPLATE
            )
            return fallback.format(
                name=child.name, count=len(names), chores=self._join_chore_names(names),
            )

    def _resolve_tts_entity(self, explicit: str = "") -> str:
        """The tts.* entity to speak through, or "" if none can be found."""
        if explicit:
            return explicit
        configured = self._tts_setting("read_aloud_tts_entity", "")
        if configured:
            return configured
        # Single-TTS households are the common case; picking the only one
        # beats making them configure it.
        candidates = sorted(
            state.entity_id for state in self.hass.states.async_all("tts")
        )
        return candidates[0] if candidates else ""

    async def async_read_aloud(
        self, child_id: str, media_player: str = "", tts_entity: str = "",
        message: str = "",
    ) -> str:
        """Speak a child's outstanding chores. Returns what was said."""
        target = media_player or self._tts_setting("read_aloud_media_player", "")
        if not target:
            raise ValueError(
                "No media player given, and no default set in Settings"
            )

        speaker = self._resolve_tts_entity(tts_entity)
        if not speaker:
            raise ValueError(
                "No text-to-speech entity found. Set one in Settings or pass tts_entity."
            )

        text = message.strip() or self.build_read_aloud_message(child_id)

        # blocking=True so a bad media player or a broken TTS reaches the
        # caller. This is a service a parent invokes deliberately; "it silently
        # did nothing" is the worst possible answer.
        await self.hass.services.async_call(
            "tts", "speak",
            {
                "entity_id": speaker,
                "media_player_entity_id": target,
                "message": text,
            },
            blocking=True,
        )
        _LOGGER.info("Read aloud to %s via %s: %s", target, speaker, text)

        self.hass.bus.async_fire(
            "taskmate_read_aloud",
            {
                "child_id": child_id,
                "media_player": target,
                "tts_entity": speaker,
                "message": text,
            },
        )
        return text

    def read_aloud_preview(self, child_id: str) -> dict[str, Any]:
        """What would be said, without saying it — for the panel's preview."""
        return {
            "child_id": child_id,
            "message": self.build_read_aloud_message(child_id),
            "tts_entity": self._resolve_tts_entity(),
            "media_player": self._tts_setting("read_aloud_media_player", ""),
        }
