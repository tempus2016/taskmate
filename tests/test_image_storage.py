"""Tests for the pure chore-image storage helpers (custom_components.taskmate.images)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from custom_components.taskmate import images


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

    hass.async_add_executor_job = _exec
    return hass


JPEG = b"\xff\xd8\xff" + b"\x00" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
WEBP = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 32
HEIC = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 32


def test_detect_allowed_ext_accepts_web_formats():
    assert images.detect_allowed_ext(JPEG) == "jpg"
    assert images.detect_allowed_ext(PNG) == "png"
    assert images.detect_allowed_ext(WEBP) == "webp"


def test_detect_allowed_ext_rejects_heic():
    # photos.py accepts HEIC for evidence, but a browser can't render it and a
    # chore image is only ever displayed, so storing one yields a broken image.
    from custom_components.taskmate import photos

    assert photos.detect_image_ext(HEIC) == "heic"
    assert images.detect_allowed_ext(HEIC) is None


def test_detect_allowed_ext_rejects_non_images():
    assert images.detect_allowed_ext(b"not an image at all") is None
    assert images.detect_allowed_ext(b"") is None


def test_is_taskmate_image_url_accepts_well_formed():
    assert images.is_taskmate_image_url("/api/taskmate/image/" + "a" * 32 + ".jpg")


def test_is_taskmate_image_url_rejects_everything_else():
    for bad in (
        "",
        None,
        "/api/taskmate/photo/" + "a" * 32 + ".jpg",  # the OTHER store
        "/api/taskmate/image/../../secret.txt",
        "/api/taskmate/image/sub/dir.jpg",
        "/api/taskmate/image/short.jpg",
        "/api/taskmate/image/" + "a" * 32 + ".heic",
        "/api/taskmate/image/" + "a" * 32 + ".svg",
        "javascript:alert(1)",
        "https://evil.example/x.jpg",
    ):
        assert not images.is_taskmate_image_url(bad), bad


def test_image_file_for_url_maps_into_the_images_dir(tmp_path):
    hass = _hass(tmp_path)
    name = "b" * 32 + ".png"
    path = images.image_file_for_url(hass, f"/api/taskmate/image/{name}")
    assert path == Path(tmp_path, "taskmate_images", name)


def test_image_file_for_url_rejects_traversal(tmp_path):
    hass = _hass(tmp_path)
    assert images.image_file_for_url(hass, "/api/taskmate/image/../../etc/passwd") is None
    assert images.image_file_for_url(hass, "/api/taskmate/photo/" + "a" * 32 + ".jpg") is None


def test_async_delete_image_removes_the_file(tmp_path):
    hass = _hass(tmp_path)
    directory = Path(tmp_path, "taskmate_images")
    directory.mkdir(parents=True)
    name = "c" * 32 + ".jpg"
    (directory / name).write_bytes(JPEG)
    run(images.async_delete_image(hass, f"/api/taskmate/image/{name}"))
    assert not (directory / name).exists()


def test_async_delete_image_ignores_foreign_and_missing(tmp_path):
    hass = _hass(tmp_path)
    # Must not raise, and must not touch the photo store.
    run(images.async_delete_image(hass, "/api/taskmate/photo/" + "a" * 32 + ".jpg"))
    run(images.async_delete_image(hass, "/api/taskmate/image/" + "d" * 32 + ".jpg"))
    run(images.async_delete_image(hass, ""))


def test_total_images_bytes(tmp_path):
    hass = _hass(tmp_path)
    assert images.total_images_bytes(hass) == 0
    directory = Path(tmp_path, "taskmate_images")
    directory.mkdir(parents=True)
    (directory / ("e" * 32 + ".jpg")).write_bytes(b"x" * 100)
    (directory / "ignored.txt").write_bytes(b"y" * 999)
    assert images.total_images_bytes(hass) == 100


def test_sign_image_url_passes_through_foreign_urls(tmp_path):
    hass = _hass(tmp_path)
    assert images.sign_image_url(hass, "") == ""
    assert images.sign_image_url(hass, "https://x/y.jpg") == "https://x/y.jpg"
