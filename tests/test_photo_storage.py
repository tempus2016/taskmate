"""Tests for the pure evidence-photo storage helpers (custom_components.taskmate.photos)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from custom_components.taskmate import photos


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _hass(tmp_path: Path):
    hass = MagicMock()
    hass.config.path = MagicMock(side_effect=lambda *p: str(Path(tmp_path, *p)))

    async def _exec(func, *args):
        return func(*args)

    hass.async_add_executor_job = MagicMock(side_effect=_exec)
    return hass


# ── detect_image_ext ────────────────────────────────────────────────────────

def test_detect_jpeg():
    assert photos.detect_image_ext(b"\xff\xd8\xff\xe0\x00\x10JFIF") == "jpg"


def test_detect_png():
    assert photos.detect_image_ext(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8) == "png"


def test_detect_webp():
    assert photos.detect_image_ext(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"


def test_detect_heic():
    data = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00"
    assert photos.detect_image_ext(data) == "heic"


def test_detect_rejects_non_image():
    assert photos.detect_image_ext(b"not an image at all") is None
    assert photos.detect_image_ext(b"") is None
    assert photos.detect_image_ext(b"<html>") is None


# ── photo_file_for_url (path-traversal safety) ──────────────────────────────

def test_photo_file_for_valid_url(tmp_path):
    hass = _hass(tmp_path)
    name = "0123456789abcdef0123456789abcdef.jpg"
    p = photos.photo_file_for_url(hass, f"/api/taskmate/photo/{name}")
    assert p == Path(tmp_path, photos.PHOTOS_DIR, name)


def test_photo_file_for_url_rejects_foreign_url(tmp_path):
    hass = _hass(tmp_path)
    assert photos.photo_file_for_url(hass, "http://example.com/x.jpg") is None
    assert photos.photo_file_for_url(hass, "/local/snap.jpg") is None
    assert photos.photo_file_for_url(hass, "") is None


def test_photo_file_for_url_rejects_traversal(tmp_path):
    hass = _hass(tmp_path)
    assert photos.photo_file_for_url(hass, "/api/taskmate/photo/../secrets.yaml") is None
    assert photos.photo_file_for_url(hass, "/api/taskmate/photo/..%2f..%2fx.jpg") is None
    assert photos.photo_file_for_url(hass, "/api/taskmate/photo/evil.txt") is None
    assert photos.photo_file_for_url(hass, "/api/taskmate/photo/sub/dir.jpg") is None


# ── sign_photo_url (foreign/blank passthrough — no HA needed) ───────────────

def test_sign_photo_url_passes_through_foreign(tmp_path):
    hass = _hass(tmp_path)
    # Foreign/blank URLs return unchanged without touching async_sign_path.
    assert photos.sign_photo_url(hass, "") == ""
    assert photos.sign_photo_url(hass, "http://example.com/x.jpg") == "http://example.com/x.jpg"
    assert photos.sign_photo_url(hass, "/local/snap.jpg") == "/local/snap.jpg"


# ── async_delete_photo ──────────────────────────────────────────────────────

def test_delete_photo_removes_file(tmp_path):
    hass = _hass(tmp_path)
    name = "0123456789abcdef0123456789abcdef.jpg"
    directory = Path(tmp_path, photos.PHOTOS_DIR)
    directory.mkdir(parents=True)
    f = directory / name
    f.write_bytes(b"data")
    run(photos.async_delete_photo(hass, f"/api/taskmate/photo/{name}"))
    assert not f.exists()


def test_delete_photo_missing_file_is_noop(tmp_path):
    hass = _hass(tmp_path)
    name = "0123456789abcdef0123456789abcdef.jpg"
    run(photos.async_delete_photo(hass, f"/api/taskmate/photo/{name}"))  # no raise


def test_delete_photo_ignores_foreign_url(tmp_path):
    hass = _hass(tmp_path)
    run(photos.async_delete_photo(hass, "http://example.com/x.jpg"))  # no raise, no exec
    hass.async_add_executor_job.assert_not_called()
