"""Authenticated HTTP endpoints for uploading and serving chore evidence photos.

Two views, both auth-gated by ``HomeAssistantView`` (so photos are never public):

* ``POST /api/taskmate/photo``        — upload one image, returns ``{"photo_url": ...}``
* ``GET  /api/taskmate/photo/<name>`` — serve a stored image

Pure path/validation logic lives in :mod:`.photos` (unit-tested); this module is
the thin aiohttp wrapper, verified on the dev HA instance.
"""

from __future__ import annotations

import asyncio
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

    # Unlike the image/sound uploads this one is deliberately open to any
    # authenticated user — a child has to be able to post their own evidence.
    # That makes it the one upload path a non-admin can drive, so it carries
    # its own limits: a per-user rate cap, a bound on how many bodies are
    # buffered at once (each one can be MAX_UPLOAD_BYTES), and a per-user cap
    # on uploads that were never attached to a chore.
    MAX_UPLOADS_PER_WINDOW = 20
    RATE_WINDOW_SECONDS = 60
    MAX_CONCURRENT_UPLOADS = 4
    # A body that hasn't arrived in full by then is dropped, so a trickled
    # upload can't hold one of the slots open for everyone else.
    BODY_READ_SECONDS = 60
    # Uploads never attached to anything are swept this soon when the disk
    # budget is hit, so a run of junk uploads can't block evidence for a day.
    FULL_BUDGET_SWEEP_HOURS = 1
    # The household pool is MAX_TOTAL_BYTES; one account may hold at most this
    # much of it in photos nobody has submitted yet. A child posts a photo and
    # then submits the chore, so eight full-size uploads in flight is plenty,
    # and a sibling cannot fill the pool so that nobody else's evidence fits.
    PER_USER_UNATTACHED_BUDGET = 64 * 1024 * 1024

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._limiter = photos.UploadRateLimiter(self.MAX_UPLOADS_PER_WINDOW, self.RATE_WINDOW_SECONDS)
        self._slots = asyncio.Semaphore(self.MAX_CONCURRENT_UPLOADS)
        self._owners = photos.UploadOwners()

    async def post(self, request: web.Request) -> web.Response:
        user = request.get("hass_user")
        user_id = getattr(user, "id", "") or "anonymous"
        if self._limiter.check(user_id):
            _LOGGER.warning("Rejecting photo upload from %s: rate limit exceeded", user_id)
            return self.json_message("Too many uploads, try again shortly", HTTPStatus.TOO_MANY_REQUESTS)

        # Every slot busy means every slot is buffering somebody's body. Say
        # so now rather than queue: a queue of waiting handlers is itself a
        # pile of open connections one account can build.
        if self._slots.locked():
            return self.json_message("Too many uploads at once, try again in a moment", HTTPStatus.TOO_MANY_REQUESTS)
        async with self._slots:
            return await self._handle_upload(request, user_id)

    async def _handle_upload(self, request: web.Request, user_id: str) -> web.Response:
        # Cheap pre-check on the declared length before reading the body.
        if request.content_length and request.content_length > photos.MAX_UPLOAD_BYTES:
            return self.json_message("File too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)

        # This account's own pile of not-yet-submitted photos comes first: the
        # household pool is shared, this one is theirs alone.
        mine = await self._async_unattached_bytes(user_id)
        if mine + (request.content_length or 0) > self.PER_USER_UNATTACHED_BUDGET:
            return self._too_many_waiting()

        # Check the disk budget before accepting a body, not only after: there
        # is no point buffering megabytes we are about to refuse.
        used = await self.hass.async_add_executor_job(photos.total_photos_bytes, self.hass)
        if used >= photos.MAX_TOTAL_BYTES:
            used = await self._async_sweep_when_full(user_id)
        if used >= photos.MAX_TOTAL_BYTES:
            return self.json_message("Photo storage full", HTTPStatus.INSUFFICIENT_STORAGE)

        try:
            async with asyncio.timeout(self.BODY_READ_SECONDS):
                data = await self._read_file_part(request)
        except TimeoutError:
            return self.json_message("Upload took too long", HTTPStatus.REQUEST_TIMEOUT)
        if isinstance(data, web.Response):
            return data

        ext = photos.detect_image_ext(bytes(data))
        if ext is None:
            return self.json_message("Not a valid image", HTTPStatus.BAD_REQUEST)

        # Re-check with the real size now the body is in hand (the pre-checks
        # above only knew the declared length and that neither budget was
        # already full).
        mine = await self._async_unattached_bytes(user_id)
        if mine + len(data) > self.PER_USER_UNATTACHED_BUDGET:
            return self._too_many_waiting()
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

        self._owners.record(name, user_id)
        return self.json({"photo_url": f"{photos.URL_PREFIX}/{name}"})

    def _too_many_waiting(self) -> web.Response:
        return self.json_message(
            "You have too many photos waiting to be attached to a chore. Submit or remove those first.",
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        )

    def _referenced(self) -> set[str]:
        coordinator = _get_coordinator(self.hass)
        return photos.referenced_photo_urls(coordinator.storage) if coordinator is not None else set()

    async def _async_unattached_bytes(self, user_id: str) -> int:
        """Bytes of this user's uploads that no completion has claimed yet."""
        names = self._owners.unattached_for(user_id, self._referenced())
        if not names:
            return 0
        total, missing = await self.hass.async_add_executor_job(
            photos.files_bytes, photos.photos_path(self.hass), names
        )
        for name in missing:
            self._owners.forget(name)
        return total

    async def _read_file_part(self, request: web.Request) -> bytearray | web.Response:
        """Read the "file" part of the multipart body, or a response to send instead."""
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
        return data

    async def _async_sweep_when_full(self, user_id: str) -> int:
        """Make room for this upload and return the new usage.

        The requesting account's own unattached uploads go first, whatever
        their age: a photo they posted a minute ago and never submitted is
        theirs to lose, and taking it means their pile can't be what blocks
        them. Only then are everyone's hour-old orphans swept — a sibling's
        fresh, still-to-be-submitted evidence is never evicted by someone
        else's upload.
        """
        referenced = self._referenced()
        own = self._owners.unattached_for(user_id, referenced)
        for name in own:
            await photos.async_delete_photo(self.hass, f"{photos.URL_PREFIX}/{name}")
            self._owners.forget(name)
        if own:
            _LOGGER.info("Photo storage was full: dropped %d of %s's own unattached upload(s)", len(own), user_id)
        if _get_coordinator(self.hass) is not None:
            removed = await photos.async_sweep_orphan_photos(
                self.hass, referenced, max_age_hours=self.FULL_BUDGET_SWEEP_HOURS
            )
            if removed:
                _LOGGER.info("Photo storage was full: swept %d unattached upload(s)", removed)
        return await self.hass.async_add_executor_job(photos.total_photos_bytes, self.hass)


class TaskMatePhotoServeView(HomeAssistantView):
    """Serve a stored evidence photo by its generated filename."""

    url = photos.URL_PREFIX + "/{filename}"
    name = "api:taskmate:photo:serve"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, filename: str) -> web.Response:
        if not photos.FILENAME_RE.fullmatch(filename):
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
