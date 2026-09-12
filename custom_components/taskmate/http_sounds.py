"""aiohttp views for custom completion sounds (#856).

Mirrors ``http_images.py``, including its posture: **upload is admin-only**
because it writes files to disk and only the admin panel ever calls it, while
serving stays plain-authenticated so any household member's card can play a
sound. The serve view also accepts HA's signed-path signature, which is how a
plain ``Audio()`` in a card loads without a bearer token.
"""

from __future__ import annotations

import logging
import uuid
from http import HTTPStatus

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from . import sounds

_LOGGER = logging.getLogger(__name__)

SOUND_HTTP_VIEWS_REGISTERED = "sound_http_registered"


class TaskMateSoundUploadView(HomeAssistantView):
    """Receive a multipart audio upload and store it under the config dir."""

    url = sounds.URL_PREFIX
    name = "api:taskmate:sound:upload"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        # Admin-only: this writes files and is only ever called by the panel.
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return self.json_message("Admin required", HTTPStatus.FORBIDDEN)

        # Cheap pre-check on the declared length before reading the body.
        if request.content_length and request.content_length > sounds.MAX_UPLOAD_BYTES:
            return self.json_message("File too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)

        try:
            reader = await request.multipart()
        except (ValueError, AssertionError):
            return self.json_message("Expected multipart form", HTTPStatus.BAD_REQUEST)

        # Bound the scan so a stream of endlessly-named non-"file" parts can't
        # hold the handler open indefinitely (mirrors the photo upload).
        field = await reader.next()
        parts_scanned = 0
        while field is not None and field.name != "file":
            parts_scanned += 1
            if parts_scanned > 16:
                return self.json_message("Too many form parts", HTTPStatus.BAD_REQUEST)
            field = await reader.next()
        if field is None:
            return self.json_message("No file provided", HTTPStatus.BAD_REQUEST)

        # Stream the part, enforcing the size cap as we go.
        data = bytearray()
        while True:
            chunk = await field.read_chunk()
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > sounds.MAX_UPLOAD_BYTES:
                return self.json_message("File too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)

        ext = sounds.detect_allowed_ext(bytes(data))
        if ext is None:
            return self.json_message("Not a supported sound (MP3, OGG, WAV or M4A)", HTTPStatus.BAD_REQUEST)

        used = await self.hass.async_add_executor_job(sounds.total_sounds_bytes, self.hass)
        if used + len(data) > sounds.MAX_TOTAL_BYTES:
            return self.json_message("Sound storage full", HTTPStatus.INSUFFICIENT_STORAGE)

        name = f"{uuid.uuid4().hex}.{ext}"
        directory = sounds.sounds_path(self.hass)
        payload = bytes(data)

        def _write() -> None:
            directory.mkdir(parents=True, exist_ok=True)
            (directory / name).write_bytes(payload)

        try:
            await self.hass.async_add_executor_job(_write)
        except OSError as err:
            _LOGGER.error("Failed to store custom sound: %s", err)
            return self.json_message("Could not store sound", HTTPStatus.INTERNAL_SERVER_ERROR)

        return self.json({"file": name, "sound_url": sounds.sound_url_for_name(name)})


class TaskMateSoundServeView(HomeAssistantView):
    """Serve a stored custom sound by its generated filename."""

    url = sounds.URL_PREFIX + "/{filename}"
    name = "api:taskmate:sound:serve"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, filename: str) -> web.Response:
        if not sounds.FILENAME_RE.match(filename):
            return web.Response(status=HTTPStatus.NOT_FOUND)

        path = sounds.sounds_path(self.hass) / filename

        def _read() -> bytes | None:
            try:
                return path.read_bytes()
            except (FileNotFoundError, OSError):
                return None

        data = await self.hass.async_add_executor_job(_read)
        if data is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        return web.Response(
            body=data,
            content_type=sounds.content_type_for(filename),
            headers={
                "Cache-Control": "private, max-age=31536000",
                # Same as the photo view: these files are user-supplied, so
                # don't let a browser content-sniff them into something
                # executable on the Home Assistant origin.
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": "inline",
            },
        )


def async_register_sound_views(hass: HomeAssistant) -> None:
    """Register the upload + serve views once."""
    from .const import DOMAIN

    if hass.data.get(DOMAIN, {}).get(SOUND_HTTP_VIEWS_REGISTERED):
        return
    hass.http.register_view(TaskMateSoundUploadView(hass))
    hass.http.register_view(TaskMateSoundServeView(hass))
    hass.data.setdefault(DOMAIN, {})[SOUND_HTTP_VIEWS_REGISTERED] = True
    _LOGGER.debug("Registered TaskMate sound HTTP views")
