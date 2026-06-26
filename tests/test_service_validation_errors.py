"""Coordinator ValueErrors surface as clean ServiceValidationErrors.

Coordinator methods raise ``ValueError`` for bad/rejected input (locked
avatar, insufficient gift balance, unknown id, ...). The service layer wraps
handlers in ``_safe`` so the frontend/WebSocket caller gets a clean failure
result with the message instead of an unhandled error + traceback. A handler
that already raises ``ServiceValidationError`` must pass through untouched.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol

import custom_components.taskmate as tm


async def _registered_schemas() -> dict:
    """Register services against a fake hass and capture each service's schema.

    Registration only stores closures; it does not touch the coordinator, so a
    minimal fake hass is enough to inspect the real ``vol.Schema`` objects.
    """
    schemas: dict = {}

    class _Services:
        def async_register(self, domain, name, handler, schema=None):
            schemas[name] = schema

    await tm._async_register_services(SimpleNamespace(services=_Services()))
    return schemas


@pytest.mark.asyncio
async def test_value_error_becomes_service_validation_error():
    handler = AsyncMock(side_effect=ValueError("That avatar is not unlocked yet"))
    wrapped = tm._safe(handler)
    with pytest.raises(tm.ServiceValidationError, match="not unlocked yet"):
        await wrapped(object())


@pytest.mark.asyncio
async def test_clean_call_passes_through():
    handler = AsyncMock(return_value=None)
    call = object()
    await tm._safe(handler)(call)
    handler.assert_awaited_once_with(call)


@pytest.mark.asyncio
async def test_service_validation_error_not_double_wrapped():
    """A handler that already raises ServiceValidationError is left as-is."""
    original = tm.ServiceValidationError("already clean")
    handler = AsyncMock(side_effect=original)
    with pytest.raises(tm.ServiceValidationError) as excinfo:
        await tm._safe(handler)(object())
    assert excinfo.value is original


def _schema_entry(schema, key):
    """Return (marker, validator) for `key` in a vol.Schema, or (None, None).

    Inspecting the schema avoids running the cv.* validators, which are mocked
    out in the test harness; voluptuous itself is real.
    """
    for marker, validator in schema.schema.items():
        if getattr(marker, "schema", marker) == key:
            return marker, validator
    return None, None


@pytest.mark.asyncio
async def test_add_chore_schema_accepts_difficulty():
    """The add_chore schema must whitelist `difficulty`. vol.Schema rejects
    unknown keys by default, so without the key the whole call would 400."""
    schema = (await _registered_schemas())[tm.SERVICE_ADD_CHORE]
    marker, validator = _schema_entry(schema, "difficulty")

    assert marker is not None, "add_chore schema is missing the 'difficulty' key"
    assert isinstance(marker, vol.Optional)
    assert marker.default() == tm.DEFAULT_DIFFICULTY
    # Constrained to the known tiers.
    assert isinstance(validator, vol.In)
    assert validator.container == tm.DIFFICULTY_TIERS


@pytest.mark.asyncio
async def test_complete_chore_schema_accepts_photo_url():
    """The complete_chore schema must accept the optional photo_url evidence."""
    schema = (await _registered_schemas())[tm.SERVICE_COMPLETE_CHORE]
    marker, _ = _schema_entry(schema, "photo_url")

    assert marker is not None, "complete_chore schema is missing 'photo_url'"
    assert isinstance(marker, vol.Optional)
