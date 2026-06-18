"""Authenticated HTTP endpoints for uploading and serving chore evidence photos.

Two views, both auth-gated by ``HomeAssistantView`` (so photos are never public):

* ``POST /api/taskmate/photo``        — upload one image, returns ``{"photo_url": ...}``
* ``GET  /api/taskmate/photo/<name>`` — serve a stored image

Pure path/validation logic lives in :mod:`.photos` (unit-tested); this module is
the thin aiohttp wrapper, verified on the dev HA instance.
"""
from __future__ import annotations

import logging
import uuid
from http import HTTPStatus

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from . import photos

_LOGGER = logging.getLogger(__name__)

HTTP_VIEWS_REGISTERED = "photo_http_registered"


class TaskMatePhotoUploadView(HomeAssistantView):
    """Receive a multipart image upload and store it under the config dir."""

    url = photos.URL_PREFIX
    name = "api:taskmate:photo:upload"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        # Cheap pre-check on the declared length before reading the body.
        if request.content_length and request.content_length > photos.MAX_UPLOAD_BYTES:
            return self.json_message(
                "File too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE
            )

        try:
            reader = await request.multipart()
        except (ValueError, AssertionError):
            return self.json_message("Expected multipart form", HTTPStatus.BAD_REQUEST)

        # Find the "file" part.
        field = await reader.next()
        while field is not None and field.name != "file":
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
            if len(data) > photos.MAX_UPLOAD_BYTES:
                return self.json_message(
                    "File too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE
                )

        ext = photos.detect_image_ext(bytes(data))
        if ext is None:
            return self.json_message("Not a valid image", HTTPStatus.BAD_REQUEST)

        name = f"{uuid.uuid4().hex}.{ext}"
        directory = photos.photos_path(self.hass)
        payload = bytes(data)

        def _write() -> None:
            directory.mkdir(parents=True, exist_ok=True)
            (directory / name).write_bytes(payload)

        try:
            await self.hass.async_add_executor_job(_write)
        except OSError as err:
            _LOGGER.error("Failed to store evidence photo: %s", err)
            return self.json_message(
                "Could not store photo", HTTPStatus.INTERNAL_SERVER_ERROR
            )

        return self.json({"photo_url": f"{photos.URL_PREFIX}/{name}"})


class TaskMatePhotoServeView(HomeAssistantView):
    """Serve a stored evidence photo by its generated filename."""

    url = photos.URL_PREFIX + "/{filename}"
    name = "api:taskmate:photo:serve"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, filename: str) -> web.Response:
        if not photos.FILENAME_RE.match(filename):
            return web.Response(status=HTTPStatus.NOT_FOUND)

        path = photos.photos_path(self.hass) / filename

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
            content_type=photos.content_type_for(filename),
            headers={"Cache-Control": "private, max-age=31536000"},
        )


def async_register_photo_views(hass: HomeAssistant) -> None:
    """Register the upload + serve views once."""
    from .const import DOMAIN

    if hass.data.get(DOMAIN, {}).get(HTTP_VIEWS_REGISTERED):
        return
    hass.http.register_view(TaskMatePhotoUploadView(hass))
    hass.http.register_view(TaskMatePhotoServeView(hass))
    hass.data.setdefault(DOMAIN, {})[HTTP_VIEWS_REGISTERED] = True
    _LOGGER.debug("Registered TaskMate photo HTTP views")
