"""Pure storage/validation helpers for chore evidence photos.

This module deliberately has NO Home Assistant HTTP / aiohttp imports so it can
be imported from the coordinator modules (for cleanup) and unit-tested without a
real HA install. The aiohttp views live in ``http_photos.py``.

Photos are stored as ``<32 hex>.<ext>`` under ``<config>/taskmate_photos`` and
served (auth-gated) at ``/api/taskmate/photo/<name>``.
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

# Directory under the HA config dir (survives integration upgrades).
PHOTOS_DIR = "taskmate_photos"

# Public URL prefix for upload (POST) and serve (GET /<name>).
URL_PREFIX = "/api/taskmate/photo"

# Defensive cap. The child card downscales + JPEG-compresses before upload, so a
# legitimate evidence photo is well under this; the cap only catches abuse/bugs.
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB

# Total disk budget for all stored evidence photos. Each photo is small (the
# card downscales + JPEG-compresses before upload), so this is generous — it
# only caps runaway/abusive uploads (SEC-2).
MAX_TOTAL_BYTES = 512 * 1024 * 1024  # 512 MB

# Stored filenames are always a generated uuid4().hex + a known image extension.
# Anything else is rejected before any filesystem access (path-traversal safety).
FILENAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp|heic)$")

CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "heic": "image/heic",
}


def detect_image_ext(data: bytes) -> str | None:
    """Return a file extension for known image magic bytes, else None.

    Sniffs the actual bytes rather than trusting any client-declared type. The
    card always sends JPEG; PNG/WebP/HEIC are accepted defensively for direct
    API callers.
    """
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    # ISO-BMFF: "....ftyp<brand>"; HEIC brands start the major-brand field.
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"mif1", b"heif"):
        return "heic"
    return None


def content_type_for(filename: str) -> str:
    """Map a stored filename to its Content-Type (defaults to image/jpeg)."""
    ext = filename.rsplit(".", 1)[-1].lower()
    return CONTENT_TYPES.get(ext, "image/jpeg")


def photos_path(hass) -> Path:
    """Absolute path to the evidence-photos directory."""
    return Path(hass.config.path(PHOTOS_DIR))


def is_taskmate_photo_url(photo_url: str) -> bool:
    """True only for a well-formed ``/api/taskmate/photo/<name>`` URL of ours.

    Pure (no hass / no filesystem) so it can guard untrusted ``photo_url`` input
    at the service/coordinator boundary. Rejects blanks, foreign URLs and any
    dangerous scheme (``javascript:``, external ``http(s):``) and anything whose
    name fails the strict filename pattern.
    """
    if not photo_url:
        return False
    prefix = URL_PREFIX + "/"
    if not photo_url.startswith(prefix):
        return False
    return bool(FILENAME_RE.match(photo_url[len(prefix):]))


def photo_file_for_url(hass, photo_url: str) -> Path | None:
    """Map a ``/api/taskmate/photo/<name>`` URL to its file path.

    Returns None for anything that isn't one of our photo URLs or whose name
    fails the strict filename pattern (rejects traversal, sub-paths, foreign
    URLs). Never touches the filesystem.
    """
    if not photo_url:
        return None
    prefix = URL_PREFIX + "/"
    if not photo_url.startswith(prefix):
        return None
    name = photo_url[len(prefix):]
    if not FILENAME_RE.match(name):
        return None
    return photos_path(hass) / name


def sign_photo_url(hass, photo_url: str, expiration_hours: int = 24) -> str:
    """Return a self-authenticating signed URL for one of our photo URLs.

    Browsers don't send the HA bearer token on plain ``<img>`` / top-level
    navigation requests, so the auth-gated serve view returns 401 on a bare
    URL. ``async_sign_path`` appends an ``?authSig=`` token the HTTP auth
    middleware accepts, so the admin panel can render thumbnails and open/save
    the full photo. Foreign/blank URLs are returned unchanged.

    The HA imports are local so this module stays importable without a real HA
    install (the pure helpers above are unit-tested).
    """
    if not photo_url or not photo_url.startswith(URL_PREFIX + "/"):
        return photo_url
    from datetime import timedelta

    try:
        # Import inside the try: this is called on the completion path now
        # (#686 signs the evidence photo for the approval push), and an
        # ImportError escaping here would fail the completion itself — which
        # is exactly what "never break delivery over a signing hiccup" is
        # meant to prevent.
        from homeassistant.components.http.auth import async_sign_path

        return async_sign_path(hass, photo_url, timedelta(hours=expiration_hours))
    except Exception:  # noqa: BLE001 - never break state delivery over a signing hiccup
        _LOGGER.debug("Could not sign photo URL %s", photo_url, exc_info=True)
        return photo_url


async def async_delete_photo(hass, photo_url: str) -> None:
    """Best-effort delete of the file backing a photo URL.

    No-op for foreign URLs or a missing file; logs other OS errors at debug.
    """
    path = photo_file_for_url(hass, photo_url)
    if path is None:
        return

    def _unlink() -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as err:  # pragma: no cover - defensive
            _LOGGER.debug("Could not delete evidence photo %s: %s", path, err)

    await hass.async_add_executor_job(_unlink)


def total_photos_bytes(hass) -> int:
    """Sum of all stored evidence-photo file sizes (0 if the dir is absent)."""
    directory = photos_path(hass)
    if not directory.is_dir():
        return 0
    total = 0
    for p in directory.iterdir():
        if p.is_file() and FILENAME_RE.match(p.name):
            try:
                total += p.stat().st_size
            except OSError:  # pragma: no cover - defensive
                pass
    return total


async def async_sweep_orphan_photos(hass, referenced_urls, max_age_hours: int = 24) -> int:
    """Delete stored photos not referenced by any completion (SEC-2).

    Covers photos orphaned by history pruning and uploads that were never
    attached to a completion. Files younger than ``max_age_hours`` are kept so
    an in-flight upload (uploaded but not yet submitted) is not removed.
    Returns the number of files deleted.
    """
    prefix = URL_PREFIX + "/"
    referenced = {
        url[len(prefix):] for url in referenced_urls
        if url and url.startswith(prefix)
    }
    directory = photos_path(hass)

    def _sweep() -> int:
        if not directory.is_dir():
            return 0
        cutoff = time.time() - max_age_hours * 3600
        removed = 0
        for p in directory.iterdir():
            if not (p.is_file() and FILENAME_RE.match(p.name)):
                continue
            if p.name in referenced:
                continue
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
                    removed += 1
            except OSError:  # pragma: no cover - defensive
                pass
        return removed

    return await hass.async_add_executor_job(_sweep)
