"""The chore-image HTTP views (#750).

These assert on the source text rather than importing the module: aiohttp is
not installed in the test environment and conftest does not stub it, which is
why no test imports ``http_photos`` either. The behaviour that can be tested
without aiohttp — the storage helpers the views delegate to — is covered by
``test_image_storage.py``.
"""
from __future__ import annotations

import pathlib
import re

from custom_components.taskmate import images

SRC = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components" / "taskmate" / "http_images.py"
).read_text(encoding="utf-8")


def test_views_are_bound_to_the_image_prefix():
    # url is `images.URL_PREFIX` / `images.URL_PREFIX + "/{filename}"`; assert
    # both the wiring and the value the wiring resolves to.
    assert "url = images.URL_PREFIX" in SRC
    assert 'url = images.URL_PREFIX + "/{filename}"' in SRC
    assert images.URL_PREFIX == "/api/taskmate/image"


def test_upload_view_is_admin_gated():
    # Chore editing is @_admin_only; an endpoint any household member could
    # write files through would be a step down from that posture.
    assert 'request.get("hass_user")' in SRC
    assert "is_admin" in SRC
    assert re.search(r"HTTPStatus\.FORBIDDEN", SRC)


def test_the_admin_check_precedes_any_body_read():
    # A 403 must not require streaming the upload first.
    assert SRC.index("is_admin") < SRC.index("await request.multipart()")


def test_upload_enforces_the_image_caps_not_the_photo_caps():
    assert "images.MAX_UPLOAD_BYTES" in SRC
    assert "images.MAX_TOTAL_BYTES" in SRC
    assert "photos.MAX_UPLOAD_BYTES" not in SRC
    assert images.MAX_UPLOAD_BYTES == 2 * 1024 * 1024
    assert images.MAX_TOTAL_BYTES == 64 * 1024 * 1024


def test_upload_sniffs_bytes_via_the_narrowed_detector():
    # Must use detect_allowed_ext (no HEIC), not photos.detect_image_ext.
    assert "images.detect_allowed_ext" in SRC
    assert "detect_image_ext" not in SRC


def test_upload_returns_an_image_url_key():
    # The panel reads body.image_url; "photo_url" here would silently no-op.
    assert '"image_url"' in SRC
    assert '"photo_url"' not in SRC


def test_serve_view_validates_the_filename_before_touching_disk():
    assert "images.FILENAME_RE.match(filename)" in SRC
    assert SRC.index("FILENAME_RE.match(filename)") < SRC.index("read_bytes()")


def test_registration_is_idempotent():
    assert "IMAGE_HTTP_VIEWS_REGISTERED" in SRC
    assert "def async_register_image_views" in SRC


def test_frontend_registers_the_image_views():
    frontend = (
        pathlib.Path(__file__).resolve().parent.parent
        / "custom_components" / "taskmate" / "frontend.py"
    ).read_text(encoding="utf-8")
    assert "async_register_image_views" in frontend, (
        "views that are never registered mean every image 404s"
    )
