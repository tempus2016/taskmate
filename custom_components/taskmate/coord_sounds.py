"""Coordinator mixin for custom completion sounds (#856).

The file itself is written to disk by the upload view in ``http_sounds.py``;
this mixin owns the *registry* — the display name a user sees in the sound
dropdown — and the cascade that keeps chores from holding a dangling
``custom:`` reference after a sound is deleted.
"""

from __future__ import annotations

import logging

from .models import CustomSound
from .sounds import (
    CUSTOM_PREFIX,
    FILENAME_RE,
    async_delete_sound_file,
    clean_sound_name,
    sign_sound_url,
    sound_url_for_name,
)

_LOGGER = logging.getLogger(__name__)


class SoundsMixin:
    """Register, rename and delete user-uploaded completion sounds."""

    def custom_sounds_state(self) -> list[dict]:
        """The custom sound list as the panel and the cards consume it.

        ``value`` is what goes in a chore's ``completion_sound``; ``url`` is
        *signed*, because a card plays it with a bare ``Audio()`` which carries
        no bearer token and would otherwise 401 against the auth-gated serve
        view. Mirrors how ``images.sign_image_url`` feeds chore pictures.
        """
        return [
            {
                "value": f"{CUSTOM_PREFIX}{s.file}",
                "file": s.file,
                "name": s.name,
                "url": sign_sound_url(self.hass, sound_url_for_name(s.file)),
            }
            for s in self.storage.get_custom_sounds()
        ]

    async def async_add_custom_sound(self, file: str, name: str) -> CustomSound:
        """Register an already-uploaded sound file under a display name."""
        if not FILENAME_RE.match(file or ""):
            raise ValueError(f"Not a valid sound file name: {file}")
        if self.storage.get_custom_sound(file):
            raise ValueError(f"Sound {file} is already registered")

        sound = CustomSound(name=clean_sound_name(name), file=file)
        self.storage.add_custom_sound(sound)
        await self.storage.async_save()
        await self.async_refresh()
        return sound

    async def async_rename_custom_sound(self, file: str, name: str) -> CustomSound:
        """Change a custom sound's display name."""
        if not self.storage.rename_custom_sound(file, clean_sound_name(name)):
            raise ValueError(f"Unknown custom sound: {file}")
        await self.storage.async_save()
        await self.async_refresh()
        return self.storage.get_custom_sound(file)

    async def async_remove_custom_sound(self, file: str) -> int:
        """Delete a custom sound, its file, and any chore reference to it.

        Returns the number of chores whose ``completion_sound`` was reset. The
        registry row goes first so a failed unlink still removes the sound from
        the UI rather than leaving a row whose file may be gone.
        """
        if not self.storage.get_custom_sound(file):
            raise ValueError(f"Unknown custom sound: {file}")

        reset = self.storage.reset_chores_using_sound(f"{CUSTOM_PREFIX}{file}")
        self.storage.remove_custom_sound(file)
        await self.storage.async_save()
        await async_delete_sound_file(self.hass, file)
        await self.async_refresh()

        if reset:
            _LOGGER.debug("Reset %d chore(s) to the default sound after deleting %s", reset, file)
        return reset
