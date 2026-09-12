"""The evidence-photo upload view's resource limits (source-level wiring).

aiohttp is not installed in the test environment, so — as with
``test_image_views.py`` — this asserts on the wiring in the source and leaves
the behaviour to ``test_photo_storage.py`` (the limiter itself) and the live
ha-dev run.
"""

from __future__ import annotations

import pathlib

SRC = (pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "http_photos.py").read_text(
    encoding="utf-8"
)


def test_upload_is_rate_limited_per_user():
    assert "photos.UploadRateLimiter" in SRC
    assert "self._limiter.check(user_id)" in SRC
    assert "TOO_MANY_REQUESTS" in SRC


def test_upload_bounds_concurrent_bodies():
    """Each in-flight upload can buffer MAX_UPLOAD_BYTES, so cap how many run."""
    assert "asyncio.Semaphore(self.MAX_CONCURRENT_UPLOADS)" in SRC
    assert "async with self._slots:" in SRC


def test_disk_budget_is_checked_before_reading_a_body():
    """The budget check must not sit only after megabytes are already buffered."""
    pre = SRC.index("Check the disk budget before accepting a body")
    multipart = SRC.index("await request.multipart()")
    assert pre < multipart


def test_rate_limit_is_keyed_on_the_requesting_user():
    assert 'user = request.get("hass_user")' in SRC
    assert 'user_id = getattr(user, "id", "") or "anonymous"' in SRC
