"""Pure storage/validation helpers for chore images (#750).

Deliberately mirrors ``photos.py`` in shape but NOT in lifecycle. Evidence
photos are transient artefacts of a completion and are orphan-swept at midnight
by ``coordinator._async_sweep_orphan_photos``, whose referenced set is built
only from completions. Chore images are configuration referenced by a chore, so
they live in their own directory and are never swept — they are deleted
explicitly when the chore is deleted or its image replaced.

Like ``photos.py`` this module has NO Home Assistant HTTP / aiohttp imports at
module scope, so it can be imported from coordinator modules and unit-tested
without a real HA install. The aiohttp views live in ``http_images.py``.

Images are stored as ``<32 hex>.<ext>`` under ``<config>/taskmate_images`` and
served (auth-gated) at ``/api/taskmate/image/<name>``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .photos import content_type_for, detect_image_ext, matching_files_bytes

_LOGGER = logging.getLogger(__name__)

# Directory under the HA config dir (survives integration upgrades).
IMAGES_DIR = "taskmate_images"

# Public URL prefix for upload (POST) and serve (GET /<name>).
URL_PREFIX = "/api/taskmate/image"

# The panel downscales to 512px and re-encodes as JPEG before upload, so a real
# chore image is a few tens of KB. This cap only catches abuse/bugs.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB

# Total disk budget for all stored chore images.
MAX_TOTAL_BYTES = 64 * 1024 * 1024  # 64 MB

# HEIC is deliberately absent: photos.py accepts it because a phone may upload
# one directly, but a chore image is only ever *displayed*, and most browsers
# cannot render HEIC — storing one produces a silently broken image.
ALLOWED_EXTS = ("jpg", "png", "webp")

FILENAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")

# Re-exported so http_images.py has a single import site for its serve view.
__all__ = [
    "ALLOWED_EXTS",
    "FILENAME_RE",
    "IMAGES_DIR",
    "MAX_TOTAL_BYTES",
    "MAX_UPLOAD_BYTES",
    "URL_PREFIX",
    "async_delete_image",
    "content_type_for",
    "detect_allowed_ext",
    "image_file_for_url",
    "images_path",
    "is_taskmate_image_url",
    "sign_image_url",
    "total_images_bytes",
]


def detect_allowed_ext(data: bytes) -> str | None:
    """Sniff image magic bytes, narrowed to the browser-renderable formats."""
    ext = detect_image_ext(data)
    return ext if ext in ALLOWED_EXTS else None


def images_path(hass) -> Path:
    """Absolute path to the chore-images directory."""
    return Path(hass.config.path(IMAGES_DIR))


def is_taskmate_image_url(image_url: str) -> bool:
    """True only for a well-formed ``/api/taskmate/image/<name>`` URL of ours.

    Pure (no hass / no filesystem) so it can guard untrusted input at the
    websocket boundary. Rejects blanks, the evidence-photo prefix, foreign
    URLs, dangerous schemes and anything failing the strict filename pattern.
    """
    if not image_url:
        return False
    prefix = URL_PREFIX + "/"
    if not image_url.startswith(prefix):
        return False
    return bool(FILENAME_RE.match(image_url[len(prefix) :]))


def image_file_for_url(hass, image_url: str) -> Path | None:
    """Map a ``/api/taskmate/image/<name>`` URL to its path, or None."""
    if not is_taskmate_image_url(image_url):
        return None
    return images_path(hass) / image_url[len(URL_PREFIX) + 1 :]


def sign_image_url(hass, image_url: str, expiration_hours: int = 24) -> str:
    """Return a self-authenticating signed URL for one of our image URLs.

    Browsers don't send the HA bearer token on plain ``<img>`` requests, so the
    auth-gated serve view 401s on a bare URL. Foreign/blank URLs pass through.
    The HA import is local so this module stays importable without a real HA.
    """
    if not image_url or not image_url.startswith(URL_PREFIX + "/"):
        return image_url
    from datetime import timedelta

    try:
        from homeassistant.components.http.auth import async_sign_path

        return async_sign_path(hass, image_url, timedelta(hours=expiration_hours))
    except Exception:  # noqa: BLE001 - never break state delivery over a signing hiccup
        _LOGGER.debug("Could not sign image URL %s", image_url, exc_info=True)
        return image_url


async def async_delete_image(hass, image_url: str) -> None:
    """Best-effort delete of the file backing an image URL.

    No-op for foreign URLs (including evidence photos) or a missing file.
    """
    path = image_file_for_url(hass, image_url)
    if path is None:
        return

    def _unlink() -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as err:  # pragma: no cover - defensive
            _LOGGER.debug("Could not delete chore image %s: %s", path, err)

    await hass.async_add_executor_job(_unlink)


def total_images_bytes(hass) -> int:
    """Sum of all stored chore-image file sizes (0 if the dir is absent)."""
    return matching_files_bytes(images_path(hass), FILENAME_RE)
