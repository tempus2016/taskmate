"""aiohttp views for chore images (#750).

Mirrors ``http_photos.py``. The one deliberate difference is that **upload is
admin-only**: chore editing is already ``@_admin_only`` in websocket.py, and
only the admin panel uploads, so allowing any authenticated household member to
write files to disk would weaken the existing posture for no benefit. Serving
stays plain-authenticated, matching photos.
"""

from __future__ import annotations

import logging
import uuid
from http import HTTPStatus

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from . import images

_LOGGER = logging.getLogger(__name__)

IMAGE_HTTP_VIEWS_REGISTERED = "image_http_registered"


class TaskMateImageUploadView(HomeAssistantView):
    """Receive a multipart image upload and store it under the config dir."""

    url = images.URL_PREFIX
    name = "api:taskmate:image:upload"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        # Admin-only: this writes files and is only ever called by the panel.
        user = request.get("hass_user")
        if user is None or not user.is_admin:
            return self.json_message("Admin required", HTTPStatus.FORBIDDEN)

        # Cheap pre-check on the declared length before reading the body.
        if request.content_length and request.content_length > images.MAX_UPLOAD_BYTES:
            return self.json_message("File too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)

        try:
            reader = await request.multipart()
        except (ValueError, AssertionError):
            return self.json_message("Expected multipart form", HTTPStatus.BAD_REQUEST)

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
            if len(data) > images.MAX_UPLOAD_BYTES:
                return self.json_message("File too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)

        ext = images.detect_allowed_ext(bytes(data))
        if ext is None:
            return self.json_message("Not a supported image (JPEG, PNG or WebP)", HTTPStatus.BAD_REQUEST)

        used = await self.hass.async_add_executor_job(images.total_images_bytes, self.hass)
        if used + len(data) > images.MAX_TOTAL_BYTES:
            return self.json_message("Image storage full", HTTPStatus.INSUFFICIENT_STORAGE)

        name = f"{uuid.uuid4().hex}.{ext}"
        directory = images.images_path(self.hass)
        payload = bytes(data)

        def _write() -> None:
            directory.mkdir(parents=True, exist_ok=True)
            (directory / name).write_bytes(payload)

        try:
            await self.hass.async_add_executor_job(_write)
        except OSError as err:
            _LOGGER.error("Failed to store chore image: %s", err)
            return self.json_message("Could not store image", HTTPStatus.INTERNAL_SERVER_ERROR)

        return self.json({"image_url": f"{images.URL_PREFIX}/{name}"})


class TaskMateImageServeView(HomeAssistantView):
    """Serve a stored chore image by its generated filename."""

    url = images.URL_PREFIX + "/{filename}"
    name = "api:taskmate:image:serve"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, filename: str) -> web.Response:
        if not images.FILENAME_RE.match(filename):
            return web.Response(status=HTTPStatus.NOT_FOUND)

        path = images.images_path(self.hass) / filename

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
            content_type=images.content_type_for(filename),
            headers={"Cache-Control": "private, max-age=31536000"},
        )


def async_register_image_views(hass: HomeAssistant) -> None:
    """Register the upload + serve views once."""
    from .const import DOMAIN

    if hass.data.get(DOMAIN, {}).get(IMAGE_HTTP_VIEWS_REGISTERED):
        return
    hass.http.register_view(TaskMateImageUploadView(hass))
    hass.http.register_view(TaskMateImageServeView(hass))
    hass.data.setdefault(DOMAIN, {})[IMAGE_HTTP_VIEWS_REGISTERED] = True
    _LOGGER.debug("Registered TaskMate image HTTP views")
