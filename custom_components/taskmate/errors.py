"""Translated user-facing errors.

``TaskMateError`` is what coordinator and service code raises when it refuses
an action (unknown id, sold out, switched off, ...). It is both:

* a ``ValueError`` — so every existing ``except ValueError`` and test that
  expects one keeps working; and
* a ``ServiceValidationError`` carrying ``translation_domain`` /
  ``translation_key`` / ``translation_placeholders`` — so Home Assistant's own
  UI, and the TaskMate cards and panel (via ``__taskmate_error_text``), show
  the message in the user's language.

The English text (what ``str(err)`` returns, what the log shows and what older
frontends display) is read from this integration's ``translations/en.json``
``exceptions`` section, so each message is written once.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _load_english() -> dict[str, str]:
    path = Path(__file__).parent / "translations" / "en.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _LOGGER.warning("TaskMate: could not read %s; errors will show their keys", path)
        return {}
    return {key: str(entry.get("message", "")) for key, entry in (data.get("exceptions") or {}).items()}


# Read once at import (integration import runs off the event loop).
_ENGLISH: dict[str, str] = _load_english()


def english_message(key: str, placeholders: dict[str, str] | None = None) -> str:
    """The English text for an exception key, with its placeholders filled."""
    template = _ENGLISH.get(key)
    if template is None:
        return key
    if not placeholders:
        return template
    try:
        return template.format(**placeholders)
    except (KeyError, IndexError, ValueError):
        return template


class TaskMateError(ServiceValidationError, ValueError):
    """A refused action, reported in the user's language."""

    def __init__(self, key: str, **placeholders: Any) -> None:
        ph = {name: "" if value is None else str(value) for name, value in placeholders.items()}
        super().__init__(
            english_message(key, ph),
            translation_domain=DOMAIN,
            translation_key=key,
            translation_placeholders=ph,
        )
        # Kept on the instance as plain attributes too, so code (and the
        # WebSocket error helper) can read them whichever base set them.
        self.translation_domain = DOMAIN
        self.translation_key = key
        self.translation_placeholders = ph


def error_translation(err: BaseException) -> dict[str, Any]:
    """Translation fields for ``connection.send_error`` (empty when there are none)."""
    key = getattr(err, "translation_key", None)
    if not key:
        return {}
    return {
        "translation_domain": getattr(err, "translation_domain", None) or DOMAIN,
        "translation_key": key,
        "translation_placeholders": getattr(err, "translation_placeholders", None) or {},
    }


def send_translated_error(connection: Any, msg_id: int, code: str, key: str, **placeholders: Any) -> None:
    """``connection.send_error`` for a refused WebSocket command, translated like ``TaskMateError``."""
    err = TaskMateError(key, **placeholders)
    connection.send_error(msg_id, code, str(err), **error_translation(err))


def error_body(key: str, **placeholders: Any) -> dict[str, Any]:
    """JSON body for a refused HTTP request (uploads): the English message plus
    the translation fields the frontend's ``__taskmate_error_text`` reads."""
    err = TaskMateError(key, **placeholders)
    return {"message": str(err), **error_translation(err)}
