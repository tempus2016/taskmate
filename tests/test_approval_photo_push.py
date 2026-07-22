"""Evidence photo in the approval push (#686).

A parent approving "tidy your room" from the lock screen should be able to see
the room. The photo is signed before it reaches the notifier, because the
companion app fetches attachments without the user's bearer token.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coord_notifications import NotificationCoordinator

SIGNED = "/api/taskmate/photo/abc.jpg?authSig=tok"


def _notifier():
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    storage = MagicMock()
    return NotificationCoordinator(hass, storage), hass


def _meta(actionable=True):
    meta = MagicMock()
    meta.id = "pending_chore_approval"
    meta.actionable = actionable
    return meta


async def _send(service, context, actionable=True):
    notifier, hass = _notifier()
    await notifier._send_to(service, "Ella completed 'Tidy room'", _meta(actionable), context)
    assert hass.services.async_call.await_count == 1
    return hass.services.async_call.await_args[0][2]


class TestPhotoAttachment:
    @pytest.mark.asyncio
    async def test_photo_is_attached_for_the_mobile_app(self):
        data = await _send("mobile_app_phone", {"entry_id": "c1", "photo_url": SIGNED})
        assert data["data"]["image"] == SIGNED

    @pytest.mark.asyncio
    async def test_ios_attachment_form_is_sent_too(self):
        """Android reads data.image, iOS reads data.attachment.url — send both
        so one payload works on either platform."""
        data = await _send("mobile_app_phone", {"entry_id": "c1", "photo_url": SIGNED})
        assert data["data"]["attachment"]["url"] == SIGNED

    @pytest.mark.asyncio
    async def test_approve_reject_actions_survive_the_photo(self):
        data = await _send("mobile_app_phone", {"entry_id": "c1", "photo_url": SIGNED})
        actions = [a["action"] for a in data["data"]["actions"]]
        assert actions == ["TASKMATE_APPROVE_c1", "TASKMATE_REJECT_c1"]
        assert data["data"]["tag"]

    @pytest.mark.asyncio
    async def test_no_photo_means_no_attachment_keys(self):
        data = await _send("mobile_app_phone", {"entry_id": "c1", "photo_url": ""})
        assert "image" not in data["data"]
        assert "attachment" not in data["data"]

    @pytest.mark.asyncio
    async def test_non_mobile_backends_get_no_attachment(self):
        """Telegram/email/persistent would render a raw payload, not a picture."""
        data = await _send("telegram", {"entry_id": "c1", "photo_url": SIGNED})
        assert "data" not in data

    @pytest.mark.asyncio
    async def test_photo_without_an_entry_id_still_attaches(self):
        """No entry id means no action buttons, but the picture is still useful."""
        data = await _send("mobile_app_phone", {"photo_url": SIGNED})
        assert data["data"]["image"] == SIGNED

    @pytest.mark.asyncio
    async def test_non_actionable_type_can_still_carry_a_photo(self):
        data = await _send("mobile_app_phone", {"photo_url": SIGNED}, actionable=False)
        assert data["data"]["image"] == SIGNED

    @pytest.mark.asyncio
    async def test_message_is_unchanged_by_the_photo(self):
        data = await _send("mobile_app_phone", {"entry_id": "c1", "photo_url": SIGNED})
        assert data["message"] == "Ella completed 'Tidy room'"


class TestSigning:
    def test_context_signs_the_photo_url(self):
        """An unsigned URL 401s for the companion app, so signing must happen
        before the notifier sees it."""
        source = (
            __import__("pathlib").Path(__file__).resolve().parent.parent
            / "custom_components" / "taskmate" / "coord_points.py"
        ).read_text(encoding="utf-8")
        assert "photos.sign_photo_url(self.hass, photo_url)" in source

    def test_completion_photo_is_passed_to_the_notifier(self):
        source = (
            __import__("pathlib").Path(__file__).resolve().parent.parent
            / "custom_components" / "taskmate" / "coord_chores.py"
        ).read_text(encoding="utf-8")
        assert "photo_url=completion.photo_url" in source


class TestSigningIsNeverFatal:
    def test_signing_import_is_inside_the_try(self):
        """sign_photo_url runs on the completion path now. An ImportError
        escaping it would fail the completion itself, which is precisely what
        its "never break delivery" contract exists to prevent."""
        source = (
            __import__("pathlib").Path(__file__).resolve().parent.parent
            / "custom_components" / "taskmate" / "photos.py"
        ).read_text(encoding="utf-8")
        body = source[source.index("def sign_photo_url"):source.index("async def async_delete_photo")]
        try_at = body.index("try:")
        import_at = body.index("from homeassistant.components.http.auth import async_sign_path")
        assert try_at < import_at, "the HA import must sit inside the try block"

    def test_unsignable_url_falls_back_to_the_original(self):
        from custom_components.taskmate import photos
        assert photos.sign_photo_url(None, "/api/taskmate/photo/x.jpg") == "/api/taskmate/photo/x.jpg"

    def test_foreign_urls_are_returned_untouched(self):
        from custom_components.taskmate import photos
        assert photos.sign_photo_url(None, "https://evil.example/x.jpg") == "https://evil.example/x.jpg"
