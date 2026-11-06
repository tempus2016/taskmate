"""Read-aloud (#684).

Speak a child's outstanding chores to a media player: "Ella, you have three
things left: make your bed, brush your teeth and pack your bag."

The sentence comes from parent-editable templates when they are set (a
family may well want wording that isn't any of the shipped languages), and
otherwise from the ``notify.read_aloud_*`` strings in Home Assistant's
language, like the push notifications.
"""

from __future__ import annotations

import logging
from typing import Any

from . import notify_strings
from .errors import TaskMateError

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
        """ "a, b and c" — spoken lists need a conjunction, not commas."""
        joiner = self._tts_setting("read_aloud_joiner", "")
        if not names:
            return ""
        if len(names) == 1:
            return names[0]
        if not joiner:
            # No custom joiner: the language's own "a, b and c".
            return notify_strings.join_names(self.hass, names)
        return f"{', '.join(names[:-1])} {joiner} {names[-1]}"

    def build_read_aloud_message(self, child_id: str) -> str:
        """The sentence to speak for a child. Raises ValueError if unknown."""
        child = self.storage.get_child(child_id)
        if not child:
            raise TaskMateError("child_not_found", child_id=child_id)

        chores = self.get_due_chores_for_child(child_id)
        names = [c.name for c in chores]

        if not names:
            setting, key = "read_aloud_done_template", "read_aloud_done"
        elif len(names) == 1:
            setting, key = "read_aloud_one_template", "read_aloud_one"
        else:
            setting, key = "read_aloud_template", "read_aloud_many"
        template = self._tts_setting(setting, "") or notify_strings.text(self.hass, key)

        try:
            return notify_strings.safe_format(
                template,
                {"name": child.name, "count": len(names), "chores": self._join_chore_names(names)},
                strict=True,
            )
        except (KeyError, IndexError, ValueError, AttributeError):
            # A parent-edited template with a bad placeholder must not silence
            # the feature — fall back to the built-in wording.
            _LOGGER.warning(
                "read-aloud template %r has an unknown placeholder; using the default",
                template,
            )
            fallback = (
                DEFAULT_DONE_TEMPLATE if not names else DEFAULT_ONE_TEMPLATE if len(names) == 1 else DEFAULT_TEMPLATE
            )
            return fallback.format(
                name=child.name,
                count=len(names),
                chores=self._join_chore_names(names),
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
        candidates = sorted(state.entity_id for state in self.hass.states.async_all("tts"))
        return candidates[0] if candidates else ""

    async def async_read_aloud(
        self,
        child_id: str,
        media_player: str = "",
        tts_entity: str = "",
        message: str = "",
        context: Any = None,
    ) -> str:
        """Speak a child's outstanding chores. Returns what was said."""
        target = media_player or self._tts_setting("read_aloud_media_player", "")
        if not target:
            raise TaskMateError("tts_no_media_player")

        speaker = self._resolve_tts_entity(tts_entity)
        if not speaker:
            raise TaskMateError("tts_no_entity")

        text = message.strip() or self.build_read_aloud_message(child_id)

        # blocking=True so a bad media player or a broken TTS reaches the
        # caller. This is a service a parent invokes deliberately; "it silently
        # did nothing" is the worst possible answer.
        # Forward the caller's context so Home Assistant applies that user's
        # entity permissions to the speaker, instead of the call arriving
        # unattributed and bypassing them.
        await self.hass.services.async_call(
            "tts",
            "speak",
            {
                "entity_id": speaker,
                "media_player_entity_id": target,
                "message": text,
            },
            blocking=True,
            context=context,
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
