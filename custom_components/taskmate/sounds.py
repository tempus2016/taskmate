"""Pure storage/validation helpers for custom completion sounds (#856).

Deliberately mirrors ``images.py`` in shape. Custom sounds are configuration
referenced by a chore's ``completion_sound``, so — like chore images and unlike
evidence photos — they are never swept; they are deleted explicitly when the
user removes them from the panel.

Like ``images.py`` this module has NO Home Assistant HTTP / aiohttp imports at
module scope, so it can be imported from coordinator modules and unit-tested
without a real HA install. The aiohttp views live in ``http_sounds.py``.

Sounds are stored as ``<32 hex>.<ext>`` under ``<config>/taskmate_sounds`` and
served (auth-gated) at ``/api/taskmate/sound/<name>``. A chore selects one by
storing ``custom:<32 hex>`` in its ``completion_sound`` field — see
``const.is_valid_completion_sound``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .photos import matching_files_bytes

_LOGGER = logging.getLogger(__name__)

# Directory under the HA config dir (survives integration upgrades).
SOUNDS_DIR = "taskmate_sounds"

# Public URL prefix for upload (POST) and serve (GET /<name>).
URL_PREFIX = "/api/taskmate/sound"

# A completion sound is a short clip played on a tap. The cap is deliberately
# tight: anything approaching a megabyte is a song, not a sound effect, and
# would delay the very feedback it is supposed to give.
MAX_UPLOAD_BYTES = 1024 * 1024  # 1 MB

# Total disk budget for all stored custom sounds.
MAX_TOTAL_BYTES = 32 * 1024 * 1024  # 32 MB

# Formats every browser HA runs in can decode via <audio>/Audio(). FLAC and
# friends are deliberately absent: a sound that stores fine but silently fails
# to play is worse than a rejected upload.
ALLOWED_EXTS = ("mp3", "ogg", "wav", "m4a")

CONTENT_TYPES = {
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
}

FILENAME_RE = re.compile(r"^[0-9a-f]{32}\.(mp3|ogg|wav|m4a)$")

# Prefix marking a chore's completion_sound as a reference to a custom sound.
CUSTOM_PREFIX = "custom:"

# Stored display names are user input rendered in the panel and the chore
# dropdown. Cap the length so one pathological name cannot break the layout.
MAX_NAME_LEN = 40

__all__ = [
    "ALLOWED_EXTS",
    "CUSTOM_PREFIX",
    "FILENAME_RE",
    "MAX_NAME_LEN",
    "MAX_TOTAL_BYTES",
    "MAX_UPLOAD_BYTES",
    "SOUNDS_DIR",
    "URL_PREFIX",
    "async_delete_sound_file",
    "clean_sound_name",
    "content_type_for",
    "detect_allowed_ext",
    "is_custom_sound",
    "sign_sound_url",
    "sound_file_for_name",
    "sound_id_for_value",
    "sound_url_for_name",
    "sounds_path",
    "total_sounds_bytes",
]


def detect_allowed_ext(data: bytes) -> str | None:
    """Return a file extension for known audio magic bytes, else None.

    Sniffs the actual bytes rather than trusting the client-declared type, for
    the same reason ``photos.detect_image_ext`` does: the declared type is
    attacker-controlled and the stored extension decides the Content-Type we
    later serve it back with.
    """
    if data[:3] == b"ID3":
        return "mp3"
    # Bare MPEG audio with no ID3 tag. The 11-bit frame sync (0xFFE) alone is
    # far too weak a test: 0xFF 0xFE is also a UTF-16LE byte-order mark, so any
    # UTF-16 text file passed as audio and was then stored and served back from
    # this origin as audio/mpeg. Validate the whole 4-byte frame header, whose
    # reserved values a BOM does not satisfy.
    if len(data) >= 4 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        version = (data[1] >> 3) & 0x03  # 01 is reserved
        layer = (data[1] >> 1) & 0x03  # 00 is reserved
        bitrate = (data[2] >> 4) & 0x0F  # 0000 is "free", 1111 is bad
        sample_rate = (data[2] >> 2) & 0x03  # 11 is reserved
        if version != 0x01 and layer != 0x00 and bitrate not in (0x00, 0x0F) and sample_rate != 0x03:
            return "mp3"
    if data[:4] == b"OggS":
        return "ogg"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    # ISO-BMFF: "....ftyp<brand>". These are the brands Apple/ffmpeg emit for
    # AAC-in-MP4 audio.
    if data[4:8] == b"ftyp" and data[8:12] in (b"M4A ", b"mp42", b"isom"):
        return "m4a"
    return None


def content_type_for(filename: str) -> str:
    """Map a stored filename to its Content-Type (defaults to audio/mpeg)."""
    ext = filename.rsplit(".", 1)[-1].lower()
    return CONTENT_TYPES.get(ext, "audio/mpeg")


def clean_sound_name(name: str | None, fallback: str = "Sound") -> str:
    """Normalise a user-supplied display name to something safe to render.

    Strips control characters (which can scramble a line of panel output),
    collapses whitespace and truncates. Never returns an empty string, so a
    sound always has something clickable in the dropdown.
    """
    if not name:
        return fallback
    cleaned = "".join(ch for ch in str(name) if ch.isprintable())
    cleaned = " ".join(cleaned.split())[:MAX_NAME_LEN].strip()
    return cleaned or fallback


def sounds_path(hass) -> Path:
    """Absolute path to the custom-sounds directory."""
    return Path(hass.config.path(SOUNDS_DIR))


def is_custom_sound(value: str | None) -> bool:
    """True only for a well-formed ``custom:<32 hex>.<ext>`` sound value.

    Pure (no hass / no filesystem) so it can guard untrusted input at the
    websocket and service boundaries before any filesystem access.
    """
    if not value or not value.startswith(CUSTOM_PREFIX):
        return False
    return bool(FILENAME_RE.match(value[len(CUSTOM_PREFIX) :]))


def sound_id_for_value(value: str | None) -> str | None:
    """Return the stored filename behind a ``custom:`` sound value, else None."""
    if not is_custom_sound(value):
        return None
    return value[len(CUSTOM_PREFIX) :]


def sound_url_for_name(filename: str) -> str:
    """Public serve URL for a stored sound filename."""
    return f"{URL_PREFIX}/{filename}"


def sound_file_for_name(hass, filename: str) -> Path | None:
    """Map a stored filename to its path, or None if it fails validation."""
    if not FILENAME_RE.match(filename or ""):
        return None
    return sounds_path(hass) / filename


def sign_sound_url(hass, sound_url: str, expiration_hours: int = 24) -> str:
    """Return a self-authenticating signed URL for one of our sound URLs.

    Browsers don't send the HA bearer token on ``Audio()`` requests, so the
    auth-gated serve view 401s on a bare URL. Mirrors ``images.sign_image_url``;
    foreign/blank URLs pass through untouched. The HA import is local so this
    module stays importable without a real HA.
    """
    if not sound_url or not sound_url.startswith(URL_PREFIX + "/"):
        return sound_url
    from datetime import timedelta

    try:
        from homeassistant.components.http.auth import async_sign_path

        return async_sign_path(hass, sound_url, timedelta(hours=expiration_hours))
    except Exception:  # noqa: BLE001 - never break state delivery over a signing hiccup
        _LOGGER.debug("Could not sign sound URL %s", sound_url, exc_info=True)
        return sound_url


async def async_delete_sound_file(hass, filename: str) -> None:
    """Best-effort delete of a stored sound file.

    No-op for a name failing validation or a file that is already gone.
    """
    path = sound_file_for_name(hass, filename)
    if path is None:
        return

    def _unlink() -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as err:  # pragma: no cover - defensive
            _LOGGER.debug("Could not delete custom sound %s: %s", path, err)

    await hass.async_add_executor_job(_unlink)


def total_sounds_bytes(hass) -> int:
    """Sum of all stored custom-sound file sizes (0 if the dir is absent)."""
    return matching_files_bytes(sounds_path(hass), FILENAME_RE)
