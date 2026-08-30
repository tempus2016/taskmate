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
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

HTTP_VIEWS_REGISTERED = "photo_http_registered"


def _get_coordinator(hass: HomeAssistant):
    from .coordinator import TaskMateCoordinator

    for value in hass.data.get(DOMAIN, {}).values():
        if isinstance(value, TaskMateCoordinator):
            return value
    return None


async def _may_view_photo(hass: HomeAssistant, request: web.Request, filename: str) -> bool:
    """Whether the requesting user may read this evidence photo.

    Evidence photos can contain images of children, so being merely logged in is
    not enough: allow an admin, a configured TaskMate parent, or the child whose
    own completion references the file (via their linked HA user). Signed
    ``<img>`` requests resolve to the signing user, so per-user client-side
    signing keeps this bound to the actual viewer.
    """
    user = request.get("hass_user")
    if user is None:
        return False
    if getattr(user, "is_admin", False):
        return True
    coordinator = _get_coordinator(hass)
    if coordinator is None:
        return False
    if user.id in (coordinator.storage.get_parent_user_ids() or []):
        return True
    photo_url = f"{photos.URL_PREFIX}/{filename}"
    for comp in coordinator.storage.get_completions():
        if getattr(comp, "photo_url", "") != photo_url:
            continue
        child = coordinator.get_child(comp.child_id)
        if child and getattr(child, "linked_user_id", "") == user.id:
            return True
    return False


class TaskMatePhotoUploadView(HomeAssistantView):
    """Receive a multipart image upload and store it under the config dir."""

    url = photos.URL_PREFIX
    name = "api:taskmate:photo:upload"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        # Cheap pre-check on the declared length before reading the body.
        if request.content_length and request.content_length > photos.MAX_UPLOAD_BYTES:
            return self.json_message("File too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)

        try:
            reader = await request.multipart()
        except (ValueError, AssertionError):
            return self.json_message("Expected multipart form", HTTPStatus.BAD_REQUEST)

        # Find the "file" part. Bound the scan so a stream of endlessly-named
        # non-"file" parts can't hold a handler open indefinitely.
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
            if len(data) > photos.MAX_UPLOAD_BYTES:
                return self.json_message("File too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)

        ext = photos.detect_image_ext(bytes(data))
        if ext is None:
            return self.json_message("Not a valid image", HTTPStatus.BAD_REQUEST)

        # DoS guard: reject if the photo store is already at its disk budget.
        used = await self.hass.async_add_executor_job(photos.total_photos_bytes, self.hass)
        if used + len(data) > photos.MAX_TOTAL_BYTES:
            return self.json_message("Photo storage full", HTTPStatus.INSUFFICIENT_STORAGE)

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
            return self.json_message("Could not store photo", HTTPStatus.INTERNAL_SERVER_ERROR)

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

        # Return 404 (not 403) when unauthorized so the endpoint doesn't confirm
        # a file exists to a caller who may not read it.
        if not await _may_view_photo(self.hass, request, filename):
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
            headers={
                "Cache-Control": "private, max-age=31536000",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": "inline",
            },
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
